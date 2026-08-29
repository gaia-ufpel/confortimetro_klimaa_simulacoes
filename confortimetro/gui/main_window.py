"""
Main window for the Confortimetro Klimaa application.
"""

import os
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
from queue import Queue
import copy
from typing import Optional

from confortimetro.simulation import Simulation
from confortimetro.config import SimulationConfig
from confortimetro.idf import read_zone_names
from .components import (
    PathConfigPanel,
    SimulationConfigPanel,
    ResultsPanel,
    ControlPanel,
    open_simulations_window
)
from .theme import COLORS, SPACE, BottomSheet, Card, apply_theme, scrollable


class MainWindow(tk.Tk):
    """Main application window."""
    
    def __init__(self, config_path: str = "examples/config.json"):
        super().__init__()
        
        self.config_path = config_path
        self.configs: Optional[SimulationConfig] = None
        self.simulation_thread: Optional[threading.Thread] = None
        self.simulation_queue: Optional[Queue] = None
        self._simulations_window: Optional[tk.Toplevel] = None
        
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
        """Topbar de execução, parâmetros no meio, log num bottom sheet."""
        from tkinter import ttk

        container = ttk.Frame(self, style="Main.TFrame")
        container.pack(fill="both", expand=True, padx=SPACE[5], pady=SPACE[5])

        header = ttk.Frame(container, style="Main.TFrame")
        header.pack(fill="x", pady=(0, SPACE[3]))
        ttk.Label(header, text="Confortímetro Klimaa",
                  style="H1.TLabel").pack(anchor="w")
        ttk.Label(header, text="Simulações personalizadas com EnergyPlus",
                  style="Sub.TLabel").pack(anchor="w", pady=(SPACE[1], 0))

        # --- Topbar: executar, salvar/carregar e estado da simulação ---
        topbar = Card(container, pad=SPACE[3])
        topbar.pack(fill="x", pady=(0, SPACE[4]))
        self.control_panel = ControlPanel(topbar.body, callback=self)
        self.control_panel.pack(fill="x")

        # --- Parâmetros: caminhos e simulação no mesmo card ---
        params_card = Card(container, "Parâmetros da simulação")
        params_card.pack(fill="both", expand=True)
        params = scrollable(params_card.body)

        self.path_panel = PathConfigPanel(params, callback=self)
        self.path_panel.pack(fill="x")
        ttk.Separator(params, orient="horizontal",
                      style="Modern.TSeparator").pack(fill="x",
                                                      pady=(0, SPACE[4]))
        self.simulation_panel = SimulationConfigPanel(params, callback=self)
        self.simulation_panel.pack(fill="both", expand=True)

        # --- Log: painel inferior colapsável ---
        self.log_sheet = BottomSheet(container, "Log de execução")
        self.log_sheet.pack(fill="x", pady=(SPACE[4], 0))
        self.results_panel = ResultsPanel(self.log_sheet.body, callback=self)
        self.results_panel.pack(fill="both", expand=True)

        ttk.Label(container, text="Desenvolvido para o GAIA — UFPel",
                  style="Sub.TLabel").pack(pady=(SPACE[3], 0))

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
            
        except Exception as e:
            self.results_panel.append_error(f"Erro ao carregar configuração: {str(e)}")
            self.configs = SimulationConfig()  # Fallback to default
    
    def _update_ui_from_config(self):
        """Update UI components with configuration data."""
        if not self.configs:
            return
        
        # Update path panel
        self.path_panel.set_idf_path(self.configs.idf_path)
        self.path_panel.set_output_path(self.configs.output_path)
        self.path_panel.set_epw_path(self.configs.epw_path)
        self.path_panel.set_energy_path(self.configs.energy_path)
        
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
        self.configs.output_path = self.path_panel.get_output_path()
        self.configs.epw_path = self.path_panel.get_epw_path()
        self.configs.energy_path = self.path_panel.get_energy_path()
        
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
    
    def on_open_simulations(self):
        """Abre a listagem de simulações já executadas e o comparador."""
        if self._simulations_window and self._simulations_window.winfo_exists():
            self._simulations_window.lift()
            self._simulations_window.focus_force()
            return

        # A pasta configurada é a da próxima execução; a listagem interessa na
        # pasta que a contém, onde ficam todas as execuções anteriores.
        output_path = self.path_panel.get_output_path()
        outputs_root = os.path.dirname(output_path.rstrip(os.sep)) or "."
        if not os.path.isdir(outputs_root):
            outputs_root = "."

        self._simulations_window = open_simulations_window(self, outputs_root)

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
