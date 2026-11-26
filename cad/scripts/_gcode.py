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
from typing import Iterable, Sequence

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
# The milling directions a recipe may declare for a side cut: conventional,
# each tooth's chip thin to thick (the stock on the cutter's left of its
# travel under M3), and climb, thick to thin.
CUT_DIRECTIONS = ("conventional", "climb")
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
    # The file line the move is on (1-based; 0 when built by hand).
    line: int = 0
    # The spindle's turn in force: +1 under M3 (clockwise seen from above),
    # -1 under M4, 0 when stopped (M5) or before either.
    spindle: int = 0

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
class Stop:
    """An ``M0`` program stop or an ``M6`` tool change: its line, the comment
    line just before it (the operator's instruction; ``None`` when the previous
    line is not a comment), the tool position there (``None`` per axis while
    unknown), how many moves precede it, the tool an ``M6`` calls (``T`` on its
    line) and whether the spindle was still on (an ``M3``/``M4`` since the last
    ``M5``)."""

    line: int
    kind: str  # "M0" or "M6"
    comment: str | None
    position: tuple[float | None, float | None, float | None]
    moves_before: int
    tool: int | None = None
    spindle_on: bool = False


@dataclass(frozen=True)
class Probe:
    """A probing move (``G38.2``-``G38.5``, ``code`` 38.2...) or a work-offset
    setting (``G10 L20 P1``, ``code`` 10.0): its line, how many moves precede
    it, the axis words it names, and whether the spindle was on."""

    line: int
    code: float
    moves_before: int
    axes: tuple[tuple[str, float], ...]
    spindle_on: bool = False


@dataclass(frozen=True)
class Program:
    path: Path
    moves: tuple[Move, ...]
    stops: tuple[Stop, ...] = ()
    # Every S word in file order, as (line, rpm).
    spindle: tuple[tuple[int, float], ...] = ()
    # Lines holding a machine-coordinate move (G28/G30/G53).
    machine_moves: tuple[int, ...] = ()
    # G38.x probing moves and G10 L20 P1 settings, in file order.
    probes: tuple[Probe, ...] = ()
    # Set on the slices :meth:`tool_sections` returns.
    section: int | None = None

    @property
    def name(self) -> str:
        """The file name, with ``@k`` for its ``k``-th tool section."""
        return self.path.name if self.section is None else f"{self.path.name}@{self.section}"

    @property
    def pauses(self) -> tuple[Stop, ...]:
        return tuple(s for s in self.stops if s.kind == "M0")

    @property
    def tool_changes(self) -> tuple[Stop, ...]:
        return tuple(s for s in self.stops if s.kind == "M6")

    @property
    def spindle_rpm(self) -> frozenset[float]:
        return frozenset(rpm for _line, rpm in self.spindle)

    @property
    def cutting(self) -> tuple[Move, ...]:
        return tuple(m for m in self.moves if m.motion is not Motion.RAPID)

    def tool_sections(self) -> list[Program]:
        """The program split at its ``M6`` tool changes: the tool loaded
        before the program runs (when anything happens before the first
        ``M6``), then one slice from each ``M6`` on."""
        changes = self.tool_changes
        bounds = [(stop.line, stop.moves_before) for stop in changes]
        if not changes or changes[0].moves_before or any(line < changes[0].line for line, _rpm in self.spindle):
            bounds.insert(0, (0, 0))
        sections = []
        for index, (first, start) in enumerate(bounds):
            last, end = bounds[index + 1] if index + 1 < len(bounds) else (math.inf, len(self.moves))
            sections.append(Program(
                self.path,
                self.moves[start:end],
                tuple(s for s in self.stops if first <= s.line < last),
                tuple(w for w in self.spindle if first <= w[0] < last),
                tuple(n for n in self.machine_moves if first <= n < last),
                tuple(p for p in self.probes if first <= p.line < last),
                index,
            ))
        return sections

    def tool_section(self, index: int) -> Program:
        sections = self.tool_sections()
        if not 0 <= index < len(sections):
            raise ValueError(f"{self.path.name}: no tool section {index} (it has {len(sections)})")
        return sections[index]


def read_program(path: Path) -> Program:
    """Parse one posted file.

    A machine-coordinate block (G28/G30/G53) still applies its modal G words:
    the motion, and the distance mode the Grbl post sets with ``G28 G91 Z0``
    before its ``G90``. Its axis words are skipped because they are not part
    coordinates, and the axes it moves are unknown until a later block sets
    them; its line is recorded. A probing move (G38.2-G38.5) stops where the
    probe trips, so the axes it names become unknown; ``G10 L20 P1`` makes the
    current position read the values it names. Both record a :class:`Probe`.
    A part move made in incremental mode (G91), an R-form arc and any other
    ``G10`` are refused, not modelled. ``M0`` and ``M6`` record a
    :class:`Stop`.
    """
    position: list[float | None] = [None, None, None]
    motion: Motion | None = None
    incremental = False
    plane = 17
    feed: float | None = None
    rotation = 0
    moves: list[Move] = []
    stops: list[Stop] = []
    spindle: list[tuple[int, float]] = []
    machine_moves: list[int] = []
    probes: list[Probe] = []
    previous = ""
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        # A CNCjs "%msg" line is the operator's instruction CNCjs shows at the
        # next M0 (it sends no comment); any other "%" directive is not modelled.
        if raw.strip().startswith("%"):
            if not raw.strip().lower().startswith("%msg "):
                raise ValueError(f"{Path(path).name}:{number}: only the CNCjs %msg directive is modelled: {raw.strip()}")
            previous = f"({raw.strip()[5:].strip()})"
            continue
        line = _COMMENT.sub("", raw).strip().upper()
        words = [(letter, float(value)) for letter, value in _WORD.findall(line)]
        if line and not words:
            # Text left outside a comment (comments do not nest: the first ")"
            # ends one) reaches the controller as code, which refuses it.
            raise ValueError(f"{Path(path).name}:{number}: text outside a comment, sent as code: {raw.strip()}")
        codes = {value for letter, value in words if letter == "G"}
        mcodes = {value for letter, value in words if letter == "M"}
        for kind, code in (("M0", 0), ("M6", 6)):
            if code in mcodes:
                comment = previous[1:-1].strip() if previous.startswith("(") and previous.endswith(")") else None
                tool = next((int(v) for letter, v in words if letter == "T"), None) if code == 6 else None
                stops.append(Stop(number, kind, comment, (position[0], position[1], position[2]), len(moves), tool, rotation != 0))
        if mcodes & {3, 4}:
            rotation = 1 if 3 in mcodes else -1
        if 5 in mcodes:
            rotation = 0
        if raw.strip():
            previous = raw.strip()
        for letter, value in words:
            if letter == "G" and value in (0, 1, 2, 3):
                motion = Motion(int(value))
            elif letter == "G" and value in (90, 91):
                incremental = value == 91
            elif letter == "G" and value in (17, 18, 19):
                plane = int(value)
            elif letter == "S":
                spindle.append((number, value))
            elif letter == "F":
                feed = value
        axes = {letter: value for letter, value in words if letter in "XYZ"}
        if codes & {28, 30, 53}:
            machine_moves.append(number)
            # A bare G28/G30 homes every axis; otherwise only the named axes move.
            moved = "XYZ" if codes & {28, 30} and not axes else axes
            for i, axis in enumerate("XYZ"):
                if axis in moved:
                    position[i] = None
            continue
        probing = sorted(codes & {38.2, 38.3, 38.4, 38.5})
        if probing or 10 in codes:
            if 10 in codes and (("L", 20.0) not in words or ("P", 1.0) not in words):
                raise ValueError(f"{Path(path).name}:{number}: only G10 L20 P1 is modelled: {raw.strip()}")
            probes.append(Probe(number, probing[0] if probing else 10.0, len(moves), tuple(axes.items()), rotation != 0))
            for i, axis in enumerate("XYZ"):
                if axis in axes:
                    position[i] = None if probing else axes[axis]
            if probing:
                motion = None  # G38 is modal: a later bare axis word would probe again
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
                line=number, spindle=rotation,
            ))
        position = target
    return Program(Path(path), tuple(moves), tuple(stops), tuple(spindle), tuple(machine_moves), tuple(probes))


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
            raise ValueError(f"{nc.name}: feed move to {m.end} without a feed rate")
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
    return [Finding(program.name, "depth", f"deepest Z {lowest:.3f}, expected {z_min:.3f}")]


def _speeds(program: Program) -> list[float]:
    """The speeds the S words set, in order, repeats of the running one dropped."""
    speeds: list[float] = []
    for _line, rpm in program.spindle:
        if not speeds or speeds[-1] != rpm:
            speeds.append(rpm)
    return speeds


