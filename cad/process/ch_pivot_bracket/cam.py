"""FreeCAD CAM recipe for MHA-CH-08, the pivot bracket.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The bracket's sizes
come from the feature export (its sides, inboard and outboard faces, foot
end, seat and foot top, the arch, the bore, the hold-down hole and the apex
tap); the blank, the skims, levels, spots, tips and the stacks from
``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter diameters, speeds
and feeds from the shop (``shop/``) and the plan's authored drill settings.
Every path is written here (``rt.custom``): straight lines and arcs a recipe
can state exactly. Typed here, because neither record carries them: the #2
centre drill's catalogue geometry (it sets the spot depth), the twist drills'
118° point, the approach, safe and clearance heights, the face overhang, the
vise jaws' depth (keep-out shapes only) and the machine's Z top for the tap
file's retract.

Route (the agent's for speed, owner rulings 2026-11-21; plan text in
``plan.toml``): one 3/4 in square 1018 blank 1.45-1.50 long per run, the
bar's length along the bracket's height. Lying on the 1 in + 1/2 in parallel
stacks: PB01 skims the west side W, PB02 (W down) faces the east side to the
width. Upright on the 1 in parallels: PB03 faces the seat, spots and drills
the #15 hold-down hole from it into the waste above the foot. Lying, the
inboard face I up: PB04 profiles the arch through the ear and spots, drills
(D) and opens (F) the bore through it, both into the waste the step removes; the jaws
grip only that waste. Lying, I down: PB05 faces the foot end to the length
and mills the step to the ear, opening the bore and the hold-down hole.
Upright on the seat: PB06 spots and drills #43 through the apex into the
bore; PB07 is the hand-tap stop.

Work frames (G54), each set in its setup:
- PB01-PB02: X0 the blank's left end, Y0 the fixed jaw (I), Z0 the stacks.
- PB03: X0 I, Y0 the fixed jaw (W), Z0 the faced seat.
- PB04: X0 the seat (the right end, the part to -X), Y0 W, Z0 the stacks.
- PB05: X0 the seat (the left end), Y0 W, Z0 the stacks (I).
- PB06-PB07: X0 I (the right side, the part to -X), Y0 W, Z0 the
  parallels (the seat).

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock; the
arch is profiled climb (G2 round the outside). The
apex hole is tapped by hand (FluidNC cannot rigid-tap; owner, Pedro,
2026-11-17), the T-handle wrench's centre hole on the spring point of the
Fisher tap guide in the 1/2 in R8 collet (owner, Pedro, 2026-11-21: "use
https://littlemachineshop.com/products/tap-guide-fisher?variant=45472915226805
on r8 0.5 collet"), spindle off, the operator jogging Z down to push the
point home. FluidNC refuses jogs while an M0 holds the program
(http://wiki.fluidnc.com/en/features/single_block_mode), so the tap stop is
a file of its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ch_pivot_bracket"
COMMENT = "MHA-CH-08 pivot bracket"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("PB01_west", ("west_side",)),
    ("PB02_width", ("east_side",)),
    ("PB03_seat", (("seat",), ("hold_spot",), ("hold_drill",))),
    (
        "PB04_arch_bore",
        (("arch",), ("bore_spot",), ("bore_drill",), ("bore_open",)),
    ),
    ("PB05_step", ("step",)),
    ("PB06_apex", (("apex_spot",), ("apex_drill",))),
    ("PB07_apex_tap", ("apex_tap",)),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held, and the tap file before its retract
# (the tap guide).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the tap, the pins, the saw and the files are not).
CAM_TOOLS = (
    "em-half",
    "spot",
    "drill-15",
    "drill-d",
    "drill-f",
    "drill-43",
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
# The 4-40 UNC thread's basic major diameter, .1120 in (ASME B1.1): the
# export names the thread, not its sizes.
UNC_4_40_MAJOR_MM = 0.112 * IN
# The tap file's first motion: G53 G0 to machine Z0, the homed top (as the
# magnifying clamp's recipe: FluidNC sets an axis's machine position to its
# homing mpos_mm, default 0, and Z homes up); the owner (Pedro) confirmed
# it, answered in person 2026-11-21 (cnc rulings record): machine Z = 0 is
# the top of travel after homing.
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
# The arch outline's allowed stray of the cutter centre from its offset.
OUTLINE_TOL_MM = 0.01
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


def _inside(value: float, band: list[float]) -> bool:
    """``value`` in ``band``, to the export's 0.001 mm rounding."""
    return band[0] - 1e-3 <= value <= band[1] + 1e-3


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, abs_tol=1e-3)


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
    xy: tuple[float, float], top: float, tip: float, peck: float, clear: float
) -> list[str]:
    """Drill from ``top`` to ``tip`` in pecks of ``peck``, each with a full
    retract to the R plane and a rapid back to just above the last peck (one
    plunge when ``peck`` reaches the tip). Moves to and from the hole run at
    ``clear``."""
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


def _stepover(y: tuple[float, float], max_step: float) -> tuple[int, float]:
    """(passes, stepover) of a zigzag face across ``y`` (low, high): equal
    widths, each at most ``max_step``, reaching ``FACE_OVERHANG_MM`` past
    both edges. Every pass engages at most the stepover: the first one's
    edge runs one stepover inside the high edge, the last one's overhangs."""
    span = y[1] - y[0] + FACE_OVERHANG_MM
    n = math.ceil(span / max_step - 1e-9)
    return n, span / n


