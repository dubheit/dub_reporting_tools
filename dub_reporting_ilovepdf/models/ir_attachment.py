from odoo import fields, models


class IrAttachment(models.Model):
    _name = 'ir.attachment'
    _inherit = ['ir.attachment', 'mail.thread']

    # Add tracking on key fields
    name = fields.Char(tracking=True)
