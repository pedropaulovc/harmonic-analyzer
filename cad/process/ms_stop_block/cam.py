"""FreeCAD CAM recipe for MHA-MS-02, the measuring-stick stop block.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The block's sizes come
from the feature export (its envelope, the rebate, its corner relief, the
roof chamfers, the thumb hole and the two plate holes); the bar, the skims,
face levels, the rebate's aims and steps, the chamfer offset, spots, pecks,
tap reaches and the holding from ``plan.toml`` ``[parameters]`` and
``milling_cuts``; cutter diameters, speeds and feeds from the shop
(``shop/``). Every path is written here (``rt.custom``): straight lines a
recipe can state exactly. Typed here, because neither record carries them:
the #2 centre drill's catalogue geometry (it sets the spot depth), the twist
drills' 118° point, the machine's Z top for the tap files' retract, the
approach, safe and clearance heights, the face overhang and the vise jaws'
depth (keep-out shapes only).

Route (plan text in ``plan.toml``): a slice of the 3/4 × 1-1/4 C360 bar,
the bar's 1-1/4 width along the block's length X, its 3/4 thickness the
height Y, the sawn slice the depth Z. Lying on the stacked parallels: MS01
skims the sawn back face, MS02 faces the mating face to the depth; MS03 skims
the locating edge, MS04 faces the top to the height. Mating face up, gripped
across the bar's as-bought 1-1/4 ends (the waste beyond both final ends):
MS05_rebate mills the rebate with the 1/8 in end mill, MS05_relief plunge-mills
its corner relief with the 1/16 in long-reach end mill, both stopping short of the bar's ends, so the
roof is never squeezed by the jaws. Upright, gripped on the mating and back
faces: MS06 faces the locating end and chamfers its roof corner, MS07 the
far end to the length. Lying as for MS04 again, the locating edge down and
the top face up: MS07b chamfers the far end's roof corner (upright, the
finished far end stands too little over the jaws for the chamfer mill's
point: issue #3607). Lying, locating edge up: MS08 spots and drills the
thumb hole into the rebate; MS09 brings the tap guide over it. After
MHA-MS-03's pair pilot: MS10 and MS11 bring it over each plate hole.

Work frames (G54), each set in its setup; model frame x along the length
from the locating end, y up from the locating edge, z into the block from
the mating face:
- MS01: X0 the bar's left end, Y0 the fixed jaw's face, Z0 the faced back
  face. MS02: the same X0 Y0, Z0 the stacks' top (the back face).
- MS03: X0 Y0 as MS01, Z0 the faced locating edge. MS04: Z0 the stacks' top.
- MS05: X0 the top face (left), Y0 the fixed jaw's face (the bar's
  locating-end side), Z0 the mating face; +Y toward the fixed jaw.
- MS06/MS07: X0 the top face (left), Y0 the fixed jaw's face, Z0 the
  parallels' top.
- MS07b: X0 the far end (right, the part to -X), Y0 the fixed jaw's face
  (the mating face), Z0 the stacks' top (the locating edge).
- MS08/MS09: X0 the locating end (right, the part to -X), Y0 the fixed jaw's
  face (the mating face), Z0 the stacks' top (the top face).
- MS10/MS11: X0 the locating edge (right, the part to -X), Y0 the fixed
  jaw's face (the locating end).

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock. The
holes are tapped by hand (FluidNC cannot rigid-tap; owner, Pedro,
2026-11-17), the T-handle wrench's centre hole on the spring point of the
Fisher tap guide in the 1/2 in R8 collet (owner, Pedro, 2026-11-21: "use
https://littlemachineshop.com/products/tap-guide-fisher?variant=45472915226805
on r8 0.5 collet"), spindle off, the operator jogging Z down to push the
point home; each tap stop is a file of its
own that ends with M30 over its hole (FluidNC refuses jogs in an M0 hold,
http://wiki.fluidnc.com/en/features/single_block_mode).
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ms_stop_block"
COMMENT = "MHA-MS-02 stop block"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("MS01_back", ("back_face",)),
    ("MS02_mating", ("mating_face",)),
    ("MS03_edge", ("locating_edge",)),
    ("MS04_height", ("top_face",)),
    # The relief is its own file: the rebate is checked with the spindle
    # stopped at its end, and the relief's cutter is to buy, so the relief
    # may run on another day from a fresh zero.
    ("MS05_rebate", ("rebate",)),
    ("MS05_relief", ("relief",)),
    ("MS06_locating_end", (("locating_end",), ("locating_chamfer",))),
    ("MS07_far_end", ("far_end",)),
    ("MS07b_far_chamfer", ("far_chamfer",)),
    ("MS08_thumb", (("thumb_spot",), ("thumb_drill",))),
    ("MS09_thumb_tap", ("tap_thumb",)),
    ("MS10_plate_tap_1", ("tap_plate_1",)),
    ("MS11_plate_tap_2", ("tap_plate_2",)),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the taps and the files are not).
CAM_TOOLS = (
    "em-half",
    "em-eighth",
    "em-sixteenth",
    "chamfer",
    "spot",
    "drill-43",
    "tap-guide",
)
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included: the shop record names
# the tool, not its geometry.
CENTRE_DRILL = {
    "pilot_mm": 0.078125 * IN,
    "pilot_length_mm": 0.078125 * IN,
    "body_mm": 0.1875 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# The chamfer mill's included angle (shop: "90 Degree Cut"), taken as a sharp
# point; the plan's first-corner check catches a tip flat.
CHAMFER_DEG = 90.0
# A tap file's first motion: G53 G0 to machine Z0, the homed top (FluidNC
# sets an axis's machine position to its homing mpos_mm, default 0, and Z
# homes up); the owner (Pedro) confirmed it, answered in person 2026-11-21
# (cnc rulings record): machine Z = 0 is the top of travel after homing.
MACHINE_Z_TOP_MM = 0.0
# Face and chamfer passes start and finish this far clear of the stock.
APPROACH_MM = 2.54
# Faces reach at least this far past the faces the jaws grip.
FACE_OVERHANG_MM = 0.5
# Plunges and drill R planes start this far above the stock top.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# The relief cutter feeds down the cut rebate to this far above its floor.
RELIEF_ENTRY_MM = 0.1
# Keep-outs: each vise jaw's depth outward from the gripped face.
JAW_DEPTH_MM = IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# Class ZZ minus pin gauges (the shop's sets): a pin is up to this under its
# marked size, never over.
PIN_MINUS_MM = 0.0002 * IN
# The least wall a cutter test hole keeps to the slice's faces, the final
# end, the rebate and the other test hole.
TEST_WALL_MM = 0.75


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


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


def _levels(top: float, bottom: float, max_step: float) -> list[float]:
    """Equal step-down levels no deeper than ``max_step`` from ``top`` to
    ``bottom``, ``bottom`` last."""
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


def _close(a: float, b: float, what: str) -> None:
    if not math.isclose(a, b, abs_tol=1e-3):
        raise ValueError(f"{what} {a:g}, expected {b:.4f}")


def _spot_depth(dia: float) -> float:
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
    xy: tuple[float, float], top: float, tip: float, peck: float, clear: float
) -> list[str]:
    """Drill from ``top`` to ``tip`` in pecks of ``peck`` with a full retract
    to the R plane and a rapid back to just above the last peck. Moves to and
    from the hole run at ``clear``."""
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


def _stations(low: float, high: float, radius: float, woc: float) -> list[float]:
    """Face pass centres across ``low``..``high``, equally spaced, the fewest
    no wider apart than ``woc``: the first takes one step of the stock, the
    last reaches ``FACE_OVERHANG_MM`` past ``high``."""
    span = high - low + FACE_OVERHANG_MM
    n = math.ceil(span / woc - 1e-9)
    step = span / n
    return [_r(low - radius + step * (k + 1)) for k in range(n)]


def _face(
    levels: list[float], top: float, x: tuple[float, float], ys: list[float]
) -> list[str]:
    """Zigzag faces at ``levels``: at each, one X pass per Y in ``ys`` from
    beyond ``x[0]`` to beyond ``x[1]`` and back, alternating; every plunge,
    level change and stepover beside the stock."""
    clear = _r(top + CLEAR_MM)
    x0, x1 = _r(x[0]), _r(x[1])
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{x0:.3f} Y{ys[0]:.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
    ]
    for z in levels:
        lines.append(f"G1 Z{_r(z):.3f} F{{feed}}")
        for k, y in enumerate(ys):
            if k:
                lines.append(f"G1 Y{y:.3f} F{{feed}}")
            lines.append(f"G1 X{x1 if k % 2 == 0 else x0:.3f} F{{feed}}")
        if len(ys) % 2:
            lines.append(f"G1 X{x0:.3f} F{{feed}}")
        if z != levels[-1]:
            lines.append(f"G1 Y{ys[0]:.3f} F{{feed}}")
    return lines + [f"G0 Z{clear:.3f}"]


def _slot(
    x: float, ys: tuple[float, float], levels: list[float], entry: float | None
) -> tuple[list[str], float]:
    """A slot along Y at ``x``: plunged at alternate ends to each level (at
    the plunge feed), cut end to end at each. With ``entry`` the cutter first
    feeds down an open rebate to that Z. Returns the lines and the Y it ends
    at, still down."""
    ends = (_r(ys[0]), _r(ys[1]))
    lines = [f"G0 X{_r(x):.3f} Y{ends[0]:.3f}", f"G0 Z{SAFE_MM:.3f}"]
    if entry is not None:
        lines.append(f"G1 Z{_r(entry):.3f} F{{feed}}")
    for k, z in enumerate(levels):
        lines.append(f"G1 Z{_r(z):.3f} F{{plunge}}")
        lines.append(f"G1 Y{ends[(k + 1) % 2]:.3f} F{{feed}}")
    return lines, ends[len(levels) % 2]


def _chamfer(
    x: float, ys: tuple[float, float], top: float, tip: float, start_top: float
) -> list[str]:
    """One straight chamfer pass along Y at ``x``, the tip at ``tip``,
    plunged beside the stock, whose top is now ``top``; the tool change finds
    it at ``start_top``, the program's starting stock top, so the move over
    to the pass runs above that."""
    clear = _r(start_top + CLEAR_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{_r(x):.3f} Y{_r(ys[0]):.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
        f"G1 Z{_r(tip):.3f} F{{plunge}}",
        f"G1 Y{_r(ys[1]):.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def _det(rows: list[list[float]]) -> float:
    (a, b, c), (d, e, f), (g, h, i) = rows
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    f = features["features"]
    p = plan["parameters"]

    def plane(name: str) -> float:
        return f[name]["plane"]["value"]

    length = plane("far_end") - plane("locating_end")
    height = plane("top_face") - plane("locating_edge")
    depth = plane("back_face") - plane("mating_face")
    for name, key, value in (
        ("far_end", "length", length),
        ("top_face", "height", height),
    ):
        band = f[name][key]
        if not band[0] <= value <= band[1]:
            raise ValueError(
                f"model {key} {value:.4f} is outside the printed band {band}"
            )
    if any(plane(n) != 0.0 for n in ("locating_end", "locating_edge", "mating_face")):
        raise ValueError(
            "expected the locating end, locating edge and mating face at 0"
        )

    # The rebate (model frame): open to the mating face, the roof over it,
    # its back at the rebate width from the mating face, the relief a notch
    # in its back beside the roof. Aims: each band's middle.
    def mid(band: list[float]) -> float:
        return (band[0] + band[1]) / 2

    ceiling = height - mid(f["rebate_ceiling"]["roof_thickness"])
    # The ceiling's roughness in microinches, the inch drawing's unit.
    _agree(plan, "ceiling_ra_uin", round(f["rebate_ceiling"]["finish_ra"] / 0.0254))
    slot_height = mid(f["rebate_floor"]["rebate_height"])
    floor = ceiling - slot_height
    slot_depth = mid(f["rebate_back"]["rebate_width"])
    relief_depth = mid(f["relief_back"]["relief_depth"])
    _agree(plan, "roof_aim_mm", height - ceiling)
    _agree(plan, "rebate_height_aim_mm", slot_height)
    _agree(plan, "rebate_depth_aim_mm", slot_depth)
    _agree(plan, "relief_bottom_mm", slot_depth + relief_depth)
    back_wall = f["back_face"]["back_wall"]
    rebate_width = f["rebate_back"]["rebate_width"]
    _agree(plan, "thickness_min_mm", rebate_width[1] + back_wall[0])
    _agree(plan, "thickness_max_mm", rebate_width[0] + back_wall[1])
    # MS02 faces to the window's middle: at +.010/0 on the rebate (owner
    # ruling 2026-11-21) the window's floor is the model's (.48) REF depth,
    # so facing to the model would aim at the reject edge.
    _agree(
        plan, "thickness_aim_mm", (p["thickness_min_mm"] + p["thickness_max_mm"]) / 2
    )
    aim = p["thickness_aim_mm"]
    # The relief cutter's point above the stacks, on the thinnest block.
    _agree(
        plan, "relief_floor_height_mm", p["thickness_min_mm"] - p["relief_bottom_mm"]
    )
    if not p["thickness_min_mm"] - 1e-6 <= depth <= p["thickness_max_mm"] + 1e-6:
        raise ValueError(f"the model's depth {depth:.3f} is outside the thickness band")

    # The bar: its 1-1/4 width along X, its 3/4 thickness along Y, the sawn
    # slice along Z; the final ends equally inside the bar's ends.
    bar_x, bar_y = p["bar_width_mm"], p["bar_thickness_mm"]
    _close(bar_x, p["blank_x_in"] * IN, "process.bar_width_mm")
    _close(bar_y, p["blank_y_in"] * IN, "process.bar_thickness_mm")
    slice_min, slice_max = p["blank_z_min_mm"], p["blank_z_max_mm"]
    _close(slice_max, p["blank_z_in"] * IN, "process.blank_z_max_mm")
    back_skim, edge_skim = p["back_skim_mm"], p["edge_skim_mm"]
    trim = (bar_x - length) / 2
    _agree(plan, "end_trim_mm", trim)
    if slice_min - back_skim < aim + 0.5:
        raise ValueError(
            f"the shortest slice less the skim, {slice_min - back_skim:.3f}, leaves under .5 mm to face to the depth"
        )
    if bar_y - edge_skim < height:
        raise ValueError("the bar's thickness less the edge skim is under the height")
    mating_top = slice_max - back_skim
    _agree(plan, "mating_top_max_mm", mating_top)
    height_top = bar_y - edge_skim
    _agree(plan, "height_top_mm", height_top)
    far_top = bar_x - trim
    _agree(plan, "far_top_mm", far_top)

    # Holding: the 1 in and 1/2 in parallels stacked under each jaw lying;
    # one 1 in parallel upright. Grips: jaw height less them.
    jaw_h, jaw_w = p["vise_jaw_height_mm"], p["vise_jaw_width_mm"]
    lying_grip = jaw_h - p["riser_height_mm"]
    upright_grip = jaw_h - p["parallel_height_mm"]
    _agree(plan, "lying_grip_mm", lying_grip)
    _agree(plan, "upright_grip_mm", upright_grip)
    for key, along in (
        ("vise_bar_inset_mm", bar_x),
        ("vise_height_inset_mm", height),
        ("vise_length_inset_mm", length),
    ):
        _agree(plan, key, -(jaw_w - along) / 2)

    # Cutters.
    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    e8 = _shop_tool(plan, shop, "em-eighth")["diameter_mm"]
    e16 = _shop_tool(plan, shop, "em-sixteenth")["diameter_mm"]
    d43 = _shop_tool(plan, shop, "drill-43")["diameter_mm"]
    em_r, e8_r, e16_r = em / 2, e8 / 2, e16 / 2
    for name in (
        "back face",
        "mating face",
        "locating edge",
        "top face",
        "locating end",
        "far end",
    ):
        _close(_cut(plan, name, "cutter_dia_mm"), em, f"'{name}' cutter_dia_mm")
    for name in ("rebate", "rebate walls"):
        _close(_cut(plan, name, "cutter_dia_mm"), e8, f"'{name}' cutter_dia_mm")
    _close(_cut(plan, "relief", "cutter_dia_mm"), e16, "'relief' cutter_dia_mm")
    relief_height = f["relief_floor"]["relief_height"]
    if not relief_height[0] <= e16 <= relief_height[1]:
        raise ValueError(
            f"the relief cutter Ø{e16} is outside the relief height band {relief_height}"
        )
    if e8 >= slot_height:
        raise ValueError("the rebate cutter is not under the rebate height")
    woc = p["face_stepover_max_mm"]
    if woc > em / 2 + 1e-9:
        raise ValueError("face_stepover_max_mm is over half the face cutter")
    face_rpm, face_feed = _setting(plan, shop, "back face")
    for name in ("mating face", "locating edge", "top face", "locating end", "far end"):
        if _setting(plan, shop, name) != (face_rpm, face_feed):
            raise ValueError(f"'{name}' runs at another setting than 'back face'")
    step = p["face_step_max_mm"]
    mating_levels = _levels(mating_top, aim, step)
    height_levels = _levels(height_top, height, step)
    locating_levels = _levels(bar_x, far_top, step)
    far_levels = _levels(far_top, length, step)
    for name, levels, top, bottom in (
        ("mating face", mating_levels, mating_top, aim),
        ("top face", height_levels, height_top, height),
        ("locating end", locating_levels, bar_x, far_top),
        ("far end", far_levels, far_top, length),
    ):
        doc = (top - bottom) / len(levels)
        if doc > _cut(plan, name, "axial_doc_mm") + 1e-9:
            raise ValueError(f"'{name}' levels of {doc:.3f} exceed its axial_doc_mm")
    for name, skim in (("back face", back_skim), ("locating edge", edge_skim)):
        _close(_cut(plan, name, "axial_doc_mm"), skim, f"'{name}' axial_doc_mm")
    for name in (
        "back face",
        "mating face",
        "locating edge",
        "top face",
        "locating end",
        "far end",
    ):
        if _cut(plan, name, "radial_woc_mm") > woc + 1e-9:
            raise ValueError(
                f"'{name}' radial_woc_mm is over process.face_stepover_max_mm"
            )

    # MS05, the rebate: machine X = height - y (X0 the top face), Y = -(x +
    # trim) (Y0 the bar's locating-end side), Z = -z (Z0 the mating face).
    x_ceiling, x_floor = height - ceiling, height - floor
    x_centre = (x_ceiling + x_floor) / 2
    _agree(plan, "rebate_centre_x_mm", x_centre)
    tab = p["rebate_tab_mm"]
    slot_ys = (-(tab + e8_r), -(bar_x - tab - e8_r))
    # The rebate stops ``tab`` short of the bar's ends, both in the waste
    # the end facing removes: at least 1 mm past each final end.
    if tab > trim - 1.0:
        raise ValueError("the rebate does not run at least 1 mm past each final end")
    rebate_rpm, rebate_feed = _setting(plan, shop, "rebate")
    if _setting(plan, shop, "rebate walls") != (rebate_rpm, rebate_feed):
        raise ValueError("'rebate walls' runs at another setting than 'rebate'")
    relief_rpm, relief_feed = _setting(plan, shop, "relief")
    rebate_levels = _levels(0.0, -slot_depth, p["rebate_step_mm"])
    _close(
        _cut(plan, "rebate", "axial_doc_mm"),
        p["rebate_step_mm"],
        "'rebate' axial_doc_mm",
    )
    wall = (slot_height - e8) / 2
    _agree(plan, "rebate_wall_mm", wall)
    _close(
        _cut(plan, "rebate walls", "radial_woc_mm"),
        p["rebate_wall_mm"],
        "'rebate walls' radial_woc_mm",
    )
    _close(
        _cut(plan, "rebate walls", "axial_doc_mm"),
        p["rebate_depth_aim_mm"],
        "'rebate walls' axial_doc_mm",
    )
    x_ceiling_pass = x_ceiling + e8_r
    x_floor_pass = x_floor - e8_r
    x_relief = x_ceiling + e16_r
    rough, end = _slot(x_centre, slot_ys, rebate_levels, None)
    # Finish both walls full depth, each climbing (ball screws): the floor
    # wall running +Y, the ceiling wall -Y, from whichever end the rough
    # ended at.
    near, far = _r(slot_ys[0]), _r(slot_ys[1])
    if end == far:
        walls = [
            f"G1 X{_r(x_floor_pass):.3f} F{{feed}}",
            f"G1 Y{near:.3f} F{{feed}}",
            f"G1 X{_r(x_ceiling_pass):.3f} F{{feed}}",
            f"G1 Y{far:.3f} F{{feed}}",
        ]
    else:
        walls = [
            f"G1 X{_r(x_ceiling_pass):.3f} F{{feed}}",
            f"G1 Y{far:.3f} F{{feed}}",
            f"G1 X{_r(x_floor_pass):.3f} F{{feed}}",
            f"G1 Y{near:.3f} F{{feed}}",
        ]
    rebate_lines = [f"G0 Z{CLEAR_MM:.3f}", *rough, *walls, f"G0 Z{CLEAR_MM:.3f}"]
    # The relief is plunge-milled (owner ruling 2026-11-21, relayed by
    # CncBlockA): the 1/16 in long-reach end mill plunges straight down past
    # the rebate's back at stations no more than half its diameter apart, its
    # load along its axis. Between two plunges a ridge stands on each side:
    # its height (the scallop) is the cutter radius less the half-chord, and
    # the relief's clear height between the ridges, √(D² − s²) for a cutter D
    # at the step s, must stay in its band. The least cutter the traveler
    # accepts is then hypot(band minimum, s), and the step is held to half
    # of it too (s ≤ band minimum / √3), so any cutter it accepts plunges no
    # more than half itself apart.
    relief_bottom = -(slot_depth + relief_depth)
    relief_span = abs(slot_ys[1] - slot_ys[0])
    step_cap = min(e16 / 2, relief_height[0] / math.sqrt(3))
    intervals = math.ceil(relief_span / step_cap - 1e-9)
    plunge_step = relief_span / intervals
    _agree(plan, "relief_plunge_step_mm", plunge_step)
    scallop = e16_r - math.sqrt(e16_r**2 - (plunge_step / 2) ** 2)
    _agree(plan, "relief_scallop_mm", scallop)
    # The cutter band whose plunges leave the relief's clear height (between
    # the ridges) in its band; the traveler mics the cutter against it.
    cutter_min = math.hypot(relief_height[0], plunge_step)
    _agree(plan, "relief_cutter_min_mm", cutter_min)
    _agree(plan, "relief_cutter_max_mm", relief_height[1])
    if e16 < cutter_min or plunge_step > cutter_min / 2 + 1e-9:
        raise ValueError("the relief's plunge ridges leave it under its height band")
    # Setup 6 gauges each 3-flute cutter by a test plunge in the waste end,
    # read with the pins: the GO pin, at its least, is not under the least
    # good cut and the NO-GO pin, at its most, not over the largest. The
    # 1/8 in cut's band is the rebate band less the two wall passes (the
    # walls run at the nominal cutter's offsets); the 1/16 in cut's is the
    # relief cutter band above. Each plunge feeds as its program plunges.
    rebate_band = f["rebate_floor"]["rebate_height"]
    slot_cut = (
        rebate_band[0] - (slot_height - e8),
        rebate_band[1] - (slot_height - e8),
    )
    _agree(plan, "slot_cut_min_mm", slot_cut[0])
    _agree(plan, "slot_cut_max_mm", slot_cut[1])
    for name, (lo, hi) in (
        ("slot", slot_cut),
        ("relief", (cutter_min, relief_height[1])),
    ):
        go = math.ceil(round((lo + PIN_MINUS_MM) / IN * 1000, 6)) / 1000
        nogo = math.floor(round(hi / IN * 1000, 6)) / 1000
        for key, value in (("go", go), ("nogo", nogo)):
            stated = p[f"{name}_{key}_pin_in"]
            if not math.isclose(stated, value, abs_tol=1e-6):
                raise ValueError(
                    f"process.{name}_{key}_pin_in {stated:g}, the recipe picks {value:.3f}"
                )
        if go >= nogo:
            raise ValueError(f"no pin pair reads the {name} test cut's band")
    _close(
        _cut(plan, "slot test plunge", "cutter_dia_mm"),
        e8,
        "'slot test plunge' cutter_dia_mm",
    )
    _close(
        _cut(plan, "relief test plunge", "cutter_dia_mm"),
        e16,
        "'relief test plunge' cutter_dia_mm",
    )
    if _setting(plan, shop, "slot test plunge") != (rebate_rpm, rebate_feed):
        raise ValueError("'slot test plunge' runs at another setting than 'rebate'")
    if _setting(plan, shop, "relief test plunge") != (relief_rpm, relief_feed):
        raise ValueError("'relief test plunge' runs at another setting than 'relief'")
    _agree(plan, "slot_test_feed_mm_min", rebate_feed / 2)
    _agree(plan, "relief_test_feed_mm_min", relief_feed)
    # The test holes, at the largest cut the pins pass, all in the waste
    # end the end facing removes (at test_y_mm from the fixed jaw's face, the
    # retests as far from the moving jaw's), clear of the rebate and of each
    # other by TEST_WALL_MM, so a pin cannot push a thin web aside.
    _agree(plan, "test_far_y_mm", bar_x - p["test_y_mm"])
    holes = (
        (p["slot_test_x_mm"], slot_cut[1] / 2),
        (p["relief_test_x_mm"], relief_height[1] / 2),
    )
    y, wall = p["test_y_mm"], TEST_WALL_MM - 1e-9
    for x, r in holes:
        if not (
            y - r >= wall
            and trim - (y + r) >= wall
            and x - r - x_floor >= wall
            and height - (x + r) >= wall
        ):
            raise ValueError(
                f"the test hole at X{x:g} is not {TEST_WALL_MM} mm inside the waste end"
            )
    (x1, r1), (x2, r2) = holes
    if abs(x2 - x1) - r1 - r2 < wall:
        raise ValueError(f"the test holes are not {TEST_WALL_MM} mm apart")
    relief_ys = [
        slot_ys[0] + k * (slot_ys[1] - slot_ys[0]) / intervals
        for k in range(intervals + 1)
    ]
    entry = _r(-slot_depth + RELIEF_ENTRY_MM)
    relief_lines = [
        f"G0 Z{CLEAR_MM:.3f}",
        f"G0 X{_r(x_relief):.3f} Y{_r(relief_ys[0]):.3f}",
        f"G0 Z{SAFE_MM:.3f}",
        f"G1 Z{entry:.3f} F{{feed}}",
    ]
    for k, y in enumerate(relief_ys):
        if k:
            relief_lines.append(f"G1 Y{_r(y):.3f} F{{feed}}")
        relief_lines += [f"G1 Z{_r(relief_bottom):.3f} F{{feed}}", f"G0 Z{entry:.3f}"]
    relief_lines.append(f"G0 Z{CLEAR_MM:.3f}")
    relief_centres = [[_r(x_relief), _r(y)] for y in relief_ys]

    # MS06/MS07, the ends, and MS06's roof chamfer: machine X = height - y (the
    # top face at X0), the faces along X, Y across [-depth, 0]; the chamfer
    # mill's axis offset outside the top face, its point below the end so
    # the cone cuts the printed leg on both faces. MS07b chamfers the far
    # corner lying, top face up: its axis offset outside the far end (X0),
    # its point the same depth below the top face.
    chamfer_rpm, chamfer_feed = _setting(plan, shop, "locating chamfer")
    if _setting(plan, shop, "far chamfer") != (chamfer_rpm, chamfer_feed):
        raise ValueError(
            "'far chamfer' runs at another setting than 'locating chamfer'"
        )
    leg = f["roof_chamfer_1"]["size_nominal"]
    if f["roof_chamfer_2"]["size_nominal"] != leg:
        raise ValueError("the two roof chamfers differ")
    offset = p["chamfer_offset_mm"]
    tip_depth = (leg + offset) / math.tan(math.radians(CHAMFER_DEG / 2))
    _agree(plan, "chamfer_tip_depth_mm", tip_depth)
    chamfer_ys = (tip_depth + APPROACH_MM, -depth - tip_depth - APPROACH_MM)

    # MS08, the thumb hole from the locating edge into the rebate: machine
    # X = -x, Y = -z, Z = height - y.
    thumb = f["thumb_tap"]
    if thumb["axis"] != [0.0, 1.0, 0.0] or thumb["at"][1] != 0.0:
        raise ValueError("thumb_tap: expected along +y from the locating edge")
    if not math.isclose(d43, thumb["nominal_dia"], abs_tol=1e-3):
        raise ValueError(f"#43 Ø{d43} is not the thumb hole's drill {thumb['dia']}")
    thumb_xy = (_r(-thumb["at"][0]), _r(-thumb["at"][2]))
    model_floor = plane("rebate_floor")
    thumb_tip = height - (model_floor + p["thumb_drill_past_mm"] + _point(d43))
    _agree(plan, "thumb_tip_height_mm", thumb_tip)
    if height - thumb_tip >= ceiling - 1.0:
        raise ValueError("the thumb drill's point comes within 1 mm of the roof")
    roof_low = height - f["rebate_ceiling"]["roof_thickness"][1]
    if p["thumb_tap_reach_mm"] > roof_low - 0.25:
        raise ValueError("the thumb tap's reach comes within .010 of the lowest roof")
    if p["thumb_tap_reach_mm"] <= model_floor:
        raise ValueError("the thumb tap's reach does not pass the rebate floor")
    spot_rpm, spot_feed = _setting(plan, shop, "thumb spot")
    d43_rpm, d43_feed = _setting(plan, shop, "thumb drill")
    _close(
        _cut(plan, "thumb spot", "cutter_dia_mm"),
        p["spot_dia_mm"],
        "'thumb spot' cutter_dia_mm",
    )
    spot = _spot_depth(p["spot_dia_mm"])
    if p["spot_dia_mm"] >= d43:
        raise ValueError("the spot is not under the #43 drill")
    stated = _op_with_cut(plan, "thumb drill")[0]
    if stated["hole_depth_mm"] != "{{cad.thumb_tap_thru_length_ref}}":
        raise ValueError(
            "'thumb drill' hole_depth_mm is not the thumb hole's through length"
        )
    if stated["peck"] != {"step_mm": p["peck_43_mm"], "retract": "full"}:
        raise ValueError(
            "'thumb drill' peck is not process.peck_43_mm with full retract"
        )

    # MS10/MS11, the plate holes after MHA-MS-03's pair pilot: machine X =
    # -y (X0 the locating edge), Y = -x (Y0 the locating end).
    plate_xy = []
    for name in ("plate_tap_1", "plate_tap_2"):
        hole = f[name]
        if hole["axis"] != [0.0, 0.0, 1.0] or hole["at"][2] != 0.0:
            raise ValueError(f"{name}: expected into the mating face")
        plate_xy.append((_r(-hole["at"][1]), _r(-hole["at"][0])))
        reach = p["plate_tap_reach_mm"]
        if not hole["thread_depth"][1] < reach < hole["drill_depth"][0]:
            raise ValueError(
                f"{name}: the tap reach is not between the thread and the drilled depth"
            )

    # The tap guide's stack (mg_magnifying_clamp's rule): the spindle-to-
    # table maximum (machines.pm-30mv) less 25.0 to bring the point down,
    # the vise bed, the stacks, the tallest tapping setup (the thumb hole's,
    # the height) and the collet gauge, rounded down to .01 in.
    stack = (
        p["spindle_to_table_mm"]
        - 25.0
        - p["vise_bed_height_mm"]
        - p["riser_height_mm"]
        - height
        - p["r8_collet_gauge_mm"]
    )
    _agree(plan, "tap_stack_max_mm", math.floor(stack / IN * 100) / 100 * IN)

    names = {t["id"]: t["name"] for t in plan["tools"]}
    numbers = {
        t["id"]: n
        for n, t in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    frames = {
        "back": ([-trim, bar_y - edge_skim, depth], [[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
        "mating": ([-trim, -edge_skim, depth], [[1, 0, 0], [0, -1, 0], [0, 0, -1]]),
        "edge": ([-trim, 0.0, depth], [[1, 0, 0], [0, 0, 1], [0, -1, 0]]),
        "height": ([-trim, 0.0, 0.0], [[1, 0, 0], [0, 0, -1], [0, 1, 0]]),
        "rebate": ([-trim, height, 0.0], [[0, -1, 0], [-1, 0, 0], [0, 0, -1]]),
        "locating": ([far_top, height, depth], [[0, -1, 0], [0, 0, 1], [-1, 0, 0]]),
        "far": ([0.0, height, 0.0], [[0, -1, 0], [0, 0, -1], [1, 0, 0]]),
        # MS07b: lying as for MS04, the far end to the right.
        "far_chamfer": ([length, 0.0, 0.0], [[1, 0, 0], [0, 0, -1], [0, 1, 0]]),
        "thumb": ([0.0, height, 0.0], [[-1, 0, 0], [0, 0, -1], [0, -1, 0]]),
    }
    for key, (_origin, axes) in frames.items():
        if not math.isclose(_det(axes), 1.0):
            raise ValueError(f"frame {key!r} is not right-handed")
    frames = {k: {"origin": o, "axes": a} for k, (o, a) in frames.items()}

    em_tool = {
        "tool": "em-half",
        "dia": em,
        "shape": "endmill",
        "flutes": 3,
        "rpm": face_rpm,
        "feed": face_feed,
        "plunge": face_feed,
    }
    e8_tool = {
        "tool": "em-eighth",
        "dia": e8,
        "shape": "endmill",
        "flutes": 3,
        "rpm": rebate_rpm,
        "feed": rebate_feed,
        "plunge": rebate_feed / 2,
    }
    e16_tool = {
        "tool": "em-sixteenth",
        "dia": e16,
        "shape": "endmill",
        "flutes": 3,
        "rpm": relief_rpm,
        "feed": relief_feed,
        "plunge": relief_feed,
    }
    # FreeCAD's chamfer bit has no tip angle; the posted lines are the
    # recipe's own, so the 90° chamfer mill is carried as a 90° pointed bit.
    chamfer_tool = {
        "tool": "chamfer",
        "dia": _shop_tool(plan, shop, "chamfer")["diameter_mm"],
        "shape": "drill",
        "tip_angle": CHAMFER_DEG,
        "rpm": chamfer_rpm,
        "feed": chamfer_feed,
        "plunge": chamfer_feed / 2,
    }
    spot_tool = {
        "tool": "spot",
        "dia": CENTRE_DRILL["body_mm"],
        "shape": "drill",
        "tip_angle": CENTRE_DRILL["point_deg"],
        "rpm": spot_rpm,
        "feed": spot_feed,
        "plunge": spot_feed,
    }
    d43_tool = {
        "tool": "drill-43",
        "dia": d43,
        "shape": "drill",
        "tip_angle": DRILL_POINT_DEG,
        "rpm": d43_rpm,
        "feed": d43_feed,
        "plunge": d43_feed,
    }

    lying_x = (-em_r - APPROACH_MM, bar_x + em_r + APPROACH_MM)
    upright_x = (-em_r - APPROACH_MM, height + em_r + APPROACH_MM)
    ys_bar = _stations(-bar_y, 0.0, em_r, woc)
    ys_depth = _stations(-depth, 0.0, em_r, woc)
    stock = {
        "back": ((0.0, bar_x), (-bar_y, 0.0), (-(slice_max - back_skim), back_skim)),
        "mating": ((0.0, bar_x), (-bar_y, 0.0), (0.0, mating_top)),
        "edge": ((0.0, bar_x), (-depth, 0.0), (-height_top, edge_skim)),
        "height": ((0.0, bar_x), (-depth, 0.0), (0.0, height_top)),
        "rebate": ((0.0, height), (-bar_x, 0.0), (-depth, 0.0)),
        "locating": ((0.0, height), (-depth, 0.0), (0.0, bar_x)),
        "far": ((0.0, height), (-depth, 0.0), (0.0, far_top)),
        "far_chamfer": ((-length, 0.0), (-depth, 0.0), (0.0, height)),
        "thumb": ((-length, 0.0), (-depth, 0.0), (0.0, height)),
    }
    locating_tip = far_top - tip_depth
    _agree(plan, "locating_chamfer_tip_mm", locating_tip)
    # MS07b: the point below the top face, lying (Z0 the locating edge).
    far_tip = height - tip_depth
    _agree(plan, "far_chamfer_tip_mm", far_tip)
    jobs = [
        {
            **em_tool,
            "frame": "back",
            "label": "back face",
            "ops": [
                [
                    "back_face",
                    "skim the back face",
                    _face([0.0], back_skim, lying_x, ys_bar),
                ]
            ],
        },
        {
            **em_tool,
            "frame": "mating",
            "label": "mating face",
            "ops": [
                [
                    "mating_face",
                    "face the mating face to the depth",
                    _face(mating_levels, mating_top, lying_x, ys_bar),
                ]
            ],
        },
        {
            **em_tool,
            "frame": "edge",
            "label": "locating edge",
            "ops": [
                [
                    "locating_edge",
                    "skim the locating edge",
                    _face([0.0], edge_skim, lying_x, ys_depth),
                ]
            ],
        },
        {
            **em_tool,
            "frame": "height",
            "label": "top face",
            "ops": [
                [
                    "top_face",
                    "face the top to the height",
                    _face(height_levels, height_top, lying_x, ys_depth),
                ]
            ],
        },
        {
            **e8_tool,
            "frame": "rebate",
            "label": "rebate",
            "ops": [["rebate", "mill the rebate", rebate_lines]],
        },
        {
            **e16_tool,
            "frame": "rebate",
            "label": "relief",
            "ops": [["relief", "mill the corner relief", relief_lines]],
        },
        {
            **em_tool,
            "frame": "locating",
            "label": "locating end",
            "ops": [
                [
                    "locating_end",
                    "face the locating end",
                    _face(locating_levels, bar_x, upright_x, ys_depth),
                ]
            ],
        },
        {
            **chamfer_tool,
            "frame": "locating",
            "label": "locating chamfer",
            "ops": [
                [
                    "locating_chamfer",
                    "chamfer the locating end's roof corner",
                    _chamfer(-offset, chamfer_ys, far_top, locating_tip, bar_x),
                ]
            ],
        },
        {
            **em_tool,
            "frame": "far",
            "label": "far end",
            "ops": [
                [
                    "far_end",
                    "face the far end to the length",
                    _face(far_levels, far_top, upright_x, ys_depth),
                ]
            ],
        },
        {
            **chamfer_tool,
            "frame": "far_chamfer",
            "label": "far chamfer",
            "ops": [
                [
                    "far_chamfer",
                    "chamfer the far end's roof corner",
                    _chamfer(offset, chamfer_ys, height, far_tip, height),
                ]
            ],
        },
        {
            **spot_tool,
            "frame": "thumb",
            "label": "thumb spot",
            "ops": [
                [
                    "thumb_spot",
                    "spot the thumb hole",
                    _spot(thumb_xy, height, height - spot, height + CLEAR_MM),
                ]
            ],
        },
        {
            **d43_tool,
            "frame": "thumb",
            "label": "thumb drill",
            "ops": [
                [
                    "thumb_drill",
                    "drill the thumb hole into the rebate",
                    _pecked(
                        thumb_xy, height, thumb_tip, p["peck_43_mm"], height + CLEAR_MM
                    ),
                ]
            ],
        },
    ]
    for job in jobs:
        job["stock"] = stock[job["frame"]]

    # One file per hole to tap: the tap guide loaded by the file's own M6
    # (its %msg names the hole), Z to the machine's top in machine
    # coordinates before any XY, over the hole, M30: the controller ends
    # Idle, so the operator can jog the guide's point down into the wrench.
    manual = {}
    for key, at, what in (
        ("tap_thumb", thumb_xy, "4-40 PLUG TAP IN THE THUMB HOLE"),
        (
            "tap_plate_1",
            plate_xy[0],
            "2-56 PLUG THEN BOTTOMING TAP IN PLATE HOLE 1, NEAR THE LOCATING END",
        ),
        ("tap_plate_2", plate_xy[1], "2-56 PLUG THEN BOTTOMING TAP IN PLATE HOLE 2"),
    ):
        manual[key] = {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": f"SPINDLE STAYS OFF. NEXT: {what}",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{at[0]:.3f} Y{at[1]:.3f}",
                f"({what}. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND TO THE NOTED DRO Z, READ WITH THE POINT PUSHED HOME. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": list(at),
        }

    # Keep-outs (machine frame of each program): the jaws, from the gripped
    # faces outward, up to their tops; the part's own finished faces where a
    # cutter works beside them.
    def jaws(
        width: float, along: tuple[float, float], z_top: float
    ) -> list[dict[str, Any]]:
        centre = (along[0] + along[1]) / 2
        x = (centre - jaw_w / 2, centre + jaw_w / 2)
        return [
            _box("fixed jaw", x, (0.0, JAW_DEPTH_MM), z_top),
            _box("moving jaw", x, (-width - JAW_DEPTH_MM, -width), z_top),
        ]

    jaws_back = jaws(bar_y, (0.0, bar_x), lying_grip - (slice_min - back_skim))
    jaws_mating = jaws(bar_y, (0.0, bar_x), lying_grip)
    jaws_edge = jaws(depth, (0.0, bar_x), lying_grip - height_top)
    jaws_height = jaws(depth, (0.0, bar_x), lying_grip)
    jaws_upright = jaws(depth, (0.0, height), upright_grip)
    jaws_thumb = jaws(depth, (-length, 0.0), lying_grip)
    jaws_far_chamfer = jaws(depth, (-length, 0.0), lying_grip)
    # MS05: gripped across the bar's width, the jaws along machine X; the
    # thinnest accepted block sets their tops highest below Z0.
    rebate_jaw_top = lying_grip - p["thickness_min_mm"]
    rebate_x = (height / 2 - jaw_w / 2, height / 2 + jaw_w / 2)
    rebate_jaws = [
        _box("fixed jaw", rebate_x, (0.0, JAW_DEPTH_MM), rebate_jaw_top),
        _box("moving jaw", rebate_x, (-bar_x - JAW_DEPTH_MM, -bar_x), rebate_jaw_top),
    ]
    roof = _box("roof", (-JAW_DEPTH_MM, x_ceiling), (-bar_x, 0.0), 0.0)
    floor_box = _box(
        "rebate floor", (x_floor, height + JAW_DEPTH_MM), (-bar_x, 0.0), 0.0
    )
    tabs = [
        _box(
            "locating-side tab",
            (-JAW_DEPTH_MM, height + JAW_DEPTH_MM),
            (-tab, 0.0),
            0.0,
        ),
        _box(
            "far-side tab",
            (-JAW_DEPTH_MM, height + JAW_DEPTH_MM),
            (-bar_x, -bar_x + tab),
            0.0,
        ),
    ]
    rebate_back = _box(
        "rebate back",
        (-JAW_DEPTH_MM, height + JAW_DEPTH_MM),
        (-bar_x, 0.0),
        -slot_depth,
    )
    relief_side = _box(
        "below the rebate back",
        (x_ceiling + e16, height + JAW_DEPTH_MM),
        (-bar_x, 0.0),
        -slot_depth,
    )
    relief_back = _box(
        "relief back",
        (-JAW_DEPTH_MM, height + JAW_DEPTH_MM),
        (-bar_x, 0.0),
        -(slot_depth + relief_depth),
    )
    # The rebate cleared at its back, across its height, at both final ends
    # and midway.
    stations = [-trim, -(trim + length / 2), -(trim + length)]
    rebate_points = [
        (x, y) for y in stations for x in (x_ceiling + 1e-3, x_centre, x_floor - 1e-3)
    ]

    t = numbers
    expect: list[list[Any]] = []

    def face_checks(levels, top, span, y, boxes):
        return [
            ["depth", {"z_min": _r(levels[-1])}],
            ["rapids_clear", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            *[
                [
                    "face_passes",
                    {
                        "z": _r(z),
                        "y": [y, 0.0],
                        "max_engagement": woc,
                        "radius": em_r,
                        "span": span,
                        "overhang": FACE_OVERHANG_MM,
                    },
                ]
                for z in levels
            ],
            ["keep_out", {"radius": em_r, "boxes": boxes}],
        ]

    def hole_checks(centres, top, bottom, radius, boxes):
        return [
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": top, "open_holes": centres}],
            ["vertical_below_top", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": radius, "boxes": boxes}],
        ]

    def chamfer_checks(top, boxes):
        return [
            ["rapids_clear", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": chamfer_tool["dia"] / 2, "boxes": boxes}],
        ]

    programs = {
        "MS01_back": (
            back_skim,
            [t["em-half"]],
            0.0,
            [face_checks([0.0], back_skim, bar_x, -bar_y, jaws_back)],
        ),
        "MS02_mating": (
            mating_top,
            [t["em-half"]],
            aim,
            [face_checks(mating_levels, mating_top, bar_x, -bar_y, jaws_mating)],
        ),
        "MS03_edge": (
            edge_skim,
            [t["em-half"]],
            0.0,
            [face_checks([0.0], edge_skim, bar_x, -depth, jaws_edge)],
        ),
        "MS04_height": (
            height_top,
            [t["em-half"]],
            height,
            [face_checks(height_levels, height_top, bar_x, -depth, jaws_height)],
        ),
        "MS05_rebate": (
            0.0,
            [t["em-eighth"]],
            -slot_depth,
            [
                [
                    ["rapids_clear", {"z_top": 0.0}],
                    ["air_feed", {"z_top": 0.0}],
                    [
                        "cleared",
                        {"points": rebate_points, "radius": e8_r, "z": _r(-slot_depth)},
                    ],
                    [
                        "keep_out",
                        {
                            "radius": e8_r,
                            "boxes": [
                                *rebate_jaws,
                                roof,
                                floor_box,
                                *tabs,
                                rebate_back,
                            ],
                        },
                    ],
                ],
            ],
        ),
        "MS05_relief": (
            0.0,
            [t["em-sixteenth"]],
            relief_bottom,
            [
                [
                    # Every plunge station, no more than half the cutter apart
                    # (the scallop bound above), each to the relief's back.
                    [
                        "holes",
                        {"centres": relief_centres, "z_bottom": _r(relief_bottom)},
                    ],
                    ["rapids_clear", {"z_top": 0.0, "open_holes": relief_centres}],
                    ["air_feed", {"z_top": 0.0}],
                    [
                        "keep_out",
                        {
                            "radius": e16_r,
                            "boxes": [
                                *rebate_jaws,
                                roof,
                                floor_box,
                                *tabs,
                                relief_side,
                                relief_back,
                            ],
                        },
                    ],
                ],
            ],
        ),
        "MS06_locating_end": (
            bar_x,
            [t["em-half"], t["chamfer"]],
            locating_tip,
            [
                face_checks(locating_levels, bar_x, height, -depth, jaws_upright),
                chamfer_checks(far_top, jaws_upright),
            ],
        ),
        "MS07_far_end": (
            far_top,
            [t["em-half"]],
            length,
            [face_checks(far_levels, far_top, height, -depth, jaws_upright)],
        ),
        "MS07b_far_chamfer": (
            height,
            [t["chamfer"]],
            far_tip,
            [chamfer_checks(height, jaws_far_chamfer)],
        ),
        "MS08_thumb": (
            height,
            [t["spot"], t["drill-43"]],
            thumb_tip,
            [
                hole_checks(
                    [list(thumb_xy)],
                    height,
                    height - spot,
                    CENTRE_DRILL["body_mm"] / 2,
                    jaws_thumb,
                ),
                hole_checks([list(thumb_xy)], height, thumb_tip, d43 / 2, jaws_thumb),
            ],
        ),
    }
    for name, (top, tools, deepest, sections) in programs.items():
        expect += [
            [name, "tool_changes", {"z_top": top, "tools": tools, "loads_first": True}],
            [name, "spindle", {"rpm": [[2800.0]] * len(tools)}],
            [name, "pauses", {"z_top": top, "count": 0}],
            [name, "depth", {"z_min": _r(deepest)}],
        ]
        if len(sections) == 1:
            expect += [
                [name, check, kwargs]
                for check, kwargs in sections[0]
                if check != "depth"
            ]
        else:
            for k, checks in enumerate(sections):
                expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]
    for name, key, top in (
        ("MS09_thumb_tap", "tap_thumb", height),
        ("MS10_plate_tap_1", "tap_plate_1", 0.0),
        ("MS11_plate_tap_2", "tap_plate_2", 0.0),
    ):
        expect += [
            [
                name,
                "tap_stop",
                {
                    "tool": t["tap-guide"],
                    "at": manual[key]["at"],
                    "machine_top": MACHINE_Z_TOP_MM,
                },
            ],
            [name, "air_feed", {"z_top": top}],
        ]
    speeds = {face_rpm, rebate_rpm, relief_rpm, chamfer_rpm, spot_rpm, d43_rpm}
    if speeds != {2800.0}:
        raise ValueError(
            f"every setting runs at 2800 rpm in the programs' checks, not {sorted(speeds)}"
        )

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
            doc, f"Block {key}", ctx["step"], frame["origin"], frame["axes"]
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
