r"""Pure-data contract for the cone pivot post's tall vise soft jaw (MHA-DT-005-TL-04).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
built-up cone post's vise hold (prechips S11) two of these 6061 plates replace
the PM 6 in vise's hardened jaw plates on the vise's own M10 jaw screws. The
jaws close on the two cone-boss caps through one cap jaw button each
(MHA-DT-005-TL-03) while foot B sits on 1/2 in parallels on the vise bed, so
each plate must reach over the full caps and stay under the head shoulder and
the crank boss. The fixed-jaw and moving-jaw plates are identical: two made.

Frame (model): origin at the plate's bottom-left corner on its back face (the
face that seats on the vise jaw); +X along the jaw, +Y up from the vise bed,
+Z out of the gripping face toward the work, so the gripping face is
Z = PLATE_THICK. The inventory's soft-jaw frame (prechips pedro-shop.toml,
[fixtures.vise-pm-6-tall-soft-jaws]: X along the jaw centred on the plate,
Y = 0 the gripping face with +Y into the vise jaw, Z = 0 the plate bottom on
the vise bed) is this frame by inv = (x - PLATE_LENGTH / 2, PLATE_THICK - z, y).

Vendor-interface exception to the UNC thread rule: the bolt holes clear the
vise's own M10 x 1.5 jaw screws (vise-pm-6 jaw_bolt), so they stay M10
clearance; this part carries no thread.
"""

from __future__ import annotations

import dt_cone_pivot_post_spec as post
import dt_cone_pivot_post_tl_cap_jaw_button_spec as button
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace
from _hole_spec import HoleSpec
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

MM_PER_IN = 25.4

# Plate: the hardened plate's length, the jaw height above the vise bed, and
# the finished thickness after the gripping face is skimmed in place.
PLATE_LENGTH = 158.67
PLATE_HEIGHT = 63.5
PLATE_THICK = 19.05
# Bolt holes: an example reading of the hardened plate's two holes (+-50.8
# about the plate centre, symmetric), spotted through it. Each stands its
# two-place reading from its own end; both print from the left end.
# 7/16 drill through, 11/16 end-mill counterbore from the gripping face to the
# hardened plate's counterbore depth plus 1.25, so the vise's own screws reach
# the same thread.
BOLT_END_OFFSET = 28.54
BOLT_HEIGHT = 22.5
BOLT_LEFT_X = BOLT_END_OFFSET
BOLT_RIGHT_X = round(PLATE_LENGTH - BOLT_END_OFFSET, 2)
BOLT_XS = (BOLT_LEFT_X, BOLT_RIGHT_X)
BOLT_HOLE_DIA = 7.0 / 16.0 * MM_PER_IN
CBORE_DIA = 11.0 / 16.0 * MM_PER_IN
CBORE_DEPTH = 11.75
BOLT_HOLE_SPEC = HoleSpec(
    "counterbore_socket",
    "3/8",
    overrides_mm={
        "HoleDiameter": BOLT_HOLE_DIA,
        "CounterBoreDiameter": CBORE_DIA,
        "CounterBoreDepth": CBORE_DEPTH,
    },
)

# Places select the title block's general bands; nothing on the plate is a
# fit. The checks below prove those bands hold the S11 hold.
LENGTH_PLACES = 2
HEIGHT_PLACES = 1
THICK_PLACES = 2
BOLT_PLACES = 2

# The vise's own M10 x 1.5 socket head jaw screws (ISO 4762: head 16.0
# diameter, 10.0 high) and its readings (vise-pm-6: opening 6.135 in, hardened
# jaw plate 0.7010 in thick).
JAW_SCREW_MAJOR = 10.0
JAW_SCREW_HEAD_DIA = 16.0
JAW_SCREW_HEAD_HEIGHT = 10.0
VISE_OPENING = 6.135 * MM_PER_IN
HARD_JAW_DEPTH = 0.7010 * MM_PER_IN
# S11: foot B stands on two 1/2 in parallels on the vise bed.
PARALLEL_HEIGHT = 0.5 * MM_PER_IN

_XX = printed_band_mm(2)
_HOLE_MAX = BOLT_HOLE_DIA + drilled_oversize_mm()
_HEIGHT_RANGE = limits(PLATE_HEIGHT, HEIGHT_PLACES)
_THICK_RANGE = limits(PLATE_THICK, THICK_PLACES)

