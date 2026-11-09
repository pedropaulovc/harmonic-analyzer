"""Explicit, volume-bounded interference-fit contract for the frame.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract. Only build_fr_frame_assembly (and the assemblies
that contain it) and verify_soundness:fr_frame fold this module, so it imports
only what its own pairs need.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM
from _interference_common import numbered_pairs, smooth_annulus_limit_mm3
from fr_frame_attachment_spec import COLUMN_SOCKET_DIAMETER
from fr_harmonic_base_fasteners import (
    HOLD_DOWN_ENGAGEMENT as _HOLD_DOWN_ENGAGEMENT,
    HOLD_DOWN_TAP_DRILL_DIA as _HOLD_DOWN_TAP_DRILL_DIA,
    HOLD_DOWN_THREAD as _HOLD_DOWN_THREAD,
)
from fr_vn_frame_cross_screw_spec import SHANK_DIA as _FRAME_CROSS_DIA
from fr_vn_frame_cross_screw_spec import SHANK_LEN as _FRAME_CROSS_LENGTH
from fr_vn_frame_cross_screw_spec import THREAD as _FRAME_CROSS_THREAD

# Minimum socket chord across the screw's complete major-diameter envelope.
# Only tapped casting lands may overlap the stock helical thread. Since the
# owner ruling of 2026-11-05 each near wall is a #10 clearance and only the
# far land is tapped, so this whole-casting bound is conservative. Neither
# the clearance-drilled tubes nor the cap skirts receive an exemption.
_FRAME_CROSS_CASTING_LENGTH = _FRAME_CROSS_LENGTH - math.sqrt(
    COLUMN_SOCKET_DIAMETER**2 - _FRAME_CROSS_DIA**2
)
_FRAME_CROSS_GATE_LIMIT_MM3 = smooth_annulus_limit_mm3(
    _FRAME_CROSS_DIA,
    TAP_DRILL_MM[_FRAME_CROSS_THREAD],
    _FRAME_CROSS_CASTING_LENGTH,
)

ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    **numbered_pairs(
        "fr-vn-lag-screw",
        range(1, 5),
        "fr-harmonic-base",
        smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM[_HOLD_DOWN_THREAD],
            _HOLD_DOWN_TAP_DRILL_DIA,
            _HOLD_DOWN_ENGAGEMENT,
        ),
    ),
    **numbered_pairs(
        "fr-vn-frame-cross-screw",
        range(1, 5),
        "fr-harmonic-base",
        _FRAME_CROSS_GATE_LIMIT_MM3,
    ),
    **numbered_pairs(
        "fr-vn-frame-cross-screw",
        range(5, 9),
        "fr-top-frame",
        _FRAME_CROSS_GATE_LIMIT_MM3,
    ),
    # MHA-FR-VN-52 / 91410A540 1/4-20 (major 6.35, #7 drill 5.105): thread from
    # the hub's spot face, 21.082 from the bore axis (fr_top_frame_spec
    # HUB_SET_SPOT_FROM_AXIS), to the cup tip 6.56 from the axis (0.21 clear of
    # the gooseneck's bare O12.70 leg): 14.478 to the O13.208 bore wall, the only
    # length that overlaps the casting (14.80 averaged over the annulus, the
    # wall curving away across it), inside the 14.83 bound.
    frozenset(
        ("fr-vn-gooseneck-set-screw-1", "fr-top-frame-1")
    ): smooth_annulus_limit_mm3(6.35, 5.105, 14.83),
    # Four nameplate corners: 6.35-mm stock shank through the .063 (1.6002) plate.
    **numbered_pairs(
        "sh-vn-brass-fillister-screw",
        range(1, 5),
        "fr-harmonic-base",
        smooth_annulus_limit_mm3(2.8448, 2.261, 4.7498),
    ),
}
