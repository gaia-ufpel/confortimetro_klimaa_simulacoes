from enum import Enum

class ModuleType(str, Enum):
    COMPLETE = "COMPLETE"
    CLOSED_WINDOW = "CLOSED_WINDOW"
    FIXED_AC_WITHOUT_VENT = "FIXED_AC_WITHOUT_VENT"
    
    def __str__(self) -> str:
        return self.value