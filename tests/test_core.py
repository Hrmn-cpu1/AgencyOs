import tempfile
import unittest
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
        self.app.decide(self.actor, draft['approval_id'], 'approved')
        project = self.app.create_project(self.actor, opportunity, {})['id']
        task = self.app.create_task(self.actor, project, {'title':'Auditar site'})['id']
        with self.assertRaises(Problem):
            self.app.complete_task(self.actor, task, {'evidence':''})
        self.app.complete_task(self.actor, task, {'evidence':'Checklist revisado'})
        self.assertEqual(self.app.one('SELECT status FROM tasks WHERE id=?', (task,))['status'], 'done')
        self.assertGreaterEqual(len(self.app.dashboard()['events']), 9)
        self.assertGreaterEqual(len(self.app.dashboard()['evidence']), 4)
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

    def test_auth_and_rbac(self):
        with self.assertRaises(Problem):
            self.app.login('owner', 'incorrect-password')
        with self.assertRaises(Problem):
            self.app.bootstrap('another', 'long-password-for-tests')
        with self.assertRaises(Problem) as error:
            self.app.authorize({'role':'operator'}, 'approve')
        self.assertEqual(error.exception.status, 403)


if __name__ == '__main__':
    unittest.main()
