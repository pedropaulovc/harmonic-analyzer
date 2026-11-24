"""FreeCAD CAM recipe for MHA-CH-06, the rocker arm (hub MHA-CH-12 bonded
into strap MHA-CH-13, the drawing's note 2).

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The arm's sizes come
from the feature export (the hub's axis and diameter band, the hub length,
the strap's thickness, the pivot bore's band, the #47 rod-pin hole's place
and band, the strap's arcs and tips); the hold, the passes, the drill runs
past the hub and strap and the feeds from ``plan.toml`` ``[parameters]`` and
``milling_cuts``; the face speed from the shop setting the face operations
name and the drills' diameters from the shop (``shop/``). Every path is
written here (``rt.custom``): straight lines a recipe can state exactly.
Typed here, because neither record carries them: the #2 centre drill's
catalogue geometry (it sets the spot depth), the twist drills' 118° point,
the safe height and the blocks' and clamps' keep-out boxes.

Route (plan text in ``plan.toml``): after the bond's 24 h cure the arm lies
on two 1-2-3 blocks, 2 in up, the hub's lower end in the .500 gap between
them, a step clamp over each block, the strap's right tip on a third block.

- RA01 (strap face 1 up): face the hub's top end (datum G's) to the hub end
  height over the strap's top face in two X passes, the cutter's centre at
  Y +r then -r.
- RA02 (turned over, strap face 2 up, trammed on the strap's top edge): face
  the other end the same way; the F drill through the hub down its letter-D
  pilot bore; spot and drill #47 through the strap at the rod-pin hole's
  BASIC place.

Work frame (G54, both programs): X0 Y0 the hub's axis, Z0 the strap's top
face. RA02 is the model frame moved to the hub's axis and the strap's +Z
face; RA01 is that turned over about Y (the hub's -Z end up).

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges at the cutting feed, real G0 above the stock.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ch_rocker_arm"
COMMENT = "MHA-CH-06 rocker arm"
# Programs in order, each listing its operation keys, one section per group
# (a FreeCAD Job), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("RA01_first_end", (("face_first",),)),
    (
        "RA02_second_end_holes",
        (("face_second",), ("bore",), ("rod_spot",), ("rod_drill",)),
    ),
)
# Every program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the gauge blocks, the deburring set, the files and the
# sanding roll are not).
CAM_TOOLS = ("em-half", "drill-f", "spot", "drill-47")
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included, its pilot ground
# with a 118° point: the shop record names the tool, not its geometry.
CENTRE_DRILL = {
    "body_mm": 3 / 16 * IN,
    "pilot_mm": 5 / 64 * IN,
    "pilot_length_mm": 5 / 64 * IN,
    "point_deg": 60.0,
    "pilot_point_deg": 118.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# Plunges, face entries and drill R planes start this far above the surface
# they cut: real G0 brings the tool down to it.
SAFE_MM = 1.0
# A 1-2-3 block's width across the strap and length along it (shop-equipment
# fixtures.blocks-123: 1 x 2 x 3 in); each stands on its 1 x 3 face. The
# gap blocks are centred on the hub's axis in Y; the tip block on the
# strap's tip, the arc's middle between the tip's ends.
BLOCK_WIDTH_MM = 1 * IN
BLOCK_LENGTH_MM = 3 * IN
# A step clamp's keep-out: its toe either side of its station along X, and
# 2 in from the hub's axis either way in Y (the clamps reach in from the
# back; both sides kept clear), up to the plan's least clamp top.
CLAMP_REACH_Y_MM = 2 * IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# The export's F band starts at the HA drill table's 6.528 mm; the shop
# record's .2570 in is 6.5278 mm: the drill is held to the band within this.
DRILL_TABLE_ROUNDING_MM = 0.0005


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


def _speed(plan: dict[str, Any], name: str) -> tuple[float, float]:
    """(rpm, mm/min) the drill cut ``name`` states; its operation prints the
    same rpm (the operator sets it at the tool change)."""
    op = _op_with_cut(plan, name)[0]
    rpm, feed = _cut(plan, name, "rpm"), _cut(plan, name, "feed_mm_min")
    if float(op["rpm"]) != rpm:
        raise ValueError(f"'{name}' rpm {rpm:g} is not its operation's {op['rpm']}")
    return rpm, feed


def _setting(
    plan: dict[str, Any], shop: dict[str, Any], name: str
) -> tuple[float, float]:
    """(rpm, mm/min) of the shop cutting setting the operation holding cut
    ``name`` names: feed = chip load × flutes × rpm."""
    record = shop["settings"][_op_with_cut(plan, name)[0]["settings"]]
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


def _spot_depth(dia: float) -> float:
    """Depth below the surface at which the #2 centre drill reaches ``dia``:
    on its pilot's 118° point under the pilot's diameter, on its 60°
    countersink between the pilot and the body."""
    pilot, body = CENTRE_DRILL["pilot_mm"], CENTRE_DRILL["body_mm"]
    if not 0 < dia <= body or math.isclose(dia, pilot, abs_tol=1e-6):
        raise ValueError(
            f"spot Ø{dia:.3f} is not a point spot under the pilot Ø{pilot:.3f} "
            f"nor between the pilot and the body Ø{body:.3f}"
        )
    if dia < pilot:
        return dia / 2 / math.tan(math.radians(CENTRE_DRILL["pilot_point_deg"] / 2))
    half = math.radians(CENTRE_DRILL["point_deg"] / 2)
    return CENTRE_DRILL["pilot_length_mm"] + (dia - pilot) / 2 / math.tan(half)


def _point(dia: float) -> float:
    """A twist drill's point length."""
    return dia / 2 / math.tan(math.radians(DRILL_POINT_DEG / 2))


