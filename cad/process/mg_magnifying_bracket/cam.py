"""FreeCAD CAM recipe for MHA-MG-01, the magnifying bracket.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The bracket's sizes
come from the feature export (the outer face, the free end, both sides, the
seat and the foot's underside, the neck's inner face, the nose, the lever tap
and the two mounting holes); the blank, the skims, levels, spots, tips and the
holding from ``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter
diameters, speeds and feeds from the shop (``shop/``) and the plan's authored
drill settings. Every path is written here (``rt.custom``): straight lines and
arcs a recipe can state exactly. Typed here, because neither record carries
them: the #2 centre drill's catalogue geometry (it sets the spot depth), the
twist drills' 118° point, the 1/4-20 thread's pitch, the approach, safe and
clearance heights, the face overhang, the vise jaws' depth and the parallels'
length (keep-out shapes only) and the machine's Z top for the tap file's
retract.

Route (the agent's, for speed; plan text in ``plan.toml``): one blank of 1/2 ×
2-1/4 in 1018 flat, sawn 4.75-4.80 long, the bar's length along the bracket's
height (the neck), its width across the foot. MB01, on edge on the 1 in
parallels: face the bar's upper edge to the foot's length (the free end F;
the lower, as-bought edge stays as the outer face O). MB02, upright on the
vise bed: face the seat, spot and drill the two #37 mounting holes down from
it, through the foot into the notch's waste. MB03, lying on the 1 in + 1/2 in
stacks (one under the seat end, one under the sawn end), gripped across its
length (the seat on the fixed jaw, a rod on the sawn end): face the high side
H, then mill the notch between the foot and the neck, open at F, half the
width deep, the neck's wall left 0.5 mm full. MB04, H down: face the low side
L to the width, then mill the notch's other half through to MB03's, so no
thin skin is ever cut. The nose waste is sawn off at the
bench. MB05, on edge on the stacks, the foot past the jaws' left side: face
the neck's inner face to the neck thickness and square the inside corner
under the foot (the end mill's square corner; MB03's cutter left its radius
there). MB06, on edge on the 1 in parallels, the nose past the jaws' right
side: profile the nose R.217 and spot and drill #7 through for the tap; MB07
is the hand-tap stop.

Work frames (G54), each set in its setup:
- MB01: X0 the blank's seat end (left), Y0 the fixed jaw (L), Z0 the
  parallels (O).
- MB02: X0 the free end F (right, the part to -X), Y0 the fixed jaw (L), Z0
  the faced seat.
- MB03: X0 the outer face O (left), Y0 the fixed jaw (the seat), Z0 the
  stacks (L).
- MB04: X0 O (right, the part to -X), Y0 the fixed jaw (the seat), Z0 the
  stacks (H).
- MB05-MB07: X0 the seat (left), Y0 the fixed jaw (L), Z0 the stacks or the
  parallels (O).

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed or ramped along a pass, real G0
above the stock; the nose is profiled climb (G2 round the outside). The lever
tap is tapped by hand (FluidNC cannot rigid-tap; owner, Pedro, 2026-11-17)
under the Fisher spring tap guide in the 1/2 in R8 collet (owner, Pedro,
2026-11-21), spindle off; FluidNC refuses jogs while an M0 holds the program
(http://wiki.fluidnc.com/en/features/single_block_mode), so the tap stop is a
file of its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "mg_magnifying_bracket"
COMMENT = "MHA-MG-01 magnifying bracket"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("MB01_width", ("width",)),
    ("MB02_seat", (("seat",), ("mount_spot",), ("mount_drill",))),
    # One end mill, one section per speed (an M0 stop between them).
    ("MB03_notch", (("high_side",), ("notch",), ("foot_wall",))),
    ("MB04_low", (("low_side",), ("notch_through",), ("foot_wall_through",))),
    ("MB05_neck", ("neck",)),
    ("MB06_nose", (("nose_rough",), ("nose_finish",), ("tap_spot",), ("tap_drill",))),
    ("MB07_lever_tap", ("lever_tap",)),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held, and the tap file before its retract
# (the tap guide).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the tap, the saw and the files are not).
CAM_TOOLS = ("em-half", "spot", "drill-37", "drill-7", "tap-guide")
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
# The 1/4-20 UNC thread's pitch (ASME B1.1, 20 threads per inch) and a plug
# tap's chamfer of five threads: the export names the thread, not its sizes.
UNC_1_4_20_PITCH_MM = IN / 20
PLUG_TAP_LEAD_THREADS = 5
# The tap file's first motion: G53 G0 to machine Z0, the homed top (owner,
# Pedro, answered in person 2026-11-21, cnc rulings record: machine Z = 0 is
# the top of travel after homing).
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
# Keep-outs: each vise jaw's depth outward from the gripped face; the
# parallels' length (4 in, shop-equipment fixtures.parallels-lms-6745).
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 4 * IN
# The nose outline's allowed stray of the cutter centre from its offset.
OUTLINE_TOL_MM = 0.01
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01


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
    names (chip load × flutes × rpm), or, with no setting, the rpm and feed
    the cut itself authors."""
    op, record_cut = _op_with_cut(plan, cut)
    if "settings" not in op:
        return _cut(plan, cut, "rpm"), _cut(plan, cut, "feed_mm_min")
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    feed = record["chip_load_mm_per_tooth"] * record["flutes"] * rpm
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


def _inside(value: float, band: list[float]) -> bool:
    """``value`` in ``band``, to the export's 0.001 mm rounding."""
    return band[0] - 1e-3 <= value <= band[1] + 1e-3


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, abs_tol=1e-3)


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


def _plunged(
    points: list[tuple[float, float]], top: float, tip: float, clear: float
) -> list[str]:
    """One plunge per hole from the R plane to ``tip``; moves between the
    holes at ``clear``."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    lines = [f"G0 Z{clear:.3f}"]
    for x, y in points:
        lines += [
            f"G0 X{x:.3f} Y{y:.3f}",
            f"G0 Z{r_plane:.3f}",
            f"G1 Z{_r(tip):.3f} F{{feed}}",
            f"G0 Z{r_plane:.3f}",
            f"G0 Z{clear:.3f}",
        ]
    return lines


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
    from the cutter-centre end ``x[0]`` (beside the part: every plunge, level
    change and return is there) to ``x[1]`` and back, alternating direction;
    an odd count ends with a feed back to ``x[0]``."""
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
            lines.append(f"G1 X{x0:.3f} F{{feed}}")
        if z != levels[-1]:
            lines.append(f"G1 Y{ys[0]:.3f} F{{feed}}")
    return lines + [f"G0 Z{clear:.3f}"]


