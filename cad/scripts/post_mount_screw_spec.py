r"""Pure-data contract shared by the MHA-142 post mount screw part and drawing.

MHA-142 is MSC 40923898 (1/4-20 x 3-1/2 slotted fillister, U37c) cut to
length: a MODIFIED purchased part.  Its head seats on the MHA-016
counterbore floor and the shank threads through the MHA-091 plate, which
swings over the base, so the cut end must never stand proud of the plate's
underside.  The cut length is therefore a real, model-owned dimension on the
sheet (policy rule 2), not a number in an installation note (rule 6, Main's
eye pass of warm-c486).  Across the printed post and plate bands no single
length both stays flush and keeps the engagement minimum (U27 check below),
so the length prints as a REFERENCE and each screw is cut to its own hole at
assembly.

The engagement this leaves is the named rule-12 exception in
``cad/docs/drawing-simplicity-policy.md``.  The sheet states it as a plain
fact, "ENGAGEMENT 0.90D MIN", the last line of the cut-length callout
(CUT_TO_FIT_CALLOUT), formatted from the floored worst case
POST_MOUNT_ENGAGEMENT_PRINTED; the asserts below still guard that value and
the nominal chain.
"""

from __future__ import annotations

import math

import _config
import cone_pivot_post_spec as post
import cone_swing_platform_spec as platform
from _fit_limits import deviations
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

SKU = "40923898"
THREAD_DIA_MM, STOCK_LENGTH_MM, HEAD_H_MM, _HEAD_DIA, _PITCH = FILLISTER_SIZES[SKU]
# The cut-to-fit nominal: MHA-142's own length, applied by its trim.  The
# shared size row stays the supplied screw.
CUT_LENGTH_MM = 86.0

# Head seated on the MHA-016 counterbore floor: the under-head face to the
# plate's top face, at the model's nominal post.
GRIP_MM = post.BLOCK_HEIGHT - post.ATTACHMENT_CBORE_DEPTH
# The longest cut whose end is flush with the MHA-091 underside.
FLUSH_LENGTH_MM = GRIP_MM + platform.PLATE_THICKNESS

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
    CUT_LENGTH_SKETCH: {CUT_LENGTH_DIMENSION: 1},
    CUT_END_BREAK_SKETCH: {CUT_END_BREAK_DIMENSION: 1},
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
REFERENCE_SKETCHES = (CUT_LENGTH_SKETCH,)
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
# U41: 1/4 plate as supplied.  Integ carries the same mill band as
# cone_swing_platform_spec.PLATE_STOCK_BAND; this branch predates it.
PLATE_STOCK_BAND_MM = 0.13
# Two breaks eat thread, both held to a deburr, not the title block's 0.25
# (Main's engagement ruling on #857):
# - the MHA-091 tap's entry: deburr only, 0.1 max.  Integ carries this as
#   cone_swing_platform_spec.POST_MOUNT_TAP_EDGE_BREAK (the platform's local
#   override); this branch predates it, and integ dedupes it to one copy.
# - the screw's cut end: a deburr (the shop hacksaws and files the burr),
#   0.1 max.  The model holds 0.1 as the nominal of its band; the sheet
#   prints the single limit "0.1 MAX" in a cropped 10:1 view of the tip, because
#   a 0.1 dimension at 1:1 is illegible and a printed +0/-0.1 band reads as
#   permitting no break at all (Main's MHA-142 eye pass on #857).
POST_MOUNT_TAP_EDGE_BREAK = 0.1
CUT_END_BREAK_MM = 0.1
CUT_END_BREAK_BAND = (0.0, -0.1)  # (upper, lower), the _fit_limits convention
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

# The named rule-12 exception (User, U37c/U41): 0.90D minimum engagement.
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
# No single length satisfies both corners (84.89 vs 87.21 at the current
# bands), so the shop cannot cut to a print band: each screw is cut to its
# own hole at assembly (MHA-A03), and the sheet prints the modelled length as
# a REFERENCE dimension with no band.  If the bands ever tighten enough for a
# fixed length to exist, this raises and the sheet should carry that band.
FIXED_CUT_LENGTH_EXISTS = FIXED_LENGTH_ENGAGEMENT_MIN_MM <= FIXED_LENGTH_FLUSH_MAX_MM
if FIXED_CUT_LENGTH_EXISTS:
    raise ValueError(
        "a fixed MHA-142 cut length now fits both corners "
        f"({FIXED_LENGTH_ENGAGEMENT_MIN_MM:.2f}..{FIXED_LENGTH_FLUSH_MAX_MM:.2f}): "
        "print it with its band instead of a reference length"
    )

