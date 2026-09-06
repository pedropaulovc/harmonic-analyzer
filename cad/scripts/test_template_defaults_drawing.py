"""COM-free contracts for the inherited drawing-template ABBA control."""

import asyncio
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from diagnostics import benchmark_template_defaults as probe
from diagnostics import probe_drawing_template_save as save_control


def test_variants_preserve_exact_sheet_ratio_and_precision():
    first = probe.TemplateSpec((2, 1), 2)
    assert first.scale == (2.0, 1.0)
    assert first != probe.TemplateSpec((1, 1), 2)
    assert first != probe.TemplateSpec((2, 1), 3)


@pytest.mark.parametrize(
    "scale,decimals",
    [((0, 1), 2), ((1, float("nan")), 2), ((1, 1), -1), ((1, 1), True)],
)
def test_invalid_template_variant_fails_before_native_work(scale, decimals):
    with pytest.raises(ValueError):
        probe.TemplateSpec(scale, decimals)


def test_unit_contract_preserves_observed_custom_mm_terminal_state():
    probe.validate_units(
        {"system": 4, "linear": 0, "decimals": 2}, probe.TemplateSpec((2, 1), 2)
    )


@pytest.mark.parametrize(
    "units",
    [
        {"system": 5, "linear": 0, "decimals": 2},
        {"system": 4, "linear": 3, "decimals": 2},
        {"system": 4, "linear": 0, "decimals": 3},
    ],
)
def test_unit_contract_does_not_wildcard_system_length_or_precision(units):
    with pytest.raises(RuntimeError, match="units/precision differ"):
        probe.validate_units(units, probe.TemplateSpec((2, 1), 2))


@pytest.fixture
def blank_note(monkeypatch):
    counts = {
        name: 0
        for name in (
            "Text",
            "Line",
            "Arc",
            "PolyLine",
            "Triangle",
            "ArrowHead",
            "Polygon",
            "Ellipse",
            "Parabola",
            "Point",
        )
    }
    data = SimpleNamespace(
        **{f"Get{name}Count": lambda name=name: counts[name] for name in counts}
    )
    fmt = SimpleNamespace(
        TypeFaceName="Century Gothic",
        CharHeight=0.0035,
        CharHeightInPts=13,
        IsHeightSpecifiedInPts=lambda: False,
        WidthFactor=1.0,
        Bold=False,
        Italic=False,
    )
    note = SimpleNamespace(
        GetText=lambda: "",
        PropertyLinkedText='$PRPSHEET:"Material"',
        HasMultipleFonts=False,
        GetExtent=lambda: (0.1, 0.2, 0, 0.16, 0.21, 0),
    )
    annotation = SimpleNamespace(
        GetType=lambda: 6,
        GetName=lambda: "generated-note",
        GetDisplayData=lambda: data,
        GetLeaderCount=lambda: 0,
        GetMultiJogLeaderCount=lambda: 0,
        GetTextFormatCount=lambda: 1,
        GetTextFormat=lambda index: fmt,
        GetUseDocTextFormat=lambda index: True,
        GetPosition=lambda: (0.1, 0.21, 0),
        GetSpecificAnnotation=lambda: note,
        Visible=1,
    )
    monkeypatch.setattr(probe, "_early_bound", lambda raw, kind: raw)
    return SimpleNamespace(annotation=annotation, note=note, counts=counts, fmt=fmt)


def test_blank_link_requires_native_zero_ink_and_keeps_anchor_font(blank_note):
    witness = probe.blank_linked_note_witness(blank_note.annotation, blank_note.note)
    assert set(witness["native_counts"].values()) == {0}
    assert witness["anchor"] == [0.1, 0.21, 0]
    assert witness["font_definition"]["font"] == "Century Gothic"
    assert witness["font_definition"]["height_m"] == 0.0035


@pytest.mark.parametrize(
    "kind",
    [
        "Text",
        "Line",
        "Arc",
        "PolyLine",
        "Triangle",
        "ArrowHead",
        "Polygon",
        "Ellipse",
        "Parabola",
        "Point",
    ],
)
def test_empty_gettext_never_hides_native_display_ink(blank_note, kind):
    blank_note.counts[kind] = 1
    with pytest.raises((RuntimeError, ValueError), match="primitive"):
        probe.blank_linked_note_witness(blank_note.annotation, blank_note.note)


@pytest.mark.parametrize("field", ["GetLeaderCount", "GetMultiJogLeaderCount"])
def test_blank_link_exclusion_refuses_native_leaders(blank_note, field):
    setattr(blank_note.annotation, field, lambda: 1)
    with pytest.raises(RuntimeError, match="leaders"):
        probe.blank_linked_note_witness(blank_note.annotation, blank_note.note)


def test_blank_link_exclusion_requires_the_documented_font_scope(blank_note):
    blank_note.note.HasMultipleFonts = True
    with pytest.raises(RuntimeError, match="formatting"):
        probe.blank_linked_note_witness(blank_note.annotation, blank_note.note)


