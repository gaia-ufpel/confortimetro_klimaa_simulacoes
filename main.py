"""
Ambiens - Simulações de Conforto Térmico com EnergyPlus e Python

Ponto de entrada principal da aplicação.
"""

import json
import multiprocessing
import os
import sys

from confortimetro.gui.main_window import MainWindow
from confortimetro.paths import app_data_path


def resolve_config_path() -> str:
    """
    Caminho do config.json a ser usado pela interface.

    Rodando do repositório: `examples/config.json`, como sempre.
    Rodando pelo executável (PyInstaller): uma cópia gravável em
    `%LOCALAPPDATA%\\ConfortimetroKlimaa`, semeada na primeira execução com o
    config.json embutido no pacote (o diretório do executável pode ser
    somente leitura para o usuário).
    """
    if not getattr(sys, "frozen", False):
        return os.path.join("examples", "config.json")

    user_config = os.path.join(app_data_path(), "config.json")
    if not os.path.exists(user_config):
        os.makedirs(os.path.dirname(user_config), exist_ok=True)
        bundle_path = getattr(sys, "_MEIPASS")
        with open(os.path.join(bundle_path, "examples", "config.json")) as reader:
            data = json.load(reader)

        # Os caminhos do config versionado são relativos ao repositório e de
        # Linux; no executável apontam para os exemplos embutidos.
        data["_idf_path"] = os.path.join(bundle_path, *data["_idf_path"].split("/")[1:])
        data["epw_path"] = os.path.join(bundle_path, *data["epw_path"].split("/")[1:])
        data["input_path"] = os.path.dirname(data["_idf_path"])
        # Saída e EnergyPlus vazios: caem nos padrões da plataforma
        # (paths.new_run_path e find_energy_path) ao carregar a configuração.
        data["runs_root_path"] = ""
        data["output_path"] = ""
        data["expanded_idf_path"] = ""
        data["energy_path"] = ""

        with open(user_config, "w") as writer:
            json.dump(data, writer, indent=4)
    return user_config


def main():
    """
    Função principal da aplicação.

    Cria e executa a interface gráfica principal do Ambiens.
    """
    # No executável do Windows, o ProcessPoolExecutor de recompute_runs relança
    # este mesmo .exe para cada worker (spawn). Sem freeze_support o filho volta
    # a abrir a interface em vez de rodar a tarefa — janelas se multiplicando e
    # nenhuma estatística regerada. Tem que ser a primeira coisa do main().
    multiprocessing.freeze_support()

    try:
        app = MainWindow(config_path=resolve_config_path())
        app.mainloop()

    except KeyboardInterrupt:
        print("\nAplicação interrompida pelo usuário.")
    except Exception as e:
        print(f"Erro ao executar a aplicação: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
