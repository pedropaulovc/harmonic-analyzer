"""FreeCAD CAM recipe for MHA-CH-13-TL-01, the rocker-strap sub-plate.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The plate's sizes come
from the feature export (planes, sawn ends, notches, pockets, counterbore,
holes), the same manifest the traveler's ``fence_plate`` adapter binds; the
blank, the edge stock, levels, widths of cut, hole depths and the holding
from ``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter
diameters, speeds and feeds from the shop (``shop/``). Every path is written here
(``rt.custom``): straight lines a recipe can state exactly. Typed here,
because neither record carries them: the #2 centre drill's catalogue geometry
(it sets the spot depth), the twist drills' 118° point, the machine's Z top
for the tap files' retract, the approach, safe and clearance heights, the
face overhang, the 1-2-3 blocks' footprint, the straps' lanes and the vise
jaws' depth (keep-out shapes only).

Route (plan text in ``plan.toml``): the 1/2 x 6 in 6061 bar is wider than the
vise opens, so SP01 splits the plate off a 13 in length on the table: the
front edge (rough and finish), a 1/2 in slot through behind the plate, the
back edge's finish, at two hand-set speeds (M0 stops). SP02 cuts the top in
one vise clamping: fence and stop tops faced, the plate top (Z0) milled round
them, the stop and fence walls finished, the hub counterbore plunged (1/2 in
end mill); the fence notches, clamp pockets and the hub tap's spot (1/8 in
end mill); spot, #43 and #21 drills. Then one short file per hole to tap,
SP03_tap_*: the tap guide loaded (M6), Z to the machine's top, over the
hole, M30; the operator taps by hand with the wrench under the tap guide.

The programs work in the plate's model frame, the strap programs' G54: X0
the stop face, Y0 the fence face (plate at -Y), Z0 the plate top.

Toolpath rules (owner rulings 2026-11-16): faces zigzag, plunges beside the
stock at the cutting feed, plunges into metal at the plan's plunge feed, real
G0 above the stock. Side cuts are conventional with the clockwise spindle:
material at +Y of the cutter feeds +X, at -Y feeds -X, at -X feeds +Y, at +X
feeds -Y, so pocket walls run clockwise.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ch_rocker_strap_tl_sub_plate"
COMMENT = "MHA-CH-13-TL-01 rocker-strap sub-plate"
# Programs in order, each listing its operation keys. A program whose keys are
# grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes and M0 stops.
#
# The holes are tapped by hand (FluidNC cannot rigid-tap; owner, Pedro,
# 2026-11-17), the T-handle wrench's centre hole on the spring point of the
# Fisher tap guide in the 1/2 in R8 collet (owner, Pedro, 2026-11-21: "use
# https://littlemachineshop.com/products/tap-guide-fisher?variant=45472915226805
# on r8 0.5 collet"), spindle off, the operator jogging Z down to push the
# point home. FluidNC, like Grbl, refuses jog commands while an M0
# holds the program (FluidNC wiki, "Single Block Mode": a pause "is a
# standard feed hold ... jogging disabled during pause";
# http://wiki.fluidnc.com/en/features/single_block_mode), so each tap stop
# is a file of its own that ends with M30 over its hole, the controller
# Idle: SP03_tap_clamp_1..4, then SP03_tap_hub.
TAP_HOLES = ("clamp_1", "clamp_2", "clamp_3", "clamp_4", "hub")
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("SP01_split_edges", (("front_edge",), ("slot",), ("back_edge",))),
    (
        "SP02_top",
        (
            ("tops", "floor", "walls"),
            ("counterbore",),
            ("notches", "pockets", "hub_spot"),
            ("spot",),
            ("drill_43",),
            ("drill_21",),
        ),
    ),
    # A literal (``_cam_programs.program_names`` reads it by AST): one per
    # TAP_HOLES entry, in order.
    ("SP03_tap_clamp_1", ("tap_clamp_1",)),
    ("SP03_tap_clamp_2", ("tap_clamp_2",)),
    ("SP03_tap_clamp_3", ("tap_clamp_3",)),
    ("SP03_tap_clamp_4", ("tap_clamp_4",)),
    ("SP03_tap_hub", ("tap_hub",)),
)
if tuple(name for name, _ops in PROGRAMS[2:]) != tuple(
    f"SP03_tap_{hole}" for hole in TAP_HOLES
):
    raise ValueError("PROGRAMS must list one SP03_tap_* file per TAP_HOLES entry")
# Every program loads its own first tool (M6, the tool setter): SP01 runs
# once per plate on whatever the mill last held, SP02 after a vise setup,
# each tap file before its retract (the tap guide).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (tools off the mill, the saw, the taps and the files, are
# not). SP02 runs all but the last; the tap files the last.
CAM_TOOLS = (
    "em-half",
    "em-eighth",
    "spot",
    "drill-43",
    "drill-21",
    "tap-guide",
)
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included: the shop record names
# the tool, not its geometry.
CENTRE_DRILL = {
    "body_mm": 3 / 16 * IN,
    "pilot_mm": 5 / 64 * IN,
    "pilot_length_mm": 5 / 64 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# A tap file's first motion: G53 G0 to machine Z0, the homed top. FluidNC
# sets an axis's machine position to its homing mpos_mm (default 0) after
# homing, and Z homes up (cad/config/shop-equipment/
# cnc.pm-30mv-controller: switches on all three axes); the owner (Pedro)
# confirmed it, answered in person 2026-11-21 (cnc rulings record): machine
# Z = 0 is the top of travel after homing.
MACHINE_Z_TOP_MM = 0.0
# Side and face passes start and finish with the cutter this far clear of
# the stock's ends, so every plunge and stepover link there is in the air.
APPROACH_MM = 2.54
# Faces reach this far past the fence's and stop's edges.
FACE_OVERHANG_MM = 0.5
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# SP01 keep-outs: a 1-2-3 block lying flat (2 in across Y, 3 in along X); a
# strap's lane, its half width and its reach past the clamp point, and its
# run out to its stud beyond the bar's end.
BLOCK_ACROSS_MM = 2 * IN
BLOCK_ALONG_MM = 3 * IN
STRAP_HALF_WIDTH_MM = 12.7
STRAP_NOSE_MM = 12.7
STRAP_RUN_MM = 4 * IN
# Nothing passes under a strap: its keep-out has no top.
STRAP_TOP_MM = 1000.0
# SP02 keep-outs: each vise jaw's depth outward from the plate's long edge.
JAW_DEPTH_MM = IN


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


def _setting(
    plan: dict[str, Any], shop: dict[str, Any], cut: str
) -> tuple[float, float]:
    """(rpm, mm/min) of the shop setting the operation holding ``cut`` names:
    its chip load × flutes × rpm, or its stated in/min feed. A cut that
    states its own rpm and feed must agree."""
    op, record_cut = _op_with_cut(plan, cut)
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    if "chip_load_mm_per_tooth" in record:
        feed = record["chip_load_mm_per_tooth"] * record["flutes"] * rpm
    else:
        value, unit = record["feed"].split()
        if unit != "in/min":
            raise ValueError(
                f"settings.{op['settings']}: feed {record['feed']!r} is not in/min"
            )
        feed = float(value) * IN
    for key, expected in (("rpm", rpm), ("feed_mm_min", feed)):
        if key in record_cut and not math.isclose(
            _cut(plan, cut, key), expected, abs_tol=1e-3
        ):
            raise ValueError(
                f"'{cut}' {key} {_cut(plan, cut, key):g} is not its setting's {expected:g}"
            )
    return rpm, feed


def _cut_feed(plan: dict[str, Any], name: str) -> tuple[float, float]:
    """(rpm, mm/min) of the plan's drill or plunge cut ``name``, which carries
    both; its rpm must be its operation's."""
    op_rpm = float(_op_with_cut(plan, name)[0]["rpm"])
    rpm = _cut(plan, name, "rpm")
    if rpm != op_rpm:
        raise ValueError(f"'{name}' at {rpm:g} rpm, its operation at {op_rpm:g}")
    return rpm, _cut(plan, name, "feed_mm_min")


