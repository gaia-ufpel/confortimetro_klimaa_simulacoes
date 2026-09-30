# PRD — Assistente propõe simulações e o usuário confirma
Status: em implementação · Autor: Gabriel Leite Bessa · Data: 29/09/2026 · PRDs relacionados: 003, 004

## 1. Problema

O assistente (PRD 003) só analisa. Quando a análise sugere outra rodada ("e com a
janela sempre fechada?", "e com `temp_ac_max` 28?"), o usuário sai do chat, abre
**Nova execução** ou **Duplicar**, acha os campos e dispara à mão. Quem não conhece
os campos de `SimulationConfig` trava aí.

## 2. Decisão

O assistente **propõe**; só o usuário **executa**. Uma simulação anual leva de
dezenas de minutos a horas e passa de 1 GB, então nada roda sem um clique explícito
sobre a configuração que vai rodar.

1. Ferramenta nova `propor_simulacao(base_execucao?, alteracoes[{campo, valor}], motivo)`
   em `assistant/tools.py`. Não executa nada: parte da configuração da tela de
   execução (lida na thread do Tk ao enviar a pergunta) ou da `configs.json` de uma
   execução (como o **Duplicar**: `source_idf_path`, saída nova), aplica as
   alterações com a semântica do `--set` do CLI e valida.
2. Validação (`assistant/simulacao.py`), equivalente ao `--print-config` mais o que a
   GUI confere antes de rodar: IDF e EPW existem, EnergyPlus válido
   (`is_energy_path`), zonas existem no IDF (`read_zone_names`), pares min/max
   coerentes, `module_type` válido. Inválida → erro para o modelo corrigir, sem
   proposta. Equipamento faltando (`unwired_equipment`) e período > 31 dias viram
   **avisos** na confirmação.
3. Só campos de modelo/clima/conforto/controle são alteráveis (`EDITABLE_FIELDS`).
   Saída, EnergyPlus e derivados ficam fora; o período vem do `RunPeriod` do IDF.
4. A proposta fica na conversa (`proposals`, status `pendente → iniciada |
   descartada | substituida`) e o painel mostra um **cartão de confirmação** com a
   configuração, os avisos e os botões **Executar simulação** / **Descartar**. Uma
   proposta nova substitui a pendente.
5. **Executar simulação** chama `MainWindow.start_assistant_simulation`, que usa o
   mesmo `start_simulation` do botão Executar: pasta nova na raiz da listagem
   (`new_run_path`), linha "em simulação" em Execuções, log, thread acompanhada por
   `_check_simulation_thread`. Nenhum pipeline novo, nenhuma espera em primeiro
   plano: o chat continua usável e, ao terminar, o usuário não é levado para fora da
   conversa.
6. Uma simulação por vez, como na tela de execução: com outra rodando, a
   confirmação é recusada com mensagem e a proposta continua pendente.
7. O prompt de sistema lista o estado de cada proposta; o modelo não afirma que uma
   simulação começou ou terminou.

### Faixas aceitas na proposta

`FIELD_RANGES`/`POSITIVE_RANGES` em `confortimetro/assistant/simulacao.py`. Valor
não finito é recusado em qualquer campo numérico. Faixas da tela de execução e da
validade do PMV (ISO 7730 / ASHRAE 55):

| Campo | Faixa |
|---|---|
| `met` | 0,8 a 4,0 |
| `wme` | ≥ 0 e < `met` |
| `clo_min`, `clo_max` | 0 a 2 |
| `pmv_lowerbound`, `pmv_upperbound` | -3 a 3 |
| `pmv_comfort_bound` | > 0 e ≤ 3 |
| `temp_ac_min`, `temp_ac_max` | 10 a 35 °C |
| `max_vel` | > 0 e ≤ 2 m/s |
| `co2_limit` | 400 a 5000 ppm |
| `adaptative_bound` | um dos valores de `PORCENT2ADAPTATIVE` |
| `clo_delta`, `air_speed_delta` | > 0 |
| `temp_open_window_bound` | margem (°C) sobre `temp_ar`, padrão 5; maior que 0 e até 15 |

O IDF não entra na proposta: é sempre o escolhido pelo usuário (ou o da execução
base). IDF sem `Zone` recusa qualquer `rooms`. Uma proposta pendente por resposta;
as extras voltam ao modelo como erro.

## 3. Fora

- Execução sem confirmação, fila de simulações ou várias em paralelo.
- Editar o IDF (período, ocupação) pelo chat — continua no **Editar IDF**.
- Corrigir equipamento pelo chat: a proposta só avisa; confirmar é rodar com
  `ignore_missing_equipment`, como o "Rodar mesmo assim?" da tela de execução.
- Servidor MCP (outra frente).

## 4. Critério de pronto

- Teste de GUI: pedido → proposta validada → confirmação → execução iniciada por
  `start_simulation` → listada "em simulação"; descartar ou não confirmar não roda
  nada (`tests/test_gui_pages.py`).
- Testes de ferramenta: validação recusa zona inexistente, arquivo faltando, campo
  proibido, faixa invertida e módulo inválido (`tests/test_assistant.py`).
