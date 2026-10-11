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

import _config
import dt_cone_pivot_post_spec as post
from _printed_tolerance import printed_deviations

# Face (the jaw-to-cap spacer) and spigot (the centring stub). Both axial
# sizes print from the faced jaw face: the shoulder and the overall length.
FACE_DIA = 15.0
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

# The band's reason belongs on its callout (policy rule 2): it names the mate
# and states the acceptance, so the 0.05 band is not read as unjustified.
POST_NUMBER = _config.parts("dt-cone-pivot-post")["number"]
SPIGOT_CALLOUT = f"ENTERS {POST_NUMBER}\nCONE PIVOT POST\nJOURNAL BORE BY HAND"

# The shoulder bears on the cap annulus only: the face, at its largest and
# shifted by the spigot's largest float, stays inside the smallest cone boss
# the post's print accepts; at its smallest and shifted the other way it still
# covers the bore edge, so the shoulder always lands on the annulus.
FACE_PLACES = 1
_FACE_MIN, _FACE_MAX = [round(FACE_DIA + deviation, 12) for deviation in printed_deviations(FACE_DIA, FACE_PLACES)]
_FLOAT_MAX = (post.BORE_DIA + post.RUNNING_BORE_BAND[0]) - (SPIGOT_DIA + SPIGOT_BAND[1])
CONE_BOSS_MIN = round(
    post.CONE_BOSS_DIA + printed_deviations(
        post.CONE_BOSS_DIA, post.DRAWING_PRECISION["ConeBossProfile"]["ConeBossDia"]
    )[0],
    12,
)
if _FACE_MAX / 2.0 + _FLOAT_MAX / 2.0 >= CONE_BOSS_MIN / 2.0:
    raise AssertionError("cap jaw-button face can overhang the cone boss cap")
if _FACE_MIN / 2.0 - _FLOAT_MAX / 2.0 <= (post.BORE_DIA + post.RUNNING_BORE_BAND[0]) / 2.0:
    raise AssertionError("cap jaw-button shoulder can miss the cap annulus")

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
# No general note: the spigot's fit acceptance sits on its own callout.
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"

