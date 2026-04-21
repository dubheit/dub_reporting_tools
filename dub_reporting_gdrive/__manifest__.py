{
    'name': 'Reporting Tools - Google Drive',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'Sync templates from Google Drive to Odoo',
    'author': 'Dubhe',
    'website': 'https://www.dubhe.it',
    'description': """
Google Drive Integration for Report Templates
==============================================

Sync report templates from Google Drive to Odoo attachments.
Any reporting module (Carbone, ILovePDF, etc.) can then read from these attachments.

Features
--------
* Select templates directly from Google Drive
* Support for Google Docs (exported as DOCX)
* Support for Google Sheets (exported as XLSX)
* Support for native DOCX/XLSX/ODT/ODS files
* Manual sync button
* Automatic sync via Google Drive Push Notifications
* Service Account authentication (server-to-server)
* OAuth2 authentication (per-user access)

Requirements
------------
* google-api-python-client
* google-auth
* google-auth-oauthlib
    """,
    'depends': ['dub_reporting_base'],
    'external_dependencies': {
        'python': [
            'google-api-python-client',
            'google-auth',
            'google-auth-oauthlib',
        ]
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
        'views/ir_actions_report_views.xml',
        'wizard/gdrive_file_picker_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
