r"""Pure-data contract for the cone pivot post's cap jaw button (MHA-DT-005-TL-03).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
built-up cone post's vise hold (prechips S11) one button sits between each soft
jaw and a cone-boss cap: the spigot drops into the journal bore mouth and the
shoulder bears on the cap annulus, so the jaw load goes into the cap and never
into the body. Two are made.

Frame: the button axis is model +X, the jaw face at X0 and the spigot end at
+X (turned as it sits in the lathe: the jaw face is the faced end).
"""

from __future__ import annotations

import dt_cone_pivot_post_spec as post
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace

# Face (the jaw-to-cap spacer) and spigot (the centring stub). Both axial
# sizes print from the faced jaw face: the shoulder and the overall length.
FACE_DIA = 16.0
FACE_THICK = 3.0
SPIGOT_DIA = 12.2
SPIGOT_LENGTH = 2.0
OVERALL_LENGTH = FACE_THICK + SPIGOT_LENGTH

# The spigot drops into the post's journal bore by hand: its largest size stays
# a hand clearance under the smallest bore the post's running band allows. Its
# smallest only lets the button float sideways, and the shoulder still lands
# on the cap annulus (below).
SPIGOT_BAND = (0.0, -0.05)  # (upper, lower) deviations
_BORE_MIN = post.BORE_DIA + post.RUNNING_BORE_BAND[1]
SPIGOT_HAND_CLEARANCE_MIN = 0.05
if SPIGOT_DIA + SPIGOT_BAND[0] > _BORE_MIN - SPIGOT_HAND_CLEARANCE_MIN:
    raise AssertionError("cap jaw-button spigot does not drop into the smallest journal bore")

# The shoulder bears on the cap annulus only: the face, at its largest and
# shifted by the spigot's largest float, stays inside the cone boss.
FACE_PLACES = 1
_FACE_MAX = limits(FACE_DIA, FACE_PLACES)[1]
_FLOAT_MAX = (post.BORE_DIA + post.RUNNING_BORE_BAND[0]) - (SPIGOT_DIA + SPIGOT_BAND[1])
if _FACE_MAX / 2.0 + _FLOAT_MAX / 2.0 >= post.CONE_BOSS_DIA / 2.0:
    raise AssertionError("cap jaw-button face can overhang the cone boss cap")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FaceProfile": {"FaceDia"},
    "Face": {"FaceThick"},
    "SpigotProfile": {"SpigotDia"},
    "Spigot": {"OverallLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "FaceProfile": {"FaceDia": FACE_PLACES},
    "Face": {"FaceThick": 1},
    "SpigotProfile": {"SpigotDia": 2},
    "Spigot": {"OverallLength": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked jaw-button dimension needs authored places")

SURFACE_FINISHES = ()
# No general note: the spigot band alone sets the hand clearance in the
# post's journal bore (asserted above), so the print carries no fit note.
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"

_AXIS = ([1.0, 0.0, 0.0], ("__frame__",))
EXPORT_FEATURES: dict[str, ExportFeature] = {
    "spigot": ExportFeature(
        kind="boss",
        faces=(CylinderFace(SPIGOT_DIA),),
        requirements=("dia",),
        fields={
            "at": ([FACE_THICK, 0.0, 0.0], ("FACE_THICK",)),
            "axis": _AXIS,
            "dia": (
                limits(SPIGOT_DIA, 2, SPIGOT_BAND),
                ("SPIGOT_DIA", "SPIGOT_BAND", ("dt_cone_pivot_post_spec", "BORE_DIA"),
                 ("dt_cone_pivot_post_spec", "RUNNING_BORE_BAND")),
            ),
            "dia_nominal": (SPIGOT_DIA, ("SPIGOT_DIA",)),
        },
        precision={"dia": 2},
    ),
    "spigot_end": ExportFeature(
        kind="face",
        faces=(PlanarFace((1.0, 0.0, 0.0), OVERALL_LENGTH),),
        requirements=("length",),
        fields={
            "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
            "plane": (
                {"frame": "model", "axis": "x", "value": OVERALL_LENGTH},
                ("OVERALL_LENGTH",),
            ),
            "length": (limits(OVERALL_LENGTH, 1), ("OVERALL_LENGTH",)),
            "length_nominal": (OVERALL_LENGTH, ("OVERALL_LENGTH",)),
        },
        precision={"length": 1},
    ),
    "cap_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((1.0, 0.0, 0.0), FACE_THICK),),
        requirements=("thickness",),
        fields={
            "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "x", "value": FACE_THICK}, ("FACE_THICK",)),
            "thickness": (limits(FACE_THICK, 1), ("FACE_THICK",)),
            "thickness_nominal": (FACE_THICK, ("FACE_THICK",)),
            "dia": (
                limits(FACE_DIA, FACE_PLACES),
                ("FACE_DIA", ("dt_cone_pivot_post_spec", "CONE_BOSS_DIA")),
            ),
        },
        precision={"thickness": 1, "dia": FACE_PLACES},
    ),
    "jaw_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((-1.0, 0.0, 0.0), 0.0),),
        requirements=("thickness",),
        fields={
            "normal": ([-1.0, 0.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "x", "value": 0.0}, ("__frame__",)),
            "thickness": (limits(FACE_THICK, 1), ("FACE_THICK",)),
        },
        precision={"thickness": 1},
    ),
}
