"""Listagem das simulações já executadas."""

import os
import sqlite3
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

from confortimetro.results import database
from confortimetro.results.compare import list_runs, recompute_runs

from ..theme import COLORS, FONTS, SPACE, Card, RoundedButton, toast

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

_STATUS_TEXT = {
    'pronta': 'pronta',
    'desatualizada': 'desatualizada',
    'sem estatísticas': 'sem estatísticas',
    'sem planilhas': 'sem planilhas',
}


class SimulationsPanel(ttk.Frame):
    """Tabela de execuções à esquerda, detalhes à direita, comparador embaixo."""


class SimulationsPanel(ttk.Frame):
    """Tabela de execuções à esquerda, detalhes da selecionada à direita."""

    def __init__(self, parent, outputs_path: str = "./outputs", callback=None):
        super().__init__(parent, style="Main.TFrame")
        # Quem hospeda a página trata nova execução, detalhes, duplicação e
        # comparação; o painel só sabe qual execução está selecionada.
        self.callback = callback
        self.outputs_path = tk.StringVar(value=outputs_path)
        self.status_var = tk.StringVar(value="")
        self._runs: list[dict] = []
        self._busy = False
        self._sort_state = (None, False)

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        # Topbar: todas as ações da página, na ordem em que se usa uma
        # execução — criar, ver, repetir, corrigir, abrir, comparar.
        toolbar = Card(self, pad=SPACE[3])
        toolbar.pack(fill="x", pady=(0, SPACE[4]))
        row = ttk.Frame(toolbar.body, style="Surface.TFrame")
        row.pack(fill="x")

        RoundedButton(row, text="Nova execução", variant="primary", icon="new",
                      command=self._new_run).pack(side="left")
        RoundedButton(row, text="Ver detalhes", variant="ghost", icon="details",
                      command=self._open_details).pack(side="left", padx=(SPACE[3], 0))
        RoundedButton(row, text="Duplicar", variant="ghost", icon="duplicate",
                      command=self._duplicate).pack(side="left", padx=(SPACE[2], 0))
        RoundedButton(row, text="Regerar estatísticas", variant="ghost", icon="recompute",
                      command=self.recompute_selected).pack(side="left",
                                                            padx=(SPACE[2], 0))
        RoundedButton(row, text="Abrir pasta", variant="ghost", icon="open",
                      command=self.open_selected_folder).pack(side="left",
                                                              padx=(SPACE[2], 0))
        RoundedButton(row, text="Atualizar", variant="ghost", icon="refresh",
                      command=self.refresh).pack(side="left", padx=(SPACE[2], 0))
        RoundedButton(row, text="Comparar selecionadas", variant="primary", icon="compare", command=self._compare).pack(side="right")

        info_row = ttk.Frame(toolbar.body, style="Surface.TFrame")
        info_row.pack(fill="x", pady=(SPACE[2], 0))
        # A pasta de saídas é ajuste de máquina: mora nas configurações e não
        # ocupa espaço aqui.
        ttk.Label(info_row, textvariable=self.status_var,
                  style="Caption.TLabel").pack(side="right")

        # A listagem fica com a altura das suas 12 linhas e a comparação recebe
        # todo o espaço restante: é ela que cresce quando a janela cresce.
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True)

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
        self.tree.bind("<Double-1>", lambda _event: self._open_details())

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
            toast(self, f"Banco indisponível ({error}). Lendo direto das planilhas.",
                  "warn")

        try:
            self._runs = list_runs(outputs_path, known_mtimes=known)
        except OSError as error:
            toast(self, f"Não foi possível ler a pasta: {error}", "error")
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

        ready = sum(1 for run in self._runs if run['status'] == 'pronta')
        message = (f"{len(self._runs)} execuções, {ready} com estatísticas "
                   "completas")
        if ingested:
            message += f". {ingested} ingeridas no banco agora"
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

    def set_outputs_path(self, path: str):
        """Troca a pasta listada (vem das configurações) e relê."""
        if path and path != self.outputs_path.get():
            self.outputs_path.set(path)
            self.refresh()

    def _new_run(self):
        if self.callback:
            self.callback.on_new_run()

    def _selected_run(self):
        """Primeira execução selecionada, ou aviso no rodapé."""
        runs = self._selected_runs()
        if not runs:
            toast(self, "Escolha uma execução na lista.", "warn")
            return None
        return runs[0]

    def _open_details(self):
        run = self._selected_run()
        if run and self.callback:
            self.callback.on_open_run_details(run)

    def _duplicate(self):
        run = self._selected_run()
        if run and self.callback:
            self.callback.on_duplicate_run(run)

    def _compare(self):
        """Manda as execuções escolhidas para a página de comparação."""
        runs = self._selected_runs()
        if len(runs) < 2:
            toast(self, "Escolha ao menos duas execuções para comparar.", "warn")
            return
        if self.callback:
            self.callback.on_compare_runs(runs, self.outputs_path.get())

    def open_selected_folder(self):
        runs = self._selected_runs()
        if not runs:
            toast(self, "Escolha uma execução para abrir a pasta.", "warn")
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
            toast(self, "As execuções escolhidas já têm estatísticas atualizadas.",
                  "warn")
            return

        self._busy = True
        self._set_status(f"Regerando estatísticas de {len(runs)} execuções. Isso lê todas "
                         "as planilhas por zona e leva minutos.")

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
            toast(self, f"{len(failed)} execuções falharam ao regerar:\n{detail}",
                  "error", timeout=10000)
        else:
            toast(self, f"{len(errors)} execuções regeradas.", "ok")
