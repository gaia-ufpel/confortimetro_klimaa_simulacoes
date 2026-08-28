"""
Simulation configuration panel component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Protocol, Optional, List

from ..theme import SPACE, ChipSelect, RangeField
from confortimetro.control import MODULES_MAPPER
from confortimetro.config import ADAPTATIVE2PORCENT, PORCENT2ADAPTATIVE
from confortimetro.module_type import ModuleType


# Rótulos do combobox: o nome do enum não diz o que cada módulo faz.
MODULE_LABELS = {
    ModuleType.COMPLETE:
        "Completo (janela, ventilador e ar-condicionado)",
    ModuleType.WITHOUT_FAN:
        "Sem ventilador (janela e ar-condicionado)",
    ModuleType.FIXED_AC_WITHOUT_FAN:
        "Ar-condicionado fixo (janela e AC com setpoint fixo, sem ventilador)",
    ModuleType.CLOSED_WINDOW:
        "Janela fechada (ventilador e ar-condicionado)",
}
LABEL2MODULE = {label: module for module, label in MODULE_LABELS.items()}


class SimulationConfigCallback(Protocol):
    """Protocol for simulation configuration callbacks."""
    
    def on_simulation_config_changed(self) -> None:
        """Called when simulation configuration is changed."""
        ...


class SimulationConfigPanel(ttk.Frame):
    """Panel for simulation configuration."""
    
    def __init__(self, parent, callback: Optional[SimulationConfigCallback] = None):
        super().__init__(parent, style="Card.TFrame")
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
                               padding=SPACE[3])
        frame.pack(fill="x", pady=(0, SPACE[3]))
        for column in range(4):
            frame.columnconfigure(column, weight=1, uniform="fields")
        return frame

    def _range(self, parent, column: int, label: str, lower: float,
               upper: float, step: float = 0.1) -> RangeField:
        """Create a min-max range spanning two columns of `parent`."""
        field = RangeField(parent, label, lower, upper, step,
                           on_change=self._on_config_changed)
        field.grid(row=0, column=column, columnspan=2, rowspan=2,
                   padx=SPACE[1], pady=(0, SPACE[2]), sticky="ew")
        return field

    def _field(self, parent, column: int, label: str) -> ttk.Entry:
        """Create a labeled entry in `column` of `parent`."""
        ttk.Label(parent, text=label, style="Label.TLabel").grid(
            row=0, column=column, padx=SPACE[1], pady=(0, SPACE[1]), sticky="w")
        entry = ttk.Entry(parent, style="Field.TEntry")
        entry.grid(row=1, column=column, padx=SPACE[1], pady=(0, SPACE[2]),
                   sticky="ew")
        entry.bind('<FocusOut>', self._on_config_changed)
        return entry

    def _build_pmv_section(self):
        """Build PMV configuration section."""
        section = self._section("Conforto PMV")

        # Faixa do PMV na escala ASHRAE (-3 frio … +3 quente).
        self.pmv_range = self._range(section, 0, "Faixa de PMV", -3.0, 3.0)
        self.pmv_lowerbound_entry = self.pmv_range.min_entry
        self.pmv_upperbound_entry = self.pmv_range.max_entry

        self.vel_max_entry = self._field(section, 2, "Velocidade máxima")

        ttk.Label(section, text="Margem do adaptativo", style="Label.TLabel").grid(
            row=0, column=3, padx=SPACE[1], pady=(0, SPACE[1]), sticky="w")
        self.selected_adaptative = tk.StringVar()
        self.cbx_adaptative = ttk.Combobox(
            section, textvariable=self.selected_adaptative,
            style="Field.TCombobox")
        self.cbx_adaptative["values"] = ("80%", "90%")
        self.cbx_adaptative["state"] = "readonly"
        self.cbx_adaptative.grid(row=1, column=3, padx=SPACE[1], pady=SPACE[1], sticky="ew")
        self.cbx_adaptative.bind('<<ComboboxSelected>>', self._on_config_changed)

    def _build_temperature_section(self):
        """Build temperature configuration section."""
        section = self._section("Condicionamento e metabolismo")

        self.temp_ac_range = self._range(
            section, 0, "Faixa de temperatura do AC (°C)", 10.0, 35.0, 0.5)
        self.temp_ac_min_entry = self.temp_ac_range.min_entry
        self.temp_ac_max_entry = self.temp_ac_range.max_entry

        self.met_entry = self._field(section, 2, "Met")
        self.wme_entry = self._field(section, 3, "Wme")

    def _build_comfort_section(self):
        """Build comfort configuration section."""
        section = self._section("Conforto e qualidade do ar")

        self.comfort_bound_entry = self._field(section, 0, "Banda de conforto")
        self.co2_limit_entry = self._field(section, 1, "Limite de CO2")
        self.air_speed_delta_entry = self._field(
            section, 2, "Variação da vel. de ventilação")
        self.temp_open_window_bound_entry = self._field(
            section, 3, "Margem de temp. p/ abrir janela")

    def _build_clothing_section(self):
        """Build clothing configuration section."""
        section = self._section("Vestimenta (Clo)")

        self.clo_range = self._range(section, 0, "Faixa de Clo", 0.0, 2.0, 0.05)
        self.clo_min_entry = self.clo_range.min_entry
        self.clo_max_entry = self.clo_range.max_entry

        self.clo_delta_entry = self._field(section, 2, "Variação do Clo")

        # Prioridade do Clo sobre os equipamentos
        self.clo_priority_var = tk.BooleanVar(value=True)
        self.clo_priority_check = ttk.Checkbutton(
            section, text="Ajustar Clo antes dos equipamentos",
            variable=self.clo_priority_var, command=self._on_config_changed,
            style="Card.TCheckbutton")
        self.clo_priority_check.grid(row=1, column=3, padx=SPACE[1], pady=SPACE[1], sticky="w")

    def _build_rooms_module_section(self):
        """Build rooms and module configuration section."""
        section = self._section("Zonas e módulo de condicionamento")

        ttk.Label(section, text="Salas", style="Label.TLabel").grid(
            row=0, column=0, columnspan=2, padx=SPACE[1], sticky="w")
        self.rooms_select = ChipSelect(section, "Selecione uma sala…",
                                       on_change=self._on_config_changed)
        self.rooms_select.grid(row=1, column=0, columnspan=2, padx=SPACE[1],
                               pady=(SPACE[1], SPACE[2]), sticky="ew")

        ttk.Label(section, text="Módulo", style="Label.TLabel").grid(
            row=0, column=2, columnspan=2, padx=SPACE[1], sticky="w")
        self.selected_module = tk.StringVar()
        self.cbx_module = ttk.Combobox(section, textvariable=self.selected_module,
                                       style="Field.TCombobox")
        self.cbx_module["values"] = [MODULE_LABELS[m] for m in MODULES_MAPPER]
        self.cbx_module["state"] = "readonly"
        self.cbx_module.grid(row=1, column=2, columnspan=2, padx=SPACE[1],
                             pady=(SPACE[1], SPACE[2]), sticky="new")
        self.cbx_module.bind('<<ComboboxSelected>>', self._on_config_changed)

    def set_room_options(self, rooms):
        """Zonas oferecidas no seletor de salas (lidas do IDF escolhido)."""
        self.rooms_select.set_options(rooms)

    def _on_config_changed(self, event=None):
        """Handle configuration change."""
        if self.callback:
            self.callback.on_simulation_config_changed()
    
    def get_configuration(self) -> dict:
        """Get current configuration as dictionary."""
        try:
            return {
                'pmv_lowerbound': self.pmv_range.get()[0],
                'pmv_upperbound': self.pmv_range.get()[1],
                'max_vel': float(self.vel_max_entry.get()) if self.vel_max_entry.get() else 0.0,
                'adaptative_bound': PORCENT2ADAPTATIVE.get(self.selected_adaptative.get(), 0.8),
                'temp_ac_min': self.temp_ac_range.get()[0],
                'temp_ac_max': self.temp_ac_range.get()[1],
                'met': float(self.met_entry.get()) if self.met_entry.get() else 0.0,
                'wme': float(self.wme_entry.get()) if self.wme_entry.get() else 0.0,
                'pmv_comfort_bound': float(self.comfort_bound_entry.get()) if self.comfort_bound_entry.get() else 0.0,
                'co2_limit': float(self.co2_limit_entry.get()) if self.co2_limit_entry.get() else 0.0,
                'air_speed_delta': float(self.air_speed_delta_entry.get()) if self.air_speed_delta_entry.get() else 0.0,
                'temp_open_window_bound': float(self.temp_open_window_bound_entry.get()) if self.temp_open_window_bound_entry.get() else 0.0,
                'clo_min': self.clo_range.get()[0],
                'clo_max': self.clo_range.get()[1],
                'clo_delta': float(self.clo_delta_entry.get()) if self.clo_delta_entry.get() else 0.0,
                'clo_priority': bool(self.clo_priority_var.get()),
                'rooms': self.rooms_select.get_values(),
                'module_type': LABEL2MODULE.get(self.selected_module.get())
            }
        except (ValueError, KeyError) as e:
            # Return default values on error
            return {}
    
    def set_configuration(self, config: dict):
        """Set configuration from dictionary."""
        self.pmv_range.set(config.get('pmv_lowerbound', -0.5),
                           config.get('pmv_upperbound', 0.5))
        
        self.vel_max_entry.delete(0, tk.END)
        self.vel_max_entry.insert(0, str(config.get('max_vel', '')))
        
        self.selected_adaptative.set(ADAPTATIVE2PORCENT.get(config.get('adaptative_bound', 0.8), '80%'))
        
        self.temp_ac_range.set(config.get('temp_ac_min', 16.0),
                               config.get('temp_ac_max', 30.0))
        
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
        
        self.clo_range.set(config.get('clo_min', 0.5),
                           config.get('clo_max', 1.0))
        
        self.clo_delta_entry.delete(0, tk.END)
        self.clo_delta_entry.insert(0, str(config.get('clo_delta', '')))

        self.clo_priority_var.set(bool(config.get('clo_priority', True)))
        
        self.rooms_select.set_values(config.get('rooms', []))
        
        module_type = config.get('module_type')
        if module_type:
            module_type = ModuleType(str(module_type))
            self.selected_module.set(MODULE_LABELS.get(module_type, ''))
