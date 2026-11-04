"""Explicit, volume-bounded interference-fit contract for the top assembly.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract. Explicit ``@Role:N`` selectors are resolved to
observed native names only after file, selected member and reference readback.
Only build_ha_harmonic_analyzer_assembly and
verify_soundness:ha_harmonic_analyzer fold this module. The thread and seat
limits it shares with the magnifier and summing tables are imported from
their owners: the top assembly contains both, so that adds no foreign re-key.
"""

from __future__ import annotations

from collections.abc import Mapping

import sm_summing_lever_spec
from _hole_spec import TAP_DRILL_MM, blind_cut_dia_mm
from _interference_common import numbered_pairs, smooth_annulus_limit_mm3
from _mg_magnifier_interference import (
    _MG_FIXTURE_THREAD_LIMIT,
    _MG_LEVER_THREAD_LIMIT,
    _MG_ROD_THREAD_LIMIT,
)
from _sm_summing_interference import _KNIFE_HANGER_SEAT_OVERLAP_LIMIT
from dt_pinion_pivot_block_geometry import BLOCK_HEIGHT as _PINION_BLOCK_HEIGHT
from dt_swing_stop_screw_spec import EMBED_LEN as _STOP_EMBED_LEN
from dt_swing_stop_screw_spec import SHANK_DIA as _STOP_SHANK_DIA
from dt_swing_stop_screw_spec import THREAD as _STOP_THREAD
from dt_vn_slotted_screw_spec import SHANK_DIA as _BLOCK_SCREW_DIA
from dt_vn_slotted_screw_spec import SHANK_LEN as _BLOCK_SCREW_LENGTH
from dt_vn_slotted_screw_spec import THREAD as _BLOCK_SCREW_THREAD
from fr_harmonic_base_fasteners import (
    PEDESTAL_SCREW_ENGAGEMENT as _PEDESTAL_SCREW_ENGAGEMENT,
)
from fr_harmonic_base_spec import POCKET_SKIN as _BASE_DECK_SKIN
from stock_anchor_geom import ANCHOR_9489T111

# The bracket's two #2-56 screws (major 2.1844) in the summing lever's Ø1.778
# receiver drill over the full engagement (magnifying_bracket_joint_layout).
_MG_BRACKET_SCREW_TRIPLE_MM = (2.1844, 1.778, 4.7625)

_CHANNEL_ANCHOR_THREAD_LIMIT = smooth_annulus_limit_mm3(
    ANCHOR_9489T111.thread_major_dia_mm,
    blind_cut_dia_mm(sm_summing_lever_spec.HOLE_SPEC),
    sm_summing_lever_spec.COEFFICIENT_T,
)
# Each MHA-SM-VN-53 dowel pressed up to the floor of its Ø3.1496 ream in the
# MHA-FR-02 crossbar's faced underside (owner ruling 2026-10-24, T+H3;
# sm_vn_knife_mount_dowel_spec.PRESS_HOLE_DIA, .1240 REAM H7 +.0005/0:
# smallest 3.1496), its largest catalogue diameter 3.18262 over its 11.938
# press depth (sm_vn_knife_mount_dowel_spec.DIA_MAX, PRESS_DEPTH).  All three are
# literals, test-pinned to their owners like _sm_summing_interference's
# _KNIFE_HANGER_REACH, so a crossbar or dowel edit does not re-key this
# table.  The models are line to line, so this bounds the press at its
# print-worst: the largest catalogue pin in the smallest ream, the whole
# depth.  The dowels belong to the summing subassembly and the crossbar to
# the frame's, so the pairs are checked at the top level (ALLOWED_PAIRS
# below); in the summing subassembly each pin slips in its knife mount's
# round hole or slot, with no overlap.
_KNIFE_DOWEL_HOLE_MIN = 3.1496
_KNIFE_DOWEL_DIA_MAX = 3.18262
_KNIFE_DOWEL_PRESS_DEPTH = 11.938
_KNIFE_DOWEL_PRESS_LIMIT = smooth_annulus_limit_mm3(
    _KNIFE_DOWEL_DIA_MAX, _KNIFE_DOWEL_HOLE_MIN, _KNIFE_DOWEL_PRESS_DEPTH
)

