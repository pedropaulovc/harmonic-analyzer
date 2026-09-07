"""Measured sheet-format cells, never an offset compensating for title reflow."""

import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from contextlib import nullcontext


def box_lines(left=0.33, bottom=0.035, right=0.42, top=0.055):
    return [
        ((left, bottom, 0), (right, bottom, 0)),
        ((right, bottom, 0), (right, top, 0)),
        ((right, top, 0), (left, top, 0)),
        ((left, top, 0), (left, bottom, 0)),
    ]


def test_cell_and_anchor_follow_measured_borders_not_old_title_offset():
    from diagnostics import _linked_title_cell as cell

    lines = box_lines()
    measured = cell.enclosing_cell(lines, (0.379, 0.047, 0))
    assert measured == (0.33, 0.035, 0.42, 0.055)
    assert cell.left_anchor(measured, (0.379, 0.047, 0), 0.006) == (0.333, 0.047, 0)
    shifted = [tuple((x + 0.01, y, z) for x, y, z in line) for line in lines]
    new_cell = cell.enclosing_cell(shifted, (0.389, 0.047, 0))
    assert cell.left_anchor(new_cell, (0.389, 0.047, 0), 0.006)[0] == pytest.approx(
        0.343
    )


def test_open_cell_does_not_fall_back_to_outer_sheet_frame():
    from diagnostics import _linked_title_cell as cell

    lines = box_lines()[:-1] + box_lines(0, 0, 0.4318, 0.2794)
    # An interior partial left rule stops the nearest candidate from closing.
    lines.append(((0.33, 0.044, 0), (0.33, 0.051, 0)))
    with pytest.raises(RuntimeError, match="closed"):
        cell.enclosing_cell(lines, (0.379, 0.047, 0))


def test_left_cell_is_explicit_diagnostic_variant():
    from diagnostics.probe_fresh_title_update import Variant

    assert Variant("pre_save_left_title_cell").name == "LEFT_TITLE_CELL"


def test_segmented_borders_and_outer_frame_choose_innermost_cell():
    from diagnostics import _linked_title_cell as cell

    lines = box_lines() + box_lines(0, 0, 0.4318, 0.2794)
    lines.pop(0)
    lines.extend(
        [((0.33, 0.035, 0), (0.37, 0.035, 0)), ((0.37, 0.035, 0), (0.42, 0.035, 0))]
    )
    assert cell.enclosing_cell(lines, (0.379, 0.047, 0)) == (0.33, 0.035, 0.42, 0.055)


@pytest.mark.parametrize(
    "mode", ["missing", "on_border", "nan", "nonplanar", "degenerate", "gap"]
)
def test_cell_rejects_missing_ambiguous_or_invalid_native_borders(mode):
    from diagnostics import _linked_title_cell as cell

    lines, anchor = box_lines(), (0.379, 0.047, 0)
    if mode == "missing":
        lines = []
    if mode == "on_border":
        anchor = (0.33, 0.047, 0)
    if mode == "nan":
        lines[0] = ((float("nan"), 0.035, 0), (0.42, 0.035, 0))
    if mode == "nonplanar":
        lines[0] = ((0.33, 0.035, 0.0001), (0.42, 0.035, 0))
    if mode == "degenerate":
        lines[0] = (lines[0][0], lines[0][0])
    if mode == "gap":
        lines[0] = ((0.330001, 0.035, 0), (0.42, 0.035, 0))
    with pytest.raises(RuntimeError):
        cell.enclosing_cell(lines, anchor)


@pytest.mark.parametrize("height", [0, -0.003, float("nan"), 0.3])
def test_bad_font_height_cannot_choose_an_inset(height):
    from diagnostics import _linked_title_cell as cell

    with pytest.raises(RuntimeError):
        cell.left_anchor((0.33, 0.035, 0.42, 0.055), (0.379, 0.047, 0), height)


def test_native_and_pdf_fit_are_strict_without_geometry_or_pixel_tolerance():
    from diagnostics import _linked_title_cell as cell

    bounds = (0.33, 0.035, 0.42, 0.055)
    row = {"extent": (0.333, 0.04, 0, 0.4, 0.047, 0)}
    cell.require_native_fit(bounds, row)
    row["extent"] = (0.33 - 1e-12, 0.04, 0, 0.4, 0.047, 0)
    with pytest.raises(RuntimeError, match="fit"):
        cell.require_native_fit(bounds, row)
    factor = 72 / 0.0254
    pdf = {
        "page_size_pt": (1224, 792),
        "characters": [
            {
                "box_pt": (
                    0.333 * factor,
                    792 - 0.047 * factor,
                    0.4 * factor,
                    792 - 0.04 * factor,
                )
            }
        ],
    }
    cell.require_pdf_fit(bounds, pdf)
    pdf["characters"][0]["box_pt"] = (
        (0.33 - 1e-8) * factor,
        792 - 0.047 * factor,
        0.4 * factor,
        792 - 0.04 * factor,
    )
    with pytest.raises(RuntimeError, match="fit"):
        cell.require_pdf_fit(bounds, pdf)
    pdf["characters"] = []
    with pytest.raises(RuntimeError, match="no title glyphs"):
        cell.require_pdf_fit(bounds, pdf)


