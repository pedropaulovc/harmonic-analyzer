"""FreeCAD CAM recipe for MHA-PN-01, the pen frame.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The frame's sizes
come from the feature export (its width, height and depth, the window and
the thumb-screw tap); the blank, the skims, face levels, the window's finish
stock, levels and run past, the spot, pecks and the parallels from
``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter diameters, speeds
and feeds from the shop (``shop/``). Every path is written here
(``rt.custom``): straight lines a recipe can state exactly. Typed here,
because neither record carries them: the #2 centre drill's catalogue
geometry (it sets the spot depth), the twist drill's 118° point, the plug
tap's chamfer (it sets how far the tap runs past the rail), the axial and
radial limits of the window's cuts (Harvey Tool's tables, cited in the
plan), the machine's Z top for the tap file's retract, the approach, safe
and clearance heights, the face overhang and the vise jaws' depth (keep-out
shapes only).

Route (plan text in ``plan.toml``): one 3/8 x 1-1/4 in C36000 blank about
1.70 long. Upright on a 1 in parallel pair, gripped on the bar's wide faces:
PF01 faces the top end, PF02 (turned over) the bottom end to the height. On
edge on the same pair: PF03 skims the left face, PF04 (turned over) faces
the right face to the width. Lying on the 1 in + 1/2 in parallel stacks
under the end rails, gripped on the ends: PF05 skims the back face, PF06
(turned over) faces the front face to the depth, roughs the window with a
1/8 in slot round its edge and finishes its walls and corners with the same
end mill (owner ruling 2026-11-23, tool audit Q9: the corners print R.065,
.060-.070; no 5/64 cutter). Upright, the bottom end up: PF07
spots and drills the #43 through the bottom rail into the window, PF08
brings the tap guide over it for tapping by hand.

Work frames (G54), each set in its setup:
- PF01/PF02: X0 Y0 the bar's axis, Z0 the faced top end (PF01) or the
  parallels' top (PF02); +Y toward the fixed jaw (the back face).
- PF03: X0 the bottom end, Y0 the fixed jaw (back face), Z0 the parallels.
- PF04: X0 the top end, Y0 the fixed jaw (back face), Z0 the parallels.
- PF05: X0 the left face, Y0 the fixed jaw (bottom end), Z0 the stacks.
- PF06: X0 the left face, Y0 the fixed jaw (top end), Z0 the stacks (the
  back face).
- PF07/PF08: X0 the left face (the part to -X), Y0 the fixed jaw (back
  face), Z0 the bottom end.

Faces are the drawing's: its front view looks at the model's +Z face, so
the model's front_face feature (Z0) is the drawing's back face, the face
the hole's .16 is measured from.

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, plunges into metal (each
window level) at the plan's plunge feed, real G0 above the stock. The hole
is tapped by hand (FluidNC cannot rigid-tap; owner, Pedro, 2026-11-17), the
T-handle wrench's centre hole on the spring point of the Fisher tap guide
in the 1/2 in R8 collet (owner, Pedro, 2026-11-21: "use
https://littlemachineshop.com/products/tap-guide-fisher?variant=45472915226805
on r8 0.5 collet"), spindle off, the operator jogging Z down to push the
point home. FluidNC, like Grbl, refuses jogs
while an M0 holds the program (FluidNC wiki, "Single Block Mode",
http://wiki.fluidnc.com/en/features/single_block_mode), so the tap stop is a
file of its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "pn_pen_frame"
COMMENT = "MHA-PN-01 pen frame"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("PF01_top_end", ("top_end",)),
    ("PF02_height", ("bottom_end",)),
    ("PF03_left_face", ("left_face",)),
    ("PF04_width", ("right_face",)),
    ("PF05_back_face", ("back_face",)),
    (
        "PF06_window",
        (("front_face",), ("window_rough", "window_finish")),
    ),
    ("PF07_tap_drill", (("tap_spot",), ("tap_drill",))),
    ("PF08_tap", ("tap",)),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held, and the tap file before its retract
# (the tap guide).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the tap, the saw and the files are not).
CAM_TOOLS = ("em-half", "em-eighth", "spot", "drill-43", "tap-guide")
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included: the shop record names
# the tool, not its geometry.
CENTRE_DRILL = {
    "pilot_mm": 5 / 64 * IN,
    "pilot_length_mm": 5 / 64 * IN,
    "body_mm": 3 / 16 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# A plug tap's chamfer, in threads: 3-5 (ASME B94.9); the longest is taken,
# so every thread in the rail is full once the point is this far past it.
PLUG_CHAMFER_THREADS = 5
# The window's cut limit the plan cites (Harvey Tool speeds and feeds
# tables, Brass row): the 1/8 in slot's axial depth at most .35 × its
# diameter (series 720xx, slotting). The finish runs the same end mill at
# the slot's levels and setting, its radial depth the finish stock on the
# walls and in the corners alike: a lighter cut than the slot before it.
SLOT_AXIAL_MAX = 0.35
# The finish turns each corner on an arc about the slot path's corner, of
# the finish stock's radius, as straight chords: each chord stands at most
# this far inside its arc (half the outline check's allowance).
CORNER_SAG_MAX_MM = 0.0025
# Each window plunge runs at half the cutter's chip load (the rocker strap
# plan's plunge rule).
PLUNGE_CHIP_FRACTION = 0.5
# A tap file's first motion: G53 G0 to machine Z0, the homed top. FluidNC
# sets an axis's machine position to its homing mpos_mm (default 0) after
# homing, and Z homes up (cad/config/shop-equipment/
# cnc.pm-30mv-controller: switches on all three axes); the owner (Pedro)
# confirmed it, answered in person 2026-11-21 (cnc rulings record): machine
# Z = 0 is the top of travel after homing.
MACHINE_Z_TOP_MM = 0.0
# Face passes start and finish with the cutter this far clear of the part's
# ends, so every plunge and stepover link is in the air beside it.
APPROACH_MM = 2.54
# Faces reach at least this far past the faces the jaws grip.
FACE_OVERHANG_MM = 0.5
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped face; the
# parallels' length (4 in, shop-equipment fixtures.parallels-lms-6745).
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 4 * IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# The window outline checks' allowance on the cutter centre's offset.
OUTLINE_TOL_MM = 0.005
_THREAD = re.compile(r"#?\d+(?:/\d+)?-(\d+) UN[CF]-[123]B")


def _plan_operations(plan: dict[str, Any]):
    for setup in plan["setups"]:
        yield from setup.get("operations", ())


def _op_with_cut(
    plan: dict[str, Any], name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    for op in _plan_operations(plan):
        for cut in op.get("milling_cuts", ()):
            if cut["name"] == name:
                return op, cut
    raise KeyError(f"plan has no milling cut {name!r}")


def _resolve(plan: dict[str, Any], value: Any, what: str) -> float:
    """A number, or a ``{{process.<parameter>}}`` binding read from [parameters]."""
    if isinstance(value, str):
        match = re.fullmatch(r"\{\{process\.(\w+)\}\}", value.strip())
        if not match:
            raise ValueError(
                f"{what} = {value!r}: only numbers and {{{{process.…}}}} bindings are read"
            )
        value = plan["parameters"][match.group(1)]
    return float(value)


def _cut(plan: dict[str, Any], name: str, key: str) -> float:
    """Field ``key`` of the plan's milling cut ``name``."""
    return _resolve(plan, _op_with_cut(plan, name)[1][key], f"'{name}' {key}")


