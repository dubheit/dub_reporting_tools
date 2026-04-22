# Reporting Tools — Google Drive

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-19.0-875A7B.svg)](https://www.odoo.com/)
[![CI](https://github.com/dubheit/dub_reporting_tools/actions/workflows/test.yml/badge.svg?branch=19.0)](https://github.com/dubheit/dub_reporting_tools/actions)

Sync report templates from **Google Drive** straight into Odoo
attachments — no more emailing DOCX files around.

---

## What it does

Give any reporting module (Carbone, BIRT, iLovePDF, …) access to
templates stored in Google Drive. Updates in the source Google Doc, Sheet
or uploaded file flow back into Odoo automatically.

## Features

- **Browse Google Drive** from a native Odoo file picker
- **Supports Google Docs** (exported as DOCX on the fly)
- **Supports Google Sheets** (exported as XLSX)
- **Supports native** DOCX, XLSX, ODT, ODS files
- **Manual sync** — one-click refresh of any template
- **Automatic sync** via Google Drive push notifications (webhooks)
- **Two auth options**
  - Service Account — server-to-server, no per-user consent
  - OAuth2 — per-user access, respects Drive sharing rules

## Quick start

### 1. Set up a Google Cloud project

In [console.cloud.google.com](https://console.cloud.google.com/):

- Create (or pick) a project.
- Enable the **Google Drive API**.
- Create either a **Service Account** *or* an **OAuth2 Client ID**.

### 2. Configure Odoo

**Settings → Technical → Reporting → Google Drive**:

| Field | Purpose |
|---|---|
| Auth method | Service Account or OAuth2 |
| Credentials | Uploaded JSON key / client ID + secret |
| Shared Drive ID | Optional — pick a specific drive |

### 3. Attach a Drive template to any report

Open a Carbone / BIRT / iLovePDF report definition and pick "From Google
Drive" in the template source. Browse, pick, done.

## Automatic sync

The module registers a Drive push notification channel. Any change to a
watched file triggers a cron-free re-sync into the Odoo attachment, so
your next render already uses the latest version.

## Dependencies

- [`dub_reporting_base`](../dub_reporting_base)
- Python: `google-api-python-client`, `google-auth`, `google-auth-oauthlib`

## Support

- **Website:** [dubhe.it](https://dubhe.it)
- **Email:** [support@dubhe.it](mailto:support@dubhe.it)
- **Issues:** [github.com/dubheit/dub_reporting_tools/issues](https://github.com/dubheit/dub_reporting_tools/issues)

## License

LGPL-3. Copyright © 2025 Dubhe Srls.
