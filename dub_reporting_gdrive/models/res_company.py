import json
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    """Extended company model with Google Drive configuration."""

    _inherit = 'res.company'

    # Authentication Method
    gdrive_auth_method = fields.Selection(
        string="Google Drive Authentication",
        selection=[
            ('service_account', 'Service Account (Server-to-Server)'),
            ('oauth2', 'OAuth2 (Per-User)'),
        ],
        default='service_account',
        help="Service Account: shared access, files must be shared with SA email.\n"
             "OAuth2: each user connects their own Google account."
    )

    # Service Account Configuration
    gdrive_service_account_file = fields.Binary(
        string="Service Account JSON File",
        attachment=False,
        help="Upload the JSON credentials file downloaded from Google Cloud Console.\n"
             "Go to: Console > IAM > Service Accounts > Create Key > JSON"
    )
    gdrive_service_account_filename = fields.Char(
        string="Filename",
    )
    gdrive_service_account_json = fields.Text(
        string="Service Account JSON",
        compute='_compute_service_account_json',
        inverse='_inverse_service_account_json',
        store=True,
    )
    gdrive_service_account_email = fields.Char(
        string="Service Account Email",
        compute='_compute_service_account_info',
        store=True,
        help="Share your Drive files/folders with this email address."
    )
    gdrive_service_account_project = fields.Char(
        string="Project ID",
        compute='_compute_service_account_info',
        store=True,
    )

    # OAuth2 Configuration (company-level client credentials)
    gdrive_client_id = fields.Char(
        string="OAuth2 Client ID",
        help="Client ID from Google Cloud Console OAuth2 credentials."
    )
    gdrive_client_secret = fields.Char(
        string="OAuth2 Client Secret",
        help="Client Secret from Google Cloud Console OAuth2 credentials."
    )

    # Upload Configuration
    gdrive_upload_folder_id = fields.Char(
        string="Upload Folder ID",
        help="Google Drive folder ID where new templates will be saved.\n"
             "Create a folder on Drive and share it with the Service Account email."
    )
    gdrive_upload_folder_name = fields.Char(
        string="Upload Folder Name",
        readonly=True,
        help="Name of the configured upload folder."
    )

    # Webhook Configuration
    gdrive_webhook_enabled = fields.Boolean(
        string="Enable Auto-Sync",
        default=False,
        help="Automatically sync templates when files change on Google Drive.\n"
             "Requires a publicly accessible HTTPS URL."
    )

    @api.depends('gdrive_service_account_file')
    def _compute_service_account_json(self):
        """Convert uploaded binary file to JSON text."""
        import base64
        for company in self:
            if company.gdrive_service_account_file:
                try:
                    content = base64.b64decode(company.gdrive_service_account_file)
                    company.gdrive_service_account_json = content.decode('utf-8')
                except Exception:
                    company.gdrive_service_account_json = False
            else:
                company.gdrive_service_account_json = False

    def _inverse_service_account_json(self):
        """Allow direct setting of JSON text (converts to binary)."""
        import base64
        for company in self:
            if company.gdrive_service_account_json:
                content = company.gdrive_service_account_json.encode('utf-8')
                company.gdrive_service_account_file = base64.b64encode(content)
            else:
                company.gdrive_service_account_file = False

    @api.depends('gdrive_service_account_json')
    def _compute_service_account_info(self):
        """Extract email and project from Service Account JSON."""
        for company in self:
            email = False
            project = False

            if company.gdrive_service_account_json:
                try:
                    sa_info = json.loads(company.gdrive_service_account_json)
                    email = sa_info.get('client_email', '')
                    project = sa_info.get('project_id', '')
                except (json.JSONDecodeError, TypeError):
                    pass

            company.gdrive_service_account_email = email
            company.gdrive_service_account_project = project
