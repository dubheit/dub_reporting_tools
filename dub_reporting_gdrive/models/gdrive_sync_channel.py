import logging
import uuid
from datetime import datetime, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class GDriveSyncChannel(models.Model):
    """Track Google Drive push notification channels."""

    _name = 'gdrive.sync.channel'
    _description = 'Google Drive Sync Channel'
    _order = 'expiration desc'

    name = fields.Char(
        string="Channel ID",
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
    file_id = fields.Char(
        string="Google Drive File ID",
        required=True,
        index=True,
    )
    resource_id = fields.Char(
        string="Resource ID",
        readonly=True,
        help="Google's internal resource identifier",
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

    @api.model
    def _register_channel(self, file_id):
        """Register a new push notification channel for a file.

        Args:
            file_id: Google Drive file ID to watch

        Returns:
            Created channel record
        """
        company = self.env.company

        if not company.gdrive_webhook_enabled:
            return False

        try:
            service = self.env['gdrive.service']._get_service()
        except UserError:
            _logger.warning("Cannot register webhook: Google Drive not configured")
            return False

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # Check if URL is HTTPS (required by Google)
        if not base_url.startswith('https://'):
            _logger.warning("Cannot register webhook: HTTPS URL required")
            return False

        channel_id = str(uuid.uuid4())

        # Channels expire after max 24 hours, we set 23h
        expiration_time = datetime.now() + timedelta(hours=23)
        expiration_ms = int(expiration_time.timestamp() * 1000)

        body = {
            'id': channel_id,
            'type': 'web_hook',
            'address': f'{base_url}/gdrive/webhook',
            'expiration': expiration_ms,
        }

        try:
            response = service.files().watch(
                fileId=file_id,
                body=body,
                supportsAllDrives=True,
            ).execute()

            channel = self.create({
                'name': channel_id,
                'company_id': company.id,
                'file_id': file_id,
                'resource_id': response.get('resourceId'),
                'expiration': datetime.fromtimestamp(int(response['expiration']) / 1000),
                'state': 'active',
            })

            _logger.info("Registered GDrive webhook channel %s for file %s", channel_id, file_id)
            return channel

        except Exception as e:
            _logger.error("Failed to register GDrive webhook: %s", e)
            return False

    def _stop_channel(self):
        """Stop a push notification channel."""
        self.ensure_one()

        if self.state != 'active':
            return

        try:
            service = self.env['gdrive.service']._get_service()
            service.channels().stop(body={
                'id': self.name,
                'resourceId': self.resource_id,
            }).execute()
        except Exception as e:
            _logger.warning("Failed to stop GDrive channel %s: %s", self.name, e)

        self.write({'state': 'stopped'})

    @api.model
    def _cron_renew_channels(self):
        """Cron job to renew expiring channels.

        Run every 12 hours to renew channels expiring in next 12 hours.
        """
        threshold = datetime.now() + timedelta(hours=12)

        # Find expiring channels
        expiring = self.search([
            ('state', '=', 'active'),
            ('expiration', '<=', threshold),
        ])

        for channel in expiring:
            _logger.info("Renewing GDrive channel %s for file %s", channel.name, channel.file_id)

            # Stop old channel
            channel._stop_channel()

            # Register new channel
            self._register_channel(channel.file_id)

    @api.model
    def _cleanup_expired(self):
        """Mark expired channels as expired."""
        self.search([
            ('state', '=', 'active'),
            ('expiration', '<', datetime.now()),
        ]).write({'state': 'expired'})

    def unlink(self):
        """Stop channels before deleting."""
        for channel in self.filtered(lambda c: c.state == 'active'):
            channel._stop_channel()
        return super().unlink()
