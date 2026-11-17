"""FreeCAD CAM recipe for MHA-CH-06-TL-20, the oblique trammel base bar (bars 1 and 2).

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. No part dimension is
typed here: lengths, hole and slot positions come from the manifest; blank
size, cutter tip depths, radial steps and jack positions from ``plan.toml``
``[parameters]`` and ``milling_cuts``; cutter diameters, speeds and feeds from
``shop.toml``. A CAD change reaches the programs through the re-exported
manifest. Typed here, because neither record carries them: the #2 centre
drill's catalogue geometry (it sets the spot depth), the S2 strap clearance,
the approach clearance, the drilling R plane, the facing plunge feed, the
side-1 face's least skin, the tap stops' heights, the flip's lift and the
probe's search distance and feeds.

Setups follow ``plan.toml``: S2 edges on 1-2-3 blocks; S3 in the vise, one
file per bar: face side 1, stop for the flip end-for-end, face side 2, probe
the flipped bar's left end for X0, then without unclamping (owner ruling
2026-11-16, "merge") square the ends, mill the slots, spot, drill, tap and
counterbore. After the side-2 face both bars sit ZERO END left, ZERO EDGE
(the model's low side) at the back jaw, the model's underside face up (bar 1
C'BORE SIDE, bar 2 RAIL SIDE), so every through feature is shared and only
the bracket holes are bar 1's. Sawing and deburring stay manual.

Toolpath rules (owner rulings 2026-11-16, Pedro):

- "replace fusion with oss cam": FreeCAD's CAM workbench builds and posts
  every program, with real G0 rapids above the stock.
- Edges: "Cut edge 1 in +X and edge 2 in −X", so both stay conventional (the
  dechatter edge settings were measured conventional) and neither returns
  through the air: each pass on the front edge ends where the next pass on the
  back edge starts, level by level.
- Faces: the PM-30MV conversion has ball screws, so face passes zigzag
  (climb on alternate passes).
- Ends, slots, spot, drill and counterbore keep their plan strategy: ends
  one-way conventional, slots conventional inside from the plunge corner the
  plan names, holes plunged from the stock top.
- Ends at the measured 2250 rpm, slots at 1250, set by hand on the knob at an
  operator comment and ``M0`` (owner: "why not single program with m0 for
  spindle/tool change").
- One NC file per bar per setup (Main, 2026-11-16, relaying the owner), with
  ``M6 T<n>`` tool changes the sender expands (CNCjs "Manual Tool Change"
  with the electronic tool setter; the PM-30MV's FluidNC v3.7.8 has no
  manual-change support of its own). The flip is an ``M0`` with the spindle
  stopped and the Tri Fly lifted; the side-2 face needs X only roughly (it
  runs a cutter diameter past each end), and the 3D touch probe then finds
  the flipped bar's left end and sets X0 with ``G38.2`` and ``G10 L20 P1``
  (Main relaying the owner, 2026-11-16), so no jog is needed while FluidNC
  holds at the ``M0``. Taps are turned by hand in the spring tap guide,
  spindle off, the CNC stopping over each hole.
- Facing is on the 2 in Shrum Tri Fly (owner, 2026-11-16). The tool setter
  cannot measure it, so each file starts with it loaded and touched off by
  hand (plan S3); it stays in through the flip, and the first ``M6`` (the
  probe) hands over to the tool setter.

Tool numbers are the tools' places in the plan's tool list (the saw, cut off
the mill, left out); the files' tool changes follow the plan's Setup 3
operations. The CAM model frame is the setup WCS (G54), one for all of S3:
X0 ZERO END (before the probe sets it, the previous bar's or the vise
setup's, close enough to face by), Y0 ZERO EDGE, bar at -Y, Z0 the
parallels' top, which the bar sits on (Main relaying the owner, 2026-11-16:
no top-face touch-off; the faced thickness puts the top at Z = finished
thickness), i.e. ``x' = x - x0``, ``y' = -(y - y_low)``,
``z' = thickness - (z - z_underside)``. Side 1 faces at a fixed Z, half the
nominal allowance off; the plan's blank-thickness band is what guarantees it
cleans up and stays within the plan's checked depth of cut (:func:`context`
refuses a band that does not).
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ch_rocker_arm_tl_oblique_base_bar"
COMMENT = "MHA-CH-06-TL-20 oblique base bar"
# Programs in order, each listing its operation keys; a key may name a list of
# operations (the edges' interleaved passes). A program whose keys are grouped
# in tuples is one section per group (a FreeCAD Job, or a manual section: the
# flip stop, the probe, the tap stops), joined at M6 tool changes and M0
# stops; it starts with its first section's tool loaded.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("BB01_S2_edges_T1", ("edges",)),
    ("BB02_S3_bar1", (("face_side1",), ("flip",), ("face_side2",), ("probe_x0",), ("left_end", "right_end"),
                      ("slot_near", "slot_far"), ("spot_rail",), ("spot_bracket",), ("drill_rail",), ("drill_bracket",),
                      ("tap",), ("counterbore",))),
    ("BB03_S3_bar2", (("face_side1",), ("flip",), ("face_side2",), ("probe_x0",), ("left_end", "right_end"),
                      ("slot_near", "slot_far"), ("spot_rail",), ("drill_rail",), ("tap",))),
)
# Plan tools bar 2 never uses: it has no bracket holes.
BAR1_ONLY = ("bracket-drill", "counterbore")
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included: the shop record names
# the tool, not its geometry.
CENTRE_DRILL = {"body_mm": 3 / 16 * IN, "pilot_mm": 5 / 64 * IN, "pilot_length_mm": 5 / 64 * IN}
# Strap studs and nuts stand above the bar in S2; their height is not recorded,
# so moves between the two edges clear the stock top by this much.
STRAP_CLEARANCE_MM = 60.0
# Side and face passes start and finish with the cutter this far clear of the
# stock, so every plunge enters air beside it, never the material. Edge and
# end plunges therefore run at the pass's cutting feed; only the slots plunge
# into metal, at the plan's slow corner-plunge feed.
APPROACH_MM = 2.54
# S2's right-hand plunges sit past the sawn blank end, whose length is only as
# good as the saw: they clear a blank up to this much over the plan's length.
SAW_ALLOWANCE_MM = 3.81
# Faces reach at least this far past the bar's front and back edges, so a bar
# at the top of its width band or a ZERO EDGE edge-find error leaves no lip
# (past ZERO EDGE they reach farther: _face_layout). The cutter then passes
# over the vise jaws, which stand below the faced top (the context checks it).
FACE_OVERHANG_MM = 0.5
# Side 1 faces at a fixed Z; the thinnest blank the plan allows must still
# lose at least this skin (.004 in) there, so the mill-finish face and any
# saw burr come off and side 1 is a full datum for side 2.
FACE_SKIN_MIN_MM = 0.1016
# Plunges and drill pecks start this far above the stock top: real G0 brings
# the tool down to it, so only this much of each plunge is above the stock.
# FreeCAD measures each G83 peck from this R plane, so a higher one would
# also make the first peck feed through air.
SAFE_MM = 1.0
# The tap's point stops this far above each rail hole for the hand tap (the
# drills' R plane), moving between holes this far above the top.
TAP_CLEAR_MM = 5.0
# The flip stop lifts the Tri Fly this far above the parallels' top, room to
# lift the bar out and turn it over beneath it.
FLIP_LIFT_MM = 75.0
# The flipped bar is set back centred on the jaws by eye, and its blank length
# varies: the probe starts this far left of the nominal left end (descending
# beside it, clear of it) and searches as far past it. The side-2 face runs a
# cutter diameter past each end, so it covers the same shift.
PROBE_SEARCH_MM = 20.0
# Probe feeds (mm/min): the seek, and the slow second touch the zero is set
# at, within the TP05 listing's 50-200 mm/min probing feed.
PROBE_SEEK_FEED = 150.0
PROBE_TOUCH_FEED = 50.0


def _feed_mm_min(text: str) -> float:
    match = re.fullmatch(r"\s*([\d.]+)\s*in/min\s*", text)
    if not match:
        raise ValueError(f"feed {text!r}: expected 'N in/min'")
    return float(match.group(1)) * IN


def _plan_operations(plan: dict[str, Any]):
    for setup in plan["setups"]:
        yield from setup.get("operations", ())


def _op_with_cut(plan: dict[str, Any], name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for op in _plan_operations(plan):
        for cut in op.get("milling_cuts", ()):
            if cut["name"] == name:
                return op, cut
    raise KeyError(f"plan has no milling cut {name!r}")


def _cut(plan: dict[str, Any], name: str) -> dict[str, Any]:
    return _op_with_cut(plan, name)[1]


def _plunge_feed(plan: dict[str, Any], name: str) -> tuple[float, float]:
    """(rpm, mm/min) of the plan's plunge or drill cut ``name``: the operation's
    rpm, and feed per tooth × flutes × rpm."""
    op, cut = _op_with_cut(plan, name)
    return float(op["rpm"]), cut["feed_per_tooth_mm"] * cut["flutes"] * op["rpm"]


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


def _setting(shop: dict[str, Any], name: str) -> tuple[float, float]:
    record = shop["settings"][name]
    return float(record["rpm"]), _feed_mm_min(record["feed"])


def _levels(depth: float, max_step: float) -> list[float]:
    """Equal depth levels from the stock top (Z0) down to ``-depth``, as few as
    keep each no deeper than ``max_step``."""
    n = math.ceil(depth / max_step - 1e-9)
    return [-depth * (k + 1) / n for k in range(n)]


def _stations(trim: float, max_step: float, finish: float = 0.0) -> list[float]:
    """Cutter offsets beyond the final position, raw face inward: equal steps of
    at most ``max_step`` from ``trim`` (the raw face) to ``finish``, then, when
    ``finish`` is set, the finishing pass at 0. No pass cuts air."""
    n = math.ceil((trim - finish) / max_step - 1e-9)
    rough = [finish + (trim - finish) * (n - k) / n for k in range(1, n + 1)]
    return [*rough, 0.0] if finish else rough


def _face_layout(width: float, dia: float, woc: float, name: str) -> dict[str, Any]:
    """Zigzag face passes over a bar ``width`` wide at Y -width..0, each pass
    taking ``woc`` (the plan cut's radial width, which its force estimate
    assumes) of stock no earlier pass cut, the first included.

    FreeCAD's MillFace lays its lines a whole percentage of the cutter apart
    from the bottom of the face's box, inset a cutter radius, and cuts the top
    line first: with the box flush with the bar's ZERO EDGE side that first
    pass runs nearly full width. So the box's top sits a cutter diameter less
    one step above Y0 (the cutter overhangs the fixed jaw, below the faced
    top), putting the first line one step into the bar, and its bottom
    ``passes`` steps below Y0, reaching at least FACE_OVERHANG_MM past the
    far edge. The plan must declare the engagement this posts."""
    reach = width + FACE_OVERHANG_MM
    passes = math.ceil(reach / woc - 1e-9)
    percent = math.ceil(100 * reach / (passes * dia) - 1e-9)
    step = percent * dia / 100
    if not math.isclose(step, woc, abs_tol=1e-3):
        raise ValueError(f"'{name}' radial_woc_mm {woc:.3f}: {passes} passes post {step:.3f} mm engagements "
                         f"(StepOver {percent}% of the {dia:.3f} mm cutter); declare that width")
    return {"passes": passes, "woc": step, "y": (-passes * step, dia - step)}


def context(features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str) -> dict[str, Any]:
    f = features["features"]
    x0 = f["bar_spindle_end"]["plane"]["value"]
    y_low = f["bar_low_side"]["plane"]["value"]
    z_under = f["underside_seat"]["plane"]["value"]
    length = f["bar_far_end"]["plane"]["value"] - x0
    width = f["bar_high_side"]["plane"]["value"] - y_low
    thick = f["top_seat"]["plane"]["value"] - z_under
    p = plan["parameters"]
    blank = (p["blank_length_in"] * IN, p["blank_width_in"] * IN, p["blank_thickness_in"] * IN)
    # Side 1 faces at a fixed Z, half the nominal allowance off: the operator
    # types nothing per bar. The plan's blank-thickness band must then clean up
    # there and stay within the depth of cut the plan's face cuts were checked
    # at; side 2 takes the rest.
    side1 = thick + (blank[2] - thick) / 2
    blank_min, blank_max = p["blank_thickness_min_in"] * IN, p["blank_thickness_max_in"] * IN
    side1_doc = _cut(plan, "side 1 face")["axial_doc_mm"]
    side2_doc = _cut(plan, "side 2 face")["axial_doc_mm"]
    if blank_min - side1 < FACE_SKIN_MIN_MM - 1e-6:
        raise ValueError(f"process.blank_thickness_min_in: side 1 faces at Z {side1:.3f}, so a {blank_min:.3f} mm blank "
                         f"loses only {blank_min - side1:.3f} mm there (< {FACE_SKIN_MIN_MM} mm): it may not clean up")
    if blank_max - side1 > side1_doc + 1e-6:
        raise ValueError(f"process.blank_thickness_max_in: side 1 faces at Z {side1:.3f}, so a {blank_max:.3f} mm blank "
                         f"is cut {blank_max - side1:.3f} mm deep, past the 'side 1 face' cut's {side1_doc:.3f} mm")
    if not math.isclose(side1 - thick, side2_doc, abs_tol=1e-3):
        raise ValueError(f"'side 2 face' axial_doc_mm {side2_doc:.3f} is not the {side1 - thick:.3f} mm side 2 cuts")
    x_trim = (blank[0] - length) / 2  # blank centred: equal trim at each end
    y_trim = (blank[1] - width) / 2
    # The faces overhang the bar's edges (FACE_OVERHANG_MM), over the vise jaws:
    # the lower faced top (side 2, on the parallels) must stand above them.
    if p["parallel_height_mm"] + thick <= p["vise_jaw_height_mm"]:
        raise ValueError(f"faced top {p['parallel_height_mm'] + thick:.3f} mm above the vise bed is not above the "
                         f"{p['vise_jaw_height_mm']:.3f} mm jaws; the face overhang would cut them")

    def frame(point):  # model mm -> S3 WCS mm
        return (point[0] - x0, -(point[1] - y_low), thick - (point[2] - z_under))

    rail = sorted((v for v in f.values() if v["kind"] == "threaded_hole"), key=lambda v: v["at"][0])
    # S3 drills the rail holes at their manifest stations, which is only right
    # when the drawing holds those stations (a "station" requirement with
    # limits; owner ruling 2026-11-16 "Rail holes CNC at ±0.05 mm OK"). A REF
    # station means the plan transfers each hole from its own rail, so posting
    # at the nominal would drill off the real rail. The program set is fixed
    # (they are the task's declared targets), so the whole post is refused.
    ref = sorted(k for k, v in f.items() if v["kind"] == "threaded_hole" and "station" not in v["requirements"])
    if ref:
        raise ValueError(f"rail stations {ref} are REF in this manifest; S3 would drill at nominal, so nothing is posted")
    bracket = sorted((v for v in f.values() if v["kind"] == "hole"), key=lambda v: (v["at"][0], v["at"][1]))
    counterbores = [v for v in f.values() if v["kind"] == "counterbore"]
    if {c["parent"] for c in counterbores} != {k for k, v in f.items() if v["kind"] == "hole"}:
        raise ValueError("every bracket hole must carry one counterbore")
    slots = [f["near_slot"], f["far_slot"]]

    em_half = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    face_dia = _shop_tool(plan, shop, "face-mill")["diameter_mm"]
    cbore_em = _shop_tool(plan, shop, "counterbore")["diameter_mm"]
    rail_drill = _shop_tool(plan, shop, "rail-drill")["diameter_mm"]
    bracket_drill = _shop_tool(plan, shop, "bracket-drill")["diameter_mm"]
    spot_dia = _cut(plan, "spot R1–R4, B1–B2")["cutter_dia_mm"]
    spot_depth = CENTRE_DRILL["pilot_length_mm"] + (spot_dia - CENTRE_DRILL["pilot_mm"]) / 2 / math.tan(math.radians(30))
    edge_rpm, edge_feed = _setting(shop, "em-half-hss-6061-v11-wide")
    end_rpm, end_feed = _setting(shop, "em-half-hss-6061-v11-narrow")
    slot_rpm, slot_feed = _setting(shop, "basebar-slot-rough-6061-t6511")
    face_rpm, face_feed = _setting(shop, "basebar-trifly-6061-t6511")
    _, slot_plunge = _plunge_feed(plan, "S1–S2 corner plunges")
    spot_rpm, spot_feed = _plunge_feed(plan, "spot R1–R4, B1–B2")
    rail_rpm, rail_feed = _plunge_feed(plan, "R1–R4")
    bracket_rpm, bracket_feed = _plunge_feed(plan, "B1–B2")
    cbore_rpm, cbore_feed = _plunge_feed(plan, "B1–B2 counterbores")
    edge_step = _cut(plan, "front edge rough")["radial_woc_mm"]
    edge_finish = _cut(plan, "front edge finish")["radial_woc_mm"]
    left_step = _cut(plan, "left end to ZERO END")["radial_woc_mm"]
    right_step = _cut(plan, "right end to length")["radial_woc_mm"]
    faces = {key: _face_layout(width, face_dia, _cut(plan, name)["radial_woc_mm"], name)
             for key, name in (("face_side1", "side 1 face"), ("face_side2", "side 2 face"))}
    face_flutes = {_cut(plan, name)["flutes"] for name in ("side 1 face", "side 2 face")}
    if len(face_flutes) != 1:
        raise ValueError(f"'side 1 face' and 'side 2 face' disagree on the Tri Fly's flutes: {sorted(face_flutes)}")
    # Equal slot depth steps, none deeper than the plan's. FreeCAD steps down by
    # a fixed amount, so the equal step is rounded up at 1 µm: the last step
    # then lands on the final depth instead of adding a sliver level.
    slot_depth = thick + p["slot_breakthrough_in"] * IN
    slot_count = math.ceil(slot_depth / (p["slot_step_in"] * IN) - 1e-9)
    slot_step = math.ceil(slot_depth / slot_count * 1e6) / 1e6

    # Each slot depth step starts with a plunge at the cutter-centre corner
    # nearest that slot's jack (largest X, plan S3): the jacks carry the push.
    jacks = [(p[f"jack_{side}_x_in"] * IN, p[f"jack_{side}_y_in"] * IN) for side in ("left", "right")]

    def slot_geometry(slot):
        separation = sum(slot["separation"]) / 2
        a = frame(slot["at"])
        b = frame((slot["at"][0], slot["at"][1] + separation, slot["at"][2]))
        y = (min(a[1], b[1]), max(a[1], b[1]))
        jack = min(jacks, key=lambda j: abs(j[0] - a[0]))
        e = (slot["width_nominal"] - em_half) / 2  # cutter-centre offset inside the slot
        return {"x": a[0], "y": y, "width": slot["width_nominal"],
                "plunge": [a[0] + e, min(y, key=lambda v: abs(v - jack[1]))]}

    def holes(items):
        return [list(frame(v["at"])[:2]) for v in items]

    cbore = counterbores[0]
    # Tool numbers: places in the plan's tool list, less the saw (it cuts the
    # blanks off the mill). Setup 3's tools in operation order give each S3
    # file's tool changes; its first tool, the Tri Fly, is loaded and touched
    # off by hand before the file runs, so it has no M6.
    names = {t["id"]: t["name"] for t in plan["tools"]}
    numbers = {t["id"]: n for n, t in enumerate((t for t in plan["tools"] if t["id"] != "saw"), 1)}
    setup3 = next(s for s in plan["setups"] if any(op.get("tool") == "face-mill" for op in s.get("operations", ())))
    order: list[str] = []
    for op in setup3["operations"]:
        if op.get("tool") and (not order or order[-1] != op["tool"]):
            order.append(op["tool"])
    if order[0] != "face-mill":
        raise ValueError(f"Setup 3 starts with {order[0]!r}; its files start with the Tri Fly loaded")
    changes = order[1:]
    # The flip: the Tri Fly lifted, the spindle stopped, the bar turned over
    # end-for-end by hand; the side-2 face then restarts the spindle. Each stop's
    # instruction is a CNCjs %msg line, which CNCjs shows when the M0 pauses it
    # (a comment is stripped before sending and never shown).
    flip_gcode = [f"G0 Z{FLIP_LIFT_MM:.3f}", "M5",
                  "%msg PAUSE: SPINDLE STOPPED. UNCLAMP, FLIP THE BAR END-FOR-END, SIDE 1 DOWN, ZERO EDGE AT THE FIXED JAW,"
                  " CENTRED ON THE JAW MARKS, RE-CLAMP, JACKS TOUCHING, THEN CYCLE START", "M0"]
    # X0 by the touch probe: from beside the flipped bar's left end at
    # mid-thickness, seek it in +X, back off, touch it again slowly and set X0
    # the end trim inside it. The probe descends by G38.3, which stops on a
    # bar that is not where expected, and the G38.2 after it then alarms on
    # the tripped probe (FluidNC 3.7.8 MotionControl.cpp mc_probe_cycle,
    # ProbeFailInitial). The ball radius only moves the trim: ZERO END is cut
    # at X0 and every station is measured from it.
    ball = p["probe_ball_radius_mm"]
    probe_clear, probe_x0 = thick + TAP_CLEAR_MM, -(ball + x_trim)
    x_from, x_to = -x_trim - ball - PROBE_SEARCH_MM, -x_trim + PROBE_SEARCH_MM
    probe_gcode = [
        f"G0 Z{probe_clear:.3f}", f"G0 X{x_from:.3f} Y{-width / 2:.3f}",
        f"G38.3 Z{thick / 2:.3f} F{PROBE_SEEK_FEED:g}",
        f"G38.2 X{x_to:.3f} F{PROBE_SEEK_FEED:g}", f"G38.4 X{x_from:.3f} F{PROBE_SEEK_FEED:g}",
        f"G38.2 X{x_to:.3f} F{PROBE_TOUCH_FEED:g}",
        f"G10 L20 P1 X{probe_x0:.3f}",
        f"G38.4 X{probe_x0 - PROBE_SEARCH_MM:.3f} F{PROBE_SEEK_FEED:g}", f"G0 Z{probe_clear:.3f}",
    ]
    # The hand tap: the CNC stops over each rail hole, spindle off, at the
    # drills' R plane, for the tap to be turned in the spring tap guide.
    tap_clear, tap_z = thick + TAP_CLEAR_MM, thick + SAFE_MM
    tap_points = [[f"R{i}", x, y] for i, (x, y) in enumerate(holes(rail), 1)]
    tap_gcode = [f"G0 Z{tap_clear:.3f}"]
    for label, x, y in tap_points:
        tap_gcode += [f"G0 X{x:.3f} Y{y:.3f}", f"G0 Z{tap_z:.3f}",
                      f"%msg PAUSE: TAP {label} BY HAND IN THE SPRING TAP GUIDE, SPINDLE OFF, BACK THE TAP OUT, THEN CYCLE START",
                      "M0", f"G0 Z{tap_clear:.3f}"]
    return {
        "stem": STEM, "step": step_path, "comment": COMMENT,
        "model": {"origin": [x0, y_low, z_under + thick], "axes": [[1, 0, 0], [0, -1, 0], [0, 0, -1]]},
        "length": length, "width": width, "thick": thick, "side1": side1, "blank_max": blank_max,
        "blank": list(blank), "x_trim": x_trim, "y_trim": y_trim,
        "names": names, "numbers": numbers,
        "tool_changes": {
            "BB02_S3_bar1": [numbers[t] for t in changes],
            "BB03_S3_bar2": [numbers[t] for t in changes if t not in BAR1_ONLY],
        },
        "tools": {
            "em_half": em_half, "cbore": cbore_em,
            "rail_drill": rail_drill, "bracket_drill": bracket_drill, "centre_drill": CENTRE_DRILL,
        },
        "edge": {"rpm": edge_rpm, "feed": edge_feed, "step": edge_step, "finish": edge_finish,
                 "tip": p["edge_cut_tip_z_mm"], "stepdown": p["side_max_stepdown_mm"],
                 "offsets": _stations(y_trim, edge_step, edge_finish),
                 "levels": _levels(blank[2] - p["edge_cut_tip_z_mm"], p["side_max_stepdown_mm"])},
        "face": {"rpm": face_rpm, "feed": face_feed, "dia": face_dia, "flutes": face_flutes.pop(), "sides": faces},
        "ends": {"rpm": end_rpm, "feed": end_feed, "tip": p["end_cut_tip_z_mm"],
                 "stepdown": p["side_max_stepdown_mm"], "left_step": left_step, "right_step": right_step,
                 "left": _stations(x_trim, left_step), "right": _stations(x_trim, right_step),
                 "levels": _levels(thick - p["end_cut_tip_z_mm"], p["side_max_stepdown_mm"])},
        "slots": {"rpm": slot_rpm, "feed": slot_feed, "plunge": slot_plunge,
                  "step": slot_step, "breakthrough": p["slot_breakthrough_in"] * IN,
                  "items": [slot_geometry(s) for s in slots]},
        "spot": {"rpm": spot_rpm, "feed": spot_feed, "depth": spot_depth},
        "rail": {"rpm": rail_rpm, "feed": rail_feed, "dia": rail[0]["nominal_dia"], "centres": holes(rail)},
        "bracket": {"rpm": bracket_rpm, "feed": bracket_feed, "dia": bracket[0]["dia_nominal"], "centres": holes(bracket)},
        "cbore": {"rpm": cbore_rpm, "feed": cbore_feed, "dia": cbore["dia_nominal"], "depth": cbore["depth_ref"]},
        "tap": {"tool": numbers["tap"], "label": f"{names['tap']} in the spring tap guide", "setting": "SPINDLE STAYS OFF",
                "points": tap_points, "gcode": tap_gcode},
        "flip": {"tool": numbers["face-mill"], "label": names["face-mill"], "setting": "SPINDLE STAYS OFF",
                 "gcode": flip_gcode, "z": FLIP_LIFT_MM},
        "probe": {"tool": numbers["probe"], "label": names["probe"], "setting": "SPINDLE OFF - PROBE IN",
                  "gcode": probe_gcode, "x0": probe_x0},
        "drill_tip": p["drill_tip_z_mm"],
    }


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    L, W, T = ctx["length"], ctx["width"], ctx["thick"]
    r = ctx["tools"]["em_half"] / 2
    edge, ends, slots = ctx["edge"], ctx["ends"], ctx["slots"]
    bt = ctx["blank"][2]
    out: list[tuple[str, str, dict[str, Any]]] = [
        ("BB01_S2_edges_T1", "spindle", {"rpm": edge["rpm"]}),
        ("BB01_S2_edges_T1", "depth", {"z_min": -bt + edge["tip"]}),
        ("BB01_S2_edges_T1", "rapids_clear", {"z_top": 0.0}),
        ("BB01_S2_edges_T1", "air_feed", {"z_top": 0.0}),
        # Owner ruling 2026-11-16: edge 1 +X, edge 2 -X, so no pass returns.
        ("BB01_S2_edges_T1", "no_return", {"axis": "X", "span": L / 2}),
        # Front edge becomes ZERO EDGE: conventional, cutter +X (plan S2).
        ("BB01_S2_edges_T1", "side_passes", {"axis": "Y", "final": -r, "raw": -ctx["y_trim"] - r,
                                              "max_step": edge["step"], "finish": edge["finish"], "direction": 1.0,
                                              "span": L / 2, "below_z": 0.0, "max_stepdown": edge["stepdown"]}),
        ("BB01_S2_edges_T1", "side_passes", {"axis": "Y", "final": W + r, "raw": W + ctx["y_trim"] + r,
                                              "max_step": edge["step"], "finish": edge["finish"], "direction": -1.0,
                                              "span": L / 2, "below_z": 0.0, "max_stepdown": edge["stepdown"]}),
    ]
    face, side1, top1 = ctx["face"], ctx["side1"], ctx["blank_max"]
    # S3, one file per bar: checks per tool section (``PROGRAM@k``, the file
    # split at its M6 tool changes). The Tri Fly section faces both sides, the
    # flip between them; its stock top is the thickest blank. From the probe
    # on, the stock top is the faced thickness T.
    rail, bracket = ctx["rail"]["centres"], ctx["bracket"]["centres"]
    spot_z, through = T - ctx["spot"]["depth"], ctx["drill_tip"]
    faces = [("depth", {"z_min": T}), ("rapids_clear", {"z_top": top1}), ("air_feed", {"z_top": top1}),
             *(("face_passes", {"z": z, "y": (-W, 0.0), "max_engagement": face["sides"][key]["woc"],
                                "radius": face["dia"] / 2, "span": L / 2, "overhang": FACE_OVERHANG_MM})
               for key, z in (("face_side1", side1), ("face_side2", T))),
             # The flip: one stop, the spindle stopped, the Tri Fly lifted.
             ("pauses", {"z_top": top1, "count": 1, "spindle_off": True})]
    probed = [("probe_zero", {"axis": "X", "value": ctx["probe"]["x0"], "z_top": T}),
              ("rapids_clear", {"z_top": T}), ("air_feed", {"z_top": T})]

    def drilled(centres, z_bottom):
        points = [tuple(c) for c in centres]
        return [("holes", {"centres": points, "z_bottom": z_bottom}),
                ("rapids_clear", {"z_top": T, "open_holes": points}),
                ("vertical_below_top", {"z_top": T}),
                ("air_feed", {"z_top": T})]

    t1 = [("depth", {"z_min": ends["tip"]}), ("rapids_clear", {"z_top": T}), ("air_feed", {"z_top": T}),
          # Left end becomes ZERO END, cutter -Y; right end to length, cutter +Y.
          ("side_passes", {"axis": "X", "final": -r, "raw": -ctx["x_trim"] - r, "max_step": ends["left_step"],
                           "direction": -1.0, "span": W / 2, "below_z": T, "max_stepdown": ends["stepdown"]}),
          ("side_passes", {"axis": "X", "final": L + r, "raw": L + ctx["x_trim"] + r, "max_step": ends["right_step"],
                           "direction": 1.0, "span": W / 2, "below_z": T, "max_stepdown": ends["stepdown"]})]
    for slot in slots["items"]:
        # Cutter-centre envelope inside the slot: the arc-centre line widened by
        # e each side, its ends rounded by e about the arc centres.
        e = (slot["width"] - 2 * r) / 2
        t1.append(("bounds", {
            "window": ((slot["x"] - 3 * r, slot["x"] + 3 * r), (slot["y"][0] - 3 * r, slot["y"][1] + 3 * r)),
            "x": (slot["x"] - e, slot["x"] + e), "y": (slot["y"][0] - e, slot["y"][1] + e),
            "z_min": -slots["breakthrough"], "arc": "G2", "entry": tuple(slot["plunge"]), "z_top": T,
        }))
    tapped = [("pauses", {"z_top": T, "count": len(rail), "at": [tuple(c) for c in rail], "spindle_off": True}),
              ("rapids_clear", {"z_top": T}), ("air_feed", {"z_top": T})]
    for program, bar1 in (("BB02_S3_bar1", True), ("BB03_S3_bar2", False)):
        # (speeds, checks) per tool section, in file order.
        sections = [
            ([face["rpm"]], faces),
            ([], probed),
            # Ends at 2250, then an M0 stop to set the knob to the slots' 1250.
            ([ends["rpm"], slots["rpm"]], t1),
            ([ctx["spot"]["rpm"]], drilled(rail + bracket if bar1 else rail, spot_z)),
            ([ctx["rail"]["rpm"]], drilled(rail, through)),
            *([([ctx["bracket"]["rpm"]], drilled(bracket, through))] if bar1 else []),
            ([], tapped),
            *([([ctx["cbore"]["rpm"]], drilled(bracket, T - ctx["cbore"]["depth"]))] if bar1 else []),
        ]
        out += [
            (program, "tool_changes", {"z_top": T, "tools": ctx["tool_changes"][program]}),
            (program, "spindle", {"rpm": [speeds for speeds, _checks in sections]}),
            # The flip, the slots' speed stop and one stop per tapped hole.
            (program, "pauses", {"z_top": T, "count": 2 + len(rail)}),
        ]
        for k, (_speeds, checks) in enumerate(sections):
            out += [(f"{program}@{k}", check, kw) for check, kw in checks]
    return out


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job per
    operation group; returns {"ops": {operation key: operation, list of
    operations, or the manual tap section}}."""
    L, W, T = ctx["length"], ctx["width"], ctx["thick"]
    bl, _width, bt = ctx["blank"]
    xt, yt, side1, top1 = ctx["x_trim"], ctx["y_trim"], ctx["side1"], ctx["blank_max"]
    tl, names, numbers = ctx["tools"], ctx["names"], ctx["numbers"]
    cd = tl["centre_drill"]
    r = tl["em_half"] / 2
    clear = r + APPROACH_MM  # side passes run this far past the stock's ends
    s2_right = clear + SAW_ALLOWANCE_MM
    doc = rt.document()
    bar = rt.import_step(doc, "Bar", ctx["step"], ctx["model"]["origin"], ctx["model"]["axes"])

    def tool(key, cut, plunge, shape="endmill", dia=None, flutes=2, tip_angle=None):
        return rt.tool_controller(doc, names[key], numbers[key], shape, dia, cut["rpm"], cut["feed"], plunge,
                                  flutes=flutes, tip_angle=tip_angle)

    ops: dict[str, Any] = {}
    # S2 (X0 blank left end, Y0 finished front edge, bar at +Y, Z0 blank top).
    # The model is the finished bar lengthened past both blank ends, so each pass
    # plunges and leaves beside the blank. Level by level and station by
    # station, the front edge runs +X (Direction CCW round the model) and the
    # back edge -X: both conventional, each pass starting where the last ended.
    e = ctx["edge"]
    s2 = rt.job(doc, "BB01 S2 edges, 1-2-3 blocks + straps", [rt.box(doc, "S2_model", (-clear, bl + s2_right), (0, W), (-bt, 0))],
                ((0, bl), (-yt, W + yt), (-bt, 0)))
    em = tool("em-half", e, e["feed"], dia=tl["em_half"])
    m2 = rt.model(s2)
    edges = (("front", rt.straight_edge(m2, y=0, z=0)), ("back", rt.straight_edge(m2, y=W, z=0)))
    passes, top = [], 0.0
    for level in e["levels"]:
        for offset in e["offsets"]:
            for side, edge in edges:
                passes.append(rt.profile(s2, em, f"{side} edge Z{level:.3f} +{offset:.3f}", edge, "Outside", "CCW",
                                         top, level, top - level, clearance=STRAP_CLEARANCE_MM, safe=SAFE_MM, offset=offset))
        top = level
    ops["edges"] = passes
    # S3 (X0 ZERO END, Y0 ZERO EDGE, bar at -Y, Z0 the parallels' top). Faces:
    # zigzag along X; the face model runs a cutter diameter plus the approach
    # past each blank end, so every plunge and stepover link is clear of the
    # stock. Side 1's stock top is the thickest blank the plan allows.
    fc = ctx["face"]
    run = fc["dia"] + APPROACH_MM
    for key, label, height, stock_top in (("face_side1", "S3 face side 1", side1, top1), ("face_side2", "S3 face side 2", T, side1)):
        layout = fc["sides"][key]
        target = rt.job(doc, label, [rt.box(doc, f"{key}_model", (-xt - run, L + xt + run), tuple(layout["y"]), (0, height))],
                        ((-xt, L + xt), (-W, 0), (0, stock_top)))
        # Face plunge at half the cutting feed: a shop habit, not a plan or shop record.
        tc = tool("face-mill", fc, fc["feed"] / 2, dia=fc["dia"], flutes=fc["flutes"])
        ops[key] = rt.face(target, tc, label, rt.top_face(rt.model(target), height), stock_top, height, layout["woc"],
                           safe=stock_top + SAFE_MM)
    # After the side-2 face and the probe's X0, top at T. The ends cut along a
    # helper box as long as the bar is wide plus the approach each side; the
    # slots follow the bar's own loops. Ends and slots are separate jobs, one
    # per spindle speed, joined at an M0 stop.
    en, sl = ctx["ends"], ctx["slots"]
    ends_job = rt.job(doc, "S3 ends", [bar, rt.box(doc, "S3_ends", (0, L), (-W - clear, clear), (0, T))],
                      ((-xt, L + xt), (-W, 0), (0, T)))
    ends_tc = tool("em-half", en, en["feed"], dia=tl["em_half"])
    helper = rt.model(ends_job, 1)
    for key, x, stations in (("left_end", 0.0, en["left"]), ("right_end", L, en["right"])):
        edge = rt.straight_edge(helper, x=x, z=T)
        stepover = stations[0] / (len(stations) - 1) if len(stations) > 1 else 0.0
        group, top = [], T
        for level in (T + d for d in en["levels"]):
            group.append(rt.profile(ends_job, ends_tc, f"{key} Z{level:.3f}", edge, "Outside", "CCW", top, level, top - level,
                                    safe=T + SAFE_MM, passes=len(stations), stepover=stepover))
            top = level
        ops[key] = group
    s3_stock = ((0, L), (-W, 0), (0, T))  # squared to length from here on
    slots_job = rt.job(doc, "S3 slots after M0", [bar], s3_stock)
    slot_tc = tool("em-half", sl, sl["plunge"], dia=tl["em_half"])
    for key, slot in zip(("slot_near", "slot_far"), sl["items"]):
        loop = rt.inner_loop(rt.model(slots_job, 0), T, slot["x"], sum(slot["y"]) / 2)
        # Inside the slot, clockwise: conventional with a clockwise spindle.
        ops[key] = rt.profile(slots_job, slot_tc, f"Slot X{slot['x']:.2f}", loop, "Inside", "CW", T, -sl["breakthrough"],
                              sl["step"], safe=T + SAFE_MM, start_point=slot["plunge"])
    # Holes, same clamping and frame: one job per operation, each over the bar.
    sp, ra, br, cb = ctx["spot"], ctx["rail"], ctx["bracket"], ctx["cbore"]
    through = ctx["drill_tip"]
    for key, label, tool_key, cut, shape, dia, tip_angle, holes, final, peck in (
        ("spot_rail", "S3 spot rail holes", "spot", sp, "drill", cd["body_mm"], 60, (ra["dia"], ra["centres"]), T - sp["depth"], None),
        ("spot_bracket", "S3 spot bracket holes (bar 1)", "spot", sp, "drill", cd["body_mm"], 60, (br["dia"], br["centres"]), T - sp["depth"], None),
        ("drill_rail", "S3 drill rail holes thru", "rail-drill", ra, "drill", tl["rail_drill"], 118, (ra["dia"], ra["centres"]), through, tl["rail_drill"]),
        ("drill_bracket", "S3 drill bracket holes thru (bar 1)", "bracket-drill", br, "drill", tl["bracket_drill"], 118, (br["dia"], br["centres"]), through, tl["bracket_drill"]),
        ("counterbore", "S3 counterbore bracket holes (bar 1)", "counterbore", cb, "endmill", tl["cbore"], None, (cb["dia"], br["centres"]), T - cb["depth"], None),
    ):
        target = rt.job(doc, label, [bar], s3_stock)
        tc = tool(tool_key, cut, cut["feed"], shape=shape, dia=dia, flutes=None, tip_angle=tip_angle)
        ops[key] = rt.drill(target, tc, label, rt.holes(rt.model(target), *holes), T, final, T + SAFE_MM, peck=peck)
    # Manual sections, their G-code written by context(): the flip stop, the
    # probe's X0 and the hand-tap stops.
    ops["flip"], ops["probe_x0"], ops["tap"] = ctx["flip"], ctx["probe"], ctx["tap"]
    rt.generate(doc)
    return {"ops": ops}
