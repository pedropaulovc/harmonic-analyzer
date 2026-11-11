"""Straight inclined tooth spaces, cut natively (MHA-DT-07, the 64T).

Owner ruling 2026-11-10 on #2332 (option A): the crank-drive gear's teeth
are straight, inclined to its axis, each tooth space the cutter's own form
fed in a straight line (``straight_gash`` owns the geometry). This module
authors that cut: a full-tip blank, the cutter's plane built from read-back
reference geometry, the form sketched on it by equation curves, a mid-plane
cut along the tooth line, then volume and native-flank gates and the
circular pattern. It lives beside ``_gear`` rather than in it so the shared
gear helper, which every other gear recipe keys on, is unchanged.
"""

from __future__ import annotations

import json
import math
from typing import Any

import _telemetry

from _check import check
from _com import _early_bound, _read_member
from _feature_tree import _feature_by_name, name_last_feature
from _gear import R_CLEAR_IN, ToothedDisc, equation_curve, pattern_about_z
from _part_checks import volume_check
from _paths import IN
from _sketch import ensure_fully_defined
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from stock_form_cutter import StockFormProfile
from straight_gash import StraightGash, Vector

__all__ = ["assert_straight_gash_flanks", "build_straight_gash_gear"]


def _plane_frame(adapter: Any, name: str) -> tuple[Vector, Vector]:
    """A reference plane's unit normal and one point on it (mm), read back
    from ``IRefPlane::Transform`` (build_dt_crankshaft's ``_plane_normal``:
    the third rotation row is the normal; the translation, metres in
    [9:12], is the image of the canonical plane's origin)."""
    feature = _early_bound(_feature_by_name(adapter, name), "IFeature")
    plane = _early_bound(feature.GetSpecificFeature2(), "IRefPlane")
    data = [float(v) for v in _read_member(_read_member(plane, "Transform"), "ArrayData")]
    return (data[6], data[7], data[8]), tuple(1000.0 * v for v in data[9:12])


def _delete_feature(adapter: Any, name: str, kind: str) -> None:
    """Select a feature by name and delete it (build_dt_crankshaft)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(name, kind, 0, 0, 0, False, 0, null_callout(), 0):
        raise RuntimeError(f"cannot select {name!r} for deletion")
    if not model.Extension.DeleteSelection2(0):
        raise RuntimeError(f"DeleteSelection2 refused {name!r}")
    model.ClearSelection2(True)


async def _plane_through(
    adapter: Any,
    name: str,
    *,
    base_plane: str,
    pivot_axis: str,
    angle_deg: float,
    direction: Vector,
) -> None:
    """The angled plane through ``pivot_axis`` that CONTAINS ``direction``.

    ``InsertRefPlane`` has two angled solutions per magnitude and the
    adapter's sign picks one undocumented way, so the normal is read back
    and the wrong solution deleted for its mirror (build_dt_crankshaft).
    """
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    for attempt, signed in enumerate((angle_deg, -angle_deg)):
        check(
            f"create_plane {name} ({signed:+.6f} deg about {pivot_axis})",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="angle", base_plane=base_plane, angle=signed, pivot_axis=pivot_axis
                )
            ),
        )
        name_last_feature(adapter, name)
        normal, _ = _plane_frame(adapter, name)
        off_plane = abs(sum(n * d for n, d in zip(normal, direction, strict=True)))
        _telemetry.info(f"{name}: attempt {attempt + 1} normal {normal}, |n.d| = {off_plane:.3e}")
        if off_plane < 1e-6:
            return
        _delete_feature(adapter, name, "PLANE")
    raise RuntimeError(f"{name}: neither angled-plane solution contains {direction}")


async def _crossing_plane(adapter: Any, name: str, z_mm: float) -> None:
    """Front offset to z = ``z_mm``, its side proven from the read-back
    origin rather than the adapter's undocumented offset sign."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    for attempt, offset in enumerate((z_mm, -z_mm)):
        check(
            f"create_plane {name} (Front {offset:+.6f} mm)",
            await adapter.create_plane(
                CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=offset)
            ),
        )
        name_last_feature(adapter, name)
        normal, origin = _plane_frame(adapter, name)
        station = sum(n * o for n, o in zip(normal, origin, strict=True)) * (
            1.0 if normal[2] > 0.0 else -1.0
        )
        _telemetry.info(f"{name}: attempt {attempt + 1} normal {normal}, station {station:.9f} mm")
        if abs(abs(normal[2]) - 1.0) < 1e-9 and abs(station - z_mm) < 1e-6:
            return
        _delete_feature(adapter, name, "PLANE")
    raise RuntimeError(f"{name}: no Front offset lands at z = {z_mm} mm")


