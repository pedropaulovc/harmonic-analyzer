"""Offline release contracts for the MHA-DT-VN-59 axial arm-to-hub seam pin."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import dt_crank_hub_geometry as geometry
import dt_vn_crank_hub_pin_spec as pin_spec
import draw_dt_vn_crank_hub_pin as drawing
from _drawing_edges import ViewEdge, ViewEdges
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

    # Callout above the pin outline and left of the right view's PinDia text.
    assert drawing.THREAD_NOTE_XY[1] > drawing.END_CENTER[1] + drawing.HALF_DIA
    assert drawing.THREAD_NOTE_XY[0] + 0.035 < drawing.RIGHT_KEEP["PinDia"][0] - 0.018


def _circle(
    center_mm: tuple[float, float, float],
    radius_mm: float,
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> ViewEdge:
    return ViewEdge(
        edge=object(), line=None, circle=(*center_mm, *axis, radius_mm), vertices=None
    )


def test_pull_thread_callout_selects_entry_not_coincident_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import build_vn_crank_hub_pin as build

    entry = _circle(build.PULL_THREAD_ENTRY_POINT, pin_spec.PULL_THREAD_TAP_DRILL / 2.0)
    exit_rim = _circle((0.0, 0.0, pin_spec.PIN_LEN), entry.circle[6])
    outer = _circle(build.PULL_THREAD_ENTRY_POINT, pin_spec.PIN_DIA / 2.0)
    rims = ViewEdges(label="extraction end", edges=(exit_rim, outer, entry))
    monkeypatch.setattr(drawing, "scan_view_edges", lambda _view, **_kwargs: rims)
    assert drawing._pull_thread_entry_edge(object()) is entry.edge


@pytest.mark.parametrize(
    "rim",
    [
        _circle((0.0, 0.0, pin_spec.PIN_LEN), pin_spec.PULL_THREAD_TAP_DRILL / 2.0),
        _circle((0.0, 0.0, 0.0), pin_spec.PIN_DIA / 2.0),
        _circle((0.0, 0.0, 0.0), pin_spec.PULL_THREAD_MAJOR / 2.0),
        _circle((0.0, 0.0, 0.0), pin_spec.PULL_THREAD_TAP_DRILL / 2.0, (1.0, 0.0, 0.0)),
    ],
)
def test_pull_thread_entry_refuses_wrong_visible_rim(
    monkeypatch: pytest.MonkeyPatch, rim: ViewEdge
) -> None:
    rims = ViewEdges(label="wrong end", edges=(rim,))
    monkeypatch.setattr(drawing, "scan_view_edges", lambda _view, **_kwargs: rims)
    with pytest.raises(RuntimeError, match="no visible circle"):
        drawing._pull_thread_entry_edge(object())



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
        (("<MOD-DIAM> 1.60 THRU ALL",), False),
        (("M2x0.4 Tapped Hole",), False),
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


@pytest.mark.parametrize("drill_only", [False, True])
def test_build_uses_entry_native_callout_and_exact_automatic_note_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    saved_pull_thread: tuple[SimpleNamespace, SimpleNamespace],
    drill_only: bool,
) -> None:
    """Exercise authoring, unchanged rendered-text refusal and finalizer policy."""
    model, _definition = saved_pull_thread
    source = tmp_path / "vn-crank-hub-pin.SLDPRT"
    source.write_bytes(b"offline source sentinel")
    monkeypatch.setattr(drawing, "SOURCE", source)
    adapter = SimpleNamespace(currentModel=model, open_model=AsyncMock())
    entry = _circle((0.0, 0.0, 0.0), pin_spec.PULL_THREAD_TAP_DRILL / 2.0)
    exit_rim = _circle((0.0, 0.0, pin_spec.PIN_LEN), pin_spec.PULL_THREAD_TAP_DRILL / 2.0)
    outer = _circle((0.0, 0.0, 0.0), pin_spec.PIN_DIA / 2.0)

    def place_view(_adapter, _source, orientation, *_center, **_kwargs):
        # Front looks from +Z onto the exit; Back sees the Z=0 entry.
        visible = {"*Back": (outer, entry), "*Front": (outer, exit_rim)}
        return ViewEdges(label=orientation, edges=visible.get(orientation, ()))

    monkeypatch.setattr(drawing, "place_view", place_view)
    monkeypatch.setattr(drawing, "scan_view_edges", lambda view, **_kwargs: view)
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *_args, **_kwargs: (object(), object()))
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *_args, **_kwargs: [])
    for name in (
        "check", "read_required_properties", "stamp_drawing_summary",
        "set_hidden_lines_removed", "assert_imported_precision",
        "set_reference_dimensions", "add_view_centerline", "add_property_linked_note",
    ):
        monkeypatch.setattr(drawing, name, lambda *_args, **_kwargs: None)
    centre_marks = []

    def auto_center_marks(_adapter, view, **_kwargs):
        centre_marks.append(view)
        return True

    monkeypatch.setattr(drawing, "auto_center_marks", auto_center_marks)
    native_calls = []

    def add_native_hole_callout(_adapter, view, *, edge, callout_xy, label):
        native_calls.append((view, edge, callout_xy))
        texts = (
            ("<MOD-DIAM> 1.60 THRU ALL",)
            if drill_only else ("M2x0.4 - 6H THRU ALL",)
        )
        data = SimpleNamespace(
            GetTextCount=lambda: len(texts), GetTextAtIndex=lambda index: texts[index]
        )
        annotation = SimpleNamespace(GetDisplayData=lambda: data)
        # No writable text member: this route may not manufacture a thread label.
        return SimpleNamespace(GetAnnotation=lambda: annotation)

    monkeypatch.setattr(drawing, "add_native_hole_callout", add_native_hole_callout)
    finalize = AsyncMock(return_value={"pdf": str(drawing.PDF)})
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    if drill_only:
        with pytest.raises(RuntimeError, match="through semantics"):
            asyncio.run(drawing.build(adapter))
        finalize.assert_not_awaited()
    else:
        assert asyncio.run(drawing.build(adapter)) == {"pdf": str(drawing.PDF)}
        finalize.assert_awaited_once()
        options = finalize.await_args.kwargs
        assert options["pdf_title"] == pin_spec.DRAWING_TITLE
        assert options["redundant_note_substrings"] == ("Tapped Hole",)
        assert options["expected_redundant_notes"] == 1
    [(view, edge, xy)] = native_calls
    assert edge is entry.edge
    assert xy == drawing.THREAD_NOTE_XY
    assert centre_marks == [view]



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
