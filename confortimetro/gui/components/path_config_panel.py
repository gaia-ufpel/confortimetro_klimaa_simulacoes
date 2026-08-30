"""
Path configuration panel component.
"""

import os
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Protocol, Optional

from ..theme import COLORS, SPACE, RoundedButton, icon
from confortimetro.config import (
    REQUIRED_EP_API_VERSION,
    REQUIRED_EP_VERSION,
    energy_api_version,
    energy_path_version,
    find_energy_path,
    is_energy_path,
)


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


#: Todos os campos de caminho, na ordem em que aparecem. A chave é o que
#: `PathConfigPanel(fields=...)` seleciona: a tela principal mostra os
#: caminhos que mudam a cada simulação e a janela de configurações, os que
#: são da máquina.
FIELD_KEYS = ("idf", "output", "epw", "energy")

SIMULATION_FIELDS = ("idf", "epw")
MACHINE_FIELDS = ("output", "energy")


#: Tudo o que muda de um campo para o outro: rótulo, atributo do Entry,
#: dica, título do seletor e o método do callback. `filetypes=None` marca os
#: campos que escolhem uma pasta em vez de um arquivo.
FIELDS = {
    "idf": dict(
        label="Arquivo IDF", entry="inputfile_entry",
        tooltip="Arquivo de entrada do modelo EnergyPlus (.idf)",
        title="Selecione o arquivo IDF",
        filetypes=(("Arquivos IDF", "*.idf"), ("Todos os arquivos", "*.*")),
        callback="on_idf_path_changed"),
    "output": dict(
        label="Pasta das execuções", entry="outputfolder_entry",
        tooltip="Raiz onde cada execução ganha a sua própria subpasta",
        title="Selecione a pasta das execuções", filetypes=None,
        callback="on_output_path_changed"),
    "epw": dict(
        label="Arquivo climático (EPW)", entry="epwfile_entry",
        tooltip="Arquivo de dados climáticos (.epw)",
        title="Selecione o arquivo climático",
        filetypes=(("Arquivos EPW", "*.epw"), ("Todos os arquivos", "*.*")),
        callback="on_epw_path_changed"),
    "energy": dict(
        label="Caminho do EnergyPlus", entry="energy_path_entry",
        tooltip="Diretório de instalação do EnergyPlus",
        title="Selecione a pasta do EnergyPlus", filetypes=None,
        callback="on_energy_path_changed"),
}


