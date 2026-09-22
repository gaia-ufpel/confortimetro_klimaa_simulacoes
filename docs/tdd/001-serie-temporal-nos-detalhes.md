# TDD-001: Série temporal por timestep nos detalhes da execução
Status: aceito (implementado na branch worktree-serie-temporal)
Autor: Gabriel Leite Bessa · Revisores: — · Data: 22/09/2026 · PRD relacionado: [PRD-002](../prd/002-serie-temporal-nos-detalhes.md)

## Resumo

Adicionar à página **Detalhes da execução** um notebook com as abas Resumo (conteúdo
atual) e Série temporal. A aba nova é um componente Tkinter com quatro painéis matplotlib
de eixo compartilhado, resolução adaptativa ao zoom (timesteps brutos ou média + faixa
mín.–máx. por bloco) e uma tabela lateral com os valores do timestep clicado.

## Contexto / Background

- `MainWindow._build_detail_page` (`confortimetro/gui/main_window.py:214`) empilha KPIs,
  "Estatísticas por zona" e "Configuração da execução"; `on_open_run_details`
  (`main_window.py:849`) preenche a página a partir do dicionário `run`
  (`path`, `rooms_disponiveis`, `config`, `status`).
- `load_zone_series(run_path, room)` (`confortimetro/results/series.py:44`) lê
  `<ZONA>.xlsx`, renomeia colunas pelos apelidos de `COLUMNS` e grava um pickle em
  `.series_cache/`; leituras seguintes levam milissegundos.
- `ComparisonPanel` (`confortimetro/gui/components/comparison_panel.py`) já embute figuras
  com `FigureCanvasTkAgg` + `NavigationToolbar2Tk`, lê séries em thread e usa as mensagens
  de espera/`toast` do tema — padrões reaproveitados aqui.
- Os gráficos de série do comparador (`charts.carpete`, `charts.periodo`) redesenham tudo
  a cada chamada e têm janela fixa.

## Problema

Ver PRD-002 §1: não há como inspecionar o comportamento do controle timestep a timestep
dentro do software. Tecnicamente: ~52 mil pontos × 12 variáveis por zona num ano de
6 timesteps/h; desenhar tudo a cada zoom é lento e visualmente ilegível, e reduzir por
decimação esconde picos e acionamentos curtos.

## Objetivos e não-objetivos

Objetivos
- Aba Série temporal com os requisitos 1–12 do PRD.
- Redução de resolução como função pura, testável sem Tk.
- Nenhum custo na abertura da página enquanto a aba não é aberta.

Não-objetivos
- Streaming durante a simulação; múltiplas execuções; exportação; painéis configuráveis.
- Mudar o formato do cache ou do `<ZONA>.xlsx`.
- Reaproveitar o componente no comparador (pode vir depois, se pedido).

## Proposta

### Arquivos

| Arquivo | Mudança |
|---|---|
| `confortimetro/results/series.py` | `COLUMNS` ganha `em_conforto` → `EM_CONFORTO_{room}:Schedule Value`. Nova função pura `window_series` (abaixo). |
| `confortimetro/gui/components/timeseries_panel.py` | Novo `TimeSeriesPanel(ttk.Frame)`. |
| `confortimetro/gui/main_window.py` | `_build_detail_page`: `ttk.Notebook` abaixo dos KPIs; aba Resumo recebe os cards atuais, aba Série temporal recebe o painel. `on_open_run_details` chama `timeseries_panel.set_run(run)`. |
| `tests/test_window_series.py` | Check da redução. |
| `docs/CLI.md` | Menção à aba (seção de séries) e à coluna `em_conforto`. |

Adicionar `em_conforto` a `COLUMNS` não invalida caches: o pickle é refeito só quando a
planilha muda, então caches antigos ficam sem a coluna até um `refresh` — tratado como
"variável ausente" (req. 11). `clear_cache` resolve para quem quiser a coluna.

### Contrato de `window_series`

Entrada: série da zona (DataFrame de `load_zone_series`, ordenado por `data`), início e
fim da janela (datetimes), limite de pontos N.

Saída: DataFrame indexado pelo instante (início do bloco), com:

