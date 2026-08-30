"""
Design system da interface: tokens, estilos ttk e os poucos widgets que
precisam de cantos arredondados (Tk não tem border-radius — ver docs/DESIGN.md).
"""

import os
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import sv_ttk
from PIL import Image, ImageDraw, ImageFont, ImageTk

# Chrome neutro do tema Sun Valley (sv_ttk) + o verde da marca como acento.
# Os sprites do sv_ttk são imagens: a cor dos widgets ttk não é configurável,
# então bg/surface/line seguem a paleta dele e o verde vive nos widgets
# desenhados à mão (Card, RoundedButton, trilhos).
COLORS = {
    # `surface` é o #fafafa do sprite de card/labelframe do sv_ttk: qualquer
    # outro valor deixa um retângulo de fundo diferente dentro das seções.
    "bg": "#f0f0f0",
    "surface": "#fafafa",
    "surface_2": "#eaeaea",
    "line": "#d8d8d8",
    "text": "#1c1c1c",
    # Verdes de texto escurecidos: o #588157 da paleta reprova em contraste
    # (3.1:1 sobre a areia). Continuam servindo de fundo/detalhe, não de texto.
    "text_mute": "#406346",
    "primary": "#3a5a40",
    "primary_h": "#588157",
    "primary_d": "#344e41",
    "accent": "#a3b18a",
    # Laranja do bulbo da logo. Só decorativo (2.6:1 sobre `surface`): serve de
    # preenchimento em barra/indicador de calor, nunca de cor de texto.
    "hot": "#f67a24",
    # Cinza do polegar de scrollbar do sv_ttk, para as barras tk clássicas.
    "scroll": "#c2c2c2",
    "ok": "#4e7a4d",
    "warn": "#a06b00",
    "danger": "#b3261e",
}

SPACE = (0, 4, 8, 12, 16, 24, 32)

RADIUS = {"card": 12, "control": 8, "pill": 999}

#: Ícones do Lucide (ISC, `assets/LUCIDE-LICENSE.txt`), pelo ponto de código do
#: glifo na fonte. Tk não carrega fonte de arquivo, então o glifo é desenhado
#: com o Pillow e vira uma imagem — daí a fonte não precisar estar instalada na
#: máquina. Para usar um ícone novo, pegue o código em
#: https://unpkg.com/lucide-static/font/info.json e acrescente aqui.
ICON_FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "assets", "lucide.ttf")

ICONS = {
    "play": 57660,
    "stop": 57703,
    "save": 57677,
    "open": 57927,
    "new": 57661,
    "details": 57530,
    "duplicate": 57502,
    "refresh": 57669,
    "compare": 58019,
    "settings": 57684,
    "back": 57416,
    "export": 57522,
    "clear": 57999,
    "browse": 57681,
    "detect": 58199,
    "chart": 58021,
    "edit": 58143,
    "timestep": 57824,
    "recompute": 57673,
    "chevron-right": 57455,
    "chevron-down": 57453,
    "info": 57593,
    "running": 57609,
    "success": 57894,
    "warning": 57747,
    "error": 57476,
}

_ICON_CACHE: dict = {}


def icon(name: str, size: int = 16, color: str = None, master=None):
    """Ícone como `PhotoImage`, desenhado na cor pedida.

    O cache é obrigatório e não só uma economia: o Tk não segura referência de
    imagem, e um `PhotoImage` sem dono em Python some no coletor e deixa o
    botão vazio. A chave inclui o interpretador do `master` porque uma imagem
    pertence ao Tk que a criou: reaproveitá-la em outra janela (dois `Tk()` na
    mesma sessão, como nos testes) dá `image "pyimageN" doesn't exist`.
    """
    color = color or COLORS["text"]
    key = (name, size, color, id(master.tk) if master is not None else None)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]

    code = ICONS.get(name)
    if code is None:
        return None
    try:
        font = ImageFont.truetype(ICON_FONT, size)
    except OSError:
        # Sem a fonte o rótulo do botão continua legível; só o ícone falta.
        return None

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    # `anchor="mm"` centraliza o glifo na caixa; sem isso ele encosta na borda
    # de cima e o alinhamento com o texto do botão muda a cada ícone.
    draw.text((size / 2, size / 2), chr(code), font=font, fill=color, anchor="mm")

    photo = ImageTk.PhotoImage(image, master=master)
    _ICON_CACHE[key] = photo
    return photo

# Preenchido por apply_theme com a família resolvida na máquina.
FONTS: dict = {}

