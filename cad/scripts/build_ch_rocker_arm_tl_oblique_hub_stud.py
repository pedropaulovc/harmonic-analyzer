r"""Reproduction script: oblique-trammel hub clamp stud (MHA-CH-06-TL-33).

The turned steel stud that replaces the bonded TL-VN-80 gauge pin
(``ch_rocker_arm_tl_oblique_hub_stud_spec``): a flange under the TL-21
carrier, a shank that slips up through the carrier's HUB bore and the TL-34
sleeve, and the gauge pin's .4000 locating nose with a #10-24 blind tap for
the TL-VN-85 hub screw.  The shank root carries a modelled tool radius,
printed as a single MAX limit.

Layout: three stacked Front-plane-parallel circles extruded +Z (flange from
the Front Plane, shank from ``FlangeTop``, nose from ``NoseBase``), so the
flange underside is the Front Plane (z = 0) and the nose top is at
z = LENGTH.  ``Axis1`` is the stud axis (Top Plane x Right Plane, local Z).
The hidden ``FitReference`` sketch on the Right Plane carries the fit-up
length (flange seat to nose top, a reference) and the supply length (flange
seat up, a single MIN limit) for the side view.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_hub_stud.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _holes import blind_hole_volume_mm3, wizard_holes
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_pmi import author_part_pmi
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _single_limit_tolerance import set_single_limit
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from ch_rocker_arm_tl_oblique_hub_stud_spec import (
    DIA,
    DRAWING_BANDS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FIT_LENGTH,
    FLANGE_DIA,
    FLANGE_THICK,
    LENGTH,
    NOSE_LENGTH,
    ROOT_FILLET_BAND,
    ROOT_FILLET_R,
    ROOT_FILLET_TOL_TYPE,
    SHANK_DIA,
    SHANK_LENGTH,
    SUPPLY_LENGTH_BAND,
    SUPPLY_LENGTH_MIN,
    SUPPLY_LENGTH_TOL_TYPE,
    TAP_DRILL_DIA,
    TAP_SPEC,
    UNIT,
)

PART_NAME = "ch-rocker-arm-tl-oblique-hub-stud"
MATERIAL = "Plain Carbon Steel"  # 1018 bar; see _appearance.apply_material
# The assembly mates the stud axis to ``Axis1@<stud>``: the first (and only)
# reference axis the part creates.
STUD_AXIS = "Axis1"

V_FLANGE = math.pi * (FLANGE_DIA / 2.0) ** 2 * FLANGE_THICK
V_SHANK = math.pi * (SHANK_DIA / 2.0) ** 2 * SHANK_LENGTH
V_NOSE = math.pi * (DIA / 2.0) ** 2 * NOSE_LENGTH
# Pappus: the root spandrel r^2 (1 - pi/4), its centroid r (10 - 3 pi) /
# (3 (4 - pi)) out from the shank surface, revolved about the stud axis.
_SPANDREL = ROOT_FILLET_R**2 * (1.0 - math.pi / 4.0)
_SPANDREL_R = SHANK_DIA / 2.0 + ROOT_FILLET_R * (10.0 - 3.0 * math.pi) / (
    3.0 * (4.0 - math.pi)
)
V_FILLET = 2.0 * math.pi * _SPANDREL_R * _SPANDREL


async def _boss(
    adapter,
    plane: str,
    dia: float,
    depth: float,
    *,
    label: str,
    profile: str,
    feature: str,
    dia_name: str,
    depth_name: str,
) -> list[tuple[str, str]]:
    """One on-axis circle on ``plane`` extruded +Z by ``depth``."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    await define_circle(
        adapter,
        0.0,
        0.0,
        dia / 2.0,
        label,
        dims=dims,
        names=(f"{dia_name}Cx", f"{dia_name}Cy", dia_name),
        drives=(None, None, f'"{dia_name}"'),
    )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, profile)
    jobs = dims.apply(adapter, profile)
    check(
        f"extrude {label}",
        await adapter.create_extrusion(ExtrusionParameters(depth=depth)),
    )
    name_last_feature(adapter, feature)
    depth_dim = name_dimensions(adapter, feature, [depth_name])
    jobs.append((depth_dim[0], f'"{depth_name}"'))
    return jobs


