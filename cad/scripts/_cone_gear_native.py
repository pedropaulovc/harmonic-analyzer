"""Native cone-gear authoring shared by the family builder (MHA-DT-03) and the
tip gear's (MHA-DT-37): the tooth-gap equation segments and the
construction-only inspection witnesses each part prints.

A builder never imports another builder (test_buildgraph); both read these
here, so the T006 leaves are authored exactly as the family's teeth.
"""

from __future__ import annotations

import math
from typing import Any

import _telemetry
from _check import check
from _com import _early_bound
from _cone_gear_geometry import R_CLEAR_MM
from _drawing_dimension_insert import add_diametric_linear_dimension
from _feature_tree import name_last_feature
from _sketch import (
    SketchDims,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from dt_cone_gear_notes import BLANK_DIA_REFERENCE_SKETCH
from dt_cone_gear_spec import (
    DEFAULT_TEETH,
    DIAMETRAL_PITCH,
    FACE_WIDTH,
    MM_PER_IN,
    floor_radius_min_mm,
    stock_form_profile,
)

# Sketch-only length of the tip-diameter witness stub: short, because the side
# view shows the sketch, and on T012 (6:1) the stub stands just off the
# silhouette.
_BLANK_WITNESS_STUB_MM = 0.25


def native_gap_segments(teeth: int) -> tuple[tuple[str, str, str], ...]:
    """Rotate the canonical core gap by pi/N, in main's cut_tooth_gap order."""
    phase = math.pi / teeth
    cosine, sine = f"{math.cos(phase):.17g}", f"{math.sin(phase):.17g}"
    return tuple(
        (
            segment.name,
            f"({cosine})*({segment.x})-({sine})*({segment.y})",
            f"({sine})*({segment.x})+({cosine})*({segment.y})",
        )
        for segment in stock_form_profile(teeth).cut_order_native_segments(
            unit_scale=1.0 / MM_PER_IN, clearance_radius_mm=R_CLEAR_MM
        )
    )


def _as_construction(adapter: Any, entity_id: str) -> None:
    """Make a registered sketch line construction-only and prove the flag."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _author_tooth_thickness_reference(
    adapter: Any, teeth: int = DEFAULT_TEETH
) -> SketchDims:
    """Author the native circular-thickness acceptance scale on the +X tooth.

    Its value is the actual installed cutter's pitch-circle arc thickness.
    The construction length is an inspection witness, not a chord oracle or a
    controlling flank equation. The solid remains the finite core curves.
    The sketch is seeded at ``teeth`` and driven by the "ToothCount", "DP"
    and "ToothThickness" globals (MHA-DT-37 authors its T006 one the same).
    """
    tooth_reference = SketchDims()
    thickness_mm = stock_form_profile(teeth).pitch_tooth_thickness_mm
    check(
        "create_sketch tooth-thickness reference",
        await adapter.create_sketch("Front"),
    )
    pitch_radius_mm = teeth / DIAMETRAL_PITCH * MM_PER_IN / 2.0
    set_sketch_direct_db(adapter, True)
    tooth_line = check(
        "tooth-thickness reference line",
        await adapter.add_line(
            pitch_radius_mm,
            -thickness_mm / 2.0,
            pitch_radius_mm,
            thickness_mm / 2.0,
        ),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, tooth_line)
    check(
        "tooth-thickness reference vertical",
        await adapter.add_sketch_constraint(tooth_line, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{tooth_line}.start",
        "origin",
        "horizontal_distance",
        pitch_radius_mm,
        "tooth-thickness pitch radius",
    )
    tooth_reference.record(
        "ToothPitchRadius",
        '"ToothCount" / "DP" / 2',
    )
    await dimension_between(
        adapter,
        f"{tooth_line}.start",
        "origin",
        "vertical_distance",
        thickness_mm / 2.0,
        "tooth-thickness chord centred on the X axis",
    )
    tooth_reference.record("ToothHalfThickness", '"ToothThickness" / 2')
    await dimension_between(
        adapter,
        f"{tooth_line}.start",
        f"{tooth_line}.end",
        "vertical_distance",
        thickness_mm,
        "circular tooth thickness",
    )
    tooth_reference.record("ToothThickness", '"ToothThickness"')
    await ensure_fully_defined(adapter, "tooth-thickness reference sketch")
    check(
        "exit_sketch tooth-thickness reference",
        await adapter.exit_sketch(),
    )
    return tooth_reference


async def _author_gap_floor_reference(
    adapter: Any, teeth: int = DEFAULT_TEETH
) -> SketchDims:
    """Author the model-owned gap-floor dimension: a construction circle at the
    modelled floor, its diameter driven by the configuration-scoped FloorDia.

    The translated cutter root is an off-centre arc. This origin-centred
    witness carries its minimum radial envelope and the permitted functional
    MIN/MAX limits; it is not a circular BRep floor or a cutter driving size.
    Seeded at ``teeth``; driven by the "FloorDia" global.
    """
    floor = SketchDims()
    check("create_sketch gap-floor reference", await adapter.create_sketch("Front"))
    circle = await define_circle(
        adapter,
        0.0,
        0.0,
        floor_radius_min_mm(teeth),
        "gap-floor reference",
        dims=floor,
        names=(None, None, "FloorDia"),
        drives=(None, None, '"FloorDia"'),
    )
    _as_construction(adapter, circle)
    await ensure_fully_defined(adapter, "gap-floor reference sketch")
    check("exit_sketch gap-floor reference", await adapter.exit_sketch())
    return floor


@_telemetry.traced("part.cone_gear.blank_dia_reference")
async def _author_blank_dia_reference(adapter: Any, radius: float) -> SketchDims:
    """Hidden Right-plane witness of the tip diameter for the side view
    (rule 11), dt_alignment_pinion's OutsideDiaReference.

    An axis centerline across the face width (sketch u = model -Z) and a
    short construction stub at the tip radius on the front face; the doubled
    centerline-to-stub dimension is the printed tip diameter, driven by the
    blank's own 2 * "Ra" so every configuration prints its own blank.
    """
    ref = SketchDims()
    check("create_sketch blank-dia reference", await adapter.create_sketch("Right"))
    # Inference suppressed: the witness lies on the tip silhouette.
    set_sketch_direct_db(adapter, True)
    axis = check(
        "blank-dia reference axis",
        await adapter.add_centerline(0.0, 0.0, -FACE_WIDTH, 0.0),
    )
    witness = check(
        "blank-dia witness stub",
        await adapter.add_line(0.0, radius, -_BLANK_WITNESS_STUB_MM, radius),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, witness)
    for label, line in (("axis", axis), ("witness", witness)):
        check(
            f"blank-dia reference {label} horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
    check(
        "blank-dia reference axis starts at the front face",
        await adapter.add_sketch_constraint(f"{axis}.start", "origin", "coincident"),
    )
    check(
        "blank-dia witness starts at the front face",
        await adapter.add_sketch_constraint(
            f"{witness}.start", "origin", "vertical_points"
        ),
    )
    # The span and the stub's length only define the sketch: auto-named,
    # unmarked. FACE_WIDTH is one value across all configurations.
    await dimension_between(
        adapter,
        f"{axis}.start",
        f"{axis}.end",
        "horizontal_distance",
        FACE_WIDTH,
        "blank-dia reference span",
    )
    ref.record(None, None)
    await dimension_between(
        adapter,
        f"{witness}.start",
        f"{witness}.end",
        "horizontal_distance",
        _BLANK_WITNESS_STUB_MM,
        "blank-dia witness stub length",
    )
    ref.record(None, None)
    # Centerline to the witness's start POINT (build_dt_alignment_pinion: a
    # centerline-to-line pick made a plain linear dimension).
    await add_diametric_linear_dimension(
        adapter, axis, f"{witness}.start", (-FACE_WIDTH / 2.0, radius + 5.0), "BlankDia"
    )
    ref.record("BlankDia", '2 * "Ra"')
    await ensure_fully_defined(adapter, "blank-dia reference sketch")
    check("exit_sketch blank-dia reference", await adapter.exit_sketch())
    name_last_feature(adapter, BLANK_DIA_REFERENCE_SKETCH)
    return ref
