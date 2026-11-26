"""FreeCAD CAM recipe for MHA-SM-02, the knife mount.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The block's sizes come
from the feature export (its width, height and depth, the reamed knife bore,
the #30 drilled datum-B hole and the #10-24 tap hole); the blank, the skims, face
levels, spots, pecks, tips, the parallels and the position bands from
``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter diameters, speeds
and feeds from the shop (``shop/``). Every path is written here
(``rt.custom``): straight lines a recipe can state exactly. Typed here,
because neither record carries them: the #2 centre drill's catalogue geometry
(it sets the spot depth), the twist drills' 118° point, the machine's Z top
for the tap file's retract, the approach, safe and clearance heights, the
face overhang and the vise jaws' depth (keep-out shapes only).

Route (plan text in ``plan.toml``): two blanks and a trial coupon of 5/8 x
1-1/4 in 4140 HT flat, sawn 1.05-1.15 long; the bar's thickness is the
block's depth (Z), its width the height (Y), the sawn length the width (X).
KM01 (lying, gripped on the bar edges, A at the fixed jaw) skims a broad face
to the back face K; KM02 (turned over) faces the front face F to the depth.
KM03 (on edge, A down, F at the fixed jaw) skims the underside U. KM04
(upright, S up) skims the S end; KM05 (S down) faces the N end to the width.
KM06 (on edge, U down, S at the left) faces the top seat A to the height,
spots, drills datum B #30 (owner ruling 2026-11-24, fit audit OQ19), and drills the #25 tap
hole; KM07 brings the tap guide over the tap hole and ends. KM08 (lying, K
down, gripped on the ends, S at the fixed jaw, A at the left) spots, pilots
#25, drills 31/64 and reams the .4990 knife bore through (owner ruling
2026-11-23, tool audit Q13: the bore Ø.4985 +.0015/0, no 12 mm reamer).

Work frames (G54), each set in its setup:
- KM01: X0 the S end (the left), Y0 the fixed jaw (the A bar edge), Z0 the
  faced back face K.
- KM02: X0 the N end, Y0 the fixed jaw (A edge), Z0 the stacks' top (K).
- KM03: X0 the N end, Y0 the fixed jaw (F), Z0 the faced underside U.
- KM04: X0 the underside U, Y0 the fixed jaw (F), Z0 the faced S end.
- KM05: X0 the underside U (the right), Y0 the fixed jaw (F), Z0 the
  parallels' top (S).
- KM06, KM07: X0 the S end, Y0 the fixed jaw (F), Z0 the parallels' top (U).
- KM08: X0 the top seat A, Y0 the fixed jaw (S), Z0 the stacks' top (K).

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock; the
reamers are fed in and fed back out, never rapided out of a bore. The tap is
turned by hand under the spring tap guide (FluidNC cannot rigid-tap; owner,
Pedro, 2026-11-17), so the tap stop is a file of its own that ends with M30
over its hole (FluidNC refuses jogs in the Hold an M0 leaves).
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "sm_knife_mount"
COMMENT = "MHA-SM-02 knife mount"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes; flat keys are one Job.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("KM01_back", ("back_face",)),
    ("KM02_front", ("front_face",)),
    ("KM03_bottom", ("underside",)),
    ("KM04_s_end", ("s_end",)),
    ("KM05_width", ("n_end",)),
    (
        "KM06_top_holes",
        (
            ("top_face",),
            ("top_spot",),
            ("dowel_drill",),
            ("tap_drill",),
        ),
    ),
    ("KM07_stud_tap", ("tap_stud",)),
    ("KM08_bore", (("bore_spot",), ("bore_pilot",), ("bore_drill",), ("bore_ream",))),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held, and the tap file before its retract
# (the tap guide).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the taps, the saw, the files and the gauges are not).
CAM_TOOLS = (
    "em-half",
    "spot",
    "drill-30",
    "drill-25",
    "drill-31-64",
    "reamer-4990",
    "tap-guide",
)
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included: the shop record names
# the tool, not its geometry.
CENTRE_DRILL = {
    "pilot_mm": 5 / 64 * IN,
    "pilot_length_mm": 5 / 64 * IN,
    "body_mm": 3 / 16 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# The tap file's first motion: G53 G0 to machine Z0, the homed top. FluidNC
# sets an axis's machine position to its homing mpos_mm (default 0) after
# homing, and Z homes up (cad/config/shop-equipment/
# cnc.pm-30mv-controller: switches on all three axes); the owner (Pedro)
# confirmed it, answered in person 2026-11-21 (cnc rulings record): machine
# Z = 0 is the top of travel after homing.
MACHINE_Z_TOP_MM = 0.0
# Face passes start and finish with the cutter this far clear of the part's
# ends, so every plunge and stepover link is in the air beside it.
APPROACH_MM = 2.54
# Faces reach at least this far past the faces the jaws grip.
FACE_OVERHANG_MM = 0.5
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped face; the
# parallels' length (4 in, shop-equipment fixtures.parallels-lms-6745).
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 4 * IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# The least metal the recipe leaves between a drilled hole and the knife bore.
WEB_MIN_MM = 1.5
# The B-to-tap spacing over gauge pins is a gross check (the program holds
# the tap's Ø.005 position): ±.010, wider than the zone plus the pins'
# clearance in their holes, so a good part never reads outside it.
TAP_SPACING_GROSS_MM = 0.254
FACE_CUTS = ("back face", "depth", "underside", "s end", "width", "height")


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
    names (chip load × flutes × rpm). Every cut here runs at a setting."""
    op, _record_cut = _op_with_cut(plan, cut)
    if "settings" not in op:
        raise ValueError(f"'{cut}' names no shop setting")
    record = shop["settings"][op["settings"]]
    if record["material"] != plan["material_key"]:
        raise ValueError(
            f"'{cut}' setting {op['settings']} is not for {plan['material_key']}"
        )
    tool_ref = next(t["ref"] for t in plan["tools"] if t["id"] == op["tool"])
    if record["tool"] != tool_ref:
        raise ValueError(f"'{cut}' setting {op['settings']} is not {tool_ref}'s")
    rpm = float(record["rpm"])
    return rpm, record["chip_load_mm_per_tooth"] * record["flutes"] * rpm


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
    """Drill from ``top`` to ``tip`` in pecks of ``peck`` (``None``: one
    feed), each with a full retract to the R plane and a rapid back to just
    above the last peck. Moves to and from the hole run at ``clear``."""
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


