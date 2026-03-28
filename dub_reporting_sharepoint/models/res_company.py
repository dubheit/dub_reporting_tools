import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    """Extended company model with SharePoint/Microsoft configuration."""

    _inherit = 'res.company'

    # Authentication Method
    sharepoint_auth_method = fields.Selection(
        string="SharePoint Authentication",
        selection=[
            ('app', 'App Registration (Server-to-Server)'),
            ('oauth2', 'OAuth2 (Per-User)'),
        ],
        default='app',
        help="App Registration: shared access using Azure AD app credentials.\n"
             "OAuth2: each user connects their own Microsoft account."
    )

    # Azure AD App Registration
    sharepoint_tenant_id = fields.Char(
        string="Tenant ID",
        help="Azure AD Tenant ID (Directory ID).\n"
             "Find in: Azure Portal > Azure Active Directory > Overview"
    )
    sharepoint_client_id = fields.Char(
        string="Client ID",
        help="Application (client) ID from Azure AD App Registration.\n"
             "Find in: Azure Portal > App registrations > Your app > Overview"
    )
    sharepoint_client_secret = fields.Char(
        string="Client Secret",
        help="Client secret from Azure AD App Registration.\n"
             "Create in: Azure Portal > App registrations > Your app > Certificates & secrets"
    )

    # SharePoint Site Configuration
    sharepoint_site_id = fields.Char(
        string="SharePoint Site ID",
        help="Default SharePoint site ID for file operations.\n"
             "Leave empty to use OneDrive or specify per-report."
    )
    sharepoint_site_name = fields.Char(
        string="Site Name",
        readonly=True,
    )
    sharepoint_drive_id = fields.Char(
        string="Default Drive ID",
        help="Default document library (drive) ID.\n"
             "Leave empty to use the site's default drive."
    )
    sharepoint_drive_name = fields.Char(
        string="Drive Name",
        readonly=True,
    )

    # Upload Configuration
    sharepoint_upload_folder_id = fields.Char(
        string="Upload Folder ID",
        help="Folder ID where modified templates will be saved.\n"
             "Leave empty to save in root of the drive."
    )
    sharepoint_upload_folder_name = fields.Char(
        string="Upload Folder Name",
        readonly=True,
    )

    # Webhook Configuration
    sharepoint_webhook_enabled = fields.Boolean(
        string="Enable Auto-Sync",
        default=False,
        help="Automatically sync templates when files change on SharePoint.\n"
             "Requires a publicly accessible HTTPS URL."
    )
