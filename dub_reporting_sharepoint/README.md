# Reporting Tools — SharePoint / OneDrive

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-19.0-875A7B.svg)](https://www.odoo.com/)
[![CI](https://github.com/dubheit/dub_reporting_tools/actions/workflows/test.yml/badge.svg?branch=19.0)](https://github.com/dubheit/dub_reporting_tools/actions)

Sync report templates from **Microsoft SharePoint** or **OneDrive**
directly into Odoo attachments via Microsoft Graph.

---

## What it does

Let any reporting module (Carbone, BIRT, iLovePDF, …) consume templates
kept in your corporate SharePoint site or personal OneDrive. Updates in
the source file flow back into Odoo automatically.

## Features

- **Browse SharePoint / OneDrive** from a native Odoo file picker
- **Supports DOCX, XLSX, PPTX** — native Office formats
- **Manual sync** — one-click refresh of any template
- **Automatic sync** via Microsoft Graph webhooks
- **Two auth options**
  - App Registration (service principal) — server-to-server, no per-user consent
  - OAuth2 — per-user access, respects SharePoint ACLs

## Quick start

### 1. Register an Azure AD application

In [portal.azure.com](https://portal.azure.com/) → **Azure Active
Directory → App registrations → New registration**:

- Grant the `Files.Read.All` (or `Files.ReadWrite.All`) Graph permission.
- For service auth: create a client secret.
- For OAuth2 auth: configure a redirect URI pointing to Odoo.

### 2. Configure Odoo

**Settings → Technical → Reporting → SharePoint**:

| Field | Purpose |
|---|---|
| Tenant ID | From Azure AD |
| Client ID | From Azure AD app registration |
| Auth method | App Registration or OAuth2 |
| Credentials | Client secret / client ID + redirect |

### 3. Attach a SharePoint template to any report

Open any Carbone / BIRT / iLovePDF report definition and pick "From
SharePoint" in the template source. Browse, pick, done.

## Automatic sync

The module subscribes to Microsoft Graph change notifications. Any
change to a watched file triggers a re-sync into the Odoo attachment,
so your next render already uses the latest version.

## Dependencies

- [`dub_reporting_base`](../dub_reporting_base)
- Python: `msal` (Microsoft Authentication Library), `requests`

## Support

- **Website:** [dubhe.it](https://dubhe.it)
- **Email:** [support@dubhe.it](mailto:support@dubhe.it)
- **Issues:** [github.com/dubheit/dub_reporting_tools/issues](https://github.com/dubheit/dub_reporting_tools/issues)

## License

LGPL-3. Copyright © 2025 Dubhe Srls.
