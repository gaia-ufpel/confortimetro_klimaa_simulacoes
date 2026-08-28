# Documentação técnica — Confortímetro Klimaa

Documento de referência do projeto: arquitetura, configuração, algoritmo de
controle, saídas, interfaces e manutenção. Complementos:

- [`CLI.md`](CLI.md) — execução headless, flags e diagnóstico operacional.
- [`WINDOWS.md`](WINDOWS.md) — instalação e execução no Windows.

## 1. Visão geral

O Confortímetro Klimaa roda simulações anuais de edificações no EnergyPlus e,
a cada timestep de zona, decide o estado dos sistemas de conforto de cada sala:
abertura de janela, ventilador (velocidade do ar), ar-condicionado (PTHP),
ventilação dedicada (DOAS) e vestimenta dos ocupantes (clo). As decisões usam
PMV (Fanger) e o modelo adaptativo ASHRAE 55, ambos lidos/calculados dentro do
próprio timestep. O resultado é exportado em planilhas Excel por sala, mais
estatísticas agregadas.

Três entradas para o mesmo pipeline:

| Interface | Comando | Uso |
|---|---|---|
| CLI (headless) | `.venv/bin/python cli.py` | Automação, execuções longas, agentes. |
| Desktop Tkinter | `python main.py` | Uso interativo local. |
| Web Flask/Socket.IO | `./bin/run_web.sh` | Upload de IDF/EPW, progresso ao vivo, ZIP dos resultados. |

## 2. Arquitetura

```text
config.json / GUI / formulário web
        │
        v
 SimulationConfig  (dataclass; deriva input_path, expanded_idf_path, met_as_watts)
        │
        v
 Simulation.run(queue)          confortimetro/simulation.py
        │
        ├─1. MODULES_MAPPER[module_type] → instancia o condicionador
        ├─2. IDFProcessor.validate_idf() + process_idf()   ← grava o IDF no lugar
        ├─3. ExpandObjects (subprocess, timeout 300 s)     → <input_path>/expanded.idf
        ├─4. cria output_path e salva configs.json
        ├─5. pyenergyplus.api: callback begin_zone_timestep_after_init_heat_balance
        │        └── Conditioner.__call__ → room_conditioner(state, room) por sala
        └─6. pós-processamento: eplusout.eso → <SALA>.xlsx → ESTATISTICAS.xlsx
                                             → ATELIE1_SPLIT.xlsx
```

Fluxograma do condicionador:
[`assets/room_conditioner_flowchart.png`](assets/room_conditioner_flowchart.png).

### Mapa de código

| Caminho | Responsabilidade |
|---|---|
| `cli.py` | Parse de argumentos, `--set`, `--print-config`, execução e código de saída. |
| `main.py` | Abre a `MainWindow` Tkinter. |
| `confortimetro/simulation.py` | Orquestrador do pipeline (6 etapas acima) e verificações de erro. |
| `confortimetro/idf/processor.py` | Validação e modificação do IDF via eppy. |
| `confortimetro/control/base.py` | Classe base: handlers, PMV cacheado, busca de clo/velocidade/setpoints, critério de conforto. |
| `confortimetro/control/{complete,closed_window,without_fan,fixed_ac_without_fan}.py` | As quatro estratégias de condicionamento. |
| `confortimetro/config.py` | Dataclass de configuração e (de)serialização JSON. |
| `confortimetro/results/` | Pós-processamento: `excel.py` (ESO → planilha), `stats.py`, `periods.py` (recortes sazonais), `plots.py`. |
| `confortimetro/module_type.py` | Enum `ModuleType`. |
| `confortimetro/gui/` | Janela e painéis Tkinter (caminhos, parâmetros, controles, resultados). |
| `confortimetro/web/` | Flask + Socket.IO, upload, sessões e adaptador `WebSimulationManager`. |
| `examples/` | `config.json`, IDFs (`idf/`) e EPWs (`epw/`) de referência. |
| `bin/` | `install.sh`/`install.bat`, `executar.bat`, `run_web.sh`. |
| `scripts/generate_flowchart.py` | Gera o fluxograma da documentação. |
| `docs/material/`, `docs/backups/` | PDFs do EnergyPlus e versões antigas em notebook; fora do versionamento. |

## 3. Requisitos

