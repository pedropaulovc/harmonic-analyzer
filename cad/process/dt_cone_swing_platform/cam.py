"""FreeCAD CAM recipe for MHA-DT-20, the cone swing platform.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The plate's sizes come
from the feature export (the outline's corners and radii, the chamfer, the
lock notch, the top relief, the pivot bore, the hold-down hole and its
counterbore, the two post taps); the blank, the wastes, the levels, the holes'
depths and the feeds from ``plan.toml`` ``[parameters]`` and
``milling_cuts``; cutter, drill and reamer diameters and the end mills'
settings from the shop (``shop/``). Every path is written here
(``rt.custom``): straight lines and arcs a recipe can state exactly. Typed
here, because neither record carries them: the #1 centre drill's catalogue
geometry, the twist drills' 118° point, the machine's Z top for the tap
files' retract, the safe and clearance heights, the vise jaws' depth, the
parallels' thickness and the 1-2-3 blocks' and step clamps' footprints
(keep-out shapes only).

Route (plan text in ``plan.toml``): the plate is laid in the 1/4 x 2-1/2 in
bar at 1.86° so that its east edge is the bar's straight edge E, as
supplied; every other edge is milled. Setup 2, the sawn blank underside up
on parallels in the vise, E against the fixed jaw, both ends overhanging:
PL01 faces both ends to length and drills every hole from the underside
(the pivot B, the hold-down drilled and counterbored, the two post taps'
and the wedge screw's #7 holes); PL02/PL03 bring the tap guide over each
post hole. Setup 3, vise off, the 1/2 x 6 in aluminium spoil plate on five
1-2-3 blocks, step-clamped: PL04 drills its two clearance holes for the
post screws. Setup 4, the blank top up on the plate, screwed down from
below through the post taps and trammed on E: PL05 runs the B drill on
into the plate and reams the pivot (the bar flat on the plate takes the
reamer's thrust), then drills the plate through the hold-down and wedge
holes; PL06-PL07 bring the tap guide over each; PL08 cuts the outline
through (the SE corner cleared, roughed level by level, finished), the
wedge of waste screwed down; PL09 cuts the top relief to its floor (the
shoulder screw's measured length, or the sheet's .010 REF below the top).

Work frames (G54), each set in its setup (S3 = the plate frame):
- PL01-PL03: X0 the sawn blank's south end (left), +X north along E; Y0 the
  fixed jaw's face (edge E), the blank at -Y; Z0 the underside (up).
- PL04: X0 the spoil plate's left end, Y0 its front edge, the plate at +Y;
  Z0 its top.
- PL05-PL08: X0 Y0 the pivot bore's axis, +X north along E, +Y west (E at
  the front, -Y); Z0 the spoil plate's top (the plate's underside).
- PL09: as PL08 but Z0 the relief's floor.

Toolpath rules (owner rulings 2026-11-16): plunges beside the stock at the
cutting feed, real G0 above the stock. The outline runs anticlockwise round
the part (conventional outside with M3), the counterbore's helix and the
relief clockwise (conventional inside). The holes are tapped by hand
(FluidNC cannot rigid-tap; owner, Pedro, 2026-11-17), the T-handle wrench's
centre hole on the spring point of the Fisher tap guide in the 1/2 in R8
collet (owner, Pedro, 2026-11-21: "use
https://littlemachineshop.com/products/tap-guide-fisher?variant=45472915226805
on r8 0.5 collet"), spindle off; FluidNC refuses jogs while an M0 holds the
program (FluidNC wiki, "Single Block Mode"), so each tap stop is a file of
its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_cone_swing_platform"
COMMENT = "MHA-DT-20 cone swing platform"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    (
        "PL01_holes",
        (
            ("ends",),
            ("hole_spots",),
            ("holddown_drill",),
            ("holddown_cbore",),
            ("pivot_drill",),
            ("post_drills",),
        ),
    ),
    ("PL02_post_far_tap", ("post_far_tap_stop",)),
    ("PL03_post_near_tap", ("post_near_tap_stop",)),
    ("PL04_plate_holes", (("plate_spots",), ("plate_clearance",))),
    (
        "PL05_seat_drills",
        (("pivot_redrill",), ("pivot_ream",), ("holddown_seat",), ("screw_seats",)),
    ),
    ("PL06_holddown_tap", ("holddown_tap_stop",)),
    ("PL07_wedge_tap", ("wedge_tap_stop",)),
    ("PL08_outline", (("outline",),)),
    ("PL09_relief", (("relief",),)),
)
# Every program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the taps, the gauges and the files are not).
CAM_TOOLS = (
    "em-quarter",
    "em-eighth",
    "spot",
    "drill-31",
    "drill-b",
    "reamer",
    "drill-7",
    "drill-l",
    "drill-25",
    "drill-43",
    "tap-guide",
)
IN = 25.4
# #1 combined drill and countersink (shop centre-drills-carbide-60, trade
# size 1): 1/8 body, 3/64 pilot and pilot length, 60° countersink, its pilot
# ground with a 118° point (as ch_channel_lever's recipe).
CENTRE_DRILL = {
    "body_mm": 1 / 8 * IN,
    "pilot_mm": 3 / 64 * IN,
    "pilot_length_mm": 3 / 64 * IN,
    "point_deg": 60.0,
    "pilot_point_deg": 118.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# The tap files' first motion: G53 G0 to machine Z0, the homed top; the owner
# (Pedro) confirmed it, answered in person 2026-11-21 (cnc rulings record).
MACHINE_Z_TOP_MM = 0.0
# Plunges and drill R planes start this far above the stock top.
SAFE_MM = 1.0
# Moves between cuts run this far above the highest obstacle (jaw tops,
# screw heads).
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped edge; the
# parallels' thickness (1/8 in, fixtures.parallels-lms-6745); a 1-2-3 block
# lying flat (3 x 2 in, 1 in up, fixtures.blocks-123); a step clamp's
# footprint round its stud (LMS 1268 kit: about 1 x 4 in, 2 in tall above the
# plate with its step block).
JAW_DEPTH_MM = IN
PARALLEL_THICKNESS_MM = IN / 8
BLOCK_MM = (3 * IN, 2 * IN, IN)
CLAMP_MM = (IN, 4 * IN, 2 * IN)
# A cutter passes a jaw end, a block, a screw head or a blank edge at no less
# than this.
JAW_CLEARANCE_MM = 1.5
# A waste corner the outline must cut away lies at least this far inside the
# cutter's reach (no sliver left to fly).
SLIVER_MARGIN_MM = 0.3
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# The end mills' shop settings in 1018 CF.
QUARTER_SETTING = "endmill-carbide-3fl-1-4-1018-cf"
EIGHTH_SETTING = "endmill-carbide-3fl-1-8-1018-cf-tru-edge"
# Screw heads standing on the part's top (Setup 4), as keep-outs: the #4-40
# socket head (Ø.183 x .112) at the hold-down hole and the #10-24 socket head
# (Ø.312 x .190) at the wedge (ASME B18.3 nominal head sizes).
HEAD_4_40_MM = (0.183 * IN, 0.112 * IN)
HEAD_10_24_MM = (0.312 * IN, 0.190 * IN)
# The #10-24 tap's major diameter and the #4-40's (ASME B1.1 basic), which
# pass through the part's holes to the plate below.
TAP_10_24_MM = 0.19 * IN
TAP_4_40_MM = 0.112 * IN


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


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


def _r(value: float) -> float:
    """A coordinate as the post prints it (3 places)."""
    return round(value + 0.0, 3)


def _xy(p: tuple[float, float]) -> str:
    return f"X{_r(p[0]):.3f} Y{_r(p[1]):.3f}"


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
    """Depth below the surface at which the #1 centre drill's 60° countersink
    reaches ``dia`` (between its pilot and its body)."""
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


# --- plane geometry (2-D points as (x, y) tuples) ---------------------------


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _add(a, b, k=1.0):
    return (a[0] + k * b[0], a[1] + k * b[1])


def _unit(v):
    length = math.hypot(*v)
    return (v[0] / length, v[1] / length)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _right(d):
    """The right-hand normal of direction ``d``: outward on an anticlockwise
    outline."""
    return (d[1], -d[0])


def _meet(p, d, q, e):
    """Where the line through ``p`` along ``d`` meets the one through ``q``
    along ``e``."""
    t = _cross(_sub(q, p), e) / _cross(d, e)
    return _add(p, d, t)


def _fillet(corner, d_in, d_out, radius):
    """The arc of ``radius`` tangent to a path arriving at ``corner`` along
    ``d_in`` and leaving along ``d_out``: (tangent in, centre, tangent out)."""
    turn = math.acos(max(-1.0, min(1.0, _dot(d_in, d_out))))
    back = radius * math.tan(turn / 2)
    t_in, t_out = _add(corner, d_in, -back), _add(corner, d_out, back)
    side = 1.0 if _cross(d_in, d_out) > 0 else -1.0
    centre = _add(t_in, (-d_in[1] * side, d_in[0] * side), radius)
    return t_in, centre, t_out


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The plate as the routes assume it: model X across (east -X), Y the
    thickness (underside 0, top up), Z along (north +Z); the pivot bore on
    the model origin; every station from the pivot. Returns model (x, z)
    points and the frame that lays edge E along the bar."""
    f = features["features"]
    pivot, holddown = f["pivot_bore"], f["holddown"]
    if pivot["at"][0] != 0.0 or pivot["at"][2] != 0.0:
        raise ValueError("the pivot bore is off the model origin")
    for name in ("pivot_bore", "post_mount_west", "post_mount_east", "holddown"):
        if f[name]["axis"][0] != 0.0 or f[name]["axis"][2] != 0.0:
            raise ValueError(f"{name} does not run along model Y")
    if f["underside"]["plane"] != {"frame": "model", "axis": "y", "value": 0.0}:
        raise ValueError("the underside is not the model's Y0 plane")
    if f["tip_dowel"]["made_at"] != "assembly":
        raise ValueError(
            "the tip dowel is no longer made at assembly: this route does not make it"
        )
    if holddown["cbore_depth_from"] != "underside":
        raise ValueError("the hold-down's counterbore is not from the underside")
    o = f["outline"]
    north = f["north_edge"]["plane"]["value"]
    south = f["south_edge"]["plane"]["value"]
    if f["north_edge"]["station_from"] != "pivot_bore" or not math.isclose(
        north, f["north_edge"]["station_nominal"]
    ):
        raise ValueError("the north edge is not stationed from the pivot")
    if not math.isclose(north - south, f["south_edge"]["length_nominal"], abs_tol=1e-6):
        raise ValueError("the south edge is not the length from the north edge")
    ne = (-o["north_east_x_nominal"], north)
    nw = (o["north_west_x_nominal"], north)
    sw = (o["south_west_x_nominal"], south)
    se = (-o["south_east_x_nominal"], south)
    if o["extent_x"] != [se[0], sw[0]] or o["extent_z"] != [south, north]:
        raise ValueError("the outline's extent is not its four corners'")
    ch = f["se_chamfer"]
    if ch["start_x_from"] != "pivot_bore" or ch["rise_from"] != "south_edge":
        raise ValueError(
            "the chamfer's legs are not stationed as the recipe reads them"
        )
    if not math.isclose(ch["start_x_nominal"] - se[0], ch["run_ref"], abs_tol=1e-6):
        raise ValueError("the chamfer's run is not its start less the SE corner")
    notch = f["lock_notch"]
    relief = f["top_relief"]
    if (
        relief["open_to"] != "north_edge"
        or relief["centre_at"][0] != 0.0
        or relief["centre_at"][2] != 0.0
    ):
        raise ValueError(
            "the top relief is not round the pivot, open to the north edge"
        )
    if not math.isclose(
        relief["width_nominal"], 2 * relief["end_radius_nominal"], abs_tol=1e-6
    ):
        raise ValueError("the top relief's end is not a full round of its width")

    def xz(name: str) -> tuple[float, float]:
        at = f[name]["at"]
        return (at[0], at[2])

    return {
        "ne": ne,
        "nw": nw,
        "sw": sw,
        "se": se,
        "r_ne": o["ne_radius_nominal"],
        "r_nw": o["nw_radius_nominal"],
        "r_sw": o["sw_radius_nominal"],
        "chamfer_start": (ch["start_x_nominal"], south),
        "chamfer_rise": ch["rise_nominal"],
        "seat": (notch["seat_at"][0], notch["seat_at"][2]),
        "run": (notch["run_dir"][0], notch["run_dir"][2]),
        "notch_half": notch["width_nominal"] / 2,
        "relief_r": relief["end_radius_nominal"],
        "relief_ref": relief["depth_ref"],
        "north_station": f["north_edge"]["station"],
        "pivot_band": pivot["dia"],
        "holddown": xz("holddown"),
        "holddown_band": holddown["dia"],
        "cbore_dia": holddown["cbore_dia_nominal"],
        "cbore_band": holddown["cbore_dia"],
        "cbore_depth": holddown["cbore_depth_nominal"],
        "cbore_depth_band": holddown["cbore_depth"],
        "post_west": xz("post_mount_west"),
        "post_east": xz("post_mount_east"),
        "post_band": f["post_mount_west"]["dia"],
        "thickness_band": f["top_face"]["thickness_band_mm"],
        "thickness": f["top_face"]["thickness_as_supplied"],
    }


