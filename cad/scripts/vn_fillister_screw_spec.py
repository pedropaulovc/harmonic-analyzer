r"""Purchased brass fillister screw (McMaster 90114A511) nominals.

PURE DATA, no SolidWorks/COM calls or native recipe in its import closure.
This module owns the brass vendor-model scalars and the shared fillister
catalogue table. The native recipes consume these values, not the other way
round. Existing SKU-specific pure specs retain ownership of their rows.
The platen, clip, guide, guide lock, harmonic base and assemblies read the
brass head/shank nominals here without importing a stock build recipe (#880).
"""

from __future__ import annotations

import vn_frame_cross_screw_spec as cross_screw
import vn_slotted_screw_spec as block_screw
from vn_swing_stop_screw_spec import FILLISTER_SIZE as stop_screw_size


BF_MAJOR_R = 2.8448 / 2.0
BF_LEN = 6.35
BF_HH = 2.7178
BF_HEAD_R = 4.6482 / 2.0
BF_PITCH = 0.635
BF_SLOT_W = 0.9906   # Slot Width@Sketch1
BF_SLOT_D = 1.2192   # Slot Depth@Sketch1


FILLISTER_SIZES = {
    # part:        (major dia, length, head height, head dia, pitch)
    "90280A108": stop_screw_size,
    "90280A194": (4.1656, 12.7, 3.9624, 6.858, 0.79375),
    "90280A197": (4.1656, 19.05, 3.9624, 6.858, 0.79375),
    "90280A199": (4.1656, 25.4, 3.9624, 6.858, 0.79375),
    "90280A201": (4.1656, 31.75, 3.9624, 6.858, 0.79375),
    # Live McMaster product table, 2026-10-08: #8-32 x 1-1/2, same head.
    "90280A203": (
        block_screw.SHANK_DIA,
        block_screw.SHANK_LEN,
        block_screw.HEAD_H,
        block_screw.HEAD_DIA,
        block_screw.PITCH,
    ),
    "90280A837": (
        cross_screw.SHANK_DIA,
        cross_screw.SHANK_LEN,
        cross_screw.HEAD_H,
        cross_screw.HEAD_DIA,
        cross_screw.PITCH,
    ),
    # 18-8 stainless fillister, the same 0.183 x 0.107 #4-40 head (McMaster
    # 91794A product table, read 2026-09-25).
    "91794A112": (2.8448, 15.875, 2.7178, 4.6482, 0.635),
    # 18-8 stainless #2-56 x 1/4, live product page and technical drawing
    # read 2026-10-08. Derived family details are not vendor-verified.
    "91794A077": (2.1844, 6.35, 2.1082, 3.556, 25.4 / 56.0),
    # 18-8 stainless fillister, 0-80 x 1/4, high narrow head 0.096 x 0.055,
    # fully threaded (McMaster 91794A055 product page, read 2026-09-30).
    # Sizes only: its vendor model is a different tree (drafted head, neck,
    # tip-seeded thread), so diag_build_91794A055 builds it, not
    # build_fillister.
    "91794A055": (1.524, 6.35, 1.397, 2.4384, 25.4 / 80.0),
    # Value Collection MSC 40923906, 1/4-20 x 4 in slotted fillister,
    # SAE J82 steel, zinc.  Catalog-only ideal model: the existing ASME
    # B18.6.3 1/4 maxima (A 0.414, O 0.237) and family geometry laws, not
    # vendor CAD or a measured replica.  The full-shank modeled thread does
    # not verify the supplier's threaded length.  MHA-VN-031 cuts the
    # supplied 4 in stock to fit; never change this row to its cut length.
    "40923906": (6.35, 4.0 * 25.4, 0.237 * 25.4, 0.414 * 25.4, 25.4 / 20.0),
}


THREAD = "#4-40"
HEAD_DIA = 2.0 * BF_HEAD_R
HEAD_H = BF_HH
SHANK_DIA = 2.0 * BF_MAJOR_R
SHANK_LEN = BF_LEN
