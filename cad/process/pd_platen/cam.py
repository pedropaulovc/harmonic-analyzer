"""FreeCAD CAM recipe for MHA-PD-02, the platen.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The plate's sizes come
from the feature export (its length, height and thickness bands, the four
sockets, the ten guide holes and their counterbores); the blank's gate, the
fixture bar, the placement, the cuts, the tape and the stacks from
``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter diameters, speeds
and feeds from the shop (``shop/``) and the plan's authored settings. Every
path is written here (``rt.custom``): straight lines and one circle per
counterbore, which a recipe can state exactly. Typed here, because no record
carries them: the #1 centre drill's catalogue geometry (it sets the spot
depth), the twist drills' 118° point, the machine's Z top for the tap files'
retract, the approach, safe and clearance heights, the face overhang, the
feeler leaf, the edge finder's radius and the clearances the checks below
hold.

Route (plan text in ``plan.toml``): the 1/4 × 6 × 11 in brass blank is
bonded, for every cut, to the 1/2 × 6 × 18 in 6061 fixture bar clamped on
two 1-2-3 blocks on the table (no vise). PL01 skims the bar's top under the
blank's place; PL02 plunges four relief pockets under the socket stations.
PL03, run three times with the blank turned over each time (B, P, B up),
faces one equal cut off the top. PL04, P up: face P to the thickness, mill
the four edges to size with the cutter's side (the whole margin goes to
chips), spot the fourteen holes, #50 through the four sockets, #27 through
the ten guide holes, counterbore the ten from P. PL05-PL08 bring the tap
guide over each socket for tapping by hand.

Work frame (G54), X and Y set once on the bar for every program: X0 the
platen's left edge and Y0 its bottom edge as drawn, +X along the plate. The
drawing's view shows the back face, and the plate is cut paper face up, so
work Y is minus the drawing's Y (the bottom edge is at the back of the
table) and work Z counts up from the back face. Z0:
- PL01: the skimmed bar top (its high point less the skim); PL02 the same.
- PL03: the cut face (the top's high point less the cut).
- PL04 and the tap files: the plate's underside (the back face, on the
  tape stack), set from P's top less the miked thickness.

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock; only
plunges into metal (the relief pockets, the counterbores) take the plan's
slow feed. The edges are milled with the cutter's side in one-way passes
with the plate on the cutter's left: conventional with the spindle's M3
(``_gcode.engagements``' convention, which the engagement check below
holds them to). The sockets are tapped by hand (FluidNC cannot rigid-tap;
owner, Pedro, 2026-11-17) under the Fisher tap guide in the 1/2 in R8
collet (owner, Pedro, 2026-11-21), spindle off. FluidNC, like Grbl, refuses
jogs while an M0 holds the program (FluidNC wiki, "Single Block Mode",
http://wiki.fluidnc.com/en/features/single_block_mode), so each tap stop is
a file of its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "pd_platen"
COMMENT = "MHA-PD-02 platen"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("PL01_bar_skim", ("bar_skim",)),
    ("PL02_bar_relief", ("relief",)),
    ("PL03_face", ("face",)),
    (
        "PL04_platen",
        (
            ("thickness", "edges"),
            ("spot",),
            ("socket_drill",),
            ("guide_drill",),
            ("cbore",),
        ),
    ),
    ("PL05_tap_1", ("tap_1",)),
    ("PL06_tap_2", ("tap_2",)),
    ("PL07_tap_3", ("tap_3",)),
    ("PL08_tap_4", ("tap_4",)),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held, and each tap file before its
# retract (the tap guide).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the tap, the files and the scrapers are not).
CAM_TOOLS = ("em-half", "spot", "drill-50", "drill-27", "em-quarter", "tap-guide")
IN = 25.4
# The Fisher tap guide's overall length, 3 1/8 in (its sellers' size,
# cad/config/shop-equipment/ tools.tap-guide-fisher): the most it stands
# below the collet face.
TAP_GUIDE_OAL_MM = 3.125 * IN
# ANSI #1 combined drill and countersink, 60° included (the carbide set's
# trade size 1, "for 3/64 in drill bit"): the shop record names the set, not
# its geometry.
CENTRE_DRILL = {
    "pilot_mm": 3 / 64 * IN,
    "pilot_length_mm": 3 / 64 * IN,
    "body_mm": 1 / 8 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# A tap file's first motion: G53 G0 to machine Z0, the homed top (FluidNC
# sets an axis's machine position to its homing mpos_mm, default 0, and Z
# homes up; the owner, Pedro, confirmed it in person 2026-11-21, cnc rulings
# record).
MACHINE_Z_TOP_MM = 0.0
# Face passes start and finish with the cutter this far clear of the stock's
# ends, and edge passes this far clear of its edges, so every plunge and
# stepover link is in the air beside it.
APPROACH_MM = 2.54
# Faces reach at least this far past the stock's long edges.
FACE_OVERHANG_MM = 0.5
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top.
CLEAR_MM = 5.0
# The feeler leaf every Z zero is touched on (.002 in) and the edge finder's
# radius (.100 in).
FEELER_MM = 0.002 * IN
FINDER_RADIUS_MM = 0.1 * IN
# Authored clearances the checks hold. A gated blank leaves at least this
# much on every edge; a step clamp's zone stays this far from the cutter;
# the relief pocket stands this far round the tap and below its point; the
# tap's point stops this far under the thickest plate (.100, past a plug
# chamfer of five #2-56 threads, .089).
MARGIN_MIN_MM = 1.0
CLAMP_CLEAR_MM = 5.0
RELIEF_CLEAR_MM = 0.5
TAP_PAST_MM = 0.1 * IN
# The plate bridges a bare seam between tape strips: the widest seam is at
# most this many plate thicknesses (author's criterion; a wider one would let
# the cutter push the plate down into it).
TAPE_GAP_MAX_THICKNESSES = 2.0
# Keep-out shapes stand this high above Z0: every move over a clamp zone,
# whatever its height, is refused.
CLAMP_TOP_MM = 1000.0
# The engagement check's cell (mm): the edges' radial steps are held to
# their declared width within one cell.
ENGAGEMENT_CELL_MM = 0.05
# Feeds the plan authors, recomputed here from the figures its [parameters]
# comment cites, so a slip in either place is refused. Drills in in/rev
# (AutoDrill, row Brass: the centre drill's pilot and the #50 under the 1/16
# in column, the #27 under the 1/8 in column); the bar's skim in in/tooth
# (the 6G table, Al/Al Alloys, 1/2 in); end-mill plunges into metal in
# in/tooth (the author's choice).
SPOT_FEED_PER_REV_MM = 0.001 * IN
SOCKET_FEED_PER_REV_MM = 0.001 * IN
GUIDE_FEED_PER_REV_MM = 0.003 * IN
BAR_SKIM_CHIP_LOAD_MM = 0.0042 * IN
PLUNGE_CHIP_LOAD_MM = 0.00025 * IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# A drill against its hole's printed band: the shop records the drill's
# nominal size (#27: .1440 in, 3.6576), the band's floor is that size
# rounded to 3.658; anything closer than this is the same size.
SIZE_TOL_MM = 0.001


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
    """(rpm, mm/min) of the operation holding ``cut``: the shop setting it
    names (chip load × flutes × rpm), or, with no setting, the rpm and feed
    the cut itself authors."""
    op, _record_cut = _op_with_cut(plan, cut)
    if "settings" not in op:
        return _cut(plan, cut, "rpm"), _cut(plan, cut, "feed_mm_min")
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


def _same(plan: dict[str, Any], cut: str, key: str, parameter: str) -> None:
    """Milling cut ``cut``'s ``key`` is the plan parameter ``parameter``."""
    if not math.isclose(
        _cut(plan, cut, key), plan["parameters"][parameter], abs_tol=1e-6
    ):
        raise ValueError(f"'{cut}' {key} is not process.{parameter}")


