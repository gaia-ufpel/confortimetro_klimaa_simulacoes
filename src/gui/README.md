# Interface Gráfica Refatorada - Confortímetro Klimaa

## Visão Geral

A interface gráfica foi completamente refatorada seguindo princípios de **Separação de Responsabilidades** e **Programação Modular**. A nova arquitetura torna o código mais maintível, testável e extensível.

## Estrutura dos Componentes

```
src/gui/
├── __init__.py                     # Exports principais
├── main_window.py                  # Janela principal (Controller)
└── components/
    ├── __init__.py                 # Exports dos componentes
    ├── path_config_panel.py        # Configuração de caminhos
    ├── simulation_config_panel.py  # Configuração de simulação
    ├── results_panel.py            # Exibição de resultados
    └── control_panel.py            # Controles de execução
```

## Como Usar

### Método 1: Nova Interface
```python
from src.gui.main_window import MainWindow

app = MainWindow()
app.mainloop()
```

### Método 2: Compatibilidade (Legado)
```python
from src.gui import SimulationGUI

app = SimulationGUI()
app.mainloop()
```

## Componentes Detalhados

### 🗂️ PathConfigPanel
**Responsabilidade**: Gerenciar configurações de caminhos de arquivos

**Funcionalidades**:
- Seleção de arquivo IDF
- Seleção de diretório de saída
- Seleção de arquivo EPW (clima)
- Seleção do diretório do EnergyPlus
- Validação automática de caminhos
- Callbacks para notificação de mudanças

### ⚙️ SimulationConfigPanel
**Responsabilidade**: Gerenciar parâmetros de simulação

**Funcionalidades**:
- Configurações de PMV (Predicted Mean Vote)
- Parâmetros de temperatura e velocidade
- Configurações de conforto adaptativo
- Parâmetros de vestimenta (Clo)
- Seleção de módulos de simulação
- Configuração de salas
- Validação de dados de entrada

### 📊 ResultsPanel
**Responsabilidade**: Exibir resultados e logs da simulação

**Funcionalidades**:
- Diferentes tipos de mensagem (Info, Warning, Error, Success)
- Timestamps automáticos
- Auto-scroll para acompanhar progresso
- Formatação com cores por tipo de mensagem
- Função de limpeza de resultados
- Text wrapping responsivo

### 🎛️ ControlPanel
**Responsabilidade**: Controlar execução da simulação

**Funcionalidades**:
- Botão Executar/Parar simulação
- Barra de progresso animada
- Status em tempo real
- Salvar/Carregar configurações
- Controle de estado dos botões
- Indicadores visuais de progresso

### 🏠 MainWindow
**Responsabilidade**: Coordenar todos os componentes

**Funcionalidades**:
- Layout responsivo e redimensionável
- Gerenciamento centralizado de configurações
- Coordenação entre componentes via callbacks
- Threading para simulações não-bloqueantes
- Validação centralizada
- Tratamento de erros

## Melhorias Implementadas

### ✅ Arquitetura
- **Separação de Responsabilidades**: Cada componente tem uma função específica
- **Baixo Acoplamento**: Componentes se comunicam via callbacks
- **Alta Coesão**: Funcionalidades relacionadas agrupadas
- **Padrão MVC**: Model (Config), View (Components), Controller (MainWindow)

### ✅ Usabilidade
- **Layout Responsivo**: Interface se adapta ao tamanho da janela
- **Feedback Visual**: Cores e ícones para diferentes tipos de mensagem
- **Progress Tracking**: Barra de progresso e status em tempo real
- **Auto-save**: Configurações salvas automaticamente

### ✅ Manutenibilidade
- **Código Modular**: Fácil de manter e estender
- **Documentação**: Docstrings em todos os métodos
- **Type Hints**: Tipagem para melhor IDE support
- **Protocols**: Contratos bem definidos para callbacks

### ✅ Testabilidade
- **Componentes Isolados**: Podem ser testados independentemente
- **Injeção de Dependência**: Via callbacks para mocking
- **Estado Controlado**: Fácil verificação de estados

## Padrões de Design Utilizados

1. **Observer Pattern**: Callbacks para notificação de mudanças
2. **Strategy Pattern**: Diferentes tipos de mensagem no ResultsPanel
3. **Model-View-Controller**: Separação clara de responsabilidades
4. **Protocol Pattern**: Contratos bem definidos com typing.Protocol

## Executando a Interface

### Pré-requisitos
- Python 3.8+
- tkinter (geralmente incluído com Python)
- Dependências do projeto principal

### Execução
```bash
# Navegue para o diretório do projeto
cd confortimetro_klimaa_simulacoes

# Execute a interface
python -c "from src.gui.main_window import main; main()"
```

## Desenvolvimento Futuro

### Próximas Melhorias Sugeridas:
1. **Testes Automatizados**: Unit tests para cada componente
2. **Validação em Tempo Real**: Feedback imediato nos campos
3. **Tooltips**: Ajuda contextual
4. **Temas**: Dark/Light mode
5. **Undo/Redo**: Histórico de configurações
6. **Múltiplas Abas**: Suporte a várias configurações
7. **Wizard**: Configuração guiada para novos usuários
8. **Export/Import**: Configurações em diferentes formatos

### Extensibilidade:
- **Novos Componentes**: Fácil adição de novos painéis
- **Plugins**: Sistema de plugins para funcionalidades específicas
- **Customização**: Temas e layouts personalizáveis

## Migração do Código Legado

O código antigo permanece funcional através do arquivo `src/gui.py` que redireciona para a nova implementação:

```python
# Código legado ainda funciona
from src.gui import SimulationGUI

# Internamente usa a nova implementação
app = SimulationGUI()  # -> MainWindow()
```

## Contribuindo

Para contribuir com melhorias na interface:

1. Siga o padrão de separação de responsabilidades
2. Use type hints e docstrings
3. Implemente callbacks para comunicação entre componentes
4. Mantenha compatibilidade com a API existente
5. Adicione testes para novos componentes

## Licença

Este código segue a mesma licença do projeto principal.
