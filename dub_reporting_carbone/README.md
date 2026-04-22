# Reporting Tools — Carbone

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-19.0-875A7B.svg)](https://www.odoo.com/)
[![Carbone](https://img.shields.io/badge/Carbone-v5-3ECFB4.svg)](https://carbone.io/)
[![CI](https://github.com/dubheit/dub_reporting_tools/actions/workflows/test.yml/badge.svg?branch=19.0)](https://github.com/dubheit/dub_reporting_tools/actions)

Render pixel-perfect DOCX, XLSX, PDF, ODT and ODS reports from Odoo using
[Carbone.io](https://carbone.io/) — the template engine that lets
business users design reports in Word or Excel instead of XML.

---

## Table of Contents

- [Why Carbone](#why-carbone)
- [Features](#features)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Template authoring](#template-authoring)
- [Studio integration](#studio-integration)
- [Output formats](#output-formats)
- [Asynchronous rendering](#asynchronous-rendering)
- [Template storage bridges](#template-storage-bridges)
- [Dependencies](#dependencies)
- [Development & tests](#development--tests)
- [Support](#support)
- [License](#license)

---

## Why Carbone

QWeb is powerful but asks your finance team to read HTML/XML. Carbone turns
the relationship around: business users design templates in **Word, Excel,
LibreOffice or Google Docs**, mark fields with `{d.field_name}` tags, and
Carbone renders them back with real data — preserving every fonts, border
and layout pixel.

This module brings the full Carbone v5 API into Odoo: just pick "Carbone"
as the report engine, upload your template, and your existing
`ir.actions.report` works like before.

## Features

- **Design in Office tools** — DOCX, XLSX, ODT, ODS templates authored in Word/Excel/LibreOffice
- **Multiple output formats** — PDF, DOCX, XLSX, ODT, ODS (and anything else Carbone can convert to)
- **Template caching** — Carbone hashes each template to avoid redundant uploads
- **Asynchronous rendering** — webhooks for large reports
- **Carbone Studio** — live in-browser template editor (requires Carbone Enterprise)
- **Translations** — localise content per language using the Carbone `i18n` engine
- **Full v5 API support** — converter, timezone, complement, enum, currency, units, and more
- **Enhanced logging** — every call traced with render time and payload size

## Architecture

```text
┌──────────────┐        ┌──────────────────┐       ┌──────────────────┐
│ ir.actions.  │  ──▶   │ dub_reporting_   │  ──▶  │ api.carbone.io   │
│ report       │        │ carbone          │       │ (cloud or self-  │
│ (type=       │        │                  │       │  hosted)         │
│ carbone)     │  ◀──   │  - upload tmpl   │  ◀──  │                  │
└──────────────┘ bytes  │  - render         │ PDF/  └──────────────────┘
                        │  - translate      │ DOCX
                        │  - cache          │
                        └──────────────────┘
```

## Quick start

### 1. Get a Carbone API token

Sign up at [carbone.io](https://carbone.io/) (free tier available) and
copy your API token.

### 2. Configure Odoo

**Settings → Technical → Reporting → Carbone**:

| Field | Purpose |
|---|---|
| API URL | `https://api.carbone.io` (cloud) or your self-hosted endpoint |
| API Token | Personal access token from Carbone |
| API Version | `5` (default) |
| Async Threshold | Reports longer than N records use webhooks |

### 3. Create a Carbone report

Go to **Technical → Actions → Reports**, set:

- **Report Type**: Carbone
- **Template**: upload your `.docx` / `.xlsx` / `.odt` / `.ods`
- **Output**: pick the target format (PDF is the most common)

### 4. Use it

Attach the report to any form (invoice, sale order, partner, …) like a
regular Odoo report. Users click Print — Carbone does the rest.

## Template authoring

Carbone tags are intuitive. In a Word document you write:

```text
Hello {d.partner_id.name},

Your invoice {d.name} for {d.amount_total:formatC(EUR)} is due
on {d.invoice_date_due:formatD(DD/MM/YYYY)}.

{d.invoice_line_ids[i].name}      {d.invoice_line_ids[i].price_subtotal}
{d.invoice_line_ids[i+1].name}    {d.invoice_line_ids[i+1].price_subtotal}
```

Full Carbone syntax reference: [carbone.io/documentation](https://carbone.io/documentation.html).

## Studio integration

If you have a **Carbone Enterprise** licence, the module embeds **Carbone
Studio** — a live, browser-based template editor. Click *Edit in Studio*
from any Carbone report and your template opens in the Studio UI with
Odoo data bindings preloaded.

## Output formats

| Input template | Output options |
|---|---|
| `.docx` | DOCX, PDF, ODT |
| `.xlsx` | XLSX, PDF, ODS |
| `.odt` | ODT, DOCX, PDF |
| `.ods` | ODS, XLSX, PDF |
| `.html` | HTML, PDF |

## Asynchronous rendering

Reports above the configured threshold are rendered asynchronously:

1. Odoo submits the request and receives a `render_id`.
2. Carbone processes in the background and hits the webhook.
3. Odoo downloads the result and attaches it to the user's session.

This keeps Odoo responsive on large reports and avoids HTTP timeouts.

## Template storage bridges

Two optional bridge modules let you source Carbone templates from cloud
drives:

- [`dub_reporting_carbone_gdrive`](../dub_reporting_carbone_gdrive) — Google Drive
- [`dub_reporting_carbone_sharepoint`](../dub_reporting_carbone_sharepoint) — SharePoint / OneDrive

Each auto-installs when both Carbone and the corresponding storage module
are present.

## Dependencies

- [`dub_reporting_base`](../dub_reporting_base)
- Python: `requests`
- External service: Carbone.io API (cloud or self-hosted)

## Development & tests

```bash
odoo -c odoo.conf -d test_db --test-tags /dub_reporting_carbone \
     --stop-after-init --http-port=0
```

## Support

- **Website:** [dubhe.it](https://dubhe.it)
- **Email:** [support@dubhe.it](mailto:support@dubhe.it)
- **Issues:** [github.com/dubheit/dub_reporting_tools/issues](https://github.com/dubheit/dub_reporting_tools/issues)

## License

LGPL-3. Copyright © 2025 Dubhe Srls.
