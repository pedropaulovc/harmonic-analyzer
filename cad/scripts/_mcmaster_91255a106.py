"""Pure 91255A106 button-screw dimensions; isolate this SKU's cache inputs."""

from _button_head_dimensions import ButtonHeadScrew

PART_NO = "91255A106"
IN = 25.4

DIMS = ButtonHeadScrew(
    part_no=PART_NO,
    major_dia=0.112 * IN,
    pitch=IN / 40.0,
    length=0.25 * IN,
    head_dia=0.213 * IN,
    head_h=0.059 * IN,
    hex_af=1.0 / 16.0 * IN,
)

if DIMS.flat_top_dia <= 2.0 * DIMS.hex_corner_r:
    raise ValueError("91255A106 flat top no longer covers the hex socket")
if DIMS.head_h - DIMS.socket_depth <= DIMS.band_h:
    raise ValueError("91255A106 socket floor falls into the head's band")
