"""
GUI components package.
"""

from .path_config_panel import (
    MACHINE_FIELDS,
    SIMULATION_FIELDS,
    PathConfigPanel,
)
from .simulation_config_panel import SimulationConfigPanel
from .idf_editor_panel import IDFEditorPanel
from .results_panel import ResultsPanel
from .control_panel import ControlPanel
from .simulations_panel import SimulationsPanel
from .comparison_panel import ComparisonPanel

__all__ = [
    'MACHINE_FIELDS',
    'SIMULATION_FIELDS',
    'PathConfigPanel',
    'SimulationConfigPanel', 
    'IDFEditorPanel',
    'ResultsPanel',
    'ControlPanel',
    'SimulationsPanel',
    'ComparisonPanel',
]
