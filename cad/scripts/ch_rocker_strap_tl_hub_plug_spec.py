r"""Pure-data contract for MHA-CH-13-TL-02, the rocker strap's hub plug.

Shop tooling for the rocker-strap sub-plate fixture MHA-CH-13-TL-00 (owner,
2026-11-17). A stepped plug seated in MHA-CH-13-TL-01's hub counterbore: its
pilot slips into the strap blank's reamed hub hole (MHA-CH-13) and locates
the blank on the counterbore; the hub screw MHA-CH-13-TL-VN-51 passes its
bore, through the washer MHA-CH-13-TL-VN-52, into the plate. Turned on the
manual lathe in one chucking.

- Body: matched slip fit in the counterbore. The counterbore is milled first
  (TL-01, Ø.500 at the title block's .XXX) and the body is turned to it, so
  its Ø.499 is a reference nominal and the stated diametral clearance is the
  requirement (drawing-guidelines.md rule 4, matched pairs).
- Pilot: explicit limits .3985-.3995, a locating fit in the strap's reamed
  .4000-.4005 hub hole (``ch_rocker_hub_fit.STRAP_HOLE_BAND``), clearance
  .0005-.0020. Every strap blank goes over the one plug, so the pilot cannot
  be matched to a hole; its band is the shop's turned-diameter row (.001
  wide), which LEARN machinist review r5 required (.3990-.3995 was .0005
  wide). The play it adds to the outline's position is checked below.
- Body length .170 and overall length .272 at the title block's .XXX: seated
  on the counterbore floor the shoulder stays below the plate's Z0 floor and
  the pilot's top below the strap's top (so the washer clamps the strap, not
  the plug) yet inside the hole; asserted below at the worst case of the
  printed bands. StrapFixtureCad 2026-11-17: the body length moved from the
  contract's .177 to .170 so the title-block band passes (at .177 the
  shoulder stood up to .002 above Z0).
- Bore: Ø.201 drilled through (#7 drill), clears the #10-32 hub screw
  (owner ruling 2026-11-23: "change the screw to #10-32. The sub-plate's
  tapped hole becomes #10-32 and the plug's bore .201 (#7 drill).",
  reversing 2026-11-17's "Use a 1/4-20 hub screw.", whose Ø.266 bore left
  a .064 wall under the pilot). The wall under the pilot is .096 at the
  worst case, over rule 17's .080 target, so the bore states no wall.

Frame: axis +Z, centred; z = 0 the body's bottom face (on the counterbore
floor, the Front Plane), the pilot's top at z = OVERALL_LENGTH.

Mirrored constants: the strap hole's nominal (``ch_rocker_strap_spec.
HOLE_DIA``) and thickness (``ch_rocker_arm_spec.ARM_THICKNESS``), the plate's
counterbore (``ch_rocker_strap_tl_sub_plate_spec``) and the plan's tape are
copied, not imported: the strap spec pulls the whole rocker-arm spec into this
part's closure, the plate spec would re-key the plug on every plate edit, and
no COM leaf may read a plan TOML. ``test_ch_rocker_strap_tl_hub_plug_drawing``
asserts each copy against its authority. ``ch_rocker_hub_fit`` is pure data
and is imported.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

import math

import _config
from _package_units import drawing_unit
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from ch_rocker_hub_fit import STRAP_HOLE_BAND

PART_NAME = "ch-rocker-strap-tl-hub-plug"
# Literal row names, so the recipe tracks exactly this registry row.
_ROW = _config.parts("ch-rocker-strap-tl-hub-plug")
if PART_NAME != "ch-rocker-strap-tl-hub-plug":
    raise AssertionError("PART_NAME and the registry row it reads disagree")
PART_NUMBER = str(_ROW["number"])
UNIT = drawing_unit("parts/ch-rocker-strap-tl-hub-plug", _ROW)
INCH = 25.4

STRAP_NUMBER = "MHA-CH-13"
PLATE_NUMBER = "MHA-CH-13-TL-01"
WASHER_NUMBER = "MHA-CH-13-TL-VN-52"
SCREW_NUMBER = "MHA-CH-13-TL-VN-51"

XX = printed_band_mm(2, unit=UNIT)
XXX = printed_band_mm(3, unit=UNIT)
DRILLED_PLUS = drilled_oversize_mm(unit=UNIT)

# --- Mirrored mates (asserted against their authorities in the pytest) ---
# MHA-CH-13-TL-01's hub counterbore, both at the title block's .XXX; its
# depth is from Z0, the plate floor the strap's tape lies on.
COUNTERBORE_DIA = 12.7  # .500
COUNTERBORE_DEPTH = 4.699  # .185
# MHA-CH-13's hub hole, reamed +.0005/.0000 on the .400 nominal.
STRAP_HOLE_DIA = 10.16  # .400
STRAP_HOLE_LIMITS = (
    STRAP_HOLE_DIA + STRAP_HOLE_BAND[1],
    STRAP_HOLE_DIA + STRAP_HOLE_BAND[0],
)
# MHA-CH-13's finished thickness .098 +/-.001, at its thinnest.
STRAP_THICKNESS_MIN = 2.4638
# MHA-CH-13's edges: half the surface-profile band (ch_rocker_arm_spec
# ``_PROFILE_HALF``, +/-.010), the outline's whole positional allowance.
STRAP_PROFILE_HALF = 0.254
# drawing-guidelines.md, What the shop holds: a turned diameter +/-.0005.
TURNED_DIA_ROW = 0.0127
# Plan tape_stack_mm and its band tape_stack_min_mm..tape_stack_max_mm: blue
# painter's tape on both faces with CA glue between (owner ruling
# 2026-11-23), .011 nominal, every bond miked into .009-.013.
TAPE_STACK = 0.28
TAPE_MIN = 0.23
TAPE_MAX = 0.33
# The #10-32 hub screw's major diameter, the bore's clearance target.
SCREW_MAJOR_DIA = 4.826  # .190

# --- The plug ---
BODY_DIA = 12.6746  # .499 REF, turned to the measured counterbore
# Diametral clearance of the body in the measured counterbore (lower, upper).
BODY_CLEARANCE = (0.0127, 0.0381)  # .0005-.0015
BODY_LENGTH = 4.318  # .170
OVERALL_LENGTH = 6.9088  # .272
PILOT_LIMITS = (10.1219, 10.1473)  # .3985-.3995
# The model sits mid-band; the sheet prints the two limits (swTolLIMIT).
PILOT_DIA = (PILOT_LIMITS[0] + PILOT_LIMITS[1]) / 2.0
BORE_DIA = 5.1054  # .201, #7 drill
CHAMFER = 0.508  # .02 x 45 deg on the pilot's top edge
PILOT_LENGTH = OVERALL_LENGTH - BODY_LENGTH

LENGTH_PLACES = 3
BODY_DIA_PLACES = 3
BORE_PLACES = 3
PILOT_PLACES = 4
CHAMFER_PLACES = 2

for _value, _places in (
    (BODY_DIA, BODY_DIA_PLACES),
    (BODY_LENGTH, LENGTH_PLACES),
    (OVERALL_LENGTH, LENGTH_PLACES),
    (BORE_DIA, BORE_PLACES),
    (CHAMFER, CHAMFER_PLACES),
    (PILOT_LIMITS[0], PILOT_PLACES),
    (PILOT_LIMITS[1], PILOT_PLACES),
    (COUNTERBORE_DIA, 3),
    (COUNTERBORE_DEPTH, 3),
):
    _step = INCH * 10.0**-_places
    if abs(round(_value / _step) * _step - _value) > 1e-9:
        raise AssertionError(f"{_value} mm is off its {_places}-place inch grid")


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text, no leading zero."""
    return f"{value_mm / INCH:.{places}f}".removeprefix("0")


