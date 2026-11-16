"""Read posted G-code and check it against the CAD-derived expectations of a CAM recipe.

Fusion's toolpaths are only as right as the selections and heights the recipe gave
it, and three of the four errors found while programming the oblique base bar
(spot depth measured from the counterbore floor, a feed height below the stock
top, slots cut from outside the slot) left every toolpath valid with no warning.
These checks read the posted file, the artefact that reaches the machine, and
compare it with positions derived from the part's ``features.toml``.

Only absolute, linear-unit programs (G90 G21) with G17 XY arcs are modelled:
arcs contribute their endpoints, which is enough for every check here because
each check bounds positions that toolpaths reach at a segment end.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

_COMMENT = re.compile(r"\(.*?\)|;.*")
_WORD = re.compile(r"([A-Z])\s*(-?\d*\.?\d+)")
_TOL_MM = 0.002


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
    them. A part move made in incremental mode (G91) is refused, not modelled.
    """
    position: list[float | None] = [None, None, None]
    motion: Motion | None = None
    incremental = False
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
            elif letter == "S":
                spindle.add(value)
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
            start = target if None in position else position
            moves.append(Move(motion, tuple(start), tuple(target)))  # type: ignore[arg-type]
        position = target
    return Program(Path(path), tuple(moves), frozenset(spindle))


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
) -> list[Finding]:
    """Cutting moves below the stock top (Z0) whose endpoint lies in the XY
    ``window`` span exactly ``x`` × ``y`` (cutter-centre bounds of a pocket or
    slot), reach exactly ``z_min``, and turn every arc one way: ``arc`` is
    ``"G2"`` (clockwise; conventional inside a pocket with a right-hand spindle)
    or ``"G3"``."""
    (wx0, wx1), (wy0, wy1) = window
    inside = [
        m for m in program.cutting
        if m.end[2] < 0 and wx0 <= m.end[0] <= wx1 and wy0 <= m.end[1] <= wy1
    ]
    if not inside:
        return [Finding(program.path.name, "bounds", f"no cutting move in window {window}")]
    got_x = (min(m.end[0] for m in inside), max(m.end[0] for m in inside))
    got_y = (min(m.end[1] for m in inside), max(m.end[1] for m in inside))
    findings = []
    if not all(_close(a, b) for a, b in zip((*got_x, *got_y), (*x, *y))):
        findings.append(Finding(
            program.path.name, "bounds",
            f"cutter centre X[{got_x[0]:.3f},{got_x[1]:.3f}] Y[{got_y[0]:.3f},{got_y[1]:.3f}], "
            f"expected X[{x[0]:.3f},{x[1]:.3f}] Y[{y[0]:.3f},{y[1]:.3f}]",
        ))
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
) -> list[Finding]:
    """Straight side-cut passes along the other axis, longer than ``span``, at
    constant ``axis`` coordinate and below ``below_z``: the last pass sits at
    ``final`` and runs in ``direction`` (+1/-1) along the other axis, and no pass
    removes more than ``max_step``. ``raw`` is the cutter-centre coordinate that
    just touches the raw face, so each step is the distance between consecutive
    pass positions, starting from ``raw``. With ``finish``, the final pass
    removes no more than that finishing step."""
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
    last = [m for m in passes if _close(m.end[a], final)]
    if last and any((m.end[b] - m.start[b]) * direction <= 0 for m in last):
        findings.append(Finding(program.path.name, "passes", f"final pass does not run {'+' if direction > 0 else '-'}{'XY'[b]}"))
    return findings
