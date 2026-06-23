import base64
import json
import logging
import time
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    """Extended report model with Carbone.io integration.
    
    This model extends ir.actions.report to add support for Carbone.io
    reporting engine with full API v5 features support.
    """
    
    _inherit = "ir.actions.report"

    report_type = fields.Selection(
        selection_add=[("carbone", "Carbone")],
        ondelete={"carbone": "set default"}
    )

    # Template Source Selection
    carbone_template_source = fields.Selection(
        string="Template Source",
        selection=[
            ('upload', 'Upload File'),
        ],
        default='upload',
        help="Choose where the template file comes from.\n"
             "Upload: manually upload a template file.\n"
             "Additional options may be available with other modules."
    )

    # Template and Data
    carbone_template_file = fields.Binary(
        string='Carbone Template',
        help="Upload the Carbone template file (DOCX, XLSX, ODT, ODS, etc.)"
    )
    carbone_template_filename = fields.Char(
        string='Template Filename',
        help="Original filename of the uploaded template"
    )
    carbone_json_data = fields.Text(
        string='Carbone JSON Data',
        help="Python code to prepare JSON data for Carbone rendering. "
             "Use 'object' variable to access the record."
    )

    # HTML Template (alternative to file upload)
    carbone_use_html_template = fields.Boolean(
        string='Use HTML Template',
        default=False,
        help="Use the HTML template below instead of uploading a file."
    )
    carbone_html_template = fields.Html(
        string='HTML Template',
        sanitize=False,  # Allow all HTML including Carbone tags
        help="HTML template with Carbone placeholders like {d.name}, {d.email}. "
             "Use standard HTML/CSS for formatting."
    )

    # Output Configuration
    carbone_report_type = fields.Selection(
        string="Output Format",
        selection=[
            ("pdf", "PDF"),
            ("docx", "Microsoft Word (DOCX)"),
            ("xlsx", "Microsoft Excel (XLSX)"),
            ("odt", "LibreOffice/OpenOffice Document (ODT)"),
            ("ods", "LibreOffice/OpenOffice Spreadsheet (ODS)"),
            ("csv", "CSV"),
            ("jpg", "Image (JPG)"),
            ("png", "Image (PNG)"),
        ],
        default="pdf",
        help="Output format for the generated report"
    )

    # PDF Options
    carbone_pdf_watermark = fields.Char(
        string="PDF Watermark",
        help="Text to display as watermark on PDF output."
    )
    carbone_pdf_encrypt = fields.Boolean(
        string="Encrypt PDF",
        help="Enable PDF encryption with password protection."
    )
    carbone_pdf_open_password = fields.Char(
        string="Open Password",
        help="Password required to open the PDF document."
    )
    carbone_pdf_permission_password = fields.Char(
        string="Permission Password",
        help="Password required to modify the PDF document."
    )
    carbone_pdf_version = fields.Selection(
        string="PDF Version",
        selection=[
            ("0", "PDF 1.4"),
            ("1", "PDF 1.5"),
            ("2", "PDF 1.6"),
            ("3", "PDF 1.7"),
            ("15", "PDF/A-1b"),
            ("16", "PDF/A-2b"),
        ],
        help="PDF version for compliance. Use PDF/A for legal archiving."
    )
    carbone_pdf_quality = fields.Integer(
        string="PDF Quality",
        default=90,
        help="Image quality for PDF (1-100). Lower values reduce file size."
    )
    carbone_pdf_max_resolution = fields.Selection(
        string="Max Image Resolution",
        selection=[
            ("75", "75 DPI (Screen)"),
            ("150", "150 DPI (Low)"),
            ("300", "300 DPI (Print)"),
            ("600", "600 DPI (High)"),
            ("1200", "1200 DPI (Very High)"),
        ],
        help="Maximum resolution for images in PDF. Lower values reduce file size."
    )

    # CSV Options
    carbone_csv_separator = fields.Char(
        string="Field Separator",
        default=",",
        help="Character to separate fields in CSV output (default: comma)."
    )
    carbone_csv_delimiter = fields.Char(
        string="Text Delimiter",
        default='"',
        help="Character to delimit text fields in CSV output (default: double quote)."
    )
    carbone_csv_charset = fields.Selection(
        string="CSV Charset",
        selection=[
            ("0", "System default"),
            ("76", "UTF-8"),
            ("1", "Windows-1252"),
        ],
        default="76",
        help="Character encoding for CSV output."
    )

    # Image Options (JPG/PNG)
    carbone_image_width = fields.Integer(
        string="Image Width",
        help="Width in pixels for image output. Leave empty for default."
    )
    carbone_image_height = fields.Integer(
        string="Image Height",
        help="Height in pixels for image output. Leave empty for default."
    )
    carbone_image_quality = fields.Integer(
        string="Image Quality (JPG)",
        default=85,
        help="Quality for JPG images (1-100). Higher values = better quality, larger file."
    )
    carbone_image_compression = fields.Integer(
        string="Compression (PNG)",
        default=6,
        help="Compression level for PNG images (0-9). Higher values = smaller file, slower."
    )

    # Carbone v5 Options
    carbone_converter = fields.Selection(
        string="Converter",
        selection=[
            ('L', 'LibreOffice'),
            ('O', 'OnlyOffice'),
            ('C', 'Chromium'),
        ],
        help="Converter engine to use for rendering. If not set, uses Carbone default (LibreOffice)."
    )
    carbone_timezone = fields.Selection(
        string="Timezone",
        selection=lambda self: self._get_timezone_selection(),
        help="Timezone for date/time formatting in the report"
    )
    carbone_lang = fields.Selection(
        string="Language",
        selection=lambda self: self._get_carbone_lang_selection(),
        help="Language code for formatting (numbers, dates, currencies). "
             "Languages are loaded from Odoo installed languages."
    )
    carbone_complement_data = fields.Text(
        string='Complement Data',
        help="Additional JSON data accessible via {c.} tags in template"
    )
    carbone_enum_mappings = fields.Text(
        string='Enum Mappings',
        help="JSON object with enum mappings for :convEnum() formatter"
    )
    carbone_translations = fields.Text(
        string='Translations (JSON)',
        help="JSON object with translations for multi-language reports. "
             "Format: {\"en-us\": {\"key\": \"value\"}, \"it-it\": {\"key\": \"valore\"}}. "
             "If translation lines are configured below, they take precedence."
    )
    carbone_translation_ids = fields.One2many(
        "carbone.translation",
        "report_id",
        string="Translation Lines",
        help="Manage translations using Odoo's standard translation system. "
             "Use {t(key)} tags in the template.",
    )
    carbone_use_partner_lang = fields.Boolean(
        string='Use Partner Language',
        default=True,
        help="Automatically use the partner's language for the report. "
             "Falls back to report language setting if partner has no language."
    )

    # Currency Conversion
    carbone_currency_source = fields.Many2one(
        'res.currency',
        string='Source Currency',
        help="Currency of the source data. Used with :formatC() formatter for conversion."
    )
    carbone_currency_target = fields.Many2one(
        'res.currency',
        string='Target Currency',
        help="Target currency for conversion. If not set, uses source currency."
    )
    carbone_currency_rates = fields.Text(
        string='Custom Exchange Rates',
        help="JSON object with custom exchange rates. Format: {\"EUR\": 1, \"USD\": 1.10, \"GBP\": 0.85}. "
             "If empty, Carbone uses its built-in rates."
    )

    # Template Organization
    carbone_category = fields.Char(
        string='Carbone Category',
        help="Category for organizing templates on Carbone server (like a folder)"
    )
    carbone_comment = fields.Char(
        string='Carbone Comment',
        help="Comment or description for the template on Carbone server"
    )

    # Template Caching
    carbone_template_id = fields.Char(
        string='Cached Template ID',
        readonly=True,
        help="Carbone template ID from previous upload (for caching)"
    )
    carbone_use_template_cache = fields.Boolean(
        string='Use Template Cache',
        default=True,
        help="If enabled, uploads template only once and reuses the template ID"
    )
    
    # Async Rendering
    carbone_rendering_mode = fields.Selection(
        string="Rendering Mode",
        selection=[
            ('sync', 'Synchronous'),
            ('async', 'Asynchronous (Webhook)'),
        ],
        default='sync',
        help="Sync: blocks UI until report is ready (max 60s). "
             "Async: uses webhook for long reports (max 5 min), allows user to continue working."
    )
    carbone_webhook_timeout = fields.Integer(
        string='Webhook Timeout',
        default=300,
        help="Timeout in seconds for async rendering (default: 300s = 5 minutes)"
    )

    # Batch Processing
    carbone_batch_output = fields.Selection(
        string="Batch Output",
        selection=[
            ('pdf', 'Merged PDF (single file)'),
            ('zip', 'ZIP Archive (separate files)'),
        ],
        default='pdf',
        help="When printing multiple records:\n"
             "- Merged PDF: All reports combined into a single PDF file\n"
             "- ZIP Archive: Each report as a separate file in a ZIP archive"
    )

    # Format compatibility mapping: template_extension -> allowed output formats
    CARBONE_FORMAT_COMPATIBILITY = {
        # Document formats (ODT, DOCX, DOC) - can also export to images
        'odt': ['pdf', 'docx', 'odt', 'txt', 'html', 'jpg', 'png'],
        'docx': ['pdf', 'docx', 'odt', 'txt', 'html', 'jpg', 'png'],
        'doc': ['pdf', 'docx', 'odt', 'txt', 'html', 'jpg', 'png'],
        # Spreadsheet formats (ODS, XLSX, XLS)
        'ods': ['pdf', 'xlsx', 'ods', 'csv', 'jpg', 'png'],
        'xlsx': ['pdf', 'xlsx', 'ods', 'csv', 'jpg', 'png'],
        'xls': ['pdf', 'xlsx', 'ods', 'csv', 'jpg', 'png'],
        # Presentation formats (ODP, PPTX, PPT)
        'odp': ['pdf', 'pptx', 'odp', 'jpg', 'png'],
        'pptx': ['pdf', 'pptx', 'odp', 'jpg', 'png'],
        'ppt': ['pdf', 'pptx', 'odp', 'jpg', 'png'],
        # Drawing formats (ODG)
        'odg': ['pdf', 'svg', 'png', 'jpg'],
        # HTML
        'html': ['pdf', 'html', 'jpg', 'png'],
        'htm': ['pdf', 'html', 'jpg', 'png'],
    }

    def _has_carbone_template(self):
        """Check if a Carbone template is configured.

        This method can be overridden by bridge modules (gdrive, sharepoint)
        to add support for external template sources.

        Returns:
            bool: True if a template is configured
        """
        self.ensure_one()
        return bool(self.carbone_template_file) or (
            self.carbone_use_html_template and self.carbone_html_template
        )

    def _get_carbone_template_filename(self):
        """Get the template filename.

        This method can be overridden by bridge modules (gdrive, sharepoint)
        to return the filename from external sources.

        Returns:
            str: Template filename or None
        """
        self.ensure_one()
        if self.carbone_use_html_template and self.carbone_html_template:
            return f"{self.name}.html"
        return self.carbone_template_filename

    def _get_carbone_template_data(self):
        """Get the template data for upload.

        This method can be overridden by bridge modules (gdrive, sharepoint)
        to return template data from external sources.

        Returns:
            tuple: (template_data_base64, template_name) or (None, None)
        """
        self.ensure_one()

        if self.carbone_use_html_template and self.carbone_html_template:
            # Use HTML template
            html_content = self.carbone_html_template
            if isinstance(html_content, bytes):
                html_content = html_content.decode('utf-8')

            if not html_content.strip().lower().startswith('<!doctype') and not html_content.strip().lower().startswith('<html'):
                html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>'''
            elif not html_content.strip().lower().startswith('<!doctype'):
                html_content = '<!DOCTYPE html>\n' + html_content

            html_bytes = html_content.encode('utf-8')
            template_data = base64.b64encode(html_bytes).decode('utf-8')
            template_name = f"{self.name}.html"
            return template_data, template_name

        elif self.carbone_template_file:
            # Use uploaded file
            template_data = self.carbone_template_file
            if isinstance(template_data, bytes):
                template_data = template_data.decode('utf-8')
            template_name = self.carbone_template_filename or f"{self.name}.odt"
            return template_data, template_name

        return None, None

    def _get_template_extension(self):
        """Get template file extension.

        Returns:
            str: Lowercase file extension without dot, or None if no template
        """
        self.ensure_one()
        filename = self._get_carbone_template_filename()
        if not filename:
            return None
        if '.' in filename:
            return filename.lower().rsplit('.', 1)[1]
        return None

    def _get_allowed_output_formats(self):
        """Get allowed output formats based on template type.

        Returns:
            list: List of allowed output format codes, or all formats if unknown
        """
        self.ensure_one()
        ext = self._get_template_extension()
        if ext and ext in self.CARBONE_FORMAT_COMPATIBILITY:
            return self.CARBONE_FORMAT_COMPATIBILITY[ext]
        # If unknown template type, allow all formats (Carbone will validate)
        return ['pdf', 'docx', 'xlsx', 'odt', 'ods', 'csv', 'jpg', 'png']

    def _validate_format_compatibility(self):
        """Validate that output format is compatible with template type.

        Raises:
            ValidationError: If output format is not compatible with template
        """
        self.ensure_one()
        ext = self._get_template_extension()
        if not ext:
            return  # No template yet, skip validation

        output_format = self.carbone_report_type or 'pdf'
        allowed = self._get_allowed_output_formats()

        if output_format not in allowed:
            # Build user-friendly error message
            ext_upper = ext.upper()
            format_upper = output_format.upper()
            allowed_str = ', '.join([f.upper() for f in allowed])
            raise ValidationError(_(
                "Cannot convert %(ext)s template to %(format)s format.\n\n"
                "Templates with extension .%(ext_lower)s can only be converted to: %(allowed)s\n\n"
                "Tip: To export as CSV, use a spreadsheet template (XLSX or ODS)."
            ) % {
                'ext': ext_upper,
                'format': format_upper,
                'ext_lower': ext,
                'allowed': allowed_str,
            })

    @api.constrains('carbone_report_type', 'carbone_template_filename')
    def _check_format_compatibility(self):
        """Constraint to validate format compatibility when saving."""
        for report in self:
            if report.report_type == 'carbone' and report.carbone_template_filename:
                report._validate_format_compatibility()

    @api.model
    def _get_timezone_selection(self):
        """Get available timezone list for selection field.

        Returns:
            list: List of (value, label) tuples for timezone selection
        """
        import pytz
        return [(tz, tz) for tz in pytz.common_timezones]

    @api.model
    def _get_carbone_lang_selection(self):
        """Get available languages from Odoo res.lang in Carbone format.

        Converts Odoo language codes (it_IT) to Carbone format (it-it).

        Returns:
            list: List of (carbone_code, name) tuples for language selection
        """
        langs = self.env['res.lang'].search([('active', '=', True)])
        result = []
        for lang in langs:
            # Convert Odoo format (it_IT) to Carbone format (it-it)
            carbone_code = lang.code.lower().replace('_', '-')
            result.append((carbone_code, lang.name))
        return result

    def _build_convert_to_options(self):
        """Build the convertTo parameter with format-specific options.

        Returns:
            str or dict: Simple format string or dict with formatName and formatOptions
        """
        self.ensure_one()
        output_format = self.carbone_report_type
        format_options = {}

        # PDF Options
        if output_format == 'pdf':
            if self.carbone_pdf_watermark:
                format_options['Watermark'] = self.carbone_pdf_watermark
            if self.carbone_pdf_encrypt:
                format_options['EncryptFile'] = True
                if self.carbone_pdf_open_password:
                    format_options['DocumentOpenPassword'] = self.carbone_pdf_open_password
                if self.carbone_pdf_permission_password:
                    format_options['PermissionPassword'] = self.carbone_pdf_permission_password
            if self.carbone_pdf_version:
                format_options['SelectPdfVersion'] = int(self.carbone_pdf_version)
            if self.carbone_pdf_quality and self.carbone_pdf_quality != 90:
                format_options['Quality'] = self.carbone_pdf_quality
            if self.carbone_pdf_max_resolution:
                format_options['MaxImageResolution'] = int(self.carbone_pdf_max_resolution)

        # CSV Options
        elif output_format == 'csv':
            if self.carbone_csv_separator and self.carbone_csv_separator != ',':
                format_options['fieldSeparator'] = self.carbone_csv_separator
            if self.carbone_csv_delimiter and self.carbone_csv_delimiter != '"':
                format_options['textDelimiter'] = self.carbone_csv_delimiter
            if self.carbone_csv_charset:
                format_options['characterSet'] = self.carbone_csv_charset

        # JPG Options
        elif output_format == 'jpg':
            if self.carbone_image_width:
                format_options['PixelWidth'] = self.carbone_image_width
            if self.carbone_image_height:
                format_options['PixelHeight'] = self.carbone_image_height
            if self.carbone_image_quality and self.carbone_image_quality != 85:
                format_options['Quality'] = self.carbone_image_quality

        # PNG Options
        elif output_format == 'png':
            if self.carbone_image_width:
                format_options['PixelWidth'] = self.carbone_image_width
            if self.carbone_image_height:
                format_options['PixelHeight'] = self.carbone_image_height
            if self.carbone_image_compression and self.carbone_image_compression != 6:
                format_options['Compression'] = self.carbone_image_compression

        # Return simple format or dict with options
        if format_options:
            return {
                'formatName': output_format,
                'formatOptions': format_options
            }
        return output_format

    def _get_partner_lang_from_recordset(self, recordset):
        """Get partner language from recordset in Carbone format.

        Tries to find a partner on the record and returns their language
        converted to Carbone format (e.g., 'it_IT' -> 'it-it').

        Args:
            recordset: Odoo recordset to check for partner

        Returns:
            str: Language code in Carbone format (e.g., 'it-it') or None
        """
        if not recordset:
            return None

        record = recordset[0] if len(recordset) > 1 else recordset
        partner = None

        # Try common partner field names
        for field_name in ['partner_id', 'partner_shipping_id', 'commercial_partner_id']:
            if hasattr(record, field_name):
                partner = getattr(record, field_name)
                if partner and partner.lang:
                    break

        # If record itself is a partner
        if not partner and record._name == 'res.partner' and record.lang:
            partner = record

        if partner and partner.lang:
            # Convert Odoo lang (it_IT) to Carbone format (it-it)
            odoo_lang = partner.lang
            carbone_lang = odoo_lang.lower().replace('_', '-')
            _logger.debug(f"Detected partner language: {odoo_lang} -> {carbone_lang}")
            return carbone_lang

        return None

    def _validate_carbone_config(self):
        """Validate Carbone configuration before rendering.

        Raises:
            ValidationError: If configuration is invalid
        """
        self.ensure_one()

        company = self.env.user.company_id

        if not company.carbone_api_url:
            raise ValidationError(_(
                "Carbone API URL is not configured. "
                "Please configure it in Settings > Reporting Tools."
            ))

        if not company.carbone_access_token:
            raise ValidationError(_(
                "Carbone Access Token is not configured. "
                "Please configure it in Settings > Reporting Tools."
            ))

        # Check for template using generic method (can be overridden by bridge modules)
        if not self._has_carbone_template():
            raise ValidationError(_(
                "Carbone template is not configured for report '%s'. "
                "Please upload a template file or configure an external source."
            ) % self.name)

        if not self.carbone_json_data:
            raise ValidationError(_(
                "Carbone JSON data is not configured for report '%s'."
            ) % self.name)

        # Validate format compatibility
        self._validate_format_compatibility()

        _logger.debug(f"Carbone configuration validated for report: {self.name}")
    
    def _prepare_carbone_headers(self, include_auth=True, content_type=None):
        """Prepare HTTP headers for Carbone API requests.
        
        Args:
            include_auth (bool): Whether to include Authorization header
            content_type (str): Content-Type header value
            
        Returns:
            dict: HTTP headers dictionary
        """
        company = self.env.user.company_id
        headers = {
            'carbone-version': '5',
            'Accept': 'application/json',
        }
        
        if content_type:
            headers['Content-Type'] = content_type
        
        if include_auth and company.carbone_access_token:
            headers['Authorization'] = f'Bearer {company.carbone_access_token}'
        
        return headers
    
    def _upload_template(self):
        """Upload template to Carbone API and cache template ID.

        Returns:
            str: Template ID from Carbone API

        Raises:
            UserError: If template upload fails
        """
        self.ensure_one()
        company = self.env.user.company_id

        # Check if we can use cached template (but not for HTML templates which may change)
        if self.carbone_use_template_cache and self.carbone_template_id and not self.carbone_use_html_template:
            _logger.info(f"Using cached template ID: {self.carbone_template_id}")
            return self.carbone_template_id

        _logger.info(f"Uploading template for report: {self.name}")

        # Get template data using generic method (can be overridden by bridge modules)
        template_data, template_name = self._get_carbone_template_data()

        if not template_data:
            raise UserError(_("No template data available for report '%s'.") % self.name)

        _logger.info(f"Using template: {template_name}")

        try:

            payload = {
                'template': template_data,
                'name': template_name,
            }

            # Add tag from company settings
            if company.carbone_template_tag:
                payload['tags'] = [company.carbone_template_tag]

            # Add category from report
            if self.carbone_category:
                payload['category'] = self.carbone_category

            # Add comment from report
            if self.carbone_comment:
                payload['comment'] = self.carbone_comment

            response = requests.post(
                f'{company.carbone_api_url}/template',
                headers=self._prepare_carbone_headers(content_type='application/json'),
                json=payload,
                timeout=30
            )

            response.raise_for_status()

            result = response.json()
            template_id = result.get('data', {}).get('templateId')

            if not template_id:
                raise UserError(_(
                    "Invalid response from Carbone API: missing templateId"
                ))

            # Cache template ID if caching is enabled
            if self.carbone_use_template_cache:
                self.sudo().write({'carbone_template_id': template_id})
                _logger.info(f"Template cached with ID: {template_id}")

            return template_id

        except requests.exceptions.Timeout:
            _logger.error("Template upload timeout")
            raise UserError(_(
                "Template upload timeout. Please check your connection and try again."
            ))
        except requests.exceptions.RequestException as e:
            _logger.error(f"Template upload failed: {str(e)}", exc_info=True)
            raise UserError(_(
                "Failed to upload template to Carbone API.\n\nError: %s"
            ) % str(e))
    
    def _prepare_render_payload(self, recordset):
        """Prepare JSON payload for Carbone rendering.
        
        Args:
            recordset: Odoo recordset to render
            
        Returns:
            dict: Render payload for Carbone API
        """
        self.ensure_one()
        
        _logger.debug(f"Preparing render data for {len(recordset)} record(s)")
        
        # Prepare main data
        try:
            if len(recordset) > 1:
                # Multi-record rendering: create array of objects
                items = []
                for rec in recordset:
                    item_data = safe_eval(
                        self.carbone_json_data.replace('\n', ''),
                        {"object": rec}
                    )
                    # Add _filename from print_report_name for batch ZIP naming
                    if self.print_report_name:
                        try:
                            from odoo.tools.safe_eval import datetime, dateutil, time as safe_time
                            filename = safe_eval(
                                self.print_report_name,
                                {"object": rec, "time": safe_time, "datetime": datetime, "dateutil": dateutil}
                            )
                            item_data['reportFilename'] = filename
                            _logger.debug(f"Filename for record {rec.id}: {filename}")
                        except Exception as e:
                            _logger.warning(f"Error evaluating print_report_name: {e}")
                    items.append(item_data)

                # Wrap in 'items' array for Carbone loop: {d.items[i].field}
                data = {'items': items}
                _logger.debug(f"Multi-record data prepared: {len(items)} items")
            else:
                # Single record rendering: use data directly
                data = safe_eval(
                    self.carbone_json_data.replace('\n', ''),
                    {"object": recordset}
                )
                _logger.debug(f"Single record data prepared")
        except Exception as e:
            _logger.error(f"Error evaluating JSON data: {str(e)}", exc_info=True)
            raise UserError(_(
                "Error preparing report data.\n\nError: %s"
            ) % str(e))
        
        # Build payload with v5 options
        payload = {
            'data': data,
        }

        # Handle convertTo with format options
        payload['convertTo'] = self._build_convert_to_options()

        # Enable batch processing for multiple records
        if len(recordset) > 1:
            payload['batchSplitBy'] = 'd.items'
            batch_output = self.carbone_batch_output or 'pdf'
            payload['batchOutput'] = batch_output
            # Use reportFilename from data for ZIP file naming
            if self.print_report_name:
                payload['reportName'] = '{d.reportFilename}'
            _logger.debug(f"Batch processing enabled for {len(recordset)} records, output: {batch_output}")

        # Add optional v5 parameters
        if self.carbone_converter:
            payload['converter'] = self.carbone_converter
        
        if self.carbone_timezone:
            payload['timezone'] = self.carbone_timezone
        
        if self.carbone_lang:
            payload['lang'] = self.carbone_lang
        
        # Add complement data if provided
        if self.carbone_complement_data:
            try:
                complement = safe_eval(
                    self.carbone_complement_data.replace('\n', ''),
                    {"object": recordset}
                )
                payload['complement'] = complement
            except Exception as e:
                _logger.warning(f"Error evaluating complement data: {str(e)}")
        
        # Add enum mappings if provided
        if self.carbone_enum_mappings:
            try:
                enum_data = json.loads(self.carbone_enum_mappings)
                payload['enum'] = enum_data
            except json.JSONDecodeError as e:
                _logger.warning(f"Invalid enum mappings JSON: {str(e)}")

        # Add translations: structured lines take precedence over JSON field
        if self.carbone_translation_ids:
            translations_data = self.env["carbone.translation"].get_translations_for_report(self.id)
            if translations_data:
                payload['translations'] = translations_data
        elif self.carbone_translations:
            try:
                translations_data = json.loads(self.carbone_translations)
                payload['translations'] = translations_data
            except json.JSONDecodeError as e:
                _logger.warning(f"Invalid translations JSON: {str(e)}")

        # Add currency conversion options
        if self.carbone_currency_source:
            payload['currencySource'] = self.carbone_currency_source.name
        if self.carbone_currency_target:
            payload['currencyTarget'] = self.carbone_currency_target.name
        if self.carbone_currency_rates:
            try:
                rates_data = json.loads(self.carbone_currency_rates)
                payload['currencyRates'] = rates_data
            except json.JSONDecodeError as e:
                _logger.warning(f"Invalid currency rates JSON: {str(e)}")

        # Auto-detect partner language if enabled
        _logger.info(f"carbone_use_partner_lang = {self.carbone_use_partner_lang}, carbone_lang = {self.carbone_lang}")
        if self.carbone_use_partner_lang:
            partner_lang = self._get_partner_lang_from_recordset(recordset)
            if partner_lang:
                payload['lang'] = partner_lang
                _logger.info(f"Using partner language: {partner_lang}")
        else:
            _logger.info(f"Partner language detection disabled, using fallback: {self.carbone_lang}")

        _logger.info(f"Render payload prepared: {len(json.dumps(payload))} bytes")
        _logger.info(f"Payload content: {json.dumps(payload, indent=2)}")
        return payload
    
    @api.model
    def _render_carbone(self, report_ref, docids, data):
        """Render report using Carbone.io API v5.
        
        This method implements synchronous rendering using the Carbone v5 API.
        For asynchronous rendering with webhooks, see _render_carbone_async().
        
        Args:
            report_ref: Report reference (name or id)
            docids: Document IDs as comma-separated string
            data: Additional data (not used currently)
            
        Returns:
            tuple: (report_content, report_format) or 'async' for async mode
            
        Raises:
            UserError: If rendering fails
        """
        company = self.env.user.company_id
        report = self._get_report(report_ref)
        
        # Check if async rendering is enabled
        if report.carbone_rendering_mode == 'async':
            return report._render_carbone_async(report_ref, docids, data)
        
        _logger.info(f"Starting Carbone report rendering: {report.name}")
        
        try:
            # Validate configuration
            report._validate_carbone_config()
            
            # Parse document IDs
            record_ids = [int(d) for d in docids.split(',')]
            recordset = self.env[report.model].browse(record_ids)
            
            _logger.debug(f"Rendering {len(recordset)} record(s) of model {report.model}")
            
            # Upload template (or use cached)
            template_id = report._upload_template()
            
            # Prepare render payload
            payload = report._prepare_render_payload(recordset)
            
            # Step 1: POST /render/{templateId} to start rendering
            _logger.debug(f"Sending render request to Carbone API")
            
            render_response = requests.post(
                f'{company.carbone_api_url}/render/{template_id}',
                headers=report._prepare_carbone_headers(content_type='application/json'),
                json=payload,
                timeout=60
            )
            
            render_response.raise_for_status()
            
            # Step 2: Extract renderId from response
            render_result = render_response.json()
            render_id = render_result.get('data', {}).get('renderId')
            
            if not render_id:
                raise UserError(_(
                    "Invalid response from Carbone API: missing renderId"
                ))
            
            _logger.debug(f"Render started, renderId: {render_id}")
            
            # Step 3: GET /render/{renderId} to retrieve the actual PDF
            retrieve_response = requests.get(
                f'{company.carbone_api_url}/render/{render_id}',
                headers=report._prepare_carbone_headers(),
                timeout=60
            )
            
            retrieve_response.raise_for_status()
            
            _logger.info(
                f"Report rendered successfully: {report.name} "
                f"({len(retrieve_response.content)} bytes)"
            )

            # Log success
            report._log_report_request(record_ids, success=True)

            # Determine output format: ZIP for batch zip output, otherwise original format
            output_format = report.carbone_report_type
            if len(recordset) > 1 and report.carbone_batch_output == 'zip':
                output_format = 'zip'

            content = retrieve_response.content
            # Draw full-height vector column rules over the body when configured
            if output_format == 'pdf' and report.report_overlay:
                content = report._apply_report_overlay(content)

            return content, output_format

        except ValidationError:
            # Re-raise validation errors as-is
            raise
        except requests.exceptions.Timeout:
            _logger.error("Carbone render request timeout")
            report._log_report_request(record_ids, success=False)
            raise UserError(_(
                "Report rendering timeout. "
                "For large reports, consider using asynchronous mode."
            ))
        except requests.exceptions.HTTPError as e:
            error_msg = str(e)
            is_batch_error = False
            is_converter_error = False
            try:
                error_detail = e.response.json()
                error_msg = error_detail.get('error', error_msg)
                # Check if it's a batch processing error
                if 'Batch processing deactivated' in error_msg or 'nbReportMaxPerBatch' in error_msg:
                    is_batch_error = True
                # Check if it's a converter unavailable error
                if 'disabled or unavailable' in error_msg or 'converter' in error_msg.lower():
                    is_converter_error = True
            except:
                pass
            
            # If batch processing is not available and we have multiple records, fallback to individual rendering
            if is_batch_error and len(recordset) > 1:
                _logger.warning(f"Batch processing not available, falling back to individual rendering")
                return report._render_carbone_individual(recordset, template_id, record_ids)

            # Handle converter unavailable error with user-friendly message
            if is_converter_error:
                converter_name = report.carbone_converter or 'default'
                _logger.error(f"Converter '{converter_name}' not available: {error_msg}")
                report._log_report_request(record_ids, success=False)
                raise UserError(_(
                    "The converter '%(converter)s' is not available on the Carbone server.\n\n"
                    "Please go to the report settings (Carbone Options tab) and either:\n"
                    "- Select a different converter (LibreOffice is usually available)\n"
                    "- Leave the converter field empty to use the server default\n\n"
                    "Technical details: %(error)s"
                ) % {'converter': converter_name, 'error': error_msg})

            _logger.error(f"Carbone API error: {error_msg}", exc_info=True)
            report._log_report_request(record_ids, success=False)
            raise UserError(_(
                "Carbone API error: %s"
            ) % error_msg)
        except Exception as e:
            _logger.error(f"Unexpected error during Carbone rendering: {str(e)}", exc_info=True)
            report._log_report_request(record_ids, success=False)
            raise UserError(_(
                "Unexpected error during report generation.\n\nError: %s"
            ) % str(e))

    def _render_carbone_individual(self, recordset, template_id, record_ids):
        """Fallback method to render reports individually when batch is not available.
        
        Args:
            recordset: Odoo recordset to render
            template_id: Carbone template ID
            record_ids: List of record IDs
            
        Returns:
            tuple: (merged_pdf_content, report_format)
        """
        from io import BytesIO
        try:
            from PyPDF2 import PdfMerger
        except ImportError:
            try:
                from PyPDF2 import PdfFileMerger as PdfMerger
            except ImportError:
                raise UserError(_(
                    "PyPDF2 is required for multi-record reports but not installed. "
                    "Please install it or contact your administrator."
                ))
        
        company = self.env.user.company_id
        merger = PdfMerger()
        
        _logger.info(f"Rendering {len(recordset)} reports individually")
        
        try:
            for idx, record in enumerate(recordset, 1):
                _logger.debug(f"Rendering record {idx}/{len(recordset)}: {record.display_name}")
                
                # Prepare single record payload
                payload = {
                    'data': safe_eval(
                        self.carbone_json_data.replace('\n', ''),
                        {"object": record}
                    ),
                    'convertTo': self.carbone_report_type,
                }
                
                # Add optional parameters
                if self.carbone_converter:
                    payload['converter'] = self.carbone_converter
                if self.carbone_timezone:
                    payload['timezone'] = self.carbone_timezone
                if self.carbone_lang:
                    payload['lang'] = self.carbone_lang
                
                # Render single report
                render_response = requests.post(
                    f'{company.carbone_api_url}/render/{template_id}',
                    headers=self._prepare_carbone_headers(content_type='application/json'),
                    json=payload,
                    timeout=60
                )
                render_response.raise_for_status()
                
                render_result = render_response.json()
                render_id = render_result.get('data', {}).get('renderId')
                
                if not render_id:
                    raise UserError(_(
                        "Invalid response from Carbone API for record %s"
                    ) % record.display_name)
                
                # Retrieve PDF
                retrieve_response = requests.get(
                    f'{company.carbone_api_url}/render/{render_id}',
                    headers=self._prepare_carbone_headers(),
                    timeout=60
                )
                retrieve_response.raise_for_status()
                
                # Add to merger
                pdf_stream = BytesIO(retrieve_response.content)
                merger.append(pdf_stream)
                
                _logger.debug(f"Record {idx} rendered successfully ({len(retrieve_response.content)} bytes)")
            
            # Merge all PDFs
            output_stream = BytesIO()
            merger.write(output_stream)
            merger.close()
            
            merged_content = output_stream.getvalue()
            output_stream.close()
            
            _logger.info(
                f"All reports merged successfully: {self.name} "
                f"({len(recordset)} documents, {len(merged_content)} bytes)"
            )
            
            # Log success
            self._log_report_request(record_ids, success=True)
            
            return merged_content, self.carbone_report_type
            
        except Exception as e:
            _logger.error(f"Error during individual rendering: {str(e)}", exc_info=True)
            self._log_report_request(record_ids, success=False)
            raise UserError(_(
                "Error generating individual reports: %s"
            ) % str(e))
    
    @api.model
    def _render_carbone_async(self, report_ref, docids, data):
        """Render report asynchronously using Carbone webhook.
        Uses Carbone v5 webhook headers and a correlation request_id.
        """
        company = self.env.user.company_id
        report = self._get_report(report_ref)
        _logger.info(f"Starting async Carbone report rendering: {report.name}")
        try:
            report._validate_carbone_config()
            record_ids = [int(d) for d in docids.split(',')]
            recordset = self.env[report.model].browse(record_ids)
            _logger.debug(f"Async rendering {len(recordset)} record(s) of model {report.model}")

            # Upload template (or use cached)
            template_id = report._upload_template()

            # Prepare payload
            payload = report._prepare_render_payload(recordset)

            # Webhook URL and correlation id
            webhook_base = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            webhook_url = f"{webhook_base}/carbone/webhook"
            import uuid
            request_id = str(uuid.uuid4())
            _logger.debug(f"Webhook URL: {webhook_url}, request_id: {request_id}")

            # Headers with webhook
            headers = report._prepare_carbone_headers(content_type='application/json')
            headers['carbone-webhook-url'] = webhook_url
            headers['carbone-webhook-header-x-odoo-request-id'] = request_id

            # Start async rendering
            render_response = requests.post(
                f"{company.carbone_api_url}/render/{template_id}",
                headers=headers,
                json=payload,
                timeout=60,
            )
            render_response.raise_for_status()

            _logger.info("Async render started, awaiting webhook callback")

            # Track pending request
            self.env['carbone.async.render'].sudo().create({
                'name': request_id,  # placeholder until renderId arrives
                'request_id': request_id,
                'report_id': report.id,
                'user_id': self.env.user.id,
                'record_ids': docids,
                'model': report.model,
                'state': 'pending',
            })
            return 'async', None
        except ValidationError:
            raise
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            try:
                error_detail = e.response.json()
                error_msg = error_detail.get('error', error_msg)
            except Exception:
                pass
            _logger.error(f"Carbone async API error: {error_msg}", exc_info=True)
            raise UserError(_( "Carbone API error: %s" ) % error_msg)
        except Exception as e:
            _logger.error(f"Unexpected error during async rendering: {str(e)}", exc_info=True)
            raise UserError(_( "Unexpected error during async report setup.\n\nError: %s" ) % str(e))
    
    def action_invalidate_template_cache(self):
        """Invalidate cached Carbone template ID.

        This action forces the template to be re-uploaded on next render.
        Useful when template has been modified.
        """
        for report in self:
            if report.carbone_template_id:
                _logger.info(f"Invalidating template cache for report: {report.name}")
                report.write({'carbone_template_id': False})

    def _sync_template_metadata_to_carbone(self):
        """Sync template metadata (category, name) to Carbone server via PATCH."""
        self.ensure_one()

        if not self.carbone_template_id:
            return False

        company = self.env.user.company_id
        if not company.carbone_api_url:
            return False

        template_name = self.carbone_template_filename or f"{self.name}.odt"

        payload = {
            'name': template_name,
        }

        if self.carbone_category:
            payload['category'] = self.carbone_category

        # Add comment from report
        if self.carbone_comment:
            payload['comment'] = self.carbone_comment

        # Add tag from company settings
        if company.carbone_template_tag:
            payload['tags'] = [company.carbone_template_tag]

        try:
            response = requests.patch(
                f'{company.carbone_api_url}/template/{self.carbone_template_id}',
                headers=self._prepare_carbone_headers(content_type='application/json'),
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                _logger.info(f"Template metadata synced for: {self.name}")
                return True
            else:
                _logger.warning(f"Failed to sync template metadata: HTTP {response.status_code}")
                return False

        except Exception as e:
            _logger.warning(f"Failed to sync template metadata: {e}")
            return False

    def write(self, vals):
        """Override write to sync metadata and invalidate cache when needed."""
        # Invalidate template cache if template source changes
        template_fields = ['carbone_use_html_template', 'carbone_html_template', 'carbone_template_file']
        if any(f in vals for f in template_fields):
            # Clear cached template ID when template source changes
            if 'carbone_template_id' not in vals:
                vals['carbone_template_id'] = False
            _logger.info("Template source changed, invalidating cache")

        result = super().write(vals)

        # Sync to Carbone if category or comment changed and template is cached
        if 'carbone_category' in vals or 'carbone_comment' in vals:
            for report in self:
                if report.carbone_template_id and report.report_type == 'carbone':
                    report._sync_template_metadata_to_carbone()

        return result

    # --- Carbone Studio methods ---

    def action_save_template_from_studio(self, data_uri, extension):
        """Save template from Carbone Studio dataURI to the report."""
        self.ensure_one()
        if not data_uri:
            _logger.warning("Empty dataURI received from Carbone Studio")
            return False

        filename = self.carbone_template_filename or f"template.{extension}"
        if not filename.lower().endswith(f".{extension}"):
            name_part = filename.rsplit('.', 1)[0] if '.' in filename else filename
            filename = f"{name_part}.{extension}"

        self.write({
            'carbone_template_file': data_uri,
            'carbone_template_filename': filename,
            'carbone_template_id': False,
        })
        _logger.info(
            "Template saved from Carbone Studio for report: %s", self.name
        )
        return True

    def _get_sample_json_data(self):
        """Get sample JSON data for Studio preview."""
        self.ensure_one()
        if self.model:
            record = self.env[self.model].search([], limit=1)
            if record and self.carbone_json_data:
                try:
                    from odoo.tools.safe_eval import safe_eval
                    local_vars = {
                        'object': record,
                        'env': self.env,
                        'time': __import__('time'),
                    }
                    safe_eval(
                        self.carbone_json_data, local_vars,
                        mode='exec', nocopy=True,
                    )
                    return local_vars.get('result', {})
                except Exception as e:
                    _logger.warning(
                        "Failed to generate sample JSON data: %s", e
                    )
                    return {}
        return {}

    def action_open_in_studio(self):
        """Open wizard to select sample record, then open Carbone Studio."""
        self.ensure_one()
        if not self._has_carbone_template():
            raise UserError(_(
                "No template file configured. "
                "Upload a template or configure an external source."
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Open in Carbone Studio'),
            'res_model': 'carbone.studio.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_report_id': self.id,
            },
        }

    @api.model
    def _get_report_from_name(self, report_name):
        """Override to support Carbone report type detection.
        
        Args:
            report_name (str): Report name
            
        Returns:
            ir.actions.report: Report record
        """
        res = super()._get_report_from_name(report_name)
        if res:
            return res
        
        # Search for Carbone reports
        report_model = self.env["ir.actions.report"]
        context = self.env["res.users"].context_get()
        domain = [
            ('report_type', '=', 'carbone'),
            ('report_name', '=', report_name)
        ]
        
        report = report_model.with_context(**context).search(domain, limit=1)
        if report:
            _logger.debug(f"Found Carbone report: {report_name}")
        
        return report
