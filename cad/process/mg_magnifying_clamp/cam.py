"""FreeCAD CAM recipe for MHA-MG-02, the magnifying clamp.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The block's sizes
come from the feature export (its height, the hex, the cross bore and both
tapped holes); the blank, the bottom skim, face levels, spots, pecks, the
parallels and the drill's run past the corner from ``plan.toml``
``[parameters]`` and ``milling_cuts``; cutter diameters, speeds and feeds
from the shop (``shop/``). Every path is written here (``rt.custom``): straight
lines a recipe can state exactly. Typed here, because neither record carries
them: the #2 centre drill's catalogue geometry (it sets the spot depth), the
twist drills' 118° point, the machine's Z top for the tap files' retract,
the approach, safe and clearance heights, the face overhang and the vise
jaws' depth (keep-out shapes only).

Route (plan text in ``plan.toml``): the blank stands upright on two 1 in
parallels in the vise, bottom end up: MC01 faces the bottom, spots and
drills the rod hole (#43); MC02 brings the tap guide over it for tapping by
hand. It then lies corner up between the parallels: MC03 spots the corner
and drills F through both corners. Upright again, top end up: MC04 faces the
top to length in levels, spots and drills the thumb hole into the bore;
MC05 brings the tap guide over it.

Work frames (G54), each set in its setup:
- MC01/MC02: X0 Y0 the hex axis, Z0 the faced bottom end; the corners along
  X, +Y toward the fixed jaw.
- MC03: X0 the faced bottom end, +X along the block; Y0 the axis; Z0 the top
  corner.
- MC04/MC05: X0 Y0 the hex axis, Z0 the parallels' top (the faced bottom).

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock. The
holes are tapped by hand (FluidNC cannot rigid-tap; owner, Pedro,
2026-11-17), the T-handle wrench's centre hole on the spring point of the
Fisher tap guide in the 1/2 in R8 collet (owner, Pedro, 2026-11-21: "use
https://littlemachineshop.com/products/tap-guide-fisher?variant=45472915226805
on r8 0.5 collet"), spindle off, the operator jogging Z down to push the
point home. FluidNC, like Grbl, refuses jogs
while an M0 holds the program (FluidNC wiki, "Single Block Mode",
http://wiki.fluidnc.com/en/features/single_block_mode), so each tap stop is
a file of its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "mg_magnifying_clamp"
COMMENT = "MHA-MG-02 magnifying clamp"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("MC01_bottom", (("bottom_face",), ("rod_spot",), ("rod_drill",))),
    ("MC02_rod_tap", ("tap_rod",)),
    ("MC03_cross_bore", (("corner_spot",), ("cross_drill",))),
    ("MC04_top", (("top_face",), ("thumb_spot",), ("thumb_drill",))),
    ("MC05_thumb_tap", ("tap_thumb",)),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held, and each tap file before its
# retract (the tap guide).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (tools off the mill, the saw, the tap and the files, are
# not).
CAM_TOOLS = ("em-half", "spot", "drill-43", "drill-f", "tap-guide")
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included: the shop record names
# the tool, not its geometry.
CENTRE_DRILL = {
    "body_mm": 3 / 16 * IN,
    "pilot_mm": 5 / 64 * IN,
    "pilot_length_mm": 5 / 64 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# A tap file's first motion: G53 G0 to machine Z0, the homed top. FluidNC
# sets an axis's machine position to its homing mpos_mm (default 0) after
# homing, and Z homes up (cad/config/shop-equipment/
# cnc.pm-30mv-controller: switches on all three axes); the owner (Pedro)
# confirmed it, answered in person 2026-11-21 (cnc rulings record): machine
# Z = 0 is the top of travel after homing.
MACHINE_Z_TOP_MM = 0.0
# Face passes start and finish with the cutter this far clear of the
# block's corners, so every plunge and stepover link is in the air beside it.
APPROACH_MM = 2.54
# Faces reach at least this far past the flats the jaws grip.
FACE_OVERHANG_MM = 0.5
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped flat; the
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
    """(rpm, mm/min) of the shop setting the operation holding ``cut`` names:
    its chip load × flutes × rpm, or its stated in/min feed. A cut that
    states its own rpm and feed must agree."""
    op, record_cut = _op_with_cut(plan, cut)
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    if "chip_load_mm_per_tooth" in record:
        feed = record["chip_load_mm_per_tooth"] * record["flutes"] * rpm
    else:
        value, unit = record["feed"].split()
        if unit != "in/min":
            raise ValueError(
                f"settings.{op['settings']}: feed {record['feed']!r} is not in/min"
            )
        feed = float(value) * IN
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
    """Drill from ``top`` to ``tip``: in pecks of ``peck`` with a full
    retract to the R plane and a rapid back to just above the last peck, or
    in one feed when ``peck`` is None. Moves to and from the hole run at
    ``clear``."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    depths = []
    if peck is not None:
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


