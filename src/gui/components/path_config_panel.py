"""
Path configuration panel component.
"""

import tkinter as tk
from tkinter import filedialog, ttk
from typing import Protocol, Optional


class PathConfigCallback(Protocol):
    """Protocol for path configuration callbacks."""
    
    def on_idf_path_changed(self, path: str) -> None:
        """Called when IDF path is changed."""
        ...
    
    def on_output_path_changed(self, path: str) -> None:
        """Called when output path is changed."""
        ...
    
    def on_epw_path_changed(self, path: str) -> None:
        """Called when EPW path is changed."""
        ...
    
    def on_energy_path_changed(self, path: str) -> None:
        """Called when Energy path is changed."""
        ...


class PathConfigPanel(ttk.Frame):
    """Panel for path configuration."""
    
    def __init__(self, parent, callback: Optional[PathConfigCallback] = None):
        super().__init__(parent)
        self.callback = callback
        self._build_ui()
    
    def _build_ui(self):
        """Build the UI components with modern styling."""
        # Configure grid weights for responsive layout
        self.grid_columnconfigure(0, weight=1)
        
        # Create path input fields with better styling
        self._create_path_field(
            row=0, 
            label="📄 Arquivo IDF:",
            entry_var_name="inputfile_entry",
            browse_command=self._browse_idf,
            change_callback=self._on_idf_changed,
            tooltip="Arquivo de entrada do modelo EnergyPlus (.idf)"
        )
        
        self._create_path_field(
            row=2,
            label="📁 Diretório de Saída:",
            entry_var_name="outputfolder_entry", 
            browse_command=self._browse_output,
            change_callback=self._on_output_changed,
            tooltip="Pasta onde os resultados serão salvos"
        )
        
        self._create_path_field(
            row=4,
            label="🌤️ Arquivo Climático (EPW):",
            entry_var_name="epwfile_entry",
            browse_command=self._browse_weather,
            change_callback=self._on_epw_changed,
            tooltip="Arquivo de dados climáticos (.epw)"
        )
        
        self._create_path_field(
            row=6,
            label="⚡ Caminho do EnergyPlus:",
            entry_var_name="energy_path_entry",
            browse_command=self._browse_energy,
            change_callback=self._on_energy_changed,
            tooltip="Diretório de instalação do EnergyPlus"
        )
    
    def _create_path_field(self, row, label, entry_var_name, browse_command, change_callback, tooltip=""):
        """Create a styled path input field."""
        # Label
        label_widget = ttk.Label(self, text=label, style="Body.TLabel")
        label_widget.grid(row=row, column=0, sticky="w", padx=(0, 10), pady=(10, 5))
        
        # Create tooltip if provided
        if tooltip:
            self._create_tooltip(label_widget, tooltip)
        
        # Input field container
        input_frame = ttk.Frame(self)
        input_frame.grid(row=row+1, column=0, sticky="ew", padx=(0, 10), pady=(0, 15))
        input_frame.grid_columnconfigure(0, weight=1)
        
        # Entry field
        entry = ttk.Entry(input_frame, style="Modern.TEntry", font=('Segoe UI', 9))
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        entry.bind('<FocusOut>', change_callback)
        entry.bind('<KeyRelease>', lambda e: self._validate_path(entry))
        
        # Browse button
        browse_btn = ttk.Button(
            input_frame,
            text="📂 Procurar",
            style="Outline.TButton",
            command=browse_command,
            width=12
        )
        browse_btn.grid(row=0, column=1)
        
        # Store reference to entry
        setattr(self, entry_var_name, entry)
        
        # Status indicator (will show validation feedback)
        status_label = ttk.Label(input_frame, text="", font=('Segoe UI', 8))
        status_label.grid(row=1, column=0, sticky="w", pady=(2, 0))
        setattr(self, f"{entry_var_name}_status", status_label)
    
    def _create_tooltip(self, widget, text):
        """Create a simple tooltip for a widget."""
        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = ttk.Label(tooltip, text=text, style="Muted.TLabel", 
                             background="#f0f0f0", relief="solid", borderwidth=1)
            label.pack()
            
            # Auto-hide after 3 seconds
            tooltip.after(3000, tooltip.destroy)
        
        widget.bind('<Enter>', show_tooltip)
    
    def _validate_path(self, entry):
        """Validate path and show visual feedback."""
        import os
        
        path = entry.get().strip()
        if not path:
            return
        
        # Get the corresponding status label
        entry_name = None
        for attr_name in dir(self):
            if getattr(self, attr_name, None) is entry:
                entry_name = attr_name
                break
        
        if not entry_name:
            return
        
        status_label = getattr(self, f"{entry_name}_status", None)
        if not status_label:
            return
        
        # Validate based on entry type
        if "file" in entry_name:
            # File validation
            if os.path.isfile(path):
                status_label.config(text="✅ Arquivo encontrado", foreground="#22c55e")
                entry.config(style="Modern.TEntry")
            else:
                status_label.config(text="❌ Arquivo não encontrado", foreground="#ef4444")
                # Could add error styling here
        else:
            # Directory validation  
            if os.path.isdir(path):
                status_label.config(text="✅ Diretório válido", foreground="#22c55e")
                entry.config(style="Modern.TEntry")
            else:
                status_label.config(text="❌ Diretório não encontrado", foreground="#ef4444")
    
    def _browse_idf(self):
        """Browse for IDF file."""
        filename = filedialog.askopenfilename(
            initialdir=".", 
            title="Select IDF File", 
            filetypes=(("IDF Files", "*.idf"), ("all files", "*.*"))
        )
        if filename:
            self.inputfile_entry.delete(0, tk.END)
            self.inputfile_entry.insert(0, filename)
            self._on_idf_changed()
    
    def _browse_output(self):
        """Browse for output directory."""
        filename = filedialog.askdirectory(
            initialdir=".", 
            title="Select Output Folder"
        )
        if filename:
            self.outputfolder_entry.delete(0, 'end')
            self.outputfolder_entry.insert(0, filename)
            self._on_output_changed()
    
    def _browse_weather(self):
        """Browse for weather file."""
        filename = filedialog.askopenfilename(
            initialdir=".", 
            title="Select Weather File", 
            filetypes=(("EPW Files", "*.epw"), ("all files", "*.*"))
        )
        if filename:
            self.epwfile_entry.delete(0, 'end')
            self.epwfile_entry.insert(0, filename)
            self._on_epw_changed()
    
    def _browse_energy(self):
        """Browse for Energy directory."""
        filename = filedialog.askdirectory(
            initialdir=".", 
            title="Select Energy Folder"
        )
        if filename:
            self.energy_path_entry.delete(0, 'end')
            self.energy_path_entry.insert(0, filename)
            self._on_energy_changed()
    
    def _on_idf_changed(self, event=None):
        """Handle IDF path change."""
        if self.callback:
            self.callback.on_idf_path_changed(self.inputfile_entry.get())
    
    def _on_output_changed(self, event=None):
        """Handle output path change."""
        if self.callback:
            self.callback.on_output_path_changed(self.outputfolder_entry.get())
    
    def _on_epw_changed(self, event=None):
        """Handle EPW path change."""
        if self.callback:
            self.callback.on_epw_path_changed(self.epwfile_entry.get())
    
    def _on_energy_changed(self, event=None):
        """Handle energy path change."""
        if self.callback:
            self.callback.on_energy_path_changed(self.energy_path_entry.get())
    
    def set_idf_path(self, path: str):
        """Set IDF path."""
        self.inputfile_entry.delete(0, tk.END)
        self.inputfile_entry.insert(0, path)
    
    def set_output_path(self, path: str):
        """Set output path."""
        self.outputfolder_entry.delete(0, tk.END)
        self.outputfolder_entry.insert(0, path)
    
    def set_epw_path(self, path: str):
        """Set EPW path."""
        self.epwfile_entry.delete(0, tk.END)
        self.epwfile_entry.insert(0, path)
    
    def set_energy_path(self, path: str):
        """Set energy path."""
        self.energy_path_entry.delete(0, tk.END)
        self.energy_path_entry.insert(0, path)
    
    def get_idf_path(self) -> str:
        """Get IDF path."""
        return self.inputfile_entry.get()
    
    def get_output_path(self) -> str:
        """Get output path."""
        return self.outputfolder_entry.get()
    
    def get_epw_path(self) -> str:
        """Get EPW path."""
        return self.epwfile_entry.get()
    
    def get_energy_path(self) -> str:
        """Get energy path."""
        return self.energy_path_entry.get()
