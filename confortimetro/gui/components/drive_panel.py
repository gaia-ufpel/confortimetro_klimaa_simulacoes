"""Google Drive na interface: conexão (Configurações) e diálogo de compartilhar.

Toda chamada ao Drive roda numa thread (`in_background`) e volta para o Tk
por `after`: login no navegador, envio e permissões levam segundos a minutos.
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from confortimetro.drive import auth, sync

from ..theme import COLORS, SPACE, RoundedButton, toast

POLL_MS = 100


def in_background(widget, work, done, tick=None):
    """Roda `work()` numa thread e chama `done(resultado, erro)` no Tk.

    Como no assistente, a thread só põe o resultado numa fila e quem fala com
    o Tk é o `after` da thread principal; `tick` roda a cada consulta.
    """
    results = queue.Queue()

    def target():
        try:
            results.put((work(), None))
        except Exception as exc:
            results.put((None, exc))

    def poll():
        try:
            result, error = results.get_nowait()
        except queue.Empty:
            if tick:
                tick()
            widget.after(POLL_MS, poll)
            return
        done(result, error)

    threading.Thread(target=target, daemon=True).start()
    widget.after(POLL_MS, poll)


def _service():
    service = auth.service()
    if service is None:
        raise auth.DriveError("Conecte o Google Drive em Configurações.")
    return service


class DriveSettings(ttk.Frame):
    """Conectar/desconectar a conta, na página de Configurações."""

    def __init__(self, parent, on_connected=None, **kwargs):
        super().__init__(parent, style="Surface.TFrame", **kwargs)
        self.on_connected = on_connected
        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, style="Body.TLabel",
                  wraplength=640, justify="left").pack(anchor="w")
        buttons = ttk.Frame(self, style="Surface.TFrame")
        buttons.pack(anchor="w", pady=(SPACE[3], 0))
        self.connect_button = RoundedButton(buttons, text="Conectar Google Drive",
                                            icon="cloud", command=self._connect)
        self.connect_button.pack(side="left")
        self.disconnect_button = RoundedButton(buttons, text="Desconectar", variant="ghost",
                                               icon="unlink", command=self._disconnect)
        self.disconnect_button.pack(side="left", padx=(SPACE[2], 0))
        ttk.Label(self, text="Com a conta conectada, cada execução concluída vai sozinha "
                             "para a pasta \"Ambiens\" do seu Drive. O app só enxerga os "
                             "arquivos que ele mesmo criou lá.",
                  style="Caption.TLabel", wraplength=640, justify="left").pack(
                      anchor="w", pady=(SPACE[3], 0))
        self.refresh()

    def refresh(self):
        state = sync.load_state()
        account = state.get("account")
        if not auth.client_path():
            text = ("Indisponível: o cliente OAuth do Google não foi configurado nesta "
                    "instalação (veja docs/DRIVE.md). O restante do app funciona normalmente.")
            connect, disconnect = "disabled", "disabled"
        elif account and state.get("reconnect"):
            text = (f"O acesso de {account} expirou ou foi revogado. Conecte de novo; "
                    "as execuções pendentes vão em seguida.")
            connect, disconnect = "normal", "normal"
        elif account:
            text = f"Conectado como {account}."
            connect, disconnect = "disabled", "normal"
        else:
            text = "Nenhuma conta conectada."
            connect, disconnect = "normal", "disabled"
        if account and state["pending"]:
            text += f" {len(state['pending'])} execução(ões) pendente(s) de envio."
        self.status_var.set(text)
        self.connect_button.configure(
            state=connect, text="Reconectar" if account else "Conectar Google Drive")
        self.disconnect_button.configure(state=disconnect)

    def _connect(self):
        self.connect_button.configure(state="disabled")
        self.status_var.set("Termine o login na janela do navegador que abriu…")

        def done(email, error):
            self.refresh()
            if error:
                toast(self, f"Não foi possível conectar: {error}", "error", timeout=10000)
                return
            toast(self, f"Google Drive conectado ({email}). Enviando as execuções.", "ok")
            if self.on_connected:
                self.on_connected()

        in_background(self, sync.connect, done)

    def _disconnect(self):
        if not messagebox.askyesno(
                "Desconectar Google Drive",
                "O app deixa de sincronizar e esquece o acesso a esta conta. "
                "Os arquivos já enviados continuam no seu Drive.",
                parent=self):
            return

        def done(_result, error):
            self.refresh()
            if error:
                toast(self, f"Falha ao desconectar: {error}", "error")
            else:
                toast(self, "Google Drive desconectado.", "ok")
            if self.on_connected:
                self.on_connected()

        in_background(self, sync.disconnect, done)


def open_share_dialog(widget, run_path: str):
    """Diálogo de compartilhar a pasta da execução no Drive. Devolve a janela.

    Modal como o `theme.ask_choices` (a exceção à regra de não abrir
    `Toplevel`), mas não espera fechar: as ações rodam em segundo plano.
    """
    parent = widget.winfo_toplevel()
    name = os.path.basename(os.path.normpath(run_path))
    window = tk.Toplevel(parent)
    window.title("Compartilhar execução")
    window.configure(bg=COLORS["bg"])
    window.transient(parent)
    window.resizable(False, False)

    body = ttk.Frame(window, style="TFrame", padding=SPACE[4])
    body.pack(fill="both", expand=True)
    ttk.Label(body, text=f"Compartilhar “{name}”", style="CardTitle.TLabel").pack(
        anchor="w")
    ttk.Label(body, text="Atenção: o link dá acesso de leitura a qualquer pessoa que o "
                         "tenha, mesmo sem conta Google. Para restringir, convide por "
                         "e-mail e pare de compartilhar o link.",
              style="Body.TLabel", foreground=COLORS["warn"], wraplength=480,
              justify="left").pack(anchor="w", pady=(SPACE[2], SPACE[3]))

    link_row = ttk.Frame(body, style="TFrame")
    link_row.pack(anchor="w")
    window.copy_button = RoundedButton(link_row, text="Copiar link", icon="link")
    window.copy_button.pack(side="left")
    window.unshare_button = RoundedButton(link_row, text="Parar de compartilhar link",
                                          variant="ghost", icon="unlink")
    window.unshare_button.pack(side="left", padx=(SPACE[2], 0))

    ttk.Label(body, text="Convidar por e-mail (somente leitura)", style="Body.TLabel").pack(
        anchor="w", pady=(SPACE[4], SPACE[1]))
    invite_row = ttk.Frame(body, style="TFrame")
    invite_row.pack(fill="x")
    window.emails = tk.StringVar()
    ttk.Entry(invite_row, textvariable=window.emails, width=44).pack(
        side="left", fill="x", expand=True)
    window.invite_button = RoundedButton(invite_row, text="Convidar", icon="mail")
    window.invite_button.pack(side="left", padx=(SPACE[2], 0))
    ttk.Label(body, text="Separe vários e-mails por vírgula. Cada pessoa recebe um "
                         "aviso do Google.", style="Caption.TLabel").pack(anchor="w")

    window.status = tk.StringVar()
    ttk.Label(body, textvariable=window.status, style="Caption.TLabel", wraplength=480,
              justify="left").pack(anchor="w", pady=(SPACE[3], 0))
    RoundedButton(body, text="Fechar", variant="ghost", command=window.destroy).pack(
        anchor="e", pady=(SPACE[3], 0))

    actions = (window.copy_button, window.unshare_button, window.invite_button)

    def idle():
        for button in actions:
            button.configure(state="normal")
        window.unshare_button.configure(
            state="normal" if sync.is_link_shared(run_path) else "disabled")

    def run(message, work, done):
        for button in actions:
            button.configure(state="disabled")
        window.status.set(message)

        def finish(result, error):
            if not window.winfo_exists():
                return
            idle()
            if error:
                window.status.set(f"Falhou: {error}")
                toast(parent, f"Drive: {error}", "error", timeout=10000)
            else:
                done(result)

        # Agendado na janela principal: fechar o diálogo não cancela a consulta.
        in_background(parent, work, finish)

    def copied(url):
        # Na janela principal: o conteúdo da área de transferência é do Tk
        # dono dela e sumiria com o diálogo.
        parent.clipboard_clear()
        parent.clipboard_append(url)
        window.status.set(f"Link copiado: {url}")
        toast(parent, "Link copiado para a área de transferência.", "ok")

    def invited(emails):
        window.emails.set("")
        window.status.set("Convite enviado para " + ", ".join(emails) + ".")

    def invite():
        emails = sync.parse_emails(window.emails.get())
        if not emails:
            window.status.set("Digite ao menos um e-mail.")
            return
        run("Enviando convites…",
            lambda: (sync.invite(_service(), run_path, emails), emails)[1], invited)

    window.copy_button.configure(command=lambda: run(
        "Enviando a execução e criando o link…",
        lambda: sync.share_link(_service(), run_path), copied))
    window.unshare_button.configure(command=lambda: run(
        "Removendo o link…", lambda: sync.unshare_link(_service(), run_path),
        lambda _r: window.status.set("O link deixou de funcionar. Convidados por e-mail "
                                     "continuam com acesso.")))
    window.invite_button.configure(command=invite)
    idle()

    window.bind("<Escape>", lambda _event: window.destroy())
    window.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - window.winfo_width()) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - window.winfo_height()) // 3
    window.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    window.grab_set()
    return window
