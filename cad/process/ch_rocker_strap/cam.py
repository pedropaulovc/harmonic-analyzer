"""FreeCAD CAM recipe for MHA-CH-13, the rocker strap.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. No part dimension is
typed here: the thickness, hub hole and outline come from the manifest (and
its STEP, which FreeCAD profiles); the blank, the part's place in it, the
face stock split, the tape stack and its seams, skin and depth levels, the
plate's relief, fence notches and the bushing from ``plan.toml``
``[parameters]`` and ``milling_cuts``; cutter diameters, speeds and feeds
from the shop (``shop/``).
Typed here, because neither record carries them: the #2 centre drill's
catalogue geometry (it sets the spot depth), the approach clearance, the face
overhang past the blank's edges, the face-1 least skin, the safe and
clearance heights, the flip's lift, the share of a printed band the posted
outline may use, the through cut's margin to the strap and the plate, and
the least spacing of the two tape layers' seams.

Route (owner, 2026-11-17, no tabs; process text in the plan): the 12 x
1-1/2 x 1/8 in 1018 CF flat lies on a shop-made 6061 sub-plate gripped in the
vise, against the plate's fence and end stop. One work frame (G54), set once
per vise setup with no blank in and fixed to the plate: X0 the end stop's
face (the blank's left end), Y0 the fence face with the blank at -Y, Z0 the
faced plate top. The strap lies with its top arc (concave side) toward the
fence and its bottom arc away from it, its hub always at the plan's
``hub_x_mm``, ``-hub_y_mm``: over the centre of the plate's counterbored
relief.

- RS01 (edge clamps on): rough face 1 at a fixed Z, stop for the flip (end
  for end, the same edge on the fence), rough face 2. Release, turn over
  (face 1 up), reseat.
- RS02: finish face 1. Release, turn over (face 2 up) and reseat.
- RS03: finish face 2 to the finished thickness, spot, drill and ream the hub
  hole into the relief, the tips above the relief's floor. The file ends
  after the ream.
- RS04 (edge clamps off): the blank bonded on blue painter's tape on both
  faces with CA glue between, so Z is the plate top with the tape stack
  under the part; a stepped plug in the relief locates the reamed hub, a
  screw and shouldered bushing hold it, the edge on the fence
  sets its rotation. With the 1/8 in end mill: clear the waste between the
  outline and the fence under both tips (the fence is notched there), rough
  the outline at the finish stock down to the onion skin, finish the wall at
  size down to the skin, then cut through the skin at size into the stack.
  Every move keeps the cutter off the un-notched fence and the bushing.

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws), plunges
beside the stock at the cutting feed, plunges into metal (the outline levels)
at the plan's plunge feed, real G0 above the stock. The outline runs
anticlockwise round the part: conventional with a clockwise spindle; the
waste clearing runs the same way along the top arc. The reamer feeds in and
out (a rapid retract can score the press-fit bore).
"""

from __future__ import annotations

import itertools
import math
import re
from typing import Any

