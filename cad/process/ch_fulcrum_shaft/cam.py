"""FreeCAD CAM recipe for MHA-CH-04, the fulcrum shaft: its two set-screw flats.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The shaft's length,
diameter and both flats (stations, length, across) come from the feature
export; the riser stacks and the vise from ``plan.toml`` ``[parameters]``;
the end mill's diameter, speed and feed from the shop (``shop/``). Every path
is written here (``rt.custom``): straight lines a recipe can state exactly.
Typed here, because neither record carries them: the ramp's drop per leg, the
safe and clearance heights and the vise jaws' depth (keep-out shapes only).

Route (plan text in ``plan.toml``): both domes are turned first; the shaft
then lies along the vise jaws on one 1 in parallel on edge, centred between
the jaws, centred along them, gripped on its O.D.: FS01 mills both
flats in one clamping, so they face the same way.

Work frame (G54): X0 the apex of dome A (the datum end), +X along the shaft;
Y0 the shaft's axis, +Y toward the fixed jaw; Z0 the top of the O.D.

Each flat is cut with the 1/8 in end mill's bottom, the cutter between the
jaws: its centre crosses the flat's width (Y) at two or more X stations a
cutter radius inside the flat's ends, so the ends are straight and square
to the axis. The cutter ramps in across the flat in legs no deeper than
``RAMP_DROP_MM`` (the end mill is not on record as centre-cutting), then
takes the full-depth passes, zigzag (owner ruling 2026-11-16, ball screws).
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ch_fulcrum_shaft"
COMMENT = "MHA-CH-04 fulcrum shaft"
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (("FS01_flats", ("flats",)),)
# The program loads its own end mill (M6, the tool setter): the setup starts
# on whatever the mill last held.
LOAD_FIRST_TOOL = ("FS01_flats",)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these.
CAM_TOOLS = ("em-eighth",)
# The export's flats, in cutting order, and the end X0 is set on.
FLATS = ("flat_datum", "flat_far")
X0_END = "datum_end"
IN = 25.4
# Each ramp leg crosses the flat's width dropping at most this much: about 2°
# over the .107 in flat (authored).
RAMP_DROP_MM = 0.1
# Ramps start this far above the O.D. top: real G0 brings the cutter to it.
SAFE_MM = 0.1
# Moves between the flats run this far above the jaw tops.
CLEAR_MM = 5.0
# Keep-outs: each vise jaw's depth outward from the gripped O.D.
JAW_DEPTH_MM = IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# The owned mechanical edge finder's tip Ø (shop-equipment tools.edge-finder).
EDGE_FINDER_DIA_IN = 0.200


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
    its chip load × flutes × rpm."""
    op, _record_cut = _op_with_cut(plan, cut)
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    return rpm, record["chip_load_mm_per_tooth"] * record["flutes"] * rpm


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


def _stations(start: float, end: float, step: float) -> list[float]:
    """Equally spaced stations from ``start`` to ``end``, at most ``step`` apart."""
    n = max(1, math.ceil((end - start) / step - 1e-9))
    return [_r(start + (end - start) * k / n) for k in range(n + 1)]


