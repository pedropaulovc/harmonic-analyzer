"""The as-machined report: the part the posted programs cut, against its CAD.

``cam_nc.py`` runs it after a recipe's programs posted and passed their
checks. From the recipe's own declaration (its ``as_machined(ctx, inputs)``,
plain data built from what the recipe and its plan already hold) it takes,
per part: the blank (a box in one setup frame, at the plan's nominal sawn
length and at both limits where the plan gives a band), the route (each
program in the order it runs and the setup frame it runs in; derived from
``PROGRAMS`` and the jobs' frames unless the recipe lists it) and every
tool's cutting shape (derived from the jobs: end mill, ball end, drill or
chamfer point, the recipe's ``CENTRE_DRILL``). ``_freecad_as_machined.py``
cuts every posted move that can reach the blank from it with OCC booleans in
headless FreeCAD and compares the result with the part's STEP.

It writes ``cad/out/nc/<stem>/as_machined.json``: per part and blank length
the volume, mass, centre-of-gravity offset, material left over and gouged
(each region's thickness), the material each program removed, every feed
pass that removed nothing and every rapid that removed material; and, when a
region is thicker than :data:`NOISE_MM`, ``as_machined.png`` with it drawn.
A recipe that declares nothing, or one this model cannot hold, is reported
``covered: false`` with its reason, never skipped in silence.

A recipe declares the differences it expects (``expected``, per part: hand
taps, a later lathe operation, an edge break filed at the bench, a cutter's
form, a size aimed inside its band), each a named box with its reason.
Every over-noise region is matched against them: the report counts the
unexplained ones (a clean recipe: 0) and names each expected difference
that no longer differs.

The report is not an output of the ``cam:<stem>`` task (no release ships
it, no target names it). Each recipe states its mode in
``AS_MACHINED_MODE``: :data:`MODE_REPORT` never fails the task;
:data:`MODE_GATE` fails it on an unexplained region, an expected difference
that is gone or a rapid that cuts. Turning a recipe to gating is that one
line. ``HARMONIC_AS_MACHINED=skip`` skips a report-mode recipe's report
(an inner loop); builds and releases leave it unset.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import _cam_programs
import _gcode

MODE_REPORT = "report"
MODE_GATE = "gate"
MODES = (MODE_REPORT, MODE_GATE)
# A difference thinner than this is noise: above the post's 0.001 mm
# rounding, FreeCAD's tessellation and the 0.0254 mm radial opening of the
# clamp's CB10 bore pass; below the tightest positional band in the plans
# (±0.102 mm). Measured on the column clamp trial (2026-11-25).
NOISE_MM = 0.075
SPEC_ENV = "HARMONIC_AS_MACHINED_SPEC"  # _freecad_as_machined.SPEC_ENV
RESULT_MARKER = "FREECAD_AS_MACHINED_RESULT "
REPORT_NAME = "as_machined.json"
PICTURE_NAME = "as_machined.png"
LOG_NAME = "as_machined.log"
OUTPUT_NAMES = (REPORT_NAME, PICTURE_NAME, LOG_NAME)
# "skip": no report for a report-mode recipe (a gating one always runs).
SKIP_ENV = "HARMONIC_AS_MACHINED"
# A region lies within an expected difference's box to this much (OCC's
# bound boxes carry the shapes' tolerances).
EXTENT_TOL_MM = 0.01
TIMEOUT_S = 1800
# freecadcmd processes at once: each part and blank length is one.
PARALLEL = 4
# A program of more moves is not cut move by move (one move's boolean costs
# more as the part grows: ms_stick's 540 numeral strokes take 300 s so, its
# 2400 graduation strokes ran past the 30 min timeout) but as one union of
# its moves (_freecad_as_machined). Its passes and rapids are then measured
# against the part before and after it. Every milling program is under it.
MOVE_CAP = 400
# The tool's envelope reaches this far above the blank's top in each setup:
# clear of the top face (no coincident faces in the booleans), and no
# farther, since nothing above the blank is cut. A V-bit's cone is as wide
# as it is tall: at 5 mm, ms_stick's 0.5 mm deep numeral strokes swept
# cones 3 mm across and their union ran past the 30 min timeout.
CLEAR_MM = 0.5
# A ramp is cut as flat pieces at their lower end, each dropping at most this.
RAMP_DZ_MM = 0.02
# An arc outside the XY plane is cut as chords of at most this angle.
ARC_STEP_DEG = 2.0
# A feed pass removing less than this removed nothing; a rapid removing
# more than this cut.
AIR_MM3 = 1e-3
RAPID_CUT_MM3 = 1e-3
BALL_STEPS = 12
# g/cm3 by the plan's ``milling_material`` key.
DENSITY_G_CM3 = {
    "aluminum_6061": 2.70,
    "brass": 8.50,
    "steel_1018": 7.87,
    "steel_o1": 7.81,
}
_AXES = {"x": 0, "y": 1, "z": 2}


class NotCovered(Exception):
    """The recipe's programs cannot be simulated: the reason."""


@dataclass(frozen=True)
class Frame:
    origin: tuple[float, float, float]
    axes: tuple[tuple[float, float, float], ...]  # rows: the setup's X, Y, Z in model coordinates

    def to_setup(self, p):
        return tuple(sum(self.axes[k][i] * (p[i] - self.origin[i]) for i in range(3)) for k in range(3))

    def to_model(self, q):
        return tuple(self.origin[i] + sum(self.axes[k][i] * q[k] for k in range(3)) for i in range(3))


