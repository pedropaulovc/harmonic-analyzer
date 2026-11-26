"""FreeCAD CAM recipe for MHA-PD-17, the transgear disc hub.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The hub's sizes come
from the feature export (the flange, the hub body, the spigot, the faces'
planes, the flange holes' centres, the key pin's chord, stop and station);
the parallels, the spot, the runs past the faces, the flat, the pecks and
the feeds from ``plan.toml`` ``[parameters]`` and ``milling_cuts``; the
drills', the end mill's and the reamer's diameters and the speeds from the
shop (``shop/``). Every path is written here (``rt.custom``): straight lines
a recipe can state exactly. Typed here, because no record carries them: the
#2 centre drill's catalogue geometry (it sets the spot depth), the twist
drills' 118° point, the 1/16 end mill's 1/8 in shank (MSC 35497056's
listing, #3568), the approach, safe and clearance heights and the vise
jaws' depth (keep-out shapes only).

Route (plan text in ``plan.toml``): the hub is turned, faced and its bore
reamed on the lathe (no NC). Setup 3 stands it upright, the flange's front
face on two stacked parallels, the body hanging between them: CM01 spots and
drills the three #51 holes through the flange. Setup 4 lays it across the
vise, gripped end to end, the body on a parallel against the fixed jaw:
CM02 plunges a flat with the 1/16 end mill where the chord hole meets the
sloping O.D., drills the #56 knockout through and the #53 to the stop;
CM03 reams .0615 to the stop.

Work frames (G54): CM01 X0 Y0 the bore's axis, Z0 the flange's rear face,
+Z up the spigot, the holes at 0°, 120° and 240° from +X (X along the
jaws). CM02/CM03 X0 the hub's axis (+X the chord's side), Y0 the hub front
face on the fixed jaw (the hub toward -Y), Z0 the hub's axis, +Z the chord
hole's entry side.

Toolpath rules (owner rulings 2026-11-16): plunges at the cutting feed, real
G0 above the stock; reamers fed in and fed out.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "pd_transgear_disc_hub"
COMMENT = "MHA-PD-17 transgear disc hub"
# Programs in order, each listing its operation keys, one section per
# group (a FreeCAD Job), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("CM01_flange_holes", (("flange_spot",), ("flange_drill",))),
    ("CM02_pin_hole", (("pin_flat",), ("pin_knockout",), ("pin_pilot",))),
    ("CM03_pin_ream", (("pin_ream",),)),
)
# Every program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the lathe tools, the gauges and the files are not).
CAM_TOOLS = ("spot", "drill-51", "endmill", "drill-56", "drill-53", "reamer-0615")
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included, its pilot ground
# with a 118° point: the shop record names the tool, not its geometry.
CENTRE_DRILL = {
    "body_mm": 3 / 16 * IN,
    "pilot_mm": 5 / 64 * IN,
    "pilot_length_mm": 5 / 64 * IN,
    "point_deg": 60.0,
    "pilot_point_deg": 118.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# The 1/16 end mill's shank (MSC 35497056, read 2026-11-24, #3568: 1/8 in).
ENDMILL_SHANK_MM = IN / 8
# The flat's floor this far under the O.D. at the end mill's outer edge.
FLAT_UNDER_MM = 0.2
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top (or the jaw tops).
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped part; the
# parallels' length (6 in, shop-equipment fixtures.parallels-lms-6745).
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 6 * IN
# The hub body's least radial air to each stack's inner face (CM01), and
# the knockout's point's least height over the parallel (CM02).
AIR_MIN_MM = 0.2
# Setup 1 (lathe): the blade's chuck-side face at least this far from the
# jaw fronts when it parts the hub off.
BLADE_ROOM_MM = 3.0
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
        match = re.fullmatch(r"\{\{process\.(\w+)\}\}", value)
        if not match:
            raise ValueError(f"{what}: expected a number or {{{{process.<name>}}}}")
        return float(plan["parameters"][match.group(1)])
    return float(value)


def _cut(plan: dict[str, Any], name: str, key: str) -> float:
    """Field ``key`` of the plan's milling cut ``name``."""
    return _resolve(plan, _op_with_cut(plan, name)[1][key], f"'{name}' {key}")


