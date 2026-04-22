# Reporting Tools — BIRT

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-19.0-875A7B.svg)](https://www.odoo.com/)
[![BIRT](https://img.shields.io/badge/BIRT-Eclipse-F0B429.svg)](https://eclipse-birt.github.io/birt-website/)
[![CI](https://github.com/dubheit/dub_reporting_tools/actions/workflows/test.yml/badge.svg?branch=19.0)](https://github.com/dubheit/dub_reporting_tools/actions)

Integrate **Eclipse BIRT** — the industry-standard data-driven reporting
engine — directly into Odoo. Perfect for complex, analytical, cross-module
reports that query PostgreSQL straight with SQL.

---

## Table of Contents

- [Why BIRT](#why-birt)
- [Features](#features)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Template authoring](#template-authoring)
- [HTTP template mode](#http-template-mode)
- [JDBC configuration](#jdbc-configuration)
- [Supported output formats](#supported-output-formats)
- [Dependencies](#dependencies)
- [Development & tests](#development--tests)
- [Support](#support)
- [License](#license)

---

## Why BIRT

BIRT is what you reach for when QWeb is not enough and you need:

- **Cross-module reports** that pull from 10+ Odoo tables with joins.
- **Data-heavy layouts** — aged-receivables listings, audit reports, KPI dashboards.
- **Precise pagination** — page breaks on grouped data, running totals, headers and footers exactly where you want them.
- **Charts and crosstabs** built inside the report, not assembled from screenshots.

BIRT runs as a separate Java engine. This module lets Odoo upload
`.rptdesign` templates to the engine over HTTP and stream back the rendered
output.

## Features

- 📤 **HTTP template serving** — Odoo hosts the template, BIRT fetches it on demand
- 🎨 **`.rptdesign` templates** — designed in the free Eclipse BIRT Designer
- 🖨️ **Multiple output formats** — PDF (most common), DOCX, XLSX, HTML
- 🔗 **JDBC connection string management** — per-company overrides supported
- 🏷️ **Version-aware output** — pin BIRT output format to specific engine versions
- 🐳 **Works great with containers** — point Odoo at a BIRT Docker image and you're done

## Architecture

```text
┌───────────────────┐  POST /render      ┌──────────────────────┐
│ Odoo              │ ───────────────▶  │ BIRT engine          │
│ ir.actions.report │  (template URL,   │ (Docker container)    │
│ type=birt         │   JDBC, params)   │                      │
│                   │                    │ 1. Fetch template    │
│ GET /report/tmpl/ │  ◀───────────────  │    from Odoo         │
│   {action_id}     │  (rptdesign xml)  │ 2. Query PostgreSQL  │
│                   │                    │    via JDBC          │
│                   │  ◀───────────────  │ 3. Render PDF/DOCX   │
│                   │  (binary stream)   │ 4. Return to Odoo    │
└───────────────────┘                    └──────────────────────┘
```

## Quick start

### 1. Run a BIRT engine

The easiest way is Docker. Any image that exposes the standard BIRT
viewer REST endpoint works. Example:

```bash
docker run -d --name birt \
  -p 8080:8080 \
  -e JDBC_URL="jdbc:postgresql://host.docker.internal:5432/odoo?user=odoo&password=odoo" \
  your-birt-image
```

### 2. Configure Odoo

**Settings → Technical → Reporting → BIRT**:

| Field | Example |
|---|---|
| BIRT Server URL | `http://birt:8080` |
| JDBC URL | `jdbc:postgresql://db:5432/odoo?user=odoo&password=odoo` |
| Output Format Version | `4.15` (match your engine) |

### 3. Create a BIRT report

**Technical → Actions → Reports → Create**:

- **Report Type**: BIRT
- **Output**: `application/pdf` (or whatever MIME type you need)
- **Template** (upload your `.rptdesign` file)

### 4. Print it

Attach the report to any model with a standard Odoo report action. Users
click Print, BIRT renders, Odoo returns the stream.

## Template authoring

Templates are `.rptdesign` XML files created in the **Eclipse BIRT
Designer** — a free desktop tool. The designer lets you:

- Define datasets with SQL queries against the Odoo database
- Bind report parameters (like `object_id`, `company_id`) from the Odoo action
- Drag-and-drop charts, crosstabs, grids
- Preview with real data straight from PostgreSQL

Upload the `.rptdesign` into the Odoo report action and you're done.

## HTTP template mode

Instead of keeping the template on the BIRT server filesystem, Odoo
serves the template via HTTP. The BIRT engine fetches it whenever a
render is requested — which means:

- **Zero sync issues** — update the template in Odoo, next render picks it up.
- **Multi-tenant** — a single BIRT engine can serve templates from many Odoo databases.
- **Access control** — the URL carries an Odoo token; unauthorized fetches fail.

## JDBC configuration

JDBC connection strings can be set globally or per-company. Each report
template pulls the relevant string from Odoo settings at render time, so
multi-company setups Just Work.

## Supported output formats

| MIME type | Extension |
|---|---|
| `application/pdf` | `.pdf` |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | `.docx` |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `.xlsx` |
| `text/html` | `.html` |

## Dependencies

- [`dub_reporting_base`](../dub_reporting_base)
- Python: `requests`, `lxml`
- External: an Eclipse BIRT engine reachable over HTTP

## Development & tests

```bash
odoo -c odoo.conf -d test_db --test-tags /dub_reporting_birt \
     --stop-after-init --http-port=0
```

## Support

- **Website:** [dubhe.it](https://dubhe.it)
- **Email:** [support@dubhe.it](mailto:support@dubhe.it)
- **Issues:** [github.com/dubheit/dub_reporting_tools/issues](https://github.com/dubheit/dub_reporting_tools/issues)

## License

LGPL-3. Copyright © 2025 Dubhe Srls.
