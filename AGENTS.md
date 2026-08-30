# Confortímetro Klimaa — simulações

Simulações de conforto térmico com EnergyPlus. O núcleo Python modifica um IDF,
registra um controlador que decide janela/ventilador/AC/DOAS a cada timestep e
exporta os resultados em planilhas Excel.

## Executar

Sempre a partir da raiz do repositório, com o venv do projeto:

```bash
.venv/bin/python cli.py --set output_path=./outputs/run_001   # headless (CLI)
.venv/bin/python cli.py --print-config                        # valida sem simular
python main.py                                                # GUI Tkinter
```

No Windows o usuário final usa o instalador
`ConfortimetroKlimaa-<versão>-setup.exe` (gerado por
`.github/workflows/windows-build.yml` com PyInstaller + Inno Setup, a partir de
`packaging/`); a partir do código, `bin\install.bat` e `bin\executar.bat`
(ver [`docs/WINDOWS.md`](docs/WINDOWS.md)). Nada de caminho com
`/` fixo nem `.venv/bin` no código — use `os.path.join` e
`platform.system()`.

**Antes de rodar ou alterar qualquer coisa do pipeline de simulação, leia
[`docs/CLI.md`](docs/CLI.md)** — flags, todos os campos de
configuração, módulos de condicionamento, etapas do pipeline, requisitos do IDF,
saídas e diagnóstico de erros.

## Armadilhas que custam caro

- **Uma execução é um diretório com `configs.json` ou `parameters.txt`**
  (`compare.RUN_MARKERS`). O `parameters.txt` é o formato anterior ao JSON: as
  pastas antigas em `./outputs` só têm ele, e exigir `configs.json` sumia com
  elas da listagem. `compare.read_config` lê os dois.
- **Cada execução é uma pasta em `paths.runs_root()`** — `%LOCALAPPDATA%` no
  Windows, `~/.local/share/ConfortimetroKlimaa/execucoes` no Linux,
  `~/Library/Application Support` no macOS — e leva tudo consigo: `modelo.idf`
  (a cópia processada), `in.idf`, `expanded.idf` e as saídas do EnergyPlus.
  `CONFORTIMETRO_DATA_DIR` muda essa raiz; uma simulação anual passa de 1 GB.
- **O IDF de entrada não é mais modificado no lugar.** O `IDFProcessor` grava as
  alterações na cópia dentro da execução (`modelo.idf`), e `source_idf_path`
  guarda o original. Execuções paralelas sobre o mesmo modelo deixaram de
  colidir — mas `idf_path` muda no meio do `run()`, então leia `source_idf_path`
  quando quiser o arquivo escolhido pelo usuário.
- **Uma simulação anual leva de dezenas de minutos a horas.** Não a rode em
  primeiro plano esperando resposta rápida; use `--print-config` para validar
  a configuração antes.
- **O executável Windows é gerado só no CI** (`windows-latest`): PyInstaller +
  Inno Setup não rodam em Linux. A versão vem do `version` do `pyproject.toml`,
  e a tag `v<version>` precisa bater com ela ou o build falha de propósito.
  Armadilhas do `.spec` e do `.iss` em [`docs/WINDOWS.md`](docs/WINDOWS.md).
- O período e o passo do pós-processamento vêm do `RunPeriod` e do `Timestep`
  do IDF (`read_run_period`, `read_timesteps_per_hour`); o descarte inicial é de
  dois dias de aquecimento, proporcional ao timestep.

## Interface gráfica (Tkinter)

`confortimetro/gui/main_window.py` é um roteador de **páginas** — uma janela
só, sem `Toplevel`. Todas ficam montadas em `self.page_host` e `show_page(nome)`
troca quem está packado, com uma transição de 180 ms (`_slide`, `place` nas
duas páginas; misturar `pack` e `place` no mesmo host empurra a que entra).

- `runs` (inicial) — `SimulationsPanel`: topbar com todas as ações
  (**Nova execução**, **Ver detalhes**, **Duplicar**, **Regerar
  estatísticas**, **Abrir pasta**, **Atualizar** e **Comparar
  selecionadas**), pasta de saídas e status na linha de baixo, listagem e
  detalhes da selecionada ocupando o resto. **Configurações** fica no
  cabeçalho da página.
- `compare` — `ComparisonPanel` (`components/comparison_panel.py`): zona,
  catálogo de gráficos com as opções de cada um, tabela comparativa,
  exportação em CSV e a figura ao lado.
