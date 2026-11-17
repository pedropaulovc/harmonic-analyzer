r"""Mitee-Bite 26000 -- Pitbull edge clamp, tool steel, knife edge, with its #4-40 x 3/8 SHCS.

Used as ch-rocker-strap-tl-vn-edge-clamp (MHA-CH-13-TL-VN-50), the four
clamps that hold the strap blank's edge on the sub-plate (owner,
2026-11-17).  Geometry, frame and catalogue facts are
``ch_rocker_strap_tl_vn_edge_clamp_spec``'s (from Mitee-Bite's 26000.STEP,
probed headless).

Authored directly in the part frame (screw axis +Z, z = 0 the heel line,
knife toward +Y), so the production build applies no transform.  Every
sketch point is given in model millimetres and mapped through its sketch's
own ``ModelToSketchTransform``: no plane's sketch-axis convention is
assumed, and a point that does not lie in the sketch plane fails the build
(which also proves each offset plane's side).

1. ClampProfile on the Right Plane: the side profile's lines and arcs,
   extruded mid-plane across the clamp's width -> ClampBody.
2. CounterboreProfile on a plane clear above the clamp: the slotted
   counterbore's obround, cut mid-plane down to its floor (the half above
   is air) -> Counterbore.
3. ScrewSlotProfile on the Front Plane: the through slot's obround, cut
   through all both ways -> ScrewSlot (above the floor it lies inside the
   counterbore).
4. ScrewProfile on the Right Plane: the screw's half profile about the Z
   axis, revolved as a SEPARATE body (no merge: its head sits on the
   counterbore floor) -> Screw.
5. ScrewSocketProfile on a plane at the head top: the 3/32 hex, cut
   mid-plane (the half above lies in the counterbore's air) -> ScrewSocket.

The vendor model is not committed (Mitee-Bite's CAD download), so there is
no replica gate: the standalone run is catalog-only.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_26000.py
"""

from __future__ import annotations

import math
import sys
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

if __package__:
    from . import _script_paths  # noqa: F401
else:
    import _script_paths  # noqa: F401
from _check import check  # noqa: E402
from _com import _early_bound  # noqa: E402
from _feature_tree import name_last_feature  # noqa: E402
from _part_checks import volume_check  # noqa: E402
from _sketch import set_sketch_direct_db  # noqa: E402
import ch_rocker_strap_tl_vn_edge_clamp_spec as spec  # noqa: E402
from diagnostics.diag_mcmaster_lib import no_sketch_inference, offset_plane  # noqa: E402

PART_NO = spec.SKU
_V_TOL = 0.005
_IN_PLANE_MM = 1e-6

type Point3 = tuple[float, float, float]


def _sketch_uv(adapter, point: Point3) -> tuple[float, float]:
    """The active sketch's (u, v), mm, of a model point in mm; the point must
    lie in the sketch plane."""
    from solidworks_mcp.adapters.com_variant import double_array

    sketch = _early_bound(adapter.currentModel.SketchManager.ActiveSketch, "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    raw = _early_bound(
        utility.CreatePoint(double_array([value / 1000.0 for value in point])),
        "IMathPoint",
    )
    moved = _early_bound(raw.MultiplyTransform(transform), "IMathPoint")
    u, v, w = (float(value) * 1000.0 for value in moved.ArrayData)
    if not all(map(math.isfinite, (u, v, w))) or abs(w) > _IN_PLANE_MM:
        raise RuntimeError(
            f"{PART_NO}: model point {point} is off the sketch plane ({w} mm)"
        )
    return u, v


