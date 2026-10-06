---
id: 0005-klimaa-ajustes-de-acompanhamento-da-sincronizacao
title: 'klimaa: ajustes de acompanhamento da sincronização com o Drive'
repo: 'gaia-ufpel/confortimetro_klimaa_simulacoes'
type: codigo
agent: 'merge-task'
priority: baixa
created: 2026-10-06T18:18:20Z
updated: 2026-10-06T18:24:54Z
briefing_hash: 5bd65330732f84aa4d8a49d2ee2818d47186358ee2c49b03df560d739f6156fb
approved: '2026-10-06T18:18:21Z'
panel: 'merge-klimaa-drive-ajustes'
next: 'APROVADO em ver-klimaa-drive-ajustes, PENDENCIAS: nenhuma: merge-klimaa-drive-ajustes na fila'
---

## Request

## Briefing

### 2026-10-06T18:18:20Z
Você é AGENTE (não orquestrador): não delegue, não pergunte, não amplie escopo.
Repo: /mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes/.agents/worktrees/drive-ajustes (branch drive-ajustes, a partir de origin/main com a integração do Google Drive já mesclada em confortimetro/drive/). Ajustes de acompanhamento da revisão:
1. sync.py:40 incluir in.idf na lista de permitidos (respeitando o teto de tamanho), para execuções antigas sem modelo.idf manterem as superfícies do assistente (tools._zone_surfaces) após o pull.
2. sync.py:244 recriar execução com mesmo nome não pode perder o run_id: preservar run_id quando a pasta local ainda tem o mesmo id (gravar o run_id num arquivo pequeno dentro da pasta da execução, ex. .ambiens-drive.json, e usá-lo como fonte); execução apagada localmente não volta pelo pull como "nome (2)".
3. sync.py:451 sync_all não pode engolir DriveError de gravação do estado no pull: virar status de erro visível, como no push.
4. sync.py:217 aviso de arquivo acima do teto logado uma vez por execução por sessão, não a cada chamada.
5. auth.py:120 estreitar o except AttributeError ao caso do timeout.
6. sync.py:82/87 Optional explícito nas assinaturas.
Teste em tests/test_drive.py para 1, 2 e 3.
Pronto quando: `/mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes/.venv/bin/python -m pytest tests -q` passa na worktree e há commit na branch drive-ajustes. Não faça merge nem push.
Devolva: comandos rodados + saída, diff resumido por item.
Pare e relate se: precisar de credencial real ou de decisão de produto não coberta.

## History

- 2026-10-06T18:18:20Z — todo (created)

- 2026-10-06T18:18:21Z — briefing aprovado pelo dono (sha256 5bd65330732f)

- 2026-10-06T18:18:23Z — doing

- 2026-10-06T18:22:19Z — doing

- 2026-10-06T18:24:52Z — doing

- 2026-10-06T18:24:54Z — doing
