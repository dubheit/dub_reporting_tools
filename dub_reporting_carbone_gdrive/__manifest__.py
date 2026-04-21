{
    'name': 'Reporting Tools - Carbone + Google Drive',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'Bridge module: Use Google Drive templates with Carbone',
    'author': 'Dubhe',
    'website': 'https://www.dubhe.it',
    'description': """
Carbone + Google Drive Integration
==================================

This bridge module integrates Google Drive templates with Carbone reports.

Features:
---------
* Select Carbone templates from Google Drive
* Sync templates automatically when files change
* Save modified templates back to Google Drive

Requirements:
-------------
* dub_reporting_carbone module
* dub_reporting_gdrive module

This module is automatically installed when both Carbone and Google Drive
modules are present.
    """,
    'depends': [
        'dub_reporting_carbone',
        'dub_reporting_gdrive',
    ],
    'data': [
        'views/ir_actions_report_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': True,
}
