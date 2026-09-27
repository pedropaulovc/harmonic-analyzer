r"""Reproduction script: cylinder gear arbor (book ch. 13, pp. 22-25).

Plain Ø3/8 in steel STATIONARY arbor carrying the 20 identical cylinder
gears with their integral eccentric cams (~134 mm stack at 7.06 mm
Z-pitch, alternating with the black connecting rods that ride the cams).
No keyseat: gear k turns k/80 rev per crank turn (ch. 29 gear law), so
the 20 gears all spin at DIFFERENT speeds and cannot be keyed to a
common shaft -- they run free on this fixed arbor (DIMENSIONS.md ch. 13,
"M6.2 keyway refutation"; the legacy keyseat was fiction, removed in
M6.2). The arbor fills both pedestal strap bores and is held by one cup-point
set screw in each pedestal's crown apex (#743, MHA-147); each end is domed
proud of its strap -- the bright dome the photographs show on each pedestal.

Dimensions: cad/DIMENSIONS.md "Chapter 13" - dia legacy (med), length
derived from the stack + eight-views 8/8 pedestals (low).

Layout: arbor axis along +Y from the origin, plain cylinder y 0..ARBOR_LENGTH
(a REFERENCE length: the span over both pedestal straps, cut to fit at
assembly), plus a spherical dome ARBOR_DOME_HEIGHT high past each end.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cylinder_gear_shaft.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _common import (
    SketchDims,
    _early_bound,
    _read_member,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from cylinder_bank_layout import ARBOR_DOME_HEIGHT, ARBOR_LENGTH
from cylinder_gear_shaft_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    REFERENCE_SKETCHES,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    SURFACE_FINISHES,
)

PART_NAME = "cylinder-gear-shaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

SHAFT_RADIUS = SHAFT_DIA / 2.0
SHAFT_LENGTH = ARBOR_LENGTH  # the cylinder: the span over both straps (REF)
DOME_HEIGHT = ARBOR_DOME_HEIGHT
DOME_SPHERE_RADIUS = (SHAFT_RADIUS**2 + DOME_HEIGHT**2) / (2.0 * DOME_HEIGHT)
V_DOME = math.pi * DOME_HEIGHT**2 * (3.0 * DOME_SPHERE_RADIUS - DOME_HEIGHT) / 3.0


def _select_end_face_mark1(adapter, y_mm: float) -> None:
    """Select the flat end face carrying the axis point (0, ``y_mm``, 0) with
    selection mark 1, the mark ``InsertDome`` requires. Only the end face
    contains the axis point; the cylinder is a full radius away."""
    from solidworks_mcp.adapters.solidworks.features import (
        _all_body_faces,
        _flag_feature_methods,
    )

    target = (0.0, y_mm / 1000.0, 0.0)
    best, best_d = None, 1e-6
    for face in _all_body_faces(adapter):
        near = adapter._attempt(
            lambda f=face: list(f.GetClosestPointOn(*target)), default=None
        )
        if not near or len(near) < 3:
            continue
        d = math.dist(near[:3], target)
        if d < best_d:
            best, best_d = face, d
    if best is None:
        raise RuntimeError(f"no arbor end face on the axis at y={y_mm:g} mm")
    adapter.currentModel.ClearSelection2(True)
    entity = _flag_feature_methods(best, "IEntity", "Select2")
    if not adapter._attempt(lambda e=entity: e.Select2(False, 1), default=False):
        raise RuntimeError(f"cannot select the arbor end face at y={y_mm:g} (mark 1)")


def _dome_end(adapter, y_mm: float, name: str) -> None:
    """One spherical dome DOME_HEIGHT high on the end face at ``y_mm``: on a
    circular face InsertDome's non-elliptic dome is a spherical cap
    (diag_build_9490T1's Dome1 is the proven precedent)."""
    _select_end_face_mark1(adapter, y_mm)
    with _telemetry.span("feature.dome", label=name):
        adapter.currentModel.InsertDome(
            DOME_HEIGHT / 1000.0,  # metres
            False,  # ReverseDir: the end face's own normal points off the rod
            False,  # DoEllipticSurface: a spherical cap
        )
    adapter.currentModel.ClearSelection2(True)
    name_last_feature(adapter, name)


async def _dome_reference(adapter) -> list[tuple[str, str]]:
    """The hidden DomeReference sketch (cylinder_gear_shaft_spec): one
    construction line along the axis over the north dome whose driving
    dimension IS the dome height, equation-bound to its global."""
    sketch = "DomeReference"
    check(f"create_sketch {sketch}", await adapter.create_sketch("Front"))
    # Direct-to-DB: the line runs along the sketch's own axis, so creation
    # inference would snap in relations that over-define it.
    set_sketch_direct_db(adapter, True)
    line = check(
        f"{sketch} line",
        await adapter.add_line(0.0, SHAFT_LENGTH, 0.0, SHAFT_LENGTH + DOME_HEIGHT),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{sketch} line did not take the construction flag")
    check(
        f"{sketch} vertical",
        await adapter.add_sketch_constraint(line, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "vertical_distance",
        DOME_HEIGHT,
        sketch,
    )
    await anchor_point_to_origin(adapter, f"{line}.start", 0.0, SHAFT_LENGTH, sketch)
    await ensure_fully_defined(adapter, f"{sketch} sketch")
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    full = name_dimensions(adapter, sketch, ["DomeHeight", "DomeHeightAnchor1"])
    return list(zip(full, ('"DomeHeight"', '"ShaftLength"'), strict=True))


def _hide_reference_sketches(adapter) -> None:
    """Blank the drawing-reference sketches and prove each one reads hidden."""
    for name in REFERENCE_SKETCHES:
        blank_sketch(adapter, name)
    part = _early_bound(adapter.currentModel, "IPartDoc")
    shown = [
        name
        for name in REFERENCE_SKETCHES
        # swVisibilityState_e: 1 hidden
        if int(_read_member(part.FeatureByName(name), "Visible")) != 1
    ]
    if shown:
        raise RuntimeError(f"reference sketches still visible after blanking: {shown}")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the arbor diameter and length. The mm
    # suffix is load-bearing -- this is an INCH document and the equation manager
    # reads BARE numbers in document units (an unsuffixed 176 would be 176 in).
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLength", f"{SHAFT_LENGTH}mm")
    await set_global(adapter, "DomeHeight", f"{DOME_HEIGHT}mm")

    drive_jobs: list[tuple[str, str]] = []

    # On-axis circle (centre at the origin): define_circle records ONLY the
    # diameter dim (the X/Z centre slots are relations, not display dims).
    shaft = SketchDims()
    check("create_sketch shaft", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        SHAFT_RADIUS,
        "shaft circle",
        dims=shaft,
        names=("ShaftCx", "ShaftCz", "ShaftDia"),
        drives=(None, None, '"ShaftDia"'),
    )
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs += shaft.apply(adapter, "ShaftProfile")
    check(
        "extrude shaft",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHAFT_LENGTH)),
    )
    name_last_feature(adapter, "Shaft")
    depth_dim = name_dimensions(adapter, "Shaft", ["Depth"])
    drive_jobs += [(depth_dim[0], '"ShaftLength"')]
    v_shaft = math.pi * SHAFT_RADIUS**2 * SHAFT_LENGTH
    # expected: pi * 4.7625^2 * 164.58 = ~11,727 mm^3
    await volume_check(adapter, "shaft", v_shaft, 0.005 * v_shaft)
    # Both ends domed into the photographed bright caps (#743).
    _dome_end(adapter, 0.0, "SouthDome")
    _dome_end(adapter, SHAFT_LENGTH, "NorthDome")
    v_shaft += 2.0 * V_DOME
    await volume_check(adapter, "shaft + domes", v_shaft, 0.005 * v_shaft)
    drive_jobs += await _dome_reference(adapter)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven shaft (equations neutral)", v_shaft, 0.005 * v_shaft
    )
    _hide_reference_sketches(adapter)

    # Named central axis (arbor axis along +Y through the origin) so the
    # cylinder gears ride it coincident axis-to-axis in the assembly.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "shaft axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "ShaftProfile", "ShaftDia", *deviations(SHAFT_DIA_BAND)
    )
    # Decimal places belong to the model dimension, not to the sheet: the
    # drawing imports these and only asserts they survived.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The one running surface's roughness lives on the MODEL as a plain
    # annotation; the drawing imports the control and places the symbol.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
