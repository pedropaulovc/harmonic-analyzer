r"""Pure-data contract for the keyed arbor's key (MHA-DT-03-TL-06).

Shop tooling (issue #2465). The 1/16 square key bonded in MHA-DT-03-TL-03's
keyseat that carries each keyed blank's clock while its teeth are cut: the
machine key's own undersized section (``cone_land_key``: the blanks' keyways
are sized for it), cut short. McMaster's only undersized 1/16 key stock,
98830A511, is already MHA-DT-VN-71's SKU (one SKU in two identities would
force a Shared identity, AGENTS.md), so this is a made tooling part cut from
such stock, e.g. that bar's offcut; only its length is made.

Part frame (MHA-DT-VN-71's): origin at the key's shoulder end, on its bottom
face, mid-width; length along +Z, height along +X, width centred on the Top
Plane. In the arbor's frame the key lies on the keyseat floor (+X) with its
end on the end radius's centre line.
"""

from __future__ import annotations

import _config
import cone_land_key
import dt_cone_gear_tl_keyed_arbor_spec as arbor
from _package_units import drawing_unit

PART_NAME = "dt-cone-gear-tl-arbor-key"
_ROW = _config.parts("dt-cone-gear-tl-arbor-key")
if PART_NAME != "dt-cone-gear-tl-arbor-key":
    raise AssertionError("PART_NAME and the registry row it reads disagree")
PART_NUMBER = str(_ROW["number"])
UNIT = drawing_unit("parts/dt-cone-gear-tl-arbor-key", _ROW)

SIZE = cone_land_key.KEY_SIZE_MM
SIZE_BAND = cone_land_key.KEY_STOCK_BAND
LENGTH = arbor.KEY_LENGTH
LENGTH_PLACES = arbor.KEY_LENGTH_PLACES
# The arbor's frame: the key's bottom face on the keyseat floor, its end on
# the end radius's centre line.
FLOOR_OFFSET_MM = arbor.KEYSEAT_FLOOR_OFFSET
END_Z_MM = arbor.KEY_END_Z

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "KeyProfile": {"KeyWidth", "KeyHeight"},
    "KeyBody": {"CutLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "KeyProfile": {"KeyWidth": 4, "KeyHeight": 4},
    "KeyBody": {"CutLength": LENGTH_PLACES},
}
# The section is the stock's, printed as its fraction reference; its
# tolerance is the stock's, not a title-block band.
STOCK_FRACTION_DENOMINATOR = 16
STOCK_FRACTION_DIMENSIONS = {"KeyWidth": SIZE, "KeyHeight": SIZE}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked arbor key dimension needs authored places")
if abs(arbor.inch_grid_mm(LENGTH, LENGTH_PLACES) - LENGTH) > 1e-9:
    raise AssertionError("the key's length is off its .XX grid")

# One note line names the stock (rule 7); the arbor's keyseat and the blanks'
# keyways print the key's fit.
DRAWING_NOTES = "CUT FROM 1/16 SQUARE UNDERSIZED KEY STOCK; SECTION AS SUPPLIED."
