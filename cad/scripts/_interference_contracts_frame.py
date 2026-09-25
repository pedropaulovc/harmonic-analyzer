"""Intended-fit interference contracts for the frame assembly.

Read by ``build_frame_assembly`` directly, so only that assembly's recipe
carries the geometry these limits are computed from; ``verify.py`` reaches the
same table through ``_interference_contracts.allowed_interference_pairs``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from _interference_contracts import numbered_pairs, smooth_annulus_limit_mm3
from build_harmonic_base import (
    HOLD_DOWN_ENGAGEMENT as _HOLD_DOWN_ENGAGEMENT,
    HOLD_DOWN_TAP_DRILL_DIA as _HOLD_DOWN_TAP_DRILL_DIA,
    HOLD_DOWN_THREAD as _HOLD_DOWN_THREAD,
)
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM
from frame_attachment_spec import COLUMN_SOCKET_DIAMETER
from frame_cross_screw_spec import SHANK_DIA as _FRAME_CROSS_DIA
from frame_cross_screw_spec import SHANK_LEN as _FRAME_CROSS_LENGTH
from frame_cross_screw_spec import THREAD as _FRAME_CROSS_THREAD


# Minimum socket chord across the screw's complete major-diameter envelope.
# Only the two tapped casting lands may overlap the stock helical thread.
# Neither the clearance-drilled tubes nor the cap skirts receive an exemption.
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
        "lag-screw",
        range(1, 5),
        "harmonic-base",
        smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM[_HOLD_DOWN_THREAD],
            _HOLD_DOWN_TAP_DRILL_DIA,
            _HOLD_DOWN_ENGAGEMENT,
        ),
    ),
    **numbered_pairs(
        "frame-cross-screw",
        range(1, 5),
        "harmonic-base",
        _FRAME_CROSS_GATE_LIMIT_MM3,
    ),
    **numbered_pairs(
        "frame-cross-screw",
        range(5, 9),
        "top-frame",
        _FRAME_CROSS_GATE_LIMIT_MM3,
    ),
    frozenset(("gooseneck-set-screw-1", "top-frame-1")): smooth_annulus_limit_mm3(
        6.35, 5.105, 6.95
    ),
    # Four nameplate corners: 6.35-mm stock shank through the 1.5-mm plate.
    **numbered_pairs(
        "fillister-screw",
        range(1, 5),
        "harmonic-base",
        smooth_annulus_limit_mm3(2.8448, 2.261, 4.85),
    ),
}
