"""Pure 91251A157 socket-screw dimensions; isolate mechanical cache inputs."""

from _hole_spec import THREAD_MAJOR_MM
from _socket_head_dimensions import SocketHeadScrew


PART_NO = "91251A157"
IN = 25.4

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=THREAD_MAJOR_MM["#6-32"],
    pitch=IN / 32.0,
    length=1.5 * IN,
    head_dia=0.226 * IN,
    head_h=0.138 * IN,
    socket_af=7.0 / 64.0 * IN,
    socket_depth=0.064 * IN,
    thread_length=0.75 * IN,
)
