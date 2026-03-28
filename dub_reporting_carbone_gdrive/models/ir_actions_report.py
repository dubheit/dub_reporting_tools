import logging

from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    """Bridge: Extend Carbone reports to support Google Drive templates."""

    _inherit = 'ir.actions.report'

    # Add Google Drive option to template source selection
    carbone_template_source = fields.Selection(
        selection_add=[('gdrive', 'Google Drive')],
        ondelete={'gdrive': 'set default'},
    )

    def _has_carbone_template(self):
        """Override to check for Google Drive attachment."""
        self.ensure_one()

        # Check parent sources first
        if super()._has_carbone_template():
            return True

        # Check Google Drive source
        if self.carbone_template_source == 'gdrive':
            return bool(self.gdrive_attachment_id)

        return False

    def _get_carbone_template_filename(self):
        """Override to return Google Drive attachment filename."""
        self.ensure_one()

        # If using Google Drive, get filename from attachment
        if self.carbone_template_source == 'gdrive' and self.gdrive_attachment_id:
            return self.gdrive_attachment_id.name

        # Fall back to parent
        return super()._get_carbone_template_filename()

    def _get_carbone_template_data(self):
        """Override to return Google Drive attachment data."""
        self.ensure_one()

        # If using Google Drive, get data from attachment
        if self.carbone_template_source == 'gdrive' and self.gdrive_attachment_id:
            attachment = self.gdrive_attachment_id
            template_data = attachment.datas
            if isinstance(template_data, bytes):
                template_data = template_data.decode('utf-8')
            template_name = attachment.name or f"{self.name}.odt"
            _logger.info(f"Using Google Drive template: {template_name}")
            return template_data, template_name

        # Fall back to parent
        return super()._get_carbone_template_data()

    def action_sync_from_gdrive(self):
        """Override to also invalidate Carbone template cache after sync."""
        # Call parent method
        result = super().action_sync_from_gdrive()

        # Invalidate Carbone template cache so it re-uploads next time
        if self.carbone_template_source == 'gdrive':
            self.write({'carbone_template_id': False})
            _logger.info(f"Carbone template cache invalidated after GDrive sync for: {self.name}")

        return result

    def action_save_template_from_studio(self, data_uri, extension):
        """Override to also update Google Drive attachment when source is gdrive."""
        self.ensure_one()

        if not data_uri:
            _logger.warning("Empty dataURI received from Carbone Studio")
            return False

        # Always save to carbone_template_file (call parent method indirectly)
        filename = self.carbone_template_filename or f"template.{extension}"

        # Ensure filename has correct extension
        if not filename.lower().endswith(f".{extension}"):
            name_part = filename.rsplit('.', 1)[0] if '.' in filename else filename
            filename = f"{name_part}.{extension}"

        # Save to carbone_template_file
        self.write({
            'carbone_template_file': data_uri,
            'carbone_template_filename': filename,
            'carbone_template_id': False,  # Invalidate cache since template changed
        })

        # If using Google Drive source, also update the attachment
        if self.carbone_template_source == 'gdrive' and self.gdrive_attachment_id:
            # Get filename from attachment or generate one
            attachment = self.gdrive_attachment_id
            att_filename = attachment.name or filename

            # Ensure correct extension
            if not att_filename.lower().endswith(f".{extension}"):
                name_part = att_filename.rsplit('.', 1)[0] if '.' in att_filename else att_filename
                att_filename = f"{name_part}.{extension}"

            # Update attachment content
            attachment.write({
                'datas': data_uri,
                'name': att_filename,
            })

            _logger.info(f"Template saved from Studio to attachment: {att_filename}")

            # Auto-sync to Google Drive if enabled or if file exists on Drive
            if self.gdrive_auto_sync or self.gdrive_file_id:
                try:
                    _logger.info(f"Auto-syncing template to Google Drive for report: {self.name}")
                    self.action_save_to_gdrive()
                except Exception as e:
                    _logger.warning(f"Failed to auto-sync to Google Drive: {e}")
                    # Don't raise - local save was successful

        _logger.info(f"Template saved from Carbone Studio for report: {self.name}")
        return True

    def action_save_to_gdrive(self):
        """Save template to Google Drive.

        If the template originally came from Drive (gdrive_file_id exists),
        updates the existing file. Otherwise creates a new file.
        """
        import base64
        from odoo import fields as odoo_fields

        self.ensure_one()

        # Check for template content from various sources
        template_content = None
        template_name = None
        mime_type = None

        # First try Google Drive attachment (modified locally)
        if self.gdrive_attachment_id:
            template_content = base64.b64decode(self.gdrive_attachment_id.datas)
            template_name = self.gdrive_attachment_id.name
            mime_type = self.gdrive_attachment_id.mimetype
        # Then try Carbone template file
        elif self.carbone_template_file:
            template_content = base64.b64decode(self.carbone_template_file)
            template_name = self.carbone_template_filename or f"{self.name}.docx"
            # Guess mime type from filename
            if template_name.endswith('.docx'):
                mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif template_name.endswith('.xlsx'):
                mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif template_name.endswith('.odt'):
                mime_type = 'application/vnd.oasis.opendocument.text'
            elif template_name.endswith('.ods'):
                mime_type = 'application/vnd.oasis.opendocument.spreadsheet'
            else:
                mime_type = 'application/octet-stream'

        if not template_content:
            raise UserError(_("No template content to upload."))

        # Google native formats that cannot be updated with binary content
        GOOGLE_NATIVE_MIMES = [
            'application/vnd.google-apps.document',
            'application/vnd.google-apps.spreadsheet',
            'application/vnd.google-apps.presentation',
        ]

        # Check if we should update existing file or create new
        # Cannot update Google native formats (Docs, Sheets) with binary content
        can_update = self.gdrive_file_id and self.gdrive_mime_type not in GOOGLE_NATIVE_MIMES

        if can_update:
            # Update existing binary file on Drive
            _logger.info("Updating existing file on Google Drive: %s", self.gdrive_file_id)

            result = self.env['gdrive.service'].update_file(
                file_id=self.gdrive_file_id,
                content=template_content,
                mime_type=mime_type,
            )

            # Update sync timestamp
            self.write({
                'gdrive_last_sync': odoo_fields.Datetime.now(),
                'gdrive_last_modified': result.get('modifiedTime'),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Template Updated on Google Drive'),
                    'message': _('File "%s" has been updated.') % result.get('name'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            # Create new file - either no existing file or original was Google native format
            is_google_native = self.gdrive_mime_type in GOOGLE_NATIVE_MIMES

            company = self.env.company
            folder_id = company.gdrive_upload_folder_id

            if not folder_id:
                raise UserError(_(
                    "Upload folder not configured.\n\n"
                    "Go to Settings > Reporting Tools > Google Drive Templates "
                    "and configure the Upload Folder ID."
                ))

            # Generate filename for new file
            name_base, ext = template_name.rsplit('.', 1) if '.' in template_name else (template_name, 'docx')
            # Add timestamp only if creating from Google native (to differentiate from original)
            if is_google_native:
                timestamp = odoo_fields.Datetime.now().strftime('%Y%m%d_%H%M%S')
                new_filename = f"{name_base}_{timestamp}.{ext}"
            else:
                new_filename = f"{name_base}.{ext}"

            _logger.info("Creating new file on Google Drive: %s (was_google_native=%s)",
                        new_filename, is_google_native)

            result = self.env['gdrive.service'].upload_file(
                content=template_content,
                filename=new_filename,
                mime_type=mime_type,
                folder_id=folder_id,
            )

            # Update report with new file ID
            self.write({
                'gdrive_file_id': result.get('id'),
                'gdrive_file_name': result.get('name'),
                'gdrive_mime_type': result.get('mimeType'),
                'gdrive_last_sync': odoo_fields.Datetime.now(),
            })

            # Different message if converting from Google native format
            if is_google_native:
                message = _('Google Doc converted to "%s" (native formats cannot be updated directly)') % new_filename
            else:
                message = _('New file created: "%s"') % new_filename

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Template Saved to Google Drive'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