def _setting(
    plan: dict[str, Any], shop: dict[str, Any], cut: str
) -> tuple[float, float]:
    """(rpm, mm/min) of the operation holding ``cut``: the shop setting it
    names (chip load × flutes × rpm, or its stated feed), or, with no
    setting, the rpm and feed the cut itself authors."""
    op, record_cut = _op_with_cut(plan, cut)
    if "settings" not in op:
        return _cut(plan, cut, "rpm"), _cut(plan, cut, "feed_mm_min")
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    if "chip_load_mm_per_tooth" in record:
        feed = record["chip_load_mm_per_tooth"] * record["flutes"] * rpm
    else:
        value, unit = record["feed"].split()
        if unit != "in/min":
            raise ValueError(f"setting {op['settings']!r}: feed unit {unit!r}")
        feed = float(value) * IN
    for key, expected in (("rpm", rpm), ("feed_mm_min", feed)):
        if key in record_cut and not math.isclose(
            _cut(plan, cut, key), expected, abs_tol=1e-3
        ):
            raise ValueError(
                f"'{cut}' {key} {_cut(plan, cut, key):g} is not its setting's {expected:g}"
            )
    return rpm, feed


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


def _levels(top: float, bottom: float, max_step: float) -> list[float]:
    """Equal step-down levels no deeper than ``max_step`` from ``top`` to
    ``bottom``, ``bottom`` last."""
    n = math.ceil((top - bottom) / max_step - 1e-9)
    return [top - (top - bottom) * (k + 1) / n for k in range(n - 1)] + [bottom]


def _r(value: float) -> float:
    """A coordinate as the post prints it (3 places)."""
    return round(value + 0.0, 3)


def _box(
    name: str, x: tuple[float, float], y: tuple[float, float], z_top: float
) -> dict[str, Any]:
    return {"name": name, "x": [x[0], x[1]], "y": [y[0], y[1]], "z_top": z_top}


def _agree(plan: dict[str, Any], key: str, value: float) -> None:
    """A plan parameter the recipe recomputes from the export and the shop."""
    stated = plan["parameters"][key]
    if not math.isclose(stated, value, abs_tol=PLAN_TOL_MM):
        raise ValueError(f"process.{key} {stated:g}, the recipe computes {value:.4f}")


def _spot_depth(dia: float) -> float:
    """Depth below the surface at which the #2 centre drill's 60° countersink
    reaches ``dia``; refused unless it is between the pilot and the body."""
    pilot, body = CENTRE_DRILL["pilot_mm"], CENTRE_DRILL["body_mm"]
    if not pilot < dia <= body:
        raise ValueError(
            f"spot Ø{dia:.3f} is not between the pilot Ø{pilot:.3f} and the body Ø{body:.3f}"
        )
    half = math.radians(CENTRE_DRILL["point_deg"] / 2)
    return CENTRE_DRILL["pilot_length_mm"] + (dia - pilot) / 2 / math.tan(half)


def _point(dia: float) -> float:
    """A twist drill's point length."""
    return dia / 2 / math.tan(math.radians(DRILL_POINT_DEG / 2))


def _frame(
    origin: list[float], y_axis: list[float], z_axis: list[float]
) -> dict[str, Any]:
    """A right-handed setup frame from its Y and Z model axes: X = Y × Z."""
    y, z = y_axis, z_axis
    x = [
        y[1] * z[2] - y[2] * z[1],
        y[2] * z[0] - y[0] * z[2],
        y[0] * z[1] - y[1] * z[0],
    ]
    return {"origin": origin, "axes": [x, y, z]}


def _to(frame: dict[str, Any], p: list[float]) -> list[float]:
    """Model point ``p`` in the setup frame."""
    d = [p[i] - frame["origin"][i] for i in range(3)]
    return [sum(axis[i] * d[i] for i in range(3)) for axis in frame["axes"]]


