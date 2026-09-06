"""The exported-ink comparison must see strokes, not just page bounding boxes."""

from PIL import Image
import pytest

from probe_drawing_thread_ink import ink_difference
import probe_drawing_thread_view as view_probe
from types import SimpleNamespace
import asyncio


def test_identical_exports_have_no_ink_difference(tmp_path):
    first, second = tmp_path / "a.png", tmp_path / "b.png"
    image = Image.new("RGB", (10, 10), "white")
    image.save(first)
    image.save(second)
    assert ink_difference(first, second)["difference_box_pixels"] is None


def test_one_changed_internal_stroke_pixel_is_detected(tmp_path):
    first, second = tmp_path / "a.png", tmp_path / "b.png"
    image = Image.new("RGB", (10, 10), "white")
    image.save(first)
    image.putpixel((3, 4), (0, 0, 0))
    image.save(second)
    assert ink_difference(first, second)["difference_box_pixels"] == (3, 4, 4, 5)


def test_different_page_sizes_are_not_a_valid_visibility_witness(tmp_path):
    first, second = tmp_path / "a.png", tmp_path / "b.png"
    Image.new("RGB", (10, 10), "white").save(first)
    Image.new("RGB", (20, 10), "white").save(second)
    with pytest.raises(ValueError, match="dimensions differ"):
        ink_difference(first, second)


def test_native_polyline_parser_preserves_arc_metadata_style_and_all_points():
    line = (0, 0, -1, 6, 0, 0, 0, 0, 2, 0.1, 0.2, 0, 0.3, 0.4, 0)
    geometry = tuple(range(12))
    arc = (1, 12, *geometry, -1, 6, 0, 0, 0, 0, 1, 0.5, 0.6, 0)
    parsed = view_probe.parse_polylines((*line, *arc))
    assert len(parsed) == 2
    assert parsed[0]["points"] == ((0.1, 0.2, 0), (0.3, 0.4, 0))
    assert parsed[1]["geometry"] == geometry
    assert parsed[1]["style"] == (-1, 6, 0, 0, 0, 0)
    assert parsed[1]["points"] == ((0.5, 0.6, 0),)


@pytest.mark.parametrize(
    "data",
    [
        (0,),
        (0, 12),
        (1, 0),
        (2, 0),
        (0, 0, 0),
        (0, 0, 0, 0, 0, 0, 0, 0, -1),
        (0, 0, 0, 0, 0, 0, 0, 0, 1),
        (float("nan"),),
    ],
)
def test_incomplete_or_unknown_native_polylines_are_not_partial_success(data):
    with pytest.raises(ValueError):
        view_probe.parse_polylines(data)


def test_native_data_comparison_preserves_multiplicity_and_capture_errors():
    assert view_probe.data_difference(
        {"lines": [(1, 2), (1, 2)]}, {"lines": [(1, 2)]}
    ) == {
        "outcome": "changed",
        "changes": {"lines": {"removed": [[1, 2]], "added": []}},
    }
    assert (
        view_probe.data_difference({"error": "native call rejected"}, {"lines": []})[
            "outcome"
        ]
        == "capture_error"
    )


