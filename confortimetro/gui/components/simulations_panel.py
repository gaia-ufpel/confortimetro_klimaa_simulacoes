"""Listagem das simulações já executadas."""

import datetime
import os
import queue
import re
import sqlite3
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

from confortimetro.config import ADAPTATIVE2PORCENT
from confortimetro.drive import sync as drive_sync
from confortimetro.results import database
from confortimetro.results.compare import export_runs_zip, list_runs, recompute_runs

from ..theme import COLORS, FONTS, SPACE, Card, RoundedButton, toast
from .drive_panel import in_background
from .simulation_config_panel import MODULE_LABELS

# Colunas da listagem: (id, título, largura).
_LIST_COLUMNS = [
    ("run", "Execução", 210),
    ("module_type", "Módulo", 150),
    ("idf", "IDF", 140),
    ("epw", "Clima", 140),
    ("rooms", "Zonas", 55),
    ("status", "Estatísticas", 115),
    ("modificado", "Modificado", 115),
    ("drive", "Drive", 95),
]

_DRIVE_TEXT = {
    drive_sync.SYNCED: "sincronizado",
    drive_sync.SENDING: "enviando…",
    drive_sync.PENDING: "pendente",
    drive_sync.ERROR: "erro",
}

_STATUS_TEXT = {
    'pronta': 'pronta',
    'desatualizada': 'desatualizada',
    'sem estatísticas': 'sem estatísticas',
    'sem planilhas': 'sem planilhas',
    'interrompida': 'Interrompida',
    'falhou': 'Falhou',
}

# Nome criado sozinho (data e hora): não diz nada, então o IDF o substitui.
_AUTO_NAME = re.compile(r"^\d{8}_\d{4}(_\d+)?$")

# Módulo em português, igual ao do editor (só o que vem antes do parêntese).
_MODULE_NAMES = {module.value: label.split(" (")[0]
                 for module, label in MODULE_LABELS.items()}


