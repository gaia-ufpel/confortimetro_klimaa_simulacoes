"""Comportamentos da aba Série temporal que dependem do Tk e do matplotlib."""

import matplotlib.dates as mdates
import numpy
import pandas
import pytest
from matplotlib.backend_bases import MouseEvent

tk = pytest.importorskip("tkinter")

from confortimetro.results.series import COLUMNS


def _serie(n=2000, conforto=True):
    df = pandas.DataFrame({alias: numpy.zeros(n) for alias in COLUMNS})
    df['data'] = pandas.date_range('2015-01-01', periods=n, freq='10min')
    df['temp_operativa'] = numpy.linspace(18, 28, n)
    df['em_conforto'] = 1.0
    df.loc[min(1500, n - 1), 'em_conforto'] = 0.0
    return df if conforto else df.drop(columns='em_conforto')


@pytest.fixture
def panel():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("sem display para o Tk")
    from confortimetro.gui.components import TimeSeriesPanel
    from confortimetro.gui.theme import apply_theme

    root.geometry("1200x800")
    apply_theme(root)
    panel = TimeSeriesPanel(root)
    panel.pack(fill="both", expand=True)
    root.update()
    yield panel
    root.destroy()


def _show(panel, series):
    panel._series = series
    panel._show_plot()
    panel.update()
    panel.show_all()
    panel.canvas.draw()


def _click(panel, stamp):
    axes = panel.axes[0]
    x, y = axes.transData.transform((mdates.date2num(stamp), sum(axes.get_ylim()) / 2))
    panel._on_click(MouseEvent('button_press_event', panel.canvas, x, y, button=1))


def test_setas_do_teclado_andam_um_timestep_sem_mexer_no_zoom(panel):
    series = _serie()
    _show(panel, series)
    _click(panel, series['data'][1000])
    assert panel._selected == 1000
    xlim = panel.axes[0].get_xlim()

    widget = panel.canvas.get_tk_widget()
    widget.focus_force()
    panel.update()
    widget.event_generate('<Right>')
    widget.event_generate('<Right>')
    widget.event_generate('<Left>')
    panel.update()

    assert panel._selected == 1001
    # O ← do matplotlib é "voltar no histórico de zoom"; não pode disparar.
    assert panel.axes[0].get_xlim() == xlim


def test_leitura_antiga_e_descartada_ao_trocar_de_execucao(panel, monkeypatch):
    from confortimetro.gui.components import timeseries_panel

    monkeypatch.setattr(timeseries_panel.threading, "Thread",
                        lambda target, daemon: type("T", (), {"start": lambda self: None})())
    panel.set_run({'path': '/a', 'rooms_disponiveis': ['SALA1']})
    panel.activate()
    token_antigo = panel._token

    panel.set_run({'path': '/b', 'rooms_disponiveis': ['SALA2']})
    panel._load_done(token_antigo, 'SALA1', _serie())

    assert panel._series is None


def test_clique_com_lupa_ou_pan_ativos_nao_seleciona(panel):
    series = _serie()
    _show(panel, series)

    panel.toolbar.zoom()
    _click(panel, series['data'][500])
    assert panel._selected is None

    panel.toolbar.zoom()  # desliga
    _click(panel, series['data'][500])
    assert panel._selected == 500


def test_selecionar_fora_da_janela_recentra(panel):
    series = _serie()
    _show(panel, series)
    panel._render(series['data'][0], series['data'][143])  # só o primeiro dia
    panel._select(1500)

    low, high = panel.axes[0].get_xlim()
    stamp = mdates.date2num(series['data'][1500])
    assert low < stamp < high
    assert abs((low + high) / 2 - stamp) < 1e-6


def test_sem_em_conforto_faixa_some_e_legenda_avisa(panel):
    _show(panel, _serie(conforto=False))

    textos = [text.get_text() for text in panel.axes[1].get_legend().get_texts()]
    assert 'Conforto não gravado' in textos
    assert 'Em conforto' not in textos


def test_com_em_conforto_mostra_os_dois_estados(panel):
    _show(panel, _serie())

    textos = [text.get_text() for text in panel.axes[1].get_legend().get_texts()]
    assert {'Em conforto', 'Fora de conforto'} <= set(textos)


def test_tabela_temporal_e_paginada_e_seleciona_o_timestep(panel):
    series = _serie(501)
    _show(panel, series)

    panel.show_table_view()
    panel.update()

    assert panel.series_table_body.winfo_ismapped()
    assert len(panel.series_table.get_children()) == 250
    assert 'página 1/3' in panel.table_page_var.get()

    panel._change_table_page(1)
    assert panel.series_table.get_children()[0] == '250'
    panel.series_table.selection_set('300')
    panel.update()

    assert panel._selected == 300
    assert panel.selected_var.get() == series['data'][300].strftime('%d/%m/%Y %H:%M')
