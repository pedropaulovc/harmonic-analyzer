"""FreeCAD CAM recipe for MHA-DT-24, the pinion return leaf spring: its #30
hole, and the forming numbers the traveler prints.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The hole's diameter
band and its station from the pad's end, the strip's thickness band and
developed length, both bends' radius bands and formed angles and the flat
come from the feature export; the piece, the tape stack, the cover, the
vise, the pecks, the drill's run past the strip and the strip's modulus and
yield from ``plan.toml`` ``[parameters]`` and ``milling_cuts``; the #30's and
the #2 mandrel's diameters from ``shop/``. Every path is written here
(``rt.custom``). Typed here, because neither record carries them: the twist
drill's 118° point, the safe and clearance heights and the vise jaws' depth
(keep-out shapes only).

Route (``plan.toml``): a .60 x 2.50 in piece hacksawed off the 17-7 PH roll
is bonded on blue tape and CA glue to the spoil plate on 1 in parallels
across the vise jaws, and a 1 in length of the 1/2 x 3/4 in 6061 bar is
bonded over it on its 1/2 in face, the same way. PS01 pecks the #30 through
the cover, the strip and both tape stacks into the plate, so the drill meets
the .015 strip backed on both faces (no breakthrough grab, no lobing). The
outline is then filed from the hole at the bench, and the two bends formed
over the #2 drill's shank in the bench vise.

Work frame (G54): X0 the plate's left end, +X along the jaws; Y0 the fixed
jaw's face, +Y toward it; Z0 the plate's bare top. The piece lies with its
pad end to the left: model -X (the developed strip from the pad's end) runs
work +X, model +Y (the strip's top face) work +Z, model +Z (the pad's wing
side) work +Y.

Forming (no program): the formed radius of a strip let go from a mandrel of
radius Ri is Rf = Ri / (4x^3 - 3x + 1), x = Ri Y / (E t) (the springback
relation the platen clip's former uses), and the bend's angle springs back
by (Ri + t/2) / (Rf + t/2), its mid-surface keeping its length. The context
checks the #2 shank's formed radius against both bends' printed bands at the
strip's thickness limits and the yield on record, and how far the yield may
rise before the radius leaves them.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_pinion_spring"
COMMENT = "MHA-DT-24 pinion return leaf spring"
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (("PS01_hole", (("hole_drill",),)),)
# The program loads its own tool (M6, the tool setter).
LOAD_FIRST_TOOL = ("PS01_hole",)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these.
CAM_TOOLS = ("drill-30",)
IN = 25.4
# Jobber drills' point (the shop record gives the diameter only).
DRILL_POINT_DEG = 118.0
# The R plane stands this far above the cover's highest top: real G0 brings
# the drill down to it.
SAFE_MM = 1.0
# Moves to and from the hole run this far above the higher of the jaw tops
# and the cover; the drill stands out of the chuck at least the cover's top
# over its tip plus this.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Setup 3 marks the rough outline this far outside the finished edges.
MARK_OUTSIDE_IN = 1 / 32
# Keep-outs: each vise jaw's depth outward from the gripped plate.
JAW_DEPTH_MM = IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# A plan number in inches agrees to its printed .001.
PLAN_TOL_IN = 0.0005
# An inch acceptance printed to .001 is rounded inward to it.
READ_STEP_IN = 0.001


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


def _speed(plan: dict[str, Any], shop: dict[str, Any], cut: str) -> tuple[float, float]:
    """(rpm, mm/min) of the shop setting the cut's operation names: its rpm,
    and its chip load per lip times the lips times the rpm."""
    op, _record = _op_with_cut(plan, cut)
    setting = shop["settings"][op["settings"]]
    rpm = float(setting["rpm"])
    return rpm, rpm * setting["flutes"] * setting["chip_load_mm_per_tooth"]


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


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


def _agree_inward(plan: dict[str, Any], key: str, band_mm: tuple[float, float]) -> None:
    """``<key>_min_in``/``_max_in``: a band in mm, printed in inches rounded
    inward to the calipers' .001."""
    low = math.ceil(band_mm[0] / IN / READ_STEP_IN - 1e-6) * READ_STEP_IN
    high = math.floor(band_mm[1] / IN / READ_STEP_IN + 1e-6) * READ_STEP_IN
    _agree(plan, f"{key}_min_in", low, 1e-6)
    _agree(plan, f"{key}_max_in", high, 1e-6)


