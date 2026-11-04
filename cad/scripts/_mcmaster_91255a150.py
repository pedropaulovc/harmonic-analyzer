"""Pure 91255A150 button-screw dimensions; isolate this SKU's cache inputs.

Catalogue (https://www.mcmaster.com/91255A150/, read live 2026-11-04):
"Black-Oxide Button Head Hex-Drive Screw, Alloy Steel, 6-32 Thread Size,
5/8" Long"; head Ø0.262 x 0.073 in, 5/64 in hex drive, fully threaded,
140,000 psi tensile, Rockwell C39, class 3A, ASME B18.3 / ASTM F835, $18.56
per pack of 100. Its head and drive are the replica-gated 91255A148's (the
1/2 in length of the same series, ``diagnostics/diag_build_91255A148.py``),
so ``ButtonHeadScrew``'s law is that screw's own.
"""

from _button_head_dimensions import ButtonHeadScrew

PART_NO = "91255A150"
IN = 25.4
THREAD = "#6-32"
LENGTH_TEXT = "5/8"
PACK_QUANTITY = 100
TENSILE_PSI = 140_000

DIMS = ButtonHeadScrew(
    part_no=PART_NO,
    major_dia=0.138 * IN,
    pitch=IN / 32.0,
    length=0.625 * IN,
    head_dia=0.262 * IN,
    head_h=0.073 * IN,
    hex_af=5.0 / 64.0 * IN,
)

if DIMS.flat_top_dia <= 2.0 * DIMS.hex_corner_r:
    raise ValueError("91255A150 flat top no longer covers the hex socket")
if DIMS.head_h - DIMS.socket_depth <= DIMS.band_h:
    raise ValueError("91255A150 socket floor falls into the head's band")
