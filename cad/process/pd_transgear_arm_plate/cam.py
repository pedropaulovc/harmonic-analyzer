"""FreeCAD CAM recipe for MHA-PD-19, the transgear arm plate.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The plate's sizes come
from the feature export (the rear face's thickness, the outline's end round,
tapers, side edges and top corners, the press hole K and its chamfer, the
screw holes and their countersinks); the blank, the spoil block, the levels,
the spots and the feeds from ``plan.toml`` ``[parameters]`` and
``milling_cuts``; cutter, drill, reamer and countersink diameters from the
shop (``shop/``). Every path is written here (``rt.custom``): straight
lines and arcs a recipe can state exactly. Typed here, because neither
record carries them: the #1 centre drill's catalogue geometry (it sets the
spot depth), the twist drills' 118° point, the countersink's 82°, K's
chamfer's 90° (cut by hand at the bench, checked here only for its pin
check), the safe and clearance heights, the vise jaws' depth (keep-out
shapes only).

Route (plan text in ``plan.toml``): the 1/4 x 1-1/2 in bar's long edges are
the plate's side edges, as supplied. The sawn blank is bonded face A down on
a 6061 spoil block held in the vise, its C edge flush with the block's edge
at the fixed jaw. AP01 faces the rear face to the thickness, spots, drills
#1 through K and both screw holes, opens K 27/64 and reams it .4385; AP02
countersinks the screw holes; AP03 clears the end's corners with a half
circle, then mills the end round, the tapers and the top edge with the
cutter's side, through into the spoil block. K's face-A chamfer is cut by
hand at the bench after the plate is freed (delegated ruling 2026-11-22,
owner review #2144): no NC.

Work frame (G54), set in Setup 2:
- AP01-AP03 (``bond``): X0 Y0 K's axis, the plate's length along -X (the
  end round at +X), +Y toward the fixed jaw (the C edge, model +X); Z0 face
  A (model Z0), the rear face up. Work (X, Y, Z) = (-y, x, z).

Toolpath rules (owner rulings 2026-11-16): plunges beside the stock at the
cutting feed, real G0 above the stock. The outline is conventional (G3,
anticlockwise round the plate with M3), each pass entered and left in air on
an edge's extension past a side edge (a convex corner: the extension lies
outside the plate). The reamer is fed in and fed out.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "pd_transgear_arm_plate"
COMMENT = "MHA-PD-19 transgear arm plate"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    (
        "AP01_holes",
        (("face",), ("spots",), ("screw_drill",), ("press_drill",), ("press_ream",)),
    ),
    ("AP02_sink", (("screw_sink",),)),
    ("AP03_outline", (("corner_clear", "outline"),)),
)
# Every program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the files and the gauges are not).
CAM_TOOLS = ("em", "spot", "drill-1", "drill-27-64", "reamer", "sink")
IN = 25.4
# #1 combined drill and countersink (shop centre-drills-carbide-60, trade
# size 1): 1/8 body, 3/64 pilot and pilot length, 60° countersink, its pilot
# ground with a 118° point (as ch_channel_lever's recipe).
CENTRE_DRILL = {
    "body_mm": 1 / 8 * IN,
    "pilot_mm": 3 / 64 * IN,
    "pilot_length_mm": 3 / 64 * IN,
    "point_deg": 60.0,
    "pilot_point_deg": 118.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# The countersink's included angle (shop riser-countersink: 82°) and K's
# chamfer's (the sheet's 45°, the hand countersink's 90°).
SINK_DEG = 82.0
CHAMFER_DEG = 90.0
# The 3/8 in end mill's shop setting in 1018 CF.
EM_SETTING = "endmill-carbide-3fl-3-8-1018-cf"
# Plunges and drill R planes start this far above the stock top.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top (nothing stands over
# the spoil block's top).
CLEAR_MM = 5.0
# A face pass reaches this far past each edge of the blank.
FACE_OVERHANG_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped face.
JAW_DEPTH_MM = IN
# The outline's elements: how far the cutter centre may stray from its
# offset, and the sampling of the posted arcs (check_outline).
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


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


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


def _agree_band(plan: dict[str, Any], key: str, band: tuple[float, float]) -> None:
    """A band the plan states as ``<key>_min_mm`` and ``<key>_max_mm``."""
    _agree(plan, f"{key}_min_mm", band[0])
    _agree(plan, f"{key}_max_mm", band[1])


def _spot_depth(dia: float) -> float:
    """Depth below the surface at which the #1 centre drill reaches ``dia``:
    on its pilot's 118° point under the pilot's diameter, on its 60°
    countersink between the pilot and the body."""
    pilot, body = CENTRE_DRILL["pilot_mm"], CENTRE_DRILL["body_mm"]
    if not 0 < dia <= body or math.isclose(dia, pilot, abs_tol=1e-6):
        raise ValueError(
            f"spot Ø{dia:.3f} is neither under the pilot nor on the countersink"
        )
    if dia < pilot:
        return dia / 2 / math.tan(math.radians(CENTRE_DRILL["pilot_point_deg"] / 2))
    half = math.radians(CENTRE_DRILL["point_deg"] / 2)
    return CENTRE_DRILL["pilot_length_mm"] + (dia - pilot) / 2 / math.tan(half)


def _point(dia: float) -> float:
    """A twist drill's point length."""
    return dia / 2 / math.tan(math.radians(DRILL_POINT_DEG / 2))


