"""FreeCAD CAM recipe for MHA-PD-03, the platen clip (two off).

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. No part dimension is
typed here: the rail, the slits, the finger, the corners, the holes, the
bows and the developed sheet come from the manifest; the blanks, the parts'
places on them, the tape stack, the cutter's tip height, the depth levels, the
vise, the plate and the strip's springback inputs from ``plan.toml``
``[parameters]``; the cutter's diameter, flute length, speed and feed from
the shop (``shop/``). Typed here, because neither record carries them: the
safe and clearance heights, the approach off the plate's end, the vise
jaws' depth (keep-out shapes only), the share of a printed band the posted
path may use, the die profile's stray allowance and the hole's clearing
circle.

Route (plan text in ``plan.toml``): two blanks sawn from the .032 strip
are bonded to the spoil plate on blue painter's tape on both faces with CA
glue between (owner 2026-11-23; ``fixtures.sheet-spoil-
plate``) gripped in the vise on parallels: blank A's back edge on the fixed
jaw, blank B's against blank A's front edge, both left ends flush with the
plate's left end. One file, PC01_sheet, with the 1/32 in carbide downcut end
mill: the four Ø.116 holes, each plunged near its centre and opened by two
circles; the two clips' flat outlines (rail, slits, finger) at their
developed length; then the bow former's four die laminations, each cut out
round its rectangle and split along its die profile by one pass (the kerf
between its male and female halves). Every outline and hole runs four
equal depth levels from the thickest strip on the thickest tape stack, the
last with its tip a few thousandths into the spoil plate, so each piece
comes free of its blank on its own island of tape.

Work frame (G54): X0 the plate's left end, Y0 the fixed jaw's face (the
plate's back edge), +Y toward the fixed jaw; Z0 the plate top. Each clip
lies with its length along X, its near end left and its spring edge toward
the fixed jaw. The cutter centre runs a cutter radius outside each outline,
anticlockwise round each part and clockwise round each hole (the part on
its left): conventional with a clockwise spindle. Every joint of the clip's
outline is tangent, so the cutter makes no corner of its own; the slits'
full R ends are the outline's only concave turns.

The bow former's dies are four laminations of the same strip, stacked: the
male halves carry the platen face's bow, the female halves the outer
face's, both drawn from the springback-corrected die radius the recipe
solves for (Ri/Rf = 4x^3 - 3x + 1, x = Ri Y / (E t)).
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "pd_platen_clip"
COMMENT = "MHA-PD-03 platen clip"
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (("PC01_sheet", ("sheet",)),)
# The file loads its own end mill (M6, the tool setter): the setup starts on
# whatever the mill last held.
LOAD_FIRST_TOOL = ("PC01_sheet",)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these.
CAM_TOOLS = ("em-thirty-second",)
IN = 25.4
# Each outline is entered from the air beyond the plate's left end: the
# cutter comes down this far (beyond its radius) left of X0, then feeds in
# through the blank's left margin; it never plunges into a part's sheet.
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
# The die laminations are tooling with no printed band: their profile path
# may stray this far. It also covers the female face, which stands the
# strip's thickness off the male face where the kerf is the cutter's width
# (.025 farther than the cutter's radius), with the posted path's sampling.
DIE_TOL_MM = 0.05
# The finish circle is posted as this many equal clockwise arcs: each 30°,
# so the checker's samples of the posted path (every .25 mm) fall on the
# wall's own (every 30° round a quarter) and the hole's .01 share of its
# band is held point for point.
HOLE_ARCS = 12
# A hole is opened by a clearing circle whose centre runs this share of the
# cutter's radius from the hole's centre (under one radius, so it clears the
# centre; far enough out that the finish circle's cut overlaps it), then by
# the finish circle.
HOLE_CLEAR_FRACTION = 0.9
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# Bow features' end stations agree with the slits' and holes' to this (mm).
STATION_TOL_MM = 1e-3


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


def _plane(features: dict[str, Any], name: str, axis: str) -> float:
    plane = features[name]["plane"]
    if plane["frame"] != "model" or plane["axis"] != axis:
        raise ValueError(f"{name}: expected a model {axis.upper()} plane")
    return float(plane["value"])


def _band(feature: dict[str, Any], key: str) -> float:
    low, high = feature[key]
    return high - low


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


def _shifted(element: dict[str, Any], dx: float, dy: float) -> dict[str, Any]:
    moved = dict(element)
    for key in ("start", "end", "centre"):
        if key in element:
            moved[key] = [element[key][0] + dx, element[key][1] + dy]
    return moved


def _offset_one(element: dict[str, Any], d: float) -> dict[str, Any]:
    """``element`` moved ``d`` to the right of its way (negative: left)."""
    if "centre" not in element:
        u = _tangent(element, "start")
        n = (u[1] * d, -u[0] * d)
        return _shifted(element, *n)
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


def _offset_loop(
    elements: list[dict[str, Any]], r: float, inside_max: float
) -> list[tuple]:
    """The cutter-centre path ``r`` to the right of a closed outline (outside
    a part run anticlockwise, inside a hole run clockwise), starting and
    ending at the middle of the first element, which must be a line. A
    tangent joint joins directly; a convex corner is rounded by a G3 arc
    about it. A concave corner the cutter would round itself is refused: the
    title block's INSIDE CORNERS max (``inside_max``) bounds such a corner's
    radius, the cutter's, so the cutter's radius is checked against it too.
    Returns segments ("line", start, end) or ("arc", start, end, centre,
    clockwise)."""
    if r > inside_max + 1e-9:
        raise ValueError(
            f"the cutter's R{r:.4f} is over the title block's inside-corner"
            f" R{inside_max:.4f} max"
        )
    if "centre" in elements[0]:
        raise ValueError("the loop must start on a line")
    moved = [_offset_one(e, r) for e in elements]
    pieces: list[tuple] = []
    count = len(elements)
    for k in range(count):
        e = moved[k]
        if "centre" in e:
            pieces.append(("arc", e["start"], e["end"], e["centre"], not _ccw(e)))
        else:
            pieces.append(("line", e["start"], e["end"]))
        nxt = elements[(k + 1) % count]
        u_in, u_out = _tangent(elements[k], "end"), _tangent(nxt, "start")
        turn = _cross(u_in, u_out)
        dot = u_in[0] * u_out[0] + u_in[1] * u_out[1]
        if abs(turn) < 1e-9 and dot > 0:
            if math.dist(e["end"], moved[(k + 1) % count]["start"]) > 1e-6:
                raise ValueError(f"{elements[k]['name']}: offset ends do not meet")
            continue
        if turn < 0:
            raise ValueError(
                f"inside corner after {elements[k]['name']}: the outline has a"
                " concave corner the cutter would round"
            )
        corner = elements[k]["end"]
        pieces.append(("arc", e["end"], moved[(k + 1) % count]["start"], corner, False))
    first = pieces[0]
    mid = [(first[1][0] + first[2][0]) / 2, (first[1][1] + first[2][1]) / 2]
    return [("line", mid, first[2]), *pieces[1:], ("line", first[1], mid)]


def _segments(elements: list[dict[str, Any]]) -> list[tuple]:
    return [
        ("arc", e["start"], e["end"], e["centre"], not _ccw(e))
        if "centre" in e
        else ("line", e["start"], e["end"])
        for e in elements
    ]


def _moves(segs: list[tuple], shift: tuple[float, float]) -> list[str]:
    """The segments as feed moves in the work frame (each from the last end)."""
    lines = []
    for seg in segs:
        x, y = _r(seg[2][0] + shift[0]), _r(seg[2][1] + shift[1])
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


def _area(elements: list[dict[str, Any]]) -> float:
    """Signed area (shoelace over the edges, each arc a polygon of chords)."""
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


def _clip(f: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The clip's flat (developed) outline in model X/Y, anticlockwise round
    the part from the near rail end, every 180° round split in two, each
    element with the share of its locating band the cutter may stray."""
    near = _plane(f, "near_end", "x")
    far = _plane(f, "far_end", "x")
    outer = _plane(f, "outer_edge", "y")
    rail = _plane(f, "rail_edge", "y")
    spring = _plane(f, "spring_edge", "y")
    slits, bows, sheet = f["slits"], f["bows"], f["sheet"]
    if not (near == outer == 0.0 and f["far_end"]["length_from"] == "near_end"):
        raise ValueError("expected the near end and the outer edge at the model's zero")
    if not math.isclose(far, f["far_end"]["length_nominal"], abs_tol=1e-6):
        raise ValueError("far_end: its plane is not its length from the near end")
    width = slits["width_nominal"]
    if not math.isclose(slits["end_radius"], width / 2, abs_tol=1e-6):
        raise ValueError("slits: the end radius is not half the slit (no full R)")
    if slits["width_from"] != "rail_edge" or slits["bridge_near_from"] != "near_end":
        raise ValueError(
            "slits: expected the width from the rail edge, stations from the near end"
        )
    finger_y = rail + width
    tip_r = f["spring_tips"]["width"] / 2
    if not math.isclose(spring - finger_y, 2 * tip_r, abs_tol=1e-6):
        raise ValueError("spring_tips: the finger's width is not its full R ends'")
    bridge_near = slits["bridge_near_nominal"]
    bridge_far = slits["bridge_far_nominal"]
    if not math.isclose(far - bridge_far, bridge_near - near, abs_tol=STATION_TOL_MM):
        raise ValueError("slits: the bridge does not stand in the middle")
    # The finger's flat length from the bridge (the slit's round centre, where
    # each bow rejoins the flat) to its tip, along the bows: the blank's tips
    # stand past the rail ends by what forming draws back.
    if not math.isclose(bows["rejoin_near"], bridge_near, abs_tol=STATION_TOL_MM):
        raise ValueError("bows: they do not rejoin the flat at the slit's round")
    finger = bows["developed_finger"]
    tip_near = bridge_near - finger
    tip_far = bridge_far + finger
    developed = tip_far - tip_near
    if not math.isclose(developed, sheet["developed_length"], abs_tol=STATION_TOL_MM):
        raise ValueError(
            "sheet: the developed length is not the two fingers and the bridge"
        )
    corner = f["rail_end_corners"]["radius_nominal"]
    slit_corner = f["slit_corners"]["radius_nominal"]
    holes = f["screw_holes"]
    if holes["x_near_from"] != "near_end" or holes["y_from"] != "outer_edge":
        raise ValueError(
            "screw_holes: expected stations from the near end and outer edge"
        )
    if not math.isclose(
        bows["leave_near"], holes["x_near_nominal"], abs_tol=STATION_TOL_MM
    ):
        raise ValueError("bows: they do not leave the flat at the hole station")

    tol_len = BAND_FRACTION * _band(f["far_end"], "length")
    tol_rail = BAND_FRACTION * _band(f["rail_edge"], "width")
    tol_spring = BAND_FRACTION * _band(f["spring_edge"], "width")
    tol_slit = BAND_FRACTION * min(
        _band(slits, "width"), _band(slits, "bridge_near"), _band(slits, "bridge_far")
    )
    tol_corner = BAND_FRACTION * _band(f["rail_end_corners"], "radius")
    tol_slit_corner = BAND_FRACTION * _band(f["slit_corners"], "radius")
    tol_tip = tol_len
    ym = finger_y + tip_r
    sm = rail + width / 2
    cn, cf = tip_near + tip_r, tip_far - tip_r
    el = [
        _line(
            "near rail end", (near, rail - slit_corner), (near, outer + corner), tol_len
        ),
        _arc(
            "near outer corner",
            (near, corner),
            (corner, outer),
            (corner, corner),
            tol_corner,
        ),
        _line("outer edge", (corner, outer), (far - corner, outer), tol_rail),
        _arc(
            "far outer corner",
            (far - corner, outer),
            (far, corner),
            (far - corner, corner),
            tol_corner,
        ),
        _line("far rail end", (far, corner), (far, rail - slit_corner), tol_len),
        _arc(
            "far slit corner",
            (far, rail - slit_corner),
            (far - slit_corner, rail),
            (far - slit_corner, rail - slit_corner),
            tol_slit_corner,
        ),
        _line(
            "far slit, rail side",
            (far - slit_corner, rail),
            (bridge_far, rail),
            tol_slit,
        ),
        _arc(
            "far slit end, rail half",
            (bridge_far, rail),
            (bridge_far - width / 2, sm),
            (bridge_far, sm),
            tol_slit,
        ),
        _arc(
            "far slit end, finger half",
            (bridge_far - width / 2, sm),
            (bridge_far, finger_y),
            (bridge_far, sm),
            tol_slit,
        ),
        _line(
            "far slit, finger side", (bridge_far, finger_y), (cf, finger_y), tol_slit
        ),
        _arc("far tip, inner half", (cf, finger_y), (tip_far, ym), (cf, ym), tol_tip),
        _arc("far tip, outer half", (tip_far, ym), (cf, spring), (cf, ym), tol_tip),
        _line("spring edge", (cf, spring), (cn, spring), tol_spring),
        _arc("near tip, outer half", (cn, spring), (tip_near, ym), (cn, ym), tol_tip),
        _arc("near tip, inner half", (tip_near, ym), (cn, finger_y), (cn, ym), tol_tip),
        _line(
            "near slit, finger side", (cn, finger_y), (bridge_near, finger_y), tol_slit
        ),
        _arc(
            "near slit end, finger half",
            (bridge_near, finger_y),
            (bridge_near + width / 2, sm),
            (bridge_near, sm),
            tol_slit,
        ),
        _arc(
            "near slit end, rail half",
            (bridge_near + width / 2, sm),
            (bridge_near, rail),
            (bridge_near, sm),
            tol_slit,
        ),
        _line(
            "near slit, rail side", (bridge_near, rail), (slit_corner, rail), tol_slit
        ),
        _arc(
            "near slit corner",
            (slit_corner, rail),
            (near, rail - slit_corner),
            (slit_corner, rail - slit_corner),
            tol_slit_corner,
        ),
    ]
    dims = {
        "near": near,
        "far": far,
        "spring": spring,
        "rail": rail,
        "slit_width": width,
        "slit_width_min": slits["width"][0],
        "slit_end_radius": slits["end_radius"],
        "tip_near": tip_near,
        "tip_far": tip_far,
        "developed": developed,
        "finger_width": 2 * tip_r,
        "bow_from": bows["leave_near"],
        "bow_to": bridge_near,
        "holes": [
            (holes["x_near_nominal"], holes["y_nominal"]),
            (holes["x_far_nominal"], holes["y_nominal"]),
        ],
        "hole_dia": holes["dia"],
        "hole_tol": BAND_FRACTION
        * min(_band(holes, "dia"), _band(holes, "x_near"), _band(holes, "y")),
    }
    if not math.isclose(
        far - holes["x_far_nominal"], holes["x_near_nominal"], abs_tol=STATION_TOL_MM
    ):
        raise ValueError("screw_holes: the far hole is not the near one's mirror")
    return el, dims


