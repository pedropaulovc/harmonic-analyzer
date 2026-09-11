"""Offline contracts for the arbor-pedestal drawing."""

from __future__ import annotations

import arbor_pedestal_spec
import build_arbor_pedestal as part
import draw_arbor_pedestal as drawing
from _drawing_contract import model_toleranced_dimensions
from _hole_spec import blind_cut_dia_mm


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is arbor_pedestal_spec.DRAWING_DIMENSIONS
    marked = set().union(*arbor_pedestal_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert marked == {
        "Width",
        "Depth",
        "FootHt",
        "BoreDia",
    }


def test_arbor_bore_closes_the_configured_running_fit() -> None:
    import _config

    assert round(arbor_pedestal_spec.BORE_DIA, 2) == 9.55
    assert drawing.DIMENSION_PRECISION == {
        "Width": 1,
        "Depth": 1,
        "FootHt": 1,
        "BoreDia": 2,
    }
    shaft_limits = (9.505, 9.525)
    bore_limits = (9.550, 9.580)
    clearances = (
        bore_limits[0] - shaft_limits[1],
        bore_limits[1] - shaft_limits[0],
    )
    expected = tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    assert tuple(round(value, 3) for value in clearances) == expected


def test_screw_hole_contract_is_part_owned() -> None:
    spec = arbor_pedestal_spec.SCREW_HOLE_SPEC
    assert part.SCREW_HOLE_SPEC is spec
    assert spec.kind == "clearance"
    assert spec.size == "#4"
    assert spec.fit == "normal"
    assert arbor_pedestal_spec.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)
    assert part.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)


def test_tangent_crown_closes_the_upright_profile() -> None:
    root_x = arbor_pedestal_spec.FOOT_WIDTH / 2.0
    tangent_x = arbor_pedestal_spec.TAPER_TANGENT_X
    tangent_y = arbor_pedestal_spec.TAPER_TANGENT_Y
    radius_x = tangent_x
    radius_y = tangent_y - arbor_pedestal_spec.BORE_HEIGHT
    flank_x = tangent_x - root_x
    flank_y = tangent_y - arbor_pedestal_spec.FOOT_HEIGHT

    assert abs(
        radius_x**2 + radius_y**2 - arbor_pedestal_spec.TOP_RADIUS**2
    ) < 1e-9
    assert abs(radius_x * flank_x + radius_y * flank_y) < 1e-9
    assert 0.0 < tangent_x < root_x
    assert arbor_pedestal_spec.FOOT_HEIGHT < tangent_y
    assert arbor_pedestal_spec.BORE_HEIGHT < tangent_y
    assert "StrapProfile" not in arbor_pedestal_spec.DRAWING_DIMENSIONS
    assert "DomeProfile" not in arbor_pedestal_spec.DRAWING_DIMENSIONS


def test_running_bore_and_mating_foot_seat_carry_surface_finish_controls() -> None:
    by_key = {c.key: c for c in arbor_pedestal_spec.SURFACE_FINISHES}
    assert set(by_key) == {"arbor_bore", "foot_seat"}
    assert by_key["arbor_bore"].roughness_um == 1.6
    assert by_key["arbor_bore"].face.contains_y_mm == arbor_pedestal_spec.BORE_HEIGHT
    # The seat is the only face that MUST be cut on a part the title block
    # otherwise leaves CAST/MACHINED; it is the y=0 plane facing -Y.
    assert by_key["foot_seat"].roughness_um == 3.2
    assert by_key["foot_seat"].face.normal == (0, -1, 0)
    assert by_key["foot_seat"].face.offset_mm == 0.0
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"
    }


def test_projected_view_alignment_is_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.TOP_CENTER[1] > drawing.FRONT_CENTER[1]
    assert drawing.ISO_CENTER[0] > drawing.FRONT_CENTER[0]


def test_part_stamps_make_flexible_material_and_protective_finish() -> None:
    assert part.MATERIAL == "Plain Carbon Steel"
    import _config

    config = _config.parts("arbor-pedestal")
    assert config["material"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert config["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert config["finish"] == (
        "BLACK JAPAN/ENAMEL; MASK BORE AND FOOT SEAT; OIL BARE MACHINED SURFACES"
    )
    assert config["process"] == "machined from solid stock or casting"
    # Two identical pedestals: the south support plus the north one rotated
    # 180 about Y (build_drive_train_assembly places both).
    assert int(config["quantity"]) == 2
