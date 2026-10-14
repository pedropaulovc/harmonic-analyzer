"""Catalogue-only McMaster 92314A253 plain external-hex stock recipe.

No supplier CAD was harvested. The 93075A194 hex/shank/thread construction
is reused as a nominal representation, not a supplier dimensional guarantee.
The optional bearing height positions COMPLETE 50.8-mm stock before the
production trim; it never shortens stock or removes its factory thread phase.
No socket, Allen recess, integral washer or added bearing stub is modeled.
"""

from dataclasses import dataclass

from _mcmaster_92314a253 import DIMS
from _stock_recipe import stock_recipe
from diagnostics.diag_mcmaster_hex_head import HexHeadScrew, build_hex_head_screw


@dataclass(frozen=True, slots=True)
class _PositionedHexScrew(HexHeadScrew):
    bearing_y_mm: float = 0.0

    @property
    def underside_y(self) -> float:
        return self.bearing_y_mm


@stock_recipe("92314A253", threaded=True)
async def build_92314A253(adapter, truth=None, *, bearing_y_mm: float = 0.0):
    dims = _PositionedHexScrew(
        part_no=DIMS.part_no,
        major_dia=DIMS.major_dia,
        pitch=DIMS.pitch,
        length=DIMS.length,
        head_af=DIMS.head_af,
        head_h=DIMS.head_h,
        bearing_y_mm=bearing_y_mm,
    )
    await build_hex_head_screw(adapter, dims)
