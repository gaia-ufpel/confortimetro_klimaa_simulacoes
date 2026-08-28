"""
Control panel component.
"""

import tkinter as tk
from tkinter import ttk
from typing import Protocol, Optional


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
        super().__init__(parent)
        self.callback = callback
        self.is_running = False
        self._build_ui()
    
    def _build_ui(self):
        """Build the UI components with modern styling."""
        # Main control buttons with improved layout
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=0, pady=0)
        
        # Button container for centering
        button_container = ttk.Frame(button_frame)
        button_container.pack(anchor="center", pady=20)
        
        # Run/Stop button - Primary action
        self.run_button = ttk.Button(
            button_container, 
            text="▶️ Executar Simulação", 
            width=25,
            style="Primary.TButton",
            command=self._on_run_clicked
        )
        self.run_button.pack(side="left", padx=10)
        
        # Secondary actions frame
        secondary_frame = ttk.Frame(button_container)
        secondary_frame.pack(side="left", padx=(30, 0))
        
        # Save config button
        self.save_button = ttk.Button(
            secondary_frame, 
            text="💾 Salvar", 
            width=15,
            style="Outline.TButton",
            command=self._on_save_clicked
        )
        self.save_button.pack(side="top", pady=(0, 5))
        
        # Load config button
        self.load_button = ttk.Button(
            secondary_frame, 
            text="📂 Carregar", 
            width=15,
            style="Outline.TButton",
            command=self._on_load_clicked
        )
        self.load_button.pack(side="top")
        
        # Status and progress section
        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # Status indicator
        status_container = ttk.Frame(status_frame)
        status_container.pack(anchor="center")
        
        # Status label with icon
        status_label_frame = ttk.Frame(status_container)
        status_label_frame.pack(pady=(0, 10))
        
        self.status_icon = ttk.Label(status_label_frame, text="✅", font=('Segoe UI', 12))
        self.status_icon.pack(side="left", padx=(0, 5))
        
        self.progress_var = tk.StringVar()
        self.progress_var.set("Pronto para executar")
        
        self.status_label = ttk.Label(
            status_label_frame, 
            textvariable=self.progress_var,
            style="Body.TLabel",
            font=('Segoe UI', 10, 'bold')
        )
        self.status_label.pack(side="left")
        
        # Progress bar with modern styling
        self.progress_bar = ttk.Progressbar(
            status_container, 
            mode='indeterminate',
            length=300,
            style="Modern.Horizontal.TProgressbar"
        )
        self.progress_bar.pack(pady=5)
    
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
            # Update button for stop action
            self.run_button.config(
                text="⏹️ Parar Simulação", 
                style="Danger.TButton"
            )
            
            # Disable secondary buttons
            self.save_button.config(state="disabled")
            self.load_button.config(state="disabled")
            
            # Update status
            self.progress_bar.start(10)  # Start animation
            self.progress_var.set("Executando simulação...")
            self.status_icon.config(text="⚙️")
            
        else:
            # Update button for run action
            self.run_button.config(
                text="▶️ Executar Simulação", 
                style="Primary.TButton"
            )
            
            # Enable secondary buttons
            self.save_button.config(state="normal")
            self.load_button.config(state="normal")
            
            # Update status
            self.progress_bar.stop()  # Stop animation
            self.progress_var.set("Pronto para executar")
            self.status_icon.config(text="✅")
    
    def set_status(self, status: str, status_type: str = "info"):
        """
        Set the status message with appropriate icon.
        
        Args:
            status: Status message to display
            status_type: Type of status ('info', 'success', 'warning', 'error')
        """
        icons = {
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌',
            'running': '⚙️'
        }
        
        self.progress_var.set(status)
        self.status_icon.config(text=icons.get(status_type, 'ℹ️'))
    
    def enable_buttons(self, enabled: bool = True):
        """
        Enable or disable all buttons.
        
        Args:
            enabled: Whether to enable the buttons
        """
        state = "normal" if enabled else "disabled"
        
        if not self.is_running:  # Only enable if not running
            self.run_button.config(state=state)
            self.save_button.config(state=state)
            self.load_button.config(state=state)
    
    def get_is_running(self) -> bool:
        """Check if simulation is running."""
        return self.is_running
