from enum import Enum

class ModuleType(str, Enum):
    COMPLETE = "COMPLETE"
    CLOSED_WINDOW = "CLOSED_WINDOW"
    FIXED_AC_WITHOUT_FAN = "FIXED_AC_WITHOUT_FAN"
    WITHOUT_FAN = "WITHOUT_FAN"
    # Roda o EnergyPlus com o IDF como está: sem controlador, sem edição do IDF.
    ENERGYPLUS_ONLY = "ENERGYPLUS_ONLY"
    
    def __str__(self) -> str:
        return self.value