def _layout(g: dict[str, Any]) -> dict[str, Any]:
    """Edge E (the east edge, NE to SE) laid along the bar: ``u`` runs along
    it north to south, ``n`` square to it into the plate (west). The
    top-up work frame (Setup 4): X = -p·u (north +X), Y = p·n (west +Y),
    both from the pivot; a proper rotation of the model's top view."""
    u = _unit(_sub(g["se"], g["ne"]))
    n = (-u[1], u[0])
    if _dot(n, _sub(g["sw"], g["se"])) <= 0:
        raise ValueError("the plate does not lie west of edge E")

    def work(p):
        return (-_dot(p, u), _dot(p, n))

    return {"u": u, "n": n, "work": work}


def _outline(g: dict[str, Any], work) -> list[dict[str, Any]]:
    """The milled outline in the top-up frame, anticlockwise from edge E's
    north lead to its south lead: lines and minor arcs (``cw`` marks the
    notch's seat, the only arc turning clockwise). Each corner fillet's
    tangent points come from the two edges it joins."""
    ne, nw, sw, se = (work(g[k]) for k in ("ne", "nw", "sw", "se"))
    cs = work(g["chamfer_start"])
    # The chamfer's east end: up edge E from the SE corner by its rise.
    d_e = _unit(_sub(ne, se))  # along E, north
    d_s = _unit(_sub(se, sw))  # along the south edge, toward E
    rise_dir = _unit(_sub(work((0.0, 1.0)), work((0.0, 0.0))))  # model +Z
    ce = _meet(se, d_e, _add(se, rise_dir, g["chamfer_rise"]), _right(rise_dir))
    d_n = _unit(_sub(nw, ne))  # along the north edge, west
    d_w = _unit(_sub(sw, nw))  # along the west edge, south
    ne_in, ne_c, ne_out = _fillet(ne, d_e, d_n, g["r_ne"])
    nw_in, nw_c, nw_out = _fillet(nw, d_n, d_w, g["r_nw"])
    sw_in, sw_c, sw_out = _fillet(sw, d_w, d_s, g["r_sw"])
    # The notch: its centre line from the seat along the run; its sides at
    # the half width; where they meet the west edge, its mouth corners.
    seat = work(g["seat"])
    run = _unit(_sub(work(_add(g["seat"], g["run"])), seat))
    h = g["notch_half"]
    side_n = (-run[1], run[0])  # the side the anticlockwise path meets first
    if _dot(side_n, d_w) > 0:
        side_n = (-side_n[0], -side_n[1])
    a_seat, b_seat = _add(seat, side_n, h), _add(seat, side_n, -h)
    a_mouth = _meet(nw, d_w, a_seat, run)
    b_mouth = _meet(nw, d_w, b_seat, run)
    apex = _add(seat, run, -h)
    return [
        {"name": "E north lead", "start": _add(ne_in, d_e, -5.0), "end": ne_in},
        {"name": "NE round", "start": ne_in, "end": ne_out, "centre": ne_c},
        {"name": "north edge", "start": ne_out, "end": nw_in},
        {"name": "NW round", "start": nw_in, "end": nw_out, "centre": nw_c},
        {"name": "west edge north", "start": nw_out, "end": a_mouth},
        {"name": "notch north side", "start": a_mouth, "end": a_seat},
        {
            "name": "notch seat north",
            "start": a_seat,
            "end": apex,
            "centre": seat,
            "cw": True,
        },
        {
            "name": "notch seat south",
            "start": apex,
            "end": b_seat,
            "centre": seat,
            "cw": True,
        },
        {"name": "notch south side", "start": b_seat, "end": b_mouth},
        {"name": "west edge south", "start": b_mouth, "end": sw_in},
        {"name": "SW round", "start": sw_in, "end": sw_out, "centre": sw_c},
        {"name": "south edge", "start": sw_out, "end": cs},
        {"name": "chamfer", "start": cs, "end": ce},
        {"name": "E south lead", "start": ce, "end": _add(ce, d_e, 5.0)},
    ]


def _direction(e: dict[str, Any], at_end: bool):
    """An element's direction of travel at its start or end."""
    if "centre" not in e:
        return _unit(_sub(e["end"], e["start"]))
    p = e["end"] if at_end else e["start"]
    radial = _unit(_sub(p, e["centre"]))
    return (radial[1], -radial[0]) if e.get("cw") else (-radial[1], radial[0])


def _offset_path(elements: list[dict[str, Any]], d: float, z: float) -> list[str]:
    """The cutter-centre path at offset ``d`` outside ``elements`` (an
    anticlockwise chain), at ``z``: each line shifted to its right, each arc
    grown (anticlockwise) or shrunk (the clockwise seat) by ``d``, and a G3
    of radius ``d`` round every sharp convex corner. Starts with the move
    to the first point at feed (the caller plunges there)."""
    lines: list[str] = []
    previous_end = None
    for k, e in enumerate(elements):
        d_start = _direction(e, False)
        start = _add(e["start"], _right(d_start), d)
        if previous_end is not None and math.dist(previous_end, start) > 1e-6:
            corner = e["start"]
            if _cross(_direction(elements[k - 1], True), d_start) <= 0:
                raise ValueError(f"{e['name']}: a concave corner the path cannot turn")
            lines.append(
                f"G3 {_xy(start)} I{_r(corner[0] - previous_end[0]):.3f} J{_r(corner[1] - previous_end[1]):.3f}"
            )
        d_end = _direction(e, True)
        end = _add(e["end"], _right(d_end), d)
        if "centre" in e:
            c = e["centre"]
            motion = "G2" if e.get("cw") else "G3"
            if math.dist(c, start) < 1e-6:
                raise ValueError(f"{e['name']}: the offset shrinks the arc to a point")
            lines.append(
                f"{motion} {_xy(end)} I{_r(c[0] - start[0]):.3f} J{_r(c[1] - start[1]):.3f}"
            )
        else:
            lines.append(f"G1 {_xy(end)}")
        previous_end = end
    return lines


