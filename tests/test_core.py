import tempfile
import unittest
import sqlite3
from pathlib import Path

from agencyos.core import Agency, Problem


class AgencyFlowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.app = Agency(self.path)
        self.app.bootstrap('owner', 'long-password-for-tests')
        token, _ = self.app.login('owner', 'long-password-for-tests')
        self.actor = self.app.session(token)['id']

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def test_complete_flow_persists_evidence_and_events(self):
        opportunity = self.app.create_opportunity(self.actor, {'title':'Revisão do site', 'source':'manual', 'currency':'GBP'})['id']
        draft = self.app.draft_proposal(self.actor, opportunity)
        with self.assertRaises(Problem):
            self.app.create_project(self.actor, opportunity, {})
        self.assertEqual(self.app.one('SELECT status FROM approvals WHERE id=?', (draft['approval_id'],))['status'], 'pending')
        self.app.revise_proposal(self.actor, draft['id'], {'content':'Escopo revisado pelo operador.'})
        self.assertEqual(len(self.app.many('SELECT id FROM proposal_revisions WHERE proposal_id=?', (draft['id'],))), 2)
        self.app.decide(self.actor, draft['approval_id'], 'approved')
        with self.assertRaises(Problem):
            self.app.revise_proposal(self.actor, draft['id'], {'content':'Tarde demais'})
        with self.assertRaises(Problem):
            self.app.confirm_sale(self.actor, opportunity, {'client_id':'x', 'confirmation':'Cliente aceitou'})
        self.app.record_dispatch(self.actor, draft['id'], {'channel':'E-mail', 'reference':'Enviado em 01/09, conversa 42'})
        client = self.app.create_client(self.actor, {'name':'Empresa de teste'})['id']
        sale = self.app.confirm_sale(self.actor, opportunity, {'client_id':client, 'confirmation':'Aceite escrito registrado', 'amount_minor':15000})['id']
        self.assertEqual(self.app.one('SELECT amount_minor FROM sales WHERE id=?', (sale,))['amount_minor'], 15000)
        project = self.app.create_project(self.actor, opportunity, {})['id']
        self.assertEqual(self.app.one('SELECT client_id FROM projects WHERE id=?', (project,))['client_id'], client)
        task = self.app.create_task(self.actor, project, {'title':'Auditar site'})['id']
        with self.assertRaises(Problem):
            self.app.complete_task(self.actor, task, {'evidence':''})
        self.app.complete_task(self.actor, task, {'evidence':'Checklist revisado'})
        self.assertEqual(self.app.one('SELECT status FROM tasks WHERE id=?', (task,))['status'], 'done')
        self.assertGreaterEqual(len(self.app.dashboard()['events']), 13)
        self.assertGreaterEqual(len(self.app.dashboard()['evidence']), 7)
        self.app.close()
        self.app = Agency(self.path)
        self.assertEqual(self.app.one('SELECT status FROM tasks WHERE id=?', (task,))['status'], 'done')

    def test_rejection_duplicate_and_invalid_inputs(self):
        with self.assertRaises(Problem):
            self.app.create_opportunity(self.actor, {'title':'x','source':'manual','budget_minor':-1})
        opportunity = self.app.create_opportunity(self.actor, {'title':'Projeto','source':'VintePila'})['id']
        draft = self.app.draft_proposal(self.actor, opportunity)
        with self.assertRaises(Problem):
            self.app.draft_proposal(self.actor, opportunity)
        self.app.decide(self.actor, draft['approval_id'], 'rejected')
        with self.assertRaises(Problem):
            self.app.decide(self.actor, draft['approval_id'], 'approved')
        self.assertEqual(self.app.one('SELECT status FROM proposals WHERE id=?', (draft['id'],))['status'], 'rejected')
        self.assertNotIn('message.sent', [e['type'] for e in self.app.dashboard()['events']])

    def test_policy_gates_and_upgrade_on_existing_db(self):
        opportunity = self.app.create_opportunity(self.actor, {'title':'Site','source':'manual'})['id']
        draft = self.app.draft_proposal(self.actor, opportunity)
        with self.assertRaises(Problem):
            self.app.record_dispatch(self.actor, draft['id'], {'channel':'E-mail', 'reference':'ref'})
        with self.assertRaises(Problem):
            self.app.revise_proposal(self.actor, draft['id'], {'content':'   '})
        self.app.decide(self.actor, draft['approval_id'], 'approved')
        with self.assertRaises(Problem):
            self.app.draft_proposal(self.actor, opportunity)
        with self.assertRaises(Problem):
            self.app.create_project(self.actor, opportunity, {})
        self.app.record_dispatch(self.actor, draft['id'], {'channel':'E-mail', 'reference':'ref'})
        with self.assertRaises(Problem):
            self.app.record_dispatch(self.actor, draft['id'], {'channel':'E-mail', 'reference':'duplicado'})
        client = self.app.create_client(self.actor, {'name':'Cliente'})['id']
        with self.assertRaises(Problem):
            self.app.confirm_sale(self.actor, opportunity, {'client_id':client, 'confirmation':'aceite', 'amount_minor':-1})
        self.app.confirm_sale(self.actor, opportunity, {'client_id':client, 'confirmation':'aceite'})
        self.app.close()
        self.app = Agency(self.path)
        self.assertEqual(len(self.app.dashboard()['sales']), 1)

    def test_auth_and_rbac(self):
        with self.assertRaises(Problem):
            self.app.login('owner', 'incorrect-password')
        with self.assertRaises(Problem):
            self.app.bootstrap('another', 'long-password-for-tests')
        with self.assertRaises(Problem) as error:
            self.app.authorize({'role':'operator'}, 'approve')
        self.assertEqual(error.exception.status, 403)


class UpgradeTest(unittest.TestCase):
    def test_existing_client_survives_schema_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'old.sqlite3'
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE clients (id TEXT PRIMARY KEY, name TEXT NOT NULL, website TEXT, notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)")
                db.execute("INSERT INTO clients VALUES ('existing', 'Cliente antigo', NULL, '', '2026-01-01')")
            app = Agency(path)
            try:
                self.assertEqual(app.one('SELECT name FROM clients WHERE id=?', ('existing',))['name'], 'Cliente antigo')
                self.assertEqual(app.many('SELECT id FROM sales'), [])
            finally:
                app.close()


if __name__ == '__main__':
    unittest.main()