| Item | Detalhe |
|---|---|
| Python | 3.10+ (o código usa `list[str]`, `dict[str, int]`). |
| EnergyPlus | 9.4. `energy_path` precisa conter `Energy+.idd`, `ExpandObjects` (`.exe` no Windows) e o pacote `pyenergyplus`. Padrões por plataforma em `default_energy_path()`: `/usr/local/EnergyPlus-9-4-0`, `C:\EnergyPlusV9-4-0`, `/Applications/EnergyPlus-9-4-0`. |
| Dependências | `requirements.txt` (raiz; `pip install -e .` usa o mesmo arquivo via `pyproject.toml`): eppy, numpy, pandas, pythermalcomfort, dataclasses-json, ladybug-comfort, esoreader, matplotlib, openpyxl. A web adiciona `requirements-web.txt` (Flask, Flask-SocketIO, pytest). |
| Tkinter | Só para a interface desktop. |
| IDF | Precisa conter as zonas de `rooms`, `PEOPLE_<ZONA>`, o PTHP `<ZONA> PTHP` e aceitar os schedules de controle (seção 6). |

Instalação:

```bash
# Linux/macOS
./bin/install.sh            # cria .venv e instala requirements.txt
# Windows
bin\install.bat             # idem; depois bin\executar.bat abre a GUI
# Web (venv separada, venv_web)
./bin/run_web.sh install
```

Para importar `confortimetro` de fora da raiz do repositório:
`.venv/bin/pip install -e .`.

`bin/run_web.sh` também aceita `start` (padrão), `test`, `clean` e `help`.

## 4. Configuração

Base: `examples/config.json`, lido por `SimulationConfig.from_json()`. A
configuração efetiva de cada execução é copiada para
`<output_path>/configs.json`.

Dois campos aparecem no JSON com underscore porque têm *property* associada:
`_idf_path` (→ `idf_path`) e `_met` (→ `met`). Em `--set` e na GUI use os nomes
públicos.

### Caminhos

| Campo | Descrição |
|---|---|
| `_idf_path` | IDF de entrada. Ao ser definido, recalcula os três derivados abaixo. |
| `epw_path` | Arquivo climático `.epw`. |
| `energy_path` | Raiz da instalação do EnergyPlus. Se ausente/inexistente, `from_json` cai no padrão da plataforma. |
| `output_path` | Diretório de saída; criado se não existir e **reutilizado** se já existir. |
| `input_path`, `expanded_idf_path`, `idf_filename` | Derivados do IDF. Não editar. |

### Conforto e controle

| Campo | Padrão | Descrição |
|---|---|---|
| `_met` / `met` | 1.2 | Taxa metabólica; recalcula `met_as_watts = met × 58,1 × 1,8`. |
| `met_as_watts` | derivado | Escrito no schedule `METABOLISMO`. Não editar. |
| `wme` | 0.0 | Trabalho mecânico externo (schedule `WORK_EF`). |
| `clo_min` / `clo_max` / `clo_delta` | 0.5 / 1.0 / 0.1 | Grade de vestimenta varrida a cada timestep. |
| `pmv_lowerbound` / `pmv_upperbound` | −0.5 / 0.5 | Faixa de PMV aceita como conforto. |
| `pmv_comfort_bound` | 0.2 | Margem extra do critério de conforto com janela fechada. |
| `adaptative_bound` | 2.5 | Semibanda adaptativa: 2.5 = 90% de aceitação, 3.5 = 80%. |
| `temp_ac_min` / `temp_ac_max` | 18.0 / 30.0 | Limites dos setpoints de aquecimento e resfriamento (°C). |
| `temp_open_window_bound` | 3.0 | Quanto a temperatura externa pode ficar abaixo da interna e ainda permitir janela aberta. |
| `max_vel` / `air_speed_delta` | 1.2 / 0.15 | Teto e passo da velocidade do ar. |
| `co2_limit` | 900.0 | ppm que aciona o DOAS com janela fechada. |
| `rooms` | lista | Zonas controladas e exportadas; os nomes precisam bater com o IDF. |
| `module_type` | `COMPLETE` | Estratégia de condicionamento (seção 5). |

Constante de código, não configurável: `ac_on_max_timesteps = 12` — depois de
12 timesteps seguidos com AC ligado, o condicionador zera tudo e recomeça.

## 5. Módulos de condicionamento

Registrados em `MODULES_MAPPER` (`confortimetro/control/__init__.py`).

