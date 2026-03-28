import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class GDriveFilePicker(models.TransientModel):
    """Wizard for selecting a file from Google Drive."""

    _name = 'gdrive.file.picker'
    _description = 'Google Drive File Picker'

    report_id = fields.Many2one(
        'ir.actions.report',
        string="Report",
        required=True,
        ondelete='cascade',
    )
    search_query = fields.Char(
        string="Search",
        help="Search for files by name",
    )
    file_ids = fields.One2many(
        'gdrive.file.picker.line',
        'picker_id',
        string="Files",
    )
    selected_file_id = fields.Many2one(
        'gdrive.file.picker.line',
        string="Selected File",
    )
    page_token = fields.Char(
        string="Page Token",
        help="Token for loading more results",
    )
    has_more = fields.Boolean(
        string="Has More Results",
        compute='_compute_has_more',
    )

    @api.depends('page_token')
    def _compute_has_more(self):
        for wizard in self:
            wizard.has_more = bool(wizard.page_token)

    @api.model
    def default_get(self, fields_list):
        """Default get without loading files (loaded after create)."""
        return super().default_get(fields_list)

    @api.model_create_multi
    def create(self, vals_list):
        """Create wizard and load files."""
        wizards = super().create(vals_list)
        for wizard in wizards:
            wizard._load_files()
        return wizards

    def _load_files(self, query='', page_token=None):
        """Load files from Google Drive."""
        try:
            result = self.env['gdrive.service'].search_files(
                query=query,
                page_token=page_token,
            )

            # Create file lines
            for file_data in result.get('files', []):
                self.env['gdrive.file.picker.line'].create({
                    'picker_id': self.id,
                    **self._prepare_file_line(file_data),
                })

            self.page_token = result.get('nextPageToken')

        except UserError as e:
            _logger.warning("Failed to load GDrive files: %s", e)

    def _prepare_file_line(self, file_data):
        """Prepare values for a file picker line."""
        mime_type = file_data.get('mimeType', '')

        # Determine file type label
        if mime_type == 'application/vnd.google-apps.document':
            file_type = 'Google Docs'
        elif mime_type == 'application/vnd.google-apps.spreadsheet':
            file_type = 'Google Sheets'
        elif 'wordprocessingml' in mime_type:
            file_type = 'DOCX'
        elif 'spreadsheetml' in mime_type:
            file_type = 'XLSX'
        elif 'opendocument.text' in mime_type:
            file_type = 'ODT'
        elif 'opendocument.spreadsheet' in mime_type:
            file_type = 'ODS'
        else:
            file_type = mime_type.split('/')[-1].upper()

        return {
            'file_id': file_data.get('id'),
            'name': file_data.get('name'),
            'mime_type': mime_type,
            'file_type': file_type,
            'modified_time': file_data.get('modifiedTime'),
            'web_link': file_data.get('webViewLink'),
            'icon_link': file_data.get('iconLink'),
        }

    def action_search(self):
        """Search for files matching the query."""
        self.ensure_one()

        # Clear old results
        self.file_ids.unlink()

        # Load new results
        self._load_files(query=self.search_query or '')

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'gdrive.file.picker',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_load_more(self):
        """Load more results."""
        self.ensure_one()

        if not self.page_token:
            return

        # Load more files (appends to existing)
        self._load_files(
            query=self.search_query or '',
            page_token=self.page_token,
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'gdrive.file.picker',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_select(self):
        """Select the chosen file and update the report."""
        self.ensure_one()

        if not self.selected_file_id:
            raise UserError(_("Please select a file from the list."))

        selected = self.selected_file_id

        # Update report with selected file info
        vals = {
            'gdrive_file_id': selected.file_id,
            'gdrive_file_name': selected.name,
            'gdrive_mime_type': selected.mime_type,
        }

        # Set template source if the field exists (from dub_reporting_carbone)
        if hasattr(self.report_id, 'carbone_template_source'):
            vals['carbone_template_source'] = 'gdrive'

        self.report_id.write(vals)

        # Trigger initial sync to download the file
        self.report_id.action_sync_from_gdrive()

        return {'type': 'ir.actions.act_window_close'}


class GDriveFilePickerLine(models.TransientModel):
    """Line item for Google Drive file picker."""

    _name = 'gdrive.file.picker.line'
    _description = 'Google Drive File Picker Line'
    _order = 'name'

    picker_id = fields.Many2one(
        'gdrive.file.picker',
        string="Picker",
        required=True,
        ondelete='cascade',
    )
    file_id = fields.Char(
        string="File ID",
        required=True,
    )
    name = fields.Char(
        string="Name",
        required=True,
    )
    mime_type = fields.Char(
        string="MIME Type",
    )
    file_type = fields.Char(
        string="Type",
    )
    modified_time = fields.Char(
        string="Modified",
    )
    web_link = fields.Char(
        string="Link",
    )
    icon_link = fields.Char(
        string="Icon",
    )

    def action_select_this(self):
        """Select this file and update the report."""
        self.ensure_one()

        report = self.picker_id.report_id
        if not report:
            raise UserError(_("No report associated with this picker."))

        # Update report with selected file info
        vals = {
            'gdrive_file_id': self.file_id,
            'gdrive_file_name': self.name,
            'gdrive_mime_type': self.mime_type,
        }

        # Set template source if the field exists (from dub_reporting_carbone)
        if hasattr(report, 'carbone_template_source'):
            vals['carbone_template_source'] = 'gdrive'

        report.write(vals)

        # Trigger initial sync to download the file
        report.action_sync_from_gdrive()

        return {'type': 'ir.actions.act_window_close'}
