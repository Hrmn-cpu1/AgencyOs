let csrf = '';
let state = {};
let role = '';
const $ = id => document.getElementById(id);
const notice = message => { $('notice').textContent = message; setTimeout(() => { if ($('notice').textContent === message) $('notice').textContent = ''; }, 6000); };
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

async function api(path, body) {
  const response = await fetch(path, {method: body === undefined ? 'GET' : 'POST', credentials:'same-origin',
    headers: body === undefined ? {} : {'Content-Type':'application/json','X-CSRF-Token':csrf},
    body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw Error(data.error || `HTTP ${response.status}`);
  return data;
}

async function refresh() {
  state = await api('/api/dashboard');
  const pending = state.approvals.filter(item => item.status === 'pending').length;
  $('stats').innerHTML = [[state.opportunities.length,'Oportunidades'],[pending,'Aprovações'],[state.projects.length,'Projetos']]
    .map(([number,label]) => `<div class="stat"><strong>${number}</strong><small>${label}</small></div>`).join('');
  $('opportunities').innerHTML = state.opportunities.map(item => {
    const proposals = state.proposals.filter(p => p.opportunity_id === item.id);
    const pendingApproval = state.approvals.some(a => a.status === 'pending' && proposals.some(p => p.id === a.subject_id));
    const dispatched = state.dispatches.some(d => proposals.some(p => p.id === d.proposal_id));
    const sale = state.sales.find(s => s.opportunity_id === item.id);
    const clientOptions = state.clients.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
    return `<article class="card"><span class="badge">${escapeHtml(item.status)}</span><h3>${escapeHtml(item.title)}</h3><p class="meta">${escapeHtml(item.source)} · ${escapeHtml(item.currency)}${item.budget_minor === null ? '' : ' · ' + (item.budget_minor/100).toFixed(2)}</p><p>${escapeHtml(item.notes)}</p><div class="actions">${(item.status === 'discovered' || item.status === 'drafted') && !pendingApproval ? `<button data-action="draft" data-id="${item.id}">Criar rascunho</button>` : ''}</div>${item.status === 'approved' && dispatched && !sale && role === 'owner' ? `<details><summary>Confirmar venda</summary><form data-form="sale" data-id="${item.id}" class="stack"><label>Cliente<select name="client_id" required><option value="">Selecione</option>${clientOptions}</select></label><label>Valor confirmado (${escapeHtml(item.currency)})<input name="amount" type="number" min="0" step="0.01" placeholder="Opcional"></label><label>Comprovação da venda<textarea name="confirmation" maxlength="2000" required placeholder="Descreva o aceite recebido"></textarea></label><button>Confirmar venda</button></form></details>` : ''}${sale ? `<p class="meta">Venda confirmada · ${escapeHtml(sale.currency)}${sale.amount_minor === null ? '' : ' ' + (sale.amount_minor / 100).toFixed(2)}</p>${item.status !== 'converted' ? `<button data-action="project" data-id="${item.id}">Abrir projeto</button>` : ''}` : ''}</article>`;
  }).join('') || '<p>Nenhuma oportunidade cadastrada.</p>';
  $('approvalList').innerHTML = state.approvals.filter(item => item.status === 'pending').map(item => {
    const proposal = state.proposals.find(p => p.id === item.subject_id);
    const versions = state.revisions.filter(r => r.proposal_id === item.subject_id).length;
    return `<article class="card"><span class="badge">Aguardando revisão · versão ${versions}</span><p class="content">${escapeHtml(proposal?.content)}</p>${role === 'owner' ? `<div class="actions"><button data-action="approve" data-id="${item.id}">Aprovar rascunho</button><button data-action="reject" data-id="${item.id}" class="danger">Rejeitar</button></div>` : ''}</article>`;
  }).join('') || '<p>Nenhuma aprovação pendente.</p>';
  $('proposals').innerHTML = state.proposals.map(item => {
    const dispatch = state.dispatches.find(d => d.proposal_id === item.id);
    const history = state.revisions.filter(r => r.proposal_id === item.id);
    return `<article class="card"><span class="badge">${escapeHtml(item.status)}</span><p class="content">${escapeHtml(item.content)}</p>${item.status === 'pending' ? `<details><summary>Editar antes de aprovar</summary><form data-form="revise" data-id="${item.id}" class="stack"><label>Texto da proposta<textarea name="content" rows="8" maxlength="10000" required>${escapeHtml(item.content)}</textarea></label><button>Salvar revisão</button></form></details>` : ''}<details><summary>Histórico de versões (${history.length})</summary>${history.map((revision, index) => `<div class="task"><p class="meta">Versão ${history.length - index} · ${escapeHtml(revision.created_at)}</p><p class="content">${escapeHtml(revision.content)}</p></div>`).join('')}</details>${item.status === 'approved' && !dispatch ? `<details><summary>Registrar envio feito por você</summary><form data-form="dispatch" data-id="${item.id}" class="stack"><label>Canal<input name="channel" required maxlength="100" placeholder="Ex.: e-mail"></label><label>Referência ou comprovante<input name="reference" required maxlength="1000" placeholder="Ex.: data e referência da conversa"></label><button>Registrar envio</button></form></details>` : ''}${dispatch ? `<p class="meta">Envio registrado: ${escapeHtml(dispatch.channel)} · ${escapeHtml(dispatch.reference)}</p>` : ''}</article>`;
  }).join('') || '<p>Nenhuma proposta.</p>';
  $('projectList').innerHTML = state.projects.map(item => `<article class="card"><h3>${escapeHtml(item.title)}</h3><span class="badge">${escapeHtml(item.status)}</span><div>${state.tasks.filter(t => t.project_id === item.id).map(t => `<div class="task"><p class="meta">${escapeHtml(t.status === 'done' ? '✓' : '○')} ${escapeHtml(t.title)}</p>${t.status === 'todo' ? `<details><summary>Concluir com evidência</summary><form data-form="complete" data-id="${t.id}" class="stack"><label>O que foi entregue?<textarea name="evidence" maxlength="2000" required></textarea></label><button>Concluir tarefa</button></form></details>` : ''}</div>`).join('')}</div><details><summary>Adicionar tarefa</summary><form data-form="task" data-id="${item.id}" class="stack"><label>Título<input name="title" maxlength="200" required></label><button>Adicionar tarefa</button></form></details></article>`).join('') || '<p>Nenhum projeto. Confirme uma venda para começar.</p>';
  $('events').innerHTML = state.events.map(item => `<article class="card"><strong>${escapeHtml(item.type)}</strong><p class="meta">${escapeHtml(item.created_at)} · ${escapeHtml(item.subject_type)} ${escapeHtml(item.subject_id.slice(0,8))}</p></article>`).join('') || '<p>Nenhum evento.</p>';
  $('runs').innerHTML = state.runs.map(item => `<article class="card"><strong>${escapeHtml(item.worker)} / ${escapeHtml(item.skill)}</strong><p class="meta">${escapeHtml(item.status)} · ${escapeHtml(item.tool)} · ${escapeHtml(item.created_at)}</p><p class="meta">Evidências da execução: ${state.evidence.filter(e => e.run_id === item.id).length}</p></article>`).join('') || '<p>Nenhuma execução.</p>';
  $('runs').innerHTML += `<details class="card"><summary>Evidências registradas (${state.evidence.length})</summary>${state.evidence.map(item => `<div class="task"><strong>${escapeHtml(item.kind)}</strong><p class="meta">${escapeHtml(item.subject_type)} · ${escapeHtml(item.created_at)}</p><p class="content">${escapeHtml(item.data_json)}</p></div>`).join('') || '<p>Nenhuma evidência.</p>'}</details>`;
}

async function start() {
  try {
    const user = await api('/api/me'); csrf = user.csrf; role = user.role;
    $('loginPanel').classList.add('hidden'); $('app').classList.remove('hidden'); $('logout').classList.remove('hidden');
    await refresh();
  } catch { $('loginPanel').classList.remove('hidden'); $('app').classList.add('hidden'); $('logout').classList.add('hidden'); }
}

if (location.protocol === 'http:' && !['127.0.0.1', 'localhost'].includes(location.hostname)) {
  $('lanNotice').classList.remove('hidden');
}

$('loginForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  try {
    const response = await api('/api/login', {username:form.get('username'),password:form.get('password')});
    csrf = response.csrf; event.currentTarget.reset(); await start();
  } catch(error) { notice(error.message); }
});

