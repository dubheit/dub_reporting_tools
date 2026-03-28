import json
import logging
from odoo import http
from odoo.http import request, content_disposition
from odoo.addons.web.controllers.report import ReportController

_logger = logging.getLogger(__name__)


class BaseReportController(ReportController):
    """Base controller for external reporting engines.
    
    This controller provides common functionality for handling custom report types.
    Specific engine modules should extend this to add their routing logic.
    """

    @staticmethod
    def _prepare_error_response(error_msg, status_code=500):
        """Prepare standardized error response.
        
        Args:
            error_msg (str): Error message
            status_code (int): HTTP status code
            
        Returns:
            werkzeug.Response: Error response with proper headers
        """
        response = request.make_response(
            json.dumps({
                'error': error_msg,
                'status': 'error'
            }),
            headers=[
                ('Content-Type', 'application/json'),
                ('Cache-Control', 'no-cache')
            ]
        )
        response.status_code = status_code
        _logger.error(f"Report error response: {error_msg}")
        return response

    @staticmethod
    def _prepare_success_response(content, filename, content_type='application/pdf'):
        """Prepare standardized success response with report content.
        
        Args:
            content (bytes): Report content
            filename (str): Suggested filename for download
            content_type (str): MIME type of the content
            
        Returns:
            werkzeug.Response: Success response with report content
        """
        headers = [
            ('Content-Type', content_type),
            ('Content-Disposition', content_disposition(filename)),
            ('Content-Length', len(content))
        ]
        
        _logger.info(f"Report generated successfully: {filename} ({len(content)} bytes)")
        return request.make_response(content, headers=headers)

    @staticmethod
    def _validate_report_params(report_id, docids):
        """Validate common report parameters.
        
        Args:
            report_id: Report ID or name
            docids: Document IDs to render
            
        Returns:
            tuple: (report, docids_list)
            
        Raises:
            ValueError: If parameters are invalid
        """
        if not report_id:
            raise ValueError("Report ID is required")
        
        if not docids:
            raise ValueError("Document IDs are required")
        
        # Parse docids if string
        if isinstance(docids, str):
            docids = [int(x) for x in docids.split(',') if x]
        elif not isinstance(docids, list):
            docids = [int(docids)]
        
        return report_id, docids
