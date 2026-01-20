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

from src.simulation import Simulation
from src.utils.simulation_config import SimulationConfig
from .components import (
    PathConfigPanel, 
    SimulationConfigPanel, 
    ResultsPanel, 
    ControlPanel
)


class MainWindow(tk.Tk):
    """Main application window."""
    
    def __init__(self, config_path: str = "resources/config.json"):
        super().__init__()
        
        self.config_path = config_path
        self.configs: Optional[SimulationConfig] = None
        self.simulation_thread: Optional[threading.Thread] = None
        self.simulation_queue: Optional[Queue] = None
        
        self._setup_window()
        self._setup_styles()
        self._build_ui()
        self._load_configuration()
    
    def _setup_window(self):
        """Setup the main window properties."""
        self.title("🌡️ Confortímetro Klimaa - Simulações EnergyPlus")
        self.geometry("1200x900")
        self.minsize(800, 600)
        
        # Modern gradient-like background
        self.configure(background="#f8f9fa")
        
        # Center window on screen
        self.center_window()
        
        # Set window icon if available
        try:
            # You can add an icon file here
            # self.iconbitmap("resources/icon.ico")
            pass
        except:
            pass
    
    def _setup_styles(self):
        """Setup the UI styles with modern theme."""
        from tkinter import ttk
        
        self.style = ttk.Style()
        self.style.theme_use("clam")  # Better base theme
        
        # Color palette - Modern blue/green theme
        colors = {
            'primary': '#2563eb',      # Blue 600
            'primary_light': '#3b82f6', # Blue 500
            'primary_dark': '#1d4ed8',  # Blue 700
            'secondary': '#10b981',     # Emerald 500
            'secondary_light': '#34d399', # Emerald 400
            'accent': '#f59e0b',        # Amber 500
            'danger': '#ef4444',        # Red 500
            'success': '#22c55e',       # Green 500
            'warning': '#f59e0b',       # Amber 500
            'background': '#f8f9fa',    # Gray 50
            'surface': '#ffffff',       # White
            'surface_alt': '#f1f5f9',   # Slate 100
            'text': '#1e293b',          # Slate 800
            'text_muted': '#64748b',    # Slate 500
            'border': '#e2e8f0',        # Slate 200
        }
        
        # Configure frame styles
        self.style.configure("Main.TFrame", 
                           background=colors['background'])
        
        self.style.configure("Card.TFrame", 
                           background=colors['surface'],
                           relief="flat",
                           borderwidth=1)
        
        self.style.configure("Header.TFrame", 
                           background=colors['primary'],
                           relief="flat")
        
        # Configure label styles
        self.style.configure("Title.TLabel", 
                           background=colors['surface'],
                           foreground=colors['text'],
                           font=('Segoe UI', 12, 'bold'))
        
        self.style.configure("Header.TLabel", 
                           background=colors['primary'],
                           foreground='white',
                           font=('Segoe UI', 14, 'bold'))
        
        self.style.configure("Body.TLabel", 
                           background=colors['surface'],
                           foreground=colors['text'],
                           font=('Segoe UI', 9))
        
        self.style.configure("Muted.TLabel", 
                           background=colors['surface'],
                           foreground=colors['text_muted'],
                           font=('Segoe UI', 8))
        
        # Configure button styles
        self.style.configure("Primary.TButton",
                           background=colors['primary'],
                           foreground='white',
                           font=('Segoe UI', 9, 'bold'),
                           padding=(16, 8),
                           relief="flat")
        
        self.style.map("Primary.TButton",
                      background=[('active', colors['primary_light']),
                                ('pressed', colors['primary_dark'])])
        
        self.style.configure("Secondary.TButton",
                           background=colors['secondary'],
                           foreground='white',
                           font=('Segoe UI', 9, 'bold'),
                           padding=(16, 8),
                           relief="flat")
        
        self.style.map("Secondary.TButton",
                      background=[('active', colors['secondary_light'])])
        
        self.style.configure("Danger.TButton",
                           background=colors['danger'],
                           foreground='white',
                           font=('Segoe UI', 9, 'bold'),
                           padding=(16, 8),
                           relief="flat")
        
        self.style.configure("Outline.TButton",
                           background=colors['surface'],
                           foreground=colors['primary'],
                           font=('Segoe UI', 9),
                           padding=(12, 6),
                           relief="solid",
                           borderwidth=1)
        
        # Configure entry styles
        self.style.configure("Modern.TEntry",
                           foreground=colors['text'],
                           font=('Segoe UI', 9),
                           padding=8,
                           relief="flat",
                           borderwidth=1)
        
        # Configure combobox styles
        self.style.configure("Modern.TCombobox",
                           foreground=colors['text'],
                           font=('Segoe UI', 9),
                           padding=8)
        
        # Configure progress bar
        self.style.configure("Modern.Horizontal.TProgressbar",
                           background=colors['primary'],
                           troughcolor=colors['surface_alt'],
                           borderwidth=0,
                           lightcolor=colors['primary'],
                           darkcolor=colors['primary'])
        
        # Configure separator
        self.style.configure("Modern.TSeparator",
                           background=colors['border'])
        
        # Store colors for component access
        self.colors = colors
    
    def _build_ui(self):
        """Build the user interface with modern card-based layout."""
        from tkinter import ttk
        
        # Configure main frame
        self.configure(background=self.colors['background'])
        
        # Main container with padding
        main_container = ttk.Frame(self, style="Main.TFrame")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header with app title
        header_frame = ttk.Frame(main_container, style="Header.TFrame")
        header_frame.pack(fill="x", pady=(0, 20))
        
        # App icon/title
        title_container = ttk.Frame(header_frame, style="Header.TFrame")
        title_container.pack(fill="x", padx=20, pady=15)
        
        ttk.Label(title_container, text="🌡️", 
                 font=('Segoe UI', 24)).pack(side="left")
        
        title_frame = ttk.Frame(title_container, style="Header.TFrame")
        title_frame.pack(side="left", padx=(10, 0))
        
        ttk.Label(title_frame, text="Confortímetro Klimaa", 
                 style="Header.TLabel",
                 font=('Segoe UI', 18, 'bold')).pack(anchor="w")
        ttk.Label(title_frame, text="Simulações Personalizadas com EnergyPlus", 
                 style="Header.TLabel",
                 font=('Segoe UI', 10)).pack(anchor="w")
        
        # Content area with scrollable frame if needed
        content_frame = ttk.Frame(main_container, style="Main.TFrame")
        content_frame.pack(fill="both", expand=True)
        
        # Path configuration card
        path_card = self._create_card(content_frame, "📁 Configuração de Caminhos")
        path_card.pack(fill="x", pady=(0, 15))
        
        self.path_panel = PathConfigPanel(path_card, callback=self)
        self.path_panel.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Simulation configuration card
        sim_card = self._create_card(content_frame, "⚙️ Configuração de Simulação")
        sim_card.pack(fill="both", expand=True, pady=(0, 15))
        
        self.simulation_panel = SimulationConfigPanel(sim_card, callback=self)
        self.simulation_panel.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Control panel card
        control_card = self._create_card(content_frame, "🎮 Controles")
        control_card.pack(fill="x", pady=(0, 15))
        
        self.control_panel = ControlPanel(control_card, callback=self)
        self.control_panel.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Results card
        results_card = self._create_card(content_frame, "📊 Resultados e Log")
        results_card.pack(fill="both", expand=True)
        
        self.results_panel = ResultsPanel(results_card, callback=self)
        self.results_panel.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Footer
        footer_frame = ttk.Frame(main_container, style="Main.TFrame")
        footer_frame.pack(fill="x", pady=(15, 0))
        
        ttk.Label(footer_frame, text="🌱 Desenvolvido para GAIA - UFPEL", 
                 style="Muted.TLabel").pack(pady=10)
    
    def _create_card(self, parent, title):
        """Create a card container with title."""
        from tkinter import ttk
        
        # Card container
        card_container = ttk.Frame(parent, style="Main.TFrame")
        
        # Card header
        header = ttk.Frame(card_container, style="Card.TFrame")
        header.pack(fill="x")
        
        ttk.Label(header, text=title, style="Title.TLabel").pack(
            anchor="w", padx=20, pady=15)
        
        # Separator
        ttk.Separator(card_container, style="Modern.TSeparator").pack(
            fill="x", padx=20)
        
        # Card content
        content = ttk.Frame(card_container, style="Card.TFrame")
        content.pack(fill="both", expand=True)
        
        return content
    
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
