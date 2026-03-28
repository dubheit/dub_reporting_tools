from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    ilovepdf_public_key = fields.Char(
        string='ILovePDF Public Key',
        help='Public key from your ILovePDF developer account'
    )
    ilovepdf_secret_key = fields.Char(
        string='ILovePDF Secret Key',
        help='Secret key from your ILovePDF developer account'
    )
