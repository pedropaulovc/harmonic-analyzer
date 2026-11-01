"""Offline contracts for the rod pivot pin (MHA-CH-10) part and drawing.

The installed pressed pin under ``cad/docs/drawing-guidelines.md``
(user ruling 2026-10-09, PR #1292 review F1): three native model dimensions
whose places and limits the PART owns -- the diameter with its grind band and
its two fits flagged at the callout, the installed length as REFERENCE, and
the blank's cut length from a blanked reference sketch as a single MIN limit
(drawing-simplicity-policy.md `How the repository implements the guidelines`;
PR #1292 review N1: never note text; machinist review #1522) -- no GD&T, no
roughness symbol, and one note line: installed state, flush ends, removable.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_ch_rod_pivot_pin as part
import ch_connecting_rod_spec as rod
import ch_rod_pivot_pin_notes as notes
import ch_rod_pivot_pin_spec as spec
import draw_ch_rod_pivot_pin as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def _build_source() -> str:
    return Path(part.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-rod-pivot-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-rod-pivot-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-rod-pivot-pin_drawing.png")
    entry = DRAWINGS_BY_NAME["ch_rod_pivot_pin"]
    assert entry.script == Path(drawing.__file__).resolve()
    assert entry.part == "ch_rod_pivot_pin"
    assert part.PART_NAME == entry.artifact_stem == "ch-rod-pivot-pin"


def test_installed_model_is_flush_with_the_fork() -> None:
    assert spec.PIN_INSTALLED_LENGTH == rod.FORK_THICKNESS
    assert spec.PIN_END_PROUD_MAX == 0.0
    assert part.HALF_LEN == pytest.approx(rod.FORK_THICKNESS / 2.0)
    assert part.V_PIN == pytest.approx(
        math.pi * (spec.PIN_DIA / 2.0) ** 2 * rod.FORK_THICKNESS
    )
    build = _build_source()
    assert "Csk" not in build


def test_pin_axis_and_mid_plane_contract() -> None:
    build = _build_source()
    # Axis1 = part Z (Right x Top); symmetric about the Front Plane.
    assert 'name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0' in build
    assert '"origin", axis_line, "midpoint"' in build
    assert 'create_sketch("Right")' in build
    assert "RevolveParameters(angle=360.0)" in build
    assert "volume_check(" in build


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.RIGHT_KEEP) == marked == {"PinDia", "PinLen", "BlankLen"}
    assert notes.REFERENCE_DIMENSIONS == {"PinLen"}
    # Drawing-only data stays out of the spec the channel assembly imports.
    for name in ("DRAWING_DIMENSIONS", "DRAWING_PRECISION", "REFERENCE_DIMENSIONS"):
        assert not hasattr(spec, name), name
    assert not hasattr(drawing, "FRONT_KEEP")


def test_precision_and_band_are_authored_on_the_part() -> None:
    # The journal is the as-bought drill rod: no model band (its stock
    # fraction prints as a REFERENCE; the supplier's grind governs).
    assert "draw_ch_rod_pivot_pin.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "assert_imported_precision(" in source
    # A LINEAR reference: the plural helper forces a diameter glyph.
    assert "set_reference_dimensions(" not in source
    assert "set_reference_dimension(adapter, matches[0]" in source
    assert "hidden_sketches.curate_view_dimensions(" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _build_source()
    assert "require_saved_drawing_properties(" in _build_source()
    assert model_toleranced_dimensions(part) == {}


def test_blank_length_is_a_model_dimension_with_its_min_limit() -> None:
    """PR #1292 review N1 and machinist review #1522 (rule 4 (tighten only
    for function)): the cut length prints from a blanked reference sketch on
    the pin axis as a single MIN limit at one place, never from note text and
    never as a symmetric band -- its only job is to leave dressing stock."""
    assert spec.PIN_BLANK_LENGTH == 6.604  # .26 MIN
    assert spec.PIN_BLANK_LENGTH_TOL_TYPE == 5  # swTolType_e.swTolMIN
    assert not hasattr(spec, "PIN_BLANK_LENGTH_BAND")
    assert notes.DRAWING_DIMENSIONS["BlankReference"] == {"BlankLen"}
    build = "".join(_build_source().split())
    assert 'set_global(adapter,"BlankLen",f"{PIN_BLANK_LENGTH}mm")' in build
    assert 'blank.record("BlankLen",\'"BlankLen"\')' in build
    assert 'name_last_feature(adapter,"BlankReference")' in build
    assert '"origin",blank_line,"midpoint"' in build
    assert "tolerance.Type=PIN_BLANK_LENGTH_TOL_TYPE" in build
    assert "tolerance.SetValues(0.0,0.0)" in build
    assert 'blank_reference_sketches(adapter,("BlankReference",))' in build
    # The limit is set (the call, after its def) before the drawing marks are
    # cleared and re-applied.
    assert build.rindex("_blank_min_limit(adapter)") < build.index(
        "clear_dimensions_for_drawing(adapter)"
    )
    source = _source()
    assert '"BlankLen": "BLANK"' in source
    # The shortest blank still leaves dressing stock over the thickest fork.
    assert spec.BUDGET["blank_excess_min"] > 0.0


def test_print_carries_no_gdt_roughness_or_callouts() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "add_surface_finish(",
        "add_native_hole_callout(",
    ):
        assert helper not in source, helper
    # The dimension callouts are descriptive words below native values: the
    # journal's stock and fits, the installed reference's and the blank's
    # words. Nothing rides ABOVE: a line break there is stored but never
    # printed (ch_rod_pivot_pin r1 render).
    assert source.count("set_dimension_callouts(") == 1
    assert 'location="above"' not in source
    assert "author_part_pmi" not in _build_source()
    assert (
        "for view in (front, right, iso):\n        set_hidden_lines_removed" in source
    )
    assert "add_view_centerline(" in source


def test_journal_fits_hold_at_the_drill_rod_grind() -> None:
    """Machinist review #1522 (rules 4 and 7): the press and the running fit
    hold at the drill rod's own grind band."""
    assert spec.BUDGET["interference_min"] > 0.0
    assert spec.BUDGET["running_clearance_min"] > 0.0


