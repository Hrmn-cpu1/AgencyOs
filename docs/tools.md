# Decisões de ferramentas nesta fase

| Ferramenta | Função e integração | Licença / custo | API, MCP, hospedagem, segurança, alternativa |
|---|---|---|---|
| Python 3.12 (biblioteca padrão) | API HTTP, Orchestrator e testes; sem dependência externa | PSF; software sem cobrança, servidor custa à parte | APIs internas neste repositório; MCP não aplicável; hospedável pelo operador; manter runtime corrigido; alternativa futura: framework HTTP maduro |
| SQLite (embutido no Python) | Estado persistente com transações e chaves estrangeiras | Domínio público; sem cobrança, storage custa à parte | SQL local, sem MCP; volume persistente e backups são necessários; não atende múltiplas instâncias; alternativa PostgreSQL |
| GitHub Actions | Testes em push e PR | Serviço GitHub; consumo sujeito ao plano da conta | Workflow YAML, sem MCP no runtime; não colocar secrets de produção na CI; alternativa: outra CI |

Não foram adotados agentes de IA, provedores de modelo, automações de marketplace, crawlers, SEO, CRM ou ferramentas de ads. A integração dependerá da capacidade e das regras verificadas de cada serviço. O conector manual deixa registrar oportunidades do VintePila sem afirmar acesso automático, usar APIs inexistentes ou disparar mensagens. Custos e licenças de produtos não incluídos serão verificados quando uma integração concreta for implementada.
