"""Sheet-only dimension set for the pinion arbor (MHA-DT-22).

Every plain Ø5/16 span's size is on the view (fan-out dt-fab-3 round 3: a size
given only in note prose was not on the view).  The front bond land's flank
diameter is the spec's; the back bond land carries its own (#1038 r8 machinist
review: a 2X callout that reaches one land left the other to elimination).
The two spans outside the journals (the collar's, by the head, with the pin
hole; the back stub, past the back land) take the same limits and the same
mate, so one 2X diameter on the back stub sizes both and note 2 names them
(round 5: the collar span has no open sheet space for its own block, which
SolidWorks flipped onto the front land's witnesses either side).  Only
build_dt_pinion_arbor and draw_dt_pinion_arbor import this module, so
dt_pinion_arbor_spec (which the collar, pin, rig fit-up and other sheets
read) stays as it is.  The sheet's maps are the spec's plus these entries.
"""

from __future__ import annotations

import dt_pinion_arbor_spec as spec

# Each diameter is measured at a short construction witness run along its
# flank, from its station toward the back crown (mm from the head rear face):
# the back stub's between the back land and the crown.
BOND_ZONE_WITNESS_LEN = 4.0
SPAN_WITNESS_LEN = 4.0
# #1038 re-pitch: 221.0 -> 231.7 with the back land's .42 in move, so the
# witness still starts ~2.1 past the land and ends ~1.8 short of the rim.
BACK_STUB_DIA_FROM_HEAD_REAR = 231.7
BACK_STUB_DIA_Z = spec.HEAD_REAR_Z + BACK_STUB_DIA_FROM_HEAD_REAR
# One size for both spans outside the journals; note 2 names the two.
BACK_STUB_DIA_PREFIX = "2X <MOD-DIAM>"
# The back bond land's witness starts 2.28 past the relief's back shoulder,
# where its block, hung left of its line under the shaft, sits between the
# 6.80 and 8.25 station witnesses (draw_dt_pinion_arbor).
BACK_BOND_DIA_FROM_HEAD_REAR = 175.0
BACK_BOND_DIA_Z = spec.HEAD_REAR_Z + BACK_BOND_DIA_FROM_HEAD_REAR
if not (
    spec.BOND_RELIEF_BACK_FROM_HEAD_REAR
    < BACK_BOND_DIA_FROM_HEAD_REAR
    < BACK_BOND_DIA_FROM_HEAD_REAR + BOND_ZONE_WITNESS_LEN
    < spec.BACK_JOURNAL_FROM_HEAD_REAR
):
    raise AssertionError("the back bond land's witness must lie on that land")
# One size for both journal lands, on the back land (#1038 ruling: under the
# shaft the front land's block had no open space between its 2.61 and 1.82
# station witnesses).  Note 1 names them.
JOURNAL_DIA_PREFIX = "2X <MOD-DIAM>"
_NEW_SPANS = (
    (
        "BackBondReference",
        "BackBondDia",
        BACK_BOND_DIA_FROM_HEAD_REAR,
        BOND_ZONE_WITNESS_LEN,
    ),
    ("BackStubReference", "BackStubDia", BACK_STUB_DIA_FROM_HEAD_REAR, SPAN_WITNESS_LEN),
)
SPAN_REFERENCES = (
    (
        "BondZoneReference",
        "BondZoneDia",
        spec.BOND_ZONE_DIA_FROM_HEAD_REAR,
        BOND_ZONE_WITNESS_LEN,
    ),
    *_NEW_SPANS,
)
# Four places, as the bond zone: the -.0004/-.0038 band prints exactly.
_SPAN_PLACES = spec.DRAWING_PRECISION["BondZoneReference"]["BondZoneDia"]

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    **spec.DRAWING_DIMENSIONS,
    **{feature: {name} for feature, name, _station, _length in _NEW_SPANS},
}
REFERENCE_SKETCHES = (
    *spec.REFERENCE_SKETCHES,
    *(feature for feature, _name, _station, _length in _NEW_SPANS),
)
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    **spec.DRAWING_PRECISION,
    **{feature: {name: _SPAN_PLACES} for feature, name, _station, _length in _NEW_SPANS},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if any(feature in spec.DRAWING_DIMENSIONS for feature, *_ in _NEW_SPANS):
    raise AssertionError("dt_pinion_arbor_spec now owns a span reference this module adds")
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked integral-arbor dimension needs authored places")
