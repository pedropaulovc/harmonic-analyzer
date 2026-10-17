r"""Pure 91251A196 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91251A196: black-oxide alloy steel socket head screw, #8-32 UNC class
3A, 5/8 in long, fully threaded, head Ø0.27 x 0.164 in, 9/64 in hex drive,
Rockwell C37, 170,000 psi, ASTM A574 (https://www.mcmaster.com/91251A196/,
read live 2026-10-17; $15.24 per pack of 100).

Every ``DIMS`` field is that live catalogue table's except the socket depth:
the page gives none, so the socket takes ASME B18.3's minimum key engagement
for #8, 0.077 in (the 91251A108 convention). Class 3A is not modelled (nominal
UN cutter).

Vendor model (a reading note, not used): the product page's SLDPRT (SHA-256
``e7fe3961d447b3123ad067dc87db8d863b4452732368037f7d8080202bd771bb``) and STEP
(SHA-256
``5b6fb26efa1d652c8b52dd69570b3851c7ceb2381af3ce16cb2571f7f3610924``),
downloaded 2026-10-17 and read in FreeCAD 1.1, show a hex socket 0.082 in deep
and a 50-groove knurled head, a 60 deg socket entry countersink, a 20 deg
thread runout cone and a 0.6P tip chamfer, none of which the family recipe
draws. It is NOT replica-gated (user ruling 2026-10-17) and no copy is kept in
the repo.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91251A196"
IN = 25.4
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "#8-32"
LENGTH_TEXT = "5/8"

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.164 * IN,
    pitch=IN / 32.0,
    length=0.625 * IN,  # under the head
    head_dia=0.27 * IN,
    head_h=0.164 * IN,
    socket_af=9.0 / 64.0 * IN,
    socket_depth=0.077 * IN,  # standard minimum key engagement
)
