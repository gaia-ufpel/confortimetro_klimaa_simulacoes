---
id: 0002-klimaa-revisao-do-core-em-busca
title: 'klimaa revisão do core em busca de lógicas quebradas'
repo: 'gaia-ufpel/confortimetro_klimaa_simulacoes'
type: diagnostico
agent: 'claude'
priority: alta
created: 2026-10-03T06:31:07Z
updated: 2026-10-03T07:02:09Z
briefing_hash: ca29d7c4a8131dccfab584241c58a52834f5360e41d9cbd34b44a0417356d0b5
approved: '2026-10-03T06:31:49Z'
panel: 'klimaa-rev-core'
---

## Request

## Briefing

### 2026-10-03T06:31:47Z
Você é AGENTE (não orquestrador): não delegue, não pergunte, não amplie escopo. Não leia .env*, nada de produção, sem push. SOMENTE LEITURA no código: não corrija nada.
Repo: /mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes (confortímetro Klimaa simulações, EnergyPlus). Worktree: <repo>/.agents/worktrees/rev-core, branch docs/revisao-core a partir de main local.
Contexto do dono: o objetivo do projeto é simulação e pesquisa; resultado errado silencioso é o pior defeito. A pesquisa anterior (docs/pesquisa-variaveis-simulacao.html na branch docs/variaveis-simulacao) já achou: Output:Variables com nome errado (Radiante, Adaptative) em confortimetro/idf/processor.py:819-861 e limite PMV fixo 0.5 em stats.py:164. Não repita esses; cite-os só como já conhecidos.
Revise o core em busca de lógica quebrada: confortimetro/idf/processor.py, confortimetro/control/*, confortimetro/simulation.py, confortimetro/config.py, confortimetro/results/* (stats, compare, charts), cálculo de conforto (PMV/PPD, adaptativo ASHRAE 55, temperatura operativa), unidades e conversões, agregação temporal (horas ocupadas, timestep, médias vs somas de energia J→kWh), leitura do CSV/SQL do EnergyPlus, controle (setpoints, histerese, estados), seed/aleatoriedade e reprodutibilidade, tratamento de erro que engole falha da simulação. GUI e assistant só onde alimentam o cálculo.
Para cada achado: arquivo:linha, o que está errado, cenário concreto que produz número errado, severidade (crítico = invalida resultado de pesquisa; alto; médio), correção sugerida em uma linha, e se possível prova (teste mínimo rodado com pytest -k ou script em python que mostra o erro; não commite teste que falha). Rode a suíte existente (`python -m pytest -q`) e relate.
Entregue docs/revisao-core.html curto (decisões/achados críticos no topo, tabela por severidade, pt-BR) e commite só ele.
Pronto quando: docs/revisao-core.html commitado; saída do pytest; `git diff --stat main...HEAD`.
Pare e relate se: rodar EnergyPlus exigir instalação ou rede; o repo não tiver o core nos caminhos citados.
Devolva: comandos rodados + saída + lista de achados por severidade.

## History

- 2026-10-03T06:31:07Z — todo (created)

- 2026-10-03T06:31:49Z — briefing aprovado pelo dono (sha256 ca29d7c4a813)

- 2026-10-03T07:02:09Z — doing
