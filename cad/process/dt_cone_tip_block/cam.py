"""FreeCAD CAM recipe for MHA-DT-21, the cone tip block.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The block's sizes come
from the feature export (its height, width and depth bands; the 1/4-28
adjuster with its countersinks; the #4-40 pinch tap and its #30 clearance; the
#4-40 foot tap; the slit); the blank, the skims, levels, passes, spots, pecks,
the stacks and the saw's arbor (the owned R8 stepped arbor's recorded sizes
and the two bounds measured at its mounting) from ``plan.toml`` ``[parameters]``
and ``milling_cuts``; the end mill's diameter, speed and feed from the shop
(``shop/``), the hole and saw settings from the plan's authored operations.
Every path is written here (``rt.custom``): straight lines and circles a
recipe can state exactly. Typed here, because neither record carries them:
the #2 centre drill's catalogue geometry (it sets the spot depth), the twist
drills' 118° point, the chamfer mill's 90°, the plug and bottoming taps'
chamfer lengths in threads, the machine's Z top for the tap files' retract,
the approach, safe and clearance heights, the face overhang and the vise
jaws' depth (keep-out shapes only).

Route (plan text in ``plan.toml``): a strip about .80 wide sawn off the end
of the 1/2 x 2-1/4 in 1018 flat, the bar's 2-1/4 width the block's height.
DT01 (lying, gripped on the bar's edges) faces S to the depth off the
cold-finished N; DT02 (on edge, gripped on N and S) skims E; DT03 (upright)
skims the top; DT04 (upright, turned over) faces the seat to the height,
spots and drills the #43 foot hole from it, DT05 brings the tap guide over
it. DT06 (on edge, E down) faces W to the width, spots and drills the #43
pinch hole through both halves (the block's two sides of the slit), opens
the W half #30 to the slot; DT07 (W down) brings the tap guide over it from
E. DT08 (lying, N up) spots, drills #3
through and countersinks the adjuster, its height from the seat the
measured MHA-DT-05 axis height H (a G54 X shift the traveler sets); DT09
brings the tap guide over it; DT10 (S up) countersinks its other end.
DT11 (on edge, E down, the top end past the right jaw side) saws the slit
into the adjuster with the owned 2-3/4 x .064 slitting saw on the owned R8
stepped arbor: a light first pass, a stop to read the friction drive's
marker lines, then the rest.

Work frames (G54), each set in its setup:
- DT01: X0 the strip's E-marked sawn face (left), Y0 the fixed jaw (the
  bar edge toward the seat), Z0 the stacks' top (N).
- DT02: X0 the unmarked bar edge, the top to be (left; the seat edge to
  the right), Y0 the fixed jaw (N), Z0 E skimmed.
- DT03: X0 W (left), Y0 the fixed jaw (N), Z0 the top skimmed.
- DT04/DT05: X0 E (left), Y0 the fixed jaw (N), Z0 the parallels' top (the
  top).
- DT06: X0 the seat (left), Y0 the fixed jaw (N), Z0 the stacks' top (E).
- DT07: X0 the seat (right, the block to -X), Y0 the fixed jaw (N); no Z0.
- DT08/DT09: X0 the seat (left) shifted by H - 1.500, Y0 the fixed jaw (E),
  Z0 the nominal depth below N (touched off on N, so the countersink is cut
  from the face whatever the block's depth).
- DT10: X0 the seat (right, the block to -X) shifted by H - 1.500, Y0 the
  fixed jaw (E), Z0 the nominal depth below S (touched off on S).
- DT11: X0 the top (right, the block to -X), Y0 the fixed jaw (N), Z0 the
  stacks' top (E); Z is the saw's lower face.

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock. The
countersinks are circles of the chamfer mill inside the hole (climb, G3).
The saw's passes run one way, conventional for an M3 saw right of the block
(+Y: a climb cut would let the teeth grab and slip the arbor's friction
drive), each from beside the block to past it. The holes are tapped by hand
(FluidNC cannot rigid-tap; owner, Pedro, 2026-11-17), the T-handle wrench's
centre hole on the spring point of the Fisher tap guide in the 1/2 in R8
collet (owner, Pedro, 2026-11-21: "use
https://littlemachineshop.com/products/tap-guide-fisher?variant=45472915226805
on r8 0.5 collet"), spindle off, the operator jogging Z down to push the
point home. FluidNC, like Grbl, refuses jogs while an M0 holds the program
(FluidNC wiki, "Single Block Mode",
http://wiki.fluidnc.com/en/features/single_block_mode), so each tap stop is
a file of its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_cone_tip_block"
COMMENT = "MHA-DT-21 cone tip block"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes. A literal: dodo.py reads it with ast.literal_eval.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("DT01_depth", ("depth_face",)),
    ("DT02_east", ("east_face",)),
    ("DT03_top", ("top_face",)),
    ("DT04_seat", (("seat_face",), ("foot_spot",), ("foot_drill",))),
    ("DT05_foot_tap", ("tap_foot",)),
    (
        "DT06_west",
        (("west_face",), ("pinch_spot",), ("pinch_drill",), ("pinch_clearance",)),
    ),
    ("DT07_pinch_tap", ("tap_pinch",)),
    ("DT08_adjuster", (("adjuster_spot",), ("adjuster_drill",), ("north_csk",))),
    ("DT09_adjuster_tap", ("tap_adjuster",)),
    ("DT10_south_csk", ("south_csk",)),
    ("DT11_slit", (("slit_first",), ("slit_check",), ("slit",))),
)
# The end mill, drill and chamfer programs and the tap stops load their own
# first tool (M6, the tool setter); the saw program runs on the saw already
# on its arbor and touched off, which the tool setter cannot measure.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS if name != "DT11_slit")
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the cutoff saw, the taps and the files are not).
CAM_TOOLS = (
    "em-half",
    "spot",
    "drill-43",
    "drill-30",
    "drill-3",
    "chamfer",
    "tap-guide",
    "slit-saw",
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
# point.
CHAMFER_DEG = 90.0
# Hand taps' chamfers, in threads (ASME B94.9): plug 3-5, bottoming 1-2.
PLUG_CHAMFER_THREADS = (3.0, 5.0)
BOTTOMING_CHAMFER_THREADS = (1.0, 2.0)
# A standard #4 hand tap's thread length, 9/16 in, and a 1/4 in one's, 1 in
# (ASME B94.9): the shank stays out of the hole.
TAP_THREAD_LENGTH_MM = {"#4": 0.5625 * IN, "1/4": 1.0 * IN}
# A #4 hand tap's shank, .141 in (ASME B94.9): it cannot follow into a #30.
TAP_4_SHANK_MM = 0.141 * IN
# The Fisher tap guide's overall length, 3 1/8 in (its sellers' size,
# cad/config/shop-equipment/ tools.tap-guide-fisher): the most it stands
# below the collet face, taken off the tap stack for the tap's own reach.
TAP_GUIDE_OAL_MM = 3.125 * IN
# A tap file's first motion: G53 G0 to machine Z0, the homed top. FluidNC
# sets an axis's machine position to its homing mpos_mm (default 0) after
# homing, and Z homes up; the owner (Pedro) confirmed it, answered in person
# 2026-11-21 (cnc rulings record): machine Z = 0 is the top of travel after
# homing.
MACHINE_Z_TOP_MM = 0.0
# Face passes start and finish with the cutter this far clear of the stock.
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
# The saw's arbor (the owned R8 stepped arbor: its body above the saw, its
# cap below) clears the block's top end by at least this at the slit's full
# depth: the reach past the arbor is (the saw - the arbor) / 2 less this.
ARBOR_CLEAR_MM = 1.0
# The spindle nose stands at least this far over everything in the vise.
NOSE_CLEAR_MM = 1.0
# The saw is touched off with its rim this far in over the top end.
TOUCH_IN_MM = 3.0
# The slit's printed ceiling less this is the most the miked blade and its
# axial runout may add up to.
KERF_ALLOWANCE_MM = 0.002 * IN
# The saw's side runout is read this far in from its teeth; the rim swings
# wider by the saw's radius over the radius less this.
RUNOUT_INSET_MM = IN / 8
# Machinery's Handbook milling power for the saw's passes, the figures
# prechips' milling screen takes for milling_material steel_1018: unit power
# (hp per in³/min, plain carbon steel 160-180 HB), the feed factor at .001
# in/tooth and the tool-wear factor (as the CH-01 and CH-03 recipes).
SAW_UNIT_POWER_HP = 0.78
SAW_FEED_FACTOR = 1.60
SAW_FEED_FACTOR_AT_MM = 0.0254
SAW_WEAR_FACTOR = 1.10
WATTS_PER_HP = 745.7
# The friction drive's torque is recomputed to this (N·m).
DRIVE_TOL_NM = 0.05
# A saw pass may take this share of the friction drive's torque at most: the
# drive's friction and preload are a table's, not measured, and the saw runs
# oiled (friction .10 under a preload a quarter low leaves about half).
DRIVE_RESERVE = 2.0
# The arbor's length from the spindle nose is rounded up to this (.1 in).
ARBOR_LENGTH_STEP_MM = 0.1 * IN
# How far the arbor drops before its R8 shank is free of the spindle: an R8
# collet's overall length, 4.000 in (Logan Actuator Co., "Collet
# Specifications", R8 row, Overall Length B 4.000,
# https://www.loganact.com/tips/collet.htm, read 2026-11-24). The arbor's own
# shank length is not on its record: with this figure the check below asks
# for 171 mm of the 303 mm under the nose, so a shank up to 5 in longer than
# the collet's still passes.
R8_SHANK_MM = 4.0 * IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# The #43 drill against the tap drill's printed band: the shop records the
# drill's nominal .089 in (2.2606), the band's floor is that size rounded to
# 2.261; anything closer than this is the same size.
SIZE_TOL_MM = 0.001


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


def _mid(band: list[float]) -> float:
    return (band[0] + band[1]) / 2


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


def _det(rows: list[list[float]]) -> float:
    (a, b, c), (d, e, f), (g, h, i) = rows
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def _to(frame: dict[str, Any], p: list[float]) -> list[float]:
    """Model point ``p`` in the setup frame."""
    d = [p[i] - frame["origin"][i] for i in range(3)]
    return [sum(axis[i] * d[i] for i in range(3)) for axis in frame["axes"]]


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


def _countersink(
    xy: tuple[float, float], top: float, tip: float, orbit: float, clear: float
) -> list[str]:
    """The chamfer mill's point fed down the hole's axis to ``tip`` (its cone
    inside the hole: nothing cut), out to ``orbit`` and once round it climb
    (G3), back to the axis and out: a 90° countersink of radius ``orbit``
    plus the cone's radius at the face."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    x, y = xy
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{_r(x):.3f} Y{_r(y):.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(tip):.3f} F{{plunge}}",
        f"G1 X{_r(x + orbit):.3f} F{{feed}}",
        f"G3 X{_r(x + orbit):.3f} Y{_r(y):.3f} I{_r(-orbit):.3f} J0.000 F{{feed}}",
        f"G1 X{_r(x):.3f} F{{feed}}",
        f"G1 Z{r_plane:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def _saw(
    xs: list[float], z: float, y: tuple[float, float], top: float, clear: float
) -> list[str]:
    """Saw passes at each centre X in ``xs``, every one from ``y[0]`` to
    ``y[1]`` at the saw's lower face ``z``: up to ``clear`` first, over to
    the pass's start beside the block, down to the stock top plus SAFE_MM in
    a rapid, to ``z`` at feed, along Y at feed, up to ``clear``."""
    safe = _r(top + SAFE_MM)
    clear = _r(clear)
    y0, y1 = _r(y[0]), _r(y[1])
    lines = [f"G0 Z{clear:.3f}"]
    for x in xs:
        lines += [
            f"G0 X{_r(x):.3f} Y{y0:.3f}",
            f"G0 Z{safe:.3f}",
            f"G1 Z{_r(z):.3f} F{{feed}}",
            f"G1 Y{y1:.3f} F{{feed}}",
            f"G0 Z{clear:.3f}",
        ]
    return lines


