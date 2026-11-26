"""FreeCAD CAM recipe for MHA-MG-06, the output fixture.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The hex, the rod
bore's station from the spigot face and its band come from the feature
export; the parallels, their ends, the bar's overhang past the jaws, the
spot and the drill's run past the lower corner from ``plan.toml``
``[parameters]`` and ``milling_cuts``; the F drill's size, speeds and feeds
from the shop (``shop/``). Every path is written here (``rt.custom``).
Typed here, because neither record carries them: the #2 centre drill's
catalogue geometry (it sets the spot depth), the twist drill's 118° point,
the safe and clearance heights and the vise jaws' depth (keep-out shapes
only).

Route (plan text in ``plan.toml``): the spigot, its groove and the axial
#4-40 are made on the lathe on the end of the 7/16 hex bar (Setup 1). The
bar then lies corner up along the vise jaws on two 1 in parallels, its
spigot end .50 in out past the jaws' left side, the parallels' left ends
stopping short of the bore: MO01 spots the top corner and drills F through
both corners into the air under the bar. The part is parted off the bar
afterwards (Setup 3), so the whole bar is gripped while it is drilled.

Work frame (G54), MO01: X0 the spigot face, +X along the bar away from it;
Y0 the hex axis (the turned spigot's, by the edge finder); Z0 the top corner.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "mg_output_fixture"
COMMENT = "MHA-MG-06 output fixture"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("MO01_cross_bore", (("corner_spot",), ("cross_drill",))),
)
# The program loads its own first tool (M6, the tool setter): the setup
# starts on whatever the mill last held.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the lathe's, the taps and the files are not).
CAM_TOOLS = ("spot", "drill-f")
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
# Drill R planes start this far above the top corner: real G0 brings the
# tool down to it.
SAFE_MM = 1.0
# Moves to and from the hole run this far above the jaw tops.
CLEAR_MM = 5.0
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
    """(rpm, mm/min) of the shop setting the operation holding ``cut`` names
    (its stated in/min feed). A cut that states its own rpm and feed must
    agree."""
    op, record_cut = _op_with_cut(plan, cut)
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
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


def _plunge(xy: list[float], tip: float, clear: float) -> list[str]:
    """One feed from the R plane above the top corner (Z0) to ``tip``; moves
    to and from the hole at ``clear``."""
    clear, r_plane = _r(clear), _r(SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(tip):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    f = features["features"]
    p = plan["parameters"]
    hex_, bore = f["hex"], f["rod_bore"]
    af = hex_["af_ref"]
    ac = 2 * af / math.sqrt(3)
    if hex_["axis"] != [1.0, 0.0, 0.0] or hex_["corner"] != [0.0, 1.0, 0.0]:
        raise ValueError("hex: expected along +X, its corners on ±Y")
    face_x = f["spigot_face"]["plane"]["value"]
    free_x = f["free_end"]["plane"]["value"]
    length = face_x - free_x
    if bore["axis"] != [0.0, 1.0, 0.0] or bore["at"][2] != 0 or not bore.get("thru"):
        raise ValueError(
            "rod_bore: expected through the corners, along Y, on the hex axis"
        )
    station = face_x - bore["at"][0]
    band = bore["face_station"]
    if not band[0] <= station <= band[1]:
        raise ValueError(
            f"rod_bore {station:.4f} from the spigot face is outside {band}"
        )
    if not math.isclose(-bore["at"][1], ac / 2, abs_tol=1e-3):
        raise ValueError("rod_bore: expected to enter at a corner")

    dF = _shop_tool(plan, shop, "drill-f")["diameter_mm"]
    if not bore["dia"][0] <= dF <= bore["dia"][1]:
        raise ValueError(f"F drill Ø{dF} outside the bore band {bore['dia']}")
    if not math.isclose(_cut(plan, "cross drill", "cutter_dia_mm"), dF, abs_tol=1e-4):
        raise ValueError("'cross drill' cutter_dia_mm is not the F drill's")
    spot_rpm, spot_feed = _setting(plan, shop, "corner spot")
    f_rpm, f_feed = _setting(plan, shop, "cross drill")
    if not math.isclose(
        _cut(plan, "corner spot", "cutter_dia_mm"),
        p["corner_spot_dia_mm"],
        abs_tol=1e-6,
    ):
        raise ValueError(
            "'corner spot' cutter_dia_mm is not process.corner_spot_dia_mm"
        )
    corner_spot = _spot_depth(p["corner_spot_dia_mm"])
    if p["corner_spot_dia_mm"] >= dF:
        raise ValueError("the corner spot is not under the F drill")
    for name in ("corner spot", "cross drill"):
        if not math.isclose(
            _cut(plan, name, "stations_mm"), station, abs_tol=PLAN_TOL_MM
        ):
            raise ValueError(
                f"'{name}' stations_mm is not the bore's station {station:.3f}"
            )

    # The bar corner up, its lower diagonal flats (30° from horizontal) on
    # the parallels' inner top edges: the gap between them af − 2 × their
    # thickness, the lower corner hanging that far below their tops.
    gap = af - 2 * p["parallel_thickness_mm"]
    drop = gap / 2 * math.tan(math.radians(30))
    corner_top = ac - drop  # the top corner above the parallels' tops
    cross_tip = -(ac + p["cross_drill_past_mm"] + _point(dF))
    grip = p["vise_jaw_height_mm"] - p["parallel_height_mm"]
    _agree(plan, "cross_grip_mm", grip)
    cross_jaw_top = grip - corner_top
    _agree(plan, "cross_jaw_top_mm", cross_jaw_top)
    _agree(plan, "cross_tip_height_mm", corner_top + cross_tip)
    clear = max(0.0, cross_jaw_top) + CLEAR_MM
    # The parallels' left ends stand clear of the drill (it exits into air),
    # and under the bar past the part, so the bar rests on them full width.
    par_start = p["cross_parallel_start_mm"]
    if par_start - (station + bore["dia"][1] / 2) < 1.0:
        raise ValueError("the parallels reach under the bore")
    # The spigot end stands out past the jaws' left side far enough for the
    # edge finder (Ø.200 tip under a Ø.500 shank) to reach the spigot face
    # and the spigot's sides; the drill still runs within the bar's grip.
    jaw_from = p["jaw_side_from_face_mm"]
    if jaw_from < 2.54 + 6.35:
        raise ValueError("the spigot face is too close to the jaws for the edge finder")
    if station + dF / 2 < jaw_from - IN:
        raise ValueError("the bore is more than an inch out past the jaws")
    if p["bar_length_min_mm"] < par_start + IN:
        raise ValueError("the bar is too short to lie on the parallels")
    _agree(plan, "part_length_mm", length)

    names = {t["id"]: t["name"] for t in plan["tools"]}
    numbers = {
        t["id"]: n
        for n, t in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    bore_xy = [_r(station), 0.0]
    spot_tool = {
        "tool": "spot",
        "dia": CENTRE_DRILL["body_mm"],
        "shape": "drill",
        "tip_angle": CENTRE_DRILL["point_deg"],
        "rpm": spot_rpm,
        "feed": spot_feed,
        "plunge": spot_feed,
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
    # G54 = axes · (model point − origin): X0 the spigot face, +X toward the
    # free end (model −X); Z up the top corner (model −Y); Y model −Z.
    frames = {
        "cross": {
            "origin": [face_x, -ac / 2, 0.0],
            "axes": [[-1, 0, 0], [0, 0, -1], [0, -1, 0]],
        },
    }
    hy = af / 2
    stock = ((0.0, length), (-hy, hy), (-ac, 0.0))
    jobs = [
        {
            **spot_tool,
            "frame": "cross",
            "label": "corner spot",
            "stock": stock,
            "ops": [
                [
                    "corner_spot",
                    "spot the top corner",
                    _plunge(bore_xy, -corner_spot, clear),
                ]
            ],
        },
        {
            **f_tool,
            "frame": "cross",
            "label": "cross drill",
            "stock": stock,
            "ops": [
                [
                    "cross_drill",
                    "drill F through the corners",
                    _plunge(bore_xy, cross_tip, clear),
                ]
            ],
        },
    ]

    # Keep-outs: the parallels from their left ends to the right, their tops
    # corner_top below Z0; the jaws from their left side on, gripping the
    # vertical flats to the jaw tops; the vise bed under the parallels.
    par_top = -corner_top
    par_x = (par_start, par_start + PARALLEL_LENGTH_MM)
    jaw_x = (jaw_from, jaw_from + p["vise_jaw_width_mm"])
    boxes = [
        _box("moving-jaw parallel", par_x, (-hy, -gap / 2), par_top),
        _box("fixed-jaw parallel", par_x, (gap / 2, hy), par_top),
        _box("vise bed", jaw_x, (-hy, hy), par_top - p["parallel_height_mm"]),
        _box("moving jaw", jaw_x, (-hy - JAW_DEPTH_MM, -hy), cross_jaw_top),
        _box("fixed jaw", jaw_x, (hy, hy + JAW_DEPTH_MM), cross_jaw_top),
    ]

    def hole_checks(bottom: float, radius: float) -> list[list[Any]]:
        return [
            ["holes", {"centres": [bore_xy], "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": 0.0, "open_holes": [bore_xy]}],
            ["vertical_below_top", {"z_top": 0.0}],
            ["air_feed", {"z_top": 0.0}],
            ["keep_out", {"radius": radius, "boxes": boxes}],
        ]

    name = "MO01_cross_bore"
    top = max(0.0, cross_jaw_top)
    expect: list[list[Any]] = [
        [
            name,
            "tool_changes",
            {
                "z_top": top,
                "tools": [numbers["spot"], numbers["drill-f"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[spot_rpm], [f_rpm]]}],
        [name, "pauses", {"z_top": top, "count": 0}],
        [name, "depth", {"z_min": _r(cross_tip)}],
    ]
    for k, checks in enumerate(
        (
            hole_checks(-corner_spot, CENTRE_DRILL["body_mm"] / 2),
            hole_checks(cross_tip, dF / 2),
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
    section; returns {"ops": {operation key: operation}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(
            doc, f"Fixture {key}", ctx["step"], frame["origin"], frame["axes"]
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
# The turned spigot's round, as a polygon of this many sides inscribed in
# it: each facet falls short of the CAD's round by r(1 - cos(180°/n)) =
# 0.0016 mm, a gouge sliver under the report's 1e-3 mm3 region floor along
# the spigot's longest plain run (72 sides left 33 slivers of 0.004 mm3,
# past the report's 40 measured regions, so it could not call them explained).
SPIGOT_SIDES = 128


def as_machined(ctx: dict[str, Any], inputs: Any) -> dict[str, Any]:
    """The bar as Setup 1's lathe leaves it, in MO01's frame: the hex prism
    (the export's hex across flats, its corners on the frame's Z) from the
    spigot's shoulder to the free end, joined to the turned spigot (its
    nominal diameter, a SPIGOT_SIDES-gon run 1 mm into the hex, inside it)
    from the spigot face to the shoulder. The groove and the axial #4-40
    the lathe also makes are not in it: the report shows them as material
    left. The bar beyond the free end (parted off afterwards, Setup 3) is
    left out: MO01 drills only within the part. No sawn length to band."""
    f = inputs.features["features"]
    af = f["hex"]["af_ref"]
    ac = 2 * af / math.sqrt(3)
    spigot = f["spigot"]["length_nominal"]
    length = f["spigot_face"]["plane"]["value"] - f["free_end"]["plane"]["value"]
    if not math.isclose(spigot + f["hex"]["length_nominal"], length, abs_tol=1e-3):
        raise ValueError("the spigot and the hex do not make the part's length")
    r = f["spigot"]["nominal_dia"] / 2
    hexagon = [
        [0.0, 0.0],
        [af / 2, -ac / 4],
        [af / 2, -3 * ac / 4],
        [0.0, -ac],
        [-af / 2, -3 * ac / 4],
        [-af / 2, -ac / 4],
    ]
    round_ = [
        [r * math.cos(2 * math.pi * k / SPIGOT_SIDES), -ac / 2 + r * math.sin(2 * math.pi * k / SPIGOT_SIDES)]
        for k in range(SPIGOT_SIDES)
    ]
    # The lathe's groove and axial #4-40 (Setup 1), not in the blank: model
    # coordinates, the hex axis on model X, the spigot face at its plane.
    face = f["spigot_face"]["plane"]["value"]
    groove, tap = f["groove"], f["tap"]
    spigot_r = f["spigot"]["dia"][1] / 2
    tap_r = tap["dia"][1] / 2
    expected = [
        {
            "name": "wire groove",
            "kind": "left",
            "within": [
                [
                    face - groove["station"][1] - groove["radius"][1],
                    face - groove["station"][0] + groove["radius"][1],
                ],
                [-spigot_r, spigot_r],
                [-spigot_r, spigot_r],
            ],
            "reason": "the full-radius wire groove is turned on the lathe in Setup 1 "
            "(Spigot end: face, turn, groove, drill and tap)",
            "max_mm": (f["spigot"]["dia"][1] - groove["root_dia"][0]) / 2,
        },
        {
            "name": "axial #4-40",
            "kind": "left",
            "within": [
                [face - tap["axis_depth"][1] - _point(2 * tap_r), face],
                [-tap_r, tap_r],
                [-tap_r, tap_r],
            ],
            "reason": "the axial #4-40 is drilled and tapped on the lathe in Setup 1 "
            "(Spigot end: face, turn, groove, drill and tap)",
            "max_mm": tap_r,
        },
    ]
    return {
        "parts": {
            "": {
                "blank": {
                    "frame": "cross",
                    "prism": [
                        {"axis": "x", "polygon": hexagon, "span": [spigot, length]},
                        {"axis": "x", "polygon": round_, "span": [0.0, spigot + 1.0]},
                    ],
                },
                "expected": expected,
            }
        },
        "skip": {},
        "notes": [
            "The blank is the lathe's (Setup 1) hex and spigot; its groove and "
            "axial #4-40 tap are lathe work the route does not mill."
        ],
    }