# Jaw top above foot B at the plate's printed height band.
JAW_TOP_ABOVE_FOOT = tuple(height - PARALLEL_HEIGHT for height in _HEIGHT_RANGE)
# The jaws reach over the full caps: the cap top at the post's highest cone
# axis and largest boss.
_BOSS_MAX = limits(post.CONE_BOSS_DIA, post.DRAWING_PRECISION_BY_NAME["ConeBossDia"])[1]
CAP_TOP_ABOVE_FOOT = post.BORE_HEIGHT + post.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM + _BOSS_MAX / 2.0
# ...and stay under the head shoulder and the crank boss underside.
_HEAD_SHOULDER_MIN = post.HEAD_BASE_Y
_CRANK_BOSS_UNDERSIDE = post.CRANK_BORE_HEIGHT - post.CRANK_BOSS_DIA / 2.0
JAW_TOP_MARGINS = {
    "over the cone caps": JAW_TOP_ABOVE_FOOT[0] - CAP_TOP_ABOVE_FOOT,
    "under the head shoulder": _HEAD_SHOULDER_MIN - JAW_TOP_ABOVE_FOOT[1],
    "under the crank boss": _CRANK_BOSS_UNDERSIDE - JAW_TOP_ABOVE_FOOT[1],
}
if min(JAW_TOP_MARGINS.values()) <= 0.0:
    raise AssertionError(f"soft-jaw height misses the S11 hold: {JAW_TOP_MARGINS}")

# The cap jaw button bears on solid gripping face: its largest face, at the
# post's lowest cone axis, stays above the counterbore rims.
_BUTTON_FACE_MAX = limits(button.FACE_DIA, button.FACE_PLACES)[1]
_BUTTON_BOTTOM_ABOVE_BED = (
    PARALLEL_HEIGHT + post.BORE_HEIGHT - post.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM
) - _BUTTON_FACE_MAX / 2.0
_CBORE_TOP_ABOVE_BED = BOLT_HEIGHT + _XX + (CBORE_DIA + _XX) / 2.0
BUTTON_OVER_CBORE = _BUTTON_BOTTOM_ABOVE_BED - _CBORE_TOP_ABOVE_BED
if BUTTON_OVER_CBORE <= 0.0:
    raise AssertionError("cap jaw button lands on a soft-jaw counterbore")

# The vise still closes on the buttons over the caps with the thicker plates.
OPENING_WITH_PLATES = VISE_OPENING - 2.0 * (_THICK_RANGE[1] - HARD_JAW_DEPTH)
GRIP_SPAN = post.CONE_BOSS_LENGTH + 2.0 * limits(button.FACE_THICK, 1)[1]
if OPENING_WITH_PLATES <= GRIP_SPAN:
    raise AssertionError("soft jaws cannot open over the buttoned cone caps")

# The jaw screws: heads sink under the gripping face, pass the hole, and
# clear the counterbore; the counterbore floor keeps a rule-12 wall.
WALL_FLOOR = 2.0
SCREW_HEAD_RECESS = CBORE_DEPTH - _XX - JAW_SCREW_HEAD_HEIGHT
SCREW_HEAD_CLEARANCE = CBORE_DIA - _XX - JAW_SCREW_HEAD_DIA
CBORE_FLOOR = _THICK_RANGE[0] - (CBORE_DEPTH + _XX)
if min(SCREW_HEAD_RECESS, SCREW_HEAD_CLEARANCE, BOLT_HOLE_DIA - JAW_SCREW_MAJOR) <= 0.0:
    raise AssertionError("the vise's jaw screws do not seat below the gripping face")
if CBORE_FLOOR < WALL_FLOOR:
    raise AssertionError("soft-jaw counterbore floor under the rule-12 wall")
