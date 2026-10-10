"""Catalogue dimensions for the MHA-VN-011 knurled-head thumb screw.

McMaster 91882A221: steel raised knurled-head thumb screw, #4-40 x 7/16".
The values are the ones the recipe table ``diag_mcmaster_thumb.THUMB_SPECS
["91882A221"]`` builds the solid from; ``test_ms_measuring_stick_assembly``
pins the two equal. This module is pure data, so stop and assembly specs can
read the screw without importing the SolidWorks recipe.

Part frame (``build_vn_thumb_screw``): the outer head face lies at X=0, the
axis runs along +X, the collar's bearing face is at X=HEAD_STACK_LEN and the
thread tip at X=HEAD_STACK_LEN + SHANK_LEN.
"""

from __future__ import annotations

SKU = "91882A221"
THREAD = "#4-40"
SHANK_DIA = 2.8448  # #4 major diameter, 0.112 in
PITCH = 25.4 / 40.0
SHANK_LEN = 11.1125  # 7/16 in under the collar
COLLAR_DIA = 6.35
COLLAR_H = 2.38125
HEAD_DIA = 9.525
HEAD_H = 2.38125
HEAD_STACK_LEN = COLLAR_H + HEAD_H
OVERALL_LEN = HEAD_STACK_LEN + SHANK_LEN