@dataclass(frozen=True)
class Setup:
    program: str
    frame_key: str | None  # None: a program of manual sections only (nothing cut)
    frame: Frame | None
    entry_tool: int | None  # the tool loaded before the program's first M6


@dataclass(frozen=True)
class Expected:
    """A difference the recipe expects (hand work, a later lathe operation,
    an edge break, a cutter's form, a size aimed inside its band): every
    over-noise region of ``kind`` within the model-space box ``within`` (and
    no deeper than ``max_mm``) is explained by it. With an aim, the region
    is the aimed size against the CAD's: it must be ``|aim - cad|`` deep,
    within the noise line, and the aim is reported against its band."""
    name: str
    kind: str
    within: tuple[tuple[float, float], ...]
    reason: str
    max_mm: float | None
    variants: tuple[str, ...] | None  # None: every blank length
    aim: dict[str, Any] | None  # band_mm [lo, hi], cad_mm, aim_mm


@dataclass
class PartRoute:
    id: str
    step: str
    blanks: dict[str, list[dict[str, Any]]]  # variant -> model-space prisms (``base`` polygon, ``dir``), unioned
    lengths: dict[str, float] | None
    setups: list[Setup]
    density: float | None
    expected: list[Expected] = field(default_factory=list)


@dataclass
class Declaration:
    mode: str
    parts: list[PartRoute]
    profiles: dict[int, list[tuple[float, float]]]
    skipped: dict[str, str]
    uncut_tools: tuple[int, ...] = ()
    notes: list[str] = field(default_factory=list)


# --- declaration ---------------------------------------------------------


def frame(spec: dict[str, Any], what: str) -> Frame:
    origin = tuple(float(v) for v in spec["origin"])
    axes = tuple(tuple(float(v) for v in row) for row in spec["axes"])
    if len(origin) != 3 or len(axes) != 3 or any(len(row) != 3 for row in axes):
        raise NotCovered(f"frame {what} is not an origin and three axes")
    for i in range(3):
        for j in range(3):
            dot = sum(axes[i][k] * axes[j][k] for k in range(3))
            if abs(dot - (i == j)) > 1e-9:
                raise NotCovered(f"frame {what} is not orthonormal")
    (a, b, c), (d, e, f), (g, h, i) = axes
    if a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g) < 0:
        raise NotCovered(f"frame {what} is a mirror (det -1), not a rigid setup")
    return Frame(origin, axes)  # type: ignore[arg-type]


def tool_profile(job: dict[str, Any], centre_drill: dict[str, float] | None) -> list[tuple[float, float]]:
    """A job's tool as its (r, h) half-profile from the tip, its last radius
    carried up the shank."""
    r = float(job["dia"]) / 2
    if job["tool"] == "spot" and centre_drill is not None:
        pilot = centre_drill["pilot_mm"] / 2
        tip = math.radians(centre_drill.get("pilot_point_deg", 118.0) / 2)
        body = math.radians(centre_drill["point_deg"] / 2)
        length = centre_drill["pilot_length_mm"]
        if abs(r - centre_drill["body_mm"] / 2) > 1e-9:
            raise NotCovered(f"spot job dia {2 * r} is not CENTRE_DRILL body {centre_drill['body_mm']}")
        return [(0.0, 0.0), (pilot, pilot / math.tan(tip)), (pilot, length), (r, length + (r - pilot) / math.tan(body))]
    shape = job["shape"]
    if shape == "endmill":
        return [(r, 0.0)]
    if shape == "drill":
        angle = float(job.get("tip_angle", 180.0))
        return [(r, 0.0)] if angle >= 180.0 else [(0.0, 0.0), (r, r / math.tan(math.radians(angle / 2)))]
    if shape == "ballend":
        return [(r * math.sin(t), r * (1 - math.cos(t))) for t in (k * math.pi / 2 / BALL_STEPS for k in range(BALL_STEPS + 1))]
    raise NotCovered(f"tool {job['tool']} ({shape}) has no cutting profile; declare one under 'tools'")


def _op_frames(ctx: dict[str, Any]) -> dict[str, str]:
    return {op[0]: job.get("frame") for job in ctx["jobs"] for op in job["ops"]}


def _op_tools(ctx: dict[str, Any]) -> dict[str, int]:
    return {op[0]: ctx["numbers"][job["tool"]] for job in ctx["jobs"] for op in job["ops"]}


def _keys(ops) -> list[str]:
    return [key for item in ops for key in ([item] if isinstance(item, str) else item)]


def _find(tree: Any, key: str) -> Any:
    if isinstance(tree, dict):
        if key in tree:
            return tree[key]
        for value in tree.values():
            found = _find(value, key)
            if found is not None:
                return found
    return None


def _prism(fr: Frame, axis: int, polygon, lo: float, hi: float) -> dict[str, Any]:
    others = [i for i in range(3) if i != axis]

    def model(ab, h):
        q = [0.0, 0.0, 0.0]
        q[others[0]], q[others[1]], q[axis] = ab[0], ab[1], h
        return list(fr.to_model(q))

    base = [model(ab, lo) for ab in polygon]
    return {"base": base, "dir": [t - b for t, b in zip(model(polygon[0], hi), base[0])]}


def _section(spec: dict[str, Any]) -> tuple[int, list[tuple[float, ...]], float, float]:
    axis = _AXES[spec["axis"]]
    polygon = [tuple(float(v) for v in point) for point in spec["polygon"]]
    lo, hi = (float(v) for v in spec["span"])
    if len(polygon) < 3 or any(len(point) != 2 for point in polygon):
        raise NotCovered(f"blank prism polygon {spec['polygon']} is not three or more points")
    if lo >= hi:
        raise NotCovered(f"blank span {lo}..{hi} is not increasing")
    return axis, polygon, lo, hi


