import json
import logging
import os
from unittest.mock import patch, MagicMock
from odoo.tests.common import TransactionCase, tagged, _super_send
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Default test token for Carbone API (can be overridden via CARBONE_TEST_API_KEY env var)
_CARBONE_TEST_TOKEN = (
    'test_eyJhbGciOiJFUzUxMiIsInR5cCI6IkpXVCJ9'
    '.eyJpc3MiOiIxMTI5NjQyMjQwODM5NDcxNTEzIiwiYXVkIjoiY2FyYm9uZSIs'
    'ImV4cCI6MjQwNjM3OTA0OSwiZGF0YSI6eyJ0eXBlIjoidGVzdCJ9fQ'
    '.AdahaoHKffubKA2DUf1i4CTgTzIx6IsXSqUfWOsmvsE22_NzzO_9JTHNdegjlK8d6vD4q1hmSS99sTpP9HHI_1rr'
    'ADhlo0K5p5XJI8vQJZpdjGyvsjVvKXkA9WQiQ7PnnFN-FVgOncgzrFVVH8NUCMexFdHBBCY6PH2QgM8mgzpweq-K'
)


def _mock_carbone_post(url, **kwargs):
    """Mock Carbone API POST requests."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()

    if '/template' in url and '/render/' not in url:
        # Template upload response
        resp.json.return_value = {
            'success': True,
            'data': {'templateId': 'mock_template_id_abc123'},
        }
    elif '/render/' in url:
        # Render request response
        resp.json.return_value = {
            'success': True,
            'data': {'renderId': 'mock_render_id_xyz789.pdf'},
        }
    return resp


def _mock_carbone_get(url, **kwargs):
    """Mock Carbone API GET requests."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()

    if '/render/' in url:
        # Render retrieval - return fake PDF content
        resp.content = b'%PDF-1.4 mock pdf content for testing'
    return resp


