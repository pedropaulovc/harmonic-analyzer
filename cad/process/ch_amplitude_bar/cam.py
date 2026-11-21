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

The slitting saw runs horizontally on its arbor: its lower face is the
programmed Z, touched off by hand (it has no tool-setter length, so CA02 and
CA04 load no tool), and its rim cuts the notch floor while its faces cut the
walls. Every saw pass runs one way, conventional for an M3 saw: -Y with the
saw left of the ends, +Y with it right of them (the other way it climbs, and
a slitting saw climbing grabs and feeds itself in). CA01 and CA03 leave the
end mill parked over the saw's touch-off station, high enough that the
arbor mounted in its place hangs clear of the stock: the saw then comes down
in Z only, and moves in X and Y only with its arbor's spacers and nut clear
of the bars and the jaws (``keep_out`` checks each part's every move after
the first rise from the touch-off, which is straight up, both as cut and as
proved in air with Z0 raised ``saw_proof_raise_mm``).

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
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("CA00_riser_face", ("riser_face",)),
    ("CA01_foot_end", ("foot_end",)),
    ("CA02_foot_notch", ("foot_notch",)),
    ("CA03_top_end", ("top_end",)),
    ("CA04_top_notch", ("top_notch",)),
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
# The arbor spacer by the saw clears the bar's end by this much at the top
# notch's deepest point.
COLLAR_CLEAR_MM = 1.0
# The saw is touched off with its rim this far in over the bar ends.
TOUCH_IN_MM = 3.0
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
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
# The plan's saw touch-off lowers the saw in steps of this (0.01 mm).
SAW_TOUCH_STEP_MM = 0.01


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
    _agree(plan, "top_excess_max_mm", p["blank_length_max_mm"] - skim - length)
    if p["blank_length_min_mm"] - skim < length:
        raise ValueError("the shortest blank less the foot skim is under the length")
    _agree(plan, "measured_length_min_mm", g["length_band"][0])
    _agree(plan, "measured_length_max_mm", p["blank_length_max_mm"] - skim)
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
    if protrusion <= g["top"]["depth"][1] + COLLAR_CLEAR_MM:
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

    # Notches: each band's middle, and the saw's reach.
    foot, top = g["foot"], g["top"]
    _agree(plan, "foot_notch_width_mm", _mid(foot["width"]))
    _agree(plan, "foot_notch_depth_mm", _mid(foot["depth"]))
    _agree(plan, "top_notch_width_mm", _mid(top["width"]))
    _agree(plan, "top_notch_depth_mm", _mid(top["depth"]))
    # The P2-P4 bars' ledges are cut from the P1 bar's saw Z0: each is off by
    # the touch-off's error, by its down face's height against P1's where the
    # notch is cut (the seat sweep accepts up to seat_offset_max_mm) and by
    # the sweep's own reading error. Their sum, with ledge_margin_min_mm to
    # spare, stays inside each ledge's half band.
    ledge_budget = (
        p["saw_touch_error_mm"] + p["seat_offset_max_mm"] + p["seat_measure_mm"]
    )
    # The two measuring terms are no finer than the shop's gauges: the
    # touch-off its steps plus the leaf's and P1's miked readings, the sweep
    # two miked sections plus the DTI's reading.
    mic = shop["gauges"]["micrometers"]["resolution_mm"]
    dti = shop["gauges"]["dti"]["resolution_mm"]
    if p["saw_touch_error_mm"] < SAW_TOUCH_STEP_MM + 2 * mic - 1e-9:
        raise ValueError(
            "process.saw_touch_error_mm is finer than its touch-off steps and two "
            "micrometer readings"
        )
    if p["seat_measure_mm"] < 2 * mic + dti - 1e-9:
        raise ValueError(
            "process.seat_measure_mm is finer than two micrometer readings and the DTI"
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
    _agree(
        plan,
        "saw_collar_dia_max_mm",
        2 * (radius - top["depth"][1] - COLLAR_CLEAR_MM),
    )
    # The arbor round the saw (tools.gear-cutter-arbor-1, to buy: its sizes
    # are the plan's assumed limits, checked when it is mounted): by the saw,
    # spacers no wider than the collar limit; below it, spacers at least
    # saw_spacer_below_min_mm deep, then the nut, all within saw_below_max_mm
    # of the saw's lower face and the nut no wider than saw_nut_dia_max_mm.
    collar_r = p["saw_collar_dia_max_mm"] / 2
    nut_r = p["saw_nut_dia_max_mm"] / 2
    below = p["saw_below_max_mm"]
    spacer_below = p["saw_spacer_below_min_mm"]
    if not 0 < spacer_below < below:
        raise ValueError("the spacers under the saw are not inside its stack's depth")
    # The saw's arbor, spacers and nut stay past the jaw side, never over the
    # jaws: the saw's centre is beyond the ends by its radius less the notch.
    for name, depth in (("foot", foot["depth"][1]), ("top", top["depth"][1])):
        if protrusion + radius - depth - max(collar_r, nut_r) <= 0:
            raise ValueError(
                f"the saw arbor's spacers or nut reach over the jaws at the {name} notch"
            )
    # The saw moves between passes with its stack's lowest point CLEAR_MM over
    # the bars' top.
    saw_clear = section + CLEAR_MM + below
    _agree(plan, "saw_clear_z_mm", saw_clear)
    # The saw programs' air proof raises Z0 by saw_proof_raise_mm: enough to
    # lift the whole stack CLEAR_MM over the bars' top at the lowest level
    # (raised by less, the nut that passes under the top ends would rise
    # into them).
    proof_raise = p["saw_proof_raise_mm"]
    lowest_level = min(foot["ledge_nominal"], top["ledge_nominal"])
    if proof_raise < below + section - lowest_level + CLEAR_MM - 1e-6:
        raise ValueError(
            "process.saw_proof_raise_mm leaves the arbor's stack under the bars' top "
            "in the saw programs' air proof"
        )
    # The touch-off station: the saw's rim TOUCH_IN_MM in over the ends, over
    # the middle of the bar against the fixed jaw (X mirrored for the top
    # ends); the spacers and the nut, hanging below the saw as it comes down,
    # stay past the ends.
    touch_x = radius - TOUCH_IN_MM
    _agree(plan, "saw_touch_x_mm", touch_x)
    _agree(plan, "saw_touch_y_mm", -pitch / 2)
    if touch_x - max(nut_r, collar_r) < COLLAR_CLEAR_MM:
        raise ValueError("the arbor's nut reaches the bar ends at the saw's touch-off")
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
    saw_rpm, saw_feed = _setting(plan, shop, "foot notch")
    for name in ("top notch rough", "top notch"):
        if _setting(plan, shop, name) != (saw_rpm, saw_feed):
            raise ValueError(f"'{name}' runs at another setting than 'foot notch'")
    if (saw_rpm, saw_feed) != (p["saw_rpm"], p["saw_feed_per_min_mm"]):
        raise ValueError(
            "the saw's cuts are not process.saw_rpm and saw_feed_per_min_mm"
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
    # CA01 and CA03 leave T1 parked over the saw's touch-off station, so high
    # that the arbor mounted in its place (its lowest point no more than
    # saw_arbor_length_mm from the nose; T1's tip at least its collet and
    # projection out) hangs CLEAR_MM over the bars' top: the saw never moves
    # in X or Y on a height the controller does not know.
    park_z = (
        section
        + CLEAR_MM
        + p["saw_arbor_length_mm"]
        - (p["r8_collet_gauge_mm"] + p["half_mill_projection_min_mm"])
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
    # and feeds itself in).
    em_y = (-load - r - APPROACH_MM, r + APPROACH_MM)
    saw_y = (-load - radius - APPROACH_MM, radius + APPROACH_MM)
    foot_ledge, top_ledge = foot["ledge_nominal"], top["ledge_nominal"]
    foot_zs = [foot_ledge, foot_ledge + p["foot_notch_width_mm"] - thick]
    top_zs = [top_ledge, top_ledge + p["top_notch_width_mm"] - thick]
    foot_saw_x = [p["foot_notch_depth_mm"] - radius]
    top_saw_x = [radius - d for d in top_steps]
    side = {
        "foot_end": ([-r], [end_z], em_y),
        "foot_notch": (foot_saw_x, foot_zs, saw_y[::-1]),
        "top_end": (top_xs, [end_z], em_y[::-1]),
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
        "foot_notch": "foot",
        "top_end": "top",
        "top_notch": "top",
    }
    tools_of = {
        "foot_end": ("em-half", em, "endmill", 3, em_rpm, em_feed),
        "foot_notch": ("saw", saw, "slittingsaw", None, saw_rpm, saw_feed),
        "top_end": ("em-half", em, "endmill", 3, em_rpm, em_feed),
        "top_notch": ("saw", saw, "slittingsaw", None, saw_rpm, saw_feed),
    }
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
    # the jaw side overhang air from Z0 to their top, which the nut may pass
    # under while the saw cuts.
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
            p["foot_notch_depth_mm"],
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
            [name, "pauses", {"z_top": section, "count": 0}],
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
            # Each part as cut, and as proved in air (Z0 raised proof_raise:
            # every part that much higher over the same shapes).
            frame = frame_of[key]
            for lift, when in ((0.0, ""), (proof_raise, ", proved in air")):
                for part, radius_of, lo, hi in (
                    ("spacers above the saw", collar_r, thick, None),
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
        "manual": {},
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
