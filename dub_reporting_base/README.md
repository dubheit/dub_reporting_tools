# Reporting Base Module

Base module for integrating external reporting engines with Odoo 18.0.

## Overview

This module provides common functionality for integrating external reporting engines (Carbone, BIRT, Jasper, etc.) with Odoo. It establishes a standardized architecture for reporting modules.

## Features

- **Abstract Methods**: Common interface for reporting engines
- **Utilities**: Validation, logging, error handling, and data preparation
- **Base Controller**: Standardized HTTP routing and response handling
- **JavaScript Framework**: Common UI utilities for report actions
- **Settings Section**: Dedicated "Reporting Tools" section in General Settings

## Architecture

### Models

#### `ir.actions.report` (inherited)

Provides common methods:
- `_render_report_engine()`: Abstract method for engine routing
- `_validate_report_config()`: Validate report configuration
- `_prepare_report_data()`: Prepare data for rendering
- `_handle_render_error()`: Standardized error handling
- `_log_report_request()`: Log report generation requests

#### `res.config.settings` (inherited)

Placeholder for engine-specific configuration fields.

### Controllers

#### `BaseReportController`

Provides:
- `_prepare_error_response()`: Standardized error responses
- `_prepare_success_response()`: Standardized success responses with content
- `_validate_report_params()`: Parameter validation

### JavaScript

#### `report_action.js`

Utilities:
- `blockUI()`: Block UI during report generation
- `unblockUI()`: Unblock UI after completion
- `handleDownloadError()`: Handle download errors with notifications
- `downloadReport()`: Download report using standard utilities

## Usage

This module is a technical dependency for specific reporting engine modules. It should not be used directly.

### For Developers

To create a new reporting engine module:

1. Add `dub_reporting_base` as a dependency
2. Inherit `ir.actions.report` and implement engine-specific rendering
3. Add configuration fields to `res.config.settings`
4. Inject settings into the "Reporting Tools" section using XPath:
   ```xml
   <xpath expr="//block[@id='reporting_tools_settings']" position="inside">
       <setting string="Your Engine">...</setting>
   </xpath>
   ```
5. Create controller extending `BaseReportController`
6. Register JavaScript handler using `reportActionRegistry`

## Installation

Install as a dependency of specific reporting engine modules.

## Dependencies

- `base`
- `web`

## License

LGPL-3

## Author

Dubhe IT (https://www.dubhe.it)
