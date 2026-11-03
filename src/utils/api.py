"""Consistent API errors, bounded input and secret-free timing records."""
import logging
from time import perf_counter
from uuid import uuid4
from flask import g, jsonify, request
from pymongo.errors import PyMongoError
from werkzeug.exceptions import HTTPException


def configure_api(app):
    app.config['MAX_CONTENT_LENGTH'] = 64 * 1024

    @app.before_request
    def begin():
        g.request_id, g.started = uuid4().hex, perf_counter()
        if not request.path.startswith('/api/'):
            return
        for key, minimum, maximum in [('limit', 1, 100), ('offset', 0, 10000)]:
            value = request.args.get(key, str(minimum))
            if len(value) > 5 or not value.isascii() or not value.isdigit() or not minimum <= int(value) <= maximum:
                return jsonify(code='invalid_pagination', message='Paginação inválida.', error='Paginação inválida.'), 400
        term = request.args.get('q', '')
        conversation = (request.view_args or {}).get('conversa_id', '')
        if len(term) > 200 or len(conversation) > 128:
            return jsonify(code='invalid_input', message='Entrada muito longa.', error='Entrada muito longa.'), 400

    @app.errorhandler(HTTPException)
    def http_error(exc):
        if request.path.startswith('/api/'):
            message = 'Requisição inválida.'
            return jsonify(code=f'http_{exc.code}', message=message, error=message), exc.code
        return exc

    @app.errorhandler(PyMongoError)
    def mongo_error(exc):
        logging.getLogger(__name__).warning('database_unavailable request_id=%s', g.request_id)
        return jsonify(code='database_unavailable', message='Banco de dados indisponível.', error='Banco de dados indisponível.'), 503

    @app.after_request
    def finish(response):
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
            if response.is_json and response.status_code >= 400:
                data = response.get_json()
                data.setdefault('message', data.get('error', 'Falha na requisição.'))
                data.setdefault('code', {400:'invalid_input', 401:'unauthorized', 403:'email_unverified', 404:'not_found', 429:'daily_quota_exceeded', 502:'ai_unavailable', 503:'database_unavailable'}.get(response.status_code, 'request_failed'))
                data['request_id'] = g.request_id
                response.set_data(app.json.dumps(data))
            if response.status_code == 429:
                response.headers['Retry-After'] = '60'
        response.headers['X-Request-ID'] = g.request_id
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Report-only until all Firebase providers/CDNs have been exercised.
        response.headers['Content-Security-Policy-Report-Only'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://www.gstatic.com https://cdn.jsdelivr.net https://apis.google.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://*.googleapis.com https://*.firebaseio.com https://*.firebaseapp.com; frame-src https://*.firebaseapp.com https://accounts.google.com; object-src 'none'; base-uri 'self'"
        logging.getLogger(__name__).info('request_id=%s endpoint=%s status=%s duration_ms=%.1f', g.request_id, request.endpoint, response.status_code, (perf_counter()-g.started)*1000)
        return response
