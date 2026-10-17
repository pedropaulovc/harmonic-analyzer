r"""Pure 91290A168 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91290A168: black-oxide alloy steel socket head screw, M4 x 0.7 mm,
class 5g6g, 20 mm long, fully threaded, head Ø7 x 4 mm, 3 mm hex drive, class
12.9, Rockwell C41, DIN 912 / ISO 4762 (https://www.mcmaster.com/91290A168/,
read live 2026-10-17; $14.47 per pack of 100).

Every ``DIMS`` field is that live catalogue table's except the socket depth:
the page gives none, so the socket takes ISO 4762's minimum key engagement (t
min) for M4, 2.0 mm (the 91251A108 convention). Class 5g6g is not modelled:
the family's 60 deg cutter is ISO 68-1's basic profile as well as UN's, so the
metric size takes it at its pitch.

Vendor model (a reading note, not used): the product page's SLDPRT (SHA-256
``d95f5c3556da2eb440809a63d8e4511e9bf35dba2e57dafa8c55c9c5bc2a1e10``) and STEP
(SHA-256
``8673cceae9ae657b9f1123f3cc019893698c47f39fcc0a5c376aee0c8cc3cf71``),
downloaded 2026-10-17 and read in FreeCAD 1.1, show a hex socket 3.0 mm deep
and a 72-groove knurled head, 45 deg head edge breaks, a 90 deg socket entry
countersink, an under-head fillet with a 60 deg runout cone and a 0.75H tip
chamfer, none of which the family recipe draws. It is NOT replica-gated (user
ruling 2026-10-17) and no copy is kept in the repo.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91290A168"
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "M4"
LENGTH_TEXT = "20"

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=4.0,
    pitch=0.7,
    length=20.0,  # under the head
    head_dia=7.0,
    head_h=4.0,
    socket_af=3.0,
    socket_depth=2.0,  # standard minimum key engagement
)
