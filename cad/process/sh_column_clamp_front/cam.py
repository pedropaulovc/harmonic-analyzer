"""FreeCAD CAM recipe for MHA-SH-01, the column clamp front.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The half's sizes come
from the feature export (its width, height and depth, both ear holes and the
bore they straddle); the blank, the skims, face levels, spots, pecks and the
riser from ``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter
diameters, speeds and feeds from the shop (``shop/``) and the plan's authored drill
settings. Every path is written here (``rt.custom``): straight lines a recipe
can state exactly. Typed here, because neither record carries them: the #2
centre drill's catalogue geometry (it sets the spot depth), the twist drills'
118° point, the approach, safe and clearance heights, the face overhang and
the vise jaws' depth (keep-out shapes only).

Route (owner ruling 2026-11-20; plan text in ``plan.toml``): one 3/4 in
square 1018 blank about 2.0 long per run. Upright on a 1 in parallel pair:
CF01 faces the first end, CF02 (turned over) faces the other end to the
width. Lying on the 1 in + 1/2 in parallel stacks: CF03 faces the bottom
face, CF04 (bottom down) the top face to the height, CF05 (jaws on the top
and bottom faces) skims the mating face, CF06 (mating face down) faces the
bar face to the depth, then spots and drills both #9 ear holes from one zero.
The bore is not cut here: MHA-SH-02's traveler bolts each front to its back
and interpolates the full bore on the split line (its ``CB09_pair_bore``).

Work frames (G54), each set in its setup:
- CF01: X0 Y0 the bar's axis, Z0 the faced first end.
- CF02: X0 Y0 the bar's axis, Z0 the parallels' top (the first end).
- CF03-CF05: X0 the left end, Y0 the fixed jaw, Z0 the parallels' top.
- CF06: X0 the RIGHT end (the near side, marked N), Y0 the fixed jaw (the
  bottom face, marked B, against it), Z0 the parallels' top (the mating
  face). The holes' stations from N and height from B are the drawing's.

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "sh_column_clamp_front"
COMMENT = "MHA-SH-01 column clamp front"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("CF01_first_end", ("first_end",)),
    ("CF02_length", ("length",)),
    ("CF03_bottom", ("bottom_face",)),
    ("CF04_height", ("top_face",)),
    ("CF05_mating", ("mating_face",)),
    ("CF06_bar_drill", (("outside_face",), ("ear_spot",), ("ear_drill",))),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw and the files are not).
CAM_TOOLS = ("em-half", "spot", "drill-9")
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


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The half's sizes and ear holes from the export, each checked against
    the frame the recipe assumes: the mating face X0 with the bar face at +X,
    the bore axis along Y at the origin, the height along Y centred, the
    width along Z with the near side at +Z."""
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
    if f["mating_face"]["plane"]["value"] != 0.0:
        raise ValueError("mating_face: expected at model X0")
    depth = f["bar_face"]["plane"]["value"]
    if not math.isclose(depth, f["bar_face"]["depth_nominal"], abs_tol=1e-3):
        raise ValueError(
            f"bar face at X {depth:.4f} is not the depth {f['bar_face']['depth_nominal']}"
        )
    bore = f["bore"]
    if bore["at"] != [0.0, 0.0, 0.0] or bore["axis"] != [0.0, 1.0, 0.0]:
        raise ValueError("bore: expected along Y through the model origin")
    bore_max = bore["mate_od_nominal"] + bore["diametral_clearance"][1]
    holes = []
    for name in ("ear_hole_1", "ear_hole_2"):
        hole = f[name]
        if hole["axis"] != [-1.0, 0.0, 0.0] or not math.isclose(
            hole["at"][0], depth, abs_tol=1e-3
        ):
            raise ValueError(
                f"{name}: expected through the part from the bar face along -X"
            )
        station = abs(hole["at"][2])
        if (
            not hole["station"][0]
            <= math.copysign(station, hole["at"][2])
            <= hole["station"][1]
        ):
            raise ValueError(
                f"{name}: Z {hole['at'][2]} is outside its station band {hole['station']}"
            )
        if not math.isclose(
            hole["at"][1] - bottom, hole["height_nominal"], abs_tol=1e-3
        ):
            raise ValueError(
                f"{name}: its height from the bottom is not {hole['height_nominal']}"
            )
        # The ear wall at the band extremes: the nearest station, the
        # largest hole and the largest bore (drawing note 1, MIN EAR WALL).
        wall = min(abs(s) for s in hole["station"]) - hole["dia"][1] / 2 - bore_max / 2
        if wall < hole["web_to_bore_min"] - 1e-6:
            raise ValueError(
                f"{name}: worst ear wall {wall:.4f} under the drawn {hole['web_to_bore_min']}"
            )
        holes.append(
            {
                "name": name,
                "at": hole["at"],
                "dia": hole["dia"],
                "nominal": hole["nominal_dia"],
            }
        )
    return {
        "width": width,
        "height": height,
        "depth": depth,
        "near": near,
        "bottom": bottom,
        "holes": holes,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    width, height, depth = g["width"], g["height"], g["depth"]

    # The blank: the square bar's section, sawn to length.
    section = p["blank_section_in"] * IN
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
    if bottom_level <= height or mating_level <= depth:
        raise ValueError(
            "the section leaves nothing to face to the height or the depth"
        )

    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    d9 = _shop_tool(plan, shop, "drill-9")["diameter_mm"]
    r = em / 2
    for hole in g["holes"]:
        if not hole["dia"][0] <= d9 <= hole["dia"][1]:
            raise ValueError(f"#9 Ø{d9} is outside {hole['name']}'s band {hole['dia']}")
    step_max = p["face_stepover_max_mm"]
    face_cuts = (
        "first end",
        "length",
        "bottom face",
        "height",
        "mating face",
        "outside face",
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
    level_max = p["face_step_max_mm"]
    length_levels = _levels(upright_top, width, level_max)
    height_levels = _levels(bottom_level, height, level_max)
    depth_levels = _levels(mating_level, depth, level_max)
    for name in ("length", "height", "outside face"):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), level_max, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not process.face_step_max_mm")

    # Holes: spot under the drill (no chamfer at the mouth), then the #9
    # pecked with full retracts until its full diameter is past the mating
    # face, into the gap between the parallels.
    spot_rpm, spot_feed = _setting(plan, shop, "ear spot")
    drill_rpm, drill_feed = _setting(plan, shop, "ear drill")
    if not math.isclose(
        _cut(plan, "ear spot", "cutter_dia_mm"), p["spot_dia_mm"], abs_tol=1e-6
    ):
        raise ValueError("'ear spot' cutter_dia_mm is not process.spot_dia_mm")
    if p["spot_dia_mm"] >= d9:
        raise ValueError(
            "the spot is not under the #9 drill: it would chamfer the hole"
        )
    spot_depth = _spot_depth(p["spot_dia_mm"])
    peck = p["peck_mm"]
    op = _op_with_cut(plan, "ear drill")[0]
    if op["peck"] != {"step_mm": peck, "retract": "full"}:
        raise ValueError("'ear drill' peck is not process.peck_mm with full retract")
    if op["hole_depth_mm"] != "{{cad.depth_mm}}":
        raise ValueError("'ear drill' hole_depth_mm is not {{cad.depth_mm}}")
    tip = -(p["drill_past_mm"] + _point(d9))
    _agree(plan, "drill_tip_height_mm", tip)

    # Vise: upright on the single 1 in pair, lying on the stacked risers.
    upright_grip = p["vise_jaw_height_mm"] - p["parallel_height_mm"]
    lying_grip = p["vise_jaw_height_mm"] - p["riser_height_mm"]
    _agree(plan, "upright_grip_mm", upright_grip)
    _agree(plan, "lying_grip_mm", lying_grip)
    t = p["parallel_thickness_mm"]

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)). Raw faces: the mating
    # face's skim beyond X0, the bar face the rest of the section beyond it;
    # the bottom face's skim below it, the top face the rest above.
    raw_mating = -mating_skim
    raw_outside = raw_mating + section
    raw_bottom = g["bottom"] - bottom_skim
    raw_top = raw_bottom + section
    centre_x = (raw_mating + raw_outside) / 2
    centre_y = (raw_bottom + raw_top) / 2
    far = g["near"] - width
    frames = {
        "first_end": _frame([centre_x, centre_y, far], [0, -1, 0], [0, 0, -1]),
        "length": _frame([centre_x, centre_y, far], [0, 1, 0], [0, 0, 1]),
        # Bottom up, the raw bar face against the fixed jaw: the near side
        # lands at the left end (X0).
        "bottom": _frame([raw_outside, raw_top, g["near"]], [1, 0, 0], [0, -1, 0]),
        "top": _frame([raw_mating, g["bottom"], g["near"]], [-1, 0, 0], [0, 1, 0]),
        "mating": _frame([raw_outside, g["bottom"], g["near"]], [0, -1, 0], [-1, 0, 0]),
        # Bar face up, B against the fixed jaw: the near side N is the RIGHT end.
        "outside": _frame([0.0, g["bottom"], g["near"]], [0, -1, 0], [1, 0, 0]),
    }
    hs = section / 2
    lying_x = (0.0, width)
    stocks = {
        "first_end": ((-hs, hs), (-hs, hs), (-upright_top, end_skim)),
        "length": ((-hs, hs), (-hs, hs), (0.0, upright_top)),
        "bottom": (lying_x, (-section, 0.0), (0.0, section)),
        "top": (lying_x, (-section, 0.0), (0.0, bottom_level)),
        "mating": (lying_x, (-height, 0.0), (0.0, section)),
        "outside": ((-width, 0.0), (-height, 0.0), (0.0, mating_level)),
    }
    for key, frame in frames.items():
        # Every frame's part corner lands where its stock says.
        if key in ("bottom", "top", "mating"):
            x0 = _to(frame, [0.0, 0.0, g["near"]])[0]
            if not math.isclose(x0, 0.0, abs_tol=1e-6):
                raise ValueError(f"{key}: the near side is not at X0")
    holes = []
    for hole in g["holes"]:
        x, y, _z = _to(frames["outside"], hole["at"])
        holes.append([_r(x), _r(y)])
    if not all(-width < x < 0 and -height < y < 0 for x, y in holes):
        raise ValueError(f"ear holes {holes} are not on the part in the CF06 frame")
    # The holes clear the parallels: each between the stacks, inside them.
    for x, y in holes:
        if not (-height + t < y - d9 / 2 and y + d9 / 2 < -t):
            raise ValueError(f"the ear hole at Y {y} reaches a parallel ({t} thick)")

    em_tool = {
        "tool": "em-half",
        "dia": em,
        "shape": "endmill",
        "flutes": 3,
        "rpm": face_rpm,
        "feed": face_feed,
        "plunge": face_feed,
    }
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
        "tool": "drill-9",
        "dia": d9,
        "shape": "drill",
        "tip_angle": DRILL_POINT_DEG,
        "rpm": drill_rpm,
        "feed": drill_feed,
        "plunge": drill_feed,
    }

    # Passes: upright the square section in X and Y; lying the width along X
    # (from X0 at the left end, or to X0 at the right in CF06) and the
    # gripped span across Y from the fixed jaw (Y0) down.
    def run(x: tuple[float, float]) -> tuple[float, float]:
        return (x[0] - r - APPROACH_MM, x[1] + r + APPROACH_MM)

    upright_ys = _stations((-hs, hs), r, step_max)
    square_ys = _stations((-section, 0.0), r, step_max)
    split_ys = _stations((-height, 0.0), r, step_max)
    faces = {
        "first_end": ([0.0], end_skim, run((-hs, hs)), upright_ys, (-hs, hs), section),
        "length": (
            length_levels,
            upright_top,
            run((-hs, hs)),
            upright_ys,
            (-hs, hs),
            section,
        ),
        "bottom_face": (
            [bottom_level],
            section,
            run(lying_x),
            square_ys,
            (-section, 0.0),
            width,
        ),
        "top_face": (
            height_levels,
            bottom_level,
            run(lying_x),
            square_ys,
            (-section, 0.0),
            width,
        ),
        "mating_face": (
            [mating_level],
            section,
            run(lying_x),
            split_ys,
            (-height, 0.0),
            width,
        ),
        "outside_face": (
            depth_levels,
            mating_level,
            run((-width, 0.0)),
            split_ys,
            (-height, 0.0),
            width,
        ),
    }
    frame_of = {
        "first_end": "first_end",
        "length": "length",
        "bottom_face": "bottom",
        "top_face": "top",
        "mating_face": "mating",
        "outside_face": "outside",
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
    clear = depth + CLEAR_MM
    jobs.append(
        {
            **spot_tool,
            "frame": "outside",
            "label": "ear spot",
            "stock": stocks["outside"],
            "ops": [
                [
                    "ear_spot",
                    "spot both ear holes",
                    [
                        line
                        for xy in holes
                        for line in _spot(xy, depth, depth - spot_depth, clear)
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
                    "drill both ear holes #9",
                    [
                        line
                        for xy in holes
                        for line in _pecked(xy, depth, tip, peck, clear)
                    ],
                ]
            ],
        }
    )

    # Keep-outs. Upright: the jaws grip two faces of the square from the
    # parallels' top to the jaw top, across the jaw width. Lying: the jaws
    # beside the gripped span from the riser's top to the jaw top; the
    # parallel stacks under its edges.
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
        "bottom_face": jaws(lying_grip, lying_x, (-section, 0.0)),
        "top_face": jaws(lying_grip, lying_x, (-section, 0.0)),
        "mating_face": jaws(lying_grip, lying_x, (-height, 0.0)),
        "outside_face": jaws(lying_grip, (-width, 0.0), (-height, 0.0)),
    }
    drill_keep = keep["outside_face"] + parallels((-width, 0.0), (-height, 0.0))

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

    def hole_checks(bottom: float, radius: float) -> list[list[Any]]:
        return [
            ["holes", {"centres": holes, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": depth, "open_holes": holes}],
            ["vertical_below_top", {"z_top": depth}],
            ["air_feed", {"z_top": depth}],
            ["keep_out", {"radius": radius, "boxes": drill_keep}],
        ]

    single = {
        "CF01_first_end": "first_end",
        "CF02_length": "length",
        "CF03_bottom": "bottom_face",
        "CF04_height": "top_face",
        "CF05_mating": "mating_face",
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
    name = "CF06_bar_drill"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": mating_level,
                "tools": [tn["em-half"], tn["spot"], tn["drill-9"]],
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
            hole_checks(depth - spot_depth, CENTRE_DRILL["body_mm"] / 2),
            hole_checks(tip, d9 / 2),
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
            doc, f"Clamp front {key}", ctx["step"], frame["origin"], frame["axes"]
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
