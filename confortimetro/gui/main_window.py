"""
Main window for the Confortimetro Klimaa application.
"""

import os
import subprocess
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox, filedialog
from queue import Queue
import copy
from typing import Optional

from confortimetro.config import SimulationConfig
from confortimetro.idf import (apply_equipment_fixes, plan_equipment_fixes,
                                read_zone_names, unwired_equipment,
                                write_idf_fields)
from confortimetro.paths import new_run_path, runs_root
from .components import (
    COMPARISON_HEADINGS,
    MACHINE_FIELDS,
    SIMULATION_FIELDS,
    PathConfigPanel,
    SimulationConfigPanel,
    IDFEditorPanel,
    ResultsPanel,
    ControlPanel,
    SimulationsPanel,
    ComparisonPanel,
    TimeSeriesPanel,
    AssistantPanel,
    AssistantSettings,
)
from .theme import (
    COLORS,
    FONTS,
    SPACE,
    BottomSheet,
    Card,
    RoundedButton,
    apply_theme,
    ask_choices,
    icon,
    toast,
)


class MainWindow(tk.Tk):
    """Main application window."""
    
    def __init__(self, config_path: str = "examples/config.json"):
        super().__init__()
        
        self.config_path = config_path
        self.configs: Optional[SimulationConfig] = None
        self.simulation_thread: Optional[threading.Thread] = None
        # A simulação em andamento, para poder pedir o cancelamento a ela.
        self.simulation = None
        self.simulation_queue: Optional[Queue] = None
        self._simulation_error: Optional[str] = None
        # A listagem só é relida quando alguma execução termina.
        self._runs_dirty = False
        self._detail_run: Optional[dict] = None
        # `after` da transição de página em andamento, se houver.
        
        self._setup_window()
        apply_theme(self)
        self._build_ui()
        self._load_configuration()
    
    def _setup_window(self):
        """Setup the main window properties."""
        self.title("Confortímetro Klimaa — Simulações EnergyPlus")
        self.geometry("1200x900")
        self.minsize(800, 600)
        self.configure(background=COLORS["bg"])
        self._set_icon()
        self.center_window()

    def _set_icon(self):
        """Ícone da janela. Vários tamanhos porque o Tk reduz imagem sem
        suavizar: entregar um PNG grande só deixa o ícone da barra serrilhado.
        Cada tamanho é rasterizado do `logo.svg`; o gerenciador de janela pega
        o mais próximo. Falha silenciosa: nem todo WM suporta `iconphoto`."""
        assets = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "assets")
        try:
            self._icons = [
                tk.PhotoImage(file=os.path.join(assets, f"logo-{size}.png"))
                for size in (32, 48, 64, 128, 256, 512)
            ]
            self.iconphoto(True, *self._icons)
        except tk.TclError:
            pass

    def _build_ui(self):
        """Uma página por vez no mesmo host: execuções, detalhes, execução e
        configurações. Todas ficam montadas; navegar é `place`.
        """
        from tkinter import ttk

        container = ttk.Frame(self, style="Main.TFrame")
        container.pack(fill="both", expand=True, padx=SPACE[5], pady=SPACE[5])

        header = ttk.Frame(container, style="Main.TFrame")
        header.pack(fill="x", pady=(0, SPACE[3]))
        # `background` explícito: sobre o fundo da janela o estilo não basta
        # (ver o tk_setPalette em theme.apply_theme).
        ttk.Label(header, text="Confortímetro Klimaa", style="H1.TLabel",
                  background=COLORS["bg"]).pack(anchor="w")
        self.subtitle_label = ttk.Label(
            header, text="Simulações personalizadas com EnergyPlus",
            style="Sub.TLabel", background=COLORS["bg"])
        self.subtitle_label.pack(anchor="w", pady=(SPACE[1], 0))

        self.page_host = ttk.Frame(container, style="Main.TFrame")
        self.page_host.pack(fill="both", expand=True)

        footer = ttk.Frame(container, style="Main.TFrame")
        footer.pack(pady=(SPACE[3], 0))
        ttk.Label(footer, text="Feito por ",
                  style="Sub.TLabel", background=COLORS["bg"]).pack(side="left")
        link = ttk.Label(footer, text="glbessa", style="Sub.TLabel",
                         background=COLORS["bg"], cursor="hand2")
        link.configure(foreground=COLORS["accent"], font=FONTS["caption"] + ("underline",))
        link.pack(side="left")
        link.bind("<Button-1>",
                  lambda _e: webbrowser.open("https://github.com/glbessa"))

        self._pages = {
            "runs": self._build_runs_page(),
            "compare": self._build_compare_page(),
            "detail": self._build_detail_page(),
            "editor": self._build_editor_page(),
            "settings": self._build_settings_page(),
            "assistant": self._build_assistant_page(),
        }
        self._current_page = None
        self.show_page("runs")

    # ----------------------------------------------------------- navegação

    _PAGE_SUBTITLES = {
        "runs": "Execuções realizadas e comparação de resultados",
        "compare": "Comparação entre execuções",
        "detail": "Detalhes da execução",
        "editor": "Nova execução com EnergyPlus",
        "settings": "Configurações desta máquina",
        "assistant": "Converse sobre os resultados das execuções",
    }

    def show_page(self, name: str):
        """Mostra uma página trazendo-a para a frente da pilha."""
        if self._current_page == name:
            return

        self._current_page = name
        self.subtitle_label.configure(text=self._PAGE_SUBTITLES[name])

        # A listagem só relê a pasta quando alguma execução terminou: o sync
        # do banco custa segundos e não vale a cada ida e volta.
        if name == "runs" and self._runs_dirty:
            self._runs_dirty = False
            self.simulations_panel.refresh()

        # Troca seca: a anterior sai, a nova ocupa o host. Animar o deslize
        # repintava a página inteira a cada quadro e o Tk, sem double
        # buffering, pisca.
        for key, page in self._pages.items():
            if key == name:
                page.place(relx=0, rely=0, relwidth=1, relheight=1)
            else:
                page.place_forget()

    def _page_nav(self, page, title: str, back_to: str = None):
        """Cabeçalho da página: título e, quando faz sentido, o botão voltar."""
        from tkinter import ttk

        row = ttk.Frame(page, style="Main.TFrame")
        row.pack(fill="x", pady=(0, SPACE[3]))
        if back_to:
            RoundedButton(row, text="Voltar", variant="bar", icon="back",
                          command=lambda: self.show_page(back_to)).pack(side="left",
                                                                        padx=(0, SPACE[3]))
        ttk.Label(row, text=title, style="H2.TLabel",
                  background=COLORS["bg"]).pack(side="left")
        return row

    # -------------------------------------------------------------- páginas

    def _build_runs_page(self):
        from tkinter import ttk

        page = ttk.Frame(self.page_host, style="Main.TFrame")
        nav = self._page_nav(page, "Execuções")
        RoundedButton(nav, text="Configurações", variant="bar", icon="settings",
                      command=lambda: self.show_page("settings")).pack(side="right")

        self.simulations_panel = SimulationsPanel(page, self._outputs_root(),
                                                  callback=self)
        self.simulations_panel.pack(fill="both", expand=True)
        return page

    def _build_compare_page(self):
        """Tabela e gráficos das execuções escolhidas na listagem."""
        from tkinter import ttk

        page = ttk.Frame(self.page_host, style="Main.TFrame")
        self._page_nav(page, "Comparação de resultados", back_to="runs")

        self.comparison_panel = ComparisonPanel(page)
        self.comparison_panel.pack(fill="both", expand=True)
        return page

    def _build_detail_page(self):
        """Configuração completa da execução selecionada, com as ações dela."""
        from tkinter import ttk

        page = ttk.Frame(self.page_host, style="Main.TFrame")
        self._page_nav(page, "Detalhes da execução", back_to="runs")

        # --- Ações ancoradas no rodapé ---
        actions = Card(page, pad=SPACE[3])
        actions.pack(side="bottom", fill="x", pady=(SPACE[3], 0))
        row = ttk.Frame(actions.body, style="Surface.TFrame")
        row.pack(fill="x")
        RoundedButton(row, text="Duplicar para nova execução", variant="primary", icon="duplicate",
                      command=lambda: self.on_duplicate_run(self._detail_run)).pack(
                          side="left")
        RoundedButton(row, text="Abrir pasta", variant="ghost", icon="open",
                       command=self._open_detail_folder).pack(side="left",
                                                              padx=(SPACE[2], 0))
        self.detail_recompute_button = RoundedButton(
            row, text="Regerar estatísticas", variant="ghost", icon="recompute",
            command=self._recompute_detail_stats)
        self.detail_recompute_button.pack(side="left", padx=(SPACE[2], 0))

        # --- Abas: o resumo de sempre e a série temporal timestep a timestep ---
        self.detail_tabs = ttk.Notebook(page, style="Section.TNotebook")
        self.detail_tabs.pack(fill="both", expand=True)
        summary = ttk.Frame(self.detail_tabs, style="Main.TFrame")
        series_tab = Card(self.detail_tabs, pad=SPACE[3])
        self.detail_tabs.add(summary, text="Resumo")
        self.detail_tabs.add(series_tab, text="Série temporal")
        self.timeseries_panel = TimeSeriesPanel(series_tab.body)
        self.timeseries_panel.pack(fill="both", expand=True)
        assistant_tab = Card(self.detail_tabs, pad=SPACE[3])
        self.detail_tabs.add(assistant_tab, text="Assistente")
        self.detail_assistant = AssistantPanel(assistant_tab.body, self._outputs_root)
        self.detail_assistant.pack(fill="both", expand=True)
        # A série só é lida com a aba visível: abrir os detalhes continua
        # tão rápido quanto antes.
        self.detail_tabs.bind("<<NotebookTabChanged>>", self._on_detail_tab_changed)

        # --- Resumo de consumo (KPI cards) ---
        kpi_card = Card(summary, pad=SPACE[3])
        kpi_card.pack(fill="x", pady=(0, SPACE[3]))
        kpi_row = ttk.Frame(kpi_card.body, style="Surface.TFrame")
        kpi_row.pack(fill="x")

        self.kpi_total_var = tk.StringVar(value="—")
        self.kpi_aquec_var = tk.StringVar(value="—")
        self.kpi_resfr_var = tk.StringVar(value="—")

        def _make_kpi(title: str, var: tk.StringVar, color: str, icon_name: str):
            f = ttk.Frame(kpi_row, style="Surface.TFrame")
            ic = icon(icon_name, 16, color, master=self)
            lbl_title = ttk.Label(f, text=" " + title, image=ic, compound="left",
                                  style="Caption.TLabel")
            lbl_title.image = ic
            lbl_title.pack(anchor="w")

            val_f = ttk.Frame(f, style="Surface.TFrame")
            val_f.pack(anchor="w", pady=(SPACE[1], 0))
            lbl_val = ttk.Label(val_f, textvariable=var, style="H1.TLabel",
                                background=COLORS["surface"])
            lbl_val.configure(foreground=color)
            lbl_val.pack(side="left")

            lbl_unit = ttk.Label(val_f, text=" kWh", style="Label.TLabel",
                                 background=COLORS["surface"])
            lbl_unit.configure(foreground=COLORS["text_mute"])
            lbl_unit.pack(side="left", anchor="s", pady=(0, 3))
            return f

        kpi1 = _make_kpi("Consumo Total", self.kpi_total_var, COLORS["primary"], "zap")
        kpi1.pack(side="left", padx=(SPACE[2], SPACE[5]))

        ttk.Separator(kpi_row, orient="vertical").pack(
            side="left", fill="y", padx=(0, SPACE[5]))

        kpi2 = _make_kpi("Aquecimento", self.kpi_aquec_var, COLORS["hot"], "flame")
        kpi2.pack(side="left", padx=(0, SPACE[5]))

        ttk.Separator(kpi_row, orient="vertical").pack(
            side="left", fill="y", padx=(0, SPACE[5]))

        kpi3 = _make_kpi("Resfriamento", self.kpi_resfr_var, "#2b6cb0", "snowflake")
        kpi3.pack(side="left", padx=(0, SPACE[5]))

        # --- Estatísticas por zona ---
        stats_card = Card(summary, "Estatísticas por zona")
        stats_card.pack(fill="x", pady=(0, SPACE[3]))
        self.detail_stats = ttk.Treeview(stats_card.body, style="Modern.Treeview",
                                         show="headings", height=4)
        stats_scroll = ttk.Scrollbar(stats_card.body, orient="horizontal",
                                     command=self.detail_stats.xview)
        self.detail_stats.configure(xscrollcommand=stats_scroll.set)
        stats_scroll.pack(side="bottom", fill="x")
        self.detail_stats.pack(fill="x")
        self.detail_stats.tag_configure("total", font=FONTS["label"])
        self.detail_empty_var = tk.StringVar(
            value="Escolha uma execução na listagem para ver os resultados.")
        self.detail_empty = ttk.Label(summary, textvariable=self.detail_empty_var,
                                      style="Caption.TLabel", justify="left")

        # --- Configuração da execução ---
        card = Card(summary, "Configuração da execução")
        card.pack(fill="both", expand=True)
        self.detail_text = tk.Text(
            card.body, wrap="none", state="disabled", font=FONTS["mono"],
            background=COLORS["surface"], foreground=COLORS["text"],
            relief="flat", borderwidth=0, highlightthickness=1,
            highlightbackground=COLORS["line"], padx=SPACE[3], pady=SPACE[3])
        detail_scroll = ttk.Scrollbar(card.body, orient="vertical",
                                      command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        detail_scroll.pack(side="right", fill="y")
        self.detail_text.pack(side="left", fill="both", expand=True)

        return page

    def _build_editor_page(self):
        """Topbar de execução, parâmetros no meio, log num bottom sheet."""
        from tkinter import ttk

        page = ttk.Frame(self.page_host, style="Main.TFrame")
        self._page_nav(page, "Execução", back_to="runs")

        # --- Topbar: executar, salvar/carregar e estado da simulação ---
        topbar = Card(page, pad=SPACE[3])
        topbar.pack(fill="x", pady=(0, SPACE[4]))
        self.control_panel = ControlPanel(topbar.body, callback=self)
        self.control_panel.pack(fill="x")

        # --- Log: painel inferior colapsável (ancorado no rodapé) ---
        self.log_sheet = BottomSheet(page, "Log de execução")
        self.log_sheet.pack(side="bottom", fill="x", pady=(SPACE[4], 0))
        self.results_panel = ResultsPanel(self.log_sheet.body, callback=self)
        self.results_panel.pack(fill="both", expand=True)

        # --- Parâmetros: as abas já são o card, sem moldura em volta ---
        self.simulation_panel = SimulationConfigPanel(page, callback=self)
        self.simulation_panel.pack(side="top", fill="both", expand=True)
        # Os caminhos entram como primeira aba: o IDF e o EPW são a entrada da
        # simulação, não mais um bloco solto acima dos parâmetros.
        self.path_panel = PathConfigPanel(self.simulation_panel.notebook,
                                           callback=self,
                                           fields=SIMULATION_FIELDS,
                                           padding=SPACE[3])
        self.simulation_panel.insert_tab(0, self.path_panel, "Arquivos")
        self._build_idf_editor_tabs()
        return page

    def _build_idf_editor_tabs(self):
        """Inclui Período e Ocupação diretamente nas abas da execução."""
        self.idf_editor_panel = IDFEditorPanel(self.simulation_panel.notebook,
                                                on_save=self.on_save_idf_copy)
        self.simulation_panel.insert_tab(1, self.idf_editor_panel.period_tab,
                                          "Período", select=False)
        self.simulation_panel.insert_tab(2, self.idf_editor_panel.occupation_tab,
                                          "Ocupação", select=False)
        self.simulation_panel.notebook.bind(
            "<<NotebookTabChanged>>", self._load_idf_editor_for_selected_tab,
            add="+")

    def _load_idf_editor_for_selected_tab(self, _event=None):
        """Carrega o IDF ao abrir Período ou Ocupação diretamente.

        As duas abas ficam sempre disponíveis na execução. Sem esse
        carregamento sob demanda, elas só recebiam conteúdo ao usar o atalho
        ``Editar IDF`` do painel Arquivos.
        """
        selected = self.simulation_panel.notebook.select()
        editor_tabs = (str(self.idf_editor_panel.period_tab),
                       str(self.idf_editor_panel.occupation_tab))
        if selected not in editor_tabs:
            return

        idf_path = self.path_panel.get_idf_path().strip()
        if (idf_path and os.path.isfile(idf_path)
                and idf_path != self.idf_editor_panel.idf_path):
            self.idf_editor_panel.load(idf_path)

    def _build_settings_page(self):
        """Os caminhos que são da máquina, não da simulação."""
        from tkinter import ttk

        page = ttk.Frame(self.page_host, style="Main.TFrame")
        self._page_nav(page, "Configurações", back_to="runs")

        card = Card(page, "Configurações da máquina")
        card.pack(fill="x")
        self.settings_panel = PathConfigPanel(card.body, callback=self,
                                              fields=MACHINE_FIELDS)
        self.settings_panel.pack(fill="x")
        ttk.Label(card.body, text="Valem para todas as simulações desta "
                                  "máquina e são salvos junto da configuração.",
                  style="Caption.TLabel").pack(anchor="w", pady=(SPACE[3], 0))

        assistant_card = Card(page, "Assistente de análise")
        assistant_card.pack(fill="x", pady=(SPACE[3], 0))
        self.assistant_settings = AssistantSettings(assistant_card.body)
        self.assistant_settings.pack(fill="x")
        return page

    def _build_assistant_page(self):
        """Chat sobre as execuções escolhidas na listagem."""
        from tkinter import ttk

        page = ttk.Frame(self.page_host, style="Main.TFrame")
        self._page_nav(page, "Assistente de análise", back_to="runs")
        card = Card(page, pad=SPACE[3])
        card.pack(fill="both", expand=True)
        self.assistant_panel = AssistantPanel(card.body, self._outputs_root)
        self.assistant_panel.pack(fill="both", expand=True)
        return page

    def _outputs_root(self) -> str:
        """Pasta que a listagem lê: a raiz das execuções, das configurações."""
        outputs_root = (self.settings_panel.get_output_path()
                        if hasattr(self, "settings_panel") else "")
        if not outputs_root and self.configs:
            outputs_root = self.configs.runs_root_path or ""

        if not outputs_root or not os.path.isdir(outputs_root):
            outputs_root = runs_root(create=True)
        return outputs_root

    def center_window(self):
        """Center the window on the screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def _load_configuration(self):
        """Load configuration from file."""
        try:
            if not os.path.exists(self.config_path):
                # Create default configuration
                self.configs = SimulationConfig()
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                self.configs.to_json(self.config_path)
                self.results_panel.append_info("Configuração padrão criada.")
            else:
                self.configs = SimulationConfig.from_json(self.config_path)
                self.results_panel.append_info("Configuração carregada com sucesso.")
            
            # Update UI with loaded configuration
            self._update_ui_from_config()
            self.simulations_panel.set_outputs_path(self._outputs_root())
            
        except Exception as e:
            self.results_panel.append_error(f"Erro ao carregar configuração: {str(e)}")
            self.configs = SimulationConfig()  # Fallback to default
    
    def _update_ui_from_config(self):
        """Update UI components with configuration data."""
        if not self.configs:
            return
        
        # Update path panel
        self.path_panel.set_idf_path(self.configs.idf_path)
        self.settings_panel.set_output_path(
            self.configs.runs_root_path or runs_root())
        self.path_panel.set_epw_path(self.configs.epw_path)
        self.settings_panel.set_energy_path(self.configs.energy_path)
        
        self._refresh_room_options(self.configs.idf_path)
        if os.path.isfile(self.configs.idf_path):
            self.idf_editor_panel.load(self.configs.idf_path)

        # Update simulation panel
        config_dict = {
            'pmv_lowerbound': self.configs.pmv_lowerbound,
            'pmv_upperbound': self.configs.pmv_upperbound,
            'max_vel': self.configs.max_vel,
            'adaptative_bound': self.configs.adaptative_bound,
            'temp_ac_min': self.configs.temp_ac_min,
            'temp_ac_max': self.configs.temp_ac_max,
            'met': self.configs.met,
            'wme': self.configs.wme,
            'pmv_comfort_bound': self.configs.pmv_comfort_bound,
            'co2_limit': self.configs.co2_limit,
            'air_speed_delta': self.configs.air_speed_delta,
            'temp_open_window_bound': self.configs.temp_open_window_bound,
            'clo_min': self.configs.clo_min,
            'clo_max': self.configs.clo_max,
            'clo_delta': self.configs.clo_delta,
            'clo_priority': self.configs.clo_priority,
            'rooms': self.configs.rooms,
            'module_type': self.configs.module_type
        }
        self.simulation_panel.set_configuration(config_dict)
    
    def _update_config_from_ui(self):
        """Update configuration from UI components."""
        if not self.configs:
            self.configs = SimulationConfig()
        
        # Update from path panel
        self.configs.idf_path = self.path_panel.get_idf_path()
        self.configs.runs_root_path = self.settings_panel.get_output_path()
        self.configs.epw_path = self.path_panel.get_epw_path()
        self.configs.energy_path = self.settings_panel.get_energy_path()
        
        # Update from simulation panel
        sim_config = self.simulation_panel.get_configuration()
        if sim_config:  # Only update if we got valid configuration
            for key, value in sim_config.items():
                if hasattr(self.configs, key):
                    setattr(self.configs, key, value)
    
    def _save_configuration(self):
        """Save current configuration to file."""
        try:
            self._update_config_from_ui()
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            self.configs.to_json(self.config_path)
            self.results_panel.append_success("Configuração salva com sucesso.")
            
        except Exception as e:
            self.results_panel.append_error(f"Erro ao salvar configuração: {str(e)}")
            toast(self, f"Erro ao salvar configuração: {e}", "error")
    
    def _resolve_missing_equipment(self) -> list:
        """Faltas de equipamento que sobram depois de oferecer a correção.

        Quando dá para copiar o equipamento de outra zona do próprio IDF, a
        interface pergunta e grava um modelo novo ao lado do original — o
        arquivo escolhido pelo usuário nunca é reescrito.
        """
        problems = unwired_equipment(self.configs.idf_path,
                                     self.configs.rooms or [],
                                     self.configs.module_type)
        if not problems:
            return []
        for problem in problems:
            self.results_panel.append_warning(problem)

        rooms = self.configs.rooms or []
        fixes, _ = plan_equipment_fixes(self.configs.idf_path, rooms,
                                        self.configs.module_type)
        if not fixes:
            return problems

        # Com mais de um sistema para copiar, quem escolhe é o usuário: o
        # ar-condicionado de cada zona pode ser um equipamento diferente.
        choices = {}
        for fix in fixes:
            if len(fix["templates"]) > 1:
                choices.setdefault(
                    fix["prefix"],
                    (f"Copiar o {fix['label']} de:",
                     [f"{source} ({kind})"
                      for kind, source in dict.fromkeys(fix["templates"])]))
        if choices:
            answer = ask_choices(
                self, "Incluir o equipamento que falta?",
                f"{len(fixes)} zona(s) sem o equipamento que o módulo "
                f"{self.configs.module_type} controla. O IDF escolhido não é "
                "alterado: as inclusões vão para um arquivo novo ao lado dele, "
                "que passa a ser o modelo desta simulação.\n\nDe qual zona "
                "copiar o equipamento?",
                {label: options for label, options in choices.values()},
                confirm="Incluir", cancel="Agora não")
            if answer is None:
                return problems
            template_rooms = {}
            for prefix, (label, _) in choices.items():
                template_rooms[prefix] = answer[label].split(" (")[0]
            fixes, _ = plan_equipment_fixes(self.configs.idf_path, rooms,
                                            self.configs.module_type,
                                            template_rooms)

        # O log leva o inventário completo: um IDF costuma ter mais de um
        # sistema de ar-condicionado, e o usuário precisa ver qual foi copiado
        # e que objetos entram no modelo por causa disso.
        for fix in fixes:
            self.results_panel.append_info(fix["description"])
            if fix.get("note"):
                self.results_panel.append_warning(fix["note"])
            for detail in fix.get("details", ()):
                self.results_panel.append_info(f"    {detail}")

        detail = "\n".join(f"• {fix['description']}" for fix in fixes[:6])
        rest = len(fixes) - 6
        if rest > 0:
            detail += f"\n• (e mais {rest} no log)"

        notes = list(dict.fromkeys(fix["note"] for fix in fixes if fix.get("note")))
        if notes:
            detail += "\n\n" + "\n".join(notes)

        created = {}
        for fix in fixes:
            for object_type, _ in fix["objects"]:
                created[object_type] = created.get(object_type, 0) + 1
        if created:
            summary = ", ".join(f"{count}× {object_type}"
                                for object_type, count in sorted(created.items()))
            detail += f"\n\nObjetos criados: {summary} (nomes no log)."

        # Confirmação final mesmo depois do seletor: só aqui a lista reflete
        # o molde escolhido.
        if not messagebox.askyesno(
                "Incluir o equipamento que falta?",
                f"{detail}\n\nO IDF escolhido não é alterado: as inclusões vão "
                "para um arquivo novo ao lado dele, que passa a ser o modelo "
                "desta simulação.\n\nIncluir?",
                icon="question", parent=self):
            return problems

        target = self._new_idf_name(self.configs.idf_path, "equipamentos")
        try:
            apply_equipment_fixes(self.configs.idf_path, target, fixes)
        except (OSError, IndexError) as error:
            toast(self, f"Não foi possível gravar o IDF: {error}", "error")
            return problems

        self.path_panel.set_idf_path(target)
        self.on_idf_path_changed(target)
        toast(self, f"Equipamento incluído em {os.path.basename(target)}.", "ok")
        return unwired_equipment(target, self.configs.rooms or [],
                                 self.configs.module_type)

    def _validate_configuration(self) -> bool:
        """Validate the current configuration."""
        if not self.configs:
            toast(self, "Configuração não carregada.", "error")
            return False
        
        # Check required paths
        if not os.path.exists(self.configs.idf_path):
            toast(self, "Arquivo IDF não encontrado.", "error")
            return False
        
        if not os.path.exists(self.configs.epw_path):
            toast(self, "Arquivo EPW não encontrado.", "error")
            return False
        
        if not os.path.exists(self.configs.energy_path):
            toast(self, "Pasta do EnergyPlus não existe.", "error")
            return False

        # Zona sem o equipamento do módulo simularia inteira decidindo no vazio;
        # a simulação também barra isso, mas o aviso aqui chega antes da espera.
        self.configs.ignore_missing_equipment = False
        problems = self._resolve_missing_equipment()
        if problems:
            head = "\n".join(problems[:3])
            rest = len(problems) - 3
            if rest > 0:
                head += f"\n(e mais {rest} no log)"
            # Confirmação bloqueante, e não toast: a simulação leva horas e
            # começaria com zonas decidindo no vazio.
            if not messagebox.askyesno(
                    "Equipamento faltando no IDF",
                    f"{head}\n\nEssas zonas vão simular sem o equipamento que o "
                    f"módulo {self.configs.module_type} controla.\n\n"
                    "Rodar mesmo assim?",
                    icon="warning", default="no", parent=self):
                toast(self, "Simulação cancelada: equipamento faltando no IDF.",
                      "error")
                return False
            self.configs.ignore_missing_equipment = True
            self.results_panel.append_warning(
                "Simulação iniciada ignorando o equipamento faltante.")

        return True
    
    def _run_simulation_thread(self, q: Queue):
        """Run simulation in a separate thread."""
        try:
            if self.configs is None:
                raise ValueError("Configuration not loaded")
            # Importado aqui, e não no topo: pythermalcomfort compila com numba
            # ao ser importado e custa ~12 s — a GUI abre sem ele.
            from confortimetro.simulation import Simulation

            self.simulation = Simulation(copy.deepcopy(self.configs))
            self.simulation.run(q)
        except Exception as e:
            self._simulation_error = str(e)
            q.put(f"Erro durante a simulação: {str(e)}\n")
    
    def _handle_simulation_message(self, message: str):
        """Mensagem da simulação: percentual vai para a barra, o resto, no log."""
        message = message.strip()
        if message.startswith("PROGRESS "):
            self.control_panel.set_progress(float(message.split()[1]))
            return
        lower = message.lower()
        if "erro" in lower or "error" in lower or message.startswith("Erro"):
            self.results_panel.append_error(message)
            self._simulation_error = message
            self.control_panel.set_status(message, "error")
            return
        self.results_panel.append_info(message)
        self.control_panel.set_status(message, "running")

    def _check_simulation_thread(self):
        """Check simulation thread status and update UI."""
        if self.simulation_thread and self.simulation_thread.is_alive():
            # Get messages from queue
            while not self.simulation_queue.empty():
                self._handle_simulation_message(self.simulation_queue.get())
            
            # Schedule next check
            self.after(100, self._check_simulation_thread)
        else:
            # Simulation finished: as mensagens que sobraram na fila entram
            # antes do status final, senão elas o sobrescrevem.
            if self.simulation_queue:
                while not self.simulation_queue.empty():
                    self._handle_simulation_message(self.simulation_queue.get())

            self.control_panel.set_running_state(False)
            self.control_panel.run_button.configure(state="normal")
            interrupted = bool(self.simulation and self.simulation.stop_requested)
            has_error = bool(getattr(self, "_simulation_error", None))
            if interrupted:
                self.results_panel.append_warning("Simulação interrompida.")
                self.control_panel.set_status("Simulação interrompida", "warning")
            elif has_error:
                self.results_panel.append_error(
                    "Simulação finalizada com erros. Verifique os logs acima.")
                self.control_panel.set_status("Simulação falhou", "error")
            else:
                self.results_panel.append_success("Simulação concluída!")
                self.control_panel.set_status("Simulação concluída", "success")
            self._runs_dirty = True
            finished_path = getattr(self, "_running_run_path", None)
            if finished_path:
                self.simulations_panel.clear_running(finished_path)
                self._running_run_path = None
            self.simulation = None
            if finished_path and not interrupted and not has_error:
                run = next((r for r in self.simulations_panel._runs
                            if r['path'] == finished_path), None)
                if run is not None:
                    self.on_open_run_details(run)
    
    # Callback implementations for PathConfigPanel
    def on_idf_path_changed(self, path: str):
        """Handle IDF path change."""
        if self.configs:
            self.configs.idf_path = path
        self._refresh_room_options(path)
        if os.path.isfile(path):
            self.idf_editor_panel.load(path)

    # ------------------------------------------------------------ editor IDF

    def on_edit_idf(self):
        """Carrega o IDF e abre a aba Período na tela de execução."""
        idf_path = self.path_panel.get_idf_path().strip()
        if not idf_path or not os.path.isfile(idf_path):
            toast(self, "Escolha um arquivo IDF antes de editá-lo.", "warn")
            return
        self.idf_editor_panel.load(idf_path)
        self.simulation_panel.notebook.select(self.idf_editor_panel.period_tab)

    def on_save_idf_copy(self):
        """Grava um IDF novo ao lado do original e passa a usá-lo.

        O arquivo escolhido pelo usuário nunca é reescrito: cada edição vira
        um `<nome>_editado.idf` (com sufixo numérico se já existir).
        """
        source = self.idf_editor_panel.idf_path
        updates = self.idf_editor_panel.get_updates()
        if updates is None:      # já avisou qual campo está inválido
            return
        if not updates:
            toast(self, "Nenhum campo foi alterado.", "info")
            return

        target = self._new_idf_name(source)
        try:
            write_idf_fields(source, target, updates)
        except (OSError, IndexError) as error:
            toast(self, f"Não foi possível gravar o IDF: {error}", "error")
            return

        self.path_panel.set_idf_path(target)
        self.on_idf_path_changed(target)
        self.simulation_panel.notebook.select(self.path_panel)
        toast(self, f"IDF salvo em {os.path.basename(target)}.", "ok")

    @staticmethod
    def _new_idf_name(source: str, suffix: str = "editado") -> str:
        """`<nome>_<sufixo>.idf`, numerado enquanto o nome já existir."""
        base, extension = os.path.splitext(source)
        candidate = f"{base}_{suffix}{extension}"
        counter = 2
        while os.path.exists(candidate):
            candidate = f"{base}_{suffix}_{counter}{extension}"
            counter += 1
        return candidate

    def _refresh_room_options(self, idf_path: str):
        """Ofereça as zonas do IDF escolhido no seletor de salas."""
        self.simulation_panel.set_room_options(read_zone_names(idf_path))
    
    def on_output_path_changed(self, path: str):
        """Handle runs root change."""
        if self.configs:
            self.configs.runs_root_path = path
        self.simulations_panel.set_outputs_path(self._outputs_root())
    
    def on_epw_path_changed(self, path: str):
        """Handle EPW path change."""
        if self.configs:
            self.configs.epw_path = path
    
    def on_energy_path_changed(self, path: str):
        """Handle energy path change."""
        if self.configs:
            self.configs.energy_path = path
    
    # Callback implementations for SimulationConfigPanel
    def on_simulation_config_changed(self):
        """Handle simulation configuration change."""
    
    # Callback implementations for ResultsPanel
    def on_results_cleared(self):
        """Handle results cleared."""
        pass
    
    # Callback implementations for ControlPanel
    def on_run_simulation(self):
        """Handle run simulation request."""
        if self.control_panel.get_is_running():
            return
        
        self._simulation_error = None

        # Save current configuration
        self._update_config_from_ui()
        
        # Validate configuration
        if not self._validate_configuration():
            return

        # Cada rodada escreve numa subpasta nova da raiz configurada; nunca
        # por cima da anterior.
        self.configs.output_path = new_run_path(root=self.configs.runs_root_path)
        # Entra na listagem como "em simulação" já na largada, antes de a
        # pasta existir.
        self._running_run_path = self.configs.output_path
        self.simulations_panel.set_running(self._running_run_path, self.configs)
        
        # Start simulation
        self.control_panel.set_running_state(True)
        self.log_sheet.set_open(True)
        self.results_panel.append_info("Iniciando simulação...")
        
        # Create queue for communication
        self.simulation_queue = Queue()
        
        # Start simulation thread
        self.simulation_thread = threading.Thread(
            target=self._run_simulation_thread,
            args=(self.simulation_queue,)
        )
        self.simulation_thread.start()
        
        # Start checking thread status
        self.after(100, self._check_simulation_thread)
    
    def on_stop_simulation(self):
        """Handle stop simulation request."""
        if not (self.simulation_thread and self.simulation_thread.is_alive()):
            return
        # `stop_simulation` da API do EnergyPlus: ele encerra no próximo passo,
        # então a thread continua viva por alguns segundos e o botão fica
        # desabilitado até ela terminar de verdade.
        self.results_panel.append_warning("Parada de simulação solicitada...")
        self.control_panel.set_status("Interrompendo simulação...", "warning")
        self.control_panel.run_button.configure(state="disabled")
        if self.simulation:
            self.simulation.stop()
    
    # --- Callbacks do SimulationsPanel ---

    def on_new_run(self):
        """Página de execução; a pasta de saída sai da raiz ao rodar."""
        self.show_page("editor")

    def on_compare_runs(self, runs: list, outputs_path: str):
        """Leva as execuções escolhidas para a página de comparação."""
        self.comparison_panel.set_runs(runs, outputs_path)
        self.show_page("compare")

    def on_ask_assistant(self, runs: list, outputs_path: str):
        """Página do assistente com as execuções escolhidas como contexto."""
        self.assistant_panel.set_context([run['run'] for run in runs])
        self.show_page("assistant")

    def on_open_run_details(self, run: dict):
        """Página com a configuração completa da execução escolhida."""
        self._detail_run = run
        lines = [run['run'], "-" * len(run['run']), "",
                 f"{'pasta':24s} {os.path.abspath(run['path'])}",
                 f"{'status':24s} {run['status']}",
                 f"{'modificado':24s} {run['modificado'].strftime('%d/%m/%Y %H:%M')}",
                 f"{'zonas':24s} {', '.join(run['rooms_disponiveis']) or '—'}", ""]
        lines += [f"{key.lstrip('_'):24s} {value}"
                  for key, value in run['config'].items()]

        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", "\n".join(lines))
        self.detail_text.configure(state="disabled")
        self._render_detail_stats(run)
        self.detail_tabs.select(0)
        self.timeseries_panel.set_run(run)
        self.detail_assistant.set_context([run['run']], run_filter=run['run'])
        self.show_page("detail")

    def _on_detail_tab_changed(self, _event=None):
        if self.detail_tabs.index("current") == 1:
            self.timeseries_panel.activate()
        else:
            self.timeseries_panel.deactivate()

    def _render_detail_stats(self, run: dict):
        """Uma linha por zona, lida do ESTATISTICAS.xlsx que a execução já gravou."""
        import pandas

        from confortimetro.results.compare import COMPARISON_COLUMNS, PERCENTAGE_COLUMNS

        tree = self.detail_stats
        tree.delete(*tree.get_children())

        stats_path = os.path.join(run['path'], 'ESTATISTICAS.xlsx')
        if not os.path.exists(stats_path):
            self.kpi_total_var.set("—")
            self.kpi_aquec_var.set("—")
            self.kpi_resfr_var.set("—")
            tree["columns"] = ("aviso",)
            tree.heading("aviso", text="Estatísticas")
            tree.column("aviso", width=600, anchor="w", stretch=True)
            tree.insert("", "end", values=(
                "Sem estatísticas: use Regerar estatísticas na listagem.",))
            self.detail_empty_var.set(
                "Esta execução ainda não tem ESTATISTICAS.xlsx. Use Regerar estatísticas para calcular os indicadores a partir das planilhas existentes.")
            self.detail_empty.pack(anchor="w", pady=(SPACE[2], 0))
            return

        try:
            df = pandas.read_excel(stats_path)
        except Exception as error:
            self.kpi_total_var.set("—")
            self.kpi_aquec_var.set("—")
            self.kpi_resfr_var.set("—")
            tree["columns"] = ("aviso",)
            tree.heading("aviso", text="Estatísticas")
            tree.column("aviso", width=600, anchor="w", stretch=True)
            tree.insert("", "end", values=(f"Não foi possível ler: {error}",))
            self.detail_empty_var.set("Não foi possível abrir as estatísticas. Tente regerá-las a partir das planilhas da execução.")
            self.detail_empty.pack(anchor="w", pady=(SPACE[2], 0))
            return

        self.detail_empty.pack_forget()

        def _fmt_kwh(val):
            if val is None or pandas.isna(val):
                return "—"
            return f"{float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        total_kwh = df['Energia total (kWh)'].sum() if 'Energia total (kWh)' in df.columns else None
        aquec_kwh = df['Aquecimento (kWh)'].sum() if 'Aquecimento (kWh)' in df.columns else None
        resfr_kwh = df['Resfriamento (kWh)'].sum() if 'Resfriamento (kWh)' in df.columns else None

        self.kpi_total_var.set(_fmt_kwh(total_kwh))
        self.kpi_aquec_var.set(_fmt_kwh(aquec_kwh))
        self.kpi_resfr_var.set(_fmt_kwh(resfr_kwh))

        columns = ["Nome da sala"] + [column for column in COMPARISON_COLUMNS
                                      if column in df.columns]
        tree["columns"] = columns
        for column in columns:
            tree.heading(column, text=COMPARISON_HEADINGS.get(column, column))
            width = 160 if column == "Nome da sala" else 130
            tree.column(column, width=width, minwidth=width,
                        anchor="w" if column == "Nome da sala" else "e",
                        stretch=False)

        def _fmt_cell(col, val):
            if pandas.isna(val):
                return "—"
            if isinstance(val, (int, float)):
                if col in PERCENTAGE_COLUMNS:
                    return f"{val * 100:.1f}%".replace(".", ",")
                return f"{val:.3f}".replace(".", ",")
            return val

        for _, row in df.iterrows():
            tree.insert("", "end", values=[_fmt_cell(col, row[col]) for col in columns])

        # Linha TOTAL no rodapé da tabela
        if len(df) > 0 and total_kwh is not None:
            total_row_values = []
            for col in columns:
                if col == "Nome da sala":
                    total_row_values.append("TOTAL")
                elif col == "Energia total (kWh)":
                    total_row_values.append(f"{total_kwh:.3f}".replace(".", ","))
                elif col == "Aquecimento (kWh)" and aquec_kwh is not None:
                    total_row_values.append(f"{aquec_kwh:.3f}".replace(".", ","))
                elif col == "Resfriamento (kWh)" and resfr_kwh is not None:
                    total_row_values.append(f"{resfr_kwh:.3f}".replace(".", ","))
                else:
                    total_row_values.append("—")
            tree.insert("", "end", values=total_row_values, tags=("total",))

        tree.configure(height=max(4, min(len(df) + 1, 8)))

    def on_duplicate_run(self, run: Optional[dict]):
        """Carrega a configuração da execução na página de execução, com uma
        pasta de saída nova — duplicar é repetir os parâmetros, nunca escrever
        por cima dos resultados que já existem.
        """
        if not run:
            return
        try:
            config = SimulationConfig.from_json(
                os.path.join(run['path'], "configs.json"))
        except Exception as error:
            toast(self, f"Não foi possível ler a configuração: {error}", "error")
            return

        # `idf_path` da execução aponta para a cópia dentro dela; o modelo
        # escolhido pelo usuário é o `source_idf_path`.
        if config.source_idf_path:
            config.idf_path = config.source_idf_path
        config.output_path = None
        config.runs_root_path = self._outputs_root()

        self.configs = config
        self._update_ui_from_config()
        self.results_panel.append_info(f"Configuração duplicada de {run['run']}.")
        self.show_page("editor")

    def _recompute_detail_stats(self):
        if not self._detail_run:
            toast(self, "Abra uma execução antes de regerar as estatísticas.", "warn")
            return
        self.simulations_panel.tree.selection_set(self._detail_run["path"])
        self.simulations_panel.recompute_selected()

    def _open_detail_folder(self):
        if not self._detail_run:
            return
        path = os.path.abspath(self._detail_run['path'])
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])

    def on_save_config(self):
        """Handle save configuration request."""
        self._save_configuration()
    
    def on_load_config(self):
        """Handle load configuration request."""
        file_path = filedialog.askopenfilename(
            title="Carregar Configuração",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.config_path)
        )
        
        if file_path:
            try:
                self.configs = SimulationConfig.from_json(file_path)
                self._update_ui_from_config()
                self.results_panel.append_success(f"Configuração carregada de: {file_path}")
            except Exception as e:
                self.results_panel.append_error(f"Erro ao carregar configuração: {str(e)}")
                toast(self, f"Erro ao carregar configuração: {e}", "error")


def main():
    """Main entry point."""
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
