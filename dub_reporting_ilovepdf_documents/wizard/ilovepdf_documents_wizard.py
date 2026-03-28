import base64
import logging
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.dub_reporting_ilovepdf.wizard.ilovepdf_wizard import ILOVEPDF_TOOLS

_logger = logging.getLogger(__name__)


class ILovePDFDocumentsWizard(models.TransientModel):
    _name = 'ilovepdf.documents.wizard'
    _description = 'ILovePDF Documents Processing Wizard'
    _inherit = 'ilovepdf.wizard'

    # Override attachment_ids to not be required (we use document_ids)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments',
        required=False,
    )

    document_ids = fields.Many2many(
        'documents.document',
        string='Documents',
        required=True,
    )

    @api.model
    def default_get(self, fields_list):
        # Skip parent's default_get for attachment_ids
        res = models.TransientModel.default_get(self, fields_list)
        # Check for default_document_ids from context (set by server action)
        default_doc_ids = self.env.context.get('default_document_ids', [])
        if default_doc_ids:
            res['document_ids'] = [(6, 0, default_doc_ids)]
        else:
            # Fallback to active_ids
            active_ids = self.env.context.get('active_ids', [])
            if active_ids and self.env.context.get('active_model') == 'documents.document':
                res['document_ids'] = [(6, 0, active_ids)]
        return res

    @api.onchange('tool')
    def _onchange_tool(self):
        """Validate selected documents against tool requirements."""
        if not self.tool or not self.document_ids:
            return

        tool_config = ILOVEPDF_TOOLS.get(self.tool)
        if not tool_config:
            return

        # Check minimum files for multi-file operations
        min_files = tool_config.get('min_files', 1)
        if len(self.document_ids) < min_files:
            return {
                'warning': {
                    'title': _('Invalid Selection'),
                    'message': _('This operation requires at least %d files.') % min_files,
                }
            }

        # Check file types
        valid_mimetypes = tool_config['input_mimetypes']
        invalid_docs = self.document_ids.filtered(
            lambda d: d.mimetype not in valid_mimetypes
        )
        if invalid_docs:
            return {
                'warning': {
                    'title': _('Invalid File Type'),
                    'message': _('Some documents are not supported for this operation: %s') %
                              ', '.join(invalid_docs.mapped('name')),
                }
            }

    def action_process(self):
        """Execute the ILovePDF processing on documents."""
        self.ensure_one()

        if not self.document_ids:
            raise ValidationError(_('Please select at least one document.'))

        tool_config = ILOVEPDF_TOOLS.get(self.tool)
        if not tool_config:
            raise ValidationError(_('Invalid operation selected.'))

        # Validate file types
        valid_mimetypes = tool_config['input_mimetypes']
        for document in self.document_ids:
            if document.mimetype not in valid_mimetypes:
                raise ValidationError(_(
                    'Document "%(name)s" is not supported for this operation. '
                    'Expected: %(types)s',
                    name=document.name,
                    types=', '.join(valid_mimetypes)
                ))

        # Validate minimum files
        min_files = tool_config.get('min_files', 1)
        if len(self.document_ids) < min_files:
            raise ValidationError(_(
                'This operation requires at least %d files.'
            ) % min_files)

        _logger.info('Starting ILovePDF %s for %d document(s)', self.tool, len(self.document_ids))

        # Start task
        server, task = self._start_task(self.tool)
        _logger.debug('Task started: server=%s, task=%s', server, task)

        # Upload files from documents
        uploaded_files = []
        for document in self.document_ids:
            # Use document's attachment
            attachment = document.attachment_id
            if not attachment:
                raise ValidationError(_('Document "%s" has no file attached.') % document.name)

            server_filename = self._upload_file(server, task, attachment)
            uploaded_files.append({
                'server_filename': server_filename,
                'filename': document.name,
            })
            _logger.debug('File uploaded: %s -> %s', document.name, server_filename)

        # Process
        options = self._get_process_options()
        process_result = self._process_task(server, task, self.tool, uploaded_files, options)
        _logger.debug('Process result: %s', process_result)

        # Download result
        result_content = self._download_result(server, task)
        _logger.info('Downloaded result: %d bytes', len(result_content))

        # Generate output filename
        if len(self.document_ids) == 1:
            output_filename = self._get_output_filename(
                self.document_ids[0].name, tool_config
            )
        else:
            output_filename = f"merged_{self.tool}.{tool_config['output_extension']}"

        # Get folder from first document
        folder_id = self.document_ids[0].folder_id.id if self.document_ids[0].folder_id else False

        # Create new document with result
        new_document = self.env['documents.document'].create({
            'name': output_filename,
            'datas': base64.b64encode(result_content),
            'mimetype': self._get_output_mimetype(tool_config['output_extension']),
            'folder_id': folder_id,
            'owner_id': self.env.user.id,
        })

        # Post message in chatter of original document(s)
        tool_name = ILOVEPDF_TOOLS[self.tool]['name']
        for document in self.document_ids:
            body = Markup(
                '<p>Processed with <b>ILovePDF - %s</b></p>'
                '<p>Result: <a href="/documents/%s">%s</a></p>'
            ) % (tool_name, new_document.id, new_document.name)
            document.message_post(
                body=body,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

        _logger.info('Created new document: %s (ID: %d)', new_document.name, new_document.id)

        # Just close the wizard (no redirect)
        return {'type': 'ir.actions.act_window_close'}