def _draw(adapter, segments: Sequence[tuple], to_model) -> None:
    """Lines and arcs given in a 2-D frame that ``to_model`` lifts to model
    mm. An ``arc`` is its minor arc; an ``arc_ccw`` runs counter-clockwise
    in the 2-D frame (a semicircle). Each arc is laid counter-clockwise in
    its sketch, whichever way the sketch's axes map onto the 2-D frame."""

    def uv(point):
        return _sketch_uv(adapter, to_model(point))

    o, x, y = uv((0.0, 0.0)), uv((1.0, 0.0)), uv((0.0, 1.0))
    mirrored = (x[0] - o[0]) * (y[1] - o[1]) - (x[1] - o[1]) * (y[0] - o[0]) < 0.0
    set_sketch_direct_db(adapter, True)
    try:
        for kind, *points in segments:
            if kind == "line":
                (u1, v1), (u2, v2) = uv(points[0]), uv(points[1])
                check(f"{PART_NO} line", adapter.add_line(u1, v1, u2, v2))
                continue
            c, p, q = points
            if kind == "arc":
                turn = (p[0] - c[0]) * (q[1] - c[1]) - (p[1] - c[1]) * (q[0] - c[0])
                if abs(turn) < 1e-9:
                    raise ValueError(f"{PART_NO}: a semicircle must be an arc_ccw")
                counter_clockwise = turn > 0.0
            elif kind == "arc_ccw":
                counter_clockwise = True
            else:
                raise ValueError(f"{PART_NO}: unknown segment {kind!r}")
            start, end = (p, q) if counter_clockwise != mirrored else (q, p)
            (cu, cv), (su, sv), (eu, ev) = uv(c), uv(start), uv(end)
            check(f"{PART_NO} arc", adapter.add_arc(cu, cv, su, sv, eu, ev))
    finally:
        set_sketch_direct_db(adapter, False)


def _polygon(points: Sequence[tuple[float, float]]) -> tuple[tuple, ...]:
    return tuple(
        ("line", a, b) for a, b in zip(points, (*points[1:], points[0]), strict=True)
    )


def obround(dia: float) -> tuple[tuple, ...]:
    """A slot of ``dia`` from the screw axis SLOT_TRAVEL toward the heel,
    part (X, Y); its caps are semicircles, counter-clockwise in (X, Y)."""
    r = dia / 2.0
    t = spec.SLOT_TRAVEL
    return (
        ("arc_ccw", (0.0, 0.0), (r, 0.0), (-r, 0.0)),
        ("line", (-r, 0.0), (-r, -t)),
        ("arc_ccw", (0.0, -t), (-r, -t), (r, -t)),
        ("line", (r, -t), (r, 0.0)),
    )


def _side(point: tuple[float, float]) -> Point3:
    """Part (Y, Z) on the X = 0 (Right) plane."""
    return 0.0, point[0], point[1]


def _plan(z: float):
    def lift(point: tuple[float, float]) -> Point3:
        return point[0], point[1], z

    return lift


