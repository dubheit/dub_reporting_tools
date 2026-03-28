from odoo import models, fields


class ResUsersSettings(models.Model):
    """Extended user settings with SharePoint OAuth2 tokens."""

    _inherit = 'res.users.settings'

    sharepoint_token = fields.Char(
        string="SharePoint Access Token",
        groups="base.group_system",
    )
    sharepoint_rtoken = fields.Char(
        string="SharePoint Refresh Token",
        groups="base.group_system",
    )
    sharepoint_token_validity = fields.Datetime(
        string="Token Validity",
    )
