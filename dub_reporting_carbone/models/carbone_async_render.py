import logging
import base64
from markupsafe import Markup
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class CarboneAsyncRender(models.Model):
    """Track asynchronous Carbone render requests."""
    
    _name = 'carbone.async.render'
    _description = 'Carbone Async Render Request'
    _order = 'create_date desc'
    
    name = fields.Char(string='Render ID', required=True, index=True)
    request_id = fields.Char(string='Request ID', required=True, index=True)
    report_id = fields.Many2one('ir.actions.report', string='Report', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    record_ids = fields.Char(string='Record IDs', required=True)
    model = fields.Char(string='Model', required=True)
    
    state = fields.Selection([
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], string='State', default='pending', required=True)
    
    result_file = fields.Binary(string='Result File', attachment=True)
    result_filename = fields.Char(string='Filename')
    error_message = fields.Text(string='Error Message')
    
    webhook_received = fields.Datetime(string='Webhook Received')
    
    def _notify_user(self, content, filename):
        """Send report to user via chat/notification.
        Prefers a direct chat from OdooBot; falls back to notification.
        
        Args:
            content: Report binary content (base64)
            filename: Report filename
        """
        self.ensure_one()
        
        # Create attachment
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'datas': content,
            'mimetype': 'application/pdf',
            'type': 'binary',
        })
        
        # Try to get OdooBot partner, fallback to Administrator partner
        odoobot = self.env['res.partner'].sudo().search([('name', '=', 'OdooBot')], limit=1)
        if not odoobot:
            try:
                odoobot = self.env.ref('base.partner_root')
            except Exception:
                odoobot = self.user_id.partner_id
        
        # Message body
        message = Markup("%s <b>%s</b> %s<br/>%s") % (
            _("Your report"),
            self.report_id.name,
            _("is ready!"),
            _("Click on the attachment below to download it.")
        )
        
        # Try direct chat channel with OdooBot
        try:
            Channel = self.env['discuss.channel'].sudo()
            # Find existing 1-1 chat with OdooBot and the user
            domain = [
                ('channel_type', '=', 'chat'),
                ('channel_partner_ids', 'in', [self.user_id.partner_id.id]),
                ('channel_partner_ids', 'in', [odoobot.id]),
            ]
            channel = Channel.search(domain, limit=1)
            if not channel:
                channel = Channel.create({
                    'name': 'OdooBot',
                    'channel_type': 'chat',
                    'channel_partner_ids': [(6, 0, [self.user_id.partner_id.id, odoobot.id])],
                })
            channel.sudo().message_post(
                body=message,
                subject=_('Report Ready: %s') % self.report_id.name,
                author_id=odoobot.id,
                attachments=[(filename, base64.b64decode(content))],
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            _logger.info(f"Report delivered via chat channel {channel.id} to user {self.user_id.name}")
            return
        except Exception as e:
            _logger.warning(f"chat channel delivery failed for user={self.user_id.id}: {e}")
        
        # Fallback: notify in Inbox
        try:
            self.env['mail.thread'].sudo().message_notify(
                partner_ids=[self.user_id.partner_id.id],
                body=message,
                subject=_('Report Ready: %s') % self.report_id.name,
                author_id=odoobot.id,
                attachments=[(filename, base64.b64decode(content))],
            )
            _logger.info(f"Report notification sent to user {self.user_id.name} (Inbox)")
        except Exception as e:
            _logger.warning(f"message_notify failed, user={self.user_id.id}: {e}")
            # Last resort: post on user's partner chatter
            self.user_id.partner_id.sudo().message_post(
                body=message,
                subject=_('Report Ready: %s') % self.report_id.name,
                author_id=odoobot.id,
                attachments=[(filename, base64.b64decode(content))],
            )
            _logger.info(f"Report posted on partner chatter for user {self.user_id.name}")

    def _notify_user_error(self, error_message):
        """Send error notification to user via chat.

        Args:
            error_message: Error message to display
        """
        self.ensure_one()

        # Try to get OdooBot partner
        odoobot = self.env['res.partner'].sudo().search([('name', '=', 'OdooBot')], limit=1)
        if not odoobot:
            try:
                odoobot = self.env.ref('base.partner_root')
            except Exception:
                odoobot = self.user_id.partner_id

        # Error message body
        message = Markup("<b>%s</b><br/><br/>%s<br/><code>%s</code>") % (
            _("Report generation failed"),
            _("Error:"),
            error_message
        )

        # Try direct chat channel with OdooBot
        try:
            Channel = self.env['discuss.channel'].sudo()
            domain = [
                ('channel_type', '=', 'chat'),
                ('channel_partner_ids', 'in', [self.user_id.partner_id.id]),
                ('channel_partner_ids', 'in', [odoobot.id]),
            ]
            channel = Channel.search(domain, limit=1)
            if not channel:
                channel = Channel.create({
                    'name': 'OdooBot',
                    'channel_type': 'chat',
                    'channel_partner_ids': [(6, 0, [self.user_id.partner_id.id, odoobot.id])],
                })
            channel.sudo().message_post(
                body=message,
                subject=_('Report Error: %s') % self.report_id.name,
                author_id=odoobot.id,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            _logger.info(f"Error notification sent via chat to user {self.user_id.name}")
        except Exception as e:
            _logger.warning(f"Error notification via chat failed: {e}")
