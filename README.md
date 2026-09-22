# AgencyOS

Fundação operacional de uma agência digital. O fluxo funcional começa com uma oportunidade inserida manualmente, gera um rascunho de proposta editável, exige aprovação do proprietário, registra o envio feito fora do sistema e a confirmação da venda antes de abrir um projeto. Tarefas exigem evidência para conclusão. A interface se adapta às telas de celular. O processamento e a base ficam no servidor.

## Executar localmente

Requer Python 3.12, sem pacotes externos.

```bash
python -m agencyos setup --username owner
python -m agencyos serve
```

Abra `http://127.0.0.1:8000`. O primeiro comando pede uma senha de pelo menos 12 caracteres sem gravá-la no terminal nem no repositório. O banco SQLite fica em `data/agencyos.sqlite3`. Faça backup desse arquivo com o serviço parado ou usando a API de backup do SQLite.

```bash
python -m unittest discover -s tests -v
```

## Escopo entregue

- Login com sessão de 12 horas, senha scrypt, token de sessão armazenado apenas como hash, cookie HttpOnly e proteção CSRF.
- Oportunidade por conector manual, rascunho determinístico editável com versões, decisão humana, registro manual de envio, confirmação da venda vinculada a cliente, projeto, tarefas e comprovação de conclusão.
- Registro persistente de execuções, eventos e evidências. Alteração e evento são gravados na mesma transação.
- Contratos Python para Worker, Skill, Tool e Connector, com registro explícito no Orchestrator.
- Painel responsivo de oportunidades, aprovações, projetos e atividade.
- Testes de fluxo, persistência, autenticação e API HTTP na CI.

**Estado real:** o rascunho usa um modelo de texto, sem IA; nenhuma proposta é enviada automaticamente. O registro de envio e o aceite são declarações do operador acompanhadas de texto de evidência, sem conferência externa. Plataformas de terceiros ainda não estão integradas. Nenhuma credencial de terceiros é necessária nesta fase. O aplicativo não está implantado na nuvem. Consulte [roteiro de teste](docs/testing.md), [arquitetura](docs/architecture.md), [decisões de ferramentas](docs/tools.md) e [próximos passos](docs/roadmap.md).

## Acesso pelo celular

Para um teste rápido com o notebook e o celular na mesma rede Wi-Fi, siga [o guia de teste pelo celular](docs/mobile-test.md). O comando `python -m agencyos serve --lan-test` abre somente um modo temporário para a rede local. Use um banco e senha exclusivos de teste, sem dados reais.

Implante em um servidor persistente com HTTPS, proxy reverso e volume para o banco. Configure `AGENCYOS_HOST`, `AGENCYOS_PORT`, `AGENCYOS_DB` e `AGENCYOS_SECURE_COOKIE=1`; configure os backups, monitoramento e restrinja a rede antes de abrir acesso público. **Não exponha a porta HTTP diretamente na internet.** O servidor recusa escutar fora do loopback sem a configuração de cookie seguro. Esta primeira versão é indicada para um único operador e validação controlada; [arquitetura](docs/architecture.md) descreve o caminho para produção.