STEM = "ch_rocker_strap"
COMMENT = "MHA-CH-13 rocker strap"
# Programs in order, each listing its operation keys. A program whose keys are
# grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section: the flip stop), joined at M6 tool changes and M0 stops.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("RS01_rough_faces", (("face_1_rough",), ("flip",), ("face_2_rough",))),
    ("RS02_finish_face_1", ("face_1_finish",)),
    ("RS03_finish_face_2_hub", (("face_2_finish",), ("spot",), ("drill",), ("ream",))),
    (
        "RS04_outline",
        ("fence_sliver", "outline_rough", "outline_finish", "outline_through"),
    ),
)
# Every program loads its own first tool (M6, the tool setter): none relies on
# the tool and length the previous file left. RS01 -> RS02 -> RS03 would hand
# T1 on, but RS01 follows RS04's T2 on the next blank, RS04 follows RS03's T5,
# and the plan sends a thin blank back for a skim (RS02 or RS03 again) or a
# file is restarted after an abort on T3-T5: CNCjs keeps whatever length was
# last set, so a carried-over tool would be cut with another's length.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (tools off the mill, the saw and the files, are not).
CAM_TOOLS = ("em-half", "em-eighth", "spot", "hub-drill", "hub-reamer")
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
# Faces reach at least this far past the blank's fence and clamp edges, over
# the fence, clamps and end stop, which stand below the faced top (the
# context checks).
FACE_OVERHANG_MM = 0.5
# Face 1 roughs at a fixed Z; the thinnest blank the plan allows must still
# lose at least this skin (.004 in) there, so the mill-finish face comes off.
FACE_SKIN_MIN_MM = 0.1016
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it, so only this much of each plunge is above the
# stock. FreeCAD measures each G83 peck from the R plane.
SAFE_MM = 1.0
# Moves between holes run this far above the stock top.
CLEAR_MM = 5.0
# The flip stop lifts the 1/2 in end mill this far above the plate, room to
# release the clamps and turn the blank over beneath it.
FLIP_LIFT_MM = 50.0
# The posted outline's cutter centre may stray from its offset by this share
# of the tightest printed band locating that edge; the rest is the machine's.
BAND_FRACTION = 0.1
# The through cut keeps at least this much (.004 in) to the strap's
# underside and to the plate at both ends of the tape stack's band: the tool
# setter's and the Z0 touch-off's repeatability, the author's allowance.
THROUGH_MARGIN_MM = 0.1
# The two tape layers' seams at least this far (1/2 in) apart across the
# blank: the brief asks about half a strip (1.41 in wide), the author's floor.
SEAM_OFFSET_MIN_MM = 12.7


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


def _steps(lo: float, hi: float, step: float) -> list[float]:
    """``lo`` to ``hi``, both included, in equal steps no longer than ``step``."""
    n = max(1, math.ceil((hi - lo) / step))
    return [lo + (hi - lo) * k / n for k in range(n + 1)]


