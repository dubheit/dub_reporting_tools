import json
import logging
from datetime import datetime, timedelta

from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import io
except ImportError:
    _logger.warning("Google API libraries not installed. Install with: pip install google-api-python-client google-auth google-auth-oauthlib")
    service_account = None
    Credentials = None
    Request = None
    build = None
    MediaIoBaseDownload = None


# Google Drive MIME types
GOOGLE_DOCS_MIME = 'application/vnd.google-apps.document'
GOOGLE_SHEETS_MIME = 'application/vnd.google-apps.spreadsheet'
DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
ODT_MIME = 'application/vnd.oasis.opendocument.text'
ODS_MIME = 'application/vnd.oasis.opendocument.spreadsheet'

# Supported template MIME types for search
SUPPORTED_MIME_TYPES = [
    GOOGLE_DOCS_MIME,
    GOOGLE_SHEETS_MIME,
    DOCX_MIME,
    XLSX_MIME,
    ODT_MIME,
    ODS_MIME,
]

# Export mappings for Google native formats
EXPORT_MAPPINGS = {
    GOOGLE_DOCS_MIME: {
        'mime': DOCX_MIME,
        'extension': '.docx',
    },
    GOOGLE_SHEETS_MIME: {
        'mime': XLSX_MIME,
        'extension': '.xlsx',
    },
}

# Google API scopes
# Note: drive.file allows creating files and accessing files created by this app
# drive scope gives full access to files shared with the service account
SCOPES = [
    'https://www.googleapis.com/auth/drive',  # Full access to files shared with the account
]