def check_spindle(program: Program, rpm: float | Sequence[float | Sequence[float]]) -> list[Finding]:
    """``rpm`` alone: every S word sets that speed. A sequence: one entry per
    tool section (the program split at its M6 tool changes), each the speed,
    or the speeds in order, that section sets; an empty entry is a section
    with the spindle off. Within a tool section a speed change needs an M0
    stop between the two S words: the PM-30MV's speed is set by hand."""
    findings = []
    if isinstance(rpm, (int, float)):
        if program.spindle_rpm != {float(rpm)}:
            findings.append(Finding(program.name, "spindle", f"S words {sorted(program.spindle_rpm)}, expected {float(rpm)}"))
    else:
        actual = [_speeds(section) for section in program.tool_sections()]
        expected = [[float(r)] if isinstance(r, (int, float)) else [float(v) for v in r] for r in rpm]
        if actual != expected:
            findings.append(Finding(program.name, "spindle", f"speeds per tool section {actual}, expected {expected}"))
    for section in program.tool_sections():
        for (before, old), (line, new) in zip(section.spindle, section.spindle[1:]):
            if old != new and not any(before < stop.line < line for stop in section.pauses):
                findings.append(Finding(program.name, "spindle", f"line {line}: S{new:g} after S{old:g} without an M0 stop between"))
    return findings


def _retracted(stop: Stop, z_top: float) -> bool:
    z = stop.position[2]
    return z is not None and z > z_top + _TOL_MM


def check_pauses(
    program: Program, z_top: float, count: int, at: Sequence[tuple[float, float]] | None = None, spindle_off: bool = False,
) -> list[Finding]:
    """``count`` M0 stops, each with the tool retracted above the stock top
    and an operator comment on the line before it; with ``at``, the stops sit
    over those XY points, in order; with ``spindle_off``, an ``M5`` has stopped
    the spindle before each (the operator's hands are at the tool or bar)."""
    findings = []
    if len(program.pauses) != count:
        findings.append(Finding(program.name, "pauses", f"{len(program.pauses)} M0 stops, expected {count}"))
    for pause in program.pauses:
        if not _retracted(pause, z_top):
            findings.append(Finding(program.name, "pauses", f"line {pause.line}: M0 with Z {pause.position[2]}, not retracted above {z_top:.3f}"))
        if not pause.comment:
            findings.append(Finding(program.name, "pauses", f"line {pause.line}: M0 without an operator comment before it"))
        if spindle_off and pause.spindle_on:
            findings.append(Finding(program.name, "pauses", f"line {pause.line}: M0 with the spindle on (no M5 before it)"))
    if at is not None:
        got = [(p.position[0], p.position[1]) for p in program.pauses]
        if len(got) != len(at) or not all(
            x is not None and y is not None and _close(x, ex) and _close(y, ey) for (x, y), (ex, ey) in zip(got, at)
        ):
            findings.append(Finding(program.name, "pauses", f"M0 stops at {got}, expected at {[tuple(p) for p in at]}"))
    return findings


def check_tool_changes(
    program: Program, z_top: float, tools: Sequence[int], loads_first: bool = False
) -> list[Finding]:
    """The M6 tool changes call ``tools`` in order (without ``loads_first``,
    the tool loaded before the program runs is not one). Each comes with the
    spindle stopped (M5), the tool retracted above the stock top ``z_top`` and
    an operator comment on the line before it. Between an M6 and the new
    tool's first feed move only rapids run, and any that moves X or Y stays
    above the stock top. With ``loads_first`` the program's first M6 comes
    before any move or S word: the program never runs on the tool length the
    previous program left. No G28/G30/G53 anywhere: the sender (CNCjs) makes
    every tool-change move itself."""
    findings = []
    changes = program.tool_changes
    called = [stop.tool for stop in changes]
    if called != list(tools):
        findings.append(Finding(program.name, "tools", f"M6 calls {called}, expected {list(tools)}"))
    if loads_first and (
        not changes
        or changes[0].moves_before
        or any(line < changes[0].line for line, _rpm in program.spindle)
    ):
        detail = "moves or spindle words before the first M6: the program runs on the previous tool's length"
        findings.append(Finding(program.name, "tools", detail))
    for index, stop in enumerate(changes):
        if stop.moves_before and not _retracted(stop, z_top):
            findings.append(Finding(program.name, "tools", f"line {stop.line}: M6 with Z {stop.position[2]}, not retracted above {z_top:.3f}"))
        if stop.spindle_on:
            findings.append(Finding(program.name, "tools", f"line {stop.line}: M6 with the spindle on (no M5 before it)"))
        if not stop.comment:
            findings.append(Finding(program.name, "tools", f"line {stop.line}: M6 without an operator comment before it"))
        end = changes[index + 1].moves_before if index + 1 < len(changes) else len(program.moves)
        for m in program.moves[stop.moves_before:end]:
            if m.motion is not Motion.RAPID:
                break
            lateral = not (_close(m.start[0], m.end[0]) and _close(m.start[1], m.end[1]))
            if lateral and min(m.start[2], m.end[2]) <= z_top + _TOL_MM:
                findings.append(Finding(
                    program.name, "tools",
                    f"T{stop.tool}: G0 to X{m.end[0]:.3f} Y{m.end[1]:.3f} at Z{min(m.start[2], m.end[2]):.3f}, "
                    f"not above the stock top {z_top:.3f}, before its first feed",
                ))
    if program.machine_moves:
        findings.append(Finding(program.name, "tools", f"machine-coordinate moves (G28/G30/G53) on lines {list(program.machine_moves)}"))
    return findings


def check_tap_stop(program: Program, tool: int, at: tuple[float, float], machine_top: float) -> list[Finding]:
    """A hand-tap stop file: the controller ends Idle over one hole so the
    operator can jog Z (FluidNC, like Grbl, refuses jogs in the Hold an M0
    leaves). Its one ``M6`` calls ``tool`` (the guide) before any motion; its
    first motion is ``G53 G0`` naming Z alone (the top, in machine
    coordinates: Z was left jogged down by the operator); then only rapids
    in X and Y, ending over ``at``; no feed move, no spindle word, no Z move
    in part coordinates (nothing lowers the guide but the operator's jog);
    the last command is ``M30``. ``machine_top`` is the lowest machine Z the
    retract may name."""
    findings: list[Finding] = []

    def fail(detail: str) -> None:
        findings.append(Finding(program.name, "tap_stop", detail))

    if program.section is not None:
        fail("a tap stop is a whole file, not a tool section")
        return findings
    if [stop.tool for stop in program.tool_changes] != [tool]:
        fail(f"M6 calls {[stop.tool for stop in program.tool_changes]}, expected [{tool}]")
    if program.pauses:
        fail(f"M0 on lines {[p.line for p in program.pauses]}: an M0 holds the controller, where jogging is refused")
    if program.spindle:
        fail(f"spindle words on lines {[line for line, _rpm in program.spindle]}: the spindle stays off")
    commands: list[tuple[int, set[float], set[float], dict[str, float]]] = []
    for number, raw in enumerate(Path(program.path).read_text(encoding="utf-8").splitlines(), 1):
        if raw.strip().startswith("%"):
            continue
        words = [(letter, float(value)) for letter, value in _WORD.findall(_COMMENT.sub("", raw).strip().upper())]
        if words:
            g = {v for letter, v in words if letter == "G"}
            m = {v for letter, v in words if letter == "M"}
            commands.append((number, g, m, {k: v for k, v in words if k in "XYZ"}))
    for number, g, m, _axes in commands:
        if m & {3, 4}:
            fail(f"line {number}: M3/M4 starts the spindle; the spindle stays off")
        if g & {28, 30}:
            fail(f"line {number}: G28/G30 moves the guide to a stored position")
    m6 = next((number for number, _g, m, _a in commands if 6 in m), None)
    motions = [(number, g, axes) for number, g, _m, axes in commands if axes]
    if m6 is None or (motions and motions[0][0] < m6):
        fail("motion before the M6: the guide's length is not set")
    if not motions or not (53 in motions[0][1] and 0 in motions[0][1] and set(motions[0][2]) == {"Z"}):
        fail("the first motion is not a G53 G0 Z retract to the top")
    xy = None
    for number, g, axes in motions[1:]:
        if g & {1, 2, 3} or g & {28, 30, 53}:
            fail(f"line {number}: only G0 in part coordinates may follow the retract")
        if "Z" in axes:
            fail(f"line {number}: a Z move in part coordinates; the operator jogs the guide down")
        if "X" in axes and "Y" in axes:
            xy = (axes["X"], axes["Y"])
    if program.cutting:
        fail(f"{len(program.cutting)} feed moves")
    if xy is None or not (_close(xy[0], at[0]) and _close(xy[1], at[1])):
        fail(f"ends over {xy}, expected over {tuple(at)}")
    if not commands or 30 not in commands[-1][2]:
        fail("the last command is not M30 (the controller must end Idle)")
    if 53 in (motions[0][1] if motions else set()) and motions[0][2].get("Z", -math.inf) < machine_top:
        fail(f"the G53 retract names Z{motions[0][2]['Z']:.3f}, below the machine top {machine_top:.3f}")
    return findings


