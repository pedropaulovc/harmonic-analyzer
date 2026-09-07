"""Fresh title controls must reproduce first, change one operation, and stay owned."""

import asyncio
import copy
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_fresh_title_update as probe
from diagnostics import _owned_native_documents as owned
from test_owned_native_documents_drawing import Model, native  # noqa: F401


@pytest.mark.parametrize("returned", [True, False, None])
@pytest.mark.parametrize("variant,method,field,args", [
    (probe.Variant.EDIT_REBUILD, "EditRebuild3", "edit_rebuild", ()),
    (probe.Variant.FORCE_REBUILD, "ForceRebuild3", "force_rebuild", (False,)),
])
def test_rebuild_is_one_checked_pre_save_call_without_redraw(
    monkeypatch, returned, variant, method, field, args
):
    calls = []
    native_rebuild = Mock(side_effect=lambda *actual: calls.append(field) or returned)
    model = SimpleNamespace(
        GraphicsRedraw2=Mock(side_effect=AssertionError("different variant")),
    )
    setattr(model, method, native_rebuild)
    adapter = SimpleNamespace(
        currentModel=model,
        ownership=SimpleNamespace(saving_as=lambda _: __import__("contextlib").nullcontext()),
    )
    observer = SimpleNamespace(record=lambda stage: calls.append(stage))
    monkeypatch.setattr(probe.common, "apply_custom_properties", lambda *_: None)

    def save(current, path, *, artifact_context, **kwargs):
        for kind, target in (("drawing", path), ("pdf", kwargs["pdf_path"])):
            with artifact_context(kind, target):
                calls.append(kind)

    monkeypatch.setattr(probe.drawing, "save_drawing", save)

    def run():
        with probe.finalizer_observations(adapter, observer, variant) as counts:
            probe.common.apply_custom_properties(adapter, {"UNIT_DISPLAY": "MM"})
            probe.drawing.save_drawing(adapter, "owned.SLDDRW", pdf_path="owned.pdf")
        return counts

    if returned is True:
        assert run()[field] == 1
        assert (
            calls.index("before_native_save")
            < calls.index(field)
            < calls.index(f"after_pre_save_{field}")
            < calls.index("drawing")
            < calls.index("pdf")
        )
    else:
        with pytest.raises(RuntimeError, match=method):
            run()
        assert "drawing" not in calls and "pdf" not in calls
    native_rebuild.assert_called_once_with(*args)
    model.GraphicsRedraw2.assert_not_called()


def glyphs(dx=0.0, dy=0.0):
    return {
        "page_size_pt": (1224.0, 792.0),
        "text": "rocker-arm",
        "ink_box_pt": (100 + dx, 20 + dy, 119 + dx, 25 + dy),
        "characters": [
            {
                "text": letter,
                "box_pt": (100 + i * 2 + dx, 20 + dy, 101 + i * 2 + dx, 25 + dy),
            }
            for i, letter in enumerate("rocker-arm")
        ],
    }


