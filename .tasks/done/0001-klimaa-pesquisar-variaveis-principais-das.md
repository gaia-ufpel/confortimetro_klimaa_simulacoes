---
id: 0001-klimaa-pesquisar-variaveis-principais-das
title: 'klimaa: pesquisar variáveis principais das simulações energéticas'
repo: 'gaia-ufpel/confortimetro_klimaa_simulacoes'
type: pesquisa
agent: 'sonnet'
priority: media
created: 2026-10-03T06:19:45Z
updated: 2026-10-05T20:52:56Z
briefing_hash: b13f74f3a80d58536e53d05ddd5b87d2664b30f10a146848259ba88f0edda94e
approved: '2026-10-03T06:19:46Z'
panel: 'pesq-variaveis-klimaa'
next: 'docs/variaveis-simulacao mergeada na main pelo PR #14 (main local não avançou para origin/main; worktree /mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes/.agents/'
---

## Request

## Briefing

### 2026-10-03T06:19:46Z
Você é AGENTE (não orquestrador): não delegue, não pergunte, não amplie escopo. Não leia .env*, nada de produção, sem push.
Pesquisa (sem código de produto), no repositório do Ambiens desktop (confortímetro Klimaa simulações): /mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes. Trabalhe SÓ na worktree /mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes/.agents/worktrees/pesq-variaveis (branch docs/variaveis-simulacao a partir de origin/main); leia o código pela worktree. Não toque no checkout principal (tem mudança do dono não commitada).

Pergunta do dono: "quais são as principais variáveis que são analisadas em simulações energéticas no Ambiens / confortímetro Klimaa simulações".
Faça:
1. No código do Ambiens (worktree; outputs/ e logs/ não versionados podem ser lidos no checkout principal, só leitura: README.md, AGENTS.md, docs/, confortimetro/, examples/, outputs/, cli.py, main.py): levante quais variáveis o sistema lê, simula e reporta — entradas (IDF/EPW: clima, envoltória, ocupação, cargas internas, HVAC/ventilação natural, setpoints, schedules), saídas pedidas ao EnergyPlus (Output:Variable/Meter, ex.: Zone Mean Air Temperature, Zone Operative Temperature, Mean Radiant Temperature, umidade relativa, velocidade do ar, consumo/energia por uso final, cargas de aquecimento/resfriamento, horas de desconforto) e métricas de conforto calculadas (PMV/PPD ISO 7730/ASHRAE 55, conforto adaptativo ASHRAE 55/EN 16798, horas de conforto, graus-hora, etc.). Para cada uma: nome no código/IDF, unidade, onde aparece (arquivo:linha), para que é usada. Separe o que o sistema de fato usa do que só é suportado.
2. Contexto externo curto (fontes citadas com link): quais variáveis a prática de simulação energética e de conforto considera principais (ASHRAE 55, ISO 7730, EN 16798-1, NBR 15575 desempenho térmico, RTQ-C/INI-C do PBE Edifica no Brasil). Aponte as que o Ambiens NÃO cobre e se valeria cobrir.
3. Entregue docs/pesquisa-variaveis-simulacao.html curto (decisões/resumo no topo: top ~10 variáveis em uma tabela; depois detalhes; depois lacunas e perguntas), HTML autocontido, legível no celular, pt-BR. Commit único pt-BR, sem push.
Pronto quando: arquivo existe; cada variável do sistema tem arquivo:linha conferível; `git -C /mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes/.agents/worktrees/pesq-variaveis log --oneline -1`; `git -C /mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes status --short` igual ao início (checkout principal intocado).
Pare e relate se: o código do Ambiens não tiver as saídas configuradas (ex.: tudo vem de IDF do usuário) — aí descreva o que dá para inferir dos exemplos.
Devolva: caminho do HTML + resumo das top variáveis + comandos rodados.

## History

- 2026-10-03T06:19:45Z — todo (created)

- 2026-10-03T06:19:46Z — briefing aprovado pelo dono (sha256 b13f74f3a80d)

- 2026-10-03T06:19:53Z — doing

- 2026-10-05T20:52:56Z — done
