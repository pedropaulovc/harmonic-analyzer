"""Offline contracts for the transgear rear bushing (MHA-PD-24) and its drawing."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import _config
import build_pd_transgear_rear_bushing as part
import draw_pd_transgear_rear_bushing as drawing
import transgear_cluster_fit as fit
import pd_transgear_pin_spec as pin
import pd_transgear_rear_bushing_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-rear-bushing.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-rear-bushing.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-transgear-rear-bushing_drawing.png")
    row = DRAWINGS_BY_NAME["pd_transgear_rear_bushing"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.PROFILE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.PROFILE_KEEP)
    assert spec.REFERENCE_DIMENSIONS == frozenset()
    assert set(drawing.PROFILE_KEEP) == {"RingLength"}


def test_the_bore_and_the_length_carry_model_bands() -> None:
    """The bore runs on the pin, so its reamed band lives on the model
    dimension; the length's band holds the shim count (#2124)."""
    assert model_toleranced_dimensions(part) == {
        ("RingProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)",
        ("Ring", "RingLength"): "LENGTH_BAND",
    }


def test_the_bore_runs_on_the_pin_and_names_it() -> None:
    """drawing-guidelines.md rule 4 (tighten only for function, and name the mate): the running-fit callout names the mate and its clearance;
    drawing-guidelines.md rule 12 (hole and slot callouts say what to do): the fit bore's process is REAM."""
    low, high = fit.BORE_DIAMETRAL_CLEARANCE
    assert 0.0 < low < high
    assert spec.BORE_DIA == pin.DIA
    assert spec.BORE_DIA_BAND == fit.BORE_DIA_BAND
    callout = drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert callout.splitlines()[0] == "REAM THRU"
    assert pin.PIN_NUMBER in callout
    assert f"{pin.inch_text(low, 4)}-{pin.inch_text(high, 4)}" in callout


def test_wall_holds_the_target_at_the_printed_worst_case() -> None:
    worst = (
        spec.OD
        - printed_band_mm(spec.OD_PLACES, unit=spec.UNIT)
        - (spec.BORE_DIA + spec.BORE_DIA_BAND[0])
    ) / 2.0
    assert worst >= WALL_TARGET_MM


def test_the_length_band_holds_the_float_open_and_the_count_to_four() -> None:
    """#2124: the shortest bushing leaves the unshimmed float over the floor;
    the longest gap takes no more than four of the thinnest shims, and the
    title block's .XXX row would take a fifth."""
    assert spec.LENGTH == fit.REAR_BUSHING_LENGTH
    assert spec.LENGTH_BAND == fit.REAR_BUSHING_LENGTH_BAND
    assert spec.DRAWING_PRECISION_BY_NAME["RingLength"] == fit.LENGTH_PLACES == 3
    assert fit.UNSHIMMED_FLOAT_RANGE[0] >= fit.END_FLOAT_MIN
    assert fit.SHIM_COUNT_RANGE[1] <= fit.SHIM_COUNT_MAX == 4
    row = printed_band_mm(3, unit=spec.UNIT)
    longest_at_row = fit.UNSHIMMED_FLOAT_RANGE[1] + row - spec.LENGTH_BAND
    assert (longest_at_row - fit.END_FLOAT_MIN) // fit.SHIM.THICKNESS_MIN > 4
    assert drawing.DIMENSION_CALLOUTS["RingLength"] == spec.LENGTH_CALLOUT


def test_only_the_sleeve_thrust_face_carries_a_finish() -> None:
    """The MHA-PD-10 sleeve turns on the front face; the arm face seats on
    the shims at the title block's finish."""
    (control,) = spec.SURFACE_FINISHES
    assert control.key == "sleeve_face"
    assert control.roughness_um == MACHINED_UM
    assert (tuple(control.face.normal), control.face.offset_mm) == (
        (0.0, 0.0, 1.0),
        spec.LENGTH,
    )
    assert set(drawing.FACE_FINISHES) == {"sleeve_face"}
    assert _config.parts("pd-transgear-feed-pinion")["number"] in (
        spec.THRUST_FACE_CAPTION
    )


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
    for text in drawing.DIMENSION_CALLOUTS.values():
        lines = text.splitlines()
        assert len(lines) <= 4
        assert all(len(line) <= 70 for line in lines)


def test_registry_row_is_the_turned_brass_mha_180() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-24"
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
    assert carried["Isometric View Note"] == spec.ISOMETRIC_VIEW_NOTE
    assert set(part._SAVED_DRAWING_PROPERTIES) <= set(required)
