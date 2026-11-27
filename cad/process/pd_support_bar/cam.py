"""FreeCAD CAM recipe for MHA-PD-07, the support bar.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The bar's sizes come
from the feature export (its length, height and depth bands, the two clamp
holes, the two clamp slots and the pivot tap with their sizes, stations and
heights); the blank, the top face's skim, END A's passes, the spot, drill,
counterbore and countersink depths, the slots' programmed widths and ramps,
the three holds and the stacks from ``plan.toml`` ``[parameters]`` and
``milling_cuts``; cutter diameters, flute lengths and end-mill speeds from
the shop (``shop/``), the drills', the counterbore's and the countersinks'
speeds from the plan's operations. Every path is written here
(``rt.custom``): straight lines, and each slot a racetrack of two lines and
two half circles. Typed here, because neither record carries them: the #2
centre drill's catalogue geometry (it sets the spot depth), the twist
drills' 118° point, the chamfer mill's 90° point, the 1/8 in end mill's
diameter tolerance and the tap's major diameter and chamfer, the approach,
safe and clearance heights, the face overhang, the vise jaws' depth and the
parallels' length (keep-out shapes only), the farthest a hole may stand out
past a jaw's side, the least room a pickup needs and the margins the
length, the height and the countersink keep inside their bands.

Route (plan text in ``plan.toml``): one blank of the 3/8 x 1 in 1018 flat
about 17.87 long; the 3/8 thickness is the drawing's depth as supplied and
the bottom edge stays as supplied; the far end stays sawn and filed.

- SB02 (on edge, the bottom edge down, the back face at the fixed jaw): the
  top edge skimmed to the top face T, .993 above the bottom edge.
- SB03 (lying, the front face F up, T at the fixed jaw, the sawn END A just
  out past the jaws' right side): END A milled with the cutter's side to
  X0; clamp holes 1 and 2 and the pivot hole spotted; the clamp holes
  drilled #9 and counterbored with the 5/16 in end mill; the pivot hole
  drilled #29 and its front mouth countersunk.
- SB04 (the same hold slid along the jaws, the milled END A 5.75 in out
  past them; X0 picked up again on it): both clamp slots ramped through
  with the 1/8 in end mill, then their counterbores.
- SB05 (turned over end for end, the back face up, T at the fixed jaw, END
  A 5.75 in out past the jaws' left side; X0 picked up on it): the pivot
  hole's back mouth countersunk.
- SB06 (the same hold): the tap guide brought over the pivot hole, the
  spindle off; the 8-32 thread is cut by hand under it.

The re-clamp: the bar is three times the jaws' width. A #9 drilled 5 in out
past the jaws would bend the bar far over a finish hole's limit, so SB03
keeps its holes within ``HOLE_OUT_MAX_MM`` of a jaw's side. No hold keeps
both END A in reach for a pickup and the slots near the jaws, so the slots
are milled, not drilled: the 1/8 in end mill ramping a few thousandths a
lap, which prechips' deflection screen passes at their overhang. Every
pickup is the same milled END A, ``PICKUP_ROOM_MIN_MM`` or more out past
the jaws. SB02, SB04 and SB05 hold the bar at one station along the jaws,
so SB02's own passes, proved in air, travel farther to each side than any
later pickup (``REACH_RULE_TOL_MM`` to spare for the rule).

Work frames (G54); X0 the milled END A in every one:
- SB02: +X to the right, the bar toward -X; Y0 the fixed jaw (the back
  face); Z0 the parallels' top (the bottom edge), set from the miked width.
- SB03/SB04: the bar toward -X; Y0 the fixed jaw (T); Z0 the front face F.
- SB05/SB06: +X along the bar; Y0 the fixed jaw (T); Z0 the back face.

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock. END
A is milled with the cutter's side in one-way conventional passes; the
slots run clockwise (G2), the wall on the cutter's left: conventional with
the spindle's M3. The thread is tapped by hand (FluidNC cannot rigid-tap;
owner, Pedro, 2026-11-17) under the Fisher spring tap guide in the 1/2 in
R8 collet (owner, Pedro, 2026-11-21), spindle off. FluidNC refuses jogs
while an M0 holds the program, so the tap stop is a file of its own that
ends with M30 over the hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "pd_support_bar"
COMMENT = "MHA-PD-07 support bar"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes; a flat list is one Job.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("SB02_top", ("top_face",)),
    (
        "SB03_end_a",
        (
            ("end_a",),
            ("spot",),
            ("clamp_drill",),
            ("counterbore",),
            ("pivot_drill",),
            ("front_csk",),
        ),
    ),
    ("SB04_slots", ("slots", "slot_counterbores")),
    ("SB05_back_csk", ("back_csk",)),
    ("SB06_tap", ("tap",)),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the tap, the files and the gauges are not).
CAM_TOOLS = (
    "em-half",
    "spot",
    "drill-9",
    "cbore",
    "drill-29",
    "chamfer",
    "em-eighth",
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
# The chamfer mill's included angle (shop tools.chamfer-mill-carbide-1-4-90:
# "90°", its cone running to a point): the drawing's countersink angle.
CHAMFER_POINT_DEG = 90.0
# The 1/8 in end mill may be this much under its nominal diameter, never over
# (shop/common.toml, McMaster's 88815A18 page: -0.0020 to 0.0000 in).
EM_UNDERSIZE_MAX_MM = 0.002 * IN
# The #8 thread's major diameter (ASME B1.1) and a plug tap's chamfer, 5
# threads at 32 to the inch (ASME B94.9): the tap's reach through the bar.
TAP_MAJOR_MM = 0.164 * IN
TAP_CHAMFER_MM = 5 / 32 * IN
# A standard #8 hand tap's thread length (shop-equipment
# tools.taps-unc-hand.members.8-32-plug, .75 in).
TAP_THREAD_MM = 0.75 * IN
# The Fisher tap guide's overall length, 3 1/8 in (its sellers' size,
# cad/config/shop-equipment/ tools.tap-guide-fisher): the most it stands
# below the collet face, taken off the tap stack for the tap's own reach.
TAP_GUIDE_OAL_MM = 3.125 * IN
# A tap file's first motion: G53 G0 to machine Z0, the homed top (as the
# magnifying clamp's recipe: FluidNC sets an axis's machine position to its
# homing mpos_mm, default 0, and Z homes up); the owner (Pedro) confirmed
# it, answered in person 2026-11-21 (cnc rulings record): machine Z = 0 is
# the top of travel after homing.
MACHINE_Z_TOP_MM = 0.0
# Face passes start and finish with the cutter this far clear of the part's
# ends, and end passes this far clear of its faces, so every plunge and
# stepover link is in the air beside it.
APPROACH_MM = 2.54
# Faces reach at least this far past the faces the jaws grip.
FACE_OVERHANG_MM = 0.5
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top.
CLEAR_MM = 5.0
# Keep-outs: each vise jaw's depth outward from the gripped face; the
# parallels' length (4 in, shop-equipment fixtures.parallels-lms-6745).
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 4 * IN
# The .200 in edge finder's tip radius (tools.edge-finder) and the least it
# starts clear of the end it is brought up to.
EDGE_FINDER_RADIUS_MM = 0.1 * IN
PICKUP_APPROACH_MM = 0.1 * IN
# The re-clamp's limits (author's): a drilled hole's centre at most this far
# out past a jaw's side in its hold; a pickup end at least this far out past
# the jaws, so the edge finder and the eye reach it; the rule sets the bar
# along the jaws within 1/16 in, twice over between two holds.
HOLE_OUT_MAX_MM = 0.5 * IN
PICKUP_ROOM_MIN_MM = 1.0 * IN
REACH_RULE_TOL_MM = 0.125 * IN
# The least the cutter's lowest face level stands over the jaw tops.
JAW_CLEAR_MIN_MM = 1.0
# Margins (author's) inside the drawing's bands: the sawn length at each
# limit; the countersink under its maximum (touch-off, tool setter, a worn
# point) and over its hole (a chamfer, not a rub).
LENGTH_MARGIN_MM = 1.0
CSK_MARGIN_MM = 0.25
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# A cutter against its hole's printed band: the shop records the tool's
# nominal inch size, the band's floor is that size rounded; anything closer
# than this is the same size.
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
    return round(value + 0.0, 3) + 0.0


def _box(
    name: str, x: tuple[float, float], y: tuple[float, float], z_top: float
) -> dict[str, Any]:
    return {"name": name, "x": [x[0], x[1]], "y": [y[0], y[1]], "z_top": z_top}


def _agree(plan: dict[str, Any], key: str, value: float) -> None:
    """A plan parameter the recipe recomputes from the export and the shop."""
    stated = plan["parameters"][key]
    if not math.isclose(stated, value, abs_tol=PLAN_TOL_MM):
        raise ValueError(f"process.{key} {stated:g}, the recipe computes {value:.4f}")


def _same(plan: dict[str, Any], cut: str, key: str, value: float, what: str) -> None:
    """Field ``key`` of the milling cut ``cut`` is ``value`` (``what``)."""
    if not math.isclose(_cut(plan, cut, key), value, abs_tol=1e-4):
        raise ValueError(f"'{cut}' {key} is not {what} ({value:g})")


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


def _point(dia: float, included_deg: float = DRILL_POINT_DEG) -> float:
    """The length of a point of ``included_deg`` on ``dia``."""
    return dia / 2 / math.tan(math.radians(included_deg / 2))


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


def _plunged(xy: list[float], top: float, tip: float) -> list[str]:
    """One plunge from the R plane to ``tip`` (no peck: L/D under 3), a rapid
    back to the R plane; moves to and from the hole at the clearance height."""
    clear, r_plane = _r(top + CLEAR_MM), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(tip):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
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


def _end_stations(raw: float, final: float, max_step: float) -> list[float]:
    """End-face positions from just inside ``raw`` to ``final`` in equal
    radial steps no deeper than ``max_step``, ``final`` last."""
    n = math.ceil(abs(raw - final) / max_step - 1e-9)
    return [raw + (final - raw) * (k + 1) / n for k in range(n)]


def _end(xs: list[float], y: tuple[float, float], z: float, top: float) -> list[str]:
    """One-way side passes at the cutter-centre Xs ``xs``, each from
    ``y[0]`` to ``y[1]`` at depth ``z``: plunged beside the part at feed,
    lifted and rapided back to the start beside it between passes. The
    tool starts at the clearance height above ``top``."""
    clear, safe = _r(top + CLEAR_MM), _r(top + SAFE_MM)
    lines = [f"G0 Z{clear:.3f}"]
    for x in xs:
        lines += [
            f"G0 X{_r(x):.3f} Y{_r(y[0]):.3f}",
            f"G0 Z{safe:.3f}",
            f"G1 Z{_r(z):.3f} F{{feed}}",
            f"G1 Y{_r(y[1]):.3f} F{{feed}}",
            f"G0 Z{clear:.3f}",
        ]
    return lines


def _racetrack_xy(
    centre: list[float], half_run: float, offset: float
) -> tuple[float, float, float, float, float]:
    """A slot path's printed coordinates: the two half circles' centre Xs,
    the two straights' Ys (the +Y one first) and their offset from the
    slot's centre line."""
    return (
        _r(centre[0] - half_run),
        _r(centre[0] + half_run),
        _r(centre[1] + offset),
        _r(centre[1] - offset),
        _r(offset),
    )