def _notch(
    top: float,
    surface: float,
    levels: list[float],
    xs: list[float],
    foot_y: float,
    waste_y: float,
    radius: float,
) -> list[str]:
    """A notch from the faced ``surface`` down its ``levels`` that never
    steps over in uncut stock (a full-width cut): at each level every
    station ``xs`` (from beside F in to the neck's wall) ramps along Y from
    the waste line ``waste_y`` down to the foot's line ``foot_y`` and feeds
    back level, taking the wedge the ramp left; it then rises to the level
    above (cut, or the face) and steps over there to the next station. Each
    pass meets only the strip between its station and the one before (the
    stations' step) until its last ``radius`` into the closed waste end,
    where it also takes the scallop the station before left against that
    end, as a cutter does entering any closed corner: the pass back is posted
    as those two moves. Moves between cuts are G0 above the raw top
    ``top``."""
    clear = _r(top + CLEAR_MM)
    foot, waste = _r(foot_y), _r(waste_y)
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{xs[0]:.3f} Y{waste:.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
        f"G1 Z{_r(surface):.3f} F{{feed}}",
    ]
    above = surface
    for z in levels:
        for k, x in enumerate(xs):
            if k:
                lines += [f"G1 Z{_r(above):.3f} F{{feed}}", f"G1 X{x:.3f} F{{feed}}"]
            lines += [
                f"G1 Y{foot:.3f} Z{_r(z):.3f} F{{feed}}",
                f"G1 Y{_r(waste_y + radius):.3f} F{{feed}}",
                f"G1 Y{waste:.3f} F{{feed}}",
            ]
        if z != levels[-1]:
            lines.append(f"G1 X{xs[0]:.3f} F{{feed}}")
        above = z
    return lines + [f"G0 Z{clear:.3f}"]


