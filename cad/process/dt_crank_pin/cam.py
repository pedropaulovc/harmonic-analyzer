"""FreeCAD CAM recipe for MHA-DT-09, the crank pin: its #45 keeper-ring hole.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The pin's length, big
and small ends, the hole's diameter band, its station from the big end and
its axis come from the feature export; the parallel, the overhang, the spot,
the pecks and the drill's run past the pin from ``plan.toml``
``[parameters]`` and ``milling_cuts``; the #45's diameter from ``shop/``.
Every path is written here (``rt.custom``). Typed here, because neither
record carries them: the #1 centre drill's catalogue geometry (it sets the
spot depth), the twist drill's 118° point, the safe and clearance heights and
the vise jaws' depth (keep-out shapes only).

Route (``plan.toml``): the pin is bought (McMaster 98390A254, No. 3 taper
pin); on the mill it lies along the vise jaws on one 1 in parallel standing
on edge, the big end .25 in out past the jaws' left side, a second pin of the
pack on the parallel's right end. DP01 spots the hole with the #1 centre
drill and pecks the #45 through, in the overhang, into air.

Work frame (G54): X0 the big end's rim plane, +X along the pin toward the
small end; Y0 the pin's axis, +Y toward the fixed jaw; Z0 the top of the pin
over the hole's station.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_crank_pin"
COMMENT = "MHA-DT-09 crank pin"
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("DP01_ring_hole", (("hole_spot",), ("hole_drill",))),
)
# The program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = ("DP01_ring_hole",)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the files are not).
CAM_TOOLS = ("spot", "drill-45")
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
# Drill R planes start this far above the pin's top: real G0 brings the tool
# down to it, beside the jaws.
SAFE_MM = 1.0
# Moves to and from the hole run this far above the jaw tops; each tool
# projects at least the jaw tops plus its depth plus this from the chuck.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped pin; the spacer
# (a second pin of the pack) on the 4 in parallel's right end.
JAW_DEPTH_MM = IN
SPACER_MM = 1.75 * IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
HOLE = "ring_hole"


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


def _speed(plan: dict[str, Any], shop: dict[str, Any], cut: str) -> tuple[float, float]:
    """(rpm, mm/min) the plan authors on the cut, agreeing with the rpm of the
    shop setting its operation names (the setting's feed is printed text)."""
    op, _record = _op_with_cut(plan, cut)
    rpm, feed = _cut(plan, cut, "rpm"), _cut(plan, cut, "feed_mm_min")
    if float(shop["settings"][op["settings"]]["rpm"]) != rpm:
        raise ValueError(f"'{cut}': its setting's rpm is not the cut's {rpm:g}")
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
    """Depth below the pin's top at which the #1 centre drill's 60° countersink
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
    """Drill from the pin's top to ``tip`` in pecks of ``peck``, each with a
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
    """The pin and its hole from the export, in the model frame: the pin's
    axis along model X from the big end's rim plane at X0, the hole along
    model Z entering at the pin's top."""
    f = features["features"]
    taper, hole = f["taper"], f[HOLE]
    if taper["axis"] != [1.0, 0.0, 0.0] or taper["at"] != [0.0, 0.0, 0.0]:
        raise ValueError("taper: expected the model X axis from the origin")
    if f["big_end"]["plane"] != {"frame": "model", "axis": "x", "value": 0.0}:
        raise ValueError("big_end: expected the model X0 plane")
    length = taper["length_ref"]
    if not math.isclose(f["small_end"]["plane"]["value"], length, abs_tol=1e-6):
        raise ValueError("small_end: not at the pin's length from the big end")
    if hole["station_from"] != "big_end" or "thru" not in hole["requirements"]:
        raise ValueError(f"{HOLE}: expected a through hole stationed from the big end")
    if hole["axis"] != [0.0, 0.0, -1.0] or hole["at"][1] != 0.0:
        raise ValueError(f"{HOLE}: expected a cross hole down model Z, on the axis")
    big, small = taper["dia_ref"], taper["small_dia_ref"]
    station = hole["at"][0]
    if not math.isclose(station, hole["station_nominal"], abs_tol=1e-6):
        raise ValueError(f"{HOLE}: 'at' is not its station from the big end")
    dia_at_hole = big - (big - small) * station / length
    if not math.isclose(hole["at"][2], dia_at_hole / 2, abs_tol=1e-6):
        raise ValueError(f"{HOLE}: 'at' is not on the pin's top at its station")
    return {
        "length": length,
        "big": big,
        "small": small,
        "station": station,
        "station_max": hole["station"][1],
        "dia": hole["dia"],
        "dia_at_hole": dia_at_hole,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    length, big = g["length"], g["big"]
    dia = g["dia_at_hole"]
    radius = dia / 2

    d45 = _shop_tool(plan, shop, "drill-45")["diameter_mm"]
    if not g["dia"][0] <= d45 <= g["dia"][1]:
        raise ValueError(f"#45 Ø{d45} is outside the hole's band {g['dia']}")
    if not math.isclose(_cut(plan, "hole drill", "cutter_dia_mm"), d45, abs_tol=1e-3):
        raise ValueError("'hole drill' cutter_dia_mm is not the #45's")

    # The pin on one parallel on edge: the jaw tops above Z0 (the pin's top
    # at the hole) by the jaw height less the parallel and the pin's diameter
    # there; the parallel narrower than the pin's small end, so the jaws close
    # on the pin.
    jaw_top = p["vise_jaw_height_mm"] - p["riser_height_mm"] - dia
    _agree(plan, "jaw_top_over_pin_mm", jaw_top)
    if jaw_top < 0:
        raise ValueError(
            "the pin stands above the jaw tops: the jaws would not grip it"
        )
    if p["parallel_thickness_mm"] >= g["small"]:
        raise ValueError(
            "the parallel is as wide as the pin: the jaws would close on it"
        )
    overhang = p["big_end_overhang_mm"]
    if overhang >= length:
        raise ValueError("the big end's overhang leaves nothing in the jaws")

    spot_dia = p["spot_dia_mm"]
    if not math.isclose(
        _cut(plan, "hole spot", "cutter_dia_mm"), spot_dia, abs_tol=1e-6
    ):
        raise ValueError("'hole spot' cutter_dia_mm is not process.spot_dia_mm")
    if not d45 < spot_dia <= CENTRE_DRILL["body_mm"]:
        raise ValueError("the spot is not between the #45 and the centre drill's body")
    spot_depth = _spot_depth(spot_dia)
    tip = -(dia + p["hole_drill_past_mm"] + _point(d45))
    _agree(plan, "hole_tip_height_mm", dia + tip)
    peck = p["hole_peck_mm"]
    op = _op_with_cut(plan, "hole drill")[0]
    if op["peck"] != {"step_mm": "{{process.hole_peck_mm}}", "retract": "full"}:
        raise ValueError(
            "'hole drill' peck is not process.hole_peck_mm with full retract"
        )
    if peck > d45:
        raise ValueError("process.hole_peck_mm is over one #45 diameter")

    # The hole drills in the overhang: the centre drill's body and the drill,
    # at the station's far limit, clear the jaws' and the parallel's left
    # side; each tool reaches its depth with the drill chuck above the jaw tops.
    if g["station_max"] + CENTRE_DRILL["body_mm"] / 2 >= overhang:
        raise ValueError("the hole is not in the overhang: the tools reach the jaws")
    if p["spot_projection_min_mm"] < jaw_top + spot_depth + CLEAR_MM:
        raise ValueError("spot_projection_min_mm: the chuck would reach the jaw tops")
    if p["drill_45_projection_min_mm"] < jaw_top - tip + CLEAR_MM:
        raise ValueError(
            "drill_45_projection_min_mm: the chuck would reach the jaw tops"
        )
    for key, oal in (("spot", "centre_drill_oal_mm"), ("drill_45", "drill_45_oal_mm")):
        if p[f"{key}_projection_min_mm"] >= p[oal]:
            raise ValueError(f"{key}_projection_min_mm: longer than the tool")

    speeds = {name: _speed(plan, shop, name) for name in ("hole spot", "hole drill")}
    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frame (model point -> axes · (p - origin)): X along the pin from the
    # big end (model +X), Z up the hole's axis (model +Z), origin the pin's
    # top over its axis in the big end's plane at the hole's radius.
    frame = _frame([0.0, 0.0, radius], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])
    x, y, z = _to(frame, [g["station"], 0.0, radius])
    if not (
        math.isclose(x, g["station"], abs_tol=1e-6)
        and math.isclose(y, 0.0, abs_tol=1e-9)
        and math.isclose(z, 0.0, abs_tol=1e-9)
    ):
        raise ValueError("the frame does not put the hole on the axis at the pin's top")
    hole = [_r(x), _r(y)]
    half_big = big / 2
    stock = (
        (0.0, length),
        (-half_big, half_big),
        (-radius - half_big, half_big - radius),
    )
    clear = jaw_top + CLEAR_MM

    jobs = [
        {
            "tool": "spot",
            "dia": CENTRE_DRILL["body_mm"],
            "shape": "drill",
            "tip_angle": CENTRE_DRILL["point_deg"],
            "rpm": speeds["hole spot"][0],
            "feed": speeds["hole spot"][1],
            "plunge": speeds["hole spot"][1],
            "label": "hole spot",
            "ops": [
                ["hole_spot", "spot the ring hole", _spot(hole, -spot_depth, clear)]
            ],
        },
        {
            "tool": "drill-45",
            "dia": d45,
            "shape": "drill",
            "tip_angle": DRILL_POINT_DEG,
            "rpm": speeds["hole drill"][0],
            "feed": speeds["hole drill"][1],
            "plunge": speeds["hole drill"][1],
            "label": "hole drill",
            "ops": [
                [
                    "hole_drill",
                    "peck the #45 ring hole through",
                    _pecked(hole, tip, peck, clear),
                ]
            ],
        },
    ]

    # Keep-outs: the jaws from the overhang on (to their tops), the 4 in
    # parallel under the pin from the jaws' left face (to its top, the pin's
    # underside at the hole), the spacer pin on the parallel's right end.
    jaw_x = (overhang, overhang + p["vise_jaw_width_mm"])
    parallel_x = (overhang, overhang + p["parallel_length_mm"])
    half = p["parallel_thickness_mm"] / 2
    boxes = [
        _box("moving jaw", jaw_x, (-half_big - JAW_DEPTH_MM, -half_big), jaw_top),
        _box("fixed jaw", jaw_x, (half_big, half_big + JAW_DEPTH_MM), jaw_top),
        _box("parallel", parallel_x, (-half, half), -dia),
        _box(
            "spacer",
            (parallel_x[1] - SPACER_MM, parallel_x[1]),
            (-half_big, half_big),
            half_big - radius,
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
                "tools": [tn["spot"], tn["drill-45"]],
                "loads_first": True,
            },
        ],
        [
            name,
            "spindle",
            {"rpm": [[speeds["hole spot"][0]], [speeds["hole drill"][0]]]},
        ],
        [name, "pauses", {"z_top": jaw_top, "count": 0}],
        [name, "depth", {"z_min": _r(tip)}],
    ]
    for k, checks in enumerate(
        (hole_checks(-spot_depth, CENTRE_DRILL["body_mm"]), hole_checks(tip, d45))
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": {"hole": frame},
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
    frame = ctx["frames"]["hole"]
    model = rt.import_step(doc, "Pin", ctx["step"], frame["origin"], frame["axes"])
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