@pytest.mark.parametrize("mode", ["preserved", "wrong_alignment", "lost_link", "throws"])
def test_same_justification_uses_void_setter_then_redraw_before_save(monkeypatch, mode):
    calls = []
    note = SimpleNamespace(justification=2, link=probe.TITLE_LINK)
    note.GetTextJustification = Mock(side_effect=lambda: note.justification)

    def set_justification(value):
        calls.append(("justify", value))
        if mode == "throws":
            raise RuntimeError("native setter failed")
        note.justification = 1 if mode == "wrong_alignment" else value
        note.link = "literal" if mode == "lost_link" else note.link
        # Native void: None must not be treated as an API failure.

    note.SetTextJustification = Mock(side_effect=set_justification)
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: note)
    model = SimpleNamespace(GraphicsRedraw2=Mock(side_effect=lambda: calls.append("redraw")))
    from contextlib import nullcontext

    adapter = SimpleNamespace(
        currentModel=model,
        ownership=SimpleNamespace(saving_as=lambda _: nullcontext()),
    )

    def observe(stage):
        calls.append(stage)
        before = {
            "key": "format/title", "linked_text": probe.TITLE_LINK,
            "horizontal_justification": 2, "vertical_justification": 0, "locked": False,
        }
        after = dict(before, horizontal_justification=note.justification, linked_text=note.link)
        probe.require_title_style(before, after)

    observer = SimpleNamespace(annotation=annotation, record=observe)
    monkeypatch.setattr(probe, "_early_bound", lambda raw, _: raw)
    original_properties = Mock()
    monkeypatch.setattr(probe.common, "apply_custom_properties", original_properties)

    def save(current, path, *, artifact_context, **kwargs):
        for kind, target in (("drawing", path), ("pdf", kwargs["pdf_path"])):
            with artifact_context(kind, target):
                calls.append(kind)

    monkeypatch.setattr(probe.drawing, "save_drawing", save)

    def run():
        with probe.finalizer_observations(adapter, observer, probe.Variant.REJUSTIFY) as counts:
            probe.common.apply_custom_properties(adapter, {"UNIT_DISPLAY": "MM"})
            probe.drawing.save_drawing(adapter, "owned.SLDDRW", pdf_path="owned.pdf")
        return counts

    if mode == "preserved":
        assert run() == {
            "properties": 1, "drawing": 1, "pdf": 1,
            "redraw": 1, "edit_rebuild": 0, "force_rebuild": 0, "justification": 1,
        }
        assert calls.index("before_native_save") < calls.index(("justify", 2))
        assert calls.index(("justify", 2)) < calls.index("after_pre_save_rejustify")
        assert calls.index("after_pre_save_rejustify") < calls.index("redraw")
        assert calls.index("redraw") < calls.index("after_pre_save_rejustify_redraw")
        assert calls.index("after_pre_save_rejustify_redraw") < calls.index("drawing")
        assert calls.index("drawing") < calls.index("pdf")
        model.GraphicsRedraw2.assert_called_once_with()
    else:
        with pytest.raises(RuntimeError):
            run()
        assert "drawing" not in calls and "pdf" not in calls
        model.GraphicsRedraw2.assert_not_called()
    note.GetTextJustification.assert_called_once_with()
    note.SetTextJustification.assert_called_once_with(2)
    assert probe.common.apply_custom_properties is original_properties
    assert probe.drawing.save_drawing is save


def test_glyph_classification_requires_material_rigid_printed_movement():
    assert (
        probe.printed_displacement(glyphs(), glyphs())["classification"] == "unchanged"
    )
    result = probe.printed_displacement(glyphs(), glyphs(20.481))
    assert result["classification"] == "reproduced"
    assert result["displacement_mm"] == pytest.approx((7.22524, 0))
    assert (
        probe.printed_displacement(glyphs(), glyphs(0.000001))["classification"]
        == "subpixel_delta"
    )
    distorted = glyphs(20)
    distorted["characters"][2]["box_pt"] = (123, 20, 124, 25)
    assert (
        probe.printed_displacement(glyphs(), distorted)["classification"]
        == "nonrigid_delta"
    )


@pytest.mark.parametrize("field", ["text", "page", "count", "glyph", "nan"])
def test_glyph_invalid_content_or_geometry_is_never_a_positive_control(field):
    after = glyphs(20)
    if field == "text":
        after["text"] = "wrong"
    if field == "page":
        after["page_size_pt"] = (612, 792)
    if field == "count":
        after["characters"].pop()
    if field == "glyph":
        after["characters"][0]["text"] = "X"
    if field == "nan":
        after["characters"][0]["box_pt"] = (float("nan"), 0, 2, 3)
    with pytest.raises(RuntimeError):
        probe.printed_displacement(glyphs(), after)


@pytest.mark.parametrize(
    "classification", ["unchanged", "subpixel_delta", "nonrigid_delta"]
)
@pytest.mark.parametrize(
    "candidate", [probe.Variant.REDRAW, probe.Variant.EDIT_REBUILD, probe.Variant.REJUSTIFY]
)
def test_candidate_is_not_even_started_without_reproduction(classification, candidate):
    calls = []

    async def trial(variant):
        calls.append(variant)
        return {
            "printed": {"classification": classification},
            "png_delta": {"changed_pixel_count": 100},
        }

    result = asyncio.run(probe.run_pair(trial, candidate))
    assert calls == [probe.Variant.BASELINE]
    assert result == "inconclusive_baseline_not_reproduced"


