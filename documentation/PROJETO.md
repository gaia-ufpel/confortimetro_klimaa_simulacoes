# Documentação técnica — Confortímetro Klimaa

## 1. Visão geral

O Confortímetro Klimaa executa simulações de edifícios no EnergyPlus e altera,
a cada timestep de zona, os atuadores associados a janelas, ventilação,
velocidade do ar, ar-condicionado, vestimenta (clo) e DOAS. O objetivo é
avaliar e buscar condições de conforto por zona, usando PMV e o modelo
adaptativo do EnergyPlus.

O projeto possui duas interfaces:

| Interface | Entrada | Situação |
| --- | --- | --- |
| Desktop Tkinter | `python main.py` | Caminho integrado ao núcleo de simulação. |
| Web Flask/Socket.IO | `./run_web.sh` | Executa o mesmo pipeline do desktop em uma cópia temporária do IDF por sessão. |

## 2. Arquitetura e fluxo

```text
resources/config.json ──> MainWindow (Tkinter) ──> SimulationConfig
                                                     │
                                                     v
                                               Simulation.run(queue)
                                                     │
                    ┌────────────────────────────────┼───────────────────────────────┐
                    v                                v                               v
            IDFProcessor                       ExpandObjects                    EnergyPlus API
          altera e salva IDF               cria expanded.idf              callback Conditioner
                                                                            por zona/timestep
                                                                                   │
                                                                                   v
                                                            eplusout.eso ─> planilhas .xlsx
```

`Simulation` em `src/simulation.py` é o orquestrador. Ele seleciona um
controlador pelo `module_type`, processa o IDF, chama o `ExpandObjects`, cria
o diretório de saída e roda o EnergyPlus via `pyenergyplus.api`. Ao final,
extrai o arquivo `eplusout.eso` e gera planilhas.

O diagrama do condicionador está em
[`assets/room_conditioner_flowchart.png`](assets/room_conditioner_flowchart.png).

### Componentes

| Local | Responsabilidade |
| --- | --- |
| `main.py` | Cria a janela `MainWindow`. |
| `src/gui/main_window.py` | Carrega/salva a configuração, valida caminhos, inicia a simulação em thread e exibe mensagens da fila. |
| `src/gui/components/` | Painéis de caminhos, parâmetros, controles e logs. |
| `src/utils/simulation_config.py` | Dataclass `SimulationConfig`, serialização JSON e campos derivados do IDF. |
| `src/simulation.py` | Pipeline de execução e pós-processamento. |
| `src/processors/idf_processor.py` | Leitura/alteração do IDF com Eppy. |
| `src/modules/` | Estratégias de controle que o callback do EnergyPlus executa. |
| `src/utils/__init__.py` | Exportação de resultados ESO para Excel, estatísticas e cortes sazonais. |
| `src/web/` | Interface HTTP/WebSocket, uploads e empacotamento de saídas. |

## 3. Requisitos

### Externos

- Python 3.10 é a versão encontrada no ambiente `venv_web`; o código usa
  anotações como `list[str]`, portanto requer Python 3.9 ou superior.
- EnergyPlus instalado. `energy_path` precisa conter `Energy+.idd`, o
  executável `ExpandObjects` (ou `ExpandObjects.exe` no Windows) e o pacote
  `pyenergyplus` compatível.
- Um IDF válido, um EPW e nomes de zonas/pessoas compatíveis com os nomes
  configurados.
- Tkinter para a interface desktop.

### Bibliotecas Python

As dependências declaradas estão em `src/web/requirements.txt`:

```text
Flask 2.3.3, Flask-SocketIO 5.3.6, python-socketio 5.8.0,
python-engineio 4.7.1, eppy, numpy 1.24.3, pandas,
pythermalcomfort, dataclasses-json, pytest e pytest-flask
```

O núcleo também importa `pyenergyplus`, fornecido pela instalação compatível
do EnergyPlus. As demais dependências Python do pipeline estão listadas no
arquivo de requisitos da web.