def _unit(v: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(*v)
    return (v[0] / length, v[1] / length)


def _bond(p: tuple[float, float]) -> tuple[float, float]:
    """A model XY point in the bond frame: (X, Y) = (-y, x)."""
    return (-p[1], p[0])


def _plunge(
    xy: tuple[float, float], top: float, z: float, clear: float, out: str = "G0"
) -> list[str]:
    """One straight plunge at ``xy`` from above ``top`` to ``z`` at the feed,
    then out to the R plane by ``out`` (``G0``, or ``G1`` fed out). Moves to
    and from the hole run at ``clear``."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    back = f"G1 Z{r_plane:.3f} F{{feed}}" if out == "G1" else f"G0 Z{r_plane:.3f}"
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        back,
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
    z: float, top: float, x: tuple[float, float], ys: list[float], clear: float
) -> list[str]:
    """One zigzag face at ``z``: one X pass per Y in ``ys`` between the
    cutter-centre ends ``x``, alternating direction, starting at the low X
    end, plunged there in air past the blank's end."""
    x0, x1 = _r(x[0]), _r(x[1])
    lines = [
        f"G0 Z{_r(clear):.3f}",
        f"G0 X{x0:.3f} Y{ys[0]:.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
    ]
    for k, y in enumerate(ys):
        if k:
            lines.append(f"G1 Y{y:.3f} F{{feed}}")
        lines.append(f"G1 X{x1 if k % 2 == 0 else x0:.3f} F{{feed}}")
    return lines + [f"G0 Z{_r(clear):.3f}"]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The plate as the route assumes it, in model mm: K on model Z at the
    origin, face A at Z0, the rear face at +Z; the end round about K, its
    tapers tangent to it, the side edges on X = ±half width up from the
    kinks to the top edge's corners."""
    f = features["features"]
    k, outline = f["press_hole"], f["outline"]
    if k["at"][:2] != [0.0, 0.0] or outline["from"] != "press_hole":
        raise ValueError("K is off the model origin or the outline is not from K")
    for name in ("locator_1", "locator_2"):
        if f[name].get("made_at") != "assembly":
            raise ValueError(
                f"{name} is no longer made at assembly: this route does not make it"
            )
    for name in ("press_hole", "screw_hole_1", "screw_hole_2"):
        if f[name]["axis"] != [0.0, 0.0, -1.0] or f[name]["thru"] is not True:
            raise ValueError(f"{name} is not a through hole along model Z")
    if (
        f["press_hole"]["chamfer_at"] != "face_a"
        or f["face_a"]["plane"]["value"] != 0.0
    ):
        raise ValueError("K's chamfer is not at face A, or face A is off Z0")
    for name in ("screw_hole_1", "screw_hole_2"):
        if f[name]["csk_at"] != "rear_face":
            raise ValueError(f"{name}'s countersink is not on the rear face")
    half = outline["edge_right_x_nominal"]
    if not math.isclose(outline["edge_left_x_nominal"], half):
        raise ValueError("the side edges are not symmetric about K")
    tl, tr = outline["tangent_left_at"], outline["tangent_right_at"]
    if not math.isclose(tl[0], -tr[0]) or not math.isclose(tl[1], tr[1]):
        raise ValueError("the tapers are not mirror images about K")
    return {
        "thickness": f["rear_face"]["thickness_nominal"],
        "thickness_band": f["rear_face"]["thickness"],
        "half": half,
        "side_band": outline["edge_right_x"],
        "radius": outline["end_r_nominal"],
        "radius_band": outline["end_r"],
        "kink_y": outline["kink_y_nominal"],
        "kink_right_y": outline["kink_right_y_nominal"],
        "tangent_left": (tl[0], tl[1]),
        "tangent_right": (tr[0], tr[1]),
        "top_left": (-half, outline["top_left_y_nominal"]),
        "top_right": (half, outline["top_right_y_nominal"]),
        "top_left_band": outline["top_left_y"],
        "top_right_band": outline["top_right_y"],
        "k_dia": k["nominal_dia"],
        "k_band": k["dia"],
        "chamfer_band": k["chamfer_leg"],
        "chamfer_leg": k["chamfer_leg_nominal"],
        "chamfer_angle": k["chamfer_angle_deg"],
        "screws": [tuple(f[n]["at"][:2]) for n in ("screw_hole_1", "screw_hole_2")],
        "screw_band": f["screw_hole_1"]["dia"],
        "position_dia": f["screw_hole_1"]["position_dia"],
        "sink_dia": f["screw_hole_1"]["csk_dia_nominal"],
        "sink_band": f["screw_hole_1"]["csk_dia"],
        "sink_angle": f["screw_hole_1"]["csk_angle_deg_nominal"],
    }


def _area(g: dict[str, Any]) -> float:
    """The plate's outline area (the round sampled every 0.1°)."""
    radius = g["radius"]
    pts = [
        g["top_left"],
        g["top_right"],
        (g["half"], g["kink_right_y"]),
        g["tangent_right"],
    ]
    a0 = math.atan2(g["tangent_right"][1], g["tangent_right"][0])
    a1 = math.atan2(g["tangent_left"][1], g["tangent_left"][0])
    if a1 > a0:
        a1 -= 2 * math.pi
    n = max(2, math.ceil(math.degrees(a0 - a1) * 10))
    pts += [
        (
            radius * math.cos(a0 + (a1 - a0) * i / n),
            radius * math.sin(a0 + (a1 - a0) * i / n),
        )
        for i in range(1, n)
    ]
    pts += [g["tangent_left"], (-g["half"], g["kink_y"])]
    return 0.5 * abs(
        sum(
            pts[i][0] * pts[(i + 1) % len(pts)][1]
            - pts[(i + 1) % len(pts)][0] * pts[i][1]
            for i in range(len(pts))
        )
    )


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    t, half, radius = g["thickness"], g["half"], g["radius"]

    dem = _shop_tool(plan, shop, "em")["diameter_mm"]
    d1 = _shop_tool(plan, shop, "drill-1")["diameter_mm"]
    d2764 = _shop_tool(plan, shop, "drill-27-64")["diameter_mm"]
    dream = _shop_tool(plan, shop, "reamer")["diameter_mm"]
    rc = dem / 2
    if not g["screw_band"][0] - 1e-6 <= d1 <= g["screw_band"][1]:
        raise ValueError(f"#1 Ø{d1} outside the screw holes' band {g['screw_band']}")
    # K prints the set reamer's size and no band: the reamer is that size.
    if not math.isclose(dream, g["k_dia"], abs_tol=1e-6):
        raise ValueError(f"the reamer Ø{dream} is not K's Ø{g['k_dia']}")
    if not d1 < d2764 < dream:
        raise ValueError("the 27/64 does not lie between the #1 and the reamer")
    if not math.isclose(g["sink_angle"], SINK_DEG):
        raise ValueError(f"the countersink is {g['sink_angle']}°, the tool {SINK_DEG}°")
    if not math.isclose(g["chamfer_angle"] * 2, CHAMFER_DEG):
        raise ValueError("K's chamfer is not the hand countersink's 45°")
    for name, dia in (
        ("face rough", dem),
        ("face finish", dem),
        ("corner clear", dem),
        ("outline", dem),
        ("screw drill", d1),
        ("press drill", d2764),
        ("press ream", dream),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not its tool's Ø{dia}")
    if not math.isclose(_cut(plan, "spot", "cutter_dia_mm"), p["spot_dia_mm"]):
        raise ValueError("'spot' cutter_dia_mm is not process.spot_dia_mm")
    if not p["spot_dia_mm"] < d1:
        raise ValueError("the spot is not under the #1")

    # The blank: the bar as supplied; the plate's length along model Y with
    # round_waste below the round; the C edge (model +X) the Y datum.
    if not math.isclose(p["blank_width_in"] * IN, 2 * half, abs_tol=1e-6):
        raise ValueError(
            "the bar's width is not the plate's: the side edges are the bar's"
        )
    for edge in ("min", "max"):
        other = p[f"blank_width_{edge}_mm"] - half
        if not g["side_band"][0] - 1e-6 <= other <= g["side_band"][1] + 1e-6:
            raise ValueError(
                f"a {edge} gated width puts the front edge outside its band"
            )
    _agree(plan, "thickness_target_mm", t)
    wb = p["round_waste_mm"]
    right_end = radius + wb
    length_plate = g["top_left"][1] + radius
    if p["blank_length_min_mm"] < length_plate + wb:
        raise ValueError("the shortest blank is short of the plate")
    left_end_max = right_end - p["blank_length_max_mm"]
    _agree(plan, "x_set_mm", right_end + 2.54)
    _agree(plan, "y_set_mm", half + 2.54)
    _agree(plan, "z_touch_x_mm", right_end - p["blank_length_in"] * IN / 2)
    _agree(plan, "z_touch_y_mm", -half + IN / 2)

    # Facing: two levels; the passes from beside the largest blank's left end
    # to past its right end.
    rough_doc = p["blank_thickness_max_mm"] - p["face_rough_z_mm"]
    finish_doc = p["face_rough_z_mm"] - t
    for name, doc in (("face rough", rough_doc), ("face finish", finish_doc)):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), doc, abs_tol=PLAN_TOL_MM):
            raise ValueError(f"'{name}' axial_doc_mm is not {doc:.4f}")
        span = [
            _resolve(plan, v, name) for v in _op_with_cut(plan, name)[1]["traverse_mm"]
        ]
        if not all(
            math.isclose(a, b, abs_tol=PLAN_TOL_MM)
            for a, b in zip(span, (left_end_max, right_end))
        ):
            raise ValueError(f"'{name}' traverse_mm is not the largest blank's span")
    step = p["face_stepover_mm"]
    if not step < rc:
        raise ValueError("the facing stepover is not under half the cutter")
    face_y = (-(p["blank_width_max_mm"] - half), half)
    ys = _stations(face_y, rc, step)
    face_x = (left_end_max - rc - 1.5, right_end + rc + 1.5)
    raw_top = p["blank_thickness_max_mm"]
    clear_raw = raw_top + CLEAR_MM
    clear = t + CLEAR_MM

    # Holes: K and both screw holes in the bond frame.
    k = (0.0, 0.0)
    screws = [tuple(_r(c) for c in _bond(s)) for s in g["screws"]]
    spot_z = t - _spot_depth(p["spot_dia_mm"])
    # The drills' full diameter and the reamer's bevel reach into the spoil
    # block through the tape stack at its thickest.
    for key in ("drill_past_mm", "ream_past_mm"):
        if not p[key] > p["tape_stack_max_mm"]:
            raise ValueError(
                f"process.{key} does not clear the tape stack at its thickest"
            )
    drill_1_tip = -(p["drill_past_mm"] + _point(d1))
    drill_2764_tip = -(p["drill_past_mm"] + _point(d2764))
    _agree(plan, "drill_1_tip_mm", drill_1_tip)
    _agree(plan, "drill_2764_tip_mm", drill_2764_tip)
    _agree(plan, "ream_tip_mm", -p["ream_past_mm"])
    for name in ("screw drill", "press drill"):
        if _op_with_cut(plan, name)[0]["peck"] != "none":
            raise ValueError(f"'{name}' is one plunge (L/D under 1): peck = \"none\"")
    # The countersinks: the point on each screw hole's axis, its cone at the
    # sheet's Ø at the faced rear face.
    if not math.isclose(p["sink_dia_mm"], g["sink_dia"], abs_tol=1e-6):
        raise ValueError("process.sink_dia_mm is not the countersink's nominal Ø")
    sink_tip = t - p["sink_dia_mm"] / 2 / math.tan(math.radians(SINK_DEG / 2))
    _agree(plan, "sink_tip_mm", sink_tip)
    if not d1 < p["sink_dia_mm"] < _cut(plan, "screw sink", "cutter_dia_mm"):
        raise ValueError("the countersink's rim is not between the #1 and the tool")
    if sink_tip <= 0:
        raise ValueError("the countersink's point reaches face A")
    # The .250 pin standing in a countersink: its end below the rear face for
    # a rim at each end of the sheet's band.
    pin = p["sink_pin_dia_mm"]
    if not d1 < pin < g["sink_band"][0]:
        raise ValueError("the countersink pin is not between the hole and the rim")
    tan_half = math.tan(math.radians(SINK_DEG / 2))
    depths = tuple((rim - pin) / 2 / tan_half for rim in g["sink_band"])
    _agree_band(plan, "sink_pin_depth", depths)
    _agree(plan, "sink_pin_depth_mid_mm", sum(depths) / 2)

    # The outline (model frame first): each taper's outward normal, the
    # kinks on the side edges, the leads past the side edges.
    def taper(tangent: tuple[float, float], kink: tuple[float, float]):
        along = _unit((kink[0] - tangent[0], kink[1] - tangent[1]))
        normal = _unit(tangent)  # radial at the tangent point
        if abs(along[0] * normal[0] + along[1] * normal[1]) > 1e-6:
            raise ValueError("a taper is not tangent to the end round")
        return along, normal

    kink_l = (-half, g["kink_y"])
    kink_r = (half, g["kink_right_y"])
    along_l, n_l = taper(g["tangent_left"], kink_l)
    along_r, n_r = taper(g["tangent_right"], kink_r)
    lead = p["outline_lead_mm"]

    def past(kink, along, normal, side: float) -> float:
        """How far along the taper's extension the cutter centre stands
        ``lead`` clear of the side edge at X = side·half."""
        x_centre = kink[0] + rc * normal[0]
        return (side * (half + rc + lead) - x_centre) / along[0]

    s_l, s_r = past(kink_l, along_l, n_l, -1.0), past(kink_r, along_r, n_r, 1.0)
    ext_l = (kink_l[0] + s_l * along_l[0], kink_l[1] + s_l * along_l[1])
    ext_r = (kink_r[0] + s_r * along_r[0], kink_r[1] + s_r * along_r[1])
    top_dir = _unit(
        (g["top_left"][0] - g["top_right"][0], g["top_left"][1] - g["top_right"][1])
    )
    n_top = (top_dir[1], -top_dir[0])  # right of the way: outward, anticlockwise
    top_s = (half + rc + lead) / -top_dir[0]
    top_start = (
        g["top_right"][0] - top_s * top_dir[0] - rc * 0.0,
        g["top_right"][1] - top_s * top_dir[1],
    )
    top_end = (
        g["top_left"][0] + top_s * top_dir[0],
        g["top_left"][1] + top_s * top_dir[1],
    )

    def off(q: tuple[float, float], n: tuple[float, float]) -> tuple[float, float]:
        return (q[0] + rc * n[0], q[1] + rc * n[1])

    levels_n = int(p["outline_levels"])
    bottom = p["outline_bottom_mm"]
    level = (t - bottom) / levels_n
    _agree(plan, "outline_level_mm", level)
    levels = [_r(t - level * i) for i in range(1, levels_n + 1)]
    # The last level is through the stack into the spoil block at its
    # thickest and still inside the block at its thinnest.
    if (
        not p["tape_stack_max_mm"]
        < -bottom
        < p["tape_stack_min_mm"] + p["spoil_height_mm"]
    ):
        raise ValueError(
            "the outline's last level is not through the tape stack, in the spoil block"
        )
    for name in ("corner clear", "outline"):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), p["outline_level_mm"]):
            raise ValueError(f"'{name}' axial_doc_mm is not process.outline_level_mm")
    # The corner clearing: a half circle about K whose swath meets the
    # finish pass's and reaches past the blank's corners at the round's end.
    rr = p["rough_arc_radius_mm"]
    corner = math.hypot(right_end, p["blank_width_max_mm"] - half)
    if rr - rc > radius + 2 * rc - 0.25:
        raise ValueError(
            "the corner clearing leaves a ring the finish pass cannot reach"
        )
    if rr + rc < corner + 0.5 or rr + rc < math.hypot(right_end, half) + 0.5:
        raise ValueError(
            "the corner clearing's swath falls short of the blank's corners"
        )
    if rr - rc < max(p["blank_width_max_mm"] - half, half) + 0.25:
        raise ValueError(
            "the corner clearing's ends are not in air beside the side edges"
        )

    def bond_line(a, b) -> str:
        x, y = _bond(b)
        return f"G1 X{_r(x):.3f} Y{_r(y):.3f} F{{feed}}"

    def bond_lines() -> tuple[list[str], list[str]]:
        corner_clear = [f"G0 Z{_r(clear):.3f}"]
        start, end = _bond((-rr, 0.0)), _bond((rr, 0.0))
        for z in levels:
            corner_clear += [
                f"G0 X{_r(start[0]):.3f} Y{_r(start[1]):.3f}",
                f"G0 Z{_r(t + SAFE_MM):.3f}",
                f"G1 Z{z:.3f} F{{feed}}",
                f"G3 X{_r(end[0]):.3f} Y{_r(end[1]):.3f} I{_r(-start[0]):.3f} J{_r(-start[1]):.3f} F{{feed}}",
                f"G0 Z{_r(clear):.3f}",
            ]
        lower = [
            off(ext_l, n_l),
            off(g["tangent_left"], n_l),
            off(g["tangent_right"], n_r),
            off(ext_r, n_r),
        ]
        top = [off(top_start, n_top), off(top_end, n_top)]
        outline = [f"G0 Z{_r(clear):.3f}"]
        for z in levels:
            a = _bond(lower[0])
            b = _bond(lower[1])
            c = _bond(lower[2])
            outline += [
                f"G0 X{_r(a[0]):.3f} Y{_r(a[1]):.3f}",
                f"G0 Z{_r(t + SAFE_MM):.3f}",
                f"G1 Z{z:.3f} F{{feed}}",
                f"G1 X{_r(b[0]):.3f} Y{_r(b[1]):.3f} F{{feed}}",
                f"G3 X{_r(c[0]):.3f} Y{_r(c[1]):.3f} I{_r(-b[0]):.3f} J{_r(-b[1]):.3f} F{{feed}}",
                bond_line(lower[2], lower[3]),
                f"G0 Z{_r(clear):.3f}",
            ]
            s, e = _bond(top[0]), _bond(top[1])
            outline += [
                f"G0 X{_r(s[0]):.3f} Y{_r(s[1]):.3f}",
                f"G0 Z{_r(t + SAFE_MM):.3f}",
                f"G1 Z{z:.3f} F{{feed}}",
                f"G1 X{_r(e[0]):.3f} Y{_r(e[1]):.3f} F{{feed}}",
                f"G0 Z{_r(clear):.3f}",
            ]
        return corner_clear, outline

    corner_lines, outline_lines = bond_lines()

    def element(name: str, a, b, centre=None) -> dict[str, Any]:
        e = {
            "name": name,
            "start": list(map(_r, _bond(a))),
            "end": list(map(_r, _bond(b))),
            "tol": OUTLINE_TOL_MM,
        }
        if centre is not None:
            e["centre"] = list(map(_r, _bond(centre)))
        return e

    elements = [
        element("left taper's extension", ext_l, kink_l),
        element("left taper", kink_l, g["tangent_left"]),
        element("end round", g["tangent_left"], g["tangent_right"], (0.0, 0.0)),
        element("right taper", g["tangent_right"], kink_r),
        element("right taper's extension", kink_r, ext_r),
        element("top edge's right extension", top_start, g["top_right"]),
        element("top edge", g["top_right"], g["top_left"]),
        element("top edge's left extension", g["top_left"], top_end),
    ]

    # K's chamfer, cut by hand at the bench: its rim from the sheet.
    rim = g["k_dia"] / 2 + g["chamfer_leg"]
    _agree(plan, "chamfer_rim_dia_mm", 2 * rim)
    _agree_band(
        plan, "chamfer_rim", tuple(g["k_dia"] + 2 * leg for leg in g["chamfer_band"])
    )
    # The check: a pin between K's top limit and the smallest rim stands in
    # the chamfer; its end sits half the rim-less-pin below face A. The band
    # holds for any K in its band: the shallowest end from K's top limit and
    # the shortest leg, the deepest from K's low limit and the longest.
    pin = p["chamfer_pin_dia_mm"]
    if not g["k_band"][1] < pin < g["k_dia"] + 2 * g["chamfer_band"][0]:
        raise ValueError("the chamfer pin does not seat on the chamfer")
    _agree_band(
        plan,
        "chamfer_pin_depth",
        (
            (g["k_band"][1] + 2 * g["chamfer_band"][0] - pin) / 2,
            (g["k_band"][0] + 2 * g["chamfer_band"][1] - pin) / 2,
        ),
    )

    # Holding. The spoil block's top over the jaw tops.
    spoil_over = (
        p["parallel_height_mm"] + p["spoil_height_mm"] - p["vise_jaw_height_mm"]
    )
    _agree(plan, "spoil_over_jaws_mm", spoil_over)
    if spoil_over <= 0:
        raise ValueError("the spoil block's top is not over the jaw tops")
    if (
        p["vise_jaw_height_mm"] - p["parallel_height_mm"]
        < shop["limits"]["vise_grip_min_mm"]
    ):
        raise ValueError("the jaws grip the spoil block less than the shop's minimum")
    # The bond: the finished plate's area less its three holes.
    holes_area = math.pi / 4 * (g["k_dia"] ** 2 + 2 * d1**2)
    _agree(plan, "bond_area_mm2", _area(g) - holes_area)

    # Inspection bands from K, over the plug: the pin gauge one .001 step
    # under K (a plug to measure from; K itself is not gauged).
    plug_r = p["plug_radius_mm"]
    if not 0.0 < g["k_dia"] - 2 * plug_r <= 0.0254 + 1e-9:
        raise ValueError("the plug is not the pin gauge next under K")
    for key, band in (
        ("side_over_plug", g["side_band"]),
        ("round_over_plug", g["radius_band"]),
    ):
        _agree_band(plan, key, (band[0] + plug_r, band[1] + plug_r))
    zone = g["position_dia"] / 2
    for i, key in enumerate(("screw_1_from_k", "screw_2_from_k")):
        d = math.hypot(*g["screws"][i])
        _agree_band(plan, key, (d - zone, d + zone))

    # Speeds and feeds: the end mill's from its shop setting; the rest the
    # plan's, each cut against its parameters.
    setting = shop["settings"][EM_SETTING]
    _agree(plan, "em_rpm", setting["rpm"])
    _agree(
        plan,
        "em_feed_per_min_mm",
        setting["rpm"] * setting["flutes"] * setting["chip_load_mm_per_tooth"],
    )
    speeds = {}
    for name, rpm_key, feed_key in (
        ("face rough", "em_rpm", "em_feed_per_min_mm"),
        ("face finish", "em_rpm", "em_feed_per_min_mm"),
        ("corner clear", "em_rpm", "em_feed_per_min_mm"),
        ("outline", "em_rpm", "em_feed_per_min_mm"),
        ("spot", "spot_rpm", "spot_feed_per_min_mm"),
        ("screw drill", "drill_1_rpm", "drill_1_feed_per_min_mm"),
        ("press drill", "drill_2764_rpm", "drill_2764_feed_per_min_mm"),
        ("press ream", "ream_rpm", "ream_feed_per_min_mm"),
        ("screw sink", "sink_rpm", "sink_feed_per_min_mm"),
    ):
        op, cut = _op_with_cut(plan, name)
        rpm = _resolve(plan, cut.get("rpm", op.get("rpm", p[rpm_key])), f"'{name}' rpm")
        if not math.isclose(rpm, p[rpm_key]):
            raise ValueError(f"'{name}' rpm {rpm:g} is not process.{rpm_key}")
        if not math.isclose(_resolve(plan, op["rpm"], f"'{name}' op rpm"), p[rpm_key]):
            raise ValueError(f"'{name}' operation rpm is not process.{rpm_key}")
        feed = _cut(plan, name, "feed_mm_min")
        if not math.isclose(feed, p[feed_key], abs_tol=1e-6):
            raise ValueError(f"'{name}' feed_mm_min is not process.{feed_key}")
        speeds[name] = (p[rpm_key], p[feed_key])

    names = {t_["id"]: t_["name"] for t_ in plan["tools"]}
    numbers = {
        t_["id"]: n
        for n, t_ in enumerate((t_ for t_ in plan["tools"] if t_["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    tips = {"spot": CENTRE_DRILL["point_deg"], "sink": SINK_DEG}

    def section(
        tool: str, dia: float, cut: str, shape: str, frame: str, ops: list, stock
    ) -> dict[str, Any]:
        rpm, feed = speeds[cut]
        spec = {
            "tool": tool,
            "dia": dia,
            "shape": shape,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
            "frame": frame,
            "label": cut,
            "ops": ops,
            "stock": stock,
        }
        if shape == "drill":
            spec["tip_angle"] = tips.get(tool, DRILL_POINT_DEG)
        else:
            spec["flutes"] = 3 if tool == "em" else 2
        return spec

    frames = {
        "bond": {"origin": [0.0, 0.0, 0.0], "axes": [[0, -1, 0], [1, 0, 0], [0, 0, 1]]},
    }
    blank = ((left_end_max, right_end), face_y, (0.0, raw_top))
    dsink = _cut(plan, "screw sink", "cutter_dia_mm")
    spots = [k, *screws]
    jobs = [
        section(
            "em",
            dem,
            "face rough",
            "endmill",
            "bond",
            [
                [
                    "face",
                    "face the rear face",
                    _face(p["face_rough_z_mm"], raw_top, face_x, ys, clear_raw)
                    + _face(t, raw_top, face_x, ys, clear_raw),
                ]
            ],
            blank,
        ),
        section(
            "spot",
            CENTRE_DRILL["body_mm"],
            "spot",
            "drill",
            "bond",
            [
                [
                    "spots",
                    "spot K and the screw holes",
                    [line for xy in spots for line in _plunge(xy, t, spot_z, clear)],
                ]
            ],
            blank,
        ),
        section(
            "drill-1",
            d1,
            "screw drill",
            "drill",
            "bond",
            [
                [
                    "screw_drill",
                    "drill #1 through K and the screw holes",
                    [
                        line
                        for xy in spots
                        for line in _plunge(xy, t, drill_1_tip, clear)
                    ],
                ]
            ],
            blank,
        ),
        section(
            "drill-27-64",
            d2764,
            "press drill",
            "drill",
            "bond",
            [["press_drill", "open K 27/64", _plunge(k, t, drill_2764_tip, clear)]],
            blank,
        ),
        section(
            "reamer",
            dream,
            "press ream",
            "drill",
            "bond",
            [
                [
                    "press_ream",
                    "ream K .4385",
                    _plunge(k, t, -p["ream_past_mm"], clear, out="G1"),
                ]
            ],
            blank,
        ),
        section(
            "sink",
            dsink,
            "screw sink",
            "drill",
            "bond",
            [
                [
                    "screw_sink",
                    "countersink the screw holes",
                    [line for xy in screws for line in _plunge(xy, t, sink_tip, clear)],
                ]
            ],
            blank,
        ),
        section(
            "em",
            dem,
            "outline",
            "endmill",
            "bond",
            [
                ["corner_clear", "clear the end's corners", corner_lines],
                [
                    "outline",
                    "the end round, the tapers and the top edge",
                    outline_lines,
                ],
            ],
            blank,
        ),
    ]

    # Keep-outs. Setup 2: the jaws, their tops spoil_over below the spoil
    # block's top (under the tape stack: at its thinnest the jaws stand
    # highest), the fixed jaw's face at the C edge, the moving jaw's at the
    # block's other edge, along the block centred on the jaws.
    spoil_top = -p["tape_stack_min_mm"]
    spoil_x = (
        right_end + p["spoil_end_margin_mm"] - p["spoil_length_mm"],
        right_end + p["spoil_end_margin_mm"],
    )
    mid = sum(spoil_x) / 2
    jaw_x = (mid - p["vise_jaw_width_mm"] / 2, mid + p["vise_jaw_width_mm"] / 2)
    jaw_z = spoil_top - spoil_over
    bond_boxes = [
        _box("fixed jaw", jaw_x, (half, half + JAW_DEPTH_MM), jaw_z),
        _box(
            "moving jaw",
            jaw_x,
            (half - p["spoil_width_mm"] - JAW_DEPTH_MM, half - p["spoil_width_mm"]),
            jaw_z,
        ),
    ]

    tn = numbers

    def hole_checks(
        program: str, centres, z_bottom: float, radius: float, open_holes=()
    ):
        return [
            [
                program,
                "holes",
                {"centres": [list(c) for c in centres], "z_bottom": _r(z_bottom)},
            ],
            [
                program,
                "rapids_clear",
                {"z_top": t, "open_holes": [list(c) for c in open_holes]},
            ],
            [program, "vertical_below_top", {"z_top": t}],
            [program, "air_feed", {"z_top": t}],
            [program, "keep_out", {"radius": radius, "boxes": bond_boxes}],
        ]

    clear_box = {"stock": [list(a) for a in blank]}
    expect: list[list[Any]] = [
        [
            "AP01_holes",
            "tool_changes",
            {
                "z_top": raw_top,
                "tools": [
                    tn["em"],
                    tn["spot"],
                    tn["drill-1"],
                    tn["drill-27-64"],
                    tn["reamer"],
                ],
                "loads_first": True,
            },
        ],
        [
            "AP01_holes",
            "spindle",
            {
                "rpm": [
                    [speeds["face rough"][0]],
                    [speeds["spot"][0]],
                    [speeds["screw drill"][0]],
                    [speeds["press drill"][0]],
                    [speeds["press ream"][0]],
                ]
            },
        ],
        ["AP01_holes", "pauses", {"z_top": raw_top, "count": 0}],
        ["AP01_holes", "depth", {"z_min": _r(drill_2764_tip)}],
        ["AP01_holes@0", "rapids_clear", {"z_top": raw_top}],
        ["AP01_holes@0", "air_feed", {"z_top": raw_top}],
        ["AP01_holes@0", "keep_out", {"radius": rc, "boxes": bond_boxes}],
        [
            "AP01_holes@0",
            "face_passes",
            {
                "z": _r(p["face_rough_z_mm"]),
                "y": list(face_y),
                "max_engagement": step,
                "radius": rc,
                "span": p["blank_length_min_mm"],
                "overhang": FACE_OVERHANG_MM,
            },
        ],
        [
            "AP01_holes@0",
            "face_passes",
            {
                "z": _r(t),
                "y": list(face_y),
                "max_engagement": step,
                "radius": rc,
                "span": p["blank_length_min_mm"],
                "overhang": FACE_OVERHANG_MM,
            },
        ],
        *hole_checks("AP01_holes@1", spots, spot_z, CENTRE_DRILL["body_mm"] / 2),
        *hole_checks("AP01_holes@2", spots, drill_1_tip, d1 / 2, spots),
        *hole_checks("AP01_holes@3", [k], drill_2764_tip, d2764 / 2, [k]),
        *hole_checks("AP01_holes@4", [k], -p["ream_past_mm"], dream / 2, [k]),
        ["AP01_holes@4", "feed_out", {"z_top": t}],
        [
            "AP02_sink",
            "tool_changes",
            {"z_top": t, "tools": [tn["sink"]], "loads_first": True},
        ],
        ["AP02_sink", "spindle", {"rpm": [[speeds["screw sink"][0]]]}],
        ["AP02_sink", "pauses", {"z_top": t, "count": 0}],
        ["AP02_sink", "depth", {"z_min": _r(sink_tip)}],
        *hole_checks("AP02_sink@0", screws, sink_tip, dsink / 2, screws),
        [
            "AP03_outline",
            "tool_changes",
            {"z_top": t, "tools": [tn["em"]], "loads_first": True},
        ],
        ["AP03_outline", "spindle", {"rpm": [[speeds["outline"][0]]]}],
        ["AP03_outline", "pauses", {"z_top": t, "count": 0}],
        ["AP03_outline", "depth", {"z_min": _r(bottom)}],
        ["AP03_outline@0", "rapids_clear", {"z_top": t}],
        ["AP03_outline@0", "air_feed", {"z_top": t}],
        ["AP03_outline@0", "keep_out", {"radius": rc, "boxes": bond_boxes}],
        [
            "AP03_outline@0",
            "outline",
            {
                "elements": elements,
                "passes": [{"offset": rc, "levels": levels}],
                "z_top": t,
                "clearing": [{"x": [-0.5, _r(rr + 0.5)], "levels": levels}],
            },
        ],
        [
            "AP03_outline@0",
            "cleared",
            {
                "points": [
                    [_r(right_end), _r(half)],
                    [_r(right_end), _r(-(p["blank_width_max_mm"] - half))],
                    [_r(left_end_max), _r(half)],
                    [_r(left_end_max), _r(-(p["blank_width_max_mm"] - half))],
                ],
                "radius": rc,
                "z": _r(bottom),
            },
        ],
    ]
    del clear_box

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
            doc, f"Plate {key}", ctx["step"], frame["origin"], frame["axes"]
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
    rt.generate(doc)
    return {"ops": ops}