def _spot(xy: tuple[float, float], top: float, z: float, clear: float) -> list[str]:
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _pecked(
    xy: tuple[float, float], top: float, tip: float, peck: float, clear: float
) -> list[str]:
    """Drill from ``top`` to ``tip`` in pecks of ``peck``, each with a full
    retract to the R plane and a rapid back to just above the last peck.
    Moves to and from the hole run at ``clear``."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    depths = []
    depth = top
    while depth - peck > tip + 1e-6:
        depth -= peck
        depths.append(_r(depth))
    depths.append(_r(tip))
    lines = [f"G0 Z{clear:.3f}", f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}", f"G0 Z{r_plane:.3f}"]
    previous = None
    for z in depths:
        if previous is not None:
            lines += [f"G0 Z{r_plane:.3f}", f"G0 Z{_r(previous + PECK_REENTRY_MM):.3f}"]
        lines.append(f"G1 Z{z:.3f} F{{feed}}")
        previous = z
    return lines + [f"G0 Z{r_plane:.3f}", f"G0 Z{clear:.3f}"]


def _stations(y: tuple[float, float], radius: float, max_step: float) -> list[float]:
    """Zigzag pass stations across the face ``y`` (low, high), from its high
    side: each pass takes the same width, at most ``max_step``, and together
    the cutter reaches ``FACE_OVERHANG_MM`` past both edges."""
    span = y[1] - y[0] + FACE_OVERHANG_MM
    n = math.ceil(span / max_step - 1e-9)
    step = span / n
    if 2 * radius - step < FACE_OVERHANG_MM:
        raise ValueError(
            f"a {step:.3f} stepover leaves the first pass short of the edge"
        )
    first = y[1] + radius - step
    return [_r(first - k * step) for k in range(n)]


def _face(
    levels: list[float], top: float, x: tuple[float, float], ys: list[float]
) -> list[str]:
    """Zigzag faces at ``levels``: at each, one X pass per Y in ``ys``
    between the cutter-centre ends ``x``, alternating direction, starting at
    the low X end; every plunge, level change and stepover beside the part."""
    clear = _r(top + CLEAR_MM)
    x0, x1 = _r(x[0]), _r(x[1])
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{x0:.3f} Y{ys[0]:.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
    ]
    for z in levels:
        lines.append(f"G1 Z{_r(z):.3f} F{{feed}}")
        for k, y in enumerate(ys):
            if k:
                lines.append(f"G1 Y{y:.3f} F{{feed}}")
            lines.append(f"G1 X{x1 if k % 2 == 0 else x0:.3f} F{{feed}}")
        if len(ys) % 2:
            # Back to the low X side, beside the part, for the next level.
            lines.append(f"G1 X{x0:.3f} F{{feed}}")
        if z != levels[-1]:
            lines.append(f"G1 Y{ys[0]:.3f} F{{feed}}")
    return lines + [f"G0 Z{clear:.3f}"]


def _loop(
    x: tuple[float, float], y: tuple[float, float], top: float, levels: list[float]
) -> list[str]:
    """A cutter-centre rectangle ``x`` × ``y`` inside the window, clockwise
    seen from above (conventional inside it with a right-hand spindle), at
    each of ``levels``: a straight plunge at the plunge feed at the middle of
    its left side, then once round at the cutting feed."""
    clear = _r(top + CLEAR_MM)
    xa, xb = _r(x[0]), _r(x[1])
    ya, yb = _r(y[0]), _r(y[1])
    ym = _r((y[0] + y[1]) / 2)
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{xa:.3f} Y{ym:.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
    ]
    for z in levels:
        lines += [
            f"G1 Z{_r(z):.3f} F{{plunge}}",
            f"G1 Y{yb:.3f} F{{feed}}",
            f"G1 X{xb:.3f} F{{feed}}",
            f"G1 Y{ya:.3f} F{{feed}}",
            f"G1 X{xa:.3f} F{{feed}}",
            f"G1 Y{ym:.3f} F{{feed}}",
        ]
    return lines + [f"G0 Z{clear:.3f}"]


def _finish_loop(
    x: tuple[float, float],
    y: tuple[float, float],
    corner: float,
    turn: float,
    top: float,
    levels: list[float],
) -> list[str]:
    """The finish path inside the window's walls ``x`` × ``y``, clockwise
    seen from above: each wall ``corner`` - ``turn`` in from it, each corner
    an arc of radius ``turn`` about the point ``corner`` in from both walls
    (the slot path's corner), so the corners come out at radius ``corner``.
    Each arc runs as equal chords no more than ``CORNER_SAG_MAX_MM`` inside
    it. At each of ``levels`` a straight plunge at the plunge feed at the
    middle of the left wall's path, then once round at the cutting feed.
    Each coordinate goes onto the G-code's .001 mm grid away from the
    window's middle (under .001 mm toward its wall), so no rounding
    leaves the cutter centre farther than its offset from a wall."""
    (x0, x1), (y0, y1) = x, y
    clear = _r(top + CLEAR_MM)
    xm, ym = (x0 + x1) / 2, (y0 + y1) / 2

    def outward(value: float, middle: float) -> float:
        step = math.ceil if value > middle else math.floor
        return step(round(value * 1000, 6)) / 1000

    xa = outward(x0 + corner - turn, xm)
    chords = math.ceil((math.pi / 4) / math.acos(1 - CORNER_SAG_MAX_MM / turn) - 1e-9)
    # (arc centre, start angle in degrees), clockwise from the top-left.
    arcs = (
        ((x0 + corner, y1 - corner), 180.0),
        ((x1 - corner, y1 - corner), 90.0),
        ((x1 - corner, y0 + corner), 0.0),
        ((x0 + corner, y0 + corner), -90.0),
    )
    lap = []
    for (cx, cy), start in arcs:
        for k in range(chords + 1):
            a = math.radians(start - 90.0 * k / chords)
            px = outward(cx + turn * math.cos(a), xm)
            py = outward(cy + turn * math.sin(a), ym)
            lap.append(f"G1 X{px:.3f} Y{py:.3f} F{{feed}}")
    lap.append(f"G1 X{xa:.3f} Y{_r(ym):.3f} F{{feed}}")
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{xa:.3f} Y{_r(ym):.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
    ]
    for z in levels:
        lines += [f"G1 Z{_r(z):.3f} F{{plunge}}", *lap]
    return lines + [f"G0 Z{clear:.3f}"]


def _outline(
    x: tuple[float, float], y: tuple[float, float], corner: float
) -> list[dict[str, Any]]:
    """The window's walls ``x`` × ``y`` with corners of radius ``corner``,
    clockwise from the middle of the left wall, as outline elements."""
    (x0, x1), (y0, y1), c = x, y, corner
    ym = (y0 + y1) / 2
    tol = OUTLINE_TOL_MM
    return [
        {"name": "left wall", "start": [x0, ym], "end": [x0, y1 - c], "tol": tol},
        {
            "name": "corner",
            "start": [x0, y1 - c],
            "end": [x0 + c, y1],
            "centre": [x0 + c, y1 - c],
            "tol": tol,
        },
        {"name": "far wall", "start": [x0 + c, y1], "end": [x1 - c, y1], "tol": tol},
        {
            "name": "corner",
            "start": [x1 - c, y1],
            "end": [x1, y1 - c],
            "centre": [x1 - c, y1 - c],
            "tol": tol,
        },
        {"name": "right wall", "start": [x1, y1 - c], "end": [x1, y0 + c], "tol": tol},
        {
            "name": "corner",
            "start": [x1, y0 + c],
            "end": [x1 - c, y0],
            "centre": [x1 - c, y0 + c],
            "tol": tol,
        },
        {"name": "near wall", "start": [x1 - c, y0], "end": [x0 + c, y0], "tol": tol},
        {
            "name": "corner",
            "start": [x0 + c, y0],
            "end": [x0, y0 + c],
            "centre": [x0 + c, y0 + c],
            "tol": tol,
        },
        {"name": "left wall", "start": [x0, y0 + c], "end": [x0, ym], "tol": tol},
    ]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The frame's sizes, window and tap from the export, each checked
    against the frame the recipe assumes: the left face X0, the bottom end
    Y0, the model's front_face (the drawing's back face) Z0, the window
    through Z, the tap into the bottom end along +Y."""
    f = features["features"]
    for name, axis in (("left_face", "x"), ("bottom_face", "y"), ("front_face", "z")):
        plane = f[name]["plane"]
        if plane["axis"] != axis or plane["value"] != 0.0:
            raise ValueError(f"{name}: expected at model {axis.upper()}0")
    sizes = {}
    for name, key, axis in (
        ("right_face", "width", "x"),
        ("top_face", "height", "y"),
        ("back_face", "depth", "z"),
    ):
        plane, nominal = f[name]["plane"], f[name][f"{key}_nominal"]
        if plane["axis"] != axis or not math.isclose(
            plane["value"], nominal, abs_tol=1e-3
        ):
            raise ValueError(
                f"{name} at {axis.upper()} {plane['value']} is not the {key} {nominal}"
            )
        sizes[key] = nominal
    window = f["window"]
    if window["axis"] != [0.0, 0.0, 1.0] or window["thru"] is not True:
        raise ValueError("window: expected through the part along Z")
    x0, y0 = window["left_wall_nominal"], window["bottom_wall_nominal"]
    x1, y1 = x0 + window["width_nominal"], y0 + window["height_nominal"]
    if not (0 < x0 < x1 < sizes["width"] and 0 < y0 < y1 < sizes["height"]):
        raise ValueError("window: its walls are not inside the frame")
    tap = f["thumb_screw_tap"]
    match = _THREAD.fullmatch(tap["thread"])
    if match is None:
        raise ValueError(f"thumb_screw_tap: thread {tap['thread']!r}")
    at = tap["at"]
    if tap["axis"] != [0.0, 1.0, 0.0] or at[1] != 0.0:
        raise ValueError("thumb_screw_tap: expected into the bottom end along +Y")
    if tap["breaks_into"] != "window" or tap["thru"] is not True:
        raise ValueError(
            "thumb_screw_tap: expected through the bottom rail into the window"
        )
    if not (
        math.isclose(at[0], tap["station_nominal"], abs_tol=1e-3)
        and math.isclose(at[2], tap["depth_station_nominal"], abs_tol=1e-3)
        and x0 < at[0] < x1
    ):
        raise ValueError(
            "thumb_screw_tap: not at its stations, or not under the window"
        )
    return {
        **sizes,
        "window_x": (x0, x1),
        "window_y": (y0, y1),
        "corner_r": window["corner_r"],
        "tap_at": at,
        "tap_dia": tap["dia"],
        "tap_wall_min": tap["wall_min"],
        "pitch": IN / int(match.group(1)),
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    W, H, D = g["width"], g["height"], g["depth"]

    # The blank: the bar's section (width × thickness), sawn to length.
    bw, bt = p["blank_width_in"] * IN, p["blank_thick_in"] * IN
    _agree(plan, "blank_width_mm", bw)
    _agree(plan, "blank_thick_mm", bt)
    blank_min, blank_max = p["blank_length_min_in"] * IN, p["blank_length_max_in"] * IN
    end_skim, edge_skim, face_skim = (
        p["end_skim_mm"],
        p["edge_skim_mm"],
        p["face_skim_mm"],
    )
    upright_top = blank_max - end_skim
    _agree(plan, "upright_top_max_mm", upright_top)
    if blank_min - end_skim < H:
        raise ValueError(
            f"the shortest blank less the top-end skim, {blank_min - end_skim:.3f}, is under the height {H:.3f}"
        )
    edge_level, face_level = bw - edge_skim, bt - face_skim
    _agree(plan, "edge_level_mm", edge_level)
    _agree(plan, "face_level_mm", face_level)
    if edge_level <= W or face_level <= D:
        raise ValueError("the bar leaves nothing to face to the width or the depth")
    # PF03 and PF05 skim at a fixed height above the parallels: the bar's
    # width and thickness, miked before Setup 2, must give each skim at
    # least bar_skim_min_mm and at most one face level.
    skim_min, skim_max = p["bar_skim_min_mm"], p["face_step_max_mm"]
    for key, level in (("bar_width", edge_level), ("bar_thick", face_level)):
        _agree(plan, f"{key}_min_mm", level + skim_min)
        _agree(plan, f"{key}_max_mm", level + skim_max)
    if not p["bar_width_min_mm"] <= bw <= p["bar_width_max_mm"] or not (
        p["bar_thick_min_mm"] <= bt <= p["bar_thick_max_mm"]
    ):
        raise ValueError("the nominal bar is outside its own size window")
    for key, size in (
        ("blank_x_in", bw),
        ("blank_y_in", blank_min),
        ("blank_z_in", bt),
    ):
        if not math.isclose(p[key] * IN, size, abs_tol=PLAN_TOL_MM):
            raise ValueError(f"process.{key} is not the blank's {size / IN:.3f} in")

    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    e8 = _shop_tool(plan, shop, "em-eighth")["diameter_mm"]
    d43 = _shop_tool(plan, shop, "drill-43")["diameter_mm"]
    r = em / 2
    lo, hi = g["tap_dia"]
    if not lo - 1e-3 <= d43 <= hi:
        raise ValueError(f"#43 Ø{d43} is not the tap drill band {g['tap_dia']}")
    step_max = p["face_stepover_max_mm"]
    face_cuts = ("top end", "height", "left face", "width", "back face", "depth")
    face_rpm, face_feed = _setting(plan, shop, "top end")
    for name in face_cuts:
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), em, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' cutter Ø{_cut(plan, name, 'cutter_dia_mm')}, the end mill is Ø{em}"
            )
        if _setting(plan, shop, name) != (face_rpm, face_feed):
            raise ValueError(f"'{name}' runs at another setting than 'top end'")
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), step_max, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' radial_woc_mm is not process.face_stepover_max_mm"
            )
    for name, doc in (
        ("top end", end_skim),
        ("left face", edge_skim),
        ("back face", face_skim),
    ):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), doc, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not its skim")
    level_max = p["face_step_max_mm"]
    height_levels = _levels(upright_top, H, level_max)
    width_levels = _levels(edge_level, W, level_max)
    depth_levels = _levels(face_level, D, level_max)
    for name in ("height", "width", "depth"):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), level_max, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not process.face_step_max_mm")

    # The window: the 1/8 in end mill slots round it finish_stock inside the
    # walls, then finishes the walls and corners a cutter radius inside them,
    # both from the front face to run_past below the back face, between the
    # parallel stacks, at the same levels and setting (owner ruling
    # 2026-11-23, tool audit Q9: no 5/64 cutter).
    for name in ("window rough", "window plunge", "window finish"):
        if not math.isclose(p["window_cutter_dia_mm"], e8, abs_tol=1e-6) or not (
            math.isclose(_cut(plan, name, "cutter_dia_mm"), e8, abs_tol=1e-6)
        ):
            raise ValueError(f"'{name}' cutter is not the shop's Ø{e8}")
    r8 = e8 / 2
    stock = p["window_finish_stock_mm"]
    if stock <= 0:
        raise ValueError(f"window_finish_stock_mm {stock} leaves no finish")
    # The finish turns each corner about the slot path's corner, so the
    # corners come out at the cutter's radius plus the stock: the printed
    # R.065's band (.060-.070) must hold it.
    d_rough = r8 + stock
    corner_lo, corner_hi = g["corner_r"]
    if not corner_lo <= d_rough <= corner_hi:
        raise ValueError(
            f"the window's corners come out at R{d_rough:.3f}, outside the printed"
            f" corner band {corner_lo:.3f}-{corner_hi:.3f}"
        )
    if not math.isclose(
        _cut(plan, "window finish", "radial_woc_mm"), stock, abs_tol=1e-6
    ):
        raise ValueError(
            "'window finish' radial_woc_mm is not process.window_finish_stock_mm"
        )
    run_past = p["window_run_past_mm"]
    bottom = -run_past
    window_levels = _levels(D, bottom, SLOT_AXIAL_MAX * e8)
    _agree(plan, "window_step_mm", (D - bottom) / len(window_levels))
    for name in ("window rough", "window finish"):
        if not math.isclose(
            _cut(plan, name, "axial_doc_mm"), p["window_step_mm"], abs_tol=1e-6
        ):
            raise ValueError(f"'{name}' axial_doc_mm is not process.window_step_mm")
    window_rpm, window_feed = _setting(plan, shop, "window rough")
    if _setting(plan, shop, "window finish") != (window_rpm, window_feed):
        raise ValueError("'window finish' runs at another setting than the slot")
    _agree(plan, "window_plunge_feed_per_min_mm", PLUNGE_CHIP_FRACTION * window_feed)
    if _setting(plan, shop, "window plunge") != (
        window_rpm,
        p["window_plunge_feed_per_min_mm"],
    ):
        raise ValueError(
            f"'window plunge' is not {window_rpm:g} rpm at"
            " process.window_plunge_feed_per_min_mm"
        )
    x0, x1 = g["window_x"]
    y0, y1 = g["window_y"]
    _agree(plan, "window_right_mm", x1)
    _agree(plan, "window_far_mm", H - y0)
    _agree(plan, "window_near_mm", H - y1)
    if x1 - x0 <= 2 * (d_rough + r8) or y1 - y0 <= 2 * (d_rough + r8):
        raise ValueError(
            "the rough slot leaves no slug: it would mill the whole window"
        )

    # The thumb-screw tap, from the bottom end: spot under the #43, the #43
    # pecked with full retracts until its full diameter is past the bottom
    # rail, the plug tap's chamfer run past the rail into the window.
    spot_rpm, spot_feed = _setting(plan, shop, "tap spot")
    drill_rpm, drill_feed = _setting(plan, shop, "tap drill")
    _agree(plan, "spot_feed_per_min_mm", spot_feed)
    _agree(plan, "drill_43_feed_per_min_mm", drill_feed)
    if not math.isclose(
        _cut(plan, "tap spot", "cutter_dia_mm"), p["spot_dia_mm"], abs_tol=1e-6
    ):
        raise ValueError("'tap spot' cutter_dia_mm is not process.spot_dia_mm")
    if p["spot_dia_mm"] >= d43:
        raise ValueError(
            "the spot is not under the #43 drill: it would chamfer the hole"
        )
    spot_depth = _spot_depth(p["spot_dia_mm"])
    peck = p["peck_mm"]
    op = _op_with_cut(plan, "tap drill")[0]
    if op["peck"] != {"step_mm": peck, "retract": "full"}:
        raise ValueError("'tap drill' peck is not process.peck_mm with full retract")
    if op["hole_depth_mm"] != "{{process.drill_full_depth_mm}}":
        raise ValueError(
            "'tap drill' hole_depth_mm is not {{process.drill_full_depth_mm}}"
        )
    rail = y0
    full_depth = rail + p["tap_drill_past_mm"]
    _agree(plan, "drill_full_depth_mm", full_depth)
    tip = full_depth + _point(d43)
    _agree(plan, "drill_tip_depth_mm", tip)
    _agree(plan, "drill_tip_height_mm", H - tip)
    reach_min = rail + PLUG_CHAMFER_THREADS * g["pitch"]
    _agree(plan, "tap_reach_min_mm", reach_min)
    _agree(plan, "tap_wall_min_mm", g["tap_wall_min"])
    if not p["tap_reach_min_mm"] <= p["tap_reach_mm"] <= p["tap_reach_max_mm"] < y1:
        raise ValueError(
            "process.tap_reach_mm is not between its min and max, or the max reaches the window's far wall"
        )

    # Vise: upright and on edge on the 1 in pair, lying on the stacks.
    upright_grip = p["vise_jaw_height_mm"] - p["parallel_height_mm"]
    lying_grip = p["vise_jaw_height_mm"] - p["riser_height_mm"]
    _agree(plan, "upright_grip_mm", upright_grip)
    _agree(plan, "lying_grip_mm", lying_grip)
    if lying_grip >= D:
        raise ValueError(
            "lying, the jaws reach the front face: the faces would cut the jaws"
        )
    t = p["parallel_thickness_mm"]
    # The window and its run past lie between the stacks under the ends: no
    # window cutter leaves the window.
    if not (t < y0 and y1 < H - t):
        raise ValueError(f"the window reaches a parallel stack ({t} thick)")
    # The tap guide and the tap together: the spindle-to-table maximum less
    # the tool-change clearance, the vise, the parallels, the frame upright
    # and the collet, rounded down to .01 in.
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["parallel_height_mm"]
        - H
        - p["r8_collet_gauge_mm"]
    )
    _agree(plan, "tap_stack_max_mm", math.floor(stack / IN * 100 + 1e-9) / 100 * IN)

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)). Raw faces: the left
    # face's skim beyond X0, the right the rest of the bar's width beyond
    # it; the back face's (model Z0) skim beyond Z0, the front face the rest
    # of its thickness; the top end's skim beyond the height.
    raw_left = -edge_skim
    raw_right = raw_left + bw
    raw_front = -face_skim
    raw_back = raw_front + bt
    cx, cz = (raw_left + raw_right) / 2, (raw_front + raw_back) / 2
    frames = {
        # Upright, the back face (model Z0) to the fixed jaw (+Y).
        "top": _frame([cx, H, cz], [0, 0, -1], [0, 1, 0]),
        "bottom": _frame([cx, H, cz], [0, 0, -1], [0, -1, 0]),
        # On edge, the back face to the fixed jaw: X0 the bottom end, then
        # turned over, the top end.
        "left": _frame([raw_right, 0.0, raw_front], [0, 0, -1], [-1, 0, 0]),
        "right": _frame([0.0, H, raw_front], [0, 0, -1], [1, 0, 0]),
        # Lying: the bottom end to the fixed jaw, then turned end for end,
        # the top end; X0 the left face.
        "lying": _frame([0.0, 0.0, raw_back], [0, -1, 0], [0, 0, -1]),
        "flipped": _frame([0.0, H, 0.0], [0, 1, 0], [0, 0, 1]),
        # Upright, the bottom end up, the back face to the fixed jaw (the
        # hole's drawing station is from it): X0 the left face, on the right.
        "tap": _frame([0.0, 0.0, 0.0], [0, 0, -1], [0, -1, 0]),
    }
    hw, ht = bw / 2, bt / 2
    stocks = {
        "top": ((-hw, hw), (-ht, ht), (-upright_top, end_skim)),
        "bottom": ((-hw, hw), (-ht, ht), (0.0, upright_top)),
        "left": ((0.0, H), (-bt, 0.0), (0.0, bw)),
        "right": ((0.0, H), (-bt, 0.0), (0.0, edge_level)),
        "lying": ((0.0, W), (-H, 0.0), (0.0, bt)),
        "flipped": ((0.0, W), (-H, 0.0), (0.0, face_level)),
        "tap": ((-W, 0.0), (-D, 0.0), (-H, 0.0)),
    }
    # Every frame puts the finished part where its stock box says.
    for key, frame in frames.items():
        corners = [
            _to(frame, [a, b, c]) for a in (0.0, W) for b in (0.0, H) for c in (0.0, D)
        ]
        for axis in range(3):
            low, high = stocks[key][axis]
            values = [corner[axis] for corner in corners]
            if min(values) < low - 1e-6 or max(values) > high + 1e-6:
                raise ValueError(
                    f"{key}: the part is outside its stock along {'XYZ'[axis]}"
                )
    hole = _to(frames["tap"], g["tap_at"])
    if not math.isclose(hole[2], 0.0, abs_tol=1e-6):
        raise ValueError("the tap's entry is not on Z0 (the bottom end) in PF07")
    hole_xy = [_r(hole[0]), _r(hole[1])]

    em_tool = {
        "tool": "em-half",
        "dia": em,
        "shape": "endmill",
        "flutes": 3,
        "rpm": face_rpm,
        "feed": face_feed,
        "plunge": face_feed,
    }
    window_tool = {
        "tool": "em-eighth",
        "dia": e8,
        "shape": "endmill",
        "flutes": 3,
        "rpm": window_rpm,
        "feed": window_feed,
        "plunge": p["window_plunge_feed_per_min_mm"],
    }
    spot_tool = {
        "tool": "spot",
        "dia": CENTRE_DRILL["body_mm"],
        "shape": "drill",
        "tip_angle": CENTRE_DRILL["point_deg"],
        "rpm": spot_rpm,
        "feed": spot_feed,
        "plunge": spot_feed,
    }
    drill_tool = {
        "tool": "drill-43",
        "dia": d43,
        "shape": "drill",
        "tip_angle": DRILL_POINT_DEG,
        "rpm": drill_rpm,
        "feed": drill_feed,
        "plunge": drill_feed,
    }

    def run(x: tuple[float, float]) -> tuple[float, float]:
        return (x[0] - r - APPROACH_MM, x[1] + r + APPROACH_MM)

    upright_x, upright_y = (-hw, hw), (-ht, ht)
    edge_x, edge_y = (0.0, H), (-bt, 0.0)
    lying_x, lying_y = (0.0, W), (-H, 0.0)
    upright_ys = _stations(upright_y, r, step_max)
    edge_ys = _stations(edge_y, r, step_max)
    lying_ys = _stations(lying_y, r, step_max)
    # key: (frame, levels, stock top, X run, pass stations, face Y, X span)
    faces = {
        "top_end": ("top", [0.0], end_skim, run(upright_x), upright_ys, upright_y, bw),
        "bottom_end": (
            "bottom",
            height_levels,
            upright_top,
            run(upright_x),
            upright_ys,
            upright_y,
            bw,
        ),
        "left_face": ("left", [edge_level], bw, run(edge_x), edge_ys, edge_y, H),
        "right_face": (
            "right",
            width_levels,
            edge_level,
            run(edge_x),
            edge_ys,
            edge_y,
            H,
        ),
        "back_face": ("lying", [face_level], bt, run(lying_x), lying_ys, lying_y, W),
        "front_face": (
            "flipped",
            depth_levels,
            face_level,
            run(lying_x),
            lying_ys,
            lying_y,
            W,
        ),
    }
    jobs = []
    for key, (frame, levels, top, xs, ys, _y, _span) in faces.items():
        jobs.append(
            {
                **em_tool,
                "frame": frame,
                "label": key.replace("_", " "),
                "stock": stocks[frame],
                "ops": [
                    [
                        key,
                        f"face the {key.replace('_', ' ')}",
                        _face(levels, top, xs, ys),
                    ]
                ],
            }
        )

    # The window in PF06's frame (X0 the left face, Y0 the top end).
    wx = (x0, x1)
    wy = (y0 - H, y1 - H)
    rough_x, rough_y = (
        (wx[0] + d_rough, wx[1] - d_rough),
        (wy[0] + d_rough, wy[1] - d_rough),
    )
    stock_back = ((0.0, W), (-H, 0.0), (0.0, D))
    jobs += [
        {
            **window_tool,
            "frame": "flipped",
            "label": "window",
            "stock": stock_back,
            "ops": [
                [
                    "window_rough",
                    "rough the window",
                    _loop(rough_x, rough_y, D, window_levels),
                ],
                [
                    "window_finish",
                    "finish the window",
                    _finish_loop(wx, wy, d_rough, stock, D, window_levels),
                ],
            ],
        },
        {
            **spot_tool,
            "frame": "tap",
            "label": "tap spot",
            "stock": stocks["tap"],
            "ops": [
                [
                    "tap_spot",
                    "spot the thumb-screw hole",
                    _spot(hole_xy, 0.0, -spot_depth, CLEAR_MM),
                ]
            ],
        },
        {
            **drill_tool,
            "frame": "tap",
            "label": "tap drill",
            "stock": stocks["tap"],
            "ops": [
                [
                    "tap_drill",
                    "drill the thumb-screw hole #43",
                    _pecked(hole_xy, 0.0, -tip, peck, CLEAR_MM),
                ]
            ],
        },
    ]

    # The tap file: the tap guide loaded by its own M6 (its %msg names the
    # hole), Z to the machine's top in machine coordinates before any XY
    # (the operator left Z jogged down after the last tool change), over the
    # hole, M30: the controller ends Idle, so the operator can jog the
    # guide's point down into the wrench.
    manual = {
        "tap": {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": "SPINDLE STAYS OFF. NEXT: 4-40 TAP IN THE BOTTOM END",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{hole_xy[0]:.3f} Y{hole_xy[1]:.3f}",
                "(4-40 TAP IN THE BOTTOM END. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND TO THE NOTED DRO Z, READ WITH THE POINT PUSHED HOME. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": hole_xy,
        }
    }

    # Keep-outs. The jaws beside the gripped span, from their top (grip
    # above the parallels or stacks, less where Z0 is) up, across the jaw
    # width; lying, the stacks under the ends.
    jaw_w = p["vise_jaw_width_mm"]

    def jaws(
        z_top: float, x: tuple[float, float], y: tuple[float, float]
    ) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - jaw_w / 2, mid + jaw_w / 2)
        return [
            _box("moving jaw", span, (y[0] - JAW_DEPTH_MM, y[0]), z_top),
            _box("fixed jaw", span, (y[1], y[1] + JAW_DEPTH_MM), z_top),
        ]

    mid = W / 2
    par_x = (mid - PARALLEL_LENGTH_MM / 2, mid + PARALLEL_LENGTH_MM / 2)
    stacks = [
        _box("moving-jaw stack", par_x, (-H, -H + t), 0.0),
        _box("fixed-jaw stack", par_x, (-t, 0.0), 0.0),
    ]
    keep = {
        "top_end": jaws(upright_grip - (blank_min - end_skim), upright_x, upright_y),
        "bottom_end": jaws(upright_grip, upright_x, upright_y),
        "left_face": jaws(upright_grip, edge_x, edge_y),
        "right_face": jaws(upright_grip, edge_x, edge_y),
        "back_face": jaws(lying_grip, lying_x, lying_y),
        "front_face": jaws(lying_grip, lying_x, lying_y),
    }
    window_keep = keep["front_face"] + stacks
    tap_keep = jaws(upright_grip - H, (-W, 0.0), (-D, 0.0))

    tn = numbers
    expect: list[list[Any]] = []

    def face_checks(key: str) -> list[list[Any]]:
        _frame_key, levels, top, _xs, _ys, y, span = faces[key]
        return [
            ["depth", {"z_min": _r(levels[-1])}],
            ["rapids_clear", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            *[
                [
                    "face_passes",
                    {
                        "z": _r(z),
                        "y": list(y),
                        "max_engagement": step_max,
                        "radius": r,
                        "span": span,
                        "overhang": FACE_OVERHANG_MM,
                    },
                ]
                for z in levels
            ],
            ["keep_out", {"radius": r, "boxes": keep[key]}],
        ]

    # The slot and the finish against the window's outline with its corners
    # at R d_rough: the slot's path (sharp-cornered) d_rough inside it, the
    # finish's a cutter radius inside it, turning each corner about the
    # slot's corner; every level of the slot before any of the finish.
    window_z = [_r(z) for z in window_levels]
    window_checks = [
        ["depth", {"z_min": _r(bottom)}],
        ["rapids_clear", {"z_top": D}],
        ["air_feed", {"z_top": D}],
        [
            "outline",
            {
                "elements": _outline(wx, wy, d_rough),
                "passes": [
                    {"offset": d_rough, "levels": window_z},
                    {"offset": r8, "levels": window_z},
                ],
                "z_top": D,
                "clearing": [],
            },
        ],
        ["keep_out", {"radius": r8, "boxes": window_keep}],
    ]

    def hole_checks(z_bottom: float, radius: float) -> list[list[Any]]:
        return [
            ["holes", {"centres": [hole_xy], "z_bottom": _r(z_bottom)}],
            ["rapids_clear", {"z_top": 0.0, "open_holes": [hole_xy]}],
            ["vertical_below_top", {"z_top": 0.0}],
            ["air_feed", {"z_top": 0.0}],
            ["keep_out", {"radius": radius, "boxes": tap_keep}],
        ]

    single = {
        "PF01_top_end": "top_end",
        "PF02_height": "bottom_end",
        "PF03_left_face": "left_face",
        "PF04_width": "right_face",
        "PF05_back_face": "back_face",
    }
    for name, key in single.items():
        top = faces[key][2]
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": top, "tools": [tn["em-half"]], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[face_rpm]]}],
            [name, "pauses", {"z_top": top, "count": 0}],
            *[[name, check, kwargs] for check, kwargs in face_checks(key)],
        ]
    name = "PF06_window"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": face_level,
                "tools": [tn["em-half"], tn["em-eighth"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[face_rpm], [window_rpm]]}],
        [name, "pauses", {"z_top": face_level, "count": 0}],
        [name, "depth", {"z_min": _r(bottom)}],
    ]
    for k, checks in enumerate((face_checks("front_face"), window_checks)):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]
    name = "PF07_tap_drill"
    expect += [
        [
            name,
            "tool_changes",
            {"z_top": 0.0, "tools": [tn["spot"], tn["drill-43"]], "loads_first": True},
        ],
        [name, "spindle", {"rpm": [[spot_rpm], [drill_rpm]]}],
        [name, "pauses", {"z_top": 0.0, "count": 0}],
        [name, "depth", {"z_min": _r(-tip)}],
    ]
    for k, checks in enumerate(
        (
            hole_checks(-spot_depth, CENTRE_DRILL["body_mm"] / 2),
            hole_checks(-tip, d43 / 2),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]
    expect += [
        [
            "PF08_tap",
            "tap_stop",
            {"tool": tn["tap-guide"], "at": hole_xy, "machine_top": MACHINE_Z_TOP_MM},
        ],
        ["PF08_tap", "air_feed", {"z_top": 0.0}],
    ]

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": frames,
        "names": names,
        "numbers": numbers,
        "jobs": jobs,
        "manual": manual,
        "expect": expect,
    }


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    return [(program, check, kwargs) for program, check, kwargs in ctx["expect"]]


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job per
    section; returns {"ops": {operation key: operation or manual section}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(
            doc, f"Pen frame {key}", ctx["step"], frame["origin"], frame["axes"]
        )
        for key, frame in ctx["frames"].items()
    }
    ops: dict[str, Any] = {}
    for section in ctx["jobs"]:
        target = rt.job(
            doc, section["label"], [models[section["frame"]]], section["stock"]
        )
        tc = rt.tool_controller(
            doc,
            ctx["names"][section["tool"]],
            ctx["numbers"][section["tool"]],
            section["shape"],
            section["dia"],
            section["rpm"],
            section["feed"],
            section["plunge"],
            flutes=section.get("flutes"),
            tip_angle=section.get("tip_angle"),
        )
        for key, label, lines in section["ops"]:
            ops[key] = rt.custom(target, tc, label, lines)
    ops.update(ctx["manual"])
    rt.generate(doc)
    return {"ops": ops}