def test_blank_linked_extents_are_raw_only_after_native_proof(monkeypatch, blank_note):
    @dataclass
    class Bounds:
        name: str
        kind: int = 6

    edge_note = SimpleNamespace(
        GetText=lambda: probe.common._METRIC_EDGE_BREAK_NOTE,
        PropertyLinkedText="",
        GetExtent=lambda: (0.2, 0.3, 0, 0.25, 0.31, 0),
    )
    edge_annotation = SimpleNamespace(
        GetType=lambda: 6, GetSpecificAnnotation=lambda: edge_note, Visible=1
    )
    sheet = SimpleNamespace(GetProperties2=lambda: (2, 12, 2, 1, 0, 0.4318, 0.2794, 1))
    view = SimpleNamespace(
        GetAnnotations=lambda: [edge_annotation, blank_note.annotation]
    )
    model = SimpleNamespace(
        GetCurrentSheet=lambda: sheet,
        GetFirstView=lambda: view,
        GetEditSheet=lambda: True,
        GetUserPreferenceIntegerValue=lambda key: {263: 4, 47: 0, 49: 2}[key],
        Extension=SimpleNamespace(GetUserPreferenceInteger=lambda pref, scope: 2),
    )
    monkeypatch.setattr(
        probe.common, "assert_asme_b_sheet", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(probe, "annotation_box", lambda *args: Bounds("edge-break"))
    adapter = SimpleNamespace(currentModel=model)
    spec = probe.TemplateSpec((2, 1), 2)
    before = probe.defaults_snapshot(adapter, spec)
    blank_note.note.GetExtent = lambda: (0.1, 0.2, 0, 0.1, 0.21, 0)
    after = probe.defaults_snapshot(adapter, spec)
    assert before != after
    assert probe.defaults_semantics(before) == probe.defaults_semantics(after)
    assert before["blank_linked_extent_observations"][0]["extent"][3] == 0.16
    assert after["blank_linked_extent_observations"][0]["extent"][3] == 0.1
    blank_note.fmt.Bold = True
    changed_font = probe.defaults_snapshot(adapter, spec)
    assert probe.defaults_semantics(changed_font) != probe.defaults_semantics(after)
    blank_note.fmt.Bold = False
    blank_note.annotation.GetPosition = lambda: (0.101, 0.21, 0)
    changed_anchor = probe.defaults_snapshot(adapter, spec)
    assert probe.defaults_semantics(changed_anchor) != probe.defaults_semantics(after)
    blank_note.annotation.GetPosition = lambda: (0.1, 0.21, 0)
    blank_note.note.PropertyLinkedText = '$PRPSHEET:"Finish"'
    changed_expression = probe.defaults_snapshot(adapter, spec)
    assert probe.defaults_semantics(changed_expression) != probe.defaults_semantics(
        after
    )


def test_nonempty_note_extent_is_still_a_strict_semantic_witness():
    first = {
        "sheet_notes": probe.semantic_multiset(
            [{"text": "Material: steel", "extent": [0.1, 0.2, 0, 0.16, 0.21, 0]}]
        )
    }
    second = {
        "sheet_notes": probe.semantic_multiset(
            [{"text": "Material: steel", "extent": [0.1, 0.2, 0, 0.17, 0.21, 0]}]
        )
    }
    assert probe.defaults_semantics(first) != probe.defaults_semantics(second)


def test_candidate_omits_all_setters_and_blank_rebuilds(monkeypatch, tmp_path):
    calls = []
    template = tmp_path / "owned.DRWDOT"
    template.write_bytes(b"derived template")
    draw = SimpleNamespace(ViewZoomtofit2=lambda: calls.append("zoom"))
    sheet = object()
    ddoc = SimpleNamespace(
        EditSheet=lambda: calls.append("edit_sheet"), GetCurrentSheet=lambda: sheet
    )
    adapter = SimpleNamespace(currentModel=draw)
    monkeypatch.setattr(probe, "_early_bound", lambda raw, kind: ddoc)
    monkeypatch.setattr(
        probe.drawing,
        "new_drawing",
        lambda *args, **kwargs: calls.append(("new", kwargs["template"])) or draw,
    )
    monkeypatch.setattr(
        probe.common,
        "assert_asme_b_sheet",
        lambda *args, **kwargs: calls.append(("assert", kwargs["scale"])),
    )
    assert probe.inherited_drawing(
        adapter, template, probe.TemplateSpec((2, 1), 2)
    ) == (draw, sheet)
    assert calls == [
        ("new", str(template)),
        "edit_sheet",
        ("assert", (2.0, 1.0)),
        "zoom",
    ]


def test_missing_candidate_template_never_falls_back_to_seat_default(tmp_path):
    with pytest.raises(FileNotFoundError):
        probe.inherited_drawing(
            object(), tmp_path / "missing.DRWDOT", probe.TemplateSpec((1, 1), 2)
        )


def test_setup_injection_is_module_local_and_preserves_arguments():
    def original(*args, **kwargs):
        return "draw", "sheet"

    def replacement(*args, **kwargs):
        return "candidate", "sheet"

    module = SimpleNamespace(new_project_drawing=original)
    with probe.replaced_setup(module, replacement):
        assert module.new_project_drawing is replacement
    assert module.new_project_drawing is original


def test_setup_injection_restores_on_error():
    original = object()
    module = SimpleNamespace(new_project_drawing=original)
    with pytest.raises(RuntimeError):
        with probe.replaced_setup(module, object()):
            raise RuntimeError("recipe failed")
    assert module.new_project_drawing is original


def test_setup_contract_rejects_unexpected_runtime_variant():
    expected = probe.TemplateSpec((2, 1), 2)
    probe.check_setup_arguments(expected, {"scale": (2, 1), "property_view": "part"})
    with pytest.raises(ValueError, match="variant"):
        probe.check_setup_arguments(expected, {"scale": (1, 1)})
    with pytest.raises(ValueError, match="keyword"):
        probe.check_setup_arguments(expected, {"scale": (2, 1), "quality": "draft"})


def test_same_native_key_changes_are_detected_on_reopen():
    before = {"a": {"body": [0, 1, 2, 3]}}
    with pytest.raises(RuntimeError, match="reopen"):
        probe.compare_exact(before, {"a": {"body": [0, 1, 2, 4]}}, "reopen")


def test_semantic_multiset_preserves_duplicates_but_not_generated_ids():
    first = {
        "DetailItem1": {"kind": 4, "value": 0.127},
        "DetailItem2": {"kind": 4, "value": 0.127},
    }
    second = {
        "DetailItem55": {"kind": 4, "value": 0.127},
        "DetailItem56": {"kind": 4, "value": 0.127},
    }
    assert probe.semantic_multiset(first.values()) == probe.semantic_multiset(
        second.values()
    )
    assert probe.semantic_multiset(first.values()) != probe.semantic_multiset(
        [{"kind": 4, "value": 0.127}]
    )


@pytest.mark.parametrize(
    "returned", [(False, 1, 0), (False, 0, 0), (True, 1, 0), True, (True, 0), (1, 0, 0)]
)
def test_partial_template_file_does_not_prove_success(tmp_path, returned):
    target = tmp_path / "partial.DRWDOT"
    target.write_bytes(b"partial output")
    with pytest.raises(RuntimeError, match="SaveAs3 failed"):
        save_control.require_save_result(returned, target)


def test_save_requires_documented_success_and_complete_file(tmp_path):
    target = tmp_path / "owned.DRWDOT"
    with pytest.raises(RuntimeError, match="complete file"):
        save_control.require_save_result((True, 0, 0), target)
    target.write_bytes(b"complete file")
    save_control.require_save_result(
        (True, 0, 4), target
    )  # Warnings stay in the report.


def test_preparation_uses_the_persisted_legacy_shape_once(tmp_path):
    path, calls, row = tmp_path / "owned.DRWDOT", [], {}

    def save(name, version, options):
        calls.append((name, version, options))
        Path(name).write_bytes(b"owned saved template")
        return 0

    model = SimpleNamespace(
        ClearSelection2=lambda all: calls.append(("clear", all)), SaveAs3=save
    )
    probe.save_prepared_template(model, path, row)
    assert calls == [("clear", True), (str(path), 0, 0)]
    assert row["save_return"] == 0
    assert row["save_method"] == "IModelDoc2.SaveAs3(path,0,0)"


def test_preparation_never_accepts_legacy_integer_without_fresh_file(tmp_path):
    model = SimpleNamespace(ClearSelection2=lambda all: None, SaveAs3=lambda *args: 0)
    path = tmp_path / "missing.DRWDOT"
    with pytest.raises(RuntimeError, match="no complete file"):
        probe.save_prepared_template(model, path, {})
    path.write_bytes(b"pre-existing")
    with pytest.raises(ValueError, match="not fresh"):
        probe.save_prepared_template(model, path, {})


def test_immutable_hash_is_pinned_before_replacement(tmp_path):
    source = tmp_path / "part.SLDPRT"
    source.write_bytes(b"initial native identity")
    pinned = probe.immutable_hashes([source])
    source.write_bytes(b"replaced between trials")
    assert (
        probe.immutable_changes(pinned)[str(source)]["expected"] == pinned[str(source)]
    )


def test_actual_two_recipes_redirect_before_evaluating_output_aliases(tmp_path):
    specs = []
    commit = probe.recipes.revision("HEAD")
    for target in probe.TARGETS:
        source = tmp_path / f"{probe.DRAWINGS_BY_NAME[target].artifact_stem}.SLDPRT"
        source.write_bytes(b"fixture native file; never opened")
        trial = tmp_path / target
        trial.mkdir()
        module, spec = probe.load_recipe(commit, target, trial, source)
        assert module.SOURCE == source
        assert module.SLDDRW == module.OUTPUTS.slddrw
        assert module.PDF == module.OUTPUTS.pdf
        assert module.PNG == module.OUTPUTS.png
        assert all(
            path.parent == trial for path in (module.SLDDRW, module.PDF, module.PNG)
        )
        specs.append(spec)
    assert specs == [probe.TemplateSpec((2, 1), 2)] * 2


def test_cross_arm_checks_sheet_notes_and_empty_view_quality():
    source, digest = Path("C:/same/marker.SLDPRT"), "a" * 64
    snapshot = {
        "defaults": {"sheet_notes": ["0.25 MM"]},
        "view_modes": [json.dumps("precise")],
        "semantic_annotations": [],
    }
    changed = {**snapshot, "defaults": {"sheet_notes": ["0.010 IN"]}}
    assert probe.cross_arm_signature(
        snapshot, source, digest
    ) != probe.cross_arm_signature(changed, source, digest)
    changed = {**snapshot, "view_modes": [json.dumps("draft")]}
    assert probe.cross_arm_signature(
        snapshot, source, digest
    ) != probe.cross_arm_signature(changed, source, digest)


def test_semantic_datum_strips_only_verified_native_annotation_labels():
    dimension = {
        "kind": "model_dimension",
        "components": [
            {
                "name": "Width",
                "qualified_name": "Width@Foot@pedestal.Part",
                "value_system": 0.024,
            }
        ],
    }

    def row(view, annotation):
        return {
            "kind": "datum_to_model_display_dimension",
            "owner_view": view,
            "target_annotation": annotation,
            "source": {"path": "C:/same/pedestal.SLDPRT", "configuration": "Default"},
            "dimension": dimension,
            "datum": {"label": "A", "shoulder": True, "display_style": 2},
        }

    first = row("Sheet1/View1", "DetailItem20")
    second = row("Sheet1/View98", "DetailItem204")
    assert probe.semantic_attachment(
        first,
        {"dimensions": {"Sheet1/View1/DetailItem20/4": dimension}},
        "Sheet1/View1",
    ) == probe.semantic_attachment(
        second,
        {"dimensions": {"Sheet1/View98/DetailItem204/4": dimension}},
        "Sheet1/View98",
    )
    with pytest.raises(RuntimeError, match="target"):
        probe.semantic_attachment(first, {"dimensions": {}}, "Sheet1/View1")


def test_finished_semantics_exclude_raw_drawing_filename_observations(monkeypatch):
    @dataclass
    class Bounds:
        name: str
        format_signature: tuple = ("Century Gothic", 0.0035)

    def snapshot_for(annotation_name, drawing_name):
        view_key = "Sheet1/unique-view-" + drawing_name
        key = f"{view_key}/{annotation_name}/4"
        dimension = {
            "kind": "drawing_reference",
            "components": [
                {
                    "name": "RD1",
                    "qualified_name": "RD1@Drawing View1@<drawing>",
                    "value_system": 0.127,
                }
            ],
        }
        geometry = {
            "models": {
                view_key: {
                    "path": str(Path("C:/same/marker.SLDPRT")),
                    "configuration": "Default",
                }
            },
            "checked": {},
            "excluded": {key: {"reason": "no model-geometry attachments", "kinds": []}},
            "dimensions": {key: dimension},
            "dimensions_excluded": {},
            "semantic_attachments": {},
            "dimension_observations": {
                key: [{"full_name": f"RD1@Drawing View1@{drawing_name}.Drawing"}]
            },
        }
        annotation = SimpleNamespace(
            GetType=lambda: 4, GetName=lambda: annotation_name, Visible=1
        )
        view = SimpleNamespace(
            GetAnnotations=lambda: [annotation],
            GetOrientationName=lambda: "*Front",
            Position=(0.1, 0.2),
            ScaleDecimal=2.0,
            Angle=0.0,
            GetDisplayMode2=lambda: 2,
            GetFacettedHlrDisplay=lambda: False,
            GetCThreadQuality=lambda: True,
            GetDisplayTangentEdges2=lambda: 0,
            GetUseParentDisplayMode=lambda: False,
            GetDisplayEdgesInShadedMode=lambda: False,
        )
        monkeypatch.setattr(
            probe.attachments, "snapshot", lambda *args, **kwargs: geometry
        )
        monkeypatch.setattr(probe.attachments, "views", lambda model: {view_key: view})
        return probe.finished_snapshot(
            SimpleNamespace(currentModel=object(), swApp=object()),
            probe.TemplateSpec((2, 1), 2),
        )

    monkeypatch.setattr(probe, "_early_bound", lambda raw, kind: raw)
    monkeypatch.setattr(probe.attachments, "layout", lambda model: {})
    monkeypatch.setattr(probe, "defaults_snapshot", lambda *args: {})
    monkeypatch.setattr(
        probe,
        "annotation_box",
        lambda adapter, annotation: Bounds(annotation.GetName()),
    )
    first = snapshot_for("DetailItem1", "baseline-owned")
    second = snapshot_for("DetailItem99", "candidate-owned")
    assert first["native_annotations"] != second["native_annotations"]
    assert first["attachments"] != second["attachments"]
    source = Path("C:/same/marker.SLDPRT")
    assert probe.cross_arm_signature(
        first, source, "a" * 64
    ) == probe.cross_arm_signature(second, source, "a" * 64)
    assert "baseline-owned" not in json.dumps(first["semantic_annotations"])


def test_runtime_fingerprints_include_diagnostic_imports(monkeypatch, tmp_path):
    diagnostic = tmp_path / "cad/scripts/diagnostics"
    diagnostic.mkdir(parents=True)
    files = [
        diagnostic / name
        for name in (
            "benchmark_template_defaults.py",
            "_owned_native_documents.py",
            "probe_drawing_attachments.py",
        )
    ]
    for path in files:
        path.write_text("# unique test source\n", encoding="utf-8")
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe, "__file__", str(files[0]))
    monkeypatch.setattr(
        probe.recipes, "helper_fingerprints", lambda: {"base": "digest"}
    )
    result = probe.runtime_fingerprints()
    assert all(str(path.relative_to(tmp_path)) in result for path in files)


