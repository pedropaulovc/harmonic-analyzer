r"""Pure-data contract for the pivot bracket's angle-plate ledge (MHA-CH-008-TL-01).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
bracket's S4 setup (prechips bracket plan S4 hold) the bracket's seat face
lies on the reworked angle plate's upright (MHA-CH-008-TL-02) and its foot
free end rests on this 1018 block, screwed to the upright by two
#10-24 x 5/8 SHCS through #5 holes. The ledge top carries the downward
facing and drilling load and sets the foot's tilt about the setup's
plate-normal axis. Fitting: the ledge stands on a 1-2-3 block on the table,
back face flat on the upright, while its screws are tightened.

Frame (model, mm): origin at the ledge's left end, on its bottom face and in
its back face (the face that seats on the upright). +X along the ledge, +Y up,
+Z out of the front face (the back face is Z0, the front face Z LEDGE_THICK).
It is the angle plate's model frame translated by
(PLATE_LENGTH/2 - LEDGE_WIDTH/2, BLOCK_HEIGHT, 0), so the inventory's fixture
frame (bracket plan setup frame TC) is
TC = (x - LEDGE_WIDTH/2, -z, y + BLOCK_HEIGHT - (PLATE_HEIGHT + PART_PROUD)).
"""

from __future__ import annotations

import ch_pivot_bracket_spec as bracket
import ch_pivot_bracket_tl_angle_plate_spec as plate
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace
from _hole_spec import blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm

# As thick as the foot's depth off the upright and as tall as the gap from the
# 1-2-3 block to the foot's free end. Wider than the 16 foot it carries (the
# inventory's 16 left its screw holes under 1.5 end walls, the rule-12 floor);
# its ends stay clear of the bridge's stud nuts.
LEDGE_WIDTH = 20.0
LEDGE_THICK = bracket.FOOT_H  # 6.0
LEDGE_HEIGHT = round(plate.LEDGE_TOP_Y - plate.BLOCK_HEIGHT, 6)  # 15.9
if LEDGE_WIDTH < bracket.FOOT_W:
    raise AssertionError("ledge narrower than the bracket foot it carries")
if limits(LEDGE_WIDTH, 1)[1] / 2.0 >= plate.STUD_HALF_PITCH - plate.STUD_NUT_DIA / 2.0:
    raise AssertionError("ledge end reaches a bridge stud nut")

# The top sets the foot's tilt about the plate normal: it must stay parallel
# to the table within 0.02 over the foot's width (about 0.04 at the bracket's
# crown). The block keeps the bottom parallel to the table, so the height band
# across the full top is that parallelism, and the height itself is otherwise
# free (S4 touches Z on the part).
TOP_PARALLEL = 0.02
HEIGHT_BAND = (TOP_PARALLEL / 2.0, -TOP_PARALLEL / 2.0)  # (upper, lower)
HEIGHT_PLACES = 2

# Two #5 screw holes, 8.0 under the top: on the upright's tapped-hole pitch,
# dimensioned from the bottom face the block holds, under the plate's one
# station band (its derivation lives with the taps).
CLEARANCE_SPEC = plate.LEDGE_CLEARANCE_SPEC
HOLE_X = (
    LEDGE_WIDTH / 2.0 - plate.SCREW_HALF_PITCH,
    LEDGE_WIDTH / 2.0 + plate.SCREW_HALF_PITCH,
)
HOLE_Y = round(plate.SCREW_Y - plate.BLOCK_HEIGHT, 6)  # 7.9
LOCATION_BAND = plate.LOCATION_BAND
LOCATION_PLACES = plate.LOCATION_PLACES
HOLE_DIA = blind_cut_dia_mm(CLEARANCE_SPEC)
_HOLE_R_MAX = (HOLE_DIA + drilled_oversize_mm()) / 2.0
HOLE_LIGAMENTS_MIN = {
    "left end": HOLE_X[0] - LOCATION_BAND - _HOLE_R_MAX,
    "right end": limits(LEDGE_WIDTH, 1)[0] - HOLE_X[1] - LOCATION_BAND - _HOLE_R_MAX,
    "web": HOLE_X[1] - HOLE_X[0] - 2.0 * LOCATION_BAND - 2.0 * _HOLE_R_MAX,
    "bottom": HOLE_Y - LOCATION_BAND - _HOLE_R_MAX,
}
if min(HOLE_LIGAMENTS_MIN.values()) < 2.0:
    raise AssertionError(f"ledge screw-hole ligaments {HOLE_LIGAMENTS_MIN} under 2.0")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LedgeProfile": {"Width", "Height"},
    "Ledge": {"Thick"},
    "ScrewHoles": {"Hole1X", "Hole2X", "Hole1Y"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LedgeProfile": {"Width": 1, "Height": HEIGHT_PLACES},
    "Ledge": {"Thick": 1},
    "ScrewHoles": {"Hole1X": LOCATION_PLACES, "Hole2X": LOCATION_PLACES, "Hole1Y": LOCATION_PLACES},
}
HOLE_LOCATION_DIMENSIONS = DRAWING_DIMENSIONS["ScrewHoles"]
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked ledge dimension needs authored places")

