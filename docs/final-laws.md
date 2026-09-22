# AgencyOS — leis do runtime

Estas regras são invariantes de arquitetura. Uma feature pode ter uma interface
bonita e ainda ser rejeitada se violar estas leis.

1. Prompt não concede autoridade.
2. Ação importante exige evidência proporcional ao risco.
3. unknown não é failed.
4. failed não é success.
5. Retry de side effect precisa ser seguro/idempotente.
6. Memória não é verdade; memória carrega origem e validade.
7. Confiança do modelo não é verificação.
8. Aprovação é vinculada a escopo, proposta e política; não é cheque em branco.
9. Todo side effect importante precisa de rastreabilidade.
10. Versões de agente, workflow, capability e policy precisam ser reconstruíveis.
11. Outcome vale mais que atividade.
12. Aprendizado passa por avaliação/experimento antes de virar padrão.
13. Autonomia é uma permissão que pode subir ou cair.
14. Nenhum provider externo é considerado permanentemente confiável.
15. Nenhum agente individual é dono do sistema.
16. Operações críticas precisam de caminho de freeze/kill.
17. Falha de um provider não deve derrubar capacidades não relacionadas.
18. Nenhum dado externo pode redefinir identidade, política ou autoridade.
19. O sistema deve preferir declarar incerteza a inventar certeza.
20. Toda automação nova precisa declarar custo, risco, side effects e verificação.