def _face(levels: list[float], top: float, x_run: float, ys: list[float]) -> list[str]:
    """Zigzag faces at ``levels``: at each, one X pass per Y in ``ys``,
    alternating direction, starting at -X; every plunge, level change and
    stepover beside the block, past its corners."""
    clear = _r(top + CLEAR_MM)
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{-x_run:.3f} Y{ys[0]:.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
    ]
    for z in levels:
        lines.append(f"G1 Z{_r(z):.3f} F{{feed}}")
        for k, y in enumerate(ys):
            x = x_run if k % 2 == 0 else -x_run
            if k:
                lines.append(f"G1 Y{y:.3f} F{{feed}}")
            lines.append(f"G1 X{x:.3f} F{{feed}}")
        if len(ys) % 2:
            # Back to the -X side, beside the block, for the next level.
            lines.append(f"G1 X{-x_run:.3f} F{{feed}}")
        if z != levels[-1]:
            lines.append(f"G1 Y{ys[0]:.3f} F{{feed}}")
    return lines + [f"G0 Z{clear:.3f}"]


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    f = features["features"]
    p = plan["parameters"]
    height = f["top_face"]["plane"]["value"] - f["bottom_face"]["plane"]["value"]
    band = f["top_face"]["height"]
    if not band[0] <= height <= band[1]:
        raise ValueError(
            f"model height {height:.4f} is outside the printed band {band}"
        )
    af, ac = f["hex_flats"]["af_ref"], f["hex_flats"]["ac_nominal"]
    bore, rod, thumb = f["lever_bore"], f["rod_tap"], f["thumb_tap"]
    bore_y, bore_dia = bore["at"][1], bore["nominal_dia"]
    if bore["axis"] != [1.0, 0.0, 0.0] or bore["at"][0] != 0 or bore["at"][2] != 0:
        raise ValueError("lever_bore: expected along X through the axis")
    for name, hole, at, axis in (
        ("rod_tap", rod, [0.0, 0.0, 0.0], [0.0, 1.0, 0.0]),
        ("thumb_tap", thumb, [0.0, height, 0.0], [0.0, -1.0, 0.0]),
    ):
        if hole["at"] != at or hole["axis"] != axis:
            raise ValueError(f"{name}: expected on the hex axis at {at}, along {axis}")

    blank_min, blank_max = p["blank_length_min_in"] * IN, p["blank_length_max_in"] * IN
    skim = p["bottom_skim_mm"]
    upright_top = blank_max - skim
    _agree(plan, "upright_top_max_mm", upright_top)
    if blank_min - skim < height:
        raise ValueError(
            f"the shortest blank less the skim, {blank_min - skim:.3f}, is under the height {height:.3f}"
        )

    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    d43 = _shop_tool(plan, shop, "drill-43")["diameter_mm"]
    dF = _shop_tool(plan, shop, "drill-f")["diameter_mm"]
    if not math.isclose(d43, rod["dia"][0], abs_tol=1e-3) or not math.isclose(
        d43, thumb["dia"][0], abs_tol=1e-3
    ):
        raise ValueError(f"#43 Ø{d43} is not the tapped holes' drill {rod['dia']}")
    if not bore["dia"][0] <= dF <= bore["dia"][1]:
        raise ValueError(f"F drill Ø{dF} outside the bore band {bore['dia']}")
    if not math.isclose(em, _cut(plan, "bottom face", "cutter_dia_mm"), abs_tol=1e-6):
        raise ValueError(
            f"'bottom face' cutter Ø{_cut(plan, 'bottom face', 'cutter_dia_mm')}, the end mill is Ø{em}"
        )

    # Faces: two passes, one each side of the axis a cutter radius out, so
    # each takes half the cutter; together they reach the cutter's radius
    # past both gripped flats. The plan's cuts declare that width.
    woc = em / 2
    for name in ("bottom face", "top face"):
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), woc, abs_tol=1e-3):
            raise ValueError(
                f"'{name}' radial_woc_mm {_cut(plan, name, 'radial_woc_mm')}: two passes take {woc:.3f}"
            )
    ys = [_r(woc), _r(-woc)]
    if woc + em / 2 < af / 2 + FACE_OVERHANG_MM:
        raise ValueError("the face passes do not reach past the gripped flats")
    x_run = _r(ac / 2 + em / 2 + APPROACH_MM)
    face_rpm, face_feed = _setting(plan, shop, "bottom face")
    if _setting(plan, shop, "top face") != (face_rpm, face_feed):
        raise ValueError("'top face' runs at another setting than 'bottom face'")
    if not math.isclose(_cut(plan, "bottom face", "axial_doc_mm"), skim, abs_tol=1e-6):
        raise ValueError("'bottom face' axial_doc_mm is not process.bottom_skim_mm")
    top_levels = _levels(upright_top, height, p["face_step_max_mm"])
    top_doc = (upright_top - height) / len(top_levels)
    if top_doc > _cut(plan, "top face", "axial_doc_mm") + 1e-9:
        raise ValueError(f"top levels of {top_doc:.3f} exceed 'top face' axial_doc_mm")

    # Holes. MC01: Z0 the faced bottom; the rod drill's full diameter to its
    # drawn depth. MC04: Z0 the bottom; the thumb drill's to its drawn depth,
    # the bore's axis. MC03: Z0 the top corner; through the far corner.
    spot_rpm, spot_feed = _setting(plan, shop, "rod spot")
    for name in ("corner spot", "thumb spot"):
        if _setting(plan, shop, name) != (spot_rpm, spot_feed):
            raise ValueError(f"'{name}' runs at another setting than 'rod spot'")
    d43_rpm, d43_feed = _setting(plan, shop, "rod drill")
    if _setting(plan, shop, "thumb drill") != (d43_rpm, d43_feed):
        raise ValueError("'thumb drill' runs at another setting than 'rod drill'")
    f_rpm, f_feed = _setting(plan, shop, "cross drill")
    for name, key in (
        ("rod spot", "end_spot_dia_mm"),
        ("thumb spot", "end_spot_dia_mm"),
        ("corner spot", "corner_spot_dia_mm"),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), p[key], abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not process.{key}")
    end_spot = _spot_depth(p["end_spot_dia_mm"])
    if p["end_spot_dia_mm"] >= d43:
        raise ValueError(
            "the end spot is not under the #43 drill: it would chamfer the MG-04 seat"
        )
    corner_spot = _spot_depth(p["corner_spot_dia_mm"])
    if p["corner_spot_dia_mm"] >= dF:
        raise ValueError("the corner spot is not under the F drill")
    rod_depth = rod["drill_depth_nominal"]
    thumb_depth = thumb["drill_depth_nominal"]
    rod_tip = -(rod_depth + _point(d43))
    thumb_tip = height - thumb_depth - _point(d43)
    if rod_depth + _point(d43) >= bore_y - bore["dia"][1] / 2:
        raise ValueError("the rod drill's point reaches the bore")
    if height - thumb_depth > bore_y + bore_dia / 2:
        raise ValueError("the thumb drill's full diameter does not break into the bore")
    _agree(plan, "rod_tip_height_mm", blank_min - skim + rod_tip)
    _agree(plan, "thumb_tip_height_mm", thumb_tip)
    # The plan's pecking check reads the depth this recipe drills: the
    # adapter's binding of the export's drill_depth_nominal.
    for name, binding in (
        ("rod drill", "{{cad.rod_drill_depth_mm}}"),
        ("thumb drill", "{{cad.thumb_drill_depth_mm}}"),
    ):
        stated = _op_with_cut(plan, name)[0]["hole_depth_mm"]
        if stated != binding:
            raise ValueError(
                f"'{name}' operation hole_depth_mm {stated!r}, not {binding}"
            )
    peck = p["peck_43_mm"]
    for name in ("rod drill", "thumb drill"):
        if _op_with_cut(plan, name)[0]["peck"] != {"step_mm": peck, "retract": "full"}:
            raise ValueError(
                f"'{name}' peck is not process.peck_43_mm with full retract"
            )

    # Cross setup: the corner-down block between the parallels. Its lower
    # diagonal flats (30° from horizontal) rest on the parallels' inner top
    # edges, the gap between them af − 2 × their thickness.
    gap = af - 2 * p["parallel_thickness_mm"]
    drop = gap / 2 * math.tan(math.radians(30))
    corner_top = ac - drop  # the top corner above the parallels' tops
    cross_tip = -(ac + p["cross_drill_past_mm"] + _point(dF))
    # Lying corner up, the block is wholly below the jaw tops: they stand
    # the grip less the top corner's height above Z0. Every move between
    # holes runs CLEAR_MM above them.
    grip = p["vise_jaw_height_mm"] - p["parallel_height_mm"]
    _agree(plan, "upright_grip_mm", grip)
    cross_jaw_top = grip - corner_top
    cross_clear = max(0.0, cross_jaw_top) + CLEAR_MM
    _agree(plan, "cross_tip_height_mm", corner_top + cross_tip)
    if bore_y - bore["dia"][1] / 2 <= p["cross_parallel_end_mm"]:
        raise ValueError("the parallels reach under the bore")

    names = {t["id"]: t["name"] for t in plan["tools"]}
    numbers = {
        t["id"]: n
        for n, t in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    centre = [0.0, 0.0]
    bore_xy = [_r(bore_y), 0.0]
    em_tool = {"tool": "em-half", "dia": em, "shape": "endmill", "flutes": 3}
    spot_tool = {
        "tool": "spot",
        "dia": CENTRE_DRILL["body_mm"],
        "shape": "drill",
        "tip_angle": CENTRE_DRILL["point_deg"],
        "rpm": spot_rpm,
        "feed": spot_feed,
        "plunge": spot_feed,
    }
    d43_tool = {
        "tool": "drill-43",
        "dia": d43,
        "shape": "drill",
        "tip_angle": DRILL_POINT_DEG,
        "rpm": d43_rpm,
        "feed": d43_feed,
        "plunge": d43_feed,
    }
    f_tool = {
        "tool": "drill-f",
        "dia": dF,
        "shape": "drill",
        "tip_angle": DRILL_POINT_DEG,
        "rpm": f_rpm,
        "feed": f_feed,
        "plunge": f_feed,
    }
    # Frames (model point p -> axes · (p - origin)), stocks and tops.
    frames = {
        "bottom": {
            "origin": [0.0, 0.0, 0.0],
            "axes": [[1, 0, 0], [0, 0, 1], [0, -1, 0]],
        },
        "cross": {
            "origin": [ac / 2, 0.0, 0.0],
            "axes": [[0, 1, 0], [0, 0, 1], [1, 0, 0]],
        },
        "top": {"origin": [0.0, 0.0, 0.0], "axes": [[1, 0, 0], [0, 0, -1], [0, 1, 0]]},
    }
    hx, hy = ac / 2, af / 2
    stock_bottom = ((-hx, hx), (-hy, hy), (-upright_top, skim))
    stock_cross = ((0.0, upright_top), (-hy, hy), (-ac, 0.0))
    stock_top = ((-hx, hx), (-hy, hy), (0.0, upright_top))
    jobs = [
        {
            **em_tool,
            "frame": "bottom",
            "label": "bottom face",
            "rpm": face_rpm,
            "feed": face_feed,
            "plunge": face_feed,
            "stock": stock_bottom,
            "ops": [
                ["bottom_face", "face the bottom end", _face([0.0], skim, x_run, ys)]
            ],
        },
        {
            **spot_tool,
            "frame": "bottom",
            "label": "rod spot",
            "stock": stock_bottom,
            "ops": [
                [
                    "rod_spot",
                    "spot the rod hole",
                    _spot(centre, 0.0, -end_spot, CLEAR_MM),
                ]
            ],
        },
        {
            **d43_tool,
            "frame": "bottom",
            "label": "rod drill",
            "stock": stock_bottom,
            "ops": [
                [
                    "rod_drill",
                    "drill the rod hole",
                    _pecked(centre, 0.0, rod_tip, peck, CLEAR_MM),
                ]
            ],
        },
        {
            **spot_tool,
            "frame": "cross",
            "label": "corner spot",
            "rpm": spot_rpm,
            "stock": stock_cross,
            "ops": [
                [
                    "corner_spot",
                    "spot the top corner",
                    _spot(bore_xy, 0.0, -corner_spot, cross_clear),
                ]
            ],
        },
        {
            **f_tool,
            "frame": "cross",
            "label": "cross drill",
            "stock": stock_cross,
            "ops": [
                [
                    "cross_drill",
                    "drill F through the corners",
                    _pecked(bore_xy, 0.0, cross_tip, None, cross_clear),
                ]
            ],
        },
        {
            **em_tool,
            "frame": "top",
            "label": "top face",
            "rpm": face_rpm,
            "feed": face_feed,
            "plunge": face_feed,
            "stock": stock_top,
            "ops": [
                [
                    "top_face",
                    "face the top to length",
                    _face(top_levels, upright_top, x_run, ys),
                ]
            ],
        },
        {
            **spot_tool,
            "frame": "top",
            "label": "thumb spot",
            "stock": stock_top,
            "ops": [
                [
                    "thumb_spot",
                    "spot the thumb hole",
                    _spot(centre, height, height - end_spot, height + CLEAR_MM),
                ]
            ],
        },
        {
            **d43_tool,
            "frame": "top",
            "label": "thumb drill",
            "stock": stock_top,
            "ops": [
                [
                    "thumb_drill",
                    "drill the thumb hole into the bore",
                    _pecked(centre, height, thumb_tip, peck, height + CLEAR_MM),
                ]
            ],
        },
    ]

    # One file per hole to tap: the tap guide loaded by the file's own M6
    # (its %msg names the hole), Z to the machine's top in machine
    # coordinates before any XY (the operator left Z jogged down after the
    # last tool change or tap), over the hole, M30: the controller ends Idle,
    # so the operator can jog the guide's point down into the wrench.
    manual = {}
    for key, what in (
        ("tap_rod", "THE ROD HOLE, BOTTOM END"),
        ("tap_thumb", "THE THUMB HOLE, TOP END"),
    ):
        manual[key] = {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": f"SPINDLE STAYS OFF. NEXT: 4-40 TAP IN {what}",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{centre[0]:.3f} Y{centre[1]:.3f}",
                f"(4-40 TAP IN {what}. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND TO THE NOTED DRO Z, READ WITH THE POINT PUSHED HOME. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": centre,
        }

    # Keep-outs. Upright: the jaws grip the flats at ±af/2 from the parallels'
    # tops to the jaw tops; across the cutter's whole X run.
    jaw_x = (-p["vise_jaw_width_mm"] / 2, p["vise_jaw_width_mm"] / 2)

    def jaws(z_top, x=jaw_x):
        return [
            _box("moving jaw", x, (-hy - JAW_DEPTH_MM, -hy), z_top),
            _box("fixed jaw", x, (hy, hy + JAW_DEPTH_MM), z_top),
        ]

    # MC01: the jaw tops below the faced bottom by the shortest blank less
    # the skim, less the grip.
    jaws_bottom = jaws(grip - (blank_min - skim))
    jaws_top = jaws(grip)
    # MC03: the parallels' tops corner_top below Z0, from the bottom end
    # cross_parallel_end_mm in, out to the left; the jaws above them grip the
    # vertical flats to the jaw tops.
    par_top = -corner_top
    par_x = (
        p["cross_parallel_end_mm"] - PARALLEL_LENGTH_MM,
        p["cross_parallel_end_mm"],
    )
    cross_boxes = [
        _box("moving-jaw parallel", par_x, (-hy, -gap / 2), par_top),
        _box("fixed-jaw parallel", par_x, (gap / 2, hy), par_top),
        _box(
            "vise bed",
            (par_x[0], upright_top),
            (-hy, hy),
            par_top - p["parallel_height_mm"],
        ),
        # The block centred on the jaws along X.
        *jaws(cross_jaw_top, (jaw_x[0] + upright_top / 2, jaw_x[1] + upright_top / 2)),
    ]

    t = numbers
    expect: list[list[Any]] = []

    def hole_checks(centres, top, bottom, radius, boxes):
        return [
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": top, "open_holes": centres}],
            ["vertical_below_top", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": radius, "boxes": boxes}],
        ]

    def face_checks(levels, top, boxes):
        return [
            ["depth", {"z_min": _r(levels[-1])}],
            ["rapids_clear", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            *[
                [
                    "face_passes",
                    {
                        "z": _r(z),
                        "y": [-hy, hy],
                        "max_engagement": woc,
                        "radius": em / 2,
                        "span": ac,
                        "overhang": FACE_OVERHANG_MM,
                    },
                ]
                for z in levels
            ],
            ["keep_out", {"radius": em / 2, "boxes": boxes}],
        ]

    programs = {
        "MC01_bottom": (
            skim,
            [t["em-half"], t["spot"], t["drill-43"]],
            [[face_rpm], [spot_rpm], [d43_rpm]],
            rod_tip,
            [
                face_checks([0.0], skim, jaws_bottom),
                hole_checks(
                    [centre], 0.0, -end_spot, CENTRE_DRILL["body_mm"] / 2, jaws_bottom
                ),
                hole_checks([centre], 0.0, rod_tip, d43 / 2, jaws_bottom),
            ],
        ),
        # Lying corner up, the jaw tops stand above the block: every tool
        # change and every move across to the hole stays above them.
        "MC03_cross_bore": (
            max(0.0, cross_jaw_top),
            [t["spot"], t["drill-f"]],
            [[spot_rpm], [f_rpm]],
            cross_tip,
            [
                hole_checks(
                    [bore_xy],
                    0.0,
                    -corner_spot,
                    CENTRE_DRILL["body_mm"] / 2,
                    cross_boxes,
                ),
                hole_checks([bore_xy], 0.0, cross_tip, dF / 2, cross_boxes),
            ],
        ),
        "MC04_top": (
            upright_top,
            [t["em-half"], t["spot"], t["drill-43"]],
            [[face_rpm], [spot_rpm], [d43_rpm]],
            thumb_tip,
            [
                face_checks(top_levels, upright_top, jaws_top),
                hole_checks(
                    [centre],
                    height,
                    height - end_spot,
                    CENTRE_DRILL["body_mm"] / 2,
                    jaws_top,
                ),
                hole_checks([centre], height, thumb_tip, d43 / 2, jaws_top),
            ],
        ),
    }
    for name, (top, tools, speeds, deepest, sections) in programs.items():
        expect += [
            [name, "tool_changes", {"z_top": top, "tools": tools, "loads_first": True}],
            [name, "spindle", {"rpm": speeds}],
            [name, "pauses", {"z_top": top, "count": 0}],
            [name, "depth", {"z_min": _r(deepest)}],
        ]
        for k, checks in enumerate(sections):
            expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]
    for name, key, top in (
        ("MC02_rod_tap", "tap_rod", 0.0),
        ("MC05_thumb_tap", "tap_thumb", height),
    ):
        expect += [
            [
                name,
                "tap_stop",
                {
                    "tool": t["tap-guide"],
                    "at": manual[key]["at"],
                    "machine_top": MACHINE_Z_TOP_MM,
                },
            ],
            [name, "air_feed", {"z_top": top}],
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
            doc, f"Clamp {key}", ctx["step"], frame["origin"], frame["axes"]
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


def as_machined(ctx: dict[str, Any], inputs: Any) -> dict[str, Any]:
    """The sawn blank of 1/2 in hex bar in MC01's frame: a hex prism along Z
    on the hex axis, the plan's blank_af_in across the flats on Y, its
    corners on X; the sawn bottom end at +bottom_skim_mm stays put (Z0 is
    set from its high point less the skim), the length down Z at the plan's
    blank_length_min_in-blank_length_max_in band and its middle (the plan
    marks no nominal length). Every program runs in its jobs' frame, in
    order; the tap files (MC02, MC05) cut nothing."""
    p = inputs.plan["parameters"]
    lengths = {
        "nominal": (p["blank_length_min_in"] + p["blank_length_max_in"]) / 2 * IN,
        "min": p["blank_length_min_in"] * IN,
        "max": p["blank_length_max_in"] * IN,
    }
    hy = p["blank_af_in"] * IN / 2
    hx = 2 * hy / math.sqrt(3)
    skim = p["bottom_skim_mm"]
    return {
        "parts": {
            "": {
                "blank": {
                    "frame": "bottom",
                    "prism": {
                        "axis": "z",
                        "polygon": [
                            [hx, 0.0],
                            [hx / 2, hy],
                            [-hx / 2, hy],
                            [-hx, 0.0],
                            [-hx / 2, -hy],
                            [hx / 2, -hy],
                        ],
                        "span": [skim - lengths["nominal"], skim],
                    },
                    "length": {"axis": "z", "keep": "max", "mm": lengths},
                }
            }
        },
        "skip": {},
    }
