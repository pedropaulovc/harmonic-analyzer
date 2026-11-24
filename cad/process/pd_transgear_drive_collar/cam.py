"""FreeCAD CAM recipe for MHA-PD-22, the transgear drive collar.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The collar's sizes
come from the feature export (the outside, the pilot, the bore, the dowel
holes' and the flat pin's centres from the bore, the flat pin's floor
station, the supply lengths); the body's supply length, the parallels, the
spots, the pecks, the runs past the seat face and the feeds from
``plan.toml`` ``[parameters]`` and ``milling_cuts``; the drills' and
reamers' diameters and the speeds from the shop (``shop/``). Every path is
written here (``rt.custom``): straight lines a recipe can state exactly.
Typed here, because no record carries them: the #2 centre drill's catalogue
geometry (it sets the spot depths), the twist drills' 118° point, the
approach, safe and clearance heights and the vise jaws' depth (keep-out
shapes only).

Route (plan text in ``plan.toml``): the collar is turned, its bore drilled #11
and the body parted off long on the lathe (no NC). It then stands in the
vise seat face down on two stacked parallels, the pilot hanging between
them, rear face up: CM01 spots, drills #43 and reams the 2X .0930 dowel
holes through into the gap between the stacks, then drills #53 and reams
the .0615 flat pin's hole blind to its floor.

Work frame (G54): X0 Y0 the bore's axis (swept with the DTI), +X toward the
dowel on the model's +Y; Z0 the rear face, the body's supply length above
the seat face.

Toolpath rules (owner rulings 2026-11-16): plunges at the cutting feed, real
G0 above the stock; reamers fed in and fed out.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "pd_transgear_drive_collar"
COMMENT = "MHA-PD-22 transgear drive collar"
# Programs in order, each listing its operation keys, one section per
# group (a FreeCAD Job), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    (
        "CM01_holes",
        (
            ("spot",),
            ("dowel_drill",),
            ("dowel_ream",),
            ("flat_drill",),
            ("flat_ream",),
        ),
    ),
)
# Every program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the lathe tools, the gauges and the files are not).
CAM_TOOLS = ("spot", "drill-43", "reamer-0930", "drill-53", "reamer-0615")
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
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top (or the jaw tops).
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped outside; the
# parallels' length (6 in, shop-equipment fixtures.parallels-lms-6745).
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 6 * IN
# The pilot's least radial air to each stack's inner face.
PILOT_AIR_MIN_MM = 0.2
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
    op, record_cut = _op_with_cut(plan, cut)
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


def _fed(xy: tuple[float, float], z: float, clear: float) -> list[str]:
    """A plunge fed in and fed back out to the R plane (a reamer: a rapid
    out of a finished hole can score it)."""
    clear, r_plane = _r(clear), _r(SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G1 Z{r_plane:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def _pecked(
    xy: tuple[float, float], tip: float, peck: float, clear: float
) -> list[str]:
    """Drill from Z0 to ``tip`` in pecks of ``peck`` with a full retract to
    the R plane and a rapid back to just above the last peck. Moves to and
    from the hole run at ``clear``."""
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


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The collar as the route assumes it: the outside, pilot and bore on the
    model Z axis from the seat face at z = 0 (rearward +Z); the dowel holes
    through along Z on the Y axis; the flat pin's hole blind from the rear
    face along -Z on -Y, its floor stationed from the seat face."""
    f = features["features"]
    outer, pilot, bore = f["outer"], f["pilot"], f["bore"]
    if f["seat_face"]["plane"]["value"] != 0.0:
        raise ValueError("seat_face: expected the model's z = 0 plane")
    for name in ("outer", "pilot", "bore"):
        feature = f[name]
        if feature["at"][:2] != [0.0, 0.0] or abs(feature["axis"][2]) != 1.0:
            raise ValueError(f"{name}: expected on the model Z axis")
    if not bore["thru"]:
        raise ValueError("bore: expected through")
    dowels = []
    for name in ("dowel_a", "dowel_b"):
        hole = f[name]
        if (
            hole["axis"] != [0.0, 0.0, 1.0]
            or not hole["thru"]
            or hole["at"][0] != 0.0
            or hole["offset_from"] != "bore"
            or hole["offset_axis"] != "y"
        ):
            raise ValueError(
                f"{name}: expected through along Z on the Y axis, from the bore"
            )
        low, high = hole["offset"]
        if not low <= abs(hole["at"][1]) <= high:
            raise ValueError(f"{name}: its centre lies outside its exported offset")
        dowels.append((hole["at"][1], hole["dia"], (low, high)))
    flat = f["flat_pin_hole"]
    if (
        flat["axis"] != [0.0, 0.0, -1.0]
        or flat["at"][0] != 0.0
        or flat["centre_from"] != "bore"
        or flat["centre_axis"] != "y"
    ):
        raise ValueError(
            "flat_pin_hole: expected blind along -Z on the Y axis, from the bore"
        )
    floor = f["flat_pin_floor"]
    if floor["station_from"] != "seat_face" or floor["floor_of"] != "flat_pin_hole":
        raise ValueError(
            "flat_pin_floor: expected the flat pin's floor from the seat face"
        )
    if dowels[0][0] * dowels[1][0] >= 0 or dowels[1][0] * flat["at"][1] <= 0:
        raise ValueError(
            "dowels: expected either side of the axis, dowel_b on the flat pin's side"
        )
    return {
        "outer_dia": outer["nominal_dia"],
        "outer_least": outer["dia"][0],
        "outer_most": outer["dia"][1],
        "pilot_max": pilot["dia"][1],
        "bore_dia": bore["dia"],
        "dowels": dowels,
        "flat_y": flat["at"][1],
        "flat_dia": flat["dia"],
        "flat_centre": flat["centre"],
        "floor_band": floor["station"],
        "body_supply_min": f["rear_face"]["supply_length_min"],
        "pilot_supply_min": f["pilot_face"]["supply_length_min"],
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    body = p["body_supply_in"] * IN
    body_min, body_max = p["body_min_in"] * IN, p["body_max_in"] * IN
    if body_min < g["body_supply_min"] - 1e-6 or not body_min <= body <= body_max:
        raise ValueError(
            "process.body_min_in..body_max_in: under the supply or around no target"
        )
    pilot_min, pilot_max = p["pilot_supply_min_in"], p["pilot_supply_max_in"]
    if (
        pilot_min * IN < g["pilot_supply_min"] - 1e-6
        or not pilot_min <= p["pilot_supply_in"] <= pilot_max
    ):
        raise ValueError(
            "process.pilot_supply_min_in..max_in: under the supply or around no target"
        )
    # The part-off is fixed from Z0: the seat face's window mirrors the body's.
    part_off = p["part_off_in"]
    if not math.isclose(
        part_off, p["pilot_supply_in"] + p["body_supply_in"], abs_tol=1e-6
    ) or (
        part_off - pilot_max < p["body_min_in"] - 1e-6
        or part_off - pilot_min > p["body_max_in"] + 1e-6
    ):
        raise ValueError(
            "process.part_off_in: the seat face's window parts the body outside its window"
        )
    radius = g["outer_dia"] / 2

    # The exported limits of the reamed sizes and the dowel centres are the
    # spec's ANALYSIS bands (the sheet prints neither: the pins are the
    # holes' gauges and the wheels' trial accepts the centres); they bound
    # this recipe's own consistency checks only.
    # Tools: each drill under its reamer, each reamer inside its band, each
    # spot under its drill.
    d43 = _shop_tool(plan, shop, "drill-43")["diameter_mm"]
    d53 = _shop_tool(plan, shop, "drill-53")["diameter_mm"]
    r93 = _shop_tool(plan, shop, "reamer-0930")["diameter_mm"]
    r615 = _shop_tool(plan, shop, "reamer-0615")["diameter_mm"]
    dowel_band = g["dowels"][0][1]
    for name, dia, band in (
        ("reamer-0930", r93, dowel_band),
        ("reamer-0615", r615, g["flat_dia"]),
    ):
        if not band[0] <= dia <= band[1]:
            raise ValueError(f"{name} Ø{dia} is outside its hole band {band}")
    if not d43 < r93 or not d53 < r615:
        raise ValueError("a drill is not under its reamer")
    for cut, dia in (
        ("dowel drill", d43),
        ("dowel ream", r93),
        ("flat drill", d53),
        ("flat ream", r615),
    ):
        if not math.isclose(_cut(plan, cut, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{cut}' cutter_dia_mm is not its tool's Ø{dia}")
    if not math.isclose(
        _cut(plan, "spot", "cutter_dia_mm"), p["spot_dia_mm"], abs_tol=1e-6
    ):
        raise ValueError("'spot' cutter_dia_mm is not process.spot_dia_mm")
    if p["spot_dia_mm"] >= min(d43, d53):
        raise ValueError("the spot is not under both drills")
    if abs(g["flat_y"]) - p["spot_dia_mm"] / 2 <= g["bore_dia"][1] / 2:
        raise ValueError("the flat pin's spot runs into the bore's edge")
    spot = _spot_depth(p["spot_dia_mm"])

    # Holding: the seat face on the stacks' tops, the pilot hanging in the
    # gap between them (printed at the outside's band middle, cleared at its
    # least), the rear face (Z0) the body's supply above it.
    thick = p["parallel_thickness_mm"]
    _agree(
        plan, "parallel_gap_mm", (g["outer_least"] + g["outer_most"]) / 2 - 2 * thick
    )
    gap = g["outer_least"] - 2 * thick
    if g["pilot_max"] / 2 > gap / 2 - PILOT_AIR_MIN_MM:
        raise ValueError("the pilot does not hang clear between the stacks")
    jaw_top = p["vise_jaw_height_mm"] - p["parallel_stack_mm"] - body
    _agree(plan, "rear_over_jaws_mm", -jaw_top)
    seat = -body

    # Dowels: through, the #43's full diameter drill_past_mm past the seat
    # face and the reamer's end ream_past_mm past it, both into the gap
    # beside the pilot.
    dowel_drill_tip = seat - p["drill_past_mm"] - _point(d43)
    _agree(plan, "dowel_drill_tip_mm", dowel_drill_tip)
    dowel_ream_tip = seat - p["ream_past_mm"]
    _agree(plan, "dowel_ream_tip_mm", dowel_ream_tip)
    bevel = p["ream_bevel_max_in"] * IN
    if p["ream_past_mm"] <= bevel or dowel_ream_tip <= dowel_drill_tip:
        raise ValueError(
            "the dowel reamer is not full size through, or runs past the drill"
        )
    for y, _dia, band in g["dowels"]:
        if not band[0] <= abs(y) <= band[1]:
            raise ValueError("a dowel centre lies outside its band")
        if abs(y) - d43 / 2 <= g["pilot_max"] / 2:
            raise ValueError("a dowel drill runs into the pilot below the seat face")
        if d43 / 2 >= gap / 2:
            raise ValueError("a dowel drill reaches the stacks")
    # The flat pin's hole: from Z0 down to its stations from the seat face.
    # With the body anywhere in its window and the reamer's bevel up to
    # ream_bevel_max_in, the full-diameter floor stays in the printed band;
    # the drill's point stays in the body; the reamer stays in the drilled
    # full diameter.
    ream_station = p["flat_ream_station_in"] * IN
    drill_station = p["flat_drill_station_in"] * IN
    flat_ream_tip = seat + ream_station
    _agree(plan, "flat_ream_tip_mm", flat_ream_tip)
    flat_drill_full = seat + drill_station
    flat_drill_tip = flat_drill_full - _point(d53)
    _agree(plan, "flat_drill_tip_mm", flat_drill_tip)
    floor_low = ream_station + (body_min - body)
    floor_high = ream_station + (body_max - body) + bevel
    band = g["floor_band"]
    if floor_low < band[0] - 1e-6 or floor_high > band[1] + 1e-6:
        raise ValueError(
            f"the flat pin's floor {floor_low:.3f}..{floor_high:.3f} leaves {band}"
        )
    if (
        drill_station >= ream_station
        or drill_station - _point(d53) + (body_min - body) <= 0
    ):
        raise ValueError("the #53 is not past the reamer, or its point leaves the body")
    if not g["flat_centre"][0] <= abs(g["flat_y"]) <= g["flat_centre"][1]:
        raise ValueError("the flat pin's centre lies outside its band")
    for key, depth in (
        ("dowel drill", body + p["drill_past_mm"]),
        ("flat drill", body - drill_station),
    ):
        stated = _op_with_cut(plan, key)[0]
        if not math.isclose(float(stated["hole_depth_mm"]), depth, abs_tol=PLAN_TOL_MM):
            raise ValueError(f"'{key}' hole_depth_mm is not {depth:.3f}")
    for key, peck, dia in (
        ("dowel drill", p["peck_43_mm"], d43),
        ("flat drill", p["peck_53_mm"], d53),
    ):
        stated = _op_with_cut(plan, key)[0]
        if stated["peck"] != {"step_mm": peck, "retract": "full"}:
            raise ValueError(f"'{key}' peck is not its process peck with full retract")
        if peck > dia + 1e-6:
            raise ValueError(f"'{key}' pecks over its drill's diameter")
    deepest = -min(dowel_drill_tip, dowel_ream_tip, flat_drill_tip, flat_ream_tip)
    if p["tool_out_min_in"] * IN < deepest + CLEAR_MM:
        raise ValueError("process.tool_out_min_in does not reach the deepest tip")

    speeds = {
        name: _setting(plan, shop, name)
        for name in ("spot", "dowel drill", "dowel ream", "flat drill", "flat ream")
    }
    for names, key in (
        (("spot",), "spot_feed_per_min_mm"),
        (("dowel drill", "flat drill"), "drill_feed_per_min_mm"),
        (("dowel ream", "flat ream"), "ream_feed_per_min_mm"),
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

    def section(
        tool: str, dia: float, shape: str, cut: str, tip: float | None
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
            "frame": "top",
            "stock": stock,
        }

    # Frame (model point q -> axes · (q - origin)): work X the model's +Y,
    # work Z the model's +Z (up, from the supplied rear face), work Y = Z × X.
    frames = {
        "top": {"origin": [0.0, 0.0, body], "axes": [[0, 1, 0], [-1, 0, 0], [0, 0, 1]]}
    }
    stock = (
        (-radius, radius),
        (-radius, radius),
        (seat - p["pilot_supply_in"] * IN, 0.0),
    )
    dowel_xy = [[_r(y), 0.0] for y, _dia, _band in g["dowels"]]
    flat_xy = [_r(g["flat_y"]), 0.0]
    clear = max(0.0, jaw_top) + CLEAR_MM
    jobs = [
        {
            **section(
                "spot",
                CENTRE_DRILL["body_mm"],
                "drill",
                "spot",
                CENTRE_DRILL["point_deg"],
            ),
            "label": "spots",
            "ops": [
                [
                    "spot",
                    "spot the three holes",
                    [
                        line
                        for xy in dowel_xy + [flat_xy]
                        for line in _spot(xy, -spot, clear)
                    ],
                ]
            ],
        },
        {
            **section("drill-43", d43, "drill", "dowel drill", DRILL_POINT_DEG),
            "label": "dowel drill",
            "ops": [
                [
                    "dowel_drill",
                    "drill #43 through",
                    [
                        line
                        for xy in dowel_xy
                        for line in _pecked(xy, dowel_drill_tip, p["peck_43_mm"], clear)
                    ],
                ]
            ],
        },
        {
            **section("reamer-0930", r93, "reamer", "dowel ream", None),
            "label": "dowel ream",
            "ops": [
                [
                    "dowel_ream",
                    "ream .0930 through",
                    [
                        line
                        for xy in dowel_xy
                        for line in _fed(xy, dowel_ream_tip, clear)
                    ],
                ]
            ],
        },
        {
            **section("drill-53", d53, "drill", "flat drill", DRILL_POINT_DEG),
            "label": "flat drill",
            "ops": [
                [
                    "flat_drill",
                    "drill #53 blind",
                    _pecked(flat_xy, flat_drill_tip, p["peck_53_mm"], clear),
                ]
            ],
        },
        {
            **section("reamer-0615", r615, "reamer", "flat ream", None),
            "label": "flat ream",
            "ops": [
                ["flat_ream", "ream .0615 blind", _fed(flat_xy, flat_ream_tip, clear)]
            ],
        },
    ]

    # Keep-outs: the jaws on the outside's equator across the jaws' width,
    # their tops jaw_top from Z0; the stacks under the seat face, between
    # the jaws and the gap.
    half_w = p["vise_jaw_width_mm"] / 2
    half_p = PARALLEL_LENGTH_MM / 2
    boxes = [
        _box(
            "moving jaw", (-half_w, half_w), (-radius - JAW_DEPTH_MM, -radius), jaw_top
        ),
        _box("fixed jaw", (-half_w, half_w), (radius, radius + JAW_DEPTH_MM), jaw_top),
        _box("moving-jaw stack", (-half_p, half_p), (-radius, -gap / 2), seat),
        _box("fixed-jaw stack", (-half_p, half_p), (gap / 2, radius), seat),
    ]

    def hole_checks(
        centres: list[list[float]], bottom: float, radius_: float
    ) -> list[list[Any]]:
        return [
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": 0.0, "open_holes": centres}],
            ["vertical_below_top", {"z_top": 0.0}],
            ["air_feed", {"z_top": 0.0}],
            ["keep_out", {"radius": radius_, "boxes": boxes}],
        ]

    t = numbers
    top = max(0.0, jaw_top)
    name = "CM01_holes"
    rpms = [
        speeds[cut][0]
        for cut in ("spot", "dowel drill", "dowel ream", "flat drill", "flat ream")
    ]
    expect: list[list[Any]] = [
        [
            name,
            "tool_changes",
            {"z_top": top, "tools": [t[k] for k in CAM_TOOLS], "loads_first": True},
        ],
        [name, "spindle", {"rpm": [[rpm] for rpm in rpms]}],
        [name, "pauses", {"z_top": top, "count": 0}],
        [name, "depth", {"z_min": _r(min(dowel_drill_tip, dowel_ream_tip))}],
    ]
    for k, (centres, bottom, dia) in enumerate(
        (
            (dowel_xy + [flat_xy], -spot, CENTRE_DRILL["body_mm"]),
            (dowel_xy, dowel_drill_tip, d43),
            (dowel_xy, dowel_ream_tip, r93),
            ([flat_xy], flat_drill_tip, d53),
            ([flat_xy], flat_ream_tip, r615),
        )
    ):
        expect += [
            [f"{name}@{k}", check, kwargs]
            for check, kwargs in hole_checks(centres, bottom, dia / 2)
        ]
    for k in (2, 4):
        expect.append([f"{name}@{k}", "feed_out", {"z_top": 0.0}])

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
            doc, f"Collar {key}", ctx["step"], frame["origin"], frame["axes"]
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
