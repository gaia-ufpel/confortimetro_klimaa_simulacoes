# Execução por linha de comando

Guia para agentes automatizados rodarem as simulações do Confortímetro Klimaa
sem interface gráfica nem servidor web.

## 1. Pré-requisitos

| Requisito | Detalhe |
|---|---|
| EnergyPlus | Versão 9.4 instalada (ex.: `/usr/local/EnergyPlus-9-4-0`). A pasta precisa conter `Energy+.idd`, `ExpandObjects` e o pacote `pyenergyplus`. |
| Python | 3.10+ |
| Dependências | `eppy`, `numpy`, `pandas`, `pythermalcomfort`, `ladybug-comfort`, `esoreader`, `matplotlib`, `openpyxl` |
| Arquivo IDF | Modelo EnergyPlus com as zonas e schedules esperados (ver seção 6) |
| Arquivo EPW | Arquivo climático |

Ambiente virtual do repositório: `.venv` (já criado nesta máquina, com todas as
dependências). Para recriar:

```bash
python -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements-web.txt
```

Verificação rápida:

```bash
.venv/bin/python -c "import eppy, esoreader, pythermalcomfort; print('deps ok')"
ls /usr/local/EnergyPlus-9-4-0/Energy+.idd /usr/local/EnergyPlus-9-4-0/ExpandObjects
```

## 2. Comando

```bash
.venv/bin/python cli.py [--config CAMINHO] [--set CHAVE=VALOR ...] [--print-config] [--quiet]
```

Executar sempre a partir da raiz do repositório (os imports são `src.*` e os
caminhos padrão da configuração são relativos).

| Flag | Efeito |
|---|---|
| `--config` | JSON de configuração. Padrão: `examples/config.json`. |
| `--set CHAVE=VALOR` | Sobrescreve um campo. Repetível. O valor é lido como JSON quando possível (`1.3`, `true`, `["ATELIE1"]`); caso contrário vira string. |
| `--print-config` | Imprime a configuração final resolvida e sai **sem simular**. Use para validar antes de gastar horas de CPU. |
| `--quiet` | Suprime o resumo de progresso ao final. |

Código de saída: `0` sucesso, `1` falha (mensagem em stderr).

### Exemplos

Rodar a configuração padrão em um diretório de saída próprio:

```bash
.venv/bin/python cli.py --set output_path=./outputs/run_001
```

Trocar modelo, clima e módulo:

```bash
.venv/bin/python cli.py \
  --set idf_path=./examples/idf/FAURB/FAURB_PTHP_ENTORNO.idf \
  --set epw_path=./examples/epw/BRA_RS_Camaqua.869890_INMET.epw \
  --set energy_path=/usr/local/EnergyPlus-9-4-0 \
  --set module_type=CLOSED_WINDOW \
  --set 'rooms=["ATELIE1","ATELIE2"]' \
  --set output_path=./outputs/run_closed_window
```

Validar sem simular:

```bash
.venv/bin/python cli.py --print-config --set output_path=./outputs/x
```

## 3. Configuração

`examples/config.json` é a base. Campos (classe `SimulationConfig` em
`confortimetro/config.py`):

### Caminhos

| Campo | Tipo | Descrição |
|---|---|---|
| `_idf_path` | str | Caminho do IDF de entrada. **No JSON o nome tem underscore**; em `--set` use `idf_path` (é uma property). |
| `epw_path` | str | Arquivo climático `.epw`. |
| `output_path` | str | Diretório de saída. Criado se não existir. |
| `energy_path` | str | Raiz da instalação do EnergyPlus. Detectado automaticamente quando o valor gravado no config não existe (veja abaixo). |
| `input_path` | str | Derivado de `idf_path` (diretório do IDF). Não defina manualmente. |
| `expanded_idf_path` | str | Derivado: `<input_path>/expanded.idf`. Não defina manualmente. |
| `idf_filename` | str | Derivado. Não defina manualmente. |

### Conforto e controle

