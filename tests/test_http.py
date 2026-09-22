import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from agencyos.core import Agency
from agencyos.server import make_handler


class HttpFlowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Agency(Path(self.temp.name) / 'http.sqlite3')
        self.app.bootstrap('owner', 'long-password-for-tests')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.app))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.app.close()
        self.temp.cleanup()

    def request(self, method, path, data=None, cookie=None, csrf=None, origin=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        headers = {'Content-Type':'application/json'}
        if cookie: headers['Cookie'] = cookie
        if csrf: headers['X-CSRF-Token'] = csrf
        if origin: headers['Origin'] = origin
        conn.request(method, path, json.dumps(data).encode() if data is not None else None, headers)
        response = conn.getresponse()
        result = response.status, json.loads(response.read()), response.getheader('Set-Cookie')
        conn.close()
        return result

    def test_cookie_csrf_and_approval_flow(self):
        self.assertEqual(self.request('GET', '/api/dashboard')[0], 401)
        status, payload, cookie = self.request('POST', '/api/login', {'username':'owner','password':'long-password-for-tests'})
        self.assertEqual(status, 200)
        self.assertIn('HttpOnly', cookie)
        cookie = cookie.split(';')[0]
        csrf = payload['csrf']
        self.assertEqual(self.request('POST','/api/opportunities',{'title':'Project','source':'manual'},cookie)[0], 403)
        self.assertEqual(self.request('POST','/api/opportunities',{'title':'Project','source':'manual'},cookie,csrf,'https://evil.example')[0], 403)
        status, opportunity, _ = self.request('POST','/api/opportunities',{'title':'Project','source':'manual'},cookie,csrf)
        self.assertEqual(status, 201)
        status, draft, _ = self.request('POST',f"/api/opportunities/{opportunity['id']}/draft",{},cookie,csrf)
        self.assertEqual(status, 201)
        status, _, _ = self.request('POST',f"/api/approvals/{draft['approval_id']}/decision",{'decision':'approved'},cookie,csrf)
        self.assertEqual(status, 200)
        status, project, _ = self.request('POST',f"/api/opportunities/{opportunity['id']}/project",{},cookie,csrf)
        self.assertEqual(status, 201)
        self.assertTrue(project['id'])


if __name__ == '__main__':
    unittest.main()