def blanks(spec: dict[str, Any], frames: dict[str, Frame]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, float] | None]:
    """The blank per variant (``nominal``, then ``min`` and ``max`` where its
    ``length`` gives a band) as model-space prisms, their union: each a
    ``base`` polygon and the ``dir`` vector it is extruded along. Declared
    in setup frame ``frame`` as a ``box`` (three spans), a ``prism`` (a
    bar's section: ``polygon`` in the frame's other two axes in increasing
    order, axis z -> (x, y), x -> (y, z), y -> (x, z), along ``axis`` over
    ``span``), or a list of prisms (a shape turned before it is milled, e.g.
    a hex bar and the spigot turned on its end; no length band). ``length``
    names the frame ``axis`` the sawn length runs along (a prism's own
    axis), the face that stays put (``keep``: the face that setup touches
    off) and the lengths ``mm`` by variant."""
    if spec["frame"] not in frames:
        raise NotCovered(f"blank frame {spec['frame']!r} is no frame of the recipe")
    fr = frames[spec["frame"]]
    if isinstance(spec.get("prism"), list):
        if "length" in spec:
            raise NotCovered("a blank of several prisms takes no length band")
        return {"nominal": [_prism(fr, *_section(p)) for p in spec["prism"]]}, None
    if "prism" in spec:
        axis, polygon, lo, hi = _section(spec["prism"])
        if "length" in spec and _AXES[spec["length"]["axis"]] != axis:
            raise NotCovered("a prism blank's length runs along its own axis")
    elif "box" in spec:
        box = [tuple(float(v) for v in pair) for pair in spec["box"]]
        if len(box) != 3 or any(a >= b for a, b in box):
            raise NotCovered(f"blank box {spec['box']} is not three increasing spans")
        axis = _AXES[spec["length"]["axis"]] if "length" in spec else 2
        (a0, a1), (b0, b1) = (box[i] for i in range(3) if i != axis)
        polygon, (lo, hi) = [(a0, b0), (a1, b0), (a1, b1), (a0, b1)], box[axis]
    else:
        raise NotCovered("the blank is neither a box nor a prism")
    spans = {"nominal": (lo, hi)}
    lengths = None
    if "length" in spec:
        keep, lengths = spec["length"]["keep"], dict(spec["length"]["mm"])
        if keep not in ("min", "max") or "nominal" not in lengths:
            raise NotCovered(f"blank length {spec['length']} needs keep min|max and a nominal")
        spans = {name: (lo, lo + length) if keep == "min" else (hi - length, hi) for name, length in lengths.items()}
    return {name: [_prism(fr, axis, polygon, start, end)] for name, (start, end) in spans.items()}, lengths


def blank_corners(blank: list[dict[str, Any]]) -> list[tuple[float, ...]]:
    return [tuple(c) for prism in blank for p in prism["base"] for c in (p, [a + d for a, d in zip(p, prism["dir"])])]


def expected(specs: list[dict[str, Any]], frames: dict[str, Frame], variants: list[str]) -> list[Expected]:
    """A part's ``expected`` differences, checked: each a ``name``, a
    ``kind`` (left or gouge), a ``reason``, the box ``within`` it lies (three
    spans in model coordinates, or in setup ``frame``: its corners' model
    bound box), and optionally ``max_mm``, ``variants`` (blank lengths it
    applies to) and ``aim`` (``band_mm`` [lo, hi], ``cad_mm``, ``aim_mm``)."""
    out, names = [], set()
    for spec in specs:
        name = spec.get("name")
        if not name or name in names:
            raise NotCovered(f"expected difference name {name!r} is missing or repeated")
        names.add(name)
        if spec.get("kind") not in ("left", "gouge"):
            raise NotCovered(f"expected {name!r} kind {spec.get('kind')!r} is not left or gouge")
        if not str(spec.get("reason", "")).strip():
            raise NotCovered(f"expected {name!r} gives no reason")
        box = [tuple(float(v) for v in pair) for pair in spec["within"]]
        if len(box) != 3 or any(len(pair) != 2 or pair[0] >= pair[1] for pair in box):
            raise NotCovered(f"expected {name!r} within {spec['within']} is not three increasing spans")
        if "frame" in spec:
            if spec["frame"] not in frames:
                raise NotCovered(f"expected {name!r} frame {spec['frame']!r} is no frame of the recipe")
            corners = [frames[spec["frame"]].to_model((x, y, z)) for x in box[0] for y in box[1] for z in box[2]]
            box = [(min(c[i] for c in corners), max(c[i] for c in corners)) for i in range(3)]
        applies = spec.get("variants")
        if applies is not None and (not applies or set(applies) - set(variants)):
            raise NotCovered(f"expected {name!r} variants {applies} are not blank lengths {variants}")
        aim = spec.get("aim")
        if aim is not None:
            aim = {"band_mm": [float(v) for v in aim["band_mm"]], "cad_mm": float(aim["cad_mm"]),
                   "aim_mm": float(aim["aim_mm"])}
            if len(aim["band_mm"]) != 2 or aim["band_mm"][0] >= aim["band_mm"][1]:
                raise NotCovered(f"expected {name!r} aim band {aim['band_mm']} is not [lo, hi]")
        max_mm = spec.get("max_mm")
        out.append(Expected(name, spec["kind"], tuple(box), str(spec["reason"]),  # type: ignore[arg-type]
                            None if max_mm is None else float(max_mm),
                            None if applies is None else tuple(applies), aim))
    return out


