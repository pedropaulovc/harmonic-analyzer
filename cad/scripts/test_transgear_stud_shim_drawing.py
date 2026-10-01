"""Offline contracts for the transgear stud shim (MHA-178) drawing."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import _config
import build_transgear_stud_shim as part
import draw_transgear_stud_shim as drawing
import paper_drive_assembly_steps as steps
import transgear_stub_spec as stub
import transgear_stud_shim_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-stud-shim.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-stud-shim.pdf")
    assert (
        DRAWINGS_BY_NAME["transgear_stud_shim"].script
        == Path(drawing.__file__).resolve()
    )
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.SIDE_KEEP)
    assert set(drawing.DRAWING_PRECISION_BY_NAME) == marked
    assert drawing.DRAWING_PRECISION_BY_NAME == spec.DRAWING_PRECISION_BY_NAME
    assert set(drawing.SIDE_KEEP) == set(spec.REFERENCE_DIMENSIONS)


def test_only_the_bore_carries_a_model_band() -> None:
    """The bore must pass the #10-32 major, so its band lives on the model
    dimension.  The thickness is faced to fit at assembly: the model's is the
    nominal fit, never a toleranced make-to size."""
    assert model_toleranced_dimensions(part) == {
        ("RingProfile", "BoreDia"): "*deviations(ID_BAND)",
    }
    fitted = f"{spec.THICKNESS:.2f}"
    assert fitted not in spec.DRAWING_NOTES
    assert fitted not in drawing.DIMENSION_CALLOUTS["DiscThick"]


def test_the_bore_callout_names_its_drilled_process() -> None:
    """Rule 7: a hole callout states its process.  The +0.10/0 bore is the
    title block's DRILLED HOLES class, so it is drilled, not reamed."""
    assert drawing.DIMENSION_CALLOUTS["BoreDia"] == "DRILL THRU"
    assert spec.ID_BAND == (0.10, 0.0)


def test_smallest_bore_passes_the_thread_major() -> None:
    assert spec.ID + min(spec.ID_BAND) - stub.REAR_THREAD_MAJOR > 0.0
    assert spec.OD == stub.COLLAR_DIA


def test_every_accepted_part_set_is_faced_from_the_blank_above_the_floor() -> None:
    """R9-65: the shim is faced to the fit it carries, never under its floor;
    the blank is thick enough to face to the thickest fit."""
    assert spec.GAP_MIN >= spec.THICKNESS_FLOOR - 1e-9
    assert spec.GAP_MIN <= spec.THICKNESS <= spec.GAP_MAX
    assert spec.BLANK_THICKNESS_MIN >= spec.GAP_MAX + spec.FACING_ALLOWANCE - 1e-9
    callout = drawing.DIMENSION_CALLOUTS["DiscThick"]
    assert f"{spec.GAP_MIN:.2f}-{spec.GAP_MAX:.2f}" in callout
    assert drawing.FIT_STEP_KEY == "stud-faced-to-fit"
    assert drawing.FIT_STEP_KEY in steps.SEQUENCE
    assert callout.endswith(f"PER {steps.step_ref(drawing.FIT_STEP_KEY)}")
    assert f"{spec.BLANK_THICKNESS_MIN:.2f} MIN" in spec.DRAWING_NOTES


def test_the_floor_and_the_blank_refuse_a_fit_they_cannot_make() -> None:
    # Positive control: the accepted range and blank pass.
    spec.check_fit_up(spec.GAP_MIN, spec.GAP_MAX, spec.BLANK_THICKNESS_MIN)
    # Negative control: a fit under the floor.
    with pytest.raises(AssertionError, match="floor"):
        spec.check_fit_up(
            spec.THICKNESS_FLOOR - 0.01, spec.GAP_MAX, spec.BLANK_THICKNESS_MIN
        )
    # Negative control: a blank whose low limit leaves no facing allowance.
    with pytest.raises(AssertionError, match="facing allowance"):
        spec.check_fit_up(spec.GAP_MIN, spec.GAP_MAX, spec.GAP_MAX - 0.01)


def test_sheet_text_stays_short() -> None:
    for text in (
        spec.DRAWING_NOTES,
        *drawing.DIMENSION_CALLOUTS.values(),
    ):
        lines = text.splitlines()
        assert len(lines) <= 4
        assert all(len(line) <= 70 for line in lines)


def test_registry_row_is_the_turned_mha_178() -> None:
    row = _config.parts("transgear-stud-shim")
    assert row["number"] == "MHA-178"
    assert row["title"] == "Transgear Stud Shim"
    assert int(row["quantity"]) == 1
    assert "12L14" in row["material_specification"]
    assert row["tolerance_class"] == "machined_block"


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    """The drawing refuses a source part missing a required property; every
    one must be carried and non-blank."""
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
    assert [ast.unparse(a) for a in stamp.args] == [
        "adapter",
        "PART_NAME",
        "{'Manufacturing Notes': DRAWING_NOTES}",
    ]
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(
        None, part.PART_NAME, {"Manufacturing Notes": spec.DRAWING_NOTES}
    )
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
