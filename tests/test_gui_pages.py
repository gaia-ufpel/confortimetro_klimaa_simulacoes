"""Navegação por páginas da janela principal e duplicação de execução."""

import datetime
import os

import pytest

tk = pytest.importorskip("tkinter")

from confortimetro.config import SimulationConfig


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFORTIMETRO_DATA_DIR", str(tmp_path / "dados"))
    from confortimetro.gui.main_window import MainWindow

    # Configuração já existente: sem ela a janela cai no `SimulationConfig()`
    # sem argumentos e quebra antes de montar as páginas.
    idf_base = tmp_path / "base.idf"
    idf_base.write_text("Zone,\n  SALA1,\n")
    config_path = tmp_path / "config.json"
    SimulationConfig(met_as_watts=125.496, _idf_path=str(idf_base), _met=1.2,
                     epw_path=str(tmp_path / "clima.epw"), rooms=["SALA1"],
                     energy_path=str(tmp_path / "EnergyPlus"),
                     output_path=str(tmp_path / "saidas" / "run_000")).to_json(
                         str(config_path))

    try:
        window = MainWindow(config_path=str(config_path))
    except tk.TclError:
        pytest.skip("sem display para o Tk")
    yield window
    window.destroy()


def _settle(window):
    """Espera a transição de página terminar antes de olhar o que está no ar."""
    for _ in range(200):
        window.update()
        if window._sliding is None:
            return
    raise AssertionError("a transição de página não terminou")


def test_paginas_trocam(window):
    assert window._current_page == "runs"
    window.show_page("editor")
    _settle(window)
    assert window._pages["editor"].winfo_ismapped()
    assert not window._pages["runs"].winfo_ismapped()


def test_duplicar_reaproveita_parametros_com_saida_nova(window, tmp_path):
    idf = tmp_path / "modelo.idf"
    idf.write_text("Zone,\n  SALA1,\n")
    run_path = tmp_path / "execucao_antiga"
    run_path.mkdir()
    config = SimulationConfig(met_as_watts=125.496, _idf_path=str(run_path / "modelo.idf"),
                             _met=1.2, epw_path="clima.epw", output_path=str(run_path),
                             source_idf_path=str(idf), pmv_upperbound=0.9)
    config.to_json(str(run_path / "configs.json"))

    window.on_duplicate_run({'run': 'execucao_antiga', 'path': str(run_path),
                          'status': 'pronta', 'rooms_disponiveis': [],
                          'modificado': datetime.datetime.now(), 'config': {}})

    assert window._current_page == "editor"
    assert window.configs.pmv_upperbound == 0.9
    # O modelo escolhido pelo usuário, não a cópia dentro da execução…
    assert window.configs.idf_path == str(idf)
    # …e nunca a mesma pasta de saída.
    assert os.path.abspath(window.configs.output_path) != os.path.abspath(run_path)


def _toast_text(frame):
    """Texto do toast (o rótulo é o segundo filho, depois da barra de cor)."""
    return " ".join(child.cget("text") for child in frame.winfo_children()
                    if "text" in child.keys())


def test_comparar_abre_pagina_propria(window, tmp_path):
    runs = []
    for name in ("run_a", "run_b"):
        run_path = tmp_path / name
        run_path.mkdir()
        (run_path / "configs.json").write_text("{}")
        runs.append({'run': name, 'path': str(run_path), 'status': 'sem estatísticas',
                     'rooms_disponiveis': [], 'config': {},
                     'modificado': datetime.datetime.now()})

    window.on_compare_runs(runs, str(tmp_path))
    _settle(window)

    assert window._current_page == "compare"
    # Sem estatísticas não há o que comparar, mas o usuário precisa saber disso
    # na própria página, não numa tela em branco.
    assert any("estatísticas" in _toast_text(frame)
               for frame in getattr(window, "_toasts", []))
