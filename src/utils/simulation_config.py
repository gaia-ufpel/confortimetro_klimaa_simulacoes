from dataclasses import dataclass
import json
import os

from utils.module_type import ModuleType

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
        
        return SimulationConfig(**data)
