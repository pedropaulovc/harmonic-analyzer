r"""Pure 91290A115 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91290A115: black-oxide alloy steel socket head screw, M3 x 0.5 mm,
class 5g6g, 10 mm long, fully threaded, head Ø5.5 x 3 mm, 2.5 mm hex drive,
class 12.9, Rockwell C41, DIN 912 / ISO 4762
(https://www.mcmaster.com/91290A115/, read live 2026-10-17; $13.23 per pack of
100).

Every ``DIMS`` field is that live catalogue table's except the socket depth:
the page gives none, so the socket takes ISO 4762's minimum key engagement (t
min) for M3, 1.3 mm (the 91251A108 convention). Class 5g6g is not modelled:
the family's 60 deg cutter is ISO 68-1's basic profile as well as UN's, so the
metric size takes it at its pitch.

Vendor model (a reading note, not used): the product page's SLDPRT (SHA-256
``bf8dce120aa6a6cc3414fbd419b233e3053241103812254828656946033dedd3``) and STEP
(SHA-256
``f33505b4b05370d959ec6f94d8770c8676f745e50dab9e06814cc470c8dcd88e``),
downloaded 2026-10-17 and read in FreeCAD 1.1, show a hex socket 2.0 mm deep
and a 72-groove knurled head, 45 deg head edge breaks, a 90 deg socket entry
countersink, an under-head fillet with a 60 deg runout cone and a 0.75H tip
chamfer, none of which the family recipe draws. It is NOT replica-gated (user
ruling 2026-10-17) and no copy is kept in the repo.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91290A115"
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "M3"
LENGTH_TEXT = "10"

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=3.0,
    pitch=0.5,
    length=10.0,  # under the head
    head_dia=5.5,
    head_h=3.0,
    socket_af=2.5,
    socket_depth=1.3,  # standard minimum key engagement
)