# The cone-platform pivot screw now carries its full McMaster #10-24 thread
# envelope. Bound its exact nested tap engagement by the same conservative
# smooth-annulus contract as every other migrated stock thread.
ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    **numbered_pairs(
        "sm-summing-1/sm-vn-knife-hanger-stud",
        range(1, 3),
        "sm-summing-1/sm-vn-knife-hanger-washer",
        _KNIFE_HANGER_SEAT_OVERLAP_LIMIT,
        second_number=None,
    ),
    **numbered_pairs(
        "sm-summing-1/sm-vn-knife-hanger-washer",
        range(1, 3),
        "fr-frame-1/fr-top-frame",
        _KNIFE_HANGER_SEAT_OVERLAP_LIMIT,
    ),
    # Four MHA-SM-VN-53 dowels, two per knife mount, all in the one crossbar.
    **numbered_pairs(
        "sm-summing-1/sm-vn-knife-mount-dowel",
        range(1, 5),
        "fr-frame-1/fr-top-frame",
        _KNIFE_DOWEL_PRESS_LIMIT,
    ),
    frozenset(
        ("mg-magnifier-1/sh-vn-thumb-screw-2", "mg-magnifier-1/mg-output-fixture-1")
    ): _MG_FIXTURE_THREAD_LIMIT,
    frozenset(
        (
            "mg-magnifier-1/mg-magnifying-vertical-rod-1",
            "mg-magnifier-1/mg-magnifying-clamp-1",
        )
    ): _MG_ROD_THREAD_LIMIT,
    frozenset(
        (
            "mg-magnifier-1/mg-magnifying-lever-1",
            "mg-magnifier-1/mg-magnifying-bracket-1",
        )
    ): _MG_LEVER_THREAD_LIMIT,
    # Two #2-56 x 1/4 screws seat on the flange's front face.
    # Only thread/lever overlap is allowed; the bracket must remain clear.
    **numbered_pairs(
        "mg-magnifier-1/mg-vn-magnifying-bracket-screw",
        range(1, 3),
        "sm-summing-1/sm-summing-lever",
        smooth_annulus_limit_mm3(*_MG_BRACKET_SCREW_TRIPLE_MM),
    ),
    **numbered_pairs(
        "ch-channel-1/ch-vn-spring-hook",
        range(1, sm_summing_lever_spec.HOLE_COUNT + 1),
        "sm-summing-1/sm-summing-lever",
        _CHANNEL_ANCHOR_THREAD_LIMIT,
    ),
    frozenset(
        (
            "fr-frame-1/fr-harmonic-base-1",
            "dt-drive-train-1/dt-vn-cone-pivot-screw-1",
        )
    ): smooth_annulus_limit_mm3(4.826, 3.797, 9.525),
    **numbered_pairs(
        "dt-drive-train-1/dt-vn-cone-lock-knob",
        range(1, 2),
        "fr-frame-1/fr-harmonic-base",
        smooth_annulus_limit_mm3(6.35, 5.105, 12.7),
    ),
    **numbered_pairs(
        "dt-drive-train-1/@SwingStopScrew:",
        range(1, 2),
        "fr-frame-1/fr-harmonic-base",
        smooth_annulus_limit_mm3(
            _STOP_SHANK_DIA, TAP_DRILL_MM[_STOP_THREAD], _STOP_EMBED_LEN
        ),
    ),
    # Bound only the threaded material actually inside the base seat.
    **numbered_pairs(
        "dt-drive-train-1/dt-vn-slotted-screw",
        range(1, 5),
        "fr-frame-1/fr-harmonic-base",
        smooth_annulus_limit_mm3(
            _BLOCK_SCREW_DIA,
            TAP_DRILL_MM[_BLOCK_SCREW_THREAD],
            _BLOCK_SCREW_LENGTH - _PINION_BLOCK_HEIGHT,
        ),
    ),
    **numbered_pairs(
        "dt-drive-train-1/@FootScrew:",
        range(1, 2),
        "fr-frame-1/fr-harmonic-base",
        smooth_annulus_limit_mm3(2.8448, 2.261, 8.725),
    ),
    # The unchanged #8-32 x 3/4 stock inserts 14.05 through the pedestal ledge.
    # Only the retained skin can overlap: the protruding tip is in pocket air.
    **numbered_pairs(
        "dt-drive-train-1/dt-vn-pedestal-hold-down-screw",
        range(1, 3),
        "fr-frame-1/fr-harmonic-base",
        smooth_annulus_limit_mm3(
            4.1656, 3.454, min(_PEDESTAL_SCREW_ENGAGEMENT, _BASE_DECK_SKIN)
        ),
    ),
    # The two #2-56 x 7/16 (11.1125) MHA-CH-VN-52 keeper foot screws: the head
    # sits flush in the 8.0 foot's 2.1082 counterbore, so 11.1125 - (8.0 -
    # 2.1082) = 5.2207 enters the top frame's tap (ch_fulcrum_keeper_spec).
    **numbered_pairs(
        "ch-channel-1/ch-vn-frame-side-screw",
        range(1, 3),
        "fr-frame-1/fr-top-frame",
        smooth_annulus_limit_mm3(2.1844, 1.778, 5.2207),
    ),
    # #743 PR2: the two #8-32 x 5/8 (15.875) MHA-CH-VN-57 rocker-bracket hold-downs
    # (one per bracket since the 2026-10-09 flip; 5/8 since owner Q13c) pass
    # the .24 (6.096) bracket foot and engage 9.779 of the support's transferred seats.
    # Literals, like the rows above, so this table does not re-key on the
    # rocker bank's layout; test_rocker_bracket_seat_layout pins them to
    # rocker_bracket_seat_layout.
    **numbered_pairs(
        "ch-channel-1/ch-vn-bracket-hold-down-screw",
        range(1, 3),
        "fr-frame-1/fr-rocker-arm-support",
        smooth_annulus_limit_mm3(4.1656, 3.454, 15.875 - 6.096),
    ),
}