class PathConfigPanel(ttk.Frame):
    """Panel for path configuration."""

    def __init__(self, parent, callback: Optional[PathConfigCallback] = None,
                 fields: tuple = FIELD_KEYS, **kwargs):
        super().__init__(parent, style="Surface.TFrame", **kwargs)
        self.callback = callback
        self._fields = fields
        self._build_ui()
    
    def _build_ui(self):
        """Build the UI components: one labeled path field per row."""
        self.grid_columnconfigure(0, weight=1)

        for index, key in enumerate(self._fields):
            self._create_path_field(index, key)

    def _create_path_field(self, index, key):
        """Create a path field: label above, entry + actions, status below."""
        spec = FIELDS[key]
        label, entry_var_name, tooltip = spec["label"], spec["entry"], spec["tooltip"]
        change_callback = lambda event=None, k=key: self._notify(k)
        browse_command = lambda k=key: self._browse(k)
        field = ttk.Frame(self, style="Surface.TFrame")
        field.grid(row=index, column=0, sticky="ew", pady=(0, SPACE[4]))
        field.grid_columnconfigure(0, weight=1)

        label_widget = ttk.Label(field, text=label, style="Label.TLabel")
        label_widget.grid(row=0, column=0, columnspan=3, sticky="w",
                          pady=(0, SPACE[1]))
        if tooltip:
            self._create_tooltip(label_widget, tooltip)

        entry = ttk.Entry(field, style="Field.TEntry")
        entry.grid(row=1, column=0, sticky="ew", padx=(0, SPACE[2]))
        entry.bind('<FocusOut>', change_callback)
        entry.bind('<KeyRelease>', lambda e, k=key: self._validate_path(k))

        RoundedButton(field, text="Procurar", variant="ghost", icon="browse",
                      command=browse_command).grid(row=1, column=1)

        # O caminho do EnergyPlus ganha um botão de detecção automática: é o
        # único campo cujo valor a máquina consegue descobrir sozinha.
        if entry_var_name == "energy_path_entry":
            RoundedButton(field, text="Detectar", variant="ghost", icon="detect",
                          command=self.detect_energy_path).grid(
                              row=1, column=2, padx=(SPACE[2], 0))

        setattr(self, entry_var_name, entry)

        # Só ocupa espaço quando tem o que dizer: vazio, deixava um buraco de
        # 15 px entre um campo e o próximo.
        status_label = ttk.Label(field, text="", style="Caption.TLabel")
        status_label.grid(row=2, column=0, columnspan=3, sticky="w",
                          pady=(SPACE[1], 0))
        status_label.grid_remove()
        setattr(self, f"{entry_var_name}_status", status_label)

    def _create_tooltip(self, widget, text):
        """Balão de ajuda enquanto o ponteiro está sobre o widget."""
        # Um balão por widget: sem isso, cada <Enter> criava um Toplevel novo
        # que só sumia por timeout, e eles se empilhavam na tela.
        state = {'window': None}

        def hide(_event=None):
            if state['window'] is not None:
                state['window'].destroy()
                state['window'] = None

        def show(event):
            hide()
            tooltip = tk.Toplevel(widget)
            state['window'] = tooltip
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
            ttk.Label(tooltip, text=text, style="Caption.TLabel",
                      background=COLORS["bg"], relief="solid",
                      borderwidth=1, padding=SPACE[2]).pack()

        widget.bind('<Enter>', show)
        widget.bind('<Leave>', hide)
        widget.bind('<Destroy>', hide)
    
    def detect_energy_path(self):
        """Procura a instalação do EnergyPlus e preenche o campo."""
        path = find_energy_path()
        if path:
            self.set_energy_path(path)
            self._notify('energy')
        else:
            self.energy_path_entry_status.config(
                text=f"❌ EnergyPlus {REQUIRED_EP_VERSION} não encontrado — "
                     "instale-o ou informe a pasta em Procurar",
                foreground=COLORS["danger"]
            )
            self.energy_path_entry_status.grid()

    def _validate_energy_path(self, path: str, status_label):
        """Feedback do campo do EnergyPlus: precisa do IDD e do pyenergyplus."""
        if not is_energy_path(path):
            status_label.config(
                text=" Não é uma instalação do EnergyPlus (falta Energy+.idd "
                     "ou pyenergyplus). Aponte para a pasta raiz",
                foreground=COLORS["danger"],
                image=icon("error", 14, COLORS["danger"], master=self), compound="left"
            )
            return

        version = energy_path_version(path)
        api_version = energy_api_version(path)
        api_suffix = f" (API Python {api_version})" if api_version else ""
        if api_version and api_version != REQUIRED_EP_API_VERSION:
            status_label.config(
                text=f" API Python {api_version} encontrada. O programa espera "
                     f"a {REQUIRED_EP_API_VERSION} (EnergyPlus "
                     f"{REQUIRED_EP_VERSION}) e a simulação pode falhar",
                foreground=COLORS["warn"],
                image=icon("warning", 14, COLORS["warn"], master=self), compound="left"
            )
            return
        if version == REQUIRED_EP_VERSION or not version:
            status_label.config(
                text=f"EnergyPlus {version or 'detectado'}{api_suffix}",
                foreground=COLORS["ok"],
                image=icon("success", 14, COLORS["ok"], master=self), compound="left"
            )
        else:
            status_label.config(
                text=f" Versão {version}{api_suffix} encontrada. O programa "
                     f"espera a {REQUIRED_EP_VERSION} e a simulação pode falhar",
                foreground=COLORS["warn"],
                image=icon("warning", 14, COLORS["warn"], master=self), compound="left"
            )

    def _validate_path(self, key):
        """Validate path and show visual feedback."""
        entry = getattr(self, FIELDS[key]["entry"])
        status_label = getattr(self, f'{FIELDS[key]["entry"]}_status')
        path = entry.get().strip()

        if not path:
            status_label.grid_remove()
            return

        status_label.grid()

        if key == "energy":
            self._validate_energy_path(path, status_label)
            return

        # Arquivo ou diretório, conforme o campo.
        is_file = FIELDS[key]["filetypes"] is not None
        found = os.path.isfile(path) if is_file else os.path.isdir(path)
        noun = "Arquivo" if is_file else "Diretório"
        if found:
            status_label.config(text=f" {noun} encontrado", foreground=COLORS["ok"],
                                image=icon("success", 14, COLORS["ok"], master=self),
                                compound="left")
            entry.config(style="Field.TEntry")
        else:
            status_label.config(text=f" {noun} não encontrado",
                                foreground=COLORS["danger"],
                                image=icon("error", 14, COLORS["danger"], master=self),
                                compound="left")

    def _browse(self, key):
        """Seletor de arquivo ou de pasta, conforme o campo."""
        spec = FIELDS[key]
        if spec["filetypes"] is None:
            filename = filedialog.askdirectory(initialdir=".", title=spec["title"])
        else:
            filename = filedialog.askopenfilename(
                initialdir=".", title=spec["title"], filetypes=spec["filetypes"])
        if filename:
            entry = getattr(self, spec["entry"])
            entry.delete(0, tk.END)
            entry.insert(0, filename)
            self._notify(key)

    def _notify(self, key):
        """Avisa a janela principal que o caminho mudou."""
        if self.callback:
            getattr(self.callback, FIELDS[key]["callback"])(
                getattr(self, FIELDS[key]["entry"]).get())

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
        self._validate_path('energy')
    
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
