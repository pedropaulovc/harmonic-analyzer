r"""Build the pivot bracket's reworked angle plate (MHA-CH-008-TL-02; shop fixture).

A bought 4 x 5 x 3-1/2 in cast-iron angle plate, modelled at its bought
envelope (its slots are omitted), with the four holes the shop adds to the
upright: two #10-24 tapped through holes for the ledge screws and two letter-X
clearance holes for the bridge studs (``ch_pivot_bracket_tl_angle_plate_spec``).

Layout: the base and the upright are Front-plane rectangles from the
plate's left end on the table plane, each extruded -Z (behind the upright's
front face, which is Z0); the holes are drilled from that front face.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_pivot_bracket_tl_angle_plate.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_tolerance,
)
from _hole_spec import blind_cut_dia_mm
from _holes import wizard_holes
from _saved_part_guard import require_saved_drawing_properties
from ch_pivot_bracket_tl_angle_plate_spec import (
    BANDED_DIMENSIONS,
    BASE_THICK,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    LOCATION_BAND,
    PLATE_HEIGHT,
    PLATE_LENGTH,
    PLATE_WIDTH,
    SCREW_Y,
    STUD_SPEC,
    STUD_X,
    STUD_Y,
    TAP_SPEC,
    TAP_X,
    UPRIGHT_THICK,
)

PART_NAME = "ch-pivot-bracket-tl-angle-plate"
MATERIAL = "Gray Cast Iron"  # the registry row names the bought plate
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

TAP_DRILL = blind_cut_dia_mm(TAP_SPEC)
STUD_DRILL = blind_cut_dia_mm(STUD_SPEC)
V_BASE = PLATE_LENGTH * BASE_THICK * PLATE_WIDTH
V_PLATE = V_BASE + PLATE_LENGTH * (PLATE_HEIGHT - BASE_THICK) * UPRIGHT_THICK
V_TAPPED = V_PLATE - len(TAP_X) * math.pi * (TAP_DRILL / 2.0) ** 2 * UPRIGHT_THICK
V_TOTAL = V_TAPPED - len(STUD_X) * math.pi * (STUD_DRILL / 2.0) ** 2 * UPRIGHT_THICK
# Tight enough that a missing or mis-sized hole (>= 140 mm^3) fails.
_V_TOL = 40.0


async def _box_behind_front(
    adapter,
    corner: tuple[float, float],
    size: tuple[float, float],
    depth: float,
    *,
    names: tuple[str, ...],
    drives: tuple[str, ...],
    profile: str,
    feature: str,
    depth_name: str,
    depth_drive: str,
) -> list[tuple[str, str]]:
    """A Front-plane rectangle from ``corner`` extruded ``depth`` along -Z."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    x0, y0 = corner
    w, h = size
    dims = SketchDims()
    check(f"create_sketch {profile}", await adapter.create_sketch("Front"))
    rect = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label=profile, dims=dims,
        names=list(names), drives=list(drives),
    )
    await ensure_fully_defined(adapter, profile)
    check(f"exit_sketch {profile}", await adapter.exit_sketch())
    name_last_feature(adapter, profile)
    jobs = dims.apply(adapter, profile)
    check(
        f"extrude {feature}",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=depth, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, feature)
    jobs.append((name_dimensions(adapter, feature, [depth_name])[0], depth_drive))
    return jobs


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    await set_global(adapter, "PlateLength", f"{PLATE_LENGTH}mm")
    await set_global(adapter, "PlateWidth", f"{PLATE_WIDTH}mm")
    await set_global(adapter, "PlateHeight", f"{PLATE_HEIGHT}mm")
    await set_global(adapter, "BaseThick", f"{BASE_THICK}mm")
    await set_global(adapter, "UprightThick", f"{UPRIGHT_THICK}mm")
    await set_global(adapter, "TapX1", f"{TAP_X[0]}mm")
    await set_global(adapter, "TapX2", f"{TAP_X[1]}mm")
    await set_global(adapter, "TapY", f"{SCREW_Y}mm")
    await set_global(adapter, "StudX1", f"{STUD_X[0]}mm")
    await set_global(adapter, "StudX2", f"{STUD_X[1]}mm")
    await set_global(adapter, "StudY", f"{STUD_Y}mm")

    # Bought envelope: the base under the table-plane origin, then the
    # upright standing on it, flush with the base's front edge.
    drive_jobs = await _box_behind_front(
        adapter, (0.0, 0.0), (PLATE_LENGTH, BASE_THICK), PLATE_WIDTH,
        names=("BaseLength", "BaseThick"), drives=('"PlateLength"', '"BaseThick"'),
        profile="BaseProfile", feature="Base",
        depth_name="BaseWidth", depth_drive='"PlateWidth"',
    )
    await volume_check(adapter, "base", V_BASE, _V_TOL)
    drive_jobs += await _box_behind_front(
        adapter, (0.0, BASE_THICK), (PLATE_LENGTH, PLATE_HEIGHT - BASE_THICK), UPRIGHT_THICK,
        names=("UprightLength", "UprightHeight", "UprightBase"),
        drives=('"PlateLength"', '"PlateHeight" - "BaseThick"', '"BaseThick"'),
        profile="UprightProfile", feature="Upright",
        depth_name="UprightThick", depth_drive='"UprightThick"',
    )
    await volume_check(adapter, "bought plate", V_PLATE, _V_TOL)

    # The shop's four holes, each pair ONE native wizard feature drilled
    # from the upright's front face; each pair's second height repeats the
    # first's and stays off the print.
    taps = wizard_holes(
        adapter,
        TAP_SPEC,
        [[x, SCREW_Y, 0.0] for x in TAP_X],
        (0.0, 0.0, 1.0),
        "ledge screw taps (#10-24 through)",
        name="LedgeTaps",
        expect_dia_mm=TAP_DRILL,
        placement_dims=[
            (("Tap1X", '"TapX1"'), ("Tap1Y", '"TapY"')),
            (("Tap2X", '"TapX2"'), ("Tap2Y", '"TapY"')),
        ],
    )
    drive_jobs += taps.placement_drive_jobs
    await volume_check(adapter, "plate with taps", V_TAPPED, _V_TOL)
    studs = wizard_holes(
        adapter,
        STUD_SPEC,
        [[x, STUD_Y, 0.0] for x in STUD_X],
        (0.0, 0.0, 1.0),
        "bridge stud holes (letter X through)",
        name="StudHoles",
        expect_dia_mm=STUD_DRILL,
        placement_dims=[
            (("Stud1X", '"StudX1"'), ("Stud1Y", '"StudY"')),
            (("Stud2X", '"StudX2"'), ("Stud2Y", '"StudY"')),
        ],
    )
    drive_jobs += studs.placement_drive_jobs
    await volume_check(adapter, "reworked plate", V_TOTAL, _V_TOL)

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven plate (equations neutral)", V_TOTAL, _V_TOL)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    for feature_name, dimension_names in BANDED_DIMENSIONS.items():
        for dimension_name in sorted(dimension_names):
            set_dimension_symmetric_tolerance(
                adapter, feature_name, dimension_name, LOCATION_BAND
            )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
