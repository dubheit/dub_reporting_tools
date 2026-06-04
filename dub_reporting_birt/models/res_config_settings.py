from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    birt_base_url = fields.Char(
        related='company_id.birt_base_url',
        readonly=False,
    )
    birt_username = fields.Char(
        related='company_id.birt_username',
        readonly=False,
    )
    birt_password = fields.Char(
        related='company_id.birt_password',
        readonly=False,
    )
    birt_odoo_internal_url = fields.Char(
        related='company_id.birt_odoo_internal_url',
        readonly=False,
    )
    birt_db_host = fields.Char(
        related='company_id.birt_db_host',
        readonly=False,
    )
    birt_db_port = fields.Char(
        related='company_id.birt_db_port',
        readonly=False,
    )
    birt_db_name = fields.Char(
        related='company_id.birt_db_name',
        readonly=False,
    )
    birt_db_user = fields.Char(
        related='company_id.birt_db_user',
        readonly=False,
    )
    birt_db_password = fields.Char(
        related='company_id.birt_db_password',
        readonly=False,
    )