def test_reproduced_pdf_without_changed_pixels_is_not_candidate_authority():
    async def trial(_):
        return {
            "printed": {"classification": "reproduced"},
            "png_delta": {"changed_pixel_count": 0},
        }

    with pytest.raises(RuntimeError, match="pixels"):
        asyncio.run(probe.run_pair(trial, probe.Variant.REDRAW))


@pytest.mark.parametrize(
    "candidate", [probe.Variant.REDRAW, probe.Variant.EDIT_REBUILD, probe.Variant.REJUSTIFY]
)
def test_candidate_runs_once_after_baseline_and_keeps_failure(candidate):
    calls = []

    async def trial(variant):
        calls.append(variant)
        if variant is candidate:
            raise RuntimeError("native failed")
        return {
            "printed": {"classification": "reproduced"},
            "png_delta": {"changed_pixel_count": 80},
        }

    with pytest.raises(RuntimeError, match="native failed"):
        asyncio.run(probe.run_pair(trial, candidate))
    assert calls == [probe.Variant.BASELINE, candidate]


@pytest.mark.parametrize("candidate", [probe.Variant.BASELINE, "pre_save_edit_rebuild"])
def test_pair_requires_an_explicit_candidate_enum_before_baseline(candidate):
    trial = Mock(side_effect=AssertionError("must reject before native trial"))
    with pytest.raises(ValueError):
        asyncio.run(probe.run_pair(trial, candidate))
    trial.assert_not_called()


@pytest.mark.parametrize("candidate", [[], ["baseline"], ["unknown"]])
def test_cli_rejects_missing_or_invalid_candidate_before_environment(
    monkeypatch, candidate
):
    environment = Mock(side_effect=AssertionError("CLI must reject first"))
    monkeypatch.setattr(probe, "require_owned_diagnostic_environment", environment)
    arguments = ["--source", "part.SLDPRT", "--guard-source", "guard.SLDPRT"]
    if candidate:
        arguments.extend(("--candidate", *candidate))
    with pytest.raises(SystemExit) as error:
        probe.main(arguments)
    assert error.value.code == 2
    environment.assert_not_called()


@pytest.mark.parametrize(
    "variant", [probe.Variant.BASELINE, probe.Variant.REDRAW, probe.Variant.EDIT_REBUILD]
)
def test_finalizer_hooks_preserve_call_order_and_only_candidate_redraws(
    monkeypatch, variant
):
    calls = []
    model = SimpleNamespace(
        GraphicsRedraw2=lambda: calls.append("redraw"),
        EditRebuild3=lambda: calls.append("edit_rebuild") or True,
    )
    ownership = SimpleNamespace()

    @contextmanager
    def saving_as(path):
        calls.append(("owned_save", path))
        yield

    ownership.saving_as = saving_as
    adapter = SimpleNamespace(currentModel=model, ownership=ownership)
    observer = SimpleNamespace(record=lambda stage: calls.append(stage))

    def properties(current, values):
        assert current is adapter and values == {"UNIT_DISPLAY": "MM"}
        calls.append("property_write")

    @contextmanager
    def context(kind, path):
        calls.append(("original_span", kind))
        yield

    def save(current, path, *, artifact_context, **kwargs):
        assert current is adapter
        for kind, target in (("drawing", path), ("pdf", kwargs["pdf_path"])):
            with artifact_context(kind, target):
                calls.append(("native", kind))
        return {"drawing": path, "pdf": kwargs["pdf_path"]}

    monkeypatch.setattr(probe.common, "apply_custom_properties", properties)
    monkeypatch.setattr(probe.drawing, "save_drawing", save)
    with probe.finalizer_observations(adapter, observer, variant) as receipt:
        probe.common.apply_custom_properties(adapter, {"UNIT_DISPLAY": "MM"})
        probe.drawing.save_drawing(
            adapter, "copy.SLDDRW", pdf_path="copy.pdf", artifact_context=context
        )
    assert probe.common.apply_custom_properties is properties
    assert probe.drawing.save_drawing is save
    assert receipt == {
        "properties": 1,
        "drawing": 1,
        "pdf": 1,
        "redraw": int(variant is probe.Variant.REDRAW),
        "edit_rebuild": int(variant is probe.Variant.EDIT_REBUILD),
        "force_rebuild": 0,
        "justification": 0,
    }
    assert (
        calls.index("after_property_link_before_unit")
        < calls.index("property_write")
        < calls.index("after_unit_property")
    )
    assert (
        calls.index("before_native_save")
        < calls.index(("native", "drawing"))
        < calls.index("after_native_save")
    )
    assert (
        calls.index("after_native_save")
        < calls.index("before_pdf_export")
        < calls.index(("native", "pdf"))
    )
    assert calls.count("redraw") == int(variant is probe.Variant.REDRAW)
    assert calls.count("edit_rebuild") == int(variant is probe.Variant.EDIT_REBUILD)
    if variant is probe.Variant.REDRAW:
        assert (
            calls.index("before_native_save")
            < calls.index("redraw")
            < calls.index("after_pre_save_redraw")
            < calls.index(("native", "drawing"))
        )


