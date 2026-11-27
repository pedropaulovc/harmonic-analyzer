"""FreeCAD CAM recipe for MHA-DT-02, the arbor pedestal.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The pedestal's sizes
come from the feature export (the width, the far face to near end depth, the
strap, the foot top, the flanks and the crown, the drilled bore, the hold-down
hole and the apex tap); the blank, the skims, face levels, the step's
stations and levels, the outline's passes, spots, pecks and the holds from
``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter diameters, speeds
and feeds from the shop (``shop/``) and the plan's authored drill
settings. Every path is written here (``rt.custom``): straight lines and
arcs a recipe can state exactly. Typed here, because neither record carries
them: the #2 centre drill's catalogue geometry (it sets the spot depth), the
twist drills' 118° point, the machine's Z top for the tap file's retract,
the approach, safe and clearance heights, the face overhang and the vise
jaws' depth (keep-out shapes only).

Route (plan text in ``plan.toml``): one 1 x 1-1/4 in 1018 blank about 2.25
long per run, its length along the model's Y (the pedestal's height).
Lying on the 1 in bar face W, jaws on the two 1-1/4 faces: PA01 faces the
east side to the width. Lying on the far face's bar face, jaws on W and E:
PA02 faces the near end to the depth plus the stock left on the far face.
Upright, a sawn end up: PA03 faces the foot seat, spots and drills the #15
hold-down hole into the waste above the foot. Lying again, the near end up,
the far face's stock on the stacks: PA04 mills the step down to the strap
(which opens the hold-down hole), then spots and drills (V) the arbor
bore through the strap. Upright on the seat: PA05 faces the top end to the
height, spots and drills #43 from the apex into the bore; PA06 brings the
tap guide over it for tapping by hand. Far face up, the foot gripped
between the jaws by the seat and the foot top: PA07 faces the far face to
the depth and profiles the flanks and the crown through the strap.

Work frames (G54), each set in its setup:
- PA01: X0 the blank's left end, Y0 the fixed jaw (the far face's bar
  face), Z0 the stacks' top (W).
- PA02: X0 the blank's RIGHT end, Y0 the fixed jaw (W), Z0 the stacks' top
  (the far face's bar face).
- PA03: X0 the near end (the LEFT side), Y0 the fixed jaw (W), Z0 the faced
  seat.
- PA04: X0 the seat (the RIGHT end), Y0 the fixed jaw (W), Z0 the stacks'
  top (the far face's bar face).
- PA05/PA06: X0 the near end (the RIGHT side), Y0 the fixed jaw (W), Z0 the
  parallels' top (the seat).
- PA07: X0 the part's centre between W and E, Y0 the fixed jaw (the seat),
  Z0 the parallel's top (the near end).

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock; the
outline climbs (ball screws). The step's passes cut conventional (#3691: the
owner's 2026-11-25 ruling on #3590, no program climbs before a measured
climb test; the step's setting was measured conventional). The apex hole is tapped
by hand (FluidNC cannot rigid-tap; owner, Pedro, 2026-11-17), the T-handle
wrench's centre hole on the spring point of the Fisher tap guide in the
1/2 in R8 collet (owner, Pedro, 2026-11-21: "use
https://littlemachineshop.com/products/tap-guide-fisher?variant=45472915226805
on r8 0.5 collet"), spindle off, the operator jogging Z down to push the
point home. FluidNC, like Grbl, refuses jogs while an M0
holds the program (FluidNC wiki, "Single Block Mode",
http://wiki.fluidnc.com/en/features/single_block_mode), so the tap stop is a
file of its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_arbor_pedestal"
COMMENT = "MHA-DT-02 arbor pedestal"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes; flat keys are one Job.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("PA01_width", ("width",)),
    ("PA02_depth", ("depth",)),
    ("PA03_seat", (("seat",), ("hold_spot",), ("hold_drill",))),
    (
        "PA04_step_bore",
        (("step",), ("bore_spot",), ("bore_drill",)),
    ),
    ("PA05_top_apex", (("top",), ("apex_spot",), ("apex_drill",))),
    ("PA06_apex_tap", ("tap_apex",)),
    ("PA07_outline", ("far_face", "outline")),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held, and the tap file before its retract
# (the tap guide).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the tap, the saw and the files are not).
CAM_TOOLS = (
    "em-half",
    "spot",
    "drill-15",
    "drill-v",
    "drill-43",
    "tap-guide",
)
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included: the shop record names
# the tool, not its geometry.
CENTRE_DRILL = {
    "body_mm": 3 / 16 * IN,
    "pilot_mm": 5 / 64 * IN,
    "pilot_length_mm": 5 / 64 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# The tap file's first motion: G53 G0 to machine Z0, the homed top. FluidNC
# sets an axis's machine position to its homing mpos_mm (default 0) after
# homing, and Z homes up (cad/config/shop-equipment/
# cnc.pm-30mv-controller: switches on all three axes); the owner (Pedro)
# confirmed it, answered in person 2026-11-21 (cnc rulings record): machine
# Z = 0 is the top of travel after homing.
MACHINE_Z_TOP_MM = 0.0
# Face and step passes start and finish with the cutter this far clear of
# the part's sides, so every plunge and stepover link is in the air beside it.
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
# parallels' length (4 in, shop-equipment fixtures.parallels-lms-6745). In
# PA07 the strap stands over the moving jaw's body: its keep-out runs 4 in
# out from the foot top, past the strap's end.
JAW_DEPTH_MM = IN
JAW_BODY_MM = 4 * IN
PARALLEL_LENGTH_MM = 4 * IN
# The outline's cutter centre may stray this far from its offset (the post's
# 3 places and the arc's end-point rounding).
OUTLINE_TOL_MM = 0.01
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# A drill may sit this far outside its hole's band (the band's inch limits
# and the tool's inch size each rounded to mm).
BAND_TOL_MM = 0.001


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
    xy: tuple[float, float], top: float, tip: float, peck: float | None, clear: float
) -> list[str]:
    """Drill from ``top`` to ``tip`` in pecks of ``peck`` (``None``: one
    plunge), each with a full retract to the R plane and a rapid back to just
    above the last peck. Moves to and from the hole run at ``clear``."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    depths = []
    depth = top
    while peck is not None and depth - peck > tip + 1e-6:
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
    levels: list[float], top: float, xs: list[float], y: tuple[float, float]
) -> list[str]:
    """The step, level by level: at each, one pass per station in ``xs``
    (from the open end toward the foot), every pass along -Y from ``y[0]``
    to ``y[1]``: the uncut stock on the cutter's +X side, on the left of
    travel, conventional with the clockwise (M3) spindle. Each pass plunges
    beside the part and lifts above the stock top before the next."""
    safe, clear = _r(top + SAFE_MM), _r(top + CLEAR_MM)
    lines = [f"G0 Z{clear:.3f}"]
    for z in levels:
        for x in xs:
            lines += [
                f"G0 X{_r(x):.3f} Y{_r(y[0]):.3f}",
                f"G0 Z{safe:.3f}",
                f"G1 Z{_r(z):.3f} F{{feed}}",
                f"G1 Y{_r(y[1]):.3f} F{{feed}}",
                f"G0 Z{safe:.3f}",
            ]
    return lines + [f"G0 Z{clear:.3f}"]


