import logging
import uuid
from datetime import datetime, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    requests = None


# MS Graph subscription max expiration for drive items is ~30 days
MAX_SUBSCRIPTION_DAYS = 29


class SharePointSubscription(models.Model):
    """Track Microsoft Graph webhook subscriptions for drives.

    MS Graph webhooks work at the drive level, not file level.
    When changes occur, we use the Delta API to find what changed.
    """

    _name = 'sharepoint.subscription'
    _description = 'SharePoint Webhook Subscription'
    _order = 'expiration desc'

    name = fields.Char(
        string="Subscription ID",
        required=True,
        index=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True,
        ondelete='cascade',
        default=lambda self: self.env.company,
    )
    drive_id = fields.Char(
        string="Drive ID",
        required=True,
        index=True,
    )
    resource = fields.Char(
        string="Resource",
        readonly=True,
        help="MS Graph resource path",
    )
    expiration = fields.Datetime(
        string="Expiration",
        readonly=True,
    )
    state = fields.Selection(
        string="State",
        selection=[
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('stopped', 'Stopped'),
        ],
        default='active',
        readonly=True,
    )
    client_state = fields.Char(
        string="Client State",
        readonly=True,
        help="Secret for validating webhook notifications",
    )
    delta_link = fields.Char(
        string="Delta Link",
        help="Token for tracking changes since last sync",
    )

    @api.model
    def _get_or_create_drive_subscription(self, drive_id):
        """Get existing subscription for drive or create new one.

        Args:
            drive_id: SharePoint/OneDrive drive ID

        Returns:
            Subscription record or False
        """
        company = self.env.company

        if not company.sharepoint_webhook_enabled:
            _logger.info("SharePoint webhook not enabled")
            return False

        # Check for existing active subscription
        existing = self.search([
            ('drive_id', '=', drive_id),
            ('company_id', '=', company.id),
            ('state', '=', 'active'),
        ], limit=1)

        if existing:
            _logger.info("Using existing subscription %s for drive %s", existing.name, drive_id)
            return existing

        # Create new subscription
        return self._register_drive_subscription(drive_id)

    @api.model
    def _register_drive_subscription(self, drive_id):
        """Register a new webhook subscription for a drive.

        MS Graph webhooks monitor the entire drive, not individual files.

        Args:
            drive_id: SharePoint/OneDrive drive ID

        Returns:
            Created subscription record or False
        """
        company = self.env.company

        if not company.sharepoint_webhook_enabled:
            return False

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # Check if URL is HTTPS (required by Microsoft)
        if not base_url.startswith('https://'):
            _logger.warning("Cannot register webhook: HTTPS URL required. Current URL: %s", base_url)
            return False

        # Generate unique client state for validation
        client_state = str(uuid.uuid4())

        # Resource path for the drive root (monitors all changes in drive)
        resource = f'/drives/{drive_id}/root'

        # Expiration time (max 29 days for drive items)
        expiration = datetime.utcnow() + timedelta(days=MAX_SUBSCRIPTION_DAYS)

        # Prepare subscription payload
        payload = {
            'changeType': 'updated',
            'notificationUrl': f'{base_url}/sharepoint/webhook',
            'resource': resource,
            'expirationDateTime': expiration.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'clientState': client_state,
        }

        try:
            service = self.env['sharepoint.service']
            token = service._get_token()

            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            }

            _logger.info("Registering SharePoint subscription for drive %s", drive_id)
            _logger.debug("Subscription payload: %s", payload)

            response = requests.post(
                'https://graph.microsoft.com/v1.0/subscriptions',
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code == 201:
                result = response.json()

                # Get initial delta link
                delta_link = self._get_initial_delta_link(drive_id, token)

                subscription = self.create({
                    'name': result['id'],
                    'company_id': company.id,
                    'drive_id': drive_id,
                    'resource': resource,
                    'expiration': datetime.fromisoformat(
                        result['expirationDateTime'].replace('Z', '+00:00')
                    ).replace(tzinfo=None),
                    'state': 'active',
                    'client_state': client_state,
                    'delta_link': delta_link,
                })

                _logger.info("Registered SharePoint subscription %s for drive %s",
                            result['id'], drive_id)
                return subscription

            _logger.error("Failed to create SharePoint subscription: %s - %s",
                         response.status_code, response.text)
            return False

        except Exception as e:
            _logger.error("Failed to register SharePoint subscription: %s", e)
            return False

    def _get_initial_delta_link(self, drive_id, token):
        """Get initial delta link for tracking changes.

        Args:
            drive_id: Drive ID
            token: Access token

        Returns:
            Delta link URL or None
        """
        try:
            headers = {'Authorization': f'Bearer {token}'}

            # Request delta with token=latest to get current state
            response = requests.get(
                f'https://graph.microsoft.com/v1.0/drives/{drive_id}/root/delta?token=latest',
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('@odata.deltaLink')

            _logger.warning("Failed to get initial delta link: %s", response.text)
            return None

        except Exception as e:
            _logger.warning("Failed to get initial delta link: %s", e)
            return None

    def get_changes(self):
        """Get changes since last sync using Delta API.

        Returns:
            list of changed item IDs
        """
        self.ensure_one()

        if not self.delta_link:
            _logger.warning("No delta link for subscription %s", self.name)
            return []

        try:
            service = self.env['sharepoint.service']
            token = service._get_token()

            headers = {'Authorization': f'Bearer {token}'}

            changed_items = []
            next_link = self.delta_link

            while next_link:
                response = requests.get(next_link, headers=headers, timeout=30)

                if response.status_code != 200:
                    _logger.error("Delta API error: %s - %s",
                                 response.status_code, response.text)
                    break

                data = response.json()

                # Collect changed item IDs
                for item in data.get('value', []):
                    item_id = item.get('id')
                    if item_id and not item.get('deleted'):
                        changed_items.append(item_id)
                        _logger.debug("Changed item: %s (%s)", item.get('name'), item_id)

                # Get next page or save delta link
                next_link = data.get('@odata.nextLink')
                if not next_link:
                    new_delta_link = data.get('@odata.deltaLink')
                    if new_delta_link:
                        self.write({'delta_link': new_delta_link})

            _logger.info("Found %d changed items in drive %s", len(changed_items), self.drive_id)
            return changed_items

        except Exception as e:
            _logger.error("Failed to get changes for subscription %s: %s", self.name, e)
            return []

    def _renew_subscription(self):
        """Renew an existing subscription."""
        self.ensure_one()

        if self.state != 'active':
            return False

        # New expiration time
        expiration = datetime.utcnow() + timedelta(days=MAX_SUBSCRIPTION_DAYS)

        try:
            service = self.env['sharepoint.service']
            token = service._get_token()

            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            }

            payload = {
                'expirationDateTime': expiration.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            }

            response = requests.patch(
                f'https://graph.microsoft.com/v1.0/subscriptions/{self.name}',
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                self.write({
                    'expiration': datetime.fromisoformat(
                        result['expirationDateTime'].replace('Z', '+00:00')
                    ).replace(tzinfo=None),
                })
                _logger.info("Renewed SharePoint subscription %s", self.name)
                return True

            _logger.error("Failed to renew SharePoint subscription: %s - %s",
                         response.status_code, response.text)
            return False

        except Exception as e:
            _logger.error("Failed to renew SharePoint subscription %s: %s", self.name, e)
            return False

    def _stop_subscription(self):
        """Delete a subscription from Microsoft Graph."""
        self.ensure_one()

        if self.state != 'active':
            return

        try:
            service = self.env['sharepoint.service']
            token = service._get_token()

            headers = {
                'Authorization': f'Bearer {token}',
            }

            response = requests.delete(
                f'https://graph.microsoft.com/v1.0/subscriptions/{self.name}',
                headers=headers,
                timeout=30,
            )

            if response.status_code in (204, 404):
                _logger.info("Stopped SharePoint subscription %s", self.name)
            else:
                _logger.warning("Failed to stop SharePoint subscription %s: %s",
                              self.name, response.text)

        except Exception as e:
            _logger.warning("Failed to stop SharePoint subscription %s: %s", self.name, e)

        self.write({'state': 'stopped'})

    @api.model
    def _cron_renew_subscriptions(self):
        """Cron job to renew expiring subscriptions.

        Run daily to renew subscriptions expiring in next 7 days.
        """
        threshold = datetime.now() + timedelta(days=7)

        # Find expiring subscriptions
        expiring = self.search([
            ('state', '=', 'active'),
            ('expiration', '<=', threshold),
        ])

        for subscription in expiring:
            _logger.info("Renewing SharePoint subscription %s for drive %s",
                        subscription.name, subscription.drive_id)
            subscription._renew_subscription()

    @api.model
    def _cleanup_expired(self):
        """Mark expired subscriptions as expired."""
        self.search([
            ('state', '=', 'active'),
            ('expiration', '<', datetime.now()),
        ]).write({'state': 'expired'})

    def unlink(self):
        """Stop subscriptions before deleting."""
        for subscription in self.filtered(lambda s: s.state == 'active'):
            subscription._stop_subscription()
        return super().unlink()
