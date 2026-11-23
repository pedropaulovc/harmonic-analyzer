"""FreeCAD CAM recipe for MHA-FR-05, the rocker arm support.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The support's sizes
come from the feature export (the end faces, the foot and the top face, the
slant planes, the web faces, the pocket and cavity squares and their corner
radii, the foot holes and the chamfer's leg band); the blank, levels,
stepovers, allowances, holes' depths and the holding from ``plan.toml``
``[parameters]`` and ``milling_cuts``; cutter diameters, speeds and feeds
from the shop (``shop/``) and the plan's authored drill settings. Every path
is written here (``rt.custom``). Typed here, because no record carries them:
the #2 centre drill's catalogue geometry (it sets the spot depth), the twist
drills' 118° point, the approach, safe and clearance heights, the sampling
steps of the paths and the keep-out sizes of the clamps (a strap's lane, a
flange nut's reach).

Route (plan text in ``plan.toml``): one 3 x 8 x 8 in 1018 slab, the part's
X (7.56) along the sawn 8 in length, Y (7.00, the foot at -Y) along the
bar's 8 in width, Z (2.50) across the 3 in thickness, centred in it. On the
table on four 1-2-3 blocks under two end straps, side A (+Z) up: FR01 spots
and drills two 13/32 stud holes through the slab inside the cavity and
counterbores them in the boss (waste) for the flange nuts. Studs up through
them hold the slab by the uncut boss, nuts and stud ends below the top; the
straps come off. Side A in three files: FR02 the rough levels, the pocket
floor (the web) and the slant face; FR03 the pocket walls; FR04 the outline
to just past the mid-plane, then the chamfer mill on the slant face's
edges, the pocket rim and the cavity rim's groove in the web. Flipped end
over end onto the same studs (nuts on the boss's side B face), the boss on
the centre blocks and screw jacks under the end posts: FR05-FR07 mill side
B the same way (no groove), the outline meeting side A's past the
mid-plane. Two end straps then hold the frame by its posts and FR08 cuts
the cavity through the web, freeing the boss on its studs; at its M6 T5
stop the boss and studs come out and the chamfer mill cuts side B's cavity
rim. Standing on its top face, the foot up, under two straps: FR09 spots
and drills the four foot holes.

Work frames (G54):
- FR01-FR08: X0 Y0 the part's centre (FR01-FR04 between the sawn ends and
  the bar's edges; FR05-FR08 on the stud holes and the bar's edges), Z0 the
  slab's mid-plane (the top less half the miked thickness). FR01-FR04 +Z is
  model +Z (side A up); FR05-FR08 the slab turned end over end about Y:
  X is model -X, Z model -Z. The part is symmetric in X and in Z, so one
  side's geometry serves both.
- FR09: X0 the centre between the end faces, Y0 the centre between the
  slants (Y is model Z), Z0 the foot face (Z is model -Y).

Toolpath rules (owner rulings 2026-11-16): faces and rough levels zigzag
(ball screws), real G0 only above the stock, plunges beside the stock or
into waste a level deep at the plunge feed; the outline, the pocket walls
and the cavity climb.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "fr_rocker_arm_support"
COMMENT = "MHA-FR-05 rocker arm support"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes; sections of one tool at one speed run on without a stop.
# Each side runs as three files, so each climb loop is a tool section of its
# own that check_outline reads whole: the rough levels, the floor and the
# slant face; the pocket walls; the outline, then the chamfers.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("FR01_studs", (("stud_spot",), ("stud_drill",), ("stud_cbore",))),
    ("FR02_a_mill", (("a_rough",), ("a_floor",), ("a_slant",))),
    ("FR03_a_walls", (("a_walls",),)),
    ("FR04_a_outline", (("a_outline",), ("a_chamfer",))),
    ("FR05_b_mill", (("b_rough",), ("b_floor",), ("b_slant",))),
    ("FR06_b_walls", (("b_walls",),)),
    ("FR07_b_outline", (("b_outline",), ("b_chamfer",))),
    ("FR08_cavity", (("cavity",), ("b_cavity_chamfer",))),
    ("FR09_foot", (("foot_spot",), ("foot_drill",))),
)
# Every program loads its first tool (M6, the tool setter): each runs after a
# new clamping on whatever the mill last held.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's
# tool list among these.
CAM_TOOLS = ("em-3-8", "spot", "drill-13-32", "drill-5-16", "chamfer")
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
# Passes start and finish this far clear of the stock's or the part's edge.
APPROACH_MM = 2.54
# Plunges and drill R planes start this far above the stock top.
SAFE_MM = 1.0
# Rapids between cuts run this far above the stock top: over the studs'
# flange nuts and the studs' ends (the plan's holding keeps each stud's end
# at most stud_above_seat_mm above its nut's seat).
CLEAR_MM = 50.8
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Path sampling: the passes are computed at this spacing; each move between
# two nodes is checked at its midpoint.
SAMPLE_MM = 0.5
# Cutter-footprint sampling: its rim every RIM_STEP_DEG, an interior grid at
# DISC_GRID_MM, and CHORD_POINTS along each chord the footprint cuts on the
# rim's lower edges (the foot edge, the pocket's +Y wall): the slant falls
# along +Y, so its highest point under the cutter lies on the rim's lowest
# edge inside the footprint, exactly.
RIM_STEP_DEG = 0.5
DISC_GRID_MM = 1.0
CHORD_POINTS = 17
# Keep-outs typed here (no record gives them): a step clamp's lane, half its
# width either side of its centre line, its nose this far past the clamp
# point; a 3/8-16 flange nut's reach about its stud; a strap's height over
# what it clamps.
STRAP_HALF_WIDTH_MM = 12.7
STRAP_NOSE_MM = 12.7
NUT_RADIUS_MM = 12.7
# The spindle nose over the studs: wherever a nose of the plan's
# spindle_nose_dia_max_mm comes over a stud's flange nut, its face (the
# tool's tip plus its holder's gauge and projection) stays at least
# NOSE_CLEAR_MM above the stud's highest allowed end.
NOSE_CLEAR_MM = 5.0
STRAP_HEIGHT_MM = 25.4
# Path tolerances: an outline's cutter centre may stray this far from its
# offset (3 places, arc end-point rounding); a plan number the recipe
# recomputes must agree to this.
OUTLINE_TOL_MM = 0.01
PLAN_TOL_MM = 0.01


def _plan_operations(plan: dict[str, Any]):
    for setup in plan["setups"]:
        yield from setup.get("operations", ())


def _op_with_cut(plan: dict[str, Any], name: str) -> tuple[dict[str, Any], dict[str, Any]]:
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
            raise ValueError(f"{what} = {value!r}: only numbers and {{{{process.…}}}} bindings are read")
        value = plan["parameters"][match.group(1)]
    return float(value)


def _cut(plan: dict[str, Any], name: str, key: str) -> float:
    return _resolve(plan, _op_with_cut(plan, name)[1][key], f"'{name}' {key}")


def _setting(plan: dict[str, Any], shop: dict[str, Any], cut: str) -> tuple[float, float]:
    """(rpm, mm/min) of the operation holding ``cut``: the shop setting it
    names, or, with no setting, the rpm and feed the cut itself authors."""
    op, record_cut = _op_with_cut(plan, cut)
    if "settings" not in op:
        return _cut(plan, cut, "rpm"), _cut(plan, cut, "feed_mm_min")
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    feed = record["chip_load_mm_per_tooth"] * record["flutes"] * rpm
    for key, expected in (("rpm", rpm), ("feed_mm_min", feed)):
        if key in record_cut and not math.isclose(_cut(plan, cut, key), expected, abs_tol=1e-3):
            raise ValueError(f"'{cut}' {key} {_cut(plan, cut, key):g} is not its setting's {expected:g}")
    return rpm, feed


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


def _levels(top: float, bottom: float, max_step: float) -> list[float]:
    """Equal step-down levels no deeper than ``max_step`` from ``top`` to
    ``bottom``, ``bottom`` last."""
    n = math.ceil((top - bottom) / max_step - 1e-9)
    return [top - (top - bottom) * (k + 1) / n for k in range(n - 1)] + [bottom]


def _r(value: float) -> float:
    """A coordinate as the post prints it (3 places)."""
    return round(value + 0.0, 3)


def _segment_distance(a, b, p) -> float:
    """Distance in XY from point ``p`` to the segment ``a``–``b``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1])


def _box(name: str, x: tuple[float, float], y: tuple[float, float], z_top: float) -> dict[str, Any]:
    return {"name": name, "x": [x[0], x[1]], "y": [y[0], y[1]], "z_top": z_top}


def _agree(plan: dict[str, Any], key: str, value: float) -> None:
    """A plan parameter the recipe recomputes from the export and the shop."""
    stated = plan["parameters"][key]
    if not math.isclose(stated, value, abs_tol=PLAN_TOL_MM):
        raise ValueError(f"process.{key} {stated:g}, the recipe computes {value:.4f}")


def _spot_depth(dia: float) -> float:
    """Depth at which the #2 centre drill's 60° countersink reaches ``dia``."""
    pilot, body = CENTRE_DRILL["pilot_mm"], CENTRE_DRILL["body_mm"]
    if not pilot < dia <= body:
        raise ValueError(f"spot Ø{dia:.3f} is not between the pilot Ø{pilot:.3f} and the body Ø{body:.3f}")
    half = math.radians(CENTRE_DRILL["point_deg"] / 2)
    return CENTRE_DRILL["pilot_length_mm"] + (dia - pilot) / 2 / math.tan(half)