@tagged('post_install', '-at_install')
class TestCarboneReportLocal(TransactionCase):
    """Test Carbone report configuration and local logic (no API calls)."""

    def setUp(self):
        super().setUp()

        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner for Carbone',
            'email': 'test@carbone.example.com',
        })

        # Get demo report via xml_id (works with JSON name fields in Odoo 19)
        self.report = self.env.ref(
            'dub_reporting_carbone.demo_report_partner_i18n',
            raise_if_not_found=False,
        )
        if not self.report:
            self.report = self.env['ir.actions.report'].search([
                ('model', '=', 'res.partner'),
                ('report_type', '=', 'carbone'),
                ('report_name', '=', 'demo_partner_i18n'),
            ], limit=1)

        if not self.report:
            self.skipTest("Partner Demo Report not found (install with demo data)")

        api_key = os.environ.get('CARBONE_TEST_API_KEY') or _CARBONE_TEST_TOKEN
        self.company = self.env.user.company_id
        self.company.sudo().write({
            'carbone_api_url': 'https://api.carbone.io',
            'carbone_access_token': api_key,
        })
        self.env.invalidate_all()

    def test_01_report_configuration(self):
        """Test report is properly configured."""
        self.assertTrue(self.report, "Report should exist")
        self.assertEqual(self.report.report_type, 'carbone')
        self.assertEqual(self.report.carbone_report_type, 'pdf')
        self.assertTrue(self.report.carbone_template_file, "Template file should be set")
        self.assertTrue(self.report.carbone_json_data, "JSON data should be set")

    def test_02_validation_missing_url(self):
        """Test validation fails with missing API URL."""
        self.env.cr.execute(
            "UPDATE res_company SET carbone_api_url = NULL WHERE id = %s",
            (self.company.id,),
        )
        self.env.invalidate_all()
        with self.assertRaises(ValidationError):
            self.report._validate_carbone_config()

    def test_02b_validation_missing_token(self):
        """Test validation fails with missing access token."""
        self.env.cr.execute(
            "UPDATE res_company SET carbone_access_token = NULL WHERE id = %s",
            (self.company.id,),
        )
        self.env.invalidate_all()
        with self.assertRaises(ValidationError):
            self.report._validate_carbone_config()

    def test_02c_validation_valid(self):
        """Test validation passes with proper configuration."""
        try:
            self.report._validate_carbone_config()
        except ValidationError:
            self.fail("Validation should pass with proper configuration")

    def test_04_render_payload_preparation(self):
        """Test JSON payload preparation for single record."""
        payload = self.report._prepare_render_payload(self.partner)

        self.assertIn('data', payload)
        self.assertIn('convertTo', payload)
        self.assertEqual(payload['convertTo'], 'pdf')
        self.assertIn('name', payload['data'])
        self.assertIn('email', payload['data'])
        self.assertEqual(payload['data']['name'], 'Test Partner for Carbone')

    def test_04b_multi_record_payload(self):
        """Test payload preparation for multiple records."""
        partner2 = self.env['res.partner'].create({
            'name': 'Second Test Partner',
            'email': 'test2@carbone.example.com',
        })
        partners = self.partner | partner2

        payload = self.report._prepare_render_payload(partners)
        self.assertIn('data', payload)
        self.assertIn('items', payload['data'])
        self.assertEqual(len(payload['data']['items']), 2)
        self.assertIn('batchSplitBy', payload)

    def test_06_cache_invalidation(self):
        """Test template cache invalidation."""
        self.report.sudo().write({'carbone_template_id': 'fake_template_id_123'})
        self.assertEqual(self.report.carbone_template_id, 'fake_template_id_123')

        self.report.action_invalidate_template_cache()
        self.assertFalse(self.report.carbone_template_id, "Cache should be cleared")

    def test_08_report_binding(self):
        """Test report binding is properly set."""
        binding = self.env.ref(
            'dub_reporting_carbone.report_partner_demo',
            raise_if_not_found=False,
        )
        if binding:
            self.assertEqual(binding.binding_model_id.model, 'res.partner')
            self.assertEqual(binding.binding_type, 'report')

    def test_09_format_compatibility(self):
        """Test format compatibility validation."""
        allowed = self.report._get_allowed_output_formats()
        self.assertIn('pdf', allowed)
        self.assertIn('docx', allowed)

    def test_10_template_data(self):
        """Test template data retrieval."""
        self.assertTrue(self.report._has_carbone_template())
        data, name = self.report._get_carbone_template_data()
        self.assertTrue(data, "Template data should be available")
        self.assertTrue(name, "Template name should be returned")


