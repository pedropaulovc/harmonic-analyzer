"""COM-free contracts for the inherited drawing-template ABBA control."""

import asyncio
from contextlib import contextmanager
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
        module, spec = probe.load_recipe(commit, target, trial, tmp_path)
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
    snapshot = {
        "defaults": {"sheet_notes": ["0.25 MM"]},
        "view_modes": ["precise"],
        "semantic_annotations": [],
    }
    changed = {**snapshot, "defaults": {"sheet_notes": ["0.010 IN"]}}
    assert probe.cross_arm_signature(snapshot) != probe.cross_arm_signature(changed)
    changed = {**snapshot, "view_modes": ["draft"]}
    assert probe.cross_arm_signature(snapshot) != probe.cross_arm_signature(changed)


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
                view_key: {"path": "C:/same/marker.SLDPRT", "configuration": "Default"}
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
    assert probe.cross_arm_signature(first) == probe.cross_arm_signature(second)
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
    roots = []
    ownership = SimpleNamespace(
        register_directory=lambda path: roots.append(path),
        register_source=lambda path: None,
    )

    async def cleanup():
        cleanup_calls.append(len(calls))
        if failure.get("cleanup"):
            raise RuntimeError("cleanup evidence")
        if failure.get("between_trials") and len(calls) == 1:
            source.write_bytes(b"source replaced after first trial")

    adapter = SimpleNamespace(ownership=ownership, close_owned_documents=cleanup)

    def load(commit, target, directory, source_root):
        (directory / "recipe-source.py").write_text("# fixed recipe", encoding="utf-8")
        return SimpleNamespace(SOURCE=source), probe.TemplateSpec((2, 1), 2)

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
        if failure.get("trial"):
            raise RuntimeError("recipe evidence")
        row["reopened"] = {
            "defaults": {"notes": ["0.25 MM"]},
            "view_modes": ["precise"],
            "semantic_annotations": ["unchanged"],
        }
        if failure.get("semantic") and variant == "candidate":
            row["reopened"]["semantic_annotations"] = ["dimension missing"]

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


def test_final_hash_read_error_is_evidence_not_a_lost_checkpoint(monkeypatch, tmp_path):
    source = tmp_path / "owned.SLDPRT"
    source.write_bytes(b"fixture")

    def denied(path):
        raise PermissionError("native file is not readable")

    monkeypatch.setattr(probe.attachments, "file_digest", denied)
    changed = probe.immutable_changes({str(source): "pinned"})
    assert changed[str(source)]["expected"] == "pinned"
    assert "not readable" in changed[str(source)]["error"]


def test_trial_claims_creation_then_scopes_exact_save_and_restores_hooks(
    monkeypatch, tmp_path
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
        return ["native", "pdf", "png"]

    async def close_model(*, save):
        assert save is False
        events.append("close")
        return SimpleNamespace(success=True)

    async def open_model(path):
        assert Path(path) == outputs.slddrw
        events.append("reopen")
        return SimpleNamespace(success=True)

    module = SimpleNamespace(OUTPUTS=outputs, finalize_drawing=finalize)
    model = SimpleNamespace(GetPathName=lambda: str(outputs.slddrw))
    adapter = SimpleNamespace(
        ownership=SimpleNamespace(creating_document=creating, saving_as=saving),
        currentModel=model,
        close_model=close_model,
        open_model=open_model,
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
    monkeypatch.setattr(
        probe, "compare_reopened", lambda before, after: events.append("compare")
    )
    monkeypatch.setattr(
        probe.recipes, "validate_artifacts", lambda artifacts, outputs: artifacts
    )
    row = {}
    asyncio.run(
        probe.run_trial(
            adapter, module, probe.TemplateSpec((2, 1), 2), "baseline", {}, row
        )
    )
    assert events == [
        "create_enter",
        "create_exit",
        "save_enter",
        "native_save",
        "save_exit",
        "close",
        "reopen",
        "compare",
        "close",
    ]
    assert module.new_project_drawing is setup
    assert module.finalize_drawing is finalize
    assert len(row["setup_seconds"]) == 1
    assert row["validation_seconds"] >= 0
