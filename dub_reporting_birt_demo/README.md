# Reporting Tools — BIRT Demo

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-18.0-875A7B.svg)](https://www.odoo.com/)

A ready-to-use BIRT report on real Odoo data — a tour of what the BIRT
engine of [`dub_reporting_birt`](../dub_reporting_birt) does, and in
particular of the on-screen viewer of wizard reports.

## What's inside

| Report | Data | Where |
|---|---|---|
| Sales by Customer (BIRT) | `sale.order` | **Sales → Reporting → Sales by Customer (BIRT)** |

In Italian the menu is **Vendite → Rendicontazione → Vendite per cliente
(BIRT)**.

The wizard asks for the company, the period (default: the current year)
and whether to include the quotations (default: confirmed orders only).
**Print** opens the report in the viewer:

- **HTML preview** first, with a switch to **PDF** (pdf.js), zoom,
  **Edit parameters** (reopens the wizard) and **Download** (PDF).
- **Grouped by customer** (the commercial partner of the order), with the
  order date, number, salesperson, untaxed amount and total, a total per
  customer and a grand total.
- **Folding**: click a customer row to fold or unfold its orders; the
  viewer buttons fold or unfold them all. The customer totals stay visible.
- **Drilldown**: the customer name opens the customer, the order number
  opens the order, "Orders: N" opens the list of the customer's orders with
  the filters of the report.
- **Language of the user**: labels, dates and amounts follow the language
  of the user (English and Italian included); the period is in the user
  timezone.

The links and the row ids used for folding are only emitted in the HTML
preview: the PDF carries no dead links.

Amounts are in the company currency: an order in another currency is
converted with the rate stored on the order (`currency_rate`, the rate at
the order date).

The menu is visible to the Sales administrators (**Sales / Administrator**),
the only ones allowed to run the wizard: BIRT reads the orders straight
from PostgreSQL, without the record rules of the salespersons.

## Quick start

1. Install [`dub_reporting_birt`](../dub_reporting_birt) and configure it
   in **Settings → Reporting Tools**: the BIRT server URL, the URL BIRT
   uses to reach Odoo (it downloads the template from Odoo) and, if the
   BIRT server does not have them already, the database connection fields.
2. Install this module (it depends on the Sales app).
3. Go to **Sales → Reporting → Sales by Customer (BIRT)** and print.

The PDF goes through the two-phase endpoint `/run2phase`, a custom servlet
of the BIRT server (see the **Render Endpoint** field of
`dub_reporting_birt`); the HTML preview uses the standard `/preview`
endpoint. On a BIRT server without `/run2phase`, set **Render Endpoint** to
*Viewer (/run)* on the report (**Settings → Technical → Reports**).

## Use it as a learning resource

The template is `reports/templates/sales_by_customer.rptdesign`, the
wizard is `wizards/sales_by_customer_wizard.py`. They show how to:

- pass filters, translated labels and the date and number formats of the
  user language as report parameters (`_get_birt_params`);
- read the database connection from the `db_*` parameters sent by Odoo,
  with the BIRT server settings as fallback (root-level `propertyBindings`);
- mark group header, detail and group footer rows with the bookmarks
  `h|<keys>|`, `d|<keys>|<n>` and `t|<keys>|` for the folding;
- open a record (`odoo-drill:?key=record&model=<model>&id=<id>`) or a
  custom action (`odoo-drill:?key=orders&partner_id=<id>`, handled by
  `_get_birt_drilldown_action`) from the HTML preview;
- keep the template in the module: it is loaded into the report at every
  install and update of the module.

## Dependencies

- [`dub_reporting_birt`](../dub_reporting_birt)
- `sale_management` — the Sales app

## Support

- **Website:** [dubhe.it](https://dubhe.it)
- **Email:** [support@dubhe.it](mailto:support@dubhe.it)
- **Issues:** [github.com/dubheit/dub_reporting_tools/issues](https://github.com/dubheit/dub_reporting_tools/issues)

## License

LGPL-3.

Copyright © 2026 Dubhe Srls.
