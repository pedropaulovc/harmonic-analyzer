r"""Pure 91251A197 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91251A197: black-oxide alloy steel socket head screw, #8-32 UNC class
3A, 3/4 in long, fully threaded, head Ø0.27 x 0.164 in, 9/64 in hex drive,
Rockwell C37, 170,000 psi, ASTM A574 (https://www.mcmaster.com/91251A197/,
read live 2026-10-17; $18.68 per pack of 100).

Every ``DIMS`` field is that live catalogue table's except the socket depth:
the page gives none, so the socket takes ASME B18.3's minimum key engagement
for #8, 0.077 in (the 91251A108 convention). Class 3A is not modelled (nominal
UN cutter).

Vendor model (a reading note, not used): the product page's SLDPRT (SHA-256
``8f52201b526d02bbf56d11bebc85a329a141aade6b1b2a19bc9b0f707f8281b5``) and STEP
(SHA-256
``1ec8f71f860a945f6539b8540838c38dee0ea6c793ef68ca1b8b378ff64be3e5``),
downloaded 2026-10-17 and read in FreeCAD 1.1, show a hex socket 0.082 in deep
and a 50-groove knurled head, a 60 deg socket entry countersink, a 20 deg
thread runout cone and a 0.6P tip chamfer, none of which the family recipe
draws. It is NOT replica-gated (user ruling 2026-10-17) and no copy is kept in
the repo.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91251A197"
IN = 25.4
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "#8-32"
LENGTH_TEXT = "3/4"

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.164 * IN,
    pitch=IN / 32.0,
    length=0.75 * IN,  # under the head
    head_dia=0.27 * IN,
    head_h=0.164 * IN,
    socket_af=9.0 / 64.0 * IN,
    socket_depth=0.077 * IN,  # standard minimum key engagement
)
