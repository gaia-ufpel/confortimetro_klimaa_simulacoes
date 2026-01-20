# Como Executar o Confortímetro Klimaa

## Opções de Execução

### 1. Execução Padrão (Nova Interface)
```bash
python main.py
```
- Usa a nova interface modular e refatorada
- Interface mais moderna e maintível
- **RECOMENDADO** para uso geral

### 2. Execução com Launcher
```bash
# Nova interface (padrão)
python launcher.py

# Interface legada (compatibilidade)
python launcher.py --legacy

# Especificar arquivo de configuração
python launcher.py --config path/to/config.json

# Ver todas as opções
python launcher.py --help
```

### 3. Execução Programática

#### Nova Interface
```python
from src.gui.main_window import MainWindow

app = MainWindow()
app.mainloop()
```

#### Interface Legada (Compatibilidade)
```python
from src.gui import SimulationGUI

app = SimulationGUI()
app.mainloop()
```

## Diferenças Entre as Interfaces

### 🆕 Nova Interface (MainWindow)
**Vantagens:**
- ✅ Código modular e organizadoRede
- ✅ Componentes reutilizáveis
- ✅ Melhor separação de responsabilidades
- ✅ Interface mais responsiva
- ✅ Melhor tratamento de erros
- ✅ Facilidade de manutenção
- ✅ Padrões de design modernos

**Funcionalidades:**
- Layout responsivo e redimensionável
- Diferentes tipos de mensagem (Info, Warning, Error, Success)
- Barra de progresso animada
- Status em tempo real
- Auto-scroll nos resultados
- Botões de salvar/carregar configuração

### 🔄 Interface Legada (SimulationGUI)
**Vantagens:**
- ✅ Compatibilidade total com código existente
- ✅ Funcionalidade testada e estável

**Quando usar:**
- Quando precisar de compatibilidade absoluta
- Para verificar comportamento do código antigo
- Durante transição gradual

## Configuração

### Arquivo de Configuração Padrão
```
resources/config.json
```

### Especificar Configuração Personalizada
```bash
python launcher.py --config /caminho/para/minha/config.json
```

## Requisitos

### Dependências Python
- Python 3.8+
- tkinter (geralmente incluído)
- Dependências do projeto (ver requirements.txt)

### Dependências Externas
- EnergyPlus (para simulações)
- Arquivos IDF e EPW apropriados

## Resolução de Problemas

### Erro de Import
```bash
# Se houver erro "module not found"
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
python main.py
```

### Erro NumPy/Numba
```bash
# Se houver conflito de versão NumPy
pip install "numpy<1.25"
```

### Interface Não Aparece
```bash
# Verificar se tkinter está instalado
python -c "import tkinter; print('tkinter OK')"

# Se não estiver (Ubuntu/Debian)
sudo apt-get install python3-tk
```

### Problemas de Configuração
```bash
# Executar com interface legada para comparar
python launcher.py --legacy

# Verificar estrutura dos arquivos
python test_structure.py
```

## Exemplos de Uso

### Uso Básico
```bash
# Executar com interface nova
python main.py
```

### Desenvolvimento
```bash
# Testar estrutura
python test_structure.py

# Testar main
python test_main.py

# Usar interface legada para comparação
python launcher.py --legacy
```

### Scripts Automatizados
```python
#!/usr/bin/env python3
import sys
from src.gui.main_window import MainWindow

def run_with_config(config_path):
    """Executar com configuração específica."""
    app = MainWindow(config_path)
    app.mainloop()

if __name__ == "__main__":
    config = sys.argv[1] if len(sys.argv) > 1 else "resources/config.json"
    run_with_config(config)
```

## Logs e Debug

### Habilitar Logs Detalhados
```python
import logging
logging.basicConfig(level=logging.DEBUG)

from src.gui.main_window import MainWindow
app = MainWindow()
app.mainloop()
```

### Verificar Funcionalidade
```bash
# Testar imports
python -c "from src.gui.main_window import MainWindow; print('✅ Import OK')"

# Testar criação da interface
python -c "from src.gui.main_window import MainWindow; app = MainWindow(); app.destroy(); print('✅ Interface OK')"
```

## Migração do Código Antigo

Se você tem scripts que usam a interface antiga:

### Antes (Antigo)
```python
from src.gui import SimulationGUI
app = SimulationGUI()
app.mainloop()
```

### Depois (Novo)
```python
from src.gui.main_window import MainWindow
app = MainWindow()
app.mainloop()
```

### Compatibilidade (Transição)
```python
# Ainda funciona - redireciona para nova interface
from src.gui import SimulationGUI
app = SimulationGUI()  # Internamente usa MainWindow
app.mainloop()
```

## Performance

### Nova Interface vs Legada
- **Inicialização**: Nova interface pode ser ligeiramente mais lenta na primeira execução
- **Uso de Memória**: Similar entre ambas
- **Responsividade**: Nova interface é mais responsiva durante simulações
- **Stability**: Ambas são estáveis, nova tem melhor tratamento de erros

## Contribuindo

Para desenvolvedores que querem contribuir:

1. **Use sempre a nova interface** para novos recursos
2. **Mantenha compatibilidade** com a interface legada
3. **Teste ambas as interfaces** antes de fazer commit
4. **Documente mudanças** que afetem a interface

## Suporte

Se encontrar problemas:

1. Execute `python test_structure.py` para verificar a instalação
2. Execute `python test_main.py` para verificar o main.py
3. Tente a interface legada com `python launcher.py --legacy`
4. Verifique os logs de erro na interface
5. Reporte issues com informações detalhadas
