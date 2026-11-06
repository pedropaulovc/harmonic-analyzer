r"""Pure 92220A165 socket-screw dimensions; isolate this SKU's cache inputs.

McMaster 92220A165: alloy steel low-profile socket head screw, black-oxide,
#10-24 UNC class 3A right hand, 3/4 in long (measured from under the head),
fully threaded, head Ø5/16 x 3/32 in, 3/32 in hex drive, 140,000 psi,
Rockwell C39, ASME B18.3, flat tip (https://www.mcmaster.com/92220A165/, read
live 2026-11-06; $11.38 per pack of 50).

Every ``DIMS`` field is that live catalogue table's except the socket depth:
the page gives none, so the socket takes ASME B18.3's minimum key engagement
for the #10 low head, 0.072 in (Brighton-Best "Socket Low Head Cap Screws"
product data sheet, ASME B18.3 key-dimension table, read 2026-11-06; the
91251A108 convention).  Class 3A is not modelled (nominal UN cutter).  No
vendor model was downloaded: the geometry is the 91251A family's catalogue
recipe, not a STEP measurement.
"""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "92220A165"
IN = 25.4
# The catalogue's designation, as the C4 fastener table prints it.
THREAD = "#10-24"
LENGTH_TEXT = "3/4"

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.19 * IN,
    pitch=IN / 24.0,
    length=0.75 * IN,  # under the head
    head_dia=5.0 / 16.0 * IN,
    head_h=3.0 / 32.0 * IN,
    socket_af=3.0 / 32.0 * IN,
    socket_depth=0.072 * IN,  # standard minimum key engagement
)
