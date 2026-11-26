"""FreeCAD CAM recipe for MHA-MS-01, the measuring stick's graduated scale.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The stick's sizes, the
graduations (count, pitch, the 0 tick's station from the datum end, the three
tick lengths, the V angle, the width and depth limits) and the numerals
(depth, height, the stroke layers' names and ink box) come from the feature
export; the numerals' stroke centrelines from the DXFs the export names
(``cad/references``, the files the model itself is cut from); the blank, the
fixture bar, the tape, the levels and the engraving depths from ``plan.toml``
``[parameters]`` and ``milling_cuts``; the cutter's diameter, the speeds and
feeds and the vise from ``shop/``. Every path is written here
(``rt.custom``); tick stations are computed, never typed. Typed here, because
no record carries them: the safe and clearance heights, the passes' leads,
the placing tolerance of a bar set by rule, 6061's modulus and the model
probe's offsets.

Route (``plan.toml``): the vise grips a 12 in 6061 bar on edge, and MS01
faces its top. The blank is bonded to that top on tape and never clamped.
MS02 mills both ends and both edges with the 1/2 in end mill, level by
level, anticlockwise (the stick on the left of every pass: conventional
with M3), every pass entered in air, beside the blank and off the fixture
bar (the last levels reach the tape and the bar's top). MS03 engraves
the 101 graduations with the 30 degree V bit, each from off the ruled edge
inward; MS04 the numerals along their stroke centrelines.

Work frames (G54):
- MS01: X0 the bar's right end (the bar to -X), Y0 its rear face (on the
  fixed jaw; the bar to -Y), Z0 its top as bought.
- MS02 to MS04: X0 the datum end (the stick to -X), Y0 the blank's rear edge
  as bought, ``outline_trim_mm`` behind the plain edge (the stick to -Y, the
  ruled edge toward the operator), Z0 the ruled face. Model x runs with
  machine X; model y and z are reversed (the ruled face is model z 0, the
  engraving cut into +z). MS02 takes X0 from the raw end; before MS03 the
  traveler sets it again on the milled datum end.

The single hold (the stick is longer than the jaws) is checked in
:func:`context`: the bar's overhang past the jaws under the plan's screening
load, the seat under every graduation and numeral, the jaws' and the bar's
keep-outs in every program.

:func:`build` also probes the model: at every tick and every numeral stroke
the STEP solid must be cut where this recipe cuts and whole beside it, so a
wrong frame, a mirrored numeral or a misplaced half-division tick stops the
build.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

STEM = "ms_stick"
COMMENT = "MHA-MS-01 stick"
# Programs in order, each listing its operation keys (one FreeCAD Job each).
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("MS01_fixture_face", ("fixture_face",)),
    ("MS02_outline", ("outline",)),
    ("MS03_graduations", ("graduations",)),
    ("MS04_numerals", ("numerals",)),
)
# Every program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the tape, the saw, the files and the scrapers are not).
CAM_TOOLS = ("em-half", "engraver")
IN = 25.4
# R planes: real G0 brings the end mill down to SAFE_MM above the top and the
# engraving bit to ENGRAVE_SAFE_MM above the ruled face; moves between the
# end mill's passes run at CLEAR_MM. Nothing stands above the blank's top.
SAFE_MM = 1.0
ENGRAVE_SAFE_MM = 0.5
CLEAR_MM = 5.0
# Each end-mill pass starts and ends with the cutter this far clear of the
# raw blank; each tick starts with the bit's centre this far off the ruled
# edge.
PASS_LEAD_MM = 2.0
TICK_LEAD_MM = 0.75
# Keep-outs: each vise jaw's depth outward from the fixture bar.
JAW_DEPTH_MM = IN
# A bar centred by rule (the fixture along the jaws, the blank along the
# fixture) lies within this of its place.
PLACE_TOL_MM = 3.0
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.001
# 6061-T6: 10.2 million psi (Machinery's Handbook, Typical Elastic
# Properties; prechips materials.aluminum_6061 elastic_modulus_gpa 70.3).
E_6061_MPA = 70300.0
# The numerals' stroke layers (features.numerals.stroke_layers) are tracked
# DXFs here, in model millimetres (gen_ms_stick_numerals_dxf.py).
REFERENCES = Path(__file__).resolve().parents[2] / "references"
# Strokes whose ink boxes lie nearer than this along the stick are one numeral.
NUMERAL_SPLIT_MM = 1.0
# Coverage samples along the numerals' strokes are at most this far apart.
STROKE_SAMPLE_MM = 0.2
# The model probe: this far below the ruled face, and this far inside or
# beyond a tick's inner end.
PROBE_DEPTH_MM = 0.1
PROBE_END_MM = 0.15


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
    """(rpm, mm/min) of the shop setting the operation of ``cut`` names: its
    chip load times its flutes and speed, or its stated in/min. The setting
    must be for that operation's tool on the plan's material."""
    op, _record = _op_with_cut(plan, cut)
    record = shop["settings"][op["settings"]]
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == op["tool"])
    if record["tool"] != ref or record["material"] != plan["material_key"]:
        raise ValueError(
            f"'{cut}': settings.{op['settings']} is not for {ref} on {plan['material_key']}"
        )
    rpm = float(record["rpm"])
    if "chip_load_mm_per_tooth" in record:
        return rpm, rpm * record["flutes"] * record["chip_load_mm_per_tooth"]
    match = re.fullmatch(r"([\d.]+) in/min", record["feed"])
    if not match:
        raise ValueError(
            f"settings.{op['settings']}: feed {record['feed']!r} is not in/min"
        )
    return rpm, float(match.group(1)) * IN


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


def _same(plan: dict[str, Any], cut: str, key: str, value: float) -> None:
    """A milling cut's field the recipe cuts by."""
    stated = _cut(plan, cut, key)
    if not math.isclose(stated, value, abs_tol=1e-6):
        raise ValueError(f"'{cut}' {key} {stated:g} is not the recipe's {value:g}")


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


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The stick's sizes and engraving from the export, each checked against
    the frame the recipe assumes: zero end, plain edge and ruled face at model
    X0, Y0 and Z0; the datum end, the ruled edge and the back at their
    nominals; the engraving cut into +Z, the ticks open to the ruled edge and
    stationed from the datum end."""
    f = features["features"]

    def plane(name: str, axis: str) -> float:
        p = f[name]["plane"]
        if p["axis"] != axis:
            raise ValueError(f"{name}: expected a plane across model {axis.upper()}")
        return p["value"]

    if plane("zero_end", "x") or plane("plain_edge", "y") or plane("ruled_face", "z"):
        raise ValueError(
            "zero end, plain edge and ruled face: expected at model X0, Y0, Z0"
        )
    length, width, thick = (
        plane("datum_end", "x"),
        plane("ruled_edge", "y"),
        plane("back_face", "z"),
    )
    for name, key, value, origin in (
        ("zero_end", "length", length, "datum_end"),
        ("ruled_edge", "width", width, "plain_edge"),
        ("back_face", "thickness", thick, "ruled_face"),
    ):
        if not math.isclose(f[name][f"{key}_nominal"], value, abs_tol=1e-6):
            raise ValueError(
                f"{name}: the model's {value:.4f} is not its nominal {key}"
            )
        if f[name][f"{key}_from"] != origin:
            raise ValueError(f"{name}: {key} is not from {origin}")
    grads, numerals = f["graduations"], f["numerals"]
    up = [0.0, 0.0, 1.0]
    if (
        grads["axis"] != up
        or numerals["axis"] != up
        or grads["open_to"] != "ruled_edge"
        or grads["zero_station_from"] != "datum_end"
    ):
        raise ValueError(
            "graduations and numerals: expected cut into +Z, the ticks open to the ruled edge and stationed from the datum end"
        )
    if grads["v_angle_deg"] != numerals["v_angle_deg"]:
        raise ValueError(
            "graduations and numerals: one bit cuts both, their V angles differ"
        )
    return {
        "length": length,
        "width": width,
        "thick": thick,
        "thick_band": f["back_face"]["thickness"],
        "grads": grads,
        "numerals": numerals,
    }


def _ticks(grads: dict[str, Any], half_index: int) -> list[dict[str, Any]]:
    """Every graduation: its index from the 0, its station from the datum end,
    its kind and its length, from the declared count, pitch and 0 station."""
    count, per, pitch = grads["count"], grads["per_division"], grads["minor_pitch"]
    zero = grads["zero_station_nominal"]
    if (count - 1) % per:
        raise ValueError(f"{count} graduations are not whole divisions of {per}")
    if not grads["zero_station"][0] <= zero <= grads["zero_station"][1]:
        raise ValueError("the 0 tick's nominal station is outside its band")
    ten = zero - (count - 1) * pitch
    if not math.isclose(ten, grads["ten_station_ref"], abs_tol=1e-6):
        raise ValueError(
            f"the last tick's station {ten:.4f} is not the declared ten_station_ref {grads['ten_station_ref']:.4f}"
        )
    if 2 * half_index != per:
        raise ValueError(
            f"process.half_tick_index {half_index} is not halfway between the 0 and the 1 ({per} ticks apart)"
        )
    ticks = []
    for index in range(count):
        kind = (
            "full" if index % per == 0 else ("half" if index == half_index else "minor")
        )
        nominal = grads[f"{kind}_length_nominal"]
        low, high = grads[f"{kind}_length"]
        if not low <= nominal <= high:
            raise ValueError(f"{kind} tick length {nominal} is outside its band")
        ticks.append(
            {
                "index": index,
                "station": zero - index * pitch,
                "kind": kind,
                "length": nominal,
            }
        )
    return ticks


def _rings(path: Path) -> list[list[tuple[float, float]]]:
    """Every LWPOLYLINE's vertices in a stroke-layer DXF."""
    lines = path.read_text(encoding="ascii").splitlines()
    pairs = [
        (lines[i].strip(), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)
    ]
    rings: list[list[tuple[float, float]]] = []
    ring: list[tuple[float, float]] | None = None
    x = 0.0
    for code, value in pairs:
        if code == "0":
            ring = None
            if value == "LWPOLYLINE":
                ring = []
                rings.append(ring)
        elif ring is not None and code == "10":
            x = float(value)
        elif ring is not None and code == "20":
            ring.append((x, float(value)))
    return rings


