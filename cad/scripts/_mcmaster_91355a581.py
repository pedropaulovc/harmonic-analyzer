r"""Pure 91355A581 flanged button-screw dimensions; isolate this SKU's cache inputs.

McMaster 91355A581: black-oxide alloy steel flanged button head hex drive
screw, #4-40 UNC class 3A, right hand, 3/4 in under the head, fully
threaded, flat tip; button head Ø0.193 x 0.059 in high (the height includes
the flange), flange Ø0.234, 1/16 in hex drive; 120,000 psi, Rockwell C39,
ASTM F835, US origin; $15.93 per pack of 100. SOURCED: the product page
https://www.mcmaster.com/91355A581/ read live in a headless browser on
2026-11-02 (and its row in the 4-40 flanged button head listing,
https://www.mcmaster.com/products/flanged-button-head-screws/thread-size~4-40/).

Measured from the vendor STEP (the page's free 3-D STEP, read 2026-11-02,
SHA-256 fb11dbce2c9adce8fba6469c344020b1d238337763c22215e3f85afced460aa7;
not committed), headless OCP: the flange is 0.024 in thick (``FLANGE_H``);
its flat underside ends at Ø0.2224 before the edge round, so the bearing
face is taken as Ø0.222 (``BEARING_DIA_MIN``: the page prints no flange
tolerance); the underhead fillet (R.010) meets the bearing face at Ø0.132.

STANDARD: ASME B18.3 length tolerance through 1 in: -0.03 in
(``LENGTH_TOL_MINUS``); a screw is never longer than nominal. The page and
the standard give no underhead transition bound for this head, so
``FILLET_DIA_MAX`` takes B18.3 Table 1's #4 socket head cap screw
transition diameter, 0.141 in max, over the vendor model's Ø0.132
[ASSUMPTION].

The recipe is the button head family's catalogue envelope
(``diag_mcmaster_button_head``) with a square-edged flange; no replica gate.
"""

from _button_head_dimensions import ButtonHeadScrew

PART_NO = "91355A581"
IN = 25.4
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "#4-40"
LENGTH_TEXT = "3/4"
PACK_QUANTITY = 100
PACK_PRICE_USD = 15.93
LENGTH_TOL_MINUS = 0.03 * IN  # ASME B18.3, up to 1 in long
FLANGE_H = 0.024 * IN  # vendor STEP
BEARING_DIA_MIN = 0.222 * IN  # vendor STEP: the flange's flat underside
FILLET_DIA_MAX = 0.141 * IN  # ASME B18.3 Table 1's #4 SHCS bound [ASSUMPTION]

DIMS = ButtonHeadScrew(
    part_no=PART_NO,
    major_dia=0.112 * IN,
    pitch=IN / 40.0,
    length=3.0 / 4.0 * IN,  # under the head
    head_dia=0.193 * IN,
    head_h=0.059 * IN,  # includes the flange
    hex_af=1.0 / 16.0 * IN,
    flange_dia=0.234 * IN,
    flange_h=FLANGE_H,
)
LENGTH_MIN = DIMS.length - LENGTH_TOL_MINUS

if DIMS.flat_top_dia <= 2.0 * DIMS.hex_corner_r:
    raise ValueError("91355A581 flat top no longer covers the hex socket")
if DIMS.head_h - DIMS.socket_depth <= DIMS.band_h:
    raise ValueError("91355A581 socket floor falls into the flange")
if not FILLET_DIA_MAX < BEARING_DIA_MIN < DIMS.flange_dia:
    raise ValueError("91355A581 bearing face is not between its fillet and flange")
