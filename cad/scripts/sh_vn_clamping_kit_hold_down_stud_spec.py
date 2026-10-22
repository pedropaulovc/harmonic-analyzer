r"""HoldDownStud rework of the shared PM kit (MHA-SH-VN-57).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: ``build_sh_vn_clamping_kit_hardware`` revolves a genuinely length-driven
blank, then adds separate native factory-end and cut-end chamfers. The finished
envelope is ``PROFILE``. The jig still mates ``ScrewAxis``; neither the lower
end nor the loaded lower thread interval moves when the unused upper end is
shortened. TNut and FlangeNut remain as supplied.

SOURCED: Precision Matthews' 52-piece clamping kit, 14 mm (9/16 in) T-slots,
SKU 52PCCK-9/16-14mm, shop inventory fixtures.clamping-kit-pm-52pcck-14mm:
https://www.precisionmatthews.com/products/52pcck-9-16-14mm
The listing states 1/2-13 studs and hardened steel, but no individual stud
lengths, chamfers or complete-thread limits. datasheet-built: no vendor CAD
obtained (listing checked 2026-10-17 UTC).

FROM C4: ``THREAD``, selected kit ``STOCK_LENGTH`` / ``STOCK_LENGTH_MM``,
finished ``LENGTH`` and its ordinary printed band come from the fasteners
spec; ``MAJOR_DIA`` comes from the base-bar stud clearance authority. The
selected 3 in kit stock length remains UNVERIFIED against the delivered kit;
57.2 is the fixed manufactured finished length under the title-block tolerance,
not a vendor SKU, a kit dimension or an assembly-set length. HD1-HD3 qualify
the measured installed setup against that full printed length band.
Main selected default B after the illustrated-choice timeout; this records
that implementation ruling, not explicit user approval.

ESTIMATED: the unmodified lower factory chamfer is 1.0 at 45 degrees. The
new upper chamfer is a manufactured 1.0 MAX, at the native feature's 45 degrees.
Neither chamfer proves a complete external-thread setback: measure U separately.
PM T-nut depth, flange-nut complete internal span and all installed intervals
remain unknown until measured. No hold-down washer is added. The fit helper
has no nominal-installed default and makes no force/preload/strength claim.

Part frame: axis +Y, lower factory end y = 0, cut end y = LENGTH. ScrewAxis
is Front Plane x Right Plane, unchanged. Threads are not modelled: the solid
is the major-diameter envelope with the two chamfers. Volume is the cylinder
less each 45-degree corner ring: pi * (R*c*c - c*c*c/3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners

CONFIGURATION = "HoldDownStud"
SUPPLIER = "Precision Matthews"
SKU = "52PCCK-9/16-14mm"
SOURCE_URL = "https://www.precisionmatthews.com/products/52pcck-9-16-14mm"
MATERIAL = "Plain Carbon Steel"  # hardened steel (listing); library stand-in
QUANTITY = fasteners.HOLD_DOWN_STUD_COUNT
THREAD = fasteners.HOLD_DOWN_STUD_THREAD
STOCK_LENGTH = fasteners.HOLD_DOWN_STUD_STOCK_LENGTH
STOCK_LENGTH_MM = fasteners.HOLD_DOWN_STUD_STOCK_LENGTH_MM
LENGTH = fasteners.HOLD_DOWN_STUD_LENGTH_MM
LENGTH_PLACES = fasteners.HOLD_DOWN_STUD_LENGTH_PLACES
LENGTH_BAND = fasteners.HOLD_DOWN_STUD_LENGTH_BAND
CLEARANCE_MIN = fasteners.HOLD_DOWN_STUD_CLEARANCE_MIN
COMPLETE_PROJECTION_PITCHES = fasteners.HOLD_DOWN_STUD_COMPLETE_PROJECTION_PITCHES
THREAD_PITCH_MM = fasteners.HOLD_DOWN_STUD_PITCH_MM
MAJOR_DIA = base_bar.HOLD_DOWN_STUD_DIA

# Preserve the installed jig's member description under the shared purchase Number.
BOM_DESCRIPTION = f"{THREAD} STUD, CUT {LENGTH:.1f}"
PROCESS = (
    "rework purchased PM 52PCCK-9/16-14mm 1/2-13 x 3 in stud stock: shorten only "
    "unused upper end to drawing length and restore cut-end chamfer; preserve "
    "lower factory end, loaded lower thread interval and original insertion"
)
FINISH = "BLACK OXIDE AS SUPPLIED; OIL BARE CUT END"
TOLERANCE_CLASS = "machined_block"
LOWER_FACTORY_CHAMFER = 1.0  # ESTIMATED; as supplied and unmodified
CUT_END_CHAMFER_MAX = 1.0
CUT_END_CHAMFER_PLACES = 1
CUT_END_CHAMFER_ANGLE_DEG = 45.0
RADIUS = MAJOR_DIA / 2.0

# (y, radius), finished envelope; the builder's rectangular blank receives
# these two separate native chamfer features after its length-driven revolve.
PROFILE: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (0.0, RADIUS - LOWER_FACTORY_CHAMFER),
    (LOWER_FACTORY_CHAMFER, RADIUS),
    (LENGTH - CUT_END_CHAMFER_MAX, RADIUS),
    (LENGTH, RADIUS - CUT_END_CHAMFER_MAX),
    (LENGTH, 0.0),
)
VOLUME_MM3 = math.pi * (
    RADIUS**2 * LENGTH
    - sum(RADIUS * c**2 - c**3 / 3.0 for c in (LOWER_FACTORY_CHAMFER, CUT_END_CHAMFER_MAX))
)

DRAWING_DIMENSIONS = {
    "StudProfile": {"FinishedLength"},
    "CutEndChamfer": {"CutEndChamfer"},
}
DRAWING_PRECISION = {
    "StudProfile": {"FinishedLength": LENGTH_PLACES},
    "CutEndChamfer": {"CutEndChamfer": CUT_END_CHAMFER_PLACES},
}
DRAWING_PRECISION_BY_NAME = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
DIMENSION_TOLERANCE_TYPES = {"FinishedLength": 0, "CutEndChamfer": 6}  # NONE / MAX
# The drawing refreshes the angle text from the saved native chamfer definition;
# these labels do not substitute typed values for the associated MAX driver.
DIMENSION_CALLOUTS = {
    "FinishedLength": "FINISHED CUT LENGTH;\nUPPER FREE END ONLY",
    "CutEndChamfer": "CUT END",
}
STOCK_NOTE = f"{THREAD} X {STOCK_LENGTH} IN STUD STOCK; PM {SKU} KIT"
LOWER_END_NOTE = "LOWER FACTORY END UNMODIFIED"
# The kit reference sheet owns this one-line installation legend. The separate
# REWORK sheet reads STOCK_NOTE and LOWER_END_NOTE through their own properties.
DRAWING_NOTES = (
    "THREAD NOT MODELLED; BOTTOMS IN THE T-NUT, FLUSH WITH ITS FOOT; "
    "CUT UPPER END PER REWORK."
)

# REWORK carries the native fabrication controls and their title-block band.
# MHA-CH-06-TL-00, steps HD1-HD3 on sheet 10, qualifies the actual installed
# setup against that band; it does not substitute a different cut-length range.
# The drawing imports that assembly's reference for installed acceptance only;
# no duplicate saved note properties compete with it. The conditional helper
# below is not a claim of verified delivered-kit measurements.


@dataclass(frozen=True)
class MeasuredInterval:
    """Closed measured bounds in mm, including measurement uncertainty.

    Also used for the axial envelope of the actual lower loaded thread span,
    measured from the unchanged lower factory end. No unknown/nominal sentinel.
    """

    lower_mm: float
    upper_mm: float

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.lower_mm)
            or not math.isfinite(self.upper_mm)
            or self.lower_mm < 0.0
            or self.upper_mm < self.lower_mm
        ):
            raise ValueError("measured interval must have finite ordered nonnegative bounds")


@dataclass(frozen=True)
class StudFitBounds:
    """Conditional geometric bounds, not installed verification or load proof."""

    clearance_min_mm: float
    complete_projection_min_mm: float
    required_projection_mm: float
    full_actual_nut_span_retained: bool
    lower_loaded_interval_retained: bool
    insertion_unchanged: bool

    @property
    def acceptable(self) -> bool:
        return (
            self.clearance_min_mm >= CLEARANCE_MIN
            and self.complete_projection_min_mm >= self.required_projection_mm
            and self.full_actual_nut_span_retained
            and self.lower_loaded_interval_retained
            and self.insertion_unchanged
        )


def measured_fit_bounds(
    *,
    finished_length: MeasuredInterval,
    base_bar_thickness: MeasuredInterval,
    moving_block_height: MeasuredInterval,
    lower_insertion: MeasuredInterval,
    original_lower_insertion: MeasuredInterval,
    nut_span: MeasuredInterval,
    washer_stack: MeasuredInterval,
    upper_thread_setback: MeasuredInterval,
    lower_factory_thread_start: MeasuredInterval,
    lower_loaded_interval: MeasuredInterval,
    thread_pitch_mm: float,
) -> StudFitBounds:
    """Bound G and Q from explicit measured intervals, with no rescue insertion.

    H bounds the nearest block/wing obstruction over BOTH complete hand-swept
    passes; D is the unchanged lower insertion below the bar. N is the measured
    reach from the seated bearing face to the far end of the actual complete
    internal nut threads. This conservatively envelopes their full span: do not
    substitute just a thread length or nominal nut body height. U is the
    independently measured cut-end complete-thread setback, NOT the chamfer.
    B, W and every measurement include their uncertainty. The lower loaded
    interval is the envelope of the ORIGINAL engaged complete lower threads.

    Gmin = Bmin + Hmin + Dmin - Lmax.
    Qmin = Lmin - Dmax - Bmax - Wmax - Nmax - Umax.
    Acceptance is conditional on these supplied measurements. It neither
    verifies the PM kit nor replaces the actual installed sweep/thread check.
    """
    intervals = (
        finished_length, base_bar_thickness, moving_block_height, lower_insertion,
        original_lower_insertion, nut_span, washer_stack, upper_thread_setback,
        lower_factory_thread_start, lower_loaded_interval,
    )
    if not all(isinstance(value, MeasuredInterval) for value in intervals):
        raise ValueError("every actual measurement must be an explicit MeasuredInterval")
    if not math.isfinite(thread_pitch_mm) or thread_pitch_mm <= 0.0:
        raise ValueError("actual thread pitch must be finite and positive")
    if finished_length.lower_mm <= 0.0 or nut_span.lower_mm <= 0.0:
        raise ValueError("finished length and complete nut-thread span must be positive")
    complete_upper_end = finished_length.lower_mm - upper_thread_setback.upper_mm
    nut_lower_min = (
        lower_insertion.lower_mm + base_bar_thickness.lower_mm + washer_stack.lower_mm
    )
    nut_upper_max = (
        lower_insertion.upper_mm + base_bar_thickness.upper_mm
        + washer_stack.upper_mm + nut_span.upper_mm
    )
    return StudFitBounds(
        clearance_min_mm=(
            base_bar_thickness.lower_mm + moving_block_height.lower_mm
            + lower_insertion.lower_mm - finished_length.upper_mm
        ),
        complete_projection_min_mm=complete_upper_end - nut_upper_max,
        required_projection_mm=thread_pitch_mm * COMPLETE_PROJECTION_PITCHES,
        full_actual_nut_span_retained=(
            nut_lower_min >= lower_factory_thread_start.upper_mm
            and nut_upper_max <= complete_upper_end
        ),
        lower_loaded_interval_retained=(
            lower_loaded_interval.lower_mm >= lower_factory_thread_start.upper_mm
            and lower_loaded_interval.upper_mm <= lower_insertion.lower_mm
            and lower_loaded_interval.upper_mm <= complete_upper_end
            and lower_loaded_interval.upper_mm > lower_loaded_interval.lower_mm
        ),
        insertion_unchanged=lower_insertion == original_lower_insertion,
    )


if not (
    0.0 < LOWER_FACTORY_CHAMFER < RADIUS
    and 0.0 < CUT_END_CHAMFER_MAX < RADIUS
    and LOWER_FACTORY_CHAMFER + CUT_END_CHAMFER_MAX < LENGTH < STOCK_LENGTH_MM
):
    raise ValueError("hold-down stud: invalid finished rework envelope")
