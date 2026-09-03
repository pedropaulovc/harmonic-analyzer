r"""Reproduction script: transgear stud (book ch. 23, pp. 56-59, 62-63).

The stepped steel stud that plugs into the transgear bracket's bore
(build_transgear_bracket.py, on the support bar's back) and carries the
whole fixed-reduction stack: a 3/8" base section through the bracket and
the latch arm's big hub, then a turned-down O5 front seat for the 12T DP30
feed pinion + 120T disc (their bores cannot take 3/8" -- the 12T base
circle r 4.92 sits under the wall), ending in a retaining collar (the
photo's end hardware collapsed to a collar -- simplification).

Layout: axis +Y from the bracket-back end at the origin; the assembly
rotates +Y to -Z (machine front). Base y 0..9.1 (bracket + arm hub), seat
y 9.1..22.9 (feed pinion + disc), collar 22.9..26.9.
Dimensions: memory/paper-drive-rework.md E7/E8.

Dimension scheme: the three lands carry true DIAMETRIC dims (doubled
centerline-to-outline dims, ``swDiametricLinearDimension``) plus a
per-land length dim -- the machinist-facing set the manufacturing drawing
inserts as marked model items (a plain chain dim would print the radius
and the step drops, not the diameters a lathe operator works to).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_stub.py
"""

from __future__ import annotations

import math
import sys

import _config
import _telemetry
from _common import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    define_circle,
    _early_bound,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from transgear_stub_spec import (
    BASE_DIA,
    BASE_DIA_BAND,
    BASE_LEN,
    CAP_DIA,
    CAP_LEN,
    CAP_SLOT_D,
    CAP_SLOT_W,
    COLLAR_DIA,
    COLLAR_LEN,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    SEAT_DIA,
    SEAT_DIA_BAND,
    SEAT_LEN,
    SURFACE_FINISHES,
)

PART_NAME = "transgear-stub"
MATERIAL = "Plain Carbon Steel"



def _com_get(obj, name: str):
    """Zero-argument COM member that late-bound dispatch may expose as a
    method or a value (the ``'tuple' object is not callable`` trap)."""
    value = getattr(obj, name)
    return value() if callable(value) else value


def _circular_strip_area_mm2(diameter_mm: float, width_mm: float) -> float:
    """Area of a diameter-spanning strip clipped by a circular profile."""
    if not 0.0 < width_mm <= diameter_mm:
        raise ValueError("strip width must be positive and no greater than diameter")
    radius = diameter_mm / 2.0
    half_width = width_mm / 2.0
    return (
        width_mm * math.sqrt(radius**2 - half_width**2)
        + 2.0 * radius**2 * math.asin(half_width / radius)
    )


def _brass_region_from_stations(
    stations_mm: tuple[float, ...],
    collar_start_mm: float,
    cap_start_mm: float,
    *,
    tolerance_mm: float = 1e-3,
) -> str | None:
    """Classify a face from exact B-rep axial stations, never an approximate box."""
    if not stations_mm:
        return None
    first = min(stations_mm)
    if first < collar_start_mm - tolerance_mm:
        return None
    if first >= cap_start_mm - tolerance_mm:
        return "cap"
    return "collar"


def _brass_span_evidence_region(
    stations_mm: tuple[float, ...],
    collar_start_mm: float,
    cap_start_mm: float,
    cap_end_mm: float,
    *,
    tolerance_mm: float = 1e-3,
) -> str | None:
    """Return the region proved by a nonzero axial span wholly inside it."""
    if not stations_mm:
        return None
    first, last = min(stations_mm), max(stations_mm)
    if last - first <= tolerance_mm:
        return None
    if (
        first >= collar_start_mm - tolerance_mm
        and last <= cap_start_mm + tolerance_mm
    ):
        return "collar"
    if first >= cap_start_mm - tolerance_mm and last <= cap_end_mm + tolerance_mm:
        return "cap"
    return None


