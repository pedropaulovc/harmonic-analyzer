"""FreeCAD CAM recipe for MHA-CH-02, the channel lever.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The lever's sizes come
from the feature export (hub, plate faces, outline, bore and holes); the
blank, the load, the steps, the tabs and the holding from ``plan.toml``
``[parameters]`` and ``milling_cuts``; cutter diameters, speeds and feeds
from the shop (``shop/``) and the plan's authored drill settings. Every path
is written here (``rt.custom``): lines and arcs a recipe can state exactly.
Typed here, because neither record carries them: the #1 centre drill's
catalogue geometry (it sets the spot depth), the twist drill's 118° point,
the approach, safe and clearance heights and the vise jaws' depth
(keep-out shapes only).

Route (plan text in ``plan.toml``): four 5/16 x 1 in blanks per load, side by
side across the jaws on a faced 1/2 in aluminium spoil plate on 1 in
parallels. Side B up: CL01 faces B to the hub's thickness, CL02 pockets B
down to the plate's near face (the 1/2 in end mill's slot and its arc round
the hub, then the 1/8 in end mill's rings into the bar-to-hub roots), CL03
spots and drills the fulcrum bore D, then opens it F (owner ruling 2026-11-24,
fit audit question 1: no reamer), CL04 spots and drills the #47 and
#21 holes. Turned over, side A up: CL05 pockets A to the plate's far face,
CL06 cuts the outline on seven tabs with the 1/8 in end mill, which leaves
the two bar-to-hub roots at its own radius, R.0625, inside the drawing's
2X R.065 (.060-.070; owner ruling 2026-11-23, tool audit Q9: no 5/64 in
cutter), and CL07, on the same tool, rounds the hubs above and below the
plate. A switch to a plate fixture replaces CL06, CL07 and their setup only.

Work frames (G54), each set in its setup: X0 the blanks' left ends (flush),
Y0 the fixed jaw, Z0 the spoil plate's top. Blank k's centre line is Y
−(k + ½) × the pitch; the hub centre is ``hub_from_end_mm`` from the left
end. Side B up (CL01-CL04): the lever turned about X (model y → −Y, model
z → −Z, face A on the plate). Side A up (CL05-CL07): model axes, face B on
the plate.

Toolpath rules (owner rulings 2026-11-16): plunges beside the stock at the
cutting feed, plunges into metal at the plan's slow feed, real G0 above the
stock.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ch_channel_lever"
COMMENT = "MHA-CH-02 channel lever, four per load"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("CL01_face_b", ("face_b",)),
    ("CL02_pocket_b", (("pocket_b",), ("rings_b",))),
    ("CL03_bore", (("bore_spot",), ("bore_drill",), ("bore_open",))),
    ("CL04_holes", (("holes_spot",), ("drill_47",), ("drill_21",))),
    ("CL05_pocket_a", (("pocket_a",), ("rings_a",))),
    ("CL06_outline", ("outline",)),
    # Its own program, not a second CL06 section: on the same tool at the
    # same speed the post joins sections with no M6 or M0, so CL06's
    # per-section checks could not tell the outline's passes from these.
    ("CL07_hub", ("outline_hub",)),
)
# Every program loads its own first tool (M6, the tool setter), but CL07:
# it runs on the 1/8 in end mill CL06 left in the spindle, already touched
# off.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS if name != "CL07_hub")
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these.
CAM_TOOLS = (
    "em-half",
    "em-eighth",
    "spot",
    "drill-47",
    "drill-21",
    "drill-d",
    "drill-f",
)
IN = 25.4
# ANSI #1 combined drill and countersink, 60° included (McMaster 2925A11,
# "for 3/64 in drill bit"): the shop record names the tool, not its geometry.
CENTRE_DRILL = {
    "pilot_mm": 3 / 64 * IN,
    "pilot_length_mm": 3 / 64 * IN,
    "body_mm": 1 / 8 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# Passes start and finish with the cutter this far clear of the stock.
APPROACH_MM = 2.54
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped face.
JAW_DEPTH_MM = IN
# How far the cutter centre may stray from its offset round the outline.
OUTLINE_TOL_MM = 0.05
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


def _setting(
    plan: dict[str, Any], shop: dict[str, Any], cut: str
) -> tuple[float, float]:
    """(rpm, mm/min) of the operation holding ``cut``: the shop setting it
    names (chip load × flutes × rpm), or, with no setting, the rpm and feed
    the cut itself authors."""
    op, record_cut = _op_with_cut(plan, cut)
    if "settings" not in op:
        return _cut(plan, cut, "rpm"), _cut(plan, cut, "feed_mm_min")
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    feed = record["chip_load_mm_per_tooth"] * record["flutes"] * rpm
    for key, expected in (("rpm", rpm), ("feed_mm_min", feed)):
        if key in record_cut and not math.isclose(
            _cut(plan, cut, key), expected, abs_tol=1e-3
        ):
            raise ValueError(
                f"'{cut}' {key} {_cut(plan, cut, key):g} is not its setting's {expected:g}"
            )
    return rpm, feed


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


def _levels(top: float, bottom: float, max_step: float) -> list[float]:
    """Equal steps no larger than ``max_step`` from ``top`` to ``bottom``,
    ``bottom`` last."""
    n = math.ceil((top - bottom) / max_step - 1e-9)
    return [top - (top - bottom) * (k + 1) / n for k in range(n - 1)] + [bottom]


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


def _mid(band: list[float]) -> float:
    return (band[0] + band[1]) / 2


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


def _xy(x: float, y: float) -> str:
    return f"X{_r(x):.3f} Y{_r(y):.3f}"


def _arc(
    motion: str,
    start: tuple[float, float],
    end: tuple[float, float],
    centre: tuple[float, float],
) -> str:
    """G2/G3 to ``end`` about ``centre``, I/J relative to ``start``."""
    i, j = centre[0] - start[0], centre[1] - start[1]
    return f"{motion} {_xy(*end)} I{_r(i):.3f} J{_r(j):.3f}"


def _polar(c: tuple[float, float], radius: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return (c[0] + radius * math.cos(a), c[1] + radius * math.sin(a))


def _spot(xy: tuple[float, float], top: float, z: float, clear: float) -> list[str]:
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 {_xy(*xy)}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _pecked(
    xy: tuple[float, float], top: float, tip: float, peck: float, clear: float
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
    lines = [f"G0 Z{clear:.3f}", f"G0 {_xy(*xy)}", f"G0 Z{r_plane:.3f}"]
    previous = None
    for z in depths:
        if previous is not None:
            lines += [f"G0 Z{r_plane:.3f}", f"G0 Z{_r(previous + PECK_REENTRY_MM):.3f}"]
        lines.append(f"G1 Z{z:.3f} F{{feed}}")
        previous = z
    return lines + [f"G0 Z{r_plane:.3f}", f"G0 Z{clear:.3f}"]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The lever's sizes from the export, each checked against the frame the
    recipe assumes: its length along model X from the fulcrum bore at the
    origin, its width along Y, its faces along Z (B, the near face, at −Z)."""
    f = features["features"]
    planes = {}
    for name in ("hub_near_face", "hub_far_face", "plate_near_face", "plate_far_face"):
        plane = f[name]["plane"]
        if plane["axis"] != "z":
            raise ValueError(f"{name} is not a Z plane")
        planes[name] = plane["value"]
    if not (
        planes["hub_near_face"]
        < planes["plate_near_face"]
        < planes["plate_far_face"]
        < planes["hub_far_face"]
    ):
        raise ValueError(
            f"the faces are not hub B, plate B, plate A, hub A up Z: {planes}"
        )
    holes = {}
    for name in ("fulcrum_bore", "bar_pin_hole", "spring_hole"):
        hole = f[name]
        if hole["axis"] != [0.0, 0.0, 1.0] or not hole.get("thru"):
            raise ValueError(f"{name} is not a through hole along Z")
        if hole["at"][1] != 0.0:
            raise ValueError(f"{name} is off the lever's centre line")
        holes[name] = {"x": hole["at"][0], "dia": hole["dia"]}
    if holes["fulcrum_bore"]["x"] != 0.0 or f["hub"]["at"][:2] != [0.0, 0.0]:
        raise ValueError("the hub and fulcrum bore are not at the model origin")
    outline = f["outline"]
    tangent = outline["taper_tangent_at"]
    tip = outline["tip_at"]
    if tip[1] != 0.0 or tangent[1] <= 0:
        raise ValueError(
            "the tip is not on the centre line, its tangent point above it"
        )
    return {
        "hub_band": f["hub_far_face"]["length"],
        "offset_band": f["plate_near_face"]["offset"],
        "plate_band": f["plate_far_face"]["thickness"],
        "hub_r": f["hub"]["dia_nominal"] / 2,
        "bar_half": outline["bar_height_nominal"] / 2,
        "taper_start": outline["taper_start_nominal"],
        "tangent": (tangent[0], tangent[1]),
        "tip": (tip[0], 0.0),
        "tip_r": outline["tip_radius_nominal"],
        "root_corner_r": outline["root_corner_r"],
        "holes": holes,
    }


