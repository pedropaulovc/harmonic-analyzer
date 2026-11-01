"""Offline contracts for the transgear front bushing (MHA-PD-25) and its drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

import pytest

import _config
import build_pd_transgear_front_bushing as part
import draw_pd_transgear_front_bushing as drawing
import transgear_cluster_fit as fit
from pd_cluster_stack_band import PRINTED_LENGTH_BAND_IN, STACK_NAME
import pd_transgear_disc_hub_spec as hub
import pd_transgear_front_bushing_spec as spec
import pd_transgear_pin_spec as pin
import pd_vn_transgear_retaining_ring_spec as ring
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _inch_wall_limits import WALL_TARGET_MM
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
    assert spec.REFERENCE_DIMENSIONS == frozenset()
    assert "RingLength" in drawing.PROFILE_KEEP


def test_the_chamfer_prints_a_max_the_ring_never_reaches() -> None:
    """The O.D. break prints as a single MAX limit (the modelled size is the
    max); the MHA-PD-VN-61 ring bears wholly on the flat inside the largest
    chamfer on the smallest O.D."""
    flat_dia_min = (
        spec.OD
        - printed_band_mm(spec.OD_PLACES, unit=spec.UNIT)
        - 2.0 * spec.FRONT_CHAMFER
    )
    assert ring.OD < flat_dia_min


def test_the_bore_and_the_printed_length_carry_model_bands() -> None:
    """The bore runs on the pin, so its reamed band lives on the model
    dimension; the length is a printed term of the disc cluster stack."""
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


def test_the_rear_face_covers_the_hub_front_face_past_its_bore() -> None:
    """R9-68: the bushing traps the hub, so at the smallest printed O.D. its
    rear face reaches a millimetre past the hub's largest D-bore, and stays
    on the hub's front face (inside the smallest hub body)."""
    od_r_min = (spec.OD - printed_band_mm(spec.OD_PLACES, unit=spec.UNIT)) / 2.0
    overlap = od_r_min - (hub.BORE_DIA + hub.BORE_BAND[0]) / 2.0
    assert spec.OD == pytest.approx(11.938) and spec.OD_PLACES == 2
    assert overlap >= 1.0
    assert spec.HUB_FACE_OVERLAP_WORST == pytest.approx(overlap)
    hub_r_min = (
        hub.HUB_DIA - printed_band_mm(hub.HUB_DIA_PLACES, unit=hub.UNIT)
    ) / 2.0
    od_r_max = (spec.OD + printed_band_mm(spec.OD_PLACES, unit=spec.UNIT)) / 2.0
    assert od_r_max < hub_r_min


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
    bushing_r = (
        spec.OD - printed_band_mm(spec.OD_PLACES, unit=spec.UNIT)
    ) / 2.0 - hub.EDGE_BREAK_MAX
    assert inner_r < flat < nose_r < bushing_r
    removed_cap = nose_r**2 * math.acos(flat / nose_r) - flat * math.sqrt(
        nose_r**2 - flat**2
    )
    bearing_area = math.pi * (nose_r**2 - inner_r**2) - removed_cap
    assert bearing_area > 0.0
    assert fit.RECESS_RANGE[0] >= 0.0


def test_the_length_is_a_printed_term_of_the_disc_cluster_stack() -> None:
    """#2038: printed 4 places, +/-.0007, named on the stack; nothing is faced
    to fit, set at assembly or supplied as a blank."""
    assert spec.LENGTH == fit.FRONT_BUSHING_LENGTH
    assert spec.LENGTH_BAND == fit.LENGTH_BAND == PRINTED_LENGTH_BAND_IN
    assert spec.LENGTH_PLACES == fit.LENGTH_PLACES == 4
    assert spec.DRAWING_PRECISION_BY_NAME["RingLength"] == 4
    assert "RingLength" not in spec.REFERENCE_DIMENSIONS
    callout = drawing.DIMENSION_CALLOUTS["RingLength"]
    assert callout == spec.LENGTH_CALLOUT
    assert STACK_NAME in callout
    sources = (
        Path(drawing.__file__).read_text(encoding="utf-8"),
        Path(part.__file__).read_text(encoding="utf-8"),
    )
    for text in (*drawing.DIMENSION_CALLOUTS.values(), *sources):
        for banned in ("FACED TO FIT", "SET AT ASSEMBLY", "SUPPLY", "step_ref"):
            assert banned not in text
    assert not hasattr(drawing, "FIT_STEP_KEY")
    assert not hasattr(spec, "DRAWING_NOTES")


def test_the_bore_and_both_end_faces_run_machined() -> None:
    """drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the bore runs on the pin, the faces bear (review of 6de7230aa:
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


def test_each_face_symbol_names_its_thrust_mate() -> None:
    """Machinist review: an end-face Ra 1.6 with no stated function reads as
    over-specification.  Each face's symbol names the part it thrusts on."""
    targets = {
        control.key: control.production_method for control in spec.SURFACE_FINISHES
    }

    def names(text: str, number: str) -> bool:
        return re.search(rf"(?<![\w-]){re.escape(number)}(?![\w-])", text) is not None

    assert names(targets["nose_face"], hub.SLEEVE_NUMBER)
    assert names(targets["ring_face"], pin.RING_NUMBER)
    assert pin.RING_NUMBER == _config.parts("pd-vn-transgear-retaining-ring")["number"]


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
    for text in drawing.DIMENSION_CALLOUTS.values():
        lines = text.splitlines()
        assert len(lines) <= 4
        assert all(len(line) <= 70 for line in lines)


def test_registry_row_is_the_turned_brass_mha_181() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-25"
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