def _plunge_feed(plan: dict[str, Any], name: str) -> tuple[float, float]:
    """(rpm, mm/min) of a plunge cut given per tooth: its operation's rpm ×
    the cut's flutes × its feed per tooth."""
    rpm = float(_op_with_cut(plan, name)[0]["rpm"])
    return rpm, rpm * _cut(plan, name, "flutes") * _cut(plan, name, "feed_per_tooth_mm")


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


def _levels(top: float, bottom: float, max_step: float) -> list[float]:
    """Equal step-down levels no deeper than ``max_step`` from ``top`` to
    ``bottom``, ``bottom`` last."""
    n = math.ceil((top - bottom) / max_step - 1e-9)
    return [top - (top - bottom) * (k + 1) / n for k in range(n - 1)] + [bottom]


def _steps(lo: float, hi: float, step: float) -> list[float]:
    """``lo`` to ``hi``, both included, in equal steps no longer than ``step``."""
    n = max(1, math.ceil((hi - lo) / step))
    return [lo + (hi - lo) * k / n for k in range(n + 1)]


def _layout(reach: float, woc: float, name: str) -> tuple[int, float]:
    """Equal passes, each taking at most the plan cut's radial width, over
    ``reach``: the plan must declare the width they post."""
    n = math.ceil(reach / woc - 1e-9)
    step = reach / n
    if not math.isclose(step, woc, abs_tol=1e-3):
        raise ValueError(
            f"'{name}' radial_woc_mm {woc:.4f}: {n} passes over {reach:.4f} take {step:.4f}; declare that width"
        )
    return n, step


def _r(value: float) -> float:
    """A coordinate as the post prints it (3 places)."""
    return round(value + 0.0, 3)


def _up(value: float) -> float:
    """``value`` rounded up to the post's 3 places (a cutter radius: the
    centre stays off the wall, never into it)."""
    return math.ceil(value * 1000 - 1e-6) / 1000


def _box(
    name: str, x: tuple[float, float], y: tuple[float, float], z_top: float
) -> dict[str, Any]:
    return {"name": name, "x": [x[0], x[1]], "y": [y[0], y[1]], "z_top": z_top}


def _complement(name, x, y, holes, z_top):
    """Boxes covering the rectangle ``x`` × ``y`` less the rectangles ``holes``
    (each ((x0, x1), (y0, y1))): strips between the holes' X edges, each cut
    round the holes it crosses."""
    xs = sorted({x[0], x[1], *(v for h in holes for v in h[0] if x[0] < v < x[1])})
    boxes = []
    for a, b in zip(xs, xs[1:]):
        crossing = sorted(h[1] for h in holes if h[0][0] < b and h[0][1] > a)
        lo = y[0]
        for h0, h1 in crossing:
            if h0 > lo:
                boxes.append(_box(f"{name} {len(boxes) + 1}", (a, b), (lo, h0), z_top))
            lo = max(lo, h1)
        if lo < y[1]:
            boxes.append(_box(f"{name} {len(boxes) + 1}", (a, b), (lo, y[1]), z_top))
    return boxes


def _rect_distance(rect, p) -> float:
    (x0, x1), (y0, y1) = rect
    return math.hypot(max(x0 - p[0], 0.0, p[0] - x1), max(y0 - p[1], 0.0, p[1] - y1))