def test_note_states_installed_state_and_flush_ends() -> None:
    lines = notes.DRAWING_NOTES.splitlines()
    assert len(lines) <= 4  # drawing-guidelines.md rule 7 (notes: few, flagged, never a method)
    assert lines == [
        "1. INSTALLED STATE SHOWN: BOTH ENDS DRESSED FLUSH WITH THE MHA-CH-03"
        " FORK FACES AT ASSEMBLY, NEVER PROUD.",
    ]
    text = notes.DRAWING_NOTES
    # drawing-simplicity-policy.md `How the repository implements the guidelines` and drawing-guidelines.md rule 7 (notes: few, flagged, never a method) (PR #1292 review N1): the blank's size and limit are the
    # BlankLen model dimension's, so no limit may ride the note text.
    for limit in (f"{spec.PIN_BLANK_LENGTH:g}", "MIN", "\u00b1", "+/-"):
        assert limit not in text, limit
    # The fits ride the Ø callout (#1522), so the note restates neither.
    for fit in ("PRESS IN", "PRESSED", "RUNS", "#47", "BLANK"):
        assert fit not in text, fit
    assert "PEEN" not in text and "#746" not in text
    assert "DRILL ROD" not in text  # the title-block MATERIAL owns the stock
    assert '"Manufacturing Notes": DRAWING_NOTES' in _build_source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()


def test_mating_part_numbers_on_the_sheet_are_live() -> None:
    assert _config.parts("ch-connecting-rod")["number"] == "MHA-CH-03"
    assert _config.parts("ch-rocker-arm")["number"] == "MHA-CH-06"
    import ch_rocker_arm_spec as arm

    assert str(arm.ROD_HOLE_SPEC.size).lstrip("#") == "47"


def test_sheet_runs_at_10_to_1_and_lands_clear_of_the_title_block() -> None:
    assert drawing.SHEET_SCALE == (10.0, 1.0)
    assert drawing.VIEW_SCALE == (10, 1)
    assert _source().count("scale=VIEW_SCALE") == 3
    (dia_x, dia_y) = drawing.RIGHT_KEEP["PinDia"]
    assert dia_y > drawing.RIGHT_CENTER[1] + drawing.HALF_DIA
    assert dia_x < drawing.RIGHT_CENTER[0] - 0.015  # off the centerline pick
    assert drawing.RIGHT_KEEP["PinLen"][1] < drawing.RIGHT_CENTER[1] - drawing.HALF_DIA
    assert drawing.RIGHT_KEEP["BlankLen"][1] < drawing.RIGHT_KEEP["PinLen"][1] - 0.010
    for x, y in (*drawing.RIGHT_KEEP.values(), drawing.NOTES_XY):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)
    assert (
        drawing.FRONT_CENTER[0] + drawing.HALF_DIA
        < drawing.RIGHT_CENTER[0] - drawing.HALF_LEN - 0.010
    )
    assert (
        drawing.RIGHT_CENTER[0] + drawing.HALF_LEN
        < drawing.ISO_CENTER[0] - drawing.HALF_LEN - 0.010
    )


def test_part_registry_row() -> None:
    config = _config.parts("ch-rod-pivot-pin")
    assert config["number"] == "MHA-CH-10"
    assert int(config["quantity"]) == 20
    assert config["tolerance_class"] == "machined_block"
    assert "fit_class" not in config
    assert config["process"] == (
        "cut from drill rod; pressed into the rod fork at assembly, ends dressed flush"
    )
    for field in ("material", "material_specification"):
        assert "drill rod" in str(config[field])
    assert "annealed" in str(config["material_specification"])
    assert len(str(config["material"])) <= 36