def _pecked(
    xy: tuple[float, float],
    top: float,
    tip: float,
    peck: float,
    clear: float,
    r_plane: float,
) -> list[str]:
    """Drill from ``top`` to ``tip`` in pecks of ``peck``, each with a full
    retract to the R plane and a rapid back to just above the last peck."""
    clear, r_plane = _r(clear), _r(r_plane)
    depths = []
    depth = top
    while depth - peck > tip + 1e-6:
        depth -= peck
        depths.append(_r(depth))
    depths.append(_r(tip))
    lines = [f"G0 Z{clear:.3f}", f"G0 {_xy(xy)}", f"G0 Z{r_plane:.3f}"]
    previous = None
    for z in depths:
        if previous is not None:
            lines += [f"G0 Z{r_plane:.3f}", f"G0 Z{_r(previous + PECK_REENTRY_MM):.3f}"]
        lines.append(f"G1 Z{z:.3f} F{{feed}}")
        previous = z
    return lines + [f"G0 Z{r_plane:.3f}", f"G0 Z{clear:.3f}"]


def _spot(xy: tuple[float, float], z: float, clear: float, r_plane: float) -> list[str]:
    return [
        f"G0 Z{_r(clear):.3f}",
        f"G0 {_xy(xy)}",
        f"G0 Z{_r(r_plane):.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{_r(r_plane):.3f}",
        f"G0 Z{_r(clear):.3f}",
    ]


def _reamed(
    xy: tuple[float, float], tip: float, clear: float, r_plane: float
) -> list[str]:
    """Ream from the R plane to ``tip`` and back out, both at feed."""
    return [
        f"G0 Z{_r(clear):.3f}",
        f"G0 {_xy(xy)}",
        f"G0 Z{_r(r_plane):.3f}",
        f"G1 Z{_r(tip):.3f} F{{feed}}",
        f"G1 Z{_r(r_plane):.3f} F{{feed}}",
        f"G0 Z{_r(clear):.3f}",
    ]


def _helix(
    centre: tuple[float, float],
    radius: float,
    pitch: float,
    bottom: float,
    clear: float,
) -> list[str]:
    """The counterbore: down a G2 helix of ``radius`` about ``centre`` from
    the face (Z0) to ``bottom``, one level turn there, then to the
    centre and out. Each turn ends where it starts."""
    cx, cy = centre
    sx = _r(cx + radius)
    top = 0.0
    turns = math.ceil((top - bottom) / pitch - 1e-9)
    step = (top - bottom) / turns
    lines = [
        f"G0 Z{_r(clear):.3f}",
        f"G0 X{sx:.3f} Y{_r(cy):.3f}",
        f"G0 Z{_r(SAFE_MM):.3f}",
        f"G1 Z{_r(top):.3f} F{{feed}}",
    ]
    for k in range(1, turns + 1):
        lines.append(
            f"G2 X{sx:.3f} Y{_r(cy):.3f} I{_r(-radius):.3f} J0.000 Z{_r(top - k * step):.3f}"
        )
    lines += [
        f"G2 X{sx:.3f} Y{_r(cy):.3f} I{_r(-radius):.3f} J0.000",
        f"G1 X{_r(cx):.3f} Y{_r(cy):.3f}",
        f"G0 Z{_r(clear):.3f}",
    ]
    return lines


