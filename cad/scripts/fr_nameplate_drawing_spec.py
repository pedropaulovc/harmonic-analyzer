r"""Pure-data print contract for the nameplate's manufacturing drawing (#628).

PURE DATA, no SolidWorks/COM imports. ``build_fr_nameplate`` marks and gives
places to exactly ``DRAWING_DIMENSIONS``; ``draw_fr_nameplate`` keeps exactly
those model dimensions and adds one sheet-derived reference, the floor under
the engraving, whose places live in ``DRAWING_REFERENCE_PRECISION``. Kept
apart from ``fr_nameplate_spec`` on purpose: that module feeds the base and
the frame assembly, so a print-only edit here must not rebuild them.

Fit (owner-ratified 2026-10-15, fr-harmonic-base RV-01): the base's four
#4-40 seats are spotted through the finished plate at assembly
(drawing-guidelines.md rule 19 (absorb stacks at fit-up)), so the plate's
holes need only keep their head on the raised border and a real edge
ligament. Each hole locates from its two adjacent plate edges at the title
block's three-place grade; the corner profile, the sunk field and the engraving
are the vendored DXF contours the build imports, named on the sheet rather
than redrawn as dimensions.
"""

from __future__ import annotations

import math

from _dxf_text import read_lwpolylines
from _hole_spec import CLEARANCE_MM
from _inch_wall_limits import WALL_TARGET_MM
from _paths import REFERENCES_DIR
from _printed_tolerance import drilled_oversize_mm, printed_deviations
from _release_artwork import bundle_path
import fr_nameplate_spec as nameplate
from fr_nameplate_spec import PLATE_HEIGHT, PLATE_THICKNESS, PLATE_WIDTH, SCREW_XY, UNIT

# --- Model dimensions the print shows: feature -> parametric names. The slab's
# extrude depth is the plate thickness; the Hole Wizard placement sketch
# carries each station from the part origin, the plate's lower-left corner
# (S0X is the left column, S0Z the bottom row). The outline is an imported
# contour and the field and engraving cuts are mid-plane (their one depth is
# twice the depth below the face), so no feature dimension carries the plate's
# width or height, a far-edge hole station or a depth below the decorated
# face: each is the one driving dimension the build gives it in a hidden
# reference sketch (drawing-simplicity-policy.md, "The model owns tolerance
# and precision"). FaceReference lies on the decorated face (the Front plane);
# SectionReference on SECTION_PLANE, section A-A's cutting plane. ---
FACE_REFERENCE = "FaceReference"
SECTION_REFERENCE = "SectionReference"
REFERENCE_SKETCHES = (FACE_REFERENCE, SECTION_REFERENCE)
SECTION_PLANE = "SectionAPlane"
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateSlab": {"PlateThick"},
    "ScrewHoles": {"S0X", "S0Z"},
    FACE_REFERENCE: {"PlateWidth", "PlateHeight", "RightHoleStation", "TopHoleStation"},
    SECTION_REFERENCE: {"FieldDepth", "EngravingDepth"},
}

# Places. The engraving is incised .012 below the .016 sunk field, so the
# thinnest floor left under it is the thickness less .028: the thickness and
# both depths print .XXX so that floor is a measured number
# (Main ruling 2026-10-14; the floor's shortfall under rule 17's .060 floor is
# stated on the sheet, MINIMUM_NOTES). The outline and the hole stations
# print .XX: the outline DXF defines the profile, and the base is spotted
# through the plate at assembly, so no fit or stack reads either closer; the
# hole ligament holds rule 17's .080 at the .XX band (HOLE_LIGAMENT_WORST).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateSlab": {"PlateThick": nameplate.PLATE_THICKNESS_PRECISION},
    "ScrewHoles": {"S0X": 2, "S0Z": 2},
    FACE_REFERENCE: {
        "PlateWidth": 2,
        "PlateHeight": 2,
        "RightHoleStation": 2,
        "TopHoleStation": 2,
    },
    SECTION_REFERENCE: {"FieldDepth": 3, "EngravingDepth": 3},
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

# The one sheet-derived dimension: the floor left under the engraving, a
# parenthesised reference (thickness less the engraving depth) with no band
# and no model dimension to import. Keyed by the sheet's label.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"floor under engraving": 3}

# Section A-A's depths from the decorated face: the sunk field, then every
# engraved groove (border pinstripe and field lettering alike) to one floor.
# The floor left under the engraving prints as a reference at its nominal
# (.035); its worst case at the printed bands, ENGRAVING_FLOOR_MIN (.025),
# sits under rule 17's .060 floor as a decorative exception, not a structural
# wall (user ruling 2026-10-14; declared as fr-nameplate machinist exception
# RV-02), and the sheet states it as a minimum in MINIMUM_NOTES.
FIELD_DEPTH = 0.4064  # .016
ENGRAVING_FLOOR_DEPTH = 0.7112  # .028
FLOOR_UNDER_ENGRAVING = PLATE_THICKNESS - ENGRAVING_FLOOR_DEPTH

