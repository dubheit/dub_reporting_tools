# Reporting Tools — iLovePDF for Documents

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-18.0-875A7B.svg)](https://www.odoo.com/)

Bring every **iLovePDF** operation straight into Odoo Enterprise's
**Documents** app.

## What it does

The base [`dub_reporting_ilovepdf`](../dub_reporting_ilovepdf) module adds
PDF operations to any `ir.attachment`. This bridge extends the same
wizard to `document.document`, so users can merge, split, compress, OCR,
watermark, protect — all from inside the Documents workspace.

## Features

- Same PDF operations as [`dub_reporting_ilovepdf`](../dub_reporting_ilovepdf),
  available from the Documents view
- Results saved as new **document versions** (history preserved)
- Chatter notification on each processed document
- Action automatically available on all Documents folders — existing and
  future — via a `post_init_hook`

## Quick start

1. Install [`dub_reporting_ilovepdf`](../dub_reporting_ilovepdf) and
   configure your iLovePDF Public Key.
2. Install this module (Odoo Enterprise `documents` must be present).
3. Open any document → **Action → Process with iLovePDF**.

## Dependencies

- [`dub_reporting_ilovepdf`](../dub_reporting_ilovepdf)
- `documents` — Odoo Enterprise Documents module

## Support

- **Website:** [dubhe.it](https://dubhe.it)
- **Email:** [support@dubhe.it](mailto:support@dubhe.it)
- **Issues:** [github.com/dubheit/dub_reporting_tools/issues](https://github.com/dubheit/dub_reporting_tools/issues)

## License

LGPL-3. Copyright © 2025 Dubhe Srls.
