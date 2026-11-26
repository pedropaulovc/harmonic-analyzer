"""FreeCAD CAM recipe for MHA-DT-12, the cylinder gear: its teeth and its notch.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD with that context and checks the posted
G-code against :func:`expectations`. Every path is written here
(``rt.custom``): straight X passes at one Y, which a recipe states exactly.

Route (plan text in ``plan.toml``; route R2, owner ruling 2026-11-22): ten
reamed and faced blanks on the shop-made gang arbor, back faces toward its
shoulder, the stack's O.D. turned on the lathe; the arbor then in the BS-0
dividing head's 3-jaw (on its turned body) with the BS-0 tailstock in its
tail centre, on the PM-30MV's table, spindle along X. A disc cutter in the
vertical spindle lies flat at the stack's axis height and cuts on the
operator's side of the stack, one X pass a tooth space, the head indexed by
hand at an M0 between passes:

- GP01_first_space: one space, -X, ending past blank 1 with the cutter drawn
  back along Y to ``measure_park_y_mm`` (room to mike over the pins): run on
  space 1 and on space 61 (20 crank turns on) for the two-pin depth check,
  re-run deeper from a corrected G54 Y.
- GP02_teeth: feeds back to the depth along +Y past blank 1 (as every GP01
  run reaches it), then spaces 2-120, alternately +X and -X (each pass ends
  where the next begins; no form cutter is drawn back through a cut space),
  then the closure pass in space 1 again (120 indexes of 5 spaces on the
  15-hole circle are 40 crank turns: the plunger is back in space 1's hole).
  Y never moves between spaces: the axis's repeatability stays out of the
  space-to-space depth.
- GP03_notch: the slotting saw through space 1 to the notch's depth, -X to
  over blank 1's back face, then out along Y.

Work frame (G54), all three programs: X0 blank 1's back face (the arbor's
shoulder), +X toward the tailstock; Y0 the stack's tips on the operator's
side, +Y into the stack (the stack's axis at Y = R); Z0 the stack's axis.
Y0 is set by touching the tool's rim on the tips, so every Y the programs
command is the rim's reach into the stack; the tool's centre is its radius
behind it (the keep-out shapes are shifted by that radius).

Checks this recipe makes before any file is posted (Main's conditions,
2026-11-22): the tooth count and the index (count, plate circle, closure);
the plunge against the teeth's band; the depth budget in the depth check's
own measure, over two pins in opposite spaces less the O.D. (the blanks
with the least and the most arbor deflection, their spread and the
micrometer inside the acceptance); the runout budget (the journal's TIR on
the BS-0 from the body and blank 10's O.D., Setup 5's O.D. offset, the
arbor's fit in the bore) against the teeth's runout limit; the cutter and saw reach against the
BS-0 jaws; and the plan's derived numbers. Typed here, because no record
carries them: the bending of a stepped beam, the chip of a form cutter and
the spin-up dwell.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

STEM = "dt_cylinder_gear"
COMMENT = "MHA-DT-12 cylinder gear"
# Programs in order, each listing its operation keys; GP02 is a posted Job
# (its first pass) then a manual section (the index stops and the rest).
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("GP01_first_space", ("first_space",)),
    ("GP02_teeth", (("second_space",), ("other_spaces",))),
    ("GP03_notch", ("notch",)),
)
# No program loads its tool: each is touched off on the stack (Y0, and Z0 by
# the height gauge), not on the tool setter.
LOAD_FIRST_TOOL: tuple[str, ...] = ()
# The plan's tools the mill runs, numbered by their places in its tool list.
CAM_TOOLS = ("cutter", "saw")
IN = 25.4
# Seconds the spindle runs up after each restart before the cutter moves.
DWELL_S = 2
# Least room GP01's park leaves between the cutter's rim and the tips for the
# depth check: a 2-3 in micrometer's anvil and frame over the pin (1.50 in).
MEASURE_ROOM_MM = 38.1
# Shapes the tools must miss stand this high (every move is at Z0).
SHAPE_TOP_MM = 1000.0
# How far the tailstock and the chuck reach along X from their faces (any
# length past the tools' reach serves).
FAR_MM = 100.0
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# Load stations across each rim's face width for the per-blank deflection.
RIM_STATIONS = 10
# Inch plan numbers agree to half their last (.0001) digit.
IN_TOL = 0.00005
# One horsepower in in·lbf/min, and psi in MPa (unit power to specific
# cutting energy).
HP_IN_LBF_MIN = 396000.0
PSI_MPA = 0.00689475729


def _r(value: float) -> float:
    """A coordinate as the post prints it (3 places)."""
    return round(value + 0.0, 3)


def _agree(
    plan: dict[str, Any], key: str, value: float, tol: float = PLAN_TOL_MM
) -> None:
    stated = plan["parameters"][key]
    if not math.isclose(stated, value, abs_tol=tol):
        raise ValueError(f"process.{key} {stated:g}, the recipe computes {value:.4f}")


def _box(
    name: str, x: tuple[float, float], y: tuple[float, float], shift: float
) -> dict[str, Any]:
    """A shape in the frame with Y0 at the tips, shifted by the tool's radius
    (the programmed Y is the rim's, the tool's centre is ``shift`` behind)."""
    return {
        "name": name,
        "x": [x[0], x[1]],
        "y": [y[0] + shift, y[1] + shift],
        "z_top": SHAPE_TOP_MM,
    }


def _setting(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    """The shop settings record the plan's spindle operation with ``tool``
    names (every such operation names the same one)."""
    names = {
        op["settings"]
        for setup in plan["setups"]
        for op in setup.get("operations", ())
        if op.get("tool") == tool and op.get("speed_kind") == "spindle"
    }
    if len(names) != 1:
        raise ValueError(
            f"plan's {tool} operations name settings {sorted(names)}, expected one"
        )
    return shop["settings"][names.pop()]


def _index(teeth: int, head: dict[str, Any]) -> dict[str, Any]:
    """The BS-0's plate and spaces for ``teeth`` equal steps: the first plate
    circle (plates in order, circles smallest first) that holds the crank's
    fraction of a turn exactly, and the closure after ``teeth`` steps."""
    turn = Fraction(head["worm_ratio"], teeth)
    for plate, circles in sorted(head["plate_holes"].items()):
        for circle in sorted(circles):
            spaces = turn * circle
            if spaces.denominator == 1:
                total = int(spaces) * teeth
                if total % circle:
                    raise ValueError(
                        f"{teeth} steps of {spaces} on {circle} do not close"
                    )
                return {
                    "plate": plate,
                    "circle": circle,
                    "turns": int(turn),
                    "spaces": int(spaces) - int(turn) * circle,
                    "total_turns": total // circle,
                }
    raise ValueError(f"no plate circle divides {turn} turn exactly")


def _beam(
    sections: list[tuple[float, float, float]],
    fixed: float,
    pinned: float,
    modulus: float,
    steps: int = 2000,
) -> Any:
    """A stepped round beam fixed at ``fixed`` (the BS-0 jaws) and pinned at
    ``pinned`` (the tailstock centre): each section (start, end, diameter) in
    mm, ``modulus`` in MPa. Returns ``deflection(load_at, force)`` in mm under
    ``force`` (N) at ``load_at``: the cantilever's bending under the load and
    under the tail's reaction, integrated twice; the reaction makes the tail's
    deflection zero. The section stiffness and the tail's unit bending are
    computed once for every load station."""
    xs = [fixed + (pinned - fixed) * k / steps for k in range(steps + 1)]

    def inertia(x: float) -> float:
        for start, end, dia in sections:
            if start - 1e-9 <= x <= end + 1e-9:
                return math.pi * dia**4 / 64
        raise ValueError(f"no section at {x}")

    stiffness = [modulus * inertia(x) for x in xs]

    def cantilever(at: float) -> list[float]:
        curvature = [max(at - x, 0.0) / k for x, k in zip(xs, stiffness)]
        slope, deflection = [0.0], [0.0]
        for i in range(1, len(xs)):
            h = xs[i] - xs[i - 1]
            slope.append(slope[-1] + (curvature[i] + curvature[i - 1]) / 2 * h)
            deflection.append(deflection[-1] + (slope[i] + slope[i - 1]) / 2 * h)
        return deflection

    under_tail = cantilever(pinned)

    def deflection(load_at: float, force: float) -> float:
        under_load = cantilever(load_at)
        reaction = force * under_load[-1] / under_tail[-1]
        k = min(range(len(xs)), key=lambda i: abs(xs[i] - load_at))
        return force * under_load[k] - reaction * under_tail[k]

    return deflection


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    f = features["features"]
    p = plan["parameters"]
    teeth = f["teeth"]
    count = int(teeth["count"])
    plunge = tuple(teeth["plunge"])
    notch = tuple(f["notch"]["depth"])
    pitch = f["cam_face"]["thickness_nominal"]
    face = f["rim_face"]["face_width_nominal"]
    gang = p["gang"]
    rims_end = (gang - 1) * pitch + face
    stack_end = gang * pitch
    radius = p["stack_od_aim_mm"] / 2

    # The stack's O.D. aim inside the print's band, and the plan's band.
    od = tuple(teeth["dia"])
    if (
        not od[0]
        <= p["stack_od_min_in"] * IN
        < p["stack_od_max_in"] * IN
        <= od[1] + 1e-9
    ):
        raise ValueError("the stack's O.D. band leaves the print's")
    _agree(
        plan, "stack_od_aim_mm", (p["stack_od_min_in"] + p["stack_od_max_in"]) / 2 * IN
    )

    # The cutter: the #2 of the 48DP set, whose range holds the count (the
    # plan states the set's records; the test reads them against the
    # shop-equipment inventory). Sizes: the shop records' diameter_mm.
    lo, hi = p["cutter_member_teeth_min"], p["cutter_member_teeth_max"]
    if not lo <= count <= hi:
        raise ValueError(
            f"cutter #{teeth['cutter_number']} cuts {lo}-{hi}, not {count} teeth"
        )
    if (
        p["cutter_diametral_pitch"] != teeth["diametral_pitch"]
        or p["cutter_pressure_angle_deg"] != teeth["pressure_angle_deg"]
    ):
        raise ValueError("the cutter set's pitch or pressure angle is not the teeth's")
    cutter_r = shop["tools"]["gear-cutters-48dp-20pa"]["diameter_mm"] / 2
    saw_r = shop["tools"]["cylinder-notch-saw"]["diameter_mm"] / 2
    if p["saw_thickness_mm"] > f["notch"]["width_max"]:
        raise ValueError("the saw is wider than the notch's limit")

    # Speeds: the plan's settings records; the mill's range.
    machine = shop["machines"]["pm-30mv"]

    def speed(tool: str) -> tuple[float, float, dict[str, Any]]:
        s = _setting(plan, shop, tool)
        rpm = float(s["rpm"])
        if not any(lo <= rpm <= hi for lo, hi in machine["rpm_ranges"]):
            raise ValueError(f"{tool} at {rpm:g} rpm is outside the PM-30MV's ranges")
        return rpm, rpm * s["flutes"] * s["chip_load_mm_per_tooth"], s

    cutter_rpm, cutter_feed, cutter_setting = speed("cutter")
    saw_rpm, saw_feed, _saw_setting = speed("saw")

    # Index: worm and plates from machines.bs-0; the count from the teeth.
    index = _index(count, shop["machines"]["bs-0"])
    if index["total_turns"] != shop["machines"]["bs-0"]["worm_ratio"]:
        raise ValueError(
            f"{count} indexes are {index['total_turns']} turns, not one spindle turn"
        )
    setup = next(s for s in plan["setups"] if isinstance(s.get("indexing"), dict))
    if setup["indexing"].get("positions") != count:
        raise ValueError(
            f"the plan indexes {setup['indexing'].get('positions')} positions, the teeth are {count}"
        )

    # The plunge and the notch: the bands' middles.
    y_teeth = (plunge[0] + plunge[1]) / 2
    y_notch = (notch[0] + notch[1]) / 2
    _agree(plan, "plunge_aim_mm", y_teeth)
    _agree(plan, "notch_aim_mm", y_notch)

    # Pass ends: past the rims by the margin at the deepest limit's half chord.
    margin = p["pass_margin_mm"]
    half_cutter = math.sqrt(2 * cutter_r * plunge[1] - plunge[1] ** 2)
    half_saw = math.sqrt(2 * saw_r * notch[1] - notch[1] ** 2)
    x_start, x_end = rims_end + half_cutter + margin, -(half_cutter + margin)
    saw_start, saw_end = rims_end + half_saw + margin, 0.0
    _agree(plan, "cutter_x_start_mm", x_start)
    _agree(plan, "cutter_x_end_mm", x_end)
    _agree(plan, "saw_x_start_mm", saw_start)
    _agree(plan, "saw_x_end_mm", saw_end)
    # Neither tool reaches the BS-0 jaws (the standoff from the shoulder).
    for name, reach in (("cutter", x_end - cutter_r), ("saw", saw_end - saw_r)):
        if reach <= -p["standoff_mm"]:
            raise ValueError(
                f"the {name} reaches X{reach:.2f}, past the jaws at X{-p['standoff_mm']:.2f}"
            )
    # The saw's touch-off: raised half a space, on a tip. That crest stands
    # the tip's drop farther into +Y than the tangent at Z0 (Y0), so the rim,
    # a paper short of it, is at drop - paper.
    half_space = math.pi / count
    _agree(plan, "saw_touch_z_mm", radius * math.sin(half_space))
    _agree(
        plan, "saw_touch_y_mm", -(p["paper_mm"] - radius * (1 - math.cos(half_space)))
    )

    # Arbor (X from the shoulder): body to the jaws, journal, pilot, thread
    # (its first part the relief groove at the pilot's end).
    journal_end = p["journal_length_mm"]
    pilot_end = journal_end + p["pilot_length_mm"]
    relief_end = pilot_end + p["relief_width_mm"]
    tail = pilot_end + p["thread_length_mm"]
    if stack_end + p["collar_length_mm"] > tail:
        raise ValueError("the collar runs past the arbor's tail")
    if journal_end >= stack_end or journal_end < stack_end - pitch + face:
        raise ValueError("the journal must end inside blank 10's bore")
    if p["relief_width_mm"] < p["thread_pitch_mm"]:
        raise ValueError("the thread relief is narrower than one pitch")
    if (
        not p["relief_dia_mm"]
        < p["thread_minor_mm"]
        < p["thread_major_mm"]
        < p["pilot_dia_mm"]
    ):
        raise ValueError("relief < thread minor < major < pilot does not hold")
    # The nut clamps: at the thinnest stack the collar's outer face stands at
    # least two full threads past the relief, so the nut bears on the collar,
    # never on the pilot's shoulder or the run-out (the cone kit's
    # NUT_THREAD_MARGIN rule).
    collar_face_min = gang * f["cam_face"]["thickness"][0] + p["collar_length_mm"]
    nut_margin = collar_face_min - relief_end - 2 * p["thread_pitch_mm"]
    if nut_margin <= 0:
        raise ValueError(
            f"the nut cannot clamp the stack: collar face {collar_face_min:.3f} mm "
            f"is not two threads past the relief's end {relief_end:.3f} mm"
        )
    if pilot_end <= gang * f["cam_face"]["thickness"][1]:
        raise ValueError("the collar does not ride the pilot at the thickest stack")
    # prechips' beam (Setups 6 and 7): from the jaws to the tail centre.
    for setup in plan["setups"]:
        beam = setup.get("beam")
        if isinstance(beam, dict):
            span = [-p["standoff_mm"], tail]
            for key in ("extent_mm", "supports_mm"):
                if any(abs(a - b) > 0.01 for a, b in zip(beam[key], span)):
                    raise ValueError(
                        f"{setup['title']}: beam.{key} {beam[key]}, the arbor spans "
                        f"[{span[0]:.2f}, {span[1]:.2f}]"
                    )
    _agree(plan, "stack_stickout_mm", p["standoff_mm"] + tail)

    # Depth budget (Main's condition 1): the cut's peak force on the arbor at
    # its worst station along the rims, as a stepped beam fixed at the jaws
    # and pinned at the tailstock (the plan states prechips' constants).
    modulus = p["arbor_modulus_gpa"] * 1000
    _agree(
        plan,
        "beam_brass_equiv_dia_mm",
        p["journal_dia_min_mm"]
        * (p["arbor_modulus_gpa"] / p["brass_modulus_gpa"]) ** 0.25,
    )
    kc = p["brass_unit_power_hp_min_per_in3"] * HP_IN_LBF_MIN * PSI_MPA
    # The posted feed is the settings record's flutes × chip × rpm; a cutter
    # with fewer teeth (down to the plan's least accepted) takes a chip larger
    # by flutes / teeth at that feed: the budget is taken at that chip.
    if p["cutter_teeth_min"] > cutter_setting["flutes"]:
        raise ValueError(
            "the least accepted cutter has more teeth than the feed assumes"
        )
    chip = (
        2
        * cutter_setting["chip_load_mm_per_tooth"]
        * cutter_setting["flutes"]
        / p["cutter_teeth_min"]
        * math.sqrt(plunge[1] / (2 * cutter_r))
    )
    profile = (
        2 * plunge[1] / math.cos(math.radians(teeth["pressure_angle_deg"]))
        + math.pi * IN / teeth["diametral_pitch"] / 2
    )
    force = kc * chip * profile
    sections = [
        (-p["standoff_mm"], 0.0, p["body_dia_mm"]),
        (0.0, journal_end, p["journal_dia_min_mm"]),
        (journal_end, pilot_end, p["pilot_dia_mm"]),
        (pilot_end, relief_end, p["relief_dia_mm"]),
        (relief_end, tail, p["thread_minor_mm"]),
    ]

    # The arbor's deflection under the cut at each blank's rim: the same for
    # every space of a blank (the same cut), so it moves each blank's mean
    # depth, not the depth around it.
    bend = _beam(sections, -p["standoff_mm"], tail, modulus)

    def rim_deflection(blank: int) -> list[float]:
        x0 = (blank - 1) * pitch
        return [
            abs(bend(x0 + face * k / RIM_STATIONS, force))
            for k in range(RIM_STATIONS + 1)
        ]

    rims = {blank: rim_deflection(blank) for blank in range(1, gang + 1)}
    deep = min(rims, key=lambda b: min(rims[b]))
    shallow = max(rims, key=lambda b: max(rims[b]))
    if (deep, shallow) != (p["depth_deep_blank"], p["depth_shallow_blank"]):
        raise ValueError(
            f"the depth check's blanks are {deep} (deepest) and {shallow} "
            f"(shallowest), not {p['depth_deep_blank']} and {p['depth_shallow_blank']}"
        )
    deflection = max(rims[shallow])
    # Depth budget (Main's condition 1), in the depth check's own measure:
    # over two pins in opposite spaces less the O.D., the drawing's acceptance
    # (the stack's eccentricity on the head cancels across the diameter; it is
    # the tooth runout the drawing bounds, booked below). The reading moves
    # twice the depth. Window: the acceptance band less one micrometer
    # resolution at each end per reading (two readings, over pins and O.D.);
    # the deep and shallow blanks' expected spread fits inside it, the aim
    # centring it.
    resolution_in = shop["gauges"]["micrometers"]["resolution_mm"] / IN
    window = (
        p["pins_less_od_min_in"] + 2 * resolution_in,
        p["pins_less_od_max_in"] - 2 * resolution_in,
    )
    _agree(plan, "depth_window_min_in", window[0], IN_TOL)
    _agree(plan, "depth_window_max_in", window[1], IN_TOL)
    spread_in = 2 * (max(rims[shallow]) - min(rims[deep])) / IN
    _agree(plan, "depth_spread_in", math.ceil(spread_in * 1e4 - 1e-6) / 1e4, IN_TOL)
    if p["depth_spread_in"] >= window[1] - window[0]:
        raise ValueError(
            f"depth spread {p['depth_spread_in']:.4f} in does not fit the window "
            f"{window[0]:.4f}-{window[1]:.4f}"
        )
    # A shallow cut is corrected by the two readings' mean to mid-window;
    # readings no further apart than the stop then both land inside it, a
    # reading's resolution to spare at each end.
    mid = (window[0] + window[1]) / 2
    _agree(plan, "depth_aim_in", math.floor(mid * 1e4 + 0.5 + 1e-6) / 1e4, IN_TOL)
    stop = p["depth_spread_stop_in"]
    aim = p["depth_aim_in"]
    if not (
        2 * p["depth_spread_in"] <= stop
        and aim - stop / 2 >= window[0] + resolution_in
        and aim + stop / 2 <= window[1] - resolution_in
    ):
        raise ValueError(
            f"depth_spread_stop_in {stop:.4f} is not between twice the expected spread "
            f"{p['depth_spread_in']:.4f} and what the window {window[0]:.4f}-{window[1]:.4f} holds about {aim:.4f}"
        )
    depth_spread = p["depth_spread_in"] * IN
    # The space-1/space-61 index: 60 spaces is whole turns of the circle.
    half_turns = Fraction(shop["machines"]["bs-0"]["worm_ratio"], 2)
    if count % 2 or half_turns.denominator != 1:
        raise ValueError("the opposite space is not whole crank turns")
    _agree(plan, "opposite_turns", float(half_turns))
    # Runout budget (Main's condition 2): the teeth run true to the BS-0 axis;
    # the bore rides the journal. The journal's axis, a straight line (one
    # chucking with the body and the tail centre), is bounded at two places
    # Setup 6 indicates: the body beside the BS-0 jaws (its TIR there) and
    # blank 10's O.D. (its TIR, plus the O.D.'s own offset from the journal
    # left by Setup 5: the body's lathe-jaw TIR tapering to nothing at the
    # tail centre, its share at blank 10's near face). Between the two its
    # offset is at most the larger; then the arbor's fit in the largest bore.
    # The journal is turned to the reamed blanks (Setup 4), .3758 at least by
    # the micrometer; the bore is the reamer's, taken at the sheet's largest.
    fit = f["bore"]["dia"][1] - p["journal_dia_min_mm"]
    share = (tail - (stack_end - pitch)) / (tail + p["standoff_mm"])
    journal = max(p["mount_tir_max_mm"], p["mount_tir_max_mm"] * (1 + share))
    runout = journal + fit
    if runout > teeth["tooth_runout_tir_max"]:
        raise ValueError(
            f"runout budget {runout:.4f} mm exceeds {teeth['tooth_runout_tir_max']}"
        )
    if p["journal_dia_min_mm"] >= f["bore"]["dia"][0]:
        raise ValueError("the journal's least size does not enter the least bore")

    names = {t["id"]: t["name"] for t in plan["tools"]}
    numbers = {
        t["id"]: n
        for n, t in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    clear = p["clear_y_mm"]
    park = p["measure_park_y_mm"]
    if park > -MEASURE_ROOM_MM:
        raise ValueError(
            f"GP01 parks the cutter {-park:.2f} mm back from the tips: under the {MEASURE_ROOM_MM:g} mm "
            "the micrometer needs over the pin"
        )
    rpm_word = f"M3 S{cutter_rpm:g}"
    feed_word = f"F{cutter_feed:.2f}"

    def message(k: int) -> str:
        done = (k - 1) * index["spaces"]
        return (
            f"INDEX TO SPACE {k} OF {count}: {index['spaces']} SPACES ON THE {index['circle']}-HOLE CIRCLE OF PLATE "
            f"{index['plate']}, SAME CRANK DIRECTION; {done // index['circle']} TURNS {done % index['circle']} SPACES "
            "FROM SPACE 1. LOCK, THEN CYCLE START"
        )

    closure = (
        f"INDEX BACK TO SPACE 1: {index['spaces']} SPACES ON THE {index['circle']}-HOLE CIRCLE; THE PLUNGER DROPS IN "
        f"SPACE 1'S MARKED HOLE, {index['total_turns']} TURNS IN ALL. LOCK, THEN CYCLE START: THIS PASS CUTS NO CHIPS"
    )
    # GP02's passes: spaces 3-120 after the index stops (space 2 is its
    # posted first pass, the index to it made by hand after the depth check),
    # then space 1 again; the direction alternates from +X.
    messages = [message(k) for k in range(3, count + 1)] + [closure]
    ends = (_r(x_start), _r(x_end))
    lines: list[str] = []
    at = ends[0]  # space 2's pass ends at X start
    for text in messages:
        at = ends[1] if at == ends[0] else ends[0]
        lines += [
            "M5",
            f"%msg {text}",
            "M0",
            rpm_word,
            f"G4 P{DWELL_S}",
            f"G1 X{at:.3f} {feed_word}",
        ]
    if at != ends[1]:
        raise ValueError("GP02's closure pass does not end past blank 1")
    lines.append(f"G1 Y{clear:.3f} {feed_word}")

    # Frame: the gear model posed as blank 1 (model Z is X; model -Y the tips
    # on the operator's side, at Y0).
    frames = {
        "stack": {
            "origin": [0.0, -radius, 0.0],
            "axes": [[0, 0, 1], [0, 1, 0], [-1, 0, 0]],
        }
    }
    stock = ((0.0, pitch), (0.0, 2 * radius), (-radius, radius))

    def job(
        tool: str,
        dia: float,
        rpm: float,
        feed: float,
        key: str,
        label: str,
        gcode: list[str],
    ) -> dict[str, Any]:
        return {
            "tool": tool,
            "dia": dia,
            "shape": "slittingsaw",
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
            "frame": "stack",
            "label": label,
            "stock": stock,
            "ops": [[key, label, gcode]],
        }

    jobs = [
        job(
            "cutter",
            2 * cutter_r,
            cutter_rpm,
            cutter_feed,
            "first_space",
            "first space",
            [
                f"G0 Y{clear:.3f}",
                "G0 Z0.000",
                f"G0 X{ends[0]:.3f}",
                f"G4 P{DWELL_S}",
                f"G1 Y{_r(y_teeth):.3f} F{{feed}}",
                f"G1 X{ends[1]:.3f} F{{feed}}",
                f"G1 Y{park:.3f} F{{feed}}",
            ],
        ),
        job(
            "cutter",
            2 * cutter_r,
            cutter_rpm,
            cutter_feed,
            "second_space",
            "second space",
            [
                f"G1 X{ends[1]:.3f} Y{_r(y_teeth):.3f} Z0.000 F{{feed}}",
                f"G4 P{DWELL_S}",
                f"G1 X{ends[0]:.3f} F{{feed}}",
            ],
        ),
        job(
            "saw",
            2 * saw_r,
            saw_rpm,
            saw_feed,
            "notch",
            "notch",
            [
                f"G0 Y{clear:.3f}",
                "G0 Z0.000",
                f"G0 X{_r(saw_start):.3f}",
                f"G4 P{DWELL_S}",
                f"G1 Y{_r(y_notch):.3f} F{{feed}}",
                f"G1 X{_r(saw_end):.3f} F{{feed}}",
                f"G1 Y{clear:.3f} F{{feed}}",
            ],
        ),
    ]
    manual = {
        "other_spaces": {
            "tool": numbers["cutter"],
            "label": names["cutter"],
            "setting": f"SET SPINDLE TO {cutter_rpm:g} RPM",
            "gcode": lines,
        }
    }

    # Keep-outs, Y0 at the tips (axis at Y = radius), shifted by each tool's
    # radius. The tool lies at Z0; its arbor's nut and shoulder lie off Z0,
    # where the whole stack, collar, chuck and tailstock stand within their
    # radii of the axis.
    def shapes(depth_max: float, shift: float) -> list[dict[str, Any]]:
        chuck = p["bs0_chuck_dia_mm"] / 2
        collar = p["collar_dia_mm"] / 2
        tail_w = p["tailstock_half_width_mm"]
        return [
            _box(
                "the rims past the deepest limit",
                (0.0, rims_end),
                (depth_max, 2 * radius),
                shift,
            ),
            _box(
                "the cam bosses",
                (0.0, stack_end),
                (radius - p["boss_dia_mm"] / 2, radius + p["boss_dia_mm"] / 2),
                shift,
            ),
            _box(
                "the TL-04 collar, the nut and the arbor's tail",
                (stack_end, tail),
                (radius - collar, radius + collar),
                shift,
            ),
            _box(
                "the BS-0 tailstock (ASSUMED width)",
                (tail, tail + FAR_MM),
                (radius - tail_w, radius + tail_w),
                shift,
            ),
            _box(
                "the BS-0 chuck and jaws",
                (-p["standoff_mm"] - FAR_MM, -p["standoff_mm"]),
                (radius - chuck, radius + chuck),
                shift,
            ),
        ]

    def nut_shapes(shift: float) -> list[dict[str, Any]]:
        return [
            _box("the stack (any height)", (0.0, stack_end), (0.0, 2 * radius), shift),
            *shapes(0.0, shift)[2:],
        ]

    expect: list[list[Any]] = []
    top = radius  # the stack's top: every move is at Z0, below it
    for name, tool, rpm, depth, first, msgs, (a, b), tool_r, nut_r, depth_max in (
        (
            "GP01_first_space",
            "cutter",
            cutter_rpm,
            y_teeth,
            -1,
            [],
            ends,
            cutter_r,
            p["cutter_arbor_nut_dia_mm"] / 2,
            plunge[1],
        ),
        (
            "GP02_teeth",
            "cutter",
            cutter_rpm,
            y_teeth,
            1,
            messages,
            ends,
            cutter_r,
            p["cutter_arbor_nut_dia_mm"] / 2,
            plunge[1],
        ),
        (
            "GP03_notch",
            "saw",
            saw_rpm,
            y_notch,
            -1,
            [],
            (_r(saw_start), _r(saw_end)),
            saw_r,
            p["saw_arbor_cap_dia_mm"] / 2,
            notch[1],
        ),
    ):
        expect += [
            [name, "tool_changes", {"z_top": top, "tools": [], "loads_first": False}],
            [name, "spindle", {"rpm": [[rpm]]}],
            [name, "depth", {"z_min": 0.0}],
            [name, "air_feed", {"z_top": top}],
            [
                name,
                "indexed_passes",
                {
                    "ends": [a, b],
                    "y": _r(depth),
                    "first": first,
                    "messages": msgs,
                    "rapid_y_max": clear,
                },
            ],
            [name, "keep_out", {"radius": tool_r, "boxes": shapes(depth_max, tool_r)}],
            [name, "keep_out", {"radius": nut_r, "boxes": nut_shapes(tool_r)}],
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
        "budget": {
            "force_n": force,
            "deflection_mm": deflection,
            "depth_spread_mm": depth_spread,
            "runout_mm": runout,
            "index": index,
        },
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
            doc, f"Gear {key}", ctx["step"], frame["origin"], frame["axes"]
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
        )
        for key, label, lines in section["ops"]:
            ops[key] = rt.custom(target, tc, label, lines)
    ops.update(ctx["manual"])
    rt.generate(doc)
    return {"ops": ops}
