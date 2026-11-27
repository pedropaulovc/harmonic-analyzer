"""FreeCAD CAM recipe for MHA-PD-14, the latch hook.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. No part dimension is
typed here: the flat pattern (the ear and base, the arm, its taper, the root
relief and the full round tip), the formed profile (the roll, the straight,
the tab and their printed stations), the strip and the screw holes come
from the manifest; the blank, the die blank, the parts' places, the tape
stack, the tips, the depth levels, the vise, the plate and the strip's
springback inputs from ``plan.toml`` ``[parameters]``; the cutters' and the
drill's diameters, flute length, speeds and feeds from the shop (``shop/``)
or the plan's cut rows. Typed here, because neither record carries them: the
safe and clearance heights, the vise jaws' depth (keep-out shapes only), the
share of a printed band the posted path may use, the die profile's stray
allowance, the channel passes' margin and run-out, the twist drill's
point angle and the search step for the springback window.

Route (plan text in ``plan.toml``):

- HL01_sheet, the 1/16 in carbide downcut end mill (T1): the blank sawn off
  the .032 sheet bonded to the spoil plate on blue painter's tape on both
  faces with CA glue between (owner 2026-11-23). The hook's flat pattern
  (the ear and base as one L with the arm hanging off the ear's top edge) and
  a trial strip (the arm's width and length, the same full round tip) nested
  in the L's elbow, each cut round in two levels, the last into the plate.
- HL02_former, the 1/4 in carbide end mill (T2): the former, two die halves
  from one length of the on-hand 6061 1/2 x 6 bar, bonded the same way.
  Each half's face is the strip's face as pressed (the springback-corrected
  roll and tab, Ri/Rf = 4x^3 - 3x + 1, x = Ri Y / (E t), at the design yield
  and the nominal strip); the faces face each other across a channel, cut
  first at every level (a slot along the inner face, a pass along the
  outer), then each half is cut round (back edge, ends, face) at each level.
- HL03_holes, the #30 drill (T3): the 2X screw holes through the base after
  the ear is bent, the base bonded flat to the plate, the ear standing up.

Work frames (G54), +Y toward the fixed jaw, Z0 the spoil plate's top:
HL01 and HL02, X0 the plate's left end, Y0 the fixed jaw's face; HL03, X0
the ear's outer face, Y0 the base's low edge (the model's frame, moved up by
the tape stack). Every outline is run anticlockwise (the part on the
cutter's left) and every clearing pass the outline's way, its stock on the
left, but the die channel's opening slot, which meets both sides:
conventional with a clockwise spindle (owner 2026-11-25).
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "pd_latch_hook"
COMMENT = "MHA-PD-14 latch hook"
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("HL01_sheet", ("sheet",)),
    ("HL02_former", ("former",)),
    ("HL03_holes", ("holes",)),
)
# Each file loads its own tool (M6, the tool setter): each setup starts on
# whatever the mill last held.
LOAD_FIRST_TOOL = ("HL01_sheet", "HL02_former", "HL03_holes")
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these.
CAM_TOOLS = ("em-sixteenth", "em-quarter", "drill-30")
AS_MACHINED_NOT_COVERED = (
    "the STEP is the formed hook; HL01 cuts its flat pattern, HL02 the former"
    " from bar and HL03 drills the base after a hand bend, so no program cuts"
    " the STEP's shape from one stock"
)
IN = 25.4
# The descent starts this far above the stock top: real G0 brings the cutter
# to it.
SAFE_MM = 1.0
# Moves to and from the cut run this far above the stock top (or the jaws).
CLEAR_MM = 5.0
# Keep-outs: each vise jaw's depth away from the plate it grips.
JAW_DEPTH_MM = IN
# The posted path's cutter centre may stray from its offset by this share of
# the tightest printed band locating that edge; the rest is the machine's.
BAND_FRACTION = 0.1
# The die halves and the trial strip are tooling with no printed band: their
# paths may stray this far.
DIE_TOL_MM = 0.05
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# Jobber drills' point (the shop record gives the diameter only).
DRILL_POINT_DEG = 118.0
# The die channel's passes run this far off each finished face (the
# finishing loops take it), and start and stop this far beyond what the
# cutter can reach of the blank; the outline check counts clearing this far
# past the blank's ends.
CLEARING_MARGIN_MM = 0.5
CLEARING_EXTENSION_MM = 40.0
# The springback window is searched in steps of this many MPa of yield.
WINDOW_STEP_MPA = 0.05
# The engagement check's cell (mm), finer than its 0.05 default: a full-width
# slot run obliquely across that grid reads up to 1.2 cells over the cutter's
# width (6.41 for 6.35 on HL02's lead-ins), past the check's one-cell slack;
# at 0.025 it reads 6.37, within it.
ENGAGEMENT_CELL_MM = 0.025


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


def _cut_speed(plan: dict[str, Any], cut: str) -> tuple[float, float, dict[str, Any]]:
    """(rpm, mm/min) the plan authors on the cut, agreeing with its
    operation's rpm (a shop setting's or the op's own)."""
    op, _record = _op_with_cut(plan, cut)
    rpm, feed = _cut(plan, cut, "rpm"), _cut(plan, cut, "feed_mm_min")
    return rpm, feed, op


def _plan_tool(plan: dict[str, Any], tool: str) -> dict[str, Any]:
    return next(t for t in plan["tools"] if t["id"] == tool)


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


def _band(feature: dict[str, Any], key: str) -> float:
    low, high = feature[key]
    return high - low


def _within(value: float, band: list[float]) -> bool:
    return band[0] - 1e-9 <= value <= band[1] + 1e-9


