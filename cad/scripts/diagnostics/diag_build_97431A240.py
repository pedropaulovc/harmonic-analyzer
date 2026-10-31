r"""McMaster 97431A240 -- side-mount (E-style) external retaining ring for a
1/8 in shaft, phosphate-coated carbon steel (MHA-PD-VN-61, R9-68).

Catalogue-only: the live page (https://www.mcmaster.com/97431A240/, read
2026-10-31) gives the ring O.D. 0.230 in and thickness 0.015 in, and its 2-D
drawing (97431A240 X.GIF, SHA-256
439a4768c3d8a643a51fb30e74de18dfb79313963d196b126cc9130fb1643206) the
0.094 in free diameter across the prongs.  The CAD download was refused
(HTTP 403), so there is no vendor model and no replica gate.

The outline is the 97431A260 harvest's law (amet, 2026-10-02, SHA-256
dc3d0f8549d8851713aa234e24f338e9f0d41dbc96550669c281c99c3d9f4cff, the
replica that passed its gate before #290 retired that ring), set on this
ring's catalogue circles.  Measured on the 97431A240 drawing (1582 px/in) it
holds: the relief arc's radius is (Ring OD + Free Diameter) / 3.875
(0.0836 in), the window lines run radially at 90 deg and atan(1/3) off the
far prong's axis, the gap's prong corners lie at 126.9 deg on the free
circle, and the gap lines rise at the harvest's slope (0.312 against its
0.3124) to the O.D. at 148.8 deg.  The two fillet radii keep the harvest's
proportions to the thickness (0.7 and 0.35) [INFERENCE: below the drawing's
resolution].

- outline (sketched like the vendor's Sketch1, extruded mid-plane by the
  thickness): the O.D. arc, open across the gap; two gap lines down to the
  gripping circle Ø FREE_DIA, whose three arcs are the prongs; and two
  windows between the prongs, each bounded by a radial line at 90 deg, the
  relief arc and a radial line at atan(1/3) off the gap's far side.
- gap fillets: 0.7 x thickness on the six corners where the gap lines meet
  the O.D. and where the window lines meet the relief arc.
- prong fillets: 0.35 x thickness on the six corners where the gap lines
  and the window lines meet the prong arcs.

Frame: ring axis +Y, origin mid-thickness, gap opening toward +X.  The
recipe sketches on the Top plane, whose sketch (u, v) is model (X, -Z); the
vendor-style (s, t) outline, gap toward -s, is half-turned into it:
(u, v) = (-s, -t), so every vertex below is negated and every arc keeps its
sense.
"""

from __future__ import annotations

import math

from _check import check
from _feature_tree import name_last_feature
from _part_checks import volume_check
from _stock_recipe import stock_recipe
from diagnostics.diag_mcmaster_lib import assert_profile_closed, draw_closed_profile
from diagnostics.sketch_profile import Arc, Line, Segment
from pd_vn_transgear_retaining_ring_spec import FREE_DIA, OD, THICKNESS

OUTER_R = OD / 2.0  # 2.921, "Ring OD"
PRONG_R = FREE_DIA / 2.0  # 1.1938, "Free Diameter"
RELIEF_R = (OD + FREE_DIA) / 3.875  # 2.123768, the relief arc (a radius)
GAP_CORNER_FILLET_R = 0.7 * THICKNESS  # 0.2667
PRONG_CORNER_FILLET_R = 0.35 * THICKNESS  # 0.13335

# The gap line rises from its prong corner toward the O.D. at the 97431A260
# harvest's slope: its solved vertices (-0.86868, 1.15824) on the free circle
# and (-3.069212, 1.845634) on the O.D.
_GAP_SLOPE = (1.845634 - 1.15824) / (0.86868 - 3.069212)  # dt/ds, -0.312377
_WINDOW_SLOPE = 1.0 / 3.0  # the far window line runs radially at atan(1/3)


def _gap_od() -> tuple[float, float]:
    """The gap line from its prong corner out to the O.D. circle, t > 0."""
    s0, t0 = -0.6 * PRONG_R, 0.8 * PRONG_R
    # (s0 + k, t0 + _GAP_SLOPE k) on the O.D., k < 0 (outward along -s).
    a = 1.0 + _GAP_SLOPE**2
    b = 2.0 * (s0 + t0 * _GAP_SLOPE)
    c = s0**2 + t0**2 - OUTER_R**2
    k = (-b - math.sqrt(b * b - 4.0 * a * c)) / (2.0 * a)
    return (s0 + k, t0 + _GAP_SLOPE * k)


