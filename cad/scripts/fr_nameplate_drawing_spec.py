r"""Pure-data print contract for the nameplate's manufacturing drawing (#628).

PURE DATA, no SolidWorks/COM imports. ``build_fr_nameplate`` marks and gives
places to exactly ``DRAWING_DIMENSIONS``; ``draw_fr_nameplate`` keeps exactly
those model dimensions. Kept apart from ``fr_nameplate_spec`` on purpose: that
module feeds the base and the frame assembly, so a print-only edit here must
not rebuild them.

Fit (owner-ratified 2026-10-15, fr-harmonic-base RV-01): the base's four
#4-40 seats are spotted through the finished plate at assembly
(drawing-guidelines.md rule 19 (absorb stacks at fit-up)), so the plate's
holes need only keep their head on the raised border and a real edge
ligament. Each hole locates from its two adjacent plate edges at the title
block's three-place grade; the outline and the etch resist are one vendored
DXF, named on the sheet rather than redrawn as dimensions.
"""

from __future__ import annotations

import math

from _dxf_text import read_lwpolylines
from _hole_spec import CLEARANCE_MM
from _inch_wall_limits import WALL_TARGET_MM
from _paths import REFERENCES_DIR
from _printed_tolerance import drilled_oversize_mm, printed_deviations
from _release_artwork import bundle_path
import fr_harmonic_base_fasteners as base_fasteners
import fr_nameplate_spec as nameplate
from fr_nameplate_spec import PLATE_HEIGHT, PLATE_THICKNESS, PLATE_WIDTH, SCREW_XY, UNIT

# --- Model dimensions the print shows: feature -> parametric names. The slab's
# extrude depth is the plate thickness; the Hole Wizard placement sketch
# carries each station from the part origin, the plate's lower-left corner
# (S0X is the left column, S0Z the bottom row). The outline is an imported
# contour and the etched field's cut is mid-plane (its one depth is twice the
# depth below the face), so no feature dimension carries the plate's width or
# height, a far-edge hole station or a depth below the decorated face: each
# is the one driving dimension the build gives it in a hidden reference
# sketch (drawing-simplicity-policy.md, "The model owns tolerance and
# precision"). FaceReference lies on the decorated face (the Front plane);
# SectionReference on SECTION_PLANE, section A-A's cutting plane. ---
FACE_REFERENCE = "FaceReference"
SECTION_REFERENCE = "SectionReference"
REFERENCE_SKETCHES = (FACE_REFERENCE, SECTION_REFERENCE)
SECTION_PLANE = "SectionAPlane"
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateSlab": {"PlateThick"},
    "ScrewHoles": {"S0X", "S0Z"},
    FACE_REFERENCE: {"PlateWidth", "PlateHeight", "RightHoleStation", "TopHoleStation"},
    SECTION_REFERENCE: {"FieldDepth"},
}

# Places. The thickness prints .XXX, so the floor under the etched field is a
# measured number (stated on the sheet, MINIMUM_NOTES); the field depth
# prints its limits at three places (FIELD_DEPTH_LIMITS). The outline and the
# hole stations print .XX: the resist DXF defines the profile, and the base is
# spotted through the plate at assembly, so no fit or stack reads either
# closer; the hole ligament holds rule 17's .080 at the .XX band
# (HOLE_LIGAMENT_WORST).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateSlab": {"PlateThick": nameplate.PLATE_THICKNESS_PRECISION},
    "ScrewHoles": {"S0X": 2, "S0Z": 2},
    FACE_REFERENCE: {
        "PlateWidth": 2,
        "PlateHeight": 2,
        "RightHoleStation": 2,
        "TopHoleStation": 2,
    },
    SECTION_REFERENCE: {"FieldDepth": 3},
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

# Section A-A's one depth below the decorated face: the etched field. Owner
# ruling 2026-11-20 (Pedro), #2313: "A" -- etch the field ~.010 (.008-.012),
# letters and border proud and polished. One time-set depth printed as its
# limits replaces the former .016 sunk field and .028 engraving floor. The
# floor it leaves, the thinnest printed plate less the deepest etch, is under
# rule 17's .060 floor (fr-nameplate machinist exception RV-05), and the
# sheet states it as a minimum in MINIMUM_NOTES.
FIELD_DEPTH = 0.254  # .010
FIELD_DEPTH_LIMITS = (0.2032, 0.3048)  # .008-.012
FIELD_FLOOR_MIN = (
    PLATE_THICKNESS
    + printed_deviations(
        PLATE_THICKNESS, DRAWING_PRECISION["PlateSlab"]["PlateThick"], unit=UNIT
    )[0]
    - FIELD_DEPTH_LIMITS[1]
)
if not FIELD_DEPTH_LIMITS[0] < FIELD_DEPTH < FIELD_DEPTH_LIMITS[1]:
    raise AssertionError(f"the etch depth {FIELD_DEPTH} is outside its limits")
