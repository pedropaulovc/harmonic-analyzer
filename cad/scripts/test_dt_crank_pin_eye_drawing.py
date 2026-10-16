"""Offline contracts for the keeper-chain anchor eye (MHA-DT-028) part and drawing.

A ``visual_noncritical`` formed-wire eye under ``cad/docs/drawing-guidelines.md``
(#1076): three native model dimensions whose places the PART owns -- the
loop's inside diameter and the tail's length from a blanked reference sketch
in the eye's plane, and the wire as REFERENCE -- every one at the title
block's one place, no GD&T, no roughness symbol, and at most four note lines.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_dt_crank_pin_eye as part
import dt_crank_pin_eye_notes as notes
import dt_crank_pin_eye_spec as spec
import draw_dt_crank_pin_eye as drawing
import vn_keeper_chain_spec as chain
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def _build_source() -> str:
    return Path(part.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-pin-eye.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-pin-eye.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crank-pin-eye_drawing.png")
    entry = DRAWINGS_BY_NAME["dt_crank_pin_eye"]
    assert entry.script == Path(drawing.__file__).resolve()
    assert entry.part == "dt_crank_pin_eye"
    assert part.PART_NAME == entry.artifact_stem == "dt-crank-pin-eye"


def test_printed_sizes_derive_from_the_eye_spec() -> None:
    assert notes.LOOP_ID == pytest.approx(2.0 * spec.LOOP_R - spec.WIRE_DIA)
    assert notes.LOOP_ID == pytest.approx(3.3)


def test_bead_chain_passes_the_smallest_printed_loop() -> None:
    # The loop's callout says the bead chain passes freely: the loop must
    # admit a bead at the title block's lower limit for the places it prints
    # at, not just at nominal (drawing-guidelines.md: controlled limits must
    # produce the fit).
    places = notes.DRAWING_PRECISION_BY_NAME["LoopID"]
    band = float(str(_config.title_block(f"linear_{places}pl")["display"]).lstrip("±"))
    smallest = round(notes.LOOP_ID, places) - band
    assert spec.LOOP_ID_MIN == pytest.approx(smallest)
    assert (smallest - chain.BEAD_DIA) / 2.0 >= chain.EYE_BEAD_PASS_AIR


def test_marked_dimension_set_lives_in_the_notes_module() -> None:
    assert part.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    assert notes.DRAWING_DIMENSIONS == {
        "WireProfile": {"WireDia"},
        "EyeReference": {"LoopID", "TailLen"},
    }
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) | set(drawing.TOP_KEEP) == marked
    assert not set(drawing.SIDE_KEEP) & set(drawing.TOP_KEEP)
    assert notes.REFERENCE_DIMENSIONS == {"WireDia"}
    assert set(notes.DIMENSION_CALLOUTS) <= marked
    for name in ("DRAWING_DIMENSIONS", "DRAWING_PRECISION", "DRAWING_NOTES"):
        assert not hasattr(spec, name), name


def test_precision_is_authored_on_the_part_at_the_title_block_place() -> None:
    assert notes.DRAWING_PRECISION_BY_NAME == {"WireDia": 1, "LoopID": 1, "TailLen": 1}
    assert "draw_dt_crank_pin_eye.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "assert_imported_precision(" in source
    assert "hidden_sketches.curate_view_dimensions(" in source
    assert (
        "set_reference_dimensions(adapter, annotations, REFERENCE_DIMENSIONS)" in source
    )
    build = _build_source()
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in build
    assert "require_saved_drawing_properties(" in build
    assert model_toleranced_dimensions(part) == {}


def test_eye_reference_sketch_carries_loop_and_tail() -> None:
    build = "".join(_build_source().split())
    assert 'create_sketch("Right")' in build
    assert 'names=("LoopCx",None,"LoopID")' in build
    assert 'drives=(\'"LoopR"\',None,\'2*"LoopR"-"WireDia"\')' in build
    # The tail is measured from the loop centre to its end, along its axis.
    assert (
        'f"{loop_inside}.center",f"{tail_axis}.end","vertical_distance",TAIL_LEN'
        in build
    )
    assert 'ref.record("TailLen",\'"TailLen"\')' in build
    assert 'name_last_feature(adapter,"EyeReference")' in build
    assert 'blank_reference_sketches(adapter,("EyeReference",))' in build


def test_side_view_geometry_matches_the_part_frame() -> None:
    # Right view: sheet x runs along model -Z, so the loop centre (Z = -LoopR)
    # is right of the tail (Z = 0) by LoopR, and the tail's end is TailLen
    # above the loop centre.
    s = drawing._S
    assert drawing.LOOP_CENTER_XY[0] - drawing.TAIL_END_XY[0] == pytest.approx(
        spec.LOOP_R * s
    )
    assert drawing.TAIL_END_XY[1] - drawing.LOOP_CENTER_XY[1] == pytest.approx(
        spec.TAIL_LEN * s
    )
    assert drawing.LOOP_CENTER_XY[0] == pytest.approx(drawing.SIDE_CENTER[0])


def test_print_carries_no_gdt_roughness_or_hole_callouts() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "add_surface_finish(",
        "add_native_hole_callout(",
    ):
        assert helper not in source, helper
    assert "for view in (side, top, iso):\n        set_hidden_lines_removed" in source
    assert '"*Isometric"' in source


def test_notes_are_few_and_carry_no_values() -> None:
    lines = notes.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4  # drawing-guidelines.md rule 7
    for number, line in enumerate(lines, start=1):
        assert line.startswith(f"{number}. "), line
    text = notes.DRAWING_NOTES
    for value in ("\u00b1", "+/-", "\u00d8", "MM", "1.0", "3.0", "4.0"):
        assert value not in text, value
    assert "MHA-DT-006" in text and "MHA-VN-006" in text
    assert "MHA-VN-035" in notes.DIMENSION_CALLOUTS["LoopID"]
    assert '"Manufacturing Notes": DRAWING_NOTES' in _build_source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()


def test_mating_part_numbers_are_live() -> None:
    assert _config.parts("dt-crank-arm")["number"] == "MHA-DT-006"
    assert _config.parts("vn-fillister-screw")["number"] == "MHA-VN-006"
    assert _config.parts("vn-keeper-chain")["number"] == "MHA-VN-035"


def test_views_are_in_projection_and_clear_of_the_title_block() -> None:
    assert drawing.SHEET_SCALE == (10.0, 1.0)
    assert _source().count("scale=VIEW_SCALE") == 3
    assert drawing.TOP_CENTER[0] == drawing.SIDE_CENTER[0]
    assert drawing.TOP_ANGLE == pytest.approx(-math.pi / 2.0)
    for x, y in (
        *drawing.SIDE_KEEP.values(),
        *drawing.TOP_KEEP.values(),
        drawing.NOTES_XY,
    ):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)
    loop_x, loop_y = drawing.SIDE_KEEP["LoopID"]
    assert math.dist((loop_x, loop_y), drawing.LOOP_CENTER_XY) > drawing.HALF_OD
    tail_x, tail_y = drawing.SIDE_KEEP["TailLen"]
    assert tail_x < drawing.TAIL_END_XY[0]
    assert drawing.LOOP_CENTER_XY[1] < tail_y < drawing.TAIL_END_XY[1]


class _View:
    """A drawing view whose ``Angle`` write either takes or is refused."""

    def __init__(self, *, refuses_rotation: bool = False) -> None:
        self._refuses = refuses_rotation
        self._angle = 0.0

    @property
    def Angle(self) -> float:
        return self._angle

    @Angle.setter
    def Angle(self, value: float) -> None:
        if not self._refuses:
            self._angle = value


class _DrawingModel:
    def EditRebuild3(self) -> bool:
        return True


@pytest.fixture
def turn_top_view(monkeypatch: pytest.MonkeyPatch):
    """Run ``_turn_top_view`` on fake views. The side view projects model
    points through the sheet layout; the top view projects them to the same
    sheet x, shifted by ``top_shift`` per landmark (the tail's end, y > 0, or
    the loop's far wire, z < 0)."""
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)

    def run(
        *, refuses_rotation: bool = False, top_shift: dict[str, float] | None = None
    ) -> _View:
        shift = top_shift or {}
        side, top = _View(), _View(refuses_rotation=refuses_rotation)

        def project(_adapter, view, point, *, label):
            x, y = drawing._side_xy(point[2] * 1000.0, point[1] * 1000.0)
            if view is top:
                return x + shift.get("tail end" if point[1] > 0.0 else "loop", 0.0), y
            return x, y

        monkeypatch.setattr(drawing, "model_point_in_view", project)
        drawing._turn_top_view(object(), _DrawingModel(), side, top)
        return top

    return run


