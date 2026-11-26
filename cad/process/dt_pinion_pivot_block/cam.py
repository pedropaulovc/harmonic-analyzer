"""FreeCAD CAM recipe for MHA-DT-18, the pinion pivot block.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The block's sizes come
from the feature export (its width, height and depth, the reamed pivot bore,
the F-drilled lift bore and
both hold-down holes); the blank, the skims, face levels, spots, pecks, tips
and the parallels from ``plan.toml`` ``[parameters]`` and ``milling_cuts``;
cutter diameters, speeds and feeds from the shop (``shop/``) and the plan's
authored drill and reamer settings. Every path is written here
(``rt.custom``): straight lines a recipe can state exactly. Typed here,
because neither record carries them: the #2 centre drill's catalogue geometry
(it sets the spot depth), the twist drills' 118° point, the approach, safe and
clearance heights, the face overhang and the vise jaws' depth (keep-out
shapes only).

Route (plan text in ``plan.toml``): one blank of 1/2 x 2-1/4 in 1018 flat,
sawn 1.05-1.15 long, per run; the bar's width is the block's width (X) with
its waste on the ends, the sawn length its height (Y), the bar's thickness
its depth (Z). PB01 (on edge, back face against the fixed jaw) skims a sawn
face to the bottom face B. PB02 (on edge, gripped on the bar's two edges, B
down) faces the top to the height, then spots and drills both #9 hold-down
holes through between the parallels. PB03 (upright, gripped on B and the top)
skims the east bar edge to the east end; PB04 (turned over) faces the west
end to the width. PB05 (lying, gripped on the two ends) faces the front face
to the depth, then spots both bores, drills the pivot bore C and the lift
bore F through, and reams the pivot bore .2510 (owner ruling 2026-11-24,
fit audit question 12; fit audit F26).

Work frames (G54), each set in its setup:
- PB01: X0 the east bar edge (the left end), Y0 the fixed jaw (the back
  face), Z0 the faced bottom face B.
- PB02: X0 the back face, Y0 the fixed jaw (the east bar edge), Z0 the
  parallels' top (B). The hold-downs' stations count from the east bar edge:
  PB03 takes exactly ``east_skim_mm`` off that edge, so they land at their
  drawn stations from the finished ends.
- PB03: X0 the back face, Y0 the fixed jaw (B), Z0 the faced east end.
- PB04: X0 the back face, Y0 the fixed jaw (the top face), Z0 the parallels'
  top (the east end).
- PB05: X0 the bottom face B, Y0 the fixed jaw (the west end), Z0 the
  parallels' top (the back face).

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock; the
reamer is fed in and fed back out, never rapided out of a bore.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_pinion_pivot_block"
COMMENT = "MHA-DT-18 pinion pivot block"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("PB01_bottom", ("bottom_face",)),
    ("PB02_top_holds", (("top_face",), ("hold_spot",), ("hold_drill",))),
    ("PB03_east_end", ("east_end",)),
    ("PB04_width", ("west_end",)),
    (
        "PB05_front_bores",
        (
            ("front_face",),
            ("bore_spot",),
            ("bore_drill",),
            ("lift_drill",),
            ("bore_ream",),
        ),
    ),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, files and gauges are not).
CAM_TOOLS = ("em-half", "spot", "drill-9", "drill-c", "drill-f", "reamer")
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
FACE_CUTS = ("bottom face", "height", "east end", "width", "front face")


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
    the cut itself authors (which the operation's rpm must repeat)."""
    op, record_cut = _op_with_cut(plan, cut)
    if "settings" not in op:
        rpm = _cut(plan, cut, "rpm")
        if float(op["rpm"]) != rpm:
            raise ValueError(f"'{cut}' rpm {rpm:g} is not its operation's {op['rpm']}")
        return rpm, _cut(plan, cut, "feed_mm_min")
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
    feed), each with a full retract to the R plane and a rapid back to just
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


