{
    "name": "Reporting Tools - Carbone",
    "version": "19.0.4.0.0",
    "category": "Tools",
    "summary": "Carbone.io reporting engine integration with Studio",
    "author": "Dubhe Srls",
    "website": "https://dubhe.it",
    "description": """
Carbone.io Reporting Engine
============================

This module integrates Carbone.io API v5 for advanced document generation.

Features:
---------
* Support for multiple output formats (PDF, DOCX, XLSX, ODT, ODS)
* Template caching for improved performance
* Asynchronous rendering with webhooks for large reports
* Carbone Studio integration for live template editing
* Full Carbone v5 API support (converter, timezone, complement, enum, etc.)
* Enhanced error handling and logging

Requirements:
-------------
* dub_reporting_base module
* Carbone.io API access token (https://carbone.io)
* Carbone Enterprise Edition license for Studio (optional)
    """,
    "depends": ["dub_reporting_base"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "wizard/carbone_studio_wizard_views.xml",
        "views/carbone_translation_views.xml",
        "views/res_config_settings.xml",
        "views/ir_actions_report_views.xml",
        "views/carbone_template_list_views.xml",
    ],
    "demo": [
        "demo/demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "dub_reporting_carbone/static/src/js/report_action.js",
            "dub_reporting_carbone/static/src/js/carbone_studio_widget.js",
            "dub_reporting_carbone/static/src/xml/carbone_studio.xml",
        ],
    },
    "pre_init_hook": "pre_init_hook",
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
