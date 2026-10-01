"""Offline contracts for the transgear arm plate (MHA-165) drawing."""

from __future__ import annotations

import math
from pathlib import Path

import _config
import build_transgear_arm_plate as part
import draw_transgear_arm_plate as drawing
import transgear_arm_plate_geometry as geometry
import transgear_arm_plate_spec as spec
import transgear_hanger_joints as joints
from _buildgraph import module_deps_of
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_limits import deviations


def _band(places: int) -> float:
    return _config.title_block(f"linear_{places}pl")["value_in"] * 25.4


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-arm-plate.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-arm-plate.pdf")
    row = DRAWINGS_BY_NAME["transgear_arm_plate"]
    assert row.script == Path(drawing.__file__).resolve()
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    views = (drawing.PLAN_KEEP, drawing.BACK_KEEP, drawing.SECTION_KEEP)
    assert set().union(*views) == marked
    assert sum(len(view) for view in views) == len(marked)
    assert set(drawing.DIMENSION_CALLOUTS) | set(drawing.CALLOUTS_ABOVE) <= marked
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS


def test_the_explicit_bands_are_the_bore_the_knob_float_and_the_hole_positions() -> (
    None
):
    assert model_toleranced_dimensions(part) == {
        ("ScrewHoleProfile", "ScrewHoleX1"): "HOLE_POSITION_TOLERANCE",
        ("ScrewHoleProfile", "ScrewHoleX2"): "HOLE_POSITION_TOLERANCE",
        ("ScrewHoleProfile", "ScrewHoleY"): "HOLE_POSITION_TOLERANCE",
        ("BearingProfile", "HubToBoss"): "HUB_TO_BOSS_TOLERANCE",
        ("BoreProfile", "BoreDia"): "*deviations(BORE_BAND)",
    }
    # The running bore prints the geometry's clearance limits over Ø8.5.
    lower, upper = deviations(spec.BORE_BAND)
    assert (lower, upper) == geometry.BORE_DIA_LIMITS
    assert 0.0 < lower < upper


def test_every_printed_band_is_no_wider_than_the_arithmetic_assumed() -> None:
    """The walls and the screw engagement were judged at the geometry
    module's bands; the title-block row each printed place count invokes must
    not be wider."""
    for places, band in spec.BAND_BY_PLACES.items():
        assert band >= _band(places)
    precision = spec.DRAWING_PRECISION_BY_NAME
    for name, judged in (
        ("ThicknessOverArm", geometry.BAND_XX),
        ("HubDia", geometry.BAND_XX),
        ("NotchLeftY", geometry.BAND_XX),
        ("NotchRightY", geometry.BAND_XX),
        ("CskDia", geometry.CSK_DIA_BAND),
        ("HubFaceToMounting", geometry.BAND_XXX),
    ):
        assert judged >= _band(precision[name]), name
    # The explicitly banded dimensions print enough places to show their band.
    for name in ("BoreDia", "HubToBoss", "ScrewHoleX1", "ScrewHoleX2", "ScrewHoleY"):
        assert precision[name] == 3, name


def test_the_worst_case_walls_hold_at_the_printed_bands() -> None:
    """Recompute the thinnest walls from the printed title-block rows."""
    drill = _config.title_block("drilled_hole")["plus_mm"]
    bore_r_max = (geometry.BORE_DIA + geometry.BORE_DIA_LIMITS[1]) / 2.0
    hub_wall = (
        geometry.HUB_DIA - _band(spec.DRAWING_PRECISION_BY_NAME["HubDia"])
    ) / 2.0 - bore_r_max
    assert hub_wall >= geometry.WALL_TARGET
    position = spec.HOLE_POSITION_TOLERANCE * math.sqrt(2.0)
    for x, y in geometry.SCREW_HOLES:
        centre_gap = math.hypot(x, y) - position
        hole_wall = centre_gap - bore_r_max - (geometry.SCREW_HOLE_DIA + drill) / 2.0
        assert hole_wall >= geometry.WALL_TARGET
    for name, (_nominal, worst) in geometry.WALLS.items():
        assert worst >= geometry.WALL_TARGET, name


def test_the_plate_screws_engage_the_arm_one_and_a_half_diameters() -> None:
    assert joints.PLATE_SCREW_ENGAGEMENT_WORST_D >= joints.ENGAGEMENT_TARGET_D


def test_the_section_cuts_the_whole_plate_on_the_bore_axis() -> None:
    (x0, y0, _), (x1, y1, _) = drawing.SECTION_LINE_MODEL
    assert x0 == x1 == 0.0
    assert min(y0, y1) < -geometry.END_R
    assert max(y0, y1) > geometry.arm_upper_edge_y(0.0)


def test_registry_row_is_the_made_steel_mha_165() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-165"
    assert int(row["quantity"]) == 1
    assert "1018" in row["material_specification"]
    assert str(row["finish"]).strip()
    assert row["tolerance_class"] == "machined_block"


def test_the_build_imports_no_drawing_or_assembly_module() -> None:
    deps = module_deps_of(Path(part.__file__))
    assert not [
        dep
        for dep in deps
        if Path(str(dep)).stem.startswith(("draw_", "build_"))
        and Path(str(dep)).stem != "build_transgear_arm_plate"
    ]
