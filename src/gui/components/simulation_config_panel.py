"""
Simulation configuration panel component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Protocol, Optional, List

from src.modules import MODULES_MAPPER
from src.utils import ADAPTATIVE2PORCENT, PORCENT2ADAPTATIVE
from src.utils.module_type import ModuleType


class SimulationConfigCallback(Protocol):
    """Protocol for simulation configuration callbacks."""
    
    def on_simulation_config_changed(self) -> None:
        """Called when simulation configuration is changed."""
        ...


class SimulationConfigPanel(ttk.Frame):
    """Panel for simulation configuration."""
    
    def __init__(self, parent, callback: Optional[SimulationConfigCallback] = None):
        super().__init__(parent)
        self.callback = callback
        self._build_ui()
    
    def _build_ui(self):
        """Build the UI components."""
        # PMV configuration
        self._build_pmv_section()
        
        # Temperature and environment section
        self._build_temperature_section()
        
        # Comfort and air quality section
        self._build_comfort_section()
        
        # Clothing section
        self._build_clothing_section()
        
        # Rooms and module section
        self._build_rooms_module_section()
    
    def _build_pmv_section(self):
        """Build PMV configuration section."""
        # PMV lowerbound
        ttk.Label(self, text="PMV Min:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.pmv_lowerbound_entry = ttk.Entry(self, width=10)
        self.pmv_lowerbound_entry.grid(row=1, column=0, padx=5, pady=2)
        self.pmv_lowerbound_entry.bind('<FocusOut>', self._on_config_changed)
        
        # PMV upperbound
        ttk.Label(self, text="PMV Max:").grid(row=0, column=1, padx=5, pady=2, sticky="w")
        self.pmv_upperbound_entry = ttk.Entry(self, width=10)
        self.pmv_upperbound_entry.grid(row=1, column=1, padx=5, pady=2)
        self.pmv_upperbound_entry.bind('<FocusOut>', self._on_config_changed)
        
        # Velocity max
        ttk.Label(self, text="Velocidade Max:").grid(row=0, column=2, padx=5, pady=2, sticky="w")
        self.vel_max_entry = ttk.Entry(self, width=10)
        self.vel_max_entry.grid(row=1, column=2, padx=5, pady=2)
        self.vel_max_entry.bind('<FocusOut>', self._on_config_changed)
        
        # Adaptative
        ttk.Label(self, text="Margem Adaptativo:").grid(row=0, column=3, padx=5, pady=2, sticky="w")
        self.selected_adaptative = tk.StringVar()
        self.cbx_adaptative = ttk.Combobox(self, textvariable=self.selected_adaptative, width=10)
        self.cbx_adaptative["values"] = ("80%", "90%")
        self.cbx_adaptative["state"] = "readonly"
        self.cbx_adaptative.grid(row=1, column=3, padx=5, pady=2)
        self.cbx_adaptative.bind('<<ComboboxSelected>>', self._on_config_changed)
    
    def _build_temperature_section(self):
        """Build temperature configuration section."""
        # Temperature ac min
        ttk.Label(self, text="Temperatura AC Min:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.temp_ac_min_entry = ttk.Entry(self, width=10)
        self.temp_ac_min_entry.grid(row=3, column=0, padx=5, pady=2)
        self.temp_ac_min_entry.bind('<FocusOut>', self._on_config_changed)
        
        # Temperature ac max
        ttk.Label(self, text="Temperatura AC Max:").grid(row=2, column=1, padx=5, pady=2, sticky="w")
        self.temp_ac_max_entry = ttk.Entry(self, width=10)
        self.temp_ac_max_entry.grid(row=3, column=1, padx=5, pady=2)
        self.temp_ac_max_entry.bind('<FocusOut>', self._on_config_changed)
        
        # Met
        ttk.Label(self, text="Met:").grid(row=2, column=2, padx=5, pady=2, sticky="w")
        self.met_entry = ttk.Entry(self, width=10)
        self.met_entry.grid(row=3, column=2, padx=5, pady=2)
        self.met_entry.bind('<FocusOut>', self._on_config_changed)
        
        # Wme
        ttk.Label(self, text="Wme:").grid(row=2, column=3, padx=5, pady=2, sticky="w")
        self.wme_entry = ttk.Entry(self, width=10)
        self.wme_entry.grid(row=3, column=3, padx=5, pady=2)
        self.wme_entry.bind('<FocusOut>', self._on_config_changed)
    
    def _build_comfort_section(self):
        """Build comfort configuration section."""
        # Comfort bound
        ttk.Label(self, text="Banda de conforto:").grid(row=4, column=0, padx=5, pady=2, sticky="w")
        self.comfort_bound_entry = ttk.Entry(self, width=10)
        self.comfort_bound_entry.grid(row=5, column=0, padx=5, pady=2)
        self.comfort_bound_entry.bind('<FocusOut>', self._on_config_changed)
        
        # CO2 limit
        ttk.Label(self, text="Limite CO2:").grid(row=4, column=1, padx=5, pady=2, sticky="w")
        self.co2_limit_entry = ttk.Entry(self, width=10)
        self.co2_limit_entry.grid(row=5, column=1, padx=5, pady=2)
        self.co2_limit_entry.bind('<FocusOut>', self._on_config_changed)
        
        # Air speed delta
        ttk.Label(self, text="Variação da vel. ventilação:").grid(row=4, column=2, padx=5, pady=2, sticky="w")
        self.air_speed_delta_entry = ttk.Entry(self, width=10)
        self.air_speed_delta_entry.grid(row=5, column=2, padx=5, pady=2)
        self.air_speed_delta_entry.bind('<FocusOut>', self._on_config_changed)
        
        # Temp open window bound
        ttk.Label(self, text="Margem temp. abertura janela:").grid(row=4, column=3, padx=5, pady=2, sticky="w")
        self.temp_open_window_bound_entry = ttk.Entry(self, width=10)
        self.temp_open_window_bound_entry.grid(row=5, column=3, padx=5, pady=2)
        self.temp_open_window_bound_entry.bind('<FocusOut>', self._on_config_changed)
    
    def _build_clothing_section(self):
        """Build clothing configuration section."""
        # Clo min
        ttk.Label(self, text="Clo mínimo:").grid(row=6, column=0, padx=5, pady=2, sticky="w")
        self.clo_min_entry = ttk.Entry(self, width=10)
        self.clo_min_entry.grid(row=7, column=0, padx=5, pady=2)
        self.clo_min_entry.bind('<FocusOut>', self._on_config_changed)
        
        # Clo max
        ttk.Label(self, text="Clo máximo:").grid(row=6, column=1, padx=5, pady=2, sticky="w")
        self.clo_max_entry = ttk.Entry(self, width=10)
        self.clo_max_entry.grid(row=7, column=1, padx=5, pady=2)
        self.clo_max_entry.bind('<FocusOut>', self._on_config_changed)
        
        # Clo delta
        ttk.Label(self, text="Variação do Clo:").grid(row=6, column=2, padx=5, pady=2, sticky="w")
        self.clo_delta_entry = ttk.Entry(self, width=10)
        self.clo_delta_entry.grid(row=7, column=2, padx=5, pady=2)
        self.clo_delta_entry.bind('<FocusOut>', self._on_config_changed)
    
    def _build_rooms_module_section(self):
        """Build rooms and module configuration section."""
        # Rooms
        ttk.Label(self, text="Salas:").grid(row=8, column=0, padx=5, pady=2, sticky="w")
        self.rooms_entry = ttk.Entry(self, width=50)
        self.rooms_entry.grid(row=8, column=1, columnspan=3, padx=5, pady=2, sticky="ew")
        self.rooms_entry.bind('<FocusOut>', self._on_config_changed)
        
        # Module Type
        ttk.Label(self, text="Módulo:").grid(row=9, column=0, padx=5, pady=2, sticky="w")
        self.selected_module = tk.StringVar()
        self.cbx_module = ttk.Combobox(self, textvariable=self.selected_module, width=30)
        self.cbx_module["values"] = [m.value for m in MODULES_MAPPER.keys()]
        self.cbx_module["state"] = "readonly"
        self.cbx_module.grid(row=9, column=1, columnspan=3, padx=5, pady=2, sticky="ew")
        self.cbx_module.bind('<<ComboboxSelected>>', self._on_config_changed)
        
        # Configure column weights for responsiveness
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)
        self.columnconfigure(3, weight=1)
    
    def _on_config_changed(self, event=None):
        """Handle configuration change."""
        if self.callback:
            self.callback.on_simulation_config_changed()
    
    def get_configuration(self) -> dict:
        """Get current configuration as dictionary."""
        try:
            return {
                'pmv_lowerbound': float(self.pmv_lowerbound_entry.get()) if self.pmv_lowerbound_entry.get() else 0.0,
                'pmv_upperbound': float(self.pmv_upperbound_entry.get()) if self.pmv_upperbound_entry.get() else 0.0,
                'max_vel': float(self.vel_max_entry.get()) if self.vel_max_entry.get() else 0.0,
                'adaptative_bound': PORCENT2ADAPTATIVE.get(self.selected_adaptative.get(), 0.8),
                'temp_ac_min': float(self.temp_ac_min_entry.get()) if self.temp_ac_min_entry.get() else 0.0,
                'temp_ac_max': float(self.temp_ac_max_entry.get()) if self.temp_ac_max_entry.get() else 0.0,
                'met': float(self.met_entry.get()) if self.met_entry.get() else 0.0,
                'wme': float(self.wme_entry.get()) if self.wme_entry.get() else 0.0,
                'pmv_comfort_bound': float(self.comfort_bound_entry.get()) if self.comfort_bound_entry.get() else 0.0,
                'co2_limit': float(self.co2_limit_entry.get()) if self.co2_limit_entry.get() else 0.0,
                'air_speed_delta': float(self.air_speed_delta_entry.get()) if self.air_speed_delta_entry.get() else 0.0,
                'temp_open_window_bound': float(self.temp_open_window_bound_entry.get()) if self.temp_open_window_bound_entry.get() else 0.0,
                'clo_min': float(self.clo_min_entry.get()) if self.clo_min_entry.get() else 0.0,
                'clo_max': float(self.clo_max_entry.get()) if self.clo_max_entry.get() else 0.0,
                'clo_delta': float(self.clo_delta_entry.get()) if self.clo_delta_entry.get() else 0.0,
                'rooms': [room.strip() for room in self.rooms_entry.get().split(',') if room.strip()],
                'module_type': ModuleType[self.selected_module.get()] if self.selected_module.get() else None
            }
        except (ValueError, KeyError) as e:
            # Return default values on error
            return {}
    
    def set_configuration(self, config: dict):
        """Set configuration from dictionary."""
        self.pmv_lowerbound_entry.delete(0, tk.END)
        self.pmv_lowerbound_entry.insert(0, str(config.get('pmv_lowerbound', '')))
        
        self.pmv_upperbound_entry.delete(0, tk.END)
        self.pmv_upperbound_entry.insert(0, str(config.get('pmv_upperbound', '')))
        
        self.vel_max_entry.delete(0, tk.END)
        self.vel_max_entry.insert(0, str(config.get('max_vel', '')))
        
        self.selected_adaptative.set(ADAPTATIVE2PORCENT.get(config.get('adaptative_bound', 0.8), '80%'))
        
        self.temp_ac_min_entry.delete(0, tk.END)
        self.temp_ac_min_entry.insert(0, str(config.get('temp_ac_min', '')))
        
        self.temp_ac_max_entry.delete(0, tk.END)
        self.temp_ac_max_entry.insert(0, str(config.get('temp_ac_max', '')))
        
        self.met_entry.delete(0, tk.END)
        self.met_entry.insert(0, str(config.get('met', '')))
        
        self.wme_entry.delete(0, tk.END)
        self.wme_entry.insert(0, str(config.get('wme', '')))
        
        self.comfort_bound_entry.delete(0, tk.END)
        self.comfort_bound_entry.insert(0, str(config.get('pmv_comfort_bound', '')))
        
        self.co2_limit_entry.delete(0, tk.END)
        self.co2_limit_entry.insert(0, str(config.get('co2_limit', '')))
        
        self.air_speed_delta_entry.delete(0, tk.END)
        self.air_speed_delta_entry.insert(0, str(config.get('air_speed_delta', '')))
        
        self.temp_open_window_bound_entry.delete(0, tk.END)
        self.temp_open_window_bound_entry.insert(0, str(config.get('temp_open_window_bound', '')))
        
        self.clo_min_entry.delete(0, tk.END)
        self.clo_min_entry.insert(0, str(config.get('clo_min', '')))
        
        self.clo_max_entry.delete(0, tk.END)
        self.clo_max_entry.insert(0, str(config.get('clo_max', '')))
        
        self.clo_delta_entry.delete(0, tk.END)
        self.clo_delta_entry.insert(0, str(config.get('clo_delta', '')))
        
        rooms = config.get('rooms', [])
        self.rooms_entry.delete(0, tk.END)
        self.rooms_entry.insert(0, ','.join(rooms) if rooms else '')
        
        module_type = config.get('module_type')
        if module_type:
            self.selected_module.set(module_type.value if hasattr(module_type, 'value') else str(module_type))
