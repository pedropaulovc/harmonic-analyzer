r"""Pure Phillips flat (82 deg countersunk) head machine screw record.

For McMaster's ASME B18.6.3 Phillips flat head machine screws (91771A, 18-8
stainless).  ``diagnostics/diag_mcmaster_oval.py`` draws a slotted, crowned
oval head and cannot express a flat top with a cross recess, so this record
and ``diagnostics/diag_mcmaster_phillips_flat_head.py`` carry the family.
Catalogue first: the head diameter, the 82 deg angle, the overall length,
the thread and the head height are the catalogue's; the forms below that the
catalogue does not state were read off McMaster's 91771A110 model (its STEP
in FreeCAD 1.1, 2026-10-17; not replica-gated, user ruling 2026-10-17; the
per-SKU module labels each such value):

* head: a sharp flat top of diameter ``head_dia`` (no rim land), then the
  82 deg cone (41 deg to the axis) down to the thread major;
* thread: the family 60 deg cutter (crest flat P/8 at the major, root flat
  P/8 at major/2 - 0.75H) on a tip-seeded helix, cut on the shank only and
  ending in a flat face ``thread_top_depth`` below the top (91771A110: the
  catalogue's 0.067 in head height), below the cone-to-shank junction; no
  runout;
* tip: 45 deg x ``tip_chamfer`` (radial);
* Phillips recess: every wall a plane at ``recess_draft_deg`` to the axis,
  narrowing downward -- four wings, each between two planes
  ``wing_half_width`` off its centre line at the top, and between each pair
  of adjacent wings a V notch of two planes ``web_distance`` from the axis at
  the top, each running from one wing's side to the diagonal with its normal
  22.5 deg off the other wing -- bounded by a vertical entry cylinder of radius
  ``entry_r`` and below it by a ``recess_cone_semi_deg`` cone whose apex is
  ``recess_depth`` below the top.

Frame: axis +Y, head up, the flat top at y = 0 (``seated_recess`` gives its
nominal depth below a matching countersink's mouth), the tip at y = -length.
McMaster measures a flat head's length overall, top to tip, so ``length`` is
that.

Profiles are pure tuples, (radius, y) in mm on the Front sketch, ``(p0, p1)``
line pairs listed in order (``revolved_volume`` integrates them).  The recess
outline is in the top-plane sketch's own (x, y); it is symmetric under the
square's rotations and reflections, so the sketch's axis directions do not
matter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]

# The wings' sketched ends stand this far past the entry cylinder, so the
# drafted wing still reaches the cylinder at the foot of the entry; the
# refill revolve puts the excess back.
WING_REACH_MARGIN = 0.2


def _loop(points: tuple[Point, ...]) -> tuple[tuple[Point, Point], ...]:
    return tuple(zip(points, points[1:] + points[:1]))


def revolved_volume(loop: tuple[tuple[Point, Point], ...]) -> float:
    """Exact volume of a closed (radius, y) line loop revolved about the y axis."""
    total = sum(
        (y1 - y0) * (x0 * x0 + x0 * x1 + x1 * x1) / 3.0 for (x0, y0), (x1, y1) in loop
    )
    return abs(math.pi * total)


@dataclass(frozen=True, slots=True)
class PhillipsFlatHeadScrew:
    """Catalogue and vendor-model dimensions of one Phillips flat head
    machine screw, in mm."""

    part_no: str
    major_dia: float
    pitch: float
    length: float  # overall, flat top to tip
    head_dia: float  # sharp, at the flat top
    head_angle_deg: float  # included
    tip_chamfer: float  # 45 deg, radial
    thread_top_depth: float  # the groove's flat end, below the top
    wing_half_width: float  # at the top
    web_distance: float  # at the top
    recess_draft_deg: float  # each recess wall to the axis
    entry_r: float
    recess_cone_semi_deg: float
    recess_depth: float  # the bottom cone's apex, below the top

    def __post_init__(self) -> None:
        if self.head_r <= self.major_r:
            raise ValueError(f"{self.part_no}: head not over the major")
        if self.thread_top_depth <= self.junction_depth:
            raise ValueError(f"{self.part_no}: the thread reaches the head cone")
        if self.recess_depth <= self.thread_top_depth:
            raise ValueError(f"{self.part_no}: the recess stops above the thread top")
        if self.web_distance / math.cos(math.pi / 8.0) >= self.entry_r:
            raise ValueError(f"{self.part_no}: the web corners leave the entry")
        if self.wing_reach >= self.head_r:
            raise ValueError(f"{self.part_no}: the sketched wings leave the head top")
        if self.cone_r_at(self.cone_tip_top_depth) >= self.web_distance_at(
            self.cone_tip_top_depth
        ):
            raise ValueError(f"{self.part_no}: the recess cone tip leaves the web")
        if self.wing_half_width_at(self.thread_top_depth) <= 0.0:
            raise ValueError(
                f"{self.part_no}: the drafted wings close above the thread top"
            )

    # --- axis frame ---------------------------------------------------------------
    @property
    def top_y(self) -> float:
        """The flat top sits on the origin."""
        return 0.0

    @property
    def tip_y(self) -> float:
        return self.top_y - self.length

    @property
    def major_r(self) -> float:
        return self.major_dia / 2.0

    @property
    def head_r(self) -> float:
        return self.head_dia / 2.0

    @property
    def h_sharp(self) -> float:
        return self.pitch * math.sqrt(3.0) / 2.0

    @property
    def root_r(self) -> float:
        return self.major_r - 0.75 * self.h_sharp

    @property
    def junction_depth(self) -> float:
        """Depth below the top where the head cone meets the major."""
        half = math.radians(self.head_angle_deg / 2.0)
        return (self.head_r - self.major_r) / math.tan(half)

    @property
    def junction_y(self) -> float:
        return self.top_y - self.junction_depth

    def seated_recess(self, mouth_dia: float, csk_angle_deg: float) -> float:
        """Nominal depth of the flat top below a countersink's sharp mouth.

        The head cone bears on a countersink of the same included angle, so
        the flat top sits where that countersink is ``head_dia`` across.
        Nominal geometry only: it assumes no head-angle or countersink-angle
        tolerance, which the catalogue does not state.
        """
        if csk_angle_deg != self.head_angle_deg:
            raise ValueError(
                f"{self.part_no}: a {csk_angle_deg} deg countersink does not "
                f"match the {self.head_angle_deg} deg head"
            )
        if mouth_dia < self.head_dia:
            raise ValueError(
                f"{self.part_no}: the head stands proud of a Ø{mouth_dia} mouth"
            )
        half = math.radians(self.head_angle_deg / 2.0)
        return (mouth_dia - self.head_dia) / (2.0 * math.tan(half))

    # --- thread -------------------------------------------------------------------
    @property
    def split_y(self) -> float:
        """Where the shank revolve (threaded alone) ends and the head revolve
        starts: the thread's flat top."""
        return self.top_y - self.thread_top_depth

    @property
    def threaded_length(self) -> float:
        return self.length - self.thread_top_depth

    @property
    def helix_revs(self) -> float:
        """Tip-seeded helix, threaded length + P high (past the split)."""
        return self.threaded_length / self.pitch + 1.0

    # --- recess -------------------------------------------------------------------
    @property
    def draft_slope(self) -> float:
        return math.tan(math.radians(self.recess_draft_deg))

    @property
    def cone_slope(self) -> float:
        return math.tan(math.radians(self.recess_cone_semi_deg))

    @property
    def wing_reach(self) -> float:
        """Sketched wing end, measured along the wing from the axis."""
        return self.entry_r + WING_REACH_MARGIN

    @property
    def entry_depth(self) -> float:
        """Where the bottom cone meets the entry cylinder, below the top."""
        return self.recess_depth - self.entry_r / self.cone_slope

    @property
    def cone_tip_top_depth(self) -> float:
        """The cone-tip revolve cut's top: P/4 above the thread top, where the
        cone still lies inside the drafted web."""
        return self.thread_top_depth - self.pitch / 4.0

    def wing_half_width_at(self, depth: float) -> float:
        return self.wing_half_width - depth * self.draft_slope

    def web_distance_at(self, depth: float) -> float:
        return self.web_distance - depth * self.draft_slope

    def cone_r_at(self, depth: float) -> float:
        return (self.recess_depth - depth) * self.cone_slope

    def recess_outline(self, depth: float = 0.0) -> tuple[Point, ...]:
        """The cross-and-notch outline at ``depth`` (the drafted cut's
        section), counter-clockwise from the +x wing's end: per quadrant the
        wing end, the wing side meeting its notch plane, the notch's diagonal
        corner, the other notch plane meeting the next wing's side."""
        w = self.wing_half_width_at(depth)
        e = self.web_distance_at(depth)
        reach = self.wing_reach - depth * self.draft_slope
        c, s = math.cos(math.pi / 8.0), math.sin(math.pi / 8.0)
        side = (e - w * c) / s  # y = w on the plane normal at 67.5 deg
        corner = e / c * math.sqrt(0.5)  # the notch's 45 deg corner
        quadrant = ((reach, -w), (reach, w), (side, w), (corner, corner), (w, side))
        points: list[Point] = []
        for k in range(4):
            ck, sk = (1.0, 0.0, -1.0, 0.0)[k], (0.0, 1.0, 0.0, -1.0)[k]
            points += [(x * ck - y * sk, x * sk + y * ck) for x, y in quadrant]
        return tuple(points)

    def recess_area(self, depth: float, n_theta: int = 400) -> float:
        """The recess's section at ``depth``: the outline inside
        min(entry_r, cone) -- eight times the 0..45 deg sector, by the midpoint
        rule on the polar boundary (the outline is star-shaped about the
        axis; in 0..45 deg it is the +x wing's side or the notch plane normal
        at 67.5 deg, whichever is farther)."""
        w = self.wing_half_width_at(depth)
        e = self.web_distance_at(depth)
        bound = min(self.entry_r, self.cone_r_at(depth))
        if bound <= 0.0:
            return 0.0
        step = math.pi / 4.0 / n_theta
        total = 0.0
        for i in range(n_theta):
            t = (i + 0.5) * step
            rho = max(w / math.sin(t), e / math.cos(t - 3.0 * math.pi / 8.0))
            total += min(rho, bound) ** 2
        return 4.0 * total * step

    def recess_volume(self, n_depth: int = 200, n_theta: int = 400) -> float:
        """The whole recess, by the midpoint rule over depth."""
        step = self.recess_depth / n_depth
        return step * sum(
            self.recess_area((i + 0.5) * step, n_theta) for i in range(n_depth)
        )

    # --- profiles -----------------------------------------------------------------
    def body_profile(self) -> tuple[tuple[Point, Point], ...]:
        """The revolve's closed half-section, clockwise from the axis at the
        top: top face, 82 deg cone, major, tip chamfer, axis."""
        top, tip, tc = self.top_y, self.tip_y, self.tip_chamfer
        return _loop(
            (
                (0.0, top),
                (self.head_r, top),
                (self.major_r, self.junction_y),
                (self.major_r, tip + tc),
                (self.major_r - tc, tip),
                (0.0, tip),
            )
        )

    def head_profile(self) -> tuple[tuple[Point, Point], ...]:
        """The head revolve's half-section, ``body_profile`` above the thread
        top: top face, 82 deg cone, the major down to the thread top."""
        top, y0 = self.top_y, self.split_y
        return _loop(
            (
                (0.0, top),
                (self.head_r, top),
                (self.major_r, self.junction_y),
                (self.major_r, y0),
                (0.0, y0),
            )
        )

    def shank_profile(self) -> tuple[tuple[Point, Point], ...]:
        """The shank revolve's half-section, ``body_profile`` below the thread
        top: the major down to the tip chamfer, the tip, the axis."""
        y0, tip, tc = self.split_y, self.tip_y, self.tip_chamfer
        return _loop(
            (
                (0.0, y0),
                (self.major_r, y0),
                (self.major_r, tip + tc),
                (self.major_r - tc, tip),
                (0.0, tip),
            )
        )

    def refill_profile(self) -> tuple[tuple[Point, Point], ...]:
        """Revolve boss putting back what the drafted cut (blind to the thread
        top) took outside the recess: from the cone at the thread top up the
        cone and the entry cylinder, out over the top and down the head's
        outside to the thread top."""
        y0 = self.split_y
        return _loop(
            (
                (self.cone_r_at(self.thread_top_depth), y0),
                (self.entry_r, self.top_y - self.entry_depth),
                (self.entry_r, self.top_y),
                (self.head_r, self.top_y),
                (self.major_r, self.junction_y),
                (self.major_r, y0),
            )
        )

    def cone_tip_profile(self) -> tuple[Point, Point, Point]:
        """Revolve-cut triangle: the recess cone below the drafted cut, from
        its apex up to ``cone_tip_top_depth``."""
        d = self.cone_tip_top_depth
        return (
            (0.0, self.top_y - self.recess_depth),
            (self.cone_r_at(d), self.top_y - d),
            (0.0, self.top_y - d),
        )

    def thread_cutter(self) -> tuple[Point, Point, Point, Point]:
        """The family cutter chain, centred 7P/16 past the tip."""
        p = self.pitch
        cy = self.tip_y - 7.0 * p / 16.0
        crest = self.major_r + self.h_sharp / 16.0
        return (
            (crest, cy + 15.0 * p / 32.0),
            (self.root_r, cy + p / 16.0),
            (self.root_r, cy - p / 16.0),
            (crest, cy - 15.0 * p / 32.0),
        )