def _inside(point: tuple[float, float], poly: list[tuple[float, float]]) -> bool:
    """Whether ``point`` lies inside the closed polygon ``poly`` (even-odd)."""
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


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
    # The face cuts' declared depths (process parameters, so the measured
    # setting's envelope can be proved from the plan) are their deepest cuts:
    # rough, the thickest blank's first face or the second face, whichever is
    # deeper; finish, the finish stock on either face.
    for name, deepest in (
        ("face rough", max(b_max - z1, z1 - z2)),
        ("face finish", max(z2 - z3, z3 - thick)),
    ):
        declared = _cut(plan, name, "axial_doc_mm")
        if not math.isclose(declared, deepest, abs_tol=1e-3):
            raise ValueError(
                f"'{name}' axial_doc_mm {declared:g} is not its deepest cut, {deepest:.4f}"
            )
    # The faces overhang the fence, the clamps and the end stop: all must
    # stand below the lowest faced top.
    for name in ("fence_height_mm", "clamp_height_mm", "end_stop_height_mm"):
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
    # RS04 frame: the part's underside on the bond's stack (blue tape, CA
    # glue, blue tape), so every part Z rises by the stack. The file is posted
    # on the nominal stack; the operator mics each bond's stack into the
    # record's band. Rough and finish stop at the onion skin; the through
    # pass cuts the skin and into the stack, never the plate.
    stack = p["tape_stack_mm"]
    stack_band = (p["tape_stack_min_mm"], p["tape_stack_max_mm"])
    if p["tape_thickness_mm"] != stack:
        raise ValueError(
            "process.tape_thickness_mm (the adapter's name for the stack) is not process.tape_stack_mm"
        )
    if not stack_band[0] < stack < stack_band[1]:
        raise ValueError(f"tape stack {stack} is outside its band {stack_band}")
    top4 = stack + thick
    skin = stack + p["outline_skin_mm"]
    through = stack - p["outline_breakthrough_mm"]
    if not 0 < through < stack < skin < top4:
        raise ValueError(
            f"stack {stack:.3f}, skin Z {skin:.3f}, through Z {through:.3f}: not plate < through < stack < skin < top {top4:.3f}"
        )
    # The through cut's Z is fixed over the plate; the strap's underside
    # stands at whatever stack the bond has. At both ends of the band the cut
    # must clear the strap's underside (binding at the thinnest stack) and
    # stop short of the plate (its Z does not move with the stack), each by
    # THROUGH_MARGIN_MM.
    for s in stack_band:
        if through > s - THROUGH_MARGIN_MM:
            raise ValueError(
                f"at a {s:.2f} mm stack the through cut at Z {through:.3f} is not {THROUGH_MARGIN_MM} mm below the strap's underside"
            )
        if through < THROUGH_MARGIN_MM:
            raise ValueError(
                f"at a {s:.2f} mm stack the through cut at Z {through:.3f} is not {THROUGH_MARGIN_MM} mm above the plate"
            )
    # The highest the strap's top stands: the thickest stack. Rapids and the
    # bushing's clearance are judged there.
    top4_max = stack_band[1] + thick
    origin4 = [origin[0], origin[1], z_under - stack]

    # The rough slot reaches 2r + finish stock outside the part: it must stay
    # inside the blank at the far edge and the ends (the waste frame stays
    # whole on the tape). On the fence side the notches and the clearing
    # below take over.
    samples = [pt for e in elements for pt in _outline_samples(e)]
    reach = em_eighth + finish_stock
    margins = {
        "far edge": min(y for _x, y in samples) + bw - reach,
        "left end": min(x for x, _y in samples) - reach,
        "right end": bl - max(x for x, _y in samples) - reach,
    }
    broken = {k: round(v, 3) for k, v in margins.items() if v <= 0}
    if broken:
        raise ValueError(f"the outline slot breaks out of the blank at {broken} mm")

    # Tape seams run along X, each layer's at its distance from the fence face
    # (plan tape_seam_*_mm). The two layers' seams sit apart, and at no X do
    # both lie in the slot's band (outside the part, within the rough slot's
    # reach of its edge): no cut rides on a seam of both layers.
    seam_blank, seam_plate = -p["tape_seam_blank_mm"], -p["tape_seam_plate_mm"]
    if abs(seam_blank - seam_plate) < SEAM_OFFSET_MIN_MM:
        raise ValueError(
            f"the blank's and the plate's tape seams are {abs(seam_blank - seam_plate):.2f} mm apart (< {SEAM_OFFSET_MIN_MM})"
        )

    def in_slot(x: float, y: float) -> bool:
        near = [pt for pt in samples if abs(pt[0] - x) < reach]
        return (
            bool(near)
            and min(math.dist((x, y), pt) for pt in near) < reach
            and not _inside((x, y), samples)
        )

    both = [
        x
        for x in _steps(0.0, bl, 0.5)
        if in_slot(x, seam_blank) and in_slot(x, seam_plate)
    ]
    if both:
        raise ValueError(
            f"both tape seams lie in the outline slot at X {both[0]:.1f}-{both[-1]:.1f}"
        )

    outline_rpm, outline_feed, outline_flutes = _setting(plan, shop, "outline rough")
    for name in ("outline finish", "outline through", "fence sliver"):
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
        top4, skin, _cut(plan, "outline rough", "axial_doc_mm")
    )
    # The finish takes the whole wall, top to skin, in one level (the plan's
    # cut binds that depth to its prechips adapter, cad.outline_wall_depth_mm).
    finish_step, finish_levels = top4 - skin, [skin]
    through_step, through_levels = _levels(
        skin, through, _cut(plan, "outline through", "axial_doc_mm")
    )

    # The bushing's flange stands on the part round the hub: the cutter's
    # edge on the finish pass (the part edge) must keep the plan's clearance.
    hub_xy = (hub_x, hub_y)
    keep = p["bushing_flange_dia_mm"] / 2 + p["bushing_clearance_mm"]
    nearest = min(math.dist(hub_xy, pt) for pt in samples)
    if nearest < keep:
        raise ValueError(
            f"the outline passes {nearest:.3f} from the hub, inside the bushing flange's {keep:.3f}"
        )
    flange_top = top4_max + p["bushing_stack_height_mm"]
    clear4 = flange_top + SAFE_MM

    # Fence sliver: under each tip the rough slot leaves a strip of blank
    # against the fence narrower than the plan's sliver_width_min_mm. In each
    # notch (hub_x -/+ the plan's inner..outer, the cutter centre a radius
    # inside it) rings concentric with the top arc, each a radial step
    # farther out, clear it from the through slot's edge (2r off the part;
    # the first ring's inner edge one step off it, clear of the finish stock)
    # out past the fence face, every level down to the through depth. The
    # cutter crosses Y0 only inside a notch, which is at least a cutter
    # diameter deep. Fence-side ring first, so each later ring has the waste
    # on its part side only; each runs the top arc's way (+X to -X).
    notch_depth, notch_floor = p["fence_notch_depth_mm"], p["fence_notch_floor_z_mm"]
    if notch_depth < em_eighth or notch_floor >= through:
        raise ValueError(
            f"fence notch {notch_depth:.3f} deep with its floor at Z {notch_floor:.3f}: needs >= {em_eighth:.3f} deep, floor below Z {through:.3f}"
        )
    woc = _cut(plan, "fence sliver", "radial_woc_mm")
    if not finish_stock < woc <= em_eighth:
        raise ValueError(
            f"'fence sliver' radial_woc_mm {woc} is not between the finish stock and the cutter"
        )
    _sliver_step, sliver_levels = _levels(
        top4, through, _cut(plan, "fence sliver", "axial_doc_mm")
    )
    cx, cy = xy(top["arc_centre"])
    top_radius = math.dist((cx, cy), xy(top["ends"][0]))
    if cy <= 0:
        raise ValueError("the top arc's centre is not on the fence side")
    inner, outer = p["fence_notch_inner_mm"], p["fence_notch_outer_mm"]
    notches = [[hub_x - outer, hub_x - inner], [hub_x + inner, hub_x + outer]]
    # Outside the notches the strip the rough slot leaves against the fence
    # stays at least sliver_width_min_mm wide: no thin sliver left in place.
    strip_min = p["sliver_width_min_mm"]
    for x in _steps(0.0, bl, 0.5):
        if any(a <= x <= b for a, b in notches):
            continue
        edge = max(
            (
                y + math.sqrt(reach**2 - (sx - x) ** 2)
                for sx, y in samples
                if abs(sx - x) < reach
            ),
            default=-bw,
        )
        if -edge < strip_min:
            raise ValueError(
                f"at X {x:.2f}, outside the fence notches, the rough slot leaves a {-edge:.3f} mm strip against the fence (< sliver_width_min_mm {strip_min})"
            )
    sliver_gcode: list[str] = []
    clearing, cleared = [], []
    for a, b in notches:
        lo, hi = a + r, b - r
        if not 0 <= a < lo < hi < b <= bl:
            raise ValueError(
                f"fence notch X [{a}, {b}] is not inside the blank, a cutter wide"
            )
        low_x = min(max(cx, lo), hi)  # where the rings lie farthest from the fence
        rings = []
        for k in itertools.count(1):
            rho = top_radius - (r + k * woc)
            if k * woc > bw:
                raise ValueError(f"the rings in notch [{a}, {b}] never reach the fence")
            half = math.sqrt(rho**2 - (cy - r) ** 2)  # the disk leaves the blank
            x0, x1 = max(lo, cx - half), min(hi, cx + half)
            if x0 < x1:
                rings.append((rho, x0, x1))
            if cy - math.sqrt(rho**2 - (low_x - cx) ** 2) + r >= 0:
                break
        for z in sliver_levels:
            for rho, x0, x1 in reversed(rings):
                y0 = cy - math.sqrt(rho**2 - (x0 - cx) ** 2)
                y1 = cy - math.sqrt(rho**2 - (x1 - cx) ** 2)
                sliver_gcode += [
                    f"G0 Z{clear4:.4f}",
                    f"G0 X{x1:.4f} Y{y1:.4f}",
                    f"G0 Z{top4 + SAFE_MM:.4f}",
                    f"G1 Z{z:.4f} F{{plunge}}",
                    f"G2 X{x0:.4f} Y{y0:.4f} I{cx - x1:.4f} J{cy - y1:.4f} F{{feed}}",
                ]
        sliver_gcode.append(f"G0 Z{clear4:.4f}")
        clearing.append({"x": [lo, hi], "levels": sliver_levels})
        # The blank between the through slot (2r off the top arc) and the
        # fence, over the X the cutter centre reaches.
        cleared += [
            [x, y]
            for x in _steps(lo, hi, 0.5)
            for y in _steps(-bw, 0.0, 0.25)
            if math.dist((cx, cy), (x, y)) < top_radius - em_eighth - 0.01
        ]

    # Keep-outs: the fence (Y0 to its width, up to its height) but for the
    # notches, the notches' back walls and floors, and the bushing.
    fence_y, fence_top = [0.0, p["fence_width_mm"]], p["fence_height_mm"]
    plate_x = [p["plate_start_x_mm"], p["plate_start_x_mm"] + p["plate_length_mm"]]
    edges = [plate_x[0], *[x for n in notches for x in n], plate_x[1]]
    fixtures = [
        {"name": "fence", "x": [x0, x1], "y": fence_y, "z_top": fence_top}
        for x0, x1 in zip(edges[::2], edges[1::2])
    ]
    for a, b in notches:
        fixtures.append(
            {
                "name": "notch floor",
                "x": [a, b],
                "y": [0.0, notch_depth],
                "z_top": notch_floor,
            }
        )
        if notch_depth < fence_y[1]:
            fixtures.append(
                {
                    "name": "notch wall",
                    "x": [a, b],
                    "y": [notch_depth, fence_y[1]],
                    "z_top": fence_top,
                }
            )
    bushing = {"name": "bushing", "centre": hub_xy, "radius": keep, "z_top": flange_top}

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
    import cam_nc

    if -ream_tip <= cam_nc.ream_full_diameter_past_min_mm(plan, "hub-reamer"):
        raise ValueError(
            f"reamer tip Z {ream_tip:.3f}: its full diameter does not reach the strap's underside (cnc.ream-full-diameter)"
        )
    # The relief is a counterbore with the bushing screw's tapped hole in its
    # floor: both tips stop the plan's clearance above that floor.
    relief_floor = -p["hub_relief_depth_mm"]
    lowest_tip = relief_floor + p["relief_floor_clearance_mm"]
    # Both ends run out into the relief, wider than either; its floor is the
    # first solid below them.
    cam_nc.ream_end_face_clear(
        plan,
        "hub-reamer",
        reamer_dia,
        ream_tip,
        drill_dia,
        drill_tip + drill_dia / 2 / math.tan(math.radians(59)),
        relief_floor,
    )
    if min(drill_tip, ream_tip) < lowest_tip:
        raise ValueError(
            f"drill tip Z {drill_tip:.3f} / reamer tip Z {ream_tip:.3f} below Z {lowest_tip:.3f}, the relief floor {relief_floor:.3f} plus its clearance"
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
        " LEFT END ON THE END STOP, PLATE WIPED CLEAN, RE-CLAMP, THEN CYCLE START",
        "M0",
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
            numbers[t] for t in ("em-half", "spot", "hub-drill", "hub-reamer")
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
            # Away from the hub and its bushing: the -X foot of the bottom arc.
            "start": xy(bottom["ends"][0]),
            "origin": origin4,
            "top": top4,
            "top_max": top4_max,
            "skin": skin,
            "bottom": through,
            "clearance": clear4,
            "rough": {"step": rough_step, "levels": rough_levels},
            "finish": {"step": finish_step, "levels": finish_levels},
            "through": {"step": through_step, "levels": through_levels},
            "sliver": {"gcode": sliver_gcode, "clearing": clearing, "cleared": cleared},
            "fixtures": fixtures,
            "bushing": bushing,
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
    t1 = ctx["numbers"]["em-half"]
    rs1, rs2, rs3, rs4 = (name for name, _ops in PROGRAMS)
    out: list[tuple[str, str, dict[str, Any]]] = [
        # RS01: both rough faces, one tool, the flip stop between them. Face 2
        # starts from Z1 + SAFE_MM, above the thickest blank's top, so the
        # file's stock top is that blank's.
        (rs1, "spindle", {"rpm": face["rpm"]}),
        (rs1, "tool_changes", {"z_top": b_max, "tools": [t1], "loads_first": True}),
        (rs1, "pauses", {"z_top": b_max, "count": 1, "spindle_off": True}),
        (rs1, "depth", {"z_min": z["face_2_rough"][1]}),
        (rs1, "rapids_clear", {"z_top": b_max}),
        (rs1, "air_feed", {"z_top": b_max}),
        (rs1, *faced("face_1_rough")),
        (rs1, *faced("face_2_rough")),
        (rs2, "spindle", {"rpm": face["rpm"]}),
        (
            rs2,
            "tool_changes",
            {"z_top": z["face_1_finish"][2], "tools": [t1], "loads_first": True},
        ),
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
        ([ctx["spot"]["rpm"]], hole("spot")),
        ([ctx["drill"]["rpm"]], hole("drill")),
        ([ctx["ream"]["rpm"]], hole("ream", feed_out=True)),
    ]
    out += [
        (
            rs3,
            "tool_changes",
            {"z_top": T, "tools": ctx["tool_changes"], "loads_first": True},
        ),
        (rs3, "spindle", {"rpm": [speeds for speeds, _checks in sections]}),
        (rs3, "pauses", {"z_top": T, "count": 0}),
    ]
    for k, (_speeds, checks) in enumerate(sections):
        out += [(f"{rs3}@{k}", check, kw) for check, kw in checks]

    # RS04: one tool, one speed. The fence-sliver rings first, then rough at
    # the finish stock outside the part and finish at the part edge, both to
    # the skin, then through at the part edge: anticlockwise, in the
    # elements' order, no tabs. The cutter misses the un-notched fence, the
    # notches' walls and floors and the bushing; nothing cuts the plate.
    ol = ctx["outline"]
    r, top4 = ol["dia"] / 2, ol["top"]
    out += [
        (rs4, "spindle", {"rpm": ol["rpm"]}),
        (
            rs4,
            "tool_changes",
            {
                "z_top": top4,
                "tools": [ctx["numbers"]["em-eighth"]],
                "loads_first": True,
            },
        ),
        (rs4, "pauses", {"z_top": top4, "count": 0}),
        (rs4, "depth", {"z_min": ol["bottom"]}),
        (rs4, "rapids_clear", {"z_top": ol["top_max"]}),
        (rs4, "air_feed", {"z_top": top4}),
        (
            rs4,
            "outline",
            {
                "elements": ol["elements"],
                "z_top": top4,
                "passes": [
                    {"offset": r + ol["stock"], "levels": ol["rough"]["levels"]},
                    {"offset": r, "levels": ol["finish"]["levels"]},
                    {"offset": r, "levels": ol["through"]["levels"]},
                ],
                "clearing": ol["sliver"]["clearing"],
            },
        ),
        (
            rs4,
            "cleared",
            {"points": ol["sliver"]["cleared"], "radius": r, "z": ol["bottom"]},
        ),
        (
            rs4,
            "keep_out",
            {"radius": r, "boxes": ol["fixtures"], "circles": [ol["bushing"]]},
        ),
    ]
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
    # Faces: zigzag along X; each face model runs past both blank ends by a
    # cutter diameter and the approach, so every plunge and stepover link is
    # in the air beside the blank (over the end stop, below the faced top).
    fc = ctx["face"]
    run = fc["dia"] + APPROACH_MM
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
    # RS04: the strap on the tape stack (its own model, raised by the stack). The
    # fence-sliver rings (written by context()), then the top face's perimeter
    # outside, anticlockwise (conventional), entered at the bottom arc's -X
    # foot, away from the bushing; links clear the bushing's top.
    ol = ctx["outline"]
    top4 = ol["top"]
    strap4 = rt.import_step(
        doc, "Strap on tape", ctx["step"], ol["origin"], ctx["model"]["axes"]
    )
    stock4 = ((0, bl), (-bw, 0), (top4 - T, top4))  # the tape stack under the part
    outline_job = rt.job(doc, "outline", [strap4], stock4)
    otc = tool("em-eighth", ol["rpm"], ol["feed"], ol["plunge"], ol["dia"], flutes=3)
    ops["fence_sliver"] = rt.custom(
        outline_job, otc, "fence sliver", ol["sliver"]["gcode"]
    )
    perimeter = rt.top_face(rt.model(outline_job), top4)
    heights = {
        "clearance": ol["clearance"],
        "safe": top4 + SAFE_MM,
        "start_point": ol["start"],
    }
    for key, start, final, offset in (
        ("rough", top4, ol["skin"], ol["stock"]),
        ("finish", top4, ol["skin"], 0.0),
        ("through", ol["skin"], ol["bottom"], 0.0),
    ):
        ops[f"outline_{key}"] = rt.profile(
            outline_job,
            otc,
            f"outline {key}",
            perimeter,
            "Outside",
            "CCW",
            start,
            final,
            ol[key]["step"],
            offset=offset,
            **heights,
        )
    # The manual section, its G-code written by context(): the flip stop.
    ops["flip"] = ctx["flip"]
    rt.generate(doc)
    return {"ops": ops}
