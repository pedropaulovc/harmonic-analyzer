"""FreeCAD CAM recipe for MHA-DT-12-TL-01, the cylinder gears' cam turning
fixture body.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The disc's sizes and
the hole stations come from the feature export (the register, the thickness,
the stub hole's and the clock-pin hole's stations from the register axis,
their ream bands and the pin hole's depth band); the parallels, spots, pecks,
the runs past the back face and the feeds from ``plan.toml`` ``[parameters]``
and ``milling_cuts``; drill and reamer diameters from the shop (``shop/``).
Every path is written here (``rt.custom``): straight lines a recipe can
state exactly. Typed here, because neither record carries them: the #2
centre drill's catalogue geometry (it sets the spot depths), the twist
drills' 118° point, the approach, safe and clearance heights, the least run
of the #65 below the .0365 reamer's end and the vise jaws' depth (keep-out
shapes only).

Route (plan text in ``plan.toml``): the register and both faces are made on
the lathe (no NC). The disc then lies back face down on two 1 in parallels in
the vise, gripped across its register, face F up: CF01 spots, drills 23/64
and reams .3740 through for the stub; CF02 spots, drills #65 and reams .0365
blind for the clock pin. Both holes are cut from one pick-up, so their
stations from the register axis are the programs' coordinates.

Work frame (G54), set in the setup: X0 Y0 the register axis, Z0 face F (up);
+X along the jaws, the throw line (model +Y) along +X, so the stub hole sits
at -X and the clock-pin hole at +X, its small offset (model -X) at +Y, toward
the fixed jaw.

Toolpath rules (owner rulings 2026-11-16): plunges at the cutting feed, real
G0 above the stock; reamers feed in and feed back out with the spindle
running, so no rapid leaves a reamed hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_cylinder_gear_tl_cam_fixture"
COMMENT = "MHA-DT-12-TL-01 cylinder gear cam turning fixture"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("CF01_stub_hole", (("stub_spot",), ("stub_drill",), ("stub_ream",))),
    ("CF02_pin_hole", (("pin_spot",), ("pin_drill",), ("pin_ream",))),
)
# Every program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the lathe tools, the gauges and the files are not).
CAM_TOOLS = ("spot", "drill-23-64", "reamer-3740", "drill-65", "reamer-0365")
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
# Moves between cuts run this far above face F (the jaw tops stand below it).
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# The #65's full diameter runs at least this far below the .0365 reamer's
# end, so the reamer never bottoms on the drill's point (.020 in).
PIN_DRILL_BELOW_REAM_MIN_MM = 0.508
# Keep-outs: each vise jaw's depth outward from the gripped register; the
# parallels' length (4 in, shop-equipment fixtures.parallels-lms-6745).
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 4 * IN
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
    xy: tuple[float, float], top: float, tip: float, peck: float | None, clear: float
) -> list[str]:
    """Drill from ``top`` to ``tip``: in pecks of ``peck`` with a full
    retract to the R plane and a rapid back to just above the last peck, or
    in one feed when ``peck`` is None. Moves to and from the hole run at
    ``clear``."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    depths = []
    depth = top
    while peck is not None and depth - peck > tip + 1e-6:
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


def _reamed(xy: tuple[float, float], top: float, tip: float, clear: float) -> list[str]:
    """Ream from the R plane to ``tip`` in one feed and back out at the same
    feed, spindle running, so the reamer never rapids out of the hole."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(tip):.3f} F{{feed}}",
        f"G1 Z{r_plane:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The disc as the route assumes it: the register along model Z from the
    back face (Z0) to face F; both holes along -Z from face F, the stub hole
    through on the -Y side of the axis, the clock-pin hole blind, each
    located by its printed stations from the register axis."""
    f = features["features"]
    register, stub, pin = f["register"], f["stub_hole"], f["pin_hole"]
    back = f["back_face"]["plane"]["value"]
    front = f["front_face"]["plane"]["value"]
    if (
        back != 0.0
        or register["axis"] != [0.0, 0.0, 1.0]
        or register["at"]
        != [
            0.0,
            0.0,
            0.0,
        ]
    ):
        raise ValueError("register: expected along model Z through the origin from Z0")
    thickness = front - back
    if not register["length"][0] <= thickness <= register["length"][1]:
        raise ValueError(
            f"model thickness {thickness:.4f} is outside the printed band "
            f"{register['length']}"
        )
    for name, hole in (("stub_hole", stub), ("pin_hole", pin)):
        if hole["axis"] != [0.0, 0.0, -1.0] or hole["at"][2] != front:
            raise ValueError(f"{name}: expected along -Z from face F")
        for axis in ("x", "y"):
            key = f"station_{axis}"
            if key in hole and hole[f"{key}_from"] != "register":
                raise ValueError(f"{name}: expected {key} from the register axis")
    if not stub.get("thru") or stub["at"][0] != 0.0 or stub["at"][1] >= 0.0:
        raise ValueError("stub_hole: expected through, on the -Y centreline")
    if not math.isclose(-stub["at"][1], stub["station_y_nominal"], abs_tol=1e-6):
        raise ValueError("stub_hole: its station is not its model position")
    if not (
        math.isclose(abs(pin["at"][0]), pin["station_x_nominal"], abs_tol=1e-6)
        and math.isclose(abs(pin["at"][1]), pin["station_y_nominal"], abs_tol=1e-6)
    ):
        raise ValueError("pin_hole: its stations are not its model position")
    if "depth" not in pin or "thru" in pin:
        raise ValueError("pin_hole: expected blind, with a depth band")
    return {
        "thickness": thickness,
        "dia": register["nominal_dia"],
        "radius": register["nominal_dia"] / 2,
        "stub_at": stub["at"],
        "stub_dia": stub["dia"],
        "pin_at": pin["at"],
        "pin_dia": pin["dia"],
        "pin_depth": pin["depth"],
    }