def _sketch_mapper(adapter: Any, gash: StraightGash) -> tuple[Vector, Vector, Vector]:
    """The ACTIVE sketch's affine map of the gash's normal section.

    SolidWorks picks an angled plane's sketch axes, so they are read off
    ``ModelToSketchTransform`` (the _oblique_pivot_block_model mapper): the
    crossing point and both section axes must lie in the sketch plane and the
    axes must map orthonormal. Returns the crossing point's sketch (u, v) and
    the sketch images of r and n, all in mm (the axes per mm).
    """
    import pythoncom
    from win32com.client import VARIANT

    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError("tooth-space sketch: no active sketch")
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def raw(model_mm: Vector) -> Vector:
        point = math_util.CreatePoint(
            VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm])
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    origin = raw(gash.crossing_point)
    axes = []
    for label, direction in (("r", gash.radial), ("n", gash.section_tangential)):
        tip = raw(tuple(o + d for o, d in zip(gash.crossing_point, direction, strict=True)))
        axes.append(tuple(t - o for t, o in zip(tip, origin, strict=True)))
        if abs(tip[2]) > 1e-6:
            raise RuntimeError(f"tooth-space sketch: section axis {label} leaves the plane by {tip[2]:g} mm")
    if abs(origin[2]) > 1e-6:
        raise RuntimeError(f"tooth-space sketch: the crossing point is {origin[2]:g} mm off the plane")
    r_axis, n_axis = axes
    dot = r_axis[0] * n_axis[0] + r_axis[1] * n_axis[1]
    lengths = (math.hypot(*r_axis[:2]), math.hypot(*n_axis[:2]))
    if abs(dot) > 1e-9 or any(abs(length - 1.0) > 1e-9 for length in lengths):
        raise RuntimeError(f"tooth-space sketch axes are not orthonormal: {r_axis}, {n_axis}")
    _telemetry.info(f"tooth-space sketch: crossing {origin}, r -> {r_axis}, n -> {n_axis}")
    return origin, r_axis, n_axis


def _literal(value: float) -> str:
    """Fixed-point curve literal: the equation parser takes no exponents
    (farm run 20261110T210742240Z: a 3.4e-18 sketch-origin residue from
    ``.12g`` failed the first flank)."""
    return f"{round(value, 12) + 0.0:.12f}"


def _affine_expression(offset: float, along_x: float, along_y: float, x: str, y: str) -> str:
    """``offset + along_x * x + along_y * y``, dropping terms below 1e-12."""
    terms = [_literal(offset)]
    terms += [
        f"({_literal(coefficient)})*({expression})"
        for coefficient, expression in ((along_x, x), (along_y, y))
        if abs(coefficient) >= 1e-12
    ]
    return "+".join(f"({term})" if index == 0 else term for index, term in enumerate(terms))


