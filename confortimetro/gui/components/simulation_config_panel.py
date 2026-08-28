"""
Simulation configuration panel component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Protocol, Optional, List

from confortimetro.control import MODULES_MAPPER
from confortimetro.config import ADAPTATIVE2PORCENT, PORCENT2ADAPTATIVE
from confortimetro.module_type import ModuleType


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
        """Build the UI components, one LabelFrame per logical section."""
        self._build_pmv_section()
        self._build_temperature_section()
        self._build_comfort_section()
        self._build_clothing_section()
        self._build_rooms_module_section()

    def _section(self, title: str) -> ttk.LabelFrame:
        """Create a titled section that stretches with the window."""
        frame = ttk.LabelFrame(self, text=title, style="Section.TLabelframe",
                               padding=10)
        frame.pack(fill="x", pady=(0, 10))
        for column in range(4):
            frame.columnconfigure(column, weight=1, uniform="fields")
        return frame

    def _field(self, parent, column: int, label: str) -> ttk.Entry:
        """Create a labeled entry in `column` of `parent`."""
        ttk.Label(parent, text=label, style="Body.TLabel").grid(
            row=0, column=column, padx=5, pady=(0, 2), sticky="w")
        entry = ttk.Entry(parent, style="Modern.TEntry")
        entry.grid(row=1, column=column, padx=5, pady=2, sticky="ew")
        entry.bind('<FocusOut>', self._on_config_changed)
        return entry

    def _build_pmv_section(self):
        """Build PMV configuration section."""
        section = self._section("Conforto PMV")

        self.pmv_lowerbound_entry = self._field(section, 0, "PMV Min:")
        self.pmv_upperbound_entry = self._field(section, 1, "PMV Max:")
        self.vel_max_entry = self._field(section, 2, "Velocidade Max:")

        ttk.Label(section, text="Margem Adaptativo:", style="Body.TLabel").grid(
            row=0, column=3, padx=5, pady=(0, 2), sticky="w")
        self.selected_adaptative = tk.StringVar()
        self.cbx_adaptative = ttk.Combobox(
            section, textvariable=self.selected_adaptative,
            style="Modern.TCombobox")
        self.cbx_adaptative["values"] = ("80%", "90%")
        self.cbx_adaptative["state"] = "readonly"
        self.cbx_adaptative.grid(row=1, column=3, padx=5, pady=2, sticky="ew")
        self.cbx_adaptative.bind('<<ComboboxSelected>>', self._on_config_changed)

    def _build_temperature_section(self):
        """Build temperature configuration section."""
        section = self._section("Condicionamento e metabolismo")

        self.temp_ac_min_entry = self._field(section, 0, "Temperatura AC Min:")
        self.temp_ac_max_entry = self._field(section, 1, "Temperatura AC Max:")
        self.met_entry = self._field(section, 2, "Met:")
        self.wme_entry = self._field(section, 3, "Wme:")

    def _build_comfort_section(self):
        """Build comfort configuration section."""
        section = self._section("Conforto e qualidade do ar")

        self.comfort_bound_entry = self._field(section, 0, "Banda de conforto:")
        self.co2_limit_entry = self._field(section, 1, "Limite CO2:")
        self.air_speed_delta_entry = self._field(
            section, 2, "Variação da vel. ventilação:")
        self.temp_open_window_bound_entry = self._field(
            section, 3, "Margem temp. abertura janela:")

    def _build_clothing_section(self):
        """Build clothing configuration section."""
        section = self._section("Vestimenta (Clo)")

        self.clo_min_entry = self._field(section, 0, "Clo mínimo:")
        self.clo_max_entry = self._field(section, 1, "Clo máximo:")
        self.clo_delta_entry = self._field(section, 2, "Variação do Clo:")

        # Prioridade do Clo sobre os equipamentos
        self.clo_priority_var = tk.BooleanVar(value=True)
        self.clo_priority_check = ttk.Checkbutton(
            section, text="Ajustar Clo antes dos equipamentos",
            variable=self.clo_priority_var, command=self._on_config_changed)
        self.clo_priority_check.grid(row=1, column=3, padx=5, pady=2, sticky="w")

    def _build_rooms_module_section(self):
        """Build rooms and module configuration section."""
        section = self._section("Zonas e módulo de condicionamento")

        ttk.Label(section, text="Salas:", style="Body.TLabel").grid(
            row=0, column=0, padx=5, pady=2, sticky="w")
        self.rooms_entry = ttk.Entry(section, style="Modern.TEntry")
        self.rooms_entry.grid(row=0, column=1, columnspan=3, padx=5, pady=2,
                              sticky="ew")
        self.rooms_entry.bind('<FocusOut>', self._on_config_changed)

        ttk.Label(section, text="Módulo:", style="Body.TLabel").grid(
            row=1, column=0, padx=5, pady=2, sticky="w")
        self.selected_module = tk.StringVar()
        self.cbx_module = ttk.Combobox(section, textvariable=self.selected_module,
                                       style="Modern.TCombobox")
        self.cbx_module["values"] = [m.value for m in MODULES_MAPPER.keys()]
        self.cbx_module["state"] = "readonly"
        self.cbx_module.grid(row=1, column=1, columnspan=3, padx=5, pady=2,
                             sticky="ew")
        self.cbx_module.bind('<<ComboboxSelected>>', self._on_config_changed)

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
                'clo_priority': bool(self.clo_priority_var.get()),
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

        self.clo_priority_var.set(bool(config.get('clo_priority', True)))
        
        rooms = config.get('rooms', [])
        self.rooms_entry.delete(0, tk.END)
        self.rooms_entry.insert(0, ','.join(rooms) if rooms else '')
        
        module_type = config.get('module_type')
        if module_type:
            self.selected_module.set(module_type.value if hasattr(module_type, 'value') else str(module_type))