# Section A-A cuts the whole plate at SECTION_Y (plate-local), in the gap
# between the CHICAGO row and the scroll ornament. Along the cut (plate x):
# the raised border's top (the decorated face) up to 3.15, the border
# pinstripe groove (the engraving floor) 3.16..3.60, then the sunk field. The
# offline test proves each station against the DXFs.
SECTION_Y = 14.85
SECTION_FACE_X = 2.6
SECTION_GROOVE_X = 3.38
SECTION_FIELD_X = 5.5
# SectionReference's points (plate x, z), each on a cut-face line the section
# shows: the decorated face at its station, the groove floor and the field
# floor at theirs. A depth's dimension spans the face point to its floor
# point. Points, not construction chords: the section shows the sketch to
# keep its dimensions, and a chord lying on a cut-face line printed grey
# dashes over the outline, read as hidden lines in a section (ENFORCE
# review, rule 9).
SECTION_REFERENCE_POINTS: dict[str, tuple[float, float]] = {
    "face": (SECTION_FACE_X, 0.0),
    "groove": (SECTION_GROOVE_X, -ENGRAVING_FLOOR_DEPTH),
    "field": (SECTION_FIELD_X, -FIELD_DEPTH),
}
ENGRAVING_FLOOR_MIN = (
    PLATE_THICKNESS
    + printed_deviations(
        PLATE_THICKNESS, DRAWING_PRECISION["PlateSlab"]["PlateThick"], unit=UNIT
    )[0]
    - (
        ENGRAVING_FLOOR_DEPTH
        + printed_deviations(
            ENGRAVING_FLOOR_DEPTH,
            DRAWING_PRECISION[SECTION_REFERENCE]["EngravingDepth"],
            unit=UNIT,
        )[1]
    )
)
if ENGRAVING_FLOOR_MIN <= 0.0:
    raise AssertionError(
        f"engraving can reach through the plate: {ENGRAVING_FLOOR_MIN}"
    )

# The sunk field's one job is to stay above the engraving's floor, so the
# lettering cut into the field stays incised (PR #1468 r4 review: the .XXX
# field depth carried no stated function; its callout now names it). Both
# depths print .XXX: the engraving floor sits .012 under the field nominal
# and ENGRAVING_BELOW_FIELD_MIN (.002) at the printed bands. At the .XX
# row's +-.01 the field could cut deeper than the engraving and erase it,
# so the field's three places are the function's, not an over-specification.
ENGRAVING_BELOW_FIELD_MIN = (
    ENGRAVING_FLOOR_DEPTH
    + printed_deviations(
        ENGRAVING_FLOOR_DEPTH,
        DRAWING_PRECISION[SECTION_REFERENCE]["EngravingDepth"],
        unit=UNIT,
    )[0]
    - (
        FIELD_DEPTH
        + printed_deviations(
            FIELD_DEPTH, DRAWING_PRECISION[SECTION_REFERENCE]["FieldDepth"], unit=UNIT
        )[1]
    )
)
if ENGRAVING_BELOW_FIELD_MIN <= 0.0:
    raise AssertionError(
        f"the sunk field can cut below the engraving: {ENGRAVING_BELOW_FIELD_MIN}"
    )

# The original cosmetic-joint full-thread shortfall is owned by the pure
# mechanical spec (fr-nameplate RV-03). The base's through-tap conversion does
# not change the stock screw or its projection through the plate.

# The three vendored contours the build imports (cad/references), named on the
# sheet by the path cut_release stages each at in the release bundle, spelled
# exactly as the file is (lower case: the path must open as printed). No
# digits, no method: the shop cuts them however it engraves.
OUTLINE_DXF_NAME = "fr-nameplate-outline.dxf"
FIELD_DXF_NAME = "fr-nameplate-field.dxf"
ENGRAVING_DXF_NAME = "fr-nameplate-engraving.dxf"

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
DIMENSION_CALLOUTS = {"PlateThick": "SETS FLOOR UNDER ENGRAVING"}
# Two rows of at most 18 characters, so even a block left-aligned on the
# field's dimension line stays inside the border. "DEPTH" ties the .016 to
# the face it is measured from; the second row gives its function (PR #1468
# r6 review: "SUNK FIELD / ABOVE ENGRAVING" could read as the field standing
# .016 above the engraving floor).
FIELD_DEPTH_CALLOUT = "SUNK FIELD DEPTH\nENGRAVING BELOW IT"
ENGRAVING_DEPTH_CALLOUT = "ALL ENGRAVING"
SECTION_CALLOUTS = {
    "FieldDepth": FIELD_DEPTH_CALLOUT,
    "EngravingDepth": ENGRAVING_DEPTH_CALLOUT,
}
FLOOR_UNDER_ENGRAVING_CALLOUT = "FLOOR UNDER ENGRAVING"
HOLE_CALLOUT_PROCESS = "DRILL"


def _stated_minimum(value_mm: float) -> str:
    """A worst-case minimum in inches at three places, rounded DOWN: never overstated."""
    text = f"{math.floor(value_mm / 25.4 * 1000.0 + 1e-9) / 1000.0:.3f}"
    return text[1:] if text.startswith("0.") else text


# The two stated shortfalls, plain facts below the screw-head note:
# fr-nameplate machinist exceptions RV-02 (the floor) and RV-03 (the screws'
# full thread in the base), each formatted from its worst-case value above.
FLOOR_MINIMUM_NOTE = f"FLOOR UNDER ENGRAVING {_stated_minimum(ENGRAVING_FLOOR_MIN)} MIN"
SCREW_ENGAGEMENT_NOTE = (
    f"SCREWS ENGAGE {_stated_minimum(nameplate.SCREW_FULL_THREAD_MIN)} MIN FULL THREAD"
)
MINIMUM_NOTES = "\n".join((FLOOR_MINIMUM_NOTE, SCREW_ENGAGEMENT_NOTE))

# The DXF rows: fr-nameplate machinist exception RV-01 (the outline, the sunk
# field and the engraving are the release bundle's DXF artwork, not
# dimensioned on the sheet).
MANUFACTURING_NOTES = "\n".join(
    (
        f"OUTLINE AND CORNERS PER {bundle_path(OUTLINE_DXF_NAME)}",
        f"SUNK FIELD PER {bundle_path(FIELD_DXF_NAME)}",
        f"ENGRAVING PER {bundle_path(ENGRAVING_DXF_NAME)}",
        "DXF PATHS ARE RELATIVE TO THE RELEASE BUNDLE",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
