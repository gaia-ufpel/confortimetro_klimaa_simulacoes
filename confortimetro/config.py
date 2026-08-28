from dataclasses import dataclass
import glob
import json
import os
import platform
import re
import shutil

from confortimetro.module_type import ModuleType

# Banda do modelo adaptativo por nível de aceitação (ASHRAE 55).
PORCENT2ADAPTATIVE = {
    "90%": 2.5,
    "80%": 3.5
}

ADAPTATIVE2PORCENT = {value: key for key, value in PORCENT2ADAPTATIVE.items()}

# Versão da API do pyenergyplus que o projeto usa.
REQUIRED_EP_VERSION = "9.4"


def _platform_globs() -> list[str]:
    """Padrões de instalação do EnergyPlus na plataforma atual."""
    system = platform.system()
    if system == "Windows":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        return [r"C:\EnergyPlusV*", os.path.join(program_files, "EnergyPlusV*")]
    if system == "Darwin":
        return ["/Applications/EnergyPlus-*"]
    return ["/usr/local/EnergyPlus-*", "/opt/EnergyPlus-*"]


def default_energy_path() -> str:
    """Instalação padrão do EnergyPlus 9.4 na plataforma atual."""
    if platform.system() == "Windows":
        return r"C:\EnergyPlusV9-4-0"
    if platform.system() == "Darwin":
        return "/Applications/EnergyPlus-9-4-0"
    return "/usr/local/EnergyPlus-9-4-0"


def is_energy_path(path: str) -> bool:
    """
    Verdadeiro se `path` é a raiz de uma instalação utilizável do EnergyPlus.

    Exige os dois arquivos que a simulação usa: o IDD e a API Python. Isso
    rejeita uma subpasta da instalação, que existe mas quebra depois com
    `IDD file not found`.
    """
    if not path or not os.path.isdir(path):
        return False
    return os.path.isfile(os.path.join(path, "Energy+.idd")) and os.path.isfile(
        os.path.join(path, "pyenergyplus", "api.py")
    )


def energy_path_version(path: str) -> str:
    """
    Versão da instalação, extraída do nome do diretório
    (`EnergyPlusV9-4-0`, `EnergyPlus-9-4-0`, `EnergyPlus-23-2-0`).

    Retorna "" quando o nome não segue nenhum dos padrões.
    """
    match = re.search(r"(\d+)[-.](\d+)", os.path.basename(os.path.normpath(path)))
    return f"{match.group(1)}.{match.group(2)}" if match else ""


def _windows_registry_paths() -> list[str]:
    """Instalações do EnergyPlus registradas no desinstalador do Windows."""
    if platform.system() != "Windows":
        return []

    import winreg

    found = []
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            uninstall = winreg.OpenKey(root, key_path)
        except OSError:
            continue
        with uninstall:
            for index in range(winreg.QueryInfoKey(uninstall)[0]):
                try:
                    with winreg.OpenKey(uninstall, winreg.EnumKey(uninstall, index)) as sub:
                        name = winreg.QueryValueEx(sub, "DisplayName")[0]
                        if not str(name).startswith("EnergyPlus"):
                            continue
                        found.append(winreg.QueryValueEx(sub, "InstallLocation")[0])
                except OSError:
                    continue
    return found


def find_energy_path() -> str:
    """
    Localiza a instalação do EnergyPlus, preferindo sempre a
    `REQUIRED_EP_VERSION`.

    Ordem das fontes: variável `ENERGYPLUS_DIR`, `energyplus` no PATH,
    diretórios padrão da plataforma e, no Windows, o registro. Retorna "" se
    nenhuma instalação válida for encontrada.
    """
    candidates = []

    env_path = os.environ.get("ENERGYPLUS_DIR")
    if env_path:
        candidates.append(env_path)

    executable = shutil.which("energyplus")
    if executable:
        candidates.append(os.path.dirname(os.path.realpath(executable)))

    for pattern in _platform_globs():
        candidates.extend(sorted(glob.glob(pattern), reverse=True))

    candidates.extend(_windows_registry_paths())

    valid = [path for path in candidates if is_energy_path(path)]
    for path in valid:
        if energy_path_version(path) == REQUIRED_EP_VERSION:
            return path
    return valid[0] if valid else ""


@dataclass
class SimulationConfig:
    met_as_watts: float
    _idf_path: str
    _met: float

    epw_path: str = None
    output_path: str = None
    energy_path: str = None
    rooms: list[str] = None
    pmv_upperbound: float = 0.5
    pmv_lowerbound: float = -0.5
    co2_limit: float = 1000
    max_vel: float = 1.2
    adaptative_bound: float = 2.5
    temp_ac_min: float = 16.0
    temp_ac_max: float = 30.0
    wme: float = 0.0
    clo_max: float = 1.0
    clo_min: float = 0.5
    clo_delta: float = 0.1

    input_path: str = None
    expanded_idf_path: str = None
    idf_filename: str = None
    temp_open_window_bound: float = 5.0
    air_speed_delta: float = 0.15
    pmv_comfort_bound: float = 0.2
    module_type: ModuleType = ModuleType.COMPLETE

    def __post_init__(self):
        self.input_path = os.path.dirname(self.idf_path)
        self.expanded_idf_path = os.path.join(self.input_path, "expanded.idf")
        self.idf_filename = os.path.basename(self.idf_path)
        self.met_as_watts = self.met * 58.1 * 1.8

    @property
    def idf_path(self):
        return self._idf_path

    @idf_path.setter
    def idf_path(self, idf_path: str):
        self._idf_path = idf_path
        self.input_path = os.path.dirname(self.idf_path)
        self.expanded_idf_path = os.path.join(self.input_path, "expanded.idf")
        self.idf_filename = os.path.basename(self.idf_path)

    @property
    def met(self):
        return self._met
    
    @met.setter
    def met(self, met: float):
        self._met = met
        self.met_as_watts = met * 58.1 * 1.8

    def to_json(self, json_path: str=None):
        if json_path is None:
            json_path = os.path.join(self.output_path, "config.json")

        with open(json_path, "w") as writer:
            json.dump(self.__dict__, writer, indent=4)
    
    @staticmethod
    def from_json(json_path: str):
        with open(json_path, "r") as reader:
            data = json.load(reader)
        
        config = SimulationConfig(**data)

        # O config.json versionado traz caminhos de Linux; numa máquina sem esse
        # diretório, redetecta em vez de abrir a GUI com um caminho quebrado.
        if not is_energy_path(config.energy_path):
            config.energy_path = find_energy_path() or default_energy_path()

        return config
