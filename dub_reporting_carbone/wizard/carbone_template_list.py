# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import requests
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CarboneTemplateList(models.TransientModel):
    """Wizard to list and manage templates on Carbone server."""

    _name = 'carbone.template.list'
    _description = 'Carbone Server Templates'

    name = fields.Char(string='Name', readonly=True)
    template_id = fields.Char(string='Version ID', readonly=True)
    constant_id = fields.Char(string='Template ID', readonly=True, help='Constant ID for versioning')
    extension = fields.Char(string='Extension', readonly=True)
    size = fields.Integer(string='Size (bytes)', readonly=True)
    created_at = fields.Datetime(string='Created', readonly=True)
    deployed_at = fields.Datetime(string='Deployed', readonly=True)
    expire_at = fields.Datetime(string='Expires', readonly=True)
    category = fields.Char(string='Category', readonly=True)
    comment = fields.Char(string='Comment', readonly=True)
    tags = fields.Char(string='Tags', readonly=True)
    origin = fields.Selection([
        ('api', 'API'),
        ('studio', 'Studio'),
    ], string='Origin', readonly=True)
    linked_report_id = fields.Many2one(
        'ir.actions.report',
        string='Linked Report',
        compute='_compute_linked_report',
        store=False,
    )

    @api.depends('template_id')
    def _compute_linked_report(self):
        """Find if this template is linked to an Odoo report."""
        Report = self.env['ir.actions.report']
        for record in self:
            if record.template_id:
                report = Report.search([
                    ('carbone_template_id', '=', record.template_id)
                ], limit=1)
                record.linked_report_id = report.id if report else False
            else:
                record.linked_report_id = False

    @api.model
    def action_fetch_templates(self):
        """Fetch templates from Carbone server and display them."""
        company = self.env.company
        api_url = company.carbone_api_url
        access_token = company.carbone_access_token
        template_tag = company.carbone_template_tag

        if not api_url:
            raise UserError(_("Carbone API URL is not configured."))
        if not access_token:
            raise UserError(_("Carbone Access Token is not configured."))
        if not template_tag:
            raise UserError(_(
                "Template Tag is not configured.\n\n"
                "Please configure a tag in Settings > Reporting Tools > Carbone.io "
                "to filter templates belonging to this Odoo instance."
            ))

        # Clear existing records
        self.search([]).unlink()

        # Fetch templates from API (filtered by tag - required)
        templates = self._fetch_templates_from_api(api_url, access_token, template_tag)

        # Double-check: filter client-side to ensure only templates with our tag are shown
        templates = [
            tpl for tpl in templates
            if template_tag in (tpl.get('tags') or [])
        ]

        # Create records
        for tpl in templates:
            created_at = None

            # Parse dates (can be Unix timestamp or ISO string)
            if tpl.get('createdAt'):
                try:
                    created_at_val = tpl['createdAt']
                    if isinstance(created_at_val, (int, float)):
                        created_at = datetime.fromtimestamp(created_at_val)
                    else:
                        created_at = datetime.fromisoformat(
                            str(created_at_val).replace('Z', '+00:00')
                        )
                except (ValueError, TypeError, OSError):
                    pass


            # API uses versionId (or templateId in some cases) and type for extension
            version_id = tpl.get('versionId') or tpl.get('templateId')
            constant_id = tpl.get('id')  # Constant ID for versioning

            # Parse deployedAt and expireAt timestamps
            deployed_at = None
            expire_at = None

            if tpl.get('deployedAt'):
                try:
                    deployed_at_val = tpl['deployedAt']
                    if deployed_at_val and deployed_at_val != 0:
                        if isinstance(deployed_at_val, (int, float)):
                            deployed_at = datetime.fromtimestamp(deployed_at_val)
                except (ValueError, TypeError, OSError):
                    pass

            if tpl.get('expireAt'):
                try:
                    expire_at_val = tpl['expireAt']
                    if expire_at_val and expire_at_val != 0:
                        if isinstance(expire_at_val, (int, float)):
                            expire_at = datetime.fromtimestamp(expire_at_val)
                except (ValueError, TypeError, OSError):
                    pass

            # Origin: 0 = API, 1 = Studio
            origin_val = tpl.get('origin', 0)
            origin = 'studio' if origin_val == 1 else 'api'

            self.create({
                'name': tpl.get('name') or (version_id[:20] if version_id else ''),
                'template_id': version_id,
                'constant_id': constant_id,
                'extension': tpl.get('type') or tpl.get('extension'),
                'size': tpl.get('size', 0),
                'created_at': created_at,
                'deployed_at': deployed_at,
                'expire_at': expire_at,
                'category': tpl.get('category'),
                'comment': tpl.get('comment'),
                'tags': ', '.join(tpl.get('tags', [])) if tpl.get('tags') else '',
                'origin': origin,
            })

        return {
            'name': _('Carbone Server Templates'),
            'type': 'ir.actions.act_window',
            'res_model': 'carbone.template.list',
            'view_mode': 'list',
            'target': 'current',
            'context': {'create': False},
        }

    def _fetch_templates_from_api(self, api_url, access_token, template_tag):
        """Fetch templates from Carbone API, filtered by tag."""
        templates = []
        cursor = None
        base_url = api_url.rstrip('/')

        headers = {
            'Authorization': f'Bearer {access_token}',
            'carbone-version': '5',
        }

        while True:
            url = f"{base_url}/templates"
            params = {
                'limit': 100,
                'tags': template_tag,  # Always filter by tag
            }
            if cursor:
                params['cursor'] = cursor

            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        # data['data'] can be a list directly or an object with 'templates' key
                        raw_data = data.get('data', [])
                        if isinstance(raw_data, list):
                            batch = raw_data
                        else:
                            batch = raw_data.get('templates', [])
                        templates.extend(batch)

                        # Check for pagination
                        has_more = data.get('hasMore', False)
                        cursor = data.get('nextCursor') or (raw_data.get('nextCursor') if isinstance(raw_data, dict) else None)
                        if not cursor or not batch or not has_more:
                            break
                    else:
                        error_msg = data.get('error', 'Unknown error')
                        raise UserError(_("Carbone API error: %s") % error_msg)
                elif response.status_code == 401:
                    raise UserError(_("Invalid Carbone API token."))
                elif response.status_code == 404:
                    _logger.warning("Templates endpoint not found, API may not support listing")
                    break
                elif response.status_code == 501:
                    # Stateless mode - endpoint not available
                    raise UserError(_(
                        "Template listing is not available.\n\n"
                        "Your Carbone server is running in stateless mode (without database).\n"
                        "This feature requires Carbone Cloud or Carbone On-Premise with database enabled."
                    ))
                else:
                    raise UserError(
                        _("Carbone API returned HTTP %s") % response.status_code
                    )

            except requests.exceptions.Timeout:
                raise UserError(_("Connection to Carbone API timed out."))
            except requests.exceptions.ConnectionError:
                raise UserError(_("Could not connect to Carbone API."))

        return templates

    def action_delete_template(self):
        """Delete selected template from Carbone server."""
        self.ensure_one()

        if not self.template_id:
            raise UserError(_("No template ID to delete."))

        # Check if linked to a report
        if self.linked_report_id:
            raise UserError(_(
                "This template is linked to report '%s'. "
                "Delete the report or invalidate its cache first."
            ) % self.linked_report_id.name)

        company = self.env.company
        api_url = company.carbone_api_url
        access_token = company.carbone_access_token

        if not api_url or not access_token:
            raise UserError(_("Carbone API is not configured."))

        headers = {
            'Authorization': f'Bearer {access_token}',
            'carbone-version': '5',
        }

        url = f"{api_url.rstrip('/')}/template/{self.template_id}"

        try:
            response = requests.delete(url, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Remove from list
                    self.unlink()
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _("Template Deleted"),
                            'message': _("Template successfully deleted from Carbone server."),
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    raise UserError(_("Failed to delete: %s") % data.get('error', 'Unknown'))
            elif response.status_code == 404:
                # Template already gone, remove from list
                self.unlink()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _("Template Not Found"),
                        'message': _("Template was already deleted from server."),
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_("HTTP %s from Carbone API") % response.status_code)

        except requests.exceptions.Timeout:
            raise UserError(_("Connection to Carbone API timed out."))
        except requests.exceptions.ConnectionError:
            raise UserError(_("Could not connect to Carbone API."))

    def action_delete_orphan_templates(self):
        """Delete all templates not linked to any Odoo report."""
        orphans = self.search([]).filtered(lambda t: not t.linked_report_id)

        if not orphans:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("No Orphan Templates"),
                    'message': _("All templates are linked to Odoo reports."),
                    'type': 'info',
                    'sticky': False,
                }
            }

        deleted_count = 0
        errors = []

        for orphan in orphans:
            try:
                result = orphan.action_delete_template()
                if result and result.get('params', {}).get('type') == 'success':
                    deleted_count += 1
            except UserError as e:
                errors.append(str(e))

        message = _("Deleted %d orphan template(s).") % deleted_count
        if errors:
            message += _(" Errors: %s") % ', '.join(errors[:3])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Cleanup Complete"),
                'message': message,
                'type': 'success' if not errors else 'warning',
                'sticky': bool(errors),
            }
        }

    def action_refresh_list(self):
        """Refresh the template list."""
        return self.action_fetch_templates()