class GDriveService(models.AbstractModel):
    """Google Drive API service wrapper."""

    _name = 'gdrive.service'
    _description = 'Google Drive Service'

    def _check_libraries(self):
        """Check if required libraries are installed."""
        if build is None:
            raise UserError(_(
                "Google API libraries not installed.\n\n"
                "Install with:\n"
                "pip install google-api-python-client google-auth google-auth-oauthlib"
            ))

    @api.model
    def _get_service_account_credentials(self):
        """Get credentials from Service Account JSON."""
        self._check_libraries()
        company = self.env.company

        if not company.gdrive_service_account_json:
            raise UserError(_("Google Drive Service Account JSON not configured."))

        try:
            sa_info = json.loads(company.gdrive_service_account_json)
            credentials = service_account.Credentials.from_service_account_info(
                sa_info,
                scopes=SCOPES
            )
            return credentials
        except json.JSONDecodeError:
            raise UserError(_("Invalid Service Account JSON format."))
        except Exception as e:
            raise UserError(_("Failed to load Service Account credentials: %s") % str(e))

    @api.model
    def _get_oauth2_credentials(self, user=None):
        """Get OAuth2 credentials for a user."""
        self._check_libraries()
        user = user or self.env.user
        settings = user.res_users_settings_id

        if not settings or not settings.gdrive_rtoken:
            raise UserError(_(
                "Google Drive not connected for user %s.\n"
                "Please connect your Google account in Settings."
            ) % user.name)

        company = self.env.company
        if not company.gdrive_client_id or not company.gdrive_client_secret:
            raise UserError(_("Google Drive OAuth2 client credentials not configured."))

        credentials = Credentials(
            token=settings.gdrive_token,
            refresh_token=settings.gdrive_rtoken,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=company.gdrive_client_id,
            client_secret=company.gdrive_client_secret,
            scopes=SCOPES,
        )

        # Refresh if expired
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                # Update stored tokens
                settings.sudo().write({
                    'gdrive_token': credentials.token,
                    'gdrive_token_validity': datetime.now() + timedelta(seconds=3600),
                })
            except Exception as e:
                _logger.error("Failed to refresh Google token: %s", e)
                raise UserError(_(
                    "Failed to refresh Google access token.\n"
                    "Please reconnect your Google account."
                ))

        return credentials

    @api.model
    def _get_credentials(self, user=None):
        """Get credentials based on company auth method."""
        company = self.env.company

        if company.gdrive_auth_method == 'service_account':
            return self._get_service_account_credentials()
        else:
            return self._get_oauth2_credentials(user)

    @api.model
    def _get_service(self, user=None):
        """Get Google Drive API service."""
        credentials = self._get_credentials(user)
        return build('drive', 'v3', credentials=credentials)

    @api.model
    def test_connection(self):
        """Test Google Drive API connection."""
        try:
            service = self._get_service()
            # Try to get info about the authenticated user/service
            about = service.about().get(fields='user').execute()
            return {
                'success': True,
                'email': about.get('user', {}).get('emailAddress', 'Unknown'),
                'message': _("Connection successful!"),
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e),
            }

    @api.model
    def search_files(self, query='', page_token=None, page_size=50):
        """Search for files on Google Drive.

        Args:
            query: Search query string
            page_token: Token for pagination
            page_size: Number of results per page

        Returns:
            dict with 'files' list and 'nextPageToken'
        """
        service = self._get_service()

        # Build MIME type filter
        mime_filters = " or ".join([
            f"mimeType='{mime}'" for mime in SUPPORTED_MIME_TYPES
        ])

        # Build full query
        q = f"({mime_filters}) and trashed=false"
        if query:
            q = f"name contains '{query}' and {q}"

        try:
            response = service.files().list(
                q=q,
                pageSize=page_size,
                pageToken=page_token,
                fields='nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink, iconLink)',
                orderBy='modifiedTime desc',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()

            return {
                'files': response.get('files', []),
                'nextPageToken': response.get('nextPageToken'),
            }
        except Exception as e:
            _logger.error("Failed to search Google Drive: %s", e)
            raise UserError(_("Failed to search Google Drive: %s") % str(e))

    @api.model
    def get_file_metadata(self, file_id):
        """Get metadata for a specific file.

        Args:
            file_id: Google Drive file ID

        Returns:
            dict with file metadata
        """
        service = self._get_service()

        try:
            return service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, modifiedTime, size, webViewLink',
                supportsAllDrives=True,
            ).execute()
        except Exception as e:
            _logger.error("Failed to get file metadata: %s", e)
            raise UserError(_("Failed to get file metadata: %s") % str(e))

    @api.model
    def download_file(self, file_id):
        """Download a file from Google Drive.

        For Google Docs/Sheets, exports to DOCX/XLSX.
        For other files, downloads directly.

        Args:
            file_id: Google Drive file ID

        Returns:
            tuple (content_bytes, filename, mime_type)
        """
        service = self._get_service()

        try:
            # Get file metadata
            metadata = self.get_file_metadata(file_id)
            mime_type = metadata.get('mimeType')
            name = metadata.get('name', 'download')

            # Check if it's a Google native format that needs export
            if mime_type in EXPORT_MAPPINGS:
                export_info = EXPORT_MAPPINGS[mime_type]
                content = service.files().export(
                    fileId=file_id,
                    mimeType=export_info['mime'],
                ).execute()

                # Add extension if not present
                if not name.endswith(export_info['extension']):
                    name = name + export_info['extension']

                return content, name, export_info['mime']
            else:
                # Direct download for binary files (supportsAllDrives for Shared Drives)
                request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
                buffer = io.BytesIO()
                downloader = MediaIoBaseDownload(buffer, request)

                done = False
                while not done:
                    status, done = downloader.next_chunk()

                return buffer.getvalue(), name, mime_type

        except Exception as e:
            _logger.error("Failed to download file: %s", e)
            raise UserError(_("Failed to download file from Google Drive: %s") % str(e))

    @api.model
    def upload_file(self, content, filename, mime_type, folder_id=None):
        """Upload a file to Google Drive.

        Args:
            content: File content as bytes
            filename: Name for the file on Drive
            mime_type: MIME type of the file
            folder_id: Optional folder ID to upload to

        Returns:
            dict with file metadata (id, name, webViewLink)
        """
        from googleapiclient.http import MediaInMemoryUpload

        service = self._get_service()

        # Prepare file metadata
        file_metadata = {
            'name': filename,
        }

        if folder_id:
            file_metadata['parents'] = [folder_id]

        # Create media upload
        media = MediaInMemoryUpload(
            content,
            mimetype=mime_type,
            resumable=True
        )

        try:
            # Upload file (supportsAllDrives for Shared Drives)
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, mimeType',
                supportsAllDrives=True,
            ).execute()

            _logger.info("File uploaded to Google Drive: %s (ID: %s)",
                        file.get('name'), file.get('id'))

            return file

        except Exception as e:
            _logger.error("Failed to upload file to Google Drive: %s", e)
            raise UserError(_("Failed to upload file to Google Drive: %s") % str(e))

    @api.model
    def update_file(self, file_id, content, mime_type, new_name=None):
        """Update an existing file on Google Drive.

        Args:
            file_id: Google Drive file ID to update
            content: New file content as bytes
            mime_type: MIME type of the file
            new_name: Optional new name for the file

        Returns:
            dict with updated file metadata (id, name, webViewLink)
        """
        from googleapiclient.http import MediaInMemoryUpload

        service = self._get_service()

        # Prepare file metadata (only if renaming)
        file_metadata = {}
        if new_name:
            file_metadata['name'] = new_name

        # Create media upload
        media = MediaInMemoryUpload(
            content,
            mimetype=mime_type,
            resumable=True
        )

        try:
            # Update file (supportsAllDrives for Shared Drives)
            file = service.files().update(
                fileId=file_id,
                body=file_metadata if file_metadata else None,
                media_body=media,
                fields='id, name, webViewLink, mimeType, modifiedTime',
                supportsAllDrives=True,
            ).execute()

            _logger.info("File updated on Google Drive: %s (ID: %s)",
                        file.get('name'), file.get('id'))

            return file

        except Exception as e:
            _logger.error("Failed to update file on Google Drive: %s", e)
            raise UserError(_("Failed to update file on Google Drive: %s") % str(e))

    @api.model
    def get_oauth_url(self, redirect_uri, state=None):
        """Generate OAuth2 authorization URL.

        Args:
            redirect_uri: Callback URL after authorization
            state: State parameter for CSRF protection

        Returns:
            Authorization URL string
        """
        self._check_libraries()
        company = self.env.company

        if not company.gdrive_client_id:
            raise UserError(_("Google Drive OAuth2 Client ID not configured."))

        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                'web': {
                    'client_id': company.gdrive_client_id,
                    'client_secret': company.gdrive_client_secret,
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                }
            },
            scopes=SCOPES,
            redirect_uri=redirect_uri,
        )

        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=state,
        )

        return auth_url

    @api.model
    def exchange_code_for_tokens(self, code, redirect_uri):
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from Google
            redirect_uri: Same redirect_uri used in authorization

        Returns:
            dict with access_token, refresh_token, expires_in
        """
        self._check_libraries()
        company = self.env.company

        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                'web': {
                    'client_id': company.gdrive_client_id,
                    'client_secret': company.gdrive_client_secret,
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                }
            },
            scopes=SCOPES,
            redirect_uri=redirect_uri,
        )

        flow.fetch_token(code=code)
        credentials = flow.credentials

        return {
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'expires_in': 3600,  # Default 1 hour
        }