| Caso | Colunas |
|---|---|
| Timesteps na janela ≤ N | Os valores brutos de cada variável, um por timestep. Flag `aggregated = False`. |
| Timesteps na janela > N | Para cada variável contínua (temperaturas, banda, PMV, CO₂, energia): `<var>_mean`, `<var>_min`, `<var>_max`. Para estados (`janela`, `ventilador`, `ac`, `doas`, `em_conforto`): máximo do bloco (qualquer acionamento = acionado; para `em_conforto`, mínimo — qualquer desconforto = desconforto). Flag `aggregated = True`. |

Regras:
- Tamanho do bloco = teto(timesteps na janela / N), em número de timesteps (não em tempo),
  para que o bloco reduza exatamente até 1 timestep ao aproximar.
- Blocos alinhados ao início da série (não da janela), para que arrastar não faça os
  blocos "tremerem".
- A janela é expandida em um bloco de cada lado, para que a linha não termine antes da
  borda do gráfico.
- Colunas ausentes na série são ignoradas.
- Energia: média/mín./máx. do valor por timestep (J), não soma — o eixo mantém a mesma
  unidade em qualquer zoom.

### Componente `TimeSeriesPanel`

Layout: barra superior (combo de zona, "Ver tudo", status) · à esquerda canvas +
toolbar · à direita `Treeview` de duas colunas (`Variável`, `Valor`) com largura fixa.

Fluxo:

```
set_run(run) ──► guarda run, limpa figura, preenche combo com rooms_disponiveis
                  (só lê a série se a aba estiver visível; senão marca "pendente")
<<NotebookTabChanged>> para esta aba + pendente ──► load(room)
load(room) ──► token += 1; mensagem de espera; thread: load_zone_series
            ──► after(0): se token ainda é o atual → série em memória → render(ano inteiro)
                            senão descarta (req. 12)
xlim_changed ──► after_cancel/after(150 ms) ──► render(xlim atual)
render(início, fim) ──► window_series(...,N = largura do eixo em px)
                     ──► limpa os eixos e redesenha; religa o xlim_changed
                     ──► draw_idle
clique (button_press_event, fora do modo zoom/pan da toolbar)
       ──► searchsorted na série completa → índice do timestep → select(i)
← / → ──► select(i ± 1)
select(i) ──► move axvline em todos os eixos; preenche Treeview; se i fora da janela, recentra
```

Painéis: eixo X compartilhado (`sharex`), formatação de datas automática do matplotlib.
Painel 3 desenha os estados como faixas horizontais (`broken_barh` por trecho contínuo),
como `charts.periodo`. Painel 2 tem no rodapé uma faixa de conforto com os dois estados
de `em_conforto`: verde onde vale 1 (em conforto), vermelho onde vale 0 (fora de
conforto), com legenda; no modo agregado, um bloco com qualquer timestep fora de conforto
fica vermelho (mínimo do bloco). Sem a coluna, a faixa some e a legenda indica
"conforto não gravado". Painel 4 usa eixo Y duplo (CO₂ à esquerda, energia à direita).
Cores e estilo de `charts._style`/`PALETTE`.

Tabela: data/hora, e para cada apelido de `COLUMNS` um rótulo em pt-BR com unidade
(temperaturas em °C, PMV, conforto como "Em conforto/Fora de conforto", CO₂ em ppm, energia em kWh convertida de J, estados como
"Aberta/Fechada", "Ligado/Desligado"); coluna ausente → "— (não gravada)".

### Pontos de falha

| Falha | Tratamento |
|---|---|
| `FileNotFoundError` (sem `<ZONA>.xlsx`) | Estado vazio no canvas; combo só lista zonas com planilha. |
| `ValueError` de planilha antiga | Mensagem de erro no canvas com o texto da exceção. |
| Troca de execução/zona durante leitura | Token de geração; resultado velho descartado. |
| Clique durante zoom/pan da toolbar | Ignorado (`toolbar.mode` não vazio). |
| Janela sem nenhum timestep (arraste para fora do período) | `window_series` devolve vazio; artistas limpos, sem exceção. |

### Concorrência

Uma leitura por vez por painel, em `threading.Thread(daemon=True)`; toda mutação de
widget volta ao thread principal por `after(0, ...)`, como em `ComparisonPanel.plot`.
Duas leituras simultâneas do mesmo pickle (comparador + detalhes) são só leitura; a
escrita do cache já é a mesma de hoje.

