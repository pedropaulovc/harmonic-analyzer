"""Offline contracts for the crank-arm drawing.

The print is the fleet's reference for cad/docs/drawing-simplicity-policy.md:
a pinned hand-crank lever carries no datums, frames, roughness symbols or
basic dimensions, and its notes are three lines of process fact.
"""

from __future__ import annotations

from pathlib import Path

import crank_arm_spec
import draw_crank_arm as drawing
import build_crank_arm as arm
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import NUMBER_DRILL_MM


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-arm_drawing.png")
    assert DRAWINGS_BY_NAME["crank_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map.  A rename in one script that isn't mirrored in the
    # other fails here, offline.
    assert arm.DRAWING_DIMENSIONS is crank_arm_spec.DRAWING_DIMENSIONS
    marked = set().union(*crank_arm_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    )
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.ARM_END_X, drawing.HALF_WIDTH) == (
        crank_arm_spec.ARM_END_X,
        crank_arm_spec.HALF_WIDTH,
    )


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = _source()
    assert "scale=(1, 1)" in source  # the isometric override
    assert crank_arm_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = crank_arm_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "STOCK" in notes  # the cleanup-cut licence (Lipton)
    # The drill sizes ride the hole callouts themselves, not the notes.
    assert "DRILL" not in notes
    # Nothing the title block or a dimension already says.
    for banned in ("UOS", "DIMENSIONS IN", "LINEAR +/-", "+/-", "DATUM", "MHA-", "BA "):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_hole_callouts_state_size_and_process() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["ShaftBoreDia"].startswith("REAM THRU")
    assert "3/8 IN" in callouts["ShaftBoreDia"]
    assert callouts["DimpleDia"] == "FLAT-BOTTOM 0.50 DEEP"  # .XX -> block tol
    assert crank_arm_spec.PIN_HOLE_DIA == NUMBER_DRILL_MM["#14"]
    source = _source()
    assert source.count("add_native_hole_callout(") == 2
    assert 'label="crank-arm cross-hole"' in source
    assert 'label="handle pivot hole"' in source
    # Harvey #13: the callout says DRILL; the drill number rides as its prefix.
    assert 'process="#14 DRILL"' in source
    assert 'process="15/64 DRILL"' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3-5: a pinned hand-crank lever is not
    # on the GD&T allowlist and nothing runs on its bore.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(crank_arm_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(crank_arm_spec, "GEOMETRIC_CONTROLS")
    assert crank_arm_spec.SURFACE_FINISHES == ()
    assert "surface_finishes=SURFACE_FINISHES" in Path(arm.__file__).read_text(
        encoding="utf-8"
    )


def test_only_the_reamed_bore_prints_three_decimals() -> None:
    source = _source()
    assert '{"ShaftBoreDia": 3}' in source
    assert crank_arm_spec.SHAFT_BORE_BAND == (0.05, 0.00)
    build_source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "set_dimension_bilateral_tolerance(" in build_source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, top, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_dimple_is_shown_where_it_is_visible() -> None:
    # The dimple is cut on the z=0 face, so the principal view is the *Back*
    # face and the edge-on view is *Top turned by pi (third angle from a back
    # principal); the side view is *Left.  A leader to a hidden circle was a
    # machinist-review clarity finding.
    source = _source()
    assert 'place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER' in source
    assert 'place_view(adapter, str(SOURCE), "*Left", *RIGHT_CENTER' in source
    assert "top.Angle = math.pi" in source
    # Model +X runs to the LEFT on a back view.
    assert drawing._sheet_x(10.0) < drawing._sheet_x(0.0)


def test_overall_length_is_a_conspicuous_reference() -> None:
    source = _source()
    assert 'label="overall length reference"' in source
    assert 'set_arc_endpoints_to_max(adapter, overall, label="overall length reference")' in source
    assert '_early_bound(overall, "IDisplayDimension").GetAnnotation()' in source
    assert crank_arm_spec.ARM_END_X + crank_arm_spec.HALF_WIDTH == 93.0


def test_one_origin_per_view_and_the_cross_hole_station() -> None:
    source = _source()
    assert 'label="shaft-to-handle-pivot location"' in source
    assert "pin_station = add_edge_dimension(" in source
    assert 'label="cross-hole station from broad face"' in source
    assert "find_edge_near(" in source
    assert crank_arm_spec.ARM_THICKNESS / 2.0 == 4.0
    assert crank_arm_spec.DIMPLE_X == 30.0
    assert '"DimpleX":' in source


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    assert "BoreProfile" not in arm.DRAWING_DIMENSIONS
    assert "PinHoleProfile" not in arm.DRAWING_DIMENSIONS
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert 'HoleSpec("drilled_fractional", "15/64")' in source
    assert 'HoleSpec("drilled_number", "#14")' in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("crank-arm")
    expected = "SAE 1018 CF bar, ASTM A108-24"
    assert spec["material"] == expected
    assert spec["material_specification"] == expected
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
