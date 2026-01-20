#!/usr/bin/env python3
"""
Teste de correção do erro NumPy/Numba
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_numpy_version():
    """Testar se o NumPy está na versão correta."""
    try:
        import numpy
        version = numpy.__version__
        print(f"✓ NumPy version: {version}")
        
        # Verificar se é 1.24 ou menor
        major, minor = map(int, version.split('.')[:2])
        if major == 1 and minor <= 24:
            print("✓ NumPy version is compatible with Numba")
            return True
        else:
            print("✗ NumPy version is too high for Numba")
            return False
    except Exception as e:
        print(f"✗ Erro ao importar NumPy: {e}")
        return False

def test_numba_import():
    """Testar se o Numba pode ser importado."""
    try:
        import numba
        print(f"✓ Numba version: {numba.__version__}")
        return True
    except Exception as e:
        print(f"✗ Erro ao importar Numba: {e}")
        return False

def test_pythermalcomfort_import():
    """Testar se pythermalcomfort pode ser importado."""
    try:
        import pythermalcomfort
        print("✓ pythermalcomfort importado com sucesso")
        return True
    except Exception as e:
        print(f"✗ Erro ao importar pythermalcomfort: {e}")
        return False

def test_simulation_import():
    """Testar se a simulação pode ser importada."""
    try:
        from src.simulation import Simulation
        print("✓ Simulation importado com sucesso")
        return True
    except Exception as e:
        print(f"✗ Erro ao importar Simulation: {e}")
        return False

def test_modules_import():
    """Testar se os módulos podem ser importados."""
    try:
        from src.modules import MODULES_MAPPER
        print(f"✓ MODULES_MAPPER importado com sucesso - {len(MODULES_MAPPER)} módulos")
        return True
    except Exception as e:
        print(f"✗ Erro ao importar MODULES_MAPPER: {e}")
        return False

def main():
    """Executar todos os testes."""
    print("=== Teste de Correção do Erro NumPy/Numba ===\n")
    
    tests = [
        test_numpy_version,
        test_numba_import,
        test_pythermalcomfort_import,
        test_simulation_import,
        test_modules_import
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()  # Linha em branco
    
    print(f"=== Resultado: {passed}/{total} testes passaram ===")
    
    if passed == total:
        print("✓ Correção do erro NumPy/Numba bem-sucedida!")
        print("✓ A aplicação agora deve funcionar corretamente")
        return True
    else:
        print("✗ Alguns testes falharam. Verifique os erros acima.")
        return False

if __name__ == "__main__":
    main()