def floor_text(value_mm: float, places: int) -> str:
    """A stated minimum, never rounded up past the derived value."""
    scaled = math.floor(round(value_mm / INCH * 10**places, 6))
    return inch_text(scaled / 10**places * INCH, places)


# The body's nominal sits inside its own clearance window on the nominal
# counterbore, so the reference nominal is a size the fit can reach.
if not BODY_CLEARANCE[0] < COUNTERBORE_DIA - BODY_DIA < BODY_CLEARANCE[1]:
    raise AssertionError("the body's REF nominal is outside its clearance window")

# The pilot in the reamed hub hole: clear at both ends.
PILOT_CLEARANCE = (
    round(STRAP_HOLE_LIMITS[0] - PILOT_LIMITS[1], 6),
    round(STRAP_HOLE_LIMITS[1] - PILOT_LIMITS[0], 6),
)
if not PILOT_CLEARANCE[0] > 0.0:
    raise AssertionError(f"the pilot can bind in the hub hole: {PILOT_CLEARANCE}")
if not PILOT_LIMITS[1] < BODY_DIA - 2.0 * XXX:
    raise AssertionError("the pilot does not step down from the body")
# The pilot's band is one the lathe holds by cutting to a number: no
# narrower than the shop's turned-diameter row (drawing-guidelines.md, What
# the shop holds: +/-.0005, .001 wide). LEARN machinist review r5 refused
# .3990-.3995 (.0005 wide): a band under the row needs a fit route, and a
# matched pilot cannot serve every strap blank.
if PILOT_LIMITS[1] - PILOT_LIMITS[0] < 2.0 * TURNED_DIA_ROW - 1e-9:
    raise AssertionError("the pilot's band is narrower than the shop's turned row")