def declaration(recipe: Any, ctx: dict[str, Any], inputs: SimpleNamespace) -> Declaration:
    """The recipe's declaration, resolved and checked; :class:`NotCovered`
    with the reason when it declares none or this model cannot hold it."""
    if not hasattr(recipe, "as_machined"):
        reason = getattr(recipe, "AS_MACHINED_NOT_COVERED", None)
        raise NotCovered(reason or "the recipe declares no as_machined(ctx, inputs)")
    mode = getattr(recipe, "AS_MACHINED_MODE", None)
    if mode not in MODES:
        raise NotCovered(f"AS_MACHINED_MODE {mode!r} is not one of {MODES}")
    decl = recipe.as_machined(ctx, inputs)
    frames = {key: frame(spec, key) for key, spec in {**ctx.get("frames", {}), **decl.get("frames", {})}.items()}
    programs = {name: _keys(ops) for name, ops in recipe.PROGRAMS}
    skipped = dict(decl.get("skip", {}))
    if unknown := sorted(set(skipped) - set(programs)):
        raise NotCovered(f"skip names no program: {unknown}")
    op_frames, op_tools = _op_frames(ctx), _op_tools(ctx)
    centre_drill = getattr(recipe, "CENTRE_DRILL", None)
    profiles: dict[int, list[tuple[float, float]]] = {}
    for job in ctx["jobs"]:
        number = ctx["numbers"][job["tool"]]
        if number in decl.get("tools", {}):
            continue
        profile = tool_profile(job, centre_drill)
        if profiles.setdefault(number, profile) != profile:
            raise NotCovered(f"tool T{number} has two shapes")
    for number, profile in decl.get("tools", {}).items():
        profiles[int(number)] = [tuple(float(v) for v in point) for point in profile]  # type: ignore[misc]
    uncut = tuple(sorted(set(ctx["numbers"].values()) - set(profiles)))

    def derived(name: str) -> str | None:
        found = {op_frames[key] for key in programs[name] if key in op_frames}
        if None in found:
            raise NotCovered(f"{name}'s jobs name no frame; declare its route")
        if len(found) > 1:
            raise NotCovered(f"{name} runs in several frames {sorted(found)}; declare its route")
        return found.pop() if found else None

    def entry_tool(name: str) -> int | None:
        return next((op_tools[key] for key in programs[name] if key in op_tools), None)

    if set(decl["parts"]) != set(inputs.steps):
        raise NotCovered(f"declares parts {sorted(decl['parts'])}, the recipe posts for {sorted(inputs.steps)}")
    parts, routed = [], set()
    for part_id, spec in decl["parts"].items():
        if "route" in spec:
            route = [(name, key) for name, key in spec["route"]]
        else:
            route = [(name, derived(name)) for name in programs if name not in skipped]
        setups = []
        for name, key in route:
            if name not in programs:
                raise NotCovered(f"part {part_id!r} route names no program {name!r}")
            if key is not None and key not in frames:
                raise NotCovered(f"{name} frame {key!r} is no frame of the recipe")
            setups.append(Setup(name, key, frames[key] if key is not None else None, entry_tool(name)))
            routed.add(name)
        part_blanks, lengths = blanks(spec["blank"], frames)
        material = _find(inputs.plan.get(part_id, inputs.plan) if part_id else inputs.plan, "milling_material")
        parts.append(PartRoute(part_id, str(inputs.steps[part_id]), part_blanks, lengths, setups, DENSITY_G_CM3.get(material),
                               expected(spec.get("expected", []), frames, list(part_blanks))))
    if missing := sorted(set(programs) - routed - set(skipped)):
        raise NotCovered(f"programs neither routed nor skipped: {missing}")
    return Declaration(mode, parts, profiles, skipped, uncut, list(decl.get("notes", [])))


# --- moves ---------------------------------------------------------------


def _lower(a, b):
    return min(a[2], b[2])


