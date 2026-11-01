"""Offline contracts for the transgear knob thrust ring (MHA-PD-15) drawing."""

from __future__ import annotations

import ast
import importlib.util
import math
from pathlib import Path

import pytest

import _config
import _printed_tolerance
import build_pd_transgear_knob_thrust_ring as part
import draw_pd_transgear_knob_thrust_ring as drawing
import pd_transgear_knob_thrust_ring_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from pd_cluster_stack_band import PRINTED_LENGTH_BAND, STACK_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith(
        "/slddrw/pd-transgear-knob-thrust-ring.SLDDRW"
    )
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-knob-thrust-ring.pdf")
    assert (
        DRAWINGS_BY_NAME["pd_transgear_knob_thrust_ring"].script
        == Path(drawing.__file__).resolve()
    )
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.SIDE_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    # The bore's process rides on the bore's own dimension, in the view that
    # carries it; the length's stack callout on the length, in the side view.
    # Each rides a dimension its feature marks.
    for feature, callouts in spec.DIMENSION_CALLOUTS.items():
        assert set(callouts) <= spec.DRAWING_DIMENSIONS[feature], feature
    assert set(spec.DIMENSION_CALLOUTS["RingProfile"]) <= set(drawing.END_KEEP)
    assert set(spec.DIMENSION_CALLOUTS["Ring"]) <= set(drawing.SIDE_KEEP)


def test_the_float_stop_carries_its_band_and_the_bore_takes_the_drilled_row() -> None:
    """The length is the forward stop of the knob's end float (contract §12):
    its band lives on the model dimension, from a named constant.  The bore
    (drilled, never under size) and the O.D. carry no band of their own: the
    DRILL THRU callout takes the title block's DRILLED HOLES row and the O.D.
    is governed by its places alone."""
    assert model_toleranced_dimensions(part) == {
        ("Ring", "RingLength"): "LENGTH_TOL",
    }
    assert spec.ID_BAND == (_printed_tolerance.drilled_oversize_mm(), 0.0)


def test_the_banded_length_names_the_stack_it_serves() -> None:
    """drawing-guidelines.md rule 4: a band tighter than the title block names
    the mating parts it serves, by drawing number."""
    shaft = _config.parts("pd-transgear-knob-shaft")["number"]
    plate = _config.parts("pd-transgear-arm-plate")["number"]
    assert spec.LENGTH_TOL < _printed_tolerance.printed_band_mm(spec.LENGTH_PLACES)
    assert spec.DIMENSION_CALLOUTS["Ring"] == {"RingLength": spec.LENGTH_CALLOUT}
    assert shaft in spec.LENGTH_CALLOUT and plate in spec.LENGTH_CALLOUT
    assert STACK_NAME in spec.LENGTH_CALLOUT