| `module_type` | Classe | Janela | Ventilador | AC | DOAS |
|---|---|---|---|---|---|
| `COMPLETE` | `ConditionerComplete` | sim, com regra adaptativa | sim | setpoints por PMV | sim |
| `CLOSED_WINDOW` | `ConditionerClosedWindow` | sempre fechada | sim | setpoints por PMV | sim |
| `WITHOUT_FAN` | `ConditionerWithoutFan` | sim | não (vel fixa em 0) | setpoints por PMV | sim |
| `FIXED_AC_WITHOUT_FAN` | `ConditionerFixedAcWithoutFan` | sim | não | setpoints fixos do IDF | sim |

### Lógica comum (`Conditioner`)

No primeiro timestep útil (fora do warmup e com `api_data_fully_ready`), o
condicionador adquire todos os handlers de variáveis e atuadores; qualquer um
faltando levanta `RuntimeError` listando os ausentes. Exceções dentro do
callback são capturadas, guardadas em `self.error` e o EnergyPlus é parado —
sem isso o ctypes engoliria o erro e a simulação seguiria com os atuadores
congelados.

Sala **ocupada**:

1. `get_best_clo_for_comfort` varre a grade `clo_min…clo_max` e aplica o clo com
   PMV mais próximo de zero; devolve também se esse PMV caiu na faixa de conforto.
2. Se está confortável: ventilador e AC desligados, contador de AC zerado.
3. Se o AC passou de `ac_on_max_timesteps`, tudo é desligado.
4. Janela (exceto `CLOSED_WINDOW`): abre quando a temperatura externa está
   abaixo do máximo adaptativo, não muito mais fria que a interna
   (`temp_open_window_bound`) e o AC está desligado. Na faixa 25–27,2 °C acima do
   máximo adaptativo, o `COMPLETE` calcula a velocidade de ar necessária
   (`get_vel_adap`) e, se ela ultrapassa `max_vel`, fecha a janela.
5. Janela fechada e ainda sem conforto: `get_best_velocity_with_pmv` ajusta a
   velocidade; se esgotar a faixa, liga o AC.
6. AC ligado: `get_best_temperatures_with_pmv` busca os setpoints de
   resfriamento/aquecimento (passo de 1 °C dentro de `temp_ac_min…temp_ac_max`).
7. DOAS liga se `co2 ≥ co2_limit` e a janela está fechada.
8. Grava clo, vel, status de janela/vent/AC/DOAS, setpoints, PMV, banda
   adaptativa e `EM_CONFORTO` (`is_comfortable`).

Sala **desocupada**: tudo é desligado, `EM_CONFORTO = 1` e a janela pode abrir
para purgar CO₂ — fora dos meses 6 a 9 (inverno hardcoded), com a operativa
acima do mínimo adaptativo. Se a operativa cai abaixo do mínimo, a abertura
fica bloqueada até a operativa voltar acima da temperatura neutra.

PMV: `ladybug_comfort.pmv.predicted_mean_vote_no_set`, com `v_relative` e
`clo_dynamic` do `pythermalcomfort`. As três funções são `lru_cache`-adas
(`_pmv` com 100 000 entradas) porque o controlador repete as mesmas combinações
dezenas de vezes por timestep.

## 6. Processamento do IDF

`IDFProcessor` roda antes da simulação e **grava o IDF de entrada no lugar**:

1. valida IDF/IDD e a presença dos objetos `Building`, `Zone` e das zonas de `rooms`;
2. renomeia o `RunPeriod` com o nome da pasta de saída;
3. ajusta schedules existentes de metabolismo/trabalho (e, no módulo de AC fixo,
   os setpoints);
4. garante os `ScheduleTypeLimits` (`On/Off`, `Any Number`) e cria/atualiza os
   `Schedule:Constant` globais e por sala;
5. associa os schedules de metabolismo, trabalho e velocidade do ar aos objetos
   `People`;
6. adiciona as `Output:Variable` em frequência `Timestep`;
7. salva o IDF.

Schedules por sala (`<X>_<ZONA>`): `CLO`, `JANELA`, `VENT`, `VEL`, `AC`,
`DOAS_STATUS`, `TEMP_COOL_AC`, `TEMP_HEAT_AC`, `PMV`, `TEMP_OP_MAX_ADAP`,
`ADAP_MIN`, `ADAP_MAX`, `EM_CONFORTO`. Globais: `METABOLISMO`, `WORK_EF` e o
schedule de CO₂ externo (400 ppm).