@pytest.fixture
def orchestration(monkeypatch, tmp_path):
    """Native behavior is replaced, but the real ABBA/checkpoint loop runs."""
    source = (
        tmp_path / f"{probe.DRAWINGS_BY_NAME['arbor_pedestal'].artifact_stem}.SLDPRT"
    )
    source.write_bytes(b"owned fixture source")
    original = tmp_path / "project.DRWDOT"
    original.write_bytes(b"owned fixture template")
    calls, cleanup_calls, preparations = [], [], []
    failure = {}
    roots, registered_sources, loaded_sources = [], [], []
    ownership = SimpleNamespace(
        register_directory=lambda path: roots.append(path),
        register_source=lambda path: registered_sources.append(Path(path)),
    )

    async def cleanup():
        cleanup_calls.append(len(calls))
        if failure.get("cleanup"):
            raise RuntimeError("cleanup evidence")
        if failure.get("between_trials") and len(calls) == 1:
            source.write_bytes(b"source replaced after first trial")
        if failure.get("copy_between_trials") and len(calls) == 1:
            loaded_sources[0].write_bytes(b"copy changed; must not reset")
        if failure.get("previous_output") and len(calls) == 2:
            loaded_sources[0].write_bytes(b"previous saved output changed")

    adapter = SimpleNamespace(ownership=ownership, close_owned_documents=cleanup)

    def load(commit, target, directory, owned_source):
        (directory / "recipe-source.py").write_text("# fixed recipe", encoding="utf-8")
        loaded_sources.append(owned_source)
        return SimpleNamespace(SOURCE=owned_source), probe.TemplateSpec((2, 1), 2)

    async def prepare(adapter, spec, directory, row):
        preparations.append(spec)
        path = directory / "derived.DRWDOT"
        path.write_bytes(b"owned derived template")
        row.update(
            path=str(path), sha256=probe.attachments.file_digest(path), seconds=1
        )
        if failure.get("prepare"):
            row.update(status="failed", error="preparation evidence")
            raise RuntimeError("preparation evidence")
        row["status"] = "passed"
        return row

    async def trial(adapter, module, spec, variant, template, row):
        calls.append(variant)
        # Checkpoint is already on disk before any trial-side native call.
        checkpoint = json.loads((roots[0] / "measurements.json").read_text())
        assert checkpoint["trials"][-1]["status"] == "running"
        row.update(setup_seconds=[0.5], recipe_seconds=10, validation_seconds=2)
        assert module.SOURCE.read_bytes() == b"owned fixture source"
        if failure.get("trial"):
            raise RuntimeError("recipe evidence")
        if failure.get("presentation_output"):
            module.SOURCE.write_bytes(b"retained saved presentation")
        row["source_output_sha256"] = probe.attachments.file_digest(module.SOURCE)
        row["source_snapshots"] = {
            "initial": {"value": 1},
            "cold_reopened": {"value": 1},
        }
        row["reopened"] = {
            "defaults": {"notes": ["0.25 MM"]},
            "view_modes": [json.dumps("precise")],
            "semantic_annotations": [json.dumps("unchanged")],
        }
        if failure.get("semantic") and variant == "candidate":
            row["reopened"]["semantic_annotations"] = [json.dumps("dimension missing")]
        if failure.get("source_semantic") and variant == "candidate":
            row["source_snapshots"]["cold_reopened"] = {"value": 2}

    monkeypatch.setattr(probe.common, "PROJECT_DRWDOT", original)
    monkeypatch.setattr(probe, "runtime_fingerprints", lambda: {"input": "unchanged"})
    monkeypatch.setattr(probe.recipes, "revision", lambda revision: "frozen-head")
    monkeypatch.setattr(probe, "load_recipe", load)
    monkeypatch.setattr(probe, "prepare_template", prepare)
    monkeypatch.setattr(probe, "run_trial", trial)

    def run():
        return asyncio.run(
            probe.benchmark(
                adapter,
                ["arbor_pedestal"],
                "recipe-head",
                tmp_path,
                tmp_path / "reports",
            )
        )

    return SimpleNamespace(
        run=run,
        report=lambda: json.loads((roots[0] / "measurements.json").read_text()),
        calls=calls,
        cleanup_calls=cleanup_calls,
        preparations=preparations,
        failure=failure,
        source=source,
        loaded_sources=loaded_sources,
        registered_sources=registered_sources,
    )


