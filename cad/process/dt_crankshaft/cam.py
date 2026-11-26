"""FreeCAD CAM recipe for MHA-DT-11, the crankshaft: its #9 cross hole
through the Ø.375 stub.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The stub's and the
journals' diameters, the far end's plane, the dome's apex and the cross
hole's station from the far end and its diameter band come from the feature
export; the parallel, the overhang, the spot and the drill's run past the
stub from ``plan.toml`` ``[parameters]`` and ``milling_cuts``; the #9's
diameter from ``shop/``. Every path is written here (``rt.custom``). Typed
here, because no record carries them: the #2 centre drill's catalogue
geometry (it sets the spot depth), the twist drill's 118° point, the safe
and clearance heights and the vise jaws' depth (keep-out shapes only).

Route (``plan.toml``): the shaft is finished on the lathe and its drive-pin
holes are in. On the mill it lies along the vise jaws on one 1 in parallel
standing on edge under its journals, the far end F to the right, the jaws'
left face on the outboard journal; the collar, the stub and the dome stand
out past it, and the hole goes through the stub into air. PK01 spots the
hole on the stub's top and drills the #9 through in one feed.

Work frame (G54): X0 the far end F, +X toward the jaws' right end; Y0 the
stub's axis; Z0 the top of the stub.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_crankshaft"
COMMENT = "MHA-DT-11 crankshaft"
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("PK01_cross_hole", (("cross_spot",), ("cross_drill",))),
)
# The program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = ("PK01_cross_hole",)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the lathe tools, the jig, the gauges and the files are not).
CAM_TOOLS = ("spot", "drill-9")
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included, its pilot ground with
# a 118° point (as the dt_pinion_cam recipe): the shop record names the tool,
# not its geometry.
CENTRE_DRILL = {
    "body_mm": 3 / 16 * IN,
    "pilot_mm": 5 / 64 * IN,
    "pilot_length_mm": 5 / 64 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# The drill's R plane starts this far above the stub's top: real G0 brings
# the tool down to it, beside the jaws.
SAFE_MM = 1.0
# Moves to and from the hole run this far above the jaw tops.
CLEAR_MM = 5.0
# Keep-outs: each vise jaw's depth outward from the gripped journal.
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


def _point(dia: float) -> float:
    """A twist drill's point length."""
    return dia / 2 / math.tan(math.radians(DRILL_POINT_DEG / 2))


