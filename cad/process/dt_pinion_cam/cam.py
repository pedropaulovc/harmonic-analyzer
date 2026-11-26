"""FreeCAD CAM recipe for MHA-DT-23, the pinion eccentric cam.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The disc's sizes come
from the feature export (the cam O.D. and its offset from the bore, the
length, the bore and the set-screw hole's station and reach); the parallels,
spots, pecks, the runs past the bottom face and the feeds from ``plan.toml``
``[parameters]`` and ``milling_cuts``; drill and reamer diameters from the
shop (``shop/``). Every path is written here (``rt.custom``): straight lines
a recipe can state exactly. Typed here, because neither record carries them:
the #2 centre drill's catalogue geometry (it sets the spot depths), the twist
drills' 118° point, the machine's Z top for the tap file's retract, the
approach, safe and clearance heights and the vise jaws' depth (keep-out
shapes only).

Route (plan text in ``plan.toml``): the O.D. and both faces are turned on
the lathe (no NC). The disc then stands on its front face on the parallels
in the vise, gripped on its O.D.: CM01 spots, drills C and reams the bore
through, offset from the O.D. axis along the jaws. It then lies in the vise,
its axis along the jaws, the thick side up: CM02 spots and drills #50 down
into the bore; CM03 brings the tap guide over it for tapping by hand.

Work frames (G54), each set in its setup:
- CM01: X0 Y0 the O.D. axis, Z0 the rear face (up); the bore at +X.
- CM02/CM03: X0 the front face, +X along the disc's axis; Y0 the O.D.
  axis; Z0 the O.D.'s top line.

Toolpath rules (owner rulings 2026-11-16): plunges at the cutting feed, real
G0 above the stock. The hole is tapped by hand (FluidNC cannot rigid-tap;
owner, Pedro, 2026-11-17), the T-handle wrench's centre hole on the spring
point of the Fisher tap guide in the 1/2 in R8 collet (owner, Pedro,
2026-11-21: "use
https://littlemachineshop.com/products/tap-guide-fisher?variant=45472915226805
on r8 0.5 collet"), spindle off, the operator jogging Z down to push the
point home. FluidNC refuses jogs while an M0 holds the program (FluidNC
wiki, "Single Block Mode",
http://wiki.fluidnc.com/en/features/single_block_mode), so the tap stop is
a file of its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_pinion_cam"
COMMENT = "MHA-DT-23 pinion eccentric cam"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("CM01_bore", (("bore_spot",), ("bore_drill",), ("bore_ream",))),
    ("CM02_set_screw", (("tap_spot",), ("tap_drill",))),
    ("CM03_set_screw_tap", ("tap_stop",)),
)
# Every program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the lathe tools, the tap and the files are not).
CAM_TOOLS = ("spot", "drill-c", "reamer", "drill-50", "tap-guide")
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
# The tap file's first motion: G53 G0 to machine Z0, the homed top (as the
# magnifying clamp's recipe); the owner (Pedro) confirmed it, answered in
# person 2026-11-21 (cnc rulings record): machine Z = 0 is the top of travel
# after homing.
MACHINE_Z_TOP_MM = 0.0
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top (or the jaw tops).
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped O.D.; the
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
    in one feed when ``peck`` is None. Moves to and
    from the hole run at ``clear``."""
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
    feed, spindle running, so the reamer never rapids out of the bore."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(tip):.3f} F{{feed}}",
        f"G1 Z{r_plane:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def _geometry(features: dict[str, Any]) -> dict[str, float]:
    """The disc as the routes assume it: the O.D. and the bore along model Z
    from the front face, the bore offset from the O.D. axis along +Y (the
    thin side), the set-screw hole radial along +Y from the O.D. on the
    thick side at its station from the front face."""
    f = features["features"]
    od, bore, tap = f["cam_od"], f["bore"], f["set_screw_tap"]
    front = f["front_face"]["plane"]["value"]
    rear = f["rear_face"]["plane"]["value"]
    if front != 0.0 or od["axis"] != [0.0, 0.0, 1.0] or bore["axis"] != [0.0, 0.0, 1.0]:
        raise ValueError(
            "cam_od and bore: expected along model Z from the front face at Z0"
        )
    length = rear - front
    if not od["length"][0] <= length <= od["length"][1]:
        raise ValueError(
            f"model length {length:.4f} is outside the printed band {od['length']}"
        )
    offset = [b - a for a, b in zip(od["at"], bore["at"])]
    ecc = bore["eccentricity_nominal"]
    if offset[0] != 0.0 or not math.isclose(offset[1], ecc, abs_tol=1e-6):
        raise ValueError(f"bore offset {offset} from the O.D. axis is not +Y {ecc}")
    if bore["thin_side"] != [0.0, 1.0, 0.0] or not bore["thru"]:
        raise ValueError("bore: expected through, its thin side +Y")
    radius = od["nominal_dia"] / 2
    if tap["axis"] != [0.0, 1.0, 0.0] or tap["at"][0] != 0.0:
        raise ValueError("set_screw_tap: expected radial along +Y in the X0 plane")
    if not math.isclose(tap["at"][1], od["at"][1] - radius, abs_tol=1e-6):
        raise ValueError(
            "set_screw_tap: expected to start on the O.D. at the thick side"
        )
    if tap["angle_from_thin_side_deg"] != 180.0 or tap["into"] != "bore":
        raise ValueError(
            "set_screw_tap: expected opposite the thin side, into the bore"
        )
    if tap["station_from"] != "front_face" or tap["at"][2] != tap["station_nominal"]:
        raise ValueError("set_screw_tap: expected its station from the front face")
    return {
        "length": length,
        "od": od["nominal_dia"],
        "radius": radius,
        "ecc": ecc,
        "bore_dia": bore["dia"],
        "station": tap["station_nominal"],
        # From the O.D.'s top line to the bore's axis, along the hole.
        "reach": bore["at"][1] - tap["at"][1],
        "tap_dia": tap["dia"],
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    length, radius, ecc, station, reach = (
        g["length"],
        g["radius"],
        g["ecc"],
        g["station"],
        g["reach"],
    )

    spot_dia = CENTRE_DRILL["body_mm"]
    dc = _shop_tool(plan, shop, "drill-c")["diameter_mm"]
    dr = _shop_tool(plan, shop, "reamer")["diameter_mm"]
    d50 = _shop_tool(plan, shop, "drill-50")["diameter_mm"]
    if not g["bore_dia"][0] <= dr <= g["bore_dia"][1]:
        raise ValueError(f"reamer Ø{dr} outside the bore band {g['bore_dia']}")
    if not dc < dr:
        raise ValueError(f"C drill Ø{dc} leaves nothing for the reamer Ø{dr}")
    if not g["tap_dia"][0] <= d50 <= g["tap_dia"][1]:
        raise ValueError(f"#50 Ø{d50} outside the tap drill band {g['tap_dia']}")
    # The plan's cuts declare the shop's diameters (the reamer's and the
    # drills'); the spots declare their spot diameters, checked below.
    for name, dia in (("bore drill", dc), ("bore ream", dr), ("tap drill", d50)):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not its tool's Ø{dia}")

    # CM01: the disc on its front face on the stacked parallels; Z0 the rear
    # face. The jaws grip the O.D. from the parallels' tops to the jaw tops.
    grip = p["vise_jaw_height_mm"] - p["riser_height_mm"]
    _agree(plan, "bore_grip_mm", grip)
    bore_jaw_top = grip - length  # the jaw tops below Z0
    gap = g["od"] - 2 * p["parallel_thickness_mm"]
    _agree(plan, "bore_parallel_gap_mm", gap)
    for name, key in (
        ("bore spot", "bore_spot_dia_mm"),
        ("tap spot", "tap_spot_dia_mm"),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), p[key], abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not process.{key}")
    if p["bore_spot_dia_mm"] >= dc:
        raise ValueError("the bore spot is not under the C drill")
    bore_spot = _spot_depth(p["bore_spot_dia_mm"])
    bore_tip = -(length + p["drill_past_mm"] + _point(dc))
    ream_tip = -(length + p["ream_past_mm"])
    import cam_nc

    if p["ream_past_mm"] <= cam_nc.ream_full_diameter_past_min_mm(plan, "reamer"):
        raise ValueError(
            "the reamer's full diameter does not reach face F (cnc.ream-full-diameter)"
        )
    # The reamer's flat end runs out into the gap between the stacks.
    cam_nc.ream_end_face_clear(
        "reamer", ream_tip, -(length + p["drill_past_mm"]), -length, -math.inf
    )
    _agree(plan, "bore_drill_tip_mm", bore_tip)
    _agree(plan, "bore_ream_tip_mm", ream_tip)
    bore_xy = [_r(ecc), 0.0]
    # The bore runs out between the parallels: its radius along Y under the
    # gap's half-width.
    if max(dc, dr) / 2 >= gap / 2:
        raise ValueError("the drill or reamer reaches the parallels under the disc")
    if radius - ecc - dr / 2 < features["features"]["bore"]["thin_wall_min"] - 1e-6:
        raise ValueError("the nominal bore leaves less than the thin-side wall")

    # CM02: lying in the vise, axis along X, its O.D. on the 1 in
    # parallels' inner top edges; Z0 the O.D.'s top line.
    drop = math.sqrt(radius**2 - (gap / 2) ** 2)  # axis above the parallels' tops
    _agree(plan, "cross_axis_height_mm", drop)
    cross_jaw_top = p["vise_jaw_height_mm"] - p["parallel_height_mm"] - drop - radius
    _agree(plan, "cross_jaw_top_mm", cross_jaw_top)
    # The tap stack's ceiling (CM03, the same hold): spindle-to-table maximum
    # less the tool-change clearance, the vise bed, the parallels, the cam's
    # top above them and the collet's gauge, rounded down to .01 in.
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["parallel_height_mm"]
        - (drop + radius)
        - p["r8_collet_gauge_mm"]
    )
    _agree(plan, "tap_stack_max_mm", math.floor(stack / 0.254 + 1e-9) * 0.254)
    if p["tap_spot_dia_mm"] >= d50:
        raise ValueError("the tap spot is not under the #50 drill")
    tap_spot = _spot_depth(p["tap_spot_dia_mm"])
    tap_tip = -(reach + _point(d50))
    _agree(plan, "tap_drill_tip_mm", tap_tip)
    # Setup 3's jobber #50 must stand out of its chuck past this: its tip
    # below the jaw tops.
    _agree(plan, "tap_tip_below_jaw_top_mm", cross_jaw_top - tap_tip)
    # Setup 3 turns the cam about its O.D. axis until the shank in the bore
    # sits on Y0. The hole's angle from the thin side carries the title
    # block's angular tolerance, so the shank's Y off Y0 may be at most the
    # eccentricity × tan(that angle). Stated to 0.1 µm: the plan prints it.
    angular = features["general_tolerances"]["angular_deg"]
    orient = ecc * math.tan(math.radians(angular))
    if not math.isclose(p["orient_band_mm"], orient, abs_tol=1e-4):
        raise ValueError(
            f"process.orient_band_mm {p['orient_band_mm']:g}, the recipe computes "
            f"{orient:.4f} (eccentricity × tan {angular:g}°)"
        )
    # The drill's full diameter runs to the bore's axis, so it breaks into
    # the bore; its point must stay off the far wall.
    if -tap_tip >= reach + dr / 2:
        raise ValueError("the #50's point reaches the bore's far wall")
    tap_xy = [_r(station), 0.0]
    cross_clear = max(0.0, cross_jaw_top) + CLEAR_MM

    for name, binding in (
        ("bore drill", "{{cad.envelope_z_mm}}"),
        ("tap drill", "{{cad.set_screw_tap_into_axis_mm}}"),
    ):
        stated = _op_with_cut(plan, name)[0]["hole_depth_mm"]
        if stated != binding:
            raise ValueError(
                f"'{name}' operation hole_depth_mm {stated!r}, not {binding}"
            )
    if _op_with_cut(plan, "bore drill")[0]["peck"] != "none":
        raise ValueError("'bore drill' peck is not none (L/D 1.5, one feed)")
    if _op_with_cut(plan, "tap drill")[0]["peck"] != {
        "step_mm": p["peck_50_mm"],
        "retract": "full",
    }:
        raise ValueError("'tap drill' peck is not process.peck_50_mm with full retract")
    speeds = {
        name: _speed(plan, name)
        for name in ("bore spot", "bore drill", "bore ream", "tap spot", "tap drill")
    }
    for name, key in (
        ("bore spot", "bore_spot_feed_per_min_mm"),
        ("bore drill", "drill_c_feed_per_min_mm"),
        ("bore ream", "ream_feed_per_min_mm"),
        ("tap spot", "tap_spot_feed_per_min_mm"),
        ("tap drill", "drill_50_feed_per_min_mm"),
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

    def drill(tool: str, dia: float, name: str, shape: str = "drill") -> dict[str, Any]:
        rpm, feed = speeds[name]
        spec = {
            "tool": tool,
            "dia": dia,
            "shape": shape,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
        }
        if shape == "drill":
            spec["tip_angle"] = (
                CENTRE_DRILL["point_deg"] if tool == "spot" else DRILL_POINT_DEG
            )
        else:
            spec["flutes"] = 6
        return spec

    # Frames (model point p -> axes · (p - origin)).
    frames = {
        "bore": {
            "origin": [0.0, -ecc, length],
            "axes": [[0, 1, 0], [-1, 0, 0], [0, 0, 1]],
        },
        "cross": {
            "origin": [0.0, -ecc - radius, 0.0],
            "axes": [[0, 0, 1], [-1, 0, 0], [0, -1, 0]],
        },
    }
    stock_bore = ((-radius, radius), (-radius, radius), (-length, 0.0))
    stock_cross = ((0.0, length), (-radius, radius), (-2 * radius, 0.0))
    jobs = [
        {
            **drill("spot", spot_dia, "bore spot"),
            "frame": "bore",
            "label": "bore spot",
            "stock": stock_bore,
            "ops": [
                [
                    "bore_spot",
                    "spot the bore",
                    _spot(bore_xy, 0.0, -bore_spot, CLEAR_MM),
                ]
            ],
        },
        {
            **drill("drill-c", dc, "bore drill"),
            "frame": "bore",
            "label": "bore drill",
            "stock": stock_bore,
            "ops": [
                [
                    "bore_drill",
                    "drill C through",
                    _pecked(bore_xy, 0.0, bore_tip, None, CLEAR_MM),
                ]
            ],
        },
        {
            **drill("reamer", dr, "bore ream", "endmill"),
            "frame": "bore",
            "label": "bore ream",
            "stock": stock_bore,
            "ops": [
                [
                    "bore_ream",
                    "ream the bore through",
                    _reamed(bore_xy, 0.0, ream_tip, CLEAR_MM),
                ]
            ],
        },
        {
            **drill("spot", spot_dia, "tap spot"),
            "frame": "cross",
            "label": "tap spot",
            "stock": stock_cross,
            "ops": [
                [
                    "tap_spot",
                    "spot the set-screw hole",
                    _spot(tap_xy, 0.0, -tap_spot, cross_clear),
                ]
            ],
        },
        {
            **drill("drill-50", d50, "tap drill"),
            "frame": "cross",
            "label": "tap drill",
            "stock": stock_cross,
            "ops": [
                [
                    "tap_drill",
                    "drill #50 into the bore",
                    _pecked(tap_xy, 0.0, tap_tip, p["peck_50_mm"], cross_clear),
                ]
            ],
        },
    ]

    # The tap stop: the tap guide loaded by the file's own M6 (its %msg
    # names the hole), Z to the machine's top in machine coordinates before
    # any XY, over the hole, M30: the controller ends Idle, so the operator
    # can jog the guide's point down into the wrench.
    manual = {
        "tap_stop": {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": "SPINDLE STAYS OFF. NEXT: 2-56 TAP IN THE SET-SCREW HOLE",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{tap_xy[0]:.3f} Y{tap_xy[1]:.3f}",
                "(2-56 TAP IN THE SET-SCREW HOLE. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND TO THE NOTED DRO Z, READ WITH THE POINT PUSHED HOME. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": tap_xy,
        }
    }

    # Keep-outs. CM01: the jaws on the O.D. at ±radius along Y, their tops
    # bore_jaw_top below Z0, across the jaws' width; the stacked parallels
    # under the disc against each jaw, their tops at the front face.
    jaw_x = (-p["vise_jaw_width_mm"] / 2, p["vise_jaw_width_mm"] / 2)
    par_x = (-PARALLEL_LENGTH_MM / 2, PARALLEL_LENGTH_MM / 2)
    bore_boxes = [
        _box("moving jaw", jaw_x, (-radius - JAW_DEPTH_MM, -radius), bore_jaw_top),
        _box("fixed jaw", jaw_x, (radius, radius + JAW_DEPTH_MM), bore_jaw_top),
        _box("moving-jaw parallels", par_x, (-radius, -gap / 2), -length),
        _box("fixed-jaw parallels", par_x, (gap / 2, radius), -length),
    ]
    # CM02: the jaws on the O.D.'s equator, their tops cross_jaw_top above
    # Z0; the 1 in parallels' inner edges under it, their tops at the axis
    # less the drop. The disc near the jaws' right ends (X0 its front face).
    par_top = -radius - drop
    cross_x = (
        -p["vise_jaw_width_mm"] + p["cross_jaw_end_mm"] + length,
        p["cross_jaw_end_mm"] + length,
    )
    cross_boxes = [
        _box("moving jaw", cross_x, (-radius - JAW_DEPTH_MM, -radius), cross_jaw_top),
        _box("fixed jaw", cross_x, (radius, radius + JAW_DEPTH_MM), cross_jaw_top),
        _box("moving-jaw parallel", cross_x, (-radius, -gap / 2), par_top),
        _box("fixed-jaw parallel", cross_x, (gap / 2, radius), par_top),
    ]

    t = numbers
    expect: list[list[Any]] = []

    def hole_checks(centres, bottom, radius_, boxes):
        return [
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": 0.0, "open_holes": centres}],
            ["vertical_below_top", {"z_top": 0.0}],
            ["air_feed", {"z_top": 0.0}],
            ["keep_out", {"radius": radius_, "boxes": boxes}],
        ]

    programs = {
        "CM01_bore": (
            0.0,
            [t["spot"], t["drill-c"], t["reamer"]],
            [
                [speeds["bore spot"][0]],
                [speeds["bore drill"][0]],
                [speeds["bore ream"][0]],
            ],
            bore_tip,
            [
                hole_checks([bore_xy], -bore_spot, spot_dia / 2, bore_boxes),
                hole_checks([bore_xy], bore_tip, dc / 2, bore_boxes),
                hole_checks([bore_xy], ream_tip, dr / 2, bore_boxes)
                + [["feed_out", {"z_top": 0.0}]],
            ],
        ),
        # Lying, the jaw tops stand above the disc: every tool change and
        # every move across to the hole stays above them.
        "CM02_set_screw": (
            max(0.0, cross_jaw_top),
            [t["spot"], t["drill-50"]],
            [[speeds["tap spot"][0]], [speeds["tap drill"][0]]],
            tap_tip,
            [
                hole_checks(
                    [tap_xy], -tap_spot, CENTRE_DRILL["pilot_mm"] / 2, cross_boxes
                ),
                hole_checks([tap_xy], tap_tip, d50 / 2, cross_boxes),
            ],
        ),
    }
    for name, (top, tools, rpms, deepest, sections) in programs.items():
        expect += [
            [name, "tool_changes", {"z_top": top, "tools": tools, "loads_first": True}],
            [name, "spindle", {"rpm": rpms}],
            [name, "pauses", {"z_top": top, "count": 0}],
            [name, "depth", {"z_min": _r(deepest)}],
        ]
        for k, checks in enumerate(sections):
            expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]
    expect += [
        [
            "CM03_set_screw_tap",
            "tap_stop",
            {"tool": t["tap-guide"], "at": tap_xy, "machine_top": MACHINE_Z_TOP_MM},
        ],
        ["CM03_set_screw_tap", "air_feed", {"z_top": 0.0}],
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
            doc, f"Cam {key}", ctx["step"], frame["origin"], frame["axes"]
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
