"""
Control panel component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Protocol, Optional

from ..theme import SPACE, RoundedButton, StatusPill


class ControlPanelCallback(Protocol):
    """Protocol for control panel callbacks."""
    
    def on_run_simulation(self) -> None:
        """Called when run simulation is requested."""
        ...
    
    def on_stop_simulation(self) -> None:
        """Called when stop simulation is requested."""
        ...
    
    def on_save_config(self) -> None:
        """Called when save configuration is requested."""
        ...
    
    def on_load_config(self) -> None:
        """Called when load configuration is requested."""
        ...


class ControlPanel(ttk.Frame):
    """Panel for simulation controls."""
    
    def __init__(self, parent, callback: Optional[ControlPanelCallback] = None):
        super().__init__(parent, style="Card.TFrame")
        self.callback = callback
        self.is_running = False
        self._build_ui()
    
    def _build_ui(self):
        """Build the topbar row: actions on the left, status on the right."""
        row = ttk.Frame(self, style="Card.TFrame")
        row.pack(fill="x")

        self.run_button = RoundedButton(
            row, text="Executar simulação", variant="primary", width=200,
            command=self._on_run_clicked)
        self.run_button.pack(side="left")

        self.save_button = RoundedButton(
            row, text="Salvar", variant="ghost", width=110,
            command=self._on_save_clicked)
        self.save_button.pack(side="left", padx=(SPACE[2], 0))

        self.load_button = RoundedButton(
            row, text="Carregar", variant="ghost", width=110,
            command=self._on_load_clicked)
        self.load_button.pack(side="left", padx=(SPACE[2], 0))

        self.status_pill = StatusPill(row, "Pronto para executar", "info")
        self.status_pill.pack(side="right")

        # Só aparece durante a execução — barra parada não informa nada.
        self.progress_bar = ttk.Progressbar(
            self, mode="indeterminate",
            style="Modern.Horizontal.TProgressbar")

    def _on_run_clicked(self):
        """Handle run button click."""
        if self.is_running:
            if self.callback:
                self.callback.on_stop_simulation()
        else:
            if self.callback:
                self.callback.on_run_simulation()
    
    def _on_save_clicked(self):
        """Handle save button click."""
        if self.callback:
            self.callback.on_save_config()
    
    def _on_load_clicked(self):
        """Handle load button click."""
        if self.callback:
            self.callback.on_load_config()
    
    def set_running_state(self, is_running: bool):
        """
        Set the running state of the simulation with visual feedback.

        Args:
            is_running: Whether simulation is currently running
        """
        self.is_running = is_running

        if is_running:
            self.run_button.configure(text="Parar simulação", variant="danger")
            self.save_button.configure(state="disabled")
            self.load_button.configure(state="disabled")
            self.progress_bar.pack(fill="x", pady=(SPACE[3], 0))
            self.progress_bar.start(10)
            self.set_status("Executando simulação...", "running")
        else:
            self.run_button.configure(text="Executar simulação",
                                      variant="primary")
            self.save_button.configure(state="normal")
            self.load_button.configure(state="normal")
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.set_status("Pronto para executar", "info")

    def set_status(self, status: str, status_type: str = "info"):
        """
        Set the status message.

        Args:
            status: Status message to display
            status_type: 'info', 'success', 'warning', 'error' or 'running'
        """
        self.status_pill.set(status, status_type)

    def enable_buttons(self, enabled: bool = True):
        """
        Enable or disable all buttons.
        
        Args:
            enabled: Whether to enable the buttons
        """
        state = "normal" if enabled else "disabled"

        if not self.is_running:  # Only enable if not running
            self.run_button.configure(state=state)
            self.save_button.configure(state=state)
            self.load_button.configure(state=state)
    
    def get_is_running(self) -> bool:
        """Check if simulation is running."""
        return self.is_running
