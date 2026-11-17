"""FreeCAD CAM recipe for MHA-CH-13, the rocker strap.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. No part dimension is
typed here: the thickness, hub hole and outline come from the manifest (and
its STEP, which FreeCAD profiles); the blank, the part's place in it, the
face stock split, depth levels, tab and clamp stations from ``plan.toml``
``[parameters]`` and ``milling_cuts``; cutter diameters, speeds and feeds
from ``shop.toml``. Typed here, because neither record carries them: the #2
centre drill's catalogue geometry (it sets the spot depth), the approach
clearance, the blank's placement allowance before the probe, the face
overhang past the blank's edges, the face-1 least skin, the safe and
clearance heights, the flip's lift, the probe feeds and the share of a
printed band the posted outline may use.

Route (owner, 2026-11-17; process text in the manifest's notes): the 12 x
1-1/2 x 1/8 in 1018 CF flat lies on a shop-made 6061 sub-plate gripped in the
vise, pushed against the plate's fixed fence by four low-profile edge clamps
that stand below the faced top. Work frame (G54), one for every file: X0 the
blank's left end (set by the touch probe in RS03; before it, the blank sits at
the plate's X0 mark by eye), Y0 the fence face with the blank at -Y, Z0 the
faced plate top, so Z is thickness. The strap lies with its top arc (concave
side) toward the fence and its bottom arc toward the clamps, its hub at the
plan's ``hub_x_mm``, ``-hub_y_mm``.

- RS01: rough face 1 at a fixed Z, stop for the flip (end for end, the same
  edge on the fence), rough face 2. Release, turn over (face 1 up), reseat.
- RS02: finish face 1. Release, turn over (face 2 up) and reseat.
- RS03: finish face 2 to the finished thickness, probe X0 on the blank's left
  end, spot, drill and ream the hub hole (into the plate's relief hole), then
  mill the outline with the 1/8 in end mill in three cuts: rough at the
  plan's finish stock outside the part down to the tab height, through the
  rest of the thickness into the plate skipping the clamp-side tabs, finish at
  the part edge over the full depth lifting over the tabs. The tabs are filed
  off by hand.

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws), plunges
beside the stock at the cutting feed, plunges into metal (the outline levels)
at the plan's plunge feed, real G0 above the stock. The outline runs
anticlockwise round the part: conventional with a clockwise spindle. The
reamer feeds in and out (a rapid retract can score the press-fit bore).
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ch_rocker_strap"
COMMENT = "MHA-CH-13 rocker strap"
# Programs in order, each listing its operation keys. A program whose keys are
# grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section: the flip stop, the probe), joined at M6 tool changes and M0 stops;
# it starts with its first section's tool loaded.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("RS01_rough_faces", (("face_1_rough",), ("flip",), ("face_2_rough",))),
    ("RS02_finish_face_1", ("face_1_finish",)),
    (
        "RS03_finish_face_2_hub_outline",
        (
            ("face_2_finish",),
            ("probe_x0",),
            ("spot",),
            ("drill",),
            ("ream",),
            ("outline_rough", "outline_through", "outline_finish"),
        ),
    ),
)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (tools off the mill, the saw and the files, are not).
CAM_TOOLS = ("em-half", "em-eighth", "probe", "spot", "hub-drill", "hub-reamer")
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included: the shop record names
# the tool, not its geometry.
CENTRE_DRILL = {
    "body_mm": 3 / 16 * IN,
    "pilot_mm": 5 / 64 * IN,
    "pilot_length_mm": 5 / 64 * IN,
    "point_deg": 60.0,
}
# Face passes start and finish with the cutter this far clear of the blank's
# ends, so every plunge and stepover link is in the air beside it.
APPROACH_MM = 2.54
# Until the probe sets X0 (RS03), the blank's left end sits at the plate's X0
# mark by eye; the faces run this much farther past each end, and the probe
# searches this far either side of it.
END_ALLOWANCE_MM = 10.0
# Faces reach at least this far past the blank's fence and clamp edges, over
# the fence and clamps, which stand below the faced top (the context checks).
FACE_OVERHANG_MM = 0.5
# Face 1 roughs at a fixed Z; the thinnest blank the plan allows must still
# lose at least this skin (.004 in) there, so the mill-finish face comes off.
FACE_SKIN_MIN_MM = 0.1016
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it, so only this much of each plunge is above the
# stock. FreeCAD measures each G83 peck from the R plane.
SAFE_MM = 1.0
# Moves between holes, outline passes and the probe's moves run this far above
# the stock top.
CLEAR_MM = 5.0
# The flip stop lifts the 1/2 in end mill this far above the plate, room to
# release the clamps and turn the blank over beneath it.
FLIP_LIFT_MM = 50.0
# Probe feeds (mm/min): the seek, and the slow second touch the zero is set
# at, within the TP05 listing's 50-200 mm/min probing feed.
PROBE_SEEK_FEED = 150.0
PROBE_TOUCH_FEED = 50.0
# The posted outline's cutter centre may stray from its offset by this share
# of the tightest printed band locating that edge; the rest is the machine's.
BAND_FRACTION = 0.1


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


def _cut(plan: dict[str, Any], name: str, key: str) -> float:
    """Field ``key`` of the plan's milling cut ``name``: a number, or a
    ``{{process.<parameter>}}`` binding read from the plan's [parameters]. A
    ``{{cad.…}}`` binding is the prechips adapter's, which this recipe cannot
    evaluate, so it is refused."""
    value = _op_with_cut(plan, name)[1][key]
    if isinstance(value, str):
        match = re.fullmatch(r"\{\{process\.(\w+)\}\}", value.strip())
        if not match:
            raise ValueError(
                f"'{name}' {key} = {value!r}: only numbers and {{{{process.…}}}} bindings are read"
            )
        value = plan["parameters"][match.group(1)]
    return float(value)


def _setting(
    plan: dict[str, Any], shop: dict[str, Any], cut: str
) -> tuple[float, float, int]:
    """(rpm, mm/min, flutes) of the shop cutting setting the operation holding
    ``cut`` names: feed = chip load × flutes × rpm."""
    op, _cut_record = _op_with_cut(plan, cut)
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    return (
        rpm,
        record["chip_load_mm_per_tooth"] * record["flutes"] * rpm,
        record["flutes"],
    )


def _cut_feed(plan: dict[str, Any], name: str) -> tuple[float, float]:
    """(rpm, mm/min) of the plan's drill or plunge cut ``name``, which carries
    both; its rpm must be its operation's."""
    op_rpm = float(_op_with_cut(plan, name)[0]["rpm"])
    rpm = _cut(plan, name, "rpm")
    if rpm != op_rpm:
        raise ValueError(f"'{name}' at {rpm:g} rpm, its operation at {op_rpm:g}")
    return rpm, _cut(plan, name, "feed_mm_min")


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