# The fit-to-hole acceptance (MHA-A03): each screw's cut end sits between
# flush with its own MHA-091 underside and this much short of it, never proud.
# A band on the cut end's position relative to that underside, in the
# (upper, lower) _fit_limits convention: upper 0 IS "never proud", lower is
# the most it may be cut short.  POST_SCREW_CUT_TO_FIT_SHORT is the one copy
# of the allowance: integ's platform engagement stack imports it, and the
# worst-case engagement below spends all of it.
POST_SCREW_CUT_TO_FIT_BAND = (0.0, -0.3)
_fit_lower, _fit_upper = deviations(POST_SCREW_CUT_TO_FIT_BAND)
if _fit_upper != 0.0:
    raise ValueError("the cut-to-fit band must top out flush: never proud")
POST_SCREW_CUT_TO_FIT_SHORT = -_fit_lower
# No MHA-A03 procedure sheet exists, so the acceptance prints where the part
# sheet delegates the cut: the CutLength dimension's callout (Codex P1 on
# #857).  The number is the band's, at the cut length's own places; a band
# the places would round is refused rather than printed wrong.
_FIT_PLACES = DRAWING_PRECISION[CUT_LENGTH_SKETCH][CUT_LENGTH_DIMENSION]
if round(POST_SCREW_CUT_TO_FIT_SHORT, _FIT_PLACES) != POST_SCREW_CUT_TO_FIT_SHORT:
    raise ValueError("the cut-to-fit allowance does not print at the cut length's places")

# The named exception's worst case, cut to fit: unlike the fixed-length
# corner above, the floor drops out (each screw is cut to its own hole), so
# the plate limits it -- the thinnest stock, the full fit-to-hole allowance,
# and both breaks at their maximum.  Mirrors integ's
# cone_swing_platform_spec.POST_MOUNT_ENGAGEMENT_WORST, which dedupes to this.
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
        f"MHA-142 worst-case engagement {POST_MOUNT_ENGAGEMENT_WORST:.2f} "
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
CUT_TO_FIT_CALLOUT = (
    "CUT TO FIT AT ASSEMBLY\n"
    f"END FLUSH TO {POST_SCREW_CUT_TO_FIT_SHORT:.{_FIT_PLACES}f} SHORT\n"
    "OF MHA-091 UNDERSIDE,\n"
    "NEVER PROUD,\n"
    f"ENGAGEMENT {POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D MIN"
)

# The model as built, on the nominal chain: the reference length never
# stands proud, and still holds the exception's minimum.
if CUT_LENGTH_MM > FLUSH_LENGTH_MM:
    raise ValueError(
        f"MHA-142 modelled length {CUT_LENGTH_MM} stands proud of the nominal "
        f"MHA-091 underside ({FLUSH_LENGTH_MM:.2f})"
    )
ENGAGEMENT_NOMINAL_MM = CUT_LENGTH_MM - GRIP_MM
if ENGAGEMENT_NOMINAL_MM < MIN_ENGAGEMENT_MM:
    raise ValueError(
        f"MHA-142 nominal engagement {ENGAGEMENT_NOMINAL_MM:.2f} is under "
        f"{MIN_ENGAGEMENT_DIAMETERS:.2f}D"
    )

# --- The modification the shop makes (Main's ruling on the cut end) ---
# The supplied screw is 3-1/2 in, factory-chamfered at its tip.  Cutting it to
# fit removes that tip, so the 0.1 break at the new end is MHA-142's own
# modification, not a property of the fillister family: the builder builds
# the stock screw at its supplied length (STOCK_LENGTH_MM, the shared
# recipe's row), then trims it at CutLength and breaks the new end with
# CutEndBreak.
if abs(STOCK_LENGTH_MM - 3.5 * 25.4) > 1e-9:
    raise ValueError("the MSC 40923898 row is not the supplied 3-1/2 in screw")
# The family's factory tip: 45 deg x 0.7P (diag_mcmaster_fillister's law).
FACTORY_TIP_CHAMFER_MM = 0.7 * _PITCH
MAJOR_RADIUS_MM = THREAD_DIA_MM / 2.0
# The family's thread groove (same module): root flat P/8 at the major radius
# less 0.75 of the sharp-V height, 30 deg flanks.  At radius r the groove's
# axial width is P/8 + (2/sqrt 3)(r - root).
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

# Rule 6: no dimension, no tolerance, no installation sequence.  The cut
# length is the reference dimension above; its fit-to-hole acceptance is the
# CutLength callout (CUT_TO_FIT_CALLOUT), not a note.
MANUFACTURING_NOTES = (
    "DEBURR CUT END.\nUNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE."
)
