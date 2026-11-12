r"""Pure 91251A337 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91251A337: black-oxide alloy steel socket head screw, 10-32 UNF
class 3A, 5/16 in long, fully threaded, head Ø5/16 x 0.19 in, 5/32 in hex
drive, Rockwell C37, 170,000 psi (https://www.mcmaster.com/91251A337/, read
live 2026-11-12; $22.41 per pack of 50).

Every ``DIMS`` field is that live catalogue table's except the socket depth:
the page gives none, so the socket takes ASME B18.3's minimum key engagement
for #10, 0.090 in (the 91251A108 convention). Class 3A is not modelled
(nominal UN cutter). No vendor model was fetched.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91251A337"
IN = 25.4
THREAD = "#10-32"
LENGTH_TEXT = "5/16"
PACK_QUANTITY = 50
# ASME B18.3 socket head cap screw length tolerance to 1 in long: -.03 in.
LENGTH_SHORT = 0.03 * IN

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.190 * IN,
    pitch=IN / 32.0,
    length=0.3125 * IN,  # under the head
    head_dia=0.3125 * IN,
    head_h=0.19 * IN,
    socket_af=5.0 / 32.0 * IN,
    socket_depth=0.090 * IN,  # standard minimum key engagement
)
