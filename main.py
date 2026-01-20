"""
Confortímetro Klimaa - Simulações Personalizadas com EnergyPlus e Python

Ponto de entrada principal da aplicação.
"""

from src.gui.main_window import MainWindow

def main():
    """
    Função principal da aplicação.
    
    Cria e executa a interface gráfica principal do Confortímetro Klimaa.
    """
    try:
        # Criar e executar a aplicação
        app = MainWindow()
        app.mainloop()
        
    except KeyboardInterrupt:
        print("\nAplicação interrompida pelo usuário.")
    except Exception as e:
        print(f"Erro ao executar a aplicação: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()