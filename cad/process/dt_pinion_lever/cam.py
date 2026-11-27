"""FreeCAD CAM recipe for MHA-DT-16, the pinion engage lever.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The lever's sizes come
from the feature export (the Ø.51 hub on +Z, the SR crown on its far end,
the Ø.24 grip rod on +Y from the hub's axis, its station from the mouth face,
the F-drilled flat-bottom bore, the root's inside-corner ceiling); the piece,
the window round the part, the tabs, levels, steps, scallop and the holes
from ``plan.toml`` ``[parameters]``; the cutters' diameters, speeds and feeds
from the shop (``shop/``) or the plan's authored operations. Every path is
written here (``rt.custom``): lines and arcs a recipe can state exactly.
Typed here, because neither record carries them: the #2 centre drill's
catalogue geometry, the twist drill's 118° point, the 1/16 in end mill's
1/8 in shank, the approach, safe and clearance heights and the vise jaws'
depth (keep-out shapes only).

Route (plan text in ``plan.toml``): the whole lever is milled out of a
4.75 in piece sawn off the 1/2 x 2-1/4 in 1018 flat, lying in the vise on
1-1/2 in parallel stacks and gripped on the bar's cold-finished edges, the
same edge at the fixed jaw in both setups. The rod lies along the bar, its
axis .20 below the bar's top (the mouth face, kept as bought); the hub's
axis runs through the bar's thickness. A window round the part is cleared
from each face, so the part ends hanging on two tabs on the rod's axis
plane: one behind the hub, one past the rod's tip. Mouth face up,
DT16_top_rough clears the window to a ball's radius past the axis plane
(passes of the 1/4 in end mill along the rod, each cut one way, a contour at
.010 stock round the part at each level) and finishes the hub's wall and the
rod's tip face; DT16_top_rod finishes the rod's upper half with the 1/4 in
ball end mill in passes along it; DT16_top_root cuts the rod's root with the
1/16 in end mill in fine levels (INSIDE CORNERS R.040 MAX) and finishes the
rod's tip face beside the tip tab, where the 1/4 in end mill cannot reach;
DT16_top_holes spots, drills the bore with the F drill, flattens its floor
with the 1/4 in HSS end mill, and drills F through the reference hole.
Turned end for end about the jaws' axis (mouth face down), DT16_crown_rough
clears the rest of the window and the shadow under the rod,
DT16_crown_dome_rod finishes the SR crown in rings and the rod's lower half
with the ball, DT16_crown_root the root's lower half and the tip face beside
the tab. The tabs are sawn and filed at the bench.

Work frames (G54), each set in its setup, in model terms (model: hub axis
+Z through the origin, rod +Y, mouth face at Z+.20):
- top (DT16_top_*): X = model Y (+X toward the rod's tip), Y = -model X
  (+Y toward the fixed jaw), Z0 the mouth face (the bar's top); X0 Y0 the
  hub's axis, set from the piece's left end and the fixed jaw.
- crown (DT16_crown_*): the top frame turned 180° about Y: X = -model Y
  (the rod toward -X), Y = -model X, Z0 the parallels' top (the mouth face,
  down); X0 from the reference hole the top frame drilled, Y0 the fixed jaw.

Toolpath rules (owner rulings 2026-11-16; #3590: no climb pass unless the
plan declares it with a reason, and none is declared here): real G0 above
the stock, feed below it; plunges beside the stock at the cutting feed and
into metal at the plunge feed. Every side cut is conventional under M3
(the stock on the cutter's left): contours round the part run anticlockwise
as each setup's spindle sees them, the ball's passes along the rod run
toward the rod's tip on one side and toward the hub on the other, and the
root's levels all run the same way, the cutter lifted and brought back
over the start between them. The window's raster passes overlap (no more
than a cutter's width apart): the first is a full-width slot along the
window's wall, and each next one meets uncut steel on its far side only, so
they all run the one way that cuts that side conventional, the cutter
lifted and brought back over the next start between them. The plan's
paths are stated here in model terms for the top frame (clockwise round the
part); the top frame is a turn of the model plan, so it runs them reversed,
and the crown frame mirrors the plan, so it runs them as stated.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_pinion_lever"
COMMENT = "MHA-DT-16 pinion engage lever"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes. A literal: dodo.py reads it with ast.literal_eval.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("DT16_top_rough", ("top_rough", "top_wall", "top_tip")),
    ("DT16_top_rod", ("top_rod_semi", "top_rod_finish")),
    ("DT16_top_root", ("top_root", "top_tip_tab")),
    (
        "DT16_top_holes",
        (("spot",), ("bore_drill", "ref_drill"), ("bore_floor",)),
    ),
    ("DT16_crown_rough", ("crown_rough", "crown_wall", "crown_tip")),
    (
        "DT16_crown_dome_rod",
        ("crown_dome_semi", "crown_dome_finish", "crown_rod_semi", "crown_rod_finish"),
    ),
    ("DT16_crown_root", ("crown_root", "crown_tip_tab")),
)
# Every program loads its own first tool (M6, the tool setter): a restart or
# a re-run never inherits the previous file's tool length.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, files and gauges are not).
CAM_TOOLS = (
    "em-quarter",
    "ball",
    "em-sixteenth",
    "spot",
    "drill-f",
    "em-hss",
)
# The 1/16 in end mill's shank (MSC 35497056, read 2026-11-24, #3568: 1/8 in;
# the shop record gives its diameter and its .500 of flutes only).
SIXTEENTH_SHANK_MM = 25.4 / 8
IN = 25.4
# ANSI #2 combined drill and countersink, 60° included: the shop record names
# the tool, not its geometry.
CENTRE_DRILL = {
    "pilot_mm": 0.078125 * IN,
    "pilot_length_mm": 0.078125 * IN,
    "body_mm": 0.1875 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# Heights above the stock top: a rapid stops SAFE_MM over it before a feed
# move down; moves between cuts run at CLEAR_MM over it.
SAFE_MM = 1.0
CLEAR_MM = 5.0
# The vise jaws' depth across the jaws (keep-out shapes only).
JAW_DEPTH_MM = IN
# A plunge into metal starts this far above the floor the column was cleared
# to (the switch from the cutting feed in air to the plunge feed).
PLUNGE_ABOVE_MM = 0.5
# Plan parameters the recipe recomputes agree to this.
PLAN_TOL_MM = 0.01
# A raster span shorter than this is not cut.
MIN_CUT_MM = 0.2
# The ball stops this far short of touching the hub's wall.
BALL_SHORT_MM = 0.02


def _plan_operations(plan: dict[str, Any]):
    for setup in plan["setups"]:
        yield from setup.get("operations", ())


def _op_with_cut(
    plan: dict[str, Any], name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    for op in _plan_operations(plan):
        cuts = op.get("milling_cuts", ())
        if not isinstance(cuts, list):
            continue
        for cut in cuts:
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
    op, record_cut = _op_with_cut(plan, cut)
    if "settings" not in op:
        return _cut(plan, cut, "rpm"), _cut(plan, cut, "feed_mm_min")
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    feed = record["chip_load_mm_per_tooth"] * record["flutes"] * rpm
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


def _levels(top: float, bottom: float, max_step: float) -> list[float]:
    """Equal step-down levels no deeper than ``max_step`` from ``top`` to
    ``bottom``, ``bottom`` last."""
    n = math.ceil((top - bottom) / max_step - 1e-9)
    return [top - (top - bottom) * (k + 1) / n for k in range(n - 1)] + [bottom]


def _r(value: float) -> float:
    """A coordinate as the post prints it (3 places)."""
    return round(value + 0.0, 3)


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


def ball_cusp(rb: float, radius: float, step: float) -> float:
    """The cusp a ball end mill of radius ``rb`` leaves between two passes
    ``step`` radians apart round a convex circle of ``radius`` (the rod's
    section, the crown's meridian), its centres on the circle of radius
    ``radius + rb``: where the two balls' surfaces cross on the bisector."""
    reach = radius + rb
    half = step / 2
    return (
        reach * math.cos(half)
        - math.sqrt(rb * rb - (reach * math.sin(half)) ** 2)
        - radius
    )


def ball_step(rb: float, radius: float, scallop: float) -> float:
    """The widest step (radians) whose :func:`ball_cusp` is ``scallop``."""
    # The widest step at which the two balls still overlap.
    lo, hi = 0.0, 2.0 * math.asin(rb / (radius + rb))
    for _ in range(60):
        mid = (lo + hi) / 2
        if ball_cusp(rb, radius, mid) > scallop:
            hi = mid
        else:
            lo = mid
    return lo


# --- the part's geometry, in model plan coordinates (x across the rod, y
# along it) and e, the height above the rod's axis plane on the side being
# cut (toward the mouth face in the top setup, toward the crown in the crown
# setup).


class Lever:
    """The lever's section at a height ``e`` on either side of the rod's axis
    plane: the hub's disc (the crown's above its rim on the crown side), the
    rod's strip and the two tabs."""

    def __init__(self, g: dict[str, float]):
        self.g = g

    def rod_half(self, e: float) -> float:
        """Half the rod's width at height ``e`` (zero above it)."""
        rod = self.g["rod_r"]
        return math.sqrt(rod * rod - e * e) if abs(e) < rod else 0.0

    def rod_reach(self, e: float) -> float:
        """The widest the rod stands at or above ``e`` on this side: what a
        flat-bottomed cutter at ``e`` must stay clear of."""
        return self.g["rod_r"] if e <= 0.0 else self.rod_half(e)

    def hub_reach(self, side: str, e: float) -> float:
        """The hub's (or crown's) widest radius at or above ``e``."""
        g = self.g
        if e <= g["hub_half"]:
            return g["hub_r"]
        if side == "top":
            return 0.0  # above the mouth face
        # The crown: a sphere of radius crown_r whose centre is crown_c past
        # the axis plane on the mouth side.
        d = e + g["crown_c"]
        return math.sqrt(g["crown_r"] ** 2 - d * d) if d < g["crown_r"] else 0.0

    def tabs_at(self, e: float) -> bool:
        """A tab stands at or above ``e`` (below its top face)."""
        return e < self.g["tab_half_t"]

    def blocked(
        self, side: str, e: float, x: float, grow: float, back: float, front: float
    ):
        """The y intervals a cutter centre on the line ``x`` at height ``e``
        must keep out of: the part's section at ``e`` grown by ``grow``
        (stock plus the cutter's radius), the tabs to the window's ends."""
        g = self.g
        out = []
        hub = self.hub_reach(side, e)
        if hub > 0.0 and abs(x) < hub + grow:
            h = math.sqrt((hub + grow) ** 2 - x * x)
            out.append((-h, h))
        rod = self.rod_reach(e)
        if rod > 0.0 and abs(x) < rod + grow:
            out.append((0.0, g["tip_y"] + grow))
        if self.tabs_at(e) and abs(x) < g["tab_half_w"] + grow:
            out.append((-back - grow, 0.0))
            out.append((g["tip_y"], front + grow))
        return out


def _subtract(span: tuple[float, float], blocked: list[tuple[float, float]]):
    """``span`` less the union of ``blocked``, as sorted intervals."""
    parts = [span]
    for a, b in blocked:
        out = []
        for c, d in parts:
            if b <= c or a >= d:
                out.append((c, d))
                continue
            if a > c:
                out.append((c, a))
            if b < d:
                out.append((b, d))
        parts = out
    return sorted(parts)


class Writer:
    """G-code in one setup's frame from model plan coordinates (x, y) and
    heights e. ``flip`` False: the top frame (X = y, Y = -x, Z = e - mouth);
    True: the crown frame (X = -y, Y = -x, Z = e + mouth)."""

    def __init__(self, flip: bool, mouth: float, top: float):
        self.flip, self.mouth, self.top = flip, mouth, top
        self.lines: list[str] = [f"G0 Z{_r(top + CLEAR_MM):.3f}"]

    def xy(self, x: float, y: float) -> tuple[float, float]:
        return (_r(-y), _r(-x)) if self.flip else (_r(y), _r(-x))

    def z(self, e: float) -> float:
        return _r(e + self.mouth) if self.flip else _r(e - self.mouth)

    def conventional(self, path: list[tuple]) -> list[tuple]:
        """A path stated clockwise in model terms round the part, as this
        frame cuts it conventional: anticlockwise as its spindle sees it. The
        top frame turns the model plan (clockwise stays clockwise), so it runs
        the path reversed; the crown frame mirrors it, so it runs it as
        stated."""
        return path if self.flip else _reverse(path)

    def along_x(self, y_frame: float) -> float:
        """The frame X direction (+1/-1) a straight pass along X at frame Y
        ``y_frame`` runs in to cut conventional under M3 against stock lying
        toward Y0 (the rod's axis): the stock on the cutter's left."""
        return 1.0 if y_frame < 0.0 else -1.0

    def up(self) -> None:
        """Straight up to the clearance height (a rapid: the column above a
        cut is clear)."""
        self.lines.append(f"G0 Z{_r(self.top + CLEAR_MM):.3f}")

    def over(self, x: float, y: float) -> None:
        """At the clearance height, over (x, y), then down to the safe height."""
        X, Y = self.xy(x, y)
        self.lines.append(f"G0 X{X:.3f} Y{Y:.3f}")
        self.lines.append(f"G0 Z{_r(self.top + SAFE_MM):.3f}")

    def down(self, e: float, cleared: float | None = None) -> None:
        """Feed down to ``e``: through the air at the cutting feed, then, below
        ``cleared`` (the floor the column was cleared to; None: all air), into
        metal at the plunge feed."""
        if cleared is None:
            self.lines.append(f"G1 Z{self.z(e):.3f} F{{feed}}")
            return
        switch = self.z(cleared + PLUNGE_ABOVE_MM)
        if self.z(e) < switch < self.top:
            self.lines.append(f"G1 Z{switch:.3f} F{{feed}}")
        self.lines.append(f"G1 Z{self.z(e):.3f} F{{plunge}}")

    def plunge(self, e: float) -> None:
        """Straight down to ``e`` from where the cutter stands, all of it at
        the plunge feed (what lies below may be metal)."""
        self.lines.append(f"G1 Z{self.z(e):.3f} F{{plunge}}")

    def lift(self, e: float) -> None:
        """Feed straight up to ``e`` inside the column already cut (below the
        stock's top, where no rapid runs)."""
        self.lines.append(f"G1 Z{self.z(e):.3f} F{{feed}}")

    def line(self, x: float, y: float) -> None:
        X, Y = self.xy(x, y)
        self.lines.append(f"G1 X{X:.3f} Y{Y:.3f} F{{feed}}")

    def arc(self, start, end, centre, cw_model: bool) -> None:
        """An arc in the plan from ``start`` to ``end`` round ``centre``."""
        sx, sy = self.xy(*start)
        ex, ey = self.xy(*end)
        cx, cy = self.xy(*centre)
        cw = cw_model != self.flip
        word = "G2" if cw else "G3"
        self.lines.append(
            f"{word} X{ex:.3f} Y{ey:.3f} I{_r(cx - sx):.3f} J{_r(cy - sy):.3f} F{{feed}}"
        )

    def path(self, path: list[tuple]) -> None:
        """Cut ``path`` (a start point and segments ("L", end) or ("A", end,
        centre, clockwise in model terms)), already at its start."""
        for seg in path[1:]:
            if seg[0] == "L":
                self.line(*seg[1])
            else:
                self.arc(_end_of(path, seg), seg[1], seg[2], seg[3])


def _end_of(path: list[tuple], seg: tuple) -> tuple[float, float]:
    """The point a path is at when ``seg`` starts."""
    k = next(i for i, s in enumerate(path) if s is seg)
    return path[k - 1][1]


def _reverse(path: list[tuple]) -> list[tuple]:
    """The same path run from its end to its start."""
    points = [seg[1] for seg in path]
    out = [("P", points[-1])]
    for k in range(len(path) - 1, 0, -1):
        seg = path[k]
        start = points[k - 1]
        out.append(("L", start) if seg[0] == "L" else ("A", start, seg[2], not seg[3]))
    return out


def _mirror(path: list[tuple]) -> list[tuple]:
    """``path`` mirrored across the rod's axis (x -> -x) and run backwards,
    so it stays clockwise."""
    flipped = [("P", (-path[0][1][0], path[0][1][1]))]
    for seg in path[1:]:
        end = (-seg[1][0], seg[1][1])
        if seg[0] == "L":
            flipped.append(("L", end))
        else:
            flipped.append(("A", end, (-seg[2][0], seg[2][1]), not seg[3]))
    return _reverse(flipped)


def _join(first: list[tuple], second: list[tuple]) -> list[tuple]:
    """``first`` then ``second``, which starts where ``first`` ends."""
    if math.dist(first[-1][1], second[0][1]) > 1e-6:
        raise ValueError("paths do not meet")
    return first + second[1:]


def _outline(
    lever: Lever, side: str, e: float, stock: float, r: float, rod: bool
) -> list[list[tuple]]:
    """The cutter-centre paths (radius ``r``), clockwise in model terms, round
    the part's section at height ``e`` grown by ``stock``: the hub's (or
    crown's) arc and, with ``rod``, the rod's sides and tip; split where a tab
    stands. Without ``rod`` the hub's arc runs between where the cutter meets
    the rod's sides."""
    g = lever.g
    hub = lever.hub_reach(side, e)
    if hub <= 0.0:
        return []
    big = hub + stock + r
    half = lever.rod_reach(e)
    tabs = lever.tabs_at(e)
    gap = g["tab_half_w"] + stock + r
    if half <= 0.0:
        if tabs:
            raise ValueError("a tab without the rod beside it")
        start = (0.0, big)
        return [
            [
                ("P", start),
                ("A", (0.0, -big), (0.0, 0.0), True),
                ("A", start, (0.0, 0.0), True),
            ]
        ]
    side_x = half + stock + r
    if side_x >= big:
        raise ValueError(f"at e {e:.3f} the rod's offset side misses the hub")
    meet = math.sqrt(big * big - side_x * side_x)
    back_x = gap if tabs else 0.0
    back = (back_x, -math.sqrt(big * big - back_x * back_x))
    if rod:
        # The right half: over the tip from beside the tip tab (or the tip's
        # middle), round the strip's corner, down the rod's right side and
        # round the hub's back to beside the back tab (or its bottom). A tab
        # wider than the strip's end moves the start onto the corner's arc.
        end_y = g["tip_y"] + stock
        corner_x = half + stock
        tip_x = gap if tabs else 0.0
        if tip_x < corner_x:
            right = [("P", (tip_x, end_y + r)), ("L", (corner_x, end_y + r))]
        elif tip_x < side_x:
            angle = math.acos((tip_x - corner_x) / r)
            right = [("P", (tip_x, end_y + r * math.sin(angle)))]
        else:
            raise ValueError("the tip tab is as wide as the rod")
        right += [
            ("A", (side_x, end_y), (corner_x, end_y), True),
            ("L", (side_x, meet)),
            ("A", back, (0.0, 0.0), True),
        ]
        left = _mirror(right)
        return [right, left] if tabs else [_join(right, left)]
    start = (side_x, meet)
    if tabs:
        return [
            [("P", start), ("A", back, (0.0, 0.0), True)],
            [("P", (-back[0], back[1])), ("A", (-side_x, meet), (0.0, 0.0), True)],
        ]
    return [
        [
            ("P", start),
            ("A", back, (0.0, 0.0), True),
            ("A", (-side_x, meet), (0.0, 0.0), True),
        ]
    ]


def raster_lines(
    half_w: float, r: float, stepover: float, inner: float
) -> list[tuple[float, float]]:
    """The window's raster lines (model x, along the rod) in the order they
    are cut, each with the side (+1: +x, -1: -x) its uncut steel lies on:
    from the -x wall in to -``inner``, then from the +x wall in to +``inner``
    (where the tabs' blocked spans begin, so no ridge stands beside a tab),
    each group's steps equal and no more than ``stepover``; then, when the
    two inner lines leave steel between them, one on the axis (a slot in that
    rib). The first line from each wall is a full-width slot; each next one
    meets steel only on its inner side, the outer side cut by the line before
    over the same spans (the part's blocked spans only grow toward the
    axis)."""
    lo, hi = -half_w + r, half_w - r
    if not r <= inner < hi:
        raise ValueError("the window is too narrow for a raster beside the tabs")
    n = math.ceil((hi - inner) / stepover - 1e-9)
    step = (hi - inner) / n
    # The inner lines exactly on ±inner: the tabs' spans begin there.
    lines = [(lo + step * k, 1.0) for k in range(n)] + [(-inner, 1.0)]
    lines += [(hi - step * k, -1.0) for k in range(n)] + [(inner, -1.0)]
    if inner > r:
        lines.append((0.0, 1.0))
    return lines


def _rough(
    lever: Lever,
    side: str,
    w: Writer,
    levels: list[float],
    e_top: float,
    window: tuple[float, float, float],
    r: float,
    stock: float,
    stepover: float,
    raster: bool,
) -> int:
    """Clear the window round the part in ``levels``: at each (with
    ``raster``) passes along the rod (model Y) on :func:`raster_lines`, through
    the free spans of each line (the part's section at the level less the
    stock grown by the stock and the cutter's radius, the tabs where they
    stand, the window's walls kept); then one conventional contour round the
    part at the stock. Every span runs the way that cuts its line's steel
    side conventional (clockwise round it in model terms: +y with the steel
    at +x, -y with it at -x), the cutter lifted and brought back over the
    next start. ``e_top``: the stock's top on this side (the first level
    plunges from it). Returns the spans cut."""
    half_w, back, front = window
    y_lo, y_hi = -back + r, front - r
    grow = stock + r
    cleared = e_top
    spans = 0
    for e in levels:
        # What stands at or above e, grown by the stock: the section at
        # e - stock (the rod and the crown widen toward the axis plane).
        probe = e - stock
        if raster:
            for x, steel in raster_lines(
                half_w, r, stepover, lever.g["tab_half_w"] + grow
            ):
                runs = [
                    (a, b) if steel > 0.0 else (b, a)
                    for a, b in _subtract(
                        (y_lo, y_hi), lever.blocked(side, probe, x, grow, back, front)
                    )
                    if b - a >= MIN_CUT_MM
                ]
                paths = [
                    w.conventional([("P", (x, a)), ("L", (x, b))]) for a, b in runs
                ]
                # The spans of a line in the order the frame runs them.
                if paths and paths[0][0][1][1] > paths[0][1][1][1]:
                    paths.sort(key=lambda path: -path[0][1][1])
                else:
                    paths.sort(key=lambda path: path[0][1][1])
                for path in paths:
                    w.over(*path[0][1])
                    w.down(e, cleared)
                    w.path(path)
                    w.up()
                    spans += 1
        for path in _outline(lever, side, probe, stock, r, rod=True):
            path = w.conventional(path)
            w.over(*path[0][1])
            w.down(e, cleared)
            w.path(path)
            w.up()
        cleared = e
    return spans


def _wall(
    lever: Lever, side: str, w: Writer, levels: list[float], r: float, e_top: float
) -> None:
    """Finish the hub's wall (below the rim on the crown side) at each level:
    the conventional arc round the back to the rod, split at the back tab; each
    entered at the plunge feed through the stock the level above left."""
    cleared = e_top
    for e in levels:
        for path in _outline(lever, side, e, 0.0, r, rod=False):
            path = w.conventional(path)
            w.over(*path[0][1])
            w.down(e, cleared)
            w.path(path)
            w.up()
        cleared = e


def _tip(lever: Lever, w: Writer, levels: list[float], r: float, e_top: float) -> None:
    """Finish the rod's tip face at each level the rod stands at and no tab
    does: a conventional pass across it, the cutter's side on the face; each
    entered at the plunge feed through the stock the level above left. Where
    a tab stands, the cutter (its radius wider than the rod's half less the
    tab's) cannot reach the face beside it: :func:`_tip_tab` finishes it."""
    y = lever.g["tip_y"] + r
    cleared = e_top
    for e in levels:
        half = lever.rod_reach(e)
        if half > 0.0 and not lever.tabs_at(e):
            path = w.conventional([("P", (-half - r, y)), ("L", (half + r, y))])
            w.over(*path[0][1])
            w.down(e, cleared)
            w.path(path)
            w.up()
        cleared = e


def _tab_corner(g: dict[str, float], r6: float, stock: float) -> tuple[float, float]:
    """The centre of the 1/4 in end mill's circle that bounds the corner it
    leaves beside the tip tab at a tab level: where its contour round the part
    (:func:`_outline`) starts, beside the tab's stock on the tip's corner arc,
    taken where the rod is widest (the corner then stands farthest out)."""
    gap = g["tab_half_w"] + stock + r6
    off = max(0.0, gap - (g["rod_r"] + stock))
    return gap, g["tip_y"] + stock + math.sqrt(r6 * r6 - off * off)


def tip_tab_rows(
    g: dict[str, float], r5: float, r6: float, stock: float
) -> tuple[list[float], float]:
    """The rows (model y of the 1/16 in end mill's centre) finishing the tip
    face beside the tip tab, outermost first, equally spaced no more than r5
    apart, the last on the face (tip_y + r5); and the row that would just
    touch the corner (:func:`_tab_corner`) where the 1/16 in end mill stands
    beside the tab's stock (x = tab_half_w + stock + r5), one step outside
    the first."""
    cx, cy = _tab_corner(g, r6, stock)
    x_in = g["tab_half_w"] + stock + r5
    face = cy - math.sqrt(r6 * r6 - (cx - x_in) ** 2)
    tip = g["tip_y"]
    n = math.ceil((face - tip) / r5 - 1e-9)
    step = (face - tip) / n
    return [tip + r5 + step * k for k in range(n - 1, -1, -1)], face + r5


def _tip_tab(
    lever: Lever,
    w: Writer,
    levels: list[float],
    r5: float,
    r6: float,
    stock: float,
    e_top: float,
) -> list[dict[str, float]]:
    """Finish the rod's tip face beside the tip tab with the 1/16 in end mill,
    where the 1/4 in end mill leaves its corner (:func:`_tab_corner`): each
    side of the tab in turn, at each level, a pass along the face on each of
    :func:`tip_tab_rows`, outermost first, from beside the tab's stock (the
    cutter's side on it) out to where the corner ends at the row's lower
    edge, the last out past the rod's side and its stock. Each runs +x in
    model terms (clockwise round the part: conventional), its far half inside
    the row before. Between passes the cutter rises to the level above (cut
    already), crosses there and plunges; between levels it crosses at the
    level just cut. The tab's stock keeps the cutter's radius in its corner
    with the face. ``e_top``: the lowest level the 1/4 in end mill crossed
    the whole tip at. Returns each pass's level, row and ends (model x)."""
    g = lever.g
    x_in = g["tab_half_w"] + stock + r5
    if x_in >= g["rod_r"]:
        raise ValueError("the 1/16 in end mill does not fit beside the tip tab")
    cx, cy = _tab_corner(g, r6, stock)
    rows, _raw = tip_tab_rows(g, r5, r6, stock)
    out = []
    for sign in (1.0, -1.0):
        above, at = e_top, None
        for e in levels:
            cap = lever.rod_reach(e) + stock + r5
            for y in rows:
                # Where the corner meets the row's lower edge.
                d = min(cy - (y - r5), r6)
                x_out = min(cap, cx - math.sqrt(r6 * r6 - d * d))
                if x_out - x_in < MIN_CUT_MM:
                    continue
                path = [("P", (x_in, y)), ("L", (x_out, y))]
                if sign < 0:
                    path = _mirror(path)
                path = w.conventional(path)
                if at is None:
                    w.over(*path[0][1])
                    w.down(e, above)
                else:
                    if at != above:
                        w.lift(above)
                    w.line(*path[0][1])
                    w.plunge(e)
                w.path(path)
                at = e
                out.append({"e": e, "y": y, "x_in": sign * x_in, "x_out": sign * x_out})
            above = e
        w.up()
    return out


def _ball_passes(
    lever: Lever, w: Writer, rb: float, stock: float, step: float
) -> list[dict[str, float]]:
    """Passes of the ball end mill along the rod's half on this side, its
    centre ``stock`` + rb off the rod's surface, at angles round the rod from
    one side (-90°) over the top to the other, ``step`` radians apart at
    most, each conventional (:meth:`Writer.along_x`: the rod on the cutter's
    left). A pass that runs toward the hub enters in the air past the tip and
    stops just short of the hub's wall; one that runs toward the tip comes
    down beside the hub's wall (in the air to the rod's top, then at the
    plunge feed) and leaves into the air past the tip. The pass over the top
    (the rod on both sides of the ball) runs toward the hub. Each then goes
    straight up. Returns each pass's angle, centre, ends and way."""
    g = lever.g
    reach = g["rod_r"] + stock + rb
    n = math.ceil(math.pi / step - 1e-9)
    y_tip = g["tip_y"] + rb + 1.0
    out = []
    for k in range(n + 1):
        phi = -math.pi / 2 + math.pi * k / n
        x_c = reach * math.sin(phi)
        e_c = reach * math.cos(phi)
        y_hub = math.sqrt((g["hub_r"] + stock + rb) ** 2 - x_c * x_c) + BALL_SHORT_MM
        to_tip = abs(x_c) > 1e-9 and (w.along_x(-x_c) > 0.0) != w.flip
        if to_tip:
            w.over(x_c, y_hub)
            w.down(e_c - rb, g["rod_r"] + stock)
            w.line(x_c, y_tip)
        else:
            w.over(x_c, y_tip)
            w.down(e_c - rb)
            w.line(x_c, y_hub)
        w.up()
        out.append(
            {
                "phi": phi,
                "x": x_c,
                "e_centre": e_c,
                "y_tip": y_tip,
                "y_hub": y_hub,
                "to_tip": to_tip,
            }
        )
    return out


def _dome_rings(
    lever: Lever, w: Writer, rb: float, stock: float, step: float, e_top: float
) -> list[dict[str, float]]:
    """Rings of the ball end mill over the crown, its centre ``stock`` + rb
    off the sphere, from a plunge at the apex out to the rim, ``step``
    radians apart along the meridian at most, each a full conventional circle."""
    g = lever.g
    reach = g["crown_r"] + stock + rb
    a_max = math.asin(g["hub_r"] / g["crown_r"])
    n = math.ceil(a_max / step - 1e-9)
    rings = []
    for k in range(n + 1):
        a = a_max * k / n
        rho = reach * math.sin(a)
        e_c = reach * math.cos(a) - g["crown_c"]
        if k == 0:
            w.over(0.0, 0.0)
            w.down(e_c - rb, e_top)
        else:
            # Out at the last ring's height, then down: a straight chord
            # between the two rings would dip into the sphere by its sagitta.
            # The roughing's steps over the crown stand below: all the way
            # down at the plunge feed.
            w.line(rho, 0.0)
            w.plunge(e_c - rb)
            ring = w.conventional(
                [
                    ("P", (rho, 0.0)),
                    ("A", (-rho, 0.0), (0.0, 0.0), True),
                    ("A", (rho, 0.0), (0.0, 0.0), True),
                ]
            )
            w.path(ring)
        rings.append({"a": a, "rho": rho, "e_centre": e_c})
    w.up()
    return rings


def root_levels(
    rod_r: float, bottom: float, cusp: float, max_step: float
) -> list[float]:
    """The root's levels from the rod's top down to ``bottom``: the first on
    the top itself (the crest beside the hub's wall, which the ball's pass
    over the top stops short of), then each step as deep as leaves a stair
    no taller than ``cusp`` normal to the rod's surface (a step ``s`` at
    height ``e`` stands ``s * e / rod_r`` off the surface: the full step on
    the flat top, nothing at the side), and never deeper than ``max_step``;
    ``bottom`` last."""
    out = [rod_r]
    e = rod_r
    while True:
        s = max_step if e <= 0.0 else min(max_step, cusp * rod_r / e)
        e -= s
        if e <= bottom + 1e-9:
            return out + [bottom]
        out.append(e)


def _root(
    lever: Lever,
    w: Writer,
    levels: list[float],
    r5: float,
    r6: float,
    rb: float,
    overlap: float,
) -> list[dict[str, float]]:
    """The rod's root with the 1/16 in end mill in fine levels down from the
    rod's top, each side in turn, every level conventional: in from past
    where the 1/4 in end mill's arc began on the hub's wall, round the wall
    and along the rod's side to past where the ball's last pass touched it,
    then up, back over the next level's start and down to it. The rod and
    the hub's wall meet at the small cutter's radius."""
    g = lever.g
    rod_r, hub_r = g["rod_r"], g["hub_r"]
    big = hub_r + r5
    out = []
    for sign in (1.0, -1.0):
        for e in levels:
            half = lever.rod_reach(e)
            side_x = half + r5
            meet = math.sqrt(big * big - side_x * side_x)
            # Where the ball touched the rod at this height, its pass ending
            # with its centre that far along.
            phi = math.acos(min(1.0, max(e, 0.0) / rod_r))
            x_ball = (rod_r + rb) * math.sin(phi)
            y_ball = math.sqrt((hub_r + rb) ** 2 - x_ball * x_ball) + BALL_SHORT_MM
            y_start = max(y_ball, meet) + overlap
            # The 1/4 in end mill's arc began where its side met the rod.
            x6 = half + r6
            a6 = math.atan2(math.sqrt((hub_r + r6) ** 2 - x6 * x6), x6) - overlap / big
            path = [
                ("P", (side_x, y_start)),
                ("L", (side_x, meet)),
                ("A", (big * math.cos(a6), big * math.sin(a6)), (0.0, 0.0), True),
            ]
            if sign < 0:
                path = _mirror(path)
            path = w.conventional(path)
            w.over(*path[0][1])
            w.down(e)
            w.path(path)
            w.up()
            out.append(
                {"e": e, "x": sign * side_x, "y_start": y_start, "meet": meet, "a6": a6}
            )
    return out


def _spot(xy: tuple[float, float], z: float) -> list[str]:
    return [
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{SAFE_MM:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{CLEAR_MM:.3f}",
    ]


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    f = features["features"]
    p = plan["parameters"]

    # The model frame this recipe assumes: the hub's axis +Z through the
    # origin, the rod +Y from it, the mouth face a plane across Z above.
    model = features["frames"]["model"]
    if model["x"] != [1.0, 0.0, 0.0] or model["y"] != [0.0, 1.0, 0.0]:
        raise ValueError("expected the identity model frame")
    hub, crown, rod, bore = f["hub"], f["crown"], f["grip_rod"], f["bore"]
    mouth = f["mouth_face_b"]["plane"]
    if mouth["axis"] != "z":
        raise ValueError("mouth_face_b: expected a plane across Z")
    mouth_z = mouth["value"]
    if hub["axis"] != [0.0, 0.0, 1.0] or hub["at"] != [0.0, 0.0, 0.0]:
        raise ValueError("hub: expected its axis +Z through the origin")
    if rod["axis"] != [0.0, 1.0, 0.0] or rod["at"] != [0.0, 0.0, 0.0]:
        raise ValueError("grip_rod: expected its axis +Y through the origin")
    if bore["axis"] != [0.0, 0.0, -1.0] or bore["at"] != [0.0, 0.0, mouth_z]:
        raise ValueError("bore: expected down the hub's axis from the mouth face")
    if bore["flat_bottom"] is not True or rod["length_from"] != "hub":
        raise ValueError(
            "bore: expected flat-bottomed; grip_rod: its length from the hub"
        )
    if rod["station_from"] != "mouth_face_b" or crown["overall_from"] != "mouth_face_b":
        raise ValueError(
            "grip_rod station, crown overall: expected from the mouth face"
        )
    made = {"mouth_face_b", "hub", "crown", "grip_rod", "bore"}
    for name, feature in f.items():
        if name not in made and feature.get("made_at") != "assembly":
            raise ValueError(f"{name}: a feature this recipe does not make")

    # Targets: each band's nominal (the model's), checked inside the band.
    def nominal(feature: dict[str, Any], key: str) -> float:
        value = feature[f"{key}_nominal"]
        lo, hi = feature[key]
        if not lo - 1e-6 <= value <= hi + 1e-6:
            raise ValueError(f"{key}: nominal {value} outside {feature[key]}")
        return value

    hub_r = nominal(hub, "dia") / 2
    rod_r = nominal(rod, "dia") / 2
    tip_y = nominal(rod, "length")
    crown_r = nominal(crown, "radius")
    apex = nominal(crown, "overall") - mouth_z  # below the rod's axis plane
    if not math.isclose(nominal(rod, "station"), mouth_z, abs_tol=1e-3):
        raise ValueError(
            "grip_rod: its station is not the mouth face's height over its axis"
        )
    if not math.isclose(-crown["apex_at"][2], apex, abs_tol=1e-3):
        raise ValueError(
            "crown: its apex is not the overall length from the mouth face"
        )
    if not math.isclose(rod["extent_y"][1], tip_y, abs_tol=1e-3):
        raise ValueError("grip_rod: its tip is not its length from the hub's axis")
    hub_half = mouth_z
    crown_c = crown_r - apex  # the sphere's centre past the axis plane, mouth side
    rim = math.sqrt(crown_r**2 - hub_r**2) - crown_c
    # The crown meets the wall as far below the axis plane as the mouth face
    # is above it: the wall runs the same height each side.
    if not math.isclose(rim, hub_half, abs_tol=PLAN_TOL_MM):
        raise ValueError(
            f"crown: its rim stands {rim:.3f} below the axis, not {hub_half:.3f}"
        )
    floor = nominal(bore, "depth")
    bore_lo, bore_hi = bore["dia"]
    if bore["process"] != "drill" or bore["drill"] != "F":
        raise ValueError("bore: expected F DRILL")
    _agree(plan, "apex_below_axis_mm", apex)
    _agree(plan, "mouth_above_axis_mm", mouth_z)

    # Cutters.
    r6 = _shop_tool(plan, shop, "em-quarter")["diameter_mm"] / 2
    rb = _shop_tool(plan, shop, "ball")["diameter_mm"] / 2
    sixteenth = _shop_tool(plan, shop, "em-sixteenth")
    r5 = sixteenth["diameter_mm"] / 2
    d_f = _shop_tool(plan, shop, "drill-f")["diameter_mm"]
    d_hss = _shop_tool(plan, shop, "em-hss")["diameter_mm"]
    if r5 > rod["root_corner_r_max"]:
        raise ValueError(
            f"the root cutter's radius {r5:.3f} exceeds R {rod['root_corner_r_max']:.3f} max"
        )
    # The F drill is the bore (drawing: F DRILL, the title block's DRILLED
    # HOLES band); the 1/4 in HSS end mill flattens the floor inside it.
    if not bore_lo - 1e-6 <= d_f <= bore_hi + 1e-6:
        raise ValueError("drill-f: not inside the bore's band")
    if not d_hss < d_f:
        raise ValueError("bore: expected the floor's end mill under the F drill")
    _agree(plan, "cutter_dia_mm", 2 * r6)
    _agree(plan, "ball_dia_mm", 2 * rb)
    _agree(plan, "root_cutter_dia_mm", 2 * r5)

    # The piece, the window and the frame round it.
    bar_t_min, bar_t_max = p["bar_thickness_min_mm"], p["bar_thickness_max_mm"]
    bar_w_min, bar_w_max = p["bar_width_min_mm"], p["bar_width_max_mm"]
    half_w = p["half_width_mm"]
    from_end = p["hub_from_end_mm"]
    piece_min, piece_max = p["piece_min_mm"], p["piece_max_mm"]
    win_half, win_back, win_tip = (
        p["window_half_mm"],
        p["window_back_mm"],
        p["window_tip_mm"],
    )
    stock = p["stock_mm"]
    overlap = p["floor_overlap_mm"]
    clear = p["clear_min_mm"]
    tab_w, tab_t = p["tab_width_mm"], p["tab_thickness_mm"]
    step = p["rough_step_max_mm"]
    # The window: the hub's wall contour (a cutter's diameter past the wall
    # and the stock) inside it across and behind; the ball's passes beside
    # the rod and past its tip inside it; each by clear_min_mm.
    need_half = max(hub_r + stock + 2 * r6, rod_r + stock + 2 * rb) + clear
    if win_half < need_half:
        raise ValueError(f"process.window_half_mm under {need_half:.3f}")
    if win_back < hub_r + stock + 2 * r6 + clear:
        raise ValueError(
            "process.window_back_mm: the wall's contour reaches the window's end"
        )
    if win_tip < tip_y + 2 * rb + 1.0 + clear:
        raise ValueError(
            "process.window_tip_mm: the ball's passes start in the window's end"
        )
    end_back = from_end - win_back
    end_tip = piece_min - from_end - win_tip
    _agree(plan, "end_wall_min_mm", min(end_back, end_tip))
    if min(end_back, end_tip) < p["end_wall_floor_mm"]:
        raise ValueError(
            "a frame end round the window is under process.end_wall_floor_mm"
        )
    _agree(plan, "side_wall_min_mm", half_w - (bar_w_max - bar_w_min) - win_half)
    # The tabs, and the .010 stock and one level's staircase on them, lie
    # inside the rod's section: what stands of them past the tip is inside
    # the rod's shadow, which no ball pass enters.
    corner = math.hypot(tab_w / 2 + stock, tab_t / 2 + stock + step)
    if corner >= rod_r:
        raise ValueError(
            f"a tab's corner stands {corner:.3f} off the rod's axis, outside the rod"
        )
    # The reference hole: in the frame's side, clear of the window and of
    # the moving jaw's parallels, which on the narrowest bar stand
    # bar_width_min_mm - half_width_mm from the hub's axis.
    ref_x, ref_y = p["ref_hole_x_mm"], p["ref_hole_y_mm"]
    t_par = p["parallel_thickness_mm"]
    stack_x = bar_w_min - half_w - t_par
    if not win_half + d_f / 2 + clear <= ref_x <= stack_x - d_f / 2 - clear:
        raise ValueError(
            "process.ref_hole_x_mm: the reference hole meets the window or a parallel"
        )
    if not 0.0 <= ref_y <= win_tip:
        raise ValueError("process.ref_hole_y_mm: outside the window's length")

    g = {
        "hub_r": hub_r,
        "hub_half": hub_half,
        "rod_r": rod_r,
        "tip_y": tip_y,
        "crown_r": crown_r,
        "crown_c": crown_c,
        "tab_half_w": tab_w / 2,
        "tab_half_t": tab_t / 2,
    }
    lever = Lever(g)

    # Levels. Top: from the mouth face to the ball's radius and the overlap
    # past the axis plane (the ball's side passes dip that far). Crown:
    # rastered from the thickest bar's face to the overlap short of the top
    # setup's floor; below that only the contour round the part (the window
    # is clear but for the shadow under the rod and the tabs), to the overlap
    # past the axis plane.
    top_floor = -(rb + overlap)
    crown_top = bar_t_max - mouth_z
    crown_raster_floor = -top_floor - overlap
    crown_floor = -overlap
    if bar_t_min - mouth_z < apex:
        raise ValueError("the thinnest bar does not cover the crown's apex")
    top_levels = _levels(mouth_z, top_floor, step)
    crown_raster = _levels(crown_top, crown_raster_floor, step)
    crown_contour = _levels(crown_raster_floor, crown_floor, step)
    _agree(plan, "top_floor_depth_mm", mouth_z - top_floor)
    _agree(plan, "crown_raster_z_mm", crown_raster_floor + mouth_z)
    _agree(plan, "crown_floor_z_mm", crown_floor + mouth_z)
    crown_levels = crown_raster + crown_contour
    wall_top = [e for e in top_levels if e <= hub_half]
    wall_crown = [e for e in crown_levels if e <= hub_half]
    levels_root = root_levels(
        rod_r, -overlap, p["root_cusp_max_mm"], p["root_level_max_mm"]
    )
    # The tip face beside the tip tab, with the 1/16 in end mill: from the
    # lowest level each setup's 1/4 in end mill crossed the whole tip at
    # (above the tab) down to the root's bottom, in the root's steps.
    tab_free = {
        side: min(e for e in levels if not lever.tabs_at(e))
        for side, levels in (("top", top_levels), ("crown", crown_levels))
    }
    tip_tab_levels = {
        side: _levels(e0, levels_root[-1], p["root_level_max_mm"])
        for side, e0 in tab_free.items()
    }
    tab_rows, tab_raw = tip_tab_rows(g, r5, r6, stock)
    _agree(plan, "tip_tab_step_mm", tab_raw - tab_rows[0])
    _agree(plan, "tip_station_mm", from_end + tip_y)
    # The 1/16 in end mill's flutes reach the root's lowest level from above
    # the highest part its 1/8 in shank could meet beside the root: face B on
    # the top side, the crown's dome (inside the shank's reach of the hub's
    # axis) on the crown side.
    shank_rho = hub_r + r5 - SIXTEENTH_SHANK_MM / 2
    dome_e = math.sqrt(crown_r**2 - max(shank_rho, 0.0) ** 2) - crown_c
    reach_need = max(hub_half, dome_e) - levels_root[-1]
    if sixteenth["flute_length_mm"] < reach_need:
        raise ValueError(
            f"em-sixteenth: {sixteenth['flute_length_mm']:.3f} of flutes, the root needs {reach_need:.3f}"
        )
    _agree(plan, "root_reach_mm", reach_need)
    if p["rough_stepover_mm"] > 2 * r6 + 1e-9:
        raise ValueError(
            "process.rough_stepover_mm: over the cutter's width (a rib stands between passes)"
        )
    # The raster's passes after the first (a full-width slot) step this far
    # into the steel (the plan's side cut).
    lines_x = raster_lines(win_half, r6, p["rough_stepover_mm"], tab_w / 2 + stock + r6)
    rough_woc = lines_x[1][0] - lines_x[0][0]
    _agree(plan, "rough_woc_mm", rough_woc)

    rpm6, feed6 = _setting(plan, shop, "window rough")
    plunge6 = p["plunge_feed_per_min_mm"]
    rpm_b, feed_b = _setting(plan, shop, "rod semi")
    rpm5, feed5 = _setting(plan, shop, "root")
    scallop = p["scallop_max_mm"]
    rod_step = ball_step(rb, rod_r, scallop)
    dome_step = ball_step(rb, crown_r, scallop)
    semi_step = math.radians(p["semi_step_deg"])
    _agree(plan, "rod_step_deg", math.degrees(rod_step))
    _agree(plan, "dome_step_deg", math.degrees(dome_step))

    frames = {
        "top": {
            "origin": [0.0, 0.0, mouth_z],
            "axes": [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        },
        "crown": {
            "origin": [0.0, 0.0, mouth_z],
            "axes": [[0.0, -1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, -1.0]],
        },
    }
    stocks = {
        "top": (
            (-from_end, piece_max - from_end),
            (half_w - bar_w_max, half_w),
            (-bar_t_max, 0.0),
        ),
        "crown": (
            (from_end - piece_max, from_end),
            (half_w - bar_w_max, half_w),
            (0.0, bar_t_max),
        ),
    }
    tops = {"top": 0.0, "crown": bar_t_max}
    window = (win_half, win_back, win_tip)

    def writer(side: str) -> Writer:
        return Writer(side == "crown", mouth_z, tops[side])

    lines: dict[str, list[str]] = {}
    built: dict[str, Any] = {}
    for side in ("top", "crown"):
        w = writer(side)
        if side == "top":
            built["top_rough"] = _rough(
                lever,
                side,
                w,
                top_levels,
                mouth_z,
                window,
                r6,
                stock,
                p["rough_stepover_mm"],
                True,
            )
        else:
            spans = _rough(
                lever,
                side,
                w,
                crown_raster,
                crown_top,
                window,
                r6,
                stock,
                p["rough_stepover_mm"],
                True,
            )
            _rough(
                lever,
                side,
                w,
                crown_contour,
                crown_raster_floor,
                window,
                r6,
                stock,
                p["rough_stepover_mm"],
                False,
            )
            built["crown_rough"] = spans
        lines[f"{side}_rough"] = w.lines
        w = writer(side)
        e_top = mouth_z if side == "top" else crown_top
        _wall(lever, side, w, wall_top if side == "top" else wall_crown, r6, e_top)
        lines[f"{side}_wall"] = w.lines
        w = writer(side)
        _tip(lever, w, top_levels if side == "top" else crown_levels, r6, e_top)
        lines[f"{side}_tip"] = w.lines
        for key, offset, angle in (
            ("rod_semi", stock, semi_step),
            ("rod_finish", 0.0, rod_step),
        ):
            w = writer(side)
            built[f"{side}_{key}"] = _ball_passes(lever, w, rb, offset, angle)
            lines[f"{side}_{key}"] = w.lines
        w = writer(side)
        built[f"{side}_root"] = _root(
            lever, w, levels_root, r5, r6, rb, p["root_overlap_mm"]
        )
        lines[f"{side}_root"] = w.lines
        w = writer(side)
        built[f"{side}_tip_tab"] = _tip_tab(
            lever, w, tip_tab_levels[side], r5, r6, stock, tab_free[side]
        )
        lines[f"{side}_tip_tab"] = w.lines
    for key, offset, angle in (
        ("crown_dome_semi", stock, semi_step),
        ("crown_dome_finish", 0.0, dome_step),
    ):
        w = writer("crown")
        built[key] = _dome_rings(lever, w, rb, offset, angle, crown_top)
        lines[key] = w.lines

    # The holes, in the top frame: the bore down the hub's axis from the
    # mouth face, the reference hole through the frame's side.
    bore_xy = (0.0, 0.0)
    ref_xy = writer("top").xy(ref_x, ref_y)
    spot_z = -_spot_depth(p["spot_dia_mm"])
    drill_tip = -(floor - p["drill_short_mm"])
    if -drill_tip - _point(d_f) <= 0.0:
        raise ValueError("the F drill's full diameter does not enter the bore")
    # The 1/4 in HSS end mill plunges to the floor on the axis, then turns
    # one circle there with its edge on floor_dia_mm: it flattens the floor
    # and takes the wall below the F drill's full diameter (its point's
    # cone) out to the bore's band, so the bore is Ø floor_dia_mm or the
    # drill's to its floor, the floor flat across.
    floor_z = -floor
    floor_dia = p["floor_dia_mm"]
    if not bore_lo + 1e-6 < floor_dia < bore_hi - 1e-6:
        raise ValueError("process.floor_dia_mm: not inside the bore's band")
    floor_r = (floor_dia - d_hss) / 2
    ref_tip = -(bar_t_max + _point(d_f) + p["drill_past_mm"])
    _agree(plan, "drill_tip_mm", -drill_tip)
    _agree(plan, "ref_tip_mm", -ref_tip)
    _agree(plan, "ref_tip_height_mm", bar_t_max + ref_tip)
    _agree(plan, "ref_station_mm", from_end + ref_y)
    # The lowest the ball reaches in the crown setup (its side passes), above
    # the stacks.
    _agree(plan, "ball_low_z_mm", mouth_z - rb)

    # The crown's check on the mill: the ball's tip on the apex, then over
    # sr_probe_x_mm off the axis; the drop between them for the band's SR
    # (the ball's centre SR + rb from the sphere's centre). The second touch
    # lies on the dome, inside its rim, at the band's ends.
    probe = p["sr_probe_x_mm"]
    drops = []
    for sr in crown["radius"]:
        reach = sr + rb
        if probe / reach >= hub_r / sr:
            raise ValueError(
                "process.sr_probe_x_mm: the ball touches the crown's rim, not its dome"
            )
        drops.append(reach - math.sqrt(reach * reach - probe * probe))
    _agree(plan, "sr_drop_min_mm", min(drops))
    _agree(plan, "sr_drop_max_mm", max(drops))
    spot_rpm, spot_feed = _setting(plan, shop, "spots")
    f_rpm, f_feed = _setting(plan, shop, "bore drill")
    hss_rpm, hss_feed = _setting(plan, shop, "bore floor")
    start = [f"G0 Z{CLEAR_MM:.3f}"]
    lines["spot"] = start + _spot(bore_xy, spot_z) + _spot(ref_xy, spot_z)
    lines["bore_drill"] = start + _spot(bore_xy, drill_tip)
    lines["ref_drill"] = _spot(ref_xy, ref_tip)
    lines["bore_floor"] = start + [
        f"G0 X{bore_xy[0]:.3f} Y{bore_xy[1]:.3f}",
        f"G0 Z{SAFE_MM:.3f}",
        f"G1 Z{_r(floor_z):.3f} F{{plunge}}",
        f"G1 X{_r(bore_xy[0] + floor_r):.3f} F{{plunge}}",
        # Clockwise round the bore (the wall outside the cutter): conventional
        # under M3.
        f"G2 X{_r(bore_xy[0] + floor_r):.3f} Y{bore_xy[1]:.3f} I{_r(-floor_r):.3f} J0.000 F{{plunge}}",
        f"G1 X{bore_xy[0]:.3f} F{{plunge}}",
        f"G1 Z{SAFE_MM:.3f} F{{plunge}}",
        f"G0 Z{CLEAR_MM:.3f}",
    ]

    tools = plan["tools"]
    names = {t["id"]: t["name"] for t in tools if t["id"] in CAM_TOOLS}
    order = [t["id"] for t in tools if t["id"] in CAM_TOOLS]
    if sorted(order) != sorted(CAM_TOOLS):
        raise ValueError(f"plan tools {order}, the recipe runs {CAM_TOOLS}")
    tn = {tool: k + 1 for k, tool in enumerate(order)}

    def job(tool, frame, shape, dia, rpm, feed, plunge, ops, flutes=None, tip=None):
        return {
            "tool": tool,
            "frame": frame,
            "label": f"{frame} {tool}",
            "stock": stocks[frame],
            "shape": shape,
            "dia": dia,
            "rpm": rpm,
            "feed": feed,
            "plunge": plunge,
            "flutes": flutes,
            "tip_angle": tip,
            "ops": [[key, label, lines[key]] for key, label in ops],
        }

    jobs = []
    for side in ("top", "crown"):
        jobs.append(
            job(
                "em-quarter",
                side,
                "endmill",
                2 * r6,
                rpm6,
                feed6,
                plunge6,
                [
                    (f"{side}_rough", "rough the window"),
                    (f"{side}_wall", "finish the hub's wall"),
                    (f"{side}_tip", "finish the rod's tip face"),
                ],
                flutes=3,
            )
        )
        ball_ops = (
            [
                ("crown_dome_semi", "crown semi-finish"),
                ("crown_dome_finish", "crown finish"),
            ]
            if side == "crown"
            else []
        )
        ball_ops += [
            (f"{side}_rod_semi", "rod semi-finish"),
            (f"{side}_rod_finish", "rod finish"),
        ]
        jobs.append(
            job(
                "ball",
                side,
                "ballend",
                2 * rb,
                rpm_b,
                feed_b,
                plunge6,
                ball_ops,
                flutes=2,
            )
        )
        jobs.append(
            job(
                "em-sixteenth",
                side,
                "endmill",
                2 * r5,
                rpm5,
                feed5,
                feed5,
                [
                    (f"{side}_root", "the rod's root"),
                    (f"{side}_tip_tab", "the rod's tip face beside the tab"),
                ],
                flutes=3,
            )
        )
        if side == "top":
            jobs.append(
                job(
                    "spot",
                    "top",
                    "drill",
                    CENTRE_DRILL["body_mm"],
                    spot_rpm,
                    spot_feed,
                    spot_feed,
                    [("spot", "spot the bore and the reference hole")],
                    tip=CENTRE_DRILL["point_deg"],
                )
            )
            jobs.append(
                job(
                    "drill-f",
                    "top",
                    "drill",
                    d_f,
                    f_rpm,
                    f_feed,
                    f_feed,
                    [
                        ("bore_drill", "drill the bore"),
                        ("ref_drill", "drill the reference hole"),
                    ],
                    tip=DRILL_POINT_DEG,
                )
            )
            jobs.append(
                job(
                    "em-hss",
                    "top",
                    "endmill",
                    d_hss,
                    hss_rpm,
                    hss_feed,
                    hss_feed,
                    [("bore_floor", "flatten the bore's floor")],
                    flutes=2,
                )
            )

    # Keep-outs. The jaws along the bar's edges above the stacks, the stacks
    # under the edges, each where the narrowest and thinnest bar the
    # programs accept puts it (nearest the cutters: the moving jaw closes
    # in to it; in Setup 2 the stacks' top rises to it, face B the zero); the
    # tabs between their faces; the hub's wall, the crown in bands and the
    # rod in bands, each shape inside the part over its band (the narrowest
    # section of the band): a flat cutter's point in one is a gouge. The
    # ball's paths are checked against the part by
    # test_dt_pinion_lever_process.py (a ball is not a flat cutter).
    jaw_w = p["vise_jaw_width_mm"]
    grip = p["lying_grip_mm"]
    inset = p["vise_inset_mm"]
    stack_tops = {"top": -bar_t_min, "crown": 0.0}

    def fixtures(side: str) -> list[dict[str, Any]]:
        x0 = stocks[side][0][0] + inset
        xs = [_r(x0), _r(x0 + jaw_w)]
        y_fixed, y_moving = half_w, half_w - bar_w_min
        bottom = stack_tops[side]
        return [
            {
                "name": "fixed jaw",
                "x": xs,
                "y": [_r(y_fixed), _r(y_fixed + JAW_DEPTH_MM)],
                "z_top": _r(bottom + grip),
            },
            {
                "name": "moving jaw",
                "x": xs,
                "y": [_r(y_moving - JAW_DEPTH_MM), _r(y_moving)],
                "z_top": _r(bottom + grip),
            },
            {
                "name": "fixed-jaw stack",
                "x": xs,
                "y": [_r(y_fixed - t_par), _r(y_fixed)],
                "z_top": _r(bottom),
            },
            {
                "name": "moving-jaw stack",
                "x": xs,
                "y": [_r(y_moving), _r(y_moving + t_par)],
                "z_top": _r(bottom),
            },
        ]

    def band(w: Writer, e0: float, e1: float) -> dict[str, float]:
        z0, z1 = sorted((w.z(e0), w.z(e1)))
        return {"z_top": z1, "z_bottom": z0}

    def part_boxes(side: str) -> list[dict[str, Any]]:
        w = writer(side)
        boxes = []
        for name, (y0, y1) in (
            ("the tab behind the hub", (-win_back, -hub_r)),
            ("the tab past the tip", (tip_y, win_tip)),
        ):
            xs = sorted((w.xy(0.0, y0)[0], w.xy(0.0, y1)[0]))
            boxes.append(
                {
                    "name": name,
                    "x": xs,
                    "y": [-tab_w / 2, tab_w / 2],
                    **band(w, -tab_t / 2, tab_t / 2),
                }
            )
        edges = _levels(rod_r, 0.0, p["keep_out_band_mm"])
        upper = rod_r
        xs = sorted((w.xy(0.0, 0.0)[0], w.xy(0.0, tip_y)[0]))
        for e in edges:
            half = lever.rod_half(upper)
            if half > 0.0:
                boxes.append(
                    {
                        "name": f"the rod {e:.2f}-{upper:.2f} above its axis",
                        "x": xs,
                        "y": [_r(-half), _r(half)],
                        **band(w, e, upper),
                    }
                )
            upper = e
        return boxes

    def part_circles(side: str) -> list[dict[str, Any]]:
        w = writer(side)
        circles = [
            {
                "name": "the hub's wall",
                "centre": [0.0, 0.0],
                "radius": hub_r,
                **band(w, -hub_half, hub_half),
            }
        ]
        if side == "crown":
            upper = apex
            for e in _levels(apex, hub_half, p["keep_out_band_mm"]):
                rho = lever.hub_reach("crown", upper)
                if rho > 0.0:
                    circles.append(
                        {
                            "name": f"the crown {e:.2f}-{upper:.2f} past the axis",
                            "centre": [0.0, 0.0],
                            "radius": _r(rho),
                            **band(w, e, upper),
                        }
                    )
                upper = e
        return circles

    expect: list[list[Any]] = []
    for side in ("top", "crown"):
        w = writer(side)
        top = tops[side]
        prefix = f"DT16_{side}"
        rough_floor = w.z(top_floor if side == "top" else crown_floor)
        ball_prog = f"{prefix}_rod" if side == "top" else f"{prefix}_dome_rod"
        flat_shapes = {
            "boxes": fixtures(side) + part_boxes(side),
            "circles": part_circles(side),
        }
        for program, tool, rpm, radius, shapes, depth in (
            (f"{prefix}_rough", "em-quarter", rpm6, r6, flat_shapes, rough_floor),
            (
                ball_prog,
                "ball",
                rpm_b,
                rb,
                {"boxes": fixtures(side) + part_boxes(side)[:2]},
                w.z(-rb),
            ),
            (
                f"{prefix}_root",
                "em-sixteenth",
                rpm5,
                r5,
                flat_shapes,
                w.z(levels_root[-1]),
            ),
        ):
            expect += [
                [
                    program,
                    "tool_changes",
                    {"z_top": top, "tools": [tn[tool]], "loads_first": True},
                ],
                [program, "spindle", {"rpm": [[rpm]]}],
                [program, "pauses", {"z_top": top, "count": 0}],
                [program, "depth", {"z_min": depth}],
                [program, "rapids_clear", {"z_top": top}],
                [program, "air_feed", {"z_top": top}],
                [program, "keep_out", {"radius": radius, **shapes}],
            ]
        # Declared milling directions (#3590: conventional throughout). The
        # hub's contour and wall arcs, the crown's rings and the root's arcs
        # round the hub's axis, the part inside them.
        for program in (f"{prefix}_rough", f"{prefix}_root") + (
            (ball_prog,) if side == "crown" else ()
        ):
            expect.append(
                [
                    program,
                    "arcs",
                    {
                        "z_top": top,
                        "centres": [[0.0, 0.0]],
                        "part": "inside",
                        "cut": "conventional",
                    },
                ]
            )
        # The rod's tip face: the finishing passes across it, the stock on
        # the hub's side of them.
        tip_final = w.xy(0.0, tip_y + r6)[0]
        tip_raw = w.xy(0.0, tip_y + r6 + stock / 2)[0]
        expect.append(
            [
                f"{prefix}_rough",
                "side_passes",
                {
                    "axis": "X",
                    "final": tip_final,
                    "raw": tip_raw,
                    "max_step": stock,
                    "direction": 1.0 if tip_final < tip_raw else -1.0,
                    "span": 0.5,
                    "below_z": top,
                    "cut": "conventional",
                },
            ]
        )
        # The window's raster and the contour's sides along the rod, each
        # side of the rod: every pass with its steel toward Y0 (the raster's
        # lines step in from each wall, the contour has the part there),
        # stepping in from a slot along the wall to the innermost pass.
        stations = [w.xy(x, 0.0)[1] for x, _steel in lines_x]
        for e in top_levels if side == "top" else crown_levels:
            reach = lever.rod_reach(e - stock)
            if reach > 0.0:
                stations += [
                    w.xy(sign * (reach + stock + r6), 0.0)[1] for sign in (-1, 1)
                ]
        for sign in (-1.0, 1.0):
            mine = [s for s in stations if s * sign > 1e-6]
            expect.append(
                [
                    f"{prefix}_rough",
                    "side_passes",
                    {
                        "axis": "Y",
                        "final": _r(sign * min(abs(s) for s in mine)),
                        "raw": _r(sign * (max(abs(s) for s in mine) + 2 * r6)),
                        "max_step": _r(2 * r6),
                        "direction": w.along_x(sign),
                        "span": MIN_CUT_MM / 2,
                        "below_z": top,
                        "cut": "conventional",
                    },
                ]
            )
        # The tip face beside the tab (the 1/16 in end mill): its rows across
        # the face, the corner the 1/4 in end mill left on the hub's side of
        # them, each pass the same way along frame Y on both sides of the tab.
        way = w.conventional([("P", (0.0, 0.0)), ("L", (1.0, 0.0))])
        expect.append(
            [
                f"{prefix}_root",
                "side_passes",
                {
                    "axis": "X",
                    "final": w.xy(0.0, tab_rows[-1])[0],
                    "raw": w.xy(0.0, tab_raw)[0],
                    "max_step": _r(r5),
                    "direction": math.copysign(
                        1.0, w.xy(*way[-1][1])[1] - w.xy(*way[0][1])[1]
                    ),
                    "span": MIN_CUT_MM,
                    "below_z": top,
                    "cut": "conventional",
                },
            ]
        )
        # The straight passes along the rod (the ball's, the root's along the
        # rod's side), each side of it: the rod toward Y0.
        for program, stations in (
            (
                ball_prog,
                [
                    w.xy(b["x"], 0.0)[1]
                    for key in ("rod_semi", "rod_finish")
                    for b in built[f"{side}_{key}"]
                ],
            ),
            (f"{prefix}_root", [w.xy(b["x"], 0.0)[1] for b in built[f"{side}_root"]]),
        ):
            for sign in (-1.0, 1.0):
                mine = [s for s in stations if s * sign > 1e-6]
                final = sign * min(abs(s) for s in mine)
                raw = sign * (max(abs(s) for s in mine) + 1.0)
                expect.append(
                    [
                        program,
                        "side_passes",
                        {
                            "axis": "Y",
                            "final": _r(final),
                            "raw": _r(raw),
                            "max_step": _r(max(abs(s) for s in mine) + 1.0),
                            "direction": w.along_x(sign),
                            "span": 1.0,
                            "below_z": top,
                            "cut": "conventional",
                        },
                    ]
                )
    holes = "DT16_top_holes"
    expect += [
        [
            holes,
            "tool_changes",
            {
                "z_top": 0.0,
                "tools": [tn["spot"], tn["drill-f"], tn["em-hss"]],
                "loads_first": True,
            },
        ],
        [holes, "spindle", {"rpm": [[spot_rpm], [f_rpm], [hss_rpm]]}],
        [holes, "pauses", {"z_top": 0.0, "count": 0}],
        [holes, "depth", {"z_min": _r(ref_tip)}],
        [
            f"{holes}@0",
            "holes",
            {"centres": [list(bore_xy), list(ref_xy)], "z_bottom": _r(spot_z)},
        ],
        # The F drill's two holes end at two depths (check_holes takes one):
        # the reference hole is the section's deepest point, and nothing on
        # the bore's axis reaches below its drill point (a point shape, the
        # drill's point within 0.1 of it).
        [
            f"{holes}@1",
            "keep_out",
            {
                "radius": 0.1,
                "circles": [
                    {
                        "name": "the bore below its drill point",
                        "centre": list(bore_xy),
                        "radius": 0.0,
                        "z_top": _r(drill_tip),
                    }
                ],
            },
        ],
        [f"{holes}@1", "depth", {"z_min": _r(ref_tip)}],
        [f"{holes}@2", "holes", {"centres": [list(bore_xy)], "z_bottom": _r(floor_z)}],
        [f"{holes}@2", "feed_out", {"z_top": 0.0}],
        [
            f"{holes}@2",
            "arcs",
            {
                "z_top": 0.0,
                "centres": [list(bore_xy)],
                "part": "outside",
                "cut": "conventional",
            },
        ],
    ]
    for k in range(3):
        expect += [
            [f"{holes}@{k}", "rapids_clear", {"z_top": 0.0}],
            [f"{holes}@{k}", "air_feed", {"z_top": 0.0}],
            [f"{holes}@{k}", "keep_out", {"radius": d_f / 2, "boxes": fixtures("top")}],
        ]
    for k in range(2):
        expect.append([f"{holes}@{k}", "vertical_below_top", {"z_top": 0.0}])

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": frames,
        "names": names,
        "numbers": tn,
        "jobs": jobs,
        "expect": expect,
        "geometry": g,
        "cutters": {"r6": r6, "rb": rb, "r5": r5, "hss": d_hss / 2},
        "built": built,
        "levels": {
            "top": top_levels,
            "crown": crown_levels,
            "root": levels_root,
            "tip_tab": tip_tab_levels,
            "tab_free": tab_free,
        },
        "tip_tab_rows": tab_rows,
        "holes": {
            "bore": bore_xy,
            "ref": ref_xy,
            "drill_tip": drill_tip,
            "floor": floor_z,
            "floor_r": floor_r,
            "ref_tip": ref_tip,
            "spot": spot_z,
        },
    }


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    return [(program, check, kwargs) for program, check, kwargs in ctx["expect"]]


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job per
    tool and frame; returns {"ops": {operation key: operation}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(
            doc,
            f"Pinion engage lever {key}",
            ctx["step"],
            frame["origin"],
            frame["axes"],
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
            flutes=section["flutes"],
            tip_angle=section["tip_angle"],
        )
        for key, label, lines in section["ops"]:
            ops[key] = rt.custom(target, tc, label, lines)
    rt.generate(doc)
    return {"ops": ops}