@pytest.mark.parametrize(
    "mode",
    [
        "normal",
        "null_sketch",
        "null_point",
        "bad_type",
        "duplicate",
        "nonfinite_transform",
    ],
)
def test_native_cell_reader_uses_template_sketch_and_inverse_transform(
    monkeypatch, mode
):
    from diagnostics import _linked_title_cell as cell

    monkeypatch.setattr(cell, "_early_bound", lambda raw, _: raw)
    matrix = (1.0, 0, 0, 0, 1.0, 0, 0, 0, 1.0, 0.1, 0.2, 0, 1.0, 0, 0, 0)
    inverse = SimpleNamespace(ArrayData=matrix)
    transform = SimpleNamespace(ArrayData=matrix, Inverse=lambda: inverse)
    seen_points = []

    def create_point(data):
        xyz = tuple(data.value)
        seen_points.append(xyz)

        def moved(actual):
            assert actual is inverse
            return SimpleNamespace(ArrayData=(xyz[0] + 0.1, xyz[1] + 0.2, xyz[2]))

        return SimpleNamespace(MultiplyTransform=moved)

    start = SimpleNamespace(X=0.23, Y=-0.165, Z=0)
    end = SimpleNamespace(X=0.32, Y=-0.165, Z=0)
    line = SimpleNamespace(
        GetType=lambda: 0,
        GetID=lambda: (1, 0),
        ConstructionGeometry=False,
        GetStartPoint2=lambda: start,
        GetEndPoint2=lambda: end,
    )
    curve = SimpleNamespace(
        GetType=lambda: 1, GetID=lambda: (1, 0), ConstructionGeometry=False
    )
    sketch = SimpleNamespace(
        ModelToSketchTransform=transform, GetSketchSegments=lambda: (line, curve)
    )
    sheet = SimpleNamespace(GetTemplateSketch=lambda: sketch)
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetCurrentSheet=lambda: sheet),
        swApp=SimpleNamespace(
            GetMathUtility=lambda: SimpleNamespace(CreatePoint=create_point)
        ),
    )
    if mode == "null_sketch":
        sheet.GetTemplateSketch = lambda: None
    if mode == "null_point":
        line.GetStartPoint2 = lambda: None
    if mode == "bad_type":
        curve.GetType = lambda: 100
    if mode == "duplicate":
        sketch.GetSketchSegments = lambda: (line, line)
    if mode == "nonfinite_transform":
        transform.ArrayData = (*matrix[:15], float("nan"))
    if mode != "normal":
        with pytest.raises(RuntimeError):
            cell.template_lines(adapter)
        return
    lines, receipt = cell.template_lines(adapter)
    assert seen_points == [(0.23, -0.165, 0), (0.32, -0.165, 0)]
    assert lines[0][0] == pytest.approx((0.33, 0.035, 0))
    assert receipt["segments"][0]["sketch_points"][0] == seen_points[0]
    assert receipt["segments"][1]["cell_boundary"] == "excluded_non_rule"


