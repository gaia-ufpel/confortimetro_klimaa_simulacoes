# Backlog

## UX — revisão das telas capturadas

### Alta prioridade

- [ ] **Dar contexto ao painel de detalhes na listagem** (`runs`)
  - Ao selecionar uma execução, mostrar status, período, zonas, consumo e desconforto.
  - Sem seleção, exibir estado vazio orientando o usuário a escolher uma execução.

- [ ] **Criar estados vazios orientados por ação** (`detail`, `compare`, `assistant`)
  - Detalhes sem planilha: explicar a ausência e oferecer **Regerar estatísticas**.
  - Comparação sem dados suficientes: informar que são necessárias duas ou mais execuções com estatísticas.
  - Assistente sem conversa: apresentar perguntas de exemplo clicáveis.

- [ ] **Adicionar resumo e validação antes da simulação** (`editor`)
  - Junto de **Executar simulação**, mostrar IDF, EPW, zonas, período e timestep usados.
  - Renomear a ação para **Validar e executar** ou validar explicitamente antes de iniciar.
  - Avisar que simulações anuais podem levar horas e ocupar mais de 1 GB.

- [ ] **Exibir as execuções ativas na comparação** (`compare`)
  - Mostrar nomes/chips das execuções comparadas e sua quantidade.
  - Desabilitar controles que dependem de seleção ainda inexistente e explicar o requisito.

- [ ] **Corrigir layout e orientação do editor de IDF** (`idf`)
  - Corrigir o cabeçalho cortado/alinhado à esquerda observado na captura.
  - Informar que campos em branco preservam o valor atual no IDF.
  - Reduzir o espaço ocioso quando a aba possuir poucos campos.

### Média prioridade

- [ ] **Simplificar a barra de ações das execuções** (`runs`)
  - Manter em destaque: **Nova execução**, **Ver detalhes** e **Comparar**.
  - Mover ações secundárias (duplicar, regenerar, abrir pasta, atualizar e assistente) para menu contextual ou para ações da seleção.
  - Desabilitar ações que exigem uma execução ou múltiplas execuções selecionadas.

- [ ] **Clarificar o salvamento das configurações do assistente** (`settings`)
  - Consolidar **Salvar chave** e **Salvar configurações do assistente**, ou separar visualmente credenciais e preferências.
  - Tornar o campo de modelo uma lista de opções válidas quando aplicável.

- [ ] **Validar e explicar caminhos da máquina** (`settings`)
  - Exibir validade também para a pasta de execuções.
  - Indicar disponibilidade/erro de acesso e o impacto de armazenamento no diretório escolhido.

- [ ] **Adicionar indicadores de decisão ao detalhe da execução** (`detail`)
  - Antes da tabela, apresentar consumo total, aquecimento, resfriamento, horas de desconforto e status da execução.

### Baixa prioridade

- [ ] **Ocultar “Cancelar” no assistente quando não houver geração em andamento** (`assistant`).

- [ ] **Adicionar sugestões de perguntas ao assistente** (`assistant`)
  - Exemplos: menor consumo, comparação de desconforto e horários de uso do ar-condicionado.

- [ ] **Tornar o rodapé “Feito por glbessa” mais discreto ou movê-lo para uma tela “Sobre”**.
