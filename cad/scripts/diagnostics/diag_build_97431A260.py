r"""McMaster 97431A260 -- side-mount (E-style) external retaining ring for a
5/32 in shaft, phosphate-coated carbon steel (MHA-VN-047, R9-68).

Laws: measured from the vendor model, read by the read-only dump
``cad/out/reports/mcmaster-97431A260-dump.json`` (amet, 2026-10-02) of
``cad/references/mcmaster/97431A260.SLDPRT``, SHA-256
dc3d0f8549d8851713aa234e24f338e9f0d41dbc96550669c281c99c3d9f4cff.  The vendor
file is local-only (© McMaster, gitignored, never committed; see
cad/references/mcmaster/README.md).  Vendor truth, pinned below as VENDOR_*:
volume 13.3124 mm^3, area 64.1486 mm^2, 26 faces.  Every value is the
vendor's own dimension or solved sketch geometry, in mm:

- outline (their Sketch1 on the Right plane, Boss-Extrude1 mid-plane by
  "Ring Thickness" 0.635): the Ø7.1628 O.D. arc, open across the gap; two
  gap lines down to the gripping circle Ø2.8956 ("Free Diameter"), whose
  three R1.4478 arcs are the prongs; and two windows between the prongs,
  each bounded by a radial line at 90 deg, the relief arc R2.595716 (their
  equation D1 = (Ring OD + Free Diameter) / 3.875) and a radial line at
  atan(1/3) off the gap's far side.
- Fillet1: R0.4445 (0.7 x thickness) on the six corners where the gap lines
  meet the O.D. and where the window lines meet the relief arc.
- Fillet2: R0.22225 on the six corners where the gap lines and the window
  lines meet the prong arcs.

Frame: ring axis +Y, origin mid-thickness, gap opening toward +X.  Their
axis is x and their gap opens toward +z, so replica (x, y, z) is vendor
(z, x, y), a cyclic (proper) map.  The replica sketches on the Top plane,
whose sketch (u, v) is model (X, -Z); that turns their Right-plane sketch
(s, t) into (u, v) = (-s, -t), a half-turn, so every vertex below is theirs
negated and every arc keeps its sense.

Run standalone (SolidWorks open, vendor file and dump local)::

    uv run python cad\scripts\diagnostics\diag_build_97431A260.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import check, name_last_feature, volume_check  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    assert_profile_closed,
    draw_closed_profile,
    replica_main,
)
from diagnostics.sketch_profile import Arc, Line, Segment  # noqa: E402
from vn_transgear_retaining_ring_spec import FREE_DIA, OD, THICKNESS  # noqa: E402

OUTER_R = OD / 2.0  # 3.5814, "Ring OD"
PRONG_R = FREE_DIA / 2.0  # 1.4478, "Free Diameter"
RELIEF_R = (OD + FREE_DIA) / 3.875  # 2.595716, their D1 (a radius)
GAP_CORNER_FILLET_R = 0.7 * THICKNESS  # 0.4445, their Fillet1
PRONG_CORNER_FILLET_R = 0.22225  # their Fillet2

# Their solved Sketch1 vertices, upper half (t > 0), in their sketch (s, t).
# Each is put back onto its own circle so arc ends weld exactly.
_GAP_OD = (-3.069212, 1.845634)  # Arc4 end / Line2 start
_GAP_PRONG = (-0.6 * PRONG_R, 0.8 * PRONG_R)  # Arc6 start: (-0.86868, 1.15824)
_WINDOW_SLOPE = 1.0 / 3.0  # Line6 runs radially at atan(1/3)

# The vendor truth this replica is gated against (the 2026-10-02 harvest).
VENDOR_VOLUME_MM3 = 13.3124
VENDOR_SURFACE_MM2 = 64.1486
VENDOR_FACE_COUNT = 26
VENDOR_COM_MM = (0.0, 0.0, -0.521572)


def _on_circle(point: tuple[float, float], radius: float) -> tuple[float, float]:
    scale = radius / math.hypot(*point)
    return (point[0] * scale, point[1] * scale)


def _vertices() -> dict[str, tuple[float, float]]:
    """Their Sketch1 corners, upper half, in their (s, t)."""
    window = (3.0 / math.sqrt(10.0), 1.0 / math.sqrt(10.0))
    if abs(window[1] / window[0] - _WINDOW_SLOPE) > 1e-12:
        raise AssertionError("window line is not at atan(1/3)")
    return {
        "gap_od": _on_circle(_GAP_OD, OUTER_R),
        "gap_prong": _on_circle(_GAP_PRONG, PRONG_R),
        "window_prong": (0.0, PRONG_R),
        "window_relief": (0.0, RELIEF_R),
        "far_relief": (RELIEF_R * window[0], RELIEF_R * window[1]),
        "far_prong": (PRONG_R * window[0], PRONG_R * window[1]),
    }


def corners() -> dict[str, tuple[float, float]]:
    """Every corner of the outline in the replica's Top sketch (u, v):
    theirs negated (a half-turn), ``_up`` for t > 0 and ``_dn`` for t < 0."""
    out = {}
    for name, (s, t) in _vertices().items():
        out[f"{name}_up"] = (-s, -t)
        out[f"{name}_dn"] = (-s, t)
    return out


def outline() -> tuple[Segment, ...]:
    """Their Sketch1 loop, half-turned; every Arc runs counter-clockwise."""
    c = corners()
    o = (0.0, 0.0)
    return (
        Arc(o, c["gap_od_dn"], c["gap_od_up"]),  # Arc4, the O.D.
        Line(c["gap_od_up"], c["gap_prong_up"]),  # Line2
        Arc(o, c["window_prong_up"], c["gap_prong_up"]),  # Arc6
        Line(c["window_prong_up"], c["window_relief_up"]),  # Line4
        Arc(o, c["far_relief_up"], c["window_relief_up"]),  # Arc9
        Line(c["far_relief_up"], c["far_prong_up"]),  # Line6
        Arc(o, c["far_prong_dn"], c["far_prong_up"]),  # Arc7
        Line(c["far_prong_dn"], c["far_relief_dn"]),  # Line5
        Arc(o, c["window_relief_dn"], c["far_relief_dn"]),  # Arc8
        Line(c["window_relief_dn"], c["window_prong_dn"]),  # Line3
        Arc(o, c["gap_prong_dn"], c["window_prong_dn"]),  # Arc5
        Line(c["gap_prong_dn"], c["gap_od_dn"]),  # Line1
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
    Fillet1's six, then Fillet2's six."""
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


