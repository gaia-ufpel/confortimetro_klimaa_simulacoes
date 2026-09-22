"""Chat com o assistente de análise e a seção dele nas Configurações.

A pergunta roda numa thread; ela só fala com o Tk por uma fila que o painel
esvazia com `after` — widget Tk tocado fora da thread principal trava ou
derruba a GUI.
"""

import html
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, simpledialog, ttk

from ...assistant import store
from ..theme import COLORS, FONTS, SPACE, RoundedButton, toast

PRIVACY_NOTE = ("As perguntas e os recortes das simulações consultados são enviados ao "
                "Google (Gemini). No plano gratuito, o Google pode usá-los para treinar "
                "modelos.")

_CSS = f"""
body {{ font-family: sans-serif; font-size: 10pt; color: {COLORS['text']};
        background: {COLORS['surface']}; margin: 8px; }}
.msg {{ margin: 0 0 12px 0; padding: 8px 12px; }}
.user {{ background: {COLORS['surface_2']}; }}
.who {{ font-size: 8pt; color: {COLORS['text_mute']}; font-weight: bold; }}
.empty {{ color: {COLORS['text_mute']}; }}
table {{ border-collapse: collapse; margin: 6px 0; }}
th, td {{ border: 1px solid {COLORS['line']}; padding: 3px 8px; }}
th {{ background: {COLORS['surface_2']}; }}
pre, code {{ font-family: monospace; }}
"""

_EMPTY = ("Pergunte sobre os resultados: consumo, horas de desconforto, uso de janela, "
          "ventilador e AC, comparação entre execuções…")


def markdown_to_html(text: str) -> str:
    import markdown
    return markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])


def conversation_html(messages, pending_question=None, partial=None) -> str:
    """Página com as mensagens; a pergunta em curso e a resposta parcial no fim."""
    blocks = []
    for role, text in messages:
        if role == "user":
            blocks.append(f'<div class="msg user"><div class="who">Você</div>'
                          f'{html.escape(text).replace(chr(10), "<br>")}</div>')
        else:
            blocks.append(f'<div class="msg"><div class="who">Assistente</div>'
                          f'{markdown_to_html(text)}</div>')
    if pending_question:
        blocks.append(f'<div class="msg user"><div class="who">Você</div>'
                      f'{html.escape(pending_question)}</div>')
        if partial:
            blocks.append(f'<div class="msg"><div class="who">Assistente</div>'
                          f'{markdown_to_html(partial)}</div>')
    if not blocks:
        blocks.append(f'<p class="empty">{_EMPTY}</p>')
    return f"<html><head><style>{_CSS}</style></head><body>{''.join(blocks)}</body></html>"


def ask_api_key(widget) -> str:
    """Diálogo modal pedindo a chave; salva e devolve, ou '' se o usuário desistir."""
    parent = widget.winfo_toplevel()
    window = tk.Toplevel(parent)
    window.title("Chave da API Gemini")
    window.configure(bg=COLORS["bg"])
    window.transient(parent)
    window.resizable(False, False)

    body = ttk.Frame(window, padding=SPACE[4])
    body.pack(fill="both", expand=True)
    ttk.Label(body, style="Body.TLabel", justify="left", wraplength=480, text=(
        "O assistente usa a sua própria chave da API Gemini. Crie uma gratuitamente "
        "no Google AI Studio e cole abaixo. Ela fica guardada no cofre de senhas do "
        "sistema.")).pack(anchor="w")
    link = ttk.Label(body, text=store.AI_STUDIO_URL, cursor="hand2",
                     foreground=COLORS["primary"], style="Body.TLabel")
    link.pack(anchor="w", pady=(SPACE[2], SPACE[3]))
    link.bind("<Button-1>", lambda _e: webbrowser.open(store.AI_STUDIO_URL))

    variable = tk.StringVar()
    entry = ttk.Entry(body, textvariable=variable, show="•", width=56)
    entry.pack(fill="x")
    entry.focus_set()

    answer = {}

    def accept(_event=None):
        key = variable.get().strip()
        if not key:
            return
        store.set_api_key(key)
        answer["key"] = key
        window.destroy()

    buttons = ttk.Frame(body)
    buttons.pack(anchor="e", pady=(SPACE[4], 0))
    RoundedButton(buttons, "Cancelar", command=window.destroy,
                  variant="ghost").pack(side="left", padx=(0, SPACE[2]))
    RoundedButton(buttons, "Salvar chave", command=accept).pack(side="left")
    window.bind("<Return>", accept)
    window.bind("<Escape>", lambda _e: window.destroy())

    window.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - window.winfo_width()) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - window.winfo_height()) // 3
    window.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    window.grab_set()
    parent.wait_window(window)
    return answer.get("key", "")


