import logging
from datetime import datetime, timedelta

from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import msal
    import requests
except ImportError:
    _logger.warning("MSAL or requests library not installed. Install with: pip install msal requests")
    msal = None
    requests = None


# Microsoft Graph API endpoints
GRAPH_API_URL = 'https://graph.microsoft.com/v1.0'
AUTHORITY_URL = 'https://login.microsoftonline.com'

# Supported MIME types for templates
SUPPORTED_EXTENSIONS = ['.docx', '.xlsx', '.pptx', '.odt', '.ods', '.odp']

# MS Graph scopes
SCOPES_APP = ['https://graph.microsoft.com/.default']  # For app-only auth
SCOPES_DELEGATED = [
    'https://graph.microsoft.com/Sites.Read.All',
    'https://graph.microsoft.com/Files.ReadWrite.All',
    'offline_access',
]


class SharePointService(models.AbstractModel):
    """Microsoft Graph API service wrapper for SharePoint/OneDrive."""

    _name = 'sharepoint.service'
    _description = 'SharePoint Service'

    def _check_libraries(self):
        """Check if required libraries are installed."""
        if msal is None or requests is None:
            raise UserError(_(
                "Required libraries not installed.\n\n"
                "Install with:\n"
                "pip install msal requests"
            ))

    @api.model
    def _get_app_credentials(self):
        """Get credentials for app-only authentication."""
        self._check_libraries()
        company = self.env.company

        if not all([company.sharepoint_client_id, company.sharepoint_client_secret, company.sharepoint_tenant_id]):
            raise UserError(_("SharePoint App Registration credentials not configured."))

        return {
            'client_id': company.sharepoint_client_id,
            'client_secret': company.sharepoint_client_secret,
            'tenant_id': company.sharepoint_tenant_id,
        }

    @api.model
    def _get_app_token(self):
        """Get access token using app-only authentication (client credentials flow)."""
        creds = self._get_app_credentials()

        app = msal.ConfidentialClientApplication(
            creds['client_id'],
            authority=f"{AUTHORITY_URL}/{creds['tenant_id']}",
            client_credential=creds['client_secret'],
        )

        result = app.acquire_token_for_client(scopes=SCOPES_APP)

        if 'access_token' in result:
            return result['access_token']

        error = result.get('error_description', result.get('error', 'Unknown error'))
        raise UserError(_("Failed to get SharePoint access token: %s") % error)

    @api.model
    def _get_delegated_token(self, user=None):
        """Get access token using delegated authentication (on behalf of user)."""
        self._check_libraries()
        user = user or self.env.user
        settings = user.res_users_settings_id

        if not settings or not settings.sharepoint_rtoken:
            raise UserError(_(
                "SharePoint not connected for user %s.\n"
                "Please connect your Microsoft account in Settings."
            ) % user.name)

        company = self.env.company
        creds = self._get_app_credentials()

        app = msal.ConfidentialClientApplication(
            creds['client_id'],
            authority=f"{AUTHORITY_URL}/{creds['tenant_id']}",
            client_credential=creds['client_secret'],
        )

        result = app.acquire_token_by_refresh_token(
            settings.sharepoint_rtoken,
            scopes=SCOPES_DELEGATED,
        )

        if 'access_token' in result:
            # Update stored tokens
            settings.sudo().write({
                'sharepoint_token': result['access_token'],
                'sharepoint_rtoken': result.get('refresh_token', settings.sharepoint_rtoken),
                'sharepoint_token_validity': datetime.now() + timedelta(seconds=result.get('expires_in', 3600)),
            })
            return result['access_token']

        error = result.get('error_description', result.get('error', 'Unknown error'))
        _logger.error("Failed to refresh SharePoint token: %s", error)
        raise UserError(_(
            "Failed to refresh SharePoint access token.\n"
            "Please reconnect your Microsoft account."
        ))

    @api.model
    def _get_token(self, user=None):
        """Get access token based on company auth method."""
        company = self.env.company

        if company.sharepoint_auth_method == 'app':
            return self._get_app_token()
        else:
            return self._get_delegated_token(user)

    @api.model
    def _request(self, method, endpoint, **kwargs):
        """Make authenticated request to Microsoft Graph API."""
        token = self._get_token()
        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f'Bearer {token}'

        url = f"{GRAPH_API_URL}{endpoint}"

        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            _logger.error("MS Graph API error: %s - %s", e.response.status_code, e.response.text)
            raise UserError(_("SharePoint API error: %s") % e.response.text)
        except requests.exceptions.RequestException as e:
            _logger.error("MS Graph API request failed: %s", e)
            raise UserError(_("SharePoint API request failed: %s") % str(e))

    @api.model
    def test_connection(self):
        """Test Microsoft Graph API connection."""
        try:
            token = self._get_token()
            headers = {'Authorization': f'Bearer {token}'}
            company = self.env.company

            # For app-only auth, use /sites/root endpoint
            # For delegated auth, use /me endpoint
            if company.sharepoint_auth_method == 'app':
                response = requests.get(f"{GRAPH_API_URL}/sites/root", headers=headers, timeout=10)
                if response.status_code == 200:
                    site_info = response.json()
                    return {
                        'success': True,
                        'email': f"App → {site_info.get('displayName', 'SharePoint')}",
                        'message': _("Connection successful (App authentication)!"),
                    }
            else:
                response = requests.get(f"{GRAPH_API_URL}/me", headers=headers, timeout=10)
                if response.status_code == 200:
                    user_info = response.json()
                    return {
                        'success': True,
                        'email': user_info.get('userPrincipalName', user_info.get('mail', 'Unknown')),
                        'message': _("Connection successful!"),
                    }

            return {
                'success': False,
                'message': f"HTTP {response.status_code}: {response.text}",
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e),
            }

    @api.model
    def get_sites(self):
        """Get list of SharePoint sites accessible to the app/user."""
        response = self._request('GET', '/sites?search=*')
        return response.json().get('value', [])

    @api.model
    def get_site_drives(self, site_id):
        """Get document libraries (drives) for a SharePoint site."""
        response = self._request('GET', f'/sites/{site_id}/drives')
        return response.json().get('value', [])

    @api.model
    def search_files(self, query='', site_id=None, drive_id=None):
        """Search for files in SharePoint/OneDrive.

        Args:
            query: Search query string
            site_id: Optional SharePoint site ID
            drive_id: Optional drive ID

        Returns:
            list of file items
        """
        if drive_id:
            endpoint = f'/drives/{drive_id}/root/search(q=\'{query}\')'
        elif site_id:
            endpoint = f'/sites/{site_id}/drive/root/search(q=\'{query}\')'
        else:
            # Search in user's OneDrive
            endpoint = f'/me/drive/root/search(q=\'{query}\')'

        try:
            response = self._request('GET', endpoint)
            items = response.json().get('value', [])

            # Filter to supported file types
            filtered = []
            for item in items:
                name = item.get('name', '').lower()
                if any(name.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                    filtered.append(item)

            return filtered
        except Exception as e:
            _logger.error("Failed to search SharePoint: %s", e)
            raise UserError(_("Failed to search SharePoint: %s") % str(e))

    @api.model
    def get_drive_items(self, drive_id, folder_id=None, page_size=50):
        """Get items in a drive folder.

        Args:
            drive_id: Drive ID
            folder_id: Optional folder ID (defaults to root)
            page_size: Number of items per page

        Returns:
            dict with 'items' list and optional 'nextLink'
        """
        if folder_id:
            endpoint = f'/drives/{drive_id}/items/{folder_id}/children'
        else:
            endpoint = f'/drives/{drive_id}/root/children'

        params = {
            '$top': page_size,
            '$orderby': 'lastModifiedDateTime desc',
        }

        response = self._request('GET', endpoint, params=params)
        data = response.json()

        return {
            'items': data.get('value', []),
            'nextLink': data.get('@odata.nextLink'),
        }

    @api.model
    def get_file_metadata(self, drive_id, item_id):
        """Get metadata for a specific file.

        Args:
            drive_id: Drive ID
            item_id: Item ID

        Returns:
            dict with file metadata
        """
        response = self._request('GET', f'/drives/{drive_id}/items/{item_id}')
        return response.json()

    @api.model
    def download_file(self, drive_id, item_id):
        """Download a file from SharePoint/OneDrive.

        Args:
            drive_id: Drive ID
            item_id: Item ID

        Returns:
            tuple (content_bytes, filename, mime_type)
        """
        # Get file metadata first
        metadata = self.get_file_metadata(drive_id, item_id)
        filename = metadata.get('name', 'download')
        mime_type = metadata.get('file', {}).get('mimeType', 'application/octet-stream')

        # Download content
        response = self._request('GET', f'/drives/{drive_id}/items/{item_id}/content')

        return response.content, filename, mime_type

    @api.model
    def upload_file(self, drive_id, folder_id, content, filename, mime_type=None):
        """Upload a file to SharePoint/OneDrive.

        Args:
            drive_id: Drive ID
            folder_id: Parent folder ID
            content: File content as bytes
            filename: Name for the file
            mime_type: Optional MIME type

        Returns:
            dict with file metadata (id, name, webUrl)
        """
        # For files < 4MB, use simple upload
        if len(content) < 4 * 1024 * 1024:
            endpoint = f'/drives/{drive_id}/items/{folder_id}:/{filename}:/content'
            headers = {}
            if mime_type:
                headers['Content-Type'] = mime_type

            response = self._request('PUT', endpoint, data=content, headers=headers)
            return response.json()

        # For larger files, use upload session (resumable upload)
        return self._upload_large_file(drive_id, folder_id, content, filename)

    @api.model
    def _upload_large_file(self, drive_id, folder_id, content, filename):
        """Upload large file using upload session."""
        # Create upload session
        endpoint = f'/drives/{drive_id}/items/{folder_id}:/{filename}:/createUploadSession'
        response = self._request('POST', endpoint, json={
            'item': {'@microsoft.graph.conflictBehavior': 'replace'}
        })
        upload_url = response.json().get('uploadUrl')

        # Upload in chunks
        chunk_size = 10 * 1024 * 1024  # 10MB chunks
        file_size = len(content)

        for i in range(0, file_size, chunk_size):
            chunk = content[i:i + chunk_size]
            chunk_end = min(i + chunk_size - 1, file_size - 1)

            headers = {
                'Content-Length': str(len(chunk)),
                'Content-Range': f'bytes {i}-{chunk_end}/{file_size}',
            }

            response = requests.put(upload_url, data=chunk, headers=headers)
            response.raise_for_status()

            if response.status_code in (200, 201):
                return response.json()

        raise UserError(_("Failed to complete file upload"))

    @api.model
    def update_file(self, drive_id, item_id, content, mime_type=None):
        """Update an existing file on SharePoint/OneDrive.

        Args:
            drive_id: Drive ID
            item_id: Item ID
            content: New file content as bytes
            mime_type: Optional MIME type

        Returns:
            dict with updated file metadata
        """
        headers = {}
        if mime_type:
            headers['Content-Type'] = mime_type

        response = self._request('PUT', f'/drives/{drive_id}/items/{item_id}/content',
                                  data=content, headers=headers)
        return response.json()

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
        creds = self._get_app_credentials()

        app = msal.ConfidentialClientApplication(
            creds['client_id'],
            authority=f"{AUTHORITY_URL}/{creds['tenant_id']}",
            client_credential=creds['client_secret'],
        )

        auth_url = app.get_authorization_request_url(
            scopes=SCOPES_DELEGATED,
            redirect_uri=redirect_uri,
            state=state,
        )

        return auth_url

    @api.model
    def exchange_code_for_tokens(self, code, redirect_uri):
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from Microsoft
            redirect_uri: Same redirect_uri used in authorization

        Returns:
            dict with access_token, refresh_token, expires_in
        """
        self._check_libraries()
        creds = self._get_app_credentials()

        app = msal.ConfidentialClientApplication(
            creds['client_id'],
            authority=f"{AUTHORITY_URL}/{creds['tenant_id']}",
            client_credential=creds['client_secret'],
        )

        result = app.acquire_token_by_authorization_code(
            code,
            scopes=SCOPES_DELEGATED,
            redirect_uri=redirect_uri,
        )

        if 'access_token' in result:
            return {
                'access_token': result['access_token'],
                'refresh_token': result.get('refresh_token'),
                'expires_in': result.get('expires_in', 3600),
            }

        error = result.get('error_description', result.get('error', 'Unknown error'))
        raise UserError(_("Failed to exchange code for tokens: %s") % error)
