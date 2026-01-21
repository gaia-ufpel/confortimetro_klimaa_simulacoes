# Confortímetro Klimaa - Simulações Personalizadas com EnergyPlus e Python

<div align="center">

![User Interface](/resources/imgs/UI.png)

Sistema de simulação e otimização de **conforto térmico** desenvolvido no âmbito do projeto Confortímetro Klimaa na **Universidade Federal de Pelotas (UFPel)**.

</div>

---

## 📌 Objetivo do Projeto

O **Confortímetro Klimaa** é uma ferramenta para **gestão e otimização do conforto térmico** em ambientes internos, utilizando simulações energéticas avançadas. O sistema:

- **Simula** o comportamento térmico de edificações utilizando o motor **EnergyPlus**
- **Calcula** índices de conforto térmico como **PMV (Predicted Mean Vote)** e modelo adaptativo
- **Otimiza** automaticamente parâmetros de climatização (ar-condicionado, ventilação, abertura de janelas)
- **Gera** resultados detalhados em formato Excel para análise posterior
- **Integra** com a API Python do EnergyPlus para controle em tempo de simulação

### Casos de Uso

- Análise de conforto térmico em edifícios acadêmicos (FAURB/UFPel)
- Otimização de sistemas de HVAC para eficiência energética
- Pesquisa em conforto adaptativo e PMV
- Simulações paramétricas de edificações

---

## 🛠️ Tecnologias Utilizadas

### Motor de Simulação
| Tecnologia | Descrição |
|------------|-----------|
| **EnergyPlus 9.4+** | Motor de simulação energética de edificações |
| **PyEnergyPlus API** | API Python nativa para integração com EnergyPlus |
| **Eppy >= 0.5.62** | Biblioteca Python para manipulação de arquivos IDF |

### Linguagem e Bibliotecas Principais
| Tecnologia | Versão | Descrição |
|------------|--------|-----------|
| **Python** | 3.8+ | Linguagem principal do projeto |
| **NumPy** | 1.24.3 | Computação numérica |
| **Pandas** | >= 1.5.0 | Manipulação e análise de dados |
| **pythermalcomfort** | >= 2.8.0 | Cálculos de conforto térmico |
| **ladybug-comfort** | - | Cálculos avançados de PMV |

### Interface Gráfica Desktop
| Tecnologia | Descrição |
|------------|-----------|
| **Tkinter** | Interface gráfica nativa Python |
| **Threading** | Execução não-bloqueante das simulações |

### Interface Web
| Tecnologia | Versão | Descrição |
|------------|--------|-----------|
| **Flask** | 2.3.3 | Framework web Python |
| **Flask-SocketIO** | 5.3.6 | WebSockets para tempo real |
| **Bootstrap 5** | - | Framework CSS responsivo |
| **JavaScript ES6** | - | Lógica de frontend |

### Gerenciamento de Projeto
| Tecnologia | Descrição |
|------------|-----------|
| **Poetry** | Gerenciamento de dependências (opcional) |
| **pip/venv** | Ambiente virtual Python |
| **Git** | Controle de versão |

---

## 🏗️ Arquitetura e Estrutura do Projeto