def _hole(
    name: str, c: tuple[float, float], radius: float, tol: float
) -> list[dict[str, Any]]:
    """A hole's wall run clockwise (the part on the left), in four quarters
    from its +X point."""
    x, y = c
    pts = [(x + radius, y), (x, y - radius), (x - radius, y), (x, y + radius)]
    return [
        _arc(f"{name}, quarter {k + 1}", pts[k], pts[(k + 1) % 4], c, tol)
        for k in range(4)
    ]


def _springback(ri: float, yield_mpa: float, modulus: float, t: float) -> float:
    """Ri/Rf of a strip bent to inside radius ``ri`` and let go:
    4x^3 - 3x + 1, x = Ri Y / (E t); 0 (no set) from x = 1/2, where the
    bend stays elastic."""
    x = min(ri * yield_mpa / (modulus * t), 0.5)
    return 4 * x**3 - 3 * x + 1


def _formed_rise(
    rd: float, run: float, yield_mpa: float, modulus: float, t: float
) -> float:
    """The bow's rise once let go from a die of mid-surface radius ``rd``
    over ``run``: three tangent arcs (lift, crown, return), each keeping its
    length as its curvature springs back."""
    a = math.asin(run / (4 * rd))
    ri = rd - t / 2
    k = _springback(ri, yield_mpa, modulus, t)
    if k <= 0:
        return 0.0
    rf = ri / k + t / 2
    return 2 * rf * (1 - math.cos(a * rd / rf))