def _strokes(
    numerals: dict[str, Any],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """The numerals' stroke centrelines in model XY. Each DXF ring is one
    straight stroke's outline at the face: a half-round about each end, so
    the middle of each half-round's two end vertices is that end of the
    centreline. The rings' ink box must be the export's ``x_span``/``y_span``."""
    rings = [
        ring for name in numerals["stroke_layers"] for ring in _rings(REFERENCES / name)
    ]
    if not rings:
        raise ValueError("the numerals' stroke layers hold no stroke")
    strokes = []
    for ring in rings:
        n = len(ring)
        if n < 6 or n % 2:
            raise ValueError(f"a stroke outline of {n} vertices is not two half-rounds")
        k = n // 2
        ends = []
        for a, b in ((ring[k], ring[n - 1]), (ring[0], ring[k - 1])):
            ends.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
        strokes.append((ends[0], ends[1]))
    for axis, key in ((0, "x_span"), (1, "y_span")):
        values = [p[axis] for ring in rings for p in ring]
        box = (min(values), max(values))
        if not all(
            math.isclose(a, b, abs_tol=1e-4) for a, b in zip(box, numerals[key])
        ):
            raise ValueError(
                f"the stroke layers' ink box {box[0]:.4f}..{box[1]:.4f} is not the export's {key} {numerals[key]}"
            )
    return strokes


def _numeral_groups(strokes: list) -> list[list]:
    """The strokes grouped by numeral, in order along the stick."""
    groups: list[list] = []
    reach = -math.inf
    for stroke in sorted(strokes, key=lambda s: (min(s[0][0], s[1][0]), s)):
        if min(stroke[0][0], stroke[1][0]) > reach + NUMERAL_SPLIT_MM:
            groups.append([])
        groups[-1].append(stroke)
        reach = max(reach, stroke[0][0], stroke[1][0])
    return groups


def _chains(strokes: list) -> list[list[tuple[float, float]]]:
    """One numeral's strokes joined end to end into as few paths as a greedy
    walk finds: each starts at an end where an odd number of unused strokes
    meet, or at the first end left, and follows unused strokes until none
    leaves."""

    def key(p: tuple[float, float]) -> tuple[float, float]:
        return (round(p[0], 4), round(p[1], 4))

    unused = [(key(p), key(q)) for p, q in strokes]
    chains = []
    while unused:
        degree: dict[tuple[float, float], int] = {}
        for a, b in unused:
            degree[a] = degree.get(a, 0) + 1
            degree[b] = degree.get(b, 0) + 1
        odd = sorted(k for k, d in degree.items() if d % 2)
        at = (odd or sorted(degree))[0]
        chain = [at]
        while True:
            index = next((i for i, s in enumerate(unused) if at in s), None)
            if index is None:
                break
            a, b = unused.pop(index)
            at = b if at == a else a
            chain.append(at)
        chains.append(chain)
    return chains


def _width(tip: float, depth: float, angle_deg: float) -> float:
    """A V groove's width at the face: the bit's flat tip plus its flanks."""
    return tip + 2 * depth * math.tan(math.radians(angle_deg / 2))


def _levels(
    depth: float, count: int, step: float, finish: float, limit: float, what: str
) -> list[float]:
    """Engraving depths, positive: ``count`` equal rough levels of ``step``,
    then the last ``finish`` to ``depth``."""
    if not math.isclose(step, (depth - finish) / count, abs_tol=1e-4):
        raise ValueError(
            f"{what}: {count} levels of {step:g} and a last {finish:g} do not make {depth:g}"
        )
    if step > limit + 1e-9 or finish > limit:
        raise ValueError(
            f"{what}: a level of {step:g} is over process.engrave_step_max_mm {limit:g}"
        )
    return [step * k for k in range(1, count + 1)] + [depth]


def _pass(points: tuple[tuple[float, float], ...], z: float) -> list[str]:
    """One end-mill pass at ``z``: a rapid to its first point at the clearance
    height, down to the R plane, a plunge there at the cutting feed, straight
    moves through the rest, and back up."""
    entry, *rest = points
    return [
        f"G0 X{_r(entry[0]):.3f} Y{_r(entry[1]):.3f}",
        f"G0 Z{SAFE_MM:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        *(f"G1 X{_r(q[0]):.3f} Y{_r(q[1]):.3f} F{{feed}}" for q in rest),
        f"G0 Z{CLEAR_MM:.3f}",
    ]


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    length, width = g["length"], g["width"]
    thick_min, thick_max = g["thick_band"]
    grads, numerals = g["grads"], g["numerals"]
    angle = grads["v_angle_deg"]

    # The vise and the fixture bar: the single hold.
    vise = shop["workholding"]["vise-pm-6"]
    for key, field in (
        ("vise_bed_height_mm", "bed_height_mm"),
        ("vise_jaw_height_mm", "jaw_height_mm"),
        ("vise_jaw_width_mm", "jaw_width_mm"),
    ):
        if p[key] != vise[field]:
            raise ValueError(f"process.{key} is not shop workholding.vise-pm-6.{field}")
    jaw_w = p["vise_jaw_width_mm"]
    bar_l, bar_w, bar_h = (
        p["fixture_length_mm"],
        p["fixture_width_mm"],
        p["fixture_height_mm"],
    )
    face = p["fixture_face_mm"]
    faced_h = bar_h - face
    _agree(plan, "fixture_faced_height_mm", faced_h)
    _agree(plan, "fixture_overhang_mm", (bar_l - jaw_w) / 2)
    _agree(plan, "fixture_clamp_end_mm", (bar_l + jaw_w) / 2)
    raw_proud = p["parallel_height_mm"] + bar_h - p["vise_jaw_height_mm"]
    proud = raw_proud - face
    _agree(plan, "fixture_raw_proud_mm", raw_proud)
    _agree(plan, "fixture_proud_mm", proud)
    _agree(plan, "fixture_grip_mm", p["vise_jaw_height_mm"] - p["parallel_height_mm"])
    if proud <= 0:
        raise ValueError("the fixture bar's faced top is not above the jaw tops")
    _agree(plan, "fixture_seat_start_mm", -(bar_l - length) / 2)
    _agree(plan, "fixture_seat_end_mm", length + (bar_l - length) / 2)
    blank_max = p["blank_length_max_mm"]
    blank_min = p["blank_length_in"] * IN
    if not math.isclose(blank_max, p["blank_length_max_in"] * IN, abs_tol=1e-6):
        raise ValueError(
            "process.blank_length_max_mm is not blank_length_max_in × 25.4"
        )
    if (bar_l - blank_max) / 2 < PLACE_TOL_MM + p["face_cutter_dia_mm"]:
        raise ValueError("the fixture bar's faced top does not carry the whole blank")

    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    r = em / 2
    if p["face_cutter_dia_mm"] != em:
        raise ValueError(
            "process.face_cutter_dia_mm is not the 1/2 in end mill's diameter"
        )
    rpm, feed = _setting(plan, shop, "outline")
    if _setting(plan, shop, "fixture face") != (rpm, feed):
        raise ValueError("'fixture face' runs at another setting than 'outline'")
    # The bar's overhang under the screening load at the farthest cut past a
    # jaw side: a cantilever F·a³/(3EI), bending down (the bar on edge) and
    # across (its 1/2 in thickness).
    arm = (blank_max - jaw_w) / 2 + 2 * PLACE_TOL_MM + r + PASS_LEAD_MM
    if arm > (bar_l - jaw_w) / 2 + PLACE_TOL_MM:
        raise ValueError("the farthest cut lies past the fixture bar's end")
    load = p["fixture_check_load_n"]
    bends = {
        "down": load * arm**3 / (3 * E_6061_MPA * bar_w * faced_h**3 / 12),
        "across": load * arm**3 / (3 * E_6061_MPA * faced_h * bar_w**3 / 12),
    }
    for way, bend in bends.items():
        if bend > p["fixture_deflection_max_mm"]:
            raise ValueError(
                f"the fixture bar's overhang bends {bend:.4f} mm {way} under {load:g} N, over process.fixture_deflection_max_mm"
            )

    # MS01: two passes along the bar's whole top, the first woc wide from the
    # rear face, the second the rest; both run past both ends.
    woc = p["fixture_face_woc_mm"]
    if not 0 < bar_w - woc <= woc < em:
        raise ValueError(
            "process.fixture_face_woc_mm: the two passes do not face the bar's top"
        )
    _same(plan, "fixture face", "cutter_dia_mm", em)
    _same(plan, "fixture face", "axial_doc_mm", face)
    _same(plan, "fixture face", "radial_woc_mm", woc)
    face_y = (r - woc, woc - bar_w - r)
    face_over = 2 * r - woc
    face_x = (r + PASS_LEAD_MM, -bar_l - r - PASS_LEAD_MM)
    face_lines = [
        f"G0 Z{CLEAR_MM:.3f}",
        f"G0 X{_r(face_x[0]):.3f} Y{_r(face_y[0]):.3f}",
        f"G0 Z{SAFE_MM:.3f}",
        f"G1 Z{_r(-face):.3f} F{{feed}}",
        f"G1 X{_r(face_x[1]):.3f} F{{feed}}",
        f"G1 Y{_r(face_y[1]):.3f} F{{feed}}",
        f"G1 X{_r(face_x[0]):.3f} F{{feed}}",
        f"G0 Z{CLEAR_MM:.3f}",
    ]

    # MS02: the outline. Z0 is the blank's top (the ruled face), so the tape
    # stack moves the bar under the stick, never the stick's back. Depth:
    # through the thickest bar into the stack, short of the bar even on the
    # thinnest stack; under the thinnest bar on the thinnest stack (the bar's
    # top highest) into the fixture's top by fixture_skim_max_mm at most.
    stack_min, stack_max = p["tape_stack_min_mm"], p["tape_stack_max_mm"]
    if not 0 < stack_min <= p["tape_stack_mm"] <= stack_max:
        raise ValueError(
            "process.tape_stack_mm is not inside tape_stack_min_mm..tape_stack_max_mm"
        )
    trim = p["outline_trim_mm"]
    depth = p["outline_depth_mm"]
    step = p["outline_step_mm"]
    rounds = p["outline_levels"]
    _agree(plan, "outline_depth_mm", thick_max + p["outline_breakthrough_mm"])
    if not math.isclose(depth, rounds * step, abs_tol=1e-6):
        raise ValueError(
            "process.outline_depth_mm is not outline_levels × outline_step_mm"
        )
    if not 0 < p["outline_breakthrough_mm"] <= stack_min:
        raise ValueError(
            "under the thickest bar the outline does not end in the thinnest tape stack"
        )
    skim = depth - (thick_min + stack_min)
    if skim > p["fixture_skim_max_mm"]:
        raise ValueError(
            f"under the thinnest bar on the thinnest stack the outline enters the fixture {skim:.3f} mm, over process.fixture_skim_max_mm"
        )
    front_max = p["blank_width_max_mm"] - width - trim
    front_min = p["blank_width_min_mm"] - width - trim
    if min(front_min, trim) <= 0:
        raise ValueError("an edge of the narrowest blank does not clean up")
    _agree(plan, "outline_radial_max_mm", max(trim, front_max))
    radial = p["outline_radial_max_mm"]
    surplus = blank_max - length - trim
    if blank_min - length - trim <= 0:
        raise ValueError("the zero end of the shortest blank does not clean up")
    if not math.isclose(
        2 * p["blank_scribe_in"],
        p["blank_length_in"] + p["blank_length_max_in"],
        abs_tol=1e-9,
    ):
        raise ValueError(
            "process.blank_scribe_in is not the middle of the blank's length band"
        )
    stations = math.ceil(surplus / trim - 1e-9)
    if stations != p["outline_end_stations"]:
        raise ValueError(
            f"process.outline_end_stations {p['outline_end_stations']}: the longest blank's zero end takes {stations} passes of process.outline_trim_mm"
        )
    _same(plan, "outline", "cutter_dia_mm", em)
    _same(plan, "outline", "axial_doc_mm", step)
    _same(plan, "outline", "radial_woc_mm", radial)
    _agree(plan, "bond_area_mm2", length * width, tol=0.01)
    jaw_top = -(thick_min + stack_min + proud)
    if -depth - jaw_top < p["jaw_clearance_min_mm"]:
        raise ValueError(
            "the outline's deepest pass is within process.jaw_clearance_min_mm of the jaw tops"
        )

    # Frame of MS02 to MS04 (model point p -> axes · (p - origin)): X0 the
    # datum end, Y0 the blank's rear edge, trim behind the plain edge, Z0 the
    # ruled face, model y and z reversed.
    frame = _frame([length, -trim, 0.0], [0, -1, 0], [0, 0, -1])
    plain_y, ruled_y = _to(frame, [0, 0, 0])[1], _to(frame, [0, width, 0])[1]
    zero_x = _to(frame, [0, 0, 0])[0]
    if not (
        math.isclose(plain_y, -trim)
        and math.isclose(ruled_y, -trim - width)
        and math.isclose(zero_x, -length)
    ):
        raise ValueError(
            "the stick's frame does not put the plain edge at Y−trim and the zero end at X−length"
        )
    # The frame values the traveler prints: the ruled edge's Y, and the X the
    # edge finder sets on the raw right end, trim outside X0.
    _agree(plan, "ruled_edge_y_mm", -ruled_y)
    _agree(plan, "datum_find_x_mm", p["edge_finder_radius_mm"] + trim)
    raw_x = (-length - surplus, trim)
    raw_y = (-p["blank_width_max_mm"], 0.0)
    # The fixture bar across: its rear face is the fence the blank's rear
    # edge is set against (Y0). The last levels reach the tape and, under a
    # thin blank, the bar's top, so every pass is entered clear of the bar
    # as well as of the blank: behind its rear face or in front of its
    # front face, where nothing stands at this height.
    if p["blank_width_max_mm"] > bar_w:
        raise ValueError("the widest blank overhangs the fixture bar's front face")
    out_x = (raw_x[1] + r + PASS_LEAD_MM, raw_x[0] - r - PASS_LEAD_MM)
    out_y = (r + PASS_LEAD_MM, -bar_w - r - PASS_LEAD_MM)
    end_x = [zero_x - r - trim * k for k in range(stations - 1, -1, -1)]
    front_pass_y, rear_pass_y, datum_pass_x = ruled_y - r, plain_y + r, r
    # Each pass: where it is entered, then the points it feeds through. The
    # edge passes feed across to their line before running along it.
    passes = (
        *(((x, out_y[0]), (x, out_y[1])) for x in end_x),
        ((out_x[1], out_y[1]), (out_x[1], front_pass_y), (out_x[0], front_pass_y)),
        ((datum_pass_x, out_y[1]), (datum_pass_x, out_y[0])),
        ((out_x[0], out_y[0]), (out_x[0], rear_pass_y), (out_x[1], rear_pass_y)),
    )
    out_levels = [_r(-step * k) for k in range(1, rounds + 1)]
    outline_lines = [f"G0 Z{CLEAR_MM:.3f}"]
    for z in out_levels:
        for points in passes:
            outline_lines += _pass(points, z)
    corners = ((zero_x, plain_y), (zero_x, ruled_y), (0.0, ruled_y), (0.0, plain_y))
    edge_points = [list(c) for c in corners]
    edge_points += [
        [_r(zero_x + 5.0 * k), y]
        for y in (plain_y, ruled_y)
        for k in range(1, int(length // 5.0) + 1)
    ]
    edge_points += [[x, _r((plain_y + ruled_y) / 2)] for x in (zero_x, 0.0)]

    # The engraving bit: its tip from the plan (the shop-equipment record's
    # tip width), its angle the drawing's V. A groove's width at the face
    # follows from its depth; each depth is held engrave_depth_margin_mm
    # inside every limit it meets.
    tip = p["engraver_tip_mm"]
    margin = p["engrave_depth_margin_mm"]
    e_rpm, e_feed = _setting(plan, shop, "graduations")
    if _setting(plan, shop, "numerals") != (e_rpm, e_feed):
        raise ValueError("'numerals' runs at another setting than 'graduations'")
    if not math.isclose(p["engrave_feed_per_min_mm"], e_feed, abs_tol=1e-6):
        raise ValueError(
            "process.engrave_feed_per_min_mm is not the engraving setting's feed"
        )
    if not math.isclose(p["engrave_slow_feed_per_min_mm"], e_feed / 2, abs_tol=1e-6):
        raise ValueError(
            "process.engrave_slow_feed_per_min_mm is not half the engraving setting's feed"
        )
    for cut in ("graduations", "numerals"):
        _same(plan, cut, "rpm", e_rpm)
        _same(plan, cut, "feed_mm_min", e_feed)
    tick_depth, tick_w = p["tick_depth_mm"], p["tick_width_mm"]
    _agree(plan, "tick_width_mm", _width(tip, tick_depth, angle))
    w_min, w_max = grads["width"]
    if not (
        tick_depth - margin >= grads["depth_min"]
        and _width(tip, tick_depth - margin, angle) >= w_min
        and _width(tip, tick_depth + margin, angle) <= w_max
        and thick_min - tick_depth - margin >= grads["floor_min"]
    ):
        raise ValueError(
            "process.tick_depth_mm is not process.engrave_depth_margin_mm inside the graduations' depth, width and floor limits"
        )
    finish = p["engrave_finish_mm"]
    limit = p["engrave_step_max_mm"]
    tick_levels = _levels(
        tick_depth,
        p["tick_rough_levels"],
        p["tick_rough_step_mm"],
        finish,
        limit,
        "graduations",
    )
    _agree(plan, "tick_rough_depth_mm", tick_depth - finish)
    _same(plan, "graduations", "cutter_dia_mm", tick_w)
    _same(plan, "graduations", "radial_woc_mm", tick_w)
    _same(plan, "graduations", "axial_doc_mm", p["tick_rough_step_mm"])

    ticks = _ticks(grads, p["half_tick_index"])
    pitch = grads["minor_pitch"]
    tick_out_y = _r(ruled_y - TICK_LEAD_MM)
    tick_z = [_r(-z) for z in tick_levels]
    seat = (
        p["fixture_seat_start_mm"] + PLACE_TOL_MM,
        p["fixture_seat_end_mm"] - PLACE_TOL_MM,
    )
    grad_lines = [f"G0 Z{CLEAR_MM:.3f}"]
    tick_paths = []
    for tick in ticks:
        x, _y, _z = _to(frame, [length - tick["station"], width, 0.0])
        if not seat[0] <= length - tick["station"] <= seat[1]:
            raise ValueError(
                f"tick {tick['index']} is not over the fixture bar's faced top"
            )
        x = _r(x)
        end_y = _r(ruled_y + tick["length"] - tick_w / 2)
        tick_paths.append(
            {
                "index": tick["index"],
                "kind": tick["kind"],
                "x": x,
                "end_y": end_y,
                "face_end_y": ruled_y + tick["length"],
            }
        )
        grad_lines += [f"G0 X{x:.3f} Y{tick_out_y:.3f}", f"G0 Z{ENGRAVE_SAFE_MM:.3f}"]
        for k, z in enumerate(tick_z):
            # The plunge is beside the stick, in air; only the last level's
            # pass runs at the slow feed.
            last = k == len(tick_z) - 1
            word = "{plunge}" if last else "{feed}"
            grad_lines += [
                f"G1 Z{z:.3f} F{{feed}}",
                f"G1 Y{end_y:.3f} F{word}",
                f"G0 Z{ENGRAVE_SAFE_MM:.3f}",
            ]
            if not last:
                grad_lines.append(f"G0 Y{tick_out_y:.3f}")
    grad_lines.append(f"G0 Z{CLEAR_MM:.3f}")

    # The numerals: the model's stroke centrelines, by numeral along the
    # stick, each numeral's strokes chained.
    num_depth, num_w = p["numeral_depth_mm"], p["numeral_width_mm"]
    _agree(plan, "numeral_width_mm", _width(tip, num_depth, angle))
    strokes = _strokes(numerals)
    groups = _numeral_groups(strokes)
    if len(groups) != (grads["count"] - 1) // grads["per_division"] + 1:
        raise ValueError(
            f"the stroke layers hold {len(groups)} numerals, not one per long tick"
        )
    cells = {
        round(
            max(q[0] for s in group for q in s) - min(q[0] for s in group for q in s), 4
        )
        for group in groups
    }
    if len(cells) != 1:
        raise ValueError(f"the numerals' heights differ: {sorted(cells)}")
    cell = cells.pop()
    h_min, h_max = numerals["height"]
    if not (
        num_depth - margin >= numerals["depth_min"]
        and cell + _width(tip, num_depth - margin, angle) >= h_min
        and cell + _width(tip, num_depth + margin, angle) <= h_max
        and thick_min - num_depth - margin >= numerals["floor_min"]
    ):
        raise ValueError(
            "process.numeral_depth_mm is not process.engrave_depth_margin_mm inside the numerals' depth, height and floor limits"
        )
    num_levels = _levels(
        num_depth,
        p["numeral_rough_levels"],
        p["numeral_rough_step_mm"],
        finish,
        limit,
        "numerals",
    )
    _same(plan, "numerals", "cutter_dia_mm", num_w)
    _same(plan, "numerals", "radial_woc_mm", num_w)
    _same(plan, "numerals", "axial_doc_mm", p["numeral_rough_step_mm"])
    # The drawing's gaps (sheet 4), as it dimensions them: along the stick
    # between a numeral's ink and its own long tick's flank, and across it
    # between the ink and that tick's end. Each stays numeral_gap_min_mm at
    # the widths this bit cuts; no other tick's ink comes that near, nor the
    # stick's edges.
    gap_min = p["numeral_gap_min_mm"]
    for index, group in enumerate(groups):
        xs = [q[0] for stroke in group for q in stroke]
        ys = [q[1] for stroke in group for q in stroke]
        ink_lo, ink_hi = min(xs) - num_w / 2, max(xs) + num_w / 2
        ink_top = max(ys) + num_w / 2
        for tick in ticks:
            x = length - tick["station"]
            along = max(ink_lo - (x + tick_w / 2), (x - tick_w / 2) - ink_hi)
            across = (width - tick["length"]) - ink_top
            own = tick["index"] == index * grads["per_division"]
            gap = min(along, across) if own else max(along, across)
            if gap < gap_min - 1e-9:
                raise ValueError(
                    f"numeral {index}'s ink comes {gap:.3f} mm from tick {tick['index']}'s, under process.numeral_gap_min_mm"
                )
        if not (
            seat[0] <= min(xs)
            and max(xs) <= seat[1]
            and gap_min <= ink_lo
            and ink_hi <= length - gap_min
            and gap_min <= min(ys) - num_w / 2
        ):
            raise ValueError(
                f"numeral {index} is off the stick's face or the fixture bar's faced top"
            )
    num_z = [_r(-z) for z in num_levels]
    num_lines = [f"G0 Z{CLEAR_MM:.3f}"]
    num_starts, num_samples, num_boxes, air = [], [], [], []
    reach = 0.0
    for index, group in enumerate(groups):
        xs = [_to(frame, [q[0], q[1], 0.0])[0] for s in group for q in s]
        ys = [_to(frame, [q[0], q[1], 0.0])[1] for s in group for q in s]
        ink_x = (min(xs) - num_w / 2, max(xs) + num_w / 2)
        ink_y = (min(ys) - num_w / 2, max(ys) + num_w / 2)
        # Beside, behind and in front of this numeral the face is kept.
        num_boxes += [
            _box(
                f"face left of numeral {index}",
                (reach if index else zero_x, ink_x[0]),
                (ruled_y, plain_y),
                0.0,
            ),
            _box(f"face behind numeral {index}", ink_x, (ink_y[1], plain_y), 0.0),
            _box(f"face in front of numeral {index}", ink_x, (ruled_y, ink_y[0]), 0.0),
        ]
        reach = ink_x[1]
        for chain in _chains(group):
            points = [[_r(v) for v in _to(frame, [q[0], q[1], 0.0])[:2]] for q in chain]
            num_starts.append(points[0])
            num_lines += [
                f"G0 X{points[0][0]:.3f} Y{points[0][1]:.3f}",
                f"G0 Z{ENGRAVE_SAFE_MM:.3f}",
            ]
            for k, z in enumerate(num_z):
                last = k == len(num_z) - 1
                word = "{plunge}" if last else "{feed}"
                num_lines.append(f"G1 Z{z:.3f} F{{plunge}}")
                num_lines += [f"G1 X{q[0]:.3f} Y{q[1]:.3f} F{word}" for q in points[1:]]
                num_lines.append(f"G0 Z{ENGRAVE_SAFE_MM:.3f}")
                if not last and points[-1] != points[0]:
                    num_lines.append(f"G0 X{points[0][0]:.3f} Y{points[0][1]:.3f}")
            for a, b in zip(points, points[1:]):
                n = max(1, math.ceil(math.dist(a, b) / STROKE_SAMPLE_MM))
                num_samples += [
                    [a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n]
                    for k in range(n + 1)
                ]
                air.append([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, -PROBE_DEPTH_MM])
    num_boxes.append(
        _box("face right of the last numeral", (reach, 0.0), (ruled_y, plain_y), 0.0)
    )
    num_lines.append(f"G0 Z{CLEAR_MM:.3f}")

    # The model probe (build): air on every tick's centreline just inside
    # its end and on every numeral stroke's middle; metal just beyond every
    # tick's end and half a pitch beside it.
    metal = []
    for path in tick_paths:
        inner = path["face_end_y"]
        air.append([path["x"], inner - PROBE_END_MM, -PROBE_DEPTH_MM])
        metal.append([path["x"], inner + PROBE_END_MM, -PROBE_DEPTH_MM])
        metal.append([path["x"] + pitch / 2, inner - PROBE_END_MM, -PROBE_DEPTH_MM])

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    em_tool = {
        "tool": "em-half",
        "dia": em,
        "shape": "endmill",
        "flutes": 3,
        "rpm": rpm,
        "feed": feed,
        "plunge": feed,
    }
    bit_tool = {
        "tool": "engraver",
        "dia": _shop_tool(plan, shop, "engraver")["diameter_mm"],
        "shape": "endmill",
        "flutes": 1,
        "rpm": e_rpm,
        "feed": e_feed,
        "plunge": e_feed / 2,
    }
    bar_stock = ((-bar_l, 0.0), (-bar_w, 0.0), (-bar_h, 0.0))
    blank_stock = (raw_x, raw_y, (-thick_max, 0.0))
    stick_stock = ((zero_x, 0.0), (ruled_y, plain_y), (-g["thick"], 0.0))
    jobs = [
        {
            **em_tool,
            "frame": "fixture",
            "label": "fixture face",
            "stock": bar_stock,
            "ops": [["fixture_face", "face the fixture bar's top", face_lines]],
        },
        {
            **em_tool,
            "frame": "stick",
            "label": "outline",
            "stock": blank_stock,
            "ops": [["outline", "ends and edges to size", outline_lines]],
        },
        {
            **bit_tool,
            "frame": "stick",
            "label": "graduations",
            "stock": stick_stock,
            "ops": [["graduations", "engrave the graduations", grad_lines]],
        },
        {
            **bit_tool,
            "frame": "stick",
            "label": "numerals",
            "stock": stick_stock,
            "ops": [["numerals", "engrave the numerals", num_lines]],
        },
    ]

    # Keep-outs. MS01: the jaws under the bar's middle, their tops below its
    # raw top. MS02 to MS04: the jaws anywhere along the bar (the blank is
    # set on it by rule), their tops below the thinnest blank on the thinnest
    # tape stack (the highest they stand under Z0).
    mid = -bar_l / 2
    bar_jaws = [
        _box(
            "fixed jaw",
            (mid - jaw_w / 2 - PLACE_TOL_MM, mid + jaw_w / 2 + PLACE_TOL_MM),
            (0.0, JAW_DEPTH_MM),
            -raw_proud,
        ),
        _box(
            "moving jaw",
            (mid - jaw_w / 2 - PLACE_TOL_MM, mid + jaw_w / 2 + PLACE_TOL_MM),
            (-bar_w - JAW_DEPTH_MM, -bar_w),
            -raw_proud,
        ),
    ]
    along = (
        p["fixture_seat_start_mm"] - length - surplus - PLACE_TOL_MM,
        p["fixture_seat_end_mm"] - length + PLACE_TOL_MM,
    )
    stick_jaws = [
        _box("fixed jaw", along, (0.0, JAW_DEPTH_MM), jaw_top),
        _box("moving jaw", along, (-bar_w - JAW_DEPTH_MM, -bar_w), jaw_top),
    ]
    stick_box = _box("the stick", (zero_x, 0.0), (ruled_y, plain_y), 0.0)
    bar_box = _box(
        "fixture bar below the skim",
        along,
        (-bar_w, 0.0),
        -(thick_min + stack_min + p["fixture_skim_max_mm"]),
    )
    floor = _box(
        "stock under the engraving",
        (zero_x, 0.0),
        (ruled_y, plain_y),
        -(thick_min - grads["floor_min"]),
    )
    # MS03: the face beyond every tick's inner end and between the ticks.
    land = tick_w
    tick_boxes = []
    for path, after in zip(tick_paths, [*tick_paths[1:], None]):
        x = path["x"]
        tick_boxes.append(
            _box(
                f"face beyond tick {path['index']}",
                (x - land, x + land),
                (path["face_end_y"], plain_y),
                0.0,
            )
        )
        if after is not None:
            tick_boxes.append(
                _box(
                    f"face between ticks {path['index']} and {after['index']}",
                    (x + land, after["x"] - land),
                    (ruled_y, plain_y),
                    0.0,
                )
            )
    tick_boxes.append(
        _box(
            "face left of the 0 tick",
            (zero_x, tick_paths[0]["x"] - land),
            (ruled_y, plain_y),
            0.0,
        )
    )
    tick_boxes.append(
        _box(
            "face right of the last tick",
            (tick_paths[-1]["x"] + land, 0.0),
            (ruled_y, plain_y),
            0.0,
        )
    )
    shortest = min(TICK_LEAD_MM + t["length"] - tick_w / 2 for t in ticks)

    def common(name: str, number: int, speed: float, z_min: float) -> list[list[Any]]:
        return [
            [
                name,
                "tool_changes",
                {"z_top": 0.0, "tools": [number], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[speed]]}],
            [name, "pauses", {"z_top": 0.0, "count": 0}],
            [name, "depth", {"z_min": _r(z_min)}],
            [name, "rapids_clear", {"z_top": 0.0}],
            [name, "air_feed", {"z_top": 0.0}],
        ]

    t1, t2 = numbers["em-half"], numbers["engraver"]
    expect: list[list[Any]] = []
    name = "MS01_fixture_face"
    expect += common(name, t1, rpm, -face)
    expect += [
        [
            name,
            "holes",
            {"centres": [[_r(face_x[0]), _r(face_y[0])]], "z_bottom": _r(-face)},
        ],
        [
            name,
            "face_passes",
            {
                "z": _r(-face),
                "y": [-bar_w, 0.0],
                "max_engagement": woc,
                "radius": r,
                "span": bar_l,
                "overhang": face_over,
            },
        ],
        [name, "keep_out", {"radius": r, "boxes": bar_jaws}],
    ]
    name = "MS02_outline"
    expect += common(name, t1, rpm, -depth)
    expect += [
        [
            name,
            "holes",
            {
                "centres": [[_r(q[0][0]), _r(q[0][1])] for q in passes],
                "z_bottom": _r(-depth),
            },
        ],
        [
            name,
            "side_passes",
            {
                "axis": "X",
                "final": _r(zero_x - r),
                "raw": _r(zero_x - r - surplus),
                "max_step": trim,
                "direction": -1.0,
                "span": -raw_y[0],
                "below_z": 0.0,
                "max_stepdown": step,
            },
        ],
        [
            name,
            "side_passes",
            {
                "axis": "Y",
                "final": _r(front_pass_y),
                "raw": _r(raw_y[0] - r),
                "max_step": radial,
                "direction": 1.0,
                "span": length,
                "below_z": 0.0,
                "max_stepdown": step,
            },
        ],
        [
            name,
            "side_passes",
            {
                "axis": "X",
                "final": _r(datum_pass_x),
                "raw": _r(raw_x[1] + r),
                "max_step": trim,
                "direction": 1.0,
                "span": -raw_y[0],
                "below_z": 0.0,
                "max_stepdown": step,
            },
        ],
        [
            name,
            "side_passes",
            {
                "axis": "Y",
                "final": _r(rear_pass_y),
                "raw": _r(raw_y[1] + r),
                "max_step": trim,
                "direction": -1.0,
                "span": length,
                "below_z": 0.0,
                "max_stepdown": step,
            },
        ],
        [
            name,
            "engagement",
            {
                "stock": [list(raw_x), list(raw_y), [-thick_max, 0.0]],
                "radius": r,
                "max_radial": radial,
                "min_length": 2 * r,
                "cut": "conventional",
            },
        ],
        [name, "cleared", {"points": edge_points, "radius": r, "z": _r(-depth)}],
        [name, "keep_out", {"radius": r, "boxes": [stick_box, bar_box, *stick_jaws]}],
    ]
    name = "MS03_graduations"
    expect += common(name, t2, e_rpm, -tick_depth)
    expect += [
        [
            name,
            "holes",
            {
                "centres": [[q["x"], tick_out_y] for q in tick_paths],
                "z_bottom": _r(-tick_depth),
            },
        ],
        [
            name,
            "side_passes",
            {
                "axis": "X",
                "final": tick_paths[-1]["x"],
                "raw": _r(tick_paths[0]["x"] - pitch),
                "max_step": pitch,
                "direction": 1.0,
                "span": _r(shortest - 0.05),
                "below_z": 0.0,
                "max_stepdown": limit,
            },
        ],
        [
            name,
            "cleared",
            {
                "points": [
                    [q["x"], y] for q in tick_paths for y in (tick_out_y, q["end_y"])
                ],
                "radius": 0.0,
                "z": _r(-tick_depth),
            },
        ],
        [
            name,
            "keep_out",
            {"radius": tick_w / 2, "boxes": [*tick_boxes, floor, *stick_jaws]},
        ],
    ]
    name = "MS04_numerals"
    expect += common(name, t2, e_rpm, -num_depth)
    expect += [
        [name, "holes", {"centres": num_starts, "z_bottom": _r(-num_depth)}],
        [name, "cleared", {"points": num_samples, "radius": 0.0, "z": _r(-num_depth)}],
        [
            name,
            "keep_out",
            {"radius": num_w / 2, "boxes": [*num_boxes, floor, *stick_jaws]},
        ],
    ]

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": {"stick": frame},
        "bar": [list(axis) for axis in bar_stock],
        "names": names,
        "numbers": numbers,
        "jobs": jobs,
        "manual": {},
        "expect": expect,
        "probe": {"air": air, "metal": metal},
        "ticks": tick_paths,
        "numerals": len(groups),
        "bends": bends,
    }


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    return [(program, check, kwargs) for program, check, kwargs in ctx["expect"]]


def probe(inside: Any, points: dict[str, list[list[float]]]) -> None:
    """The model is cut where the recipe cuts (``air``) and whole where it
    keeps the face (``metal``); ``inside`` tells whether a setup-frame point
    lies in the solid."""
    wrong = [f"metal at {p}" for p in points["air"] if inside(p)]
    wrong += [f"no metal at {p}" for p in points["metal"] if not inside(p)]
    if wrong:
        shown = "; ".join(wrong[:5])
        raise RuntimeError(
            f"the model is not engraved where the recipe engraves ({len(wrong)} of {len(points['air']) + len(points['metal'])} probes): {shown}"
        )


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job per
    program; returns {"ops": {operation key: operation}}."""
    doc = rt.document()
    frame = ctx["frames"]["stick"]
    stick = rt.import_step(doc, "Stick", ctx["step"], frame["origin"], frame["axes"])
    solid = stick.Shape
    probe(lambda p: solid.isInside(rt.FreeCAD.Vector(*p), 1e-6, True), ctx["probe"])
    models = {"stick": stick, "fixture": rt.box(doc, "Fixture bar", *ctx["bar"])}
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
    """What the as-machined report needs: the sawn brass blank bonded to the
    fixture bar, in the ``stick`` frame. Its length along X at the plan's
    sawn band (``blank_length_in``..``blank_length_max_in``), nominal the
    scribed ``blank_scribe_in``; X0 is ``outline_trim_mm`` inside its right
    end, so that end stays put. Across Y its rear edge at Y0 and the bar's
    nominal ``blank_width_in``; its thickness the bar's as supplied, never
    machined (the model's). MS01 faces the fixture bar, not the part. The
    engraving bit is a V of the plan's tip flat and the graduations' angle,
    which the jobs (a flat end mill of the shank) cannot describe."""
    p = inputs.plan["parameters"]
    g = _geometry(inputs.features)
    trim = p["outline_trim_mm"]
    lengths = {
        "nominal": p["blank_scribe_in"] * IN,
        "min": p["blank_length_in"] * IN,
        "max": p["blank_length_max_mm"],
    }
    shank = next(job["dia"] for job in ctx["jobs"] if job["tool"] == "engraver") / 2
    tip = p["engraver_tip_mm"] / 2
    flank = math.tan(math.radians(g["grads"]["v_angle_deg"] / 2))
    # The engraved bands in model coordinates (the stick frame's X is model
    # x less the length): the ticks from the ruled edge in to the longest
    # tick the drawing allows, half a pitch past the end ticks; the numerals'
    # ink box widened by half a stroke. The plan cuts both wider and deeper
    # than the model (plan.toml's FLAGGED note on the numerals' width): the
    # ticks tick_width_mm wide and tick_depth_mm deep, the middle of the
    # drawing's bands, against the modelled .016 MIN groove; the numerals
    # numeral_width_mm wide against the model's near-sharp 0.24 V, which the
    # bit's 0.1 tip cannot cut.
    grads, nums = g["grads"], g["numerals"]
    ticks = [t["x"] + g["length"] for t in ctx["ticks"]]
    pitch = grads["minor_pitch"]
    tick_w, num_w = p["tick_width_mm"], p["numeral_width_mm"]
    tick_box = [
        [min(ticks) - pitch / 2, max(ticks) + pitch / 2],
        [g["width"] - grads["half_length"][1] - tick_w / 2, g["width"]],
        [0.0, p["tick_depth_mm"]],
    ]
    num_box = [
        [nums["x_span"][0] - num_w / 2, nums["x_span"][1] + num_w / 2],
        [nums["y_span"][0] - num_w / 2, nums["y_span"][1] + num_w / 2],
        [0.0, p["numeral_depth_mm"]],
    ]
    v_bit = "MS03/MS04 engrave with the 30° V bit (owner's engraver, plan Setup 3)"
    expected = [
        {
            "name": "graduations wider and deeper than modelled",
            "kind": "gouge",
            "within": tick_box,
            "reason": f"{v_bit} {tick_w} wide and {p['tick_depth_mm']} deep, the middle of the drawing's bands; "
                      "the model's grooves are narrower (.016) and shallower",
            "max_mm": tick_w / 2,
        },
        {
            "name": "numerals wider than modelled",
            "kind": "gouge",
            "within": num_box,
            "reason": f"{v_bit} {num_w} wide; the model's strokes are a near-sharp 0.24 V the bit's tip cannot cut",
            "max_mm": num_w / 2,
        },
        {
            "name": "engraving slivers past the report's cap",
            "kind": "left",
            "within": tick_box,
            "reason": "slivers along the engraving, too many for the report to measure one by one; the largest, "
                      "which it measures, are under the noise line",
            # _as_machined.NOISE_MM: a sliver the report measures is never
            # explained here, only those past its region cap.
            "max_mm": 0.075,
        },
    ]
    return {
        "parts": {
            "": {
                "blank": {
                    "frame": "stick",
                    "box": [
                        [trim - lengths["nominal"], trim],
                        [-p["blank_width_in"] * IN, 0.0],
                        [-g["thick"], 0.0],
                    ],
                    "length": {"axis": "x", "keep": "max", "mm": lengths},
                },
                "expected": expected,
            }
        },
        "skip": {"MS01_fixture_face": "faces the fixture bar's top, not the stick"},
        "tools": {ctx["numbers"]["engraver"]: [[tip, 0.0], [shank, (shank - tip) / flank]]},
    }