if FIELD_FLOOR_MIN <= 0.0:
    raise AssertionError(f"the etch can reach through the plate: {FIELD_FLOOR_MIN}")

# Section A-A cuts the whole plate at SECTION_Y (plate-local), in the gap
# between the CHICAGO row and the scroll ornament. Along the cut (plate x):
# the raised border's top (the decorated face) up to the field's edge at
# 3.60, then the etched field. The offline test proves each station against
# the DXFs.
SECTION_Y = 14.85
SECTION_FACE_X = 2.6
SECTION_FIELD_X = 5.5
# SectionReference's points (plate x, z), each on a cut-face line the section
# shows: the decorated face at its station and the field floor at its. The
# depth's dimension spans the face point to the floor point. Points, not
# construction chords: the section shows the sketch to keep its dimension,
# and a chord lying on a cut-face line printed grey dashes over the outline,
# read as hidden lines in a section (ENFORCE review, rule 9).
SECTION_REFERENCE_POINTS: dict[str, tuple[float, float]] = {
    "face": (SECTION_FACE_X, 0.0),
    "field": (SECTION_FIELD_X, -FIELD_DEPTH),
}

# The original cosmetic-joint full-thread shortfall is owned by the pure
# mechanical spec (fr-nameplate RV-03). The base's through-tap conversion does
# not change the stock screw or its projection through the plate.

# The vendored contours (cad/references). The build imports the outline (the
# slab), the field's edge (cut to the etch depth) and the letters and ornament
# with their counters (bossed back to the face, filled even-odd). The sheet names
# only the resist, by the path cut_release stages it at in the release
# bundle, spelled exactly as the file is (lower case: the path must open as
# printed): its outer loop is the outline, and its inner loops are the
# finished field's edges set back by the etch depth (the resist widened by
# FIELD_DEPTH per edge for the etch's undercut), so the border and the
# letters it covers stand at their finished size once etched.
OUTLINE_DXF_NAME = "fr-nameplate-outline.dxf"
FIELD_DXF_NAME = "fr-nameplate-field.dxf"
LETTERS_DXF_NAME = "fr-nameplate-letters.dxf"
RESIST_DXF_NAME = "fr-nameplate-resist.dxf"

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
    "right": DRAWING_PRECISION[FACE_REFERENCE]["RightHoleStation"],
    "bottom": DRAWING_PRECISION["ScrewHoles"]["S0Z"],
    "top": DRAWING_PRECISION[FACE_REFERENCE]["TopHoleStation"],
}

