# Teste funcional local

Esta etapa roda em um computador com Python 3.12; o GitHub guarda o código e executa testes, mas não hospeda a aplicação. O banco criado para este teste fica apenas no computador.

1. Baixe o código do repositório e, na pasta do projeto, execute `python -m agencyos setup --username owner`. Defina uma senha de ao menos 12 caracteres.
2. Execute `python -m agencyos serve` e abra `http://127.0.0.1:8000` no navegador do mesmo computador.
3. Entre, abra **Projetos** e registre um cliente fictício.
4. Em **Pipeline**, registre uma oportunidade fictícia com fonte `teste manual` e crie o rascunho.
5. Em **Aprovações**, edite o texto e revise antes de aprovar. Em **Propostas**, registre o envio manual usando uma referência de teste, sem enviar mensagens reais.
6. Volte ao **Pipeline**, confirme a venda fictícia com o cliente cadastrado, abra o projeto e adicione uma tarefa.
7. Conclua a tarefa com uma descrição de evidência. Em **Atividade**, confira eventos, execuções e evidências. Reinicie o servidor e confira se os dados persistiram.

Use apenas dados fictícios durante o teste. Para apagar o teste, pare o servidor e remova `data/agencyos.sqlite3`. Não remova esse arquivo caso contenha trabalho real.