_FAMILY_CANDIDATES = ("Segoe UI", "Inter", "DejaVu Sans")
_MONO_CANDIDATES = ("Consolas", "JetBrains Mono", "DejaVu Sans Mono")


def _pick_family(candidates, fallback):
    """Primeira família instalada, senão a fonte padrão do Tk."""
    available = {name.lower() for name in tkfont.families()}
    for name in candidates:
        if name.lower() in available:
            return name
    return tkfont.nametofont(fallback).cget("family")


def fmt_num(value, empty: str = "") -> str:
    """Número como o usuário brasileiro escreve: vírgula decimal.

    Texto que não é número volta intacto — o campo pode estar guardando algo
    que não veio de um float.
    """
    if value is None or value == "":
        return empty
    try:
        return f"{float(value):g}".replace(".", ",")
    except (TypeError, ValueError):
        return str(value)


def parse_num(text, default: float = 0.0) -> float:
    """Lê o que o campo tem, aceitando vírgula ou ponto como decimal."""
    try:
        return float(str(text).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


def rounded_rect(canvas: tk.Canvas, x1, y1, x2, y2, radius, **kwargs):
    """Retângulo de cantos arredondados como polígono suavizado."""
    radius = min(radius, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1,
        x2, y1 + radius, x2, y2 - radius, x2, y2,
        x2 - radius, y2, x1 + radius, y2, x1, y2,
        x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def apply_theme(root: tk.Misc) -> None:
    """Configura fontes e todos os estilos ttk. Chamar antes de criar widgets."""
    family = _pick_family(_FAMILY_CANDIDATES, "TkDefaultFont")
    mono = _pick_family(_MONO_CANDIDATES, "TkFixedFont")

    FONTS.update({
        "h1": (family, 18, "bold"),
        "h2": (family, 13, "bold"),
        "label": (family, 10, "bold"),
        "body": (family, 10),
        "caption": (family, 9),
        "mono": (mono, 9),
        "mono_bold": (mono, 9, "bold"),
        "mono_small": (mono, 8),
    })

    sv_ttk.set_theme("light", root)

    # set_theme roda tk_setPalette, que grava `*background` no banco de opções
    # do Tk. `ttk.Label` tem `-background` própria, e o valor herdado do banco
    # vence o do estilo: sem isto, todo rótulo pinta o #fafafa do sv_ttk e os
    # que ficam sobre o fundo da janela aparecem como retângulos claros.
    # Os que vão sobre a janela pedem `background=COLORS["bg"]` na criação.
    root.option_add("*background", COLORS["surface"])

    style = ttk.Style(root)

    style.configure("Main.TFrame", background=COLORS["bg"])
    # Nome próprio, não "Card.TFrame": esse já existe no sv_ttk, com um sprite
    # de moldura que aparecia por baixo de cada linha de campo.
    style.configure("Surface.TFrame", background=COLORS["surface"])

    style.configure("H1.TLabel", background=COLORS["bg"],
                    foreground=COLORS["primary"], font=FONTS["h1"])
    # Título de página, sobre o fundo da janela (o CardTitle é o de dentro
    # do card, sobre a superfície branca).
    style.configure("H2.TLabel", background=COLORS["bg"],
                    foreground=COLORS["text"], font=FONTS["h2"])
    style.configure("Sub.TLabel", background=COLORS["bg"],
                    foreground=COLORS["text_mute"], font=FONTS["caption"])
    style.configure("CardTitle.TLabel", background=COLORS["surface"],
                    foreground=COLORS["primary"], font=FONTS["h2"])
    style.configure("Label.TLabel", background=COLORS["surface"],
                    foreground=COLORS["text"], font=FONTS["label"])
    style.configure("Body.TLabel", background=COLORS["surface"],
                    foreground=COLORS["text"], font=FONTS["body"])
    style.configure("Caption.TLabel", background=COLORS["surface"],
                    foreground=COLORS["text_mute"], font=FONTS["caption"])

    # Entry, Combobox, Checkbutton, Progressbar, Treeview e Scrollbar não são
    # configurados aqui: os estilos nomeados herdam o visual do sv_ttk. Só
    # sobra o que ele não cobre (fundos de card, fontes, cores de texto).

    style.configure("Modern.TSeparator", background=COLORS["line"])

    # Sem background próprio: o TLabelframe do sv_ttk é um sprite de moldura e
    # pintar o fundo por cima come a borda.
    style.configure("Section.TLabelframe.Label", background=COLORS["surface"],
                    foreground=COLORS["text_mute"], font=FONTS["label"])

    # Só o fundo da faixa de abas: as abas em si são sprites do sv_ttk.
    style.configure("Section.TNotebook", background=COLORS["surface"],
                    borderwidth=0)
    style.configure("Section.TNotebook.Tab", font=FONTS["label"])

    style.configure("Modern.Treeview", rowheight=26, font=FONTS["body"])
    style.configure("Modern.Treeview.Heading", font=FONTS["label"])


class Card(tk.Frame):
    """Superfície branca de cantos arredondados. Conteúdo vai em `.body`."""

    def __init__(self, parent, title: str = "", radius: int = RADIUS["card"],
                 pad: int = SPACE[4], **kwargs):
        super().__init__(parent, bg=COLORS["bg"], highlightthickness=0, bd=0,
                         **kwargs)
        self._radius = radius
        # Fundo desenhado atrás do corpo; o corpo branco fica recuado pelo
        # padding e por isso nunca cobre os cantos arredondados.
        self._bg = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0, bd=0)
        self._bg.place(x=0, y=0, relwidth=1, relheight=1)

        self.body = ttk.Frame(self, style="Surface.TFrame")
        self.body.pack(fill="both", expand=True, padx=pad, pady=pad)

        if title:
            ttk.Label(self.body, text=title, style="CardTitle.TLabel").pack(
                anchor="w", pady=(0, SPACE[3]))

        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event=None):
        width, height = self.winfo_width(), self.winfo_height()
        if width < 4 or height < 4:
            return
        self._bg.delete("shape")
        rounded_rect(self._bg, 1, 1, width - 2, height - 2, self._radius,
                     fill=COLORS["surface"], outline=COLORS["line"], width=1,
                     tags="shape")