def _die_radius(
    run: float, rise: float, yield_mpa: float, modulus: float, t: float
) -> float:
    """The die's mid-surface radius whose bow springs back to ``rise``,
    between the tightest bow the run allows and the elastic limit."""
    lo = run / 4 * (1 + 1e-9)
    hi = modulus * t / (2 * yield_mpa) + t / 2
    for _ in range(200):
        mid = (lo + hi) / 2
        if _formed_rise(mid, run, yield_mpa, modulus, t) > rise:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _bow_mid(x0: float, run: float, rd: float, y: float) -> list[dict[str, Any]]:
    """One bow's mid surface left to right from (x0, y): lift (anticlockwise),
    crown (clockwise), return (anticlockwise), each radius ``rd``."""
    a = math.asin(run / (4 * rd))
    lift_c = (x0, y + rd)
    p1 = (x0 + rd * math.sin(a), y + rd * (1 - math.cos(a)))
    crown_c = (x0 + 2 * rd * math.sin(a), y + rd - 2 * rd * math.cos(a))
    crest = (crown_c[0], crown_c[1] + rd)
    p2 = (x0 + 3 * rd * math.sin(a), p1[1])
    return_c = (x0 + run, y + rd)
    end = (x0 + run, y)
    return [
        _arc("lift", (x0, y), p1, lift_c, DIE_TOL_MM),
        _arc("crown, rising", p1, crest, crown_c, DIE_TOL_MM),
        _arc("crown, falling", crest, p2, crown_c, DIE_TOL_MM),
        _arc("return", p2, end, return_c, DIE_TOL_MM),
    ]


