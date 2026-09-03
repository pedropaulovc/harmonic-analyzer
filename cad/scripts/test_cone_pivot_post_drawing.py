"""Offline contracts for the v2 cone-pivot-post source and drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_pivot_post as part
import cone_pivot_post_spec as spec
import draw_cone_pivot_post as drawing
from _assembly import _seed_flip
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-pivot-post.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-pivot-post.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-pivot-post_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_pivot_post"].script
        == Path(drawing.__file__).resolve()
    )


def test_v2_harvest_is_the_exact_dimensional_contract() -> None:
    assert (spec.BLOCK_DIA, spec.BLOCK_HEIGHT) == (42.011, 86.0)
    assert (spec.HEAD_DIA, spec.HEAD_HEIGHT, spec.HEAD_BASE_Y) == (
        42.7506,
        26.6,
        59.4,
    )
    assert (
        spec.CRANK_BOSS_DIA,
        spec.CRANK_BORE_DIA,
        spec.CRANK_BORE_HEIGHT,
        spec.CRANK_BORE_OFFSET,
    ) == (21.93, 11.438, 72.7, 0.0)
    assert spec.CRANK_BOSS_LENGTH_IN == 2.8360
    assert round(spec.CRANK_BOSS_LENGTH, 4) == 72.0344
    assert round(spec.CRANK_BOSS_START_Z, 4) == -21.3753
    assert round(spec.CRANK_BOSS_END_Z, 4) == 50.6591
    assert (spec.CONE_BOSS_DIA, spec.BORE_DIA, spec.BORE_HEIGHT) == (
        17.2,
        12.2808,
        33.368,
    )
    assert spec.INCLINE_DEG == 12.5182
    assert (
        spec.ATTACHMENT_SPACING,
        spec.ATTACHMENT_THRU_DIA,
        spec.ATTACHMENT_CBORE_DIA,
        spec.ATTACHMENT_CBORE_DEPTH,
    ) == (26.88704, 7.14248, 11.50874, 6.0198)
    assert spec.HARVESTED_VOLUME_MM3 == 112_302.9406
    assert spec.HARVESTED_MASS_KG == 0.808581173


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert marked == {
        "MainBodyDia",
        "MainBodyHt",
        "HeadDia",
        "HeadHt",
        "CrankAxisY",
        "CrankBossDia",
        "CrankBoreDia",
    }
    assert drawing.FRONT_KEEP["CrankBossDia"][1] == (
        drawing._front_y(drawing.CRANK_BORE_HEIGHT) + 0.018
    )
    assert drawing.FRONT_KEEP["CrankBoreDia"][1] == (
        drawing._front_y(drawing.CRANK_BORE_HEIGHT) - 0.012
    )


def test_inclined_journal_is_defined_by_a_leader_note_from_its_rim() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "journal_entity = _bore_rim_edge(adapter, front, diameter_mm=BORE_DIA)" in source
    assert "add_attached_note(" in source
    assert "entity=journal_entity" in source
    # Sizes, axis height and swing angle all come from the spec constants.
    for constant in ("CONE_BOSS_DIA", "BORE_DIA", "BORE_HEIGHT", "INCLINE_DEG"):
        assert f"{{{constant}:" in source, constant
    assert "BORE THRU" in source
    # The boxed journal-axis coordinate table is gone with the position frame.
    assert not hasattr(spec, "JOURNAL_AXIS_POINTS")
    assert not hasattr(spec, "JOURNAL_AXIS_ORIENTATION_NOTE")
    assert "SetBalloon" not in source
    assert "JOURNAL AXIS COORDINATES" not in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "MACHINE THE FOOT SEAT" in notes
    assert "AS-CAST ELSEWHERE" in notes
    assert "BORE THE CRANK BORE" in notes
    # Material and paint/masking are title-block fields; sizes ride the views.
    for banned in (
        "A48", "CAST ASTM", "MASK", "DATUM", "BASIC", "+/-", "12.2808", "11.438",
        "11.50874", "26.88704", "X.XX", "UOS",
    ):
        assert banned not in notes, banned
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_attachment_holes_use_a_native_callout_and_a_spacing_dimension() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "west_rim, east_rim = _attachment_thru_rims(adapter, top)" in source
    assert "add_native_hole_callout(" in source
    assert "edge=east_rim" in source
    # Harvey #13: the callout says DRILL; 0.28125 in (9/32) is the 7.142 through.
    assert 'process="9/32 DRILL"' in source
    assert abs(spec.ATTACHMENT_THRU_DIA - 9.0 / 32.0 * 25.4) < 0.01
    assert "_add_attachment_spacing(adapter, top, west_rim, east_rim)" in source
    assert "draw.AddHorizontalDimension2(TOP_CENTER[0], TOP_CENTER[1] - 0.026, 0.0)" in source
    assert 'set_arc_endpoints_to_center(adapter, display, label="attachment spacing")' in source
    # The rims are picked by entity at the counterbore floor, never by sheet xy.
    assert "center_y_mm = BLOCK_HEIGHT - ATTACHMENT_CBORE_DEPTH" in source
    assert "ATTACHMENT_CBORE_DIA" not in source
    assert "ATTACHMENT_SPACING" not in source


def test_source_records_exact_manual_photo_provenance() -> None:
    sources = "\n".join(
        (
            Path(spec.__file__).read_text(encoding="utf-8"),
            Path(part.__file__).read_text(encoding="utf-8"),
        )
    )
    assert "ch30_images/page003_img01.png" in sources
    assert "ch11_images/page002_img05.jpeg" in sources
    assert "page002_img06.jpeg" in sources
    assert "manually rederived" in sources


def test_part_exposes_semantic_mating_references() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    for name in (
        "ConeShaftNormal",
        "journal axis",
        "swing pivot",
        "mount east",
        "mount west",
    ):
        assert f'"{name}"' in source
    assert '_create_feature_cylinder_axis(' in source
    assert '"ConeShaftBoss",\n        CONE_BOSS_DIA / 2.0' in source
    assert '(("mount west", ATTACHMENT_X), ("mount east", -ATTACHMENT_X))' in source
    assert not hasattr(part, "CRANK_BORE_DX")
    assert not hasattr(part, "CRANK_BORE_Y")
    assert "HARVESTED_VOLUME_MM3" in source


def test_rotated_post_reverses_the_cone_shaft_axial_mate_side() -> None:
    assert not _seed_flip("cone-shaft axial d=22.01", 22.01)


def test_v2_feature_topology_uses_midplane_extrusions_and_hole_wizard() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert part.ATTACHMENT_HOLE_SPEC.kind == "counterbore_fillister"
    assert part.ATTACHMENT_HOLE_SPEC.size == "1/4"
    assert part.ATTACHMENT_HOLE_SPEC.overrides_mm == {
        "HoleDiameter": spec.ATTACHMENT_THRU_DIA,
        "CounterBoreDiameter": spec.ATTACHMENT_CBORE_DIA,
        "CounterBoreDepth": spec.ATTACHMENT_CBORE_DEPTH,
    }
    assert "_revolved_cylinder" not in source
    assert "create_revolve" not in source
    assert source.count("both_directions=True") == 2
    assert source.count('create_sketch("ConeShaftNormal")') == 2
    assert "angle=-INCLINE_DEG" in source
    assert 'HoleSpec(\n    "counterbore_fillister",\n    "1/4"' in source
    assert source.count("wizard_holes(") == 1
    assert "attachment_cut.placement_drive_jobs" in source
    assert 'name="AttachmentScrewHoles"' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rules 3-5: a machined casting is not on the
    # GD&T allowlist.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "_add_basic_value(",
    ):
        assert helper not in source, helper
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "SURFACE_FINISHES")


def test_only_the_fitted_diameters_print_three_decimals() -> None:
    assert drawing.DIMENSION_PRECISION == {
        "MainBodyDia": 3,
        "HeadDia": 3,
        "CrankBossDia": 3,
        "CrankBoreDia": 3,
    }
    assert drawing.DIMENSION_CALLOUTS == {"CrankBoreDia": "BORE THRU"}
    assert spec.TURNED_DIAMETER_TOLERANCE_MM == 0.05
    assert spec.CRANK_BORE_TOLERANCE_MM == 0.025


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.TOP_CENTER == (0.105, 0.235)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 1
    assert source.count("scale=(1, 2)") == 2


def test_bore_rim_com_scan_is_traced() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        '@_telemetry.traced("drawing.bore_rim_scan")\n'
        "def _bore_rim_edge"
    ) in source


def test_plan_view_label_is_placed() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        '"UPPER PLAN SCALE 1:2 (+X RIGHT, +Z DOWN)",\n'
        "        0.070,\n        0.263,"
    ) in source


def test_part_config_is_a_machined_casting() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-pivot-post")
    assert "A48" in str(config["material_specification"])
    assert "A48" in str(config["material"])
    assert "RAL 6005" in str(config["finish"])
    assert "SSPC-SP 3" in str(config["finish"])
    assert "50-75 um DFT" in str(config["finish"])
    assert "boss" in str(config["finish"]).lower()
    assert "cast + machined" in str(config["process"])
    assert int(config["quantity"]) == 1
