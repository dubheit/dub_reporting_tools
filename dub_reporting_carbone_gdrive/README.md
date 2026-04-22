# Reporting Tools — Carbone + Google Drive

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-19.0-875A7B.svg)](https://www.odoo.com/)

Bridge module: use **Google Drive** as the source of truth for your
**Carbone** templates.

## What it does

Auto-installed when both [`dub_reporting_carbone`](../dub_reporting_carbone)
and [`dub_reporting_gdrive`](../dub_reporting_gdrive) are present. It
glues them together so Carbone report templates can live in Google
Drive and refresh automatically.

## Features

- Pick Carbone templates from a Google Drive file picker
- Automatic template refresh when the source Doc/file changes
- Push modified templates back to Google Drive (round-trip edit)

## Quick start

Just install it — everything else is handled by the two modules it
bridges.

1. Make sure [`dub_reporting_carbone`](../dub_reporting_carbone) is
   configured with a working Carbone API token.
2. Make sure [`dub_reporting_gdrive`](../dub_reporting_gdrive) is
   authenticated against Google.
3. Open any Carbone report — you'll now see *"From Google Drive"* as a
   template source.

## Dependencies

- [`dub_reporting_carbone`](../dub_reporting_carbone)
- [`dub_reporting_gdrive`](../dub_reporting_gdrive)

## Support

- **Website:** [dubhe.it](https://dubhe.it)
- **Email:** [support@dubhe.it](mailto:support@dubhe.it)

## License

LGPL-3. Copyright © 2025 Dubhe Srls.
