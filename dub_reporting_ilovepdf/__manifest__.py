{
    'name': 'Reporting Tools - ILovePDF',
    'version': '19.0.1.0.1',
    'category': 'Technical',
    'summary': 'ILovePDF API integration for document processing',
    'description': """
ILovePDF Integration
====================

This module integrates ILovePDF API for document processing operations
directly from Odoo attachments.

Features:
---------
* Convert Office documents to PDF (DOCX, XLSX, PPTX)
* Convert images to PDF
* Convert PDF to images
* Compress PDF files
* Merge multiple PDFs
* Split PDF into separate files
* Rotate PDF pages
* Add watermarks to PDFs
* Add page numbers
* Remove/add password protection
* Repair damaged PDFs
* Convert to PDF/A format
* OCR on scanned PDFs

Requirements:
-------------
* dub_reporting_base module
* ILovePDF API credentials (https://developer.ilovepdf.com)
    """,
    'author': 'Dubhe',
    'website': 'https://www.dubhe.it',
    'license': 'OPL-1',
    'price': 9.90,
    'currency': 'EUR',
    'depends': ['dub_reporting_base', 'mail'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings.xml',
        'views/ir_attachment_views.xml',
        'wizard/ilovepdf_wizard_views.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