Variáveis lidas pelo condicionador que o IDF precisa expor: `Site Outdoor Air
Drybulb Temperature`, e por zona `Zone Air Temperature`, `Zone Mean Radiant
Temperature`, `Zone Air Relative Humidity`, `Zone Operative Temperature`, `Zone
Air CO2 Concentration`, `People Occupant Count` e `Zone Thermal Comfort ASHRAE
55 Adaptive Model Temperature` (ambas em `PEOPLE_<ZONA>`).

Use `examples/idf/FAURB/FAURB_PTHP_ENTORNO.idf` como referência: um IDF
de outra fonte não funciona sem adaptação.

## 7. Saídas

| Arquivo em `output_path` | Conteúdo |
|---|---|
| `configs.json` | Configuração efetiva da execução. |
| `eplusout.eso`, `.err`, `.eio`, `.rdd`, `.end` | Saídas nativas do EnergyPlus. Diagnóstico começa no `.err`. |
| `<ZONA>.xlsx` | Série temporal da zona: temperatura externa e todas as variáveis do ESO cujo nome contém a zona. |
| `ESTATISTICAS.xlsx` | Uma linha por zona: frações do tempo ocupado com aquecimento, resfriamento, AC ligado, ventilador, janela aberta, DOAS, combinações, desconforto; CO₂ máximo; janela aberta sem pessoas (fração do tempo desocupado). |
| `ATELIE1_SPLIT.xlsx` | Abas `VERAO`, `INVERNO`, `DIAS_VERAO`, `DIAS_INVERNO` (só horas ocupadas). |

Premissas fixas do pós-processamento (`confortimetro/results/`): ano **2015**,
**6 timesteps por hora**, descarte das primeiras **288 linhas** (2 dias de
aquecimento) e períodos-alvo em `TARGET_PERIODS`. O recorte sazonal é hardcoded
na zona `ATELIE1`; se ela não está em `rooms`, a etapa é pulada com aviso na
fila de mensagens.

Erros que abortam o pipeline em vez de gerar planilha silenciosamente errada:
nenhuma variável da zona no ESO, número de linhas diferente do período
esperado, `<ZONA>.xlsx` ausente na etapa de estatísticas e zona nunca ocupada.

Para reprocessar uma simulação já rodada, chame diretamente
`summary_rooms_results_from_eso`, `get_stats_from_simulation` e
`split_target_period_excel` sobre o `output_path`.

## 8. Interfaces

### CLI

```bash
.venv/bin/python cli.py [--config CAMINHO] [--set CHAVE=VALOR ...] [--print-config] [--quiet]
```

Detalhes, exemplos e tabela de diagnóstico em [`CLI.md`](CLI.md).

### Desktop (Tkinter)

`main.py` → `MainWindow` (`confortimetro/gui/main_window.py`): carrega/salva a
configuração, valida os caminhos, roda a simulação em `threading.Thread` e
consome uma `Queue` para o log. O botão **Parar** chama `Simulation.stop()`,
que pede o encerramento à API do EnergyPlus (`request_stop`); o encerramento
não é imediato.

### Web (Flask + Socket.IO)

`./bin/run_web.sh` → `confortimetro/web/app.py`, em `http://localhost:5000`.

| Rota | Função |
|---|---|
| `GET /` | Página e criação da sessão. |
| `GET` / `POST /api/config` | Lê e atualiza a configuração da sessão. |
| `POST /api/upload` | Recebe `file` + `type` (`idf`/`epw`); só `.idf` e `.epw`, até 50 MiB, salvos em `uploads/` com nome aleatório. |
| `POST /api/simulation/start` | Inicia a simulação em thread. |
| `POST /api/simulation/stop` | Solicita parada. |
| `GET /api/simulation/status` | Estado em memória. |
| `GET /api/simulation/download` | ZIP das saídas da sessão. |

Eventos Socket.IO: `connected`, `simulation_message`, `simulation_finished`,
`ping`/`pong`.

`WebSimulationManager` (`confortimetro/web/simulation_integration.py`) copia o IDF para um
diretório temporário por sessão antes de rodar — a web, ao contrário do
desktop/CLI, não modifica o arquivo original.

## 9. Testes

```bash
.venv/bin/python -m compileall -q main.py cli.py confortimetro tests
.venv/bin/python -m pytest tests -q
```