def _levels(top: float, bottom: float, count: int) -> list[float]:
    return [_r(top - (top - bottom) * k / count) for k in range(1, count + 1)]


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    lay = _layout(g)
    work = lay["work"]
    p = plan["parameters"]

    # --- tools -------------------------------------------------------------
    d1 = _shop_tool(plan, shop, "em-quarter")["diameter_mm"]
    d2 = _shop_tool(plan, shop, "em-eighth")["diameter_mm"]
    d31 = _shop_tool(plan, shop, "drill-31")["diameter_mm"]
    db = _shop_tool(plan, shop, "drill-b")["diameter_mm"]
    dream = _shop_tool(plan, shop, "reamer")["diameter_mm"]
    d7 = _shop_tool(plan, shop, "drill-7")["diameter_mm"]
    dl = _shop_tool(plan, shop, "drill-l")["diameter_mm"]
    d25 = _shop_tool(plan, shop, "drill-25")["diameter_mm"]
    d43 = _shop_tool(plan, shop, "drill-43")["diameter_mm"]
    r1 = d1 / 2
    if not g["holddown_band"][0] - 1e-6 <= d31 <= g["holddown_band"][1]:
        raise ValueError(
            f"#31 Ø{d31} outside the hold-down's band {g['holddown_band']}"
        )
    if not g["post_band"][0] - 1e-6 <= d7 <= g["post_band"][1]:
        raise ValueError(f"#7 Ø{d7} outside the post taps' drill band {g['post_band']}")
    if not g["pivot_band"][0] - 1e-6 <= dream <= g["pivot_band"][1]:
        raise ValueError(f"the reamer Ø{dream} is outside the pivot bore's band")
    _agree(plan, "ream_allowance_mm", dream - db)
    if not 0.15 <= dream - db <= 0.4:
        raise ValueError("the B drill leaves the reamer outside .006-.016 in to take")
    for name, dia in (
        ("ends", d1),
        ("outline rough", d1),
        ("outline finish", d1),
        ("relief", d1),
        ("holddown cbore", d2),
        ("holddown drill", d31),
        ("pivot drill", db),
        ("pivot redrill", db),
        ("pivot ream", dream),
        ("post drills", d7),
        ("plate clearance", dl),
        ("screw seats", d25),
        ("holddown seat", d43),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not its tool's Ø{dia}")
    spot_dia = p["spot_dia_mm"]
    if not spot_dia < min(d31, db, d7, dl, d25):
        raise ValueError("the spot is not under every drill it starts")
    for name in ("hole spots", "plate spots"):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), spot_dia, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not process.spot_dia_mm")
    # Through the part's holes to the plate below (Setup 4): each drill and
    # tap clear of the hole it passes.
    for what, tool, hole in (
        ("#43 in the hold-down hole", d43, d31),
        ("#4-40 tap in the hold-down hole", TAP_4_40_MM, d31),
        ("#25 in the wedge hole", d25, d7),
        ("#10-24 tap in the wedge hole", TAP_10_24_MM, d7),
        ("#25 in the pivot bore", d25, dream),
        ("#10-24 tap in the pivot bore", TAP_10_24_MM, dream),
    ):
        if tool >= hole - 0.15:
            raise ValueError(f"the {what} would touch its wall")

    # --- the bar and the blank ---------------------------------------------
    t_min, t_max = g["thickness_band"]
    _agree(plan, "blank_thickness_min_mm", t_min)
    _agree(plan, "blank_thickness_max_mm", t_max)
    width = p["blank_width_in"] * IN
    outline = _outline(g, work)
    pts_w = {name: work(g[name]) for name in ("ne", "nw", "sw", "se")}
    e_y = pts_w["ne"][1]
    if not math.isclose(e_y, pts_w["se"][1], abs_tol=1e-6):
        raise ValueError("edge E does not lie along X")
    # The plate's extent along E (X) and across (from E), arcs included.
    xs, ys = [], []
    for e in outline[1:-1]:
        for q in (e["start"], e["end"]):
            xs.append(q[0])
            ys.append(q[1])
        if "centre" in e and not e.get("cw"):
            c, rad = e["centre"], math.dist(e["centre"], e["start"])
            a0 = math.atan2(e["start"][1] - c[1], e["start"][0] - c[0])
            a1 = math.atan2(e["end"][1] - c[1], e["end"][0] - c[0])
            sweep = (a1 - a0) % (2 * math.pi)
            for k in range(4):
                a = k * math.pi / 2
                if (a - a0) % (2 * math.pi) <= sweep:
                    xs.append(c[0] + rad * math.cos(a))
                    ys.append(c[1] + rad * math.sin(a))
    north_x, south_x = max(xs), min(xs)
    across = max(ys) - e_y
    _agree(plan, "plate_across_mm", across)
    if across > width - 2.0:
        raise ValueError(
            "the plate laid on E does not fit the bar's width with 2 mm to spare"
        )
    _agree(plan, "edge_e_from_pivot_mm", -e_y)
    _agree(plan, "lay_angle_deg", math.degrees(math.atan2(-lay["u"][0], -lay["u"][1])))
    # The faced blank: the plate's extent along E plus the end wastes.
    w_n, w_s = p["north_waste_mm"], p["south_waste_mm"]
    faced = north_x - south_x + w_n + w_s
    _agree(plan, "faced_length_mm", faced)
    x_north_end, x_south_end = north_x + w_n, south_x - w_s  # Setup-4 X
    # The sawn blank: X0 its south end, faced e_s in; the north end faced
    # the rest; every sawn length leaves something to face at each end.
    e_s = p["south_face_mm"]
    _agree(plan, "blank_length_min_mm", p["blank_length_in"] * IN)
    _agree(plan, "blank_length_max_mm", p["blank_length_max_in"] * IN)
    north_cut_min = p["blank_length_min_mm"] - e_s - faced
    north_cut_max = p["blank_length_max_mm"] - e_s - faced
    _agree(plan, "north_face_max_mm", north_cut_max)
    if north_cut_min < 0.5 or e_s < 0.5:
        raise ValueError("a sawn end is left with under .020 to face")
    if max(north_cut_max, e_s) > p["end_woc_max_mm"] + 1e-6:
        raise ValueError("an end facing pass takes more than process.end_woc_max_mm")

    # The waste corners the outline must take whole (no sliver): the blank's
    # NE, SE and SW corners within the rough pass's reach, the SE through
    # the corner clearing as well.
    finish_stock = p["finish_stock_mm"]
    d_rough, d_clear = r1 + finish_stock, p["clear_offset_mm"]
    reach = d_rough + r1
    corners = {
        "NE": (x_north_end, e_y),
        "SE": (x_south_end, e_y),
        "SW": (x_south_end, e_y + width),
    }

    def distance(q, elements):
        best = math.inf
        for e in elements:
            s, t_ = e["start"], e["end"]
            if "centre" in e:
                c = e["centre"]
                rad = math.dist(c, s)
                a = math.atan2(q[1] - c[1], q[0] - c[0])
                a0 = math.atan2(s[1] - c[1], s[0] - c[0])
                a1 = math.atan2(t_[1] - c[1], t_[0] - c[0])
                sweep = (a1 - a0) % (2 * math.pi)
                if (a - a0) % (2 * math.pi) <= sweep:
                    best = min(best, abs(math.dist(c, q) - rad))
                best = min(best, math.dist(q, s), math.dist(q, t_))
            else:
                dd = _sub(t_, s)
                k = max(0.0, min(1.0, _dot(_sub(q, s), dd) / _dot(dd, dd)))
                best = min(best, math.dist(q, _add(s, dd, k)))
        return best

    milled = outline[1:-1]
    for name in ("NE", "SW"):
        if distance(corners[name], milled) > reach - SLIVER_MARGIN_MM:
            raise ValueError(f"the blank's {name} corner lies past the outline's reach")
    chamfer = next(e for e in outline if e["name"] == "chamfer")
    if distance(corners["SE"], [chamfer]) > d_clear + r1 - SLIVER_MARGIN_MM:
        raise ValueError("the blank's SE corner lies past the corner clearing's reach")
    if d_clear - r1 > reach - SLIVER_MARGIN_MM:
        raise ValueError("the corner clearing leaves a ridge short of the rough pass")
    # The north strip between the faced end and the north edge, and the
    # west waste where it is narrower than the reach, go whole into chips.
    north_edge = next(e for e in outline if e["name"] == "north edge")
    for q in (north_edge["start"], north_edge["end"]):
        if x_north_end - q[0] > reach - SLIVER_MARGIN_MM:
            raise ValueError("the north strip is wider than the outline's reach")

    # --- Setup 2 (vise, underside up) --------------------------------------
    # S2 = S4 turned over about X and shifted: X2 = X4 - x_south_end + e_s,
    # Y2 = -(Y4 - e_y), Z2 = -(model y).
    shift = -x_south_end + e_s

    def s2(q):
        return (_r(q[0] + shift), _r(-(q[1] - e_y)))

    pivot4 = (0.0, 0.0)
    holes4 = {
        "pivot": pivot4,
        "holddown": work(g["holddown"]),
        "post_west": work(g["post_west"]),
        "post_east": work(g["post_east"]),
        "wedge": (p["wedge_x_mm"], p["wedge_y_mm"]),
    }
    holes2 = {k: s2(v) for k, v in holes4.items()}
    _agree(plan, "pivot_x2_mm", holes2["pivot"][0])
    _agree(plan, "holddown_x2_mm", holes2["holddown"][0])
    # The wedge screw: in the west waste, its head clear of the rough pass's
    # swath and of the bar's far edge.
    west = next(e for e in outline if e["name"] == "west edge north")
    wd = _unit(_sub(west["end"], west["start"]))
    off = _cross(wd, _sub(holes4["wedge"], west["start"]))  # right of travel: out
    head_r = HEAD_10_24_MM[0] / 2
    if -off < reach + head_r + JAW_CLEARANCE_MM:
        raise ValueError("the wedge screw's head lies in the outline's swath")
    if e_y + width - holes4["wedge"][1] < head_r + JAW_CLEARANCE_MM:
        raise ValueError("the wedge screw's head overhangs the bar's far edge")
    if not x_south_end < holes4["wedge"][0] < x_north_end:
        raise ValueError("the wedge screw is off the blank")

    jaw_w = p["vise_jaw_width_mm"]
    _agree(
        plan, "s2_jaw_top_mm", p["vise_jaw_height_mm"] - p["parallel_height_mm"] - t_min
    )
    jaw_top2 = p["s2_jaw_top_mm"]
    if p["vise_jaw_height_mm"] - p["parallel_height_mm"] < t_max:
        raise ValueError("the parallels lift the bar's top over the jaws")
    ov_min, ov_max = p["s2_overhang_min_mm"], p["s2_overhang_max_mm"]
    _agree(
        plan,
        "s2_overhang_mm",
        (p["blank_length_in"] + p["blank_length_max_in"]) / 2 * IN / 2 - jaw_w / 2,
    )
    if not ov_min < p["s2_overhang_mm"] < ov_max:
        raise ValueError("the nominal overhang lies outside its band")
    # Every hole and both end passes stand off the jaws' ends: the south
    # features left of the jaws at the least overhang, the north ones right
    # of them at the most.
    hole_r = {
        "pivot": db / 2,
        "holddown": g["cbore_dia"] / 2,
        "post_west": d7 / 2,
        "post_east": d7 / 2,
        "wedge": d7 / 2,
    }
    south_reach = max(holes2[k][0] + hole_r[k] for k in ("post_west", "post_east"))
    north_reach = min(holes2[k][0] - hole_r[k] for k in ("pivot", "holddown", "wedge"))
    _agree(plan, "s2_south_reach_mm", south_reach)
    _agree(plan, "s2_north_reach_mm", north_reach)
    if south_reach + JAW_CLEARANCE_MM > ov_min:
        raise ValueError("a south hole reaches the jaws at the least overhang")
    if north_reach - JAW_CLEARANCE_MM < ov_max + jaw_w:
        raise ValueError("a north hole reaches the jaws at the most overhang")
    clear2 = jaw_top2 + CLEAR_MM
    through2 = -(t_max + p["through_past_mm"])
    _agree(plan, "end_bottom_mm", through2)
    tips = {
        "#31": -(t_max + p["drill_past_mm"] + _point(d31)),
        "B": -(t_max + p["drill_past_mm"] + _point(db)),
        "#7": -(t_max + p["drill_past_mm"] + _point(d7)),
    }
    # The ream is Setup 4's, the bar flat on the spoil plate (its thrust
    # bends nothing there): the B drill first re-enters its hole and runs
    # drill_past_mm past the reamer's reach into the plate, then the reamer
    # takes the bore with its full diameter ream_past_mm into the plate.
    ream_tip = -p["ream_past_mm"]
    import cam_nc

    if p["ream_past_mm"] <= cam_nc.ream_full_diameter_past_min_mm(plan, "reamer"):
        raise ValueError(
            "the reamer's full diameter does not reach the bar's underside (cnc.ream-full-diameter)"
        )
    redrill_tip = -(p["ream_past_mm"] + p["drill_past_mm"] + _point(db))
    _agree(plan, "drill_31_tip_mm", tips["#31"])
    _agree(plan, "drill_b_tip_mm", tips["B"])
    _agree(plan, "drill_7_tip_mm", tips["#7"])
    _agree(plan, "ream_tip_mm", ream_tip)
    _agree(plan, "pivot_redrill_tip_mm", redrill_tip)
    for what, tip, projection in (
        ("#31 in the chuck", tips["#31"], p["drill_projection_min_mm"]),
        ("B in the chuck", tips["B"], p["drill_projection_min_mm"]),
        ("#7 in the chuck", tips["#7"], p["drill_projection_min_mm"]),
        ("1/4 in end mill in its collet", through2, p["quarter_projection_min_mm"]),
        (
            "1/8 in end mill in its collet",
            -g["cbore_depth"],
            p["eighth_projection_min_mm"],
        ),
    ):
        if tip + projection < jaw_top2 + JAW_CLEARANCE_MM - 1e-6:
            raise ValueError(f"the {what}'s nose reaches the jaw tops")
    # The counterbore: the 1/8 in end mill's centre on a circle of
    # cbore_path_radius about the hold-down, down a helix to its depth.
    cb_r = (g["cbore_dia"] - d2) / 2
    _agree(plan, "cbore_path_radius_mm", cb_r)
    if cb_r <= 0 or cb_r * 2 + d2 > g["cbore_band"][1] or cb_r - d2 / 2 > d31 / 2:
        raise ValueError(
            "the counterbore's circle is outside its band or leaves a ring"
        )
    if not g["cbore_depth_band"][0] <= g["cbore_depth"] <= g["cbore_depth_band"][1]:
        raise ValueError("the counterbore's nominal depth is outside its band")
    # The ends: the 1/4 in end mill's side square across the bar in levels,
    # beside the bar at both edges.
    end_levels = _levels(0.0, through2, int(p["end_levels"]))
    _agree(plan, "end_level_mm", -through2 / p["end_levels"])
    if not math.isclose(
        _cut(plan, "ends", "axial_doc_mm"), p["end_level_mm"], abs_tol=1e-6
    ):
        raise ValueError("'ends' axial_doc_mm is not process.end_level_mm")
    y_e, y_w = r1 + JAW_CLEARANCE_MM, -(width + r1 + JAW_CLEARANCE_MM)
    x_s_face, x_n_face = e_s, e_s + faced
    ends = [f"G0 Z{_r(clear2):.3f}"]
    for x_c, y0, y1 in ((x_s_face - r1, y_e, y_w), (x_n_face + r1, y_w, y_e)):
        for z in end_levels:
            ends += [
                f"G0 {_xy((x_c, y0))}",
                f"G0 Z{_r(SAFE_MM):.3f}",
                f"G1 Z{z:.3f} F{{feed}}",
                f"G1 {_xy((x_c, y1))}",
                f"G0 Z{_r(clear2):.3f}",
            ]
    spot_z = -_spot_depth(spot_dia)
    spots2: list[str] = []
    for key in ("post_east", "post_west", "pivot", "holddown", "wedge"):
        spots2 += _spot(holes2[key], spot_z, clear2, SAFE_MM)
    post_drills: list[str] = []
    for key in ("post_east", "post_west", "wedge"):
        post_drills += _pecked(holes2[key], 0.0, tips["#7"], math.inf, clear2, SAFE_MM)

    # --- Setup 3 (the bare spoil plate on the table) -----------------------
    pl_x, pl_y = p["pivot_plate_x_mm"], p["pivot_plate_y_mm"]
    plate_len, plate_wid, plate_t = (
        p["spoil_plate_length_mm"],
        p["spoil_plate_width_mm"],
        p["spoil_plate_thickness_mm"],
    )

    def s3(q):
        return (_r(q[0] + pl_x), _r(q[1] + pl_y))

    # The bar centred on the plate's width, the plate's extent along it
    # centred on its length.
    _agree(plan, "pivot_plate_y_mm", (plate_wid - width) / 2 - e_y)
    _agree(plan, "pivot_plate_x_mm", plate_len / 2 - (x_north_end + x_south_end) / 2)
    block_len = BLOCK_MM[0]
    blocks = [
        _box(f"1-2-3 block {k}", x, y, -plate_t)
        for k, (x, y) in enumerate(
            (
                ((0.0, block_len), (0.0, BLOCK_MM[1])),
                ((0.0, block_len), (plate_wid - BLOCK_MM[1], plate_wid)),
                ((plate_len - block_len, plate_len), (0.0, BLOCK_MM[1])),
                (
                    (plate_len - block_len, plate_len),
                    (plate_wid - BLOCK_MM[1], plate_wid),
                ),
                # The fifth block under the plate's middle, unclamped.
                (
                    (plate_len / 2 - block_len / 2, plate_len / 2 + block_len / 2),
                    (plate_wid / 2 - BLOCK_MM[1] / 2, plate_wid / 2 + BLOCK_MM[1] / 2),
                ),
            ),
            1,
        )
    ]
    clamps = [
        _box(
            f"step clamp {k}",
            (x - CLAMP_MM[0] / 2, x + CLAMP_MM[0] / 2),
            (y - CLAMP_MM[1] / 2, y + CLAMP_MM[1] / 2),
            CLAMP_MM[2],
        )
        for k, (x, y) in enumerate(
            (
                (block_len / 2, BLOCK_MM[1] / 2),
                (block_len / 2, plate_wid - BLOCK_MM[1] / 2),
                (plate_len - block_len / 2, BLOCK_MM[1] / 2),
                (plate_len - block_len / 2, plate_wid - BLOCK_MM[1] / 2),
            ),
            1,
        )
    ]
    clear3 = CLAMP_MM[2] + CLEAR_MM
    plate_tip = -(plate_t + p["drill_past_mm"] + _point(dl))
    _agree(plan, "drill_l_tip_mm", plate_tip)
    table = -(plate_t + BLOCK_MM[2])
    if plate_tip < table + JAW_CLEARANCE_MM:
        raise ValueError("the L drill reaches the table")
    posts3 = [s3(holes4["post_east"]), s3(holes4["post_west"])]
    # Every hole through the plate, and the 1/4-20 screws' heads under it
    # (Ø.375), stand off the middle block.
    middle = blocks[-1]
    for name in ("post_east", "post_west", "pivot", "wedge"):
        q = s3(holes4[name])
        gap = max(
            middle["x"][0] - q[0],
            q[0] - middle["x"][1],
            middle["y"][0] - q[1],
            q[1] - middle["y"][1],
        )
        if gap < 0.375 * IN / 2 + JAW_CLEARANCE_MM:
            raise ValueError(
                f"the {name} hole through the plate lies over the middle block"
            )
    # The part's footprint on the plate stands clear of the blocks.
    for name, x in (("south", x_south_end - reach), ("north", x_north_end + reach)):
        x3 = x + pl_x
        if (
            not block_len + JAW_CLEARANCE_MM
            < x3
            < plate_len - block_len - JAW_CLEARANCE_MM
        ):
            raise ValueError(f"the outline's {name} end reaches the blocks")
    plate_spots: list[str] = []
    plate_clearance: list[str] = []
    for q in posts3:
        plate_spots += _spot(q, spot_z, clear3, SAFE_MM)
        plate_clearance += _pecked(q, 0.0, plate_tip, math.inf, clear3, SAFE_MM)
    # The screws' float: the clearance hole round each 1/4-20 screw lets
    # the plate be trammed on E.
    _agree(plan, "screw_float_mm", (dl - 0.25 * IN) / 2)

    # --- Setup 4 (the part on the plate, G54 on the pivot) ----------------
    part_top = t_max
    clear4 = part_top + HEAD_10_24_MM[1] + CLEAR_MM
    r_plane4 = part_top + SAFE_MM
    seat_43_tip = -p["holddown_seat_depth_mm"]
    seat_25_tip = -(plate_t + p["drill_past_mm"] + _point(d25))
    _agree(plan, "drill_25_tip_mm", seat_25_tip)
    # The 4-40 plug tap's point runs tap_4_40_depth_mm into the plate
    # (process.tap_4_40_turns at 40 a inch), short of the #43's full
    # diameter by .020; its full threads (five chamfer threads back) reach
    # past the 1/2 in screw's end on the thinnest bar.
    _agree(plan, "tap_4_40_depth_mm", p["tap_4_40_turns"] * IN / 40)
    if p["tap_4_40_depth_mm"] > -seat_43_tip - _point(d43) - 0.5:
        raise ValueError("the 4-40 tap's point reaches the #43 seat's cone")
    if p["tap_4_40_depth_mm"] - 5 * IN / 40 < p["holddown_screw_length_mm"] - t_min:
        raise ValueError("the 4-40 screw runs past the seat's full threads")
    if seat_43_tip < -(plate_t - 1.0):
        raise ValueError("the #43 seat runs out under the plate")
    holddown_seat = _pecked(
        holes4["holddown"], 0.0, seat_43_tip, p["peck_43_mm"], clear4, r_plane4
    )
    screw_seats = _pecked(
        holes4["wedge"], 0.0, seat_25_tip, p["peck_25_mm"], clear4, r_plane4
    )
    blocks4 = [
        {**b, "x": [x - pl_x for x in b["x"]], "y": [y - pl_y for y in b["y"]]}
        for b in blocks
    ]
    clamps4 = [
        {**b, "x": [x - pl_x for x in b["x"]], "y": [y - pl_y for y in b["y"]]}
        for b in clamps
    ]

    # The outline: the corner clearing first (every level), then the rough
    # pass at finish_stock outside the finish, level by level, then the
    # finish pass in its levels; each level plunged at feed beside edge E,
    # in air.
    through4 = -p["outline_through_mm"]
    _agree(plan, "outline_bottom_mm", through4)
    rough_levels = _levels(part_top, through4, int(p["outline_levels"]))
    finish_levels = _levels(part_top, through4, int(p["finish_levels"]))
    _agree(plan, "outline_level_mm", (part_top - through4) / p["outline_levels"])
    _agree(plan, "finish_level_mm", (part_top - through4) / p["finish_levels"])
    if not math.isclose(
        _cut(plan, "outline rough", "axial_doc_mm"), p["outline_level_mm"], abs_tol=1e-6
    ) or not math.isclose(
        _cut(plan, "outline finish", "axial_doc_mm"), p["finish_level_mm"], abs_tol=1e-6
    ):
        raise ValueError("an outline cut's axial_doc_mm is not its process level")
    if not math.isclose(
        _cut(plan, "outline finish", "radial_woc_mm"), finish_stock, abs_tol=1e-6
    ):
        raise ValueError(
            "'outline finish' radial_woc_mm is not process.finish_stock_mm"
        )
    # Clearing: a straight pass parallel to the chamfer at d_clear outside
    # it, from beside the faced south end to beside edge E.
    cd = _unit(_sub(chamfer["end"], chamfer["start"]))
    c0 = _add(chamfer["start"], _right(cd), d_clear)
    c_start = _meet(c0, cd, (x_south_end - r1 - JAW_CLEARANCE_MM, 0.0), (0.0, 1.0))
    c_end = _meet(c0, cd, (0.0, e_y - r1 - JAW_CLEARANCE_MM), (1.0, 0.0))
    path: list[str] = [f"G0 Z{_r(clear4):.3f}"]
    for z in rough_levels:
        path += [
            f"G0 {_xy(c_start)}",
            f"G0 Z{_r(r_plane4):.3f}",
            f"G1 Z{z:.3f} F{{feed}}",
            f"G1 {_xy(c_end)}",
            f"G0 Z{_r(clear4):.3f}",
        ]
    lead = outline[0]
    for offset, levels in ((d_rough, rough_levels), (r1, finish_levels)):
        start = _add(lead["start"], _right(_direction(lead, False)), offset)
        for z in levels:
            path += [
                f"G0 {_xy(start)}",
                f"G0 Z{_r(r_plane4):.3f}",
                f"G1 Z{z:.3f} F{{feed}}",
                *_offset_path(outline, offset, z),
                f"G0 Z{_r(clear4):.3f}",
            ]
    # The relief: Z0 its floor (the shoulder screw's length above the
    # plate); a U of the 1/4 in end mill's centre at the relief's radius
    # less its own, in from beside the north edge along the east side, round
    # the pivot clockwise, out along the west side. Its walls run along the
    # model's length (north), which lies lay_angle_deg off edge E, so the
    # runs follow work() of that direction, not the work frame's X.
    rr = g["relief_r"] - r1
    _agree(plan, "relief_path_radius_mm", rr)
    if rr <= 0 or rr > r1:
        raise ValueError("the relief's U leaves a ridge between its two runs")
    north_relief = max(
        q[0]
        for e in outline[1:5]
        for q in (e["start"], e["end"])
        if abs(q[1]) <= g["relief_r"] + 1e-6
    )
    x_in = north_relief + r1 + JAW_CLEARANCE_MM + 0.5
    along = _unit(work((0.0, 1.0)))  # model north in the work frame
    across = (-along[1], along[0])  # model west
    run = x_in / along[0]
    east_pivot = _add((0.0, 0.0), across, -rr)
    west_pivot = _add((0.0, 0.0), across, rr)
    east_in = _add(east_pivot, along, run)
    west_out = _add(west_pivot, along, run)
    # The U's extent: its four ends and the circle's quadrant points the
    # clockwise arc from east_pivot to west_pivot passes.
    a_east = math.atan2(east_pivot[1], east_pivot[0])
    sweep = (a_east - math.atan2(west_pivot[1], west_pivot[0])) % math.tau
    relief_extent = [east_in, east_pivot, west_pivot, west_out] + [
        (rr * math.cos(k), rr * math.sin(k))
        for k in (0.0, math.pi / 2, math.pi, -math.pi / 2)
        if (a_east - k) % math.tau <= sweep
    ]
    # Owner ruling 2026-11-22 (#3363): a bar thinner than the shoulder takes
    # the relief at the sheet's REF depth below its top (Z0 the floor, the
    # top at relief_ref_mm); a thicker bar takes it fitted to the shoulder
    # (Z0 the shoulder's length over the plate, the top at most the
    # thickest bar less the shortest shoulder). The file is the same: one
    # level at Z0, the bar's top at most relief_stock_top_mm above it.
    _agree(plan, "relief_ref_mm", g["relief_ref"])
    relief_top = max(t_max - p["shoulder_min_mm"], p["relief_ref_mm"])
    _agree(plan, "relief_stock_top_mm", relief_top)
    # The pivot-end edge's station band, printed in the controller's mm.
    _agree(plan, "north_station_min_mm", g["north_station"][0])
    _agree(plan, "north_station_max_mm", g["north_station"][1])
    # Above the relief's floor the bar's top stands at most relief_top, so
    # the screw heads at most relief_top plus their height.
    clear10 = relief_top + HEAD_10_24_MM[1] + CLEAR_MM
    relief = [
        f"G0 Z{_r(clear10):.3f}",
        f"G0 {_xy(east_in)}",
        f"G0 Z{_r(relief_top + SAFE_MM):.3f}",
        "G1 Z0.000 F{feed}",
        f"G1 {_xy(east_pivot)}",
        f"G2 {_xy(west_pivot)} I{_r(-east_pivot[0]):.3f} J{_r(-east_pivot[1]):.3f}",
        f"G1 {_xy(west_out)}",
        f"G0 Z{_r(clear10):.3f}",
    ]

    # Tap stack ceiling for the vise setup: spindle-to-table maximum less
    # the tool-change clearance, the vise bed, the parallels, the bar and the
    # collet's gauge, rounded down to .01 in; the tap in its wrench reaches
    # at most that less the tap guide's 3 1/8 in, rounded down to .01 in.
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["parallel_height_mm"]
        - t_max
        - p["r8_collet_gauge_mm"]
    )
    _agree(plan, "tap_stack_max_mm", math.floor(stack / 0.254 + 1e-9) * 0.254)
    _agree(
        plan,
        "tap_wrench_reach_max_mm",
        math.floor((p["tap_stack_max_mm"] - 3.125 * IN) / 0.254 + 1e-9) * 0.254,
    )

    # --- speeds -----------------------------------------------------------
    for key, setting_name in (
        ("em_quarter", QUARTER_SETTING),
        ("em_eighth", EIGHTH_SETTING),
    ):
        setting = shop["settings"][setting_name]
        _agree(plan, f"{key}_rpm", setting["rpm"])
        _agree(
            plan,
            f"{key}_feed_per_min_mm",
            # The setting's printed feed (in/min to .1, prechips speeds).
            round(
                setting["rpm"]
                * setting["flutes"]
                * setting["chip_load_mm_per_tooth"]
                / IN,
                1,
            )
            * IN,
        )
    speeds = {}
    for name, rpm_key, feed_key in (
        ("ends", "em_quarter_rpm", "em_quarter_feed_per_min_mm"),
        ("outline rough", "em_quarter_rpm", "em_quarter_feed_per_min_mm"),
        ("outline finish", "em_quarter_rpm", "em_quarter_feed_per_min_mm"),
        ("relief", "em_quarter_rpm", "em_quarter_feed_per_min_mm"),
        ("holddown cbore", "em_eighth_rpm", "em_eighth_feed_per_min_mm"),
        ("hole spots", "spot_rpm", "spot_feed_per_min_mm"),
        ("plate spots", "spot_rpm", "spot_feed_per_min_mm"),
        ("holddown drill", "drill_31_rpm", "drill_31_feed_per_min_mm"),
        ("pivot drill", "drill_b_rpm", "drill_b_feed_per_min_mm"),
        ("pivot redrill", "drill_b_rpm", "drill_b_feed_per_min_mm"),
        ("pivot ream", "ream_rpm", "ream_feed_per_min_mm"),
        ("post drills", "drill_7_rpm", "drill_7_feed_per_min_mm"),
        ("plate clearance", "plate_drill_rpm", "drill_l_feed_per_min_mm"),
        ("screw seats", "plate_drill_rpm", "drill_25_feed_per_min_mm"),
        ("holddown seat", "plate_drill_rpm", "drill_43_feed_per_min_mm"),
    ):
        op, cut = _op_with_cut(plan, name)
        rpm = _resolve(plan, cut.get("rpm", op.get("rpm", p[rpm_key])), f"'{name}' rpm")
        if not math.isclose(rpm, p[rpm_key]):
            raise ValueError(f"'{name}' rpm {rpm:g} is not process.{rpm_key}")
        if "feed_mm_min" in cut:
            feed = _cut(plan, name, "feed_mm_min")
            if not math.isclose(feed, p[feed_key], abs_tol=1e-6):
                raise ValueError(f"'{name}' feed_mm_min is not process.{feed_key}")
        speeds[name] = (p[rpm_key], p[feed_key])
    # Holes at most 3 diameters deep go in one feed (prechips drill_pecking:
    # no peck without a reason there); the plate's #25 and #43 holes peck.
    for name in (
        "holddown drill",
        "pivot drill",
        "pivot redrill",
        "post drills",
        "plate clearance",
    ):
        if _op_with_cut(plan, name)[0]["peck"] != "none":
            raise ValueError(f"'{name}' is one feed: peck = \"none\"")
    for name, step in (
        ("screw seats", p["peck_25_mm"]),
        ("holddown seat", p["peck_43_mm"]),
    ):
        if _op_with_cut(plan, name)[0]["peck"] != {"step_mm": step, "retract": "full"}:
            raise ValueError(f"'{name}' peck is not its process peck with full retract")

    names = {t_["id"]: t_["name"] for t_ in plan["tools"]}
    numbers = {
        t_["id"]: n
        for n, t_ in enumerate((t_ for t_ in plan["tools"] if t_["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    def section(
        tool: str,
        dia: float,
        cut: str,
        shape: str,
        frame: str,
        key: str,
        label: str,
        lines: list,
    ) -> dict[str, Any]:
        rpm, feed = speeds[cut]
        spec = {
            "tool": tool,
            "dia": dia,
            "shape": shape,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
            "frame": frame,
            "label": cut,
            "ops": [[key, label, lines]],
            "stock": stocks[frame],
        }
        if shape == "drill":
            spec["tip_angle"] = (
                CENTRE_DRILL["point_deg"] if tool == "spot" else DRILL_POINT_DEG
            )
        else:
            spec["flutes"] = 3
        return spec

    # Frames for the STEP (model (x, y, z) -> work): Setup 4's turns the
    # model's top view onto X along E; Setup 2's turns it over about X;
    # Setup 3's shifts Setup 4's to the plate's corner.
    u, n = lay["u"], lay["n"]
    ax4 = [[-u[0], 0.0, -u[1]], [n[0], 0.0, n[1]], [0.0, 1.0, 0.0]]
    ax2 = [[-u[0], 0.0, -u[1]], [-n[0], 0.0, -n[1]], [0.0, -1.0, 0.0]]
    o2 = _add(_add((0.0, 0.0), (-u[0], -u[1]), -shift), n, e_y)
    o3 = _add(_add((0.0, 0.0), (-u[0], -u[1]), -pl_x), n, -pl_y)
    frames = {
        "holes": {"origin": [o2[0], 0.0, o2[1]], "axes": ax2},
        "plate": {"origin": [o3[0], 0.0, o3[1]], "axes": ax4},
        "part": {"origin": [0.0, 0.0, 0.0], "axes": ax4},
    }
    stocks = {
        "holes": ((0.0, p["blank_length_max_mm"]), (-width, 0.0), (-t_max, 0.0)),
        "plate": ((0.0, plate_len), (0.0, plate_wid), (-plate_t, 0.0)),
        "part": (
            (x_south_end, x_north_end),
            (e_y, e_y + width),
            (0.0, t_max),
        ),
    }
    jobs = [
        section(
            "em-quarter", d1, "ends", "endmill", "holes", "ends", "face both ends", ends
        ),
        section(
            "spot",
            CENTRE_DRILL["body_mm"],
            "hole spots",
            "drill",
            "holes",
            "hole_spots",
            "spot every hole",
            spots2,
        ),
        section(
            "drill-31",
            d31,
            "holddown drill",
            "drill",
            "holes",
            "holddown_drill",
            "drill #31 through",
            _pecked(holes2["holddown"], 0.0, tips["#31"], math.inf, clear2, SAFE_MM),
        ),
        section(
            "em-eighth",
            d2,
            "holddown cbore",
            "endmill",
            "holes",
            "holddown_cbore",
            "counterbore helix",
            _helix(
                holes2["holddown"],
                cb_r,
                p["cbore_helix_pitch_mm"],
                -g["cbore_depth"],
                clear2,
            ),
        ),
        section(
            "drill-b",
            db,
            "pivot drill",
            "drill",
            "holes",
            "pivot_drill",
            "drill B through",
            _pecked(holes2["pivot"], 0.0, tips["B"], math.inf, clear2, SAFE_MM),
        ),
        section(
            "drill-7",
            d7,
            "post drills",
            "drill",
            "holes",
            "post_drills",
            "drill #7 through",
            post_drills,
        ),
        section(
            "spot",
            CENTRE_DRILL["body_mm"],
            "plate spots",
            "drill",
            "plate",
            "plate_spots",
            "spot the post screws' holes",
            plate_spots,
        ),
        section(
            "drill-l",
            dl,
            "plate clearance",
            "drill",
            "plate",
            "plate_clearance",
            "drill L through the plate",
            plate_clearance,
        ),
        section(
            "drill-b",
            db,
            "pivot redrill",
            "drill",
            "part",
            "pivot_redrill",
            "B drill on into the plate",
            _pecked(pivot4, 0.0, redrill_tip, math.inf, clear4, r_plane4),
        ),
        section(
            "reamer",
            dream,
            "pivot ream",
            "drill",
            "part",
            "pivot_ream",
            "ream .2510 through",
            _reamed(pivot4, ream_tip, clear4, r_plane4),
        ),
        section(
            "drill-43",
            d43,
            "holddown seat",
            "drill",
            "part",
            "holddown_seat",
            "drill #43 into the plate",
            holddown_seat,
        ),
        section(
            "drill-25",
            d25,
            "screw seats",
            "drill",
            "part",
            "screw_seats",
            "drill #25 through the plate",
            screw_seats,
        ),
        section(
            "em-quarter",
            d1,
            "outline rough",
            "endmill",
            "part",
            "outline",
            "outline",
            path,
        ),
        section(
            "em-quarter",
            d1,
            "relief",
            "endmill",
            "part",
            "relief",
            "top relief",
            relief,
        ),
    ]

    def tap_stop(at: tuple[float, float], thread: str, hole: str) -> dict[str, Any]:
        return {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": f"SPINDLE STAYS OFF. NEXT: {thread} TAP IN THE {hole} HOLE",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 {_xy(at)}",
                f"({thread} TAP IN THE {hole} HOLE. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND, THE SPRING FOLLOWING, TO THE TRAVELER'S DEPTH. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": at,
        }

    manual = {
        "post_far_tap_stop": tap_stop(holes2["post_west"], "1/4-20", "FAR POST"),
        "post_near_tap_stop": tap_stop(holes2["post_east"], "1/4-20", "NEAR POST"),
        "holddown_tap_stop": tap_stop(holes4["holddown"], "4-40", "HOLD-DOWN SEAT"),
        "wedge_tap_stop": tap_stop(holes4["wedge"], "10-24", "WEDGE SEAT"),
    }

    # --- keep-outs and expectations ---------------------------------------
    jaw_x = (ov_min, ov_max + jaw_w)
    vise2 = [
        _box("fixed jaw", jaw_x, (0.0, JAW_DEPTH_MM), jaw_top2),
        _box("moving jaw", jaw_x, (-width - JAW_DEPTH_MM, -width), jaw_top2),
        _box("fixed-jaw parallel", jaw_x, (-PARALLEL_THICKNESS_MM, 0.0), -t_min),
        _box(
            "moving-jaw parallel",
            jaw_x,
            (-width, -width + PARALLEL_THICKNESS_MM),
            -t_min,
        ),
    ]
    faced2 = [_box("the faced blank", (x_s_face, x_n_face), (-width, 0.0), 0.0)]
    heads = [
        {
            "name": "#4-40 head",
            "centre": list(holes4["holddown"]),
            "radius": HEAD_4_40_MM[0] / 2,
            "z_top": part_top + HEAD_4_40_MM[1],
        },
        {
            "name": "#10-24 head",
            "centre": list(holes4["wedge"]),
            "radius": HEAD_10_24_MM[0] / 2,
            "z_top": part_top + HEAD_10_24_MM[1],
        },
    ]
    t_ = numbers

    def near(q, size=1.0):
        return [[q[0] - size, q[0] + size], [q[1] - size, q[1] + size]]

    def els(elements):
        return [
            {
                "name": e["name"],
                "start": [_r(e["start"][0]), _r(e["start"][1])],
                "end": [_r(e["end"][0]), _r(e["end"][1])],
                **(
                    {"centre": [_r(e["centre"][0]), _r(e["centre"][1])]}
                    if "centre" in e
                    else {}
                ),
                "tol": 0.02,
            }
            for e in elements
        ]

    tip2_min = min(tips.values())
    expect: list[list[Any]] = [
        [
            "PL01_holes",
            "tool_changes",
            {
                "z_top": jaw_top2,
                "tools": [
                    t_["em-quarter"],
                    t_["spot"],
                    t_["drill-31"],
                    t_["em-eighth"],
                    t_["drill-b"],
                    t_["drill-7"],
                ],
                "loads_first": True,
            },
        ],
        [
            "PL01_holes",
            "spindle",
            {
                "rpm": [
                    [speeds["ends"][0]],
                    [speeds["hole spots"][0]],
                    [speeds["holddown drill"][0]],
                    [speeds["holddown cbore"][0]],
                    [speeds["pivot drill"][0]],
                    [speeds["post drills"][0]],
                ]
            },
        ],
        ["PL01_holes", "pauses", {"z_top": jaw_top2, "count": 0}],
        ["PL01_holes", "depth", {"z_min": _r(min(tip2_min, through2))}],
        ["PL01_holes@0", "keep_out", {"radius": r1, "boxes": vise2 + faced2}],
        [
            "PL01_holes@0",
            "cleared",
            {
                "points": [
                    [x_s_face - 0.01, 0.0],
                    [x_s_face - 0.01, -width],
                    [x_n_face + 0.01, 0.0],
                    [x_n_face + 0.01, -width],
                ],
                "radius": r1,
                "z": _r(through2),
            },
        ],
        ["PL01_holes@0", "air_feed", {"z_top": 0.0}],
        [
            "PL01_holes@1",
            "keep_out",
            {"radius": CENTRE_DRILL["body_mm"] / 2, "boxes": vise2},
        ],
        ["PL01_holes@2", "keep_out", {"radius": d31 / 2, "boxes": vise2}],
        ["PL01_holes@3", "keep_out", {"radius": d2 / 2, "boxes": vise2}],
        ["PL01_holes@4", "keep_out", {"radius": db / 2, "boxes": vise2}],
        ["PL01_holes@5", "keep_out", {"radius": d7 / 2, "boxes": vise2}],
        [
            "PL01_holes@1",
            "holes",
            {
                "centres": [
                    holes2[k]
                    for k in ("post_east", "post_west", "pivot", "holddown", "wedge")
                ],
                "z_bottom": _r(spot_z),
            },
        ],
        [
            "PL01_holes@2",
            "holes",
            {"centres": [holes2["holddown"]], "z_bottom": _r(tips["#31"])},
        ],
        [
            "PL01_holes@4",
            "holes",
            {"centres": [holes2["pivot"]], "z_bottom": _r(tips["B"])},
        ],
        [
            "PL01_holes@5",
            "holes",
            {
                "centres": [holes2[k] for k in ("post_east", "post_west", "wedge")],
                "z_bottom": _r(tips["#7"]),
            },
        ],
        [
            "PL01_holes@3",
            "bounds",
            {
                "window": near(holes2["holddown"], 3.0),
                "x": [
                    _r(holes2["holddown"][0] - cb_r),
                    _r(holes2["holddown"][0] + cb_r),
                ],
                "y": [
                    _r(holes2["holddown"][1] - cb_r),
                    _r(holes2["holddown"][1] + cb_r),
                ],
                "z_min": _r(-g["cbore_depth"]),
                "arc": "G2",
            },
        ],
        ["PL01_holes@3", "air_feed", {"z_top": 0.0}],
    ]
    for k in (1, 2, 4, 5):
        opened = {
            2: [holes2["holddown"]],
            4: [holes2["pivot"]],
            5: [holes2[q] for q in ("post_east", "post_west", "wedge")],
        }.get(k, [])
        expect += [
            [f"PL01_holes@{k}", "rapids_clear", {"z_top": 0.0, "open_holes": opened}],
            [f"PL01_holes@{k}", "vertical_below_top", {"z_top": 0.0}],
            [f"PL01_holes@{k}", "air_feed", {"z_top": 0.0}],
        ]
    for program, key in (
        ("PL02_post_far_tap", "post_west"),
        ("PL03_post_near_tap", "post_east"),
    ):
        expect += [
            [
                program,
                "tap_stop",
                {
                    "tool": t_["tap-guide"],
                    "at": holes2[key],
                    "machine_top": MACHINE_Z_TOP_MM,
                },
            ],
            [program, "air_feed", {"z_top": 0.0}],
        ]
    plate_boxes = blocks + clamps
    expect += [
        [
            "PL04_plate_holes",
            "tool_changes",
            {
                "z_top": CLAMP_MM[2],
                "tools": [t_["spot"], t_["drill-l"]],
                "loads_first": True,
            },
        ],
        [
            "PL04_plate_holes",
            "spindle",
            {"rpm": [[speeds["plate spots"][0]], [speeds["plate clearance"][0]]]},
        ],
        ["PL04_plate_holes", "pauses", {"z_top": CLAMP_MM[2], "count": 0}],
        ["PL04_plate_holes", "depth", {"z_min": _r(plate_tip)}],
        ["PL04_plate_holes@0", "holes", {"centres": posts3, "z_bottom": _r(spot_z)}],
        ["PL04_plate_holes@1", "holes", {"centres": posts3, "z_bottom": _r(plate_tip)}],
        [
            "PL04_plate_holes@0",
            "keep_out",
            {"radius": CENTRE_DRILL["body_mm"] / 2, "boxes": plate_boxes},
        ],
        ["PL04_plate_holes@1", "keep_out", {"radius": dl / 2, "boxes": plate_boxes}],
        ["PL04_plate_holes@1", "rapids_clear", {"z_top": 0.0, "open_holes": posts3}],
    ]
    for k in (0, 1):
        expect += [
            [f"PL04_plate_holes@{k}", "vertical_below_top", {"z_top": 0.0}],
            [f"PL04_plate_holes@{k}", "air_feed", {"z_top": 0.0}],
        ]
    seats = [holes4["wedge"]]
    part_boxes = blocks4 + clamps4
    expect += [
        [
            "PL05_seat_drills",
            "tool_changes",
            {
                "z_top": clear4 - CLEAR_MM,
                "tools": [t_["drill-b"], t_["reamer"], t_["drill-43"], t_["drill-25"]],
                "loads_first": True,
            },
        ],
        [
            "PL05_seat_drills",
            "spindle",
            {
                "rpm": [
                    [speeds["pivot redrill"][0]],
                    [speeds["pivot ream"][0]],
                    [speeds["holddown seat"][0]],
                    [speeds["screw seats"][0]],
                ]
            },
        ],
        ["PL05_seat_drills", "pauses", {"z_top": part_top, "count": 0}],
        [
            "PL05_seat_drills",
            "depth",
            {"z_min": _r(min(seat_25_tip, seat_43_tip, redrill_tip))},
        ],
        [
            "PL05_seat_drills@0",
            "holes",
            {"centres": [pivot4], "z_bottom": _r(redrill_tip)},
        ],
        [
            "PL05_seat_drills@1",
            "holes",
            {"centres": [pivot4], "z_bottom": _r(ream_tip)},
        ],
        ["PL05_seat_drills@1", "feed_out", {"z_top": part_top}],
        [
            "PL05_seat_drills@2",
            "holes",
            {"centres": [holes4["holddown"]], "z_bottom": _r(seat_43_tip)},
        ],
        [
            "PL05_seat_drills@3",
            "holes",
            {"centres": seats, "z_bottom": _r(seat_25_tip)},
        ],
        ["PL05_seat_drills@0", "keep_out", {"radius": db / 2, "boxes": part_boxes}],
        ["PL05_seat_drills@1", "keep_out", {"radius": dream / 2, "boxes": part_boxes}],
        ["PL05_seat_drills@2", "keep_out", {"radius": d43 / 2, "boxes": part_boxes}],
        ["PL05_seat_drills@3", "keep_out", {"radius": d25 / 2, "boxes": part_boxes}],
        [
            "PL05_seat_drills@0",
            "rapids_clear",
            {"z_top": part_top, "open_holes": [pivot4]},
        ],
        ["PL05_seat_drills@1", "rapids_clear", {"z_top": part_top}],
        [
            "PL05_seat_drills@2",
            "rapids_clear",
            {"z_top": part_top, "open_holes": [holes4["holddown"]]},
        ],
        [
            "PL05_seat_drills@3",
            "rapids_clear",
            {"z_top": part_top, "open_holes": seats},
        ],
    ]
    for k in range(4):
        expect += [
            [f"PL05_seat_drills@{k}", "vertical_below_top", {"z_top": part_top}],
            [f"PL05_seat_drills@{k}", "air_feed", {"z_top": part_top}],
        ]
    for program, key in (
        ("PL06_holddown_tap", "holddown"),
        ("PL07_wedge_tap", "wedge"),
    ):
        expect += [
            [
                program,
                "tap_stop",
                {
                    "tool": t_["tap-guide"],
                    "at": holes4[key],
                    "machine_top": MACHINE_Z_TOP_MM,
                },
            ],
            [program, "air_feed", {"z_top": 0.0}],
        ]
    cleared_corners = [list(corners[k]) for k in ("NE", "SE", "SW")]
    expect += [
        [
            "PL08_outline",
            "tool_changes",
            {"z_top": part_top, "tools": [t_["em-quarter"]], "loads_first": True},
        ],
        ["PL08_outline", "spindle", {"rpm": [[speeds["outline rough"][0]]]}],
        ["PL08_outline", "pauses", {"z_top": part_top, "count": 0}],
        ["PL08_outline", "depth", {"z_min": _r(through4)}],
        ["PL08_outline", "air_feed", {"z_top": part_top}],
        ["PL08_outline", "rapids_clear", {"z_top": part_top}],
        [
            "PL08_outline",
            "keep_out",
            {"radius": r1, "boxes": part_boxes, "circles": heads},
        ],
        [
            "PL08_outline",
            "outline",
            {
                "elements": els(outline),
                "passes": [
                    {"offset": _r(d_rough), "levels": rough_levels},
                    {"offset": _r(r1), "levels": finish_levels},
                ],
                "z_top": part_top,
                "clearing": [
                    {
                        "x": [_r(c_start[0] - 1.0), _r(c_end[0] + 1.0)],
                        "levels": rough_levels,
                    }
                ],
            },
        ],
        [
            "PL08_outline",
            "cleared",
            {"points": cleared_corners, "radius": r1, "z": _r(through4)},
        ],
        [
            "PL09_relief",
            "tool_changes",
            {"z_top": relief_top, "tools": [t_["em-quarter"]], "loads_first": True},
        ],
        ["PL09_relief", "spindle", {"rpm": [[speeds["relief"][0]]]}],
        ["PL09_relief", "pauses", {"z_top": relief_top, "count": 0}],
        ["PL09_relief", "depth", {"z_min": 0.0}],
        ["PL09_relief", "rapids_clear", {"z_top": relief_top}],
        ["PL09_relief", "air_feed", {"z_top": relief_top}],
        [
            "PL09_relief",
            "keep_out",
            {
                "radius": r1,
                "circles": [
                    {**h, "z_top": h["z_top"] - part_top + relief_top} for h in heads
                ],
            },
        ],
        [
            "PL09_relief",
            "bounds",
            {
                "window": [[-rr - 1.0, x_in + 1.0], [-rr - 1.0, rr + 1.0]],
                "x": [
                    _r(min(q[0] for q in relief_extent)),
                    _r(max(q[0] for q in relief_extent)),
                ],
                "y": [
                    _r(min(q[1] for q in relief_extent)),
                    _r(max(q[1] for q in relief_extent)),
                ],
                "z_min": 0.0,
                "arc": "G2",
                "z_top": relief_top,
            },
        ],
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
            doc, f"Platform {key}", ctx["step"], frame["origin"], frame["axes"]
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