class AssistantPanel(ttk.Frame):
    """Chat sobre as execuções de `root_getter()`.

    `set_context(runs, run_filter)`: com `run_filter` (aba dos detalhes) o
    seletor mostra só as conversas daquela execução e reabre a mais recente;
    sem ele (página geral) mostra todas e começa uma conversa nova com `runs`.
    """

    POLL_MS = 80
    RENDER_MS = 250

    def __init__(self, parent, root_getter, **kwargs):
        super().__init__(parent, style="Surface.TFrame", **kwargs)
        self.root_getter = root_getter
        self.runs = []
        self.run_filter = None
        self.conversation = store.new_conversation()
        self._items = []
        self._events = queue.Queue()
        self._cancel = None
        self._worker = None
        self._pending = None
        self._partial = ""
        self._render_due = False
        self._build_ui()
        self._render()

    # --- Layout ---

    def _build_ui(self):
        top = ttk.Frame(self, style="Surface.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="Conversa", style="Caption.TLabel").pack(side="left")
        self.selector = ttk.Combobox(top, state="readonly", width=48)
        self.selector.pack(side="left", padx=(SPACE[2], SPACE[3]))
        self.selector.bind("<<ComboboxSelected>>", self._on_select)
        for text, variant, command, icon in (
                ("Nova", "ghost", self.new_conversation, "new"),
                ("Renomear", "ghost", self.rename_conversation, "edit"),
                ("Excluir", "ghost", self.delete_conversation, "clear"),
                ("Exportar", "ghost", self.export_conversation, "export")):
            RoundedButton(top, text=text, variant=variant, icon=icon,
                          command=command).pack(side="left", padx=(0, SPACE[2]))

        self.warning_var = tk.StringVar()
        self.warning = ttk.Label(self, textvariable=self.warning_var, style="Caption.TLabel",
                                 wraplength=900, justify="left")
        self.warning.configure(foreground=COLORS["warn"])

        # Rodapé empacotado antes da conversa, de baixo para cima: com a
        # janela baixa, quem encolhe é a conversa, não a caixa de pergunta.
        ttk.Label(self, text=PRIVACY_NOTE, style="Caption.TLabel", wraplength=900,
                  justify="left").pack(side="bottom", anchor="w", pady=(SPACE[2], 0))
        bottom = ttk.Frame(self, style="Surface.TFrame")
        bottom.pack(side="bottom", fill="x", pady=(SPACE[1], 0))
        self.input = tk.Text(bottom, height=3, wrap="word", font=FONTS["body"],
                             background="white", foreground=COLORS["text"],
                             relief="flat", highlightthickness=1,
                             highlightbackground=COLORS["line"],
                             padx=SPACE[2], pady=SPACE[2])
        self.input.pack(side="left", fill="x", expand=True)
        # Enter envia; Shift+Enter quebra linha.
        self.input.bind("<Return>", self._on_return)
        buttons = ttk.Frame(bottom, style="Surface.TFrame")
        buttons.pack(side="left", padx=(SPACE[2], 0))
        self.send_button = RoundedButton(buttons, text="Perguntar", icon="play",
                                         command=self.send)
        self.send_button.pack(fill="x")
        self.cancel_button = RoundedButton(buttons, text="Cancelar", variant="ghost",
                                           icon="stop", command=self.cancel)
        self.cancel_button.pack(fill="x", pady=(SPACE[1], 0))

        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, style="Caption.TLabel").pack(
            side="bottom", anchor="w")

        self.view_host = ttk.Frame(self, style="Surface.TFrame")
        self.view_host.pack(fill="both", expand=True, pady=(SPACE[2], SPACE[2]))
        self.view = self._make_view(self.view_host)

        self.suggestions = ttk.Frame(self, style="Surface.TFrame")
        ttk.Label(self.suggestions, text="Experimente perguntar:", style="Caption.TLabel").pack(
            anchor="w")
        for question in (
                "Qual execução teve o menor consumo?",
                "Em qual execução houve mais desconforto?",
                "Em quais horários o ar-condicionado foi mais usado?"):
            RoundedButton(self.suggestions, question, variant="ghost",
                          command=lambda q=question: self._use_suggestion(q)).pack(
                              anchor="w", pady=(SPACE[1], 0))
        self.suggestions.pack(fill="x", before=self.view_host, pady=(SPACE[2], 0))

    def _use_suggestion(self, question: str):
        self.input.delete("1.0", "end")
        self.input.insert("1.0", question)
        self.input.focus_set()

    def _make_view(self, parent):
        """HtmlFrame do tkinterweb; sem ele (instalação quebrada), um Text simples."""
        try:
            from tkinterweb import HtmlFrame
            view = HtmlFrame(parent, messages_enabled=False, javascript_enabled=False,
                             on_link_click=webbrowser.open, height=300)
            view.pack(fill="both", expand=True)
            return view
        except Exception:
            view = tk.Text(parent, wrap="word", state="disabled", font=FONTS["body"],
                           background=COLORS["surface"], relief="flat")
            view.pack(fill="both", expand=True)
            return view

    # --- Contexto e conversas ---

    def set_context(self, runs, run_filter=None):
        if self._busy():
            toast(self, "Espere a resposta atual ou cancele antes de trocar de contexto.", "warn")
            return
        self.runs = list(runs or [])
        self.run_filter = run_filter
        existing = store.list_conversations(run_filter) if run_filter else []
        if existing:
            self._open(existing[0]["id"])
        else:
            self.new_conversation()

    def new_conversation(self):
        if self._busy():
            return
        # Só vai para o disco com a primeira pergunta: nada de arquivos vazios.
        self.conversation = store.new_conversation(self.runs)
        self._refresh_selector()
        self._render()

    def _open(self, conversation_id):
        try:
            self.conversation = store.load_conversation(conversation_id)
        except (OSError, ValueError) as error:
            toast(self, f"Não foi possível abrir a conversa: {error}", "error")
            self.conversation = store.new_conversation(self.runs)
        self._refresh_selector()
        self._render()

    def _refresh_selector(self):
        self._items = store.list_conversations(self.run_filter)
        titles = [item["title"] for item in self._items]
        ids = [item["id"] for item in self._items]
        if self.conversation["id"] not in ids:
            self._items.insert(0, {"id": self.conversation["id"],
                                   "title": self.conversation["title"]})
            titles.insert(0, self.conversation["title"])
        self.selector.configure(values=titles)
        index = [item["id"] for item in self._items].index(self.conversation["id"])
        self.selector.current(index)

        stale = store.stale_runs(self.conversation, self.root_getter())
        if stale:
            self.warning_var.set(
                "Resultados mudaram desde esta conversa: "
                + ", ".join(f"{run} ({why})" for run, why in stale.items())
                + ". Números antigos podem não valer mais; o assistente vai consultar de novo.")
            self.warning.pack(anchor="w", before=self.view_host, pady=(SPACE[2], 0))
        else:
            self.warning.pack_forget()

    def _on_select(self, _event=None):
        if self._busy():
            self._refresh_selector()
            return
        item = self._items[self.selector.current()]
        if item["id"] != self.conversation["id"]:
            self._open(item["id"])

    def _saved(self):
        return any(item["id"] == self.conversation["id"]
                   for item in store.list_conversations())

    def rename_conversation(self):
        if self._busy() or not self._saved():
            return
        title = simpledialog.askstring("Renomear conversa", "Novo título:",
                                       initialvalue=self.conversation["title"], parent=self)
        if title and title.strip():
            self.conversation["title"] = title.strip()[:120]
            store.save_conversation(self.conversation)
            self._refresh_selector()

    def delete_conversation(self):
        if self._busy() or not self._saved():
            return
        if messagebox.askyesno("Excluir conversa",
                               f"Excluir \"{self.conversation['title']}\"? "
                               "Não dá para desfazer.", parent=self):
            store.delete_conversation(self.conversation["id"])
            self.new_conversation()

    def export_conversation(self):
        if not store.visible_messages(self.conversation):
            toast(self, "A conversa ainda está vazia.", "warn")
            return
        safe = "".join(c if c.isalnum() or c in " -_" else "_"
                       for c in self.conversation["title"])[:60].strip() or "conversa"
        path = filedialog.asksaveasfilename(
            parent=self, title="Exportar conversa", defaultextension=".md",
            initialfile=f"{safe}.md", filetypes=[("Markdown", "*.md")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as output:
                output.write(store.export_markdown(self.conversation))
        except OSError as error:
            toast(self, f"Não foi possível exportar: {error}", "error")
            return
        toast(self, "Conversa exportada.", "ok")

    # --- Pergunta ---

    def _busy(self):
        return self._worker is not None and self._worker.is_alive()

    def _on_return(self, event):
        if event.state & 0x0001:  # Shift
            return None
        self.send()
        return "break"

    def send(self):
        if self._busy():
            return
        question = self.input.get("1.0", "end").strip()
        if not question:
            return
        if not store.get_api_key() and not ask_api_key(self):
            return

        from ...assistant.client import Assistant

        self.input.delete("1.0", "end")
        self._pending, self._partial = question, ""
        self._cancel = threading.Event()
        assistant = Assistant(self.conversation, self.root_getter())
        events, cancel = self._events, self._cancel

        def work():
            from ...assistant.client import AssistantError, Cancelled
            try:
                assistant.ask(question, on_event=lambda kind, data: events.put((kind, data)),
                              cancel=cancel)
                events.put(("done", None))
            except Cancelled:
                events.put(("cancelled", question))
            except AssistantError as error:
                events.put(("error", (question, str(error))))
            except Exception as error:  # nunca deixar a thread morrer calada
                events.put(("error", (question, f"{type(error).__name__}: {error}")))

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()
        self.status_var.set("Pensando…")
        self._render()
        self.after(self.POLL_MS, self._poll)

    def cancel(self):
        if self._busy() and self._cancel is not None:
            self._cancel.set()
            self.status_var.set("Cancelando…")

    def _poll(self):
        finished = False
        try:
            while True:
                kind, data = self._events.get_nowait()
                if kind == "text":
                    self._partial += data
                    self._schedule_render()
                elif kind == "status":
                    self.status_var.set(data)
                    if data.startswith("Consultando"):
                        # O texto que veio antes da chamada de ferramenta não é
                        # a resposta final: a próxima rodada escreve de novo.
                        self._partial = ""
                elif kind == "done":
                    finished = True
                elif kind in ("cancelled", "error"):
                    finished = True
                    question = data if kind == "cancelled" else data[0]
                    # A pergunta volta para a caixa: nada se perde.
                    if not self.input.get("1.0", "end").strip():
                        self.input.insert("1.0", question)
                    if kind == "error":
                        self.status_var.set(data[1])
                        toast(self, data[1], "error", timeout=8000)
                    else:
                        self.status_var.set("Pergunta cancelada.")
        except queue.Empty:
            pass

        if finished:
            self._pending, self._partial = None, ""
            self._worker = None
            self._refresh_selector()
            self._render()
        else:
            self.after(self.POLL_MS, self._poll)

    # --- Renderização ---

    def _schedule_render(self):
        if not self._render_due:
            self._render_due = True
            self.after(self.RENDER_MS, self._render)

    def _render(self):
        self._render_due = False
        messages = store.visible_messages(self.conversation)
        if messages or self._pending:
            self.suggestions.pack_forget()
        elif not self.suggestions.winfo_ismapped():
            self.suggestions.pack(fill="x", before=self.view_host, pady=(SPACE[2], 0))
        if hasattr(self.view, "load_html"):
            self.view.load_html(conversation_html(messages, self._pending, self._partial))
            self.view.after_idle(lambda: self.view.yview_moveto(1.0))
            return
        self.view.configure(state="normal")
        self.view.delete("1.0", "end")
        for role, text in messages + ([("user", self._pending)] if self._pending else []):
            self.view.insert("end", ("Você: " if role == "user" else "Assistente: ")
                             + text + "\n\n")
        if self._partial:
            self.view.insert("end", "Assistente: " + self._partial)
        self.view.configure(state="disabled")
        self.view.see("end")


class AssistantSettings(ttk.Frame):
    """Chave, modelo e limites do assistente, na página de Configurações."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, style="Surface.TFrame", **kwargs)
        settings = store.load_settings()
        self.key_var = tk.StringVar()
        self.key_status = tk.StringVar()
        self.model_var = tk.StringVar(value=settings["model"])
        self.limit_vars = {
            "max_tool_calls": tk.IntVar(value=settings["max_tool_calls"]),
            "summarize_tokens": tk.IntVar(value=settings["summarize_tokens"]),
            "timeout_s": tk.IntVar(value=settings["timeout_s"]),
        }
        self._build_ui()
        self._update_key_status()

    def _build_ui(self):
        grid = ttk.Frame(self, style="Surface.TFrame")
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)

        ttk.Label(grid, text="Chave da API Gemini", style="Label.TLabel").grid(
            row=0, column=0, sticky="w", pady=SPACE[1])
        ttk.Entry(grid, textvariable=self.key_var, show="•").grid(
            row=0, column=1, sticky="ew", padx=SPACE[2])
        keys = ttk.Frame(grid, style="Surface.TFrame")
        keys.grid(row=0, column=2, sticky="w")
        RoundedButton(keys, text="Salvar chave", variant="ghost", icon="save",
                      command=self._save_key).pack(side="left")
        RoundedButton(keys, text="Testar chave", variant="ghost", icon="detect",
                      command=self._test_key).pack(side="left", padx=(SPACE[2], 0))
        status = ttk.Frame(grid, style="Surface.TFrame")
        status.grid(row=1, column=1, columnspan=2, sticky="w", padx=SPACE[2])
        ttk.Label(status, textvariable=self.key_status, style="Caption.TLabel").pack(side="left")
        link = ttk.Label(status, text="Criar chave no Google AI Studio", cursor="hand2",
                         style="Caption.TLabel", foreground=COLORS["primary"])
        link.pack(side="left", padx=(SPACE[3], 0))
        link.bind("<Button-1>", lambda _e: webbrowser.open(store.AI_STUDIO_URL))

        ttk.Label(grid, text="Modelo", style="Label.TLabel").grid(
            row=2, column=0, sticky="w", pady=SPACE[1])
        ttk.Entry(grid, textvariable=self.model_var).grid(
            row=2, column=1, sticky="ew", padx=SPACE[2])

        self.advanced = ttk.Frame(self, style="Surface.TFrame")
        self.toggle = RoundedButton(self, text="Avançado", variant="ghost",
                                    icon="chevron-right", command=self._toggle_advanced)
        self.toggle.pack(anchor="w", pady=(SPACE[2], 0))
        for row, (key, label, low, high, step) in enumerate((
                ("max_tool_calls", "Chamadas de ferramenta por pergunta", 1, 100, 1),
                ("summarize_tokens", "Resumir histórico acima de (tokens)",
                 50_000, 2_000_000, 50_000),
                ("timeout_s", "Timeout por chamada (s)", 10, 600, 10))):
            ttk.Label(self.advanced, text=label, style="Label.TLabel").grid(
                row=row, column=0, sticky="w", pady=SPACE[1])
            ttk.Spinbox(self.advanced, from_=low, to=high, increment=step, width=12,
                        textvariable=self.limit_vars[key]).grid(
                row=row, column=1, sticky="w", padx=SPACE[2])

        self.save_button = RoundedButton(self, text="Salvar configurações do assistente",
                                         icon="save", command=self._save_settings)
        self.save_button.pack(anchor="w", pady=(SPACE[3], 0))

    def _toggle_advanced(self):
        if self.advanced.winfo_ismapped():
            self.advanced.pack_forget()
        else:
            self.advanced.pack(fill="x", after=self.toggle, pady=(SPACE[1], 0))

    def _update_key_status(self):
        self.key_status.set("Chave salva." if store.get_api_key()
                            else "Nenhuma chave salva.")

    def _save_key(self):
        store.set_api_key(self.key_var.get())
        self.key_var.set("")
        self._update_key_status()
        toast(self, "Chave salva." if store.get_api_key() else "Chave removida.", "ok")

    def _settings(self):
        settings = {"model": self.model_var.get().strip() or store.DEFAULT_SETTINGS["model"]}
        for key, variable in self.limit_vars.items():
            try:
                settings[key] = max(1, int(variable.get()))
            except (tk.TclError, ValueError):
                settings[key] = store.DEFAULT_SETTINGS[key]
        return settings

    def _save_settings(self):
        store.save_settings(self._settings())
        toast(self, "Configurações do assistente salvas.", "ok")

    def _test_key(self):
        from ...assistant.client import AssistantError, test_key

        key = self.key_var.get().strip() or store.get_api_key()
        model = self._settings()["model"]
        self.key_status.set("Testando…")
        results = queue.Queue()

        def work():
            try:
                test_key(key, model)
                results.put(("ok", f"Chave válida para {model}."))
            except AssistantError as error:
                results.put(("error", str(error)))

        threading.Thread(target=work, daemon=True).start()

        def poll():
            try:
                kind, message = results.get_nowait()
            except queue.Empty:
                self.after(100, poll)
                return
            self._update_key_status()
            toast(self, message, kind, timeout=8000)

        self.after(100, poll)
