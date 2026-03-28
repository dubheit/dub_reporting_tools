import logging
import werkzeug

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class GDriveOAuthController(http.Controller):
    """Controller for Google Drive OAuth2 flow."""

    @http.route('/gdrive/oauth2/callback', type='http', auth='user')
    def oauth_callback(self, code=None, state=None, error=None, **kwargs):
        """Handle OAuth2 callback from Google.

        Args:
            code: Authorization code from Google
            state: State parameter for CSRF verification
            error: Error message if authorization failed
        """
        # Check for errors
        if error:
            _logger.error("Google OAuth error: %s", error)
            return request.redirect('/web#action=display_notification&params=' +
                                    werkzeug.urls.url_quote_plus(
                                        '{"title":"Google Drive","message":"Authorization failed: %s","type":"danger"}' % error
                                    ))

        if not code:
            _logger.error("No authorization code received")
            return request.redirect('/web')

        # Verify state (CSRF protection)
        stored_state = request.env['ir.config_parameter'].sudo().get_param(
            f'gdrive.oauth_state.{request.uid}'
        )

        if state != stored_state:
            _logger.error("Invalid OAuth state: expected %s, got %s", stored_state, state)
            return request.redirect('/web#action=display_notification&params=' +
                                    werkzeug.urls.url_quote_plus(
                                        '{"title":"Google Drive","message":"Invalid state parameter. Please try again.","type":"danger"}'
                                    ))

        # Clear stored state
        request.env['ir.config_parameter'].sudo().set_param(
            f'gdrive.oauth_state.{request.uid}',
            False,
        )

        try:
            # Exchange code for tokens
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            redirect_uri = f"{base_url}/gdrive/oauth2/callback"

            tokens = request.env['gdrive.service'].exchange_code_for_tokens(code, redirect_uri)

            # Store tokens in user settings
            user = request.env.user
            settings = user.res_users_settings_id
            if not settings:
                settings = request.env['res.users.settings'].create({
                    'user_id': user.id,
                })

            settings._set_gdrive_tokens(
                access_token=tokens['access_token'],
                refresh_token=tokens.get('refresh_token'),
                expires_in=tokens.get('expires_in', 3600),
            )

            _logger.info("User %s connected Google Drive successfully", user.login)

            # Redirect to settings with success message
            return request.redirect('/web#action=display_notification&params=' +
                                    werkzeug.urls.url_quote_plus(
                                        '{"title":"Google Drive","message":"Google Drive connected successfully!","type":"success"}'
                                    ))

        except Exception as e:
            _logger.error("Failed to exchange OAuth code: %s", e)
            return request.redirect('/web#action=display_notification&params=' +
                                    werkzeug.urls.url_quote_plus(
                                        '{"title":"Google Drive","message":"Failed to connect: %s","type":"danger"}' % str(e)
                                    ))
