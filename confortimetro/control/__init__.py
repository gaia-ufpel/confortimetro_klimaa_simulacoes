from confortimetro.control.complete import ConditionerComplete
from confortimetro.control.fixed_ac_without_fan import ConditionerFixedAcWithoutFan
from confortimetro.control.closed_window import ConditionerClosedWindow
from confortimetro.control.without_fan import ConditionerWithoutFan

from confortimetro.module_type import ModuleType

MODULES_MAPPER = {
    ModuleType.COMPLETE: ConditionerComplete,
    ModuleType.FIXED_AC_WITHOUT_FAN: ConditionerFixedAcWithoutFan,
    ModuleType.CLOSED_WINDOW: ConditionerClosedWindow,
    ModuleType.WITHOUT_FAN: ConditionerWithoutFan
}
