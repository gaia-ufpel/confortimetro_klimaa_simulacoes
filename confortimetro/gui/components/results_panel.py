"""
Results panel component.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Protocol, Optional

from ..theme import COLORS, FONTS, SPACE, RoundedButton


# Marcadores do log: a fonte monoespaçada não tem emoji.
_LOG_MARKS = {'info': '·', 'success': '✓', 'warning': '!', 'error': '×'}


class ResultsPanelCallback(Protocol):
    """Protocol for results panel callbacks."""
    
    def on_results_cleared(self) -> None:
        """Called when results are cleared."""
        ...


class ResultsPanel(ttk.Frame):
    """Panel for displaying simulation results."""
    
    def __init__(self, parent, callback: Optional[ResultsPanelCallback] = None):
        super().__init__(parent, style="Surface.TFrame")
        self.callback = callback
        self._build_ui()
    
    def _build_ui(self):
        """Build the UI: toolbar, log area, status bar."""
        toolbar = ttk.Frame(self, style="Surface.TFrame")
        toolbar.pack(fill="x", pady=(0, SPACE[2]))

        ttk.Label(toolbar, text="Filtro", style="Label.TLabel").pack(
            side="left", padx=(0, SPACE[2]))

        self.filter_var = tk.StringVar(value="all")
        filter_combo = ttk.Combobox(
            toolbar,
            textvariable=self.filter_var,
            values=["all", "info", "success", "warning", "error"],
            state="readonly",
            width=10,
            style="Field.TCombobox"
        )
        filter_combo.pack(side="left")
        filter_combo.bind('<<ComboboxSelected>>', self._filter_messages)

        RoundedButton(toolbar, text="Limpar", variant="ghost", icon="clear",
                      command=self._clear_results).pack(side="right")
        RoundedButton(toolbar, text="Exportar", variant="ghost", icon="export",
                      command=self._export_results).pack(
                          side="right", padx=(0, SPACE[2]))

        self.results_text = scrolledtext.ScrolledText(
            self,
            state="disabled",
            width=100,
            height=10,
            wrap="word",
            font=FONTS["mono"],
            background=COLORS["surface"],
            foreground=COLORS["text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["line"],
            padx=SPACE[3],
            pady=SPACE[3]
        )
        self.results_text.pack(fill="both", expand=True)
        # ScrolledText embute um tk.Scrollbar (não ttk), fora do tema.
        self.results_text.vbar.configure(
            background=COLORS["scroll"], troughcolor=COLORS["surface_2"],
            activebackground=COLORS["text_mute"], relief="flat", borderwidth=0,
            highlightthickness=0, width=10)

        self.results_text.tag_configure("info", foreground=COLORS["primary"],
                                        font=FONTS["mono"])
        self.results_text.tag_configure("warning", foreground=COLORS["warn"],
                                        font=FONTS["mono_bold"])
        self.results_text.tag_configure("error", foreground=COLORS["danger"],
                                        font=FONTS["mono_bold"])
        self.results_text.tag_configure("success", foreground=COLORS["ok"],
                                        font=FONTS["mono_bold"])
        self.results_text.tag_configure("timestamp", foreground=COLORS["text_mute"],
                                        font=FONTS["mono_small"])

        status_frame = ttk.Frame(self, style="Surface.TFrame")
        status_frame.pack(fill="x", pady=(SPACE[2], 0))

        self.status_var = tk.StringVar(value="Pronto")
        ttk.Label(status_frame, textvariable=self.status_var,
                  style="Caption.TLabel").pack(side="left")

        self.counter_var = tk.StringVar(value="0 mensagens")
        ttk.Label(status_frame, textvariable=self.counter_var,
                  style="Caption.TLabel").pack(side="right")

        # Store all messages for filtering
        self.all_messages = []
        self.message_count = {"info": 0, "warning": 0, "error": 0, "success": 0}

    def append_message(self, message: str, message_type: str = "info"):
        """
        Append a message to the results area with enhanced formatting.
        
        Args:
            message: The message to append
            message_type: Type of message ('info', 'warning', 'error', 'success')
        """
        import datetime
        
        # Store message for filtering
        timestamp = datetime.datetime.now()
        message_data = {
            'timestamp': timestamp,
            'message': message,
            'type': message_type
        }
        self.all_messages.append(message_data)
        
        # Update counter
        self.message_count[message_type] = self.message_count.get(message_type, 0) + 1
        self._update_counter()
        
        # Check if message should be displayed based on filter
        if self.filter_var.get() != "all" and self.filter_var.get() != message_type:
            return
        
        self.results_text.config(state="normal")
        
        # Format timestamp and message
        time_str = timestamp.strftime("%H:%M:%S")
        
        # Add icon based on message type
        icon = _LOG_MARKS.get(message_type, _LOG_MARKS['info'])

        # Insert timestamp
        self.results_text.insert(tk.END, f"[{time_str}] ", "timestamp")
        
        # Insert icon and message
        self.results_text.insert(tk.END, f"{icon} {message}\n", message_type)
        
        # Auto-scroll to bottom
        self.results_text.see(tk.END)
        
        self.results_text.config(state="disabled")
        
        # Update status
        self.status_var.set(f"Última mensagem: {time_str}")
        
        # Update the GUI
        self.update_idletasks()
    
    def _filter_messages(self, event=None):
        """Filter messages based on selected type."""
        filter_type = self.filter_var.get()
        
        # Clear current display
        self.results_text.config(state="normal")
        self.results_text.delete(1.0, tk.END)
        
        # Re-display filtered messages
        for msg_data in self.all_messages:
            if filter_type == "all" or msg_data['type'] == filter_type:
                time_str = msg_data['timestamp'].strftime("%H:%M:%S")
                
                icon = _LOG_MARKS.get(msg_data['type'], _LOG_MARKS['info'])
                
                self.results_text.insert(tk.END, f"[{time_str}] ", "timestamp")
                self.results_text.insert(tk.END, f"{icon} {msg_data['message']}\n", msg_data['type'])
        
        self.results_text.config(state="disabled")
        self.results_text.see(tk.END)
    
    def _export_results(self):
        """Export results to a file."""
        from tkinter import filedialog
        import datetime
        
        if not self.all_messages:
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Exportar Resultados"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"Exportação de Resultados - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 50 + "\n\n")
                    
                    for msg_data in self.all_messages:
                        time_str = msg_data['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
                        f.write(f"[{time_str}] [{msg_data['type'].upper()}] {msg_data['message']}\n")
                
                self.append_success(f"Resultados exportados para: {filename}")
            except Exception as e:
                self.append_error(f"Erro ao exportar: {str(e)}")
    
    def _update_counter(self):
        """Update the message counter display."""
        total = len(self.all_messages)
        if total == 0:
            self.counter_var.set("0 mensagens")
        else:
            parts = []
            if self.message_count.get("error", 0) > 0:
                parts.append(f"{self.message_count['error']} erros")
            if self.message_count.get("warning", 0) > 0:
                parts.append(f"{self.message_count['warning']} avisos")
            if self.message_count.get("success", 0) > 0:
                parts.append(f"{self.message_count['success']} sucessos")
            
            if parts:
                self.counter_var.set(f"{total} total ({', '.join(parts)})")
            else:
                self.counter_var.set(f"{total} mensagens")
    
    def _clear_results(self):
        """Clear all results with confirmation."""
        if self.all_messages:
            import tkinter.messagebox as messagebox
            if messagebox.askyesno("Confirmar", "Deseja realmente limpar todos os resultados?"):
                self.results_text.config(state="normal")
                self.results_text.delete(1.0, tk.END)
                self.results_text.config(state="disabled")
                
                # Clear stored messages
                self.all_messages.clear()
                self.message_count = {"info": 0, "warning": 0, "error": 0, "success": 0}
                self._update_counter()
                self.status_var.set("Resultados limpos")
                
                if self.callback:
                    self.callback.on_results_cleared()
    
    def append_info(self, message: str):
        """Append an info message."""
        self.append_message(message, "info")
    
    def append_warning(self, message: str):
        """Append a warning message."""
        self.append_message(message, "warning")
    
    def append_error(self, message: str):
        """Append an error message."""
        self.append_message(message, "error")
    
    def append_success(self, message: str):
        """Append a success message."""
        self.append_message(message, "success")