# What the plug's play costs the strap's outline: the hub hole's centre can
# sit off the counterbore's by half the pilot's largest clearance plus half
# the body's in the counterbore, at most .00175 (0.044 mm). Held to a fifth
# of the strap edges' profile half-band (+/-.010), so the outline program's
# own error keeps the rest.
HUB_LOCATING_ERROR_MAX = (PILOT_CLEARANCE[1] + BODY_CLEARANCE[1]) / 2.0
HUB_LOCATING_BUDGET = 0.2 * STRAP_PROFILE_HALF
if HUB_LOCATING_ERROR_MAX > HUB_LOCATING_BUDGET:
    raise AssertionError(
        f"the plug lets the strap shift {HUB_LOCATING_ERROR_MAX:.3f} mm, over "
        f"its {HUB_LOCATING_BUDGET:.3f} mm share of the outline's profile band"
    )

# Seated on the counterbore floor (plate frame: Z0 the floor the tape lies
# on, +Z up), at the worst case of the printed bands.
SEAT_Z = -COUNTERBORE_DEPTH  # nominal
_SEAT_Z_RANGE = (-COUNTERBORE_DEPTH - XXX, -COUNTERBORE_DEPTH + XXX)
SHOULDER_Z_MAX = _SEAT_Z_RANGE[1] + BODY_LENGTH + XXX
PILOT_TOP_Z = SEAT_Z + OVERALL_LENGTH  # nominal, 2.21 above Z0
PILOT_TOP_Z_RANGE = (
    _SEAT_Z_RANGE[0] + OVERALL_LENGTH - XXX,
    _SEAT_Z_RANGE[1] + OVERALL_LENGTH + XXX,
)
# The strap's underside is the stack's top; its top the stack plus the strap.
STRAP_UNDERSIDE_Z_MAX = TAPE_MAX
STRAP_TOP_Z_MIN = TAPE_MIN + STRAP_THICKNESS_MIN
if not SEAT_Z + BODY_LENGTH < 0.0:
    raise AssertionError("the plug's shoulder stands above Z0 at nominal")
if not SHOULDER_Z_MAX < 0.0:
    raise AssertionError(
        f"the plug's shoulder can stand {SHOULDER_Z_MAX:.3f} mm above Z0"
    )
if not PILOT_TOP_Z_RANGE[1] < STRAP_TOP_Z_MIN:
    raise AssertionError("the pilot can stand proud of the strap: the washer clamps it")
# The pilot's cylindrical land (under the chamfer) still reaches into the
# hole past the strap's underside.
PILOT_LAND_Z_MIN = PILOT_TOP_Z_RANGE[0] - (CHAMFER + XX)
if not PILOT_LAND_Z_MIN > STRAP_UNDERSIDE_Z_MAX:
    raise AssertionError("the pilot's land does not reach the strap's hub hole")
if not CHAMFER + XX < PILOT_LENGTH - XXX:
    raise AssertionError("the pilot chamfer eats the whole pilot")

# The bore clears the screw; the wall under the pilot at the worst case
# (smallest pilot, largest drilled bore) holds rule 17's floor and, were it
# under its target, would be stated on the bore (rule 20).
if not BORE_DIA > SCREW_MAJOR_DIA:
    raise AssertionError("the bore does not clear the #10 hub screw")
WALL_MIN = (PILOT_LIMITS[0] - (BORE_DIA + DRILLED_PLUS)) / 2.0
if WALL_MIN < WALL_FLOOR_MM:
    raise AssertionError(f"pilot wall {WALL_MIN:.3f} mm under the rule-17 floor")
