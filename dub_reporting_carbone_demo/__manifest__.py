{
    "name": "Reporting Tools - Carbone Demo",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Demo Carbone reports for invoices and sales orders",
    "author": "Dubhe",
    "website": "https://www.dubhe.it",
    "description": """
Carbone Demo Reports
=====================

Demo reports using Carbone.io templates from https://carbone.io/examples/

Includes:
- Invoice Simple (account.move)
- Quote with Datasheet (sale.order)

Templates are provided by CarboneIO SAS as open examples.
    """,
    "depends": [
        "dub_reporting_carbone",
        "account",
        "sale",
    ],
    "data": [
        "reports/report.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
