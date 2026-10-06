---
id: 0004-klimaa-integracao-e-compartilhamento-com-google
title: 'klimaa: integração e compartilhamento com Google Drive'
repo: 'gaia-ufpel/confortimetro_klimaa_simulacoes'
type: codigo
agent: 'claude'
priority: media
created: 2026-10-06T17:23:10Z
updated: 2026-10-06T18:08:57Z
briefing_hash: aec10db8ab8ae45ccc2beb7b3fcbff737424bf75ed24452ebc2e929fdb70638a
approved: '2026-10-06T17:57:29Z'
panel: 'klimaa-drive-sync-fix2'
next: 'orquestrador: agente parado com launch --parar'
---

## Request

## Briefing

### 2026-10-06T17:57:28Z
Você é AGENTE (não orquestrador): não delegue, não pergunte, não amplie escopo.
Repo: /mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes/.agents/worktrees/drive-sync (branch drive-sync, commit b076afc já tem a implementação do Drive). A revisão REPROVOU. Corrija TODOS os achados abaixo (o orquestrador promoveu os opcionais a obrigatórios), com teste em tests/test_drive.py para cada um que tiver lógica, e faça commit.

1. sync.py:346 push_after_run ignora state['pending']: ao terminar uma simulação, enviar também as execuções pendentes (mesma thread de fundo). Docstring e PROJETO.md devem bater com o comportamento.
2. sync.py:34 espelho envia eplusout.err/.csv/.sql (há .err de 1,5 GB): trocar por lista de permitidos dos artefatos de resultado (xlsx, imagens/gráficos, html, configs.json e o que mais a UI do histórico precisar para mostrar a execução após o pull) + teto de tamanho por arquivo (constante, ex. 50 MB; acima disso pula e registra no log). Confirme no código do histórico/results quais arquivos são necessários para a execução aparecer e abrir depois do pull.
3. sync.py:236 push_run marca 'enviando' e grava estado 2x sem mudança: só marcar/gravar quando houver arquivo a enviar.
4. sync.py:358 conta no estado sem token no keyring: marcar reconnect e a UI pedir reconexão.
5. sync.py:251 reconnect=True nunca limpo: limpar após push/login bem-sucedido.
6. sync.py:192 estado indexado só pelo nome da pasta: execuções homônimas de máquinas diferentes colidem. Gravar um id único da execução (uuid) em appProperties da pasta remota e no estado; adotar pasta remota só com mesmo id; nome colidindo com id diferente → pasta remota com sufixo (ex. "run_001 (2)") e pull para pasta local com sufixo. Nunca sobrescrever arquivos de outra execução.
7. sync.py:63 os.replace no Windows pode dar PermissionError: tentar de novo algumas vezes com espera curta; erro final vira status de erro visível, não engolido.
8. auth.py:113 timeout de login (300 s) gera AttributeError cru: traduzir para DriveError com mensagem em pt-BR.

Pronto quando: `/mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes/.venv/bin/python -m pytest tests -q` passa na worktree; `python -c "import confortimetro.gui.main_window"` importa sem cliente OAuth; commit na branch drive-sync. Não faça merge nem push.
Devolva: comandos rodados + saída, diff resumido por achado.
Pare e relate se: precisar de credencial real ou de decisão de produto não coberta.

## History

- 2026-10-06T17:23:10Z — todo (created)

- 2026-10-06T17:23:14Z — briefing aprovado pelo dono (sha256 a80dbbd2bfe3)

- 2026-10-06T17:23:32Z — briefing aprovado pelo dono (sha256 9c919aef5290)

- 2026-10-06T17:23:38Z — doing

- 2026-10-06T17:47:48Z — doing

- 2026-10-06T17:56:46Z — doing

- 2026-10-06T17:56:48Z — doing

- 2026-10-06T17:57:06Z — blocked

- 2026-10-06T17:57:29Z — briefing aprovado pelo dono (sha256 aec10db8ab8a)

- 2026-10-06T17:57:33Z — doing
