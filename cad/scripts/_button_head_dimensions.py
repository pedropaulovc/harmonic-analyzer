"""Pure button-head dimension laws; separate shared geometry from SKU cache inputs."""

import math
from dataclasses import dataclass

# The 91255A148 vendor-measured proportions (see its module docstring).
FLAT_TOP_PER_HEX_AF = 7.0 / 5.0
BAND_PER_HEAD_H = 0.15
BAND_DEG = 10.0
FILLET_PER_HEAD_H = 0.05
SOCKET_PER_HEAD_H = 0.55
CSK_DEG = 60.0  # draft from the axis


@dataclass(frozen=True, slots=True)
class ButtonHeadScrew:
    """Catalogue dimensions of one button head socket cap screw, in mm."""

    part_no: str
    major_dia: float
    pitch: float
    length: float  # under the head
    head_dia: float
    head_h: float
    hex_af: float

    @property
    def flat_top_dia(self) -> float:
        return FLAT_TOP_PER_HEX_AF * self.hex_af

    @property
    def band_h(self) -> float:
        return BAND_PER_HEAD_H * self.head_h

    @property
    def edge_fillet_r(self) -> float:
        return FILLET_PER_HEAD_H * self.head_h

    @property
    def socket_depth(self) -> float:
        """Flat top to the socket floor."""
        return SOCKET_PER_HEAD_H * self.head_h

    @property
    def tip_chamfer(self) -> float:
        return 0.75 * self.pitch

    @property
    def h_sharp(self) -> float:
        return self.pitch * math.sqrt(3.0) / 2.0

    @property
    def root_r(self) -> float:
        return self.major_dia / 2.0 - 0.75 * self.h_sharp

    @property
    def neck_dia(self) -> float:
        return self.major_dia + self.h_sharp / 4.0

    @property
    def hex_corner_r(self) -> float:
        return self.hex_af / math.sqrt(3.0)

    @property
    def helix_revs(self) -> float:
        return self.length / self.pitch + 1.0

    @property
    def bearing_edge_r(self) -> float:
        """Radius where the band cone meets the bearing face, before the fillet."""
        return self.head_dia / 2.0 - self.band_h * math.tan(math.radians(BAND_DEG))

    @property
    def dome_center_y(self) -> float:
        """The dome's centre on the axis, through the flat top's edge and the
        head OD at the band's top."""
        r1, y1 = self.flat_top_dia / 2.0, self.head_h
        r2, y2 = self.head_dia / 2.0, self.band_h
        return (r1**2 - r2**2 + y1**2 - y2**2) / (2.0 * (y1 - y2))

    @property
    def dome_radius(self) -> float:
        return math.hypot(self.flat_top_dia / 2.0, self.head_h - self.dome_center_y)
