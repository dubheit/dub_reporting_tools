# Reporting Base

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-18.0-875A7B.svg)](https://www.odoo.com/)
[![CI](https://github.com/dubheit/dub_reporting_tools/actions/workflows/test.yml/badge.svg?branch=18.0)](https://github.com/dubheit/dub_reporting_tools/actions)

The foundation module for the **Dubhe Reporting Tools** suite — a plugin
architecture that lets Odoo delegate report rendering to external engines
like Carbone, BIRT, iLovePDF and future additions.

---

## Table of Contents

- [Why this module](#why-this-module)
- [How it fits in](#how-it-fits-in)
- [Features](#features)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Extending the framework](#extending-the-framework)
- [Dependencies](#dependencies)
- [Development & tests](#development--tests)
- [Support](#support)
- [License](#license)

---

## Why this module

Odoo's native QWeb reports are great for simple layouts, but break down when
you need pixel-perfect Word/Excel templates, enterprise-grade PDF processing,
or advanced data-driven reporting engines.

`dub_reporting_base` introduces a **clean plugin interface** that lets any
number of external reporting engines coexist inside the same Odoo instance
without stepping on each other's toes. Install the engines you need — skip
the ones you don't.

## How it fits in

```text
                 ┌──────────────────────────────────────────────┐
                 │                    ODOO                       │
                 │                                              │
                 │     ir.actions.report   ←── user picks one   │
                 │           │                                  │
                 │           ▼                                  │
                 │   ┌──────────────────┐                       │
                 │   │ dub_reporting_   │  dispatch by engine   │
                 │   │ base             │──────┬────────────┐   │
                 │   └──────────────────┘      │            │   │
                 │           │                 ▼            ▼   │
                 │           ▼         ┌──────────┐  ┌──────────┐
                 │   ┌──────────────┐  │ carbone  │  │ birt     │
                 │   │ qweb-pdf,    │  └──────────┘  └──────────┘
                 │   │ qweb-html    │  ┌──────────┐  ┌──────────┐
                 │   │ (Odoo core)  │  │ ilovepdf │  │  …       │
                 │   └──────────────┘  └──────────┘  └──────────┘
                 └──────────────────────────────────────────────┘
```

Each specific engine module (`dub_reporting_carbone`, `dub_reporting_birt`,
`dub_reporting_ilovepdf`, ...) extends the base to register its own engine
type on `ir.actions.report.report_type`.

## Features

- **Engine routing** — extensible `_render()` dispatcher on `ir.actions.report`
- **Common utilities** — template validation, MIME detection, error wrapping, structured logging
- **Backend JavaScript framework** — shared report-action handler for all engines
- **Settings page** — unified `Settings → Technical → Reporting` section where each engine plugs its own config panel
- **Pre-init hook** — adds engine-neutral schema columns safely on install
- **No external runtime dependency** — just `base` and `web`

## Architecture

The module extends four Odoo objects:

| Object | Extension |
|---|---|
| `ir.actions.report` | Registers extension points for new engine types and dispatches rendering |
| `res.company` | Holds per-company defaults that sub-modules can extend |
| `res.config.settings` | Provides the "Reporting" section where engines plug their panels |
| `web.assets_backend` | Loads a shared JS helper used by all engines |

Engine modules only need to:

1. Add their engine key to `report_type` selection.
2. Implement `_render_<engine>(res_ids, data)` on `ir.actions.report`.
3. Register their UI and settings as usual.

## Configuration

There is nothing to configure for this base module — it is a dependency.
The **Settings → Technical → Reporting** section will appear only once an
engine module is installed.

## Extending the framework

Minimal skeleton for a new engine `dub_reporting_foo`:

```python
# models/ir_actions_report.py
from odoo import api, fields, models

class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    report_type = fields.Selection(
        selection_add=[("foo", "Foo Engine")],
        ondelete={"foo": "cascade"},
    )

    def _render_foo(self, res_ids, data=None):
        # Produce (bytes, mime_type) tuple
        return self._foo_produce(res_ids, data), "application/pdf"
```

Add it to `depends: ["dub_reporting_base"]` and you're done.

## Dependencies

- `base` — Odoo core
- `web` — for the JS client framework

No external Python or system dependencies.

## Development & tests

```bash
odoo -c odoo.conf -d test_db --test-tags /dub_reporting_base \
     --stop-after-init --http-port=0
```

CI runs on every push via GitHub Actions against PostgreSQL 16 and
Python 3.12.

## Support

- **Website:** [dubhe.it](https://dubhe.it)
- **Email:** [support@dubhe.it](mailto:support@dubhe.it)
- **Issues:** [github.com/dubheit/dub_reporting_tools/issues](https://github.com/dubheit/dub_reporting_tools/issues)

## License

LGPL-3. See [`LICENSE`](./LICENSE) for the full text.

Copyright © 2025 Dubhe Srls.