def _point(dia: float) -> float:
    """A twist drill's point length."""
    return dia / 2 / math.tan(math.radians(DRILL_POINT_DEG / 2))


def _frame(origin: list[float], y_axis: list[float], z_axis: list[float]) -> dict[str, Any]:
    """A right-handed setup frame from its Y and Z model axes: X = Y × Z."""
    y, z = y_axis, z_axis
    x = [y[1] * z[2] - y[2] * z[1], y[2] * z[0] - y[0] * z[2], y[0] * z[1] - y[1] * z[0]]
    return {"origin": origin, "axes": [x, y, z]}


def _to(frame: dict[str, Any], p: list[float]) -> list[float]:
    d = [p[i] - frame["origin"][i] for i in range(3)]
    return [sum(axis[i] * d[i] for i in range(3)) for axis in frame["axes"]]


def _spot(xy: tuple[float, float], top: float, z: float, clear: float) -> list[str]:
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _pecked(xy: tuple[float, float], top: float, tip: float, peck: float | None, clear: float) -> list[str]:
    """Drill from ``top`` to ``tip`` in pecks of ``peck`` (``None``: one
    plunge), each with a full retract to the R plane."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    depths = []
    depth = top
    while peck is not None and depth - peck > tip + 1e-6:
        depth -= peck
        depths.append(_r(depth))
    depths.append(_r(tip))
    lines = [f"G0 Z{clear:.3f}", f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}", f"G0 Z{r_plane:.3f}"]
    previous = None
    for z in depths:
        if previous is not None:
            lines += [f"G0 Z{r_plane:.3f}", f"G0 Z{_r(previous + PECK_REENTRY_MM):.3f}"]
        lines.append(f"G1 Z{z:.3f} F{{feed}}")
        previous = z
    return lines + [f"G0 Z{r_plane:.3f}", f"G0 Z{clear:.3f}"]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The support's sizes from the feature export, model frame (mm). The
    route rests on the part's symmetry in X and Z and on squares centred on
    the origin: each is checked."""
    f = features["features"]

    def plane(name: str, axis: str) -> float:
        p = f[name]["plane"]
        if p["axis"] != axis:
            raise ValueError(f"{name}: plane on {p['axis']}, expected {axis}")
        return float(p["value"])

    xe, xw = plane("east_end", "x"), plane("west_end", "x")
    yt, yf = plane("top_face", "y"), plane("foot", "y")
    web, web_m = plane("web_plus_z", "z"), plane("web_minus_z", "z")
    for what, a, b in (("ends", xe, -xw), ("top and foot", yt, -yf), ("web faces", web, -web_m)):
        if not math.isclose(a, b, abs_tol=1e-6):
            raise ValueError(f"the {what} are not symmetric about the origin: {a} / {-b}")
    slant, slant_m = f["slant_plus_z"], f["slant_minus_z"]
    at, n = slant["at"], slant["normal"]
    if not (math.isclose(at[1], yf, abs_tol=1e-6) and n[0] == 0.0 and n[2] > 0 and n[1] > 0):
        raise ValueError("slant_plus_z: expected the foot edge's point and a normal in +Y+Z")
    if not (
        math.isclose(slant_m["at"][2], -at[2], abs_tol=1e-6)
        and math.isclose(slant_m["normal"][1], n[1], abs_tol=1e-9)
        and math.isclose(slant_m["normal"][2], -n[2], abs_tol=1e-9)
    ):
        raise ValueError("slant_minus_z is not slant_plus_z mirrored in Z")
    zf, k = float(at[2]), n[1] / n[2]
    zt = zf - k * (yt - yf)
    if not math.isclose(zt, slant["top_half_width_nominal"], abs_tol=1e-3):
        raise ValueError(f"the slant reaches {zt:.4f} at the top, the export {slant['top_half_width_nominal']}")

    def square(name: str) -> tuple[float, float]:
        rec = f[name]
        half, rad = rec["size_nominal"] / 2, rec["corner_radius_nominal"]
        x0 = rec["at"][0]
        y0 = rec["at"][1]
        centre_x = x0 + half
        # The pocket's "at" is its -X -Y corner, the cavity's its -X +Y corner.
        centre_y = y0 + half if y0 < 0 else y0 - half
        if abs(centre_x) > 1e-6 or abs(centre_y) > 1e-6:
            raise ValueError(f"{name}: not centred on the origin ({centre_x}, {centre_y})")
        return half, rad

    pocket, pocket_r = square("pockets")
    cavity, cavity_r = square("cavity")
    if not math.isclose(f["pockets"]["at"][2], web, abs_tol=1e-6):
        raise ValueError("the pockets' floor is not the web face")
    holes = []
    for tag in ("a1", "a2", "a3", "a4"):
        h = f[f"foot_hole_{tag}"]
        if h["axis"] != [0.0, 1.0, 0.0] or not math.isclose(h["at"][1], yf, abs_tol=1e-6):
            raise ValueError(f"foot_hole_{tag}: expected +Y from the foot face")
        holes.append((float(h["at"][0]), float(h["at"][2]), float(h["nominal_dia"]), h["dia"]))
    chamfer = f["rim_chamfer"]
    return {
        "xe": xe,
        "yt": yt,
        "yf": yf,
        "web": web,
        "zf": zf,
        "zt": zt,
        "k": k,
        "pocket": pocket,
        "pocket_r": pocket_r,
        "cavity": cavity,
        "cavity_r": cavity_r,
        "holes": holes,
        "foot_thickness": -pocket - yf,
        "chamfer": float(chamfer["leg_nominal"]),
        "chamfer_band": [float(v) for v in chamfer["leg"]],
        "floor_corner_max": float(f["pockets"]["floor_corner_radius_max"]),
    }


# --- Heights and the cutter's footprint ----------------------------------------


def _rrect_inside(np, x, y, half: float, rad: float):
    """Inside the square of half-size ``half`` with corners of radius ``rad``,
    centred on the origin."""
    ax = np.abs(x) - (half - rad)
    ay = np.abs(y) - (half - rad)
    box = (np.abs(x) <= half) & (np.abs(y) <= half)
    corner = (ax > 0) & (ay > 0)
    return box & (~corner | (ax * ax + ay * ay <= rad * rad))