def _region_points(region, centres, radius, step=0.5):
    """Grid points of ``region`` the cutter (``radius``) can reach with its
    centre in the rectangle ``centres``: the inside corners it rounds off are
    left out."""
    (x0, x1), (y0, y1) = region
    return [
        [_r(px), _r(py)]
        for px in _steps(x0, x1, step)
        for py in _steps(y0, y1, step)
        if _rect_distance(centres, (px, py)) <= radius - 0.01
    ]


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    f = features["features"]
    p = plan["parameters"]

    def plane(name: str, axis: str) -> float:
        record = f[name]["plane"]
        if record["axis"] != axis or record["frame"] != "model":
            raise ValueError(
                f"{name}: plane {record} is not a model-frame {axis} plane"
            )
        return record["value"]

    z0, z_face, z_under = (
        plane("plate_top", "z"),
        plane("faced_top", "z"),
        plane("underside", "z"),
    )
    x0, y0 = plane("stop_face", "x"), plane("fence_face", "y")
    y_front, y_back = plane("front_edge", "y"), plane("back_edge", "y")
    if (x0, y0, z0) != (0.0, 0.0, 0.0):
        raise ValueError(
            f"stop face X {x0}, fence face Y {y0}, plate top Z {z0}: the programs' G54 is the model frame's origin"
        )
    notch_l, notch_r = f["fence_notch_left"], f["fence_notch_right"]
    x_left, x_right = plane("left_end", "x"), plane("right_end", "x")
    if notch_r["x"][1] != x_right:
        raise ValueError(
            f"right notch ends at X {notch_r['x'][1]}, the right end is X {x_right}"
        )
    pockets = [
        f[k]
        for k in sorted(
            (k for k in f if re.fullmatch(r"clamp_pocket_\d+", k)),
            key=lambda k: int(k.rsplit("_", 1)[1]),
        )
    ]
    taps = [
        f[k]
        for k in sorted(
            (k for k in f if re.fullmatch(r"clamp_tap_\d+", k)),
            key=lambda k: int(k.rsplit("_", 1)[1]),
        )
    ]
    cbore, hub_tap = f["hub_counterbore"], f["hub_tap"]
    if len(pockets) != len(taps) or not pockets:
        raise ValueError(f"{len(pockets)} clamp pockets, {len(taps)} clamp taps")

    # The traveler binds every printed size and band through the fence_plate
    # adapter; the hole depths are the plan's (its drill ops print them).
    def agree(name: str, value: float) -> None:
        if not math.isclose(p[name], value, abs_tol=1e-4):
            raise ValueError(f"process.{name} {p[name]} is not the model's {value:.4f}")

    agree("clamp_hole_depth_mm", taps[0]["at"][2] - z_under)
    agree("hub_hole_depth_mm", hub_tap["at"][2] - z_under)

    names = {t["id"]: t["name"] for t in plan["tools"]}
    numbers = {
        t["id"]: n
        for n, t in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")
    d1 = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    d8 = _shop_tool(plan, shop, "em-eighth")["diameter_mm"]
    d43 = _shop_tool(plan, shop, "drill-43")["diameter_mm"]
    d21 = _shop_tool(plan, shop, "drill-21")["diameter_mm"]
    agree("half_cutter_dia_mm", d1)
    agree("eighth_cutter_dia_mm", d8)
    r1, r8 = d1 / 2, _up(d8 / 2)
    for name, hole, dia in (("clamp taps", taps[0], d43), ("hub tap", hub_tap, d21)):
        if not math.isclose(hole["drill_dia"], dia, abs_tol=1e-3):
            raise ValueError(
                f"{name}: drawn drill Ø{hole['drill_dia']}, the plan's drill Ø{dia}"
            )
    for name, feature in (
        ("notches", notch_l),
        *((f"pocket {k}", q) for k, q in enumerate(pockets, 1)),
    ):
        if feature["corner_radius_max"] < d8 / 2:
            raise ValueError(
                f"{name}: corners R{feature['corner_radius_max']} max, under the 1/8 in end mill's R{d8 / 2}"
            )
    if not cbore["dia"][0] <= d1 <= cbore["dia"][1]:
        raise ValueError(
            f"counterbore band {cbore['dia']}: the plunged {d1} mm end mill is outside it"
        )

    # Speeds and feeds.
    rpm_e, feed_e = _setting(plan, shop, "front edge rough")
    rpm_s, feed_s = _setting(plan, shop, "slot")
    rpm_b, feed_b = _setting(plan, shop, "back edge finish")
    rpm_1, feed_1 = _setting(plan, shop, "fence and stop tops")
    for name in ("front edge finish",):
        if _setting(plan, shop, name) != (rpm_e, feed_e):
            raise ValueError(
                f"'{name}' runs at another setting than 'front edge rough'"
            )
    for name in ("plate top", "stop and fence faces"):
        if _setting(plan, shop, name) != (rpm_1, feed_1):
            raise ValueError(
                f"'{name}' runs at another setting than 'fence and stop tops': one job, one speed"
            )
    rpm_cb, feed_cb = _cut_feed(plan, "counterbore")
    if rpm_cb != rpm_1:
        raise ValueError(
            f"'counterbore' at {rpm_cb:g} rpm, T1's tops at {rpm_1:g}: one speed for T1 in SP02"
        )
    rpm_8, feed_8 = _setting(plan, shop, "pocket centre lines")
    for name in ("left notch", "right notch", "pocket walls"):
        if _setting(plan, shop, name) != (rpm_8, feed_8):
            raise ValueError(
                f"'{name}' runs at another setting than 'pocket centre lines'"
            )
    plunges = {
        name: _plunge_feed(plan, name)
        for name in ("pocket plunges", "notch plunge", "hub tap spot")
    }
    if len(set(plunges.values())) != 1 or next(iter(plunges.values()))[0] != rpm_8:
        raise ValueError(
            f"T2's plunges {plunges} are not one feed at its {rpm_8:g} rpm"
        )
    plunge_8 = plunges["pocket plunges"][1]
    rpm_sp, feed_sp = _cut_feed(plan, "clamp spots")
    rpm_43, feed_43 = _cut_feed(plan, "clamp holes")
    rpm_21, feed_21 = _cut_feed(plan, "hub hole")

    # Blank and bar.
    b_max = p["blank_thickness_max_in"] * IN
    bar_top = z_under + b_max
    agree("bar_top_max_mm", b_max)  # the thickest bar's top above its underside
    saw = p["saw_length_tol_mm"]
    edge, rough, fin = p["edge_stock_mm"], p["edge_rough_woc_mm"], p["edge_finish_mm"]
    if not math.isclose(rough + fin, edge, abs_tol=1e-6):
        raise ValueError(
            f"edge rough {rough} + finish {fin} is not the edge stock {edge}"
        )
    bar_front = y_front - edge
    bar_back = bar_front + p["blank_width_in"] * IN
    tip1 = _r(z_under - p["cutter_tip_below_mm"])
    x_lo = _r(x_left - r1 - APPROACH_MM)
    x_hi = _r(x_right + saw + r1 + APPROACH_MM)
    x_mid = _r((x_left + x_right) / 2)

    # ---- SP01: the bar on the table ------------------------------------------
    clear_a, safe_a = _r(bar_top + CLEAR_MM), _r(bar_top + SAFE_MM)
    edge_levels = [_r(z) for z in _levels(bar_top, tip1, p["side_max_stepdown_mm"])]
    slot_levels = [_r(z) for z in _levels(bar_top, tip1, p["slot_step_mm"])]
    raw_front = _r(bar_front - r1)
    y_rough, y_final = _r(raw_front + rough), _r(y_front - r1)
    slot_y = _r(y_back + fin + r1)
    y_back_pass = _r(y_back + r1)
    rest_front = slot_y + r1
    if bar_back - rest_front < BLOCK_ACROSS_MM:
        raise ValueError(
            f"the bar's remainder, {bar_back - rest_front:.2f} mm, is narrower than its 1-2-3 blocks"
        )
    # Front edge: one-way +X passes (the plate at +Y), rough then finish, each
    # at both levels; plunges beside the left end; returns at clearance.
    front = [f"G0 Z{clear_a:.3f}"]
    for y in (y_rough, y_final):
        for z in edge_levels:
            front += [
                f"G0 X{x_lo:.3f} Y{y:.3f}",
                f"G0 Z{safe_a:.3f}",
                f"G1 Z{z:.3f} F{{feed}}",
                f"G1 X{x_hi:.3f} F{{feed}}",
                f"G0 Z{clear_a:.3f}",
            ]
    # Slot: full width, alternate directions, each level entered beside the
    # bar's end the last one left at. The move across to it crosses the bar
    # at mid-length, clear of the straps.
    slot = [
        f"G0 Z{clear_a:.3f}",
        f"G0 X{x_mid:.3f}",
        f"G0 Y{slot_y:.3f}",
        f"G0 X{x_lo:.3f}",
        f"G0 Z{safe_a:.3f}",
    ]
    for k, z in enumerate(slot_levels):
        slot += [
            f"G1 Z{z:.3f} F{{feed}}",
            f"G1 X{(x_hi if k % 2 == 0 else x_lo):.3f} F{{feed}}",
        ]
    slot.append(f"G0 Z{clear_a:.3f}")
    # Back edge: one-way -X passes (the plate at -Y), beside the right end.
    back = [f"G0 Z{clear_a:.3f}"]
    for z in edge_levels:
        back += [
            f"G0 X{x_hi:.3f} Y{y_back_pass:.3f}",
            f"G0 Z{safe_a:.3f}",
            f"G1 Z{z:.3f} F{{feed}}",
            f"G1 X{x_lo:.3f} F{{feed}}",
            f"G0 Z{clear_a:.3f}",
        ]
    stock_a = [[x_left, x_right], [bar_front, bar_back], [z_under, bar_top]]
    em_half = {
        "tool": "em-half",
        "dia": d1,
        "shape": "endmill",
        "flutes": int(_cut(plan, "slot", "flutes")),
    }
    jobs = [
        {
            **em_half,
            "label": "front edge",
            "rpm": rpm_e,
            "feed": feed_e,
            "plunge": feed_e,
            "stock": stock_a,
            "ops": [["front_edge", "front edge", front]],
        },
        {
            **em_half,
            "label": "slot",
            "rpm": rpm_s,
            "feed": feed_s,
            "plunge": feed_s,
            "stock": stock_a,
            "ops": [["slot", "slot", slot]],
        },
        {
            **em_half,
            "label": "back edge",
            "rpm": rpm_b,
            "feed": feed_b,
            "plunge": feed_b,
            "stock": stock_a,
            "ops": [["back_edge", "back edge", back]],
        },
    ]
    plate_mid_y = (y_front + y_back) / 2
    rest_mid_y = (rest_front + bar_back) / 2
    strap_l = x_left + p["strap_inset_mm"]
    strap_r = x_left + p["strap_right_x_mm"]
    block_l = (strap_l - BLOCK_ALONG_MM / 2, strap_l + BLOCK_ALONG_MM / 2)
    block_r = (strap_r - BLOCK_ALONG_MM / 2, strap_r + BLOCK_ALONG_MM / 2)
    sp01_boxes = [
        _box("plate", (x_left, x_right), (y_front, y_back), bar_top),
        _box("bar remainder", (x_left, x_right), (rest_front, bar_back), bar_top),
    ]
    for label, mid in (("plate", plate_mid_y), ("remainder", rest_mid_y)):
        across = (mid - BLOCK_ACROSS_MM / 2, mid + BLOCK_ACROSS_MM / 2)
        lane = (mid - STRAP_HALF_WIDTH_MM, mid + STRAP_HALF_WIDTH_MM)
        sp01_boxes += [
            _box(f"{label} block left", block_l, across, z_under),
            _box(f"{label} block right", block_r, across, z_under),
            _box(
                f"{label} strap left",
                (x_left - STRAP_RUN_MM, strap_l + STRAP_NOSE_MM),
                lane,
                STRAP_TOP_MM,
            ),
            _box(
                f"{label} strap right",
                (strap_r - STRAP_NOSE_MM, x_right + saw + STRAP_RUN_MM),
                lane,
                STRAP_TOP_MM,
            ),
        ]
    sp1 = PROGRAMS[0][0]
    span = (x_right - x_left) / 2
    expect: list[list[Any]] = [
        [sp1, "spindle", {"rpm": [[rpm_e, rpm_s, rpm_b]]}],
        [
            sp1,
            "tool_changes",
            {"z_top": bar_top, "tools": [numbers["em-half"]], "loads_first": True},
        ],
        [sp1, "pauses", {"z_top": bar_top, "count": 2}],
        [sp1, "depth", {"z_min": tip1}],
        [sp1, "rapids_clear", {"z_top": bar_top}],
        [sp1, "air_feed", {"z_top": bar_top}],
        [
            sp1,
            "side_passes",
            {
                "axis": "Y",
                "final": y_final,
                "raw": raw_front,
                "max_step": rough,
                "direction": 1.0,
                "span": span,
                "below_z": bar_top,
                "finish": fin,
                "max_stepdown": p["side_max_stepdown_mm"],
            },
        ],
        # The back edge's raw face is the slot's wall: raw sits just inside the
        # slot's centre line so its passes (both ways) are not counted.
        [
            sp1,
            "side_passes",
            {
                "axis": "Y",
                "final": y_back_pass,
                "raw": _r(slot_y - 0.005),
                "max_step": fin,
                "direction": -1.0,
                "span": span,
                "below_z": bar_top,
                "finish": fin,
                "max_stepdown": p["side_max_stepdown_mm"],
            },
        ],
        [
            sp1,
            "cleared",
            {
                "points": [[_r(x), slot_y] for x in _steps(x_left, x_right, 5.0)],
                "radius": r1,
                "z": tip1,
            },
        ],
        [sp1, "keep_out", {"radius": r1, "boxes": sp01_boxes}],
    ]

    # ---- SP02: the plate in the vise -------------------------------------------
    oh = FACE_OVERHANG_MM
    wall_fin = p["wall_finish_mm"]
    clear_b, safe_b = _r(bar_top + CLEAR_MM), _r(bar_top + SAFE_MM)
    x_lo2 = x_lo
    y_lo2 = _r(y_front - r1 - APPROACH_MM)
    if (
        bar_top - z_face > p["face_depth_max_mm"] + 1e-6
        or bar_top - z0 > p["floor_depth_max_mm"] + 1e-6
    ):
        raise ValueError(
            f"a {b_max:.3f} mm bar leaves more than the plan's face or floor depth over the tops or Z0"
        )
    face_woc = _cut(plan, "fence and stop tops", "radial_woc_mm")
    n_f, s_f = _layout(y_back - y0 + 2 * oh, face_woc, "fence and stop tops")
    fence_ys = [_r(y_back + oh + r1 - s_f * (k + 1)) for k in range(n_f)]
    n_s, s_s = _layout(x0 - x_left + 2 * oh, face_woc, "fence and stop tops")
    stop_xs = [_r(x_left - oh - r1 + s_s * (k + 1)) for k in range(n_s)]
    tops = [
        f"G0 Z{clear_b:.3f}",
        f"G0 X{x_lo2:.3f} Y{fence_ys[0]:.3f}",
        f"G0 Z{safe_b:.3f}",
        f"G1 Z{z_face:.3f} F{{feed}}",
    ]
    for k, y in enumerate(fence_ys):
        if k:
            tops.append(f"G1 Y{y:.3f}")
        tops.append(f"G1 X{(x_hi if k % 2 == 0 else x_lo2):.3f}")
    tops += [
        f"G0 Z{clear_b:.3f}",
        f"G0 X{stop_xs[0]:.3f} Y{y_lo2:.3f}",
        f"G0 Z{safe_b:.3f}",
        f"G1 Z{z_face:.3f} F{{feed}}",
    ]
    for k, x in enumerate(stop_xs):
        if k:
            tops.append(f"G1 X{x:.3f}")
        tops.append(f"G1 Y{(y0 if k % 2 == 0 else y_lo2):.3f}")
    tops.append(f"G0 Z{clear_b:.3f}")
    # The plate top: zigzag from the front edge back, the first pass -X in
    # from the right end; the last must run -X so the fence wall's +X pass
    # after it alternates.
    floor_woc = _cut(plan, "plate top", "radial_woc_mm")
    n_fl, s_fl = _layout(y0 - y_front + oh - wall_fin, floor_woc, "plate top")
    if n_fl % 2 == 0:
        raise ValueError(
            f"'plate top' posts {n_fl} passes: an even count ends +X, beside the fence wall's +X pass"
        )
    last_floor = y0 - wall_fin - r1
    floor_ys = [_r(last_floor - s_fl * (n_fl - 1 - k)) for k in range(n_fl)]
    x_floor = _r(x0 + wall_fin + r1)
    floor = [
        f"G0 Z{clear_b:.3f}",
        f"G0 X{x_hi:.3f} Y{floor_ys[0]:.3f}",
        f"G0 Z{safe_b:.3f}",
        f"G1 Z{z0:.3f} F{{feed}}",
    ]
    for k, y in enumerate(floor_ys):
        if k:
            floor.append(f"G1 Y{y:.3f}")
        floor.append(f"G1 X{(x_floor if k % 2 == 0 else x_hi):.3f}")
    floor.append(f"G0 Z{clear_b:.3f}")
    # Walls: the stop face +Y (material at -X), round the corner onto the
    # fence face +X (material at +Y), at Z0 in one level.
    x_wall, y_wall = _r(x0 + r1), _r(y0 - r1)
    walls = [
        f"G0 X{x_wall:.3f} Y{y_lo2:.3f}",
        f"G0 Z{safe_b:.3f}",
        f"G1 Z{z0:.3f} F{{feed}}",
        f"G1 Y{y_wall:.3f}",
        f"G1 X{x_hi:.3f}",
        f"G0 Z{clear_b:.3f}",
    ]
    hub = (_r(cbore["at"][0]), _r(cbore["at"][1]))
    cb_floor = _r(cbore["floor_z"])
    counterbore = [
        f"G0 Z{clear_b:.3f}",
        f"G0 X{hub[0]:.3f} Y{hub[1]:.3f}",
        f"G0 Z{safe_b:.3f}",
        f"G1 Z{cb_floor:.3f} F{{plunge}}",
        f"G0 Z{clear_b:.3f}",
    ]
    stock_b = [[x_left, x_right], [y_front, y_back], [z_under, bar_top]]

    # T2, the 1/8 in end mill. Its stock top is still the bar's: T1 leaves a
    # corner of it standing round X0 Y0, which the left notch's passes take.
    notch_back = y0 + sum(notch_l["depth"]) / 2
    yb = _r(notch_back - r8)
    yi = y0
    nl_end = notch_l["x"][1]
    nr_start = notch_r["x"][0]
    xw, xe, xs = _r(x0 + r8), _r(nl_end - r8), _r(nr_start + r8)
    y_start = _r(y0 - r1 - r8)
    x_hi8 = _r(x_right + saw + r8 + APPROACH_MM)
    notch_levels = [
        _r(z) for z in _levels(bar_top, z0, _cut(plan, "left notch", "axial_doc_mm"))
    ]
    notches = [f"G0 Z{clear_b:.3f}"]
    for z in notch_levels:
        # Left: entered beside the stock in T1's corner, up the stop face (+Y),
        # along the notch's back wall (+X), down its end wall (-Y); then the
        # strip along the fence face (+X).
        notches += [
            f"G0 X{xw:.3f} Y{y_start:.3f}",
            f"G0 Z{safe_b:.3f}",
            f"G1 Z{z:.3f} F{{feed}}",
            f"G1 Y{yb:.3f}",
            f"G1 X{xe:.3f}",
            f"G1 Y{yi:.3f}",
            f"G0 Z{safe_b:.3f}",
            f"G0 X{xw:.3f} Y{yi:.3f}",
            f"G1 Z{z:.3f} F{{feed}}",
            f"G1 X{xe:.3f}",
            f"G0 Z{safe_b:.3f}",
        ]
    for z in notch_levels:
        # Right: plunged at the notch's end (into metal), up its end wall
        # (+Y, material at -X), out along the back wall (+X); then the strip
        # along the fence face (+X) out past the plate's end.
        notches += [
            f"G0 X{xs:.3f} Y{yi:.3f}",
            f"G0 Z{safe_b:.3f}",
            f"G1 Z{z:.3f} F{{plunge}}",
            f"G1 Y{yb:.3f} F{{feed}}",
            f"G1 X{x_hi8:.3f}",
            f"G0 Z{safe_b:.3f}",
            f"G0 X{xs:.3f} Y{yi:.3f}",
            f"G1 Z{z:.3f} F{{feed}}",
            f"G1 X{x_hi8:.3f}",
            f"G0 Z{safe_b:.3f}",
        ]
    notches.append(f"G0 Z{clear_b:.3f}")
    # Pockets: each level plunged at the centre, the centre line both ways,
    # then the walls clockwise round it (conventional).
    pocket_lines = [f"G0 Z{clear_b:.3f}"]
    pocket_rects, pocket_points = [], []
    pocket_floor = _r(pockets[0]["floor_z"])
    pocket_levels = [
        _r(z)
        for z in _levels(z0, pocket_floor, _cut(plan, "pocket walls", "axial_doc_mm"))
    ]
    for q in pockets:
        s = q["centre_x"]
        back_y, near_y = q["y_walls"]
        length = sum(q["length"]) / 2
        dx = _r(length / 2 - r8)
        yb_p, yn_p, yc = _r(back_y + r8), _r(near_y - r8), _r((back_y + near_y) / 2)
        if (
            yc - d8 / 2 > yb_p + d8 / 2 + 1e-3
            or yc + d8 / 2 < yn_p - d8 / 2 - 1e-3
            or dx <= 0
        ):
            raise ValueError(
                f"pocket at X {s}: its walls and centre line leave stock between them"
            )
        pocket_lines += [f"G0 X{_r(s):.3f} Y{yc:.3f}", f"G0 Z{safe_b:.3f}"]
        for z in pocket_levels:
            pocket_lines += [
                f"G1 Z{z:.3f} F{{plunge}}",
                f"G1 X{_r(s - dx):.3f} F{{feed}}",
                f"G1 X{_r(s + dx):.3f}",
                f"G1 Y{yb_p:.3f}",
                f"G1 X{_r(s - dx):.3f}",
                f"G1 Y{yn_p:.3f}",
                f"G1 X{_r(s + dx):.3f}",
                f"G1 Y{yc:.3f}",
                f"G1 X{_r(s):.3f}",
            ]
        pocket_lines.append(f"G0 Z{clear_b:.3f}")
        rect = ((s - length / 2, s + length / 2), (back_y, near_y))
        pocket_rects.append(rect)
        pocket_points += _region_points(rect, ((s - dx, s + dx), (yb_p, yn_p)), d8 / 2)
    hub_spot_z = _r(cb_floor - p["hub_spot_depth_mm"])
    hub_spot = [
        f"G0 X{hub[0]:.3f} Y{hub[1]:.3f}",
        f"G0 Z{safe_b:.3f}",
        f"G1 Z{hub_spot_z:.3f} F{{plunge}}",
        f"G0 Z{clear_b:.3f}",
    ]

    # Holes: R plane SAFE_MM over the plate top, moves at the faced top's
    # clearance; tips past the underside by the plan's breakthrough.
    clear_h, r_plane = _r(z_face + CLEAR_MM), _r(z0 + SAFE_MM)
    tap_xy = [(_r(t["at"][0]), _r(t["at"][1])) for t in taps]
    tap_top = taps[0]["at"][2]
    pilot, body = CENTRE_DRILL["pilot_mm"], CENTRE_DRILL["body_mm"]
    if not pilot < p["spot_dia_mm"] < body:
        raise ValueError(
            f"spot Ø{p['spot_dia_mm']} is not on the centre drill's countersink"
        )
    spot_depth = CENTRE_DRILL["pilot_length_mm"] + (
        p["spot_dia_mm"] - pilot
    ) / 2 / math.tan(math.radians(CENTRE_DRILL["point_deg"] / 2))
    spot_z = _r(tap_top - spot_depth)
    point = math.tan(math.radians(DRILL_POINT_DEG / 2))
    tip43 = _r(z_under - p["drill_breakthrough_mm"] - d43 / 2 / point)
    tip21 = _r(z_under - p["drill_breakthrough_mm"] - d21 / 2 / point)
    if not math.isclose(tip21 - z_under, p["drill_tip_below_mm"], abs_tol=1e-3):
        raise ValueError(
            f"the #21 tip is {tip21 - z_under:.3f} from the underside, process.drill_tip_below_mm {p['drill_tip_below_mm']}"
        )

    def spot_holes():
        lines = [f"G0 Z{clear_h:.3f}"]
        for x, y in tap_xy:
            lines += [
                f"G0 X{x:.3f} Y{y:.3f}",
                f"G0 Z{r_plane:.3f}",
                f"G1 Z{spot_z:.3f} F{{feed}}",
                f"G0 Z{r_plane:.3f}",
                f"G0 Z{clear_h:.3f}",
            ]
        return lines

    # #43 pecks of the plan's step from the pocket floor, full retract to R.
    peck = p["peck_43_mm"]
    pecks = []
    depth = tap_top
    while depth - peck > tip43 + 1e-6:
        depth -= peck
        pecks.append(_r(depth))
    pecks.append(tip43)
    drill_43 = [f"G0 Z{clear_h:.3f}"]
    for x, y in tap_xy:
        drill_43 += [f"G0 X{x:.3f} Y{y:.3f}", f"G0 Z{r_plane:.3f}"]
        previous = None
        for z in pecks:
            if previous is not None:
                drill_43 += [
                    f"G0 Z{r_plane:.3f}",
                    f"G0 Z{_r(previous + PECK_REENTRY_MM):.3f}",
                ]
            drill_43.append(f"G1 Z{z:.3f} F{{feed}}")
            previous = z
        drill_43 += [f"G0 Z{r_plane:.3f}", f"G0 Z{clear_h:.3f}"]
    drill_21 = [
        f"G0 Z{clear_h:.3f}",
        f"G0 X{hub[0]:.3f} Y{hub[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{tip21:.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear_h:.3f}",
    ]

    # One file per hole to tap (TAP_HOLES): the tap guide loaded by the
    # file's own M6 (its %msg names the hole and tap), Z to the machine's top
    # in machine coordinates before any XY (the operator left Z jogged down
    # on the last hole), over the hole, M30: the controller ends Idle, so the
    # operator can jog the guide's point down into the wrench.
    tap_holes = {
        **{
            f"clamp_{k}": ("4-40", f"CLAMP HOLE {k}", xy)
            for k, xy in enumerate(tap_xy, 1)
        },
        "hub": ("10-32", "THE HUB HOLE", hub),
    }
    if tuple(tap_holes) != TAP_HOLES:
        raise ValueError(f"holes to tap {tuple(tap_holes)}, programs {TAP_HOLES}")
    tap_files = {}
    for key, (thread, what, (x, y)) in tap_holes.items():
        tap_files[f"tap_{key}"] = {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": f"SPINDLE STAYS OFF. NEXT: {thread} TAP IN {what}",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{x:.3f} Y{y:.3f}",
                f"({thread} TAP IN {what}. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND THROUGH, THE POINT FOLLOWING THE TAP. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": [x, y],
        }

    em_eighth = {
        "tool": "em-eighth",
        "dia": d8,
        "shape": "endmill",
        "flutes": int(_cut(plan, "pocket walls", "flutes")),
    }
    jobs += [
        {
            **em_half,
            "label": "top",
            "rpm": rpm_1,
            "feed": feed_1,
            "plunge": feed_1,
            "stock": stock_b,
            "ops": [
                ["tops", "fence and stop tops", tops],
                ["floor", "plate top", floor],
                ["walls", "stop and fence faces", walls],
            ],
        },
        {
            **em_half,
            "label": "counterbore",
            "rpm": rpm_cb,
            "feed": feed_cb,
            "plunge": feed_cb,
            "stock": stock_b,
            "ops": [["counterbore", "counterbore", counterbore]],
        },
        {
            **em_eighth,
            "label": "notches and pockets",
            "rpm": rpm_8,
            "feed": feed_8,
            "plunge": plunge_8,
            "stock": stock_b,
            "ops": [
                ["notches", "fence notches", notches],
                ["pockets", "clamp pockets", pocket_lines],
                ["hub_spot", "hub tap spot", hub_spot],
            ],
        },
        {
            "tool": "spot",
            "dia": body,
            "shape": "drill",
            "tip_angle": CENTRE_DRILL["point_deg"],
            "label": "spot",
            "rpm": rpm_sp,
            "feed": feed_sp,
            "plunge": feed_sp,
            "stock": stock_b,
            "ops": [["spot", "spot clamp holes", spot_holes()]],
        },
        {
            "tool": "drill-43",
            "dia": d43,
            "shape": "drill",
            "tip_angle": DRILL_POINT_DEG,
            "label": "drill #43",
            "rpm": rpm_43,
            "feed": feed_43,
            "plunge": feed_43,
            "stock": stock_b,
            "ops": [["drill_43", "drill clamp holes", drill_43]],
        },
        {
            "tool": "drill-21",
            "dia": d21,
            "shape": "drill",
            "tip_angle": DRILL_POINT_DEG,
            "label": "drill #21",
            "rpm": rpm_21,
            "feed": feed_21,
            "plunge": feed_21,
            "stock": stock_b,
            "ops": [["drill_21", "drill hub hole", drill_21]],
        },
    ]

    # SP02's checks, one tool section each (@0 T1 ... @6 T7).
    jaw_x = (
        x_left + p["plate_overhang_mm"],
        x_left + p["plate_overhang_mm"] + p["vise_jaw_width_mm"],
    )
    jaw_top = z_under + p["vise_jaw_height_mm"] - p["parallel_height_mm"]
    jaws = [
        _box("moving jaw", jaw_x, (y_front - JAW_DEPTH_MM, y_front), jaw_top),
        _box("fixed jaw", jaw_x, (y_back, y_back + JAW_DEPTH_MM), jaw_top),
    ]
    stop_box = _box("end stop", (x_left, x0), (y_front, y0), z_face)
    t1_boxes = [_box("fence", (x_left, x_right), (y0, y_back), z_face), stop_box, *jaws]
    hub_square = (
        (hub[0] - d1 / 2, hub[0] + d1 / 2),
        (hub[1] - d1 / 2, hub[1] + d1 / 2),
    )
    t2_boxes = [
        _box("fence", (nl_end, nr_start), (y0, y_back), z_face),
        _box("fence behind the left notch", (x0, nl_end), (notch_back, y_back), z_face),
        _box(
            "fence behind the right notch",
            (nr_start, x_right),
            (notch_back, y_back),
            z_face,
        ),
        _box("end stop", (x_left, x0), (y_front, y_back), z_face),
        *_complement(
            "plate top", (x0, x_right), (y_front, y0), [*pocket_rects, hub_square], z0
        ),
        *jaws,
    ]
    drill_boxes = [
        _box("fence", (x_left, x_right), (y0, y_back), z_face),
        stop_box,
        *jaws,
    ]
    floor_points = [
        [_r(x), _r(y)]
        for x in _steps(x0 + r1, x_right, 5.0)
        for y in _steps(y_front, y0 - r1, 5.0)
    ]
    floor_points += [[x0, _r(y)] for y in _steps(y_front, y0 - r1, 5.0)] + [
        [_r(x), y0] for x in _steps(x0 + r1, x_right, 5.0)
    ]
    top_points = [
        [_r(x), _r(y)]
        for x in _steps(x_left, x_right, 5.0)
        for y in _steps(y0, y_back, 2.0)
    ]
    top_points += [
        [_r(x), _r(y)]
        for x in _steps(x_left, x0, 2.0)
        for y in _steps(y_front, y0, 5.0)
    ]
    notch_points = _region_points(
        ((x0, nl_end), (y0, notch_back)), ((xw, xe), (y_start, yb)), d8 / 2
    )
    notch_points += _region_points(
        ((nr_start, x_right), (y0, notch_back)), ((xs, x_hi8), (yi, yb)), d8 / 2
    )
    sp2 = PROGRAMS[1][0]
    tools2 = [numbers[t] for t in CAM_TOOLS if t != "tap-guide"]

    def hole_checks(centres, bottom, radius):
        return [
            ["holes", {"centres": centres, "z_bottom": bottom}],
            ["rapids_clear", {"z_top": z0, "open_holes": centres}],
            ["vertical_below_top", {"z_top": z0}],
            ["air_feed", {"z_top": z0}],
            ["keep_out", {"radius": radius, "boxes": drill_boxes}],
        ]

    sections = [
        [
            ["depth", {"z_min": cb_floor}],
            ["rapids_clear", {"z_top": bar_top}],
            ["air_feed", {"z_top": bar_top}],
            [
                "face_passes",
                {
                    "z": z_face,
                    "y": [y0, y_back],
                    "max_engagement": face_woc,
                    "radius": r1,
                    "span": span,
                    "overhang": oh,
                },
            ],
            [
                "face_passes",
                {
                    "z": z0,
                    "y": [y_front, y0],
                    "max_engagement": floor_woc,
                    "radius": r1,
                    "span": span,
                },
            ],
            [
                "side_passes",
                {
                    "axis": "X",
                    "final": x_wall,
                    "raw": x_floor,
                    "max_step": wall_fin,
                    "direction": 1.0,
                    "span": (y0 - y_front) / 2,
                    "below_z": bar_top,
                    "finish": wall_fin,
                },
            ],
            ["cleared", {"points": top_points, "radius": r1, "z": z_face}],
            ["cleared", {"points": floor_points, "radius": r1, "z": z0}],
            ["keep_out", {"radius": r1, "boxes": t1_boxes}],
        ],
        [
            ["depth", {"z_min": hub_spot_z}],
            ["rapids_clear", {"z_top": bar_top}],
            ["air_feed", {"z_top": bar_top}],
            ["cleared", {"points": notch_points, "radius": d8 / 2, "z": z0}],
            ["cleared", {"points": pocket_points, "radius": d8 / 2, "z": pocket_floor}],
            ["keep_out", {"radius": d8 / 2, "boxes": t2_boxes}],
        ],
        hole_checks(tap_xy, spot_z, body / 2),
        hole_checks(tap_xy, tip43, d43 / 2),
        hole_checks([hub], tip21, d21 / 2),
    ]
    expect += [
        [sp2, "tool_changes", {"z_top": bar_top, "tools": tools2, "loads_first": True}],
        [
            sp2,
            "spindle",
            {"rpm": [[rpm_1], [rpm_8], [rpm_sp], [rpm_43], [rpm_21]]},
        ],
        [sp2, "pauses", {"z_top": z0, "count": 0}],
        [sp2, "depth", {"z_min": tip21}],
    ]
    for key, section in tap_files.items():
        name = f"SP03_{key}"
        expect += [
            [
                name,
                "tap_stop",
                {
                    "tool": numbers["tap-guide"],
                    "at": section["at"],
                    "machine_top": MACHINE_Z_TOP_MM,
                },
            ],
            [name, "air_feed", {"z_top": z0}],
        ]
    for k, checks in enumerate(sections):
        expect += [[f"{sp2}@{k}", check, kwargs] for check, kwargs in checks]

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "model": {"origin": [0.0, 0.0, 0.0], "axes": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        "bbox": [[x_left, x_right], [y_front, y_back], [z_under, z_face]],
        "names": names,
        "numbers": numbers,
        "jobs": jobs,
        "manual": tap_files,
        "expect": expect,
    }


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    return [(program, check, kwargs) for program, check, kwargs in ctx["expect"]]


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job per
    section; returns {"ops": {operation key: operation or manual section}}."""
    doc = rt.document()
    plate = rt.import_step(
        doc, "Plate", ctx["step"], ctx["model"]["origin"], ctx["model"]["axes"]
    )
    bb = plate.Shape.BoundBox
    got = ((bb.XMin, bb.XMax), (bb.YMin, bb.YMax), (bb.ZMin, bb.ZMax))
    if any(
        abs(a - e) > 0.01
        for pair, expected in zip(got, ctx["bbox"])
        for a, e in zip(pair, expected)
    ):
        raise RuntimeError(f"the STEP spans {got}, the features {ctx['bbox']}")
    ops: dict[str, Any] = {}
    for section in ctx["jobs"]:
        target = rt.job(doc, section["label"], [plate], section["stock"])
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
    """What the as-machined report needs: the 13 in length of the 1/2 x 6 in
    bar SP01 holds on the table (its stock box: the sawn ends, the bar's
    as-received front edge edge_stock_mm outside the plate's front edge and
    its 6 in width behind it), in the model frame both mill programs run in
    (``build()`` imports the STEP at the identity ``ctx["model"]``; the G54
    of SP01 and SP02 is the model origin). The band is the bar's miked
    thickness, .495-.505 (the programs are posted for the thickest), its
    nominal the bar's marked .500; the underside lies on the blocks and the
    parallels, so it stays put and a thicker bar stands higher. The sawn
    length is taken at its nominal: the ends stay as sawn. The slot frees
    the bar's remainder behind the plate (an offcut). The SP03 files are the
    hand taps under the tap guide (no frame). Expected: every inside corner
    of the fence notches and clamp pockets drawn at the sheet's R.070 MAX
    and cut at the 1/8 in end mill's R.0625, a corner gouge no deeper than
    the two radii's gap along the corner's bisector to the nearer wall."""
    p = inputs.plan["parameters"]
    f = inputs.features["features"]
    thickness = {
        "nominal": p["blank_thickness_in"] * IN,
        "min": p["blank_thickness_min_in"] * IN,
        "max": p["blank_thickness_max_in"] * IN,
    }
    (x0, _x1), y, (z0, _z1) = next(
        job["stock"] for job in ctx["jobs"] if job["ops"][0][0] == "front_edge"
    )
    route = [[name, "model" if name in ("SP01_split_edges", "SP02_top") else None] for name, _ops in PROGRAMS]
    cutter = next(job["dia"] for job in ctx["jobs"] if job["tool"] == "em-eighth") / 2
    reason = (
        "inside corners drawn R.070 MAX, cut at the 1/8 in end mill's R.0625"
        " (owner ruling 2026-11-17; plan Setup 2: corners R.0625, the cutter's)"
    )

    def corners(name: str, within: list[list[float]], feature: dict[str, Any]) -> dict[str, Any]:
        # A drawn fillet R and the cutter's r leave (R - r)(√2 - 1) at most.
        return {
            "name": name,
            "kind": "gouge",
            "within": within,
            "reason": reason,
            "max_mm": (feature["corner_radius_max"] - cutter) * (math.sqrt(2) - 1),
        }

    top, faced = f["plate_top"]["plane"]["value"], f["faced_top"]["plane"]["value"]
    fence = f["fence_face"]["plane"]["value"]
    expected = []
    for key in ("fence_notch_left", "fence_notch_right"):
        n = f[key]
        xs = [min(n["x"][0], n["end_x"][0]), max(n["x"][1], n["end_x"][1])]
        expected.append(corners(f"{key} corners", [xs, [fence, fence + n["depth"][1]], [n["floor_z"], faced]], n))
    for key in sorted((k for k in f if re.fullmatch(r"clamp_pocket_\d+", k)), key=lambda k: int(k.rsplit("_", 1)[1])):
        q = f[key]
        half = q["length"][1] / 2
        within = [[q["centre_x"] - half, q["centre_x"] + half], list(q["y_walls"]), [q["floor_z"], top]]
        expected.append(corners(f"{key} corners", within, q))
    return {
        "parts": {
            "": {
                "blank": {
                    "frame": "model",
                    "box": [[x0, x0 + p["blank_length_in"] * IN], list(y), [z0, z0 + thickness["nominal"]]],
                    "length": {"axis": "z", "keep": "min", "mm": thickness},
                },
                "route": route,
                "expected": expected,
            }
        },
        "frames": {"model": ctx["model"]},
        "skip": {},
        "notes": ["the SP03 files tap by hand under the tap guide: the report cuts no thread"],
    }