def _foot_wall(
    top: float, bottom: float, ys: list[float], x_from: float, x_to: float
) -> list[str]:
    """The foot's wall at full depth: one pass per Y in ``ys`` (the last on
    the foot's line) from ``x_from`` to ``x_to`` in -X, climb with the foot
    on the cutter's right, each entered at ``x_from`` (beside F, or in the
    cut notch). Moves between passes are G0 above the raw top ``top``."""
    clear = _r(top + CLEAR_MM)
    lines = [f"G0 Z{clear:.3f}"]
    for y in ys:
        lines += [
            f"G0 X{_r(x_from):.3f} Y{_r(y):.3f}",
            f"G0 Z{_r(top + SAFE_MM):.3f}",
            f"G1 Z{_r(bottom):.3f} F{{feed}}",
            f"G1 X{_r(x_to):.3f} F{{feed}}",
            f"G0 Z{clear:.3f}",
        ]
    return lines


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The bracket's sizes and holes from the export, each checked against
    the frame the recipe assumes: the outer face O and the free end F normal
    to X, the sides L and H normal to Y centred on the origin, the seat and
    the foot's underside normal to Z, the neck's inner face normal to X, the
    nose a half-round about X at the origin with its apex toward -Z, the lever
    tap through the neck along -X at the nose's centre and the two mounting
    holes through the foot along Z."""
    f = features["features"]

    def plane(name: str, axis: str) -> float:
        p = f[name]["plane"]
        if p["axis"] != axis:
            raise ValueError(f"{name}: expected a plane normal to {axis}")
        return float(p["value"])

    outer, free = plane("outer_face", "x"), plane("free_end", "x")
    width = outer - free
    if not _close(width, f["outer_face"]["length_nominal"]):
        raise ValueError(f"F to O {width:.4f} is not the foot's length")
    low, high = plane("low_side", "y"), plane("high_side", "y")
    thick = high - low
    if not _close(thick, f["high_side"]["width_nominal"]) or not _close(low, -high):
        raise ValueError(f"L to H {thick:.4f} is not the width, centred on Y0")
    seat, under = plane("seat", "z"), plane("foot_underside", "z")
    foot = seat - under
    if not _close(foot, f["foot_underside"]["thickness_nominal"]):
        raise ValueError(f"the seat to the underside {foot:.4f} is not the foot")
    inner = plane("neck_inner_face", "x")
    neck = outer - inner
    if not _close(neck, f["neck_inner_face"]["thickness_nominal"]):
        raise ValueError(f"O to the neck's inner face {neck:.4f} is not the neck")
    nose = f["nose"]
    centre, radius = nose["center"], nose["radius_nominal"]
    if (
        nose["axis"] != [1.0, 0.0, 0.0]
        or nose["apex"] != [0.0, 0.0, -1.0]
        or any(not _close(c, 0.0) for c in centre)
        or not _close(2 * radius, thick)
        or not _close(seat - (centre[2] - radius), nose["overall_height_ref"])
    ):
        raise ValueError(
            "nose: expected a half-round about X at the origin, full width"
        )
    tap = f["lever_tap"]
    if (
        tap["axis"] != [-1.0, 0.0, 0.0]
        or not _close(tap["at"][0], outer)
        or not _close(tap["at"][1], centre[1])
        or not _close(tap["at"][2], centre[2])
        or not tap.get("thru")
        or tap["thread"] != "1/4-20 UNC-2B"
    ):
        raise ValueError(
            "lever_tap: expected a 1/4-20 through the neck at the nose's centre"
        )
    holes = []
    for name in ("mounting_hole_1", "mounting_hole_2"):
        hole = f[name]
        if (
            hole["axis"] != [0.0, 0.0, 1.0]
            or not _close(hole["at"][2], under)
            or not hole.get("thru")
            or not free < hole["at"][0] < inner
            or not _close(hole["at"][0] - free, hole["station_nominal"])
            or not _close(hole["at"][1] - low, hole["lateral_nominal"])
        ):
            raise ValueError(f"{name}: expected through the foot at its station from F")
        holes.append(hole)
    return {
        "outer": outer,
        "free": free,
        "width": width,
        "low": low,
        "thick": thick,
        "seat": seat,
        "under": under,
        "foot": foot,
        "inner": inner,
        "neck": neck,
        "radius": radius,
        "tip": seat - (centre[2] - radius),
        "tap": tap,
        "holes": holes,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    width, thick, foot, neck = g["width"], g["thick"], g["foot"], g["neck"]
    outer, low, seat = g["outer"], g["low"], g["seat"]
    radius, tip = g["radius"], g["tip"]

    # The blank: the flat bar's section, sawn to length along the neck.
    for key in ("bar_thickness", "bar_width", "blank_length"):
        for end in ("min", "max"):
            _agree(plan, f"{key}_{end}_mm", p[f"{key}_{end}_in"] * IN)
    t_max = p["bar_thickness_max_mm"]
    w_max = p["bar_width_max_mm"]
    blank_min, blank_max = p["blank_length_min_mm"], p["blank_length_max_mm"]
    seat_skim, low_skim = p["seat_skim_mm"], p["low_skim_mm"]
    high_level = thick + low_skim
    _agree(plan, "high_level_mm", high_level)
    # MB02 drills from the bar's face that L's skim later comes off.
    _agree(plan, "mount_y_mm", g["holes"][0]["lateral_nominal"] + low_skim)
    level_max = p["face_step_max_mm"]
    if t_max - high_level > level_max + 1e-9 or low_skim > level_max + 1e-9:
        raise ValueError("H's or L's facing is over one level")
    if p["bar_thickness_min_mm"] - high_level <= 0 or p["bar_width_min_mm"] <= width:
        raise ValueError("the bar leaves nothing to face to the width or the thickness")
    width_levels = _levels(w_max, width, level_max)
    _agree(plan, "width_level_mm", (w_max - width) / len(width_levels))

    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    d37 = _shop_tool(plan, shop, "drill-37")["diameter_mm"]
    d7 = _shop_tool(plan, shop, "drill-7")["diameter_mm"]
    tap_drill = _shop_tool(plan, shop, "tap-1-4-20")["tap_drill_mm"]
    r = em / 2
    if not _inside(d37, g["holes"][0]["dia"]):
        raise ValueError(f"#37 Ø{d37} is outside the mounting holes' band")
    if not _inside(d7, g["tap"]["dia"]) or not _close(d7, tap_drill):
        raise ValueError(f"#7 Ø{d7} is not the 1/4-20 tap's drill in its band")

    step_max = p["face_stepover_max_mm"]
    skim_step = p["skim_stepover_max_mm"]
    face_cuts = ("width", "seat", "high side", "low side", "neck")
    for name in (
        *face_cuts,
        "notch",
        "foot wall",
        "notch through",
        "foot wall through",
        "nose rough",
        "nose finish",
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), em, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' cutter Ø{_cut(plan, name, 'cutter_dia_mm')}, the end mill is Ø{em}"
            )
    # One measured setting per kind of cut (shop settings, bounded in
    # cad/config/shop-equipment/measured-cuts.toml): the faces (F, the seat,
    # H, L) at the face record's; the notch and the nose's rough at the
    # deep-rough record's; the foot's wall and the nose's finish, deep and
    # climb, at the climb wall record's. The neck (MB05) stays on the chart
    # setting: its stick-out is outside every record's.
    face_rpm, face_feed = _setting(plan, shop, "width")
    deep_rpm, deep_feed = _setting(plan, shop, "notch")
    wall_rpm, wall_feed = _setting(plan, shop, "foot wall")
    chart_rpm, chart_feed = _setting(plan, shop, "neck")
    for name, first in (
        ("seat", "width"),
        ("high side", "width"),
        ("low side", "width"),
        ("notch through", "notch"),
        ("nose rough", "notch"),
        ("foot wall through", "foot wall"),
        ("nose finish", "foot wall"),
    ):
        if _setting(plan, shop, name) != _setting(plan, shop, first):
            raise ValueError(f"'{name}' runs at another setting than '{first}'")
    for name, woc in (
        ("width", skim_step),
        ("seat", skim_step),
        ("high side", skim_step),
        ("low side", skim_step),
    ):
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), woc, abs_tol=1e-6):
            raise ValueError(f"'{name}' radial_woc_mm is not its stepover parameter")

    # The notch, between the foot's underside and the neck's wall (left
    # neck_stock_mm full), open at F, closed by the waste at the sawn end:
    # half its depth from H (MB03, down to notch_split_mm above the stacks,
    # L down), the rest from L once L is faced (MB04, H down, through
    # notch_past_mm past MB03's floor), so no thin skin is ever cut.
    split = (high_level + low_skim - p["notch_past_mm"]) / 2
    _agree(plan, "notch_split_mm", split)
    through = high_level - split - p["notch_past_mm"]
    _agree(plan, "notch_through_mm", through)
    notch_levels = _levels(high_level, split, p["notch_level_max_mm"])
    through_levels = _levels(thick, through, p["notch_level_max_mm"])
    _agree(plan, "notch_level_mm", (high_level - split) / len(notch_levels))
    if not math.isclose(
        (thick - through) / len(through_levels),
        p["notch_level_mm"],
        abs_tol=PLAN_TOL_MM,
    ):
        raise ValueError("MB04's notch levels are not MB03's")
    if through <= 0:
        raise ValueError("MB04's notch reaches the stacks")
    # Y passes (along the part) at X stations from beside F in to the neck's
    # wall station, each taking the same width, no wider than
    # notch_step_max_mm.
    raw_x = width + r
    wall_x = neck + p["neck_stock_mm"] + r
    n = math.ceil((raw_x - wall_x) / p["notch_step_max_mm"] - 1e-9)
    notch_step = (raw_x - wall_x) / n
    _agree(plan, "notch_step_mm", notch_step)
    notch_xs = [_r(raw_x - k * notch_step) for k in range(1, n + 1)]
    foot_y = -(foot + r)
    notch_end = p["notch_end_mm"]
    waste_y = -(notch_end - r)
    # The foot wall: each station's pass ends on the foot's line, leaving
    # cusps between the stations; they come off at full depth, climb, in
    # equal passes no wider than wall_woc_max_mm, the last on the line.
    cusp = r - math.sqrt(r**2 - (notch_step / 2) ** 2)
    wall_n = math.ceil(cusp / p["wall_woc_max_mm"] - 1e-9)
    _agree(plan, "foot_wall_woc_mm", cusp / wall_n)
    foot_ys = [_r(foot_y - cusp * (wall_n - 1 - k) / wall_n) for k in range(wall_n)]
    for name, axial, woc in (
        ("notch", p["notch_level_mm"], notch_step),
        ("notch through", p["notch_level_mm"], notch_step),
        ("foot wall", high_level - split, p["foot_wall_woc_mm"]),
        ("foot wall through", thick - through, p["foot_wall_woc_mm"]),
        ("high side", t_max - high_level, skim_step),
        ("low side", low_skim, skim_step),
        ("width", p["width_level_mm"], skim_step),
        ("seat", seat_skim, skim_step),
    ):
        if not (
            math.isclose(_cut(plan, name, "axial_doc_mm"), axial, abs_tol=1e-3)
            and math.isclose(_cut(plan, name, "radial_woc_mm"), woc, abs_tol=1e-3)
        ):
            raise ValueError(f"'{name}' depth or width is not the recipe's")

    # The saw: the nose waste off at nose_cut_in from the seat, ± its
    # tolerance; the kerf (waste side) stays short of the notch's end, and
    # the shortest blank leaves the jaws waste_min_mm of waste to grip.
    part_min = (p["nose_cut_in"] - p["nose_cut_tol_in"]) * IN
    part_max = (p["nose_cut_in"] + p["nose_cut_tol_in"]) * IN
    _agree(plan, "part_length_min_mm", part_min)
    _agree(plan, "part_length_max_mm", part_max)
    if part_min <= tip:
        raise ValueError("the shortest sawn part does not reach the nose's tip")
    if part_max + p["kerf_in"] * IN >= notch_end:
        raise ValueError("the saw's kerf reaches past the notch into the waste")
    if blank_min - seat_skim - notch_end < p["waste_min_mm"]:
        raise ValueError("the shortest blank leaves too little waste beyond the notch")

    # The neck (MB05): the inner face down to the neck from O, in levels from
    # the top of MB03's corner radius (r above the neck's stock), each in
    # zigzag X passes from the nose end to the foot's underside (the cutter's
    # edge on it): the end mill's square corner makes the inside corner.
    neck_raw = neck + p["neck_stock_mm"]
    neck_levels = _levels(neck_raw + r, neck, p["neck_level_max_mm"])
    _agree(plan, "neck_level_mm", (neck_raw + r - neck) / len(neck_levels))
    if not math.isclose(
        _cut(plan, "neck", "axial_doc_mm"), p["neck_level_mm"], abs_tol=1e-3
    ):
        raise ValueError("'neck' axial_doc_mm is not process.neck_level_mm")
    neck_woc = _cut(plan, "neck", "radial_woc_mm")

    # The nose (MB06): rough rings outside the finish stock, each at every
    # level no deeper than nose_rough_level_max_mm, outermost ring first,
    # the rings in equal steps no wider than nose_rough_step_max_mm; then
    # the finish stock at full depth in equal passes no wider than
    # wall_woc_max_mm, the last on the radius. Through the neck and
    # nose_past_mm below O.
    stock_n = p["nose_finish_stock_mm"]
    nose_depth = neck + p["nose_past_mm"]
    _agree(plan, "nose_depth_mm", nose_depth)
    rough_levels = _levels(neck, neck - nose_depth, p["nose_rough_level_max_mm"])
    _agree(plan, "nose_rough_level_mm", nose_depth / len(rough_levels))
    # The tap's (and the nose's) centre from the seat; the sawn stub beyond.
    centre_x = seat - g["tap"]["at"][2]
    corner = math.hypot(thick / 2, part_max - centre_x)
    rough_woc = corner - radius - stock_n
    _agree(plan, "nose_rough_woc_mm", rough_woc)
    rings = math.ceil(rough_woc / p["nose_rough_step_max_mm"] - 1e-9)
    _agree(plan, "nose_rough_step_mm", rough_woc / rings)
    if corner > radius + stock_n + rough_woc * (rings - 1) / rings + 2 * r:
        raise ValueError("the rough nose pass leaves the longest part's corners uncut")
    finishes = math.ceil(stock_n / p["wall_woc_max_mm"] - 1e-9)
    _agree(plan, "nose_finish_step_mm", stock_n / finishes)
    for name, axial, woc in (
        ("nose rough", p["nose_rough_level_mm"], p["nose_rough_step_mm"]),
        ("nose finish", nose_depth, p["nose_finish_step_mm"]),
    ):
        if not (
            math.isclose(_cut(plan, name, "axial_doc_mm"), axial, abs_tol=1e-3)
            and math.isclose(_cut(plan, name, "radial_woc_mm"), woc, abs_tol=1e-3)
        ):
            raise ValueError(f"'{name}' depth or width is not the plan's")
    # The jaws' right side stands nose_jaw_back_mm back from the nose's
    # centre: the cutter on the nose's sides, a lead's length back, keeps its
    # edge nose_jaw_clear_mm off it.
    lead = p["nose_lead_mm"]
    jaw_back = r + lead + p["nose_jaw_clear_mm"]
    _agree(plan, "nose_jaw_back_mm", jaw_back)
    jaw_right = centre_x - jaw_back
    # Set from the seat: the nose's centre is not drilled yet.
    _agree(plan, "nose_jaw_side_mm", jaw_right)

    # Holes: spots under each drill (no chamfer at the mouth).
    spot_rpm, spot_feed = _setting(plan, shop, "mount spot")
    spots = {}
    for name, key, drill in (
        ("mount spot", "mount_spot_dia_mm", d37),
        ("tap spot", "tap_spot_dia_mm", d7),
    ):
        if _setting(plan, shop, name) != (spot_rpm, spot_feed):
            raise ValueError(f"'{name}' runs at another speed than 'mount spot'")
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), p[key], abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not process.{key}")
        if p[key] >= drill:
            raise ValueError(
                f"'{name}' is not under its drill: it would chamfer the hole"
            )
        spots[name] = _spot_depth(p[key])
    for name, dia in (("mount drill", d37), ("tap drill", d7)):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not its tool's Ø{dia}")
    mount_rpm, mount_feed = _setting(plan, shop, "mount drill")
    tap_rpm, tap_feed = _setting(plan, shop, "tap drill")
    # Mounting holes: from the seat, full diameter mount_drill_past_mm past
    # the foot's underside into the notch's waste.
    mount_tip = -(foot + p["mount_drill_past_mm"]) - _point(d37)
    _agree(plan, "mount_tip_z_mm", mount_tip)
    # Tap drill: from the neck's face through O, full diameter
    # tap_drill_past_mm below it.
    tap_tip = -p["tap_drill_past_mm"] - _point(d7)
    _agree(plan, "tap_tip_z_mm", tap_tip)
    _agree(
        plan,
        "tap_reach_min_mm",
        neck + PLUG_TAP_LEAD_THREADS * UNC_1_4_20_PITCH_MM,
    )
    _agree(plan, "tap_reach_max_mm", neck + p["tap_overrun_max_mm"])
    for cut, depth in (
        ("mount drill", "{{cad.foot_underside_thickness_mm}}"),
        ("tap drill", "{{cad.neck_inner_face_thickness_mm}}"),
    ):
        op = _op_with_cut(plan, cut)[0]
        if op["hole_depth_mm"] != depth or op["peck"] != "none":
            raise ValueError(f"{op['tool']}: hole_depth_mm or peck is not the recipe's")

    # Vise: on edge on the 1 in pair, lying on the stacks, upright on the bed.
    jaw_h = p["vise_jaw_height_mm"]
    upright_grip = jaw_h - p["parallel_height_mm"]
    lying_grip = jaw_h - p["riser_height_mm"]
    _agree(plan, "upright_grip_mm", upright_grip)
    _agree(plan, "lying_grip_mm", lying_grip)
    if neck <= lying_grip + 1.0:
        raise ValueError("the neck's face does not clear the jaw tops")
    if high_level - lying_grip < 1.0:
        raise ValueError("the faces lying on the stacks do not stand above the jaws")
    t = p["parallel_thickness_mm"]
    jaw_w = p["vise_jaw_width_mm"]
    for key, along in (
        ("vise_blank_inset_mm", blank_max),
        ("vise_width_inset_mm", width),
    ):
        _agree(plan, key, -(jaw_w - along) / 2)
    # MB05: the jaws' left side foot_jaw_clear_mm inboard of the underside,
    # the seat that far past it; MB06: the jaws' right side
    # nose_jaw_back_mm back from the nose's centre, the longest part's sawn
    # end that far past it.
    jaw_left = foot + p["foot_jaw_clear_mm"]
    _agree(plan, "neck_overhang_mm", jaw_left)
    _agree(plan, "nose_overhang_mm", part_max - jaw_right)
    # The tap stack's ceiling: spindle-to-table maximum less the tool-change
    # clearance, the vise bed, the parallels, the foot's length standing up and
    # the collet's gauge, rounded down to .01 in.
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["parallel_height_mm"]
        - width
        - p["r8_collet_gauge_mm"]
    )
    _agree(plan, "tap_stack_max_mm", math.floor(stack / 0.254 + 1e-9) * 0.254)

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)). The raw faces: O is the
    # bar's lower edge; L low_skim_mm past the finished L, H the bar's
    # thickness past that; the seat's skim above the finished seat.
    raw_low = low - low_skim
    frames = {
        "width": _frame([outer, raw_low, seat + seat_skim], [0, -1, 0], [-1, 0, 0]),
        "seat": _frame([g["free"], raw_low, seat], [0, -1, 0], [0, 0, 1]),
        "notch": _frame([outer, raw_low, seat], [0, 0, 1], [0, 1, 0]),
        "low": _frame([outer, -low, seat], [0, 0, 1], [0, -1, 0]),
        "neck": _frame([outer, low, seat], [0, -1, 0], [-1, 0, 0]),
    }
    frames["nose"] = frames["neck"]
    long_max = blank_max - seat_skim
    stocks = {
        "width": ((0.0, blank_max), (-t_max, 0.0), (0.0, w_max)),
        "seat": ((-width, 0.0), (-t_max, 0.0), (-long_max, seat_skim)),
        "notch": ((0.0, width), (-long_max, 0.0), (0.0, t_max)),
        "low": ((-width, 0.0), (-long_max, 0.0), (0.0, high_level)),
        "neck": ((0.0, part_max), (-thick, 0.0), (0.0, neck_raw)),
        "nose": ((0.0, part_max), (-thick, 0.0), (0.0, neck)),
    }
    # Each frame puts the part where its stock says.
    for key, point, want in (
        ("width", [outer, low, seat], [seat_skim, -low_skim, 0.0]),
        ("seat", [g["free"], low, seat], [0.0, -low_skim, 0.0]),
        ("notch", [outer, low, seat], [0.0, 0.0, low_skim]),
        ("low", [outer, low, seat], [0.0, 0.0, thick]),
        ("neck", [g["inner"], -low, seat - tip], [tip, -thick, neck]),
    ):
        if not all(_close(a, b) for a, b in zip(_to(frames[key], point), want)):
            raise ValueError(
                f"{key}: the frame does not put the part where its stock is"
            )

    def xy(key: str, point: list[float]) -> list[float]:
        x, y, _z = _to(frames[key], point)
        return [_r(x), _r(y)]

    mount_xy = [xy("seat", hole["at"]) for hole in g["holes"]]
    tap_xy = xy("nose", g["tap"]["at"])
    holes = {"mount": mount_xy, "tap": [tap_xy]}

    def tool(key: str, rpm: float, feed: float, **extra: Any) -> dict[str, Any]:
        return {"tool": key, "rpm": rpm, "feed": feed, "plunge": feed, **extra}

    em_tool = tool("em-half", face_rpm, face_feed, dia=em, shape="endmill", flutes=3)

    def em_at(rpm: float, feed: float) -> dict[str, Any]:
        return {**em_tool, "rpm": rpm, "feed": feed, "plunge": feed}

    deep_tool = em_at(deep_rpm, deep_feed)
    wall_tool = em_at(wall_rpm, wall_feed)
    chart_tool = em_at(chart_rpm, chart_feed)
    spot_tool = tool(
        "spot",
        spot_rpm,
        spot_feed,
        dia=CENTRE_DRILL["body_mm"],
        shape="drill",
        tip_angle=CENTRE_DRILL["point_deg"],
    )

    def drill_tool(key: str, dia: float, rpm: float, feed: float) -> dict[str, Any]:
        return tool(key, rpm, feed, dia=dia, shape="drill", tip_angle=DRILL_POINT_DEG)

    def run(x: tuple[float, float]) -> tuple[float, float]:
        return (x[0] - r - APPROACH_MM, x[1] + r + APPROACH_MM)

    edge_ys = _stations((-t_max, 0.0), r, skim_step)
    seat_ys = _stations((-t_max, 0.0), r, skim_step)
    long_ys = _stations((-long_max, 0.0), r, skim_step)
    neck_ys = _stations((-thick, 0.0), r, step_max)

    # MB03: H faced across the whole blank, then the notch's upper half,
    # then the foot's wall; MB04: L faced, then the notch's lower half
    # through MB03's floor, then the foot's wall. The stations mirror in X
    # (O at X0 on the left in MB03, on the right in MB04); the Y lines are
    # the same (the seat at the fixed jaw).
    notch_top = t_max
    high_lines = _face([high_level], notch_top, run((0.0, width)), long_ys)
    air_x = _r(width + r + APPROACH_MM)
    notch_lines = _notch(notch_top, high_level, notch_levels, notch_xs, foot_y, waste_y, r)
    foot_lines = _foot_wall(notch_top, split, foot_ys, air_x, notch_xs[-1])
    low_lines = _face([thick], high_level, run((-width, 0.0)), long_ys)
    through_xs = [_r(-x) for x in notch_xs]
    through_lines = _notch(
        high_level, thick, through_levels, through_xs, foot_y, waste_y, r
    )
    foot_through_lines = _foot_wall(high_level, through, foot_ys, through_xs[-1], -air_x)

    # MB05: each level entered from beside the part over the fixed jaw, at
    # the nose end, then zigzag X passes to the foot's station and back.
    neck_top = neck_raw + r
    neck_in = _r(part_max - r + FACE_OVERHANG_MM)
    # The offcut spacer of Setups 7 and 8 stands on the vise bed, F to O up,
    # a sawn face flush with the jaws' far end, past the stacks' or the
    # parallels' ends: offcut_long along the jaws, width tall.
    offcut_long = blank_max - seat_skim - part_min - p["kerf_in"] * IN
    neck_stack_end = jaw_left + IN / 2 + PARALLEL_LENGTH_MM
    nose_parallel_start = jaw_right - PARALLEL_LENGTH_MM
    if (
        neck_stack_end > jaw_left + jaw_w - offcut_long
        or nose_parallel_start < jaw_right - jaw_w + offcut_long
    ):
        raise ValueError("the offcut has no room on the bed beside the supports")
    foot_x = _r(foot + r)
    side_y = _r(r + APPROACH_MM)
    nclear = _r(neck_top + CLEAR_MM)
    # MB05 and MB06 stand the part on edge: the foot rises to the part's
    # width above O. Every section opens and closes at ``travel``, above the
    # foot and every jaw, so no XY rapid after an M6 can reach either. At the
    # neck's last level the end mill stands beside the foot: its projection
    # out of the collet keeps the collet above the foot's top, and a 3 in
    # end mill still has 1 in in the collet.
    travel = _r(width + CLEAR_MM)
    projection = p["neck_mill_projection_min_mm"]
    if projection < width - neck + CLEAR_MM:
        raise ValueError(
            "neck_mill_projection_min_mm: the collet reaches the foot at the "
            "neck's last level"
        )
    if projection > p["half_mill_oal_mm"] - IN:
        raise ValueError(
            "neck_mill_projection_min_mm: less than 1 in of the end mill left "
            "in the collet"
        )
    # After each level's zigzag, one pass along the foot's underside at its
    # station, from beside L to beside H (climb: the foot on the cutter's
    # right), squares the corner across the whole width.
    far_y = _r(-thick - r - APPROACH_MM)
    neck_lines: list[str] = [
        f"G0 Z{travel:.3f}",
        f"G0 X{neck_in:.3f} Y{side_y:.3f}",
    ]
    for z in neck_levels:
        neck_lines += [
            f"G0 Z{nclear:.3f}",
            f"G0 X{neck_in:.3f} Y{side_y:.3f}",
            f"G0 Z{_r(neck_top + SAFE_MM):.3f}",
            f"G1 Z{_r(z):.3f} F{{feed}}",
            f"G1 Y{neck_ys[0]:.3f} F{{feed}}",
        ]
        for k, y in enumerate(neck_ys):
            if k:
                neck_lines.append(f"G1 Y{y:.3f} F{{feed}}")
            neck_lines.append(f"G1 X{foot_x if k % 2 == 0 else neck_in:.3f} F{{feed}}")
        if len(neck_ys) % 2:
            neck_lines.append(f"G1 X{neck_in:.3f} F{{feed}}")
        neck_lines += [
            f"G1 Y{side_y:.3f} F{{feed}}",
            f"G0 Z{nclear:.3f}",
            f"G0 X{foot_x:.3f}",
            f"G0 Z{_r(neck_top + SAFE_MM):.3f}",
            f"G1 Z{_r(z):.3f} F{{feed}}",
            f"G1 Y{far_y:.3f} F{{feed}}",
        ]
    neck_lines.append(f"G0 Z{travel:.3f}")

    # MB06: the nose outline (machine XY, climb: round the outside
    # clockwise), from beside L, round the nose, to beside H; the leads run
    # nose_lead_mm along each side back from the tangent points.
    cx, cy = tap_xy
    elements = [
        {"name": "L side", "start": [cx - lead, cy + radius], "end": [cx, cy + radius]},
        {
            "name": "nose, L half",
            "start": [cx, cy + radius],
            "end": [cx + radius, cy],
            "centre": [cx, cy],
        },
        {
            "name": "nose, H half",
            "start": [cx + radius, cy],
            "end": [cx, cy - radius],
            "centre": [cx, cy],
        },
        {"name": "H side", "start": [cx, cy - radius], "end": [cx - lead, cy - radius]},
    ]
    for element in elements:
        element["tol"] = OUTLINE_TOL_MM
    nose_bottom = neck - nose_depth
    # The rough rings, outermost first, every level each; the finish
    # passes, outermost first, at full depth.
    step_n, fin_n = p["nose_rough_step_mm"], p["nose_finish_step_mm"]
    rough_passes = [
        {"offset": r + stock_n + k * step_n, "levels": [_r(z) for z in rough_levels]}
        for k in range(rings - 1, -1, -1)
    ]
    finish_passes = [
        {"offset": r + k * fin_n, "levels": [_r(nose_bottom)]}
        for k in range(finishes - 1, -1, -1)
    ]
    # Between the nose's passes the cutter clears the jaw tops too.
    nose_clear = _r(max(upright_grip, neck) + CLEAR_MM)

    def nose_lines(passes: list[dict[str, Any]]) -> list[str]:
        """A section of nose passes, opened and closed at ``travel``."""
        first = passes[0]["offset"]
        lines: list[str] = [
            f"G0 Z{travel:.3f}",
            f"G0 X{_r(cx - lead):.3f} Y{_r(cy + radius + first):.3f}",
        ]
        for pass_ in passes:
            o = pass_["offset"]
            for z in pass_["levels"]:
                lines += [
                    f"G0 Z{nose_clear:.3f}",
                    f"G0 X{_r(cx - lead):.3f} Y{_r(cy + radius + o):.3f}",
                    f"G0 Z{_r(neck + SAFE_MM):.3f}",
                    f"G1 Z{z:.3f} F{{feed}}",
                    f"G1 X{_r(cx):.3f} F{{feed}}",
                    f"G2 X{_r(cx + radius + o):.3f} Y{_r(cy):.3f} I0.000 J{_r(-(radius + o)):.3f} F{{feed}}",
                    f"G2 X{_r(cx):.3f} Y{_r(cy - radius - o):.3f} I{_r(-(radius + o)):.3f} J0.000 F{{feed}}",
                    f"G1 X{_r(cx - lead):.3f} F{{feed}}",
                ]
        return lines + [f"G0 Z{travel:.3f}"]

    # The end mill set half_mill_projection_mm out (MB01-MB04 and, at the
    # shortest, MB06): its collet's nose clears the stock's top and the jaw
    # tops at each program's deepest end-mill cut. MB05's longer set is
    # checked above.
    for program, deepest, highest in (
        ("MB01_width", width, max(w_max, upright_grip)),
        ("MB02_seat", 0.0, seat_skim),
        ("MB03_notch", split, max(t_max, lying_grip)),
        ("MB04_low", through, max(high_level, lying_grip)),
        ("MB06_nose", nose_bottom, max(neck, upright_grip)),
    ):
        if deepest + p["half_mill_projection_mm"] < highest + CLEAR_MM:
            raise ValueError(
                f"{program}: the end mill's collet would reach the part or the jaws"
            )

    def from_travel(lines: list[str]) -> list[str]:
        """A hole section opened over the tap at ``travel`` and closed there."""
        return [
            f"G0 Z{travel:.3f}",
            f"G0 X{tap_xy[0]:.3f} Y{tap_xy[1]:.3f}",
            *lines,
            f"G0 Z{travel:.3f}",
        ]

    jobs = [
        {
            **em_tool,
            "frame": "width",
            "label": "width",
            "stock": stocks["width"],
            "ops": [
                [
                    "width",
                    "face F to the foot's length",
                    _face(width_levels, w_max, run((0.0, blank_max)), edge_ys),
                ]
            ],
        },
        {
            **em_tool,
            "frame": "seat",
            "label": "seat",
            "stock": stocks["seat"],
            "ops": [
                [
                    "seat",
                    "face the seat",
                    _face([0.0], seat_skim, run((-width, 0.0)), seat_ys),
                ]
            ],
        },
        {
            **spot_tool,
            "frame": "seat",
            "label": "mount spot",
            "stock": stocks["seat"],
            "ops": [
                [
                    "mount_spot",
                    "spot the mounting holes",
                    _plunged(mount_xy, 0.0, -spots["mount spot"], CLEAR_MM),
                ]
            ],
        },
        {
            **drill_tool("drill-37", d37, mount_rpm, mount_feed),
            "frame": "seat",
            "label": "mount drill",
            "stock": stocks["seat"],
            "ops": [
                [
                    "mount_drill",
                    "drill the mounting holes #37",
                    _plunged(mount_xy, 0.0, mount_tip, CLEAR_MM),
                ]
            ],
        },
        *(
            {
                **section_tool,
                "frame": frame,
                "label": key.replace("_", " "),
                "stock": stocks[frame],
                "ops": [[key, label, lines]],
            }
            for section_tool, frame, key, label, lines in (
                (em_tool, "notch", "high_side", "face H", high_lines),
                (deep_tool, "notch", "notch", "mill the notch", notch_lines),
                (wall_tool, "notch", "foot_wall", "the foot's wall", foot_lines),
                (em_tool, "low", "low_side", "face L", low_lines),
                (
                    deep_tool,
                    "low",
                    "notch_through",
                    "mill the notch through",
                    through_lines,
                ),
                (
                    wall_tool,
                    "low",
                    "foot_wall_through",
                    "the foot's wall through",
                    foot_through_lines,
                ),
                (
                    chart_tool,
                    "neck",
                    "neck",
                    "face the neck, square the corner",
                    neck_lines,
                ),
                (
                    deep_tool,
                    "nose",
                    "nose_rough",
                    "rough the nose",
                    nose_lines(rough_passes),
                ),
                (
                    wall_tool,
                    "nose",
                    "nose_finish",
                    "finish the nose",
                    nose_lines(finish_passes),
                ),
            )
        ),
        {
            **spot_tool,
            "frame": "nose",
            "label": "tap spot",
            "stock": stocks["nose"],
            "ops": [
                [
                    "tap_spot",
                    "spot the lever tap",
                    from_travel(
                        _spot(tap_xy, neck, neck - spots["tap spot"], nose_clear)
                    ),
                ]
            ],
        },
        {
            **drill_tool("drill-7", d7, tap_rpm, tap_feed),
            "frame": "nose",
            "label": "tap drill",
            "stock": stocks["nose"],
            "ops": [
                [
                    "tap_drill",
                    "drill the lever tap #7",
                    from_travel(_plunged([tap_xy], neck, tap_tip, nose_clear)),
                ]
            ],
        },
    ]
    manual = {
        "lever_tap": {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": "SPINDLE STAYS OFF. NEXT: 1/4-20 TAP IN THE NOSE HOLE",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{tap_xy[0]:.3f} Y{tap_xy[1]:.3f}",
                "(1/4-20 TAP IN THE NOSE HOLE. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND TO THE NOTED DRO Z, READ WITH THE POINT PUSHED HOME. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": tap_xy,
        }
    }

    # Keep-outs: the jaws beside the gripped faces from the parallels' or
    # stacks' top to the jaw top, across the jaw width; the parallels under
    # the gripped faces' edges.
    def jaws(
        z_top: float, x: tuple[float, float], y: tuple[float, float]
    ) -> list[dict[str, Any]]:
        return [
            _box("moving jaw", x, (y[0] - JAW_DEPTH_MM, y[0]), z_top),
            _box("fixed jaw", x, (y[1], y[1] + JAW_DEPTH_MM), z_top),
        ]

    def centred(x: tuple[float, float], length: float) -> tuple[float, float]:
        mid = (x[0] + x[1]) / 2
        return (mid - length / 2, mid + length / 2)

    def parallels(
        z_top: float, x: tuple[float, float], y: tuple[float, float]
    ) -> list[dict[str, Any]]:
        return [
            _box("moving-jaw parallels", x, (y[0], y[0] + t), z_top),
            _box("fixed-jaw parallels", x, (y[1] - t, y[1]), z_top),
        ]

    # Gripped across the length (MB03-MB04): the fixed jaw on the seat; one
    # stack against it under the seat end, the other under the sawn end, its
    # outer face flush with it; the rod between the sawn end and the moving
    # jaw at the part's mid-height, wherever the blank's length puts them.
    near_end = -(blank_min - seat_skim)
    rod_d = p["rod_dia_mm"]
    far_end = -long_max - rod_d - JAW_DEPTH_MM

    def across(
        z_top: float, x: tuple[float, float], part_h: float
    ) -> list[dict[str, Any]]:
        span = centred(x, jaw_w)
        return [
            _box("fixed jaw", span, (0.0, JAW_DEPTH_MM), z_top),
            _box("moving jaw", span, (far_end, near_end - rod_d), z_top),
            _box("rod", span, (-long_max - rod_d, near_end), part_h / 2 + rod_d / 2),
            _box("fixed-jaw stack", centred(x, PARALLEL_LENGTH_MM), (-t, 0.0), 0.0),
            _box(
                "sawn-end stack",
                centred(x, PARALLEL_LENGTH_MM),
                (-long_max, near_end + t),
                0.0,
            ),
        ]

    neck_jaws = (jaw_left, jaw_left + jaw_w)
    nose_jaws = (jaw_right - jaw_w, jaw_right)
    keep = {
        "width": jaws(upright_grip, centred((0.0, blank_max), jaw_w), (-t_max, 0.0))
        + parallels(0.0, centred((0.0, blank_max), PARALLEL_LENGTH_MM), (-t_max, 0.0)),
        # Upright on the vise bed: the jaw tops jaw_h above the shortest
        # blank's lower end.
        "seat": jaws(
            jaw_h - (blank_min - seat_skim),
            centred((-width, 0.0), jaw_w),
            (-t_max, 0.0),
        ),
        "notch": across(lying_grip, (0.0, width), p["bar_thickness_max_mm"]),
        "low": across(lying_grip, (-width, 0.0), high_level),
        # On edge (MB05, MB06) the foot stands the part's width tall.
        "neck": [_box("foot", (0.0, foot), (-thick, 0.0), width)]
        + jaws(lying_grip, neck_jaws, (-thick, 0.0))
        + [
            _box(
                "offcut",
                (neck_jaws[1] - offcut_long, neck_jaws[1]),
                (-thick, 0.0),
                width - p["riser_height_mm"],
            )
        ]
        # The stacks' left ends .50 inside the jaws' left side.
        + parallels(
            0.0,
            (jaw_left + IN / 2, neck_stack_end),
            (-thick, 0.0),
        ),
        "nose": [_box("foot", (0.0, foot), (-thick, 0.0), width)]
        + jaws(upright_grip, nose_jaws, (-thick, 0.0))
        + [
            _box(
                "offcut",
                (nose_jaws[0], nose_jaws[0] + offcut_long),
                (-thick, 0.0),
                width - p["parallel_height_mm"],
            )
        ]
        + parallels(0.0, (nose_parallel_start, jaw_right), (-thick, 0.0)),
    }

    tn = numbers
    expect: list[list[Any]] = []

    def face_checks(levels, top, y, span, frame, step) -> list[list[Any]]:
        return [
            ["rapids_clear", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            *[
                [
                    "face_passes",
                    {
                        "z": _r(z),
                        "y": list(y),
                        "max_engagement": step,
                        "radius": r,
                        "span": span,
                        "overhang": FACE_OVERHANG_MM,
                    },
                ]
                for z in levels
            ],
            ["keep_out", {"radius": r, "boxes": keep[frame]}],
        ]

    def hole_checks(key, frame, top, bottom, radius) -> list[list[Any]]:
        return [
            ["holes", {"centres": holes[key], "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": top, "open_holes": holes[key]}],
            ["vertical_below_top", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": radius, "boxes": keep[frame]}],
        ]

    def speeds(*rpms: float) -> list[float]:
        """The speeds a tool's sections set in order, a repeat of the running
        one dropped (it carries on, no stop)."""
        return [s for k, s in enumerate(rpms) if not k or s != rpms[k - 1]]

    def single(name, top, z_min, checks, rpms, change_top=None) -> list[list[Any]]:
        """One end mill, a section per speed in ``rpms`` (an M0 stop at each
        change). ``change_top``: what an XY rapid after the M6 must clear,
        when it stands higher than the stock top (the foot, MB05)."""
        set_speeds = speeds(*rpms)
        return [
            [
                name,
                "tool_changes",
                {
                    "z_top": top if change_top is None else change_top,
                    "tools": [tn["em-half"]],
                    "loads_first": True,
                },
            ],
            [name, "spindle", {"rpm": [set_speeds]}],
            [name, "pauses", {"z_top": top, "count": len(set_speeds) - 1}],
            [name, "depth", {"z_min": _r(z_min)}],
            *[[name, check, kwargs] for check, kwargs in checks],
        ]

    expect += single(
        "MB01_width",
        w_max,
        width,
        face_checks(width_levels, w_max, (-t_max, 0.0), blank_max, "width", skim_step),
        [face_rpm],
    )

    name = "MB02_seat"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": seat_skim,
                "tools": [tn["em-half"], tn["spot"], tn["drill-37"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[face_rpm], [spot_rpm], [mount_rpm]]}],
        [name, "pauses", {"z_top": seat_skim, "count": 0}],
        [name, "depth", {"z_min": _r(mount_tip)}],
    ]
    for k, checks in enumerate(
        (
            [
                ["depth", {"z_min": 0.0}],
                *face_checks([0.0], seat_skim, (-t_max, 0.0), width, "seat", skim_step),
            ],
            hole_checks(
                "mount", "seat", 0.0, -spots["mount spot"], CENTRE_DRILL["body_mm"] / 2
            ),
            hole_checks("mount", "seat", 0.0, mount_tip, d37 / 2),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    def notch_checks(frame, top, surface, bottom, xs, x_air, sign) -> list[list[Any]]:
        """The face at ``surface``, then the notch: its floor cleared from
        the neck's wall to F and from the foot to the notch's end, each
        station's level pass meeting no more than the stations' step; the
        foot wall's passes meet only the cusps the stations left, climb."""
        # The neck's wall meets the foot and the waste in the cutter's
        # radius (MB05 squares the foot's corner); every other edge is sharp.
        mid_x, mid_y = (neck_raw + width) / 2, (-foot - notch_end) / 2
        points = [
            [_r(sign * x), _r(y)]
            for x, y in (
                (neck_raw + 0.1, mid_y),
                (mid_x, -foot - 0.1),
                (mid_x, mid_y),
                (mid_x, -notch_end + 0.1),
                (width - 0.1, -foot - 0.1),
                (width - 0.1, mid_y),
                (width - 0.1, -notch_end + 0.1),
            )
        ]
        lo, hi = sorted((xs[-1], x_air))
        return [
            *face_checks([surface], top, (-long_max, 0.0), width, frame, skim_step),
            ["cleared", {"points": points, "radius": r, "z": _r(bottom)}],
            [
                "engagement",
                {
                    "stock": stocks[frame],
                    "radius": r,
                    "max_radial": notch_step,
                    "z": _r(bottom),
                    "window": [sorted((xs[0], xs[-1])), [_r(waste_y), _r(foot_y)]],
                    "min_length": (foot_y - waste_y) / 2,
                },
            ],
            [
                "engagement",
                {
                    "stock": stocks[frame],
                    "radius": r,
                    "max_radial": p["foot_wall_woc_mm"],
                    "z": _r(bottom),
                    "window": [[lo, hi], [foot_ys[0], foot_ys[-1]]],
                    "min_length": (hi - lo) / 2,
                    "side": "climb",
                },
            ],
        ]

    expect += single(
        "MB03_notch",
        t_max,
        split,
        notch_checks("notch", t_max, high_level, split, notch_xs, air_x, 1.0),
        [face_rpm, deep_rpm, wall_rpm],
    )
    expect += single(
        "MB04_low",
        high_level,
        through,
        notch_checks("low", high_level, thick, through, through_xs, -air_x, -1.0),
        [face_rpm, deep_rpm, wall_rpm],
    )
    corner_points = [[_r(foot + 0.1), _r(y)] for y in (-0.1, -thick / 2, -thick + 0.1)]
    expect += single(
        "MB05_neck",
        neck_top,
        neck,
        [
            ["rapids_clear", {"z_top": neck_top}],
            ["air_feed", {"z_top": neck_top}],
            *[
                [
                    "face_passes",
                    {
                        "z": _r(z),
                        "y": [-thick, 0.0],
                        "max_engagement": neck_woc,
                        "radius": r,
                        "span": neck_in - foot_x - 1.0,
                        "overhang": FACE_OVERHANG_MM,
                    },
                ]
                for z in neck_levels
            ],
            ["cleared", {"points": corner_points, "radius": r, "z": _r(neck)}],
            ["keep_out", {"radius": r, "boxes": keep["neck"]}],
        ],
        [chart_rpm],
        change_top=width,
    )

    name = "MB06_nose"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": width,
                "tools": [tn["em-half"], tn["spot"], tn["drill-7"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [speeds(deep_rpm, wall_rpm), [spot_rpm], [tap_rpm]]}],
        [name, "pauses", {"z_top": neck, "count": len(speeds(deep_rpm, wall_rpm)) - 1}],
        [name, "depth", {"z_min": _r(tap_tip)}],
    ]
    for k, checks in enumerate(
        (
            [
                ["depth", {"z_min": _r(nose_bottom)}],
                [
                    "outline",
                    {
                        "elements": elements,
                        "passes": rough_passes + finish_passes,
                        "z_top": neck,
                    },
                ],
                ["rapids_clear", {"z_top": neck}],
                ["air_feed", {"z_top": neck}],
                ["keep_out", {"radius": r, "boxes": keep["nose"]}],
            ],
            hole_checks(
                "tap",
                "nose",
                neck,
                neck - spots["tap spot"],
                CENTRE_DRILL["body_mm"] / 2,
            ),
            hole_checks("tap", "nose", neck, tap_tip, d7 / 2),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    name = "MB07_lever_tap"
    expect += [
        [
            name,
            "tap_stop",
            {"tool": tn["tap-guide"], "at": tap_xy, "machine_top": MACHINE_Z_TOP_MM},
        ],
        [name, "air_feed", {"z_top": neck}],
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
            doc,
            f"Magnifying bracket {key}",
            ctx["step"],
            frame["origin"],
            frame["axes"],
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