```
confortimetro_klimaa_simulacoes/
│
├── main.py                          # 🚀 Ponto de entrada principal (Desktop)
├── run_web.sh                       # 🌐 Script para interface web
├── install.sh                       # ⚙️ Script de instalação
│
├── src/                             # 📦 Código fonte principal
│   │
│   ├── simulation.py                # Motor de simulação EnergyPlus
│   │
│   ├── modules/                     # Módulos condicionadores
│   │   ├── conditioner.py           # Classe base do condicionador
│   │   ├── conditioner_complete.py  # Módulo completo (AC + ventilação + janela)
│   │   ├── conditioner_closed_window.py
│   │   ├── conditioner_fixed_ac_without_fan.py
│   │   └── conditioner_without_fan.py
│   │
│   ├── processors/                  # Processadores de arquivos
│   │   └── idf_processor.py         # Processamento de arquivos IDF
│   │
│   ├── utils/                       # Utilitários
│   │   ├── __init__.py              # Funções de extração de resultados
│   │   ├── simulation_config.py     # Configurações de simulação
│   │   └── module_type.py           # Enum de tipos de módulos
│   │
│   ├── gui/                         # 🖥️ Interface Desktop (Tkinter)
│   │   ├── main_window.py           # Janela principal (Controller)
│   │   └── components/              # Componentes modulares
│   │       ├── path_config_panel.py
│   │       ├── simulation_config_panel.py
│   │       ├── results_panel.py
│   │       └── control_panel.py
│   │
│   └── web/                         # 🌐 Interface Web (Flask)
│       ├── app.py                   # Aplicação Flask
│       ├── simulation_integration.py
│       ├── templates/               # Templates HTML
│       └── static/                  # CSS e JavaScript
│
├── resources/                       # 📁 Recursos e configurações
│   ├── config.json                  # Configuração padrão
│   ├── EnergyFiles/                 # Arquivos IDF de exemplo
│   └── WeatherFiles/                # Arquivos EPW climáticos
│
├── outputs/                         # 📊 Resultados das simulações
├── uploads/                         # 📤 Arquivos enviados via web
├── logs/                            # 📝 Logs de execução
├── documentation/                   # 📚 Documentação detalhada
│   ├── EXECUÇÃO.md
│   ├── MELHORIAS_INTERFACE.md
│   └── REFATORACAO_SIMULATION.md
│
└── backups/                         # Backups de arquivos
```

### Módulos de Condicionamento

O sistema oferece **4 tipos de módulos** para controle de conforto térmico:

| Módulo | Descrição |
|--------|-----------|
| `COMPLETE` | Controle completo: AC + ventilação + abertura de janelas |
| `CLOSED_WINDOW` | AC + ventilação, janelas sempre fechadas |
| `WITHOUT_FAN` | AC + janelas, sem ventilação forçada |
| `FIXED_AC_WITHOUT_FAN` | AC fixo, sem ventilação |

---

## 🚀 Como Executar

### Interface Web (Recomendado ⭐)

```bash
# Instalação e execução automática
./run_web.sh

# Acesse: http://localhost:5000
```

### Interface Desktop

```bash
# Nova interface modular (RECOMENDADO)
python main.py

# Com opções de linha de comando
python launcher.py --help
```

### Scripts Automatizados

**Windows:**
```cmd
SimulacoesPersonalizadas.bat
```

**Linux/MacOS:**
```bash
./SimulacoesPersonalizadas.sh
```

---

## 📋 Instalação

### Pré-requisitos

- **Python 3.8+**
- **EnergyPlus 9.4+** instalado no sistema
- **Tkinter** (geralmente incluído com Python)

### Instalação no Ubuntu/Debian

```bash
# Instalar tkinter se necessário
sudo apt-get install python3-tk

# Clonar repositório
git clone <url-do-repositorio>
cd confortimetro_klimaa_simulacoes

# Criar ambiente virtual e instalar dependências
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r src/web/requirements.txt
```

### Instalação com Script

```bash
./install.sh
```

### Instalação com Poetry (Opcional)

```bash
pip install poetry
poetry install
poetry run python main.py
```

---

## ⚙️ Configuração

O arquivo de configuração padrão está em `resources/config.json`:

```json
{
    "energy_path": "/usr/local/EnergyPlus-9-4-0",
    "epw_path": "./resources/WeatherFiles/BRA_RS_Camaqua.869890_INMET.epw",
    "output_path": "./outputs/resultado",
    "rooms": ["SALA_AULA", "ATELIE1", "ATELIE2"],
    "pmv_upperbound": 0.5,
    "pmv_lowerbound": -0.5,
    "temp_ac_min": 18.0,
    "temp_ac_max": 30.0,
    "module_type": "COMPLETE"
}
```

### Principais Parâmetros