def _vertices() -> dict[str, tuple[float, float]]:
    """The outline's corners, upper half (t > 0), vendor-style (s, t)."""
    window = (3.0 / math.sqrt(10.0), 1.0 / math.sqrt(10.0))
    if abs(window[1] / window[0] - _WINDOW_SLOPE) > 1e-12:
        raise AssertionError("window line is not at atan(1/3)")
    return {
        "gap_od": _gap_od(),
        "gap_prong": (-0.6 * PRONG_R, 0.8 * PRONG_R),
        "window_prong": (0.0, PRONG_R),
        "window_relief": (0.0, RELIEF_R),
        "far_relief": (RELIEF_R * window[0], RELIEF_R * window[1]),
        "far_prong": (PRONG_R * window[0], PRONG_R * window[1]),
    }


def corners() -> dict[str, tuple[float, float]]:
    """Every corner of the outline in the recipe's Top sketch (u, v):
    (s, t) negated (a half-turn), ``_up`` for t > 0 and ``_dn`` for t < 0."""
    out = {}
    for name, (s, t) in _vertices().items():
        out[f"{name}_up"] = (-s, -t)
        out[f"{name}_dn"] = (-s, t)
    return out


def outline() -> tuple[Segment, ...]:
    """The ring's loop, half-turned; every Arc runs counter-clockwise."""
    c = corners()
    o = (0.0, 0.0)
    return (
        Arc(o, c["gap_od_dn"], c["gap_od_up"]),  # the O.D.
        Line(c["gap_od_up"], c["gap_prong_up"]),
        Arc(o, c["window_prong_up"], c["gap_prong_up"]),
        Line(c["window_prong_up"], c["window_relief_up"]),
        Arc(o, c["far_relief_up"], c["window_relief_up"]),
        Line(c["far_relief_up"], c["far_prong_up"]),
        Arc(o, c["far_prong_dn"], c["far_prong_up"]),
        Line(c["far_prong_dn"], c["far_relief_dn"]),
        Arc(o, c["window_relief_dn"], c["far_relief_dn"]),
        Line(c["window_relief_dn"], c["window_prong_dn"]),
        Arc(o, c["gap_prong_dn"], c["window_prong_dn"]),
        Line(c["gap_prong_dn"], c["gap_od_dn"]),
    )


def outline_area() -> float:
    """Green's theorem round the loop; every arc is centred on the origin."""
    segments = outline()
    point = segments[0].start
    twice = 0.0
    for segment in segments:
        forward = segment.start == point
        a, b = (segment.start, segment.end) if forward else (segment.end, segment.start)
        if a != point:
            raise AssertionError(f"outline does not chain at {point}")
        if isinstance(segment, Line):
            twice += a[0] * b[1] - a[1] * b[0]
        else:
            r = math.hypot(*segment.start)
            sweep = (
                math.atan2(segment.end[1], segment.end[0])
                - math.atan2(segment.start[1], segment.start[0])
            ) % (2.0 * math.pi)
            twice += r * r * (sweep if forward else -sweep)
        point = b
    return abs(twice) / 2.0


def fillet_edge_points() -> tuple[list[list[float]], list[list[float]]]:
    """Mid-thickness points on the corner edges, model (X, 0, Z) = (u, 0, -v):
    the gap fillets' six, then the prong fillets' six."""
    c = corners()

    def edges(names: tuple[str, ...]) -> list[list[float]]:
        return [
            [c[f"{n}_{side}"][0], 0.0, -c[f"{n}_{side}"][1]]
            for n in names
            for side in ("up", "dn")
        ]

    return (
        edges(("gap_od", "window_relief", "far_relief")),
        edges(("gap_prong", "window_prong", "far_prong")),
    )


@stock_recipe("97431A240", threaded=False)
async def build_97431A240(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch outline", await adapter.create_sketch("Top"))
    await draw_closed_profile(adapter, outline(), label="ring outline", loops=1)
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "RingOutline")
    assert_profile_closed(adapter, "ring outline", loops=1, feature="RingOutline")
    check(
        "extrude ring",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RingBody")
    v = outline_area() * THICKNESS
    await volume_check(adapter, "ring outline", v, 0.005 * v)

    gap_edges, prong_edges = fillet_edge_points()
    check(
        "gap and window fillets",
        await adapter.add_fillet(GAP_CORNER_FILLET_R, gap_edges),
    )
    name_last_feature(adapter, "GapFillet")
    check(
        "prong fillets",
        await adapter.add_fillet(PRONG_CORNER_FILLET_R, prong_edges),
    )
    name_last_feature(adapter, "ProngFillet")
