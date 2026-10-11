"""Pure 91255A108 button-screw dimensions; isolate this SKU's cache inputs."""

from _button_head_dimensions import ButtonHeadScrew

PART_NO = "91255A108"
IN = 25.4

DIMS = ButtonHeadScrew(
    part_no=PART_NO,
    major_dia=0.112 * IN,
    pitch=IN / 40.0,
    length=0.375 * IN,
    head_dia=0.213 * IN,
    head_h=0.059 * IN,
    hex_af=1.0 / 16.0 * IN,
)
