import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from agencyos.core import Agency
from agencyos.server import is_local_client, make_handler


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
        status, _, _ = self.request('POST',f"/api/proposals/{draft['id']}/revise",{'content':'Texto final revisado'},cookie,csrf)
        self.assertEqual(status, 200)
        status, _, _ = self.request('POST',f"/api/approvals/{draft['approval_id']}/decision",{'decision':'approved'},cookie,csrf)
        self.assertEqual(status, 200)
        self.assertEqual(self.request('POST',f"/api/opportunities/{opportunity['id']}/project",{},cookie,csrf)[0], 409)
        status, _, _ = self.request('POST',f"/api/proposals/{draft['id']}/dispatch",{'channel':'E-mail','reference':'Confirmação manual'},cookie,csrf)
        self.assertEqual(status, 201)
        status, client, _ = self.request('POST','/api/clients',{'name':'Cliente'},cookie,csrf)
        self.assertEqual(status, 201)
        status, _, _ = self.request('POST',f"/api/opportunities/{opportunity['id']}/sale",{'client_id':client['id'],'confirmation':'Cliente aceitou'},cookie,csrf)
        self.assertEqual(status, 201)
        status, project, _ = self.request('POST',f"/api/opportunities/{opportunity['id']}/project",{},cookie,csrf)
        self.assertEqual(status, 201)
        self.assertTrue(project['id'])

    def test_lan_mode_allows_private_network_and_blocks_public_clients(self):
        self.assertTrue(is_local_client('192.168.1.42'))
        self.assertTrue(is_local_client('10.1.2.3'))
        self.assertTrue(is_local_client('172.20.0.8'))
        self.assertTrue(is_local_client('127.0.0.1'))
        self.assertFalse(is_local_client('8.8.8.8'))
        self.assertFalse(is_local_client('172.32.0.1'))
        self.assertFalse(is_local_client('invalid'))
        lan_server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.app, lan_test=True))
        thread = threading.Thread(target=lan_server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection('127.0.0.1', lan_server.server_port)
            conn.request('GET', '/', headers={'Host':f'192.168.1.42:{lan_server.server_port}'})
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn(b'AgencyOS', response.read())
            conn.close()
        finally:
            lan_server.shutdown()
            thread.join()
            lan_server.server_close()


if __name__ == '__main__':
    unittest.main()