async def _offset_plane(adapter, name: str, offset: float) -> None:
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create_plane {name}",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=offset)
        ),
    )
    name_last_feature(adapter, name)


async def _fit_reference(adapter) -> None:
    """The side view's fit-up and supply lengths, natively (rule 19): a hidden
    Right-plane sketch (sketch x = model -Z, sketch y = model Y) of two
    construction lines from the flange seat along the stud, one on each side
    of the axis -- FitLength to the nose top (a reference the fitter faces to)
    and SupplyLength (the turned length, a single MIN limit)."""
    check("create_sketch fit reference", await adapter.create_sketch("Right"))
    # Direct-to-DB: both lines start on the seat's projected edge, where
    # creation-time inference would snap them to the silhouette.
    set_sketch_direct_db(adapter, True)
    fit_y = DIA / 2.0
    supply_y = -DIA / 2.0
    fit = check(
        "fit length line",
        await adapter.add_line(
            -FLANGE_THICK, fit_y, -(FLANGE_THICK + FIT_LENGTH), fit_y
        ),
    )
    supply = check(
        "supply length line",
        await adapter.add_line(
            -FLANGE_THICK, supply_y, -(FLANGE_THICK + SUPPLY_LENGTH_MIN), supply_y
        ),
    )
    set_sketch_direct_db(adapter, False)
    for line, label in ((fit, "fit"), (supply, "supply")):
        segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
        segment.ConstructionGeometry = True  # VT_BOOL property put/get
        if segment.ConstructionGeometry is not True:
            raise RuntimeError(f"{label} reference line did not take the construction flag")
        check(
            f"{label} reference horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
    await dimension_between(
        adapter, f"{fit}.start", f"{fit}.end", "horizontal_distance", FIT_LENGTH, "fit length"
    )
    await dimension_between(
        adapter,
        f"{supply}.start",
        f"{supply}.end",
        "horizontal_distance",
        SUPPLY_LENGTH_MIN,
        "supply length",
    )
    await anchor_point_to_origin(adapter, f"{fit}.start", -FLANGE_THICK, fit_y, "fit length")
    await anchor_point_to_origin(
        adapter, f"{supply}.start", -FLANGE_THICK, supply_y, "supply length"
    )
    await ensure_fully_defined(adapter, "fit reference sketch")
    check("exit_sketch fit reference", await adapter.exit_sketch())
    name_last_feature(adapter, "FitReference")
    name_dimensions(
        adapter,
        "FitReference",
        ["FitLength", "SupplyLength", "FitSeatX", "FitSeatY", "SupplySeatX", "SupplySeatY"],
    )
    blank_reference_sketches(adapter, ("FitReference",))


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "FlangeDia", f"{FLANGE_DIA}mm")
    await set_global(adapter, "FlangeThick", f"{FLANGE_THICK}mm")
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLength", f"{SHANK_LENGTH}mm")
    await set_global(adapter, "NoseDia", f"{DIA}mm")
    await set_global(adapter, "NoseLength", f"{NOSE_LENGTH}mm")
    await set_global(adapter, "RootRadius", f"{ROOT_FILLET_R}mm")

    drive_jobs: list[tuple[str, str]] = []

    # 1. Flange: the Front Plane is its underside.
    drive_jobs += await _boss(
        adapter,
        "Front",
        FLANGE_DIA,
        FLANGE_THICK,
        label="flange",
        profile="FlangeProfile",
        feature="Flange",
        dia_name="FlangeDia",
        depth_name="FlangeThick",
    )
    volume = await volume_check(adapter, "flange", V_FLANGE, 0.005 * V_FLANGE)

    # 2. Shank: from the flange seat up through the carrier and riser.
    await _offset_plane(adapter, "FlangeTop", FLANGE_THICK)
    drive_jobs += await _boss(
        adapter,
        "FlangeTop",
        SHANK_DIA,
        SHANK_LENGTH,
        label="shank",
        profile="ShankProfile",
        feature="Shank",
        dia_name="ShankDia",
        depth_name="ShankLength",
    )
    volume = await volume_check(adapter, "shank", volume + V_SHANK, 0.005 * V_SHANK)

    # 3. Nose: the gauge pin's locating diameter and proud height.
    await _offset_plane(adapter, "NoseBase", FLANGE_THICK + SHANK_LENGTH)
    drive_jobs += await _boss(
        adapter,
        "NoseBase",
        DIA,
        NOSE_LENGTH,
        label="nose",
        profile="NoseProfile",
        feature="Nose",
        dia_name="NoseDia",
        depth_name="NoseLength",
    )
    blank_reference_geometry(adapter, (("FlangeTop", "PLANE"), ("NoseBase", "PLANE")))
    volume = await volume_check(adapter, "nose", volume + V_NOSE, 0.01 * V_NOSE)
    await bbox_extent_check(adapter, "stud length", "z", LENGTH)
    await bbox_extent_check(adapter, "flange O.D.", "x", FLANGE_DIA)

    # 4. Shank root: picked on the circular shank/flange edge at +X, the only
    #    edge through that point.
    check(
        "fillet shank root",
        await adapter.add_fillet(ROOT_FILLET_R, [[SHANK_DIA / 2.0, 0.0, FLANGE_THICK]]),
    )
    name_last_feature(adapter, "RootFillet")
    fillet_dim = name_dimensions(adapter, "RootFillet", ["RootRadius"])
    drive_jobs.append((fillet_dim[0], '"RootRadius"'))
    volume = await volume_check(
        adapter, "shank root fillet", volume + V_FILLET, 0.005 * V_SHANK
    )

    # 5. Hub screw tap: one blind #10-24 Hole Wizard tap in the nose top on
    #    the axis (the placement point coincident with the projected origin).
    tap = wizard_holes(
        adapter,
        TAP_SPEC,
        [[0.0, 0.0, LENGTH]],
        (0.0, 0.0, 1.0),
        f"hub screw tap ({TAP_SPEC.size} blind)",
        name="NoseTap",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    drive_jobs += tap.placement_drive_jobs
    v_tap = blind_hole_volume_mm3(tap.hole_dia_mm, TAP_SPEC.depth_mm)
    volume = await volume_check(adapter, "hub screw tap", volume - v_tap, 0.03 * v_tap)

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven stud (equations neutral)", volume, 0.005 * V_SHANK
    )

    # 6. Stud axis (Top Plane x Right Plane), the line the assembly mates.
    axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "hub stud axis"
    )
    if axis != STUD_AXIS:
        raise RuntimeError(f"hub stud axis came back {axis!r}, not {STUD_AXIS}")
    blank_reference_geometry(adapter, ((axis, "AXIS"),))
    await _fit_reference(adapter)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    for (feature_name, dimension_name), band in DRAWING_BANDS.items():
        set_dimension_bilateral_tolerance(
            adapter, feature_name, dimension_name, *deviations(band), display_unit=UNIT
        )
    set_single_limit(
        adapter,
        "RootFillet",
        "RootRadius",
        limit=ROOT_FILLET_R,
        band=ROOT_FILLET_BAND,
        tol_type=ROOT_FILLET_TOL_TYPE,
    )
    set_single_limit(
        adapter,
        "FitReference",
        "SupplyLength",
        limit=SUPPLY_LENGTH_MIN,
        band=SUPPLY_LENGTH_BAND,
        tol_type=SUPPLY_LENGTH_TOL_TYPE,
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=())
    apply_drawing_properties(adapter, PART_NAME)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter, ("Number", "Material Specification", "Finish", "Quantity")
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
