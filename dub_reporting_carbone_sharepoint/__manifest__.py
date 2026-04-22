{
    'name': 'Reporting Tools - Carbone + SharePoint',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Bridge module: Use SharePoint templates with Carbone',
    'author': 'Dubhe Srls',
    'website': 'https://dubhe.it',
    'description': """
Carbone + SharePoint Integration
================================

This bridge module integrates SharePoint/OneDrive templates with Carbone reports.

Features:
---------
* Select Carbone templates from SharePoint/OneDrive
* Sync templates automatically when files change
* Save modified templates back to SharePoint

Requirements:
-------------
* dub_reporting_carbone module
* dub_reporting_sharepoint module

This module is automatically installed when both Carbone and SharePoint
modules are present.
    """,
    'depends': [
        'dub_reporting_carbone',
        'dub_reporting_sharepoint',
    ],
    'data': [
        'views/ir_actions_report_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': True,
}
