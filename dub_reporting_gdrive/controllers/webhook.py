import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class GDriveWebhookController(http.Controller):
    """Controller for Google Drive push notifications."""

    @http.route('/gdrive/webhook', type='http', auth='public', methods=['POST'], csrf=False)
    def webhook(self, **kwargs):
        """Receive Google Drive push notifications.

        Google sends notifications with these headers:
        - X-Goog-Channel-ID: Channel ID we created
        - X-Goog-Resource-ID: Google's internal resource ID
        - X-Goog-Resource-State: 'sync', 'change', 'update', etc.
        - X-Goog-Resource-URI: URI of the changed resource
        - X-Goog-Changed: What changed (for updates)
        """
        headers = request.httprequest.headers

        channel_id = headers.get('X-Goog-Channel-ID')
        resource_state = headers.get('X-Goog-Resource-State')
        resource_id = headers.get('X-Goog-Resource-ID')
        changed = headers.get('X-Goog-Changed', '')

        _logger.info(
            "GDrive webhook: channel=%s, state=%s, resource=%s, changed=%s",
            channel_id, resource_state, resource_id, changed
        )

        # Sync state is just confirmation of channel creation
        if resource_state == 'sync':
            _logger.info("GDrive channel %s confirmed", channel_id)
            return request.make_response('OK', status=200)

        # Handle content changes
        if resource_state in ('change', 'update'):
            try:
                # Find the channel
                channel = request.env['gdrive.sync.channel'].sudo().search([
                    ('name', '=', channel_id),
                    ('state', '=', 'active'),
                ], limit=1)

                if not channel:
                    _logger.warning("Unknown GDrive channel: %s", channel_id)
                    return request.make_response('Unknown channel', status=200)

                # Check if content actually changed
                if 'content' in changed or resource_state == 'change':
                    # Find reports using this file
                    reports = request.env['ir.actions.report'].sudo().search([
                        ('gdrive_file_id', '=', channel.file_id),
                        ('gdrive_auto_sync', '=', True),
                    ])

                    for report in reports:
                        try:
                            _logger.info("Auto-syncing report %s from GDrive", report.name)
                            report.action_sync_from_gdrive()
                        except Exception as e:
                            _logger.error(
                                "Failed to auto-sync report %s: %s",
                                report.name, e
                            )

            except Exception as e:
                _logger.error("Error processing GDrive webhook: %s", e)

        return request.make_response('OK', status=200)
