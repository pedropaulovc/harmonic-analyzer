"""Pure dowel dimension contract; separate shared laws from SKU cache inputs."""

import math
from dataclasses import dataclass

MM_PER_IN = 25.4

# Catalogue diameter tolerance over nominal, in inches (every size above).
DIA_BAND_IN = (0.0001, 0.0003)


@dataclass(frozen=True)
class DowelEnds:
    """A vendor-modelled Round x Chamfer pair of end forms, mm and degrees."""

    point_dia: float  # the chamfered end's flat face
    chamfer_deg: float  # the chamfer cone's angle to the pin axis
    crown_r: float  # the round end's radius, tangent to the diameter

    def chamfer_len(self, dia: float) -> float:
        """Axial length of the chamfer cone on a pin of ``dia``."""
        return (dia - self.point_dia) / 2.0 / math.tan(math.radians(self.chamfer_deg))
