"""Pure 91794A060 fillister dimensions; isolate each SKU's cache inputs.

The recipe models no thread (#2886), so the part saves no supplier
reference dimensions.
"""

# 18-8 stainless #0-80 x 1/2 slotted fillister, ASME B18.6.3 (owner ruling
# 2026-11-26, #3738): same #0-80 head (Ø0.096 x 0.055 in) and thread as
# 91794A055, 1/2 in (12.7 mm) fully threaded under the head.
SKU = "91794A060"
THREAD = "#0-80"
IN = 25.4
SHANK_DIA = 0.060 * IN
SHANK_LEN = 0.500 * IN
HEAD_H = 0.055 * IN
HEAD_DIA = 0.096 * IN
PITCH = IN / 80.0
FILLISTER_SIZE = (SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, PITCH)
