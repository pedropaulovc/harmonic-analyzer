r"""Pure 91290A148 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91290A148: black-oxide alloy steel socket head screw, M4 x 0.7 mm,
class 5g6g, 12 mm long, fully threaded, head Ø7 x 4 mm, 3 mm hex drive, class
12.9, Rockwell C41, DIN 912 / ISO 4762 (https://www.mcmaster.com/91290A148/,
read live 2026-10-17; $12.30 per pack of 100).

Every ``DIMS`` field is that live catalogue table's except the socket depth:
the page gives none, so the socket takes ISO 4762's minimum key engagement (t
min) for M4, 2.0 mm (the 91251A108 convention). Class 5g6g is not modelled:
the family's 60 deg cutter is ISO 68-1's basic profile as well as UN's, so the
metric size takes it at its pitch.

Vendor model (a reading note, not used): the product page's SLDPRT (SHA-256
``3d13359e07a7c80cc5290dba1a595739c6c5182caec6dd1020aef94b79f7d4a8``) and STEP
(SHA-256
``0d40d024271575266eafd644858489ab44ddf1e7c18a01ee7f782b0cb5bbd7fc``),
downloaded 2026-10-17 and read in FreeCAD 1.1, show a hex socket 3.0 mm deep
and a 72-groove knurled head, 45 deg head edge breaks, a 90 deg socket entry
countersink, an under-head fillet with a 60 deg runout cone and a 0.75H tip
chamfer, none of which the family recipe draws. It is NOT replica-gated (user
ruling 2026-10-17) and no copy is kept in the repo.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91290A148"
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "M4"
LENGTH_TEXT = "12"

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=4.0,
    pitch=0.7,
    length=12.0,  # under the head
    head_dia=7.0,
    head_h=4.0,
    socket_af=3.0,
    socket_depth=2.0,  # standard minimum key engagement
)
