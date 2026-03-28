import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class CarboneStudioConfigController(http.Controller):

    @http.route(
        "/carbone_config/studio_params",
        type="json", auth="user"
    )
    def get_studio_params(self):
        """Return Studio configuration for the JS widget."""
        company = request.env.company
        return {
            "js_url": company.carbone_studio_js_url or "",
            "api_url": company.carbone_api_url or "https://api.carbone.io",
            "enabled": company.carbone_studio_enabled,
        }