def _machine_xy(at: list[float]) -> list[float]:
    """A model point's work X, Y: the throw line (model +Y) along +X, model
    -X along +Y (the frame's axes in :func:`context`)."""
    return [_r(at[1]), _r(-at[0])]


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    thickness, radius = g["thickness"], g["radius"]

    spot_dia = CENTRE_DRILL["body_mm"]
    d_stub = _shop_tool(plan, shop, "drill-23-64")["diameter_mm"]
    r_stub = _shop_tool(plan, shop, "reamer-3740")["diameter_mm"]
    d_pin = _shop_tool(plan, shop, "drill-65")["diameter_mm"]
    r_pin = _shop_tool(plan, shop, "reamer-0365")["diameter_mm"]
    for name, reamer, band in (
        ("stub", r_stub, g["stub_dia"]),
        ("clock-pin", r_pin, g["pin_dia"]),
    ):
        if not band[0] <= reamer <= band[1]:
            raise ValueError(f"{name} reamer Ø{reamer} outside the hole band {band}")
    if not (d_stub < r_stub and d_pin < r_pin):
        raise ValueError("a drill leaves nothing for its reamer")
    # The plan's cuts declare the shop's diameters (the reamers' and the
    # drills'); the spots declare their spot diameters, checked below.
    for name, dia in (
        ("stub drill", d_stub),
        ("stub ream", r_stub),
        ("pin drill", d_pin),
        ("pin ream", r_pin),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not its tool's Ø{dia}")
    for name, key in (
        ("stub spot", "stub_spot_dia_mm"),
        ("pin spot", "pin_spot_dia_mm"),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), p[key], abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not process.{key}")
    if p["stub_spot_dia_mm"] >= d_stub:
        raise ValueError("the stub spot is not under the 23/64 drill")
    if p["pin_spot_dia_mm"] >= d_pin:
        raise ValueError("the pin spot is not under the #65 drill")

    # The hold: the disc on the parallels, the jaws gripping the register
    # from the parallels' tops to the jaw tops; face F above the jaw tops.
    grip = p["vise_jaw_height_mm"] - p["parallel_height_mm"]
    _agree(plan, "grip_mm", grip)
    if grip >= thickness:
        raise ValueError("face F stands below the jaw tops")
    jaw_top = grip - thickness  # the jaw tops below Z0
    _agree(plan, "jaw_top_below_z0_mm", -jaw_top)
    gap = g["dia"] - 2 * p["parallel_thickness_mm"]
    _agree(plan, "parallel_gap_mm", gap)
    holds = [
        s["vise_hold"] for s in plan["setups"] if isinstance(s.get("vise_hold"), dict)
    ]
    inset = -(p["vise_jaw_width_mm"] - g["dia"]) / 2
    if len(holds) != 1 or not math.isclose(
        holds[0]["overhang_mm"][0], inset, abs_tol=PLAN_TOL_MM
    ):
        raise ValueError(f"vise_hold overhang_mm: expected [{inset:.4f}, 'rest']")

    stub_xy = _machine_xy(g["stub_at"])
    pin_xy = _machine_xy(g["pin_at"])
    # Every hole runs out (or ends) clear of the parallels under the disc.
    for name, xy, dia in (("stub", stub_xy, r_stub), ("clock-pin", pin_xy, r_pin)):
        if abs(xy[1]) + dia / 2 >= gap / 2:
            raise ValueError(f"the {name} hole reaches the parallels under the disc")

    # Stub: spot, 23/64 pecked through, ream through.
    stub_spot = _spot_depth(p["stub_spot_dia_mm"])
    stub_tip = -(thickness + p["drill_past_mm"] + _point(d_stub))
    stub_ream_tip = -(thickness + p["ream_past_mm"])
    _agree(plan, "stub_drill_tip_mm", stub_tip)
    _agree(plan, "stub_ream_tip_mm", stub_ream_tip)
    # The drill's point stays above the vise bed under the parallels.
    if -stub_tip >= thickness + p["parallel_height_mm"]:
        raise ValueError("the 23/64 drill's point reaches the vise bed")

    # Clock pin: spot, #65 pecked blind, ream blind. The reamer's end lies in
    # the depth band, so its full diameter (its short lead above the end)
    # reaches at least the band's least depth only if the end is past it;
    # the #65's full diameter runs on below the reamer's end.
    pin_spot = _spot_depth(p["pin_spot_dia_mm"])
    depth_min, depth_max = g["pin_depth"]
    ream_end = -p["pin_ream_tip_mm"]
    if not depth_min < ream_end <= depth_max:
        raise ValueError(
            f"process.pin_ream_tip_mm: the reamer's end {ream_end:.3f} mm is not "
            f"past {depth_min:.3f} and within {depth_max:.3f} (the depth band)"
        )
    if p["pin_drill_full_mm"] - ream_end < PIN_DRILL_BELOW_REAM_MIN_MM - 1e-9:
        raise ValueError(
            "process.pin_drill_full_mm: the #65 ends less than "
            f"{PIN_DRILL_BELOW_REAM_MIN_MM} mm below the reamer's end"
        )
    pin_tip = -(p["pin_drill_full_mm"] + _point(d_pin))
    _agree(plan, "pin_drill_tip_mm", pin_tip)
    if -pin_tip >= thickness - 1.0:
        raise ValueError("the #65's point comes within 1 mm of the back face")
    # The air prove-out (Setup 2) lifts Z0 by prove_raise_mm: every tip,
    # the deepest first, must then stop at least SAFE_MM above face F.
    deepest = min(stub_tip, stub_ream_tip, pin_tip, p["pin_ream_tip_mm"])
    if p["prove_raise_mm"] + deepest < SAFE_MM:
        raise ValueError(
            f"process.prove_raise_mm {p['prove_raise_mm']:g}: the air prove-out "
            f"cuts face F (deepest tip {deepest:.3f} mm)"
        )

    for name, binding in (
        ("stub drill", "{{cad.envelope_z_mm}}"),
        ("pin drill", "{{process.pin_drill_full_mm}}"),
    ):
        stated = _op_with_cut(plan, name)[0]["hole_depth_mm"]
        if stated != binding:
            raise ValueError(
                f"'{name}' operation hole_depth_mm {stated!r}, not {binding}"
            )
    if _op_with_cut(plan, "stub drill")[0]["peck"] != "none":
        raise ValueError("'stub drill' peck is not none (L/D 2.8, one feed)")
    if _op_with_cut(plan, "pin drill")[0]["peck"] != {
        "step_mm": p["pin_peck_mm"],
        "retract": "full",
    }:
        raise ValueError(
            "'pin drill' peck is not process.pin_peck_mm with full retract"
        )
    speeds = {
        name: _speed(plan, name)
        for name in (
            "stub spot",
            "stub drill",
            "stub ream",
            "pin spot",
            "pin drill",
            "pin ream",
        )
    }
    for name, key in (
        ("stub spot", "stub_spot_feed_per_min_mm"),
        ("stub drill", "drill_23_64_feed_per_min_mm"),
        ("stub ream", "ream_3740_feed_per_min_mm"),
        ("pin spot", "pin_spot_feed_per_min_mm"),
        ("pin drill", "drill_65_feed_per_min_mm"),
        ("pin ream", "ream_0365_feed_per_min_mm"),
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

    def drill(
        tool: str, dia: float, name: str, flutes: int | None = None
    ) -> dict[str, Any]:
        rpm, feed = speeds[name]
        spec = {"tool": tool, "dia": dia, "rpm": rpm, "feed": feed, "plunge": feed}
        if flutes is None:
            spec["shape"] = "drill"
            spec["tip_angle"] = (
                CENTRE_DRILL["point_deg"] if tool == "spot" else DRILL_POINT_DEG
            )
        else:
            spec["shape"] = "endmill"
            spec["flutes"] = flutes
        return spec

    # Frame (model point p -> axes · (p - origin)): face F at Z0, model +Y
    # along +X, model -X along +Y.
    frames = {
        "face": {
            "origin": [0.0, 0.0, thickness],
            "axes": [[0, 1, 0], [-1, 0, 0], [0, 0, 1]],
        }
    }
    stock = ((-radius, radius), (-radius, radius), (-thickness, 0.0))
    stub_flutes = int(_cut(plan, "stub ream", "flutes"))
    pin_flutes = int(_cut(plan, "pin ream", "flutes"))
    jobs = [
        {
            **drill("spot", spot_dia, "stub spot"),
            "label": "stub spot",
            "ops": [
                [
                    "stub_spot",
                    "spot the stub hole",
                    _spot(stub_xy, 0.0, -stub_spot, CLEAR_MM),
                ]
            ],
        },
        {
            **drill("drill-23-64", d_stub, "stub drill"),
            "label": "stub drill",
            "ops": [
                [
                    "stub_drill",
                    "drill 23/64 through",
                    _pecked(stub_xy, 0.0, stub_tip, None, CLEAR_MM),
                ]
            ],
        },
        {
            **drill("reamer-3740", r_stub, "stub ream", stub_flutes),
            "label": "stub ream",
            "ops": [
                [
                    "stub_ream",
                    "ream .3740 through",
                    _reamed(stub_xy, 0.0, stub_ream_tip, CLEAR_MM),
                ]
            ],
        },
        {
            **drill("spot", spot_dia, "pin spot"),
            "label": "pin spot",
            "ops": [
                [
                    "pin_spot",
                    "spot the clock-pin hole",
                    _spot(pin_xy, 0.0, -pin_spot, CLEAR_MM),
                ]
            ],
        },
        {
            **drill("drill-65", d_pin, "pin drill"),
            "label": "pin drill",
            "ops": [
                [
                    "pin_drill",
                    "drill #65 blind",
                    _pecked(pin_xy, 0.0, pin_tip, p["pin_peck_mm"], CLEAR_MM),
                ]
            ],
        },
        {
            **drill("reamer-0365", r_pin, "pin ream", pin_flutes),
            "label": "pin ream",
            "ops": [
                [
                    "pin_ream",
                    "ream .0365 blind",
                    _reamed(pin_xy, 0.0, p["pin_ream_tip_mm"], CLEAR_MM),
                ]
            ],
        },
    ]
    for job in jobs:
        job["frame"] = "face"
        job["stock"] = stock

    # Keep-outs: the jaws on the register at ±radius along Y, their tops
    # jaw_top below Z0, across the jaws' width; a parallel under the disc
    # against each jaw, its top at the back face.
    jaw_x = (-p["vise_jaw_width_mm"] / 2, p["vise_jaw_width_mm"] / 2)
    par_x = (-PARALLEL_LENGTH_MM / 2, PARALLEL_LENGTH_MM / 2)
    boxes = [
        _box("moving jaw", jaw_x, (-radius - JAW_DEPTH_MM, -radius), jaw_top),
        _box("fixed jaw", jaw_x, (radius, radius + JAW_DEPTH_MM), jaw_top),
        _box("moving-jaw parallel", par_x, (-radius, -gap / 2), -thickness),
        _box("fixed-jaw parallel", par_x, (gap / 2, radius), -thickness),
    ]

    t = numbers
    expect: list[list[Any]] = []

    def hole_checks(centres, bottom, radius_):
        return [
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": 0.0, "open_holes": centres}],
            ["vertical_below_top", {"z_top": 0.0}],
            ["air_feed", {"z_top": 0.0}],
            ["keep_out", {"radius": radius_, "boxes": boxes}],
        ]

    programs = {
        "CF01_stub_hole": (
            [t["spot"], t["drill-23-64"], t["reamer-3740"]],
            [
                [speeds["stub spot"][0]],
                [speeds["stub drill"][0]],
                [speeds["stub ream"][0]],
            ],
            stub_tip,
            [
                hole_checks([stub_xy], -stub_spot, spot_dia / 2),
                hole_checks([stub_xy], stub_tip, d_stub / 2),
                hole_checks([stub_xy], stub_ream_tip, r_stub / 2)
                + [["feed_out", {"z_top": 0.0}]],
            ],
        ),
        "CF02_pin_hole": (
            [t["spot"], t["drill-65"], t["reamer-0365"]],
            [
                [speeds["pin spot"][0]],
                [speeds["pin drill"][0]],
                [speeds["pin ream"][0]],
            ],
            pin_tip,
            [
                hole_checks([pin_xy], -pin_spot, CENTRE_DRILL["pilot_mm"] / 2),
                hole_checks([pin_xy], pin_tip, d_pin / 2),
                hole_checks([pin_xy], p["pin_ream_tip_mm"], r_pin / 2)
                + [["feed_out", {"z_top": 0.0}]],
            ],
        ),
    }
    for name, (tools, rpms, deepest, sections) in programs.items():
        expect += [
            [name, "tool_changes", {"z_top": 0.0, "tools": tools, "loads_first": True}],
            [name, "spindle", {"rpm": rpms}],
            [name, "pauses", {"z_top": 0.0, "count": 0}],
            [name, "depth", {"z_min": _r(deepest)}],
        ]
        for k, checks in enumerate(sections):
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
            doc, f"Fixture {key}", ctx["step"], frame["origin"], frame["axes"]
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
