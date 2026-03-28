import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    """Base report model with common functionality for external reporting engines."""
    
    _inherit = 'ir.actions.report'

    @api.model
    def _render_report_engine(self, engine_type, report_ref, docids, data=None):
        """Abstract method for engine routing.
        
        This method should be overridden by specific engine modules to implement
        their rendering logic.
        
        Args:
            engine_type (str): The report engine type (e.g., 'carbone', 'birt')
            report_ref (str): Report reference (name or id)
            docids (list): List of document IDs to render
            data (dict): Additional data for rendering
            
        Returns:
            tuple: (report_content, report_format)
            
        Raises:
            UserError: If engine type is not supported
        """
        _logger.error(
            f"Rendering engine '{engine_type}' not implemented. "
            f"Report: {report_ref}, docids: {docids}"
        )
        raise UserError(_(
            "The reporting engine '%s' is not supported. "
            "Please install the corresponding module."
        ) % engine_type)

    def _validate_report_config(self):
        """Validate report configuration before rendering.
        
        This method checks for common issues like missing configuration,
        invalid settings, etc.
        
        Returns:
            bool: True if configuration is valid
            
        Raises:
            UserError: If configuration is invalid
        """
        self.ensure_one()
        
        if not self.report_type:
            raise UserError(_("Report type is not defined for '%s'.") % self.name)
        
        if not self.model:
            raise UserError(_("Report model is not defined for '%s'.") % self.name)
        
        _logger.debug(f"Report configuration validated for {self.name}")
        return True

    @api.model
    def _prepare_report_data(self, docids, data=None):
        """Prepare data for report rendering.
        
        This method prepares the data dictionary that will be passed to the
        reporting engine. It can be overridden by specific engines to add
        custom data preparation logic.
        
        Args:
            docids (list): List of document IDs
            data (dict): Additional data
            
        Returns:
            dict: Prepared data dictionary
        """
        if data is None:
            data = {}
        
        # Add common context information
        data.update({
            'doc_ids': docids,
            'doc_model': data.get('model'),
            'lang': self.env.context.get('lang') or self.env.user.lang,
            'tz': self.env.context.get('tz') or self.env.user.tz or 'UTC',
        })
        
        _logger.debug(f"Report data prepared: {len(docids)} documents")
        return data

    @api.model
    def _handle_render_error(self, error, report_name, engine_type):
        """Handle rendering errors with standardized error messages.
        
        Args:
            error (Exception): The exception that occurred
            report_name (str): Name of the report
            engine_type (str): Type of reporting engine
            
        Raises:
            UserError: With user-friendly error message
        """
        error_msg = str(error)
        _logger.error(
            f"Report rendering failed for '{report_name}' using {engine_type} engine: {error_msg}",
            exc_info=True
        )
        
        raise UserError(_(
            "Failed to generate report '%(report)s'.\n\n"
            "Engine: %(engine)s\n"
            "Error: %(error)s\n\n"
            "Please contact your administrator if the problem persists."
        ) % {
            'report': report_name,
            'engine': engine_type,
            'error': error_msg
        })

    def _log_report_request(self, docids, success=True):
        """Log report generation requests.
        
        Args:
            docids (list): List of document IDs
            success (bool): Whether the report was generated successfully
        """
        self.ensure_one()
        
        status = "SUCCESS" if success else "FAILED"
        _logger.info(
            f"Report '{self.name}' ({self.report_type}) {status}: "
            f"{len(docids)} document(s), user: {self.env.user.name}"
        )

    def _get_report_from_name(self, report_name):
        """Override to support custom engine types.
        
        This method is called by Odoo to find the report by name.
        Extended to support detection of custom report types.
        
        Args:
            report_name (str): Report name
            
        Returns:
            ir.actions.report: Report record
        """
        res = super()._get_report_from_name(report_name)
        if res:
            _logger.debug(f"Report found: {report_name} (type: {res.report_type})")
        return res