def test_top_view_turn_accepts_views_in_projection(turn_top_view) -> None:
    assert turn_top_view().Angle == pytest.approx(drawing.TOP_ANGLE)
    near = 0.9 * drawing.ALIGN_TOL_M
    assert turn_top_view(
        top_shift={"tail end": near, "loop": -near}
    ).Angle == pytest.approx(drawing.TOP_ANGLE)


@pytest.mark.parametrize("landmark", ("tail end", "loop"))
def test_top_view_turn_rejects_each_landmark_out_of_projection(
    turn_top_view, landmark: str
) -> None:
    other = "loop" if landmark == "tail end" else "tail end"
    with pytest.raises(RuntimeError, match="not in projection") as raised:
        turn_top_view(top_shift={landmark: 1.1 * drawing.ALIGN_TOL_M})
    assert f"'{landmark}'" in str(raised.value)
    assert f"'{other}'" not in str(raised.value)


def test_top_view_turn_rejects_a_refused_rotation(turn_top_view) -> None:
    with pytest.raises(RuntimeError, match="failed to turn"):
        turn_top_view(refuses_rotation=True)


def test_part_registry_row() -> None:
    config = _config.parts("dt-crank-pin-eye")
    assert config["number"] == "MHA-DT-028"
    assert config["tolerance_class"] == "visual_noncritical"
    assert int(config["quantity"]) == 1
    assert "brass wire" in str(config["material_specification"]).lower()
    assert len(str(config["material_specification"])) <= 36