def test_wrappers_restore_after_native_failure(monkeypatch):
    props = Mock()
    save = Mock(side_effect=RuntimeError("save failed"))
    monkeypatch.setattr(probe.common, "apply_custom_properties", props)
    monkeypatch.setattr(probe.drawing, "save_drawing", save)
    observer = SimpleNamespace(record=Mock())
    adapter = SimpleNamespace(
        ownership=SimpleNamespace(
            saving_as=lambda _: __import__("contextlib").nullcontext()
        )
    )
    with pytest.raises(RuntimeError, match="save failed"):
        with probe.finalizer_observations(adapter, observer, probe.Variant.BASELINE):
            probe.common.apply_custom_properties(adapter, {"UNIT_DISPLAY": "MM"})
            probe.drawing.save_drawing(adapter, "copy.SLDDRW", pdf_path="copy.pdf")
    assert probe.common.apply_custom_properties is props
    assert probe.drawing.save_drawing is save


def test_environment_rejected_before_parent_native_wrapper(monkeypatch, tmp_path):
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")
    with pytest.raises(RuntimeError, match="AUTOSTART"):
        probe.main(
            [
                "--source",
                str(tmp_path / "missing"),
                "--candidate",
                probe.Variant.EDIT_REBUILD.value,
                "--guard-source",
                str(tmp_path / "missing"),
            ]
        )


@pytest.mark.parametrize("outcome", ["stable", "printed_shift", "other_pixels"])
def test_candidate_result_is_only_a_printed_observation(outcome):
    calls = []

    async def trial(variant):
        calls.append(variant)
        if variant is probe.Variant.BASELINE:
            return {
                "printed": {"classification": "reproduced"},
                "png_delta": {"changed_pixel_count": 40},
            }
        return {
            "printed": {
                "classification": "unchanged"
                if outcome != "printed_shift"
                else "reproduced"
            },
            "png_delta": {"changed_pixel_count": 0 if outcome == "stable" else 1},
        }

    assert asyncio.run(probe.run_pair(trial, probe.Variant.REDRAW)) == (
        "candidate_printed_stable" if outcome == "stable" else "candidate_not_stable"
    )
    assert calls == [probe.Variant.BASELINE, probe.Variant.REDRAW]


