r"""Reproduction script: crank tapered pin (book ch. 11, pp. 14-15).

The removable tapered pin that affixes the crank arm to the crankshaft —
pulled to swap the crankshaft gear. Modelled as a plain conical frustum
(period taper pins run ~1:48; the photo-scaled ends here are a touch
steeper, both low confidence).

Dimensions: cad/DIMENSIONS.md "Chapter 11" — cross-hole ~Ø5 (small end);
big end and length scaled from the p.14 photo.

Layout: pin axis along +X from the origin (big end at x=0), profile
revolved 360 deg about a centerline on the axis.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pin.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
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
from _saved_part_guard import require_saved_drawing_properties
from crank_pin_spec import (
    BIG_END_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    PIN_LENGTH,
    SMALL_END_DIA,
)

PART_NAME = "crank-pin"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): length + the two end diameters. The mm
    # suffix is load-bearing (INCH document; the equation manager reads bare
    # numbers in document units).
    await set_global(adapter, "PinLength", f"{PIN_LENGTH}mm")
    await set_global(adapter, "BigEndDia", f"{BIG_END_DIA}mm")
    await set_global(adapter, "SmallEndDia", f"{SMALL_END_DIA}mm")

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

    # Conical frustum: V = pi*h/3 * (R1^2 + R1*R2 + R2^2).
    r1, r2 = BIG_END_DIA / 2.0, SMALL_END_DIA / 2.0
    v_pin = math.pi * PIN_LENGTH / 3.0 * (r1 * r1 + r1 * r2 + r2 * r2)
    await volume_check(adapter, "pin", v_pin, 0.005 * v_pin)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pin (equations neutral)", v_pin, 0.005 * v_pin)

    await apply_material(adapter, MATERIAL)
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
