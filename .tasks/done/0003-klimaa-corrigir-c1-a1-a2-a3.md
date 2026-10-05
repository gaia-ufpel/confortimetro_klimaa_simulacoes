---
id: 0003-klimaa-corrigir-c1-a1-a2-a3
title: 'Klimaa: corrigir C1, A1, A2, A3 da revisão do core'
repo: 'gaia-ufpel/confortimetro_klimaa_simulacoes'
type: codigo
agent: 'merge-task'
priority: alta
created: 2026-10-05T20:58:16Z
updated: 2026-10-05T21:41:01Z
briefing_hash: 4c904b48501f2919838eb9902be5b8c7eadf79cb866a1f395018894360111d12
approved: '2026-10-05T20:58:16Z'
panel: 'ver-klimaa-fix-core'
next: 'fix/core-revisao mergeada na main pelo PR #16 (main local não avançou para origin/main)'
---

## Request

## Briefing

### 2026-10-05T20:58:16Z
Você é AGENTE (não orquestrador): não delegue, não pergunte, não amplie escopo. Não leia .env*, nada de produção, sem push.
Repo: /mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes. Worktree: /mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes/.agents/worktrees/klimaa-fix-core, branch fix/core-revisao a partir de origin/main.
Base: docs/revisao-core.html (revisão do core, 03/10, já na main). Corrija SÓ C1, A1, A2, A3. A4 (25 °C fixo vs limite adaptativo) é decisão metodológica do dono: NÃO mexa; M* e demais ficam fora.
- C1: estatísticas/gráficos de PMV (results/stats.py:31,161-164, results/series.py:25, results/charts.py:231-247,285) passam a usar o mesmo PMV do controlador (função _pmv/ASHRAE 55 de control/base.py, recalculado das séries: ar, radiante, UR, VEL_, CLO_), ou a série PMV_<ZONA> se ela for exatamente esse valor. A coluna do Fanger do EnergyPlus, se mantida, é rotulada "PMV Fanger (EnergyPlus)". Teste: com a execução de referência ou fixture sintética, PMV das estatísticas == PMV do controle (tolerância documentada).
- A1: janela_sem_pessoas_bloqueada vira dict por sala (control/base.py:96,198-212,230). Teste: sala A travada não muda a decisão da sala B; ordem das salas não muda o resultado.
- A2: os 4 except de idf/processor.py (668-670, 741-743, 803-805, 896-898) passam a propagar (raise); remova o return morto em 620-621. Teste: falha em People faz process_idf falhar.
- A3: parse_num levanta erro em texto inválido (gui/theme.py:158-163); start_simulation (gui/main_window.py) e a CLI chamam assistant.simulacao.validate antes de rodar; mensagem clara na GUI. Teste: air_speed_delta=0/vazio é recusado antes de simular.
Commit pt-BR por achado, sem push.
Pronto quando: suíte completa (pytest, como o repo roda; antes 173 passed, 1 skipped) verde com os testes novos; saída colada; git diff --stat origin/main...HEAD.
Pare e relate se: C1 exigir rodar o EnergyPlus para validar, ou mudar o formato do Excel/relatório que outro código consome.
Devolva: comandos + saída + números antes/depois de "PMV fora da faixa" na execução de referência (~/.local/share/ConfortimetroKlimaa/execucoes/20260928_1938, só leitura) se der para recalcular sem EnergyPlus.

## History

- 2026-10-05T20:58:16Z — todo (created)

- 2026-10-05T20:58:16Z — briefing aprovado pelo dono (sha256 4c904b48501f)

- 2026-10-05T20:58:22Z — doing

- 2026-10-05T21:37:07Z — doing

- 2026-10-05T21:41:01Z — done
