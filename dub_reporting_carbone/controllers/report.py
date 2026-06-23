import json
import base64
import logging
import mimetypes
import requests
from odoo import _, fields
from odoo.addons.web.controllers.report import ReportController
from odoo.http import (
    content_disposition,
    request,
    route,
)
from odoo.tools.safe_eval import safe_eval, time

_logger = logging.getLogger(__name__)

class ReportController(ReportController):

    def _carbone_download_filename(self, report, docids, ext):
        """Build a meaningful download filename from the report's
        print_report_name (evaluated on the printed record), falling back to
        the report display name. Avoids generic names like 'download.pdf'."""
        ids = [int(x) for x in docids.split(",") if str(x).strip().isdigit()] \
            if docids else []
        name = report.name
        if report.print_report_name and len(ids) == 1 and report.model:
            try:
                obj = request.env[report.model].browse(ids)
                name = safe_eval(
                    report.print_report_name, {"object": obj, "time": time}
                )
            except Exception:
                _logger.warning(
                    "Carbone print_report_name eval failed for %s",
                    report.report_name,
                )
        name = (name or report.name).replace("/", "-").replace("\\", "-")
        return "%s.%s" % (name, ext)

    @route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        if converter == "carbone":
            report = request.env[
                    "ir.actions.report"]._get_report_from_name(
                    reportname)
            result = report._render_carbone(reportname, docids, data)

            # Check if async mode
            if result[0] == 'async':
                # Return JSON response for async mode
                return request.make_json_response({
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Report in Background'),
                        'message': _(
                            'Your report "%s" is being generated in background. '
                            'You will receive it via chat when ready.'
                        ) % report.name,
                        'type': 'info',
                        'sticky': False,
                    }
                })
            
            # Sync mode - return file (PDF, ZIP, etc.)
            data, ext = result
            content_type = mimetypes.guess_type('report.' + ext)[0]
            if ext == 'zip':
                content_type = 'application/zip'
            filename = self._carbone_download_filename(report, docids, ext)
            http_headers = [
                ("Content-Type", content_type),
                ("Content-Length", len(data)),
                ("Content-Disposition", content_disposition(filename)),
            ]
            return request.make_response(data, headers=http_headers)
        else:
            return super().report_routes(
                reportname,
                docids=docids,
                converter=converter,
                **data,
            )
    
    @route()
    def report_download(self, data, context=None, token=None):
        requestcontent = json.loads(data)
        url, report_type = requestcontent[0], requestcontent[1]
        if report_type == "carbone":
            report_name, docids = url.split(
                "/report/carbone/")[1].split("?")[0].split('/')
            if docids:
                # Get report to check if async mode
                report = request.env["ir.actions.report"]._get_report_from_name(
                    report_name)
                
                # Check if async mode before calling report_routes
                if report.carbone_rendering_mode == 'async':
                    # Trigger async render
                    report._render_carbone(report_name, docids, {})
                    # Return notification immediately
                    message = 'Your report "%s" is being generated in background. You will receive it via chat when ready.' % report.name
                    return request.make_json_response({
                        'success': True,
                        'message': message,
                        'title': 'Report in Background',
                        'type': 'info',
                    })
                
                # Sync mode - continue with normal flow
                response = self.report_routes(
                        report_name,
                        docids=docids,
                        converter="carbone",
                        context=context
                    )

                # Determine output extension (ZIP for batch zip output with multiple records)
                ids = [int(x) for x in docids.split(",")] if docids else []
                output_ext = report.carbone_report_type
                if len(ids) > 1 and report.carbone_batch_output == 'zip':
                    output_ext = 'zip'

                # Always expose a meaningful filename (not 'download.pdf')
                filename = self._carbone_download_filename(
                    report, docids, output_ext)
                response.headers["Content-Disposition"] = content_disposition(
                    filename)
                return response
        else:
            return super().report_download(data, context=context, token=token)
    
    @route('/carbone/start_async', type='http', auth='user', methods=['POST'], csrf=False)
    def carbone_start_async(self, **kwargs):
        """Start async rendering if report is configured for async.
        Expects JSON or form data with reportname and docids.
        """
        try:
            # Parse JSON body safely (Werkzeug) or fallback to params/kwargs
            payload = {}
            try:
                payload = request.httprequest.get_json(silent=True) or {}
            except Exception:
                payload = {}
            if not payload:
                payload = dict(request.params) if request.params else {}
            if not payload:
                payload = kwargs or {}
            
            reportname = payload.get('reportname')
            docids = payload.get('docids')
            if not reportname or not docids:
                return request.make_json_response({'action': {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Async Report',
                        'message': 'Missing reportname or docids',
                        'type': 'danger',
                        'sticky': False,
                    }
                }})
            report = request.env["ir.actions.report"]._get_report_from_name(reportname)
            if not report:
                return request.make_json_response({'action': {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Async Report',
                        'message': 'Report not found',
                        'type': 'danger',
                        'sticky': False,
                    }
                }})
            # If report is not async, indicate sync flow to the frontend and exit
            if report.carbone_rendering_mode != 'async':
                _logger.info("Report not in async mode; proceeding with synchronous download")
                return request.make_json_response({'sync': True})

            # Trigger async render
            report._render_carbone(reportname, docids, {})

            # Create or get a direct chat with OdooBot (do not open UI here)
            user_partner_id = request.env.user.partner_id.id
            odoobot = request.env['res.partner'].sudo().search([('name', '=', 'OdooBot')], limit=1)
            Channel = request.env['discuss.channel'].sudo()
            domain = [
                ('channel_type', '=', 'chat'),
                ('channel_partner_ids', 'in', [user_partner_id]),
                ('channel_partner_ids', 'in', [odoobot.id] if odoobot else [user_partner_id]),
            ]
            channel = Channel.search(domain, limit=1)
            if not channel:
                partner_ids = [pid for pid in [user_partner_id, odoobot.id if odoobot else None] if pid]
                channel = Channel.create({
                    'name': 'OdooBot',
                    'channel_type': 'chat',
                    'channel_partner_ids': [(6, 0, partner_ids)],
                })

            # Return a lightweight notification; the chat popup will open automatically when the webhook posts the final message
            return request.make_json_response({
                'action': {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Report in Background',
                        'message': f'Your report "{report.name}" is being generated. You will receive it via chat when ready.',
                        'type': 'info',
                        'sticky': False,
                    }
                }
            })
        except Exception as e:
            return request.make_json_response({'action': {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Async Report Error',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': False,
                }
            }})
    
    @route('/carbone/webhook', type='http', auth='public', methods=['POST'], csrf=False)
    def carbone_webhook_json(self, **kwargs):
        """JSON webhook endpoint for Carbone async rendering callbacks.
        Expects JSON body: { success: true, data: { renderId: '...' } }.
        """
        try:
            payload = request.httprequest.get_json(silent=True) or {}
        except Exception:
            payload = {}

        # Log full payload for debugging
        _logger.info(f"Carbone webhook (json) full payload: {payload}")

        # Try different payload formats (standard vs batch)
        render_id = None
        if payload.get('data') and payload['data'].get('renderId'):
            render_id = payload['data']['renderId']
        elif payload.get('renderId'):
            # Direct renderId in payload
            render_id = payload['renderId']

        _logger.info(f"Carbone webhook (json) received: render_id={render_id}")

        try:
            async_model = request.env['carbone.async.render'].sudo()
            # pick the latest pending request
            async_render = async_model.search([('state', '=', 'pending')], order='create_date desc', limit=1)
            if not async_render:
                return request.make_json_response({'status': 'error', 'message': 'No pending render'}, status=404)

            # Check for Carbone error response
            if payload.get('success') is False:
                error_msg = payload.get('error', 'Unknown error from Carbone API')
                error_code = payload.get('code', '')
                full_error = f"{error_msg} (code: {error_code})" if error_code else error_msg
                _logger.error(f"Carbone API error: {full_error}")
                async_render.write({'state': 'failed', 'error_message': full_error})
                # Notify user of the error
                async_render._notify_user_error(full_error)
                return request.make_json_response({'status': 'error', 'message': full_error}, status=400)

            if not render_id:
                async_render.write({'state': 'failed', 'error_message': 'Missing renderId from webhook'})
                return request.make_json_response({'status': 'error', 'message': 'Missing renderId'}, status=400)
            # update render id and proceed to fetch
            async_render.write({'webhook_received': fields.Datetime.now(), 'name': render_id})
            report = async_render.report_id
            company = request.env['res.company'].sudo().browse(async_render.user_id.company_id.id)
            retrieve_response = requests.get(
                f'{company.carbone_api_url}/render/{render_id}',
                headers={'carbone-version': '5', 'Authorization': f'Bearer {company.carbone_access_token}'},
                timeout=60,
            )
            retrieve_response.raise_for_status()

            # Detect actual file extension from render_id (e.g., "xxx.zip" or "xxx.pdf")
            actual_ext = render_id.rsplit('.', 1)[-1] if '.' in render_id else report.carbone_report_type
            filename = f"{report.name}.{actual_ext}"

            async_render.write({'state': 'completed', 'result_file': base64.b64encode(retrieve_response.content), 'result_filename': filename})
            async_render._notify_user(base64.b64encode(retrieve_response.content), filename)
            return request.make_json_response({'status': 'success'})
        except Exception as e:
            _logger.error(f"Webhook JSON handler error: {e}", exc_info=True)
            return request.make_json_response({'status': 'error', 'message': str(e)}, status=500)
    
    @route('/carbone/webhook/<string:render_id>', type='http', auth='public', methods=['POST'], csrf=False)
    def carbone_webhook(self, render_id, **kwargs):
        """Webhook endpoint for Carbone async rendering callbacks.
        
        This endpoint is called by Carbone when async rendering completes.
        
        Args:
            render_id: Carbone render ID
        """
        _logger.info(f"Carbone webhook received for render: {render_id}")
        
        try:
            # Find async render request
            async_render = request.env['carbone.async.render'].sudo().search([
                ('name', '=', render_id),
                ('state', '=', 'pending')
            ], limit=1)
            
            if not async_render:
                _logger.warning(f"Async render not found or already processed: {render_id}")
                return request.make_json_response({
                    'status': 'error',
                    'message': 'Render request not found or already processed'
                }, status=404)
            
            # Update webhook received time
            async_render.write({'webhook_received': fields.Datetime.now()})
            
            # Get report and company config
            report = async_render.report_id
            company = request.env['res.company'].sudo().browse(async_render.user_id.company_id.id)
            
            # Retrieve rendered file from Carbone
            _logger.debug(f"Retrieving render from Carbone: {render_id}")
            
            retrieve_response = requests.get(
                f'{company.carbone_api_url}/render/{render_id}',
                headers={
                    'carbone-version': '5',
                    'Authorization': f'Bearer {company.carbone_access_token}',
                },
                timeout=60
            )
            
            retrieve_response.raise_for_status()

            # Detect actual file extension from render_id (e.g., "xxx.zip" or "xxx.pdf")
            actual_ext = render_id.rsplit('.', 1)[-1] if '.' in render_id else report.carbone_report_type
            filename = f"{report.name}.{actual_ext}"

            # Save result
            async_render.write({
                'state': 'completed',
                'result_file': base64.b64encode(retrieve_response.content),
                'result_filename': filename,
            })
            
            _logger.info(
                f"Async render completed successfully: {render_id} "
                f"({len(retrieve_response.content)} bytes)"
            )
            
            # Notify user via chat
            async_render._notify_user(
                base64.b64encode(retrieve_response.content),
                filename
            )
            
            return request.make_json_response({
                'status': 'success',
                'message': 'Report processed and user notified'
            })
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to retrieve render from Carbone: {str(e)}"
            _logger.error(error_msg, exc_info=True)
            
            if async_render:
                async_render.write({
                    'state': 'failed',
                    'error_message': error_msg,
                })
            
            return request.make_json_response({
                'status': 'error',
                'message': error_msg
            }, status=500)
            
        except Exception as e:
            error_msg = f"Unexpected error processing webhook: {str(e)}"
            _logger.error(error_msg, exc_info=True)
            
            if async_render:
                async_render.write({
                    'state': 'failed',
                    'error_message': error_msg,
                })
            
            return request.make_json_response({
                'status': 'error',
                'message': error_msg
            }, status=500)