def _cross(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _line(name: str, s, e, tol: float) -> dict[str, Any]:
    return {"name": name, "start": [s[0], s[1]], "end": [e[0], e[1]], "tol": tol}


def _arc(name: str, s, e, c, tol: float) -> dict[str, Any]:
    """A minor arc from ``s`` to ``e`` about ``c`` (its way: the shorter one)."""
    if not math.isclose(math.dist(c, s), math.dist(c, e), abs_tol=1e-6):
        raise ValueError(f"{name}: its ends are not on one circle")
    element = _line(name, s, e, tol)
    element["centre"] = [c[0], c[1]]
    return element


def _ccw(element: dict[str, Any]) -> bool:
    c, s, e = element["centre"], element["start"], element["end"]
    return _cross((s[0] - c[0], s[1] - c[1]), (e[0] - c[0], e[1] - c[1])) > 0


def _tangent(element: dict[str, Any], at: str) -> tuple[float, float]:
    """The element's unit direction of travel at its ``start`` or ``end``."""
    s, e = element["start"], element["end"]
    if "centre" not in element:
        d = math.dist(s, e)
        return ((e[0] - s[0]) / d, (e[1] - s[1]) / d)
    c, p = element["centre"], element[at]
    radius = math.dist(c, p)
    v = ((p[0] - c[0]) / radius, (p[1] - c[1]) / radius)
    return (-v[1], v[0]) if _ccw(element) else (v[1], -v[0])


def _reversed(element: dict[str, Any]) -> dict[str, Any]:
    flipped = dict(element)
    flipped["start"], flipped["end"] = list(element["end"]), list(element["start"])
    return flipped


def _mapped(element: dict[str, Any], f) -> dict[str, Any]:
    """``element`` through the rigid motion ``f`` (a rotation, never a mirror,
    so an arc keeps its sense)."""
    moved = dict(element)
    for key in ("start", "end", "centre"):
        if key in element:
            moved[key] = list(f(element[key]))
    return moved


def _offset_one(element: dict[str, Any], d: float) -> dict[str, Any]:
    """``element`` moved ``d`` to the right of its way (negative: left)."""
    if "centre" not in element:
        u = _tangent(element, "start")
        return _mapped(element, lambda p: (p[0] + u[1] * d, p[1] - u[0] * d))
    c = element["centre"]
    radius = math.dist(c, element["start"])
    # Anticlockwise: the centre is on the left, so the right grows the radius.
    new = radius + d if _ccw(element) else radius - d
    if new <= 0:
        raise ValueError(
            f"{element['name']}: R{radius:.4f} under the offset {abs(d):.4f}"
        )
    k = new / radius

    def pt(p):
        return [c[0] + (p[0] - c[0]) * k, c[1] + (p[1] - c[1]) * k]

    return dict(element) | {"start": pt(element["start"]), "end": pt(element["end"])}


def _offset_chain(elements: list[dict[str, Any]], d: float) -> list[dict[str, Any]]:
    """An open chain of tangent elements moved ``d`` to the right."""
    moved = [_offset_one(e, d) for e in elements]
    for a, b in zip(moved, moved[1:]):
        if math.dist(a["end"], b["start"]) > 1e-6:
            raise ValueError(f"{a['name']} → {b['name']}: not tangent")
    return moved


def _meet(a: dict[str, Any], b: dict[str, Any]) -> list[float]:
    """Where the lines through two line elements cross."""
    ua, ub = _tangent(a, "start"), _tangent(b, "start")
    den = _cross(ua, ub)
    if abs(den) < 1e-12:
        raise ValueError(f"{a['name']} and {b['name']} are parallel")
    w = (b["start"][0] - a["start"][0], b["start"][1] - a["start"][1])
    k = _cross(w, ub) / den
    return [a["start"][0] + ua[0] * k, a["start"][1] + ua[1] * k]


def _loop(
    elements: list[dict[str, Any]],
    r: float,
    inside_max: float,
    start: str,
    span: tuple[int, int] | None = None,
) -> list[tuple]:
    """The cutter-centre path ``r`` to the right of a closed outline run
    anticlockwise (outside the part), from the middle (``start="mid"``) or
    the start (``"start"``) of the first element, which must be a line, back
    to it. A tangent joint joins directly; a convex corner is rounded by a G3
    arc about it; a concave corner between two lines is cut sharp where the
    two offset lines cross (the cutter leaves its own radius there, inside
    the title block's INSIDE CORNERS max, ``inside_max``, which the cutter's
    radius is checked against). With
    ``span`` (first, last element), only those elements' pieces and the
    corners between them, open at both ends. Returns segments ("line", start,
    end) or ("arc", start, end, centre, clockwise)."""
    if r > inside_max + 1e-9:
        raise ValueError(
            f"the cutter's R{r:.4f} is over the title block's inside-corner"
            f" R{inside_max:.4f} max"
        )
    if "centre" in elements[0]:
        raise ValueError("the loop must start on a line")
    count = len(elements)
    moved = [_offset_one(e, r) for e in elements]
    corners: list[list[float] | None] = []
    for k in range(count):
        j = (k + 1) % count
        u_in, u_out = _tangent(elements[k], "end"), _tangent(elements[j], "start")
        turn = _cross(u_in, u_out)
        if abs(turn) < 1e-9 and u_in[0] * u_out[0] + u_in[1] * u_out[1] > 0:
            if math.dist(moved[k]["end"], moved[j]["start"]) > 1e-6:
                raise ValueError(f"{elements[k]['name']}: offset ends do not meet")
            corners.append(None)
            continue
        if turn > 0:
            corners.append(list(elements[k]["end"]))
            continue
        if "centre" in elements[k] or "centre" in elements[j]:
            raise ValueError(
                f"inside corner after {elements[k]['name']}: only two lines may"
                " meet in a concave corner"
            )
        p = _meet(moved[k], moved[j])
        for e, key, other in ((moved[k], "end", "start"), (moved[j], "start", "end")):
            e[key] = p
            u = _tangent(elements[k] if e is moved[k] else elements[j], "start")
            a, b = e["start"], e["end"]
            if (b[0] - a[0]) * u[0] + (b[1] - a[1]) * u[1] <= 0:
                raise ValueError(
                    f"{e['name']}: the cutter does not fit before the corner"
                )
        corners.append(None)
    tagged: list[tuple[float, tuple]] = []
    for k in range(count):
        e = moved[k]
        if "centre" in e:
            tagged.append((k, ("arc", e["start"], e["end"], e["centre"], not _ccw(e))))
        else:
            tagged.append((k, ("line", e["start"], e["end"])))
        if corners[k] is not None:
            tagged.append(
                (
                    k + 0.5,
                    (
                        "arc",
                        e["end"],
                        moved[(k + 1) % count]["start"],
                        corners[k],
                        False,
                    ),
                )
            )
    if span is not None:
        return [piece for tag, piece in tagged if span[0] <= tag <= span[1]]
    pieces = [piece for _tag, piece in tagged]
    if start == "start":
        return pieces
    first = pieces[0]
    mid = [(first[1][0] + first[2][0]) / 2, (first[1][1] + first[2][1]) / 2]
    return [("line", mid, first[2]), *pieces[1:], ("line", first[1], mid)]


def _moves(segs: list[tuple]) -> list[str]:
    """The segments as feed moves in the work frame (each from the last end)."""
    lines = []
    for seg in segs:
        x, y = _r(seg[2][0]), _r(seg[2][1])
        if seg[0] == "line":
            if math.dist(seg[1], seg[2]) < 1e-6:
                continue
            lines.append(f"G1 X{x:.3f} Y{y:.3f} F{{feed}}")
        else:
            c = seg[3]
            i, j = _r(c[0] - seg[1][0]), _r(c[1] - seg[1][1])
            word = "G2" if seg[4] else "G3"
            lines.append(f"{word} X{x:.3f} Y{y:.3f} I{i:.3f} J{j:.3f} F{{feed}}")
    return lines


def _samples(element: dict[str, Any], step: float) -> list[tuple[float, float]]:
    """Points along an element, at most ``step`` apart, both ends included."""
    s, e = element["start"], element["end"]
    if "centre" not in element:
        n = max(1, math.ceil(math.dist(s, e) / step))
        return [
            (s[0] + (e[0] - s[0]) * k / n, s[1] + (e[1] - s[1]) * k / n)
            for k in range(n + 1)
        ]
    c = element["centre"]
    radius = math.dist(c, s)
    a0 = math.atan2(s[1] - c[1], s[0] - c[0])
    a1 = math.atan2(e[1] - c[1], e[0] - c[0])
    sweep = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    n = max(1, math.ceil(radius * abs(sweep) / step))
    return [
        (
            c[0] + radius * math.cos(a0 + sweep * k / n),
            c[1] + radius * math.sin(a0 + sweep * k / n),
        )
        for k in range(n + 1)
    ]


def _area(elements: list[dict[str, Any]]) -> float:
    """Signed area (shoelace over each element's chords)."""
    pts = [q for e in elements for q in _samples(e, 0.25)[:-1]]
    return 0.5 * sum(_cross(p, q) for p, q in zip(pts, pts[1:] + pts[:1]))


def _distance(elements: list[dict[str, Any]], p: tuple[float, float]) -> float:
    """XY distance from ``p`` to the nearest of an open chain's elements."""
    best = math.inf
    for e in elements:
        s, t = e["start"], e["end"]
        if "centre" not in e:
            dx, dy = t[0] - s[0], t[1] - s[1]
            k = max(
                0.0,
                min(
                    1.0, ((p[0] - s[0]) * dx + (p[1] - s[1]) * dy) / (dx * dx + dy * dy)
                ),
            )
            best = min(best, math.dist(p, (s[0] + k * dx, s[1] + k * dy)))
            continue
        c = e["centre"]
        radius = math.dist(c, s)
        turn = _cross((s[0] - c[0], s[1] - c[1]), (t[0] - c[0], t[1] - c[1]))
        v = (p[0] - c[0], p[1] - c[1])
        inside = (
            _cross((s[0] - c[0], s[1] - c[1]), v) * turn > 0
            and _cross(v, (t[0] - c[0], t[1] - c[1])) * turn > 0
            and v[0] * (s[0] + t[0] - 2 * c[0]) + v[1] * (s[1] + t[1] - 2 * c[1]) > 0
        )
        if inside:
            best = min(best, abs(math.hypot(*v) - radius))
        else:
            best = min(best, math.dist(p, s), math.dist(p, t))
    return best


def _rotate(p, c, a: float) -> tuple[float, float]:
    ca, sa = math.cos(a), math.sin(a)
    return (
        c[0] + (p[0] - c[0]) * ca - (p[1] - c[1]) * sa,
        c[1] + (p[0] - c[0]) * sa + (p[1] - c[1]) * ca,
    )


def _point(dia: float) -> float:
    """A twist drill's point length."""
    return dia / 2 / math.tan(math.radians(DRILL_POINT_DEG / 2))


# --- The formed profile and its springback ---------------------------------


def _springback(ri: float, yield_mpa: float, modulus: float, t: float) -> float:
    """Ri/Rf of a strip bent to inside radius ``ri`` and let go:
    4x^3 - 3x + 1, x = Ri Y / (E t); refused from x = 1/2, where the bend
    stays elastic."""
    x = ri * yield_mpa / (modulus * t)
    if x >= 0.5:
        raise ValueError(f"an inside R{ri:.3f} stays elastic: the strip takes no set")
    return 4 * x**3 - 3 * x + 1


def _let_go(
    ri: float, deg: float, yield_mpa: float, modulus: float, t: float
) -> tuple[float, float]:
    """(inside radius, angle) a bend pressed to ``ri`` and ``deg`` springs back
    to: the radius by :func:`_springback`, the angle keeping the mid surface's
    length."""
    rf = ri / _springback(ri, yield_mpa, modulus, t)
    return rf, deg * (ri + t / 2) / (rf + t / 2)


def _die_for(
    rf: float, deg: float, yield_mpa: float, modulus: float, t: float
) -> tuple[float, float]:
    """(inside radius, angle) to press so the bend springs back to ``rf`` and
    ``deg`` (the formed radius rises with the pressed one)."""
    lo, hi = 1e-3, rf
    for _ in range(200):
        mid = (lo + hi) / 2
        if _let_go(mid, deg, yield_mpa, modulus, t)[0] > rf:
            hi = mid
        else:
            lo = mid
    ri = (lo + hi) / 2
    return ri, deg * (rf + t / 2) / (ri + t / 2)


def _walk(
    g: dict[str, float],
    t: float,
    roll: tuple[float, float],
    tab: tuple[float, float],
    tail: float = 0.0,
    tol: float = DIE_TOL_MM,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The strip's mid surface in the model's X/Y from the ear's lower edge
    (−t/2, 0) down the arm: the straight run to the roll, the roll (turning
    toward −X), the straight, the tab (turning back toward +X) to its square
    end, and ``tail`` more straight past it. ``roll`` and ``tab`` are each
    (inside radius, angle): the roll's inside face is its −X face, the tab's
    its +X face."""
    p = (-t / 2, 0.0)
    h = -math.pi / 2
    q = (p[0], p[1] - g["start"])
    els = [_line("lead-in", p, q, tol)]
    p = q
    rm = roll[0] + t / 2
    c = (p[0] + rm * math.sin(h), p[1] - rm * math.cos(h))
    a = math.radians(roll[1])
    q = _rotate(p, c, -a)
    els.append(_arc("roll", p, q, c, tol))
    roll_end, p, h = q, q, h - a
    straight_h = h
    q = (p[0] + g["straight"] * math.cos(h), p[1] + g["straight"] * math.sin(h))
    els.append(_line("straight", p, q, tol))
    tab_start, p = q, q
    rm = tab[0] + t / 2
    c = (p[0] - rm * math.sin(h), p[1] + rm * math.cos(h))
    a = math.radians(tab[1])
    q = _rotate(p, c, a)
    els.append(_arc("tab", p, q, c, tol))
    p, h = q, h + a
    if tail:
        els.append(
            _line(
                "runout", p, (p[0] + tail * math.cos(h), p[1] + tail * math.sin(h)), tol
            )
        )
    return els, {
        "roll_end": roll_end,
        "straight_h": straight_h,
        "tab_start": tab_start,
        "tab_centre": c,
        "tab_end": p,
    }


def _formed(g: dict[str, float], t: float, roll, tab) -> dict[str, float]:
    """The printed formed values of a hook whose roll and tab are ``roll``
    and ``tab`` (inside radius, angle), and the two caliper checks: the tab's
    far point from the ear's outer face (``tip_x``) and the ear's top edge to
    the tip (``overall``)."""
    _els, w = _walk(g, t, roll, tab)
    h = w["straight_h"]
    left = (-math.sin(h), math.cos(h))
    re_ = w["roll_end"]
    face = (
        re_[0] + g["run"] * math.cos(h) + left[0] * t / 2,
        re_[1] + g["run"] * math.sin(h) + left[1] * t / 2,
    )
    c, end = w["tab_centre"], w["tab_end"]
    rm = math.dist(c, end)
    inward = ((c[0] - end[0]) / rm, (c[1] - end[1]) / rm)
    concave = (end[0] + inward[0] * t / 2, end[1] + inward[1] * t / 2)
    # The strip ends at its tip, the full round's crown, trim short of the
    # tab's square end on the mid surface.
    a_tip = math.radians(tab[1]) - g["trim"] / rm
    tip = _rotate(w["tab_start"], c, a_tip)
    out = ((tip[0] - c[0]) / rm, (tip[1] - c[1]) / rm)
    corners = [
        (tip[0] + out[0] * t / 2, tip[1] + out[1] * t / 2),
        (tip[0] - out[0] * t / 2, tip[1] - out[1] * t / 2),
    ]
    a0 = math.atan2(w["tab_start"][1] - c[1], w["tab_start"][0] - c[0])
    convex = [
        (
            c[0] + (rm + t / 2) * math.cos(a0 + a_tip * k / 64),
            c[1] + (rm + t / 2) * math.sin(a0 + a_tip * k / 64),
        )
        for k in range(65)
    ]
    return {
        "start": g["start"],
        "roll_r": roll[0],
        "tab_r": tab[0],
        "face_x": -face[0],
        "face_y": -face[1],
        "tab_end_x": -concave[0],
        "tip_x": -min(p[0] for p in convex + corners),
        "overall": g["width"] - min(p[1] for p in corners),
    }


def _geometry(f: dict[str, Any]) -> dict[str, Any]:
    """The flat pattern and the formed profile, from the manifest."""
    strip, roll, tab, face = f["strip"], f["roll"], f["tab"], f["far_face"]
    t = strip["thickness_nominal"]
    width = f["side_edge"]["width_nominal"]
    if (
        f["side_edge"]["width_from"] != "low_edge"
        or f["side_edge"]["plane"]["value"] != width
    ):
        raise ValueError(
            "side_edge: expected the ear's width from its low edge at model Y0"
        )
    dev_tip = strip["developed_length"] - width
    g = {
        "t": t,
        "width": width,
        "flat": strip["width_nominal"],
        "dev_tip": dev_tip,
        "start": roll["start_nominal"],
        "straight": face["straight_length"],
    }
    l_roll = (roll["radius_nominal"] + t / 2) * math.radians(roll["angle"])
    l_tab = (tab["radius_nominal"] + t / 2) * math.radians(tab["angle"])
    if not math.isclose(roll["flat_centreline"], g["start"] + l_roll / 2, abs_tol=1e-3):
        raise ValueError("roll: its flat centreline is not its mid-surface middle")
    tab_start = g["start"] + l_roll + g["straight"]
    if not math.isclose(tab["flat_centreline"], tab_start + l_tab / 2, abs_tol=1e-3):
        raise ValueError(
            "tab: its flat centreline is not the straight's end plus half its arc"
        )
    g["trim"] = tab_start + l_tab - dev_tip
    if g["trim"] < 0:
        raise ValueError("the tab's square end falls short of the strip's tip")
    g["dev_tab_start"] = tab_start
    # The far face's station: from the roll's end along the straight.
    nominal_roll = (roll["radius_nominal"], roll["angle"])
    nominal_tab = (tab["radius_nominal"], tab["angle"])
    _els, w = _walk(g | {"run": 0.0}, t, nominal_roll, nominal_tab)
    h = w["straight_h"]
    left = (-math.sin(h), math.cos(h))
    p = (-face["x_nominal"] - left[0] * t / 2, -face["y_nominal"] - left[1] * t / 2)
    d = (p[0] - w["roll_end"][0], p[1] - w["roll_end"][1])
    g["run"] = d[0] * math.cos(h) + d[1] * math.sin(h)
    if (
        abs(_cross((math.cos(h), math.sin(h)), d)) > 1e-3
        or not 0 < g["run"] < g["straight"]
    ):
        raise ValueError("far_face: its point is not on the straight's far face")
    nominal = _formed(g, t, nominal_roll, nominal_tab)
    if not math.isclose(nominal["tab_end_x"], tab["end_x_nominal"], abs_tol=1e-3):
        raise ValueError("tab: the walked profile does not end at the printed end_x")
    if not math.isclose(
        nominal["overall"], f["tip_round"]["overall_height"], abs_tol=0.05
    ):
        raise ValueError(
            "tip_round: the walked profile's overall height is not the export's"
        )
    g["nominal"] = nominal
    g["roll"], g["tab"] = nominal_roll, nominal_tab
    g["bands"] = {
        "start": roll["start"],
        "roll_r": roll["radius"],
        "tab_r": tab["radius"],
        "face_x": face["x"],
        "face_y": face["y"],
        "tab_end_x": tab["end_x"],
    }
    return g


def _flat(
    f: dict[str, Any], g: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, float]]:
    """The hook's flat pattern and the trial strip, each anticlockwise in its
    own (a, b): a across the strip from the ear's top edge (the arm's rear
    edge), b along it from the ear's lower edge (the arm hangs to −b). The
    hook's first element is the top bar's top edge; the strip's its top end
    (station 0, the ear's lower edge)."""
    flat, width, dev_tip = g["flat"], g["width"], g["dev_tip"]
    tip = f["tip_round"]
    rr = tip["radius"]
    cs = tip["centre_station_nominal"]
    low_w = f["arm_low_front"]["width_nominal"]
    arm_w = f["arm_front"]["width_nominal"]
    t0, t1 = f["taper"]["start_nominal"], f["taper"]["end_nominal"]
    root = f["root_relief"]["radius_nominal"]
    if not math.isclose(cs, dev_tip - rr, abs_tol=1e-3):
        raise ValueError("tip_round: its centre is not one radius short of the tip")
    if not math.isclose(low_w, 2 * rr, abs_tol=1e-3):
        raise ValueError("tip_round: the full round is not the arm's whole width")
    for name in ("arm_front", "arm_low_front"):
        if f[name]["width_from"] != "ear_top":
            raise ValueError(f"{name}: expected its width from the ear's top edge")
    bands = [
        _band(f["side_edge"], "width"),
        _band(f["strip"], "width"),
        _band(f["arm_front"], "width"),
        _band(f["arm_low_front"], "width"),
        _band(f["taper"], "start"),
        _band(f["taper"], "end"),
        _band(f["root_relief"], "radius"),
        _band(tip, "centre_station"),
    ]
    tol = BAND_FRACTION * min(bands)
    hook = [
        _line("top edge", (flat, width), (0.0, width), tol),
        _line("rear edge", (0.0, width), (0.0, -cs), tol),
        _arc("tip round, rear half", (0.0, -cs), (rr, -dev_tip), (rr, -cs), tol),
        _arc("tip round, front half", (rr, -dev_tip), (low_w, -cs), (rr, -cs), tol),
        _line("low front edge", (low_w, -cs), (low_w, -t1), tol),
        _line("taper", (low_w, -t1), (arm_w, -t0), tol),
        _line("front edge", (arm_w, -t0), (arm_w, -root), tol),
        _arc(
            "root relief",
            (arm_w, -root),
            (arm_w + root, 0.0),
            (arm_w + root, -root),
            tol,
        ),
        _line("ear lower edge", (arm_w + root, 0.0), (flat, 0.0), tol),
        _line("base end", (flat, 0.0), (flat, width), tol),
    ]
    trial = [
        _line("top end", (low_w, 0.0), (0.0, 0.0), DIE_TOL_MM),
        _line("rear edge", (0.0, 0.0), (0.0, -cs), DIE_TOL_MM),
        _arc("tip round, rear half", (0.0, -cs), (rr, -dev_tip), (rr, -cs), DIE_TOL_MM),
        _arc(
            "tip round, front half", (rr, -dev_tip), (low_w, -cs), (rr, -cs), DIE_TOL_MM
        ),
        _line("front edge", (low_w, -cs), (low_w, 0.0), DIE_TOL_MM),
    ]
    return hook, trial, {"low_w": low_w, "arm_w": arm_w, "root": root}


def _seg_tangent(seg: tuple, at: str) -> tuple[float, float]:
    """The unit way of a ``_loop`` segment at its ``"start"`` or ``"end"``."""
    q = seg[1] if at == "start" else seg[2]
    if seg[0] == "line":
        length = math.dist(seg[1], seg[2])
        return ((seg[2][0] - seg[1][0]) / length, (seg[2][1] - seg[1][1]) / length)
    c = seg[3]
    radius = math.dist(c, q)
    v = ((q[0] - c[0]) / radius, (q[1] - c[1]) / radius)
    return (v[1], -v[0]) if seg[4] else (-v[1], v[0])


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    f = features["features"]
    p = plan["parameters"]
    g = _geometry(f)
    t = g["t"]
    t_min, t_max = f["strip"]["thickness"]
    _agree(plan, "strip_thickness_max_mm", t_max)
    hook, trial, d = _flat(f, g)
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")
    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    inside_max = p["inside_corner_max_mm"]

    # --- The plate and the vise (every CNC setup): the plate across the
    # jaws, its back edge on the fixed jaw (Y0 in HL01 and HL02), its top
    # (Z0) below the jaw tops by the jaw height less the parallels and the
    # plate.
    plate_l, plate_w = p["plate_length_mm"], p["plate_width_mm"]
    jaw_top = (
        p["vise_jaw_height_mm"] - p["parallel_height_mm"] - p["plate_thickness_mm"]
    )
    _agree(plan, "jaw_top_over_plate_mm", jaw_top)
    stack = p["tape_stack_mm"]
    stack_lo, stack_hi = p["tape_stack_min_mm"], p["tape_stack_max_mm"]
    if not stack_lo <= stack <= stack_hi:
        raise ValueError("the tape stack is outside its band")

    def plate_boxes(dx: float, dy: float, spoil: float) -> list[dict[str, Any]]:
        """The jaws and the plate in a frame whose plate's left end and fixed
        jaw's face stand at X ``dx``, Y ``dy``."""
        x = (dx, dx + plate_l)
        return [
            _box("fixed jaw", x, (dy, dy + JAW_DEPTH_MM), jaw_top),
            _box("moving jaw", x, (dy - plate_w - JAW_DEPTH_MM, dy - plate_w), jaw_top),
            _box("spoil plate", x, (dy - plate_w, dy), -spoil),
        ]

    def levels_for(top: float, tip: float, dia: float, key: str) -> list[float]:
        depth = top - tip
        _agree(plan, f"{key}_depth_mm", depth)
        count = math.ceil(depth / (p["level_depth_max_fraction"] * dia) - 1e-9)
        if count != p[f"{key}_level_count"]:
            raise ValueError(
                f"process.{key}_level_count {p[f'{key}_level_count']}, the recipe computes {count}"
            )
        step = depth / count
        _agree(plan, f"{key}_level_depth_mm", step)
        levels = [_r(top - step * (k + 1)) for k in range(count)]
        levels[-1] = _r(tip)
        return levels

    # ===== HL01_sheet: the flat pattern and the trial strip =====
    em = shop["tools"][_plan_tool(plan, "em-sixteenth")["ref"]]
    dia = em["diameter_mm"]
    r = dia / 2
    rpm1, feed1, flutes1 = _setting(plan, shop, "sheet")
    if not math.isclose(_cut(plan, "sheet", "cutter_dia_mm"), dia, abs_tol=1e-6):
        raise ValueError("'sheet' cutter_dia_mm is not the 1/16 end mill's diameter")
    # The downcut's helix pushes the taped strip onto the tape.
    if _plan_tool(plan, "em-sixteenth").get("axial_direction") != "down":
        raise ValueError("em-sixteenth: the plan's end mill must be a downcut")
    tip1 = p["sheet_tip_z_mm"]
    _agree(plan, "sheet_tip_into_plate_mm", -tip1)
    if not -p["spoil_cut_max_mm"] <= tip1 <= 0.0:
        raise ValueError(
            "the sheet cutter's tip must stand at or below the plate top, within spoil_cut_max_mm"
        )
    if stack_lo - tip1 < p["through_margin_min_mm"]:
        raise ValueError(
            "the tip is not through_margin_min_mm under the thinnest strip on the thinnest stack"
        )
    top1 = stack_hi + t_max
    if top1 - tip1 > em["flute_length_mm"]:
        raise ValueError("the sheet cut is deeper than the 1/16 end mill's flutes")
    levels1 = levels_for(top1, tip1, dia, "sheet")
    if _cut(plan, "sheet", "axial_doc_mm") + 1e-6 < top1 - levels1[0]:
        raise ValueError("'sheet' axial_doc_mm is under one level's depth")

    blank_l, blank_w = p["blank_length_in"] * IN, p["blank_width_in"] * IN
    _agree(plan, "blank_length_mm", blank_l)
    _agree(plan, "blank_width_mm", blank_w)
    left, margin, gap = p["part_left_x_mm"], p["part_margin_y_mm"], p["part_gap_mm"]
    flat, width, dev_tip = g["flat"], g["width"], g["dev_tip"]
    low_w = d["low_w"]
    if gap < dia + 2 * DIE_TOL_MM:
        raise ValueError("part_gap_mm: the hook's and the strip's paths would overlap")
    y_low = -margin - flat
    _agree(plan, "hook_base_end_y_mm", y_low + flat)

    def to_hook(q):
        return (left + width - q[1], y_low + q[0])

    def to_trial(q):
        return (left + width + gap - q[1], y_low + low_w + gap + q[0])

    hook_w = [_mapped(e, to_hook) | {"name": f"hook {e['name']}"} for e in hook]
    trial_w = [
        _mapped(e, to_trial) | {"name": f"trial strip {e['name']}"} for e in trial
    ]
    for outline in (hook_w, trial_w):
        if _area(outline) <= 0:
            raise ValueError("an outline does not run anticlockwise")
    nearest = min(_distance(hook_w, q) for e in trial_w for q in _samples(e, 0.25))
    if nearest < gap - 1e-6:
        raise ValueError(
            f"the trial strip stands {nearest:.3f} off the hook, under part_gap_mm"
        )
    right = blank_l - (left + width + gap + dev_tip)
    _agree(plan, "blank_right_margin_mm", right)
    front = blank_w - margin - flat
    _agree(plan, "blank_front_margin_mm", front)
    if min(right, front, left) < dia + p["saw_error_mm"]:
        raise ValueError("a blank margin is under the cutter plus the saw's wander")
    if y_low + 2 * low_w + gap > -margin:
        raise ValueError("the trial strip does not fit the L's elbow")
    if blank_l > plate_l or blank_w > plate_w:
        raise ValueError("the blank runs off the plate")
    _agree(plan, "sheet_from_x_mm", left - r)
    _agree(plan, "sheet_to_x_mm", left + width + gap + dev_tip + r)
    if p["em_sixteenth_projection_min_mm"] < jaw_top - tip1 + CLEAR_MM:
        raise ValueError(
            "em_sixteenth_projection_min_mm: the collet would not clear the jaw tops"
        )
    _agree(
        plan,
        "sheet_collet_over_jaw_mm",
        p["em_sixteenth_projection_min_mm"] + tip1 - jaw_top,
    )
    hook_area, trial_area = _area(hook), _area(trial)
    _agree(plan, "hook_bond_area_mm2", hook_area)
    _agree(plan, "trial_bond_area_mm2", trial_area)
    _agree(
        plan, "sheet_waste_bond_area_mm2", blank_l * blank_w - hook_area - trial_area
    )
    _agree(plan, "blank_area_mm2", blank_l * blank_w)
    _agree(plan, "hook_least_width_mm", d["arm_w"])
    _agree(plan, "trial_width_mm", low_w)

    plunge1 = feed1 * p["plunge_feed_fraction"]
    _agree(plan, "sheet_plunge_feed_mm_min", plunge1)
    clear1 = max(CLEAR_MM, jaw_top - top1 + CLEAR_MM)
    lines1 = [f"G0 Z{_r(top1 + clear1):.3f}"]
    for outline in (hook_w, trial_w):
        segs = _loop(outline, r, inside_max, "mid")
        sx, sy = _r(segs[0][1][0]), _r(segs[0][1][1])
        lines1 += [f"G0 X{sx:.3f} Y{sy:.3f}", f"G0 Z{_r(top1 + SAFE_MM):.3f}"]
        for z in levels1:
            # Plunged into the blank's waste on the path, then round once.
            lines1.append(f"G1 Z{z:.3f} F{{plunge}}")
            lines1 += _moves(segs)
        lines1.append(f"G0 Z{_r(top1 + clear1):.3f}")
    boxes1 = plate_boxes(0.0, 0.0, p["spoil_cut_max_mm"])

    # ===== HL02_former: the die halves =====
    e_mod = p["strip_modulus_mpa"]
    y_lo, y_hi = p["strip_yield_min_mpa"], p["strip_yield_max_mpa"]
    y_d = p["former_design_yield_mpa"]
    _agree(plan, "former_design_yield_mpa", (y_lo + y_hi) / 2)
    roll_die = _die_for(*g["roll"], y_d, e_mod, t)
    tab_die = _die_for(*g["tab"], y_d, e_mod, t)
    _agree(plan, "roll_die_radius_mm", roll_die[0])
    _agree(plan, "roll_die_deg", roll_die[1])
    _agree(plan, "tab_die_radius_mm", tab_die[0])
    _agree(plan, "tab_die_deg", tab_die[1])

    def pressed(yield_mpa: float, tt: float) -> dict[str, float]:
        return _formed(
            g,
            tt,
            _let_go(*roll_die, yield_mpa, e_mod, tt),
            _let_go(*tab_die, yield_mpa, e_mod, tt),
        )

    def lands(values: dict[str, float], keys=None) -> bool:
        return all(_within(values[k], g["bands"][k]) for k in (keys or g["bands"]))

    design = pressed(y_d, t)
    for key, value in design.items():
        if not math.isclose(value, g["nominal"][key], abs_tol=1e-6):
            raise ValueError(
                f"the former at the design point does not press the drawing's {key}"
            )
    if not lands(design):
        raise ValueError(
            "the drawing's nominal formed values are outside their own bands"
        )
    corners = [pressed(y, tt) for y in (y_lo, y_hi) for tt in (t_min, t_max)]
    for c in corners:
        if not lands(c, ("tab_r",)):
            raise ValueError(
                f"a yield/thickness corner springs the tab to R{c['tab_r']:.3f}, outside its band"
            )
    for key in ("roll_r", "tab_r", "face_x", "face_y", "tab_end_x"):
        _agree(plan, f"corner_{key}_min_mm", min(c[key] for c in corners))
        _agree(plan, f"corner_{key}_max_mm", max(c[key] for c in corners))
    # The window: the yields (nominal strip) this die presses every printed
    # value at, and the caliper checks' bands over it; the overall height
    # also over the strip's set-in (a shift along the arm) that keeps the roll
    # start and the far face's height in their bands.
    window = [y_d, y_d]
    for k, sign in ((0, -1.0), (1, 1.0)):
        while lands(pressed(window[k] + sign * WINDOW_STEP_MPA, t)):
            window[k] += sign * WINDOW_STEP_MPA
    _agree(plan, "window_yield_min_mpa", window[0])
    _agree(plan, "window_yield_max_mpa", window[1])
    tips, overall = [], []
    for k in range(21):
        v = pressed(window[0] + (window[1] - window[0]) * k / 20, t)
        tips.append(v["tip_x"])
        b_start, b_face = g["bands"]["start"], g["bands"]["face_y"]
        lo = max(b_start[0] - v["start"], b_face[0] - v["face_y"])
        hi = min(b_start[1] - v["start"], b_face[1] - v["face_y"])
        if lo <= hi:
            overall += [v["overall"] + lo, v["overall"] + hi]
    _agree(plan, "check_tip_x_min_mm", min(tips))
    _agree(plan, "check_tip_x_max_mm", max(tips))
    _agree(plan, "check_overall_min_mm", min(overall))
    _agree(plan, "check_overall_max_mm", max(overall))
    _agree(plan, "check_trial_length_min_mm", min(overall) - width)
    _agree(plan, "check_trial_length_max_mm", max(overall) - width)
    for key, y in (("ylo", y_lo), ("yd", y_d), ("yhi", y_hi)):
        _agree(plan, f"relation_tip_x_{key}_mm", pressed(y, t)["tip_x"])

    # The ear's bend over the drill shank: its radius the shank's, sprung
    # inside the printed band at every corner, and the overbend that lands
    # 90° at the design point.
    ear = f["ear_bend"]
    mandrel = shop["tools"][_plan_tool(plan, "mandrel")["ref"]]["diameter_mm"]
    ear_ri = mandrel / 2
    sprung = [
        _let_go(ear_ri, ear["angle_nominal"], y, e_mod, tt)[0]
        for y in (y_lo, y_hi)
        for tt in (t_min, t_max)
    ]
    if not (
        _within(ear_ri, ear["radius"])
        and all(_within(s, ear["radius"]) for s in sprung)
    ):
        raise ValueError(
            "the mandrel's ear bend springs outside the printed radius band"
        )
    _agree(plan, "ear_formed_radius_min_mm", min(sprung))
    _agree(plan, "ear_formed_radius_max_mm", max(sprung))
    ear_rf = _let_go(ear_ri, ear["angle_nominal"], y_d, e_mod, t)[0]
    _agree(
        plan,
        "ear_press_deg",
        ear["angle_nominal"] * (ear_rf + t / 2) / (ear_ri + t / 2),
    )

    # The die faces: the strip's two faces as pressed at the design point,
    # in the chord frame (s from the outer face's top along the chord from
    # the mid surface's top to its end, v to its left). Each half's top end
    # is square to the chord at s = 0 through the outer face's top (the ear's
    # lower edge's outer corner), its bottom end at the faces' last s.
    mid, _w = _walk(
        g,
        t,
        roll_die,
        (tab_die[0], tab_die[1] - math.degrees(g["trim"] / (tab_die[0] + t / 2))),
        p["die_runout_mm"],
    )
    a, b = mid[0]["start"], mid[-1]["end"]
    chord = math.dist(a, b)
    u = ((b[0] - a[0]) / chord, (b[1] - a[1]) / chord)
    n = (-u[1], u[0])

    def to_sv(q):
        return (q[0] * u[0] + q[1] * u[1], q[0] * n[0] + q[1] * n[1])

    faces = {
        "inner": [_mapped(e, to_sv) for e in _offset_chain(mid, t / 2)],
        "outer": [_mapped(e, to_sv) for e in _offset_chain(mid, -t / 2)],
    }
    s_end = max(fc[-1]["end"][0] for fc in faces.values())

    def to_s(line: dict[str, Any], key: str, s: float) -> None:
        u_l = _tangent(line, "start")
        q = line[key]
        k = (s - q[0]) / u_l[0]
        line[key] = [q[0] + u_l[0] * k, q[1] + u_l[1] * k]

    for fc in faces.values():
        to_s(fc[0], "start", 0.0)
        to_s(fc[-1], "end", s_end)
    _agree(plan, "die_length_mm", s_end)
    sag = {
        key: [
            min(q[1] for e in fc for q in _samples(e, 0.25)),
            max(q[1] for e in fc for q in _samples(e, 0.25)),
        ]
        for key, fc in faces.items()
    }

    em4 = shop["tools"][_plan_tool(plan, "em-quarter")["ref"]]
    dia2 = em4["diameter_mm"]
    r2 = dia2 / 2
    if not math.isclose(_cut(plan, "former", "cutter_dia_mm"), dia2, abs_tol=1e-6):
        raise ValueError("'former' cutter_dia_mm is not the 1/4 end mill's diameter")
    rpm2, feed2, op2 = _cut_speed(plan, "former")
    if float(op2["rpm"]) != rpm2:
        raise ValueError("'former': the operation's rpm is not the cut's")
    flutes2 = int(p["em_quarter_flutes"])
    _agree(plan, "former_feed_mm_min", p["former_chip_load_in"] * IN * flutes2 * rpm2)
    if not math.isclose(feed2, p["former_feed_mm_min"], abs_tol=PLAN_TOL_MM):
        raise ValueError("'former' feed_mm_min is not process.former_feed_mm_min")
    concave = min(
        math.dist(e["centre"], e["start"])
        for fc in faces.values()
        for e in fc
        if "centre" in e
    )
    if r2 >= concave:
        raise ValueError("the 1/4 end mill does not fit the die faces' tightest radius")
    blank_w, blank_t = p["die_blank_width_mm"], p["die_blank_thickness_max_mm"]
    blank_l = p["die_blank_length_in"] * IN
    _agree(plan, "die_blank_length_mm", blank_l)
    skim, place, e_end = (
        p["die_back_skim_mm"],
        p["die_place_error_mm"],
        p["die_end_excess_mm"],
    )
    if not (e_end + place <= dia2 and skim + place <= dia2):
        raise ValueError("the blank's end or back skims are wider than the cutter")
    tip2 = p["die_tip_z_mm"]
    if not -p["spoil_cut_max_mm"] <= tip2 <= 0.0:
        raise ValueError(
            "the die cutter's tip must stand at or below the plate top, within spoil_cut_max_mm"
        )
    top2 = stack_hi + blank_t
    if top2 - tip2 > em4["flute_length_mm"]:
        raise ValueError("the die cut is deeper than the 1/4 end mill's flutes")
    levels2 = levels_for(top2, tip2, dia2, "die")
    if _cut(plan, "former", "axial_doc_mm") + 1e-6 < top2 - levels2[0]:
        raise ValueError("'former' axial_doc_mm is under one level's depth")
    if p["em_quarter_projection_min_mm"] < max(jaw_top, top2) - tip2 + CLEAR_MM:
        raise ValueError(
            "em_quarter_projection_min_mm: the collet would not clear the blank and the jaw tops"
        )

    # One blank off the 1/2 x 6 bar, its 6 in width along X (the chord), both
    # halves in it with their faces facing across a channel: the halves as
    # pressed (the outer above, toward the fixed jaw), the inner moved
    # die_shift down -Y, so the channel between the finished faces is wider
    # than the cutter everywhere. s = 0 (the top ends) die_end_excess in from
    # the blank's left end, the right ends die_end_excess in from its right
    # end; both back edges skimmed off the sawn edges.
    x_r = blank_w - 2 * e_end
    if x_r <= s_end + CLEAR_MM:
        raise ValueError("the die faces do not fit along the blank")
    shift = p["die_shift_mm"]
    lo_i, hi_o = sag["inner"][0], sag["outer"][1]
    body = (blank_l - 2 * skim - (hi_o - lo_i) - shift) / 2
    if body < p["die_body_min_mm"]:
        raise ValueError(
            "the blank is too short for the halves' least body behind the faces"
        )
    _agree(plan, "die_least_width_mm", body)
    back_y = p["die_blank_back_y_mm"]
    front_y = back_y - blank_l
    y0 = back_y - skim - body - hi_o
    fo, fi = faces["outer"], faces["inner"]
    vb_o, vb_i = hi_o + body, lo_i - body
    v_end_o, v_end_i = fo[-1]["end"][1], fi[-1]["end"][1]
    nf = len(fo)
    els_o = [
        _line("back edge", (x_r, vb_o), (0.0, vb_o), DIE_TOL_MM),
        _line("top end", (0.0, vb_o), fo[0]["start"], DIE_TOL_MM),
        *[e | {"name": f"face, {e['name']}"} for e in fo],
        _line("run-out", fo[-1]["end"], (x_r, v_end_o), DIE_TOL_MM),
        _line("right end", (x_r, v_end_o), (x_r, vb_o), DIE_TOL_MM),
    ]
    els_i = [
        _line("back edge", (0.0, vb_i), (x_r, vb_i), DIE_TOL_MM),
        _line("right end", (x_r, vb_i), (x_r, v_end_i), DIE_TOL_MM),
        _line("run-out", (x_r, v_end_i), fi[-1]["end"], DIE_TOL_MM),
        *[_reversed(e) | {"name": f"face, {e['name']}"} for e in reversed(fi)],
        _line("top end", fi[0]["start"], (0.0, vb_i), DIE_TOL_MM),
    ]
    halves = {}
    for key, els, dy in (("outer", els_o, 0.0), ("inner", els_i, -shift)):

        def to_work(q, dy=dy):
            return (e_end + q[0], y0 + q[1] + dy)

        work = [_mapped(e, to_work) | {"name": f"{key} die {e['name']}"} for e in els]
        if _area(work) <= 0:
            raise ValueError(f"the {key} die half does not run anticlockwise")
        halves[key] = {"work": work, "area": _area(els)}
        _agree(plan, f"{key}_die_bond_area_mm2", halves[key]["area"])
    _agree(plan, "die_blank_area_mm2", blank_w * blank_l)
    # The channel: the finished faces and run-outs at least the cutter's
    # width and two margins apart, so a pass along either keeps its margin
    # off the other, and at most two widths and two margins, so a slot along
    # the inner face and one pass along the outer face clear it.
    side_o = halves["outer"]["work"][2 : 3 + nf]
    side_i = halves["inner"]["work"][2 : 3 + nf]
    gaps = [_distance(side_i, q) for e in side_o for q in _samples(e, 0.25)]
    _agree(plan, "die_gap_min_mm", min(gaps))
    _agree(plan, "die_gap_max_mm", max(gaps))
    if (
        min(gaps) < dia2 + 2 * CLEARING_MARGIN_MM
        or max(gaps) > 2 * dia2 + 2 * CLEARING_MARGIN_MM
    ):
        raise ValueError(
            "die_shift_mm: the channel is under the cutter and its margins, or over two passes wide"
        )

    reach_x = r2 + place + CLEARING_MARGIN_MM

    def run_out(segs: list[tuple], corner, above: bool) -> list[tuple]:
        """A channel pass run on past both ends of the blank: straight on
        past the right ends (the run-outs lie along X), and past the top ends
        along X, through the point the pass's margin square off its half's
        top corner where the pass ends right of that corner, so it keeps its
        margin and stays nearer its own half than the other."""
        q = segs[0][1] if above else segs[-1][2]
        via = (
            [[corner[0], corner[1] - d_pass if above else corner[1] + d_pass]]
            if q[0] > corner[0]
            else []
        )
        left = [*via, [-reach_x, (via[0] if via else q)[1]]]
        lines = [("line", a, b) for a, b in zip([q, *left], left)]
        if above:
            far_right = [blank_w + reach_x, segs[-1][2][1]]
            back = [("line", b, a) for _kind, a, b in reversed(lines)]
            return [*back, *segs, ("line", segs[-1][2], far_right)]
        far_right = [blank_w + reach_x, segs[0][1][1]]
        return [("line", far_right, segs[0][1]), *segs, *lines]

    # The channel per level: a slot along the inner face, then a pass along
    # the outer face that meets stock on its left only; each the margin off
    # its face, which the finishing loops then take.
    d_pass = r2 + CLEARING_MARGIN_MM
    tops = {
        "outer": halves["outer"]["work"][2]["start"],
        "inner": halves["inner"]["work"][2 + nf]["end"],
    }
    passes = [
        run_out(
            _loop(halves[key]["work"], d_pass, math.inf, "start", (2, 2 + nf)),
            tops[key],
            key == "outer",
        )
        for key in ("inner", "outer")
    ]
    plunge2 = feed2 * p["plunge_feed_fraction"]
    _agree(plan, "former_plunge_feed_mm_min", plunge2)
    clear2 = max(CLEAR_MM, jaw_top - top2 + CLEAR_MM)
    zc2, zs2 = _r(top2 + clear2), _r(top2 + SAFE_MM)
    lines2 = [f"G0 Z{zc2:.3f}"]
    reach_y: list[float] = []
    for z in levels2:
        for segs in passes:
            begin = segs[0][1]
            if -r2 <= begin[0] <= blank_w + r2:
                raise ValueError("a channel pass would plunge into the blank")
            reach_y += [q[1] for seg in segs for q in seg[1:3]]
            lines2 += [
                f"G0 X{_r(begin[0]):.3f} Y{_r(begin[1]):.3f}",
                f"G0 Z{zs2:.3f}",
                f"G1 Z{z:.3f} F{{plunge}}",
                *_moves(segs),
                f"G0 Z{zc2:.3f}",
            ]
    leads2 = []
    for key in ("outer", "inner"):
        work = halves[key]["work"]
        segs = _loop(work, r2, math.inf, "start")
        sx, sy = segs[0][1]
        back = _tangent(work[0], "start")
        # In from beyond the blank's end along the back edge, so the cutter
        # comes down in the air.
        run = e_end + reach_x
        ex, ey = sx - back[0] * run, sy - back[1] * run
        reach_y += [sy, ey]
        leads2.append(
            {
                "centre": [_r((sx + ex) / 2), _r((sy + ey) / 2)],
                "radius": run / 2 + 0.01,
                "levels": levels2,
            }
        )
        for z in levels2:
            lines2 += [
                f"G0 X{_r(ex):.3f} Y{_r(ey):.3f}",
                f"G0 Z{zs2:.3f}",
                f"G1 Z{z:.3f} F{{plunge}}",
                f"G1 X{_r(sx):.3f} Y{_r(sy):.3f} F{{feed}}",
                *_moves(segs),
                f"G0 Z{zc2:.3f}",
            ]
    boxes2 = plate_boxes(0.0, 0.0, p["spoil_cut_max_mm"])
    if front_y - r2 < -plate_w or blank_w > plate_l:
        raise ValueError("the blank runs off the plate")
    _agree(plan, "former_to_x_mm", blank_w)
    # The envelope: the cutter's far edge past each end of the blank on the
    # run-outs, and its reach across the jaws over every pass.
    _agree(plan, "die_lead_overhang_mm", r2 + reach_x)
    _agree(plan, "die_y_span_mm", max(reach_y) - min(reach_y) + 2 * r2)
    # The channel's middle at mid-length, cleared to the last level.
    q_out = _samples(side_o[nf // 2], 1.0)[0]
    q_in = min(
        (q for e in side_i for q in _samples(e, 0.25)),
        key=lambda q: math.dist(q, q_out),
    )
    channel_mid = [_r((q_out[0] + q_in[0]) / 2), _r((q_out[1] + q_in[1]) / 2)]

    # ===== HL03_holes: the 2X screw holes through the base =====
    holes_f = f["screw_holes"]
    if (
        holes_f["axis"] != [0.0, 0.0, 1.0]
        or holes_f["x_near_from"] != "ear_face"
        or holes_f["y_from"] != "low_edge"
    ):
        raise ValueError(
            "screw_holes: expected holes down model Z, placed from the ear's face and the low edge"
        )
    hy = holes_f["y_nominal"]
    holes = [(-holes_f["x_near_nominal"], hy), (-holes_f["x_far_nominal"], hy)]
    if not (
        math.isclose(holes_f["at"][0], holes[0][0], abs_tol=1e-6)
        and math.isclose(holes_f["at"][1], hy, abs_tol=1e-6)
    ):
        raise ValueError("screw_holes: the first hole is not at its printed stations")
    d30 = shop["tools"][_plan_tool(plan, "drill-30")["ref"]]["diameter_mm"]
    if not _within(d30, holes_f["dia"]):
        raise ValueError(f"#30 Ø{d30} is outside the holes' band {holes_f['dia']}")
    if not math.isclose(_cut(plan, "holes", "cutter_dia_mm"), d30, abs_tol=1e-3):
        raise ValueError("'holes' cutter_dia_mm is not the #30's")
    rpm3, feed3, op3 = _cut_speed(plan, "holes")
    if float(shop["settings"][op3["settings"]]["rpm"]) != rpm3:
        raise ValueError("'holes': its setting's rpm is not the cut's")
    base_len = f["base_end"]["length_nominal"]
    base_top = stack_hi + t_max
    tip3 = stack_lo - p["holes_drill_past_mm"] - _point(d30)
    _agree(plan, "holes_tip_z_mm", tip3)
    if -tip3 > p["spoil_drill_max_mm"]:
        raise ValueError(
            "the #30's point goes deeper into the plate than spoil_drill_max_mm"
        )
    ear_top = stack_hi + f["ear_top"]["height"][1]
    _agree(plan, "ear_height_max_mm", f["ear_top"]["height"][1])
    if not math.isclose(
        _cut(plan, "holes", "cutter_dia_mm"), p["drill_30_dia_mm"], abs_tol=1e-6
    ):
        raise ValueError("'holes' cutter_dia_mm is not process.drill_30_dia_mm")
    if p["drill_30_projection_min_mm"] < max(jaw_top, ear_top) - tip3 + CLEAR_MM:
        raise ValueError(
            "drill_30_projection_min_mm: the chuck would reach the ear or the jaw tops"
        )
    if p["drill_30_projection_min_mm"] >= p["drill_30_oal_mm"]:
        raise ValueError("drill_30_projection_min_mm: longer than the drill")
    ear_x, side_gap = p["holes_ear_x_on_plate_mm"], p["holes_base_from_jaw_mm"]
    jaw_y = width + side_gap
    _agree(plan, "holes_fixed_jaw_y_mm", jaw_y)
    _agree(plan, "holes_plate_from_mm", ear_x - plate_l)
    _agree(plan, "holes_plate_to_mm", ear_x)
    _agree(plan, "holes_bond_area_mm2", (base_len - ear_ri - t) * width)
    if ear_x < base_len + CLEAR_MM or jaw_y - plate_w > -dev_tip - CLEAR_MM:
        raise ValueError("the hook does not lie on the plate in HL03")
    # The ear and the flat arm stand in the model's X −t..0 from the ear's
    # top edge's corner (Y W) to the tip; the drill's body must miss them.
    wall = _box("ear and arm", (-t_max, 0.0), (-dev_tip, width), ear_top)
    for hx, _hy in holes:
        if -hx - d30 / 2 < t_max:
            raise ValueError("a screw hole's drill would touch the ear")
    boxes3 = plate_boxes(-ear_x, jaw_y, p["spoil_drill_max_mm"]) + [wall]
    clear3 = max(jaw_top, ear_top) + CLEAR_MM
    zr3 = _r(base_top + SAFE_MM)
    lines3 = []
    for hx, hy_ in holes:
        lines3 += [
            f"G0 Z{_r(clear3):.3f}",
            f"G0 X{_r(hx):.3f} Y{_r(hy_):.3f}",
            f"G0 Z{zr3:.3f}",
            f"G1 Z{_r(tip3):.3f} F{{feed}}",
            f"G0 Z{zr3:.3f}",
            f"G0 Z{_r(clear3):.3f}",
        ]
    hole_xy = [[_r(hx), _r(hy_)] for hx, hy_ in holes]

    jobs = [
        {
            "tool": "em-sixteenth",
            "dia": dia,
            "shape": "endmill",
            "flutes": flutes1,
            "rpm": rpm1,
            "feed": feed1,
            "plunge": plunge1,
            "frame": "sheet",
            "label": "sheet",
            "stock": ((0.0, blank_l), (-blank_w, 0.0), (stack, top1)),
            "ops": [["sheet", "the hook's flat pattern and the trial strip", lines1]],
        },
        {
            "tool": "em-quarter",
            "dia": dia2,
            "shape": "endmill",
            "flutes": flutes2,
            "rpm": rpm2,
            "feed": feed2,
            "plunge": plunge2,
            "frame": "former",
            "label": "former",
            "stock": ((0.0, blank_w), (front_y, back_y), (stack, top2)),
            "ops": [["former", "the former's two die halves", lines2]],
        },
        {
            "tool": "drill-30",
            "dia": d30,
            "shape": "drill",
            "tip_angle": DRILL_POINT_DEG,
            "rpm": rpm3,
            "feed": feed3,
            "plunge": feed3,
            "frame": "holes",
            "label": "holes",
            "stock": ((-base_len, 0.0), (0.0, width), (stack, base_top)),
            "ops": [["holes", "drill the 2X #30 screw holes", lines3]],
        },
    ]
    frames = {
        "sheet": {
            "origin": [-left - flat, -y_low - flat, -stack],
            "axes": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        },
        "former": {
            "origin": [-blank_w / 2, -front_y, -stack],
            "axes": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        },
        "holes": {
            "origin": [0.0, 0.0, -stack],
            "axes": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        },
    }

    n1, n2, n3 = (PROGRAMS[k][0] for k in range(3))
    expect: list[list[Any]] = [
        [
            n1,
            "tool_changes",
            {"z_top": top1, "tools": [numbers["em-sixteenth"]], "loads_first": True},
        ],
        [n1, "spindle", {"rpm": [[rpm1]]}],
        [n1, "pauses", {"z_top": top1, "count": 0}],
        [n1, "depth", {"z_min": levels1[-1]}],
        [n1, "rapids_clear", {"z_top": top1}],
        [n1, "air_feed", {"z_top": top1}],
        [
            n1,
            "outline",
            {
                "elements": hook_w + trial_w,
                "passes": [{"offset": r, "levels": levels1}],
                "z_top": top1,
                "cut": "conventional",
                "part": "left",
            },
        ],
        [n1, "keep_out", {"radius": r, "boxes": boxes1}],
        [
            n2,
            "tool_changes",
            {"z_top": top2, "tools": [numbers["em-quarter"]], "loads_first": True},
        ],
        [n2, "spindle", {"rpm": [[rpm2]]}],
        [n2, "pauses", {"z_top": top2, "count": 0}],
        [n2, "depth", {"z_min": levels2[-1]}],
        [n2, "rapids_clear", {"z_top": top2}],
        [n2, "air_feed", {"z_top": top2}],
        [
            n2,
            "outline",
            {
                "elements": halves["outer"]["work"] + halves["inner"]["work"],
                "passes": [{"offset": r2, "levels": levels2}],
                "z_top": top2,
                "clearing": [
                    {
                        "x": [-CLEARING_EXTENSION_MM, blank_w + CLEARING_EXTENSION_MM],
                        "levels": levels2,
                    }
                ],
                "leads": leads2,
                "cut": "conventional",
                "part": "left",
            },
        ],
        [n2, "keep_out", {"radius": r2, "boxes": boxes2}],
        # Every move meets at most the cutter's width, as pd_support_bar's
        # SB04 slots are held: no cut way here, because the channel's opening
        # slot meets both sides; the passes after it run the outline's way
        # (the outline check's direction rule holds them conventional).
        [
            n2,
            "engagement",
            {
                "stock": [[0.0, blank_w], [front_y, back_y], [stack, top2]],
                "radius": r2,
                "max_radial": dia2,
                "cell": ENGAGEMENT_CELL_MM,
            },
        ],
        [n2, "cleared", {"points": [channel_mid], "radius": r2, "z": levels2[-1]}],
    ]
    expect += [
        [
            n3,
            "tool_changes",
            {"z_top": base_top, "tools": [numbers["drill-30"]], "loads_first": True},
        ],
        [n3, "spindle", {"rpm": [[rpm3]]}],
        [n3, "pauses", {"z_top": base_top, "count": 0}],
        [n3, "depth", {"z_min": _r(tip3)}],
        [n3, "holes", {"centres": hole_xy, "z_bottom": _r(tip3)}],
        [n3, "rapids_clear", {"z_top": base_top, "open_holes": hole_xy}],
        [n3, "vertical_below_top", {"z_top": base_top}],
        [n3, "air_feed", {"z_top": base_top}],
        [n3, "keep_out", {"radius": d30 / 2, "boxes": boxes3}],
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
        "levels": {"sheet": levels1, "former": levels2},
        "holes": hole_xy,
    }


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    return [(program, check, kwargs) for program, check, kwargs in ctx["expect"]]


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job
    per program; returns {"ops": {operation key: operation}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(
            doc, f"Hook {key}", ctx["step"], frame["origin"], frame["axes"]
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
