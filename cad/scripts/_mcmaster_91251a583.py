r"""Pure 91251A583 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91251A583: black-oxide alloy steel socket head screw, 5/16-18 UNC,
1 in long, fully threaded, head Ø15/32 x 5/16 in, 170,000 psi
(https://www.mcmaster.com/products/socket-head-screws/thread-size~5-16-18/steel-socket-head-screws~~/length~1/,
the 5/16-18 x 1 in listing row read live 2026-10-17; $15.30 per pack of 50;
the product page is login-walled). The family's 1/4 in hex drive, class 3A,
Rockwell C37 and ASTM A574 are the 91251A582 (7/8 in) page's, read live the
same day; the listing row does not repeat them.

Every ``DIMS`` field is that live catalogue row's except the socket: the
listing gives no socket, so the socket takes the family's 1/4 in hex and
ASME B18.3's minimum key engagement for 5/16, 0.151 in (the 91251A108
convention). Class 3A is not modelled (nominal UN cutter).

STANDARD: ASME B18.3 socket head cap screw length tolerance for screws
through 1 in nominal size, up to 1 in long: -0.03 in (``LENGTH_TOL_MINUS``);
a screw is never longer than its nominal length.

No vendor model was downloaded for this length (the product page is
login-walled). The 7/8 in sibling's (91251A582, downloaded 2026-10-17 and
read in FreeCAD 1.1) shows a hex socket 0.15625 in deep and a 50-groove
knurled head, a 60 deg socket entry countersink, a 20 deg thread runout cone
and a 0.6P tip chamfer, none of which the family recipe draws. It is NOT
replica-gated (user ruling 2026-10-17) and no copy is kept in the repo.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91251A583"
IN = 25.4
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "5/16-18"
LENGTH_TEXT = "1"
PACK_QUANTITY = 50
PACK_PRICE_USD = 15.30
LENGTH_TOL_MINUS = 0.03 * IN  # ASME B18.3, up to 1 in long

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.3125 * IN,
    pitch=IN / 18.0,
    length=1.0 * IN,  # under the head
    head_dia=0.46875 * IN,
    head_h=0.3125 * IN,
    socket_af=1.0 / 4.0 * IN,
    socket_depth=0.151 * IN,  # standard minimum key engagement
)
LENGTH_MIN = DIMS.length - LENGTH_TOL_MINUS
