"""Offline contracts for the pen adjuster stud build and drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import build_pn_pen_adjust_screw as part
import draw_pn_pen_adjust_screw as drawing
import pn_pen_adjust_screw_spec as spec
import pn_pen_rod_spec
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    drawing_specification_violations,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import HoleSpec, drill_process
from _holes import cross_hole_volume_mm3


def _source(module) -> str:
    return Path(module.__file__).read_text(encoding="utf-8")


def _calls(module, name: str) -> list[ast.Call]:
    tree = ast.parse(_source(module))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (getattr(node.func, "id", None) or getattr(node.func, "attr", None)) == name
    ]


def _literal_args(call: ast.Call) -> list[object]:
    return [arg.value for arg in call.args if isinstance(arg, ast.Constant)]


def _keyword(call: ast.Call, name: str) -> ast.expr:
    (value,) = (kw.value for kw in call.keywords if kw.arg == name)
    return value


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pn-pen-adjust-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pn-pen-adjust-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pn-pen-adjust-screw_drawing.png")
    entry = DRAWINGS_BY_NAME["pn_pen_adjust_screw"]
    assert entry.script == Path(drawing.__file__).resolve()
    assert entry.artifact_stem == part.PART_NAME


def test_spec_is_the_turned_brass_stud() -> None:
    assert spec.THREAD == pn_pen_rod_spec.STUD_THREAD == "#0-80"
    assert spec.THREAD_MAJOR == pytest.approx(1.524)
    assert spec.THREAD_LENGTH == 18.0
    assert (spec.HEAD_DIA, spec.HEAD_HEIGHT) == (5.0, 5.0)
    assert spec.EYE_SPEC == HoleSpec("drilled_number", "#54")
    assert spec.EYE_DIA == pytest.approx(1.397)
    assert spec.EYE_Y == pytest.approx(20.5)
    assert spec.OVERALL_LENGTH == pytest.approx(23.0)
    assert spec.THREAD_CALLOUT == "#0-80 UNF"


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert drawing.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert drawing.DRAWING_PRECISION_BY_NAME is spec.DRAWING_PRECISION_BY_NAME
    assert spec.DRAWING_DIMENSIONS == {
        "StudProfile": {"ThreadDia", "ThreadLength", "HeadDia", "HeadHeight"},
        "EyeStationReference": {"EyeY"},
    }
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == marked
    assert {
        feature: set(names) for feature, names in spec.DRAWING_PRECISION.items()
    } == spec.DRAWING_DIMENSIONS
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ThreadDia": 3,
        "ThreadLength": 1,
        "HeadDia": 1,
        "HeadHeight": 1,
        "EyeY": 1,
    }


def test_every_marked_dimension_is_created_and_named_by_the_build() -> None:
    """Each printed name is recorded on the sketch whose feature the spec keys
    it under, so mark_dimensions_for_drawing finds exactly that set."""
    source = _source(part)
    for name in ("ThreadDia", "ThreadLength", "HeadDia", "HeadHeight"):
        assert f'profile.record("{name}", ' in source
    assert 'station.record("EyeY", EYE_Y_EXPR)' in source
    assert 'drive_jobs += profile.apply(adapter, "StudProfile")' in source
    assert 'drive_jobs += station.apply(adapter, "EyeStationReference")' in source
    assert part.EYE_Y_EXPR == '"ThreadLength" + "HeadHeight" / 2'
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert "clear_dimensions_for_drawing(adapter)" in source
    assert (
        "mark_dimensions_for_drawing(adapter, feature_name, dimension_names)" in source
    )


def test_feature_names_are_the_contract() -> None:
    named = [_literal_args(call)[0] for call in _calls(part, "name_last_feature")]
    assert named == ["StudProfile", "Stud", "EyeStationPlane", "EyeStationReference"]
    (eye,) = _calls(part, "wizard_hole_on_cylinder")
    assert ast.literal_eval(_keyword(eye, "name")) == "EyeHole"
    assert ast.literal_eval(_keyword(eye, "point_planes")) == (
        "EyeStationPlane",
        "Front Plane",
    )
    assert ast.unparse(eye.args[1]) == "EYE_SPEC"
    # Radially into the head's cylinder at +X: the drill runs along X.
    assert ast.unparse(eye.args[2]) == "[HEAD_R, EYE_Y, 0.0]"
    (plane,) = _calls(part, "CreatePlaneParameters")
    assert ast.literal_eval(_keyword(plane, "base_plane")) == "Top Plane"
    assert ast.unparse(_keyword(plane, "offset")) == "EYE_Y"


def test_every_sketch_faces_the_side_view() -> None:
    """All marked dimensions live on Right-plane sketches: the *Right side
    view, which sees the X eye end-on, imports them natively."""
    source = _source(part)
    assert source.count('create_sketch("Right")') == 2
    assert 'create_sketch("Front")' not in source
    assert 'create_sketch("Top")' not in source
    draw_source = _source(drawing)
    assert '"*Right", *SIDE_CENTER, scale=VIEW_SCALE' in draw_source
    assert drawing.SIDE_VIEW_ANGLE == -math.pi / 2.0
    assert "RevolveParameters(angle=360.0)" in source
    assert len(_calls(part, "create_revolve")) == 1


def test_stud_axis_is_axis1_through_the_origin() -> None:
    (axis,) = _calls(part, "name_bore_axis")
    assert _literal_args(axis)[:4] == ["Front Plane", 0.0, "Right Plane", 0.0]
    assert 'if stud_axis != "Axis1":' in _source(part)


def test_volumes_are_analytic() -> None:
    r_thread, r_head = spec.THREAD_MAJOR / 2.0, spec.HEAD_DIA / 2.0
    stud = math.pi * (r_thread**2 * spec.THREAD_LENGTH + r_head**2 * spec.HEAD_HEIGHT)
    assert part.V_STUD == pytest.approx(stud)
    assert part.V_EYE == pytest.approx(
        cross_hole_volume_mm3(spec.EYE_DIA, spec.HEAD_DIA)
    )
    # The eye is smaller than the full drill cylinder through the head.
    assert part.V_EYE < math.pi * (spec.EYE_DIA / 2.0) ** 2 * spec.HEAD_DIA
    assert part.V_TOTAL == pytest.approx(stud - part.V_EYE)
    source = _source(part)
    assert 'volume_check(adapter, "stud", V_STUD,' in source
    assert 'volume_check(adapter, "eye cross hole", V_TOTAL,' in source
    assert '"cosmetic thread cuts nothing", driven, 1e-6' in source


def test_cosmetic_thread_runs_the_full_thread() -> None:
    (thread,) = _calls(part, "AddThreadParameters")
    assert ast.unparse(_keyword(thread, "edge_point")) == "[THREAD_R, 0.0, 0.0]"
    assert ast.unparse(_keyword(thread, "size")) == "THREAD"
    assert ast.unparse(_keyword(thread, "depth")) == "THREAD_LENGTH"
    assert "import_cosmetic_threads(adapter, iso)" in _source(drawing)


def test_no_gdt_no_pmi_no_roughness() -> None:
    """drawing-simplicity-policy.md rule 5: the stud is not on the GD&T
    allowlist; rule 6: nothing on it runs, slides or locates."""
    for module in (part, drawing):
        source = _source(module)
        for forbidden in (
            "author_part_pmi",
            "PART_DATUMS",
            "GEOMETRIC_CONTROLS",
            "_gtol",
            "add_datum_feature(",
            "add_feature_control_frame(",
            "set_basic_dimension",
            "add_surface_finish(",
            "SURFACE_FINISHES",
        ):
            assert forbidden not in source, (module.__name__, forbidden)
    assert model_toleranced_dimensions(part) == {}
    assert "add_view_centerline(" in _source(drawing)


def test_eye_prints_the_native_wizard_callout() -> None:
    (callout,) = _calls(drawing, "add_native_hole_callout")
    assert ast.unparse(_keyword(callout, "process")) == "drill_process(EYE_SPEC)"
    assert drill_process(spec.EYE_SPEC) == "#54 DRILL"
    assert "auto_center_marks(adapter, side, holes=True" in _source(drawing)


def test_thread_callout_and_notes() -> None:
    (note,) = _calls(drawing, "add_attached_note")
    assert ast.unparse(_keyword(note, "text")) == "THREAD_CALLOUT"
    notes = spec.DRAWING_NOTES
    assert len(notes.splitlines()) <= 4
    assert not any(character.isdigit() for character in notes)
    for title_block_word in (
        "DEBUR",
        "BREAK SHARP",
        "FINISH:",
        "MATERIAL:",
        "TOLERANCE",
    ):
        assert title_block_word not in notes.upper()
    assert '{"Manufacturing Notes": DRAWING_NOTES}' in _source(part)
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source(drawing)


def test_part_stamps_make_critical_properties() -> None:
    import _config

    source = _source(part)
    assert "apply_drawing_properties(" in source
    assert (
        "require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)" in source
    )
    assert "Manufacturing Notes" in part._SAVED_DRAWING_PROPERTIES
    assert part.MATERIAL == "Brass"
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PN-007"
    assert row["material"] == "Brass"
    assert "brass" in row["material_specification"].lower()
    assert row["finish"]
    assert "DEBUR" not in row["finish"].upper()
    assert int(row["quantity"]) == 1
    numbers = [str(other["number"]) for other in _config.parts().values()]
    assert numbers.count("MHA-PN-007") == 1


def test_the_part_owns_the_printed_precision() -> None:
    draw_source = _source(drawing)
    assert (
        "assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)"
        in draw_source
    )
    assert "draw_pn_pen_adjust_screw.py" in PRECISION_MIGRATED_DRAWINGS
    assert not drawing_specification_violations(draw_source, filename=drawing.__file__)


def test_side_view_layout_reads_like_the_lathe() -> None:
    """Threaded end left, head right; lengths below, the eye's station above,
    diameters clear of both rows; everything inside the B-size border."""
    assert drawing.SHEET_SCALE == (6.0, 1.0)
    assert '"*Isometric", *ISO_CENTER, scale=VIEW_SCALE' in _source(drawing)
    assert drawing.THREAD_END_X < drawing.SHOULDER_X < drawing.EYE_X < drawing.TOP_X
    assert drawing.TOP_X - drawing.THREAD_END_X == pytest.approx(
        spec.OVERALL_LENGTH * drawing._S
    )
    keep = drawing.SIDE_KEEP
    head_bottom = drawing.AXIS_Y - drawing.HEAD_HALF
    head_top = drawing.AXIS_Y + drawing.HEAD_HALF
    assert keep["ThreadLength"][1] == keep["HeadHeight"][1] < head_bottom
    assert (
        keep["ThreadLength"][1]
        < keep["ThreadDia"][1]
        < drawing.AXIS_Y - drawing.THREAD_HALF
    )
    assert keep["EyeY"][1] > head_top
    assert (
        drawing.AXIS_Y + drawing.THREAD_HALF
        < drawing.THREAD_NOTE_XY[1]
        < keep["EyeY"][1]
    )
    assert keep["HeadDia"][0] > drawing.TOP_X
    assert drawing.EYE_CALLOUT_XY[0] > drawing.TOP_X
    assert drawing.EYE_CALLOUT_XY[1] > head_top
    assert (
        drawing.THREAD_END_X > 0.020
        and drawing.EYE_CALLOUT_XY[0] < drawing.ISO_CENTER[0]
    )
    assert drawing.EYE_RIM_PICK == (drawing.EYE_X, drawing.AXIS_Y + drawing.EYE_HALF)