- `detail` — configuração completa da execução escolhida (duplo clique na
  lista também chega aqui), com **Duplicar** e **Abrir pasta**.
- `editor` — topbar de execução (`ControlPanel`), card rolável com caminhos +
  parâmetros (`PathConfigPanel` e `SimulationConfigPanel`) e um `BottomSheet`
  com o log (`ResultsPanel`), que abre sozinho quando a simulação começa.
- `settings` — `PathConfigPanel` com os caminhos da máquina, incluindo a pasta
  de saída. A listagem só mostra a pasta; quem a edita é esta página, e
  `on_output_path_changed` empurra a mudança com
  `SimulationsPanel.set_outputs_path`. Qual pasta a listagem lê sai de
  `compare.runs_root_for`: o campo aceita tanto a pasta de uma execução
  (`outputs/run_001`, que nem existe antes de rodar) quanto a raiz que guarda
  todas (`outputs`), e quem decide é o conteúdo. Derivar por `dirname` deixava
  a listagem vazia para quem apontava a raiz.

O `SimulationsPanel` não navega: ele chama `on_new_run`,
`on_open_run_details(run)`, `on_duplicate_run(run)` e
`on_compare_runs(runs, outputs_path)` no `callback` (a `MainWindow`).
**Duplicar** relê o `configs.json` da execução, troca `idf_path` pelo
`source_idf_path` e a saída por um `new_run_path()` — nunca escreve por cima
de resultado que já existe.

A listagem só é relida ao voltar para `runs` quando `_runs_dirty` está
marcado (fim de simulação): o `database.sync` custa segundos e não vale a cada
ida e volta.

O `PathConfigPanel` monta só os campos pedidos em `fields=`: a página de
execução recebe `SIMULATION_FIELDS` (IDF e EPW, que mudam a cada rodada) e a
de configurações, `MACHINE_FIELDS` (diretório de saída e caminho do
EnergyPlus). São **duas instâncias**: leia saída/EnergyPlus em
`self.settings_panel`, IDF/EPW em `self.path_panel` — pedir o campo errado a um
painel é `AttributeError`. Toda página fica montada desde o início justamente
porque esses campos são o contrato de leitura da configuração.

O `ComparisonPanel` recebe as execuções por `set_runs(runs, outputs_path)` e
compara na hora: energia, desconforto, PMV e acionamentos na tabela, e os
gráficos de `results/charts.py` no card ao lado, com a barra do matplotlib.
Figuras de vários painéis (carpete, semana típica) passariam do espaço
disponível — o layout do matplotlib colapsaria os eixos a zero —, então acima
de 7,5 polegadas de altura elas vão para uma área rolável em tamanho natural.
Toda a leitura vem de `confortimetro/results/` — mexa lá, não na interface,
para mudar métricas, colunas ou gráficos.

## Resultados agregados

- `results/compare.py` — lista execuções, regera estatísticas e monta a tabela
  comparativa a partir dos `ESTATISTICAS.xlsx`.
- `results/database.py` — SQLite em `outputs/simulacoes.db` com os agregados em
  formato longo e histórico por ingestão. É cache e histórico, nunca a fonte:
  apagar o arquivo não perde nada, um `sync` reconstrói.
- `results/series.py` — séries por zona com cache em `.series_cache/`; sem ele
  cada gráfico esperaria ~22 s por planilha.
- `results/charts.py` — as figuras. Devolvem `Figure` e **não** usam `pyplot`:
  o estado global dele briga com o laço de eventos do Tk.

Os ícones são o **Lucide** (ISC), embutido como fonte em
`confortimetro/gui/assets/lucide.ttf`. O Tk não carrega fonte de arquivo, então
`theme.icon(nome, tamanho, cor, master=)` desenha o glifo com o Pillow e
devolve um `PhotoImage` — a fonte não precisa estar instalada na máquina, e a
cor sai do próprio tema. Duas regras: o cache é **obrigatório** (o Tk não
segura referência de imagem, e um `PhotoImage` coletado deixa o botão vazio) e
a chave inclui o interpretador do `master`, porque a imagem pertence ao `Tk`
que a criou — reusá-la em outra janela dá `image "pyimageN" doesn't exist`.
`RoundedButton(icon=...)` e o `StatusPill` desenham o par ícone + texto
centralizado; nos `ttk.Label` use `image=` com `compound="left"`. Para um ícone
novo, pegue o código em `https://unpkg.com/lucide-static/font/info.json` e
acrescente ao dicionário `ICONS`. A fonte entra no bundle pelo `datas` do
`.spec` e no pacote pelo `package-data` do `pyproject.toml`.