def _face_y_stations_mm(face) -> tuple[float, ...]:
    """Return exact Y stations from a face's analytic surface and edge topology."""
    stations: list[float] = []

    surface = face.GetSurface()
    if surface is not None:
        surface = _early_bound(surface, "ISurface")
        if surface.IsPlane():
            params = tuple(
                float(value) for value in _com_get(surface, "PlaneParams")
            )
            normal_length = math.sqrt(
                sum(component * component for component in params[:3])
            )
            if normal_length and abs(params[1] / normal_length) > 1.0 - 1e-9:
                stations.append(params[4] * 1000.0)

    for raw_edge in _com_get(face, "GetEdges") or []:
        edge = _early_bound(raw_edge, "IEdge")
        for member in ("GetStartVertex", "GetEndVertex"):
            vertex = _com_get(edge, member)
            if vertex is None:
                continue
            point = _com_get(_early_bound(vertex, "IVertex"), "GetPoint")
            stations.append(float(point[1]) * 1000.0)
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if curve.IsCircle():
            params = _com_get(curve, "CircleParams")
            stations.append(float(params[1]) * 1000.0)

    return tuple(stations)


async def _paint_collar_brass(adapter, y_from: float) -> None:
    """Apply bright brass to every collar and cap face using exact topology.

    ``IFace2.GetBox`` is deliberately unsuitable here: SolidWorks documents it
    as approximate, so its lower Y can leak below a true collar boundary and
    silently leave a face steel. Analytic plane stations plus B-rep vertices
    and circular-edge centres identify the actual axial extent instead.
    """
    from solidworks_mcp.adapters.com_variant import double_array

    rgb = _config.palette("brass_bright")
    brass = double_array([*rgb, 1.0, 1.0, 0.5, 0.31, 0.0, 0.0])
    part_h = _early_bound(adapter.currentModel, "IPartDoc")
    cap_from = y_from + COLLAR_LEN
    cap_end = cap_from + CAP_LEN
    matched = {"collar": 0, "cap": 0}
    span_evidence = {"collar": 0, "cap": 0}
    for body in part_h.GetBodies2(0, True) or []:
        for raw_face in _com_get(body, "GetFaces") or []:
            face = _early_bound(raw_face, "IFace2")
            stations = _face_y_stations_mm(face)
            if not stations:
                raise RuntimeError("face has no exact axial topology stations")
            region = _brass_region_from_stations(stations, y_from, cap_from)
            if region is None:
                continue
            face.MaterialPropertyValues = brass
            matched[region] += 1
            proof = _brass_span_evidence_region(
                stations, y_from, cap_from, cap_end
            )
            if proof is not None:
                span_evidence[proof] += 1
    for region, count in matched.items():
        if count == 0:
            raise RuntimeError(f"{region} faces not found for bright-brass finish")
        if span_evidence[region] == 0:
            raise RuntimeError(
                f"{region} has no nonzero axial-span face proving its finish region"
            )
    _telemetry.info(
        f"transgear-stub: {matched['collar']} collar + "
        f"{matched['cap']} cap faces bright brass "
        f"({span_evidence['collar']} + {span_evidence['cap']} span proofs)"
    )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the section diameters and lengths.
    # The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units (so the 3/8" base
    # is carried as its 9.525 mm value, not an unsuffixed 9.525 read as inches).
    await set_global(adapter, "BaseDia", f"{BASE_DIA}mm")
    await set_global(adapter, "BaseLen", f"{BASE_LEN}mm")
    await set_global(adapter, "SeatDia", f"{SEAT_DIA}mm")
    await set_global(adapter, "SeatLen", f"{SEAT_LEN}mm")
    await set_global(adapter, "CollarDia", f"{COLLAR_DIA}mm")
    await set_global(adapter, "CollarLen", f"{COLLAR_LEN}mm")
    await set_global(adapter, "CapDia", f"{CAP_DIA}mm")
    await set_global(adapter, "CapLen", f"{CAP_LEN}mm")
    await set_global(adapter, "CapSlotD", f"{CAP_SLOT_D}mm")

    y_seat = BASE_LEN + SEAT_LEN
    y_tip = y_seat + COLLAR_LEN
    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "axis centerline",
        await adapter.add_centerline(0.0, 0.0, 0.0, y_tip),
    )
    profile_pts = [
        (0.0, 0.0),
        (BASE_DIA / 2.0, 0.0),
        (BASE_DIA / 2.0, BASE_LEN),
        (SEAT_DIA / 2.0, BASE_LEN),
        (SEAT_DIA / 2.0, y_seat),
        (COLLAR_DIA / 2.0, y_seat),
        (COLLAR_DIA / 2.0, y_tip),
        (0.0, y_tip),
    ]
    profile_lines = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    # The centerline merged into the (0, 0)/(0, y_tip) profile corners at
    # creation, so the closed chain's own constraints define it too. Unlike
    # define_rectilinear_chain, the horizontal spans carry NO chain dims --
    # each land's outline line is pinned by its diametric dim instead, and
    # the on-axis closing segment plus closure supply the rest.
    n = len(profile_lines)
    for i, line in enumerate(profile_lines):
        (_, y1), (_, y2) = profile_pts[i], profile_pts[(i + 1) % n]
        direction = "horizontal" if y1 == y2 else "vertical"
        check(
            f"stub {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    # Land lengths (the closing on-axis segment's span is closure-supplied).
    for line, span, name, drive in (
        (profile_lines[1], BASE_LEN, "BaseLength", '"BaseLen"'),
        (profile_lines[3], SEAT_LEN, "SeatLength", '"SeatLen"'),
        (profile_lines[5], COLLAR_LEN, "CollarLength", '"CollarLen"'),
    ):
        await dimension_between(
            adapter, f"{line}.start", f"{line}.end", "vertical_distance", span,
            f"stub {name}",
        )
        profile.record(name, drive)
    # Land diameters: doubled centerline dims (value = the full diameter).
    for line, name, drive, text_y in (
        (profile_lines[1], "BaseDia", '"BaseDia"', BASE_LEN / 2.0),
        (profile_lines[3], "SeatDia", '"SeatDia"', BASE_LEN + SEAT_LEN / 2.0),
        (profile_lines[5], "CollarDia", '"CollarDia"', y_seat + COLLAR_LEN / 2.0),
    ):
        await add_diametric_linear_dimension(
            adapter, axis, line, (-8.0, text_y), name
        )
        profile.record(name, drive)
    await anchor_point_to_origin(
        adapter, f"{profile_lines[0]}.start", 0.0, 0.0, "stub anchor"
    )
    await ensure_fully_defined(adapter, "stub profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "StubProfile")
    drive_jobs = profile.apply(adapter, "StubProfile")
    check("revolve stub", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Stub")

    expected = math.pi * (
        (BASE_DIA / 2.0) ** 2 * BASE_LEN
        + (SEAT_DIA / 2.0) ** 2 * SEAT_LEN
        + (COLLAR_DIA / 2.0) ** 2 * COLLAR_LEN
    )
    await volume_check(adapter, "stub", expected, 0.005 * expected)

    # Slotted cap screw on the collar face (ch23 p.59): a CAP_DIA x CAP_LEN boss
    # on a plane at the collar's end, then a CAP_SLOT_W x CAP_SLOT_D slot cut
    # across its face (Front-plane rectangle, mid-plane cut along Z).
    end_y = BASE_LEN + SEAT_LEN + COLLAR_LEN
    check(
        "create_plane collar end",
        await adapter.create_plane(CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=end_y)),
    )
    name_last_feature(adapter, "CapPlane")
    drive_jobs.append(("D1@CapPlane", '"BaseLen" + "SeatLen" + "CollarLen"'))
    cap = SketchDims()
    check("create_sketch cap", await adapter.create_sketch("CapPlane"))
    await define_circle(
        adapter, 0.0, 0.0, CAP_DIA / 2.0, "cap", dims=cap,
        names=("CapCx", "CapCz", "CapDia"), drives=(None, None, '"CapDia"'),
    )
    await ensure_fully_defined(adapter, "cap sketch")
    check("exit_sketch cap", await adapter.exit_sketch())
    name_last_feature(adapter, "CapProfile")
    drive_jobs += cap.apply(adapter, "CapProfile")
    check("extrude cap", await adapter.create_extrusion(ExtrusionParameters(depth=CAP_LEN)))
    name_last_feature(adapter, "Cap")
    drive_jobs.append(("D1@Cap", '"CapLen"'))
    v_cap = math.pi * (CAP_DIA / 2.0) ** 2 * CAP_LEN
    got = await volume_check(adapter, "stub + cap", expected + v_cap, 0.02 * v_cap + 0.005 * expected)
    if got < expected + 0.5 * v_cap:
        raise RuntimeError("cap extruded the wrong way (into the collar) -- flip the extrude")
    slot = SketchDims()
    check("create_sketch cap slot", await adapter.create_sketch("Front"))
    slot_rect = [
        (-CAP_DIA / 2.0, end_y + CAP_LEN - CAP_SLOT_D),
        (CAP_DIA / 2.0, end_y + CAP_LEN - CAP_SLOT_D),
        (CAP_DIA / 2.0, end_y + CAP_LEN),
        (-CAP_DIA / 2.0, end_y + CAP_LEN),
    ]
    slot_lines = await add_line_chain(adapter, slot_rect)
    bottom, right, top, left = slot_lines
    for label, ent, relation in (
        ("slot bottom", bottom, "horizontal"), ("slot right", right, "vertical"),
        ("slot top", top, "horizontal"), ("slot left", left, "vertical"),
    ):
        check(f"{label} {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    check("slot span", await adapter.add_sketch_dimension(bottom, None, "linear", CAP_DIA))
    slot.record("SlotSpan", '"CapDia"')
    check("slot depth", await adapter.add_sketch_dimension(right, None, "linear", CAP_SLOT_D))
    slot.record("SlotDepth", '"CapSlotD"')
    check("slot x0", await adapter.add_sketch_dimension(f"{bottom}.start", "origin", "horizontal_distance", CAP_DIA / 2.0))
    slot.record("SlotX0", '"CapDia" / 2')
    check("slot y0", await adapter.add_sketch_dimension(f"{bottom}.start", "origin", "vertical_distance", end_y + CAP_LEN - CAP_SLOT_D))
    slot.record("SlotY0", '"BaseLen" + "SeatLen" + "CollarLen" + "CapLen" - "CapSlotD"')
    await ensure_fully_defined(adapter, "cap slot sketch")
    check("exit_sketch cap slot", await adapter.exit_sketch())
    name_last_feature(adapter, "CapSlotProfile")
    drive_jobs += slot.apply(adapter, "CapSlotProfile")
    before_slot = check(
        "measure volume before cap slot", await adapter.get_mass_properties()
    ).volume
    check("cut cap slot", await adapter.create_cut_extrude(ExtrusionParameters(depth=CAP_SLOT_W, both_directions=True)))
    after_slot = check(
        "measure volume after cap slot", await adapter.get_mass_properties()
    ).volume
    name_last_feature(adapter, "CapSlot")
    v_slot = _circular_strip_area_mm2(CAP_DIA, CAP_SLOT_W) * CAP_SLOT_D
    removed_slot = before_slot - after_slot
    if abs(removed_slot - v_slot) > 0.02 * v_slot:
        raise RuntimeError(
            f"cap slot removed {removed_slot:.3f} mm^3, expected {v_slot:.3f} mm^3"
        )
    _telemetry.success(
        f"cap slot removed {removed_slot:.3f} mm^3 (analytic {v_slot:.3f})"
    )
    expected = expected + v_cap - v_slot
    await volume_check(adapter, "stub + slotted cap", expected, 0.02 * v_cap + 0.005 * expected)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven stub (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await _paint_collar_brass(adapter, BASE_LEN + SEAT_LEN)
    await report_mass_properties(adapter)
    # Tolerance the MODEL dimensions, not the sheet text. SolidWorks renders
    # and re-renders these; a callout override on the drawing would be a frozen
    # string beside a live numeral. `deviations` fixes the (upper, lower) ->
    # (lower, upper) transposition at one chokepoint.
    set_dimension_bilateral_tolerance(
        adapter, "StubProfile", "BaseDia", *deviations(BASE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "StubProfile", "SeatDia", *deviations(SEAT_DIA_BAND)
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # GD&T lives on the MODEL as plain annotations; the drawing imports it.
    author_part_pmi(
        adapter,
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        surface_finishes=SURFACE_FINISHES,
    )
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
