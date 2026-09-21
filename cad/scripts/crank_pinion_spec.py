r"""Pure-data dimensional contract shared by the crank pinion and its drawing.

The 16T straight-spur pinion on the crankshaft that meshes the 64T crank-drive
gear (4:1 crank-to-cone reduction), with the plain hub boss on its outboard
face that the ch. 12 p. 19 photos show (page002_img02 / img06): a cylinder at
the tooth root, a little over half a face long, edge rounded, the crankshaft
end recessed inside it, and the small head of a radial retention pin on its
side. The pin is what keeps the "removable" pinion on the shaft.

Recreated under ``cad/docs/drawing-simplicity-policy.md``. The sizes a
machinist turns, bores and drills -- outside diameter, face width, bore, boss
diameter, overall length, pin station -- are NATIVE model dimensions carrying
their own decimal places and bands (rules 1, 2, 4); the tooth system that a
cut-gear print cannot express as dimensions stays in the gear-data block rule 6
allows, with every generating number marked REF; and nothing here restates the
title block.

PURE DATA, no SolidWorks/COM imports: ``build_crank_pinion`` marks and
tolerances exactly ``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` on the model,
``draw_crank_pinion`` keeps exactly the same names, and the offline test
(``test_crank_pinion_drawing.py``) fails the moment one side drifts.
"""

from __future__ import annotations

import math

import _config
import crankshaft_spec
from _gtol_spec import CylinderFace
from _hole_spec import FRACTIONAL_DRILL_MM, HoleSpec, drill_process
from _surface_finish import MACHINED_UM, SurfaceFinishControl


MM_PER_IN = 25.4

TEETH = 16
DIAMETRAL_PITCH = 25.73110354953376  # fixed-post recentered mesh
PRESSURE_ANGLE_DEG = 14.5
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH / DIAMETRAL_PITCH * MM_PER_IN
OUTSIDE_DIA = (TEETH + 2) / DIAMETRAL_PITCH * MM_PER_IN
WHOLE_DEPTH = 2.157 / DIAMETRAL_PITCH * MM_PER_IN
TRANSVERSE_CIRCULAR_TOOTH_THICKNESS = math.pi * MODULE_MM / 2.0

# The blank's outside diameter is the one tooth-system number the turner sets
# before a cutter touches the part, so it prints as a NATIVE dimension instead
# of as text in the data block -- but at the title block's general .XX grade,
# with no band of its own. The crossed 16T:64T mesh is built with
# ``fits.crank_mesh.c2c_slack_mm`` 0.25 mm of centre-distance slack on top of
# the tooth system's own 0.157/DP tip clearance (0.155 mm), so the tip circle
# has 0.405 mm of radial room: +/-0.51 diametral is +/-0.255 radial, inside it.
# A tighter band here would be a habit, not a requirement
# (cad/docs/tolerance-policy.md, "Fit classes" and the one-sided-load bullets).
MESH_C2C_SLACK_MM = _config.fit("crank_mesh")["c2c_slack_mm"]
TIP_CLEARANCE_MM = 0.157 / DIAMETRAL_PITCH * MM_PER_IN

# The bore over the crankshaft is the part's one critical fit, and the only
# reason anything here prints a third decimal: a slip fit exists only if the
# size limits on BOTH mating features are narrower than the clearance band it
# claims (tolerance-policy.md step 6b). So the band is DERIVED -- never a
# per-part number -- from the named fit class and the shaft's own published
# limits: bore_min = shaft_max + clearance_min, bore_max = shaft_min +
# clearance_max. Move either input and this moves with it.
BORE_DIA = 0.375 * MM_PER_IN  # 9.525 (3/8" crankshaft)
_CLEARANCE_MIN, _CLEARANCE_MAX = _config.fit("shaft_in_bushing")[
    "diametral_clearance_mm"
]
_SHAFT_UPPER, _SHAFT_LOWER = crankshaft_spec.SHAFT_DIA_BAND
BORE_DIA_BAND = (  # (upper, lower) deviations
    round(_SHAFT_LOWER + _CLEARANCE_MAX, 3),
    round(_SHAFT_UPPER + _CLEARANCE_MIN, 3),
)

FACE_WIDTH = 10.8  # spans the 64T row north of the v2 crank boss
# (build_crank_pinion drives the blank from this; build_drive_train_assembly's
# PINION_FACE asserts equality.)

