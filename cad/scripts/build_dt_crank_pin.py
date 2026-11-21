r"""Build removable crank taper pin MHA-DT-09.

The bought No. 3 x 1-3/4 taper pin (ASME B18.8.2, McMaster-Carr 98390A254; owner
ruling 2026-11-20, #2368) secures separate hub MHA-DT-31 to crankshaft MHA-DT-11
and is removed to release the matched arm/hub assembly for gear service.  Its
brass keeper ring passes through the one shop-drilled cross-hole near the big end.

Layout: pin axis along +X from the origin (big end at x=0), profile revolved
360 degrees about a centreline on the axis.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_crank_pin.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _dimensions import drive_dimension, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _drawing_precision import apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _saved_part_guard import require_saved_drawing_properties
from dt_crank_pin_spec import (
    RING_HOLE_DIA,
    RING_HOLE_X,
    BIG_END_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    PIN_LENGTH,
    SMALL_END_DIA,
)

PART_NAME = "dt-crank-pin"
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations): length + the two end diameters. The mm
    # suffix is load-bearing (INCH document; the equation manager reads bare
    # numbers in document units).
    set_global(adapter, "PinLength", f"{PIN_LENGTH}mm")
    set_global(adapter, "RingHoleX", f"{RING_HOLE_X}mm")
    set_global(adapter, "RingHoleDia", f"{RING_HOLE_DIA}mm")
    set_global(adapter, "BigEndDia", f"{BIG_END_DIA}mm")
    set_global(adapter, "SmallEndDia", f"{SMALL_END_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch profile", adapter.create_sketch("Front"))
    # Direct-to-DB: inferencing would snap the ~0.6 deg taper line to an
    # auto "horizontal" relation, flattening the frustum into a cylinder.
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline axis",
        adapter.add_centerline(0.0, 0.0, PIN_LENGTH, 0.0),
    )
    lines = add_line_chain(
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
        adapter.add_sketch_constraint(f"{big_end}.start", "origin", "coincident"),
    )
    check(
        "axis horizontal",
        adapter.add_sketch_constraint(centerline, None, "horizontal"),
    )
    # Record each manual dim into SketchDims as it is added (creation order):
    # length, then big-end radius, then small-end radius -- three display dims.
    check(
        "pin length",
        adapter.add_sketch_dimension(centerline, None, "linear", PIN_LENGTH),
    )
    profile.record("Length", '"PinLength"')
    for label, ent, radius, name, drive in (
        ("big end", big_end, BIG_END_DIA / 2.0, "BigRadius", '"BigEndDia" / 2'),
        ("small end", small_end, SMALL_END_DIA / 2.0, "SmallRadius", '"SmallEndDia" / 2'),
    ):
        check(
            f"{label} vertical",
            adapter.add_sketch_constraint(ent, None, "vertical"),
        )
        check(
            f"{label} radius",
            adapter.add_sketch_dimension(ent, None, "linear", radius),
        )
        profile.record(name, drive)
    ensure_fully_defined(adapter, "pin profile")
    check("exit_sketch profile", adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs += profile.apply(adapter, "PinProfile")

    check(
        "revolve pin",
        adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "Pin")

    # Conical frustum: V = pi*h/3 * (R1^2 + R1*R2 + R2^2).
    r1, r2 = BIG_END_DIA / 2.0, SMALL_END_DIA / 2.0
    v_pin = math.pi * PIN_LENGTH / 3.0 * (r1 * r1 + r1 * r2 + r2 * r2)
    volume_check(adapter, "pin", v_pin, 0.005 * v_pin)

    # Keeper-ring cross-hole: a Front-plane circle at (RING_HOLE_X, 0) cut
    # mid-plane along Z clean through the head (both directions, depth well
    # past the big end). Removed ~ a cylinder through the local pin diameter.
    ring_hole = SketchDims()
    check("create_sketch ring hole", adapter.create_sketch("Front"))
    define_circle(
        adapter, RING_HOLE_X, 0.0, RING_HOLE_DIA / 2.0, "ring hole", dims=ring_hole,
        names=("RingHoleX", "RingHoleY", "RingHoleDia"),
        drives=('"RingHoleX"', None, '"RingHoleDia"'),
    )
    ensure_fully_defined(adapter, "ring hole sketch")
    check("exit_sketch ring hole", adapter.exit_sketch())
    name_last_feature(adapter, "RingHoleProfile")
    drive_jobs += ring_hole.apply(adapter, "RingHoleProfile")
    check(
        "cut ring hole",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * BIG_END_DIA, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RingHole")
    d_at_hole = BIG_END_DIA - (BIG_END_DIA - SMALL_END_DIA) * RING_HOLE_X / PIN_LENGTH
    v_ring_hole = math.pi * (RING_HOLE_DIA / 2.0) ** 2 * d_at_hole
    v_pin -= v_ring_hole
    volume_check(adapter, "pin with ring hole", v_pin, 0.1 * v_ring_hole)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        drive_dimension(adapter, dim_name, expr)
    force_rebuild(adapter)
    volume_check(adapter, "driven pin (equations neutral)", v_pin, 0.005 * v_pin)

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
        },
    )
    artefacts = save_part_and_images(adapter, PART_NAME)
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
