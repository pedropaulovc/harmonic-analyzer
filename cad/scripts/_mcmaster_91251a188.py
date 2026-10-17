r"""Pure 91251A188 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91251A188: black-oxide alloy steel socket head screw, US origin,
#8-32 coarse thread, 1-7/8 in long, partly threaded (thread 7/8 in), head
Ø0.27 x 0.164 in, 170,000 psi (https://www.mcmaster.com/91251A188/, read live
2026-10-17 from the #8-32 black-oxide listing; $11.00 per pack of 10). The
thread length is the single-product 1-7/8 filter page's only Thread Length
facet, 7/8 in (0.875 in); the spec table has no thread-length column. The
listing's only drive-size facet at 1-7/8 is 9/64 in.

Every ``DIMS`` field is that live listing's except the socket depth: the
listing gives none, so the socket takes ASME B18.3's minimum key engagement
for #8, 0.077 in (the 91251A108 convention). Class 3A is not modelled (nominal
UN cutter).

STANDARD: ASME B18.3 socket head cap screw length tolerance for screws
through 1 in nominal size, over 1 in to 2-1/2 in long: -0.04 in
(``LENGTH_TOL_MINUS``); a screw is never longer than its nominal length.

No vendor model was downloaded (the CAD and the 2-D drawing are behind the
product page's login), so the recipe has no replica gate and no copy is kept
in the repo.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91251A188"
IN = 25.4
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "#8-32"
LENGTH_TEXT = "1-7/8"
PACK_QUANTITY = 10
PACK_PRICE_USD = 11.00
LENGTH_TOL_MINUS = 0.04 * IN  # ASME B18.3, over 1 in to 2-1/2 in long

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.164 * IN,
    pitch=IN / 32.0,
    length=1.875 * IN,  # under the head
    head_dia=0.27 * IN,
    head_h=0.164 * IN,
    socket_af=9.0 / 64.0 * IN,
    socket_depth=0.077 * IN,  # standard minimum key engagement
    thread_length=0.875 * IN,  # catalogue thread length
)
LENGTH_MIN = DIMS.length - LENGTH_TOL_MINUS
