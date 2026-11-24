"""FreeCAD CAM recipe for MHA-MG-08, the wheel bar.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The bar's sizes come
from the feature export (its length, height and depth bands, the four
holes' sizes, stations and row); the blank, the top face's cut, face levels,
end passes, spots and drill depths, the two holds and the stacks
from ``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter diameters
and end-mill speeds from the shop (``shop/``), the drills'
speeds from the plan's operations. Every path is written here
(``rt.custom``): straight lines a recipe can state exactly. Typed here,
because neither record carries them: the #2 centre drill's catalogue
geometry (it sets the spot depth), the twist drills' 118° point, the
approach, safe and clearance heights, the face overhang, the vise jaws'
depth and the parallels' length (keep-out shapes only), the farthest a hole
may stand out past a jaw's side and the least room the pickup needs.

Route (plan text in ``plan.toml``): one blank of the 3/8 x 1-1/4 in 1018
flat about 9.35 long; the 3/8 thickness is the drawing's depth as supplied.

- WB02 (on edge, edge B down, the front face F at the fixed jaw): edge A
  faced down to the top face T, .840 above B.
- WB03 (lying, F down, T at the fixed jaw, the sawn left end just out past
  the jaws): the left end milled with the cutter's side to X0; the hanger
  hole and the axle bore spotted, drilled #15 and 3/16 (owner ruling
  2026-11-24, fit audit question 18: the axle is bonded, no reamer).
- WB04 (the same hold slid along the jaws, the right end just out past
  them; X0 picked up again on the milled left end): the right end milled to
  the length; both clamp holes spotted and drilled #9.
- WB05 (on edge, T down, the back face at the fixed jaw): edge B faced down
  to the height.

The re-clamp (WB03/WB04): a centred hold leaves each end 1.58 in out past
the 6.247 in jaws, too far for a hole drilled near an end; each hold keeps
its holes within ``HOLE_OUT_MAX_MM`` of a jaw's side, and WB04's X0 is the
same milled end WB03 cut, standing at least ``PICKUP_ROOM_MIN_MM`` out past
the jaws for the edge finder.

Work frames (G54); X0 the finished left end in every one, +X along the bar:
- WB02: Y0 the fixed jaw (F), Z0 the stacks' top (edge B), set from the
  miked width.
- WB03/WB04: Y0 the fixed jaw (T), Z0 the stacks' top (F), set from the
  miked thickness.
- WB05: Y0 the fixed jaw (the back face), Z0 the stacks' top (T), set from
  the miked width.

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock. The
ends are milled with the cutter's side in one-way conventional passes.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "mg_wheel_bar"
COMMENT = "MHA-MG-08 wheel bar"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("WB02_top", ("top_face",)),
    (
        "WB03_left",
        (
            ("left_end",),
            ("left_spot",),
            ("axle_drill",),
            ("hanger_drill",),
        ),
    ),
    ("WB04_right", (("right_end",), ("right_spot",), ("clamp_drill",))),
    ("WB05_height", ("bottom_face",)),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the files and the gauges are not).
CAM_TOOLS = ("em-half", "spot", "drill-3-16", "drill-15", "drill-9")
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
# ends, and end passes this far clear of its faces, so every plunge and
# stepover link is in the air beside it.
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
# The .200 in edge finder's tip radius (tools.edge-finder).
EDGE_FINDER_RADIUS_MM = 0.1 * IN
# The re-clamp's limits (author's): a hole's centre at most this far out
# past a jaw's side in its hold (the #15 .20 from the end, held 1.58 in out,
# bends the bar .002 under its thrust, prechips' estimate; at .50 out the
# cube of the reach makes it under a hundredth of that); the pickup end at
# least this far out past the jaws, so the edge finder and the eye reach it.
HOLE_OUT_MAX_MM = 0.5 * IN
PICKUP_ROOM_MIN_MM = 1.0 * IN
# The least the cutter's lowest face level stands over the jaw tops.
JAW_CLEAR_MIN_MM = 1.0
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# A drill against its hole's printed band: the shop records the drill's
# nominal inch size, the band's floor is that size rounded; anything closer
# than this is the same size.
SIZE_TOL_MM = 0.001


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


def _mid(band: list[float]) -> float:
    return (band[0] + band[1]) / 2


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


def _spot(xy: list[float], top: float, z: float, clear: float) -> list[str]:
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _drilled(xy: list[float], top: float, tip: float, clear: float) -> list[str]:
    """One plunge from the R plane to ``tip`` (no peck: L/D under 2.2), a
    rapid back to the R plane; moves to and from the hole at ``clear``."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(tip):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
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


