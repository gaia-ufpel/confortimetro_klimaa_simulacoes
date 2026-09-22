"""Série temporal de uma execução, timestep a timestep, na página de detalhes.

Quatro painéis com o tempo compartilhado e uma tabela ao lado com o timestep
clicado. A resolução acompanha o zoom (`series.window_series`): com poucos
timesteps na tela cada um aparece; com muitos, cada bloco vira média e faixa
mínimo–máximo, para um pico ou um acionamento curto não sumir.
"""

import threading
import tkinter as tk
from tkinter import ttk

import matplotlib.dates as mdates
import numpy
import pandas
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)
from matplotlib.figure import Figure

from confortimetro.results.charts import BACKGROUND, GRID_COLOR, PALETTE, TEXT_COLOR
from confortimetro.results.series import load_zone_series, window_series

from ..theme import COLORS, SPACE, RoundedButton

JOULES_PER_KWH = 3.6e6
COMFORT_COLOR = '#588157'
DISCOMFORT_COLOR = '#b3261e'
STATES = (('janela', 'Janela', '#588157'), ('ventilador', 'Ventilador', '#a06b00'),
          ('ac', 'AC', '#b3261e'), ('doas', 'DOAS', '#7a6f9b'))
# Espera após o último zoom/arraste antes de redesenhar: a barra dispara um
# evento por eixo e vários por segundo durante o arraste.
REDRAW_DELAY_MS = 150


def _on_off(on, off):
    return lambda value: on if value else off


# Linhas da tabela lateral: apelido de `series.COLUMNS` -> (rótulo, formato).
TABLE_ROWS = (
    ('temp_externa', 'Temp. externa', lambda v: f"{v:.1f} °C"),
    ('temp_operativa', 'Temp. operativa', lambda v: f"{v:.1f} °C"),
    ('adap_min', 'Banda adapt. mín.', lambda v: f"{v:.1f} °C"),
    ('adap_max', 'Banda adapt. máx.', lambda v: f"{v:.1f} °C"),
    ('pmv', 'PMV', lambda v: f"{v:.2f}"),
    ('em_conforto', 'Conforto', _on_off('Em conforto', 'Fora de conforto')),
    ('ocupacao', 'Ocupação', lambda v: f"{v:.0f} pessoa(s)"),
    ('clo', 'Vestimenta', lambda v: f"{v:.2f} clo"),
    ('janela', 'Janela', _on_off('Aberta', 'Fechada')),
    ('ventilador', 'Ventilador', _on_off('Ligado', 'Desligado')),
    ('ac', 'AC', _on_off('Ligado', 'Desligado')),
    ('doas', 'DOAS', _on_off('Ligado', 'Desligado')),
    ('co2', 'CO₂', lambda v: f"{v:.0f} ppm"),
    ('aquecimento', 'Aquecimento', lambda v: f"{v / JOULES_PER_KWH * 1000:.1f} Wh"),
    ('resfriamento', 'Resfriamento', lambda v: f"{v / JOULES_PER_KWH * 1000:.1f} Wh"),
)


