r"""Pure-data contract for the rocker arm's pivot-screw washer (MHA-CH-006-TL-07).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's S4 profile hold the MHA-CH-006-TL-06 pivot screw's head clamps
this washer onto the upper hub face, so the clamp load goes washer -> hub ->
hub stand and the head never scuffs the hub.

Route (shop-additions.md section 2): O1 drill rod, drilled and parted off,
used as supplied (annealed), faced both sides; it only clamps.

Frame (the inventory's fixture frame, rocker-inv:1735-1751): origin on the
pivot axis at the upper hub face, +Z up; the washer sits Z0..1.5.
"""

from __future__ import annotations

import ch_rocker_arm_tl_pivot_screw_spec as screw
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace

# AUTHOR'S CHOICE: Ø10 stock O1 drill rod with its OD left as supplied (the
# inventory's 9.0 would leave a 1.2 wall); the head still bears inside it and
# its rim may overhang the Ø10.2 hub edge, which carries nothing. The wall stays under the rule-12 floor at
# the title-block band: accepted on the print for a clamp-only washer.
OUTER_DIA = 10.0
BORE_DIA = 6.6
THICK = screw.WASHER_THICK
PLACES = 1
# A drilled bore: the title block's DRILLED HOLES row, +0.10/0, held natively.
BORE_BAND = (0.10, 0.0)

# The bore passes the largest shoulder; the head, at its smallest, still
# bears on the washer face outside the largest bore.
_BORE_MIN = BORE_DIA + BORE_BAND[1]
_BORE_MAX = BORE_DIA + BORE_BAND[0]
if _BORE_MIN <= screw.SHOULDER_DIA + screw.SHOULDER_BAND[0]:
    raise AssertionError("pivot washer bore does not pass the pivot-screw shoulder")
if _BORE_MAX >= screw.HEAD_DIA + screw.HEAD_BAND[1]:
    raise AssertionError("pivot-screw head has no bearing on the washer")
# The head's clamp ring lands on the hub face, inside the arm's hub diameter;
# a washer rim past the hub edge only overhangs air.
if screw.HEAD_DIA + screw.HEAD_BAND[0] >= screw.rocker.HUB_DIA:
    raise AssertionError("pivot-screw head clamps outside the rocker hub face")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WasherProfile": {"OuterDia", "BoreDia"},
    "Washer": {"Thick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "WasherProfile": {"OuterDia": PLACES, "BoreDia": PLACES},
    "Washer": {"Thick": PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked pivot-washer dimension needs authored places")

DRAWING_NOTES = "\n".join(
    (
        "THIN WALL ACCEPTED: CLAMP WASHER ONLY, IT LOCATES NOTHING.",
    )
)
BORE_CALLOUT = "DRILL"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 5:1"

EXPORT_FEATURES: dict[str, ExportFeature] = {
    "bore": ExportFeature(
        kind="hole",
        faces=(CylinderFace(BORE_DIA),),
        requirements=("dia",),
        fields={
            "at": ([0.0, 0.0, 0.0], ("__frame__",)),
            "axis": ([0.0, 0.0, 1.0], ("__frame__",)),
            "dia": (
                limits(BORE_DIA, PLACES, BORE_BAND),
                ("BORE_DIA", "BORE_BAND", ("ch_rocker_arm_tl_pivot_screw_spec", "SHOULDER_DIA")),
            ),
            "thru": (True, ("BORE_DIA",)),
        },
        precision={"dia": PLACES},
    ),
    "hub_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
        requirements=("thickness",),
        fields={
            "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
            "thickness": (limits(THICK, PLACES), ("THICK",)),
            "dia": (limits(OUTER_DIA, PLACES), ("OUTER_DIA", ("ch_rocker_arm_spec", "HUB_DIA"))),
            "process": ("face", ("DRAWING_NOTES",)),
        },
        precision={"thickness": PLACES, "dia": PLACES},
    ),
    "head_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), THICK),),
        requirements=("thickness",),
        fields={
            "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": THICK}, ("THICK",)),
            "thickness": (limits(THICK, PLACES), ("THICK",)),
            "process": ("face", ("DRAWING_NOTES",)),
        },
        precision={"thickness": PLACES},
    ),
}
