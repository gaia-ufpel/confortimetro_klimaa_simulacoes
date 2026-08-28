"""
Results panel component.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Protocol, Optional


class ResultsPanelCallback(Protocol):
    """Protocol for results panel callbacks."""
    
    def on_results_cleared(self) -> None:
        """Called when results are cleared."""
        ...


class ResultsPanel(ttk.Frame):
    """Panel for displaying simulation results."""
    
    def __init__(self, parent, callback: Optional[ResultsPanelCallback] = None):
        super().__init__(parent)
        self.callback = callback
        self._build_ui()
    
    def _build_ui(self):
        """Build the UI components with modern styling."""
        # Header with controls
        header_frame = ttk.Frame(self)
        header_frame.pack(fill="x", padx=0, pady=(0, 10))
        
        # Filter and control buttons
        controls_frame = ttk.Frame(header_frame)
        controls_frame.pack(side="right")
        
        # Message type filter
        self.filter_var = tk.StringVar(value="all")
        filter_frame = ttk.Frame(controls_frame)
        filter_frame.pack(side="left", padx=(0, 10))
        
        ttk.Label(filter_frame, text="Filtro:", style="Body.TLabel").pack(side="left", padx=(0, 5))
        
        filter_combo = ttk.Combobox(
            filter_frame, 
            textvariable=self.filter_var,
            values=["all", "info", "success", "warning", "error"],
            state="readonly",
            width=8,
            style="Modern.TCombobox"
        )
        filter_combo.pack(side="left")
        filter_combo.bind('<<ComboboxSelected>>', self._filter_messages)
        
        # Control buttons
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(side="right", padx=(10, 0))
        
        # Export button
        ttk.Button(
            button_frame, 
            text="💾 Exportar",
            style="Outline.TButton",
            command=self._export_results
        ).pack(side="left", padx=(0, 5))
        
        # Clear button
        ttk.Button(
            button_frame, 
            text="🗑️ Limpar", 
            style="Outline.TButton",
            command=self._clear_results
        ).pack(side="left")
        
        # Results text area with modern styling
        text_frame = ttk.Frame(self)
        text_frame.pack(fill="both", expand=True)
        
        self.results_text = scrolledtext.ScrolledText(
            text_frame, 
            state="disabled", 
            width=100, 
            height=15,
            wrap="word",
            font=('Consolas', 9),
            background="#ffffff",
            foreground="#1e293b",
            relief="flat",
            borderwidth=0
        )
        self.results_text.pack(fill="both", expand=True, padx=1, pady=1)
        
        # Configure text tags for different message types with modern colors
        self.results_text.tag_configure("info", 
                                       foreground="#3b82f6", 
                                       font=('Consolas', 9))
        self.results_text.tag_configure("warning", 
                                       foreground="#f59e0b", 
                                       font=('Consolas', 9, 'bold'))
        self.results_text.tag_configure("error", 
                                       foreground="#ef4444", 
                                       font=('Consolas', 9, 'bold'))
        self.results_text.tag_configure("success", 
                                       foreground="#22c55e", 
                                       font=('Consolas', 9, 'bold'))
        self.results_text.tag_configure("timestamp", 
                                       foreground="#64748b", 
                                       font=('Consolas', 8))
        
        # Status bar
        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", pady=(5, 0))
        
        self.status_var = tk.StringVar()
        self.status_var.set("Pronto")
        
        ttk.Label(status_frame, text="Status:", style="Muted.TLabel").pack(side="left")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, style="Muted.TLabel")
        self.status_label.pack(side="left", padx=(5, 0))
        
        # Message counter
        self.counter_var = tk.StringVar()
        self.counter_var.set("0 mensagens")
        
        ttk.Label(status_frame, textvariable=self.counter_var, style="Muted.TLabel").pack(side="right")
        
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
        icons = {
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌'
        }
        icon = icons.get(message_type, 'ℹ️')
        
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
                
                icons = {
                    'info': 'ℹ️',
                    'success': '✅', 
                    'warning': '⚠️',
                    'error': '❌'
                }
                icon = icons.get(msg_data['type'], 'ℹ️')
                
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
    
    def _clear_results(self):
        """Clear all results."""
        self.results_text.config(state="normal")
        self.results_text.delete(1.0, tk.END)
        self.results_text.config(state="disabled")
        
        if self.callback:
            self.callback.on_results_cleared()
    
    def get_text(self) -> str:
        """Get all text from the results area."""
        return self.results_text.get(1.0, tk.END)
    
    def set_text(self, text: str):
        """Set the text in the results area."""
        self.results_text.config(state="normal")
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, text)
        self.results_text.config(state="disabled")
    
    def is_empty(self) -> bool:
        """Check if the results area is empty."""
        return len(self.get_text().strip()) == 0
