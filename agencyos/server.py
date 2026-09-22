"""Small HTTP control plane. Put behind HTTPS before exposing outside localhost."""
import json
import os
import re
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .core import Agency, Problem

ROOT = Path(__file__).resolve().parent.parent / 'web'


class RateLimit:
    def __init__(self):
        self.lock = threading.Lock()
        self.attempts = {}

    def check(self, key):
        with self.lock:
            current = time.monotonic()
            recent = [stamp for stamp in self.attempts.get(key, []) if current - stamp < 900]
            if len(recent) >= 5:
                raise Problem('muitas tentativas; tente novamente mais tarde', 429)
            recent.append(current)
            self.attempts[key] = recent
            if len(self.attempts) > 10000:
                self.attempts = {k: v for k, v in self.attempts.items() if v[-1] > current - 900}

    def clear(self, key):
        with self.lock:
            self.attempts.pop(key, None)


def make_handler(agency, secure_cookie=False):
    limiter = RateLimit()

    class Handler(BaseHTTPRequestHandler):
        server_version = 'AgencyOS/0.1'

        def end_headers(self):
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            super().end_headers()

        def respond(self, value, status=200, cookie=None):
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            if cookie:
                self.send_header('Set-Cookie', cookie)
            self.end_headers()
            self.wfile.write(body)

        def token(self):
            cookies = SimpleCookie()
            try:
                cookies.load(self.headers.get('Cookie', ''))
                return cookies['agencyos_session'].value if 'agencyos_session' in cookies else ''
            except Exception:
                return ''

        def user(self, action='read'):
            user = agency.session(self.token())
            agency.authorize(user, action)
            return user

        def payload(self):
            if self.headers.get_content_type() != 'application/json':
                raise Problem('Content-Type precisa ser application/json', 415)
            try:
                length = int(self.headers.get('Content-Length', '-1'))
            except ValueError:
                raise Problem('Content-Length inválido')
            if length < 0 or length > 32768:
                raise Problem('corpo inválido ou acima de 32 KB', 413)
            try:
                value = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeDecodeError):
                raise Problem('JSON inválido')
            if not isinstance(value, dict):
                raise Problem('o corpo precisa ser um objeto JSON')
            return value

        def handle_request(self, method):
            try:
                path = urlsplit(self.path).path
                if method == 'GET' and path in ('/', '/app.js', '/style.css'):
                    filename = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[path]
                    data = (ROOT / filename).read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type', {'index.html': 'text/html', 'app.js': 'text/javascript', 'style.css': 'text/css'}[filename] + '; charset=utf-8')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                if method == 'GET' and path == '/health':
                    return self.respond({'status': 'ok'})
                if method == 'POST':
                    origin = self.headers.get('Origin')
                    if origin and origin != f"{'https' if secure_cookie else 'http'}://{self.headers.get('Host')}":
                        raise Problem('origem inválida', 403)
                    data = self.payload()
                    if path == '/api/login':
                        key = self.client_address[0]
                        limiter.check(key)
                        username, password = data.get('username'), data.get('password')
                        if not isinstance(username, str) or not isinstance(password, str):
                            raise Problem('credenciais inválidas', 401)
                        token, csrf = agency.login(username, password)
                        limiter.clear(key)
                        cookie = f'agencyos_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200' + ('; Secure' if secure_cookie else '')
                        return self.respond({'csrf': csrf}, cookie=cookie)
                if method == 'GET' and path == '/api/me':
                    user = self.user()
                    return self.respond(user)
                if method == 'GET' and path == '/api/dashboard':
                    self.user()
                    return self.respond(agency.dashboard())
                if method == 'POST':
                    action = 'approve' if re.fullmatch(r'/api/approvals/[a-f0-9]{32}/decision', path) else 'write'
                    user = self.user(action)
                    if self.headers.get('X-CSRF-Token') != user['csrf']:
                        raise Problem('token CSRF inválido', 403)
                    actor = user['id']
                    if path == '/api/logout':
                        agency.logout(self.token(), actor)
                        return self.respond({'ok': True}, cookie='agencyos_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                    if path == '/api/clients':
                        return self.respond(agency.create_client(actor, data), 201)
                    if path == '/api/opportunities':
                        return self.respond(agency.create_opportunity(actor, data), 201)
                    match = re.fullmatch(r'/api/opportunities/([a-f0-9]{32})/draft', path)
                    if match:
                        return self.respond(agency.draft_proposal(actor, match[1]), 201)
                    match = re.fullmatch(r'/api/approvals/([a-f0-9]{32})/decision', path)
                    if match:
                        return self.respond(agency.decide(actor, match[1], data.get('decision'), data.get('reason', '')))
                    match = re.fullmatch(r'/api/opportunities/([a-f0-9]{32})/project', path)
                    if match:
                        return self.respond(agency.create_project(actor, match[1], data), 201)
                    match = re.fullmatch(r'/api/projects/([a-f0-9]{32})/tasks', path)
                    if match:
                        return self.respond(agency.create_task(actor, match[1], data), 201)
                    match = re.fullmatch(r'/api/tasks/([a-f0-9]{32})/complete', path)
                    if match:
                        return self.respond(agency.complete_task(actor, match[1], data))
                raise Problem('rota não encontrada', 404)
            except Problem as error:
                self.respond({'error': str(error)}, error.status)
            except Exception:
                self.log_error('unhandled request failure')
                self.respond({'error': 'erro interno'}, HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_GET(self):
            self.handle_request('GET')

        def do_POST(self):
            self.handle_request('POST')

    return Handler


def serve(db_path, host='127.0.0.1', port=8000, secure_cookie=False):
    if host not in ('127.0.0.1', 'localhost', '::1') and not secure_cookie:
        raise Problem('acesso externo exige HTTPS e AGENCYOS_SECURE_COOKIE=1')
    agency = Agency(db_path)
    server = ThreadingHTTPServer((host, port), make_handler(agency, secure_cookie))
    try:
        print(f'AgencyOS escutando em {host}:{server.server_port}', flush=True)
        server.serve_forever()
    finally:
        server.server_close()
        agency.close()
