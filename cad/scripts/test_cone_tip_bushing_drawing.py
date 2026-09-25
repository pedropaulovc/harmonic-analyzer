"""Offline behavioral contracts for the cone-tip-bushing drawing."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import _config
import build_cone_tip_bushing as part
import cone_gear_shaft_spec
import cone_tip_bushing_spec as spec
import draw_cone_tip_bushing as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths_and_registry_entry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-tip-bushing.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-tip-bushing.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-tip-bushing_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_tip_bushing"].script == Path(drawing.__file__).resolve()
    )


def test_part_and_drawing_share_the_native_dimension_contract() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.END_KEEP) | set(drawing.SIDE_KEEP)
    assert kept == marked == {"ODDim", "BoreDiaDim", "Depth"}
    assert drawing.DIMENSION_CALLOUTS == {"BoreDiaDim": "REAM THRU"}
    assert spec.OUTER_DIA == part.OD
    assert spec.BORE_DIA == part.BORE_DIA
    assert spec.LENGTH == part.LENGTH


def test_model_owns_the_printed_precision() -> None:
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ODDim": 1,
        "BoreDiaDim": 3,
        "Depth": 1,
    }
    assert "draw_cone_tip_bushing.py" in PRECISION_MIGRATED_DRAWINGS


def test_bore_band_is_derived_live_from_the_enlarged_tip_journal_and_fit() -> None:
    assert _config.parts("cone-tip-bushing")["fit_class"] == "shaft_in_bushing"
    minimum, maximum = _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
    journal_upper, journal_lower = cone_gear_shaft_spec.SECTION_DIA_BANDS[-1]
    assert spec.BORE_DIA == pytest.approx(1.5875)
    assert spec.BORE_DIA == pytest.approx(cone_gear_shaft_spec.SECTION_DIAS[-1])
    assert part.BORE_DIA_BAND == (
        pytest.approx(journal_lower + maximum),
        pytest.approx(journal_upper + minimum),
    )
    bore_upper, bore_lower = part.BORE_DIA_BAND
    assert bore_lower - journal_upper == pytest.approx(minimum)
    assert bore_upper - journal_lower == pytest.approx(maximum)


def test_enlarged_journal_leaves_a_practical_plain_bushing_wall() -> None:
    radial_wall = (spec.OUTER_DIA - spec.BORE_DIA) / 2.0
    assert radial_wall > spec.BORE_DIA
    assert spec.LENGTH > spec.BORE_DIA
    assert not hasattr(spec, "LENGTH_TOLERANCE_MM")
    assert [name for name in dir(part) if name.endswith("_BAND")] == [
        "BORE_DIA_BAND"
    ]


def test_note_identifies_the_mate_and_required_fit_without_a_duplicate_size() -> None:
    text = spec.DRAWING_NOTES
    assert len(text.splitlines()) == 1
    assert len(text) <= 90
    assert "SLIP-FITS" in text
    assert spec.SHAFT_MATE_NUMBER in text
    assert spec.SHAFT_MATE_NUMBER == _config.parts("cone-gear-shaft")["number"]
    stripped = text.replace(spec.SHAFT_MATE_NUMBER, "")
    assert not any(character.isdigit() for character in stripped)
    for method_or_duplicate in (
        "BELL-MOUTH",
        "ONE SETUP",
        "DRILL",
        "REAM",
        "1/16",
        "1.588",
    ):
        assert method_or_duplicate not in text


def test_no_gdt_and_only_the_running_bore_has_a_surface_finish() -> None:
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")
    assert not hasattr(spec, "PART_DATUMS")
    assert [control.key for control in spec.SURFACE_FINISHES] == ["bushing_bore"]
    assert spec.SURFACE_FINISHES[0].face.diameter_mm == spec.BORE_DIA


def test_sheet_scale_and_layout_keep_every_annotation_clear() -> None:
    assert drawing.SHEET_SCALE == (8.0, 1.0)
    assert drawing.VIEW_SCALE == (8, 1)
    outer_radius = spec.OUTER_DIA * 8 / 2000.0
    half_length = spec.LENGTH * 8 / 2000.0
    assert drawing.OUTER_R == pytest.approx(outer_radius)
    for name, (x, _y) in drawing.END_KEEP.items():
        assert abs(x - drawing.END_CENTER[0]) > outer_radius + 0.004, name
    for name, (x, _y) in drawing.SIDE_KEEP.items():
        assert x > drawing.SIDE_CENTER[0] + outer_radius + 0.004, name
    for x, y in (
        *drawing.END_KEEP.values(),
        *drawing.SIDE_KEEP.values(),
        drawing.MANUFACTURING_NOTES_POS,
    ):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070)
    assert drawing.END_CENTER[0] + outer_radius < drawing.SIDE_CENTER[0] - outer_radius
    assert drawing.SIDE_CENTER[0] + outer_radius < drawing.ISO_CENTER[0] - half_length


def test_od_moves_to_the_side_view_and_the_end_view_keeps_one_diametric_callout() -> None:
    # Policy rule 7: turned diameters on the side view.  The OD is imported on
    # its sketch-plane view and dragged, so the end view's only diametric
    # dimension is the reamed bore and no two leaders cross at the centre.
    half_length = spec.LENGTH * 8 / 2000.0
    assert drawing.HALF_LENGTH == pytest.approx(half_length)
    od_x, od_y = drawing.SIDE_OD_XY
    assert od_x == pytest.approx(drawing.SIDE_CENTER[0])
    assert od_y > drawing.SIDE_CENTER[1] + half_length + 0.006
    bore_x, bore_y = drawing.END_KEEP["BoreDiaDim"]
    od_donor_x, od_donor_y = drawing.END_KEEP["ODDim"]
    # The donor text sits on the opposite quadrant from the bore callout.
    assert od_donor_x < drawing.END_CENTER[0] < bore_x
    assert bore_y < drawing.END_CENTER[1] < od_donor_y
    # ~33 mm wide bore text, centred on its x: clear of the OD circle and the
    # side view.
    assert bore_x - 0.0165 > drawing.END_CENTER[0] + drawing.OUTER_R + 0.004
    assert bore_x + 0.0165 < drawing.SIDE_CENTER[0] - drawing.OUTER_R - 0.004
    # Finish glyph above the bore callout, right of the OD circle.
    finish_x, finish_y = drawing.BORE_FINISH_XY
    assert finish_x > drawing.END_CENTER[0] + drawing.OUTER_R
    assert finish_y > bore_y + 0.020
    # The fit note stays under the lowest view feature.
    assert (
        drawing.MANUFACTURING_NOTES_POS[1]
        < min(drawing.END_CENTER[1] - drawing.OUTER_R, bore_y - 0.010) - 0.010
    )


def test_part_registry_values_remain_the_title_block_source() -> None:
    config = _config.parts("cone-tip-bushing")
    assert config["number"] == "MHA-096"
    assert config["material_specification"] == "C36000 free-machining brass"
    assert int(config["quantity"]) == 1


def _dimension_rows(node: object):
    """Yield every table row (a list whose first cell is text) in the record."""
    if isinstance(node, dict):
        for value in node.values():
            yield from _dimension_rows(value)
    elif isinstance(node, list):
        if node and isinstance(node[0], str):
            yield node
        for value in node:
            yield from _dimension_rows(value)


def test_dimensions_record_carries_the_bushing_bore() -> None:
    # Codex (#811): the tip-journal row moved to 1/16 in while the bushing's
    # own row still printed the retired 1/32 in (0.79) bore.
    record = yaml.safe_load(
        (Path(part.__file__).resolve().parents[1] / "config" / "dimensions.yaml")
        .read_text(encoding="utf-8")
    )
    rows = [
        row
        for row in _dimension_rows(record)
        if row[0].startswith("`cone-tip-bushing`")
    ]
    assert len(rows) == 1
    assert rows[0][1] == (
        f"brass sleeve Ø{spec.OUTER_DIA:g} × {spec.LENGTH:g}, "
        f"Ø{spec.BORE_DIA + 1e-9:.3f} (1/16\") bore"
    )
