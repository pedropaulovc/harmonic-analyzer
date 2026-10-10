"""Offline contracts for the crank seat thrust washer (MHA-DT-036) drawing."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

import _config
import build_dt_crank_seat_washer as part
import dt_crank_seat_washer_spec as spec
import dt_crankshaft_spec
import draw_dt_crank_seat_washer as drawing
import dt_drive_train_steps as steps
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-seat-washer.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-seat-washer.pdf")
    assert (
        DRAWINGS_BY_NAME["dt_crank_seat_washer"].script == Path(drawing.__file__).resolve()
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


def test_only_the_bore_carries_a_model_band() -> None:
    """The bore must pass the journal land, so its band lives on the model
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


def test_every_accepted_part_set_is_faced_from_the_blank_above_the_floor() -> None:
    """User ruling 2026-09-30: the washer is faced to the gap it fills and
    never goes under 0.5; the blank is thick enough to face to the widest gap
    any accepted MHA-DT-011, MHA-DT-010 and MHA-DT-005 leave."""
    assert spec.THICKNESS_FLOOR == 0.5
    assert spec.GAP_MIN >= spec.THICKNESS_FLOOR - 1e-9
    assert spec.GAP_MIN < spec.THICKNESS < spec.GAP_MAX
    assert spec.BLANK_THICKNESS_MIN >= spec.GAP_MAX + spec.FACING_ALLOWANCE - 1e-9
    # The sheet states the range it is faced to and where it is set.
    callout = drawing.DIMENSION_CALLOUTS["DiscThick"]
    assert f"{spec.GAP_MIN:.2f}-{spec.GAP_MAX:.2f}" in callout
    assert steps.step_ref(drawing.FIT_STEP_KEY) in callout
    assert drawing.FIT_STEP_KEY in steps.SEQUENCE
    assert f"{spec.BLANK_THICKNESS_MIN:.2f} MIN" in spec.DRAWING_NOTES


def _washer_spec_with(monkeypatch, module, name: str, value):
    """A fresh execution of the washer spec with one upstream value patched:
    the spec's own gate is observed, not re-derived here."""
    monkeypatch.setattr(module, name, value)
    fresh_spec = importlib.util.spec_from_file_location(
        "_washer_perturbed", spec.__file__
    )
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_the_floor_and_the_blank_refuse_a_fit_they_cannot_make(monkeypatch) -> None:
    # Positive control: the ruled collar re-executes clean.
    ruled = _washer_spec_with(
        monkeypatch, dt_crankshaft_spec, "COLLAR_LENGTH", dt_crankshaft_spec.COLLAR_LENGTH
    )
    assert ruled.GAP_MIN == pytest.approx(spec.GAP_MIN)
    # Negative control: the 10.3 collar the ruling shortened leaves the
    # thinnest fit under the floor.
    with pytest.raises(AssertionError, match="floor"):
        _washer_spec_with(monkeypatch, dt_crankshaft_spec, "COLLAR_LENGTH", 10.3)
    monkeypatch.undo()
    # Negative control: a blank whose low limit is under the widest gap.
    spec.check_fit_up(spec.GAP_MIN, spec.GAP_MAX, spec.GAP_MAX + spec.FACING_ALLOWANCE)
    with pytest.raises(AssertionError, match="facing allowance"):
        spec.check_fit_up(spec.GAP_MIN, spec.GAP_MAX, spec.GAP_MAX - 0.01)


def _crank_step_body() -> str:
    import draw_dt_drive_train_assembly as assembly

    number = steps.step_number("crank-mesh-checked")
    lines = assembly.CONE_CRANK_STEPS.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{number}. "))
    end = next(i for i, line in enumerate(lines) if line.startswith(f"{number + 1}. "))
    return " ".join(" ".join(lines[start:end]).split())


def test_the_fit_is_taken_before_the_washer_goes_on_and_the_pin_is_drilled() -> None:
    """MHA-DT-036 goes on over the shaft's rear end before the journal enters the
    bore, and MHA-DT-010's pin is match-drilled for good: the gap is measured in a
    trial fit without either, then the washer is faced, slid on and the parts
    refitted, and only then is the pin drilled."""
    import draw_dt_drive_train_assembly as assembly

    body = _crank_step_body()
    assert body.index(f"PER SHEET {assembly.CONTINUATION_SHEET}") < body.index("MATCH-DRILL")
    fit = " ".join(assembly.CRANK_WASHER_FIT_NOTES.split())
    assert f"STEP {steps.step_number('crank-mesh-checked')}" in fit
    order = ("WITHOUT MHA-DT-036", "MEASURE", "FACE MHA-DT-036", "FROM THE REAR", "SEATED")
    positions = [fit.index(phrase) for phrase in order]
    assert positions == sorted(positions)
    assert f"({spec.GAP_MIN:.2f}-{spec.GAP_MAX:.2f})" in fit


def test_smallest_bore_passes_the_largest_journal_land() -> None:
    """It goes on over the shaft's rear end, across the outboard journal."""
    bore_min = spec.ID + min(spec.ID_BAND)
    journal_max = dt_crankshaft_spec.JOURNAL_DIA + max(dt_crankshaft_spec.JOURNAL_DIA_BAND)
    assert bore_min - journal_max > 0.0
    # Rule 12 wall at the O.D.'s one-place title-block band.
    od_min = spec.OD - _config.title_block("linear_1pl")["value_in"] * 25.4
    assert (od_min - (spec.ID + max(spec.ID_BAND))) / 2.0 >= 2.0


def test_registry_row_is_the_turned_mha_172() -> None:
    row = _config.parts("dt-crank-seat-washer")
    assert row["number"] == "MHA-DT-036"
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
    r743-p1s-A failure on MHA-CH-009); every one must be carried and non-blank."""
    import _part_properties
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
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
