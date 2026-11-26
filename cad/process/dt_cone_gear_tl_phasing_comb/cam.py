"""FreeCAD CAM recipe for MHA-DT-03-TL-02, the cone tip gears' phasing comb.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. No part dimension is
typed here: the U's ends, edges, slot, blade steps and sheet come from the
manifest; the blank, its place on the spoil plate, the tape stack, the cutter's tip
height, the vise and the plate from ``plan.toml`` ``[parameters]``; the
cutter's diameter, flute length, speed and feed from the shop (``shop/``).
Typed here, because neither record carries them: the safe and clearance
heights, the vise jaws' depth (keep-out shapes only) and the share of a
printed band the posted path may use.

Route (plan text in ``plan.toml``): the blank, snipped from the .020 sheet,
is bonded to the spoil plate (``fixtures.sheet-spoil-plate``), gripped in
the vise on parallels, on blue painter's tape on both faces with CA glue
between (owner 2026-11-23). One file, CB01_outline: the 1/32
in carbide downcut end mill comes down in front of the blank, feeds in
through the blank's margin and runs round the whole U at the finished size
once per level, in the fewest equal levels each within the maker's slotting
depth, backing out through the margin and stepping down there between
levels; the last level's tip stands a few thousandths into the spoil plate
(past the tape stack, whatever the stack's and the plate top's variation),
so the comb comes free of the blank on its own island of tape.

Work frame (G54): X0 the plate's left end, Y0 the fixed jaw's face (the
plate's back edge), +Y toward the fixed jaw; Z0 the plate top. The comb lies
with its length along X, its south (open) end at the left and its near arm
(the blade staircase) toward the fixed jaw. The cutter centre runs a cutter
radius outside the outline, anticlockwise round the part: conventional with a
clockwise spindle. Inside corners (each riser's top, the level's return) are
the cutter's radius, under the title block's INSIDE CORNERS max.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_cone_gear_tl_phasing_comb"
COMMENT = "MHA-DT-03-TL-02 phasing comb"
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (("CB01_outline", ("outline",)),)
# The file loads its own end mill (M6, the tool setter): the setup starts on
# whatever the mill last held.
LOAD_FIRST_TOOL = ("CB01_outline",)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these.
CAM_TOOLS = ("em-thirtysecond",)
# Blade features south to north (the staircase's order along X).
BLADES = ("blade_t024", "blade_t018", "blade_t012", "blade_t006")
IN = 25.4
# The cutter comes down this far in front of the blank's front edge (beyond
# its radius), its tip into the plate's tape and the spoil plate only, then
# feeds in through the blank's margin to the path: it never plunges into the
# brass sheet, whose burr and tape would lift at a plunge.
APPROACH_MM = 1.0
# The descent starts this far above the stock top: real G0 brings the cutter
# to it.
SAFE_MM = 1.0
# Moves to and from the cut run this far above the stock top.
CLEAR_MM = 5.0
# Keep-outs: each vise jaw's depth away from the plate it grips.
JAW_DEPTH_MM = IN
# The posted path's cutter centre may stray from its offset by this share of
# the tightest printed band locating that edge; the rest is the machine's.
BAND_FRACTION = 0.1
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
) -> tuple[float, float, int]:
    """(rpm, mm/min, flutes) of the shop setting the operation holding ``cut``
    names: its chip load × flutes × rpm."""
    op, _record_cut = _op_with_cut(plan, cut)
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    flutes = int(record["flutes"])
    return rpm, record["chip_load_mm_per_tooth"] * flutes * rpm, flutes


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


def _plane(features: dict[str, Any], name: str, axis: str) -> float:
    plane = features[name]["plane"]
    if plane["frame"] != "model" or plane["axis"] != axis:
        raise ValueError(f"{name}: expected a model {axis.upper()} plane")
    return float(plane["value"])


def _band(feature: dict[str, Any], key: str) -> float:
    low, high = feature[key]
    return high - low


def _outline(f: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """The U's edges in model X/Y, anticlockwise round the part (the part on
    the left of each), each with its name, direction and the share of its
    locating band the cutter may stray (``tol``)."""
    south = _plane(f, "south_end", "x")
    north = _plane(f, "north_end", "x")
    seat = _plane(f, "seat", "y")
    back = _plane(f, "back", "y")
    inner = _plane(f, "spring_inner", "y")
    far = _plane(f, "far_edge", "y")
    slot = f["slot_end"]
    centre = slot["at"]
    radius = slot["end_radius_ref"]
    if not math.isclose(centre[0], slot["slot_length_nominal"], abs_tol=1e-6):
        raise ValueError("slot_end: its full R is not centred at the slot length")
    if not (
        math.isclose(centre[1] + radius, seat, abs_tol=1e-6)
        and math.isclose(centre[1] - radius, inner, abs_tol=1e-6)
    ):
        raise ValueError("slot_end: its full R is not tangent to both arms")
    blades = []
    for name in BLADES:
        blade = f[name]
        if blade["start_from"] != "south_end" or blade["depth_from"] != "seat":
            raise ValueError(f"{name}: expected start from south_end, depth from seat")
        blades.append(
            (
                name,
                south + blade["start_nominal"],
                seat - blade["depth_nominal"],
                BAND_FRACTION * min(_band(blade, "start"), _band(blade, "depth")),
            )
        )
    t006 = f[BLADES[-1]]
    level_end = south + t006["level_end_nominal"]
    tol_end = BAND_FRACTION * _band(t006, "level_end")
    tol_len = BAND_FRACTION * _band(f["north_end"], "length")
    tol_back = BAND_FRACTION * _band(f["back"], "height")
    tol_grip = BAND_FRACTION * _band(f["spring_inner"], "grip_span")
    tol_spring = BAND_FRACTION * _band(f["far_edge"], "spring_width")
    tol_slot = BAND_FRACTION * _band(slot, "slot_length")
    xs = [b[1] for b in blades]
    if not (south < xs[0] and all(a < b for a, b in zip(xs, xs[1:]))):
        raise ValueError("the blade risers do not step north in order")
    if not (level_end > xs[-1] and level_end < centre[0]):
        raise ValueError(
            "the last level's return is not between its riser and the slot"
        )
    ys = [b[2] for b in blades]
    if not (seat > ys[0] and all(a > b for a, b in zip(ys, ys[1:])) and ys[-1] > inner):
        raise ValueError(
            "the blade levels do not step deeper in order above the spring"
        )

    def line(name, s, e, tol):
        return {"name": name, "start": [s[0], s[1]], "end": [e[0], e[1]], "tol": tol}

    el = [
        line("far edge", (south, far), (north, far), tol_spring),
        line("north end", (north, far), (north, back), tol_len),
        line("back edge", (north, back), (south, back), tol_back),
        line("near arm south end", (south, back), (south, seat), tol_len),
        line("T030 seat", (south, seat), (xs[0], seat), blades[0][3]),
    ]
    level = seat
    for k, (name, x, y, tol) in enumerate(blades):
        nxt = xs[k + 1] if k + 1 < len(blades) else level_end
        el.append(line(f"{name} riser", (x, level), (x, y), tol))
        el.append(line(f"{name} level", (x, y), (nxt, y), tol))
        level = y
    el.append(line("T006 return", (level_end, level), (level_end, seat), tol_end))
    el.append(line("near arm edge", (level_end, seat), (centre[0], seat), tol_grip))
    mid = (centre[0] + radius, centre[1])
    el.append(
        {
            "name": "slot end, north half",
            "start": [centre[0], seat],
            "end": [mid[0], mid[1]],
            "centre": [centre[0], centre[1]],
            "tol": tol_slot,
        }
    )
    el.append(
        {
            "name": "slot end, south half",
            "start": [mid[0], mid[1]],
            "end": [centre[0], inner],
            "centre": [centre[0], centre[1]],
            "tol": tol_slot,
        }
    )
    el.append(line("spring inner edge", (centre[0], inner), (south, inner), tol_grip))
    el.append(line("spring south end", (south, inner), (south, far), tol_len))
    dims = {
        "south": south,
        "north": north,
        "back": back,
        "far": far,
        "seat": seat,
        "inner": inner,
        "slot_radius": radius,
        "deepest": ys[-1],
        "level_end": level_end,
    }
    return el, dims


def _cross(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _unit(s: list[float], e: list[float]) -> tuple[float, float]:
    d = math.dist(s, e)
    return ((e[0] - s[0]) / d, (e[1] - s[1]) / d)


def _offset_path(
    elements: list[dict[str, Any]], r: float, inside_max: float
) -> tuple[list[tuple], list[dict[str, Any]]]:
    """The cutter-centre path ``r`` outside the outline (right of each
    element): offset lines, offset arcs, a G3 arc round each convex corner and
    the offset lines' meeting point at each concave one. Returns the
    segments, each ("line", start, end) or ("arc", start, end, centre, cw),
    and the outline as cut: the elements with each concave corner rounded by
    the cutter's radius about that meeting point (the fillet the title
    block's inside-corner max allows)."""

    def ends(e):
        if "centre" not in e:
            u = _unit(e["start"], e["end"])
            n = (u[1], -u[0])
            return (
                [e["start"][0] + r * n[0], e["start"][1] + r * n[1]],
                [e["end"][0] + r * n[0], e["end"][1] + r * n[1]],
                u,
                u,
            )
        c = e["centre"]
        radius = math.dist(c, e["start"])
        cw = (
            _cross(
                (e["start"][0] - c[0], e["start"][1] - c[1]),
                (e["end"][0] - c[0], e["end"][1] - c[1]),
            )
            < 0
        )
        if not cw:
            raise ValueError(f"{e['name']}: only concave (clockwise) arcs are offset")
        if radius <= r:
            raise ValueError(f"{e['name']}: R{radius:.3f} under the cutter's R{r:.3f}")
        k = (radius - r) / radius

        def pt(p):
            return [c[0] + (p[0] - c[0]) * k, c[1] + (p[1] - c[1]) * k]

        def tangent(p):
            return ((p[1] - c[1]) / radius, -(p[0] - c[0]) / radius)

        return pt(e["start"]), pt(e["end"]), tangent(e["start"]), tangent(e["end"])

    offs = [ends(e) for e in elements]
    segs: list[tuple] = []
    starts = [o[0] for o in offs]
    finishes = [o[1] for o in offs]
    corners: dict[int, tuple] = {}
    count = len(elements)
    for k in range(count):
        e, nxt = elements[k], elements[(k + 1) % count]
        u_in, u_out = offs[k][3], offs[(k + 1) % count][2]
        turn = _cross(u_in, u_out)
        if abs(turn) < 1e-9:
            continue
        if turn > 0:
            continue
        # Concave: both offset lines meet a cutter radius off each edge.
        if "centre" in e or "centre" in nxt:
            raise ValueError(f"{e['name']}: a concave corner on an arc")
        if r > inside_max + 1e-9:
            raise ValueError(
                f"inside corner at {e['name']}: the cutter's R{r:.4f} is over the"
                f" title block's R{inside_max:.4f} max"
            )
        a, b = starts[k], finishes[k]
        c, d = starts[(k + 1) % count], finishes[(k + 1) % count]
        den = _cross((b[0] - a[0], b[1] - a[1]), (d[0] - c[0], d[1] - c[1]))
        t = _cross((c[0] - a[0], c[1] - a[1]), (d[0] - c[0], d[1] - c[1])) / den
        meet = [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]
        finishes[k] = meet
        starts[(k + 1) % count] = list(meet)
        # The fillet's ends: the meeting point back off each edge by r.
        corners[k] = (
            [meet[0] - r * u_in[1], meet[1] + r * u_in[0]],
            [meet[0] - r * u_out[1], meet[1] + r * u_out[0]],
            meet,
        )
    for k in range(count):
        e = elements[k]
        if "centre" in e:
            segs.append(("arc", starts[k], finishes[k], e["centre"], True))
        else:
            segs.append(("line", starts[k], finishes[k]))
        u_in, u_out = offs[k][3], offs[(k + 1) % count][2]
        if _cross(u_in, u_out) > 1e-9:
            segs.append(("arc", finishes[k], starts[(k + 1) % count], e["end"], False))
    cut = [dict(e) for e in elements]
    as_cut: list[dict[str, Any]] = []
    for k in range(count):
        if k in corners:
            cut[k]["end"] = corners[k][0]
            cut[(k + 1) % count]["start"] = corners[k][1]
    for k in range(count):
        as_cut.append(cut[k])
        if k in corners:
            e = elements[k]
            fillet = {"name": f"{e['name']} corner", "tol": e["tol"]}
            fillet |= {"start": corners[k][0], "end": corners[k][1]}
            as_cut.append(fillet | {"centre": corners[k][2]})
    return segs, as_cut


