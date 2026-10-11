"""GD&T symbols and tolerance zones, separate from face selectors
so vocabulary edits do not pull selector implementations into recipe closures.
"""

from __future__ import annotations

from typing import Literal

# SOLIDWORKS 2022+ frame-XML symbol names per geometric characteristic.
GTOL_SYMBOLS = {
    "angularity": "GTOL-ANGULAR",
    "circular_runout": "GTOL-SRUN",
    "cylindricity": "GTOL-CYL",
    "flatness": "GTOL-FLAT",
    "parallelism": "GTOL-PARA",
    "position": "GTOL-POSI",
    "profile_surface": "GTOL-SPROF",
    "perpendicularity": "GTOL-PERP",
    "straightness": "GTOL-STRAIGHT",
    "total_runout": "GTOL-TRUN",
}

ToleranceZone = Literal["linear", "diametral"]
