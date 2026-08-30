"""
Main window for the Confortimetro Klimaa application.
"""

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
from queue import Queue
import copy
from typing import Optional

from confortimetro.simulation import Simulation
from confortimetro.config import SimulationConfig
from confortimetro.idf import read_zone_names
from confortimetro.paths import new_run_path, runs_root
from confortimetro.results.compare import runs_root_for
from .components import (
    MACHINE_FIELDS,
    SIMULATION_FIELDS,
    PathConfigPanel,
    SimulationConfigPanel,
    ResultsPanel,
    ControlPanel,
    SimulationsPanel,
    ComparisonPanel,
)
from .theme import (
    COLORS,
    FONTS,
    SPACE,
    BottomSheet,
    Card,
    RoundedButton,
    apply_theme,
    scrollable,
)


class MainWindow(tk.Tk):
    """Main application window."""
    
    def __init__(self, config_path: str = "examples/config.json"):
        super().__init__()
        
        self.config_path = config_path
        self.configs: Optional[SimulationConfig] = None
        self.simulation_thread: Optional[threading.Thread] = None
        self.simulation_queue: Optional[Queue] = None
        # A listagem só é relida quando alguma execução termina.
        self._runs_dirty = False
        self._detail_run: Optional[dict] = None
        # `after` da transição de página em andamento, se houver.
        self._sliding: Optional[str] = None
        
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
        self.center_window()

    def _build_ui(self):
        """Uma página por vez no mesmo host: execuções, detalhes, execução e
        configurações. Todas ficam montadas; navegar é `pack`/`pack_forget`.
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

        ttk.Label(container, text="Desenvolvido para o GAIA — UFPel",
                  style="Sub.TLabel", background=COLORS["bg"]).pack(
                      pady=(SPACE[3], 0))

        self._pages = {
            "runs": self._build_runs_page(),
            "compare": self._build_compare_page(),
            "detail": self._build_detail_page(),
            "editor": self._build_editor_page(),
            "settings": self._build_settings_page(),
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
    }

    # Ordem das páginas na navegação: define para que lado a transição corre
    # (ir para a direita, voltar para a esquerda).
    _PAGE_ORDER = ("runs", "compare", "detail", "editor", "settings")

    # Uma transição curta orienta sem atrasar; acima disso a navegação começa
    # a parecer lenta.
    _SLIDE_MS = 180
    _SLIDE_FRAMES = 12

    def show_page(self, name: str):
        """Mostra uma página e desliza a anterior para fora."""
        if self._current_page == name:
            return

        previous = self._current_page
        self._current_page = name
        self.subtitle_label.configure(text=self._PAGE_SUBTITLES[name])

        # A listagem só relê a pasta quando alguma execução terminou: o sync
        # do banco custa segundos e não vale a cada ida e volta.
        if name == "runs" and self._runs_dirty:
            self._runs_dirty = False
            self.simulations_panel.refresh()

        if previous is None:
            self._pages[name].pack(fill="both", expand=True)
            return

        forward = (self._PAGE_ORDER.index(name)
                   > self._PAGE_ORDER.index(previous))
        self._slide(self._pages[previous], self._pages[name],
                    direction=1 if forward else -1)

    def _slide(self, outgoing, incoming, direction: int):
        """Troca as páginas deslizando as duas, com `place` sobre o host.

        Durante a animação ninguém fica packado: misturar `pack` e `place` no
        mesmo host faz a página que entra reservar espaço e empurrar a outra.
        """
        if self._sliding:
            # Clique rápido em dois botões: a animação anterior é abandonada e
            # a página dela sai de cena antes que esta comece.
            self.after_cancel(self._sliding)
            self._sliding = None
            for page in self._pages.values():
                page.place_forget()
                page.pack_forget()

        outgoing.pack_forget()
        outgoing.place(relx=0, rely=0, relwidth=1, relheight=1)
        incoming.place(relx=direction, rely=0, relwidth=1, relheight=1)
        incoming.lift()

        step = [0]

        def frame():
            step[0] += 1
            progress = step[0] / self._SLIDE_FRAMES
            if progress >= 1:
                self._sliding = None
                outgoing.place_forget()
                incoming.place_forget()
                incoming.pack(fill="both", expand=True)
                return
            # Desaceleração no fim: o movimento linear parece mecânico.
            eased = 1 - (1 - progress) ** 3
            outgoing.place_configure(relx=-direction * eased)
            incoming.place_configure(relx=direction * (1 - eased))
            self._sliding = self.after(self._SLIDE_MS // self._SLIDE_FRAMES,
                                       frame)

        self._sliding = self.after(self._SLIDE_MS // self._SLIDE_FRAMES, frame)

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

        card = Card(page, "Configuração da execução")
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

        actions = Card(page, pad=SPACE[3])
        actions.pack(fill="x", pady=(SPACE[4], 0))
        row = ttk.Frame(actions.body, style="Surface.TFrame")
        row.pack(fill="x")
        RoundedButton(row, text="Duplicar para nova execução", variant="primary", icon="duplicate",
                      command=lambda: self.on_duplicate_run(self._detail_run)).pack(
                          side="left")
        RoundedButton(row, text="Abrir pasta", variant="ghost", icon="open",
                      command=self._open_detail_folder).pack(side="left",
                                                             padx=(SPACE[2], 0))
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

        # --- Parâmetros: caminhos e simulação no mesmo card ---
        params_card = Card(page, "Parâmetros da simulação")
        params_card.pack(fill="both", expand=True)
        params = scrollable(params_card.body)

        self.path_panel = PathConfigPanel(params, callback=self,
                                          fields=SIMULATION_FIELDS)
        self.path_panel.pack(fill="x")
        ttk.Separator(params, orient="horizontal",
                      style="Modern.TSeparator").pack(fill="x",
                                                      pady=(0, SPACE[4]))
        self.simulation_panel = SimulationConfigPanel(params, callback=self)
        self.simulation_panel.pack(fill="both", expand=True)

        # --- Log: painel inferior colapsável ---
        self.log_sheet = BottomSheet(page, "Log de execução")
        self.log_sheet.pack(fill="x", pady=(SPACE[4], 0))
        self.results_panel = ResultsPanel(self.log_sheet.body, callback=self)
        self.results_panel.pack(fill="both", expand=True)
        return page

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
        return page

    def _outputs_root(self) -> str:
        """Pasta que a listagem lê, a partir do que está nas configurações."""
        output_path = (self.settings_panel.get_output_path()
                       if hasattr(self, "settings_panel") else "")
        if not output_path and self.configs:
            output_path = self.configs.output_path or ""

        outputs_root = runs_root_for(output_path)
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
            self.configs.output_path or new_run_path())
        self.path_panel.set_epw_path(self.configs.epw_path)
        self.settings_panel.set_energy_path(self.configs.energy_path)
        
        self._refresh_room_options(self.configs.idf_path)

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
        self.configs.output_path = self.settings_panel.get_output_path()
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
            messagebox.showerror("Erro", f"Erro ao salvar configuração: {str(e)}")
    
    def _validate_configuration(self) -> bool:
        """Validate the current configuration."""
        if not self.configs:
            messagebox.showerror("Erro", "Configuração não carregada!")
            return False
        
        # Check required paths
        if not os.path.exists(self.configs.idf_path):
            messagebox.showerror("Erro", "Arquivo IDF não encontrado!")
            return False
        
        if not os.path.exists(self.configs.epw_path):
            messagebox.showerror("Erro", "Arquivo EPW não encontrado!")
            return False
        
        if not os.path.exists(self.configs.energy_path):
            messagebox.showerror("Erro", "Pasta do EnergyPlus não existe!")
            return False
        
        # Check if output directory already exists
        if os.path.exists(self.configs.output_path):
            want_proceed = messagebox.askokcancel(
                "Alerta", 
                "Uma pasta de saída com esse nome já existe, tem certeza que deseja continuar?"
            )
            if not want_proceed:
                return False
        
        return True
    
    def _run_simulation_thread(self, q: Queue):
        """Run simulation in a separate thread."""
        try:
            if self.configs is None:
                raise ValueError("Configuration not loaded")
            simulation = Simulation(copy.deepcopy(self.configs))
            simulation.run(q)
        except Exception as e:
            q.put(f"Erro durante a simulação: {str(e)}\n")
    
    def _check_simulation_thread(self):
        """Check simulation thread status and update UI."""
        if self.simulation_thread and self.simulation_thread.is_alive():
            # Get messages from queue
            while not self.simulation_queue.empty():
                message = self.simulation_queue.get()
                self.results_panel.append_info(message.strip())
                # Update control panel status
                self.control_panel.set_status(message.strip(), "running")
            
            # Schedule next check
            self.after(100, self._check_simulation_thread)
        else:
            # Simulation finished
            self.control_panel.set_running_state(False)
            self.results_panel.append_success("Simulação concluída!")
            self._runs_dirty = True
            self.control_panel.set_status("Simulação concluída", "success")
            
            # Get any remaining messages
            if self.simulation_queue:
                while not self.simulation_queue.empty():
                    message = self.simulation_queue.get()
                    self.results_panel.append_info(message.strip())
    
    # Callback implementations for PathConfigPanel
    def on_idf_path_changed(self, path: str):
        """Handle IDF path change."""
        if self.configs:
            self.configs.idf_path = path
        self._refresh_room_options(path)

    def _refresh_room_options(self, idf_path: str):
        """Ofereça as zonas do IDF escolhido no seletor de salas."""
        self.simulation_panel.set_room_options(read_zone_names(idf_path))
    
    def on_output_path_changed(self, path: str):
        """Handle output path change."""
        if self.configs:
            self.configs.output_path = path
        # O campo é a pasta da próxima execução; a listagem mostra a pasta que
        # a contém, onde ficam todas as anteriores.
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
        # Auto-save configuration on change (optional)
        pass
    
    # Callback implementations for ResultsPanel
    def on_results_cleared(self):
        """Handle results cleared."""
        pass
    
    # Callback implementations for ControlPanel
    def on_run_simulation(self):
        """Handle run simulation request."""
        if self.control_panel.get_is_running():
            return
        
        # Save current configuration
        self._update_config_from_ui()
        
        # Validate configuration
        if not self._validate_configuration():
            return
        
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
        if self.simulation_thread and self.simulation_thread.is_alive():
            # Note: This is a simplified stop - in practice you might need
            # a more sophisticated way to stop the simulation
            self.results_panel.append_warning("Parada de simulação solicitada...")
            self.control_panel.set_running_state(False)
    
    # --- Callbacks do SimulationsPanel ---

    def on_new_run(self):
        """Página de execução com uma pasta de saída nova."""
        self.settings_panel.set_output_path(new_run_path())
        self.show_page("editor")

    def on_compare_runs(self, runs: list, outputs_path: str):
        """Leva as execuções escolhidas para a página de comparação."""
        self.comparison_panel.set_runs(runs, outputs_path)
        self.show_page("compare")

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
        self.show_page("detail")

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
            messagebox.showerror("Erro", f"Não foi possível ler a configuração: {error}")
            return

        # `idf_path` da execução aponta para a cópia dentro dela; o modelo
        # escolhido pelo usuário é o `source_idf_path`.
        if config.source_idf_path:
            config.idf_path = config.source_idf_path
        config.output_path = new_run_path()

        self.configs = config
        self._update_ui_from_config()
        self.results_panel.append_info(f"Configuração duplicada de {run['run']}.")
        self.show_page("editor")

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
                messagebox.showerror("Erro", f"Erro ao carregar configuração: {str(e)}")


def main():
    """Main entry point."""
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
