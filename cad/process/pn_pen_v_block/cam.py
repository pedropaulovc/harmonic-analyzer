"""FreeCAD CAM recipe for MHA-PN-05, the pen V block.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The block's sizes come
from the feature export (its faces, the neck steps, the V groove, the relief
slot, the pivot bore and the set-screw tap); the blank, the skims, face and
cut levels, spots, pecks, the #30 drill's run past the slot roof and the vise
holds from ``plan.toml`` ``[parameters]``; cutter diameters, the chamfer
mill's cone, speeds and feeds from the shop (``shop/``). Every path is
written here (``rt.custom``): straight lines a recipe can state exactly.
Typed here, because neither record carries them: the #2 centre drill's
catalogue geometry (it sets the spot depth), the twist drills' 118° point,
the approach, safe and clearance heights, the face overhang, the vise jaws'
depth and the parallels' length (keep-out shapes only), and the hand tap's
chamfer (a plug tap's three to five threads).

Route (plan text in ``plan.toml``): one blank of the 3/4 x 1-1/4 in C360
bar, about 1.1 long. Upright on 1 in parallels: VB01 faces the paper end P,
VB02 (turned over) faces the far end to the length. Lying on the 1/2 in +
5/8 in parallel stacks: VB03 skims the back face and cuts the back neck
step, VB04 (back down) faces the front to the depth and cuts the front neck
step, VB05 (bottom up) skims the bottom face B, mills the relief slot, the V
groove and their corners, VB06 (B down) faces the top to the height, then
drills the pivot bore #30 (owner ruling 2026-11-24, fit audit question 20)
and chamfers it down into the slot and breaks the
neck's two top edges with the same chamfer mill, VB07 (front
up) drills the set-screw tap hole into the bore and VB08 is its hand-tap
stop.

Work frames (G54), each set in its setup; X0 is always the paper end P, the
part to +X:
- VB01: X0 Y0 the blank's axis, Z0 the faced paper end.
- VB02: X0 Y0 the blank's axis, Z0 the parallels' top (P).
- VB03: Y0 the fixed jaw (the bar's top face against it), Z0 the stacks'
  top (the bar's raw front edge).
- VB04: Y0 the fixed jaw (the bar's bottom face), Z0 the stacks' top (the
  back face).
- VB05: Y0 the fixed jaw (the back face), Z0 the stacks' top (the top face).
- VB06: Y0 the fixed jaw (the front face), Z0 the stacks' top (B).
- VB07/VB08: Y0 the fixed jaw (B), Z0 the stacks' top (the back face).

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock or in cleared air at the cutting feed, real G0
above the stock. The set screw is tapped by hand (FluidNC cannot rigid-tap;
owner, Pedro, 2026-11-17), the T-handle wrench's centre hole on the spring
point of the Fisher tap guide in the 1/2 in R8 collet (owner, Pedro,
2026-11-21: "use
https://littlemachineshop.com/products/tap-guide-fisher?variant=45472915226805
on r8 0.5 collet"), spindle off, the operator jogging Z down to push the
point home; FluidNC refuses jogs while an M0 holds the program, so the tap
stop is a file of its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "pn_pen_v_block"
COMMENT = "MHA-PN-05 pen V block"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("VB01_paper_end", ("paper_end",)),
    ("VB02_length", ("far_end",)),
    ("VB03_back", ("back",)),
    ("VB04_front", ("front",)),
    ("VB05_bottom", (("bottom",), ("v_groove",), ("corners",))),
    (
        "VB06_top_bore",
        (
            ("top",),
            ("bore_spot",),
            ("bore_drill",),
            ("bore_chamfer", "neck_breaks"),
        ),
    ),
    ("VB07_set_screw", (("tap_spot",), ("tap_drill",))),
    ("VB08_set_screw_tap", ("tap",)),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held, and the tap file before its retract
# (the tap guide).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the tap, the saw and the files are not).
CAM_TOOLS = (
    "em-half",
    "chamfer",
    "em-eighth",
    "spot",
    "drill-30",
    "drill-43",
    "tap-guide",
)
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
# Hand taps' chamfers (ASME B94.9): a plug tap's three to five threads, a
# bottoming tap's one to two. The owned plug tap's chamfer is not on record,
# so its worst five would leave tapered thread where the set screw must run
# full to the bore: the plug tap starts the thread and the bottoming tap (to
# buy) finishes it to the same reach, which keeps the bottoming tap's worst
# two threads past the bore's farther near-wall (its smallest size) and
# stops either tap's point short of the far wall.
BOTTOMING_CHAMFER_PITCHES = 2
TAP_FAR_WALL_CLEAR_MM = 0.25
# A tap file's first motion: G53 G0 to machine Z0, the homed top. FluidNC
# sets an axis's machine position to its homing mpos_mm (default 0) after
# homing, and Z homes up (cad/config/shop-equipment/
# cnc.pm-30mv-controller: switches on all three axes); the owner (Pedro)
# confirmed it, answered in person 2026-11-21 (cnc rulings record): machine
# Z = 0 is the top of travel after homing.
MACHINE_Z_TOP_MM = 0.0
# Face and slot passes start and finish with the cutter this far clear of
# the part's ends, so every plunge and stepover link is in the air beside it.
APPROACH_MM = 2.54
# Faces reach at least this far past the faces the jaws grip.
FACE_OVERHANG_MM = 0.5
# The neck breaks' entry: the chamfer mill's point ramps down this far along
# X in the air beside the paper end to each pass's level.
BREAK_RAMP_MM = 1.0
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped face; the
# parallels' length (4 in, LMS 6745, shop-equipment fixtures.parallels-lms-6745).
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 4 * IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# Model agreement between two exported values (they share CAD constants).
MODEL_TOL_MM = 1e-3
# The 1/8 in end mill's slotting limit the plan cites (Harvey Tool miniature
# square end mills, series 720xx, speeds and feeds table, Brass row: axial
# depth .35 × its diameter): it takes the slot's step corners, buried at the
# step, in levels no deeper.
SLOT_AXIAL_MAX = 0.35
# The V's flat is swept by the chamfer mill's pointed tip at the flat's
# level (owner ruling 2026-11-23, tool audit Q9: no 5/64 cutter). A 90°
# cone's two neighbouring tip passes leave a ridge half their spacing high,
# so every point of the flat lies within this of a tip pass: its ridges
# stand at most .001 in, a tenth of the flat's printed .XX band.
V_FLAT_RIDGE_MAX_MM = 0.0254


def _plan_operations(plan: dict[str, Any]):
    for setup in plan["setups"]:
        yield from setup.get("operations", ())


def _op_with_cut(
    plan: dict[str, Any], name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    for op in _plan_operations(plan):
        cuts = op.get("milling_cuts", ())
        for cut in cuts if isinstance(cuts, list) else ():
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
    """(rpm, mm/min) of the shop setting the operation holding ``cut`` names:
    chip load × flutes × rpm, or its literal ``in/min`` feed. A cut that
    states its own rpm or feed must agree with the setting."""
    op, record_cut = _op_with_cut(plan, cut)
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    if "chip_load_mm_per_tooth" in record:
        feed = record["chip_load_mm_per_tooth"] * record["flutes"] * rpm
    else:
        match = re.fullmatch(r"([\d.]+) in/min", record["feed"])
        if not match:
            raise ValueError(f"setting {op['settings']}: feed {record['feed']!r}")
        feed = float(match.group(1)) * IN
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


def _step(
    levels: list[float], top: float, x: float, y: tuple[float, float]
) -> list[str]:
    """A neck step: one Y pass per level at cutter-centre X ``x``, from
    beside the part to beside it on the other side, alternating direction
    level to level; the cutter's side cuts the step face, its end the floor."""
    clear = _r(top + CLEAR_MM)
    ends = (_r(y[0]), _r(y[1]))
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{_r(x):.3f} Y{ends[0]:.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
    ]
    for k, z in enumerate(levels):
        lines += [
            f"G1 Z{_r(z):.3f} F{{feed}}",
            f"G1 Y{ends[(k + 1) % 2]:.3f} F{{feed}}",
        ]
    return lines + [f"G0 Z{clear:.3f}"]


