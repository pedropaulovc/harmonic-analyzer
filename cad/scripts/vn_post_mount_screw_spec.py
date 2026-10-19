r"""Pure-data contract shared by the MHA-VN-031 post mount screw part and drawing.

MHA-VN-031 is MSC 40923906 (1/4-20 x 4 in slotted fillister) cut to
length: a MODIFIED purchased part.  Its head seats on the MHA-DT-005
counterbore floor and the shank threads through the MHA-DT-020 plate, which
swings over the base, so the cut end must never stand proud of the plate's
underside.  The cut length is therefore a real, model-owned dimension on the
sheet (drawing-simplicity-policy.md `How the repository implements the guidelines`), not a number in an installation note (drawing-guidelines.md rule 7 (notes: few, flagged, never a method), Main's
eye pass of warm-c486).  Across the printed post and plate bands no single
length both stays flush and keeps the engagement minimum (U27 check below),
so the length prints as a REFERENCE and each screw is cut to its own hole at
assembly.

The engagement this leaves falls short of drawing guideline rule 18 and is
pending the user's ruling in #1019. The sheet states it as a plain
fact, "ENGAGEMENT 0.90D MIN", the last line of the cut-length callout
(CUT_TO_FIT_CALLOUT), formatted from the floored worst case
POST_MOUNT_ENGAGEMENT_PRINTED; the asserts below still guard that value and
the nominal chain.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config
import dt_cone_pivot_post_spec as post
import dt_cone_swing_platform_spec as platform
import dt_post_mount_stack as mount_stack
from _fit_deviations import deviations
from _msc_40923906 import (
    FILLISTER_SIZE, SupplierSize,
    MODEL_STRAIGHT_SKIRT_MM, MODEL_SLOT_WIDTH_MM, MODEL_SLOT_DEPTH_MM,
    MODEL_THREAD_LENGTH_MM, MODEL_PLAIN_SHANK_MM, MODEL_DOME_HEIGHT_MM,
    MODEL_DOME_RADIUS_MM, MODEL_JUNCTION_FILLET_MM,
    SUPPLIER_HEAD_OD, SUPPLIER_HEAD_HEIGHT, SUPPLIER_STRAIGHT_SKIRT,
    SUPPLIER_SLOT_WIDTH, SUPPLIER_SLOT_DEPTH, SUPPLIER_STOCK_LENGTH,
    SUPPLIER_THREAD_LENGTH, SUPPLIER_THREAD,
)

SKU = "40923906"
THREAD = platform.POST_MOUNT_SPEC.size
THREAD_DIA_MM, STOCK_LENGTH_MM, HEAD_H_MM, _HEAD_DIA, _PITCH = FILLISTER_SIZE

# Source-stock references stay outside DRAWING_DIMENSIONS: these supplier
# limits are not the finished controls or the selected representative sizes.
# The source sheet uses a bounding box, not an invented supplier crown law.
# Crown curvature, thread runout, shank bands and tip shape are unspecified.
SUPPLIER_STOCK_CONFIGURATION = "SupplierMaxLimitEnvelope"
SUPPLIER_STOCK_FEATURE = "SupplierMaxLimitProfile"
SUPPLIER_STOCK_TITLE = "SUPPLIER MAX-LIMIT ENVELOPE / NOT REPRESENTATIVE SOLID"
SUPPLIER_STOCK_NOTE = (
    "PROFILE SCHEMATIC; CROWN CURVATURE UNSPECIFIED.\n"
    "SOURCE STOCK REFERENCES ONLY; FINISHED CONTROLS ON SHEET 1."
)
SUPPLIER_MODEL_NOTE = (
    "REPRESENTATIVE CROWN; SOURCE CURVATURE UNSPECIFIED.\n"
    "SOURCE LIMIT ENVELOPE IS SEPARATE."
)
_R = SUPPLIER_HEAD_OD.envelope_mm / 2.0
_H = SUPPLIER_HEAD_HEIGHT.envelope_mm
_S = SUPPLIER_STRAIGHT_SKIRT.envelope_mm
_W = SUPPLIER_SLOT_WIDTH.envelope_mm / 2.0
_D = SUPPLIER_SLOT_DEPTH.envelope_mm
_L = SUPPLIER_STOCK_LENGTH.envelope_mm
_T = SUPPLIER_THREAD_LENGTH.envelope_mm
# The thread identity defines a 1/4 major envelope, not a supplier shank band.
_r = THREAD_DIA_MM / 2.0
# One connected slot-plane stock profile. Every marked dimension below
# attaches to its actual vertices, not disconnected dimension witness lines.
SUPPLIER_PROFILE_MM = (
    (0.0, _R), (-_S, _R), (-_H, _R), (-_H, _W),
    (-_H + _D, _W), (-_H + _D, -_W), (-_H, -_W),
    (-_H, -_R), (-_S, -_R), (0.0, -_R), (0.0, -_r),
    (_L - _T, -_r), (_L, -_r), (_L, _r), (_L - _T, _r), (0.0, _r),
)
# Section boundaries are joined to the existing full-profile vertices:
# skirt/crown interface and factory thread termination.
SUPPLIER_PROFILE_SECTIONS = ((1, 8), (11, 14))


@dataclass(frozen=True)
class SupplierProfileDimension:
    name: str
    source: SupplierSize
    vertices: tuple[int, int]
    native_type: int
    presentation: str = "length"
    callout: str | None = None


SUPPLIER_PROFILE_DIMENSIONS = (
    SupplierProfileDimension("SupplierHeadOD", SUPPLIER_HEAD_OD, (2, 7), 12, "diameter"),
    SupplierProfileDimension("SupplierHeadHeight", SUPPLIER_HEAD_HEIGHT, (0, 2), 11),
    SupplierProfileDimension("SupplierStraightSkirt", SUPPLIER_STRAIGHT_SKIRT, (0, 1), 11),
    SupplierProfileDimension("SupplierSlotWidth", SUPPLIER_SLOT_WIDTH, (4, 5), 12),
    SupplierProfileDimension("SupplierSlotDepth", SUPPLIER_SLOT_DEPTH, (3, 4), 11),
    SupplierProfileDimension(
        "SupplierStockLength", SUPPLIER_STOCK_LENGTH, (15, 13), 11,
        callout="AS-SUPPLIED UNDER-HEAD LENGTH",
    ),
    SupplierProfileDimension(
        "SupplierThreadLength", SUPPLIER_THREAD_LENGTH, (14, 13), 11,
        callout=f"FACTORY PARTIAL THREAD\n{SUPPLIER_THREAD}",
    ),
)
SUPPLIER_STOCK_DIMENSIONS = {
    SUPPLIER_STOCK_FEATURE: {row.name for row in SUPPLIER_PROFILE_DIMENSIONS}
}

# Head seated on the MHA-DT-005 counterbore floor: the under-head face to the
# plate's top face, at the model's nominal post.
GRIP_MM = mount_stack.GRIP_MM
# The longest cut whose end is flush with the MHA-DT-020 underside.
FLUSH_LENGTH_MM = mount_stack.FLUSH_LENGTH_MM

# Model-owned drawing controls.  The cut length lives on a hidden reference
# sketch with ONE driving dimension (under-head face to cut end).  The cut
# end's break is a driving dimension of the deburr CUTTER's own profile,
# CutEndDeburrProfile -- the boss hook's StockDeburrProfile pattern -- not a
# hidden reference sketch: no view could import it from one.
# Dead under: a childless part-hidden CutEndBreakReference, shown in the
# part in memory (part_sketches_shown) around creating and curating the 10:1
# detail, targeted feature import (pms857-f543, f54309af5, drawing leaf log
# dt-logs/spring/pms857-f543-drawing-leaf.log, first xx: "tip detail break
# view is missing model dimensions: ['CutEndBreak']; available=[] from
# features=['CutEndBreakReference']").  Observed in that leaf, not claimed as
# the cause: the detail's hidden-sketch check read the sketch Visible=2
# (shown), children=0, and showed nothing further.  Untested: the per-view
# override on a detail, an entire-model import, other detail types.
# Later (b6552f13b, swmaker000008): no DETAIL view offers CutEndBreak at
# all -- 10:1 HLR, 10:1 HLV, 5:1, 2:1, before or after the Front's import
# all returned available=[] -- while a cropped 10:1 MODEL view imported
# it.  So the break prints in a cropped 10:1 model view of the tip.
CUT_LENGTH_SKETCH = "CutLengthReference"
CUT_LENGTH_DIMENSION = "CutLength"
CUT_END_BREAK_SKETCH = "CutEndDeburrProfile"
CUT_END_BREAK_DIMENSION = "CutEndBreak"
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    CUT_LENGTH_SKETCH: {CUT_LENGTH_DIMENSION},
    CUT_END_BREAK_SKETCH: {CUT_END_BREAK_DIMENSION},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    CUT_LENGTH_SKETCH: {CUT_LENGTH_DIMENSION: mount_stack.CUT_LENGTH_PLACES},
    CUT_END_BREAK_SKETCH: {CUT_END_BREAK_DIMENSION: 1},
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
REFERENCE_SKETCHES = (CUT_LENGTH_SKETCH, SUPPLIER_STOCK_FEATURE)
# Which view claims which marked dimension: the 1:1 Front view carries only
# the cut length; the break is claimed only by the cropped 10:1 tip view.
FRONT_VIEW_DIMENSIONS = {CUT_LENGTH_SKETCH: {CUT_LENGTH_DIMENSION}}
TIP_VIEW_DIMENSIONS = {CUT_END_BREAK_SKETCH: {CUT_END_BREAK_DIMENSION}}

# --- U27: can one fixed cut length serve every in-band post and plate? ---
# The printed bands, as the shop reads them off the title block: the post's
# overall height is a .X dimension, its counterbore depth a .XX callout, and
# the plate is 1/4 flat bar as supplied (U41) at its mill tolerance.
_GENERAL_1PL_MM = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
_GENERAL_2PL_MM = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
_POST_HEIGHT_PRINTED = round(post.BLOCK_HEIGHT, 1)
_CBORE_DEPTH_PRINTED = round(post.ATTACHMENT_CBORE_DEPTH, 2)
# Stock thickness and tap-entry breaks are owned by the mating platform.
PLATE_STOCK_BAND_MM = platform.PLATE_STOCK_BAND
# Two breaks eat thread, both held to a deburr, not the title block's 0.25:
# - the screw's cut end: a deburr (the shop hacksaws and files the burr),
#   0.1 max.  The model holds 0.1 as the nominal of its band; the sheet
#   prints the single limit "0.1 MAX" in a cropped 10:1 view of the tip, because
#   a 0.1 dimension at 1:1 is illegible and a printed +0/-0.1 band reads as
#   permitting no break at all (Main's MHA-VN-031 eye pass on #857).
POST_MOUNT_TAP_EDGE_BREAK = platform.POST_MOUNT_TAP_EDGE_BREAK
CUT_END_BREAK_MM = 0.1
CUT_END_BREAK_BAND = (0.0, -0.1)  # (upper, lower), the _fit_deviations convention
_break_lower, _break_upper = deviations(CUT_END_BREAK_BAND)
CUT_END_BREAK_MAX_MM = CUT_END_BREAK_MM + _break_upper
CUT_END_BREAK_MIN_MM = CUT_END_BREAK_MM + _break_lower
ENGAGEMENT_BREAKS_MM = POST_MOUNT_TAP_EDGE_BREAK + CUT_END_BREAK_MAX_MM
# Why the part needs its own limit: the title block's general "CHAMFER <C>
# MAX" is looser than the engagement stack below allows (the 0.90D worst
# case spends CUT_END_BREAK_MAX_MM), so the sheet must print the tighter max.
TITLE_BLOCK_CHAMFER_MAX_MM = float(_config.title_block("edge_break")["chamfer_max_mm"])
if not CUT_END_BREAK_MAX_MM < TITLE_BLOCK_CHAMFER_MAX_MM:
    raise ValueError(
        f"the cut-end break max {CUT_END_BREAK_MAX_MM} no longer tightens the "
        f"title block's chamfer {TITLE_BLOCK_CHAMFER_MAX_MM}: drop the local limit"
    )
# swTolMAX prints the dimension's NOMINAL followed by "MAX", so the printed
# limit is the band's maximum only while the nominal sits at the band's top.
CUT_END_BREAK_TOL_TYPE = 6  # swTolType_e.swTolMAX
if CUT_END_BREAK_MM != CUT_END_BREAK_MAX_MM:
    raise ValueError(
        f"CutEndBreak nominal {CUT_END_BREAK_MM} is not its band's max "
        f"{CUT_END_BREAK_MAX_MM}: a MAX-limit dimension would print the wrong limit"
    )
_BREAK_PLACES = DRAWING_PRECISION[CUT_END_BREAK_SKETCH][CUT_END_BREAK_DIMENSION]
if round(CUT_END_BREAK_MAX_MM, _BREAK_PLACES) != CUT_END_BREAK_MAX_MM:
    raise ValueError("the cut-end break max does not print at its places")
# What the tip view's dimension must read: the band's max at its places.
CUT_END_BREAK_TEXT = f"{CUT_END_BREAK_MAX_MM:.{_BREAK_PLACES}f} MAX"

# Counterbore floor above PlateTop (the post foot seats on it), both ends.
FLOOR_LOW_MM = (_POST_HEIGHT_PRINTED - _GENERAL_1PL_MM) - (
    _CBORE_DEPTH_PRINTED + _GENERAL_2PL_MM
)
FLOOR_HIGH_MM = (_POST_HEIGHT_PRINTED + _GENERAL_1PL_MM) - (
    _CBORE_DEPTH_PRINTED - _GENERAL_2PL_MM
)
PLATE_THIN_MM = platform.PLATE_THICKNESS - PLATE_STOCK_BAND_MM
PLATE_THICK_MM = platform.PLATE_THICKNESS + PLATE_STOCK_BAND_MM

# Pending ruling #1019 against rule 18: 0.90D minimum engagement.
MIN_ENGAGEMENT_DIAMETERS = 0.90
MIN_ENGAGEMENT_MM = MIN_ENGAGEMENT_DIAMETERS * THREAD_DIA_MM
# Corner 1, never proud: lowest floor on the thinnest plate.  A fixed length
# must not exceed this.
FIXED_LENGTH_FLUSH_MAX_MM = FLOOR_LOW_MM + PLATE_THIN_MM
# Corner 2, enough thread: highest floor, thickest plate.  A fixed length
# must reach at least this, after both edge breaks.  The thick plate does not
# cap it: cut flush there, the plate still holds the minimum.
FIXED_LENGTH_ENGAGEMENT_MIN_MM = FLOOR_HIGH_MM + MIN_ENGAGEMENT_MM + ENGAGEMENT_BREAKS_MM
if FIXED_LENGTH_ENGAGEMENT_MIN_MM > FLOOR_HIGH_MM + PLATE_THICK_MM:
    raise ValueError("the thick plate cannot hold 0.90D even when cut flush")
# No single length satisfies both corners at the current bands, so the shop
# cannot cut to a print band: each screw is cut to its
# own hole at assembly (MHA-DT-000), and the sheet prints the modelled length as
# a REFERENCE dimension with no band.  If the bands ever tighten enough for a
# fixed length to exist, this raises and the sheet should carry that band.
FIXED_CUT_LENGTH_EXISTS = FIXED_LENGTH_ENGAGEMENT_MIN_MM <= FIXED_LENGTH_FLUSH_MAX_MM
if FIXED_CUT_LENGTH_EXISTS:
    raise ValueError(
        "a fixed MHA-VN-031 cut length now fits both corners "
        f"({FIXED_LENGTH_ENGAGEMENT_MIN_MM:.2f}..{FIXED_LENGTH_FLUSH_MAX_MM:.2f}): "
        "print it with its band instead of a reference length"
    )

# The fit-to-hole acceptance (MHA-DT-000): each screw's cut end sits between
# flush with its own MHA-DT-020 underside and this much short of it, never proud.
# A band on the cut end's position relative to that underside, in the
# (upper, lower) _fit_deviations convention: upper 0 IS "never proud", lower is
# the most it may be cut short. The import-free mount stack owns the allowance;
# both part owners' printed-band engagement stacks spend all of it.
POST_SCREW_CUT_TO_FIT_BAND = (0.0, -platform.POST_SCREW_CUT_TO_FIT_SHORT)
_fit_lower, _fit_upper = deviations(POST_SCREW_CUT_TO_FIT_BAND)
if _fit_upper != 0.0:
    raise ValueError("the cut-to-fit band must top out flush: never proud")
POST_SCREW_CUT_TO_FIT_SHORT = -_fit_lower
# The acceptance prints where the part sheet delegates the cut: the CutLength
# callout, as well as the drive-train assembly step. The number is the band's,
# at the cut length's own places; a band the places would round is refused.
_FIT_PLACES = DRAWING_PRECISION[CUT_LENGTH_SKETCH][CUT_LENGTH_DIMENSION]
if _FIT_PLACES != mount_stack.CUT_LENGTH_PLACES:
    raise ValueError("post screw cut-length precision diverges from its nominal stack")
if round(POST_SCREW_CUT_TO_FIT_SHORT, _FIT_PLACES) != POST_SCREW_CUT_TO_FIT_SHORT:
    raise ValueError("the cut-to-fit allowance does not print at the cut length's places")

# The cut-to-fit nominal: MHA-VN-031's own length, applied by its trim (the
# shared size row stays the supplied screw).  It is the nominal post and
# plate's flush length less the middle of the fit-to-hole allowance, at the
# length's printed places, so the model is itself a cut the sheet accepts
# (Codex P2 on #857: a typed 86.0 ended 0.33 short, outside 0.3).
CUT_LENGTH_MM = mount_stack.CUT_LENGTH_MM
CUT_SHORT_NOMINAL_MM = FLUSH_LENGTH_MM - CUT_LENGTH_MM
if not 0.0 <= CUT_SHORT_NOMINAL_MM <= POST_SCREW_CUT_TO_FIT_SHORT:
    raise ValueError(
        f"MHA-VN-031 modelled length {CUT_LENGTH_MM} ends {CUT_SHORT_NOMINAL_MM:.3f} "
        f"short of the nominal MHA-DT-020 underside, outside flush to "
        f"{POST_SCREW_CUT_TO_FIT_SHORT} short"
    )

# The shortfall pending ruling #1019, cut to fit: unlike the fixed-length
# corner above, the floor drops out (each screw is cut to its own hole), so
# the plate limits it -- the thinnest stock, the full fit-to-hole allowance,
# and both breaks at their maximum. The platform's tap-exit deburr and this
# screw's cut-end break spend the same maximum in their respective stacks.
POST_MOUNT_ENGAGEMENT_WORST = round(
    platform.PLATE_THICKNESS
    - PLATE_STOCK_BAND_MM
    - POST_SCREW_CUT_TO_FIT_SHORT
    - POST_MOUNT_TAP_EDGE_BREAK
    - CUT_END_BREAK_MAX_MM,
    6,
)
POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS = POST_MOUNT_ENGAGEMENT_WORST / THREAD_DIA_MM
# A MIN never rounds up: floor to two places.
POST_MOUNT_ENGAGEMENT_PRINTED = (
    math.floor(POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS * 100.0) / 100.0
)
if POST_MOUNT_ENGAGEMENT_PRINTED < MIN_ENGAGEMENT_DIAMETERS:
    raise ValueError(
        f"MHA-VN-031 worst-case engagement {POST_MOUNT_ENGAGEMENT_WORST:.2f} "
        f"({POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS:.3f}D) is under "
        f"{MIN_ENGAGEMENT_DIAMETERS:.2f}D"
    )

# The callout states the acceptance AND the shortfall it leaves: the
# policy's named-exceptions section wants every affected sheet to state the
# exception (Codex P2 on #857, PRRT_kwDOPHDy386mOxdw).  Main's fleet ruling:
# the sheet states the FACT -- the worst-case engagement, floored above --
# never its label (no rule number, ruling id, EXCEPTION or ACCEPTED).
# Provenance stays here: the User's U37c/U41 ruling admits 0.90D under the
# 1.5D rule.  The wording follows S1's drive-train step ("ENGAGEMENT 0.90D
# MIN.").
# Pending exception ruling: MHA-VN-031 engagement (#1019).
CUT_TO_FIT_CALLOUT = (
    "CUT TO FIT AT ASSEMBLY\n"
    f"END FLUSH TO {POST_SCREW_CUT_TO_FIT_SHORT:.{_FIT_PLACES}f} SHORT\n"
    "OF MHA-DT-020 UNDERSIDE,\n"
    "NEVER PROUD,\n"
    f"ENGAGEMENT {POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D MIN"
)

# The model as built, on the nominal chain (its cut end is inside the
# acceptance, checked above), still holds the exception's minimum.
ENGAGEMENT_NOMINAL_MM = CUT_LENGTH_MM - GRIP_MM
if ENGAGEMENT_NOMINAL_MM < MIN_ENGAGEMENT_MM:
    raise ValueError(
        f"MHA-VN-031 nominal engagement {ENGAGEMENT_NOMINAL_MM:.2f} is under "
        f"{MIN_ENGAGEMENT_DIAMETERS:.2f}D"
    )

# --- The modification the shop makes (Main's ruling on the cut end) ---
# The original stock is represented at its upper length, with the inherited
# 45-degree tip convention (not a supplier tip specification). The source
# gives the actual partial-thread region; the selected skirt/slot are explicit
# midbands, not supplier nominals. The builder authors this source-corrected
# representative, then trims it at CutLength and breaks the new end with
# CutEndBreak. No shared-family full-thread ideal is used by this part.
if abs(STOCK_LENGTH_MM - 4.0 * 25.4) > 1e-9:
    raise ValueError("the MSC 40923906 row is not the supplied 4 in screw")
# Retained representative tip convention: 45 deg x 0.7P; no source tip size.
FACTORY_TIP_CHAMFER_MM = 0.7 * _PITCH
# Longest in-band seated assembly, cut flush, must still remove the supplied
# factory tip. This is stricter than checking the reference cut length alone.
LONGEST_FITTED_LENGTH_MM = FLOOR_HIGH_MM + PLATE_THICK_MM
STOCK_REACH_MARGIN_MM = (
    SUPPLIER_STOCK_LENGTH.lower_in * 25.4
    - FACTORY_TIP_CHAMFER_MM - LONGEST_FITTED_LENGTH_MM
)
if STOCK_REACH_MARGIN_MM <= 0.0:
    raise ValueError("MSC 40923906 cannot reach every printed post/plate corner")
MAJOR_RADIUS_MM = THREAD_DIA_MM / 2.0
# Representative UNC groove: root flat P/8 at the major radius less 0.75
# of the sharp-V height, 30 deg flanks. At radius r the groove's axial width
# is P/8 + (2/sqrt 3)(r - root), unchanged in the finished trimmed region.
_ROOT_RADIUS_MM = MAJOR_RADIUS_MM - 0.75 * (_PITCH * math.sqrt(3.0) / 2.0)


def _groove_per_mm_mm3(section_radius_mm: float) -> float:
    """Metal the groove removes per mm of height inside a section of this
    radius -- exact: a screw motion preserves volume, so at every radius the
    groove takes a width/pitch share of the circumference, whatever the
    phase (stock_anchor_geom.thread_groove_volume_per_mm_mm3's argument)."""
    if section_radius_mm <= _ROOT_RADIUS_MM:
        return 0.0
    slope = 2.0 / math.sqrt(3.0)
    offset = _PITCH / 8.0 - slope * _ROOT_RADIUS_MM

    def primitive(r: float) -> float:
        return 2.0 * math.pi / _PITCH * (offset * r * r / 2.0 + slope * r**3 / 3.0)

    return primitive(section_radius_mm) - primitive(_ROOT_RADIUS_MM)


def _metal_per_mm_mm3(section_radius_mm: float) -> float:
    return math.pi * section_radius_mm**2 - _groove_per_mm_mm3(section_radius_mm)


def _simpson(function, low: float, high: float, steps: int = 64) -> float:
    """Composite Simpson: exact here, every integrand being a cubic in height."""
    width = (high - low) / steps
    total = function(low) + function(high)
    for index in range(1, steps):
        total += (4 if index % 2 else 2) * function(low + index * width)
    return total * width / 3.0


def _trim_section_radius(height_above_tip_mm: float) -> float:
    return min(
        MAJOR_RADIUS_MM,
        MAJOR_RADIUS_MM - FACTORY_TIP_CHAMFER_MM + height_above_tip_mm,
    )


# Metal the trim removes: the factory tip (a threaded 45 deg cone) plus the
# plain threaded run up to the cut.  Split where the section radius reaches
# the root, so each piece is one cubic.
_ROOT_REACHED_MM = _ROOT_RADIUS_MM - (MAJOR_RADIUS_MM - FACTORY_TIP_CHAMFER_MM)
TRIM_REMOVED_MM3 = (
    _simpson(
        lambda h: _metal_per_mm_mm3(_trim_section_radius(h)), 0.0, _ROOT_REACHED_MM
    )
    + _simpson(
        lambda h: _metal_per_mm_mm3(_trim_section_radius(h)),
        _ROOT_REACHED_MM,
        FACTORY_TIP_CHAMFER_MM,
    )
    + _metal_per_mm_mm3(MAJOR_RADIUS_MM)
    * (STOCK_LENGTH_MM - FACTORY_TIP_CHAMFER_MM - CUT_LENGTH_MM)
)
# Metal the 45 deg break removes at the new end: between the cone and the
# major radius, over the break's height.
CUT_END_DEBURR_REMOVED_MM3 = _simpson(
    lambda h: _metal_per_mm_mm3(MAJOR_RADIUS_MM)
    - _metal_per_mm_mm3(MAJOR_RADIUS_MM - CUT_END_BREAK_MM + h),
    0.0,
    CUT_END_BREAK_MM,
)
if not 0.0 < _ROOT_REACHED_MM < FACTORY_TIP_CHAMFER_MM:
    raise ValueError("the factory tip no longer cuts below the thread root")
if STOCK_LENGTH_MM - FACTORY_TIP_CHAMFER_MM <= CUT_LENGTH_MM:
    raise ValueError("the cut no longer clears the factory tip")

# The whole removed tip and the new deburr remain inside the factory thread.
# Thus their existing analytic volumes remain valid after the partial-thread
# cutover. These guards refuse a future cut reaching into plain stock.
if not MODEL_PLAIN_SHANK_MM < CUT_LENGTH_MM - CUT_END_BREAK_MM:
    raise ValueError("the finished cut/deburr reaches outside the factory thread")
if not MODEL_PLAIN_SHANK_MM < FLOOR_LOW_MM:
    raise ValueError("the factory thread no longer reaches the lowest plate entry")
_PLAIN_TURNS = MODEL_PLAIN_SHANK_MM / _PITCH
if not math.isclose(_PLAIN_TURNS, round(_PLAIN_TURNS), rel_tol=0.0, abs_tol=1e-9):
    raise ValueError("the partial-thread boundary no longer preserves the tip phase")

# Stock mass contracts for the corrected representative. Head shape is the
# explicitly documented spherical convention, not supplier-exact curvature.
_HEAD_RADIUS = _HEAD_DIA / 2.0
MODEL_REVOLVED_VOLUME_MM3 = (
    math.pi * _HEAD_RADIUS**2 * MODEL_STRAIGHT_SKIRT_MM
    + math.pi * MODEL_DOME_HEIGHT_MM**2
    * (MODEL_DOME_RADIUS_MM - MODEL_DOME_HEIGHT_MM / 3.0)
    + math.pi * MAJOR_RADIUS_MM**2 * (STOCK_LENGTH_MM - FACTORY_TIP_CHAMFER_MM)
    + math.pi * FACTORY_TIP_CHAMFER_MM / 3.0 * (
        MAJOR_RADIUS_MM**2
        + MAJOR_RADIUS_MM * (MAJOR_RADIUS_MM - FACTORY_TIP_CHAMFER_MM)
        + (MAJOR_RADIUS_MM - FACTORY_TIP_CHAMFER_MM)**2
    )
)


def _slot_removed_volume_mm3() -> float:
    """Integrate the slot's strip through the selected cylindrical/cap head."""
    half_width = MODEL_SLOT_WIDTH_MM / 2.0
    floor = HEAD_H_MM - MODEL_SLOT_DEPTH_MM
    if not 0.0 < floor < MODEL_STRAIGHT_SKIRT_MM < HEAD_H_MM:
        raise ValueError("representative slot floor must sit inside the head skirt")

    def strip(radius: float) -> float:
        return 2.0 * (
            half_width * math.sqrt(max(0.0, radius**2 - half_width**2))
            + radius**2 * math.asin(min(1.0, half_width / radius))
        )

    center = HEAD_H_MM - MODEL_DOME_RADIUS_MM
    transition = center + math.sqrt(MODEL_DOME_RADIUS_MM**2 - half_width**2)
    cap_strip = _simpson(
        lambda y: strip(math.sqrt(MODEL_DOME_RADIUS_MM**2 - (y - center)**2)),
        MODEL_STRAIGHT_SKIRT_MM, transition, steps=256,
    )
    # Above transition the entire spherical cross-section lies inside the slot.
    def primitive(y):
        return math.pi * (MODEL_DOME_RADIUS_MM**2 * y - (y - center)**3 / 3.0)

    return (
        strip(_HEAD_RADIUS) * (MODEL_STRAIGHT_SKIRT_MM - floor)
        + cap_strip + primitive(HEAD_H_MM) - primitive(transition)
    )


MODEL_SLOT_REMOVED_MM3 = _slot_removed_volume_mm3()
MODEL_THREAD_REMOVED_MM3 = (
    _groove_per_mm_mm3(MAJOR_RADIUS_MM) * (MODEL_THREAD_LENGTH_MM - FACTORY_TIP_CHAMFER_MM)
    + _simpson(
        lambda h: _groove_per_mm_mm3(_trim_section_radius(h)),
        _ROOT_REACHED_MM, FACTORY_TIP_CHAMFER_MM,
    )
)
# The concave under-head P/10 round ADDS the annular square-minus-quarter-circle
# region. Pappus/integrating its radial shells gives the exact revolved volume:
# 2*pi*[R*f^2*(1-pi/4) + f^3*(5/6-pi/4)]. It is wholly above the distal
# factory-thread region and below the slot floor, so neither removal changes.
MODEL_JUNCTION_FILLET_ADDED_MM3 = 2.0 * math.pi * (
    MAJOR_RADIUS_MM * MODEL_JUNCTION_FILLET_MM**2 * (1.0 - math.pi / 4.0)
    + MODEL_JUNCTION_FILLET_MM**3 * (5.0 / 6.0 - math.pi / 4.0)
)
MODEL_STOCK_VOLUME_MM3 = (
    MODEL_REVOLVED_VOLUME_MM3 - MODEL_SLOT_REMOVED_MM3 - MODEL_THREAD_REMOVED_MM3
    + MODEL_JUNCTION_FILLET_ADDED_MM3
)

# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): no dimension, no tolerance, no installation sequence.  The cut
# length is the reference dimension above; its fit-to-hole acceptance is the
# CutLength callout (CUT_TO_FIT_CALLOUT), not a note.
MANUFACTURING_NOTES = (
    "DEBURR CUT END.\nUNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE.\n"
    + SUPPLIER_MODEL_NOTE
)
