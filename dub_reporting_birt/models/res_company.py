from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    birt_base_url = fields.Char(
        string="BIRT Server URL",
        help="Base URL of the BIRT viewer (e.g. http://birt:8080/birt)",
    )
    birt_username = fields.Char(string="BIRT Username")
    birt_password = fields.Char(string="BIRT Password")
    birt_odoo_internal_url = fields.Char(
        string="Odoo Internal URL",
        default="http://odoo:8069",
        help="URL used by the BIRT container to reach Odoo "
             "(Docker service name). Used for HTTP template serving.",
    )
