from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import babel_locale_parse, format_date, get_lang, posix_to_ldml


class SalesByCustomerWizard(models.TransientModel):
    """Parameters of the "Sales by Customer" BIRT demo report.

    BIRT reads the orders straight from PostgreSQL (data set of
    ``reports/templates/sales_by_customer.rptdesign``): the wizard sends the
    filters, the labels translated in the language of the user and the date
    and number formats of that language as report parameters, then shows the
    report in the on-screen viewer of ``dub_reporting_birt``.
    """

    _name = "dub.birt.demo.sale.customer.wizard"
    _inherit = ["dub.birt.report.wizard.mixin"]
    _description = "Sales by Customer (BIRT Demo)"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        domain=lambda self: [("id", "in", self.env.companies.ids)],
    )
    date_from = fields.Date(
        string="Date From",
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(month=1, day=1),
    )
    date_to = fields.Date(
        string="Date To",
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(month=12, day=31),
    )
    include_quotations = fields.Boolean(
        help="Also show the quotations (draft and sent). By default the "
        "report shows the confirmed orders only.",
    )

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from > wizard.date_to:
                raise ValidationError(
                    self.env._("The start date must be before the end date.")
                )

    def _get_birt_report(self):
        return self.env.ref("dub_reporting_birt_demo.action_report_sales_by_customer")

    def _get_birt_filename(self, fmt):
        self.ensure_one()
        return "%s %s %s.%s" % (
            self.env._("Sales by Customer"), self.date_from, self.date_to, fmt,
        )

    def _get_order_states(self):
        self.ensure_one()
        return ["draft", "sent", "sale"] if self.include_quotations else ["sale"]

    def _get_tz(self):
        tz = self.env.context.get("tz") or self.env.user.tz
        return tz if tz in pytz.all_timezones_set else "UTC"

    def _get_period_bounds(self):
        """Return the period as naive UTC datetimes, the end excluded: the
        order date is stored in UTC, the period is in the user timezone."""
        self.ensure_one()
        tz = pytz.timezone(self._get_tz())

        def to_utc(day):
            local = tz.localize(datetime.combine(day, time.min))
            return local.astimezone(pytz.utc).replace(tzinfo=None)

        return to_utc(self.date_from), to_utc(self.date_to + timedelta(days=1))

    def _get_sale_order_domain(self):
        """The orders of the report, as the data set selects them."""
        self.ensure_one()
        date_start, date_stop = self._get_period_bounds()
        return [
            ("company_id", "=", self.company_id.id),
            ("state", "in", self._get_order_states()),
            ("date_order", ">=", fields.Datetime.to_string(date_start)),
            ("date_order", "<", fields.Datetime.to_string(date_stop)),
        ]

    def _get_birt_params(self):
        self.ensure_one()
        date_start, date_stop = self._get_period_bounds()
        lang = get_lang(self.env)
        params = {
            # Filters: the positional parameters of the data set query
            "company_id": self.company_id.id,
            "datetime_from": fields.Datetime.to_string(date_start),
            "datetime_to": fields.Datetime.to_string(date_stop),
            "states": ",".join(self._get_order_states()),
            "tz": self._get_tz(),
            # Formats of the user language, applied by the template
            "date_pattern": posix_to_ldml(
                lang.date_format, locale=babel_locale_parse(lang.code)),
            "decimal_point": lang.decimal_point,
            "thousands_sep": lang.thousands_sep or "",
            # Page header
            "company_name": self.company_id.name,
            "period": "%s - %s" % (
                format_date(self.env, self.date_from),
                format_date(self.env, self.date_to),
            ),
        }
        params.update(self._get_birt_labels())
        return params

    def _get_birt_labels(self):
        """Static texts of the template, in the language of the user."""
        self.ensure_one()
        _ = self.env._
        return {
            "title": _("Sales by Customer"),
            "scope": _("Confirmed orders and quotations")
            if self.include_quotations else _("Confirmed orders"),
            "currency": _("Amounts in %s", self.company_id.currency_id.name),
            "lbl_period": _("Period"),
            "lbl_date": _("Date"),
            "lbl_order": _("Order"),
            "lbl_salesperson": _("Salesperson"),
            "lbl_untaxed": _("Untaxed"),
            "lbl_total": _("Total"),
            "lbl_grand_total": _("Grand Total"),
            "lbl_orders": _("Orders"),
            "lbl_page": _("Page"),
        }

    def _get_birt_drilldown_action(self, key, values):
        """Drilldown of the HTML preview: ``orders`` opens the orders of the
        customer ``partner_id`` selected by the report."""
        if key != "orders":
            return super()._get_birt_drilldown_action(key, values)
        self.ensure_one()
        partner = self.env["res.partner"].browse(
            self._birt_drilldown_int(values, "partner_id")).exists()
        if not partner:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Orders - %s", partner.display_name),
            "res_model": "sale.order",
            "views": [(False, "list"), (False, "form")],
            "domain": self._get_sale_order_domain() + [
                ("partner_id.commercial_partner_id", "=", partner.id),
            ],
            "context": {"create": False},
            "target": "current",
        }