def _gcode(
    segs: list[tuple],
    shift: tuple[float, float],
    levels: list[float],
    top: float,
    clear: float,
    entry_y: float,
) -> list[str]:
    """The path as G-code in the work frame: down to the first level at
    ``entry_y`` in front of the blank, level with the first segment's middle
    (the spring arm's front edge); at each level in through the margin to
    it, the segments round and back to it, and back out the way it came to
    ``entry_y``, where the next level steps down; lift."""

    def w(p):
        return (_r(p[0] + shift[0]), _r(p[1] + shift[1]))

    first = segs[0]
    mid = [(first[1][0] + first[2][0]) / 2, (first[1][1] + first[2][1]) / 2]
    sx, sy = w(mid)
    ex, ey = w(first[2])
    lines = [
        f"G0 Z{_r(top + clear):.3f}",
        f"G0 X{sx:.3f} Y{_r(entry_y):.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
    ]
    for z in levels:
        lines.append(f"G1 Z{_r(z):.3f} F{{feed}}")
        lines.append(f"G1 Y{sy:.3f} F{{feed}}")
        lines.append(f"G1 X{ex:.3f} Y{ey:.3f} F{{feed}}")
        for seg in segs[1:]:
            x, y = w(seg[2])
            if seg[0] == "line":
                if math.dist(seg[1], seg[2]) < 1e-6:
                    continue
                lines.append(f"G1 X{x:.3f} Y{y:.3f} F{{feed}}")
            else:
                c = seg[3]
                i, j = _r(c[0] - seg[1][0]), _r(c[1] - seg[1][1])
                word = "G2" if seg[4] else "G3"
                lines.append(f"{word} X{x:.3f} Y{y:.3f} I{i:.3f} J{j:.3f} F{{feed}}")
        lines.append(f"G1 X{sx:.3f} Y{sy:.3f} F{{feed}}")
        lines.append(f"G1 Y{_r(entry_y):.3f} F{{feed}}")
    lines.append(f"G0 Z{_r(top + clear):.3f}")
    return lines