| Campo | Padrão | Descrição |
|---|---|---|
| `_met` / `met` | 1.2 | Taxa metabólica. Setar `met` recalcula `met_as_watts = met * 58.1 * 1.8`. |
| `met_as_watts` | derivado | Não defina manualmente. |
| `wme` | 0.0 | Trabalho mecânico externo. |
| `clo_min` / `clo_max` / `clo_delta` | 0.5 / 1.0 / 0.1 | Faixa e passo de vestimenta. |
| `pmv_lowerbound` / `pmv_upperbound` | -0.5 / 0.5 | Faixa de PMV aceitável. |
| `pmv_comfort_bound` | 0.2 | Margem de conforto usada nas decisões do controlador. |
| `adaptative_bound` | 2.5 | Banda do modelo adaptativo: `2.5` = 90% de aceitação, `3.5` = 80%. |
| `temp_ac_min` / `temp_ac_max` | 18.0 / 30.0 | Limites de setpoint do ar-condicionado (°C). |
| `temp_open_window_bound` | 3.0 | Tolerância (°C) para abrir a janela. |
| `max_vel` | 1.2 | Velocidade máxima do ar (m/s) do ventilador. |
| `air_speed_delta` | 0.15 | Passo de incremento da velocidade do ar. |
| `co2_limit` | 900.0 | Limite de CO₂ (ppm) que aciona a ventilação/DOAS. |
| `rooms` | lista | Zonas do IDF processadas e exportadas. |
| `module_type` | `COMPLETE` | Estratégia de condicionamento (seção 4). |

## 4. Módulos de condicionamento (`module_type`)

Definidos em `confortimetro/control/`, mapeados em `MODULES_MAPPER`:

| Valor | Classe | Comportamento |
|---|---|---|
| `COMPLETE` | `ConditionerComplete` | Estratégia completa: janela, ventilador, ar-condicionado e DOAS. |
| `CLOSED_WINDOW` | `ConditionerClosedWindow` | Janela sempre fechada. |
| `FIXED_AC_WITHOUT_FAN` | `ConditionerFixedAcWithoutFan` | Setpoint fixo de ar-condicionado, sem ventilador. |
| `WITHOUT_FAN` | `ConditionerWithoutFan` | Sem ventilador, demais estratégias ativas. |

## 5. O que acontece durante a execução

`Simulation.run()` (`confortimetro/simulation.py`), em ordem:

1. **Módulo condicionador** instanciado a partir de `module_type`.
2. **Processamento do IDF** (`confortimetro/idf/processor.py`): valida e insere
   os schedules de controle (`AC_*`, `VENT_*`, `JANELA_*`, `PMV_*`, `ADAP_*`,
   `EM_CONFORTO_*`, `DOAS_STATUS_*`, `METABOLISMO`, `WORK_EF`, …). **Grava o IDF
   modificado no lugar.**
3. **ExpandObjects**: copia o IDF para `<input_path>/in.idf`, roda o binário
   `ExpandObjects` (timeout 300 s) e gera `<input_path>/expanded.idf`.
4. **Diretório de saída** criado; a configuração efetiva é salva em
   `<output_path>/configs.json`.
5. **EnergyPlus** roda via `pyenergyplus`, com o condicionador registrado no
   callback `begin_zone_timestep_after_init_heat_balance` — ou seja, o controle
   de conforto é decidido a cada timestep dentro da simulação.
6. **Pós-processamento**: `eplusout.eso` → uma planilha por zona → estatísticas →
   recorte por período.

Uma simulação anual leva de dezenas de minutos a horas. O EnergyPlus escreve
seu progresso direto no stdout (`Warming up`, `Starting Simulation at …`).

## 6. Requisitos do IDF

O IDF precisa já conter, por zona listada em `rooms`, os objetos que o
processador altera — em especial `PEOPLE_<ZONA>`, o PTHP `<ZONA> PTHP` e os
schedules citados acima. Um IDF genérico de outra fonte **não** funciona sem
adaptação; use `examples/idf/FAURB/FAURB_PTHP_ENTORNO.idf` como
referência. Erros de validação abortam antes da simulação com
`Erros de validação do IDF: [...]`.

O intervalo de simulação (`RunPeriod`) e `timesteps_per_hour` vêm do IDF. O
pós-processamento assume **ano de 2015, 6 timesteps por hora** e descarta as
primeiras 288 linhas (dois dias de aquecimento); IDFs com outra configuração
produzem carimbos de data errados nas planilhas.

## 7. Saídas em `output_path`

| Arquivo | Conteúdo |
|---|---|
| `configs.json` | Configuração efetiva daquela execução. |
| `eplusout.eso` / `.csv` / `.err` / `.eio` / `.rdd` | Saídas brutas do EnergyPlus. Comece o diagnóstico por `eplusout.err`. |
| `<ZONA>.xlsx` | Série temporal por zona: temperatura externa, ocupação, PMV, temperatura operativa, CO₂, estados de janela/ventilador/AC/DOAS. |
| `ESTATISTICAS.xlsx` | Uma linha por zona com frações do tempo ocupado: aquecimento, resfriamento, ventilador ligado, janela aberta, DOAS, desconforto, CO₂ máximo. |
| `ATELIE1_SPLIT.xlsx` | Recorte por período (`VERAO`, `INVERNO`, `DIAS_VERAO`, `DIAS_INVERNO`). |