def _levels(top: float, bottom: float, max_step: float) -> tuple[float, list[float]]:
    """FreeCAD's step-down (equal steps no deeper than ``max_step``, rounded up
    at 1 µm so the last lands on ``bottom`` instead of adding a sliver level)
    and the levels it cuts at."""
    n = math.ceil((top - bottom) / max_step - 1e-9)
    step = math.ceil((top - bottom) / n * 1e6) / 1e6
    return step, [top - step * (k + 1) for k in range(n - 1)] + [bottom]


def _face_layout(width: float, dia: float, woc: float, name: str) -> dict[str, Any]:
    """Zigzag face passes over a blank ``width`` wide at Y -width..0, each pass
    taking ``woc`` (the plan cut's radial width) of stock no earlier pass cut,
    the first included.

    FreeCAD's MillFace lays its lines a whole percentage of the cutter apart
    from the bottom of the face's box, inset a cutter radius, and cuts the top
    line first: with the box flush with the fence edge that first pass runs
    nearly full width. So the box's top sits a cutter diameter less one step
    above Y0 (the cutter overhangs the fence, below the faced top), putting the
    first line one step into the blank, and its bottom ``passes`` steps below
    Y0, reaching at least FACE_OVERHANG_MM past the clamp edge. The plan must
    declare the engagement this posts."""
    reach = width + FACE_OVERHANG_MM
    passes = math.ceil(reach / woc - 1e-9)
    percent = math.ceil(100 * reach / (passes * dia) - 1e-9)
    step = percent * dia / 100
    if not math.isclose(step, woc, abs_tol=1e-3):
        raise ValueError(
            f"'{name}' radial_woc_mm {woc:.3f}: {passes} passes post {step:.3f} mm engagements "
            f"(StepOver {percent}% of the {dia:.3f} mm cutter); declare that width"
        )
    return {"passes": passes, "woc": step, "y": (-passes * step, dia - step)}