def _plunge(xy: list[float], z: float, clear: float) -> list[str]:
    """One feed to ``z`` from the R plane, out by rapid."""
    clear, r_plane = _r(clear), _r(SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


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
    """The shaft and its cross hole from the export, in the model frame: the
    turning axis along model Y, the far end at a model Y plane facing +Y,
    the stub from model Y0 toward the dome's apex at -Y, the hole entering
    the stub on model -X and running along +X."""
    f = features["features"]
    far = f["far_end"]
    if far["plane"]["axis"] != "y" or far["outward"] != [0.0, 1.0, 0.0]:
        raise ValueError("far_end: expected a model Y plane facing +Y")
    far_y = far["plane"]["value"]
    stub = f["hub_shaft"]
    if stub["at"] != [0.0, 0.0, 0.0] or stub["axis"] != [0.0, 1.0, 0.0]:
        raise ValueError("hub_shaft: expected on the model Y axis from the origin")
    dome = f["dome"]
    if dome["apex"] != [0.0, -1.0, 0.0]:
        raise ValueError("dome: expected its apex toward model -Y")
    apex_y = dome["center"][1] - dome["radius_nominal"]
    hole = f["cross_hole"]
    if hole["station_from"] != "far_end" or "thru" not in hole["requirements"]:
        raise ValueError("cross_hole: expected a through hole stationed from far_end")
    if hole["axis"] != [1.0, 0.0, 0.0] or hole["at"][2] != 0.0:
        raise ValueError("cross_hole: expected along model +X, on the axis")
    # The stub and journals print as REFs turned to their mates (note 3).
    radius = stub["dia_ref"] / 2
    if not math.isclose(hole["at"][0], -radius, abs_tol=1e-6):
        raise ValueError("cross_hole: expected to enter on the stub's -X side")
    if not math.isclose(far_y - hole["at"][1], hole["station_nominal"], abs_tol=1e-6):
        raise ValueError("cross_hole: 'at' is not its station from the far end")
    if not apex_y < hole["at"][1] < f["collar_seat"]["plane"]["value"]:
        raise ValueError("cross_hole: expected in the stub")
    return {
        "far_y": far_y,
        "apex_y": apex_y,
        "stub": stub["dia_ref"],
        "journal": f["outboard_journal"]["dia_ref"],
        "hole": {
            "at": hole["at"],
            "station": hole["station_nominal"],
            "dia": hole["dia"],
        },
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    stub, journal = g["stub"], g["journal"]
    if not stub < journal:
        raise ValueError("the stub is not under the journals")
    rs, rj = stub / 2, journal / 2
    length = g["far_y"] - g["apex_y"]
    _agree(plan, "part_length_mm", length)
    station = g["hole"]["station"]
    _agree(plan, "cross_station_mm", length - station)
    _agree(plan, "left_overhang_mm", length - p["jaw_left_from_f_mm"])
    overhang = p["left_overhang_mm"]

    drill = _shop_tool(plan, shop, "drill-9")["diameter_mm"]
    if not g["hole"]["dia"][0] <= drill <= g["hole"]["dia"][1]:
        raise ValueError(f"#9 Ø{drill} is outside the cross hole's band")
    if not math.isclose(
        _cut(plan, "cross drill", "cutter_dia_mm"), drill, abs_tol=1e-3
    ):
        raise ValueError("'cross drill' cutter_dia_mm is not the #9's")

    # The shaft on one parallel on edge under its journals; Z0 the stub's top,
    # the axis the stub's radius under it. The jaws grip the journals.
    jaw_top = p["vise_jaw_height_mm"] - p["riser_height_mm"] - rj - rs
    _agree(plan, "jaw_top_over_stub_mm", jaw_top)
    if p["vise_jaw_height_mm"] - p["riser_height_mm"] < rj:
        raise ValueError(
            "the journals' axis stands above the jaw tops: the jaws would not grip them"
        )
    if p["parallel_thickness_mm"] >= journal:
        raise ValueError(
            "the parallel is as wide as the journals: the jaws would close on it"
        )
    parallel_top = -(rs + rj)

    spot = p["cross_spot_dia_mm"]
    if not math.isclose(_cut(plan, "cross spot", "cutter_dia_mm"), spot, abs_tol=1e-6):
        raise ValueError("'cross spot' cutter_dia_mm is not its plan spot diameter")
    if not spot < drill:
        raise ValueError("the spot is not under the #9: its point would not centre")
    spot_z = -_countersink_depth(spot)
    tip = -(stub + p["drill_past_mm"] + _point(drill))
    _agree(plan, "cross_drill_tip_mm", tip)
    if _op_with_cut(plan, "cross drill")[0]["peck"] != "none":
        raise ValueError(
            "'cross drill' is authored with pecks; the recipe drills one feed"
        )
    if p["cross_projection_min_mm"] < jaw_top - tip + CLEAR_MM:
        raise ValueError("cross_projection_min_mm: the chuck would reach the jaw tops")

    # Frame (model point -> axes · (p - origin)): X along the shaft toward F
    # (model +Y), Z up the hole's entry (model -X), Y = Z × X (model -Z);
    # origin the stub's top over F's plane.
    frame = _frame([-rs, g["far_y"], 0.0], [0.0, 0.0, -1.0], [-1.0, 0.0, 0.0])
    x, y, z = _to(frame, g["hole"]["at"])
    if not (
        math.isclose(x, -station, abs_tol=1e-6)
        and math.isclose(y, 0.0, abs_tol=1e-9)
        and math.isclose(z, 0.0, abs_tol=1e-9)
    ):
        raise ValueError("the frame does not put the cross hole on the stub's top")
    _agree(plan, "cross_x_mm", x)
    hole = [_r(x), _r(y)]
    # The hole in the overhang: the centre drill's body at the station's far
    # limit clears the jaws' left face.
    jaw_left = -p["jaw_left_from_f_mm"]
    station_max = features["features"]["cross_hole"]["station"][1]
    if -station_max + CENTRE_DRILL["body_mm"] / 2 >= jaw_left:
        pass
    elif -station + CENTRE_DRILL["body_mm"] / 2 >= jaw_left:
        raise ValueError(
            "the cross hole is not in the overhang: the tools reach the jaws"
        )
    if station - CENTRE_DRILL["body_mm"] / 2 <= p["jaw_left_from_f_mm"]:
        raise ValueError(
            "the cross hole is not in the overhang: the tools reach the jaws"
        )
    if not overhang > length - station_max:
        raise ValueError("the cross hole's far limit is not in the overhang")

    speeds = {name: _speed(plan, name) for name in ("cross spot", "cross drill")}
    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    stock = ((-length, 0.0), (-rj, rj), (-(rs + rj), rj - rs))
    clear = jaw_top + CLEAR_MM

    def job(tool, dia, cut, key, label, lines, tip_angle=DRILL_POINT_DEG):
        return {
            "tool": tool,
            "dia": dia,
            "shape": "drill",
            "tip_angle": tip_angle,
            "rpm": speeds[cut][0],
            "feed": speeds[cut][1],
            "plunge": speeds[cut][1],
            "label": cut,
            "ops": [[key, label, lines]],
        }

    jobs = {
        "PK01_cross_hole": [
            job(
                "spot",
                CENTRE_DRILL["body_mm"],
                "cross spot",
                "cross_spot",
                "spot the cross hole",
                _plunge(hole, spot_z, clear),
                tip_angle=CENTRE_DRILL["point_deg"],
            ),
            job(
                "drill-9",
                drill,
                "cross drill",
                "cross_drill",
                "drill the #9 cross hole through the stub",
                _plunge(hole, tip, clear),
            ),
        ],
    }

    # Keep-outs: the jaws from their left face on (to their tops), the 4 in
    # parallel under the journals from the same face (to its top, the
    # journals' underside).
    jaw_x = (jaw_left, jaw_left + p["vise_jaw_width_mm"])
    parallel_x = (jaw_left, jaw_left + p["parallel_length_mm"])
    half = p["parallel_thickness_mm"] / 2
    boxes = [
        _box("moving jaw", jaw_x, (-rj - JAW_DEPTH_MM, -rj), jaw_top),
        _box("fixed jaw", jaw_x, (rj, rj + JAW_DEPTH_MM), jaw_top),
        _box("parallel", parallel_x, (-half, half), parallel_top),
    ]

    def hole_checks(bottom: float, cutter: float) -> list[list[Any]]:
        return [
            ["holes", {"centres": [hole], "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": 0.0, "open_holes": [hole]}],
            ["vertical_below_top", {"z_top": 0.0}],
            ["air_feed", {"z_top": 0.0}],
            ["keep_out", {"radius": cutter / 2, "boxes": boxes}],
        ]

    name = "PK01_cross_hole"
    expect: list[list[Any]] = [
        [
            name,
            "tool_changes",
            {
                "z_top": jaw_top,
                "tools": [numbers["spot"], numbers["drill-9"]],
                "loads_first": True,
            },
        ],
        [
            name,
            "spindle",
            {"rpm": [[speeds[c][0]] for c in ("cross spot", "cross drill")]},
        ],
        [name, "pauses", {"z_top": jaw_top, "count": 0}],
        [name, "depth", {"z_min": _r(tip)}],
    ]
    for k, checks in enumerate(
        (hole_checks(spot_z, CENTRE_DRILL["body_mm"]), hole_checks(tip, drill))
    ):
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
    model = rt.import_step(
        doc, "Crankshaft", ctx["step"], frame["origin"], frame["axes"]
    )
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
