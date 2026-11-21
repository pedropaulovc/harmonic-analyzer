"""FreeCAD CAM recipe for MHA-CH-03, the connecting rod.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The rod's sizes come
from the feature export (ring, bore, shank, fork, slot, pin hole and the face
planes); the blank, the load, the steps, the tabs and the holding from
``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter diameters,
speeds and feeds from the shop (``shop/``) and the plan's authored drill and
saw settings. Every path is written here (``rt.custom``): lines and arcs a
recipe can state exactly. Typed here, because neither record carries them:
the #1 centre drill's catalogue geometry (it sets the spot depth), the twist
drill's 118° point, the approach, safe and clearance heights and the vise
jaws' depth (keep-out shapes only).

Route (plan text in ``plan.toml``): two 1/4 x 2 in blanks per load, side by
side across the jaws on a 1/2 in aluminium support plate on 1 in parallels,
each rod along its blank, the ring at the left end. Each face is pocketed
inside the blank's uncut edges (its frame): the ring's zone full width, the
ring and the fork standing as islands; along the shank only a band the
shank's width plus the outline's kerf, the waste beyond it staying whole.
Side 2 (the fork's far face) up: CR01 skims the fork's far face and roughs
side 2 to .020 over its floors. Side 1 (the datum face, as bought) up: CR02
roughs side 1; the blanks are released and reseated; CR03 finishes side 1.
Side 2 up again: CR04 finishes side 2, trims the blank's right end to the
fork's crown and clears the waste beside the fork's end through; CR05 bores
the ring by interpolation; CR06 saws the fork slot with the slitting saw
running horizontally; CR07 spots, drills and reams the pin hole; CR08 cuts
the outline on seven tabs with the 1/8 in end mill and recuts the four
inside corners with the 5/64 in end mill. A switch to a plate fixture
replaces CR08 and its setup only.

Work frames (G54): X0 the blanks' left ends (flush), Y0 the fixed jaw, blank
k's centre line at Y −(k + ½) × the pitch, the ring's centre
``ring_from_end_mm`` from the left end. Side 2 up (CR01, CR04-CR08): Z0 the
support plate's top, which is the datum face (model y → X, model −x → Y,
model z → Z). Side 1 up (CR02, CR03): Z0 the datum face, on top (model y →
X, model x → Y, model −z → Z).

Toolpath rules (owner rulings 2026-11-16): plunges beside the stock at the
cutting feed, plunges into metal at the plan's slow feed, real G0 above the
stock. The slitting saw has no tool-setter length: CR06 loads no tool, its
Z0 is touched off from the saw's lower face.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ch_connecting_rod"
COMMENT = "MHA-CH-03 connecting rod, two per load"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("CR01_rough_2", (("rough_2",), ("band_rough_2",))),
    ("CR02_rough_1", (("rough_1",), ("band_rough_1",))),
    ("CR03_finish_1", (("finish_1",), ("band_1",))),
    ("CR04_finish_2", (("finish_2",), ("band_2",))),
    ("CR05_bore", ("bore",)),
    ("CR06_slot", ("slot",)),
    ("CR07_pin", (("pin_spot",), ("pin_drill",), ("pin_ream",))),
    ("CR08_outline", (("outline",), ("roots",))),
)
# The end mill and drill-chuck programs load their own first tool (M6, the
# tool setter); the saw program runs on the saw already on its arbor and
# touched off, which the tool setter cannot measure.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS if name != "CR06_slot")
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these.
CAM_TOOLS = (
    "em-half",
    "em-eighth",
    "spot",
    "drill-49",
    "reamer-0775",
    "em-5-64",
    "saw",
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
# The 5/64 in root passes run this far along the shank's flank and this far
# round the ring (degrees) or along the fork's side from each corner, inside
# the 1/8 in cutter's cut. The flank run must reach past where the 1/8 in
# cutter's round leaves the flank (context() checks it against both
# corners: a shorter run leaves a sliver of its R.0625 above R.040 MAX); a
# short one keeps the cutter off the shank's tabs near the corners.
ROOT_RUN_MM = 1.0
ROOT_ARC_DEG = 15.0
ROOT_SIDE_MM = 1.0
# The 1/8 in outline and the 1/2 in fork contour overlap this far along the
# fork's sides past the slot's floor.
FORK_OVERLAP_MM = 1.0
# The arbor spacer by the saw clears the fork's crown by this much.
COLLAR_CLEAR_MM = 1.0
# The saw is touched off over the fork against the fixed jaw, its rim this
# far in over the crown.
TOUCH_IN_MM = 3.0
# The feeler leaf under a tool touched off on a face (.002 in).
LEAF_MM = 0.0508
# The plan's air proofs raise Z0 1.000 in.
AIR_PROOF_RAISE_MM = 25.4
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


def _reamed(xy: tuple[float, float], top: float, tip: float, clear: float) -> list[str]:
    """Ream from the R plane to ``tip`` and back out, both at feed."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 {_xy(*xy)}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(tip):.3f} F{{feed}}",
        f"G1 Z{r_plane:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def _side(
    xs: list[float],
    zs: list[float],
    y: tuple[float, float],
    top: float,
    clear: float | None = None,
) -> list[str]:
    """Side passes at each Z in ``zs`` and, at each, each cutter-centre X in
    ``xs`` in order, every pass from ``y[0]`` to ``y[1]`` (one direction):
    down to the level at feed beside the load, along Y at feed, up and back
    in rapids at ``clear`` (default the stock top plus ``CLEAR_MM``)."""
    clear = _r(top + CLEAR_MM if clear is None else clear)
    safe = _r(top + SAFE_MM)
    y0, y1 = _r(y[0]), _r(y[1])
    lines = [f"G0 Z{clear:.3f}"]
    for z in zs:
        for x in xs:
            lines += [
                f"G0 X{_r(x):.3f} Y{y0:.3f}",
                f"G0 Z{safe:.3f}",
                f"G1 Z{_r(z):.3f} F{{feed}}",
                f"G1 Y{y1:.3f} F{{feed}}",
                f"G0 Z{clear:.3f}",
            ]
    return lines


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The rod's sizes from the export, each checked against the frame the
    recipe assumes: the ring's centre at the origin, the rod along model +Y,
    its width along X, its faces along Z (the datum face, the fork's near
    face, at −Z)."""
    f = features["features"]
    planes = {}
    for name in (
        "datum_face",
        "ring_near_face",
        "shank_near_face",
        "shank_far_face",
        "ring_far_face",
        "fork_far_face",
    ):
        plane = f[name]["plane"]
        if plane["axis"] != "z":
            raise ValueError(f"{name} is not a Z plane")
        planes[name] = plane["value"]
    values = list(planes.values())
    if values != sorted(values) or len(set(values)) != len(values):
        raise ValueError(
            f"the faces are not datum, ring, shank, shank, ring, fork up Z: {planes}"
        )
    for name in ("ring", "strap_bore"):
        if f[name]["at"] != [0.0, 0.0, 0.0] or f[name]["axis"] != [0.0, 0.0, 1.0]:
            raise ValueError(f"{name} is not on the model origin along Z")
    left, right = (f[k]["plane"] for k in ("shank_left_flank", "shank_right_flank"))
    if left["axis"] != "x" or right["axis"] != "x" or left["value"] != -right["value"]:
        raise ValueError("the shank's flanks are not X planes either side of the axis")
    fork = f["fork"]
    crown = fork["crown_at"]
    pin = f["pin_hole"]
    if crown[0] != 0.0 or pin["at"][:2] != crown[:2] or pin["axis"] != [0.0, 0.0, 1.0]:
        raise ValueError("the crown and the pin hole are not on the rod's axis")
    if not pin.get("thru") or not f["strap_bore"].get("thru"):
        raise ValueError("the bore and the pin hole are not through")
    slot = f["fork_slot"]
    if slot["open_to"] != "crown" or not slot.get("thru"):
        raise ValueError("the fork slot is not through and open to the crown")
    w = fork["width_nominal"] / 2
    if not math.isclose(fork["extent_y"][1], crown[1] + w, abs_tol=1e-6):
        raise ValueError("the fork's crown is not a full round on the pin")
    return {
        "datum": planes["datum_face"],
        "fork_t": _mid(f["fork_far_face"]["thickness"]),
        "ring_near": _mid(f["ring_near_face"]["offset"]),
        "ring_t": _mid(f["ring_far_face"]["thickness"]),
        "shank_near": _mid(f["shank_near_face"]["offset"]),
        "shank_t": _mid(f["shank_far_face"]["thickness"]),
        "ring_r": f["ring"]["dia_nominal"] / 2,
        "bore": f["strap_bore"]["dia"],
        "half": right["value"],
        "w": w,
        "fork_base": fork["extent_y"][0],
        "crown": crown[1],
        "slot_width": _mid(slot["width"]),
        "near_tine": _mid(slot["near_tine"]),
        "far_tine": _mid(slot["far_tine"]),
        "slot_depth": _mid(slot["depth"]),
        "corner_max": slot["corner_radius_max"],
        "pin": pin["dia"],
    }


def _hops(
    a: tuple[float, float],
    b: tuple[float, float],
    z: float,
    boxes: list[dict[str, Any]],
) -> list[str]:
    """The straight run ``a`` to ``b`` at ``z``, hopping each bar tab box it
    crosses below the box's top: up at its first edge, level over it, down
    at its far edge."""
    lines = []
    lo, hi = sorted((a[0], b[0]))
    crossing = [
        box
        for box in boxes
        if box["kind"] == "bar"
        and z < box["top"] - 1e-6
        and lo <= box["x"][0]
        and box["x"][1] <= hi
        and box["y"][0] <= a[1] <= box["y"][1]
    ]
    forward = b[0] > a[0]
    crossing.sort(key=lambda box: box["x"][0] if forward else -box["x"][1])
    for box in crossing:
        x0, x1 = (box["x"][0], box["x"][1]) if forward else (box["x"][1], box["x"][0])
        lines += [
            f"G1 {_xy(x0, a[1])} F{{feed}}",
            f"G1 Z{_r(box['top']):.3f} F{{feed}}",
            f"G1 {_xy(x1, a[1])} F{{feed}}",
            f"G1 Z{_r(z):.3f} F{{plunge}}",
        ]
    return lines + [f"G1 {_xy(*b)} F{{feed}}"]


def _ring_arc(
    c: tuple[float, float],
    radius: float,
    start_deg: float,
    end_deg: float,
    z: float,
    boxes: list[dict[str, Any]],
) -> list[str]:
    """Anticlockwise round ``c`` from ``start_deg`` to ``end_deg`` at ``z``,
    hopping each ring tab box (at its angle) on an arc at the tab's top.
    Every arc states the cutting feed: one after a hop's plunge would run on
    at the plunge feed."""
    lines = []
    at = start_deg
    for box in sorted(
        (b for b in boxes if b["kind"] == "ring" and z < b["top"] - 1e-6),
        key=lambda b: b["deg"],
    ):
        a0, a1 = box["deg"] - box["half_deg"], box["deg"] + box["half_deg"]
        if not start_deg < a0 < a1 < end_deg:
            raise ValueError(f"the ring tab at {box['deg']:g}° is off the lap's arc")
        lines += [
            _arc("G3", _polar(c, radius, at), _polar(c, radius, a0), c) + " F{feed}",
            f"G1 Z{_r(box['top']):.3f} F{{feed}}",
            _arc("G3", _polar(c, radius, a0), _polar(c, radius, a1), c),
            f"G1 Z{_r(z):.3f} F{{plunge}}",
        ]
        at = a1
    end = _arc("G3", _polar(c, radius, at), _polar(c, radius, end_deg), c)
    lines.append(end + " F{feed}")
    return lines


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    n_blanks = int(p["blanks_per_load"])
    pitch = p["blank_pitch_mm"]
    load = n_blanks * pitch

    # The blank and the load: the ring at the left end, the crown short of
    # the shortest blank's right end by its margin (the tape's reading and
    # the saw cut's squareness: a short blank would leave a flat on the
    # crown, and the slot's depth and the boss's length are taken from it;
    # CR04 trims the end to the crown).
    _agree(plan, "blank_length_min_mm", p["blank_length_in"] * IN)
    _agree(plan, "blank_length_max_mm", p["blank_length_max_in"] * IN)
    _agree(plan, "blank_pitch_mm", p["blank_width_in"] * IN)
    t_max = p["blank_thickness_in"] * IN
    _agree(plan, "blank_thickness_max_mm", t_max)
    t_min = p["blank_thickness_min_mm"]
    rx = p["ring_from_end_mm"]
    big_r = g["ring_r"]
    if rx - big_r < p["end_margin_min_mm"]:
        raise ValueError("the ring does not clear the blank's left end by its margin")
    crown_x = rx + g["crown"] + g["w"]
    _agree(plan, "crown_x_mm", crown_x)
    if p["blank_length_min_mm"] - crown_x < p["crown_margin_min_mm"]:
        raise ValueError(
            "the crown is not short of the shortest blank's right end by its margin"
        )
    _agree(plan, "end_trim_max_mm", p["blank_length_max_mm"] - crown_x)
    l_max = p["blank_length_max_mm"]
    centres = [-(k + 0.5) * pitch for k in range(n_blanks)]

    # Heights above the datum face (Z0 with side 2 up): each band's middle.
    fork_t = g["fork_t"]
    ring_near, ring_far = g["ring_near"], g["ring_near"] + g["ring_t"]
    shank_near, shank_far = g["shank_near"], g["shank_near"] + g["shank_t"]
    for key, value in (
        ("fork_thickness_mm", fork_t),
        ("ring_near_mm", ring_near),
        ("ring_far_mm", ring_far),
        ("shank_near_mm", shank_near),
        ("shank_far_mm", shank_far),
    ):
        _agree(plan, key, value)
    if t_min <= fork_t:
        raise ValueError("the thinnest blank does not clean up at the fork's thickness")
    allow = p["floor_stock_mm"]
    # Side 2 up, Z0 the datum face; side 1 up, Z0 the datum face on top.
    side2 = {
        "top": fork_t,
        "ring": ring_far,
        "floor": shank_far,
    }
    side1 = {
        "top": 0.0,
        "ring": -ring_near,
        "floor": -shank_near,
    }
    for side in (side2, side1):
        side["ring_rough"] = side["ring"] + allow
        side["floor_rough"] = side["floor"] + allow
        if side["ring_rough"] >= side["top"] - 0.1:
            raise ValueError("the ring's rough face is at the fork's face")
    _agree(plan, "ring_rough_2_mm", side2["ring_rough"])
    _agree(plan, "floor_rough_2_mm", side2["floor_rough"])
    _agree(plan, "ring_rough_1_mm", side1["ring_rough"])
    _agree(plan, "floor_rough_1_mm", side1["floor_rough"])

    # Holding: the support plate on the parallels; the jaws' top above Z0.
    support = p["parallel_height_mm"] + p["support_plate_thickness_mm"]
    _agree(plan, "support_height_mm", support)
    jaw_top = p["vise_jaw_height_mm"] - support
    _agree(plan, "jaw_top_mm", jaw_top)
    if jaw_top < shop["limits"]["vise_grip_min_mm"]:
        raise ValueError("the jaws grip the blanks less than the shop's minimum")
    jaw_w = p["vise_jaw_width_mm"]
    jaw_x0 = p["jaw_start_mm"]
    _agree(plan, "jaw_end_mm", jaw_x0 + jaw_w)

    # The 1/2 in end mill: the pockets' rows inside the frame, the fork's
    # contour, the ring's face, the end trim and the waste by the fork's end.
    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    r = em / 2
    _agree(plan, "face_cutter_dia_mm", em)
    em_rpm, em_feed = _setting(plan, shop, "rough 2")
    for name in ("skim 2", "rough 1", "finish 1", "finish 2", "end zone", "end trim"):
        if _setting(plan, shop, name) != (em_rpm, em_feed):
            raise ValueError(f"'{name}' runs at another setting than 'rough 2'")
    e8 = _shop_tool(plan, shop, "em-eighth")["diameter_mm"]
    r8 = e8 / 2
    _agree(plan, "eighth_cutter_dia_mm", e8)
    # The frame: each blank's edges outside the 1/8 in band round the ring.
    edge = big_r + e8
    _agree(plan, "pocket_half_width_mm", edge)
    if pitch / 2 - edge < p["frame_min_mm"]:
        raise ValueError("the frame beside the ring is under its minimum")
    level_max = p["pocket_level_max_mm"]
    rows_reach = edge - r
    n_rows = math.ceil(2 * rows_reach / p["pocket_woc_max_mm"] - 1e-9) + 1
    dys = [rows_reach - 2 * rows_reach * k / (n_rows - 1) for k in range(n_rows)]
    w, fb_rel = g["w"], g["fork_base"]
    fork_band = w + r
    band_rows = [dy for dy in dys if abs(dy) < fork_band]
    if len(band_rows) % 2 or not band_rows:
        raise ValueError("the fork's rows are not in pairs")
    ring_re = big_r + r
    x_left = -r - APPROACH_MM
    x_right = l_max + r + APPROACH_MM
    plunge = p["half_plunge_feed_per_min_mm"]
    # Only the ring's zone (the ring, its band and the frame's inside round
    # them) is pocketed full width; along the shank the two middle rows clear
    # the shank and the 1/8 in outline's kerf beside it, and the waste beyond
    # stays whole. The outer rows run to where the innermost of them reaches
    # the band's outside.
    kerf = g["half"] + e8
    shank_rows = [dy for dy in dys if abs(dy) < r]
    if (
        len(shank_rows) != 2
        or min(shank_rows) - r > -kerf
        or max(shank_rows) + r < kerf
        or not all(abs(dy) < fork_band for dy in shank_rows)
    ):
        raise ValueError("the two middle rows do not clear the shank's kerf")
    outer_rows = [dy for dy in dys if dy not in shank_rows]
    x_zone = rx + math.sqrt(edge**2 - (min(abs(dy) for dy in outer_rows) - r) ** 2)
    # Where the middle rows meet the ring when it stands as an island.
    shank_x = rx + math.sqrt(ring_re**2 - shank_rows[0] ** 2)

    # The fork slot: its floor, the end zone's left side, and the saw.
    slot_floor_x = rx + g["crown"] + w - g["slot_depth"]
    _agree(plan, "slot_floor_x_mm", slot_floor_x)
    if jaw_x0 + jaw_w > slot_floor_x - 1.0:
        raise ValueError("the jaws reach the saw's sweep past the slot's floor")
    saw = _shop_tool(plan, shop, "saw")["diameter_mm"]
    _agree(plan, "saw_dia_mm", saw)
    saw_r = saw / 2
    saw_t = p["saw_thickness_mm"]
    if not saw_t < g["slot_width"] <= 2 * saw_t:
        raise ValueError("the fork slot is not two saw passes wide")
    _agree(
        plan,
        "saw_collar_dia_max_mm",
        2 * (saw_r - g["slot_depth"] - COLLAR_CLEAR_MM),
    )
    near_wall = g["near_tine"]
    far_wall = fork_t - g["far_tine"]
    if not math.isclose(far_wall - near_wall, g["slot_width"], abs_tol=1e-3):
        raise ValueError("the tines and the slot do not make the fork")
    saw_zs = [near_wall, far_wall - saw_t]
    _agree(plan, "saw_low_mm", saw_zs[0])
    _agree(plan, "saw_high_mm", saw_zs[1])
    n_steps = math.ceil(g["slot_depth"] / p["slot_step_max_mm"] - 1e-9)
    slot_steps = [g["slot_depth"] * (k + 1) / n_steps for k in range(n_steps)]
    _agree(plan, "slot_step_mm", slot_steps[0])
    saw_rpm, saw_feed = _setting(plan, shop, "fork slot")
    if (saw_rpm, saw_feed) != (p["saw_rpm"], p["saw_feed_per_min_mm"]):
        raise ValueError("the saw's cut is not process.saw_rpm and saw_feed_per_min_mm")
    if not math.isclose(
        _cut(plan, "fork slot", "radial_woc_mm"), slot_steps[0], abs_tol=1e-6
    ):
        raise ValueError("'fork slot' radial_woc_mm is not process.slot_step_mm")
    saw_xs = [crown_x + saw_r - d for d in slot_steps]

    # The arbor round the saw (tools.gear-cutter-arbor-1, to buy: its sizes
    # are the plan's assumed limits, checked when it is mounted): above the
    # saw, spacers no wider than the collar limit; below it, spacers at least
    # saw_spacer_below_min_mm deep, then the nut, all within saw_below_max_mm
    # of the saw's lower face and the nut no wider than saw_nut_dia_max_mm.
    collar_r = p["saw_collar_dia_max_mm"] / 2
    nut_r = p["saw_nut_dia_max_mm"] / 2
    below = p["saw_below_max_mm"]
    spacer_below = p["saw_spacer_below_min_mm"]
    if not 0 < spacer_below < below:
        raise ValueError("the spacers under the saw are not inside its stack's depth")
    # CR06 moves between passes with the stack's lowest point CLEAR_MM over
    # the stock top.
    saw_clear = t_max + CLEAR_MM + below
    _agree(plan, "saw_clear_z_mm", saw_clear)
    # The touch-off station: over the fork against the fixed jaw, the saw's
    # rim TOUCH_IN_MM in over its crown; the spacers and the nut, hanging
    # below the saw as it comes down onto the fork, stay past the crown.
    touch = (crown_x + saw_r - TOUCH_IN_MM, centres[0])
    _agree(plan, "saw_touch_x_mm", touch[0])
    _agree(plan, "saw_touch_y_mm", touch[1])
    # The saw's and T3's Z0 on the fork's F face, over the .002 leaf.
    _agree(plan, "fork_touch_z_mm", fork_t + LEAF_MM)
    if touch[0] - max(nut_r, collar_r) < crown_x + COLLAR_CLEAR_MM:
        raise ValueError("the arbor's nut reaches the crown at the saw's touch-off")
    # CR05 leaves T1 parked over that station, high enough that the arbor
    # mounted in its place (its lowest point no more than saw_arbor_length_mm
    # from the nose; T1's tip at least its collet and projection out) hangs
    # CLEAR_MM over the stock top: the saw never moves in X or Y on a
    # height the controller does not know.
    park_z = (
        t_max
        + CLEAR_MM
        + p["saw_arbor_length_mm"]
        - (p["r8_collet_gauge_mm"] + p["half_mill_projection_min_mm"])
    )
    _agree(plan, "saw_park_z_mm", park_z)

    # The ring's bore: interpolated by the 1/2 in end mill, a centre plunge
    # and a circle at each level, then the finish circle and a spring pass.
    bore_d = _mid(g["bore"])
    bore_finish = p["bore_finish_mm"]
    rough_rr = (bore_d - 2 * bore_finish - em) / 2
    finish_rr = (bore_d - em) / 2
    _agree(plan, "bore_rough_radius_mm", rough_rr)
    _agree(plan, "bore_finish_radius_mm", finish_rr)
    if rough_rr - r > r:
        raise ValueError(
            "the bore's rough circle leaves a slug round the centre plunge"
        )
    through = p["through_mm"]
    bore_levels = _levels(ring_far, ring_near - through, level_max)
    bore_rpm, bore_feed = _setting(plan, shop, "bore")
    if _setting(plan, shop, "bore rough") != (bore_rpm, bore_feed):
        raise ValueError("'bore rough' runs at another setting than 'bore'")
    if not math.isclose(_cut(plan, "bore", "radial_woc_mm"), bore_finish, abs_tol=1e-6):
        raise ValueError("'bore' radial_woc_mm is not process.bore_finish_mm")

    # Pin hole: spot, the #49 through in pecks, the .0775 reamer through.
    tools = {
        k: _shop_tool(plan, shop, k)["diameter_mm"]
        for k in CAM_TOOLS
        if k not in ("spot", "saw")
    }
    pin_band = g["pin"]
    if not pin_band[0] - 1e-3 <= tools["reamer-0775"] <= pin_band[1]:
        raise ValueError("the reamer is outside the pin hole's band")
    if not tools["drill-49"] < tools["reamer-0775"]:
        raise ValueError("the #49 is not under the reamer")
    spot_dia = p["spot_dia_mm"]
    if spot_dia >= tools["drill-49"]:
        raise ValueError("the spot is not under the #49: it would chamfer the hole")
    spot_depth = _spot_depth(spot_dia)
    drill_tip = -(p["drill_past_mm"] + _point(tools["drill-49"]))
    _agree(plan, "drill_tip_mm", drill_tip)
    ream_tip = -p["ream_past_mm"]
    spot_rpm, spot_feed = _setting(plan, shop, "pin spot")
    drill_rpm, drill_feed = _setting(plan, shop, "pin drill")
    ream_rpm, ream_feed = _setting(plan, shop, "pin ream")
    peck = _op_with_cut(plan, "pin drill")[0]["peck"]["step_mm"]

    # The outline: the 1/8 in end mill round each rod over the waste's
    # thickness (both faces pocketed to the shank's), on tabs; open past the
    # slot's floor, where the 1/2 in end mill's contour cut the fork's sides.
    e8_rpm, e8_feed = _setting(plan, shop, "band rough 2")
    for name in ("band rough 1", "band 1", "band 2", "outline"):
        if _setting(plan, shop, name) != (e8_rpm, e8_feed):
            raise ValueError(f"'{name}' runs at another setting than 'band rough 2'")
    plunge8 = p["eighth_plunge_feed_per_min_mm"]
    out_levels = _levels(shank_far, shank_near - through, p["outline_level_max_mm"])
    tab_t = p["tab_thickness_mm"]
    tab_top = shank_near + tab_t
    _agree(plan, "tab_top_mm", tab_top)
    tab_half = (p["tab_width_mm"] + e8) / 2
    half = g["half"]
    big8 = big_r + r8
    jx8 = math.sqrt(big8**2 - (half + r8) ** 2)
    c8 = math.degrees(math.atan2(half + r8, jx8))
    k8 = math.sqrt(r8**2 - (r8 - (w - half)) ** 2)
    fb = rx + fb_rel
    start_x = p["outline_start_x_mm"]
    bar_tabs = [
        ("top", p["tab_top_1_x_mm"]),
        ("bottom", p["tab_bottom_1_x_mm"]),
        ("top", p["tab_top_2_x_mm"]),
        ("bottom", p["tab_bottom_2_x_mm"]),
        ("top", p["tab_top_3_x_mm"]),
    ]
    ring_tabs = [p["tab_ring_1_deg"], p["tab_ring_2_deg"]]
    for side, x in bar_tabs:
        if not jx8 + tab_half < x < fb_rel - k8 - tab_half:
            raise ValueError(f"the tab at x {x:g} is off the shank's flanks")
        if side == "bottom" and abs(x - start_x) < tab_half + r8:
            raise ValueError("a tab lies at the outline's start")
    tab_deg = math.degrees(math.asin(tab_half / big8))
    for deg in ring_tabs:
        if not c8 + tab_deg < deg < 360 - c8 - tab_deg:
            raise ValueError(f"the ring tab at {deg:g}° is off the ring's free arc")
        # A tab holds only where frame stands outside the kerf there: the
        # kerf's outside at its angle must leave the frame's minimum to the
        # blank's left end and to its edge.
        a = math.radians(deg)
        out_x = rx + edge * math.cos(a)
        out_y = abs(edge * math.sin(a))
        if min(out_x, pitch / 2 - out_y) < p["frame_min_mm"]:
            raise ValueError(f"the ring tab at {deg:g}° has no frame outside the kerf")
    stations = sorted(
        {rx + big_r * math.cos(math.radians(d)) for d in ring_tabs}
        | {rx + x for _side, x in bar_tabs}
    )
    if len(stations) != len(bar_tabs) + len(ring_tabs):
        raise ValueError("two tabs share a station")
    for k, station in enumerate(stations, 1):
        _agree(plan, f"tab_station_{k}_mm", station)
    _agree(plan, "rod_start_mm", rx - big_r)
    _agree(plan, "outline_end_mm", slot_floor_x + FORK_OVERLAP_MM)

    # The 5/64 in end mill's roots: the four inside corners (shank flank to
    # ring, flank to fork step) from the 1/8 in cutter's to its own radius.
    e5 = tools["em-5-64"]
    r5 = e5 / 2
    if r5 > g["corner_max"] or r5 > p["inside_corner_max_mm"]:
        raise ValueError(
            "the 5/64 in end mill's radius is over the inside-corner ceiling"
        )
    root_rpm, root_feed = _setting(plan, shop, "roots")
    root_levels = _levels(shank_far, shank_near - through, p["root_level_max_mm"])
    # The roots' cut as the plan declares it to the bending screen: the
    # cutter, its station (the fork's step) and its radial engagement at a
    # corner (the 1/8 in cutter's radius less its own).
    _agree(plan, "root_cutter_dia_mm", e5)
    _agree(plan, "root_station_mm", fb)
    _agree(plan, "root_woc_mm", r8 - r5)
    # The levels the outline and the roots cut (their cuts' declared depths)
    # and the bending screen's stations and webs.
    _agree(plan, "outline_level_mm", (out_levels[0] - out_levels[1]))
    _agree(plan, "root_level_mm", (root_levels[0] - root_levels[1]))
    _agree(plan, "blank_mid_mm", pitch / 2)
    _agree(plan, "web_d_finish_mm", side2["floor_rough"] - shank_near)
    _agree(plan, "pin_x_mm", rx + g["crown"])
    _agree(plan, "slot_mid_x_mm", (slot_floor_x + crown_x) / 2)

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)), blank 0's ring at
    # (rx, -pitch/2).
    datum = g["datum"]
    frames = {
        "two": {
            "origin": [-pitch / 2, -rx, datum],
            "axes": [[0, 1, 0], [-1, 0, 0], [0, 0, 1]],
        },
        "one": {
            "origin": [pitch / 2, -rx, datum],
            "axes": [[0, 1, 0], [1, 0, 0], [0, 0, -1]],
        },
    }
    stock_two = ((0.0, l_max), (-load, 0.0), (0.0, t_max))
    stock_one = ((0.0, l_max), (-load, 0.0), (-t_max, 0.0))

    # --- the pockets ---------------------------------------------------------
    def fork_loop(yc: float) -> list[str]:
        """The fork island's contour at offset ``r``, anticlockwise from the
        middle of its base line."""
        cc = rx + g["crown"]
        b = fb - r
        return [
            f"G1 Y{_r(yc - w):.3f} F{{feed}}",
            _arc("G3", (b, yc - w), (fb, yc - w - r), (fb, yc - w)),
            f"G1 X{_r(cc):.3f} F{{feed}}",
            _arc("G3", (cc, yc - w - r), (cc, yc + w + r), (cc, yc)),
            f"G1 X{_r(fb):.3f} F{{feed}}",
            _arc("G3", (fb, yc + w + r), (b, yc + w), (fb, yc + w)),
            f"G1 Y{_r(yc):.3f} F{{feed}}",
        ]

    def pocket_level(
        yc: float, z: float, top: float, ring_island: bool, above: float
    ) -> list[str]:
        """One blank's pocket at ``z`` (the cut above it reached ``above``).
        Over the ring (not ``ring_island``): the middle rows from beside the
        blank's left end to the fork's base, the fork's contour, then the
        outer rows across the ring's zone. Round the ring: the middle rows
        from the ring (a plunge into metal at the slow feed) to the fork's
        base, the fork's contour, and back round the ring's right side."""
        clear, safe = _r(top + CLEAR_MM), _r(top + SAFE_MM)
        hi, lo = shank_rows
        xf = fb - r
        start_x = shank_x if ring_island else x_left
        lines = [
            f"G0 Z{clear:.3f}",
            f"G0 {_xy(start_x, yc + hi)}",
            f"G0 Z{safe:.3f}",
        ]
        if ring_island:
            lines += [
                f"G1 Z{_r(above):.3f} F{{feed}}",
                f"G1 Z{_r(z):.3f} F{{plunge}}",
            ]
        else:
            lines.append(f"G1 Z{_r(z):.3f} F{{feed}}")
        lines += [
            f"G1 X{_r(xf):.3f} F{{feed}}",
            f"G1 Y{_r(yc):.3f} F{{feed}}",
            *fork_loop(yc),
            f"G1 Y{_r(yc + lo):.3f} F{{feed}}",
            f"G1 X{_r(start_x):.3f} F{{feed}}",
        ]
        if ring_island:
            lines.append(_arc("G3", (shank_x, yc + lo), (shank_x, yc + hi), (rx, yc)))
        else:
            # Out along the low side's outer rows and back along the high
            # side's, zigzag: right across the zone, step, left to beside the
            # blank's left end, where the cutter crosses to the high side.
            low = sorted((dy for dy in outer_rows if dy < 0), reverse=True)
            high = sorted(dy for dy in outer_rows if dy > 0)
            for k, dy in enumerate(low + high[::-1]):
                lines += [
                    f"G1 Y{_r(yc + dy):.3f} F{{feed}}",
                    f"G1 X{_r(x_zone if k % 2 == 0 else x_left):.3f} F{{feed}}",
                ]
        return lines + [f"G0 Z{clear:.3f}"]

    def skim_fork(yc: float) -> list[str]:
        """The fork's far face: one pass along the axis from beside the
        blank's right end to the fork's base."""
        clear, safe = _r(t_max + CLEAR_MM), _r(t_max + SAFE_MM)
        return [
            f"G0 Z{clear:.3f}",
            f"G0 {_xy(x_right, yc)}",
            f"G0 Z{safe:.3f}",
            f"G1 Z{_r(fork_t):.3f} F{{feed}}",
            f"G1 X{_r(fb):.3f} F{{feed}}",
            f"G0 Z{clear:.3f}",
        ]

    def ring_face(yc: float, z: float, top: float) -> list[str]:
        """Rows across the ring's face, on the rough rows' lines: each from
        beside the ring's left to no further right than the rough rows went
        (``x_zone``), so the cutter stays in the roughed zone (the waste past
        it is whole). The first row plunges into the floor stock at the slow
        feed."""
        clear, safe = _r(top + CLEAR_MM), _r(top + SAFE_MM)
        lines = [f"G0 Z{clear:.3f}"]
        for k, dy in enumerate(dys):
            span = math.sqrt(max(big_r**2 - dy**2, 0.0)) + r + APPROACH_MM
            right = min(rx + span, x_zone)
            a, b = (rx - span, right) if k % 2 == 0 else (right, rx - span)
            if k == 0:
                lines += [
                    f"G0 {_xy(a, yc + dy)}",
                    f"G0 Z{safe:.3f}",
                    f"G1 Z{_r(z):.3f} F{{plunge}}",
                ]
            else:
                lines.append(f"G1 {_xy(a, yc + dy)} F{{feed}}")
            lines.append(f"G1 X{_r(b):.3f} F{{feed}}")
        return lines + [f"G0 Z{clear:.3f}"]

    def band_lines(yc: float, levels: list[float], top: float) -> list[str]:
        """The 1/8 in end mill's circle round the ring at its offset."""
        clear, safe = _r(top + CLEAR_MM), _r(top + SAFE_MM)
        c = (rx, yc)
        a0, a1 = (rx + big8, yc), (rx - big8, yc)
        lines = [f"G0 Z{clear:.3f}", f"G0 {_xy(*a0)}", f"G0 Z{safe:.3f}"]
        for z in levels:
            lines += [
                f"G1 Z{_r(z):.3f} F{{feed}}",
                _arc("G3", a0, a1, c),
                _arc("G3", a1, a0, c),
            ]
        return lines + [f"G0 Z{clear:.3f}"]

    def side_pockets(
        side: dict[str, float], top: float, rough: bool
    ) -> tuple[list[str], list[float], list[str]]:
        """(1/2 in lines, the 1/8 in band's levels, band lines) for one face,
        ``top`` the stock's top on it."""
        lines: list[str] = []
        if rough:
            upper = _levels(top, side["ring_rough"], level_max)
            lower = _levels(side["ring_rough"], side["floor_rough"], level_max)
            band = _levels(
                side["ring_rough"], side["floor_rough"], p["band_level_max_mm"]
            )
        else:
            upper, lower = [], [side["floor"]]
            band = _levels(side["floor_rough"], side["floor"], p["band_level_max_mm"])
        for yc in centres:
            above = top
            for z in upper:
                lines += pocket_level(yc, z, top, False, above)
                above = z
            if not rough:
                lines += ring_face(yc, side["ring"], top)
                above = side["floor_rough"]
            for z in lower:
                lines += pocket_level(yc, z, top, True, above)
                above = z
        band_out = [ln for yc in centres for ln in band_lines(yc, band, top)]
        return lines, band, band_out

    # Side 2's rough: the skim of the fork's far face, then the rough levels
    # from the stock's top.
    skim2 = [ln for yc in centres for ln in skim_fork(yc)]
    rough2, band_rough2_levels, band_rough2 = side_pockets(side2, t_max, True)
    rough2 = skim2 + rough2
    rough1, band_rough1_levels, band_rough1 = side_pockets(side1, 0.0, True)
    finish1, band1_levels, band1 = side_pockets(side1, 0.0, False)
    finish2, band2_levels, band2 = side_pockets(side2, t_max, False)

    # The end: trim the right end to the crown through the full thickness,
    # then cut through round each fork's end, from the crown along both its
    # sides to past the slot's floor (both faces' contours took the kerf
    # there to the shank's faces).
    trim_x = crown_x + r
    trim = _side(
        [trim_x], [-through], (r + APPROACH_MM, -load - r - APPROACH_MM), t_max
    )
    end_levels = _levels(shank_far, shank_near - through, level_max)
    end_zone: list[str] = []
    clear2, safe2 = _r(t_max + CLEAR_MM), _r(t_max + SAFE_MM)
    for yc in centres:
        cc = rx + g["crown"]
        rc = w + r
        apex = (cc + rc, yc)
        for sign, motion in ((1.0, "G3"), (-1.0, "G2")):
            side_pt = (cc, yc + sign * rc)
            for z in end_levels:
                end_zone += [
                    f"G0 Z{clear2:.3f}",
                    f"G0 {_xy(*apex)}",
                    f"G0 Z{safe2:.3f}",
                    f"G1 Z{_r(z):.3f} F{{feed}}",
                    _arc(motion, apex, side_pt, (cc, yc)),
                    f"G1 X{_r(slot_floor_x - FORK_OVERLAP_MM):.3f} F{{feed}}",
                ]
        end_zone.append(f"G0 Z{clear2:.3f}")
    finish2 = finish2 + trim + end_zone

    # The bores: every blank's rough levels, then every blank's finish
    # circle and its spring pass (the check orders clearing before passes).
    # Each rough comes down at the cutting feed to the ring's face, through
    # the air the finish of side 2 left over it, then plunges into metal at
    # the slow feed.
    bore: list[str] = []
    for yc in centres:
        c = (rx, yc)
        a, b = (rx + rough_rr, yc), (rx - rough_rr, yc)
        bore += [
            f"G0 Z{clear2:.3f}",
            f"G0 {_xy(*c)}",
            f"G0 Z{safe2:.3f}",
            f"G1 Z{_r(ring_far):.3f} F{{feed}}",
        ]
        for z in bore_levels:
            bore += [
                f"G1 Z{_r(z):.3f} F{{plunge}}",
                f"G1 {_xy(*a)} F{{feed}}",
                _arc("G2", a, b, c),
                _arc("G2", b, a, c),
                f"G1 {_xy(*c)} F{{feed}}",
            ]
        bore.append(f"G0 Z{clear2:.3f}")
    # Each finish circle: down the roughed centre to the full depth, onto the
    # circle on a half-circle lead-in tangent to it (no plunge on the wall),
    # the finish lap and the spring lap, then off it on the other half of
    # that circle back to the centre before the retract (no rapid up the
    # finished wall).
    for yc in centres:
        c = (rx, yc)
        a, b = (rx + finish_rr, yc), (rx - finish_rr, yc)
        lead = (rx + finish_rr / 2, yc)
        bore += [
            f"G0 {_xy(*c)}",
            f"G0 Z{safe2:.3f}",
            f"G1 Z{_r(bore_levels[-1]):.3f} F{{feed}}",
            _arc("G2", c, a, lead),
            _arc("G2", a, b, c),
            _arc("G2", b, a, c),
            _arc("G2", a, b, c),
            _arc("G2", b, a, c),
            _arc("G2", a, c, lead),
            f"G0 Z{clear2:.3f}",
        ]
    # T1 parked for the saw's mounting and touch-off (Setup 5): up to the
    # park height, then along X past the crowns, then along Y over the fork
    # against the fixed jaw.
    bore += [
        f"G0 Z{_r(park_z):.3f}",
        f"G0 X{_r(touch[0]):.3f}",
        f"G0 Y{_r(touch[1]):.3f}",
    ]

    # The slot: the saw's passes along +Y, each Z level in steps into the
    # crown: with an M3 saw right of the forks a pass along +Y is
    # conventional (along -Y it would climb, and a slitting saw climbing
    # grabs and feeds itself in). Between passes the saw rises to
    # saw_clear, its stack's lowest point clear over the stock.
    slot = _side(
        saw_xs,
        saw_zs,
        (-load - saw_r - APPROACH_MM, saw_r + APPROACH_MM),
        t_max,
        saw_clear,
    )

    # The pin holes.
    pins = [(rx + g["crown"], yc) for yc in centres]
    clear_f = fork_t + CLEAR_MM
    pin_spot = [
        ln for xy in pins for ln in _spot(xy, fork_t, fork_t - spot_depth, clear_f)
    ]
    pin_drill = [
        ln for xy in pins for ln in _pecked(xy, fork_t, drill_tip, peck, clear_f)
    ]
    pin_ream = [ln for xy in pins for ln in _reamed(xy, fork_t, ream_tip, clear_f)]

    # The outline and its tabs, rod by rod.
    elements: list[dict[str, Any]] = []
    tabs: list[dict[str, Any]] = []
    outline: list[str] = []
    x_end = slot_floor_x + FORK_OVERLAP_MM
    for k, yc in enumerate(centres):
        name = f"rod {k + 1}"
        c = (rx, yc)
        j_top = (rx + jx8, yc + half + r8)
        j_bot = (rx + jx8, yc - half - r8)
        els = [
            {
                "name": f"{name} bottom flank",
                "start": (rx + jx8, yc - half),
                "end": (fb - k8, yc - half),
            },
            {
                "name": f"{name} bottom fork side",
                "start": (fb, yc - w),
                "end": (x_end, yc - w),
            },
            {
                "name": f"{name} top fork side",
                "start": (x_end, yc + w),
                "end": (fb, yc + w),
            },
            {
                "name": f"{name} top flank",
                "start": (fb - k8, yc + half),
                "end": (rx + jx8, yc + half),
            },
            {
                "name": f"{name} ring top",
                "start": _polar(c, big_r, c8),
                "end": (rx - big_r, yc),
                "centre": c,
            },
            {
                "name": f"{name} ring bottom",
                "start": (rx - big_r, yc),
                "end": _polar(c, big_r, -c8),
                "centre": c,
            },
        ]
        for e in els:
            e["tol"] = OUTLINE_TOL_MM
        elements += els
        boxes = []
        for side, x in bar_tabs:
            sign = 1.0 if side == "top" else -1.0
            y_span = sorted((yc + sign * (half - 1.0), yc + sign * (half + r8 + 1.0)))
            boxes.append(
                {
                    "name": f"{name} {side} x{x:g}",
                    "kind": "bar",
                    "x": (rx + x - tab_half, rx + x + tab_half),
                    "y": tuple(y_span),
                }
            )
        for deg in ring_tabs:
            # The box round the tab's arcs alone: the ring's edge (less a
            # margin inward) and the cutter's path, between the hop's ends
            # and through its middle (an arc over an axis bulges past its
            # ends). On a slanted tab the path past either end leaves it.
            corners = [
                _polar(c, rr, a)
                for rr in (big_r - 1.0, big8)
                for a in (deg - tab_deg, deg, deg + tab_deg)
            ]
            xs = sorted(q[0] for q in corners)
            ys = sorted(q[1] for q in corners)
            boxes.append(
                {
                    "name": f"{name} ring {deg:g}°",
                    "kind": "ring",
                    "deg": deg,
                    "half_deg": tab_deg,
                    "x": (xs[0], xs[-1]),
                    "y": (ys[0], ys[-1]),
                }
            )
        for box in boxes:
            box.update(top=tab_top, floor=shank_near, thickness=tab_t)
            tabs.append(
                {
                    key: box[key]
                    for key in ("name", "x", "y", "top", "floor", "thickness")
                }
            )
        start = (rx + start_x, yc - half - r8)
        outline += [
            f"G0 Z{clear2:.3f}",
            f"G0 {_xy(*start)}",
            f"G0 Z{safe2:.3f}",
            f"G1 Z{_r(shank_far + SAFE_MM):.3f} F{{feed}}",
        ]
        for z in out_levels:
            corner_b = (fb - k8, yc - half - r8)
            corner_t = (fb - k8, yc + half + r8)
            outline.append(f"G1 Z{_r(z):.3f} F{{plunge}}")
            outline += _hops(start, corner_b, z, boxes)
            outline += [
                _arc("G3", corner_b, (fb, yc - w - r8), (fb, yc - w)),
                f"G1 X{_r(x_end):.3f} F{{feed}}",
                f"G0 Z{clear2:.3f}",
                f"G0 {_xy(x_end, yc + w + r8)}",
                f"G0 Z{safe2:.3f}",
                f"G1 Z{_r(z):.3f} F{{feed}}",
                f"G1 X{_r(fb):.3f} F{{feed}}",
                _arc("G3", (fb, yc + w + r8), corner_t, (fb, yc + w)),
            ]
            outline += _hops(corner_t, j_top, z, boxes)
            outline += _ring_arc(c, big8, c8, 360.0 - c8, z, boxes)
            outline += _hops(j_bot, start, z, boxes)
        outline.append(f"G0 Z{clear2:.3f}")

    # The roots, rod by rod, corner by corner, level by level.
    big5 = big_r + r5
    j5 = math.sqrt(big5**2 - (half + r5) ** 2)
    c5 = math.degrees(math.atan2(half + r5, j5))
    d5 = math.sqrt(r5**2 - (r5 - (w - half)) ** 2)
    # Each flank run reaches past where the 1/8 in cutter's round leaves the
    # flank (ring side jx8, step side fb - k8) from where the 5/64 in
    # cutter's own round meets it (j5, fb - d5): shorter, it leaves a sliver
    # of the R.0625 on the flank, over R.040 MAX.
    if ROOT_RUN_MM < max(jx8 - j5, k8 - d5) + OUTLINE_TOL_MM:
        raise ValueError("a root pass stops short of the 1/8 in cutter's round")
    # The root passes stay off every bar tab: the tab's material spans its
    # width along the flank, out from the flank by the kerf.
    tab_w = p["tab_width_mm"]
    for _flank, x in bar_tabs:
        if not (
            j5 + ROOT_RUN_MM + r5 < x - tab_w / 2
            and x + tab_w / 2 < fb_rel - d5 - ROOT_RUN_MM - r5
        ):
            raise ValueError(f"a root pass reaches the tab at x {x:g}")
    root_elements: list[dict[str, Any]] = []
    roots: list[str] = []
    for k, yc in enumerate(centres):
        name = f"rod {k + 1}"
        c = (rx, yc)
        els = [
            {
                "name": f"{name} top ring root flank",
                "start": (rx + j5 + ROOT_RUN_MM, yc + half),
                "end": (rx + j5, yc + half),
            },
            {
                "name": f"{name} top ring root",
                "start": _polar(c, big_r, c5),
                "end": _polar(c, big_r, c5 + ROOT_ARC_DEG),
                "centre": c,
            },
            {
                "name": f"{name} bottom ring root",
                "start": _polar(c, big_r, -c5 - ROOT_ARC_DEG),
                "end": _polar(c, big_r, -c5),
                "centre": c,
            },
            {
                "name": f"{name} bottom ring root flank",
                "start": (rx + j5, yc - half),
                "end": (rx + j5 + ROOT_RUN_MM, yc - half),
            },
            {
                "name": f"{name} bottom step flank",
                "start": (fb - d5 - ROOT_RUN_MM, yc - half),
                "end": (fb - d5, yc - half),
            },
            {
                "name": f"{name} bottom step side",
                "start": (fb, yc - w),
                "end": (fb + ROOT_SIDE_MM, yc - w),
            },
            {
                "name": f"{name} top step side",
                "start": (fb + ROOT_SIDE_MM, yc + w),
                "end": (fb, yc + w),
            },
            {
                "name": f"{name} top step flank",
                "start": (fb - d5, yc + half),
                "end": (fb - d5 - ROOT_RUN_MM, yc + half),
            },
        ]
        for e in els:
            e["tol"] = OUTLINE_TOL_MM
        root_elements += els
        paths = [
            (
                (rx + j5 + ROOT_RUN_MM, yc + half + r5),
                [
                    f"G1 {_xy(rx + j5, yc + half + r5)} F{{feed}}",
                    _arc(
                        "G3",
                        (rx + j5, yc + half + r5),
                        _polar(c, big5, c5 + ROOT_ARC_DEG),
                        c,
                    ),
                ],
            ),
            (
                _polar(c, big5, -c5 - ROOT_ARC_DEG),
                [
                    _arc(
                        "G3",
                        _polar(c, big5, -c5 - ROOT_ARC_DEG),
                        (rx + j5, yc - half - r5),
                        c,
                    ),
                    f"G1 {_xy(rx + j5 + ROOT_RUN_MM, yc - half - r5)} F{{feed}}",
                ],
            ),
            (
                (fb - d5 - ROOT_RUN_MM, yc - half - r5),
                [
                    f"G1 {_xy(fb - d5, yc - half - r5)} F{{feed}}",
                    _arc(
                        "G3", (fb - d5, yc - half - r5), (fb, yc - w - r5), (fb, yc - w)
                    ),
                    f"G1 {_xy(fb + ROOT_SIDE_MM, yc - w - r5)} F{{feed}}",
                ],
            ),
            (
                (fb + ROOT_SIDE_MM, yc + w + r5),
                [
                    f"G1 {_xy(fb, yc + w + r5)} F{{feed}}",
                    _arc(
                        "G3", (fb, yc + w + r5), (fb - d5, yc + half + r5), (fb, yc + w)
                    ),
                    f"G1 {_xy(fb - d5 - ROOT_RUN_MM, yc + half + r5)} F{{feed}}",
                ],
            ),
        ]
        for start, body in paths:
            # Each start is in the 1/8 in cutter's cut, through the waste:
            # up over the stock and back to it for each level.
            for z in root_levels:
                roots += [
                    f"G0 Z{safe2:.3f}",
                    f"G0 {_xy(*start)}",
                    f"G1 Z{_r(z):.3f} F{{feed}}",
                    *body,
                ]
        roots.append(f"G0 Z{clear2:.3f}")

    def job(
        key,
        label,
        tool,
        dia,
        shape,
        rpm,
        feed,
        plunge_feed,
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
            "plunge": plunge_feed,
            "frame": frame,
            "label": label,
            "stock": stock_box,
            "ops": [[key, label, lines]],
        }

    centre_deg = CENTRE_DRILL["point_deg"]
    jobs = [
        job(
            "rough_2",
            "rough side 2",
            "em-half",
            em,
            "endmill",
            em_rpm,
            em_feed,
            plunge,
            "two",
            stock_two,
            rough2,
            3,
        ),
        job(
            "band_rough_2",
            "ring band rough side 2",
            "em-eighth",
            e8,
            "endmill",
            e8_rpm,
            e8_feed,
            plunge8,
            "two",
            stock_two,
            band_rough2,
            3,
        ),
        job(
            "rough_1",
            "rough side 1",
            "em-half",
            em,
            "endmill",
            em_rpm,
            em_feed,
            plunge,
            "one",
            stock_one,
            rough1,
            3,
        ),
        job(
            "band_rough_1",
            "ring band rough side 1",
            "em-eighth",
            e8,
            "endmill",
            e8_rpm,
            e8_feed,
            plunge8,
            "one",
            stock_one,
            band_rough1,
            3,
        ),
        job(
            "finish_1",
            "finish side 1",
            "em-half",
            em,
            "endmill",
            em_rpm,
            em_feed,
            plunge,
            "one",
            stock_one,
            finish1,
            3,
        ),
        job(
            "band_1",
            "ring band side 1",
            "em-eighth",
            e8,
            "endmill",
            e8_rpm,
            e8_feed,
            plunge8,
            "one",
            stock_one,
            band1,
            3,
        ),
        job(
            "finish_2",
            "finish side 2, trim and clear the end",
            "em-half",
            em,
            "endmill",
            em_rpm,
            em_feed,
            plunge,
            "two",
            stock_two,
            finish2,
            3,
        ),
        job(
            "band_2",
            "ring band side 2",
            "em-eighth",
            e8,
            "endmill",
            e8_rpm,
            e8_feed,
            plunge8,
            "two",
            stock_two,
            band2,
            3,
        ),
        job(
            "bore",
            "bore the rings",
            "em-half",
            em,
            "endmill",
            bore_rpm,
            bore_feed,
            plunge,
            "two",
            stock_two,
            bore,
            3,
        ),
        job(
            "slot",
            "saw the fork slots",
            "saw",
            saw,
            "slittingsaw",
            saw_rpm,
            saw_feed,
            saw_feed,
            "two",
            stock_two,
            slot,
        ),
        job(
            "pin_spot",
            "spot the pin holes",
            "spot",
            CENTRE_DRILL["body_mm"],
            "drill",
            spot_rpm,
            spot_feed,
            spot_feed,
            "two",
            stock_two,
            pin_spot,
            2,
            centre_deg,
        ),
        job(
            "pin_drill",
            "drill the pin holes #49",
            "drill-49",
            tools["drill-49"],
            "drill",
            drill_rpm,
            drill_feed,
            drill_feed,
            "two",
            stock_two,
            pin_drill,
            2,
            DRILL_POINT_DEG,
        ),
        job(
            "pin_ream",
            "ream the pin holes",
            "reamer-0775",
            tools["reamer-0775"],
            "reamer",
            ream_rpm,
            ream_feed,
            ream_feed,
            "two",
            stock_two,
            pin_ream,
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
            "two",
            stock_two,
            outline,
            3,
        ),
        job(
            "roots",
            "recut the inside corners",
            "em-5-64",
            e5,
            "endmill",
            root_rpm,
            root_feed,
            root_feed,
            "two",
            stock_two,
            roots,
            2,
        ),
    ]

    # Keep-outs: the jaws beside the load from Z0 (side 2 up) or the
    # plate (side 1 up) to their top; the islands below their faces; each
    # blank's frame below its top.
    def jaws(top: float) -> list[dict[str, Any]]:
        return [
            _box(
                "moving jaw",
                (jaw_x0, jaw_x0 + jaw_w),
                (-load - JAW_DEPTH_MM, -load),
                top,
            ),
            _box("fixed jaw", (jaw_x0, jaw_x0 + jaw_w), (0.0, JAW_DEPTH_MM), top),
        ]

    jaws2 = jaws(jaw_top)
    jaws1 = jaws(jaw_top - t_min)

    def frames_of(top: float) -> list[dict[str, Any]]:
        out = []
        for k, yc in enumerate(centres):
            out += [
                _box(
                    f"blank {k + 1} frame +Y",
                    (0.0, slot_floor_x),
                    (yc + edge, yc + pitch / 2),
                    top,
                ),
                _box(
                    f"blank {k + 1} frame -Y",
                    (0.0, slot_floor_x),
                    (yc - pitch / 2, yc - edge),
                    top,
                ),
            ]
        return out

    def islands(side: dict[str, float]) -> tuple[list[dict], list[dict]]:
        boxes, circles = [], []
        cc = rx + g["crown"]
        for k, yc in enumerate(centres):
            boxes.append(_box(f"fork {k + 1}", (fb, cc), (yc - w, yc + w), side["top"]))
            circles.append(
                {
                    "name": f"crown {k + 1}",
                    "centre": [cc, yc],
                    "radius": w,
                    "z_top": side["top"],
                }
            )
            circles.append(
                {
                    "name": f"ring {k + 1}",
                    "centre": [rx, yc],
                    "radius": big_r,
                    "z_top": side["ring"],
                }
            )
        return boxes, circles

    # Points each pocket tool must clear: the shank and the outline's kerf
    # beside it from the ring to the fork's base, and the fork contour's cut
    # up to ``x_hi``; the ring's zone above the ring's face; round the ring
    # for the band.
    def pocket_points(yc: float, x_hi: float) -> list[list[float]]:
        pts = []
        x = shank_x + 1.0
        while x <= fb - 1.0:
            for dy in (-kerf + 0.3, -4.0, 0.0, 4.0, kerf - 0.3):
                pts.append([_r(x), _r(yc + dy)])
            x += 6.0
        x = fb + 1.0
        while x <= min(x_hi, rx + g["crown"]):
            for dy in (w + 0.5, w + 2 * r - 0.5):
                pts += [[_r(x), _r(yc + dy)], [_r(x), _r(yc - dy)]]
            x += 3.0
        return pts

    def zone_points(yc: float) -> list[list[float]]:
        pts = []
        for deg in range(0, 360, 30):
            for radius in (2.0, 10.0, big_r - 0.5, edge - 0.5):
                q = _polar((rx, yc), radius, deg)
                pts.append([_r(q[0]), _r(q[1])])
        return pts

    def band_points(yc: float) -> list[list[float]]:
        pts = []
        for deg in range(0, 360, 15):
            for radius in (big_r + 0.3, big_r + e8 - 0.3):
                q = _polar((rx, yc), radius, deg)
                pts.append([_r(q[0]), _r(q[1])])
        return pts

    tn = numbers
    expect: list[list[Any]] = []

    def common(name, z_top, tools_loaded, rpms, z_min):
        return [
            [
                name,
                "tool_changes",
                {"z_top": z_top, "tools": tools_loaded, "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[x] for x in rpms]}],
            [name, "pauses", {"z_top": z_top, "count": 0}],
            [name, "depth", {"z_min": _r(z_min)}],
        ]

    for name, side, rough, jaw_boxes, top, check_top in (
        ("CR01_rough_2", side2, True, jaws2, side2["top"], t_max),
        ("CR02_rough_1", side1, True, jaws1, 0.0, 0.0),
        ("CR03_finish_1", side1, False, jaws1, 0.0, 0.0),
    ):
        floor = side["floor_rough"] if rough else side["floor"]
        expect += common(
            name, check_top, [tn["em-half"], tn["em-eighth"]], [em_rpm, e8_rpm], floor
        )
        boxes, circles = islands(side)
        pts = [q for yc in centres for q in pocket_points(yc, l_max)]
        expect += [
            [f"{name}@0", "rapids_clear", {"z_top": check_top}],
            [f"{name}@0", "air_feed", {"z_top": check_top}],
            [f"{name}@0", "cleared", {"points": pts, "radius": r, "z": _r(floor)}],
            [
                f"{name}@0",
                "keep_out",
                {
                    "radius": r,
                    "boxes": jaw_boxes + boxes + frames_of(check_top),
                    "circles": circles,
                },
            ],
            [f"{name}@1", "rapids_clear", {"z_top": check_top}],
            [f"{name}@1", "air_feed", {"z_top": check_top}],
            [
                f"{name}@1",
                "cleared",
                {
                    "points": [q for yc in centres for q in band_points(yc)],
                    "radius": r8,
                    "z": _r(floor),
                },
            ],
            [
                f"{name}@1",
                "keep_out",
                {
                    "radius": r8,
                    "boxes": jaw_boxes + frames_of(check_top),
                    "circles": circles,
                },
            ],
        ]
        if not rough:
            disc = []
            for yc in centres:
                for deg in range(0, 360, 30):
                    for radius in (2.0, 10.0, big_r - 0.5):
                        q = _polar((rx, yc), radius, deg)
                        disc.append([_r(q[0]), _r(q[1])])
            expect.append(
                [
                    f"{name}@0",
                    "cleared",
                    {"points": disc, "radius": r, "z": _r(side["ring"])},
                ]
            )
        else:
            expect.append(
                [
                    f"{name}@0",
                    "cleared",
                    {
                        "points": [q for yc in centres for q in zone_points(yc)],
                        "radius": r,
                        "z": _r(side["ring_rough"]),
                    },
                ]
            )
            if name == "CR01_rough_2":
                fork_pts = []
                for yc in centres:
                    for x in (fb + 2.0, rx + g["crown"]):
                        fork_pts += [
                            [_r(x), _r(yc + dy)] for dy in (-w + 0.5, 0.0, w - 0.5)
                        ]
                expect.append(
                    [
                        f"{name}@0",
                        "cleared",
                        {"points": fork_pts, "radius": r, "z": _r(side2["top"])},
                    ]
                )
    name = "CR04_finish_2"
    expect += common(
        name, t_max, [tn["em-half"], tn["em-eighth"]], [em_rpm, e8_rpm], -through
    )
    boxes, circles = islands(side2)
    pts = [q for yc in centres for q in pocket_points(yc, slot_floor_x - r)]
    end_pts = []
    for yc in centres:
        x = slot_floor_x + 0.5
        while x < rx + g["crown"]:
            for dy in (w + 0.5, w + r, w + 2 * r - 0.5):
                end_pts += [[_r(x), _r(yc + dy)], [_r(x), _r(yc - dy)]]
            x += 3.0
    trim_pts = [
        [_r(crown_x + 0.3), _r(y)]
        for y in (-0.5, -pitch + 0.5, -pitch - 0.5, -load + 0.5)
    ]
    expect += [
        [f"{name}@0", "rapids_clear", {"z_top": t_max}],
        [f"{name}@0", "air_feed", {"z_top": t_max}],
        [f"{name}@0", "cleared", {"points": pts, "radius": r, "z": _r(side2["floor"])}],
        [
            f"{name}@0",
            "cleared",
            {"points": end_pts, "radius": r, "z": _r(end_levels[-1])},
        ],
        [f"{name}@0", "cleared", {"points": trim_pts, "radius": r, "z": _r(-through)}],
        [
            f"{name}@0",
            "keep_out",
            {
                "radius": r,
                "boxes": jaws2 + boxes + frames_of(t_max),
                "circles": circles,
            },
        ],
        [f"{name}@1", "rapids_clear", {"z_top": t_max}],
        [f"{name}@1", "air_feed", {"z_top": t_max}],
        [
            f"{name}@1",
            "cleared",
            {
                "points": [q for yc in centres for q in band_points(yc)],
                "radius": r8,
                "z": _r(side2["floor"]),
            },
        ],
        [
            f"{name}@1",
            "keep_out",
            {"radius": r8, "boxes": jaws2 + frames_of(t_max), "circles": circles},
        ],
    ]

    name = "CR05_bore"
    expect += common(name, t_max, [tn["em-half"]], [bore_rpm], bore_levels[-1])
    bore_elements = []
    for k, yc in enumerate(centres):
        rb = bore_d / 2
        # The centre as the post prints it (a radial move in or out is then
        # square to the bore, not a hair against its way); quarters from 45°
        # off the radial moves in and out at 0°.
        c = (_r(rx), _r(yc))
        for q, (a0, a1) in enumerate(
            ((45, -45), (-45, -135), (-135, -225), (-225, -315))
        ):
            bore_elements.append(
                {
                    "name": f"bore {k + 1} quarter {q + 1}",
                    "start": _polar(c, rb, a0),
                    "end": _polar(c, rb, a1),
                    "centre": c,
                    "tol": OUTLINE_TOL_MM,
                }
            )
    expect += [
        [name, "rapids_clear", {"z_top": t_max}],
        [name, "air_feed", {"z_top": t_max}],
        [
            name,
            "outline",
            {
                "elements": bore_elements,
                "z_top": ring_far,
                "passes": [{"offset": r, "levels": [_r(bore_levels[-1])]}],
                "clearing": [
                    {
                        "x": [rx - big_r, rx + big_r],
                        "levels": [_r(z) for z in bore_levels],
                    }
                ],
                # Each finish lap's half-circle lead-in and lead-out, inside
                # the roughed bore at its full depth.
                "leads": [
                    {
                        "centre": [_r(rx), _r(yc)],
                        "radius": finish_rr,
                        "levels": [_r(bore_levels[-1])],
                    }
                    for yc in centres
                ],
            },
        ],
        [name, "keep_out", {"radius": r, "boxes": jaws2}],
    ]

    # The arbor round the saw, part by part: its reach from the saw's lower
    # face (the programmed Z) down (lo) and up (hi), and its radius. No move,
    # rapid or feed, brings a part into the stock, the plate or the vise:
    # the blanks over the support plate and the jaws stand on the vise; the
    # blanks' ends past the plate overhang air from Z0 to their top, which
    # the nut may pass under while the saw cuts.
    plate_end = p["support_plate_length_mm"]
    solids = jaws2 + [
        _box("the blanks over the plate", (0.0, plate_end), (-load, 0.0), t_max),
        {
            **_box(
                "the blanks past the plate", (plate_end, crown_x), (-load, 0.0), t_max
            ),
            "z_bottom": 0.0,
        },
        _box("the vise past the plate", (plate_end, jaw_x0 + jaw_w), (-load, 0.0), 0.0),
    ]

    def reach(part: str, lo: float, hi: float | None) -> list[dict[str, Any]]:
        """``solids`` as bands of the programmed Z in which a part reaching
        ``lo`` to ``hi`` from it (``hi`` None: on up) would meet them."""
        out = []
        for solid in solids:
            moved = {**solid, "name": f"{solid['name']} ({part})"}
            moved["z_top"] = _r(solid["z_top"] - lo)
            if "z_bottom" in solid and hi is not None:
                moved["z_bottom"] = _r(solid["z_bottom"] - hi)
            else:
                moved.pop("z_bottom", None)
            out.append(moved)
        return out

    name = "CR06_slot"
    expect += [
        [name, "tool_changes", {"z_top": t_max, "tools": [], "loads_first": False}],
        [name, "spindle", {"rpm": [[saw_rpm]]}],
        [name, "pauses", {"z_top": t_max, "count": 0}],
        [name, "depth", {"z_min": _r(min(saw_zs))}],
        [name, "rapids_clear", {"z_top": t_max}],
        [name, "air_feed", {"z_top": t_max}],
        [
            name,
            "side_passes",
            {
                "axis": "X",
                "final": _r(saw_xs[-1]),
                "raw": _r(crown_x + saw_r),
                "max_step": slot_steps[0],
                "direction": 1,
                "span": load,
                "below_z": t_max,
            },
        ],
        [name, "keep_out", {"radius": saw_r, "boxes": jaws2}],
    ]
    # Each arbor part as cut, and as proved in air (Z0 raised
    # AIR_PROOF_RAISE_MM: every part that much higher over the same shapes,
    # where the nut that passes under the crowns must not rise into them).
    for lift, when in ((0.0, ""), (AIR_PROOF_RAISE_MM, ", proved in air")):
        for part, radius_of, lo, hi in (
            ("spacers above the saw", collar_r, saw_t, None),
            ("spacers below the saw", collar_r, -below, 0.0),
            ("the arbor's nut", nut_r, -below, -spacer_below),
        ):
            expect.append(
                [
                    name,
                    "keep_out",
                    {
                        "radius": radius_of,
                        "boxes": reach(
                            part + when, lo + lift, None if hi is None else hi + lift
                        ),
                    },
                ]
            )

    name = "CR07_pin"
    expect += common(
        name,
        t_max,
        [tn["spot"], tn["drill-49"], tn["reamer-0775"]],
        [spot_rpm, drill_rpm, ream_rpm],
        min(drill_tip, ream_tip),
    )
    pin_xy = [[_r(x), _r(y)] for x, y in pins]
    for k, (bottom, radius) in enumerate(
        (
            (fork_t - spot_depth, CENTRE_DRILL["body_mm"] / 2),
            (drill_tip, tools["drill-49"] / 2),
            (ream_tip, tools["reamer-0775"] / 2),
        )
    ):
        expect += [
            [f"{name}@{k}", check, kwargs]
            for check, kwargs in (
                ("holes", {"centres": pin_xy, "z_bottom": _r(bottom)}),
                ("rapids_clear", {"z_top": t_max, "open_holes": pin_xy}),
                ("vertical_below_top", {"z_top": fork_t}),
                ("air_feed", {"z_top": fork_t}),
                ("keep_out", {"radius": radius, "boxes": jaws2}),
            )
        ]
    expect.append([f"{name}@2", "feed_out", {"z_top": fork_t}])

    name = "CR08_outline"
    expect += common(
        name,
        t_max,
        [tn["em-eighth"], tn["em-5-64"]],
        [e8_rpm, root_rpm],
        shank_near - through,
    )
    expect += [
        [f"{name}@0", "rapids_clear", {"z_top": t_max}],
        [f"{name}@0", "air_feed", {"z_top": t_max}],
        [
            f"{name}@0",
            "outline",
            {
                "elements": elements,
                "z_top": shank_far,
                "passes": [{"offset": r8, "levels": [_r(z) for z in out_levels]}],
                "tabs": tabs,
            },
        ],
        [f"{name}@0", "keep_out", {"radius": r8, "boxes": jaws2}],
        [f"{name}@1", "rapids_clear", {"z_top": t_max}],
        [f"{name}@1", "air_feed", {"z_top": t_max}],
        [
            f"{name}@1",
            "outline",
            {
                "elements": root_elements,
                "z_top": shank_far,
                "passes": [{"offset": r5, "levels": [_r(z) for z in root_levels]}],
            },
        ],
        [
            f"{name}@1",
            "keep_out",
            {
                "radius": r5,
                "boxes": jaws2
                + [
                    _box(
                        f"rod {k + 1} {side} tab x{x:g}",
                        (rx + x - tab_w / 2, rx + x + tab_w / 2),
                        (yc + half, yc + half + e8)
                        if side == "top"
                        else (yc - half - e8, yc - half),
                        tab_top,
                    )
                    for k, yc in enumerate(centres)
                    for side, x in bar_tabs
                ],
            },
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
        "levels": {
            "band_rough_2": band_rough2_levels,
            "band_rough_1": band_rough1_levels,
            "band_1": band1_levels,
            "band_2": band2_levels,
            "end": end_levels,
            "bore": bore_levels,
            "outline": out_levels,
            "roots": root_levels,
        },
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
            f"Connecting rod side {key} up",
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
