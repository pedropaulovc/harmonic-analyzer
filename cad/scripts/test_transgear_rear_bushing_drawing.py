"""Offline contracts for the transgear rear bushing (MHA-180) and its drawing."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import _config
import build_transgear_rear_bushing as part
import draw_transgear_rear_bushing as drawing
import paper_drive_assembly_steps as steps
import transgear_cluster_fit as fit
import transgear_pin_spec as pin
import transgear_rear_bushing_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-rear-bushing.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-rear-bushing.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-rear-bushing_drawing.png")
    row = DRAWINGS_BY_NAME["transgear_rear_bushing"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.PROFILE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.PROFILE_KEEP)
    assert set(drawing.PROFILE_KEEP) == set(spec.REFERENCE_DIMENSIONS)


def test_only_the_bore_carries_a_model_band() -> None:
    """The bore runs on the pin, so its reamed band lives on the model
    dimension.  The length is faced to fit at assembly: the model's is the
    nominal fit, never a toleranced make-to size."""
    assert model_toleranced_dimensions(part) == {
        ("RingProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)",
    }
    fitted = f"{spec.LENGTH:.2f}"
    assert fitted not in spec.DRAWING_NOTES
    assert fitted not in drawing.DIMENSION_CALLOUTS["RingLength"]


def test_the_bore_runs_on_the_pin_and_names_it() -> None:
    """Rule 2: the running-fit callout names the mate and its clearance;
    rule 7: the fit bore's process is REAM."""
    low, high = fit.BORE_DIAMETRAL_CLEARANCE
    assert 0.0 < low < high
    assert spec.BORE_DIA == pin.DIA
    assert spec.BORE_DIA_BAND == fit.BORE_DIA_BAND
    callout = drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert callout.splitlines()[0] == "REAM THRU"
    assert pin.PIN_NUMBER in callout
    assert f"{low:.3f}-{high:.3f}" in callout


def test_wall_holds_the_target_at_the_printed_worst_case() -> None:
    worst = (
        spec.OD
        - printed_band_mm(spec.OD_PLACES)
        - (spec.BORE_DIA + spec.BORE_DIA_BAND[0])
    ) / 2.0
    assert worst >= 2.0


def test_every_accepted_part_set_is_faced_from_the_blank() -> None:
    """The bushing is faced to the float it sets; the blank is long enough to
    face to the longest fit with one finishing cut left."""
    assert spec.GAP_MIN == fit.REAR_BUSHING_FITTED_MIN
    assert spec.GAP_MAX == fit.REAR_BUSHING_FITTED_MAX
    assert spec.GAP_MIN <= spec.LENGTH <= spec.GAP_MAX
    assert spec.BLANK_LENGTH_MIN >= spec.GAP_MAX + spec.FACING_ALLOWANCE - 1e-9
    assert f"{spec.BLANK_LENGTH_MIN:.2f} MIN" in spec.DRAWING_NOTES
    callout = drawing.DIMENSION_CALLOUTS["RingLength"]
    assert f"{spec.GAP_MIN:.2f}-{spec.GAP_MAX:.2f}" in callout
    assert "FACED TO FIT" in callout


def test_the_length_callout_points_at_the_rear_bushing_step() -> None:
    """The float is set after m, so the rear bushing's step follows the front
    bushing's, and the sheet's pointer follows any renumbering."""
    assert drawing.FIT_STEP_KEY == "rear-bushing-faced-to-fit"
    assert steps.step_number(drawing.FIT_STEP_KEY) == (
        steps.step_number("front-bushing-faced-to-fit") + 1
    )
    callout = drawing.DIMENSION_CALLOUTS["RingLength"]
    assert callout.endswith(f"PER {steps.step_ref(drawing.FIT_STEP_KEY)}")


def test_both_end_faces_run_machined() -> None:
    faces = {
        control.key: (control.roughness_um, control.face)
        for control in spec.SURFACE_FINISHES
    }
    assert set(faces) == {"arm_face", "sleeve_face"}
    assert {ra for ra, _ in faces.values()} == {MACHINED_UM}
    assert (tuple(faces["arm_face"][1].normal), faces["arm_face"][1].offset_mm) == (
        (0.0, 0.0, -1.0),
        0.0,
    )
    assert (
        tuple(faces["sleeve_face"][1].normal),
        faces["sleeve_face"][1].offset_mm,
    ) == ((0.0, 0.0, 1.0), spec.LENGTH)


def test_face_symbols_attach_to_their_own_end_of_the_lathe_profile() -> None:
    """The profile turns *Top a quarter turn, so model +Z runs LEFT: the arm
    face (z 0) is the right end, the sleeve face the left end."""
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


def test_sheet_text_stays_short() -> None:
    for text in (spec.DRAWING_NOTES, *drawing.DIMENSION_CALLOUTS.values()):
        lines = text.splitlines()
        assert len(lines) <= 4
        assert all(len(line) <= 70 for line in lines)


def test_registry_row_is_the_turned_brass_mha_180() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-180"
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
