"""Offline contracts for the transgear hub cap (MHA-160) and its drawing."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import _config
import build_transgear_hub_cap as part
import draw_transgear_hub_cap as drawing
import transgear_hub_cap_spec as spec
import transgear_stub_spec as stud
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout

SW_TOL_MAX = 6  # swTolType_e.swTolMAX


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-hub-cap.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-hub-cap.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-hub-cap_drawing.png")
    row = DRAWINGS_BY_NAME["transgear_hub_cap"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_prints_in_exactly_one_view() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FACE_KEEP) | set(drawing.SECTION_KEEP) == marked
    assert not set(drawing.FACE_KEEP) & set(drawing.SECTION_KEEP)
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }


def test_no_size_restates_a_title_block_band_on_the_model() -> None:
    """Every size prints its places; the chamfer's single MAX limit is not a
    band and rides its own setter."""
    assert model_toleranced_dimensions(part) == {}


def test_front_chamfer_prints_a_max_that_clears_the_spanner_holes() -> None:
    assert spec.FRONT_CHAMFER_TOL_TYPE == SW_TOL_MAX
    assert spec.FRONT_CHAMFER == spec.FRONT_CHAMFER_MAX
    assert spec.CHAMFER_INNER_EDGE_R_MIN > spec.SPANNER_HOLE_OUTER_EDGE_R_MAX
    assert spec.SPANNER_HOLE_INNER_EDGE_R_MIN > spec.CSK_DIA_MAX / 2.0


def test_cap_threads_onto_the_stud_and_seats_on_its_shoulder() -> None:
    assert spec.TAP_SPEC.size == stud.FRONT_THREAD
    # The stud's thread runs past the cap's worst-case engaged length even at
    # its shortest, so the cap (not the stud) bounds the engagement.
    assert stud.FRONT_THREAD_END_MIN > spec.CAP_LENGTH_MIN - spec.CSK_LOSS_MAX
    assert spec.REAR_FACE_MACHINE_Z == pytest.approx(
        stud.ARM_SEAT_MACHINE_Z - stud.CAP_SHOULDER_STATION
    )


def test_engagement_stack_charges_the_relief_and_the_countersink() -> None:
    nominal = (
        spec.CAP_LENGTH
        - stud.RELIEF_WIDTH
        - (spec.CSK_DIA - stud.FRONT_THREAD_MAJOR) / 2.0
    )
    worst = (
        spec.CAP_LENGTH_MIN
        - stud.RELIEF_WIDTH_MAX
        - (spec.CSK_DIA_MAX - stud.FRONT_THREAD_MAJOR) / 2.0
    )
    assert spec.ENGAGEMENT_NOMINAL == pytest.approx(nominal, abs=1e-6)
    assert spec.ENGAGEMENT_WORST == pytest.approx(worst, abs=1e-6)
    # Short of 1.5D: the policy's named exception carries it at the approved
    # floor.
    assert (
        spec.APPROVED_ENGAGEMENT_FLOOR_D
        <= spec.ENGAGEMENT_WORST_D
        < spec.ENGAGEMENT_NOMINAL_D
        < 1.5
    )


def test_sheet_notes_state_the_spec_engagement_and_webs() -> None:
    notes = spec.DRAWING_NOTES
    assert f"{spec.ENGAGEMENT_NOMINAL_D_PRINTED:.2f}D NOMINAL" in notes
    assert f"{spec.ENGAGEMENT_WORST_D_PRINTED:.2f}D MIN" in notes
    assert f"THREAD {spec.TAP_WEB_WORST_PRINTED:.2f} MIN" in notes
    assert f"O.D. {spec.OD_WEB_WORST_PRINTED:.2f} MIN" in notes
    # A MIN never rounds up past the arithmetic.
    assert spec.ENGAGEMENT_WORST_D_PRINTED <= spec.ENGAGEMENT_WORST_D
    assert spec.TAP_WEB_WORST_PRINTED <= spec.TAP_WEB_WORST + 1e-9
    assert spec.OD_WEB_WORST_PRINTED <= spec.OD_WEB_WORST + 1e-9


def test_registry_row_is_the_turned_brass_mha_160() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-160"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
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
    assert [ast.unparse(a) for a in stamp.args[:2]] == ["adapter", "PART_NAME"]
    extra = {
        ast.literal_eval(key): getattr(part, value.id)
        for key, value in zip(stamp.args[2].keys, stamp.args[2].values, strict=True)
    }
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
    assert carried["Manufacturing Notes"] == spec.DRAWING_NOTES
    assert carried["Isometric View Note"] == spec.ISOMETRIC_VIEW_NOTE
