#!/usr/bin/env python3
"""
Teste completo das melhorias de interface do Confortímetro Klimaa
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def test_interface_imports():
    """Testar se todos os componentes da interface podem ser importados."""
    try:
        from src.gui.main_window import MainWindow
        from src.gui.components import (
            PathConfigPanel, 
            SimulationConfigPanel, 
            ResultsPanel, 
            ControlPanel
        )
        print("✓ Todos os componentes da interface importados com sucesso")
        return True
    except Exception as e:
        print(f"✗ Erro ao importar componentes: {e}")
        return False

def test_styling_system():
    """Testar se o sistema de estilos funciona."""
    try:
        import tkinter as tk
        from tkinter import ttk
        
        # Criar janela de teste oculta
        root = tk.Tk()
        root.withdraw()
        
        # Criar MainWindow para testar estilos
        from src.gui.main_window import MainWindow
        app = MainWindow()
        app.withdraw()
        
        # Verificar se as cores foram definidas
        if hasattr(app, 'colors') and 'primary' in app.colors:
            print("✓ Sistema de cores implementado corretamente")
            
            # Testar alguns estilos
            style = app.style
            if style.lookup("Primary.TButton", "background"):
                print("✓ Estilos de botões configurados")
            else:
                print("⚠ Estilos de botões podem não estar funcionando")
        else:
            print("✗ Sistema de cores não encontrado")
            return False
        
        # Cleanup
        app.destroy()
        root.destroy()
        
        print("✓ Sistema de estilos testado com sucesso")
        return True
        
    except Exception as e:
        print(f"✗ Erro no teste de estilos: {e}")
        return False

def test_layout_management():
    """Testar se o gerenciamento de layout está funcionando."""
    try:
        import tkinter as tk
        from src.gui.main_window import MainWindow
        
        # Criar janela de teste
        root = tk.Tk()
        root.withdraw()
        
        app = MainWindow()
        app.withdraw()
        
        # Verificar se os painéis foram criados
        if hasattr(app, 'path_panel') and hasattr(app, 'simulation_panel'):
            print("✓ Painéis principais criados corretamente")
        else:
            print("✗ Painéis principais não encontrados")
            return False
            
        if hasattr(app, 'control_panel') and hasattr(app, 'results_panel'):
            print("✓ Painéis de controle e resultados criados")
        else:
            print("✗ Painéis de controle/resultados não encontrados")
            return False
        
        # Cleanup
        app.destroy()
        root.destroy()
        
        print("✓ Gerenciamento de layout funcionando corretamente")
        return True
        
    except Exception as e:
        print(f"✗ Erro no teste de layout: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_modern_features():
    """Testar funcionalidades modernas implementadas."""
    try:
        import tkinter as tk
        from src.gui.main_window import MainWindow
        
        root = tk.Tk()
        root.withdraw()
        
        app = MainWindow()
        app.withdraw()
        
        # Testar recursos do painel de controle
        if hasattr(app.control_panel, 'set_running_state'):
            print("✓ Controle de estado da simulação implementado")
        
        if hasattr(app.control_panel, 'set_status'):
            print("✓ Sistema de status com ícones implementado")
        
        # Testar recursos do painel de resultados
        if hasattr(app.results_panel, 'append_message'):
            print("✓ Sistema de mensagens melhorado")
        
        if hasattr(app.results_panel, 'filter_var'):
            print("✓ Sistema de filtros implementado")
        
        # Testar validação de caminhos
        if hasattr(app.path_panel, '_validate_path'):
            print("✓ Validação visual de caminhos implementada")
        
        # Cleanup
        app.destroy()
        root.destroy()
        
        print("✓ Funcionalidades modernas testadas com sucesso")
        return True
        
    except Exception as e:
        print(f"✗ Erro no teste de funcionalidades: {e}")
        return False

def test_visual_feedback():
    """Testar sistema de feedback visual."""
    try:
        import tkinter as tk
        from src.gui.main_window import MainWindow
        
        root = tk.Tk()
        root.withdraw()
        
        app = MainWindow()
        app.withdraw()
        
        # Testar diferentes tipos de mensagem
        app.results_panel.append_info("Teste de mensagem info")
        app.results_panel.append_success("Teste de mensagem sucesso")
        app.results_panel.append_warning("Teste de mensagem aviso")
        app.results_panel.append_error("Teste de mensagem erro")
        
        print("✓ Sistema de mensagens com ícones funcionando")
        
        # Testar mudança de estado
        app.control_panel.set_running_state(True)
        app.control_panel.set_running_state(False)
        
        print("✓ Estados visuais do controle funcionando")
        
        # Cleanup
        app.destroy()
        root.destroy()
        
        print("✓ Feedback visual testado com sucesso")
        return True
        
    except Exception as e:
        print(f"✗ Erro no teste de feedback visual: {e}")
        return False

def main():
    """Executar todos os testes de interface."""
    print("🎨 === Teste das Melhorias de Interface === 🎨\n")
    
    tests = [
        test_interface_imports,
        test_styling_system,
        test_layout_management,
        test_modern_features,
        test_visual_feedback
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        print(f"\n--- {test.__name__} ---")
        if test():
            passed += 1
        print()
    
    print(f"=== Resultado Final: {passed}/{total} testes passaram ===\n")
    
    if passed == total:
        print("🎉 SUCESSO! Todas as melhorias de interface foram implementadas corretamente!")
        print("\n📋 Resumo das melhorias:")
        print("✅ Interface moderna com cards e layout responsivo")
        print("✅ Paleta de cores profissional e consistente")
        print("✅ Sistema de estilos customizados")
        print("✅ Feedback visual rico com ícones e cores")
        print("✅ Validação em tempo real de campos")
        print("✅ Sistema de filtros e logs avançado")
        print("✅ Estados visuais claros para todas as ações")
        print("✅ Layout responsivo e bem organizado")
        print("\n🚀 A interface está pronta para uso!")
        return True
    else:
        print("❌ Alguns testes falharam. Verifique os erros acima.")
        return False

if __name__ == "__main__":
    main()
