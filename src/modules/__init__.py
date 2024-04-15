from modules.conditioner_complete import ConditionerComplete
from modules.conditioner_fixed_ac import ConditionerFixedAc
from modules.conditioner_without_window import ConditionerWithoutWindow
from modules.conditioner_without_vent import ConditionerWithoutVent

from utils.module_type import ModuleType

MODULES_MAPPER = {
    ModuleType.COMPLETE: ConditionerComplete,
    ModuleType.FIXED_AC_WITHOUT_VENT: ConditionerFixedAc,
    ModuleType.CLOSED_WINDOW: ConditionerWithoutWindow,
    ModuleType.WITHOUT_VENT: ConditionerWithoutVent
}
