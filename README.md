# Confortímetro Klimaa — simulações personalizadas

Ferramenta acadêmica da UFPel para simular conforto térmico em edificações com
EnergyPlus. O núcleo Python modifica um arquivo IDF, registra um controlador
durante a simulação e transforma os resultados em planilhas Excel.

## Estado do projeto

O código vive no pacote `confortimetro/` e as duas entradas — CLI e desktop
Tkinter — rodam o mesmo `Simulation.run(queue)`. Ambas modificam o IDF de
entrada no lugar.

`pytest tests` passa com 17 testes. O retrato detalhado do que está pronto e
das pendências conhecidas está na seção *Estado atual* de
[`docs/PROJETO.md`](docs/PROJETO.md#12-estado-atual-28082026).

## Início rápido (desktop)

1. Instale o EnergyPlus compatível e identifique a pasta que contém
   `Energy+.idd`, `ExpandObjects` e a API `pyenergyplus`.
2. Crie o ambiente e instale as dependências com `./bin/install.sh` (Linux/macOS)
   ou `bin\install.bat` (Windows); ambos usam
   [`requirements.txt`](requirements.txt).
3. Ajuste [`examples/config.json`](examples/config.json) para os caminhos da
   sua máquina e para as zonas do seu IDF.
4. Execute:

   ```bash
   python main.py
   ```

Na janela, valide os caminhos, escolha os parâmetros e clique em **Executar**.
Os resultados são gravados no diretório `output_path` configurado.

No Windows, o usuário final instala pelo `ConfortimetroKlimaa-<versão>-setup.exe`
publicado nas *Releases* (duplo-clique, sem Python e sem administrador); quem
roda a partir do código usa `bin\install.bat` e depois `bin\executar.bat`.
Passo a passo e como o instalador é gerado em
[`docs/WINDOWS.md`](docs/WINDOWS.md).

## Linha de comando (headless)

```bash
.venv/bin/python cli.py --set output_path=./outputs/run_001
```

Guia completo para automação e agentes em
[`docs/CLI.md`](docs/CLI.md).

## Documentação

O guia técnico completo está em
[`docs/PROJETO.md`](docs/PROJETO.md): arquitetura e mapa de
código, requisitos, todos os campos de configuração, algoritmo de controle
timestep a timestep, requisitos do IDF, saídas, as duas interfaces, testes,
armadilhas e convenções.

- [`docs/CLI.md`](docs/CLI.md) — execução headless e
  diagnóstico operacional.
- [`docs/WINDOWS.md`](docs/WINDOWS.md) — instalação no Windows.

## Estrutura essencial

```text
cli.py                      entrada por linha de comando (headless)
main.py                     entrada da interface desktop
bin/                        install.sh/.bat, executar.bat
confortimetro/
  config.py                 SimulationConfig e faixas do modelo adaptativo
  module_type.py            enum ModuleType
  simulation.py             orquestração EnergyPlus e pós-processamento
  idf/processor.py          alterações no IDF via eppy
  control/                  controladores de conforto por zona (base + 4 módulos)
  results/                  planilhas, estatísticas, recortes sazonais, gráficos
  gui/                      interface Tkinter
tests/                      testes do núcleo
examples/                   config.json, IDFs e EPWs de referência
docs/                       documentação (material/ e backups/ ficam fora do git)
scripts/                    utilitários de desenvolvimento
```

## Verificação atual

```bash
.venv/bin/python -m compileall -q main.py cli.py confortimetro tests
.venv/bin/python -m pytest tests -q
```

Os comandos verificam a sintaxe e a lógica de conforto (clo, PMV, relato de
erros).
