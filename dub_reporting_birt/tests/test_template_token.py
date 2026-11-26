import base64
from urllib.parse import parse_qs, urlsplit

from odoo.tests import HttpCase, tagged

TEMPLATE = b"<?xml version='1.0'?><report/>"


@tagged('post_install', '-at_install')
class TestBirtTemplateToken(HttpCase):
    """The template endpoint is public: only the signed URL may read it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env['ir.actions.report'].create({
            'name': 'Token test',
            'model': 'res.partner',
            'report_type': 'birt',
            'report_name': 'dub_reporting_birt.token_test',
            'birt_template_mode': 'http',
            'birt_template_file': base64.b64encode(TEMPLATE),
            'birt_template_filename': 'token_test.rptdesign',
        })

    def _get(self, token=None):
        path = '/report/birt/template/' + self.report.report_name
        if token is not None:
            path += '?token=' + token
        return self.url_open(path)

    def test_url_carries_token_and_cache_buster(self):
        query = parse_qs(urlsplit(self.report._get_birt_template_url()).query)
        self.assertEqual(query['token'], [self.report._get_birt_template_token()])
        self.assertIn('v', query)

    def test_token_differs_per_report(self):
        other = self.report.copy({'report_name': 'dub_reporting_birt.token_test_2'})
        self.assertNotEqual(other._get_birt_template_token(),
                            self.report._get_birt_template_token())

    def test_template_needs_the_token(self):
        self.assertEqual(self._get().status_code, 404)
        self.assertEqual(self._get('wrong').status_code, 404)
        response = self._get(self.report._get_birt_template_token())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, TEMPLATE)
