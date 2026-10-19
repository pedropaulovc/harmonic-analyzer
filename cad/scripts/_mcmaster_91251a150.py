r"""Pure 91251A150 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91251A150: black-oxide alloy steel socket head screw, US origin,
#6-32 UNC, 5/8 in long, fully threaded, head Ø0.226 x 0.138 in, 170,000 psi
(https://www.mcmaster.com/products/socket-head-screws/steel-socket-head-screws~~/thread-size~6-32/finish~black-oxide/length~5-8-1/,
the #6-32 x 5/8 in black-oxide listing row read live 2026-10-19; $12.27 per
pack of 100; the product page is login-walled).

Every ``DIMS`` field is that live listing's except the drive and the socket
depth: the row gives neither, so the socket takes the family's #6 hex, 7/64
in (91251A148's listing), and ASME B18.3's minimum key engagement for #6,
0.064 in (the 91251A108 convention). Class 3A is not modelled (nominal UN
cutter).

STANDARD: ASME B18.3 socket head cap screw length tolerance for screws
through 1 in nominal size, up to 1 in long: -0.03 in (``LENGTH_TOL_MINUS``);
a screw is never longer than its nominal length.

No vendor model was downloaded (the product page is login-walled), so the
recipe has no replica gate and no copy is kept in the repo.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91251A150"
IN = 25.4
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "#6-32"
LENGTH_TEXT = "5/8"
PACK_QUANTITY = 100
PACK_PRICE_USD = 12.27
LENGTH_TOL_MINUS = 0.03 * IN  # ASME B18.3, up to 1 in long

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.138 * IN,
    pitch=IN / 32.0,
    length=5.0 / 8.0 * IN,  # under the head
    head_dia=0.226 * IN,
    head_h=0.138 * IN,
    socket_af=7.0 / 64.0 * IN,
    socket_depth=0.064 * IN,  # standard minimum key engagement
)
LENGTH_MIN = DIMS.length - LENGTH_TOL_MINUS