@_telemetry.traced("gear.straight_gash")
async def build_straight_gash_gear(
    adapter: Any,
    section: StockFormProfile,
    gash: StraightGash,
    teeth: int,
    *,
    flank_bound_mm: float,
) -> ToothedDisc:
    """Cut ``teeth`` straight inclined tooth spaces into a full-tip blank.

    The cut is the shop's: ``section`` (the cutter form, straight, in its own
    plane) is sketched on the plane the cutter's centre plane is normal to,
    through the axis at ``gash.crossing_z_mm``, and extruded both ways along
    the tooth line, so each space is the exact prism and no sweep sag
    enters. The plane is built from proven read-back steps: a radial plane
    through the axis at the seed bisector, a Front offset at the crossing,
    their intersection axis, and the plane turned ``gash.inclination_deg``
    about it. One space is volume- and flank-gated, then patterned.
    """
    from solidworks_mcp.adapters.base import CreateAxisParameters, ExtrusionParameters

    if section.helix_angle_deg != 0.0:
        raise ValueError("the cutter form must be supplied in its own (straight) plane")
    if not math.isfinite(flank_bound_mm) or flank_bound_mm <= 0.0:
        raise ValueError("tooth-space flank bound must be positive and finite")
    face_width, radius = gash.face_width_mm, gash.blank_radius_mm
    removed = gash.removed_volume_mm3(section)
    blank_area = math.pi * radius**2
    if not 0.0 < teeth * removed < blank_area * face_width:
        raise ValueError("straight tooth spaces must leave positive toothed-disc material")

    check("create_sketch tooth blank", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, radius, "gear blank")
    await ensure_fully_defined(adapter, "blank sketch")
    check("exit_sketch tooth blank", await adapter.exit_sketch())
    check(
        "extrude tooth blank",
        await adapter.create_extrusion(ExtrusionParameters(depth=face_width)),
    )
    blank_volume = blank_area * face_width
    await volume_check(adapter, "blank", blank_volume, 0.005 * blank_volume)

    gear_axis = check(
        "create_axis tooth-space gear axis (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    ).name
    await _plane_through(
        adapter, "ToothSpaceRadialPlane", base_plane="Top Plane", pivot_axis=gear_axis,
        angle_deg=math.degrees(gash.azimuth_rad), direction=gash.radial,
    )
    await _crossing_plane(adapter, "ToothSpaceCrossingPlane", gash.crossing_z_mm)
    pivot = check(
        "create_axis tooth-space pivot (radial x crossing)",
        await adapter.create_axis(
            CreateAxisParameters(
                mode="two_planes", planes=["ToothSpaceRadialPlane", "ToothSpaceCrossingPlane"]
            )
        ),
    ).name
    await _plane_through(
        adapter, "ToothSpaceCutterPlane", base_plane="ToothSpaceCrossingPlane",
        pivot_axis=pivot, angle_deg=gash.inclination_deg, direction=gash.section_tangential,
    )
    blank_reference_geometry(
        adapter,
        (
            (gear_axis, "AXIS"),
            (pivot, "AXIS"),
            ("ToothSpaceRadialPlane", "PLANE"),
            ("ToothSpaceCrossingPlane", "PLANE"),
            ("ToothSpaceCutterPlane", "PLANE"),
        ),
    )

    check("create_sketch tooth space", await adapter.create_sketch("ToothSpaceCutterPlane"))
    origin, r_axis, n_axis = _sketch_mapper(adapter, gash)
    clearance = max(R_CLEAR_IN * IN, section.blank_radius_mm + 1.0)
    curves = []
    for segment in section.cut_order_native_segments(
        unit_scale=1.0 / IN, clearance_radius_mm=clearance
    ):
        x_expr, y_expr = (
            _affine_expression(o / IN, a[k], b[k], segment.x, segment.y)
            for k, o, a, b in ((0, origin[0], r_axis, n_axis), (1, origin[1], r_axis, n_axis))
        )
        curves.append(await equation_curve(adapter, segment.name, x_expr, y_expr))
    await ensure_fully_defined(
        adapter, "tooth-space sketch", fix_entities=curves, allow_fix_escalation=True
    )
    check("exit_sketch tooth space", await adapter.exit_sketch())
    name_last_feature(adapter, "ToothSpaceProfile")
    # Mid-plane: from the cutter's plane the face lies at most
    # max(crossing, face - crossing) + |Y| tan away along the tooth line.
    seed = check(
        "cut straight tooth space",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * (face_width + 2.0), both_directions=True)
        ),
    ).name
    await volume_check(adapter, "seeded tooth space", blank_volume - removed, 1.0)
    assert_straight_gash_flanks(adapter, section, gash, tolerance_mm=flank_bound_mm)
    pattern = await pattern_about_z(adapter, seed, teeth, radius, face_width / 2.0)
    expected_volume = blank_volume - teeth * removed
    volume = await volume_check(
        adapter, "toothed disc", expected_volume, 0.01 * expected_volume
    )
    return ToothedDisc(volume, (seed, str(pattern.name)))