def _display(run: dict) -> dict:
    """Nome, IDF de origem e módulo como a listagem os mostra."""
    config = run.get('config') or {}
    idf = os.path.basename(config.get('source_idf_path') or '') or run['idf']
    name = config.get('nome') or config.get('rotulo') or config.get('label')
    if not name:
        name = run['run']
        if _AUTO_NAME.match(name) and idf:
            # Hora de início, tirada do nome da pasta: a mesma que a comparação
            # mostra, e única (a de modificação mudava ao regerar e repetia).
            date, time, *suffix = name.split("_")
            name = (f"{os.path.splitext(idf)[0]} · {date[6:8]}/{date[4:6]} "
                    f"{time[:2]}:{time[2:]}" + (f" ({suffix[0]})" if suffix else ""))
    module = run['module_type']
    return {'name': name, 'idf': idf or "—",
            'module': _MODULE_NAMES.get(module, module) or "—"}


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

        # Barra inferior contextual de Comparação
        self.compare_bar = ttk.Frame(list_card.body, style="Surface.TFrame")
        self.compare_bar.pack(side="bottom", fill="x", pady=(SPACE[3], 0))
        self.compare_info_var = tk.StringVar(
            value="Selecione 2 ou mais execuções para comparar")
        ttk.Label(self.compare_bar, textvariable=self.compare_info_var,
                  style="Caption.TLabel").pack(side="left", padx=(SPACE[1], 0))

        self.compare_btn = RoundedButton(
            self.compare_bar, text="Comparar selecionadas", variant="primary",
            icon="compare", command=self._compare)
        self.compare_btn.pack(side="right")
        self.compare_btn.configure(state="disabled")

        # Container da Treeview com barras de rolagem
        tree_container = ttk.Frame(list_card.body, style="Surface.TFrame")
        tree_container.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            tree_container, style="Modern.Treeview", selectmode="extended",
            columns=[column for column, _, _ in _LIST_COLUMNS], show="headings",
            height=4)
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
        self.tree.bind("<Return>", lambda _event: self._open_details())
        self.tree.bind("<KP_Enter>", lambda _event: self._open_details())
        self.tree.bind("<FocusIn>", self._on_tree_focus)
        # Seleção múltipla sem mouse: o Treeview só a oferece com Shift/Ctrl+clique.
        self.tree.bind("<Shift-Up>", lambda _event: self._extend_selection(-1))
        self.tree.bind("<Shift-Down>", lambda _event: self._extend_selection(1))
        self.tree.bind("<Control-space>", self._toggle_focused)
        self.tree.bind("<Control-a>", self._select_all)
        self.tree.bind("<Control-A>", self._select_all)

        self.tree.tag_configure("incompleta", foreground=COLORS["text_mute"])
        self.tree.tag_configure("executando", foreground=COLORS["primary"])

        # --- Detalhes (Direita) ---
        detail_card = Card(panes, "Detalhes")
        panes.add(detail_card, weight=2)

        # Mini-toolbar contextual de ações da simulação
        self.actions_bar = ttk.Frame(detail_card.body, style="Surface.TFrame")
        self.actions_bar.pack(fill="x", pady=(0, SPACE[3]))

        self.btn_details = RoundedButton(
            self.actions_bar, text="", variant="primary", icon="details",
            tooltip="Ver detalhes", command=self._open_details)
        self.btn_details.pack(side="left")

        self.btn_duplicate = RoundedButton(
            self.actions_bar, text="", variant="ghost", icon="duplicate",
            tooltip="Duplicar simulação", command=self._duplicate)
        self.btn_duplicate.pack(side="left", padx=(SPACE[2], 0))

        self.btn_open = RoundedButton(
            self.actions_bar, text="", variant="ghost", icon="open",
            tooltip="Abrir pasta no gerenciador de arquivos", command=self.open_selected_folder)
        self.btn_open.pack(side="left", padx=(SPACE[2], 0))

        self.btn_export = RoundedButton(
            self.actions_bar, text="", variant="ghost", icon="export",
            tooltip="Exportar resultados em ZIP", command=self.export_selected_zip)
        self.btn_export.pack(side="left", padx=(SPACE[2], 0))

        self.btn_assistant = RoundedButton(
            self.actions_bar, text="", variant="ghost", icon="bot",
            tooltip="Assistente de análise", command=self._ask_assistant)
        self.btn_assistant.pack(side="left", padx=(SPACE[2], 0))

        self.btn_share = RoundedButton(
            self.actions_bar, text="", variant="ghost", icon="share",
            tooltip="Compartilhar pelo Google Drive", command=self._share)
        self.btn_share.pack(side="left", padx=(SPACE[2], 0))

        # Indicadores Chave de Desempenho (KPI Cards)
        self.kpi_frame = ttk.Frame(detail_card.body, style="Surface.TFrame")
        self.kpi_frame.pack(fill="x", pady=(0, SPACE[3]))

        self.kpi_energy_card = tk.Frame(self.kpi_frame, bg=COLORS["surface_2"],
                                        highlightthickness=1,
                                        highlightbackground=COLORS["line"])
        self.kpi_energy_card.pack(side="left", fill="both", expand=True, padx=(0, SPACE[2]))
        # Caixa normal e anchor="w": em maiúsculas centralizadas o card estreito
        # (125%) cortava as duas pontas ("ESCONFORT").
        tk.Label(self.kpi_energy_card, text="Consumo total", bg=COLORS["surface_2"],
                 fg=COLORS["text_mute"], font=FONTS["caption"], wraplength=130,
                 justify="left", anchor="w").pack(anchor="w", padx=SPACE[3], pady=(SPACE[2], 0))
        self.kpi_energy_val = tk.Label(
            self.kpi_energy_card, text="—", bg=COLORS["surface_2"],
            fg=COLORS["text"], font=FONTS["h2"], wraplength=130, justify="left",
            anchor="w")
        self.kpi_energy_val.pack(anchor="w", padx=SPACE[3], pady=(0, SPACE[2]))

        self.kpi_discomfort_card = tk.Frame(self.kpi_frame, bg=COLORS["surface_2"],
                                            highlightthickness=1,
                                            highlightbackground=COLORS["line"])
        self.kpi_discomfort_card.pack(side="left", fill="both", expand=True)
        tk.Label(self.kpi_discomfort_card, text="Desconforto", bg=COLORS["surface_2"],
                 fg=COLORS["text_mute"], font=FONTS["caption"], wraplength=130,
                 justify="left", anchor="w").pack(anchor="w", padx=SPACE[3], pady=(SPACE[2], 0))
        self.kpi_discomfort_val = tk.Label(
            self.kpi_discomfort_card, text="—", bg=COLORS["surface_2"],
            fg=COLORS["text"], font=FONTS["h2"], wraplength=130, justify="left",
            anchor="w")
        self.kpi_discomfort_val.pack(anchor="w", padx=SPACE[3], pady=(0, SPACE[2]))

        # Rodapé do painel de detalhes: Ação secundária para regerar estatísticas
        self.detail_footer = ttk.Frame(detail_card.body, style="Surface.TFrame")
        self.detail_footer.pack(side="bottom", fill="x", pady=(SPACE[2], 0))
        self.btn_recompute = RoundedButton(
            self.detail_footer, text="Regerar estatísticas", variant="ghost", icon="recompute",
            command=self.recompute_selected)
        self.btn_recompute.pack(side="right")

        # Texto detalhado com parâmetros e configurações formatados
        detail_text_frame = ttk.Frame(detail_card.body, style="Surface.TFrame")
        detail_text_frame.pack(fill="both", expand=True)

        self.detail_text = tk.Text(
            detail_text_frame, height=4, width=42, wrap="word", state="disabled",
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
        drive_state = drive_sync.load_state()
        for run in rows:
            running = run['path'] in self._running
            if not running and database.is_interrupted(run):
                run['status'] = 'interrompida'
            elif not running and database.is_failed(run):
                run['status'] = 'falhou'
            shown = _display(run)
            status = 'em simulação' if running else run['status']
            tags = ("executando",) if running else (
                () if run['status'] == 'pronta' else ("incompleta",))
            self.tree.insert(
                "", "end", iid=run['path'],
                values=(shown['name'], shown['module'], shown['idf'],
                        run['epw'] or "—", len(run['rooms_disponiveis']) or "—",
                        _STATUS_TEXT.get(status, status),
                        run['modificado'].strftime("%d/%m/%Y %H:%M"),
                        self._drive_text(run, drive_state)),
                tags=tags)

        ready = sum(1 for run in self._runs if run['status'] == 'pronta')
        total = len(rows)
        message = (f"{total} {'execução' if total == 1 else 'execuções'}, "
                   f"{ready} com estatísticas completas")
        if ingested:
            message += f". {ingested} ingeridas no banco agora"
        self._set_status(message)

    def _extend_selection(self, step):
        """Shift+seta: move o foco e acrescenta a linha à seleção."""
        current = self.tree.focus()
        target = self.tree.next(current) if step > 0 else self.tree.prev(current)
        if current and target:
            self.tree.selection_add(current, target)
            self.tree.focus(target)
            self.tree.see(target)
        return "break"

    def _toggle_focused(self, _event=None):
        """Ctrl+Espaço: põe ou tira da seleção a linha com foco."""
        item = self.tree.focus()
        if item:
            self.tree.selection_toggle(item)
        return "break"

    def _select_all(self, _event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _on_tree_focus(self, _event=None):
        """Com o foco na lista, as setas já têm de onde partir."""
        if not self.tree.focus():
            first = self.tree.get_children()
            if first:
                self.tree.focus(first[0])
                if not self.tree.selection():
                    self.tree.selection_set(first[0])

    @staticmethod
    def _drive_text(run: dict, state: dict) -> str:
        if not drive_sync.is_connected(state):
            return "—"
        return _DRIVE_TEXT.get(drive_sync.run_status(run['run'], state), "—")

    def update_drive_status(self):
        """Só a coluna Drive: o envio muda o status sem precisar reler a pasta."""
        state = drive_sync.load_state()
        runs = {run['path']: run for run in self._runs}
        for item in self.tree.get_children():
            if item in runs and item not in self._running:
                self.tree.set(item, "drive", self._drive_text(runs[item], state))

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
        self.btn_new_run.configure(text="Ver em andamento", icon="running")
        self.refresh()

    def clear_running(self, path: str):
        """Execução terminou: sai do estado 'em simulação'."""
        if self._running.pop(path, None) is not None:
            if not self._running:
                self.btn_new_run.configure(text="Nova execução", icon="new")
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
        all_runs = list(self._running.values()) + [r for r in self._runs if r['path'] not in self._running]
        return [run for run in all_runs if run['path'] in selected]

    def _update_button_states(self, selected_count: int, is_running_selected: bool = False):
        """Habilita ou desabilita as ações contextuais conforme a seleção."""
        item_state = "normal" if selected_count >= 1 else "disabled"
        for btn in (self.btn_details, self.btn_open, self.btn_assistant):
            btn.configure(state=item_state)

        # Execução ainda em andamento não pode ser duplicada nem ter estatísticas regeradas
        can_operate = item_state if not is_running_selected else "disabled"
        self.btn_duplicate.configure(state=can_operate)
        self.btn_export.configure(state=can_operate)
        self.btn_share.configure(state=can_operate if selected_count == 1 else "disabled")
        self.btn_recompute.configure(state=can_operate)

        if is_running_selected and selected_count == 1:
            self.btn_details.configure(tooltip="Ver simulação em andamento", icon="running")
        else:
            self.btn_details.configure(tooltip="Ver detalhes", icon="details")

        if selected_count >= 2:
            self.compare_btn.configure(state="normal" if not is_running_selected else "disabled")
            if is_running_selected:
                self.compare_info_var.set("Simulação em andamento não pode ser comparada")
            else:
                self.compare_info_var.set(f"{selected_count} execuções selecionadas para comparação")
        elif selected_count == 1:
            self.compare_btn.configure(state="disabled")
            if is_running_selected:
                self.compare_info_var.set("Simulação em andamento — clique em Ver em andamento para acompanhar")
            else:
                self.compare_info_var.set("Selecione mais uma execução (Ctrl+Clique) para comparar")
        else:
            self.compare_btn.configure(state="disabled")
            self.compare_info_var.set("Selecione 2 ou mais execuções para comparar")

    def _on_select(self, _event=None):
        runs = self._selected_runs()
        is_running_selected = any(r['path'] in self._running for r in runs)
        self._update_button_states(len(runs), is_running_selected=is_running_selected)

        if len(runs) == 1:
            run = runs[0]
            is_running = run['path'] in self._running
            run["summary"] = self._summary_for(run)

            # Atualizar os cards de KPI
            if is_running:
                consumo_val = "em andamento"
                desconf_val = "em andamento"
            else:
                consumo_val = self._metric_text(run, 'Energia total (kWh)', 'kWh')
                desconf_val = self._metric_text(run, 'Desconforto')
            self.kpi_energy_val.configure(text=consumo_val)
            self.kpi_discomfort_val.configure(text=desconf_val)

            # Renderização estruturada e amigável dos detalhes
            self.detail_text.configure(state="normal")
            self.detail_text.delete("1.0", "end")

            # Cabeçalho da execução
            self.detail_text.insert("end", f"{_display(run)['name']}\n", "title")

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
            if _display(run)['idf'] != "—":
                self._insert_detail_field("Modelo (IDF):", _display(run)['idf'])
            if run.get('epw'):
                self._insert_detail_field("Clima (EPW):", run['epw'])
            if run.get('module_type'):
                self._insert_detail_field("Módulo:", _display(run)['module'])

            # Seção: Parâmetros de Simulação
            config = run.get('config', {})
            _PARAM_LABELS = {
                'pmv_comfort_bound': "Banda de conforto PMV",
                'pmv_upperbound': "Limite sup. PMV",
                'pmv_lowerbound': "Limite inf. PMV",
                'adaptative_bound': "Aceitação adaptativa",
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
                    if key == 'adaptative_bound' and val in ADAPTATIVE2PORCENT:
                        val_str = f"{ADAPTATIVE2PORCENT[val]} de aceitação"
                    elif isinstance(val, float):
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
        text = config.get("run_period") or config.get("period") or config.get("start_date")
        if text:
            return text
        try:
            from confortimetro.idf import read_run_period
            idf = os.path.join(run.get("path", ""), "modelo.idf")
            start, end = read_run_period(idf)
            return f"{start:%d/%m/%Y} a {(end - datetime.timedelta(days=1)):%d/%m/%Y}"
        except Exception:
            return "consulte o IDF"

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
                                          "Energia total (kWh)", "Desconforto (%)", "Desconforto"))
            summary = {}
            if "Energia total (kWh)" in stats:
                summary["Energia total (kWh)"] = (
                    f"{stats['Energia total (kWh)'].sum():.2f}".replace(".", ","))
            desc_col = "Desconforto (%)" if "Desconforto (%)" in stats else ("Desconforto" if "Desconforto" in stats else None)
            if desc_col:
                summary["Desconforto"] = (
                    f"{stats[desc_col].mean() * 100:.1f}%".replace(".", ","))
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

    def _share(self):
        run = self._selected_run()
        if run and self.callback:
            self.callback.on_share_run(run)

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
        if not os.path.exists(path):
            toast(self, "A pasta desta execução ainda não foi criada no disco.", "info")
            return
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])

    def export_selected_zip(self):
        """Compacta as pastas das execuções selecionadas num único zip."""
        if self._busy:
            toast(self, "Aguarde a tarefa em andamento terminar.", "info")
            return
        runs = [run for run in self._selected_runs()
                if run['path'] not in self._running and os.path.isdir(run['path'])]
        if not runs:
            toast(self, "Escolha uma execução concluída para exportar.", "warn")
            return
        name = (os.path.basename(os.path.normpath(runs[0]['path']))
                if len(runs) == 1 else "execucoes")
        zip_path = filedialog.asksaveasfilename(
            parent=self, title="Exportar resultados", defaultextension=".zip",
            initialfile=f"{name}.zip", filetypes=[("ZIP", "*.zip")])
        if not zip_path:
            return

        self._busy = True
        self._set_status(f"Compactando {len(runs)} "
                         f"{'execução' if len(runs) == 1 else 'execuções'}. "
                         "Uma simulação anual passa de 1 GB e leva minutos.")

        def work():
            try:
                export_runs_zip([run['path'] for run in runs], zip_path)
                error = None
            except OSError as exc:
                error = str(exc)
            self.after(0, lambda: self._export_done(zip_path, error))

        threading.Thread(target=work, daemon=True).start()

    def _export_done(self, zip_path: str, error):
        self._busy = False
        if error:
            self._set_status("")
            toast(self, f"Falha ao exportar: {error}", "error", timeout=10000)
        else:
            self._set_status(f"Resultados exportados para {zip_path}")
            toast(self, "Resultados exportados.", "ok")

    def recompute_selected(self):
        """Regera ESTATISTICAS.xlsx das execuções selecionadas, em segundo plano."""
        if self._busy:
            toast(self, "Aguarde a tarefa em andamento terminar.", "info")
            return
        selected = self._selected_runs()
        if not selected:
            toast(self, "Escolha uma execução na lista.", "warn")
            return
        if all(run['status'] == 'interrompida' for run in selected):
            toast(self, "Execução interrompida: não há resultados para regerar.",
                  "info")
            return
        runs = [run for run in selected
                if run['status'] in ('desatualizada', 'sem estatísticas', 'sem planilhas',
                                     'falhou')]
        if not runs:
            toast(self, "As execuções escolhidas já têm estatísticas atualizadas.",
                  "info")
            return

        self._busy = True
        total = len(runs)
        finished = queue.Queue()
        started = time.monotonic()

        def tick():
            # Só a thread do Tk desenha; a do pool apenas empilha o progresso.
            count = finished.qsize()
            minutes = int((time.monotonic() - started) // 60)
            self._set_status(
                f"Regerando estatísticas: {count} de {total} "
                f"{'concluída' if count == 1 else 'concluídas'} · {minutes} min. "
                "Isso lê todas as planilhas por zona e leva minutos.")

        def done(errors, error):
            if error is not None:
                errors = {run['path']: f"{type(error).__name__}: {error}"
                          for run in runs}
            self._recompute_done(errors)

        tick()
        # Cada planilha por zona tem dezenas de milhares de linhas: fora da
        # thread a interface congelaria por minutos.
        in_background(self, lambda: recompute_runs(
            [run['path'] for run in runs],
            on_result=lambda path, error: finished.put(path)), done, tick)

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
