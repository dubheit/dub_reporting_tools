# Carbone.io Reporting Module

Advanced document generation for Odoo 18.0 using Carbone.io API v5.

## Overview

This module integrates [Carbone.io](https://carbone.io) reporting engine with Odoo, providing powerful document generation capabilities with support for multiple output formats and advanced features.

## Features

### Core Functionality
- **Multiple Output Formats**: PDF, DOCX, XLSX, ODT, ODS
- **Carbone API v5**: Full support for latest Carbone features
- **Template Caching**: Upload templates once, reuse for better performance
- **Multi-Record Rendering**: Generate reports for multiple records in single document
- **Enhanced Error Handling**: Detailed error messages and comprehensive logging

### Carbone v5 Features
- **Converter Selection**: Choose between LibreOffice, OnlyOffice, or Chromium
- **Timezone Support**: Automatic timezone conversion for dates
- **Multi-Language**: Support for multiple language codes (en-us, fr-fr, it-it, etc.)
- **Complement Data**: Additional data accessible via `{c.}` tags
- **Enum Mappings**: Use `:convEnum()` formatter with custom mappings

### Advanced Features
- **Asynchronous Rendering**: Webhook-based async rendering for large reports (coming soon)
- **Carbone Studio Integration**: Live template editing (coming soon)
- **Comprehensive Logging**: Track all report generation activities
- **Validation**: Pre-render validation of configuration and templates

## Installation

### Prerequisites

1. **Odoo 18.0**
2. **dub_reporting_base** module (installed automatically)
3. **Carbone.io Account**: Get API access token at [account.carbone.io](https://account.carbone.io)
4. **Python Dependencies**: 
   ```bash
   pip install requests pytz
   ```

### Installation Steps

1. Clone or copy module to Odoo addons directory
2. Update module list in Odoo
3. Install "Reporting Tools - Carbone" module
4. Configure Carbone API credentials in Settings

## Configuration

### Basic Setup

1. Navigate to **Settings > Reporting Tools > Carbone.io Configuration**
2. Enter your configuration:
   - **API URL**: `https://api.carbone.io` (or your on-premise URL)
   - **Access Token**: Your API token from Carbone.io

### Default Options (Optional)

Configure default values for new reports:
- **Converter**: Default rendering engine (LibreOffice/OnlyOffice/Chromium)
- **Timezone**: Default timezone for date formatting
- **Language**: Default language code for number/date formatting

### Webhook Configuration (For Async Rendering)

- **Webhook Base URL**: Your Odoo instance URL (e.g., `https://yourdomain.com`)
- Leave empty to use `web.base.url` setting

## Creating Reports

### 1. Create Report Record

1. Navigate to **Settings > Technical > Actions > Reports**
2. Create new report or edit existing
3. Set **Report Type** to "Carbone"

### 2. Configure Report

#### Basic Configuration

- **Name**: Report display name
- **Model**: Odoo model to report on
- **Output Format**: Choose format (PDF, DOCX, etc.)
- **Template File**: Upload your Carbone template

#### Data Configuration

In the **Data** tab, write Python code to prepare JSON data:

```python
{
    'data': {
        'company': object.company_id.name,
        'date': object.date,
        'lines': [
            {
                'product': line.product_id.name,
                'quantity': line.quantity,
                'price': line.price_unit,
            }
            for line in object.order_line
        ]
    }
}
```

#### Carbone Options (Optional)

In the **Carbone Options** tab:
- **Rendering Mode**: Synchronous or Asynchronous
- **Converter**: Override default converter
- **Timezone**: Override default timezone
- **Language**: Override default language

#### Advanced Data (Optional)

- **Complement Data**: Additional data for `{c.}` tags
  ```python
  {
      'footer_text': 'Confidential Document',
      'page_numbers': True
  }
  ```

- **Enum Mappings**: JSON mappings for `:convEnum()`
  ```json
  {
      "status": {
          "draft": "Draft",
          "confirmed": "Confirmed",
          "done": "Completed"
      }
  }
  ```

### 3. Template Creation

Create your document template using:
- Microsoft Word (DOCX)
- Microsoft Excel (XLSX)
- LibreOffice Writer (ODT)
- LibreOffice Calc (ODS)

#### Template Tags

Use Carbone tags in your template:

- **Simple field**: `{d.company}`
- **Formatted number**: `{d.price:formatN(2)}`
- **Formatted date**: `{d.date:formatD(DD/MM/YYYY)}`
- **Loop**: `{d.lines[i].product}`
- **Conditional**: `{d.total:ifEQ(0):show(.hidden)}`
- **Complement data**: `{c.footer_text}`
- **Enum conversion**: `{d.status:convEnum(status)}`

See [Carbone Documentation](https://carbone.io/documentation.html) for full tag reference.

## Template Caching

### How It Works

When **Use Template Cache** is enabled (default):
1. Template is uploaded to Carbone on first render
2. Template ID is stored in `carbone_template_id` field
3. Subsequent renders reuse cached template (faster)

### When to Invalidate Cache

Invalidate cache when:
- Template file has been modified
- Template is corrupted
- You want to force re-upload

Click **Invalidate Cache** button on report form.

## Usage

### Printing Reports

1. **From Record View**: Click Print button, select your Carbone report
2. **From List View**: Select records, Actions > Print, select report
3. **Programmatically**:
   ```python
   report = self.env.ref('module.report_xml_id')
   pdf_content, format = report._render_carbone(
       'report.name',
       '1,2,3',  # record IDs
       {}
   )
   ```

### Multi-Record Reports

The module automatically handles multiple records:
- Single record: renders with single data object
- Multiple records: renders with array of data objects

Your template can access record array with:
```
{d.records[i].field_name}
```

## Troubleshooting

### Common Issues

#### "Carbone API URL is not configured"
- Go to Settings > Reporting Tools
- Configure API URL and Access Token

#### "Template upload timeout"
- Check network connection
- Verify Carbone API URL is correct
- Try uploading smaller template

#### "Report rendering timeout"
- Report takes >60s to generate
- Consider using asynchronous mode (when available)
- Optimize template complexity

#### "Invalid JSON data"
- Check Python syntax in Data tab
- Ensure 'object' variable is used correctly
- Validate JSON structure

### Enable Debug Logging

Add to Odoo config file:
```ini
[options]
log_handler = odoo.addons.dub_reporting_carbone:DEBUG
```

View logs for detailed rendering information.

## API Reference

### Model: `ir.actions.report`

#### Fields

- `carbone_template_file`: Binary template file
- `carbone_report_type`: Output format selection
- `carbone_json_data`: Python code for data preparation
- `carbone_converter`: Converter engine selection
- `carbone_timezone`: Timezone for date formatting
- `carbone_lang`: Language code for formatting
- `carbone_complement_data`: Additional data
- `carbone_enum_mappings`: Enum mappings JSON
- `carbone_template_id`: Cached template ID
- `carbone_use_template_cache`: Enable template caching
- `carbone_rendering_mode`: Sync/async mode
- `carbone_webhook_timeout`: Async timeout

#### Methods

- `_render_carbone(report_ref, docids, data)`: Main render method
- `_validate_carbone_config()`: Validate configuration
- `_upload_template()`: Upload template to Carbone
- `_prepare_render_payload(recordset)`: Prepare render data
- `action_invalidate_template_cache()`: Clear cached template

## Performance Tips

1. **Enable Template Caching**: Significant speedup for repeated renders
2. **Optimize JSON Data**: Only include needed fields
3. **Simplify Templates**: Complex templates take longer to render
4. **Use Appropriate Converter**: LibreOffice is fastest, Chromium for CSS
5. **Batch Records**: Render multiple records in one request when possible

## Security

- API tokens stored in database (consider encryption in production)
- Token field has `password=True` attribute (hidden in UI)
- Validation prevents rendering without proper configuration
- All API calls logged for audit trail

## Changelog

### Version 2.0.0
- Full Carbone API v5 support
- Template caching mechanism
- Enhanced error handling and logging
- Added converter, timezone, language options
- Support for complement data and enum mappings
- PEP8 compliant code with docstrings
- Comprehensive README documentation

### Version 1.0.5
- Initial release with basic Carbone support

## Support

- **Issues**: Report on module repository
- **Carbone Docs**: [carbone.io/documentation](https://carbone.io/documentation.html)
- **Carbone Support**: [carbone.io/support](https://carbone.io/support.html)

## License

OPL-1 (Odoo Proprietary License)

## Credits

- **Original Author**: Davide Corio
- **Refactoring & v5 Support**: Dubhe IT
- **Carbone.io**: [Carbone.io Team](https://carbone.io)