def test_the_drawing_reads_the_callouts_back_and_never_writes_them() -> None:
    """Text set from the drawing writes through to the built part (#1942): the
    part build authors every callout and the sheet only reads it back."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "SetText(" not in source
    assert "set_dimension_callouts" not in source
    assert "set_reference_dimensions" not in source
    assert "_author_dimension_callouts(adapter)" in Path(part.__file__).read_text(
        encoding="utf-8"
    )


def test_the_length_text_stands_clear_of_its_extension_lines() -> None:
    """The span between the faces is too short for the banded text; it stands
    right of the rear face's extension line, above the O.D.'s."""
    x, y = drawing.SIDE_KEEP["RingLength"]
    assert x > drawing._sheet_x(spec.LENGTH) + 0.025
    assert y > drawing.SIDE_CENTER[1] + spec.OD * drawing._S / 2000.0 + 0.020


def test_ring_bore_and_opposed_axial_faces_consume_the_new_interface() -> None:
    assert spec.ID == pytest.approx(6.05)
    assert spec.ID_BAND == pytest.approx((0.10, 0.0))
    assert spec.LENGTH == pytest.approx(5.2)
    assert (
        spec.LENGTH_TOL == pytest.approx(PRINTED_LENGTH_BAND) == pytest.approx(0.02)
    )
    assert part.V_RING == pytest.approx(
        math.pi * ((spec.OD / 2.0) ** 2 - (spec.ID / 2.0) ** 2) * spec.LENGTH
    )
    assert spec.DIMENSION_CALLOUTS["RingProfile"] == {"BoreDia": spec.BORE_CALLOUT}
    assert "DRILL" in spec.BORE_CALLOUT and "REAM" not in spec.BORE_CALLOUT
    assert drawing._sheet_x(spec.LENGTH) - drawing._sheet_x(0.0) == pytest.approx(
        spec.LENGTH * drawing._S / 1000.0
    )


def test_wall_holds_at_the_worst_case_the_sheet_prints() -> None:
    """drawing-guidelines.md rule 17 (walls and webs): the smallest O.D. its printed row accepts over the
    largest bore its band accepts."""
    od_band = _printed_tolerance.printed_band_mm(spec.OD_PLACES)
    worst = ((spec.OD - od_band) - (spec.ID + max(spec.ID_BAND))) / 2.0
    assert worst >= spec.WALL_FLOOR
    assert spec.WALL_WORST == pytest.approx(worst, abs=0.01)


def _ring_spec_fresh():
    fresh_spec = importlib.util.spec_from_file_location(
        "_ring_perturbed", spec.__file__
    )
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_the_wall_gate_refuses_a_coarser_printed_row(monkeypatch) -> None:
    # Positive control: the title block as it is.
    assert _ring_spec_fresh().WALL_WORST == pytest.approx(spec.WALL_WORST)
    # Negative control: an O.D. row loose enough to thin the wall under 2.0.
    monkeypatch.setattr(
        _printed_tolerance, "printed_deviations", lambda _value, _places: (-4.0, 4.0)
    )
    with pytest.raises(AssertionError, match="floor"):
        _ring_spec_fresh()


def test_the_od_prints_at_the_coarsest_row_its_wall_allows() -> None:
    """drawing-guidelines.md rule 17 (walls and webs): nothing fits on the O.D., so it prints at the title
    block's .X row once the wall holds there."""
    assert spec.worst_wall(1) >= spec.WALL_FLOOR
    assert spec.OD_PLACES == 1


def test_the_od_is_dimensioned_on_the_side_view_beside_the_rear_face() -> None:
    """drawing-guidelines.md rule 11 (turned parts read like the lathe), turned parts: the O.D. sits on the side view, so the
    end view carries one diameter (the bore's callout) and no two diameter
    lines cross its centre."""
    assert set(drawing.END_KEEP) - drawing.MOVED_TO_SIDE == set(
        spec.DIMENSION_CALLOUTS["RingProfile"]
    )
    assert drawing.MOVED_TO_SIDE == {"RingOd"}
    assert not drawing.MOVED_TO_SIDE & set(drawing.SIDE_KEEP)
    half_od = spec.OD * drawing._S / 2000.0
    rear_x = drawing._sheet_x(spec.LENGTH)
    od_x, od_y = drawing.OD_ON_SIDE
    assert abs(od_y - drawing.SIDE_CENTER[1]) < half_od
    # The rear face's finish symbol stands between the part and the O.D.'s
    # dimension line, inside its extension-line band.
    (pick_x, _pick_y), (symbol_x, symbol_y) = drawing.FACE_FINISHES["rear_face"]
    assert pick_x == pytest.approx(rear_x)
    assert rear_x < symbol_x < od_x - 0.025
    assert abs(symbol_y - drawing.SIDE_CENTER[1]) < half_od
    # The length dimension stays above the part, clear of the O.D.
    assert drawing.SIDE_KEEP["RingLength"][1] > drawing.SIDE_CENTER[1] + half_od


def test_registry_row_is_the_turned_brass_mha_156() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-15"
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
    """The drawing refuses a source part missing a required property; every
    one must be carried and non-blank."""
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