def _slot(
    levels: list[float], top: float, x: tuple[float, float], ys: list[float]
) -> list[str]:
    """The relief slot, open at the far end: per level, passes along X from
    beside the far end (``x[1]``) in to the step (``x[0]``) and out, stepping
    over along the step face, the passes' order reversed level to level;
    every plunge beside the far end."""
    clear = _r(top + CLEAR_MM)
    x_in, x_out = _r(x[0]), _r(x[1])
    order = list(ys)
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{x_out:.3f} Y{_r(order[0]):.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
    ]
    for z in levels:
        lines.append(f"G1 Z{_r(z):.3f} F{{feed}}")
        inside = False
        for k, y in enumerate(order):
            if k:
                lines.append(f"G1 Y{_r(y):.3f} F{{feed}}")
            lines.append(f"G1 X{x_out if inside else x_in:.3f} F{{feed}}")
            inside = not inside
        if inside:
            lines.append(f"G1 X{x_out:.3f} F{{feed}}")
        order.reverse()
    return lines + [f"G0 Z{clear:.3f}"]


def _corner(
    levels: list[float], top: float, path: list[tuple[float, float]]
) -> list[str]:
    """An inside corner left by a larger cutter: the ``path`` (cutter-centre
    points along the side wall, then the step face, all in cleared air at
    their ends) at each level, its direction reversed level to level."""
    clear = _r(top + CLEAR_MM)
    route = [(_r(x), _r(y)) for x, y in path]
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{route[0][0]:.3f} Y{route[0][1]:.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
    ]
    for z in levels:
        lines.append(f"G1 Z{_r(z):.3f} F{{feed}}")
        for x, y in route[1:]:
            lines.append(f"G1 X{x:.3f} Y{y:.3f} F{{feed}}")
        route.reverse()
    return lines + [f"G0 Z{clear:.3f}"]


def _breaks(
    ys: list[float], levels: list[float], top: float, x: tuple[float, float]
) -> list[str]:
    """Edge breaks along X: for each edge (its Y) and level (the point's
    depth under ``top``), the point ramped down in the air beside the part
    to ``x[0]``, fed along to the stop ``x[1]`` and fed straight up out of
    the cut there (a rapid would leave the cut below the top), then back
    above the part.  The ramp, not a plunge: the section's hole check reads
    every straight Z descent as a hole."""
    clear, r_plane = _r(top + CLEAR_MM), _r(top + SAFE_MM)
    lines = [f"G0 Z{clear:.3f}"]
    for y in ys:
        for t in levels:
            lines += [
                f"G0 X{_r(x[0] - BREAK_RAMP_MM):.3f} Y{_r(y):.3f}",
                f"G0 Z{r_plane:.3f}",
                f"G1 X{_r(x[0]):.3f} Z{_r(top - t):.3f} F{{feed}}",
                f"G1 X{_r(x[1]):.3f} F{{feed}}",
                f"G1 Z{r_plane:.3f} F{{feed}}",
                f"G0 Z{clear:.3f}",
            ]
    return lines


def _v_levels(depth: float, max_step: float) -> list[float]:
    """The V's tip depths below the bottom face, equal steps to ``depth``."""
    n = math.ceil(depth / max_step - 1e-9)
    return [depth * (k + 1) / n for k in range(n)]


