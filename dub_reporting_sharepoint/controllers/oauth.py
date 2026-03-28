import logging
from datetime import datetime, timedelta

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class SharePointOAuthController(http.Controller):
    """Controller for Microsoft OAuth2 authentication flow."""

    @http.route('/sharepoint/oauth2/callback', type='http', auth='user')
    def oauth_callback(self, code=None, state=None, error=None, error_description=None, **kwargs):
        """Handle OAuth2 callback from Microsoft.

        Args:
            code: Authorization code to exchange for tokens
            state: State parameter for CSRF validation
            error: Error code if authorization failed
            error_description: Error description
        """
        if error:
            _logger.error("SharePoint OAuth error: %s - %s", error, error_description)
            return request.render('http_routing.http_error', {
                'status_code': 400,
                'status_message': f"SharePoint authorization failed: {error_description or error}",
            })

        if not code:
            return request.render('http_routing.http_error', {
                'status_code': 400,
                'status_message': "No authorization code received from Microsoft.",
            })

        # Validate state
        stored_state = request.env['ir.config_parameter'].sudo().get_param('sharepoint_oauth_state')
        if state != stored_state:
            _logger.warning("SharePoint OAuth state mismatch")
            return request.render('http_routing.http_error', {
                'status_code': 400,
                'status_message': "Invalid state parameter. Please try again.",
            })

        # Clear stored state
        request.env['ir.config_parameter'].sudo().set_param('sharepoint_oauth_state', '')

        try:
            # Exchange code for tokens
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            redirect_uri = f"{base_url}/sharepoint/oauth2/callback"

            tokens = request.env['sharepoint.service'].exchange_code_for_tokens(code, redirect_uri)

            # Store tokens in user settings
            user = request.env.user
            settings = user.res_users_settings_id

            if not settings:
                settings = request.env['res.users.settings'].create({
                    'user_id': user.id,
                })

            settings.sudo().write({
                'sharepoint_token': tokens['access_token'],
                'sharepoint_rtoken': tokens.get('refresh_token'),
                'sharepoint_token_validity': datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600)),
            })

            _logger.info("SharePoint OAuth completed for user %s", user.login)

            # Redirect to settings page
            return request.redirect('/odoo/settings#sharepoint')

        except Exception as e:
            _logger.error("SharePoint OAuth error: %s", e)
            return request.render('http_routing.http_error', {
                'status_code': 500,
                'status_message': f"Failed to complete SharePoint authorization: {str(e)}",
            })