| Local | Cobertura |
|---|---|
| `tests/test_clo_priority.py` | Escolha do clo com PMV mais próximo de zero e validação de `clo_delta`/`clo_min`. |
| `tests/test_pmv_fast.py` | Equivalência e cache do PMV rápido. |
| `tests/test_error_reporting.py` | Erros que devem abortar (handlers faltando, exceção no callback, ESO truncado). |
| `tests/web/` | Rotas Flask, upload, Socket.IO e o contrato com `Simulation.run(queue)` usando um simulador de teste. |

## 10. Armadilhas conhecidas

- **Execuções paralelas colidem**: `in.idf` e `expanded.idf` são gravados em
  `input_path` (o diretório do IDF). Para paralelizar, copie o IDF para um
  diretório por execução.
- **O IDF de entrada é modificado no lugar** pelo CLI e pela GUI; por isso
  `examples/idf/FAURB/*.idf` aparece sujo no `git status`.
- **`output_path` é reutilizado** se já existir, misturando resultados.
- **Simulação anual leva dezenas de minutos a horas**; valide antes com
  `--print-config`.
- **Sempre execute a partir da raiz** (os caminhos padrão da configuração são relativos; para importar de fora, `pip install -e .`).
- **Sem streaming de progresso no CLI**: as mensagens saem da `Queue` no final;
  o sinal de vida é o stdout do próprio EnergyPlus.
- **Servidor web roda com `debug=True`**: não exponha em rede pública sem
  alterar isso.
- **`ATELIE1` e as datas de 2015 são hardcoded** no pós-processamento.

## 11. Convenções de desenvolvimento

- Novo módulo de condicionamento: herde `Conditioner`, implemente
  `room_conditioner(state, room)`, adicione o valor em `ModuleType` e registre
  em `MODULES_MAPPER`.
- Nova zona: acrescente em `rooms` e confirme no IDF os objetos `PEOPLE_<ZONA>`,
  `<ZONA> PTHP` e as variáveis da seção 6.
- Nada de caminho com `/` fixo nem `.venv/bin` no código: use `os.path.join` e
  `platform.system()`.
- `outputs/`, `logs/`, `uploads/` e `backups/` ficam fora do versionamento de
  resultados.
- Esta página e o `README.md` são a referência atual do projeto.

## 12. Estado atual (28/08/2026)

Retrato do repositório no commit `2535046`, após a reorganização de pastas.

### O que está pronto e verificado

| Item | Situação |
|---|---|
| Pipeline de simulação | Funcional pelas três entradas (CLI, Tkinter, web), todas sobre o mesmo `Simulation.run(queue)`. |
| Módulos de condicionamento | Os quatro implementados e registrados em `MODULES_MAPPER`. |
| Relato de erros | Handlers ausentes, exceção no callback, código de saída do EnergyPlus, `eplusout.end`, séries truncadas e falha de escrita das planilhas abortam a execução com mensagem. |
| Testes | `pytest tests` → 22 passando (conforto/clo, PMV rápido, relato de erros, rotas e contrato da web). |
| Empacotamento | `pyproject.toml` com `pip install -e .`; dependências em `requirements.txt` e `requirements-web.txt`. |
| Documentação | Esta página, `CLI.md` e `WINDOWS.md` conferidas contra o código. |

Tamanho do código: ~4 500 linhas Python em `confortimetro/` e `tests/`.

### Pendências conhecidas

Nenhuma bloqueia o uso atual; estão em ordem aproximada de impacto.

1. `ATELIE1` e as datas de 2015 continuam hardcoded no pós-processamento
   (`results/periods.py` e os parâmetros padrão de `summary_rooms_results_from_eso`).
2. `confortimetro/web/app.py` sobe com `debug=True` e `host='0.0.0.0'` — trocar
   antes de expor o servidor fora da máquina local.
3. O IDF de entrada é modificado no lugar pelo CLI e pela GUI; só a interface
   web trabalha sobre cópia. Adotar a cópia por execução nos três caminhos
   resolveria também a colisão entre execuções paralelas.
4. Sem streaming de progresso no CLI: as mensagens da `Queue` só são impressas
   ao final.
5. Os meses de inverno (6 a 9) e o limite `ac_on_max_timesteps = 12` são
   constantes de código, não configuração.

### Fora do versionamento

`.venv/`, `venv_web/`, `outputs/` (165 execuções acumuladas na máquina de
desenvolvimento), `logs/`, `uploads/`, `docs/material/` (PDFs do EnergyPlus),
`docs/backups/` (notebooks antigos) e os `in.idf`/`expanded.idf`/`*.err`
gerados dentro de `examples/idf/`.