def _racetrack(
    centre: list[float],
    half_run: float,
    offset: float,
    top: float,
    bottom: float,
    max_step: float,
) -> list[str]:
    """A slot milled round its racetrack, clockwise (G2: the wall on the
    cutter's left). The cutter centre runs ``offset`` from the slot's centre
    line: +X along the +Y straight, round the +X half circle, -X along the
    -Y straight, round the -X half circle. It comes down to ``top``, the
    stock's own face, at the feed and ramps down the two straights, half a
    step on each, in equal laps no deeper than ``max_step`` to ``bottom``;
    one level lap there cleans the last ramp off."""
    x0, x1, ya, yb, e = _racetrack_xy(centre, half_run, offset)
    clear = _r(top + CLEAR_MM)
    depth = top - bottom
    n = math.ceil(depth / max_step - 1e-9)

    def lap(z_half: float, z_end: float) -> list[str]:
        return [
            f"G1 X{x1:.3f} Z{_r(z_half):.3f} F{{feed}}",
            f"G2 X{x1:.3f} Y{yb:.3f} I0.000 J{_r(-e):.3f} F{{feed}}",
            f"G1 X{x0:.3f} Z{_r(z_end):.3f} F{{feed}}",
            f"G2 X{x0:.3f} Y{ya:.3f} I0.000 J{e:.3f} F{{feed}}",
        ]

    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{x0:.3f} Y{ya:.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
        f"G1 Z{_r(top):.3f} F{{feed}}",
    ]
    for k in range(n):
        lines += lap(top - depth * (2 * k + 1) / (2 * n), top - depth * (k + 1) / n)
    return lines + lap(bottom, bottom) + [f"G0 Z{clear:.3f}"]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The bar's bands, holes and slots from the export, each checked against
    the frame the recipe assumes: the ends square to X about the origin, the
    top face on +Y and the bottom face below it, the front face on -Z and
    the back face on +Z, the thickness as supplied and the front face's
    finish one any process meets (no program cuts either face); the clamp
    holes and slots through from the front face along +Z, counterbored from
    it; the pivot tap through from the back face, countersunk 90° on both;
    every station from END A and every height from the top face the
    export's own. The two hook taps are made at assembly: nothing here cuts
    them."""
    f = features["features"]
    end_a = f["end_a"]["plane"]
    far = f["far_end"]
    top = f["top_face"]["plane"]
    bottom = f["bottom_face"]
    front = f["front_face"]["plane"]
    back = f["back_face"]
    if end_a["axis"] != "x" or far["plane"]["axis"] != "x":
        raise ValueError("the ends: expected square to X")
    end_x = end_a["value"]
    if far["length_from"] != "end_a" or not math.isclose(
        far["plane"]["value"] - end_x, far["length_nominal"], abs_tol=1e-3
    ):
        raise ValueError("far_end: its plane is not the length from END A")
    if top["axis"] != "y" or bottom["plane"]["axis"] != "y":
        raise ValueError("the top and bottom faces: expected square to Y")
    top_y = top["value"]
    if bottom["height_from"] != "top_face" or not math.isclose(
        top_y - bottom["plane"]["value"], bottom["height_nominal"], abs_tol=1e-3
    ):
        raise ValueError("bottom_face: its plane is not the height below the top face")
    if front["axis"] != "z" or back["plane"]["axis"] != "z":
        raise ValueError("the front and back faces: expected square to Z")
    front_z = front["value"]
    back_z = back["plane"]["value"]
    if back["depth_from"] != "front_face" or not math.isclose(
        back_z - front_z, back["depth_nominal"], abs_tol=1e-3
    ):
        raise ValueError("back_face: its plane is not the depth from the front face")
    if not back.get("as_supplied"):
        raise ValueError("back_face: expected the bar's thickness as supplied")
    if f["front_face"].get("finish_process") != "any":
        raise ValueError(
            "front_face: expected a finish any process meets (the face stays as supplied)"
        )

    def located(name: str, enters: float) -> dict[str, Any]:
        """A hole or slot's place: through, entering at ``enters``, its
        station from END A and its height from the top face its own X, Y."""
        item = f[name]
        if not item.get("thru"):
            raise ValueError(f"{name}: expected through")
        x, y, z = item["at"]
        if not math.isclose(z, enters, abs_tol=1e-6):
            raise ValueError(f"{name}: it does not enter the face the recipe expects")
        if item["station_from"] != "end_a" or item["height_from"] != "top_face":
            raise ValueError(
                f"{name}: expected its station from END A and height from the top"
            )
        if not math.isclose(x - end_x, item["station_nominal"], abs_tol=1e-3):
            raise ValueError(f"{name}: its X is not its station from END A")
        if not math.isclose(top_y - y, item["height_nominal"], abs_tol=1e-3):
            raise ValueError(f"{name}: its Y is not its height below the top face")
        return {"x": x, "y": y, "station": item["station_nominal"]}

    def counterbored(name: str) -> dict[str, Any]:
        item = f[name]
        if item["axis"] != [0.0, 0.0, 1.0]:
            raise ValueError(f"{name}: expected along +Z from the front face")
        if item["cbore_depth_from"] != "front_face":
            raise ValueError(f"{name}: expected its counterbore from the front face")
        low, high = item["cbore_depth"]
        if not low < item["cbore_depth_nominal"] < high:
            raise ValueError(f"{name}: its counterbore depth is outside its band")
        return {
            **located(name, front_z),
            "cbore_depth": item["cbore_depth_nominal"],
        }

    holes = {}
    for name in ("clamp_hole_1", "clamp_hole_2"):
        item = f[name]
        if item.get("process") != "drill":
            raise ValueError(f"{name}: expected a drilled hole")
        holes[name] = {
            **counterbored(name),
            "dia": item["dia"],
            "cbore_dia": item["cbore_dia"],
        }
    slots = {}
    for name in ("clamp_slot_3", "clamp_slot_4"):
        item = f[name]
        if item["along"] != [1.0, 0.0, 0.0]:
            raise ValueError(f"{name}: expected a slot along X")
        low, high = item["run"]
        if not low < item["run_nominal"] < high:
            raise ValueError(f"{name}: its run is outside its band")
        slots[name] = {
            **counterbored(name),
            "width": item["width"],
            "cbore_width": item["cbore_width"],
            "run": item["run_nominal"],
        }
    depths = {item["cbore_depth"] for item in (*holes.values(), *slots.values())}
    if len(depths) != 1:
        raise ValueError("the counterbores: expected one depth for all four")
    if len({tuple(slot["width"]) for slot in slots.values()}) != 1 or (
        len({tuple(slot["cbore_width"]) for slot in slots.values()}) != 1
        or len({slot["run"] for slot in slots.values()}) != 1
    ):
        raise ValueError("the clamp slots: expected one size for both")
    if len({tuple(hole["dia"]) for hole in holes.values()}) != 1 or (
        len({tuple(hole["cbore_dia"]) for hole in holes.values()}) != 1
    ):
        raise ValueError("the clamp holes: expected one size for both")
    pivot = f["pivot_tap"]
    if pivot["axis"] != [0.0, 0.0, -1.0] or pivot["thread"] != "#8-32 UNC-2B":
        raise ValueError("pivot_tap: expected #8-32 UNC-2B from the back face")
    if pivot["csk_angle_deg"] != CHAMFER_POINT_DEG or pivot["csk_faces"] != "both":
        raise ValueError("pivot_tap: expected 90° countersinks on both faces")
    for name in ("hook_tap_1", "hook_tap_2"):
        if f[name].get("made_at") != "assembly":
            raise ValueError(f"{name}: expected made at assembly, not here")
    return {
        "frame": (end_x, top_y, front_z),
        "back_z": back_z,
        "length_band": far["length"],
        "height_band": bottom["height"],
        "depth_band": back["depth"],
        "holes": holes,
        "slots": slots,
        "cbore_depth": depths.pop(),
        "pivot": {
            **located("pivot_tap", back_z),
            "dia": pivot["dia"],
            "csk_max": pivot["csk_dia_max"],
        },
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    end_x, top_y, front_z = g["frame"]

    # The blank: the bar's thickness is the drawing's depth as supplied (the
    # programs run through the band's top), its width skimmed on the top
    # edge only, its sawn length milled at END A only.
    depth_lo, depth_hi = g["depth_band"]
    bar_t = p["blank_thickness_in"] * IN
    if not depth_lo <= bar_t <= depth_hi:
        raise ValueError(
            f"the bar's {bar_t:.3f} thickness is outside the depth band {g['depth_band']}"
        )
    _agree(plan, "blank_thickness_mm", depth_hi)
    width_min, width_max = p["bar_width_min_mm"], p["bar_width_max_mm"]
    if not width_min <= p["blank_width_in"] * IN <= width_max:
        raise ValueError("the bar's width gate does not hold its nominal width")
    blank_min, blank_max = p["blank_length_in"] * IN, p["blank_length_max_in"] * IN
    _agree(plan, "blank_length_min_mm", blank_min)
    _agree(plan, "blank_length_max_mm", blank_max)
    skim = p["end_a_skim_mm"]
    _agree(plan, "sawn_end_a_mm", -skim)
    _agree(plan, "sawn_pickup_x_mm", EDGE_FINDER_RADIUS_MM + skim)
    bar_min, bar_max = blank_min - skim, blank_max - skim
    _agree(plan, "bar_length_min_mm", bar_min)
    _agree(plan, "bar_length_max_mm", bar_max)
    length_lo, length_hi = g["length_band"]
    if bar_min < length_lo + LENGTH_MARGIN_MM or bar_max > length_hi - LENGTH_MARGIN_MM:
        raise ValueError(
            f"the sawn blank less END A's skim, {bar_min:.3f}-{bar_max:.3f}, is not "
            f"{LENGTH_MARGIN_MM} inside the length band {g['length_band']}"
        )
    _agree(plan, "length_dro_min_mm", length_lo + EDGE_FINDER_RADIUS_MM)
    _agree(plan, "length_dro_max_mm", length_hi + EDGE_FINDER_RADIUS_MM)

    # The top skim: the height one level over its band's floor; the narrowest
    # bar still loses a level at its middle, and at its ends too with the
    # bow the gate admits (the hollow edge down: the top's ends stand low).
    height = p["height_target_mm"]
    level_max = p["face_step_max_mm"]
    height_lo, height_hi = g["height_band"]
    if not height_lo + level_max <= height <= width_min - level_max + 1e-9:
        raise ValueError(
            f"the top face at {height:.4f} leaves under one level over the height "
            f"band's floor {height_lo} or off the narrowest bar {width_min}"
        )
    if width_min - height < p["bow_max_mm"] - 1e-9:
        raise ValueError(
            "the bow the gate admits is more than the narrowest bar's skim"
        )
    if height + p["bow_max_mm"] > height_hi:
        raise ValueError("a bowed bar's ends would stand over the height band")

    em_record = _shop_tool(plan, shop, "em-half")
    em = em_record["diameter_mm"]
    r = em / 2
    step_max = p["face_stepover_max_mm"]
    for name in ("top face", "end a"):
        _same(plan, name, "cutter_dia_mm", em, "the end mill's diameter")
    # The top skim runs at its measured setting, END A (deeper than it was
    # measured) at the chart's.
    face_rpm, face_feed = _setting(plan, shop, "top face")
    end_rpm, end_feed = _setting(plan, shop, "end a")
    _agree(plan, "face_cutter_dia_mm", em)
    _same(plan, "top face", "radial_woc_mm", step_max, "process.face_stepover_max_mm")
    _same(plan, "top face", "axial_doc_mm", level_max, "process.face_step_max_mm")
    top_levels = _levels(width_max, height, level_max)

    # END A: the cutter's side, one level from F to end_past_mm under the
    # thickest bar's back face (into the air past the stacks' ends), in
    # equal radial steps no deeper than end_step_max_mm.
    end_step = p["end_step_max_mm"]
    end_z = -(depth_hi + p["end_past_mm"])
    _agree(plan, "end_axial_doc_mm", -end_z)
    _same(plan, "end a", "radial_woc_mm", end_step, "process.end_step_max_mm")
    _same(plan, "end a", "axial_doc_mm", -end_z, "process.end_axial_doc_mm")
    if em_record["flute_length_mm"] < -end_z:
        raise ValueError("the 1/2 in end mill's flutes are shorter than END A's cut")
    # The end mill's collet: its nose half_mill_projection_mm above the tip
    # stays clear of the bar's top (over the jaws, the stacks and the pin)
    # at the deepest end-mill cut, END A's one level.
    em_depth = max(width_max - height, -end_z)
    if p["half_mill_projection_mm"] < em_depth + CLEAR_MM:
        raise ValueError(
            f"the 1/2 in end mill's collet would reach the bar {em_depth:.3f} below its top"
        )
    end_faces = _end_stations(skim, 0.0, end_step)

    # Holes: the spot under every drill; each cutter against its hole's
    # printed band; the tips through the back face into the air.
    holes, slots, pivot = g["holes"], g["slots"], g["pivot"]

    def tool_dia(tool: str) -> float:
        return _shop_tool(plan, shop, tool)["diameter_mm"]

    d9, d29, d_cbore, d_chamfer = (
        tool_dia(t) for t in ("drill-9", "drill-29", "cbore", "chamfer")
    )
    for name, hole in holes.items():
        for what, dia, band in (
            ("drill", d9, hole["dia"]),
            ("counterbore", d_cbore, hole["cbore_dia"]),
        ):
            if not band[0] - SIZE_TOL_MM <= dia <= band[1]:
                raise ValueError(f"the {what} Ø{dia} is outside {name}'s band {band}")
    tap = _shop_tool(plan, shop, "tap-8-32")
    if not math.isclose(d29, tap["tap_drill_mm"], abs_tol=1e-6):
        raise ValueError(
            f"#29 Ø{d29} is not the 8-32 tap's drill {tap['tap_drill_mm']}"
        )
    if not pivot["dia"][0] - SIZE_TOL_MM <= d29 <= pivot["dia"][1]:
        raise ValueError(f"#29 Ø{d29} is outside the pivot tap drill's band")
    spot = p["spot_dia_mm"]
    if spot >= min(d9, d29):
        raise ValueError("the spot is not under every drill: it would chamfer a hole")
    spot_depth = _spot_depth(spot)
    tips = {
        "clamp_drill": -(depth_hi + p["drill_past_mm"] + _point(d9)),
        "pivot_drill": -(depth_hi + p["drill_past_mm"] + _point(d29)),
    }
    _agree(plan, "drill_9_tip_mm", tips["clamp_drill"])
    _agree(plan, "drill_29_tip_mm", tips["pivot_drill"])
    cbore_z = -g["cbore_depth"]
    # The countersinks: under the drawing's maximum and over the tap drill
    # by the margin; the chamfer mill's point half the mouth below the face
    # (90°), inside its flutes.
    csk = p["csk_dia_mm"]
    if not d29 + CSK_MARGIN_MM <= csk <= pivot["csk_max"] - CSK_MARGIN_MM:
        raise ValueError(
            f"the countersink Ø{csk} is not {CSK_MARGIN_MM} inside Ø{d29} "
            f"to the drawing's Ø{pivot['csk_max']} maximum"
        )
    csk_z = -_point(csk, CHAMFER_POINT_DEG)
    _agree(plan, "csk_tip_mm", csk_z)
    chamfer_record = _shop_tool(plan, shop, "chamfer")
    if chamfer_record["flute_length_mm"] < -csk_z or csk > d_chamfer:
        raise ValueError(
            "the countersink is deeper or wider than the chamfer mill's cone"
        )
    for cut, dia in (
        ("spot", spot),
        ("clamp drill", d9),
        ("counterbore", d_cbore),
        ("pivot drill", d29),
        ("front countersink", csk),
        ("back countersink", csk),
    ):
        _same(plan, cut, "cutter_dia_mm", dia, "its tool's cutting diameter")
    speeds = {
        cut: _setting(plan, shop, cut)
        for cut in (
            "spot",
            "clamp drill",
            "counterbore",
            "pivot drill",
            "front countersink",
            "back countersink",
        )
    }
    if speeds["back countersink"] != speeds["front countersink"]:
        raise ValueError("the two countersinks run at different speeds")

    # The slots: the 1/8 in end mill round a racetrack. The programmed
    # widths hold the drawing's bands for a cutter anywhere in its diameter
    # tolerance; the counterbore's path takes its step off the wall the
    # through path left.
    em8_record = _shop_tool(plan, shop, "em-eighth")
    em8 = em8_record["diameter_mm"]
    r8 = em8 / 2
    _agree(plan, "slot_cutter_dia_mm", em8)
    slot = slots["clamp_slot_3"]
    half_run = slot["run"] / 2
    widths = {
        "slot": (p["slot_width_mm"], slot["width"]),
        "slot_cbore": (p["slot_cbore_width_mm"], slot["cbore_width"]),
    }
    offsets = {}
    for key, (width, band) in widths.items():
        if not band[0] <= width - EM_UNDERSIZE_MAX_MM or not width <= band[1]:
            raise ValueError(
                f"process.{key}_width_mm {width} cut with a cutter up to "
                f"{EM_UNDERSIZE_MAX_MM:.4f} under size leaves the band {band}"
            )
        offsets[key] = (width - em8) / 2
        _agree(plan, f"{key}_cutter_min_mm", band[0] - 2 * offsets[key])
        _agree(plan, f"{key}_cutter_max_mm", band[1] - 2 * offsets[key])
    e_slot, e_cbore = offsets["slot"], offsets["slot_cbore"]
    if e_slot >= r8:
        raise ValueError("the slot's path leaves an island down its middle")
    if e_cbore - r8 >= p["slot_width_mm"] / 2:
        raise ValueError("the counterbore's path leaves a ridge beside the slot")
    # The most the counterbore's path meets: round a half circle the cutter
    # wraps the slot's end wall (radius half the slot's width) over the
    # angle a straight cut this wide would.
    wall = p["slot_width_mm"] / 2
    cbore_radial = r8 + (e_cbore**2 + r8**2 - wall**2) / (2 * e_cbore)
    if cbore_radial < e_cbore + r8 - wall:
        raise ValueError("the counterbore's half circles meet less than its straights")
    _agree(plan, "slot_cbore_radial_mm", cbore_radial)
    slot_z = -(depth_hi + p["slot_past_mm"])
    _agree(plan, "slot_bottom_mm", slot_z)
    if em8_record["flute_length_mm"] < -slot_z:
        raise ValueError(
            "the 1/8 in end mill's flutes are shorter than the slots' depth"
        )
    if p["eighth_mill_projection_min_mm"] < -slot_z + 2 * SAFE_MM:
        raise ValueError(
            "the 1/8 in end mill's collet would reach the bar at the slots' bottom"
        )
    if p["eighth_mill_projection_max_mm"] < p["eighth_mill_projection_min_mm"]:
        raise ValueError("the 1/8 in end mill's projection band is empty")
    slot_rpm, slot_feed = _setting(plan, shop, "slot")
    if _setting(plan, shop, "slot counterbore") != (slot_rpm, slot_feed):
        raise ValueError("'slot counterbore' runs at another setting than 'slot'")
    for cut, radial, step in (
        ("slot", em8, p["slot_step_max_mm"]),
        ("slot counterbore", cbore_radial, p["slot_cbore_step_max_mm"]),
    ):
        _same(plan, cut, "cutter_dia_mm", em8, "the 1/8 in end mill's diameter")
        _same(plan, cut, "radial_woc_mm", radial, "the stock its path meets")
        _same(plan, cut, "axial_doc_mm", step, "its step a lap")
    far_slot = max(s["station"] for s in slots.values())
    _agree(plan, "slot_far_station_mm", far_slot + half_run + e_slot)
    _agree(plan, "slot_cbore_far_station_mm", far_slot + half_run + e_cbore)

    # Vise: the jaws, the stacks and each hold's reach.
    jaw_h, jaw_w = p["vise_jaw_height_mm"], p["vise_jaw_width_mm"]
    vise = shop["workholding"]["vise-pm-6"]
    for key, record in (
        ("vise_jaw_height_mm", "jaw_height_mm"),
        ("vise_jaw_width_mm", "jaw_width_mm"),
        ("vise_bed_height_mm", "bed_height_mm"),
    ):
        _agree(plan, key, vise[record])
    t = p["parallel_thickness_mm"]
    pin = 0.125 * IN
    top_grip = jaw_h - p["top_riser_height_mm"]
    lying_grip = jaw_h - p["riser_height_mm"]
    _agree(plan, "top_grip_mm", top_grip)
    _agree(plan, "top_jaw_clear_mm", height - top_grip)
    _agree(plan, "lying_grip_mm", lying_grip)
    fraction = shop["limits"]["vise_grip_fraction_min"]
    grip_min = shop["limits"]["vise_grip_min_mm"]
    # (grip, the part's height in the jaws, the lowest face level above them)
    for name, grip, part_h, lowest in (
        ("SB02", top_grip, width_max, height),
        ("SB03-SB06", lying_grip, depth_hi, None),
    ):
        if grip < grip_min or grip < fraction * part_h - 1e-9:
            raise ValueError(
                f"{name}: the jaws grip {grip:.3f} of {part_h:.3f}, under the shop's minimum"
            )
        if lowest is not None and lowest - grip < JAW_CLEAR_MIN_MM:
            raise ValueError(
                f"{name}: the lowest face level {lowest:.3f} is not clear above the jaw tops {grip:.3f}"
            )
    if lying_grip >= depth_lo:
        raise ValueError(
            "SB03-SB06: the thinnest bar's top does not stand above the jaws"
        )

    # SB03 (hold A): the sawn END A end_overhang_mm out past the jaws. The
    # jaws' span from the milled END A, toward the far end.
    out = p["end_overhang_mm"]
    span_a = (out - skim, out - skim + jaw_w)
    _agree(plan, "a_clamp_start_mm", span_a[0])
    _agree(plan, "a_clamp_end_mm", span_a[1])
    if span_a[0] <= 0.0:
        raise ValueError("SB03: the jaws reach the milled END A")
    for name, station in (
        *((n, h["station"]) for n, h in holes.items()),
        ("pivot_tap", pivot["station"]),
    ):
        if not span_a[0] - HOLE_OUT_MAX_MM <= station <= span_a[1] + HOLE_OUT_MAX_MM:
            raise ValueError(
                f"{name} at {station:.3f} from END A stands over {HOLE_OUT_MAX_MM} out "
                f"past SB03's jaws {span_a[0]:.3f}-{span_a[1]:.3f}"
            )
    # SB02, SB04, SB05 (hold B): the milled END A pickup_out_mm out past the
    # jaws (SB02's sawn one the skim farther).
    pick = p["pickup_out_mm"]
    span_b = (pick, pick + jaw_w)
    _agree(plan, "top_out_mm", pick + skim)
    _agree(plan, "b_clamp_end_mm", span_b[1])
    if pick < PICKUP_ROOM_MIN_MM:
        raise ValueError(f"the pickup end stands only {pick:.3f} out past the jaws")
    if not span_b[0] <= pivot["station"] <= span_b[1]:
        raise ValueError(
            "SB05/SB06: the pivot hole is not between the jaws for the tap"
        )
    if min(s["station"] for s in slots.values()) - half_run - e_cbore - r8 <= span_b[1]:
        raise ValueError("SB04: a slot is not out past the jaws")
    _agree(plan, "z_touch_a_x_mm", -_mid(list(span_a)))
    _agree(plan, "z_touch_b_x_mm", -_mid(list(span_b)))
    _agree(plan, "z_touch_c_x_mm", _mid(list(span_b)))
    _agree(plan, "z_touch_top_y_mm", -bar_t / 2)
    _agree(plan, "z_touch_lying_y_mm", -height / 2)
    # Reach: SB02's cutter centre travels this far to each side of the jaws'
    # middle; every later pickup, the rule's error twice over, stays inside.
    centre_b = _mid(list(span_b))
    face_reach = {
        "end_a": centre_b + skim + r + APPROACH_MM,
        "far": bar_max + r + APPROACH_MM - centre_b,
    }
    touch = EDGE_FINDER_RADIUS_MM + PICKUP_APPROACH_MM
    for name, side, need in (
        ("SB04's X0 pickup", "end_a", centre_b + touch),
        ("SB04's length check", "far", bar_max + touch - centre_b),
        # Turned over, END A lies where SB02's far end did.
        ("SB05's X0 pickup", "far", centre_b + touch),
    ):
        if need + REACH_RULE_TOL_MM > face_reach[side]:
            raise ValueError(
                f"{name} needs {need:.3f} of travel from the jaws' middle, over the "
                f"{face_reach[side]:.3f} SB02 proves less {REACH_RULE_TOL_MM} for the rule"
            )

    # The tap: its point through the front face by its chamfer, its shank
    # out of the hole; the guide-and-tap stack under the spindle's opening.
    tap_point = p["tap_point_depth_mm"]
    if not depth_hi + TAP_CHAMFER_MM <= tap_point <= TAP_THREAD_MM:
        raise ValueError(
            f"process.tap_point_depth_mm {tap_point} is not between the bar plus the "
            f"tap's chamfer {depth_hi + TAP_CHAMFER_MM:.3f} and its thread {TAP_THREAD_MM}"
        )
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["riser_height_mm"]
        - depth_hi
        - p["r8_collet_gauge_mm"]
    )
    stack_max = math.floor(stack / 0.254 + 1e-9) * 0.254
    _agree(plan, "tap_stack_max_mm", stack_max)
    _agree(
        plan,
        "tap_wrench_reach_max_mm",
        math.floor((stack_max - TAP_GUIDE_OAL_MM) / 0.254 + 1e-9) * 0.254,
    )

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)); X0 the milled END A in
    # every one.
    frames = {
        # On edge, the bottom edge on the parallels, the back face against
        # the fixed jaw: T at the height, the bar toward -X.
        "top": _frame([end_x, top_y - height, g["back_z"]], [0, 0, 1], [0, 1, 0]),
        # Lying, F up, T against the fixed jaw: the bar toward -X.
        "front": _frame([end_x, top_y, front_z], [0, 1, 0], [0, 0, -1]),
        # Lying, the back face up, T against the fixed jaw: the bar toward +X.
        "back": _frame([end_x, top_y, g["back_z"]], [0, 1, 0], [0, 0, 1]),
    }
    for key, frame in frames.items():
        corner = _to(frame, [end_x, top_y, front_z])
        if not math.isclose(corner[0], 0.0, abs_tol=1e-6):
            raise ValueError(f"{key}: END A is not at X0")
    xy = {}
    for name, item in (*holes.items(), *slots.items(), ("pivot_tap", pivot)):
        x, y, _z = _to(frames["front"], [item["x"], item["y"], front_z])
        xy[name] = [_r(x), _r(y)]
    x, y, _z = _to(frames["back"], [pivot["x"], pivot["y"], g["back_z"]])
    pivot_back = [_r(x), _r(y)]
    # The stacks: one against the fixed jaw under T's strip, one under the
    # bottom edge's strip (the outer one and the pin beyond the bar). Every
    # hole and slot, and the widest thing through it, exits between them.
    through = {
        **dict.fromkeys(holes, d9 / 2),
        **dict.fromkeys(slots, p["slot_width_mm"] / 2),
        "pivot_tap": max(d29, TAP_MAJOR_MM) / 2,
    }
    for name, reach in through.items():
        y = xy[name][1]
        if not (-height + t < y - reach and y + reach < -t):
            raise ValueError(
                f"{name} at Y {y} reaches a stack ({t} wide at T and at the bottom edge)"
            )

    # Stocks: (X, Y, Z) ranges of each hold's bar.
    stocks = {
        "top": ((-bar_max, skim), (-bar_t, 0.0), (0.0, width_max)),
        "a": ((-bar_max, skim), (-height, 0.0), (-depth_hi, 0.0)),
        "b": ((-bar_max, 0.0), (-height, 0.0), (-depth_hi, 0.0)),
        "c": ((0.0, bar_max), (-height, 0.0), (-depth_hi, 0.0)),
    }
    models = {"top": "top", "a": "front", "b": "front", "c": "back"}

    em_tool = {
        "tool": "em-half",
        "dia": em,
        "shape": "endmill",
        "flutes": 3,
        "rpm": face_rpm,
        "feed": face_feed,
        "plunge": face_feed,
    }
    end_tool = {**em_tool, "rpm": end_rpm, "feed": end_feed, "plunge": end_feed}

    def point_tool(tool: str, dia: float, cut: str, angle: float) -> dict[str, Any]:
        rpm, feed = speeds[cut]
        return {
            "tool": tool,
            "dia": dia,
            "shape": "drill",
            "tip_angle": angle,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
        }

    face_x = (-bar_max - r - APPROACH_MM, skim + r + APPROACH_MM)
    bar_ys = _stations((-bar_t, 0.0), r, step_max)
    beside = (-height - r - APPROACH_MM, r + APPROACH_MM)
    end_xs = [x + r for x in end_faces]
    clamp_names = list(holes)
    slot_names = list(slots)
    spot_names = [*clamp_names, "pivot_tap"]

    def plunges(names_: list[str], tip: float) -> list[str]:
        return [line for n in names_ for line in _plunged(xy[n], 0.0, tip)]

    def hole_job(
        key: str, label: str, tool: dict[str, Any], names_: list[str], tip: float
    ) -> dict[str, Any]:
        return {
            **tool,
            "frame": "a",
            "label": key.replace("_", " "),
            "stock": stocks["a"],
            "ops": [[key, label, plunges(names_, tip)]],
        }

    chamfer_tool = point_tool(
        "chamfer", d_chamfer, "front countersink", CHAMFER_POINT_DEG
    )
    jobs = [
        {
            **em_tool,
            "frame": "top",
            "label": "top face",
            "stock": stocks["top"],
            "ops": [
                [
                    "top_face",
                    "skim the top edge down to the top face",
                    _face(top_levels, width_max, face_x, bar_ys),
                ]
            ],
        },
        {
            **end_tool,
            "frame": "a",
            "label": "end a",
            "stock": stocks["a"],
            "ops": [["end_a", "mill END A to X0", _end(end_xs, beside, end_z, 0.0)]],
        },
        hole_job(
            "spot",
            "spot clamp holes 1 and 2 and the pivot hole",
            point_tool(
                "spot", CENTRE_DRILL["body_mm"], "spot", CENTRE_DRILL["point_deg"]
            ),
            spot_names,
            -spot_depth,
        ),
        hole_job(
            "clamp_drill",
            "drill clamp holes 1 and 2 #9 through",
            point_tool("drill-9", d9, "clamp drill", DRILL_POINT_DEG),
            clamp_names,
            tips["clamp_drill"],
        ),
        hole_job(
            "counterbore",
            "counterbore clamp holes 1 and 2",
            {
                "tool": "cbore",
                "dia": d_cbore,
                "shape": "endmill",
                "flutes": 2,
                "rpm": speeds["counterbore"][0],
                "feed": speeds["counterbore"][1],
                "plunge": speeds["counterbore"][1],
            },
            clamp_names,
            cbore_z,
        ),
        hole_job(
            "pivot_drill",
            "drill the pivot hole #29 through",
            point_tool("drill-29", d29, "pivot drill", DRILL_POINT_DEG),
            ["pivot_tap"],
            tips["pivot_drill"],
        ),
        hole_job(
            "front_csk",
            "countersink the pivot hole's front mouth",
            chamfer_tool,
            ["pivot_tap"],
            csk_z,
        ),
        {
            "tool": "em-eighth",
            "dia": em8,
            "shape": "endmill",
            "flutes": 3,
            "rpm": slot_rpm,
            "feed": slot_feed,
            "plunge": slot_feed,
            "frame": "b",
            "label": "slots",
            "stock": stocks["b"],
            "ops": [
                [
                    "slots",
                    "ramp both clamp slots through",
                    [
                        line
                        for n in slot_names
                        for line in _racetrack(
                            xy[n], half_run, e_slot, 0.0, slot_z, p["slot_step_max_mm"]
                        )
                    ],
                ],
                [
                    "slot_counterbores",
                    "ramp both clamp slots' counterbores",
                    [
                        line
                        for n in slot_names
                        for line in _racetrack(
                            xy[n],
                            half_run,
                            e_cbore,
                            0.0,
                            cbore_z,
                            p["slot_cbore_step_max_mm"],
                        )
                    ],
                ],
            ],
        },
        {
            **chamfer_tool,
            "frame": "c",
            "label": "back csk",
            "stock": stocks["c"],
            "ops": [
                [
                    "back_csk",
                    "countersink the pivot hole's back mouth",
                    _plunged(pivot_back, 0.0, csk_z),
                ]
            ],
        },
    ]

    # The tap stop (as the column clamp's): the tap guide loaded by the
    # file's own M6, Z to the machine's top before any XY, over the pivot
    # hole, M30: the controller ends Idle for the operator's jog.
    manual = {
        "tap": {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": "SPINDLE STAYS OFF. NEXT: 8-32 TAP IN THE PIVOT HOLE",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{pivot_back[0]:.3f} Y{pivot_back[1]:.3f}",
                "(8-32 TAP IN THE PIVOT HOLE. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN"
                " THE WRENCH. TAP BY HAND UNTIL THE MARK ON THE TAP REACHES THE BACK FACE,"
                " PUSHING THE POINT HOME AGAIN EACH 1/2 IN. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": pivot_back,
        }
    }

    # Keep-outs: the jaws beside the gripped span, up to the jaw tops; lying,
    # the three stacks and the .125 pin, the thinnest bar setting them
    # highest under Z0 (the face that is up).
    def jaws(
        x: tuple[float, float], across: float, z_top: float
    ) -> list[dict[str, Any]]:
        return [
            _box("moving jaw", x, (-across - JAW_DEPTH_MM, -across), z_top),
            _box("fixed jaw", x, (0.0, JAW_DEPTH_MM), z_top),
        ]

    def lying_keep(x: tuple[float, float]) -> list[dict[str, Any]]:
        mid = _mid(list(x))
        along = (mid - PARALLEL_LENGTH_MM / 2, mid + PARALLEL_LENGTH_MM / 2)
        seat = -depth_lo
        return jaws(x, height, seat + lying_grip) + [
            _box("stack at the fixed jaw", along, (-t, 0.0), seat),
            _box("stacks at the moving jaw", along, (-height - t, -height + t), seat),
            _box(
                ".125 pin at the bottom edge", x, (-height - pin, -height), seat + pin
            ),
        ]

    jaws_a = (-span_a[1], -span_a[0])
    jaws_b = (-span_b[1], -span_b[0])
    keep = {
        "top": jaws(jaws_b, bar_t, top_grip),
        "a": lying_keep(jaws_a),
        "b": lying_keep(jaws_b),
        "c": lying_keep(span_b),
    }

    tn = numbers
    expect: list[list[Any]] = []

    # SB02: the face.
    expect += [
        [
            "SB02_top",
            "tool_changes",
            {"z_top": width_max, "tools": [tn["em-half"]], "loads_first": True},
        ],
        ["SB02_top", "spindle", {"rpm": [[face_rpm]]}],
        ["SB02_top", "pauses", {"z_top": width_max, "count": 0}],
        ["SB02_top", "depth", {"z_min": _r(height)}],
        ["SB02_top", "rapids_clear", {"z_top": width_max}],
        ["SB02_top", "air_feed", {"z_top": width_max}],
        *[
            [
                "SB02_top",
                "face_passes",
                {
                    "z": _r(z),
                    "y": [-bar_t, 0.0],
                    "max_engagement": step_max,
                    "radius": r,
                    "span": bar_min,
                    "overhang": FACE_OVERHANG_MM,
                },
            ]
            for z in top_levels
        ],
        ["SB02_top", "keep_out", {"radius": r, "boxes": keep["top"]}],
    ]

    def hole_checks(
        centres: list[list[float]], bottom: float, radius: float, frame: str
    ) -> list[list[Any]]:
        return [
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": 0.0, "open_holes": centres}],
            ["vertical_below_top", {"z_top": 0.0}],
            ["air_feed", {"z_top": 0.0}],
            ["keep_out", {"radius": radius, "boxes": keep[frame]}],
        ]

    def centres(names_: list[str]) -> list[list[float]]:
        return [xy[n] for n in names_]

    # SB03: END A's passes run +Y, the stock on each pass's left:
    # conventional with the spindle's M3.
    end_final, end_raw = r, skim + r
    end_checks = [
        ["depth", {"z_min": _r(end_z)}],
        ["rapids_clear", {"z_top": 0.0}],
        ["air_feed", {"z_top": 0.0}],
        [
            "side_passes",
            {
                "axis": "X",
                "final": _r(end_final),
                "raw": _r(end_raw),
                "max_step": end_step,
                "direction": 1.0,
                "span": height,
                "below_z": 0.0,
            },
        ],
        [
            "engagement",
            {
                # The bar's END A end only: the passes meet nothing else.
                "stock": ((-4 * em, skim), stocks["a"][1], stocks["a"][2]),
                "radius": r,
                "max_radial": end_step,
                "z": _r(end_z),
                "window": [[end_final, end_raw], [beside[0], beside[1]]],
                "min_length": height,
                "cut": "conventional",
            },
        ],
        ["keep_out", {"radius": r, "boxes": keep["a"]}],
    ]
    sb03 = [
        (end_rpm, end_checks),
        (
            speeds["spot"][0],
            hole_checks(
                centres(spot_names), -spot_depth, CENTRE_DRILL["body_mm"] / 2, "a"
            ),
        ),
        (
            speeds["clamp drill"][0],
            hole_checks(centres(clamp_names), tips["clamp_drill"], d9 / 2, "a"),
        ),
        (
            speeds["counterbore"][0],
            hole_checks(centres(clamp_names), cbore_z, d_cbore / 2, "a"),
        ),
        (
            speeds["pivot drill"][0],
            hole_checks(centres(["pivot_tap"]), tips["pivot_drill"], d29 / 2, "a"),
        ),
        (
            speeds["front countersink"][0],
            hole_checks(centres(["pivot_tap"]), csk_z, d_chamfer / 2, "a"),
        ),
    ]
    expect += [
        [
            "SB03_end_a",
            "tool_changes",
            {
                "z_top": 0.0,
                "tools": [
                    tn[t]
                    for t in (
                        "em-half",
                        "spot",
                        "drill-9",
                        "cbore",
                        "drill-29",
                        "chamfer",
                    )
                ],
                "loads_first": True,
            },
        ],
        ["SB03_end_a", "spindle", {"rpm": [[rpm] for rpm, _checks in sb03]}],
        ["SB03_end_a", "pauses", {"z_top": 0.0, "count": 0}],
        ["SB03_end_a", "depth", {"z_min": _r(min(end_z, *tips.values()))}],
    ]
    for k, (_rpm, checks) in enumerate(sb03):
        expect += [[f"SB03_end_a@{k}", check, kwargs] for check, kwargs in checks]

    # SB04: each slot's through path spanning the programmed width less
    # the cutter, to the slots' bottom; the counterbore's path by the
    # moves ending on each of its straights' lines, no deeper than its floor; the
    # floor cleared all round; every arc clockwise. Each path's level lap
    # (the ramps' entries start in solid stock, which no radial width
    # describes) meets no more than the plan declares, the counterbore's
    # on the cutter's left.
    expect += [
        [
            "SB04_slots",
            "tool_changes",
            {"z_top": 0.0, "tools": [tn["em-eighth"]], "loads_first": True},
        ],
        ["SB04_slots", "spindle", {"rpm": [[slot_rpm]]}],
        ["SB04_slots", "pauses", {"z_top": 0.0, "count": 0}],
        ["SB04_slots", "depth", {"z_min": _r(slot_z)}],
        ["SB04_slots", "rapids_clear", {"z_top": 0.0}],
        ["SB04_slots", "air_feed", {"z_top": 0.0}],
        ["SB04_slots", "keep_out", {"radius": r8, "boxes": keep["b"]}],
    ]
    floor_ring = (p["slot_width_mm"] + p["slot_cbore_width_mm"]) / 4
    for n in slot_names:
        cx, cy = xy[n]
        x0, x1, ya, yb, e = _racetrack_xy(xy[n], half_run, e_slot)
        _x0, _x1, ya_c, yb_c, e_c = _racetrack_xy(xy[n], half_run, e_cbore)
        box = (
            (cx - 4 * em8, cx + 4 * em8),
            (cy - 4 * em8, cy + 4 * em8),
            stocks["b"][2],
        )
        margin = (e_c - e) / 2
        expect += [
            [
                "SB04_slots",
                "bounds",
                {
                    "window": [
                        [x0 - e - margin, x1 + e + margin],
                        [yb - margin, ya + margin],
                    ],
                    "x": [_r(x0 - e), _r(x1 + e)],
                    "y": [yb, ya],
                    "z_min": _r(slot_z),
                    "arc": "G2",
                    "z_top": 0.0,
                },
            ],
            *[
                [
                    "SB04_slots",
                    "bounds",
                    {
                        "window": [
                            [x0 - margin, x1 + margin],
                            [y - margin, y + margin],
                        ],
                        "x": x,
                        "y": [yb_c, ya_c],
                        "z_min": _r(cbore_z),
                        "arc": "G2",
                        "z_top": 0.0,
                    },
                ]
                # The moves ending on each straight's line: the straight
                # itself and the half circle that runs into it.
                for y, x in (
                    (ya_c, [_r(x0 - e_c), x1]),
                    (yb_c, [x0, _r(x1 + e_c)]),
                )
            ],
            [
                "SB04_slots",
                "cleared",
                {
                    "points": [
                        [cx, _r(cy + floor_ring)],
                        [cx, _r(cy - floor_ring)],
                        [_r(x1 + floor_ring), cy],
                        [_r(x0 - floor_ring), cy],
                    ],
                    "radius": r8,
                    "z": _r(cbore_z),
                },
            ],
            [
                "SB04_slots",
                "engagement",
                {
                    "stock": box,
                    "radius": r8,
                    "max_radial": em8,
                    "z": _r(slot_z),
                    "window": [
                        [x0 - e - margin, x1 + e + margin],
                        [yb - margin, ya + margin],
                    ],
                },
            ],
            [
                "SB04_slots",
                "engagement",
                {
                    "stock": box,
                    "radius": r8,
                    "max_radial": cbore_radial,
                    "z": _r(cbore_z),
                    "window": [
                        [x0 - e_c - margin, x1 + e_c + margin],
                        [yb_c - margin, ya_c + margin],
                    ],
                    "cut": "conventional",
                },
            ],
        ]

    # SB05 and the tap stop.
    expect += [
        [
            "SB05_back_csk",
            "tool_changes",
            {"z_top": 0.0, "tools": [tn["chamfer"]], "loads_first": True},
        ],
        ["SB05_back_csk", "spindle", {"rpm": [[speeds["back countersink"][0]]]}],
        ["SB05_back_csk", "pauses", {"z_top": 0.0, "count": 0}],
        ["SB05_back_csk", "depth", {"z_min": _r(csk_z)}],
        *[
            ["SB05_back_csk", check, kwargs]
            for check, kwargs in hole_checks([pivot_back], csk_z, d_chamfer / 2, "c")
        ],
        [
            "SB06_tap",
            "tap_stop",
            {
                "tool": tn["tap-guide"],
                "at": manual["tap"]["at"],
                "machine_top": MACHINE_Z_TOP_MM,
            },
        ],
        ["SB06_tap", "air_feed", {"z_top": 0.0}],
    ]

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": frames,
        "models": models,
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
            doc, f"Support bar {key}", ctx["step"], frame["origin"], frame["axes"]
        )
        for key, frame in ctx["frames"].items()
    }
    ops: dict[str, Any] = {}
    for section in ctx["jobs"]:
        target = rt.job(
            doc,
            section["label"],
            [models[ctx["models"][section["frame"]]]],
            section["stock"],
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