def _band(feature: dict[str, Any], *names: str) -> float:
    """BAND_FRACTION of the tightest printed band among ``names``."""
    return BAND_FRACTION * min(feature[n][1] - feature[n][0] for n in names)


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    f = features["features"]
    p = plan["parameters"]
    z_under = f["broad_face_neg_z"]["plane"]["value"]
    thick = f["broad_face_pos_z"]["plane"]["value"] - z_under
    band = f["broad_face_pos_z"]["thickness"]
    if not band[0] <= thick <= band[1]:
        raise ValueError(
            f"model thickness {thick:.4f} is outside the printed band {band}"
        )
    blank = (
        p["blank_length_in"] * IN,
        p["blank_width_in"] * IN,
        p["blank_thickness_in"] * IN,
    )
    bl, bw, bt = blank
    b_min, b_max = p["blank_thickness_min_in"] * IN, p["blank_thickness_max_in"] * IN

    # Faces at fixed Z (Z is thickness): face 1 roughs off half the nominal
    # allowance less the finish stock, face 2 roughs to two finish stocks over
    # the finished thickness, then each face takes one finish stock (RS02,
    # RS03), so a nominal blank loses the same from each face. The plan's face
    # cuts take their depths from the same arithmetic (its prechips adapter,
    # cad.face_*_doc_mm); here the thinnest blank must still clean up.
    stock = p["face_finish_stock_mm"]
    z1 = bt - ((bt - thick) / 2 - stock)
    z2, z3 = thick + 2 * stock, thick + stock
    if b_min - z1 < FACE_SKIN_MIN_MM - 1e-6:
        raise ValueError(
            f"process.blank_thickness_min_in: face 1 roughs at Z {z1:.3f}, so a {b_min:.3f} mm blank "
            f"loses only {b_min - z1:.3f} mm there (< {FACE_SKIN_MIN_MM} mm): it may not clean up"
        )
    # The faces overhang the fence and the clamps: both must stand below the
    # lowest faced top.
    for name in ("fence_height_mm", "clamp_height_mm"):
        if p[name] >= thick:
            raise ValueError(
                f"process.{name} {p[name]:.3f} is not below the faced top {thick:.3f}: the face overhang would cut it"
            )

    hub = f["hub_hole"]
    hub_x, hub_y = p["hub_x_mm"], -p["hub_y_mm"]
    # Model -> work frame: a translation (the hub at its plan place, the
    # underside on the plate).
    origin = [hub["at"][0] - hub_x, hub["at"][1] - hub_y, z_under]

    def xy(point):
        return [point[0] - origin[0], point[1] - origin[1]]

    top, bottom = f["top_arc"], f["bottom_arc"]
    land = {s: f[f"tip_land_{s}_x"] for s in ("neg", "pos")}
    end = {s: f[f"end_face_{s}_x"] for s in ("neg", "pos")}
    if (
        top["ends"][0][0] > top["ends"][1][0]
        or bottom["ends"][0][0] > bottom["ends"][1][0]
    ):
        raise ValueError("top_arc/bottom_arc ends are not listed -X first")
    # The outline anticlockwise: bottom arc -X to +X, +X end face, +X tip land,
    # top arc +X to -X, -X tip land, -X end face.
    elements = [
        {
            "name": "bottom_arc",
            "start": xy(bottom["ends"][0]),
            "end": xy(bottom["ends"][1]),
            "centre": xy(bottom["arc_centre"]),
            "tol": _band(bottom, "height_below_pivot", "radius"),
        },
        {
            "name": "end_face_pos_x",
            "start": xy(end["pos"]["foot"]),
            "end": xy(end["pos"]["corner"]),
            "tol": _band(end["pos"], "foot_station"),
        },
        {
            "name": "tip_land_pos_x",
            "start": xy(land["pos"]["corner"]),
            "end": xy(land["pos"]["inner_end"]),
            "tol": _band(land["pos"], "land_length", "corner_station"),
        },
        {
            "name": "top_arc",
            "start": xy(top["ends"][1]),
            "end": xy(top["ends"][0]),
            "centre": xy(top["arc_centre"]),
            "tol": _band(top, "height_above_pivot", "radius"),
        },
        {
            "name": "tip_land_neg_x",
            "start": xy(land["neg"]["inner_end"]),
            "end": xy(land["neg"]["corner"]),
            "tol": _band(land["neg"], "land_length", "corner_station"),
        },
        {
            "name": "end_face_neg_x",
            "start": xy(end["neg"]["corner"]),
            "end": xy(end["neg"]["foot"]),
            "tol": _band(end["neg"], "foot_station"),
        },
    ]
    for a, b in zip(elements, elements[1:] + elements[:1]):
        if math.dist(a["end"], b["start"]) > 1e-3:
            raise ValueError(
                f"outline not closed: {a['name']} ends {a['end']}, {b['name']} starts {b['start']}"
            )

    em_half = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    em_eighth = _shop_tool(plan, shop, "em-eighth")["diameter_mm"]
    r = em_eighth / 2
    finish_stock = p["outline_finish_stock_mm"]
    if not math.isclose(
        _cut(plan, "outline finish", "radial_woc_mm"), finish_stock, abs_tol=1e-6
    ):
        raise ValueError(
            "'outline finish' radial_woc_mm is not process.outline_finish_stock_mm"
        )
    # The rough and through slot reaches 2r + finish stock outside the part:
    # it must stay inside the blank (its strips keep the fence and clamp edges).
    samples = [pt for e in elements for pt in _outline_samples(e)]
    reach = em_eighth + finish_stock
    margins = {
        "fence": -max(y for _x, y in samples) - reach,
        "clamps": min(y for _x, y in samples) + bw - reach,
        "left end": min(x for x, _y in samples) - reach,
        "right end": bl - max(x for x, _y in samples) - reach,
    }
    broken = {k: round(v, 3) for k, v in margins.items() if v <= 0}
    if broken:
        raise ValueError(f"the outline slot breaks out of the blank at {broken} mm")

    # Tabs: one at each clamp station (clamp_1_x_mm, clamp_2_x_mm, ...), on the
    # clamp side (bottom arc): a cutter-centre point on the through and on the
    # finish path, both on the arc's normal through the station's edge point.
    stations = [
        p[f"clamp_{k}_x_mm"]
        for k in range(
            1, 1 + sum(1 for key in p if re.fullmatch(r"clamp_\d+_x_mm", key))
        )
    ]
    if not stations:
        raise ValueError("the plan declares no clamp_<n>_x_mm stations")
    centre, radius = xy(bottom["arc_centre"]), bottom["radius_nominal"]
    foot = [xy(bottom["ends"][0])[0], xy(bottom["ends"][1])[0]]
    tab_top, through = p["tab_height_mm"], -p["outline_breakthrough_mm"]
    width, clear = p["tab_width_mm"], p["tab_width_mm"] / 2 + r
    for x in stations:
        if not foot[0] + clear <= x <= foot[1] - clear:
            raise ValueError(
                f"tab at X {x:.3f} is not on the bottom arc between its feet {foot}"
            )
    if not through < tab_top < thick:
        raise ValueError(
            f"tab height {tab_top:.3f} is not between the outline bottom {through:.3f} and the top {thick:.3f}"
        )

    def tab_points(offset):
        points = []
        for x in stations:
            edge = (x, centre[1] - math.sqrt(radius**2 - (x - centre[0]) ** 2))
            scale = (radius + offset) / radius
            points.append(
                [
                    centre[0] + (edge[0] - centre[0]) * scale,
                    centre[1] + (edge[1] - centre[1]) * scale,
                ]
            )
        return points

    outline_rpm, outline_feed, outline_flutes = _setting(plan, shop, "outline rough")
    for name in ("outline through", "outline finish"):
        if _setting(plan, shop, name) != (outline_rpm, outline_feed, outline_flutes):
            raise ValueError(
                f"'{name}' runs at another setting than 'outline rough': one job, one speed"
            )
    plunge_rpm, outline_plunge = _cut_feed(plan, "outline plunge")
    if plunge_rpm != outline_rpm:
        raise ValueError(
            f"'outline plunge' at {plunge_rpm:g} rpm, the outline at {outline_rpm:g}"
        )
    rough_step, rough_levels = _levels(
        thick, tab_top, _cut(plan, "outline rough", "axial_doc_mm")
    )
    through_step, through_levels = _levels(
        tab_top, through, _cut(plan, "outline through", "axial_doc_mm")
    )
    finish_step, finish_levels = _levels(
        thick, through, _cut(plan, "outline finish", "axial_doc_mm")
    )

    # Hub hole: spot (#2 centre drill), drill and ream through into the plate's
    # relief hole.
    if p["spot_point_deg"] != CENTRE_DRILL["point_deg"]:
        raise ValueError(
            f"spot_point_deg {p['spot_point_deg']} is not the #2 centre drill's {CENTRE_DRILL['point_deg']}"
        )
    spot_dia = p["spot_dia_mm"]
    if not CENTRE_DRILL["pilot_mm"] < spot_dia <= CENTRE_DRILL["body_mm"]:
        raise ValueError(
            f"spot_dia_mm {spot_dia:.3f} is not on the #2 centre drill's countersink"
        )
    spot_depth = CENTRE_DRILL["pilot_length_mm"] + (
        spot_dia - CENTRE_DRILL["pilot_mm"]
    ) / 2 / math.tan(math.radians(CENTRE_DRILL["point_deg"] / 2))
    drill_dia = _shop_tool(plan, shop, "hub-drill")["diameter_mm"]
    reamer_dia = _shop_tool(plan, shop, "hub-reamer")["diameter_mm"]
    if not hub["dia"][0] <= reamer_dia <= hub["dia"][1]:
        raise ValueError(
            f"reamer Ø{reamer_dia} is outside the hub hole's band {hub['dia']}"
        )
    if not drill_dia < reamer_dia < p["hub_relief_dia_mm"]:
        raise ValueError(
            f"drill Ø{drill_dia}, reamer Ø{reamer_dia} and the plate's relief Ø{p['hub_relief_dia_mm']} are not in that order"
        )
    drill_tip, ream_tip = p["drill_tip_z_mm"], p["ream_tip_z_mm"]
    if drill_tip > -drill_dia / 2 / math.tan(math.radians(59)) or ream_tip >= 0:
        raise ValueError(
            f"drill tip Z {drill_tip:.3f} / reamer tip Z {ream_tip:.3f}: the full diameter does not pass the strap's underside"
        )
    spot_rpm, spot_feed = _cut_feed(plan, "hub spot")
    drill_rpm, drill_feed = _cut_feed(plan, "hub drill")
    ream_rpm, ream_feed = _cut_feed(plan, "hub ream")
    face_rpm, face_feed, face_flutes = _setting(plan, shop, "face rough")
    if _setting(plan, shop, "face finish") != (face_rpm, face_feed, face_flutes):
        raise ValueError("'face finish' runs at another setting than 'face rough'")
    faces = {
        key: _face_layout(bw, em_half, _cut(plan, name, "radial_woc_mm"), name)
        for key, name in (("rough", "face rough"), ("finish", "face finish"))
    }

    names = {t["id"]: t["name"] for t in plan["tools"]}
    numbers = {
        t["id"]: n
        for n, t in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # The flip: the end mill lifted, the spindle stopped, the blank turned
    # over end for end by hand (the same edge on the fence); face 2's section
    # then restarts the spindle. The instruction is a CNCjs %msg line, which
    # CNCjs shows when the M0 pauses it.
    flip_gcode = [
        f"G0 Z{FLIP_LIFT_MM:.3f}",
        "M5",
        "%msg PAUSE: SPINDLE STOPPED. RELEASE THE EDGE CLAMPS, TURN THE BLANK OVER END FOR END, SAME EDGE ON THE FENCE,"
        " LEFT END AT THE X0 MARK, PLATE WIPED CLEAN, RE-CLAMP, THEN CYCLE START",
        "M0",
    ]
    # X0 by the touch probe on the blank's left end at mid-thickness: from
    # beside it, seek it in +X, back off, touch again slowly and set X0 at the
    # end. The probe descends by G38.3, which stops on a blank that is not
    # where expected; the G38.2 after it then alarms on the tripped probe
    # (FluidNC 3.7.8 MotionControl.cpp mc_probe_cycle, ProbeFailInitial). The
    # ball's bottom must stay above the plate there.
    ball = p["probe_ball_radius_mm"]
    if ball >= thick / 2:
        raise ValueError(
            f"probe ball radius {ball} would touch the plate at mid-thickness {thick / 2:.3f}"
        )
    probe_clear, probe_x0 = thick + CLEAR_MM, -ball
    x_from, x_to = (
        -ball - END_ALLOWANCE_MM - APPROACH_MM,
        END_ALLOWANCE_MM + APPROACH_MM,
    )
    probe_gcode = [
        f"G0 Z{probe_clear:.3f}",
        f"G0 X{x_from:.3f} Y{-bw / 2:.3f}",
        f"G38.3 Z{thick / 2:.3f} F{PROBE_SEEK_FEED:g}",
        f"G38.2 X{x_to:.3f} F{PROBE_SEEK_FEED:g}",
        f"G38.4 X{x_from:.3f} F{PROBE_SEEK_FEED:g}",
        f"G38.2 X{x_to:.3f} F{PROBE_TOUCH_FEED:g}",
        f"G10 L20 P1 X{probe_x0:.3f}",
        f"G38.4 X{x_from:.3f} F{PROBE_SEEK_FEED:g}",
        f"G0 Z{probe_clear:.3f}",
    ]
    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "model": {"origin": origin, "axes": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        "thick": thick,
        "blank": list(blank),
        "blank_max": b_max,
        "hub": [hub_x, hub_y],
        "hub_dia": hub["nominal_dia"],
        "names": names,
        "numbers": numbers,
        "tool_changes": [
            numbers[t]
            for t in ("probe", "spot", "hub-drill", "hub-reamer", "em-eighth")
        ],
        "face": {
            "rpm": face_rpm,
            "feed": face_feed,
            "dia": em_half,
            "flutes": face_flutes,
            "layouts": faces,
            # (operation key, plan cut kind, faced Z, stock top before it)
            "passes": [
                ["face_1_rough", "rough", z1, b_max],
                ["face_2_rough", "rough", z2, z1],
                ["face_1_finish", "finish", z3, z2],
                ["face_2_finish", "finish", thick, z3],
            ],
        },
        "outline": {
            "rpm": outline_rpm,
            "feed": outline_feed,
            "plunge": outline_plunge,
            "dia": em_eighth,
            "elements": elements,
            "stock": finish_stock,
            "start": xy(top["edge_on_axis"]),
            "rough": {"step": rough_step, "levels": rough_levels},
            "through": {"step": through_step, "levels": through_levels},
            "finish": {"step": finish_step, "levels": finish_levels},
            "bottom": through,
        },
        "tabs": {
            "top": tab_top,
            "width": width,
            "clear": clear,
            "through": tab_points(r + finish_stock),
            "finish": tab_points(r),
        },
        "spot": {
            "rpm": spot_rpm,
            "feed": spot_feed,
            "dia": CENTRE_DRILL["body_mm"],
            "z": thick - spot_depth,
        },
        "drill": {
            "rpm": drill_rpm,
            "feed": drill_feed,
            "dia": drill_dia,
            "z": drill_tip,
        },
        "ream": {"rpm": ream_rpm, "feed": ream_feed, "dia": reamer_dia, "z": ream_tip},
        "flip": {
            "tool": numbers["em-half"],
            "label": names["em-half"],
            "setting": "SPINDLE STAYS OFF",
            "gcode": flip_gcode,
        },
        "probe": {
            "tool": numbers["probe"],
            "label": names["probe"],
            "setting": "SPINDLE OFF - PROBE IN",
            "gcode": probe_gcode,
            "x0": probe_x0,
        },
    }


def _outline_samples(
    element: dict[str, Any], step: float = 0.5
) -> list[tuple[float, float]]:
    """Points along an outline element (a line, or the minor arc about its centre)."""
    s, e, c = element["start"], element["end"], element.get("centre")
    if c is None:
        n = max(1, math.ceil(math.dist(s, e) / step))
        return [
            (s[0] + (e[0] - s[0]) * k / n, s[1] + (e[1] - s[1]) * k / n)
            for k in range(n + 1)
        ]
    radius = math.dist(c, s)
    begin = math.atan2(s[1] - c[1], s[0] - c[0])
    sweep = (math.atan2(e[1] - c[1], e[0] - c[0]) - begin + math.pi) % (
        2 * math.pi
    ) - math.pi
    n = max(1, math.ceil(radius * abs(sweep) / step))
    return [
        (
            c[0] + radius * math.cos(begin + sweep * k / n),
            c[1] + radius * math.sin(begin + sweep * k / n),
        )
        for k in range(n + 1)
    ]


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    T = ctx["thick"]
    bl, bw, _bt = ctx["blank"]
    face = ctx["face"]
    z = {key: (layout, height, top) for key, layout, height, top in face["passes"]}

    def faced(key):
        layout, height, _top = z[key]
        return (
            "face_passes",
            {
                "z": height,
                "y": (-bw, 0.0),
                "max_engagement": face["layouts"][layout]["woc"],
                "radius": face["dia"] / 2,
                "span": bl / 2,
                "overhang": FACE_OVERHANG_MM,
            },
        )

    b_max = ctx["blank_max"]
    rs1, rs2, rs3 = (name for name, _ops in PROGRAMS)
    out: list[tuple[str, str, dict[str, Any]]] = [
        # RS01: both rough faces, one tool, the flip stop between them. Face 2
        # starts from Z1 + SAFE_MM, above the thickest blank's top, so the
        # file's stock top is that blank's.
        (rs1, "spindle", {"rpm": face["rpm"]}),
        (rs1, "tool_changes", {"z_top": b_max, "tools": []}),
        (rs1, "pauses", {"z_top": b_max, "count": 1, "spindle_off": True}),
        (rs1, "depth", {"z_min": z["face_2_rough"][1]}),
        (rs1, "rapids_clear", {"z_top": b_max}),
        (rs1, "air_feed", {"z_top": b_max}),
        (rs1, *faced("face_1_rough")),
        (rs1, *faced("face_2_rough")),
        (rs2, "spindle", {"rpm": face["rpm"]}),
        (rs2, "tool_changes", {"z_top": z["face_1_finish"][2], "tools": []}),
        (rs2, "pauses", {"z_top": z["face_1_finish"][2], "count": 0}),
        (rs2, "depth", {"z_min": z["face_1_finish"][1]}),
        (rs2, "rapids_clear", {"z_top": z["face_1_finish"][2]}),
        (rs2, "air_feed", {"z_top": z["face_1_finish"][2]}),
        (rs2, *faced("face_1_finish")),
    ]
    hub = [tuple(ctx["hub"])]

    def hole(key, feed_out=False):
        return [
            ("holes", {"centres": hub, "z_bottom": ctx[key]["z"]}),
            ("rapids_clear", {"z_top": T, "open_holes": hub}),
            ("vertical_below_top", {"z_top": T}),
            ("air_feed", {"z_top": T}),
            *([("feed_out", {"z_top": T})] if feed_out else []),
        ]

    ol, tabs = ctx["outline"], ctx["tabs"]
    r = ol["dia"] / 2
    sections = [
        (
            [face["rpm"]],
            [
                ("depth", {"z_min": T}),
                ("rapids_clear", {"z_top": z["face_2_finish"][2]}),
                ("air_feed", {"z_top": z["face_2_finish"][2]}),
                faced("face_2_finish"),
            ],
        ),
        (
            [],
            [
                ("probe_zero", {"axis": "X", "value": ctx["probe"]["x0"], "z_top": T}),
                ("rapids_clear", {"z_top": T}),
                ("air_feed", {"z_top": T}),
            ],
        ),
        ([ctx["spot"]["rpm"]], hole("spot")),
        ([ctx["drill"]["rpm"]], hole("drill")),
        ([ctx["ream"]["rpm"]], hole("ream", feed_out=True)),
        (
            [ol["rpm"]],
            [
                ("depth", {"z_min": ol["bottom"]}),
                ("rapids_clear", {"z_top": T}),
                ("air_feed", {"z_top": T}),
                # Rough and through at the finish stock outside the part, finish
                # at the part edge; anticlockwise, in the elements' order.
                (
                    "outline",
                    {
                        "elements": ol["elements"],
                        "z_top": T,
                        "passes": [
                            {
                                "offset": r + ol["stock"],
                                "levels": ol["rough"]["levels"]
                                + ol["through"]["levels"],
                            },
                            {"offset": r, "levels": ol["finish"]["levels"]},
                        ],
                        "tabs": [tuple(t) for t in tabs["through"] + tabs["finish"]],
                        "tab_clear": tabs["clear"],
                        "tab_top": tabs["top"],
                    },
                ),
                (
                    "tabs",
                    {
                        "centres": [tuple(t) for t in tabs["through"] + tabs["finish"]],
                        "clear": tabs["clear"],
                        "top": tabs["top"],
                    },
                ),
            ],
        ),
    ]
    out += [
        (rs3, "tool_changes", {"z_top": T, "tools": ctx["tool_changes"]}),
        (rs3, "spindle", {"rpm": [speeds for speeds, _checks in sections]}),
        (rs3, "pauses", {"z_top": T, "count": 0}),
    ]
    for k, (_speeds, checks) in enumerate(sections):
        out += [(f"{rs3}@{k}", check, kw) for check, kw in checks]
    return out


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job per
    operation group; returns {"ops": {operation key: operation or manual section}}."""
    T = ctx["thick"]
    bl, bw, _bt = ctx["blank"]
    names, numbers = ctx["names"], ctx["numbers"]
    doc = rt.document()
    strap = rt.import_step(
        doc, "Strap", ctx["step"], ctx["model"]["origin"], ctx["model"]["axes"]
    )

    def tool(key, rpm, feed, plunge, dia, shape="endmill", flutes=None, tip_angle=None):
        return rt.tool_controller(
            doc,
            names[key],
            numbers[key],
            shape,
            dia,
            rpm,
            feed,
            plunge,
            flutes=flutes,
            tip_angle=tip_angle,
        )

    ops: dict[str, Any] = {}
    # Faces: zigzag along X; each face model runs past both blank ends by the
    # placement allowance, a cutter diameter and the approach, so every plunge
    # and stepover link is clear of the blank, wherever its end sits by eye.
    fc = ctx["face"]
    run = END_ALLOWANCE_MM + fc["dia"] + APPROACH_MM
    for key, layout_key, height, stock_top in fc["passes"]:
        layout = fc["layouts"][layout_key]
        label = key.replace("_", " ")
        target = rt.job(
            doc,
            label,
            [
                rt.box(
                    doc,
                    f"{key}_model",
                    (-run, bl + run),
                    tuple(layout["y"]),
                    (0, height),
                )
            ],
            ((0, bl), (-bw, 0), (0, stock_top)),
        )
        tc = tool(
            "em-half", fc["rpm"], fc["feed"], fc["feed"], fc["dia"], flutes=fc["flutes"]
        )
        ops[key] = rt.face(
            target,
            tc,
            label,
            rt.top_face(rt.model(target), height),
            stock_top,
            height,
            layout["woc"],
            safe=stock_top + SAFE_MM,
        )
    # Hub hole, the faced strap in its frame: one job per tool.
    stock = ((0, bl), (-bw, 0), (0, T))
    hub = [tuple(ctx["hub"])]
    sp, dr, re_ = ctx["spot"], ctx["drill"], ctx["ream"]
    spot_job = rt.job(doc, "spot hub", [strap], stock)
    spot_tc = tool(
        "spot",
        sp["rpm"],
        sp["feed"],
        sp["feed"],
        sp["dia"],
        shape="drill",
        tip_angle=CENTRE_DRILL["point_deg"],
    )
    ops["spot"] = rt.drill(
        spot_job,
        spot_tc,
        "spot hub",
        rt.holes(rt.model(spot_job), ctx["hub_dia"], hub),
        T,
        sp["z"],
        T + SAFE_MM,
    )
    drill_job = rt.job(doc, "drill hub", [strap], stock)
    drill_tc = tool(
        "hub-drill",
        dr["rpm"],
        dr["feed"],
        dr["feed"],
        dr["dia"],
        shape="drill",
        tip_angle=118,
    )
    ops["drill"] = rt.drill(
        drill_job,
        drill_tc,
        "drill hub",
        rt.holes(rt.model(drill_job), ctx["hub_dia"], hub),
        T,
        dr["z"],
        T + SAFE_MM,
        peck=dr["dia"],
    )
    ream_job = rt.job(doc, "ream hub", [strap], stock)
    ream_tc = tool("hub-reamer", re_["rpm"], re_["feed"], re_["feed"], re_["dia"])
    ops["ream"] = rt.bore(
        ream_job, ream_tc, "ream hub", hub, re_["z"], T + SAFE_MM, T + CLEAR_MM
    )
    # Outline: the strap's top face's perimeter, outside, anticlockwise
    # (conventional), entered on the top arc at the hub's X (fence side, far
    # from the clamp-side tabs).
    ol, tb = ctx["outline"], ctx["tabs"]
    outline_job = rt.job(doc, "outline", [strap], stock)
    otc = tool("em-eighth", ol["rpm"], ol["feed"], ol["plunge"], ol["dia"], flutes=3)
    perimeter = rt.top_face(rt.model(outline_job), T)
    heights = {
        "clearance": T + CLEAR_MM,
        "safe": T + SAFE_MM,
        "start_point": ol["start"],
    }
    ops["outline_rough"] = rt.profile(
        outline_job,
        otc,
        "outline rough",
        perimeter,
        "Outside",
        "CCW",
        T,
        tb["top"],
        ol["rough"]["step"],
        offset=ol["stock"],
        **heights,
    )
    through = rt.profile(
        outline_job,
        otc,
        "outline through",
        perimeter,
        "Outside",
        "CCW",
        tb["top"],
        ol["bottom"],
        ol["through"]["step"],
        offset=ol["stock"],
        **heights,
    )
    ops["outline_through"] = rt.tags(
        through, tb["through"], tb["width"], tb["top"] - ol["bottom"]
    )
    finish = rt.profile(
        outline_job,
        otc,
        "outline finish",
        perimeter,
        "Outside",
        "CCW",
        T,
        ol["bottom"],
        ol["finish"]["step"],
        **heights,
    )
    ops["outline_finish"] = rt.tags(
        finish, tb["finish"], tb["width"], tb["top"] - ol["bottom"]
    )
    # Manual sections, their G-code written by context(): the flip stop and the probe's X0.
    ops["flip"], ops["probe_x0"] = ctx["flip"], ctx["probe"]
    rt.generate(doc)
    return {"ops": ops}