def _thread_major(thread: str) -> float:
    """A numbered UNC/UNF thread's major diameter (mm): #N is .060 + .013 N in
    (ASME B1.1)."""
    match = re.fullmatch(r"#(\d+)-\d+ UN[CF]-2B", thread)
    if not match:
        raise ValueError(f"thread {thread!r}: expected a numbered UNC/UNF size")
    return (0.060 + 0.013 * int(match.group(1))) * IN


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The pedestal's sizes and holes from the export, each checked against
    the frame the recipe assumes: the foot seat at Y0 centred in X, the
    height up +Y to the crown's apex, the far face at +Z, the near end and
    the strap's outer face toward −Z."""
    f = features["features"]

    def plane(name: str, axis: str) -> float:
        p = f[name]["plane"]
        if p["axis"] != axis:
            raise ValueError(f"{name}: expected a plane normal to {axis}")
        return p["value"]

    seat, foot_top = plane("foot_seat", "y"), plane("foot_top", "y")
    far, near, strap = (
        plane("far_face", "z"),
        plane("near_end", "z"),
        plane("strap_outer_face", "z"),
    )
    west, east = plane("west_side", "x"), plane("east_side", "x")
    if seat != 0.0 or not math.isclose(west, -east, abs_tol=1e-6):
        raise ValueError("expected the seat at Y0 and the sides centred on X0")
    for name, got, key in (
        ("foot_top", foot_top - seat, "height_nominal"),
        ("near_end", far - near, "depth_nominal"),
        ("strap_outer_face", far - strap, "depth_nominal"),
        ("east_side", east - west, "width_nominal"),
    ):
        if not math.isclose(got, f[name][key], abs_tol=1e-3):
            raise ValueError(f"{name}: {got:.4f} is not its {key} {f[name][key]}")
    crown = f["crown"]
    cx, cy, _cz = crown["center"]
    radius = crown["radius_nominal"]
    if cx != 0.0 or crown["axis"] != [0.0, 0.0, -1.0]:
        raise ValueError("crown: expected about a Z axis on X0")
    flanks = f["flanks"]
    root = (flanks["root_half_width_nominal"], flanks["root_height_nominal"])
    tangent = (flanks["tangent_half_width_nominal"], flanks["tangent_height_nominal"])
    if not math.isclose(root[0], east, abs_tol=1e-6) or not math.isclose(
        root[1], foot_top, abs_tol=1e-6
    ):
        raise ValueError("flanks: expected rooted on the sides at the foot top")
    if not math.isclose(math.dist(tangent, (cx, cy)), radius, abs_tol=1e-3):
        raise ValueError("flanks: the tangent point is not on the crown")
    # Tangent: the flank is square to the crown's radius at that point.
    d = (tangent[0] - root[0], tangent[1] - root[1])
    if abs(d[0] * (tangent[0] - cx) + d[1] * (tangent[1] - cy)) > 1e-3 * math.hypot(*d):
        raise ValueError("flanks: not tangent to the crown")
    top = cy + radius
    bore = f["arbor_bore"]
    if (
        bore["at"] != [cx, cy, far]
        or bore["axis"] != [0.0, 0.0, -1.0]
        or not bore["thru"]
    ):
        raise ValueError(
            "arbor_bore: expected through on the crown's axis from the far face"
        )
    hold = f["hold_down_hole"]
    if (
        hold["axis"] != [0.0, 1.0, 0.0]
        or hold["at"][:2] != [0.0, seat]
        or not hold["thru"]
    ):
        raise ValueError(
            "hold_down_hole: expected through the foot from the seat on X0"
        )
    if not near < hold["at"][2] < strap:
        raise ValueError("hold_down_hole: not behind the strap, in the foot")
    apex = f["apex_tap"]
    if (
        apex["axis"] != [0.0, -1.0, 0.0]
        or apex["at"][0] != 0.0
        or not math.isclose(apex["at"][1], top, abs_tol=1e-6)
        or apex["into"] != "arbor_bore"
        or not strap < apex["at"][2] < far
    ):
        raise ValueError("apex_tap: expected from the apex down into the bore")
    return {
        "width": east - west,
        "half": east,
        "depth": far - near,
        "strap": far - strap,
        "foot_top": foot_top,
        "far": far,
        "near": near,
        "crown_y": cy,
        "radius": radius,
        "top": top,
        "root": root,
        "tangent": tangent,
        "bore_dia": bore["dia"],
        "hold": hold,
        "apex": apex,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    width, depth, strap = g["width"], g["depth"], g["strap"]
    half, foot_top, top = g["half"], g["foot_top"], g["top"]

    # The blank: the 1 x 1-1/4 in flat, sawn to length; the 1 in along X,
    # the 1-1/4 along Z, the length along Y.
    blank_x, blank_z = p["blank_x_in"] * IN, p["blank_z_in"] * IN
    blank_min, blank_max = p["blank_length_min_in"] * IN, p["blank_length_max_in"] * IN
    if not math.isclose(p["blank_y_in"], p["blank_length_min_in"], abs_tol=1e-9):
        raise ValueError("process.blank_y_in is not the shortest blank")
    seat_skim, far_stock = p["seat_skim_mm"], p["far_face_stock_mm"]
    if blank_x <= width:
        raise ValueError(f"the bar's {blank_x:.3f} leaves nothing to face to the width")
    height = depth + far_stock
    _agree(plan, "depth_top_mm", height)
    if blank_z <= height:
        raise ValueError(
            f"the bar's {blank_z:.3f} is not over the depth plus the far face's stock {height:.3f}"
        )
    upright_top = blank_max - seat_skim
    _agree(plan, "upright_top_max_mm", upright_top)
    if blank_min - seat_skim <= top:
        raise ValueError(
            f"the shortest blank less the seat skim, {blank_min - seat_skim:.3f}, is not over the height {top:.3f}"
        )

    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    r = em / 2
    step_max = p["face_stepover_max_mm"]
    far_step_max = p["far_face_stepover_max_mm"]
    level_max = p["face_step_max_mm"]
    # Three settings: the faces (PA01-PA03, PA05), the step (PA04), and the
    # far face with the outline (PA07, one Job, one speed).
    face_rpm, face_feed = _setting(plan, shop, "width")
    step_rpm, step_feed = _setting(plan, shop, "step")
    outline_rpm, outline_feed = _setting(plan, shop, "far face")
    groups = (
        ("width", ("width", "depth", "seat", "top")),
        ("step", ("step",)),
        ("far face", ("far face", "outline rough", "outline finish")),
    )
    for lead, names in groups:
        for name in names:
            if not math.isclose(_cut(plan, name, "cutter_dia_mm"), em, abs_tol=1e-6):
                raise ValueError(
                    f"'{name}' cutter Ø{_cut(plan, name, 'cutter_dia_mm')}, the end mill is Ø{em}"
                )
            if _setting(plan, shop, name) != _setting(plan, shop, lead):
                raise ValueError(f"'{name}' runs at another setting than '{lead}'")
    for names, stepover, key in (
        (("width", "depth", "seat", "top"), step_max, "face_stepover_max_mm"),
        (("far face",), far_step_max, "far_face_stepover_max_mm"),
    ):
        for name in names:
            if not math.isclose(
                _cut(plan, name, "radial_woc_mm"), stepover, abs_tol=1e-6
            ):
                raise ValueError(f"'{name}' radial_woc_mm is not process.{key}")
    if not math.isclose(_cut(plan, "seat", "axial_doc_mm"), seat_skim, abs_tol=1e-6):
        raise ValueError("'seat' axial_doc_mm is not process.seat_skim_mm")
    for name in ("width", "depth", "top"):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), level_max, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not process.face_step_max_mm")
    width_levels = _levels(blank_x, width, level_max)
    depth_levels = _levels(blank_z, height, level_max)
    top_levels = _levels(upright_top, top, level_max)
    # The bar checked before sawing (Setup 1): PA01 and PA02 face from the
    # nominal 1 in and 1-1/4 in, so a bar over them deepens each program's
    # first level by the excess; it may grow only to the measured level
    # depth, and the same amount under is accepted (a thinner bar still
    # cleans up: its first level cuts less).
    for key, nominal, levels in (
        ("bar_x", blank_x, width_levels),
        ("bar_z", blank_z, depth_levels),
    ):
        headroom = level_max - (nominal - levels[0])
        _agree(plan, f"{key}_max_mm", nominal + headroom)
        _agree(plan, f"{key}_min_mm", nominal - headroom)
    far_level_max = p["far_face_level_mm"]
    if not math.isclose(
        _cut(plan, "far face", "axial_doc_mm"), far_level_max, abs_tol=1e-6
    ):
        raise ValueError("'far face' axial_doc_mm is not process.far_face_level_mm")
    far_levels = _levels(height, depth, far_level_max)

    # The step: from the near end down to the strap's outer face, level by
    # level; passes across the width at stations from the longest blank's
    # end (less the seat skim) to the foot top, the cutter's edge on it.
    floor = height - (depth - strap)
    _agree(plan, "step_floor_mm", floor)
    step_level = p["step_level_mm"]
    step_levels = _levels(height, floor, step_level)
    if not math.isclose(height - step_levels[0], step_level, abs_tol=PLAN_TOL_MM):
        raise ValueError(
            f"process.step_level_mm {step_level:g} does not divide the step's {height - floor:.3f}"
        )
    if not math.isclose(_cut(plan, "step", "axial_doc_mm"), step_level, abs_tol=1e-6):
        raise ValueError("'step' axial_doc_mm is not process.step_level_mm")
    raw_x, final_x = -(upright_top + r), -(foot_top + r)
    n_stations = math.ceil((final_x - raw_x) / p["step_station_max_mm"] - 1e-9)
    station = (final_x - raw_x) / n_stations
    _agree(plan, "step_station_mm", station)
    if not math.isclose(
        _cut(plan, "step", "radial_woc_mm"), station, abs_tol=PLAN_TOL_MM
    ):
        raise ValueError("'step' radial_woc_mm is not process.step_station_mm")
    step_xs = [raw_x + station * (k + 1) for k in range(n_stations)]

    # The outline: rough levels off the finish offset, then one full-depth
    # finish pass on the outline; through the strap and outline_past_mm into
    # the step's void.
    past = p["outline_past_mm"]
    outline_bottom = depth - strap - past
    stock = p["outline_finish_stock_mm"]
    rough_level = p["outline_rough_level_mm"]
    rough_levels = _levels(depth, outline_bottom, rough_level)
    if not math.isclose(depth - rough_levels[0], rough_level, abs_tol=PLAN_TOL_MM):
        raise ValueError(
            f"process.outline_rough_level_mm {rough_level:g} does not divide the outline's {depth - outline_bottom:.3f}"
        )
    _agree(plan, "outline_depth_mm", depth - outline_bottom)
    for name, doc, woc in (
        ("outline rough", rough_level, None),
        ("outline finish", depth - outline_bottom, stock),
    ):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), doc, abs_tol=PLAN_TOL_MM):
            raise ValueError(f"'{name}' axial_doc_mm is not {doc:.3f}")
        if woc is not None and not math.isclose(
            _cut(plan, name, "radial_woc_mm"), woc, abs_tol=1e-6
        ):
            raise ValueError(
                f"'{name}' radial_woc_mm is not process.outline_finish_stock_mm"
            )
    # The rough pass's widest cut: the faced top end's corner, off the crown.
    corner = math.dist((half, top), (0.0, g["crown_y"])) - g["radius"]
    _agree(plan, "outline_rough_woc_mm", corner - stock)
    if not math.isclose(
        _cut(plan, "outline rough", "radial_woc_mm"),
        corner - stock,
        abs_tol=PLAN_TOL_MM,
    ):
        raise ValueError(
            "'outline rough' radial_woc_mm is not process.outline_rough_woc_mm"
        )
    if 2 * r < corner - stock:
        raise ValueError("the rough pass does not reach the top end's corners")

    # Holes: each spot under its drill (no chamfer at the mouth); drills from
    # the authored settings.
    d15 = _shop_tool(plan, shop, "drill-15")["diameter_mm"]
    dv = _shop_tool(plan, shop, "drill-v")["diameter_mm"]
    d43 = _shop_tool(plan, shop, "drill-43")["diameter_mm"]
    hold, apex = g["hold"], g["apex"]

    def within(dia: float, band: list[float]) -> bool:
        # The bands are inch limits printed to 3-4 places: #43's .089 is
        # 2.2606 mm, the 4-40 minor's .0890 limit 2.261.
        return band[0] - BAND_TOL_MM <= dia <= band[1] + BAND_TOL_MM

    if not within(d15, hold["dia"]):
        raise ValueError(
            f"#15 Ø{d15} is outside the hold-down hole's band {hold['dia']}"
        )
    if not within(dv, g["bore_dia"]):
        raise ValueError(f"V drill Ø{dv} is outside the bore's band {g['bore_dia']}")
    if not within(d43, apex["dia"]):
        raise ValueError(f"#43 Ø{d43} is not the apex tap's drill {apex['dia']}")
    spot_rpm, spot_feed = _setting(plan, shop, "hold spot")
    for name, key, drill in (
        ("hold spot", "hold_spot_dia_mm", d15),
        ("bore spot", "bore_spot_dia_mm", dv),
        ("apex spot", "apex_spot_dia_mm", d43),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), p[key], abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not process.{key}")
        if p[key] >= drill:
            raise ValueError(
                f"process.{key} is not under its drill: it would chamfer the hole"
            )
        if _setting(plan, shop, name) != (spot_rpm, spot_feed):
            raise ValueError(f"'{name}' runs at another speed than 'hold spot'")
    hold_rpm, hold_feed = _setting(plan, shop, "hold drill")
    bore_rpm, bore_feed = _setting(plan, shop, "bore drill")
    apex_rpm, apex_feed = _setting(plan, shop, "apex drill")

    # Hold-down (PA03): one plunge from the seat, full diameter past the
    # foot top into the waste the step removes.
    hold_tip = -(foot_top + p["hold_drill_past_mm"] + _point(d15))
    _agree(plan, "hold_tip_depth_mm", -hold_tip)
    # Bore (PA04): from the step's floor through the strap and the far face's
    # stock, the V drill's full diameter past the stacks' top (into the gap
    # between them; fit audit F01: no reamer).
    bore_tip = -(p["bore_drill_past_mm"] + _point(dv))
    _agree(plan, "bore_tip_height_mm", bore_tip)
    # Apex (PA05): #43 pecked from the apex, its full diameter past the
    # bore's wall at the hole's edge.
    bore_r = dv / 2
    edge_wall = g["crown_y"] + math.sqrt(bore_r**2 - (d43 / 2) ** 2)
    apex_tip = edge_wall - p["apex_drill_past_mm"] - _point(d43)
    _agree(plan, "apex_tip_height_mm", apex_tip)
    peck = p["apex_peck_mm"]
    op = _op_with_cut(plan, "apex drill")[0]
    if op["peck"] != {"step_mm": peck, "retract": "full"}:
        raise ValueError(
            "'apex drill' peck is not process.apex_peck_mm with full retract"
        )
    # Hand tap (PA06): the plug tap's lead past the bore's wall at the
    # thread's major diameter, and 1.0 short of the bore's far wall.
    major = _thread_major(apex["thread"])
    major_wall = g["crown_y"] + math.sqrt(bore_r**2 - (major / 2) ** 2)
    _agree(plan, "tap_reach_min_mm", top - major_wall + p["plug_tap_lead_mm"])
    _agree(plan, "tap_reach_max_mm", top - (g["crown_y"] - bore_r) - 1.0)

    # Vise grips: jaw height less the parallels (upright), the stacks
    # (lying), the step's stacks and the foot's stack.
    jaw = p["vise_jaw_height_mm"]
    upright_grip = jaw - p["parallel_height_mm"]
    lying_grip = jaw - p["riser_height_mm"]
    step_grip = jaw - p["step_riser_height_mm"]
    foot_grip = jaw - p["foot_riser_height_mm"]
    for key, value in (
        ("upright_grip_mm", upright_grip),
        ("lying_grip_mm", lying_grip),
        ("step_grip_mm", step_grip),
        ("foot_grip_mm", foot_grip),
    ):
        _agree(plan, key, value)
    if step_grip >= floor:
        raise ValueError(
            f"the step's floor {floor:.3f} is not above the jaw tops {step_grip:.3f}"
        )
    if foot_grip >= outline_bottom:
        raise ValueError(
            f"the outline's bottom {outline_bottom:.3f} is not above the jaw tops {foot_grip:.3f}"
        )
    t = p["parallel_thickness_mm"]
    # Each part centred on the jaws: its ends (jaw width − its length along
    # the jaws)/2 in from the jaw sides.
    jaw_w = p["vise_jaw_width_mm"]
    for key, along in (
        ("vise_lying_inset_mm", blank_max),
        ("vise_step_inset_mm", upright_top),
        ("vise_upright_inset_mm", height),
        ("vise_foot_inset_mm", width),
    ):
        _agree(plan, key, -(jaw_w - along) / 2)
    # The tap stack's ceiling: spindle-to-table maximum less the tool-change
    # clearance, the vise bed, the parallels, the longest blank less the seat
    # skim and the collet's gauge, rounded down to .01 in.
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["parallel_height_mm"]
        - upright_top
        - p["r8_collet_gauge_mm"]
    )
    _agree(plan, "tap_stack_max_mm", math.floor(stack / 0.254 + 1e-9) * 0.254)
    # The PA07 beam's strap section: the crown's Ø less the bore's largest.
    _agree(plan, "strap_net_width_mm", 2 * g["radius"] - g["bore_dia"][1])
    # PA04's air prove-out: Z0 raised by the least .1 in multiple that puts
    # the drill's point CLEAR_MM above the uncut near end.
    raise_mm = math.ceil((height + CLEAR_MM - bore_tip) / 2.54 - 1e-9) * 2.54
    _agree(plan, "step_prove_raise_mm", raise_mm)
    # The near end (PA02) and the step's floor (PA04) each take half the
    # strap's band: the floor is cut from F, the far face later from N.
    strap_band = features["features"]["strap_outer_face"]["depth"]
    share = (strap_band[1] - strap_band[0]) / 4
    for key, value in (
        ("depth_top_min_mm", height - share),
        ("depth_top_max_mm", height + share),
        ("step_floor_min_mm", floor - share),
        ("step_floor_max_mm", floor + share),
    ):
        _agree(plan, key, value)

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)). The raw blank in the
    # model: W the bar face at the west side, the far face's bar face
    # far_stock beyond the far face (the near end faced to the depth plus
    # it), the seat skim below the seat.
    far_raw = g["far"] + far_stock
    frames = {
        # W down, the far face's bar face at the fixed jaw: X along +Y model.
        "width": _frame([-half, -seat_skim, far_raw], [0, 0, 1], [1, 0, 0]),
        # The far face's bar face down, W at the fixed jaw, the seat end right.
        "depth": _frame([-half, -seat_skim, far_raw], [-1, 0, 0], [0, 0, -1]),
        # Upright, the seat up, W at the fixed jaw, the near end left.
        "seat": _frame([-half, 0.0, g["near"]], [-1, 0, 0], [0, -1, 0]),
        # As "depth", X0 the faced seat.
        "step": _frame([-half, 0.0, far_raw], [-1, 0, 0], [0, 0, -1]),
        # Upright on the seat, W at the fixed jaw, the near end right.
        "top": _frame([-half, 0.0, g["near"]], [-1, 0, 0], [0, 1, 0]),
        # Far face up, the seat at the fixed jaw, X0 the centre.
        "outline": _frame([0.0, 0.0, g["near"]], [0, -1, 0], [0, 0, 1]),
    }
    stocks = {
        "width": ((0.0, blank_max), (-blank_z, 0.0), (0.0, blank_x)),
        "depth": ((-blank_max, 0.0), (-width, 0.0), (0.0, blank_z)),
        "seat": ((0.0, height), (-width, 0.0), (-upright_top, seat_skim)),
        "step": ((-upright_top, 0.0), (-width, 0.0), (0.0, height)),
        "top": ((-height, 0.0), (-width, 0.0), (0.0, upright_top)),
        "outline": ((-half, half), (-top, 0.0), (0.0, height)),
    }
    # Every frame lands the part where its stock says.
    for key, frame in frames.items():
        (x0, x1), (y0, y1), (z0, z1) = stocks[key]
        for corner_point in (
            [-half, 0.0, g["near"]],
            [half, foot_top, g["far"]],
        ):
            x, y, z = _to(frame, corner_point)
            if not (
                x0 - 1e-6 <= x <= x1 + 1e-6
                and y0 - 1e-6 <= y <= y1 + 1e-6
                and z0 - 1e-6 <= z <= z1 + 1e-6
            ):
                raise ValueError(f"{key}: the part is not inside its stock")

    def xy(frame: str, point: list[float]) -> list[float]:
        x, y, _z = _to(frames[frame], point)
        return [_r(x), _r(y)]

    hold_xy = xy("seat", hold["at"])
    bore_xy = xy("step", [0.0, g["crown_y"], g["far"]])
    apex_xy = xy("top", apex["at"])
    # The bore clears the step's stacks.
    if not (-width + t < bore_xy[1] - dv / 2 and bore_xy[1] + dv / 2 < -t):
        raise ValueError(f"the bore at Y {bore_xy[1]} reaches a stack ({t} thick)")

    em_tool = {
        "tool": "em-half",
        "dia": em,
        "shape": "endmill",
        "flutes": 3,
        "rpm": face_rpm,
        "feed": face_feed,
        "plunge": face_feed,
    }

    def spot_tool() -> dict[str, Any]:
        return {
            "tool": "spot",
            "dia": CENTRE_DRILL["body_mm"],
            "shape": "drill",
            "tip_angle": CENTRE_DRILL["point_deg"],
            "rpm": spot_rpm,
            "feed": spot_feed,
            "plunge": spot_feed,
        }

    def drill_tool(tool: str, dia: float, rpm: float, feed: float) -> dict[str, Any]:
        return {
            "tool": tool,
            "dia": dia,
            "shape": "drill",
            "tip_angle": DRILL_POINT_DEG,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
        }

    def run(x: tuple[float, float]) -> tuple[float, float]:
        return (x[0] - r - APPROACH_MM, x[1] + r + APPROACH_MM)

    width_ys = _stations((-blank_z, 0.0), r, step_max)
    side_ys = _stations((-width, 0.0), r, step_max)
    far_ys = _stations((-top, 0.0), r, far_step_max)
    strap_x = (-height, -(depth - strap))
    faces = {
        "width": (
            "width",
            width_levels,
            blank_x,
            run((0.0, blank_max)),
            width_ys,
            (-blank_z, 0.0),
            blank_max,
        ),
        "depth": (
            "depth",
            depth_levels,
            blank_z,
            run((-blank_max, 0.0)),
            side_ys,
            (-width, 0.0),
            blank_max,
        ),
        "seat": (
            "seat",
            [0.0],
            seat_skim,
            run((0.0, height)),
            side_ys,
            (-width, 0.0),
            height,
        ),
        "top": (
            "top",
            top_levels,
            upright_top,
            run(strap_x),
            side_ys,
            (-width, 0.0),
            strap_x[1] - strap_x[0],
        ),
        "far_face": (
            "outline",
            far_levels,
            height,
            run((-half, half)),
            far_ys,
            (-top, 0.0),
            width,
        ),
    }

    # The outline in the PA07 frame, in cutting order: up the side at +X
    # (the model's west flank), over the crown, down the other: clockwise
    # seen from above, climb with the clockwise spindle.
    def model_xy(point: tuple[float, float]) -> tuple[float, float]:
        x, y, _z = _to(frames["outline"], [point[0], point[1], g["far"]])
        return (x, y)

    (rx, ry), (tx, ty) = g["root"], g["tangent"]
    elements = [
        {
            "name": "west flank",
            "start": model_xy((-rx, ry)),
            "end": model_xy((-tx, ty)),
        },
        {
            "name": "crown",
            "start": model_xy((-tx, ty)),
            "end": model_xy((tx, ty)),
            "centre": model_xy((0.0, g["crown_y"])),
        },
        {"name": "east flank", "start": model_xy((tx, ty)), "end": model_xy((rx, ry))},
    ]
    for element in elements:
        element["start"] = [_r(v) for v in element["start"]]
        element["end"] = [_r(v) for v in element["end"]]
        if "centre" in element:
            element["centre"] = [_r(v) for v in element["centre"]]
        element["tol"] = OUTLINE_TOL_MM

    def offset_line(element: dict, off: float) -> tuple[list[float], list[float]]:
        (sx, sy), (ex, ey) = element["start"], element["end"]
        length = math.hypot(ex - sx, ey - sy)
        # Clockwise travel: the part on the right, outward on the left.
        nx, ny = -(ey - sy) / length, (ex - sx) / length
        return [sx + off * nx, sy + off * ny], [ex + off * nx, ey + off * ny]

    def outline_pass(off: float, z: float) -> list[str]:
        (s1, e1), (s3, e3) = (
            offset_line(elements[0], off),
            offset_line(elements[2], off),
        )
        cx, cy = elements[1]["centre"]
        safe, clear = _r(height + SAFE_MM), _r(height + CLEAR_MM)
        return [
            f"G0 X{_r(s1[0]):.3f} Y{_r(s1[1]):.3f}",
            f"G0 Z{safe:.3f}",
            f"G1 Z{_r(z):.3f} F{{feed}}",
            f"G1 X{_r(e1[0]):.3f} Y{_r(e1[1]):.3f} F{{feed}}",
            f"G2 X{_r(s3[0]):.3f} Y{_r(s3[1]):.3f} I{_r(cx - e1[0]):.3f} J{_r(cy - e1[1]):.3f} F{{feed}}",
            f"G1 X{_r(e3[0]):.3f} Y{_r(e3[1]):.3f} F{{feed}}",
            f"G0 Z{clear:.3f}",
        ]

    rough_off, finish_off = r + stock, r
    outline_lines = [f"G0 Z{_r(height + CLEAR_MM):.3f}"]
    for z in rough_levels:
        outline_lines += outline_pass(rough_off, z)
    outline_lines += outline_pass(finish_off, outline_bottom)
    # The offset arcs' ends agree with their centre to the post's places.
    for off in (rough_off, finish_off):
        (_s, e1), (s3, _e) = (
            offset_line(elements[0], off),
            offset_line(elements[2], off),
        )
        centre = elements[1]["centre"]
        if abs(math.dist(e1, centre) - math.dist(s3, centre)) > 0.002:
            raise ValueError("the outline's offset flanks do not meet its offset crown")

    jobs = []
    for key, (frame, levels, face_top, xs, ys, _y, _span) in faces.items():
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
                        _face(levels, face_top, xs, ys),
                    ]
                ],
            }
        )
    # PA07 is one Job: the far face, then the outline, same tool and speed.
    outline_job = jobs[-1]
    outline_job["label"] = "far face and outline"
    outline_job.update(rpm=outline_rpm, feed=outline_feed, plunge=outline_feed)
    outline_job["ops"].append(
        ["outline", "profile the flanks and the crown", outline_lines]
    )
    # Along -Y, from beside the fixed jaw (W) to beside the moving jaw (E):
    # both plunges stand over a jaw, above its top (the step's floor is).
    step_y = (r + APPROACH_MM, -width - r - APPROACH_MM)
    jobs.append(
        {
            **em_tool,
            "rpm": step_rpm,
            "feed": step_feed,
            "plunge": step_feed,
            "frame": "step",
            "label": "step",
            "stock": stocks["step"],
            "ops": [
                [
                    "step",
                    "mill the step to the strap",
                    _step(step_levels, height, step_xs, step_y),
                ]
            ],
        }
    )
    seat_clear = seat_skim + CLEAR_MM
    jobs += [
        {
            **spot_tool(),
            "frame": "seat",
            "label": "hold spot",
            "stock": stocks["seat"],
            "ops": [
                [
                    "hold_spot",
                    "spot the hold-down hole",
                    _spot(
                        hold_xy, 0.0, -_spot_depth(p["hold_spot_dia_mm"]), seat_clear
                    ),
                ]
            ],
        },
        {
            **drill_tool("drill-15", d15, hold_rpm, hold_feed),
            "frame": "seat",
            "label": "hold drill",
            "stock": stocks["seat"],
            "ops": [
                [
                    "hold_drill",
                    "drill the hold-down hole #15",
                    _pecked(hold_xy, 0.0, hold_tip, None, seat_clear),
                ]
            ],
        },
    ]
    step_clear = height + CLEAR_MM
    jobs += [
        {
            **spot_tool(),
            "frame": "step",
            "label": "bore spot",
            "stock": stocks["step"],
            "ops": [
                [
                    "bore_spot",
                    "spot the bore",
                    _spot(
                        bore_xy,
                        floor,
                        floor - _spot_depth(p["bore_spot_dia_mm"]),
                        step_clear,
                    ),
                ]
            ],
        },
        {
            **drill_tool("drill-v", dv, bore_rpm, bore_feed),
            "frame": "step",
            "label": "bore drill",
            "stock": stocks["step"],
            "ops": [
                [
                    "bore_drill",
                    "drill the bore V",
                    _pecked(bore_xy, floor, bore_tip, None, step_clear),
                ]
            ],
        },
    ]
    top_clear = top + CLEAR_MM
    jobs += [
        {
            **spot_tool(),
            "frame": "top",
            "label": "apex spot",
            "stock": stocks["top"],
            "ops": [
                [
                    "apex_spot",
                    "spot the apex",
                    _spot(
                        apex_xy,
                        top,
                        top - _spot_depth(p["apex_spot_dia_mm"]),
                        top_clear,
                    ),
                ]
            ],
        },
        {
            **drill_tool("drill-43", d43, apex_rpm, apex_feed),
            "frame": "top",
            "label": "apex drill",
            "stock": stocks["top"],
            "ops": [
                [
                    "apex_drill",
                    "drill the apex hole #43 into the bore",
                    _pecked(apex_xy, top, apex_tip, peck, top_clear),
                ]
            ],
        },
    ]

    # The tap file: the tap guide loaded by its own M6 (its %msg names the
    # hole), Z to the machine's top in machine coordinates before any XY (the
    # operator left Z jogged down after the last tool change), over the hole,
    # M30: the controller ends Idle, so the operator can jog the guide's point
    # down into the wrench.
    manual = {
        "tap_apex": {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": "SPINDLE STAYS OFF. NEXT: 4-40 TAP IN THE APEX HOLE",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{apex_xy[0]:.3f} Y{apex_xy[1]:.3f}",
                "(4-40 TAP IN THE APEX HOLE. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND INTO THE BORE TO THE NOTED DRO Z, PUSHING THE POINT HOME EACH 1/2 IN,"
                " READ WITH THE POINT PUSHED HOME. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": apex_xy,
        }
    }

    # Keep-outs. Lying: the jaws beside the gripped span from the stacks' top
    # to the jaw top, across the jaw width. Upright: the jaws grip the sides
    # from the parallels' top to the jaw top. PA07: the fixed jaw behind the
    # seat, the moving jaw's body under the strap from the foot top out.
    jaw_w = p["vise_jaw_width_mm"]

    def jaws(
        z_top: float,
        x: tuple[float, float],
        y: tuple[float, float],
        body: float = JAW_DEPTH_MM,
    ) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - jaw_w / 2, mid + jaw_w / 2)
        return [
            _box("moving jaw", span, (y[0] - body, y[0]), z_top),
            _box("fixed jaw", span, (y[1], y[1] + JAW_DEPTH_MM), z_top),
        ]

    def stacks(x: tuple[float, float], y: tuple[float, float]) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - PARALLEL_LENGTH_MM / 2, mid + PARALLEL_LENGTH_MM / 2)
        return [
            _box("moving-jaw parallels", span, (y[0], y[0] + t), 0.0),
            _box("fixed-jaw parallels", span, (y[1] - t, y[1]), 0.0),
        ]

    seat_jaw_top = upright_grip - (blank_min - seat_skim)
    keep = {
        "width": jaws(lying_grip, (0.0, blank_max), (-blank_z, 0.0)),
        "depth": jaws(lying_grip, (-blank_max, 0.0), (-width, 0.0)),
        "seat": jaws(seat_jaw_top, (0.0, height), (-width, 0.0)),
        "step": jaws(step_grip, (-upright_top, 0.0), (-width, 0.0))
        # The foot: nothing below the near end's top on the seat's side of
        # the foot top.
        + [_box("foot", (-foot_top, 0.0), (-width, 0.0), height)],
        "top": jaws(upright_grip, (-height, 0.0), (-width, 0.0)),
        "outline": jaws(foot_grip, (-half, half), (-foot_top, 0.0), JAW_BODY_MM)
        + [
            _box(
                "foot parallels",
                (-PARALLEL_LENGTH_MM / 2, PARALLEL_LENGTH_MM / 2),
                (-t, 0.0),
                0.0,
            ),
        ],
    }
    bore_keep = keep["step"] + stacks((-upright_top, 0.0), (-width, 0.0))
    # In PA07 the foot stands to the far face: the outline's cutter misses it.
    outline_keep = keep["outline"] + [
        _box("foot", (-half, half), (-foot_top, 0.0), depth)
    ]

    tn = numbers
    expect: list[list[Any]] = []

    def face_checks(key: str, boxes: list[dict[str, Any]]) -> list[list[Any]]:
        _frame_key, levels, face_top, _xs, _ys, y, span = faces[key]
        engagement = far_step_max if key == "far_face" else step_max
        return [
            *[
                [
                    "face_passes",
                    {
                        "z": _r(z),
                        "y": list(y),
                        "max_engagement": engagement,
                        "radius": r,
                        "span": span,
                        "overhang": FACE_OVERHANG_MM,
                    },
                ]
                for z in levels
            ],
            ["rapids_clear", {"z_top": face_top}],
            ["air_feed", {"z_top": face_top}],
            ["keep_out", {"radius": r, "boxes": boxes}],
        ]

    def hole_checks(
        centres: list[list[float]],
        hole_top: float,
        bottom: float,
        radius: float,
        boxes: list[dict[str, Any]],
    ) -> list[list[Any]]:
        return [
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": hole_top, "open_holes": centres}],
            ["vertical_below_top", {"z_top": hole_top}],
            ["air_feed", {"z_top": hole_top}],
            ["keep_out", {"radius": radius, "boxes": boxes}],
        ]

    for name, key in (("PA01_width", "width"), ("PA02_depth", "depth")):
        face_top = faces[key][2]
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": face_top, "tools": [tn["em-half"]], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[face_rpm]]}],
            [name, "pauses", {"z_top": face_top, "count": 0}],
            [name, "depth", {"z_min": _r(faces[key][1][-1])}],
            *[[name, check, kwargs] for check, kwargs in face_checks(key, keep[key])],
        ]

    # The step's floor: every point of it from the open end to the foot top.
    floor_points = [
        [_r(-upright_top + (upright_top - foot_top) * i / 8), _r(-width * j / 4)]
        for i in range(9)
        for j in range(5)
    ]
    spot_r = CENTRE_DRILL["body_mm"] / 2
    sections = {
        "PA03_seat": (
            seat_skim,
            [tn["em-half"], tn["spot"], tn["drill-15"]],
            [[face_rpm], [spot_rpm], [hold_rpm]],
            hold_tip,
            [
                face_checks("seat", keep["seat"]),
                hole_checks(
                    [hold_xy],
                    0.0,
                    -_spot_depth(p["hold_spot_dia_mm"]),
                    spot_r,
                    keep["seat"],
                ),
                hole_checks([hold_xy], 0.0, hold_tip, d15 / 2, keep["seat"]),
            ],
        ),
        "PA04_step_bore": (
            height,
            [tn["em-half"], tn["spot"], tn["drill-v"]],
            [[step_rpm], [spot_rpm], [bore_rpm]],
            bore_tip,
            [
                [
                    [
                        "side_passes",
                        {
                            "axis": "X",
                            "final": _r(final_x),
                            "raw": _r(raw_x),
                            "max_step": station,
                            "direction": -1.0,
                            "cut": "conventional",
                            "span": width,
                            "below_z": height,
                            "max_stepdown": step_level,
                        },
                    ],
                    ["cleared", {"points": floor_points, "radius": r, "z": _r(floor)}],
                    ["rapids_clear", {"z_top": height}],
                    ["air_feed", {"z_top": height}],
                    ["keep_out", {"radius": r, "boxes": keep["step"]}],
                ],
                hole_checks(
                    [bore_xy],
                    floor,
                    floor - _spot_depth(p["bore_spot_dia_mm"]),
                    spot_r,
                    bore_keep,
                ),
                hole_checks([bore_xy], floor, bore_tip, dv / 2, bore_keep),
            ],
        ),
        "PA05_top_apex": (
            upright_top,
            [tn["em-half"], tn["spot"], tn["drill-43"]],
            [[face_rpm], [spot_rpm], [apex_rpm]],
            apex_tip,
            [
                face_checks("top", keep["top"]),
                hole_checks(
                    [apex_xy],
                    top,
                    top - _spot_depth(p["apex_spot_dia_mm"]),
                    spot_r,
                    keep["top"],
                ),
                hole_checks([apex_xy], top, apex_tip, d43 / 2, keep["top"]),
            ],
        ),
    }
    for name, (z_top, tools, speeds, deepest, checks) in sections.items():
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": z_top, "tools": tools, "loads_first": True},
            ],
            [name, "spindle", {"rpm": speeds}],
            [name, "pauses", {"z_top": z_top, "count": 0}],
            [name, "depth", {"z_min": _r(deepest)}],
        ]
        for k, section_checks in enumerate(checks):
            expect += [
                [f"{name}@{k}", check, kwargs] for check, kwargs in section_checks
            ]

    expect += [
        [
            "PA06_apex_tap",
            "tap_stop",
            {"tool": tn["tap-guide"], "at": apex_xy, "machine_top": MACHINE_Z_TOP_MM},
        ],
        ["PA06_apex_tap", "air_feed", {"z_top": top}],
    ]

    name = "PA07_outline"
    expect += [
        [
            name,
            "tool_changes",
            {"z_top": height, "tools": [tn["em-half"]], "loads_first": True},
        ],
        [name, "spindle", {"rpm": [[outline_rpm]]}],
        [name, "pauses", {"z_top": height, "count": 0}],
        [name, "depth", {"z_min": _r(outline_bottom)}],
        *[
            [name, check, kwargs]
            for check, kwargs in face_checks("far_face", keep["outline"])
            if check != "keep_out"
        ],
        [
            name,
            "outline",
            {
                "elements": elements,
                "passes": [
                    {"offset": rough_off, "levels": [_r(z) for z in rough_levels]},
                    {"offset": finish_off, "levels": [_r(outline_bottom)]},
                ],
                "z_top": depth,
                # Clockwise round the crown, the part on the right: climb, as
                # the module docstring says (ball screws).
                "cut": "climb",
                "part": "right",
            },
        ],
        [name, "keep_out", {"radius": r, "boxes": outline_keep}],
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
            doc, f"Pedestal {key}", ctx["step"], frame["origin"], frame["axes"]
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
