"""Comparação de execuções: tabela de agregados e gráficos."""

import threading
import tkinter as tk
from tkinter import filedialog, ttk

from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)

from confortimetro.results import charts, database
from confortimetro.results.compare import (
    COMPARISON_COLUMNS,
    compare_runs,
    mismatched_periods,
)

from ..theme import COLORS, SPACE, Card, RoundedButton, scrollable, toast

# Os nomes das colunas de estatística são longos demais para caber no
# cabeçalho da tabela comparativa.
_COMPARISON_HEADINGS = {
    'Energia total (kWh)': 'Total (kWh)',
    'Aquecimento (kWh)': 'Aquec. (kWh)',
    'Resfriamento (kWh)': 'Resfr. (kWh)',
    'Fora da banda adaptativa': 'Fora adapt.',
    'PMV fora da faixa': 'PMV fora',
    'Ventilador ligado': 'Ventilador',
    'Janela aberta': 'Janela',
    'DOAS ligado': 'DOAS',
    'Nome da sala': 'Zona',
    'module_type': 'Módulo',
}


class ComparisonPanel(ttk.Frame):
    """Barra de opções em cima, números à esquerda e gráfico à direita."""

    def __init__(self, parent):
        super().__init__(parent, style="Main.TFrame")
        self.outputs_path = ""
        self.room_var = tk.StringVar()
        self.status_var = tk.StringVar(value="")
        self._runs: list[dict] = []
        self._comparison = None
        self._busy = False
        self.chart_var = tk.StringVar(value=next(iter(charts.CHARTS)))
        self.baseline_var = tk.StringVar()
        self.variable_var = tk.StringVar(value=next(iter(charts.CARPET_VARIABLES)))
        self.start_var = tk.StringVar(value='2015-01-15')
        self.days_var = tk.StringVar(value='7')

        self._build_ui()

    def set_runs(self, runs, outputs_path: str):
        """Recebe as execuções escolhidas na listagem e já compara."""
        self._runs = list(runs)
        self.outputs_path = outputs_path

        rooms = sorted({room for run in self._runs
                        for room in run['rooms_disponiveis']})
        self.room_combo["values"] = rooms
        if rooms and self.room_var.get() not in rooms:
            self.room_var.set("ATELIE1" if "ATELIE1" in rooms else rooms[0])

        self._show_chart_placeholder()
        self.compare()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        actions = Card(self, pad=SPACE[3])
        actions.pack(fill="x")
        action_row = ttk.Frame(actions.body, style="Surface.TFrame")
        action_row.pack(fill="x")

        ttk.Label(action_row, text="Zona", style="Label.TLabel").pack(
            side="left", padx=(0, SPACE[2]))
        self.room_combo = ttk.Combobox(action_row, textvariable=self.room_var,
                                       style="Field.TCombobox", state="readonly",
                                       width=18)
        self.room_combo.pack(side="left")
        RoundedButton(action_row, text="Comparar", variant="primary", icon="compare",
                      command=self.compare).pack(side="left", padx=(SPACE[3], 0))
        RoundedButton(action_row, text="Exportar CSV", variant="ghost", icon="export",
                      command=self.export_comparison).pack(side="right")

        chart_row = ttk.Frame(actions.body, style="Surface.TFrame")
        chart_row.pack(fill="x", pady=(SPACE[3], 0))
        ttk.Label(chart_row, text="Gráfico", style="Label.TLabel").pack(
            side="left", padx=(0, SPACE[2]))
        self.chart_combo = ttk.Combobox(chart_row, textvariable=self.chart_var,
                                        style="Field.TCombobox", state="readonly",
                                        values=list(charts.CHARTS), width=30)
        self.chart_combo.pack(side="left")
        self.chart_combo.bind('<<ComboboxSelected>>', self._on_chart_changed)
        RoundedButton(chart_row, text="Gerar gráfico", variant="primary", icon="chart",
                      command=self.plot).pack(side="left", padx=(SPACE[3], 0))

        # Cada gráfico mostra só as suas opções; o resto some da barra.
        self.option_row = ttk.Frame(actions.body, style="Surface.TFrame")
        self.option_row.pack(fill="x", pady=(SPACE[2], 0))
        self._option_widgets = {}
        self._build_option_fields()
        self._on_chart_changed()

        ttk.Label(actions.body, text="Os gráficos de série leem as planilhas por zona "
                                     "na primeira vez (minutos) e ficam em cache depois.",
                  style="Caption.TLabel").pack(anchor="w", pady=(SPACE[1], 0))
        ttk.Label(actions.body, textvariable=self.status_var,
                  style="Caption.TLabel").pack(anchor="w", pady=(SPACE[2], 0))

        # --- Comparação: números à esquerda, gráfico à direita ---
        compare_card = Card(self, "Comparação de resultados")
        compare_card.pack(fill="both", expand=True, pady=(SPACE[4], 0))
        compare_panes = ttk.PanedWindow(compare_card.body, orient="horizontal")
        compare_panes.pack(fill="both", expand=True)

        table_frame = ttk.Frame(compare_panes, style="Surface.TFrame")
        compare_panes.add(table_frame, weight=2)

        self.compare_tree = ttk.Treeview(table_frame, style="Modern.Treeview",
                                         show="headings", height=6)
        compare_scroll = ttk.Scrollbar(table_frame, orient="horizontal",
                                       command=self.compare_tree.xview)
        compare_scroll_y = ttk.Scrollbar(table_frame, orient="vertical",
                                         command=self.compare_tree.yview)
        self.compare_tree.configure(xscrollcommand=compare_scroll.set,
                                    yscrollcommand=compare_scroll_y.set)
        compare_scroll.pack(side="bottom", fill="x")
        compare_scroll_y.pack(side="right", fill="y")
        self.compare_tree.pack(side="left", fill="both", expand=True)

        self.chart_frame = ttk.Frame(compare_panes, style="Surface.TFrame")
        compare_panes.add(self.chart_frame, weight=5)
        self._chart_widgets = []
        self._show_chart_placeholder()

    def _build_option_fields(self):
        """Um campo por opção declarada no catálogo de gráficos."""
        baseline = ttk.Frame(self.option_row, style="Surface.TFrame")
        ttk.Label(baseline, text="Referência", style="Label.TLabel").pack(
            side="left", padx=(0, SPACE[2]))
        self.baseline_combo = ttk.Combobox(baseline, textvariable=self.baseline_var,
                                           style="Field.TCombobox", state="readonly",
                                           width=32)
        self.baseline_combo.pack(side="left")
        self._option_widgets['baseline'] = baseline

        variable = ttk.Frame(self.option_row, style="Surface.TFrame")
        ttk.Label(variable, text="Variável", style="Label.TLabel").pack(
            side="left", padx=(0, SPACE[2]))
        ttk.Combobox(variable, textvariable=self.variable_var, style="Field.TCombobox",
                     state="readonly", width=22,
                     values=list(charts.CARPET_VARIABLES)).pack(side="left")
        self._option_widgets['variable'] = variable

        period = ttk.Frame(self.option_row, style="Surface.TFrame")
        ttk.Label(period, text="Início", style="Label.TLabel").pack(
            side="left", padx=(0, SPACE[2]))
        ttk.Entry(period, textvariable=self.start_var, style="Field.TEntry",
                  width=12).pack(side="left")
        ttk.Label(period, text="Dias", style="Label.TLabel").pack(
            side="left", padx=(SPACE[3], SPACE[2]))
        ttk.Entry(period, textvariable=self.days_var, style="Field.TEntry",
                  width=5).pack(side="left")
        self._option_widgets['start'] = period
        self._option_widgets['days'] = period

    def _on_chart_changed(self, _event=None):
        options = charts.CHARTS[self.chart_var.get()][2]
        for name, widget in self._option_widgets.items():
            if name in options:
                widget.pack(side="left", padx=(0, SPACE[4]))
            else:
                widget.pack_forget()

    def _chart_options(self):
        """Valores dos campos visíveis, no formato que cada gráfico espera."""
        options = charts.CHARTS[self.chart_var.get()][2]
        values = {}
        if 'baseline' in options:
            values['baseline'] = self.baseline_var.get() or None
        if 'variable' in options:
            values['variable'] = charts.CARPET_VARIABLES[self.variable_var.get()]
        if 'start' in options:
            values['start'] = self.start_var.get().strip()
        if 'days' in options:
            try:
                values['days'] = max(int(self.days_var.get()), 1)
            except ValueError:
                values['days'] = 7
        return values

    # --------------------------------------------------------------- dados

    def _set_status(self, message: str):
        self.status_var.set(message)

    def compare(self):
        runs = self._runs
        if len(runs) < 2:
            toast(self, "Volte à listagem e escolha ao menos duas execuções.", "warn")
            return

        incomplete = [run for run in runs if run['status'] != 'pronta']
        df = self._comparison_frame(runs, self.room_var.get() or None)
        if df.empty:
            toast(self, "Nenhuma das execuções tem estatísticas completas. "
                  "Regere as que faltam na listagem.", "warn")
            return

        self._comparison = df
        self._render_comparison(df)
        self.baseline_combo["values"] = list(df['Execução'])
        if self.baseline_var.get() not in list(df['Execução']):
            self.baseline_var.set(df['Execução'].iloc[0])
        message = (f"{len(df)} linhas comparadas na zona {self.room_var.get()}."
                   + self._period_warning(df))
        if incomplete:
            message += (f" {len(incomplete)} ficaram de fora por não ter estatísticas "
                        "completas.")
        self._set_status(message)

    def _period_warning(self, df):
        """Aviso quando as execuções comparadas não cobrem o mesmo período."""
        divergent = mismatched_periods(df)
        if not divergent:
            return ""
        return (f" Atenção: {', '.join(divergent)} simulou um período diferente "
                "das demais. Os totais não são comparáveis.")

    def _render_comparison(self, df):
        columns = ["Execução", "Nome da sala", "module_type"]
        columns += [column for column in COMPARISON_COLUMNS if column in df.columns]

        self.compare_tree.delete(*self.compare_tree.get_children())
        self.compare_tree["columns"] = columns
        for column in columns:
            self.compare_tree.heading(column, text=_COMPARISON_HEADINGS.get(column, column))
            width = 250 if column == "Execução" else 130
            self.compare_tree.column(column, width=width, minwidth=width,
                                     anchor="w" if column in columns[:3] else "e",
                                     stretch=False)

        for _, row in df.iterrows():
            values = []
            for column in columns:
                value = row[column]
                values.append(f"{value:.3f}" if isinstance(value, float) else value)
            self.compare_tree.insert("", "end", values=values)

    def plot(self):
        """Desenha o gráfico escolhido para as execuções em comparação."""
        runs = [run for run in self._runs if run['status'] == 'pronta']
        if len(runs) < 2:
            toast(self, "O gráfico precisa de duas execuções com estatísticas "
                  "completas. Regere as que faltam na listagem.", "warn")
            return

        room = self.room_var.get()
        name = self.chart_var.get()
        function, needs_series, _ = charts.CHARTS[name]
        options = self._chart_options()

        # Só a leitura das séries é exclusiva; um gráfico agregado sai na hora
        # e não tem por que esperar a leitura anterior terminar.
        if needs_series and self._busy:
            toast(self, "Espere a leitura das séries terminar.", "warn")
            return

        if not needs_series:
            df = self._comparison_frame(runs, room)
            if df.empty:
                toast(self, "Sem dados agregados para essas execuções.", "warn")
                return
            try:
                figure = function(df, **options)
            except ValueError as error:
                toast(self, str(error), "error")
                return
            self._show_figure(figure, f"{name} — {room}")
            self._set_status(f"{name}: {len(df)} execuções na zona {room}."
                             + self._period_warning(df))
            return

        missing = [run['run'] for run in runs
                   if room not in run['rooms_disponiveis']]
        if missing:
            toast(self, f"{', '.join(missing)} não tem a planilha da zona {room}.",
                  "warn")
            return

        self._busy = True
        self._set_status(f"Lendo as séries de {len(runs)} execuções. A primeira leitura "
                         "de cada planilha leva cerca de 20 s.")
        series_runs = [(run['run'], run['path']) for run in runs]

        def work():
            # A leitura é o gasto; a figura sai pronta e só é anexada ao canvas
            # na thread da interface.
            try:
                figure = function(series_runs, room, **options)
            except Exception as error:
                self.after(0, lambda: self._plot_failed(error))
                return
            self.after(0, lambda: self._plot_done(figure, f"{name} — {room}"))

        threading.Thread(target=work, daemon=True).start()

    def _comparison_frame(self, runs, room):
        """Agregados das execuções: do banco quando possível, senão dos Excel."""
        paths = [run['path'] for run in runs]
        df = database.load_comparison(database.database_path(self.outputs_path),
                                      paths, room)
        return df if not df.empty else compare_runs(paths, room)

    def _plot_done(self, figure, title):
        self._busy = False
        self._show_figure(figure, title)
        self._set_status(f"{title} pronto.")

    def _plot_failed(self, error):
        self._busy = False
        toast(self, f"Falha ao gerar o gráfico: {error}", "error", timeout=10000)

    def _clear_chart(self):
        """Solta o canvas anterior; sem isso cada gráfico empilha um widget."""
        for widget in self._chart_widgets:
            widget.destroy()
        self._chart_widgets = []

    def _show_chart_placeholder(self):
        self._clear_chart()
        label = ttk.Label(
            self.chart_frame, style="Caption.TLabel", justify="center",
            text="Escolha um gráfico e clique em 'Gerar gráfico'.")
        label.pack(expand=True)
        self._chart_widgets.append(label)

    # Acima desta altura a figura não cabe no painel: um gráfico de quatro
    # painéis espremido em 300 px faz o layout do matplotlib colapsar os eixos
    # a zero e desenhar uma área vazia. Esses vão para dentro de uma área
    # rolável, no tamanho natural.
    _INLINE_MAX_INCHES = 7.5

    def _show_figure(self, figure, title):
        """Desenha o gráfico no próprio painel, com a barra de navegação."""
        self._clear_chart()
        height = figure.get_size_inches()[1]

        if height <= self._INLINE_MAX_INCHES:
            host = None
            canvas = FigureCanvasTkAgg(figure, master=self.chart_frame)
            widget = canvas.get_tk_widget()
        else:
            host = ttk.Frame(self.chart_frame, style="Surface.TFrame")
            inner = scrollable(host)
            canvas = FigureCanvasTkAgg(figure, master=inner)
            widget = canvas.get_tk_widget()
            widget.configure(height=int(height * figure.dpi))

        # A barra vai ao chão antes do gráfico: quem é empacotado primeiro tem
        # prioridade, e na ordem inversa o canvas come a barra.
        toolbar = NavigationToolbar2Tk(canvas, self.chart_frame, pack_toolbar=False)
        toolbar.configure(background=COLORS["bg"])
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")

        if host is None:
            widget.pack(fill="both", expand=True)
        else:
            host.pack(fill="both", expand=True)
            widget.pack(fill="x", expand=True)
            self._chart_widgets.append(host)

        canvas.draw()
        self._chart_widgets.extend([toolbar, widget])
        return canvas

    def export_comparison(self):
        if self._comparison is None or self._comparison.empty:
            toast(self, "Compare as execuções antes de exportar.", "warn")
            return
        path = filedialog.asksaveasfilename(
            title="Exportar comparação", defaultextension=".csv",
            initialfile="COMPARACAO.csv", filetypes=[("CSV", "*.csv")])
        if path:
            self._comparison.to_csv(path, index=False)
            self._set_status(f"Comparação exportada para {path}")

