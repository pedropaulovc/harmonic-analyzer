r"""Pure 91251A113 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91251A113: black-oxide alloy steel socket head screw, US origin,
#4-40 UNC, 3/4 in long, fully threaded, head Ø0.183 x 0.112 in, 170,000 psi
(https://www.mcmaster.com/products/socket-head-screws/steel-socket-head-screws~~/thread-size~4-40/finish~black-oxide/,
the #4-40 x 3/4 in black-oxide listing row read live 2026-11-01; $12.19 per
pack of 100). The product page https://www.mcmaster.com/91251A113/ answered
HTTP 200 on 2026-11-01 titled "Black-Oxide Alloy Steel Socket Head Screw, US
Origin, 4-40 Thread Size, 3/4" Long"; its detail and CAD are login-walled.

Every ``DIMS`` field is that live listing's except the drive and the socket
depth: the row gives neither, so they take the family's #4 values, the
3/32 in hex and ASME B18.3's minimum key engagement for #4, 0.055 in (the
91251A108 convention). Class 3A is not modelled (nominal UN cutter).

STANDARD: ASME B18.3 Table 1, #4 socket head cap screw: head diameter
0.176 in min (``HEAD_DIA_MIN``, the bearing bound) and the underhead
transition diameter 0.141 in max (``FILLET_DIA_MAX``, which must seat inside
the clearance hole); length tolerance for screws through 1 in nominal size,
up to 1 in long: -0.03 in (``LENGTH_TOL_MINUS``); a screw is never longer
than its nominal length.

No vendor model was downloaded (the product page is login-walled), so the
recipe has no replica gate and no copy is kept in the repo.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91251A113"
IN = 25.4
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "#4-40"
LENGTH_TEXT = "3/4"
PACK_QUANTITY = 100
PACK_PRICE_USD = 12.19
LENGTH_TOL_MINUS = 0.03 * IN  # ASME B18.3, up to 1 in long
HEAD_DIA_MIN = 0.176 * IN  # ASME B18.3 Table 1, A min
FILLET_DIA_MAX = 0.141 * IN  # ASME B18.3 Table 1, transition diameter max

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.112 * IN,
    pitch=IN / 40.0,
    length=3.0 / 4.0 * IN,  # under the head
    head_dia=0.183 * IN,
    head_h=0.112 * IN,
    socket_af=3.0 / 32.0 * IN,
    socket_depth=0.055 * IN,  # standard minimum key engagement
)
LENGTH_MIN = DIMS.length - LENGTH_TOL_MINUS