SURFACE_FINISHES = ()
DRAWING_NOTES = "TOP AND BOTTOM FACES LAPPED."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

_STATION = (LOCATION_BAND, -LOCATION_BAND)
EXPORT_FEATURES: dict[str, ExportFeature] = {
    "foot_rest": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 1.0, 0.0), LEDGE_HEIGHT),),
        requirements=("height", "width"),
        fields={
            "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": LEDGE_HEIGHT}, ("LEDGE_HEIGHT",)),
            "height": (
                limits(LEDGE_HEIGHT, HEIGHT_PLACES, HEIGHT_BAND),
                ("LEDGE_HEIGHT", "HEIGHT_BAND", "TOP_PARALLEL", ("ch_pivot_bracket_spec", "FOOT_W")),
            ),
            "height_nominal": (
                LEDGE_HEIGHT,
                ("LEDGE_HEIGHT", ("ch_pivot_bracket_spec", "FOOT_LEN")),
            ),
            "height_from": ("block_face", ("__frame__",)),
            "width": (limits(LEDGE_WIDTH, 1), ("LEDGE_WIDTH", ("ch_pivot_bracket_spec", "FOOT_W"))),
        },
        precision={"height": HEIGHT_PLACES, "width": 1},
    ),
    "block_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
        requirements=(),
        fields={
            "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        },
    ),
    "upright_seat": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
        requirements=("thickness",),
        fields={
            "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
            "thickness": (limits(LEDGE_THICK, 1), ("LEDGE_THICK",)),
        },
        precision={"thickness": 1},
    ),
}
for _side, _x in (("left", HOLE_X[0]), ("right", HOLE_X[1])):
    EXPORT_FEATURES[f"screw_hole_{_side}"] = ExportFeature(
        kind="hole",
        faces=(CylinderFace(HOLE_DIA, contains_x_mm=_x),),
        requirements=("dia", "station", "height"),
        fields={
            "at": ([_x, HOLE_Y, LEDGE_THICK], ("HOLE_X", "HOLE_Y", "LEDGE_THICK")),
            "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
            "drill": (CLEARANCE_SPEC.size, ("CLEARANCE_SPEC",)),
            "dia": (
                limits(HOLE_DIA, 2, (drilled_oversize_mm(), 0.0)),
                ("HOLE_DIA", ("ch_pivot_bracket_tl_angle_plate_spec", "SCREW_CLEARANCE")),
            ),
            "nominal_dia": (HOLE_DIA, ("HOLE_DIA",)),
            "thru": (True, ("CLEARANCE_SPEC",)),
            # model X from the left end; model Y from the block face
            "station": (
                limits(_x, LOCATION_PLACES, _STATION),
                ("HOLE_X", "LOCATION_BAND", ("ch_pivot_bracket_tl_angle_plate_spec", "SCREW_CLEARANCE")),
            ),
            "station_nominal": (_x, ("HOLE_X",)),
            "height": (
                limits(HOLE_Y, LOCATION_PLACES, _STATION),
                ("HOLE_Y", "LOCATION_BAND", ("ch_pivot_bracket_tl_angle_plate_spec", "SCREW_Y")),
            ),
            "height_nominal": (HOLE_Y, ("HOLE_Y",)),
            "height_from": ("block_face", ("__frame__",)),
        },
        precision={"dia": 2, "station": LOCATION_PLACES, "height": LOCATION_PLACES},
    )
