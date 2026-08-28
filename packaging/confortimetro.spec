# PyInstaller spec do Confortímetro Klimaa (GUI Tkinter, Windows).
# Build (a partir da raiz do repositório):
#   pyinstaller packaging/confortimetro.spec --noconfirm
#
# O pyenergyplus NÃO é embutido: ele é carregado em tempo de execução da
# instalação do EnergyPlus 9.4 da máquina (confortimetro/simulation.py).

import os

from PyInstaller.utils.hooks import collect_all

# Caminhos no spec são resolvidos em relação ao próprio arquivo, não ao
# diretório de onde o pyinstaller foi chamado.
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    (os.path.join(ROOT, "examples", "config.json"), "examples"),
    (os.path.join(ROOT, "examples", "idf"), "examples/idf"),
    (os.path.join(ROOT, "examples", "epw"), "examples/epw"),
]
binaries = []
hiddenimports = []

# Pacotes com dados/tabelas próprios que o analisador estático não enxerga.
# esoreader é um módulo solto (não pacote); o PyInstaller o pega sozinho.
for pkg in ("pythermalcomfort", "ladybug_comfort", "ladybug", "eppy"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["flask", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="ConfortimetroKlimaa",
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="ConfortimetroKlimaa",
)
