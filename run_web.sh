#!/bin/bash

# Confortímetro Klimaa - Web Interface Setup and Run Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
WEB_DIR="$SCRIPT_DIR/src/web"
PROJECT_ROOT="$SCRIPT_DIR"

print_status "Confortímetro Klimaa - Interface Web"
print_status "===================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 não encontrado. Por favor, instale o Python 3.8 ou superior."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
print_status "Usando Python $PYTHON_VERSION"

# Check if virtual environment exists
VENV_DIR="$PROJECT_ROOT/venv_web"

if [ ! -d "$VENV_DIR" ]; then
    print_status "Criando ambiente virtual..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
print_status "Ativando ambiente virtual..."
source "$VENV_DIR/bin/activate"

# Install/upgrade pip
print_status "Atualizando pip..."
python -m pip install --upgrade pip

# Install web requirements
print_status "Instalando dependências da interface web..."
pip install -r "$WEB_DIR/requirements.txt"

# Install main project requirements if they exist
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    print_status "Instalando dependências do projeto..."
    pip install -r "$PROJECT_ROOT/requirements.txt"
fi

# Create necessary directories
print_status "Criando diretórios necessários..."
mkdir -p "$PROJECT_ROOT/uploads"
mkdir -p "$PROJECT_ROOT/logs"

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

print_status "Configuração concluída!"
echo ""

# Function to start the web server
start_web_server() {
    print_status "Iniciando servidor web..."
    print_status "Acesse: http://localhost:5000"
    print_status "Pressione Ctrl+C para parar o servidor"
    echo ""
    
    cd "$WEB_DIR"
    python app.py
}

# Function to show usage
show_usage() {
    echo "Uso: $0 [OPÇÃO]"
    echo ""
    echo "Opções:"
    echo "  start, run       Inicia o servidor web (padrão)"
    echo "  install          Apenas instala as dependências"
    echo "  clean            Remove o ambiente virtual"
    echo "  test             Executa os testes"
    echo "  help             Mostra esta ajuda"
    echo ""
}

# Parse command line arguments
case "${1:-start}" in
    "start"|"run")
        start_web_server
        ;;
    "install")
        print_status "Instalação concluída. Execute '$0 start' para iniciar o servidor."
        ;;
    "clean")
        print_warning "Removendo ambiente virtual..."
        if [ -d "$VENV_DIR" ]; then
            rm -rf "$VENV_DIR"
            print_status "Ambiente virtual removido."
        else
            print_warning "Ambiente virtual não encontrado."
        fi
        ;;
    "test")
        print_status "Executando testes..."
        cd "$PROJECT_ROOT"
        python -m pytest src/web/tests/ -v
        ;;
    "help"|"--help"|"-h")
        show_usage
        ;;
    *)
        print_error "Opção inválida: $1"
        show_usage
        exit 1
        ;;
esac