def check_probe_zero(program: Program, axis: str, value: float, z_top: float) -> list[Finding]:
    """The probe sets one work zero: exactly one ``G10 L20 P1``, naming only
    ``axis`` = ``value``, straight after a ``G38.2`` along ``axis`` alone; no
    feed move in the program and the spindle off at every probing move (a
    touch probe is never spun); every rapid that moves X or Y stays above the
    stock top ``z_top`` (the probe descends beside the stock by ``G38.3``)."""
    findings = []
    offsets = [p for p in program.probes if p.code == 10.0]
    if len(offsets) != 1:
        return [Finding(program.name, "probe", f"{len(offsets)} G10 L20 P1 settings, expected 1")]
    offset = offsets[0]
    if dict(offset.axes).keys() != {axis} or not _close(dict(offset.axes)[axis], value):
        findings.append(Finding(program.name, "probe", f"line {offset.line}: G10 L20 P1 sets {dict(offset.axes)}, expected {axis}{value:.3f}"))
    before = [p for p in program.probes if p.line < offset.line]
    if not before or before[-1].code != 38.2 or [a for a, _v in before[-1].axes] != [axis]:
        findings.append(Finding(program.name, "probe", f"line {offset.line}: G10 L20 P1 not straight after a G38.2 along {axis}"))
    for p in program.probes:
        if p.spindle_on:
            findings.append(Finding(program.name, "probe", f"line {p.line}: probing with the spindle on"))
    if program.cutting:
        findings.append(Finding(program.name, "probe", f"{len(program.cutting)} feed moves in a probe section"))
    for m in program.moves:
        lateral = not (_close(m.start[0], m.end[0]) and _close(m.start[1], m.end[1]))
        if lateral and min(m.start[2], m.end[2]) <= z_top + _TOL_MM:
            findings.append(Finding(program.name, "probe", f"G0 to X{m.end[0]:.3f} Y{m.end[1]:.3f} at Z{min(m.start[2], m.end[2]):.3f}, not above {z_top:.3f}"))
    return findings


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
        findings.append(Finding(program.name, "holes", f"no plunge at {missing}"))
    if extra:
        findings.append(Finding(program.name, "holes", f"unexpected plunge at {extra}"))
    shallow = sorted((xy, z) for xy, z in bottoms.items() if xy in expected and not _close(z, z_bottom))
    if shallow:
        findings.append(Finding(program.name, "holes", f"bottom ≠ {z_bottom:.3f} at {shallow}"))
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
            findings.append(Finding(program.name, "rapid", f"G0 to Z{m.end[2]:.3f} at X{xy[0]} Y{xy[1]} below stock top {z_top:.3f}"))
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
                program.name, "lateral",
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
    z_top: float = 0.0,
) -> list[Finding]:
    """Cutting moves below the stock top ``z_top`` whose endpoint lies in the XY
    ``window`` sweep a path spanning exactly ``x`` × ``y`` (the cutter-centre
    envelope of a pocket or slot, arcs included), reach exactly ``z_min``, and
    turn every arc one way: ``arc`` is ``"G2"`` (clockwise; conventional inside
    a pocket with a right-hand spindle) or ``"G3"``. With ``entry``, every
    plunge (a descending Z-only feed) in the window is within ``_ENTRY_TOL_MM``
    of that XY: a CAM system enters at the path vertex nearest the point asked."""
    (wx0, wx1), (wy0, wy1) = window
    inside = [
        m for m in program.cutting
        if m.end[2] < z_top and wx0 <= m.end[0] <= wx1 and wy0 <= m.end[1] <= wy1
    ]
    if not inside:
        return [Finding(program.name, "bounds", f"no cutting move in window {window}")]
    points = [p for m in inside for p in (*m.extremes(), *([m.start] if m.start[2] < z_top else []))]
    got_x = (min(p[0] for p in points), max(p[0] for p in points))
    got_y = (min(p[1] for p in points), max(p[1] for p in points))
    findings = []
    if not all(_close(a, b) for a, b in zip((*got_x, *got_y), (*x, *y))):
        findings.append(Finding(
            program.name, "bounds",
            f"cutter centre X[{got_x[0]:.3f},{got_x[1]:.3f}] Y[{got_y[0]:.3f},{got_y[1]:.3f}], "
            f"expected X[{x[0]:.3f},{x[1]:.3f}] Y[{y[0]:.3f},{y[1]:.3f}]",
        ))
    if entry is not None:
        plunges = sorted({
            (round(m.end[0], 3), round(m.end[1], 3)) for m in inside
            if m.motion is Motion.LINEAR and m.end[2] < m.start[2] and _close(m.start[0], m.end[0]) and _close(m.start[1], m.end[1])
        })
        if not plunges or any(math.dist((px, py), entry) > _ENTRY_TOL_MM for px, py in plunges):
            findings.append(Finding(program.name, "bounds", f"plunges at {plunges}, expected only at X{entry[0]:.3f} Y{entry[1]:.3f}"))
    lowest = min(m.end[2] for m in inside)
    if not _close(lowest, z_min):
        findings.append(Finding(program.name, "bounds", f"deepest Z {lowest:.3f} in {window}, expected {z_min:.3f}"))
    wanted = {"G2": Motion.ARC_CW, "G3": Motion.ARC_CCW}[arc]
    senses = {m.motion for m in inside if m.motion in (Motion.ARC_CW, Motion.ARC_CCW)}
    if senses != {wanted}:
        findings.append(Finding(program.name, "bounds", f"arcs {sorted(s.name for s in senses)}, expected only {arc}"))
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
    cut: str | None = None,
) -> list[Finding]:
    """Straight side-cut passes along the other axis, longer than ``span``, at
    constant ``axis`` coordinate and below ``below_z``: the last pass sits at
    ``final``, every pass runs in ``direction`` (+1/-1) along the other axis (the
    side's measured settings are for one milling direction), and no pass
    removes more than ``max_step``. ``raw`` is the cutter-centre coordinate that
    just touches the raw face, so each step is the distance between consecutive
    pass positions, starting from ``raw``. With ``finish``, the final pass
    removes no more than that finishing step. With ``max_stepdown``, the pass
    depths step down from ``below_z`` (the stock top) by no more than that.

    With ``cut`` ("conventional" or "climb", the recipe's declaration), every
    pass cuts that way: the stock lies on the side of the passes that ``raw``
    steps toward ``final`` (each pass cuts into it), and under the spindle's
    turn in force at the pass (M3 clockwise seen from above) stock on the
    cutter's left of its travel is conventional, on its right climb (M4 the
    reverse). A pass with the spindle stopped fails. Without ``cut`` the
    passes' milling direction is not judged."""
    if cut not in (None, *CUT_DIRECTIONS):
        raise ValueError(f"cut {cut!r} is not one of {CUT_DIRECTIONS}")
    a = "XY".index(axis)
    b = 1 - a
    passes = [
        m for m in program.cutting
        if m.motion is Motion.LINEAR and _close(m.start[a], m.end[a]) and abs(m.end[b] - m.start[b]) > span
        and m.end[2] < below_z and _close(m.start[2], m.end[2])
        and min(raw, final) - _TOL_MM <= m.end[a] <= max(raw, final) + _TOL_MM
    ]
    if not passes:
        return [Finding(program.name, "passes", f"no {axis}-constant pass longer than {span}")]
    toward = 1.0 if final > raw else -1.0
    stations = sorted({round(m.end[a], 3) for m in passes}, key=lambda v: toward * v)
    findings = []
    if not _close(stations[-1], final):
        findings.append(Finding(program.name, "passes", f"final {axis} {stations[-1]:.3f}, expected {final:.3f}"))
    previous = raw
    for index, station in enumerate(stations):
        step = toward * (station - previous)
        limit = finish if finish is not None and index == len(stations) - 1 else max_step
        if step > limit + _TOL_MM:
            findings.append(Finding(program.name, "passes", f"{axis} {station:.3f} removes {step:.3f} > {limit:.3f}"))
        previous = station
    if max_stepdown is not None:
        for station in stations:
            levels = sorted({round(m.end[2], 3) for m in passes if _close(m.end[a], station)}, reverse=True)
            previous = below_z
            for level in levels:
                if previous - level > max_stepdown + _TOL_MM:
                    findings.append(Finding(
                        program.name, "passes",
                        f"{axis} {station:.3f}: Z {level:.3f} steps down {previous - level:.3f} > {max_stepdown:.3f}",
                    ))
                previous = level
    sign = "+" if direction > 0 else "-"
    for m in passes:
        if (m.end[b] - m.start[b]) * direction <= 0:
            findings.append(Finding(
                program.name, "passes",
                f"{axis} {m.end[a]:.3f} Z {m.end[2]:.3f}: pass does not run {sign}{'XY'[b]}",
            ))
    if cut is not None:
        findings += _cut_direction_findings(program, passes, a, toward, cut)
    return findings