def _setting(
    plan: dict[str, Any], shop: dict[str, Any], cut: str
) -> tuple[float, float]:
    """(rpm, mm/min) of the shop setting the operation holding ``cut`` names
    (its literal ``in/min`` feed); the cut's own rpm and feed must agree."""
    op, _record_cut = _op_with_cut(plan, cut)
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    match = re.fullmatch(r"([\d.]+) in/min", record["feed"])
    if not match:
        raise ValueError(f"setting {op['settings']}: feed {record['feed']!r}")
    feed = float(match.group(1)) * IN
    for key, expected in (("rpm", rpm), ("feed_mm_min", feed)):
        if not math.isclose(_cut(plan, cut, key), expected, abs_tol=1e-3):
            raise ValueError(
                f"'{cut}' {key} {_cut(plan, cut, key):g} is not its setting's {expected:g}"
            )
    return rpm, feed


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
    stated = float(plan["parameters"][key])
    if not math.isclose(stated, value, abs_tol=PLAN_TOL_MM):
        raise ValueError(f"process.{key} {stated:g}, the recipe computes {value:.4f}")


def _spot_depth(dia: float) -> float:
    """Depth below the surface at which the #2 centre drill reaches ``dia``:
    on its pilot's 118° point under the pilot's diameter, on its 60°
    countersink between the pilot and the body."""
    pilot, body = CENTRE_DRILL["pilot_mm"], CENTRE_DRILL["body_mm"]
    if not 0 < dia <= body or math.isclose(dia, pilot, abs_tol=1e-6):
        raise ValueError(
            f"spot Ø{dia:.3f} is not a point spot under the pilot Ø{pilot:.3f} "
            f"nor between the pilot and the body Ø{body:.3f}"
        )
    if dia < pilot:
        return dia / 2 / math.tan(math.radians(CENTRE_DRILL["pilot_point_deg"] / 2))
    half = math.radians(CENTRE_DRILL["point_deg"] / 2)
    return CENTRE_DRILL["pilot_length_mm"] + (dia - pilot) / 2 / math.tan(half)


def _point(dia: float) -> float:
    """A twist drill's point length."""
    return dia / 2 / math.tan(math.radians(DRILL_POINT_DEG / 2))


def _height(radius: float, x: float) -> float:
    """The hub body's top (Z) at ``x`` from its axis, seen along the axis."""
    return math.sqrt(radius**2 - x**2)


