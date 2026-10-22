r"""Swing-stop application limits and seat checks for the shared 90280A108 screw.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure. The canonical ``sh_vn_fillister_screw_90280a108_spec`` owns the stock
nominal row used by every occurrence. This nonvendor application contract
retains the sourced limits and installed swing-stop seat checks.

The stop seats fully home on the base top; the platform edge bears on its
head only when DISENGAGED. It limits the disengage swing and plays no part
in meshing: the cone-lock-knob sets and locks the engaged mesh at assembly.
HEAD_DIA/HEAD_H remain the harvested model nominals. Separate
ASME B18.6.3 stock limits below are qualified by the live SKU's declared
standard and corroborated for the slotted fillister form; they are not
manufactured title-block grades. They bound head size, slot depth, length,
the underside bearing circle and where full thread form starts near the
head, not the supplier's complete curved head/rounded-tip profile.
The two-place MIN engagement callout below owns the installed-joint limit
printed by the assembly drawing; it does not qualify supplier tail geometry.
``fr_harmonic_base_fasteners.require_stop_seat_fit`` owns receiver validation,
including the manufactured platform's thickness allowance.
"""

from __future__ import annotations

from math import ceil

from _fit_deviations import deviations
from sh_vn_fillister_screw_90280a108_spec import FILLISTER_SIZE

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
# Installed-joint acceptance, inspected on the real stock/receiver: the
# shop's 1.5D full-thread rule rounded UP to 0.01 mm (machinist review of the
# stack build: the old 1D floor printed 2.85 against 4.27 needed). The fully
# seated 3/8 screw in the through-threaded deck already gives ample full form;
# this is not a supplier tolerance on length or tip.
MIN_USEFUL_ENGAGEMENT_MM = ceil(1.5 * SHANK_DIA * 100.0) / 100.0
MIN_USEFUL_ENGAGEMENT_SOURCE = (
    "Functional installation inspection: full-form stop thread engagement "
    "at least 1.5D, rounded upward to 0.01 mm; head fully seated"
)
MIN_USEFUL_ENGAGEMENT_TEXT = f"{MIN_USEFUL_ENGAGEMENT_MM:.2f} MIN"
