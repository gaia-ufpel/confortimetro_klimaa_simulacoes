import sys
from pathlib import Path

# Permite rodar `pytest tests` da raiz sem exportar PYTHONPATH.
sys.path.append(str(Path(__file__).resolve().parents[1]))
