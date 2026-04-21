{
    'name': 'Reporting Tools - ILovePDF Documents',
    'version': '19.0.1.0.1',
    'category': 'Document Management',
    'summary': 'ILovePDF integration for Odoo Documents',
    'description': """
ILovePDF Documents Integration
==============================

This module extends the ILovePDF integration to work with Odoo Enterprise
Documents module (document.document).

Features:
---------
* Process documents directly from Documents app
* All ILovePDF operations available on documents
* Results saved as new document versions
* Chatter notifications on processed documents
* Action automatically available on all folders (existing and new)

Requirements:
-------------
* dub_reporting_ilovepdf module
* Odoo Enterprise Documents module
    """,
    'author': 'Dubhe IT',
    'website': 'https://www.dubhe.it',
    'license': 'LGPL-3',
    'depends': ['dub_reporting_ilovepdf', 'documents'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/ilovepdf_documents_wizard_views.xml',
        'data/ir_actions_server_data.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
