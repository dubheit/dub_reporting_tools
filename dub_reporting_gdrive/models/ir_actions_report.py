import base64
import logging
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    """Extended report model with Google Drive template source.

    This module provides generic Google Drive integration for report templates.
    Files are synced to ir.attachment, which can then be used by any reporting
    module (Carbone, ILovePDF, etc.).
    """

    _inherit = 'ir.actions.report'

    # Google Drive Configuration
    gdrive_file_id = fields.Char(
        string="Google Drive File ID",
        help="The unique identifier of the file on Google Drive.",
    )
    gdrive_file_name = fields.Char(
        string="Google Drive File Name",
        readonly=True,
    )
    gdrive_file_url = fields.Char(
        string="Google Drive URL",
        compute='_compute_gdrive_file_url',
    )
    gdrive_mime_type = fields.Char(
        string="Original MIME Type",
        readonly=True,
        help="The MIME type of the file on Google Drive.",
    )

    # Synced Attachment
    gdrive_attachment_id = fields.Many2one(
        'ir.attachment',
        string="Synced Template",
        readonly=True,
        ondelete='set null',
        help="The attachment containing the synced template from Google Drive.",
    )

    # Sync Status
    gdrive_last_sync = fields.Datetime(
        string="Last Synchronized",
        readonly=True,
    )
    gdrive_last_modified = fields.Char(
        string="Last Modified on Drive",
        readonly=True,
    )
    gdrive_auto_sync = fields.Boolean(
        string="Auto-Sync",
        default=False,
        help="Automatically sync template when file changes on Google Drive.\n"
             "Requires webhook to be configured in Settings.",
    )
    gdrive_sync_status = fields.Selection(
        string="Sync Status",
        selection=[
            ('synced', 'Synchronized'),
            ('outdated', 'Outdated'),
            ('not_synced', 'Not Synced'),
            ('error', 'Error'),
        ],
        compute='_compute_gdrive_sync_status',
    )

    @api.depends('gdrive_file_id')
    def _compute_gdrive_file_url(self):
        """Compute Google Drive file URL."""
        for report in self:
            if report.gdrive_file_id:
                report.gdrive_file_url = f"https://drive.google.com/file/d/{report.gdrive_file_id}/view"
            else:
                report.gdrive_file_url = False

    @api.depends('gdrive_file_id', 'gdrive_last_sync', 'gdrive_attachment_id')
    def _compute_gdrive_sync_status(self):
        """Compute sync status."""
        for report in self:
            if not report.gdrive_file_id:
                report.gdrive_sync_status = False
            elif not report.gdrive_last_sync:
                report.gdrive_sync_status = 'not_synced'
            elif not report.gdrive_attachment_id:
                report.gdrive_sync_status = 'not_synced'
            else:
                report.gdrive_sync_status = 'synced'

    def action_select_gdrive_file(self):
        """Open Google Drive file picker wizard."""
        self.ensure_one()

        return {
            'name': _('Select Google Drive File'),
            'type': 'ir.actions.act_window',
            'res_model': 'gdrive.file.picker',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_report_id': self.id,
            },
        }

    def action_sync_from_gdrive(self):
        """Download template from Google Drive and save to attachment."""
        self.ensure_one()

        if not self.gdrive_file_id:
            raise UserError(_("No Google Drive file configured for this report."))

        _logger.info("Syncing template for report %s from Google Drive file %s",
                     self.name, self.gdrive_file_id)

        try:
            # Download file
            content, filename, mime_type = self.env['gdrive.service'].download_file(
                self.gdrive_file_id
            )

            # Get metadata for last modified time
            metadata = self.env['gdrive.service'].get_file_metadata(self.gdrive_file_id)

            # Create or update attachment
            attachment_vals = {
                'name': filename,
                'datas': base64.b64encode(content),
                'res_model': 'ir.actions.report',
                'res_id': self.id,
                'mimetype': mime_type,
            }

            if self.gdrive_attachment_id:
                # Update existing attachment
                self.gdrive_attachment_id.write(attachment_vals)
                attachment = self.gdrive_attachment_id
            else:
                # Create new attachment
                attachment = self.env['ir.attachment'].create(attachment_vals)

            # Update report
            self.write({
                'gdrive_attachment_id': attachment.id,
                'gdrive_file_name': metadata.get('name'),
                'gdrive_mime_type': metadata.get('mimeType'),
                'gdrive_last_sync': fields.Datetime.now(),
                'gdrive_last_modified': metadata.get('modifiedTime'),
            })

            _logger.info("Template synced successfully: %s (%d bytes)",
                         filename, len(content))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Template Synchronized'),
                    'message': _('Template "%s" has been updated from Google Drive.') % filename,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error("Failed to sync template from Google Drive: %s", e)
            raise UserError(_("Failed to sync template from Google Drive:\n%s") % str(e))

    def action_open_gdrive_file(self):
        """Open Google Drive file in browser."""
        self.ensure_one()

        if not self.gdrive_file_url:
            raise UserError(_("No Google Drive file configured."))

        return {
            'type': 'ir.actions.act_url',
            'url': self.gdrive_file_url,
            'target': 'new',
        }

    def action_save_to_gdrive(self):
        """Save current template to Google Drive as a new file."""
        self.ensure_one()

        # Check for template content
        template_content = None
        template_name = None
        mime_type = None

        # Get template from Google Drive attachment
        if self.gdrive_attachment_id:
            template_content = base64.b64decode(self.gdrive_attachment_id.datas)
            template_name = self.gdrive_attachment_id.name
            mime_type = self.gdrive_attachment_id.mimetype

        if not template_content:
            raise UserError(_("No template content to upload."))

        # Get upload folder from company settings
        company = self.env.company
        folder_id = company.gdrive_upload_folder_id

        if not folder_id:
            raise UserError(_(
                "Upload folder not configured.\n\n"
                "Go to Settings → Reporting Tools → Google Drive Templates "
                "and configure the Upload Folder ID."
            ))

        # Generate new filename with timestamp
        name_base, ext = template_name.rsplit('.', 1) if '.' in template_name else (template_name, 'docx')
        timestamp = fields.Datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename = f"{name_base}_odoo_{timestamp}.{ext}"

        _logger.info("Uploading template to Google Drive: %s", new_filename)

        # Upload to Google Drive
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
            'gdrive_last_sync': fields.Datetime.now(),
        })

        # Return notification with link to file
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Template Saved to Google Drive'),
                'message': _('Template saved as "%s"') % new_filename,
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Register webhook channel on create if auto-sync enabled."""
        records = super().create(vals_list)

        for record in records:
            if record.gdrive_auto_sync and record.gdrive_file_id:
                self.env['gdrive.sync.channel']._register_channel(record.gdrive_file_id)

        return records

    def write(self, vals):
        """Handle webhook channel updates on write."""
        # Track which records need channel updates
        needs_channel = []

        if 'gdrive_auto_sync' in vals or 'gdrive_file_id' in vals:
            for record in self:
                old_auto_sync = record.gdrive_auto_sync
                old_file_id = record.gdrive_file_id

                new_auto_sync = vals.get('gdrive_auto_sync', old_auto_sync)
                new_file_id = vals.get('gdrive_file_id', old_file_id)

                # Register channel if:
                # 1. auto-sync enabled AND file_id changed, OR
                # 2. auto-sync being turned ON and file_id exists
                if new_auto_sync and new_file_id:
                    file_changed = new_file_id != old_file_id
                    auto_sync_enabled = not old_auto_sync and new_auto_sync
                    if file_changed or auto_sync_enabled:
                        needs_channel.append((record, new_file_id))

                # If auto-sync disabled, stop existing channels
                if old_auto_sync and not new_auto_sync and old_file_id:
                    channels = self.env['gdrive.sync.channel'].search([
                        ('file_id', '=', old_file_id),
                        ('state', '=', 'active'),
                    ])
                    for channel in channels:
                        channel._stop_channel()

        result = super().write(vals)

        # Register new channels after write
        for record, file_id in needs_channel:
            self.env['gdrive.sync.channel']._register_channel(file_id)

        return result

    def unlink(self):
        """Stop webhook channels and delete attachment before deleting."""
        for record in self:
            if record.gdrive_file_id:
                channels = self.env['gdrive.sync.channel'].search([
                    ('file_id', '=', record.gdrive_file_id),
                    ('state', '=', 'active'),
                ])
                for channel in channels:
                    channel._stop_channel()

            # Delete associated attachment
            if record.gdrive_attachment_id:
                record.gdrive_attachment_id.unlink()

        return super().unlink()