def _disc(np, radius: float):
    """Offsets sampling a flat cutter's footprint: its rim every RIM_STEP_DEG
    and an interior grid at DISC_GRID_MM."""
    angles = np.radians(np.arange(0.0, 360.0, RIM_STEP_DEG))
    rim = np.stack([radius * np.cos(angles), radius * np.sin(angles)], axis=1)
    n = int(radius // DISC_GRID_MM)
    grid = np.arange(-n, n + 1) * DISC_GRID_MM
    gx, gy = np.meshgrid(grid, grid)
    inner = np.stack([gx.ravel(), gy.ravel()], axis=1)
    inner = inner[np.hypot(inner[:, 0], inner[:, 1]) < radius]
    return np.concatenate([rim, inner])


class _Field:
    """One side's finished (or allowance-grown) top surface, the side up, in
    the model frame: below the slant on the rim, the web (``floor``) in the
    pocket, ``bottom`` outside the outline; the boss (the uncut middle the
    studs clamp) is out of reach. ``wall`` grows the rim into the pocket and
    out past the outline, ``slant`` lifts the slant."""

    def __init__(self, np, g, *, wall: float, slant: float, floor: float, bottom: float, boss: float, radius: float):
        self.np, self.g = np, g
        self.wall, self.slant, self.floor, self.bottom, self.boss = wall, slant, floor, bottom, boss
        self.radius = radius
        self.offsets = _disc(np, radius)
        # The rim's lower edges, just inside the rim.
        self.edges = (g["yf"] - wall + 1e-9, g["pocket"] - wall + 1e-9)

    def heights(self, x, y):
        np, g = self.np, self.g
        out = (np.abs(x) > g["xe"] + self.wall) | (np.abs(y) > g["yt"] + self.wall)
        pocket = _rrect_inside(np, x, y, g["pocket"] - self.wall, g["pocket_r"] - self.wall)
        rim = g["zf"] - g["k"] * (y - g["yf"]) + self.slant
        h = np.where(out, self.bottom, np.where(pocket, self.floor, rim))
        boss = (np.abs(x) <= self.boss) & (np.abs(y) <= self.boss)
        return np.where(boss, np.inf, h)

    def rim(self, x, y):
        """True where a point lies on the rim (the slant), allowance included."""
        np, g = self.np, self.g
        out = (np.abs(x) > g["xe"] + self.wall) | (np.abs(y) > g["yt"] + self.wall)
        pocket = _rrect_inside(np, x, y, g["pocket"] - self.wall, g["pocket_r"] - self.wall)
        return ~out & ~pocket

    def drop(self, points):
        """The lowest the cutter's tip may sit over each XY in ``points``
        (n × 2): the highest surface under its footprint."""
        np = self.np
        points = np.asarray(points, dtype=float)
        result = np.empty(len(points))
        chunk = max(1, 200_000 // len(self.offsets))
        t = np.linspace(-1.0, 1.0, CHORD_POINTS)
        for start in range(0, len(points), chunk):
            p = points[start : start + chunk]
            x = p[:, 0:1] + self.offsets[None, :, 0]
            y = p[:, 1:2] + self.offsets[None, :, 1]
            best = self.heights(x, y).max(axis=1)
            for edge in self.edges:
                dy = edge - p[:, 1]
                inside = np.abs(dy) < self.radius
                half = np.sqrt(np.clip(self.radius**2 - dy**2, 0.0, None)) * (1 - 1e-9)
                cx = p[:, 0:1] + half[:, None] * t[None, :]
                h = self.heights(cx, np.full_like(cx, edge)).max(axis=1)
                best = np.where(inside, np.maximum(best, h), best)
            result[start : start + chunk] = best
        return result

    def touches_rim(self, points):
        np = self.np
        points = np.asarray(points, dtype=float)
        result = np.empty(len(points), dtype=bool)
        chunk = max(1, 200_000 // len(self.offsets))
        for start in range(0, len(points), chunk):
            p = points[start : start + chunk]
            x = p[:, 0:1] + self.offsets[None, :, 0]
            y = p[:, 1:2] + self.offsets[None, :, 1]
            result[start : start + chunk] = self.rim(x, y).any(axis=1)
        return result


def _samples(a: float, b: float) -> list[float]:
    n = max(1, math.ceil(abs(b - a) / SAMPLE_MM - 1e-9))
    return [a + (b - a) * i / n for i in range(n + 1)]


def _nodes(points: list[tuple[float, float]], zs: list[float]) -> list[tuple[float, float, float]]:
    """Path nodes from samples at SAMPLE_MM, every other one a node, each
    odd sample the midpoint check of its move: where a straight move would
    pass under the surface the cutter climbs first (rising) or descends last
    (falling), so no move cuts below the field. Collinear nodes merge."""
    out: list[tuple[float, float, float]] = []

    def push(p):
        if out and all(abs(a - b) < 1e-9 for a, b in zip(out[-1], p)):
            return
        out.append(p)

    last = len(points) - 1
    i = 0
    push((points[0][0], points[0][1], zs[0]))
    while i < last:
        j = min(i + 2, last)
        z0, z1 = zs[i], zs[j]
        mid_ok = True
        if j == i + 2:
            mid_ok = (z0 + z1) / 2 >= zs[i + 1] - 1e-6
        if abs(z1 - z0) < 1e-9 and mid_ok:
            push((points[j][0], points[j][1], z1))
        elif mid_ok:
            push((points[j][0], points[j][1], z1))
        else:
            top = max(z0, z1, zs[i + 1])
            push((points[i][0], points[i][1], top))
            push((points[j][0], points[j][1], top))
            push((points[j][0], points[j][1], z1))
        i = j
    # Merge collinear runs.
    merged: list[tuple[float, float, float]] = []
    for p in out:
        if len(merged) >= 2:
            a, b = merged[-2], merged[-1]
            d1 = [b[i] - a[i] for i in range(3)]
            d2 = [p[i] - b[i] for i in range(3)]
            cross = [
                d1[1] * d2[2] - d1[2] * d2[1],
                d1[2] * d2[0] - d1[0] * d2[2],
                d1[0] * d2[1] - d1[1] * d2[0],
            ]
            dot = sum(d1[i] * d2[i] for i in range(3))
            if math.hypot(*cross) < 1e-6 * max(1.0, math.hypot(*d1) * math.hypot(*d2)) and dot > 0:
                merged[-1] = p
                continue
        merged.append(p)
    return merged


def _moves(nodes, level_above: float) -> list[str]:
    """G1 lines through ``nodes`` (repeats as posted dropped): descents
    steeper than 45° that end below ``level_above`` (into stock a level deep)
    at the plunge feed, the rest at the feed."""
    lines = []
    prev = tuple(_r(v) for v in nodes[0])
    for node in nodes[1:]:
        p = tuple(_r(v) for v in node)
        if p == prev:
            continue
        drop = prev[2] - p[2]
        falling = drop > 1e-6 and p[2] < level_above - 1e-6 and drop > math.dist(prev[:2], p[:2])
        feed = "{plunge}" if falling else "{feed}"
        lines.append(f"G1 X{p[0]:.3f} Y{p[1]:.3f} Z{p[2]:.3f} F{feed}")
        prev = p
    return lines


def _enter(p, top: float, clear: float, level_above: float) -> list[str]:
    """Rapid over ``p`` at the clearance, down to just above the stock top,
    then feed down: to just above the last level through the cleared air, and
    at the plunge feed the last level deep."""
    above = min(top + SAFE_MM, max(level_above + SAFE_MM / 2, p[2]))
    lines = [f"G0 Z{_r(clear):.3f}", f"G0 X{_r(p[0]):.3f} Y{_r(p[1]):.3f}", f"G0 Z{_r(top + SAFE_MM):.3f}"]
    if above < top + SAFE_MM - 1e-6:
        lines.append(f"G1 Z{_r(above):.3f} F{{feed}}")
    if p[2] < above - 1e-6:
        lines.append(f"G1 Z{_r(p[2]):.3f} F{{plunge}}")
    return lines


def _leave(top: float, clear: float) -> list[str]:
    return [f"G1 Z{_r(top + SAFE_MM):.3f} F{{feed}}", f"G0 Z{_r(clear):.3f}"]


def _raster(
    field: _Field,
    passes: list[tuple[str, float, tuple[float, float]]],
    levels: list[float],
    first_above: float,
    top: float,
    clear: float,
    link_max: float,
    rim_only: bool = False,
) -> tuple[list[str], int]:
    """Passes, each ``(axis, station, (start, end))`` along ``axis``, at each
    of ``levels`` in turn (the first under ``first_above``): the cutter at the
    level or on the field, whichever is higher, only where the field is below
    the level above (there is stock to cut); ``rim_only`` keeps only where the
    cutter meets the rim. Each level's runs are taken nearest end first (a
    zigzag where the runs allow); a run links to the next at the level when
    the link is at most ``link_max`` long and stays on the field below the
    stock top, else the cutter leaves and re-enters from above. Returns the
    lines and the number of entries."""
    np = field.np
    lines: list[str] = []
    entries = 0
    sampled = []
    for axis, station, (a, b) in passes:
        along = _samples(a, b)
        pts = [(s, station) if axis == "x" else (station, s) for s in along]
        mask = field.touches_rim(pts) if rim_only else np.ones(len(pts), dtype=bool)
        sampled.append((pts, field.drop(pts), mask))
    previous = first_above
    for level in levels:
        runs = []
        for pts, drops, mask in sampled:
            cut = (drops < previous - 1e-6) & mask
            i = 0
            while i < len(pts):
                if not cut[i]:
                    i += 1
                    continue
                j = i
                while j + 1 < len(pts) and cut[j + 1]:
                    j += 1
                if j > i:
                    runs.append((pts[i : j + 1], [max(level, float(d)) for d in drops[i : j + 1]]))
                i = j + 1
        position = None
        while runs:
            if position is None:
                index, reverse = 0, False
            else:
                index, reverse = min(
                    ((n, rev) for n in range(len(runs)) for rev in (False, True)),
                    key=lambda c: math.dist(position[:2], runs[c[0]][0][-1 if c[1] else 0]),
                )
            pts, zs = runs.pop(index)
            if reverse:
                pts, zs = pts[::-1], zs[::-1]
            nodes = _nodes(pts, zs)
            linked = False
            if position is not None and math.dist(position[:2], nodes[0][:2]) <= link_max + 1e-6:
                span = math.dist(position[:2], nodes[0][:2])
                lpts = [
                    (position[0] + (nodes[0][0] - position[0]) * t / span, position[1] + (nodes[0][1] - position[1]) * t / span)
                    for t in _samples(0.0, span)
                ] if span > 1e-9 else [tuple(position[:2])]
                ld = field.drop(lpts)
                if np.all(np.isfinite(ld)) and float(ld.max()) < top - SAFE_MM:
                    lnodes = _nodes(lpts, [max(level, float(d)) for d in ld])
                    lines += _moves([position, *lnodes], previous)
                    position = lnodes[-1]
                    linked = True
            if not linked:
                if position is not None:
                    lines += _leave(top, clear)
                lines += _enter(nodes[0], top, clear, previous)
                entries += 1
                position = nodes[0]
            elif math.dist(position, nodes[0]) > 1e-6:
                lines += _moves([position, nodes[0]], previous)
            lines += _moves(nodes, previous)
            position = nodes[-1]
        if position is not None:
            lines += _leave(top, clear)
        previous = level
    return lines, entries


def _rrect_loop(half: float, rad: float, offset: float, outside: bool, clockwise: bool):
    """The cutter-centre loop at ``offset`` outside (``outside``) or inside a
    rounded square, as elements (lines and arcs) and as G-code from its
    start, the middle of its -Y side. Also returns the part outline's
    elements in the same order and direction (for check_outline)."""
    h = half + offset if outside else half - offset
    rc = rad + offset if outside else rad - offset
    if rc <= 0:
        raise ValueError(f"offset {offset} leaves no corner arc in R{rad}")
    s = half - rad  # corner centres at (±s, ±s)
    # Anticlockwise sequence from the -Y side's middle.
    seq = [
        ("line", (0.0, -h), (s, -h)),
        ("arc", (s, -h), (h, -s), (s, -s)),
        ("line", (h, -s), (h, s)),
        ("arc", (h, s), (s, h), (s, s)),
        ("line", (s, h), (-s, h)),
        ("arc", (-s, h), (-h, s), (-s, s)),
        ("line", (-h, s), (-h, -s)),
        ("arc", (-h, -s), (-s, -h), (-s, -s)),
        ("line", (-s, -h), (0.0, -h)),
    ]
    part_seq = [
        ("line", (0.0, -half), (s, -half)),
        ("arc", (s, -half), (half, -s), (s, -s)),
        ("line", (half, -s), (half, s)),
        ("arc", (half, s), (s, half), (s, s)),
        ("line", (s, half), (-s, half)),
        ("arc", (-s, half), (-half, s), (-s, s)),
        ("line", (-half, s), (-half, -s)),
        ("arc", (-half, -s), (-s, -half), (-s, -s)),
        ("line", (-s, -half), (0.0, -half)),
    ]
    if clockwise:
        seq = [(e[0], e[2], e[1], *e[3:]) for e in reversed(seq)]
        part_seq = [(e[0], e[2], e[1], *e[3:]) for e in reversed(part_seq)]
    return seq, part_seq


def _loop_gcode(seq, z: float, clockwise: bool) -> list[str]:
    lines = []
    for e in seq:
        end = e[2]
        if e[0] == "line":
            lines.append(f"G1 X{_r(end[0]):.3f} Y{_r(end[1]):.3f} Z{_r(z):.3f} F{{feed}}")
        else:
            start, centre = e[1], e[3]
            word = "G2" if clockwise else "G3"
            lines.append(
                f"{word} X{_r(end[0]):.3f} Y{_r(end[1]):.3f} I{_r(centre[0] - start[0]):.3f} J{_r(centre[1] - start[1]):.3f} F{{feed}}"
            )
    return lines


def _elements(part_seq, tol: float) -> list[dict[str, Any]]:
    out = []
    for n, e in enumerate(part_seq):
        item = {"name": f"{e[0]} {n}", "start": [e[1][0], e[1][1]], "end": [e[2][0], e[2][1]], "tol": tol}
        if e[0] == "arc":
            item["centre"] = [e[3][0], e[3][1]]
        out.append(item)
    # Drop zero-length lines (a corner-only square).
    return [e for e in out if "centre" in e or math.dist(e["start"], e["end"]) > 1e-9]


def _rect_loop(xh: float, yh: float, offset: float):
    """A rectangle's outside cutter loop, clockwise (climb with M3), from the
    -Y side's middle, sharp corners rounded at the offset; and the
    rectangle's elements in the same order."""
    seq = [
        ("line", (0.0, -yh - offset), (-xh, -yh - offset)),
        ("arc", (-xh, -yh - offset), (-xh - offset, -yh), (-xh, -yh)),
        ("line", (-xh - offset, -yh), (-xh - offset, yh)),
        ("arc", (-xh - offset, yh), (-xh, yh + offset), (-xh, yh)),
        ("line", (-xh, yh + offset), (xh, yh + offset)),
        ("arc", (xh, yh + offset), (xh + offset, yh), (xh, yh)),
        ("line", (xh + offset, yh), (xh + offset, -yh)),
        ("arc", (xh + offset, -yh), (xh, -yh - offset), (xh, -yh)),
        ("line", (xh, -yh - offset), (0.0, -yh - offset)),
    ]
    part = [
        {"name": "foot, from the middle", "start": [0.0, -yh], "end": [-xh, -yh]},
        {"name": "west end", "start": [-xh, -yh], "end": [-xh, yh]},
        {"name": "top face", "start": [-xh, yh], "end": [xh, yh]},
        {"name": "east end", "start": [xh, yh], "end": [xh, -yh]},
        {"name": "foot, to the middle", "start": [xh, -yh], "end": [0.0, -yh]},
    ]
    for e in part:
        e["tol"] = OUTLINE_TOL_MM
    return seq, part


def _chamfer_depth(c: float, g: float) -> tuple[float, float]:
    """For an edge where a vertical wall meets a face sloping g (rise per run)
    going from the edge into the material, the 45° cone's depth on the wall
    that gives equal mean legs ``c``: returns (wall leg, face leg)."""
    ratio = math.sqrt(1 + g * g) / (1 - g)
    wall = 2 * c / (1 + ratio)
    return wall, wall * ratio


def _chamfer_path(points, top_z, slope, c: float, e: float):
    """Apex nodes along an edge loop: ``points`` the edge's XY with the
    outward direction (into the cutter's side) at each, ``top_z`` the face
    height there, ``slope`` the face's rise into the material there. The
    apex sits ``e`` off the wall into the cutter's side, the wall leg plus
    ``e`` below the face's edge."""
    nodes = []
    for (x, y, nx, ny), z, g in zip(points, top_z, slope):
        wall, _face = _chamfer_depth(c, g)
        nodes.append((x + nx * e, y + ny * e, z - wall - e))
    return nodes


def _rrect_edge(half: float, rad: float, inward: bool, step: float):
    """Points along a rounded square's edge every ``step``, anticlockwise from
    the -Y side's middle, each with the unit normal pointing away from the
    material: inward (into the square) for a pocket or cavity rim."""
    s = half - rad
    pts = []
    segments = [
        ("line", (0.0, -half), (s, -half), (0, -1)),
        ("arc", (s, -s), -90.0, 0.0),
        ("line", (half, -s), (half, s), (1, 0)),
        ("arc", (s, s), 0.0, 90.0),
        ("line", (s, half), (-s, half), (0, 1)),
        ("arc", (-s, s), 90.0, 180.0),
        ("line", (-half, s), (-half, -s), (-1, 0)),
        ("arc", (-s, -s), 180.0, 270.0),
        ("line", (-s, -half), (0.0, -half), (0, -1)),
    ]
    sign = -1.0 if inward else 1.0
    for seg in segments:
        if seg[0] == "line":
            (x0, y0), (x1, y1), (nx, ny) = seg[1], seg[2], seg[3]
            n = max(1, math.ceil(math.dist((x0, y0), (x1, y1)) / step))
            for i in range(n):
                t = i / n
                pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, sign * nx, sign * ny))
        else:
            (cx, cy), a0, a1 = seg[1], seg[2], seg[3]
            n = max(1, math.ceil(math.radians(a1 - a0) * rad / step))
            for i in range(n):
                a = math.radians(a0 + (a1 - a0) * i / n)
                pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a), sign * math.cos(a), sign * math.sin(a)))
    pts.append(pts[0])
    return pts