@stock_recipe("26000", threaded=False)
def build_26000(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    # 1. Body: the side profile across the width.
    check("create_sketch clamp profile", adapter.create_sketch("Right"))
    with no_sketch_inference(adapter):
        _draw(adapter, spec.PROFILE, _side)
    check("exit_sketch clamp profile", adapter.exit_sketch())
    name_last_feature(adapter, spec.BODY_SKETCH)
    check(
        "extrude clamp body",
        adapter.create_extrusion(
            ExtrusionParameters(depth=spec.WIDTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, spec.BODY_FEATURE)
    volume = spec.V_EXTRUDED
    volume_check(adapter, "clamp body", volume, _V_TOL * volume)

    # 2. Slotted counterbore, down to its floor.
    offset_plane(
        adapter, spec.COUNTERBORE_PLANE, spec.COUNTERBORE_SKETCH_Z, base="Front Plane"
    )
    check("create_sketch counterbore", adapter.create_sketch(spec.COUNTERBORE_PLANE))
    with no_sketch_inference(adapter):
        _draw(adapter, obround(spec.COUNTERBORE_DIA), _plan(spec.COUNTERBORE_SKETCH_Z))
    check("exit_sketch counterbore", adapter.exit_sketch())
    name_last_feature(adapter, spec.COUNTERBORE_SKETCH)
    check(
        "cut counterbore",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=spec.COUNTERBORE_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, spec.COUNTERBORE_FEATURE)
    volume -= spec.V_COUNTERBORE
    volume_check(adapter, "clamp counterbore", volume, _V_TOL * volume)

    # 3. Through slot.
    check("create_sketch screw slot", adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        _draw(adapter, obround(spec.THROUGH_SLOT_DIA), _plan(0.0))
    check("exit_sketch screw slot", adapter.exit_sketch())
    name_last_feature(adapter, spec.THROUGH_SLOT_SKETCH)
    # Blind both ways past the body's full height: FeatureCut3 refuses
    # ThroughAll in both directions ("Type mismatch", farm
    # 20261117T234245842Z); the counterbore's blind both-way cut is proven.
    check(
        "cut screw slot",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * spec.TOP_Z, both_directions=True)
        ),
    )
    name_last_feature(adapter, spec.THROUGH_SLOT_FEATURE)
    volume -= spec.V_THROUGH_SLOT
    volume_check(adapter, "clamp through slot", volume, _V_TOL * volume)

    # 4. The screw, its own body.
    profile = spec.screw_profile()
    check("create_sketch screw", adapter.create_sketch("Right"))
    with no_sketch_inference(adapter):
        top = _sketch_uv(adapter, (0.0, 0.0, spec.SCREW_HEAD_TOP_Z))
        tip = _sketch_uv(adapter, (0.0, 0.0, spec.SCREW_TIP_Z))
        check("screw axis", adapter.add_centerline(top[0], top[1], tip[0], tip[1]))
        # The half profile (radius, Z) lies toward +Y, radius as part Y.
        _draw(adapter, _polygon(profile), _side)
    check("exit_sketch screw", adapter.exit_sketch())
    name_last_feature(adapter, spec.SCREW_SKETCH)
    check(
        "revolve screw",
        adapter.create_revolve(RevolveParameters(angle=360.0, merge_result=False)),
    )
    name_last_feature(adapter, spec.SCREW_FEATURE)
    volume += spec.screw_revolved_volume()
    volume_check(adapter, "clamp with screw", volume, _V_TOL * volume)

    # 5. The screw's hex socket.
    offset_plane(adapter, spec.SOCKET_PLANE, spec.SCREW_HEAD_TOP_Z, base="Front Plane")
    check("create_sketch screw socket", adapter.create_sketch(spec.SOCKET_PLANE))
    with no_sketch_inference(adapter):
        _draw(adapter, _polygon(spec.socket_hexagon()), _plan(spec.SCREW_HEAD_TOP_Z))
    check("exit_sketch screw socket", adapter.exit_sketch())
    name_last_feature(adapter, spec.SOCKET_SKETCH)
    check(
        "cut screw socket",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=spec.SCREW_SOCKET_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, spec.SOCKET_FEATURE)
    volume_check(adapter, "clamp and screw", spec.V_TOTAL, _V_TOL * spec.V_TOTAL)
    _assert_two_bodies(adapter)


def _assert_two_bodies(adapter) -> None:
    """The clamp body and its screw stay separate solids."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = part.GetBodies2(0, False)  # swSolidBody, include hidden
    count = (
        0 if bodies is None else len(bodies) if isinstance(bodies, (list, tuple)) else 1
    )
    if count != 2:
        raise RuntimeError(
            f"{PART_NO}: expected the clamp body and its screw, found {count} bodies"
        )


def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    import _telemetry
    from diagnostics.diag_mcmaster_lib import (
        OUT_DIR,
        assert_seat_sketch_baseline,
        close_all,
        export_views,
        mass_properties,
    )

    with _telemetry.span("catalog.build", label=PART_NO):
        check(f"create_part {PART_NO}", adapter.create_part())
        assert_seat_sketch_baseline(adapter, PART_NO)
        build_26000(adapter)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError(f"{PART_NO} catalog build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"{PART_NO}-catalog.SLDPRT"
        check(f"save -> {path}", adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(export_views(adapter, f"{PART_NO}-catalog"))
        _telemetry.success(
            f"{PART_NO} catalog build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        close_all(adapter)
    return artefacts


if __name__ == "__main__":
    from _session import run_build  # noqa: E402 -- diagnostic path bootstrap

    sys.exit(run_build(build_catalog))