def test_abba_prepares_once_and_checkpoints_all_four_trials(orchestration):
    orchestration.run()
    assert orchestration.calls == list(probe.ORDER)
    assert len(orchestration.preparations) == 1
    assert orchestration.cleanup_calls == [1, 2, 3, 4]
    report = orchestration.report()
    assert report["status"] == "passed"
    assert all(row["status"] == "passed" for row in report["trials"])
    assert report["immutable_input_changes"] == {}
    assert report["derived_template_changes"] == {}
    assert len({row["source_sha256"] for row in report["trials"]}) == 1
    assert len(set(orchestration.loaded_sources)) == 4
    assert len({path.name for path in orchestration.loaded_sources}) == 1
    for owned in orchestration.loaded_sources:
        assert owned != orchestration.source
        assert owned.name != orchestration.source.name
        assert owned not in orchestration.registered_sources
        assert owned.read_bytes() == orchestration.source.read_bytes()
    assert orchestration.source in orchestration.registered_sources
    assert all(
        row["ownership"] == "owned_copy" for row in report["owned_sources"].values()
    )


def test_each_arm_starts_from_original_not_previous_saved_output(orchestration):
    orchestration.failure["presentation_output"] = True
    orchestration.run()
    assert len(orchestration.calls) == 4
    assert all(
        path.read_bytes() == b"retained saved presentation"
        for path in orchestration.loaded_sources
    )
    assert orchestration.source.read_bytes() == b"owned fixture source"
    for row in orchestration.report()["trials"]:
        assert row["source_output_sha256"] != row["source_sha256"]
        assert row["retained_source_sha256"] == row["source_output_sha256"]


