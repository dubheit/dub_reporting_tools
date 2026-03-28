from odoo import models


class ResConfigSettings(models.TransientModel):
    """Base configuration settings for reporting engines.
    
    This model serves as a placeholder for engine-specific settings.
    Each reporting engine module should inherit this model to add
    their specific configuration fields.
    """
    
    _inherit = 'res.config.settings'
