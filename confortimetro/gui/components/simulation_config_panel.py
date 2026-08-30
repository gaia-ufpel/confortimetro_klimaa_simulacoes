"""
Simulation configuration panel component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Protocol, Optional

from ..theme import SPACE, ChipSelect, RangeField
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
        super().__init__(parent, style="Surface.TFrame")
        self.callback = callback
        self._build_ui()
    
    def _build_ui(self):
        """Build the UI components: one notebook tab per logical group."""
        self.notebook = ttk.Notebook(self, style="Section.TNotebook")
        self.notebook.pack(fill="both", expand=True)
        self._build_comfort_tab()
        self._build_equipment_tab()
        self._build_rooms_module_tab()

    def _tab(self, title: str) -> ttk.Frame:
        """Create a notebook tab whose four columns share the width."""
        frame = ttk.Frame(self.notebook, style="Surface.TFrame",
                          padding=SPACE[3])
        self.notebook.add(frame, text=title)
        for column in range(4):
            frame.columnconfigure(column, weight=1, uniform="fields")
        return frame

    def _range(self, parent, row: int, column: int, label: str, lower: float,
               upper: float, step: float = 0.1) -> RangeField:
        """Create a min-max range spanning two columns of `parent`."""
        field = RangeField(parent, label, lower, upper, step,
                           on_change=self._on_config_changed)
        field.grid(row=row, column=column, columnspan=2, rowspan=2,
                   padx=SPACE[1], pady=(0, SPACE[2]), sticky="ew")
        return field

    def _field(self, parent, row: int, column: int, label: str) -> ttk.Entry:
        """Create a labeled entry in `column` of `parent`."""
        ttk.Label(parent, text=label, style="Label.TLabel").grid(
            row=row, column=column, padx=SPACE[1], pady=(0, SPACE[1]),
            sticky="w")
        entry = ttk.Entry(parent, style="Field.TEntry")
        entry.grid(row=row + 1, column=column, padx=SPACE[1],
                   pady=(0, SPACE[2]), sticky="ew")
        entry.bind('<FocusOut>', self._on_config_changed)
        return entry

    def _combo(self, parent, row: int, column: int, label: str, values,
               variable: tk.StringVar, columnspan: int = 1) -> ttk.Combobox:
        """Create a labeled read-only combobox in `column` of `parent`."""
        ttk.Label(parent, text=label, style="Label.TLabel").grid(
            row=row, column=column, columnspan=columnspan, padx=SPACE[1],
            pady=(0, SPACE[1]), sticky="w")
        combo = ttk.Combobox(parent, textvariable=variable,
                             style="Field.TCombobox", state="readonly",
                             values=values)
        combo.grid(row=row + 1, column=column, columnspan=columnspan,
                   padx=SPACE[1], pady=(0, SPACE[2]), sticky="ew")
        combo.bind('<<ComboboxSelected>>', self._on_config_changed)
        return combo

    def _build_comfort_tab(self):
        """PMV, metabolismo e vestimenta: as entradas do conforto do ocupante."""
        tab = self._tab("Conforto")

        # Faixa do PMV na escala ASHRAE (-3 frio … +3 quente).
        self.pmv_range = self._range(tab, 0, 0, "Faixa de PMV", -3.0, 3.0)
        self.comfort_bound_entry = self._field(tab, 0, 2, "Banda de conforto")

        self.met_entry = self._field(tab, 2, 0, "Met")
        self.wme_entry = self._field(tab, 2, 1, "Wme")
        self.selected_adaptative = tk.StringVar()
        self.cbx_adaptative = self._combo(tab, 2, 2, "Margem do adaptativo",
                                          ("80%", "90%"),
                                          self.selected_adaptative)

        self.clo_range = self._range(tab, 4, 0, "Faixa de Clo", 0.0, 2.0, 0.05)
        self.clo_delta_entry = self._field(tab, 4, 2, "Variação do Clo")

        # Prioridade do Clo sobre os equipamentos
        self.clo_priority_var = tk.BooleanVar(value=True)
        self.clo_priority_check = ttk.Checkbutton(
            tab, text="Ajustar Clo antes dos equipamentos",
            variable=self.clo_priority_var, command=self._on_config_changed,
            style="Card.TCheckbutton")
        self.clo_priority_check.grid(row=5, column=3, padx=SPACE[1],
                                     pady=(0, SPACE[2]), sticky="w")

    def _build_equipment_tab(self):
        """Ar-condicionado, ventilação e janela: o que o módulo aciona."""
        tab = self._tab("Equipamentos")

        self.temp_ac_range = self._range(
            tab, 0, 0, "Faixa de temperatura do AC (°C)", 10.0, 35.0, 0.5)
        self.vel_max_entry = self._field(tab, 0, 2, "Velocidade máxima")
        self.air_speed_delta_entry = self._field(
            tab, 0, 3, "Variação da vel. de ventilação")

        self.temp_open_window_bound_entry = self._field(
            tab, 2, 0, "Margem de temp. p/ abrir janela")
        self.co2_limit_entry = self._field(tab, 2, 1, "Limite de CO2")

    def _build_rooms_module_tab(self):
        """Zonas simuladas e módulo de condicionamento."""
        tab = self._tab("Zonas")

        ttk.Label(tab, text="Salas", style="Label.TLabel").grid(
            row=0, column=0, columnspan=2, padx=SPACE[1], sticky="w")
        self.rooms_select = ChipSelect(tab, "Selecione uma sala…",
                                       on_change=self._on_config_changed)
        self.rooms_select.grid(row=1, column=0, columnspan=2, padx=SPACE[1],
                               pady=(SPACE[1], SPACE[2]), sticky="ew")

        self.selected_module = tk.StringVar()
        self.cbx_module = self._combo(tab, 0, 2, "Módulo",
                                      list(MODULE_LABELS.values()),
                                      self.selected_module, columnspan=2)

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
