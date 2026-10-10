r"""Pure McMaster 90280A108 stock dimensions and swing-stop seat checks.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure. The fillister row in mm is the per-SKU vendor source
(``_mcmaster_90280a108.py``, SolidWorks-free at import), which the native
recipe and the same-SKU foot and latch-hook bracket specs also read; this
module adds the stock limits and the seat checks.

The stop seats fully home on the base top; the platform edge bears on its
head only when DISENGAGED. It limits the disengage swing and plays no part
in meshing: the cone-lock-knob sets and locks the engaged mesh at assembly.
HEAD_DIA/HEAD_H remain the harvested model nominals. Separate
ASME B18.6.3 stock limits below are qualified by the live SKU's declared
standard and corroborated for the slotted fillister form; they are not
manufactured title-block grades. They bound head size, slot depth, length,
the underside bearing circle and where full thread form starts near the
head, not the supplier's complete curved head/rounded-tip profile.
Only the manufactured platform's thickness uses its title-block allowance.
The two-place MIN engagement callout below owns the installed-joint limit
printed by the assembly drawing; it does not qualify supplier tail geometry.
"""

from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING

import _config
from _fit_deviations import deviations
from _mcmaster_90280a108 import FILLISTER_SIZE

if TYPE_CHECKING:
    from _hole_spec import HoleSpec

SOURCE = "McMaster 90280A108 vendor-model fillister dimensions"
THREAD_FIT_SOURCE = "https://www.mcmaster.com/90280A108/ (live product page, 2026-10-08)"
THREAD_LIMITS_SOURCE = (
    "https://www.steelmasters.co.nz/wp-content/uploads/2022/03/"
    "External_Thread_Dimensions_for_UNC_Screw_Thread_2016.pdf"
)
HEAD_LIMITS_SOURCE = (
    "https://theswissbay.ch/pdf/Books/Survival/Workshop/"
    "Machining%20and%20Machinery/Machinery's%20Handbook%20"
    "(26th%20Edition)/26663_yj5.pdf"
)
LENGTH_LIMITS_SOURCE = "https://optimas.com/imperial-parts-series-phillips-machine-screws/"
STOCK_STANDARD = "ASME B18.6.3"
THREAD = "#4-40"
THREAD_CLASS = "2A"
# Steelmasters external UNC table, No 4 / 40 TPI / 2A row, inches -> mm.
THREAD_MAJOR_MAX_MM = 0.1112 * 25.4
EXTERNAL_PITCH_DIA_MIN_MM = 0.0925 * 25.4
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, THREAD_PITCH = FILLISTER_SIZE
# Handbook Table 8, slotted (not drilled) #4 fillister row, inch -> mm.
# The Optimas ASME fillister table independently agrees on these head limits.
HEAD_DIA_MIN_MM = 0.166 * 25.4
HEAD_DIA_MAX_MM = 0.183 * 25.4
HEAD_SIDE_MIN_MM = 0.069 * 25.4
HEAD_SIDE_MAX_MM = 0.079 * 25.4
HEAD_TOTAL_MIN_MM = 0.088 * 25.4
HEAD_TOTAL_MAX_MM = 0.107 * 25.4
SLOT_DEPTH_MAX_MM = 0.048 * 25.4
# Table 8 footnote: the bearing circle at the underside is >=90% of MIN A.
HEAD_BEARING_DIA_MIN_MM = 0.90 * HEAD_DIA_MIN_MM
HEAD_BEARING_RADIUS_MIN_MM = HEAD_BEARING_DIA_MIN_MM / 2.0
UNSLOTTED_HEAD_HEIGHT_MIN_MM = HEAD_TOTAL_MIN_MM - SLOT_DEPTH_MAX_MM
# ASME length allowance for #4 machine screws, nominal lengths 1/8..1/2 in.
LENGTH_SHORT_ALLOWANCE_MM = 0.02 * 25.4
LENGTH_MIN_MM = SHANK_LEN - LENGTH_SHORT_ALLOWANCE_MM
LENGTH_MAX_MM = SHANK_LEN
# Handbook p.1568: No5 and smaller, nominal L>3D and L<=1-1/8 in,
# have full-form threads starting no farther than two pitches from the head.
# This bounds the head-end runout only, not incomplete thread at the tip.
FULL_THREAD_START_MAX_MM = 2.0 * THREAD_PITCH

# Standard stock deviations about the unchanged vendor-model nominals,
# ordered (upper, lower) as in _fit_deviations. No title-block grade is used.
HEAD_DIA_BAND = (HEAD_DIA_MAX_MM - HEAD_DIA, HEAD_DIA_MIN_MM - HEAD_DIA)
HEAD_H_BAND = (HEAD_TOTAL_MAX_MM - HEAD_H, HEAD_TOTAL_MIN_MM - HEAD_H)
SHANK_LEN_BAND = (0.0, -LENGTH_SHORT_ALLOWANCE_MM)
deviations(HEAD_DIA_BAND)
deviations(HEAD_H_BAND)
deviations(SHANK_LEN_BAND)
SHANK_DIA_BAND = None  # Raw model-body profile; qualified thread limits are above.
EMBED_LEN = SHANK_LEN
PROUD_LEN = SHANK_LEN - EMBED_LEN
CONTACT_DIA = HEAD_DIA
TIP_CHAMFER = 0.7 * THREAD_PITCH
# Installed-joint acceptance, inspected on the real stock/receiver. This is
# the design's existing >=1D floor rounded UP to a practical 0.01 mm minimum,
# not a supplier tolerance on the screw length, tip or thread runout.
MIN_USEFUL_ENGAGEMENT_MM = ceil(SHANK_DIA * 100.0) / 100.0
MIN_USEFUL_ENGAGEMENT_SOURCE = (
    "Functional installation inspection: full-form stop thread engagement "
    "at least 1D, rounded upward to 0.01 mm; head fully seated"
)
MIN_USEFUL_ENGAGEMENT_TEXT = f"{MIN_USEFUL_ENGAGEMENT_MM:.2f} MIN"
PLATE_THICKNESS_ALLOWANCE = 25.4 * float(_config.title_block("linear_2pl")["value_in"])


def require_seat_fit(seat: HoleSpec, plate_thickness: float) -> None:
    """Check the nominal seated stop; actual full-form engagement is inspected.

    Passing this source-model seat check is not evidence that the installed
    stock meets MIN_USEFUL_ENGAGEMENT_MM or that its head is fully seated.
    """
    if seat.kind != "tapped" or seat.size != THREAD or seat.end != "blind":
        raise AssertionError("swing stop requires a blind #4-40 tapped seat")
    if EMBED_LEN - TIP_CHAMFER < MIN_USEFUL_ENGAGEMENT_MM:
        raise AssertionError(
            "swing stop has less than the minimum useful thread engagement"
        )
    thread_depth = seat.overrides_mm.get("ThreadDepth", seat.depth_mm)
    if thread_depth - EMBED_LEN < 0.25 - 1e-9:
        raise AssertionError("swing stop bottoms in its threaded seat")
    if seat.depth_mm - thread_depth < 5.0 * THREAD_PITCH - 1e-9:
        raise AssertionError("swing-stop drill lacks five-pitch plug-tap lead")
    # The whole head must bear on the edge of a tolerance-low platform.
    if PROUD_LEN + HEAD_H > plate_thickness - PLATE_THICKNESS_ALLOWANCE + 1e-9:
        raise AssertionError("swing-stop head stands above the tolerance-low platform")
