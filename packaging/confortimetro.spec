# PyInstaller spec do Ambiens (GUI Tkinter, Windows).
# Build (a partir da raiz do repositório):
#   pyinstaller packaging/confortimetro.spec --noconfirm
#
# O pyenergyplus NÃO é embutido: ele é carregado em tempo de execução da
# instalação do EnergyPlus 9.4 da máquina (confortimetro/simulation.py).

import os

from PyInstaller.utils.hooks import collect_all, collect_data_files

# Caminhos no spec são resolvidos em relação ao próprio arquivo, não ao
# diretório de onde o pyinstaller foi chamado.
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    # A fonte de ícones é lida em tempo de execução pelo Pillow (theme.icon),
    # então precisa existir como arquivo dentro do bundle.
    (os.path.join(ROOT, "confortimetro", "gui", "assets"),
     "confortimetro/gui/assets"),
    # O assistente lê o código do controlador (ferramenta codigo_controle); no
    # PYZ só há bytecode, então os .py vão como arquivos.
    (os.path.join(ROOT, "confortimetro", "control", "*.py"),
     "confortimetro/control"),
    # Municípios e zonas bioclimáticas da etiquetagem INI-C, lidos do disco.
    (os.path.join(ROOT, "confortimetro", "etiquetagem", "zonas_bioclimaticas.csv"),
     "confortimetro/etiquetagem"),
    # Texto das normas e guia que o assistente consulta (assistant/normas.py).
    (os.path.join(ROOT, "confortimetro", "assistant", "normas"),
     "confortimetro/assistant/normas"),
    (os.path.join(ROOT, "examples", "config.json"), "examples"),
    (os.path.join(ROOT, "examples", "idf"), "examples/idf"),
    (os.path.join(ROOT, "examples", "epw"), "examples/epw"),
]
binaries = []
hiddenimports = []

# Cliente OAuth do Google Drive: fora do git, entra no bundle só se o CI (ou
# quem empacota) o tiver posto em confortimetro/drive/. Sem ele a seção do
# Drive aparece desabilitada (docs/DRIVE.md).
CLIENT_SECRET = os.path.join(ROOT, "confortimetro", "drive", "client_secret.json")
if os.path.isfile(CLIENT_SECRET):
    datas.append((CLIENT_SECRET, "confortimetro/drive"))

# Só o documento de descoberta do Drive v3: o googleapiclient traz o de todas
# as APIs do Google (dezenas de MB) e monta o serviço a partir dele, sem rede.
datas += collect_data_files("googleapiclient",
                            includes=["discovery_cache/documents/drive.v3.json"])
# Importados dentro das funções (confortimetro/drive/auth.py); o analisador
# estático não os vê.
hiddenimports += ["googleapiclient.discovery", "googleapiclient.http",
                  "google_auth_oauthlib.flow", "google_auth_httplib2", "httplib2",
                  "google.oauth2.credentials"]

# Pacotes com dados/tabelas próprios que o analisador estático não enxerga.
# esoreader é um módulo solto (não pacote); o PyInstaller o pega sozinho.
# tkinterweb carrega o Tkhtml (binário) do próprio pacote; keyring acha os
# backends por entry points, que vivem nos metadados.
for pkg in ("pythermalcomfort", "ladybug_comfort", "ladybug", "eppy",
            "tkinterweb", "tkinterweb_tkhtml", "keyring"):
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
    excludes=["pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="Ambiens",
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="Ambiens",
)
