# License LGPL-3

import logging
import os
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class CarboneStudioWizard(models.TransientModel):
    _name = 'carbone.studio.wizard'
    _description = 'Carbone Studio Record Selector'

    report_id = fields.Many2one(
        'ir.actions.report',
        string='Report',
        required=True,
        readonly=True,
    )
    model_name = fields.Char(
        string='Model',
        related='report_id.model',
        readonly=True,
    )
    record_id = fields.Many2oneReference(
        string='Sample Record',
        model_field='model_name',
        help='Select a record to use as sample data for the template preview',
    )

    def action_open_studio(self):
        """Open Carbone Studio with the selected record data."""
        self.ensure_one()

        report = self.report_id

        # Check for template using generic method (can be overridden by bridge modules)
        if not report._has_carbone_template():
            raise UserError(_("No template file configured for this report."))

        company = self.env.user.company_id

        # Get selected record or use first record if none selected
        record = None
        if self.record_id and report.model:
            record = self.env[report.model].browse(self.record_id).exists()
        if not record and report.model:
            record = self.env[report.model].search([], limit=1)

        # Generate sample data from selected record
        sample_data = {}
        _logger.info(f"Studio wizard: record={record}, carbone_json_data={bool(report.carbone_json_data)}")
        if record and report.carbone_json_data:
            try:
                # Evaluate JSON data expression directly (same as _prepare_render_payload)
                sample_data = safe_eval(
                    report.carbone_json_data.replace('\n', ''),
                    {'object': record}
                )
                _logger.info(f"Studio wizard: sample_data keys={list(sample_data.keys()) if sample_data else 'empty'}")
            except Exception as e:
                _logger.error(f"Failed to generate sample JSON data: {e}", exc_info=True)
        else:
            _logger.warning(f"Studio wizard: no record or no carbone_json_data configured")

        # Get template extension from filename using generic method
        template_extension = 'docx'  # default
        filename = report._get_carbone_template_filename()
        if filename:
            _name, ext = os.path.splitext(filename)
            if ext:
                template_extension = ext.lstrip('.').lower()

        # Upload template and get template ID
        try:
            template_id = report._upload_template()

            return {
                'type': 'ir.actions.client',
                'tag': 'carbone_studio_editor',
                'params': {
                    'report_id': report.id,
                    'template_id': template_id,
                    'template_extension': template_extension,
                    'api_url': company.carbone_api_url or 'https://api.carbone.io',
                    'access_token': company.carbone_access_token,
                    'sample_data': sample_data,
                    'record_name': record.display_name if record else None,
                },
            }
        except Exception as e:
            raise UserError(_("Failed to upload template to Carbone API: %s") % str(e))
