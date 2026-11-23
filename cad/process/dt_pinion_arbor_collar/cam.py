"""FreeCAD CAM recipe for MHA-DT-33, the pinion arbor retention collar: its
1/16 pin hole.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The turned O.D., the
pin hole's diameter band and its station from the datum end come from the
feature export; the bar, the parallel, the overhang, the spot, the pecks and
the drill's run past the O.D. from ``plan.toml`` ``[parameters]`` and
``milling_cuts``; the 1/16's diameter from ``shop/``. Every path is written
here (``rt.custom``). Typed here, because neither record carries them: the #1
centre drill's catalogue geometry (it sets the spot depth), the twist drill's
118° point, the safe and clearance heights and the vise jaws' depth
(keep-out shapes only).

Route (``plan.toml``): the collar is still the turned end of its 2 in blank
of 5/8 bar (faced, turned to Ø.59 .80 long, drilled 5/16). On the mill the
blank lies along the vise jaws on one 1 in parallel standing on edge, the
turned end .50 in out past the jaws' left side, an offcut of the bar on the
parallel's right end. PC01 spots the pin hole with the #1 centre drill and
pecks the 1/16 through both walls, in the overhang, into air.

Work frame (G54): X0 the datum end (face F), +X along the blank; Y0 the
turned O.D.'s axis; Z0 the top of the turned O.D.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_pinion_arbor_collar"
COMMENT = "MHA-DT-33 pinion arbor retention collar"
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("PC01_pin_hole", (("pin_spot",), ("pin_drill",))),
)
# The program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = ("PC01_pin_hole",)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the lathe tools, the blade and the files are not).
CAM_TOOLS = ("spot", "drill-1-16")
IN = 25.4
# ANSI #1 combined drill and countersink, 60° included (the carbide set's
# trade size 1, "for 3/64 in drill bit"): the shop record names the set, not
# its geometry.
CENTRE_DRILL = {
    "pilot_mm": 3 / 64 * IN,
    "pilot_length_mm": 3 / 64 * IN,
    "body_mm": 1 / 8 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop record gives the diameter only).
DRILL_POINT_DEG = 118.0
# Drill R planes start this far above the O.D. top: real G0 brings the tool
# down to it, beside the jaws.
SAFE_MM = 1.0
# Moves to and from the hole run this far above the jaw tops; each tool
# projects at least the jaw tops plus its depth plus this from the chuck.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped bar; the spacer
# (an offcut of the bar) on the 4 in parallel's right end.
JAW_DEPTH_MM = IN
SPACER_MM = IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
HOLE = "pin_hole"


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


def _speed(plan: dict[str, Any], cut: str) -> tuple[float, float]:
    """(rpm, mm/min) the plan authors on the cut, agreeing with the rpm its
    operation prints (the operation's feed is printed text)."""
    op, _record = _op_with_cut(plan, cut)
    rpm, feed = _cut(plan, cut, "rpm"), _cut(plan, cut, "feed_mm_min")
    if float(op["rpm"]) != rpm:
        raise ValueError(f"'{cut}': its operation's rpm is not the cut's {rpm:g}")
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
    """Depth below the O.D. top at which the #1 centre drill's 60° countersink
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


def _spot(xy: list[float], z: float, clear: float) -> list[str]:
    clear, r_plane = _r(clear), _r(SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _pecked(xy: list[float], tip: float, peck: float, clear: float) -> list[str]:
    """Drill from the O.D. top to ``tip`` in pecks of ``peck``, each with a
    full retract to the R plane and a rapid back to just above the last peck.
    Moves to and from the hole run at ``clear``."""
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


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The collar and its pin hole from the export, in the model frame: the
    turning axis along model Z, the datum end (face F) at Z0, the pin hole
    entering at the O.D. top (model +Y) and running down model -Y."""
    f = features["features"]
    outer, hole = f["outer"], f[HOLE]
    if outer["axis"] != [0.0, 0.0, 1.0] or outer["at"] != [0.0, 0.0, 0.0]:
        raise ValueError("outer: expected the model Z axis through the origin")
    if f["datum_end"]["plane"] != {"frame": "model", "axis": "z", "value": 0.0}:
        raise ValueError("datum_end: expected at model Z0")
    radius = outer["nominal_dia"] / 2
    if hole["station_from"] != "datum_end" or "thru" not in hole["requirements"]:
        raise ValueError(
            f"{HOLE}: expected a through hole stationed from the datum end"
        )
    if hole["axis"] != [0.0, -1.0, 0.0] or hole["at"][0] != 0.0:
        raise ValueError(f"{HOLE}: expected a cross hole down model -Y, on the axis")
    if not math.isclose(hole["at"][1], radius, abs_tol=1e-6):
        raise ValueError(f"{HOLE}: expected to enter at the O.D. top")
    if not math.isclose(hole["at"][2], hole["station_nominal"], abs_tol=1e-6):
        raise ValueError(f"{HOLE}: 'at' is not its station from the datum end")
    return {
        "length": f["far_end"]["length_nominal"],
        "od": outer["nominal_dia"],
        "bore": f["bore"]["nominal_dia"],
        "station": hole["station_nominal"],
        "station_max": hole["station"][1],
        "dia": hole["dia"],
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    od = g["od"]
    radius = od / 2
    bar = p["bar_dia_mm"]
    if not math.isclose(bar, p["bar_dia_in"] * IN, abs_tol=1e-6):
        raise ValueError("process.bar_dia_mm is not process.bar_dia_in")
    if od >= bar:
        raise ValueError("the turned O.D. is not under the bar")
    turned = p["turn_length_in"] * IN
    overhang = p["end_overhang_mm"]
    # The collar and the blade's width past it lie inside the turned length.
    if turned < g["length"] + p["blade_width_in"] * IN:
        raise ValueError("the turned length does not cover the collar and the blade")

    d16 = _shop_tool(plan, shop, "drill-1-16")["diameter_mm"]
    if not g["dia"][0] <= d16 <= g["dia"][1]:
        raise ValueError(f"1/16 Ø{d16} is outside the pin hole's band {g['dia']}")
    if not math.isclose(_cut(plan, "pin drill", "cutter_dia_mm"), d16, abs_tol=1e-3):
        raise ValueError("'pin drill' cutter_dia_mm is not the 1/16's")
    _agree(plan, "drill_1_16_dia_mm", d16)

    # The blank on one parallel on edge: the jaws grip the bar, its axis the
    # bar's radius above the parallel; Z0 is the turned O.D.'s top, on the
    # same axis. The parallel narrower than the bar, so the jaws close on it.
    jaw_top = p["vise_jaw_height_mm"] - p["riser_height_mm"] - bar / 2 - radius
    _agree(plan, "jaw_top_over_od_mm", jaw_top)
    if p["vise_jaw_height_mm"] - p["riser_height_mm"] < bar / 2:
        raise ValueError(
            "the bar's axis stands above the jaw tops: the jaws would not grip it"
        )
    if p["parallel_thickness_mm"] >= bar:
        raise ValueError(
            "the parallel is as wide as the bar: the jaws would close on it"
        )
    if turned >= p["blank_length_mm"] - overhang:
        raise ValueError("the turned end reaches past the jaws' grip on the bar")
    parallel_top = -(radius + bar / 2)

    spot_dia = p["spot_dia_mm"]
    if not math.isclose(
        _cut(plan, "pin spot", "cutter_dia_mm"), spot_dia, abs_tol=1e-6
    ):
        raise ValueError("'pin spot' cutter_dia_mm is not process.spot_dia_mm")
    if not d16 < spot_dia <= CENTRE_DRILL["body_mm"]:
        raise ValueError("the spot is not between the 1/16 and the centre drill's body")
    spot_depth = _spot_depth(spot_dia)
    tip = -(od + p["pin_drill_past_mm"] + _point(d16))
    _agree(plan, "pin_tip_height_mm", tip - parallel_top)
    peck = p["pin_peck_mm"]
    op = _op_with_cut(plan, "pin drill")[0]
    if op["peck"] != {"step_mm": "{{process.pin_peck_mm}}", "retract": "full"}:
        raise ValueError(
            "'pin drill' peck is not process.pin_peck_mm with full retract"
        )
    if peck > d16:
        raise ValueError("process.pin_peck_mm is over one 1/16 diameter")
    # The drill runs through the bore between the walls: the walls are the
    # O.D. less the bore, so it cuts twice; the tip ends under the O.D.
    if g["bore"] >= od:
        raise ValueError("the bore leaves no wall")

    # The pin hole drills in the overhang: the centre drill's body and the
    # drill, at the station's far limit, clear the jaws' and the parallel's
    # left side; each tool reaches its depth with the chuck above the jaw tops.
    if g["station_max"] + CENTRE_DRILL["body_mm"] / 2 >= overhang:
        raise ValueError(
            "the pin hole is not in the overhang: the tools reach the jaws"
        )
    if p["spot_projection_min_mm"] < jaw_top + spot_depth + CLEAR_MM:
        raise ValueError("spot_projection_min_mm: the chuck would reach the jaw tops")
    if p["drill_projection_min_mm"] < jaw_top - tip + CLEAR_MM:
        raise ValueError("drill_projection_min_mm: the chuck would reach the jaw tops")
    for key, oal in (("spot", "centre_drill_oal_mm"), ("drill", "drill_1_16_oal_mm")):
        if p[f"{key}_projection_min_mm"] >= p[oal]:
            raise ValueError(f"{key}_projection_min_mm: longer than the tool")

    speeds = {name: _speed(plan, name) for name in ("pin spot", "pin drill")}
    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frame (model point -> axes · (p - origin)): X along the blank from the
    # datum end (model +Z), Z up the pin hole's axis (model +Y), Y = Z × X
    # (model +X); origin the O.D. top over the datum end's centre.
    frame = _frame([0.0, radius, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
    x, y, z = _to(frame, [0.0, radius, g["station"]])
    if not (
        math.isclose(x, g["station"], abs_tol=1e-6)
        and math.isclose(y, 0.0, abs_tol=1e-9)
        and math.isclose(z, 0.0, abs_tol=1e-9)
    ):
        raise ValueError(
            "the frame does not put the pin hole on the axis at the O.D. top"
        )
    hole = [_r(x), _r(y)]
    stock = ((0.0, g["length"]), (-radius, radius), (-od, 0.0))
    clear = jaw_top + CLEAR_MM

    jobs = [
        {
            "tool": "spot",
            "dia": CENTRE_DRILL["body_mm"],
            "shape": "drill",
            "tip_angle": CENTRE_DRILL["point_deg"],
            "rpm": speeds["pin spot"][0],
            "feed": speeds["pin spot"][1],
            "plunge": speeds["pin spot"][1],
            "label": "pin spot",
            "ops": [["pin_spot", "spot the pin hole", _spot(hole, -spot_depth, clear)]],
        },
        {
            "tool": "drill-1-16",
            "dia": d16,
            "shape": "drill",
            "tip_angle": DRILL_POINT_DEG,
            "rpm": speeds["pin drill"][0],
            "feed": speeds["pin drill"][1],
            "plunge": speeds["pin drill"][1],
            "label": "pin drill",
            "ops": [
                [
                    "pin_drill",
                    "peck the 1/16 pin hole through",
                    _pecked(hole, tip, peck, clear),
                ]
            ],
        },
    ]

    # Keep-outs: the jaws from the overhang on (to their tops), the 4 in
    # parallel under the blank from the jaws' left face (to its top, the
    # bar's underside), the spacer on the parallel's right end (to the bar's
    # top, above Z0 by the bar's and the turned radii's difference).
    jaw_x = (overhang, overhang + p["vise_jaw_width_mm"])
    parallel_x = (overhang, overhang + p["parallel_length_mm"])
    half = p["parallel_thickness_mm"] / 2
    bar_top = bar / 2 - radius
    boxes = [
        _box("moving jaw", jaw_x, (-bar / 2 - JAW_DEPTH_MM, -bar / 2), jaw_top),
        _box("fixed jaw", jaw_x, (bar / 2, bar / 2 + JAW_DEPTH_MM), jaw_top),
        _box("parallel", parallel_x, (-half, half), parallel_top),
        _box(
            "blank's bar end",
            (turned, p["blank_length_mm"]),
            (-bar / 2, bar / 2),
            bar_top,
        ),
        _box(
            "spacer",
            (parallel_x[1] - SPACER_MM, parallel_x[1]),
            (-bar / 2, bar / 2),
            bar_top,
        ),
    ]
    name = PROGRAMS[0][0]
    tn = numbers

    def hole_checks(bottom: float, cutter: float) -> list[list[Any]]:
        return [
            ["holes", {"centres": [hole], "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": 0.0, "open_holes": [hole]}],
            ["vertical_below_top", {"z_top": 0.0}],
            ["air_feed", {"z_top": 0.0}],
            ["keep_out", {"radius": cutter / 2, "boxes": boxes}],
        ]

    expect: list[list[Any]] = [
        [
            name,
            "tool_changes",
            {
                "z_top": jaw_top,
                "tools": [tn["spot"], tn["drill-1-16"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[speeds["pin spot"][0]], [speeds["pin drill"][0]]]}],
        [name, "pauses", {"z_top": jaw_top, "count": 0}],
        [name, "depth", {"z_min": _r(tip)}],
    ]
    for k, checks in enumerate(
        (hole_checks(-spot_depth, CENTRE_DRILL["body_mm"]), hole_checks(tip, d16))
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": {"pin_hole": frame},
        "stock": stock,
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
    frame = ctx["frames"]["pin_hole"]
    model = rt.import_step(doc, "Collar", ctx["step"], frame["origin"], frame["axes"])
    ops: dict[str, Any] = {}
    for section in ctx["jobs"]:
        target = rt.job(doc, section["label"], [model], ctx["stock"])
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