def _v_offsets(half: float, max_step: float) -> list[float]:
    """Lateral tip offsets from the V's centre, equally spaced from ``-half``
    to ``half``, no further apart than ``max_step``."""
    n = max(1, math.ceil(2 * half / max_step - 1e-9))
    return [-half + 2 * half * j / n for j in range(n + 1)]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The block's faces and features from the export, each checked against
    the frame the recipe assumes: X from the paper end along the block, Y up
    from the bottom face, Z across the depth with the body's front face at
    its low end; the V, the relief slot and the pivot bore centred on the
    depth; the set screw from the front face into the bore."""
    f = features["features"]

    def plane(name: str, axis: str) -> float:
        p = f[name]["plane"]
        if p["axis"] != axis:
            raise ValueError(f"{name}: expected a plane square to model {axis.upper()}")
        return float(p["value"])

    def close(a: float, b: float, what: str) -> None:
        if not math.isclose(a, b, abs_tol=MODEL_TOL_MM):
            raise ValueError(f"{what}: {a:.4f} is not {b:.4f}")

    if plane("paper_end", "x") != 0.0 or plane("bottom_face", "y") != 0.0:
        raise ValueError("paper_end and bottom_face: expected at model X0 and Y0")
    length = plane("far_end", "x")
    close(length, f["far_end"]["length_nominal"], "far end")
    height = plane("top_face", "y")
    close(height, f["top_face"]["height_nominal"], "top face")
    z0, z1 = plane("body_front", "z"), plane("body_back", "z")
    close(z1 - z0, f["body_back"]["depth_nominal"], "body depth")
    neck0, neck1 = plane("neck_front", "z"), plane("neck_back", "z")
    close(neck0 - z0, f["neck_front"]["station_nominal"], "front neck step")
    close(neck1 - z0, f["neck_back"]["station_nominal"], "back neck step")
    steps = plane("neck_steps", "x")
    close(steps, f["neck_steps"]["station_nominal"], "neck steps")

    v = f["v_groove"]
    if v["axis"] != [1.0, 0.0, 0.0] or v["length_to"] != "neck_steps":
        raise ValueError("v_groove: expected along X from the paper end to the steps")
    if not math.isclose(v["flank_angle_deg_nominal"], 45.0) or not math.isclose(
        v["included_angle_deg"], 90.0
    ):
        raise ValueError("v_groove: the recipe cuts a 90° V with the 90° chamfer mill")
    vz0 = z0 + v["mouth_near_nominal"]
    vz1 = z0 + v["mouth_far_nominal"]
    mouth_half = (vz1 - vz0) / 2
    flat_half = v["flat_width_nominal"] / 2
    v_depth = v["flat_height_ref"]
    close(mouth_half - flat_half, v_depth, "V flat height (45° flanks)")

    rel = f["relief"]
    if rel["axis"] != [1.0, 0.0, 0.0]:
        raise ValueError("relief: expected along X")
    rz0 = z0 + rel["near_wall_nominal"]
    rz1 = z0 + rel["far_wall_nominal"]
    close(rel["station_nominal"], steps, "relief station")
    centre = (rz0 + rz1) / 2
    close((vz0 + vz1) / 2, centre, "V centre")
    close((z0 + z1) / 2, centre, "body centre")
    if not (rz0 < vz0 and vz1 < rz1 and v_depth < rel["height_nominal"]):
        raise ValueError("the V must lie inside the relief slot past the steps")

    bore = f["pivot_bore"]
    bx, by, bz = bore["at"]
    if (
        bore["axis"] != [0.0, -1.0, 0.0]
        or not math.isclose(by, height)
        or bore["breaks_into"] != "relief"
    ):
        raise ValueError("pivot_bore: expected down from the top face into the relief")
    close(bz, centre, "pivot bore depth station")
    close(bx, bore["station_nominal"], "pivot bore station")
    if bx - bore["dia"][1] / 2 <= steps:
        raise ValueError("pivot_bore: does not drop wholly into the relief slot")

    tap = f["set_screw_tap"]
    tx, ty, tz = tap["at"]
    if (
        tap["axis"] != [0.0, 0.0, 1.0]
        or not math.isclose(tz, z0)
        or tap["into"] != "pivot_bore"
    ):
        raise ValueError("set_screw_tap: expected from the front face into the bore")
    close(tx, bx, "set screw station")
    if not rel["height_nominal"] < ty < height:
        raise ValueError("set_screw_tap: expected between the slot roof and the top")

    # The neck's two top edges, broken 45° from the paper end to full_to_x
    # (owner seat ruling 2026-11-23), its run-out past the stop.
    brk = f["neck_edge_breaks"]
    if (
        brk["axis"] != [1.0, 0.0, 0.0]
        or brk["edges"] != ["neck_front", "neck_back"]
        or not math.isclose(brk["angle_deg"], 45.0)
    ):
        raise ValueError(
            "neck_edge_breaks: expected the neck's top edges at 45° along X"
        )
    if not brk["leg"][0] <= brk["leg_nominal"] <= brk["leg"][1]:
        raise ValueError("neck_edge_breaks: the leg's nominal is off its band")
    if not 0.0 < brk["full_to_x"] < steps:
        raise ValueError(
            "neck_edge_breaks: the full break must stop short of the steps"
        )
    return {
        "length": length,
        "height": height,
        "z0": z0,
        "z1": z1,
        "depth": z1 - z0,
        "neck0": neck0,
        "neck1": neck1,
        "steps": steps,
        "centre": centre,
        "mouth_half": mouth_half,
        "flat_half": flat_half,
        "flat_width": tuple(v["flat_width"]),
        "v_depth": v_depth,
        # The V runs on past the steps to where the slot's corner arcs end.
        "v_end": steps + rel["corner_r_nominal"],
        "relief": (rz0, rz1),
        "relief_height": rel["height_nominal"],
        "relief_corner": tuple(rel["corner_r"]),
        "bore_at": (bx, bz),
        "bore_dia": tuple(bore["dia"]),
        "chamfer": tuple(bore["top_chamfer"]),
        "tap_at": (tx, ty),
        "tap_dia": tuple(tap["dia"]),
        "tap_pitch": IN / _tpi(tap["thread"]),
        "break_leg": tuple(brk["leg"]),
        "break_leg_nominal": brk["leg_nominal"],
        "break_to": brk["full_to_x"],
    }


def _tpi(thread: str) -> int:
    """Threads per inch of a unified thread callout, e.g. ``#4-40 UNC-2B``."""
    match = re.fullmatch(r"(#\d+|\d+/\d+)-(\d+) UN[CF]-\dB", thread)
    if not match:
        raise ValueError(f"thread {thread!r}: expected a unified internal thread")
    return int(match.group(2))


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    length, height, depth = g["length"], g["height"], g["depth"]
    z0, z1, steps = g["z0"], g["z1"], g["steps"]

    # The blank: the bar's 3/4 in thickness along Y, its 1-1/4 in width
    # along Z, sawn to length along X.
    blank_min, blank_max = p["blank_x_in"] * IN, p["blank_x_max_in"] * IN
    thick, wide = p["blank_y_in"] * IN, p["blank_z_in"] * IN
    end_skim, back_skim, bottom_skim = (
        p["end_skim_mm"],
        p["back_skim_mm"],
        p["bottom_skim_mm"],
    )
    upright_top = blank_max - end_skim
    _agree(plan, "upright_top_max_mm", upright_top)
    if blank_min - end_skim < length:
        raise ValueError(
            f"the shortest blank less the paper-end skim, {blank_min - end_skim:.3f}, is under the length {length:.3f}"
        )
    if thick - bottom_skim <= height:
        raise ValueError("the bar's thickness leaves nothing to face to the height")
    if wide - back_skim <= depth:
        raise ValueError("the bar's width leaves nothing to face to the depth")
    # Raw faces in the model frame: the paper end's skim before X0, the bar's
    # bottom face its skim below Y0, the back face its skim beyond the body's.
    raw_bottom = -bottom_skim
    raw_top = raw_bottom + thick
    raw_back = z1 + back_skim
    raw_front = raw_back - wide
    front_top = wide - back_skim  # VB04: the raw front above the back face
    bottom_level = thick - bottom_skim  # VB05: the bottom face above the stacks
    # VB03 and VB05 skim the back face and B at a fixed height above the
    # stacks: the bar, miked before Setup 2, must give each skim at least
    # bar_skim_min_mm and at most bar_skim_max_mm, itself within one face level.
    skim_min, skim_max = p["bar_skim_min_mm"], p["bar_skim_max_mm"]
    if not 0 < skim_min < skim_max <= p["face_step_max_mm"]:
        raise ValueError("the bar's skim window is not inside one face level")
    for key, level in (("bar_width", front_top), ("bar_thick", bottom_level)):
        _agree(plan, f"{key}_min_mm", level + skim_min)
        _agree(plan, f"{key}_max_mm", level + skim_max)
    if not p["bar_width_min_mm"] <= wide <= p["bar_width_max_mm"] or not (
        p["bar_thick_min_mm"] <= thick <= p["bar_thick_max_mm"]
    ):
        raise ValueError("the nominal bar is outside its own size window")

    # Cutters.
    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    r = em / 2
    chamfer = _shop_tool(plan, shop, "chamfer")
    cone = chamfer["flute_length_mm"]
    if not math.isclose(chamfer["diameter_mm"] / 2, cone, abs_tol=1e-6):
        raise ValueError(
            "the chamfer mill's 45° cone does not run to a point: the V offsets assume it"
        )
    eighth = _shop_tool(plan, shop, "em-eighth")
    e8 = eighth["diameter_mm"]
    r8 = e8 / 2
    d30 = _shop_tool(plan, shop, "drill-30")["diameter_mm"]
    d43 = _shop_tool(plan, shop, "drill-43")["diameter_mm"]
    # Owner ruling 2026-11-23, tool audit Q9: the slot's step corners print
    # R.065 (.060-.070) and the 1/8 in end mill leaves them at its radius.
    corner_lo, corner_hi = g["relief_corner"]
    if not corner_lo <= r8 <= corner_hi:
        raise ValueError(
            f"the corner cutter's R{r8:.3f} is outside the slot corners' printed"
            f" band {corner_lo:.3f}-{corner_hi:.3f}"
        )
    if eighth["flute_length_mm"] < g["relief_height"]:
        raise ValueError("the 1/8 in end mill's flutes do not reach the slot's floor")
    # The #30 is the bore's finish (owner ruling 2026-11-24, fit audit
    # question 20): its nominal is the drilled bore's model size.
    if not g["bore_dia"][0] <= d30 <= g["bore_dia"][1]:
        raise ValueError(f"#30 Ø{d30} is outside the drilled bore band {g['bore_dia']}")
    if not g["tap_dia"][0] - MODEL_TOL_MM <= d43 <= g["tap_dia"][1] + MODEL_TOL_MM:
        raise ValueError(f"#43 Ø{d43} is outside the tap drill band {g['tap_dia']}")
    for name, dia in (
        ("paper end", em),
        ("relief", em),
        ("relief corners", e8),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' cutter Ø{_cut(plan, name, 'cutter_dia_mm')}, the tool is Ø{dia}"
            )

    # Settings: every cut of a tool runs at its first cut's setting.
    face_rpm, face_feed = _setting(plan, shop, "paper end")
    for name in (
        "far end",
        "back face",
        "back step",
        "front face",
        "front step",
        "bottom face",
        "relief",
        "top face",
    ):
        if _setting(plan, shop, name) != (face_rpm, face_feed):
            raise ValueError(f"'{name}' runs at another setting than 'paper end'")
    v_rpm, v_feed = _setting(plan, shop, "V groove")
    if _setting(plan, shop, "bore chamfer") != (v_rpm, v_feed):
        raise ValueError("'bore chamfer' runs at another setting than 'V groove'")
    if _setting(plan, shop, "neck breaks") != (v_rpm, v_feed):
        raise ValueError("'neck breaks' runs at another setting than 'V groove'")
    e8_rpm, e8_feed = _setting(plan, shop, "relief corners")
    if _setting(plan, shop, "V flat") != (v_rpm, v_feed):
        raise ValueError("'V flat' runs at another setting than 'V groove'")
    spot_rpm, spot_feed = _setting(plan, shop, "bore spot")
    if _setting(plan, shop, "tap spot") != (spot_rpm, spot_feed):
        raise ValueError("'tap spot' runs at another setting than 'bore spot'")
    d30_rpm, d30_feed = _setting(plan, shop, "bore drill")
    d43_rpm, d43_feed = _setting(plan, shop, "tap drill")
    for key, value in (
        ("spot_feed_per_min_mm", spot_feed),
        ("drill_30_feed_per_min_mm", d30_feed),
        ("drill_43_feed_per_min_mm", d43_feed),
    ):
        if not math.isclose(p[key], value, abs_tol=PLAN_TOL_MM):
            raise ValueError(
                f"process.{key} {p[key]:g} is not its setting's {value:.2f}"
            )

    step_max = p["face_stepover_max_mm"]
    level_max = p["face_step_max_mm"]
    for name in (
        "paper end",
        "far end",
        "back face",
        "front face",
        "bottom face",
        "top face",
    ):
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), step_max, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' radial_woc_mm is not process.face_stepover_max_mm"
            )
    for name, doc in (
        ("paper end", end_skim),
        ("back face", back_skim),
        ("bottom face", bottom_skim),
    ):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), doc, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not its skim")
    for name in ("far end", "front face", "top face", "back step", "front step"):
        if _cut(plan, name, "axial_doc_mm") > level_max + 1e-6:
            raise ValueError(f"'{name}' axial_doc_mm is over process.face_step_max_mm")

    length_levels = _levels(upright_top, length, level_max)
    back_level = wide - back_skim
    back_step_levels = _levels(back_level, g["neck1"] - raw_front, level_max)
    depth_levels = _levels(front_top, depth, level_max)
    front_step_levels = _levels(depth, z1 - g["neck0"], level_max)
    # The back step's depth below the back face, as printed (VB03).
    _agree(plan, "back_step_depth_mm", z1 - g["neck1"])
    height_levels = _levels(raw_top, height, level_max)
    # A neck step is cut by the end mill's side on the step face: its centre
    # one radius short of the step, its far side past the paper end.
    step_x = steps - r
    if step_x - r > 0:
        raise ValueError("the neck step cutter does not reach the paper end")

    # Relief slot: the 1/2 in end mill from the far end in to one radius off
    # the step, its passes one radius inside each wall; the 1/8 in end mill
    # then takes the two inside corners at the step down to its own radius.
    rz0, rz1 = g["relief"]
    relief_floor = bottom_level - g["relief_height"]
    relief_levels = _levels(bottom_level, relief_floor, p["relief_step_max_mm"])
    if not math.isclose(
        _cut(plan, "relief", "axial_doc_mm"), p["relief_step_max_mm"], abs_tol=1e-6
    ):
        raise ValueError("'relief' axial_doc_mm is not process.relief_step_max_mm")
    slot_lo, slot_hi = rz0 - z1 + r, rz1 - z1 - r  # VB05 frame Y: z - z1
    if slot_hi < slot_lo:
        raise ValueError("the relief slot is narrower than the 1/2 in end mill")
    n_slot = 1 + math.ceil((slot_hi - slot_lo) / step_max - 1e-9)
    slot_ys = (
        [slot_lo + (slot_hi - slot_lo) * k / (n_slot - 1) for k in range(n_slot)]
        if n_slot > 1
        else [slot_lo]
    )
    slot_x = (steps + r, length + r + APPROACH_MM)
    corner_levels = _levels(bottom_level, relief_floor, p["corner_step_max_mm"])
    _agree(plan, "corner_step_max_mm", SLOT_AXIAL_MAX * e8)
    if not math.isclose(
        _cut(plan, "relief corners", "axial_doc_mm"),
        p["corner_step_max_mm"],
        abs_tol=1e-6,
    ):
        raise ValueError(
            "'relief corners' axial_doc_mm is not process.corner_step_max_mm"
        )
    corner_x = steps + r8
    # Each corner path runs along its wall from where the 1/2 in end mill's
    # last position cut it (one end-mill radius off the step) to one 1/8
    # radius off the step, then along the step face to where the end mill
    # cut that face flat.
    corners = [
        [(steps + r, rz0 - z1 + r8), (corner_x, rz0 - z1 + r8), (corner_x, slot_ys[0])],
        [
            (steps + r, rz1 - z1 - r8),
            (corner_x, rz1 - z1 - r8),
            (corner_x, slot_ys[-1]),
        ],
    ]
    # Each path starts and ends in the end mill's cut (air at every level):
    # past its last position along the slot, or within it there.
    for path in corners:
        for x, y in (path[0], path[-1]):
            past = (
                x >= slot_x[0] - 1e-6
                and slot_lo - r + r8 - 1e-6 <= y <= slot_hi + r - r8 + 1e-6
            )
            within = (
                min(math.dist((x, y), (slot_x[0], sy)) for sy in slot_ys)
                <= r - r8 + 1e-6
            )
            if not (past or within):
                raise ValueError(
                    f"corner path end X{x:.3f} Y{y:.3f} is not in the slot's cleared air"
                )

    # V groove: the pointed 90° chamfer mill, its tip stepped down the V in
    # levels, at each level swept across it in passes along X; the outer
    # passes put the cone on both flanks. At the last level, the flat's, the
    # tip then sweeps the flat again in passes V_FLAT_RIDGE_MAX_MM × 2 apart,
    # its outer passes on the flat's edges (owner ruling 2026-11-23, tool
    # audit Q9: no 5/64 cutter; the flat keeps its .08 and its place).
    v_levels = _v_levels(g["v_depth"], p["v_step_max_mm"])
    if not math.isclose(
        _cut(plan, "V groove", "axial_doc_mm"),
        g["v_depth"] / len(v_levels),
        abs_tol=PLAN_TOL_MM,
    ):
        raise ValueError("'V groove' axial_doc_mm is not the V's level step")
    v_passes = [
        (t, _v_offsets(g["mouth_half"] - t, p["v_stepover_max_mm"])) for t in v_levels
    ]
    flat_offsets = _v_offsets(g["flat_half"], 2 * V_FLAT_RIDGE_MAX_MM)
    flat_step = 2 * g["flat_half"] / (len(flat_offsets) - 1)
    _agree(plan, "v_flat_stepover_mm", flat_step)
    if not math.isclose(
        _cut(plan, "V flat", "radial_woc_mm"), p["v_flat_stepover_mm"], abs_tol=1e-6
    ):
        raise ValueError("'V flat' radial_woc_mm is not process.v_flat_stepover_mm")
    # The tip's outer passes stand the flat's edges at its nominal width,
    # inside its printed band.
    if not g["flat_width"][0] <= 2 * g["flat_half"] <= g["flat_width"][1]:
        raise ValueError("the tip's outer flat passes leave the flat off its band")
    # Below the cone's depth the shank (the cone's top radius) meets the
    # flank exactly where the cone does and the 45° flank widens upward, so
    # the shank never cuts it.
    yc = g["centre"] - z1
    v_x = (-(cone + APPROACH_MM), g["v_end"])
    # Past the steps the V's whole section lies in the slot (the slot first):
    # the chamfer mill's reach across the V stays inside the slot's walls
    # less their corner radius.
    if g["mouth_half"] > (rz1 - rz0) / 2 - g["relief_corner"][1]:
        raise ValueError("the V's end runs into the slot's corners")

    # Pivot bore and set screw.
    spot_bore = _spot_depth(p["spot_bore_dia_mm"])
    spot_tap = _spot_depth(p["spot_tap_dia_mm"])
    if p["spot_bore_dia_mm"] >= d30:
        raise ValueError("the bore spot is not under the #30 drill")
    if p["spot_tap_dia_mm"] >= d43:
        raise ValueError(
            "the tap spot is not under the #43 drill: it would chamfer the tap"
        )
    roof = g["relief_height"]
    bore_tip = roof - p["drill_past_mm"] - _point(d30)
    _agree(plan, "bore_tip_height_mm", bore_tip)
    if bore_tip <= 0:
        raise ValueError("the #30's point reaches the stacks' level")
    chamfer_mid = (g["chamfer"][0] + g["chamfer"][1]) / 2
    bore_mid = (g["bore_dia"][0] + g["bore_dia"][1]) / 2
    chamfer_depth = bore_mid / 2 + chamfer_mid  # the pointed 45° cone's plunge
    if chamfer_depth > cone:
        raise ValueError("the bore chamfer is deeper than the chamfer mill's cone")
    # Neck edge breaks (owner seat ruling 2026-11-23): the chamfer mill's
    # point along each neck face's top edge, its nominal leg under the top,
    # in levels no deeper than the V's, from beside P (the whole cone clear
    # of it) to the export's stop, where it is fed up out of the cut: past
    # the stop the cone leaves the break's run-out into the step.
    leg = g["break_leg_nominal"]
    if leg > cone:
        raise ValueError("the neck break is deeper than the chamfer mill's cone")
    break_levels = _v_levels(leg, p["v_step_max_mm"])
    _agree(plan, "break_level_mm", leg / len(break_levels))
    if not math.isclose(
        _cut(plan, "neck breaks", "axial_doc_mm"), p["break_level_mm"], abs_tol=1e-6
    ):
        raise ValueError("'neck breaks' axial_doc_mm is not process.break_level_mm")
    break_stop = g["break_to"]
    _agree(plan, "break_full_to_mm", break_stop)
    break_start = -(cone + APPROACH_MM)
    # VB06 frame Y: -(z - z0); each break's point on its neck face.
    break_ys = [z0 - g["neck0"], z0 - g["neck1"]]
    bx, bz = g["bore_at"]
    tx, ty = g["tap_at"]
    axis = z1 - bz  # VB07 frame: the bore axis above the stacks (back face)
    tap_tip = axis - _point(d43)
    _agree(plan, "tap_tip_height_mm", tap_tip)
    bore_r_min = g["bore_dia"][0] / 2
    if _point(d43) >= bore_r_min:
        raise ValueError("the #43's point reaches the bore's far wall")
    # The thread must be full to the bore's near wall where it lies farthest
    # from the front face (the bore at its smallest).
    near_wall = bz - bore_r_min - z0
    far_wall = bz + bore_r_min - z0
    reach = (p["tap_reach_min_mm"], p["tap_reach_max_mm"])
    if not reach[0] <= p["tap_reach_mm"] <= reach[1]:
        raise ValueError("process.tap_reach_mm is not between its min and max")
    if reach[0] < near_wall + BOTTOMING_CHAMFER_PITCHES * g["tap_pitch"] - 1e-6:
        raise ValueError(
            f"tap_reach_min_mm {reach[0]:g} leaves the bottoming tap's chamfer in the wall (near wall {near_wall:.3f})"
        )
    if reach[1] > far_wall - TAP_FAR_WALL_CLEAR_MM + 1e-6:
        raise ValueError(
            f"tap_reach_max_mm {reach[1]:g} runs the tap into the bore's far wall"
        )
    # The printed hole depths and pecks are the ones the files drill.
    _agree(plan, "bore_drill_depth_mm", height - (roof - p["drill_past_mm"]))
    _agree(plan, "tap_drill_depth_mm", depth - axis)
    for cut, depth_key, peck_key in (
        ("bore drill", "bore_drill_depth_mm", "peck_30_mm"),
        ("tap drill", "tap_drill_depth_mm", "peck_43_mm"),
    ):
        op = _op_with_cut(plan, cut)[0]
        if op.get("hole_depth_mm") != f"{{{{process.{depth_key}}}}}":
            raise ValueError(
                f"'{cut}' hole_depth_mm is not {{{{process.{depth_key}}}}}"
            )
        if op.get("peck") != {
            "step_mm": f"{{{{process.{peck_key}}}}}",
            "retract": "full",
        }:
            raise ValueError(
                f"'{cut}' peck is not process.{peck_key} with full retract"
            )

    # Vise.
    upright_grip = p["vise_jaw_height_mm"] - p["parallel_height_mm"]
    lying_grip = p["vise_jaw_height_mm"] - p["stack_height_mm"]
    _agree(plan, "upright_grip_mm", upright_grip)
    _agree(plan, "lying_grip_mm", lying_grip)
    stack_top = p["stack_height_mm"] + p["vise_bed_height_mm"]
    tap_stack = (
        shop["machines"]["pm-30mv"]["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - stack_top
        - depth
        - p["r8_collet_gauge_mm"]
    )
    _agree(plan, "tap_stack_max_mm", math.floor(tap_stack / IN * 100) / 100 * IN)
    # The front neck step's floor stands above the jaws (VB04).
    if z1 - g["neck0"] - lying_grip < 1.0:
        raise ValueError("the front neck step's floor is under 1 mm above the jaw tops")
    if bottom_level - lying_grip < FACE_OVERHANG_MM + 1.0:
        raise ValueError("the bottom face stands too low above the jaw tops to skim")
    t = p["parallel_thickness_mm"]

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    cy = (raw_bottom + raw_top) / 2
    cz = (raw_front + raw_back) / 2
    frames = {
        "paper_end": _frame([0.0, cy, cz], [0, 1, 0], [-1, 0, 0]),
        "far_end": _frame([0.0, cy, cz], [0, 1, 0], [1, 0, 0]),
        "back": _frame([0.0, raw_top, raw_front], [0, 1, 0], [0, 0, 1]),
        "front": _frame([0.0, raw_bottom, z1], [0, -1, 0], [0, 0, -1]),
        "bottom": _frame([0.0, raw_top, z1], [0, 0, 1], [0, -1, 0]),
        "top": _frame([0.0, 0.0, z0], [0, 0, -1], [0, 1, 0]),
        "set_screw": _frame([0.0, 0.0, z1], [0, -1, 0], [0, 0, -1]),
    }
    for key, frame in frames.items():
        if key in ("paper_end", "far_end"):
            continue
        # The paper end is X0 and the block runs to +X in every lying frame.
        if frame["axes"][0] != [1, 0, 0] or frame["origin"][0] != 0.0:
            raise ValueError(f"{key}: the paper end is not X0 with the block to +X")
    bore_xy = tuple(_r(v) for v in _to(frames["top"], [bx, height, bz])[:2])
    tap_xy = tuple(_r(v) for v in _to(frames["set_screw"], [tx, ty, z0])[:2])
    hw, hd = wide / 2, thick / 2
    stocks = {
        "paper_end": ((-hw, hw), (-hd, hd), (-upright_top, end_skim)),
        "far_end": ((-hw, hw), (-hd, hd), (0.0, upright_top)),
        "back": ((0.0, length), (-thick, 0.0), (0.0, wide)),
        "front": ((0.0, length), (-thick, 0.0), (0.0, front_top)),
        "bottom": ((0.0, length), (-depth, 0.0), (0.0, thick)),
        "top": ((0.0, length), (-depth, 0.0), (0.0, raw_top)),
        "set_screw": ((0.0, length), (-height, 0.0), (0.0, depth)),
    }

    def tool(
        key: str, dia: float, shape: str, rpm: float, feed: float, **extra: Any
    ) -> dict[str, Any]:
        return {
            "tool": key,
            "dia": dia,
            "shape": shape,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
            **extra,
        }

    em_tool = tool("em-half", em, "endmill", face_rpm, face_feed, flutes=3)
    chamfer_tool = tool(
        "chamfer", chamfer["diameter_mm"], "chamfer", v_rpm, v_feed, flutes=2
    )
    e8_tool = tool("em-eighth", e8, "endmill", e8_rpm, e8_feed, flutes=3)
    spot_tool = tool(
        "spot",
        CENTRE_DRILL["body_mm"],
        "drill",
        spot_rpm,
        spot_feed,
        tip_angle=CENTRE_DRILL["point_deg"],
    )
    d30_tool = tool(
        "drill-30", d30, "drill", d30_rpm, d30_feed, tip_angle=DRILL_POINT_DEG
    )
    d43_tool = tool(
        "drill-43", d43, "drill", d43_rpm, d43_feed, tip_angle=DRILL_POINT_DEG
    )

    def run(x: tuple[float, float], radius: float = r) -> tuple[float, float]:
        return (x[0] - radius - APPROACH_MM, x[1] + radius + APPROACH_MM)

    upright_ys = _stations((-hd, hd), r, step_max)
    lying_ys = {
        "back": _stations((-thick, 0.0), r, step_max),
        "bottom": _stations((-depth, 0.0), r, step_max),
    }
    step_y = run((-thick, 0.0))
    back_top, front_face_top = wide, front_top
    v_lines: list[str] = []
    clear_b = _r(thick + CLEAR_MM)
    first_t, first_offsets = v_passes[0]
    v_lines += [
        f"G0 Z{clear_b:.3f}",
        f"G0 X{_r(v_x[0]):.3f} Y{_r(yc + first_offsets[0]):.3f}",
        f"G0 Z{_r(bottom_level + SAFE_MM):.3f}",
    ]
    # Every level's plunge is beside P, in the air: a level that ends at the
    # V's far end (an odd count of passes) runs back along its last pass
    # first, since a plunge there would put the cone past the flank. The
    # flat's fine sweep follows the last level at its depth. Its cone, the
    # tip inside the flat's edges, stays inside the finished V, so those
    # passes start just off P instead of with the whole cone clear of it.
    flat_x = (-APPROACH_MM, g["v_end"])
    at_start = True
    reverse = False
    last_t = None
    sweeps = [(t, offsets, v_x) for t, offsets in v_passes]
    for t_level, offsets, xs in [*sweeps, (g["v_depth"], flat_offsets, flat_x)]:
        order = list(reversed(offsets)) if reverse else list(offsets)
        if t_level != last_t:
            v_lines.append(f"G1 Z{_r(bottom_level - t_level):.3f} F{{feed}}")
        last_t = t_level
        for k, e in enumerate(order):
            if k or t_level != first_t:
                v_lines.append(f"G1 Y{_r(yc + e):.3f} F{{feed}}")
            v_lines.append(f"G1 X{_r(xs[1] if at_start else xs[0]):.3f} F{{feed}}")
            at_start = not at_start
        if not at_start:
            v_lines.append(f"G1 X{_r(xs[0]):.3f} F{{feed}}")
            at_start = True
        reverse = not reverse
    v_lines.append(f"G0 Z{clear_b:.3f}")
    corner_lines = [
        line for path in corners for line in _corner(corner_levels, bottom_level, path)
    ]
    flat_z = bottom_level - g["v_depth"]

    sections = {
        "paper_end": (
            em_tool,
            "paper_end",
            "face the paper end",
            _face([0.0], end_skim, run((-hw, hw)), upright_ys),
        ),
        "far_end": (
            em_tool,
            "far_end",
            "face the far end to the length",
            _face(length_levels, upright_top, run((-hw, hw)), upright_ys),
        ),
        "back": (
            em_tool,
            "back",
            "skim the back face, cut the back neck step",
            _face([back_level], back_top, run((0.0, length)), lying_ys["back"])
            + _step(back_step_levels, back_top, step_x, step_y),
        ),
        "front": (
            em_tool,
            "front",
            "face the front to the depth, cut the front neck step",
            _face(depth_levels, front_face_top, run((0.0, length)), lying_ys["back"])
            + _step(front_step_levels, front_face_top, step_x, step_y),
        ),
        "bottom": (
            em_tool,
            "bottom",
            "skim the bottom face, mill the relief slot",
            _face([bottom_level], thick, run((0.0, length)), lying_ys["bottom"])
            + _slot(relief_levels, thick, slot_x, slot_ys),
        ),
        "v_groove": (chamfer_tool, "bottom", "cut the V groove", v_lines),
        "corners": (
            e8_tool,
            "bottom",
            "mill the slot corners",
            corner_lines,
        ),
        "top": (
            em_tool,
            "top",
            "face the top to the height",
            _face(height_levels, raw_top, run((0.0, length)), lying_ys["bottom"]),
        ),
        "bore_spot": (
            spot_tool,
            "top",
            "spot the pivot bore",
            _spot(bore_xy, height, height - spot_bore, height + CLEAR_MM),
        ),
        "bore_drill": (
            d30_tool,
            "top",
            "drill the pivot bore #30",
            _pecked(bore_xy, height, bore_tip, p["peck_30_mm"], height + CLEAR_MM),
        ),
        "bore_chamfer": (
            chamfer_tool,
            "top",
            "chamfer the pivot bore",
            _spot(bore_xy, height, height - chamfer_depth, height + CLEAR_MM),
        ),
        "tap_spot": (
            spot_tool,
            "set_screw",
            "spot the set-screw hole",
            _spot(tap_xy, depth, depth - spot_tap, depth + CLEAR_MM),
        ),
        "tap_drill": (
            d43_tool,
            "set_screw",
            "drill the set-screw hole #43",
            _pecked(tap_xy, depth, tap_tip, p["peck_43_mm"], depth + CLEAR_MM),
        ),
    }
    jobs = [
        {
            **spec,
            "frame": frame,
            "label": key.replace("_", " "),
            "stock": stocks[frame],
            "ops": [[key, label, lines]],
        }
        for key, (spec, frame, label, lines) in sections.items()
    ]
    # The neck breaks ride the bore chamfer's Job (same tool, speed and feed).
    next(job for job in jobs if job["ops"][0][0] == "bore_chamfer")["ops"].append(
        [
            "neck_breaks",
            "break the neck's top edges",
            _breaks(break_ys, break_levels, height, (break_start, break_stop)),
        ]
    )

    manual = {
        "tap": {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": "SPINDLE STAYS OFF. NEXT: 4-40 PLUG THEN BOTTOMING TAP IN THE SET-SCREW HOLE",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{tap_xy[0]:.3f} Y{tap_xy[1]:.3f}",
                "(4-40 PLUG TAP, THEN BOTTOMING TAP, IN THE SET-SCREW HOLE, FRONT FACE. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND TO THE NOTED DRO Z, READ WITH THE POINT PUSHED HOME. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": list(tap_xy),
        }
    }

    # Keep-outs. Upright: the jaws grip the bar's wide faces from the
    # parallels' top to the jaw top. Lying: the jaws beside the gripped span
    # from the stacks' top to the jaw top; the stacks under its edges.
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

    def stacks(x: tuple[float, float], y: tuple[float, float]) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - PARALLEL_LENGTH_MM / 2, mid + PARALLEL_LENGTH_MM / 2)
        return [
            _box("moving-jaw stack", span, (y[0], y[0] + t), 0.0),
            _box("fixed-jaw stack", span, (y[1] - t, y[1]), 0.0),
        ]

    lying = (0.0, length)
    far = (steps, length + 50.0)
    keep = {
        "paper_end": jaws(upright_grip - (blank_min - end_skim), (-hw, hw), (-hd, hd)),
        "far_end": jaws(upright_grip, (-hw, hw), (-hd, hd)),
        # The body past the steps keeps its full depth: the step cutter's
        # side stays one radius off it.
        "back": jaws(lying_grip, lying, (-thick, 0.0))
        + [_box("body past the step", far, (-thick, 0.0), back_level)],
        "front": jaws(lying_grip, lying, (-thick, 0.0))
        + [_box("body past the step", far, (-thick, 0.0), depth)],
        # The slot's walls, the step face and the neck's lands either side of
        # the V's flat keep their brass below the bottom face.
        "bottom": jaws(lying_grip, lying, (-depth, 0.0))
        + [
            _box("slot's near wall", far, (-depth, rz0 - z1), bottom_level),
            _box("slot's far wall", far, (rz1 - z1, 0.0), bottom_level),
            _box(
                "neck, front of the flat",
                (-50.0, steps),
                (-depth, yc - g["flat_half"]),
                bottom_level,
            ),
            _box(
                "neck, back of the flat",
                (-50.0, steps),
                (yc + g["flat_half"], 0.0),
                bottom_level,
            ),
        ],
        "top": jaws(lying_grip, lying, (-depth, 0.0)) + stacks(lying, (-depth, 0.0)),
        "set_screw": jaws(lying_grip, lying, (-height, 0.0))
        + stacks(lying, (-height, 0.0)),
    }
    # The 1/2 in end mill in the slot also keeps one radius off the step
    # between the neck lands (the V's flat column is the chamfer mill's).
    slot_keep = keep["bottom"][:4] + [
        _box("step face", (-50.0, steps), (rz0 - z1, rz1 - z1), bottom_level),
    ]

    tn = numbers
    expect: list[list[Any]] = []

    def face_checks(
        levels: list[float],
        top: float,
        y: tuple[float, float],
        span: float,
        boxes: list[dict[str, Any]],
    ) -> list[list[Any]]:
        return [
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
            ["keep_out", {"radius": r, "boxes": boxes}],
        ]

    def hole_checks(
        centre: tuple[float, float],
        top: float,
        bottom: float,
        radius: float,
        boxes: list[dict[str, Any]],
    ) -> list[list[Any]]:
        return [
            ["holes", {"centres": [list(centre)], "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": top, "open_holes": [list(centre)]}],
            ["vertical_below_top", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": radius, "boxes": boxes}],
        ]

    def step_cleared(floor: float) -> list[list[Any]]:
        # Points across the neck step, its corner at the step face and the
        # paper end included, cleared to the floor.
        points = [
            [x, y]
            for x in (0.05, steps / 2, steps - 0.05)
            for y in (-thick + 0.05, -thick / 2, -0.05)
        ]
        return [["cleared", {"points": points, "radius": r, "z": _r(floor)}]]

    singles = {
        "VB01_paper_end": ("paper_end", end_skim, [0.0]),
        "VB02_length": ("far_end", upright_top, length_levels),
    }
    for name, (key, top, levels) in singles.items():
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": top, "tools": [tn["em-half"]], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[face_rpm]]}],
            [name, "pauses", {"z_top": top, "count": 0}],
            [name, "depth", {"z_min": _r(levels[-1])}],
            *[
                [name, c, k]
                for c, k in face_checks(levels, top, (-hd, hd), wide, keep[key])
            ],
        ]
    for name, key, top, level, step_levels in (
        ("VB03_back", "back", back_top, [back_level], back_step_levels),
        ("VB04_front", "front", front_face_top, depth_levels, front_step_levels),
    ):
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": top, "tools": [tn["em-half"]], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[face_rpm]]}],
            [name, "pauses", {"z_top": top, "count": 0}],
            [name, "depth", {"z_min": _r(step_levels[-1])}],
            *[
                [name, c, k]
                for c, k in face_checks(level, top, (-thick, 0.0), length, keep[key])
            ],
            *[[name, c, k] for c, k in step_cleared(step_levels[-1])],
        ]

    name = "VB05_bottom"
    slot_points = [
        [x, y]
        for x in (steps + 0.05, (steps + length) / 2, length - 0.05)
        for y in (slot_ys[0], yc, slot_ys[-1])
    ] + [[slot_x[0], rz0 - z1 + 0.05], [slot_x[0], rz1 - z1 - 0.05]]
    corner_points = [
        [steps + 0.05, rz0 - z1 + r8],
        [corner_x, rz0 - z1 + 0.05],
        [steps + 0.05, rz1 - z1 - r8],
        [corner_x, rz1 - z1 - 0.05],
    ]
    # Across the flat every quarter of a fine pass spacing, at P, midway and
    # at the step: each within the ridge limit of a tip pass at the flat.
    n_flat = 4 * (len(flat_offsets) - 1)
    flat_points = [
        [x, yc - g["flat_half"] + 2 * g["flat_half"] * j / n_flat]
        for x in (0.05, steps / 2, steps - 0.05)
        for j in range(n_flat + 1)
    ]
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": thick,
                "tools": [tn["em-half"], tn["chamfer"], tn["em-eighth"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[face_rpm], [v_rpm], [e8_rpm]]}],
        [name, "pauses", {"z_top": thick, "count": 0}],
        [name, "depth", {"z_min": _r(relief_floor)}],
        *[
            [f"{name}@0", check, kwargs]
            for check, kwargs in face_checks(
                [bottom_level], thick, (-depth, 0.0), length, slot_keep
            )
        ],
        [f"{name}@0", "depth", {"z_min": _r(relief_floor)}],
        [
            f"{name}@0",
            "cleared",
            {"points": slot_points, "radius": r, "z": _r(relief_floor)},
        ],
        [f"{name}@1", "depth", {"z_min": _r(flat_z)}],
        [f"{name}@1", "rapids_clear", {"z_top": bottom_level}],
        [f"{name}@1", "air_feed", {"z_top": bottom_level}],
        # The tip stays between the V's mouth edges and off the slot's walls.
        [
            f"{name}@1",
            "keep_out",
            {
                "radius": 0.0,
                "boxes": keep["bottom"][:4]
                + [
                    _box(
                        "neck land, front of the mouth",
                        (-50.0, steps),
                        (-depth, yc - g["mouth_half"]),
                        bottom_level,
                    ),
                    _box(
                        "neck land, back of the mouth",
                        (-50.0, steps),
                        (yc + g["mouth_half"], 0.0),
                        bottom_level,
                    ),
                ],
            },
        ],
        [
            f"{name}@1",
            "cleared",
            {"points": flat_points, "radius": V_FLAT_RIDGE_MAX_MM, "z": _r(flat_z)},
        ],
        [f"{name}@2", "depth", {"z_min": _r(relief_floor)}],
        [f"{name}@2", "rapids_clear", {"z_top": bottom_level}],
        [f"{name}@2", "air_feed", {"z_top": bottom_level}],
        [f"{name}@2", "keep_out", {"radius": r8, "boxes": keep["bottom"]}],
        [
            f"{name}@2",
            "cleared",
            {"points": corner_points, "radius": r8, "z": _r(relief_floor)},
        ],
    ]

    name = "VB06_top_bore"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": raw_top,
                "tools": [
                    tn["em-half"],
                    tn["spot"],
                    tn["drill-30"],
                    tn["chamfer"],
                ],
                "loads_first": True,
            },
        ],
        [
            name,
            "spindle",
            {"rpm": [[face_rpm], [spot_rpm], [d30_rpm], [v_rpm]]},
        ],
        [name, "pauses", {"z_top": raw_top, "count": 0}],
        [name, "depth", {"z_min": _r(bore_tip)}],
        *[
            [f"{name}@0", check, kwargs]
            for check, kwargs in face_checks(
                height_levels, raw_top, (-depth, 0.0), length, keep["top"]
            )
        ],
        *[
            [f"{name}@1", c, k]
            for c, k in hole_checks(
                bore_xy,
                height,
                height - spot_bore,
                CENTRE_DRILL["body_mm"] / 2,
                keep["top"],
            )
        ],
        *[
            [f"{name}@2", c, k]
            for c, k in hole_checks(bore_xy, height, bore_tip, d30 / 2, keep["top"])
        ],
        # The bore chamfer, then the neck breaks on the same tool: one
        # section.  The chamfer is the only hole; the breaks enter on ramps
        # beside P.  Below the top the point moves sideways only along the
        # neck faces, short of the stop, never into the neck between them or
        # the body past the stop (a box the point may not enter: a pinpoint
        # cutter, 0.01); the cone stands under the jaws' tops by its reach
        # there at the breaks' depth, the most it ever does.
        [
            f"{name}@3",
            "holes",
            {"centres": [list(bore_xy)], "z_bottom": _r(height - chamfer_depth)},
        ],
        [f"{name}@3", "rapids_clear", {"z_top": height, "open_holes": [list(bore_xy)]}],
        [f"{name}@3", "air_feed", {"z_top": height}],
        [f"{name}@3", "depth", {"z_min": _r(height - max(leg, chamfer_depth))}],
        [
            f"{name}@3",
            "keep_out",
            {"radius": max(0.0, lying_grip - (height - leg)), "boxes": keep["top"]},
        ],
        [
            f"{name}@3",
            "keep_out",
            {
                "radius": 0.01,
                "boxes": [
                    _box(
                        "neck between its breaks",
                        (-50.0, steps),
                        (break_ys[1] + 0.05, break_ys[0] - 0.05),
                        height,
                    ),
                    _box(
                        "body short of the bore",
                        (break_stop + 0.05, bx - 0.05),
                        (-depth, 0.0),
                        height,
                    ),
                    _box(
                        "body past the bore",
                        (bx + 0.05, length + 50.0),
                        (-depth, 0.0),
                        height,
                    ),
                ],
            },
        ],
        [
            f"{name}@3",
            "cleared",
            {
                "points": [
                    [x, y] for x in (0.05, break_stop / 2, break_stop) for y in break_ys
                ],
                "radius": 0.0,
                "z": _r(height - leg),
            },
        ],
    ]

    name = "VB07_set_screw"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": depth,
                "tools": [tn["spot"], tn["drill-43"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[spot_rpm], [d43_rpm]]}],
        [name, "pauses", {"z_top": depth, "count": 0}],
        [name, "depth", {"z_min": _r(tap_tip)}],
        *[
            [f"{name}@0", c, k]
            for c, k in hole_checks(
                tap_xy,
                depth,
                depth - spot_tap,
                CENTRE_DRILL["body_mm"] / 2,
                keep["set_screw"],
            )
        ],
        *[
            [f"{name}@1", c, k]
            for c, k in hole_checks(tap_xy, depth, tap_tip, d43 / 2, keep["set_screw"])
        ],
    ]
    expect += [
        [
            "VB08_set_screw_tap",
            "tap_stop",
            {
                "tool": tn["tap-guide"],
                "at": manual["tap"]["at"],
                "machine_top": MACHINE_Z_TOP_MM,
            },
        ],
        ["VB08_set_screw_tap", "air_feed", {"z_top": depth}],
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
        # For the process test: the cuts' geometry, not checked by _gcode.
        "v": {
            "centre_y": yc,
            "bottom": bottom_level,
            "mouth_half": g["mouth_half"],
            "passes": v_passes,
            "flat": flat_offsets,
            "x": list(v_x),
        },
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
            doc, f"V block {key}", ctx["step"], frame["origin"], frame["axes"]
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
    """What the as-machined report needs: the blank sawn off the 3/4 x 1-1/4
    in bar, as VB01 holds it upright (its stock box: the bar's section, the
    raw paper end the end skim above Z0), the sawn length below the raw end
    at the plan's blank_x_in-blank_x_max_in band and its middle (the plan
    marks no nominal). The paper end touches Z0 in VB01, so it stays put
    and a longer blank reaches further down, which VB02 faces off. Every
    program runs in its jobs' one frame; VB08 is the hand tap (no frame).
    One cutter the jobs do not describe: the chamfer mill, a 90° cone that
    runs to a point (context() refuses one that does not)."""
    p = inputs.plan["parameters"]
    lengths = {
        "nominal": (p["blank_x_in"] + p["blank_x_max_in"]) / 2 * IN,
        "min": p["blank_x_in"] * IN,
        "max": p["blank_x_max_in"] * IN,
    }
    stock = next(job["stock"] for job in ctx["jobs"] if job["ops"][0][0] == "paper_end")
    top = stock[2][1]
    dia = {job["tool"]: job["dia"] for job in ctx["jobs"]}
    cone = dia["chamfer"] / 2
    return {
        "parts": {
            "": {
                "blank": {
                    "frame": "paper_end",
                    "box": [list(stock[0]), list(stock[1]), [top - lengths["nominal"], top]],
                    "length": {"axis": "z", "keep": "max", "mm": lengths},
                }
            }
        },
        "skip": {},
        "tools": {ctx["numbers"]["chamfer"]: [[0.0, 0.0], [cone, cone]]},
        "notes": ["VB08 is the 4-40 tap by hand under the tap guide: the report cuts no thread"],
    }
