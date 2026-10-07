"""
Painel de edição dos campos do IDF usados pelas simulações.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from types import SimpleNamespace

from ..theme import COLORS, SPACE, RoundedButton, Tooltip, icon, scrollable, toast
from confortimetro.idf import (
    describe_changes, PEOPLE_METHODS, PEOPLE_METHOD_FIELD, read_people, read_run_period,
    read_timesteps_per_hour,
)
from confortimetro.idf.processor import PEOPLE_FIELDS


class IDFEditorPanel(ttk.Frame):
    """Período, passo de tempo e ocupação lidos e reescritos no IDF.

    O painel não grava nada: `get_updates` devolve só o que mudou, no formato
    que `write_idf_fields` espera, e quem salva é a `MainWindow`.
    """

    def __init__(self, notebook, on_save=None):
        """Controla abas inseridas diretamente no notebook principal.

        Período e Ocupação não ficam sob uma aba intermediária "Editar IDF".
        """
        super().__init__(notebook, style="Surface.TFrame")
        self.notebook = notebook
        self.on_save = on_save
        self.idf_path = ""
        self._people = []
        self._people_widgets = []
        self._loaded = {}
        self._build_ui()
        # A SimulationConfigPanel dona do notebook leva o período e o passo
        # junto com a configuração, para valerem na simulação sem gravar IDF.
        register = getattr(notebook.master, "register_extra", None)
        if register:
            register(self.config_fields, self.apply_config)
        notebook.bind("<<NotebookTabChanged>>", self._refresh_changes, add="+")

    def _build_ui(self):
        self.period_tab = self._tab("Período", "timestep")
        ttk.Label(
            self.period_tab,
            text=("Edite apenas o que deseja mudar. Campos em branco preservam "
                  "os valores atuais do IDF."),
            style="Caption.TLabel", justify="left").grid(
                row=0, column=0, columnspan=4, padx=SPACE[1],
                pady=(0, SPACE[2]), sticky="w")
        self.start_entry = self._field(self.period_tab, 1, 0,
                                       "Início (dd/mm/aaaa)")
        self.end_entry = self._field(self.period_tab, 1, 1,
                                      "Fim (dd/mm/aaaa)")
        self.timestep_entry = self._field(self.period_tab, 1, 2,
                                            "Passos por hora")
        ttk.Label(self.period_tab,
                  text=("As datas e os passos informados valem para a próxima "
                        "simulação (a cópia da execução); o IDF original só "
                        "muda ao salvar como novo."),
                  style="Caption.TLabel").grid(
                      row=3, column=0, columnspan=4, padx=SPACE[1],
                      pady=(SPACE[1], 0), sticky="w")
        if self.on_save:
            RoundedButton(self.period_tab, text="Salvar como novo IDF", icon="save",
                          command=self.on_save).grid(
                              row=4, column=0, padx=SPACE[1], pady=(SPACE[3], 0),
                              sticky="w")
        changes = ttk.Labelframe(self.period_tab, style="Section.TLabelframe",
                                 text="O que o Ambiens altera no IDF da execução",
                                 padding=SPACE[2])
        changes.grid(row=5, column=0, columnspan=4, padx=SPACE[1],
                     pady=(SPACE[3], 0), sticky="ew")
        self.changes_label = ttk.Label(changes, text="", style="Caption.TLabel",
                                       justify="left", wraplength=600)
        self.changes_label.pack(anchor="w")

        # A ocupação tem uma linha por objeto People: o número deles só é
        # conhecido no `load`, então a aba é remontada a cada IDF.
        self.occupation_tab = ttk.Frame(self.notebook, style="Surface.TFrame",
                                        padding=SPACE[3])
        self._add_tab(self.occupation_tab, "Ocupação", "details")
        self.people_tab = scrollable(self.occupation_tab)
        for column in range(4):
            self.people_tab.columnconfigure(column, weight=1, uniform="fields")

    def _tab(self, title: str, icon_name: str = None) -> ttk.Frame:
        frame = ttk.Frame(self.notebook, style="Surface.TFrame",
                          padding=SPACE[3])
        self._add_tab(frame, title, icon_name)
        for column in range(4):
            frame.columnconfigure(column, weight=1, uniform="fields")
        return frame

    def _add_tab(self, frame, title: str, icon_name: str = None):
        """Aba do notebook, com ícone quando houver um para o assunto."""
        image = icon(icon_name, 16, COLORS["text_mute"], master=self) \
            if icon_name else None
        if image is None:
            self.notebook.add(frame, text=title)
            return
        self.notebook.add(frame, text=f" {title}", image=image,
                          compound="left")

    def _field(self, parent, row: int, column: int, label: str,
               help: str = "") -> ttk.Entry:
        caption = ttk.Label(parent, text=label, style="Label.TLabel")
        caption.grid(row=row, column=column, padx=SPACE[1], pady=(0, SPACE[1]),
                     sticky="w")
        entry = ttk.Entry(parent, style="Field.TEntry")
        entry.grid(row=row + 1, column=column, padx=SPACE[1],
                   pady=(0, SPACE[2]), sticky="ew")
        if help:
            Tooltip(caption, help)
            Tooltip(entry, help)
        return entry

    # ------------------------------------------- período na configuração

    def config_fields(self) -> dict:
        """Período e passo a aplicar ao IDF da execução (`SimulationConfig`).

        Só o que difere do IDF carregado; `None` mantém o do arquivo. Data ou
        passo inválido levanta `ValueError` (e bloqueia a execução).
        """
        fields = {"run_period_start": None, "run_period_end": None,
                  "timesteps_per_hour": None}
        if not self._loaded:
            return fields
        dates = {}
        for key, entry, label in (("start", self.start_entry, "Início"),
                                  ("end", self.end_entry, "Fim")):
            text = entry.get().strip() or self._loaded[key]
            try:
                dates[key] = datetime.strptime(text, "%d/%m/%Y")
            except ValueError:
                raise ValueError(f"Período, {label}: “{text}” não é uma data "
                                 "dd/mm/aaaa.") from None
        if dates["end"] < dates["start"]:
            raise ValueError("Período: o fim vem antes do início.")
        if (dates["start"].strftime("%d/%m/%Y") != self._loaded["start"]
                or dates["end"].strftime("%d/%m/%Y") != self._loaded["end"]):
            fields["run_period_start"] = dates["start"].strftime("%Y-%m-%d")
            fields["run_period_end"] = dates["end"].strftime("%Y-%m-%d")
        text = self.timestep_entry.get().strip()
        if text and text != self._loaded["timestep"]:
            try:
                steps = int(float(text.replace(",", ".")))
            except ValueError:
                raise ValueError(f"Passos por hora: “{text}” não é um "
                                 "número.") from None
            if not 1 <= steps <= 60:
                raise ValueError("Passos por hora deve ficar entre 1 e 60.")
            fields["timesteps_per_hour"] = steps
        return fields

    def apply_config(self, config: dict):
        """Restaura na tela o período e o passo salvos na configuração."""
        for key, entry in (("run_period_start", self.start_entry),
                           ("run_period_end", self.end_entry)):
            try:
                text = datetime.strptime(config[key], "%Y-%m-%d").strftime("%d/%m/%Y")
            except (KeyError, TypeError, ValueError):
                continue
            entry.delete(0, tk.END)
            entry.insert(0, text)
        if config.get("timesteps_per_hour"):
            self.timestep_entry.delete(0, tk.END)
            self.timestep_entry.insert(0, str(config["timesteps_per_hour"]))

    def _refresh_changes(self, _event=None):
        """Resumo do que o processador grava no IDF, com a configuração atual."""
        host = getattr(self.notebook, "master", None)
        try:
            config = host.get_configuration()
            config["met_as_watts"] = config["met"] * 58.1 * 1.8
            lines = describe_changes(SimpleNamespace(**config))
        except Exception:     # configuração incompleta: o erro aparece ao executar
            lines = ["Corrija os campos em vermelho nas abas de configuração "
                     "para ver o resumo."]
        self.changes_label.configure(text="\n".join(f"• {line}" for line in lines))

    # ------------------------------------------------------------- leitura

    def load(self, idf_path: str):
        """Preenche o painel com os valores do IDF escolhido.

        IDF ilegível deixa os campos vazios em vez de levantar exceção, como
        as demais leituras de texto do `processor`.
        """
        self.idf_path = idf_path
        start, end = read_run_period(idf_path)
        # O fim guardado é exclusivo; o usuário edita o último dia simulado.
        self._loaded = {
            "start": start.strftime("%d/%m/%Y"),
            "end": (end - timedelta(days=1)).strftime("%d/%m/%Y"),
            "timestep": str(read_timesteps_per_hour(idf_path)),
        }
        for entry, key in ((self.start_entry, "start"),
                           (self.end_entry, "end"),
                           (self.timestep_entry, "timestep")):
            entry.delete(0, tk.END)
            entry.insert(0, self._loaded[key])

        self._people = read_people(idf_path)
        self._build_people_rows()
        self._refresh_changes()

    def _build_people_rows(self):
        for widget in self.people_tab.winfo_children():
            widget.destroy()
        self._people_widgets = []

        if not self._people:
            ttk.Label(self.people_tab, style="Body.TLabel",
                      text="Nenhum objeto People no IDF.").grid(
                          row=0, column=0, columnspan=4, padx=SPACE[1],
                          sticky="w")
            self._add_people_save_button(1)
            return

        for position, person in enumerate(self._people):
            row = position * 3
            ttk.Label(self.people_tab, style="CardTitle.TLabel",
                      text=f"{person['name']} — zona {person['zone']}").grid(
                          row=row, column=0, columnspan=4, padx=SPACE[1],
                          pady=(SPACE[2], SPACE[1]), sticky="w")

            schedule = self._field(self.people_tab, row + 1, 0,
                                   "Schedule de ocupação",
                                   help="Nome do schedule que dá a fração de "
                                        "ocupação ao longo do tempo.")
            schedule.insert(0, person["schedule"])

            method = tk.StringVar(value=person["method"] or PEOPLE_METHODS[0])
            ttk.Label(self.people_tab, text="Método de cálculo",
                      style="Label.TLabel").grid(
                          row=row + 1, column=1, padx=SPACE[1],
                          pady=(0, SPACE[1]), sticky="w")
            combo = ttk.Combobox(self.people_tab, textvariable=method,
                                 style="Field.TCombobox", state="readonly",
                                 values=list(PEOPLE_METHODS))
            combo.grid(row=row + 2, column=1, padx=SPACE[1],
                       pady=(0, SPACE[2]), sticky="ew")
            Tooltip(combo, "Como o EnergyPlus calcula o número de ocupantes "
                           "da zona.")

            value = self._field(self.people_tab, row + 1, 2, "Valor do método",
                                help="Número do método escolhido: pessoas, "
                                     "pessoas por m² ou m² por pessoa.")
            value.insert(0, self._method_value(person))

            self._people_widgets.append({
                "person": person, "schedule": schedule, "method": method,
                "value": value,
            })
        self._add_people_save_button(len(self._people) * 3)

    def _add_people_save_button(self, row: int):
        if self.on_save:
            RoundedButton(self.people_tab, text="Salvar como novo IDF", icon="save",
                          command=self.on_save).grid(
                              row=row, column=0, padx=SPACE[1], pady=(SPACE[3], SPACE[2]),
                              sticky="w")

    @staticmethod
    def _method_value(person: dict) -> str:
        """Valor do campo que o método de cálculo do objeto usa."""
        key = PEOPLE_METHOD_FIELD.get(person["method"].lower(), "people")
        return person[key]

    # -------------------------------------------------------------- escrita

    def get_updates(self):
        """Campos alterados, no formato de `write_idf_fields`.

        Devolve `None` quando alguma data ou número está inválido — um erro
        silencioso aqui geraria um IDF que o EnergyPlus recusa horas depois.
        """
        updates = {}

        period = self._period_updates()
        if period is None:
            return None
        updates.update(period)

        timestep = self.timestep_entry.get().strip()
        if timestep and timestep != self._loaded["timestep"]:
            try:
                steps = int(float(timestep.replace(",", ".")))
            except ValueError:
                toast(self, f"Passos por hora inválido: {timestep}", "error")
                return None
            if steps < 1 or steps > 60:
                toast(self, "Passos por hora deve ficar entre 1 e 60.", "error")
                return None
            updates[("Timestep", 0)] = {0: str(steps)}

        people = self._people_updates()
        if people is None:
            return None
        updates.update(people)
        return updates

    def _parse_date(self, entry, label: str):
        text = entry.get().strip()
        if not text:
            return None
        try:
            return datetime.strptime(text, "%d/%m/%Y")
        except ValueError:
            toast(self, f"{label} inválida: use dd/mm/aaaa.", "error")
            return "erro"

    def _period_updates(self):
        start = self._parse_date(self.start_entry, "Data de início")
        end = self._parse_date(self.end_entry, "Data de fim")
        if start == "erro" or end == "erro":
            return None
        if start is None and end is None:
            return {}
        # Campo vazio significa "não alterar", como nos demais campos do
        # editor. Assim é possível ajustar só uma ponta do período.
        if start is None:
            start = datetime.strptime(self._loaded["start"], "%d/%m/%Y")
        if end is None:
            end = datetime.strptime(self._loaded["end"], "%d/%m/%Y")
        if end < start:
            toast(self, "O fim do período vem antes do início.", "error")
            return None
        if (self.start_entry.get().strip() == self._loaded["start"]
                and self.end_entry.get().strip() == self._loaded["end"]):
            return {}
        # Ano em branco quando bate com o ano do EPW não é o caso aqui: o
        # usuário escolheu datas completas, então os dois anos vão junto.
        return {("RunPeriod", 0): {
            1: str(start.month), 2: str(start.day), 3: str(start.year),
            4: str(end.month), 5: str(end.day), 6: str(end.year),
        }}

    def _people_updates(self):
        updates = {}
        for widgets in self._people_widgets:
            person = widgets["person"]
            changes = {}

            schedule = widgets["schedule"].get().strip()
            if schedule and schedule != person["schedule"]:
                changes[PEOPLE_FIELDS["schedule"]] = schedule

            method = widgets["method"].get()
            value = widgets["value"].get().strip().replace(",", ".")
            if value:
                try:
                    float(value)
                except ValueError:
                    toast(self, f"Valor de ocupação inválido em "
                                f"{person['name']}: {value}", "error")
                    return None

            if method != person["method"]:
                changes[PEOPLE_FIELDS["method"]] = method
                # Trocar de método esvazia os outros dois campos: o
                # EnergyPlus recusa o objeto com mais de um preenchido.
                for key, field in PEOPLE_METHOD_FIELD.items():
                    position = PEOPLE_FIELDS[field]
                    changes[position] = value if key == method.lower() else ""
            elif value and value != self._method_value(person):
                changes[PEOPLE_FIELDS[
                    PEOPLE_METHOD_FIELD.get(method.lower(), "people")]] = value

            if changes:
                updates[("People", person["index"])] = changes
        return updates
