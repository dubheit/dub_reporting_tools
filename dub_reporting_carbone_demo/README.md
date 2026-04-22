# Reporting Tools — Carbone Demo

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-18.0-875A7B.svg)](https://www.odoo.com/)

Ready-to-use demo Carbone templates for Odoo — a gentle introduction to
the Carbone reporting engine on real Odoo models.

## What's inside

| Template | Model | Purpose |
|---|---|---|
| Invoice Simple | `account.move` | Clean, modern invoice layout |
| Quote with Datasheet | `sale.order` | Quotation + product datasheet composition |

Both templates come from Carbone's official
[examples catalogue](https://carbone.io/examples/), adapted to Odoo's data
model.

## Quick start

1. Install [`dub_reporting_carbone`](../dub_reporting_carbone) and
   configure your API token.
2. Install this module.
3. Open any customer invoice or sale order → **Print** → pick the Carbone
   variant.

That's it — no further setup needed.

## Use it as a learning resource

Open the template files under `reports/templates/` in Word or
LibreOffice to see how real Carbone tags wire up to Odoo records:
loops, conditions, formatters, translations.

## Dependencies

- [`dub_reporting_carbone`](../dub_reporting_carbone)
- `account` — for `account.move`
- `sale` — for `sale.order`

## Support

- **Website:** [dubhe.it](https://dubhe.it)
- **Email:** [support@dubhe.it](mailto:support@dubhe.it)
- **Issues:** [github.com/dubheit/dub_reporting_tools/issues](https://github.com/dubheit/dub_reporting_tools/issues)

## License

LGPL-3. Template files are provided by Carbone.io SAS as open examples.

Copyright © 2025 Dubhe Srls.
