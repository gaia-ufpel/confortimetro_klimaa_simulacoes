# PRD — Série temporal por timestep nos detalhes da execução
Status: rascunho · Autor: Gabriel Leite Bessa · Data: 22/09/2026 · TDD relacionado: [TDD-001](../tdd/001-serie-temporal-nos-detalhes.md)

## 1. Problema

Depois de uma simulação, o software mostra só agregados: os KPIs de consumo e a tabela
"Estatísticas por zona" da página **Detalhes da execução** vêm do `ESTATISTICAS.xlsx`,
uma linha por zona para o período inteiro. Para entender *por que* uma zona ficou em
desconforto ou gastou mais — o controlador abriu a janela na hora errada? o AC ficou
ligando e desligando? o CO₂ subiu com a janela fechada? — é preciso abrir o `<ZONA>.xlsx`
(~52 mil linhas, ~22 s para carregar) no Excel e montar gráficos à mão.

Os gráficos de série que existem ("Carpete anual", "Semana típica") ficam no comparador,
exigem duas execuções e mostram uma janela fixa, sem o valor exato de cada instante.

Custo de não fazer: um comportamento errado do controle só é percebido pelos agregados,
tarde e sem diagnóstico. Cada simulação anual custa de dezenas de minutos a horas; rodar
de novo "para ver o que houve" é o contorno mais caro.

## 2. Usuários e contexto

Pesquisadores e estudantes do GAIA que ajustam o controle e os cenários. O ponto de
entrada é a listagem de execuções → "Ver detalhes". Hoje contornam abrindo a planilha
por zona no Excel ou escrevendo scripts pandas avulsos.

## 3. Solução proposta

A página **Detalhes da execução** ganha duas abas abaixo dos KPIs:

- **Resumo** — estatísticas por zona e configuração, exatamente como hoje.
- **Série temporal** — nova.

Na aba **Série temporal** a pessoa escolhe a zona e vê, com o tempo no eixo horizontal
compartilhado, quatro painéis empilhados:

1. Temperatura externa, temperatura operativa e banda adaptativa.
2. PMV, com a faixa ±0,5 e uma faixa de sinalização de conforto no rodapé do painel:
   verde quando a zona está em conforto e vermelho quando não está, segundo o
   `EM_CONFORTO` que o próprio controle usa.
3. Estados do controle: janela, ventilador, AC e DOAS.
4. CO₂ e energia de aquecimento/resfriamento.

A vista abre no período inteiro. Zoom e arraste ajustam a janela; a resolução
acompanha: quando a janela visível cabe na largura do gráfico, cada timestep aparece
individualmente; quando não cabe, cada bloco de timesteps mostra a média e uma faixa
sombreada do mínimo ao máximo — um pico ou um acionamento curto nunca some ao afastar.
"Ver tudo" volta ao período inteiro.

Clicar no gráfico seleciona o **timestep real** mais próximo (nunca um ponto agregado):
uma linha vertical marca o instante e uma tabela à direita lista data/hora e o valor de
cada variável. As setas ← → do teclado avançam ou recuam um timestep.

Estados:

| Estado | Comportamento |
|---|---|
| Carregando | Mensagem no lugar do gráfico: primeira leitura da planilha leva ~20 s; depois fica em cache. A interface não trava. |
| Vazio | Execução sem `<ZONA>.xlsx` (falhou ou não terminou): aviso explicando que não há série e por quê. |
| Erro | Planilha de versão antiga ou corrompida: mensagem com o motivo (a mesma de `load_zone_series`). |
| Variável ausente | Planilha antiga sem uma coluna (ex.: `EM_CONFORTO`): o painel mostra o que tem e indica a ausência na tabela. |
| Sucesso | Gráfico + tabela, primeiro timestep ainda não selecionado (tabela com instrução "clique no gráfico"). |

## 4. Escopo

### Entra (v1)
- Abas Resumo / Série temporal na página Detalhes da execução.
- Seletor de zona entre as zonas com planilha na execução.
- Quatro painéis, zoom/arraste, "Ver tudo", resolução adaptativa com faixa mín.–máx.
- Seleção de timestep por clique e por setas, tabela lateral com os valores.
- Uma execução por vez.

### Não entra (e por quê / quando reconsiderar)
- **Acompanhamento ao vivo durante a simulação** — exige canal entre o processo do
  EnergyPlus e a GUI; reconsiderar se o diagnóstico pós-execução não bastar.
