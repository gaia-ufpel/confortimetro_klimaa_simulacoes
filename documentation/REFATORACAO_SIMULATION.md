# Refatoração do Sistema de Simulação - Separação de Responsabilidades

## Resumo das Modificações

### 1. Criação do IDFProcessor
- **Arquivo:** `src/processors/idf_processor.py`
- **Responsabilidade:** Manipulação completa de arquivos IDF
- **Funcionalidades:**
  - Validação de arquivos IDF
  - Modificação de horários e configurações
  - Adição de objetos IDF
  - Configuração de variáveis de saída
  - Resumo de informações do IDF

### 2. Refatoração da Classe Simulation
- **Arquivo:** `src/simulation.py`
- **Nova Responsabilidade:** Orquestração da simulação
- **Mudanças principais:**
  - Removida toda lógica de manipulação IDF
  - Adicionado uso do IDFProcessor
  - Melhor estruturação do processo de simulação
  - Logging melhorado
  - Tratamento de erros mais robusto

### 3. Separação de Responsabilidades

#### Antes da Refatoração:
```
Simulation.py
├── Manipulação IDF
├── Configuração de horários
├── Adição de objetos
├── Execução EnergyPlus
├── Processamento de resultados
└── Logging
```

#### Após a Refatoração:
```
Simulation.py (Orquestração)
├── Configuração do condicionador
├── Coordenação de etapas
├── Execução EnergyPlus
├── Processamento de resultados
└── Logging

IDFProcessor.py (Manipulação IDF)
├── Validação IDF
├── Modificação de horários
├── Adição de objetos
├── Configuração de saídas
└── Resumo de informações
```

## Benefícios da Refatoração

### 1. **Separação Clara de Responsabilidades**
- Cada classe tem uma responsabilidade específica e bem definida
- Facilita manutenção e debugging
- Reduz acoplamento entre componentes

### 2. **Melhor Testabilidade**
- IDFProcessor pode ser testado independentemente
- Simulação pode usar mocks do IDFProcessor
- Testes unitários mais focados

### 3. **Código Mais Limpo**
- Métodos menores e mais focados
- Menos duplicação de código
- Melhor legibilidade

### 4. **Extensibilidade**
- Fácil adição de novos processadores
- IDFProcessor pode ser reutilizado em outros contextos
- Simulation pode usar diferentes processadores

### 5. **Tratamento de Erros Melhorado**
- Erros específicos para cada responsabilidade
- Logging mais detalhado
- Recovery mais granular

## Estrutura do Processo de Simulação

### Fluxo Principal (Simulation.run):
1. **Configuração do Módulo Condicionador**
   - Seleção baseada no tipo de módulo
   - Inicialização com configurações

2. **Processamento IDF**
   - Delegado ao IDFProcessor
   - Validação e modificações necessárias

3. **Expansão de Objetos**
   - Execução do ExpandObjects
   - Preparação para simulação

4. **Preparação de Diretórios**
   - Criação de estruturas de saída
   - Salvamento de configurações

5. **Execução EnergyPlus**
   - Registro de callbacks
   - Execução da simulação

6. **Processamento de Resultados**
   - Extração de dados
   - Geração de estatísticas
   - Formatação de saídas

## Funcionalidades do IDFProcessor

### Métodos Principais:
- `validate_idf()`: Validação básica do arquivo
- `process_idf()`: Processamento completo do IDF
- `modify_schedules()`: Modificação de horários específicos
- `add_schedules()`: Adição de novos horários
- `add_output_variables()`: Configuração de variáveis de saída
- `get_idf_summary()`: Resumo das informações do IDF

### Configurações Suportadas:
- Horários de MET e WME
- Configurações de temperatura AC
- Horários de controle (janela, ventilação, AC, etc.)
- Variáveis de saída customizadas
- Objetos de conforto térmico

## Compatibilidade

### Interfaces Mantidas:
- `Simulation(configs)`: Construtor mantido
- `simulation.run(queue)`: Interface de execução mantida
- `simulation.get_idf_summary()`: Agora delega ao IDFProcessor

### Dependências:
- Todas as dependências externas mantidas
- Novos imports adicionados de forma backward-compatible
- Configurações existentes continuam funcionando

## Próximos Passos Recomendados

1. **Testes Unitários**
   - Criar testes para IDFProcessor
   - Testes de integração para Simulation
   - Mocks para EnergyPlus API

2. **Validação Avançada**
   - Validação mais robusta de arquivos IDF
   - Verificação de dependências entre objetos
   - Validação de configurações de usuário

3. **Logging Estruturado**
   - Logs em formato JSON
   - Diferentes níveis de verbosidade
   - Métricas de performance

4. **Configuração Flexível**
   - Processadores IDF configuráveis
   - Templates de configuração
   - Validação de esquemas

5. **Documentação de API**
   - Documentação detalhada dos métodos
   - Exemplos de uso
   - Guias de integração

## Arquivos Modificados

- `src/simulation.py`: Refatorado completamente
- `src/processors/__init__.py`: Criado
- `src/processors/idf_processor.py`: Criado
- `test_simulation_refactor.py`: Teste da refatoração

## Conclusão

A refatoração foi bem-sucedida em separar as responsabilidades entre orquestração de simulação e manipulação de arquivos IDF. O código agora é mais modular, testável e mantível, seguindo os princípios SOLID de design de software.