def scrollable(parent) -> ttk.Frame:
    """Área com rolagem vertical; devolve o frame onde o conteúdo vai.

    Só é usada dentro de card, então pinta a superfície do card: com o fundo
    da janela, a parte não coberta pelo conteúdo virava uma faixa cinza.
    """
    canvas = tk.Canvas(parent, bg=COLORS["surface"], highlightthickness=0, bd=0)
    bar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=bar.set)
    canvas.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")

    inner = ttk.Frame(canvas, style="Surface.TFrame")
    window = canvas.create_window((0, 0), window=inner, anchor="nw")

    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    # Menos a largura da barra: sem isso a última coluna de botões fica por
    # baixo dela.
    canvas.bind("<Configure>",
                lambda e: canvas.itemconfigure(window, width=e.width - SPACE[3]))

    # A roda só chega ao canvas via bind_all (filhos não propagam), então a
    # captura vale apenas enquanto o ponteiro está sobre esta área — senão o
    # log e os comboboxes perdem a própria rolagem.
    # Tk manda a roda como Button-4/5 no X11 e como MouseWheel no resto.
    def grab(_event=None):
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-e.delta // 120, "units"))

    def release(_event=None):
        for sequence in ("<Button-4>", "<Button-5>", "<MouseWheel>"):
            canvas.unbind_all(sequence)

    canvas.bind("<Enter>", grab)
    canvas.bind("<Leave>", release)
    return inner


#: Cor da borda esquerda de cada tipo de toast.
_TOAST_KINDS = {
    "info": "primary",
    "ok": "ok",
    "warn": "warn",
    "error": "danger",
}


def toast(widget, message: str, kind: str = "info", timeout: int = 5000):
    """Aviso flutuante no canto inferior direito da janela de `widget`.

    Substitui o messagebox nos avisos de clique: não rouba o foco nem exige um
    OK para continuar. Os toasts vivos empilham de baixo para cima.
    """
    window = widget.winfo_toplevel()
    stack = getattr(window, "_toasts", None)
    if stack is None:
        stack = window._toasts = []

    frame = tk.Frame(window, bg=COLORS["surface"], highlightthickness=1,
                     highlightbackground=COLORS["line"])
    tk.Frame(frame, bg=COLORS[_TOAST_KINDS.get(kind, "primary")], width=4).pack(
        side="left", fill="y")
    tk.Label(frame, text=message, bg=COLORS["surface"], fg=COLORS["text"],
             font=FONTS.get("body"), justify="left", wraplength=320,
             padx=SPACE[3], pady=SPACE[3]).pack(side="left")

    def close(_event=None):
        if frame in stack:
            stack.remove(frame)
            frame.destroy()
            _place_toasts(stack)

    # Clicar fecha antes do tempo; um erro longo às vezes atrapalha a leitura.
    frame.bind("<Button-1>", close)
    for child in frame.winfo_children():
        child.bind("<Button-1>", close)

    stack.append(frame)
    _place_toasts(stack)
    frame.after(timeout, close)
    return frame


