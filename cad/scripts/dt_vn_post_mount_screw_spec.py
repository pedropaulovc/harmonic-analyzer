r"""Pure-data contract shared by the MHA-DT-VN-61 post mount screw part and drawing.

MHA-DT-VN-61 is MSC 40923906 (1/4-20 x 4 in slotted fillister) cut to
length: a MODIFIED purchased part.  Its head seats on the MHA-DT-05
counterbore floor and the shank threads through the MHA-DT-20 plate, which
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
from _package_units import drawing_unit
from _printed_tolerance import edge_break_chamfer_mm, printed_deviations
import dt_cone_swing_platform_spec as platform
import dt_post_mount_stack as mount_stack
from _fit_deviations import deviations
from _msc_40923906 import (
    FILLISTER_SIZE,
    SupplierSize,
    SUPPLIER_HEAD_OD,
    SUPPLIER_HEAD_HEIGHT,
    SUPPLIER_STRAIGHT_SKIRT,
    SUPPLIER_SLOT_WIDTH,
    SUPPLIER_SLOT_DEPTH,
    SUPPLIER_STOCK_LENGTH,
    SUPPLIER_THREAD_LENGTH,
    SUPPLIER_THREAD,
    SUPPLIER_PRECISION as SUPPLIER_PRECISION,
    SUPPLIER_SOURCE as SUPPLIER_SOURCE,
)

SKU = "40923906"
# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/dt-vn-post-mount-screw", _config.parts("dt-vn-post-mount-screw"))
MM_PER_IN = 25.4


def inch_text(value_mm: float, places: int) -> str:
    """An mm length as ASME decimal-inch text (no leading zero)."""
    text = f"{value_mm / MM_PER_IN:.{places}f}"
    return text[1:] if text.startswith("0.") else text


def _on_inch_grid(value_mm: float, places: int) -> bool:
    scaled = value_mm / MM_PER_IN * 10**places
    return abs(scaled - round(scaled)) < 1e-6
THREAD = platform.POST_MOUNT_SPEC.size
THREAD_DIA_MM, STOCK_LENGTH_MM, HEAD_H_MM, _HEAD_DIA, _PITCH = FILLISTER_SIZE

# Source evidence: C:/src/dt-logs/vn-supplier-dimensions-20261019/
# msc-40923906-supplied.png and msc-fit-reconciliation.md. The historical
# comparison SVG's BEFORE column describes this unchanged solid; its proposed
# AFTER geometry is not authorized by this reference-only port.
#
# Current catalogue-family recipe: skirt .189600 in (4.815840 mm), slot width
# .055890 in (1.419606 mm), depth .083835 in (2.129409 mm). These are outside
# the source's skirt/slot bands and are NOT relabelled with supplier limits on
# the installed surfaces.  The recipe threads the whole shank; this part
# restores the plain shank above the source's 1.500 in thread
# (FACTORY_THREAD_START_MM), so both sheets show the thread MSC supplies.
# Head OD .414, height .237 and original length 4.000 match source upper limits.
SUPPLIER_STOCK_CONFIGURATION = "SupplierMaxLimitEnvelope"
SUPPLIER_STOCK_FEATURE = "SupplierMaxLimitProfile"
# Sheet 2's one caption: the views are the supplier's limits, for reference
# only; sheet 1 alone controls the finished screw.
SUPPLIER_STOCK_TITLE = (
    "SUPPLIER MAXIMUM-LIMIT ENVELOPE\n"
    "REFERENCE ONLY"
)
_R = SUPPLIER_HEAD_OD.envelope_mm / 2.0
_H = SUPPLIER_HEAD_HEIGHT.envelope_mm
_S = SUPPLIER_STRAIGHT_SKIRT.envelope_mm
_W = SUPPLIER_SLOT_WIDTH.envelope_mm / 2.0
_D = SUPPLIER_SLOT_DEPTH.envelope_mm
_L = SUPPLIER_STOCK_LENGTH.envelope_mm
_T = SUPPLIER_THREAD_LENGTH.envelope_mm
# Thread identity supplies a major envelope, NOT an unspecified shank band.
_r = THREAD_DIA_MM / 2.0
# One connected slot-plane bounding profile, not a guessed crown or fake body.
# Every supplier dimension attaches to the diagram's actual profile vertices.
SUPPLIER_PROFILE_MM = (
    (0.0, _R), (-_S, _R), (-_H, _R), (-_H, _W),
    (-_H + _D, _W), (-_H + _D, -_W), (-_H, -_W),
    (-_H, -_R), (-_S, -_R), (0.0, -_R), (0.0, -_r),
    (_L - _T, -_r), (_L, -_r), (_L, _r), (_L - _T, _r), (0.0, _r),
)
SUPPLIER_PROFILE_SECTIONS = ((1, 8), (11, 14))


@dataclass(frozen=True)
class SupplierProfileDimension:
    name: str
    source: SupplierSize | None
    vertices: tuple[int, int]
    native_type: int
    presentation: str = "length"
    callout: str | None = None
    nominal_mm: float | None = None

    @property
    def expected_mm(self) -> float:
        if self.source is not None:
            return self.source.envelope_mm
        if self.nominal_mm is None:
            raise ValueError(f"{self.name}: reference has no source extent or nominal size")
        return self.nominal_mm

    @property
    def deviations_mm(self) -> tuple[float, float] | None:
        return None if self.source is None else self.source.deviations_mm


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
        callout="FACTORY PARTIAL THREAD",
    ),
)
# Extra nominal-designation carrier, NOT an eighth printed source size/band.
# The diagram's distal end spans the existing 1/4-inch nominal major envelope;
# this reference measures those diagram vertices, never the installed helix.
SUPPLIER_THREAD_MAJOR_DIMENSION = SupplierProfileDimension(
    "SupplierThreadMajor", None, (12, 13), 12, "diameter",
    callout=SUPPLIER_THREAD,
    nominal_mm=THREAD_DIA_MM,
)
SUPPLIER_REFERENCE_DIMENSIONS = (
    *SUPPLIER_PROFILE_DIMENSIONS,
    SUPPLIER_THREAD_MAJOR_DIMENSION,
)
SUPPLIER_STOCK_DIMENSIONS = {
    SUPPLIER_STOCK_FEATURE: {row.name for row in SUPPLIER_REFERENCE_DIMENSIONS}
}

# Head seated on the MHA-DT-05 counterbore floor: the under-head face to the
# plate's top face, at the model's nominal post.
GRIP_MM = mount_stack.GRIP_MM
# The longest cut whose end is flush with the MHA-DT-20 underside.
FLUSH_LENGTH_MM = mount_stack.FLUSH_LENGTH_MM

# Model-owned drawing controls.  The cut length lives on a hidden reference
# sketch with ONE driving dimension (under-head face to cut end).  The cut
# end's break is the title block's general edge break, not a part dimension.
CUT_LENGTH_SKETCH = "CutLengthReference"
CUT_LENGTH_DIMENSION = "CutLength"
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    CUT_LENGTH_SKETCH: {CUT_LENGTH_DIMENSION},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    CUT_LENGTH_SKETCH: {CUT_LENGTH_DIMENSION: mount_stack.CUT_LENGTH_PLACES},
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
REFERENCE_SKETCHES = (CUT_LENGTH_SKETCH, SUPPLIER_STOCK_FEATURE)
# The 1:1 Front view carries the cut length.
FRONT_VIEW_DIMENSIONS = {CUT_LENGTH_SKETCH: {CUT_LENGTH_DIMENSION}}

# --- U27: can one fixed cut length serve every in-band post and plate? ---
# The printed bands, as the shop reads them off the title block of the post's
# own sheet (in the post's own unit): its overall height at the body height's
# places, its counterbore depth a two-place callout, and the plate is 1/4 flat
# bar as supplied (U41) at its mill tolerance.
_POST_UNIT = drawing_unit("parts/dt-cone-pivot-post", _config.parts("dt-cone-pivot-post"))
_POST_HEIGHT_DEVIATIONS = printed_deviations(
    post.BLOCK_HEIGHT, post.DRAWING_PRECISION_BY_NAME["MainBodyHt"], unit=_POST_UNIT
)
_CBORE_DEPTH_PLACES = 2
_CBORE_DEPTH_DEVIATIONS = printed_deviations(
    post.ATTACHMENT_CBORE_DEPTH, _CBORE_DEPTH_PLACES, unit=_POST_UNIT
)
# Stock thickness and tap-entry breaks are owned by the mating platform.
PLATE_STOCK_BAND_MM = platform.PLATE_STOCK_BAND
# Two breaks eat thread:
# - the screw's cut end: the title block's general edge break at its maximum
#   (the shop hacksaws and files the burr).  Main's ruling on the run-7 sheet:
#   no part-local break limit; the cut-to-fit allowance gave up the thread
#   instead (dt_post_mount_stack.CUT_TO_FIT_SHORT_MM).
# - the platform's tap exit: the platform's own local deburr limit.
POST_MOUNT_TAP_EDGE_BREAK = platform.POST_MOUNT_TAP_EDGE_BREAK
CUT_END_BREAK_MAX_MM = edge_break_chamfer_mm(unit=UNIT)
ENGAGEMENT_BREAKS_MM = POST_MOUNT_TAP_EDGE_BREAK + CUT_END_BREAK_MAX_MM

# Counterbore floor above PlateTop (the post foot seats on it), both ends.
FLOOR_LOW_MM = (post.BLOCK_HEIGHT + _POST_HEIGHT_DEVIATIONS[0]) - (
    post.ATTACHMENT_CBORE_DEPTH + _CBORE_DEPTH_DEVIATIONS[1]
)
FLOOR_HIGH_MM = (post.BLOCK_HEIGHT + _POST_HEIGHT_DEVIATIONS[1]) - (
    post.ATTACHMENT_CBORE_DEPTH + _CBORE_DEPTH_DEVIATIONS[0]
)
PLATE_THIN_MM = platform.PLATE_THICKNESS - PLATE_STOCK_BAND_MM
# The factory thread runs SUPPLIER_THREAD_LENGTH up from the supplied tip; the
# shank above it is plain.  Even on the lowest floor the plate's tapped hole
# sits wholly below the thread start, so only full thread engages it.
FACTORY_THREAD_START_MM = STOCK_LENGTH_MM - _T  # 2.500 in under the head
if FACTORY_THREAD_START_MM >= FLOOR_LOW_MM:
    raise ValueError("the plain shank reaches the platform's tapped hole")
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
# own hole at assembly (MHA-DT-00), and the sheet prints the modelled length as
# a REFERENCE dimension with no band.  If the bands ever tighten enough for a
# fixed length to exist, this raises and the sheet should carry that band.
FIXED_CUT_LENGTH_EXISTS = FIXED_LENGTH_ENGAGEMENT_MIN_MM <= FIXED_LENGTH_FLUSH_MAX_MM
if FIXED_CUT_LENGTH_EXISTS:
    raise ValueError(
        "a fixed MHA-DT-VN-61 cut length now fits both corners "
        f"({FIXED_LENGTH_ENGAGEMENT_MIN_MM:.2f}..{FIXED_LENGTH_FLUSH_MAX_MM:.2f}): "
        "print it with its band instead of a reference length"
    )

# The fit-to-hole acceptance (MHA-DT-00): each screw's cut end sits between
# flush with its own MHA-DT-20 underside and this much short of it, never proud.
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
# callout, as well as the drive-train assembly step. The cut length prints
# .XX; the allowance (.005) needs .XXX, and an allowance those places would
# round is refused.
_FIT_PLACES = DRAWING_PRECISION[CUT_LENGTH_SKETCH][CUT_LENGTH_DIMENSION]
if _FIT_PLACES != mount_stack.CUT_LENGTH_PLACES:
    raise ValueError("post screw cut-length precision diverges from its nominal stack")
CUT_TO_FIT_SHORT_PLACES = 3
if not _on_inch_grid(POST_SCREW_CUT_TO_FIT_SHORT, CUT_TO_FIT_SHORT_PLACES):
    raise ValueError("the cut-to-fit allowance does not print at its places")

# The cut-to-fit nominal: MHA-DT-VN-61's own length, applied by its trim (the
# shared size row stays the supplied screw).  It is the nominal post and
# plate's flush length less the middle of the fit-to-hole allowance, at the
# length's printed places, so the model is itself a cut the sheet accepts
# (Codex P2 on #857: a typed 86.0 ended 0.33 short, outside 0.3).
CUT_LENGTH_MM = mount_stack.CUT_LENGTH_MM
CUT_SHORT_NOMINAL_MM = FLUSH_LENGTH_MM - CUT_LENGTH_MM
if not 0.0 <= CUT_SHORT_NOMINAL_MM <= POST_SCREW_CUT_TO_FIT_SHORT:
    raise ValueError(
        f"MHA-DT-VN-61 modelled length {CUT_LENGTH_MM} ends {CUT_SHORT_NOMINAL_MM:.3f} "
        f"short of the nominal MHA-DT-20 underside, outside flush to "
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
        f"MHA-DT-VN-61 worst-case engagement {POST_MOUNT_ENGAGEMENT_WORST:.2f} "
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
# Pending exception ruling: MHA-DT-VN-61 engagement (#1019).
CUT_TO_FIT_CALLOUT = (
    "CUT TO FIT AT ASSEMBLY\n"
    f"END FLUSH TO {inch_text(POST_SCREW_CUT_TO_FIT_SHORT, CUT_TO_FIT_SHORT_PLACES)} SHORT\n"
    "OF MHA-DT-20 UNDERSIDE,\n"
    "NEVER PROUD,\n"
    f"ENGAGEMENT {POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D MIN"
)

# The model as built, on the nominal chain (its cut end is inside the
# acceptance, checked above), still holds the exception's minimum.
ENGAGEMENT_NOMINAL_MM = CUT_LENGTH_MM - GRIP_MM
if ENGAGEMENT_NOMINAL_MM < MIN_ENGAGEMENT_MM:
    raise ValueError(
        f"MHA-DT-VN-61 nominal engagement {ENGAGEMENT_NOMINAL_MM:.2f} is under "
        f"{MIN_ENGAGEMENT_DIAMETERS:.2f}D"
    )

# --- The modification the shop makes (Main's ruling on the cut end) ---
# The supplied screw is 4 in, modelled with the family's factory tip chamfer.
# Cutting to fit removes that tip, MHA-DT-VN-61's own modification, not a
# property of the fillister family: the builder builds the stock screw at its
# supplied length (STOCK_LENGTH_MM, the shared recipe's row), then trims it at
# CutLength.
if abs(STOCK_LENGTH_MM - 4.0 * 25.4) > 1e-9:
    raise ValueError("the MSC 40923906 row is not the supplied 4 in screw")
# The family's factory tip: 45 deg x 0.7P (diag_mcmaster_fillister's law).
FACTORY_TIP_CHAMFER_MM = 0.7 * _PITCH
# Longest in-band seated assembly, cut flush, must still remove the supplied
# factory tip. This is stricter than checking the reference cut length alone.
LONGEST_FITTED_LENGTH_MM = FLOOR_HIGH_MM + PLATE_THICK_MM
STOCK_REACH_MARGIN_MM = (
    STOCK_LENGTH_MM - FACTORY_TIP_CHAMFER_MM - LONGEST_FITTED_LENGTH_MM
)
if STOCK_REACH_MARGIN_MM <= 0.0:
    raise ValueError("MSC 40923906 cannot reach every printed post/plate corner")
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
if not 0.0 < _ROOT_REACHED_MM < FACTORY_TIP_CHAMFER_MM:
    raise ValueError("the factory tip no longer cuts below the thread root")
if STOCK_LENGTH_MM - FACTORY_TIP_CHAMFER_MM <= CUT_LENGTH_MM:
    raise ValueError("the cut no longer clears the factory tip")

# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): no dimension, no tolerance, no installation sequence.  The cut
# length is the reference dimension above; its fit-to-hole acceptance is the
# CutLength callout (CUT_TO_FIT_CALLOUT), not a note.
MANUFACTURING_NOTES = (
    "UNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE."
)