def _point(dia: float) -> float:
    """A twist drill's point length."""
    return dia / 2 / math.tan(math.radians(DRILL_POINT_DEG / 2))


def _pecked(
    xy: list[float], top: float, tip: float, peck: float, clear: float
) -> list[str]:
    """Drill from ``top`` (the cover's highest top) to ``tip`` in pecks of
    ``peck``, each with a full retract to the R plane and a rapid back to
    just above the last peck. Moves to and from the hole run at ``clear``."""
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


def _springback(ri: float, yield_mpa: float, modulus: float, t: float) -> float:
    """Ri/Rf of a strip bent to inside radius ``ri`` and let go:
    4x^3 - 3x + 1, x = Ri Y / (E t); 0 (no set) from x = 1/2, where the
    bend stays elastic."""
    x = min(ri * yield_mpa / (modulus * t), 0.5)
    return 4 * x**3 - 3 * x + 1


def _formed_radius(ri: float, yield_mpa: float, modulus: float, t: float) -> float:
    k = _springback(ri, yield_mpa, modulus, t)
    if k <= 0:
        raise ValueError("the bend over the mandrel stays elastic: no set")
    return ri / k


def _yield_limit(ri: float, modulus: float, t: float, radius_max: float) -> float:
    """The yield at which the strip let go from ``ri`` forms ``radius_max``
    (springback grows with the yield), by bisection."""
    low, high = 1.0, modulus * t / ri / 2
    for _ in range(80):
        mid = (low + high) / 2
        if ri / _springback(ri, mid, modulus, t) < radius_max:
            low = mid
        else:
            high = mid
    return low


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The strip, its hole and its bends from the export (model frame, mm)."""
    f = features["features"]
    strip, hole, bend, kink, flat = (
        f[name] for name in ("strip", "hole", "bend", "kink", "flat")
    )
    if strip["kind"] != "blank" or strip["section"] != "strip":
        raise ValueError("strip: expected the strip blank")
    if hole["x_from"] != "free_end" or hole["z_from"] != "pad_edge":
        raise ValueError(
            "hole: expected its station from the free end and the pad edge"
        )
    if hole["axis"] != [0.0, -1.0, 0.0] or "thru" not in hole["requirements"]:
        raise ValueError("hole: expected a through hole down the strip's thickness")
    if not math.isclose(
        f["free_end"]["plane"]["value"] - hole["at"][0], hole["x_nominal"], abs_tol=1e-6
    ):
        raise ValueError("hole: 'at' is not its station from the free end")
    for name in ("bend", "kink"):
        if f[name]["kind"] != "bend" or "radius" not in f[name]:
            raise ValueError(f"{name}: expected a bend with its inside radius")
    if flat["length_from"] != "kink":
        raise ValueError("flat: expected its length from the kink")
    return {
        "thick": strip["thickness_nominal"],
        "thick_band": strip["thickness"],
        "width": strip["width"],
        "developed": strip["developed_length"],
        "hole_dia": hole["dia"],
        "hole_x": hole["x_nominal"],
        "hole_x_band": hole["x"],
        "hole_z": hole["z_nominal"],
        "hole_z_band": hole["z"],
        "pad_width": f["pad_edge"]["width_nominal"],
        "pad_width_band": f["pad_edge"]["width"],
        "strip_width": f["strip_edge"]["width_nominal"],
        "strip_width_band": f["strip_edge"]["width"],
        "wing": f["pad_wing"]["length_nominal"],
        "wing_band": f["pad_wing"]["length"],
        "bend_radius": bend["radius_nominal"],
        "bend_band": bend["radius"],
        "bend_deg": bend["angle"],
        "foot_len": bend["foot_len_nominal"],
        "kink_radius": kink["radius_nominal"],
        "kink_band": kink["radius"],
        "kink_deg": kink["angle"],
        "flat": flat["length_nominal"],
        "flat_band": flat["length"],
    }


def _forming(
    g: dict[str, Any], plan: dict[str, Any], shank_dia: float
) -> dict[str, Any]:
    """The #2 shank's formed radius at the corners, the bends' angles on the
    shank, and where the bench ops mark and set the straight strip."""
    p = plan["parameters"]
    modulus, yield_min = p["strip_modulus_mpa"], p["strip_yield_min_mpa"]
    ri = shank_dia / 2
    band = (
        max(g["bend_band"][0], g["kink_band"][0]),
        min(g["bend_band"][1], g["kink_band"][1]),
    )
    formed = {t: _formed_radius(ri, yield_min, modulus, t) for t in g["thick_band"]}
    nominal = _formed_radius(ri, yield_min, modulus, g["thick"])
    low, high = min(formed.values()), max(formed.values())
    if low < band[0] or high > band[1]:
        raise ValueError(
            f"the #2 shank forms R{low:.3f}-R{high:.3f}, outside the bends' "
            f"R{band[0]:.3f}-R{band[1]:.3f}"
        )
    _agree(plan, "formed_radius_min_mm", low, 0.001)
    _agree(plan, "formed_radius_max_mm", high, 0.001)
    _agree(plan, "formed_radius_nominal_mm", nominal, 0.001)
    # The yield is a minimum (ASTM A693): the radius grows with it, so the
    # thinnest strip reaches the band's top first.
    limit = _yield_limit(ri, modulus, g["thick_band"][0], band[1])
    _agree(plan, "strip_yield_limit_mpa", limit, 1.0)
    # Each bend's angle on the shank: its mid-surface keeps its length.
    half = g["thick"] / 2
    ratio = (nominal + half) / (ri + half)
    _agree(plan, "bend_on_shank_deg", g["bend_deg"] * ratio, 0.05)
    _agree(plan, "kink_on_shank_deg", g["kink_deg"] * ratio, 0.05)
    _agree(plan, "kink_protractor_deg", 90.0 - g["kink_deg"] * ratio, 0.05)
    # The bench vise: the strip against the fixed jaw, the shank between it
    # and the moving jaw with its axis process.shank_below_jaw_mm under the
    # jaw tops. The strip is pinched at the shank's equator (each bend's
    # tangent on the clamped side) and wraps over the shank's top, so the
    # kink's arc on the shank (tip end clamped) ends at the jaw tops.
    depth = p["shank_below_jaw_mm"]
    _agree(plan, "shank_top_over_jaw_mm", ri - depth)
    if not 0 < depth < ri:
        raise ValueError(
            "process.shank_below_jaw_mm: the shank's axis must lie under the jaw tops, its top above"
        )
    kink_arc = (nominal + half) * math.radians(g["kink_deg"])
    if not math.isclose(depth, kink_arc, abs_tol=PLAN_TOL_MM):
        raise ValueError(
            "process.shank_below_jaw_mm is not the kink's mid-surface arc on the "
            f"shank, {kink_arc:.3f}: the kink's start mark would not stand at the jaw tops"
        )
    # Marks on the straight strip from the pad's end (mid-surface lengths):
    # the tip at the developed length; the kink's start mark (the tip end
    # clamped) the flat and the kink's arc on the shank short of the tip; the
    # foot's mark (the blade clamped, the foot bent over) the shank's depth
    # short of the pinch, which is the foot bend's arc on the shank past its
    # foot-side tangent (the hole's station plus the hole-to-tangent length).
    # The blade between takes the arcs' difference from the drawing's radius.
    foot = g["hole_x"] + g["foot_len"]
    _agree(plan, "foot_length_mm", foot)
    foot_arc = (nominal + half) * math.radians(g["bend_deg"])
    kink_mark = g["developed"] - g["flat"] - kink_arc
    _agree(plan, "tip_from_end_in", g["developed"] / IN, PLAN_TOL_IN)
    _agree(plan, "kink_mark_from_end_in", kink_mark / IN, PLAN_TOL_IN)
    _agree(plan, "foot_mark_from_end_in", (foot + foot_arc - depth) / IN, PLAN_TOL_IN)
    flat_half = (g["flat_band"][1] - g["flat_band"][0]) / 2
    _agree_inward(
        plan, "tip_from_end", (g["developed"] - flat_half, g["developed"] + flat_half)
    )
    return {"formed": [low, high], "nominal": nominal, "yield_limit": limit}


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]

    d30 = _shop_tool(plan, shop, "drill-30")["diameter_mm"]
    # .1285 in is 3.2639 mm; the drawing rounds its band's low edge to 3.264.
    if not g["hole_dia"][0] - 1e-3 <= d30 <= g["hole_dia"][1]:
        raise ValueError(f"#30 Ø{d30} is outside the hole's band {g['hole_dia']}")
    if not math.isclose(_cut(plan, "hole drill", "cutter_dia_mm"), d30, abs_tol=1e-3):
        raise ValueError("'hole drill' cutter_dia_mm is not the #30's")
    _agree(plan, "drill_30_dia_mm", d30, 1e-4)
    shank = _shop_tool(plan, shop, "mandrel")["diameter_mm"]
    _agree(plan, "shank_dia_mm", shank, 1e-4)
    forming = _forming(g, plan, shank)

    # The strip as bought: the export's thickness band, miked on arrival.
    _agree(plan, "strip_thickness_min_mm", g["thick_band"][0], 1e-4)
    _agree(plan, "strip_thickness_max_mm", g["thick_band"][1], 1e-4)

    # Setup 3's readings over the #30's shank in the hole: each printed
    # station from the hole's axis plus the shank's radius.
    half30 = d30 / 2
    _agree_inward(plan, "end_reading", tuple(x + half30 for x in g["hole_x_band"]))
    _agree_inward(plan, "edge_reading", tuple(z + half30 for z in g["hole_z_band"]))
    _agree_inward(plan, "wing_reading", tuple(w + half30 for w in g["wing_band"]))
    # The hole's go and no-go pins: its band, inward to the pins' .001 steps.
    _agree_inward(plan, "hole_pin", tuple(g["hole_dia"]))
    # Setup 3's rough marks, each a nominal edge's station from the hole's
    # centre plus MARK_OUTSIDE_IN: the pad's end, the pad's forward edge,
    # the aft edge (the pad's width less the forward edge's station), the
    # wing's face (toward the tip), the strip's forward edge (forward of the
    # hole: the strip's width less the aft edge's station) and the tip (the
    # developed length less the hole's station from the pad's end).
    aft = g["pad_width"] - g["hole_z"]
    for key, station in (
        ("mark_end", g["hole_x"]),
        ("mark_edge", g["hole_z"]),
        ("mark_aft", aft),
        ("mark_wing", g["wing"]),
        ("mark_strip_edge", g["strip_width"] - aft),
        ("mark_tip", g["developed"] - g["hole_x"]),
    ):
        _agree(plan, f"{key}_from_hole_in", station / IN + MARK_OUTSIDE_IN, PLAN_TOL_IN)

    # The piece: the hole's station leaves the pad's end and both pad edges
    # a filing allowance; the piece covers the developed strip past the tip.
    piece_l, piece_w = p["blank_length_in"] * IN, p["blank_width_in"] * IN
    at_x, at_y = p["hole_from_piece_end_mm"], p["hole_from_piece_edge_mm"]
    if at_x <= g["hole_x_band"][1]:
        raise ValueError("process.hole_from_piece_end_mm leaves no pad end to file")
    if at_x - g["hole_x"] + g["developed"] > piece_l:
        raise ValueError(
            "the piece is shorter than the pad end and the developed strip"
        )
    pad_half = g["pad_width_band"][1] / 2
    if not pad_half < at_y < piece_w - pad_half:
        raise ValueError("process.hole_from_piece_edge_mm leaves no pad edge to file")
    if not math.isclose(at_y, piece_w / 2, abs_tol=PLAN_TOL_MM):
        raise ValueError(
            "process.hole_from_piece_edge_mm is not across the piece's middle"
        )

    # Heights over Z0 (the plate's bare top): the tape stack, the strip, a
    # second stack and the cover, each at its limit.
    stack_max = p["tape_stack_max_mm"]
    cover_min, cover_max = p["cover_height_min_in"] * IN, p["cover_height_max_in"] * IN
    _agree(plan, "cover_height_min_mm", cover_min, 1e-4)
    _agree(plan, "cover_height_max_mm", cover_max, 1e-4)
    strip_top_max = stack_max + g["thick_band"][1]
    cover_top_min = p["tape_stack_min_mm"] * 2 + g["thick_band"][0] + cover_min
    cover_top_max = 2 * stack_max + g["thick_band"][1] + cover_max
    _agree(plan, "cover_top_max_mm", cover_top_max)
    _agree(plan, "cover_top_min_mm", cover_top_min)
    jaw_top = (
        p["vise_jaw_height_mm"] - p["parallel_height_mm"] - p["plate_thickness_mm"]
    )
    _agree(plan, "jaw_top_over_plate_mm", jaw_top)
    if p["cover_width_mm"] >= piece_w:
        raise ValueError(
            "the cover is as wide as the piece: it would rock on the strip's edge"
        )

    tip = -(_point(d30) + p["hole_drill_past_mm"])
    _agree(plan, "hole_tip_z_mm", tip)
    if -tip > p["spoil_cut_max_mm"]:
        raise ValueError(
            "the drill's tip goes deeper into the spoil plate than spoil_cut_max_mm"
        )
    depth = cover_top_max - tip
    _agree(plan, "hole_depth_mm", depth)
    peck = p["hole_peck_mm"]
    op = _op_with_cut(plan, "hole drill")[0]
    if op["peck"] != {"step_mm": "{{process.hole_peck_mm}}", "retract": "full"}:
        raise ValueError(
            "'hole drill' peck is not process.hole_peck_mm with full retract"
        )
    if peck > d30:
        raise ValueError("process.hole_peck_mm is over one #30 diameter")
    clear = max(jaw_top, cover_top_max) + CLEAR_MM
    if p["drill_30_projection_min_mm"] < clear - tip:
        raise ValueError(
            "drill_30_projection_min_mm: the chuck would reach the cover or the jaw tops"
        )
    if p["drill_30_projection_min_mm"] >= p["drill_30_oal_mm"]:
        raise ValueError("drill_30_projection_min_mm: longer than the drill")
    if depth >= p["drill_30_flute_mm"]:
        raise ValueError("the hole is deeper than the #30's flutes")

    rpm, feed = _speed(plan, shop, "hole drill")
    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # The piece's place on the plate: its pad end process.piece_x_mm from the
    # plate's left end, its edge toward the fixed jaw process.piece_y_mm off
    # the jaw.
    x0, y0 = p["piece_x_mm"], p["piece_y_mm"]
    hole = [_r(x0 + at_x), _r(-(y0 + at_y))]
    _agree(plan, "hole_x_mm", hole[0])
    _agree(plan, "hole_y_mm", hole[1])
    _agree(plan, "piece_end_x_mm", x0 + piece_l)
    _agree(plan, "blank_area_mm2", piece_l * piece_w, 0.01)
    if not at_x + d30 < p["cover_length_mm"] <= piece_l:
        raise ValueError(
            "the cover, its left end flush with the piece's, does not cover the hole"
        )
    # Frame (model point -> axes · (p - origin)): work X = model -X, work Y =
    # model +Z, work Z = model +Y (X = Y x Z), the hole's model point on the
    # strip's top face landing at the work hole over the strip's top.
    axes = [[-1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]]
    at = features["features"]["hole"]["at"]
    origin = [
        at[0] + hole[0],
        at[1] - strip_top_max,
        at[2] - hole[1],
    ]
    frame = {"origin": origin, "axes": axes}
    plate_w = p["plate_width_mm"]
    stock = ((0.0, p["plate_length_mm"]), (-plate_w, 0.0), (0.0, cover_top_max))

    jobs = [
        {
            "tool": "drill-30",
            "dia": d30,
            "shape": "drill",
            "tip_angle": DRILL_POINT_DEG,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
            "label": "hole drill",
            "ops": [
                [
                    "hole_drill",
                    "peck the #30 through the cover and the strip",
                    _pecked(hole, cover_top_max, tip, peck, clear),
                ]
            ],
        }
    ]

    # Keep-outs: the jaws across the plate (to their tops).
    jaw_x = (0.0, p["plate_length_mm"])
    boxes = [
        _box("fixed jaw", jaw_x, (0.0, JAW_DEPTH_MM), jaw_top),
        _box("moving jaw", jaw_x, (-plate_w - JAW_DEPTH_MM, -plate_w), jaw_top),
    ]
    name = PROGRAMS[0][0]
    expect: list[list[Any]] = [
        [
            name,
            "tool_changes",
            {
                "z_top": cover_top_max,
                "tools": [numbers["drill-30"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[rpm]]}],
        [name, "pauses", {"z_top": cover_top_max, "count": 0}],
        [name, "depth", {"z_min": _r(tip)}],
    ]
    for check, kwargs in (
        ["holes", {"centres": [hole], "z_bottom": _r(tip)}],
        ["rapids_clear", {"z_top": cover_top_max, "open_holes": [hole]}],
        ["vertical_below_top", {"z_top": cover_top_max}],
        ["air_feed", {"z_top": cover_top_max}],
        ["keep_out", {"radius": d30 / 2, "boxes": boxes}],
    ):
        expect.append([f"{name}@0", check, kwargs])

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": {"hole": frame},
        "stock": stock,
        "names": names,
        "numbers": numbers,
        "jobs": jobs,
        "manual": {},
        "expect": expect,
        "forming": forming,
    }


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    return [(program, check, kwargs) for program, check, kwargs in ctx["expect"]]


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job;
    returns {"ops": {operation key: operation}}."""
    doc = rt.document()
    frame = ctx["frames"]["hole"]
    model = rt.import_step(doc, "Spring", ctx["step"], frame["origin"], frame["axes"])
    ops: dict[str, Any] = {}
    for section in ctx["jobs"]:
        target = rt.job(doc, section["label"], [model], ctx["stock"])
        tc = rt.tool_controller(
            doc,
            ctx["names"][section["tool"]],
            ctx["numbers"][section["tool"]],
            section["shape"],
            section["dia"],
            section["rpm"],
            section["feed"],
            section["plunge"],
            tip_angle=section.get("tip_angle"),
        )
        for key, label, lines in section["ops"]:
            ops[key] = rt.custom(target, tc, label, lines)
    ops.update(ctx["manual"])
    rt.generate(doc)
    return {"ops": ops}


# The as-machined report (``cad/scripts/_as_machined.py``) cannot compare this
# program with the part: it drills a flat strip, and the STEP is the formed,
# installed spring.
AS_MACHINED_NOT_COVERED = (
    "PS01 drills the flat .015 strip piece on the spoil plate; MHA-DT-24's STEP is"
    " the spring formed and installed (two bends at the bench afterwards), so no"
    " blank-and-moves comparison with it exists"
)
