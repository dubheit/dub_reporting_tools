{
    'name': 'Reporting Base',
    'version': '18.0.1.1.0',
    'category': 'Technical',
    'summary': 'Base module for external reporting engines integration',
    'description': """
Reporting Base Module
=====================

This module provides common functionality for integrating external reporting
engines (Carbone, BIRT, Jasper, etc.) with Odoo.

Features:
---------
* Abstract methods for report engine routing
* Common utilities for validation, logging, and error handling
* Base controller and JavaScript framework
* Settings section for engine-specific configurations

This is a technical module that should be installed as a dependency
for specific reporting engine modules.
    """,
    'author': 'Dubhe Srls',
    'website': 'https://dubhe.it',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'views/res_config_settings.xml',
        'views/ir_actions_report_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dub_reporting_base/static/src/js/report_action.js',
        ],
    },
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
