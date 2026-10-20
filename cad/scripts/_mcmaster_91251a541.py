r"""Pure 91251A541 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 91251A541: black-oxide alloy steel socket head screw, 1/4"-20 UNRC
class 3A right hand, 7/8 in long (measured from under the head), fully
threaded, head Ø3/8 x 1/4 in, 3/16 in hex drive, Rockwell C37, 170,000 psi,
ASTM A574, tip type flat (https://www.mcmaster.com/91251A541/, read live
2026-10-19; $13.42 per pack of 50).

Every ``DIMS`` field is that live catalogue table's except the socket depth:
the page gives none, so the socket takes ASME B18.3's minimum key engagement
for 1/4, 0.120 in (the 91251A108 convention). Class 3A is not modelled
(nominal UN cutter). No vendor model was downloaded for this size: the
geometry is the 91251A family's catalogue recipe, not a STEP measurement.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91251A541"
IN = 25.4
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "1/4-20"
LENGTH_TEXT = "7/8"

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.25 * IN,
    pitch=IN / 20.0,
    length=0.875 * IN,  # under the head
    head_dia=0.375 * IN,
    head_h=0.25 * IN,
    socket_af=3.0 / 16.0 * IN,
    socket_depth=0.120 * IN,  # standard minimum key engagement
)
