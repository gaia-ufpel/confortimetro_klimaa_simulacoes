from modules.conditioner_all import ConditionerAll
from modules.conditioner_ac import ConditionerAc
from modules.conditioner_without_window import ConditionerWithoutWindow

from utils.module_type import ModuleType

MODULES_MAPPER = {
    ModuleType.COMPLETE: ConditionerAll,
    ModuleType.FIXED_AC_WITHOUT_VENT: ConditionerAc,
    ModuleType.CLOSED_WINDOW: ConditionerWithoutWindow
}
