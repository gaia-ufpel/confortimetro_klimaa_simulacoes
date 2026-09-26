# PRD — Ferramentas de diagnóstico do assistente
Status: em implementação · Autor: Gabriel Leite Bessa · Data: 26/09/2026 · PRD relacionado: 003

## 1. Problema

As ferramentas do PRD 003 leem indicadores e séries agregadas, mas não explicam
*por que* uma zona sai do conforto. Na análise do desconforto de `SEC_LINSE`
(execução `20260926_1420`) faltou saber: como é o envelope da sala, por onde ela
perde calor, se o PTHP dá conta, que setpoint o controlador pediu e por que a
janela abriu ou fechou.

## 2. Ferramentas já entregues

Todas em `confortimetro/assistant/tools.py`, só de leitura, com saída cortada
por `_limit`.

| Ferramenta | Fonte | Devolve |
|---|---|---|
| `inspecionar_zona` | `eplustbl.csv` + `modelo.idf` | área, volume, pé-direito, W/m², m²/pessoa, superfícies externas (U, azimute, orientação), janelas (U, SHGC), WWR por orientação, superfícies do AirflowNetwork |
| `balanco_termico` | `eplustbl.csv` (Sensible Heat Gain Summary) | kWh por mecanismo no período todo e componentes em W nos picos |
| `inspecionar_hvac` | `eplustbl.csv` + série | capacidades das serpentinas, vazões, carga de projeto, setpoint não atendido do E+, potência entregue × capacidade |
| `sinais_controle` | série da zona | PMV/clo do controlador, setpoints, banda adaptativa, estados, W do PTHP + resumo |
| `serie_timestep` | série da zona | qualquer variável sem agregação |

`results/tabular.py` lê o `eplustbl.csv`; o mapa superfície → zona sai do texto
do `modelo.idf` (`idf.processor._iter_objects`), sem eppy.

## 3. Limitações e como são superadas

### 3.1 Motivo de cada decisão do controlador

**Antes:** só os estados (janela, AC, …) iam para a planilha; o motivo tinha de
ser deduzido.

**Solução:** um schedule `MOTIVO_<ZONA>` por sala, escrito pelo controlador a
cada timestep, com a **soma de bits** de `confortimetro/control/motivos.py`
(`Motivo`, um `IntFlag`). Vários motivos valem ao mesmo tempo — a janela pode
estar bloqueada pela externa fria *e* o AC ligado por PMV *e* o setpoint no
limite — e todos ficam registrados. O float do EnergyPlus é exato para inteiros
até 2²⁴, então cabem 24 bits.

| Bit | Motivo | Quando |
|---:|---|---|
| 0 | `OCUPADA` | sala com gente |
| 1 | `CONFORTO_SO_COM_CLO` | clo sozinho levou o PMV à faixa |
| 2 | `AC_TEMPO_MAXIMO` | AC desligado por tempo máximo |
| 3 | `JANELA_ABERTA_ADAPTATIVO` | operativa dentro da banda |
| 4 | `JANELA_ABERTA_COM_VENTILADOR` | operativa 25–27,2 °C |
| 5 | `JANELA_BLOQUEADA_EXTERNA_QUENTE` | externa > máximo adaptativo |
| 6 | `JANELA_BLOQUEADA_EXTERNA_FRIA` | externa < temp_ar − `temp_open_window_bound` |
| 7 | `JANELA_BLOQUEADA_AC_LIGADO` | AC ligado impede abrir |
| 8 | `JANELA_FECHADA_OPERATIVA_FORA` | externa permitia, operativa fora da banda |
| 9 | `VENTILADOR_POR_PMV` | ventilador ajustado por PMV |
| 10 | `AC_LIGADO_POR_PMV` | AC ligou neste timestep |
| 11 | `AC_MANTIDO` | AC já estava ligado |
| 12 | `SETPOINT_AQUECIMENTO_NO_LIMITE` | setpoint subiu até `temp_ac_max` sem atingir o PMV |
| 13 | `SETPOINT_RESFRIAMENTO_NO_LIMITE` | setpoint desceu até `temp_ac_min` sem atingir o PMV |
| 14 | `DOAS_POR_CO2` | CO₂ ≥ `co2_limit` com janela fechada |
| 15 | `VAZIA_JANELA_PURGA_CO2` | sala vazia, janela aberta para CO₂ |
| 16 | `VAZIA_JANELA_TRAVADA_FRIO` | trava após esfriar a sala vazia |
| 17 | `VAZIA_JANELA_INVERNO` | mês de inverno, sala vazia não abre |
| 18 | `JANELA_FECHADA_VENTILADOR_NO_LIMITE` | operativa 25–27,2 °C, mas o vento adaptativo passaria de `max_vel` (vem junto com o bit 8) |

