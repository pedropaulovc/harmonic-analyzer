"""Offline contracts for the crank seat thrust washer (MHA-172) drawing."""

from __future__ import annotations

import ast
from pathlib import Path

import _config
import build_crank_seat_washer as part
import crank_seat_washer_spec as spec
import crankshaft_spec
import draw_crank_seat_washer as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-seat-washer.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-seat-washer.pdf")
    assert (
        DRAWINGS_BY_NAME["crank_seat_washer"].script == Path(drawing.__file__).resolve()
    )
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.SIDE_KEEP)
    assert set(drawing.DRAWING_PRECISION_BY_NAME) == marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }


def test_bore_and_thickness_carry_the_spec_bands() -> None:
    """The bore must pass the journal land and the thickness eats the boss
    float: both bands live on the model dimension, from the spec."""
    assert model_toleranced_dimensions(part) == {
        ("RingProfile", "BoreDia"): "*deviations(ID_BAND)",
        ("Disc", "DiscThick"): "THICKNESS_TOL",
    }
    assert spec.THICKNESS_BAND == (spec.THICKNESS_TOL, -spec.THICKNESS_TOL)


def test_smallest_bore_passes_the_largest_journal_land() -> None:
    """It goes on over the shaft's rear end, across the outboard journal."""
    bore_min = spec.ID + min(spec.ID_BAND)
    journal_max = crankshaft_spec.JOURNAL_DIA + max(crankshaft_spec.JOURNAL_DIA_BAND)
    assert bore_min - journal_max > 0.0
    # Rule 12 wall at the O.D.'s one-place title-block band.
    od_min = spec.OD - _config.title_block("linear_1pl")["value_in"] * 25.4
    assert (od_min - (spec.ID + max(spec.ID_BAND))) / 2.0 >= 2.0


def test_registry_row_is_the_turned_mha_172() -> None:
    row = _config.parts("crank-seat-washer")
    assert row["number"] == "MHA-172"
    assert int(row["quantity"]) == 1
    assert "1018" in row["material_specification"]
    assert row["tolerance_class"] == "machined_block"


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    """The drawing refuses a source part missing a required property (the
    r743-p1s-A failure on MHA-148); every one must be carried and non-blank."""
    import _common
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_common.part_properties(part.PART_NAME))
    stamp = _calls(part.__file__)["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args] == ["adapter", "PART_NAME"]
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
