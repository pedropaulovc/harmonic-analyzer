"""Offline release contracts for the MHA-DT-VN-59 axial arm-to-hub seam pin."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import dt_crank_hub_geometry as geometry
import dt_vn_crank_hub_pin_spec as pin_spec
import draw_dt_vn_crank_hub_pin as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_pin_length_is_half_the_shared_arm_thickness() -> None:
    assert pin_spec.PIN_LEN == geometry.ARM_THICKNESS / 2.0 == 4.0


def test_six_oclock_seam_leaves_the_u27_web_without_a_matched_check() -> None:
    assert geometry.HUB_SEAT_DIA_MIN_GENERAL == pytest.approx(18.6)
    assert geometry.AXIAL_PIN_DIA_STOCK_MAX == pytest.approx(4.012)
    assert geometry.HUB_BORE_DIA_MAX == pytest.approx(9.58)
    assert geometry.SEAM_WEB_WORST_MM >= geometry.WALL_TARGET_MM
    assert "DOWEL STOCK" in pin_spec.DRAWING_NOTES
    assert len(pin_spec.DRAWING_NOTES.splitlines()) <= 4


def test_pull_thread_is_nominally_two_diameters_with_distinct_walls() -> None:
    assert pin_spec.PULL_THREAD == "M2x0.4"
    assert pin_spec.PULL_THREAD_MAJOR == pytest.approx(2.0)
    assert pin_spec.PULL_THREAD_TAP_DRILL == pytest.approx(1.6)
    assert pin_spec.PULL_THREAD_LEN == pin_spec.PIN_LEN == 4.0
    assert pin_spec.PULL_THREAD_MIN_ENGAGEMENT_DIAMETERS == 2.0
    assert pin_spec.PULL_THREAD_LEN / pin_spec.PULL_THREAD_MAJOR == 2.0
    assert pin_spec.PULL_THREAD_TAP_DRILL_WALL == pytest.approx(1.2)
    assert pin_spec.PULL_THREAD_MAJOR_WALL == pytest.approx(1.0)
    assert pin_spec.PULL_THREAD_TAP_DRILL_WALL > pin_spec.PULL_THREAD_MAJOR_WALL
    assert pin_spec.PULL_THREAD_HOLE.kind == "tapped_metric"
    assert pin_spec.PULL_THREAD_HOLE.size == pin_spec.PULL_THREAD
    assert pin_spec.PULL_THREAD_HOLE.end == "through_all"
    # Rule 7: the thread is a view callout, and notes carry no method/sizes.
    assert "M2" not in pin_spec.DRAWING_NOTES
    assert "O'CLOCK" not in pin_spec.DRAWING_NOTES
    assert "DRILL" not in pin_spec.DRAWING_NOTES


def test_pull_tap_outer_end_and_callout_layout() -> None:
    import math

    import build_vn_crank_hub_pin as build

    assert build.TAP_R == pytest.approx(0.8)
    assert build.V_TAP == pytest.approx(math.pi * 0.8**2 * pin_spec.PIN_LEN)
    assert build.PULL_THREAD_ENTRY_POINT == (0.0, 0.0, 0.0)
    assert build.PULL_THREAD_ENTRY_NORMAL == (0.0, 0.0, -1.0)

    rim = math.hypot(
        drawing.THREAD_PICK[0] - drawing.FRONT_CENTER[0],
        drawing.THREAD_PICK[1] - drawing.FRONT_CENTER[1],
    )
    assert rim == pytest.approx(pin_spec.PULL_THREAD_TAP_DRILL * 10 / 2000.0)
    # Callout above the pin outline and left of the right view's PinDia text.
    assert drawing.THREAD_NOTE_XY[1] > drawing.FRONT_CENTER[1] + drawing.HALF_DIA
    assert drawing.THREAD_NOTE_XY[0] + 0.035 < drawing.RIGHT_KEEP["PinDia"][0] - 0.018


@pytest.fixture
def saved_pull_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SimpleNamespace, SimpleNamespace]:
    """Only COM wrapper conversion is replaced; validators read the data."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    definition = SimpleNamespace(
        FastenerSize="M2x0.4",
        EndCondition=1,
        ThreadEndCondition=1,
        ThruTapDrillDiameter=0.0016,
    )
    feature = SimpleNamespace(
        GetTypeName2=lambda: "HoleWzd",
        GetDefinition=lambda: definition,
    )
    model = SimpleNamespace(
        FeatureByName=lambda name: feature if name == "PullThread" else None
    )
    return model, definition


