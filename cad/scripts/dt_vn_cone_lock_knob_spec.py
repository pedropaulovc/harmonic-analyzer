r"""Pure McMaster 93585A190 nominal geometry and lock-seat checks.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure. The supplier-model scalars in mm/degrees are the per-SKU vendor
source (``_mcmaster_93585a190.py``, SolidWorks-free at import), which the
native recipe also reads. Base, swing-platform and pose readers import this
spec, not a native recipe.

The high-profile head has no collar: its chamfered underside bears directly
on the plate (or, disengaged, on the bare base). HEAD_DIA is the source
model's maximum radial envelope over the knurl crests, not a tolerance-high
supplied diameter. Head and stud supplier tolerances are unprovided; no
manufactured title-block grade is assigned to these purchased nominals.

The knob locks the cone-to-drum set at assembly (cone_set_stack): with the
pedestals already shimmed and tightened, swing the platform in until T120's
radial feeler is snug, hold it, and tighten the knob. It clamps by friction
anywhere along the lock notch.
"""

from __future__ import annotations

import _config
from _hole_spec import HoleSpec
from _mcmaster_93585a190 import (
    HEAD_H as _HEAD_H,
    HEAD_R as _HEAD_R,
    LENGTH as _LENGTH,
    MAJOR_R as _MAJOR_R,
    PITCH as _PITCH,
)
from fr_harmonic_base_fasteners import ThroughSeatMaterial, require_through_seat_fit

SOURCE = "cad/out/reports/mcmaster-93585A190-dump.json"

HEAD_DIA_BAND = None  # Unknown supplier tolerance, not a zero-width band.
HEAD_H_BAND = None
STUD_DIA_BAND = None
STUD_LEN_BAND = None

THREAD = "1/4-20"
HEAD_DIA = 2.0 * _HEAD_R
HEAD_H = _HEAD_H
STUD_DIA = 2.0 * _MAJOR_R
STUD_LEN = _LENGTH
THREAD_PITCH = _PITCH
TIP_CHAMFER = THREAD_PITCH * 0.75
MIN_USEFUL_ENGAGEMENT = 1.5 * STUD_DIA


def require_seat_fit(
    seat: HoleSpec,
    plate_thickness: float,
    stud_length: float,
    *,
    material: ThroughSeatMaterial,
) -> None:
    """Check both stock-knob poses against the actual through-threaded receiver.

    Supplier stud/tip tolerances remain unprovided. This nominal-stock check
    charges the manufactured platform's printed thickness band and the harvested
    tip chamfer; it does not turn those vendor nominals into supplied limits.
    """
    if (
        seat.kind != "tapped"
        or seat.size != THREAD
        or seat.thread_class != "2B"
        or seat.end != "through_all"
    ):
        raise AssertionError("cone lock requires a through 1/4-20 UNC-2B seat")
    plate_band = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
    for pose, insertion_min, insertion_max in (
        (
            "plate clamp",
            stud_length - plate_thickness - plate_band,
            stud_length - plate_thickness + plate_band,
        ),
        ("bare base", stud_length, stud_length),
    ):
        require_through_seat_fit(
            f"cone lock {pose}",
            seat,
            material,
            insertion_min_mm=insertion_min,
            insertion_max_mm=insertion_max,
            tip_loss_mm=TIP_CHAMFER,
        )
