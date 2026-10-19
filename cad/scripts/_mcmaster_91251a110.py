r"""Pure 91251A110 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91251A110: black-oxide alloy steel socket head screw, #4-40 UNC,
1/2 in long, fully threaded, head Ø0.183 x 0.112 in, 170,000 psi
(https://www.mcmaster.com/products/socket-head-screws/steel-socket-head-screws~~/thread-size~4-40/finish~black-oxide/length~1-2-2/,
the #4-40 x 1/2 in black-oxide listing row read live 2026-10-19; $12.26 per
pack of 100; the product page is login-walled).

Every ``DIMS`` field is that live listing's except the drive and the socket
depth: the row gives neither, so the socket takes the family's #4 hex, 3/32 in
(91251A108's), and ASME B18.3's minimum key engagement for #4, 0.051 in (the
standard's table, read live 2026-10-19). Class 3A is not modelled (nominal UN
cutter).

STANDARD: ASME B18.3 socket head cap screw length tolerance for screws
through 1 in nominal size, up to 1 in long: -0.03 in (``LENGTH_TOL_MINUS``);
a screw is never longer than its nominal length. The head's least diameter is
the standard's, 0.176 in for #4 (``HEAD_DIA_MIN``; the listing gives the
nominal only).

No vendor model was downloaded (the product page is login-walled), so the
recipe has no replica gate and no copy is kept in the repo.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91251A110"
IN = 25.4
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "#4-40"
LENGTH_TEXT = "1/2"
PACK_QUANTITY = 100
PACK_PRICE_USD = 12.26
LENGTH_TOL_MINUS = 0.03 * IN  # ASME B18.3, up to 1 in long
HEAD_DIA_MIN = 0.176 * IN  # ASME B18.3, #4

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.112 * IN,
    pitch=IN / 40.0,
    length=0.5 * IN,  # under the head
    head_dia=0.183 * IN,
    head_h=0.112 * IN,
    socket_af=3.0 / 32.0 * IN,
    socket_depth=0.051 * IN,  # standard minimum key engagement
)
LENGTH_MIN = DIMS.length - LENGTH_TOL_MINUS