def _outline(
    g: dict[str, Any], h: tuple[float, float], r: float, name: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The lever's outline about hub centre ``h`` in a side-A-up frame,
    anticlockwise (conventional outside with a clockwise spindle), and the
    corners of the cutter-centre path at offset ``r``. Each bar edge meets
    the hub in an inside corner the cutter leaves at its own radius, so the
    elements end at that fillet's tangent points."""
    hx, hy = h
    hub_r, half, ts = g["hub_r"], g["bar_half"], g["taper_start"]
    tx, ty = g["tangent"]
    c = (hx + g["tip"][0], hy)
    big = hub_r + r
    jx = math.sqrt(big * big - (half + r) ** 2)
    corner_deg = math.degrees(math.atan2(half + r, jx))

    def mirror(point: tuple[float, float]) -> tuple[float, float]:
        return (point[0], 2 * hy - point[1])

    top_p, top_t = (hx + ts, hy + half), (hx + tx, hy + ty)
    hub_end = _polar(h, hub_r, corner_deg)
    w = (hx - hub_r, hy)
    elements = [
        {
            "name": f"{name} bottom",
            "start": mirror((hx + jx, hy + half)),
            "end": mirror(top_p),
        },
        {"name": f"{name} bottom taper", "start": mirror(top_p), "end": mirror(top_t)},
        {"name": f"{name} tip", "start": mirror(top_t), "end": top_t, "centre": c},
        {"name": f"{name} top taper", "start": top_t, "end": top_p},
        {"name": f"{name} top", "start": top_p, "end": (hx + jx, hy + half)},
        {"name": f"{name} hub top", "start": hub_end, "end": w, "centre": h},
        {"name": f"{name} hub bottom", "start": w, "end": mirror(hub_end), "centre": h},
    ]
    for e in elements:
        e["tol"] = OUTLINE_TOL_MM
    # The top taper runs from T to P; outward is its right side.
    dx, dy = top_p[0] - top_t[0], top_p[1] - top_t[1]
    length = math.hypot(dx, dy)
    normal = (dy / length, -dx / length)
    tip_deg = math.degrees(math.atan2(ty, tx - g["tip"][0]))
    path = {
        "p": top_p,
        "p_line": (top_p[0], top_p[1] + r),
        "p_taper": (top_p[0] + normal[0] * r, top_p[1] + normal[1] * r),
        "t": _polar(c, g["tip_r"] + r, tip_deg),
        "j": (hx + jx, hy + half + r),
        "w": (hx - big, hy),
        "c": c,
        "corner_deg": corner_deg,
        "big": big,
    }
    return elements, path


def _lap(
    h: tuple[float, float],
    path: dict[str, Any],
    start: tuple[float, float],
    z: float,
    boxes: list[dict[str, Any]],
) -> list[str]:
    """One anticlockwise lap of the offset path at ``z``, from ``start`` on
    the bottom run round to it again. Each of ``boxes`` (a bar tab's box, or
    the hub tab's) the lap crosses below its ``top`` is hopped: up to the top
    at its first edge, level across it along the path, down at its far edge."""
    hy = h[1]

    def mirror(point: tuple[float, float]) -> tuple[float, float]:
        return (point[0], 2 * hy - point[1])

    def straight(a: tuple[float, float], b: tuple[float, float]) -> list[str]:
        lines = []
        lo, hi = sorted((a[0], b[0]))
        crossing = [
            box
            for box in boxes
            if box["kind"] == "bar"
            and z < box["top"] - 1e-6
            and lo <= box["x"][0]
            and box["x"][1] <= hi
            and box["y"][0]
            <= a[1] + (box["x"][0] - a[0]) * (b[1] - a[1]) / (b[0] - a[0])
            <= box["y"][1]
        ]
        forward = b[0] > a[0]
        crossing.sort(key=lambda box: box["x"][0] if forward else -box["x"][1])
        for box in crossing:
            x0, x1 = (
                (box["x"][0], box["x"][1]) if forward else (box["x"][1], box["x"][0])
            )
            y0 = a[1] + (x0 - a[0]) * (b[1] - a[1]) / (b[0] - a[0])
            y1 = a[1] + (x1 - a[0]) * (b[1] - a[1]) / (b[0] - a[0])
            lines += [
                f"G1 {_xy(x0, y0)} F{{feed}}",
                f"G1 Z{_r(box['top']):.3f} F{{feed}}",
                f"G1 {_xy(x1, y1)} F{{feed}}",
                f"G1 Z{_r(z):.3f} F{{plunge}}",
            ]
        return lines + [f"G1 {_xy(*b)} F{{feed}}"]

    p, c = path["p"], path["c"]
    lines = straight(start, mirror(path["p_line"]))
    lines.append(_arc("G3", mirror(path["p_line"]), mirror(path["p_taper"]), mirror(p)))
    lines += straight(mirror(path["p_taper"]), mirror(path["t"]))
    lines.append(_arc("G3", mirror(path["t"]), path["t"], c))
    lines += straight(path["t"], path["p_taper"])
    lines.append(_arc("G3", path["p_taper"], path["p_line"], p))
    lines += straight(path["p_line"], path["j"])
    hub = [box for box in boxes if box["kind"] == "hub" and z < box["top"] - 1e-6]
    if hub:
        box = hub[0]
        a0, a1 = (
            _polar(h, path["big"], 180.0 - box["deg"]),
            _polar(h, path["big"], 180.0 + box["deg"]),
        )
        lines += [
            _arc("G3", path["j"], a0, h),
            f"G1 Z{_r(box['top']):.3f} F{{feed}}",
            _arc("G3", a0, a1, h),
            f"G1 Z{_r(z):.3f} F{{plunge}}",
            _arc("G3", a1, mirror(path["j"]), h) + " F{feed}",
        ]
    else:
        lines.append(_arc("G3", path["j"], path["w"], h))
        lines.append(_arc("G3", path["w"], mirror(path["j"]), h))
    lines += straight(mirror(path["j"]), start)
    return lines


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    n_blanks = int(p["blanks_per_load"])
    pitch = p["blank_pitch_mm"]
    load = n_blanks * pitch

    # The blank and the load.
    _agree(plan, "blank_length_min_mm", p["blank_length_in"] * IN)
    _agree(plan, "blank_length_max_mm", p["blank_length_max_in"] * IN)
    _agree(plan, "blank_pitch_mm", p["blank_width_in"] * IN)
    t_max = p["blank_thickness_in"] * IN
    _agree(plan, "blank_thickness_max_mm", t_max)
    hub_x = p["hub_from_end_mm"]
    lever_end = g["tip"][0] + g["tip_r"]
    margin = p["end_margin_min_mm"]
    if (
        hub_x - g["hub_r"] < margin
        or p["blank_length_min_mm"] - hub_x - lever_end < margin
    ):
        raise ValueError(
            "the lever does not sit in the shortest blank with its end margins"
        )
    hubs = [(hub_x, -(k + 0.5) * pitch) for k in range(n_blanks)]

    # Faces: the hub's thickness, the plate's offset and thickness at their
    # bands' middles; B is faced to the hub, A stays as bought.
    hub_t = _mid(g["hub_band"])
    offset, plate_t = _mid(g["offset_band"]), _mid(g["plate_band"])
    _agree(plan, "hub_thickness_mm", hub_t)
    _agree(plan, "plate_offset_mm", offset)
    _agree(plan, "plate_thickness_mm", plate_t)
    _agree(plan, "face_removal_max_mm", t_max - hub_t)
    if p["blank_thickness_min_mm"] <= hub_t:
        raise ValueError("the thinnest blank does not clean up at the hub's thickness")
    floor_b = hub_t - offset
    floor_a = offset + plate_t
    _agree(plan, "pocket_b_floor_mm", floor_b)
    _agree(plan, "pocket_a_floor_mm", floor_a)

    # Holding: the spoil plate on the shim sheets on the parallels; the jaws'
    # top above Z0. The traveler gauges the jaws' top above the faced plate
    # against a band (jaw_top_min_mm-jaw_top_max_mm); the guards and the
    # keep-outs run at that band's ends, so any plate the band accepts is
    # proved. The as-bought plate, before and after its one facing, must land
    # inside it.
    shim = p["support_shim_sheets"] * p["support_shim_leaf_in"] * IN
    _agree(plan, "support_shim_mm", shim)
    under = p["parallel_height_mm"] + shim
    support = under + p["spoil_plate_thickness_mm"]
    _agree(plan, "support_height_mm", support)
    jaw_top_min, jaw_top_max = p["jaw_top_min_mm"], p["jaw_top_max_mm"]
    if jaw_top_min < shop["limits"]["vise_grip_min_mm"]:
        raise ValueError("the jaws grip the blanks less than the shop's minimum")
    # CL01 faces B over the moving jaw: the band's high end leaves the shop's
    # jaw-clearance floor under the faced hub (#3607).
    if hub_t - jaw_top_max < p["jaw_clear_min_mm"] - 1e-6:
        raise ValueError("the faced blanks do not stand clear of the jaws' top")
    for plate_t_now in (
        p["spoil_plate_thickness_mm"],
        p["spoil_plate_thickness_mm"] - p["spoil_plate_face_mm"],
    ):
        jaw_top_now = p["vise_jaw_height_mm"] - under - plate_t_now
        if not jaw_top_min <= jaw_top_now <= jaw_top_max:
            raise ValueError(
                f"a {plate_t_now:.3f} mm spoil plate puts the jaws' top "
                f"{jaw_top_now:.3f} mm above it, outside the traveler's band"
            )
    # The thinnest plate the band accepts.
    plate_t_min = p["vise_jaw_height_mm"] - under - jaw_top_max
    jaw_w = p["vise_jaw_width_mm"]
    jaw_x0 = (p["blank_length_in"] * IN - jaw_w) / 2
    _agree(plan, "jaw_start_mm", jaw_x0)

    # The 1/2 in end mill: face B, then the pockets' slot and its arc round
    # the hub, which keeps a frame of the blank standing beside it.
    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    r = em / 2
    _agree(plan, "face_cutter_dia_mm", em)
    # Face B runs on its own (measured) setting; the two pockets share one.
    face_rpm, face_feed = _setting(plan, shop, "face b")
    em_rpm, em_feed = _setting(plan, shop, "pocket b")
    if _setting(plan, shop, "pocket a") != (em_rpm, em_feed):
        raise ValueError("'pocket a' runs at another setting than 'pocket b'")
    woc = _cut(plan, "face b", "radial_woc_mm")
    if r - g["bar_half"] < 1.0 or r < g["tip_r"] + 1.0:
        raise ValueError(
            "the slot does not reach 1 mm past the bar's edges and its tip"
        )
    arc_r = g["hub_r"] + r
    arc_deg = math.degrees(
        math.asin((pitch / 2 - r - p["pocket_frame_min_mm"]) / arc_r)
    )
    _agree(plan, "pocket_arc_deg", arc_deg)
    x_out = p["blank_length_max_mm"] + r + APPROACH_MM
    level_max = p["pocket_level_max_mm"]
    for name, depth in (("pocket b", hub_t - floor_b), ("pocket a", hub_t - floor_a)):
        rough = depth - p["pocket_finish_mm"]
        step = rough / math.ceil(rough / level_max - 1e-9)
        if not math.isclose(
            _cut(plan, f"{name} rough", "axial_doc_mm"), step, abs_tol=1e-3
        ):
            raise ValueError(
                f"'{name} rough' axial_doc_mm is not its level, {step:.4f}"
            )
        if not math.isclose(
            _cut(plan, name, "axial_doc_mm"), p["pocket_finish_mm"], abs_tol=1e-6
        ):
            raise ValueError(f"'{name}' axial_doc_mm is not process.pocket_finish_mm")
    # Rough levels to the finish stock above each floor, then the floor.
    finish = p["pocket_finish_mm"]
    levels_b = _levels(hub_t, floor_b + finish, level_max) + [floor_b]
    levels_a = _levels(hub_t, floor_a + finish, level_max) + [floor_a]

    # The 1/8 in end mill's rings into the bar-to-hub roots.
    e8 = _shop_tool(plan, shop, "em-eighth")["diameter_mm"]
    r8 = e8 / 2
    _agree(plan, "eighth_cutter_dia_mm", e8)
    # The roots themselves: the outline's offset path leaves each at the
    # cutter's own radius, which must lie in the drawing's printed band.
    root_band = g["root_corner_r"]
    if not root_band[0] <= r8 <= root_band[1]:
        raise ValueError(
            f"the 1/8 in end mill's radius {r8:.4f} is outside the root "
            f"corners' band {root_band}"
        )
    e8_rpm, e8_feed = _setting(plan, shop, "rings b")
    for name in ("rings a", "outline", "outline hub"):
        if _setting(plan, shop, name) != (e8_rpm, e8_feed):
            raise ValueError(f"'{name}' runs at another setting than 'rings b'")
    plunge8 = p["eighth_plunge_feed_per_min_mm"]
    rings = [g["hub_r"] + r8, p["ring_outer_radius_mm"]]
    ring_deg = p["ring_half_angle_deg"]
    junction_deg = math.degrees(
        math.atan2(g["bar_half"], math.sqrt(g["hub_r"] ** 2 - g["bar_half"] ** 2))
    )
    if rings[0] + r8 < rings[1] - r8:
        raise ValueError("the two rings leave a strip between them")
    if rings[1] + r8 < g["bar_half"] / math.sin(math.radians(arc_deg)):
        raise ValueError(
            "the rings do not reach the slot arc's sweep at the bar's edge"
        )
    if ring_deg < junction_deg + 2.0:
        raise ValueError("the rings stop short of the bar-to-hub roots")
    if (
        rings[1] * math.sin(math.radians(ring_deg)) + r8
        > pitch / 2 - p["pocket_frame_min_mm"]
    ):
        raise ValueError("the outer ring cuts into the blank's frame")
    if rings[0] < arc_r - r:
        raise ValueError("the rings' start is not in the slot")
    ring_levels_b = _levels(hub_t, floor_b, p["ring_level_max_mm"])
    ring_levels_a = _levels(hub_t, floor_a, p["ring_level_max_mm"])

    # Holes: spot under each drill, drill through into the spoil plate; the F
    # drill opens each D bore to the drawing's drill size.
    tools = {
        k: _shop_tool(plan, shop, k)["diameter_mm"] for k in CAM_TOOLS if k != "spot"
    }
    holes = g["holes"]
    bore = holes["fulcrum_bore"]["dia"]
    if not bore[0] - 1e-3 <= tools["drill-f"] <= bore[1]:
        raise ValueError("the F drill is outside the bore's band")
    if not tools["drill-d"] < tools["drill-f"]:
        raise ValueError("the D drill is not under the F drill")
    for key, hole in (("drill-47", "bar_pin_hole"), ("drill-21", "spring_hole")):
        band = holes[hole]["dia"]
        if not band[0] - 1e-3 <= tools[key] <= band[1]:
            raise ValueError(f"the {key} is outside {hole}'s band {band}")
    spot_dia = p["spot_dia_mm"]
    if spot_dia >= tools["drill-47"]:
        raise ValueError("the spot is not under the #47: it would chamfer the hole")
    spot_depth = _spot_depth(spot_dia)
    past = p["drill_past_mm"]
    tips = {
        k: -(past + _point(tools[k]))
        for k in ("drill-47", "drill-21", "drill-d", "drill-f")
    }
    _agree(plan, "drill_d_tip_mm", tips["drill-d"])
    _agree(plan, "drill_f_tip_mm", tips["drill-f"])
    if plate_t_min < -min(tips.values()) + 3.0:
        raise ValueError(
            "the drills' points come within 3 mm of the spoil plate's bottom"
        )
    speeds = {
        key: _setting(plan, shop, cut)
        for key, cut in (
            ("bore_spot", "bore spot"),
            ("bore_drill", "bore drill"),
            ("bore_open", "bore open"),
            ("holes_spot", "holes spot"),
            ("drill_47", "pin hole drill"),
            ("drill_21", "spring hole drill"),
        )
    }
    # A drill fed in one go (peck = "none") is one peck the hole's depth.
    pecks = {
        key: (lambda peck: peck["step_mm"] if isinstance(peck, dict) else 1e3)(
            _op_with_cut(plan, cut)[0]["peck"]
        )
        for key, cut in (
            ("bore_drill", "bore drill"),
            ("bore_open", "bore open"),
            ("drill_47", "pin hole drill"),
            ("drill_21", "spring hole drill"),
        )
    }

    # The outline: the 1/8 in end mill round each lever on its tabs, from
    # the hub's face to through the plate's near face into the spoil plate.
    through = p["outline_through_mm"]
    # Round the whole outline over the plate's thickness only (above and
    # below it the bar is pocketed); round the hub alone above the plate and
    # below it, to .010 into the spoil plate.
    step = p["outline_level_max_mm"]
    out_levels = _levels(floor_a, offset - through, step)
    hub_levels = _levels(hub_t, floor_a, step) + _levels(offset, -through, step)
    tab_t = p["tab_thickness_mm"]
    tab_top = offset + tab_t
    _agree(plan, "tab_top_mm", tab_top)
    tab_half = (p["tab_width_mm"] + e8) / 2
    start_x = p["outline_start_x_mm"]
    # Bar tabs alternate top and bottom edges; the hub's tab is at its far
    # (-X) side. Spaced so no stretch of the lever between tabs, nor its tip
    # past the last, bends past the finish limit under the cut (prechips).
    tab_list = [
        ("top", p["tab_top_1_x_mm"]),
        ("bottom", p["tab_bottom_1_x_mm"]),
        ("top", p["tab_top_2_x_mm"]),
        ("bottom", p["tab_bottom_2_x_mm"]),
        ("top", p["tab_top_3_x_mm"]),
        ("bottom", p["tab_bottom_3_x_mm"]),
    ]
    tx = g["tangent"][0]
    for side, x in tab_list:
        if abs(x - start_x) < tab_half + r8:
            raise ValueError("a tab lies at the outline's start")
        if not g["hub_r"] + r8 + tab_half < x < tx - tab_half:
            raise ValueError(f"the tab at x {x:g} is off the bar's straight edges")
        if abs(x - g["taper_start"]) < tab_half:
            raise ValueError(f"the tab at x {x:g} straddles the taper's corner")
    tab_stations = sorted([hub_x - g["hub_r"]] + [hub_x + x for _side, x in tab_list])
    for k, station in enumerate(tab_stations, 1):
        _agree(plan, f"tab_station_{k}_mm", station)
    _agree(plan, "lever_start_mm", hub_x - g["hub_r"])
    _agree(plan, "lever_end_mm", hub_x + lever_end)

    def edge_y(x: float) -> float:
        """The bar's top edge at ``x`` from the hub's centre."""
        if x <= g["taper_start"]:
            return g["bar_half"]
        run = (x - g["taper_start"]) / (tx - g["taper_start"])
        return g["bar_half"] - run * (g["bar_half"] - g["tangent"][1])

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)): side B up turns the
    # lever about X onto its A face; side A up is the model's own axes on
    # the B face. Both put blank 0's hub at (hub_x, -pitch/2).
    hub_half = features["features"]["hub_far_face"]["plane"]["value"]
    frames = {
        "b": {
            "origin": [-hub_x, -pitch / 2, hub_half],
            "axes": [[1, 0, 0], [0, -1, 0], [0, 0, -1]],
        },
        "a": {
            "origin": [-hub_x, pitch / 2, -hub_half],
            "axes": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        },
    }
    stock_b = ((0.0, p["blank_length_max_mm"]), (-load, 0.0), (0.0, t_max))
    stock = ((0.0, p["blank_length_max_mm"]), (-load, 0.0), (0.0, hub_t))

    clear_raw, clear = t_max + CLEAR_MM, hub_t + CLEAR_MM
    safe = _r(hub_t + SAFE_MM)

    # Face B: zigzag along X across the load, each row's first bite at most
    # the plan's width, past both blank ends and 0.5 mm past both sides.
    overhang = 0.5
    first = -load - r + woc
    last = overhang - r
    n_rows = math.ceil((last - first) / woc - 1e-9)
    rows = [first + (last - first) * k / n_rows for k in range(n_rows + 1)]
    x_a, x_b = -r - APPROACH_MM, x_out
    face = [f"G0 Z{_r(clear_raw):.3f}", f"G0 {_xy(x_a, rows[0])}"]
    face += [f"G0 Z{_r(t_max + SAFE_MM):.3f}", f"G1 Z{_r(hub_t):.3f} F{{feed}}"]
    for k, y in enumerate(rows):
        if k:
            face.append(f"G1 Y{_r(y):.3f} F{{feed}}")
        face.append(f"G1 X{_r(x_b if k % 2 == 0 else x_a):.3f} F{{feed}}")
    face.append(f"G0 Z{_r(clear_raw):.3f}")

    def pocket(levels: list[float]) -> list[str]:
        lines = []
        for h in hubs:
            for z in levels:
                arc0 = (h[0] + arc_r, h[1])
                up, down = _polar(h, arc_r, arc_deg), _polar(h, arc_r, -arc_deg)
                lines += [
                    f"G0 Z{_r(clear):.3f}",
                    f"G0 {_xy(x_out, h[1])}",
                    f"G0 Z{safe:.3f}",
                    f"G1 Z{_r(z):.3f} F{{feed}}",
                    f"G1 {_xy(*arc0)} F{{feed}}",
                    _arc("G3", arc0, up, h),
                    _arc("G2", up, down, h),
                    _arc("G3", down, arc0, h),
                    f"G0 Z{_r(clear):.3f}",
                ]
        return lines

    def ring_lines(levels: list[float]) -> list[str]:
        lines = []
        for h in hubs:
            for z in levels:
                for radius in rings:
                    a0 = (h[0] + radius, h[1])
                    up, down = _polar(h, radius, ring_deg), _polar(h, radius, -ring_deg)
                    lines += [
                        f"G0 Z{_r(clear):.3f}",
                        f"G0 {_xy(*a0)}",
                        f"G0 Z{safe:.3f}",
                        f"G1 Z{_r(z):.3f} F{{feed}}",
                        _arc("G3", a0, up, h),
                        _arc("G2", up, down, h),
                        _arc("G3", down, a0, h),
                        f"G0 Z{_r(clear):.3f}",
                    ]
        return lines

    bore_xy = [h for h in hubs]
    pin_xy = [(h[0] + holes["bar_pin_hole"]["x"], h[1]) for h in hubs]
    spring_xy = [(h[0] + holes["spring_hole"]["x"], h[1]) for h in hubs]

    # The outline and its tabs, lever by lever.
    elements: list[dict[str, Any]] = []
    tabs: list[dict[str, Any]] = []
    outline: list[str] = []
    hub_elements: list[dict[str, Any]] = []
    outline_hub: list[str] = []
    for k, h in enumerate(hubs):
        els, path = _outline(g, h, r8, f"lever {k + 1}")
        elements += els
        lever_tabs = []
        for side, x in tab_list:
            sign = 1.0 if side == "top" else -1.0
            edge = edge_y(x)
            y_span = sorted(
                (h[1] + sign * (edge - 1.0), h[1] + sign * (edge + r8 + 1.0))
            )
            lever_tabs.append(
                {
                    "name": f"lever {k + 1} {side} x{x:g}",
                    "kind": "bar",
                    "x": (h[0] + x - tab_half, h[0] + x + tab_half),
                    "y": tuple(y_span),
                }
            )
        hub_deg = math.degrees(math.asin(tab_half / path["big"]))
        lever_tabs.append(
            {
                "name": f"lever {k + 1} hub",
                "kind": "hub",
                "deg": hub_deg,
                "x": (h[0] - path["big"] - 1.0, h[0] - g["hub_r"] + 1.0),
                "y": (h[1] - tab_half, h[1] + tab_half),
            }
        )
        for box in lever_tabs:
            box.update(top=tab_top, floor=offset, thickness=tab_t)
            tabs.append(
                {
                    key: box[key]
                    for key in ("name", "x", "y", "top", "floor", "thickness")
                }
            )
        start = (h[0] + start_x, 2 * h[1] - path["j"][1])
        outline += [
            f"G0 Z{_r(clear):.3f}",
            f"G0 {_xy(*start)}",
            f"G0 Z{safe:.3f}",
            f"G1 Z{_r(floor_a + SAFE_MM):.3f} F{{feed}}",
        ]
        for z in out_levels:
            outline.append(f"G1 Z{_r(z):.3f} F{{plunge}}")
            outline += _lap(h, path, start, z, lever_tabs)
        outline.append(f"G0 Z{_r(clear):.3f}")
        hub_elements += [e for e in els if " hub " in e["name"]]
        mirror_j = (path["j"][0], 2 * h[1] - path["j"][1])
        for z in hub_levels:
            outline_hub += [
                f"G0 Z{_r(clear):.3f}",
                f"G0 {_xy(*path['j'])}",
                f"G0 Z{safe:.3f}",
                f"G1 Z{_r(z):.3f} F{{feed}}",
                _arc("G3", path["j"], path["w"], h),
                _arc("G3", path["w"], mirror_j, h),
            ]
        outline_hub.append(f"G0 Z{_r(clear):.3f}")

    def job(
        key,
        label,
        tool,
        dia,
        shape,
        rpm,
        feed,
        plunge,
        frame,
        stock_box,
        lines,
        flutes=None,
        tip=None,
    ):
        return {
            "tool": tool,
            "dia": dia,
            "shape": shape,
            "flutes": flutes,
            "tip_angle": tip,
            "rpm": rpm,
            "feed": feed,
            "plunge": plunge,
            "frame": frame,
            "label": label,
            "stock": stock_box,
            "ops": [[key, label, lines]],
        }

    sp_rpm, sp_feed = speeds["bore_spot"]
    hs_rpm, hs_feed = speeds["holes_spot"]
    bd_rpm, bd_feed = speeds["bore_drill"]
    bo_rpm, bo_feed = speeds["bore_open"]
    d47_rpm, d47_feed = speeds["drill_47"]
    d21_rpm, d21_feed = speeds["drill_21"]
    centre = CENTRE_DRILL["point_deg"]
    jobs = [
        job(
            "face_b",
            "face B",
            "em-half",
            em,
            "endmill",
            face_rpm,
            face_feed,
            face_feed,
            "b",
            stock_b,
            face,
            3,
        ),
        job(
            "pocket_b",
            "pocket B",
            "em-half",
            em,
            "endmill",
            em_rpm,
            em_feed,
            em_feed,
            "b",
            stock,
            pocket(levels_b),
            3,
        ),
        job(
            "rings_b",
            "rings B",
            "em-eighth",
            e8,
            "endmill",
            e8_rpm,
            e8_feed,
            e8_feed,
            "b",
            stock,
            ring_lines(ring_levels_b),
            3,
        ),
        job(
            "bore_spot",
            "spot the bores",
            "spot",
            CENTRE_DRILL["body_mm"],
            "drill",
            sp_rpm,
            sp_feed,
            sp_feed,
            "b",
            stock,
            [
                ln
                for xy in bore_xy
                for ln in _spot(xy, hub_t, hub_t - spot_depth, clear)
            ],
            tip=centre,
        ),
        job(
            "bore_drill",
            "drill the bores D",
            "drill-d",
            tools["drill-d"],
            "drill",
            bd_rpm,
            bd_feed,
            bd_feed,
            "b",
            stock,
            [
                ln
                for xy in bore_xy
                for ln in _pecked(
                    xy, hub_t, tips["drill-d"], pecks["bore_drill"], clear
                )
            ],
            tip=DRILL_POINT_DEG,
        ),
        job(
            "bore_open",
            "open the bores F",
            "drill-f",
            tools["drill-f"],
            "drill",
            bo_rpm,
            bo_feed,
            bo_feed,
            "b",
            stock,
            [
                ln
                for xy in bore_xy
                for ln in _pecked(xy, hub_t, tips["drill-f"], pecks["bore_open"], clear)
            ],
            tip=DRILL_POINT_DEG,
        ),
        job(
            "holes_spot",
            "spot the pin and spring holes",
            "spot",
            CENTRE_DRILL["body_mm"],
            "drill",
            hs_rpm,
            hs_feed,
            hs_feed,
            "b",
            stock,
            [
                ln
                for xy in pin_xy + spring_xy
                for ln in _spot(xy, floor_b, floor_b - spot_depth, clear)
            ],
            tip=centre,
        ),
        job(
            "drill_47",
            "drill the pin holes #47",
            "drill-47",
            tools["drill-47"],
            "drill",
            d47_rpm,
            d47_feed,
            d47_feed,
            "b",
            stock,
            [
                ln
                for xy in pin_xy
                for ln in _pecked(
                    xy, floor_b, tips["drill-47"], pecks["drill_47"], clear
                )
            ],
            tip=DRILL_POINT_DEG,
        ),
        job(
            "drill_21",
            "drill the spring holes #21",
            "drill-21",
            tools["drill-21"],
            "drill",
            d21_rpm,
            d21_feed,
            d21_feed,
            "b",
            stock,
            [
                ln
                for xy in spring_xy
                for ln in _pecked(
                    xy, floor_b, tips["drill-21"], pecks["drill_21"], clear
                )
            ],
            tip=DRILL_POINT_DEG,
        ),
        job(
            "pocket_a",
            "pocket A",
            "em-half",
            em,
            "endmill",
            em_rpm,
            em_feed,
            em_feed,
            "a",
            stock,
            pocket(levels_a),
            3,
        ),
        job(
            "rings_a",
            "rings A",
            "em-eighth",
            e8,
            "endmill",
            e8_rpm,
            e8_feed,
            e8_feed,
            "a",
            stock,
            ring_lines(ring_levels_a),
            3,
        ),
        job(
            "outline",
            "outline on tabs",
            "em-eighth",
            e8,
            "endmill",
            e8_rpm,
            e8_feed,
            plunge8,
            "a",
            stock,
            outline,
            3,
        ),
        job(
            "outline_hub",
            "round the hubs",
            "em-eighth",
            e8,
            "endmill",
            e8_rpm,
            e8_feed,
            e8_feed,
            "a",
            stock,
            outline_hub,
            3,
        ),
    ]

    # Keep-outs: the jaws beside the load from Z0 to their top, the hubs'
    # bosses under the hub face. The jaws stand at the band's high end, the
    # thinnest accepted plate: its box holds the low end's.
    jaws = [
        _box(
            "moving jaw",
            (jaw_x0, jaw_x0 + jaw_w),
            (-load - JAW_DEPTH_MM, -load),
            jaw_top_max,
        ),
        _box("fixed jaw", (jaw_x0, jaw_x0 + jaw_w), (0.0, JAW_DEPTH_MM), jaw_top_max),
    ]
    bosses = [
        {
            "name": f"hub {k + 1}",
            "centre": [h[0], h[1]],
            "radius": g["hub_r"],
            "z_top": hub_t,
        }
        for k, h in enumerate(hubs)
    ]

    # Points each pocket tool must clear at its floor: along the bar's edges
    # and centre line from the hub to the tip for the slot; round the roots
    # for the rings.
    slot_points, ring_points = [], []
    half = g["bar_half"]
    for h in hubs:
        x = 8.0
        while x < g["taper_start"]:
            slot_points += [[_r(h[0] + x), _r(h[1] + y)] for y in (-half, 0.0, half)]
            x += 8.0
        slot_points.append([_r(h[0] + lever_end), _r(h[1])])
        for deg in (30.0, 35.0, 40.0, 45.0, 50.0):
            for radius in (6.2, 7.0, 8.0, 9.0, 10.0):
                if radius * math.sin(math.radians(deg)) <= half:
                    for sign in (1.0, -1.0):
                        q = _polar(h, radius, sign * deg)
                        ring_points.append([_r(q[0]), _r(q[1])])

    tn = numbers
    expect: list[list[Any]] = []

    def common(name, z_top, tools_loaded, rpms, z_min):
        return [
            [
                name,
                "tool_changes",
                {
                    "z_top": z_top,
                    "tools": tools_loaded,
                    "loads_first": name in LOAD_FIRST_TOOL,
                },
            ],
            [name, "spindle", {"rpm": [[x] for x in rpms]}],
            [name, "pauses", {"z_top": z_top, "count": 0}],
            [name, "depth", {"z_min": _r(z_min)}],
        ]

    name = "CL01_face_b"
    expect += common(name, t_max, [tn["em-half"]], [face_rpm], hub_t)
    expect += [
        [name, "rapids_clear", {"z_top": t_max}],
        [name, "air_feed", {"z_top": t_max}],
        [
            name,
            "face_passes",
            {
                "z": _r(hub_t),
                "y": [-load, 0.0],
                "max_engagement": woc,
                "radius": r,
                "span": p["blank_length_min_mm"],
                "overhang": overhang,
            },
        ],
        [name, "keep_out", {"radius": r, "boxes": jaws}],
    ]
    for name, floor, ring_floor in (
        ("CL02_pocket_b", floor_b, ring_levels_b[-1]),
        ("CL05_pocket_a", floor_a, ring_levels_a[-1]),
    ):
        expect += common(
            name, hub_t, [tn["em-half"], tn["em-eighth"]], [em_rpm, e8_rpm], floor
        )
        for k, (radius, points, z) in enumerate(
            ((r, slot_points, floor), (r8, ring_points, ring_floor))
        ):
            expect += [
                [f"{name}@{k}", "rapids_clear", {"z_top": hub_t}],
                [f"{name}@{k}", "air_feed", {"z_top": hub_t}],
                [
                    f"{name}@{k}",
                    "cleared",
                    {"points": points, "radius": radius, "z": _r(z)},
                ],
                [
                    f"{name}@{k}",
                    "keep_out",
                    {"radius": radius, "boxes": jaws, "circles": bosses},
                ],
            ]
    for name, sections in (
        (
            "CL03_bore",
            (
                (
                    "spot",
                    sp_rpm,
                    hub_t - spot_depth,
                    CENTRE_DRILL["body_mm"] / 2,
                    bore_xy,
                ),
                ("drill-d", bd_rpm, tips["drill-d"], tools["drill-d"] / 2, bore_xy),
                ("drill-f", bo_rpm, tips["drill-f"], tools["drill-f"] / 2, bore_xy),
            ),
        ),
        (
            "CL04_holes",
            (
                (
                    "spot",
                    hs_rpm,
                    floor_b - spot_depth,
                    CENTRE_DRILL["body_mm"] / 2,
                    pin_xy + spring_xy,
                ),
                ("drill-47", d47_rpm, tips["drill-47"], tools["drill-47"] / 2, pin_xy),
                (
                    "drill-21",
                    d21_rpm,
                    tips["drill-21"],
                    tools["drill-21"] / 2,
                    spring_xy,
                ),
            ),
        ),
    ):
        expect += common(
            name,
            hub_t,
            [tn[s[0]] for s in sections],
            [s[1] for s in sections],
            min(s[2] for s in sections),
        )
        # CL04's holes are in the pocket: its floor is their stock top.
        top = hub_t if name == "CL03_bore" else floor_b
        for k, (tool, _rpm, bottom, radius, centres) in enumerate(sections):
            xy = [[_r(x), _r(y)] for x, y in centres]
            expect += [
                [f"{name}@{k}", check, kwargs]
                for check, kwargs in (
                    ("holes", {"centres": xy, "z_bottom": _r(bottom)}),
                    ("rapids_clear", {"z_top": top, "open_holes": xy}),
                    ("vertical_below_top", {"z_top": top}),
                    ("air_feed", {"z_top": top}),
                    ("keep_out", {"radius": radius, "boxes": jaws}),
                )
            ]
    name = "CL06_outline"
    expect += common(name, hub_t, [tn["em-eighth"]], [e8_rpm], out_levels[-1])
    expect += [
        [name, "rapids_clear", {"z_top": hub_t}],
        [name, "air_feed", {"z_top": hub_t}],
        [
            name,
            "outline",
            {
                "elements": elements,
                "z_top": hub_t,
                "passes": [{"offset": r8, "levels": [_r(z) for z in out_levels]}],
                "tabs": tabs,
            },
        ],
        [name, "keep_out", {"radius": r8, "boxes": jaws}],
    ]
    # CL07 carries on with CL06's 1/8 in end mill: no M6 at all.
    name = "CL07_hub"
    expect += common(name, hub_t, [], [e8_rpm], -through)
    expect += [
        [name, "rapids_clear", {"z_top": hub_t}],
        [name, "air_feed", {"z_top": hub_t}],
        [
            name,
            "outline",
            {
                "elements": hub_elements,
                "z_top": hub_t,
                "passes": [{"offset": r8, "levels": [_r(z) for z in hub_levels]}],
            },
        ],
        [name, "keep_out", {"radius": r8, "boxes": jaws}],
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
    section; returns {"ops": {operation key: operation or manual section}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(
            doc,
            f"Channel lever side {key.upper()} up",
            ctx["step"],
            frame["origin"],
            frame["axes"],
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
