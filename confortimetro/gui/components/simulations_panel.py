"""Listagem das simulações já executadas."""

import datetime
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
    """Tabela de execuções à esquerda, detalhes da selecionada à direita."""

    def __init__(self, parent, outputs_path: str = "./outputs", callback=None):
        super().__init__(parent, style="Main.TFrame")
        # Quem hospeda a página trata nova execução, detalhes, duplicação e
        # comparação; o painel só sabe qual execução está selecionada.
        self.callback = callback
        self.outputs_path = tk.StringVar(value=outputs_path)
        self.status_var = tk.StringVar(value="")
        self._runs: list[dict] = []
        # Execuções em andamento: entram na listagem antes de existir pasta.
        self._running: dict[str, dict] = {}
        self._busy = False
        self._sort_state = (None, False)
        self._summary_cache: dict[str, dict] = {}

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        # A listagem fica com peso 3 e os detalhes com peso 2 no PanedWindow.
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True)

        # --- Listagem (Esquerda) ---
        list_card = Card(panes, "Simulações executadas")
        panes.add(list_card, weight=3)

        # Barra de status sutil no topo da tabela e ação rápida de nova execução
        top_info = ttk.Frame(list_card.body, style="Surface.TFrame")
        top_info.pack(fill="x", pady=(0, SPACE[2]))
        ttk.Label(top_info, textvariable=self.status_var,
                  style="Caption.TLabel").pack(side="left")
        self.btn_new_run = RoundedButton(
            top_info, text="Nova execução", variant="primary", icon="new",
            command=self._new_run)
        self.btn_new_run.pack(side="right")

        # Container da Treeview com barras de rolagem
        tree_container = ttk.Frame(list_card.body, style="Surface.TFrame")
        tree_container.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            tree_container, style="Modern.Treeview", selectmode="extended",
            columns=[column for column, _, _ in _LIST_COLUMNS], show="headings",
            height=10)
        for column, title, width in _LIST_COLUMNS:
            self.tree.heading(column, text=title,
                              command=lambda c=column: self._sort_by(c))
            self.tree.column(column, width=width, minwidth=width, anchor="w",
                             stretch=(column == "run"))
        scroll = ttk.Scrollbar(tree_container, orient="vertical",
                               command=self.tree.yview)
        scroll_x = ttk.Scrollbar(tree_container, orient="horizontal",
                                 command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=scroll_x.set)
        scroll_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _event: self._open_details())

        self.tree.tag_configure("incompleta", foreground=COLORS["text_mute"])
        self.tree.tag_configure("executando", foreground=COLORS["primary"])

        # Barra inferior contextual de Comparação
        self.compare_bar = ttk.Frame(list_card.body, style="Surface.TFrame")
        self.compare_bar.pack(fill="x", pady=(SPACE[3], 0))
        self.compare_info_var = tk.StringVar(
            value="Selecione 2 ou mais execuções para comparar")
        ttk.Label(self.compare_bar, textvariable=self.compare_info_var,
                  style="Caption.TLabel").pack(side="left", padx=(SPACE[1], 0))

        self.compare_btn = RoundedButton(
            self.compare_bar, text="Comparar selecionadas", variant="primary",
            icon="compare", command=self._compare)
        self.compare_btn.pack(side="right")
        self.compare_btn.configure(state="disabled")

        # --- Detalhes (Direita) ---
        detail_card = Card(panes, "Detalhes")
        panes.add(detail_card, weight=2)

        # Mini-toolbar contextual de ações da simulação
        self.actions_bar = ttk.Frame(detail_card.body, style="Surface.TFrame")
        self.actions_bar.pack(fill="x", pady=(0, SPACE[3]))

        self.btn_details = RoundedButton(
            self.actions_bar, text="Ver detalhes", variant="primary", icon="details",
            command=self._open_details)
        self.btn_details.pack(side="left")

        self.btn_duplicate = RoundedButton(
            self.actions_bar, text="Duplicar", variant="ghost", icon="duplicate",
            command=self._duplicate)
        self.btn_duplicate.pack(side="left", padx=(SPACE[1], 0))

        self.btn_open = RoundedButton(
            self.actions_bar, text="Abrir pasta", variant="ghost", icon="open",
            command=self.open_selected_folder)
        self.btn_open.pack(side="left", padx=(SPACE[1], 0))

        self.btn_assistant = RoundedButton(
            self.actions_bar, text="Assistente", variant="ghost", icon="info",
            command=self._ask_assistant)
        self.btn_assistant.pack(side="left", padx=(SPACE[1], 0))

        # Indicadores Chave de Desempenho (KPI Cards)
        self.kpi_frame = ttk.Frame(detail_card.body, style="Surface.TFrame")
        self.kpi_frame.pack(fill="x", pady=(0, SPACE[3]))

        self.kpi_energy_card = tk.Frame(self.kpi_frame, bg=COLORS["surface_2"],
                                        highlightthickness=1,
                                        highlightbackground=COLORS["line"])
        self.kpi_energy_card.pack(side="left", fill="both", expand=True, padx=(0, SPACE[2]))
        tk.Label(self.kpi_energy_card, text="CONSUMO TOTAL", bg=COLORS["surface_2"],
                 fg=COLORS["text_mute"], font=FONTS["caption"]).pack(anchor="w", padx=SPACE[3], pady=(SPACE[2], 0))
        self.kpi_energy_val = tk.Label(
            self.kpi_energy_card, text="—", bg=COLORS["surface_2"],
            fg=COLORS["text"], font=FONTS["h2"])
        self.kpi_energy_val.pack(anchor="w", padx=SPACE[3], pady=(0, SPACE[2]))

        self.kpi_discomfort_card = tk.Frame(self.kpi_frame, bg=COLORS["surface_2"],
                                            highlightthickness=1,
                                            highlightbackground=COLORS["line"])
        self.kpi_discomfort_card.pack(side="left", fill="both", expand=True)
        tk.Label(self.kpi_discomfort_card, text="DESCONFORTO TÉRMICO", bg=COLORS["surface_2"],
                 fg=COLORS["text_mute"], font=FONTS["caption"]).pack(anchor="w", padx=SPACE[3], pady=(SPACE[2], 0))
        self.kpi_discomfort_val = tk.Label(
            self.kpi_discomfort_card, text="—", bg=COLORS["surface_2"],
            fg=COLORS["text"], font=FONTS["h2"])
        self.kpi_discomfort_val.pack(anchor="w", padx=SPACE[3], pady=(0, SPACE[2]))

        # Texto detalhado com parâmetros e configurações formatados
        detail_text_frame = ttk.Frame(detail_card.body, style="Surface.TFrame")
        detail_text_frame.pack(fill="both", expand=True)

        self.detail_text = tk.Text(
            detail_text_frame, height=12, width=42, wrap="word", state="disabled",
            font=FONTS["body"], background=COLORS["surface"], foreground=COLORS["text"],
            relief="flat", borderwidth=0, highlightthickness=1,
            highlightbackground=COLORS["line"], padx=SPACE[3], pady=SPACE[3])
        detail_scroll = ttk.Scrollbar(detail_text_frame, orient="vertical",
                                      command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        detail_scroll.pack(side="right", fill="y")
        self.detail_text.pack(side="left", fill="both", expand=True)

        # Tags de formatação visual do texto
        self.detail_text.tag_configure("title", font=FONTS["h2"], foreground=COLORS["primary"],
                                       spacing1=2, spacing3=4)
        self.detail_text.tag_configure("section", font=FONTS["label"], foreground=COLORS["primary_d"],
                                       spacing1=10, spacing3=4)
        self.detail_text.tag_configure("param_label", font=FONTS["label"], foreground=COLORS["text_mute"])
        self.detail_text.tag_configure("param_val", font=FONTS["body"], foreground=COLORS["text"])
        self.detail_text.tag_configure("help", font=FONTS["caption"], foreground=COLORS["text_mute"],
                                       spacing1=4, spacing3=4)
        self.detail_text.tag_configure("bullet", font=FONTS["body"], foreground=COLORS["text"],
                                       lmargin1=12, lmargin2=24)

        # Rodapé do painel de detalhes: Ação secundária para regerar estatísticas
        self.detail_footer = ttk.Frame(detail_card.body, style="Surface.TFrame")
        self.detail_footer.pack(fill="x", pady=(SPACE[2], 0))
        self.btn_recompute = RoundedButton(
            self.detail_footer, text="Regerar estatísticas", variant="ghost", icon="recompute",
            command=self.recompute_selected)
        self.btn_recompute.pack(side="right")

        self._render_detail_empty()

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

        # As em andamento vêm primeiro e podem ainda não ter pasta na listagem.
        listed = {run['path'] for run in self._runs}
        rows = [self._running[path] for path in self._running if path not in listed]
        rows += self._runs

        self.tree.delete(*self.tree.get_children())
        self._summary_cache.clear()
        for run in rows:
            running = run['path'] in self._running
            status = 'em simulação' if running else run['status']
            tags = ("executando",) if running else (
                () if run['status'] == 'pronta' else ("incompleta",))
            self.tree.insert(
                "", "end", iid=run['path'],
                values=(run['run'], run['module_type'] or "—", run['idf'] or "—",
                        run['epw'] or "—", len(run['rooms_disponiveis']),
                        _STATUS_TEXT.get(status, status),
                        run['modificado'].strftime("%d/%m/%Y %H:%M")),
                tags=tags)

        ready = sum(1 for run in self._runs if run['status'] == 'pronta')
        message = (f"{len(self._runs)} execuções, {ready} com estatísticas "
                   "completas")
        if ingested:
            message += f". {ingested} ingeridas no banco agora"
        self._set_status(message)

    def set_running(self, path: str, config=None):
        """Marca uma execução como em andamento e a mostra já na listagem."""
        self._running[path] = {
            'run': os.path.basename(os.path.normpath(path)),
            'path': path,
            'status': 'em simulação',
            'module_type': getattr(config, 'module_type', None),
            'idf': os.path.basename(getattr(config, 'idf_path', '') or ''),
            'epw': os.path.basename(getattr(config, 'epw_path', '') or ''),
            'rooms_disponiveis': getattr(config, 'rooms', None) or [],
            'modificado': datetime.datetime.now(),
            'config': {},
        }
        self.refresh()

    def clear_running(self, path: str):
        """Execução terminou: sai do estado 'em simulação'."""
        if self._running.pop(path, None) is not None:
            self.refresh()

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

    def _update_button_states(self, selected_count: int):
        """Habilita ou desabilita as ações contextuais conforme a seleção."""
        item_state = "normal" if selected_count >= 1 else "disabled"
        for btn in (self.btn_details, self.btn_duplicate, self.btn_open,
                    self.btn_assistant, self.btn_recompute):
            btn.configure(state=item_state)

        if selected_count >= 2:
            self.compare_btn.configure(state="normal")
            self.compare_info_var.set(f"{selected_count} execuções selecionadas para comparação")
        elif selected_count == 1:
            self.compare_btn.configure(state="disabled")
            self.compare_info_var.set("Selecione mais uma execução (Ctrl+Clique) para comparar")
        else:
            self.compare_btn.configure(state="disabled")
            self.compare_info_var.set("Selecione 2 ou mais execuções para comparar")

    def _on_select(self, _event=None):
        runs = self._selected_runs()
        self._update_button_states(len(runs))

        if len(runs) == 1:
            run = runs[0]
            run["summary"] = self._summary_for(run)

            # Atualizar os cards de KPI
            consumo_val = self._metric_text(run, 'Energia total (kWh)', 'kWh')
            desconf_val = self._metric_text(run, 'Desconforto')
            self.kpi_energy_val.configure(text=consumo_val)
            self.kpi_discomfort_val.configure(text=desconf_val)

            # Renderização estruturada e amigável dos detalhes
            self.detail_text.configure(state="normal")
            self.detail_text.delete("1.0", "end")

            # Cabeçalho da execução
            self.detail_text.insert("end", f"{run['run']}\n", "title")

            # Seção: Informações Gerais
            self.detail_text.insert("end", "INFORMAÇÕES GERAIS\n", "section")
            self._insert_detail_field("Status:", run['status'].capitalize())
            self._insert_detail_field("Modificado:", run['modificado'].strftime("%d/%m/%Y às %H:%M"))
            self._insert_detail_field("Período:", str(self._period_text(run)))

            zonas = run.get('rooms_disponiveis') or []
            if zonas:
                zonas_str = ", ".join(zonas)
                self._insert_detail_field(f"Zonas ({len(zonas)}):", zonas_str)

            # Seção: Arquivos do Modelo
            self.detail_text.insert("end", "\nARQUIVOS E DIRETÓRIOS\n", "section")
            if run.get('idf'):
                self._insert_detail_field("Modelo (IDF):", run['idf'])
            if run.get('epw'):
                self._insert_detail_field("Clima (EPW):", run['epw'])
            if run.get('module_type'):
                self._insert_detail_field("Módulo:", run['module_type'])

            # Seção: Parâmetros de Simulação
            config = run.get('config', {})
            _PARAM_LABELS = {
                'pmv_comfort_bound': "Banda de conforto PMV",
                'pmv_upperbound': "Limite sup. PMV",
                'pmv_lowerbound': "Limite inf. PMV",
                'adaptative_bound': "Margem adaptativa (°C)",
                'met': "Taxa metabólica (met)",
                'met_as_watts': "Metabólico (W)",
                'wme': "Trabalho externo (W/m²)",
                'clo_min': "Clo mínimo",
                'clo_max': "Clo máximo",
                'clo_delta': "Variação do Clo",
                'clo_priority': "Prioridade do vestuário",
                'temp_ac_min': "Temp. mín. AC (°C)",
                'temp_ac_max': "Temp. máx. AC (°C)",
                'co2_limit': "Limite de CO₂ (ppm)",
                'max_vel': "Vel. máx. ventilador (m/s)",
                'air_speed_delta': "Variação vel. ar (m/s)",
                'temp_open_window_bound': "Margem abertura janela (°C)",
            }

            known_params = []
            for key, label in _PARAM_LABELS.items():
                if key in config:
                    val = config[key]
                    if isinstance(val, float):
                        val_str = f"{val:.2f}".rstrip("0").rstrip(".")
                    else:
                        val_str = str(val)
                    known_params.append((label, val_str))

            if known_params:
                self.detail_text.insert("end", "\nPARÂMETROS DE CONFORTO E OPERAÇÃO\n", "section")
                for label, val in known_params:
                    self._insert_detail_field(f"{label}:", val)

            self.detail_text.configure(state="disabled")

        elif runs:
            self.kpi_energy_val.configure(text="—")
            self.kpi_discomfort_val.configure(text="—")
            self.detail_text.configure(state="normal")
            self.detail_text.delete("1.0", "end")
            self.detail_text.insert("end", f"{len(runs)} execuções selecionadas\n", "title")
            self.detail_text.insert("end", "ITENS SELECIONADOS\n", "section")
            for run in runs:
                self.detail_text.insert("end", f"•  {run['run']} ", "bullet")
                self.detail_text.insert("end", f"({run['status']})\n", "help")
            self.detail_text.insert("end", "\nClique em 'Comparar selecionadas' abaixo para abrir a análise comparativa completa.\n", "help")
            self.detail_text.configure(state="disabled")
        else:
            self._render_detail_empty()

    @staticmethod
    def _period_text(run: dict) -> str:
        config = run.get("config", {})
        return (config.get("run_period") or config.get("period")
                or config.get("start_date") or "consulte o IDF")

    @staticmethod
    def _metric_text(run: dict, column: str, suffix: str = "") -> str:
        """Resumo leve: a listagem não abre planilhas grandes só por seleção."""
        value = run.get("summary", {}).get(column)
        if value is None:
            return "disponível nos detalhes" if run.get("status") == "pronta" else "sem estatísticas"
        return f"{value} {suffix}".strip()

    def _summary_for(self, run: dict) -> dict:
        """Agregados do Excel sob demanda, só para a execução escolhida."""
        path = run["path"]
        if path in self._summary_cache:
            return self._summary_cache[path]
        if run.get("status") != "pronta":
            return {}
        try:
            import pandas
            stats = pandas.read_excel(os.path.join(path, "ESTATISTICAS.xlsx"),
                                      usecols=lambda col: col in (
                                          "Energia total (kWh)", "Desconforto"))
            summary = {}
            if "Energia total (kWh)" in stats:
                summary["Energia total (kWh)"] = (
                    f"{stats['Energia total (kWh)'].sum():.2f}".replace(".", ","))
            if "Desconforto" in stats:
                summary["Desconforto"] = (
                    f"{stats['Desconforto'].mean() * 100:.1f}%".replace(".", ","))
        except Exception:
            summary = {}
        self._summary_cache[path] = summary
        return summary

    def _insert_detail_field(self, label: str, value: str):
        """Insere um par chave-valor formatado no Text widget com tabs alinhadas."""
        self.detail_text.insert("end", f"{label:<32}", "param_label")
        self.detail_text.insert("end", f" {value}\n", "param_val")

    def _render_detail_empty(self):
        self._update_button_states(0)
        if hasattr(self, "kpi_energy_val"):
            self.kpi_energy_val.configure(text="—")
        if hasattr(self, "kpi_discomfort_val"):
            self.kpi_discomfort_val.configure(text="—")
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", "Selecione uma execução na lista para visualizar seus indicadores, parâmetros e ações.", "help")
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

    def _ask_assistant(self):
        """Conversa com as execuções selecionadas; sem seleção, com todas."""
        if self.callback:
            self.callback.on_ask_assistant(self._selected_runs(), self.outputs_path.get())

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
        selected = self._selected_runs()
        if not selected:
            toast(self, "Escolha uma execução na lista.", "warn")
            return
        runs = [run for run in selected
                if run['status'] in ('desatualizada', 'sem estatísticas', 'sem planilhas')]
        if not runs:
            toast(self, "As execuções escolhidas já têm estatísticas atualizadas.",
                  "info")
            return

        self._busy = True
        status_msg = (f"Regerando estatísticas de {len(runs)} "
                      f"{'execução' if len(runs) == 1 else 'execuções'}. "
                      "Isso lê todas as planilhas por zona e leva minutos.")
        self._set_status(status_msg)

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
            if len(failed) == len(errors):
                toast(self,
                      f"{len(failed)} {'execução falhou' if len(failed) == 1 else 'execuções falharam'} ao regerar:\n{detail}",
                      "error", timeout=10000)
            else:
                succeeded = len(errors) - len(failed)
                succ_text = f"{succeeded} {'execução regerada' if succeeded == 1 else 'execuções regeradas'}"
                fail_text = f"{len(failed)} {'falhou' if len(failed) == 1 else 'falharam'}"
                toast(self, f"{succ_text}, mas {fail_text}:\n{detail}",
                      "error", timeout=10000)
        else:
            count = len(errors)
            toast(self, f"{count} {'execução regerada' if count == 1 else 'execuções regeradas'}.", "ok")
