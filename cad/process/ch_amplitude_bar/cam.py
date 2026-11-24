"""FreeCAD CAM recipe for MHA-CH-01, the amplitude bar.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The bar's sizes come
from the feature export (its section, length, both notches and the pin
hole); the blank, the skims, the steps, the load (``bars_per_load`` bars)
and the holding
from ``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter diameters,
speeds and feeds from the shop (``shop/``) and the plan's authored drill and
saw settings. Every path is written here (``rt.custom``): straight lines a
recipe can state exactly. Typed here, because neither record carries them:
the #1 centre drill's catalogue geometry (it sets the spot depth), the twist
drill's 118° point, the approach, safe and clearance heights and the vise
jaws' depth (keep-out shapes only).

Route (plan text in ``plan.toml``): ``bars_per_load`` 1/4 in square bars
per load side by side across the jaws on the riser: two plain 6061 blocks
end to end on the vise bed against the fixed jaw, narrower than the load
(the moving jaw grips the last bar, never the riser) and wide enough to
seat every bar at least half its width. Foot ends past the left jaw side:
CA01 faces them, CA02 saws the foot notch. Rolled over, top ends past the
right jaw side: CA03 faces them to the length, CA04 saws the top notch,
CA05 spots, drills and reams the pin holes through both cheeks. The riser
lifts the bars so each holder's nose, its tool set out by its stated
projection, stays above the jaw tops at the deepest cut. CA00, once for a
new riser, faces its two blocks side by side along the jaws, each standing
across them on both 1 in parallels, their tops over the jaw tops: passes
past both jaw sides, from over the fixed jaw to past the moving jaw. Every
P2-P4 bar's ledge is cut from the P1 bar's saw Z0: the plan's ledge budget
(touch-off, the seat sweep's acceptance and its reading error, the two
measuring terms no finer than the shop's gauges) is checked against each
ledge band.

Work frames (G54), each set in its setup:
- CA00: X0 the vise's left jaw side, Y0 the fixed jaw, Z0 the higher riser
  top on its parallels.
- CA01, CA02: X0 the faced foot end (the bar along +X), Y0 the fixed jaw
  (the bars' F faces toward it), Z0 the bars' L faces on the riser.
- CA03-CA05: X0 the top end at the length (the bar along -X), Y0 the fixed
  jaw (the B faces toward it), Z0 the bars' R faces on the riser.

The slitting saw runs horizontally on the owned R8 stepped saw arbor: the
body's shoulder above it, the cap and its screw below it. Its lower face is
the programmed Z, touched off by hand (it has no tool-setter length, so CA02
and CA04 load no tool), and its rim cuts the notch floor while its faces cut
the walls. Every saw pass runs one way, conventional for an M3 saw: -Y with
the saw left of the ends, +Y with it right of them (the other way it climbs,
and a slitting saw climbing grabs: on this arbor, driven by the clamp's
friction alone, it would turn on it). Each saw program's first pass is half
a step, then an M0 stop with the spindle off for a look at the saw's witness
lines; the heaviest pass's handbook torque is held under the clamp's
friction torque. CA01 and CA03 leave the end mill parked over the saw's
touch-off station, its tip clear over the bars (the arbor, shorter than the
end mill, then hangs higher): the saw comes down in Z only, and moves in X
and Y only with its arbor's body, cap and screw head clear of the bars and
the jaws (``keep_out`` checks each part's every move after the first rise
from the touch-off, which is straight up, both as cut and as proved in air
with Z0 raised ``saw_proof_raise_mm``).

Toolpath rules (owner rulings 2026-11-16): plunges beside the stock at the
cutting feed, real G0 above the stock.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ch_amplitude_bar"
COMMENT = "MHA-CH-01 amplitude bar, one load"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section: the saw's witness-line stop), joined at M6 tool changes and M0
# stops.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("CA00_riser_face", ("riser_face",)),
    ("CA01_foot_end", ("foot_end",)),
    ("CA02_foot_notch", (("foot_light",), ("foot_line",), ("foot_notch",))),
    ("CA03_top_end", ("top_end",)),
    ("CA04_top_notch", (("top_light",), ("top_line",), ("top_notch",))),
    ("CA05_pin_hole", (("pin_spot",), ("pin_drill",), ("pin_ream",))),
)
# The end mill and drill-chuck programs load their own first tool (M6, the
# tool setter); the saw programs run on the saw already on its arbor and
# touched off, which the tool setter cannot measure.
LOAD_FIRST_TOOL = ("CA00_riser_face", "CA01_foot_end", "CA03_top_end", "CA05_pin_hole")
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the cutoff saw, the press and the files are not).
CAM_TOOLS = ("em-half", "saw", "spot", "drill-49", "reamer-0775")
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
# Passes start and finish with the cutter this far clear of the load's sides.
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
# A saw pass's deepest step into the end (the plan's top-notch steps): the
# overhang's bending under a deeper bite passes the finish limit.
SAW_STEP_MAX_MM = 3.0
# Each saw program's first pass takes this share of a step, then stops (M0,
# spindle off) for the witness lines: a light proof of the friction drive.
LIGHT_PASS_SHARE = 0.5
# A saw pass may take this share of the friction drive's torque at most: the
# drive's friction and preload are a table's, not measured, and the saw runs
# oiled (friction .10 under a preload a quarter low leaves about half).
DRIVE_RESERVE = 2.0
# The plan's saw arbor: its tool id, and the shop record it names, the owned
# R8 stepped saw arbor.
ARBOR_TOOL = "saw-arbor"
ARBOR_REF = "saw-arbor-r8-stepped"
# The screw head's stand bound is the largest the plan tolerates, to this
# (.005 in).
STAND_STEP_MM = 0.127
# The saw's axial runout is read on its side face this far in from the tooth
# tips (1/8 in).
RUNOUT_INSET_MM = 3.175
# The saw is touched off with its rim this far in over the bar ends.
TOUCH_IN_MM = 3.0
# A plan number the recipe recomputes must agree to this (its rounding); a
# runout limit to this.
PLAN_TOL_MM = 0.01
RUNOUT_TOL_MM = 0.0005
# Machinery's Handbook milling power for the saw's passes, the figures
# prechips' milling screen takes for milling_material steel_1018: unit power
# (hp per in³/min, plain carbon steel 160-180 HB), the feed factor at .001
# in/tooth and the tool-wear factor.
SAW_UNIT_POWER_HP = 0.78
SAW_FEED_FACTOR = 1.60
SAW_FEED_FACTOR_AT_MM = 0.0254
SAW_WEAR_FACTOR = 1.10
WATTS_PER_HP = 745.7
# Each holder's nose stands at least this far above the jaw tops at its
# tool's deepest cut.
HOLDER_CLEAR_MM = 1.0
# CA00 faces this far past both of the riser blocks' ends, wherever the
# moving jaw closes on them.
FACE_OVERHANG_MM = 1.0
# The jaws grip the riser blocks at least this high above their parallels
# while CA00 faces them.
RISER_GRIP_MIN_MM = 12.7
# CA00's pass, touched off on the higher top, takes at least this (.001) off
# the lowest corner Setup 1 accepts.
RISER_FACE_CUT_MIN_MM = 0.0254


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


def _agree(
    plan: dict[str, Any], key: str, value: float, tol: float = PLAN_TOL_MM
) -> None:
    """A plan parameter the recipe recomputes from the export and the shop."""
    stated = plan["parameters"][key]
    if not math.isclose(stated, value, abs_tol=tol):
        raise ValueError(f"process.{key} {stated:g}, the recipe computes {value:.4f}")


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


def _heaviest(levels: list[list[float]]) -> float:
    """The deepest single bite of passes run to each depth in turn, level by
    level, each level from the raw face."""
    return max(
        depth - previous
        for depths in levels
        for previous, depth in zip([0.0, *depths], depths)
    )


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


def _face(x: tuple[float, float], ys: list[float], z: float, top: float) -> list[str]:
    """A zigzag face at ``z``: one X pass per Y in ``ys`` in order,
    alternating direction from ``x[0]``; the plunge and every stepover beside
    the stock, past ``x``'s ends."""
    clear = _r(top + CLEAR_MM)
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{_r(x[0]):.3f} Y{ys[0]:.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
    ]
    for k, y in enumerate(ys):
        if k:
            lines.append(f"G1 Y{y:.3f} F{{feed}}")
        lines.append(f"G1 X{_r(x[1] if k % 2 == 0 else x[0]):.3f} F{{feed}}")
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
    lines = [f"G0 Z{clear:.3f}", f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}", f"G0 Z{r_plane:.3f}"]
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
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(tip):.3f} F{{feed}}",
        f"G1 Z{r_plane:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The bar's sizes, notches and pin hole from the export, each checked
    against the frame the recipe assumes: the section along model X (left
    face X0) and Z (back face Z0), the length along Y from the foot end at
    Y0; the pin hole along X through the top end's cheeks."""
    f = features["features"]
    planes = {
        name: f[name]["plane"]["value"]
        for name in (
            "left_face",
            "right_face",
            "back_face",
            "front_face",
            "foot_end",
            "top_end",
        )
    }
    for name in ("left_face", "back_face", "foot_end"):
        if planes[name] != 0.0:
            raise ValueError(f"{name}: expected at the model origin")
    section = planes["right_face"]
    if not math.isclose(planes["front_face"], section, abs_tol=1e-6):
        raise ValueError("the bar is not square: right face and front face differ")
    length = planes["top_end"]
    if not math.isclose(length, f["top_end"]["length_nominal"], abs_tol=1e-3):
        raise ValueError(
            f"foot-to-top {length:.4f} is not the length {f['top_end']['length_nominal']}"
        )
    foot, top = f["foot_notch"], f["top_notch"]
    if foot["ledge_from"] != "left_face" or top["ledge_from"] != "right_face":
        raise ValueError(
            "expected the foot ledge from the left face, the top's from the right"
        )
    hole = f["top_pin_hole"]
    if hole["axis"] != [1.0, 0.0, 0.0] or hole["location_from"] != "back_face":
        raise ValueError("top_pin_hole: expected along +X, located from the back face")
    if not math.isclose(length - hole["at"][1], hole["drop_nominal"], abs_tol=1e-3):
        raise ValueError("top_pin_hole: its drop from the top end is not its nominal")
    if not math.isclose(
        hole["at"][2], hole["location_from_back_nominal"], abs_tol=1e-3
    ):
        raise ValueError(
            "top_pin_hole: its place from the back face is not its nominal"
        )
    return {
        "section": section,
        "section_band": f["front_face"]["section"],
        "length": length,
        "length_band": f["top_end"]["length"],
        "foot": foot,
        "top": top,
        "hole": hole,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    section, length = g["section"], g["length"]
    n_bars = int(p["bars_per_load"])

    # The blank and the load.
    _agree(plan, "blank_length_min_mm", p["blank_length_in"] * IN)
    _agree(plan, "blank_length_max_mm", p["blank_length_max_in"] * IN)
    skim = p["foot_skim_mm"]
    # X0 is set to the length band's middle (Setup 5), so the top end's most
    # stock past X0 is the longest blank less the skim, less that middle.
    _agree(
        plan,
        "top_excess_max_mm",
        p["blank_length_max_mm"] - skim - _mid(g["length_band"]),
    )
    if p["blank_length_min_mm"] - skim < length:
        raise ValueError("the shortest blank less the foot skim is under the length")
    # Bar 1's ruled length L1: its own x (L1 - the band's middle) in every
    # bar's 0..top_excess_max_mm window (Setup 4).
    _agree(plan, "measured_length_min_mm", _mid(g["length_band"]))
    _agree(
        plan, "measured_length_max_mm", _mid(g["length_band"]) + p["top_excess_max_mm"]
    )
    # The 1/64 in rule accepts the length to ±1/32 about the band's middle
    # (owner ruling 2026-11-23, tool audit Q3); it never proves the band.
    _agree(plan, "length_rule_min_mm", _mid(g["length_band"]) - IN / 32)
    _agree(plan, "length_rule_max_mm", _mid(g["length_band"]) + IN / 32)
    pitch = p["bar_pitch_mm"]
    _agree(plan, "bar_pitch_mm", _mid(g["section_band"]))
    _agree(plan, "bar_section_min_mm", g["section_band"][0])
    load = n_bars * pitch
    _agree(plan, "load_width_mm", load)
    # The riser: narrower than the narrowest load, so the moving jaw grips
    # the last bar and never the riser; wide enough, less the chamfer filed
    # along its far top edge, to seat the last bar at least half its width
    # in the widest load; the blocks end to end within the jaw width.
    section_min, section_max = g["section_band"]
    riser_w_min, riser_w_max = p["riser_width_min_mm"], p["riser_width_max_mm"]
    chamfer = p["riser_chamfer_mm"]
    if chamfer > section_min / 4:
        raise ValueError("process.riser_chamfer_mm unseats a quarter of the first bar")
    if riser_w_max >= n_bars * section_min:
        raise ValueError(
            "process.riser_width_max_mm is not under the narrowest load: the moving "
            "jaw would grip the riser"
        )
    if riser_w_min - chamfer < (n_bars - 0.5) * section_max:
        raise ValueError(
            "process.riser_width_min_mm less its chamfer seats the last bar under "
            "half its width"
        )
    if 2 * p["riser_length_max_mm"] > p["vise_jaw_width_mm"]:
        raise ValueError("the riser's two blocks end to end are longer than the jaws")
    protrusion = p["end_protrusion_mm"]
    jaw_w = p["vise_jaw_width_mm"]
    if protrusion <= g["top"]["depth"][1] + p["saw_arbor_clear_mm"]:
        raise ValueError(
            "the ends do not stand past the jaws by more than the top notch's depth"
        )
    _agree(plan, "far_overhang_mm", length - jaw_w - protrusion)
    _agree(plan, "foot_clamp_end_mm", protrusion + jaw_w)
    _agree(plan, "top_extent_start_mm", -length)
    _agree(plan, "top_clamp_start_mm", -(protrusion + jaw_w))
    _agree(plan, "top_clamp_end_mm", -protrusion)
    # The bars stand on the riser: the jaw tops in the setup frame (Z0 the
    # bars' down face), at the riser's least faced height.
    jaw_top = p["vise_jaw_height_mm"] - p["riser_height_min_mm"]
    # The riser's heights: its blank (1 in bar, miked in Setup 1) less one
    # riser_face_mm CA00 pass; a reface (one more pass) only above
    # riser_reface_floor_mm.
    face = p["riser_face_mm"]
    _agree(plan, "riser_height_min_mm", p["riser_blank_height_min_mm"] - face)
    _agree(plan, "riser_height_max_mm", p["riser_blank_height_max_mm"] - face)
    _agree(plan, "riser_reface_floor_mm", p["riser_height_min_mm"] + face)
    if p["riser_blank_spread_max_mm"] + RISER_FACE_CUT_MIN_MM > face + 1e-9:
        raise ValueError(
            "process.riser_blank_spread_max_mm leaves CA00's one riser_face_mm pass "
            f"under {RISER_FACE_CUT_MIN_MM} mm to take off the lowest corner"
        )
    under = p["riser_parallel_height_mm"]

    def projection(tool: str, tip_z: float, key: str, oal_key: str) -> None:
        """The tool's stated projection out of its holder puts the holder's
        nose HOLDER_CLEAR_MM above the jaw tops at its deepest tip, and the
        tool is long enough to give it with holder_grip_min_mm gripped."""
        out = p[key]
        if tip_z + out < jaw_top + HOLDER_CLEAR_MM - 1e-6:
            raise ValueError(
                f"{tool}: process.{key} {out:g} leaves its holder's nose under the "
                f"jaw tops at its deepest cut (needs {jaw_top + HOLDER_CLEAR_MM - tip_z:.2f})"
            )
        if out > p[oal_key] - p["holder_grip_min_mm"] + 1e-6:
            raise ValueError(
                f"{tool}: process.{key} {out:g} is more than process.{oal_key} "
                "less process.holder_grip_min_mm"
            )

    # Notches: each band's middle, and the saw's reach. The top notch's band
    # (.124 +.010/0, the .XXX row's width) is wider than two passes of the
    # .064 saw reach: its target is the band's middle or two saw widths, the
    # less, still inside the band.
    foot, top = g["foot"], g["top"]
    _agree(plan, "foot_notch_width_mm", _mid(foot["width"]))
    _agree(plan, "foot_notch_depth_mm", _mid(foot["depth"]))
    _agree(
        plan,
        "top_notch_width_mm",
        min(_mid(top["width"]), 2 * p["saw_thickness_mm"]),
    )
    _agree(plan, "top_notch_depth_mm", _mid(top["depth"]))
    # The P2-P4 bars' ledges are cut from the P1 bar's saw Z0: each is off by
    # the touch-off's error, by its down face's height against P1's where the
    # notch is cut (the seat sweep accepts up to seat_offset_max_mm) and by
    # the sweep's own reading error. Their sum, with ledge_margin_min_mm to
    # spare, stays inside each ledge's half band.
    ledge_budget = (
        p["saw_touch_error_mm"] + p["seat_offset_max_mm"] + p["seat_measure_mm"]
    )
    # The two measuring terms are no finer than the plan's own steps and the
    # shop's gauges: the touch-off its saw_touch_step_mm steps plus the
    # leaf's and P1's miked readings; the sweep two miked sections, the DTI's
    # reading and the zero drift its return to P1 accepts.
    mic = shop["gauges"]["micrometers"]["resolution_mm"]
    dti = shop["gauges"]["dti"]["resolution_mm"]
    if p["saw_touch_error_mm"] < p["saw_touch_step_mm"] + 2 * mic - 1e-9:
        raise ValueError(
            "process.saw_touch_error_mm is finer than its touch-off steps and two "
            "micrometer readings"
        )
    if p["seat_measure_mm"] < 2 * mic + dti + p["sweep_zero_return_mm"] - 1e-9:
        raise ValueError(
            "process.seat_measure_mm is finer than two micrometer readings, the DTI "
            "and the sweep's zero return"
        )
    for name, notch in (("foot", foot), ("top", top)):
        lo, hi = notch["ledge"]
        if not math.isclose(notch["ledge_nominal"], (lo + hi) / 2, abs_tol=1e-6):
            raise ValueError(f"the {name} ledge is not cut at its band's middle")
        if ledge_budget + p["ledge_margin_min_mm"] > (hi - lo) / 2 + 1e-9:
            raise ValueError(
                f"the {name} ledge's budget (touch-off, seat, sweep) {ledge_budget:.4f} "
                f"leaves under ledge_margin_min_mm of its ±{(hi - lo) / 2:.4f} band"
            )
    saw = _shop_tool(plan, shop, "saw")["diameter_mm"]
    _agree(plan, "saw_dia_mm", saw)
    radius = saw / 2
    thick = p["saw_thickness_mm"]
    for name in ("foot", "top"):
        width = p[f"{name}_notch_width_mm"]
        if not thick < width <= 2 * thick:
            raise ValueError(f"the {name} notch is not two saw passes wide")
    # The saw's arbor is the owned R8 stepped saw arbor (the plan's tool names
    # its shop record; its sizes are the plan's, held to the inventory record
    # by the process test): the body's shoulder above the saw, the cap and
    # its countersunk screw below it.
    arbor_ref = next(
        (t["ref"] for t in plan["tools"] if t["id"] == ARBOR_TOOL), None
    )
    if arbor_ref != ARBOR_REF or ARBOR_REF not in shop["tools"]:
        raise ValueError(
            f"the plan's saw arbor is not the owned one, shop tools.{ARBOR_REF}"
        )
    body_r = p["saw_arbor_body_dia_mm"] / 2
    cap_r = p["saw_arbor_cap_dia_mm"] / 2
    cap_t = p["saw_arbor_cap_thickness_mm"]
    head_r = p["saw_arbor_screw_head_dia_mm"] / 2
    if not 0 < head_r < cap_r:
        raise ValueError("the cap's screw head is not inside the cap")
    arbor_r = max(body_r, cap_r)
    # The saw cuts past the arbor by its radius less the arbor's, less the
    # clearance, on both sides of it (the body above, the cap below): no
    # notch's deepest limit passes that, so the body and the cap stay beyond
    # the bars' ends, which stand past the jaws, at every cut.
    arbor_clear = p["saw_arbor_clear_mm"]
    arbor_reach = radius - arbor_r - arbor_clear
    _agree(plan, "saw_depth_past_arbor_max_mm", arbor_reach)
    for name, notch in (("foot", foot), ("top", top)):
        if notch["depth"][1] > arbor_reach + 1e-9:
            raise ValueError(
                f"the {name} notch's deepest limit {notch['depth'][1]:.3f} passes "
                f"the arbor's reach {arbor_reach:.3f}: its body or cap would meet "
                "the bars' ends"
            )
    # NOT MEASURED: the screw head's stand past the cap's lower face, a
    # bounded assumption a first-load stop measures. The stack below the
    # saw's lower face is the cap plus it.
    stand = p["saw_screw_head_stand_max_mm"]
    below = cap_t + stand
    _agree(plan, "saw_below_max_mm", below)
    # The saw moves between passes with its stack's lowest point CLEAR_MM over
    # the bars' top.
    saw_clear = section + CLEAR_MM + below
    _agree(plan, "saw_clear_z_mm", saw_clear)
    # The saw programs' air proof raises Z0 by saw_proof_raise_mm, lifting
    # the whole stack CLEAR_MM over the bars' top at the lowest level: the
    # stand's bound is the largest that proof tolerates, to STAND_STEP_MM.
    proof_raise = p["saw_proof_raise_mm"]
    lowest_level = min(foot["ledge_nominal"], top["ledge_nominal"])
    stand_limit = proof_raise + lowest_level - cap_t - section - CLEAR_MM
    if stand > stand_limit + 1e-6:
        raise ValueError(
            "process.saw_proof_raise_mm leaves the arbor's stack under the bars' top "
            "in the saw programs' air proof"
        )
    if stand <= stand_limit - STAND_STEP_MM:
        raise ValueError(
            f"process.saw_screw_head_stand_max_mm {stand:g} is not the largest the "
            f"air proof tolerates ({stand_limit:.3f}, to {STAND_STEP_MM} mm)"
        )
    # The arbor's lowest point from the spindle nose: the record's distance
    # to the cap's lower face with no saw on, plus the saw, inside the
    # plan's round figure; plus the stand's bound.
    if p["saw_arbor_nose_to_cap_mm"] + thick > p["saw_arbor_below_nose_mm"]:
        raise ValueError(
            "process.saw_arbor_below_nose_mm is under the record's nose-to-cap "
            "distance plus the saw"
        )
    _agree(plan, "saw_arbor_length_mm", p["saw_arbor_below_nose_mm"] + stand)
    # The friction drive (not keyed): one face's friction torque on the clamp
    # ring between the pilot (the saw's hole) and the cap, at the plan's
    # preload and friction.
    ring = _ring_radius(p["saw_bore_mm"] / 2, min(body_r, cap_r))
    drive = p["saw_drive_friction"] * p["saw_clamp_preload_kn"] * ring
    _agree(plan, "saw_drive_torque_max_nm", drive, 0.05)
    # The screw holds that preload on its thread in the arbor: the record's
    # engagement with no saw fitted (measured), less this saw between the
    # shoulder and the cap, is at least one screw diameter.
    if p["saw_screw_engagement_no_saw_mm"] - thick < p["saw_screw_dia_mm"]:
        raise ValueError(
            "the clamp screw's thread behind this saw, "
            "process.saw_screw_engagement_no_saw_mm less the saw's thickness, is "
            "under one screw diameter"
        )
    # Runout (not measured: stops read the axial at every mounting of the
    # arbor, the radial at every clamping of the saw). Axial: a notch's width
    # is the second level's rise above the first plus the saw's swept
    # thickness (its miked thickness plus its axial runout at the rim), which
    # may run from the width's least less the rise to its most less the rise
    # and the margin. Radial: the passes are laid out on the saw's catalogue
    # diameter, so the deepest tooth cuts the floor deeper than the depth's
    # target (its band's middle) by half the tips' total swing plus half the
    # saw's excess over that diameter (the calipers read it on the first
    # load): their sum within twice the depth's most less its target less
    # the margin, either way. Both setups read to the foot notch's limits,
    # which lie inside the top notch's.
    _agree(
        plan, "saw_axial_reading_per_in_mm", IN * (radius - RUNOUT_INSET_MM) / radius
    )
    swept, swing = {}, {}
    for name, notch in (("foot", foot), ("top", top)):
        rise = p[f"{name}_notch_width_mm"] - thick
        _agree(plan, f"{name}_notch_rise_mm", rise, RUNOUT_TOL_MM)
        swept[name] = (
            notch["width"][0] - rise,
            notch["width"][1] - rise - p["saw_swept_margin_mm"],
        )
        _agree(plan, f"{name}_saw_swept_min_mm", swept[name][0], RUNOUT_TOL_MM)
        _agree(plan, f"{name}_saw_swept_max_mm", swept[name][1], RUNOUT_TOL_MM)
        if not swept[name][0] <= thick < swept[name][1]:
            raise ValueError(
                f"the {name} notch's width leaves the saw's nominal thickness no "
                "axial runout"
            )
        swing[name] = 2 * (
            notch["depth"][1]
            - p[f"{name}_notch_depth_mm"]
            - p["saw_depth_margin_mm"]
        )
        _agree(plan, f"{name}_saw_radial_tir_max_mm", swing[name], RUNOUT_TOL_MM)
    if not (
        swept["top"][0] <= swept["foot"][0]
        and swept["foot"][1] <= swept["top"][1]
        and swing["foot"] <= swing["top"]
    ):
        raise ValueError(
            "Setup 3's runout limits (the foot notch's) do not cover the top notch's"
        )
    _agree(
        plan,
        "foot_saw_axial_nominal_mm",
        (swept["foot"][1] - thick) / IN * p["saw_axial_reading_per_in_mm"],
        RUNOUT_TOL_MM,
    )
    # The touch-off station: the saw's rim TOUCH_IN_MM in over the ends, over
    # the middle of the bar against the fixed jaw (X mirrored for the top
    # ends). That is inside the arbor's reach, so the cap and its screw,
    # hanging below the saw as it comes down, are beyond the ends.
    if TOUCH_IN_MM > arbor_reach:
        raise ValueError(
            "the saw's touch-off puts its rim farther in over the ends than the "
            "arbor reaches: the cap would come down on them"
        )
    touch_x = radius - TOUCH_IN_MM
    _agree(plan, "saw_touch_x_mm", touch_x)
    _agree(plan, "saw_touch_y_mm", -pitch / 2)
    foot_depth = p["foot_notch_depth_mm"]
    top_depth = p["top_notch_depth_mm"]
    # Equal steps into the end, the deepest last.
    n_steps = math.ceil(top_depth / SAW_STEP_MAX_MM - 1e-9)
    top_steps = [top_depth * (k + 1) / n_steps for k in range(n_steps)]
    _agree(plan, "top_notch_step_mm", top_steps[0])
    for name in ("top notch rough", "top notch"):
        if not math.isclose(
            _cut(plan, name, "radial_woc_mm"), top_steps[0], abs_tol=1e-6
        ):
            raise ValueError(f"'{name}' radial_woc_mm is not process.top_notch_step_mm")
    # Each notch's first pass, at its ledge's level: a share of a step.
    lights = {
        "foot": LIGHT_PASS_SHARE * foot_depth,
        "top": LIGHT_PASS_SHARE * top_steps[0],
    }
    for name, light in lights.items():
        key = f"{name}_notch_light_mm"
        _agree(plan, key, light, RUNOUT_TOL_MM)
        if not math.isclose(
            _cut(plan, f"{name} notch light", "radial_woc_mm"), p[key], abs_tol=1e-6
        ):
            raise ValueError(f"'{name} notch light' radial_woc_mm is not process.{key}")
    saw_rpm, saw_feed = _setting(plan, shop, "foot notch")
    for name in ("foot notch light", "top notch light", "top notch rough", "top notch"):
        if _setting(plan, shop, name) != (saw_rpm, saw_feed):
            raise ValueError(f"'{name}' runs at another setting than 'foot notch'")
    if (saw_rpm, saw_feed) != (p["saw_rpm"], p["saw_feed_per_min_mm"]):
        raise ValueError(
            "the saw's cuts are not process.saw_rpm and saw_feed_per_min_mm"
        )
    # The heaviest saw pass (the deepest bite, at the saw's full width) takes
    # no more spindle torque, by the handbook's power at this feed per tooth,
    # than the friction drive carries with DRIVE_RESERVE in hand.
    teeth = _cut(plan, "foot notch", "flutes")
    if teeth != p["saw_teeth"] or not math.isclose(
        saw_feed / (saw_rpm * teeth), SAW_FEED_FACTOR_AT_MM, abs_tol=1e-6
    ):
        raise ValueError(
            "the saw's feed is not the .001 in/tooth the handbook's feed factor "
            "is taken at"
        )
    bite = _heaviest(
        [[lights["foot"], foot_depth], [foot_depth], [lights["top"], *top_steps], top_steps]
    )
    torque = _saw_torque_nm(bite, thick, saw_feed, saw_rpm)
    if torque * DRIVE_RESERVE > drive:
        raise ValueError(
            f"the saw's heaviest pass takes {torque:.1f} N·m, over the arbor's "
            f"friction drive with its reserve: {drive / DRIVE_RESERVE:.1f} of "
            f"process.saw_drive_torque_max_nm {drive:.1f}"
        )

    # Ends: the end mill on its side, full height in one level.
    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    r = em / 2
    _agree(plan, "face_cutter_dia_mm", em)
    em_rpm, em_feed = _setting(plan, shop, "foot end")
    if _setting(plan, shop, "top end") != (em_rpm, em_feed):
        raise ValueError("'top end' runs at another setting than 'foot end'")
    if not math.isclose(_cut(plan, "foot end", "radial_woc_mm"), skim, abs_tol=1e-6):
        raise ValueError("'foot end' radial_woc_mm is not process.foot_skim_mm")
    step = p["end_step_max_mm"]
    if not math.isclose(_cut(plan, "top end", "radial_woc_mm"), step, abs_tol=1e-6):
        raise ValueError("'top end' radial_woc_mm is not process.end_step_max_mm")
    end_z = -p["end_tip_below_mm"]
    for name in ("foot end", "top end"):
        if _cut(plan, name, "axial_doc_mm") < section - end_z - 1e-6:
            raise ValueError(
                f"'{name}' axial_doc_mm is under the bar's height and the tip's overrun"
            )
    projection("the end mill", end_z, "half_mill_projection_min_mm", "half_mill_oal_mm")
    # CA01 and CA03 leave T1 parked over the saw's touch-off station, its tip
    # CLEAR_MM over the bars' top, and higher if the arbor mounted in its
    # place (its lowest point no more than saw_arbor_length_mm from the nose;
    # T1's tip at least its collet and projection out) would hang lower than
    # that: the saw never moves in X or Y on a height the controller does not
    # know.
    park_z = (
        section
        + CLEAR_MM
        + max(
            0.0,
            p["saw_arbor_length_mm"]
            - (p["r8_collet_gauge_mm"] + p["half_mill_projection_min_mm"]),
        )
    )
    _agree(plan, "saw_park_z_mm", park_z)
    top_excess = p["top_excess_max_mm"]
    top_xs = [r + e for e in _levels(top_excess, 0.0, step)]

    # Pin hole: spot under the #49, drill, then ream through.
    d49 = _shop_tool(plan, shop, "drill-49")["diameter_mm"]
    dream = _shop_tool(plan, shop, "reamer-0775")["diameter_mm"]
    hole = g["hole"]
    if not hole["dia"][0] <= dream <= hole["dia"][1]:
        raise ValueError(
            f"the reamer Ø{dream} is outside the pin hole's band {hole['dia']}"
        )
    if not d49 < dream:
        raise ValueError("the #49 is not under the reamer")
    spot_rpm, spot_feed = _setting(plan, shop, "pin spot")
    drill_rpm, drill_feed = _setting(plan, shop, "pin drill")
    ream_rpm, ream_feed = _setting(plan, shop, "pin ream")
    spot_dia = p["spot_dia_mm"]
    if not math.isclose(
        _cut(plan, "pin spot", "cutter_dia_mm"), spot_dia, abs_tol=1e-6
    ):
        raise ValueError("'pin spot' cutter_dia_mm is not process.spot_dia_mm")
    if spot_dia >= d49:
        raise ValueError(
            "the spot is not under the #49 drill: it would chamfer the hole"
        )
    spot_depth = _spot_depth(spot_dia)
    peck = p["peck_mm"]
    op = _op_with_cut(plan, "pin drill")[0]
    if op["peck"] != {"step_mm": peck, "retract": "full"}:
        raise ValueError("'pin drill' peck is not process.peck_mm with full retract")
    drill_tip = -(p["drill_past_mm"] + _point(d49))
    _agree(plan, "drill_tip_height_mm", drill_tip)
    ream_tip = -p["ream_past_mm"]
    if ream_tip > -0.5:
        raise ValueError("the reamer's tip does not pass the down face")
    projection(
        "the centre drill",
        section - spot_depth,
        "spot_projection_mm",
        "centre_drill_oal_mm",
    )
    projection("the #49", drill_tip, "drill_projection_mm", "drill_49_oal_mm")
    projection("the reamer", ream_tip, "ream_projection_mm", "reamer_oal_mm")

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)). Foot: the L face (model
    # X0) down, the F face (model Z = section) toward the fixed jaw, the foot
    # end X0. Top: the R face (model X = section) down, the B face (model Z0)
    # toward the fixed jaw, the top end X0.
    frames = {
        "foot": _frame([0.0, 0.0, section], [0, 0, 1], [1, 0, 0]),
        "top": _frame([section, length, 0.0], [0, 0, -1], [-1, 0, 0]),
    }
    if _to(frames["foot"], [0.0, length, 0.0]) != [length, -section, 0.0]:
        raise ValueError("foot: the bar does not run along +X from the fixed jaw down")
    if _to(frames["top"], [section, 0.0, 0.0]) != [-length, 0.0, 0.0]:
        raise ValueError("top: the bar does not run along -X from the fixed jaw down")
    stocks = {
        "foot": ((-skim, length), (-load, 0.0), (0.0, section)),
        "top": ((-length, top_excess), (-load, 0.0), (0.0, section)),
    }
    # Each bar's place across the jaws: bar k's far face k pitches from Y0.
    hx, hy, _hz = _to(frames["top"], hole["at"])
    holes = [[_r(hx), _r(hy - k * pitch)] for k in range(n_bars)]
    if not -load < holes[-1][1] < holes[0][1] < 0 or not -protrusion < hx < 0:
        raise ValueError(f"pin holes {holes} are not on the bars in the CA05 frame")

    # Passes along Y: from beside the moving jaw's side of the load to past
    # the fixed jaw's, or back; the saw starts and ends clear of every bar.
    # The saw's passes are conventional: with it turning clockwise seen from
    # above (M3), along -Y left of the foot ends and along +Y right of the
    # top ends (the other way it climbs, and a slitting saw climbing grabs
    # and turns on its friction-driven arbor). Each notch's first, light pass
    # is a section of its own, before the witness-line stop.
    em_y = (-load - r - APPROACH_MM, r + APPROACH_MM)
    saw_y = (-load - radius - APPROACH_MM, radius + APPROACH_MM)
    foot_ledge, top_ledge = foot["ledge_nominal"], top["ledge_nominal"]
    foot_zs = [foot_ledge, foot_ledge + p["foot_notch_width_mm"] - thick]
    top_zs = [top_ledge, top_ledge + p["top_notch_width_mm"] - thick]
    foot_saw_x = [foot_depth - radius]
    top_saw_x = [radius - d for d in top_steps]
    side = {
        "foot_end": ([-r], [end_z], em_y),
        "foot_light": ([lights["foot"] - radius], foot_zs[:1], saw_y[::-1]),
        "foot_notch": (foot_saw_x, foot_zs, saw_y[::-1]),
        "top_end": (top_xs, [end_z], em_y[::-1]),
        "top_light": ([radius - lights["top"]], top_zs[:1], saw_y),
        "top_notch": (top_saw_x, top_zs, saw_y),
    }
    # The end mill's programs end with T1 parked for the saw's mounting and
    # touch-off: up to the park height, then along X past the ends, then
    # along Y over the bar against the fixed jaw.
    park = {
        "foot_end": [
            f"G0 Z{_r(park_z):.3f}",
            f"G0 X{_r(-touch_x):.3f}",
            f"G0 Y{_r(-pitch / 2):.3f}",
        ],
        "top_end": [
            f"G0 Z{_r(park_z):.3f}",
            f"G0 X{_r(touch_x):.3f}",
            f"G0 Y{_r(-pitch / 2):.3f}",
        ],
    }
    frame_of = {
        "foot_end": "foot",
        "foot_light": "foot",
        "foot_notch": "foot",
        "top_end": "top",
        "top_light": "top",
        "top_notch": "top",
    }
    end_mill = ("em-half", em, "endmill", 3, em_rpm, em_feed)
    slitting = ("saw", saw, "slittingsaw", None, saw_rpm, saw_feed)
    tools_of = {
        key: slitting if key.endswith(("_light", "_notch")) else end_mill
        for key in side
    }
    # The witness-line stop after each notch's light pass: the saw is at its
    # clear height beyond the load (the pass's last line), the spindle is
    # stopped, and the operator looks at the marker lines across the body,
    # the saw and the cap. The instruction is a CNCjs %msg line, which CNCjs
    # shows when the M0 pauses it; the next section restarts the spindle.
    line_stop = {
        "tool": numbers["saw"],
        "label": names["saw"],
        "setting": "SPINDLE STAYS OFF",
        "gcode": [
            "M5",
            "%msg PAUSE: SPINDLE STOPPED. BOTH WITNESS LINES ON THE SAW UNBROKEN:"
            " CYCLE START. A LINE BROKEN: THE SAW SLIPPED, DO NOT RESTART",
            "M0",
        ],
    }
    manual = {"foot_line": line_stop, "top_line": line_stop}
    jobs = []
    for key, (xs, zs, ys) in side.items():
        tool, dia, shape, flutes, rpm, feed = tools_of[key]
        jobs.append(
            {
                "tool": tool,
                "dia": dia,
                "shape": shape,
                "flutes": flutes,
                "rpm": rpm,
                "feed": feed,
                "plunge": feed,
                "frame": frame_of[key],
                "label": key.replace("_", " "),
                "stock": stocks[frame_of[key]],
                "ops": [
                    [
                        key,
                        key.replace("_", " "),
                        _side(xs, zs, ys, section, saw_clear if tool == "saw" else None)
                        + park.get(key, []),
                    ]
                ],
            }
        )

    # CA00_riser_face, once for a new riser (its own G54: X0 the vise's left
    # jaw side, Y0 the fixed jaw's face, Z0 the higher riser top; the job
    # carries the bar's model only as FreeCAD's Job model). The two blocks
    # side by side along the jaws, centred, each standing across them on
    # both 1 in parallels (its 3 in length gripped), their tops above the jaw
    # tops: X passes past both jaw sides, stepping from over the fixed jaw's
    # top to past the longest block's far end, face both blocks edge to edge
    # wherever they stand along the jaws (the cutter passes over the jaw
    # tops, never down beside them).
    if p["vise_jaw_height_mm"] - under < RISER_GRIP_MIN_MM:
        raise ValueError(
            "process.riser_parallel_height_mm leaves the jaws under "
            f"{RISER_GRIP_MIN_MM} mm of the riser to grip"
        )
    riser_jaw_top = p["vise_jaw_height_mm"] - under - p["riser_blank_height_min_mm"]
    if -face < riser_jaw_top + HOLDER_CLEAR_MM - 1e-6:
        raise ValueError(
            "CA00: the end mill's tip does not pass over the jaw tops: the riser's "
            "least blank height on its parallels is under them"
        )
    length_min, length_max = p["riser_length_min_mm"], p["riser_length_max_mm"]
    _agree(plan, "riser_pair_width_max_mm", 2 * riser_w_max)
    pair_max = p["riser_pair_width_max_mm"]
    _agree(plan, "riser_face_overhang_mm", -(jaw_w - pair_max) / 2)
    face_woc = _cut(plan, "riser face", "radial_woc_mm")
    if not 0 < face_woc <= r:
        raise ValueError("'riser face' radial_woc_mm is not within the cutter's radius")
    if not math.isclose(_cut(plan, "riser face", "axial_doc_mm"), face, abs_tol=1e-6):
        raise ValueError("'riser face' axial_doc_mm is not process.riser_face_mm")
    if _setting(plan, shop, "riser face") != (em_rpm, em_feed):
        raise ValueError("'riser face' runs at another setting than 'foot end'")
    riser_ys = [r - face_woc]
    while riser_ys[-1] - r > -length_max - FACE_OVERHANG_MM + 1e-9:
        riser_ys.append(riser_ys[-1] - face_woc)
    riser_ys = [_r(y) for y in riser_ys]
    riser_x = (-(r + APPROACH_MM), jaw_w + r + APPROACH_MM)
    jobs.insert(
        0,
        {
            "tool": "em-half",
            "dia": em,
            "shape": "endmill",
            "flutes": 3,
            "rpm": em_rpm,
            "feed": em_feed,
            "plunge": em_feed,
            "frame": "foot",
            "label": "riser face",
            "stock": (
                (0.0, jaw_w),
                (-length_max, 0.0),
                (-p["riser_blank_height_max_mm"], 0.0),
            ),
            "ops": [
                ["riser_face", "face the riser", _face(riser_x, riser_ys, -face, 0.0)]
            ],
        },
    )
    riser_keep = [
        _box(
            "moving jaw",
            (0.0, jaw_w),
            (-length_min - JAW_DEPTH_MM, -length_min),
            riser_jaw_top,
        ),
        _box("fixed jaw", (0.0, jaw_w), (0.0, JAW_DEPTH_MM), riser_jaw_top),
    ]
    name = "CA00_riser_face"
    riser_expect = [
        [
            name,
            "tool_changes",
            {"z_top": 0.0, "tools": [numbers["em-half"]], "loads_first": True},
        ],
        [name, "spindle", {"rpm": [[em_rpm]]}],
        [name, "pauses", {"z_top": 0.0, "count": 0}],
        [name, "depth", {"z_min": _r(-face)}],
        [name, "rapids_clear", {"z_top": 0.0}],
        [name, "air_feed", {"z_top": 0.0}],
        [
            name,
            "face_passes",
            {
                "z": _r(-face),
                "y": [-length_max, 0.0],
                "max_engagement": face_woc,
                "radius": r,
                "span": 2 * riser_w_max,
                "overhang": FACE_OVERHANG_MM,
            },
        ],
        [name, "keep_out", {"radius": r, "boxes": riser_keep}],
    ]
    clear = section + CLEAR_MM
    for key, label, tool, dia, shape, rpm, feed, lines in (
        (
            "pin_spot",
            "spot the pin holes",
            "spot",
            CENTRE_DRILL["body_mm"],
            "drill",
            spot_rpm,
            spot_feed,
            [
                ln
                for xy in holes
                for ln in _spot(xy, section, section - spot_depth, clear)
            ],
        ),
        (
            "pin_drill",
            "drill the pin holes #49",
            "drill-49",
            d49,
            "drill",
            drill_rpm,
            drill_feed,
            [ln for xy in holes for ln in _pecked(xy, section, drill_tip, peck, clear)],
        ),
        (
            "pin_ream",
            "ream the pin holes",
            "reamer-0775",
            dream,
            "reamer",
            ream_rpm,
            ream_feed,
            [ln for xy in holes for ln in _reamed(xy, section, ream_tip, clear)],
        ),
    ):
        jobs.append(
            {
                "tool": tool,
                "dia": dia,
                "shape": shape,
                "tip_angle": CENTRE_DRILL["point_deg"]
                if tool == "spot"
                else (DRILL_POINT_DEG if tool == "drill-49" else None),
                "rpm": rpm,
                "feed": feed,
                "plunge": feed,
                "frame": "top",
                "label": key.replace("_", " "),
                "stock": stocks["top"],
                "ops": [[key, label, lines]],
            }
        )

    # Keep-outs: the jaws beside the load, inward of the protrusion, from the
    # riser's top (Z0) to the jaw top; the riser under the load, against the
    # fixed jaw and inside both jaw sides, from Z0 down.
    def vise(x: tuple[float, float]) -> list[dict[str, Any]]:
        return [
            _box("moving jaw", x, (-load - JAW_DEPTH_MM, -load), jaw_top),
            _box("fixed jaw", x, (0.0, JAW_DEPTH_MM), jaw_top),
            _box("the riser", x, (-riser_w_max, 0.0), 0.0),
        ]

    keep = {
        "foot": vise((protrusion, protrusion + jaw_w)),
        "top": vise((-(protrusion + jaw_w), -protrusion)),
    }
    # The arbor round the saw, part by part: its reach from the saw's lower
    # face (the programmed Z) down (lo) and up (hi), and its radius. No move,
    # rapid or feed, brings a part into the bars, the riser or the jaws: the
    # bars between the jaws stand on the riser and the vise; their ends past
    # the jaw side overhang air from Z0 to their top, beside which the cap
    # and its screw pass while the saw cuts.
    ends = {"foot": (0.0, protrusion), "top": (-protrusion, 0.0)}
    gripped = {
        "foot": (protrusion, protrusion + jaw_w),
        "top": (-(protrusion + jaw_w), -protrusion),
    }
    solids = {
        frame: keep[frame]
        + [
            _box("the bars between the jaws", gripped[frame], (-load, 0.0), section),
            {
                **_box("the bars' ends", ends[frame], (-load, 0.0), section),
                "z_bottom": 0.0,
            },
        ]
        for frame in keep
    }

    def reach(
        frame: str, part: str, lo: float, hi: float | None
    ) -> list[dict[str, Any]]:
        """``solids[frame]`` as bands of the programmed Z in which a part
        reaching ``lo`` to ``hi`` from it (``hi`` None: on up) would meet them."""
        out = []
        for solid in solids[frame]:
            moved = {**solid, "name": f"{solid['name']} ({part})"}
            moved["z_top"] = _r(solid["z_top"] - lo)
            if "z_bottom" in solid and hi is not None:
                moved["z_bottom"] = _r(solid["z_bottom"] - hi)
            else:
                moved.pop("z_bottom", None)
            out.append(moved)
        return out

    tn = numbers
    expect: list[list[Any]] = list(riser_expect)
    for name, key, final, raw, max_step, direction, rpm, tool, loads in (
        ("CA01_foot_end", "foot_end", -r, -r - skim, skim, 1, em_rpm, "em-half", True),
        (
            "CA02_foot_notch",
            "foot_notch",
            foot_saw_x[0],
            -radius,
            foot_depth,
            -1,
            saw_rpm,
            "saw",
            False,
        ),
        (
            "CA03_top_end",
            "top_end",
            r,
            r + top_excess,
            step,
            -1,
            em_rpm,
            "em-half",
            True,
        ),
        (
            "CA04_top_notch",
            "top_notch",
            top_saw_x[-1],
            radius,
            top_steps[0],
            1,
            saw_rpm,
            "saw",
            False,
        ),
    ):
        zs = side[key][1]
        cutter_r = r if tool == "em-half" else radius
        expect += [
            [
                name,
                "tool_changes",
                {
                    "z_top": section,
                    "tools": [tn[tool]] if loads else [],
                    "loads_first": loads,
                },
            ],
            [name, "spindle", {"rpm": [[rpm]]}],
            # The saw programs stop once, spindle off: the witness-line look
            # after the light pass.
            [
                name,
                "pauses",
                {"z_top": section, "count": 1, "spindle_off": True}
                if tool == "saw"
                else {"z_top": section, "count": 0},
            ],
            [name, "depth", {"z_min": _r(min(zs))}],
            [name, "rapids_clear", {"z_top": section}],
            [name, "air_feed", {"z_top": section}],
            [
                name,
                "side_passes",
                {
                    "axis": "X",
                    "final": _r(final),
                    "raw": _r(raw),
                    "max_step": max_step,
                    "direction": direction,
                    "span": load,
                    "below_z": section,
                },
            ],
            [name, "keep_out", {"radius": cutter_r, "boxes": keep[frame_of[key]]}],
        ]
        if tool == "saw":
            frame = frame_of[key]
            # The saw comes down to a pass only beside the load: its lower
            # face never crosses the height between its highest pass and the
            # bars' top within its radius of the bars.
            over = (
                min(ends[frame][0], gripped[frame][0]),
                max(ends[frame][1], gripped[frame][1]),
            )
            expect.append(
                [
                    name,
                    "keep_out",
                    {
                        "radius": radius,
                        "boxes": [
                            {
                                **_box(
                                    "the bars' top (the saw coming down over the load)",
                                    over,
                                    (-load, 0.0),
                                    section,
                                ),
                                "z_bottom": _r(max(zs)),
                            }
                        ],
                    },
                ]
            )
            # Each arbor part as cut, and as proved in air (Z0 raised
            # proof_raise: every part that much higher over the same shapes).
            for lift, when in ((0.0, ""), (proof_raise, ", proved in air")):
                for part, radius_of, lo, hi in (
                    ("the arbor's body above the saw", body_r, thick, None),
                    ("the arbor's cap below the saw", cap_r, -cap_t, 0.0),
                    ("the cap's screw head", head_r, -below, -cap_t),
                ):
                    expect.append(
                        [
                            name,
                            "keep_out",
                            {
                                "radius": radius_of,
                                "boxes": reach(
                                    frame,
                                    part + when,
                                    lo + lift,
                                    None if hi is None else hi + lift,
                                ),
                            },
                        ]
                    )
    name = "CA05_pin_hole"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": section,
                "tools": [tn["spot"], tn["drill-49"], tn["reamer-0775"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[spot_rpm], [drill_rpm], [ream_rpm]]}],
        [name, "pauses", {"z_top": section, "count": 0}],
        [name, "depth", {"z_min": _r(min(drill_tip, ream_tip))}],
    ]
    for k, (bottom, cutter_r) in enumerate(
        (
            (section - spot_depth, CENTRE_DRILL["body_mm"] / 2),
            (drill_tip, d49 / 2),
            (ream_tip, dream / 2),
        )
    ):
        expect += [
            [f"{name}@{k}", check, kwargs]
            for check, kwargs in (
                ("holes", {"centres": holes, "z_bottom": _r(bottom)}),
                ("rapids_clear", {"z_top": section, "open_holes": holes}),
                ("vertical_below_top", {"z_top": section}),
                ("air_feed", {"z_top": section}),
                ("keep_out", {"radius": cutter_r, "boxes": keep["top"]}),
            )
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
            doc, f"Amplitude bar {key}", ctx["step"], frame["origin"], frame["axes"]
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