def _rect_edge(xh: float, yh: float, step: float, corner_steps: int = 18):
    """The outline's edge, anticlockwise from the foot's middle, every
    ``step``; at each sharp corner the normal swings round the corner point
    (the apex circles it)."""
    corners = [(xh, -yh), (xh, yh), (-xh, yh), (-xh, -yh)]
    pts = []
    sides = [((0.0, -yh), (xh, -yh), (0, -1)), ((xh, -yh), (xh, yh), (1, 0)), ((xh, yh), (-xh, yh), (0, 1)), ((-xh, yh), (-xh, -yh), (-1, 0)), ((-xh, -yh), (0.0, -yh), (0, -1))]
    for index, ((x0, y0), (x1, y1), (nx, ny)) in enumerate(sides):
        n = max(1, math.ceil(math.dist((x0, y0), (x1, y1)) / step))
        for i in range(n):
            t = i / n
            pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, nx, ny))
        if index < 4:
            cx, cy = corners[index]
            a0 = math.atan2(ny, nx)
            for j in range(corner_steps + 1):
                a = a0 + math.pi / 2 * j / corner_steps
                pts.append((cx, cy, math.cos(a), math.sin(a)))
    pts.append(pts[0])
    return pts


def context(features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str) -> dict[str, Any]:
    import numpy as np

    g = _geometry(features)
    p = plan["parameters"]
    xe, yt, web, k = g["xe"], g["yt"], g["web"], g["k"]

    # The blank: the bar's thickness band (calipers), its width band and the
    # sawn length's band; the programs are posted for the largest.
    t_max = p["bar_thickness_max_mm"]
    top = t_max / 2
    _agree(plan, "stock_top_mm", top)
    xs = p["blank_length_max_mm"] / 2
    ys = p["bar_width_max_mm"] / 2
    if p["bar_thickness_min_mm"] / 2 <= g["zf"]:
        raise ValueError("the thinnest bar does not clean up the foot's slant edge")
    if p["blank_length_min_mm"] / 2 <= xe or p["bar_width_min_mm"] / 2 <= yt:
        raise ValueError("the smallest blank does not hold the part")

    em = _shop_tool(plan, shop, "em-3-8")
    d = em["diameter_mm"]
    r = d / 2
    _agree(plan, "em_dia_mm", d)
    loc = em["flute_length_mm"]
    rpm_em, feed_em = _setting(plan, shop, "rough levels")
    plunge_em = feed_em * p["plunge_feed_fraction"]
    _agree(plan, "em_plunge_feed_mm", plunge_em)
    for name in ("floor finish", "pocket walls", "outline finish", "slant finish", "cavity rough", "cavity finish"):
        if _setting(plan, shop, name) != (rpm_em, feed_em):
            raise ValueError(f"'{name}' runs at another setting than 'rough levels'")
    a = p["finish_stock_mm"]
    boss = p["boss_half_mm"]
    bottom = -p["outline_past_mm"]
    step_r, level_max = p["rough_stepover_mm"], p["rough_level_max_mm"]
    step_s, step_f = p["slant_stepover_mm"], p["floor_stepover_mm"]
    for name, key, value in (
        ("rough levels", "radial_woc_mm", d),
        ("rough levels", "axial_doc_mm", level_max),
        ("floor finish", "radial_woc_mm", step_f),
        ("floor finish", "axial_doc_mm", a),
        ("pocket walls", "radial_woc_mm", a),
        ("outline finish", "radial_woc_mm", a),
        ("slant finish", "radial_woc_mm", step_s),
    ):
        if not math.isclose(_cut(plan, name, key), value, abs_tol=PLAN_TOL_MM):
            raise ValueError(f"'{name}' {key} is not {value:.4f}")
    # The deepest walls the end mill cuts in one pass: the outline from the
    # foot's slant edge to past the mid-plane, the pocket wall from the foot
    # rim to the web; both inside its flutes.
    outline_depth = g["zf"] - bottom
    wall_depth = g["zf"] - g["k"] * (-g["pocket"] - g["yf"]) - web
    _agree(plan, "outline_depth_mm", outline_depth)
    _agree(plan, "pocket_wall_depth_mm", wall_depth)
    for name, depth in (("outline finish", outline_depth), ("pocket walls", wall_depth)):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), depth, abs_tol=PLAN_TOL_MM):
            raise ValueError(f"'{name}' axial_doc_mm is not {depth:.4f}")
    if top - bottom > loc:
        raise ValueError(f"the levels reach {top - bottom:.2f} below the top, past the flutes' {loc}")
    # The boss: inside the cavity by the end mill's diameter and a margin,
    # so FR08's slot at the cavity wall never meets it; the studs' nuts on it.
    cav = g["cavity"]
    if boss > cav - d - p["boss_margin_mm"] + 1e-9:
        raise ValueError(f"the boss {boss} reaches within the cavity slot's {cav - d}")
    stud_x = p["stud_x_mm"]
    if stud_x + NUT_RADIUS_MM > boss:
        raise ValueError("a stud's flange nut overhangs the boss")
    if p["floor_corner_max_mm"] != g["floor_corner_max"]:
        raise ValueError("process.floor_corner_max_mm is not the export's")

    clear = top + CLEAR_MM
    levels = _levels(top, bottom, level_max)
    _agree(plan, "rough_level_mm", top - levels[0])
    floor_rough = web + a

    # Rough raster along X (the slant is level along X), stations across Y
    # from beside the bar's -Y edge to beside its +Y edge, equal steps.
    def stations(lo: float, hi: float, step: float) -> list[float]:
        n = math.ceil((hi - lo) / step - 1e-9)
        return [lo + (hi - lo) * i / n for i in range(n + 1)]

    rough_ys = stations(-(ys + r - step_r), ys + r - step_r, step_r)
    _agree(plan, "rough_station_mm", rough_ys[1] - rough_ys[0])
    x_run = (-(xs + r + APPROACH_MM), xs + r + APPROACH_MM)
    rough_field = _Field(np, g, wall=a, slant=a, floor=floor_rough, bottom=bottom, boss=boss, radius=r)
    rough_passes = [("x", y, x_run if i % 2 == 0 else x_run[::-1]) for i, y in enumerate(rough_ys)]
    rough_link = 1.5 * (rough_ys[1] - rough_ys[0])
    rough, rough_entries = _raster(rough_field, rough_passes, levels, top, top, clear, rough_link)

    # Floor finish: the web, the walls' allowance kept, passes along X.
    floor_field = _Field(np, g, wall=a, slant=a, floor=web, bottom=bottom, boss=boss, radius=r)
    fy = g["pocket"] - a - r
    floor_ys = stations(-fy, fy, step_f)
    floor_passes = [("x", y, (-fy, fy) if i % 2 == 0 else (fy, -fy)) for i, y in enumerate(floor_ys)]
    floor_link = 1.5 * (floor_ys[1] - floor_ys[0])
    floor_lines, _ = _raster(floor_field, floor_passes, [web], floor_rough, top, clear, floor_link)

    # Pocket walls: one climb loop (anticlockwise inside) at the web, the
    # whole wall in one pass. Entered and left square to the wall at the -Y
    # side's middle from wall_lead, a finish allowance in from the loop: the
    # cutter there stands in the cleared ring, clear of the allowance, so it
    # plunges and lifts in air (at the plunge feed down).
    wall_seq, wall_part = _rrect_loop(g["pocket"], g["pocket_r"], r, outside=False, clockwise=False)
    wall_start = wall_seq[0][1]
    wall_lead = (wall_start[0], wall_start[1] + a)
    walls = [
        f"G0 Z{_r(clear):.3f}",
        f"G0 X{_r(wall_lead[0]):.3f} Y{_r(wall_lead[1]):.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
        f"G1 Z{_r(web):.3f} F{{plunge}}",
        f"G1 X{_r(wall_start[0]):.3f} Y{_r(wall_start[1]):.3f} F{{feed}}",
        *_loop_gcode(wall_seq, web, clockwise=False),
        f"G1 X{_r(wall_lead[0]):.3f} Y{_r(wall_lead[1]):.3f} F{{feed}}",
        f"G1 Z{_r(top + SAFE_MM):.3f} F{{feed}}",
        f"G0 Z{_r(clear):.3f}",
    ]

    # Outline: one climb loop (clockwise outside) at the outline's bottom, the
    # whole wall in one pass, entered and left the same way outside the
    # foot's middle, in the margin the rough cleared.
    out_seq, out_part = _rect_loop(xe, yt, r)
    out_start = out_seq[0][1]
    out_lead = (out_start[0], out_start[1] - a)
    outline = [
        f"G0 Z{_r(clear):.3f}",
        f"G0 X{_r(out_lead[0]):.3f} Y{_r(out_lead[1]):.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
        f"G1 Z{_r(bottom):.3f} F{{plunge}}",
        f"G1 X{_r(out_start[0]):.3f} Y{_r(out_start[1]):.3f} F{{feed}}",
        *_loop_gcode(out_seq, bottom, clockwise=True),
        f"G1 X{_r(out_lead[0]):.3f} Y{_r(out_lead[1]):.3f} F{{feed}}",
        f"G1 Z{_r(top + SAFE_MM):.3f} F{{feed}}",
        f"G0 Z{_r(clear):.3f}",
    ]

    # Slant finish: passes along Y (the slant falls along Y, so the cutter's
    # trailing edge sweeps it), stations along X; the walls already final.
    slant_field = _Field(np, g, wall=0.0, slant=0.0, floor=web, bottom=bottom, boss=boss, radius=r)
    slant_xs = stations(-xe, xe, step_s)
    _agree(plan, "slant_station_mm", slant_xs[1] - slant_xs[0])
    y_out = yt + r + APPROACH_MM
    inner = g["pocket"] - r
    slant_passes = []
    for i, x in enumerate(slant_xs):
        spans = [(-y_out, y_out)] if abs(x) >= inner else [(-y_out, -inner), (inner, y_out)]
        slant_passes += [("y", x, span if i % 2 == 0 else span[::-1]) for span in spans]
    # Only where the cutter meets the rim, on the field itself: the walls
    # are final and the floor below, so a pass ends where it leaves the rim.
    slant, _ = _raster(slant_field, slant_passes, [-math.inf], top, top, clear, 1.5 * step_s, rim_only=True)
    slant_low = min(float(m.group(1)) for line in slant if (m := re.search(r" Z(-?[\d.]+) F", line)))
    if not g["zt"] - 1e-3 <= slant_low <= g["zt"] + 0.1:
        raise ValueError(f"the slant finish reaches Z{slant_low}, not the top edge's {g['zt']:.3f}")

    # Chamfers (T5): apex nodes round the outline (clockwise), the pocket rim
    # and the cavity groove (anticlockwise); each loop entered from above in
    # the air beside its edge (the groove ramps in along its path).
    cm = _shop_tool(plan, shop, "chamfer")
    cm_r = cm["diameter_mm"] / 2
    e = p["chamfer_clear_mm"]
    c = g["chamfer"]
    band = g["chamfer_band"]
    legs = {}
    for name, slope in (("square", 0.0), ("foot", -k), ("top", k)):
        legs[name] = _chamfer_depth(c, slope)
        for leg in legs[name]:
            if not band[0] <= leg <= band[1]:
                raise ValueError(f"the {name} edge's chamfer leg {leg:.3f} is outside {band}")
    deepest_cone = max(w for w, _ in legs.values()) + e
    if deepest_cone > cm["flute_length_mm"]:
        raise ValueError("the chamfer cone runs past the mill's cutting length")
    _agree(plan, "chamfer_foot_wall_mm", legs["foot"][0])
    _agree(plan, "chamfer_top_wall_mm", legs["top"][0])

    def slant_z(y: float) -> float:
        return g["zf"] - k * (y - g["yf"])

    outer = _rect_edge(xe, yt, 1.0)[::-1]
    outer_nodes = _chamfer_path(outer, [slant_z(pt[1]) for pt in outer], [k * pt[3] for pt in outer], c, e)
    pocket_edge = _rrect_edge(g["pocket"], g["pocket_r"], inward=True, step=1.0)
    # Into the material is against the normal (which points into the
    # pocket): the slope there is -k times the material direction's Y.
    pocket_nodes = _chamfer_path(
        pocket_edge, [slant_z(pt[1]) for pt in pocket_edge], [k * pt[3] for pt in pocket_edge], c, e
    )
    cavity_edge = _rrect_edge(cav, g["cavity_r"], inward=True, step=1.0)
    cavity_nodes = _chamfer_path(cavity_edge, [web] * len(cavity_edge), [0.0] * len(cavity_edge), c, e)

    def loop(nodes, ramp_mm: float = 0.0) -> list[str]:
        start = nodes[0]
        out = [
            f"G0 Z{_r(clear):.3f}",
            f"G0 X{_r(start[0]):.3f} Y{_r(start[1]):.3f}",
            f"G0 Z{_r(top + SAFE_MM):.3f}",
        ]
        if ramp_mm <= 0:
            out.append(f"G1 Z{_r(start[2]):.3f} F{{plunge}}")
            for n in nodes[1:]:
                out.append(f"G1 X{_r(n[0]):.3f} Y{_r(n[1]):.3f} Z{_r(n[2]):.3f} F{{feed}}")
        else:
            # Down to the web, then along the path sinking to depth over
            # ramp_mm; round once more past the ramp.
            surface = web
            out.append(f"G1 Z{_r(surface):.3f} F{{feed}}")
            run = 0.0
            prev = nodes[0]
            ramped = []
            for n in nodes[1:]:
                run += math.dist(prev[:2], n[:2])
                t = min(1.0, run / ramp_mm)
                ramped.append((n[0], n[1], surface + (n[2] - surface) * t))
                prev = n
            for n in ramped:
                out.append(f"G1 X{_r(n[0]):.3f} Y{_r(n[1]):.3f} Z{_r(n[2]):.3f} F{{plunge}}" if n[2] > nodes[0][2] + 1e-6 else f"G1 X{_r(n[0]):.3f} Y{_r(n[1]):.3f} Z{_r(n[2]):.3f} F{{feed}}")
            run = 0.0
            prev = nodes[0]
            for n in nodes[1:]:
                out.append(f"G1 X{_r(n[0]):.3f} Y{_r(n[1]):.3f} Z{_r(n[2]):.3f} F{{feed}}")
                run += math.dist(prev[:2], n[:2])
                prev = n
                if run > ramp_mm + 1.0:
                    break
        out += [f"G1 Z{_r(top + SAFE_MM):.3f} F{{feed}}", f"G0 Z{_r(clear):.3f}"]
        return out

    # Side A's cavity rim: a groove along the cavity line on the web (FR08
    # cuts the cavity out inside it). Side B's: its real edge, cut in FR08
    # after the cavity, the boss and the studs out.
    chamfers = {
        "a": loop(outer_nodes) + loop(pocket_nodes) + loop(cavity_nodes, ramp_mm=p["groove_ramp_mm"]),
        "b": loop(outer_nodes) + loop(pocket_nodes),
    }
    chamfer_low = {
        "a": min(n[2] for n in (*outer_nodes, *pocket_nodes, *cavity_nodes)),
        "b": min(n[2] for n in (*outer_nodes, *pocket_nodes)),
    }
    cavity_chamfer = loop(cavity_nodes)
    cavity_chamfer_low = min(n[2] for n in cavity_nodes)
    rpm_cm, feed_cm = _setting(plan, shop, "chamfers")
    plunge_cm = feed_cm * p["plunge_feed_fraction"]

    # --- FR01: stud holes ------------------------------------------------------
    d1332 = _shop_tool(plan, shop, "drill-13-32")["diameter_mm"]
    spot_dia = p["spot_dia_mm"]
    spot_z = top - _spot_depth(spot_dia)
    if spot_dia >= d1332:
        raise ValueError("the stud spot would chamfer its hole")
    studs = [(-stud_x, 0.0), (stud_x, 0.0)]
    stud_tip = -top - p["drill_past_mm"] - _point(d1332)
    _agree(plan, "stud_tip_mm", stud_tip)
    rpm_sp, feed_sp = _setting(plan, shop, "stud spots")
    rpm_13, feed_13 = _setting(plan, shop, "stud holes")
    peck_13 = p["stud_peck_mm"]
    op13 = _op_with_cut(plan, "stud holes")[0]
    if op13.get("peck") != {"step_mm": "{{process.stud_peck_mm}}", "retract": "full"}:
        raise ValueError("'stud holes' peck is not process.stud_peck_mm with full retract")
    # The holes clear the centre blocks under the slab.
    if p["block_inner_y_mm"] <= d1332 / 2:
        raise ValueError("a stud hole meets a centre block")
    stud_spot_lines = [line for xy in studs for line in _spot(xy, top, spot_z, clear)]
    stud_drill_lines = [line for xy in studs for line in _pecked(xy, top, stud_tip, peck_13, clear)]

    # Counterbores for the flange nuts in side A's boss, so side A's nuts and
    # stud ends sit below the top: T1 drops into each drilled hole and
    # circles out (climb), level by level. The boss is waste: FR08 frees it
    # and it comes out at FR08's M6 T5 stop.
    cb_r = p["stud_cbore_dia_mm"] / 2
    cb_floor = top - p["stud_cbore_depth_mm"]
    if d >= d1332:
        raise ValueError("the end mill does not drop into a stud hole")
    if cb_r < NUT_RADIUS_MM:
        raise ValueError("a counterbore does not take its flange nut")
    for x, y in studs:
        if max(abs(x), abs(y)) + cb_r > boss - 1e-9:
            raise ValueError(f"the counterbore at X{x:g} reaches past the boss into the part")
    cb_rings = math.ceil((cb_r - r) / (d / 3) - 1e-9)
    cbore_lines = []
    for x, y in studs:
        cbore_lines += [f"G0 Z{_r(clear):.3f}", f"G0 X{_r(x):.3f} Y{_r(y):.3f}", f"G0 Z{_r(top + SAFE_MM):.3f}"]
        for z in _levels(top, cb_floor, p["rough_level_max_mm"]):
            cbore_lines.append(f"G1 Z{_r(z):.3f} F{{plunge}}")
            for i in range(1, cb_rings + 1):
                rho = (cb_r - r) * i / cb_rings
                cbore_lines += [
                    f"G1 X{_r(x + rho):.3f} Y{_r(y):.3f} F{{feed}}",
                    f"G3 X{_r(x + rho):.3f} Y{_r(y):.3f} I{_r(-rho):.3f} J0.000 F{{feed}}",
                ]
            cbore_lines.append(f"G1 X{_r(x):.3f} Y{_r(y):.3f} F{{feed}}")
        cbore_lines.append(f"G1 Z{_r(top + SAFE_MM):.3f} F{{feed}}")
    cbore_lines.append(f"G0 Z{_r(clear):.3f}")

    # --- FR08: the cavity through the web (side B up) --------------------------
    cav_levels = _levels(web, -web - p["cavity_past_mm"], p["cavity_level_mm"])
    _agree(plan, "cavity_depth_mm", 2 * web + p["cavity_past_mm"])
    if not math.isclose(_cut(plan, "cavity rough", "axial_doc_mm"), web - cav_levels[0], abs_tol=PLAN_TOL_MM):
        raise ValueError("'cavity rough' axial_doc_mm is not the cavity's level")
    cav_rough_seq, cav_part = _rrect_loop(cav, g["cavity_r"], r + a, outside=False, clockwise=False)
    cav_fin_seq, _ = _rrect_loop(cav, g["cavity_r"], r, outside=False, clockwise=False)
    cstart = cav_rough_seq[0][1]
    cavity_lines = [
        f"G0 Z{_r(clear):.3f}",
        f"G0 X{_r(cstart[0]):.3f} Y{_r(cstart[1]):.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
        f"G1 Z{_r(web + SAFE_MM):.3f} F{{feed}}",
    ]
    for z in cav_levels:
        cavity_lines.append(f"G1 Z{_r(z):.3f} F{{plunge}}")
        cavity_lines += _loop_gcode(cav_rough_seq, z, clockwise=False)
    # The finish loop follows the last level without lifting: from the rough
    # loop's start (in the slot just cut) square out to the wall, round, and
    # back, then up the cleared slot.
    fstart = cav_fin_seq[0][1]
    cavity_lines += [
        f"G1 X{_r(fstart[0]):.3f} Y{_r(fstart[1]):.3f} F{{feed}}",
        *_loop_gcode(cav_fin_seq, cav_levels[-1], clockwise=False),
        f"G1 X{_r(cstart[0]):.3f} Y{_r(cstart[1]):.3f} F{{feed}}",
        f"G1 Z{_r(top + SAFE_MM):.3f} F{{feed}}",
        f"G0 Z{_r(clear):.3f}",
    ]

    # --- FR09: foot holes (standing, foot up) ----------------------------------
    d516 = _shop_tool(plan, shop, "drill-5-16")["diameter_mm"]
    for x, z, nominal, band_dia in g["holes"]:
        if not band_dia[0] - 0.001 <= d516 <= band_dia[1] + 0.001:
            raise ValueError(f"5/16 Ø{d516} is outside the foot hole's band {band_dia}")
    foot = g["foot_thickness"]
    foot_tip = -(foot + p["drill_past_mm"] + _point(d516))
    _agree(plan, "foot_tip_mm", foot_tip)
    # The traveler's console ream (a tight GO pin) types these.
    _agree(plan, "foot_hole_x_mm", max(abs(x) for x, _z, _n, _b in g["holes"]))
    _agree(plan, "foot_hole_y_mm", max(abs(z) for _x, z, _n, _b in g["holes"]))
    _agree(plan, "foot_clear_mm", SAFE_MM + CLEAR_MM)
    foot_spot_z = -_spot_depth(spot_dia)
    foot_xy = [(x, z) for x, z, _n, _b in g["holes"]]
    for x, z in foot_xy:
        if abs(z) - d516 / 2 <= web:
            raise ValueError("a foot hole's drill meets the web below the foot")
    rpm_fd, feed_fd = _setting(plan, shop, "foot holes")
    foot_clear = SAFE_MM + CLEAR_MM
    foot_spot_lines = [line for xy in foot_xy for line in _spot(xy, 0.0, foot_spot_z, foot_clear)]
    foot_drill_lines = [line for xy in foot_xy for line in _pecked(xy, 0.0, foot_tip, None, foot_clear)]

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {tool["id"]: n for n, tool in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)}
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    frames = {
        "a": _frame([0.0, 0.0, 0.0], [0, 1, 0], [0, 0, 1]),
        "b": _frame([0.0, 0.0, 0.0], [0, 1, 0], [0, 0, -1]),
        "foot": _frame([0.0, g["yf"], 0.0], [0, 0, 1], [0, -1, 0]),
    }
    slab = [[-xs, xs], [-ys, ys], [-top, top]]
    stocks = {
        "a": slab,
        "b": slab,
        "foot": [[-xe, xe], [-g["zf"], g["zf"]], [-2 * yt, 0.0]],
    }
    for key, frame in frames.items():
        (x0, x1), (y0, y1), (z0, z1) = stocks[key]
        for corner in ([-xe, g["yf"], -g["zf"]], [xe, yt, g["zf"]]):
            x, y, z = _to(frame, corner)
            if not (x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6 and z0 - 1e-6 <= z <= z1 + 1e-6):
                raise ValueError(f"{key}: the part is not inside its stock")

    def tool(tool_id: str, dia: float, shape: str, rpm: float, feed: float, plunge: float, **extra) -> dict[str, Any]:
        return {"tool": tool_id, "dia": dia, "shape": shape, "rpm": rpm, "feed": feed, "plunge": plunge, **extra}

    em_tool = tool("em-3-8", d, "endmill", rpm_em, feed_em, plunge_em, flutes=3)
    # FreeCAD's chamfer bit takes its angle as its own shape's; no TipAngle.
    cm_tool = tool("chamfer", cm["diameter_mm"], "chamfer", rpm_cm, feed_cm, plunge_cm, flutes=2)
    spot_tool = tool("spot", CENTRE_DRILL["body_mm"], "drill", rpm_sp, feed_sp, feed_sp, tip_angle=CENTRE_DRILL["point_deg"])
    jobs = [
        {**spot_tool, "label": "FR01 spot", "frame": "a", "stock": stocks["a"], "ops": [["stud_spot", "spot stud holes", stud_spot_lines]]},
        {
            **tool("drill-13-32", d1332, "drill", rpm_13, feed_13, feed_13, tip_angle=DRILL_POINT_DEG),
            "label": "FR01 drill",
            "frame": "a",
            "stock": stocks["a"],
            "ops": [["stud_drill", "drill stud holes", stud_drill_lines]],
        },
        {**em_tool, "label": "FR01 counterbores", "frame": "a", "stock": stocks["a"], "ops": [["stud_cbore", "counterbore stud holes", cbore_lines]]},
    ]
    # "studs": the side whose nuts and studs stand while the section runs.
    for side in ("a", "b"):
        for key, label, lines in (
            ("rough", "rough levels", rough),
            ("floor", "floor finish", floor_lines),
            ("walls", "pocket walls", walls),
            ("outline", "outline finish", outline),
            ("slant", "slant finish", slant),
        ):
            jobs.append({**em_tool, "label": f"{side} {label}", "frame": side, "stock": stocks[side], "studs": side, "ops": [[f"{side}_{key}", label, lines]]})
        jobs.append({**cm_tool, "label": f"{side} chamfers", "frame": side, "stock": stocks[side], "studs": side, "ops": [[f"{side}_chamfer", "chamfers", chamfers[side]]]})
    jobs.append({**em_tool, "label": "cavity", "frame": "b", "stock": stocks["b"], "studs": "b", "ops": [["cavity", "cavity", cavity_lines]]})
    jobs.append({**cm_tool, "label": "cavity rim", "frame": "b", "stock": stocks["b"], "ops": [["b_cavity_chamfer", "cavity rim chamfer", cavity_chamfer]]})
    jobs += [
        {**spot_tool, "label": "FR09 spot", "frame": "foot", "stock": stocks["foot"], "ops": [["foot_spot", "spot foot holes", foot_spot_lines]]},
        {
            **tool("drill-5-16", d516, "drill", rpm_fd, feed_fd, feed_fd, tip_angle=DRILL_POINT_DEG),
            "label": "FR09 drill",
            "frame": "foot",
            "stock": stocks["foot"],
            "ops": [["foot_drill", "drill foot holes", foot_drill_lines]],
        },
    ]

    # --- Checks ------------------------------------------------------------------
    # Each side's nuts sit on their seat: side A's on its counterbores'
    # floors, side B's on the boss's uncut face; each stud's end at most
    # stud_above_seat_mm above it.
    seats = {"a": cb_floor, "b": top}
    stud_end = {side: seat + p["stud_above_seat_mm"] for side, seat in seats.items()}
    nuts = {
        side: [{"name": f"stud at X{x:g}", "centre": [x, y], "radius": NUT_RADIUS_MM, "z_top": stud_end[side]} for x, y in studs]
        for side in seats
    }
    # The spindle nose over the studs, in every section cut with the studs
    # in, every tool: each move whose path passes within the nose's radius of
    # a nut keeps the nose's face clear above the stud's end.
    nose_reach = p["spindle_nose_dia_max_mm"] / 2 + NUT_RADIUS_MM
    # Both tools in the R8 collet: the face is the tip plus the collet's
    # gauge and the tool's projection.
    face_of = {
        "em-3-8": p["r8_collet_gauge_mm"] + p["em_projection_mm"],
        "chamfer": p["r8_collet_gauge_mm"] + p["chamfer_projection_mm"],
    }
    for job in jobs:
        side = job.get("studs")
        if side is None:
            continue
        if job["tool"] not in face_of:
            raise ValueError(f"{job['label']}: no holder face for {job['tool']} over the studs")
        face = face_of[job["tool"]]
        for key, _label, lines in job["ops"]:
            pos = [0.0, 0.0, clear]
            for line in lines:
                words = {w[0]: float(w[1:]) for w in line.split() if w[0] in "XYZ"}
                if not words:
                    continue
                end = [words.get(axis, pos[i]) for i, axis in enumerate("XYZ")]
                for sx, sy in studs:
                    low = min(pos[2], end[2])
                    if _segment_distance(pos[:2], end[:2], (sx, sy)) < nose_reach and low + face < stud_end[side] + NOSE_CLEAR_MM:
                        raise ValueError(
                            f"{key}: the spindle nose comes within {NOSE_CLEAR_MM} of the stud at X{sx:g} "
                            f"(tip Z{low:.3f}); lower process.stud_above_seat_mm"
                        )
                pos = end
    # A strap's lane runs out to its stud and heel, past the table's reach.
    far = 1000.0
    end_straps = [
        _box("west strap", (-far, -p["slab_strap_x_mm"] + STRAP_NOSE_MM), (-STRAP_HALF_WIDTH_MM, STRAP_HALF_WIDTH_MM), top + STRAP_HEIGHT_MM),
        _box("east strap", (p["slab_strap_x_mm"] - STRAP_NOSE_MM, far), (-STRAP_HALF_WIDTH_MM, STRAP_HALF_WIDTH_MM), top + STRAP_HEIGHT_MM),
    ]
    post_top = slant_z(0.0)
    frame_straps = [
        _box("west post strap", (-far, -p["post_strap_x_mm"] + STRAP_NOSE_MM), (-STRAP_HALF_WIDTH_MM, STRAP_HALF_WIDTH_MM), post_top + STRAP_HEIGHT_MM),
        _box("east post strap", (p["post_strap_x_mm"] - STRAP_NOSE_MM, far), (-STRAP_HALF_WIDTH_MM, STRAP_HALF_WIDTH_MM), post_top + STRAP_HEIGHT_MM),
    ]
    toe = p["foot_strap_toe_mm"]
    foot_straps = [
        _box("west strap, from -Y", (-p["foot_strap_x_mm"] - STRAP_HALF_WIDTH_MM, -p["foot_strap_x_mm"] + STRAP_HALF_WIDTH_MM), (-far, -toe + STRAP_NOSE_MM), STRAP_HEIGHT_MM),
        _box("east strap, from +Y", (p["foot_strap_x_mm"] - STRAP_HALF_WIDTH_MM, p["foot_strap_x_mm"] + STRAP_HALF_WIDTH_MM), (toe - STRAP_NOSE_MM, far), STRAP_HEIGHT_MM),
    ]
    ring_points = [
        [_r(x), _r(y)]
        for x in np.arange(-g["pocket"] + a + 1.0, g["pocket"] - a - 1.0 + 1e-9, 5.0)
        for y in np.arange(-g["pocket"] + a + 1.0, g["pocket"] - a - 1.0 + 1e-9, 5.0)
        # Between the boss and the cavity line is waste FR08 cuts out.
        if max(abs(x), abs(y)) > cav - 1.0
        and bool(_rrect_inside(np, np.array([x]), np.array([y]), g["pocket"] - a - 1.0, g["pocket_r"] - a - 1.0)[0])
    ]
    expect: list[list[Any]] = []
    fr01, a_mill, a_walls, a_outline, b_mill, b_walls, b_outline, fr_cavity, fr_foot = (name for name, _ops in PROGRAMS)

    def hole_checks(centres, bottom_z, radius, z_top, boxes):
        return [
            ["holes", {"centres": [list(c) for c in centres], "z_bottom": _r(bottom_z)}],
            ["rapids_clear", {"z_top": z_top, "open_holes": [list(c) for c in centres]}],
            ["vertical_below_top", {"z_top": z_top}],
            ["air_feed", {"z_top": z_top}],
            ["keep_out", {"radius": radius, "boxes": boxes}],
        ]

    for k_, checks in enumerate(
        (
            hole_checks(studs, spot_z, CENTRE_DRILL["body_mm"] / 2, top, end_straps),
            hole_checks(studs, stud_tip, d1332 / 2, top, end_straps),
        )
    ):
        expect += [[f"{fr01}@{k_}", check, kwargs] for check, kwargs in checks]
    expect += [
        [fr01, "tool_changes", {"z_top": top, "tools": [numbers["spot"], numbers["drill-13-32"], numbers["em-3-8"]], "loads_first": True}],
        [fr01, "spindle", {"rpm": [[rpm_sp], [rpm_13], [rpm_em]]}],
        [fr01, "pauses", {"z_top": top, "count": 0}],
        [fr01, "depth", {"z_min": _r(stud_tip)}],
        [f"{fr01}@2", "depth", {"z_min": _r(cb_floor)}],
        [f"{fr01}@2", "rapids_clear", {"z_top": top}],
        [f"{fr01}@2", "feed_out", {"z_top": top}],
        [f"{fr01}@2", "air_feed", {"z_top": top}],
        [f"{fr01}@2", "keep_out", {"radius": r, "boxes": end_straps}],
    ]


    def side_checks(side: str, mill: str, walls_name: str, outline_name: str) -> None:
        common = [
            ["rapids_clear", {"z_top": top}],
            ["feed_out", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": r, "circles": nuts[side]}],
        ]
        expect.extend(
            [
                [mill, "tool_changes", {"z_top": top, "tools": [numbers["em-3-8"]], "loads_first": True}],
                [mill, "spindle", {"rpm": rpm_em}],
                [mill, "pauses", {"z_top": top, "count": 0}],
                [mill, "depth", {"z_min": _r(bottom)}],
                *([mill, check, kwargs] for check, kwargs in common),
                [mill, "cleared", {"points": ring_points, "radius": r, "z": _r(web)}],
                [walls_name, "tool_changes", {"z_top": top, "tools": [numbers["em-3-8"]], "loads_first": True}],
                [walls_name, "spindle", {"rpm": rpm_em}],
                [walls_name, "depth", {"z_min": _r(web)}],
                *([walls_name, check, kwargs] for check, kwargs in common),
                [
                    walls_name,
                    "outline",
                    {
                        "elements": _elements(wall_part, OUTLINE_TOL_MM),
                        "passes": [{"offset": r, "levels": [_r(web)]}],
                        "leads": [{"centre": [_r(wall_lead[0]), _r(wall_lead[1])], "radius": a + OUTLINE_TOL_MM, "levels": [_r(web)]}],
                        "z_top": top,
                    },
                ],
                [outline_name, "tool_changes", {"z_top": top, "tools": [numbers["em-3-8"], numbers["chamfer"]], "loads_first": True}],
                [outline_name, "spindle", {"rpm": [[rpm_em], [rpm_cm]]}],
                [outline_name, "pauses", {"z_top": top, "count": 0}],
                [outline_name, "depth", {"z_min": _r(bottom)}],
                *([f"{outline_name}@0", check, kwargs] for check, kwargs in common),
                [
                    f"{outline_name}@0",
                    "outline",
                    {
                        "elements": out_part,
                        "passes": [{"offset": r, "levels": [_r(bottom)]}],
                        "leads": [{"centre": [_r(out_lead[0]), _r(out_lead[1])], "radius": a + OUTLINE_TOL_MM, "levels": [_r(bottom)]}],
                        "z_top": top,
                    },
                ],
                [f"{outline_name}@1", "depth", {"z_min": _r(chamfer_low[side])}],
                [f"{outline_name}@1", "rapids_clear", {"z_top": top}],
                [f"{outline_name}@1", "feed_out", {"z_top": top}],
                [f"{outline_name}@1", "air_feed", {"z_top": top}],
                [f"{outline_name}@1", "keep_out", {"radius": cm_r, "circles": nuts[side]}],
            ]
        )
    # The slant finish's lowest point is the top edge's (checked above): the
    # mill program's depth is the outline's bottom, the levels' last.

    side_checks("a", a_mill, a_walls, a_outline)
    side_checks("b", b_mill, b_walls, b_outline)
    expect += [
        [fr_cavity, "tool_changes", {"z_top": top, "tools": [numbers["em-3-8"], numbers["chamfer"]], "loads_first": True}],
        [fr_cavity, "spindle", {"rpm": [[rpm_em], [rpm_cm]]}],
        [fr_cavity, "depth", {"z_min": _r(min(cav_levels[-1], cavity_chamfer_low))}],
        [f"{fr_cavity}@0", "rapids_clear", {"z_top": top}],
        [f"{fr_cavity}@0", "feed_out", {"z_top": top}],
        [f"{fr_cavity}@0", "air_feed", {"z_top": top}],
        [f"{fr_cavity}@0", "keep_out", {"radius": r, "boxes": frame_straps, "circles": nuts["b"]}],
        # The boss and the studs are out: the rim chamfer misses the straps.
        [f"{fr_cavity}@1", "depth", {"z_min": _r(cavity_chamfer_low)}],
        [f"{fr_cavity}@1", "rapids_clear", {"z_top": top}],
        [f"{fr_cavity}@1", "feed_out", {"z_top": top}],
        [f"{fr_cavity}@1", "air_feed", {"z_top": top}],
        [f"{fr_cavity}@1", "keep_out", {"radius": cm_r, "boxes": frame_straps}],
        [
            f"{fr_cavity}@0",
            "outline",
            {
                "elements": _elements(cav_part, OUTLINE_TOL_MM),
                # The slot levels clear inside the finish pass (as
                # ch_connecting_rod's bore); the finish loop's step out from
                # the last level's slot and back to it run inside that slot.
                "passes": [{"offset": r, "levels": [_r(cav_levels[-1])]}],
                "clearing": [{"x": [_r(-cav), _r(cav)], "levels": [_r(z) for z in cav_levels]}],
                "leads": [{"centre": [_r(cstart[0]), _r(cstart[1])], "radius": a + OUTLINE_TOL_MM, "levels": [_r(cav_levels[-1])]}],
                "z_top": web,
            },
        ],
    ]
    for k_, checks in enumerate(
        (
            hole_checks(foot_xy, foot_spot_z, CENTRE_DRILL["body_mm"] / 2, 0.0, foot_straps),
            hole_checks(foot_xy, foot_tip, d516 / 2, 0.0, foot_straps),
        )
    ):
        expect += [[f"{fr_foot}@{k_}", check, kwargs] for check, kwargs in checks]
    expect += [
        [fr_foot, "tool_changes", {"z_top": 0.0, "tools": [numbers["spot"], numbers["drill-5-16"]], "loads_first": True}],
        [fr_foot, "spindle", {"rpm": [[rpm_sp], [rpm_fd]]}],
        [fr_foot, "pauses", {"z_top": 0.0, "count": 0}],
        [fr_foot, "depth", {"z_min": _r(foot_tip)}],
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
        "rough_entries": rough_entries,
    }


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    return [(program, check, kwargs) for program, check, kwargs in ctx["expect"]]


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job per
    section; returns {"ops": {operation key: operation}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(doc, f"Support {key}", ctx["step"], frame["origin"], frame["axes"])
        for key, frame in ctx["frames"].items()
    }
    ops: dict[str, Any] = {}
    for section in ctx["jobs"]:
        target = rt.job(doc, section["label"], [models[section["frame"]]], section["stock"])
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