def _place_toasts(stack):
    offset = SPACE[4]
    for frame in reversed(stack):
        frame.update_idletasks()
        frame.place(relx=1.0, rely=1.0, x=-SPACE[4], y=-offset, anchor="se")
        frame.lift()
        offset += frame.winfo_reqheight() + SPACE[2]


_BUTTON_VARIANTS = {
    "primary": (COLORS["primary"], COLORS["primary_h"], COLORS["primary_d"],
                "#ffffff", None),
    "danger": (COLORS["danger"], "#c8433c", "#8f1e18", "#ffffff", None),
    "ghost": (COLORS["surface"], COLORS["surface_2"], COLORS["line"],
              COLORS["primary"], COLORS["line"]),
    # Sobre o fundo da janela, não sobre um card.
    "bar": (COLORS["bg"], COLORS["surface_2"], COLORS["line"],
            COLORS["primary"], COLORS["line"]),
}


def widget_background(widget) -> str:
    """Cor de fundo real do widget, seja ele tk ou ttk."""
    try:
        return widget.cget("background") or COLORS["surface"]
    except tk.TclError:
        # ttk: a cor vive no estilo, não no widget.
        style = widget.cget("style") or widget.winfo_class()
        return ttk.Style().lookup(style, "background") or COLORS["surface"]


class RoundedButton(tk.Canvas):
    """Botão de cantos arredondados. Variantes: primary, ghost, bar, danger.

    A largura sai do próprio rótulo: todos os botões ficam com a mesma altura,
    o mesmo respiro lateral e a mesma largura mínima, sem número mágico em cada
    chamada. `width=` continua existindo para o caso raro de forçar uma medida.
    """

    _HEIGHT = 34
    _PAD_X = SPACE[4]
    _MIN_WIDTH = 96
    _ICON_SIZE = 16
    _ICON_GAP = SPACE[2]

    def __init__(self, parent, text: str, command=None, variant: str = "primary",
                 icon: str = None, width: int = None,
                 radius: int = RADIUS["control"]):
        super().__init__(parent, height=self._HEIGHT,
                         width=width or self._width_for(text, icon),
                         bg=widget_background(parent), highlightthickness=0, bd=0,
                         takefocus=1)
        self._fixed_width = width
        self._icon = icon
        self._text = text
        self._command = command
        self._variant = variant
        self._radius = radius
        self._state = "normal"
        self._hover = False
        self._pressed = False

        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    @classmethod
    def _width_for(cls, text: str, icon_name: str = None) -> int:
        """Largura do conteúdo mais o respiro lateral, nunca abaixo do mínimo."""
        try:
            measured = tkfont.Font(font=FONTS["body"]).measure(text)
        except (tk.TclError, KeyError):
            # Antes do apply_theme não há fonte resolvida para medir.
            measured = len(text) * 8
        if icon_name:
            measured += cls._ICON_SIZE + cls._ICON_GAP
        return max(cls._MIN_WIDTH, measured + 2 * cls._PAD_X)

    def configure(self, **kwargs):  # type: ignore[override]
        """Aceita text/variant/command/state; o resto vai para o Canvas."""
        redraw = False
        for key in ("text", "variant", "command", "state", "icon"):
            if key in kwargs:
                setattr(self, f"_{key}", kwargs.pop(key))
                redraw = True
        # Trocar o rótulo (Executar/Parar) refaz a largura, a menos que a
        # chamada tenha fixado uma.
        if redraw and self._fixed_width is None:
            super().configure(width=self._width_for(self._text, self._icon))
        result = super().configure(**kwargs) if kwargs else None
        if redraw:
            self._redraw()
        return result

    config = configure

    def _colors(self):
        base, hover, pressed, fg, outline = _BUTTON_VARIANTS[self._variant]
        # Ghost e bar não têm cor própria: são o fundo de quem os hospeda. Fixar
        # `surface` deixava o botão claro sobre um pai cinza (e vice-versa).
        if self._variant in ("ghost", "bar"):
            base = widget_background(self.master)
        if self._state == "disabled":
            return COLORS["surface_2"], COLORS["text_mute"], COLORS["line"]
        if self._pressed:
            return pressed, fg, outline
        if self._hover:
            return hover, fg, outline
        return base, fg, outline

    def _redraw(self):
        width, height = self.winfo_width(), self.winfo_height()
        if width < 4 or height < 4:
            return
        fill, fg, outline = self._colors()
        self.delete("all")
        rounded_rect(self, 1, 1, width - 2, height - 2, self._radius,
                     fill=fill, outline=outline or fill, width=1)

        # O ícone é uma imagem na cor do texto; o par ícone + rótulo fica
        # centralizado como um bloco só.
        image = icon(self._icon, self._ICON_SIZE, fg, master=self) if self._icon else None
        if image is None:
            self.create_text(width / 2, height / 2, text=self._text, fill=fg,
                             font=FONTS["body"])
            return

        text_width = tkfont.Font(font=FONTS["body"]).measure(self._text)
        block = self._ICON_SIZE + self._ICON_GAP + text_width
        left = (width - block) / 2
        # A referência da imagem vive no cache do módulo; o Tk não segura a sua.
        self.create_image(left + self._ICON_SIZE / 2, height / 2, image=image)
        self.create_text(left + self._ICON_SIZE + self._ICON_GAP, height / 2,
                         text=self._text, fill=fg, font=FONTS["body"],
                         anchor="w")

    def _on_enter(self, _event):
        self._hover = True
        self._redraw()

    def _on_leave(self, _event):
        self._hover = self._pressed = False
        self._redraw()

    def _on_press(self, _event):
        if self._state == "disabled":
            return
        self._pressed = True
        self._redraw()

    def _on_release(self, _event):
        was_pressed, self._pressed = self._pressed, False
        self._redraw()
        if was_pressed and self._state != "disabled" and self._command:
            self._command()


