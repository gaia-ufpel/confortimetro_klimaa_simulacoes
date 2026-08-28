# PyInstaller spec do Confortímetro Klimaa (GUI Tkinter, Windows).
# Build (a partir da raiz do repositório):
#   pyinstaller packaging/confortimetro.spec --noconfirm
#
# O pyenergyplus NÃO é embutido: ele é carregado em tempo de execução da
# instalação do EnergyPlus 9.4 da máquina (confortimetro/simulation.py).

from PyInstaller.utils.hooks import collect_all

datas = [
    ("examples/config.json", "examples"),
    ("examples/idf", "examples/idf"),
    ("examples/epw", "examples/epw"),
]
binaries = []
hiddenimports = []

# Pacotes com dados/tabelas próprios que o analisador estático não enxerga.
for pkg in ("pythermalcomfort", "ladybug_comfort", "ladybug", "eppy", "esoreader"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ["main.py"],
    pathex=["."],
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