def test_saved_output_change_during_cleanup_stops_without_reset(orchestration):
    orchestration.failure["copy_between_trials"] = True
    with pytest.raises(RuntimeError, match="retained source outputs changed"):
        orchestration.run()
    assert orchestration.calls == ["baseline"]
    copied = orchestration.loaded_sources[0]
    assert copied.read_bytes() == b"copy changed; must not reset"
    assert orchestration.source.read_bytes() == b"owned fixture source"
    assert orchestration.report()["immutable_input_changes"] == {}
    assert orchestration.report()["trials"][0]["status"] == "failed"
    assert (
        "saved source output changed during cleanup"
        in orchestration.report()["trials"][0]["retained_source_error"]
    )


def test_later_arm_cannot_silently_change_previous_retained_part(orchestration):
    orchestration.failure["previous_output"] = True
    with pytest.raises(RuntimeError, match="retained source outputs changed"):
        orchestration.run()
    report = orchestration.report()
    assert orchestration.calls == ["baseline", "candidate"]
    assert report["status"] == "failed"
    assert list(report["retained_source_changes"]) == [
        str(orchestration.loaded_sources[0])
    ]


@pytest.mark.parametrize(
    "changed", ["path", "configuration", "native_identity", "unresolved"]
)
def test_every_model_view_requires_exact_copy_and_configuration(
    monkeypatch, tmp_path, changed
):
    source = tmp_path / "unique-owned.SLDPRT"
    source.write_bytes(b"copy")
    native, foreign = object(), object()
    view = SimpleNamespace(ReferencedDocument=native)
    reference = {"path": str(source), "configuration": "Default"}
    adapter = SimpleNamespace(
        currentModel=object(),
        swApp=SimpleNamespace(
            GetOpenDocumentByName=lambda path: native,
            IsSame=lambda first, second: int(first is second),
        ),
    )
    monkeypatch.setattr(
        probe.attachments, "views", lambda model: {"front": view, "top": view}
    )
    monkeypatch.setattr(probe.attachments, "referenced_model", lambda view: reference)
    probe.exact_source_views(adapter, source, "Default")
    if changed == "path":
        reference["path"] = str(tmp_path / "original.SLDPRT")
    if changed == "configuration":
        reference["configuration"] = "Other"
    if changed == "native_identity":
        view.ReferencedDocument = foreign
    if changed == "unresolved":
        view.ReferencedDocument = None
    with pytest.raises(RuntimeError, match="exact copied source/config"):
        probe.exact_source_views(adapter, source, "Default")