# --- Hub boss + retention pin (ch. 12 p. 19, page002_img02 / img06) ---------
#
# The boss is the blank turned down to the ROOT circle beyond the toothed
# length: the photo reads it at the tooth roots, and the root circle is the
# largest diameter that can never meet the 64T's tips (they clear it by the
# tooth system's own tip clearance plus the mesh's centre-distance slack,
# exactly as they clear the gap floors). It runs 0.6 face widths -- the photo's
# "a little over half" -- which covers the crankshaft's outboard overhang past
# the pinion's north face and leaves its end recessed inside the boss as
# photographed (build_drive_train_assembly asserts the recess). The boss is
# extruded from the SAME faced end as the teeth, so the print carries one
# overall length from that end (rule 7: lengths from one faced end, the overall
# length real and conspicuous), and the toothed length is FaceWidth.
ROOT_DIA = (TEETH - 2.0 * 1.157) / DIAMETRAL_PITCH * MM_PER_IN  # 13.51
BOSS_DIA = ROOT_DIA
BOSS_LENGTH = 0.6 * FACE_WIDTH  # 6.48
OVERALL_LENGTH = FACE_WIDTH + BOSS_LENGTH  # 17.28
# The outer edge is rounded in the photo; a sized 45-degree break is the lathe
# operation that reads the same and rule 7 prefers a chamfer to a radius.
BOSS_CHAMFER = 1.0

# Retention pin: a plain 1/8 in straight pin (stock drill rod) through the boss
# and the crankshaft, match-drilled at assembly with the pinion on its seat --
# a one-off shop cannot hit a 0.25-wall cross-hole on two parts separately and
# have the pin pass. The pinion's print therefore shows the hole at its station
# with a MATCH DRILL callout; the pin is the hole's own drill size (a driven
# fit, like the pinion arbor in its drums) and flush with the boss on both
# sides, so nothing stands proud to catch the mesh. It sits on the pinion's own
# local -X (azimuth 0, which keeps the side view's callout clean; the azimuth is
# physically free) at the boss's mid-length. The CLOCKING against the 64T
# tooth-in-gap seed is carried by the crankshaft's hole, whose entry point is
# turned by PIN_CLOCKING_DEG: the assembly places the pinion rot_z(-seed) and
# asserts that this constant IS its seed, so a re-derived mesh phase fails
# loud at import instead of drilling the shaft at the old angle.
PIN_HOLE_SPEC = HoleSpec("drilled_fractional", "1/8")
PIN_DIA = FRACTIONAL_DRILL_MM["1/8"]  # 3.175
PIN_LENGTH = BOSS_DIA  # flush both sides
PIN_STATION = FACE_WIDTH + BOSS_LENGTH / 2.0  # 14.04 from the toothed (south) face
PIN_CLOCKING_DEG = 13.703608450714796  # = build_drive_train_assembly.PINION_SEED_DEG
if PIN_STATION - PIN_DIA / 2.0 < FACE_WIDTH + 0.5:
    raise AssertionError("retention pin hole breaks into the pinion's tooth face")
if PIN_STATION + PIN_DIA / 2.0 > OVERALL_LENGTH - BOSS_CHAMFER - 0.5:
    raise AssertionError("retention pin hole reaches the boss end break")
# The hole callout on BOTH prints (the pinion's here; the crankshaft's reads
# its twin below) carries the matched fit the way rules 2 and 6 ask: the
# drill size and the mate by number on the feature callout (only the process
# prefix is typed; the size and THRU stay the native Hole Wizard callout's),
# and the acceptance -- which pin, how it fits, where it ends -- in the one
# note line rule 6 allows for match-drill at assembly. Three short prefix
# rows: a single 70-character row would run a 5:1 side view off the sheet.
CRANKSHAFT_NUMBER = _config.parts("crankshaft")["number"]
PINION_NUMBER = _config.parts("crank-pinion")["number"]
PIN_NUMBER = _config.parts("crank-pinion-pin")["number"]
PIN_HOLE_PROCESS = (
    f"MATCH DRILL AT ASSY WITH\nCRANKSHAFT {CRANKSHAFT_NUMBER}\n"
    f"{drill_process(PIN_HOLE_SPEC)}"
)
CRANKSHAFT_PIN_HOLE_PROCESS = (
    f"MATCH DRILL AT ASSY WITH\nCRANK PINION {PINION_NUMBER}\n"
    f"{drill_process(PIN_HOLE_SPEC)}"
)
PIN_FIT_NOTE = (
    f"PIN {PIN_NUMBER} IS A LIGHT DRIVE FIT IN THE MATCH-DRILLED HOLE,\n"
    "  FLUSH WITH THE BOSS ON BOTH SIDES."
)

