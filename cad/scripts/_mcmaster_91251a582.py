r"""Pure 91251A582 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91251A582: black-oxide alloy steel socket head screw, 5/16-18 UNC
class 3A, 7/8 in long, fully threaded, head Ø0.46875 x 0.3125 in, 1/4 in hex
drive, Rockwell C37, 170,000 psi, ASTM A574
(https://www.mcmaster.com/91251A582/, read live 2026-10-17; $14.48 per pack of
50).

Every ``DIMS`` field is that live catalogue table's except the socket depth:
the page gives none, so the socket takes ASME B18.3's minimum key engagement
for 5/16, 0.151 in (the 91251A108 convention). Class 3A is not modelled
(nominal UN cutter).

Vendor model (a reading note, not used): the product page's SLDPRT (SHA-256
``9feed1cd8f28f698a03478549d6f0a70b5bc99916c1e8199b3d9857b4c99b5c7``) and STEP
(SHA-256
``1e7b1c0ae31b76b34ea88254712024f5851b9fd953af801f633caf292272d940``),
downloaded 2026-10-17 and read in FreeCAD 1.1, show a hex socket 0.15625 in
deep and a 50-groove knurled head, a 60 deg socket entry countersink, a 20 deg
thread runout cone and a 0.6P tip chamfer, none of which the family recipe
draws. It is NOT replica-gated (user ruling 2026-10-17) and no copy is kept in
the repo.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91251A582"
IN = 25.4
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "5/16-18"
LENGTH_TEXT = "7/8"

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.3125 * IN,
    pitch=IN / 18.0,
    length=0.875 * IN,  # under the head
    head_dia=0.46875 * IN,
    head_h=0.3125 * IN,
    socket_af=1.0 / 4.0 * IN,
    socket_depth=0.151 * IN,  # standard minimum key engagement
)