def test_native_source_observation_records_dirty_but_rejects_replacement(
    monkeypatch, tmp_path
):
    path = tmp_path / "copy.SLDPRT"
    configuration = SimpleNamespace(Name="Default")
    model = SimpleNamespace(
        GetPathName=lambda: str(path),
        GetType=lambda: 1,
        GetSaveFlag=lambda: True,
        Visible=True,
        ConfigurationManager=SimpleNamespace(ActiveConfiguration=configuration),
    )
    app = SimpleNamespace(
        GetOpenDocumentByName=lambda name: model,
        IsSame=lambda first, second: int(first is second),
    )
    monkeypatch.setattr(probe, "_early_bound", lambda value, interface: value)
    observation, handle = probe.source_observation(
        SimpleNamespace(swApp=app), path, model
    )
    assert handle is model
    assert observation["dirty"] == "dirty"
    assert observation["identity"] == "same_native_document"
    with pytest.raises(RuntimeError, match="native identity changed"):
        probe.source_observation(SimpleNamespace(swApp=app), path, object())


@pytest.mark.parametrize("lost", ["callout_text", "basic", "precision"])
def test_cold_source_reopen_never_waives_display_or_tolerance_loss(lost):
    geometry = {
        key: {}
        for key in (
            "checked",
            "excluded",
            "models",
            "dimensions",
            "dimensions_excluded",
            "semantic_attachments",
        )
    }
    geometry["dimensions"] = {
        "view/BoreDia/4": {"value_system": 0.009525, "tolerance_type": 1}
    }
    before = {
        "attachments": geometry,
        "layout": {},
        "defaults": {},
        "view_modes": [],
        "native_annotations": {"view/BoreDia/4": {"text": "THRU", "precision": 3}},
    }
    after = deepcopy(before)
    if lost == "callout_text":
        after["native_annotations"]["view/BoreDia/4"]["text"] = ""
    if lost == "basic":
        after["attachments"]["dimensions"]["view/BoreDia/4"]["tolerance_type"] = 0
    if lost == "precision":
        after["native_annotations"]["view/BoreDia/4"]["precision"] = 2
    with pytest.raises(RuntimeError, match="reopen"):
        probe.compare_reopened(before, after)


def test_between_trial_replacement_does_not_become_the_next_baseline(orchestration):
    orchestration.failure["between_trials"] = True
    with pytest.raises(RuntimeError, match="immutable benchmark inputs changed"):
        orchestration.run()
    assert orchestration.calls == ["baseline"]
    report = orchestration.report()
    assert report["status"] == "failed"
    assert "between trials" in report["error"]
    change = report["immutable_input_changes"][str(orchestration.source)]
    assert change["expected"] == report["trials"][0]["source_sha256"]
    assert change["actual"] != change["expected"]


def test_failed_trial_and_failed_cleanup_both_survive_in_report(orchestration):
    orchestration.failure.update(trial=True, cleanup=True)
    with pytest.raises(RuntimeError, match="cleanup evidence"):
        orchestration.run()
    report = orchestration.report()
    assert report["status"] == "failed"
    row = report["trials"][0]
    assert row["error"] == "recipe evidence"
    assert "cleanup evidence" in row["cleanup_error"]
    assert row["recipe_seconds"] == 10
    assert report["immutable_input_changes"] == {}


def test_preparation_failure_is_retained_before_any_recipe(orchestration):
    orchestration.failure["prepare"] = True
    with pytest.raises(RuntimeError, match="preparation evidence"):
        orchestration.run()
    report = orchestration.report()
    assert report["template_preparations"][0]["error"] == "preparation evidence"
    assert report["trials"] == []
    assert report["immutable_input_changes"] == {}


def test_cross_arm_mismatch_stops_after_first_candidate(orchestration):
    orchestration.failure["semantic"] = True
    with pytest.raises(RuntimeError, match="cross-arm"):
        orchestration.run()
    assert orchestration.calls == ["baseline", "candidate"]
    assert orchestration.report()["trials"][1]["status"] == "failed"


def test_source_presentation_output_is_compared_across_arms(orchestration):
    orchestration.failure["source_semantic"] = True
    with pytest.raises(RuntimeError, match="cross-arm"):
        orchestration.run()
    assert orchestration.calls == ["baseline", "candidate"]


def test_final_hash_read_error_is_evidence_not_a_lost_checkpoint(monkeypatch, tmp_path):
    source = tmp_path / "owned.SLDPRT"
    source.write_bytes(b"fixture")

    def denied(path):
        raise PermissionError("native file is not readable")

    monkeypatch.setattr(probe.attachments, "file_digest", denied)
    changed = probe.immutable_changes({str(source): "pinned"})
    assert changed[str(source)]["expected"] == "pinned"
    assert "not readable" in changed[str(source)]["error"]


