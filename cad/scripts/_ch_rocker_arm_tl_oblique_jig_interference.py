"""Explicit, volume-bounded interference-fit contract for the oblique rocker-arm jig.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract. Explicit ``@Role:N`` selectors are resolved to
observed native names only after file, selected member and reference readback. Only build_ch_rocker_arm_tl_oblique_jig_assembly (and the
assemblies that contain it) and verify_soundness:ch_rocker_arm_tl_oblique_jig fold this module, so
it imports only what its own pairs need.
"""

from __future__ import annotations

from collections.abc import Mapping

from _interference_common import numbered_pairs, smooth_annulus_limit_mm3

# Oblique shop fixture: smooth-thread overlaps only. The R4 strap holding
# fits nothing tight: the loose stop pins stand in the riser's #30 holes on
# the carrier top, the top-hat washer's 13/64 bore clears its #8-32 neck and
# its spigot hangs in the (unmodelled) strap's hub hole.
_JIG = "ch-rocker-arm-tl-oblique"
_JIG_VENDOR = "ch-rocker-arm-tl-vn-oblique"
JIG_RAIL_SCREW_THREAD = (4.1656, 3.454, 9.35)  # #8-32 into each base bar
# The common #8-32 x 3/4 (rail screw family, occurrences 17-20) up through
# Bar1 into an end bracket's bar-face thread: 19.05 less the 7.137 grip.
JIG_BAR_SCREW_THREAD = (4.1656, 3.454, 11.913)
JIG_CARRIAGE_SCREW_THREAD = (4.0, 3.242, 4.8006)  # M4 cut to fit .189 into each HGH15 carriage from the .570 floor
JIG_PILLOW_BLOCK_SCREW_THREAD = (4.1656, 3.454, 10.875)  # #8-32 x 5/8 SHCS past the 5.0 KP08 foot into an end bracket
# The four #4-40 flat heads (riser screw family, occurrences 5-8) past the
# TL-VN-84 kit FeedNut's 3.5 flange and their heads' 0.45 stand-proud into the lug.
JIG_NUT_SCREW_THREAD = (2.8448, 2.261, 11.923595)
JIG_RISER_SCREW_THREAD = (2.8448, 2.261, 10.334168)  # #4-40 into the carrier past the .24 riser's Ø.25 CSK
# The common #8-32 x 3/4 (rail screw family) as the strap clamps, into the
# carrier's #8-32 THRU taps: occurrences 21-22 (CL, CR) under 19.05 less the
# riser and strap grip; occurrence 23 (HUB) also less the washer flange.
JIG_END_CLAMP_THREAD = (4.1656, 3.454, 10.4648)
JIG_HUB_CLAMP_THREAD = (4.1656, 3.454, 8.9408)
JIG_LEVER_SCREW_THREAD = (7.9375, 6.528, 10.414)  # 5/16-18 into the carrier
JIG_PIVOT_SCREW_THREAD = (7.9375, 6.528, 14.478)  # 5/16-18 cut to .570 below shoulder-end floor
JIG_T_NUT_THREAD = (12.7, 10.716, 14.0)  # 1/2-13 stud in its T-nut
JIG_FLANGE_NUT_THREAD = (12.7, 10.716, 13.0)  # 1/2-13 stud in its flange nut
# The Tr8 screw in the FeedNut's Ø6.0 minor-diameter bore, 13.5 long as
# fitted. Over the carriage's travel the nut touches nothing else (the jig
# spec's ``feed_nut_travel_gaps``), so only the LeadScrew names the nut. Both
# are TL-VN-84 kit members, named by their role references.
JIG_FEED_NUT_THREAD = (8.0, 6.0, 13.5)
ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    # Base bar members are role references (Bar1 under rail 1, Bar2 under 2).
    **numbered_pairs(
        f"{_JIG_VENDOR}-rail-screw",
        range(1, 9),
        "@Bar1:",
        smooth_annulus_limit_mm3(*JIG_RAIL_SCREW_THREAD),
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-rail-screw",
        range(9, 17),
        "@Bar2:",
        smooth_annulus_limit_mm3(*JIG_RAIL_SCREW_THREAD),
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-rail-screw",
        range(17, 19),
        f"{_JIG}-end-bracket",
        smooth_annulus_limit_mm3(*JIG_BAR_SCREW_THREAD),
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-rail-screw",
        range(19, 21),
        f"{_JIG}-end-bracket",
        smooth_annulus_limit_mm3(*JIG_BAR_SCREW_THREAD),
        second_number=2,
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-carriage-screw",
        range(1, 5),
        "@Carriage:",
        smooth_annulus_limit_mm3(*JIG_CARRIAGE_SCREW_THREAD),
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-carriage-screw",
        range(5, 9),
        "@Carriage:",
        smooth_annulus_limit_mm3(*JIG_CARRIAGE_SCREW_THREAD),
        second_number=2,
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-bracket-screw",
        range(1, 3),
        f"{_JIG}-end-bracket",
        smooth_annulus_limit_mm3(*JIG_PILLOW_BLOCK_SCREW_THREAD),
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-bracket-screw",
        range(3, 5),
        f"{_JIG}-end-bracket",
        smooth_annulus_limit_mm3(*JIG_PILLOW_BLOCK_SCREW_THREAD),
        second_number=2,
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-riser-screw",
        range(1, 5),
        f"{_JIG}-carrier",
        smooth_annulus_limit_mm3(*JIG_RISER_SCREW_THREAD),
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-riser-screw",
        range(5, 9),
        f"{_JIG}-feed-block",
        smooth_annulus_limit_mm3(*JIG_NUT_SCREW_THREAD),
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-rail-screw",
        range(21, 23),
        f"{_JIG}-carrier",
        smooth_annulus_limit_mm3(*JIG_END_CLAMP_THREAD),
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-rail-screw",
        range(23, 24),
        f"{_JIG}-carrier",
        smooth_annulus_limit_mm3(*JIG_HUB_CLAMP_THREAD),
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-lever-screw",
        range(1, 3),
        f"{_JIG}-carrier",
        smooth_annulus_limit_mm3(*JIG_LEVER_SCREW_THREAD),
    ),
    **numbered_pairs(
        "@HoldDownStud:",
        range(1, 5),
        "@TNut:",
        smooth_annulus_limit_mm3(*JIG_T_NUT_THREAD),
        second_number=None,
    ),
    **numbered_pairs(
        "@HoldDownStud:",
        range(1, 5),
        "@FlangeNut:",
        smooth_annulus_limit_mm3(*JIG_FLANGE_NUT_THREAD),
        second_number=None,
    ),
    **numbered_pairs(
        "@FeedNut:",
        range(1, 2),
        "@LeadScrew:",
        smooth_annulus_limit_mm3(*JIG_FEED_NUT_THREAD),
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-pivot-screw",
        range(1, 2),
        f"{_JIG}-feed-block",
        smooth_annulus_limit_mm3(*JIG_PIVOT_SCREW_THREAD),
    ),
    **numbered_pairs(
        f"{_JIG_VENDOR}-pivot-screw",
        range(2, 3),
        f"{_JIG}-pivot-block",
        smooth_annulus_limit_mm3(*JIG_PIVOT_SCREW_THREAD),
    ),
}
