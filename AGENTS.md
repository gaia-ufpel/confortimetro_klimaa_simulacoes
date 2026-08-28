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

- **Execuções paralelas colidem.** `in.idf` e `expanded.idf` são gravados no
  diretório do IDF de entrada. Para rodar simulações em paralelo, copie o IDF
  para um diretório por execução e aponte `idf_path` para a cópia.
- **O IDF de entrada é modificado no lugar** pelo `IDFProcessor`. Por isso
  `examples/idf/FAURB/*.idf` aparece modificado no `git status` depois
  de cada execução — normalmente não é uma alteração para commitar.
- **Uma simulação anual leva de dezenas de minutos a horas.** Não a rode em
  primeiro plano esperando resposta rápida; use `--print-config` para validar
  a configuração antes.
- `split_target_period_excel` é hardcoded para a zona `ATELIE1`; sem ela em
  `rooms`, essa etapa é pulada com aviso.
- **O executável Windows é gerado só no CI** (`windows-latest`): PyInstaller +
  Inno Setup não rodam em Linux. A versão vem do `version` do `pyproject.toml`,
  e a tag `v<version>` precisa bater com ela ou o build falha de propósito.
  Armadilhas do `.spec` e do `.iss` em [`docs/WINDOWS.md`](docs/WINDOWS.md).
- O pós-processamento assume ano de 2015 e 6 timesteps por hora, e descarta as
  primeiras 288 linhas.

## Interface gráfica (Tkinter)

`confortimetro/gui/main_window.py` monta um `ttk.Notebook` com duas abas —
**Configuração** (caminhos + parâmetros de simulação) e **Execução**
(controles + log). Estilos e paleta ficam só em `_setup_styles`; os painéis
em `components/` recebem os nomes de estilo prontos e não redefinem cores,
exceto as de estado (✅/⚠️/❌), que são literais nos painéis.

Paleta: `#dad7cd` fundo, `#a3b18a` bordas/texto suave, `#588157` secundário
e sucesso, `#3a5a40` primário, `#344e41` texto. Erro (`#b3261e`) e aviso
(`#a06b00`) ficam fora dela de propósito — precisam se distinguir do verde.

- **Widget não packado não aparece e não dá erro.** Um card ou painel montado
  mas sem `pack`/`grid` some junto com todos os filhos, silenciosamente. Foi o
  que aconteceu com os quatro painéis até `392abe7`. Depois de mexer no
  layout, confirme com:

```bash
.venv/bin/python -c "
from confortimetro.gui.main_window import MainWindow
a = MainWindow(); a.update()
print(a.path_panel.winfo_ismapped(), a.simulation_panel.winfo_ismapped())
a.destroy()"
```

  Painel em aba não selecionada retorna `0` — selecione a aba antes de checar.

- `SimulationConfigPanel` usa um `ttk.LabelFrame` por seção. Adicionar um campo
  é chamar `_field(section, coluna, rótulo)`; não há numeração global de linhas
  para reajustar. Os nomes dos atributos (`self.*_entry`) são o contrato com
  `get_configuration`/`set_configuration` — renomear um quebra a leitura da
  configuração em silêncio, porque `get_configuration` engole `ValueError` e
  devolve `{}`.

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