WALL_STATED = WALL_MIN < WALL_TARGET_MM
WALL_TEXT = f"WALL {floor_text(WALL_MIN, 3)} MIN"

# --- Drawing contract: the PART owns places, bands, references and callouts.
BODY_PROFILE = "BodyProfile"
BODY = "Body"
PILOT_PROFILE = "PilotProfile"
PILOT = "Pilot"
PILOT_CHAMFER = "PilotChamfer"
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    BODY_PROFILE: {"BodyDia", "BoreDia"},
    BODY: {"BodyLength"},
    PILOT_PROFILE: {"PilotDia"},
    PILOT: {"OverallLength"},
    PILOT_CHAMFER: {"ChamferSize"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    BODY_PROFILE: {"BodyDia": BODY_DIA_PLACES, "BoreDia": BORE_PLACES},
    BODY: {"BodyLength": LENGTH_PLACES},
    PILOT_PROFILE: {"PilotDia": PILOT_PLACES},
    PILOT: {"OverallLength": LENGTH_PLACES},
    PILOT_CHAMFER: {"ChamferSize": CHAMFER_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()
}
for _feature, _names in DRAWING_DIMENSIONS.items():
    if set(DRAWING_PRECISION[_feature]) != _names:
        raise AssertionError(
            f"{_feature}: every marked dimension needs authored places"
        )
# The body's nominal is a reference: the stated clearance governs.
REFERENCE_DIMENSIONS: dict[str, frozenset[str]] = {
    BODY_PROFILE: frozenset({"BodyDia"}),
}

BODY_CLEARANCE_TEXT = (
    f"{inch_text(BODY_CLEARANCE[0], 4)}-{inch_text(BODY_CLEARANCE[1], 4)}"
)
PILOT_CLEARANCE_TEXT = (
    f"{inch_text(PILOT_CLEARANCE[0], 4)}-{inch_text(PILOT_CLEARANCE[1], 4)}"
)
# Callouts the PART authors below each value (the drawing imports and reads
# them back; a drawing-side SetText can write through to the part, #1942).
# Rule 4: the body names its matched mate and the clearance that governs; the
# pilot names its fit and mate with the clearance its limits give as REF.
# Rule 3: each three-place length names what it holds.
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    BODY_PROFILE: {
        "BodyDia": (
            "TURN TO MEASURED COUNTERBORE\n"
            f"{BODY_CLEARANCE_TEXT} DIAMETRAL CLEARANCE ON {PLATE_NUMBER}"
        ),
        "BoreDia": "DRILL THRU" + (f"\n{WALL_TEXT}" if WALL_STATED else ""),
    },
    BODY: {"BodyLength": f"SHOULDER BELOW\n{PLATE_NUMBER} FLOOR"},
    PILOT_PROFILE: {
        "PilotDia": (
            f"LOCATING FIT IN {STRAP_NUMBER} HUB HOLE\n"
            f"(CLEARANCE {PILOT_CLEARANCE_TEXT} REF)"
        ),
    },
    PILOT: {"OverallLength": f"PILOT TOP BELOW\n{STRAP_NUMBER} TOP FACE"},
    PILOT_CHAMFER: {"ChamferSize": "X 45\u00b0"},
}
DIMENSION_CALLOUTS_BY_NAME: dict[str, str] = {
    name: text
    for callouts in DIMENSION_CALLOUTS.values()
    for name, text in callouts.items()
}
if set(DIMENSION_CALLOUTS_BY_NAME) != set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every marked hub plug dimension carries its callout")

# Analytic volume (mm^3): two annuli and the 45 deg ring off the pilot's top
# outside edge (a triangle of leg c revolved at radius R - c/3).
V_BODY = math.pi / 4.0 * (BODY_DIA**2 - BORE_DIA**2) * BODY_LENGTH
V_PILOT = math.pi / 4.0 * (PILOT_DIA**2 - BORE_DIA**2) * PILOT_LENGTH
V_CHAMFER = math.pi * CHAMFER**2 * (PILOT_DIA / 2.0 - CHAMFER / 3.0)
V_PLUG = V_BODY + V_PILOT - V_CHAMFER

ISOMETRIC_VIEW_SCALE = (2, 1)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