def test_saved_pull_thread_accepts_correct_native_data(
    saved_pull_thread: tuple[SimpleNamespace, SimpleNamespace],
) -> None:
    model, _definition = saved_pull_thread
    drawing._require_saved_pull_thread(model)


@pytest.mark.parametrize(
    ("member", "value"),
    [
        ("FastenerSize", "M2.5x0.45"),
        ("EndCondition", 0),
        ("EndCondition", 2),
        ("ThreadEndCondition", 0),
        ("ThreadEndCondition", 2),
        ("ThruTapDrillDiameter", 0.0017),
        ("ThruTapDrillDiameter", float("nan")),
    ],
)
def test_saved_pull_thread_rejects_wrong_native_data(
    saved_pull_thread: tuple[SimpleNamespace, SimpleNamespace],
    member: str,
    value: object,
) -> None:
    model, definition = saved_pull_thread
    setattr(definition, member, value)
    with pytest.raises(RuntimeError):
        drawing._require_saved_pull_thread(model)


def test_saved_pull_thread_rejects_missing_feature(
    saved_pull_thread: tuple[SimpleNamespace, SimpleNamespace],
) -> None:
    model, _definition = saved_pull_thread
    model.FeatureByName = lambda _name: None
    with pytest.raises(RuntimeError, match="feature is missing"):
        drawing._require_saved_pull_thread(model)


@pytest.mark.parametrize(
    ("texts", "valid"),
    [
        (("M2x0.4 - 6H", "THRU ALL"), True),
        (("M2 × 0.4", "THRU"), True),
        (("M2.5x0.45", "THRU ALL"), False),
        (("M2x0.45", "THRU ALL"), False),
        (("M2x0.4", "NOTTHRU"), False),
        (("M2x0.4", "<HOLE-DEPTH> 4.0"), False),
        (("M2x0.4 THRU ALL", "<HOLE-DEPTH> 0.0"), False),
        ((), False),
    ],
)
def test_native_pull_thread_callout_validates_rendered_text(
    monkeypatch: pytest.MonkeyPatch, texts: tuple[str, ...], valid: bool
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    data = SimpleNamespace(
        GetTextCount=lambda: len(texts),
        GetTextAtIndex=lambda index: texts[index],
    )
    annotation = SimpleNamespace(GetDisplayData=lambda: data)
    display = SimpleNamespace(GetAnnotation=lambda: annotation)
    if valid:
        drawing._require_pull_thread_callout(display)
    else:
        with pytest.raises(RuntimeError, match="through semantics"):
            drawing._require_pull_thread_callout(display)


def test_drawing_registry_and_native_dimensions_are_complete() -> None:
    assert DRAWINGS_BY_NAME["dt_vn_crank_hub_pin"].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-vn-crank-hub-pin.SLDDRW")
    assert set(drawing.RIGHT_KEEP) == set().union(*pin_spec.DRAWING_DIMENSIONS.values())
    assert pin_spec.DRAWING_PRECISION_BY_NAME == {"PinDia": 1, "PinLen": 1}


def test_assembly_places_pin_axially_at_six_oclock() -> None:
    import build_dt_drive_train_assembly as assembly

    assert assembly.CRANK_HUB_PIN_ORIGIN == pytest.approx(
        (
            assembly.X_CRANK,
            assembly.Y_CRANK - geometry.AXIAL_PIN_RADIUS_FROM_AXIS,
            assembly.CRANK_FACE_Z,
        )
    )
    assert assembly.CRANK_HUB_PIN_ROWS[2] == pytest.approx((0.0, 0.0, 1.0))