Atenção: o recorte por período é gerado **apenas para `ATELIE1`**
(hardcoded em `Simulation._process_results`). Se `ATELIE1` não estiver em
`rooms`, essa etapa é pulada com um aviso na fila de mensagens.

## 8. Armadilhas ao automatizar

- **Execuções paralelas colidem.** `in.idf` e `expanded.idf` são gravados em
  `input_path`, que é o diretório do IDF de entrada. Para rodar várias
  simulações ao mesmo tempo, copie o IDF para um diretório próprio por execução
  e aponte `idf_path` para a cópia.
- **O IDF de entrada é modificado no lugar.** Trabalhe sobre cópias; o
  `git status` do repositório acusa mudanças em
  `examples/idf/FAURB/*.idf` depois de cada execução.
- **`output_path` é reutilizado** se já existir; resultados antigos podem se
  misturar aos novos. Use um diretório novo por execução.
- **Sempre execute a partir da raiz do repositório.**
- **Falha silenciosa de dependência**: sem `openpyxl`/`pandas` a simulação roda
  inteira e só quebra no pós-processamento. Valide as dependências antes.
- **Erros agora abortam.** O pipeline checa: handlers do EnergyPlus ausentes
  (aborta no primeiro timestep), exceções dentro do callback do condicionador
  (guardadas e relançadas depois do run — o ctypes as engolia), código de saída
  do `run_energyplus`, `eplusout.end` (status oficial do EnergyPlus),
  comprimento das séries do `.eso` contra o período esperado e falha ao gravar
  cada `<ZONA>.xlsx`. Qualquer um deles faz o `cli.py` sair com código 1.
- **Sem streaming de progresso**: as mensagens do pipeline vão para uma `Queue`
  e são impressas ao final. O sinal de vida durante a execução é o stdout do
  próprio EnergyPlus.
- Para retomar o pós-processamento de uma simulação já rodada sem simular de
  novo, use as funções de `confortimetro/results/`
  (`summary_rooms_results_from_eso`, `get_stats_from_simulation`,
  `split_target_period_excel`) diretamente sobre o `output_path`.

## 9. Diagnóstico

| Sintoma | Causa provável |
|---|---|
| `No module named 'pyenergyplus'` | `energy_path` errado ou EnergyPlus não instalado. |
| `IDD file not found: <path>/Energy+.idd` | `energy_path` não aponta para a raiz da instalação. |
| `Erros de validação do IDF: [...]` | O IDF não tem os objetos/zonas esperados; confira `rooms`. |
| `ExpandObjects falhou: ...` | IDF inválido ou binário `ExpandObjects` ausente/sem permissão. |
| `Timeout ao expandir objetos` | ExpandObjects passou de 300 s. |
| `Campo desconhecido em --set: X` | Nome de campo inválido; confira com `--print-config`. |
| Simulação termina mas faltam `.xlsx` | Falha no pós-processamento; veja o traceback e `eplusout.err`. |
| `File <ZONA>.xlsx not found! Skipping...` | A zona não existe no `.eso`; nome errado em `rooms`. |

## 10. Referência de código

| Caminho | Papel |
|---|---|
| `cli.py` | Entrada por linha de comando. |
| `main.py` | Entrada da interface Tkinter. |
| `bin/run_web.sh` → `confortimetro/web/app.py` | Interface web Flask/Socket.IO. |
| `confortimetro/simulation.py` | Orquestração do pipeline. |
| `confortimetro/idf/processor.py` | Modificações no IDF via eppy. |
| `confortimetro/control/` | Controladores de conforto por timestep. |
| `confortimetro/config.py` | Esquema de configuração. |
| `confortimetro/results/` | Pós-processamento e planilhas. |

## Detecção do EnergyPlus

Quando o `energy_path` do config está vazio ou não aponta para uma instalação
válida (a pasta precisa conter **`Energy+.idd`** e **`pyenergyplus/api.py`**),
`find_energy_path()` procura sozinho, nesta ordem, e prefere sempre a versão
9.4:

1. variável de ambiente `ENERGYPLUS_DIR`;
2. `energyplus` no `PATH`;
3. diretórios padrão da plataforma — `C:\EnergyPlusV*` e
   `%ProgramFiles%\EnergyPlusV*` no Windows, `/usr/local/EnergyPlus-*` e
   `/opt/EnergyPlus-*` no Linux, `/Applications/EnergyPlus-*` no macOS;
4. no Windows, as instalações registradas no desinstalador (registro).

Instalação em lugar não convencional: exporte `ENERGYPLUS_DIR` ou passe
`--set energy_path=...`. Na interface gráfica há o botão **🔍 Detectar** ao lado
do campo, e o status embaixo dele diz se a instalação é válida e se a versão é a
esperada.