def _plunge(xy: tuple[float, float], top: float, z: float, clear: float) -> list[str]:
    """One feed from the R plane over ``top`` to ``z``, a rapid back out."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _fed(xy: tuple[float, float], top: float, z: float, clear: float) -> list[str]:
    """A plunge fed in and fed back out to the R plane (a reamer: a rapid
    out of a finished hole can score it)."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G1 Z{r_plane:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def _pecked(
    xy: tuple[float, float], top: float, tip: float, peck: float, clear: float
) -> list[str]:
    """Feed from ``top`` to ``tip`` in pecks of ``peck`` with a full retract
    to the R plane and a rapid back to just above the last peck. Moves to
    and from the hole run at ``clear``."""
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


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The hub as the route assumes it: on the model Z axis, the flange's
    rear face at z = 0, the spigot toward +Z, the hub front face toward -Z;
    the flange holes through along Z on one circle; the key pin's chord
    ream along -X from the +X side, offset on -Y, its knockout on through."""
    f = features["features"]

    def plane(name: str) -> float:
        return f[name]["plane"]["value"]

    if plane("flange_rear_face") != 0.0:
        raise ValueError("flange_rear_face: expected the model's z = 0 plane")
    front, flange_front, spigot_end = (
        plane("front_face"),
        plane("flange_front_face"),
        plane("spigot_end"),
    )
    if not front < flange_front < 0.0 < spigot_end:
        raise ValueError("faces: expected front, flange front, rear, spigot end up Z")
    for name in ("flange", "spigot", "hub_body", "bore"):
        feature = f[name]
        if feature["at"][:2] != [0.0, 0.0] or abs(feature["axis"][2]) != 1.0:
            raise ValueError(f"{name}: expected on the model Z axis")
    holes = []
    for k in (1, 2, 3):
        hole = f[f"flange_hole_{k}"]
        if hole["axis"] != [0.0, 0.0, -1.0] or not hole["thru"] or hole["at"][2] != 0.0:
            raise ValueError(
                f"flange_hole_{k}: expected through along -Z from the rear face"
            )
        low, high = hole["bolt_circle_dia"]
        if not low <= 2 * math.hypot(*hole["at"][:2]) <= high:
            raise ValueError(f"flange_hole_{k}: its centre lies off its printed circle")
        holes.append((hole["at"][0], hole["at"][1]))
    ream, knockout = f["pin_ream"], f["pin_knockout"]
    if (
        ream["axis"] != [-1.0, 0.0, 0.0]
        or knockout["axis"] != ream["axis"]
        or knockout["at"] != ream["at"]
        or not knockout["thru"]
        or ream["chord_from"] != "bore"
        or ream["chord_axis"] != "y"
        or ream["station_from"] != "front_face"
    ):
        raise ValueError(
            "pin_ream, pin_knockout: expected one chord hole along -X on -Y, "
            "chorded from the bore and stationed from the front face"
        )
    chord = -ream["at"][1]
    station = ream["at"][2] - front
    for key, value in (("chord", chord), ("station", station)):
        low, high = ream[key]
        if not low <= value <= high:
            raise ValueError(f"pin_ream: its {key} {value:.4f} lies outside its band")
    return {
        "front": front,
        "flange_front": flange_front,
        "spigot_end": spigot_end,
        "flange_dia": f["flange"]["nominal_dia"],
        "flange_least": f["flange"]["dia"][0],
        "spigot_dia": f["spigot"]["dia_ref"],
        "body_dia": f["hub_body"]["nominal_dia"],
        "body_band": f["hub_body"]["dia"],
        "body_length": f["hub_body"]["length_nominal"],
        "overall": f["spigot_end"]["length_nominal"],
        "holes": holes,
        "flange_hole_dia": f["flange_hole_1"]["dia"],
        "chord": chord,
        "station": station,
        "ream_dia": ream["dia"],
        "stop": ream["stop"],
        "stop_nominal": ream["stop_nominal"],
        "knockout_dia": knockout["dia"],
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]

    # Lathe claims the traveler states (no NC): Setup 1's stickout holds the
    # facing, the parted hub, its kerf and the blade's and the AR's room;
    # Setup 2's regrip leaves the parted end out of the jaws.
    used = p["face_allowance_in"] + p["part_off_in"] + p["part_kerf_in"]
    if p["stickout_mm"] < used * IN + BLADE_ROOM_MM:
        raise ValueError(
            "process.stickout_mm leaves the blade no room clear of the jaws"
        )
    if not math.isclose(
        p["part_off_in"], g["overall"] / IN + p["regrip_allowance_in"], abs_tol=1e-4
    ):
        raise ValueError(
            "process.part_off_in is not the overall plus the regrip allowance"
        )
    _agree(plan, "regrip_out_mm", p["part_off_in"] * IN - g["body_length"])
    if not math.isclose(p["bar_use_in"], used, abs_tol=0.01):
        raise ValueError("process.bar_use_in is not the faced, parted length and kerf")
    if p["flange_run_in"] < p["part_off_in"] + p["part_kerf_in"]:
        raise ValueError("process.flange_run_in stops short of the parting line")

    # Tools: the spot under the #51; the #56 inside the flat; the #53 under
    # the reamer; the reamer and the #51 inside their bands.
    d51 = _shop_tool(plan, shop, "drill-51")["diameter_mm"]
    d56 = _shop_tool(plan, shop, "drill-56")["diameter_mm"]
    d53 = _shop_tool(plan, shop, "drill-53")["diameter_mm"]
    dem = _shop_tool(plan, shop, "endmill")["diameter_mm"]
    r615 = _shop_tool(plan, shop, "reamer-0615")["diameter_mm"]
    for name, dia, band in (
        ("drill-51", d51, g["flange_hole_dia"]),
        ("reamer-0615", r615, g["ream_dia"]),
        ("drill-56", d56, g["knockout_dia"]),
    ):
        if not band[0] <= dia <= band[1]:
            raise ValueError(f"{name} Ø{dia} is outside its hole band {band}")
    if not d56 <= dem or not d53 < r615 or not d56 < d53:
        raise ValueError(
            "the #56 is not inside the flat, or the #53 not between the #56 and the reamer"
        )
    for cut, dia in (
        ("flange drill", d51),
        ("pin flat", dem),
        ("pin knockout", d56),
        ("pin pilot", d53),
        ("pin ream", r615),
    ):
        if not math.isclose(_cut(plan, cut, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{cut}' cutter_dia_mm is not its tool's Ø{dia}")
    spot_dia = p["flange_spot_dia_mm"]
    if not math.isclose(
        _cut(plan, "flange spot", "cutter_dia_mm"), spot_dia, abs_tol=1e-6
    ):
        raise ValueError(
            "'flange spot' cutter_dia_mm is not process.flange_spot_dia_mm"
        )
    if spot_dia >= d51:
        raise ValueError("the spot is not under the #51")
    spot = _spot_depth(spot_dia)

    speeds = {
        name: _setting(plan, shop, name)
        for name in (
            "flange spot",
            "flange drill",
            "pin flat",
            "pin knockout",
            "pin pilot",
            "pin ream",
        )
    }
    for names, key in (
        (("flange spot",), "spot_feed_per_min_mm"),
        (("flange drill", "pin knockout", "pin pilot"), "drill_feed_per_min_mm"),
        (("pin flat",), "plunge_feed_per_min_mm"),
        (("pin ream",), "ream_feed_per_min_mm"),
    ):
        for name in names:
            if not math.isclose(speeds[name][1], p[key], abs_tol=1e-3):
                raise ValueError(f"'{name}' feed is not process.{key}")

    names = {t["id"]: t["name"] for t in plan["tools"]}
    numbers = {
        t["id"]: n
        for n, t in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")
    half_w = p["vise_jaw_width_mm"] / 2
    half_p = PARALLEL_LENGTH_MM / 2

    def section(
        tool: str,
        dia: float,
        shape: str,
        cut: str,
        tip: float | None,
        frame: str,
        stock,
    ) -> dict[str, Any]:
        rpm, feed = speeds[cut]
        return {
            "tool": tool,
            "dia": dia,
            "shape": shape,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
            "tip_angle": tip,
            "frame": frame,
            "stock": stock,
        }

    # --- CM01: upright on the stacks, Z0 the flange's rear face. ---------
    flange_r = g["flange_dia"] / 2
    thickness = p["parallel_thickness_mm"]
    _agree(plan, "flange_parallel_gap_mm", g["flange_dia"] - 2 * thickness)
    gap_half = g["flange_least"] / 2 - thickness
    if g["body_band"][1] / 2 > gap_half - AIR_MIN_MM:
        raise ValueError("the hub body does not hang clear between the stacks")
    seat = g["flange_front"]
    flange_jaw_top = p["vise_jaw_height_mm"] - p["parallel_stack_mm"] + seat
    _agree(plan, "flange_jaw_top_mm", flange_jaw_top)
    flange_tip = seat - p["flange_drill_past_mm"] - _point(d51)
    _agree(plan, "flange_drill_tip_mm", flange_tip)
    stated = _op_with_cut(plan, "flange drill")[0]
    if not math.isclose(
        float(stated["hole_depth_mm"]),
        -seat + p["flange_drill_past_mm"],
        abs_tol=PLAN_TOL_MM,
    ):
        raise ValueError(
            "'flange drill' hole_depth_mm is not the flange and the run past it"
        )
    if stated["peck"] != "none":
        raise ValueError("'flange drill' is one feed: peck = \"none\"")
    for x, y in g["holes"]:
        r = math.hypot(x, y)
        if abs(y) + d51 / 2 > gap_half - AIR_MIN_MM:
            raise ValueError("a flange hole's drill reaches a stack")
        if r - CENTRE_DRILL["body_mm"] / 2 <= g["spigot_dia"] / 2:
            raise ValueError("the centre drill's body reaches the spigot")
        if r - d51 / 2 <= g["body_band"][1] / 2:
            raise ValueError("a flange hole's drill runs into the hub body")
    flange_clear = max(flange_jaw_top, g["spigot_end"]) + CLEAR_MM
    if p["flange_tool_out_min_in"] * IN < flange_clear - flange_tip:
        raise ValueError(
            "process.flange_tool_out_min_in: the chuck reaches the jaw tops"
        )
    hole_xy = [[_r(x), _r(y)] for x, y in g["holes"]]
    cm01_stock = (
        (-flange_r, flange_r),
        (-flange_r, flange_r),
        (g["front"], g["spigot_end"]),
    )
    jobs = [
        {
            **section(
                "spot",
                CENTRE_DRILL["body_mm"],
                "drill",
                "flange spot",
                CENTRE_DRILL["point_deg"],
                "upright",
                cm01_stock,
            ),
            "label": "flange spots",
            "ops": [
                [
                    "flange_spot",
                    "spot the three flange holes",
                    [
                        line
                        for xy in hole_xy
                        for line in _plunge(xy, 0.0, -spot, flange_clear)
                    ],
                ]
            ],
        },
        {
            **section(
                "drill-51",
                d51,
                "drill",
                "flange drill",
                DRILL_POINT_DEG,
                "upright",
                cm01_stock,
            ),
            "label": "flange drill",
            "ops": [
                [
                    "flange_drill",
                    "drill #51 through the flange",
                    [
                        line
                        for xy in hole_xy
                        for line in _plunge(xy, 0.0, flange_tip, flange_clear)
                    ],
                ]
            ],
        },
    ]
    cm01_boxes = [
        _box(
            "moving jaw",
            (-half_w, half_w),
            (-flange_r - JAW_DEPTH_MM, -flange_r),
            flange_jaw_top,
        ),
        _box(
            "fixed jaw",
            (-half_w, half_w),
            (flange_r, flange_r + JAW_DEPTH_MM),
            flange_jaw_top,
        ),
        _box("moving-jaw stack", (-half_p, half_p), (-flange_r, -gap_half), seat),
        _box("fixed-jaw stack", (-half_p, half_p), (gap_half, flange_r), seat),
    ]
    cm01_circles = [
        {
            "name": "spigot",
            "centre": [0.0, 0.0],
            "radius": g["spigot_dia"] / 2,
            "z_top": g["spigot_end"],
        },
        {
            "name": "hub body",
            "centre": [0.0, 0.0],
            "radius": g["body_band"][1] / 2,
            "z_top": seat,
        },
    ]

    # --- CM02/CM03: lying, gripped end to end; Z0 the axis. -------------
    body_r = g["body_dia"] / 2
    r_max = g["body_band"][1] / 2
    r_min = g["body_band"][0] / 2
    axis_height = p["pin_parallel_height_mm"] + body_r
    pin_jaw_top = p["vise_jaw_height_mm"] - axis_height
    _agree(plan, "pin_jaw_top_mm", pin_jaw_top)
    _agree(plan, "pin_flange_top_mm", flange_r)
    chord, station = g["chord"], g["station"]
    xy = [_r(chord), _r(-station)]
    # The flat: the end mill's floor FLAT_UNDER_MM under the O.D. at its
    # outer edge, so the #56 starts square; it stays under the least O.D.
    flat = _height(body_r, chord + dem / 2) - FLAT_UNDER_MM
    _agree(plan, "pin_flat_bottom_mm", flat)
    if flat >= _height(r_min, chord + dem / 2):
        raise ValueError(
            "the flat's floor is not under the least O.D. at its outer edge"
        )
    em_top = _height(r_max, chord - dem / 2)
    shank_top = _height(r_max, chord - ENDMILL_SHANK_MM / 2)
    if p["endmill_reach_min_in"] * IN < shank_top - flat:
        raise ValueError(
            "process.endmill_reach_min_in: the end mill's shank reaches the body"
        )
    # No neck: the flutes run from the tip to the shank, so the shop
    # record's flute length is the end mill's reach.
    flutes = _shop_tool(plan, shop, "endmill")["flute_length_mm"]
    if flutes < p["endmill_reach_min_in"] * IN:
        raise ValueError(
            "process.endmill_reach_min_in: the end mill's flutes are shorter"
        )
    # The knockout: its full diameter knockout_past_mm past the underside at
    # the hole's inner edge; its point clear above the parallel (the body's
    # underside at the axis) for the least body.
    underside = -_height(body_r, chord - d56 / 2)
    knockout_tip = underside - p["knockout_past_mm"] - _point(d56)
    _agree(plan, "knockout_tip_mm", knockout_tip)
    if knockout_tip + _point(d56) > -_height(r_max, chord - d56 / 2):
        raise ValueError("the #56's full diameter does not leave the largest body")
    if knockout_tip < -r_min + AIR_MIN_MM:
        raise ValueError("the #56's point reaches the parallel")
    stop = -g["stop_nominal"]
    # The #53's full diameter ends at the nominal stop on purpose: its 118°
    # cone below is the pin's firm seat. A corrective CM03 rerun (the stop
    # short by the reamer's bevel, at most .010) is deliberately allowed to
    # end-cut into that cone in free-machining C360, rather than drilling the
    # #53 deeper and losing the seat; ops 350-360 take it in one rerun by the
    # measured shortfall only.
    pilot_tip = stop - _point(d53)
    _agree(plan, "pilot_tip_mm", pilot_tip)
    _agree(plan, "ream_tip_mm", stop)
    _agree(plan, "stop_shallow_mm", -g["stop"][0])
    _agree(plan, "stop_deep_mm", -g["stop"][1])
    pilot_top = _height(r_max, chord - d53 / 2)
    ream_top = _height(r_max, chord - r615 / 2)
    for key, depth, peck, dia in (
        ("pin knockout", flat - knockout_tip, p["peck_56_mm"], d56),
        ("pin pilot", flat - pilot_tip, p["peck_53_mm"], d53),
    ):
        stated = _op_with_cut(plan, key)[0]
        if not math.isclose(float(stated["hole_depth_mm"]), depth, abs_tol=PLAN_TOL_MM):
            raise ValueError(f"'{key}' hole_depth_mm is not {depth:.4f}")
        if stated["peck"] != {"step_mm": peck, "retract": "full"}:
            raise ValueError(f"'{key}' peck is not its process peck with full retract")
        if peck > dia + 1e-6:
            raise ValueError(f"'{key}' pecks over its drill's diameter")
    if p["pin_flat_peck_mm"] > dem / 2:
        raise ValueError(
            "process.pin_flat_peck_mm plunges over half the end mill's diameter"
        )
    flange_y = (-(0.0 - g["front"]), -(g["flange_front"] - g["front"]))
    pin_clear = max(flange_r, pin_jaw_top) + CLEAR_MM
    deepest = min(knockout_tip, pilot_tip, stop)
    if p["pin_tool_out_min_in"] * IN < pin_clear - deepest:
        raise ValueError(
            "process.pin_tool_out_min_in: the chuck reaches the flange's top"
        )
    # The hole's side is the work's +X: the model's -Y; down the hole the
    # model's -X; the hub front face at Y0, the hub toward -Y.
    frames = {
        "upright": {
            "origin": [0.0, 0.0, 0.0],
            "axes": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        },
        "lying": {
            "origin": [0.0, 0.0, g["front"]],
            "axes": [[0, -1, 0], [0, 0, -1], [1, 0, 0]],
        },
    }
    lying_stock = ((-flange_r, flange_r), (-g["overall"], 0.0), (-flange_r, flange_r))
    jobs += [
        {
            **section(
                "endmill", dem, "endmill", "pin flat", None, "lying", lying_stock
            ),
            "label": "pin flat",
            "ops": [
                [
                    "pin_flat",
                    "plunge the flat",
                    _pecked(xy, em_top, flat, p["pin_flat_peck_mm"], pin_clear),
                ]
            ],
        },
        {
            **section(
                "drill-56",
                d56,
                "drill",
                "pin knockout",
                DRILL_POINT_DEG,
                "lying",
                lying_stock,
            ),
            "label": "pin knockout",
            "ops": [
                [
                    "pin_knockout",
                    "drill #56 through",
                    _pecked(xy, flat, knockout_tip, p["peck_56_mm"], pin_clear),
                ]
            ],
        },
        {
            **section(
                "drill-53",
                d53,
                "drill",
                "pin pilot",
                DRILL_POINT_DEG,
                "lying",
                lying_stock,
            ),
            "label": "pin pilot",
            "ops": [
                [
                    "pin_pilot",
                    "drill #53 to the stop",
                    _pecked(xy, pilot_top, pilot_tip, p["peck_53_mm"], pin_clear),
                ]
            ],
        },
        {
            **section(
                "reamer-0615", r615, "reamer", "pin ream", None, "lying", lying_stock
            ),
            "label": "pin ream",
            "ops": [
                [
                    "pin_ream",
                    "ream .0615 to the stop",
                    _fed(xy, ream_top, stop, pin_clear),
                ]
            ],
        },
    ]
    cm02_boxes = [
        _box("fixed jaw", (-half_w, half_w), (0.0, JAW_DEPTH_MM), pin_jaw_top),
        _box(
            "moving jaw",
            (-half_w, half_w),
            (-g["overall"] - JAW_DEPTH_MM, -g["overall"]),
            pin_jaw_top,
        ),
        _box("parallel", (-half_p, half_p), (-thickness, 0.0), -r_min),
        _box("flange", (-flange_r, flange_r), (min(flange_y), max(flange_y)), flange_r),
    ]

    def hole_checks(
        centres: list[list[float]],
        top: float,
        bottom: float,
        radius: float,
        boxes,
        circles=(),
    ) -> list[list[Any]]:
        return [
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": _r(top), "open_holes": centres}],
            ["vertical_below_top", {"z_top": _r(top)}],
            ["air_feed", {"z_top": _r(top)}],
            ["keep_out", {"radius": radius, "boxes": boxes, "circles": list(circles)}],
        ]

    t = numbers
    expect: list[list[Any]] = []
    for name, tools, cuts, top, z_min, pauses_top in (
        (
            "CM01_flange_holes",
            ("spot", "drill-51"),
            ("flange spot", "flange drill"),
            flange_jaw_top,
            flange_tip,
            flange_clear - CLEAR_MM,
        ),
        (
            "CM02_pin_hole",
            ("endmill", "drill-56", "drill-53"),
            ("pin flat", "pin knockout", "pin pilot"),
            flange_r,
            knockout_tip,
            pin_clear - CLEAR_MM,
        ),
        (
            "CM03_pin_ream",
            ("reamer-0615",),
            ("pin ream",),
            flange_r,
            stop,
            pin_clear - CLEAR_MM,
        ),
    ):
        expect += [
            [
                name,
                "tool_changes",
                {
                    "z_top": _r(pauses_top),
                    "tools": [t[k] for k in tools],
                    "loads_first": True,
                },
            ],
            [name, "spindle", {"rpm": [[speeds[cut][0]] for cut in cuts]}],
            [name, "pauses", {"z_top": _r(pauses_top), "count": 0}],
            [name, "depth", {"z_min": _r(z_min)}],
        ]
    sections = (
        (
            "CM01_flange_holes@0",
            hole_xy,
            0.0,
            -spot,
            CENTRE_DRILL["body_mm"],
            cm01_boxes,
            cm01_circles,
        ),
        (
            "CM01_flange_holes@1",
            hole_xy,
            0.0,
            flange_tip,
            d51,
            cm01_boxes,
            cm01_circles,
        ),
        ("CM02_pin_hole@0", [xy], em_top, flat, dem, cm02_boxes, ()),
        ("CM02_pin_hole@1", [xy], flat, knockout_tip, d56, cm02_boxes, ()),
        ("CM02_pin_hole@2", [xy], pilot_top, pilot_tip, d53, cm02_boxes, ()),
        ("CM03_pin_ream@0", [xy], ream_top, stop, r615, cm02_boxes, ()),
    )
    for program, centres, top, bottom, dia, boxes, circles in sections:
        expect += [
            [program, check, kwargs]
            for check, kwargs in hole_checks(
                centres, top, bottom, dia / 2, boxes, circles
            )
        ]
    expect.append(["CM03_pin_ream@0", "feed_out", {"z_top": _r(ream_top)}])

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
        "spot_depth": _r(-spot),
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
            doc, f"Hub {key}", ctx["step"], frame["origin"], frame["axes"]
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
            tip_angle=section.get("tip_angle"),
        )
        for key, label, lines in section["ops"]:
            ops[key] = rt.custom(target, tc, label, lines)
    ops.update(ctx["manual"])
    rt.generate(doc)
    return {"ops": ops}
