{
    "name": "Reporting Tools - Carbone Direct Printing",
    "version": "18.0.1.0.0",
    "category": "Tools",
    "summary": "Bridge module: send Carbone reports to CUPS printers",
    "author": "Dubhe Srls",
    "website": "https://dubhe.it",
    "license": "LGPL-3",
    "depends": [
        "dub_reporting_carbone",
        "base_report_to_printer",
    ],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "dub_reporting_carbone_printer/static/src/js/carbone_print_handler.esm.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": True,
}