def _saw_depths(depth: float, max_step: float) -> list[float]:
    """Depths of the saw's passes into the end, the slit's ``depth`` last: the
    first half a step (a light cut that proves the arbor's friction drive
    before the full ones), the rest equal steps no deeper than ``max_step``."""
    n = math.ceil(depth / max_step + 0.5 - 1e-9)
    step = depth / (n - 0.5)
    return [step * (k + 0.5) for k in range(n - 1)] + [depth]


def _saw_torque_nm(step: float, width: float, feed: float, rpm: float) -> float:
    """Mean spindle torque of a saw pass ``step`` into the work and ``width``
    wide at ``feed`` mm/min: the handbook's power (unit power × feed factor ×
    wear × removal rate) over the spindle's speed."""
    removal = step * width * feed / IN**3
    watts = WATTS_PER_HP * SAW_UNIT_POWER_HP * SAW_FEED_FACTOR * SAW_WEAR_FACTOR
    return watts * removal / (2 * math.pi * rpm / 60)


def _ring_radius(inner: float, outer: float) -> float:
    """The friction radius of a clamp ring ``inner`` to ``outer`` under even
    pressure."""
    return 2 * (outer**3 - inner**3) / (3 * (outer**2 - inner**2))


def _thread(designation: str) -> tuple[str, float, float]:
    """(size, basic major Ø, pitch) in mm of a unified thread designation."""
    match = re.match(r"(#\d+|\d+/\d+)-(\d+)", designation)
    if not match:
        raise ValueError(
            f"thread {designation!r} is not a unified size-TPI designation"
        )
    size, tpi = match.group(1), int(match.group(2))
    if size.startswith("#"):
        major = (0.060 + 0.013 * int(size[1:])) * IN
    else:
        num, den = size.split("/")
        major = int(num) / int(den) * IN
    return size, major, IN / tpi


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    f = features["features"]
    p = plan["parameters"]

    # The model frame this recipe assumes: E/W along X (E at -X), the seat
    # Y0 with the top at +Y, N/S along Z (N at +Z).
    def plane(name: str, axis: str) -> float:
        feature = f[name]["plane"]
        if feature["axis"] != axis:
            raise ValueError(f"{name}: expected a plane across {axis}")
        return feature["value"]

    seat_y, top_y = plane("seat", "y"), plane("top_face", "y")
    east_x, west_x = plane("east_face", "x"), plane("west_face", "x")
    north_z, south_z = plane("north_face", "z"), plane("south_face", "z")
    if seat_y != 0.0 or not math.isclose(
        top_y, f["top_face"]["height_nominal"], abs_tol=1e-3
    ):
        raise ValueError(
            "seat/top: expected the seat at Y0 and the top the height above it"
        )
    if not math.isclose(west_x - east_x, f["west_face"]["width_nominal"], abs_tol=1e-3):
        raise ValueError("west_face: its plane is not the width from E")
    if not math.isclose(
        north_z - south_z, f["south_face"]["depth_nominal"], abs_tol=1e-3
    ):
        raise ValueError("south_face: its plane is not the depth behind N")
    made = {
        "seat",
        "top_face",
        "east_face",
        "west_face",
        "north_face",
        "south_face",
        "adjuster",
        "slit",
        "pinch_tap",
        "pinch_clearance",
        "foot_tap",
    }
    for name, feature in f.items():
        if name not in made and feature.get("made_at") != "assembly":
            raise ValueError(f"{name}: a feature this recipe does not make")
    adj, slit = f["adjuster"], f["slit"]
    pinch, clearance, foot = f["pinch_tap"], f["pinch_clearance"], f["foot_tap"]
    if adj["axis"] != [0.0, 0.0, -1.0] or not math.isclose(adj["at"][2], north_z):
        raise ValueError("adjuster: expected through along Z from N")
    if pinch["axis"] != [1.0, 0.0, 0.0] or not math.isclose(pinch["at"][0], east_x):
        raise ValueError("pinch_tap: expected along X from E")
    if clearance["axis"] != [-1.0, 0.0, 0.0] or not math.isclose(
        clearance["at"][0], west_x
    ):
        raise ValueError("pinch_clearance: expected along X from W")
    if foot["axis"] != [0.0, 1.0, 0.0] or foot["at"][1] != seat_y:
        raise ValueError("foot_tap: expected along Y from the seat")
    if slit["axis"] != [0.0, -1.0, 0.0] or not math.isclose(slit["at"][1], top_y):
        raise ValueError("slit: expected down from the top")

    # Targets: each printed band's middle.
    length = _mid(f["top_face"]["height"])
    width = _mid(f["west_face"]["width"])
    depth = _mid(f["south_face"]["depth"])
    _agree(plan, "length_target_mm", length)
    _agree(plan, "width_target_mm", width)
    _agree(plan, "depth_target_mm", depth)

    # The blank: a strip sawn off the 1/2 x 2-1/4 bar's end, the bar's
    # thickness along Z (N the cold-finished face kept), its width along Y
    # (the length), the strip's width along X. E is skimmed, W faced to the
    # width; the top is skimmed, the seat faced to the length.
    east_skim, top_skim = p["east_skim_mm"], p["top_skim_mm"]
    strip_min, strip_max = p["strip_min_mm"], p["strip_max_mm"]
    bar_w_min, bar_w_max = p["bar_width_min_mm"], p["bar_width_max_mm"]
    bar_t_min, bar_t_max = p["bar_thickness_min_mm"], p["bar_thickness_max_mm"]
    _agree(plan, "west_raw_min_mm", strip_min - east_skim)
    _agree(plan, "west_raw_max_mm", strip_max - east_skim)
    _agree(plan, "seat_raw_min_mm", bar_w_min - top_skim)
    _agree(plan, "seat_raw_max_mm", bar_w_max - top_skim)
    w_raw_max = strip_max - east_skim
    s_raw_max = bar_w_max - top_skim
    cut_min = p["face_cut_min_mm"]
    for what, least in (
        ("the thinnest bar over the depth", bar_t_min - depth),
        ("the narrowest strip over the width", strip_min - east_skim - width),
        ("the narrowest bar over the length", bar_w_min - top_skim - length),
    ):
        if least < cut_min:
            raise ValueError(
                f"{what} leaves {least:.3f}, under process.face_cut_min_mm {cut_min}"
            )
    _agree(plan, "blank_x_in", round((strip_min + strip_max) / 2 / IN, 3))

    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    r = em / 2
    woc = p["face_stepover_max_mm"]
    step = p["face_step_max_mm"]
    face_rpm, face_feed = _setting(plan, shop, "depth face")
    face_cuts = ("depth face", "east face", "top face", "seat face", "west face")
    for name in face_cuts:
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), em, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter is not the 1/2 in end mill")
        if _setting(plan, shop, name) != (face_rpm, face_feed):
            raise ValueError(f"'{name}' runs at another setting than 'depth face'")
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), woc, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' radial_woc_mm is not process.face_stepover_max_mm"
            )
        if _cut(plan, name, "axial_doc_mm") > step + 1e-6:
            raise ValueError(f"'{name}' axial_doc_mm is over process.face_step_max_mm")
    if woc > r + 1e-9:
        raise ValueError("process.face_stepover_max_mm is over half the end mill")
    if east_skim > step + 1e-9 or top_skim > 3 * step + 1e-9:
        raise ValueError("a skim is deeper than its levels allow")
    depth_levels = _levels(bar_t_max, depth, step)
    east_levels = _levels(east_skim, 0.0, step)
    top_levels = _levels(top_skim, 0.0, step)
    seat_levels = _levels(s_raw_max, length, step)
    west_levels = _levels(w_raw_max, width, step)

    # Holes. The #43 against the two #4-40 taps' drill bands; the #30 against
    # the clearance's; the #3 against the adjuster's.
    d43 = _shop_tool(plan, shop, "drill-43")["diameter_mm"]
    d30 = _shop_tool(plan, shop, "drill-30")["diameter_mm"]
    d3 = _shop_tool(plan, shop, "drill-3")["diameter_mm"]
    for name, dia in (
        ("pinch_tap", d43),
        ("foot_tap", d43),
        ("pinch_clearance", d30),
        ("adjuster", d3),
    ):
        low, high = f[name]["dia"]
        if not low - SIZE_TOL_MM <= dia <= high:
            raise ValueError(f"Ø{dia} is outside {name}'s band {f[name]['dia']}")
    spot_dia = p["spot_dia_mm"]
    if not math.isclose(
        _cut(plan, "foot spot", "cutter_dia_mm"), spot_dia, abs_tol=1e-6
    ):
        raise ValueError("'foot spot' cutter_dia_mm is not process.spot_dia_mm")
    if spot_dia >= d43:
        raise ValueError(
            "the spot is not under the #43 drill: it would chamfer the hole"
        )
    spot_depth = _spot_depth(spot_dia)
    spot_rpm, spot_feed = _setting(plan, shop, "foot spot")
    d43_rpm, d43_feed = _setting(plan, shop, "foot drill")
    d30_rpm, d30_feed = _setting(plan, shop, "pinch clearance")
    d3_rpm, d3_feed = _setting(plan, shop, "adjuster drill")
    csk_rpm, csk_feed = _setting(plan, shop, "north countersink")
    for spot_name in ("pinch spot", "adjuster spot"):
        if _setting(plan, shop, spot_name) != (spot_rpm, spot_feed):
            raise ValueError(f"'{spot_name}' runs at another setting than 'foot spot'")
    if _setting(plan, shop, "pinch drill") != (d43_rpm, d43_feed):
        raise ValueError("'pinch drill' runs at another setting than 'foot drill'")
    if _setting(plan, shop, "south countersink") != (csk_rpm, csk_feed):
        raise ValueError(
            "'south countersink' runs at another setting than the north one"
        )
    peck43, peck = p["peck_43_mm"], p["peck_mm"]
    for cut, step_mm in (
        ("foot drill", peck43),
        ("pinch drill", peck43),
        ("pinch clearance", peck),
        ("adjuster drill", peck),
    ):
        op = _op_with_cut(plan, cut)[0]
        if op["peck"] != {"step_mm": step_mm, "retract": "full"}:
            raise ValueError(f"'{cut}' peck is not its process peck with full retract")
        if step_mm > _cut(plan, cut, "cutter_dia_mm") + 1e-6:
            raise ValueError(f"'{cut}' pecks deeper than one diameter")
    # The foot hole: #43 to its drill depth band's middle (full diameter),
    # from the seat; its point below that.
    foot_depth = _mid(foot["drill_depth"])
    foot_tip = length - foot_depth - _point(d43)
    _agree(plan, "foot_tip_height_mm", foot_tip)
    # The pinch hole: #43 through both halves from W, its full diameter
    # drill_past_mm past E (into the air between the stacks); the #30 to the
    # clearance's depth band's middle from W (full diameter).
    pinch_tip = -(p["drill_past_mm"] + _point(d43))
    _agree(plan, "pinch_tip_height_mm", pinch_tip)
    clear_depth = _mid(clearance["depth"])
    _agree(plan, "clearance_depth_mm", clear_depth)
    clear_tip = width - clear_depth - _point(d30)
    _agree(plan, "clearance_tip_height_mm", clear_tip)
    # Its shoulder stands in the slit at the slit's narrowest: the slot is
    # reached, and the full #30 never enters the E half.
    slit_min = slit["width"][0]
    shoulder = width - clear_depth  # height above E
    lateral = _mid(adj["lateral"])
    if not lateral - slit_min / 2 < shoulder < lateral + slit_min / 2:
        raise ValueError("the #30's shoulder is not inside the narrowest slit")
    # The adjuster: #3 through from N, drill_past_mm past S.
    adj_tip = -(p["drill_past_mm"] + _point(d3))
    _agree(plan, "adjuster_tip_height_mm", adj_tip)
    # DT08 is touched off on N at the nominal depth (so the countersink is
    # cut from N): the #3's full diameter still runs past S on the deepest
    # block, and its point no further below the stacks' top on the thinnest
    # than the stack check below allows (it is in the air between them).
    if -p["drill_past_mm"] > depth - f["south_face"]["depth"][1] - 0.5:
        raise ValueError(
            "process.drill_past_mm: the #3 stops short of S on the deepest block"
        )

    # Countersinks: the chamfer mill's point csk_tip_depth_mm below the face,
    # circling csk_orbit_mm off the axis: the rim at the band's middle. Its
    # cone at the face is inside the drilled hole on the way down, inside its
    # flutes at the rim, and its point never reaches the hole's wall.
    csk_dia = _mid(adj["csk_dia"])
    _agree(plan, "csk_dia_aim_mm", csk_dia)
    chamfer = _shop_tool(plan, shop, "chamfer")
    z_t = p["csk_tip_depth_mm"]
    _agree(plan, "csk_orbit_mm", csk_dia / 2 - z_t)
    orbit = p["csk_orbit_mm"]
    if adj["csk_angle_deg"] != CHAMFER_DEG:
        raise ValueError("adjuster: the countersink is not the chamfer mill's 90°")
    if not z_t < d3 / 2:
        raise ValueError(
            "process.csk_tip_depth_mm: the cone cuts the hole's mouth on the way down"
        )
    if not z_t <= chamfer["flute_length_mm"]:
        raise ValueError(
            "process.csk_tip_depth_mm: the rim is past the chamfer mill's flutes"
        )
    if not 0 < orbit < d3 / 2:
        raise ValueError("process.csk_orbit_mm: the point leaves the hole")
    if adj.get("csk_ends") != "both":
        raise ValueError("adjuster: expected a countersink at both ends")

    # Taps. Each tap's point reach below the face the tap enters, read on the
    # DRO; the full thread runs as far as the reach less the chamfer's most
    # threads, the partial thread no further than the reach.
    t_size, t_major, t_pitch = _thread(foot["thread"])
    if t_size != "#4" or _thread(pinch["thread"])[0] != "#4":
        raise ValueError("the foot and pinch taps are not #4-40")
    plug_reach, bot_reach = p["foot_plug_reach_mm"], p["foot_bottoming_reach_mm"]
    drill_min = foot["drill_depth"][0]
    thread_min, thread_max = foot["thread_depth"]
    if not plug_reach < drill_min or not bot_reach <= plug_reach:
        raise ValueError(
            "process.foot_plug_reach_mm/foot_bottoming_reach_mm: between the thread and "
            "the drilled depth"
        )
    # A bottoming tap's 1-2 thread chamfer spans more than the thread depth's
    # band: its full thread ends inside the band for the middle chamfer, and
    # never past the band's ceiling for a 1-thread one (a short thread is run
    # deeper after the marked-screw check; a deep one cannot be undone).
    lo, hi = BOTTOMING_CHAMFER_THREADS
    mid = (lo + hi) / 2
    if not (
        thread_min - 1e-6 <= bot_reach - mid * t_pitch <= thread_max + 1e-6
        and bot_reach - lo * t_pitch <= thread_max + 1e-6
    ):
        raise ValueError(
            "process.foot_bottoming_reach_mm: its full thread does not end inside the "
            "thread depth's limits"
        )
    # The pinch tap from E: its full thread reaches the slit's E-side face at
    # the narrowest slit; its point stays in the #30, past its shoulder and
    # short of W; its thread length keeps the shank out.
    pinch_reach = p["pinch_tap_reach_mm"]
    slit_face = lateral - slit_min / 2  # from E
    if pinch_reach - PLUG_CHAMFER_THREADS[1] * t_pitch < slit_face:
        raise ValueError(
            "process.pinch_tap_reach_mm: the full thread stops short of the slit"
        )
    if not shoulder < pinch_reach < width or TAP_4_SHANK_MM <= d30:
        raise ValueError("process.pinch_tap_reach_mm: the point is not inside the #30")
    if pinch_reach >= TAP_THREAD_LENGTH_MM["#4"]:
        raise ValueError("process.pinch_tap_reach_mm: past a #4 tap's thread length")
    # The adjuster tap through from N, its full thread past S at the deepest
    # block, its point into the air between the stacks.
    a_size, a_major, a_pitch = _thread(adj["thread"])
    adj_reach = p["adjuster_tap_reach_mm"]
    if adj_reach - PLUG_CHAMFER_THREADS[1] * a_pitch < f["south_face"]["depth"][1]:
        raise ValueError(
            "process.adjuster_tap_reach_mm: the full thread stops short of S"
        )
    if adj_reach >= TAP_THREAD_LENGTH_MM[a_size]:
        raise ValueError(
            "process.adjuster_tap_reach_mm: past a 1/4 tap's thread length"
        )

    # Holding: lying on the 1 in + 1/2 in stacks; the strip on edge for E's
    # skim on the 5/8 in + 1/2 in stacks (about four fifths of its width in
    # the jaws, E 3-5 mm above them); upright on the 1/2 in pair.
    jaw_h, jaw_w = p["vise_jaw_height_mm"], p["vise_jaw_width_mm"]
    lying_grip = jaw_h - p["riser_height_mm"]
    east_grip = jaw_h - p["east_riser_height_mm"]
    upright_grip = jaw_h - p["parallel_height_mm"]
    _agree(plan, "lying_grip_mm", lying_grip)
    _agree(plan, "east_grip_mm", east_grip)
    _agree(plan, "upright_grip_mm", upright_grip)
    t_par = p["parallel_thickness_mm"]
    # The tap stack's ceiling: spindle-to-table maximum less the tool-change
    # clearance, the vise bed, the tallest tapping setup (DT04/DT05: the 1/2
    # in parallels and the block before its seat is faced, the setup's work
    # top) and the collet's gauge, rounded down to .01 in; the tap's own
    # reach the stack less the guide.
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["parallel_height_mm"]
        - p["seat_raw_max_mm"]
        - p["r8_collet_gauge_mm"]
    )
    stack_max = math.floor(stack / 0.254 + 1e-9) * 0.254
    _agree(plan, "tap_stack_max_mm", stack_max)
    _agree(
        plan,
        "tap_wrench_reach_max_mm",
        math.floor((stack_max - TAP_GUIDE_OAL_MM) / 0.254 + 1e-9) * 0.254,
    )
    # DT09 taps the 1/4-28 with the block lying on the 1.5 in stacks: its
    # own ceiling, the deepest block in place of the upright one.
    adj_stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["riser_height_mm"]
        - f["south_face"]["depth"][1]
        - p["r8_collet_gauge_mm"]
    )
    adj_stack_max = math.floor(adj_stack / 0.254 + 1e-9) * 0.254
    _agree(
        plan,
        "adjuster_wrench_reach_max_mm",
        math.floor((adj_stack_max - TAP_GUIDE_OAL_MM) / 0.254 + 1e-9) * 0.254,
    )
    # Centred insets of the part along the jaws: (jaw width - its length
    # along them)/2 inside the left jaw side, as the vise holds state them.
    _agree(plan, "vise_strip_inset_mm", -(jaw_w - strip_max) / 2)
    _agree(plan, "vise_bar_inset_mm", -(jaw_w - bar_w_max) / 2)
    _agree(plan, "vise_upright_inset_mm", -(jaw_w - w_raw_max) / 2)
    _agree(plan, "vise_length_inset_mm", -(jaw_w - length) / 2)

    # The slit: the owned 2-3/4 x .064 saw (shop slitting-saw-2-75-064) on the
    # owned R8 stepped arbor (shop saw-arbor-r8-stepped), horizontal, its
    # lower face saw_cut_z_mm above E (the slit's middle at the adjuster's
    # lateral place), sawing in from the top end: a first pass of half a step,
    # then equal steps no deeper than slit_step_max_mm, to the slit's depth
    # (the export's REF, into the bore).
    saw = _shop_tool(plan, shop, "slit-saw")["diameter_mm"]
    _agree(plan, "saw_dia_mm", saw)
    radius = saw / 2
    thick = p["saw_thickness_mm"]
    slit_depth = slit["depth_ref"]
    _agree(plan, "slit_depth_mm", slit_depth)
    if slit.get("extent") != "SLOT INTO BORE":
        raise ValueError("slit: expected SLOT INTO BORE")
    # The kerf: the blade, miked at its mounting, at least the slit's floor;
    # the miked blade plus its axial runout (an indicator on its side face,
    # one hand revolution) at most the slit's ceiling less KERF_ALLOWANCE_MM.
    # saw_side_tir_nominal_mm is what that leaves the catalogue blade.
    _agree(plan, "blade_min_mm", slit["width"][0])
    _agree(plan, "kerf_max_mm", slit["width"][1] - KERF_ALLOWANCE_MM)
    if not p["blade_min_mm"] <= thick < p["kerf_max_mm"]:
        raise ValueError(
            "process.saw_thickness_mm: the blade leaves no runout inside the slit's width"
        )
    _agree(plan, "saw_side_tir_nominal_mm", p["kerf_max_mm"] - thick)
    # The reading is taken RUNOUT_INSET_MM in from the teeth, where the saw
    # swings less than at its rim: with the thinnest accepted blade and the
    # reading at its limit, the rim still sweeps inside the slit's ceiling.
    rim = radius / (radius - RUNOUT_INSET_MM)
    if (
        p["blade_min_mm"] + (p["kerf_max_mm"] - p["blade_min_mm"]) * rim
        > slit["width"][1]
    ):
        raise ValueError(
            "process.kerf_max_mm: the saw's rim sweeps over the slit's width"
        )
    # The slit's depth: X0 is the top end and the saw's centre its recorded
    # radius less the depth past it, so the tips' radial runout (at most
    # saw_tip_tir_max_mm, read at the mounting) deepens the floor, and a saw
    # off its recorded diameter (miked over two opposite tips to within
    # saw_dia_tol_mm of it) moves the floor by half the error. At those
    # limits together, at both ends of the block's height band and of the
    # adjuster's height band (H measured, within the band), the floor stays
    # inside the adjuster's minor bore.
    tip_tir = p["saw_tip_tir_max_mm"]
    dia_tol = p["saw_dia_tol_mm"]
    _agree(plan, "saw_dia_min_mm", p["saw_dia_mm"] - dia_tol)
    _agree(plan, "saw_dia_max_mm", p["saw_dia_mm"] + dia_tol)
    bore_r = adj["dia"][0] / 2
    # The adjuster's axis prints (1.50) REF and is made to the measured
    # MHA-DT-05 journal height (note 2, machinist review r1, farm run
    # 20261124T110807008Z); the floor is still proved over the title
    # block's .XX band (±.01 in) around that REF, the envelope the matched
    # height was proved in before it went REF.
    xx_band = 0.01 * 25.4
    for h in (adj["height_ref"] - xx_band, adj["height_ref"] + xx_band):
        for top in f["top_face"]["height"]:
            if not (
                h - bore_r < top - slit_depth - tip_tir - dia_tol / 2
                and top - slit_depth + dia_tol / 2 < h + bore_r
            ):
                raise ValueError(
                    "the slit's floor is not inside the adjuster bore at "
                    "process.saw_tip_tir_max_mm and process.saw_dia_tol_mm"
                )
    # Setup 11's height-gauge check: the match about the drawn (REF) height,
    # as the gauge reads it from SEAT.
    _agree(plan, "adjuster_height_check_min_mm", adj["height_ref"] + adj["height_match"][0])
    _agree(plan, "adjuster_height_check_max_mm", adj["height_ref"] + adj["height_match"][1])
    _agree(plan, "saw_cut_z_mm", lateral - thick / 2)
    saw_z = p["saw_cut_z_mm"]
    if not lying_grip < saw_z:
        raise ValueError("the saw's lower face is under the jaw tops")
    # Depths into the TOP end, shallowest first, the slit's depth last.
    saw_steps = _saw_depths(slit_depth, p["slit_step_max_mm"])
    _agree(plan, "slit_first_pass_mm", saw_steps[0])
    _agree(plan, "slit_step_mm", saw_steps[1] - saw_steps[0])
    saw_xs = [radius - d for d in saw_steps]
    if not math.isclose(_cut(plan, "slit", "cutter_dia_mm"), saw, abs_tol=1e-6):
        raise ValueError("'slit' cutter_dia_mm is not the saw's")
    if not math.isclose(
        _cut(plan, "slit", "radial_woc_mm"), p["slit_step_max_mm"], abs_tol=1e-6
    ):
        raise ValueError("'slit' radial_woc_mm is not process.slit_step_max_mm")
    if not math.isclose(_cut(plan, "slit", "axial_doc_mm"), thick, abs_tol=1e-6):
        raise ValueError("'slit' axial_doc_mm is not process.saw_thickness_mm")
    teeth = p["saw_teeth"]
    if _cut(plan, "slit", "flutes") != teeth:
        raise ValueError("'slit' flutes is not process.saw_teeth")
    saw_rpm, saw_feed = _setting(plan, shop, "slit")
    if (saw_rpm, saw_feed) != (p["saw_rpm"], p["saw_feed_per_min_mm"]):
        raise ValueError("the slit is not process.saw_rpm and saw_feed_per_min_mm")
    # The first pass is the same saw at the same speed and feed, its step the
    # light one.
    for key, value in (
        ("cutter_dia_mm", saw),
        ("axial_doc_mm", thick),
        ("flutes", teeth),
        ("radial_woc_mm", p["slit_first_pass_mm"]),
    ):
        if not math.isclose(_cut(plan, "slit first", key), value, abs_tol=1e-6):
            raise ValueError(f"'slit first' {key} is not the slit's")
    if _setting(plan, shop, "slit first") != (saw_rpm, saw_feed):
        raise ValueError("the slit's first pass is not at the slit's speed and feed")
    # A saw running out at its tips by saw_tip_tir_max_mm (half of it the
    # eccentricity) stands, from one tooth to the next, at most that
    # eccentricity times the tooth pitch angle higher: under the feed per
    # tooth, so no tooth takes more than twice its feed.
    if tip_tir / 2 * 2 * math.pi / teeth >= saw_feed / (saw_rpm * teeth):
        raise ValueError(
            "process.saw_tip_tir_max_mm: a tooth could take over twice its feed"
        )
    # The arbor round the saw: the owned R8 stepped arbor (inventory
    # tools.saw-arbor-r8-stepped; the plan repeats its recorded sizes, and
    # test_dt_cone_tip_block_process.py holds the two together). The saw seats
    # against the body's shoulder on its upper (spindle) side, the body
    # saw_arbor_body_dia_mm across; the cap, saw_arbor_cap_dia_mm across and
    # saw_arbor_cap_thickness_mm thick, clamps it from below with its
    # countersunk screw. Two sizes the record does not carry are the plan's
    # bounds, measured at the mounting before the spindle starts: the screw
    # head stands at most saw_screw_stand_max_mm past the cap's face, and the
    # spindle nose (or anything wider than the body) at least
    # saw_nose_above_min_mm above the saw's upper face.
    body_r = p["saw_arbor_body_dia_mm"] / 2
    cap_r = p["saw_arbor_cap_dia_mm"] / 2
    cap_t = p["saw_arbor_cap_thickness_mm"]
    stand_max = p["saw_screw_stand_max_mm"]
    nose_above = p["saw_nose_above_min_mm"]
    if not 0 <= stand_max or not p["saw_arbor_screw_head_dia_mm"] < 2 * cap_r:
        raise ValueError("the cap's screw head is not inside the cap")
    _agree(plan, "saw_below_max_mm", cap_t + stand_max)
    below = p["saw_below_max_mm"]
    # At the cut the cap and screw hang this far below the stacks' top, right
    # of TOP: lower than the parallels' top. The keep-outs below end the
    # stacks at the jaws' right side; the traveler has the builder check at
    # every clamping that no parallel stands past it.
    _agree(plan, "saw_below_stack_top_mm", below - saw_z)
    # The arbor's lowest point from the spindle nose: the record's nose to the
    # cap's lower face (no saw fitted) plus the saw, rounded up, plus the
    # screw head's bound.
    _agree(
        plan,
        "saw_arbor_length_mm",
        math.ceil(
            (p["saw_arbor_nose_to_cap_mm"] + thick) / ARBOR_LENGTH_STEP_MM - 1e-9
        )
        * ARBOR_LENGTH_STEP_MM
        + stand_max,
    )
    # The record's own figures pass both bounds: a flush screw head, and the
    # nose the record's length less the cap above the saw.
    if p["saw_arbor_nose_to_cap_mm"] - cap_t < nose_above:
        raise ValueError(
            "process.saw_nose_above_min_mm is over what the arbor's record gives"
        )
    # The arbor goes in and comes out with the saw clamped on it, and only at
    # the machine top (the traveler sends Z there first, both times, X and Y
    # as they stand): its shank drops R8_SHANK_MM to come free. The room
    # under the spindle nose there, over the block lying on its stacks,
    # covers the arbor's length, that drop and the tool-change clearance.
    top_room = (
        machine["spindle_to_table_mm"][1]
        - p["vise_bed_height_mm"]
        - p["riser_height_mm"]
        - f["west_face"]["width"][1]
    )
    if (
        p["saw_arbor_length_mm"]
        + R8_SHANK_MM
        + shop["limits"]["tool_change_clearance_mm"]
        > top_room
    ):
        raise ValueError(
            "the arbor with its saw cannot drop out of the spindle at the "
            f"machine top: {top_room:.1f} mm under the nose"
        )
    # The cap screw's thread carries the clamp torque the drive below rests
    # on: the record's engagement with no saw fitted, less the thickest blade
    # the plan accepts (a saw moves the cap that far down the screw), is one
    # screw diameter or more.
    if p["saw_screw_engagement_no_saw_mm"] - p["kerf_max_mm"] < p["saw_screw_dia_mm"]:
        raise ValueError(
            "process.saw_screw_engagement_no_saw_mm leaves the cap screw under "
            "one diameter of thread with the saw fitted"
        )
    # The friction drive (the arbor is not keyed): one face's friction torque
    # on the clamp ring between the pilot (the saw's hole) and the narrower
    # of the body and the cap, at the plan's preload and friction; the other
    # face and the screw are its reserve. The heaviest pass (the deepest
    # step, at the kerf's ceiling) takes no more spindle torque, by the
    # handbook's power at this feed per tooth, than that drive carries with
    # DRIVE_RESERVE in hand.
    ring = _ring_radius(p["saw_bore_mm"] / 2, min(body_r, cap_r))
    drive = p["saw_drive_friction"] * p["saw_clamp_preload_kn"] * ring
    if not math.isclose(p["saw_drive_torque_max_nm"], drive, abs_tol=DRIVE_TOL_NM):
        raise ValueError(
            f"process.saw_drive_torque_max_nm {p['saw_drive_torque_max_nm']:g}, "
            f"the recipe computes {drive:.2f}"
        )
    if not math.isclose(
        saw_feed / (saw_rpm * teeth), SAW_FEED_FACTOR_AT_MM, abs_tol=1e-6
    ):
        raise ValueError(
            "the saw's feed is not the .001 in/tooth the handbook's feed factor "
            "is taken at"
        )
    bite = max(b - a for a, b in zip([0.0, *saw_steps], saw_steps, strict=False))
    torque = _saw_torque_nm(bite, p["kerf_max_mm"], saw_feed, saw_rpm)
    if torque * DRIVE_RESERVE > drive:
        raise ValueError(
            f"the saw's heaviest pass takes {torque:.1f} N·m, over the arbor's "
            f"friction drive with its reserve: {drive / DRIVE_RESERVE:.1f} of "
            f"process.saw_drive_torque_max_nm {drive:.1f}"
        )
    # The reach past the arbor, on both sides of the saw (the body above, the
    # cap below): (the saw - the wider of them) / 2 less ARBOR_CLEAR_MM. The
    # slit's depth is inside it, so at full depth the body and the cap stand
    # past the top end, and past both jaw sides the overhang puts farther in.
    arbor_r = max(body_r, cap_r)
    _agree(plan, "saw_reach_max_mm", radius - arbor_r - ARBOR_CLEAR_MM)
    if slit_depth > p["saw_reach_max_mm"] + 1e-6:
        raise ValueError("the slit is deeper than the saw's reach past its arbor")
    if saw_xs[-1] - arbor_r < ARBOR_CLEAR_MM - 1e-6:
        raise ValueError("the arbor's body or cap reaches the top end")
    overhang = p["slit_overhang_mm"]
    if overhang <= slit_depth + 1.0:
        raise ValueError("process.slit_overhang_mm: the saw reaches the jaws")
    _agree(plan, "vise_slit_inset_mm", -(jaw_w - (length - overhang)))
    # The vise spacer may be at most spacer_under_max_mm thinner than the
    # block (never thicker: Setup 2 takes the thicker strip as the block).
    # The allowance is no finer than the feeler set's thinnest leaf, so the
    # leaves that make up a larger difference can always land inside it.
    if not p["spacer_under_max_mm"] >= shop["gauges"]["feeler-gauges"]["range_mm"][0]:
        raise ValueError(
            "process.spacer_under_max_mm is finer than the thinnest feeler leaf"
        )
    # The spindle nose, saw_nose_above_min_mm or more above the saw's upper
    # face, passes over everything in the vise at the cut (the saw's lowest
    # height): the block's W and the spacer strip standing on the vise bed.
    strip_top = bar_w_max - p["riser_height_mm"]
    tallest = max(f["west_face"]["width"][1], strip_top, lying_grip)
    if saw_z + thick + nose_above < tallest + NOSE_CLEAR_MM - 1e-6:
        raise ValueError(
            "process.saw_nose_above_min_mm: the spindle nose does not clear the vise's load"
        )
    _agree(plan, "saw_clear_z_mm", f["west_face"]["width"][1] + CLEAR_MM + below)
    saw_clear = p["saw_clear_z_mm"]
    _agree(plan, "saw_touch_x_mm", radius - TOUCH_IN_MM)
    _agree(plan, "saw_touch_y_mm", -depth / 2)
    # The touch-off puts the saw's rim TOUCH_IN_MM in over the top end: inside
    # the arbor's reach, so the cap and its screw, hanging below the saw as it
    # comes down, are beyond the end.
    if TOUCH_IN_MM > p["saw_reach_max_mm"]:
        raise ValueError(
            "the saw's touch-off puts its rim farther in over the top end than "
            "the arbor reaches: the cap would come down on it"
        )
    proof_raise = p["saw_proof_raise_mm"]

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)). Raw faces in the model:
    # E's skim beyond east_x, W the rest of the strip; the top's skim above
    # top_y, the seat the rest of the bar's width below the seat; N kept. N,
    # as bought, seats against the fixed jaw whenever S is the other gripped
    # face (a machined face at the fixed jaw would need a rod at the moving
    # one), so those setups put TOP or W on the left.
    e_raw = east_x - east_skim
    s_raw = top_y + top_skim - bar_w_max
    frames = {
        "depth": ([e_raw, s_raw, north_z], [[1, 0, 0], [0, -1, 0], [0, 0, -1]]),
        "east": (
            [east_x, top_y + top_skim, north_z],
            [[0, -1, 0], [0, 0, 1], [-1, 0, 0]],
        ),
        "top": (
            [east_x + w_raw_max, top_y, north_z],
            [[-1, 0, 0], [0, 0, 1], [0, 1, 0]],
        ),
        "seat": ([east_x, top_y, north_z], [[1, 0, 0], [0, 0, 1], [0, -1, 0]]),
        "west": ([east_x, seat_y, north_z], [[0, 1, 0], [0, 0, 1], [1, 0, 0]]),
        "pinch": ([west_x, seat_y, north_z], [[0, -1, 0], [0, 0, 1], [-1, 0, 0]]),
        "adjuster": ([east_x, seat_y, south_z], [[0, 1, 0], [-1, 0, 0], [0, 0, 1]]),
        "south": ([east_x, seat_y, north_z], [[0, -1, 0], [-1, 0, 0], [0, 0, -1]]),
        "slit": ([east_x, top_y, north_z], [[0, 1, 0], [0, 0, 1], [1, 0, 0]]),
    }
    for key, (_origin, axes) in frames.items():
        if not math.isclose(_det(axes), 1.0):
            raise ValueError(f"frame {key!r} is not right-handed")
    frames = {k: {"origin": o, "axes": a} for k, (o, a) in frames.items()}

    def at(key: str, point: list[float]) -> list[float]:
        return [_r(v) for v in _to(frames[key], point)]

    foot_xy = at("seat", foot["at"])[:2]
    pinch_xy = at("west", pinch["at"])[:2]
    tap_pinch_xy = at("pinch", pinch["at"])[:2]
    adj_xy = at("adjuster", adj["at"])[:2]
    south_xy = at("south", [adj["at"][0], adj["at"][1], south_z])[:2]
    if foot_xy != [_r(foot["at"][0] - east_x), _r(foot["at"][2] - north_z)]:
        raise ValueError(f"foot hole {foot_xy} is not where the seat frame puts it")
    if not (0 < pinch_xy[0] < length and -depth < pinch_xy[1] < 0):
        raise ValueError(f"pinch hole {pinch_xy} is not on the block in DT06")
    if not math.isclose(pinch_xy[0], -tap_pinch_xy[0]) or adj_xy[0] != -south_xy[0]:
        raise ValueError("a hole's place differs between its setups")

    stocks = {
        "depth": ((0.0, strip_max), (-bar_w_max, 0.0), (0.0, bar_t_max)),
        "east": ((0.0, bar_w_max), (-depth, 0.0), (-w_raw_max, east_skim)),
        "top": ((0.0, w_raw_max), (-depth, 0.0), (-s_raw_max, top_skim)),
        "seat": ((0.0, w_raw_max), (-depth, 0.0), (0.0, s_raw_max)),
        "west": ((0.0, length), (-depth, 0.0), (0.0, w_raw_max)),
        "pinch": ((-length, 0.0), (-depth, 0.0), (0.0, width)),
        "adjuster": ((0.0, length), (-width, 0.0), (0.0, depth)),
        "south": ((-length, 0.0), (-width, 0.0), (0.0, depth)),
        "slit": ((-length, 0.0), (-depth, 0.0), (0.0, width)),
    }

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
    d43_tool = drill_tool("drill-43", d43, d43_rpm, d43_feed, DRILL_POINT_DEG)
    d30_tool = drill_tool("drill-30", d30, d30_rpm, d30_feed, DRILL_POINT_DEG)
    d3_tool = drill_tool("drill-3", d3, d3_rpm, d3_feed, DRILL_POINT_DEG)
    # FreeCAD's chamfer bit has no tip angle; the posted lines are the
    # recipe's own, so the 90° chamfer mill is carried as a 90° pointed bit.
    csk_tool = {
        **drill_tool("chamfer", chamfer["diameter_mm"], csk_rpm, csk_feed, CHAMFER_DEG),
        "plunge": csk_feed / 2,
    }
    saw_tool = {
        "tool": "slit-saw",
        "dia": saw,
        "shape": "slittingsaw",
        "flutes": None,
        "rpm": saw_rpm,
        "feed": saw_feed,
        "plunge": saw_feed,
    }

    def job(tool: dict, frame: str, key: str, label: str, lines: list[str]) -> dict:
        return {
            **tool,
            "frame": frame,
            "label": key.replace("_", " "),
            "stock": stocks[frame],
            "ops": [[key, label, lines]],
        }

    ys_bar = _stations(-bar_w_max, 0.0, r, woc)
    ys_depth = _stations(-depth, 0.0, r, woc)
    x_strip = (-r - APPROACH_MM, strip_max + r + APPROACH_MM)
    x_bar = (-r - APPROACH_MM, bar_w_max + r + APPROACH_MM)
    x_up = (-r - APPROACH_MM, w_raw_max + r + APPROACH_MM)
    x_len = (-r - APPROACH_MM, length + r + APPROACH_MM)
    faces = {
        "depth_face": (
            depth_levels,
            bar_t_max,
            x_strip,
            ys_bar,
            (-bar_w_max, 0.0),
            "depth",
            strip_min,
        ),
        "east_face": (
            east_levels,
            east_skim,
            x_bar,
            ys_depth,
            (-depth, 0.0),
            "east",
            bar_w_min,
        ),
        "top_face": (
            top_levels,
            top_skim,
            x_up,
            ys_depth,
            (-depth, 0.0),
            "top",
            w_raw_max - 2.0,
        ),
        "seat_face": (
            seat_levels,
            s_raw_max,
            x_up,
            ys_depth,
            (-depth, 0.0),
            "seat",
            w_raw_max - 2.0,
        ),
        "west_face": (
            west_levels,
            w_raw_max,
            x_len,
            ys_depth,
            (-depth, 0.0),
            "west",
            length - 1.0,
        ),
    }
    jobs = []
    for key, (levels, top, xs, ys, _y, frame, _span) in faces.items():
        if key == "seat_face":
            continue
        jobs.append(
            job(
                em_tool,
                frame,
                key,
                f"face the {key.replace('_', ' ')}",
                _face(levels, top, xs, ys),
            )
        )
    # DT04: the seat, then the foot hole.
    levels, top, xs, ys, _y, frame, _span = faces["seat_face"]
    jobs.append(
        job(
            em_tool,
            "seat",
            "seat_face",
            "face the seat to the height",
            _face(levels, top, xs, ys),
        )
    )
    seat_clear = length + CLEAR_MM
    jobs.append(
        job(
            spot_tool,
            "seat",
            "foot_spot",
            "spot the foot hole",
            _spot(foot_xy, length, length - spot_depth, seat_clear),
        )
    )
    jobs.append(
        job(
            d43_tool,
            "seat",
            "foot_drill",
            "drill the foot hole #43",
            _pecked(foot_xy, length, foot_tip, peck43, seat_clear),
        )
    )
    # DT06: W to the width is posted above; the pinch hole.
    west_clear = width + CLEAR_MM
    jobs.append(
        job(
            spot_tool,
            "west",
            "pinch_spot",
            "spot the pinch hole",
            _spot(pinch_xy, width, width - spot_depth, west_clear),
        )
    )
    jobs.append(
        job(
            d43_tool,
            "west",
            "pinch_drill",
            "drill the pinch hole #43 through",
            _pecked(pinch_xy, width, pinch_tip, peck43, west_clear),
        )
    )
    jobs.append(
        job(
            d30_tool,
            "west",
            "pinch_clearance",
            "open the W half #30 to the slot",
            _pecked(pinch_xy, width, clear_tip, peck, west_clear),
        )
    )
    # DT08: the adjuster from N; DT10: S's countersink.
    adj_clear = depth + CLEAR_MM
    csk_tip = depth - z_t
    _agree(plan, "csk_tip_height_mm", csk_tip)
    jobs.append(
        job(
            spot_tool,
            "adjuster",
            "adjuster_spot",
            "spot the adjuster",
            _spot(adj_xy, depth, depth - spot_depth, adj_clear),
        )
    )
    jobs.append(
        job(
            d3_tool,
            "adjuster",
            "adjuster_drill",
            "drill the adjuster #3 through",
            _pecked(adj_xy, depth, adj_tip, peck, adj_clear),
        )
    )
    jobs.append(
        job(
            csk_tool,
            "adjuster",
            "north_csk",
            "countersink the adjuster at N",
            _countersink(adj_xy, depth, csk_tip, orbit, adj_clear),
        )
    )
    jobs.append(
        job(
            csk_tool,
            "south",
            "south_csk",
            "countersink the adjuster at S",
            _countersink(south_xy, depth, csk_tip, orbit, adj_clear),
        )
    )
    # DT11: the slit, passes along +Y (conventional: the M3 saw right of the
    # top end), from beside the moving jaw's side of the block to past the
    # fixed jaw's. The first, light pass is a section of its own: the stop
    # after it reads the friction drive's marker line before the full passes.
    saw_y = (-depth - radius - APPROACH_MM, radius + APPROACH_MM)
    jobs.append(
        job(
            saw_tool,
            "slit",
            "slit_first",
            "saw the slit's first, light pass",
            _saw(saw_xs[:1], saw_z, saw_y, width, saw_clear),
        )
    )
    jobs.append(
        job(
            saw_tool,
            "slit",
            "slit",
            "saw the slit into the adjuster",
            _saw(saw_xs[1:], saw_z, saw_y, width, saw_clear),
        )
    )

    # One file per hole to tap: the tap guide loaded by the file's own M6,
    # Z to the machine's top before any XY, over the hole, M30: the
    # controller ends Idle for the operator's jog.
    def tap_stop(what: str, xy: list[float]) -> dict:
        return {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": f"SPINDLE STAYS OFF. NEXT: {what}",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
                f"({what}. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND TO THE NOTED DRO Z, PUSHING THE POINT HOME EACH 1/2 IN,"
                " READ WITH THE POINT PUSHED HOME. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": xy,
        }

    manual = {
        "tap_foot": tap_stop("4-40 PLUG THEN BOTTOMING TAP IN THE FOOT HOLE", foot_xy),
        "tap_pinch": tap_stop("4-40 PLUG TAP IN THE PINCH HOLE FROM E", tap_pinch_xy),
        "tap_adjuster": tap_stop("1/4-28 PLUG TAP THROUGH THE ADJUSTER", adj_xy),
        # The saw's stop after its first pass: raised clear past the top end
        # (the pass's last move), the spindle stopped, the same tool kept (no
        # M6); the next section starts the spindle again. CNCjs shows the
        # %msg line when the M0 pauses it.
        "slit_check": {
            "tool": numbers["slit-saw"],
            "label": names["slit-saw"],
            "setting": "SPINDLE STOPPED",
            "gcode": [
                "M5",
                "%msg PAUSE: SPINDLE STOPPED. BOTH MARKER LINES (CAP TO SAW, SAW TO"
                " THE ARBOR'S BODY) UNBROKEN: CYCLE START. A LINE BROKEN: STOP,"
                " THE SAW SLIPPED ON THE ARBOR",
                "M0",
            ],
            "at": [_r(saw_xs[0]), _r(saw_y[1])],
        },
    }

    # Keep-outs (each program's frame): the jaws beside the gripped span, from
    # the stacks' or parallels' top to the jaw tops, centred on the part along
    # the jaws; the stacks under the part where a hole exits.
    def jaws(
        across: float,
        along: tuple[float, float],
        z_top: float,
        across_min: float | None = None,
    ) -> list[dict]:
        centre = (along[0] + along[1]) / 2
        x = (centre - jaw_w / 2, centre + jaw_w / 2)
        near = across if across_min is None else across_min
        return [
            _box("fixed jaw", x, (0.0, JAW_DEPTH_MM), z_top),
            _box("moving jaw", x, (-across - JAW_DEPTH_MM, -near), z_top),
        ]

    def stacks(across: float, along: tuple[float, float]) -> list[dict]:
        centre = (along[0] + along[1]) / 2
        x = (centre - PARALLEL_LENGTH_MM / 2, centre + PARALLEL_LENGTH_MM / 2)
        return [
            _box("fixed-jaw stack", x, (-t_par, 0.0), 0.0),
            _box("moving-jaw stack", x, (-across, -across + t_par), 0.0),
        ]

    keep = {
        "depth_face": jaws(bar_w_max, (0.0, strip_max), lying_grip, bar_w_min),
        "east_face": jaws(depth, (0.0, bar_w_max), east_grip - (strip_min - east_skim)),
        "top_face": jaws(
            depth, (0.0, w_raw_max), upright_grip - (bar_w_min - top_skim)
        ),
        "seat_face": jaws(depth, (0.0, w_raw_max), upright_grip),
        "west_face": jaws(depth, (0.0, length), lying_grip),
    }
    # Every face's last level stands at least jaw_clear_min_mm over its jaw
    # tops: the cutter passes over them.
    for key, boxes in keep.items():
        if faces[key][0][-1] - boxes[0]["z_top"] < p["jaw_clear_min_mm"]:
            raise ValueError(
                f"{key}: the last level is under process.jaw_clear_min_mm over the jaw tops"
            )
    west_keep = keep["west_face"] + stacks(depth, (0.0, length))
    adj_keep = jaws(width, (0.0, length), lying_grip) + stacks(width, (0.0, length))
    south_keep = jaws(width, (-length, 0.0), lying_grip) + stacks(width, (-length, 0.0))
    # Every hole's exit, and each tap through it (its basic major), clears
    # the stacks under the part.
    for what, xy, half, across in (
        ("the pinch hole's exit at E", pinch_xy, t_major / 2, depth),
        ("the adjuster's exit at S", adj_xy, a_major / 2, width),
    ):
        if not (-across + t_par + half < xy[1] < -t_par - half):
            raise ValueError(f"{what} reaches a stack")
    # The least gap each leaves a stack, the hole anywhere in its drawing
    # band and the block at its least size across the jaws: the Holding texts
    # of those two setups print it.
    for key, band, half, least in (
        ("pinch_stack_clear_min_mm", pinch["depth_center"], t_major / 2, f["south_face"]["depth"][0]),
        ("adjuster_stack_clear_min_mm", adj["lateral"], a_major / 2, f["west_face"]["width"][0]),
    ):
        gap = min(band[0], least - band[1]) - half - t_par
        if gap <= 0:
            raise ValueError(f"process.{key}: the hole can reach a stack")
        _agree(plan, key, gap)
    # DT11: the jaws inward of the overhang, the stacks inside them, the
    # spacer strip standing on the vise bed at the jaws' left end, and the
    # block itself (the arbor's parts must miss it at every Z).
    side = -overhang
    slit_jaws = [
        _box("fixed jaw", (side - jaw_w, side), (0.0, JAW_DEPTH_MM), lying_grip),
        _box(
            "moving jaw",
            (side - jaw_w, side),
            (-depth - JAW_DEPTH_MM, -depth),
            lying_grip,
        ),
    ]
    slit_stacks = [
        _box("fixed-jaw stack", (side - PARALLEL_LENGTH_MM, side), (-t_par, 0.0), 0.0),
        _box(
            "moving-jaw stack",
            (side - PARALLEL_LENGTH_MM, side),
            (-depth, -depth + t_par),
            0.0,
        ),
    ]
    slit_strip = _box(
        "the spacer strip",
        (side - jaw_w, side - jaw_w + strip_max),
        (-depth, 0.0),
        strip_top,
    )
    block = _box("the block", (-length, 0.0), (-depth, 0.0), f["west_face"]["width"][1])
    solids = slit_jaws + slit_stacks + [slit_strip, block]

    def reach(part: str, lo: float) -> list[dict[str, Any]]:
        """``solids`` as bands of the programmed Z (the saw's lower face) in
        which an arbor part reaching down to ``lo`` from it would meet them."""
        return [
            {**s, "name": f"{s['name']} ({part})", "z_top": _r(s["z_top"] - lo)}
            for s in solids
        ]

    tn = numbers
    expect: list[list[Any]] = []

    def face_checks(key: str) -> list[list[Any]]:
        levels, top, _xs, _ys, y, _frame, span = faces[key]
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
                        "max_engagement": woc,
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
        xy: list[float], top: float, bottom: float, radius_: float, boxes: list
    ) -> list[list[Any]]:
        return [
            ["holes", {"centres": [xy], "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": top, "open_holes": [xy]}],
            ["vertical_below_top", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": radius_, "boxes": boxes}],
        ]

    def csk_checks(xy: list[float], boxes: list) -> list[list[Any]]:
        rim = [
            [_r(xy[0] + dx), _r(xy[1] + dy)]
            for dx, dy in (
                (csk_dia / 2, 0),
                (0, csk_dia / 2),
                (-csk_dia / 2, 0),
                (0, -csk_dia / 2),
            )
        ]
        return [
            ["holes", {"centres": [xy], "z_bottom": _r(csk_tip)}],
            ["cleared", {"points": rim, "radius": _r(z_t), "z": _r(csk_tip)}],
            ["rapids_clear", {"z_top": depth, "open_holes": [xy]}],
            ["air_feed", {"z_top": depth}],
            ["keep_out", {"radius": chamfer["diameter_mm"] / 2, "boxes": boxes}],
        ]

    for name, key in (
        ("DT01_depth", "depth_face"),
        ("DT02_east", "east_face"),
        ("DT03_top", "top_face"),
    ):
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
    seat_keep = keep["seat_face"]
    for name, top, tools, rpms, deepest, sections in (
        (
            "DT04_seat",
            s_raw_max,
            ["em-half", "spot", "drill-43"],
            [face_rpm, spot_rpm, d43_rpm],
            foot_tip,
            [
                face_checks("seat_face"),
                hole_checks(
                    foot_xy,
                    length,
                    length - spot_depth,
                    CENTRE_DRILL["body_mm"] / 2,
                    seat_keep,
                ),
                hole_checks(foot_xy, length, foot_tip, d43 / 2, seat_keep),
            ],
        ),
        (
            "DT06_west",
            w_raw_max,
            ["em-half", "spot", "drill-43", "drill-30"],
            [face_rpm, spot_rpm, d43_rpm, d30_rpm],
            pinch_tip,
            [
                [c for c in face_checks("west_face") if c[0] != "keep_out"]
                + [["keep_out", {"radius": r, "boxes": west_keep}]],
                hole_checks(
                    pinch_xy,
                    width,
                    width - spot_depth,
                    CENTRE_DRILL["body_mm"] / 2,
                    west_keep,
                ),
                hole_checks(pinch_xy, width, pinch_tip, d43 / 2, west_keep),
                hole_checks(pinch_xy, width, clear_tip, d30 / 2, west_keep),
            ],
        ),
        (
            "DT08_adjuster",
            depth,
            ["spot", "drill-3", "chamfer"],
            [spot_rpm, d3_rpm, csk_rpm],
            adj_tip,
            [
                hole_checks(
                    adj_xy,
                    depth,
                    depth - spot_depth,
                    CENTRE_DRILL["body_mm"] / 2,
                    adj_keep,
                ),
                hole_checks(adj_xy, depth, adj_tip, d3 / 2, adj_keep),
                csk_checks(adj_xy, adj_keep),
            ],
        ),
    ):
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": top, "tools": [tn[t] for t in tools], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[v] for v in rpms]}],
            [name, "pauses", {"z_top": top, "count": 0}],
            [name, "depth", {"z_min": _r(deepest)}],
        ]
        for k, checks in enumerate(sections):
            expect += [
                [f"{name}@{k}", check, kwargs]
                for check, kwargs in checks
                if check != "depth"
            ]
    name = "DT10_south_csk"
    expect += [
        [
            name,
            "tool_changes",
            {"z_top": depth, "tools": [tn["chamfer"]], "loads_first": True},
        ],
        [name, "spindle", {"rpm": [[csk_rpm]]}],
        [name, "pauses", {"z_top": depth, "count": 0}],
        [name, "depth", {"z_min": _r(csk_tip)}],
        *[[name, check, kwargs] for check, kwargs in csk_checks(south_xy, south_keep)],
    ]
    name = "DT11_slit"
    expect += [
        [name, "tool_changes", {"z_top": width, "tools": [], "loads_first": False}],
        [name, "spindle", {"rpm": [[saw_rpm]]}],
        # One stop, after the first pass: the saw raised clear where that pass
        # ended, the spindle stopped before the operator looks at the arbor.
        [
            name,
            "pauses",
            {
                "z_top": width,
                "count": 1,
                "at": [manual["slit_check"]["at"]],
                "spindle_off": True,
            },
        ],
        [name, "depth", {"z_min": _r(saw_z)}],
        [name, "rapids_clear", {"z_top": width}],
        [name, "air_feed", {"z_top": width}],
        [
            name,
            "side_passes",
            {
                "axis": "X",
                "final": _r(radius - slit_depth),
                "raw": _r(radius),
                "max_step": p["slit_step_max_mm"],
                "direction": 1.0,
                "span": depth,
                "below_z": width,
            },
        ],
        [
            name,
            "keep_out",
            {"radius": radius, "boxes": slit_jaws + slit_stacks + [slit_strip]},
        ],
    ]
    # The arbor round the saw, part by part, as cut and as proved in air
    # (Z0 raised proof_raise: every part that much higher over the same
    # shapes): the body above the saw (from its upper face up, as far as the
    # spindle) and the cap with its screw below it (down to the screw head's
    # bound). The spindle nose is over every shape at the cut (checked with
    # process.saw_nose_above_min_mm above).
    for lift, when in ((0.0, ""), (proof_raise, ", proved in air")):
        for part, radius_of, lo in (
            ("the arbor's body above the saw", body_r, thick),
            ("the arbor's cap and screw below the saw", cap_r, -below),
        ):
            expect.append(
                [
                    name,
                    "keep_out",
                    {"radius": radius_of, "boxes": reach(part + when, lo + lift)},
                ]
            )
    for program, key, top in (
        ("DT05_foot_tap", "tap_foot", length),
        ("DT07_pinch_tap", "tap_pinch", width),
        ("DT09_adjuster_tap", "tap_adjuster", depth),
    ):
        expect += [
            [
                program,
                "tap_stop",
                {
                    "tool": tn["tap-guide"],
                    "at": manual[key]["at"],
                    "machine_top": MACHINE_Z_TOP_MM,
                },
            ],
            [program, "air_feed", {"z_top": top}],
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
            doc, f"Cone tip block {key}", ctx["step"], frame["origin"], frame["axes"]
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
