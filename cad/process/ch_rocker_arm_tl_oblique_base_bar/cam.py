"""Fusion CAM recipe for MHA-CH-06-TL-20, the oblique trammel base bar (bars 1 and 2).

``fusion_cam.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then sends
:func:`build` to Fusion with that context and checks the posted G-code against
:func:`expectations`. Nothing here types a part dimension: lengths, hole and
slot positions come from the manifest; blank size, cutter tip depths and step
sizes from ``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter diameters,
speeds and feeds from ``shop.toml``. A CAD change reaches the programs through
the re-exported manifest.

Setups follow ``plan.toml``: S2 edges on 1-2-3 blocks; S3 face (two
clampings), square the ends and mill the slots in the vise; S4 spot, drill and
counterbore. In S3 and S4 both bars sit ZERO END left, ZERO EDGE (the model's
low side) at the back jaw, model Z0 face up (bar 1 C'BORE SIDE, bar 2 RAIL
SIDE), so every through feature is shared and only the bracket programs are
bar 1 only. Tapping, sawing and deburring stay manual.

The CAM model frame is the setup WCS (G54): for S3c and S4,
``x' = x - x0``, ``y' = -(y - y_low)``, ``z' = -(z - z_underside)``.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ch_rocker_arm_tl_oblique_base_bar"
POST = "Grbl"  # Fusion library post description; GRBL has no tool changer anyway.
COMMENT = "MHA-CH-06-TL-20 oblique base bar"
# Each program holds one tool: Fusion Personal refuses to post a tool change.
PROGRAMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("BB01_S2_edges_T1", ("front_edge", "back_edge")),
    ("BB02_S3_face_side1_T2", ("face_side1",)),
    ("BB03_S3_face_side2_T2", ("face_side2",)),
    ("BB04_S3_ends_slots_T1", ("left_end", "right_end", "slot_near", "slot_far")),
    ("BB05_S4_spot_rail_T3_both", ("spot_rail",)),
    ("BB06_S4_spot_bracket_T3_bar1", ("spot_bracket",)),
    ("BB07_S4_drill29_rail_T4_both", ("drill_rail",)),
    ("BB08_S4_drill12_bracket_T5_bar1", ("drill_bracket",)),
    ("BB09_S4_cbore_T6_bar1", ("counterbore",)),
)
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included: the shop record names
# the tool, not its geometry.
CENTRE_DRILL = {"body_mm": 3 / 16 * IN, "pilot_mm": 5 / 64 * IN, "pilot_length_mm": 5 / 64 * IN}
# Strap studs and nuts stand above the bar in S2; their height is not recorded,
# so moves between the two edges clear the stock top by this much.
STRAP_CLEARANCE_MM = 60.0
# Fusion spreads radial roughing steps unevenly (one 0.264 pass where 0.254 was
# asked, 2026-11-16); the plan's steps are nominal hand-feed targets.
STEP_TOLERANCE = 1.05


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

    def frame(point):  # model mm -> S3c/S4 WCS mm
        return (point[0] - x0, -(point[1] - y_low), -(point[2] - z_under))

    rail = sorted((v for v in f.values() if v["kind"] == "threaded_hole"), key=lambda v: v["at"][0])
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
    edge_rpm, edge_feed = _setting(shop, "basebar-edge-6061-t6511")
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

    def slot_geometry(slot):
        separation = sum(slot["separation"]) / 2
        a = frame(slot["at"])
        b = frame((slot["at"][0], slot["at"][1] + separation, slot["at"][2]))
        return {"x": a[0], "y": (min(a[1], b[1]), max(a[1], b[1])), "width": slot["width_nominal"]}

    def holes(items):
        return [list(frame(v["at"])[:2]) for v in items]

    cbore = counterbores[0]
    return {
        "stem": STEM, "step": step_path, "post": POST, "comment": COMMENT,
        "model": {"origin": [x0, y_low, z_under], "axes": [[1, 0, 0], [0, -1, 0], [0, 0, -1]]},
        "length": length, "width": width, "thick": thick, "side1": side1,
        "blank": list(blank), "x_trim": x_trim, "y_trim": y_trim,
        "tools": {
            "em_half": em_half, "em_face": em_face, "cbore": cbore_em,
            "rail_drill": rail_drill, "bracket_drill": bracket_drill, "centre_drill": CENTRE_DRILL,
        },
        "edge": {"rpm": edge_rpm, "feed": edge_feed, "plunge": slot_plunge, "step": edge_step, "finish": edge_finish,
                 "steps": math.ceil((y_trim - edge_finish) / edge_step) + 1, "tip": p["edge_cut_tip_z_mm"]},
        "face": {"rpm": face_rpm, "feed": face_feed, "stepover": face_stepover},
        "ends": {"rpm": edge_rpm, "feed": edge_feed, "plunge": slot_plunge, "tip": p["end_cut_tip_z_mm"],
                 "left_step": left_step, "left_steps": math.ceil(x_trim / left_step) + 1,
                 "right_step": right_step, "right_steps": math.ceil(x_trim / right_step) + 1},
        "slots": {"rpm": slot_rpm, "feed": slot_feed, "plunge": slot_plunge,
                  "step": p["slot_step_in"] * IN, "breakthrough": p["slot_breakthrough_in"] * IN,
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
        # Front edge becomes ZERO EDGE: conventional, cutter +X (plan S2).
        ("BB01_S2_edges_T1", "side_passes", {"axis": "Y", "final": -r, "raw": -ctx["y_trim"] - r,
                                              "max_step": edge["step"] * STEP_TOLERANCE, "direction": 1.0,
                                              "span": L / 2, "below_z": 0.0}),
        ("BB01_S2_edges_T1", "side_passes", {"axis": "Y", "final": W + r, "raw": W + ctx["y_trim"] + r,
                                              "max_step": edge["step"] * STEP_TOLERANCE, "direction": -1.0,
                                              "span": L / 2, "below_z": 0.0}),
        ("BB02_S3_face_side1_T2", "spindle", {"rpm": ctx["face"]["rpm"]}),
        ("BB02_S3_face_side1_T2", "depth", {"z_min": ctx["side1"]}),
        ("BB02_S3_face_side1_T2", "rapids_clear", {"z_top": bt}),
        ("BB03_S3_face_side2_T2", "spindle", {"rpm": ctx["face"]["rpm"]}),
        ("BB03_S3_face_side2_T2", "depth", {"z_min": T}),
        ("BB03_S3_face_side2_T2", "rapids_clear", {"z_top": ctx["side1"]}),
        ("BB04_S3_ends_slots_T1", "spindle", {"rpm": ends["rpm"]}),
        ("BB04_S3_ends_slots_T1", "depth", {"z_min": -T + ends["tip"]}),
        ("BB04_S3_ends_slots_T1", "rapids_clear", {"z_top": 0.0}),
        # Left end becomes ZERO END, cutter -Y; right end to length, cutter +Y.
        ("BB04_S3_ends_slots_T1", "side_passes", {"axis": "X", "final": -r, "raw": -ctx["x_trim"] - r,
                                                   "max_step": ends["left_step"] * STEP_TOLERANCE, "direction": -1.0,
                                                   "span": W / 2, "below_z": 0.0}),
        ("BB04_S3_ends_slots_T1", "side_passes", {"axis": "X", "final": L + r, "raw": L + ctx["x_trim"] + r,
                                                   "max_step": ends["right_step"] * STEP_TOLERANCE, "direction": 1.0,
                                                   "span": W / 2, "below_z": 0.0}),
    ]
    for slot in slots["items"]:
        e = (slot["width"] - 2 * r) / 2  # cutter-centre offset inside the slot
        out.append(("BB04_S3_ends_slots_T1", "bounds", {
            "window": ((slot["x"] - 3 * r, slot["x"] + 3 * r), (slot["y"][0] - 3 * r, slot["y"][1] + 3 * r)),
            "x": (slot["x"] - e, slot["x"] + e), "y": slot["y"],
            "z_min": -T - slots["breakthrough"], "arc": "G2",
        }))
    rail, bracket = ctx["rail"]["centres"], ctx["bracket"]["centres"]
    through = -T + ctx["drill_tip"]
    for program, rpm, centres, z in (
        ("BB05_S4_spot_rail_T3_both", ctx["spot"]["rpm"], rail, -ctx["spot"]["depth"]),
        ("BB06_S4_spot_bracket_T3_bar1", ctx["spot"]["rpm"], bracket, -ctx["spot"]["depth"]),
        ("BB07_S4_drill29_rail_T4_both", ctx["rail"]["rpm"], rail, through),
        ("BB08_S4_drill12_bracket_T5_bar1", ctx["bracket"]["rpm"], bracket, through),
        ("BB09_S4_cbore_T6_bar1", ctx["cbore"]["rpm"], bracket, -ctx["cbore"]["depth"]),
    ):
        out += [
            (program, "spindle", {"rpm": rpm}),
            (program, "holes", {"centres": [tuple(c) for c in centres], "z_bottom": z}),
            (program, "rapids_clear", {"z_top": 0.0, "open_holes": [tuple(c) for c in centres]}),
        ]
    return out


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside Fusion. Returns {operation key: operation}, plus the CAM object."""
    L, W, T = ctx["length"], ctx["width"], ctx["thick"]
    bl, bw, bt = ctx["blank"]
    xt, yt, side1 = ctx["x_trim"], ctx["y_trim"], ctx["side1"]
    doc, design = rt.new_design()
    part = rt.import_step(design, ctx["step"])
    bar = rt.in_frame(part, ctx["model"]["origin"], ctx["model"]["axes"])
    bodies = {
        "S2_model": rt.box((0, bl), (0, W), (-bt, 0)),
        "S2_stock": rt.box((0, bl), (-yt, W + yt), (-bt, 0)),
        "S3a_model": rt.box((-xt, L + xt), (-W, 0), (0, side1)),
        "S3a_stock": rt.box((-xt, L + xt), (-W, 0), (0, bt)),
        "S3b_model": rt.box((-xt, L + xt), (-W, 0), (0, T)),
        "S3b_stock": rt.box((-xt, L + xt), (-W, 0), (0, side1)),
        "S3c_model": bar,
        "S3c_stock": rt.box((-xt, L + xt), (-W, 0), (-T, 0)),
        "S4_model": rt.in_frame(part, ctx["model"]["origin"], ctx["model"]["axes"]),
        "S4_stock": rt.box((0, L), (-W, 0), (-T, 0)),
    }
    b = {name: rt.add_body(design, name, body) for name, body in bodies.items()}
    cam = rt.cam_product(doc)
    s = {
        key: rt.setup(cam, title, b[f"{key}_model"], b[f"{key}_stock"])
        for key, title in (
            ("S2", "S2 edges, 1-2-3 blocks + straps (X0 blank left end, Y0 finished front edge, Z0 blank top)"),
            ("S3a", "S3 face side 1, vise (Z0 underside)"),
            ("S3b", "S3 face side 2 after end-for-end flip (Z0 underside)"),
            ("S3c", "S3 ends + slots, vise (X0 ZERO END, Y0 ZERO EDGE, Z0 top)"),
            ("S4", "S4 holes, vise (X0 ZERO END, Y0 ZERO EDGE, Z0 top)"),
        )
    }
    tl = ctx["tools"]
    cd = tl["centre_drill"]
    em_half = rt.tool("flat end mill", 1, "1/2 in 2FL flat end mill", {"tool_diameter": tl["em_half"], "tool_shaftDiameter": tl["em_half"], "tool_fluteLength": 25.4, "tool_shoulderLength": 25.4, "tool_bodyLength": 31.75, "tool_overallLength": 76.2}, {"tool_numberOfFlutes": "2"})
    em_face = rt.tool("flat end mill", 2, "3/4 in 4FL flat end mill", {"tool_diameter": tl["em_face"], "tool_shaftDiameter": tl["em_face"], "tool_fluteLength": 25.4, "tool_shoulderLength": 25.4, "tool_bodyLength": 38.1, "tool_overallLength": 82.55}, {"tool_numberOfFlutes": "4"})
    centre = rt.tool("center drill", 3, "#2 centre drill", {"tool_diameter": cd["body_mm"], "tool_tipDiameter": cd["pilot_mm"], "tool_tipLength": cd["pilot_length_mm"], "tool_fluteLength": 5.08, "tool_bodyLength": 10.16, "tool_overallLength": 47.625})
    d_rail = rt.tool("drill", 4, "#29 drill", {"tool_diameter": tl["rail_drill"], "tool_fluteLength": 34.925, "tool_bodyLength": 40.64, "tool_overallLength": 63.5}, {"tool_tipAngle": "118"})
    d_bracket = rt.tool("drill", 5, "#12 drill", {"tool_diameter": tl["bracket_drill"], "tool_fluteLength": 44.45, "tool_bodyLength": 50.8, "tool_overallLength": 73.025}, {"tool_tipAngle": "118"})
    em_cbore = rt.tool("flat end mill", 6, "5/16 in 2FL flat end mill (counterbore)", {"tool_diameter": tl["cbore"], "tool_shaftDiameter": tl["cbore"], "tool_fluteLength": 19.05, "tool_shoulderLength": 19.05, "tool_bodyLength": 25.4, "tool_overallLength": 63.5}, {"tool_numberOfFlutes": "2"})

    ops = {}
    e = ctx["edge"]
    for key, name, y in (("front_edge", "Front edge -> ZERO EDGE", 0.0), ("back_edge", "Back edge to width", W)):
        op = rt.operation(s["S2"], "contour2d", em_half, name, e["rpm"], e["feed"], e["plunge"])
        rt.chain(op, [rt.straight_edge(b["S2_model"], y=y, z=-bt)], is_open=True)
        rt.set_params(op, {
            "compensation": "'right'",  # conventional: cutter +X on the front edge
            "doRoughingPasses": "true", "maximumStepover": f"{e['step']} mm", "maximumRoughingSteps": str(e["steps"]),
            "doMultipleFinishingPasses": "true", "numberOfFinishingStepovers": "1", "finishingStepover": f"{e['finish']} mm",
            "bottomHeight_offset": f"{e['tip']} mm", "doRamp": "false",
            "clearanceHeight_mode": "'from stock top'", "clearanceHeight_offset": f"{STRAP_CLEARANCE_MM} mm",
        })
        ops[key] = op
    fc = ctx["face"]
    for key, setup_key, name in (("face_side1", "S3a", "Face side 1"), ("face_side2", "S3b", "Face side 2 to thickness")):
        op = rt.operation(s[setup_key], "face", em_face, name, fc["rpm"], fc["feed"], fc["feed"] / 2)
        rt.set_params(op, {"stepover": f"{fc['stepover']} mm", "direction": "'conventional'", "passAngle": "0 deg"})
        ops[key] = op
    en = ctx["ends"]
    for key, name, x, step, steps in (
        ("left_end", "Left end -> ZERO END", 0.0, en["left_step"], en["left_steps"]),
        ("right_end", "Right end to length", L, en["right_step"], en["right_steps"]),
    ):
        op = rt.operation(s["S3c"], "contour2d", em_half, name, en["rpm"], en["feed"], en["plunge"])
        rt.chain(op, [rt.straight_edge(b["S3c_model"], x=x, z=-T)], is_open=True)
        rt.set_params(op, {
            "compensation": "'right'", "doRoughingPasses": "true", "maximumStepover": f"{step} mm",
            "maximumRoughingSteps": str(steps), "bottomHeight_offset": f"{en['tip']} mm", "doRamp": "false",
        })
        ops[key] = op
    sl = ctx["slots"]
    for key, slot in zip(("slot_near", "slot_far"), sl["items"]):
        op = rt.operation(s["S3c"], "contour2d", em_half, f"Slot X{slot['x']:.2f}", sl["rpm"], sl["feed"], sl["plunge"])
        loop = rt.inner_loop_at(b["S3c_model"], -T, slot["x"], sum(slot["y"]) / 2)
        # Reverted chain + right compensation: cutter inside the slot, clockwise.
        rt.chain(op, loop, is_open=False, reverted=True)
        rt.set_params(op, {
            "compensation": "'right'", "doMultipleDepths": "true", "maximumStepdown": f"{sl['step']} mm",
            "useEvenStepdowns": "true", "bottomHeight_offset": f"{-sl['breakthrough']} mm",
            "doRamp": "false", "doLeadIn": "false", "doLeadOut": "false",
        })
        ops[key] = op
    m4 = b["S4_model"]
    rail = rt.holes(m4, ctx["rail"]["dia"], ctx["rail"]["centres"])
    bracket = rt.holes(m4, ctx["bracket"]["dia"], ctx["bracket"]["centres"])
    cbores = rt.holes(m4, ctx["cbore"]["dia"], ctx["bracket"]["centres"])
    sp = ctx["spot"]
    spot = {"cycleType": "'drilling'", "bottomHeight_mode": "'from top'", "bottomHeight_offset": f"{-sp['depth']} mm"}
    ops["spot_rail"] = rt.drill(s["S4"], centre, "Spot rail holes (both bars)", sp["rpm"], sp["feed"], rail, spot)
    ops["spot_bracket"] = rt.drill(s["S4"], centre, "Spot bracket holes (bar 1)", sp["rpm"], sp["feed"], bracket, spot)
    tip = f"{ctx['drill_tip']} mm"
    ra, br, cb = ctx["rail"], ctx["bracket"], ctx["cbore"]
    ops["drill_rail"] = rt.drill(s["S4"], d_rail, "Drill #29 rail holes thru (both bars)", ra["rpm"], ra["feed"], rail,
                                 {"cycleType": "'chip-breaking'", "peckingDepth": f"{tl['rail_drill']} mm", "bottomHeight_offset": tip})
    ops["drill_bracket"] = rt.drill(s["S4"], d_bracket, "Drill #12 bracket holes thru (bar 1)", br["rpm"], br["feed"], bracket,
                                    {"cycleType": "'chip-breaking'", "peckingDepth": f"{tl['bracket_drill']} mm", "bottomHeight_offset": tip})
    ops["counterbore"] = rt.drill(s["S4"], em_cbore, "Counterbore bracket holes (bar 1)", cb["rpm"], cb["feed"], cbores,
                                  {"cycleType": "'drilling'"})
    rt.generate(cam)
    return {"cam": cam, "ops": ops}
