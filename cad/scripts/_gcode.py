"""Read posted G-code and check it against the CAD-derived expectations of a CAM recipe.

A CAM system's toolpaths are only as right as the selections and heights the
recipe gave it, and three of the four errors found while first programming the
oblique base bar (spot depth measured from the counterbore floor, a feed height
below the stock top, slots cut from outside the slot) left every toolpath valid
with no warning. These checks read the posted file, the artefact that reaches
the machine, and compare it with positions derived from the part's
``features.toml``. :func:`cycle_time` reads the same file for the time each
program spends cutting, feeding through the air and rapiding.

Only absolute, linear-unit programs (G90 G21, feed per minute) are modelled.
Arcs may lie in any principal plane (G17/G18/G19) with I/J/K centre offsets
relative to their start; the R form is refused, not modelled. Endpoint checks
see an arc's endpoints, which is enough for every check here because each
bounds positions that toolpaths reach at a segment end; :func:`cycle_time` and
:func:`check_air_feed` use its true length.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

_COMMENT = re.compile(r"\(.*?\)|;.*")
_WORD = re.compile(r"([A-Z])\s*(-?\d*\.?\d+)")
_TOL_MM = 0.002
# A plunge requested at a point lands on the toolpath vertex nearest it.
_ENTRY_TOL_MM = 0.01
# The machine's rapid rate is an ASSUMPTION until the converted PM-30MV's GRBL
# $110/$111 (X/Y max rate) and $112 (Z) are read off the controller: 100 in/min
# on every axis. cycle_time() takes the rate as an argument; this is the
# default the cam driver reports with.
RAPID_MM_MIN = 2540.0
# A feed move wholly above the stock top cuts nothing. Plunges and approaches
# cross the top, so they are never wholly above it; this allowance only admits
# the short entry a post may split off a plunge. Anything longer is air at feed.
AIR_FEED_MAX_MM = 2.0
# Principal plane -> (first, second) in-plane axes, ordered so their cross
# product is the plane normal (+Z, +Y, +X): G2 runs clockwise viewed from it.
_PLANE_AXES = {17: (0, 1), 18: (2, 0), 19: (1, 2)}
_OFFSET_LETTER = "IJK"


class Motion(Enum):
    RAPID = 0
    LINEAR = 1
    ARC_CW = 2
    ARC_CCW = 3


@dataclass(frozen=True)
class Move:
    motion: Motion
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    # mm/min in force for a feed move (None for a rapid, or before any F word).
    feed: float | None = None
    # Arc centre and principal plane (17/18/19), for G2/G3 only.
    centre: tuple[float, float, float] | None = None
    plane: int = 17

    def _arc(self) -> tuple[int, int, float, float, float]:
        """In-plane axes, radius, start angle and swept angle (always positive)."""
        assert self.centre is not None
        a, b = _PLANE_AXES[self.plane]
        radius = math.hypot(self.start[a] - self.centre[a], self.start[b] - self.centre[b])
        begin = math.atan2(self.start[b] - self.centre[b], self.start[a] - self.centre[a])
        finish = math.atan2(self.end[b] - self.centre[b], self.end[a] - self.centre[a])
        sweep = (begin - finish if self.motion is Motion.ARC_CW else finish - begin) % (2 * math.pi)
        if sweep < 1e-9:  # start and end coincide in the plane: a full circle
            sweep = 2 * math.pi
        return a, b, radius, begin, sweep

    @property
    def length(self) -> float:
        """Path length in mm: chord for a line, true (helical) length for an arc."""
        if self.centre is None:
            return math.dist(self.start, self.end)
        a, b, radius, _begin, sweep = self._arc()
        h = 3 - a - b
        return math.hypot(radius * sweep, self.end[h] - self.start[h])

    def extremes(self) -> list[tuple[float, float, float]]:
        """The end, plus an arc's in-plane axis extremes it sweeps through: with
        the endpoints these bound the whole path."""
        points = [self.end]
        if self.centre is None:
            return points
        a, b, radius, begin, sweep = self._arc()
        sense = -1.0 if self.motion is Motion.ARC_CW else 1.0
        for quarter in range(4):
            angle = quarter * math.pi / 2
            if (sense * (angle - begin)) % (2 * math.pi) < sweep:
                point = list(self.start)
                point[a] = self.centre[a] + radius * math.cos(angle)
                point[b] = self.centre[b] + radius * math.sin(angle)
                points.append(tuple(point))  # type: ignore[arg-type]
        return points


@dataclass(frozen=True)
class Program:
    path: Path
    moves: tuple[Move, ...]
    spindle_rpm: frozenset[float]

    @property
    def cutting(self) -> tuple[Move, ...]:
        return tuple(m for m in self.moves if m.motion is not Motion.RAPID)


def read_program(path: Path) -> Program:
    """Parse one posted file.

    A machine-coordinate block (G28/G53) still applies its modal G words: the
    motion, and the distance mode the Grbl post sets with ``G28 G91 Z0`` before
    its ``G90``. Its axis words are skipped because they are not part
    coordinates, and the axes it moves are unknown until a later block sets
    them. A part move made in incremental mode (G91), and an R-form arc, are
    refused, not modelled.
    """
    position: list[float | None] = [None, None, None]
    motion: Motion | None = None
    incremental = False
    plane = 17
    feed: float | None = None
    moves: list[Move] = []
    spindle: set[float] = set()
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = _COMMENT.sub("", raw).strip().upper()
        words = [(letter, float(value)) for letter, value in _WORD.findall(line)]
        codes = {value for letter, value in words if letter == "G"}
        for letter, value in words:
            if letter == "G" and value in (0, 1, 2, 3):
                motion = Motion(int(value))
            elif letter == "G" and value in (90, 91):
                incremental = value == 91
            elif letter == "G" and value in (17, 18, 19):
                plane = int(value)
            elif letter == "S":
                spindle.add(value)
            elif letter == "F":
                feed = value
        axes = {letter: value for letter, value in words if letter in "XYZ"}
        if codes & {28, 53}:
            # A bare G28 homes every axis; otherwise only the named axes move.
            moved = "XYZ" if 28 in codes and not axes else axes
            for i, axis in enumerate("XYZ"):
                if axis in moved:
                    position[i] = None
            continue
        if not axes:
            continue
        if incremental:
            raise ValueError(f"{Path(path).name}:{number}: incremental (G91) part move is not supported: {raw.strip()}")
        target = [axes.get(axis, position[i]) for i, axis in enumerate("XYZ")]
        if None not in target and motion is not None:
            # From an unknown start (program start, after a home) the path is
            # unknown but the endpoint is not: record it as a zero-length move
            # so endpoint checks (rapids into the stock, depth) still see it.
            known = None not in position
            start = tuple(position if known else target)
            centre = None
            if motion in (Motion.ARC_CW, Motion.ARC_CCW) and known:
                if any(letter == "R" for letter, _ in words):
                    raise ValueError(f"{Path(path).name}:{number}: R-form arc is not supported: {raw.strip()}")
                offsets = {letter: value for letter, value in words if letter in _OFFSET_LETTER}
                centre = tuple(start[i] + offsets.get(_OFFSET_LETTER[i], 0.0) for i in range(3))
            moves.append(Move(
                motion, start, tuple(target),  # type: ignore[arg-type]
                feed=None if motion is Motion.RAPID else feed, centre=centre, plane=plane,
            ))
        position = target
    return Program(Path(path), tuple(moves), frozenset(spindle))


@dataclass(frozen=True)
class CycleTime:
    """Minutes a program spends feeding at or below the stock top (``cutting``,
    an upper bound: it includes feed moves beside the part), feeding wholly
    above it (``air``), and rapiding (``rapid``). Dwells, spindle ramp-up and
    machine-coordinate moves (G28/G53) are not counted."""

    cutting: float
    air: float
    rapid: float

    @property
    def total(self) -> float:
        return self.cutting + self.air + self.rapid


def cycle_time(nc: Program, rapid_mm_min: float = RAPID_MM_MIN, z_top: float = 0.0) -> CycleTime:
    """Split ``nc``'s motion time at the stock top ``z_top``. A straight feed
    move that crosses the top is split at the crossing; an arc counts as air
    only when both its ends are above the top."""
    cutting = air = rapid = 0.0
    for m in nc.moves:
        length = m.length
        if m.motion is Motion.RAPID:
            rapid += length / rapid_mm_min
            continue
        if length == 0.0:
            continue
        if not m.feed:
            raise ValueError(f"{nc.path.name}: feed move to {m.end} without a feed rate")
        low, high = sorted((m.start[2], m.end[2]))
        if _wholly_above(m, z_top):
            above = 1.0
        elif high <= z_top + _TOL_MM or m.centre is not None:
            above = 0.0
        else:
            above = (high - z_top) / (high - low)
        air += length * above / m.feed
        cutting += length * (1.0 - above) / m.feed
    return CycleTime(cutting, air, rapid)


@dataclass(frozen=True)
class Finding:
    program: str
    check: str
    detail: str

    def __str__(self) -> str:
        return f"{self.program}: {self.check}: {self.detail}"


def _close(a: float, b: float, tol: float = _TOL_MM) -> bool:
    return abs(a - b) <= tol


def check_depth(program: Program, z_min: float) -> list[Finding]:
    """The deepest point any move reaches equals the recipe's expected depth."""
    lowest = min(min(m.start[2], m.end[2]) for m in program.moves)
    if _close(lowest, z_min):
        return []
    return [Finding(program.path.name, "depth", f"deepest Z {lowest:.3f}, expected {z_min:.3f}")]


