import io
import logging
import os
from unittest.mock import patch
from odoo.tests.common import TransactionCase, tagged, _super_send

_logger = logging.getLogger(__name__)

try:
    from pdfminer.high_level import extract_text
    HAS_PDFMINER = True
except ImportError:
    HAS_PDFMINER = False


def _allow_external(s, r, **kw):
    """Allow external HTTP requests to Carbone API during tests."""
    return _super_send(s, r, **kw)


def _pdf_text(content):
    """Extract text from PDF bytes using pdfminer."""
    if not HAS_PDFMINER:
        return ''
    return extract_text(io.BytesIO(content))


@tagged('post_install', '-at_install')
class TestDemoReports(TransactionCase):
    """Test demo Carbone reports generate valid PDFs with correct data."""

    def setUp(self):
        super().setUp()
        api_key = os.environ.get('CARBONE_TEST_API_KEY')
        if not api_key:
            self.skipTest("CARBONE_TEST_API_KEY not set")

        self.company = self.env.user.company_id
        self.company.sudo().write({
            'carbone_api_url': 'https://api.carbone.io',
            'carbone_access_token': api_key,
        })
        self.env.invalidate_all()

    def test_invoice_simple_pdf(self):
        """Test Invoice Simple generates a valid PDF with invoice data."""
        report = self.env.ref(
            'dub_reporting_carbone_demo.report_invoice_simple_carbone',
            raise_if_not_found=False,
        )
        if not report:
            self.skipTest("Invoice Simple report not found")

        invoice = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
        ], limit=1)
        if not invoice:
            self.skipTest("No demo invoice found")

        with patch.object(type(self), '_request_handler', _allow_external):
            content, rtype = report._render_carbone(
                'dub_reporting_carbone_demo.report_invoice_simple_carbone',
                str(invoice.id), None,
            )

        self.assertTrue(content, "PDF content should not be empty")
        self.assertGreater(len(content), 1000, "PDF should be larger than 1KB")
        self.assertEqual(content[:5], b'%PDF-', "Should be a valid PDF")

        if not HAS_PDFMINER:
            _logger.warning("pdfminer not installed, skipping text checks")
            return

        text = _pdf_text(content)
        _logger.info("Invoice PDF text:\n%s", text[:500])

        company_name = invoice.company_id.name
        self.assertIn(
            company_name, text,
            "PDF should contain company name '%s'" % company_name,
        )
        self.assertIn(
            invoice.partner_id.name, text,
            "PDF should contain customer name '%s'" % invoice.partner_id.name,
        )
        for line in invoice.invoice_line_ids:
            if not line.display_type and line.product_id:
                self.assertIn(
                    line.product_id.name, text,
                    "PDF should contain product '%s'" % line.product_id.name,
                )
                break

    def test_quote_datasheet_pdf(self):
        """Test Quote with Datasheet generates a valid PDF with order data."""
        report = self.env.ref(
            'dub_reporting_carbone_demo.report_quote_datasheet_carbone',
            raise_if_not_found=False,
        )
        if not report:
            self.skipTest("Quote Datasheet report not found")

        order = self.env['sale.order'].search([], limit=1)
        if not order:
            self.skipTest("No demo sale order found")

        with patch.object(type(self), '_request_handler', _allow_external):
            content, rtype = report._render_carbone(
                'dub_reporting_carbone_demo.report_quote_datasheet_carbone',
                str(order.id), None,
            )

        self.assertTrue(content, "PDF content should not be empty")
        self.assertGreater(len(content), 1000, "PDF should be larger than 1KB")
        self.assertEqual(content[:5], b'%PDF-', "Should be a valid PDF")

        if not HAS_PDFMINER:
            _logger.warning("pdfminer not installed, skipping text checks")
            return

        text = _pdf_text(content)
        _logger.info("Quote PDF text:\n%s", text[:500])

        for line in order.order_line:
            if not line.display_type and line.product_id:
                self.assertIn(
                    line.product_id.name, text,
                    "PDF should contain product '%s'" % line.product_id.name,
                )
                break

        total_str = '{:,.2f}'.format(order.amount_total)
        self.assertIn(
            total_str, text,
            "PDF should contain total amount '%s'" % total_str,
        )
