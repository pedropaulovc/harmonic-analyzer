"""FreeCAD CAM recipe for MHA-DT-22, the integral pinion arbor: its .2510
reamed cross hole through the head and its 1/16 pin hole through the shaft.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The head's and the
shaft's diameters, both holes' stations from the head's rear face and their
diameter bands come from the feature export; the bar, the parallel, the
overhang, the spots, the pecks and each tool's run past the work from
``plan.toml`` ``[parameters]`` and ``milling_cuts``; the C drill's, the
reamer's and the 1/16's diameters from ``shop/``. Every path is written here
(``rt.custom``). Typed here, because no record carries them: the #2 centre
drill's catalogue geometry (it sets the spot depths), the twist drills' 118°
point, the safe and clearance heights and the vise jaws' depth (keep-out
shapes only).

Route (``plan.toml``): both ends are faced, the blank otherwise still 5/8
bar its whole length (its full section keeps the overhang stiff under the
drill thrust). On the mill the blank lies along the vise jaws on one 1 in
parallel standing on edge, the faced head end out past the jaws' left face,
both holes in the overhang, drilled into air. PA01 spots the cross hole on
the bar's top, drills it C and reams it .2510 through the bar; PA02 spots
the pin hole with the centre drill's pilot point and pecks the 1/16 through
the bar. The holes stay through when the head is turned to Ø.59 and the
shaft to Ø.3125 afterwards.

Work frame (G54): X0 the faced head end (the crown's apex), +X toward the
back end; Y0 the bar's axis; Z0 the top of the 5/8 bar.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_pinion_arbor"
COMMENT = "MHA-DT-22 integral pinion arbor"
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("PA01_cross_hole", (("cross_spot",), ("cross_drill",), ("cross_ream",))),
    ("PA02_pin_hole", (("pin_spot",), ("pin_drill",))),
)
# Each program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = ("PA01_cross_hole", "PA02_pin_hole")
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the lathe tools, the gauges and the files are not).
CAM_TOOLS = ("spot", "drill-c", "reamer", "drill-1-16")
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included, its pilot ground with
# a 118° point (as the dt_pinion_cam recipe): the shop record names the tool,
# not its geometry.
CENTRE_DRILL = {
    "body_mm": 3 / 16 * IN,
    "pilot_mm": 5 / 64 * IN,
    "pilot_length_mm": 5 / 64 * IN,
    "point_deg": 60.0,
    "pilot_point_deg": 118.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# Drill R planes start this far above the bar's top: real G0 brings the tool
# down to it, beside the jaws.
SAFE_MM = 1.0
# Moves to and from the holes run this far above the jaw tops.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped bar.
JAW_DEPTH_MM = IN
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


def _countersink_depth(dia: float) -> float:
    """Depth below the surface at which the #2 centre drill's 60° countersink
    reaches ``dia``; refused unless it is between the pilot and the body."""
    pilot, body = CENTRE_DRILL["pilot_mm"], CENTRE_DRILL["body_mm"]
    if not pilot < dia <= body:
        raise ValueError(
            f"spot Ø{dia:.3f} is not between the pilot Ø{pilot:.3f} and the body Ø{body:.3f}"
        )
    half = math.radians(CENTRE_DRILL["point_deg"] / 2)
    return CENTRE_DRILL["pilot_length_mm"] + (dia - pilot) / 2 / math.tan(half)


def _pilot_depth(dia: float) -> float:
    """Depth at which the centre drill's pilot point alone reaches ``dia``;
    refused unless it is under the pilot."""
    if not 0 < dia < CENTRE_DRILL["pilot_mm"]:
        raise ValueError(f"spot Ø{dia:.3f} is not under the pilot")
    return dia / 2 / math.tan(math.radians(CENTRE_DRILL["pilot_point_deg"] / 2))


def _point(dia: float) -> float:
    """A twist drill's point length."""
    return dia / 2 / math.tan(math.radians(DRILL_POINT_DEG / 2))