def check_spindle(program: Program, rpm: float) -> list[Finding]:
    if program.spindle_rpm == {rpm}:
        return []
    return [Finding(program.path.name, "spindle", f"S words {sorted(program.spindle_rpm)}, expected {rpm:g}")]


def check_holes(program: Program, centres: Iterable[tuple[float, float]], z_bottom: float) -> list[Finding]:
    """Every expected hole is plunged to ``z_bottom`` and nothing else is plunged.

    A plunge is a straight Z-only feed move that descends. Its XY is the hole
    centre; the deepest plunge at that XY is the hole bottom.
    """
    bottoms: dict[tuple[float, float], float] = {}
    for m in program.cutting:
        if m.motion is Motion.LINEAR and m.end[2] < m.start[2] and _close(m.start[0], m.end[0]) and _close(m.start[1], m.end[1]):
            key = (round(m.end[0], 3), round(m.end[1], 3))
            bottoms[key] = min(bottoms.get(key, m.end[2]), m.end[2])
    expected = {(round(x, 3), round(y, 3)) for x, y in centres}
    findings = []
    missing = sorted(expected - set(bottoms))
    extra = sorted(set(bottoms) - expected)
    if missing:
        findings.append(Finding(program.path.name, "holes", f"no plunge at {missing}"))
    if extra:
        findings.append(Finding(program.path.name, "holes", f"unexpected plunge at {extra}"))
    shallow = sorted((xy, z) for xy, z in bottoms.items() if xy in expected and not _close(z, z_bottom))
    if shallow:
        findings.append(Finding(program.path.name, "holes", f"bottom ≠ {z_bottom:.3f} at {shallow}"))
    return findings


