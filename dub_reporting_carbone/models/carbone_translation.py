import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CarboneTranslation(models.Model):
    _name = "carbone.translation"
    _description = "Carbone Report Translation"
    _order = "report_id, key"

    report_id = fields.Many2one(
        "ir.actions.report",
        string="Report",
        required=True,
        ondelete="cascade",
    )
    key = fields.Char(
        string="Key",
        required=True,
        help="Translation key used in the template with {t(key)} syntax.",
    )
    value = fields.Char(
        string="Value",
        required=True,
        translate=True,
        help="Translated text. Use the translation icon to add other languages.",
    )

    _sql_constraints = [
        (
            "unique_key_per_report",
            "unique(report_id, key)",
            "Translation key must be unique per report.",
        ),
    ]

    @api.model
    def get_translations_for_report(self, report_id, lang_codes=None):
        """Build Carbone translations payload from Odoo translations.

        Returns a dict like:
            {"it-it": {"key1": "val1"}, "en-us": {"key1": "val1"}}
        """
        lines = self.search([("report_id", "=", report_id)])
        if not lines:
            return {}

        if not lang_codes:
            lang_codes = (
                self.env["res.lang"]
                .search([("active", "=", True)])
                .mapped("code")
            )

        translations = {}
        for lang_code in lang_codes:
            carbone_lang = lang_code.replace("_", "-").lower()
            lang_dict = {}
            for line in lines.with_context(lang=lang_code):
                lang_dict[line.key] = line.value or ""
            translations[carbone_lang] = lang_dict

        return translations
