"""Sheet-only dimension set for the pinion arbor (MHA-DT-22).

Every plain Ø5/16 span's size is on the view (fan-out dt-fab-3 round 3: a size
given only in note prose was not on the view).  The bond zone's flank diameter
is the spec's.  The two spans outside the journals (the collar's, by the head,
with the pin hole; the back stub, past the back land) take the same limits and
the same mate, so one 2X diameter on the back stub sizes both (round 5: the
collar span has no open sheet space for its own block, which SolidWorks
flipped onto the front land's witnesses either side).  Only
build_dt_pinion_arbor and draw_dt_pinion_arbor import this module, so
dt_pinion_arbor_spec (which the collar, pin, rig fit-up and other sheets
read) stays as it is.  The sheet's maps are the spec's plus this entry.
"""

from __future__ import annotations

import dt_pinion_arbor_spec as spec

# Each diameter is measured at a short construction witness run along its
# flank, from its station toward the back crown (mm from the head rear face):
# the back stub's between the back land and the crown.
BOND_ZONE_WITNESS_LEN = 4.0
SPAN_WITNESS_LEN = 4.0
BACK_STUB_DIA_FROM_HEAD_REAR = 221.0
BACK_STUB_DIA_Z = spec.HEAD_REAR_Z + BACK_STUB_DIA_FROM_HEAD_REAR
# One size for both spans outside the journals.
BACK_STUB_DIA_PREFIX = "2X <MOD-DIAM>"
# One size for both MHA-DT-01 bond lands either side of the relief (#2360).
BOND_ZONE_DIA_PREFIX = "2X <MOD-DIAM>"
_NEW_SPANS = (
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