def _check_truth(truth: dict | None) -> None:
    """A harvest that is not the pinned one is a different vendor file."""
    if truth is None:
        return
    mass = truth["mass"]
    faces = sum(len(body.get("faces") or []) for body in truth.get("bodies") or [])
    if (
        abs(float(mass["volume_mm3"]) - VENDOR_VOLUME_MM3) > 1e-4
        or abs(float(mass["surface_area_mm2"]) - VENDOR_SURFACE_MM2) > 1e-3
        or faces != VENDOR_FACE_COUNT
    ):
        raise RuntimeError(
            "97431A260 harvest does not match the pinned vendor truth "
            f"(volume {mass['volume_mm3']}, surface {mass['surface_area_mm2']}, "
            f"{faces} faces)"
        )


if abs(RELIEF_R - 2.595716) > 1e-6:
    raise ValueError("97431A260 relief arc no longer matches their D1")
if abs(math.hypot(*_GAP_OD) - OUTER_R) > 1e-5:
    raise ValueError("97431A260 gap corner is off the O.D.")


async def build_97431A260(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    _check_truth(truth)
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

    # Vendor (x, y, z) -> replica (z, x, y).
    adapter._mcm_com_map = lambda c: [c[2], c[0], c[1]]


if __name__ == "__main__":
    sys.exit(replica_main("97431A260", build_97431A260))