def _plunge(xy: tuple[float, float], top: float, z: float, clear: float) -> list[str]:
    """One plunge at ``xy`` from an R plane SAFE_MM over ``top`` to ``z``;
    moves to and from it at ``clear``."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _face(top: float, z: float, y: float, x: float, clear: float) -> list[str]:
    """Two X passes at ``z``: the cutter's centre at Y +``y`` along +X, then
    at Y -``y`` along -X, from and to ``x`` either side of the hub (off it);
    both conventional, the hub on the cutter's right. The entry rapids to
    SAFE_MM over ``top``, the end's highest, off the hub."""
    clear = _r(clear)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{_r(-x):.3f} Y{_r(y):.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G1 X{_r(x):.3f}",
        f"G1 Y{_r(-y):.3f}",
        f"G1 X{_r(-x):.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The arm as the route assumes it: the hub and the bore on one axis
    along model Z, the strap's faces about z = 0, the rod-pin hole parallel
    to the hub, the strap's arcs about one centre."""
    f = features["features"]
    bore, hub, rod = f["pivot_bore"], f["hub_od"], f["rod_hole"]
    for name, feature in (("pivot_bore", bore), ("hub_od", hub), ("rod_hole", rod)):
        if [abs(c) for c in feature["axis"]] != [0.0, 0.0, 1.0]:
            raise ValueError(f"{name} is not along model Z")
    if bore["at"][:2] != hub["at"][:2]:
        raise ValueError("the bore is not on the hub's axis")
    faces, strap = f["hub_faces"], f["strap_faces"]
    if not math.isclose(faces["upper_z"], -faces["lower_z"], abs_tol=1e-6):
        raise ValueError("the hub's ends are not about z = 0")
    if not math.isclose(strap["upper_z"], -strap["lower_z"], abs_tol=1e-6):
        raise ValueError("the strap's faces are not about z = 0")
    top, outer = f["top_edge"], f["profile_outer"]
    if top["arc_centre"] != outer["arc_centre"]:
        raise ValueError("the strap's arcs do not share a centre")
    return {
        "axis": (bore["at"][0], bore["at"][1]),
        "bore_band": tuple(bore["dia"]),
        "hub_band": tuple(hub["dia"]),
        "hub_nominal": hub["dia_nominal"],
        "length": faces["length_nominal"],
        "thick": strap["thickness_nominal"],
        "thick_min": strap["thickness"][0],
        "rod": (rod["at"][0], rod["at"][1]),
        "rod_band": tuple(rod["dia"]),
        "centre": tuple(top["arc_centre"][:2]),
        "top_r": top["radius"],
        "bottom_r": outer["bottom_radius"],
        "depth": outer["depth_ref"],
        "tip": f["tip_land_pos_x"]["station"],
    }


def _arc_y(g: dict[str, Any], radius: float, x: float) -> float:
    """Work Y of a strap arc at work X ``x`` (the arcs' centre above)."""
    cx, cy = g["centre"]
    return cy - math.sqrt(radius**2 - (x - cx + g["axis"][0]) ** 2) - g["axis"][1]


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    thick, length = g["thick"], g["length"]
    rod = (g["rod"][0] - g["axis"][0], g["rod"][1] - g["axis"][1])

    # The hub's ends: each faced from its own strap face to half the
    # nominal length less the strap (the joined_hub adapter's
    # cad.hub_end_height_mm); the end arrives up to the adapter's
    # cad.hub_end_supply_max_mm over the strap.
    height = (length - thick) / 2
    land_max = p["hub_land_max_in"] * IN
    supply_top = (p["hub_supply_length_max_in"] * IN - thick) / 2 + p[
        "bond_offset_max_in"
    ] * IN
    if (
        not g["hub_band"][0]
        <= p["hub_land_min_in"] * IN
        <= land_max
        <= g["hub_band"][1]
    ):
        raise ValueError("the hub's land window is outside the drawing's hub band")

    # Faces: two passes, the cutter's centre on the hub's nominal edge.
    dia = _cut(plan, "first end", "cutter_dia_mm")
    radius = dia / 2
    woc = _cut(plan, "first end", "radial_woc_mm")
    depth = _cut(plan, "first end", "axial_doc_mm")
    for name in ("first end", "second end"):
        for key, value in (
            ("cutter_dia_mm", dia),
            ("radial_woc_mm", woc),
            ("axial_doc_mm", depth),
        ):
            if _cut(plan, name, key) != value:
                raise ValueError(f"'{name}' {key} is not 'first end''s")
    _agree(plan, "face_cutter_dia_mm", dia)
    _agree(plan, "face_pass_y_mm", g["hub_nominal"] / 2)
    _agree(plan, "face_woc_mm", radius)
    # The deepest an end is faced: the longest hub, the most off-centre bond
    # and the thinnest strap, down to the nominal end height.
    _agree(
        plan,
        "face_depth_max_mm",
        (p["hub_supply_length_max_in"] * IN - g["thick_min"]) / 2
        + p["bond_offset_max_in"] * IN
        - height,
    )
    if not math.isclose(depth, p["face_depth_max_mm"], abs_tol=1e-6):
        raise ValueError("'first end' axial_doc_mm is not process.face_depth_max_mm")
    y = p["face_pass_y_mm"]
    # The first pass takes the cutter's radius less the hub's far side's
    # part, at most the plan's width.
    if min(y + radius, land_max / 2) - max(y - radius, -land_max / 2) > woc + 1e-6:
        raise ValueError("a face pass takes more than the plan's radial_woc_mm")
    x = p["face_pass_x_mm"]
    if x <= land_max / 2 + radius:
        raise ValueError("process.face_pass_x_mm: the passes start on the hub")
    for name in ("first end", "second end"):
        traverse = [
            _resolve(plan, v, name) for v in _op_with_cut(plan, name)[1]["traverse_mm"]
        ]
        if traverse != [-x, x]:
            raise ValueError(f"'{name}' traverse_mm is not ±process.face_pass_x_mm")
    face_rpm, face_feed = _setting(plan, shop, "first end")
    if _setting(plan, shop, "second end") != (face_rpm, face_feed):
        raise ValueError("the two ends' face settings differ")

    # The hold: the hub's lower end and the F drill hang in the gap between
    # the blocks; the clamps stand under the traverse height; the #47 lies
    # between the right block and the tip block, the strap's tip on it.
    gap = p["block_inner_x_mm"]
    if g["hub_band"][1] / 2 >= gap:
        raise ValueError("the hub's lower end does not clear the gap blocks")
    if not math.isclose(
        p["block_outer_x_mm"] - gap, BLOCK_LENGTH_MM, abs_tol=PLAN_TOL_MM
    ):
        raise ValueError("the gap blocks are not 3 in long")
    if p["traverse_z_mm"] <= p["clamp_top_max_mm"]:
        raise ValueError("process.traverse_z_mm is not above the clamps")
    _agree(plan, "strap_tip_x_mm", g["tip"])
    _agree(plan, "strap_depth_mm", g["depth"])
    tip_block = p["tip_block_x_mm"]
    if not p["block_outer_x_mm"] < rod[0] < tip_block < g["tip"]:
        raise ValueError("the #47 is not between the right block and the tip block")
    # The facing and the holes are on beams this recipe states: the plan's
    # spans must be the same numbers.
    beams = [
        (op.get("beam") or setup.get("beam"), op)
        for setup in plan["setups"]
        for op in setup.get("operations", ())
        if op.get("milling_cuts")
    ]
    for beam, op in beams:
        if [_resolve(plan, v, "beam") for v in beam["extent_mm"]] != [
            -p["strap_tip_x_mm"],
            p["strap_tip_x_mm"],
        ]:
            raise ValueError("a beam's extent_mm is not ±process.strap_tip_x_mm")
        supports = [_resolve(plan, v, "beam") for v in beam["supports_mm"]]
        drill = op["milling_cuts"][0]["name"].startswith("rod")
        want = [p["block_outer_x_mm"], tip_block] if drill else [-gap, gap]
        if supports != want:
            raise ValueError(
                f"beam supports {supports} for '{op['milling_cuts'][0]['name']}', expected {want}"
            )

    # The F drill: through the faced hub, its full diameter past the lower
    # end; the #47 through the strap likewise.
    dF = _shop_tool(plan, shop, "drill-f")["diameter_mm"]
    low, high = g["bore_band"]
    if not low - DRILL_TABLE_ROUNDING_MM <= dF <= high:
        raise ValueError(f"F Ø{dF} outside the bore band {g['bore_band']}")
    if dF / 2 >= gap:
        raise ValueError("the F drill reaches the gap blocks")
    d47 = _shop_tool(plan, shop, "drill-47")["diameter_mm"]
    low, high = g["rod_band"]
    if not low - DRILL_TABLE_ROUNDING_MM <= d47 <= high:
        raise ValueError(f"#47 Ø{d47} outside the hole band {g['rod_band']}")
    for name, tool in (("bore", dF), ("rod drill", d47)):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), tool, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not its tool's Ø{tool}")
    bore_tip = -(thick + height + p["bore_drill_past_mm"] + _point(dF))
    _agree(plan, "bore_tip_z_mm", bore_tip)
    rod_tip = -(thick + p["rod_drill_past_mm"] + _point(d47))
    _agree(plan, "rod_tip_z_mm", rod_tip)
    if rod[0] + d47 / 2 >= tip_block:
        raise ValueError("the #47 reaches the tip block")
    if not math.isclose(
        _cut(plan, "rod spot", "cutter_dia_mm"), p["spot_dia_mm"], abs_tol=1e-6
    ):
        raise ValueError("'rod spot' cutter_dia_mm is not process.spot_dia_mm")
    if p["spot_dia_mm"] >= d47:
        raise ValueError("the spot is not under the #47")
    spot = _spot_depth(p["spot_dia_mm"])
    speeds = {name: _speed(plan, name) for name in ("bore", "rod spot", "rod drill")}
    for name, key in (
        ("bore", "bore_feed_per_min_mm"),
        ("rod spot", "spot_feed_per_min_mm"),
        ("rod drill", "rod_feed_per_min_mm"),
    ):
        if not math.isclose(speeds[name][1], p[key], abs_tol=1e-6):
            raise ValueError(f"'{name}' feed_mm_min is not process.{key}")

    names = {t["id"]: t["name"] for t in plan["tools"]}
    numbers = {
        t["id"]: n
        for n, t in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    def section(
        tool: str, dia_: float, rpm: float, feed: float, shape: str
    ) -> dict[str, Any]:
        tip_angle = None
        if shape == "drill":
            tip_angle = CENTRE_DRILL["point_deg"] if tool == "spot" else DRILL_POINT_DEG
        return {
            "tool": tool,
            "dia": dia_,
            "shape": shape,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
            "tip_angle": tip_angle,
        }

    # Frames (model point p -> axes · (p - origin)): the second load is the
    # model frame at the hub's axis on the strap's +Z face; the first is
    # turned over about Y, on the -Z face.
    ax, ay = g["axis"]
    frames = {
        "first": {
            "origin": [ax, ay, -thick / 2],
            "axes": [[-1, 0, 0], [0, 1, 0], [0, 0, -1]],
        },
        "second": {
            "origin": [ax, ay, thick / 2],
            "axes": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        },
    }
    half = g["tip"]
    stock = (
        (-half, half),
        (_arc_y(g, g["bottom_r"], 0.0), _arc_y(g, g["top_r"], half)),
        (-thick - supply_top, supply_top),
    )
    clear = p["traverse_z_mm"]
    origin = (0.0, 0.0)
    rod_xy = (_r(rod[0]), _r(rod[1]))
    face_section = section("em-half", dia, face_rpm, face_feed, "endmill")
    jobs = [
        {
            **face_section,
            "frame": "first",
            "label": "first end",
            "stock": stock,
            "ops": [
                [
                    "face_first",
                    "face the first hub end",
                    _face(supply_top, height, y, x, clear),
                ]
            ],
        },
        {
            **face_section,
            "frame": "second",
            "label": "second end",
            "stock": stock,
            "ops": [
                [
                    "face_second",
                    "face the second hub end",
                    _face(supply_top, height, y, x, clear),
                ]
            ],
        },
        {
            **section("drill-f", dF, *speeds["bore"], "drill"),
            "frame": "second",
            "label": "bore",
            "stock": stock,
            "ops": [
                ["bore", "F through the hub", _plunge(origin, height, bore_tip, clear)]
            ],
        },
        {
            **section("spot", CENTRE_DRILL["body_mm"], *speeds["rod spot"], "drill"),
            "frame": "second",
            "label": "rod spot",
            "stock": stock,
            "ops": [["rod_spot", "spot the #47", _plunge(rod_xy, 0.0, -spot, clear)]],
        },
        {
            **section("drill-47", d47, *speeds["rod drill"], "drill"),
            "frame": "second",
            "label": "rod drill",
            "stock": stock,
            "ops": [
                [
                    "rod_drill",
                    "#47 through the strap",
                    _plunge(rod_xy, 0.0, rod_tip, clear),
                ]
            ],
        },
    ]

    # Keep-outs: the blocks' tops at the strap's underside; the clamps up to
    # the plan's least clamp top, over the gap blocks either side.
    under = -thick
    block_y = (-BLOCK_WIDTH_MM / 2, BLOCK_WIDTH_MM / 2)
    tip_mid = (_arc_y(g, g["top_r"], half) + _arc_y(g, g["bottom_r"], half)) / 2
    tip_y = (tip_mid - BLOCK_WIDTH_MM / 2, tip_mid + BLOCK_WIDTH_MM / 2)
    toe, cx = p["clamp_toe_mm"], p["clamp_x_mm"]
    boxes = [
        _box("left gap block", (-p["block_outer_x_mm"], -gap), block_y, under),
        _box("right gap block", (gap, p["block_outer_x_mm"]), block_y, under),
        _box("tip block", (tip_block, tip_block + BLOCK_LENGTH_MM), tip_y, under),
        _box(
            "left clamp",
            (-cx - toe, -cx + toe),
            (-CLAMP_REACH_Y_MM, CLAMP_REACH_Y_MM),
            p["clamp_top_max_mm"],
        ),
        _box(
            "right clamp",
            (cx - toe, cx + toe),
            (-CLAMP_REACH_Y_MM, CLAMP_REACH_Y_MM),
            p["clamp_top_max_mm"],
        ),
    ]

    t = numbers

    def face_checks() -> list[list[Any]]:
        return [
            [
                "face_passes",
                {
                    "z": _r(height),
                    "y": [-land_max / 2, land_max / 2],
                    "max_engagement": woc,
                    "radius": radius,
                    "span": 2 * land_max / 2,
                },
            ],
            ["rapids_clear", {"z_top": supply_top}],
            ["air_feed", {"z_top": supply_top}],
            ["keep_out", {"radius": radius, "boxes": boxes}],
        ]

    def hole_checks(
        xy: tuple[float, float], top: float, bottom: float, radius_: float
    ) -> list[list[Any]]:
        return [
            ["holes", {"centres": [xy], "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": top, "open_holes": [xy]}],
            ["vertical_below_top", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": radius_, "boxes": boxes}],
        ]

    first, second = (name for name, _ops in PROGRAMS)
    expect: list[list[Any]] = [
        [
            first,
            "tool_changes",
            {"z_top": supply_top, "tools": [t["em-half"]], "loads_first": True},
        ],
        [first, "spindle", {"rpm": [[face_rpm]]}],
        [first, "pauses", {"z_top": supply_top, "count": 0}],
        [first, "depth", {"z_min": _r(height)}],
        [
            second,
            "tool_changes",
            {
                "z_top": supply_top,
                "tools": [t["em-half"], t["drill-f"], t["spot"], t["drill-47"]],
                "loads_first": True,
            },
        ],
        [
            second,
            "spindle",
            {
                "rpm": [
                    [face_rpm],
                    [speeds["bore"][0]],
                    [speeds["rod spot"][0]],
                    [speeds["rod drill"][0]],
                ]
            },
        ],
        [second, "pauses", {"z_top": supply_top, "count": 0}],
        [second, "depth", {"z_min": _r(bore_tip)}],
    ]
    expect += [[f"{first}@0", check, kwargs] for check, kwargs in face_checks()]
    expect += [[f"{second}@0", check, kwargs] for check, kwargs in face_checks()]
    for k, checks in enumerate(
        (
            hole_checks(origin, height, bore_tip, dF / 2),
            hole_checks(rod_xy, 0.0, -spot, p["spot_dia_mm"] / 2),
            hole_checks(rod_xy, 0.0, rod_tip, d47 / 2),
        ),
        1,
    ):
        expect += [[f"{second}@{k}", check, kwargs] for check, kwargs in checks]

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
            doc, f"Arm {key}", ctx["step"], frame["origin"], frame["axes"]
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
            tip_angle=section.get("tip_angle"),
        )
        for key, label, lines in section["ops"]:
            ops[key] = rt.custom(target, tc, label, lines)
    ops.update(ctx["manual"])
    rt.generate(doc)
    return {"ops": ops}
