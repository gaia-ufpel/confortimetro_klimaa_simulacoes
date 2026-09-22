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
    """Deixa o Tk aplicar a troca antes de olhar o que está no ar."""
    window.update()


def test_paginas_trocam(window):
    assert window._current_page == "runs"
    window.show_page("editor")
    _settle(window)
    assert window._pages["editor"].winfo_ismapped()
    assert not window._pages["runs"].winfo_ismapped()


def test_editor_log_sheet_visivel_ao_abrir(window):
    """Garante que o log de execução não seja colapsado a 1x1 em telas 1366x768."""
    window.geometry("1366x768")
    window.show_page("editor")
    _settle(window)
    assert window.log_sheet.winfo_ismapped()
    assert not window.log_sheet._holder.winfo_ismapped()

    window.log_sheet.set_open(True)
    _settle(window)
    assert window.log_sheet._holder.winfo_ismapped()
    assert window.results_panel.winfo_height() >= 100
    assert window.results_panel.results_text.winfo_height() >= 50


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
    # …e nenhuma pasta de saída herdada: ela nasce da raiz quando a simulação
    # começa, então nunca escreve por cima da execução duplicada.
    assert window.configs.output_path is None


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


def test_simulation_error_handling(window):
    from queue import Queue
    window.simulation_queue = Queue()

    window._handle_simulation_message("Erro no pós-processamento: falha na extração")
    assert window._simulation_error == "Erro no pós-processamento: falha na extração"
    assert "falha na extração" in window.results_panel.results_text.get("1.0", "end")
    assert window.control_panel.status_pill._text == "Erro no pós-processamento: falha na extração"
    assert window.control_panel.status_pill._state == "error"

    window.simulation_thread = None
    window._check_simulation_thread()
    assert window.control_panel.status_pill._text == "Simulação falhou"
    assert window.control_panel.status_pill._state == "error"
    assert "Simulação finalizada com erros" in window.results_panel.results_text.get("1.0", "end")


def test_simulation_success_handling(window):
    from queue import Queue
    window.simulation_queue = Queue()
    window._simulation_error = None

    window._handle_simulation_message("Executando etapa final")
    assert window._simulation_error is None

    window.simulation_thread = None
    window._check_simulation_thread()
    assert window.control_panel.status_pill._text == "Simulação concluída"
    assert window.control_panel.status_pill._state == "success"
    assert "Simulação concluída!" in window.results_panel.results_text.get("1.0", "end")


def test_simulation_interrupted_handling(window):
    from queue import Queue
    from unittest.mock import MagicMock
    window.simulation_queue = Queue()
    window._simulation_error = None
    window.simulation = MagicMock()
    window.simulation.stop_requested = True

    window.simulation_thread = None
    window._check_simulation_thread()
    assert window.control_panel.status_pill._text == "Simulação interrompida"
    assert window.control_panel.status_pill._state == "warning"
    assert "Simulação interrompida." in window.results_panel.results_text.get("1.0", "end")


def test_recompute_selected_validacoes_e_mensagens(window, monkeypatch):
    panel = window.simulations_panel

    # Caso 1: Nenhuma execução selecionada
    monkeypatch.setattr(panel, "_selected_runs", lambda: [])
    panel.recompute_selected()
    toasts = [_toast_text(f) for f in getattr(window, "_toasts", [])]
    assert any("Escolha uma execução na lista" in t for t in toasts)

    # Limpa toasts
    for f in list(getattr(window, "_toasts", [])):
        f.destroy()
    window._toasts = []

    # Caso 2: Execução pronta
    monkeypatch.setattr(panel, "_selected_runs", lambda: [{'path': '/dummy', 'status': 'pronta'}])
    panel.recompute_selected()
    toasts = [_toast_text(f) for f in getattr(window, "_toasts", [])]
    assert any("As execuções escolhidas já têm estatísticas atualizadas." in t for t in toasts)

    # Limpa toasts
    for f in list(getattr(window, "_toasts", [])):
        f.destroy()
    window._toasts = []

    # Caso 3: Execução sem planilhas é aceita e dispara recompute_runs
    disparado = []
    monkeypatch.setattr("confortimetro.gui.components.simulations_panel.recompute_runs",
                        lambda paths: disparado.extend(paths) or {paths[0]: None})
    monkeypatch.setattr(panel, "_selected_runs", lambda: [{'path': '/run/sem_plan', 'status': 'sem planilhas'}])

    class MockThread:
        def __init__(self, target, daemon=None):
            self.target = target
        def start(self):
            self.target()

    monkeypatch.setattr("threading.Thread", MockThread)
    panel.recompute_selected()
    window.update()
    assert disparado == ['/run/sem_plan']


def test_recompute_done_toasts(window):
    panel = window.simulations_panel

    # 1 sucesso
    panel._recompute_done({"/p/run1": None})
    toasts = [_toast_text(f) for f in getattr(window, "_toasts", [])]
    assert any("1 execução regerada." in t for t in toasts)
    window._toasts.clear()

    # 2 sucessos
    panel._recompute_done({"/p/run1": None, "/p/run2": None})
    toasts = [_toast_text(f) for f in getattr(window, "_toasts", [])]
    assert any("2 execuções regeradas." in t for t in toasts)
    window._toasts.clear()

    # 1 falha
    panel._recompute_done({"/p/run1": "sem planilhas por zona nem arquivo eplusout.eso"})
    toasts = [_toast_text(f) for f in getattr(window, "_toasts", [])]
    assert any("1 execução falhou ao regerar" in t for t in toasts)
    window._toasts.clear()

    # 2 falhas
    panel._recompute_done({"/p/run1": "erro 1", "/p/run2": "erro 2"})
    toasts = [_toast_text(f) for f in getattr(window, "_toasts", [])]
    assert any("2 execuções falharam ao regerar" in t for t in toasts)
    window._toasts.clear()

    # Misto (1 sucesso, 1 falha)
    panel._recompute_done({"/p/run1": None, "/p/run2": "erro 2"})
    toasts = [_toast_text(f) for f in getattr(window, "_toasts", [])]
    assert any("1 execução regerada, mas 1 falhou" in t for t in toasts)
    window._toasts.clear()


def test_detalhes_abrem_no_resumo_e_serie_so_carrega_na_aba(window, tmp_path, monkeypatch):
    from confortimetro.gui.components import timeseries_panel

    carregadas = []
    monkeypatch.setattr(timeseries_panel.TimeSeriesPanel, "load",
                        lambda self, room: carregadas.append(room))
    run_path = tmp_path / "run_a"
    run_path.mkdir()
    run = {'run': 'run_a', 'path': str(run_path), 'status': 'pronta',
           'rooms_disponiveis': ['SALA1'], 'config': {},
           'modificado': datetime.datetime.now()}

    window.on_open_run_details(run)
    _settle(window)

    # Abrir os detalhes não lê a planilha: o Resumo continua instantâneo.
    assert window.detail_tabs.index("current") == 0
    assert carregadas == []

    window.detail_tabs.select(1)
    _settle(window)
    assert carregadas == ['SALA1']