@pytest.mark.parametrize(
    "mode",
    [
        "normal",
        "locked",
        "missing_cell",
        "setter_false",
        "setter_none",
        "clamped",
        "alignment",
        "font",
        "link",
        "extent",
    ],
)
def test_left_layout_sets_only_one_checked_cell_anchor_and_seals_style(
    monkeypatch, mode
):
    from diagnostics import probe_fresh_title_update as probe
    from test_fresh_title_update_drawing import title_native

    adapter, _, annotation, note, raw = title_native(monkeypatch)
    adapter.ownership = SimpleNamespace(saving_as=lambda _: nullcontext())
    calls, state = (
        [],
        {"alignment": 2, "position": (0.379, 0.047, 0), "font": {"CharHeight": 0.006}},
    )
    annotation.GetPosition = lambda: state["position"]
    note.GetTextJustification = lambda: state["alignment"]
    note.LockPosition = mode == "locked"
    note.SetTextJustification = lambda value: (
        (
            calls.append(("justify", value)),
            state.update(alignment=1 if mode != "alignment" else 3),
        )
        and None
    )
    monkeypatch.setattr(probe, "title_font_format", lambda _: dict(state["font"]))
    monkeypatch.setattr(
        probe.title_cell,
        "template_lines",
        lambda _: (
            [] if mode == "missing_cell" else box_lines(),
            {"segments": "fixture"},
        ),
    )

    def position(*xyz):
        calls.append(("position", xyz))
        state["position"] = (0.334, 0.047, 0) if mode == "clamped" else xyz
        note.GetExtent = lambda: (
            xyz[0],
            0.04,
            0,
            0.43 if mode == "extent" else 0.4,
            0.047,
            0,
        )
        raw["texts"][0]["position"] = (xyz[0], 0.04, 0)
        if mode == "font":
            state["font"]["CharHeight"] = 0.007
        if mode == "link":
            note.PropertyLinkedText = "literal"
        return {"setter_false": False, "setter_none": None}.get(mode, True)

    annotation.SetPosition2 = position
    adapter.currentModel.GraphicsRedraw2 = lambda: calls.append("redraw")
    adapter.currentModel.EditRebuild3 = Mock(side_effect=AssertionError("no rebuild"))
    original_properties = Mock()
    monkeypatch.setattr(probe.common, "apply_custom_properties", original_properties)

    def save(current, path, *, artifact_context, **kwargs):
        for kind, target in (("drawing", path), ("pdf", kwargs["pdf_path"])):
            with artifact_context(kind, target):
                calls.append(kind)

    monkeypatch.setattr(probe.drawing, "save_drawing", save)
    trial = {}
    observer = probe.TitleObserver(adapter, trial, Mock())

    def run():
        with probe.finalizer_observations(
            adapter, observer, probe.Variant.LEFT_TITLE_CELL
        ) as counts:
            probe.common.apply_custom_properties(adapter, {"UNIT_DISPLAY": "MM"})
            probe.drawing.save_drawing(adapter, "owned.SLDDRW", pdf_path="owned.pdf")
        return counts

    if mode == "normal":
        assert run() == dict(
            properties=1,
            drawing=1,
            pdf=1,
            redraw=1,
            edit_rebuild=0,
            force_rebuild=0,
            justification=1,
            linked_text=0,
            position=1,
        )
        assert calls == [
            ("justify", 1),
            ("position", (0.333, 0.047, 0)),
            "redraw",
            "drawing",
            "pdf",
        ]
        assert observer.initial["horizontal_justification"] == 2
        assert observer.layout_style["horizontal_justification"] == 1
        state["alignment"] = 2
        with pytest.raises(RuntimeError, match="style"):
            observer.record("after_pdf_export")
    else:
        with pytest.raises(RuntimeError):
            run()
        assert "drawing" not in calls and "pdf" not in calls
        if mode == "missing_cell":
            assert trial["left_title_cell"]["template_before"] == {
                "segments": "fixture"
            }
            assert calls == []
    assert probe.common.apply_custom_properties is original_properties
    assert probe.drawing.save_drawing is save
    adapter.currentModel.EditRebuild3.assert_not_called()


@pytest.mark.parametrize("native_state", ["unchanged", "changed"])
def test_left_printed_success_also_requires_exact_native_cold_equality(native_state):
    import asyncio
    from diagnostics import probe_fresh_title_update as probe

    async def trial(variant):
        if variant is probe.Variant.BASELINE:
            return {
                "printed": {"classification": "reproduced"},
                "png_delta": {"changed_pixel_count": 11232},
            }
        return {
            "printed": {"classification": "unchanged"},
            "png_delta": {"changed_pixel_count": 0},
            "left_cell_native_stability": native_state,
        }

    assert asyncio.run(probe.run_pair(trial, probe.Variant.LEFT_TITLE_CELL)) == (
        "candidate_printed_stable"
        if native_state == "unchanged"
        else "candidate_not_stable"
    )


def test_left_cli_checks_environment_before_native_and_helper_is_fingerprinted(
    monkeypatch,
):
    from diagnostics import probe_fresh_title_update as probe

    guard = Mock(side_effect=RuntimeError("expected environment guard"))
    monkeypatch.setattr(probe, "require_owned_diagnostic_environment", guard)
    with pytest.raises(RuntimeError, match="environment guard"):
        probe.main(
            [
                "--candidate",
                "pre_save_left_title_cell",
                "--source",
                "part.SLDPRT",
                "--guard-source",
                "guard.SLDPRT",
            ]
        )
    guard.assert_called_once_with()
    fingerprints = probe.pilot.helper_fingerprints()
    assert str(Path("cad/scripts/diagnostics/_linked_title_cell.py")) in fingerprints
