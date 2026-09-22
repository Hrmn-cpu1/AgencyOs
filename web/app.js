let csrf = '';
let state = {};
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
  $('opportunities').innerHTML = state.opportunities.map(item => `<article class="card"><span class="badge">${escapeHtml(item.status)}</span><h3>${escapeHtml(item.title)}</h3><p class="meta">${escapeHtml(item.source)} · ${escapeHtml(item.currency)}${item.budget_minor === null ? '' : ' · ' + (item.budget_minor/100).toFixed(2)}</p><p>${escapeHtml(item.notes)}</p><div class="actions">${item.status !== 'converted' ? `<button data-action="draft" data-id="${item.id}">Criar rascunho</button>` : ''}${item.status === 'approved' ? `<button data-action="project" data-id="${item.id}" class="secondary">Abrir projeto</button>` : ''}</div></article>`).join('') || '<p>Nenhuma oportunidade cadastrada.</p>';
  $('approvalList').innerHTML = state.approvals.filter(item => item.status === 'pending').map(item => {
    const proposal = state.proposals.find(p => p.id === item.subject_id);
    return `<article class="card"><span class="badge">Aguardando revisão</span><p class="content">${escapeHtml(proposal?.content)}</p><div class="actions"><button data-action="approve" data-id="${item.id}">Aprovar rascunho</button><button data-action="reject" data-id="${item.id}" class="danger">Rejeitar</button></div></article>`;
  }).join('') || '<p>Nenhuma aprovação pendente.</p>';
  $('proposals').innerHTML = state.proposals.map(item => `<article class="card"><span class="badge">${escapeHtml(item.status)}</span><p class="content">${escapeHtml(item.content)}</p></article>`).join('') || '<p>Nenhuma proposta.</p>';
  $('projectList').innerHTML = state.projects.map(item => `<article class="card"><h3>${escapeHtml(item.title)}</h3><span class="badge">${escapeHtml(item.status)}</span><div>${state.tasks.filter(t => t.project_id === item.id).map(t => `<p class="meta">${escapeHtml(t.status === 'done' ? '✓' : '○')} ${escapeHtml(t.title)} ${t.status === 'todo' ? `<button data-action="complete" data-id="${t.id}" class="secondary">Concluir</button>` : ''}</p>`).join('')}</div><div class="actions"><button data-action="task" data-id="${item.id}">Adicionar tarefa</button></div></article>`).join('') || '<p>Nenhum projeto. Aprove uma proposta para começar.</p>';
  $('events').innerHTML = state.events.map(item => `<article class="card"><strong>${escapeHtml(item.type)}</strong><p class="meta">${escapeHtml(item.created_at)} · ${escapeHtml(item.subject_type)} ${escapeHtml(item.subject_id.slice(0,8))}</p></article>`).join('') || '<p>Nenhum evento.</p>';
  $('runs').innerHTML = state.runs.map(item => `<article class="card"><strong>${escapeHtml(item.worker)} / ${escapeHtml(item.skill)}</strong><p class="meta">${escapeHtml(item.status)} · ${escapeHtml(item.tool)} · ${escapeHtml(item.created_at)}</p><p class="meta">Evidências: ${state.evidence.filter(e => e.run_id === item.id).length}</p></article>`).join('') || '<p>Nenhuma execução.</p>';
}

async function start() {
  try {
    const user = await api('/api/me'); csrf = user.csrf;
    $('loginPanel').classList.add('hidden'); $('app').classList.remove('hidden'); $('logout').classList.remove('hidden');
    await refresh();
  } catch { $('loginPanel').classList.remove('hidden'); $('app').classList.add('hidden'); $('logout').classList.add('hidden'); }
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

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-action]'); if (!button || button.disabled) return;
  button.disabled = true;
  try {
    const id = button.dataset.id;
    switch (button.dataset.action) {
      case 'draft': await api(`/api/opportunities/${id}/draft`, {}); break;
      case 'approve': case 'reject': await api(`/api/approvals/${id}/decision`, {decision:button.dataset.action === 'approve' ? 'approved' : 'rejected'}); break;
      case 'project': await api(`/api/opportunities/${id}/project`, {}); break;
      case 'task': { const title = prompt('Título da tarefa:'); if (!title) break; await api(`/api/projects/${id}/tasks`, {title}); break; }
      case 'complete': { const evidence = prompt('Descreva a evidência da conclusão:'); if (!evidence) break; await api(`/api/tasks/${id}/complete`, {evidence}); break; }
    }
    await refresh(); notice('Atualizado.');
  } catch(error) { notice(error.message); } finally { button.disabled = false; }
});

start();