@pytest.mark.parametrize(
    "failure", ["wrong_type", "rejected", "wrong_readback", "rebuild"]
)
def test_source_feature_control_rejects_unverified_suppression(monkeypatch, failure):
    monkeypatch.setattr(view_probe, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(view_probe, "null_variant", lambda: None)
    feature = SimpleNamespace(
        GetTypeName2=lambda: "Boss" if failure == "wrong_type" else "CosmeticThread",
        SetSuppression2=lambda *_args: failure != "rejected",
        IsSuppressed2=lambda *_args: (failure != "wrong_readback",),
    )
    model = SimpleNamespace(
        FeatureByName=lambda _name: feature, EditRebuild3=lambda: failure != "rebuild"
    )
    with pytest.raises(RuntimeError):
        view_probe.set_thread_state(model, "Cosmetic Thread1", 0)


def test_cleanup_closes_drawing_then_part_even_when_part_is_active(
    monkeypatch, tmp_path
):
    drawing_path, part_path = tmp_path / "copy.SLDDRW", tmp_path / "copy.SLDPRT"
    drawing = SimpleNamespace(GetPathName=lambda: str(drawing_path))
    part = SimpleNamespace(GetPathName=lambda: str(part_path))
    closed = []
    adapter = SimpleNamespace(currentModel=part)

    async def close(save):
        assert save is False
        closed.append(adapter.currentModel)
        adapter.currentModel = None

    adapter.close_model = close
    monkeypatch.setattr(view_probe, "check", lambda *_args: None)
    asyncio.run(
        view_probe.close_copies(adapter, ((drawing, drawing_path), (part, part_path)))
    )
    assert closed == [drawing, part]


def test_cleanup_rejects_foreign_document_before_close(monkeypatch, tmp_path):
    foreign = SimpleNamespace(GetPathName=lambda: str(tmp_path / "source.SLDPRT"))
    adapter = SimpleNamespace(currentModel=foreign)
    with pytest.raises(RuntimeError, match="outside the verified copy paths"):
        asyncio.run(
            view_probe.close_copies(adapter, ((foreign, tmp_path / "copy.SLDPRT"),))
        )


def test_native_no_change_metric_repeat_is_not_a_geometry_change():
    before = (
        5.980792051853801e-20,
        -0.0027819805794090336,
        -9.278011949235815e-20,
        4.940959892596307e-7,
        0.0004770088440113002,
        4.940959892596307e-7,
        1.2207457176682289e-11,
        3.476578172977266e-12,
        1.2076072385596641e-11,
        1.264693800884706e-28,
        -1.2461777107887238e-28,
        -1.708805686611262e-28,
    )
    after = (
        5.980792051853801e-20,
        -0.002781980579409034,
        -8.010970669824756e-20,
        4.940959892596307e-7,
        0.0004770088440113002,
        4.940959892596307e-7,
        1.2207457176682287e-11,
        3.4765781729772666e-12,
        1.207607238559664e-11,
        1.264693800884706e-28,
        -1.2461777107887238e-28,
        -3.601685334036261e-28,
    )
    report = view_probe.compare_body_metrics([(11, 17, before)], [(11, 17, after)])
    assert report[0]["deltas"][3] == 0
    assert report[0]["deltas"][11] != 0


@pytest.mark.parametrize("index", range(12))
def test_material_body_metric_change_is_never_ignored(index):
    before = [0, 0.001, 0, 1e-7, 0.001, 1e-7, 1e-11, 2e-11, 1e-11, 0, 0, 0]
    after = before.copy()
    after[index] += 1e-6 if index < 3 else 1e-6 * max(abs(before[index]), 1e-11)
    with pytest.raises(RuntimeError, match="beyond numeric guard"):
        view_probe.compare_body_metrics([(11, 17, before)], [(11, 17, after)])


def test_body_identity_match_allows_reordering_but_rejects_replacement():
    left, right = object(), object()
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    assert view_probe.match_body_identities(adapter, (left, right), (right, left)) == [
        1,
        0,
    ]
    with pytest.raises(RuntimeError, match="body identity"):
        view_probe.match_body_identities(adapter, (left, right), (left, object()))


def test_healthy_rebuild_calibrates_body_identity_exclusion_without_relaxing_metrics():
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    metrics = [(11, 17, (0, 0, 0, 1, 2, 1, 1, 1, 1, 0, 0, 0))]
    baseline, observed = (metrics, (object(),)), (metrics, (object(),))
    mode, checks = view_probe.check_body_observation(adapter, baseline, observed)
    assert mode == "healthy_rebuild_regenerates_single_body"
    assert checks[0]["deltas"] == [0] * 12
    with pytest.raises(RuntimeError, match="count changed"):
        view_probe.check_body_observation(adapter, baseline, ([], ()), mode)


def test_identity_loss_after_stable_control_is_not_silently_excluded():
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    metrics = [(11, 17, (0, 0, 0, 1, 2, 1, 1, 1, 1, 0, 0, 0))]
    body = object()
    baseline = metrics, (body,)
    mode, _checks = view_probe.check_body_observation(adapter, baseline, baseline)
    assert mode == "stable_in_healthy_rebuild"
    with pytest.raises(RuntimeError, match="geometry change not inferred"):
        view_probe.check_body_observation(
            adapter, baseline, (metrics, (object(),)), mode
        )


def test_phase_saves_open_native_copy_once_without_deleting_it(tmp_path):
    drawing, pdf = tmp_path / "copy.SLDDRW", tmp_path / "present.pdf"
    drawing.write_bytes(b"native-copy")
    calls = []

    def save(*args):
        calls.append(("native", args))
        assert drawing.read_bytes() == b"native-copy"
        return True, 0, 2

    def export(*args):
        calls.append(("pdf", args))
        pdf.write_bytes(b"new-pdf")
        return 0

    model = SimpleNamespace(
        GetPathName=lambda: str(drawing), Save3=save, SaveAs3=export
    )
    assert view_probe.save_phase(model, drawing, pdf) == {
        "save_warnings": 2,
        "pdf_save_result": 0,
    }
    assert calls == [("native", (1, 0, 0)), ("pdf", (str(pdf), 0, 0))]
    with pytest.raises(RuntimeError, match="already exists"):
        view_probe.save_phase(model, drawing, pdf)
    assert len(calls) == 2


@pytest.mark.parametrize("result", [(False, 0, 0), (True, 1, 0)])
def test_phase_native_save_failure_cannot_export_pdf(tmp_path, result):
    drawing = tmp_path / "copy.SLDDRW"
    model = SimpleNamespace(
        GetPathName=lambda: str(drawing), Save3=lambda *_args: result
    )
    with pytest.raises(RuntimeError, match="Save3 failed"):
        view_probe.save_phase(model, drawing, tmp_path / "present.pdf")


def test_present_phase_explicitly_rebuilds_before_identity_calibration():
    calls = []
    model = SimpleNamespace(EditRebuild3=lambda: calls.append("rebuild") or True)
    view_probe.prepare_phase(model, "Cosmetic Thread1", "present")
    assert calls == ["rebuild"]
    model.EditRebuild3 = lambda: False
    with pytest.raises(RuntimeError, match="healthy-control rebuild failed"):
        view_probe.prepare_phase(model, "Cosmetic Thread1", "present")


def test_definition_capture_keeps_zero_diameter_as_evidence_not_a_guessed_default(
    monkeypatch,
):
    monkeypatch.setattr(view_probe, "_early_bound", lambda value, _kind: value)
    data = SimpleNamespace(
        Diameter=0.0,
        DiameterType=3,
        BlindDepth=0.008,
        ApplyThread=0,
        Standard=0,
        StandardType="",
        Size="#10-24",
    )
    result = view_probe.feature_definition(SimpleNamespace(GetDefinition=lambda: data))
    assert result == {
        "diameter_m": 0.0,
        "diameter_type": 3,
        "blind_depth_m": 0.008,
        "apply_thread": 0,
        "standard": 0,
        "standard_type": "",
        "size": "#10-24",
    }


@pytest.mark.parametrize(
    "repeat_box,repeat_hash,suppression_box,suppression_hash,outcome",
    [
        ((1, 2, 3, 4), "a", None, "a", "inconclusive_repeat_ink_change"),
        (None, "changed", None, "a", "inconclusive_repeat_ink_change"),
        (None, "a", (1, 2, 3, 4), "a", "repeatable_source_feature_ink_change"),
        (None, "a", None, "changed", "repeatable_source_feature_ink_change"),
        (None, "a", None, "a", "inconclusive_no_source_feature_ink_change"),
    ],
)
def test_thread_ink_conclusion_requires_repeatable_control(
    repeat_box, repeat_hash, suppression_box, suppression_hash, outcome
):
    phases = {
        "present": {"pdf_vectors": {"sha256": "a"}},
        "present_again": {"pdf_vectors": {"sha256": repeat_hash}},
        "suppressed": {"pdf_vectors": {"sha256": suppression_hash}},
    }
    assert (
        view_probe.ink_outcome(
            phases,
            {"difference_box_pixels": repeat_box},
            {"difference_box_pixels": suppression_box},
        )
        == outcome
    )
