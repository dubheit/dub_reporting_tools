import logging
from odoo import models, api, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    """Base report model with common functionality for external reporting engines."""

    _inherit = 'ir.actions.report'

    report_overlay = fields.Text(
        string="PDF Column Overlay",
        help="JSON config to draw crisp vector column rules over the rendered "
             "PDF on every page (engine-agnostic). Lets a borderless body table "
             "with dynamic row heights show full-height column separators down "
             "to the footer. Format: "
             '{"x_mm": [..], "top_mm": <float>, "bottom_mm": <float>, '
             '"line_pt": <float>, "close_line": <bool>}',
    )

    def _apply_report_overlay(self, pdf_bytes):
        """Draw crisp vector column rules over a rendered PDF.

        Engine-agnostic: the body table is laid out with dynamic row heights and
        no borders; the column separators are drawn here as real vector lines
        spanning the full body height on every page, so the columns reach the
        footer regardless of how many rows there are. Coordinates come from the
        report's ``report_overlay`` JSON. A single overlay page is built once and
        merged onto every page (all pages share the same body geometry)."""
        self.ensure_one()
        import json
        from io import BytesIO
        if not self.report_overlay:
            return pdf_bytes
        try:
            cfg = json.loads(self.report_overlay)
        except (ValueError, TypeError):
            _logger.warning("Invalid report_overlay JSON on report %s", self.report_name)
            return pdf_bytes
        xs = cfg.get('x_mm') or []
        if not xs:
            return pdf_bytes
        try:
            from reportlab.pdfgen import canvas
            from PyPDF2 import PdfReader, PdfWriter
        except ImportError:
            _logger.warning("reportlab/PyPDF2 missing: skipping report overlay")
            return pdf_bytes

        mm = 72.0 / 25.4
        top = float(cfg.get('top_mm', 0.0))
        bottom = float(cfg.get('bottom_mm', 0.0))
        line_pt = float(cfg.get('line_pt', 0.5))
        close = bool(cfg.get('close_line', False))

        reader = PdfReader(BytesIO(pdf_bytes))
        pw = float(reader.pages[0].mediabox.width)
        ph = float(reader.pages[0].mediabox.height)

        # build the overlay once (same geometry on every page)
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(pw, ph))
        c.setLineWidth(line_pt)
        for x in xs:
            xp = x * mm
            c.line(xp, ph - top * mm, xp, ph - bottom * mm)
        if close and len(xs) >= 2:
            c.line(xs[0] * mm, ph - bottom * mm, xs[-1] * mm, ph - bottom * mm)
        # optional horizontal rules (e.g. the grey header frame), spanning the
        # full column block, so the whole table frame is drawn by one engine and
        # the corners join cleanly (no table-vs-overlay sub-pixel mismatch)
        for hy in (cfg.get('h_mm') or []):
            c.line(xs[0] * mm, ph - float(hy) * mm, xs[-1] * mm, ph - float(hy) * mm)
        c.save()
        buf.seek(0)
        overlay_page = PdfReader(buf).pages[0]

        writer = PdfWriter()
        for page in reader.pages:
            page.merge_page(overlay_page)
            writer.add_page(page)
        out = BytesIO()
        writer.write(out)
        return out.getvalue()

    @api.model
    def _render_report_engine(self, engine_type, report_ref, docids, data=None):
        """Abstract method for engine routing.
        
        This method should be overridden by specific engine modules to implement
        their rendering logic.
        
        Args:
            engine_type (str): The report engine type (e.g., 'carbone', 'birt')
            report_ref (str): Report reference (name or id)
            docids (list): List of document IDs to render
            data (dict): Additional data for rendering
            
        Returns:
            tuple: (report_content, report_format)
            
        Raises:
            UserError: If engine type is not supported
        """
        _logger.error(
            f"Rendering engine '{engine_type}' not implemented. "
            f"Report: {report_ref}, docids: {docids}"
        )
        raise UserError(_(
            "The reporting engine '%s' is not supported. "
            "Please install the corresponding module."
        ) % engine_type)

    def _validate_report_config(self):
        """Validate report configuration before rendering.
        
        This method checks for common issues like missing configuration,
        invalid settings, etc.
        
        Returns:
            bool: True if configuration is valid
            
        Raises:
            UserError: If configuration is invalid
        """
        self.ensure_one()
        
        if not self.report_type:
            raise UserError(_("Report type is not defined for '%s'.") % self.name)
        
        if not self.model:
            raise UserError(_("Report model is not defined for '%s'.") % self.name)
        
        _logger.debug(f"Report configuration validated for {self.name}")
        return True

    @api.model
    def _prepare_report_data(self, docids, data=None):
        """Prepare data for report rendering.
        
        This method prepares the data dictionary that will be passed to the
        reporting engine. It can be overridden by specific engines to add
        custom data preparation logic.
        
        Args:
            docids (list): List of document IDs
            data (dict): Additional data
            
        Returns:
            dict: Prepared data dictionary
        """
        if data is None:
            data = {}
        
        # Add common context information
        data.update({
            'doc_ids': docids,
            'doc_model': data.get('model'),
            'lang': self.env.context.get('lang') or self.env.user.lang,
            'tz': self.env.context.get('tz') or self.env.user.tz or 'UTC',
        })
        
        _logger.debug(f"Report data prepared: {len(docids)} documents")
        return data

    @api.model
    def _handle_render_error(self, error, report_name, engine_type):
        """Handle rendering errors with standardized error messages.
        
        Args:
            error (Exception): The exception that occurred
            report_name (str): Name of the report
            engine_type (str): Type of reporting engine
            
        Raises:
            UserError: With user-friendly error message
        """
        error_msg = str(error)
        _logger.error(
            f"Report rendering failed for '{report_name}' using {engine_type} engine: {error_msg}",
            exc_info=True
        )
        
        raise UserError(_(
            "Failed to generate report '%(report)s'.\n\n"
            "Engine: %(engine)s\n"
            "Error: %(error)s\n\n"
            "Please contact your administrator if the problem persists."
        ) % {
            'report': report_name,
            'engine': engine_type,
            'error': error_msg
        })

    def _log_report_request(self, docids, success=True):
        """Log report generation requests.
        
        Args:
            docids (list): List of document IDs
            success (bool): Whether the report was generated successfully
        """
        self.ensure_one()
        
        status = "SUCCESS" if success else "FAILED"
        _logger.info(
            f"Report '{self.name}' ({self.report_type}) {status}: "
            f"{len(docids)} document(s), user: {self.env.user.name}"
        )

    def _get_report_from_name(self, report_name):
        """Override to support custom engine types.
        
        This method is called by Odoo to find the report by name.
        Extended to support detection of custom report types.
        
        Args:
            report_name (str): Report name
            
        Returns:
            ir.actions.report: Report record
        """
        res = super()._get_report_from_name(report_name)
        if res:
            _logger.debug(f"Report found: {report_name} (type: {res.report_type})")
        return res
