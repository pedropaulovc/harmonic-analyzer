"""Pure 91251A108 socket-screw dimensions; isolate mechanical cache inputs."""

from _socket_head_dimensions import SocketHeadScrew

PART_NO = "91251A108"
IN = 25.4


DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.112 * IN,
    pitch=IN / 40.0,
    length=0.375 * IN,
    head_dia=0.183 * IN,
    head_h=0.112 * IN,
    socket_af=3.0 / 32.0 * IN,
    socket_depth=0.055 * IN,
)

