"""Offline contracts for the pivot-ball-mount drawing."""

from __future__ import annotations

from pathlib import Path

import _surface_finish
import build_pivot_ball_mount as part
import draw_pivot_ball_mount as drawing
import pivot_ball_mount_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pivot-ball-mount.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pivot-ball-mount.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pivot-ball-mount_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pivot_ball_mount"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pivot_ball_mount_spec.DRAWING_DIMENSIONS
    marked = set().union(*pivot_ball_mount_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert marked == {
        "BallDia",
        "BallRise",
        "BaseDia",
        "BaseHeight",
        "ShaftBoreDia",
        "StemDia",
    }


def test_part_uses_shared_geometry_constants() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    for name in (
        "BALL_DIA",
        "BALL_CENTER_H",
        "BASE_DIA",
        "BASE_H",
        "STEM_DIA",
        "BORE_DIA",
    ):
        assert getattr(part, name) == getattr(pivot_ball_mount_spec, name)
        assert f"{name} =" not in source


def test_callouts_clarify_bore_and_center_height() -> None:
    assert drawing.DIMENSION_CALLOUTS["ShaftBoreDia"] == "THRU"
    assert "BallRise" not in drawing.DIMENSION_CALLOUTS
    assert model_toleranced_dimensions(part) == {
        ("ShaftBoreProfile", "ShaftBoreDia"): "*deviations(SHAFT_BORE_DIA_BAND)",
        ("BallMountProfile", "BaseHeight"): "BASE_HEIGHT_TOLERANCE_MM",
        ("BallMountProfile", "BallDia"): "BALL_DIAMETER_TOLERANCE_MM",
        ("BallMountProfile", "BaseDia"): "BASE_DIAMETER_TOLERANCE_MM",
        ("BallMountProfile", "StemDia"): "STEM_DIAMETER_TOLERANCE_MM",
    }
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "HEIGHT PER NATIVE DIMENSION" not in source
    assert "+/-0.05" not in source


def test_notes_specify_ball_bore_and_shaft_without_title_block_duplicates() -> None:
    notes = pivot_ball_mount_spec.DRAWING_NOTES
    assert "6.35" in notes  # the mating pivot shaft
    assert "MATERIAL" not in notes
    assert "DATUM A" in notes
    assert "DATUM B" in notes
    assert "FINISH SYMBOL" in notes
    assert "AFTER PLATE" in notes
    assert "SHOULDERS: EDGE BREAK 0.10 MAX" in notes
    assert "NO TRANSITION BLEND OR UNDERCUT" in notes
    assert "X.XX" not in notes
    assert "BREAK EDGES" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_datum_and_geometric_controls_are_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'datum="A"' in source
    assert 'datum="B"' in source
    assert 'characteristic="position"' in source
    assert 'characteristic="perpendicularity"' in source
    assert source.count('characteristic="circular_runout"') == 1
    assert "frame_xy=(0.205, 0.165)" in source
    assert "STEM_DIM_TEXT = (0.180, _front_y(12.0))" in source
    assert "frame_xy=(0.180, _front_y(12.0) - 0.014)" in source
    assert 'characteristic="profile_surface"' in source
    # The stem FCF's leader lands at the text block's corner: mid-text pierces
    # the digits, and docking (no leader) trips the layout audit on the stale
    # off-sheet leader segment a docked gtol reports.
    assert "leader_attach_xy=STEM_DIM_TEXT" not in source
    assert (
        "leader_attach_xy=(STEM_DIM_TEXT[0] - 0.004, STEM_DIM_TEXT[1] - 0.0045)"
        in source
    )
    assert "StemDia" in drawing.FRONT_KEEP
    assert 'entity_type="SILHOUETTE"' in source
    assert source.count('entity_type="DIMENSION"') == 1
    assert "symbol_xy=(0.150, _front_y(12.0))" in source
    assert "position_tolerance_m=0.020" in source
    assert "set_basic_dimension(" in source
    assert "add_view_centerline(" in source
    assert "INTERSECT DATUM B WITHIN" not in pivot_ball_mount_spec.DRAWING_NOTES
    assert 'quantity="PAD OD"' in source
    assert "add_attached_note(" not in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(3, 1)") == 2  # elevation + pictorial


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pivot-ball-mount")
    assert "1018" in str(config["material_specification"])
    assert "1018" in str(config["material"])
    assert "ASTM B733-22" in str(config["finish"])
    assert "MP (5-9% P)" in str(config["finish"])
    assert "SC1" in str(config["finish"])
    assert "after plate" in str(config["finish"])
    assert int(config["quantity"]) == 4


def test_surface_finishes_are_part_owned_authored_and_consumed() -> None:
    by_key = {control.key: control for control in pivot_ball_mount_spec.SURFACE_FINISHES}
    assert set(by_key) == {"cross_bore", "turned_exterior_before_plate"}
    bore = by_key["cross_bore"]
    assert bore.roughness_um == _surface_finish.MACHINED_UM
    assert bore.face.diameter_mm == pivot_ball_mount_spec.BORE_DIA
    assert bore.face.contains_y_mm == pivot_ball_mount_spec.BALL_CENTER_H
    exterior = by_key["turned_exterior_before_plate"]
    assert exterior.roughness_um == _surface_finish.GROUND_UM
    assert exterior.face.diameter_mm == pivot_ball_mount_spec.BALL_DIA
    assert exterior.face.center_mm == (0.0, pivot_ball_mount_spec.BALL_CENTER_H, 0.0)

    part_source = "".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert 'surface_finish_by_key(SURFACE_FINISHES,"cross_bore")' in sheet_source
    assert (
        'surface_finish_by_key(SURFACE_FINISHES,"turned_exterior_before_plate")'
        in sheet_source
    )
    assert "roughness_ra=" not in sheet_source