@tagged('post_install', '-at_install')
class TestCarboneReportMockedAPI(TransactionCase):
    """Test Carbone API integration with mocked HTTP responses.

    These tests verify the full rendering pipeline using mocked
    Carbone API responses (no real network calls).
    """

    def setUp(self):
        super().setUp()

        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner for Carbone API',
            'email': 'test@carbone.example.com',
        })

        self.report = self.env.ref(
            'dub_reporting_carbone.demo_report_partner_i18n',
            raise_if_not_found=False,
        )
        if not self.report:
            self.report = self.env['ir.actions.report'].search([
                ('model', '=', 'res.partner'),
                ('report_type', '=', 'carbone'),
                ('report_name', '=', 'demo_partner_i18n'),
            ], limit=1)

        if not self.report:
            self.skipTest("Partner Demo Report not found (install with demo data)")

        self.company = self.env.user.company_id
        self.company.sudo().write({
            'carbone_api_url': 'https://api.carbone.io',
            'carbone_access_token': _CARBONE_TEST_TOKEN,
        })
        self.env.invalidate_all()

    @patch('odoo.addons.dub_reporting_carbone.models.ir_actions_report.requests.post',
           side_effect=_mock_carbone_post)
    @patch('odoo.addons.dub_reporting_carbone.models.ir_actions_report.requests.get',
           side_effect=_mock_carbone_get)
    def test_03_template_upload(self, mock_get, mock_post):
        """Test template upload and caching."""
        template_id = self.report._upload_template()
        self.assertTrue(template_id, "Template ID should be returned")
        self.assertEqual(template_id, 'mock_template_id_abc123')

        # Check caching
        if self.report.carbone_use_template_cache:
            self.assertEqual(self.report.carbone_template_id, template_id)

            # Second upload should use cache (no additional POST)
            cached_id = self.report._upload_template()
            self.assertEqual(cached_id, template_id, "Should use cached template")

    @patch('odoo.addons.dub_reporting_carbone.models.ir_actions_report.requests.post',
           side_effect=_mock_carbone_post)
    @patch('odoo.addons.dub_reporting_carbone.models.ir_actions_report.requests.get',
           side_effect=_mock_carbone_get)
    def test_05_report_generation(self, mock_get, mock_post):
        """Test full report generation pipeline."""
        result = self.report._render_carbone(
            self.report.report_name,
            str(self.partner.id),
            {}
        )

        self.assertTrue(result, "Report should return content")
        self.assertEqual(len(result), 2, "Should return tuple (content, format)")

        content, format_type = result
        self.assertTrue(content, "Content should not be empty")
        self.assertEqual(format_type, 'pdf', "Format should be PDF")
        self.assertGreater(len(content), 0, "Content should have data")

        # Verify API was called correctly
        self.assertTrue(mock_post.called, "POST should have been called")

    @patch('odoo.addons.dub_reporting_carbone.models.ir_actions_report.requests.post',
           side_effect=_mock_carbone_post)
    @patch('odoo.addons.dub_reporting_carbone.models.ir_actions_report.requests.get',
           side_effect=_mock_carbone_get)
    def test_07_multi_record_rendering(self, mock_get, mock_post):
        """Test rendering with multiple records."""
        partner2 = self.env['res.partner'].create({
            'name': 'Second Test Partner',
            'email': 'test2@carbone.example.com',
        })

        result = self.report._render_carbone(
            self.report.report_name,
            f"{self.partner.id},{partner2.id}",
            {}
        )

        self.assertTrue(result, "Multi-record report should work")
        content, format_type = result
        self.assertGreater(len(content), 0, "Multi-record content should have data")


@tagged('post_install', '-at_install', 'carbone_api')
class TestCarboneReportLiveAPI(TransactionCase):
    """Test Carbone API with real HTTP calls.

    These tests are tagged 'carbone_api' and skipped unless
    CARBONE_TEST_API_KEY environment variable is set.
    Run with: --test-tags carbone_api
    """

    def setUp(self):
        super().setUp()

        api_key = os.environ.get('CARBONE_TEST_API_KEY')
        if not api_key:
            self.skipTest("CARBONE_TEST_API_KEY not set, skipping live API tests")

        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner for Carbone Live',
            'email': 'test@carbone.example.com',
        })

        self.report = self.env.ref(
            'dub_reporting_carbone.demo_report_partner_i18n',
            raise_if_not_found=False,
        )
        if not self.report:
            self.skipTest("Partner Demo Report not found (install with demo data)")

        self.company = self.env.user.company_id
        self.company.sudo().write({
            'carbone_api_url': 'https://api.carbone.io',
            'carbone_access_token': api_key,
        })
        self.env.invalidate_all()

    @staticmethod
    def _allow_external(s, r, **kw):
        return _super_send(s, r, **kw)

    def test_live_01_template_upload(self):
        """Test real template upload to Carbone API."""
        with patch.object(type(self), '_request_handler', self._allow_external):
            template_id = self.report._upload_template()
            self.assertTrue(template_id, "Template ID should be returned")
            _logger.info("Live template upload successful: %s", template_id)

    def test_live_02_report_generation(self):
        """Test real report generation via Carbone API."""
        with patch.object(type(self), '_request_handler', self._allow_external):
            result = self.report._render_carbone(
                self.report.report_name,
                str(self.partner.id),
                {}
            )

            content, format_type = result
            self.assertTrue(content, "Content should not be empty")
            self.assertEqual(format_type, 'pdf')
            self.assertGreater(len(content), 100, "PDF should have substantial content")
            _logger.info("Live report generated: %d bytes", len(content))