def title_native(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    owner = object()
    note = SimpleNamespace(
        GetText=lambda: probe.TITLE,
        PropertyLinkedText=probe.TITLE_LINK,
        GetTextJustification=lambda: 2,
        GetTextVerticalJustification=lambda: 0,
        LockPosition=False,
        GetExtent=lambda: (0.36, 0.04, 0, 0.398, 0.047, 0),
    )
    annotation = SimpleNamespace(
        GetName=lambda: "TemplateTitle",
        GetType=lambda: 6,
        OwnerType=2,
        Owner=owner,
        GetSpecificAnnotation=lambda: note,
        GetPosition=lambda: (0.379, 0.047, 0),
    )
    sheet = SimpleNamespace(CustomPropertyView="Default")
    view = SimpleNamespace(
        GetName2=lambda: "Sheet1", GetAnnotations=lambda: (annotation,)
    )
    model = SimpleNamespace(
        GetType=lambda: 3,
        Visible=True,
        GetViews=lambda: ((view,),),
        GetCurrentSheet=lambda: sheet,
        GetPathName=lambda: "",
        GetCustomInfoValue=lambda *_: "MM",
    )
    app = SimpleNamespace(ActiveDoc=model, IsSame=lambda a, b: int(a is b))
    adapter = SimpleNamespace(currentModel=model, swApp=app)
    raw = {
        "lines": [],
        "arcs": [],
        "texts": [{"value": probe.TITLE, "position": (0.361, 0.040, 0)}],
    }
    monkeypatch.setattr(
        probe.pilot.shoulder, "raw_display_data", lambda _: copy.deepcopy(raw)
    )
    return adapter, view, annotation, note, raw


def test_title_resolved_and_generic_positions_are_separate_raw_observations(
    monkeypatch,
):
    adapter, _, annotation, note, raw = title_native(monkeypatch)
    trial = {}
    observer = probe.TitleObserver(adapter, trial, Mock())
    before = observer.record("before_native_save")
    raw["texts"][0]["position"] = (0.368225, 0.040, 0)
    after = observer.record("after_native_save")
    assert before["position"] == after["position"]
    assert before["extent"] == after["extent"]
    assert before["generic"] != after["generic"]
    assert trial["title_stages"] == [before, after]


@pytest.mark.parametrize(
    "variant",
    [
        "wrong_link",
        "wrong_text",
        "wrong_kind",
        "wrong_owner",
        "hidden",
        "replaced_model",
        "inactive",
        "bad_extent",
        "bad_position",
        "alignment",
    ],
)
def test_title_observer_rejects_native_context_or_semantic_mutation(
    monkeypatch, variant
):
    adapter, _, annotation, note, _ = title_native(monkeypatch)
    observer = probe.TitleObserver(adapter, {}, Mock())
    if variant == "wrong_link":
        note.PropertyLinkedText = '$PRPSHEET:"Other"'
    if variant == "wrong_text":
        note.GetText = lambda: "wrong"
    if variant == "wrong_kind":
        annotation.OwnerType = 0
    if variant == "wrong_owner":
        annotation.Owner = object()
    if variant == "hidden":
        adapter.currentModel.Visible = False
    if variant == "replaced_model":
        adapter.currentModel = object()
    if variant == "inactive":
        adapter.swApp.ActiveDoc = object()
    if variant == "bad_extent":
        note.GetExtent = lambda: ()
    if variant == "bad_position":
        annotation.GetPosition = lambda: (float("nan"), 0, 0)
    if variant == "alignment":
        note.GetTextJustification = lambda: 10
    with pytest.raises(RuntimeError):
        observer.record("before_native_save")


def test_blank_may_be_unresolved_but_title_link_must_be_unique(monkeypatch):
    adapter, view, annotation, note, _ = title_native(monkeypatch)
    note.GetText = lambda: ""
    observer = probe.TitleObserver(adapter, {}, Mock())
    assert observer.record("after_blank_setup")["text"] == ""
    with pytest.raises(RuntimeError, match="resolve"):
        observer.record("before_native_save")
    view.GetAnnotations = lambda: (annotation, annotation)
    with pytest.raises(RuntimeError, match="one exact"):
        probe.find_title(adapter)


@pytest.mark.parametrize(
    "field,value",
    [
        ("key", "Sheet1/Replacement"),
        ("linked_text", "other"),
        ("horizontal_justification", 1),
        ("vertical_justification", 1),
        ("locked", True),
    ],
)
def test_cold_title_style_change_is_not_a_recenter_observation(
    monkeypatch, field, value
):
    adapter, _, _, _, _ = title_native(monkeypatch)
    observer = probe.TitleObserver(adapter, {}, Mock())
    before = observer.record("before_native_save")
    after = copy.deepcopy(before)
    after[field] = value
    with pytest.raises(RuntimeError, match="style"):
        probe.require_title_style(before, after)


def test_same_session_valid_but_changed_justification_is_rejected(monkeypatch):
    adapter, _, _, note, _ = title_native(monkeypatch)
    observer = probe.TitleObserver(adapter, {}, Mock())
    observer.record("after_blank_setup")
    note.GetTextJustification = lambda: 1
    with pytest.raises(RuntimeError, match="style"):
        observer.record("after_front_view")


@pytest.mark.parametrize(
    "mode",
    [
        "normal",
        "not_reproduced",
        "first_save_failed",
        "candidate_save_failed",
        "copy_saved",
        "wrong_reference",
    ],
)
def test_owned_fresh_pair_preserves_originals_and_two_visible_baseline_docs(
    native,  # noqa: F811
    monkeypatch,
    tmp_path,
    mode,
):
    original_hash = probe.pilot.attachments.file_digest(native.source)
    monkeypatch.setattr(probe, "EXPECTED_SOURCE_SHA256", original_hash)
    baseline_part = Model(native.source, kind=1)
    baseline_drawing = Model(None, title="Draw2 - Sheet1", dirty=True)
    native.app.documents.extend((baseline_part, baseline_drawing))
    native.app.ActiveDoc = baseline_drawing
    source_snap = {
        "configuration": "Default",
        "dimensions": {"Diameter": {"value": 0.01, "tolerance_type": 1}},
    }
    created, saves, sources = [], [], {}
    base_open = native.adapter.open_model

    async def open_model(path):
        result = await base_open(path)
        model = native.adapter.currentModel
        model.title_note = object()
        model.SummaryInfo = lambda _: probe.TITLE
        if Path(path).suffix.upper() == ".SLDDRW":
            part = Model(sources[str(path)], kind=1)
            part.SummaryInfo = lambda _: probe.TITLE
            native.app.documents.append(part)
            model.references = [part]
        return result

    native.adapter.open_model = open_model
    monkeypatch.setattr(
        probe.pilot,
        "source_dimensions",
        lambda model, *_: (copy.deepcopy(source_snap), {"dimension": model}),
    )
    monkeypatch.setattr(probe.pilot, "helper_fingerprints", lambda: {})
    monkeypatch.setattr(probe.pilot, "adapter_fingerprints", lambda: {})
    monkeypatch.setattr(probe.pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(probe.common, "apply_custom_properties", lambda *_: None)

    def blank(adapter, **_):
        model = Model(None, title=f"Fresh{len(created)}", dirty=True)
        model.title_note = object()
        model.GraphicsRedraw2 = Mock()
        native.app.documents.append(model)
        native.app.ActiveDoc = model
        adapter.currentModel = model
        created.append(model)
        return model, object()

    monkeypatch.setattr(probe.drawing, "new_project_drawing", blank)

    def front(adapter, path, *_args, **_kwargs):
        part = native.app.GetOpenDocumentByName(path)
        adapter.currentModel.references = [part]
        return SimpleNamespace(
            ReferencedDocument=baseline_part if mode == "wrong_reference" else part
        )

    monkeypatch.setattr(probe, "place_view", front)

    class Observer:
        def __init__(self, adapter, trial, checkpoint):
            self.annotation, self.key = adapter.currentModel.title_note, "Sheet1/Title"
            self.trial, self.checkpoint = trial, checkpoint
            trial["title_stages"] = []

        def record(self, stage):
            row = {
                "stage": stage,
                "key": self.key,
                "linked_text": probe.TITLE_LINK,
                "horizontal_justification": 2,
                "vertical_justification": 0,
                "locked": False,
            }
            self.trial["title_stages"].append(row)
            self.checkpoint()
            return row

    monkeypatch.setattr(probe, "TitleObserver", Observer)

    def save(adapter, path, *, pdf_path, artifact_context):
        model = adapter.currentModel
        for kind, target in (("drawing", path), ("pdf", pdf_path)):
            with artifact_context(kind, target):
                saves.append((kind, target))
                if mode == "first_save_failed" or (
                    mode == "candidate_save_failed" and "pre_save_redraw" in str(path)
                ):
                    raise RuntimeError("native save failed")
                Path(target).write_bytes(kind.encode())
                if kind == "drawing":
                    model.path, model.title, model.dirty = (
                        str(path),
                        Path(path).name,
                        False,
                    )
                    sources[str(path)] = model.references[0].GetPathName()
                    if mode == "copy_saved":
                        Path(sources[str(path)]).write_bytes(b"unexpected source save")
        return {"drawing": str(path), "pdf": str(pdf_path)}

    monkeypatch.setattr(probe.drawing, "save_drawing", save)

    async def finalize(adapter, outputs, **_):
        probe.common.apply_custom_properties(adapter, {"UNIT_DISPLAY": "MM"})
        artifacts = probe.drawing.save_drawing(
            adapter, outputs.slddrw, pdf_path=outputs.pdf
        )
        outputs.png.write_bytes(b"PNG")
        return {**artifacts, "png": str(outputs.png)}

    monkeypatch.setattr(probe.drawing, "finalize_drawing", finalize)
    witness = {
        "semantics": {},
        "layout": {},
        "annotations": {
            "Sheet1/Title": {
                "semantic": {"text": "rocker-arm"},
                "position": (0.1, 0.2, 0),
                "generic": {},
            }
        },
    }
    monkeypatch.setattr(
        probe.retained,
        "capture_drawing",
        lambda adapter, *_: (
            copy.deepcopy(witness),
            {"Sheet1/Title": (adapter.currentModel.title_note,)},
        ),
    )
    monkeypatch.setattr(probe.pilot.attachments, "compare", lambda *_: None)
    monkeypatch.setattr(probe.pilot.attachments, "check_layout", lambda *_: None)
    monkeypatch.setattr(
        probe.retained, "export_pdf_only", lambda _, pdf: pdf.write_bytes(b"coldPDF")
    )
    monkeypatch.setattr(
        probe.drawing, "render_pdf_png", lambda _, png: png.write_bytes(b"coldPNG")
    )
    monkeypatch.setattr(
        probe.retained,
        "pdf_title",
        lambda path: glyphs(
            20
            if path.name == "cold.pdf"
            and path.parent.name == "baseline"
            and mode != "not_reproduced"
            else 0
        ),
    )
    monkeypatch.setattr(
        probe.retained,
        "compare_png",
        lambda before, _: {
            "changed_pixel_count": 100
            if before.parent.name == "baseline" and mode != "not_reproduced"
            else 0
        },
    )

    async def callback(adapter):
        return await probe.probe(
            adapter,
            native.source,
            native.source,
            tmp_path / "reports",
            probe.Variant.REDRAW,
        )

    if mode in ("normal", "not_reproduced"):
        result = asyncio.run(owned.owned_callback(native.adapter, callback))
        assert result["outcome"] == (
            "candidate_printed_stable"
            if mode == "normal"
            else "inconclusive_baseline_not_reproduced"
        )
    else:
        with pytest.raises((RuntimeError, ExceptionGroup)):
            asyncio.run(owned.owned_callback(native.adapter, callback))
    assert native.app.documents == [baseline_part, baseline_drawing]
    assert not baseline_part.dirty and baseline_drawing.dirty
    assert all(
        model not in (baseline_part, baseline_drawing) for model in native.app.closes
    )
    assert str(native.source) not in native.adapter.opens
    assert probe.pilot.attachments.file_digest(native.source) == original_hash
    assert len(created) == (2 if mode in ("normal", "candidate_save_failed") else 1)
    assert created[0].GraphicsRedraw2.call_count == 0
    if len(created) == 2:
        assert created[1].GraphicsRedraw2.call_count == 1
    (receipt,) = (tmp_path / "reports").glob("*/title-update.json")
    report = __import__("json").loads(receipt.read_text())
    assert report["inputs_before"] == report["inputs_after"]
    if mode == "copy_saved":
        assert (
            report["trials"][0]["copy_hashes"]["initial"]
            != report["trials"][0]["copy_hashes"]["final"]
        )