| Parâmetro | Descrição |
|-----------|-----------|
| `energy_path` | Caminho da instalação do EnergyPlus |
| `epw_path` | Arquivo climático EPW |
| `rooms` | Lista de zonas térmicas a simular |
| `pmv_upperbound/lowerbound` | Limites de conforto PMV (-0.5 a +0.5) |
| `temp_ac_min/max` | Faixa de temperatura do ar-condicionado |
| `module_type` | Tipo de módulo condicionador |

---

## 📊 Funcionalidades

### Interface Desktop

- ✅ **Layout responsivo** e redimensionável
- ✅ **Barra de progresso** animada
- ✅ **Status em tempo real** das simulações
- ✅ **Auto-scroll** nos resultados
- ✅ **Salvar/carregar** configurações
- ✅ **Componentes modulares** e reutilizáveis

### Interface Web

- ✅ **Design responsivo** (Desktop, Tablet, Mobile)
- ✅ **Upload drag & drop** para arquivos IDF/EPW
- ✅ **WebSockets** para atualizações em tempo real
- ✅ **Validação automática** de configurações
- ✅ **Logs categorizados** (info, sucesso, warning, erro)
- ✅ **Auto-save** de configurações

### Motor de Simulação

- ✅ Integração nativa com **PyEnergyPlus API**
- ✅ Cálculo de **PMV** e **modelo adaptativo**
- ✅ Otimização automática de temperatura e velocidade do ar
- ✅ Controle de **abertura de janelas**
- ✅ Exportação de resultados em **Excel**
- ✅ Estatísticas de conforto por zona

---

## 🧪 Testes

```bash
# Testar estrutura dos componentes
python test_structure.py

# Testar funcionamento do main.py
python test_main.py

# Testar interface (sem dependências externas)
python test_gui.py

# Testar interface web
./run_web.sh test
```

---

## 📚 Documentação Adicional

- [**documentation/EXECUÇÃO.md**](documentation/EXECUÇÃO.md) - Guia completo de execução
- [**documentation/MELHORIAS_INTERFACE.md**](documentation/MELHORIAS_INTERFACE.md) - Detalhes da refatoração da interface
- [**documentation/REFATORACAO_SIMULATION.md**](documentation/REFATORACAO_SIMULATION.md) - Refatoração do motor de simulação
- [**src/gui/README.md**](src/gui/README.md) - Documentação da interface desktop
- [**src/web/README.md**](src/web/README.md) - Documentação da interface web

---

## 🔄 Fluxo de Simulação

```
┌─────────────────┐    ┌───────────────────┐    ┌─────────────────┐
│   Configuração  │───▶│   Processamento   │───▶│   EnergyPlus    │
│   (GUI/Web)     │    │   IDF (Eppy)      │    │   Simulação     │
└─────────────────┘    └───────────────────┘    └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌───────────────────┐    ┌─────────────────┐
│    Relatórios   │◀───│   Pós-Processamento│◀───│   Condicionador │
│    Excel        │    │   (Pandas)        │    │   (Callback)    │
└─────────────────┘    └───────────────────┘    └─────────────────┘
```

---

## 🤝 Contribuindo

1. **Use a nova interface** para novos recursos
2. **Mantenha compatibilidade** com código legado
3. **Siga os padrões** de separação de responsabilidades
4. **Adicione testes** para novos componentes
5. **Documente mudanças** significativas

---

## 📞 Suporte

Em caso de problemas:

1. Execute os testes de diagnóstico (`python test_structure.py`)
2. Verifique a [documentação de execução](documentation/EXECUÇÃO.md)
3. Tente a interface legada para comparação
4. Verifique os logs em `logs/`
5. Reporte issues com detalhes

---

## 📄 Licença

Este projeto está sob a licença da **Universidade Federal de Pelotas**.

---

<div align="center">

**Desenvolvido no âmbito do projeto Confortímetro Klimaa - UFPel**

*Grupo de Pesquisa GAIA - Faculdade de Arquitetura e Urbanismo*

</div>