def check_rapids_clear(program: Program, z_top: float, open_holes: Iterable[tuple[float, float]] = ()) -> list[Finding]:
    """No rapid move reaches below the stock top, except straight down into a hole
    this same program has already fed to that depth (expanded peck re-entries)."""
    reached: dict[tuple[float, float], float] = {}
    allowed = {(round(x, 3), round(y, 3)) for x, y in open_holes}
    findings = []
    for m in program.moves:
        xy = (round(m.end[0], 3), round(m.end[1], 3))
        if m.motion is not Motion.RAPID:
            reached[xy] = min(reached.get(xy, m.end[2]), m.end[2])
            continue
        if m.end[2] >= z_top - _TOL_MM:
            continue
        reentry = xy in allowed and m.end[2] >= reached.get(xy, float("inf")) - _TOL_MM
        if not reentry:
            findings.append(Finding(program.path.name, "rapid", f"G0 to Z{m.end[2]:.3f} at X{xy[0]} Y{xy[1]} below stock top {z_top:.3f}"))
    return findings


def check_vertical_below_top(program: Program, z_top: float) -> list[Finding]:
    """Below the stock top a hole program only moves along Z: any move there that
    changes X or Y, rapid or feed, drags the tool through the part. Feeds matter
    as much as rapids because Fusion Personal may post linking moves as G1."""
    findings = []
    for m in program.moves:
        low = min(m.start[2], m.end[2]) < z_top - _TOL_MM
        lateral = not (_close(m.start[0], m.end[0]) and _close(m.start[1], m.end[1]))
        if low and lateral:
            findings.append(Finding(
                program.path.name, "lateral",
                f"{m.motion.name} X{m.start[0]:.3f} Y{m.start[1]:.3f} -> X{m.end[0]:.3f} Y{m.end[1]:.3f} below stock top {z_top:.3f}",
            ))
    return findings


