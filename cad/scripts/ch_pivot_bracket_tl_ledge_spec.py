r"""Pure-data contract for the pivot bracket's angle-plate ledge (MHA-CH-008-TL-01).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
bracket's S4 setup (prechips bracket plan S4 hold) the bracket's seat face
lies on the reworked angle plate's upright (MHA-CH-008-TL-02) and its foot
free end rests on this 1018 block, screwed to the upright by two
#10-24 x 5/8 SHCS through #5 holes. The ledge top carries the downward
facing and drilling load; S4 indicates the foot edge and touches Z on the
part, so the ledge is a plain stop. Fitting: the ledge stands on a 1-2-3
block on the table, back face flat on the upright, and the upright's taps
are spotted through its two holes before it is screwed down.

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
# 1-2-3 block to the foot's free end. Wider than the 16 foot it carries so its
# two screw holes keep the rule-12 2.0 walls at general tolerance; its ends
# stay clear of the bridge's stud nuts.
LEDGE_WIDTH = 22.0
LEDGE_THICK = bracket.FOOT_H  # 6.0
LEDGE_HEIGHT = round(plate.LEDGE_TOP_Y - plate.BLOCK_HEIGHT, 6)  # 15.9
SIZE_PLACES = 1
if LEDGE_WIDTH < bracket.FOOT_W:
    raise AssertionError("ledge narrower than the bracket foot it carries")
if limits(LEDGE_WIDTH, SIZE_PLACES)[1] / 2.0 >= plate.STUD_HALF_PITCH - plate.STUD_NUT_DIA / 2.0:
    raise AssertionError("ledge end reaches a bridge stud nut")

# Two #5 screw holes, 8.0 under the top, on the upright's tap pitch. The taps
# are spotted through these holes, so their stations only have to keep the
# walls, all at the general one-place tolerance.
CLEARANCE_SPEC = plate.LEDGE_CLEARANCE_SPEC
HOLE_X = (
    LEDGE_WIDTH / 2.0 - plate.SCREW_HALF_PITCH,
    LEDGE_WIDTH / 2.0 + plate.SCREW_HALF_PITCH,
)
HOLE_Y = round(plate.SCREW_Y - plate.BLOCK_HEIGHT, 6)  # 7.9
HOLE_X_PLACES = 1
HOLE_Y_PLACES = 1
HOLE_DIA = blind_cut_dia_mm(CLEARANCE_SPEC)
_HOLE_R_MAX = (HOLE_DIA + drilled_oversize_mm()) / 2.0
_X1 = limits(HOLE_X[0], HOLE_X_PLACES)
_X2 = limits(HOLE_X[1], HOLE_X_PLACES)
_Y = limits(HOLE_Y, HOLE_Y_PLACES)
HOLE_LIGAMENTS_MIN = {
    "left end": _X1[0] - _HOLE_R_MAX,
    "right end": limits(LEDGE_WIDTH, SIZE_PLACES)[0] - _X2[1] - _HOLE_R_MAX,
    "web": _X2[0] - _X1[1] - 2.0 * _HOLE_R_MAX,
    "bottom": _Y[0] - _HOLE_R_MAX,
    "top": limits(LEDGE_HEIGHT, SIZE_PLACES)[0] - _Y[1] - _HOLE_R_MAX,
}
if min(HOLE_LIGAMENTS_MIN.values()) < 2.0:
    raise AssertionError(f"ledge screw-hole ligaments {HOLE_LIGAMENTS_MIN} under 2.0")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LedgeProfile": {"Width", "Height"},
    "Ledge": {"Thick"},
    "ScrewHoles": {"Hole1X", "Hole2X", "Hole1Y"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LedgeProfile": {"Width": SIZE_PLACES, "Height": SIZE_PLACES},
    "Ledge": {"Thick": SIZE_PLACES},
    "ScrewHoles": {"Hole1X": HOLE_X_PLACES, "Hole2X": HOLE_X_PLACES, "Hole1Y": HOLE_Y_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked ledge dimension needs authored places")

SURFACE_FINISHES = ()
DRAWING_NOTES = "SPOT THE ANGLE PLATE TAPS THROUGH THESE HOLES."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

EXPORT_FEATURES: dict[str, ExportFeature] = {
    "foot_rest": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 1.0, 0.0), LEDGE_HEIGHT),),
        requirements=("height", "width"),
        fields={
            "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": LEDGE_HEIGHT}, ("LEDGE_HEIGHT",)),
            "height": (
                limits(LEDGE_HEIGHT, SIZE_PLACES),
                ("LEDGE_HEIGHT", "SIZE_PLACES", ("ch_pivot_bracket_spec", "FOOT_LEN")),
            ),
            "height_nominal": (
                LEDGE_HEIGHT,
                ("LEDGE_HEIGHT", ("ch_pivot_bracket_spec", "FOOT_LEN")),
            ),
            "height_from": ("block_face", ("__frame__",)),
            "width": (limits(LEDGE_WIDTH, SIZE_PLACES), ("LEDGE_WIDTH", ("ch_pivot_bracket_spec", "FOOT_W"))),
        },
        precision={"height": SIZE_PLACES, "width": SIZE_PLACES},
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
            "thickness": (limits(LEDGE_THICK, SIZE_PLACES), ("LEDGE_THICK",)),
        },
        precision={"thickness": SIZE_PLACES},
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
            "station": (limits(_x, HOLE_X_PLACES), ("HOLE_X", "HOLE_X_PLACES")),
            "station_nominal": (_x, ("HOLE_X",)),
            "height": (
                limits(HOLE_Y, HOLE_Y_PLACES),
                ("HOLE_Y", "HOLE_Y_PLACES", ("ch_pivot_bracket_tl_angle_plate_spec", "SCREW_Y")),
            ),
            "height_nominal": (HOLE_Y, ("HOLE_Y",)),
            "height_from": ("block_face", ("__frame__",)),
        },
        precision={"dia": 2, "station": HOLE_X_PLACES, "height": HOLE_Y_PLACES},
    )
