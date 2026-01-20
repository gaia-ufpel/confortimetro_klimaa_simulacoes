# Confortímetro Klimaa - Simulações Personalizadas com EnergyPlus e Python

Aplicação para gestão do conforto térmico do usuário e otimização energética por meio de simulações no EnergyPlus utilizando Python no âmbito do projeto do confortímetro Klimaa na Universidade Federal de Pelotas.

![User Interface](/resources/imgs/UI.png)

## 🚀 Como Executar

### Interface Web (NOVO! ⭐)
```bash
# Executar interface web moderna
./run_web.sh

# Acesse: http://localhost:5000
```

### Interface Desktop
```bash
# Nova interface modular (RECOMENDADO)
python main.py

# Interface com opções
python launcher.py --help
```

### Execução Automatizada

**Windows:**
```cmd
SimulacoesPersonalizas.bat
```

**Linux/MacOS:**
```bash
./SimulacoesPersonalizadas.sh
```

### Instalação Manual

1. **Instale o Poetry:**
   ```bash
   pip install poetry
   ```

2. **Instale as dependências:**
   ```bash
   poetry install
   ```

3. **Execute a aplicação:**
   ```bash
   # Nova interface
   poetry run python main.py
   
   # Interface legada (compatibilidade)
   poetry run python launcher.py --legacy
   ```

## 📋 Pré-requisitos

- Python 3.8+
- EnergyPlus (para simulações)
- Tkinter (geralmente incluído com Python)

### Instalação no Ubuntu/Debian
```bash
sudo apt-get install python3-tk
```

## 🏗️ Arquitetura da Interface

A aplicação foi refatorada com uma **arquitetura modular** seguindo princípios de separação de responsabilidades:

```
src/gui/
├── main_window.py              # Janela principal (Controller)
└── components/
    ├── path_config_panel.py    # Configuração de caminhos
    ├── simulation_config_panel.py  # Configuração de simulação  
    ├── results_panel.py        # Exibição de resultados
    └── control_panel.py        # Controles de execução
```

### Funcionalidades da Nova Interface:
- ✅ **Layout responsivo** e redimensionável
- ✅ **Diferentes tipos de mensagem** (Info, Warning, Error, Success)
- ✅ **Barra de progresso** animada
- ✅ **Status em tempo real** das simulações
- ✅ **Auto-scroll** nos resultados
- ✅ **Salvar/carregar** configurações
- ✅ **Componentes modulares** e reutilizáveis

## 🔧 Opções de Interface

### Nova Interface (Recomendada)
```python
from src.gui.main_window import MainWindow
app = MainWindow()
app.mainloop()
```

### Interface Legada (Compatibilidade)
```python
from src.gui import SimulationGUI
app = SimulationGUI()
app.mainloop()
```

## 🛠️ Tecnologias Utilizadas

- **EnergyPlus** - Motor de simulação energética
- **Python 3.8+** - Linguagem principal
- **Pandas** - Manipulação de dados
- **Eppy** - Interface Python para EnergyPlus
- **Tkinter** - Interface gráfica
- **Threading** - Simulações não-bloqueantes
- **Poetry** - Gerenciamento de dependências

## 📚 Documentação

- [**EXECUÇÃO.md**](EXECUÇÃO.md) - Guia completo de execução
- [**MELHORIAS_GUI.md**](MELHORIAS_GUI.md) - Detalhes da refatoração
- [**src/gui/README.md**](src/gui/README.md) - Documentação da interface

## 🧪 Testes

```bash
# Testar estrutura dos componentes
python test_structure.py

# Testar funcionamento do main.py
python test_main.py

# Testar interface (sem dependências externas)
python test_gui.py
```

## 🔄 Migração de Código Antigo

A aplicação mantém **total compatibilidade** com código existente:

```python
# Código antigo ainda funciona
from src.gui import SimulationGUI
app = SimulationGUI()  # Usa internamente a nova interface
```

## 📁 Estrutura do Projeto

```
confortimetro_klimaa_simulacoes/
├── main.py                     # Ponto de entrada principal
├── launcher.py                 # Launcher com opções
├── run_web.sh                  # Script para interface web
├── src/
│   ├── gui/                    # Interface gráfica modular (desktop)
│   ├── web/                    # Interface web moderna (Flask)
│   ├── modules/                # Módulos de simulação
│   ├── utils/                  # Utilitários
│   └── simulation.py           # Motor de simulação
├── resources/                  # Recursos e configurações
├── outputs/                    # Resultados das simulações
├── uploads/                    # Arquivos enviados via web
└── docs/                       # Documentação
```

## 🌐 Interface Web

A nova interface web oferece:

- **Design Moderno**: Interface responsiva com Bootstrap 5
- **Tempo Real**: Atualizações via WebSockets
- **Upload de Arquivos**: Drag & drop para IDF/EPW
- **Validação Automática**: Verificação de configurações
- **Monitoramento**: Logs e status em tempo real

Veja [src/web/README.md](src/web/README.md) para documentação completa.

## 🤝 Contribuindo

1. **Use a nova interface** para novos recursos
2. **Mantenha compatibilidade** com código legado
3. **Siga os padrões** de separação de responsabilidades
4. **Adicione testes** para novos componentes
5. **Documente mudanças** significativas

## 📞 Suporte

Em caso de problemas:

1. Execute os testes de diagnóstico
2. Verifique a [documentação de execução](EXECUÇÃO.md)
3. Tente a interface legada para comparação
4. Reporte issues com detalhes

## 📄 Licença

Este projeto está sob a licença da Universidade Federal de Pelotas.

---

**Desenvolvido no âmbito do projeto Confortímetro Klimaa - UFPel**