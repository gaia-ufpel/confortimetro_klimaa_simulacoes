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
./bin/run_web.sh                                                  # interface web
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
- O pós-processamento assume ano de 2015 e 6 timesteps por hora, e descarta as
  primeiras 288 linhas.

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