def source_witness(source, text=""):
    return {
        "configuration": "Default",
        "features": ["BoreProfile"],
        "dimensions": {
            f"BoreDia@BoreProfile@{source.stem}.Part": {
                "native": {
                    "value_system": 0.009525,
                    "tolerance_type": 1,
                    "designation": "basic",
                    "tolerance_min": 0.0,
                    "tolerance_max": 0.0,
                },
                "displays": [
                    {
                        "feature": "BoreProfile",
                        "dimension_type": 6,
                        "index": 0,
                        "marked_for_drawing": True,
                        "primary_precision": 2,
                        "tolerance_precision": 2,
                        "text": {"4": text, "8": text},
                    }
                ],
            }
        },
    }


def test_source_witness_records_only_permitted_presentation_changes(tmp_path):
    from diagnostics._source_dimension_snapshot import compare_source

    source = tmp_path / "owned.SLDPRT"
    before, after = source_witness(source), source_witness(source, "THRU")
    dimension = next(iter(after["dimensions"].values()))
    dimension["displays"][0]["primary_precision"] = 3
    handle = object()
    handles = {name: handle for name in before["dimensions"]}
    changes = compare_source(
        before,
        after,
        app=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
        handles_before=handles,
        handles_after=handles,
    )
    assert list(changes) == list(before["dimensions"])
    name = next(iter(changes))
    assert changes[name]["before"][0]["text"]["4"] == ""
    assert changes[name]["after"][0]["text"]["4"] == "THRU"
    assert changes[name]["after"][0]["primary_precision"] == 3


@pytest.mark.parametrize(
    "changed",
    [
        "value_system",
        "tolerance_type",
        "designation",
        "tolerance_min",
        "tolerance_max",
        "native_identity",
        "configuration",
        "feature",
        "dimension_name",
        "display_missing",
        "dimension_type",
        "marked_for_drawing",
    ],
)
def test_source_witness_rejects_numeric_basic_identity_and_inventory_drift(
    tmp_path, changed
):
    from diagnostics._source_dimension_snapshot import compare_source

    before = source_witness(tmp_path / "owned.SLDPRT")
    after = deepcopy(before)
    name = next(iter(before["dimensions"]))
    row = after["dimensions"][name]
    first, second = object(), object()
    handles = {name: first}
    if changed in row["native"]:
        row["native"][changed] = "not_basic" if changed == "designation" else 7
    if changed == "configuration":
        after["configuration"] = "Wrong"
    if changed == "feature":
        after["features"].append("AddedFeature")
    if changed == "dimension_name":
        after["dimensions"]["Other@BoreProfile@owned.Part"] = after["dimensions"].pop(
            name
        )
    if changed == "display_missing":
        row["displays"] = []
    if changed == "dimension_type":
        row["displays"][0]["dimension_type"] = 2
    if changed == "marked_for_drawing":
        row["displays"][0]["marked_for_drawing"] = False
    with pytest.raises(RuntimeError, match="source"):
        compare_source(
            before,
            after,
            app=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
            handles_before=handles,
            handles_after={name: second} if changed == "native_identity" else handles,
        )


def test_cross_arm_normalizes_only_verified_source_owners(tmp_path):
    first = tmp_path / "arm0" / "same-owned.SLDPRT"
    second = tmp_path / "arm1" / first.name

    def snapshot(source):
        reference = {"path": str(source), "configuration": "Default"}
        dimension = {
            "kind": "model_dimension",
            "components": [
                {
                    "name": "BoreDia",
                    "qualified_name": f"BoreDia@BoreProfile@{source.stem}.Part",
                    "value_system": 0.009525,
                    "tolerance_type": 1,
                    "designation": "basic",
                }
            ],
        }
        return {
            "defaults": {"sheet_notes": ["same printed filename"]},
            "view_modes": probe.semantic_multiset([{"source": reference}]),
            "semantic_annotations": probe.semantic_multiset(
                [
                    {
                        "view": {"source": reference},
                        "dimensions": dimension,
                        "checked": [
                            {
                                "kind": "circle",
                                "center": [0.0, 0.0, 0.0],
                                "radius": 0.0047625,
                            }
                        ],
                    }
                ]
            ),
        }

    a, b = snapshot(first), snapshot(second)
    assert a != b
    assert probe.cross_arm_signature(a, first, "a" * 64) == probe.cross_arm_signature(
        b, second, "a" * 64
    )
    assert probe.cross_arm_signature(a, first, "a" * 64) != probe.cross_arm_signature(
        a, first, "b" * 64
    )
    for wrong in ("view_path", "dimension_owner", "configuration_empty"):
        changed = deepcopy(b)
        row = json.loads(changed["semantic_annotations"][0])
        if wrong == "view_path":
            row["view"]["source"]["path"] = str(first)
        if wrong == "dimension_owner":
            row["dimensions"]["components"][0]["qualified_name"] = (
                "BoreDia@BoreProfile@original.Part"
            )
        if wrong == "configuration_empty":
            row["view"]["source"]["configuration"] = ""
        changed["semantic_annotations"] = probe.semantic_multiset([row])
        with pytest.raises(RuntimeError, match="unproved copied-source owner"):
            probe.cross_arm_signature(changed, second, "a" * 64)
    changed = deepcopy(b)
    row = json.loads(changed["semantic_annotations"][0])
    row["checked"][0]["radius"] += 0.001
    changed["semantic_annotations"] = probe.semantic_multiset([row])
    assert probe.cross_arm_signature(a, first, "a" * 64) != probe.cross_arm_signature(
        changed, second, "a" * 64
    )


