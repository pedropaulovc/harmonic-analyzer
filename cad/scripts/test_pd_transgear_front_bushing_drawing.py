"""Offline contracts for the transgear front bushing (MHA-PD-025) and its drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_pd_transgear_front_bushing as part
import draw_pd_transgear_front_bushing as drawing
import pd_paper_drive_assembly_steps as steps
import transgear_cluster_fit as fit
import pd_transgear_disc_hub_spec as hub
import pd_transgear_front_bushing_spec as spec
import pd_transgear_pin_spec as pin
import vn_transgear_retaining_ring_spec as ring
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-front-bushing.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-front-bushing.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-transgear-front-bushing_drawing.png")
    row = DRAWINGS_BY_NAME["pd_transgear_front_bushing"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.PROFILE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.PROFILE_KEEP)
    assert spec.REFERENCE_DIMENSIONS == {"RingLength"} < set(drawing.PROFILE_KEEP)


def test_the_chamfer_prints_a_max_the_ring_never_reaches() -> None:
    """The O.D. break prints as a single MAX limit (swTolMAX prints the
    nominal, so the nominal is the max); the MHA-VN-047 ring bears wholly on the
    flat inside the largest chamfer on the smallest O.D."""
    assert spec.FRONT_CHAMFER_TOL_TYPE == 6  # swTolType_e.swTolMAX
    assert spec.FRONT_CHAMFER_BAND[0] == 0.0 > spec.FRONT_CHAMFER_BAND[1]
    flat_dia_min = spec.OD - printed_band_mm(spec.OD_PLACES) - 2.0 * spec.FRONT_CHAMFER
    assert ring.OD < flat_dia_min
    assert drawing.DIMENSION_CALLOUTS["FrontChamferSize"].strip() == "X 45 DEG"


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


def test_the_rear_face_covers_the_hub_front_face_past_its_bore() -> None:
    """R9-68: the bushing traps the hub, so at the smallest printed O.D. its
    rear face reaches a millimetre past the hub's largest D-bore, and stays
    on the hub's front face (inside the smallest hub body)."""
    od_r_min = (spec.OD - printed_band_mm(spec.OD_PLACES)) / 2.0
    overlap = od_r_min - (hub.BORE_DIA + hub.BORE_BAND[0]) / 2.0
    assert spec.OD == pytest.approx(12.0) and spec.OD_PLACES == 1
    assert overlap >= 1.0
    assert spec.HUB_FACE_OVERLAP_WORST == pytest.approx(overlap)
    hub_r_min = (hub.HUB_DIA - printed_band_mm(hub.HUB_DIA_PLACES)) / 2.0
    assert (spec.OD + printed_band_mm(spec.OD_PLACES)) / 2.0 < hub_r_min


def test_the_unchanged_bushing_bears_on_the_smaller_d_flat_sleeve_nose() -> None:
    """The current steel nose still has a bearing face within the bushing's
    rear face at every size limit, with both title-block edge breaks paid.
    This is geometric contact, not a load or torque certification."""
    sleeve = fit.SLEEVE
    assert spec.BORE_DIA == sleeve.BORE_DIA == pin.DIA
    assert spec.BORE_DIA_BAND == sleeve.BORE_DIA_BAND == fit.BORE_DIA_BAND
    assert fit.BORE_DIAMETRAL_CLEARANCE == pytest.approx(
        (
            sleeve.BORE_DIA_BAND[1] - pin.DIA_BAND[0],
            sleeve.BORE_DIA_BAND[0] - pin.DIA_BAND[1],
        )
    )
    nose_r = (sleeve.BOSS_DIA + sleeve.BOSS_DIA_BAND[1]) / 2.0 - hub.EDGE_BREAK_MAX
    flat = (
        sleeve.FLAT_TO_AXIS + sleeve.FLAT_TO_AXIS_BAND[1] - hub.EDGE_BREAK_MAX
    )
    inner_r = max(
        spec.BORE_DIA + spec.BORE_DIA_BAND[0],
        sleeve.BORE_DIA + sleeve.BORE_DIA_BAND[0],
    ) / 2.0 + hub.EDGE_BREAK_MAX
    bushing_r = (spec.OD - printed_band_mm(spec.OD_PLACES)) / 2.0 - hub.EDGE_BREAK_MAX
    assert inner_r < flat < nose_r < bushing_r
    removed_cap = nose_r**2 * math.acos(flat / nose_r) - flat * math.sqrt(
        nose_r**2 - flat**2
    )
    bearing_area = math.pi * (nose_r**2 - inner_r**2) - removed_cap
    assert bearing_area > 0.0
    assert fit.HUB_NOSE_WINDOW[0] >= 0.0


