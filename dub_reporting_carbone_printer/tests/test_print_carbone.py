import re
from unittest import mock
from unittest.mock import MagicMock

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

CARBONE_MODULE = "odoo.addons.dub_reporting_carbone.models.ir_actions_report"
PRINTER_PRINT = (
    "odoo.addons.base_report_to_printer.models.printing_printer."
    "PrintingPrinter.print_document"
)


def _mock_carbone_post(url, **kwargs):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    if "/template" in url and "/render/" not in url:
        resp.json.return_value = {
            "success": True,
            "data": {"templateId": "mock_template_id_abc123"},
        }
    elif "/render/" in url:
        resp.json.return_value = {
            "success": True,
            "data": {"renderId": "mock_render_id_xyz789.pdf"},
        }
    return resp


def _mock_carbone_get(url, **kwargs):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    if "/render/" in url:
        resp.content = b"%PDF-1.4 mock pdf content for testing"
    return resp


@tagged("post_install", "-at_install")
class TestPrintCarbone(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({"name": "Label Partner"})
        self.report = self.env["ir.actions.report"].create(
            {
                "name": "Test Carbone Label",
                "model": "res.partner",
                "report_type": "carbone",
                "report_name": "dub_reporting_carbone_printer.test_label",
                "carbone_report_type": "pdf",
            }
        )
        server = self.env["printing.server"].create({})
        self.printer = self.env["printing.printer"].create(
            {
                "name": "Printer",
                "server_id": server.id,
                "system_name": "Sys Name",
                "status": "unknown",
                "default": False,
            }
        )
        self.report.printing_printer_id = self.printer
        self.report = self.report.with_context(skip_printer_exception=True)

        self._real_render_carbone = type(self.env["ir.actions.report"])._render_carbone
        patcher = mock.patch.object(
            type(self.env["ir.actions.report"]),
            "_render_carbone",
            return_value=(b"%PDF-1.4 label", "pdf"),
        )
        self.render = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch(PRINTER_PRINT)
        self.print_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def test_print_carbone_sends_pdf(self):
        self.report.print_document([self.partner.id])
        self.render.assert_called_once_with(
            "dub_reporting_carbone_printer.test_label", [self.partner.id], {}
        )
        self.print_mock.assert_called_once()
        args, kwargs = self.print_mock.call_args
        self.assertEqual(args, (self.report, b"%PDF-1.4 label"))
        self.assertEqual(kwargs["doc_format"], "carbone")
        self.assertEqual(kwargs["res_ids"], [self.partner.id])

    def test_print_carbone_title_from_print_report_name(self):
        self.report.print_report_name = "'Label %s' % object.name"
        self.report.print_document([self.partner.id])
        self.assertEqual(
            self.print_mock.call_args.kwargs["title"], "Label Label Partner"
        )

    def test_print_carbone_title_fallback_on_bad_expression(self):
        self.report.print_report_name = "object.missing_field.x"
        self.report.print_document([self.partner.id])
        self.assertEqual(
            self.print_mock.call_args.kwargs["title"], self.report.report_name
        )

    def test_print_carbone_renders_with_skip_context(self):
        seen = {}

        def _render(rep, *args, **kwargs):
            seen["skip"] = rep.env.context.get("must_skip_send_to_printer")
            return b"%PDF-1.4 label", "pdf"

        with mock.patch.object(
            type(self.env["ir.actions.report"]), "_render_carbone", _render
        ):
            self.report.print_document([self.partner.id])
        self.assertTrue(seen["skip"])

    def test_print_carbone_keeps_duplicate_ids(self):
        pid = self.partner.id
        self.report.print_document([pid, pid])
        self.render.assert_called_once_with(
            "dub_reporting_carbone_printer.test_label", [pid, pid], {}
        )

    def test_print_carbone_no_printer(self):
        self.report.printing_printer_id = False
        self.env.user.printing_printer_id = False
        self.assertFalse(self.env["printing.printer"].get_default())
        with self.assertRaises(UserError):
            self.report.print_document([self.partner.id])
        self.render.assert_not_called()
        self.print_mock.assert_not_called()

    def test_print_carbone_not_pdf(self):
        self.report.carbone_report_type = "docx"
        with self.assertRaisesRegex(UserError, "Test Carbone Label"):
            self.report.print_document([self.partner.id])
        self.render.assert_not_called()
        result = self.report.print_document_client_action([self.partner.id])
        self.assertTrue(result["download"])
        self.assertIn("Test Carbone Label", result["message"])
        self.print_mock.assert_not_called()

    def test_print_carbone_async(self):
        self.report.carbone_rendering_mode = "async"
        with self.assertRaisesRegex(UserError, "Test Carbone Label"):
            self.report.print_document([self.partner.id])
        self.render.assert_not_called()

    def test_print_carbone_zip_batch(self):
        self.report.carbone_batch_output = "zip"
        other = self.env["res.partner"].create({"name": "Other"})
        with self.assertRaisesRegex(UserError, "Test Carbone Label"):
            self.report.print_document([self.partner.id, other.id])
        self.render.assert_not_called()
        self.report.print_document([self.partner.id])
        self.print_mock.assert_called_once()

    def test_print_carbone_without_records(self):
        report = self.report.with_context(lang="en_US")
        message = "Nothing to print: no records selected."
        with self.assertRaisesRegex(UserError, message):
            report.print_document([])
        self.render.assert_not_called()
        result = report.print_document_client_action([])
        self.assertEqual(result, {"download": True, "message": message})
        self.print_mock.assert_not_called()

    def test_client_action_printable_reaches_super(self):
        self.printer.multi_thread = False
        result = self.report.print_document_client_action([self.partner.id])
        self.assertNotIsInstance(result, dict)
        self.print_mock.assert_called_once()

    def test_render_carbone_never_prints(self):
        self.report.write(
            {
                "carbone_use_html_template": True,
                "carbone_html_template": "<p>{d.name}</p>",
                "carbone_json_data": "{'name': object.name}",
            }
        )
        company = self.env.company
        company.write(
            {
                "carbone_api_url": "https://api.carbone.io",
                "carbone_access_token": "test_token",
            }
        )
        self.report.property_printing_action_id = self.env["printing.action"].create(
            {"name": "Server", "action_type": "server"}
        )
        # Use the real renderer: undo the class-level patch for this test
        real = self._real_render_carbone
        with mock.patch.object(
            type(self.env["ir.actions.report"]), "_render_carbone", real
        ), mock.patch(
            CARBONE_MODULE + ".requests.post", side_effect=_mock_carbone_post
        ) as post, mock.patch(
            CARBONE_MODULE + ".requests.get", side_effect=_mock_carbone_get
        ) as get:
            self.report._render_carbone(
                self.report.report_name, [self.partner.id], {}
            )
        post.assert_called()
        get.assert_called()
        self.print_mock.assert_not_called()

    def test_other_report_types_untouched(self):
        qweb = self.env["ir.actions.report"].create(
            {
                "name": "Test QWeb",
                "model": "res.partner",
                "report_type": "qweb-pdf",
                "report_name": "dub_reporting_carbone_printer.test_qweb",
            }
        )
        qweb.printing_printer_id = self.printer
        qweb = qweb.with_context(skip_printer_exception=True)
        with mock.patch.object(
            type(self.env["ir.actions.report"]),
            "_render_qweb_pdf",
            return_value=(b"%PDF qweb", "pdf"),
        ):
            qweb.print_document([self.partner.id])
        self.print_mock.assert_called_once()
        self.render.assert_not_called()
