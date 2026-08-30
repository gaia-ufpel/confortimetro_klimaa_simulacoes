"""Listagem das simulações já executadas e comparação dos resultados."""

import os
import sqlite3
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)

from confortimetro.results import charts, database
from confortimetro.results.compare import (
    COMPARISON_COLUMNS,
    compare_runs,
    list_runs,
    mismatched_periods,
    recompute_runs,
)

from ..theme import COLORS, FONTS, SPACE, Card, RoundedButton, scrollable

# Colunas da listagem: (id, título, largura).
_LIST_COLUMNS = [
    ("run", "Execução", 210),
    ("module_type", "Módulo", 150),
    ("idf", "IDF", 140),
    ("epw", "Clima", 140),
    ("rooms", "Zonas", 55),
    ("status", "Estatísticas", 115),
    ("modificado", "Modificado", 115),
]

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

_STATUS_TEXT = {
    'pronta': 'pronta',
    'desatualizada': 'desatualizada',
    'sem estatísticas': 'sem estatísticas',
    'sem planilhas': 'sem planilhas',
}


class SimulationsPanel(ttk.Frame):
    """Tabela de execuções à esquerda, detalhes à direita, comparador embaixo."""

    def __init__(self, parent, outputs_path: str = "./outputs"):
        super().__init__(parent, style="Main.TFrame")
        self.outputs_path = tk.StringVar(value=outputs_path)
        self.room_var = tk.StringVar()
        self.status_var = tk.StringVar(value="")
        self._runs: list[dict] = []
        self._comparison = None
        self._busy = False
        self._sort_state = (None, False)
        self.chart_var = tk.StringVar(value=next(iter(charts.CHARTS)))
        self.baseline_var = tk.StringVar()
        self.variable_var = tk.StringVar(value=next(iter(charts.CARPET_VARIABLES)))
        self.start_var = tk.StringVar(value='2015-01-15')
        self.days_var = tk.StringVar(value='7')

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        toolbar = Card(self, pad=SPACE[3])
        toolbar.pack(fill="x", pady=(0, SPACE[4]))
        row = ttk.Frame(toolbar.body, style="Surface.TFrame")
        row.pack(fill="x")

        ttk.Label(row, text="Pasta de saídas", style="Label.TLabel").pack(
            side="left", padx=(0, SPACE[2]))
        ttk.Entry(row, textvariable=self.outputs_path, style="Field.TEntry").pack(
            side="left", fill="x", expand=True)
        RoundedButton(row, text="Procurar", variant="ghost", width=110,
                      command=self._pick_outputs).pack(side="left", padx=(SPACE[2], 0))
        RoundedButton(row, text="Atualizar", variant="ghost", width=110,
                      command=self.refresh).pack(side="left", padx=(SPACE[2], 0))

        # A listagem fica com a altura das suas 12 linhas e a comparação recebe
        # todo o espaço restante: é ela que cresce quando a janela cresce.
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="x")

        # --- Listagem ---
        list_card = Card(panes, "Simulações executadas")
        panes.add(list_card, weight=3)

        self.tree = ttk.Treeview(
            list_card.body, style="Modern.Treeview", selectmode="extended",
            columns=[column for column, _, _ in _LIST_COLUMNS], show="headings",
            height=8)
        for column, title, width in _LIST_COLUMNS:
            self.tree.heading(column, text=title,
                              command=lambda c=column: self._sort_by(c))
            self.tree.column(column, width=width, minwidth=width, anchor="w",
                             stretch=(column == "run"))
        scroll = ttk.Scrollbar(list_card.body, orient="vertical",
                               command=self.tree.yview)
        # A tabela é mais larga que o painel: sem a barra horizontal a coluna
        # de data fica escondida.
        scroll_x = ttk.Scrollbar(list_card.body, orient="horizontal",
                                 command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=scroll_x.set)
        scroll_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Execuções sem estatísticas não entram na comparação: marcá-las
        # evita que o usuário selecione e receba uma tabela vazia sem motivo.
        self.tree.tag_configure("incompleta", foreground=COLORS["text_mute"])

        # --- Detalhes ---
        detail_card = Card(panes, "Detalhes")
        panes.add(detail_card, weight=2)
        self.detail_text = tk.Text(
            detail_card.body, height=12, width=42, wrap="none", state="disabled",
            font=FONTS["mono"], background=COLORS["surface"], foreground=COLORS["text"],
            relief="flat", borderwidth=0, highlightthickness=1,
            highlightbackground=COLORS["line"], padx=SPACE[3], pady=SPACE[3])
        self.detail_text.pack(fill="both", expand=True)

        # --- Ações ---
        actions = Card(self, pad=SPACE[3])
        actions.pack(fill="x", pady=(SPACE[4], 0))
        action_row = ttk.Frame(actions.body, style="Surface.TFrame")
        action_row.pack(fill="x")

        ttk.Label(action_row, text="Zona", style="Label.TLabel").pack(
            side="left", padx=(0, SPACE[2]))
        self.room_combo = ttk.Combobox(action_row, textvariable=self.room_var,
                                       style="Field.TCombobox", state="readonly",
                                       width=18)
        self.room_combo.pack(side="left")

        RoundedButton(action_row, text="Comparar selecionadas", variant="primary",
                      width=210, command=self.compare_selected).pack(
                          side="left", padx=(SPACE[3], 0))
        RoundedButton(action_row, text="Regerar estatísticas", variant="ghost",
                      width=190, command=self.recompute_selected).pack(
                          side="left", padx=(SPACE[2], 0))
        RoundedButton(action_row, text="Abrir pasta", variant="ghost", width=130,
                      command=self.open_selected_folder).pack(
                          side="left", padx=(SPACE[2], 0))
        RoundedButton(action_row, text="Exportar CSV", variant="ghost", width=150,
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
        RoundedButton(chart_row, text="Gerar gráfico", variant="primary", width=170,
                      command=self.plot_selected).pack(side="left", padx=(SPACE[3], 0))

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

    def refresh(self):
        """Sincroniza o banco, relê a pasta de saídas e repovoa a listagem."""
        outputs_path = self.outputs_path.get()
        try:
            # O banco guarda os agregados já lidos; o mtime registrado evita
            # reabrir o Excel de cada execução só para descobrir o status.
            ingested, _ = database.sync(outputs_path)
            known = database.known_mtimes(database.database_path(outputs_path))
        except (OSError, sqlite3.Error) as error:
            ingested, known = 0, {}
            self._set_status(f"Banco indisponível ({error}); lendo direto das planilhas.")

        try:
            self._runs = list_runs(outputs_path, known_mtimes=known)
        except OSError as error:
            messagebox.showerror("Erro", f"Não foi possível ler a pasta: {error}")
            return

        self.tree.delete(*self.tree.get_children())
        for run in self._runs:
            self.tree.insert(
                "", "end", iid=run['path'],
                values=(run['run'], run['module_type'] or "—", run['idf'] or "—",
                        run['epw'] or "—", len(run['rooms_disponiveis']),
                        _STATUS_TEXT.get(run['status'], run['status']),
                        run['modificado'].strftime("%d/%m/%Y %H:%M")),
                tags=() if run['status'] == 'pronta' else ("incompleta",))

        rooms = sorted({room for run in self._runs for room in run['rooms_disponiveis']})
        self.room_combo["values"] = rooms
        if rooms and self.room_var.get() not in rooms:
            self.room_var.set("ATELIE1" if "ATELIE1" in rooms else rooms[0])

        ready = sum(1 for run in self._runs if run['status'] == 'pronta')
        message = (f"{len(self._runs)} execução(ões), {ready} com estatísticas "
                   "completas")
        if ingested:
            message += f" — {ingested} ingerida(s) no banco agora"
        self._set_status(message)

    def _sort_by(self, column):
        rows = [(self.tree.set(item, column), item) for item in self.tree.get_children()]
        column_before, descending_before = self._sort_state
        descending = not descending_before if column_before == column else False
        self._sort_state = (column, descending)
        for index, (_, item) in enumerate(sorted(rows, reverse=descending)):
            self.tree.move(item, "", index)

    def _selected_runs(self) -> list[dict]:
        selected = set(self.tree.selection())
        return [run for run in self._runs if run['path'] in selected]

    def _on_select(self, _event=None):
        runs = self._selected_runs()
        lines = []
        if len(runs) == 1:
            run = runs[0]
            lines.append(f"{run['run']}\n{'-' * len(run['run'])}")
            lines.append(f"status      {run['status']}")
            lines.append(f"zonas       {', '.join(run['rooms_disponiveis']) or '—'}")
            lines.append("")
            for key, value in run['config'].items():
                if key in ('rooms', 'input_path', 'expanded_idf_path', 'idf_filename'):
                    continue
                if isinstance(value, str) and os.sep in value:
                    value = os.path.basename(value)
                lines.append(f"{key.lstrip('_'):24s} {value}")
        elif runs:
            lines.append(f"{len(runs)} execuções selecionadas:\n")
            lines.extend(f"· {run['run']} ({run['status']})" for run in runs)

        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", "\n".join(lines))
        self.detail_text.configure(state="disabled")

    # -------------------------------------------------------------- ações

    def _set_status(self, message: str):
        self.status_var.set(message)

    def _pick_outputs(self):
        path = filedialog.askdirectory(title="Pasta de saídas",
                                       initialdir=self.outputs_path.get())
        if path:
            self.outputs_path.set(path)
            self.refresh()

    def open_selected_folder(self):
        runs = self._selected_runs()
        if not runs:
            self._set_status("Selecione uma execução para abrir a pasta.")
            return
        path = os.path.abspath(runs[0]['path'])
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])

    def recompute_selected(self):
        """Regera ESTATISTICAS.xlsx das execuções selecionadas, em segundo plano."""
        if self._busy:
            return
        runs = [run for run in self._selected_runs()
                if run['status'] in ('desatualizada', 'sem estatísticas')]
        if not runs:
            self._set_status("Nenhuma execução selecionada precisa ser regerada.")
            return

        self._busy = True
        self._set_status(f"Regerando estatísticas de {len(runs)} execução(ões)… "
                         "isso lê todas as planilhas por zona e leva minutos.")

        def work():
            # Cada planilha por zona tem dezenas de milhares de linhas: fora da
            # thread a interface congelaria por minutos.
            errors = recompute_runs([run['path'] for run in runs])
            self.after(0, lambda: self._recompute_done(errors))

        threading.Thread(target=work, daemon=True).start()

    def _recompute_done(self, errors: dict):
        self._busy = False
        failed = {path: error for path, error in errors.items() if error}
        self.refresh()
        if failed:
            detail = "\n".join(f"{os.path.basename(path)}: {error}"
                               for path, error in failed.items())
            self._set_status(f"{len(failed)} execução(ões) falharam ao regerar.")
            messagebox.showwarning("Estatísticas", detail)
        else:
            self._set_status(f"{len(errors)} execução(ões) regeradas.")

    def compare_selected(self):
        runs = self._selected_runs()
        if len(runs) < 2:
            self._set_status("Selecione ao menos duas execuções para comparar.")
            return

        incomplete = [run for run in runs if run['status'] != 'pronta']
        df = self._comparison_frame(runs, self.room_var.get() or None)
        if df.empty:
            self._set_status("Nenhuma das execuções selecionadas tem estatísticas "
                             "completas; use 'Regerar estatísticas'.")
            return

        self._comparison = df
        self._render_comparison(df)
        self.baseline_combo["values"] = list(df['Execução'])
        if self.baseline_var.get() not in list(df['Execução']):
            self.baseline_var.set(df['Execução'].iloc[0])
        message = (f"{len(df)} linha(s) comparadas na zona {self.room_var.get()}."
                   + self._period_warning(df))
        if incomplete:
            message += (f" {len(incomplete)} execução(ões) ficaram de fora por não ter "
                        "estatísticas completas.")
        self._set_status(message)

    def _period_warning(self, df):
        """Aviso quando as execuções comparadas não cobrem o mesmo período."""
        divergent = mismatched_periods(df)
        if not divergent:
            return ""
        return (f" Atenção: {', '.join(divergent)} simulou um período diferente "
                "das demais; os totais não são comparáveis.")

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

    def plot_selected(self):
        """Desenha o gráfico escolhido para as execuções selecionadas."""
        runs = [run for run in self._selected_runs() if run['status'] == 'pronta']
        if len(runs) < 2:
            self._set_status("Selecione ao menos duas execuções com estatísticas "
                             "completas para gerar um gráfico.")
            return

        room = self.room_var.get()
        name = self.chart_var.get()
        function, needs_series, _ = charts.CHARTS[name]
        options = self._chart_options()

        # Só a leitura das séries é exclusiva; um gráfico agregado sai na hora
        # e não tem por que esperar a leitura anterior terminar.
        if needs_series and self._busy:
            self._set_status("Aguarde a leitura das séries em andamento terminar.")
            return

        if not needs_series:
            df = self._comparison_frame(runs, room)
            if df.empty:
                self._set_status("Sem dados agregados para essas execuções.")
                return
            try:
                figure = function(df, **options)
            except ValueError as error:
                self._set_status(str(error))
                return
            self._show_figure(figure, f"{name} — {room}")
            self._set_status(f"{name}: {len(df)} execução(ões) na zona {room}."
                             + self._period_warning(df))
            return

        missing = [run['run'] for run in runs
                   if room not in run['rooms_disponiveis']]
        if missing:
            self._set_status(f"{', '.join(missing)} não tem a planilha da zona {room}.")
            return

        self._busy = True
        self._set_status(f"Lendo as séries de {len(runs)} execução(ões)… a primeira "
                         "leitura de cada planilha leva ~20 s.")
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
        df = database.load_comparison(database.database_path(self.outputs_path.get()),
                                      paths, room)
        return df if not df.empty else compare_runs(paths, room)

    def _plot_done(self, figure, title):
        self._busy = False
        self._show_figure(figure, title)
        self._set_status(f"{title} pronto.")

    def _plot_failed(self, error):
        self._busy = False
        self._set_status(f"Falha ao gerar o gráfico: {error}")
        messagebox.showerror("Gráfico", str(error))

    def _clear_chart(self):
        """Solta o canvas anterior; sem isso cada gráfico empilha um widget."""
        for widget in self._chart_widgets:
            widget.destroy()
        self._chart_widgets = []

    def _show_chart_placeholder(self):
        self._clear_chart()
        label = ttk.Label(
            self.chart_frame, style="Caption.TLabel", justify="center",
            text="Selecione as execuções, escolha um gráfico\ne clique em "
                 "'Gerar gráfico'.")
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
            self._set_status("Compare alguma coisa antes de exportar.")
            return
        path = filedialog.asksaveasfilename(
            title="Exportar comparação", defaultextension=".csv",
            initialfile="COMPARACAO.csv", filetypes=[("CSV", "*.csv")])
        if path:
            self._comparison.to_csv(path, index=False)
            self._set_status(f"Comparação exportada para {path}")


def open_simulations_window(parent, outputs_path: str = "./outputs") -> tk.Toplevel:
    """Abre a listagem/comparador em uma janela própria."""
    window = tk.Toplevel(parent)
    window.title("Simulações e comparação de resultados")
    window.geometry("1500x980")
    window.minsize(1000, 700)
    window.configure(background=COLORS["bg"])
    panel = SimulationsPanel(window, outputs_path)
    panel.pack(fill="both", expand=True, padx=SPACE[5], pady=SPACE[5])
    return window
