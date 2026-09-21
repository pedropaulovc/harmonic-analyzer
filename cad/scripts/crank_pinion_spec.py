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
allows, with cutter inputs and derived diameters marked REF and the circular
tooth thickness carrying its own functional limit; nothing here restates the
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
from _hole_spec import FRACTIONAL_DRILL_MM, HoleSpec
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
# The mating MHA-021 gear's accepted base-tangent span has a +0/-0.020 mm
# band. Give this member the same one-sided tooth-control capability instead
# of exposing the pair to the title block's +/-0.13 mm: the nominal 0.150 mm
# tooth thinning then remains the minimum, while both members at minimum
# thickness produce 0.191 mm after converting MHA-021's normal-span band to
# transverse thickness. The exact-solid crossed-mesh study proves collision
# freedom down to 0.100 mm, so this leaves at least 0.050 mm of proven margin.
TOOTH_THICKNESS_UPPER_DEVIATION = 0.000
TOOTH_THICKNESS_LOWER_DEVIATION = -0.020

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
# claims (tolerance-policy.md step 6b). The feature callout names the mate and
# publishes the required diametral-clearance range; the dimensional band is
# DERIVED -- never a per-part number -- from that named fit class and the
# shaft's own published limits: bore_min = shaft_max + clearance_min,
# bore_max = shaft_min + clearance_max. Move either input and this moves with it.
BORE_DIA = 0.375 * MM_PER_IN  # 9.525 (3/8" crankshaft)
BORE_DIAMETRAL_CLEARANCE = tuple(
    _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
)
_CLEARANCE_MIN, _CLEARANCE_MAX = BORE_DIAMETRAL_CLEARANCE
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
# and crankshaft, match-drilled at assembly with the pinion on its seat. The
# drawing therefore governs the hole by its fit to the named pin, not by the
# model's nominal drill diameter: the shop drills undersize and reams until the
# actual pin is a light drive fit. The callout locates the operation at the
# boss mid-length and requires the fitted pin flush on both sides. The hole sits
# on the pinion's local -X; its clocking against the 64T tooth-in-gap seed is
# carried by the crankshaft hole, whose entry point is turned by
# PIN_CLOCKING_DEG. The assembly places the pinion rot_z(-seed) and asserts that
# this constant is its seed, so a re-derived mesh phase fails loud at import
# instead of drilling the shaft at the old angle.
PIN_HOLE_SPEC = HoleSpec("drilled_fractional", "1/8")
PIN_DIA = FRACTIONAL_DRILL_MM["1/8"]  # 3.175
PIN_LENGTH = BOSS_DIA  # flush both sides
PIN_STATION = FACE_WIDTH + BOSS_LENGTH / 2.0  # 14.04 from the toothed (south) face
PIN_CLOCKING_DEG = 13.703608450714796  # = build_drive_train_assembly.PINION_SEED_DEG
if PIN_STATION - PIN_DIA / 2.0 < FACE_WIDTH + 0.5:
    raise AssertionError("retention pin hole breaks into the pinion's tooth face")
if PIN_STATION + PIN_DIA / 2.0 > OVERALL_LENGTH - BOSS_CHAMFER - 0.5:
    raise AssertionError("retention pin hole reaches the boss end break")