# One roughness, on the one surface whose function depends on it: the bore is
# a size-toleranced fit onto the crankshaft, and a fit lives on the peaks as
# much as on the limits, so the bore carries the project's general machined
# grade. Nothing runs on the teeth or the faces -- they are as the title
# block's process row states (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = (
    SurfaceFinishControl("crank_pinion_bore", MACHINED_UM, CylinderFace(BORE_DIA)),
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_crank_pinion`` marks exactly these; ``draw_crank_pinion``
# keeps exactly their union across its per-view ``keep`` maps. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlankProfile": {"OutsideDia"},
    "GearBlank": {"FaceWidth"},
    "BossProfile": {"BossDia"},
    "Boss": {"OverallLength"},
    "BoreProfile": {"BoreDia"},
    "BossBreak": {"BossChamfer"},
    "PinStationPlane": {"PinStation"},
}

# --- Decimal places, authored ON THE PART ------------------------------------
#
# Policy rule 2: the places a dimension prints are part of the tolerance it
# claims, and the model owns both. ``build_crank_pinion`` applies this table
# natively (``_drawing_marks.apply_drawing_precision``) right after the drawing
# marks, so ``draw_crank_pinion`` imports each dimension verbatim and only reads
# ``GetPrimaryPrecision2()`` back off the sheet.
#
# The bore is the only fit on the part and prints three places with its own
# band. The outside diameter prints two with its own band. The face width is a
# free length between two turned faces: one place, so the title block's
# .X +/-0.8 is the band it claims -- and that is the band it needs, the 64T row
# it runs in being far wider than this face. The boss diameter, the overall
# length and the pin station are routine turned/drilled sizes at the general
# .XX grade: the boss is not a running surface (no band, no symbol), the
# overall length only has to leave the shaft end recessed (0.32 of room against
# +/-0.51 -- see the assembly's recess assert, which uses the nominal, and the
# match-drill that makes the station's own position immaterial to the fit).
# The end break is a deburr: one place.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlankProfile": {"OutsideDia": 2},
    "GearBlank": {"FaceWidth": 1},
    "BossProfile": {"BossDia": 2},
    "Boss": {"OverallLength": 2},
    "BoreProfile": {"BoreDia": 3},
    "BossBreak": {"BossChamfer": 1},
    "PinStationPlane": {"PinStation": 2},
}

# The drawing reads this flat view back off the sheet: a dimension name is
# unique across the features that expose one, and a marked dimension nobody
# authored places for would otherwise print SolidWorks' template default.
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("two features share a drawing-precision dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    _unmarked = sorted(set(_dimensions) - DRAWING_DIMENSIONS.get(_feature, set()))
    if _unmarked:
        raise AssertionError(
            f"{_feature}: precision authored for unmarked dimensions {_unmarked}"
        )


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


# Rule 6's gear-data block: the tooth system a cut-gear drawing cannot express
# as dimensions. Every generating number is REF -- the cutter and the depth of
# cut produce them, and the print's acceptance sizes are the three native
# dimensions above.
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f} (NONSTANDARD)"),
        ("MODULE (mm, REF)", f"{MODULE_MM:.3f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{PITCH_DIA:.2f}"),
        ("WHOLE DEPTH (mm, REF)", f"{WHOLE_DEPTH:.2f}"),
        (
            "CIRCULAR TOOTH THICKNESS (mm, REF)",
            f"{TRANSVERSE_CIRCULAR_TOOTH_THICKNESS:.3f}",
        ),
        ("TOOTH FORM", "SPUR INVOLUTE, FULL DEPTH"),
        ("MATES WITH", "CRANK DRIVE GEAR MHA-021, 64T"),
    ]
)

# Notes: the one part-specific process fact the title block gets wrong for a
# fine-pitch gear (drawing-simplicity-policy.md rule 6 -- a 0.25 break is a
# quarter of this tooth's whole depth) and the matched pin fit's acceptance.
# No digit here is a size: the callout owns the hole, the pin print the pin.
TOOTH_EDGE_NOTE = "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
DRAWING_NOTES = "\n".join((TOOTH_EDGE_NOTE, PIN_FIT_NOTE))
