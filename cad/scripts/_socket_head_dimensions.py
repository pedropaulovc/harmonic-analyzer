"""Pure socket-head screw dimension record, shared by catalogue sizes."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SocketHeadScrew:
    """Catalogue dimensions of one socket head cap screw, in mm.

    ``thread_length`` is the catalogue minimum thread length from the tip;
    None means fully threaded to the head.
    """

    part_no: str
    major_dia: float
    pitch: float
    length: float  # under the head
    head_dia: float
    head_h: float
    socket_af: float
    socket_depth: float
    thread_length: float | None = None

    def __post_init__(self) -> None:
        if 2.0 * self.socket_corner_r >= self.head_dia:
            raise ValueError(f"{self.part_no} socket corners break out of the head")
        if self.socket_depth >= self.head_h:
            raise ValueError(f"{self.part_no} socket floor falls through the head")
        if self.thread_length is not None and not (
            self.neck_h < self.thread_length < self.length
        ):
            raise ValueError(
                f"{self.part_no} thread length {self.thread_length} is not a"
                f" partial thread of the {self.length} shank"
            )

    @property
    def underside_y(self) -> float:
        """The bearing face sits on the origin."""
        return 0.0

    @property
    def top_y(self) -> float:
        return self.underside_y + self.head_h

    @property
    def tip_y(self) -> float:
        return self.underside_y - self.length

    @property
    def fully_threaded(self) -> bool:
        return self.thread_length is None

    @property
    def threaded_length(self) -> float:
        """Thread length from the tip: the whole shank when fully threaded."""
        return self.length if self.thread_length is None else self.thread_length

    @property
    def thread_top_y(self) -> float:
        """Where the thread ends: the bearing face when fully threaded."""
        return self.tip_y + self.threaded_length

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
        """The 45 deg cone's start at the thread top: the sharp V's crest line
        (major + H/4) under a head, the plain shank's major on a partial
        thread (no lip above the runout)."""
        if self.fully_threaded:
            return self.major_dia + self.h_sharp / 4.0
        return self.major_dia

    @property
    def neck_h(self) -> float:
        """Depth of the 45 deg cone below the thread top, to the root."""
        return self.neck_dia / 2.0 - self.root_r

    @property
    def socket_corner_r(self) -> float:
        return self.socket_af / math.sqrt(3.0)

    @property
    def helix_revs(self) -> float:
        return self.threaded_length / self.pitch + 1.0
