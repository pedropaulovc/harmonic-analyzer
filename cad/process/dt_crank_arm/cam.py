"""FreeCAD CAM recipe for MHA-DT-06, the crank arm.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The arm's sizes come
from the feature export (the hub seat, the two R.50 ends and their centres,
the anchor and pivot taps, the punched mark's station and the countersink's
limit); the blank, the overhangs, the levels, the spots, the pecks and the
feeds from ``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter, drill
and chamfer-mill diameters from the shop (``shop/``). Every path is written
here (``rt.custom``): straight lines, arcs and a helix a recipe can state
exactly. Typed here, because neither record carries them: the #1 centre
drill's catalogue geometry (it sets the spot depths), the twist drills' 118°
point, the chamfer mill's 90°, the machine's Z top for the tap files'
retract, the safe and clearance heights, the vise jaws' depth and the
parallels' length (keep-out shapes only).

Route (plan text in ``plan.toml``): the 1 x 5/16 bar is used as supplied
(width and thickness, drawing note 1). The sawn blank lies outboard face up
on two 1 in parallels in the vise, gripped on its two long edges, one end
overhanging the jaws' left ends, a same-bar spacer at the jaws' right ends.
CA01 (hub end overhanging): the hub seat by helical interpolation, the
boss end's R.50 round, the anchor tap's and the match mark's spots and the
#50 through; CA02 brings the tap guide over the anchor hole for tapping by
hand. The blank is then turned end for end, outboard face still up. CA03
(handle end overhanging): the handle end's R.50 round, the pivot spot, the
#43 through and its countersink; CA04 the tap guide over the pivot hole.

Work frames (G54), each set in its setup:
- CA01/CA02: X0 the blank's left end (the hub end's), +X along the arm;
  Y0 the fixed jaw's face (the top edge, against it), the arm at -Y; Z0
  the outboard face.
- CA03/CA04: X0 the hub end's tip (machined in CA01), the arm at -X; Y0 the
  fixed jaw's face (the bottom edge, against it), the arm at -Y; Z0 the
  outboard face.

Toolpath rules (owner rulings 2026-11-16): plunges beside the stock at the
cutting feed, real G0 above the stock. The rounds are conventional (G3,
anticlockwise round the part with M3), the seat's helix conventional inside
(G2). The holes are tapped by hand (FluidNC cannot rigid-tap; owner, Pedro,
2026-11-17), the T-handle wrench's centre hole on the spring point of the
Fisher tap guide in the 1/2 in R8 collet (owner, Pedro, 2026-11-21: "use
https://littlemachineshop.com/products/tap-guide-fisher?variant=45472915226805
on r8 0.5 collet"), spindle off; FluidNC refuses jogs while an M0 holds the
program (FluidNC wiki, "Single Block Mode"), so each tap stop is a file of
its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_crank_arm"
COMMENT = "MHA-DT-06 crank arm"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("CA01_hub_end", (("seat", "boss_round"), ("hub_spots",), ("anchor_drill",))),
    ("CA02_anchor_tap", ("anchor_tap_stop",)),
    (
        "CA03_handle_end",
        (("handle_round",), ("pivot_spot",), ("pivot_drill",), ("pivot_sink",)),
    ),
    ("CA04_pivot_tap", ("pivot_tap_stop",)),
)
# Every program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the taps, the punch and the files are not).
CAM_TOOLS = ("em", "spot", "drill-50", "drill-43", "sink", "tap-guide")
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
# The chamfer mill's included angle (shop chamfer-mill-carbide-1-4-90: 90°,
# its cone running to a point).
SINK_DEG = 90.0
# The 3/8 in end mill's shop setting in 1018 CF.
EM_SETTING = "endmill-carbide-3fl-3-8-1018-cf"
# The tap files' first motion: G53 G0 to machine Z0, the homed top; the owner
# (Pedro) confirmed it, answered in person 2026-11-21 (cnc rulings record).
MACHINE_Z_TOP_MM = 0.0
# The seat helix's free core (cut loose at break-through) at most this thick.
CORE_DIA_MAX_MM = 1.0
# Plunges and drill R planes start this far above the stock top.
SAFE_MM = 1.0
# Moves between cuts run this far above the jaw tops.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped edge; the
# parallels' length (4 in) and thickness (1/8 in, fixtures.parallels-lms-6745).
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 4 * IN
PARALLEL_THICKNESS_MM = IN / 8
# A cutter passes a jaw end or a part edge at no less than this.
JAW_CLEARANCE_MM = 1.5
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


def _spot(xy: tuple[float, float], z: float, clear: float) -> list[str]:
    clear, r_plane = _r(clear), _r(SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _pecked(
    xy: tuple[float, float], tip: float, peck: float, clear: float
) -> list[str]:
    """Drill from the stock top (Z0) to ``tip`` in pecks of ``peck``, each
    with a full retract to the R plane and a rapid back to just above it."""
    clear, r_plane = _r(clear), _r(SAFE_MM)
    depths = []
    depth = 0.0
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


def _helix(
    centre: tuple[float, float],
    radius: float,
    pitch: float,
    bottom: float,
    clear: float,
) -> list[str]:
    """The seat: down a G2 helix of ``radius`` about ``centre`` from just above
    the stock top to ``bottom`` (through, into air: the hub end overhangs),
    one level turn there, then to the centre and out. Each turn ends where it
    starts, so every G2 line is one whole turn."""
    cx, cy = centre
    sx = _r(cx + radius)
    top = SAFE_MM / 2
    turns = math.ceil((top - bottom) / pitch - 1e-9)
    step = (top - bottom) / turns
    lines = [
        f"G0 Z{_r(clear):.3f}",
        f"G0 X{sx:.3f} Y{_r(cy):.3f}",
        f"G0 Z{_r(SAFE_MM):.3f}",
        f"G1 Z{_r(top):.3f} F{{feed}}",
    ]
    for k in range(1, turns + 1):
        lines.append(
            f"G2 X{sx:.3f} Y{_r(cy):.3f} I{_r(-radius):.3f} J0.000 Z{_r(top - k * step):.3f}"
        )
    lines += [
        f"G2 X{sx:.3f} Y{_r(cy):.3f} I{_r(-radius):.3f} J0.000",
        f"G1 X{_r(cx):.3f} Y{_r(cy):.3f}",
        f"G0 Z{_r(clear):.3f}",
    ]
    return lines


def _round(
    centre: tuple[float, float], radius: float, levels: list[float], clear: float
) -> list[str]:
    """An end's R.50 round: the half circle on the -X side of ``centre``,
    anticlockwise (G3, conventional outside) from its +Y tangent point to
    its -Y one, at each of ``levels``. Each level plunges at the +Y tangent
    point, in air beside the part past the jaws' left ends."""
    cx, cy = centre
    start, end = (_r(cx), _r(cy + radius)), (_r(cx), _r(cy - radius))
    lines = [f"G0 Z{_r(clear):.3f}"]
    for z in levels:
        lines += [
            f"G0 X{start[0]:.3f} Y{start[1]:.3f}",
            f"G0 Z{_r(SAFE_MM):.3f}",
            f"G1 Z{_r(z):.3f} F{{feed}}",
            f"G3 X{end[0]:.3f} Y{end[1]:.3f} I0.000 J{_r(-radius):.3f}",
            f"G0 Z{_r(clear):.3f}",
        ]
    return lines


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The arm as the routes assume it: the hub seat's axis on model Z at the
    origin, the arm along +X, the top edge at +Y, the outboard face at +Z;
    both rounds concentric with the seat and the pivot."""
    f = features["features"]
    seat, boss, handle = f["hub_seat"], f["boss_end"], f["handle_end"]
    anchor, pivot, mark = f["anchor_tap"], f["pivot_tap"], f["match_mark"]
    if seat["at"][:2] != [0.0, 0.0] or boss["centre_at"][:2] != [0.0, 0.0]:
        raise ValueError("the hub seat or the boss round is off the model origin")
    if handle["centre_at"][:2] != pivot["at"][:2]:
        raise ValueError("the handle round is not concentric with the pivot")
    if f["seam"]["made_at"] != "assembly":
        raise ValueError(
            "the seam is no longer made at assembly: this route does not make it"
        )
    for name in ("anchor_tap", "pivot_tap", "hub_seat"):
        if f[name]["axis"] != "+Z" and f[name]["axis"] != [0.0, 0.0, 1.0]:
            raise ValueError(f"{name} does not run along model Z")
    half = f["top_edge"]["plane"]["value"]
    return {
        "half_width": half,
        "thickness": f["outboard_face"]["plane"]["value"],
        "seat_dia": seat["dia_nominal"],
        "seat_band": seat["dia"],
        "radius": boss["radius_nominal"],
        "handle_radius": handle["radius_nominal"],
        "c2c": pivot["at"][0],
        "anchor": (anchor["at"][0], anchor["at"][1]),
        "anchor_dia": anchor["dia"],
        "pivot_dia": pivot["dia"],
        "sink_max": pivot["countersink_dia_max"],
        "mark": (mark["at"][0], mark["at"][1]),
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    half, t, radius = g["half_width"], g["thickness"], g["radius"]
    if not math.isclose(g["handle_radius"], radius) or not math.isclose(radius, half):
        raise ValueError("the rounds are not full rounds of the bar's half width")

    dem = _shop_tool(plan, shop, "em")["diameter_mm"]
    d50 = _shop_tool(plan, shop, "drill-50")["diameter_mm"]
    d43 = _shop_tool(plan, shop, "drill-43")["diameter_mm"]
    dsink = _shop_tool(plan, shop, "sink")["diameter_mm"]
    for name, dia, band in (
        ("#50", d50, g["anchor_dia"]),
        ("#43", d43, g["pivot_dia"]),
    ):
        if not band[0] - 1e-6 <= dia <= band[1]:
            raise ValueError(f"{name} Ø{dia} outside its tap drill band {band}")
    for name, dia in (
        ("seat", dem),
        ("boss round", dem),
        ("handle round", dem),
        ("anchor drill", d50),
        ("pivot drill", d43),
        ("pivot sink", dsink),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not its tool's Ø{dia}")
    # The anchor and the mark take one spot (one depth, one section): under
    # the #50 for its chisel edge, and the punched mark's Ø.03 for the punch.
    for name, key in (
        ("anchor spot", "hub_spot_dia_mm"),
        ("mark spot", "hub_spot_dia_mm"),
        ("pivot spot", "pivot_spot_dia_mm"),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), p[key], abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not process.{key}")
    if not p["hub_spot_dia_mm"] < d50 or not p["pivot_spot_dia_mm"] < d43:
        raise ValueError("a spot is not under its drill")

    # The blank is the bar as supplied: Z0 its outboard face, the through
    # cuts to the thickest bar plus the run past; the drills' full diameter
    # past the underside.
    _agree(plan, "blank_thickness_max_mm", t)
    bottom = -(p["blank_thickness_max_mm"] + p["through_past_mm"])
    _agree(plan, "through_bottom_mm", bottom)
    anchor_tip = -(p["blank_thickness_max_mm"] + p["drill_past_mm"] + _point(d50))
    pivot_tip = -(p["blank_thickness_max_mm"] + p["drill_past_mm"] + _point(d43))
    _agree(plan, "anchor_drill_tip_mm", anchor_tip)
    _agree(plan, "pivot_drill_tip_mm", pivot_tip)
    levels = [
        _r(bottom * k / p["round_levels"]) for k in range(1, int(p["round_levels"]) + 1)
    ]
    _agree(plan, "round_level_mm", -bottom / p["round_levels"])
    if not math.isclose(
        _cut(plan, "boss round", "axial_doc_mm"), p["round_level_mm"], abs_tol=1e-6
    ):
        raise ValueError("'boss round' axial_doc_mm is not process.round_level_mm")

    # The seat: a helix of the cutter centre about the seat's axis to the
    # seat's nominal diameter; the rounds' cutter centre on R + its radius.
    seat_r = (g["seat_dia"] - dem) / 2
    _agree(plan, "seat_path_radius_mm", seat_r)
    if not g["seat_band"][0] <= seat_r * 2 + dem <= g["seat_band"][1]:
        raise ValueError("the seat helix's diameter is outside the seat's band")
    # The helix leaves a core of radius seat_r - cutter radius on the axis:
    # cut free at break-through, it drops out under the overhang. A core
    # thicker than CORE_DIA_MAX_MM could jam against the cutter as it falls.
    if seat_r <= 0 or 2 * (seat_r - dem / 2) > CORE_DIA_MAX_MM:
        raise ValueError("the seat helix leaves a core too thick to drop free")
    round_r = radius + dem / 2
    _agree(plan, "round_path_radius_mm", round_r)

    # The countersink: the chamfer mill's point on the pivot's axis, its
    # cone reaching the target rim diameter at the face.
    target = p["sink_dia_mm"]
    if not d43 < target <= g["sink_max"] - p["sink_margin_mm"] + 1e-6:
        raise ValueError(
            f"countersink Ø{target:.3f} not between the #43 and {g['sink_max']:.3f} less the margin"
        )
    if target >= dsink:
        raise ValueError("the countersink is wider than the chamfer mill")
    sink_tip = -target / 2 / math.tan(math.radians(SINK_DEG / 2))
    _agree(plan, "sink_tip_mm", sink_tip)

    # The jaws stand over the outboard face: grip from the parallels' tops.
    jaw_top = p["vise_jaw_height_mm"] - p["parallel_height_mm"] - t
    _agree(plan, "jaw_top_mm", jaw_top)
    clear = jaw_top + CLEAR_MM
    # The chuck's and the collets' noses ride over the jaws (the holes sit
    # within a holder's radius of the jaws' ends): at each tool's deepest
    # point its least projection keeps the nose above the jaw tops.
    for what, tip, projection in (
        ("#50 in the chuck", anchor_tip, p["drill_projection_min_mm"]),
        ("#43 in the chuck", pivot_tip, p["drill_projection_min_mm"]),
        ("end mill in its collet", bottom, p["em_projection_min_mm"]),
        ("chamfer mill in its collet", sink_tip, p["sink_projection_min_mm"]),
    ):
        if tip + projection < jaw_top + JAW_CLEARANCE_MM - 1e-6:
            raise ValueError(f"the {what}'s nose reaches the jaw tops")
    grip = p["vise_jaw_height_mm"] - p["parallel_height_mm"]
    if grip < t:
        raise ValueError("the parallels lift the bar's top over the jaws")

    # CA01 frame: model -> work: X = x + R + hub waste, Y = y - half, Z = z - t.
    e1 = p["hub_waste_mm"]
    hub = (_r(radius + e1), _r(-half))
    anchor = (_r(g["anchor"][0] + radius + e1), _r(g["anchor"][1] - half))
    mark = (_r(g["mark"][0] + radius + e1), _r(g["mark"][1] - half))
    # The jaws' left ends at least overhang_min from X0: the round's cutter,
    # the anchor's drill and every spot stand left of them by the clearance.
    ca01_reach = max(hub[0] + dem / 2, anchor[0] + d50 / 2, hub[0] + seat_r + dem / 2)
    _agree(plan, "ca01_reach_mm", ca01_reach)
    if ca01_reach + JAW_CLEARANCE_MM > p["overhang_min_mm"] + 1e-6:
        raise ValueError(
            "CA01's cuts reach the jaws or the parallels at the least overhang"
        )
    # The blank's corners at the hub end are cleared by the round's swath.
    corner = math.hypot(radius + e1, half)
    if corner > round_r + dem / 2 - 0.1:
        raise ValueError("the hub-end waste's corners lie outside the round's swath")
    # The handle-end waste after CA01 (the hub tip at X0 in CA03): the
    # longest blank's.
    e2_max = p["blank_length_max_mm"] - p["hub_waste_mm"] - (g["c2c"] + 2 * radius)
    _agree(plan, "handle_waste_max_mm", e2_max)
    if math.hypot(radius + e2_max, half) > round_r + dem / 2 - 0.1:
        raise ValueError("the handle-end waste's corners lie outside the round's swath")
    e2_min = p["blank_length_min_mm"] - p["hub_waste_mm"] - (g["c2c"] + 2 * radius)
    if e2_min < 0:
        raise ValueError("the shortest blank is short of the arm")

    # CA03 frame: turned end for end: X = -(x + R), Y = -(y + half), Z = z - t.
    pivot = (_r(-(g["c2c"] + radius)), _r(-half))
    ca03_reach = pivot[0] + dem / 2 + max(0.0, 0.0)
    _agree(plan, "ca03_reach_mm", -ca03_reach)
    if -(ca03_reach + JAW_CLEARANCE_MM) < p["handle_jaw_end_max_mm"] - 1e-6:
        raise ValueError(
            "CA03's round reaches the jaws at their farthest from the hub tip"
        )

    # Tap stack ceiling (the tap files' hold): spindle-to-table maximum less
    # the tool-change clearance, the vise bed, the parallels, the bar and the
    # collet's gauge, rounded down to .01 in.
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["parallel_height_mm"]
        - t
        - p["r8_collet_gauge_mm"]
    )
    _agree(plan, "tap_stack_max_mm", math.floor(stack / 0.254 + 1e-9) * 0.254)

    # The end mill's speed and feed are the shop setting's (2800 rpm, its
    # chip load times its flutes): the seat's helix and the rounds' levels
    # run at it.
    setting = shop["settings"][EM_SETTING]
    _agree(plan, "em_rpm", setting["rpm"])
    _agree(
        plan,
        "em_feed_per_min_mm",
        setting["rpm"] * setting["flutes"] * setting["chip_load_mm_per_tooth"],
    )
    speeds = {}
    for name, rpm_key, feed_key in (
        ("seat", "em_rpm", "em_feed_per_min_mm"),
        ("boss round", "em_rpm", "em_feed_per_min_mm"),
        ("handle round", "em_rpm", "em_feed_per_min_mm"),
        ("anchor spot", "spot_rpm", "spot_feed_per_min_mm"),
        ("mark spot", "spot_rpm", "spot_feed_per_min_mm"),
        ("pivot spot", "spot_rpm", "spot_feed_per_min_mm"),
        ("anchor drill", "drill_rpm", "drill_feed_per_min_mm"),
        ("pivot drill", "drill_rpm", "drill_feed_per_min_mm"),
        ("pivot sink", "sink_rpm", "sink_feed_per_min_mm"),
    ):
        op, cut = _op_with_cut(plan, name)
        rpm = _resolve(plan, cut.get("rpm", op.get("rpm", p[rpm_key])), f"'{name}' rpm")
        if not math.isclose(rpm, p[rpm_key]):
            raise ValueError(f"'{name}' rpm {rpm:g} is not process.{rpm_key}")
        if "feed_mm_min" in cut:
            feed = _cut(plan, name, "feed_mm_min")
            if not math.isclose(feed, p[feed_key], abs_tol=1e-6):
                raise ValueError(f"'{name}' feed_mm_min is not process.{feed_key}")
        speeds[name] = (p[rpm_key], p[feed_key])
    for name, step in (
        ("anchor drill", p["peck_50_mm"]),
        ("pivot drill", p["peck_43_mm"]),
    ):
        if _op_with_cut(plan, name)[0]["peck"] != {"step_mm": step, "retract": "full"}:
            raise ValueError(f"'{name}' peck is not its process peck with full retract")

    names = {t_["id"]: t_["name"] for t_ in plan["tools"]}
    numbers = {
        t_["id"]: n
        for n, t_ in enumerate((t_ for t_ in plan["tools"] if t_["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    def section(
        tool: str, dia: float, cut: str, shape: str, frame: str, ops: list
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
        }
        if shape == "drill":
            spec["tip_angle"] = (
                CENTRE_DRILL["point_deg"]
                if tool == "spot"
                else SINK_DEG
                if tool == "sink"
                else DRILL_POINT_DEG
            )
        else:
            spec["flutes"] = 3
        return spec

    frames = {
        "hub": {
            "origin": [-(radius + e1), half, t],
            "axes": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        },
        "handle": {
            "origin": [-radius, -half, t],
            "axes": [[-1, 0, 0], [0, -1, 0], [0, 0, 1]],
        },
    }
    length_max = p["blank_length_max_mm"]
    stock = {
        "hub": ((0.0, length_max), (-2 * half, 0.0), (-t, 0.0)),
        "handle": (
            (-(g["c2c"] + 2 * radius + e2_max), 0.0),
            (-2 * half, 0.0),
            (-t, 0.0),
        ),
    }
    spot_depths = {
        "hub": _spot_depth(p["hub_spot_dia_mm"]),
        "pivot": _spot_depth(p["pivot_spot_dia_mm"]),
    }
    jobs = [
        {
            **section(
                "em",
                dem,
                "seat",
                "endmill",
                "hub",
                [
                    [
                        "seat",
                        "hub seat helix",
                        _helix(hub, seat_r, p["seat_helix_pitch_mm"], bottom, clear),
                    ],
                ],
            ),
            "stock": stock["hub"],
        },
        {
            **section(
                "spot",
                CENTRE_DRILL["body_mm"],
                "anchor spot",
                "drill",
                "hub",
                [
                    [
                        "hub_spots",
                        "spot the anchor and the mark",
                        _spot(anchor, -spot_depths["hub"], clear)
                        + _spot(mark, -spot_depths["hub"], clear),
                    ],
                ],
            ),
            "stock": stock["hub"],
        },
        {
            **section(
                "drill-50",
                d50,
                "anchor drill",
                "drill",
                "hub",
                [
                    [
                        "anchor_drill",
                        "drill #50 through",
                        _pecked(anchor, anchor_tip, p["peck_50_mm"], clear),
                    ],
                ],
            ),
            "stock": stock["hub"],
        },
        {
            **section(
                "em",
                dem,
                "handle round",
                "endmill",
                "handle",
                [
                    [
                        "handle_round",
                        "handle end round",
                        _round(pivot, round_r, levels, clear),
                    ],
                ],
            ),
            "stock": stock["handle"],
        },
        {
            **section(
                "spot",
                CENTRE_DRILL["body_mm"],
                "pivot spot",
                "drill",
                "handle",
                [
                    [
                        "pivot_spot",
                        "spot the pivot",
                        _spot(pivot, -spot_depths["pivot"], clear),
                    ],
                ],
            ),
            "stock": stock["handle"],
        },
        {
            **section(
                "drill-43",
                d43,
                "pivot drill",
                "drill",
                "handle",
                [
                    [
                        "pivot_drill",
                        "drill #43 through",
                        _pecked(pivot, pivot_tip, p["peck_43_mm"], clear),
                    ],
                ],
            ),
            "stock": stock["handle"],
        },
        {
            **section(
                "sink",
                dsink,
                "pivot sink",
                "drill",
                "handle",
                [
                    [
                        "pivot_sink",
                        "countersink the pivot",
                        _spot(pivot, sink_tip, clear),
                    ],
                ],
            ),
            "stock": stock["handle"],
        },
    ]
    # The boss round rides the seat's Job (same tool, speed and feed).
    jobs[0]["ops"].append(
        ["boss_round", "boss end round", _round(hub, round_r, levels, clear)]
    )

    def tap_stop(
        tool_key: str, at: tuple[float, float], thread: str, hole: str
    ) -> dict[str, Any]:
        return {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": f"SPINDLE STAYS OFF. NEXT: {thread} TAP IN THE {hole} HOLE",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{at[0]:.3f} Y{at[1]:.3f}",
                f"({thread} TAP THROUGH THE {hole} HOLE. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND, THE SPRING FOLLOWING, UNTIL THE TAP'S FULL THREADS ARE THROUGH. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": at,
        }

    manual = {
        "anchor_tap_stop": tap_stop("tap-2-56", anchor, "2-56", "ANCHOR"),
        "pivot_tap_stop": tap_stop("tap-4-40", pivot, "4-40", "PIVOT"),
    }

    # Keep-outs. CA01: the jaws' left ends at the least overhang, each jaw
    # beside the bar's edge, their tops jaw_top above Z0; the parallels under
    # the bar against each jaw, their left ends at the jaws' left ends, their
    # tops at the underside.
    def boxes(jaw_x0: float) -> list[dict[str, Any]]:
        jaw_x = (jaw_x0, jaw_x0 + p["vise_jaw_width_mm"])
        par_x = (jaw_x0, jaw_x0 + PARALLEL_LENGTH_MM)
        return [
            _box("fixed jaw", jaw_x, (0.0, JAW_DEPTH_MM), jaw_top),
            _box("moving jaw", jaw_x, (-2 * half - JAW_DEPTH_MM, -2 * half), jaw_top),
            _box("fixed-jaw parallel", par_x, (-PARALLEL_THICKNESS_MM, 0.0), -t),
            _box(
                "moving-jaw parallel",
                par_x,
                (-2 * half, -2 * half + PARALLEL_THICKNESS_MM),
                -t,
            ),
        ]

    ca01_boxes = boxes(p["overhang_min_mm"])
    # CA03: the arm runs to -X from the hub tip; the jaws' left ends at most
    # handle_jaw_end_max from it (nearest the round).
    ca03_boxes = boxes(-p["handle_jaw_end_max_mm"])

    t_ = numbers
    expect: list[list[Any]] = []
    hub_corners = [
        (0.0, 0.0),
        (0.0, -2 * half),
    ]
    handle_corners = [
        (_r(-(g["c2c"] + 2 * radius + e2_max)), 0.0),
        (_r(-(g["c2c"] + 2 * radius + e2_max)), _r(-2 * half)),
    ]

    def near(xy: tuple[float, float]) -> list[list[float]]:
        """A window round one path point: only the moves ending there."""
        return [[xy[0] - 1, xy[0] + 1], [xy[1] - 1, xy[1] + 1]]

    expect += [
        [
            "CA01_hub_end",
            "tool_changes",
            {
                "z_top": jaw_top,
                "tools": [t_["em"], t_["spot"], t_["drill-50"]],
                "loads_first": True,
            },
        ],
        [
            "CA01_hub_end",
            "spindle",
            {
                "rpm": [
                    [speeds["seat"][0]],
                    [speeds["anchor spot"][0]],
                    [speeds["anchor drill"][0]],
                ]
            },
        ],
        ["CA01_hub_end", "pauses", {"z_top": jaw_top, "count": 0}],
        ["CA01_hub_end", "depth", {"z_min": _r(min(bottom, anchor_tip))}],
        ["CA01_hub_end@0", "keep_out", {"radius": dem / 2, "boxes": ca01_boxes}],
        [
            "CA01_hub_end@1",
            "keep_out",
            {"radius": CENTRE_DRILL["body_mm"] / 2, "boxes": ca01_boxes},
        ],
        ["CA01_hub_end@2", "keep_out", {"radius": d50 / 2, "boxes": ca01_boxes}],
        ["CA01_hub_end@0", "air_feed", {"z_top": 0.0}],
        [
            "CA01_hub_end@0",
            "bounds",
            {
                "window": near((hub[0] + seat_r, hub[1])),
                "x": [_r(hub[0] - seat_r), _r(hub[0] + seat_r)],
                "y": [_r(hub[1] - seat_r), _r(hub[1] + seat_r)],
                "z_min": _r(bottom),
                "arc": "G2",
            },
        ],
        [
            "CA01_hub_end@0",
            "bounds",
            {
                "window": near((hub[0], hub[1] - round_r)),
                "x": [_r(hub[0] - round_r), _r(hub[0])],
                "y": [_r(hub[1] - round_r), _r(hub[1] + round_r)],
                "z_min": _r(bottom),
                "arc": "G3",
            },
        ],
        [
            "CA01_hub_end@0",
            "cleared",
            {"points": hub_corners, "radius": dem / 2, "z": _r(bottom)},
        ],
        # The seat's helix clockwise inside it, the boss round anticlockwise
        # outside it: both conventional (module docstring).
        [
            "CA01_hub_end@0",
            "arcs",
            {
                "z_top": 0.0,
                "centres": [hub],
                "radius": seat_r,
                "part": "outside",
                "cut": "conventional",
            },
        ],
        [
            "CA01_hub_end@0",
            "arcs",
            {
                "z_top": 0.0,
                "centres": [hub],
                "radius": round_r,
                "part": "inside",
                "cut": "conventional",
            },
        ],
        [
            "CA01_hub_end@1",
            "holes",
            {"centres": [anchor, mark], "z_bottom": _r(-spot_depths["hub"])},
        ],
        ["CA01_hub_end@1", "rapids_clear", {"z_top": 0.0}],
        ["CA01_hub_end@1", "vertical_below_top", {"z_top": 0.0}],
        ["CA01_hub_end@1", "air_feed", {"z_top": 0.0}],
        ["CA01_hub_end@2", "holes", {"centres": [anchor], "z_bottom": _r(anchor_tip)}],
        ["CA01_hub_end@2", "rapids_clear", {"z_top": 0.0, "open_holes": [anchor]}],
        ["CA01_hub_end@2", "vertical_below_top", {"z_top": 0.0}],
        ["CA01_hub_end@2", "air_feed", {"z_top": 0.0}],
        [
            "CA02_anchor_tap",
            "tap_stop",
            {"tool": t_["tap-guide"], "at": anchor, "machine_top": MACHINE_Z_TOP_MM},
        ],
        ["CA02_anchor_tap", "air_feed", {"z_top": 0.0}],
        [
            "CA03_handle_end",
            "tool_changes",
            {
                "z_top": jaw_top,
                "tools": [t_["em"], t_["spot"], t_["drill-43"], t_["sink"]],
                "loads_first": True,
            },
        ],
        [
            "CA03_handle_end",
            "spindle",
            {
                "rpm": [
                    [speeds["handle round"][0]],
                    [speeds["pivot spot"][0]],
                    [speeds["pivot drill"][0]],
                    [speeds["pivot sink"][0]],
                ]
            },
        ],
        ["CA03_handle_end", "pauses", {"z_top": jaw_top, "count": 0}],
        ["CA03_handle_end", "depth", {"z_min": _r(min(bottom, pivot_tip))}],
        ["CA03_handle_end@0", "keep_out", {"radius": dem / 2, "boxes": ca03_boxes}],
        [
            "CA03_handle_end@1",
            "keep_out",
            {"radius": CENTRE_DRILL["body_mm"] / 2, "boxes": ca03_boxes},
        ],
        ["CA03_handle_end@2", "keep_out", {"radius": d43 / 2, "boxes": ca03_boxes}],
        ["CA03_handle_end@3", "keep_out", {"radius": dsink / 2, "boxes": ca03_boxes}],
        ["CA03_handle_end", "air_feed", {"z_top": 0.0}],
        ["CA03_handle_end@0", "rapids_clear", {"z_top": 0.0}],
        [
            "CA03_handle_end@0",
            "bounds",
            {
                "window": near((pivot[0], pivot[1] - round_r)),
                "x": [_r(pivot[0] - round_r), _r(pivot[0])],
                "y": [_r(pivot[1] - round_r), _r(pivot[1] + round_r)],
                "z_min": _r(bottom),
                "arc": "G3",
            },
        ],
        [
            "CA03_handle_end@0",
            "cleared",
            {"points": handle_corners, "radius": dem / 2, "z": _r(bottom)},
        ],
        [
            "CA03_handle_end@0",
            "arcs",
            {
                "z_top": 0.0,
                "centres": [pivot],
                "radius": round_r,
                "part": "inside",
                "cut": "conventional",
            },
        ],
        [
            "CA03_handle_end@1",
            "holes",
            {"centres": [pivot], "z_bottom": _r(-spot_depths["pivot"])},
        ],
        ["CA03_handle_end@2", "holes", {"centres": [pivot], "z_bottom": _r(pivot_tip)}],
        ["CA03_handle_end@2", "rapids_clear", {"z_top": 0.0, "open_holes": [pivot]}],
        ["CA03_handle_end@2", "vertical_below_top", {"z_top": 0.0}],
        ["CA03_handle_end@3", "holes", {"centres": [pivot], "z_bottom": _r(sink_tip)}],
        ["CA03_handle_end@3", "rapids_clear", {"z_top": 0.0, "open_holes": [pivot]}],
        [
            "CA04_pivot_tap",
            "tap_stop",
            {"tool": t_["tap-guide"], "at": pivot, "machine_top": MACHINE_Z_TOP_MM},
        ],
        ["CA04_pivot_tap", "air_feed", {"z_top": 0.0}],
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
            doc, f"Arm {key}", ctx["step"], frame["origin"], frame["axes"]
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