# The as-machined report (``cad/scripts/_as_machined.py``) only reports: it
# never fails the task. "gate" would fail it on a difference over the noise
# line or a rapid that cuts.
AS_MACHINED_MODE = "report"


def as_machined(ctx: dict[str, Any], inputs: Any) -> dict[str, Any]:
    """What the as-machined report needs: the blank sawn off the 3/8 x 1-1/4
    in bar, as PF01 holds it upright (its stock box: the bar's section, the
    raw top end the end skim above Z0), the sawn length below the raw top at
    the plan's 1.65-1.75 in band and its middle (the plan's "sawn 1.70
    ±.05"). The top end touches Z0 in PF01, so the raw top stays put and a
    longer blank reaches further down, which PF02 faces off. Every program
    runs in its jobs' one frame; PF08 is the hand tap (no frame)."""
    p = inputs.plan["parameters"]
    lengths = {
        "nominal": (p["blank_length_min_in"] + p["blank_length_max_in"]) / 2 * IN,
        "min": p["blank_length_min_in"] * IN,
        "max": p["blank_length_max_in"] * IN,
    }
    stock = next(job["stock"] for job in ctx["jobs"] if job["ops"][0][0] == "top_end")
    top = stock[2][1]
    return {
        "parts": {
            "": {
                "blank": {
                    "frame": "top",
                    "box": [list(stock[0]), list(stock[1]), [top - lengths["nominal"], top]],
                    "length": {"axis": "z", "keep": "max", "mm": lengths},
                }
            }
        },
        "skip": {},
        "notes": ["PF08 is the 4-40 tap by hand under the tap guide: the report cuts no thread"],
    }