### Segurança

Nada novo: leitura de arquivos locais da própria execução.

### Observabilidade

Mensagens de status na barra do painel (lendo / pronto: N timesteps / erro). Sem log novo.

### Performance

- Leitura: igual a `load_zone_series` (~20 s fria, ms com cache).
- Render: `window_series` é um fatiamento por `searchsorted` + `groupby` por número de
  bloco. Os eixos são limpos e redesenhados a cada janela (mais simples que atualizar
  artistas; o custo está no `draw`, não nos dados).
- **Medido** (ATELIE1 anual, 52 560 timesteps, 10 min, Linux sob `xvfb`, janela
  1400×900): `window_series` + montagem ~0,15–0,25 s; `draw` ~0,55–0,85 s. Total de
  ~0,7 s (1 dia) a ~1,1 s (ano), acima da meta de 300 ms do PRD. `layout='constrained'`
  dobrava o `draw` (~1,2–1,7 s) e foi trocado por margens fixas. Metade do `draw` que
  resta é o cálculo dos ticks de data nos 5 eixos. Leitura com cache: ~2 s.
- Faixas de estado e de conforto usam `broken_barh` sobre trechos contínuos:
  `fill_between(where=..., step='post')` apagava um trecho de um único timestep.
- Memória: uma zona por vez (~12 MB).

## Alternativas consideradas

- **Não fazer nada (Excel)** — é o contorno atual; lento e sem estado do controle alinhado.
- **Desenhar todos os pontos e deixar o matplotlib lidar** — ~52 mil pontos × 4 eixos
  redesenhados a cada pan; lento e sem leitura visual no ano inteiro.
- **Decimação simples (1 a cada k)** — rápida, mas esconde picos e acionamentos curtos;
  rejeitada pelo requisito 5.
- **Resample por tempo fixo (hora/dia)** — degraus de resolução discretos e bloco que não
  chega a 1 timestep; rejeitada por não ser "atômica".
- **Biblioteca interativa (plotly/bokeh em navegador, ou pyqtgraph)** — dependência nova,
  quebra o empacotamento PyInstaller atual e sai da GUI Tkinter; matplotlib já está
  instalado e embutido.
- **Novo gráfico no comparador** — exige ≥ 2 execuções e a pessoa quer inspecionar uma;
  rejeitada pela decisão de produto.

## Impacto

- Só GUI e `series.py`; CLI e pipeline de simulação intactos.
- `COLUMNS` ganha uma chave: consumidores (`charts.*`) iteram por apelido e não são afetados.
- Página de detalhes passa a ter notebook; quem navega por ela direto no código
  (`detail_stats`, `detail_text`) continua com os mesmos atributos.
- Build Windows: sem dependência nova.

## Plano de implementação

1. `em_conforto` em `COLUMNS` + `window_series` + `tests/test_window_series.py`
   (bruto ≤ N, agregado > N com mín./média/máx. corretos, estado com acionamento curto
   preservado, bloco alinhado ao início da série, coluna ausente ignorada, janela vazia).
2. `TimeSeriesPanel` isolado, verificado com `xvfb-run -a` sobre uma execução real.
3. Notebook na página de detalhes + `set_run` + leitura preguiçosa na troca de aba.
4. `docs/CLI.md` e versão.

Pronto quando: requisitos Must do PRD verificados à mão em `xvfb-run` numa execução anual
e numa antiga (sem `em_conforto`), e o teste da etapa 1 passando. Rollback: reverter o
commit; nada persistido muda.

## Riscos e questões em aberto

- Redesenho acima de 300 ms em máquinas Windows mais fracas → reduzir N (ex.: metade da
  largura em px).
- `xlim_changed` dispara uma vez por eixo com `sharex` → o debounce único cobre.
- Decidido: a sinalização de conforto usa `em_conforto` e mostra os dois estados.

## FAQ

**Por que não reaproveitar `charts.periodo`?** Ele recria a figura inteira e tem janela
fixa; aqui a figura persiste e só os dados mudam.

**Por que blocos por número de timesteps e não por tempo?** Garante descer até 1 timestep
e independe do `Timestep` do IDF (4, 6, 12 por hora).

**E os dois dias de aquecimento?** Já descartados no pós-processamento; a série só tem o
período válido.
