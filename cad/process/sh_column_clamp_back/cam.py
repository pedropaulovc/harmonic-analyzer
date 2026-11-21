"""FreeCAD CAM recipe for MHA-SH-02, the column clamp back, and its pair bore.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The half's sizes come
from the feature export (its width, height, pre-face depth and grip offset,
both tapped ear holes and the bore); the blank, the skims, face levels,
spots, pecks, the riser, the bore's finish stock, helix pitch and run past,
and the pair's front depth and holding from ``plan.toml`` ``[parameters]``
and ``milling_cuts``; cutter diameters, speeds and feeds from ``shop.toml``
and the plan's authored drill settings. Every path is written here
(``rt.custom``). Typed here, because neither record carries them: the #2
centre drill's catalogue geometry, the twist drills' 118° point, the
machine's Z top for the tap files' retract, the approach, safe and clearance
heights, the face overhang and the vise jaws' depth (keep-out shapes only).

Route (owner ruling 2026-11-20; plan text in ``plan.toml``): one 3/4 in
square 1018 blank about 2.0 long per run. Upright on a 1 in parallel pair:
CB01 faces the first end, CB02 the other end to the width. Lying on the 1 in
+ 1/2 in parallel stacks: CB03 faces the bottom face, CB04 the top to the
height, CB05 skims the mating face, CB06 (mating face down) faces the back
face to the pre-face depth (.610), spots and drills both #29 tap drills from
one zero; CB07 and CB08 bring the dead centre over each for the 8-32 hand
tap. Each back is then bolted to its front (MHA-SH-01, drilled by its
traveler) with their own #8-32 screws and gripped on the two outside faces:
CB09 interpolates the full bore on the split line (helix down, then a finish
and a spring pass at full depth), CB10 opens it .002 on the diameter if the
gauge reads it small. Unbolted, the back alone: CB11 faces the grip offset
(.020) off its mating face.

Work frames (G54), each set in its setup:
- CB01: X0 Y0 the bar's axis, Z0 the faced first end.
- CB02: X0 Y0 the bar's axis, Z0 the parallels' top (the first end).
- CB03-CB04: X0 the left end, Y0 the fixed jaw, Z0 the stacks' top.
- CB05: X0 the right end (the near side), Y0 the fixed jaw (B), Z0 the
  stacks' top.
- CB06-CB08: X0 the LEFT end (the near side, marked N), Y0 the fixed jaw
  (the bottom face B against it), Z0 the stacks' top (the mating face).
- CB09-CB10: X0 the two N ends (flush), Y0 the split line (+Y toward the
  fixed jaw and the back), Z0 the parallels' top (both B faces).
- CB11: X0 the right end (N), Y0 the fixed jaw (B), Z0 the mating face as
  it stands after the bore.

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock; the
bore climbs (G3, a clockwise spindle) and enters on a helix, never a plunge.
The holes are tapped by hand on the dead centre, spindle off (as the
magnifying clamp): FluidNC refuses jogs while an M0 holds the program
(http://wiki.fluidnc.com/en/features/single_block_mode), so each tap stop is
a file of its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "sh_column_clamp_back"
COMMENT = "MHA-SH-02 column clamp back"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("CB01_first_end", ("first_end",)),
    ("CB02_length", ("length",)),
    ("CB03_bottom", ("bottom_face",)),
    ("CB04_height", ("top_face",)),
    ("CB05_mating", ("mating_face",)),
    ("CB06_back_drill", (("outside_face",), ("ear_spot",), ("ear_drill",))),
    ("CB07_tap_1", ("tap_1",)),
    ("CB08_tap_2", ("tap_2",)),
    ("CB09_pair_bore", ("pair_bore",)),
    ("CB10_bore_open", ("bore_open",)),
    ("CB11_face_off", ("face_off",)),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held, and each tap file before its
# retract (the dead centre).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the tap and the files are not).
CAM_TOOLS = ("em-half", "spot", "drill-29", "dead-centre")
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
# A tap file's first motion: G53 G0 to machine Z0, the homed top (as the
# magnifying clamp's recipe: FluidNC sets an axis's machine position to its
# homing mpos_mm, default 0, and Z homes up) [INFERENCE: the owner's
# config's Z mpos_mm is not on record].
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


def _circle(cx: float, radius: float, z0: float, z1: float) -> list[str]:
    """One climb (G3) turn of ``radius`` about (``cx``, 0) from its +X point,
    descending from ``z0`` to ``z1`` (a flat circle when equal), in two
    half-turns so no arc's end is its start."""
    mid = _r((z0 + z1) / 2)
    left, right = _r(cx - radius), _r(cx + radius)
    return [
        f"G3 X{left:.3f} Y0.000 Z{mid:.3f} I{-_r(radius):.3f} J0.000 F{{feed}}",
        f"G3 X{right:.3f} Y0.000 Z{_r(z1):.3f} I{_r(radius):.3f} J0.000 F{{feed}}",
    ]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The half's sizes and tapped ear holes from the export, each checked
    against the frame the recipe assumes: the bore axis along Y at the model
    origin, the split line (the mating face before its final facing) at X0
    with the back face at −X and the faced mating face the grip offset
    behind it, the height along Y centred, the width along Z with the near
    side at +Z."""
    f = features["features"]
    near, far = f["near_side"]["plane"]["value"], f["far_side"]["plane"]["value"]
    width = near - far
    if not math.isclose(width, f["far_side"]["width_nominal"], abs_tol=1e-3):
        raise ValueError(
            f"near-to-far {width:.4f} is not the width {f['far_side']['width_nominal']}"
        )
    bottom, top = f["bottom_face"]["plane"]["value"], f["top_face"]["plane"]["value"]
    height = top - bottom
    if not math.isclose(height, f["top_face"]["height_nominal"], abs_tol=1e-3):
        raise ValueError(
            f"bottom-to-top {height:.4f} is not the height {f['top_face']['height_nominal']}"
        )
    mating, back = f["mating_face"], f["back_face"]
    grip = mating["grip_offset_nominal"]
    if not math.isclose(-mating["plane"]["value"], grip, abs_tol=1e-3):
        raise ValueError(
            f"mating face at X {mating['plane']['value']} is not the grip offset {grip} behind the bore axis"
        )
    pre_depth = -back["plane"]["value"]
    if not math.isclose(pre_depth, back["depth_nominal"] + grip, abs_tol=1e-3):
        raise ValueError(
            f"back face at X {back['plane']['value']} is not the depth plus the grip offset"
        )
    bore = f["bore"]
    if bore["at"] != [0.0, 0.0, 0.0] or bore["axis"] != [0.0, 1.0, 0.0]:
        raise ValueError("bore: expected along Y through the model origin")
    bore_band = [bore["mate_od_nominal"] + c for c in bore["diametral_clearance"]]
    if not bore_band[0] <= bore["dia_ref"] <= bore_band[1]:
        raise ValueError(f"bore Ø{bore['dia_ref']} is outside its band {bore_band}")
    holes = []
    for name in ("ear_tap_1", "ear_tap_2"):
        hole = f[name]
        if hole["axis"] != [1.0, 0.0, 0.0] or not math.isclose(
            hole["at"][0], -pre_depth, abs_tol=1e-3
        ):
            raise ValueError(
                f"{name}: expected through the part from the back face along +X"
            )
        if not hole["station"][0] <= hole["at"][2] <= hole["station"][1]:
            raise ValueError(
                f"{name}: Z {hole['at'][2]} is outside its station band {hole['station']}"
            )
        if not math.isclose(
            hole["at"][1] - bottom, hole["height_nominal"], abs_tol=1e-3
        ):
            raise ValueError(
                f"{name}: its height from the bottom is not {hole['height_nominal']}"
            )
        holes.append(
            {
                "name": name,
                "at": hole["at"],
                "dia": hole["dia"],
                "station": abs(hole["at"][2]),
            }
        )
    return {
        "width": width,
        "height": height,
        "height_max": f["top_face"]["height"][1],
        "pre_depth": pre_depth,
        "grip": grip,
        "near": near,
        "bottom": bottom,
        "bore_dia": bore["dia_ref"],
        "bore_band": bore_band,
        "holes": holes,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    width, height, pre_depth = g["width"], g["height"], g["pre_depth"]

    # The blank: the square bar's section, sawn to length.
    section = p["blank_section_in"] * IN
    _agree(plan, "blank_section_mm", section)
    blank_min, blank_max = p["blank_length_min_in"] * IN, p["blank_length_max_in"] * IN
    end_skim, bottom_skim, mating_skim = (
        p["end_skim_mm"],
        p["bottom_skim_mm"],
        p["mating_skim_mm"],
    )
    upright_top = blank_max - end_skim
    _agree(plan, "upright_top_max_mm", upright_top)
    if blank_min - end_skim < width:
        raise ValueError(
            f"the shortest blank less the first-end skim, {blank_min - end_skim:.3f}, is under the width {width:.3f}"
        )
    bottom_level = section - bottom_skim
    mating_level = section - mating_skim
    if bottom_level <= height or mating_level <= pre_depth:
        raise ValueError(
            "the section leaves nothing to face to the height or the depth"
        )

    em_record = _shop_tool(plan, shop, "em-half")
    em = em_record["diameter_mm"]
    d29 = _shop_tool(plan, shop, "drill-29")["diameter_mm"]
    tap = _shop_tool(plan, shop, "tap-8-32")
    r = em / 2
    if not math.isclose(d29, tap["tap_drill_mm"], abs_tol=1e-6):
        raise ValueError(
            f"#29 Ø{d29} is not the 8-32 tap's drill {tap['tap_drill_mm']}"
        )
    for hole in g["holes"]:
        if not hole["dia"][0] <= d29 <= hole["dia"][1]:
            raise ValueError(
                f"#29 Ø{d29} is outside {hole['name']}'s band {hole['dia']}"
            )
    step_max = p["face_stepover_max_mm"]
    face_cuts = (
        "first end",
        "length",
        "bottom face",
        "height",
        "mating face",
        "outside face",
        "face off",
    )
    face_rpm, face_feed = _setting(plan, shop, "first end")
    for name in face_cuts:
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), em, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' cutter Ø{_cut(plan, name, 'cutter_dia_mm')}, the end mill is Ø{em}"
            )
        if _setting(plan, shop, name) != (face_rpm, face_feed):
            raise ValueError(f"'{name}' runs at another setting than 'first end'")
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), step_max, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' radial_woc_mm is not process.face_stepover_max_mm"
            )
    for name, doc in (
        ("first end", end_skim),
        ("bottom face", bottom_skim),
        ("mating face", mating_skim),
    ):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), doc, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not its skim")
    if _op_with_cut(plan, "face off")[1]["axial_doc_mm"] != "{{cad.grip_offset_mm}}":
        raise ValueError("'face off' axial_doc_mm is not {{cad.grip_offset_mm}}")
    level_max = p["face_step_max_mm"]
    length_levels = _levels(upright_top, width, level_max)
    height_levels = _levels(bottom_level, height, level_max)
    depth_levels = _levels(mating_level, pre_depth, level_max)
    for name in ("length", "height", "outside face"):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), level_max, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not process.face_step_max_mm")

    # Holes: spot under the drill, then the #29 pecked with full retracts
    # until its full diameter is past the mating face, into the gap between
    # the stacks.
    spot_rpm, spot_feed = _setting(plan, shop, "ear spot")
    drill_rpm, drill_feed = _setting(plan, shop, "ear drill")
    if not math.isclose(
        _cut(plan, "ear spot", "cutter_dia_mm"), p["spot_dia_mm"], abs_tol=1e-6
    ):
        raise ValueError("'ear spot' cutter_dia_mm is not process.spot_dia_mm")
    if p["spot_dia_mm"] >= d29:
        raise ValueError(
            "the spot is not under the #29 drill: it would chamfer the hole"
        )
    spot_depth = _spot_depth(p["spot_dia_mm"])
    peck = p["peck_mm"]
    op = _op_with_cut(plan, "ear drill")[0]
    if op["peck"] != {"step_mm": peck, "retract": "full"}:
        raise ValueError("'ear drill' peck is not process.peck_mm with full retract")
    if op["hole_depth_mm"] != "{{cad.pre_face_depth_mm}}":
        raise ValueError("'ear drill' hole_depth_mm is not {{cad.pre_face_depth_mm}}")
    tip = -(p["drill_past_mm"] + _point(d29))
    _agree(plan, "drill_tip_height_mm", tip)

    # Vise: upright on the single 1 in pair, lying on the stacked risers.
    upright_grip = p["vise_jaw_height_mm"] - p["parallel_height_mm"]
    lying_grip = p["vise_jaw_height_mm"] - p["riser_height_mm"]
    _agree(plan, "upright_grip_mm", upright_grip)
    _agree(plan, "lying_grip_mm", lying_grip)
    t = p["parallel_thickness_mm"]
    # The tap stack's ceiling (the dead centre's reach out of its collet plus
    # the tap's in its wrench): spindle-to-table maximum less the tool-change
    # clearance, the vise bed, the stacks, the setup's tallest stock (the
    # section, as the capacity check takes it) and the collet's gauge,
    # rounded down to .01 in.
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["riser_height_mm"]
        - section
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

    # Frames (model point p -> axes · (p - origin)). The split line (the
    # mating face before its facing) is model X0 and the back face −X. Raw
    # faces: the mating face's skim beyond X0, the back face the rest of the
    # section beyond it; the bottom face's skim below it, the top the rest.
    raw_mating = mating_skim
    raw_outside = raw_mating - section
    raw_bottom = g["bottom"] - bottom_skim
    raw_top = raw_bottom + section
    centre_x = (raw_mating + raw_outside) / 2
    centre_y = (raw_bottom + raw_top) / 2
    near = g["near"]
    far = near - width
    frames = {
        "first_end": _frame([centre_x, centre_y, far], [0, -1, 0], [0, 0, -1]),
        "length": _frame([centre_x, centre_y, far], [0, 1, 0], [0, 0, 1]),
        # Bottom up, the raw mating face against the fixed jaw.
        "bottom": _frame([raw_mating, raw_top, near], [1, 0, 0], [0, -1, 0]),
        "top": _frame([raw_outside, g["bottom"], near], [-1, 0, 0], [0, 1, 0]),
        # Mating face up, B against the fixed jaw: the near side is the
        # RIGHT end, the part to -X.
        "mating": _frame([raw_outside, g["bottom"], near], [0, -1, 0], [1, 0, 0]),
        # Outside face up, B against the fixed jaw: the near side N is the LEFT end.
        "outside": _frame([0.0, g["bottom"], near], [0, -1, 0], [-1, 0, 0]),
        # The bolted pair: the back toward the fixed jaw, the N ends at X0.
        "pair": _frame([0.0, g["bottom"], near], [-1, 0, 0], [0, 1, 0]),
        # The back alone, mating face up: Z0 that face as it stands.
        "face_off": _frame([0.0, g["bottom"], near], [0, -1, 0], [1, 0, 0]),
    }

    def x_range(key: str) -> tuple[float, float]:
        ends = sorted(_to(frames[key], [0.0, 0.0, z])[0] for z in (near, far))
        if not math.isclose(min(abs(e) for e in ends), 0.0, abs_tol=1e-6):
            raise ValueError(f"{key}: no end of the part is at X0")
        return (ends[0], ends[1])

    hs = section / 2
    xr = {
        key: x_range(key)
        for key in ("bottom", "top", "mating", "outside", "pair", "face_off")
    }
    if xr["outside"] != (0.0, width) or xr["pair"] != (0.0, width):
        raise ValueError("CB06 and the pair: N is not the left end")
    # The front's depth (its band, as the pair is assembled from any front)
    # and this back's pre-face depth band (the depth band plus the grip
    # offset nominal, as the plan sizes it): the stock takes the nominals,
    # the keep-outs and the screw check the band ends that bring each
    # obstacle nearest.
    front_min, front_max = p["other_half_depth_min_mm"], p["other_half_depth_max_mm"]
    front_depth = (front_min + front_max) / 2
    pre_min, pre_max = (
        d + g["grip"] for d in features["features"]["back_face"]["depth"]
    )
    height_max = g["height_max"]
    stocks = {
        "first_end": ((-hs, hs), (-hs, hs), (-upright_top, end_skim)),
        "length": ((-hs, hs), (-hs, hs), (0.0, upright_top)),
        "bottom": (xr["bottom"], (-section, 0.0), (0.0, section)),
        "top": (xr["top"], (-section, 0.0), (0.0, bottom_level)),
        "mating": (xr["mating"], (-height, 0.0), (0.0, section)),
        "outside": (xr["outside"], (-height, 0.0), (0.0, mating_level)),
        "pair": (xr["pair"], (-front_depth, pre_depth), (0.0, height_max)),
        "face_off": (xr["face_off"], (-height, 0.0), (-pre_depth, 0.0)),
    }
    holes = []
    for hole in g["holes"]:
        x, y, _z = _to(frames["outside"], hole["at"])
        holes.append([_r(x), _r(y)])
    if not all(0 < x < width and -height < y < 0 for x, y in holes):
        raise ValueError(f"ear holes {holes} are not on the part in the CB06 frame")
    for _x, y in holes:
        if not (-height + t < y - d29 / 2 and y + d29 / 2 < -t):
            raise ValueError(f"the ear hole at Y {y} reaches a parallel ({t} thick)")

    # The pair bore: centred on the split line at the bore's station from N.
    bore_x, bore_y, _ = _to(frames["pair"], [0.0, 0.0, 0.0])
    if not math.isclose(bore_y, 0.0, abs_tol=1e-9):
        raise ValueError("the bore is not on the split line")
    bore_x = _r(bore_x)
    big = g["bore_dia"] / 2
    r_finish = big - r
    r_rough = r_finish - p["bore_finish_stock_mm"]
    if not 0 < r_rough < r:
        raise ValueError(
            f"the rough helix's radius {r_rough:.3f} leaves a core or exceeds the cutter's {r:.3f}"
        )
    r_open = r_finish + p["bore_open_mm"] / 2
    if 2 * (r_open + r) > g["bore_band"][1] or 2 * (r_finish + r) < g["bore_band"][0]:
        raise ValueError("the finish or the opened bore is outside the bore band")
    bore_top = height_max
    bore_bottom = -p["bore_past_mm"]
    if em_record["flute_length_mm"] < bore_top - bore_bottom:
        raise ValueError(
            "the end mill's flutes do not cover the pair's height and the run past"
        )
    turns = math.ceil((bore_top - bore_bottom) / p["helix_pitch_mm"] - 1e-9)
    pitch = (bore_top - bore_bottom) / turns
    if not math.isclose(
        _cut(plan, "bore rough", "axial_doc_mm"), p["helix_pitch_mm"], abs_tol=1e-6
    ):
        raise ValueError("'bore rough' axial_doc_mm is not process.helix_pitch_mm")
    # The bore's feeds: the setting's chip load holds at the cutter's edge,
    # which runs (r_rough + r)/r_rough faster than its centre on the helix.
    bore_feed = face_feed * r_rough / (r_rough + r)
    _agree(plan, "bore_feed_per_min_mm", bore_feed)
    for name in ("bore rough", "bore finish", "bore open"):
        if _setting(plan, shop, name) != (face_rpm, p["bore_feed_per_min_mm"]):
            raise ValueError(
                f"'{name}' does not run at {face_rpm:g} rpm and process.bore_feed_per_min_mm"
            )
    # The pair's holding: a parallel under each outside face's band behind
    # the bore, the back's stopped short of it along the jaws; a 1-2-3 block
    # between the moving jaw and the front's bar face, between the screw
    # heads.
    if front_min - t <= big:
        raise ValueError("the front's parallel reaches under the bore")
    if pre_min - t <= big and p["back_parallel_end_mm"] <= big:
        raise ValueError("the back's parallel reaches under the bore")
    head = p["screw_head_dia_mm"] / 2
    station = min(h["station"] for h in g["holes"])
    if p["spacer_block_width_mm"] / 2 >= station - head:
        raise ValueError("the 1-2-3 block reaches the screw heads")
    if p["screw_length_mm"] >= front_min + pre_min:
        raise ValueError(
            "the screws stand out of the back face against the fixed jaw in the least pair"
        )
    _agree(
        plan, "pair_jaw_span_mm", front_depth + pre_depth + p["spacer_block_length_mm"]
    )
    # The collet's face stays above the 1-2-3 block and the fixed jaw (the
    # collet nose overhangs both from the bore's edge) with the cutter at the
    # bottom of the bore: the plan's least projection sets it.
    _agree(plan, "bore_tip_height_mm", bore_bottom)
    collet_face = bore_bottom + p["bore_mill_projection_min_mm"]
    for what, z in (
        ("the 1-2-3 block", p["spacer_block_height_mm"] - p["parallel_height_mm"]),
        ("the fixed jaw", upright_grip),
    ):
        if collet_face <= z:
            raise ValueError(
                f"at the bore's bottom the collet's face, Z {collet_face:.2f}, is not above {what}, Z {z:.2f}"
            )

    em_tool = {
        "tool": "em-half",
        "dia": em,
        "shape": "endmill",
        "flutes": 3,
        "rpm": face_rpm,
        "feed": face_feed,
        "plunge": face_feed,
    }
    bore_tool = {**em_tool, "feed": bore_feed, "plunge": bore_feed}
    spot_tool = {
        "tool": "spot",
        "dia": CENTRE_DRILL["body_mm"],
        "shape": "drill",
        "tip_angle": CENTRE_DRILL["point_deg"],
        "rpm": spot_rpm,
        "feed": spot_feed,
        "plunge": spot_feed,
    }
    drill_tool = {
        "tool": "drill-29",
        "dia": d29,
        "shape": "drill",
        "tip_angle": DRILL_POINT_DEG,
        "rpm": drill_rpm,
        "feed": drill_feed,
        "plunge": drill_feed,
    }

    def run(x: tuple[float, float]) -> tuple[float, float]:
        return (x[0] - r - APPROACH_MM, x[1] + r + APPROACH_MM)

    upright_ys = _stations((-hs, hs), r, step_max)
    square_ys = _stations((-section, 0.0), r, step_max)
    split_ys = _stations((-height, 0.0), r, step_max)
    grip = g["grip"]
    faces = {
        "first_end": (
            [0.0],
            end_skim,
            run((-hs, hs)),
            upright_ys,
            (-hs, hs),
            section,
            "first_end",
        ),
        "length": (
            length_levels,
            upright_top,
            run((-hs, hs)),
            upright_ys,
            (-hs, hs),
            section,
            "length",
        ),
        "bottom_face": (
            [bottom_level],
            section,
            run(xr["bottom"]),
            square_ys,
            (-section, 0.0),
            width,
            "bottom",
        ),
        "top_face": (
            height_levels,
            bottom_level,
            run(xr["top"]),
            square_ys,
            (-section, 0.0),
            width,
            "top",
        ),
        "mating_face": (
            [mating_level],
            section,
            run(xr["mating"]),
            split_ys,
            (-height, 0.0),
            width,
            "mating",
        ),
        "outside_face": (
            depth_levels,
            mating_level,
            run(xr["outside"]),
            split_ys,
            (-height, 0.0),
            width,
            "outside",
        ),
        "face_off": (
            [-grip],
            0.0,
            run(xr["face_off"]),
            split_ys,
            (-height, 0.0),
            width,
            "face_off",
        ),
    }
    jobs = []
    for key, (levels, top, xs, ys, _y, _span, frame) in faces.items():
        if key == "face_off":
            continue
        jobs.append(
            {
                **em_tool,
                "frame": frame,
                "label": key.replace("_", " "),
                "stock": stocks[frame],
                "ops": [
                    [
                        key,
                        f"face the {key.replace('_', ' ')}",
                        _face(levels, top, xs, ys),
                    ]
                ],
            }
        )
    clear = pre_depth + CLEAR_MM
    jobs.append(
        {
            **spot_tool,
            "frame": "outside",
            "label": "ear spot",
            "stock": stocks["outside"],
            "ops": [
                [
                    "ear_spot",
                    "spot both tap drills",
                    [
                        line
                        for xy in holes
                        for line in _spot(xy, pre_depth, pre_depth - spot_depth, clear)
                    ],
                ]
            ],
        }
    )
    jobs.append(
        {
            **drill_tool,
            "frame": "outside",
            "label": "ear drill",
            "stock": stocks["outside"],
            "ops": [
                [
                    "ear_drill",
                    "drill both tap drills #29",
                    [
                        line
                        for xy in holes
                        for line in _pecked(xy, pre_depth, tip, peck, clear)
                    ],
                ]
            ],
        }
    )

    # The pair bore: a climbing helix down from the taller half's top at the
    # rough radius to the run past the underside, a flat turn there, out to
    # the finish radius (the flutes now span the whole wall), a finish turn
    # and a spring turn, back to the centre, up. The opening file goes down
    # the open bore's centre, out to the opened radius, two turns, back.
    bore_clear = _r(bore_top + CLEAR_MM)
    rough = [
        f"G0 Z{bore_clear:.3f}",
        f"G0 X{_r(bore_x + r_rough):.3f} Y0.000",
        f"G0 Z{_r(bore_top + SAFE_MM):.3f}",
        f"G1 Z{_r(bore_top):.3f} F{{feed}}",
    ]
    for k in range(turns):
        rough += _circle(
            bore_x, r_rough, bore_top - k * pitch, bore_top - (k + 1) * pitch
        )
    rough += _circle(bore_x, r_rough, bore_bottom, bore_bottom)
    rough.append(f"G1 X{_r(bore_x + r_finish):.3f} F{{feed}}")
    rough += _circle(bore_x, r_finish, bore_bottom, bore_bottom) * 2
    rough += [f"G1 X{bore_x:.3f} F{{feed}}", f"G0 Z{bore_clear:.3f}"]
    opening = [
        f"G0 Z{bore_clear:.3f}",
        f"G0 X{bore_x:.3f} Y0.000",
        f"G0 Z{_r(bore_top + SAFE_MM):.3f}",
        f"G1 Z{_r(bore_bottom):.3f} F{{feed}}",
        f"G1 X{_r(bore_x + r_open):.3f} F{{feed}}",
        *(_circle(bore_x, r_open, bore_bottom, bore_bottom) * 2),
        f"G1 X{bore_x:.3f} F{{feed}}",
        f"G0 Z{bore_clear:.3f}",
    ]
    for key, label, lines in (
        ("pair_bore", "interpolate the pair's bore", rough),
        ("bore_open", "open the bore", opening),
    ):
        jobs.append(
            {
                **bore_tool,
                "frame": "pair",
                "label": label,
                "stock": stocks["pair"],
                "ops": [[key, label, lines]],
            }
        )
    levels, top, xs, ys, _y, _span, frame = faces["face_off"]
    jobs.append(
        {
            **em_tool,
            "frame": frame,
            "label": "face off",
            "stock": stocks[frame],
            "ops": [
                [
                    "face_off",
                    "face the grip offset off the mating face",
                    _face(levels, top, xs, ys),
                ]
            ],
        }
    )

    # One file per hole to tap (as the magnifying clamp's): the dead centre
    # loaded by the file's own M6, Z to the machine's top before any XY, over
    # the hole, M30: the controller ends Idle for the operator's jog.
    manual = {}
    for k, xy in enumerate(holes, 1):
        what = f"TAP DRILL {k}, THE ONE {'NEAR' if k == 1 else 'FAR FROM'} N"
        manual[f"tap_{k}"] = {
            "tool": numbers["dead-centre"],
            "label": names["dead-centre"],
            "setting": f"SPINDLE STAYS OFF. NEXT: 8-32 TAP IN {what}",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
                f"(8-32 TAP IN {what}. JOG Z DOWN ONTO THE WRENCH, LIGHT PRESSURE."
                " TAP BY HAND THROUGH TO THE NOTED DRO Z, JOGGING Z TO KEEP THE POINT SEATED. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": xy,
        }

    # Keep-outs.
    jaw_w = p["vise_jaw_width_mm"]

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
        x: tuple[float, float], y: tuple[float, float]
    ) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - PARALLEL_LENGTH_MM / 2, mid + PARALLEL_LENGTH_MM / 2)
        return [
            _box("moving-jaw parallels", span, (y[0], y[0] + t), 0.0),
            _box("fixed-jaw parallels", span, (y[1] - t, y[1]), 0.0),
        ]

    keep = {
        "first_end": jaws(upright_grip - (blank_min - end_skim), (-hs, hs), (-hs, hs)),
        "length": jaws(upright_grip, (-hs, hs), (-hs, hs)),
        "bottom_face": jaws(lying_grip, xr["bottom"], (-section, 0.0)),
        "top_face": jaws(lying_grip, xr["top"], (-section, 0.0)),
        "mating_face": jaws(lying_grip, xr["mating"], (-height, 0.0)),
        "outside_face": jaws(lying_grip, xr["outside"], (-height, 0.0)),
        "face_off": jaws(lying_grip - pre_depth, xr["face_off"], (-height, 0.0)),
    }
    drill_keep = keep["outside_face"] + parallels(xr["outside"], (-height, 0.0))
    pair_mid = width / 2
    pair_keep = [
        _box(
            "fixed jaw",
            (pair_mid - jaw_w / 2, pair_mid + jaw_w / 2),
            (pre_min, pre_min + JAW_DEPTH_MM),
            upright_grip,
        ),
        _box(
            "1-2-3 block",
            (
                bore_x - p["spacer_block_width_mm"] / 2,
                bore_x + p["spacer_block_width_mm"] / 2,
            ),
            (-front_max - p["spacer_block_length_mm"], -front_min),
            p["spacer_block_height_mm"] - p["parallel_height_mm"],
        ),
        _box(
            "front parallel",
            (pair_mid - PARALLEL_LENGTH_MM / 2, pair_mid + PARALLEL_LENGTH_MM / 2),
            (-front_max, -front_min + t),
            0.0,
        ),
        _box(
            "back parallel",
            (
                bore_x - p["back_parallel_end_mm"] - PARALLEL_LENGTH_MM,
                bore_x - p["back_parallel_end_mm"],
            ),
            (pre_min - t, pre_max),
            0.0,
        ),
    ]

    tn = numbers
    expect: list[list[Any]] = []

    def face_checks(key: str) -> list[list[Any]]:
        levels, top, _xs, _ys, y, span, _frame_key = faces[key]
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

    def hole_checks(bottom: float, radius: float) -> list[list[Any]]:
        return [
            ["holes", {"centres": holes, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": pre_depth, "open_holes": holes}],
            ["vertical_below_top", {"z_top": pre_depth}],
            ["air_feed", {"z_top": pre_depth}],
            ["keep_out", {"radius": radius, "boxes": drill_keep}],
        ]

    single = {
        "CB01_first_end": "first_end",
        "CB02_length": "length",
        "CB03_bottom": "bottom_face",
        "CB04_height": "top_face",
        "CB05_mating": "mating_face",
        "CB11_face_off": "face_off",
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
    name = "CB06_back_drill"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": mating_level,
                "tools": [tn["em-half"], tn["spot"], tn["drill-29"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[face_rpm], [spot_rpm], [drill_rpm]]}],
        [name, "pauses", {"z_top": mating_level, "count": 0}],
        [name, "depth", {"z_min": _r(tip)}],
    ]
    for k, checks in enumerate(
        (
            face_checks("outside_face"),
            hole_checks(pre_depth - spot_depth, CENTRE_DRILL["body_mm"] / 2),
            hole_checks(tip, d29 / 2),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]
    for name, key in (("CB07_tap_1", "tap_1"), ("CB08_tap_2", "tap_2")):
        expect += [
            [
                name,
                "tap_stop",
                {
                    "tool": tn["dead-centre"],
                    "at": manual[key]["at"],
                    "machine_top": MACHINE_Z_TOP_MM,
                },
            ],
            [name, "air_feed", {"z_top": pre_depth}],
        ]
    window = [[bore_x - big - 1.0, bore_x + big + 1.0], [-big - 1.0, big + 1.0]]
    for name, radius in (("CB09_pair_bore", r_finish), ("CB10_bore_open", r_open)):
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": bore_top, "tools": [tn["em-half"]], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[face_rpm]]}],
            [name, "pauses", {"z_top": bore_top, "count": 0}],
            [name, "depth", {"z_min": _r(bore_bottom)}],
            [
                name,
                "bounds",
                {
                    "window": window,
                    "x": [_r(bore_x - radius), _r(bore_x + radius)],
                    "y": [-_r(radius), _r(radius)],
                    "z_min": _r(bore_bottom),
                    "arc": "G3",
                    "z_top": bore_top,
                },
            ],
            [name, "rapids_clear", {"z_top": bore_top}],
            [name, "air_feed", {"z_top": bore_top}],
            [name, "keep_out", {"radius": r, "boxes": pair_keep}],
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
            doc, f"Clamp back {key}", ctx["step"], frame["origin"], frame["axes"]
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