def _mid(band: list[float]) -> float:
    return (band[0] + band[1]) / 2


def _spot_depth(dia: float) -> float:
    """Depth below the surface at which the #1 centre drill's 60° countersink
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


def _plunge(
    xy: tuple[float, float], top: float, z: float, clear: float, feed: str = "feed"
) -> list[str]:
    """One straight plunge at ``xy`` from above ``top`` to ``z`` and out,
    at the controller's ``feed`` (``"feed"`` or ``"plunge"``). Moves to and
    from the hole run at ``clear``."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{{feed}}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _counterbore(
    xy: tuple[float, float], top: float, floor: float, orbit: float, clear: float
) -> list[str]:
    """Plunge down the drilled hole at ``xy`` to ``floor`` at the plunge feed,
    step ``orbit`` out along +X, one clockwise circle (conventional inside a
    bore with a right-hand spindle), back to the centre and out."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    x, y = xy
    out = _r(x + orbit)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{x:.3f} Y{y:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(floor):.3f} F{{plunge}}",
        f"G1 X{out:.3f} F{{feed}}",
        f"G2 X{out:.3f} Y{y:.3f} I{_r(x - out):.3f} J0.000 F{{feed}}",
        f"G1 X{x:.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _stations(y: tuple[float, float], radius: float, max_step: float) -> list[float]:
    """Zigzag pass stations across the face ``y`` (low, high), from its high
    side: each pass takes the same width, at most ``max_step``, and together
    the cutter reaches ``FACE_OVERHANG_MM`` past both edges."""
    span = y[1] - y[0] + FACE_OVERHANG_MM
    n = math.ceil(span / max_step - 1e-9)
    step = span / n
    if 2 * radius - step < FACE_OVERHANG_MM:
        raise ValueError(
            f"a {step:.3f} stepover leaves the first pass short of the edge"
        )
    first = y[1] + radius - step
    return [_r(first - k * step) for k in range(n)]


def _face(
    z: float,
    top: float,
    x: tuple[float, float],
    ys: list[float],
    lead_y: float | None = None,
) -> list[str]:
    """One zigzag face at ``z``: one X pass per Y in ``ys`` between the
    cutter-centre ends ``x``, alternating direction, starting at the low X
    end. With ``lead_y`` the plunge is at that Y (beside the stock's high
    edge) and a feed move brings the cutter to the first pass."""
    clear = _r(top + CLEAR_MM)
    x0, x1 = _r(x[0]), _r(x[1])
    start = ys[0] if lead_y is None else _r(lead_y)
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{x0:.3f} Y{start:.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
    ]
    if lead_y is not None:
        lines.append(f"G1 Y{ys[0]:.3f} F{{feed}}")
    for k, y in enumerate(ys):
        if k:
            lines.append(f"G1 Y{y:.3f} F{{feed}}")
        lines.append(f"G1 X{x1 if k % 2 == 0 else x0:.3f} F{{feed}}")
    return lines + [f"G0 Z{clear:.3f}"]


def _stock_left(raw: float, finish: float, max_step: float) -> list[float]:
    """The stock each pass of an edge leaves on it: from the largest margin
    ``raw`` down to ``finish`` in equal steps no deeper than ``max_step``,
    then none (the finish pass)."""
    n = math.ceil((raw - finish) / max_step - 1e-9)
    return [raw - (raw - finish) * (k + 1) / n for k in range(n)] + [0.0]


def _side(
    axis: str,
    stations: list[float],
    run: tuple[float, float],
    z: float,
    top: float,
) -> list[str]:
    """One-way side passes at the cutter-centre ``stations`` along ``axis``
    (``"X"`` or ``"Y"``), each along the other axis from ``run[0]`` to
    ``run[1]`` at depth ``z``: plunged beside the stock at feed, lifted and
    rapided back to the start beside it between passes. The tool starts at
    the clearance height above ``top``."""
    clear, safe = _r(top + CLEAR_MM), _r(top + SAFE_MM)
    other = "Y" if axis == "X" else "X"
    lines = []
    for station in stations:
        lines += [
            f"G0 {axis}{_r(station):.3f} {other}{_r(run[0]):.3f}",
            f"G0 Z{safe:.3f}",
            f"G1 Z{_r(z):.3f} F{{feed}}",
            f"G1 {other}{_r(run[1]):.3f} F{{feed}}",
            f"G0 Z{clear:.3f}",
        ]
    return lines


def _plane(feature: dict[str, Any], axis: str, value: float, name: str) -> None:
    plane = feature["plane"]
    if plane["axis"] != axis or not math.isclose(plane["value"], value, abs_tol=1e-3):
        raise ValueError(f"{name}: expected at model {axis.upper()} {value:g}")


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The plate's bands, sockets and guide holes from the export, each
    checked against the frame the recipe assumes: the left edge X0 with the
    plate along +X, the bottom edge Y0 with the top edge at +Y, the paper
    face Z0 with the back face at +Z, every hole through from the paper face
    along +Z."""
    f = features["features"]
    _plane(f["left_edge"], "x", 0.0, "left_edge")
    _plane(f["bottom_edge"], "y", 0.0, "bottom_edge")
    _plane(f["paper_face"], "z", 0.0, "paper_face")
    right, top, back = f["right_edge"], f["top_edge"], f["back_face"]
    _plane(right, "x", right["width_nominal"], "right_edge")
    _plane(top, "y", top["height_nominal"], "top_edge")
    _plane(back, "z", back["thickness_nominal"], "back_face")
    handled = {
        "left_edge",
        "right_edge",
        "bottom_edge",
        "top_edge",
        "paper_face",
        "back_face",
    }
    sockets, guides = [], []
    for name, feature in f.items():
        if name in handled:
            continue
        socket = name.startswith("socket_") and feature["kind"] == "threaded_hole"
        guide = name.startswith("guide_") and feature["kind"] == "hole"
        if not (socket or guide):
            raise ValueError(f"{name}: a feature this recipe does not make")
        if feature["axis"] != [0.0, 0.0, 1.0] or feature["at"][2] != 0.0:
            raise ValueError(f"{name}: expected from the paper face along +Z")
        if feature.get("thru") is not True:
            raise ValueError(f"{name}: expected a through hole")
        x, y = feature["at"][0], feature["at"][1]
        if not feature["station"][0] <= x <= feature["station"][1]:
            raise ValueError(f"{name}: X {x} is outside its station band")
        if not feature["height"][0] <= y <= feature["height"][1]:
            raise ValueError(f"{name}: Y {y} is outside its height band")
        hole = {"name": name, "x": x, "y": y, "dia": feature["dia"]}
        if socket:
            sockets.append({**hole, "thread": feature["thread"]})
        else:
            if feature["cbore_depth_from"] != "paper_face":
                raise ValueError(f"{name}: its counterbore is not from the paper face")
            guides.append(
                {
                    **hole,
                    "cbore_dia": feature["cbore_dia"],
                    "cbore_depth": feature["cbore_depth"],
                }
            )
    if not sockets or not guides:
        raise ValueError("no sockets or no guide holes in the export")
    for key in ("dia", "thread"):
        if any(hole[key] != sockets[0][key] for hole in sockets):
            raise ValueError(f"the sockets differ in {key}")
    for key in ("dia", "cbore_dia", "cbore_depth"):
        if any(hole[key] != guides[0][key] for hole in guides):
            raise ValueError(f"the guide holes differ in {key}")
    sockets.sort(key=lambda hole: (hole["x"], hole["y"]))
    guides.sort(key=lambda hole: (hole["x"], hole["y"]))
    return {
        "length_band": right["width"],
        "height_band": top["height"],
        "thickness_band": back["thickness"],
        "thickness_nominal": back["thickness_nominal"],
        "sockets": sockets,
        "guides": guides,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    machine = shop["machines"]["pm-30mv"]

    # Targets: the middle of each printed band.
    length = _mid(g["length_band"])
    height = _mid(g["height_band"])
    thick = _mid(g["thickness_band"])
    _agree(plan, "length_target_mm", length)
    _agree(plan, "height_target_mm", height)
    _agree(plan, "thickness_target_mm", thick)

    # The blank: its nominal sizes inside Setup 1's gate, and wider than the
    # vise opens (the route's premise: no vise).
    blank_l, blank_w = p["blank_length_in"] * IN, p["blank_width_in"] * IN
    blank_t = p["blank_thickness_in"] * IN
    gates = {
        "length": (p["blank_length_min_mm"], p["blank_length_max_mm"], blank_l),
        "width": (p["blank_width_min_mm"], p["blank_width_max_mm"], blank_w),
        "thickness": (
            p["blank_thickness_min_mm"],
            p["blank_thickness_max_mm"],
            blank_t,
        ),
    }
    for name, (low, high, nominal) in gates.items():
        if not low <= nominal <= high:
            raise ValueError(
                f"the blank's nominal {name} {nominal} is outside its gate"
            )
    l_min, l_max = gates["length"][:2]
    w_min, w_max = gates["width"][:2]
    t_min, t_max = gates["thickness"][:2]
    if w_min <= shop["workholding"]["vise-pm-6"]["opening_mm"]:
        raise ValueError(
            "the blank fits the vise's opening: the plan's premise is gone"
        )

    # Placement: the blank's left end on the scribed line, its front edge
    # flush with the bar's, each within the tolerance; X0/Y0 the platen's
    # left and bottom edges, centred in the nominal blank.
    bar_l, bar_w, bar_t = p["bar_length_mm"], p["bar_width_mm"], p["bar_thickness_mm"]
    tol, blank_left = p["placement_tol_mm"], p["blank_left_mm"]
    margin_x, margin_y = (blank_l - length) / 2, (blank_w - height) / 2
    x0_bar, y0_bar = blank_left + margin_x, margin_y + height
    _agree(plan, "x0_from_bar_left_mm", x0_bar)
    _agree(plan, "y0_from_bar_front_mm", y0_bar)
    _agree(plan, "x_set_mm", -(x0_bar + FINDER_RADIUS_MM))
    _agree(plan, "y_set_mm", -(y0_bar + FINDER_RADIUS_MM))
    # What each edge's margin can be, smallest and largest, over the gate
    # and the placement.
    margins = {
        "left": (margin_x - tol, margin_x + tol),
        "right": (l_min - length - margin_x - tol, l_max - length - margin_x + tol),
        "front": (margin_y - tol, margin_y + tol),
        "back": (w_min - height - margin_y - tol, w_max - height - margin_y + tol),
    }
    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    r = em / 2
    for name, (low, high) in margins.items():
        if low < MARGIN_MIN_MM:
            raise ValueError(f"the {name} margin can be {low:.3f}: nothing to clean up")
        if high >= em:
            raise ValueError(
                f"the {name} margin can be {high:.3f}: a rim past the cutter"
            )
    # The largest blank's box and the bar's, in the work frame.
    blank_x = (-margins["left"][1], length + margins["right"][1])
    blank_y = (-height - margins["front"][1], margins["back"][1])
    bar_x = (-x0_bar, bar_l - x0_bar)
    bar_y = (-y0_bar, bar_w - y0_bar)
    clamp = p["clamp_zone_mm"]
    clamps = [
        _box(
            "left step clamps",
            (bar_x[0] - clamp, bar_x[0] + clamp),
            (bar_y[0] - clamp, bar_y[1] + clamp),
            CLAMP_TOP_MM,
        ),
        _box(
            "right step clamps",
            (bar_x[1] - clamp, bar_x[1] + clamp),
            (bar_y[0] - clamp, bar_y[1] + clamp),
            CLAMP_TOP_MM,
        ),
    ]
    free_x = (bar_x[0] + clamp + CLAMP_CLEAR_MM, bar_x[1] - clamp - CLAMP_CLEAR_MM)

    # Facing: the cutter, the stepover, the equal cuts and the last one.
    step_max = p["face_stepover_max_mm"]
    if not math.isclose(p["face_cutter_dia_mm"], em, abs_tol=1e-6):
        raise ValueError("process.face_cutter_dia_mm is not the 1/2 in end mill's")
    if step_max > em / 2 + 1e-9:
        raise ValueError("the face stepover is over half the cutter")
    cut = p["face_cut_mm"]
    _agree(plan, "face_z_set_mm", cut + FEELER_MM)
    _agree(plan, "third_cut_min_mm", t_min - 3 * cut)
    _agree(plan, "third_cut_max_mm", t_max - 3 * cut)
    third_max = t_max - 3 * cut
    last = (t_min - 3 * cut - thick, third_max - thick)
    _agree(plan, "final_face_doc_max_mm", last[1])
    if last[0] <= 0.1:
        raise ValueError(f"the thinnest blank leaves {last[0]:.3f} for the last face")
    # Setup 6's Z0: T1 touched over the spot Setup 5 mics, the middle of the
    # nominal blank's FRONT edge and the inset in from it, the tool's whole
    # tip on the blank wherever it was placed. The entries after a reset: the
    # faced P plus the leaf; the plate's own edges at the finder's radius.
    inset = p["z_touch_inset_in"] * IN
    if inset - tol <= r:
        raise ValueError(
            "process.z_touch_inset_in: the end mill's tip overhangs the blank"
        )
    _agree(plan, "z_touch_x_mm", blank_left + blank_l / 2 - x0_bar)
    _agree(plan, "z_touch_y_mm", inset - y0_bar)
    _agree(plan, "z_leaf_mm", FEELER_MM)
    _agree(plan, "faced_z_set_mm", thick + FEELER_MM)
    _agree(plan, "edge_x_set_mm", -FINDER_RADIUS_MM)
    _agree(plan, "edge_y_set_mm", FINDER_RADIUS_MM)
    face_rpm, face_feed = _setting(plan, shop, "face")
    for name in ("face", "face 2", "face 3", "thickness", "edge rough", "edge finish"):
        _same(plan, name, "cutter_dia_mm", "face_cutter_dia_mm")
        if _setting(plan, shop, name) != (face_rpm, face_feed):
            raise ValueError(f"'{name}' runs at another setting than 'face'")
    for name in ("face", "face 2", "face 3", "thickness", "bar skim"):
        _same(plan, name, "radial_woc_mm", "face_stepover_max_mm")
    for name in ("face", "face 2", "face 3"):
        _same(plan, name, "axial_doc_mm", "face_cut_mm")
    _same(plan, "thickness", "axial_doc_mm", "final_face_doc_max_mm")

    # The bar: skimmed under the largest blank and a margin round it, the
    # cutter's edge clear of the clamps; four relief pockets under the
    # sockets.
    skim, skim_margin = p["bar_skim_mm"], p["bar_skim_margin_mm"]
    _agree(plan, "bar_z_set_mm", skim + FEELER_MM)
    seat = (blank_x[0] - skim_margin, blank_x[1] + skim_margin)
    _agree(plan, "seat_left_mm", seat[0])
    _agree(plan, "seat_right_mm", seat[1])
    _agree(plan, "bar_skim_left_mm", x0_bar + seat[0])
    _agree(plan, "bar_skim_right_mm", x0_bar + seat[1])
    _same(plan, "bar skim", "cutter_dia_mm", "face_cutter_dia_mm")
    _same(plan, "bar skim", "axial_doc_mm", "bar_skim_mm")
    skim_rpm, skim_feed = _setting(plan, shop, "bar skim")
    _same(plan, "bar skim", "feed_mm_min", "bar_skim_feed_per_min_mm")
    _agree(
        plan,
        "bar_skim_feed_per_min_mm",
        BAR_SKIM_CHIP_LOAD_MM * _cut(plan, "bar skim", "flutes") * skim_rpm,
    )
    # Top the bar can have above the blocks: the thinnest skimmed twice, the
    # thickest as bought.
    if not p["bar_top_min_mm"] <= bar_t - skim <= p["bar_top_max_mm"]:
        raise ValueError("the skimmed bar's top is outside bar_top_min/max_mm")
    relief = p["relief_depth_mm"]
    relief_rpm, plunge_feed = _setting(plan, shop, "tap relief")
    _same(plan, "tap relief", "cutter_dia_mm", "face_cutter_dia_mm")
    _same(plan, "tap relief", "feed_mm_min", "plunge_feed_per_min_mm")
    _agree(
        plan,
        "plunge_feed_per_min_mm",
        PLUNGE_CHIP_LOAD_MM * _cut(plan, "tap relief", "flutes") * relief_rpm,
    )
    if relief_rpm != skim_rpm:
        raise ValueError("'tap relief' runs at another speed than 'bar skim'")

    # The hold (owner, 2026-11-23): painter's tape on the bar and on the
    # blank, CA glue between. Z0 is the underside where the plate was miked
    # and touched; elsewhere the underside sits up to the stack band's width
    # under it. The through cut clears the underside wherever the stack is
    # and stays inside the thinnest stack, short of the bar.
    stack_min, stack_max = p["tape_stack_min_mm"], p["tape_stack_max_mm"]
    if not stack_min < p["tape_stack_mm"] < stack_max:
        raise ValueError("process.tape_stack_mm is outside its band")
    spread = stack_max - stack_min
    through = p["outline_breakthrough_mm"]
    if through <= spread:
        raise ValueError(
            f"the through cut {through} can leave a skin where the stack is "
            f"{spread:.2f} thinner than under Z0"
        )
    if through >= stack_min:
        raise ValueError(
            f"the through cut {through} reaches the bar under the thinnest "
            f"stack {stack_min}"
        )
    # The faced thickness elsewhere differs from the target by the stack's
    # difference from the touched spot: within half the thickness band.
    if spread >= (g["thickness_band"][1] - g["thickness_band"][0]) / 2:
        raise ValueError(
            "the stack's band does not fit inside the thickness band round the target"
        )
    # Butted strips along X on each face: they cover the bar's width and the
    # widest blank's; the blank's first is centred on its FRONT edge, so its
    # seams sit a fraction of a strip off the bar's.
    strip, count = p["tape_strip_width_mm"], p["tape_strip_count"]
    offset, gap = p["tape_seam_offset_mm"], p["tape_seam_gap_max_mm"]
    if count * strip < max(bar_w, w_max) or offset + (count - 1) * strip < w_max:
        raise ValueError(f"{count} strips of {strip} leave a face bare")
    shift = offset % strip
    if min(shift, strip - shift) < strip / 4:
        raise ValueError("the blank's seams lie within a quarter strip of the bar's")
    if not 0 <= gap <= TAPE_GAP_MAX_THICKNESSES * thick:
        raise ValueError(f"a {gap:.2f} seam: the plate does not bridge it")
    # The bar's strips start the overhang left of the scribed line and run at
    # least the overhang past the right end of the longest gated blank placed
    # long, wholly on the skimmed seat (never across its step) and so clear
    # of the step clamps' zones; the blank's strips are longer than the
    # longest gated blank (trimmed flush).
    overhang = p["tape_end_overhang_mm"]
    bar_strip = p["tape_bar_strip_length_mm"]
    tape_x = (-margin_x - overhang, -margin_x - overhang + bar_strip)
    if overhang <= tol:
        raise ValueError("the bar's tape can leave the blank's left end bare")
    if tape_x[1] - (-margin_x + tol + l_max) < overhang:
        raise ValueError(
            f"the bar's {bar_strip} strips end under {overhang} past the longest blank"
        )
    if tape_x[0] < seat[0] or tape_x[1] > seat[1]:
        raise ValueError("the bar's tape runs off the skimmed seat, across its step")
    if p["tape_blank_strip_length_mm"] < l_max:
        raise ValueError("the blank's strips leave an end of the longest blank bare")
    # The bond prechips is told: the tape under a square patch as long as the
    # plate is high, less the bare seams it can cross and two relief pockets.
    side = g["height_band"][0]
    seams = math.floor(side / strip) + 1
    patch = (side - seams * gap) * side - 2 * math.pi * r * r
    _agree(plan, "bond_patch_area_mm2", patch)

    # Edges: the cutter's side, one level from P to the through depth, the
    # stock each pass leaves from the largest margin down.
    edge_step, edge_finish = p["outline_step_max_mm"], p["outline_finish_mm"]
    _agree(plan, "outline_axial_doc_mm", thick + through)
    _same(plan, "edge rough", "radial_woc_mm", "outline_step_max_mm")
    _same(plan, "edge finish", "radial_woc_mm", "outline_finish_mm")
    for name in ("edge rough", "edge finish"):
        _same(plan, name, "axial_doc_mm", "outline_axial_doc_mm")
    left = {
        name: _stock_left(high, edge_finish, edge_step)
        for name, (_low, high) in margins.items()
    }

    # Holes.
    d50 = _shop_tool(plan, shop, "drill-50")["diameter_mm"]
    d27 = _shop_tool(plan, shop, "drill-27")["diameter_mm"]
    quarter = _shop_tool(plan, shop, "em-quarter")["diameter_mm"]
    for dia, holes_, what in ((d50, g["sockets"], "#50"), (d27, g["guides"], "#27")):
        low, high = holes_[0]["dia"]
        if not low - SIZE_TOL_MM <= dia <= high:
            raise ValueError(f"{what} Ø{dia} is outside its holes' band {[low, high]}")
    for name, dia in (("socket drill", d50), ("guide drill", d27)):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not its drill's Ø{dia}")
        op = _op_with_cut(plan, name)[0]
        if op["peck"] != "none":
            raise ValueError(f"'{name}' is one plunge (peck none)")
        if op["hole_depth_mm"] != "{{process.thickness_target_mm}}":
            raise ValueError(f"'{name}' hole_depth_mm is not the thickness target")
    spot_dia = p["spot_dia_mm"]
    _same(plan, "spot", "cutter_dia_mm", "spot_dia_mm")
    if spot_dia >= d50:
        raise ValueError("the spot is not under the #50: it would chamfer a socket")
    spot_depth = _spot_depth(spot_dia)
    if spot_depth >= g["thickness_band"][0]:
        raise ValueError("the spot goes through the plate")
    spot_rpm, spot_feed = _setting(plan, shop, "spot")
    socket_rpm, socket_feed = _setting(plan, shop, "socket drill")
    guide_rpm, guide_feed = _setting(plan, shop, "guide drill")
    for name, key, per_rev, rpm in (
        ("spot", "spot_feed_per_min_mm", SPOT_FEED_PER_REV_MM, spot_rpm),
        (
            "socket drill",
            "socket_drill_feed_per_min_mm",
            SOCKET_FEED_PER_REV_MM,
            socket_rpm,
        ),
        (
            "guide drill",
            "guide_drill_feed_per_min_mm",
            GUIDE_FEED_PER_REV_MM,
            guide_rpm,
        ),
    ):
        _same(plan, name, "feed_mm_min", key)
        _agree(plan, key, per_rev * rpm)
    past = p["drill_past_mm"]
    socket_tip = -(past + _point(d50))
    guide_tip = -(past + _point(d27))
    _agree(plan, "socket_tip_height_mm", socket_tip)
    _agree(plan, "guide_tip_height_mm", guide_tip)
    # The relief pocket under each socket: wider than the tap, deeper than
    # the #50's tip and the tap's point, the thinnest tape stack counted.
    major = (
        0.060 + 0.013 * int(re.match(r"#(\d+)-", g["sockets"][0]["thread"]).group(1))
    ) * IN
    if em < major + 2 * RELIEF_CLEAR_MM:
        raise ValueError("the relief pocket is not wider than the tap")
    tap_depth = g["thickness_band"][1] + TAP_PAST_MM
    _agree(plan, "tap_point_depth_mm", tap_depth)
    pocket_floor = stack_min + relief
    tap_below = tap_depth - g["thickness_band"][0]
    if pocket_floor < max(tap_below, -socket_tip) + RELIEF_CLEAR_MM:
        raise ValueError(
            f"the relief pocket's floor {pocket_floor:.3f} under the plate is not "
            f"{RELIEF_CLEAR_MM} below the tap's point {tap_below:.3f}"
        )
    if -guide_tip - stack_min >= bar_t / 2:
        raise ValueError("the #27 goes over half way through the bar")

    # Counterbores: the 1/4 in end mill down the drilled hole, one circle.
    cbore_band, depth_band = g["guides"][0]["cbore_dia"], g["guides"][0]["cbore_depth"]
    if not math.isclose(p["cbore_cutter_dia_mm"], quarter, abs_tol=1e-6):
        raise ValueError("process.cbore_cutter_dia_mm is not the 1/4 in end mill's")
    orbit = (_mid(cbore_band) - quarter) / 2
    _agree(plan, "cbore_orbit_mm", orbit)
    if not cbore_band[0] < quarter + 2 * p["cbore_orbit_mm"] < cbore_band[1]:
        raise ValueError("the counterbore's diameter is outside its band")
    if not d27 < quarter:
        raise ValueError("the counterbore cutter is not over the guide hole")
    floor = thick - _mid(depth_band)
    _agree(plan, "cbore_floor_height_mm", floor)
    if floor <= 0.25:
        raise ValueError(f"the counterbore leaves a {floor:.3f} floor")
    _same(plan, "counterbore plunge", "cutter_dia_mm", "cbore_cutter_dia_mm")
    _same(plan, "counterbore wall", "cutter_dia_mm", "cbore_cutter_dia_mm")
    _same(plan, "counterbore wall", "radial_woc_mm", "cbore_orbit_mm")
    cbore_rpm, cbore_feed = _setting(plan, shop, "counterbore wall")
    plunge_rpm, cbore_plunge = _setting(plan, shop, "counterbore plunge")
    if (plunge_rpm, cbore_plunge) != (cbore_rpm, plunge_feed):
        raise ValueError("'counterbore plunge' is not the plan's plunge feed and speed")

    # Stacks from the table: the shortest tool reaches each setup's deepest
    # cut (the reason for the blocks), the tap stack fits under the spindle,
    # and the cutter's travel is inside the machine's.
    reach_min, reach_max = machine["spindle_to_table_mm"]
    gauge = p["r8_collet_gauge_mm"]
    base = p["block_height_mm"] + p["bar_top_min_mm"]
    for what, deepest, tool in (
        ("PL02's pockets", -relief, p["half_mill_projection_min_mm"]),
        ("PL04's holes", guide_tip, p["quarter_mill_projection_min_mm"]),
    ):
        if base + deepest + gauge + tool < reach_min:
            raise ValueError(f"{what}: the shortest tool does not reach the cut")
    if p["bar_top_min_mm"] + gauge + p["half_mill_projection_min_mm"] >= reach_min:
        raise ValueError("the bar is reachable on the table: the blocks are not needed")
    _agree(plan, "tap_stack_max_mm", TAP_GUIDE_OAL_MM + p["tap_wrench_reach_max_mm"])
    ceiling = (
        reach_max
        - shop["limits"]["tool_change_clearance_mm"]
        - p["block_height_mm"]
        - p["bar_top_max_mm"]
        - stack_max
        - g["thickness_band"][1]
        - gauge
    )
    if p["tap_stack_max_mm"] > ceiling:
        raise ValueError(
            f"the tap stack {p['tap_stack_max_mm']} does not fit under {ceiling:.3f}"
        )
    # The drill chuck with its longest drill fits there too (the envelope's
    # longest tool is the tap stack, which bounds it).
    chuck_stack = p["drill_chuck_gauge_mm"] + p["drill_projection_max_mm"]
    if chuck_stack > min(ceiling + gauge, gauge + p["tap_stack_max_mm"]):
        raise ValueError(
            f"the drill chuck and its longest drill, {chuck_stack}, stand longer "
            "than the tap stack the envelope allows for"
        )

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)); the plate paper face
    # up, turned about X: work Y is minus the model's, work Z counts up
    # from the back face. In PL03 the model sits under the cut face.
    y_axis, z_axis = [0, -1, 0], [0, 0, -1]
    frames = {
        "face": _frame([0.0, 0.0, 0.0], y_axis, z_axis),
        "platen": _frame([0.0, 0.0, g["thickness_nominal"]], y_axis, z_axis),
    }
    stocks = {
        "bar": (bar_x, bar_y, (skim - bar_t, skim)),
        "face": (blank_x, blank_y, (cut - t_max, cut)),
        "platen": (blank_x, blank_y, (0.0, third_max)),
        # After the face: the plate at its thickness.
        "holes": (blank_x, blank_y, (0.0, thick)),
    }
    sockets = []
    for hole in g["sockets"]:
        x, y, _z = _to(frames["platen"], [hole["x"], hole["y"], 0.0])
        sockets.append([_r(x), _r(y)])
    guides = []
    for hole in g["guides"]:
        x, y, _z = _to(frames["platen"], [hole["x"], hole["y"], 0.0])
        guides.append([_r(x), _r(y)])
    holes = sorted(sockets + guides)
    if not all(0 < x < length and -height < y < 0 for x, y in holes):
        raise ValueError(f"holes {holes} are not on the platen in the work frame")
    _agree(plan, "bar_relief_left_mm", x0_bar + sockets[0][0])
    _agree(plan, "bar_relief_right_mm", x0_bar + sockets[-1][0])
    if {x for x, _y in sockets} != {sockets[0][0], sockets[-1][0]}:
        raise ValueError("the sockets are not in two columns")

    half_tool = {
        "tool": "em-half",
        "dia": em,
        "shape": "endmill",
        "flutes": 3,
        "rpm": face_rpm,
        "feed": face_feed,
        "plunge": face_feed,
    }
    bar_tool = {**half_tool, "rpm": skim_rpm, "feed": skim_feed, "plunge": plunge_feed}
    spot_tool = {
        "tool": "spot",
        "dia": CENTRE_DRILL["body_mm"],
        "shape": "drill",
        "tip_angle": CENTRE_DRILL["point_deg"],
        "rpm": spot_rpm,
        "feed": spot_feed,
        "plunge": spot_feed,
    }
    socket_tool = {
        "tool": "drill-50",
        "dia": d50,
        "shape": "drill",
        "tip_angle": DRILL_POINT_DEG,
        "rpm": socket_rpm,
        "feed": socket_feed,
        "plunge": socket_feed,
    }
    guide_tool = {**socket_tool, "tool": "drill-27", "dia": d27}
    guide_tool.update(rpm=guide_rpm, feed=guide_feed, plunge=guide_feed)
    quarter_tool = {
        "tool": "em-quarter",
        "dia": quarter,
        "shape": "endmill",
        "flutes": 3,
        "rpm": cbore_rpm,
        "feed": cbore_feed,
        "plunge": plunge_feed,
    }

    # PL01: the bar's top over the seat, passes along X across the bar's
    # whole width; the plunge off the bar's back edge.
    bar_ys = _stations(bar_y, r, step_max)
    bar_lead = bar_y[1] + r + APPROACH_MM
    if not (free_x[0] <= seat[0] - r and seat[1] + r <= free_x[1]):
        raise ValueError("the bar skim reaches a step clamp's zone")
    # PL03/PL04: the largest blank, passes along X from beside its left end
    # to beside its right end.
    face_x = (blank_x[0] - r - APPROACH_MM, blank_x[1] + r + APPROACH_MM)
    if not (free_x[0] <= face_x[0] - r and face_x[1] + r <= free_x[1]):
        raise ValueError("the face passes reach a step clamp's zone")
    face_ys = _stations(blank_y, r, step_max)
    # Edges, the plate on the cutter's left: the left edge passes -Y, the
    # right +Y, the front (toward the operator) +X, the back -X. The left
    # and right passes run past the largest blank; the front and back ones,
    # cut after them, past the finished ends.
    edge_z = -through
    run_y = (blank_y[1] + r + APPROACH_MM, blank_y[0] - r - APPROACH_MM)
    run_x = (-r - APPROACH_MM, length + r + APPROACH_MM)
    edges = {
        "left": ("X", [-(s + r) for s in left["left"]], run_y),
        "right": ("X", [length + s + r for s in left["right"]], run_y[::-1]),
        "front": ("Y", [-(height + s + r) for s in left["front"]], run_x),
        "back": ("Y", [s + r for s in left["back"]], run_x[::-1]),
    }
    edge_lines = [f"G0 Z{_r(third_max + CLEAR_MM):.3f}"]
    for axis, stations, run in edges.values():
        edge_lines += _side(axis, stations, run, edge_z, third_max)

    clear = thick + CLEAR_MM
    jobs = [
        {
            **bar_tool,
            "model": "bar",
            "label": "bar skim",
            "stock": stocks["bar"],
            "ops": [
                [
                    "bar_skim",
                    "skim the bar's top",
                    _face(0.0, skim, seat, bar_ys, bar_lead),
                ]
            ],
        },
        {
            **bar_tool,
            "model": "bar",
            "label": "tap relief",
            "stock": stocks["bar"],
            "ops": [
                [
                    "relief",
                    "plunge the four relief pockets",
                    [
                        line
                        for xy in sockets
                        for line in _plunge(xy, 0.0, -relief, CLEAR_MM, "plunge")
                    ],
                ]
            ],
        },
        {
            **half_tool,
            "model": "face",
            "label": "face",
            "stock": stocks["face"],
            "ops": [["face", "face the blank", _face(0.0, cut, face_x, face_ys)]],
        },
        {
            **half_tool,
            "model": "platen",
            "label": "thickness and edges",
            "stock": stocks["platen"],
            "ops": [
                [
                    "thickness",
                    "face P to the thickness",
                    _face(thick, third_max, face_x, face_ys),
                ],
                ["edges", "mill the four edges to size", edge_lines],
            ],
        },
        {
            **spot_tool,
            "model": "platen",
            "label": "spot",
            "stock": stocks["holes"],
            "ops": [
                [
                    "spot",
                    "spot the fourteen holes",
                    [
                        line
                        for xy in holes
                        for line in _plunge(xy, thick, thick - spot_depth, clear)
                    ],
                ]
            ],
        },
        {
            **socket_tool,
            "model": "platen",
            "label": "socket drill",
            "stock": stocks["holes"],
            "ops": [
                [
                    "socket_drill",
                    "drill the four sockets #50",
                    [
                        line
                        for xy in sockets
                        for line in _plunge(xy, thick, socket_tip, clear)
                    ],
                ]
            ],
        },
        {
            **guide_tool,
            "model": "platen",
            "label": "guide drill",
            "stock": stocks["holes"],
            "ops": [
                [
                    "guide_drill",
                    "drill the ten guide holes #27",
                    [
                        line
                        for xy in guides
                        for line in _plunge(xy, thick, guide_tip, clear)
                    ],
                ]
            ],
        },
        {
            **quarter_tool,
            "model": "platen",
            "label": "counterbore",
            "stock": stocks["holes"],
            "ops": [
                [
                    "cbore",
                    "counterbore the ten guide holes",
                    [
                        line
                        for xy in guides
                        for line in _counterbore(xy, thick, floor, orbit, clear)
                    ],
                ]
            ],
        },
    ]

    # One file per socket to tap: the tap guide loaded by the file's own M6,
    # Z to the machine's top before any XY, over the hole, M30: the
    # controller ends Idle for the operator's jog.
    tags = {(_r(h["x"]), _r(-h["y"])): h["name"] for h in g["sockets"]}
    manual = {}
    for k, xy in enumerate(sockets, 1):
        what = f"SOCKET {tags[tuple(xy)].removeprefix('socket_').upper()}"
        manual[f"tap_{k}"] = {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": f"SPINDLE STAYS OFF. NEXT: 2-56 TAP IN {what}",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
                f"(2-56 TAP IN {what}. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND THROUGH TO THE NOTED DRO Z, READ WITH THE POINT PUSHED HOME."
                " JOG Z UP CLEAR)",
                "M30",
            ],
            "at": xy,
        }

    tn = numbers
    expect: list[list[Any]] = []

    def face_checks(
        z: float, top: float, y: tuple[float, float], span: float
    ) -> list[list[Any]]:
        return [
            ["rapids_clear", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            [
                "face_passes",
                {
                    "z": _r(z),
                    "y": list(y),
                    "max_engagement": step_max,
                    "radius": r,
                    "span": span,
                    "overhang": FACE_OVERHANG_MM,
                },
            ],
            ["keep_out", {"radius": r, "boxes": clamps}],
        ]

    def hole_checks(
        centres: list[list[float]], bottom: float, top: float, radius: float
    ) -> list[list[Any]]:
        return [
            ["depth", {"z_min": _r(bottom)}],
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": radius, "boxes": clamps}],
        ]

    def single(name: str, top: float, rpm: float) -> list[list[Any]]:
        return [
            [
                name,
                "tool_changes",
                {"z_top": top, "tools": [tn["em-half"]], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[rpm]]}],
            [name, "pauses", {"z_top": top, "count": 0}],
        ]

    name = "PL01_bar_skim"
    expect += single(name, skim, skim_rpm)
    expect += [[name, "depth", {"z_min": 0.0}]]
    expect += [
        [name, check, kwargs]
        for check, kwargs in face_checks(0.0, skim, bar_y, seat[1] - seat[0] - 1.0)
    ]
    name = "PL02_bar_relief"
    expect += single(name, 0.0, skim_rpm)
    expect += [
        [name, check, kwargs] for check, kwargs in hole_checks(sockets, -relief, 0.0, r)
    ]
    expect += [[name, "vertical_below_top", {"z_top": 0.0}]]
    name = "PL03_face"
    expect += single(name, cut, face_rpm)
    expect += [[name, "depth", {"z_min": 0.0}]]
    expect += [
        [name, check, kwargs] for check, kwargs in face_checks(0.0, cut, blank_y, l_min)
    ]

    name = "PL04_platen"
    order = ["em-half", "spot", "drill-50", "drill-27", "em-quarter"]
    expect += [
        [
            name,
            "tool_changes",
            {"z_top": thick, "tools": [tn[t] for t in order], "loads_first": True},
        ],
        [
            name,
            "spindle",
            {"rpm": [[face_rpm], [spot_rpm], [socket_rpm], [guide_rpm], [cbore_rpm]]},
        ],
        [name, "pauses", {"z_top": thick, "count": 0}],
        [name, "depth", {"z_min": _r(guide_tip)}],
    ]
    # Each edge: its last pass at the finished size, from the largest
    # margin's raw station in the plan's steps, the plate on the cutter's
    # left.
    way = {"left": -1.0, "right": 1.0, "front": 1.0, "back": -1.0}
    span = {"X": height, "Y": length}
    edge_checks = [
        [
            "side_passes",
            {
                "axis": axis,
                "final": _r(stations[-1]),
                "raw": _r(
                    stations[-1]
                    + margins[edge][1] * (1.0 if stations[0] > stations[-1] else -1.0)
                ),
                "max_step": edge_step,
                "finish": edge_finish,
                "direction": way[edge],
                "span": span[axis],
                "below_z": 0.0,
            },
        ]
        for edge, (axis, stations, _run) in edges.items()
    ]
    expect += [
        [f"{name}@0", check, kwargs]
        for check, kwargs in [
            ["depth", {"z_min": _r(edge_z)}],
            *face_checks(thick, third_max, blank_y, l_min),
            *edge_checks,
            # What the edge passes really meet in the largest blank: no more
            # than the plan's step, on the cutter's left (conventional, M3).
            [
                "engagement",
                {
                    "stock": [list(axis) for axis in stocks["platen"]],
                    "radius": r,
                    "max_radial": edge_step,
                    "z": _r(edge_z),
                    "min_length": height,
                    "cut": "conventional",
                    "cell": ENGAGEMENT_CELL_MM,
                },
            ],
        ]
    ]
    sections = (
        hole_checks(holes, thick - spot_depth, thick, CENTRE_DRILL["body_mm"] / 2),
        hole_checks(sockets, socket_tip, thick, d50 / 2),
        hole_checks(guides, guide_tip, thick, d27 / 2),
        hole_checks(guides, floor, thick, quarter / 2),
    )
    for k, checks in enumerate(sections, 1):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]
        if k < 4:
            expect.append([f"{name}@{k}", "vertical_below_top", {"z_top": thick}])
    # Each counterbore: the cutter's centre stays within the circle's box
    # round its hole, turns clockwise only and reaches the floor.
    for x, y in guides:
        expect.append(
            [
                f"{name}@4",
                "bounds",
                {
                    "window": [[x - 1.0, x + 1.0], [y - 1.0, y + 1.0]],
                    "x": [_r(x - orbit), _r(x + orbit)],
                    "y": [_r(y - orbit), _r(y + orbit)],
                    "z_min": _r(floor),
                    "arc": "G2",
                    "entry": [x, y],
                    "z_top": thick,
                },
            ]
        )
    # The counterbore circles, clockwise inside each: conventional.
    expect.append(
        [
            f"{name}@4",
            "arcs",
            {
                "z_top": thick,
                "centres": guides,
                "part": "outside",
                "cut": "conventional",
            },
        ]
    )
    for k, key in enumerate(sorted(manual), 5):
        expect += [
            [
                f"PL{k:02d}_{key}",
                "tap_stop",
                {
                    "tool": tn["tap-guide"],
                    "at": manual[key]["at"],
                    "machine_top": MACHINE_Z_TOP_MM,
                },
            ],
            [f"PL{k:02d}_{key}", "air_feed", {"z_top": thick}],
        ]

    # The cutter's centre stays inside the machine's travel: every station
    # and run end of every program, and the edge finder's two touches.
    reach = {
        "x": [
            -(x0_bar + FINDER_RADIUS_MM),
            *seat,
            *face_x,
            *run_x,
            *edges["left"][1],
            *edges["right"][1],
        ],
        "y": [
            -(y0_bar + FINDER_RADIUS_MM),
            bar_lead,
            *bar_ys,
            *face_ys,
            *run_y,
            *edges["front"][1],
            *edges["back"][1],
        ],
    }
    travel = machine["travel_mm"]
    for axis, stations in reach.items():
        span = max(stations) - min(stations)
        if span > travel[axis]:
            raise ValueError(f"the {axis} travel {span:.1f} is over {travel[axis]}")

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": frames,
        "bar": [list(bar_x), list(bar_y), [skim - bar_t, 0.0]],
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
            doc, f"Platen {key}", ctx["step"], frame["origin"], frame["axes"]
        )
        for key, frame in ctx["frames"].items()
    }
    models["bar"] = rt.box(doc, "Fixture bar", *ctx["bar"])
    ops: dict[str, Any] = {}
    for section in ctx["jobs"]:
        target = rt.job(
            doc, section["label"], [models[section["model"]]], section["stock"]
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
