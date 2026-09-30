# Fluxos de uso — Ambiens

Diagnóstico da interface atual e proposta para o público principal: **pesquisador que já dispõe de IDF e EPW**. Base: leitura da implementação em 26/09/2026; os fluxos propostos ainda não estão implementados. Aqui, “verificado” significa conferido no código e nos testes existentes, não observado com usuários nem validado por uma simulação anual.

## Objetivo e escopo

Permitir configurar um experimento, executá-lo sem perder a rastreabilidade do modelo, inspecionar os resultados e comparar cenários com confiança. O caminho principal é **preparar → validar → executar → analisar → duplicar e comparar**. Inclui o uso interativo da GUI, recuperação de resultados e a CLI como alternativa para automação. Instalação do EnergyPlus, criação de um IDF do zero, desenho físico do edifício e alteração do algoritmo de conforto ficam fora desta rodada.

## Mapa do que existe hoje

| ID | Objetivo do pesquisador | Caminho atual | Saídas e exceções observadas |
|---|---|---|---|
| F1 | Preparar o ambiente | Execuções → Configurações → escolher pasta das execuções e instalação do EnergyPlus; a instalação pode ser detectada | As escolhas alimentam a configuração em memória; a pasta da listagem é atualizada. Salvar a configuração é uma ação separada na tela Execução. `main_window.py:408-428, 522-553`; `path_config_panel.py:41-77` |
| F2 | Configurar um cenário | Execuções → Nova execução → Arquivos (IDF/EPW), Período/Ocupação, Conforto, Equipamentos e Zonas | As zonas são oferecidas a partir do IDF. Período/Ocupação só entram na simulação depois de **Salvar como novo IDF**, que troca o arquivo selecionado; campos vazios preservam os valores existentes. Pode-se Salvar/Carregar um JSON. `main_window.py:343-406, 776-834`; `idf_editor_panel.py`; `simulation_config_panel.py` |
| F3 | Validar e executar | Execução → Validar e executar | Confere existência de IDF, EPW e diretório do EnergyPlus. Para equipamentos faltantes, oferece gerar outro IDF ou confirmar explicitamente a execução incompleta. Cria pasta nova, mostra log/progresso e permite solicitar parada. `main_window.py:555-774, 862-915` |
| F4 | Encontrar e recuperar resultados | Execuções → selecionar uma execução → Ver detalhes; ou Regerar estatísticas | A listagem distingue execução em andamento, pronta, sem planilhas, sem estatísticas e desatualizada. A regeneração usa planilhas e, quando possível, o ESO; ocorre em segundo plano. `simulations_panel.py:209-275, 539-578`; `results/compare.py:133-160, 192-214` |
| F5 | Analisar uma execução | Detalhes → Resumo / Série temporal / Assistente; Abrir pasta | Resumo lê `ESTATISTICAS.xlsx`, série temporal lê a planilha da zona sob demanda; assistente exige chave Gemini na primeira pergunta. Sem estatísticas, a tela orienta a regeneração. `main_window.py:225-341, 933-1059`; `timeseries_panel.py`; `assistant_panel.py:230-419` |
| F6 | Repetir e comparar cenários | Duplicar execução → ajustar parâmetros → executar; selecionar 2+ execuções → Comparar selecionadas → zona, gráfico, CSV | A duplicação recupera o IDF original (`source_idf_path`) e não reutiliza a pasta de resultados. A comparação pode excluir execuções sem estatísticas e avisa sobre períodos divergentes; gráficos de série são gerados sob demanda. `main_window.py:1061-1085`; `comparison_panel.py:61-83, 251-283, 311-374` |
| F5b | Rodar um cenário pedido ao assistente | Assistente → pedir a simulação → cartão de confirmação → **Executar simulação** | O assistente só propõe (`propor_simulacao`): valida IDF, EPW, EnergyPlus, zonas e faixas; avisa equipamento faltando e período longo. Confirmada, a simulação segue o caminho do botão Executar (`MainWindow.start_simulation`) e aparece em Execuções como em simulação; uma por vez. PRD 005; `assistant/simulacao.py`; `assistant_panel.py` |
| F7 | Automatizar lotes | `cli.py --config ... --set ...` e `scripts/lote.py`; `--print-config` mostra a configuração resolvida | CLI e GUI usam o mesmo pipeline; uma pasta de saída por execução é responsabilidade de quem automatiza. `docs/CLI.md:32-90, 192-204`; `cli.py:49-74` |

## Atritos e riscos priorizados