def _die_profile(
    length: float, stations: tuple[float, float, float, float], rd: float, y: float
) -> list[dict[str, Any]]:
    """The die's mid surface along the finger, left to right at height ``y``:
    the tip flat, the near bow, the bridge flat, the far bow, the tip flat."""
    s1, s2, s3, s4 = stations
    near = _bow_mid(s1, s2 - s1, rd, y)
    far = _bow_mid(s3, s4 - s3, rd, y)
    pieces = [
        _line("near tip flat", (0.0, y), (s1, y), DIE_TOL_MM),
        *[e | {"name": f"near bow {e['name']}"} for e in near],
        _line("bridge flat", (s2, y), (s3, y), DIE_TOL_MM),
        *[e | {"name": f"far bow {e['name']}"} for e in far],
        _line("far tip flat", (s4, y), (length, y), DIE_TOL_MM),
    ]
    return pieces


def _lamination(
    length: float, height: float, flat: float, t: float, mid: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """A die lamination's male (below the kerf) and female (above) halves in
    its own X/Y, each anticlockwise round itself: the male face is the
    platen face's bow (the mid surface t/2 below), the female the outer
    face's (t/2 above)."""
    male_face = _offset_chain(mid, t / 2)
    female_face = _offset_chain(mid, -t / 2)
    top = flat + t
    male = [
        _line("male back edge", (0.0, 0.0), (length, 0.0), DIE_TOL_MM),
        _line("male right end", (length, 0.0), (length, flat), DIE_TOL_MM),
        *[_reversed(e) | {"name": f"male {e['name']}"} for e in reversed(male_face)],
        _line("male left end", (0.0, flat), (0.0, 0.0), DIE_TOL_MM),
    ]
    female = [
        *[e | {"name": f"female {e['name']}"} for e in female_face],
        _line("female right end", (length, top), (length, height), DIE_TOL_MM),
        _line("female back edge", (length, height), (0.0, height), DIE_TOL_MM),
        _line("female left end", (0.0, height), (0.0, top), DIE_TOL_MM),
    ]
    return male, female, male[2:-1]


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    f = features["features"]
    p = plan["parameters"]
    clip, d = _clip(f)
    sheet_t = f["sheet"]["thickness"]

    tool = _plan_tool(plan, "em-thirty-second")
    em = shop["tools"][tool["ref"]]
    dia = em["diameter_mm"]
    r = dia / 2
    rpm, feed, flutes = _setting(plan, shop, "sheet")
    if not math.isclose(_cut(plan, "sheet", "cutter_dia_mm"), dia, abs_tol=1e-6):
        raise ValueError("'sheet' cutter_dia_mm is not the end mill's diameter")
    # The downcut's helix pushes the taped clip's narrow finger onto the tape.
    if tool.get("axial_direction") != "down":
        raise ValueError("em-thirty-second: the plan's end mill must be a downcut")

    # The slit: the cutter runs down one side and back up the other, so it
    # fits inside the slit's nominal width, its radius inside the full R end.
    if dia >= d["slit_width"]:
        raise ValueError(
            f"the cutter's Ø{dia:.3f} does not fit the slit's {d['slit_width']:.3f}"
        )
    if r >= d["slit_end_radius"]:
        raise ValueError("the cutter's radius does not fit the slit's full R end")
    _agree(plan, "slit_cutter_clearance_mm", d["slit_width"] - dia)

    # Depth: equal levels down to the tip, from the thickest strip on the
    # thickest tape stack (blue tape, CA glue, blue tape), the tip into the
    # spoil plate. Z0 is the plate top, so the tip's depth into the plate is
    # the same on every stack; the tip's margin under the strip's underside
    # is least on the thinnest stack.
    stack = p["tape_stack_mm"]
    stack_lo, stack_hi = p["tape_stack_min_mm"], p["tape_stack_max_mm"]
    if stack_lo > stack:
        raise ValueError("tape_stack_min_mm is over the tape stack")
    if stack_hi < stack:
        raise ValueError("tape_stack_max_mm is under the tape stack")
    tip = p["sheet_tip_z_mm"]
    _agree(plan, "sheet_tip_into_plate_mm", -tip)
    if not -p["spoil_cut_max_mm"] <= tip <= 0.0:
        raise ValueError(
            "the cutter's tip must stand at or below the plate top, no deeper"
            " than spoil_cut_max_mm"
        )
    if stack_lo - tip < p["through_margin_min_mm"]:
        raise ValueError(
            "the tip is not through_margin_min_mm below the thinnest strip's"
            " underside on the thinnest tape stack"
        )
    t_min, t_max = p["strip_thickness_min_mm"], p["strip_thickness_max_mm"]
    if not t_min <= sheet_t <= t_max:
        raise ValueError("the drawing's sheet is outside the strip's thickness band")
    top = stack_hi + t_max
    depth = top - tip
    _agree(plan, "sheet_depth_mm", depth)
    if depth > em["flute_length_mm"]:
        raise ValueError(
            f"the cut ({depth:.3f}) is deeper than the end mill's flutes"
            f" ({em['flute_length_mm']:.3f})"
        )
    count = math.ceil(depth / (p["level_depth_max_fraction"] * dia) - 1e-9)
    if count != p["level_count"]:
        raise ValueError(
            f"process.level_count {p['level_count']}, the recipe computes {count}"
        )
    step = depth / count
    _agree(plan, "level_depth_mm", step)
    if _cut(plan, "sheet", "axial_doc_mm") + 1e-6 < step:
        raise ValueError("'sheet' axial_doc_mm is under one level's depth")
    levels = [_r(top - step * (k + 1)) for k in range(count)]
    levels[-1] = _r(tip)

    # The bow former's die: its mid-surface radius springs back to the
    # drawing's rise at the middle yield, nominal strip; every corner of the
    # strip's yield and thickness bands lands inside the drawing's rise band.
    bows = f["bows"]
    run = d["bow_to"] - d["bow_from"]
    modulus = p["strip_modulus_mpa"]
    y_lo, y_hi = p["strip_yield_min_mpa"], p["strip_yield_max_mpa"]
    rd = _die_radius(run, bows["rise_nominal"], (y_lo + y_hi) / 2, modulus, sheet_t)
    _agree(plan, "die_bow_radius_mm", rd)
    die_rise = 2 * rd * (1 - math.cos(math.asin(run / (4 * rd))))
    _agree(plan, "die_bow_rise_mm", die_rise)
    rises = [
        _formed_rise(rd, run, y, modulus, t)
        for y in (y_lo, y_hi)
        for t in (t_min, t_max)
    ]
    _agree(plan, "formed_rise_min_mm", min(rises))
    _agree(plan, "formed_rise_max_mm", max(rises))
    lo, hi = bows["rise"]
    if not (lo <= min(rises) and max(rises) <= hi):
        raise ValueError(
            f"the former's bows spring back to {min(rises):.3f}-{max(rises):.3f},"
            f" outside the drawing's rise {lo:.3f}-{hi:.3f}"
        )
    # The laminations: as long as the rail (their ends square the clip's rail
    # ends), the male's back edge to its flats, the female above the kerf.
    lam_l = d["far"] - d["near"]
    lam_h = p["lamination_height_mm"]
    lam_flat = p["lamination_flat_mm"]
    stations = (d["bow_from"], d["bow_to"], lam_l - d["bow_to"], lam_l - d["bow_from"])
    mid = _die_profile(lam_l, stations, rd, lam_flat + sheet_t / 2)
    male, female, male_face = _lamination(lam_l, lam_h, lam_flat, sheet_t, mid)
    female_least = lam_h - (lam_flat + sheet_t + die_rise)
    if min(lam_flat, female_least) < p["lamination_body_min_mm"]:
        raise ValueError("a die half is thinner than lamination_body_min_mm")
    stack = p["lamination_count"] * t_min
    finger_w = d["finger_width"]
    _agree(plan, "die_stack_mm", p["lamination_count"] * sheet_t)
    gap_to_rail = d["slit_width_min"]
    if not (
        finger_w - stack < finger_w / 2
        and p["lamination_count"] * t_max < finger_w + gap_to_rail
    ):
        raise ValueError(
            "the die stack must cover most of the finger's width and stay clear of the rail"
        )

    # Holes: the finish circle at the drilled band's middle, entered from the
    # clearing circle on a clockwise arc round a circle that holds the hole's
    # centre (so it turns the hole's way all along).
    hole_r = sum(d["hole_dia"]) / 4
    _agree(plan, "hole_dia_target_mm", 2 * hole_r)
    ring = hole_r - r
    clear_r = HOLE_CLEAR_FRACTION * r
    if ring - clear_r > 2 * r - 1e-6:
        raise ValueError("the hole's two circles leave a ring uncut")
    lead_j = (clear_r**2 - ring**2) / (2 * ring)

    # Layout. Blank A's back edge on the fixed jaw (Y0), blank B's against
    # blank A's front edge, both left ends at X0. Parts run down from the
    # back edge: clip 1, clip 2 and lamination 1 on A; laminations 2-4 on B.
    blank_l, blank_w = p["blank_length_in"] * IN, p["blank_width_in"] * IN
    _agree(plan, "blank_length_mm", blank_l)
    _agree(plan, "blank_width_mm", blank_w)
    left = p["part_left_x_mm"]
    margin, gap = p["part_margin_y_mm"], p["part_gap_mm"]
    if left + d["tip_near"] - r - APPROACH_MM < r:
        raise ValueError(
            "part_left_x_mm: the finger's tip path runs off the blank's end"
        )
    right = blank_l - (left + d["tip_far"])
    _agree(plan, "blank_right_margin_mm", right)
    if right < dia + p["saw_error_mm"]:
        raise ValueError("blank_right_margin_mm: the path may run off the sawn end")
    clip_h = d["spring"]
    shifts_a = [(left, -margin - clip_h), (left, -margin - 2 * clip_h - gap)]
    lam_tops = [-margin - 2 * clip_h - 2 * gap]
    lam_tops += [-blank_w - margin - k * (lam_h + gap) for k in range(3)]
    if (
        lam_tops[0] - lam_h < -blank_w + margin
        or lam_tops[-1] - lam_h < -2 * blank_w + margin
    ):
        raise ValueError("the parts do not fit the blanks' widths")
    _agree(plan, "clip_spring_edge_y_mm", -margin)
    _agree(plan, "blank_a_front_margin_mm", lam_tops[0] - lam_h + blank_w)
    _agree(plan, "blank_b_front_margin_mm", lam_tops[-1] - lam_h + 2 * blank_w)
    if p["lamination_count"] != len(lam_tops):
        raise ValueError("lamination_count: the blanks hold four laminations")

    # The plate and the vise: the plate across the jaws, its back edge on
    # the fixed jaw (Y0), its top (Z0) below the jaw tops by the jaw height
    # less the parallels and the plate.
    plate_l, plate_w = p["plate_length_mm"], p["plate_width_mm"]
    if blank_l > plate_l or 2 * blank_w > plate_w:
        raise ValueError("the blanks run off the plate")
    jaw_top = (
        p["vise_jaw_height_mm"] - p["parallel_height_mm"] - p["plate_thickness_mm"]
    )
    _agree(plan, "jaw_top_over_plate_mm", jaw_top)
    if p["em_projection_min_mm"] < jaw_top - tip + CLEAR_MM:
        raise ValueError(
            "em_projection_min_mm: the collet would not clear the jaw tops"
            " with the tip at the cut"
        )
    _agree(plan, "collet_over_jaw_mm", p["em_projection_min_mm"] + tip - jaw_top)
    clear = max(CLEAR_MM, jaw_top - top + CLEAR_MM)
    boxes = [
        _box("fixed jaw", (0.0, plate_l), (0.0, JAW_DEPTH_MM), jaw_top),
        _box(
            "moving jaw", (0.0, plate_l), (-plate_w - JAW_DEPTH_MM, -plate_w), jaw_top
        ),
        _box("spoil plate", (0.0, plate_l), (-plate_w, 0.0), -p["spoil_cut_max_mm"]),
    ]

    # Bond: each piece the cut leaves on the tape.
    clip_area = _area(clip) - 2 * math.pi * hole_r**2
    male_area, female_area = _area(male), _area(female)
    waste_a = blank_l * blank_w - 2 * clip_area - male_area - female_area
    waste_b = blank_l * blank_w - 3 * (male_area + female_area)
    _agree(plan, "clip_bond_area_mm2", clip_area)
    _agree(plan, "male_bond_area_mm2", male_area)
    _agree(plan, "female_bond_area_mm2", female_area)
    _agree(plan, "waste_a_bond_area_mm2", waste_a)
    _agree(plan, "waste_b_bond_area_mm2", waste_b)
    _agree(plan, "clip_finger_width_mm", finger_w)
    _agree(plan, "female_least_width_mm", female_least)

    # The paths, in the work frame.
    entry_x = -r - APPROACH_MM
    _agree(plan, "entry_overhang_mm", r - entry_x)
    _agree(plan, "sheet_from_x_mm", left + d["tip_near"] - r)
    _agree(plan, "sheet_to_x_mm", left + d["tip_far"] + r)
    _agree(plan, "blank_area_mm2", blank_l * blank_w)
    _agree(plan, "plate_to_x_mm", plate_l)
    if p["plate_from_x_mm"] != 0.0:
        raise ValueError(
            "plate_from_x_mm: the blanks' left ends are flush with the plate's"
        )
    work_elements: list[dict[str, Any]] = []
    lines: list[str] = [f"G0 Z{_r(top + clear):.3f}"]
    hole_centres = []
    leads = []

    def descend(x: float, y: float, z: float, word: str) -> None:
        lines.extend(
            [
                f"G0 X{_r(x):.3f} Y{_r(y):.3f}",
                f"G0 Z{_r(top + SAFE_MM):.3f}",
                f"G1 Z{z:.3f} F{{{word}}}",
            ]
        )

    for k, (sx, sy) in enumerate(shifts_a, 1):
        for h, (hx, hy) in enumerate(d["holes"], 1):
            c = (hx + sx, hy + sy)
            hole_centres.append(c)
            work_elements += _hole(f"clip {k} hole {h}", c, hole_r, d["hole_tol"])
            leads.append(
                {"centre": [_r(c[0]), _r(c[1])], "radius": ring, "levels": levels}
            )
            cx, cy = _r(c[0]), _r(c[1])
            for z in levels:
                # Plunged on the clearing circle, round it, out on the lead
                # to the finish circle's bottom, round that, up.
                descend(cx + clear_r, cy, z, "plunge")
                lines += [
                    f"G2 X{_r(cx - clear_r):.3f} Y{cy:.3f} I{_r(-clear_r):.3f} J0.000 F{{feed}}",
                    f"G2 X{_r(cx + clear_r):.3f} Y{cy:.3f} I{_r(clear_r):.3f} J0.000 F{{feed}}",
                    f"G2 X{cx:.3f} Y{_r(cy - ring):.3f} I{_r(-clear_r):.3f} J{_r(lead_j):.3f} F{{feed}}",
                ]
                start = (cx, _r(cy - ring))
                for n in range(1, HOLE_ARCS + 1):
                    a = -math.pi / 2 - 2 * math.pi * n / HOLE_ARCS
                    end = (_r(cx + ring * math.cos(a)), _r(cy + ring * math.sin(a)))
                    lines.append(
                        f"G2 X{end[0]:.3f} Y{end[1]:.3f} I{_r(cx - start[0]):.3f}"
                        f" J{_r(cy - start[1]):.3f} F{{feed}}"
                    )
                    start = end
                lines.append(f"G0 Z{_r(top + clear):.3f}")

    def loop(segs: list[tuple], shift: tuple[float, float]) -> None:
        """Down off the plate's end, in through the margin to the loop's
        start, round at each level, back out the way it came."""
        sx, sy = _r(segs[0][1][0] + shift[0]), _r(segs[0][1][1] + shift[1])
        # The way in and out through the blank's left margin.
        leads.append(
            {
                "centre": [_r((entry_x + sx) / 2), sy],
                "radius": (sx - entry_x) / 2,
                "levels": levels,
            }
        )
        descend(entry_x, sy, levels[0], "feed")
        for n, z in enumerate(levels):
            if n:
                lines.append(f"G1 Z{z:.3f} F{{feed}}")
            lines.append(f"G1 X{sx:.3f} Y{sy:.3f} F{{feed}}")
            lines.extend(_moves(segs, shift))
            lines.append(f"G1 X{_r(entry_x):.3f} Y{sy:.3f} F{{feed}}")
        lines.append(f"G0 Z{_r(top + clear):.3f}")

    inside_max = p["inside_corner_max_mm"]
    clip_segs = _offset_loop(clip, r, inside_max)
    for k, shift in enumerate(shifts_a, 1):
        work_elements += [
            _shifted(e, *shift) | {"name": f"clip {k} {e['name']}"} for e in clip
        ]
        loop(clip_segs, shift)

    rect = [
        _line("left end", (0.0, lam_h), (0.0, 0.0), DIE_TOL_MM),
        _line("back edge", (0.0, 0.0), (lam_l, 0.0), DIE_TOL_MM),
        _line("right end", (lam_l, 0.0), (lam_l, lam_h), DIE_TOL_MM),
        _line("top edge", (lam_l, lam_h), (0.0, lam_h), DIE_TOL_MM),
    ]
    rect_segs = _offset_loop(rect, r, inside_max)
    kerf = _offset_chain(male_face, r)
    kerf_segs = [
        ("line", [lam_l + r, lam_flat + r], kerf[0]["start"]),
        *_segments(kerf),
        ("line", kerf[-1]["end"], [-r, lam_flat + r]),
    ]
    for k, top_y in enumerate(lam_tops, 1):
        shift = (left, top_y - lam_h)
        work_elements += [
            _shifted(e, *shift) | {"name": f"lamination {k} {e['name']}"}
            for e in (*male, *female)
        ]
        loop(rect_segs, shift)
        mx, my = _r(kerf_segs[0][1][0] + shift[0]), _r(kerf_segs[0][1][1] + shift[1])
        for n, z in enumerate(levels):
            descend(mx, my, z, "feed")
            lines.extend(_moves(kerf_segs, shift))
            lines.append(f"G0 Z{_r(top + clear):.3f}")
        # The kerf's mouths: the cutter crosses the gap between the halves'
        # ends there, in the rectangle's own cut.
        for x in (left + lam_l + r, left - r):
            leads.append({"centre": [_r(x), my], "radius": 2 * r, "levels": levels})

    numbers = {
        t["id"]: n
        for n, t in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")
    names = {t["id"]: t["name"] for t in plan["tools"]}
    plunge = feed * p["plunge_feed_fraction"]
    _agree(plan, "plunge_feed_mm_min", plunge)
    jobs = [
        {
            "tool": "em-thirty-second",
            "dia": dia,
            "shape": "endmill",
            "flutes": flutes,
            "rpm": rpm,
            "feed": feed,
            "plunge": plunge,
            "frame": "plate",
            "label": "sheet",
            "stock": ((0.0, blank_l), (-2 * blank_w, 0.0), (stack, top)),
            "ops": [["sheet", "holes, clips and die laminations", lines]],
        }
    ]
    frames = {
        "plate": {
            "origin": [-shifts_a[0][0], -shifts_a[0][1], -stack],
            "axes": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        }
    }
    t = numbers["em-thirty-second"]
    name = PROGRAMS[0][0]
    expect = [
        [name, "tool_changes", {"z_top": top, "tools": [t], "loads_first": True}],
        [name, "spindle", {"rpm": [[rpm]]}],
        [name, "pauses", {"z_top": top, "count": 0}],
        [name, "depth", {"z_min": levels[-1]}],
        [name, "rapids_clear", {"z_top": top}],
        [name, "air_feed", {"z_top": top}],
        [
            name,
            "outline",
            {
                "elements": work_elements,
                "passes": [{"offset": r, "levels": levels}],
                "z_top": top,
                "leads": leads,
                "cut": "conventional",
                "part": "left",
            },
        ],
        [name, "cleared", {"points": hole_centres, "radius": r, "z": levels[-1]}],
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
        "levels": levels,
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
            doc, f"Clip {key}", ctx["step"], frame["origin"], frame["axes"]
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
