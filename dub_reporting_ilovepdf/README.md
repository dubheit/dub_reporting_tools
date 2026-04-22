# Reporting Tools — iLovePDF

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-19.0-875A7B.svg)](https://www.odoo.com/)
[![iLovePDF](https://img.shields.io/badge/iLovePDF-API-E05D44.svg)](https://developer.ilovepdf.com/)
[![CI](https://github.com/dubheit/dub_reporting_tools/actions/workflows/test.yml/badge.svg?branch=19.0)](https://github.com/dubheit/dub_reporting_tools/actions)

Run **13+ PDF operations** on any Odoo attachment — merge, split, compress,
OCR, watermark, password-protect — through the
[iLovePDF](https://developer.ilovepdf.com/) API. No Python libraries to
install, no PDF engine to maintain.

---

## Table of Contents

- [What it does](#what-it-does)
- [Supported operations](#supported-operations)
- [Features](#features)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Using the wizard](#using-the-wizard)
- [Extending to Documents](#extending-to-documents)
- [Dependencies](#dependencies)
- [Development & tests](#development--tests)
- [Support](#support)
- [License](#license)

---

## What it does

Every PDF or Office attachment in Odoo gains a **Process with iLovePDF**
action. Pick an operation, tweak the options, and get a processed
document back — attached to the same record, chatter message included.

Works on any `ir.attachment`: invoices, quotations, purchase orders,
projects, custom modules — if Odoo can attach it, iLovePDF can process it.

## Supported operations

| Category | Operations |
|---|---|
| **Convert to PDF** | Office → PDF (DOCX/XLSX/PPTX), Images → PDF, HTML → PDF |
| **Convert from PDF** | PDF → Images (JPG/PNG), PDF → Office (DOCX/XLSX), PDF → PDF/A |
| **Optimise** | Compress, Repair damaged |
| **Organise** | Merge multiple PDFs, Split a PDF, Extract pages |
| **Transform** | Rotate, Add watermark, Add page numbers |
| **Secure** | Add password, Remove password |
| **Recognise** | OCR scanned PDFs |

## Features

- 🔌 **Cloud-powered** — no local PDF libraries to install or maintain
- 🔐 **API token auth** — scoped per Odoo instance
- 🧩 **Wizard-driven** — consistent UX across all operations
- 📎 **Attachment-based** — works on anything `ir.attachment` stores
- 💬 **Chatter notifications** — users see what ran on their records
- 🌐 **Documents integration** — optional bridge to Odoo Enterprise's Documents app

## Architecture

```text
┌──────────────┐   pick       ┌──────────────────┐   start task   ┌──────────────┐
│ ir.attachment│ ─operation─▶ │ dub_reporting_   │ ─────────────▶ │ iLovePDF API │
│              │   via wizard │ ilovepdf wizard  │                │ (cloud)      │
│              │              │                  │ ◀─────────────  │              │
│              │ ◀──────────  │ download result  │   processed    │              │
└──────────────┘  attached    └──────────────────┘   file         └──────────────┘
                   & chatter
```

Each operation follows the same three-step pattern:
`start task → upload source → execute → download result`.

## Quick start

### 1. Get an iLovePDF developer account

Register at [developer.ilovepdf.com](https://developer.ilovepdf.com/) and
copy your **Public Key** (project token). A generous free tier is
available.

### 2. Configure Odoo

**Settings → Technical → Reporting → iLovePDF**:

| Field | Purpose |
|---|---|
| Public Key | From iLovePDF developer dashboard |
| API URL | `https://api.ilovepdf.com` (default) |
| Result Retention | How long results are kept attached to chatter |

### 3. Use it

Open any attachment in Odoo, click **Process with iLovePDF**, pick an
operation, configure its parameters, and click Run. The processed file
appears as a new attachment on the same record.

## Using the wizard

Each operation exposes its own parameters:

| Operation | Relevant parameters |
|---|---|
| Compress | Compression level (low/recommended/extreme) |
| Watermark | Text or image, position, opacity, rotation |
| Page numbers | Starting number, position, font, first page |
| Split | Page ranges or every N pages |
| Merge | Order of attachments |
| Protect | Password, permissions (print/copy) |
| OCR | Language (50+ languages supported) |

## Extending to Documents

The companion module
[`dub_reporting_ilovepdf_documents`](../dub_reporting_ilovepdf_documents)
adds the same operations to Odoo Enterprise's **Documents** app — right
inside the document preview.

## Dependencies

- [`dub_reporting_base`](../dub_reporting_base)
- `mail` — for chatter notifications
- Python: `requests`
- External service: iLovePDF API credentials

## Development & tests

```bash
odoo -c odoo.conf -d test_db --test-tags /dub_reporting_ilovepdf \
     --stop-after-init --http-port=0
```

## Support

- **Website:** [dubhe.it](https://dubhe.it)
- **Email:** [support@dubhe.it](mailto:support@dubhe.it)
- **Issues:** [github.com/dubheit/dub_reporting_tools/issues](https://github.com/dubheit/dub_reporting_tools/issues)

## License

LGPL-3. Copyright © 2025 Dubhe Srls.
