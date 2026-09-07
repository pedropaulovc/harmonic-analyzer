"""Only four explicit template note layout transitions may be baked."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import _baked_template_layout as layout
from diagnostics import probe_baked_template_layout as probe
from test_owned_native_documents_drawing import Model, native  # noqa: F401
from test_title_cell_drawing import box_lines


def note(link, text="", x=0.35, y=0.027, height=0.006, horizontal=2):
    return {
        "link": link,
        "text": text,
        "visible": 1,
        "owner_type": 2,
        "kind": 6,
        "position": [x, y, 0],
        "horizontal": horizontal,
        "vertical": 0,
        "lock": "unlocked",
        "font": {
            "CharHeight": height,
            "CharHeightInPts": 20,
            "IsHeightSpecifiedInPts": True,
            "GetUseDocTextFormat": False,
            "TypeFaceName": "Century Gothic",
            "Bold": False,
        },
        "extent": [x, y - 0.004, 0, x + 0.01, y, 0],
        "extent_scope": "measured" if text else "observed_zero_ink",
        "display": {
            "counts": {"Text": int(bool(text))},
            "texts": [
                {
                    "value": text,
                    "position": [x, y - 0.004, 0],
                    "height_m": height,
                    "font": "Century Gothic",
                    "reference": 1,
                }
            ]
            if text
            else [],
            "primitives": {"Line": []},
        },
    }


def scene():
    notes = {
        "title": note(layout.TITLE_LINK, x=0.37, y=0.047),
        "dwg": note(layout.NUMBER_LINK, x=0.35),
        "rev": note(layout.REVISION_LINK, x=0.385),
        "label": note("REV", "REV", x=0.376, y=0.034, height=0.00254, horizontal=1),
        "dwg_label": note(
            "DWG.  NO.", "DWG.  NO.", x=0.342, y=0.034, height=0.00254, horizontal=1
        ),
    }
    lines = (
        box_lines(0.338, 0.036, 0.42, 0.056)
        + box_lines(0.338, 0.019, 0.378, 0.036)
        + box_lines(0.378, 0.019, 0.398, 0.036)
    )
    return notes, lines


def test_revision_cell_comes_from_value_not_misplaced_static_label():
    notes, lines = scene()
    plan = layout.layout_plan(notes, lines)
    assert set(plan) == {"title", "dwg", "rev", "label"}
    assert plan["label"]["position"][0] == 0.378 + 0.00254 / 2
    assert plan["rev"]["position"][0] == plan["label"]["position"][0]
    assert plan["dwg"]["position"] == [0.342, 0.027, 0]
    assert plan["title"]["height_m"] == 0.006
    assert plan["rev"]["height_m"] == plan["dwg"]["height_m"] == 0.0035


def transformed():
    notes, lines = scene()
    before = {"notes": notes, "units": [4, 0, 2], "surface_finishes": ["raw unchanged"]}
    after = deepcopy(before)
    plan = layout.layout_plan(notes, lines)
    for name, target in plan.items():
        row = after["notes"][name]
        row["position"], row["horizontal"] = list(target["position"]), 1
        if target["role"] in ("number", "revision"):
            row["font"].update(
                CharHeight=0.0035, CharHeightInPts=10, IsHeightSpecifiedInPts=False
            )
        row["extent"] = [
            target["position"][0],
            target["position"][1] - 0.004,
            0,
            target["position"][0] + 0.006,
            target["position"][1],
            0,
        ]
        for text in row["display"]["texts"]:
            text["position"] = row["position"]
    return before, after, plan


def test_exact_allowlist_accepts_intended_layout_and_keeps_original_snapshot():
    before, after, plan = transformed()
    original = deepcopy(before)
    layout.require_transition(before, after, plan)
    assert before == original


@pytest.mark.parametrize(
    "mode",
    [
        "link",
        "text",
        "bold",
        "vertical",
        "lock",
        "units",
        "sf",
        "unmodified_label",
        "clamp",
        "font",
        "multiplicity",
    ],
)
def test_allowlist_rejects_non_layout_changes_and_bad_readbacks(mode):
    before, after, plan = transformed()
    row = after["notes"]["rev"]
    if mode == "link":
        row["link"] = "literal"
    if mode == "text":
        row["text"] = "unexpected"
    if mode == "bold":
        row["font"]["Bold"] = True
    if mode == "vertical":
        row["vertical"] = 1
    if mode == "lock":
        row["lock"] = "locked"
    if mode == "units":
        after["units"] = [5, 0, 2]
    if mode == "sf":
        after["surface_finishes"] = []
    if mode == "unmodified_label":
        after["notes"]["dwg_label"]["position"][0] += 0.001
    if mode == "clamp":
        row["position"][0] += 0.0001
    if mode == "font":
        row["font"]["CharHeight"] = 0.0036
    if mode == "multiplicity":
        row["display"]["texts"] = [{"value": "x"}]
    with pytest.raises(RuntimeError):
        layout.require_transition(before, after, plan)


def test_cold_snapshot_never_waives_changed_alignment_or_visible_extent():
    _, after, _ = transformed()
    cold = deepcopy(after)
    cold["notes"]["label"]["extent"][0] += 1e-12
    with pytest.raises(RuntimeError):
        layout.require_equal(after, cold, "cold")
    cold = deepcopy(after)
    cold["notes"]["rev"]["extent"][0] += (
        0.1  # Proven empty-note extent is observation only.
    )
    layout.require_equal(after, cold, "cold")
    cold["notes"]["rev"]["horizontal"] = 2
    with pytest.raises(RuntimeError):
        layout.require_equal(after, cold, "cold")


def test_field_fit_must_include_unchanged_static_number_label():
    notes, lines = scene()
    plan = layout.validation_plan(notes, lines, layout.layout_plan(notes, lines))
    assert "dwg_label" in plan


def test_mutator_refuses_changed_active_document_before_any_setter():
    adapter = SimpleNamespace(
        currentModel=object(),
        swApp=SimpleNamespace(ActiveDoc=object(), IsSame=lambda a, b: int(a is b)),
    )
    calls = Mock(side_effect=AssertionError("no native setter allowed"))
    annotation = SimpleNamespace(GetSpecificAnnotation=calls)
    with pytest.raises(RuntimeError, match="active"):
        layout.apply_layout(
            adapter,
            {"note": (annotation, None)},
            {"note": {"role": "title"}},
            [],
            Mock(),
        )
    calls.assert_not_called()


@pytest.mark.parametrize("rejection", ["none", "format", "position", "locked"])
def test_exact_native_setter_shapes_and_rejections(monkeypatch, rejection):
    monkeypatch.setattr(layout.cells, "required", lambda value, _: value)
    note = SimpleNamespace(
        LockPosition=rejection == "locked", SetTextJustification=Mock()
    )
    fmt = SimpleNamespace(CharHeight=0.006)
    ann = SimpleNamespace(
        Owner=None,
        GetSpecificAnnotation=lambda: note,
        GetTextFormat=lambda index: fmt,
        SetTextFormat=Mock(return_value=rejection != "format"),
        SetPosition2=Mock(return_value=rejection != "position"),
    )
    model = SimpleNamespace(GraphicsRedraw2=Mock())
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(ActiveDoc=model, IsSame=lambda a, b: int(a is b)),
    )
    rows = []
    plan = {
        "rev": {"role": "revision", "height_m": 0.0035, "position": [0.38, 0.027, 0]}
    }
    if rejection == "none":
        layout.apply_layout(adapter, {"rev": (ann, None)}, plan, rows, Mock())
        ann.SetTextFormat.assert_called_once_with(0, False, fmt)
        assert fmt.CharHeight == 0.0035
        note.SetTextJustification.assert_called_once_with(1)
        ann.SetPosition2.assert_called_once_with(0.38, 0.027, 0)
        model.GraphicsRedraw2.assert_called_once_with()
        return
    with pytest.raises(RuntimeError):
        layout.apply_layout(adapter, {"rev": (ann, None)}, plan, rows, Mock())
    model.GraphicsRedraw2.assert_not_called()
    if rejection == "locked":
        ann.SetTextFormat.assert_not_called()
    if rejection == "format":
        ann.SetPosition2.assert_not_called()
    assert rows


@pytest.mark.parametrize("mode", ["replaced_note", "replaced_owner", "multiplicity"])
def test_exact_annotation_and_owner_handles_cannot_be_replaced(mode):
    annotation, owner = object(), object()
    after = {
        "note": (
            object() if mode == "replaced_note" else annotation,
            object() if mode == "replaced_owner" else owner,
        )
    }
    if mode == "multiplicity":
        after["extra"] = (annotation, owner)
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    with pytest.raises(RuntimeError):
        layout.require_same_handles(app, {"note": (annotation, owner)}, after)


@pytest.mark.parametrize("mode", ["fit", "overflow", "near", "empty_ink"])
def test_native_fit_does_not_waive_empty_ink_overflow_or_near_collision(mode):
    notes = {"a": note("REV", "REV", x=0.38, y=0.03)}
    plan = {"a": {"role": "label", "cell": [0.37, 0.01, 0.40, 0.04]}}
    if mode == "fit":
        assert layout.require_field_fit(notes, plan)["checked"] == ["a"]
        return
    if mode == "overflow":
        notes["a"]["extent"][3] = 0.401
    if mode == "empty_ink":
        notes["a"]["text"] = ""
    if mode == "near":
        notes["b"] = note("Other", "Other", x=0.3905, y=0.03)
        plan["b"] = {"role": "label", "cell": [0.37, 0.01, 0.42, 0.04]}
    with pytest.raises(RuntimeError):
        layout.require_field_fit(notes, plan)


def test_pdf_fit_uses_bottom_left_coordinates_and_preserves_whitespace_evidence(
    monkeypatch,
):
    from diagnostics import probe_retained_drawing_export as retained

    notes = {"label": note("DWG.  NO.", "DWG.  NO.")}
    plan = {"label": {"cell": [0.33, 0.02, 0.38, 0.04]}}
    glyph = {
        "text": "DWG. NO.",
        "ink_box_pt": tuple(v * 72 / 0.0254 for v in [0.34, 0.025, 0.36, 0.03]),
    }
    monkeypatch.setattr(retained, "pdf_title", lambda *args: glyph)
    result = layout.pdf_field_fit("unused.pdf", notes, plan)
    assert result["fields"]["label"]["native_text"] == "DWG.  NO."
    assert result["fields"]["label"]["text"] == "DWG. NO."
    glyph["text"] = "DWG. Na."
    with pytest.raises(RuntimeError, match="text differs"):
        layout.pdf_field_fit("unused.pdf", notes, plan)


def test_bare_creation_does_not_call_project_normalization(monkeypatch):
    expected = object()
    native_new = Mock(return_value=expected)
    monkeypatch.setattr(probe.common, "new_drawing", native_new)
    normalized = Mock(side_effect=AssertionError("no normalization"))
    monkeypatch.setattr(probe.common, "new_project_drawing", normalized)
    assert probe.bare_drawing("adapter", "source.DRWDOT") is expected
    native_new.assert_called_once_with(
        "adapter",
        template="source.DRWDOT",
        width=probe.common.ASME_B_WIDTH_M,
        height=probe.common.ASME_B_HEIGHT_M,
    )
    normalized.assert_not_called()


@pytest.mark.parametrize(
    "mode",
    [
        "pass",
        "partial_creation",
        "transition",
        "save_failed",
        "save_drift",
        "cold_drift",
        "print_drift",
    ],
)
def test_owned_blank_control_preserves_baseline_and_never_opens_a_model(
    native,  # noqa: F811
    monkeypatch,
    tmp_path,
    mode,
):
    import asyncio
    import json
    from diagnostics import _owned_native_documents as owned

    original = tmp_path / "original.DRWDOT"
    original.write_bytes(b"exact original template")
    monkeypatch.setattr(probe.common, "PROJECT_DRWDOT", original)
    monkeypatch.setattr(probe.pilot, "helper_fingerprints", lambda: {})
    monkeypatch.setattr(probe.pilot, "adapter_fingerprints", lambda: {})
    monkeypatch.setattr(probe.pilot.benchmark, "revision", lambda _: "frozen")
    baseline = Model(None, title="User unsaved", dirty=True)
    native.app.documents.append(baseline)
    native.app.ActiveDoc = baseline
    before, after, plan = transformed()
    created, templates, snapshots = [], [], []

    def bare(adapter, template):
        model = Model(None, title=f"Blank{len(created)}", dirty=True)
        model.stage = "before" if not created else "cold"
        model.annotation, model.owner = object(), object()
        native.app.documents.append(model)
        native.app.ActiveDoc = model
        adapter.currentModel = model
        created.append(model)
        templates.append(template)
        if mode == "partial_creation":
            raise RuntimeError("creation failed after assignment")
        return model

    def snapshot(adapter):
        model = adapter.currentModel
        value = deepcopy(before if model.stage == "before" else after)
        if (mode == "save_drift" and model.stage == "saved") or (
            mode == "cold_drift" and model.stage == "cold"
        ):
            value["notes"]["label"]["horizontal"] = 2
        snapshots.append(model.stage)
        return value, {"a": (model.annotation, model.owner)}, []

    def apply(adapter, *_args):
        adapter.currentModel.stage = "after"
        if mode == "transition":
            raise RuntimeError("native clamp rejected")

    def save(model, path, row):
        row["save_return"] = 0
        if mode == "save_failed":
            raise RuntimeError("native SaveAs failed")
        path.write_bytes(b"new derived template")
        model.path, model.title, model.dirty = str(path), path.name, False
        model.stage = "saved"

    def printing(adapter, directory):
        pdf, png = directory / "format.pdf", directory / "format.png"
        pdf.write_bytes(b"PDF")
        png.write_bytes(b"PNG")
        return {"pdf": str(pdf), "png": str(png)}

    monkeypatch.setattr(probe, "bare_drawing", bare)
    monkeypatch.setattr(layout, "blank_snapshot", snapshot)
    monkeypatch.setattr(layout, "layout_plan", lambda *_: plan)
    monkeypatch.setattr(layout, "apply_layout", apply)
    monkeypatch.setattr(layout, "validation_plan", lambda *_: plan)
    monkeypatch.setattr(layout, "require_field_fit", lambda *_: {})
    monkeypatch.setattr(layout, "pdf_field_fit", lambda *_: {})
    monkeypatch.setattr(probe.defaults, "save_prepared_template", save)
    monkeypatch.setattr(probe.printed, "printed_witness", printing)

    def compare(*_):
        if mode == "print_drift":
            raise RuntimeError("printed glyphs changed")
        return {"changed_pixel_count": 0}

    monkeypatch.setattr(probe.printed, "compare_printed", compare)

    async def callback(adapter):
        return await probe.probe(adapter, tmp_path / "reports")

    if mode == "pass":
        result = asyncio.run(owned.owned_callback(native.adapter, callback))
        assert result["outcome"] == "blank_template_layout_persisted"
    else:
        with pytest.raises(ExceptionGroup):
            asyncio.run(owned.owned_callback(native.adapter, callback))
    assert native.app.documents == [baseline] and baseline.dirty
    assert baseline not in native.app.closes
    assert not native.adapter.opens
    assert original.read_bytes() == b"exact original template"
    (path,) = (tmp_path / "reports").glob("*/template-layout.json")
    report = json.loads(path.read_text())
    assert report["inputs_before"] == report["inputs_after"]
    assert report["status"] == ("passed" if mode == "pass" else "failed")
    assert len(created) == (2 if mode in {"pass", "cold_drift", "print_drift"} else 1)
    if len(created) == 2:
        assert templates[0] == original
        assert str(templates[1]) == report["derived_template"]
        assert templates[1].read_bytes() == b"new derived template"
        evidence = json.loads((path.parent / "ownership.json").read_text())
        assert str(templates[1]) in evidence["frozen_inputs"]


def test_primary_and_cleanup_errors_are_both_retained(monkeypatch, tmp_path):
    import asyncio
    import json

    original = tmp_path / "original.DRWDOT"
    original.write_bytes(b"source")
    monkeypatch.setattr(probe.common, "PROJECT_DRWDOT", original)
    monkeypatch.setattr(probe.pilot, "helper_fingerprints", lambda: {})
    monkeypatch.setattr(probe.pilot, "adapter_fingerprints", lambda: {})
    monkeypatch.setattr(probe.pilot.benchmark, "revision", lambda _: "frozen")

    async def transform(*_):
        raise RuntimeError("primary validation")

    async def close():
        raise RuntimeError("cleanup rejection")

    monkeypatch.setattr(probe, "transform", transform)
    adapter = SimpleNamespace(
        ownership=SimpleNamespace(register_directory=Mock(), register_source=Mock()),
        close_owned_documents=close,
    )
    with pytest.raises(ExceptionGroup) as result:
        asyncio.run(probe.probe(adapter, tmp_path / "reports"))
    assert len(result.value.exceptions) == 2
    (path,) = (tmp_path / "reports").glob("*/template-layout.json")
    errors = json.loads(path.read_text())["errors"]
    assert "primary validation" in errors[0] and "cleanup rejection" in errors[1]


def test_resized_native_text_height_is_not_an_unchecked_layout_wildcard():
    before, after, plan = transformed()
    for state in (before, after):
        row = state["notes"]["rev"]
        row.update(text="v32", extent_scope="measured")
        row["display"]["texts"] = [
            {"value": "v32", "height_m": 0.006, "position": [0.38, 0.025, 0]}
        ]
        row["display"]["counts"]["Text"] = 1
    after["notes"]["rev"]["display"]["texts"][0]["height_m"] = 0.0035
    layout.require_transition(before, after, plan)
    after["notes"]["rev"]["display"]["texts"][0]["height_m"] = 0.0036
    with pytest.raises(RuntimeError, match="displayed height"):
        layout.require_transition(before, after, plan)


@pytest.mark.parametrize(
    "autostart,pid,remote",
    [("1", "31860", "off"), ("0", "", "off"), ("0", "31860", "rw")],
)
def test_cli_refuses_unsafe_environment_before_parent_seat(
    monkeypatch, autostart, pid, remote
):
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", autostart)
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", pid)
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", remote)
    runner = Mock(side_effect=AssertionError("unsafe native invocation"))
    monkeypatch.setattr(probe, "run_copy_diagnostic", runner)
    with pytest.raises(RuntimeError):
        probe.main(["--worker"])
    runner.assert_not_called()


def test_unknown_template_annotation_is_not_silently_excluded(monkeypatch):
    monkeypatch.setattr(layout.cells, "required", lambda value, _: value)
    unknown = SimpleNamespace(GetType=lambda: 14)
    view = SimpleNamespace(GetAnnotations=lambda: [unknown])
    adapter = SimpleNamespace(currentModel=SimpleNamespace(GetViews=lambda: [[view]]))
    with pytest.raises(RuntimeError, match="unsupported template annotation kind 14"):
        layout.note_inventory(adapter)


def test_blank_control_refuses_a_model_reference(monkeypatch):
    monkeypatch.setattr(layout.cells, "required", lambda value, _: value)
    view = SimpleNamespace(ReferencedDocument=object())
    model = SimpleNamespace(GetViews=lambda: [[view]])
    with pytest.raises(RuntimeError, match="source model reference"):
        layout.blank_snapshot(SimpleNamespace(currentModel=model))