def _cut_direction_findings(program: Program, passes: list[Move], a: int, toward: float, cut: str) -> list[Finding]:
    """Each straight pass along axis ``1 - a`` with the stock ``toward`` along
    axis ``a``: the way it cuts against the declared ``cut``."""
    b = 1 - a
    findings = []
    for m in passes:
        travel = [0.0, 0.0]
        travel[b] = math.copysign(1.0, m.end[b] - m.start[b])
        stock = [0.0, 0.0]
        stock[a] = toward
        # Seen from above (+Z): the stock is on the travel's left when travel x stock points up.
        left = travel[0] * stock[1] - travel[1] * stock[0] > 0
        where = f"{'XY'[a]} {m.end[a]:.3f} Z {m.end[2]:.3f}"
        if m.spindle == 0:
            findings.append(Finding(program.name, "cut", f"{where}: spindle stopped (no M3/M4 in force), declared {cut}"))
            continue
        ran = CUT_DIRECTIONS[0] if (1 if left else -1) * m.spindle > 0 else CUT_DIRECTIONS[1]
        if ran != cut:
            findings.append(Finding(
                program.name, "cut",
                f"{where}: pass runs {'+' if travel[b] > 0 else '-'}{'XY'[b]} with the stock on the cutter's "
                f"{'left' if left else 'right'} under M{3 if m.spindle > 0 else 4}: {ran}, declared {cut}",
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
            program.name, "air_feed",
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
        Finding(program.name, "return", f"G0 {axis}{m.start[i]:.3f} -> {axis}{m.end[i]:.3f} travels {abs(m.end[i] - m.start[i]):.3f} > {span:.3f}")
        for m in program.moves
        if m.motion is Motion.RAPID and abs(m.end[i] - m.start[i]) > span
    ]


def check_face_passes(
    program: Program,
    z: float,
    y: tuple[float, float],
    max_engagement: float,
    radius: float,
    span: float,
    overhang: float = 0.0,
) -> list[Finding]:
    """A zigzag face of the stock's Y extent ``y``: the straight X passes
    longer than ``span`` at depth ``z`` alternate direction pass to pass; each
    pass, in cutting order, takes at most ``max_engagement`` of stock no
    earlier pass cut (the radial width the plan's force estimate assumes, the
    first pass included); together the cutter (``radius``) clears all of ``y``
    and reaches ``overhang`` past both edges."""
    passes = [
        m for m in program.cutting
        if m.motion is Motion.LINEAR and _close(m.start[2], z) and _close(m.end[2], z)
        and _close(m.start[1], m.end[1]) and abs(m.end[0] - m.start[0]) > span
    ]
    if not passes:
        return [Finding(program.name, "face", f"no X pass longer than {span} at Z {z:.3f}")]
    findings = []
    for before, after in zip(passes, passes[1:]):
        if (before.end[0] - before.start[0]) * (after.end[0] - after.start[0]) > 0:
            findings.append(Finding(program.name, "face", f"passes at Y {before.end[1]:.3f} and Y {after.end[1]:.3f} run the same way"))
    cut: list[tuple[float, float]] = []  # disjoint Y intervals of stock already cut
    for m in passes:
        low, high = max(m.end[1] - radius, y[0]), min(m.end[1] + radius, y[1])
        reach = max(high - low, 0.0)
        engaged = reach - sum(max(0.0, min(high, b) - max(low, a)) for a, b in cut)
        if engaged > max_engagement + _TOL_MM:
            findings.append(Finding(program.name, "face", f"pass at Y {m.end[1]:.3f} engages {engaged:.3f} > {max_engagement:.3f}"))
        if reach > 0:
            merged = [(low, high)]
            for a, b in cut:
                if b < merged[0][0] or a > merged[0][1]:
                    merged.append((a, b))
                else:
                    merged[0] = (min(a, merged[0][0]), max(b, merged[0][1]))
            cut = merged
    stations = sorted(m.end[1] for m in passes)
    cleared = sum(b - a for a, b in cut)
    if (cleared < y[1] - y[0] - _TOL_MM or stations[0] - radius > y[0] - overhang + _TOL_MM
            or stations[-1] + radius < y[1] + overhang - _TOL_MM):
        findings.append(Finding(
            program.name, "face",
            f"cutter covers Y[{stations[0] - radius:.3f},{stations[-1] + radius:.3f}] clearing {cleared:.3f} of "
            f"face Y[{y[0]:.3f},{y[1]:.3f}] ±{overhang:.3f}",
        ))
    return findings


def check_feed_out(program: Program, z_top: float) -> list[Finding]:
    """No rapid leaves from below the stock top: a reamer (or anything else in
    a finished bore) is fed out, never rapided out, which can score the bore."""
    return [
        Finding(
            program.name,
            "feed_out",
            f"G0 from X{m.start[0]:.3f} Y{m.start[1]:.3f} Z{m.start[2]:.3f}, "
            f"below the stock top {z_top:.3f}",
        )
        for m in program.moves
        if m.motion is Motion.RAPID and m.start[2] < z_top - _TOL_MM
    ]


# Outline checks sample each feed move at most this far apart along XY.
_SAMPLE_MM = 0.25
# How many offending points an outline finding lists before summarising.
_SHOWN = 3

Point = Sequence[float]


def _xy_points(m: Move, step: float = _SAMPLE_MM) -> list[tuple[float, ...]]:
    """Points along ``m`` no more than ``step`` apart in XY, its end included, its
    start not. A G17 arc is sampled on its circle; any other arc as its chord."""
    if m.centre is not None and m.plane == 17:
        a, b, radius, begin, sweep = m._arc()
        sense = -1.0 if m.motion is Motion.ARC_CW else 1.0
        n = max(1, math.ceil(radius * sweep / step))
        angles = [begin + sense * sweep * k / n for k in range(1, n + 1)]
        rise = m.end[2] - m.start[2]
        return [
            (
                m.centre[a] + radius * math.cos(angle),
                m.centre[b] + radius * math.sin(angle),
                m.start[2] + rise * k / n,
            )
            for k, angle in enumerate(angles, 1)
        ]
    n = max(1, math.ceil(math.dist(m.start[:2], m.end[:2]) / step))
    pairs = list(zip(m.start, m.end))
    return [tuple(s + (e - s) * k / n for s, e in pairs) for k in range(1, n + 1)]


def _first_inside(m: Move, lo: Point, hi: Point) -> Point | None:
    """The first point of ``m`` (start included) inside the closed box from
    ``lo`` to ``hi``: exact for a line, the start and :func:`_xy_points`
    samples for an arc."""
    if m.centre is not None:
        points = (m.start, *_xy_points(m))
        return next(
            (p for p in points if all(a <= v <= b for v, a, b in zip(p, lo, hi))),
            None,
        )
    t0, t1 = 0.0, 1.0
    for s, e, a, b in zip(m.start, m.end, lo, hi):
        if s == e:
            if not a <= s <= b:
                return None
            continue
        ta, tb = sorted(((a - s) / (e - s), (b - s) / (e - s)))
        t0, t1 = max(t0, ta), min(t1, tb)
        if t0 > t1:
            return None
    return tuple(s + (e - s) * t0 for s, e in zip(m.start, m.end))


def _cross(o: Point, a: Point, b: Point) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _element_distance(element: dict, p: Point) -> tuple[float, Point | None]:
    """XY distance from ``p`` to an outline element (a line from ``start`` to
    ``end``, or with ``centre`` the minor arc between them on its circle), and
    the element's direction (start to end) where ``p`` projects onto its
    interior; ``None`` where its nearest point is an end (a corner)."""
    s, e = element["start"], element["end"]
    c = element.get("centre")
    if c is not None:
        turn = _cross(c, s, e)
        # Within the arc's sector: between its end radii, on the arc's side.
        mid = (s[0] + e[0] - 2 * c[0], s[1] + e[1] - 2 * c[1])
        bisector = (p[0] - c[0]) * mid[0] + (p[1] - c[1]) * mid[1]
        if _cross(c, s, p) * turn > 0 and _cross(c, p, e) * turn > 0 and bisector > 0:
            sign = 1.0 if turn > 0 else -1.0
            tangent = (-sign * (p[1] - c[1]), sign * (p[0] - c[0]))
            return abs(math.dist(c, p[:2]) - math.dist(c, s)), tangent
        return min(math.dist(s, p[:2]), math.dist(e, p[:2])), None
    dx, dy = e[0] - s[0], e[1] - s[1]
    if dx == 0.0 and dy == 0.0:  # a Z-only move
        return math.dist(s, p[:2]), None
    t = ((p[0] - s[0]) * dx + (p[1] - s[1]) * dy) / (dx * dx + dy * dy)
    clamped = max(0.0, min(1.0, t))
    foot = (s[0] + clamped * dx, s[1] + clamped * dy)
    return math.dist(foot, p[:2]), ((dx, dy) if 0.0 < t < 1.0 else None)


def _element_samples(element: dict, step: float) -> list[tuple[float, float]]:
    s, e = element["start"], element["end"]
    c = element.get("centre")
    if c is None:
        n = max(1, math.ceil(math.dist(s, e) / step))
        dx, dy = e[0] - s[0], e[1] - s[1]
        return [(s[0] + dx * k / n, s[1] + dy * k / n) for k in range(n + 1)]
    radius = math.dist(c, s)
    begin = math.atan2(s[1] - c[1], s[0] - c[0])
    end = math.atan2(e[1] - c[1], e[0] - c[0])
    sweep = (end - begin + math.pi) % (2 * math.pi) - math.pi  # minor arc
    n = max(1, math.ceil(radius * abs(sweep) / step))
    angles = [begin + sweep * k / n for k in range(n + 1)]
    return [(c[0] + radius * math.cos(a), c[1] + radius * math.sin(a)) for a in angles]


def _report(
    findings: list[Finding], name: str, what: str, items: list[str], check="outline"
) -> None:
    """One finding listing the first offending ``items``."""
    if items:
        shown = "; ".join(items[:_SHOWN])
        more = f" (+{len(items) - _SHOWN} more)" if len(items) > _SHOWN else ""
        detail = f"{len(items)} {what}: {shown}{more}"
        findings.append(Finding(name, check, detail))


def _where(p: Point) -> str:
    return f"X{p[0]:.3f} Y{p[1]:.3f} Z{p[2]:.3f}"


def _element_side(element: dict, p: Point) -> str:
    """Which side of an outline element's running way (start to end) ``p``
    lies on, seen from above: ``"left"`` or ``"right"``. On an arc the left
    of an anticlockwise run is inside its circle."""
    s, e = element["start"], element["end"]
    c = element.get("centre")
    if c is None:
        return "left" if _cross(s, e, p) > 0 else "right"
    inside = math.dist(c, p[:2]) < math.dist(c, s)
    return "left" if inside == (_cross(c, s, e) > 0) else "right"


def _judge_cut(
    point: Point,
    step: tuple[float, float],
    tangent: tuple[float, float] | None,
    element: dict,
    part: str,
    cut: str,
    spindle: int,
    wrong: dict[str, list[str]],
) -> None:
    """One outline pass point against the declared ``cut``, the part lying on
    ``part`` of its nearest ``element``'s way (:func:`check_outline`); each
    fault is added to ``wrong`` under its description."""
    where = _where(point)
    if spindle == 0:
        wrong.setdefault(f"pass points with the spindle stopped (no M3/M4 in force), declared {cut}", []).append(where)
        return
    if tangent is not None:
        if _element_side(element, point) == part:
            wrong.setdefault(f"cutter centres on the part's side ({part}) of their element", []).append(
                f"{where} ({element['name']})"
            )
            return
        along = step[0] * tangent[0] + step[1] * tangent[1] >= 0
        part_left = (part == "left") == along
    else:
        # A corner: the part is on the side the corner point lies from the centre.
        s, e = element["start"], element["end"]
        corner = s if math.dist(s, point[:2]) <= math.dist(e, point[:2]) else e
        turn = step[0] * (corner[1] - point[1]) - step[1] * (corner[0] - point[0])
        if abs(turn) < 1e-12:
            return
        part_left = turn > 0
    ran = CUT_DIRECTIONS[0] if (1 if part_left else -1) * spindle > 0 else CUT_DIRECTIONS[1]
    if ran != cut:
        side = "left" if part_left else "right"
        what = f"pass points cutting {ran} (the part on the cutter's {side} under M{3 if spindle > 0 else 4}), declared {cut}"
        wrong.setdefault(what, []).append(where)


def check_arcs(
    program: Program,
    z_top: float,
    centres: Iterable[tuple[float, float]],
    part: str,
    cut: str,
    radius: float | None = None,
) -> list[Finding]:
    """The G17 arcs fed below ``z_top`` about each of ``centres`` (XY, a bore's
    or a round's axis; with ``radius``, only the cutter-centre circle of that
    radius about it) cut the declared way. ``part`` says where the part
    lies from the arc's circle, as the recipe states: ``"outside"`` (a bore,
    a counterbore: the wall beyond the cutter's outer edge) or ``"inside"``
    (a round, a boss: the wall inside its inner edge). The part is on the
    cutter's left when it lies outside a clockwise (G2) arc or inside an
    anticlockwise (G3) one: under M3 conventional, else climb (M4 the
    reverse). An arc with the spindle stopped fails, and so does a centre
    no arc is fed about. Straight moves (entries, plunges) are not judged."""
    if cut not in CUT_DIRECTIONS:
        raise ValueError(f"cut {cut!r} is not one of {CUT_DIRECTIONS}")
    if part not in ("inside", "outside"):
        raise ValueError(f"part {part!r} is not 'inside' or 'outside'")
    findings: list[Finding] = []
    for centre in centres:
        arcs = [
            m for m in program.cutting
            if m.centre is not None and m.plane == 17 and min(m.start[2], m.end[2]) < z_top - _TOL_MM
            and _close(m.centre[0], centre[0]) and _close(m.centre[1], centre[1])
            and (radius is None or abs(math.dist(m.start[:2], m.centre[:2]) - radius) <= _ENTRY_TOL_MM)
        ]
        if not arcs:
            about = f"X{centre[0]:.3f} Y{centre[1]:.3f}" + ("" if radius is None else f" at R{radius:.3f}")
            findings.append(Finding(program.name, "cut", f"no arc fed below Z{z_top:.3f} about {about}"))
        for m in arcs:
            code = "G2" if m.motion is Motion.ARC_CW else "G3"
            where = f"line {m.line} {code} about X{centre[0]:.3f} Y{centre[1]:.3f} to Z{m.end[2]:.3f}"
            if m.spindle == 0:
                findings.append(Finding(program.name, "cut", f"{where}: spindle stopped (no M3/M4 in force), declared {cut}"))
                continue
            left = (part == "outside") == (m.motion is Motion.ARC_CW)
            ran = CUT_DIRECTIONS[0] if (1 if left else -1) * m.spindle > 0 else CUT_DIRECTIONS[1]
            if ran != cut:
                findings.append(Finding(
                    program.name, "cut",
                    f"{where}, the part {part} it, under M{3 if m.spindle > 0 else 4}: {ran}, declared {cut}",
                ))
    return findings


def check_outline(
    program: Program,
    elements: Sequence[dict],
    passes: Sequence[dict],
    z_top: float,
    clearing: Sequence[dict] = (),
    tabs: Sequence[dict] = (),
    leads: Sequence[dict] = (),
    cut: str | None = None,
    part: str | None = None,
) -> list[Finding]:
    """Profile passes round a closed part outline. ``elements`` are its lines
    and minor arcs (``start``, ``end``, optional ``centre``) in the order and
    direction the cutter runs, each with a ``name`` and the ``tol`` the cutter
    centre may stray from its offset there; ``passes``, in the order they are
    cut, are each a cutter-centre ``offset`` from the outline and its depth
    ``levels``. Below the stock top ``z_top`` every feed move that moves in XY
    runs level, every point of it lies at a pass's offset from the nearest
    element at one of that pass's levels (no gouge, no stray), no pass's
    point comes after a later pass's, and every point runs the element's way
    (anticlockwise elements: conventional outside the part with a clockwise
    spindle). Each pass covers the whole outline at each of its levels.

    Each of ``clearing`` is waste cleared before the passes, an ``x`` range
    and its ``levels``: there a point farther from the outline than every
    pass offset (plus the element's ``tol``) at one of those levels is
    clearing, not a stray; :func:`check_cleared` checks what it clears and
    :func:`check_keep_out` what it must miss.

    Each of ``leads`` is a ``centre`` and ``radius`` inside waste the
    clearing has already cut, with its ``levels``, where a pass is entered
    and left on arcs (a bore's finish circle, from and back to its centre):
    a waste point inside one at one of its levels is neither clearing nor a
    stray and is in no order, so each pass's lead-out and the next one's
    lead-in may follow it. The direction rule still holds there.

    Each of ``tabs`` is a bridge the passes leave standing to hold the part:
    a ``name``, an ``x`` × ``y`` box spanning the outline and every pass's
    cutter-centre path across the tab (its ends square to the path; the tab
    is the box's length along the path less the cutter's diameter), the
    tab's ``top`` and ``floor`` Z and the recipe's ``thickness``. Below its
    top no cutter centre enters the box on any feed move, plunges and ramps
    included; every pass cut below its top hops over it level at exactly its
    top and at the pass's offset, and that hop is the only XY feed allowed
    off the levels. Only there, and only at levels under its top, is the
    outline excused coverage. Each tab must stand: its top less its floor is
    the recipe's thickness, a level reaches its floor, its box holds outline
    and every pass cut below its top hops it.

    With ``cut`` ("conventional" or "climb", the recipe's declaration) and
    ``part`` ("left" or "right": the side of the elements' running way the
    part lies on, which the recipe states), every pass point is judged
    from the posted path: the cutter centre must lie on the other side of
    its nearest element (a centre on the part's side is in the part), and
    with the part's side of the travel (the element's side for a point
    running the element's way, the reverse for one running against it; at
    a corner, the side the corner lies on from the centre) and the
    spindle's turn in force (M3 clockwise seen from above: the part on
    the cutter's left is conventional, on its right climb; M4 the
    reverse), it must cut the declared way. A pass point with the spindle
    stopped fails. Clearing and lead points are not judged: their stock is
    not the outline's. G2 or G3 alone cannot say it: on an anticlockwise
    outside outline the convex corners are G3 and the concave ones G2,
    all conventional."""
    if cut not in (None, *CUT_DIRECTIONS):
        raise ValueError(f"cut {cut!r} is not one of {CUT_DIRECTIONS}")
    if (cut is None) != (part is None) or part not in (None, "left", "right"):
        raise ValueError(f"cut and part go together (part 'left' or 'right'), got cut {cut!r}, part {part!r}")
    name = program.name
    findings: list[Finding] = []
    levels = {round(z, 3) for p in passes for z in p["levels"]}
    levels |= {round(z, 3) for c in clearing for z in c["levels"]}
    levels |= {round(z, 3) for c in leads for z in c["levels"]}

    def inside(tab: dict, p: Point, margin: float = 0.0) -> bool:
        (x0, x1), (y0, y1) = tab["x"], tab["y"]
        return x0 - margin <= p[0] <= x1 + margin and y0 - margin <= p[1] <= y1 + margin

    def hop_of(p: Point) -> dict | None:
        """The tab whose top ``p`` rides, inside its box."""
        return next(
            (t for t in tabs if _close(p[2], t["top"]) and inside(t, p, _TOL_MM)),
            None,
        )

    def hop(m: Move) -> bool:
        return (
            bool(tabs)
            and _close(m.start[2], m.end[2])
            and all(hop_of(q) is not None for q in (m.start, *_xy_points(m)))
        )

    moves = [
        m
        for m in program.cutting
        if min(m.start[2], m.end[2]) < z_top - _TOL_MM
        and not (_close(m.start[0], m.end[0]) and _close(m.start[1], m.end[1]))
    ]
    if not moves:
        return [Finding(name, "outline", f"no XY feed move below Z{z_top:.3f}")]
    off_level = [
        f"{_where(m.end)} from Z{m.start[2]:.3f}"
        for m in moves
        if not hop(m)
        and (
            not _close(m.start[2], m.end[2])
            or not any(_close(m.end[2], z) for z in levels)
        )
    ]
    _report(findings, name, f"XY feed moves off the levels {sorted(levels)}", off_level)

    def at(z: float, zs: Iterable[float]) -> bool:
        return any(_close(z, v) for v in zs)

    # (pass index, level) -> grid cell -> that pass's cutter-centre points
    grids: dict[tuple[int, float], dict[tuple[int, int], list[Point]]] = {}
    stray: list[str] = []
    backward: list[str] = []
    late: list[str] = []
    stage = 0  # 0 clearing, k + 1 pass k: the latest cut so far
    hops: dict[str, set[int]] = {t["name"]: set() for t in tabs}
    bites: dict[str, list[str]] = {t["name"]: [] for t in tabs}
    for t in tabs:
        (x0, x1), (y0, y1) = t["x"], t["y"]
        lo = (x0 + _TOL_MM, y0 + _TOL_MM, -math.inf)
        hi = (x1 - _TOL_MM, y1 - _TOL_MM, t["top"] - _TOL_MM)
        for m in program.cutting:
            point = _first_inside(m, lo, hi)
            if point is not None:
                bites[t["name"]].append(_where(point))
    farthest = max(p["offset"] for p in passes)
    # What a declared cut finds, by kind, each with its points.
    wrong: dict[str, list[str]] = {}
    cell = farthest + max(e["tol"] for e in elements) + _SAMPLE_MM
    for m in moves:
        previous = m.start
        for point in _xy_points(m):
            nearest = [(*_element_distance(e, point), e) for e in elements]
            distance, tangent, element = min(nearest, key=lambda item: item[0])
            step = (point[0] - previous[0], point[1] - previous[1])
            if tangent is not None:
                if step[0] * tangent[0] + step[1] * tangent[1] < 0:
                    backward.append(_where(point))
            previous = point
            level = next((z for z in levels if _close(point[2], z)), None)
            tab = hop_of(point)
            if tab is not None:
                riding = {
                    k
                    for k, p in enumerate(passes)
                    if abs(distance - p["offset"]) <= element["tol"]
                }
                hops[tab["name"]] |= riding
                if level is None:  # the hop: at a pass's offset, never stage
                    if not riding:
                        where = f"{_where(point)} is {distance:.3f}"
                        stray.append(f"{where} from {element['name']}")
                    continue
            waste = distance > farthest + element["tol"]
            if waste and any(
                math.dist(c["centre"], point[:2]) <= c["radius"] + _TOL_MM
                and at(point[2], c["levels"])
                for c in leads
            ):
                continue
            if waste and any(
                c["x"][0] <= point[0] <= c["x"][1] and at(point[2], c["levels"])
                for c in clearing
            ):
                stages = [0]
            else:
                stages = [
                    k + 1
                    for k, p in enumerate(passes)
                    if abs(distance - p["offset"]) <= element["tol"]
                    and at(point[2], p["levels"])
                ]
                if not stages:
                    where = f"{_where(point)} is {distance:.3f}"
                    stray.append(f"{where} from {element['name']}")
                    continue
                if cut is not None:
                    _judge_cut(point, step, tangent, element, part, cut, m.spindle, wrong)
            # A point two passes could own goes to the earliest not yet done.
            chosen = min((s for s in stages if s >= stage), default=min(stages))
            if chosen < stage:
                late.append(_where(point))
            stage = max(stage, chosen)
            key = (int(point[0] // cell), int(point[1] // cell))
            for k in (s - 1 for s in stages if s and level is not None):
                grid = grids.setdefault((k, level), {})
                grid.setdefault(key, []).append(point[:2])
    what = "cutter-centre points off every pass offset or its levels"
    _report(findings, name, what, stray)
    _report(findings, name, "points running against the outline's way", backward)
    for what, items in wrong.items():
        _report(findings, name, what, items, check="cut")
    _report(findings, name, "points of a pass cut after a later pass", late)
    samples = [(e, s) for e in elements for s in _element_samples(e, 1.0)]
    for k, p in enumerate(passes):
        reach = p["offset"]
        for z in p["levels"]:
            grid = grids.get((k, round(z, 3)), {})
            excused = [t for t in tabs if z < t["top"] - _TOL_MM]
            uncovered = []
            for element, s in samples:
                if any(inside(t, s) for t in excused):
                    continue
                limit = reach + element["tol"]
                cx, cy = int(s[0] // cell), int(s[1] // cell)
                cells = [(cx + i, cy + j) for i in (-1, 0, 1) for j in (-1, 0, 1)]
                near = (q for c in cells for q in grid.get(c, ()))
                if not any(math.dist(q, s) <= limit for q in near):
                    uncovered.append(f"{element['name']} at X{s[0]:.3f} Y{s[1]:.3f}")
            what = f"outline points the offset-{reach:.3f} pass leaves uncut at"
            _report(findings, name, f"{what} Z{z:.3f}", uncovered)
    pass_levels = [z for p in passes for z in p["levels"]]
    for t in tabs:
        tab = f"tab {t['name']}"
        thick = t["top"] - t["floor"]
        if not _close(thick, t["thickness"]):
            detail = f"{tab} is {thick:.3f} thick, the recipe's {t['thickness']:.3f}"
            findings.append(Finding(name, "outline", detail))
        if not any(z <= t["floor"] + _TOL_MM for z in pass_levels):
            detail = f"{tab}: no level reaches its floor Z{t['floor']:.3f}"
            findings.append(Finding(name, "outline", detail))
        if not any(inside(t, s) for _e, s in samples):
            findings.append(
                Finding(name, "outline", f"{tab}: its box holds no outline")
            )
        if not hops[t["name"]]:
            detail = f"{tab}: no pass hops it at Z{t['top']:.3f}"
            findings.append(Finding(name, "outline", detail))
        else:
            for k, p in enumerate(passes):
                below = any(z < t["top"] - _TOL_MM for z in p["levels"])
                if below and k not in hops[t["name"]]:
                    detail = (
                        f"{tab}: the offset-{p['offset']:.3f} pass, cut below its "
                        f"top, never hops it at Z{t['top']:.3f}"
                    )
                    findings.append(Finding(name, "outline", detail))
        what = f"cutter centres below {tab}'s top Z{t['top']:.3f} in its box"
        _report(findings, name, what, bites[t["name"]])
    return findings


def check_cleared(
    program: Program, points: Sequence[Point], radius: float, z: float
) -> list[Finding]:
    """Waste cleared to depth: a level feed move at ``z`` passes within the
    cutter ``radius`` of every XY point in ``points``."""
    cutting = program.cutting
    level = [m for m in cutting if _close(m.start[2], z) and _close(m.end[2], z)]
    uncut = [
        f"X{p[0]:.3f} Y{p[1]:.3f}"
        for p in points
        if not any(_move_distance(m, p) <= radius + _TOL_MM for m in level)
    ]
    findings: list[Finding] = []
    what = f"points no cut at Z{z:.3f} clears"
    _report(findings, program.name, what, uncut, "cleared")
    return findings


def _box_distance(box: dict, p: Point) -> float:
    (x0, x1), (y0, y1) = box["x"], box["y"]
    dx = max(x0 - p[0], 0.0, p[0] - x1)
    dy = max(y0 - p[1], 0.0, p[1] - y1)
    return math.hypot(dx, dy)


# A vise jaw, a clamp or a strap clamp, by its keep-out shape's name: the noun
# (jaw, clamp, strap, singular or plural) after at most two qualifiers, then
# optionally an index or a side, then optionally a parenthesised tool part
# ("fixed jaw", "left step clamps", "step clamp 3", "plate strap left",
# "moving jaw (the arbor's cap below the saw)": a recipe that checks an
# arbor's parts shifts the jaw's top by the part's reach, so the gap is that
# part's air over the jaw). Supports under or beside them ("fixed-jaw
# parallel", "stacks at the moving jaw", "vise bed", the strap's "plate block
# left"), the vise body ("the vise past the plate") and stock between them
# ("the bars between the jaws") are not. test_cam_nc lists every fixture name
# the posted recipes declare with "jaw", "clamp" or "strap" in it.
_JAW_SHAPE = re.compile(
    r"^(?:(?!(?:the|at|between|past|on|under|beside)\b)[\w-]+ ){0,2}"
    r"(?:jaw|jaws|clamp|clamps|strap|straps)(?: (?:\d+|left|right))?(?: \(.*\))?$",
    re.IGNORECASE,
)


def is_jaw_shape(name: str) -> bool:
    return bool(_JAW_SHAPE.match(name))


def check_keep_out(
    program: Program,
    radius: float,
    boxes: Sequence[dict] = (),
    circles: Sequence[dict] = (),
    clearance: float = 0.0,
) -> list[Finding]:
    """No move, rapid or feed, brings the cutter (``radius``) into a fixture
    shape below its top: each of ``boxes`` an ``x`` × ``y`` rectangle, each of
    ``circles`` a ``centre`` and ``radius``, each with a ``name`` and a
    ``z_top`` below which the cutter must miss it. A shape with a
    ``z_bottom`` (stock overhanging its support, air under it) spans only the
    band between the two: there the cutter's path from one sampled point to
    the next must not cross the band within reach of either point. A recipe
    whose tool reaches above or below its programmed point (an arbor's
    spacers and nut round a slitting saw) checks each such part with every
    shape's band shifted by the part's reach.

    Over a vise jaw or a clamp (:func:`is_jaw_shape`; no ``z_bottom``) the
    cutter keeps ``clearance`` of air: a point within its reach of the shape
    and at or above the top but less than ``clearance`` over it is a
    ``jaw_clearance`` finding naming the file, the least clearance and its
    line. The programmed point is the tool's lowest (an end mill's end, a
    drill's or chamfer mill's point)."""
    shapes = [(b, lambda p, b=b: _box_distance(b, p)) for b in boxes]
    shapes += [
        (c, lambda p, c=c: math.dist(c["centre"], p[:2]) - c["radius"]) for c in circles
    ]
    hits: dict[str, list[str]] = {}
    # shape name -> (count, least clearance, its line, its point)
    thin: dict[str, tuple[int, float, int, Point]] = {}
    for m in program.moves:
        previous = m.start
        for point in (m.start, *_xy_points(m)):
            for shape, distance in shapes:
                low, high = point[2], point[2]
                near = distance(point)
                if "z_bottom" in shape:
                    low, high = sorted((previous[2], point[2]))
                    near = min(near, distance(previous))
                if low < shape["z_top"] - _TOL_MM and high > shape.get("z_bottom", -math.inf) + _TOL_MM:
                    if near < radius - _TOL_MM:
                        hits.setdefault(shape["name"], []).append(_where(point))
                elif (
                    clearance > 0.0
                    and "z_bottom" not in shape
                    and is_jaw_shape(shape["name"])
                    and near < radius - _TOL_MM
                    and point[2] - shape["z_top"] < clearance - _TOL_MM
                ):
                    gap = point[2] - shape["z_top"]
                    count, least, line, at = thin.get(shape["name"], (0, math.inf, 0, point))
                    if gap < least:
                        least, line, at = gap, m.line, point
                    thin[shape["name"]] = (count + 1, least, line, at)
            previous = point
    findings: list[Finding] = []
    for shape, items in hits.items():
        what = f"cutter points into {shape}"
        _report(findings, program.name, what, items, "keep_out")
    for shape, (count, least, line, at) in thin.items():
        detail = (
            f"{count} cutter points over {shape}'s top under the {clearance:.3f} mm floor: "
            f"least {least:.3f} mm ({least / 25.4:.3f} in) at line {line} ({_where(at)})"
        )
        findings.append(Finding(program.name, "jaw_clearance", detail))
    return findings


def _move_distance(m: Move, point: Point) -> float:
    """XY distance from ``point`` to the path of move ``m``."""
    if m.centre is not None and m.plane == 17:
        a, b, radius, begin, sweep = m._arc()
        sense = -1.0 if m.motion is Motion.ARC_CW else 1.0
        dx, dy = point[0] - m.centre[a], point[1] - m.centre[b]
        if (sense * (math.atan2(dy, dx) - begin)) % (2 * math.pi) <= sweep:
            return abs(math.hypot(dx, dy) - radius)
        return min(math.dist(m.start[:2], point[:2]), math.dist(m.end[:2], point[:2]))
    return _element_distance({"start": m.start[:2], "end": m.end[:2]}, point)[0]


# The engagement simulation's height-field cell (mm): engagements are
# measured to within one cell.
ENGAGEMENT_CELL_MM = 0.05
# A feed move is cut in straight pieces no longer than this (arcs, ramps).
_PIECE_MM = 0.25
# A move's radial engagement is the stock it removes per unit of travel,
# averaged over each stretch of this length.
_RATE_MM = 0.5


@dataclass(frozen=True)
class Engagement:
    """What one feed move cut of the simulated stock: its index in
    ``program.moves``; its radial engagement (``radial``, mm): the stock
    area it removes per mm of the face it cuts (a line's travel; an arc's
    turn at the removed band's mean radius), the most over any ``_RATE_MM`` of
    it, which is the width of a steady side or face cut and the diameter of
    a slot (a plunge: the span of what it removed); the
    deepest stock it met below the stock's surface (``axial``, mm); and on
    which side of its travel that stock lay with a right-hand (M3) cutter,
    by its centroid: ``"climb"`` (the right), ``"conventional"`` (the
    left), ``"both"`` (on the centre line: a slot, a plunge) or ``""`` (it
    met none)."""

    index: int
    move: Move
    radial: float
    axial: float
    side: str


def engagements(
    program: Program,
    stock: Sequence[Sequence[float]],
    radius: float,
    cell: float = ENGAGEMENT_CELL_MM,
) -> list[Engagement]:
    """Cut the box ``stock`` ((x0, x1), (y0, y1), (z0, z1), its top z1) with a
    flat end mill of ``radius``, every move in order (rapids too, so the
    stock stays true), on a height field of ``cell`` squares, and return one
    :class:`Engagement` per feed move. Each removed cell is placed along the
    move where its leading edge reached it (a line's offset from its path,
    an arc's from its circle, G17 only)."""
    import numpy as np

    (x0, x1), (y0, y1), (_z0, top) = stock
    nx, ny = max(1, round((x1 - x0) / cell)), max(1, round((y1 - y0) / cell))
    xs = x0 + (np.arange(nx) + 0.5) * (x1 - x0) / nx
    ys = y0 + (np.arange(ny) + 0.5) * (y1 - y0) / ny
    height = np.full((nx, ny), float(top))
    area = (x1 - x0) / nx * (y1 - y0) / ny
    result: list[Engagement] = []
    for index, m in enumerate(program.moves):
        if m.start == m.end and m.centre is None:
            continue
        arc = m.centre is not None and m.plane == 17 and m.motion is not Motion.RAPID
        points = [m.start, *(_xy_points(m, _PIECE_MM) if arc else _pieces(m))]
        removed_x: list = []
        removed_y: list = []
        axial = 0.0
        for a, b in zip(points, points[1:]):
            z = min(a[2], b[2])
            if z >= top - _TOL_MM:
                continue
            i = np.nonzero((xs >= min(a[0], b[0]) - radius) & (xs <= max(a[0], b[0]) + radius))[0]
            j = np.nonzero((ys >= min(a[1], b[1]) - radius) & (ys <= max(a[1], b[1]) + radius))[0]
            if not len(i) or not len(j):
                continue
            gx, gy = np.meshgrid(xs[i], ys[j], indexing="ij")
            dx, dy = b[0] - a[0], b[1] - a[1]
            span = dx * dx + dy * dy
            t = np.clip(((gx - a[0]) * dx + (gy - a[1]) * dy) / span, 0.0, 1.0) if span > 0 else 0.0
            inside = (gx - a[0] - t * dx) ** 2 + (gy - a[1] - t * dy) ** 2 < radius * radius
            window = height[i[0]:i[-1] + 1, j[0]:j[-1] + 1]
            cut = inside & (window > z + _TOL_MM)
            if cut.any():
                axial = max(axial, float((window[cut] - z).max()))
                removed_x.append(gx[cut])
                removed_y.append(gy[cut])
                window[cut] = z
        if m.motion is Motion.RAPID:
            continue
        if not removed_x:
            result.append(Engagement(index, m, 0.0, 0.0, ""))
            continue
        rx, ry = np.concatenate(removed_x), np.concatenate(removed_y)
        if arc:
            a_, b_, r_arc, begin, sweep = m._arc()
            cx, cy = m.centre[a_], m.centre[b_]
            rho = np.hypot(rx - cx, ry - cy)
            outward = rho - r_arc
            sense = -1.0 if m.motion is Motion.ARC_CW else 1.0
            turned = (sense * (np.arctan2(ry - cy, rx - cx) - begin)) % (2 * math.pi)
            # Cells behind the start come out just under a full turn.
            turned = np.where(turned > (sweep + 2 * math.pi) / 2, turned - 2 * math.pi, turned)
            # The cutter centre first comes within the radius of a cell this
            # far (radians) before the cell's own angle.
            lead = np.arccos(np.clip((rho**2 + r_arc**2 - radius**2) / (2 * np.maximum(rho, 1e-9) * r_arc), -1.0, 1.0))
            reached = np.clip(turned - lead, 0.0, sweep) / sweep
            # Per mm along the removed band's mean radius: an annular band w
            # wide (a side cut, a slot) then reads w.
            contact = max(r_arc + float(outward.mean()), cell)
            n = max(1, math.ceil(r_arc * sweep / _RATE_MM - 1e-9))
            per_bin = contact * sweep / n
            # Moving clockwise, the left of travel is outward of the circle.
            offset = outward if m.motion is Motion.ARC_CW else -outward
        else:
            dx, dy = m.end[0] - m.start[0], m.end[1] - m.start[1]
            length = math.hypot(dx, dy)
            if length < _TOL_MM:  # a plunge: what it removed, its span along X
                span = float(rx.max() - rx.min()) + cell
                result.append(Engagement(index, m, span, axial, "both"))
                continue
            along = ((rx - m.start[0]) * dx + (ry - m.start[1]) * dy) / length
            offset = ((rx - m.start[0]) * -dy + (ry - m.start[1]) * dx) / length
            reached = np.clip(along - np.sqrt(np.clip(radius**2 - offset**2, 0.0, None)), 0.0, length) / length
            n = max(1, math.ceil(length / _RATE_MM - 1e-9))
            per_bin = length / n
        counts = np.bincount(np.minimum((reached * n).astype(int), n - 1), minlength=n)
        radial = float(counts.max() * area / per_bin)
        centroid = float(offset.mean())
        side = "climb" if centroid < -cell else ("conventional" if centroid > cell else "both")
        result.append(Engagement(index, m, radial, axial, side))
    return result


def _pieces(m: Move) -> list[tuple[float, ...]]:
    """A line's end, or for a ramp (XY and Z both changing) its points every
    ``_PIECE_MM``: each piece then cuts at its lower end's Z."""
    if _close(m.start[2], m.end[2]) or math.dist(m.start[:2], m.end[:2]) < _TOL_MM:
        return [m.end]
    n = max(1, math.ceil(m.length / _PIECE_MM))
    return [tuple(s + (e - s) * k / n for s, e in zip(m.start, m.end)) for k in range(1, n + 1)]


def check_engagement(
    program: Program,
    stock: Sequence[Sequence[float]],
    radius: float,
    max_radial: float,
    z: float | None = None,
    window: Sequence[Sequence[float]] | None = None,
    min_length: float = 0.0,
    cut: str | None = None,
    cell: float = ENGAGEMENT_CELL_MM,
) -> list[Finding]:
    """The passes a plan declares a radial width for meet no more stock than
    that: the program cuts the box ``stock`` (:func:`engagements`), and every
    feed move selected (both ends at ``z`` when given, both ends' XY inside
    ``window`` ((x0, x1), (y0, y1)) when given, at least ``min_length`` long)
    meets at most ``max_radial`` across its travel, to within one ``cell``;
    with ``cut`` (``"conventional"``/``"climb"``, declared as on
    :func:`check_side_passes`) every one that meets stock meets it the
    declared way: on the cutter's left for conventional under M3, on its
    right for climb (M4 the reverse); one that meets stock on both sides
    (a slot, a plunge) or with the spindle stopped fails. Stations alone
    cannot show this: what a pass meets depends on what every earlier move
    left, at the part's edges too."""
    if cut not in (None, *CUT_DIRECTIONS):
        raise ValueError(f"cut {cut!r} is not one of {CUT_DIRECTIONS}")
    (wx0, wx1), (wy0, wy1) = window if window is not None else ((-math.inf, math.inf),) * 2

    def selected(m: Move) -> bool:
        return (
            (z is None or (_close(m.start[2], z) and _close(m.end[2], z)))
            and all(wx0 - _TOL_MM <= p[0] <= wx1 + _TOL_MM and wy0 - _TOL_MM <= p[1] <= wy1 + _TOL_MM for p in (m.start, m.end))
            and m.length >= min_length
        )

    chosen = [e for e in engagements(program, stock, radius, cell) if selected(e.move)]
    if not chosen:
        return [Finding(program.name, "engagement", f"no feed move at Z {z} in {window} at least {min_length} long")]
    findings = []
    for e in chosen:
        m = e.move
        where = f"X{m.start[0]:.3f} Y{m.start[1]:.3f} -> X{m.end[0]:.3f} Y{m.end[1]:.3f} Z{m.end[2]:.3f}"
        if e.radial > max_radial + cell:
            findings.append(Finding(program.name, "engagement", f"{where} meets {e.radial:.3f} radial > {max_radial:.3f}"))
        if cut is None or not e.side:
            continue
        if m.spindle == 0:
            findings.append(Finding(program.name, "engagement", f"{where}: spindle stopped (no M3/M4 in force), declared {cut}"))
        elif e.side == "both":
            findings.append(Finding(program.name, "engagement", f"{where} meets stock on both sides, declared {cut}"))
        else:
            # engagements() reads the side for a clockwise (M3) cutter; M4 swaps it.
            ran = e.side if m.spindle > 0 else CUT_DIRECTIONS[1 - CUT_DIRECTIONS.index(e.side)]
            if ran != cut:
                findings.append(Finding(
                    program.name, "engagement",
                    f"{where} cuts {ran} under M{3 if m.spindle > 0 else 4}, declared {cut}",
                ))
    return findings
