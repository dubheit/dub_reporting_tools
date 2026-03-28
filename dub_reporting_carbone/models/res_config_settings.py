import logging
import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    """Extended configuration settings with Carbone.io fields."""

    _inherit = 'res.config.settings'

    # API Configuration
    carbone_api_url = fields.Char(
        related="company_id.carbone_api_url",
        readonly=False
    )
    carbone_access_token = fields.Char(
        related="company_id.carbone_access_token",
        readonly=False
    )

    # API Status (computed, not stored)
    carbone_api_status = fields.Html(
        string="API Status",
        compute="_compute_carbone_api_status",
    )

    # Default Settings
    carbone_default_converter = fields.Selection(
        related="company_id.carbone_default_converter",
        readonly=False
    )
    carbone_default_timezone = fields.Selection(
        related="company_id.carbone_default_timezone",
        readonly=False
    )
    carbone_default_lang = fields.Selection(
        related="company_id.carbone_default_lang",
        readonly=False
    )

    # Studio Integration
    carbone_studio_enabled = fields.Boolean(
        related="company_id.carbone_studio_enabled",
        readonly=False,
    )
    carbone_studio_js_url = fields.Char(
        related="company_id.carbone_studio_js_url",
        readonly=False,
    )

    # Template Organization
    carbone_template_tag = fields.Char(
        related="company_id.carbone_template_tag",
        readonly=False
    )

    @api.depends('carbone_api_url', 'carbone_access_token')
    def _compute_carbone_api_status(self):
        """Compute API status by checking the Carbone /status endpoint."""
        for record in self:
            if not record.carbone_api_url:
                record.carbone_api_status = '<span class="text-muted">Configure API URL first</span>'
                continue

            try:
                # Check /status endpoint with v5 header
                status_url = f"{record.carbone_api_url.rstrip('/')}/status"
                headers = {'carbone-version': '5'}
                response = requests.get(status_url, headers=headers, timeout=5)

                if response.status_code == 200:
                    data = response.json()
                    status_info = []

                    # Service status
                    success = data.get('success', False)
                    if success:
                        status_info.append('<span class="text-success"><i class="fa fa-check-circle"/> Service Online</span>')
                    else:
                        status_info.append('<span class="text-danger"><i class="fa fa-times-circle"/> Service Error</span>')

                    # Version info
                    version = data.get('version')
                    if version:
                        status_info.append(f'<span class="text-muted ms-3">v{version}</span>')

                    record.carbone_api_status = ' '.join(status_info)
                else:
                    record.carbone_api_status = f'<span class="text-warning"><i class="fa fa-exclamation-triangle"/> HTTP {response.status_code}</span>'

            except requests.exceptions.Timeout:
                record.carbone_api_status = '<span class="text-danger"><i class="fa fa-clock-o"/> Connection Timeout</span>'
            except requests.exceptions.ConnectionError:
                record.carbone_api_status = '<span class="text-danger"><i class="fa fa-unlink"/> Connection Failed</span>'
            except Exception as e:
                _logger.warning("Carbone API status check failed: %s", e)
                record.carbone_api_status = f'<span class="text-danger"><i class="fa fa-exclamation-circle"/> Error</span>'

    def action_test_carbone_connection(self):
        """Test Carbone API connection and show detailed result."""
        self.ensure_one()

        if not self.carbone_api_url:
            raise UserError(_("Please configure the Carbone API URL first."))

        if not self.carbone_access_token:
            raise UserError(_("Please configure the Carbone Access Token first."))

        try:
            # Test /status endpoint with v5 header
            status_url = f"{self.carbone_api_url.rstrip('/')}/status"
            headers = {'carbone-version': '5'}
            response = requests.get(status_url, headers=headers, timeout=10)

            if response.status_code != 200:
                raise UserError(_("Carbone API returned HTTP %s") % response.status_code)

            data = response.json()
            if not data.get('success'):
                raise UserError(_("Carbone API reported an error: %s") % data.get('error', 'Unknown'))

            # Build success message
            message_parts = [_("Connection successful!")]

            version = data.get('version')
            if version:
                message_parts.append(_("Version: %s") % version)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Carbone API"),
                    'message': '\n'.join(message_parts),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except requests.exceptions.Timeout:
            raise UserError(_("Connection to Carbone API timed out. Please check the URL."))
        except requests.exceptions.ConnectionError:
            raise UserError(_("Could not connect to Carbone API. Please check the URL and your network connection."))

    def action_view_server_templates(self):
        """Open the Carbone server templates list."""
        return self.env['carbone.template.list'].action_fetch_templates()
