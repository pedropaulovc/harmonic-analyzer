r"""Pure-data print contract for the nameplate's manufacturing drawing (#628).

PURE DATA, no SolidWorks/COM imports. ``build_fr_nameplate`` marks and gives
places to exactly ``DRAWING_DIMENSIONS``; ``draw_fr_nameplate`` keeps exactly
those model dimensions and adds the sheet-derived ones whose places live in
``DRAWING_REFERENCE_PRECISION``. Kept apart from ``fr_nameplate_spec`` on
purpose: that module feeds the base and the frame assembly, so a print-only
edit here must not rebuild them.

Fit (Main ruling, 2026-10-14): the base's four #4-40 seats are spotted through
the finished plate at assembly (drawing-guidelines.md rule 19 (absorb stacks
at fit-up)), so the plate's holes need only keep their head on the raised
border and a real edge ligament. Each hole locates from its two adjacent plate
edges at the title block's one-place grade; the corner profile, the sunk field
and the engraving are the vendored DXF contours the build imports, named on
the sheet rather than redrawn as dimensions.
"""

from __future__ import annotations

from _hole_spec import CLEARANCE_MM
from _printed_tolerance import drilled_oversize_mm, printed_deviations
from fr_nameplate_spec import PLATE_HEIGHT, PLATE_THICKNESS, PLATE_WIDTH, SCREW_XY

# --- Model dimensions the print shows: feature -> parametric names. The slab's
# extrude depth is the plate thickness; the Hole Wizard placement sketch
# carries each station from the part origin, the plate's lower-left corner
# (S0X is the left column, S0Z the bottom row). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateSlab": {"PlateThick"},
    "ScrewHoles": {"S0X", "S0Z"},
}

# Places. The engraving is incised 0.300 below the 0.400 sunk field, so the
# thinnest floor left under it is the thickness less 0.700: the thickness
# prints .XXX so that floor is a measured number, not a .X guess (Main ruling
# 2026-10-14; the shortfall under rule 17's 1.5 floor is reported, not hidden).
# The hole stations print .X: the base is spotted through the plate.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateSlab": {"PlateThick": 3},
    "ScrewHoles": {"S0X": 1, "S0Z": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if DRAWING_PRECISION.keys() != DRAWING_DIMENSIONS.keys() or any(
    set(DRAWING_PRECISION[feature]) != names
    for feature, names in DRAWING_DIMENSIONS.items()
):
    raise AssertionError("every marked nameplate dimension needs authored places")

# Sheet-derived dimensions (no model parameter of their own: the outline is an
# imported contour, and the far-edge hole stations are its edges' distances
# to the right and top hole centres). Keyed by the sheet's label.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    "plate width": 1,
    "plate height": 1,
    "right hole station": 1,
    "top hole station": 1,
    "sunk field depth": 3,
    "engraving depth": 3,
}

# Section A-A's depths from the decorated face: the sunk field, then every
# engraved groove (border pinstripe and field lettering alike) to one floor.
FIELD_DEPTH = 0.4
ENGRAVING_FLOOR_DEPTH = 0.7
ENGRAVING_FLOOR_MIN = (
    PLATE_THICKNESS
    + printed_deviations(PLATE_THICKNESS, DRAWING_PRECISION["PlateSlab"]["PlateThick"])[
        0
    ]
    - (
        ENGRAVING_FLOOR_DEPTH
        + printed_deviations(
            ENGRAVING_FLOOR_DEPTH, DRAWING_REFERENCE_PRECISION["engraving depth"]
        )[1]
    )
)
if ENGRAVING_FLOOR_MIN <= 0.0:
    raise AssertionError(
        f"engraving can reach through the plate: {ENGRAVING_FLOOR_MIN}"
    )

# Each hole's station from its adjacent edges, as the sheet prints it.
SCREW_HOLE_DIA = CLEARANCE_MM[("#4", "close")]
HOLE_EDGE_STATIONS: dict[str, float] = {
    "left": min(x for x, _ in SCREW_XY),
    "right": PLATE_WIDTH - max(x for x, _ in SCREW_XY),
    "bottom": min(y for _, y in SCREW_XY),
    "top": PLATE_HEIGHT - max(y for _, y in SCREW_XY),
}
_STATION_PLACES = {
    "left": DRAWING_PRECISION["ScrewHoles"]["S0X"],
    "right": DRAWING_REFERENCE_PRECISION["right hole station"],
    "bottom": DRAWING_PRECISION["ScrewHoles"]["S0Z"],
    "top": DRAWING_REFERENCE_PRECISION["top hole station"],
}

# Edge ligaments at the printed worst case: the largest drilled hole at the
# station's least accepted value (drawing-guidelines.md rule 17's 1.5 floor).
LIGAMENT_FLOOR = 1.5
_HOLE_R_MAX = (SCREW_HOLE_DIA + drilled_oversize_mm()) / 2.0
HOLE_LIGAMENTS_WORST: dict[str, float] = {
    edge: station + printed_deviations(station, _STATION_PLACES[edge])[0] - _HOLE_R_MAX
    for edge, station in HOLE_EDGE_STATIONS.items()
}
if min(HOLE_LIGAMENTS_WORST.values()) < LIGAMENT_FLOOR:
    raise AssertionError(
        f"nameplate screw-hole ligaments {HOLE_LIGAMENTS_WORST} under {LIGAMENT_FLOOR}"
    )
# The largest station shift any accepted plate may show, for the head-on-border
# check the offline test runs against the vendored field contour.
HOLE_STATION_SHIFT_MAX = max(
    max(abs(value) for value in printed_deviations(station, _STATION_PLACES[edge]))
    for edge, station in HOLE_EDGE_STATIONS.items()
)

DIMENSION_PREFIXES = {"S0X": "2X ", "S0Z": "2X "}
DIMENSION_CALLOUTS = {"PlateThick": "SETS ENGRAVING FLOOR"}
STATION_PREFIX = "2X "
FIELD_DEPTH_CALLOUT = "SUNK FIELD"
ENGRAVING_DEPTH_CALLOUT = "ALL ENGRAVING"
HOLE_CALLOUT_PROCESS = "DRILL"

# The three vendored contours the build imports (cad/references), named on the
# sheet. No digits, no method: the shop cuts them however it engraves.
OUTLINE_DXF_NAME = "FR-NAMEPLATE-OUTLINE.DXF"
FIELD_DXF_NAME = "FR-NAMEPLATE-FIELD.DXF"
ENGRAVING_DXF_NAME = "FR-NAMEPLATE-ENGRAVING.DXF"
MANUFACTURING_NOTES = "\n".join(
    (
        f"OUTLINE AND CORNERS PER {OUTLINE_DXF_NAME}",
        f"SUNK FIELD PER {FIELD_DXF_NAME}",
        f"ENGRAVING PER {ENGRAVING_DXF_NAME}",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
