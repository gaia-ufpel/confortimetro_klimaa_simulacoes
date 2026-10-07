"""Servidor de simulações na página de Configurações: endereço, token e modo."""

import tkinter as tk
from tkinter import ttk

from confortimetro.remote import client as remote

from ..theme import SPACE, RoundedButton, toast
from .drive_panel import in_background


class RemoteSettings(ttk.Frame):
    """Liga o modo remoto e baixa as execuções concluídas no servidor."""

    def __init__(self, parent, runs_root, on_synced=None, **kwargs):
        super().__init__(parent, style="Surface.TFrame", **kwargs)
        self.runs_root = runs_root
        self.on_synced = on_synced
        settings = remote.load_settings()

        ttk.Label(self, text="Endereço do servidor", style="Label.TLabel").pack(anchor="w")
        self.url_entry = ttk.Entry(self, style="Field.TEntry")
        self.url_entry.insert(0, settings["url"])
        self.url_entry.pack(fill="x", pady=(SPACE[1], SPACE[3]))

        ttk.Label(self, text="Token de acesso (em branco mantém o salvo)",
                  style="Label.TLabel").pack(anchor="w")
        self.token_entry = ttk.Entry(self, style="Field.TEntry", show="•")
        self.token_entry.pack(fill="x", pady=(SPACE[1], SPACE[3]))

        self.active_var = tk.BooleanVar(value=settings["ativo"])
        ttk.Checkbutton(self, text="Executar as simulações no servidor",
                        variable=self.active_var).pack(anchor="w")

        self.status_var = tk.StringVar(value="Modo remoto ativo." if settings["ativo"]
                                       else "Simulações rodam nesta máquina.")
        ttk.Label(self, textvariable=self.status_var, style="Body.TLabel",
                  wraplength=640, justify="left").pack(anchor="w", pady=(SPACE[3], 0))

        buttons = ttk.Frame(self, style="Surface.TFrame")
        buttons.pack(anchor="w", pady=(SPACE[3], 0))
        RoundedButton(buttons, text="Salvar e testar", icon="cloud",
                      command=self._save).pack(side="left")
        RoundedButton(buttons, text="Baixar execuções do servidor", variant="ghost",
                      icon="refresh", command=self._sync).pack(side="left", padx=(SPACE[2], 0))
        ttk.Label(self, text="No modo remoto o IDF e o EPW vão para o servidor, que simula e "
                             "devolve os resultados sem os arquivos brutos do EnergyPlus. "
                             "O EnergyPlus local deixa de ser necessário.",
                  style="Caption.TLabel", wraplength=640, justify="left").pack(
                      anchor="w", pady=(SPACE[3], 0))

    def _save(self):
        url, token = self.url_entry.get().strip(), self.token_entry.get().strip()
        if self.active_var.get() and not url:
            toast(self, "Informe o endereço do servidor.", "error")
            return
        remote.save_settings(url, self.active_var.get())
        if token:
            remote.set_token(token)
            self.token_entry.delete(0, "end")
        if not url:
            self.status_var.set("Simulações rodam nesta máquina.")
            return
        self.status_var.set("Testando conexão…")

        def done(me, error):
            if error:
                self.status_var.set(f"Falha ao conectar: {error}")
                return
            text = f"Conectado como {me['usuario']}{' (admin)' if me['admin'] else ''}."
            quota = me.get("cota") or {}
            if quota.get("excedida"):
                text += (f" Atenção: o servidor usa {quota['usado_gb']} GB, acima da cota de "
                         f"{quota['limite_gb']} GB.")
            self.status_var.set(text)

        in_background(self, lambda: remote.Client().me(), done)

    def _sync(self):
        root = self.runs_root()

        def done(count, error):
            if error:
                toast(self, f"Falha ao baixar: {error}", "error", timeout=10000)
                return
            toast(self, f"{count} execução(ões) baixada(s) do servidor." if count
                  else "Nada novo no servidor.", "ok")
            if count and self.on_synced:
                self.on_synced()

        in_background(self, lambda: remote.sync(root), done)
