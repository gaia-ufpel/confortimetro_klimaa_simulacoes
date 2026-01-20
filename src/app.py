"""
Arquivo de compatibilidade - redireciona para o novo main.py

DEPRECATED: Use main.py na raiz do projeto
"""

import sys
import os
import warnings

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Função principal - redireciona para a nova interface."""
    warnings.warn(
        "src/app.py está deprecated. Use 'python main.py' na raiz do projeto.",
        DeprecationWarning,
        stacklevel=2
    )
    
    print("AVISO: src/app.py está deprecated.")
    print("Execute 'python main.py' na raiz do projeto.")
    print("Redirecionando para a nova interface...\n")
    
    try:
        from gui.main_window import MainWindow
        app = MainWindow()
        app.mainloop()
        
    except ImportError:
        print("Erro: Não foi possível importar a interface.")
        print("Execute 'python main.py' a partir do diretório raiz do projeto.")
        sys.exit(1)

if __name__ == "__main__":
    main()
