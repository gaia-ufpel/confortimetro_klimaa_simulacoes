from modules.conditioner_complete import ConditionerComplete
from modules.conditioner_fixed_ac_without_fan import ConditionerFixedAcWithoutFan
from modules.conditioner_closed_window import ConditionerClosedWindow
from modules.conditioner_without_fan import ConditionerWithoutFan

from utils.module_type import ModuleType

MODULES_MAPPER = {
    ModuleType.COMPLETE: ConditionerComplete,
    ModuleType.FIXED_AC_WITHOUT_FAN: ConditionerFixedAcWithoutFan,
    ModuleType.CLOSED_WINDOW: ConditionerClosedWindow,
    ModuleType.WITHOUT_FAN: ConditionerWithoutFan
}
