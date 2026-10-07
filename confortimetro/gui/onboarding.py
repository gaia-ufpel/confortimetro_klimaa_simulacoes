"""Apresentação das funcionalidades depois de instalar (ou reinstalar) o app.

Só o instalador sabe que houve uma instalação: a pasta de dados sobrevive à
desinstalação, então uma marca guardada pelo app não distinguiria uma
reinstalação. O `installer.iss` grava `onboarding=pendente` em
`instalacao.ini`, ao lado do `Ambiens.exe`, a cada instalação; o app mostra a
apresentação enquanto a marca estiver pendente e grava `feito` ao fechá-la.

Rodando do repositório não há instalador nem marca: `AMBIENS_ONBOARDING=1`
força a apresentação, e o botão em Configurações a reabre a qualquer hora.
"""

import configparser
import os
import sys
import tkinter as tk
from tkinter import ttk

from confortimetro.config import REQUIRED_EP_VERSION, energy_path_version, find_energy_path

from .components import DriveSettings
from .theme import COLORS, SPACE, RoundedButton

MARKER_FILE = "instalacao.ini"
SECTION = "Ambiens"
KEY = "onboarding"
FORCE_VARIABLE = "AMBIENS_ONBOARDING"


def marker_path():
    """`instalacao.ini` do instalador, ou `None` fora do executável."""
    if not getattr(sys, "frozen", False):
        return None
    return os.path.join(os.path.dirname(sys.executable), MARKER_FILE)


def _read(path):
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    return parser


def pending() -> bool:
    """A apresentação deve abrir sozinha nesta inicialização?"""
    if os.environ.get(FORCE_VARIABLE) == "1":
        return True
    path = marker_path()
    if not path or not os.path.isfile(path):
        return False
    return _read(path).get(SECTION, KEY, fallback="") == "pendente"


def mark_done():
    """Não mostra de novo até a próxima instalação. Falha ao gravar não é
    erro do usuário: no pior caso a apresentação reaparece na próxima vez."""
    path = marker_path()
    if not path or not os.path.isfile(path):
        return
    parser = _read(path)
    if not parser.has_section(SECTION):
        parser.add_section(SECTION)
    parser.set(SECTION, KEY, "feito")
    try:
        with open(path, "w", encoding="utf-8") as writer:
            parser.write(writer)
    except OSError:
        pass


def _energyplus_text(app) -> str:
    path = (app.configs.energy_path if app.configs else "") or find_energy_path()
    if not path:
        return (f"Não encontramos o EnergyPlus {REQUIRED_EP_VERSION} nesta máquina. "
                "Sem ele dá para ver e comparar execuções, mas não simular. "
                "Instale pelo link abaixo e informe a pasta em Configurações.")
    version = energy_path_version(path)
    if version != REQUIRED_EP_VERSION:
        return (f"Encontramos o EnergyPlus {version or '(versão desconhecida)'} em {path}, "
                f"mas o Ambiens espera a {REQUIRED_EP_VERSION}: a simulação pode falhar.")
    return f"EnergyPlus {REQUIRED_EP_VERSION} encontrado em {path}. Tudo pronto para simular."


def _steps(app):
    """(título, texto, extra) de cada passo; `extra(parent)` monta widgets."""
    import webbrowser

    def energyplus_link(parent):
        RoundedButton(parent, text="Baixar o EnergyPlus 9.4", variant="ghost", icon="cloud",
                      command=lambda: webbrowser.open(
                          "https://github.com/NREL/EnergyPlus/releases/tag/v9.4.0")).pack(
                              anchor="w")

    def drive(parent):
        DriveSettings(parent, on_connected=app.drive_sync).pack(fill="x")

    return [
        ("Boas-vindas ao Ambiens",
         "O Ambiens roda simulações de conforto térmico no EnergyPlus, controlando "
         "janelas, ventiladores e ar-condicionado de cada sala, e mostra os "
         "resultados em tabelas e gráficos. Estes passos mostram o essencial; "
         "dá para rever tudo depois em Configurações.", None),
        ("EnergyPlus", _energyplus_text(app), energyplus_link),
        ("Onde ficam as execuções",
         f"Cada simulação vira uma pasta em:\n{app._outputs_root()}\n\n"
         "Uma simulação anual passa de 1 GB. Se o disco do sistema for pequeno, "
         "troque a pasta em Configurações.", None),
        ("Google Drive",
         "Conectando sua conta, cada execução concluída vai sozinha para a pasta "
         "\"Ambiens\" do seu Drive e as de outras máquinas aparecem aqui. "
         "Também dá para compartilhar uma execução com colegas. Se preferir, "
         "conecte depois em Configurações.", drive),
        ("Sua primeira simulação",
         "Em \"Nova execução\" você escolhe o modelo (IDF), o clima (EPW), as salas "
         "e a estratégia de controle, e acompanha o progresso. Depois, na lista de "
         "execuções, abra os detalhes, compare execuções ou converse com o "
         "assistente sobre os resultados.", None),
    ]


def open_onboarding(app):
    """Janela de passos sobre a janela principal. Devolve a janela."""
    window = tk.Toplevel(app)
    window.title("Conheça o Ambiens")
    window.configure(bg=COLORS["surface"])
    window.transient(app)
    window.resizable(False, False)

    steps = _steps(app)
    body = ttk.Frame(window, style="Surface.TFrame", padding=SPACE[5])
    body.pack(fill="both", expand=True)
    content = ttk.Frame(body, style="Surface.TFrame", width=560, height=300)
    content.pack(fill="both", expand=True)
    content.pack_propagate(False)
    footer = ttk.Frame(body, style="Surface.TFrame")
    footer.pack(fill="x", pady=(SPACE[4], 0))
    counter = ttk.Label(footer, style="Caption.TLabel")
    counter.pack(side="left")

    def close():
        mark_done()
        window.destroy()

    skip = RoundedButton(footer, text="Pular", variant="ghost", command=close)
    back = RoundedButton(footer, text="Voltar", variant="ghost")
    forward = RoundedButton(footer, text="Próximo")
    forward.pack(side="right")
    back.pack(side="right", padx=(0, SPACE[2]))
    skip.pack(side="right", padx=(0, SPACE[2]))

    def show(index):
        window.step = index
        for child in content.winfo_children():
            child.destroy()
        title, text, extra = steps[index]
        ttk.Label(content, text=title, style="H2.TLabel",
                  background=COLORS["surface"]).pack(anchor="w", pady=(0, SPACE[3]))
        ttk.Label(content, text=text, style="Body.TLabel", wraplength=540,
                  justify="left").pack(anchor="w", pady=(0, SPACE[3]))
        if extra:
            extra(content)
        counter.configure(text=f"{index + 1} de {len(steps)}")
        last = index == len(steps) - 1
        back.configure(state="normal" if index else "disabled",
                       command=lambda: show(index - 1))
        forward.configure(text="Abrir o editor" if last else "Próximo",
                          command=finish if last else lambda: show(index + 1))

    def finish():
        close()
        app.on_new_run()

    window.show, window.forward = show, forward
    window.protocol("WM_DELETE_WINDOW", close)
    window.bind("<Escape>", lambda _event: close())
    show(0)

    window.update_idletasks()
    x = app.winfo_rootx() + (app.winfo_width() - window.winfo_width()) // 2
    y = app.winfo_rooty() + (app.winfo_height() - window.winfo_height()) // 3
    window.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    window.grab_set()
    return window
