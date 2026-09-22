# Arquitetura inicial

## Fluxo implementado

`manual connector → opportunity.discovered → sales worker → proposal_draft skill → proposal_template tool → run + evidence → revisão humana → aprovação do proprietário → registro de envio manual → confirmação da venda → project.created → task.created → task.completed + evidence`

O Control Plane é a API HTTP + tela responsiva; Worker/Execution Plane é o Orchestrator e seus registros; Connector Plane tem um conector manual real; Policy/Approval Plane bloqueia a conversão em projeto até a aprovação, registro de envio e confirmação do aceite; Evidence/Event Plane mantém registros de entrada, saída, execução e decisão em SQLite. O endpoint `/api/dashboard` alimenta o painel de observabilidade. O domínio guarda moedas como código ISO e valores opcionais em unidades mínimas inteiras. A interface começa em PT-BR; textos precisam ser externalizados antes de oferecer EN/ES. Ações automáticas de envio, publicação e gasto não existem nesta fase.

## Limites de extensão

`agencyos/contracts.py` define os Protocols de Worker, Skill, Tool e Connector e objetos Context/Result. `Orchestrator` registra implementações por nome. Um Connector novo deve declarar capacidades reais e gerar oportunidade com fonte, URL e evidência de entrada. Um Worker novo deve produzir Result e registrar run/evidence na transação. Adicione eventos de domínio com versão de payload antes de ligar sistemas externos; para entrega confiável entre processos, adicione outbox transacional e consumidores idempotentes.

## Dados e integridade

`agencyos/schema.sql` modela users, sessions, clients, opportunities, proposals, proposal_revisions, approvals, proposal_dispatches, sales, projects, tasks, runs, evidence e events. As novas tabelas usam `CREATE TABLE IF NOT EXISTS` para preservar bancos da primeira versão. Chaves estrangeiras, unicidade e transações protegem o fluxo. `budget_minor` guarda unidade mínima e não representa receita recebida; `sales.amount_minor` é valor declarado e não significa pagamento recebido. A venda exige confirmação expressa, e abrir projeto é uma ação posterior. O histórico de eventos e as revisões são append-only na API, sem endpoint de exclusão.

## Segurança e produção

Bootstrap interativo cria um único owner. API exige sessão; mutações exigem CSRF e origem compatível quando o navegador fornece Origin. Apenas owner pode aprovar; há limite simples por IP no login. HTML gerado no painel escapa conteúdo recebido. Não há cadastro aberto. Secrets não devem entrar no Git. O limite de login está em memória e não atende múltiplas réplicas. Para produção pública: proxy HTTPS confiável, cabeçalhos de host permitidos, rate limiting distribuído, logs estruturados com retenção, backups testados, alertas, gestão de operadores, migrações e PostgreSQL com isolamento por cliente. SQLite permite validar um processo, mas não serve para escala distribuída. Trocar de banco requer camada de repositório e migração dos dados; não é uma troca de configuração.