class RangeField(ttk.Frame):
    """Faixa mínimo–máximo: um campo numérico em cada ponta e um trilho de
    dois cursores entre eles. Campo e cursor são a mesma informação — mexer
    num atualiza o outro.

    `min_entry` e `max_entry` são `ttk.Entry` de verdade: quem lê a
    configuração continua chamando `.get()` neles.
    """

    _TRACK_HEIGHT = 30
    _HANDLE = 7

    def __init__(self, parent, label: str, lower: float, upper: float,
                 step: float = 0.1, on_change=None, entry_width: int = 7):
        super().__init__(parent, style="Surface.TFrame")
        self._lower, self._upper, self._step = lower, upper, step
        self._on_change = on_change
        self._dragging = None

        ttk.Label(self, text=label, style="Label.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, SPACE[1]))

        self.min_entry = ttk.Entry(self, style="Field.TEntry",
                                   width=entry_width, justify="center")
        self.min_entry.grid(row=1, column=0, sticky="w")

        self._track = tk.Canvas(self, height=self._TRACK_HEIGHT,
                                bg=COLORS["surface"], highlightthickness=0,
                                bd=0)
        self._track.grid(row=1, column=1, sticky="ew", padx=SPACE[2])
        self.columnconfigure(1, weight=1)

        self.max_entry = ttk.Entry(self, style="Field.TEntry",
                                   width=entry_width, justify="center")
        self.max_entry.grid(row=1, column=2, sticky="e")

        for entry in (self.min_entry, self.max_entry):
            entry.bind("<KeyRelease>", self._from_entries)
            entry.bind("<FocusOut>", self._commit)

        self._track.bind("<Configure>", lambda e: self._redraw())
        self._track.bind("<ButtonPress-1>", self._on_press)
        self._track.bind("<B1-Motion>", self._on_drag)
        self._track.bind("<ButtonRelease-1>", self._on_release)

    # -- valores -----------------------------------------------------------
    def get(self) -> tuple:
        """(mínimo, máximo) já ordenados e dentro do domínio."""
        low = self._read(self.min_entry, self._lower)
        high = self._read(self.max_entry, self._upper)
        if low > high:
            low, high = high, low
        return low, high

    def set(self, low, high):
        self._write(self.min_entry, self._clamp(low))
        self._write(self.max_entry, self._clamp(high))
        self._redraw()

    def _read(self, entry, fallback):
        text = entry.get().strip()
        if not text:
            return fallback
        return self._clamp(parse_num(text, fallback))

    def _write(self, entry, value):
        entry.delete(0, tk.END)
        entry.insert(0, fmt_num(value))

    def _clamp(self, value):
        return min(max(float(value), self._lower), self._upper)

    def _snap(self, value):
        return round(round(value / self._step) * self._step, 6)

    # -- geometria ---------------------------------------------------------
    def _span(self):
        width = self._track.winfo_width()
        return self._HANDLE, max(width - self._HANDLE, self._HANDLE + 1)

    def _to_x(self, value):
        left, right = self._span()
        ratio = (value - self._lower) / (self._upper - self._lower)
        return left + ratio * (right - left)

    def _to_value(self, x):
        left, right = self._span()
        ratio = (x - left) / (right - left)
        return self._clamp(self._lower + ratio * (self._upper - self._lower))

    # -- desenho e interação ----------------------------------------------
    def _redraw(self):
        width = self._track.winfo_width()
        if width < 8:
            return
        low, high = self.get()
        middle = self._TRACK_HEIGHT / 2
        left, right = self._span()

        self._track.delete("all")
        self._track.create_line(left, middle, right, middle,
                                fill=COLORS["surface_2"], width=6,
                                capstyle="round")
        self._track.create_line(self._to_x(low), middle, self._to_x(high),
                                middle, fill=COLORS["primary"], width=6,
                                capstyle="round")
        for value in (low, high):
            x = self._to_x(value)
            self._track.create_oval(x - self._HANDLE, middle - self._HANDLE,
                                    x + self._HANDLE, middle + self._HANDLE,
                                    fill=COLORS["surface"],
                                    outline=COLORS["primary"], width=2)

    def _from_entries(self, _event=None):
        self._redraw()

    def _commit(self, _event=None):
        low, high = self.get()
        self.set(low, high)
        if self._on_change:
            self._on_change()

    def _on_press(self, event):
        low, high = self.get()
        # Arrasta o cursor mais próximo do clique.
        self._dragging = ("min" if abs(event.x - self._to_x(low))
                          <= abs(event.x - self._to_x(high)) else "max")
        self._on_drag(event)

    def _on_drag(self, event):
        if not self._dragging:
            return
        value = self._snap(self._to_value(event.x))
        low, high = self.get()
        if self._dragging == "min":
            self._write(self.min_entry, min(value, high))
        else:
            self._write(self.max_entry, max(value, low))
        self._redraw()

    def _on_release(self, _event):
        if self._dragging:
            self._dragging = None
            self._commit()


class BottomSheet(ttk.Frame):
    """Painel inferior colapsável, no espírito do painel do VS Code: uma barra
    sempre visível e o conteúdo (em `.body`) que abre e fecha."""

    def __init__(self, parent, title: str):
        super().__init__(parent, style="Main.TFrame")
        self._open = False

        bar = ttk.Frame(self, style="Main.TFrame")
        bar.pack(fill="x")

        self._toggle = RoundedButton(bar, text=title, variant="bar",
                                     icon="chevron-right", command=self.toggle)
        self._toggle.configure(bg=COLORS["bg"])
        self._toggle.pack(side="left")
        self._title = title

        self.actions = ttk.Frame(bar, style="Main.TFrame")
        self.actions.pack(side="right")

        self._holder = Card(self, pad=SPACE[3])
        self.body = self._holder.body

    def toggle(self):
        self.set_open(not self._open)

    def set_open(self, is_open: bool):
        self._open = is_open
        if is_open:
            self._holder.pack(fill="both", expand=True, pady=(SPACE[2], 0))
        else:
            self._holder.pack_forget()
        self._toggle.configure(text=self._title,
                               icon="chevron-down" if is_open else "chevron-right")

    @property
    def is_open(self) -> bool:
        return self._open


class ChipSelect(ttk.Frame):
    """Escolha de vários itens: um combobox lista as opções e cada escolha
    vira um chip removível. Aceita valor digitado quando não há opções (IDF
    ainda não lido, por exemplo)."""

    def __init__(self, parent, placeholder: str = "Adicionar…", on_change=None):
        super().__init__(parent, style="Surface.TFrame")
        self._placeholder = placeholder
        self._on_change = on_change
        self._values: list = []

        self._var = tk.StringVar(value=placeholder)
        self._combo = ttk.Combobox(self, textvariable=self._var,
                                   style="Field.TCombobox", state="readonly")
        self._combo.grid(row=0, column=0, sticky="ew")
        self._combo.bind("<<ComboboxSelected>>", self._on_pick)
        self._combo.bind("<Return>", self._on_pick)
        self.columnconfigure(0, weight=1)

        self._chips = ttk.Frame(self, style="Surface.TFrame")
        self._chips.grid(row=1, column=0, sticky="ew", pady=(SPACE[2], 0))

        self.set_options([])

    def set_options(self, options):
        """Opções do combobox; some as já escolhidas."""
        self._option_list = list(options)
        remaining = [o for o in self._option_list if o not in self._values]
        self._combo["values"] = remaining
        # Sem opções conhecidas, o campo vira texto livre: melhor digitar o
        # nome da zona do que ficar travado.
        self._combo["state"] = "readonly" if self._option_list else "normal"
        self._var.set(self._placeholder if self._option_list else "")

    def get_values(self) -> list:
        return list(self._values)

    def set_values(self, values):
        # `rooms` vem nulo em configuração antiga; sem isso duplicar aquela
        # execução quebrava aqui.
        self._values = [v for v in dict.fromkeys(values or []) if v]
        self.set_options(self._option_list)
        self._render_chips()

    def _on_pick(self, _event=None):
        value = self._var.get().strip()
        if value and value != self._placeholder and value not in self._values:
            self._values.append(value)
            self.set_options(self._option_list)
            self._render_chips()
            if self._on_change:
                self._on_change()

    def _remove(self, value):
        self._values.remove(value)
        self.set_options(self._option_list)
        self._render_chips()
        if self._on_change:
            self._on_change()

    def _render_chips(self):
        for child in self._chips.winfo_children():
            child.destroy()
        if not self._values:
            ttk.Label(self._chips, text="Nenhuma sala selecionada",
                      style="Caption.TLabel").pack(anchor="w")
            return
        for value in self._values:
            chip = tk.Frame(self._chips, bg=COLORS["surface_2"],
                            highlightthickness=1,
                            highlightbackground=COLORS["line"])
            chip.pack(side="left", padx=(0, SPACE[2]), pady=(0, SPACE[1]))
            tk.Label(chip, text=value, bg=COLORS["surface_2"],
                     fg=COLORS["text"], font=FONTS["body"]).pack(
                         side="left", padx=(SPACE[2], SPACE[1]), pady=SPACE[1])
            close = tk.Label(chip, text="×", bg=COLORS["surface_2"],
                             fg=COLORS["text_mute"], font=FONTS["label"],
                             cursor="hand2")
            close.pack(side="left", padx=(0, SPACE[2]))
            close.bind("<Button-1>", lambda e, v=value: self._remove(v))


# Estado: fundo, cor do texto e nome do ícone (o mesmo do estado).
_PILL_STATES = {
    "info": (COLORS["surface_2"], COLORS["text"]),
    "running": (COLORS["surface_2"], COLORS["text"]),
    "success": (COLORS["ok"], "#ffffff"),
    "warning": (COLORS["warn"], "#ffffff"),
    "error": (COLORS["danger"], "#ffffff"),
}


class StatusPill(tk.Canvas):
    """Cápsula de estado: ícone + texto sobre fundo derivado do estado."""

    _HEIGHT = 28
    _ICON_SIZE = 14
    _ICON_GAP = SPACE[2]

    def __init__(self, parent, text: str = "", state: str = "info"):
        super().__init__(parent, height=self._HEIGHT, bg=COLORS["surface"],
                         highlightthickness=0, bd=0)
        self._text = text
        self._state = state
        self.bind("<Configure>", lambda e: self._redraw())
        self._resize()

    def set(self, text: str, state: str = "info"):
        self._text, self._state = text, state
        self._resize()
        self._redraw()

    def _resize(self):
        """A cápsula acompanha o texto — não deve esticar pela linha toda."""
        width = tkfont.Font(font=FONTS["body"]).measure(self._text)
        self.configure(width=width + self._ICON_SIZE + self._ICON_GAP + SPACE[5])

    def _redraw(self):
        width, height = self.winfo_width(), self.winfo_height()
        if width < 4 or height < 4:
            return
        fill, fg = _PILL_STATES.get(self._state, _PILL_STATES["info"])
        self.delete("all")
        # A pill neutra é quase da cor do card: sem a borda ela some.
        outline = COLORS["line"] if fill == COLORS["surface_2"] else fill
        rounded_rect(self, 1, 1, width - 2, height - 2, height / 2,
                     fill=fill, outline=outline)

        image = icon(self._state, self._ICON_SIZE, fg, master=self)
        text_width = tkfont.Font(font=FONTS["body"]).measure(self._text)
        if image is None:
            self.create_text(width / 2, height / 2, text=self._text, fill=fg,
                             font=FONTS["body"])
            return
        left = (width - (self._ICON_SIZE + self._ICON_GAP + text_width)) / 2
        self.create_image(left + self._ICON_SIZE / 2, height / 2, image=image)
        self.create_text(left + self._ICON_SIZE + self._ICON_GAP, height / 2,
                         text=self._text, fill=fg, font=FONTS["body"],
                         anchor="w")


def demo():
    """Auto-checagem: tokens resolvidos, estilos registrados, widgets desenham."""
    root = tk.Tk()
    root.geometry("400x300")
    apply_theme(root)
    assert FONTS["body"][1] == 10, FONTS
    assert ttk.Style(root).lookup("CardTitle.TLabel", "foreground") == COLORS["primary"]

    card = Card(root, "Título")
    card.pack(fill="both", expand=True)
    button = RoundedButton(card.body, "Executar", variant="primary")
    button.pack()
    pill = StatusPill(card.body, "Pronto", "success")
    pill.pack(fill="x")
    root.update()

    assert card._bg.find_withtag("shape"), "card sem forma desenhada"
    assert button.find_all(), "botão sem forma desenhada"
    # Largura vem do rótulo: rótulo curto encolhe até o mínimo, rótulo longo
    # cresce com ele.
    assert button.winfo_reqwidth() == RoundedButton._MIN_WIDTH
    largo = RoundedButton(card.body, "Comparar as execuções selecionadas")
    assert largo.winfo_reqwidth() > button.winfo_reqwidth()

    com_icone = RoundedButton(card.body, "Executar", icon="play")
    com_icone.pack()
    root.update()
    assert icon("play", master=root) is not None, "fonte de ícones não carregou"
    # Forma, ícone e rótulo: sem o ícone o canvas teria só dois itens.
    assert len(com_icone.find_all()) == 3
    button.configure(state="disabled")
    assert button._colors()[0] == COLORS["surface_2"]
    pill.set("Falhou", "error")
    assert pill.find_all()

    rng = RangeField(card.body, "PMV", -3.0, 3.0, 0.1)
    rng.pack(fill="x")
    rng.set(-0.5, 0.5)
    root.update()
    assert rng.get() == (-0.5, 0.5), rng.get()
    rng.set(-9, 9)                       # fora do domínio: precisa grampear
    assert rng.get() == (-3.0, 3.0), rng.get()
    rng.min_entry.delete(0, tk.END)      # campo vazio não pode virar exceção
    assert rng.get() == (-3.0, 3.0), rng.get()
    rng.set(1.0, -1.0)                   # invertido: sai ordenado
    assert rng.get() == (-1.0, 1.0), rng.get()
    assert rng._to_value(rng._to_x(2.0)) == 2.0
    # Vírgula na tela, float na leitura — e ponto digitado continua valendo.
    rng.set(-0.5, 1.5)
    assert rng.min_entry.get() == "-0,5", rng.min_entry.get()
    rng.max_entry.delete(0, tk.END)
    rng.max_entry.insert(0, "2.5")
    assert rng.get() == (-0.5, 2.5), rng.get()
    assert fmt_num("") == "" and fmt_num(None) == "" and fmt_num("abc") == "abc"
    assert fmt_num(1000) == "1000" and fmt_num(0.15) == "0,15"
    assert parse_num("0,15") == 0.15 and parse_num("", 7.0) == 7.0

    chips = ChipSelect(card.body)
    chips.pack(fill="x")
    chips.set_options(["A", "B"])
    chips.set_values(["A", "A", ""])          # duplicatas e vazio caem fora
    assert chips.get_values() == ["A"], chips.get_values()
    assert list(chips._combo["values"]) == ["B"]   # já escolhida sai da lista
    chips._remove("A")
    assert chips.get_values() == []

    # Janela própria: o card acima já ocupa a primeira.
    window = tk.Toplevel(root)
    window.geometry("500x300")
    sheet = BottomSheet(window, "Log")
    sheet.pack(fill="both", expand=True)
    ttk.Label(sheet.body, text="conteúdo", style="Body.TLabel").pack()
    root.update()
    assert not sheet.is_open and not sheet._holder.winfo_ismapped()
    sheet.toggle()
    root.update()
    assert sheet.is_open and sheet._holder.winfo_ismapped()
    window.destroy()
    root.destroy()
    print("theme ok")


if __name__ == "__main__":
    demo()