def _flank_samples(section: Any) -> tuple[tuple[int, float, tuple[float, float]], ...]:
    """Sample the cutter form's actual finite flank, never extrapolate it."""
    low, high = section.flank_parameter_min, section.flank_parameter_max
    if high <= low:
        raise ValueError("tooth space has no active finite flank interval")
    return tuple(
        (side, parameter, section.flank_point(parameter, side=side))
        for side in (-1, 1)
        for parameter in (low + (high - low) / 4.0, low + 3.0 * (high - low) / 4.0)
    )


@_telemetry.traced("gear.straight_gash_flanks")
def assert_straight_gash_flanks(
    adapter: Any,
    section: Any,
    gash: StraightGash,
    *,
    tolerance_mm: float,
) -> None:
    """Measure the seed space's native flanks at quarter/mid/three-quarter face.

    Volume cannot tell the wrong hand, a wrong inclination or crossing, or a
    turned seed from the right one. Each flank sample (X, Y) is followed
    along the tooth line to the station and the nearest trimmed native face
    point must lie within ``tolerance_mm`` (the extrude's numerical fidelity,
    not a machining band). A wrong hand moves the three-quarter-face flank
    by 2 (z - crossing) tan(beta), about 1.7 mm.
    """
    if not math.isfinite(tolerance_mm) or tolerance_mm <= 0.0:
        raise ValueError("tooth-space flank tolerance must be positive and finite")
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"straight tooth space requires one solid body, found {len(bodies)}")
    body = _early_bound(bodies[0], "IBody2")
    faces = tuple(_early_bound(face, "IFace2") for face in (body.GetFaces() or ()))
    if not faces:
        raise RuntimeError("straight tooth space has no native faces")
    records = []
    mismatches = []
    for fraction in (0.25, 0.5, 0.75):
        z = gash.face_width_mm * fraction
        for side, parameter, (x, y) in _flank_samples(section):
            expected = gash.point(x, y, z)
            if math.hypot(expected[0], expected[1]) >= gash.blank_radius_mm:
                raise ValueError(f"flank sample u={parameter:.9g} leaves the blank at z={z:g}")
            nearest = None
            distance = math.inf
            for face in faces:
                raw = face.GetClosestPointOn(*(value / 1000.0 for value in expected))
                if raw is None or len(raw) != 5:
                    raise RuntimeError("tooth-space native closest-point query failed")
                candidate = tuple(float(value) * 1000.0 for value in raw[:3])
                if not all(math.isfinite(value) for value in candidate):
                    raise RuntimeError("tooth-space native closest point is nonfinite")
                candidate_distance = math.dist(expected, candidate)
                if candidate_distance < distance:
                    distance, nearest = candidate_distance, candidate
            records.append(
                {
                    "face_fraction": fraction,
                    "flank_side": side,
                    "flank_parameter": parameter,
                    "expected_xyz_mm": expected,
                    "native_xyz_mm": nearest,
                    "distance_mm": distance,
                }
            )
            if distance > tolerance_mm:
                mismatches.append(
                    f"z/face={fraction:g}, side={side}, u={parameter:.9g}: "
                    f"native flank distance {distance:.9g} mm"
                )
    _telemetry.info(
        "crank.straight_tooth_space_flanks "
        + json.dumps(
            {
                "inclination_deg": gash.inclination_deg,
                "crossing_z_mm": gash.crossing_z_mm,
                "azimuth_rad": gash.azimuth_rad,
                "tolerance_mm": tolerance_mm,
                "points": records,
            },
            sort_keys=True,
        )
    )
    if mismatches:
        raise RuntimeError("straight tooth-space flank mismatch: " + "; ".join(mismatches))
