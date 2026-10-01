"""Offline contracts for the transgear pivot spacer (MHA-167) and its drawing."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import _config
import build_transgear_pivot_spacer as part
import draw_transgear_pivot_spacer as drawing
import transgear_pivot_spacer_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _surface_finish import MACHINED_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-pivot-spacer.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-pivot-spacer.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-pivot-spacer_drawing.png")
    row = DRAWINGS_BY_NAME["transgear_pivot_spacer"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.PROFILE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.PROFILE_KEEP)
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    # Every size is a "hold it" size: O.D. and bore under the .XXX row, the
    # length under its explicit band.
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {3}


def test_only_the_length_carries_a_band_on_the_model() -> None:
    """The pivot head play rides the length, so its band is a native model
    tolerance from the spec (policy rule 2).  The O.D. and the bore print at
    .XXX and the title block's row governs them; restating that row on the
    dimension is what policy rule 1 forbids."""
    assert model_toleranced_dimensions(part) == {
        ("Ring", "RingLength"): "LENGTH_BAND",
    }
    assert 0.0 < spec.LENGTH_BAND < _config.title_block("linear_3pl")["value_in"] * 25.4


def test_wall_bands_cover_the_printed_xxx_row() -> None:
    """The wall stack charges the O.D. and bore at least the .XXX row they
    print under, and the MIN the sheet states never rounds the worst case
    up (policy rule 12)."""
    row = _config.title_block("linear_3pl")["value_in"] * 25.4
    assert spec.OD_BAND >= row and spec.BORE_DIA_BAND >= row
    worst_at_row = (spec.OD - row - (spec.BORE_DIA + row)) / 2.0
    assert spec.WALL_WORST_PRINTED <= spec.WALL_WORST + 1e-9 <= worst_at_row + 1e-9
    assert 1.5 <= spec.WALL_WORST_PRINTED < 2.0


def test_sheet_notes_carry_the_wall_and_no_facing_step() -> None:
    """R9-6: the spacer is fitted as made, never faced."""
    lines = spec.DRAWING_NOTES.splitlines()
    assert f"WALL {spec.WALL_WORST_PRINTED:.2f} MIN." in lines
    assert not any("FACE" in line for line in lines)
    # The length and its band ride the dimension, never the note text.
    assert "±" not in spec.DRAWING_NOTES
    assert f"{spec.LENGTH:.3f}" not in spec.DRAWING_NOTES


def test_both_end_faces_run_machined_and_the_bore_carries_no_symbol() -> None:
    faces = {
        control.key: (control.roughness_um, control.face)
        for control in spec.SURFACE_FINISHES
    }
    assert set(faces) == {"front_face", "rear_face"}
    front_ra, front = faces["front_face"]
    rear_ra, rear = faces["rear_face"]
    assert front_ra == rear_ra == MACHINED_UM
    # Part frame: axis +Z, the bar-side face at z 0, the arm-side face at
    # z LENGTH (the RearFace plane).
    assert (tuple(front.normal), front.offset_mm) == ((0.0, 0.0, -1.0), 0.0)
    assert (tuple(rear.normal), rear.offset_mm) == ((0.0, 0.0, 1.0), spec.LENGTH)


def test_face_symbols_attach_to_their_own_end_of_the_lathe_profile() -> None:
    """The profile turns *Top a quarter turn, so model +Z runs LEFT: the front
    (bar) face is the right end, the rear (arm) face the left end.  A pick on
    the other end would hang the symbol on the wrong face."""
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    centre_x = drawing.PROFILE_CENTER[0]

    def sheet_x(z_mm: float) -> float:
        return centre_x - (z_mm - spec.LENGTH / 2.0) * scale

    assert drawing.PROFILE_ANGLE == pytest.approx(-0.5 * 3.141592653589793)
    faces = {control.key: control.face for control in spec.SURFACE_FINISHES}
    for key, (pick, _symbol) in drawing.FACE_FINISHES.items():
        assert pick[0] == pytest.approx(sheet_x(faces[key].offset_mm))
        radius = abs(pick[1] - drawing.PROFILE_CENTER[1]) / scale
        assert spec.BORE_DIA / 2.0 < radius < spec.OD / 2.0
    # Third angle: the end view seen from the +Z (left) end sits left of the
    # profile, on its axis.
    assert drawing.END_CENTER[0] < drawing.PROFILE_CENTER[0]
    assert drawing.END_CENTER[1] == drawing.PROFILE_CENTER[1]


def test_turned_part_diameters_follow_the_machinist() -> None:
    # Rule 7: the O.D. is moved onto the lathe profile; the bore, a solid
    # circle only end-on, keeps the end view.
    assert set(drawing.PROFILE_KEEP) == {"RingLength"}
    assert set(drawing.END_KEEP) == {"BoreDia", "RingOd"}
    profile_right = drawing.PROFILE_CENTER[0] + spec.LENGTH * drawing._S / 2.0
    assert drawing.OD_ON_PROFILE[0] > profile_right
    assert drawing.OD_ON_PROFILE[1] == drawing.PROFILE_CENTER[1]
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE {}:{}".format(
        *spec.ISOMETRIC_VIEW_SCALE
    )


def test_registry_row_is_the_turned_brass_mha_167() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-167"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"
    assert "fit_class" not in row


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    """The drawing refuses a source part missing a required property; every
    one must be carried and non-blank, and the notes the sheet links are the
    spec's."""
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
    assert set(part._SAVED_DRAWING_PROPERTIES) <= set(required)