class TimeSeriesPanel(ttk.Frame):
    """Zona em cima, gráfico à esquerda, valores do timestep à direita."""

    def __init__(self, parent):
        super().__init__(parent, style="Surface.TFrame")
        self.room_var = tk.StringVar()
        self.status_var = tk.StringVar(value="")
        self._run = None
        self._series = None
        self._selected = None
        self._pending = False
        self._active = False
        self._token = 0
        self._redraw_job = None
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        bar = ttk.Frame(self, style="Surface.TFrame")
        bar.pack(fill="x", pady=(0, SPACE[2]))
        ttk.Label(bar, text="Zona", style="Label.TLabel").pack(
            side="left", padx=(0, SPACE[1]))
        self.room_combo = ttk.Combobox(bar, textvariable=self.room_var,
                                       style="Field.TCombobox", state="readonly",
                                       width=16)
        self.room_combo.pack(side="left", padx=(0, SPACE[2]))
        self.room_combo.bind('<<ComboboxSelected>>',
                             lambda _e: self.load(self.room_var.get()))
        RoundedButton(bar, text="Ver tudo", variant="ghost", icon="chart",
                      command=self.show_all).pack(side="left")
        ttk.Label(bar, textvariable=self.status_var,
                  style="Caption.TLabel").pack(side="right")

        body = ttk.Frame(self, style="Surface.TFrame")
        body.pack(fill="both", expand=True)

        # A tabela entra primeiro para garantir a largura dela; o gráfico fica
        # com o resto.
        side = ttk.Frame(body, style="Surface.TFrame")
        side.pack(side="right", fill="y", padx=(SPACE[2], 0))
        self.selected_var = tk.StringVar(value="Clique no gráfico para ver um timestep.")
        ttk.Label(side, textvariable=self.selected_var, style="Label.TLabel",
                  wraplength=250).pack(anchor="w", pady=(0, SPACE[1]))
        self.table = ttk.Treeview(side, style="Modern.Treeview", show="headings",
                                  columns=("variavel", "valor"), height=len(TABLE_ROWS))
        self.table.heading("variavel", text="Variável")
        self.table.heading("valor", text="Valor")
        self.table.column("variavel", width=145, stretch=False)
        self.table.column("valor", width=120, stretch=False)
        # Em 1366×768 as 15 linhas não cabem inteiras.
        table_scroll = ttk.Scrollbar(side, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=table_scroll.set)
        table_scroll.pack(side="right", fill="y")
        self.table.pack(fill="y", expand=True)

        self.chart_frame = ttk.Frame(body, style="Surface.TFrame")
        self.chart_frame.pack(side="left", fill="both", expand=True)

        # Margens fixas em vez de `layout='constrained'`: o layout automático
        # era recalculado a cada redesenho e dobrava o tempo de zoom/arraste.
        self.figure = Figure(figsize=(9, 7), facecolor=BACKGROUND)
        self.axes = self.figure.subplots(4, 1, sharex=True,
                                         gridspec_kw={'height_ratios': [3, 2, 1.4, 2]})
        self.figure.subplots_adjust(left=0.08, right=0.93, top=0.98, bottom=0.06,
                                    hspace=0.12)
        self.energy_axes = self.axes[3].twinx()
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_frame)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.chart_frame,
                                            pack_toolbar=False)
        self.toolbar.configure(background=COLORS["surface"])
        self.toolbar.update()
        self.message = ttk.Label(self.chart_frame, style="Caption.TLabel",
                                 justify="center")

        self.canvas.mpl_connect('button_press_event', self._on_click)
        widget = self.canvas.get_tk_widget()
        # Setas no próprio widget: o manipulador de teclas do matplotlib usa
        # ← e → para voltar e avançar o histórico de zoom.
        widget.bind('<Left>', lambda _e: self._step(-1) or "break")
        widget.bind('<Right>', lambda _e: self._step(1) or "break")

        self._show_message("Abra uma execução para ver a série temporal.")

    def _show_message(self, text):
        self.toolbar.pack_forget()
        self.canvas.get_tk_widget().pack_forget()
        self.message.configure(text=text)
        self.message.pack(expand=True)

    def _show_plot(self):
        self.message.pack_forget()
        # A barra vai ao chão antes do canvas; na ordem inversa o canvas a come.
        self.toolbar.pack(side="bottom", fill="x")
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # -------------------------------------------------------------- dados

    def set_run(self, run):
        """Troca a execução; a série só é lida quando a aba fica visível."""
        self._run = run
        self._series = None
        self._token += 1
        self._clear_selection()
        rooms = list(run.get('rooms_disponiveis') or [])
        self.room_combo["values"] = rooms
        self.room_var.set(rooms[0] if rooms else "")
        self.status_var.set("")
        if not rooms:
            self._pending = False
            self._show_message(
                "Esta execução não tem planilhas por zona (<ZONA>.xlsx).\n"
                "A simulação falhou ou não terminou; não há série para mostrar.")
            return
        self._pending = True
        self._show_message("A série é lida ao abrir esta aba.")
        if self._active:
            self.activate()

    def activate(self):
        """Chamado quando a aba fica visível."""
        self._active = True
        if self._pending:
            self.load(self.room_var.get())

    def deactivate(self):
        self._active = False

    def load(self, room):
        if not self._run or not room:
            return
        self._pending = False
        self._token += 1
        token = self._token
        self._series = None
        self._clear_selection()
        self.status_var.set(f"Lendo {room}…")
        self._show_message(f"Lendo a série da zona {room}…\n"
                           "A primeira leitura da planilha leva cerca de 20 s; "
                           "depois fica em cache.")
        run_path = self._run['path']

        def work():
            try:
                series = load_zone_series(run_path, room)
            except Exception as error:  # noqa: BLE001 — vira mensagem na tela
                self.after(0, lambda: self._load_failed(token, room, error))
                return
            self.after(0, lambda: self._load_done(token, room, series))

        threading.Thread(target=work, daemon=True).start()

    def _load_done(self, token, room, series):
        # Troca de execução ou de zona no meio da leitura: resultado velho.
        if token != self._token:
            return
        if series.empty:
            self._show_message(f"A planilha da zona {room} não tem timesteps.")
            return
        self._series = series.sort_values('data').reset_index(drop=True)
        self.status_var.set(f"{room}: {len(self._series)} timesteps.")
        self._show_plot()
        self.show_all()

    def _load_failed(self, token, room, error):
        if token != self._token:
            return
        self.status_var.set(f"Falha ao ler {room}.")
        self._show_message(f"Não foi possível ler a série da zona {room}:\n{error}")

    # ------------------------------------------------------------ desenho

    def show_all(self):
        if self._series is None:
            return
        data = self._series['data']
        self._render(data.iloc[0], data.iloc[-1])

    def _on_xlim_changed(self, _axes):
        if self._redraw_job is not None:
            self.after_cancel(self._redraw_job)
        self._redraw_job = self.after(REDRAW_DELAY_MS, self._redraw_visible)

    def _redraw_visible(self):
        self._redraw_job = None
        if self._series is None:
            return
        low, high = self.axes[0].get_xlim()
        self._render(_timestamp(low), _timestamp(high))

    def _render(self, start, end):
        width = int(self.axes[0].bbox.width) or 800
        frame, aggregated = window_series(self._series, start, end, max(width, 200))

        # `cla` também zera os callbacks do eixo: o `xlim_changed` é religado
        # só depois do `set_xlim`, senão o próprio redesenho dispararia outro.
        for axes in (*self.axes, self.energy_axes):
            axes.cla()
        if not frame.empty:
            self._draw_temperatures(self.axes[0], frame, aggregated)
            self._draw_pmv(self.axes[1], frame, aggregated)
            self._draw_states(self.axes[2], frame)
            self._draw_co2_energy(self.axes[3], self.energy_axes, frame, aggregated)
        for axes in self.axes:
            _style(axes)
        _style(self.energy_axes, grid=False)
        self.axes[0].set_xlim(start, end)
        self.axes[-1].xaxis.set_major_formatter(
            mdates.ConciseDateFormatter(self.axes[-1].xaxis.get_major_locator()))
        self._draw_selection_line()
        self.axes[0].callbacks.connect('xlim_changed', self._on_xlim_changed)
        self.canvas.draw_idle()

    def _draw_temperatures(self, axes, frame, aggregated):
        x = frame['data']
        if aggregated and 'adap_min_min' in frame:
            axes.fill_between(x, frame['adap_min_min'], frame['adap_max_max'],
                              color=COMFORT_COLOR, alpha=0.15, step='post',
                              linewidth=0, label='Banda adaptativa')
        elif 'adap_min' in frame:
            axes.fill_between(x, frame['adap_min'], frame['adap_max'],
                              color=COMFORT_COLOR, alpha=0.15, step='post',
                              linewidth=0, label='Banda adaptativa')
        _line(axes, frame, 'temp_externa', aggregated, PALETTE[1], 'Externa')
        _line(axes, frame, 'temp_operativa', aggregated, PALETTE[0], 'Operativa')
        axes.set_ylabel('°C', color=TEXT_COLOR, fontsize=9)
        _legend(axes)

    def _draw_pmv(self, axes, frame, aggregated):
        axes.axhspan(-0.5, 0.5, color=COMFORT_COLOR, alpha=0.08, linewidth=0)
        _line(axes, frame, 'pmv', aggregated, PALETTE[0], 'PMV')
        axes.set_ylabel('PMV', color=TEXT_COLOR, fontsize=9)
        # Faixa no rodapé com os dois estados do EM_CONFORTO que o controle usa.
        if 'em_conforto' in frame:
            transform = axes.get_xaxis_transform()
            comfort = frame['em_conforto']
            _strip(axes, frame['data'], comfort >= 1, (0, 0.08), COMFORT_COLOR,
                   transform=transform, label='Em conforto')
            _strip(axes, frame['data'], comfort < 1, (0, 0.08), DISCOMFORT_COLOR,
                   transform=transform, label='Fora de conforto')
        else:
            axes.plot([], [], ' ', label='Conforto não gravado')
        _legend(axes)

    def _draw_states(self, axes, frame):
        ticks, labels = [], []
        for row, (name, label, color) in enumerate(reversed(STATES)):
            ticks.append(row + 0.4)
            labels.append(label if name in frame else f"{label} (—)")
            if name in frame:
                _strip(axes, frame['data'], frame[name] > 0, (row, 0.8), color,
                       alpha=0.8)
        axes.set_ylim(0, len(STATES))
        axes.set_yticks(ticks, labels)

    def _draw_co2_energy(self, axes, energy_axes, frame, aggregated):
        _line(axes, frame, 'co2', aggregated, PALETTE[5], 'CO₂')
        axes.set_ylabel('ppm', color=TEXT_COLOR, fontsize=9)
        for name, label, color in (('aquecimento', 'Aquecimento', DISCOMFORT_COLOR),
                                   ('resfriamento', 'Resfriamento', '#2b6cb0')):
            _line(energy_axes, frame, name, aggregated, color, label,
                  scale=1000 / JOULES_PER_KWH)
        # O `cla` devolve o eixo gêmeo à esquerda, por cima do de CO₂.
        energy_axes.yaxis.tick_right()
        energy_axes.yaxis.set_label_position('right')
        energy_axes.set_ylabel('Wh', color=TEXT_COLOR, fontsize=9)
        energy_axes.set_ylim(bottom=0)
        handles, labels = axes.get_legend_handles_labels()
        more_handles, more_labels = energy_axes.get_legend_handles_labels()
        if handles or more_handles:
            axes.legend(handles + more_handles, labels + more_labels, ncol=3,
                        labelcolor=TEXT_COLOR, fontsize=7, loc='upper left',
                        facecolor=BACKGROUND, edgecolor='none', framealpha=0.85)

    # ------------------------------------------------------------ seleção

    def _on_click(self, event):
        if self._series is None or event.xdata is None or self.toolbar.mode:
            return
        if event.inaxes not in (*self.axes, self.energy_axes):
            return
        self.canvas.get_tk_widget().focus_set()
        stamps = self._series['data'].to_numpy()
        target = _timestamp(event.xdata).to_datetime64()
        index = int(stamps.searchsorted(target))
        # O mais próximo entre o vizinho da esquerda e o da direita.
        if index >= len(stamps) or (index > 0 and
                                    target - stamps[index - 1] < stamps[index] - target):
            index -= 1
        self._select(index)

    def _step(self, delta):
        if self._series is None or self._selected is None:
            return
        self._select(self._selected + delta)

    def _select(self, index):
        index = max(0, min(index, len(self._series) - 1))
        self._selected = index
        row = self._series.iloc[index]
        self.selected_var.set(row['data'].strftime('%d/%m/%Y %H:%M'))
        self.table.delete(*self.table.get_children())
        for name, label, fmt in TABLE_ROWS:
            value = row.get(name)
            text = "— (não gravada)" if value is None or pandas.isna(value) else fmt(value)
            self.table.insert("", "end", values=(label, text))

        low, high = self.axes[0].get_xlim()
        stamp = mdates.date2num(row['data'])
        if not low <= stamp <= high:
            # Fora da janela: recentra mantendo a largura; o redesenho vem do
            # `xlim_changed`, e a linha é redesenhada junto.
            half = (high - low) / 2
            self.axes[0].set_xlim(stamp - half, stamp + half)
        self._draw_selection_line()
        self.canvas.draw_idle()

    def _draw_selection_line(self):
        for line in getattr(self, '_selection_lines', []):
            if line.axes is not None:
                line.remove()
        self._selection_lines = []
        if self._selected is None or self._series is None:
            return
        stamp = self._series['data'].iloc[self._selected]
        self._selection_lines = [axes.axvline(stamp, color=TEXT_COLOR, linewidth=1,
                                              linestyle='--', alpha=0.7)
                                 for axes in self.axes]

    def _clear_selection(self):
        self._selected = None
        self._draw_selection_line()
        self.selected_var.set("Clique no gráfico para ver um timestep.")
        self.table.delete(*self.table.get_children())


