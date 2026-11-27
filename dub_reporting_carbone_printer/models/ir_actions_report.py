import logging

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval, time

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _dub_check_carbone_printable(self, record_ids):
        """Raise a UserError when this Carbone report cannot go to a printer."""
        self.ensure_one()
        if not record_ids:
            raise UserError(_("Nothing to print: no records selected."))
        if (self.carbone_report_type or "pdf") != "pdf":
            raise UserError(
                _(
                    "Only PDF Carbone reports can be sent to a printer "
                    "(report %(name)s produces %(format)s).",
                    name=self.name,
                    format=(self.carbone_report_type or "").upper(),
                )
            )
        if self.carbone_rendering_mode == "async":
            raise UserError(
                _(
                    "Asynchronous Carbone reports cannot be sent to a printer "
                    "(report %(name)s).",
                    name=self.name,
                )
            )
        if len(record_ids) > 1 and self.carbone_batch_output == "zip":
            raise UserError(
                _(
                    "Report %(name)s produces a ZIP for several records "
                    "and cannot be sent to a printer.",
                    name=self.name,
                )
            )

    def print_document_client_action(self, record_ids, data=None):
        if self.report_type == "carbone":
            self.ensure_one()
            try:
                self._dub_check_carbone_printable(record_ids)
            except UserError as e:
                # The base implementation swallows every error (or prints in a
                # thread): tell the client to download instead of a printer
                # failure.
                return {"download": True, "message": str(e)}
        return super().print_document_client_action(record_ids, data=data)

    def print_document(self, record_ids, data=None):
        if self.report_type != "carbone":
            return super().print_document(record_ids, data=data)
        self.ensure_one()
        self._dub_check_carbone_printable(record_ids)
        # Resolve the printer before rendering so that a missing printer
        # never triggers a call to the Carbone API.
        behaviour = self.behaviour()
        printer = behaviour.pop("printer", None)
        if not printer:
            raise UserError(_("No printer configured to print this report."))
        document, __ = self.with_context(
            must_skip_send_to_printer=True
        )._render_carbone(self.report_name, list(record_ids), data or {})
        # Duplicated from the base printing module on purpose: reusing it would
        # require mutating its process-wide REPORT_TYPES dict.
        title = self._dub_carbone_print_title(record_ids)
        behaviour["title"] = title
        behaviour["res_ids"] = record_ids
        return printer.print_document(
            self, document, doc_format="carbone", **behaviour
        )

    def _dub_carbone_print_title(self, record_ids):
        """Return the print job title (same rules as the base printing module)."""
        if self.print_report_name:
            try:
                names = [
                    safe_eval(self.print_report_name, {"object": obj, "time": time})
                    for obj in self.env[self.model].browse(record_ids)
                ]
            except Exception:
                _logger.warning(
                    "Cannot evaluate print_report_name of report %s",
                    self.report_name,
                    exc_info=True,
                )
                return self.report_name
            title = " ".join(names)
            if len(title) > 80:
                title = title[:80] + "…"
            return title
        return self.report_name
