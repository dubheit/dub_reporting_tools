{
    "name": "Reporting Tools - BIRT Demo",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Demo BIRT report: sales by customer in the on-screen viewer",
    "author": "Dubhe Srls",
    "website": "https://dubhe.it",
    "description": """
BIRT Demo Report
================

A wizard report showing what the BIRT engine does in Odoo:

- Sales by Customer (sale.order), grouped by customer with totals
- On-screen viewer: HTML preview and PDF, edit parameters, download
- Drilldown from the HTML preview to the customer and to the order
- Customer groups that fold and unfold in the HTML preview
- Labels, dates and amounts in the language of the user
    """,
    "depends": [
        "dub_reporting_birt",
        "sale_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "reports/report.xml",
        "views/sales_by_customer_wizard_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