- **Várias execuções sobrepostas** — o comparador já cobre agregados e séries; reconsiderar
  se o uso pedir comparar instante a instante.
- **Exportar o recorte visível** — a planilha por zona já tem todos os timesteps.
- **Escolher quais variáveis/painéis mostrar** — quatro painéis fixos até haver pedido.
- **Métricas agregadas por mês/semana** — fora deste pedido.

## 5. Requisitos

1. **Must** — Quando a pessoa abre "Detalhes da execução", o sistema deve mostrar as abas
   Resumo e Série temporal, com Resumo selecionada e idêntica à página atual.
2. **Must** — Quando a aba Série temporal é aberta e a execução tem planilhas por zona, o
   sistema deve carregar a primeira zona sem bloquear a interface.
3. **Must** — O gráfico deve mostrar os quatro painéis da seção 3 com eixo de tempo
   compartilhado.
4. **Must** — Enquanto a janela visível tiver até N timesteps (N ≈ largura do gráfico em
   pixels), o sistema deve desenhar cada timestep sem agregação.
5. **Must** — Enquanto a janela visível tiver mais que N timesteps, o sistema deve desenhar
   por bloco a média e a faixa mínimo–máximo; nos estados de controle, um bloco com
   qualquer acionamento deve aparecer como acionado.
6. **Must** — Quando a janela visível muda (zoom, arraste, "Ver tudo"), o sistema deve
   recalcular a resolução.
7. **Must** — Quando a pessoa clica no gráfico, o sistema deve selecionar o timestep real
   mais próximo, marcá-lo e listar data/hora e todas as variáveis na tabela lateral.
8. **Should** — Quando há um timestep selecionado, ← e → devem mover a seleção um timestep.
9. **Must** — Se a execução não tiver planilha por zona, o sistema deve mostrar o estado
   vazio com o motivo, sem erro não tratado.
10. **Must** — O painel de PMV deve sinalizar cada instante como em conforto ou fora de
    conforto conforme `EM_CONFORTO`, com cores distintas e legenda; a tabela lateral deve
    mostrar "Em conforto" / "Fora de conforto" no timestep selecionado.
11. **Must** — Se a planilha for de versão antiga sem alguma variável, o sistema deve
    desenhar as demais e marcar a ausente na tabela.
12. **Should** — Trocar de execução ou de zona durante uma leitura não deve mostrar dados
    da execução/zona anterior.

## 6. Abordagem técnica (alto nível)

Tudo local, na GUI Tkinter. A série vem de `load_zone_series`
(`confortimetro/results/series.py`), que já cacheia a planilha em pickle. A página de
detalhes (`MainWindow._build_detail_page`) ganha um notebook com um componente novo; a
redução de resolução fica numa função pura testável sem Tk. Desenho em
[TDD-001](../tdd/001-serie-temporal-nos-detalhes.md).

## 7. Métricas de sucesso

Ferramenta interna, sem telemetria. Critérios observáveis:
- **Primária**: do clique em "Ver detalhes" até o gráfico do ano inteiro ≤ 2 s com cache
  quente e ≤ 30 s na primeira leitura `[suposição: medir numa execução anual de 6 timesteps/h]`.
- Zoom/arraste redesenham em ≤ 300 ms `[suposição: medir em execução anual]`.
- Diagnóstico: o próximo comportamento estranho do controle é explicado pela aba, sem
  abrir o Excel (validar com o grupo após uso).
- **Contra-métrica**: abrir a aba Resumo não pode ficar mais lento que hoje — a série só é
  lida quando a aba Série temporal é aberta.

## 8. Riscos, suposições e questões em aberto

- **Suposição**: redesenho abaixo de 300 ms com ~52 mil linhas × 12 variáveis. Teste mais
  barato: protótipo da função de redução + `draw_idle` em execução real.
- **Risco**: memória com o cache carregado — ~12 MB por zona (docs/CLI.md); só a zona
  aberta fica em memória.
- **Risco**: planilhas antigas sem colunas novas — coberto pelo requisito 11.
- **Decidido (22/09/2026)**: a sinalização de conforto usa `EM_CONFORTO` e mostra os dois
  estados (em conforto / fora de conforto), não só o desconforto.

## 9. Rollout

Sem flag: entra na próxima versão do instalador. Execuções antigas funcionam, com as
variáveis ausentes marcadas. Rollback: reverter a versão; nada é persistido além do cache
de séries, que já existe.