def _area(elements: list[dict[str, Any]]) -> float:
    """The U's area (shoelace over its edges, each arc a polygon of chords)."""
    pts = []
    for e in elements:
        if "centre" not in e:
            pts.append(e["start"])
            continue
        c = e["centre"]
        radius = math.dist(c, e["start"])
        a0 = math.atan2(e["start"][1] - c[1], e["start"][0] - c[0])
        a1 = math.atan2(e["end"][1] - c[1], e["end"][0] - c[0])
        sweep = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for k in range(64):
            a = a0 + sweep * k / 64
            pts.append([c[0] + radius * math.cos(a), c[1] + radius * math.sin(a)])
    return 0.5 * sum(_cross(p, q) for p, q in zip(pts, pts[1:] + pts[:1]))


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    f = features["features"]
    p = plan["parameters"]
    elements, d = _outline(f)
    top_face = f["top"]
    sheet_max = top_face["stock_thickness"][1]
    if not math.isclose(_plane(f, "underside", "z"), 0.0, abs_tol=1e-9):
        raise ValueError("underside: expected the model's Z0")

    em = _shop_tool(plan, shop, "em-thirtysecond")
    dia = em["diameter_mm"]
    r = dia / 2
    rpm, feed, flutes = _setting(plan, shop, "outline")
    if not math.isclose(_cut(plan, "outline", "cutter_dia_mm"), dia, abs_tol=1e-6):
        raise ValueError("'outline' cutter_dia_mm is not the end mill's diameter")

    # Inside corners: the cutter's radius under the title block's max.
    segs, as_cut = _offset_path(elements, r, p["inside_corner_max_mm"])
    concave = len(as_cut) - len(elements)
    if concave != len(BLADES) + 1:
        raise ValueError(
            f"{concave} inside corners; the staircase has {len(BLADES) + 1}"
        )
    # The narrowest gap the cutter runs in: under the deepest level, above
    # the spring arm.
    gap = d["deepest"] - d["inner"]
    if gap < dia + 2 * max(e["tol"] for e in elements):
        raise ValueError(
            f"the slot under the deepest blade ({gap:.3f}) passes no cutter"
        )

    # Through the sheet: the tip into the spoil plate. Z0 is the bare plate
    # top, so the tip's depth into the plate is the same on every tape stack
    # (the comb's .004, at most spoil_cut_max_mm); its margin under the
    # sheet's underside (on the stack's top) is least on the thinnest stack.
    stack = p["tape_stack_mm"]
    stack_lo, stack_hi = p["tape_stack_min_mm"], p["tape_stack_max_mm"]
    if stack_lo > stack:
        raise ValueError("tape_stack_min_mm is over the tape stack")
    if stack_hi < stack:
        raise ValueError("tape_stack_max_mm is under the tape stack")
    tip = p["outline_tip_z_mm"]
    _agree(plan, "outline_tip_into_plate_mm", -tip)
    if not -p["spoil_cut_max_mm"] <= tip <= 0.0:
        raise ValueError(
            "the cutter's tip must stand at or below the plate top, no deeper"
            " than spoil_cut_max_mm"
        )
    if stack_lo - tip < p["through_margin_min_mm"]:
        raise ValueError(
            "the tip is not through_margin_min_mm below the thinnest sheet's"
            " underside on the thinnest tape stack"
        )
    top = stack + sheet_max
    # The thickest sheet on the thickest stack: the first level's real depth
    # and the floor every rapid and tool change stays above.
    top_hi = stack_hi + sheet_max
    depth = top - tip
    _agree(plan, "outline_depth_mm", depth)
    if top_hi - tip > em["flute_length_mm"]:
        raise ValueError(
            f"the cut ({top_hi - tip:.3f}) is deeper than the end mill's flutes"
            f" ({em['flute_length_mm']:.3f})"
        )
    # Equal levels, the fewest with each no deeper than the stated share of
    # the cutter's diameter (the maker's slotting depth), from the top to
    # the tip.
    count = math.ceil(depth / (p["level_depth_max_fraction"] * dia) - 1e-9)
    if count != p["level_count"]:
        raise ValueError(
            f"process.level_count {p['level_count']}, the recipe computes {count}"
        )
    step = depth / count
    _agree(plan, "level_depth_mm", step)
    if _cut(plan, "outline", "axial_doc_mm") + 1e-6 < step:
        raise ValueError("'outline' axial_doc_mm is under one level's depth")
    levels = [_r(top - step * (k + 1)) for k in range(count)]
    levels[-1] = _r(tip)
    # On the thickest stack the sheet stands higher and the first level
    # takes more: still no deeper than the maker's share of the diameter.
    if top_hi - levels[0] > p["level_depth_max_fraction"] * dia + 1e-6:
        raise ValueError(
            "the first level on the thickest tape stack is deeper than"
            " level_depth_max_fraction of the cutter's diameter"
        )

    # The blank and the comb's place on it, the blank's place on the plate.
    margin = p["blank_margin_mm"]
    length = d["north"] - d["south"]
    height = d["back"] - d["far"]
    _agree(plan, "blank_length_mm", length + 2 * margin)
    _agree(plan, "blank_width_mm", height + 2 * margin)
    if p["blank_length_in"] * IN + PLAN_TOL_MM < length + 2 * margin:
        raise ValueError("process.blank_length_in is short of the comb and margins")
    if p["blank_width_in"] * IN + PLAN_TOL_MM < height + 2 * margin:
        raise ValueError("process.blank_width_in is short of the comb and margins")
    if margin < dia + p["blank_edge_error_mm"]:
        raise ValueError(
            "blank_margin_mm: the cutter's path may run off a snipped edge"
        )
    bx, by = p["blank_left_x_mm"], p["blank_back_y_mm"]
    shift = (bx + margin - d["south"], -by - margin - d["back"])
    _agree(plan, "comb_south_x_mm", shift[0] + d["south"])
    _agree(plan, "comb_back_y_mm", shift[1] + d["back"])
    plate_l, plate_w = p["plate_length_mm"], p["plate_width_mm"]
    if (
        bx + p["blank_length_in"] * IN > plate_l
        or by + p["blank_width_in"] * IN > plate_w
    ):
        raise ValueError("the blank runs off the plate")

    # Bond: the comb and the waste round it, each on its own island of tape
    # once cut.
    comb_area = _area(elements)
    waste_area = p["blank_length_in"] * IN * p["blank_width_in"] * IN - comb_area
    _agree(plan, "comb_bond_area_mm2", comb_area)
    _agree(plan, "waste_bond_area_mm2", waste_area)

    # The vise: the plate across the jaws, its back edge on the fixed jaw
    # (Y0), its top (Z0) below the jaw tops by the jaw height less the
    # parallels and the plate.
    jaw_top = (
        p["vise_jaw_height_mm"] - p["parallel_height_mm"] - p["plate_thickness_mm"]
    )
    _agree(plan, "jaw_top_over_plate_mm", jaw_top)
    if p["em_thirtysecond_projection_min_mm"] < jaw_top - tip + CLEAR_MM:
        raise ValueError(
            "em_thirtysecond_projection_min_mm: the collet would not clear the"
            " jaw tops with the tip at the cut"
        )
    clear = max(CLEAR_MM, jaw_top - top + CLEAR_MM)
    boxes = [
        _box("fixed jaw", (0.0, plate_l), (0.0, JAW_DEPTH_MM), jaw_top),
        _box(
            "moving jaw", (0.0, plate_l), (-plate_w - JAW_DEPTH_MM, -plate_w), jaw_top
        ),
        _box("spoil plate", (0.0, plate_l), (-plate_w, 0.0), -p["spoil_cut_max_mm"]),
    ]

    numbers = {
        t["id"]: n
        for n, t in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")
    names = {t["id"]: t["name"] for t in plan["tools"]}

    z_cut = levels[-1]
    front = -by - p["blank_width_in"] * IN
    entry_y = front - r - APPROACH_MM
    if entry_y - r < -plate_w:
        raise ValueError("the cutter's way in runs off the plate's front edge")
    lines = _gcode(segs, shift, levels, top, clear, entry_y)
    entry_x = _r((segs[0][1][0] + segs[0][2][0]) / 2 + shift[0])
    start_y = _r((segs[0][1][1] + segs[0][2][1]) / 2 + shift[1])
    work_elements = [
        {
            **e,
            "start": [e["start"][0] + shift[0], e["start"][1] + shift[1]],
            "end": [e["end"][0] + shift[0], e["end"][1] + shift[1]],
            **(
                {"centre": [e["centre"][0] + shift[0], e["centre"][1] + shift[1]]}
                if "centre" in e
                else {}
            ),
        }
        for e in as_cut
    ]
    jobs = [
        {
            "tool": "em-thirtysecond",
            "dia": dia,
            "shape": "endmill",
            "flutes": flutes,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
            "frame": "plate",
            "label": "outline",
            "stock": (
                (bx, bx + p["blank_length_in"] * IN),
                (-by - p["blank_width_in"] * IN, -by),
                (stack, top),
            ),
            "ops": [["outline", "cut the U out", lines]],
        }
    ]
    frames = {
        "plate": {
            "origin": [-shift[0], -shift[1], -stack],
            "axes": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        }
    }
    t = numbers["em-thirtysecond"]
    name = PROGRAMS[0][0]
    expect = [
        [name, "tool_changes", {"z_top": top_hi, "tools": [t], "loads_first": True}],
        [name, "spindle", {"rpm": [[rpm]]}],
        [name, "pauses", {"z_top": top_hi, "count": 0}],
        [name, "depth", {"z_min": z_cut}],
        [name, "rapids_clear", {"z_top": top_hi}],
        [name, "air_feed", {"z_top": top}],
        [
            name,
            "outline",
            {
                "elements": work_elements,
                "passes": [{"offset": r, "levels": levels}],
                "z_top": top,
                # The way in and back out through the blank's front margin,
                # at every level: waste in no order (each level's way out
                # follows its pass, the next level's way in follows that).
                "leads": [
                    {
                        "centre": [entry_x, _r((entry_y + start_y) / 2)],
                        "radius": (start_y - entry_y) / 2,
                        "levels": levels,
                    }
                ],
                "cut": "conventional",
                "part": "left",
            },
        ],
        [name, "keep_out", {"radius": r, "boxes": boxes}],
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
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job;
    returns {"ops": {operation key: operation}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(
            doc, f"Comb {key}", ctx["step"], frame["origin"], frame["axes"]
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
    """What the as-machined report needs: the snipped blank on the nominal
    tape stack, at its steel-rule place on the plate (CB01's stock box:
    blank_left_x_mm and blank_back_y_mm in from the plate's left end and
    back edge), the sheet's thickness at the drawing's stock band
    (``top.stock_thickness``) and its nominal (``stock_thickness_nominal``,
    the .020 sheet as bought). The underside lies on the tape, so it stays
    put and a thicker sheet stands higher; the tape stack's own band moves
    the whole sheet and is not a blank size. Expected: the staircase's
    inside corners left at the cutter's radius (drawn sharp); on the
    thickest sheet the as-rolled top over the nominal runs into the same
    region, so it is declared for that length alone."""
    f = inputs.features["features"]
    top = f["top"]
    lo, hi = top["stock_thickness"]
    thickness = {"nominal": top["stock_thickness_nominal"], "min": lo, "max": hi}
    x, y, (z0, _z1) = ctx["jobs"][0]["stock"]
    r = ctx["jobs"][0]["dia"] / 2
    # A sharp drawn corner cut at the cutter's r leaves r(1 - 1/√2) to the
    # nearer wall; with the sheet's excess on top, the corner's top edge
    # stands that and the excess apart. Plus the post's 0.001 mm rounding
    # of the path (the report measures 0.0003 over the bare figure).
    corner = r * (1 - 1 / math.sqrt(2)) + 0.001
    excess = hi - thickness["nominal"]
    underside = _plane(f, "underside", "z")
    xs = [_plane(f, "south_end", "x"), _plane(f, "north_end", "x")]
    ys = [_plane(f, "far_edge", "y"), _plane(f, "back", "y")]
    reason = (
        "the staircase's inside corners are drawn sharp and cut at the 1/32 in"
        " end mill's radius, under the title block's inside-corner max"
        " (plan inside_corner_max_mm)"
    )
    expected = [
        {
            "name": "inside corners at the cutter's radius",
            "kind": "left",
            "within": [xs, ys, [underside, underside + thickness["nominal"]]],
            "reason": reason,
            "max_mm": corner,
            "variants": ["nominal", "min"],
        },
        {
            "name": "inside corners on the thickest as-rolled sheet",
            "kind": "left",
            "within": [xs, ys, [underside, underside + hi]],
            "reason": reason + "; the .020 sheet as bought may stand to its"
            " stock band's top, over the drawing's nominal (plan Setup 1 mikes it)",
            "max_mm": math.hypot(corner, excess),
            "variants": ["max"],
        },
    ]
    return {
        "parts": {
            "": {
                "blank": {
                    "frame": "plate",
                    "box": [list(x), list(y), [z0, z0 + thickness["nominal"]]],
                    "length": {"axis": "z", "keep": "min", "mm": thickness},
                },
                "expected": expected,
            }
        },
        "skip": {},
    }
