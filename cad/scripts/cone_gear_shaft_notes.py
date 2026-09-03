"""Drawing-only text derived from the cone gear shaft's manufacturing spec."""

from __future__ import annotations

from _fit_limits import fit_limits
from cone_gear_shaft_spec import SECTION_DIA_BAND, SECTION_DIAS


TIP_LANDS_NOTE = "\n".join(
    (
        "DETAIL A TIP LANDS",
        *(
            fit_limits(diameter, SECTION_DIA_BAND, diameter=True)
            for diameter in SECTION_DIAS[2:]
        ),
    )
)
