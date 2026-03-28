import base64
import logging
import requests
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# ILovePDF API endpoints
ILOVEPDF_API_URL = 'https://api.ilovepdf.com/v1'

# Tool definitions with supported input/output formats
ILOVEPDF_TOOLS = {
    'officepdf': {
        'name': 'Office to PDF',
        'description': 'Convert Office documents (DOCX, XLSX, PPTX) to PDF',
        'input_mimetypes': [
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/msword',
            'application/vnd.ms-excel',
            'application/vnd.ms-powerpoint',
            'application/vnd.oasis.opendocument.text',
            'application/vnd.oasis.opendocument.spreadsheet',
            'application/vnd.oasis.opendocument.presentation',
        ],
        'output_extension': 'pdf',
        'multi_file': False,
    },
    'imagepdf': {
        'name': 'Image to PDF',
        'description': 'Convert images to PDF',
        'input_mimetypes': ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/tiff'],
        'output_extension': 'pdf',
        'multi_file': True,
    },
    'pdfjpg': {
        'name': 'PDF to Image',
        'description': 'Convert PDF pages to images',
        'input_mimetypes': ['application/pdf'],
        'output_extension': 'zip',  # Multiple images returned as ZIP
        'multi_file': False,
    },
    'compress': {
        'name': 'Compress PDF',
        'description': 'Reduce PDF file size',
        'input_mimetypes': ['application/pdf'],
        'output_extension': 'pdf',
        'multi_file': False,
    },
    'merge': {
        'name': 'Merge PDFs',
        'description': 'Combine multiple PDFs into one',
        'input_mimetypes': ['application/pdf'],
        'output_extension': 'pdf',
        'multi_file': True,
        'min_files': 2,
    },
    'split': {
        'name': 'Split PDF',
        'description': 'Split PDF into separate files',
        'input_mimetypes': ['application/pdf'],
        'output_extension': 'zip',
        'multi_file': False,
    },
    'rotate': {
        'name': 'Rotate PDF',
        'description': 'Rotate PDF pages',
        'input_mimetypes': ['application/pdf'],
        'output_extension': 'pdf',
        'multi_file': False,
    },
    'watermark': {
        'name': 'Add Watermark',
        'description': 'Add text or image watermark to PDF',
        'input_mimetypes': ['application/pdf'],
        'output_extension': 'pdf',
        'multi_file': False,
    },
    'pagenumber': {
        'name': 'Add Page Numbers',
        'description': 'Add page numbers to PDF',
        'input_mimetypes': ['application/pdf'],
        'output_extension': 'pdf',
        'multi_file': False,
    },
    'unlock': {
        'name': 'Unlock PDF',
        'description': 'Remove password protection from PDF',
        'input_mimetypes': ['application/pdf'],
        'output_extension': 'pdf',
        'multi_file': False,
    },
    'protect': {
        'name': 'Protect PDF',
        'description': 'Add password protection to PDF',
        'input_mimetypes': ['application/pdf'],
        'output_extension': 'pdf',
        'multi_file': False,
    },
    'repair': {
        'name': 'Repair PDF',
        'description': 'Repair damaged PDF files',
        'input_mimetypes': ['application/pdf'],
        'output_extension': 'pdf',
        'multi_file': False,
    },
    'pdfa': {
        'name': 'Convert to PDF/A',
        'description': 'Convert PDF to PDF/A format for archiving',
        'input_mimetypes': ['application/pdf'],
        'output_extension': 'pdf',
        'multi_file': False,
    },
    'pdfocr': {
        'name': 'OCR PDF',
        'description': 'Apply OCR to scanned PDF documents',
        'input_mimetypes': ['application/pdf'],
        'output_extension': 'pdf',
        'multi_file': False,
    },
}


