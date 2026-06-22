import base64
import logging
from io import BytesIO
from urllib.parse import urljoin

import requests
from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    report_type = fields.Selection(
        selection_add=[('birt', "BIRT")],
        ondelete={'birt': 'set default'},
    )
    birt_template_file = fields.Binary(
        string="BIRT Template (.rptdesign)",
    )
    birt_template_filename = fields.Char(
        string="Template Filename",
    )
    birt_json_data = fields.Text(
        string="BIRT Data Method",
        help="Python expression evaluated on each printed record to build "
             "extra BIRT scalar parameters, e.g. 'object.birt_report_data()'. "
             "It must return a flat dict {param_name: value}; values are sent "
             "as report parameters (available in params[] anywhere, including "
             "the master page header/footer). Repeating detail rows should "
             "still be fetched by the template via JDBC.",
    )
    birt_overlay = fields.Text(
        string="BIRT Vector Overlay",
        help="Optional JSON describing vertical column rules drawn as crisp "
             "vector lines on top of the rendered PDF (every page). Lets the "
             "body table use fully dynamic row heights while the column "
             "separators still span the full body height. Schema: "
             '{"x_mm": [..], "top_mm": <float>, "bottom_mm": <float>, '
             '"line_pt": <float>, "close_line": <bool>}. Coordinates are in '
             "millimetres from the page top-left.",
    )
    birt_report_type = fields.Selection(
        [('pdf', 'PDF')],
        string="Output Format",
        default='pdf',
    )
    birt_format_version = fields.Char(
        string="BIRT Format Version",
    )
    birt_jdbc_string = fields.Char(
        string="JDBC Connection String",
    )
    birt_template_mode = fields.Selection(
        [('http', 'HTTP'), ('filesystem', 'Filesystem')],
        string="Template Mode",
        default='http',
        help="How the template is provided to the BIRT server.\n"
             "HTTP: Odoo serves the template via URL (requires "
             "URL_REPORT_PATH_POLICY=domain in BIRT web.xml).\n"
             "Filesystem: The template must exist on BIRT server's "
             "filesystem (reports folder).",
    )
    birt_endpoint = fields.Selection(
        [('run', 'Viewer (/run)'), ('run2phase', 'Two-phase (/run2phase)')],
        string="Render Endpoint",
        default='run',
        help="Viewer /run uses a combined run-and-render task: page "
             "variables shown in the master page are shifted by one "
             "page. The custom /run2phase servlet renders in two "
             "phases (run -> report document -> render) so page-level "
             "rolling totals in the page footer are exact. Required "
             "for fiscal prints with per-page totals (libro giornale, "
             "libro inventari).",
    )
    birt_db_host = fields.Char(
        string="DB Host",
        help="PostgreSQL host as seen from the BIRT server. Overrides the "
             "company-level value for this report only. Sent to BIRT as "
             "report parameter at render time; the template must use "
             "property bindings reading the db_* parameters. Leave empty "
             "to use the company default.",
    )
    birt_db_port = fields.Char(string="DB Port")
    birt_db_name = fields.Char(string="DB Name")
    birt_db_user = fields.Char(string="DB User")
    birt_db_password = fields.Char(string="DB Password")

    def _check_birt_config(self):
        """Validate BIRT report configuration before rendering."""
        self.ensure_one()
        company = self.env.company
        if not company.birt_base_url:
            raise UserError(_(
                "BIRT server URL is not configured.\n"
                "Go to Settings > Reporting Tools to set the BIRT Base URL."
            ))
        if self.birt_template_mode == 'http' and not self.birt_template_file:
            raise UserError(_(
                "No BIRT template uploaded for report '%s'.\n"
                "Upload a .rptdesign file or switch to filesystem mode."
            ) % self.name)

    def _get_birt_template_url(self):
        """Build the URL from which BIRT can fetch the template via HTTP.

        The controller at /report/birt/template/<report_name> serves the
        binary content of the uploaded .rptdesign file.  The URL uses the
        internal Docker hostname ``odoo`` so that the BIRT container can
        reach it
        """
        self.ensure_one()
        base = self.env.company.birt_odoo_internal_url or 'http://odoo:8069'
        url = urljoin(base, '/report/birt/template/' + self.report_name)
        # Cache-buster: BIRT caches the downloaded design by URL, so a
        # modified template would never be re-fetched. Appending the
        # record write timestamp forces a fresh download after updates.
        if self.write_date:
            url += '?v=' + self.write_date.strftime('%Y%m%d%H%M%S')
        return url

    def _get_birt_db_params(self):
        """Build the DB connection parameters sent to BIRT at render time.

        Fallback chain per field: report value, then company value. Only
        non-empty values are sent: when a parameter is missing the template
        property bindings fall back to the BIRT server's own JVM system
        properties (-DDB_HOST etc.).
        """
        self.ensure_one()
        company = self.env.company
        params = {}
        for field in ('db_host', 'db_port', 'db_name', 'db_user',
                      'db_password'):
            value = self['birt_' + field] or company['birt_' + field]
            if value:
                params[field] = value
        return params

    def _render_birt(self, report_ref, docids, data=None):
        """Render a BIRT report.

        Args:
            report_ref: Report reference (name or xmlid).
            docids: Comma-separated document IDs or list.
            data: Extra parameters forwarded to the BIRT engine.

        Returns:
            tuple: (content_bytes, output_format)
        """
        report = self._get_report(report_ref)
        report._check_birt_config()
        company = self.env.company

        if report.birt_template_mode == 'http':
            report_path = report._get_birt_template_url()
        else:
            report_path = report.report_name
            if not report_path.endswith('.rptdesign'):
                report_path += '.rptdesign'

        params = dict(data or {})
        # Convention used by the calling wizards: the BIRT report
        # parameters are nested under the 'data' key (mirroring the
        # QWeb report API). Flatten them, otherwise requests would
        # serialize the dict as its keys and BIRT would silently
        # fall back to the template default parameter values.
        nested = params.pop('data', None)
        if isinstance(nested, dict):
            params.update(nested)
        if isinstance(docids, (list, tuple)):
            params['ids'] = ','.join(str(i) for i in docids)
        elif docids:
            params['ids'] = str(docids)

        # Data method: evaluate birt_json_data on the (first) printed record to
        # build extra scalar parameters. Unlike dataset rows, parameters are
        # known before the run and are therefore readable in the master page
        # header/footer (which a two-phase render cannot reach via dataset).
        if report.birt_json_data and params.get('ids'):
            ids = [int(i) for i in str(params['ids']).split(',') if i]
            records = self.env[report.model].browse(ids) if report.model else None
            if records:
                try:
                    extra = safe_eval(
                        report.birt_json_data.replace('\n', ''),
                        {"object": records[:1], "objects": records},
                    )
                except Exception as e:
                    raise UserError(_(
                        "Error evaluating BIRT data method for report "
                        "'%(name)s':\n%(err)s", name=report.name, err=e)) from e
                if isinstance(extra, dict):
                    for key, value in extra.items():
                        params[key] = '' if value is None else str(value)

        # DB connection forwarded as report parameters (report -> company
        # fallback). Templates with property bindings on the db_* params
        # use them; unset values fall back to the BIRT server JVM
        # system properties.
        params.update(report._get_birt_db_params())

        output_format = report.birt_report_type or 'pdf'
        _logger.info(
            "BIRT render: report=%s format=%s mode=%s",
            report.report_name, output_format, report.birt_template_mode,
        )

        url = urljoin(
            company.birt_base_url + '/',
            report.birt_endpoint or 'run',
        )
        params['__report'] = report_path
        params['__format'] = output_format

        try:
            # POST keeps the DB credentials out of the query string
            # (and therefore out of Tomcat/proxy access logs).
            resp = requests.post(url, data=params, timeout=120)
            resp.raise_for_status()
        except requests.RequestException as e:
            msg = getattr(e.response, 'text', 'No details') if hasattr(e, 'response') else str(e)
            raise UserError(_(
                "BIRT server error (HTTP %(code)s):\n%(msg)s",
                code=getattr(getattr(e, 'response', None), 'status_code', 'birt'),
                msg=msg,
            )) from e

        content = resp.content
        if output_format == 'pdf' and report.birt_overlay:
            content = report._apply_birt_overlay(content)

        return content, output_format

    def _apply_birt_overlay(self, pdf_bytes):
        """Draw crisp vector column rules over a rendered BIRT PDF.

        The body table is laid out by BIRT with dynamic row heights and no
        borders; the column separators are drawn here as real vector lines
        spanning the full body height on every page, so the columns reach the
        footer regardless of how many rows there are. Coordinates come from the
        report's ``birt_overlay`` JSON. A single overlay page is built once and
        merged onto every page (all pages share the same body geometry)."""
        self.ensure_one()
        import json
        from io import BytesIO as _BytesIO
        try:
            cfg = json.loads(self.birt_overlay)
        except (ValueError, TypeError):
            _logger.warning("Invalid birt_overlay JSON on report %s", self.report_name)
            return pdf_bytes
        xs = cfg.get('x_mm') or []
        if not xs:
            return pdf_bytes
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from PyPDF2 import PdfReader, PdfWriter
        except ImportError:
            _logger.warning("reportlab/PyPDF2 missing: skipping BIRT overlay")
            return pdf_bytes

        mm = 72.0 / 25.4
        top = float(cfg.get('top_mm', 0.0))
        bottom = float(cfg.get('bottom_mm', 0.0))
        line_pt = float(cfg.get('line_pt', 0.5))
        close = bool(cfg.get('close_line', False))

        reader = PdfReader(_BytesIO(pdf_bytes))
        pw = float(reader.pages[0].mediabox.width)
        ph = float(reader.pages[0].mediabox.height)

        # build the overlay once (same geometry on every page)
        buf = _BytesIO()
        c = canvas.Canvas(buf, pagesize=(pw, ph))
        c.setLineWidth(line_pt)
        for x in xs:
            xp = x * mm
            c.line(xp, ph - top * mm, xp, ph - bottom * mm)
        if close and len(xs) >= 2:
            c.line(xs[0] * mm, ph - bottom * mm, xs[-1] * mm, ph - bottom * mm)
        c.save()
        buf.seek(0)
        overlay_page = PdfReader(buf).pages[0]

        writer = PdfWriter()
        for page in reader.pages:
            page.merge_page(overlay_page)
            writer.add_page(page)
        out = _BytesIO()
        writer.write(out)
        return out.getvalue()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.birt_template_file:
                record._update_birt_template_metadata()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in (
            'birt_template_file', 'birt_format_version', 'birt_jdbc_string',
        )):
            for record in self:
                if record.birt_template_file:
                    record._update_birt_template_metadata()
        return res

    def _update_birt_template_metadata(self):
        """Update version and JDBC URL inside a .rptdesign XML template."""
        self.ensure_one()
        if not self.birt_template_file:
            return
        try:
            content = base64.b64decode(self.birt_template_file)
            tree = etree.parse(BytesIO(content))
            root = tree.getroot()
            changed = False

            if self.birt_format_version:
                report_el = root.find('report')
                if report_el is not None:
                    report_el.set('version', self.birt_format_version)
                    changed = True

            if self.birt_jdbc_string:
                for elem in root.iter():
                    if elem.tag == 'property' and elem.get('name') == 'odaURL':
                        elem.text = self.birt_jdbc_string
                        changed = True

            if changed:
                new_content = etree.tostring(tree, encoding='UTF-8', xml_declaration=True)
                super(IrActionsReport, self).write({
                    'birt_template_file': base64.b64encode(new_content),
                })
        except Exception as e:
            _logger.error("Error updating BIRT template metadata: %s", e)