def _ream(xy: tuple[float, float], top: float, tip: float, clear: float) -> list[str]:
    """Feed the reamer from the R plane to ``tip`` and feed it back out to the
    R plane, spindle running: no rapid leaves the bore."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(tip):.3f} F{{feed}}",
        f"G1 Z{r_plane:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


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


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The block's sizes, bores and hold-downs from the export, each checked
    against the frame the recipe assumes: west end to east end along X, the
    bottom face B to the top along Y, the back face Z0 to the front along Z;
    both bores entering the front along −Z, both hold-downs the top along −Y."""
    f = features["features"]

    def plane(name: str, axis: str) -> float:
        face = f[name]["plane"]
        if face["axis"] != axis:
            raise ValueError(f"{name}: expected a plane square to model {axis}")
        return face["value"]

    west, east = plane("west_end", "x"), plane("east_end", "x")
    bottom, top = plane("bottom_face", "y"), plane("top_face", "y")
    back, front = plane("back_face", "z"), plane("front_face", "z")
    sizes = {
        "width": (east - west, f["east_end"]["width_nominal"]),
        "height": (top - bottom, f["top_face"]["height_nominal"]),
        "depth": (front - back, f["front_face"]["depth_nominal"]),
    }
    for name, (span, nominal) in sizes.items():
        if not math.isclose(span, nominal, abs_tol=1e-3):
            raise ValueError(
                f"the faces' {name} {span:.4f} is not the {name} {nominal}"
            )
    if back != 0.0:
        raise ValueError("back_face: expected at model Z0")
    bores = []
    for name, process in (("pivot_bore", "ream"), ("lift_bore", "drill")):
        hole = f[name]
        if (
            hole["axis"] != [0.0, 0.0, -1.0]
            or not math.isclose(hole["at"][2], front, abs_tol=1e-3)
            or hole.get("thru") is not True
            or hole["process"] != process
        ):
            raise ValueError(
                f"{name}: expected {process} through from the front face along -Z"
            )
        bores.append({"name": name, "at": hole["at"], "dia": hole["dia"]})
    holds = []
    for name in ("west_hold_down", "east_hold_down"):
        hole = f[name]
        if (
            hole["axis"] != [0.0, -1.0, 0.0]
            or not math.isclose(hole["at"][1], top, abs_tol=1e-3)
            or hole.get("thru") is not True
        ):
            raise ValueError(
                f"{name}: expected drilled through from the top face along -Y"
            )
        holds.append({"name": name, "at": hole["at"], "dia": hole["dia"]})
    return {
        "west": west,
        "east": east,
        "bottom": bottom,
        "top": top,
        "width": east - west,
        "height": top - bottom,
        "depth": front - back,
        "bores": bores,
        "holds": holds,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    width, height, depth = g["width"], g["height"], g["depth"]

    # The blank: the bar's width along X (its waste on the ends), the sawn
    # length along Y, the bar's thickness along Z.
    w_min, w_max = p["blank_width_min_in"] * IN, p["blank_width_max_in"] * IN
    t_min, t_max = p["blank_thickness_min_in"] * IN, p["blank_thickness_max_in"] * IN
    l_min, l_max = p["blank_length_min_in"] * IN, p["blank_length_max_in"] * IN
    bottom_skim, east_skim = p["bottom_skim_mm"], p["east_skim_mm"]
    if l_min - bottom_skim <= height:
        raise ValueError(
            f"the shortest blank less the bottom skim, {l_min - bottom_skim:.3f}, is not over the height {height:.3f}"
        )
    if w_min - east_skim <= width:
        raise ValueError(
            f"the narrowest bar less the east skim, {w_min - east_skim:.3f}, is not over the width {width:.3f}"
        )
    if t_min <= depth:
        raise ValueError(
            f"the thinnest bar {t_min:.3f} leaves nothing to face to the depth {depth:.3f}"
        )
    edge_top = l_max - bottom_skim
    upright_top = w_max - east_skim
    _agree(plan, "edge_top_max_mm", edge_top)
    _agree(plan, "upright_top_max_mm", upright_top)
    _agree(plan, "front_top_max_mm", t_max)

    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    d9 = _shop_tool(plan, shop, "drill-9")["diameter_mm"]
    dc = _shop_tool(plan, shop, "drill-c")["diameter_mm"]
    df = _shop_tool(plan, shop, "drill-f")["diameter_mm"]
    dr = _shop_tool(plan, shop, "reamer")["diameter_mm"]
    r = em / 2
    for hole in g["holds"]:
        if not hole["dia"][0] <= d9 <= hole["dia"][1]:
            raise ValueError(f"#9 Ø{d9} is outside {hole['name']}'s band {hole['dia']}")
    pivot_bore, lift_bore = g["bores"]
    if not pivot_bore["dia"][0] <= dr <= pivot_bore["dia"][1]:
        raise ValueError(f"reamer Ø{dr} is outside pivot_bore's band {pivot_bore['dia']}")
    if not lift_bore["dia"][0] <= df <= lift_bore["dia"][1]:
        raise ValueError(f"F drill Ø{df} is outside lift_bore's band {lift_bore['dia']}")
    if not p["spot_dia_mm"] < dc < dr:
        raise ValueError("the spot, the C drill and the reamer are not in rising order")
    if not p["spot_dia_mm"] < df:
        raise ValueError("the spot is not under the F drill: it would chamfer the bore")
    step_max = p["face_stepover_max_mm"]
    level_max = p["face_step_max_mm"]
    face_rpm, face_feed = _setting(plan, shop, "bottom face")
    for name in FACE_CUTS:
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), em, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' cutter Ø{_cut(plan, name, 'cutter_dia_mm')}, the end mill is Ø{em}"
            )
        if _setting(plan, shop, name) != (face_rpm, face_feed):
            raise ValueError(f"'{name}' runs at another setting than 'bottom face'")
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), step_max, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' radial_woc_mm is not process.face_stepover_max_mm"
            )
    if not math.isclose(
        _cut(plan, "bottom face", "axial_doc_mm"), bottom_skim, abs_tol=1e-6
    ):
        raise ValueError("'bottom face' axial_doc_mm is not process.bottom_skim_mm")
    for name in ("height", "east end", "width", "front face"):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), level_max, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not process.face_step_max_mm")
    height_levels = _levels(edge_top, height, level_max)
    east_levels = _levels(east_skim, 0.0, level_max)
    width_levels = _levels(upright_top, width, level_max)
    depth_levels = _levels(t_max, depth, level_max)

    # Holes: spot under the drill (no chamfer at the mouth); the #9 pecked
    # with full retracts, the C drill in one feed; each until its full
    # diameter is past the far face, into the gap between the parallels; the
    # reamer fed in until its full diameter is past the back face and out.
    spot_rpm, spot_feed = _setting(plan, shop, "hold spot")
    if _setting(plan, shop, "bore spot") != (spot_rpm, spot_feed):
        raise ValueError("'bore spot' runs at another setting than 'hold spot'")
    hold_rpm, hold_feed = _setting(plan, shop, "hold drill")
    bore_rpm, bore_feed = _setting(plan, shop, "bore drill")
    lift_rpm, lift_feed = _setting(plan, shop, "lift drill")
    ream_rpm, ream_feed = _setting(plan, shop, "bore ream")
    for name in ("hold spot", "bore spot"):
        if not math.isclose(
            _cut(plan, name, "cutter_dia_mm"), p["spot_dia_mm"], abs_tol=1e-6
        ):
            raise ValueError(f"'{name}' cutter_dia_mm is not process.spot_dia_mm")
    if p["spot_dia_mm"] >= d9:
        raise ValueError(
            "the spot is not under the #9 drill: it would chamfer the hole"
        )
    for name, dia in (
        ("hold drill", d9),
        ("bore drill", dc),
        ("lift drill", df),
        ("bore ream", dr),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not its tool's Ø{dia}")
    spot_depth = _spot_depth(p["spot_dia_mm"])
    peck = p["peck_mm"]
    op = _op_with_cut(plan, "hold drill")[0]
    if op["peck"] != {"step_mm": peck, "retract": "full"}:
        raise ValueError("'hold drill' peck is not process.peck_mm with full retract")
    if op["hole_depth_mm"] != "{{cad.top_face_height_mm}}":
        raise ValueError("'hold drill' hole_depth_mm is not {{cad.top_face_height_mm}}")
    for name in ("bore drill", "lift drill"):
        op = _op_with_cut(plan, name)[0]
        if op["peck"] != "none" or op["hole_depth_mm"] != "{{cad.front_face_depth_mm}}":
            raise ValueError(
                f"'{name}' is not one feed through {{{{cad.front_face_depth_mm}}}}"
            )
    if depth / dc > 3:
        raise ValueError("the C drill's L/D is over 3: it would need pecks")
    past = p["drill_past_mm"]
    hold_tip = -(past + _point(d9))
    bore_tip = -(past + _point(dc))
    lift_tip = -(past + _point(df))
    _agree(plan, "hold_tip_height_mm", hold_tip)
    _agree(plan, "bore_tip_height_mm", bore_tip)
    _agree(plan, "lift_tip_height_mm", lift_tip)
    ream_tip = p["ream_tip_height_mm"]
    if not bore_tip < ream_tip < -past:
        raise ValueError(
            f"reamer tip Z {ream_tip:.3f}: not past the back face by {past} or below the C drill's tip {bore_tip:.3f}"
        )
    import cam_nc

    if -ream_tip <= cam_nc.ream_full_diameter_past_min_mm(plan, "reamer"):
        raise ValueError(
            f"reamer tip Z {ream_tip:.3f}: its full diameter does not reach the back face (cnc.ream-full-diameter)"
        )
    # The reamer's flat end runs out into the gap between the parallels.
    cam_nc.ream_end_face_clear(plan, "reamer", dr, ream_tip, dc, -past, -math.inf)
    # The sheet's re-ream MDI runs at the program's R plane and parks at its
    # clearance.
    _agree(plan, "ream_r_plane_mm", depth + SAFE_MM)
    _agree(plan, "ream_clear_mm", depth + CLEAR_MM)

    # Vise: on edge and lying on the 1 in parallels and the 1-1/2 in stacks,
    # upright on the 1/2 in parallels.
    edge_grip = p["vise_jaw_height_mm"] - p["parallel_height_mm"]
    upright_grip = p["vise_jaw_height_mm"] - p["short_parallel_height_mm"]
    lying_grip = p["vise_jaw_height_mm"] - p["riser_height_mm"]
    _agree(plan, "edge_grip_mm", edge_grip)
    _agree(plan, "upright_grip_mm", upright_grip)
    _agree(plan, "lying_grip_mm", lying_grip)
    t = p["parallel_thickness_mm"]

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)). The raw east bar edge
    # stands east_skim beyond the east end; the raw bottom face bottom_skim
    # below B; the back face (as bought) is model Z0 throughout.
    raw_east = g["east"] + east_skim
    frames = {
        # On edge, sawn face up, the back face against the fixed jaw: the
        # east bar edge lands at the left end (X0).
        "bottom": _frame([raw_east, g["bottom"], 0.0], [0, 0, -1], [0, -1, 0]),
        # On edge, B down, the east bar edge against the fixed jaw: the back
        # face at the left (X0).
        "top": _frame([raw_east, g["bottom"], 0.0], [1, 0, 0], [0, 1, 0]),
        # Upright, the east edge up, B against the fixed jaw.
        "east": _frame([g["east"], g["bottom"], 0.0], [0, -1, 0], [1, 0, 0]),
        # Upright, the east end down, the top against the fixed jaw.
        "west": _frame([g["east"], g["top"], 0.0], [0, 1, 0], [-1, 0, 0]),
        # Lying, back face down, the west end against the fixed jaw.
        "front": _frame([g["west"], g["bottom"], 0.0], [-1, 0, 0], [0, 0, 1]),
    }
    for key, frame in frames.items():
        # Each frame's back face is at X0 or (PB01) the jaw at Y0, its part to +X.
        corner = _to(frame, [g["east"], g["bottom"], 0.0])
        if key == "bottom" and not math.isclose(corner[1], 0.0, abs_tol=1e-6):
            raise ValueError("bottom: the back face is not at Y0")
        if key in ("top", "east", "west") and not math.isclose(
            corner[0], 0.0, abs_tol=1e-6
        ):
            raise ValueError(f"{key}: the back face is not at X0")
    stocks = {
        "bottom": ((0.0, w_max), (-t_max, 0.0), (-(l_max - bottom_skim), bottom_skim)),
        "top": ((0.0, t_max), (-w_max, 0.0), (0.0, edge_top)),
        "east": ((0.0, t_max), (-height, 0.0), (-(w_max - east_skim), east_skim)),
        "west": ((0.0, t_max), (-height, 0.0), (0.0, upright_top)),
        "front": ((0.0, height), (-width, 0.0), (0.0, t_max)),
    }
    holds = []
    for hole in g["holds"]:
        x, y, z = _to(frames["top"], hole["at"])
        if not math.isclose(z, height, abs_tol=1e-6):
            raise ValueError(
                f"{hole['name']} does not enter at the top in the PB02 frame"
            )
        holds.append([_r(x), _r(y)])
    # The stations the sheet prints for PB02, from the east bar edge.
    _agree(plan, "hold_west_y_mm", holds[0][1])
    _agree(plan, "hold_east_y_mm", holds[1][1])
    bores = []
    for hole in g["bores"]:
        x, y, z = _to(frames["front"], hole["at"])
        if not math.isclose(z, depth, abs_tol=1e-6):
            raise ValueError(
                f"{hole['name']} does not enter at the front in the PB05 frame"
            )
        bores.append([_r(x), _r(y)])
    pivots, lifts = bores[:1], bores[1:]
    # The holes clear the parallels: PB02's against the bar edges (the
    # narrowest bar puts the moving jaw's nearest), PB05's against the ends.
    for x, y in holds:
        if not (-w_min + t < y - d9 / 2 and y + d9 / 2 < -t):
            raise ValueError(f"the hold-down at Y {y} reaches a parallel ({t} thick)")
    for x, y in bores:
        big = max(dr, df)
        if not (-width + t < y - big / 2 and y + big / 2 < -t):
            raise ValueError(f"the bore at Y {y} reaches a parallel ({t} thick)")

    em_tool = {
        "tool": "em-half",
        "dia": em,
        "shape": "endmill",
        "flutes": 3,
        "rpm": face_rpm,
        "feed": face_feed,
        "plunge": face_feed,
    }

    def drill_tool(
        tool: str, dia: float, rpm: float, feed: float, angle: float
    ) -> dict:
        return {
            "tool": tool,
            "dia": dia,
            "shape": "drill",
            "tip_angle": angle,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
        }

    spot_tool = drill_tool(
        "spot", CENTRE_DRILL["body_mm"], spot_rpm, spot_feed, CENTRE_DRILL["point_deg"]
    )
    hold_tool = drill_tool("drill-9", d9, hold_rpm, hold_feed, DRILL_POINT_DEG)
    bore_tool = drill_tool("drill-c", dc, bore_rpm, bore_feed, DRILL_POINT_DEG)
    lift_tool = drill_tool("drill-f", df, lift_rpm, lift_feed, DRILL_POINT_DEG)
    ream_tool = drill_tool("reamer", dr, ream_rpm, ream_feed, DRILL_POINT_DEG)

    def run(x: tuple[float, float]) -> tuple[float, float]:
        return (x[0] - r - APPROACH_MM, x[1] + r + APPROACH_MM)

    # (levels, stock top, cutter-centre X ends, Y stations, face Y, part X span)
    faces = {
        "bottom_face": (
            [0.0],
            bottom_skim,
            run((0.0, w_max)),
            _stations((-t_max, 0.0), r, step_max),
            (-t_max, 0.0),
            w_max,
        ),
        "top_face": (
            height_levels,
            edge_top,
            run((0.0, t_max)),
            _stations((-w_max, 0.0), r, step_max),
            (-w_max, 0.0),
            t_max,
        ),
        "east_end": (
            east_levels,
            east_skim,
            run((0.0, t_max)),
            _stations((-height, 0.0), r, step_max),
            (-height, 0.0),
            t_max,
        ),
        "west_end": (
            width_levels,
            upright_top,
            run((0.0, t_max)),
            _stations((-height, 0.0), r, step_max),
            (-height, 0.0),
            t_max,
        ),
        "front_face": (
            depth_levels,
            t_max,
            run((0.0, height)),
            _stations((-width, 0.0), r, step_max),
            (-width, 0.0),
            height,
        ),
    }
    frame_of = {
        "bottom_face": "bottom",
        "top_face": "top",
        "east_end": "east",
        "west_end": "west",
        "front_face": "front",
    }
    jobs = []
    for key, (levels, top, xs, ys, _y, _span) in faces.items():
        jobs.append(
            {
                **em_tool,
                "frame": frame_of[key],
                "label": key.replace("_", " "),
                "stock": stocks[frame_of[key]],
                "ops": [
                    [
                        key,
                        f"face the {key.replace('_', ' ')}",
                        _face(levels, top, xs, ys),
                    ]
                ],
            }
        )
    hold_clear = height + CLEAR_MM
    bore_clear = depth + CLEAR_MM
    holes_jobs = (
        (
            spot_tool,
            "top",
            "hold_spot",
            "spot both hold-downs",
            holds,
            [
                ln
                for xy in holds
                for ln in _spot(xy, height, height - spot_depth, hold_clear)
            ],
        ),
        (
            hold_tool,
            "top",
            "hold_drill",
            "drill both hold-downs #9",
            holds,
            [
                ln
                for xy in holds
                for ln in _pecked(xy, height, hold_tip, peck, hold_clear)
            ],
        ),
        (
            spot_tool,
            "front",
            "bore_spot",
            "spot both bores",
            bores,
            [
                ln
                for xy in bores
                for ln in _spot(xy, depth, depth - spot_depth, bore_clear)
            ],
        ),
        (
            bore_tool,
            "front",
            "bore_drill",
            "drill the pivot bore C",
            pivots,
            [
                ln
                for xy in pivots
                for ln in _pecked(xy, depth, bore_tip, None, bore_clear)
            ],
        ),
        (
            lift_tool,
            "front",
            "lift_drill",
            "drill the lift bore F",
            lifts,
            [
                ln
                for xy in lifts
                for ln in _pecked(xy, depth, lift_tip, None, bore_clear)
            ],
        ),
        (
            ream_tool,
            "front",
            "bore_ream",
            "ream the pivot bore .2510",
            pivots,
            [ln for xy in pivots for ln in _ream(xy, depth, ream_tip, bore_clear)],
        ),
    )
    for tool, frame, key, label, _centres, lines in holes_jobs:
        jobs.append(
            {
                **tool,
                "frame": frame,
                "label": label,
                "stock": stocks[frame],
                "ops": [[key, label, lines]],
            }
        )

    # Keep-outs: the jaws beside the gripped span from the parallels' top to
    # the jaw top, across the jaw width (a jaw's face is placed where the
    # part's extreme can put it); the parallels under the part's gripped edges.
    jaw_w = p["vise_jaw_width_mm"]

    def jaws(
        z_top: float, x: tuple[float, float], moving: tuple[float, float]
    ) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - jaw_w / 2, mid + jaw_w / 2)
        return [
            _box("moving jaw", span, (moving[0] - JAW_DEPTH_MM, moving[1]), z_top),
            _box("fixed jaw", span, (0.0, JAW_DEPTH_MM), z_top),
        ]

    def parallels(
        x: tuple[float, float], moving: tuple[float, float]
    ) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - PARALLEL_LENGTH_MM / 2, mid + PARALLEL_LENGTH_MM / 2)
        return [
            _box("moving-jaw parallel", span, (moving[0], moving[1] + t), 0.0),
            _box("fixed-jaw parallel", span, (-t, 0.0), 0.0),
        ]

    keep = {
        "bottom_face": jaws(
            edge_grip - (l_min - bottom_skim), (0.0, w_max), (-t_max, -t_min)
        ),
        "top_face": jaws(edge_grip, (0.0, t_max), (-w_max, -w_min)),
        "east_end": jaws(
            upright_grip - (w_min - east_skim), (0.0, t_max), (-height, -height)
        ),
        "west_end": jaws(upright_grip, (0.0, t_max), (-height, -height)),
        "front_face": jaws(lying_grip, (0.0, height), (-width, -width)),
    }
    hold_keep = keep["top_face"] + parallels((0.0, t_max), (-w_max, -w_min))
    bore_keep = keep["front_face"] + parallels((0.0, height), (-width, -width))

    tn = numbers
    expect: list[list[Any]] = []

    def face_checks(key: str) -> list[list[Any]]:
        levels, top, _xs, _ys, y, span = faces[key]
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

    def hole_checks(
        centres: list[list[float]],
        top: float,
        bottom: float,
        radius: float,
        boxes: list,
    ) -> list[list[Any]]:
        return [
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": top, "open_holes": centres}],
            ["vertical_below_top", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": radius, "boxes": boxes}],
        ]

    single = {
        "PB01_bottom": "bottom_face",
        "PB03_east_end": "east_end",
        "PB04_width": "west_end",
    }
    for name, key in single.items():
        top = faces[key][1]
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
    spot_r = CENTRE_DRILL["body_mm"] / 2
    name = "PB02_top_holds"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": edge_top,
                "tools": [tn["em-half"], tn["spot"], tn["drill-9"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[face_rpm], [spot_rpm], [hold_rpm]]}],
        [name, "pauses", {"z_top": edge_top, "count": 0}],
        [name, "depth", {"z_min": _r(hold_tip)}],
    ]
    for k, checks in enumerate(
        (
            face_checks("top_face"),
            hole_checks(holds, height, height - spot_depth, spot_r, hold_keep),
            hole_checks(holds, height, hold_tip, d9 / 2, hold_keep),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]
    name = "PB05_front_bores"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": t_max,
                "tools": [
                    tn["em-half"],
                    tn["spot"],
                    tn["drill-c"],
                    tn["drill-f"],
                    tn["reamer"],
                ],
                "loads_first": True,
            },
        ],
        [
            name,
            "spindle",
            {"rpm": [[face_rpm], [spot_rpm], [bore_rpm], [lift_rpm], [ream_rpm]]},
        ],
        [name, "pauses", {"z_top": t_max, "count": 0}],
        [name, "depth", {"z_min": _r(min(bore_tip, lift_tip))}],
    ]
    for k, checks in enumerate(
        (
            face_checks("front_face"),
            hole_checks(bores, depth, depth - spot_depth, spot_r, bore_keep),
            hole_checks(pivots, depth, bore_tip, dc / 2, bore_keep),
            hole_checks(lifts, depth, lift_tip, df / 2, bore_keep),
            [
                *hole_checks(pivots, depth, ream_tip, dr / 2, bore_keep),
                ["feed_out", {"z_top": depth}],
            ],
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": frames,
        "names": names,
        "numbers": numbers,
        "jobs": jobs,
        "manual": {},
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
            doc, f"Pivot block {key}", ctx["step"], frame["origin"], frame["axes"]
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
