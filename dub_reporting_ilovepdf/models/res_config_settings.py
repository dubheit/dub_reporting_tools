import logging
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ILOVEPDF_API_URL = 'https://api.ilovepdf.com/v1'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ilovepdf_public_key = fields.Char(
        related='company_id.ilovepdf_public_key',
        readonly=False,
        string='ILovePDF Public Key'
    )
    ilovepdf_secret_key = fields.Char(
        related='company_id.ilovepdf_secret_key',
        readonly=False,
        string='ILovePDF Secret Key'
    )

    # API Status (computed, not stored)
    ilovepdf_api_status = fields.Html(
        string="API Status",
        compute="_compute_ilovepdf_api_status",
    )

    # Module installation field
    module_dub_reporting_ilovepdf_documents = fields.Boolean(
        string='Enable Documents Integration',
        help='Install the ILovePDF integration for Odoo Enterprise Documents module.'
    )

    @api.depends('ilovepdf_public_key')
    def _compute_ilovepdf_api_status(self):
        """Compute API status by testing authentication."""
        for record in self:
            if not record.ilovepdf_public_key:
                record.ilovepdf_api_status = '<span class="text-muted">Configure API credentials first</span>'
                continue

            try:
                response = requests.post(
                    f'{ILOVEPDF_API_URL}/auth',
                    json={'public_key': record.ilovepdf_public_key},
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )

                if response.status_code == 200:
                    record.ilovepdf_api_status = '<span class="text-success"><i class="fa fa-check-circle"/> Credentials Valid</span>'
                elif response.status_code == 401:
                    record.ilovepdf_api_status = '<span class="text-danger"><i class="fa fa-times-circle"/> Invalid Credentials</span>'
                else:
                    record.ilovepdf_api_status = f'<span class="text-warning"><i class="fa fa-exclamation-triangle"/> HTTP {response.status_code}</span>'

            except requests.exceptions.Timeout:
                record.ilovepdf_api_status = '<span class="text-danger"><i class="fa fa-clock-o"/> Connection Timeout</span>'
            except requests.exceptions.ConnectionError:
                record.ilovepdf_api_status = '<span class="text-danger"><i class="fa fa-unlink"/> Connection Failed</span>'
            except Exception as e:
                _logger.warning("ILovePDF API status check failed: %s", e)
                record.ilovepdf_api_status = '<span class="text-danger"><i class="fa fa-exclamation-circle"/> Error</span>'

    def action_test_ilovepdf_connection(self):
        """Test ILovePDF API connection and show detailed result."""
        self.ensure_one()

        if not self.ilovepdf_public_key:
            raise UserError(_("Please configure the ILovePDF Public Key first."))

        try:
            response = requests.post(
                f'{ILOVEPDF_API_URL}/auth',
                json={'public_key': self.ilovepdf_public_key},
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code == 401:
                raise UserError(_("Invalid API credentials. Please check your Public Key."))

            if response.status_code != 200:
                raise UserError(_("ILovePDF API returned HTTP %s") % response.status_code)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("ILovePDF API"),
                    'message': _("Connection successful! Credentials are valid."),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except requests.exceptions.Timeout:
            raise UserError(_("Connection to ILovePDF API timed out."))
        except requests.exceptions.ConnectionError:
            raise UserError(_("Could not connect to ILovePDF API. Please check your network connection."))