if BOLT_HEIGHT - _XX - (CBORE_DIA + _XX) / 2.0 < WALL_FLOOR:
    raise AssertionError("soft-jaw counterbore breaks the bottom wall")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateLength", "PlateHeight"},
    "Plate": {"PlateThick"},
    "BoltHoles": {"BoltLeftX", "BoltRightX", "BoltY"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {"PlateLength": LENGTH_PLACES, "PlateHeight": HEIGHT_PLACES},
    "Plate": {"PlateThick": THICK_PLACES},
    "BoltHoles": {"BoltLeftX": BOLT_PLACES, "BoltRightX": BOLT_PLACES, "BoltY": BOLT_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked soft-jaw dimension needs authored places")
# Both holes stand on the one printed height.
DIMENSION_PREFIXES = {("BoltHoles", "BoltY"): "2X "}

SURFACE_FINISHES = ()
DRAWING_NOTES = "\n".join(
    (
        "COUNTERBORE FROM THE GRIPPING FACE. SPOT THE BOLT HOLES",
        "THROUGH THE VISE'S HARDENED JAW PLATE.",
        "SKIM THE GRIPPING FACE IN PLACE ON THE VISE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

_JAW_TOP_SOURCES = (
    "PLATE_HEIGHT",
    "PARALLEL_HEIGHT",
    ("dt_cone_pivot_post_spec", "BORE_HEIGHT"),
    ("dt_cone_pivot_post_spec", "JOURNAL_AXIS_HEIGHT_TOLERANCE_MM"),
    ("dt_cone_pivot_post_spec", "CONE_BOSS_DIA"),
    ("dt_cone_pivot_post_spec", "HEAD_BASE_Y"),
    ("dt_cone_pivot_post_spec", "CRANK_BORE_HEIGHT"),
    ("dt_cone_pivot_post_spec", "CRANK_BOSS_DIA"),
)
_CBORE_FLOOR_Z = PLATE_THICK - CBORE_DEPTH


def _bolt_features(side: str, x: float, name: str) -> dict[str, ExportFeature]:
    hole = f"bolt_{side}"
    return {
        hole: ExportFeature(
            kind="hole",
            faces=(CylinderFace(BOLT_HOLE_DIA, contains_x_mm=x),),
            requirements=("dia", "thru", "station", "height"),
            fields={
                "at": ([x, BOLT_HEIGHT, PLATE_THICK], (name, "BOLT_HEIGHT", "PLATE_THICK")),
                "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
                "dia": (
                    [BOLT_HOLE_DIA, round(_HOLE_MAX, 12)],
                    ("BOLT_HOLE_DIA", "JAW_SCREW_MAJOR"),
                ),
                "nominal_dia": (BOLT_HOLE_DIA, ("BOLT_HOLE_DIA",)),
                "thru": (True, ("BOLT_HOLE_SPEC",)),
                "station": (limits(x, BOLT_PLACES), (name,)),
                "station_nominal": (x, (name,)),
                "height": (limits(BOLT_HEIGHT, BOLT_PLACES), ("BOLT_HEIGHT",)),
                "height_nominal": (BOLT_HEIGHT, ("BOLT_HEIGHT",)),
            },
            precision={"dia": 2, "station": BOLT_PLACES, "height": BOLT_PLACES},
        ),
        f"{hole}_counterbore": ExportFeature(
            kind="counterbore",
            faces=(
                CylinderFace(CBORE_DIA, contains_x_mm=x),
                PlanarFace((0.0, 0.0, 1.0), _CBORE_FLOOR_Z, contains_x_mm=x),
            ),
            requirements=("dia", "depth"),
            fields={
                "parent": (hole, ("BOLT_HOLE_SPEC",)),
                "dia": (limits(CBORE_DIA, 2), ("CBORE_DIA", "JAW_SCREW_HEAD_DIA")),
                "nominal_dia": (CBORE_DIA, ("CBORE_DIA",)),
                "depth": (limits(CBORE_DEPTH, 2), ("CBORE_DEPTH", "JAW_SCREW_HEAD_HEIGHT")),
                "depth_ref": (CBORE_DEPTH, ("CBORE_DEPTH",)),
            },
            precision={"dia": 2, "depth": 2},
        ),
    }


EXPORT_FEATURES: dict[str, ExportFeature] = {
    # The gripping face carries a cap jaw button on each cone-boss cap.
    "grip_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), PLATE_THICK),),
        requirements=("thickness",),
        fields={
            "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": PLATE_THICK}, ("PLATE_THICK",)),
            "thickness": (_THICK_RANGE, ("PLATE_THICK",)),
            "thickness_nominal": (PLATE_THICK, ("PLATE_THICK",)),
        },
        precision={"thickness": THICK_PLACES},
    ),
    # The back face seats on the vise jaw in place of the hardened plate.
    "jaw_seat": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
        requirements=("thickness",),
        fields={
            "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
            "thickness": (_THICK_RANGE, ("PLATE_THICK",)),
        },
        precision={"thickness": THICK_PLACES},
    ),
    # The bottom edge stands on the vise bed beside the parallels.
    "bed_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
        requirements=("height",),
        fields={
            "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
            "height": (_HEIGHT_RANGE, ("PLATE_HEIGHT",)),
        },
        precision={"height": HEIGHT_PLACES},
    ),
    # The jaw top: over the cone caps, under the head shoulder and crank boss.
    "jaw_top": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 1.0, 0.0), PLATE_HEIGHT),),
        requirements=("height",),
        fields={
            "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": PLATE_HEIGHT}, ("PLATE_HEIGHT",)),
            "height": (_HEIGHT_RANGE, _JAW_TOP_SOURCES),
            "height_nominal": (PLATE_HEIGHT, ("PLATE_HEIGHT",)),
            "length": (limits(PLATE_LENGTH, LENGTH_PLACES), ("PLATE_LENGTH",)),
        },
        precision={"height": HEIGHT_PLACES, "length": LENGTH_PLACES},
    ),
    **_bolt_features("left", BOLT_LEFT_X, "BOLT_LEFT_X"),
    **_bolt_features("right", BOLT_RIGHT_X, "BOLT_RIGHT_X"),
}
