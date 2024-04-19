from enum import Enum

class ModuleType(str, Enum):
    COMPLETE = "COMPLETE"
    CLOSED_WINDOW = "CLOSED_WINDOW"
    FIXED_AC_WITHOUT_FAN = "FIXED_AC_WITHOUT_FAN"
    WITHOUT_FAN = "WITHOUT_FAN"
    
    def __str__(self) -> str:
        return self.value