def pieces(move: _gcode.Move, top: float) -> list[dict[str, Any]]:
    """The flat pieces a move's tool sweeps below the blank's ``top``, in
    setup coordinates: a G17 arc at its UPPER Z (a helix turn never cuts
    below its path; the next turn or the flat bottom turns take what it
    leaves, and a helix that ends without one leaves its floor up to one
    turn's drop, as a helical floor does), a plunge standing at its lowest
    point, a flat line, a ramp in pieces each at its lower end and dropping
    at most :data:`RAMP_DZ_MM`; an arc in another plane, or a G17 helix
    from at or above ``top``, as chords. Pieces at or above ``top`` cut
    nothing and are dropped; nothing for a move wholly there, or of no
    length."""
    if min(move.start[2], move.end[2], *(p[2] for p in move.extremes())) >= top:
        return []
    if move.centre is not None and move.plane == 17 and max(move.start[2], move.end[2]) < top:
        _a, _b, radius, begin, sweep = move._arc()
        sense = -1.0 if move.motion is _gcode.Motion.ARC_CW else 1.0
        return [{"kind": "arc", "c": [move.centre[0], move.centre[1]], "r": radius, "a0": begin,
                 "sweep": sense * sweep, "z": max(move.start[2], move.end[2])}]
    if move.centre is not None:
        a, b, radius, begin, sweep = move._arc()
        sense = -1.0 if move.motion is _gcode.Motion.ARC_CW else 1.0
        n = max(1, math.ceil(math.degrees(sweep) / ARC_STEP_DEG))
        h = 3 - a - b
        points = []
        for k in range(n + 1):
            t = begin + sense * sweep * k / n
            p = [0.0, 0.0, 0.0]
            p[a] = move.centre[a] + radius * math.cos(t)
            p[b] = move.centre[b] + radius * math.sin(t)
            p[h] = move.start[h] + (move.end[h] - move.start[h]) * k / n
            points.append(tuple(p))
    else:
        points = [move.start, move.end]
    out: list[dict[str, Any] | None] = []
    for s, e in zip(points, points[1:]):
        if math.dist(s[:2], e[:2]) < 1e-9:
            if abs(s[2] - e[2]) > 1e-9:
                out.append({"kind": "stand", "x": s[0], "y": s[1], "z": _lower(s, e)} if _lower(s, e) < top else None)
            continue
        # Less a hair, so a 0.1 mm drop is five 0.02 pieces, not six.
        n = max(1, math.ceil(abs(e[2] - s[2]) / RAMP_DZ_MM - 1e-9))
        sub = [tuple(s[i] + (e[i] - s[i]) * k / n for i in range(3)) for k in range(n + 1)]
        out += [{"kind": "seg", "a": [p[0], p[1]], "b": [q[0], q[1]], "z": _lower(p, q), "caps": [False, False]}
                if _lower(p, q) < top else None for p, q in zip(sub, sub[1:])]
    # The tool standing at each end of a chain of pieces (a run not broken
    # by one dropped above ``top``); a cap between two pieces is inside the
    # pieces either side of it (to within one piece's drop), and every cap is
    # a revolved solid in the one boolean.
    chains: list[list[dict[str, Any]]] = [[]]
    for piece in out:
        if piece is None:
            chains.append([])
        elif piece["kind"] == "seg":
            chains[-1].append(piece)
    for segs in chains:
        if segs:
            segs[0]["caps"][0] = segs[-1]["caps"][1] = True
    return [piece for piece in out if piece is not None]


def move_tools(program: _gcode.Program, entry_tool: int | None) -> list[int | None]:
    """The tool each move runs with: the last ``M6`` before it, else the
    tool the program starts on."""
    changes = sorted(program.tool_changes, key=lambda s: s.moves_before)
    tools, tool, k = [], entry_tool, 0
    for index in range(len(program.moves)):
        while k < len(changes) and changes[k].moves_before <= index:
            tool, k = changes[k].tool, k + 1
        tools.append(tool)
    return tools


def is_pass(move: _gcode.Move, profile: list[tuple[float, float]]) -> bool:
    """A feed move at one Z at least its tool's diameter long."""
    return (move.motion is not _gcode.Motion.RAPID and abs(move.start[2] - move.end[2]) < 1e-6
            and move.length >= 2 * max(r for r, _h in profile))


def drop_stood(found: list[dict[str, Any]], tool: int, last: tuple | None) -> tuple[list[dict[str, Any]], tuple | None]:
    """Drop what the tool already cut standing where the program's previous
    piece left it (the same tool, point and Z): a line's start cap, and a
    retract's standing (a rise stands at its lowest point, its start). The
    removal is unchanged; ms_stick's numerals: the strokes' coincident caps
    doubled the booleans' time, and its 707 retracts out of the strokes
    cost a boolean each. Also where this move leaves the tool."""
    kept = []
    for piece in found:
        if piece["kind"] == "seg":
            if piece["caps"][0] and last == (tool, *piece["a"], piece["z"]):
                piece["caps"][0] = False
            last = (tool, *piece["b"], piece["z"])
        elif piece["kind"] == "stand":
            here = (tool, piece["x"], piece["y"], piece["z"])
            if here == last:
                continue
            last = here
        else:
            last = None
        kept.append(piece)
    return kept, last


def program_moves(program: _gcode.Program, setup: Setup, top: float, profiles) -> tuple[list[dict], int]:
    """The program's moves FreeCAD cuts (those of a tool with a profile that
    can reach the blank), and how many moves of tools without a cutting
    shape (tap guides, probes) were left out. Rapids and passes are marked
    ``probe``: what a program too long to cut move by move still measures."""
    spec, uncut, last = [], 0, None
    for index, (move, tool) in enumerate(zip(program.moves, move_tools(program, setup.entry_tool))):
        if move.start == move.end and move.centre is None:
            continue
        if tool not in profiles:
            uncut, last = uncut + 1, None
            continue
        found, last = drop_stood(pieces(move, top), tool, last)
        if found:
            probe = "rapid" if move.motion is _gcode.Motion.RAPID else "pass" if is_pass(move, profiles[tool]) else None
            spec.append({"index": index, "tool": tool, "pieces": found, "probe": probe})
    return spec, uncut


# --- run -----------------------------------------------------------------


def build_spec(decl: Declaration, nc_dir: Path, mesh_dir: Path) -> tuple[dict[str, Any], dict]:
    """The FreeCAD spec, and per (part, variant, program) the moves sent."""
    kept: dict = {}
    parts = []
    programs = {setup.program: _gcode.read_program(nc_dir / f"{setup.program}.nc")
                for part in decl.parts for setup in part.setups}
    for part in decl.parts:
        variants = []
        for name, blank in part.blanks.items():
            corners = blank_corners(blank)
            out = []
            for setup in part.setups:
                if setup.frame is None:
                    continue
                top = max(setup.frame.to_setup(c)[2] for c in corners)
                moves, uncut = program_moves(programs[setup.program], setup, top, decl.profiles)
                kept[(part.id, name, setup.program)] = ([m["index"] for m in moves], uncut, programs[setup.program], setup)
                out.append({"name": setup.program, "origin": list(setup.frame.origin),
                            "axes": [list(row) for row in setup.frame.axes], "top": top + CLEAR_MM, "moves": moves})
            variants.append({"name": name, "blank": blank, "programs": out})
        parts.append({"id": part.id, "step": part.step, "variants": variants,
                      "profiles": {str(n): [list(p) for p in prof] for n, prof in decl.profiles.items()}})
    return {"marker": RESULT_MARKER, "noise_mm": NOISE_MM, "move_cap": MOVE_CAP, "mesh_dir": str(mesh_dir), "parts": parts}, kept