| Prioridade | Evidência | Efeito no fluxo | Melhoria proposta |
|---|---|---|---|
| P0 | `SimulationConfigPanel.get_configuration()` devolve `{}` quando **qualquer** campo numérico é inválido; `_update_config_from_ui()` ignora `{}` e `_validate_configuration()` segue para executar (`simulation_config_panel.py:212-238`; `main_window.py:522-538, 656-699, 862-899`). | O pesquisador pode rodar por horas com valores anteriores sem perceber. O rótulo “Validar e executar” sugere validação de parâmetros, mas a checagem atual é sobretudo de caminhos/equipamentos. | Bloquear a execução e o salvamento da configuração quando houver campo inválido; indicar aba, campo e erro; mostrar resumo dos parâmetros efetivos antes de iniciar. |
| P1 | “Nova execução” na barra superior abre diretamente `editor`, enquanto o outro botão usa `on_new_run()`; ambos deixam os campos como estavam (`main_window.py:193-212, 919-921`). Duplicar também abre o mesmo editor (`1061-1085`). | Não fica claro se a próxima rodada é nova, baseada no último rascunho ou duplicada. | Definir semântica explícita para **Nova execução** (valores padrão ou último rascunho, a decidir com usuários), marcar “Duplicada de …” e mostrar origem do cenário no editor. Unificar as duas entradas de Nova execução. |
| P1 | Selecionar 2+ execuções habilita a comparação mesmo se alguma não está pronta (`simulations_panel.py:307-321`); `ComparisonPanel.compare()` omite as incompletas e só avisa depois (`comparison_panel.py:251-275`). | É possível entrar na tela com menos de dois cenários realmente comparáveis; a comparação pode parecer completa quando não é. | Mostrar já na seleção quantas execuções/zona têm dados, bloquear se houver menos de duas elegíveis e listar nominalmente as excluídas; conservar aviso de períodos divergentes junto dos totais. |
| P1 | Se `ESTATISTICAS.xlsx` faltar, detalhes orienta a regerar; o botão de regerar nos detalhes chama a ação da seleção na lista (`main_window.py:977-1003, 1087-1092`). | A recuperação depende de seleção e status de uma outra página, em vez de operar claramente sobre a execução aberta. | Ação de recuperação vinculada à execução exibida, com progresso e retorno de sucesso/erro na própria tela de detalhes. |
| P2 | `docs/PROJETO.md:26-44, 186-199, 271-284` ainda diz que o IDF de entrada é alterado e que execuções paralelas colidem; o comportamento atual copia o modelo para a pasta da execução (`docs/CLI.md:166-184, 281-288`). | Instruções conflitantes reduzem a confiança sobre proveniência e segurança do modelo. | Atualizar a documentação técnica obsoleta e apontar deste mapa para um guia único de execução. |
| P2 | A GUI permite escolher manualmente o diretório do EnergyPlus, mas `_validate_configuration()` apenas verifica se ele existe (`main_window.py:671-673`); `is_energy_path()` exige IDD e API (`config.py:73-85`). | Uma pasta existente mas inadequada pode falhar só depois do início. | Reusar a checagem de instalação na pré-validação e apresentar a versão esperada. |

Prioridades são **hipóteses de impacto**, não resultados medidos com usuários. P0 significa risco de resultado cientificamente incorreto; P1 interrompe ou torna ambígua uma tarefa central; P2 melhora compreensão e diagnóstico.

## Fluxo-alvo para o pesquisador

1. **Preparação (uma vez por máquina).** Conferir EnergyPlus 9.4 e pasta de execuções; status claro de instalação válida ou instrução de correção. A configuração permanece visível em Configurações.
2. **Definir cenário.** Entrar em Nova execução, escolher IDF e EPW, conferir zonas e módulo. Ajustar período/ocupação em uma cópia do IDF quando necessário. Exibir o IDF efetivamente selecionado, sobretudo após uma correção de equipamentos.
3. **Revisar antes do custo alto.** Validar todos os campos e intervalos; mostrar erros no local e impedir o início. Mostrar modelo/clima, zonas, período, módulo, parâmetros relevantes, pasta nova de saída e avisos de equipamentos. O usuário confirma apenas escolhas de modelagem que exigem decisão.
4. **Acompanhar.** A execução aparece como “em simulação”; log, etapa, progresso quando disponível e solicitação de parada permanecem acessíveis. Estados finais distintos: concluída, interrompida, falhou. A pasta e o diagnóstico continuam acessíveis nos três estados.
5. **Analisar e recuperar.** Abrir Resumo e selecionar zona na Série temporal; se faltarem agregados, oferecer regeneração ali com feedback. Assistente é opcional e deve usar o contexto da execução aberta.
6. **Comparar experimento.** Duplicar um cenário mantendo a proveniência, mudar apenas a variável de interesse, executar em pasta nova; selecionar ao menos duas execuções **prontas e com a mesma zona**; sinalizar diferenças de período antes da interpretação de kWh, comparar gráficos/tabela e exportar CSV.

## Critérios verificáveis para a próxima implementação

- Um número inválido em qualquer aba impede Salvar e Validar e executar, preserva o que foi digitado e informa qual campo corrigir; nenhum diretório de execução é criado.
- A abertura por qualquer um dos botões “Nova execução” segue a mesma regra de origem dos parâmetros, informada no editor; “Duplicar” exibe a origem e usa o IDF escolhido na execução anterior, com pasta de saída inédita.
- Selecionar duas execuções sem estatísticas não produz uma comparação aparentemente válida; a interface informa quais faltam e como recuperá-las.
- Regerar estatísticas a partir de Detalhes atua na execução aberta e atualiza seu Resumo depois da conclusão ou mostra o erro da tentativa.
- EnergyPlus em pasta existente sem `Energy+.idd`/API é rejeitado antes de criar a execução.
- Execuções com períodos diferentes exibem aviso ao lado dos totais da comparação; nenhum total é apresentado como diretamente comparável sem esse contexto.

## Questões para validar com pesquisadores

1. “Nova execução” deve partir dos valores padrão, do último rascunho ou da última execução? A recomendação inicial é **último rascunho explicitamente identificado**, com Duplicar reservado para repetir uma execução concluída; confirmar em 3–5 sessões observadas [meta sugerida, não medida].
2. Que campos devem aparecer na revisão antes da execução para detectar um cenário errado sem obrigar a percorrer todas as abas?
3. Uma execução com períodos distintos deve apenas avisar, ou deve impedir comparações de energia total? A recomendação inicial é aviso persistente, sem bloquear métricas normalizadas.

Fonte operacional atual para a CLI e pipeline: [`CLI.md`](CLI.md). Este documento não altera parâmetros científicos nem substitui validação do IDF pelo pipeline.
