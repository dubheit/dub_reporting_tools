# Reporting Tools — Carbone Direct Printing

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo](https://img.shields.io/badge/Odoo-18.0-875A7B.svg)](https://www.odoo.com/)

Bridge module between `dub_reporting_carbone` and the OCA
[`base_report_to_printer`](https://github.com/OCA/report-print-send): Carbone
reports can be sent straight to a CUPS printer, as QWeb reports already can.

## Installation

The module is `auto_install`: it is installed automatically as soon as both
`dub_reporting_carbone` and `base_report_to_printer` are installed. The OCA
module needs `pycups`. `libcups2-dev` and `python3-dev` are needed only to
build `pycups` from source.

## Configuration

Nothing to configure in this module. Use the `base_report_to_printer` settings:

- **Printer**: set it per report (Settings > Technical > Reports) or per user
  (user preferences).
- **Action**: set the report action to "Send to Printer" (per report or per
  user). With any other action the report is downloaded as usual.

Set the printer per report or per user rather than marking a printer as the
global default: when a printer is resolved, `base_report_to_printer` checks
the CUPS connection on every report action, even when the action then
downloads the file.

## Limits / behaviour

- Only **PDF**, **synchronous** Carbone reports can be printed. Asynchronous
  reports, other output formats and the ZIP produced for several records are
  not sent to a printer: the report is downloaded as usual, with a notice
  explaining why.
- Report actions without records (`active_ids` empty, e.g. wizard reports
  driven only by `data`) are never sent to a printer; they download as before.
- Server-side renders (mail attachments, previews) never print.
- If CUPS or the render fails, the web client shows the printer warning with a
  **Print** button that downloads the report.
- With multi-thread printers the job runs after the request: success is
  reported before the job runs and a later failure is not shown.
- The handler is registered in the `ir.actions.report handlers` registry with
  sequence 5. Any other handler that redirects or substitutes report actions
  must register with a sequence below 5 to run first.

## License

LGPL-3
