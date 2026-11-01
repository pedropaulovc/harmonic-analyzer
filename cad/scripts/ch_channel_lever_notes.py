r"""Channel-lever drawing data -- the marked-dimension contract, the decimal
places the part authors on each printed dimension, and the isometric label.

Kept OUT of ``ch_channel_lever_spec``: assemblies and the error budget import
the spec for geometry, so drawing-only data living there would re-key
``assembly:ch_channel`` on every print edit.  Imported only by
``build_ch_channel_lever`` (which marks, places and stamps them), the drawing
and its offline test.
"""

from __future__ import annotations

# Every size, location and band prints from its native model dimension, and
# each tight band names its mate or function on its own callout
# (drawing-guidelines.md rules 4 and 7), so the sheet needs no note.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    # Full-height bar; its tip is a full round about the spring hole.
    "LeverOutline": {"BarHeight"},
    "LeverBody": {"LeverThick"},
    "HubProfile": {"HubDia"},
    "Hub": {"HubLength"},
    # The plate's near face from the hub face the levers stack on: a hidden
    # reference line (no metal) from the hub face to the plate face.
    "PlateOffsetReference": {"PlateOffset"},
    "FulcrumProfile": {"FulcrumDia"},
    # Both arms from the fulcrum bore (the part origin): the Hole Wizard
    # placement dimensions themselves.
    "BarPinHole": {"BarPinCx"},
    "SpringHole": {"SpringCx"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md),
# in inches: two on the milled bar height and the turned hub (the walls read
# them), three on the plate, the plate offset, the hub length (the station
# pitch's .278) and both lever arms, four on the reamed fulcrum bore.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LeverOutline": {"BarHeight": 2},
    "LeverBody": {"LeverThick": 3},
    "HubProfile": {"HubDia": 2},
    "Hub": {"HubLength": 3},
    "PlateOffsetReference": {"PlateOffset": 3},
    "FulcrumProfile": {"FulcrumDia": 4},
    "BarPinHole": {"BarPinCx": 3},
    "SpringHole": {"SpringCx": 3},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked dimension must state its decimal places")

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
