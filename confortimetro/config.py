from dataclasses import dataclass
import json
import os
import platform

from confortimetro.module_type import ModuleType

# Banda do modelo adaptativo por nível de aceitação (ASHRAE 55).
PORCENT2ADAPTATIVE = {
    "90%": 2.5,
    "80%": 3.5
}

ADAPTATIVE2PORCENT = {value: key for key, value in PORCENT2ADAPTATIVE.items()}

def default_energy_path() -> str:
    """Instalação padrão do EnergyPlus 9.4 na plataforma atual."""
    if platform.system() == "Windows":
        return r"C:\EnergyPlusV9-4-0"
    if platform.system() == "Darwin":
        return "/Applications/EnergyPlus-9-4-0"
    return "/usr/local/EnergyPlus-9-4-0"


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

        # O config.json versionado traz caminhos de Linux; num Windows sem esse
        # diretório, cai no padrão da plataforma em vez de abrir a GUI quebrada.
        if not config.energy_path or not os.path.isdir(config.energy_path):
            config.energy_path = default_energy_path()

        return config