**Cor, fonte, raio, espaçamento e os widgets arredondados ficam só em
`confortimetro/gui/theme.py`; a razão de cada escolha está em
[`docs/DESIGN.md`](docs/DESIGN.md)** — leia antes de mexer na aparência. Os
painéis em `components/` consomem `COLORS`/`SPACE`/`FONTS` e os nomes de
estilo prontos, e não definem literais próprios.

Os widgets ttk usam o tema **sv_ttk** (Sun Valley, visual Windows 11), ligado
em `apply_theme`. Os sprites dele são PNG: entry, combobox, checkbutton,
progressbar, treeview e scrollbar **não aceitam cor** — não tente reestilizá-los
em `theme.py`, os estilos nomeados (`Field.TEntry`, `Modern.Treeview`, …) só
herdam. O verde da marca vive nos widgets desenhados à mão e nos títulos.

`sv_ttk.set_theme` roda `tk_setPalette`, que grava `*background` no banco de
opções do Tk. Como `ttk.Label` tem `-background` própria, **o valor do banco
vence o do estilo**: `apply_theme` reescreve a opção para `COLORS["surface"]` e
os poucos rótulos que ficam sobre o fundo da janela (cabeçalho e rodapé)
passam `background=COLORS["bg"]` na criação. Rótulo com retângulo de fundo
errado é sempre isso.

**Não reuse um nome de estilo do sv_ttk.** `Card.TFrame` já existe lá, com um
sprite de moldura: nosso frame de fundo branco herdava a borda dele e cada
linha de campo ganhava um retângulo fantasma. O estilo passou a se chamar
`Surface.TFrame`. Pelo mesmo motivo `Section.TLabelframe` não define
`background` — pintar por cima do sprite come a moldura.

Tk **não** tem `border-radius`: card, botão e pill de status são desenhados
num `tk.Canvas` por `theme.rounded_rect`. O resto continua ttk plano.

- **Widget não packado não aparece e não dá erro.** Um card ou painel montado
  mas sem `pack`/`grid` some junto com todos os filhos, silenciosamente. Foi o
  que aconteceu com os quatro painéis até `392abe7`. Depois de mexer no
  layout, confirme com:

```bash
.venv/bin/python -c "
from confortimetro.gui.main_window import MainWindow
a = MainWindow(); a.show_page('editor'); a.update()
print(a.path_panel.winfo_ismapped(), a.simulation_panel.winfo_ismapped())
a.destroy()"
```

  O log só é mapeado com o `BottomSheet` aberto (`a.log_sheet.set_open(True)`),
  e cada painel só é mapeado com a sua página visível. `tests/test_gui_pages.py`
  cobre a troca de página e a duplicação (pula sem display).

- **Painel dentro de card vai em `card.body`, não no `Card`.** O `Card` já usa
  `pack` para o próprio corpo; empacotar outra coisa nele mistura geometrias.

- **As salas vêm do IDF.** `read_zone_names` (em `confortimetro/idf/processor.py`)
  lê os nomes de zona do texto do IDF sem eppy nem IDD; `MainWindow._refresh_room_options`
  alimenta o `ChipSelect`. IDF inválido → lista vazia e campo de texto livre,
  nunca exceção.

- `SimulationConfigPanel` usa um `ttk.LabelFrame` por seção. Adicionar um campo
  é chamar `_field(section, coluna, rótulo)`; não há numeração global de linhas
  para reajustar. Os nomes dos atributos (`self.*_entry`) são o contrato com
  `get_configuration`/`set_configuration` — renomear um quebra a leitura da
  configuração em silêncio, porque `get_configuration` engole `ValueError` e
  devolve `{}`. Os pares min/max (PMV, temperatura do AC, Clo) passaram a ser
  `RangeField`, e as salas um `ChipSelect` — os atributos `*_min_entry` /
  `*_max_entry` seguem existindo, apontando para os campos das pontas.

## Verificação

```bash
.venv/bin/python -m compileall -q main.py cli.py confortimetro tests
.venv/bin/python -m pytest tests -q
```

## Git

Commit e push direto na branch atual, incluindo a `main`. Não crie branch de
trabalho nem abra pull request para entregar uma alteração — este é um
repositório de pesquisa com um único autor, e o fluxo de revisão só atrasa.

Continua valendo: commite apenas quando o usuário pedir, e não inclua no commit
o IDF de entrada modificado pela execução (`examples/idf/**`), que o
`IDFProcessor` reescreve no lugar a cada rodada.
