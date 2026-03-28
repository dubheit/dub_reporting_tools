from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Authentication Method
    sharepoint_auth_method = fields.Selection(
        related='company_id.sharepoint_auth_method',
        readonly=False,
    )

    # Azure AD App Registration
    sharepoint_tenant_id = fields.Char(
        related='company_id.sharepoint_tenant_id',
        readonly=False,
    )
    sharepoint_client_id = fields.Char(
        related='company_id.sharepoint_client_id',
        readonly=False,
    )
    sharepoint_client_secret = fields.Char(
        related='company_id.sharepoint_client_secret',
        readonly=False,
    )

    # SharePoint Site Configuration
    sharepoint_site_id = fields.Char(
        related='company_id.sharepoint_site_id',
        readonly=False,
    )
    sharepoint_site_name = fields.Char(
        related='company_id.sharepoint_site_name',
        readonly=True,
    )
    sharepoint_drive_id = fields.Char(
        related='company_id.sharepoint_drive_id',
        readonly=False,
    )
    sharepoint_drive_name = fields.Char(
        related='company_id.sharepoint_drive_name',
        readonly=True,
    )

    # Upload Configuration
    sharepoint_upload_folder_id = fields.Char(
        related='company_id.sharepoint_upload_folder_id',
        readonly=False,
    )
    sharepoint_upload_folder_name = fields.Char(
        related='company_id.sharepoint_upload_folder_name',
        readonly=True,
    )

    # Webhook Configuration
    sharepoint_webhook_enabled = fields.Boolean(
        related='company_id.sharepoint_webhook_enabled',
        readonly=False,
    )

    def action_test_sharepoint_connection(self):
        """Test SharePoint connection."""
        self.ensure_one()

        result = self.env['sharepoint.service'].test_connection()

        if result['success']:
            message = _("Connection successful!\nConnected as: %s") % result['email']
            msg_type = 'success'
        else:
            message = _("Connection failed:\n%s") % result['message']
            msg_type = 'danger'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('SharePoint Connection Test'),
                'message': message,
                'type': msg_type,
                'sticky': False,
            }
        }

    def action_connect_sharepoint(self):
        """Start OAuth2 flow to connect Microsoft account."""
        self.ensure_one()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        redirect_uri = f"{base_url}/sharepoint/oauth2/callback"

        # Generate state for CSRF protection
        import secrets
        state = secrets.token_urlsafe(32)

        # Store state in session
        self.env['ir.config_parameter'].sudo().set_param('sharepoint_oauth_state', state)

        auth_url = self.env['sharepoint.service'].get_oauth_url(redirect_uri, state)

        return {
            'type': 'ir.actions.act_url',
            'url': auth_url,
            'target': 'self',
        }

    def action_list_sharepoint_sites(self):
        """List available SharePoint sites."""
        self.ensure_one()

        try:
            sites = self.env['sharepoint.service'].get_sites()

            if not sites:
                raise UserError(_("No SharePoint sites found or accessible."))

            # Format site list for display
            site_list = "\n".join([
                f"• {s.get('displayName', 'Unknown')}: {s.get('id', 'N/A')}"
                for s in sites[:20]  # Limit to 20 sites
            ])

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('SharePoint Sites'),
                    'message': site_list,
                    'type': 'info',
                    'sticky': True,
                }
            }
        except Exception as e:
            raise UserError(_("Failed to list SharePoint sites: %s") % str(e))

    def action_list_sharepoint_drives(self):
        """List available drives for the configured SharePoint site."""
        self.ensure_one()

        site_id = self.sharepoint_site_id
        if not site_id:
            raise UserError(_("Please enter a Site ID first."))

        try:
            drives = self.env['sharepoint.service'].get_site_drives(site_id)

            if not drives:
                raise UserError(_("No document libraries found for this site."))

            # Format drive list for display
            drive_list = "\n".join([
                f"• {d.get('name', 'Unknown')}: {d.get('id', 'N/A')}"
                for d in drives[:20]
            ])

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('SharePoint Drives'),
                    'message': drive_list,
                    'type': 'info',
                    'sticky': True,
                }
            }
        except Exception as e:
            raise UserError(_("Failed to list SharePoint drives: %s") % str(e))
