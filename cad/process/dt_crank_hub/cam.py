"""FreeCAD CAM recipe for MHA-DT-31, the crank hub.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The hub's sizes come
from the feature export (the barrel, the bore, the front and rear faces, the
#14 hole's station); the vise, the parallels, the spot, the pecks, the run
past the barrel's bottom and the feeds from ``plan.toml`` ``[parameters]``
and ``milling_cuts``; the drill's diameter from the shop (``shop/``). Every
path is written here (``rt.custom``): straight lines a recipe can state
exactly. Typed here, because neither record carries them: the #2 centre
drill's catalogue geometry (it sets the spot depth), the twist drill's 118°
point, the approach, safe and clearance heights and the vise jaws' depth
(keep-out shapes only).

Route (plan text in ``plan.toml``): the hub is turned and its bore drilled on
the lathe (no NC). It then lies in the vise, its axis along the jaws,
gripped on the barrel with the barrel on two 1 in parallels' inner top
edges: CM01 spots the barrel's top line and drills #14 down through the
barrel and the bore into the gap between the parallels. The #14 hole is
taper-reamed at assembly with the crankshaft (drawing note 1).

Work frame (G54): X0 the front face, +X along the hub's axis toward the rear
face; Y0 the barrel's axis; Z0 the barrel's top line.

Toolpath rules (owner rulings 2026-11-16): plunges at the cutting feed, real
G0 above the stock.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_crank_hub"
COMMENT = "MHA-DT-31 crank hub"
# Programs in order, each listing its operation keys, one section per
# group (a FreeCAD Job), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("CM01_pin_hole", (("pin_spot",), ("pin_drill",))),
)
# Every program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the lathe tools, the gauges and the files are not).
CAM_TOOLS = ("spot", "drill-14")
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
# Keep-outs: each vise jaw's depth outward from the gripped barrel; the
# parallels' length (4 in, shop-equipment fixtures.parallels-lms-6745).
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 4 * IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# The export's #14 band starts at the HA drill table's 4.623 mm, the shop
# record's .1820 in is 4.6228 mm: the drill is held to the band within this.
DRILL_TABLE_ROUNDING_MM = 0.0005


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


def _speed(plan: dict[str, Any], name: str) -> tuple[float, float]:
    """(rpm, mm/min) the milling cut ``name`` states; its operation prints
    the same rpm (the operator sets it at the tool change)."""
    op = _op_with_cut(plan, name)[0]
    rpm, feed = _cut(plan, name, "rpm"), _cut(plan, name, "feed_mm_min")
    if float(op["rpm"]) != rpm:
        raise ValueError(f"'{name}' rpm {rpm:g} is not its operation's {op['rpm']}")
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
    stated = plan["parameters"][key]
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
    """Drill from ``top`` to ``tip`` in pecks of ``peck`` with a full retract
    to the R plane and a rapid back to just above the last peck. Moves to and
    from the hole run at ``clear``."""
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


def _geometry(features: dict[str, Any]) -> dict[str, float]:
    """The hub as the route assumes it: the barrel, the bore and the faces
    along model Y from the front face at Y0; the #14 hole radial along +X,
    starting on the barrel at its station from the front face."""
    f = features["features"]
    barrel, bore, hole = f["barrel"], f["bore"], f["pin_hole"]
    front = f["front_face"]["plane"]["value"]
    rear = f["rear_face"]["plane"]["value"]
    if (
        front != 0.0
        or barrel["axis"] != [0.0, 1.0, 0.0]
        or bore["axis"] != [0.0, 1.0, 0.0]
    ):
        raise ValueError("barrel and bore: expected along model Y from the front face")
    if (
        barrel["at"][0] != 0.0
        or barrel["at"][2] != 0.0
        or bore["at"] != [0.0, 0.0, 0.0]
    ):
        raise ValueError("barrel and bore: expected on the model Y axis")
    if not bore["thru"]:
        raise ValueError("bore: expected through")
    length = rear - front
    band = f["rear_face"]["length"]
    if not band[0] <= length <= band[1]:
        raise ValueError(
            f"model length {length:.4f} is outside the printed band {band}"
        )
    radius = barrel["nominal_dia"] / 2
    start = barrel["at"][1]
    end = start + barrel["length_nominal"]
    if hole["axis"] != [1.0, 0.0, 0.0] or hole["at"][2] != 0.0 or not hole["thru"]:
        raise ValueError("pin_hole: expected through along +X in the Z0 plane")
    if not math.isclose(hole["at"][0], -radius, abs_tol=1e-6):
        raise ValueError("pin_hole: expected to start on the barrel")
    if hole["station_from"] != "front_face" or hole["at"][1] != hole["station_nominal"]:
        raise ValueError("pin_hole: expected its station from the front face")
    station = hole["station_nominal"]
    if not start < station < end:
        raise ValueError(f"pin_hole station {station} is off the barrel {start}–{end}")
    return {
        "length": length,
        "radius": radius,
        "barrel": (start, end),
        "bore_dia": bore["dia"],
        "station": station,
        "hole_dia": hole["dia"],
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    length, radius, station = g["length"], g["radius"], g["station"]

    d14 = _shop_tool(plan, shop, "drill-14")["diameter_mm"]
    low, high = g["hole_dia"]
    if not low - DRILL_TABLE_ROUNDING_MM <= d14 <= high:
        raise ValueError(f"#14 Ø{d14} outside the hole band {g['hole_dia']}")
    if not math.isclose(_cut(plan, "pin drill", "cutter_dia_mm"), d14, abs_tol=1e-6):
        raise ValueError(f"'pin drill' cutter_dia_mm is not its tool's Ø{d14}")
    if not math.isclose(
        _cut(plan, "pin spot", "cutter_dia_mm"), p["spot_dia_mm"], abs_tol=1e-6
    ):
        raise ValueError("'pin spot' cutter_dia_mm is not process.spot_dia_mm")
    if p["spot_dia_mm"] >= d14:
        raise ValueError("the spot is not under the #14")
    spot = _spot_depth(p["spot_dia_mm"])

    # Lying in the vise, axis along X, the barrel on the parallels' inner
    # top edges; Z0 the barrel's top line.
    gap = 2 * radius - 2 * p["parallel_thickness_mm"]
    _agree(plan, "cross_parallel_gap_mm", gap)
    drop = math.sqrt(radius**2 - (gap / 2) ** 2)  # axis above the parallels' tops
    _agree(plan, "cross_axis_height_mm", drop)
    jaw_top = p["vise_jaw_height_mm"] - p["parallel_height_mm"] - drop - radius
    _agree(plan, "cross_jaw_top_mm", jaw_top)
    # Only the barrel rests on the edges: the seat and relief, smaller,
    # stand clear above them.
    for name in ("seat", "relief"):
        feature = features["features"][name]
        small = feature.get("dia_ref") or feature["nominal_dia"]
        if small / 2 >= radius:
            raise ValueError(f"{name} is not under the barrel")
    # The #14 runs through the barrel, its full diameter past the bottom
    # line, into the gap between the parallels.
    tip = -(2 * radius + p["drill_past_mm"] + _point(d14))
    _agree(plan, "drill_tip_mm", tip)
    if d14 / 2 >= gap / 2:
        raise ValueError("the #14 reaches the parallels under the barrel")
    # The hole runs inside the barrel's length, off its ends by more than
    # the drill's radius.
    start, end = g["barrel"]
    if not start + d14 / 2 < station < end - d14 / 2:
        raise ValueError("the #14 breaks out of the barrel's ends")
    peck = p["peck_14_mm"]
    stated = _op_with_cut(plan, "pin drill")[0]
    if stated["peck"] != {"step_mm": peck, "retract": "full"}:
        raise ValueError("'pin drill' peck is not process.peck_14_mm with full retract")
    if peck > d14 + 1e-6:
        raise ValueError("process.peck_14_mm is over the #14's diameter")
    if stated["hole_depth_mm"] != "{{cad.barrel_dia_mm}}":
        raise ValueError("'pin drill' hole_depth_mm is not {{cad.barrel_dia_mm}}")
    speeds = {name: _speed(plan, name) for name in ("pin spot", "pin drill")}
    for name, key in (
        ("pin spot", "spot_feed_per_min_mm"),
        ("pin drill", "drill_14_feed_per_min_mm"),
    ):
        if not math.isclose(speeds[name][1], p[key], abs_tol=1e-6):
            raise ValueError(f"'{name}' feed_mm_min is not process.{key}")

    names = {t["id"]: t["name"] for t in plan["tools"]}
    numbers = {
        t["id"]: n
        for n, t in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    def drill(tool: str, dia: float, name: str) -> dict[str, Any]:
        rpm, feed = speeds[name]
        return {
            "tool": tool,
            "dia": dia,
            "shape": "drill",
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
            "tip_angle": CENTRE_DRILL["point_deg"]
            if tool == "spot"
            else DRILL_POINT_DEG,
        }

    # Frame (model point p -> axes · (p - origin)): work X the model's +Y
    # (front face to rear), work Z the model's -X (up, from the hole's start
    # on the barrel's top line), work Y = Z × X.
    frames = {
        "cross": {
            "origin": [-radius, 0.0, 0.0],
            "axes": [[0, 1, 0], [0, 0, -1], [-1, 0, 0]],
        },
    }
    stock = ((0.0, length), (-radius, radius), (-2 * radius, 0.0))
    xy = [_r(station), 0.0]
    clear = max(0.0, jaw_top) + CLEAR_MM
    jobs = [
        {
            **drill("spot", CENTRE_DRILL["body_mm"], "pin spot"),
            "frame": "cross",
            "label": "pin spot",
            "stock": stock,
            "ops": [["pin_spot", "spot the #14 hole", _spot(xy, 0.0, -spot, clear)]],
        },
        {
            **drill("drill-14", d14, "pin drill"),
            "frame": "cross",
            "label": "pin drill",
            "stock": stock,
            "ops": [
                [
                    "pin_drill",
                    "drill #14 through",
                    _pecked(xy, 0.0, tip, peck, clear),
                ]
            ],
        },
    ]

    # Keep-outs: the jaws on the barrel's equator, their tops jaw_top above
    # Z0, across the jaws' width centred on the hub; the parallels under it,
    # their tops at the axis less the drop.
    middle = length / 2
    jaw_x = (middle - p["vise_jaw_width_mm"] / 2, middle + p["vise_jaw_width_mm"] / 2)
    par_x = (middle - PARALLEL_LENGTH_MM / 2, middle + PARALLEL_LENGTH_MM / 2)
    par_top = -radius - drop
    boxes = [
        _box("moving jaw", jaw_x, (-radius - JAW_DEPTH_MM, -radius), jaw_top),
        _box("fixed jaw", jaw_x, (radius, radius + JAW_DEPTH_MM), jaw_top),
        _box("moving-jaw parallel", par_x, (-radius, -gap / 2), par_top),
        _box("fixed-jaw parallel", par_x, (gap / 2, radius), par_top),
    ]

    t = numbers
    top = max(0.0, jaw_top)

    def hole_checks(bottom: float, radius_: float) -> list[list[Any]]:
        return [
            ["holes", {"centres": [xy], "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": 0.0, "open_holes": [xy]}],
            ["vertical_below_top", {"z_top": 0.0}],
            ["air_feed", {"z_top": 0.0}],
            ["keep_out", {"radius": radius_, "boxes": boxes}],
        ]

    name = "CM01_pin_hole"
    expect: list[list[Any]] = [
        [
            name,
            "tool_changes",
            {"z_top": top, "tools": [t["spot"], t["drill-14"]], "loads_first": True},
        ],
        [name, "spindle", {"rpm": [[speeds["pin spot"][0]], [speeds["pin drill"][0]]]}],
        [name, "pauses", {"z_top": top, "count": 0}],
        [name, "depth", {"z_min": _r(tip)}],
    ]
    for k, checks in enumerate(
        (hole_checks(-spot, p["spot_dia_mm"] / 2), hole_checks(tip, d14 / 2))
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
