"""Transactional application service. All state changes and their audit events commit together."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .contracts import Context, Result


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid.uuid4().hex


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def require_text(data, key, limit=200):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise Problem(f'{key}: texto obrigatório, até {limit} caracteres')
    return value.strip()


def optional_text(data, key, limit=2000):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value) > limit:
        raise Problem(f'{key}: texto de até {limit} caracteres')
    return value.strip()


class ManualConnector:
    name = 'manual'

    def capabilities(self):
        return {'ingest': True, 'search': False, 'send': False}

    def ingest(self, payload):
        return {'title': require_text(payload, 'title'),
                'source': require_text(payload, 'source', 100),
                'source_url': optional_text(payload, 'source_url', 500),
                'notes': optional_text(payload, 'notes')}


class ProposalTool:
    name = 'proposal_template'

    def execute(self, context):
        opportunity = context.input
        content = (f"Olá! Vi a oportunidade: {opportunity['title']}.\n\n"
                   "Podemos alinhar objetivos, escopo, prazo e critérios de aceitação antes de fechar a proposta. "
                   "Qual é o resultado esperado e a data desejada?\n\n"
                   "Rascunho para revisão humana. Preço e prazo ainda não foram definidos.")
        return Result({'content': content}, {'method': 'deterministic_template',
                                              'source_opportunity_id': opportunity['id']})


class ProposalSkill:
    name = 'proposal_draft'

    def perform(self, context, tools):
        return tools['proposal_template'].execute(context)


class SalesWorker:
    name = 'sales'

    def run(self, context, skills, tools):
        return skills['proposal_draft'].perform(context, tools)


class Orchestrator:
    def __init__(self):
        self.tools = {'proposal_template': ProposalTool()}
        self.skills = {'proposal_draft': ProposalSkill()}
        self.workers = {'sales': SalesWorker()}
        self.connectors = {'manual': ManualConnector()}

    def execute(self, worker, skill, tool, context):
        if worker not in self.workers or skill not in self.skills or tool not in self.tools:
            raise Problem('worker, skill ou tool não registrado')
        return self.workers[worker].run(context, self.skills, self.tools)


class Agency:
    def __init__(self, db_path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.executescript(Path(__file__).with_name('schema.sql').read_text())
        self.orchestrator = Orchestrator()

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        with self.lock:
            try:
                self.db.execute('BEGIN IMMEDIATE')
                yield
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def one(self, sql, args=()):
        row = self.db.execute(sql, args).fetchone()
        return dict(row) if row else None

    def many(self, sql, args=()):
        return [dict(row) for row in self.db.execute(sql, args).fetchall()]

    def event(self, kind, actor, subject_type, subject_id, payload=None):
        self.db.execute('INSERT INTO events(type,actor_id,subject_type,subject_id,payload_json,created_at) VALUES(?,?,?,?,?,?)',
                        (kind, actor, subject_type, subject_id, encoded(payload or {}), now()))

    def evidence(self, run_id, subject_type, subject_id, kind, data):
        self.db.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?)',
                        (uid(), run_id, subject_type, subject_id, kind, encoded(data), now()))

    def bootstrap(self, username, password):
        if not re.fullmatch(r'[a-zA-Z0-9_.-]{3,40}', username) or len(password) < 12:
            raise Problem('usuário inválido ou senha com menos de 12 caracteres')
        with self.transaction():
            if self.one('SELECT id FROM users LIMIT 1'):
                raise Problem('proprietário já configurado', 409)
            salt = secrets.token_hex(16)
            digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1).hex()
            user_id = uid()
            self.db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',
                            (user_id, username, digest, salt, 'owner', now()))
            self.event('user.bootstrapped', user_id, 'user', user_id)

    def login(self, username, password):
        with self.lock:
            user = self.one('SELECT * FROM users WHERE username=?', (username,))
            salt = user['salt'] if user else '00' * 16
            digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1).hex()
            if not user or not hmac.compare_digest(digest, user['password_hash']):
                raise Problem('credenciais inválidas', 401)
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        expires = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        with self.transaction():
            self.db.execute('INSERT INTO sessions VALUES(?,?,?,?)',
                            (hashlib.sha256(token.encode()).hexdigest(), user['id'], csrf, expires))
            self.event('session.created', user['id'], 'user', user['id'])
        return token, csrf

    def session(self, token):
        if not token:
            raise Problem('autenticação necessária', 401)
        with self.lock:
            user = self.one('SELECT users.id,users.username,users.role,sessions.csrf FROM sessions JOIN users ON users.id=sessions.user_id WHERE sessions.token_hash=? AND sessions.expires_at>?',
                            (hashlib.sha256(token.encode()).hexdigest(), now()))
        if not user:
            raise Problem('sessão expirada', 401)
        return user

    def logout(self, token, actor):
        with self.transaction():
            self.db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))
            self.event('session.deleted', actor, 'user', actor)

    def authorize(self, user, action):
        roles = {'read': {'owner', 'operator', 'viewer'},
                 'write': {'owner', 'operator'}, 'approve': {'owner'}}
        if user['role'] not in roles[action]:
            raise Problem('permissão insuficiente', 403)

    def create_client(self, actor, data):
        name = require_text(data, 'name')
        website = optional_text(data, 'website', 500)
        notes = optional_text(data, 'notes')
        if website and not website.startswith('https://'):
            raise Problem('website precisa começar com https://')
        client_id = uid()
        with self.transaction():
            self.db.execute('INSERT INTO clients VALUES(?,?,?,?,?)', (client_id, name, website, notes, now()))
            self.event('client.created', actor, 'client', client_id)
        return {'id': client_id}

    def create_opportunity(self, actor, data):
        normalized = self.orchestrator.connectors['manual'].ingest(data)
        url = normalized['source_url']
        if url and not url.startswith('https://'):
            raise Problem('source_url precisa começar com https://')
        currency = data.get('currency', 'BRL')
        if currency not in ('BRL', 'GBP', 'USD', 'EUR'):
            raise Problem('moeda não suportada')
        budget = data.get('budget_minor')
        if budget is not None and (type(budget) is not int or not 0 <= budget <= 10**12):
            raise Problem('budget_minor precisa ser inteiro não negativo')
        opportunity_id = uid()
        with self.transaction():
            self.db.execute('INSERT INTO opportunities VALUES(?,?,?,?,?,?,?,?,?)',
                            (opportunity_id, normalized['title'], normalized['source'], url,
                             budget, currency, normalized['notes'], 'discovered', now()))
            self.event('opportunity.discovered', actor, 'opportunity', opportunity_id,
                       {'connector': 'manual', 'source': normalized['source']})
            self.evidence(None, 'opportunity', opportunity_id, 'manual_input', normalized)
        return {'id': opportunity_id}

    def draft_proposal(self, actor, opportunity_id):
        with self.transaction():
            opportunity = self.one('SELECT * FROM opportunities WHERE id=?', (opportunity_id,))
            if not opportunity:
                raise Problem('oportunidade não encontrada', 404)
            if opportunity['status'] in ('approved', 'converted'):
                raise Problem('oportunidade já aprovada ou convertida', 409)
            if self.one("SELECT approvals.id FROM approvals JOIN proposals ON proposals.id=approvals.subject_id WHERE proposals.opportunity_id=? AND approvals.status='pending'", (opportunity_id,)):
                raise Problem('já existe proposta pendente', 409)
            run_id, proposal_id, approval_id = uid(), uid(), uid()
            input_data = dict(opportunity)
            self.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (run_id, actor, 'sales', 'proposal_draft', 'proposal_template',
                             encoded(input_data), None, 'running', now(), None))
            try:
                result = self.orchestrator.execute('sales', 'proposal_draft', 'proposal_template',
                                                   Context(actor, run_id, input_data))
            except Exception:
                self.db.execute('UPDATE runs SET status=?,finished_at=? WHERE id=?', ('failed', now(), run_id))
                self.event('run.failed', actor, 'run', run_id)
                raise
            self.db.execute('UPDATE runs SET status=?,output_json=?,finished_at=? WHERE id=?',
                            ('completed', encoded(result.output), now(), run_id))
            self.db.execute('INSERT INTO proposals VALUES(?,?,?,?,?,?)',
                            (proposal_id, opportunity_id, result.output['content'], 'pending', now(), None))
            self.db.execute('INSERT INTO proposal_revisions VALUES(?,?,?,?,?)',
                            (uid(), proposal_id, result.output['content'], actor, now()))
            self.db.execute("UPDATE opportunities SET status='drafted' WHERE id=?", (opportunity_id,))
            self.db.execute('INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (approval_id, 'proposal', proposal_id, 'human_approval_before_external_send',
                             'pending', actor, None, None, now(), None))
            self.evidence(run_id, 'proposal', proposal_id, 'generated_draft', result.evidence)
            self.event('proposal.generated', actor, 'proposal', proposal_id, {'run_id': run_id})
            self.event('approval.requested', actor, 'approval', approval_id, {'proposal_id': proposal_id})
        return {'id': proposal_id, 'approval_id': approval_id, 'run_id': run_id}

    def revise_proposal(self, actor, proposal_id, data):
        content = require_text(data, 'content', 10000)
        with self.transaction():
            proposal = self.one('SELECT * FROM proposals WHERE id=?', (proposal_id,))
            if not proposal:
                raise Problem('proposta não encontrada', 404)
            if proposal['status'] != 'pending':
                raise Problem('só é possível editar uma proposta pendente', 409)
            if proposal['content'] == content:
                raise Problem('nenhuma alteração no conteúdo', 409)
            self.db.execute('UPDATE proposals SET content=? WHERE id=?', (content, proposal_id))
            self.db.execute('INSERT INTO proposal_revisions VALUES(?,?,?,?,?)',
                            (uid(), proposal_id, content, actor, now()))
            self.evidence(None, 'proposal', proposal_id, 'human_revision',
                          {'actor_id': actor, 'sha256': hashlib.sha256(content.encode()).hexdigest()})
            self.event('proposal.revised', actor, 'proposal', proposal_id)
        return {'id': proposal_id, 'status': 'pending'}

    def decide(self, actor, approval_id, decision, reason=''):
        if decision not in ('approved', 'rejected'):
            raise Problem('decisão inválida')
        if not isinstance(reason, str) or len(reason) > 1000:
            raise Problem('motivo inválido')
        with self.transaction():
            approval = self.one('SELECT * FROM approvals WHERE id=?', (approval_id,))
            if not approval:
                raise Problem('aprovação não encontrada', 404)
            if approval['status'] != 'pending':
                raise Problem('aprovação já decidida', 409)
            self.db.execute('UPDATE approvals SET status=?,decided_by=?,reason=?,decided_at=? WHERE id=?',
                            (decision, actor, reason, now(), approval_id))
            if approval['subject_type'] == 'proposal':
                self.db.execute('UPDATE proposals SET status=?,decided_at=? WHERE id=?',
                                (decision, now(), approval['subject_id']))
                if decision == 'approved':
                    opportunity = self.one('SELECT opportunity_id FROM proposals WHERE id=?', (approval['subject_id'],))
                    self.db.execute("UPDATE opportunities SET status='approved' WHERE id=?", (opportunity['opportunity_id'],))
            self.evidence(None, 'approval', approval_id, 'human_decision',
                          {'decision': decision, 'reason': reason, 'actor_id': actor})
            self.event('approval.' + decision, actor, 'approval', approval_id)
            self.event('proposal.' + decision, actor, 'proposal', approval['subject_id'])
        return {'status': decision}

    def record_dispatch(self, actor, proposal_id, data):
        channel = require_text(data, 'channel', 100)
        reference = require_text(data, 'reference', 1000)
        with self.transaction():
            proposal = self.one('SELECT * FROM proposals WHERE id=?', (proposal_id,))
            if not proposal:
                raise Problem('proposta não encontrada', 404)
            if proposal['status'] != 'approved':
                raise Problem('proposta precisa estar aprovada', 409)
            if self.one('SELECT id FROM proposal_dispatches WHERE proposal_id=?', (proposal_id,)):
                raise Problem('envio já registrado', 409)
            dispatch_id = uid()
            self.db.execute('INSERT INTO proposal_dispatches VALUES(?,?,?,?,?,?)',
                            (dispatch_id, proposal_id, channel, reference, actor, now()))
            self.evidence(None, 'proposal', proposal_id, 'manual_dispatch',
                          {'channel': channel, 'reference': reference, 'actor_id': actor})
            self.event('proposal.dispatch_recorded', actor, 'proposal', proposal_id,
                       {'dispatch_id': dispatch_id, 'channel': channel})
        return {'id': dispatch_id}

    def confirm_sale(self, actor, opportunity_id, data):
        client_id = require_text(data, 'client_id', 32)
        confirmation = require_text(data, 'confirmation', 2000)
        amount = data.get('amount_minor')
        if amount is not None and (type(amount) is not int or not 0 <= amount <= 10**12):
            raise Problem('amount_minor precisa ser inteiro não negativo')
        with self.transaction():
            opportunity = self.one('SELECT * FROM opportunities WHERE id=?', (opportunity_id,))
            if not opportunity:
                raise Problem('oportunidade não encontrada', 404)
            if opportunity['status'] != 'approved':
                raise Problem('oportunidade precisa ter proposta aprovada', 409)
            if not self.one('SELECT id FROM clients WHERE id=?', (client_id,)):
                raise Problem('cliente não encontrado', 404)
            proposal = self.one('''SELECT proposals.id FROM proposals JOIN proposal_dispatches
                                   ON proposals.id=proposal_dispatches.proposal_id
                                   WHERE proposals.opportunity_id=? AND proposals.status='approved'
                                   ORDER BY proposal_dispatches.created_at DESC LIMIT 1''', (opportunity_id,))
            if not proposal:
                raise Problem('registre o envio manual da proposta antes de confirmar a venda', 409)
            if self.one('SELECT id FROM sales WHERE opportunity_id=?', (opportunity_id,)):
                raise Problem('venda já confirmada', 409)
            sale_id = uid()
            self.db.execute('INSERT INTO sales VALUES(?,?,?,?,?,?,?,?,?)',
                            (sale_id, opportunity_id, proposal['id'], client_id, confirmation,
                             amount, opportunity['currency'], actor, now()))
            self.evidence(None, 'sale', sale_id, 'human_confirmation',
                          {'confirmation': confirmation, 'actor_id': actor})
            self.event('sale.confirmed', actor, 'sale', sale_id,
                       {'opportunity_id': opportunity_id, 'proposal_id': proposal['id']})
        return {'id': sale_id}

    def create_project(self, actor, opportunity_id, data):
        with self.transaction():
            opportunity = self.one('SELECT * FROM opportunities WHERE id=?', (opportunity_id,))
            if not opportunity:
                raise Problem('oportunidade não encontrada', 404)
            if opportunity['status'] != 'approved':
                raise Problem('proposta precisa estar aprovada', 409)
            sale = self.one('SELECT * FROM sales WHERE opportunity_id=?', (opportunity_id,))
            if not sale:
                raise Problem('confirme a venda antes de abrir o projeto', 409)
            project_id = uid()
            self.db.execute('INSERT INTO projects VALUES(?,?,?,?,?,?)',
                            (project_id, opportunity_id, sale['client_id'], opportunity['title'], 'active', now()))
            self.db.execute("UPDATE opportunities SET status='converted' WHERE id=?", (opportunity_id,))
            self.event('project.created', actor, 'project', project_id,
                       {'opportunity_id': opportunity_id, 'sale_id': sale['id']})
        return {'id': project_id}

    def create_task(self, actor, project_id, data):
        title = require_text(data, 'title')
        with self.transaction():
            if not self.one('SELECT id FROM projects WHERE id=?', (project_id,)):
                raise Problem('projeto não encontrado', 404)
            task_id = uid()
            self.db.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?)', (task_id, project_id, title, 'todo', now(), None))
            self.event('task.created', actor, 'task', task_id, {'project_id': project_id})
        return {'id': task_id}

    def complete_task(self, actor, task_id, data):
        description = require_text(data, 'evidence', 2000)
        with self.transaction():
            task = self.one('SELECT * FROM tasks WHERE id=?', (task_id,))
            if not task:
                raise Problem('tarefa não encontrada', 404)
            if task['status'] != 'todo':
                raise Problem('tarefa já concluída', 409)
            self.evidence(None, 'task', task_id, 'completion', {'description': description})
            self.db.execute("UPDATE tasks SET status='done',completed_at=? WHERE id=?", (now(), task_id))
            self.event('task.completed', actor, 'task', task_id)
        return {'status': 'done'}

    def dashboard(self):
        with self.lock:
            return {key: self.many(f'SELECT * FROM {table} ORDER BY created_at DESC LIMIT 100') for key, table in (
                ('opportunities', 'opportunities'), ('proposals', 'proposals'),
                ('approvals', 'approvals'), ('clients', 'clients'),
                ('projects', 'projects'), ('tasks', 'tasks'), ('runs', 'runs'),
                ('sales', 'sales'), ('dispatches', 'proposal_dispatches'),
                ('revisions', 'proposal_revisions'))} | {
                'events': self.many('SELECT * FROM events ORDER BY id DESC LIMIT 100'),
                'evidence': self.many('SELECT * FROM evidence ORDER BY created_at DESC LIMIT 100'),
                'connectors': [{'name': connector.name, 'capabilities': connector.capabilities()} for connector in self.orchestrator.connectors.values()],
            }
