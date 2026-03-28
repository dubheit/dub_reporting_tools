import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SharePointFilePicker(models.TransientModel):
    """Wizard for selecting a file from SharePoint/OneDrive."""

    _name = 'sharepoint.file.picker'
    _description = 'SharePoint File Picker'

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
        'sharepoint.file.picker.line',
        'picker_id',
        string="Files",
    )
    selected_file_id = fields.Many2one(
        'sharepoint.file.picker.line',
        string="Selected File",
    )
    # Pagination
    next_link = fields.Char(
        string="Next Link",
        help="URL for loading more results",
    )
    has_more = fields.Boolean(
        string="Has More Results",
        compute='_compute_has_more',
    )

    @api.depends('next_link')
    def _compute_has_more(self):
        for wizard in self:
            wizard.has_more = bool(wizard.next_link)

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

    def _load_files(self, search_query=None):
        """Load files from SharePoint."""
        company = self.env.company

        if not company.sharepoint_drive_id:
            return

        try:
            service = self.env['sharepoint.service']

            if search_query:
                # Search mode
                items = service.search_files(
                    query=search_query,
                    drive_id=company.sharepoint_drive_id,
                )
                next_link = None
            else:
                # Browse root
                result = service.get_drive_items(
                    company.sharepoint_drive_id,
                    folder_id=None,
                )
                items = result.get('items', [])
                next_link = result.get('nextLink')

            # Create file lines
            for item in items:
                # Skip folders for now, only show files
                if 'folder' in item:
                    continue

                self.env['sharepoint.file.picker.line'].create({
                    'picker_id': self.id,
                    **self._prepare_file_line(item),
                })

            self.next_link = next_link

        except Exception as e:
            _logger.warning("Failed to load SharePoint files: %s", e)

    def _prepare_file_line(self, item):
        """Prepare values for a file picker line."""
        mime_type = item.get('file', {}).get('mimeType', '')

        # Determine file type label
        if 'wordprocessingml' in mime_type or 'word' in mime_type:
            file_type = 'DOCX'
        elif 'spreadsheetml' in mime_type or 'excel' in mime_type:
            file_type = 'XLSX'
        elif 'presentationml' in mime_type or 'powerpoint' in mime_type:
            file_type = 'PPTX'
        elif 'opendocument.text' in mime_type:
            file_type = 'ODT'
        elif 'opendocument.spreadsheet' in mime_type:
            file_type = 'ODS'
        elif 'opendocument.presentation' in mime_type:
            file_type = 'ODP'
        else:
            # Try to get from filename
            name = item.get('name', '')
            if '.' in name:
                file_type = name.rsplit('.', 1)[1].upper()
            else:
                file_type = mime_type.split('/')[-1].upper() if mime_type else 'Unknown'

        # Format modified time
        modified = item.get('lastModifiedDateTime', '')
        if modified:
            modified = modified[:16].replace('T', ' ')

        return {
            'item_id': item.get('id'),
            'name': item.get('name'),
            'mime_type': mime_type,
            'file_type': file_type,
            'modified_time': modified,
            'web_url': item.get('webUrl'),
            'size': item.get('size', 0),
        }

    def action_search(self):
        """Search for files matching the query."""
        self.ensure_one()

        # Clear old results
        self.file_ids.unlink()

        # Load new results
        self._load_files(search_query=self.search_query or '')

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sharepoint.file.picker',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_refresh(self):
        """Refresh file list."""
        self.ensure_one()

        # Clear old results
        self.file_ids.unlink()
        self.search_query = False

        # Load files
        self._load_files()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sharepoint.file.picker',
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
            'sharepoint_drive_id': self.env.company.sharepoint_drive_id,
            'sharepoint_item_id': selected.item_id,
            'sharepoint_file_name': selected.name,
            'sharepoint_mime_type': selected.mime_type,
        }

        # Set template source if the field exists (from dub_reporting_carbone_sharepoint)
        if hasattr(self.report_id, 'carbone_template_source'):
            vals['carbone_template_source'] = 'sharepoint'

        self.report_id.write(vals)

        # Trigger initial sync to download the file
        self.report_id.action_sync_from_sharepoint()

        return {'type': 'ir.actions.act_window_close'}


class SharePointFilePickerLine(models.TransientModel):
    """Line item for SharePoint file picker."""

    _name = 'sharepoint.file.picker.line'
    _description = 'SharePoint File Picker Line'
    _order = 'name'

    picker_id = fields.Many2one(
        'sharepoint.file.picker',
        string="Picker",
        required=True,
        ondelete='cascade',
    )
    item_id = fields.Char(
        string="Item ID",
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
    web_url = fields.Char(
        string="URL",
    )
    size = fields.Integer(
        string="Size",
    )

    def action_select_this(self):
        """Select this file and update the report."""
        self.ensure_one()

        report = self.picker_id.report_id
        if not report:
            raise UserError(_("No report associated with this picker."))

        company = self.env.company

        # Update report with selected file info
        vals = {
            'sharepoint_drive_id': company.sharepoint_drive_id,
            'sharepoint_item_id': self.item_id,
            'sharepoint_file_name': self.name,
            'sharepoint_mime_type': self.mime_type,
        }

        # Set template source if the field exists (from dub_reporting_carbone_sharepoint)
        if hasattr(report, 'carbone_template_source'):
            vals['carbone_template_source'] = 'sharepoint'

        report.write(vals)

        # Trigger initial sync to download the file
        report.action_sync_from_sharepoint()

        return {'type': 'ir.actions.act_window_close'}
