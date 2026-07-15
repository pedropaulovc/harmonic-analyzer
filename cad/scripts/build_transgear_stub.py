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
from typing import Any

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
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from transgear_stub_spec import (
    BASE_DIA,
    BASE_LEN,
    COLLAR_DIA,
    COLLAR_LEN,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    SEAT_DIA,
    SEAT_LEN,
)

PART_NAME = "transgear-stub"
MATERIAL = "Plain Carbon Steel"


@_telemetry.traced("dim.diametric", label_param="label")
async def _diametric_dim(
    adapter: Any, centerline: str, line: str, text_xy: tuple[float, float], label: str
) -> None:
    """Driving doubled (diameter) dim between the revolve centerline and one
    outline line (``swDiametricLinearDimension``). ``text_xy`` in sketch mm."""
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [centerline, line], 0)
    ext = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    # Early-bound out param: returns (IDisplayDimension, swAddSpecificDimension_e).
    display, status = ext.AddSpecificDimension(
        text_xy[0] / 1000.0, text_xy[1] / 1000.0, 0.0, 15, 0
    )  # 15 = swDimensionType_e.swDiametricLinearDimension
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"{label}: AddSpecificDimension(diametric) failed ({status})")
    _telemetry.success(f"diametric dim {label}")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

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
        (x1, y1), (x2, y2) = profile_pts[i], profile_pts[(i + 1) % n]
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
        await _diametric_dim(adapter, axis, line, (-8.0, text_y), name)
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

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven stub (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