Regras: bits novos só no fim, nunca renumerar (planilhas antigas dependem dos
valores). Registrar o motivo **não pode mudar decisão nenhuma** — os testes
comparam as ações com e sem o registro. Os módulos sem janela ou sem ventilador
usam só os bits que se aplicam a eles. Na sala vazia a janela fechada também
marca os bits 5 e 6 quando a externa a bloqueia (lá o limite quente é `≥`); o
bit 16 só vale enquanto a trava ainda segura a janela (operativa abaixo da
neutra). Os bits 9 e 12/13 são conservadores: ventilador por PMV só com
velocidade final > 0, setpoint no limite só se o PMV *no* limite ainda fica fora
da faixa.

A planilha ganha a coluna `MOTIVO_<ZONA>:Schedule Value` (apelido `motivo`);
as ferramentas devolvem os nomes decodificados com `motivos.decode`.

### 3.2 Potência demandada, não só entregue

**Antes:** só a energia entregue pelo PTHP; a capacidade vinha do relatório.

**Solução:** variáveis de saída novas, por timestep, em
`IDFProcessor._add_output_variables`:

| Apelido | Variável do EnergyPlus |
|---|---|
| `demanda_aquecimento_w` / `demanda_resfriamento_w` | `Zone Predicted Sensible Load to Heating/Cooling Setpoint Heat Transfer Rate` |
| `serpentina_aquecimento_w` / `serpentina_apoio_w` | `Heating Coil Heating Rate` (DX e resistência) |
| `serpentina_resfriamento_w` | `Cooling Coil Total Cooling Rate` |
| `termostato_aquecimento` / `termostato_resfriamento` | `Zone Thermostat Heating/Cooling Setpoint Temperature` |

`inspecionar_hvac` passa a comparar demanda × entrega × capacidade: horas com
demanda acima da capacidade (subdimensionamento real) e horas em que a
resistência de apoio entrou.

### 3.3 Balanço térmico por período

**Antes:** só o total anual do `eplustbl.csv`.

**Solução:** o balanço do ar da zona por timestep (W; positivo = calor entrando
no ar):

| Apelido | Variável |
|---|---|
| `balanco_ganhos_internos_w` | `Zone Air Heat Balance Internal Convective Heat Gain Rate` |
| `balanco_superficies_w` | `Zone Air Heat Balance Surface Convection Rate` |
| `balanco_entre_zonas_w` | `Zone Air Heat Balance Interzone Air Transfer Rate` |
| `balanco_ar_externo_w` | `Zone Air Heat Balance Outdoor Air Transfer Rate` (infiltração/janela) |
| `balanco_sistema_ar_w` | `Zone Air Heat Balance System Air Transfer Rate` (PTHP/DOAS) |
| `balanco_sistema_conv_w` | `Zone Air Heat Balance System Convective Heat Gain Rate` |
| `balanco_armazenamento_w` | `Zone Air Heat Balance Air Energy Storage Rate` |
| `janelas_ganho` / `janelas_perda` | `Zone Windows Total Heat Gain/Loss Energy` (J) |

`balanco_termico` aceita `inicio`/`fim` e `somente_ocupado`, integra a série em
kWh por componente e cai no relatório anual quando a execução é anterior a
essas colunas (avisando).

Custo: ~19 colunas a mais por zona no ESO e na planilha. Se pesar, o grupo do
balanço pode ir para frequência horária.

### 3.4 Corte de linhas em `sinais_controle`

**Antes:** um mês ocupado (~1500 timesteps) caía para 25 linhas.

**Solução**, só na ferramenta (vale para execuções antigas):
- `apenas_mudancas: true` — devolve só os timesteps em que janela, ventilador,
  AC, DOAS, setpoints ou motivo mudaram, com a duração até a próxima mudança.
- `colunas` — subconjunto das colunas de controle.
- O resumo passa a contar horas por motivo (cada bit) no período.

## 4. Compatibilidade

- Execuções antigas não têm as colunas das seções 3.1–3.3: as ferramentas
  dizem isso e usam o que existe; nada quebra.
- O cache de séries subiu para `CACHE_VERSION = 3` (a primeira leitura de cada
  zona volta a abrir a planilha, ~22 s).
- Para ter os dados novos, a execução precisa ser simulada de novo.

## 5. Verificação

- Testes unitários do controlador: o motivo gravado para cenários conhecidos e
  as decisões idênticas às de antes.
- Testes das ferramentas com planilhas sintéticas que têm e que não têm as
  colunas novas.
- Uma simulação curta (poucos dias) com EnergyPlus confirmando que as colunas
  chegam ao `<ZONA>.xlsx`.