def _end_stations(raw: float, final: float, max_step: float) -> list[float]:
    """End-face positions from just inside ``raw`` to ``final`` in equal
    radial steps no deeper than ``max_step``, ``final`` last."""
    n = math.ceil(abs(raw - final) / max_step - 1e-9)
    return [raw + (final - raw) * (k + 1) / n for k in range(n)]


def _end(xs: list[float], y: tuple[float, float], z: float, top: float) -> list[str]:
    """One-way side passes at the cutter-centre Xs ``xs``, each from
    ``y[0]`` to ``y[1]`` at depth ``z``: plunged beside the part at feed,
    lifted and rapided back to the start beside it between passes. The
    tool starts at the clearance height above ``top``."""
    clear, safe = _r(top + CLEAR_MM), _r(top + SAFE_MM)
    lines = [f"G0 Z{clear:.3f}"]
    for x in xs:
        lines += [
            f"G0 X{_r(x):.3f} Y{_r(y[0]):.3f}",
            f"G0 Z{safe:.3f}",
            f"G1 Z{_r(z):.3f} F{{feed}}",
            f"G1 Y{_r(y[1]):.3f} F{{feed}}",
            f"G0 Z{clear:.3f}",
        ]
    return lines


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The bar's bands and holes from the export, each checked against the
    frame the recipe assumes: the ends square to X about the origin, the top
    face at the hole row's height above it on +Y and the bottom face below,
    the front face on -Z and the back face on +Z; every hole through from the
    front face along +Z on the row, its station from the left end and its
    height from the top face the export's own."""
    f = features["features"]
    left = f["left_end"]["plane"]
    right = f["right_end"]
    top = f["top_face"]["plane"]
    bottom = f["bottom_face"]
    front = f["front_face"]["plane"]
    back = f["back_face"]
    if left["axis"] != "x" or right["plane"]["axis"] != "x":
        raise ValueError("the ends: expected square to X")
    left_x = left["value"]
    if not math.isclose(
        right["plane"]["value"] - left_x, right["length_nominal"], abs_tol=1e-3
    ):
        raise ValueError("right_end: its plane is not the length from the left end")
    if top["axis"] != "y" or bottom["plane"]["axis"] != "y":
        raise ValueError("the top and bottom faces: expected square to Y")
    top_y = top["value"]
    if not math.isclose(
        top_y - bottom["plane"]["value"], bottom["height_nominal"], abs_tol=1e-3
    ):
        raise ValueError("bottom_face: its plane is not the height below the top face")
    if front["axis"] != "z" or back["plane"]["axis"] != "z":
        raise ValueError("the front and back faces: expected square to Z")
    front_z = front["value"]
    if not math.isclose(
        back["plane"]["value"] - front_z, back["depth_nominal"], abs_tol=1e-3
    ):
        raise ValueError("back_face: its plane is not the depth from the front face")
    holes = {}
    for name in ("hanger_hole", "axle_bore", "clamp_hole_1", "clamp_hole_2"):
        hole = f[name]
        if hole["axis"] != [0.0, 0.0, 1.0] or not hole.get("thru"):
            raise ValueError(f"{name}: expected through along +Z from the front face")
        x, y, z = hole["at"]
        if not math.isclose(z, front_z, abs_tol=1e-6):
            raise ValueError(f"{name}: expected to enter the front face")
        if hole["station_from"] != "left_end" or hole["height_from"] != "top_face":
            raise ValueError(
                f"{name}: expected its station from the left end and height from the top"
            )
        if not math.isclose(x - left_x, hole["station_nominal"], abs_tol=1e-3):
            raise ValueError(f"{name}: its X is not its station from the left end")
        if not math.isclose(top_y - y, hole["height_nominal"], abs_tol=1e-3):
            raise ValueError(f"{name}: its Y is not its height below the top face")
        holes[name] = {"x": x, "y": y, "dia": hole["dia"], "station": hole["station"]}
    if f["axle_bore"].get("process") != "drill":
        raise ValueError("axle_bore: expected a drilled bore")
    return {
        "frame": (left_x, top_y, front_z),
        "back_z": back["plane"]["value"],
        "length_band": right["length"],
        "height_band": bottom["height"],
        "height_nominal": bottom["height_nominal"],
        "depth_band": back["depth"],
        "holes": holes,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    left_x, top_y, front_z = g["frame"]

    # Targets: the middle of the length's and the height's printed bands.
    length = _mid(g["length_band"])
    height = _mid(g["height_band"])
    _agree(plan, "length_target_mm", length)
    _agree(plan, "height_target_mm", height)

    # The blank: the bar's thickness is the drawing's depth as supplied, its
    # width faced down from both edges, its sawn length milled at both ends.
    bar_t = p["blank_thickness_in"] * IN
    _agree(plan, "blank_thickness_mm", bar_t)
    depth_lo, depth_hi = g["depth_band"]
    _agree(plan, "depth_max_mm", depth_hi)
    if not depth_lo <= bar_t <= depth_hi:
        raise ValueError(
            f"the bar's {bar_t:.3f} thickness is outside the depth band {g['depth_band']}"
        )
    width_min, width_max = p["bar_width_min_mm"], p["bar_width_max_mm"]
    if not width_min <= p["blank_width_in"] * IN <= width_max:
        raise ValueError("the bar's width gate does not hold its nominal width")
    blank_min, blank_max = p["blank_length_in"] * IN, p["blank_length_max_in"] * IN
    _agree(plan, "blank_length_min_mm", blank_min)
    _agree(plan, "blank_length_max_mm", blank_max)
    left_skim = p["left_end_skim_mm"]
    if blank_min - left_skim - length < 0.5:
        raise ValueError(
            f"the shortest blank less the left-end skim, {blank_min - left_skim:.3f}, "
            f"leaves under 0.5 mm on the right end over the length {length:.3f}"
        )
    _agree(plan, "right_end_station_mm", left_skim + length)
    _agree(plan, "length_dro_min_mm", g["length_band"][0] + EDGE_FINDER_RADIUS_MM)
    _agree(plan, "length_dro_max_mm", g["length_band"][1] + EDGE_FINDER_RADIUS_MM)
    # The top face's cut, B to T: the narrowest bar still loses a skim off
    # edge A, and WB05 still takes a skim off edge B down to the height.
    top_w = p["top_width_mm"]
    level_max = p["face_step_max_mm"]
    if not height + level_max <= top_w <= width_min - level_max:
        raise ValueError(
            f"the top face's cut {top_w:.3f} leaves edge A or edge B under one level"
        )

    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    r = em / 2
    step_max = p["face_stepover_max_mm"]
    face_cuts = ("top face", "height", "left end", "right end")
    for name in face_cuts:
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), em, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' cutter Ø{_cut(plan, name, 'cutter_dia_mm')}, the end mill is Ø{em}"
            )
    # The faces run at their measured setting, the ends (deeper than it was
    # measured) at the chart's: each pair at one speed.
    face_rpm, face_feed = _setting(plan, shop, "top face")
    if _setting(plan, shop, "height") != (face_rpm, face_feed):
        raise ValueError("'height' runs at another setting than 'top face'")
    end_rpm, end_feed = _setting(plan, shop, "left end")
    if _setting(plan, shop, "right end") != (end_rpm, end_feed):
        raise ValueError("'right end' runs at another setting than 'left end'")
    for name in ("top face", "height"):
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), step_max, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' radial_woc_mm is not process.face_stepover_max_mm"
            )
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), level_max, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not process.face_step_max_mm")
    top_levels = _levels(width_max, top_w, level_max)
    height_levels = _levels(top_w, height, level_max)

    # Ends: the cutter's side, one level from the thickest bar's back face to
    # end_past_mm under F (into the air past the stacks' ends), in equal
    # radial steps no deeper than end_step_max_mm.
    end_step = p["end_step_max_mm"]
    end_z = -p["end_past_mm"]
    _agree(plan, "end_axial_doc_mm", depth_hi - end_z)
    for name in ("left end", "right end"):
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), end_step, abs_tol=1e-6):
            raise ValueError(f"'{name}' radial_woc_mm is not process.end_step_max_mm")
        if not math.isclose(
            _cut(plan, name, "axial_doc_mm"), depth_hi - end_z, abs_tol=1e-6
        ):
            raise ValueError(f"'{name}' axial_doc_mm is not process.end_axial_doc_mm")
    # The end mill's collet: its nose half_mill_projection_mm above the tip
    # stays clear of the stock's top (over the jaws, the stacks and the pin)
    # at the deepest end-mill cut: a face's levels or an end's one level.
    em_depth = max(width_max - top_w, top_w - height, depth_hi - end_z)
    if p["half_mill_projection_mm"] < em_depth + CLEAR_MM:
        raise ValueError(
            f"the end mill's collet would reach the bar {em_depth:.3f} below its top"
        )
    right_raw = blank_max - left_skim
    left_faces = _end_stations(-left_skim, 0.0, end_step)
    right_faces = _end_stations(right_raw, length, end_step)

    # Holes: the spot under every drill; each drill against its hole's
    # printed band; the tips through F into the air.
    holes = g["holes"]

    def tool_dia(tool: str) -> float:
        return _shop_tool(plan, shop, tool)["diameter_mm"]

    d316, d15, d9 = (tool_dia(t) for t in ("drill-3-16", "drill-15", "drill-9"))
    for name, dia in (
        ("axle_bore", d316),
        ("hanger_hole", d15),
        ("clamp_hole_1", d9),
        ("clamp_hole_2", d9),
    ):
        low, high = holes[name]["dia"]
        if not low - SIZE_TOL_MM <= dia <= high:
            raise ValueError(
                f"the drill Ø{dia} is outside {name}'s band {holes[name]['dia']}"
            )
    spot = p["spot_dia_mm"]
    if spot >= min(d316, d15, d9):
        raise ValueError("the spot is not under every drill: it would chamfer a hole")
    spot_depth = _spot_depth(spot)
    # The thinnest bar's top stands depth_hi − depth_lo under the programs'
    # top: its spot is that much shallower and must still pass the pilot.
    thin_spot = spot - 2 * (depth_hi - depth_lo) * math.tan(
        math.radians(CENTRE_DRILL["point_deg"] / 2)
    )
    if thin_spot <= CENTRE_DRILL["pilot_mm"]:
        raise ValueError("on the thinnest bar the spot does not reach past the pilot")
    for key, dia in (("drill_3_16", d316), ("drill_15", d15), ("drill_9", d9)):
        _agree(plan, f"{key}_tip_mm", -(p["drill_past_mm"] + _point(dia)))
    for cut, dia in (
        ("left spot", spot),
        ("right spot", spot),
        ("axle drill", d316),
        ("hanger drill", d15),
        ("clamp drill", d9),
    ):
        if not math.isclose(_cut(plan, cut, "cutter_dia_mm"), dia, abs_tol=1e-4):
            raise ValueError(f"'{cut}' cutter_dia_mm is not its tool's Ø{dia}")
    spot_rpm, spot_feed = _setting(plan, shop, "left spot")
    if _setting(plan, shop, "right spot") != (spot_rpm, spot_feed):
        raise ValueError("'right spot' runs at another speed than 'left spot'")
    speeds = {
        cut: _setting(plan, shop, cut)
        for cut in ("axle drill", "hanger drill", "clamp drill")
    }

    # Vise: the jaws, the stacks and each hold's reach.
    jaw_h, jaw_w = p["vise_jaw_height_mm"], p["vise_jaw_width_mm"]
    t = p["parallel_thickness_mm"]
    grips = {
        "top_grip_mm": jaw_h - p["top_riser_height_mm"],
        "lying_grip_mm": jaw_h - p["riser_height_mm"],
        "height_grip_mm": jaw_h - p["height_riser_height_mm"],
    }
    for key, value in grips.items():
        _agree(plan, key, value)
    fraction = shop["limits"]["vise_grip_fraction_min"]
    grip_min = shop["limits"]["vise_grip_min_mm"]
    # (grip, the part's height in the jaws, the lowest face level above them)
    holds = {
        "WB02": (grips["top_grip_mm"], width_max, top_w),
        "WB03/WB04": (grips["lying_grip_mm"], depth_hi, None),
        "WB05": (grips["height_grip_mm"], top_w, height),
    }
    for name, (grip, part_h, lowest) in holds.items():
        if grip < grip_min or grip < fraction * part_h - 1e-9:
            raise ValueError(
                f"{name}: the jaws grip {grip:.3f} of {part_h:.3f}, under the shop's minimum"
            )
        if lowest is not None and lowest - grip < JAW_CLEAR_MIN_MM:
            raise ValueError(
                f"{name}: the lowest face level {lowest:.3f} is not clear above the jaw tops {grip:.3f}"
            )
    if grips["lying_grip_mm"] >= depth_lo:
        raise ValueError(
            "WB03/WB04: the thinnest bar's back face does not stand above the jaws"
        )

    # The centred holds (WB02, WB05): each end of the longest blank out past
    # the jaws by half the difference.
    _agree(plan, "vise_overhang_mm", (blank_max - jaw_w) / 2)
    _agree(plan, "vise_clamp_end_mm", (blank_max + jaw_w) / 2)
    # The re-clamp (WB03, WB04), in the bar's work X (X0 the milled left end).
    out = p["end_overhang_mm"]
    _agree(plan, "left_clamp_end_mm", out + jaw_w)
    _agree(plan, "right_clamp_end_mm", blank_max - out)
    _agree(plan, "right_clamp_start_mm", blank_max - out - jaw_w)
    jaws_a = (out - left_skim, out - left_skim + jaw_w)
    # WB04 sets the sawn right end `out` past the jaws, so the jaws move
    # with the blank's length: the shortest and the longest bound them.
    jaws_b_lo = (blank_min - left_skim - out - jaw_w, blank_min - left_skim - out)
    jaws_b_hi = (blank_max - left_skim - out - jaw_w, blank_max - left_skim - out)
    for name, jaws in (
        ("hanger_hole", [jaws_a]),
        ("axle_bore", [jaws_a]),
        ("clamp_hole_1", [jaws_b_lo, jaws_b_hi]),
        ("clamp_hole_2", [jaws_b_lo, jaws_b_hi]),
    ):
        x = holes[name]["x"] - left_x
        for lo, hi in jaws:
            if x < lo - HOLE_OUT_MAX_MM or x > hi + HOLE_OUT_MAX_MM:
                raise ValueError(
                    f"{name} at X {x:.3f} stands over {HOLE_OUT_MAX_MM} out past its hold's jaws {lo:.3f}-{hi:.3f}"
                )
    # Each end is milled out past its hold's jaws (the cutter's near side at
    # the finished end, the jaw side inside it).
    if jaws_a[0] < 0.0:
        raise ValueError("WB03: the jaws reach past the finished left end")
    if jaws_b_hi[1] > length:
        raise ValueError("WB04: the jaws reach past the finished right end")
    # The pickup: the milled left end out past WB04's jaws (the shortest blank).
    reach = jaws_b_lo[0]
    _agree(plan, "pickup_reach_min_mm", reach)
    if reach < PICKUP_ROOM_MIN_MM:
        raise ValueError(
            f"WB04: the milled left end stands only {reach:.3f} out past the jaws"
        )
    _agree(plan, "z_touch_left_x_mm", _mid(list(jaws_a)))
    _agree(plan, "z_touch_right_x_mm", _mid(list(jaws_b_lo)))
    if not jaws_b_hi[0] <= p["z_touch_right_x_mm"] <= jaws_b_lo[1]:
        raise ValueError("WB04's Z touch-off is not over the jaws for every blank")

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)); X0 the finished left end
    # in every one.
    frames = {
        # On edge, B on the stacks, F against the fixed jaw: T at top_w.
        "top": _frame([left_x, top_y - top_w, front_z], [0, 0, -1], [0, 1, 0]),
        # Lying, F on the stacks, T against the fixed jaw.
        "lying": _frame([left_x, top_y, front_z], [0, 1, 0], [0, 0, 1]),
        # On edge, T on the stacks, the back face against the fixed jaw.
        "height": _frame([left_x, top_y, g["back_z"]], [0, 0, 1], [0, -1, 0]),
    }
    for key, frame in frames.items():
        corner = _to(frame, [left_x, top_y, front_z])
        if not math.isclose(corner[0], 0.0, abs_tol=1e-6):
            raise ValueError(f"{key}: the left end is not at X0")
    xy = {}
    for name, hole in holes.items():
        x, y, _z = _to(frames["lying"], [hole["x"], hole["y"], front_z])
        xy[name] = [_r(x), _r(y)]
    # Both stacks against the moving jaw, under edge B: every hole and the
    # largest tool through it exit clear of them.
    largest = max(d316, d15, d9, CENTRE_DRILL["body_mm"])
    for name, (_x, y) in xy.items():
        if not (-top_w + 2 * t < y - largest / 2 and y + largest / 2 < 0.0):
            raise ValueError(
                f"{name} at Y {y} reaches the stacks at the moving jaw ({2 * t} wide)"
            )

    run_x = (-left_skim, blank_max - left_skim)
    stocks = {
        "top": (run_x, (-bar_t, 0.0), (0.0, width_max)),
        "left": (run_x, (-top_w, 0.0), (0.0, depth_hi)),
        "right": ((0.0, run_x[1]), (-top_w, 0.0), (0.0, depth_hi)),
        "height": ((0.0, length), (-bar_t, 0.0), (0.0, top_w)),
    }

    em_tool = {
        "tool": "em-half",
        "dia": em,
        "shape": "endmill",
        "flutes": 3,
        "rpm": face_rpm,
        "feed": face_feed,
        "plunge": face_feed,
    }
    end_tool = {**em_tool, "rpm": end_rpm, "feed": end_feed, "plunge": end_feed}

    def point_tool(
        tool: str, dia: float, rpm: float, feed: float, angle: float
    ) -> dict[str, Any]:
        return {
            "tool": tool,
            "dia": dia,
            "shape": "drill",
            "tip_angle": angle,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
        }

    spot_tool = point_tool(
        "spot", CENTRE_DRILL["body_mm"], spot_rpm, spot_feed, CENTRE_DRILL["point_deg"]
    )
    drill_rows = {
        "axle_drill": (
            "drill-3-16",
            d316,
            "axle drill",
            ["axle_bore"],
            "drill the axle bore 3/16 through",
        ),
        "hanger_drill": (
            "drill-15",
            d15,
            "hanger drill",
            ["hanger_hole"],
            "drill the hanger hole #15 through",
        ),
        "clamp_drill": (
            "drill-9",
            d9,
            "clamp drill",
            ["clamp_hole_1", "clamp_hole_2"],
            "drill both clamp holes #9 through",
        ),
    }
    tips = {
        key: -(p["drill_past_mm"] + _point(row[1])) for key, row in drill_rows.items()
    }

    clear = depth_hi + CLEAR_MM
    face_x = (run_x[0] - r - APPROACH_MM, run_x[1] + r + APPROACH_MM)
    height_x = (-r - APPROACH_MM, length + r + APPROACH_MM)
    bar_ys = _stations((-bar_t, 0.0), r, step_max)
    beside = (-top_w - r - APPROACH_MM, r + APPROACH_MM)
    left_xs = [x - r for x in left_faces]
    right_xs = [x + r for x in right_faces]
    left_holes, right_holes = (
        ["hanger_hole", "axle_bore"],
        ["clamp_hole_1", "clamp_hole_2"],
    )

    def drill_job(key: str, frame: str) -> dict[str, Any]:
        tool, dia, cut, names_, label = drill_rows[key]
        rpm, feed = speeds[cut]
        return {
            **point_tool(tool, dia, rpm, feed, DRILL_POINT_DEG),
            "frame": frame,
            "label": cut,
            "stock": stocks[frame],
            "ops": [
                [
                    key,
                    label,
                    [
                        line
                        for n in names_
                        for line in _drilled(xy[n], depth_hi, tips[key], clear)
                    ],
                ]
            ],
        }

    jobs = [
        {
            **em_tool,
            "frame": "top",
            "label": "top face",
            "stock": stocks["top"],
            "ops": [
                [
                    "top_face",
                    "face edge A down to the top face",
                    _face(top_levels, width_max, face_x, bar_ys),
                ]
            ],
        },
        {
            **end_tool,
            "frame": "left",
            "label": "left end",
            "stock": stocks["left"],
            "ops": [
                [
                    "left_end",
                    "mill the left end to X0",
                    _end(left_xs, beside[::-1], end_z, depth_hi),
                ]
            ],
        },
        {
            **spot_tool,
            "frame": "left",
            "label": "left spot",
            "stock": stocks["left"],
            "ops": [
                [
                    "left_spot",
                    "spot the hanger hole and the axle bore",
                    [
                        line
                        for n in left_holes
                        for line in _spot(xy[n], depth_hi, depth_hi - spot_depth, clear)
                    ],
                ]
            ],
        },
        drill_job("axle_drill", "left"),
        drill_job("hanger_drill", "left"),
        {
            **end_tool,
            "frame": "right",
            "label": "right end",
            "stock": stocks["right"],
            "ops": [
                [
                    "right_end",
                    "mill the right end to the length",
                    _end(right_xs, beside, end_z, depth_hi),
                ]
            ],
        },
        {
            **spot_tool,
            "frame": "right",
            "label": "right spot",
            "stock": stocks["right"],
            "ops": [
                [
                    "right_spot",
                    "spot both clamp holes",
                    [
                        line
                        for n in right_holes
                        for line in _spot(xy[n], depth_hi, depth_hi - spot_depth, clear)
                    ],
                ]
            ],
        },
        drill_job("clamp_drill", "right"),
        {
            **em_tool,
            "frame": "height",
            "label": "height",
            "stock": stocks["height"],
            "ops": [
                [
                    "bottom_face",
                    "face edge B down to the height",
                    _face(height_levels, top_w, height_x, bar_ys),
                ]
            ],
        },
    ]

    # Keep-outs: the jaws beside the gripped span, from the stacks' top to
    # the jaw tops; the stacks and the .125 pin under and beside edge B in
    # WB03/WB04 (WB04's jaws the union over every blank length).
    def jaws(
        x: tuple[float, float], across: float, z_top: float
    ) -> list[dict[str, Any]]:
        return [
            _box("moving jaw", x, (-across - JAW_DEPTH_MM, -across), z_top),
            _box("fixed jaw", x, (0.0, JAW_DEPTH_MM), z_top),
        ]

    def lying_keep(x: tuple[float, float]) -> list[dict[str, Any]]:
        mid = _mid(list(x))
        stacks = (mid - PARALLEL_LENGTH_MM / 2, mid + PARALLEL_LENGTH_MM / 2)
        return jaws(x, top_w, grips["lying_grip_mm"]) + [
            _box("stacks at the moving jaw", stacks, (-top_w, -top_w + 2 * t), 0.0),
            _box(".125 pin at edge B", x, (-top_w - 0.125 * IN, -top_w), 0.125 * IN),
        ]

    centred = ((blank_max - jaw_w) / 2 - left_skim, (blank_max + jaw_w) / 2 - left_skim)
    keep = {
        "top": jaws(centred, bar_t, grips["top_grip_mm"]),
        "left": lying_keep(jaws_a),
        "right": lying_keep((jaws_b_lo[0], jaws_b_hi[1])),
        "height": jaws(centred, bar_t, grips["height_grip_mm"]),
    }

    tn = numbers
    expect: list[list[Any]] = []

    def face_checks(levels: list[float], top: float, frame: str) -> list[list[Any]]:
        return [
            ["depth", {"z_min": _r(levels[-1])}],
            ["rapids_clear", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            *[
                [
                    "face_passes",
                    {
                        "z": _r(z),
                        "y": [-bar_t, 0.0],
                        "max_engagement": step_max,
                        "radius": r,
                        "span": length,
                        "overhang": FACE_OVERHANG_MM,
                    },
                ]
                for z in levels
            ],
            ["keep_out", {"radius": r, "boxes": keep[frame]}],
        ]

    for name, levels, top, frame in (
        ("WB02_top", top_levels, width_max, "top"),
        ("WB05_height", height_levels, top_w, "height"),
    ):
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": top, "tools": [tn["em-half"]], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[face_rpm]]}],
            [name, "pauses", {"z_top": top, "count": 0}],
            *[
                [name, check, kwargs]
                for check, kwargs in face_checks(levels, top, frame)
            ],
        ]

    def hole_checks(
        names_: list[str], bottom: float, radius: float, frame: str
    ) -> list[list[Any]]:
        centres = [xy[n] for n in names_]
        return [
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": depth_hi, "open_holes": centres}],
            ["vertical_below_top", {"z_top": depth_hi}],
            ["air_feed", {"z_top": depth_hi}],
            ["keep_out", {"radius": radius, "boxes": keep[frame]}],
        ]

    def end_checks(
        final: float, raw: float, direction: float, frame: str
    ) -> list[list[Any]]:
        # The left end's passes run -Y and the right end's +Y: the stock on
        # each pass's left, conventional with the spindle's M3.
        xs = sorted((final, raw))
        return [
            ["depth", {"z_min": _r(end_z)}],
            ["rapids_clear", {"z_top": depth_hi}],
            ["air_feed", {"z_top": depth_hi}],
            [
                "side_passes",
                {
                    "axis": "X",
                    "final": _r(final),
                    "raw": _r(raw),
                    "max_step": end_step,
                    "direction": direction,
                    "span": top_w,
                    "below_z": depth_hi,
                },
            ],
            [
                "engagement",
                {
                    "stock": stocks[frame],
                    "radius": r,
                    "max_radial": end_step,
                    "z": _r(end_z),
                    "window": [xs, [beside[0], beside[1]]],
                    "min_length": top_w,
                    "side": "conventional",
                },
            ],
            ["keep_out", {"radius": r, "boxes": keep[frame]}],
        ]

    sections = {
        "WB03_left": (
            [
                tn["em-half"],
                tn["spot"],
                tn["drill-3-16"],
                tn["drill-15"],
            ],
            [
                ([end_rpm], end_checks(-r, -left_skim - r, -1.0, "left")),
                (
                    [spot_rpm],
                    hole_checks(
                        left_holes,
                        depth_hi - spot_depth,
                        CENTRE_DRILL["body_mm"] / 2,
                        "left",
                    ),
                ),
                (
                    [speeds["axle drill"][0]],
                    hole_checks(["axle_bore"], tips["axle_drill"], d316 / 2, "left"),
                ),
                (
                    [speeds["hanger drill"][0]],
                    hole_checks(["hanger_hole"], tips["hanger_drill"], d15 / 2, "left"),
                ),
            ],
            min(end_z, tips["axle_drill"], tips["hanger_drill"]),
        ),
        "WB04_right": (
            [tn["em-half"], tn["spot"], tn["drill-9"]],
            [
                ([end_rpm], end_checks(length + r, right_raw + r, 1.0, "right")),
                (
                    [spot_rpm],
                    hole_checks(
                        right_holes,
                        depth_hi - spot_depth,
                        CENTRE_DRILL["body_mm"] / 2,
                        "right",
                    ),
                ),
                (
                    [speeds["clamp drill"][0]],
                    hole_checks(right_holes, tips["clamp_drill"], d9 / 2, "right"),
                ),
            ],
            min(end_z, tips["clamp_drill"]),
        ),
    }
    for name, (tools, program_sections, deepest) in sections.items():
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": depth_hi, "tools": tools, "loads_first": True},
            ],
            [name, "spindle", {"rpm": [speeds_ for speeds_, _c in program_sections]}],
            [name, "pauses", {"z_top": depth_hi, "count": 0}],
            [name, "depth", {"z_min": _r(deepest)}],
        ]
        for k, (_speeds, checks) in enumerate(program_sections):
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
    section; returns {"ops": {operation key: operation}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(
            doc, f"Wheel bar {key}", ctx["step"], frame["origin"], frame["axes"]
        )
        for key, frame in ctx["frames"].items()
    }
    by_job = {"top": "top", "left": "lying", "right": "lying", "height": "height"}
    ops: dict[str, Any] = {}
    for section in ctx["jobs"]:
        target = rt.job(
            doc, section["label"], [models[by_job[section["frame"]]]], section["stock"]
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