def test_every_accepted_part_set_is_faced_from_the_blank() -> None:
    """The bushing is faced to the m it sets; the blank is long enough to
    face to the longest fit with one finishing cut left."""
    assert spec.GAP_MIN == fit.FRONT_BUSHING_FITTED_MIN
    assert spec.GAP_MAX == fit.FRONT_BUSHING_FITTED_MAX
    assert spec.GAP_MIN <= spec.LENGTH <= spec.GAP_MAX
    assert spec.BLANK_LENGTH_MIN >= spec.GAP_MAX + spec.FACING_ALLOWANCE - 1e-9
    # R9-68: the spigot on the step moves the window to 4.18-5.88 (the
    # step-to-nose chain); m read with hub and disc forward on the bushing
    # adds the hub's recess behind the nose, 5.98, so the blank is 6.10.
    assert (spec.GAP_MIN, spec.GAP_MAX) == pytest.approx((4.1767, 5.9783), abs=1e-4)
    assert spec.BLANK_LENGTH_MIN == pytest.approx(6.10)
    assert f"{spec.BLANK_LENGTH_MIN:.2f} MIN" in spec.DRAWING_NOTES
    callout = drawing.DIMENSION_CALLOUTS["RingLength"]
    assert f"{spec.GAP_MIN:.2f}-{spec.GAP_MAX:.2f}" in callout
    assert "FACED TO FIT" in callout


def test_the_length_callout_points_at_the_front_bushing_step() -> None:
    """m is set first, cluster forward, so the front bushing's step precedes
    the rear bushing's, and the sheet's pointer follows any renumbering."""
    assert drawing.FIT_STEP_KEY == "front-bushing-faced-to-fit"
    assert steps.step_number(drawing.FIT_STEP_KEY) < steps.step_number(
        "rear-bushing-faced-to-fit"
    )
    callout = drawing.DIMENSION_CALLOUTS["RingLength"]
    assert callout.endswith(f"PER {steps.step_ref(drawing.FIT_STEP_KEY)}")


def test_the_bore_and_both_end_faces_run_machined() -> None:
    """Rule 5: the bore runs on the pin, the faces bear (review of 6de7230aa:
    the running bore had no Ra)."""
    faces = {
        control.key: (control.roughness_um, control.face)
        for control in spec.SURFACE_FINISHES
    }
    assert set(faces) == {"bore", "nose_face", "ring_face"}
    assert {ra for ra, _ in faces.values()} == {MACHINED_UM}
    assert faces["bore"][1].diameter_mm == pin.DIA
    assert (tuple(faces["nose_face"][1].normal), faces["nose_face"][1].offset_mm) == (
        (0.0, 0.0, -1.0),
        0.0,
    )
    assert (
        tuple(faces["ring_face"][1].normal),
        faces["ring_face"][1].offset_mm,
    ) == ((0.0, 0.0, 1.0), spec.LENGTH)


def test_face_symbols_attach_to_their_own_end_of_the_lathe_profile() -> None:
    """The profile turns *Top a quarter turn, so model +Z runs LEFT: the nose
    face (z 0) is the right end, the ring face the left end.  Each pick lies
    on the flat, inside the chamfer's inner edge."""
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    centre_x = drawing.PROFILE_CENTER[0]

    def sheet_x(z_mm: float) -> float:
        return centre_x - (z_mm - spec.LENGTH / 2.0) * scale

    assert drawing.PROFILE_ANGLE == pytest.approx(-0.5 * 3.141592653589793)
    faces = {control.key: control.face for control in spec.SURFACE_FINISHES}
    for key, (pick, _symbol) in drawing.FACE_FINISHES.items():
        assert pick[0] == pytest.approx(sheet_x(faces[key].offset_mm))
        radius = abs(pick[1] - drawing.PROFILE_CENTER[1]) / scale
        assert spec.BORE_DIA / 2.0 < radius < spec.OD / 2.0 - spec.FRONT_CHAMFER


def test_the_bore_finish_lands_on_the_bore_circle_clear_of_the_od() -> None:
    """The end view shows the bore round: the leader lands on its circle,
    away from the Ø callout's upper-right landing, and the symbol (its ink
    grows about 15 mm right and 7 mm up at 2.5 mm text) clears the O.D.
    circle and the horizontal centre line."""
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    cx, cy = drawing.END_CENTER
    ax, ay = drawing.BORE_FINISH_ATTACH
    assert ((ax - cx) ** 2 + (ay - cy) ** 2) ** 0.5 == pytest.approx(
        spec.BORE_DIA * scale / 2.0
    )
    assert ax < cx and ay < cy
    sx, sy = drawing.BORE_FINISH_SYMBOL
    ink_right, ink_top = sx + 0.015, sy + 0.007
    assert ink_right < cx - spec.OD * scale / 2.0
    assert ink_top < cy


def test_sheet_text_stays_short() -> None:
    for text in (spec.DRAWING_NOTES, *drawing.DIMENSION_CALLOUTS.values()):
        lines = text.splitlines()
        assert len(lines) <= 4
        assert all(len(line) <= 70 for line in lines)


def test_registry_row_is_the_turned_brass_mha_181() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-025"
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