def _plunge(
    xy: list[float], z: float, clear: float, feed_out: bool = False
) -> list[str]:
    """One feed to ``z`` from the R plane; out by rapid, or (a reamer) by
    feed to the bar's top first."""
    clear, r_plane = _r(clear), _r(SAFE_MM)
    out = ["G1 Z0.000 F{feed}"] if feed_out else []
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        *out,
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _pecked(xy: list[float], tip: float, peck: float, clear: float) -> list[str]:
    """Drill from the bar's top to ``tip`` in pecks of ``peck``, each with a
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
    """The arbor and its two holes from the export, in the model frame: the
    turning axis along model Z, the head's rear face at a model Z plane facing
    +Z, both holes entering on model -Y and running up model +Y."""
    f = features["features"]
    rear = f["head_rear"]["plane"]
    if rear["axis"] != "z" or f["head_rear"]["outward"] != [0.0, 0.0, 1.0]:
        raise ValueError("head_rear: expected a model Z plane facing +Z")
    rear_z = rear["value"]
    for name in ("head", "neck"):
        if f[name]["at"] != [0.0, 0.0, rear_z]:
            raise ValueError(f"{name}: expected to start at the head's rear face")
    if f["head"]["axis"] != [0.0, 0.0, -1.0] or f["neck"]["axis"] != [0.0, 0.0, 1.0]:
        raise ValueError("head, neck: expected along model -Z and +Z")
    holes = {}
    for name, radius in (
        ("cross_hole", f["head"]["nominal_dia"] / 2),
        ("pin_hole", f["shaft"]["nominal_dia"] / 2),
    ):
        hole = f[name]
        if hole["station_from"] != "head_rear" or "thru" not in hole["requirements"]:
            raise ValueError(
                f"{name}: expected a through hole stationed from head_rear"
            )
        if hole["axis"] != [0.0, 1.0, 0.0] or hole["at"][0] != 0.0:
            raise ValueError(f"{name}: expected a cross hole up model +Y, on the axis")
        if not math.isclose(hole["at"][1], -radius, abs_tol=1e-6):
            raise ValueError(f"{name}: expected to enter on its diameter's -Y side")
        station = abs(hole["at"][2] - rear_z)
        if not math.isclose(station, hole["station_nominal"], abs_tol=1e-6):
            raise ValueError(
                f"{name}: 'at' is not its station from the head's rear face"
            )
        holes[name] = {
            "at": hole["at"],
            "station": hole["station_nominal"],
            "station_max": hole["station"][1],
            "dia": hole["dia"],
        }
    if not f["cross_hole"]["at"][2] < rear_z < f["pin_hole"]["at"][2]:
        raise ValueError(
            "expected the cross hole in the head and the pin hole in the shaft"
        )
    return {
        "rear_z": rear_z,
        "head": f["head"]["nominal_dia"],
        "crown_apex": f["head_crown"]["center"][2] - f["head_crown"]["radius_nominal"],
        "holes": holes,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    bar = p["bar_dia_mm"]
    if not math.isclose(bar, p["bar_dia_in"] * IN, abs_tol=1e-6):
        raise ValueError("process.bar_dia_mm is not process.bar_dia_in")
    if g["head"] >= bar:
        raise ValueError("the head is not under the bar")
    radius = bar / 2
    # X0 is the faced head end (the crown's apex): the head is not yet turned,
    # the blank is 5/8 bar its whole length.
    apex_z = g["crown_apex"]
    _agree(plan, "left_overhang_mm", p["jaw_left_x_mm"])
    overhang = p["jaw_left_x_mm"]

    tools = {
        key: _shop_tool(plan, shop, key)["diameter_mm"]
        for key in ("drill-c", "reamer", "drill-1-16")
    }
    cross, pin = g["holes"]["cross_hole"], g["holes"]["pin_hole"]
    if not cross["dia"][0] <= tools["reamer"] <= cross["dia"][1]:
        raise ValueError(f"reamer Ø{tools['reamer']} is outside the cross hole's band")
    if not tools["drill-c"] < tools["reamer"]:
        raise ValueError("the C drill does not leave stock for the reamer")
    if not pin["dia"][0] <= tools["drill-1-16"] <= pin["dia"][1]:
        raise ValueError(f"1/16 Ø{tools['drill-1-16']} is outside the pin hole's band")
    for cut, key in (
        ("cross drill", "drill-c"),
        ("cross ream", "reamer"),
        ("pin drill", "drill-1-16"),
    ):
        if not math.isclose(_cut(plan, cut, "cutter_dia_mm"), tools[key], abs_tol=1e-3):
            raise ValueError(f"'{cut}' cutter_dia_mm is not the {key}'s")
    _agree(plan, "drill_1_16_dia_mm", tools["drill-1-16"])

    # The blank on one parallel on edge: the jaws grip the bar, its axis the
    # bar's radius above the parallel; Z0 the bar's top. The parallel narrower
    # than the bar, so the jaws close on the bar.
    jaw_top = p["vise_jaw_height_mm"] - p["riser_height_mm"] - bar
    _agree(plan, "jaw_top_over_bar_mm", jaw_top)
    if p["vise_jaw_height_mm"] - p["riser_height_mm"] < radius:
        raise ValueError(
            "the bar's axis stands above the jaw tops: the jaws would not grip it"
        )
    if p["parallel_thickness_mm"] >= bar:
        raise ValueError(
            "the parallel is as wide as the bar: the jaws would close on it"
        )
    parallel_top = -bar

    # Spots: the cross hole's on the head's top with the countersink; the pin
    # hole's on the bar's top with the pilot's point only (its countersink
    # would open the finished Ø.3125's hole past the 1/16).
    cross_spot = p["cross_spot_dia_mm"]
    pin_spot = p["pin_spot_dia_mm"]
    for cut, dia in (("cross spot", cross_spot), ("pin spot", pin_spot)):
        if not math.isclose(_cut(plan, cut, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{cut}' cutter_dia_mm is not its plan spot diameter")
    if not cross_spot < tools["drill-c"]:
        raise ValueError(
            "the cross spot is not under the C drill: its point would not centre"
        )
    if not tools["drill-1-16"] <= pin_spot:
        raise ValueError("the pin spot is under the 1/16")
    cross_spot_z = -_countersink_depth(cross_spot)
    pin_spot_z = -_pilot_depth(pin_spot)

    # Tips: each drill's full diameter past the bar's underside; the reamer
    # past it by its lead.
    drill_tip = -(bar + p["drill_past_mm"] + _point(tools["drill-c"]))
    ream_tip = -(bar + p["ream_past_mm"])
    import cam_nc

    if p["ream_past_mm"] <= cam_nc.ream_full_diameter_past_min_mm(plan, "reamer"):
        raise ValueError(
            "the reamer's full diameter does not reach the bar's underside (cnc.ream-full-diameter)"
        )
    # The cross hole is in the overhang: the reamer's flat end runs out in air.
    cam_nc.ream_end_face_clear(
        "reamer", ream_tip, -(bar + p["drill_past_mm"]), -bar, -math.inf
    )
    pin_tip = -(bar + p["pin_drill_past_mm"] + _point(tools["drill-1-16"]))
    _agree(plan, "cross_drill_tip_mm", drill_tip)
    _agree(plan, "cross_ream_tip_mm", ream_tip)
    _agree(plan, "pin_drill_tip_mm", pin_tip)
    if _op_with_cut(plan, "cross drill")[0]["peck"] != "none":
        raise ValueError(
            "'cross drill' is authored with pecks; the recipe drills one feed"
        )
    peck = p["pin_peck_mm"]
    op = _op_with_cut(plan, "pin drill")[0]
    if op["peck"] != {"step_mm": "{{process.pin_peck_mm}}", "retract": "full"}:
        raise ValueError(
            "'pin drill' peck is not process.pin_peck_mm with full retract"
        )
    if peck > tools["drill-1-16"]:
        raise ValueError("process.pin_peck_mm is over one 1/16 diameter")

    # Each hole in its own clamping's overhang: each tool's widest part at the
    # station's far limit clears the jaws' and the parallel's left face; each
    # chuck stays above the jaw tops beside the hole.
    cross_overhang = p["cross_jaw_left_mm"]
    offset = g["rear_z"] - g["crown_apex"]
    cross_far = offset - (2 * cross["station"] - cross["station_max"])
    if cross_far + CENTRE_DRILL["body_mm"] / 2 >= cross_overhang:
        raise ValueError(
            "the cross hole is not in the overhang: the tools reach the jaws"
        )
    if p["cross_projection_min_mm"] < jaw_top - drill_tip + CLEAR_MM:
        raise ValueError("cross_projection_min_mm: the chuck would reach the jaw tops")
    pin_far = offset + pin["station_max"]
    if pin_far + CENTRE_DRILL["body_mm"] / 2 >= overhang:
        raise ValueError(
            "the pin hole is not in the overhang: the tools reach the jaws"
        )
    if p["drill_projection_min_mm"] < jaw_top - pin_tip + CLEAR_MM:
        raise ValueError("drill_projection_min_mm: the chuck would reach the jaw tops")

    speeds = {
        name: _speed(plan, name)
        for name in ("cross spot", "cross drill", "cross ream", "pin spot", "pin drill")
    }
    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frame (model point -> axes · (p - origin)): X along the arbor from the
    # faced head end (model +Z), Z up the holes' entry (model -Y), Y = Z × X
    # (model -X); origin the bar's top over the crown's apex.
    frame = _frame([0.0, -radius, apex_z], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0])
    xy = {}
    for name, key in (("cross_hole", "cross_x_mm"), ("pin_hole", "pin_x_mm")):
        hole = g["holes"][name]
        x, y, _z = _to(frame, hole["at"])
        signed = (
            g["rear_z"]
            - apex_z
            + (hole["station"] if name == "pin_hole" else -hole["station"])
        )
        if not (
            math.isclose(x, signed, abs_tol=1e-6) and math.isclose(y, 0.0, abs_tol=1e-9)
        ):
            raise ValueError(
                f"the frame does not put {name} on the axis at its station"
            )
        _agree(plan, key, x)
        xy[name] = [_r(x), _r(y)]
    stock = ((0.0, p["part_length_mm"]), (-radius, radius), (-bar, 0.0))
    clear = jaw_top + CLEAR_MM

    def job(
        tool, dia, cut, key, label, lines, tip_angle=DRILL_POINT_DEG, shape="drill"
    ):
        return {
            "tool": tool,
            "dia": dia,
            "shape": shape,
            "tip_angle": tip_angle,
            "rpm": speeds[cut][0],
            "feed": speeds[cut][1],
            "plunge": speeds[cut][1],
            "label": cut,
            "ops": [[key, label, lines]],
        }

    jobs = {
        "PA01_cross_hole": [
            job(
                "spot",
                CENTRE_DRILL["body_mm"],
                "cross spot",
                "cross_spot",
                "spot the cross hole",
                _plunge(xy["cross_hole"], cross_spot_z, clear),
                tip_angle=CENTRE_DRILL["point_deg"],
            ),
            job(
                "drill-c",
                tools["drill-c"],
                "cross drill",
                "cross_drill",
                "drill the cross hole C through the bar",
                _plunge(xy["cross_hole"], drill_tip, clear),
            ),
            job(
                "reamer",
                tools["reamer"],
                "cross ream",
                "cross_ream",
                "ream the cross hole .2510 through, fed out",
                _plunge(xy["cross_hole"], ream_tip, clear, feed_out=True),
                tip_angle=None,
                shape="endmill",
            ),
        ],
        "PA02_pin_hole": [
            job(
                "spot",
                CENTRE_DRILL["body_mm"],
                "pin spot",
                "pin_spot",
                "spot the pin hole with the pilot's point",
                _plunge(xy["pin_hole"], pin_spot_z, clear),
                tip_angle=CENTRE_DRILL["point_deg"],
            ),
            job(
                "drill-1-16",
                tools["drill-1-16"],
                "pin drill",
                "pin_drill",
                "peck the 1/16 pin hole through",
                _pecked(xy["pin_hole"], pin_tip, peck, clear),
            ),
        ],
    }

    # Keep-outs, per clamping: the jaws from their left face on (to their
    # tops), the 4 in parallel under the bar from the same face (to its top,
    # the bar's underside).
    half = p["parallel_thickness_mm"] / 2

    def boxes(left: float) -> list[dict[str, Any]]:
        jaw_x = (left, left + p["vise_jaw_width_mm"])
        parallel_x = (left, left + p["parallel_length_mm"])
        return [
            _box("moving jaw", jaw_x, (-radius - JAW_DEPTH_MM, -radius), jaw_top),
            _box("fixed jaw", jaw_x, (radius, radius + JAW_DEPTH_MM), jaw_top),
            _box("parallel", parallel_x, (-half, half), parallel_top),
        ]

    tn = numbers

    def hole_checks(
        hole: list[float], bottom: float, cutter: float, left: float
    ) -> list[list[Any]]:
        return [
            ["holes", {"centres": [hole], "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": 0.0, "open_holes": [hole]}],
            ["vertical_below_top", {"z_top": 0.0}],
            ["air_feed", {"z_top": 0.0}],
            ["keep_out", {"radius": cutter / 2, "boxes": boxes(left)}],
        ]

    expect: list[list[Any]] = []
    for name, tool_ids, sections in (
        (
            "PA01_cross_hole",
            ("spot", "drill-c", "reamer"),
            (
                hole_checks(
                    xy["cross_hole"],
                    cross_spot_z,
                    CENTRE_DRILL["body_mm"],
                    cross_overhang,
                ),
                hole_checks(
                    xy["cross_hole"], drill_tip, tools["drill-c"], cross_overhang
                ),
                hole_checks(
                    xy["cross_hole"], ream_tip, tools["reamer"], cross_overhang
                ),
            ),
        ),
        (
            "PA02_pin_hole",
            ("spot", "drill-1-16"),
            (
                hole_checks(
                    xy["pin_hole"], pin_spot_z, CENTRE_DRILL["body_mm"], overhang
                ),
                hole_checks(xy["pin_hole"], pin_tip, tools["drill-1-16"], overhang),
            ),
        ),
    ):
        cuts = [job_["label"] for job_ in jobs[name]]
        expect += [
            [
                name,
                "tool_changes",
                {
                    "z_top": jaw_top,
                    "tools": [tn[t] for t in tool_ids],
                    "loads_first": True,
                },
            ],
            [name, "spindle", {"rpm": [[speeds[c][0]] for c in cuts]}],
            [name, "pauses", {"z_top": jaw_top, "count": 0}],
            [
                name,
                "depth",
                {
                    "z_min": _r(
                        min(ream_tip, drill_tip) if name.startswith("PA01") else pin_tip
                    )
                },
            ],
        ]
        for k, checks in enumerate(sections):
            expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": {"holes": frame},
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
    frame = ctx["frames"]["holes"]
    model = rt.import_step(doc, "Arbor", ctx["step"], frame["origin"], frame["axes"])
    ops: dict[str, Any] = {}
    for sections in ctx["jobs"].values():
        for section in sections:
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