@pytest.mark.parametrize(
    "output_change", ["unchanged", "presentation", "value", "cold_text_loss"]
)
def test_trial_claims_creation_then_scopes_exact_save_and_restores_hooks(
    monkeypatch, tmp_path, output_change
):
    events = []
    outputs = probe.common.DrawingOutputs(
        tmp_path / "owned.SLDDRW", tmp_path / "owned.pdf", tmp_path / "owned.png"
    )

    @contextmanager
    def creating(kind, path):
        assert path == outputs.slddrw
        events.append("create_enter")
        yield
        events.append("create_exit")

    @contextmanager
    def saving(path):
        assert path == outputs.slddrw
        assert events[-1] == "create_exit"
        events.append("save_enter")
        yield
        events.append("save_exit")

    async def finalize(adapter, actual_outputs):
        assert events[-1] == "save_enter"
        assert actual_outputs == outputs
        events.append("native_save")
        if output_change != "unchanged":
            source.write_bytes(b"saved reference presentation")
        return ["native", "pdf", "png"]

    async def close_owned_documents():
        events.append("close_all_owned")

    async def open_model(path):
        assert Path(path) == outputs.slddrw
        events.append("reopen")
        return SimpleNamespace(success=True)

    source = tmp_path / "owned-source.SLDPRT"
    source.write_bytes(b"copy bytes")
    module = SimpleNamespace(OUTPUTS=outputs, finalize_drawing=finalize, SOURCE=source)
    model = SimpleNamespace(GetPathName=lambda: str(outputs.slddrw))
    adapter = SimpleNamespace(
        ownership=SimpleNamespace(creating_document=creating, saving_as=saving),
        currentModel=model,
        close_owned_documents=close_owned_documents,
        open_model=open_model,
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )

    def setup(current, **kwargs):
        assert current is adapter
        assert events[-1] == "create_enter"
        assert kwargs == {"scale": (2, 1)}
        return model, object()

    async def build(current):
        module.new_project_drawing(current, scale=(2, 1))
        return await module.finalize_drawing(current, outputs)

    module.new_project_drawing, module.build = setup, build
    monkeypatch.setattr(probe.common, "new_project_drawing", setup)
    monkeypatch.setattr(probe, "_early_bound", lambda raw, kind: raw)
    monkeypatch.setattr(probe, "check", lambda label, result: None)
    monkeypatch.setattr(probe, "finished_snapshot", lambda *args: {"fresh": "witness"})
    monkeypatch.setattr(probe, "exact_source_views", lambda *args: None)
    observed_handles = []

    def source_state(adapter, path, previous):
        observed_handles.append(previous)
        return {
            "configuration": "Default",
            "dirty": "dirty" if events and "native_save" not in events else "clean",
        }, model

    dimension_handle, reopened_handle = object(), object()
    snapshots_taken = []

    def snapshot(app, native, path, *, required):
        assert native is model and path == source
        assert required == probe.SOURCE_DIMENSIONS["arbor_pedestal"]
        text = "THRU" if events and output_change != "unchanged" else ""
        if "reopen" in events and output_change == "cold_text_loss":
            text = ""
        result = source_witness(source, text)
        if events and output_change == "value":
            next(iter(result["dimensions"].values()))["native"]["value_system"] += 0.001
        snapshots_taken.append(deepcopy(result))
        handle = reopened_handle if "reopen" in events else dimension_handle
        return result, {name: handle for name in result["dimensions"]}

    monkeypatch.setattr(probe, "dimension_snapshot", snapshot)
    monkeypatch.setattr(probe, "source_observation", source_state)
    monkeypatch.setattr(
        probe, "compare_reopened", lambda before, after: events.append("compare")
    )
    monkeypatch.setattr(
        probe.recipes, "validate_artifacts", lambda artifacts, outputs: artifacts
    )
    row = {
        "target": "arbor_pedestal",
        "source_sha256": probe.attachments.file_digest(source),
    }

    def run():
        return asyncio.run(
            probe.run_trial(
                adapter, module, probe.TemplateSpec((2, 1), 2), "baseline", {}, row
            )
        )

    if output_change == "value":
        with pytest.raises(RuntimeError, match="source value/tolerance/BASIC changed"):
            run()
        assert "value/tolerance/BASIC" in row["recipe_error"]
        assert source.read_bytes() == b"copy bytes"
        assert "native_save" not in events
        assert "reopen" not in events
        assert module.finalize_drawing is finalize
        return
    if output_change == "cold_text_loss":
        with pytest.raises(RuntimeError, match="cold source presentation/semantics"):
            run()
        assert source.read_bytes() == b"saved reference presentation"
        assert "reopen" in events
        assert "compare" not in events
        return
    run()
    assert events == [
        "create_enter",
        "create_exit",
        "save_enter",
        "native_save",
        "save_exit",
        "close_all_owned",
        "reopen",
        "compare",
        "close_all_owned",
    ]
    assert module.new_project_drawing is setup
    assert module.finalize_drawing is finalize
    assert len(row["setup_seconds"]) == 1
    assert row["validation_seconds"] >= 0
    assert set(row["owned_source_native"]) == {
        "recipe_source_open",
        "after_initial_snapshot",
        "before_drawing_save",
        "after_drawing_save",
        "after_recipe",
        "cold_source_reopen",
        "after_persisted_checks",
    }
    # New source after cold close must not be compared with a stale COM handle.
    assert observed_handles == [None, model, model, model, model, None, model]
    assert row["owned_source_native"]["before_drawing_save"]["dirty"] == "dirty"
    assert len(snapshots_taken) == 4
    assert row["recipe_elapsed_seconds"] == pytest.approx(
        row["recipe_seconds"] + row["recipe_excluded_source_snapshot_seconds"]
    )
    assert row["recipe_excluded_source_snapshot_seconds"] == pytest.approx(
        row["source_snapshot_seconds"]["initial"]
        + row["source_snapshot_seconds"]["before_drawing_save"]
    )
    if output_change == "presentation":
        assert row["source_output_sha256"] != row["source_sha256"]
        assert row["source_presentation_changes"]["cold_reopened"]
        assert source.read_bytes() == b"saved reference presentation"