class ILovePDFWizard(models.TransientModel):
    _name = 'ilovepdf.wizard'
    _description = 'ILovePDF Processing Wizard'

    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments',
        required=True,
    )
    tool = fields.Selection(
        selection='_get_tool_selection',
        string='Operation',
        required=True,
    )
    tool_description = fields.Char(
        string='Description',
        compute='_compute_tool_description',
    )

    # Compress options
    compression_level = fields.Selection([
        ('extreme', 'Extreme (lowest quality)'),
        ('recommended', 'Recommended'),
        ('low', 'Low (best quality)'),
    ], string='Compression Level', default='recommended')

    # Rotate options
    rotation_angle = fields.Selection([
        ('90', '90° clockwise'),
        ('180', '180°'),
        ('270', '90° counter-clockwise'),
    ], string='Rotation', default='90')

    # Watermark options
    watermark_text = fields.Char(string='Watermark Text')
    watermark_position = fields.Selection([
        ('center', 'Center'),
        ('top', 'Top'),
        ('bottom', 'Bottom'),
    ], string='Watermark Position', default='center')

    # Protect options
    password = fields.Char(string='Password')

    # Page number options
    page_number_position = fields.Selection([
        ('bottom-center', 'Bottom Center'),
        ('bottom-right', 'Bottom Right'),
        ('bottom-left', 'Bottom Left'),
        ('top-center', 'Top Center'),
        ('top-right', 'Top Right'),
        ('top-left', 'Top Left'),
    ], string='Position', default='bottom-center')

    @api.model
    def _get_tool_selection(self):
        return [(key, val['name']) for key, val in ILOVEPDF_TOOLS.items()]

    @api.depends('tool')
    def _compute_tool_description(self):
        for record in self:
            if record.tool and record.tool in ILOVEPDF_TOOLS:
                record.tool_description = ILOVEPDF_TOOLS[record.tool]['description']
            else:
                record.tool_description = ''

    @api.onchange('tool')
    def _onchange_tool(self):
        """Validate selected files against tool requirements."""
        if not self.tool or not self.attachment_ids:
            return

        tool_config = ILOVEPDF_TOOLS.get(self.tool)
        if not tool_config:
            return

        # Check minimum files for multi-file operations
        min_files = tool_config.get('min_files', 1)
        if len(self.attachment_ids) < min_files:
            return {
                'warning': {
                    'title': _('Invalid Selection'),
                    'message': _('This operation requires at least %d files.') % min_files,
                }
            }

        # Check file types
        valid_mimetypes = tool_config['input_mimetypes']
        invalid_files = self.attachment_ids.filtered(
            lambda a: a.mimetype not in valid_mimetypes
        )
        if invalid_files:
            return {
                'warning': {
                    'title': _('Invalid File Type'),
                    'message': _('Some files are not supported for this operation: %s') %
                              ', '.join(invalid_files.mapped('name')),
                }
            }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            res['attachment_ids'] = [(6, 0, active_ids)]
        return res

    def _get_jwt_token(self):
        """Get JWT token from ILovePDF API authentication endpoint."""
        company = self.env.company
        if not company.ilovepdf_public_key:
            raise UserError(_(
                'ILovePDF API credentials not configured. '
                'Please go to Settings > Reporting Tools to configure them.'
            ))

        try:
            response = requests.post(
                f'{ILOVEPDF_API_URL}/auth',
                json={'public_key': company.ilovepdf_public_key},
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data['token']
        except requests.exceptions.RequestException as e:
            _logger.error('Failed to get ILovePDF auth token: %s', e)
            raise UserError(_('Failed to authenticate with ILovePDF: %s') % str(e))

    def _start_task(self, tool):
        """Start a new ILovePDF task."""
        token = self._get_jwt_token()
        headers = {'Authorization': f'Bearer {token}'}

        try:
            response = requests.get(
                f'{ILOVEPDF_API_URL}/start/{tool}',
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data['server'], data['task']
        except requests.exceptions.RequestException as e:
            _logger.error('Failed to start ILovePDF task: %s', e)
            raise UserError(_('Failed to start processing task: %s') % str(e))

    def _upload_file(self, server, task, attachment):
        """Upload a file to ILovePDF server."""
        token = self._get_jwt_token()
        headers = {'Authorization': f'Bearer {token}'}

        file_content = base64.b64decode(attachment.datas)

        try:
            response = requests.post(
                f'https://{server}/v1/upload',
                headers=headers,
                data={'task': task},
                files={'file': (attachment.name, file_content, attachment.mimetype)},
                timeout=120
            )
            response.raise_for_status()
            data = response.json()
            return data['server_filename']
        except requests.exceptions.RequestException as e:
            _logger.error('Failed to upload file to ILovePDF: %s', e)
            raise UserError(_('Failed to upload file: %s') % str(e))

    def _process_task(self, server, task, tool, files, options=None):
        """Process the uploaded files."""
        token = self._get_jwt_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

        payload = {
            'task': task,
            'tool': tool,
            'files': files,
        }
        if options:
            payload.update(options)

        try:
            response = requests.post(
                f'https://{server}/v1/process',
                headers=headers,
                json=payload,
                timeout=300
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error('Failed to process ILovePDF task: %s', e)
            raise UserError(_('Failed to process files: %s') % str(e))

    def _download_result(self, server, task):
        """Download the processed file."""
        token = self._get_jwt_token()
        headers = {'Authorization': f'Bearer {token}'}

        try:
            response = requests.get(
                f'https://{server}/v1/download/{task}',
                headers=headers,
                timeout=120
            )
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            _logger.error('Failed to download ILovePDF result: %s', e)
            raise UserError(_('Failed to download result: %s') % str(e))

    def _get_process_options(self):
        """Get tool-specific processing options."""
        options = {}

        if self.tool == 'compress':
            options['compression_level'] = self.compression_level

        elif self.tool == 'rotate':
            options['rotate'] = int(self.rotation_angle)

        elif self.tool == 'watermark':
            if self.watermark_text:
                options['text'] = self.watermark_text
                options['vertical_position'] = self.watermark_position

        elif self.tool == 'protect':
            if self.password:
                options['password'] = self.password

        elif self.tool == 'pagenumber':
            options['facing_pages'] = False
            position_parts = self.page_number_position.split('-')
            if len(position_parts) == 2:
                options['vertical_position'] = position_parts[0]
                options['horizontal_position'] = position_parts[1]

        return options

    def _get_output_filename(self, original_name, tool_config):
        """Generate output filename based on original name and tool."""
        name_without_ext = original_name.rsplit('.', 1)[0] if '.' in original_name else original_name
        output_ext = tool_config['output_extension']
        tool_suffix = ILOVEPDF_TOOLS[self.tool]['name'].replace(' ', '_').lower()
        return f"{name_without_ext}_{tool_suffix}.{output_ext}"

    def action_process(self):
        """Execute the ILovePDF processing."""
        self.ensure_one()

        if not self.attachment_ids:
            raise ValidationError(_('Please select at least one attachment.'))

        tool_config = ILOVEPDF_TOOLS.get(self.tool)
        if not tool_config:
            raise ValidationError(_('Invalid operation selected.'))

        # Validate file types
        valid_mimetypes = tool_config['input_mimetypes']
        for attachment in self.attachment_ids:
            if attachment.mimetype not in valid_mimetypes:
                raise ValidationError(_(
                    'File "%(name)s" is not supported for this operation. '
                    'Expected: %(types)s',
                    name=attachment.name,
                    types=', '.join(valid_mimetypes)
                ))

        # Validate minimum files
        min_files = tool_config.get('min_files', 1)
        if len(self.attachment_ids) < min_files:
            raise ValidationError(_(
                'This operation requires at least %d files.'
            ) % min_files)

        _logger.info('Starting ILovePDF %s for %d file(s)', self.tool, len(self.attachment_ids))

        # Start task
        server, task = self._start_task(self.tool)
        _logger.debug('Task started: server=%s, task=%s', server, task)

        # Upload files
        uploaded_files = []
        for attachment in self.attachment_ids:
            server_filename = self._upload_file(server, task, attachment)
            uploaded_files.append({
                'server_filename': server_filename,
                'filename': attachment.name,
            })
            _logger.debug('File uploaded: %s -> %s', attachment.name, server_filename)

        # Process
        options = self._get_process_options()
        process_result = self._process_task(server, task, self.tool, uploaded_files, options)
        _logger.debug('Process result: %s', process_result)

        # Download result
        result_content = self._download_result(server, task)
        _logger.info('Downloaded result: %d bytes', len(result_content))

        # Create new attachment with result
        if len(self.attachment_ids) == 1:
            output_filename = self._get_output_filename(
                self.attachment_ids[0].name, tool_config
            )
        else:
            output_filename = f"merged_{self.tool}.{tool_config['output_extension']}"

        new_attachment = self.env['ir.attachment'].create({
            'name': output_filename,
            'datas': base64.b64encode(result_content),
            'mimetype': self._get_output_mimetype(tool_config['output_extension']),
            'res_model': self.attachment_ids[0].res_model,
            'res_id': self.attachment_ids[0].res_id,
        })

        # Post message in chatter of original attachment(s)
        tool_name = ILOVEPDF_TOOLS[self.tool]['name']
        for attachment in self.attachment_ids:
            body = Markup(
                '<p>Processed with <b>ILovePDF - %s</b></p>'
                '<p>Result: <a href="/web/content/%s?download=true">%s</a></p>'
            ) % (tool_name, new_attachment.id, new_attachment.name)
            attachment.message_post(
                body=body,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

        _logger.info('Created new attachment: %s (ID: %d)', new_attachment.name, new_attachment.id)

        # Just close the wizard (no redirect)
        return {'type': 'ir.actions.act_window_close'}

    def _get_output_mimetype(self, extension):
        """Get MIME type for output file extension."""
        mimetypes = {
            'pdf': 'application/pdf',
            'zip': 'application/zip',
            'jpg': 'image/jpeg',
            'png': 'image/png',
        }
        return mimetypes.get(extension, 'application/octet-stream')