def _flat(xs: list[float], half: float, depth: float, clear: float) -> list[str]:
    """One flat: a rapid to SAFE_MM above the top, a feed down to the top,
    ramp legs across Y (alternating) down to ``-depth`` at the first X
    station, then a full-depth pass across Y at each station, stepping X at
    the flat's edge."""
    n = math.ceil(depth / RAMP_DROP_MM - 1e-9)
    levels = [_r(-depth * (k + 1) / n) for k in range(n)]
    ys = [_r(-half), _r(half)]
    lines = [
        f"G0 Z{_r(clear):.3f}",
        f"G0 X{xs[0]:.3f} Y{ys[0]:.3f}",
        f"G0 Z{_r(SAFE_MM):.3f}",
        "G1 Z0.000 F{feed}",
    ]
    side = 0
    for z in levels:
        side = 1 - side
        lines.append(f"G1 Y{ys[side]:.3f} Z{z:.3f} F{{feed}}")
    # The last ramp leg ends at depth: one full-depth pass at the first station.
    side = 1 - side
    lines.append(f"G1 Y{ys[side]:.3f} F{{feed}}")
    for x in xs[1:]:
        side = 1 - side
        lines.append(f"G1 X{x:.3f} F{{feed}}")
        lines.append(f"G1 Y{ys[side]:.3f} F{{feed}}")
    return lines + [f"G0 Z{_r(clear):.3f}"]


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    f = features["features"]
    p = plan["parameters"]
    outer = f["outer"]
    if outer["axis"] != [0.0, 0.0, 1.0] or outer["at"] != [0.0, 0.0, 0.0]:
        raise ValueError("outer: expected the model Z axis")
    dia = outer["dia_ref"]  # the bought rod, as supplied
    radius = dia / 2

    def apex(name: str) -> float:
        """The end's plane; for a form-cut dome, the apex the shop's form
        radius (not the model's) leaves, the dome being cut full on the O.D."""
        item = f[name]
        value = item["plane"]["value"]
        if item["kind"] == "dome" and "dome_form_radius_in" in p:
            form = p["dome_form_radius_in"] * IN
            cut = form - math.sqrt(form**2 - radius**2)
            value += item["outward"][2] * (cut - item["height_ref"])
        return value

    end = f[X0_END]
    plane = apex(X0_END)
    inward = -end["outward"][2]
    length = abs(apex("far_end") - apex("datum_end"))
    if not math.isclose(p["stock_dia_in"] * IN, dia, abs_tol=1e-6):
        raise ValueError(f"process.stock_dia_in is not the O.D. Ø{dia:.4f}")
    # Setup 6's Y0 pick-up: the owned .200 edge finder (shop-equipment
    # tools.edge-finder, "Mechanical edge finder, .200 in") on the bought O.D.
    _agree(plan, "edge_finder_radius_mm", EDGE_FINDER_DIA_IN * IN / 2)
    _agree(plan, "y0_edge_find_mm", radius + EDGE_FINDER_DIA_IN * IN / 2)

    em = _shop_tool(plan, shop, "em-eighth")["diameter_mm"]
    cutter = em / 2
    rpm, feed = _setting(plan, shop, FLATS[0])
    normals = set()
    flats = []
    for name in FLATS:
        item = f[name]
        normals.add(tuple(item["normal"]))
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), em, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not the end mill's Ø{em}")
        if _setting(plan, shop, name) != (rpm, feed):
            raise ValueError(f"'{name}' runs at another setting than '{FLATS[0]}'")
        xa, xb = sorted(inward * (z - plane) for z in item["span"])
        across = item["across_nominal"]
        depth = dia - across
        half = math.sqrt(radius**2 - (across - radius) ** 2)
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), depth, abs_tol=1e-3):
            raise ValueError(
                f"'{name}' axial_doc_mm is not the flat's depth {depth:.3f}"
            )
        if xb - xa < em:
            raise ValueError(f"{name}: {xb - xa:.3f} long, under the cutter Ø{em}")
        step = _cut(plan, name, "radial_woc_mm")
        if step > cutter + 1e-9:
            raise ValueError(f"'{name}' radial_woc_mm {step} is over half the cutter")
        xs = _stations(xa + cutter, xb - cutter, step)
        _agree(plan, f"{name}_from_mm", xa)
        _agree(plan, f"{name}_to_mm", xb)
        flats.append(
            {"name": name, "x": (xa, xb), "xs": xs, "half": half, "depth": depth}
        )
    if len(normals) != 1:
        raise ValueError(
            f"the flats face different ways: {sorted(normals)}; one clamping cuts both"
        )
    if len({round(fl["depth"], 6) for fl in flats}) != 1:
        raise ValueError("the flats are cut to different depths")
    depth = flats[0]["depth"]

    # The shaft on one parallel standing on edge, centred between the jaws,
    # its O.D. in the jaws: the jaw tops stand above Z0 (the O.D. top) by the
    # jaw height less the parallel and the O.D.
    jaw_top = p["vise_jaw_height_mm"] - p["riser_height_mm"] - dia
    _agree(plan, "jaw_top_over_od_mm", jaw_top)
    if jaw_top < 0:
        raise ValueError(
            "the O.D. stands above the jaw tops: the jaws would not grip it"
        )
    if p["parallel_thickness_mm"] >= dia:
        raise ValueError(
            "the parallel is as wide as the O.D.: the jaws would close on it"
        )
    jaw_from = (length - p["vise_jaw_width_mm"]) / 2
    _agree(plan, "vise_jaw_from_x0_mm", jaw_from)
    _agree(plan, "vise_jaw_to_x0_mm", jaw_from + p["vise_jaw_width_mm"])
    # The cutter between the jaws: its edge clears the jaw faces (the O.D.),
    # and it reaches the flats' floor with its collet above the jaw tops.
    for fl in flats:
        if fl["half"] + cutter >= radius:
            raise ValueError(f"{fl['name']}: the cutter reaches the jaw faces")
    if p["em_eighth_projection_min_mm"] < jaw_top + depth + CLEAR_MM:
        raise ValueError(
            "em_eighth_projection_min_mm: the end mill would not reach the flats"
            " with its collet clear of the jaw tops"
        )
    clear = jaw_top + CLEAR_MM

    numbers = {
        t["id"]: n
        for n, t in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")
    names = {t["id"]: t["name"] for t in plan["tools"]}

    lines: list[str] = []
    for fl in flats:
        lines += _flat(fl["xs"], fl["half"], fl["depth"], clear)
    jobs = [
        {
            "tool": "em-eighth",
            "dia": em,
            "shape": "endmill",
            "flutes": 3,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
            "frame": "shaft",
            "label": "flats",
            "stock": ((0.0, length), (-radius, radius), (-dia, 0.0)),
            "ops": [["flats", "mill both flats", lines]],
        }
    ]
    # Frame: model point -> axes · (p - origin). X along the shaft inward from
    # the X0 end; Z up the flats' normal; Y = Z × X.
    nx, ny, nz = next(iter(normals))
    xaxis = [0.0, 0.0, float(inward)]
    yaxis = [
        ny * xaxis[2] - nz * xaxis[1],
        nz * xaxis[0] - nx * xaxis[2],
        nx * xaxis[1] - ny * xaxis[0],
    ]
    frames = {
        "shaft": {
            "origin": [radius * nx, radius * ny, plane],
            "axes": [xaxis, yaxis, [nx, ny, nz]],
        }
    }

    # Keep-outs below Z0: the jaws past the O.D. (to their tops), and the O.D.
    # left beside each flat (to Z0).
    jaw_x = (jaw_from, jaw_from + p["vise_jaw_width_mm"])
    boxes = [
        _box("moving jaw", jaw_x, (-radius - JAW_DEPTH_MM, -radius), jaw_top),
        _box("fixed jaw", jaw_x, (radius, radius + JAW_DEPTH_MM), jaw_top),
    ]
    edges = [0.0] + [x for fl in flats for x in fl["x"]] + [length]
    for k in range(0, len(edges), 2):
        boxes.append(
            _box(
                f"O.D. kept {k // 2}", (edges[k], edges[k + 1]), (-radius, radius), 0.0
            )
        )
    corners = [
        [x, s * fl["half"]] for fl in flats for x in fl["x"] for s in (-1, 1)
    ] + [[sum(fl["x"]) / 2, 0.0] for fl in flats]
    t = numbers["em-eighth"]
    name = PROGRAMS[0][0]
    expect = [
        [name, "tool_changes", {"z_top": jaw_top, "tools": [t], "loads_first": True}],
        [name, "spindle", {"rpm": [[rpm]]}],
        [name, "pauses", {"z_top": jaw_top, "count": 0}],
        [name, "depth", {"z_min": _r(-depth)}],
        [name, "rapids_clear", {"z_top": 0.0}],
        [name, "air_feed", {"z_top": 0.0}],
        [name, "cleared", {"points": corners, "radius": cutter, "z": _r(-depth)}],
        [name, "keep_out", {"radius": cutter, "boxes": boxes}],
    ]
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
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job;
    returns {"ops": {operation key: operation}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(
            doc, f"Shaft {key}", ctx["step"], frame["origin"], frame["axes"]
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
        )
        for key, label, lines in section["ops"]:
            ops[key] = rt.custom(target, tc, label, lines)
    ops.update(ctx["manual"])
    rt.generate(doc)
    return {"ops": ops}