# Edge ligaments at the printed worst case (drawing-guidelines.md rule 17's
# .080 target), measured to the vendored outline itself: each hole is concentric
# with a rounded corner, so the corner arc, not a straight edge, is nearest
# when the shop drills both stations at their minima (PR #1468 r3 review).
# Each hole locates from its corner's two edges, so its accepted centres are
# the rectangle of the two printed station limits in that corner's DXF frame.
# The outline is convex (asserted), and distance to a convex boundary is
# concave inside it, so the least distance over a rectangle lies at one of its
# four vertices. The largest hole is the callout's .120 (exactly the model's)
# plus the DRILLED HOLES allowance.
LIGAMENT_FLOOR = WALL_TARGET_MM
_HOLE_R_MAX = (SCREW_HOLE_DIA + drilled_oversize_mm(unit=UNIT)) / 2.0
_OUTLINE_TEXT = (REFERENCES_DIR / OUTLINE_DXF_NAME).read_text(encoding="ascii")
_OUTLINE = read_lwpolylines(_OUTLINE_TEXT[_OUTLINE_TEXT.find("\nENTITIES\n") :])[0][0]
_TURNS = [
    (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
    for a, b, c in zip(
        _OUTLINE, _OUTLINE[1:] + _OUTLINE[:1], _OUTLINE[2:] + _OUTLINE[:2]
    )
]
if min(_TURNS) < 0.0 < max(_TURNS):
    raise AssertionError("the nameplate outline is no longer convex")


def _outline_distance(point: tuple[float, float]) -> float:
    """Least distance from ``point`` to the outline's polyline."""
    best = math.inf
    for (ax, ay), (bx, by) in zip(_OUTLINE, _OUTLINE[1:] + _OUTLINE[:1]):
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        t = 0.0
        if length2 > 0.0:
            t = min(
                1.0, max(0.0, ((point[0] - ax) * dx + (point[1] - ay) * dy) / length2)
            )
        best = min(best, math.hypot(point[0] - ax - t * dx, point[1] - ay - t * dy))
    return best


def _station_limits(edge: str) -> tuple[float, float]:
    station = HOLE_EDGE_STATIONS[edge]
    lower, upper = printed_deviations(station, _STATION_PLACES[edge], unit=UNIT)
    return station + lower, station + upper


def _accepted_centres(x: float, y: float) -> list[tuple[float, float]]:
    """The four extreme accepted centres of the hole nearest (x, y)'s corner."""
    if x < PLATE_WIDTH / 2.0:
        xs = _station_limits("left")
    else:
        xs = tuple(PLATE_WIDTH - limit for limit in _station_limits("right"))
    if y < PLATE_HEIGHT / 2.0:
        ys = _station_limits("bottom")
    else:
        ys = tuple(PLATE_HEIGHT - limit for limit in _station_limits("top"))
    return [(cx, cy) for cx in xs for cy in ys]


HOLE_LIGAMENT_WORST = min(
    _outline_distance(centre) - _HOLE_R_MAX
    for x, y in SCREW_XY
    for centre in _accepted_centres(x, y)
)
if HOLE_LIGAMENT_WORST < LIGAMENT_FLOOR:
    raise AssertionError(
        f"nameplate screw-hole ligament {HOLE_LIGAMENT_WORST:.3f} under {LIGAMENT_FLOOR}"
    )
# The largest station shift any accepted plate may show, for the head-on-border
# check the offline test runs against the vendored field contour.
HOLE_STATION_SHIFT_MAX = max(
    max(
        abs(value)
        for value in printed_deviations(station, _STATION_PLACES[edge], unit=UNIT)
    )
    for edge, station in HOLE_EDGE_STATIONS.items()
)

DIMENSION_PREFIXES = {
    "S0X": "2X ",
    "S0Z": "2X ",
    "RightHoleStation": "2X ",
    "TopHoleStation": "2X ",
}
# Section A-A's depth names its feature only: its limits are the owner's
# etch depth (fr-nameplate RV-07), and the floor they leave is a stated
# minimum (MINIMUM_NOTES).
FIELD_DEPTH_CALLOUT = "ETCHED FIELD DEPTH"
SECTION_CALLOUTS = {"FieldDepth": FIELD_DEPTH_CALLOUT}
HOLE_CALLOUT_PROCESS = "DRILL"


def _stated_minimum(value_mm: float) -> str:
    """A worst-case minimum in inches at three places, rounded DOWN: never overstated."""
    text = f"{math.floor(value_mm / 25.4 * 1000.0 + 1e-9) / 1000.0:.3f}"
    return text[1:] if text.startswith("0.") else text


# The two stated shortfalls, plain facts below the DXF rows: fr-nameplate
# machinist exceptions RV-05 (the floor under the etched field) and RV-03
# (the screws' full thread in the base), each formatted from its worst-case
# value. The screws' value is the installed overlap with the base's full
# female thread, past its entrance break, not the screw's bare projection
# (rule 18).
FLOOR_MINIMUM_NOTE = f"FLOOR UNDER ETCHED FIELD {_stated_minimum(FIELD_FLOOR_MIN)} MIN"
SCREW_ENGAGEMENT_NOTE = (
    "SCREWS ENGAGE "
    f"{_stated_minimum(base_fasteners.NAMEPLATE_INSTALLED_FULL_THREAD_MIN)}"
    " MIN FULL THREAD"
)
MINIMUM_NOTES = "\n".join((FLOOR_MINIMUM_NOTE, SCREW_ENGAGEMENT_NOTE))

# The DXF rows: fr-nameplate machinist exception RV-01 (the outline and the
# etch resist are the release bundle's DXF artwork, not dimensioned on the
# sheet).
MANUFACTURING_NOTES = "\n".join(
    (
        f"OUTLINE AND ETCH RESIST PER {bundle_path(RESIST_DXF_NAME)}",
        "DXF PATH IS RELATIVE TO THE RELEASE BUNDLE",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