Instalação manual mínima:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r src/web/requirements.txt ladybug-comfort esoreader matplotlib
```

O `install.sh` não é utilizável no estado atual: ele procura
`requirements.txt` na raiz, arquivo que não existe. Use `run_web.sh`, que
instala as dependências em `venv_web` e inicia a interface funcional.

## 4. Configuração

O arquivo padrão é `resources/config.json`. A configuração é desserializada
por `SimulationConfig.from_json()` e uma cópia é salva em
`<output_path>/configs.json` ao iniciar a simulação.

### Campos

| Campo | Significado |
| --- | --- |
| `_idf_path` | Arquivo IDF de entrada. A propriedade pública correspondente é `idf_path`. |
| `_met` | Metabolismo em met. A propriedade pública é `met`. |
| `met_as_watts` | Campo recalculado como `met × 58,1 × 1,8`; o valor do JSON é sobrescrito na inicialização. |
| `epw_path` | Arquivo climático EPW. |
| `energy_path` | Pasta de instalação do EnergyPlus. |
| `output_path` | Pasta onde o EnergyPlus e o pós-processamento gravam os resultados. |
| `rooms` | Zonas/salas que serão controladas e exportadas. Os nomes precisam coincidir com o IDF. |
| `module_type` | `COMPLETE`, `CLOSED_WINDOW`, `WITHOUT_FAN` ou `FIXED_AC_WITHOUT_FAN`. |
| `pmv_lowerbound`, `pmv_upperbound` | Faixa de PMV considerada confortável. |
| `pmv_comfort_bound` | Tolerância extra usada pelo critério de conforto com janela fechada. |
| `adaptative_bound` | Semifaixa em torno da temperatura adaptativa. |
| `temp_ac_min`, `temp_ac_max` | Limites das temperaturas de aquecimento e resfriamento. |
| `temp_open_window_bound` | Limite para decidir abertura de janela a partir da temperatura externa. |
| `max_vel`, `air_speed_delta` | Máxima velocidade do ar e passo para seu ajuste. |
| `co2_limit` | Limite para acionar o DOAS com janela fechada. |
| `clo_min`, `clo_max`, `clo_delta` | Faixa e passo para ajuste da vestimenta. |
| `wme` | Eficiência de trabalho mecânico usada no PMV. |
| `input_path`, `expanded_idf_path`, `idf_filename` | Derivados de `idf_path` pela dataclass; não devem ser editados manualmente. |

Exemplo reduzido:

```json
{
  "_idf_path": "./resources/EnergyFiles/FAURB/FAURB_PTHP_ENTORNO.idf",
  "_met": 1.2,
  "epw_path": "./resources/WeatherFiles/BRA_RS_Camaqua.869890_INMET.epw",
  "energy_path": "/caminho/para/EnergyPlus",
  "output_path": "./outputs/minha-simulacao",
  "rooms": ["ATELIE1"],
  "module_type": "COMPLETE"
}
```

Não use o `config.json` versionado sem revisão: ele contém um caminho absoluto
específico de outra máquina no campo `output_path`.

## 5. Execução desktop

1. Confira o IDF, EPW, diretório do EnergyPlus e a pasta de saída na janela.
2. Ajuste os campos de conforto e escolha o módulo.
3. Clique em **Executar**. A janela bloqueia apenas os controles; a simulação
   roda em uma `threading.Thread` e mensagens passam por uma `Queue`.
4. Aguarde o log indicar a extração das planilhas.

O botão **Parar** apenas muda o estado visual e registra uma solicitação: ele
não interrompe o processo/API do EnergyPlus. Fechar a aplicação ou alterar a
integração é necessário para cancelamento real.

O IDF de entrada é modificado **no próprio arquivo** por `IDFProcessor` antes
da execução. Faça uma cópia do IDF antes de rodar simulações, especialmente
ao repetir execuções: schedules e algumas variáveis de saída são adicionados
ao arquivo.

## 6. Processamento do IDF e controle térmico

### Alterações no IDF

`IDFProcessor` executa, nesta ordem:

1. valida existência de IDF/IDD e objetos `Building` e `Zone`;
2. altera o nome do `RunPeriod` para o nome da pasta de saída;
3. ajusta schedules de metabolismo e trabalho mecânico; no módulo de AC fixo,
   também ajusta os setpoints existentes;
4. adiciona tipos de schedule, schedules globais e schedules por sala;
5. associa schedules de metabolismo, trabalho e velocidade aos objetos
   `People`;
6. adiciona variáveis de saída em frequência `Timestep`;
7. salva o IDF de entrada.

O callback precisa que o IDF disponibilize os atuadores/schedules com os
nomes esperados, como `CLO_<SALA>`, `JANELA_<SALA>`, `VENT_<SALA>`,
`AC_<SALA>` e `TEMP_OP_MAX_ADAP_<SALA>`. A validação atual não confirma a
existência desses objetos; erros de handle aparecem na execução.

### Módulos disponíveis

| Tipo | Comportamento |
| --- | --- |
| `COMPLETE` | Considera abertura de janela, velocidade/ventilador, ajuste de clo, AC e DOAS. |
| `CLOSED_WINDOW` | Mantém janela fechada; controla ventilação, clo, AC e DOAS. |
| `WITHOUT_FAN` | Considera janela e AC sem estratégia ativa de ventilador. |
| `FIXED_AC_WITHOUT_FAN` | Considera janela e AC fixo, sem ventilador. |

Para zonas ocupadas, a base `Conditioner` primeiro avalia toda a faixa de clo
configurada e aplica o valor cujo PMV fica mais próximo de zero. Se ele já
estiver na faixa de conforto, ventilador e AC são desligados; caso contrário,
os módulos podem ajustar velocidade do ar, janela e AC. PMV é calculado por
`ladybug_comfort.pmv.predicted_mean_vote`, usando velocidade relativa e clo
dinâmico de `pythermalcomfort`.

Para zonas sem ocupação, os módulos desligam os sistemas e podem abrir janela
conforme a estação. O controlador atual considera inverno os meses 6 a 9.

## 7. Saídas

O EnergyPlus grava os arquivos nativos na pasta configurada. Depois, o
pós-processamento gera:

| Artefato | Origem/conteúdo |
| --- | --- |
| `configs.json` | Configuração usada na execução. |
| `eplusout.eso` | Saída nativa do EnergyPlus, insumo do pós-processamento. |
| `<SALA>.xlsx` | Série temporal da sala, incluindo variáveis encontradas no ESO. |
| `ESTATISTICAS.xlsx` | Frações de ocupação/uso de HVAC, desconforto, CO₂ máximo e janela sem ocupação por sala. |
| `ATELIE1_SPLIT.xlsx` | Recortes de verão/inverno para `ATELIE1`. |

O último item é sempre solicitado para `ATELIE1`; se essa sala não estiver na
lista ou seu Excel não for produzido, a etapa final falha. Os períodos de
análise são fixos em `src/utils/__init__.py` e usam datas de 2015.

## 8. Interface web e API

`src/web/app.py` expõe os endpoints abaixo. Uploads aceitam apenas `.idf` e
`.epw`, com máximo de 50 MiB, e são salvos em `uploads/` com nome aleatório.

| Método e rota | Função |
| --- | --- |
| `GET /` | Entrega a página da aplicação e cria uma sessão Flask. |
| `GET /api/config` | Lê a configuração da sessão. |
| `POST /api/config` | Atualiza a configuração da sessão. |
| `POST /api/upload` | Recebe `file` e `type` (`idf` ou `epw`). |
| `POST /api/simulation/start` | Solicita início da simulação. |
| `POST /api/simulation/stop` | Apenas marca a parada solicitada; não cancela o trabalho. |
| `GET /api/simulation/status` | Retorna o estado em memória. |
| `GET /api/simulation/download` | Compacta as saídas temporárias da sessão. |

Eventos Socket.IO: `connected`, `simulation_message`, `simulation_finished`,
`ping` e `pong`.

### Estado real da integração web

`simulation_integration.py` instancia `Simulation` e `SimulationConfig` do
núcleo atual, encaminhando a fila de progresso por Socket.IO. Cada execução
copia o IDF para uma pasta temporária da sessão, de forma que o arquivo enviado
ou selecionado não é alterado. O botão de parada solicita o encerramento à API
do EnergyPlus; o servidor deve permanecer ativo até a finalização da thread.

## 9. Testes e verificação

Testes disponíveis:

| Local | Cobertura pretendida |
| --- | --- |
| `tests/legacy/test_numpy_fix.py` | Importações e compatibilidade de bibliotecas numéricas. |
| `tests/legacy/test_simulation_refactor.py` | Importações da simulação/processador e mapeador de módulos. |
| `tests/legacy/test_interface_improvements.py` | Estrutura e estilos da GUI. |
| `src/web/tests/` | Rotas Flask, upload e Socket.IO. |

Verificação executada durante esta documentação:

```bash
python -m compileall -q main.py src tests
python -m pytest src/web/tests -q
```

A compilação e a suíte web passam no estado atual. A suíte inclui uma execução
do adaptador web com o contrato real de `Simulation.run(queue)`, usando um
simulador de teste para não executar um ano inteiro de EnergyPlus.

## 10. Limitações e manutenção prioritária

1. Tornar `ATELIE1`/datas de 2015 configuráveis no pós-processamento e evitar
   a falha quando essa sala não foi solicitada.
2. Executar sem `debug=True` antes de expor o servidor em rede pública.
3. Revisar os scripts `simulacoes_personalizadas.sh` e `.bat`: eles apontam
   para `src/main.py`, que não existe; o ponto de entrada atual é `main.py`.

## 11. Convenções para desenvolvimento

- Preserve o IDF original fora da pasta de execução ou trabalhe com cópia.
- Ao adicionar uma zona, atualize `rooms` e confirme todos os nomes de
  schedules/atuadores no IDF.
- Para um novo módulo, herde `Conditioner`, implemente
  `room_conditioner(state, room)` e registre a classe em `MODULES_MAPPER`.
- Os diretórios `outputs/`, `logs/` e `backups/` são ignorados pelo Git.
- Os documentos em `documentation/history/` servem como histórico e podem
  divergir do repositório; esta página e o `README.md` são a referência atual.
