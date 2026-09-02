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


async def _paint_collar_brass(adapter, y_from: float) -> None:
    """Face-level bright-brass finish on the collar + cap (every face whose box
    lies at or above the collar's start ``y_from`` along the +Y axis); the
    steel stud below stays as the material renders it. Fails loud if nothing
    matched."""
    from solidworks_mcp.adapters.com_variant import double_array

    rgb = _config.palette("brass_bright")
    brass = double_array([*rgb, 1.0, 1.0, 0.5, 0.31, 0.0, 0.0])
    part_h = _early_bound(adapter.currentModel, "IPartDoc")
    n = 0
    for body in part_h.GetBodies2(0, True) or []:
        for face in _com_get(body, "GetFaces") or []:
            box = _com_get(face, "GetBox")
            if not box:
                continue
            ymin = float(box[1]) * 1000.0
            if ymin >= y_from - 1e-3:
                face.MaterialPropertyValues = brass
                n += 1
    if n < 4:
        raise RuntimeError(f"collar/cap faces not found ({n} matched)")
    _telemetry.info(f"transgear-stub: {n} collar + cap faces bright brass")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters, RevolveParameters

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
    cap_plane = check(
        "create_plane collar end",
        await adapter.create_plane(CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=end_y)),
    )
    cap = SketchDims()
    check("create_sketch cap", await adapter.create_sketch(getattr(cap_plane, "name", cap_plane)))
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
    check("cut cap slot", await adapter.create_cut_extrude(ExtrusionParameters(depth=CAP_SLOT_W, both_directions=True)))
    name_last_feature(adapter, "CapSlot")
    v_slot = CAP_DIA * CAP_SLOT_D * CAP_SLOT_W  # the slot spans the cap's full diameter
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
