import base64
import json
import logging
import mimetypes

from odoo import http
from odoo.http import content_disposition, request
from odoo.addons.dub_reporting_base.controllers.report import BaseReportController
from odoo.tools.safe_eval import safe_eval, time

_logger = logging.getLogger(__name__)


class BirtReportTemplateController(http.Controller):
    """Serve .rptdesign templates to the BIRT server via HTTP.

    When ``birt_template_mode`` is ``http``, the BIRT engine fetches the
    template from this endpoint instead of reading it from the filesystem.
    The route is public so the BIRT container can reach it without a
    session cookie (traffic is internal Docker network only).
    """

    @http.route(
        '/report/birt/template/<path:report_name>',
        type='http',
        auth='public',
    )
    def birt_template(self, report_name, **kwargs):
        report = request.env['ir.actions.report'].sudo().search([
            ('report_name', '=', report_name),
        ], limit=1)
        if not report or not report.birt_template_file:
            report_name_rpt = report_name + '.rptdesign'
            report = request.env['ir.actions.report'].sudo().search([
                ('report_name', '=', report_name_rpt),
            ], limit=1)
        if not report or not report.birt_template_file:
            return request.not_found()
        content = base64.b64decode(report.birt_template_file)
        return request.make_response(
            content,
            headers=[
                ('Content-Disposition', content_disposition(
                    report.birt_template_filename or 'template.rptdesign'
                )),
                ('Content-Length', str(len(content))),
            ],
        )


class BirtReportController(BaseReportController):
    """Controller for BIRT report rendering and download."""

    def _get_report_from_name(self, report_name):
        report = request.env['ir.actions.report'].sudo().search([
            ('report_name', '=', report_name),
            ('report_type', '=', 'birt'),
        ], limit=1)
        return report

    def _birt_filename(self, report, docids, fmt):
        """Build a meaningful download filename from the report's
        print_report_name (evaluated on the printed record), falling back to
        the report display name. Avoids generic names like
        'module.report_name.pdf'."""
        ids = [int(i) for i in (docids or []) if str(i).strip().isdigit()]
        name = report.name or report.report_name
        if report.print_report_name and len(ids) == 1 and report.model:
            try:
                record = request.env[report.model].sudo().browse(ids[0])
                name = safe_eval(
                    report.print_report_name,
                    {'object': record, 'time': time},
                )
            except Exception:
                _logger.warning(
                    "BIRT print_report_name eval failed for %s",
                    report.report_name,
                )
        name = (name or report.report_name).replace('/', '-').replace('\\', '-')
        return '{}.{}'.format(name, fmt)

    @http.route('/report/birt/<path:report_name>', type='http', auth='user')
    def report_birt(self, report_name, docids=None, **kwargs):
        report = self._get_report_from_name(report_name)
        if not report:
            return request.not_found()

        mimetype = mimetypes.guess_type(
            'report.' + (report.birt_report_type or 'pdf')
        )[0] or 'application/octet-stream'

        data = kwargs.get('data') or {}
        if isinstance(data, str):
            data = json.loads(data)

        id_list = docids.split(',') if docids else []
        content, fmt = report._render_birt(
            report.report_name,
            id_list,
            data=data,
        )

        filename = self._birt_filename(report, id_list, fmt)
        return request.make_response(
            content,
            headers=[
                ('Content-Type', mimetype),
                ('Content-Disposition', content_disposition(filename)),
            ],
        )

    @http.route('/report/download', type='http', auth='user')
    def report_download(self, data, context=None, token=None, **kwargs):
        # Handle BIRT reports, delegate others to super
        try:
            requestcontent = json.loads(data)
            url = requestcontent[0]
            if 'birt' not in url and not url.startswith('/report/birt/'):
                return super().report_download(data, context=context, token=token, **kwargs)
        except Exception:
            return super().report_download(data, context=context, token=token, **kwargs)

        try:
            # Parse: /report/birt/report_name/docids
            report_url = url
            if '?' in report_url:
                report_url = report_url.split('?')[0]
            parts = report_url.strip('/').split('/')
            # parts: ['report', 'birt', 'report_name', 'docids']
            report_name = parts[2] if len(parts) > 2 else None
            docids = parts[3] if len(parts) > 3 else None

            options = requestcontent[1] if len(requestcontent) > 1 else {}
            data = options.get('data', {})

            report = self._get_report_from_name(report_name)
            if not report:
                raise UserError("Invalid BIRT report URL: " + url)

            fmt = report.birt_report_type or 'pdf'
            id_list = docids.split(',') if docids else []
            content, _ = report._render_birt(
                report.report_name,
                id_list,
                data=data,
            )

            filename = self._birt_filename(report, id_list, fmt)
            return request.make_response(
                content,
                headers=[
                    ('Content-Type', mimetypes.guess_type(filename)[0] or 'application/octet-stream'),
                    ('Content-Disposition', content_disposition(filename)),
                ],
            )
        except Exception:
            _logger.exception("Error in BIRT report_download")
            raise
