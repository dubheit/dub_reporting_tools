from datetime import datetime, timedelta

from odoo import models, fields, api


class ResUsersSettings(models.Model):
    """Extended user settings for Google Drive OAuth2 tokens."""

    _inherit = 'res.users.settings'

    gdrive_rtoken = fields.Char(
        string="Google Drive Refresh Token",
        copy=False,
        groups='base.group_system',
    )
    gdrive_token = fields.Char(
        string="Google Drive Access Token",
        copy=False,
        groups='base.group_system',
    )
    gdrive_token_validity = fields.Datetime(
        string="Token Validity",
        copy=False,
        groups='base.group_system',
    )

    def _set_gdrive_tokens(self, access_token, refresh_token, expires_in=3600):
        """Store OAuth2 tokens after authorization.

        Args:
            access_token: Google access token
            refresh_token: Google refresh token (may be None on refresh)
            expires_in: Token validity in seconds
        """
        values = {
            'gdrive_token': access_token,
            'gdrive_token_validity': datetime.now() + timedelta(seconds=expires_in),
        }
        if refresh_token:
            values['gdrive_rtoken'] = refresh_token

        self.sudo().write(values)

    def _clear_gdrive_tokens(self):
        """Clear Google Drive tokens (disconnect)."""
        self.sudo().write({
            'gdrive_rtoken': False,
            'gdrive_token': False,
            'gdrive_token_validity': False,
        })


class ResUsers(models.Model):
    """Extended user model with Google Drive connection status."""

    _inherit = 'res.users'

    gdrive_connected = fields.Boolean(
        string="Google Drive Connected",
        compute='_compute_gdrive_connected',
    )

    @api.depends('res_users_settings_id.gdrive_rtoken')
    def _compute_gdrive_connected(self):
        """Check if user has connected Google Drive."""
        for user in self:
            settings = user.res_users_settings_id
            user.gdrive_connected = bool(settings and settings.gdrive_rtoken)

    def action_disconnect_gdrive(self):
        """Disconnect Google Drive for current user."""
        self.ensure_one()
        if self.res_users_settings_id:
            self.res_users_settings_id._clear_gdrive_tokens()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Google Drive',
                'message': 'Google Drive disconnected successfully.',
                'type': 'success',
            }
        }