def check_bounds(
    program: Program,
    window: tuple[tuple[float, float], tuple[float, float]],
    x: tuple[float, float],
    y: tuple[float, float],
    z_min: float,
    arc: str,
    entry: tuple[float, float] | None = None,
) -> list[Finding]:
    """Cutting moves below the stock top (Z0) whose endpoint lies in the XY
    ``window`` sweep a path spanning exactly ``x`` × ``y`` (the cutter-centre
    envelope of a pocket or slot, arcs included), reach exactly ``z_min``, and
    turn every arc one way: ``arc`` is ``"G2"`` (clockwise; conventional inside
    a pocket with a right-hand spindle) or ``"G3"``. With ``entry``, every
    plunge (a descending Z-only feed) in the window is within ``_ENTRY_TOL_MM``
    of that XY: a CAM system enters at the path vertex nearest the point asked."""
    (wx0, wx1), (wy0, wy1) = window
    inside = [
        m for m in program.cutting
        if m.end[2] < 0 and wx0 <= m.end[0] <= wx1 and wy0 <= m.end[1] <= wy1
    ]
    if not inside:
        return [Finding(program.path.name, "bounds", f"no cutting move in window {window}")]
    points = [p for m in inside for p in (*m.extremes(), *([m.start] if m.start[2] < 0 else []))]
    got_x = (min(p[0] for p in points), max(p[0] for p in points))
    got_y = (min(p[1] for p in points), max(p[1] for p in points))
    findings = []
    if not all(_close(a, b) for a, b in zip((*got_x, *got_y), (*x, *y))):
        findings.append(Finding(
            program.path.name, "bounds",
            f"cutter centre X[{got_x[0]:.3f},{got_x[1]:.3f}] Y[{got_y[0]:.3f},{got_y[1]:.3f}], "
            f"expected X[{x[0]:.3f},{x[1]:.3f}] Y[{y[0]:.3f},{y[1]:.3f}]",
        ))
    if entry is not None:
        plunges = sorted({
            (round(m.end[0], 3), round(m.end[1], 3)) for m in inside
            if m.motion is Motion.LINEAR and m.end[2] < m.start[2] and _close(m.start[0], m.end[0]) and _close(m.start[1], m.end[1])
        })
        if not plunges or any(math.dist((px, py), entry) > _ENTRY_TOL_MM for px, py in plunges):
            findings.append(Finding(program.path.name, "bounds", f"plunges at {plunges}, expected only at X{entry[0]:.3f} Y{entry[1]:.3f}"))
    lowest = min(m.end[2] for m in inside)
    if not _close(lowest, z_min):
        findings.append(Finding(program.path.name, "bounds", f"deepest Z {lowest:.3f} in {window}, expected {z_min:.3f}"))
    wanted = {"G2": Motion.ARC_CW, "G3": Motion.ARC_CCW}[arc]
    senses = {m.motion for m in inside if m.motion in (Motion.ARC_CW, Motion.ARC_CCW)}
    if senses != {wanted}:
        findings.append(Finding(program.path.name, "bounds", f"arcs {sorted(s.name for s in senses)}, expected only {arc}"))
    return findings


def check_side_passes(
    program: Program,
    axis: str,
    final: float,
    raw: float,
    max_step: float,
    direction: float,
    span: float,
    below_z: float,
    finish: float | None = None,
    max_stepdown: float | None = None,
) -> list[Finding]:
    """Straight side-cut passes along the other axis, longer than ``span``, at
    constant ``axis`` coordinate and below ``below_z``: the last pass sits at
    ``final``, every pass runs in ``direction`` (+1/-1) along the other axis (the
    side's measured settings are for one milling direction), and no pass
    removes more than ``max_step``. ``raw`` is the cutter-centre coordinate that
    just touches the raw face, so each step is the distance between consecutive
    pass positions, starting from ``raw``. With ``finish``, the final pass
    removes no more than that finishing step. With ``max_stepdown``, the pass
    depths step down from ``below_z`` (the stock top) by no more than that."""
    a = "XY".index(axis)
    b = 1 - a
    passes = [
        m for m in program.cutting
        if m.motion is Motion.LINEAR and _close(m.start[a], m.end[a]) and abs(m.end[b] - m.start[b]) > span
        and m.end[2] < below_z and _close(m.start[2], m.end[2])
        and min(raw, final) - _TOL_MM <= m.end[a] <= max(raw, final) + _TOL_MM
    ]
    if not passes:
        return [Finding(program.path.name, "passes", f"no {axis}-constant pass longer than {span}")]
    toward = 1.0 if final > raw else -1.0
    stations = sorted({round(m.end[a], 3) for m in passes}, key=lambda v: toward * v)
    findings = []
    if not _close(stations[-1], final):
        findings.append(Finding(program.path.name, "passes", f"final {axis} {stations[-1]:.3f}, expected {final:.3f}"))
    previous = raw
    for index, station in enumerate(stations):
        step = toward * (station - previous)
        limit = finish if finish is not None and index == len(stations) - 1 else max_step
        if step > limit + _TOL_MM:
            findings.append(Finding(program.path.name, "passes", f"{axis} {station:.3f} removes {step:.3f} > {limit:.3f}"))
        previous = station
    if max_stepdown is not None:
        for station in stations:
            levels = sorted({round(m.end[2], 3) for m in passes if _close(m.end[a], station)}, reverse=True)
            previous = below_z
            for level in levels:
                if previous - level > max_stepdown + _TOL_MM:
                    findings.append(Finding(
                        program.path.name, "passes",
                        f"{axis} {station:.3f}: Z {level:.3f} steps down {previous - level:.3f} > {max_stepdown:.3f}",
                    ))
                previous = level
    sign = "+" if direction > 0 else "-"
    for m in passes:
        if (m.end[b] - m.start[b]) * direction <= 0:
            findings.append(Finding(
                program.path.name, "passes",
                f"{axis} {m.end[a]:.3f} Z {m.end[2]:.3f}: pass does not run {sign}{'XY'[b]}",
            ))
    return findings