$('logout').addEventListener('click', async () => { try { await api('/api/logout', {}); csrf=''; await start(); } catch(error) { notice(error.message); } });

document.querySelectorAll('nav button').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('nav button').forEach(b => b.classList.toggle('selected', b === button));
  document.querySelectorAll('.tab').forEach(section => section.classList.toggle('hidden', section.id !== button.dataset.tab));
}));

$('opportunityForm').addEventListener('submit', async event => {
  event.preventDefault(); const form = new FormData(event.currentTarget); const budget = form.get('budget');
  const data = {title:form.get('title'),source:form.get('source'),source_url:form.get('source_url'),notes:form.get('notes'),currency:form.get('currency')};
  if (budget) data.budget_minor = Math.round(Number(budget)*100);
  try { await api('/api/opportunities', data); event.currentTarget.reset(); await refresh(); notice('Oportunidade registrada.'); } catch(error) { notice(error.message); }
});

$('clientForm').addEventListener('submit', async event => {
  event.preventDefault(); const form = new FormData(event.currentTarget);
  try { await api('/api/clients', Object.fromEntries(form)); event.currentTarget.reset(); await refresh(); notice('Cliente registrado.'); } catch(error) { notice(error.message); }
});

document.addEventListener('submit', async event => {
  const form = event.target.closest('form[data-form]'); if (!form) return;
  event.preventDefault();
  const button = form.querySelector('button'); button.disabled = true;
  const data = Object.fromEntries(new FormData(form));
  try {
    const id = form.dataset.id;
    switch (form.dataset.form) {
      case 'revise': await api(`/api/proposals/${id}/revise`, data); break;
      case 'dispatch': await api(`/api/proposals/${id}/dispatch`, data); break;
      case 'sale': {
        const body = {client_id:data.client_id, confirmation:data.confirmation};
        if (data.amount !== '') body.amount_minor = Math.round(Number(data.amount) * 100);
        await api(`/api/opportunities/${id}/sale`, body); break;
      }
      case 'task': await api(`/api/projects/${id}/tasks`, data); break;
      case 'complete': await api(`/api/tasks/${id}/complete`, data); break;
    }
    await refresh(); notice('Atualizado.');
  } catch(error) { notice(error.message); } finally { button.disabled = false; }
});

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-action]'); if (!button || button.disabled) return;
  button.disabled = true;
  try {
    const id = button.dataset.id;
    switch (button.dataset.action) {
      case 'draft': await api(`/api/opportunities/${id}/draft`, {}); break;
      case 'approve': case 'reject': await api(`/api/approvals/${id}/decision`, {decision:button.dataset.action === 'approve' ? 'approved' : 'rejected'}); break;
      case 'project': await api(`/api/opportunities/${id}/project`, {}); break;
    }
    await refresh(); notice('Atualizado.');
  } catch(error) { notice(error.message); } finally { button.disabled = false; }
});

start();
