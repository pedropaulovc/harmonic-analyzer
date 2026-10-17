r"""Pure 91251A540 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91251A540: black-oxide alloy steel socket head screw, 1/4-20 UNRC
class 3A, 3/4 in long, fully threaded, head Ø0.375 x 0.25 in, 3/16 in hex
drive, Rockwell C37, 170,000 psi, ASTM A574
(https://www.mcmaster.com/91251A540/, read live 2026-10-17; $12.42 per pack of
50).

Every ``DIMS`` field is that live catalogue table's except the socket depth:
the page gives none, so the socket takes ASME B18.3's minimum key engagement
for 1/4, 0.120 in (the 91251A108 convention). Class 3A is not modelled
(nominal UN cutter).

Vendor model (a reading note, not used): the product page's SLDPRT (SHA-256
``33e4e61fa7b6ca29e8ecb4638d9c99421b83ed0e3a0742ef8500bcd5492fb774``) and STEP
(SHA-256
``94ab0ed5323b88d716ad98a46626d0a9a1bb72a0503eb1d3e343e6bd841c36dd``),
downloaded 2026-10-17 and read in FreeCAD 1.1, show a hex socket 0.125 in deep
and a 50-groove knurled head, a 60 deg socket entry countersink, a 20 deg
thread runout cone and a 0.6P tip chamfer, none of which the family recipe
draws. It is NOT replica-gated (user ruling 2026-10-17) and no copy is kept in
the repo.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91251A540"
IN = 25.4
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "1/4-20"
LENGTH_TEXT = "3/4"

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.25 * IN,
    pitch=IN / 20.0,
    length=0.75 * IN,  # under the head
    head_dia=0.375 * IN,
    head_h=0.25 * IN,
    socket_af=3.0 / 16.0 * IN,
    socket_depth=0.120 * IN,  # standard minimum key engagement
)