def _timestamp(number):
    """Número de data do matplotlib -> Timestamp sem fuso, como a série."""
    return pandas.Timestamp(mdates.num2date(number)).tz_localize(None)


def _line(axes, frame, name, aggregated, color, label, scale=1.0):
    """Valor bruto, ou média com a faixa mín.–máx. do bloco quando agregado."""
    x = frame['data']
    if aggregated:
        if f'{name}_mean' not in frame:
            return
        axes.fill_between(x, frame[f'{name}_min'] * scale, frame[f'{name}_max'] * scale,
                          color=color, alpha=0.2, step='post', linewidth=0)
        axes.plot(x, frame[f'{name}_mean'] * scale, color=color, linewidth=1.2,
                  drawstyle='steps-post', label=label)
    elif name in frame:
        axes.plot(x, frame[name] * scale, color=color, linewidth=1.2, label=label)


def _strip(axes, stamps, mask, band, color, **kwargs):
    """Faixa horizontal nos trechos contínuos em que `mask` vale.

    Cada timestep ocupa até o seguinte. `fill_between(where=...)` precisa de
    dois pontos seguidos e apagava um acionamento de um único timestep.
    """
    x = mdates.date2num(stamps)
    if len(x) == 0:
        return
    step = x[1] - x[0] if len(x) > 1 else 1 / 144
    edges = numpy.append(x, x[-1] + step)
    flags = numpy.concatenate(([0], numpy.asarray(mask, dtype=int), [0]))
    starts = numpy.flatnonzero(numpy.diff(flags) == 1)
    ends = numpy.flatnonzero(numpy.diff(flags) == -1)
    spans = [(edges[a], edges[b] - edges[a]) for a, b in zip(starts, ends)]
    axes.broken_barh(spans, band, facecolors=color, linewidth=0, **kwargs)


def _style(axes, grid=True):
    axes.set_facecolor(BACKGROUND)
    axes.tick_params(colors=TEXT_COLOR, labelsize=8)
    for spine in ('top', 'right'):
        axes.spines[spine].set_visible(not grid)
    for spine in ('left', 'bottom'):
        axes.spines[spine].set_color(GRID_COLOR)
    if grid:
        axes.grid(True, color=GRID_COLOR, linewidth=0.6, alpha=0.7)


def _legend(axes):
    if axes.get_legend_handles_labels()[0]:
        axes.legend(labelcolor=TEXT_COLOR, fontsize=7, ncol=4, loc='upper left',
                    facecolor=BACKGROUND, edgecolor='none', framealpha=0.85)