def _stations(y: tuple[float, float], radius: float, max_step: float) -> list[float]:
    """Zigzag pass stations across the face ``y`` (low, high), from its high
    side: each pass takes the same width, at most ``max_step``, and together
    the cutter reaches ``FACE_OVERHANG_MM`` past both edges."""
    n, step = _stepover(y, max_step)
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
    from the cutter-centre end ``x[0]`` (beside the part: every plunge, level
    change and return is there) to ``x[1]`` and back, alternating direction.
    With ``x[1]`` inside the part (a step's wall) each stepover there cuts
    along the wall; the passes are even in number, so every level ends back
    at ``x[0]``."""
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
            # Back to the x[0] side, beside the part, for the next level.
            lines.append(f"G1 X{x0:.3f} F{{feed}}")
        if z != levels[-1]:
            lines.append(f"G1 Y{ys[0]:.3f} F{{feed}}")
    return lines + [f"G0 Z{clear:.3f}"]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The bracket's sizes and holes from the export, each checked against
    the frame the recipe assumes: the sides W and E along X centred on the
    origin, the seat at Y0 and the foot top above it, the inboard face I and
    the outboard face along Z with the foot end beyond, the arch round Z over
    the top, the bore along -Z through the ear, the hold-down along -Y
    through the foot and the apex tap along -Y from the apex into the bore."""
    f = features["features"]

    def plane(name: str, axis: str) -> float:
        p = f[name]["plane"]
        if p["axis"] != axis:
            raise ValueError(f"{name}: expected a plane normal to {axis}")
        return float(p["value"])

    west, east = plane("west_side", "x"), plane("east_side", "x")
    width = east - west
    if not _close(width, f["east_side"]["width_nominal"]) or not _close(west, -east):
        raise ValueError(f"W to E {width:.4f} is not the width, centred on X0")
    seat, foot_top = plane("seat", "y"), plane("foot_top", "y")
    if seat != 0.0 or not _close(foot_top - seat, f["foot_top"]["height_nominal"]):
        raise ValueError("the seat is not Y0 or the foot top not its height above it")
    inboard = plane("inboard_face", "z")
    outboard = plane("outboard_face", "z")
    foot_end = plane("foot_end", "z")
    ear = outboard - inboard
    length = foot_end - inboard
    if not _close(ear, f["outboard_face"]["thickness_nominal"]):
        raise ValueError(f"I to the outboard face {ear:.4f} is not the ear's thickness")
    if not _close(length, f["foot_end"]["length_nominal"]):
        raise ValueError(f"I to the foot end {length:.4f} is not the length")
    arch = f["arch"]
    centre, radius = arch["center"], arch["radius_nominal"]
    if (
        arch["axis"] != [0.0, 0.0, 1.0]
        or not _close(centre[0], 0.0)
        or not _close(2 * radius, width)
        or not _close(centre[1] + radius, arch["overall_height_nominal"])
    ):
        raise ValueError("arch: expected a half-round about Z over the full width")
    height = centre[1] + radius
    bore = f["bore"]
    if (
        bore["axis"] != [0.0, 0.0, -1.0]
        or not _close(bore["at"][2], outboard)
        or not _close(bore["at"][0], 0.0)
        or not bore.get("thru")
    ):
        raise ValueError(
            "bore: expected through the ear along -Z from the outboard face"
        )
    hold = f["hold_down"]
    if (
        hold["axis"] != [0.0, -1.0, 0.0]
        or not _close(hold["at"][1], foot_top)
        or not _close(hold["at"][0], 0.0)
        or not hold.get("thru")
        or not outboard < hold["at"][2] < foot_end
    ):
        raise ValueError("hold_down: expected through the foot along -Y from its top")
    tap = f["apex_tap"]
    if (
        tap["axis"] != [0.0, -1.0, 0.0]
        or not _close(tap["at"][1], height)
        or not _close(tap["at"][0], 0.0)
        or tap["into"] != "bore"
        or tap["thread"] != "#4-40 UNC-2B"
        or not inboard < tap["at"][2] < outboard
    ):
        raise ValueError(
            "apex_tap: expected a 4-40 along -Y from the apex into the bore"
        )
    return {
        "west": west,
        "width": width,
        "foot_top": foot_top,
        "inboard": inboard,
        "ear": ear,
        "length": length,
        "arch_centre": centre,
        "radius": radius,
        "height": height,
        "bore": bore,
        "hold": hold,
        "tap": tap,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    width, ear, length, height = g["width"], g["ear"], g["length"], g["height"]
    west, inboard, foot_top = g["west"], g["inboard"], g["foot_top"]
    radius = g["radius"]
    bore_y = g["bore"]["at"][1]
    bore_dia = g["bore"]["dia"]

    # The blank: the square bar's section, sawn to length along the height.
    section = p["blank_section_mm"]
    _agree(plan, "blank_section_mm", p["blank_section_in"] * IN)
    blank_min, blank_max = p["blank_length_min_in"] * IN, p["blank_length_max_in"] * IN
    _agree(plan, "blank_length_min_mm", blank_min)
    _agree(plan, "blank_length_max_mm", blank_max)
    seat_skim, west_skim = p["seat_skim_mm"], p["west_skim_mm"]
    top_max = blank_max - seat_skim
    _agree(plan, "upright_top_max_mm", top_max)
    if blank_min - seat_skim <= height:
        raise ValueError(
            f"the shortest blank less the seat skim, {blank_min - seat_skim:.3f}, is not over the height {height:.3f}"
        )
    west_level = section - west_skim
    if west_level <= width or section <= length:
        raise ValueError(
            "the section leaves nothing to face to the width or the length"
        )

    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    d15 = _shop_tool(plan, shop, "drill-15")["diameter_mm"]
    dd = _shop_tool(plan, shop, "drill-d")["diameter_mm"]
    df = _shop_tool(plan, shop, "drill-f")["diameter_mm"]
    d43 = _shop_tool(plan, shop, "drill-43")["diameter_mm"]
    tap_drill = _shop_tool(plan, shop, "tap-4-40")["tap_drill_mm"]
    r = em / 2
    hold_band, tap_band = g["hold"]["dia"], g["tap"]["dia"]
    if not _inside(d15, hold_band):
        raise ValueError(f"#15 Ø{d15} is outside the hold-down's band {hold_band}")
    if not _inside(df, bore_dia):
        raise ValueError(f"F Ø{df} is outside the bore's band {bore_dia}")
    if not dd < df:
        raise ValueError(f"D Ø{dd} is not under the F drill Ø{df}")
    if not _inside(d43, tap_band) or not _close(d43, tap_drill):
        raise ValueError(
            f"#43 Ø{d43} is not the 4-40 tap's drill in the band {tap_band}"
        )

    # The faces W, E and the seat run the measured face setting; the arch
    # and PB05 (the foot end, the step and its full-depth wall pass, one
    # operation) stay on the chart's: the arch's finish and the wall pass
    # cut deeper than any measured pass. Each face cut declares its true
    # stepover, the most any of its passes engages (posted: face_passes),
    # and its true depth.
    face_cap = p["face_stepover_max_mm"]
    step_max = p["step_stepover_max_mm"]
    face_cuts = {
        "west side": "lying_stepover_mm",
        "width": "lying_stepover_mm",
        "seat": "seat_stepover_mm",
    }
    chart_cuts = ("foot end", "step", "arch rough", "arch finish", "step wall")
    face_rpm, face_feed = _setting(plan, shop, "west side")
    em_rpm, em_feed = _setting(plan, shop, "step")
    for name in (*face_cuts, *chart_cuts):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), em, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' cutter Ø{_cut(plan, name, 'cutter_dia_mm')}, the end mill is Ø{em}"
            )
    for names, first, speeds in (
        (face_cuts, "west side", (face_rpm, face_feed)),
        (chart_cuts, "step", (em_rpm, em_feed)),
    ):
        for name in names:
            if _setting(plan, shop, name) != speeds:
                raise ValueError(f"'{name}' runs at another setting than '{first}'")
    for name, key in (
        *face_cuts.items(),
        ("foot end", "step_stepover_max_mm"),
        ("step", "step_stepover_max_mm"),
    ):
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), p[key], abs_tol=1e-6):
            raise ValueError(f"'{name}' radial_woc_mm is not process.{key}")
    level_max = p["face_step_max_mm"]
    width_levels = _levels(west_level, width, level_max)
    _agree(plan, "width_level_mm", (west_level - width) / len(width_levels))
    for name, doc in (
        ("west side", west_skim),
        ("seat", seat_skim),
        ("width", p["width_level_mm"]),
        ("foot end", level_max),
        ("step", p["step_level_mm"]),
    ):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), doc, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not its skim or level")
    if west_skim > level_max + 1e-9 or section - length > level_max + 1e-9:
        raise ValueError("the W skim or the foot end's facing is over one level")
    step_levels = _levels(length, ear, level_max)
    _agree(plan, "step_level_mm", (length - ear) / len(step_levels))

    # Arch: rough levels finish_stock off the radius, then the full-depth
    # finish on it; through the ear and arch_past_mm into the waste.
    stock_a = p["arch_finish_stock_mm"]
    arch_depth = ear + p["arch_past_mm"]
    _agree(plan, "arch_depth_mm", arch_depth)
    rough_levels = _levels(section, section - arch_depth, p["arch_rough_level_mm"])
    _agree(plan, "arch_rough_level_mm", arch_depth / len(rough_levels))
    corner = math.hypot(width / 2, top_max - g["arch_centre"][1])
    rough_woc = corner - radius - stock_a
    _agree(plan, "arch_rough_woc_mm", rough_woc)
    if corner > radius + stock_a + 2 * r:
        raise ValueError("the rough arch pass leaves the longest blank's corners uncut")
    for name, axial, woc in (
        ("arch rough", p["arch_rough_level_mm"], p["arch_rough_woc_mm"]),
        ("arch finish", arch_depth, stock_a),
    ):
        if not (
            math.isclose(_cut(plan, name, "axial_doc_mm"), axial, abs_tol=1e-6)
            and math.isclose(_cut(plan, name, "radial_woc_mm"), woc, abs_tol=1e-6)
        ):
            raise ValueError(f"'{name}' depth or width is not the plan's")

    # Holes: spots under each drill (no chamfer at the mouth).
    spot_rpm, spot_feed = _setting(plan, shop, "hold spot")
    spots = {}
    for name, key, drill in (
        ("hold spot", "hold_spot_dia_mm", d15),
        ("bore spot", "bore_spot_dia_mm", dd),
        ("apex spot", "apex_spot_dia_mm", d43),
    ):
        if _setting(plan, shop, name) != (spot_rpm, spot_feed):
            raise ValueError(f"'{name}' runs at another speed than 'hold spot'")
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), p[key], abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not process.{key}")
        if p[key] >= drill:
            raise ValueError(
                f"'{name}' is not under its drill: it would chamfer the hole"
            )
        spots[name] = _spot_depth(p[key])
    for name, dia in (
        ("hold drill", d15),
        ("bore drill", dd),
        ("bore open", df),
        ("apex drill", d43),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not its tool's Ø{dia}")
    hold_rpm, hold_feed = _setting(plan, shop, "hold drill")
    drill_rpm, drill_feed = _setting(plan, shop, "bore drill")
    open_rpm, open_feed = _setting(plan, shop, "bore open")
    apex_rpm, apex_feed = _setting(plan, shop, "apex drill")

    # Hold-down: from the seat, full diameter hold_drill_past_mm past the
    # foot top; its point in the shortest blank above the parallels.
    hold_full = -(foot_top + p["hold_drill_past_mm"])
    hold_tip = hold_full - _point(d15)
    _agree(plan, "hold_tip_height_mm", blank_min - seat_skim + hold_tip)
    # Bore: from I down through the ear; the D's and the F's full diameters
    # bore_drill_past_mm past the outboard face's plane.
    out_z = section - ear
    bore_full = out_z - p["bore_drill_past_mm"]
    bore_tip = bore_full - _point(dd)
    open_tip = bore_full - _point(df)
    _agree(plan, "bore_tip_height_mm", bore_tip)
    _agree(plan, "bore_open_tip_height_mm", open_tip)
    arch_bottom = section - arch_depth
    # Apex: the #43 full diameter apex_drill_past_mm past the bore's wall
    # where the drill's edge meets it; the tap's lead past the wall at the
    # thread's major diameter and short of the far wall.
    bore_r = bore_dia[0] / 2
    wall = bore_y + math.sqrt(bore_r**2 - (d43 / 2) ** 2)
    apex_full = wall - p["apex_drill_past_mm"]
    apex_tip = apex_full - _point(d43)
    _agree(plan, "apex_tip_height_mm", apex_tip)
    if apex_tip <= bore_y - bore_r:
        raise ValueError("the #43's point reaches the bore's far wall")
    major = UNC_4_40_MAJOR_MM
    major_wall = bore_y + math.sqrt(bore_r**2 - (major / 2) ** 2)
    _agree(plan, "tap_reach_min_mm", height - major_wall + p["plug_tap_lead_mm"])
    _agree(plan, "tap_reach_max_mm", height - (bore_y - bore_r) - 1.0)
    for op, (key, peck) in (
        (_op_with_cut(plan, "hold drill")[0], ("{{cad.foot_top_height_mm}}", "none")),
        (_op_with_cut(plan, "bore drill")[0], (ear + p["bore_drill_past_mm"], "none")),
        (
            _op_with_cut(plan, "apex drill")[0],
            (
                "{{cad.apex_tap_into_axis_mm}}",
                {"step_mm": p["apex_peck_mm"], "retract": "full"},
            ),
        ),
    ):
        if op["hole_depth_mm"] != key or op["peck"] != peck:
            raise ValueError(f"{op['tool']}: hole_depth_mm or peck is not the recipe's")

    # Vise: upright on the 1 in pair, lying on the stacked risers.
    upright_grip = p["vise_jaw_height_mm"] - p["parallel_height_mm"]
    lying_grip = p["vise_jaw_height_mm"] - p["riser_height_mm"]
    _agree(plan, "upright_grip_mm", upright_grip)
    _agree(plan, "lying_grip_mm", lying_grip)
    if arch_bottom <= lying_grip or ear <= lying_grip:
        raise ValueError("the arch or the step's floor reaches the jaw tops")
    # The 1/2 in end mill's stick-out is the measured settings' assembly
    # (half_mill_projection_mm): at each program's deepest end-mill cut its
    # collet nose stays CLEAR_MM over that program's stock top.
    projection = p["half_mill_projection_mm"]
    for what, top, deepest in (
        ("PB01", section, west_level),
        ("PB02", west_level, width),
        ("PB03", seat_skim, 0.0),
        ("PB04", section, arch_bottom),
        ("PB05", section, ear),
    ):
        if deepest + projection < top + CLEAR_MM:
            raise ValueError(
                f"{what}: the collet nose {projection:g} out comes to "
                f"{top - deepest - projection:.3f} above the stock top"
            )
    t = p["parallel_thickness_mm"]
    jaw_w = p["vise_jaw_width_mm"]
    for key, along in (
        ("vise_lying_inset_mm", blank_max),
        ("vise_upright_inset_mm", section),
        ("vise_seat_inset_mm", length),
    ):
        _agree(plan, key, -(jaw_w - along) / 2)
    # The tap stack's ceiling: spindle-to-table maximum less the tool-change
    # clearance, the vise bed, the parallels, the bracket and the collet's
    # gauge, rounded down to .01 in.
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["parallel_height_mm"]
        - height
        - p["r8_collet_gauge_mm"]
    )
    _agree(plan, "tap_stack_max_mm", math.floor(stack / 0.254 + 1e-9) * 0.254)

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)). Raw faces: W's skim
    # beyond W, E the rest of the section; I is the bar's face, its opposite
    # a section away; the seat's skim below Y0.
    raw_east = west - west_skim + section
    raw_foot = inboard + section
    frames = {
        "west": _frame([raw_east, -seat_skim, inboard], [0, 0, -1], [-1, 0, 0]),
        "width": _frame([west, top_max, inboard], [0, 0, -1], [1, 0, 0]),
        "seat": _frame([west, 0.0, inboard], [-1, 0, 0], [0, -1, 0]),
        "arch": _frame([west, 0.0, raw_foot], [-1, 0, 0], [0, 0, -1]),
        "step": _frame([west, 0.0, inboard], [-1, 0, 0], [0, 0, 1]),
        "apex": _frame([west, 0.0, inboard], [-1, 0, 0], [0, 1, 0]),
    }
    stocks = {
        "west": ((0.0, blank_max), (-section, 0.0), (0.0, section)),
        "width": ((0.0, blank_max), (-section, 0.0), (0.0, west_level)),
        "seat": ((0.0, section), (-width, 0.0), (-top_max, seat_skim)),
        "arch": ((-top_max, 0.0), (-width, 0.0), (0.0, section)),
        "step": ((0.0, top_max), (-width, 0.0), (0.0, section)),
        "apex": ((-length, 0.0), (-width, 0.0), (0.0, height)),
    }

    def xy(key: str, point: list[float]) -> list[float]:
        x, y, _z = _to(frames[key], point)
        return [_r(x), _r(y)]

    hold_xy = xy("seat", g["hold"]["at"])
    bore_xy = xy("arch", g["bore"]["at"])
    arch_c = xy("arch", g["arch_centre"])
    tap_xy = xy("apex", g["tap"]["at"])
    # Each frame puts the part where its stock says.
    for key, point, want in (
        ("seat", [west, 0.0, inboard], [0.0, 0.0, 0.0]),
        ("arch", [west, 0.0, inboard], [0.0, 0.0, section]),
        ("step", [-west, foot_top, inboard + length], [foot_top, -width, length]),
        ("apex", [west, height, inboard], [0.0, 0.0, height]),
    ):
        if not all(_close(a, b) for a, b in zip(_to(frames[key], point), want)):
            raise ValueError(
                f"{key}: the frame does not put the part where its stock is"
            )
    holes = {"hold": [hold_xy], "bore": [bore_xy], "apex": [tap_xy]}

    def tool(key: str, rpm: float, feed: float, **extra: Any) -> dict[str, Any]:
        return {"tool": key, "rpm": rpm, "feed": feed, "plunge": feed, **extra}

    em_face = tool("em-half", face_rpm, face_feed, dia=em, shape="endmill", flutes=3)
    em_tool = tool("em-half", em_rpm, em_feed, dia=em, shape="endmill", flutes=3)
    spot_tool = tool(
        "spot",
        spot_rpm,
        spot_feed,
        dia=CENTRE_DRILL["body_mm"],
        shape="drill",
        tip_angle=CENTRE_DRILL["point_deg"],
    )

    def drill_tool(key: str, dia: float, rpm: float, feed: float) -> dict[str, Any]:
        return tool(key, rpm, feed, dia=dia, shape="drill", tip_angle=DRILL_POINT_DEG)

    def run(x: tuple[float, float]) -> tuple[float, float]:
        return (x[0] - r - APPROACH_MM, x[1] + r + APPROACH_MM)

    # The faces at the measured cap; PB05's foot end and step at their own
    # (unchanged, chart) stepover.
    lying_ys = _stations((-section, 0.0), r, face_cap)
    seat_ys = _stations((-width, 0.0), r, face_cap)
    _agree(plan, "lying_stepover_mm", _stepover((-section, 0.0), face_cap)[1])
    _agree(plan, "seat_stepover_mm", _stepover((-width, 0.0), face_cap)[1])
    width_ys = _stations((-width, 0.0), r, step_max)
    blank_x = run((0.0, blank_max))
    # The step: X passes from beside the far end to the foot top's station
    # (the cutter's edge on it) and back; their stepovers at the wall sweep
    # it between pairs of stations. The facing stations, the last moved onto
    # E's line: the first pair's stepover starts beyond W and the last
    # pair's ends on E, so the stepovers sweep the wall to both edges and
    # leave only scallops between the pairs, which one full-depth wall pass
    # along -Y (climb) takes off.
    wall_x = foot_top + r
    far_x = top_max + r + APPROACH_MM
    step_ys = [*width_ys[:-1], _r(-width)]
    if len(step_ys) % 2:
        raise ValueError("an odd number of step passes ends a level at the wall")
    if step_ys[0] < 0 or step_ys[-2] - r + width > step_max + 1e-9:
        raise ValueError("the step's stations leave W unswept or overload the E pass")
    gap = max(step_ys[k] - step_ys[k + 1] for k in range(1, len(step_ys) - 1, 2))
    scallop = r - math.sqrt(r**2 - (gap / 2) ** 2)
    _agree(plan, "wall_finish_woc_mm", scallop)
    for name, axial, woc in (("step wall", length - ear, p["wall_finish_woc_mm"]),):
        if not (
            math.isclose(_cut(plan, name, "axial_doc_mm"), axial, abs_tol=1e-3)
            and math.isclose(_cut(plan, name, "radial_woc_mm"), woc, abs_tol=1e-6)
        ):
            raise ValueError(f"'{name}' depth or width is not the recipe's")
    wall_y = (_r(r + APPROACH_MM), _r(-width - r - APPROACH_MM))
    step_lines = _step_lines(
        length, section, ear, step_levels, width_ys, step_ys, r, far_x, wall_x, wall_y
    )

    # Arch outline (machine XY of the arch frame, climb: round the outside
    # clockwise), from beside E, round the arch, to beside W; the leads run
    # arch_lead_mm along each side below the tangent points.
    cx, cy = arch_c
    lead = p["arch_lead_mm"]
    elements = [
        {
            "name": "east side",
            "start": [cx + lead, cy - radius],
            "end": [cx, cy - radius],
        },
        {
            "name": "arch, east half",
            "start": [cx, cy - radius],
            "end": [cx - radius, cy],
            "centre": [cx, cy],
        },
        {
            "name": "arch, west half",
            "start": [cx - radius, cy],
            "end": [cx, cy + radius],
            "centre": [cx, cy],
        },
        {
            "name": "west side",
            "start": [cx, cy + radius],
            "end": [cx + lead, cy + radius],
        },
    ]
    for element in elements:
        element["tol"] = OUTLINE_TOL_MM
    passes = [
        {"offset": r + stock_a, "levels": [_r(z) for z in rough_levels]},
        {"offset": r, "levels": [_r(arch_bottom)]},
    ]
    arch_lines: list[str] = []
    for pass_ in passes:
        o = pass_["offset"]
        for z in pass_["levels"]:
            arch_lines += [
                f"G0 Z{_r(section + CLEAR_MM):.3f}",
                f"G0 X{_r(cx + lead):.3f} Y{_r(cy - radius - o):.3f}",
                f"G0 Z{_r(section + SAFE_MM):.3f}",
                f"G1 Z{z:.3f} F{{feed}}",
                f"G1 X{_r(cx):.3f} F{{feed}}",
                f"G2 X{_r(cx - radius - o):.3f} Y{_r(cy):.3f} I0.000 J{_r(radius + o):.3f} F{{feed}}",
                f"G2 X{_r(cx):.3f} Y{_r(cy + radius + o):.3f} I{_r(radius + o):.3f} J0.000 F{{feed}}",
                f"G1 X{_r(cx + lead):.3f} F{{feed}}",
            ]
    arch_lines.append(f"G0 Z{_r(section + CLEAR_MM):.3f}")

    seat_top = seat_skim
    jobs = [
        {
            **em_face,
            "frame": "west",
            "label": "west side",
            "stock": stocks["west"],
            "ops": [
                ["west_side", "skim W", _face([west_level], section, blank_x, lying_ys)]
            ],
        },
        {
            **em_face,
            "frame": "width",
            "label": "east side",
            "stock": stocks["width"],
            "ops": [
                [
                    "east_side",
                    "face E to the width",
                    _face(width_levels, west_level, blank_x, lying_ys),
                ]
            ],
        },
        {
            **em_face,
            "frame": "seat",
            "label": "seat",
            "stock": stocks["seat"],
            "ops": [
                [
                    "seat",
                    "face the seat",
                    _face([0.0], seat_top, run((0.0, section)), seat_ys),
                ]
            ],
        },
        {
            **spot_tool,
            "frame": "seat",
            "label": "hold spot",
            "stock": stocks["seat"],
            "ops": [
                [
                    "hold_spot",
                    "spot the hold-down hole",
                    _spot(hold_xy, 0.0, -spots["hold spot"], CLEAR_MM),
                ]
            ],
        },
        {
            **drill_tool("drill-15", d15, hold_rpm, hold_feed),
            "frame": "seat",
            "label": "hold drill",
            "stock": stocks["seat"],
            "ops": [
                [
                    "hold_drill",
                    "drill the hold-down hole #15",
                    _pecked(hold_xy, 0.0, hold_tip, math.inf, CLEAR_MM),
                ]
            ],
        },
        {
            **em_tool,
            "frame": "arch",
            "label": "arch",
            "stock": stocks["arch"],
            "ops": [["arch", "profile the arch", arch_lines]],
        },
        {
            **spot_tool,
            "frame": "arch",
            "label": "bore spot",
            "stock": stocks["arch"],
            "ops": [
                [
                    "bore_spot",
                    "spot the bore",
                    _spot(
                        bore_xy,
                        section,
                        section - spots["bore spot"],
                        section + CLEAR_MM,
                    ),
                ]
            ],
        },
        {
            **drill_tool("drill-d", dd, drill_rpm, drill_feed),
            "frame": "arch",
            "label": "bore drill",
            "stock": stocks["arch"],
            "ops": [
                [
                    "bore_drill",
                    "drill the bore D",
                    _pecked(bore_xy, section, bore_tip, math.inf, section + CLEAR_MM),
                ]
            ],
        },
        {
            **drill_tool("drill-f", df, open_rpm, open_feed),
            "frame": "arch",
            "label": "bore open",
            "stock": stocks["arch"],
            "ops": [
                [
                    "bore_open",
                    "open the bore with the F drill",
                    _pecked(bore_xy, section, open_tip, math.inf, section + CLEAR_MM),
                ]
            ],
        },
        {
            **em_tool,
            "frame": "step",
            "label": "step",
            "stock": stocks["step"],
            "ops": [["step", "face the foot end, mill the step", step_lines]],
        },
        {
            **spot_tool,
            "frame": "apex",
            "label": "apex spot",
            "stock": stocks["apex"],
            "ops": [
                [
                    "apex_spot",
                    "spot the apex",
                    _spot(
                        tap_xy, height, height - spots["apex spot"], height + CLEAR_MM
                    ),
                ]
            ],
        },
        {
            **drill_tool("drill-43", d43, apex_rpm, apex_feed),
            "frame": "apex",
            "label": "apex drill",
            "stock": stocks["apex"],
            "ops": [
                [
                    "apex_drill",
                    "drill the apex hole #43",
                    _pecked(
                        tap_xy, height, apex_tip, p["apex_peck_mm"], height + CLEAR_MM
                    ),
                ]
            ],
        },
    ]
    manual = {
        "apex_tap": {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": "SPINDLE STAYS OFF. NEXT: 4-40 TAP IN THE APEX HOLE",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{tap_xy[0]:.3f} Y{tap_xy[1]:.3f}",
                "(4-40 TAP IN THE APEX HOLE. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND TO THE NOTED DRO Z, READ WITH THE POINT PUSHED HOME. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": tap_xy,
        }
    }

    # Keep-outs. Upright: the jaws grip W and E from the parallels' top to
    # the jaw top, across the jaw width. Lying: the jaws beside the gripped
    # span from the stacks' top to the jaw top; the stacks under its edges.
    def jaws(
        z_top: float, x: tuple[float, float], y: tuple[float, float]
    ) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - jaw_w / 2, mid + jaw_w / 2)
        return [
            _box("moving jaw", span, (y[0] - JAW_DEPTH_MM, y[0]), z_top),
            _box("fixed jaw", span, (y[1], y[1] + JAW_DEPTH_MM), z_top),
        ]

    def parallels(
        z_top: float, x: tuple[float, float], y: tuple[float, float]
    ) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - PARALLEL_LENGTH_MM / 2, mid + PARALLEL_LENGTH_MM / 2)
        return [
            _box("moving-jaw parallels", span, (y[0], y[0] + t), z_top),
            _box("fixed-jaw parallels", span, (y[1] - t, y[1]), z_top),
        ]

    lying = (0.0, blank_max)
    keep = {
        "west": jaws(lying_grip, lying, (-section, 0.0)),
        "width": jaws(lying_grip, lying, (-section, 0.0)),
        "seat": jaws(
            upright_grip - (blank_min - seat_skim), (0.0, section), (-width, 0.0)
        )
        + parallels(-(blank_min - seat_skim), (0.0, section), (-width, 0.0)),
        "arch": jaws(lying_grip, (-blank_max, 0.0), (-width, 0.0))
        + parallels(0.0, (-blank_max, 0.0), (-width, 0.0)),
        "step": jaws(lying_grip, lying, (-width, 0.0))
        + parallels(0.0, lying, (-width, 0.0)),
        "apex": jaws(upright_grip, (-length, 0.0), (-width, 0.0))
        + parallels(0.0, (-length, 0.0), (-width, 0.0)),
    }

    tn = numbers
    expect: list[list[Any]] = []

    def face_checks(levels, top, y, span, frame, engagement) -> list[list[Any]]:
        return [
            ["rapids_clear", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            *[
                [
                    "face_passes",
                    {
                        "z": _r(z),
                        "y": list(y),
                        "max_engagement": engagement,
                        "radius": r,
                        "span": span,
                        "overhang": FACE_OVERHANG_MM,
                    },
                ]
                for z in levels
            ],
            ["keep_out", {"radius": r, "boxes": keep[frame]}],
        ]

    def hole_checks(key, frame, top, bottom, radius) -> list[list[Any]]:
        return [
            ["holes", {"centres": holes[key], "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": top, "open_holes": holes[key]}],
            ["vertical_below_top", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": radius, "boxes": keep[frame]}],
        ]

    for name, levels, top in (
        ("PB01_west", [west_level], section),
        ("PB02_width", width_levels, west_level),
    ):
        frame = "west" if name == "PB01_west" else "width"
        engagement = p["lying_stepover_mm"]
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": top, "tools": [tn["em-half"]], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[face_rpm]]}],
            [name, "pauses", {"z_top": top, "count": 0}],
            [name, "depth", {"z_min": _r(levels[-1])}],
            *[
                [name, check, kwargs]
                for check, kwargs in face_checks(
                    levels, top, (-section, 0.0), blank_max, frame, engagement
                )
            ],
        ]

    name = "PB03_seat"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": seat_top,
                "tools": [tn["em-half"], tn["spot"], tn["drill-15"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[face_rpm], [spot_rpm], [hold_rpm]]}],
        [name, "pauses", {"z_top": seat_top, "count": 0}],
        [name, "depth", {"z_min": _r(hold_tip)}],
    ]
    for k, checks in enumerate(
        (
            [
                ["depth", {"z_min": 0.0}],
                *face_checks(
                    [0.0],
                    seat_top,
                    (-width, 0.0),
                    section,
                    "seat",
                    p["seat_stepover_mm"],
                ),
            ],
            hole_checks(
                "hold", "seat", 0.0, -spots["hold spot"], CENTRE_DRILL["body_mm"] / 2
            ),
            hole_checks("hold", "seat", 0.0, hold_tip, d15 / 2),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    name = "PB04_arch_bore"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": section,
                "tools": [tn["em-half"], tn["spot"], tn["drill-d"], tn["drill-f"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[em_rpm], [spot_rpm], [drill_rpm], [open_rpm]]}],
        [name, "pauses", {"z_top": section, "count": 0}],
        [name, "depth", {"z_min": _r(min(bore_tip, open_tip))}],
    ]
    for k, checks in enumerate(
        (
            [
                ["depth", {"z_min": _r(arch_bottom)}],
                [
                    "outline",
                    {
                        "elements": elements,
                        "passes": passes,
                        "z_top": section,
                        # Clockwise round the arch, the part on the right:
                        # climb, as the module docstring says (ball screws).
                        "cut": "climb",
                        "part": "right",
                    },
                ],
                ["rapids_clear", {"z_top": section}],
                ["air_feed", {"z_top": section}],
                ["keep_out", {"radius": r, "boxes": keep["arch"]}],
            ],
            hole_checks(
                "bore",
                "arch",
                section,
                section - spots["bore spot"],
                CENTRE_DRILL["body_mm"] / 2,
            ),
            hole_checks("bore", "arch", section, bore_tip, dd / 2),
            hole_checks("bore", "arch", section, open_tip, df / 2),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    name = "PB05_step"
    floor_points = [
        [_r(x), _r(y)]
        for x in (foot_top + 0.1, (foot_top + top_max) / 2, top_max)
        for y in (-width, -width / 2, 0.0)
    ]
    expect += [
        [
            name,
            "tool_changes",
            {"z_top": section, "tools": [tn["em-half"]], "loads_first": True},
        ],
        [name, "spindle", {"rpm": [[em_rpm]]}],
        [name, "pauses", {"z_top": section, "count": 0}],
        [name, "depth", {"z_min": _r(ear)}],
        *[
            [name, check, kwargs]
            for check, kwargs in face_checks(
                [length, *step_levels],
                section,
                (-width, 0.0),
                top_max - foot_top - r,
                "step",
                step_max,
            )
        ],
        [name, "cleared", {"points": floor_points, "radius": r, "z": _r(ear)}],
        [
            name,
            "side_passes",
            {
                "axis": "X",
                "final": _r(wall_x),
                "raw": _r(wall_x + p["wall_finish_woc_mm"]),
                "max_step": p["wall_finish_woc_mm"],
                "direction": -1.0,
                "span": width,
                "below_z": length,
            },
        ],
        # What the wall pass really meets: the scallops only, climb, E's and
        # W's edges included (stations alone cannot show the edges).
        [
            name,
            "engagement",
            {
                "stock": stocks["step"],
                "radius": r,
                "max_radial": p["wall_finish_woc_mm"],
                "z": _r(ear),
                "window": [[_r(wall_x), _r(wall_x)], [wall_y[1], wall_y[0]]],
                "min_length": width,
                "cut": "climb",
            },
        ],
    ]

    name = "PB06_apex"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": height,
                "tools": [tn["spot"], tn["drill-43"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[spot_rpm], [apex_rpm]]}],
        [name, "pauses", {"z_top": height, "count": 0}],
        [name, "depth", {"z_min": _r(apex_tip)}],
    ]
    for k, checks in enumerate(
        (
            hole_checks(
                "apex",
                "apex",
                height,
                height - spots["apex spot"],
                CENTRE_DRILL["body_mm"] / 2,
            ),
            hole_checks("apex", "apex", height, apex_tip, d43 / 2),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    name = "PB07_apex_tap"
    expect += [
        [
            name,
            "tap_stop",
            {"tool": tn["tap-guide"], "at": tap_xy, "machine_top": MACHINE_Z_TOP_MM},
        ],
        [name, "air_feed", {"z_top": height}],
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


def _step_lines(
    length: float,
    section: float,
    ear: float,
    levels: list[float],
    ys: list[float],
    step_ys: list[float],
    radius: float,
    far_x: float,
    wall_x: float,
    wall_y: tuple[float, float],
) -> list[str]:
    """PB05: the foot end faced at ``length`` across the whole part (X passes
    from beside the seat at the facing stations ``ys``), then the step's
    ``levels``, each in X passes at ``step_ys`` from beside the far end to the
    wall station and back, then one full-depth wall pass from beside W along
    -Y (climb: the wall on the cutter's right) to beside E. Every plunge and
    level change is beside the part; the moves between them are G0 above the
    raw stock top ``section``."""
    foot = _face([length], section, (-radius - APPROACH_MM, far_x), ys)
    step = _face(levels, section, (far_x, wall_x), step_ys)
    clear = _r(section + CLEAR_MM)
    return [
        *foot,
        *step[1:],
        f"G0 X{_r(wall_x):.3f} Y{wall_y[0]:.3f}",
        f"G0 Z{_r(section + SAFE_MM):.3f}",
        f"G1 Z{_r(ear):.3f} F{{feed}}",
        f"G1 Y{wall_y[1]:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    return [(program, check, kwargs) for program, check, kwargs in ctx["expect"]]


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job per
    section; returns {"ops": {operation key: operation or manual section}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(
            doc, f"Pivot bracket {key}", ctx["step"], frame["origin"], frame["axes"]
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
