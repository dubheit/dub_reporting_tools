import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    """Settings page for Google Drive integration."""

    _inherit = 'res.config.settings'

    # Authentication Method
    gdrive_auth_method = fields.Selection(
        related='company_id.gdrive_auth_method',
        readonly=False,
    )

    # Service Account
    gdrive_service_account_file = fields.Binary(
        related='company_id.gdrive_service_account_file',
        readonly=False,
    )
    gdrive_service_account_filename = fields.Char(
        related='company_id.gdrive_service_account_filename',
        readonly=False,
    )
    gdrive_service_account_json = fields.Text(
        related='company_id.gdrive_service_account_json',
        readonly=False,
    )
    gdrive_service_account_email = fields.Char(
        related='company_id.gdrive_service_account_email',
        readonly=True,
    )
    gdrive_service_account_project = fields.Char(
        related='company_id.gdrive_service_account_project',
        readonly=True,
    )

    # OAuth2
    gdrive_client_id = fields.Char(
        related='company_id.gdrive_client_id',
        readonly=False,
    )
    gdrive_client_secret = fields.Char(
        related='company_id.gdrive_client_secret',
        readonly=False,
    )

    # Upload Configuration
    gdrive_upload_folder_id = fields.Char(
        related='company_id.gdrive_upload_folder_id',
        readonly=False,
    )
    gdrive_upload_folder_name = fields.Char(
        related='company_id.gdrive_upload_folder_name',
        readonly=True,
    )

    # Webhook
    gdrive_webhook_enabled = fields.Boolean(
        related='company_id.gdrive_webhook_enabled',
        readonly=False,
    )

    # Status (computed)
    gdrive_connection_status = fields.Selection(
        string="Connection Status",
        selection=[
            ('not_configured', 'Not Configured'),
            ('error', 'Error'),
            ('connected', 'Connected'),
        ],
        compute='_compute_gdrive_connection_status',
    )
    gdrive_connection_message = fields.Char(
        string="Status Message",
        compute='_compute_gdrive_connection_status',
    )

    @api.depends('gdrive_auth_method', 'gdrive_service_account_json', 'gdrive_client_id')
    def _compute_gdrive_connection_status(self):
        """Compute connection status based on configuration."""
        for record in self:
            if record.gdrive_auth_method == 'service_account':
                if not record.gdrive_service_account_json:
                    record.gdrive_connection_status = 'not_configured'
                    record.gdrive_connection_message = _("Service Account JSON not configured")
                else:
                    record.gdrive_connection_status = 'connected'
                    record.gdrive_connection_message = _("Service Account configured")
            else:
                if not record.gdrive_client_id or not record.gdrive_client_secret:
                    record.gdrive_connection_status = 'not_configured'
                    record.gdrive_connection_message = _("OAuth2 credentials not configured")
                else:
                    record.gdrive_connection_status = 'connected'
                    record.gdrive_connection_message = _("OAuth2 configured - users can connect")

    def action_test_gdrive_connection(self):
        """Test Google Drive API connection."""
        self.ensure_one()

        result = self.env['gdrive.service'].test_connection()

        if result['success']:
            message = _("Connection successful!\n\nAuthenticated as: %s") % result.get('email', 'Unknown')
            msg_type = 'success'
        else:
            message = _("Connection failed!\n\n%s") % result.get('message', 'Unknown error')
            msg_type = 'danger'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Google Drive Connection Test'),
                'message': message,
                'type': msg_type,
                'sticky': False,
            }
        }

    def set_values(self):
        """Override to force recompute of service account JSON and validate folder."""
        res = super().set_values()
        # Force recompute of service account fields when file is uploaded
        if self.gdrive_service_account_file:
            self.company_id._compute_service_account_json()
            self.company_id._compute_service_account_info()

        # Validate and get folder name when folder ID is set
        if self.gdrive_upload_folder_id:
            try:
                folder_info = self.env['gdrive.service'].get_file_metadata(
                    self.gdrive_upload_folder_id
                )
                self.company_id.gdrive_upload_folder_name = folder_info.get('name', '')
            except Exception as e:
                self.company_id.gdrive_upload_folder_name = _("(Invalid folder ID)")

        return res

    def action_connect_gdrive(self):
        """Start OAuth2 flow for current user."""
        self.ensure_one()

        if self.gdrive_auth_method != 'oauth2':
            raise UserError(_("OAuth2 authentication is not enabled."))

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        redirect_uri = f"{base_url}/gdrive/oauth2/callback"

        # Generate state for CSRF protection
        import secrets
        state = secrets.token_urlsafe(32)

        # Store state in session
        self.env['ir.config_parameter'].sudo().set_param(
            f'gdrive.oauth_state.{self.env.uid}',
            state,
        )

        auth_url = self.env['gdrive.service'].get_oauth_url(redirect_uri, state)

        return {
            'type': 'ir.actions.act_url',
            'url': auth_url,
            'target': 'self',
        }
