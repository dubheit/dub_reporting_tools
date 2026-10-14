from odoo import api, models
from odoo.models import MAGIC_COLUMNS


class BirtReportWizardMixin(models.AbstractModel):
    """Show a BIRT report rendered from a wizard in an on-screen viewer.

    The viewer opens in the report's ``birt_report_type`` (HTML preview or
    PDF), lets the user switch format and reopen the wizard to change the
    parameters. Inheriting wizards implement ``_get_birt_report`` and
    ``_get_birt_params`` and return ``action_birt_view()`` from their print
    button.
    """

    _name = "dub.birt.report.wizard.mixin"
    _description = "BIRT Report Wizard Viewer Mixin"

    def _get_birt_report(self):
        """Return the ``ir.actions.report`` record to render."""
        raise NotImplementedError()

    def _get_birt_params(self):
        """Return the BIRT report parameters as a flat dict."""
        return {}

    def _get_birt_filename(self, fmt):
        self.ensure_one()
        return f"{self._get_birt_report().name}.{fmt}"

    def _birt_viewer_render(self, fmt):
        self.ensure_one()
        report = self._get_birt_report()
        return self.env["ir.actions.report"]._render_birt(
            report,
            [self.id],
            data={"data": self._get_birt_params()},
            output_format=fmt,
        )

    def action_birt_view(self):
        self.ensure_one()
        report = self._get_birt_report()
        # Reopened from a viewer: keep the format the user switched to
        fmt = self.env.context.get("birt_viewer_format")
        return {
            "type": "ir.actions.client",
            "tag": "dub_reporting_birt.viewer",
            "name": report.name,
            "params": {
                "name": report.name,
                "model": self._name,
                "res_id": self.id,
                # Wizards are transient: keep the values to rebuild the
                # record if the vacuum removes it while the viewer is open.
                "values": self.copy_data()[0],
                "format": fmt or report.birt_report_type or "pdf",
                "replace": bool(self.env.context.get("birt_viewer_replace")),
            },
        }

    @api.model
    def birt_viewer_ensure(self, res_id, values):
        """Return the id of the wizard behind a viewer, recreating it from
        ``values`` when it no longer exists."""
        wizard = self.browse(res_id).exists()
        if wizard and wizard.create_uid == self.env.user:
            return wizard.id
        values = {
            key: value
            for key, value in (values or {}).items()
            if key in self._fields and key not in MAGIC_COLUMNS
        }
        return self.create(values).id

    def action_birt_reopen(self, fmt=None):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self._get_birt_report().name,
            "res_model": self._name,
            "res_id": self.id,
            "views": [(False, "form")],
            "target": "new",
            "context": {
                "birt_viewer_replace": True,
                "birt_viewer_format": fmt if fmt in ("pdf", "html") else False,
            },
        }