def _wholly_above(m: Move, z_top: float) -> bool:
    return min(m.start[2], m.end[2]) >= z_top - _TOL_MM


def check_air_feed(program: Program, z_top: float, max_mm: float = AIR_FEED_MAX_MM) -> list[Finding]:
    """No feed move lies wholly above the stock top for longer than ``max_mm``:
    above the stock every move is a rapid (G0), and a feed move there is time
    spent cutting air at feed rate."""
    return [
        Finding(
            program.path.name, "air_feed",
            f"{m.motion.name} {m.length:.3f} mm at feed above stock top {z_top:.3f}: "
            f"X{m.start[0]:.3f} Y{m.start[1]:.3f} Z{m.start[2]:.3f} -> X{m.end[0]:.3f} Y{m.end[1]:.3f} Z{m.end[2]:.3f}",
        )
        for m in program.cutting
        if _wholly_above(m, z_top) and m.length > max_mm
    ]


def check_no_return(program: Program, axis: str, span: float) -> list[Finding]:
    """No rapid travels farther than ``span`` along ``axis``. A one-way side cut
    returns to its start through the air after every pass; cutting two
    opposite sides in opposite directions ends each pass where the next begins."""
    i = "XYZ".index(axis)
    return [
        Finding(program.path.name, "return", f"G0 {axis}{m.start[i]:.3f} -> {axis}{m.end[i]:.3f} travels {abs(m.end[i] - m.start[i]):.3f} > {span:.3f}")
        for m in program.moves
        if m.motion is Motion.RAPID and abs(m.end[i] - m.start[i]) > span
    ]


def check_face_passes(
    program: Program,
    z: float,
    y: tuple[float, float],
    max_stepover: float,
    radius: float,
    span: float,
) -> list[Finding]:
    """A zigzag face: the straight X passes longer than ``span`` at depth ``z``
    alternate direction pass to pass, sit no more than ``max_stepover`` apart,
    and their cutter (``radius``) covers the face's Y extent ``y``."""
    passes = [
        m for m in program.cutting
        if m.motion is Motion.LINEAR and _close(m.start[2], z) and _close(m.end[2], z)
        and _close(m.start[1], m.end[1]) and abs(m.end[0] - m.start[0]) > span
    ]
    if not passes:
        return [Finding(program.path.name, "face", f"no X pass longer than {span} at Z {z:.3f}")]
    findings = []
    for before, after in zip(passes, passes[1:]):
        if (before.end[0] - before.start[0]) * (after.end[0] - after.start[0]) > 0:
            findings.append(Finding(program.path.name, "face", f"passes at Y {before.end[1]:.3f} and Y {after.end[1]:.3f} run the same way"))
    stations = sorted({round(m.end[1], 3) for m in passes})
    for low, high in zip(stations, stations[1:]):
        if high - low > max_stepover + _TOL_MM:
            findings.append(Finding(program.path.name, "face", f"stepover {high - low:.3f} between Y {low:.3f} and Y {high:.3f} > {max_stepover:.3f}"))
    if stations[0] - radius > y[0] + _TOL_MM or stations[-1] + radius < y[1] - _TOL_MM:
        findings.append(Finding(
            program.path.name, "face",
            f"cutter covers Y[{stations[0] - radius:.3f},{stations[-1] + radius:.3f}], face Y[{y[0]:.3f},{y[1]:.3f}]",
        ))
    return findings
