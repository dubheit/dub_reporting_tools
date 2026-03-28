import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SharePointWebhookController(http.Controller):
    """Controller for Microsoft Graph webhook notifications.

    MS Graph sends notifications when changes occur in a drive.
    We then use the Delta API to find what specific files changed.
    """

    @http.route('/sharepoint/webhook', type='http', auth='public', methods=['POST'], csrf=False)
    def webhook(self, validationToken=None, **kwargs):
        """Receive Microsoft Graph webhook notifications.

        Microsoft sends two types of requests:
        1. Validation request with validationToken query param (must echo back)
        2. Notification request with JSON body containing changes
        """
        # Handle validation request (during subscription creation)
        if validationToken:
            _logger.info("SharePoint webhook validation request received")
            return request.make_response(
                validationToken,
                headers=[('Content-Type', 'text/plain')],
                status=200
            )

        # Handle notification request
        try:
            import json
            body = request.httprequest.get_data(as_text=True)
            data = json.loads(body) if body else {}

            notifications = data.get('value', [])
            _logger.info("Received %d SharePoint notifications", len(notifications))

            for notification in notifications:
                subscription_id = notification.get('subscriptionId')
                client_state = notification.get('clientState')
                resource = notification.get('resource')
                change_type = notification.get('changeType')

                _logger.info(
                    "SharePoint notification: subscription=%s, change=%s, resource=%s",
                    subscription_id, change_type, resource
                )

                # Find the subscription
                subscription = request.env['sharepoint.subscription'].sudo().search([
                    ('name', '=', subscription_id),
                    ('state', '=', 'active'),
                ], limit=1)

                if not subscription:
                    _logger.warning("Unknown SharePoint subscription: %s", subscription_id)
                    continue

                # Validate client state
                if client_state != subscription.client_state:
                    _logger.warning("Invalid client state for subscription %s", subscription_id)
                    continue

                # Process changes using Delta API
                if change_type == 'updated':
                    self._process_drive_changes(subscription)

        except Exception as e:
            _logger.error("Error processing SharePoint webhook: %s", e, exc_info=True)

        # Always return 202 Accepted to acknowledge receipt
        return request.make_response('', status=202)

    def _process_drive_changes(self, subscription):
        """Process changes in a drive using Delta API.

        Args:
            subscription: sharepoint.subscription record
        """
        try:
            # Get changed items using Delta API
            changed_item_ids = subscription.get_changes()

            if not changed_item_ids:
                _logger.info("No changed items found for subscription %s", subscription.name)
                return

            # Find reports that use any of these items
            reports = request.env['ir.actions.report'].sudo().search([
                ('sharepoint_drive_id', '=', subscription.drive_id),
                ('sharepoint_item_id', 'in', changed_item_ids),
                ('sharepoint_auto_sync', '=', True),
            ])

            _logger.info("Found %d reports to sync for drive %s", len(reports), subscription.drive_id)

            for report in reports:
                try:
                    _logger.info("Auto-syncing report '%s' from SharePoint", report.name)
                    report.action_sync_from_sharepoint()
                except Exception as e:
                    _logger.error("Failed to auto-sync report '%s': %s", report.name, e)

        except Exception as e:
            _logger.error("Error processing drive changes: %s", e, exc_info=True)
