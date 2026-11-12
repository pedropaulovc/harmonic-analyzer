"""Explicit, volume-bounded interference-fit contract for the channel bank.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract. Only build_ch_channel_assembly (and the
assemblies that contain it) and verify_soundness:ch_channel fold this module, so
it imports only what its own pairs need.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM
from _interference_common import numbered_pairs, smooth_annulus_limit_mm3
from sh_vn_arbor_set_screw_spec import THREAD as _ARBOR_SET_SCREW_THREAD

# The MHA-SH-VN-58 BarPin members (sh_vn_pivot_pin_bar_spec), the Ø1.984375
# (5/64 nominal) dowel pressed into each MHA-CH-01 bar's Ø1.9558 (.077 in)
# top-pin ream through both top-notch cheeks: 6.35 bar less the .124 (3.1496)
# notch (inch #290).
# Literals, so this table does not re-key on the pin spec;
# test_sh_vn_pivot_pin_bar_fit pins them to it.
BAR_PIVOT_PIN_PRESS = (1.984375, 1.9558, 6.35 - 3.1496)
# The MHA-SH-VN-58 RodPin members (sh_vn_pivot_pin_rod_spec), the same dowel
# pressed into each MHA-CH-03 rod's Ø1.9558 fork ream through both tines:
# .240 (6.096) fork less the .106 (2.6924) slot (user ruling 2026-10-09, PR
# #1292 review F1; slot widened #982; inch #290);
# test_sh_vn_pivot_pin_rod_fit pins the literals to the pin spec.
ROD_PIVOT_PIN_PRESS = (1.984375, 1.9558, 6.096 - 2.6924)
# build_ch_channel_assembly inserts both members of channel j's pins in
# channel order, the RodPin then the BarPin: instances 2j + 1 and 2j + 2, while
# channel j's rod and bar are each its (j + 1)th instance
# (_copied_chain_instances pins the bar's number).
_PIVOT_PIN = "sh-vn-pivot-pin"
# The MHA-CH-VN-53 #4-40 apex set screws (user, 2026-10-10), one down through
# each MHA-CH-08 ear's arch (apex .388 (9.852) over the bore since #1371,
# #290) into its Ø.256 bore, the tap cut at its drill. The thread's major envelope crosses no
# longer a metal column than the apex's height over the bore axis less the
# bore's height at the envelope's edge, so the smooth annulus over that column
# bounds the overlap; the cup on the modelled shaft flat is contact, as the
# arbor's screws on the arbor. Screw n is placed with bracket n (south first).
# Literals (apex over the bore, bore), like the rows above, so this table
# does not re-key on the bracket spec; test_ch_channel_assembly_drawing pins
# them to ch_pivot_bracket_spec. #911: re-pin to the measured overlap x 1.10
# from the first channel leaf.
PIVOT_EAR_APEX_AND_BORE = (9.852, 6.5024)
_PIVOT_EAR_TAP_COLUMN = PIVOT_EAR_APEX_AND_BORE[0] - math.sqrt(
    (PIVOT_EAR_APEX_AND_BORE[1] / 2.0) ** 2
    - (THREAD_MAJOR_MM[_ARBOR_SET_SCREW_THREAD] / 2.0) ** 2
)
PIVOT_EAR_SET_SCREW_LIMIT = smooth_annulus_limit_mm3(
    THREAD_MAJOR_MM[_ARBOR_SET_SCREW_THREAD],
    TAP_DRILL_MM[_ARBOR_SET_SCREW_THREAD],
    _PIVOT_EAR_TAP_COLUMN,
)
FULCRUM_SET_SCREW_THREAD = (1.854, 1.511, 3.96875)
ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    **{
        frozenset((f"{_PIVOT_PIN}-{2 * n - 1}", f"ch-connecting-rod-{n}")): (
            smooth_annulus_limit_mm3(*ROD_PIVOT_PIN_PRESS)
        )
        for n in range(1, 21)
    },
    **{
        frozenset((f"{_PIVOT_PIN}-{2 * n}", f"ch-amplitude-bar-{n}")): (
            smooth_annulus_limit_mm3(*BAR_PIVOT_PIN_PRESS)
        )
        for n in range(1, 21)
    },
    **numbered_pairs(
        "sh-vn-arbor-set-screw",
        range(1, 3),
        "ch-pivot-bracket",
        PIVOT_EAR_SET_SCREW_LIMIT,
        second_number=None,
    ),
    # The two MHA-CH-VN-55 #1-72 x 5/32 (3.96875) set screws in the keeper crown
    # taps (#53 drill, 1.511), bounded over the screw's whole length; rear
    # keeper and screw are both placed first, so their suffixes match. A
    # smooth-annulus bound for the first build -- re-pin to the measured
    # overlap x 1.10 from the first channel leaf. Literals, like the rows
    # above; test_ch_fulcrum_shaft_drawing pins them to the specs.
    **numbered_pairs(
        "ch-vn-fulcrum-set-screw",
        range(1, 3),
        "ch-fulcrum-keeper",
        smooth_annulus_limit_mm3(*FULCRUM_SET_SCREW_THREAD),
        second_number=None,
    ),
}
