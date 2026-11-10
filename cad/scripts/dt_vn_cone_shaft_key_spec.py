r"""MHA-DT-VN-71 cone shaft key: McMaster 98830A511 key stock cut to length.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Owner decision C1 keyed, 2026-11-09 (PR #1992): one 1/16 square
key in the keyseat along MHA-DT-04's land 1 drives the 64T (MHA-DT-07) and
T030..T120 (MHA-DT-03) through their broached keyways (``cone_land_key``
owns every key, keyseat and keyway number).  The key is bought as 12 in
undersized key stock and cut to ``cone_land_key.KEY_LENGTH_MM``; cutting to
length keeps it a vendor part (cad/docs/subsystem-identities.md).

Part frame: origin at the key's south (collar) end, on its bottom face, in
the middle of its width; length along local +Z, height along local +X (the
bottom face lies on the Right Plane), width centred on the Top Plane.  In
the drive train the key's frame is the shaft's, set off along +X by the
keyseat floor and along +Z by the collar face plus ``KEY_END_SET_MM``.
"""

from __future__ import annotations

import _config
import _mcmaster_98830a511 as _catalogue
import cone_land_key
from _package_units import drawing_unit

UNIT = drawing_unit("parts/dt-vn-cone-shaft-key", _config.parts("dt-vn-cone-shaft-key"))
SKU = _catalogue.PART_NO

# The section is the stock's as supplied: cone_land_key's key is the
# catalogue's undersized 1/16 square.
SIZE = cone_land_key.KEY_SIZE_MM
SIZE_BAND = cone_land_key.KEY_STOCK_BAND
if (SIZE, SIZE_BAND) != (_catalogue.SIZE, _catalogue.SIZE_BAND):
    raise AssertionError(f"cone_land_key's key is not {SKU}'s section")
# The only made size: the cut length, at the title block's .XX.
LENGTH = cone_land_key.KEY_LENGTH_MM
LENGTH_PLACES = cone_land_key.KEY_LENGTH_PLACES
STOCK_LENGTH = _catalogue.LENGTH
if not LENGTH < STOCK_LENGTH + _catalogue.LENGTH_BAND[1]:
    raise AssertionError(f"one {SKU} bar does not yield the key")

# Seat in the shaft frame (cone_land_key's clock: centred on +X).
FLOOR_OFFSET_MM = cone_land_key.KEYSEAT_FLOOR_OFFSET_MM
END_SET_MM = cone_land_key.KEY_END_SET_MM

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "KeyProfile": {"KeyWidth", "KeyHeight"},
    "KeyCutProfile": {"CutLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "KeyProfile": {"KeyWidth": 4, "KeyHeight": 4},
    "KeyCutProfile": {"CutLength": LENGTH_PLACES},
}
# The section is the bought stock's, printed as the supplier's fraction
# reference: its tolerance is the catalogue's, not a title-block band.
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
    raise AssertionError("every marked MHA-DT-VN-71 dimension needs authored places")

# One note line names the stock (rule 7); the section's fractions are the
# supplier's reference sizes, so they carry no fit reason of their own: the
# keyseat and keyways print the key's fit on MHA-DT-04, MHA-DT-03 and
# MHA-DT-07, and MHA-DT-00 seats it.  The cut ends take the title block's
# edge break.
DRAWING_NOTES = f"CUT FROM McMASTER-CARR {SKU} KEY STOCK; SECTION AS SUPPLIED."
