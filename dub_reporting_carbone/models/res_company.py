from odoo import models, fields, api, _


class ResCompany(models.Model):
    """Extended company model with Carbone.io configuration fields."""
    
    _inherit = 'res.company'

    # API Configuration
    carbone_api_url = fields.Char(
        string="Carbone API URL",
        default="https://api.carbone.io",
        help="Carbone.io API endpoint URL. Use https://api.carbone.io for cloud or your on-premise URL."
    )
    carbone_access_token = fields.Char(
        string="Carbone Access Token",
        help="API access token from Carbone.io. Get yours at https://account.carbone.io"
    )
    
    # Default Settings
    carbone_default_converter = fields.Selection(
        string="Default Converter",
        selection=[
            ('L', 'LibreOffice'),
            ('O', 'OnlyOffice'),
            ('C', 'Chromium'),
        ],
        help="Default converter engine for all Carbone reports"
    )
    carbone_default_timezone = fields.Selection(
        string="Default Timezone",
        selection=lambda self: self._get_timezone_selection(),
        help="Default timezone for date/time formatting in reports"
    )
    carbone_default_lang = fields.Selection(
        string="Default Language",
        selection=[
            ('en-us', 'English (US)'),
            ('en-gb', 'English (GB)'),
            ('fr-fr', 'French'),
            ('it-it', 'Italian'),
            ('de-de', 'German'),
            ('es-es', 'Spanish'),
        ],
        help="Default language code for formatting (numbers, dates, currencies)"
    )
    
    # Studio Integration
    carbone_studio_enabled = fields.Boolean(
        string="Enable Carbone Studio",
        default=False,
        help="Enable Carbone Studio integration for live template editing"
    )
    carbone_studio_js_url = fields.Char(
        string="Carbone Studio JS URL",
        default="https://bin.carbone.io/studio/5.1.1/carbone-studio.min.js",
        help="CDN URL for the Carbone Studio JavaScript file."
    )

    # Template Organization
    carbone_template_tag = fields.Char(
        string="Template Tag",
        default=lambda self: self.env.cr.dbname,
        help="Tag to associate with templates uploaded from Odoo. "
             "Used to filter templates in the list view. "
             "Leave empty to see all templates."
    )
    
    @api.model
    def _get_timezone_selection(self):
        """Get available timezone list for selection field.
        
        Returns:
            list: List of (value, label) tuples for timezone selection
        """
        import pytz
        return [(tz, tz) for tz in pytz.common_timezones]

