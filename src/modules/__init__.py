from src.modules.conditioner_complete import ConditionerComplete
from src.modules.conditioner_fixed_ac_without_fan import ConditionerFixedAcWithoutFan
from src.modules.conditioner_closed_window import ConditionerClosedWindow
from src.modules.conditioner_without_fan import ConditionerWithoutFan

from src.utils.module_type import ModuleType

MODULES_MAPPER = {
    ModuleType.COMPLETE: ConditionerComplete,
    ModuleType.FIXED_AC_WITHOUT_FAN: ConditionerFixedAcWithoutFan,
    ModuleType.CLOSED_WINDOW: ConditionerClosedWindow,
    ModuleType.WITHOUT_FAN: ConditionerWithoutFan
}
