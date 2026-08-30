"""
GUI components package.
"""

from .path_config_panel import (
    MACHINE_FIELDS,
    SIMULATION_FIELDS,
    PathConfigPanel,
)
from .simulation_config_panel import SimulationConfigPanel
from .results_panel import ResultsPanel
from .control_panel import ControlPanel
from .simulations_panel import SimulationsPanel, open_simulations_window

__all__ = [
    'MACHINE_FIELDS',
    'SIMULATION_FIELDS',
    'PathConfigPanel',
    'SimulationConfigPanel', 
    'ResultsPanel',
    'ControlPanel',
    'SimulationsPanel',
    'open_simulations_window'
]
