import json
import logging
import requests
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class CarboneStudioProxy(http.Controller):
    """Proxy controller for Carbone Studio API requests.
    
    Carbone Studio makes requests to /render and /template endpoints.
    This controller proxies those requests to the actual Carbone API.
    """
    
    def _get_carbone_config(self):
        """Get Carbone configuration for Studio from company settings."""
        company = request.env.company
        api_url = company.carbone_api_url or 'https://api.carbone.io'
        token = company.carbone_access_token or ''
        return {
            'api_url': api_url,
            'token': token,
        }
    
    @http.route(['/render', '/render/<path:path>', '/carbone/studio/render', '/carbone/studio/render/<path:path>'], type='http', auth='user', methods=['GET', 'POST'], csrf=False)
    def studio_render_proxy(self, path=None, **kwargs):
        """Proxy render requests from Studio to Carbone API."""
        config = self._get_carbone_config()
        url = f"{config['api_url']}/render" + (f"/{path}" if path else "")
        
        # Forward all relevant headers from the original request
        headers = {
            'carbone-version': '5',
        }
        if config['token']:
            headers['Authorization'] = f"Bearer {config['token']}"
        
        # Forward Content-Type from original request
        req_content_type = request.httprequest.headers.get('Content-Type')
        if req_content_type:
            headers['Content-Type'] = req_content_type
        
        _logger.info(f"Studio render proxy: {request.httprequest.method} {url}")
        
        try:
            if request.httprequest.method == 'POST':
                # Forward POST request
                body = request.httprequest.get_data()
                response = requests.post(url, headers=headers, data=body, timeout=60)
            else:
                # Forward GET request
                response = requests.get(url, headers=headers, timeout=60)
            
            _logger.info(f"Studio render proxy response: {response.status_code}")
            
            # Return response with all headers
            resp_headers = [
                ('Content-Type', response.headers.get('Content-Type', 'application/octet-stream')),
            ]
            # Forward content-disposition if present
            if 'Content-Disposition' in response.headers:
                resp_headers.append(('Content-Disposition', response.headers['Content-Disposition']))
            
            return request.make_response(
                response.content,
                headers=resp_headers,
                status=response.status_code
            )
        except Exception as e:
            _logger.error(f"Studio render proxy error: {e}", exc_info=True)
            return request.make_json_response({'error': str(e)}, status=500)
    
    @http.route(['/template', '/template/<path:path>', '/carbone/studio/template', '/carbone/studio/template/<path:path>'], type='http', auth='user', methods=['GET', 'POST'], csrf=False)
    def studio_template_proxy(self, path=None, **kwargs):
        """Proxy template requests from Studio to Carbone API."""
        config = self._get_carbone_config()
        url = f"{config['api_url']}/template" + (f"/{path}" if path else "")
        
        # Forward all relevant headers from the original request
        headers = {
            'carbone-version': '5',
        }
        if config['token']:
            headers['Authorization'] = f"Bearer {config['token']}"
        
        # Forward Content-Type from original request
        req_content_type = request.httprequest.headers.get('Content-Type')
        if req_content_type:
            headers['Content-Type'] = req_content_type
        
        _logger.info(f"Studio template proxy: {request.httprequest.method} {url}")
        
        try:
            if request.httprequest.method == 'POST':
                # Forward POST request
                body = request.httprequest.get_data()
                response = requests.post(url, headers=headers, data=body, timeout=60)
            else:
                # Forward GET request
                response = requests.get(url, headers=headers, timeout=60)
            
            _logger.info(f"Studio template proxy response: {response.status_code}")
            if response.status_code != 200:
                _logger.error(f"Studio template proxy error response: {response.text[:500]}")
            
            # Return response with all headers
            resp_headers = [
                ('Content-Type', response.headers.get('Content-Type', 'application/octet-stream')),
            ]
            # Forward content-disposition if present
            if 'Content-Disposition' in response.headers:
                resp_headers.append(('Content-Disposition', response.headers['Content-Disposition']))
            
            return request.make_response(
                response.content,
                headers=resp_headers,
                status=response.status_code
            )
        except Exception as e:
            _logger.error(f"Studio template proxy error: {e}", exc_info=True)
            return request.make_json_response({'error': str(e)}, status=500)