def _ream(xy: tuple[float, float], top: float, tip: float, clear: float) -> list[str]:
    """Feed the reamer from the R plane to ``tip`` and feed it back out to the
    R plane, spindle running: no rapid leaves the hole."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(tip):.3f} F{{feed}}",
        f"G1 Z{r_plane:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def _stations(y: tuple[float, float], radius: float, max_step: float) -> list[float]:
    """Zigzag pass stations across the face ``y`` (low, high), from its high
    side: each pass takes the same width, at most ``max_step``, and together
    the cutter reaches ``FACE_OVERHANG_MM`` past both edges."""
    span = y[1] - y[0] + FACE_OVERHANG_MM
    n = math.ceil(span / max_step - 1e-9)
    step = span / n
    if 2 * radius - step < FACE_OVERHANG_MM:
        raise ValueError(
            f"a {step:.3f} stepover leaves the first pass short of the edge"
        )
    first = y[1] + radius - step
    return [_r(first - k * step) for k in range(n)]


def _face(
    levels: list[float], top: float, x: tuple[float, float], ys: list[float]
) -> list[str]:
    """Zigzag faces at ``levels``: at each, one X pass per Y in ``ys``
    between the cutter-centre ends ``x``, alternating direction, starting at
    the low X end; every plunge, level change and stepover beside the part."""
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
            # Back to the low X side, beside the part, for the next level.
            lines.append(f"G1 X{x0:.3f} F{{feed}}")
        if z != levels[-1]:
            lines.append(f"G1 Y{ys[0]:.3f} F{{feed}}")
    return lines + [f"G0 Z{clear:.3f}"]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The block's faces and holes from the export, each checked against the
    frame the recipe assumes: the S end (+X) to the N end along X, the
    underside U to the top seat A along Y, the back face K to the front face F
    along Z; the knife bore through from F along −Z; datum B and the tap hole
    blind from A along −Y."""
    f = features["features"]

    def plane(name: str, axis: str) -> float:
        face = f[name]["plane"]
        if face["axis"] != axis:
            raise ValueError(f"{name}: expected a plane square to model {axis}")
        return face["value"]

    s_end, n_end = plane("plus_x_side", "x"), plane("minus_x_side", "x")
    under, top = plane("bottom_face", "y"), plane("top_seat", "y")
    back, front = plane("back_face", "z"), plane("front_face", "z")
    sizes = {
        "width": (s_end - n_end, f["minus_x_side"]["width_nominal"]),
        "height": (top - under, f["bottom_face"]["height_nominal"]),
        "depth": (front - back, f["back_face"]["depth_nominal"]),
    }
    for name, (span, nominal) in sizes.items():
        if not math.isclose(span, nominal, abs_tol=1e-3):
            raise ValueError(
                f"the faces' {name} {span:.4f} is not the {name} {nominal}"
            )
    bore = f["knife_bore"]
    if (
        bore["axis"] != [0.0, 0.0, -1.0]
        or not math.isclose(bore["at"][2], front, abs_tol=1e-3)
        or bore.get("thru") is not True
        or bore["process"] != "ream"
    ):
        raise ValueError(
            "knife_bore: expected reamed through from the front face along -Z"
        )
    dowel = f["dowel_hole"]
    if (
        dowel["axis"] != [0.0, -1.0, 0.0]
        or not math.isclose(dowel["at"][1], top, abs_tol=1e-3)
        or dowel["process"] != "drill"
        or dowel.get("thru")
    ):
        raise ValueError("dowel_hole: expected drilled blind from the top seat along -Y")
    tap = f["stud_tap"]
    if tap["axis"] != [0.0, -1.0, 0.0] or not math.isclose(
        tap["at"][1], top, abs_tol=1e-3
    ):
        raise ValueError("stud_tap: expected tapped blind from the top seat along -Y")
    return {
        "s_end": s_end,
        "n_end": n_end,
        "under": under,
        "top": top,
        "back": back,
        "front": front,
        "width": s_end - n_end,
        "height": top - under,
        "depth": front - back,
        "bore": bore,
        "dowel": dowel,
        "tap": tap,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    width, height, depth = g["width"], g["height"], g["depth"]
    bore, dowel, tap = g["bore"], g["dowel"], g["tap"]

    # The blank: the sawn length along X, the bar's width along Y, its
    # thickness along Z.
    t_min, t_max = p["blank_thickness_min_mm"], p["blank_thickness_max_mm"]
    w_min, w_max = p["blank_width_min_mm"], p["blank_width_max_mm"]
    l_min, l_max = p["blank_length_min_mm"], p["blank_length_max_mm"]
    for key in ("thickness", "width", "length"):
        for end in ("min", "max"):
            _agree(plan, f"blank_{key}_{end}_mm", p[f"blank_{key}_{end}_in"] * IN)
    back_skim, under_skim, end_skim = (
        p["back_skim_mm"],
        p["bottom_skim_mm"],
        p["end_skim_mm"],
    )
    for what, least, skim, size in (
        ("thinnest bar", t_min, back_skim, depth),
        ("narrowest bar", w_min, under_skim, height),
        ("shortest blank", l_min, end_skim, width),
    ):
        if least - skim <= size:
            raise ValueError(
                f"the {what} less its skim, {least - skim:.3f}, leaves nothing to face to {size:.3f}"
            )
    front_top = t_max - back_skim
    top_top = w_max - under_skim
    end_top = l_max - end_skim
    _agree(plan, "front_top_max_mm", front_top)
    _agree(plan, "top_top_max_mm", top_top)
    _agree(plan, "end_top_max_mm", end_top)

    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    d30 = _shop_tool(plan, shop, "drill-30")["diameter_mm"]
    d25 = _shop_tool(plan, shop, "drill-25")["diameter_mm"]
    d3164 = _shop_tool(plan, shop, "drill-31-64")["diameter_mm"]
    r4990 = _shop_tool(plan, shop, "reamer-4990")["diameter_mm"]
    r = em / 2
    # Datum B is the #30 drill at the DRILLED HOLES row (owner ruling
    # 2026-11-24, fit audit OQ19): the drill is the band's low end.
    if not math.isclose(d30, dowel["dia"][0], abs_tol=1e-6):
        raise ValueError(f"#30 Ø{d30} is not datum B's drilled size {dowel['dia'][0]}")
    if not bore["dia"][0] <= r4990 <= bore["dia"][1]:
        raise ValueError(
            f".4990 reamer Ø{r4990} is outside the knife bore's band {bore['dia']}"
        )
    if not tap["dia"][0] <= d25 <= tap["dia"][1]:
        raise ValueError(f"#25 Ø{d25} is outside the tap drill's band {tap['dia']}")
    if not p["spot_dia_mm"] < d30:
        raise ValueError("the spot is not under the #30")
    if not d25 < d3164 < r4990:
        raise ValueError(
            "the #25 pilot, the 31/64 drill and the .4990 reamer are not in rising order"
        )
    step_max = p["face_stepover_max_mm"]
    level_max = p["face_step_max_mm"]
    face_rpm, face_feed = _setting(plan, shop, "back face")
    for name in FACE_CUTS:
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), em, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' cutter Ø{_cut(plan, name, 'cutter_dia_mm')}, the end mill is Ø{em}"
            )
        if _setting(plan, shop, name) != (face_rpm, face_feed):
            raise ValueError(f"'{name}' runs at another setting than 'back face'")
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), step_max, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' radial_woc_mm is not process.face_stepover_max_mm"
            )
    for name, skim in (
        ("back face", back_skim),
        ("underside", under_skim),
        ("s end", end_skim),
    ):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), skim, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not its skim")
    for name in ("depth", "width", "height"):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), level_max, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not process.face_step_max_mm")
    depth_levels = _levels(front_top, depth, level_max)
    width_levels = _levels(end_top, width, level_max)
    height_levels = _levels(top_top, height, level_max)

    # Holes. KM06: spot both, #30 pecked for datum B, #25 pecked for the
    # tap. KM08: spot, #25 pilot pecked, the 31/64 drill in one feed, the
    # .4990 reamer fed in and out.
    spot_rpm, spot_feed = _setting(plan, shop, "top spot")
    if _setting(plan, shop, "bore spot") != (spot_rpm, spot_feed):
        raise ValueError("'bore spot' runs at another setting than 'top spot'")
    d30_rpm, d30_feed = _setting(plan, shop, "dowel drill")
    d25_rpm, d25_feed = _setting(plan, shop, "tap drill")
    if _setting(plan, shop, "bore pilot") != (d25_rpm, d25_feed):
        raise ValueError("'bore pilot' runs at another setting than 'tap drill'")
    d3164_rpm, d3164_feed = _setting(plan, shop, "bore drill")
    r4990_rpm, r4990_feed = _setting(plan, shop, "bore ream")
    for name in ("top spot", "bore spot"):
        if not math.isclose(
            _cut(plan, name, "cutter_dia_mm"), p["spot_dia_mm"], abs_tol=1e-6
        ):
            raise ValueError(f"'{name}' cutter_dia_mm is not process.spot_dia_mm")
    for name, dia in (
        ("dowel drill", d30),
        ("tap drill", d25),
        ("bore pilot", d25),
        ("bore drill", d3164),
        ("bore ream", r4990),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not its tool's Ø{dia}")
    spot_depth = _spot_depth(p["spot_dia_mm"])
    dowel_peck, tap_peck = p["dowel_peck_mm"], p["tap_peck_mm"]
    for cut, peck, hole_depth in (
        ("dowel drill", dowel_peck, "{{cad.dowel_hole_depth_mm}}"),
        ("tap drill", tap_peck, "{{cad.stud_tap_drill_depth_mm}}"),
        ("bore pilot", tap_peck, "{{cad.back_face_depth_mm}}"),
    ):
        op = _op_with_cut(plan, cut)[0]
        if op["peck"] != {"step_mm": peck, "retract": "full"}:
            raise ValueError(f"'{cut}' peck is not its process peck with full retract")
        if op["hole_depth_mm"] != hole_depth:
            raise ValueError(f"'{cut}' hole_depth_mm is not {hole_depth}")
    op = _op_with_cut(plan, "bore drill")[0]
    if op["peck"] != "none" or op["hole_depth_mm"] != "{{cad.back_face_depth_mm}}":
        raise ValueError(
            "'bore drill' is not one feed through {{cad.back_face_depth_mm}}"
        )
    if depth / d3164 > 3:
        raise ValueError("the 31/64 drill's L/D is over 3: it would need pecks")
    past = p["drill_past_mm"]
    # Datum B (KM06, Z0 = U): the #30's full diameter at the drawing's depth,
    # as the tap drill's (the band .36-.38 takes the drill's point).
    dowel_depth = dowel["depth_nominal"]
    dowel_drill_tip = height - (dowel_depth + _point(d30))
    tap_drill_tip = height - (tap["drill_depth_nominal"] + _point(d25))
    _agree(plan, "dowel_drill_tip_height_mm", dowel_drill_tip)
    _agree(plan, "tap_drill_tip_height_mm", tap_drill_tip)
    # The knife bore (KM08, Z0 = K).
    pilot_tip = -(past + _point(d25))
    bore_tip = -(past + _point(d3164))
    _agree(plan, "pilot_tip_height_mm", pilot_tip)
    _agree(plan, "bore_drill_tip_height_mm", bore_tip)
    bore_ream_tip = p["bore_ream_tip_height_mm"]
    if not bore_tip < bore_ream_tip < -past:
        raise ValueError(
            f".4990 reamer tip Z {bore_ream_tip:.3f}: not past K by {past} or below the drill's tip {bore_tip:.3f}"
        )
    import cam_nc

    if -bore_ream_tip <= cam_nc.ream_full_diameter_past_min_mm(plan, "reamer-4990"):
        raise ValueError(
            f".4990 reamer tip Z {bore_ream_tip:.3f}: its full diameter does not reach K (cnc.ream-full-diameter)"
        )
    _agree(plan, "bore_ream_r_plane_mm", depth + SAFE_MM)
    _agree(plan, "bore_ream_clear_mm", depth + CLEAR_MM)
    # The sheet's re-ream MDI feeds at the reamer's setting.
    _agree(plan, "bore_ream_feed_mm_min", r4990_feed)

    # Hand tap (KM07): the bottoming tap's chamfer may be at most the drill's
    # shallowest full-diameter depth less the thread depth; the plug tap's
    # point stops .006 in above that depth.
    _agree(
        plan, "tap_chamfer_max_mm", tap["drill_depth"][0] - tap["thread_depth_nominal"]
    )
    _agree(plan, "plug_tap_point_mm", tap["drill_depth"][0] - 0.006 * IN)
    # The bore's parallelism, printed by the inspection.
    _agree(plan, "bore_parallelism_mm", bore["parallelism"])

    # Vise grips: jaw height less the parallels (on edge, upright) and the
    # stacks (lying).
    jaw = p["vise_jaw_height_mm"]
    edge_grip = jaw - p["parallel_height_mm"]
    lying_grip = jaw - p["riser_height_mm"]
    _agree(plan, "edge_grip_mm", edge_grip)
    _agree(plan, "lying_grip_mm", lying_grip)
    jaw_w = p["vise_jaw_width_mm"]
    for key, along in (
        ("vise_long_inset_mm", l_max),
        ("vise_upright_inset_mm", top_top),
        ("vise_top_inset_mm", width),
        ("vise_bore_inset_mm", height),
    ):
        _agree(plan, key, -(jaw_w - along) / 2)
    for name, (grip, faced) in {
        "KM02": (lying_grip, depth),
        "KM05": (edge_grip, width),
        "KM06": (edge_grip, height),
    }.items():
        if grip >= faced:
            raise ValueError(
                f"{name}: the faced top {faced:.3f} is not above the jaw tops {grip:.3f}"
            )
    # The tap stack's ceiling: spindle-to-table maximum less the tool-change
    # clearance, the vise bed, the parallels, KM06's work top and the
    # collet's gauge, rounded down to .01 in; the tap's reach in its wrench,
    # less the guide's 3 1/8 in, rounded down to .01 in.
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["parallel_height_mm"]
        - top_top
        - p["r8_collet_gauge_mm"]
    )
    stack = math.floor(stack / 0.254 + 1e-9) * 0.254
    _agree(plan, "tap_stack_max_mm", stack)
    _agree(
        plan,
        "tap_wrench_reach_max_mm",
        math.floor((stack - 3.125 * IN) / 0.254 + 1e-9) * 0.254,
    )
    t = p["parallel_thickness_mm"]

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)). The raw S end stands
    # end_skim beyond the finished S end, the raw underside under_skim below
    # U, the raw back face back_skim behind K; the raw A edge and N end stand
    # where the largest blank puts them.
    raw_s = g["s_end"] + end_skim
    raw_n = raw_s - l_max
    raw_a = g["under"] - under_skim + w_max
    frames = {
        # Lying, a broad face up (it becomes K), the A edge at the fixed jaw,
        # S at the left.
        "back": _frame([raw_s, raw_a, g["back"]], [0, 1, 0], [0, 0, -1]),
        # Lying, K down, the A edge at the fixed jaw, N at the left.
        "front": _frame([raw_n, raw_a, g["back"]], [0, 1, 0], [0, 0, 1]),
        # On edge, A down, F at the fixed jaw, N at the left.
        "underside": _frame([raw_n, g["under"], g["front"]], [0, 0, 1], [0, -1, 0]),
        # Upright, S up, F at the fixed jaw, U at the left.
        "s_end": _frame([g["s_end"], g["under"], g["front"]], [0, 0, 1], [1, 0, 0]),
        # Upright, S down, F at the fixed jaw, U at the right (X0).
        "n_end": _frame([g["s_end"], g["under"], g["front"]], [0, 0, 1], [-1, 0, 0]),
        # On edge, U down, F at the fixed jaw, S at the left.
        "top": _frame([g["s_end"], g["under"], g["front"]], [0, 0, 1], [0, 1, 0]),
        # Lying, K down, S at the fixed jaw, A at the left.
        "bore": _frame([g["s_end"], g["top"], g["back"]], [1, 0, 0], [0, 0, 1]),
    }
    # Each frame's references where the setup sheet puts them: the corner of
    # S, U and F, or of S, A and K, at the named zeros.
    suf = [g["s_end"], g["under"], g["front"]]
    sak = [g["s_end"], g["top"], g["back"]]
    for key, corner, axes in (
        ("back", sak, (2,)),
        ("front", sak, (2,)),
        ("underside", suf, (1, 2)),
        ("s_end", suf, (0, 1, 2)),
        ("n_end", suf, (0, 1, 2)),
        ("top", suf, (0, 1, 2)),
        ("bore", sak, (0, 1, 2)),
    ):
        at = _to(frames[key], corner)
        for axis in axes:
            if not math.isclose(at[axis], 0.0, abs_tol=1e-6):
                raise ValueError(
                    f"{key}: the reference corner is not at {'XYZ'[axis]}0"
                )
    stocks = {
        "back": ((0.0, l_max), (-w_max, 0.0), (-(t_max - back_skim), back_skim)),
        "front": ((0.0, l_max), (-w_max, 0.0), (0.0, front_top)),
        "underside": ((0.0, l_max), (-depth, 0.0), (-(w_max - under_skim), under_skim)),
        "s_end": ((0.0, top_top), (-depth, 0.0), (-(l_max - end_skim), end_skim)),
        "n_end": ((-top_top, 0.0), (-depth, 0.0), (0.0, end_top)),
        "top": ((0.0, width), (-depth, 0.0), (0.0, top_top)),
        "bore": ((0.0, height), (-width, 0.0), (0.0, depth)),
    }

    def entry(frame: str, hole: dict[str, Any], z_top: float) -> list[float]:
        x, y, z = _to(frames[frame], hole["at"])
        if not math.isclose(z, z_top, abs_tol=1e-6):
            raise ValueError(
                f"a hole does not enter at Z {z_top:.3f} in the {frame} frame"
            )
        return [_r(x), _r(y)]

    b_xy = entry("top", dowel, height)
    tap_xy = entry("top", tap, height)
    bore_xy = entry("bore", bore, depth)
    # The stations the sheet prints: B at the drawing's side and row, the tap
    # .300 BASIC from B, the bore .824 BASIC from A and .500 from S.
    if not math.isclose(
        b_xy[0], dowel["side_nominal"], abs_tol=1e-3
    ) or not math.isclose(-b_xy[1], dowel["row_nominal"], abs_tol=1e-3):
        raise ValueError(f"datum B at {b_xy} is not the drawing's side and row")
    _agree(plan, "tap_x_mm", tap_xy[0])
    if not math.isclose(tap_xy[0] - b_xy[0], tap["basic_from_b"], abs_tol=1e-3):
        raise ValueError("the tap is not its BASIC from B")
    if not math.isclose(bore_xy[0], bore["basic_from_a"], abs_tol=1e-3):
        raise ValueError("the bore is not its BASIC from A")
    _agree(plan, "bore_y_mm", -bore_xy[1])
    if not math.isclose(-bore_xy[1] - b_xy[0], bore["basic_from_b"], abs_tol=1e-3):
        raise ValueError("the bore is not its BASIC from B")
    # The bore's two readings, on the height gauge over pins: each axis's
    # error is the pins' play (each pin rests on its hole's low side) plus
    # the gauge's count (half a count for the reading from A; a full count
    # for the bore from B, the difference of two readings). The bore's GO pin
    # plays half the bore's band; drilled B takes the largest pin of the
    # .001-step pin-gauge sets that enters it, which plays at most half a
    # step (b_pin_step_mm). Each reading's band is the zone's radius less its
    # error about its BASIC (outside it no bore is in the zone); the radial
    # test, each axis's error added, then accepts the bore.
    count = shop["gauges"]["height-gauge"]["resolution_mm"]
    bore_play = (bore["dia"][1] - bore["dia"][0]) / 2
    b_play = p["b_pin_step_mm"] / 2
    err_a = bore_play + count / 2
    err_b = bore_play + b_play + count
    _agree(plan, "bore_err_a_mm", err_a)
    _agree(plan, "bore_err_b_mm", err_b)
    if (
        plan["parameters"]["bore_err_a_mm"] < err_a - 1e-6
        or plan["parameters"]["bore_err_b_mm"] < err_b - 1e-6
    ):
        raise ValueError("the bore's reading errors are stated below the recipe's")
    radius = bore["position_dia"] / 2
    for key, basic, half in (
        ("bore_from_a", bore["basic_from_a"], radius - err_a),
        ("bore_from_b", bore["basic_from_b"], radius - err_b),
    ):
        if half <= 0:
            raise ValueError(f"{key}: the reading error leaves no band")
        _agree(plan, f"{key}_min_mm", basic - half)
        _agree(plan, f"{key}_max_mm", basic + half)
    # The tap's spacing to B, a gross check only: wider than half the zone
    # plus the pins' clearance (B's set pin's step; the #25 hole's
    # drill-point wander allowed as much again).
    pin_play = p["b_pin_step_mm"]
    if TAP_SPACING_GROSS_MM < tap["position_dia"] / 2 + 2 * pin_play:
        raise ValueError("the tap spacing's gross band is inside the pins' play")
    _agree(plan, "tap_from_b_min_mm", tap["basic_from_b"] - TAP_SPACING_GROSS_MM)
    _agree(plan, "tap_from_b_max_mm", tap["basic_from_b"] + TAP_SPACING_GROSS_MM)
    # KM07's reference station on A: the tap's point (no wider than its drill)
    # stands on solid A between B and the tap drill.
    ref_x = plan["parameters"]["tap_ref_x_mm"]
    if not (b_xy[0] + dowel["dia"][1] / 2 + d25 / 2 < ref_x < tap_xy[0] - d25):
        raise ValueError(
            f"the tap's reference station X {ref_x} is not on solid A between B and the tap drill"
        )
    # Metal left between each blind hole's drill point and the knife bore.
    for name, hole, tip_depth, dia in (
        ("datum B", dowel, height - dowel_drill_tip, d30),
        ("the tap", tap, height - tap_drill_tip, d25),
    ):
        tip_y = g["top"] - tip_depth
        dx = abs(hole["at"][0] - bore["at"][0])
        reach = max(dx - dia / 2, 0.0)
        gap = math.hypot(reach, tip_y - bore["at"][1]) - r4990 / 2
        if gap < WEB_MIN_MM:
            raise ValueError(f"{name}'s drill point is {gap:.2f} from the bore")
    # The bore clears KM08's parallels under S and N.
    if not (-width + t < bore_xy[1] - r4990 / 2 and bore_xy[1] + r4990 / 2 < -t):
        raise ValueError(f"the bore at Y {bore_xy[1]} reaches a parallel ({t} thick)")
    # The coupon (gripped on its sawn ends, its A edge at X0) holds the bore
    # inside it with its shortest length and narrowest width.
    if not (
        bore_xy[0] + r4990 / 2 < w_min - under_skim and -bore_xy[1] + r4990 / 2 < l_min - t
    ):
        raise ValueError("the bore does not fit inside the smallest coupon")
    # KM06's blind holes stop above the parallels' top.
    if min(dowel_drill_tip, tap_drill_tip) <= 0:
        raise ValueError("a KM06 hole reaches the parallels")

    em_tool = {
        "tool": "em-half",
        "dia": em,
        "shape": "endmill",
        "flutes": 3,
        "rpm": face_rpm,
        "feed": face_feed,
        "plunge": face_feed,
    }

    def drill_tool(
        tool: str, dia: float, rpm: float, feed: float, angle: float
    ) -> dict:
        return {
            "tool": tool,
            "dia": dia,
            "shape": "drill",
            "tip_angle": angle,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
        }

    spot_tool = drill_tool(
        "spot", CENTRE_DRILL["body_mm"], spot_rpm, spot_feed, CENTRE_DRILL["point_deg"]
    )
    d30_tool = drill_tool("drill-30", d30, d30_rpm, d30_feed, DRILL_POINT_DEG)
    d25_tool = drill_tool("drill-25", d25, d25_rpm, d25_feed, DRILL_POINT_DEG)
    d3164_tool = drill_tool("drill-31-64", d3164, d3164_rpm, d3164_feed, DRILL_POINT_DEG)
    r4990_tool = drill_tool("reamer-4990", r4990, r4990_rpm, r4990_feed, DRILL_POINT_DEG)

    def run(x: tuple[float, float]) -> tuple[float, float]:
        return (x[0] - r - APPROACH_MM, x[1] + r + APPROACH_MM)

    # (levels, stock top, cutter-centre X ends, Y stations, face Y, part X span)
    faces = {
        "back_face": (
            [0.0],
            back_skim,
            run((0.0, l_max)),
            _stations((-w_max, 0.0), r, step_max),
            (-w_max, 0.0),
            l_max,
        ),
        "front_face": (
            depth_levels,
            front_top,
            run((0.0, l_max)),
            _stations((-w_max, 0.0), r, step_max),
            (-w_max, 0.0),
            l_max,
        ),
        "underside": (
            [0.0],
            under_skim,
            run((0.0, l_max)),
            _stations((-depth, 0.0), r, step_max),
            (-depth, 0.0),
            l_max,
        ),
        "s_end": (
            [0.0],
            end_skim,
            run((0.0, top_top)),
            _stations((-depth, 0.0), r, step_max),
            (-depth, 0.0),
            top_top,
        ),
        "n_end": (
            width_levels,
            end_top,
            run((-top_top, 0.0)),
            _stations((-depth, 0.0), r, step_max),
            (-depth, 0.0),
            top_top,
        ),
        "top_face": (
            height_levels,
            top_top,
            run((0.0, width)),
            _stations((-depth, 0.0), r, step_max),
            (-depth, 0.0),
            width,
        ),
    }
    frame_of = {
        "back_face": "back",
        "front_face": "front",
        "underside": "underside",
        "s_end": "s_end",
        "n_end": "n_end",
        "top_face": "top",
    }
    jobs = []
    for key, (levels, top, xs, ys, _y, _span) in faces.items():
        jobs.append(
            {
                **em_tool,
                "frame": frame_of[key],
                "label": key.replace("_", " "),
                "stock": stocks[frame_of[key]],
                "ops": [
                    [
                        key,
                        f"face the {key.replace('_', ' ')}",
                        _face(levels, top, xs, ys),
                    ]
                ],
            }
        )
    top_clear = height + CLEAR_MM
    bore_clear = depth + CLEAR_MM
    holes_jobs = (
        (
            spot_tool,
            "top",
            "top_spot",
            "spot datum B and the tap hole",
            [
                ln
                for xy in (b_xy, tap_xy)
                for ln in _spot(xy, height, height - spot_depth, top_clear)
            ],
        ),
        (
            d30_tool,
            "top",
            "dowel_drill",
            "drill datum B #30",
            _pecked(b_xy, height, dowel_drill_tip, dowel_peck, top_clear),
        ),
        (
            d25_tool,
            "top",
            "tap_drill",
            "drill the tap hole #25",
            _pecked(tap_xy, height, tap_drill_tip, tap_peck, top_clear),
        ),
        (
            spot_tool,
            "bore",
            "bore_spot",
            "spot the knife bore",
            _spot(bore_xy, depth, depth - spot_depth, bore_clear),
        ),
        (
            d25_tool,
            "bore",
            "bore_pilot",
            "pilot the knife bore #25",
            _pecked(bore_xy, depth, pilot_tip, tap_peck, bore_clear),
        ),
        (
            d3164_tool,
            "bore",
            "bore_drill",
            "drill the knife bore 31/64",
            _pecked(bore_xy, depth, bore_tip, None, bore_clear),
        ),
        (
            r4990_tool,
            "bore",
            "bore_ream",
            "ream the knife bore .4990",
            _ream(bore_xy, depth, bore_ream_tip, bore_clear),
        ),
    )
    for tool, frame, key, label, lines in holes_jobs:
        jobs.append(
            {
                **tool,
                "frame": frame,
                "label": label,
                "stock": stocks[frame],
                "ops": [[key, label, lines]],
            }
        )

    # The tap file: the tap guide loaded by its own M6 (its %msg names the
    # hole), Z to the machine's top in machine coordinates before any XY (the
    # operator left Z jogged down after the last tool change), over the hole,
    # M30: the controller ends Idle, so the operator can jog the guide's point
    # down into the wrench.
    manual = {
        "tap_stud": {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": "SPINDLE STAYS OFF. NEXT: 10-24 TAPS IN THE STUD HOLE",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{tap_xy[0]:.3f} Y{tap_xy[1]:.3f}",
                "(10-24 PLUG THEN BOTTOMING TAP IN THE STUD HOLE. JOG Z DOWN TO PUSH THE GUIDE POINT HOME"
                " IN THE WRENCH. TAP BY HAND TO THE NOTED DRO Z, PUSHING THE POINT HOME EACH 1/2 IN,"
                " READ WITH THE POINT PUSHED HOME. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": tap_xy,
        }
    }

    # Keep-outs: the jaws beside the gripped span from the parallels' top to
    # the jaw top, across the jaw width (a jaw's face is placed where the
    # part's extreme can put it); the parallels under the part's gripped edges.
    def jaws(
        z_top: float, x: tuple[float, float], moving: tuple[float, float]
    ) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - jaw_w / 2, mid + jaw_w / 2)
        return [
            _box("moving jaw", span, (moving[0] - JAW_DEPTH_MM, moving[1]), z_top),
            _box("fixed jaw", span, (0.0, JAW_DEPTH_MM), z_top),
        ]

    def parallels(
        x: tuple[float, float], moving: tuple[float, float]
    ) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - PARALLEL_LENGTH_MM / 2, mid + PARALLEL_LENGTH_MM / 2)
        return [
            _box("moving-jaw parallel", span, (moving[0], moving[1] + t), 0.0),
            _box("fixed-jaw parallel", span, (-t, 0.0), 0.0),
        ]

    keep = {
        # Z0 on the faced top: the lowest piece puts the jaw tops highest.
        "back_face": jaws(
            lying_grip - (t_min - back_skim), (0.0, l_max), (-w_max, -w_min)
        ),
        "front_face": jaws(lying_grip, (0.0, l_max), (-w_max, -w_min)),
        "underside": jaws(
            edge_grip - (w_min - under_skim), (0.0, l_max), (-depth, -depth)
        ),
        "s_end": jaws(edge_grip - (l_min - end_skim), (0.0, top_top), (-depth, -depth)),
        "n_end": jaws(edge_grip, (-top_top, 0.0), (-depth, -depth)),
        "top_face": jaws(edge_grip, (0.0, width), (-depth, -depth)),
        "bore": jaws(lying_grip, (0.0, height), (-width, -width)),
    }
    top_keep = keep["top_face"] + parallels((0.0, width), (-depth, -depth))
    bore_keep = keep["bore"] + parallels((0.0, height), (-width, -width))

    tn = numbers
    expect: list[list[Any]] = []

    def face_checks(key: str) -> list[list[Any]]:
        levels, top, _xs, _ys, y, span = faces[key]
        return [
            ["depth", {"z_min": _r(levels[-1])}],
            ["rapids_clear", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            *[
                [
                    "face_passes",
                    {
                        "z": _r(z),
                        "y": list(y),
                        "max_engagement": step_max,
                        "radius": r,
                        "span": span,
                        "overhang": FACE_OVERHANG_MM,
                    },
                ]
                for z in levels
            ],
            ["keep_out", {"radius": r, "boxes": keep[key]}],
        ]

    def hole_checks(
        centres: list[list[float]],
        top: float,
        bottom: float,
        radius: float,
        boxes: list,
    ) -> list[list[Any]]:
        return [
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": top, "open_holes": centres}],
            ["vertical_below_top", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": radius, "boxes": boxes}],
        ]

    single = {
        "KM01_back": "back_face",
        "KM02_front": "front_face",
        "KM03_bottom": "underside",
        "KM04_s_end": "s_end",
        "KM05_width": "n_end",
    }
    for name, key in single.items():
        top = faces[key][1]
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": top, "tools": [tn["em-half"]], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[face_rpm]]}],
            [name, "pauses", {"z_top": top, "count": 0}],
            *[[name, check, kwargs] for check, kwargs in face_checks(key)],
        ]
    spot_r = CENTRE_DRILL["body_mm"] / 2
    name = "KM06_top_holes"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": top_top,
                "tools": [
                    tn["em-half"],
                    tn["spot"],
                    tn["drill-30"],
                    tn["drill-25"],
                ],
                "loads_first": True,
            },
        ],
        [
            name,
            "spindle",
            {"rpm": [[face_rpm], [spot_rpm], [d30_rpm], [d25_rpm]]},
        ],
        [name, "pauses", {"z_top": top_top, "count": 0}],
        [name, "depth", {"z_min": _r(min(dowel_drill_tip, tap_drill_tip))}],
    ]
    for k, checks in enumerate(
        (
            face_checks("top_face"),
            hole_checks([b_xy, tap_xy], height, height - spot_depth, spot_r, top_keep),
            hole_checks([b_xy], height, dowel_drill_tip, d30 / 2, top_keep),
            hole_checks([tap_xy], height, tap_drill_tip, d25 / 2, top_keep),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]
    expect += [
        [
            "KM07_stud_tap",
            "tap_stop",
            {"tool": tn["tap-guide"], "at": tap_xy, "machine_top": MACHINE_Z_TOP_MM},
        ],
        ["KM07_stud_tap", "air_feed", {"z_top": height}],
    ]
    name = "KM08_bore"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": depth,
                "tools": [
                    tn["spot"],
                    tn["drill-25"],
                    tn["drill-31-64"],
                    tn["reamer-4990"],
                ],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[spot_rpm], [d25_rpm], [d3164_rpm], [r4990_rpm]]}],
        [name, "pauses", {"z_top": depth, "count": 0}],
        [name, "depth", {"z_min": _r(bore_tip)}],
    ]
    for k, checks in enumerate(
        (
            hole_checks([bore_xy], depth, depth - spot_depth, spot_r, bore_keep),
            hole_checks([bore_xy], depth, pilot_tip, d25 / 2, bore_keep),
            hole_checks([bore_xy], depth, bore_tip, d3164 / 2, bore_keep),
            [
                *hole_checks([bore_xy], depth, bore_ream_tip, r4990 / 2, bore_keep),
                ["feed_out", {"z_top": depth}],
            ],
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

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
            doc, f"Knife mount {key}", ctx["step"], frame["origin"], frame["axes"]
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
# The .4990 chucking reamer's 45° lead, taken at .020 (the longest the plan
# allowed for datum B's reamer before B became drilled). KM08 reams the
# knife bore through, so its tip ends out of the part and the lead's length
# changes nothing the report measures. The jobs carry the reamer as a 118°
# drill for FreeCAD.
REAMER_LEAD_MM = 0.020 * IN


def as_machined(ctx: dict[str, Any], inputs: Any) -> dict[str, Any]:
    """What the as-machined report needs: the sawn 4140 blank in KM01's
    ``back`` frame, its sawn length along X at the plan's band
    (``blank_length_min_mm``..``blank_length_max_mm``), nominal its middle
    (the saw is not marked at one size). X0 is the S end, which KM04 skims
    from its high point, so it stays put. The bar's width (Y) and thickness
    (Z) at their bands' middles: the thickness from the K face (KM01's Z0 is
    the top less the skim), the width from the U edge (KM03's Z0 is the edge
    less the skim), which the frames put where the widest bar has it. KM07 is
    a tap guide by hand and cuts nothing. The .4990 reamer cuts with a 45°
    lead of :data:`REAMER_LEAD_MM`, not a drill's point."""
    p = inputs.plan["parameters"]
    lengths = {
        "nominal": (p["blank_length_min_mm"] + p["blank_length_max_mm"]) / 2,
        "min": p["blank_length_min_mm"],
        "max": p["blank_length_max_mm"],
    }
    width = (p["blank_width_min_mm"] + p["blank_width_max_mm"]) / 2
    thickness = (p["blank_thickness_min_mm"] + p["blank_thickness_max_mm"]) / 2
    _x, (y0, _y1), (_z0, z1) = next(job["stock"] for job in ctx["jobs"] if job["frame"] == "back")
    tools = {}
    for job in ctx["jobs"]:
        if job["tool"].startswith("reamer-"):
            r = job["dia"] / 2
            tools[ctx["numbers"][job["tool"]]] = [[r - REAMER_LEAD_MM, 0.0], [r, REAMER_LEAD_MM]]
    return {
        "parts": {
            "": {
                "blank": {
                    "frame": "back",
                    "box": [[0.0, lengths["nominal"]], [y0, y0 + width], [z1 - thickness, z1]],
                    "length": {"axis": "x", "keep": "min", "mm": lengths},
                },
            }
        },
        "skip": {},
        "tools": tools,
        "notes": ["the #10-24 thread is tapped by hand (KM07 brings the tap guide over it)"],
    }
