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
    birt_db_host = fields.Char(
        string="BIRT DB Host",
        help="PostgreSQL host as seen from the BIRT server "
             "(e.g. 'db' or '127.0.0.1' for an SSH tunnel). Sent to BIRT "
             "as report parameter at render time. Leave empty to use the "
             "BIRT server's own configuration (JVM system properties).",
    )
    birt_db_port = fields.Char(
        string="BIRT DB Port",
        help="PostgreSQL port as seen from the BIRT server.",
    )
    birt_db_name = fields.Char(
        string="BIRT DB Name",
        help="Database queried by BIRT reports.",
    )
    birt_db_user = fields.Char(
        string="BIRT DB User",
        help="PostgreSQL user for BIRT report queries.",
    )
    birt_db_password = fields.Char(
        string="BIRT DB Password",
        help="PostgreSQL password for BIRT report queries.",
    )