# The matched-hole callout on both part records identifies both seated parts,
# the shared boss-mid-length operation and the actual fitted pin. It deliberately
# omits the modeled hole nominal: reaming to a functional acceptance governs,
# and the pin identity plus flush condition stay on the feature callout.
CRANKSHAFT_NUMBER = _config.parts("crankshaft")["number"]
PINION_NUMBER = _config.parts("crank-pinion")["number"]
PIN_NUMBER = _config.parts("crank-pinion-pin")["number"]
BORE_PROCESS_CALLOUT = "REAM THRU"
BORE_FIT_CALLOUT = "\n".join(
    (
        "BORE LIMITS GOVERN",
        f"MATE SHAFT {CRANKSHAFT_NUMBER}",
        f"(\N{DIAMETER SIGN}{crankshaft_spec.SHAFT_DIA:.3f} "
        f"+{_SHAFT_UPPER:.3f}/{_SHAFT_LOWER:.3f})",
        f"(DIA CLR {_CLEARANCE_MIN:.3f}-{_CLEARANCE_MAX:.3f} mm)",
    )
)
PIN_HOLE_PROCESS = "\n".join(
    (
        "MATCH DRILL AT BOSS MID-LENGTH",
        f"AT ASSY WITH CRANKSHAFT {CRANKSHAFT_NUMBER}",
        f"REAM TO FIT PIN {PIN_NUMBER}",
        "SEAT BY LIGHT HAND-HAMMER TAPS",
        "NOT REMOVABLE BY HAND",
        "FLUSH BOTH SIDES",
    )
)
CRANKSHAFT_PIN_HOLE_PROCESS = "\n".join(
    (
        f"MATCH DRILL AT ASSY WITH CRANK PINION {PINION_NUMBER}",
        "AT PINION BOSS MID-LENGTH",
        f"REAM TO FIT PIN {PIN_NUMBER}",
        "SEAT BY LIGHT HAND-HAMMER TAPS",
        "NOT REMOVABLE BY HAND",
        "FLUSH BOTH SIDES",
    )
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
# keeps exactly their union across its per-view ``keep`` maps. The
# ``BossProfile`` is a Right-plane revolve profile with construction-only
# witnesses for the tooth blank and bore. It therefore owns all four printed
# turned diameters/lengths on the side view without changing the solid:
# ``BossDia`` and ``OverallLength`` drive the revolve, while ``OutsideDia`` and
# ``BoreDia`` are equation-driven native reference dimensions attached to the
# matching axial extents (rule 2's reference-sketch allowance and rule 7's
# turned-part layout). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GearBlank": {"FaceWidth"},
    "BossProfile": {"OutsideDia", "BoreDia", "BossDia", "OverallLength"},
    "BossBreak": {"BossChamfer"},
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
# derived band. The outside diameter prints two at the general grade. The face
# width is a free length between two turned faces: one place, so the title
# block's .X +/-0.8 is the band it claims -- and that is the band it needs, the
# 64T row it runs in being far wider than this face. The boss diameter is a
# routine turned size at the general .XX grade: it is not a running surface
# (no band, no symbol). The match-drilled pin station is deliberately absent:
# its callout locates the shared operation at boss mid-length and the actual
# crankshaft/pinion stack sets it. The overall length is one place like the
# face width: it only has to leave the shaft end recessed inside the boss, a
# look, not a fit. The end break is a deburr: one place.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GearBlank": {"FaceWidth": 1},
    "BossProfile": {
        "OutsideDia": 2,
        "BoreDia": 3,
        "BossDia": 1,
        "OverallLength": 1,
    },
    "BossBreak": {"BossChamfer": 1},
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
# as ordinary view dimensions. Cutter inputs and derived diameters are REF;
# circular tooth thickness is the shop's controlling acceptance and carries
# the explicit one-sided pair-derived limit above.
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f} (NONSTANDARD)"),
        ("MODULE (mm, REF)", f"{MODULE_MM:.3f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{PITCH_DIA:.2f}"),
        ("WHOLE DEPTH (mm, REF)", f"{WHOLE_DEPTH:.2f}"),
        (
            "CIRCULAR TOOTH THICKNESS (mm)",
            f"{TRANSVERSE_CIRCULAR_TOOTH_THICKNESS:.3f} "
            f"+{TOOTH_THICKNESS_UPPER_DEVIATION:.3f}/"
            f"{TOOTH_THICKNESS_LOWER_DEVIATION:.3f}",
        ),
        ("TOOTH FORM", "SPUR INVOLUTE, FULL DEPTH"),
        ("MATES WITH", "CRANK DRIVE GEAR MHA-021, 64T"),
    ]
)

# The title block's normal 0.25 edge break is a quarter of this fine tooth's
# whole depth, so the print carries the one part-specific exception it needs.
# The nonstandard cutter geometry is already explicit in the gear-data block;
# it needs no duplicate method prohibition.
TOOTH_EDGE_NOTE = "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
DRAWING_NOTES = TOOTH_EDGE_NOTE