def _run_unit(spec: dict[str, Any], freecadcmd: Path, work: Path, tag: str) -> tuple[dict[str, Any] | None, str, str | None]:
    """One freecadcmd: its result, its console output and what went wrong
    (None when nothing did), so the caller logs the output either way."""
    path = work / f"spec-{tag}.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    try:
        completed = subprocess.run(
            [str(freecadcmd), str(_cam_programs.AS_MACHINED_RUNTIME_PATH)],
            env={**os.environ, SPEC_ENV: str(path.resolve())},
            cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=TIMEOUT_S, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = "".join(s if isinstance(s, str) else s.decode("utf-8", "replace") for s in (exc.stdout, exc.stderr) if s)
        return None, output, f"FreeCAD as-machined for {tag} ran past {TIMEOUT_S} s"
    output = completed.stdout + completed.stderr
    lines = [line for line in output.splitlines() if line.startswith(RESULT_MARKER)]
    if len(lines) != 1:
        return None, output, f"FreeCAD printed {len(lines)} as-machined result lines for {tag}: {output[-1500:]!r}"
    result = json.loads(lines[0].removeprefix(RESULT_MARKER))
    if "error" in result:
        return None, output, f"FreeCAD as-machined failed for {tag}:\n{result['error']}"
    return result, output, None


def run_freecad(spec: dict[str, Any], freecadcmd: Path, work: Path, log: Path) -> dict[str, Any]:
    """One freecadcmd per part and blank length, :data:`PARALLEL` at a time
    (each cuts its own blank from scratch); their results merged in order.
    Every console output goes to ``log``, before a failed unit raises."""
    units = [
        (i, {**spec, "parts": [{**part, "variants": [variant]}]}, f"{part['id'] or 'part'}-{variant['name']}")
        for i, part in enumerate(spec["parts"]) for variant in part["variants"]
    ]
    with ThreadPoolExecutor(max_workers=min(PARALLEL, len(units))) as pool:
        done = list(pool.map(lambda unit: _run_unit(unit[1], freecadcmd, work, unit[2]), units))
    log.write_text("\n".join(f"===== {tag}\n{output}" for (_i, _s, tag), (_r, output, _e) in zip(units, done)), encoding="utf-8")
    if errors := [error for _r, _o, error in done if error is not None]:
        raise RuntimeError("\n".join(errors))
    parts: list[dict[str, Any]] = []
    for (i, _spec, _tag), (result, _output, _error) in zip(units, done):
        found = result["parts"][0]
        if i == len(parts):
            parts.append({**found, "variants": []})
        parts[i]["variants"] += found["variants"]
    return {"freecad_version": done[0][0]["freecad_version"], "parts": parts}


def passes(program: _gcode.Program, entry_tool: int | None, sent: list[int], removed: list[float | None],
           profiles: dict[int, list[tuple[float, float]]]) -> tuple[list[dict], list[dict]]:
    """Passes (:func:`is_pass`) that removed nothing (one wholly above the
    blank was not cut at all) and rapids that removed material. A move FreeCAD
    did not measure (``None``: a program cut in one boolean) is neither."""
    by_index = dict(zip(sent, removed))
    air, rapid_cuts = [], []
    for index, (move, tool) in enumerate(zip(program.moves, move_tools(program, entry_tool))):
        if tool not in profiles:
            continue
        gone = by_index.get(index, 0.0)
        if gone is None:
            continue
        if move.motion is _gcode.Motion.RAPID:
            if gone > RAPID_CUT_MM3:
                rapid_cuts.append({"move": index, "tool": tool, "from": list(move.start), "to": list(move.end),
                                   "removed_mm3": gone})
        elif is_pass(move, profiles[tool]) and gone < AIR_MM3:
            air.append({"move": index, "tool": tool, "z_mm": move.start[2], "length_mm": move.length,
                        "minutes": move.length / move.feed if move.feed else None,
                        "above_blank": index not in by_index})
    return air, rapid_cuts


def _norm(v):
    return math.sqrt(sum(x * x for x in v))


def _inside(extent, box) -> bool:
    return all(lo - EXTENT_TOL_MM <= a and b <= hi + EXTENT_TOL_MM for (a, b), (lo, hi) in zip(extent, box))


def explain(variant: str, over: list[dict[str, Any]], unmeasured: dict[str, list[dict[str, Any]]],
            expects: list[Expected]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Mark every over-noise region with the expected difference that
    explains it (``expected``: its name, or None), and match the regions too
    many to measure (their depth unknown) by their extent alone. Returns the
    unexplained regions, and per expected difference of this blank length
    the regions it explained (``stale`` when none: the difference it
    declares is gone) and, for an aim, the aim against its band."""
    applicable = [e for e in expects if e.variants is None or variant in e.variants]
    count = {e.name: 0 for e in applicable}
    deepest = {e.name: 0.0 for e in applicable}

    def match(kind: str, region: dict[str, Any], depth: float | None) -> Expected | None:
        for e in applicable:
            if e.kind != kind or not _inside(region["extent_mm"], e.within):
                continue
            if depth is not None and e.max_mm is not None and depth > e.max_mm:
                continue
            if depth is not None and e.aim is not None and abs(depth - abs(e.aim["aim_mm"] - e.aim["cad_mm"])) > NOISE_MM:
                continue
            return e
        return None

    unexplained = []
    for region in over:
        e = match(region["kind"], region, region["thickness_mm"])
        region["expected"] = e.name if e else None
        if e is None:
            unexplained.append(region)
        else:
            count[e.name] += 1
            deepest[e.name] = max(deepest[e.name], region["thickness_mm"])
    for kind, regions in unmeasured.items():
        for region in regions:
            e = match(kind, region, None)
            if e is None:
                unexplained.append({"kind": kind, "thickness_mm": None, "at_mm": None, "expected": None, **region})
            else:
                count[e.name] += 1
    rows = []
    for e in applicable:
        row: dict[str, Any] = {"name": e.name, "kind": e.kind, "reason": e.reason, "regions": count[e.name],
                               "deepest_mm": deepest[e.name], "stale": count[e.name] == 0}
        if e.aim is not None:
            lo, hi = e.aim["band_mm"]
            row["aim"] = {**e.aim, "in_band": lo <= e.aim["aim_mm"] <= hi, "cad_in_band": lo <= e.aim["cad_mm"] <= hi}
        rows.append(row)
    return unexplained, rows


def summarize(decl: Declaration, result: dict[str, Any], kept: dict) -> dict[str, Any]:
    parts = {}
    for part, found in zip(decl.parts, result["parts"]):
        cad = found["cad"]
        variants = {}
        for variant in found["variants"]:
            am = variant["am"]
            programs, air, rapid_cuts = [], [], []
            for prog in variant["programs"]:
                sent, uncut, program, setup = kept[(part.id, variant["name"], prog["name"])]
                a, r = passes(program, setup.entry_tool, sent, prog["removed_mm3"], decl.profiles)
                air += [{"program": prog["name"], **p} for p in a]
                rapid_cuts += [{"program": prog["name"], **p} for p in r]
                programs.append({"program": prog["name"], "removed_mm3": prog["total_mm3"], "shed_mm3": prog["shed_mm3"],
                                 "accounting": prog["accounting"],
                                 "moves_cut": len(sent), "moves_of_uncut_tools": uncut,
                                 "air_passes": len(a), "air_pass_minutes": sum(p["minutes"] or 0.0 for p in a),
                                 "seconds": prog["seconds"]})
            over = [{"kind": kind, **r} for kind in ("left", "gouge") for r in variant[kind] if r["thickness_mm"] > NOISE_MM]
            unmeasured = {kind: variant[f"{kind}_rest"].pop("unmeasured") for kind in ("left", "gouge")}
            unexplained, expected_rows = explain(variant["name"], over, unmeasured, part.expected)
            density = part.density
            variants[variant["name"]] = {
                "blank_length_mm": (part.lengths or {}).get(variant["name"]),
                "blank_mm3": variant["blank_mm3"],
                "volume_mm3": {"cad": cad["volume_mm3"], "as_machined": am["volume_mm3"],
                               "difference": am["volume_mm3"] - cad["volume_mm3"]},
                "mass_g": None if density is None else {"cad": cad["volume_mm3"] * density / 1000,
                                                        "as_machined": am["volume_mm3"] * density / 1000},
                "cog_mm": {"cad": cad["cog_mm"], "as_machined": am["cog_mm"]},
                "cog_offset_mm": _norm([a - c for a, c in zip(am["cog_mm"], cad["cog_mm"])]),
                "bbox_mm": {"cad": cad["bbox_mm"], "as_machined": am["bbox_mm"]},
                "as_machined_solids": am["solids"],
                "max_left_mm": max((r["thickness_mm"] for r in variant["left"]), default=0.0),
                "max_gouge_mm": max((r["thickness_mm"] for r in variant["gouge"]), default=0.0),
                "over_noise": over,
                "unexplained": unexplained,
                "expected": expected_rows,
                "left": variant["left"], "left_rest": variant["left_rest"],
                "gouge": variant["gouge"], "gouge_rest": variant["gouge_rest"],
                "programs": programs,
                "air_passes": air,
                "rapid_cuts": rapid_cuts,
                "seconds": variant["seconds"],
                "_meshes": variant["meshes"],
            }
        parts[part.id] = {"step": Path(part.step).name, "density_g_cm3": part.density,
                          "route": [[s.program, s.frame_key] for s in part.setups], "variants": variants}
    return parts


def picture(parts: dict[str, Any], path: Path) -> bool:
    """Every part and blank length with a region over the noise line: three
    orthographic views of the CAD (grey), the material left (red) and the
    gouges (blue). False when there is none."""
    rows = [(pid, name, v) for pid, part in parts.items() for name, v in part["variants"].items() if v["_meshes"]]
    if not rows:
        return False
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    views = (("top (X-Y)", 0, 1), ("front (X-Z)", 0, 2), ("side (Y-Z)", 1, 2))
    fig, axes = plt.subplots(len(rows), 3, figsize=(15, 5 * len(rows)), squeeze=False)
    for row, (pid, name, v) in enumerate(rows):
        meshes = json.loads(Path(v["_meshes"]).read_text(encoding="utf-8"))
        for col, (title, i, j) in enumerate(views):
            ax = axes[row][col]
            ax.add_collection(PolyCollection([[(p[i], p[j]) for p in t] for t in meshes["cad"]],
                                             facecolor="0.85", edgecolor="none"))
            for kind, colour in (("left", "red"), ("gouge", "blue")):
                for region in meshes[kind]:
                    ax.add_collection(PolyCollection([[(p[i], p[j]) for p in t] for t in region],
                                                     facecolor=colour, edgecolor=colour, linewidth=0.3, alpha=0.8))
            ax.autoscale_view()
            ax.set_aspect("equal")
            ax.set_title(f"{pid or 'part'} {name}: {title}  left {v['max_left_mm']:.3f} mm (red), "
                         f"gouge {v['max_gouge_mm']:.3f} mm (blue), {len(v['unexplained'])} unexplained", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return True


def report(stem: str, recipe: Any, ctx: dict[str, Any], inputs: SimpleNamespace, nc_dir: Path,
           freecadcmd: Callable[[], Path]) -> dict[str, Any]:
    """Run the report and write it beside the programs. Returns the report."""
    started = time.perf_counter()
    for name in OUTPUT_NAMES:
        (nc_dir / name).unlink(missing_ok=True)
    out: dict[str, Any] = {"stem": stem, "noise_mm": NOISE_MM}
    try:
        decl = declaration(recipe, ctx, inputs)
    except NotCovered as exc:
        out.update(covered=False, reason=str(exc), mode=getattr(recipe, "AS_MACHINED_MODE", None))
    except Exception as exc:  # noqa: BLE001 -- a declaration that raises is the recipe's error, reported
        out.update(covered=True, mode=getattr(recipe, "AS_MACHINED_MODE", None),
                   error=f"declaration: {type(exc).__name__}: {exc}")
    else:
        out.update(covered=True, mode=decl.mode, skipped=decl.skipped, uncut_tools=list(decl.uncut_tools), notes=decl.notes)
        try:
            with tempfile.TemporaryDirectory(prefix="as-machined-") as work:
                spec, kept = build_spec(decl, nc_dir, Path(work))
                result = run_freecad(spec, freecadcmd(), Path(work), nc_dir / LOG_NAME)
                out["freecad_version"] = result["freecad_version"]
                out["parts"] = summarize(decl, result, kept)
                out["picture"] = PICTURE_NAME if picture(out["parts"], nc_dir / PICTURE_NAME) else None
            for part in out["parts"].values():
                for v in part["variants"].values():
                    v.pop("_meshes")
        except Exception as exc:  # noqa: BLE001 -- the report records its own failure
            out["error"] = f"{type(exc).__name__}: {exc}"
            out.pop("parts", None)
    out["seconds"] = time.perf_counter() - started
    (nc_dir / REPORT_NAME).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return out


def headline(out: dict[str, Any]) -> dict[str, Any]:
    """The report's numbers as flat span attributes: the worst over every
    part and blank length."""
    attrs: dict[str, Any] = {"as_machined.covered": out["covered"], "as_machined.seconds": out["seconds"]}
    if not out["covered"]:
        attrs["as_machined.reason"] = out["reason"]
        return attrs
    attrs["as_machined.mode"] = out["mode"]
    if "error" in out:
        attrs["as_machined.error"] = out["error"]
        return attrs
    variants = [v for part in out["parts"].values() for v in part["variants"].values()]
    attrs.update({
        "as_machined.max_left_mm": max(v["max_left_mm"] for v in variants),
        "as_machined.max_gouge_mm": max(v["max_gouge_mm"] for v in variants),
        "as_machined.cog_offset_mm": max(v["cog_offset_mm"] for v in variants),
        "as_machined.volume_difference_mm3": max((v["volume_mm3"]["difference"] for v in variants), key=abs),
        "as_machined.over_noise": sum(len(v["over_noise"]) for v in variants),
        "as_machined.unexplained": sum(len(v["unexplained"]) for v in variants),
        "as_machined.stale_expected": sum(row["stale"] for v in variants for row in v["expected"]),
        "as_machined.air_passes": sum(len(v["air_passes"]) for v in variants),
        "as_machined.rapid_cuts": sum(len(v["rapid_cuts"]) for v in variants),
    })
    return attrs


def failures(out: dict[str, Any]) -> list[str]:
    """What a gating recipe fails on, by part and blank length: a
    declaration that does not cover it, every region over the noise line
    its recipe does not expect (and every region too many to measure
    outside what it expects), every expected difference that is gone, every
    aim outside its band, and every rapid that cut."""
    if not out["covered"]:
        return [f"{out['stem']}: not covered: {out['reason']}"] if out.get("mode") == MODE_GATE else []
    found = [f"{out['stem']}: the report failed: {out['error']}"] if "error" in out else []
    for pid, part in (out.get("parts") or {}).items():
        for name, v in part["variants"].items():
            where = f"{pid or out['stem']} {name}"
            for r in v["unexplained"]:
                depth = "unmeasured" if r["thickness_mm"] is None else f"{r['thickness_mm']:.3f} mm"
                found.append(f"{where}: unexplained {r['kind']} {depth} in {r['extent_mm']}")
            found += [f"{where}: expected {row['name']!r} ({row['kind']}) is gone" for row in v["expected"] if row["stale"]]
            found += [f"{where}: expected {row['name']!r} aims at {row['aim']['aim_mm']} outside its band {row['aim']['band_mm']}"
                      for row in v["expected"] if "aim" in row and not row["aim"]["in_band"]]
            found += [f"{where}: rapid {r['program']} move {r['move']} removed {r['removed_mm3']:.3f} mm3" for r in v["rapid_cuts"]]
    return found
