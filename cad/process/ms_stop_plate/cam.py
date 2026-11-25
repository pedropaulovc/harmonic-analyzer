"""FreeCAD CAM recipe for MHA-MS-03, the stop plate.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The plate's sizes and
both holes come from the feature export (their stations from the locating
end, their height from the locating edge, the #49 pair pilot's diameter and
its depth in MHA-MS-02); the stack, the spot, the pecks and the tips from
``plan.toml`` ``[parameters]`` and ``milling_cuts``; the drills' diameters
from ``shop/``. Every path is written here (``rt.custom``). Typed here,
because neither record carries them: the #1 centre drill's catalogue geometry
(it sets the spot depth), the twist drills' 118° point, the safe and
clearance heights and the vise jaws' depth (keep-out shapes only).

Route (``plan.toml``): the plate is cut and filed at the bench; on the mill
it lies seating face down on its finished MHA-MS-02 block, the two gripped
together across their .84 length on 1 in parallels, locating ends on the
fixed jaw. MS01 spots both holes with the #1 centre drill and drills the #49
pilots through the plate into the block, .300 below the block face. MS02:
the plate turned over about its long axis on the same block, its pilots over
the block's open window; the #41 opens both through into the window.

Work frames (G54), each set in its setup:
- MS01: X0 the locating edges (on the right; the pair to -X), Y0 the fixed
  jaw (the locating ends; the pair to -Y), Z0 the plate's top at its nominal
  thickness above the block face.
- MS02: X0 the plate's locating edge (now on the left; the plate to +X), Y0
  the fixed jaw, Z0 the plate's top (its seating face).

The stack's top stands below the jaw tops, so every move between holes runs
above the jaws.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ms_stop_plate"
COMMENT = "MHA-MS-03 stop plate"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("MS01_pair_pilot", (("pair_spot",), ("pair_pilot",))),
    ("MS02_open", ("plate_open",)),
)
# Every program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the files and the scrapers are not).
CAM_TOOLS = ("spot", "drill-49", "drill-41")
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
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# Drill R planes start this far above the plate's top: real G0 brings the
# tool down to it, between the jaws.
SAFE_MM = 1.0
# Moves between holes run this far above the jaw tops.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped end.
JAW_DEPTH_MM = IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# The plate's nominal and the flip: model Z of the outer and seating faces.
HOLES = ("clearance_hole_1", "clearance_hole_2")


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
    """(rpm, mm/min) the plan authors on the cut (no settings record: the
    plate's alloy is not on record), agreeing with its operation's rpm."""
    op, _record = _op_with_cut(plan, cut)
    rpm, feed = _cut(plan, cut, "rpm"), _cut(plan, cut, "feed_mm_min")
    if "settings" in op or float(op["rpm"]) != rpm:
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
    """Depth below the surface at which the #1 centre drill's 60° countersink
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


def _pecked(
    xy: list[float], top: float, tip: float, peck: float, clear: float
) -> list[str]:
    """Drill from ``top`` to ``tip`` in pecks of ``peck``, each with a full
    retract to the R plane and a rapid back to just above the last peck.
    Moves to and from the hole run at ``clear``."""
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
    """The plate's sizes and holes from the export, each checked against the
    frame the recipe assumes: the locating end at model X0, the locating edge
    at Y0, the seating face at Z0 with the plate below it, both holes through
    along Z from the outer face, the pair pilot alike on both."""
    f = features["features"]
    if (
        f["locating_end"]["plane"]["value"] != 0.0
        or f["locating_edge"]["plane"]["value"] != 0.0
        or f["seating_face"]["plane"]["value"] != 0.0
    ):
        raise ValueError(
            "locating end, locating edge and seating face: expected at model X0, Y0, Z0"
        )
    length = f["far_end"]["plane"]["value"]
    height = f["roof_edge"]["plane"]["value"]
    thickness = -f["outer_face"]["plane"]["value"]
    for name, value, nominal in (
        ("far_end", length, f["far_end"]["length_nominal"]),
        ("roof_edge", height, f["roof_edge"]["height_nominal"]),
        ("outer_face", thickness, f["outer_face"]["thickness_nominal"]),
    ):
        if not math.isclose(value, nominal, abs_tol=1e-3):
            raise ValueError(
                f"{name}: the model's {value:.4f} is not its nominal {nominal}"
            )
    holes = []
    pilots = set()
    for name in HOLES:
        hole = f[name]
        if hole["axis"] != [0.0, 0.0, 1.0] or not hole.get("thru"):
            raise ValueError(
                f"{name}: expected through the plate along +Z from the outer face"
            )
        x, y, _z = hole["at"]
        if not hole["station"][0] <= x <= hole["station"][1]:
            raise ValueError(
                f"{name}: X {x} is outside its station band {hole['station']}"
            )
        if not hole["height"][0] <= y <= hole["height"][1]:
            raise ValueError(
                f"{name}: Y {y} is outside its height band {hole['height']}"
            )
        pilots.add(
            (
                hole["pair_pilot_dia"],
                tuple(hole["pair_pilot_depth_in_mate"]),
                hole["pair_pilot_depth_in_mate_nominal"],
            )
        )
        holes.append({"name": name, "at": hole["at"], "dia": hole["dia"]})
    if len(pilots) != 1:
        raise ValueError(f"the holes' pair pilots differ: {sorted(pilots)}")
    pilot_dia, _pilot_band, pilot_depth = pilots.pop()
    return {
        "length": length,
        "height": height,
        "thickness": thickness,
        "thickness_max": f["outer_face"]["thickness"][1],
        "holes": holes,
        "pilot_dia": pilot_dia,
        "pilot_depth": pilot_depth,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    length, height, thickness = g["length"], g["height"], g["thickness"]

    d49 = _shop_tool(plan, shop, "drill-49")["diameter_mm"]
    d41 = _shop_tool(plan, shop, "drill-41")["diameter_mm"]
    if not math.isclose(d49, g["pilot_dia"], abs_tol=1e-4):
        raise ValueError(f"#49 Ø{d49} is not the declared pair pilot Ø{g['pilot_dia']}")
    for hole in g["holes"]:
        if not hole["dia"][0] <= d41 <= hole["dia"][1]:
            raise ValueError(
                f"#41 Ø{d41} is outside {hole['name']}'s band {hole['dia']}"
            )
    if not math.isclose(_cut(plan, "plate open", "cutter_dia_mm"), d41, abs_tol=1e-6):
        raise ValueError("'plate open' cutter_dia_mm is not the #41's")
    if _cut(plan, "pair pilot", "cutter_dia_mm") != d49:
        raise ValueError("'pair pilot' cutter_dia_mm is not the #49's")

    # The stack in the vise: the plate's nominal on the block, below the jaw
    # tops; the pilot's full diameter at the declared depth in the block.
    stack = p["block_depth_mm"] + thickness
    _agree(plan, "stack_height_mm", stack)
    below = p["vise_jaw_height_mm"] - p["parallel_height_mm"] - stack
    _agree(plan, "stack_below_jaw_top_mm", below)
    if below <= 0:
        raise ValueError(
            "the stack stands above the jaw tops: the plate is not gripped"
        )
    _agree(plan, "vise_inset_mm", -(p["vise_jaw_width_mm"] - height) / 2)
    pilot_tip = -(thickness + g["pilot_depth"] + _point(d49))
    _agree(plan, "pilot_tip_height_mm", pilot_tip)
    if p["block_depth_mm"] + pilot_tip + thickness <= 0:
        raise ValueError("the pilot's point breaks through the block's back")
    open_tip = -(g["thickness_max"] + p["open_past_mm"] + _point(d41))
    _agree(plan, "open_tip_height_mm", open_tip)
    if -open_tip - g["thickness_max"] >= p["block_window_depth_mm"]:
        raise ValueError("the #41's point reaches the block's window floor")

    spot_dia = p["spot_dia_mm"]
    if not math.isclose(
        _cut(plan, "pair spot", "cutter_dia_mm"), spot_dia, abs_tol=1e-6
    ):
        raise ValueError("'pair spot' cutter_dia_mm is not process.spot_dia_mm")
    if spot_dia >= d49:
        raise ValueError("the spot is not under the #49: it would chamfer the block")
    spot_depth = _spot_depth(spot_dia)
    if spot_depth - thickness >= g["pilot_depth"]:
        raise ValueError(
            "the spot reaches past the #49's full-diameter depth in the block"
        )
    peck = p["pilot_peck_mm"]
    op = _op_with_cut(plan, "pair pilot")[0]
    if op["peck"] != {"step_mm": peck, "retract": "full"}:
        raise ValueError(
            "'pair pilot' peck is not process.pilot_peck_mm with full retract"
        )
    if _op_with_cut(plan, "plate open")[0]["peck"] != "none":
        raise ValueError("'plate open' is one plunge (peck none)")
    speeds = {
        name: _speed(plan, name) for name in ("pair spot", "pair pilot", "plate open")
    }
    for rpm, feed in speeds.values():
        if rpm != p["hole_rpm"] or not math.isclose(feed, p["hole_feed_per_min_mm"]):
            raise ValueError(
                "a hole cut is not at process.hole_rpm/hole_feed_per_min_mm"
            )

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)). MS01: the outer face up
    # at Z0, the locating end at the fixed jaw (+Y), the locating edge on the
    # right. MS02: the plate turned over about its length (model X): the
    # seating face up at Z0, the locating end still at the fixed jaw, the
    # locating edge now on the left.
    frames = {
        "pair": _frame([0.0, 0.0, -thickness], [-1, 0, 0], [0, 0, -1]),
        "open": _frame([0.0, 0.0, 0.0], [-1, 0, 0], [0, 0, 1]),
    }
    stocks = {
        "pair": ((-height, 0.0), (-length, 0.0), (-thickness, 0.0)),
        "open": ((0.0, height), (-length, 0.0), (-thickness, 0.0)),
    }
    centres = {}
    for key, frame in frames.items():
        points = []
        for hole in g["holes"]:
            x, y, z = _to(
                frame,
                [hole["at"][0], hole["at"][1], -thickness if key == "pair" else 0.0],
            )
            if not math.isclose(z, 0.0, abs_tol=1e-6):
                raise ValueError(
                    f"{key}: {hole['name']} does not enter at the plate's top"
                )
            points.append([_r(x), _r(y)])
        (x0, x1), (y0, y1), _z = stocks[key]
        if not all(x0 < x < x1 and y0 < y < y1 for x, y in points):
            raise ValueError(f"{key}: holes {points} are not on the plate")
        centres[key] = points
    # MS02 puts each pilot over the block's window: the block's locating edge
    # lies under the plate's roof edge, so a hole's height from the plate's
    # locating edge stands at height − that from the block's.
    for hole in g["holes"]:
        on_block = height - hole["at"][1]
        reach = hole["dia"][1] / 2
        if not (
            p["block_window_low_mm"] < on_block - reach
            and on_block + reach < p["block_window_high_mm"]
        ):
            raise ValueError(
                f"{hole['name']}: turned over, it stands at {on_block:.3f} on the block, not over its window"
            )

    jaw_top = below
    clear = jaw_top + CLEAR_MM
    spot_tool = {
        "tool": "spot",
        "dia": CENTRE_DRILL["body_mm"],
        "shape": "drill",
        "tip_angle": CENTRE_DRILL["point_deg"],
        "rpm": speeds["pair spot"][0],
        "feed": speeds["pair spot"][1],
        "plunge": speeds["pair spot"][1],
    }
    d49_tool = {
        "tool": "drill-49",
        "dia": d49,
        "shape": "drill",
        "tip_angle": DRILL_POINT_DEG,
        "rpm": speeds["pair pilot"][0],
        "feed": speeds["pair pilot"][1],
        "plunge": speeds["pair pilot"][1],
    }
    d41_tool = {
        "tool": "drill-41",
        "dia": d41,
        "shape": "drill",
        "tip_angle": DRILL_POINT_DEG,
        "rpm": speeds["plate open"][0],
        "feed": speeds["plate open"][1],
        "plunge": speeds["plate open"][1],
    }
    jobs = [
        {
            **spot_tool,
            "frame": "pair",
            "label": "pair spot",
            "stock": stocks["pair"],
            "ops": [
                [
                    "pair_spot",
                    "spot both holes",
                    [
                        line
                        for xy in centres["pair"]
                        for line in _spot(xy, 0.0, -spot_depth, clear)
                    ],
                ]
            ],
        },
        {
            **d49_tool,
            "frame": "pair",
            "label": "pair pilot",
            "stock": stocks["pair"],
            "ops": [
                [
                    "pair_pilot",
                    "drill both #49 pilots into the block",
                    [
                        line
                        for xy in centres["pair"]
                        for line in _pecked(xy, 0.0, pilot_tip, peck, clear)
                    ],
                ]
            ],
        },
        {
            **d41_tool,
            "frame": "open",
            "label": "plate open",
            "stock": stocks["open"],
            "ops": [
                [
                    "plate_open",
                    "open both holes #41",
                    [
                        line
                        for xy in centres["open"]
                        for line in _pecked(xy, 0.0, open_tip, -open_tip + 1.0, clear)
                    ],
                ]
            ],
        },
    ]

    # Keep-outs: the jaws on the two ends (Y), their tops above the stack,
    # across the jaw width centred on the plate.
    jaw_w = p["vise_jaw_width_mm"]

    def jaws(x: tuple[float, float]) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - jaw_w / 2, mid + jaw_w / 2)
        return [
            _box("moving jaw", span, (-length - JAW_DEPTH_MM, -length), jaw_top),
            _box("fixed jaw", span, (0.0, JAW_DEPTH_MM), jaw_top),
        ]

    keep = {"pair": jaws(stocks["pair"][0]), "open": jaws(stocks["open"][0])}
    tn = numbers

    def hole_checks(key: str, bottom: float, radius: float) -> list[list[Any]]:
        return [
            ["holes", {"centres": centres[key], "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": 0.0, "open_holes": centres[key]}],
            ["vertical_below_top", {"z_top": 0.0}],
            ["air_feed", {"z_top": 0.0}],
            ["keep_out", {"radius": radius, "boxes": keep[key]}],
        ]

    expect: list[list[Any]] = []
    name = "MS01_pair_pilot"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": jaw_top,
                "tools": [tn["spot"], tn["drill-49"]],
                "loads_first": True,
            },
        ],
        [
            name,
            "spindle",
            {"rpm": [[speeds["pair spot"][0]], [speeds["pair pilot"][0]]]},
        ],
        [name, "pauses", {"z_top": jaw_top, "count": 0}],
        [name, "depth", {"z_min": _r(pilot_tip)}],
    ]
    for k, checks in enumerate(
        (
            hole_checks("pair", -spot_depth, CENTRE_DRILL["body_mm"] / 2),
            hole_checks("pair", pilot_tip, d49 / 2),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]
    name = "MS02_open"
    expect += [
        [
            name,
            "tool_changes",
            {"z_top": jaw_top, "tools": [tn["drill-41"]], "loads_first": True},
        ],
        [name, "spindle", {"rpm": [[speeds["plate open"][0]]]}],
        [name, "pauses", {"z_top": jaw_top, "count": 0}],
        [name, "depth", {"z_min": _r(open_tip)}],
        *[
            [name, check, kwargs]
            for check, kwargs in hole_checks("open", open_tip, d41 / 2)
        ],
    ]

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
            doc, f"Stop plate {key}", ctx["step"], frame["origin"], frame["axes"]
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


# The as-machined report (``cad/scripts/_as_machined.py``) only reports: it
# never fails the task. "gate" would fail it on a difference over the noise
# line or a rapid that cuts.
AS_MACHINED_MODE = "report"


def as_machined(ctx: dict[str, Any], inputs: Any) -> dict[str, Any]:
    """What the as-machined report needs: the plate as it comes to the mill,
    sawn and filed to its outline at the bench (Setups 1-2; the filed roof
    chamfers are not in a box), MS01's stock in the ``pair`` frame, its
    thickness the sheet's as rolled: the outer face's band, nominal the
    drawing's (the model's). The seating face lies on the block, so the
    outer face (MS01's top) moves with the thickness. Both programs cut in
    their own frames; the #49's run into the block below is not this part."""
    g = _geometry(inputs.features)
    band = inputs.features["features"]["outer_face"]["thickness"]
    (x0, x1), (y0, y1), _z = next(job["stock"] for job in ctx["jobs"] if job["frame"] == "pair")
    return {
        "parts": {
            "": {
                "blank": {
                    "frame": "pair",
                    "box": [[x0, x1], [y0, y1], [-g["thickness"], 0.0]],
                    "length": {
                        "axis": "z",
                        "keep": "min",
                        "mm": {"nominal": g["thickness"], "min": band[0], "max": band[1]},
                    },
                }
            }
        },
        "skip": {},
        "notes": ["the outline and both roof chamfers are sawn and filed at the bench (Setups 1-2)"],
    }
