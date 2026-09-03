"""Offline contracts for the v2 cone-pivot-post source and drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_pivot_post as part
import cone_gear_shaft_spec
import cone_pivot_post_spec as spec
import draw_cone_pivot_post as drawing
from _assembly import _seed_flip
from _drawing_contract import model_toleranced_dimensions
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
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | {"JournalBoreDia"}
    assert kept == marked
    assert marked == {
        "MainBodyDia",
        "MainBodyHt",
        "HeadDia",
        "HeadHt",
        "CrankAxisY",
        "CrankBossDia",
        "CrankBoreDia",
        "ConeBossLen",
        "JournalBoreDia",
    }
    # The crank boss and bore are leadered from BELOW the collar-height span,
    # which sits close on the right; the heights chain on the left.
    assert drawing.FRONT_KEEP["HeadHt"][0] == drawing.FRONT_CENTER[0] + 0.032
    assert drawing.FRONT_KEEP["CrankBoreDia"][1] < drawing._front_y(59.4)
    assert drawing.FRONT_KEEP["CrankBossDia"][1] < drawing.FRONT_KEEP["CrankBoreDia"][1]
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "ConeShaftBoss", ["ConeBossLen"])' in part_source


def test_inclined_journal_is_defined_in_an_axis_normal_section() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # The cut direction comes from the journal rim's circle axis on the model,
    # never from the sign of INCLINE_DEG (the build negates it against a
    # reversed plane).
    assert "journal_entity = _bore_rim_edge(adapter, front, diameter_mm=BORE_DIA)" in source
    assert "trace = _journal_trace(_journal_axis(journal_entity))" in source
    assert "section = _cut_journal_section(adapter, top, trace)" in source
    assert 'section_label="A"' in source
    assert "    INCLINE_DEG,\n" not in source  # not even imported
    # The bore imports into the section FIRST (one view per model dimension)
    # with its band on the model dimension; the axis height is a section
    # dimension from the foot; the boss is flagged from its rim as cast.
    assert source.index("view_label=\"section\"") < source.index("view_label=\"front\"")
    assert '"JournalBoreDia": (' in source
    assert "_add_journal_axis_height(adapter, section, trace)" in source
    assert 'set_arc_endpoints_to_center(adapter, display, label="journal axis height")' in source
    assert 'text=f"BOSS <MOD-DIAM>{CONE_BOSS_DIA:.2f} AS CAST"' in source
    assert "entity=boss_entity" in source
    # The prose journal definition and its four-decimal bore are gone.
    assert "JOURNAL <MOD-DIAM>" not in source
    assert "BORE_DIA:.4f" not in source
    assert not hasattr(spec, "JOURNAL_AXIS_POINTS")
    assert "SetBalloon" not in source
    assert drawing.SECTION_CENTER == (0.235, 0.145)
    assert drawing.SECTION_HALF_SPAN_MM > spec.HEAD_DIA / 2.0 + 10.0


def test_journal_bore_band_rides_the_model_dimension() -> None:
    # Bands only on the two running bores; the as-cast body, collar and crank
    # boss outside diameters carry none.
    assert spec.JOURNAL_BORE_BAND == (0.025, 0.000)
    assert spec.CRANK_BORE_TOLERANCE_MM == 0.025
    assert not hasattr(spec, "TURNED_DIAMETER_TOLERANCE_MM")
    assert model_toleranced_dimensions(part) == {
        ("CrankBoreProfile", "CrankBoreDia"): "CRANK_BORE_TOLERANCE_MM",
        ("JournalBoreProfile", "JournalBoreDia"): "*deviations(JOURNAL_BORE_BAND)",
    }
    # The shaft journal (h band) plus this bore band keep a running clearance.
    shaft_min = cone_gear_shaft_spec.JOURNAL_DIA + cone_gear_shaft_spec.SECTION_DIA_BAND[1]
    bore_min = spec.BORE_DIA + spec.JOURNAL_BORE_BAND[1]
    assert bore_min - cone_gear_shaft_spec.JOURNAL_DIA >= 0.05 - 1e-9
    assert bore_min > shaft_min


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "MACHINE THE FOOT SEAT" in notes
    assert "AS-CAST ELSEWHERE" in notes
    assert "BORE THE CRANK BORE" in notes
    assert "MOUNTING PAIR CENTRED ON THE POST AXIS" in notes
    # The swing angle prints ONE place (title-block +/-1 degree) and names the
    # section that is normal to the journal.
    assert "JOURNAL AXIS 12.5 DEG FROM THE CRANK BORE" in notes
    assert "SECTION A-A IS NORMAL TO IT" in notes
    # Material and paint/masking are title-block fields; sizes ride the views.
    for banned in (
        "A48", "CAST ASTM", "MASK", "DATUM", "BASIC", "+/-", "12.2808", "11.438",
        "11.50874", "26.88704", "12.518", "X.XX", "UOS",
    ):
        assert banned not in notes, banned
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.068)' in source


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


def test_only_the_fitted_bores_print_three_decimals() -> None:
    assert drawing.DIMENSION_PRECISION == {
        "MainBodyDia": 2,
        "HeadDia": 2,
        "CrankBossDia": 2,
        "CrankBoreDia": 3,
        "JournalBoreDia": 3,
    }
    assert drawing.DIMENSION_CALLOUTS == {
        "CrankBoreDia": "BORE THRU",
        "JournalBoreDia": "BORE THRU",
        "MainBodyDia": "BODY",
        "HeadDia": "COLLAR",
    }


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, top, section):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.TOP_CENTER == (0.105, 0.235)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 2  # elevation + section
    assert source.count("scale=(1, 2)") == 2


def test_bore_rim_com_scan_is_traced() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        '@_telemetry.traced("drawing.bore_rim_scan")\n'
        "def _bore_rim_edge"
    ) in source


def test_plan_view_label_is_placed() -> None:
    assert drawing.PLAN_LABEL_XY == (0.070, 0.263)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"UPPER PLAN SCALE 1:2 (+X RIGHT, +Z DOWN)",\n        *PLAN_LABEL_XY,' in source


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
