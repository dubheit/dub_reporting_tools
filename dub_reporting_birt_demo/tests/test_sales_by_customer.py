import base64
from datetime import date
from unittest.mock import patch

from lxml import etree

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

NS = {"b": "http://www.eclipse.org/birt/2005/design"}
WIZARD = "dub.birt.demo.sale.customer.wizard"
REPORT = "dub_reporting_birt_demo.action_report_sales_by_customer"


@tagged("post_install", "-at_install")
class TestSalesByCustomer(TransactionCase):
    """The wizard sends the right parameters: the data set query of the
    template runs here on PostgreSQL with them, BIRT is not involved."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create({
            "name": "BIRT Demo Customer",
            "is_company": True,
        })
        cls.contact = cls.env["res.partner"].create({
            "name": "BIRT Demo Contact",
            "parent_id": cls.customer.id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "BIRT Demo Service",
            "type": "service",
            "list_price": 100.0,
        })
        # confirmed by a contact: grouped under its company
        cls.order = cls._create_order(cls.contact, "2025-03-10 10:00:00", confirm=True)
        cls.quotation = cls._create_order(cls.customer, "2025-04-10 10:00:00")
        cls.order_before = cls._create_order(
            cls.customer, "2024-12-31 10:00:00", confirm=True)
        cls.wizard = cls.env[WIZARD].create({
            "company_id": cls.company.id,
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
        })

    @classmethod
    def _create_order(cls, partner, date_order, confirm=False, pricelist=None):
        vals = {
            "partner_id": partner.id,
            "company_id": cls.company.id,
            "order_line": [Command.create({
                "product_id": cls.product.id,
                "product_uom_qty": 2,
            })],
        }
        if pricelist:
            vals["pricelist_id"] = pricelist.id
        order = cls.env["sale.order"].create(vals)
        if confirm:
            order.action_confirm()
        # the confirmation sets the order date to now
        order.date_order = date_order
        return order

    def _report_rows(self, wizard):
        """Run the data set query of the template with the wizard
        parameters, bound by position as BIRT binds them."""
        report = self.env.ref(REPORT)
        design = etree.fromstring(base64.b64decode(report.birt_template_file))
        data_set = design.find(".//b:oda-data-set[@name='Orders']", NS)
        query = data_set.find("b:property[@name='queryText']", NS).text
        bindings = sorted(
            (int(s.find("b:property[@name='position']", NS).text),
             s.find("b:property[@name='paramName']", NS).text)
            for s in data_set.findall("b:list-property[@name='parameters']/b:structure", NS)
        )
        self.assertEqual(query.count("?"), len(bindings))
        params = wizard._get_birt_params()
        self.env.flush_all()
        self.env.cr.execute(
            query.replace("?", "%s"), [params[name] for _position, name in bindings])
        return self.env.cr.dictfetchall()

    def test_report_action(self):
        report = self.env.ref(REPORT)
        self.assertEqual(report.report_type, "birt")
        self.assertEqual(report.model, WIZARD)
        self.assertEqual(report.birt_report_type, "html")
        self.assertEqual(report.birt_template_mode, "http")
        self.assertTrue(report.birt_template_file)
        self.assertEqual(self.wizard._get_birt_report(), report)

    def test_print_opens_the_viewer(self):
        action = self.wizard.action_birt_view()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "dub_reporting_birt.viewer")
        params = action["params"]
        self.assertEqual(params["model"], WIZARD)
        self.assertEqual(params["res_id"], self.wizard.id)
        self.assertEqual(params["format"], "html")
        self.assertFalse(params["replace"])
        values = params["values"]
        self.assertEqual(values["company_id"], self.company.id)
        self.assertEqual(fields.Date.to_date(values["date_from"]), date(2025, 1, 1))
        self.assertEqual(fields.Date.to_date(values["date_to"]), date(2025, 12, 31))
        self.assertFalse(values["include_quotations"])

    def test_default_period_is_the_current_year(self):
        wizard = self.env[WIZARD].create({})
        today = fields.Date.context_today(wizard)
        self.assertEqual(wizard.company_id, self.env.company)
        self.assertEqual(wizard.date_from, date(today.year, 1, 1))
        self.assertEqual(wizard.date_to, date(today.year, 12, 31))
        self.assertFalse(wizard.include_quotations)

    def test_dates_in_order(self):
        with self.assertRaises(ValidationError):
            self.env[WIZARD].create({"date_from": "2025-12-31", "date_to": "2025-01-01"})

    def test_birt_params(self):
        params = self.wizard.with_context(tz="Europe/Rome", lang="en_US")._get_birt_params()
        self.assertEqual(params["company_id"], self.company.id)
        self.assertEqual(params["states"], "sale")
        # the period is in the user timezone, the bounds in UTC
        self.assertEqual(params["tz"], "Europe/Rome")
        self.assertEqual(params["datetime_from"], "2024-12-31 23:00:00")
        self.assertEqual(params["datetime_to"], "2025-12-31 23:00:00")
        self.assertEqual(params["date_pattern"], "MM/dd/yyyy")
        self.assertEqual(params["decimal_point"], ".")
        self.assertEqual(params["thousands_sep"], ",")
        self.assertEqual(params["company_name"], self.company.name)
        self.assertEqual(params["period"], "01/01/2025 - 12/31/2025")
        self.assertEqual(params["title"], "Sales by Customer")
        self.assertEqual(params["scope"], "Confirmed orders")
        self.assertEqual(params["currency"], "Amounts in %s" % self.company.currency_id.name)
        for key in ("lbl_period", "lbl_date", "lbl_order", "lbl_salesperson",
                    "lbl_untaxed", "lbl_total", "lbl_grand_total", "lbl_orders",
                    "lbl_page"):
            self.assertTrue(params[key], key)
        # every parameter is declared by the template, or BIRT ignores it
        design = etree.fromstring(base64.b64decode(self.env.ref(REPORT).birt_template_file))
        declared = {p.get("name") for p in design.iterfind(".//b:scalar-parameter", NS)}
        self.assertLessEqual(set(params), declared)

    def test_birt_params_in_italian(self):
        self.env["res.lang"]._activate_lang("it_IT")
        params = self.wizard.with_context(lang="it_IT")._get_birt_params()
        self.assertEqual(params["date_pattern"], "dd/MM/yyyy")
        self.assertEqual(params["decimal_point"], ",")
        self.assertEqual(params["thousands_sep"], ".")
        self.assertEqual(params["period"], "01/01/2025 - 31/12/2025")
        self.assertEqual(params["title"], "Vendite per cliente")
        self.assertEqual(params["lbl_total"], "Totale")

    def test_quotations_excluded_by_default(self):
        rows = self._report_rows(self.wizard)
        order_ids = {row["order_id"] for row in rows}
        self.assertIn(self.order.id, order_ids)
        self.assertNotIn(self.quotation.id, order_ids)
        self.assertNotIn(self.order_before.id, order_ids)
        # same selection as the orders opened by the drilldown
        self.assertEqual(
            order_ids, set(self.env["sale.order"].search(self.wizard._get_sale_order_domain()).ids))
        row = next(row for row in rows if row["order_id"] == self.order.id)
        self.assertEqual(row["partner_id"], self.customer.id)
        self.assertEqual(row["customer_name"], "BIRT Demo Customer")
        self.assertEqual(row["order_name"], self.order.name)
        self.assertEqual(row["order_date"], date(2025, 3, 10))
        self.assertAlmostEqual(float(row["amount_untaxed"]), self.order.amount_untaxed)
        self.assertAlmostEqual(float(row["amount_total"]), self.order.amount_total)
        self.assertEqual(row["customer_order_count"], 1)

    def test_quotations_included(self):
        self.wizard.include_quotations = True
        self.assertEqual(self.wizard._get_birt_params()["states"], "draft,sent,sale")
        rows = self._report_rows(self.wizard)
        order_ids = {row["order_id"] for row in rows}
        self.assertIn(self.order.id, order_ids)
        self.assertIn(self.quotation.id, order_ids)
        self.assertNotIn(self.order_before.id, order_ids)
        row = next(row for row in rows if row["order_id"] == self.order.id)
        self.assertEqual(row["customer_order_count"], 2)

    def test_amounts_in_company_currency(self):
        eur = self.env.ref("base.EUR")
        other = eur if self.company.currency_id != eur else self.env.ref("base.USD")
        other.active = True
        self.env["res.currency.rate"].create({
            "name": "2025-05-09",
            "currency_id": other.id,
            "company_id": self.company.id,
            "rate": 2.0,
        })
        pricelist = self.env["product.pricelist"].create({
            "name": "BIRT Demo Foreign Currency",
            "currency_id": other.id,
            "company_id": self.company.id,
        })
        order = self._create_order(
            self.customer, "2025-05-10 10:00:00", confirm=True, pricelist=pricelist)
        self.assertEqual(order.currency_id, other)
        self.assertNotEqual(order.currency_rate, 1.0)
        row = next(row for row in self._report_rows(self.wizard) if row["order_id"] == order.id)
        self.assertAlmostEqual(
            float(row["amount_untaxed"]), round(order.amount_untaxed / order.currency_rate, 2))
        self.assertAlmostEqual(
            float(row["amount_total"]), round(order.amount_total / order.currency_rate, 2))

    def test_drilldown_order(self):
        action = self.wizard.birt_drilldown({
            "key": "record", "model": "sale.order", "id": str(self.order.id),
        })
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "sale.order")
        self.assertEqual(action["res_id"], self.order.id)
        self.assertEqual(action["views"], [(False, "form")])

    def test_drilldown_partner(self):
        action = self.wizard.birt_drilldown({
            "key": "record", "model": "res.partner", "id": str(self.customer.id),
        })
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "res.partner")
        self.assertEqual(action["res_id"], self.customer.id)
        self.assertEqual(action["views"], [(False, "form")])

    def test_drilldown_customer_orders(self):
        action = self.wizard.birt_drilldown({
            "key": "orders", "partner_id": str(self.customer.id),
        })
        self.assertEqual(action["res_model"], "sale.order")
        orders = self.env["sale.order"].search(action["domain"])
        self.assertEqual(orders, self.order)
        self.wizard.include_quotations = True
        action = self.wizard.birt_drilldown({
            "key": "orders", "partner_id": str(self.customer.id),
        })
        orders = self.env["sale.order"].search(action["domain"])
        self.assertEqual(orders, self.order | self.quotation)
        self.assertFalse(self.wizard.birt_drilldown({"key": "orders", "partner_id": "0"}))
        self.assertFalse(self.wizard.birt_drilldown({"key": "unknown"}))

    def test_render_request(self):
        """What Odoo posts to BIRT: the wizard parameters, flattened, and the
        output format both as BIRT format and as template parameter."""
        self.company.birt_base_url = "http://birt.test:8080/birt"
        with patch(
            "odoo.addons.dub_reporting_birt.models.ir_actions_report.requests.post"
        ) as post:
            post.return_value.content = b"<html></html>"
            self.wizard._birt_viewer_render("html")
            url, = post.call_args.args
            data = post.call_args.kwargs["data"]
            self.assertEqual(url, "http://birt.test:8080/birt/preview")
            self.assertEqual(data["__format"], "html")
            self.assertEqual(data["odoo_output_format"], "html")
            self.assertIn("/report/birt/template/dub_reporting_birt_demo.sales_by_customer",
                          data["__report"])
            self.assertEqual(data["states"], "sale")
            self.assertEqual(data["company_id"], self.company.id)
            self.assertEqual(data["ids"], str(self.wizard.id))

            post.return_value.content = b"%PDF-"
            self.wizard._birt_viewer_render("pdf")
            url, = post.call_args.args
            data = post.call_args.kwargs["data"]
            self.assertEqual(url, "http://birt.test:8080/birt/run2phase")
            self.assertEqual(data["odoo_output_format"], "pdf")
