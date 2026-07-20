r"""Reproduction script: crank tapered pin (book ch. 11, pp. 14-15).

The removable tapered pin that affixes the crank arm to the crankshaft —
pulled to swap the crankshaft gear. Modelled with its 1:48 frustum, turned
mushroom pull head, and transverse hole for the separate brass pull ring.

Dimensions: cad/DIMENSIONS.md "Chapter 11" — cross-hole ~Ø5 (small end);
big end and length scaled from the p.14 photo.

Layout: pin axis along +X from the origin (big end at x=0), profile
revolved 360 deg about a centerline on the axis.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pin.py
"""

from __future__ import annotations

import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    drive_dimension,
    define_circle,
    define_polygon_chain,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    POLISHED_STEEL,
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
from _saved_part_guard import require_saved_drawing_properties
from crank_pin_spec import (
    BIG_END_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    HEAD_DIA,
    HEAD_LENGTH,
    PIN_LENGTH,
    RING_HOLE_DIA,
    RING_HOLE_X,
    SMALL_END_DIA,
)

PART_NAME = "crank-pin"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): length + the two end diameters. The mm
    # suffix is load-bearing (INCH document; the equation manager reads bare
    # numbers in document units).
    await set_global(adapter, "PinLength", f"{PIN_LENGTH}mm")
    await set_global(adapter, "BigEndDia", f"{BIG_END_DIA}mm")
    await set_global(adapter, "SmallEndDia", f"{SMALL_END_DIA}mm")
    await set_global(adapter, "HeadLength", f"{HEAD_LENGTH}mm")
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "RingHoleDia", f"{RING_HOLE_DIA}mm")
    await set_global(adapter, "RingHoleOffset", f"{abs(RING_HOLE_X)}mm")

    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    # Direct-to-DB: inferencing would snap the ~0.6 deg taper line to an
    # auto "horizontal" relation, flattening the frustum into a cylinder.
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, PIN_LENGTH, 0.0),
    )
    lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (0.0, BIG_END_DIA / 2.0),
            (PIN_LENGTH, SMALL_END_DIA / 2.0),
            (PIN_LENGTH, 0.0),
        ],
    )
    set_sketch_direct_db(adapter, False)
    big_end, _taper, small_end, _axis_closure = lines
    # 8-DOF profile: the centerline merged into the (0, 0) /
    # (PIN_LENGTH, 0) chain ends, so horizontal + a length dim on it keep
    # the small end on the axis; the taper line rides its pinned
    # neighbours (no h/v on it -- that is the whole point of the frustum).
    check(
        "anchor big end",
        await adapter.add_sketch_constraint(f"{big_end}.start", "origin", "coincident"),
    )
    check(
        "axis horizontal",
        await adapter.add_sketch_constraint(centerline, None, "horizontal"),
    )
    # Record each manual dim into SketchDims as it is added (creation order):
    # length, then big-end radius, then small-end radius -- three display dims.
    check(
        "pin length",
        await adapter.add_sketch_dimension(centerline, None, "linear", PIN_LENGTH),
    )
    profile.record("Length", '"PinLength"')
    for label, ent, radius, name, drive in (
        ("big end", big_end, BIG_END_DIA / 2.0, "BigRadius", '"BigEndDia" / 2'),
        ("small end", small_end, SMALL_END_DIA / 2.0, "SmallRadius", '"SmallEndDia" / 2'),
    ):
        check(
            f"{label} vertical",
            await adapter.add_sketch_constraint(ent, None, "vertical"),
        )
        check(
            f"{label} radius",
            await adapter.add_sketch_dimension(ent, None, "linear", radius),
        )
        profile.record(name, drive)
    await ensure_fully_defined(adapter, "pin profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs += profile.apply(adapter, "PinProfile")

    check(
        "revolve pin",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "Pin")

    # The book close-up shows a turned mushroom pull head, not the bare frustum
    # the first model stopped at.  A short neck at x=0 grows into a 10 mm head;
    # the sloped shoulders approximate the worn radiused original while keeping
    # the feature fully parametric and robust as a revolve.
    head_points = [
        (0.0, 0.0),
        (-HEAD_LENGTH, 0.0),
        (-HEAD_LENGTH, 0.35 * HEAD_DIA),
        (-0.78 * HEAD_LENGTH, HEAD_DIA / 2.0),
        (-0.22 * HEAD_LENGTH, HEAD_DIA / 2.0),
        (0.0, BIG_END_DIA / 2.0),
    ]
    check("create_sketch pull head", await adapter.create_sketch("Front"))
    _head_axis = check(
        "add_centerline pull-head axis",
        await adapter.add_centerline(0.0, 0.0, -HEAD_LENGTH, 0.0),
    )
    head_lines = await add_line_chain(adapter, head_points)
    head_dims = SketchDims()
    await define_polygon_chain(
        adapter,
        head_lines,
        head_points,
        anchor=0,
        label="pull-head profile",
        dims=head_dims,
        names=[
            "HeadLength",
            "HeadEndRadius",
            "HeadShoulderRun",
            "HeadShoulderRise",
            "HeadCrownLength",
            "HeadNeckRun",
            "HeadNeckDrop",
        ],
        drives=[
            '"HeadLength"',
            '0.35 * "HeadDia"',
            '0.22 * "HeadLength"',
            '0.15 * "HeadDia"',
            '0.56 * "HeadLength"',
            '0.22 * "HeadLength"',
            '"HeadDia" / 2 - "BigEndDia" / 2',
        ],
    )
    await ensure_fully_defined(adapter, "pull-head profile")
    check("exit_sketch pull head", await adapter.exit_sketch())
    name_last_feature(adapter, "PullHeadProfile")
    drive_jobs += head_dims.apply(adapter, "PullHeadProfile")
    check(
        "revolve pull head",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "PullHead")

    # Transverse hole for the loose brass pull ring.  Front-plane normal is
    # local Z, so this cut crosses the head exactly as in the isolated pin photo.
    ring_hole = SketchDims()
    check("create_sketch ring hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        RING_HOLE_X,
        0.0,
        RING_HOLE_DIA / 2.0,
        "pull-ring hole",
        dims=ring_hole,
        names=("RingHoleOffset", "RingHoleY", "RingHoleDia"),
        drives=('"RingHoleOffset"', None, '"RingHoleDia"'),
    )
    await ensure_fully_defined(adapter, "pull-ring hole")
    check("exit_sketch ring hole", await adapter.exit_sketch())
    name_last_feature(adapter, "RingHoleProfile")
    drive_jobs += ring_hole.apply(adapter, "RingHoleProfile")
    check(
        "cut pull-ring hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=HEAD_DIA + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RingHole")

    # Capture the completed shank/head/ring-hole volume as the drive-neutrality
    # reference.  The multi-step head is deliberately checked from live geometry.
    measured = await adapter.get_mass_properties()
    if not measured.is_success:
        raise RuntimeError(f"crank-pin mass properties failed: {measured.error}")
    v_final = measured.data.volume
    await volume_check(adapter, "pin shank + pull head", v_final, 0.5)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pin (equations neutral)", v_final, 0.5)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number", "Material Specification", "Finish", "Quantity",
            "Manufacturing Notes", "End View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
    HEAD_DIA,
    HEAD_LENGTH,
