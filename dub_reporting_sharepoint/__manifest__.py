{
    'name': 'Reporting Tools - SharePoint',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Sync templates from SharePoint/OneDrive to Odoo',
    'author': 'Dubhe',
    'website': 'https://www.dubhe.it',
    'description': """
SharePoint/OneDrive Integration for Report Templates
=====================================================

Sync report templates from SharePoint or OneDrive to Odoo attachments.
Any reporting module (Carbone, ILovePDF, etc.) can then read from these attachments.

Features
--------
* Select templates directly from SharePoint/OneDrive
* Support for Word documents (DOCX)
* Support for Excel spreadsheets (XLSX)
* Support for PowerPoint presentations (PPTX)
* Manual sync button
* Automatic sync via Microsoft Graph webhooks
* App Registration authentication (server-to-server)
* OAuth2 authentication (per-user access)

Requirements
------------
* msal (Microsoft Authentication Library)
* requests
    """,
    'depends': ['dub_reporting_base'],
    'external_dependencies': {
        'python': [
            'msal',
            'requests',
        ]
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
        'views/ir_actions_report_views.xml',
        'wizard/sharepoint_file_picker_views.xml',
    ],
    'license': 'OPL-1',
    'installable': True,
    'application': False,
    'auto_install': False,
}
