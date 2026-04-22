{
    "name": "Reporting Tools - BIRT",
    "version": "18.0.1.0.0",
    "category": "Tools",
    "summary": "Eclipse BIRT reporting engine integration",
    "author": "Dubhe Srls",
    "website": "https://dubhe.it",
    "description": """
Eclipse BIRT Reporting Engine
==============================

This module integrates Eclipse BIRT for advanced report generation.

Features:
---------
* Upload .rptdesign templates and serve them to the BIRT engine via HTTP
* BIRT server renders reports in PDF (or other formats)
* JDBC connection string and format version management
* Supports HTTP template mode (Odoo serves templates to BIRT container)

Requirements:
-------------
* dub_reporting_base module
* Eclipse BIRT server (e.g. via Docker container)
    """,
    "depends": ["dub_reporting_base"],
    "external_dependencies": {"python": ["requests", "lxml"]},
    "data": [
        "views/ir_actions_report_views.xml",
        "views/res_config_settings.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
