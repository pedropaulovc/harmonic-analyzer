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
the approach clearance, the drilling R plane and the facing plunge feed.

Setups follow ``plan.toml``: S2 edges on 1-2-3 blocks; S3 in the vise, one
clamping per bar from the side-2 face on (owner ruling 2026-11-16, "merge"):
face side 1, flip, face side 2, then without unclamping square the ends, mill
the slots, spot, drill and
counterbore. After the side-2 face both bars sit ZERO END left, ZERO EDGE (the
model's low side) at the back jaw, model Z0 face up (bar 1 C'BORE SIDE, bar 2
RAIL SIDE), so every through feature is shared and only the bracket programs
are bar 1 only. Tapping, sawing and deburring stay manual.

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
- Ends at the measured 2250 rpm (owner ruling 2026-11-16), slots at 1250.
  The PM-30MV's speed is set by hand on the knob and the tool and zeros do
  not change, so BB04 stays one program: the slots follow an operator
  comment and ``M0`` to reset the knob (owner: "why not single program with
  m0 for spindle/tool change"). A tool change stays a separate program.

Each program is one tool (GRBL has no tool changer) and one FreeCAD Job per
spindle speed. The CAM model frame is the setup WCS (G54): for S3c (S3 after
the side-2 face), ``x' = x - x0``, ``y' = -(y - y_low)``,
``z' = -(z - z_underside)``.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ch_rocker_arm_tl_oblique_base_bar"
COMMENT = "MHA-CH-06-TL-20 oblique base bar"
# Programs in order, each listing its operation keys; a key may name a list of
# operations (the edges' interleaved passes). A program whose keys are grouped
# in tuples is one section per group, each its own FreeCAD Job, joined at an
# M0 spindle-speed stop.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("BB01_S2_edges_T1", ("edges",)),
    ("BB02_S3_face_side1_T2", ("face_side1",)),
    ("BB03_S3_face_side2_T2", ("face_side2",)),
    ("BB04_S3_ends_slots_T1", (("left_end", "right_end"), ("slot_near", "slot_far"))),
    ("BB05_S3_spot_rail_T3_both", ("spot_rail",)),
    ("BB06_S3_spot_bracket_T3_bar1", ("spot_bracket",)),
    ("BB07_S3_drill29_rail_T4_both", ("drill_rail",)),
    ("BB08_S3_drill12_bracket_T5_bar1", ("drill_bracket",)),
    ("BB09_S3_cbore_T6_bar1", ("counterbore",)),
)
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
# Faces overhang the bar's front and back edges by this much, so a bar at the
# top of its width band or a ZERO EDGE edge-find error leaves no lip. The
# cutter then passes over the vise jaws, which stand below the faced top (the
# context checks it); 0.5 keeps the base bar at nine passes.
FACE_OVERHANG_MM = 0.5
# Plunges and drill pecks start this far above the stock top: real G0 brings
# the tool down to it, so only this much of each plunge is above the stock.
# FreeCAD measures each G83 peck from this R plane, so a higher one would
# also make the first peck feed through air.
SAFE_MM = 1.0


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
    side1 = thick + (blank[2] - thick) / 2  # side 1 takes half the facing allowance
    x_trim = (blank[0] - length) / 2  # blank centred: equal trim at each end
    y_trim = (blank[1] - width) / 2
    # The faces overhang the bar's edges (FACE_OVERHANG_MM), over the vise jaws:
    # the lower faced top (side 2, on the parallels) must stand above them.
    if p["parallel_height_mm"] + thick <= p["vise_jaw_height_mm"]:
        raise ValueError(f"faced top {p['parallel_height_mm'] + thick:.3f} mm above the vise bed is not above the "
                         f"{p['vise_jaw_height_mm']:.3f} mm jaws; the face overhang would cut them")

    def frame(point):  # model mm -> S3c WCS mm
        return (point[0] - x0, -(point[1] - y_low), -(point[2] - z_under))

    rail = sorted((v for v in f.values() if v["kind"] == "threaded_hole"), key=lambda v: v["at"][0])
    # BB05/BB07 drill the rail holes at their manifest stations, which is only
    # right when the drawing holds those stations (a "station" requirement with
    # limits; owner ruling 2026-11-16 "Rail holes CNC at ±0.05 mm OK"). A REF
    # station means the plan transfers each hole from its own rail, so posting
    # at the nominal would drill off the real rail. The program set is fixed
    # (they are the task's declared targets), so the whole post is refused.
    ref = sorted(k for k, v in f.items() if v["kind"] == "threaded_hole" and "station" not in v["requirements"])
    if ref:
        raise ValueError(f"rail stations {ref} are REF in this manifest; BB05/BB07 would drill at nominal, so nothing is posted")
    bracket = sorted((v for v in f.values() if v["kind"] == "hole"), key=lambda v: (v["at"][0], v["at"][1]))
    counterbores = [v for v in f.values() if v["kind"] == "counterbore"]
    if {c["parent"] for c in counterbores} != {k for k, v in f.items() if v["kind"] == "hole"}:
        raise ValueError("every bracket hole must carry one counterbore")
    slots = [f["near_slot"], f["far_slot"]]

    em_half = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    em_face = _shop_tool(plan, shop, "em-face")["diameter_mm"]
    cbore_em = _shop_tool(plan, shop, "counterbore")["diameter_mm"]
    rail_drill = _shop_tool(plan, shop, "rail-drill")["diameter_mm"]
    bracket_drill = _shop_tool(plan, shop, "bracket-drill")["diameter_mm"]
    spot_dia = _cut(plan, "spot R1–R4, B1–B2")["cutter_dia_mm"]
    spot_depth = CENTRE_DRILL["pilot_length_mm"] + (spot_dia - CENTRE_DRILL["pilot_mm"]) / 2 / math.tan(math.radians(30))
    edge_rpm, edge_feed = _setting(shop, "em-half-hss-6061-v11-wide")
    end_rpm, end_feed = _setting(shop, "em-half-hss-6061-v11-narrow")
    slot_rpm, slot_feed = _setting(shop, "basebar-slot-rough-6061-t6511")
    face_rpm, face_feed = _setting(shop, "basebar-face-6061-t6511")
    _, slot_plunge = _plunge_feed(plan, "S1–S2 corner plunges")
    spot_rpm, spot_feed = _plunge_feed(plan, "spot R1–R4, B1–B2")
    rail_rpm, rail_feed = _plunge_feed(plan, "R1–R4")
    bracket_rpm, bracket_feed = _plunge_feed(plan, "B1–B2")
    cbore_rpm, cbore_feed = _plunge_feed(plan, "B1–B2 counterbores")
    edge_step = _cut(plan, "front edge rough")["radial_woc_mm"]
    edge_finish = _cut(plan, "front edge finish")["radial_woc_mm"]
    left_step = _cut(plan, "left end to ZERO END")["radial_woc_mm"]
    right_step = _cut(plan, "right end to length")["radial_woc_mm"]
    face_stepover = _cut(plan, "side 1 face")["radial_woc_mm"]
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
    return {
        "stem": STEM, "step": step_path, "comment": COMMENT,
        "model": {"origin": [x0, y_low, z_under], "axes": [[1, 0, 0], [0, -1, 0], [0, 0, -1]]},
        "length": length, "width": width, "thick": thick, "side1": side1,
        "blank": list(blank), "x_trim": x_trim, "y_trim": y_trim,
        "tools": {
            "em_half": em_half, "em_face": em_face, "cbore": cbore_em,
            "rail_drill": rail_drill, "bracket_drill": bracket_drill, "centre_drill": CENTRE_DRILL,
        },
        "edge": {"rpm": edge_rpm, "feed": edge_feed, "step": edge_step, "finish": edge_finish,
                 "tip": p["edge_cut_tip_z_mm"], "stepdown": p["side_max_stepdown_mm"],
                 "offsets": _stations(y_trim, edge_step, edge_finish),
                 "levels": _levels(blank[2] - p["edge_cut_tip_z_mm"], p["side_max_stepdown_mm"])},
        "face": {"rpm": face_rpm, "feed": face_feed, "stepover": face_stepover},
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
        ("BB02_S3_face_side1_T2", "spindle", {"rpm": ctx["face"]["rpm"]}),
        ("BB02_S3_face_side1_T2", "depth", {"z_min": ctx["side1"]}),
        ("BB02_S3_face_side1_T2", "rapids_clear", {"z_top": bt}),
        ("BB02_S3_face_side1_T2", "air_feed", {"z_top": bt}),
        ("BB02_S3_face_side1_T2", "face_passes", {"z": ctx["side1"], "y": (-W - FACE_OVERHANG_MM, FACE_OVERHANG_MM), "max_stepover": ctx["face"]["stepover"],
                                                   "radius": ctx["tools"]["em_face"] / 2, "span": L / 2}),
        ("BB03_S3_face_side2_T2", "spindle", {"rpm": ctx["face"]["rpm"]}),
        ("BB03_S3_face_side2_T2", "depth", {"z_min": T}),
        ("BB03_S3_face_side2_T2", "rapids_clear", {"z_top": ctx["side1"]}),
        ("BB03_S3_face_side2_T2", "air_feed", {"z_top": ctx["side1"]}),
        ("BB03_S3_face_side2_T2", "face_passes", {"z": T, "y": (-W - FACE_OVERHANG_MM, FACE_OVERHANG_MM), "max_stepover": ctx["face"]["stepover"],
                                                   "radius": ctx["tools"]["em_face"] / 2, "span": L / 2}),
        # Ends at 2250, then an M0 stop to set the knob to the slots' 1250:
        # one S word per section, the tool retracted with an operator comment.
        ("BB04_S3_ends_slots_T1", "spindle", {"rpm": [ends["rpm"], slots["rpm"]]}),
        ("BB04_S3_ends_slots_T1", "pauses", {"z_top": 0.0, "count": 1}),
        ("BB04_S3_ends_slots_T1", "depth", {"z_min": -T + ends["tip"]}),
        ("BB04_S3_ends_slots_T1", "rapids_clear", {"z_top": 0.0}),
        ("BB04_S3_ends_slots_T1", "air_feed", {"z_top": 0.0}),
        # Left end becomes ZERO END, cutter -Y; right end to length, cutter +Y.
        ("BB04_S3_ends_slots_T1", "side_passes", {"axis": "X", "final": -r, "raw": -ctx["x_trim"] - r,
                                                   "max_step": ends["left_step"], "direction": -1.0,
                                                   "span": W / 2, "below_z": 0.0, "max_stepdown": ends["stepdown"]}),
        ("BB04_S3_ends_slots_T1", "side_passes", {"axis": "X", "final": L + r, "raw": L + ctx["x_trim"] + r,
                                                   "max_step": ends["right_step"], "direction": 1.0,
                                                   "span": W / 2, "below_z": 0.0, "max_stepdown": ends["stepdown"]}),
    ]
    for slot in slots["items"]:
        # Cutter-centre envelope inside the slot: the arc-centre line widened by
        # e each side, its ends rounded by e about the arc centres.
        e = (slot["width"] - 2 * r) / 2
        out.append(("BB04_S3_ends_slots_T1", "bounds", {
            "window": ((slot["x"] - 3 * r, slot["x"] + 3 * r), (slot["y"][0] - 3 * r, slot["y"][1] + 3 * r)),
            "x": (slot["x"] - e, slot["x"] + e), "y": (slot["y"][0] - e, slot["y"][1] + e),
            "z_min": -T - slots["breakthrough"], "arc": "G2", "entry": tuple(slot["plunge"]),
        }))
    rail, bracket = ctx["rail"]["centres"], ctx["bracket"]["centres"]
    through = -T + ctx["drill_tip"]
    for program, rpm, centres, z in (
        ("BB05_S3_spot_rail_T3_both", ctx["spot"]["rpm"], rail, -ctx["spot"]["depth"]),
        ("BB06_S3_spot_bracket_T3_bar1", ctx["spot"]["rpm"], bracket, -ctx["spot"]["depth"]),
        ("BB07_S3_drill29_rail_T4_both", ctx["rail"]["rpm"], rail, through),
        ("BB08_S3_drill12_bracket_T5_bar1", ctx["bracket"]["rpm"], bracket, through),
        ("BB09_S3_cbore_T6_bar1", ctx["cbore"]["rpm"], bracket, -ctx["cbore"]["depth"]),
    ):
        out += [
            (program, "spindle", {"rpm": rpm}),
            (program, "holes", {"centres": [tuple(c) for c in centres], "z_bottom": z}),
            (program, "rapids_clear", {"z_top": 0.0, "open_holes": [tuple(c) for c in centres]}),
            (program, "vertical_below_top", {"z_top": 0.0}),
            (program, "air_feed", {"z_top": 0.0}),
        ]
    return out


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job per
    program; returns {"ops": {operation key: operation or list of operations}}."""
    L, W, T = ctx["length"], ctx["width"], ctx["thick"]
    bl, _width, bt = ctx["blank"]
    xt, yt, side1 = ctx["x_trim"], ctx["y_trim"], ctx["side1"]
    tl = ctx["tools"]
    cd = tl["centre_drill"]
    r = tl["em_half"] / 2
    clear = r + APPROACH_MM  # side passes run this far past the stock's ends
    s2_right = clear + SAW_ALLOWANCE_MM
    doc = rt.document()
    bar = rt.import_step(doc, "Bar", ctx["step"], ctx["model"]["origin"], ctx["model"]["axes"])

    def half_inch(cut, plunge):
        return rt.tool_controller(doc, "1/2 in 2FL flat end mill", 1, "endmill", tl["em_half"], cut["rpm"], cut["feed"], plunge, flutes=2)

    ops: dict[str, Any] = {}
    # S2 (X0 blank left end, Y0 finished front edge, bar at +Y, Z0 blank top).
    # The model is the finished bar lengthened past both blank ends, so each pass
    # plunges and leaves beside the blank. Level by level and station by
    # station, the front edge runs +X (Direction CCW round the model) and the
    # back edge -X: both conventional, each pass starting where the last ended.
    e = ctx["edge"]
    s2 = rt.job(doc, "BB01 S2 edges, 1-2-3 blocks + straps", [rt.box(doc, "S2_model", (-clear, bl + s2_right), (0, W), (-bt, 0))],
                ((0, bl), (-yt, W + yt), (-bt, 0)))
    em = half_inch(e, e["feed"])
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
    # S3a/S3b (Z0 underside): zigzag along X. The face model runs a cutter
    # diameter plus the approach past each blank end, so every plunge and every
    # stepover link is clear of the stock.
    fc = ctx["face"]
    run = tl["em_face"] + APPROACH_MM
    for key, label, height, stock_top in (("face_side1", "BB02 S3 face side 1", side1, bt), ("face_side2", "BB03 S3 face side 2", T, side1)):
        target = rt.job(doc, label, [rt.box(doc, f"{key}_model", (-xt - run, L + xt + run), (-W - FACE_OVERHANG_MM, FACE_OVERHANG_MM), (0, height))],
                        ((-xt, L + xt), (-W, 0), (0, stock_top)))
        # Face plunge at half the cutting feed: a shop habit, not a plan or shop record.
        tc = rt.tool_controller(doc, "3/4 in 4FL flat end mill", 2, "endmill", tl["em_face"], fc["rpm"], fc["feed"], fc["feed"] / 2, flutes=4)
        ops[key] = rt.face(target, tc, label, rt.top_face(rt.model(target), height), stock_top, height, fc["stepover"],
                           safe=stock_top + SAFE_MM)
    # S3c (S3 after the side-2 face: X0 ZERO END, Y0 ZERO EDGE, bar at -Y, Z0
    # top). The ends cut along a helper box as long as the bar is wide plus the
    # approach each side; the slots follow the bar's own loops. Ends and slots
    # are separate jobs, one per spindle speed, joined in BB04 at an M0 stop.
    en, sl = ctx["ends"], ctx["slots"]
    ends_job = rt.job(doc, "BB04 S3 ends, vise", [bar, rt.box(doc, "S3c_ends", (0, L), (-W - clear, clear), (-T, 0))],
                      ((-xt, L + xt), (-W, 0), (-T, 0)))
    ends_tc = half_inch(en, en["feed"])
    helper = rt.model(ends_job, 1)
    for key, x, stations in (("left_end", 0.0, en["left"]), ("right_end", L, en["right"])):
        edge = rt.straight_edge(helper, x=x, z=0)
        stepover = stations[0] / (len(stations) - 1) if len(stations) > 1 else 0.0
        group, top = [], 0.0
        for level in en["levels"]:
            group.append(rt.profile(ends_job, ends_tc, f"{key} Z{level:.3f}", edge, "Outside", "CCW", top, level, top - level,
                                    safe=SAFE_MM, passes=len(stations), stepover=stepover))
            top = level
        ops[key] = group
    s3c_stock = ((0, L), (-W, 0), (-T, 0))  # squared to length from here on
    slots_job = rt.job(doc, "BB04 S3 slots after M0, vise", [bar], s3c_stock)
    slot_tc = half_inch(sl, sl["plunge"])
    for key, slot in zip(("slot_near", "slot_far"), sl["items"]):
        loop = rt.inner_loop(rt.model(slots_job, 0), 0.0, slot["x"], sum(slot["y"]) / 2)
        # Inside the slot, clockwise: conventional with a clockwise spindle.
        ops[key] = rt.profile(slots_job, slot_tc, f"Slot X{slot['x']:.2f}", loop, "Inside", "CW", 0.0, -T - sl["breakthrough"],
                              sl["step"], safe=SAFE_MM, start_point=slot["plunge"])
    # Holes, same clamping and frame: one job per program, each over the bar.
    sp, ra, br, cb = ctx["spot"], ctx["rail"], ctx["bracket"], ctx["cbore"]
    through = -T + ctx["drill_tip"]
    for key, label, tool, holes, final, peck in (
        ("spot_rail", "BB05 S3 spot rail holes (both bars)", (3, "#2 centre drill", "drill", cd["body_mm"], sp, 60), (ra["dia"], ra["centres"]), -sp["depth"], None),
        ("spot_bracket", "BB06 S3 spot bracket holes (bar 1)", (3, "#2 centre drill", "drill", cd["body_mm"], sp, 60), (br["dia"], br["centres"]), -sp["depth"], None),
        ("drill_rail", "BB07 S3 drill #29 rail holes thru (both bars)", (4, "#29 drill", "drill", tl["rail_drill"], ra, 118), (ra["dia"], ra["centres"]), through, tl["rail_drill"]),
        ("drill_bracket", "BB08 S3 drill #12 bracket holes thru (bar 1)", (5, "#12 drill", "drill", tl["bracket_drill"], br, 118), (br["dia"], br["centres"]), through, tl["bracket_drill"]),
        ("counterbore", "BB09 S3 counterbore bracket holes (bar 1)", (6, "5/16 in 2FL flat end mill (counterbore)", "endmill", tl["cbore"], cb, None), (cb["dia"], br["centres"]), -cb["depth"], None),
    ):
        number, name, shape, dia, cut, tip_angle = tool
        target = rt.job(doc, label, [bar], s3c_stock)
        tc = rt.tool_controller(doc, name, number, shape, dia, cut["rpm"], cut["feed"], cut["feed"], tip_angle=tip_angle)
        ops[key] = rt.drill(target, tc, label, rt.holes(rt.model(target), *holes), 0.0, final, SAFE_MM, peck=peck)
    rt.generate(doc)
    return {"ops": ops}
