import base64
import logging
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    """Extended report model with SharePoint template source."""

    _inherit = 'ir.actions.report'

    # SharePoint Configuration
    sharepoint_drive_id = fields.Char(
        string="SharePoint Drive ID",
        help="The drive (document library) containing the file.",
    )
    sharepoint_item_id = fields.Char(
        string="SharePoint Item ID",
        help="The unique identifier of the file on SharePoint/OneDrive.",
    )
    sharepoint_file_name = fields.Char(
        string="SharePoint File Name",
        readonly=True,
    )
    sharepoint_file_url = fields.Char(
        string="SharePoint URL",
        compute='_compute_sharepoint_file_url',
    )
    sharepoint_mime_type = fields.Char(
        string="Original MIME Type",
        readonly=True,
    )

    # Synced Attachment
    sharepoint_attachment_id = fields.Many2one(
        'ir.attachment',
        string="Synced Template",
        readonly=True,
        ondelete='set null',
        help="The attachment containing the synced template from SharePoint.",
    )

    # Sync Status
    sharepoint_last_sync = fields.Datetime(
        string="Last Synchronized",
        readonly=True,
    )
    sharepoint_last_modified = fields.Char(
        string="Last Modified on SharePoint",
        readonly=True,
    )
    sharepoint_auto_sync = fields.Boolean(
        string="Auto-Sync",
        default=False,
        help="Automatically sync template when file changes on SharePoint.\n"
             "Requires webhook to be configured in Settings.",
    )
    sharepoint_sync_status = fields.Selection(
        string="Sync Status",
        selection=[
            ('synced', 'Synchronized'),
            ('outdated', 'Outdated'),
            ('not_synced', 'Not Synced'),
            ('error', 'Error'),
        ],
        compute='_compute_sharepoint_sync_status',
    )

    @api.depends('sharepoint_item_id', 'sharepoint_drive_id')
    def _compute_sharepoint_file_url(self):
        """Compute SharePoint file URL (web view)."""
        for report in self:
            # URL will be fetched from metadata if needed
            report.sharepoint_file_url = False

    @api.depends('sharepoint_item_id', 'sharepoint_last_sync', 'sharepoint_attachment_id')
    def _compute_sharepoint_sync_status(self):
        """Compute sync status."""
        for report in self:
            if not report.sharepoint_item_id:
                report.sharepoint_sync_status = False
            elif not report.sharepoint_last_sync:
                report.sharepoint_sync_status = 'not_synced'
            elif not report.sharepoint_attachment_id:
                report.sharepoint_sync_status = 'not_synced'
            else:
                report.sharepoint_sync_status = 'synced'

    def action_select_sharepoint_file(self):
        """Open SharePoint file picker wizard."""
        self.ensure_one()

        return {
            'name': _('Select SharePoint File'),
            'type': 'ir.actions.act_window',
            'res_model': 'sharepoint.file.picker',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_report_id': self.id,
            },
        }

    def action_sync_from_sharepoint(self):
        """Download template from SharePoint and save to attachment."""
        self.ensure_one()

        if not self.sharepoint_drive_id or not self.sharepoint_item_id:
            raise UserError(_("No SharePoint file configured for this report."))

        _logger.info("Syncing template for report %s from SharePoint item %s",
                     self.name, self.sharepoint_item_id)

        try:
            # Download file
            content, filename, mime_type = self.env['sharepoint.service'].download_file(
                self.sharepoint_drive_id,
                self.sharepoint_item_id,
            )

            # Get metadata for last modified time
            metadata = self.env['sharepoint.service'].get_file_metadata(
                self.sharepoint_drive_id,
                self.sharepoint_item_id,
            )

            # Create or update attachment
            attachment_vals = {
                'name': filename,
                'datas': base64.b64encode(content),
                'res_model': 'ir.actions.report',
                'res_id': self.id,
                'mimetype': mime_type,
            }

            if self.sharepoint_attachment_id:
                self.sharepoint_attachment_id.write(attachment_vals)
                attachment = self.sharepoint_attachment_id
            else:
                attachment = self.env['ir.attachment'].create(attachment_vals)

            # Update report
            self.write({
                'sharepoint_attachment_id': attachment.id,
                'sharepoint_file_name': metadata.get('name'),
                'sharepoint_mime_type': metadata.get('file', {}).get('mimeType'),
                'sharepoint_last_sync': fields.Datetime.now(),
                'sharepoint_last_modified': metadata.get('lastModifiedDateTime'),
            })

            _logger.info("Template synced successfully: %s (%d bytes)",
                         filename, len(content))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Template Synchronized'),
                    'message': _('Template "%s" has been updated from SharePoint.') % filename,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error("Failed to sync template from SharePoint: %s", e)
            raise UserError(_("Failed to sync template from SharePoint:\n%s") % str(e))

    def action_open_sharepoint_file(self):
        """Open SharePoint file in browser."""
        self.ensure_one()

        if not self.sharepoint_drive_id or not self.sharepoint_item_id:
            raise UserError(_("No SharePoint file configured."))

        try:
            metadata = self.env['sharepoint.service'].get_file_metadata(
                self.sharepoint_drive_id,
                self.sharepoint_item_id,
            )
            web_url = metadata.get('webUrl')

            if web_url:
                return {
                    'type': 'ir.actions.act_url',
                    'url': web_url,
                    'target': 'new',
                }

            raise UserError(_("Could not get SharePoint file URL."))

        except Exception as e:
            raise UserError(_("Failed to open SharePoint file: %s") % str(e))

    def action_save_to_sharepoint(self):
        """Save current template to SharePoint."""
        self.ensure_one()

        # Check for template content
        template_content = None
        template_name = None
        mime_type = None

        if self.sharepoint_attachment_id:
            template_content = base64.b64decode(self.sharepoint_attachment_id.datas)
            template_name = self.sharepoint_attachment_id.name
            mime_type = self.sharepoint_attachment_id.mimetype

        if not template_content:
            raise UserError(_("No template content to upload."))

        # Get upload configuration
        company = self.env.company
        drive_id = self.sharepoint_drive_id or company.sharepoint_drive_id
        folder_id = company.sharepoint_upload_folder_id or 'root'

        if not drive_id:
            raise UserError(_(
                "SharePoint Drive not configured.\n\n"
                "Go to Settings → Reporting Tools → SharePoint Templates "
                "and configure the Drive ID."
            ))

        # If we have an existing item and it's not a Microsoft native format, update it
        if self.sharepoint_item_id:
            try:
                _logger.info("Updating existing file on SharePoint: %s", self.sharepoint_item_id)

                result = self.env['sharepoint.service'].update_file(
                    drive_id,
                    self.sharepoint_item_id,
                    template_content,
                    mime_type,
                )

                self.write({
                    'sharepoint_last_sync': fields.Datetime.now(),
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
            except Exception as e:
                _logger.warning("Failed to update SharePoint file, creating new: %s", e)

        # Create new file
        timestamp = fields.Datetime.now().strftime('%Y%m%d_%H%M%S')
        name_base, ext = template_name.rsplit('.', 1) if '.' in template_name else (template_name, 'docx')
        new_filename = f"{name_base}_odoo_{timestamp}.{ext}"

        _logger.info("Creating new file on SharePoint: %s", new_filename)

        result = self.env['sharepoint.service'].upload_file(
            drive_id,
            folder_id,
            template_content,
            new_filename,
            mime_type,
        )

        self.write({
            'sharepoint_drive_id': drive_id,
            'sharepoint_item_id': result.get('id'),
            'sharepoint_file_name': result.get('name'),
            'sharepoint_mime_type': result.get('file', {}).get('mimeType'),
            'sharepoint_last_sync': fields.Datetime.now(),
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Template Saved to SharePoint'),
                'message': _('Template saved as "%s"') % new_filename,
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Register webhook subscription on create if auto-sync enabled."""
        records = super().create(vals_list)

        for record in records:
            if record.sharepoint_auto_sync and record.sharepoint_drive_id:
                # Ensure drive-level subscription exists
                self.env['sharepoint.subscription']._get_or_create_drive_subscription(
                    record.sharepoint_drive_id,
                )

        return records

    def write(self, vals):
        """Handle webhook subscription updates on write."""
        needs_subscription = []

        if 'sharepoint_auto_sync' in vals or 'sharepoint_drive_id' in vals:
            for record in self:
                old_auto_sync = record.sharepoint_auto_sync
                old_drive_id = record.sharepoint_drive_id

                new_auto_sync = vals.get('sharepoint_auto_sync', old_auto_sync)
                new_drive_id = vals.get('sharepoint_drive_id', old_drive_id)

                # Register drive subscription if:
                # 1. auto-sync enabled AND drive_id changed, OR
                # 2. auto-sync being turned ON and drive_id exists
                if new_auto_sync and new_drive_id:
                    drive_changed = new_drive_id != old_drive_id
                    auto_sync_enabled = not old_auto_sync and new_auto_sync
                    if drive_changed or auto_sync_enabled:
                        needs_subscription.append(new_drive_id)

        result = super().write(vals)

        # Register new drive subscriptions after write
        for drive_id in set(needs_subscription):
            self.env['sharepoint.subscription']._get_or_create_drive_subscription(drive_id)

        return result

    def unlink(self):
        """Delete attachment before deleting."""
        for record in self:
            if record.sharepoint_attachment_id:
                record.sharepoint_attachment_id.unlink()

        # Note: We don't stop drive subscriptions because other reports may use them
        return super().unlink()
