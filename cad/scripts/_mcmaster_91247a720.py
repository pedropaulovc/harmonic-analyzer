"""Pure McMaster 91247A720 dimensions for the diagnostic replica.

Separate from the diagnostic COM recipe to limit cache blast radius.
"""

from __future__ import annotations

GB_MAJOR_R = 12.7 / 2.0
GB_LEN = 50.8
GB_HW = 19.05
GB_HH = 7.9375
GB_PITCH = 25.4 / 13.0  # stored 1.953846
GB_MTL = 31.75
GB_UNDERSIDE = 21.43125  # (L + HH)/2 - HH
GB_WASHER_T = 0.2


HEAD_AF = GB_HW
HEAD_H = GB_HH
SHANK_DIA = 2.0 * GB_MAJOR_R
SHANK_LEN = GB_LEN
UNDERHEAD_LEN = GB_LEN - GB_WASHER_T
