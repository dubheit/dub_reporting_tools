import logging

from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    """Bridge: Extend Carbone reports to support SharePoint templates."""

    _inherit = 'ir.actions.report'

    # Add SharePoint option to template source selection
    carbone_template_source = fields.Selection(
        selection_add=[('sharepoint', 'SharePoint/OneDrive')],
        ondelete={'sharepoint': 'set default'},
    )

    def _has_carbone_template(self):
        """Override to check for SharePoint attachment."""
        self.ensure_one()

        # Check parent sources first
        if super()._has_carbone_template():
            return True

        # Check SharePoint source
        if self.carbone_template_source == 'sharepoint':
            return bool(self.sharepoint_attachment_id)

        return False

    def _get_carbone_template_filename(self):
        """Override to return SharePoint attachment filename."""
        self.ensure_one()

        # If using SharePoint, get filename from attachment
        if self.carbone_template_source == 'sharepoint' and self.sharepoint_attachment_id:
            return self.sharepoint_attachment_id.name

        # Fall back to parent
        return super()._get_carbone_template_filename()

    def _get_carbone_template_data(self):
        """Override to return SharePoint attachment data."""
        self.ensure_one()

        # If using SharePoint, get data from attachment
        if self.carbone_template_source == 'sharepoint' and self.sharepoint_attachment_id:
            attachment = self.sharepoint_attachment_id
            template_data = attachment.datas
            if isinstance(template_data, bytes):
                template_data = template_data.decode('utf-8')
            template_name = attachment.name or f"{self.name}.docx"
            _logger.info(f"Using SharePoint template: {template_name}")
            return template_data, template_name

        # Fall back to parent
        return super()._get_carbone_template_data()

    def action_sync_from_sharepoint(self):
        """Override to also invalidate Carbone template cache after sync."""
        # Call parent method
        result = super().action_sync_from_sharepoint()

        # Invalidate Carbone template cache so it re-uploads next time
        if self.carbone_template_source == 'sharepoint':
            self.write({'carbone_template_id': False})
            _logger.info(f"Carbone template cache invalidated after SharePoint sync for: {self.name}")

        return result

    def action_save_template_from_studio(self, data_uri, extension):
        """Override to also update SharePoint attachment when source is sharepoint."""
        self.ensure_one()

        if not data_uri:
            _logger.warning("Empty dataURI received from Carbone Studio")
            return False

        # Always save to carbone_template_file
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

        # If using SharePoint source, also update the attachment
        if self.carbone_template_source == 'sharepoint' and self.sharepoint_attachment_id:
            # Get filename from attachment or generate one
            attachment = self.sharepoint_attachment_id
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

            # Auto-sync to SharePoint if enabled or if file exists on SharePoint
            if self.sharepoint_auto_sync or self.sharepoint_item_id:
                try:
                    _logger.info(f"Auto-syncing template to SharePoint for report: {self.name}")
                    self.action_save_to_sharepoint()
                except Exception as e:
                    _logger.warning(f"Failed to auto-sync to SharePoint: {e}")
                    # Don't raise - local save was successful

        _logger.info(f"Template saved from Carbone Studio for report: {self.name}")
        return True

    def action_save_to_sharepoint(self):
        """Save template to SharePoint.

        If the template originally came from SharePoint (sharepoint_item_id exists),
        updates the existing file. Otherwise creates a new file.
        """
        import base64
        from odoo import fields as odoo_fields

        self.ensure_one()

        # Check for template content from various sources
        template_content = None
        template_name = None
        mime_type = None

        # First try SharePoint attachment (modified locally)
        if self.sharepoint_attachment_id:
            template_content = base64.b64decode(self.sharepoint_attachment_id.datas)
            template_name = self.sharepoint_attachment_id.name
            mime_type = self.sharepoint_attachment_id.mimetype
        # Then try Carbone template file
        elif self.carbone_template_file:
            template_content = base64.b64decode(self.carbone_template_file)
            template_name = self.carbone_template_filename or f"{self.name}.docx"
            # Guess mime type from filename
            if template_name.endswith('.docx'):
                mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif template_name.endswith('.xlsx'):
                mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif template_name.endswith('.pptx'):
                mime_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            else:
                mime_type = 'application/octet-stream'

        if not template_content:
            raise UserError(_("No template content to upload."))

        # Check if we should update existing file or create new
        if self.sharepoint_item_id and self.sharepoint_drive_id:
            # Update existing file on SharePoint
            _logger.info("Updating existing file on SharePoint: %s", self.sharepoint_item_id)

            result = self.env['sharepoint.service'].update_file(
                self.sharepoint_drive_id,
                self.sharepoint_item_id,
                template_content,
                mime_type,
            )

            # Update sync timestamp
            self.write({
                'sharepoint_last_sync': odoo_fields.Datetime.now(),
                'sharepoint_last_modified': result.get('lastModifiedDateTime'),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Template Updated on SharePoint'),
                    'message': _('File "%s" has been updated.') % result.get('name'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            # Create new file
            company = self.env.company
            drive_id = company.sharepoint_drive_id
            folder_id = company.sharepoint_upload_folder_id or 'root'

            if not drive_id:
                raise UserError(_(
                    "SharePoint Drive not configured.\n\n"
                    "Go to Settings > Reporting Tools > SharePoint Templates "
                    "and configure the Drive ID."
                ))

            # Generate filename for new file
            name_base, ext = template_name.rsplit('.', 1) if '.' in template_name else (template_name, 'docx')
            new_filename = f"{name_base}.{ext}"

            _logger.info("Creating new file on SharePoint: %s", new_filename)

            result = self.env['sharepoint.service'].upload_file(
                drive_id,
                folder_id,
                template_content,
                new_filename,
                mime_type,
            )

            # Update report with new file ID
            self.write({
                'sharepoint_drive_id': drive_id,
                'sharepoint_item_id': result.get('id'),
                'sharepoint_file_name': result.get('name'),
                'sharepoint_mime_type': result.get('file', {}).get('mimeType'),
                'sharepoint_last_sync': odoo_fields.Datetime.now(),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Template Saved to SharePoint'),
                    'message': _('New file created: "%s"') % new_filename,
                    'type': 'success',
                    'sticky': False,
                }
            }
