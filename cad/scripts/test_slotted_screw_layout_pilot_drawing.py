"""Synthetic sheet data tests; no claimed native slotted source identities."""

from copy import deepcopy
import asyncio
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _slotted_screw_layout_witness as witness


def rectangle(xmin=0.05, ymin=0.10, xmax=0.08, ymax=0.15):
    return dict(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)


@pytest.mark.parametrize(
    "actual",
    [
        "FIRST\rSECOND",
        "FIRST\r\r\nSECOND",
        "FIRST\tSECOND",
        "FIRST\vSECOND",
        "FIRST\x00\nSECOND",
        "FIRST\x85SECOND",
        "FIRST\u2028SECOND",
        "FIRST\nCHANGED",
        "FIRST\nSECON",
        "FIRST\nSECOND\n",
        "FIRST\n SECOND",
        " FIRST\nSECOND",
        None,
        1,
        b"FIRST\nSECOND",
    ],
)
def test_native_spec_text_rejects_every_nonserialization_change(actual):
    with pytest.raises(RuntimeError, match="exact text differs"):
        witness._require_spec_text(actual, "FIRST\nSECOND", "exact text differs")


@pytest.fixture
def scene():
    # These arbitrary keys/values are synthetic. Native types/IDs come only from
    # the separately reviewed acceptance manifest, never from this fixture.
    dimensions, annotations = {}, {}
    for key, orientation in witness.DIMENSION_VIEWS.items():
        annotation_key = f"{orientation}/{key}"
        dimensions[key] = {
            "annotation_key": annotation_key,
            "orientation": orientation,
            "presentation": {"show_dimension_value": True},
            "native_text_values": [" 2.50 "],
        }
        annotations[annotation_key] = {
            "semantic": {"owner_type": 0, "kind": 4, "visible": 1, "dangling": False},
            "measurement": {
                "envelope": rectangle(),
                "body": rectangle(),
                "native_strokes": [
                    {"start": [0.06, 0.1], "end": [0.06, 0.15], "width_m": 0.0}
                ],
            },
        }
    views = {
        orientation: {
            "orientation": orientation,
            "scale": [6.0, 1.0],
            "outline": [0.05, 0.1, 0.08, 0.15],
        }
        for orientation in witness.VIEWS
    }
    return {
        "model_dimensions": {"dimensions": dimensions},
        "annotations": annotations,
    }, views


def test_candidate_requires_entire_native_stroke_envelope_inside_border(scene):
    bank, views = scene
    result = witness.layout_geometry(bank, views, [0.01, 0.01, 0.42, 0.27])
    assert result["border_status"] == "inside"
    key = bank["model_dimensions"]["dimensions"]["HeadHt@Head"]["annotation_key"]
    bank["annotations"][key]["measurement"]["envelope"]["ymax"] = 0.271
    result = witness.layout_geometry(bank, views, [0.01, 0.01, 0.42, 0.27])
    assert result["border_status"] == "outside"
    assert result["head_height_top_clearance_m"] == pytest.approx(-0.001)
    witness.require_border(witness.LayoutObservation.BASELINE, result)
    with pytest.raises(RuntimeError, match="candidate.*border"):
        witness.require_border(witness.LayoutObservation.CANDIDATE, result)


@pytest.mark.parametrize(
    "damage",
    [
        "hidden",
        "dangling",
        "excluded",
        "missing",
        "extra",
        "numeric_hidden",
        "wrong_view",
        "wrong_scale",
        "nonfinite",
        "missing_strokes",
    ],
)
def test_geometry_rejects_incomplete_or_changed_contract(scene, damage):
    bank, views = scene
    key = bank["model_dimensions"]["dimensions"]["HeadHt@Head"]["annotation_key"]
    row = bank["annotations"][key]
    if damage == "hidden":
        row["semantic"]["visible"] = 3
    if damage == "dangling":
        row["semantic"]["dangling"] = True
    if damage == "excluded":
        row["measurement_exclusion"] = "unsupported"
    if damage == "missing":
        del bank["annotations"][key]
    if damage == "extra":
        bank["model_dimensions"]["dimensions"]["Extra@Sketch"] = deepcopy(
            bank["model_dimensions"]["dimensions"]["HeadHt@Head"]
        )
    if damage == "numeric_hidden":
        bank["model_dimensions"]["dimensions"]["HeadHt@Head"]["presentation"][
            "show_dimension_value"
        ] = False
    if damage == "wrong_view":
        bank["model_dimensions"]["dimensions"]["HeadHt@Head"]["orientation"] = "*Top"
    if damage == "wrong_scale":
        views["*Front"]["scale"] = [3.0, 1.0]
    if damage == "nonfinite":
        row["measurement"]["envelope"]["ymax"] = float("nan")
    if damage == "missing_strokes":
        row["measurement"]["native_strokes"] = []
    with pytest.raises(
        (RuntimeError, ValueError),
        match="contract|dimension|measurement|stroke|scale|finite",
    ):
        witness.layout_geometry(bank, views, [0.01, 0.01, 0.42, 0.27])


def test_no_existing_target_is_silently_opted_in():
    from diagnostics._recipe_acceptance_targets import TARGETS

    assert "slotted_screw" not in TARGETS  # Enrollment awaits real builder data.
    witness.require_selection(None, ("rocker_arm",), TARGETS)
    with pytest.raises(ValueError, match="slotted"):
        witness.require_selection(
            witness.LayoutObservation.CANDIDATE, ("rocker_arm",), TARGETS
        )
    with pytest.raises(ValueError, match="enrollment"):
        witness.require_selection(
            witness.LayoutObservation.CANDIDATE, ("slotted_screw",), TARGETS
        )


def synthetic_manifest():
    return NS(
        coverage=witness.SemanticCoverage.MODEL_DIMENSIONS_ONLY,
        dimensions=witness.spec.DRAWING_DIMENSIONS,
        basic={},
        entity_labels={},
        view_roles={},
        model_dimensions=tuple(
            NS(key=key, orientation=view)
            for key, view in witness.DIMENSION_VIEWS.items()
        ),
        model_views=witness.VIEWS,
    )


@pytest.fixture
def live_scene(scene, monkeypatch, tmp_path):
    from _drawing_common import DrawingOutputs

    bank, views = scene
    part_path, native_path = tmp_path / "owned-source.SLDPRT", tmp_path / "owned.SLDDRW"
    part_path.write_bytes(b"owned source")
    native_path.write_bytes(b"owned drawing")
    outputs = DrawingOutputs(
        native_path, tmp_path / "built.pdf", tmp_path / "built.png"
    )
    outputs.pdf.write_bytes(b"existing recipe PDF")
    part = NS(
        GetPathName=lambda: str(part_path), GetType=lambda: 1, GetSaveFlag=lambda: False
    )
    model = NS(
        GetPathName=lambda: str(native_path),
        GetType=lambda: 3,
        GetSaveFlag=lambda: True,
        Visible=True,
    )
    app = NS(
        ActiveDoc=model,
        IsSame=lambda a, b: int(a is b),
        GetOpenDocumentByName=lambda path: part if Path(path) == part_path else None,
    )
    adapter = NS(
        currentModel=model,
        swApp=app,
        ownership=NS(
            assert_current_owned=lambda: NS(paths={native_path}), directories={tmp_path}
        ),
    )
    monkeypatch.setattr(witness, "_early_bound", lambda value, _: value)
    sheet = {
        "geometry": witness.layout_geometry(bank, views, [0.01, 0.01, 0.42, 0.27]),
        "source_notes": {},
        "notes": {},
        "sheet_properties": [0, 0, 6.0, 1.0, 0, 0.432, 0.279, 0],
        "zone_margins_m": [0.01] * 4,
    }
    return NS(
        adapter=adapter,
        model=model,
        part=part,
        source=part_path,
        outputs=outputs,
        bank=bank,
        views=views,
        handles={},
        sheet=sheet,
    )


@pytest.mark.parametrize(
    "damage",
    ["hidden", "wrong_active", "wrong_kind", "wrong_path", "wrong_source", "unowned"],
)
def test_actual_capture_rejects_context_before_sheet_or_export(
    live_scene, monkeypatch, damage
):
    c = live_scene
    if damage == "hidden":
        c.model.Visible = False
    if damage == "wrong_active":
        c.adapter.swApp.ActiveDoc = object()
    if damage == "wrong_kind":
        c.model.GetType = lambda: 1
    if damage == "wrong_path":
        c.model.GetPathName = lambda: "another.SLDDRW"
    if damage == "wrong_source":
        c.part.GetPathName = lambda: "another.SLDPRT"
    if damage == "unowned":
        c.adapter.ownership.assert_current_owned = Mock(
            side_effect=RuntimeError("not owned")
        )
    sheet = Mock(side_effect=AssertionError("no native measurements permitted"))
    export = Mock(side_effect=AssertionError("no export permitted"))
    monkeypatch.setattr(witness, "sheet_witness", sheet)
    from diagnostics import probe_retained_drawing_export as printed

    monkeypatch.setattr(printed, "export_pdf_only", export)
    record, checkpoint = {}, Mock()
    with pytest.raises(RuntimeError, match="owned|identity|copied PART"):
        witness.capture(
            c.adapter,
            phase=witness.CapturePhase.REOPENED,
            bank=c.bank,
            handles=c.handles,
            source=c.source,
            outputs=c.outputs,
            record=record,
            checkpoint=checkpoint,
        )
    assert record["reopened"]["status"] == "failed"
    assert len(record["reopened"]["hashes_after"]) == 2
    sheet.assert_not_called()
    export.assert_not_called()
    checkpoint.assert_called_once()


@pytest.mark.parametrize("phase", tuple(witness.CapturePhase))
@pytest.mark.parametrize(
    "failure",
    ["none", "export", "render", "cancel", "keyboard", "dirty", "hash", "checkpoint"],
)
def test_capture_retains_primary_and_all_guard_evidence(
    live_scene, monkeypatch, phase, failure
):
    from diagnostics import probe_retained_drawing_export as printed

    c = live_scene
    primary = RuntimeError("original PDF failure")
    if failure == "cancel":
        primary = asyncio.CancelledError("interrupted render")
    if failure == "keyboard":
        primary = KeyboardInterrupt("interrupted render")
    monkeypatch.setattr(witness, "sheet_witness", lambda *_: c.sheet)
    calls = []

    def export(adapter, path):
        calls.append(path)
        assert adapter is c.adapter and path.name == "slotted-cold.pdf"
        if failure == "export":
            c.part.GetSaveFlag = lambda: True
            raise primary
        path.write_bytes(b"cold PDF")

    def read(pdf, png):
        if failure in ("render", "cancel", "keyboard"):
            c.part.GetSaveFlag = lambda: True
            raise primary
        if failure == "dirty":
            c.part.GetSaveFlag = lambda: True
        if failure == "hash":
            c.source.write_bytes(b"changed copy")
        assert pdf.name == (
            "built.pdf" if phase is witness.CapturePhase.BUILT else "slotted-cold.pdf"
        )
        assert png.name == f"slotted-{phase.value}-full.png"
        return {"literal": "observed"}

    monkeypatch.setattr(printed, "export_pdf_only", export)
    monkeypatch.setattr(witness, "read_pdf", read)
    monkeypatch.setattr(
        witness, "require_pdf_content", lambda *_: {"native_body": "literal"}
    )
    checkpoints = []

    def checkpoint():
        checkpoints.append(1)
        if failure == "checkpoint" and len(checkpoints) == 2:
            raise primary

    record = {}

    def operation():
        return witness.capture(
            c.adapter,
            phase=phase,
            bank=c.bank,
            handles=c.handles,
            source=c.source,
            outputs=c.outputs,
            record=record,
            checkpoint=checkpoint,
        )

    expected_failure = failure not in ("none", "export") or (
        failure == "export" and phase is witness.CapturePhase.REOPENED
    )
    if not expected_failure:
        operation()
    else:
        with pytest.raises(BaseException) as caught:
            operation()
        if failure not in ("dirty", "hash"):
            assert caught.value is primary
    row = record[phase.value]
    assert row["status"] == ("failed" if expected_failure else "captured")
    assert row["before"] == {"drawing_dirty": True, "source_dirty": False}
    assert "after" in row and len(row["hashes_after"]) == 2
    assert len(calls) == (1 if phase is witness.CapturePhase.REOPENED else 0)
    assert len(checkpoints) == 2
    if failure in ("render", "cancel", "keyboard") or (
        failure == "export" and phase is witness.CapturePhase.REOPENED
    ):
        assert row["error"] == repr(primary)
        assert row["guard_errors"] and any(
            "dirty state" in note for note in primary.__notes__
        )


@pytest.mark.parametrize("property_ending", ["\n", "\r\n"])
@pytest.mark.parametrize("note_ending", ["\n", "\r\n"])
def test_sheet_reader_uses_actual_views_native_properties_and_linked_notes(
    live_scene, monkeypatch, property_ending, note_ending
):
    c = live_scene
    native_views = []
    for orientation, row in c.views.items():
        native_views.append(
            NS(
                GetName2=lambda orientation=orientation: orientation,
                GetOrientationName=lambda orientation=orientation: orientation,
                ScaleRatio=row["scale"],
                GetOutline=lambda row=row: row["outline"],
                ReferencedDocument=c.part,
            )
        )
    sheet = NS(
        GetProperties2=lambda: (0.0, 0.0, 6.0, 1.0, 0.0, 0.432, 0.279, 0.0),
        GetZoneMargin=lambda index: (0.009, 0.010, 0.011, 0.012)[index],
    )
    c.model.GetCurrentSheet = lambda: sheet
    c.model.GetViews = lambda: ((object(), *native_views),)
    monkeypatch.setattr(
        witness.attachments,
        "views",
        lambda _: {str(i): view for i, view in enumerate(native_views)},
    )
    texts = {
        "Manufacturing Notes": witness.spec.DRAWING_NOTES.replace(
            "\n", property_ending
        ),
        "End View Note": witness.spec.END_VIEW_NOTE,
    }
    c.part.GetCustomInfoValue = lambda configuration, name: texts[name]
    for name, value in texts.items():
        key = f"Sheet/{name}"
        c.bank["annotations"][key] = {
            "semantic": {"owner_type": 1, "kind": 6, "visible": 1, "dangling": False},
            "measurement": {"body": rectangle(), "envelope": rectangle()},
        }
        note = NS(
            PropertyLinkedText=witness.property_link(name),
            GetText=lambda value=value: value.replace("\r\n", "\n").replace(
                "\n", note_ending
            ),
        )
        c.handles[key] = (NS(GetSpecificAnnotation=lambda note=note: note),)
    result = witness.sheet_witness(c.adapter, c.model, c.part, c.bank, c.handles)
    assert result["geometry"]["drawable_m"] == pytest.approx([0.012, 0.01, 0.421, 0.27])
    assert result["source_notes"] == texts
    assert {name: row["text"] for name, row in result["notes"].items()} == {
        name: value.replace("\r\n", "\n").replace("\n", note_ending)
        for name, value in texts.items()
    }
    note.PropertyLinkedText = witness.property_link("Wrong property")
    with pytest.raises(RuntimeError, match="linked manufacturing note"):
        witness.sheet_witness(c.adapter, c.model, c.part, c.bank, c.handles)


@pytest.mark.parametrize(
    "damage",
    [
        "none",
        "off_page",
        "outside_body",
        "missing",
        "ambiguous",
        "nonfinite",
        "numeric_prefix",
        "numeric_suffix",
        "extra_text",
    ],
)
def test_required_pdf_text_is_literal_unique_and_inside_native_body(scene, damage):
    bank, _ = scene
    # Arbitrary synthetic coordinates; page points and native metres are explicit.
    glyphs = [
        {"text": text, "box_pt": [145 + index, 290, 146 + index, 295]}
        for index, text in enumerate("2.50")
    ]
    if damage == "off_page":
        glyphs[0]["box_pt"][3] = 800
    if damage == "outside_body":
        glyphs[0]["box_pt"][0] = 1
    if damage == "missing":
        glyphs.pop()
    if damage == "ambiguous":
        glyphs *= 2
    if damage == "nonfinite":
        glyphs[0]["box_pt"][0] = float("nan")
    if damage == "numeric_prefix":
        glyphs.insert(0, {"text": "1", "box_pt": [144, 290, 145, 295]})
    if damage in ("numeric_suffix", "extra_text"):
        glyphs.append(
            {
                "text": "1" if damage == "numeric_suffix" else "wrong",
                "box_pt": [149, 290, 150, 295],
            }
        )
    printed = {"page_size_pt": [1224, 792], "glyphs": glyphs}
    if damage != "none":
        with pytest.raises(RuntimeError, match="printed text|finite"):
            witness.require_pdf_content(printed, {"notes": {}}, bank)
        return
    result = witness.require_pdf_content(printed, {"notes": {}}, bank)
    assert len(result) == 3 and all(
        row["required"] == ["2.50"] for row in result.values()
    )


@pytest.mark.parametrize("route", ["parent", "worker"])
def test_capture_only_cli_forwards_exact_owned_producer_contract(
    monkeypatch, tmp_path, route
):
    import sys
    from diagnostics import probe_datum_policy_recipes as pilot
    from diagnostics import _recipe_template_factory as factories

    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", Mock())
    monkeypatch.setattr(factories, "require_factory_environment", Mock())
    monkeypatch.setattr(
        pilot.benchmark, "revision", lambda _: witness.PRODUCER_REVISION
    )
    calls, parent = [], Mock()
    monkeypatch.setitem(sys.modules, "dodo", NS(_run=parent))

    async def capture(*args, **kwargs):
        calls.append((args, kwargs))
        return {"acceptance": "not_accepted"}

    monkeypatch.setattr(witness, "capture_only", capture)
    monkeypatch.setattr(
        pilot, "run_copy_diagnostic", lambda callback: asyncio.run(callback(object()))
    )
    args = [
        "--source-root",
        str(tmp_path),
        "--guard-root",
        str(tmp_path),
        "--target",
        "slotted_screw",
        "--candidate",
        witness.PRODUCER_REVISION,
        "--factory",
        "prepared",
        "--layout-observation",
        "capture_only",
    ]
    if route == "worker":
        args.append("--worker")
        assert pilot.main(args) == {"acceptance": "not_accepted"}
        assert len(calls) == 1
        assert calls[0][0][1] == witness.PRODUCER_REVISION
        assert (
            calls[0][1]["setup_controller"].variant is factories.DrawingFactory.PREPARED
        )
        parent.assert_not_called()
        return
    assert pilot.main(args) == 0
    command = parent.call_args.args[0]
    for option, value in (
        ("--target", "slotted_screw"),
        ("--candidate", witness.PRODUCER_REVISION),
        ("--factory", "prepared"),
        ("--layout-observation", "capture_only"),
    ):
        assert command[command.index(option) + 1] == value
    assert parent.call_args.kwargs["com"] is True and not calls


@pytest.mark.parametrize(
    "args",
    [
        ["--target", "slotted_screw"],
        ["--target", "slotted_screw", "--layout-observation", "candidate"],
        [
            "--target",
            "rocker_arm",
            "--layout-observation",
            "capture_only",
            "--factory",
            "prepared",
        ],
        ["--target", "slotted_screw", "--layout-observation", "capture_only"],
        [
            "--target",
            "slotted_screw",
            "--layout-observation",
            "capture_only",
            "--factory",
            "normal",
        ],
        [
            "--target",
            "slotted_screw",
            "--layout-observation",
            "capture_only",
            "--factory",
            "prepared",
            "--source-observation",
            "alignment_save",
        ],
    ],
)
def test_incomplete_or_mixed_enrollment_contract_fails_before_environment(
    monkeypatch, tmp_path, args
):
    from diagnostics import probe_datum_policy_recipes as pilot

    environment = Mock(side_effect=AssertionError("must not attach"))
    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", environment)
    with pytest.raises(ValueError, match="registered|enrollment|slotted"):
        pilot.main(
            ["--source-root", str(tmp_path), "--guard-root", str(tmp_path), *args]
        )
    environment.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "none",
        "crlf_notes",
        "linked_reports",
        "wrong_hash",
        "wrong_producer",
        "initial_dirty",
        "initial_unreadable",
        "initial_zero",
        "initial_getter_error",
        "recipe_dirty",
        "build_dirty",
        "build",
        "build_checkpoint",
        "cancel_checkpoint",
        "keyboard_checkpoint",
        "build_checkpoint_cleanup",
        "timing_checkpoint",
        "build_owner_exit",
        "cancel_owner_exit",
        "keyboard_owner_exit",
        "raw_capture",
        "source_drift",
        "copy_drift",
        "runtime_drift",
        "cleanup",
    ],
)
async def test_actual_capture_callback_preserves_source_scope_and_nonacceptance(
    monkeypatch, tmp_path, failure
):
    from _drawing_build import normal_drawing_factory
    from diagnostics import probe_datum_policy_recipes as pilot
    from diagnostics import _recipe_template_factory as factories
    from diagnostics import _source_dimension_snapshot as source_reads
    from test_benchmark_drawing_recipes import recipe
    from test_datum_policy_recipes_drawing import Adapter, fixture_sources

    source_root, guard_root = fixture_sources(tmp_path, monkeypatch)
    for root in (source_root, guard_root):
        (root / "slotted-screw.SLDPRT").write_bytes(b"synthetic source")
    digest = witness.attachments.file_digest(source_root / "slotted-screw.SLDPRT")
    monkeypatch.setattr(witness, "SOURCE_SHA256", digest)
    originals = {
        path: path.read_bytes()
        for root in (source_root, guard_root)
        for path in root.glob("*.SLDPRT")
    }
    if failure == "wrong_hash":
        (guard_root / "slotted-screw.SLDPRT").write_bytes(b"not pinned")
    monkeypatch.setattr(
        pilot.benchmark, "recipe_source", lambda *_: recipe(Path("not-opened.SLDPRT"))
    )
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen-runtime")
    monkeypatch.setattr(pilot, "helper_fingerprints", lambda: {"helper": "same"})
    fingerprint = {"adapter": "same"}
    monkeypatch.setattr(pilot, "adapter_fingerprints", lambda: dict(fingerprint))
    monkeypatch.setattr(witness, "_early_bound", lambda value, _: value)
    primary_type = {
        "cancel_checkpoint": asyncio.CancelledError,
        "keyboard_checkpoint": KeyboardInterrupt,
        "timing_checkpoint": PermissionError,
        "cancel_owner_exit": asyncio.CancelledError,
        "keyboard_owner_exit": KeyboardInterrupt,
    }.get(failure, RuntimeError)
    primary = primary_type(f"original {failure} failure")
    checkpoint_error = PermissionError("secondary checkpoint sharing violation")
    cleanup_error = RuntimeError("secondary owned cleanup failure")
    scope_error = PermissionError("secondary ownership receipt sharing violation")
    checkpoint_failures = []
    original_write = Path.write_text

    def write_report(path, data, *args, **kwargs):
        if (
            "checkpoint" in failure
            and path.name == "capture.json"
            and '"recipe_seconds"' in data
            and not checkpoint_failures
        ):
            error = primary if failure == "timing_checkpoint" else checkpoint_error
            checkpoint_failures.append(error)
            raise error
        return original_write(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write_report)
    events, scopes = [], []
    adapter = Adapter("normal")
    source = NS(GetType=lambda: 1, GetSaveFlag=lambda: False)
    if failure == "initial_dirty":
        source.GetSaveFlag = lambda: True
    if failure == "initial_unreadable":
        source.GetSaveFlag = lambda: None
    if failure == "initial_zero":
        source.GetSaveFlag = lambda: 0
    if failure == "initial_getter_error":
        source.GetSaveFlag = Mock(side_effect=primary)
    model = NS(GetType=lambda: 3, GetSaveFlag=lambda: True, Visible=True)
    owned = {"native": None, "source": None}
    source.GetPathName = lambda: str(owned["source"])
    model.GetPathName = lambda: str(owned["native"])
    source.GetCustomInfoValue = lambda config, key: {
        "Generator": "wrong producer"
        if failure == "wrong_producer"
        else "harmonic-analyzer @ 3c0c4a97",
        "Manufacturing Notes": witness.spec.DRAWING_NOTES.replace("\n", "\r\n")
        if failure == "crlf_notes"
        else witness.spec.DRAWING_NOTES,
        "End View Note": witness.spec.END_VIEW_NOTE,
    }[key]
    adapter.swApp.GetOpenDocumentByName = lambda path: (
        source if Path(path) == owned["source"] else None
    )
    adapter.ownership.directories = set()
    adapter.ownership.register_directory = lambda path: (
        adapter.ownership.directories.add(Path(path).resolve())
    )
    adapter.ownership.assert_current_owned = lambda: NS(
        paths={owned["native"].resolve()} if owned["native"] is not None else set()
    )
    from contextlib import contextmanager

    @contextmanager
    def creating(kind, path):
        scopes.append((kind, path))
        yield

    adapter.ownership.creating_document = creating
    if failure.endswith("owner_exit"):
        from diagnostics._owned_native_documents import DiagnosticDocuments
        from types import MethodType

        adapter.ownership.creation = None
        adapter.ownership._output = lambda value: Path(value)
        adapter.ownership.inventory = Mock()
        adapter.ownership.checkpoint = Mock(side_effect=scope_error)
        adapter.ownership.creating_document = MethodType(
            DiagnosticDocuments.creating_document, adapter.ownership
        )

    async def open_model(path):
        owned["source"] = Path(path)
        assert Path(path) not in originals
        events.append("open_copy")
        adapter.currentModel = adapter.swApp.ActiveDoc = source
        return NS(is_success=True, data={})

    async def close():
        events.append("close")
        adapter.currentModel = adapter.swApp.ActiveDoc = None
        if failure == "cleanup" and len(events) > 2:
            raise primary
        if failure == "build_checkpoint_cleanup" and len(events) > 2:
            raise cleanup_error

    async def draw(outputs, actual_source):
        events.append("recipe")
        if failure == "linked_reports":
            # The real AST loader canonicalizes SOURCE, not the native open input.
            assert actual_source == owned["source"].resolve()
        else:
            assert actual_source == owned["source"]
        if failure in ("recipe_dirty", "build_dirty"):
            source.GetSaveFlag = lambda: True
        if failure in (
            "build",
            "build_dirty",
            "build_checkpoint",
            "cancel_checkpoint",
            "keyboard_checkpoint",
            "build_checkpoint_cleanup",
            "build_owner_exit",
            "cancel_owner_exit",
            "keyboard_owner_exit",
        ):
            raise primary
        owned["native"] = outputs.slddrw
        adapter.currentModel = adapter.swApp.ActiveDoc = model
        artifacts = {"drawing": outputs.slddrw, "pdf": outputs.pdf, "png": outputs.png}
        for path in artifacts.values():
            path.write_bytes(b"recipe output")
        if failure == "copy_drift":
            actual_source.write_bytes(b"changed")
        if failure == "runtime_drift":
            fingerprint["adapter"] = "changed"
        return {key: str(path) for key, path in artifacts.items()}

    adapter.open_model, adapter.close_owned_documents, adapter.draw = (
        open_model,
        close,
        draw,
    )
    parameter = object()
    reads = []

    def source_snapshot(app, model, path, *, required):
        assert (
            app is adapter.swApp
            and model is source
            and required == witness.spec.DRAWING_DIMENSIONS
        )
        reads.append(model)
        return {
            "raw": "changed"
            if failure == "source_drift" and len(reads) > 1
            else "exact"
        }, {"parameter": parameter}

    monkeypatch.setattr(source_reads, "dimension_snapshot", source_snapshot)
    monkeypatch.setattr(source_reads, "compare_source", Mock())

    def annotation_snapshot(actual_adapter):
        assert actual_adapter is adapter
        events.append("annotation_snapshot")
        if failure == "raw_capture":
            source.GetSaveFlag = lambda: True
            raise primary
        return {"raw": "retained slots"}, {"handle": parameter}

    monkeypatch.setattr(pilot.shoulder, "all_annotation_layout", annotation_snapshot)

    def background_snapshot(actual_adapter, annotations, handles, directory, setup):
        assert actual_adapter is adapter and annotations == {"raw": "retained slots"}
        assert handles == {"handle": parameter} and directory.parent == reports
        assert isinstance(setup, Setup)
        events.append("background_snapshot")
        return {"annotations": {}}

    monkeypatch.setattr(witness, "capture_sheet_background", background_snapshot)
    monkeypatch.setattr(
        witness,
        "capture_roles",
        lambda *_, background: (
            {"observed": "not an acceptance manifest"}
            if background == {"annotations": {}}
            else pytest.fail("missing background")
        ),
    )

    class Setup:
        variant = factories.DrawingFactory.PREPARED
        guards = {}

        async def configure(self, actual_adapter, module, report, directory):
            assert actual_adapter is adapter
            events.append("prepared_factory")
            self.factory = normal_drawing_factory(adapter, module.TEMPLATE_SPEC)
            return self.factory

        def require_used(self):
            self.factory.require_used()

        def final_guards(self):
            events.append("factory_final_guards")
            return []

    reports = tmp_path / "reports"
    if failure == "linked_reports":
        destination = tmp_path / "actual-reports"
        destination.mkdir()
        if os.name == "nt":
            # Directory junctions need no Windows symlink privilege.
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(reports), str(destination)],
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            reports.symlink_to(destination, target_is_directory=True)
        assert reports.resolve() == destination and reports != destination

    def operation():
        return pilot.pilot(
            adapter,
            witness.PRODUCER_REVISION,
            source_root,
            guard_root,
            reports,
            targets=("slotted_screw",),
            setup_controller=Setup(),
            layout_observation=witness.LayoutObservation.CAPTURE_ONLY,
        )

    if failure in ("none", "crlf_notes", "linked_reports"):
        result = await operation()
        assert result["acceptance"] == "not_accepted"
    else:
        with pytest.raises(primary_type) as caught:
            await operation()
        if failure in (
            "build",
            "build_dirty",
            "raw_capture",
            "cleanup",
            "initial_getter_error",
            "build_checkpoint",
            "cancel_checkpoint",
            "keyboard_checkpoint",
            "build_checkpoint_cleanup",
            "timing_checkpoint",
            "build_owner_exit",
            "cancel_owner_exit",
            "keyboard_owner_exit",
        ):
            assert caught.value is primary
    if failure == "wrong_hash":
        assert not events and not reports.exists()
        return
    (receipt,) = reports.glob("*/capture.json")
    report = json.loads(receipt.read_text(encoding="utf-8"))
    assert report["acceptance"] == "not_accepted"
    assert report["status"] == (
        "capture_only"
        if failure in ("none", "crlf_notes", "linked_reports")
        else "failed"
    )
    if failure == "crlf_notes":
        # Native 06no8kxz vs producer _seyh1jg: 17 exact lines, 16 inserted CRs.
        raw = report["source_properties"]["Manufacturing Notes"]
        assert len(raw) == 970 and raw.count("\r\n") == 16
        assert len(witness.spec.DRAWING_NOTES) == 954
        assert raw == witness.spec.DRAWING_NOTES.replace("\n", "\r\n")
    if failure == "linked_reports":
        assert reports in Path(report["copy_source"]).parents
        assert Path(report["copy_source"]).resolve() != Path(report["copy_source"])
    assert "reopened" not in report and "comparison" not in report
    assert all(path.read_bytes() == expected for path, expected in originals.items())
    assert len(report["sources_after"]) == 7
    assert events[-1] == "factory_final_guards" and events.count("close") == 2
    if failure.endswith("owner_exit"):
        adapter.ownership.checkpoint.assert_called_once_with()
        assert adapter.ownership.creation is None
        assert report["error"] == repr(primary)
        assert report["recipe_scope_errors"] == [repr(scope_error)]
        assert any(repr(scope_error) in note for note in primary.__notes__)
        assert report["source_dirty_before"] is False
        assert report["source_dirty_final"] is False
    if "checkpoint" in failure:
        assert checkpoint_failures and report["error"] == repr(primary)
        assert report["source_dirty_before"] is False
        assert report["source_dirty_final"] is False
        assert report["recipe_seconds"] >= 0
        if failure != "timing_checkpoint":
            assert report["recipe_checkpoint_errors"] == [repr(checkpoint_error)]
            assert any(repr(checkpoint_error) in note for note in primary.__notes__)
        if failure == "build_checkpoint_cleanup":
            assert report["final_guard_errors"] == [repr(cleanup_error)]
            assert any(repr(cleanup_error) in note for note in primary.__notes__)
    if failure in (
        "source_drift",
        "copy_drift",
        "runtime_drift",
        "cleanup",
        "none",
        "crlf_notes",
        "linked_reports",
    ):
        assert report["annotations"] == {"raw": "retained slots"}
        assert len(scopes) == 1
        assert report["recipe_seconds"] >= 0
        assert events.count("background_snapshot") == 1
    if failure == "raw_capture":
        assert report["capture_final"]["source_dirty"] is True
        assert report["final_guard_errors"] and primary.__notes__
    if failure.startswith("initial_"):
        assert not reads and "recipe" not in events and not scopes
    if failure in ("recipe_dirty", "build_dirty"):
        assert report["source_dirty_before"] is False
        assert report["source_dirty_final"] is True
        assert any("source dirty" in error for error in report["final_guard_errors"])
        assert report["sources_after"][report["copy_source"]] == digest
    if failure == "build_dirty":
        assert any("source dirty" in note for note in primary.__notes__)


@pytest.fixture
def sheet_background(tmp_path, monkeypatch):
    retained = json.loads(
        (Path(__file__).parent / "fixtures/slotted_hidden_sheet_finish.json").read_text(
            encoding="utf-8"
        )
    )
    path = tmp_path / "cache" / "entry" / "receipt.json"
    path.parent.mkdir(parents=True)
    prepared = {
        "status": retained["prepared_status"],
        "before": {"sheet_surface_finishes": [retained["prepared_hidden_sf"]]},
        "after": {"sheet_surface_finishes": [deepcopy(retained["prepared_hidden_sf"])]},
    }
    path.write_text(json.dumps(prepared), encoding="utf-8")
    digest = witness.attachments.file_digest(path)
    controller = NS(
        inputs={str(path): digest},
        row={
            "variant": "prepared",
            "accessors": [
                {
                    "kind": kind,
                    "status": "passed",
                    "path": str(path.with_name("prepared.DRWDOT")),
                    "artifacts": {str(path): digest},
                }
                for kind in ("miss", "hit")
            ],
        },
    )
    sheet = object()
    adapter = NS(
        currentModel=NS(GetCurrentSheet=lambda: sheet),
        swApp=NS(IsSame=lambda a, b: int(a is b)),
    )
    key = retained["annotation_key"]
    monkeypatch.setattr(witness, "_early_bound", lambda value, _: value)
    return NS(
        raw={key: retained["annotation"]},
        handles={key: (NS(Owner=sheet),)},
        directory=tmp_path,
        controller=controller,
        adapter=adapter,
        key=key,
        path=path,
        prepared=prepared,
    )


def test_retained_sheet_fixture_preserves_preparer_status_and_native_numeric_types(
    sheet_background,
):
    c = sheet_background
    assert c.prepared["status"] == "validated"
    assert type(c.raw[c.key]["position"][0]) is float
    assert type(c.raw[c.key]["generic"]["lines"][0][3]) is float
    assert (
        type(c.prepared["before"]["sheet_surface_finishes"][0]["position"][0]) is float
    )
    assert type(c.raw[c.key]["semantic"]["kind"]) is int


def test_actual_recipe_gate_tracks_retained_slotted_fixture():
    from test_dodo_recipe import _load_dodo

    task = next(row for row in _load_dodo().task_check() if row["name"] == "recipe")
    test_path = Path(__file__).resolve()
    fixture_path = test_path.parent / "fixtures/slotted_hidden_sheet_finish.json"
    assert str(test_path) in task["actions"][0][1][0]
    assert str(fixture_path) in task["file_dep"]


@pytest.mark.parametrize(
    "damage",
    [
        "none",
        "line",
        "position",
        "text",
        "visible",
        "attached",
        "null_slot",
        "dangling",
        "owner",
        "owner_type",
        "owner_null",
        "duplicate",
        "missing",
        "missing_guard",
        "receipt_hash",
        "prepared_changed",
        "prepared_duplicate",
        "wrong_kind",
        "bool_kind",
        "bool_coordinate",
        "incomplete_accessors",
    ],
)
def test_retained_hidden_sheet_background_is_exact_and_capture_only(
    sheet_background, damage
):
    c = sheet_background
    row = c.raw[c.key]
    if damage == "line":
        row["generic"]["lines"][0][7] += 1e-12
    if damage == "position":
        row["position"][0] = 1e-12
    if damage == "text":
        row["generic"]["texts"] = [{"value": "unexpected"}]
    if damage == "visible":
        row["semantic"]["visible"] = 1
    if damage == "attached":
        row["semantic"]["attachment_types"] = [2]
    if damage == "null_slot":
        row["semantic"]["null_attachments"] = [True]
    if damage == "dangling":
        row["semantic"]["dangling"] = True
    if damage == "owner":
        c.handles[c.key][0].Owner = object()
    if damage == "owner_type":
        row["semantic"]["owner_type"] = 0
    if damage == "owner_null":
        row["semantic"]["owner_null"] = True
    if damage == "duplicate":
        c.raw["duplicate"] = deepcopy(row)
    if damage == "missing":
        c.raw.clear()
    if damage == "missing_guard":
        c.controller.inputs.clear()
    if damage == "receipt_hash":
        c.path.write_text("changed", encoding="utf-8")
    if damage in ("prepared_changed", "prepared_duplicate"):
        rows = c.prepared["after"]["sheet_surface_finishes"]
        if damage == "prepared_changed":
            rows[0]["position"][0] = 1e-12
        else:
            rows.append(deepcopy(rows[0]))
        c.path.write_text(json.dumps(c.prepared), encoding="utf-8")
        digest = witness.attachments.file_digest(c.path)
        c.controller.inputs[str(c.path)] = digest
        for accessor in c.controller.row["accessors"]:
            accessor["artifacts"][str(c.path)] = digest
    if damage == "wrong_kind":
        row["semantic"]["kind"] = 99
    if damage == "bool_kind":
        row["semantic"]["owner_type"] = True
    if damage == "bool_coordinate":
        row["position"][0] = False
    if damage == "incomplete_accessors":
        c.controller.row["accessors"].pop()
    if damage != "none":
        with pytest.raises(RuntimeError, match="slotted|hidden sheet SF"):
            witness.capture_sheet_background(
                c.adapter, c.raw, c.handles, c.directory, c.controller
            )
        return
    observed = witness.capture_sheet_background(
        c.adapter, c.raw, c.handles, c.directory, c.controller
    )
    assert observed["annotations"] == c.raw
    assert observed["annotations"][c.key] is not row
    assert observed["scope"].startswith("capture_only")
    assert observed["sha256"] == c.controller.inputs[str(c.path)]


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["parent", "worker", "pilot", "callback"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("HARMONIC_BSURF_GRID_CONTROL", "boundary-domain"),
        ("HARMONIC_BSURF_GRID_CONTROL", "column-row-grid"),
        ("HARMONIC_TOOTH_SELECTOR_OBSERVATION", "endpoints"),
    ],
)
async def test_capture_rejects_every_nondefault_environment_factor_before_native(
    monkeypatch,
    tmp_path,
    route,
    field,
    value,
):
    from diagnostics import probe_datum_policy_recipes as pilot
    from diagnostics import _recipe_template_factory as factories

    monkeypatch.setenv(field, value)
    environment = Mock(
        side_effect=AssertionError("must reject before native environment")
    )
    monkeypatch.setattr(pilot, "require_owned_diagnostic_environment", environment)
    setup = NS(variant=factories.DrawingFactory.PREPARED)
    with pytest.raises(ValueError, match="grid|tooth"):
        if route == "callback":
            await witness.capture_only(
                object(),
                witness.PRODUCER_REVISION,
                tmp_path,
                tmp_path,
                tmp_path / "reports",
                setup_controller=setup,
            )
        elif route == "pilot":
            await pilot.pilot(
                object(),
                witness.PRODUCER_REVISION,
                tmp_path,
                tmp_path,
                tmp_path / "reports",
                targets=("slotted_screw",),
                layout_observation=witness.LayoutObservation.CAPTURE_ONLY,
                setup_controller=setup,
            )
        else:
            pilot.main(
                [
                    "--source-root",
                    str(tmp_path),
                    "--guard-root",
                    str(tmp_path),
                    "--target",
                    "slotted_screw",
                    "--layout-observation",
                    "capture_only",
                    "--factory",
                    "prepared",
                    "--candidate",
                    witness.PRODUCER_REVISION,
                    *(["--worker"] if route == "worker" else []),
                ]
            )
    environment.assert_not_called()
    assert not (tmp_path / "reports").exists()


@pytest.mark.parametrize(
    "damage",
    [
        "none",
        "wrong_parameter",
        "wrong_named",
        "wrong_roundtrip",
        "wrong_source",
        "wrong_owner",
        "wrong_view",
        "missing",
        "extra",
        "retained_hidden",
        "retained_hidden_changed",
        "retained_unknown",
        "retained_unknown_template",
    ],
)
def test_raw_role_capture_reuses_slots_and_proves_live_native_identity(
    monkeypatch, damage, sheet_background
):
    parameters, raw, handles, views = {}, {}, {}, {}
    part = NS(Parameter=lambda role: parameters[role])
    for index, (role, orientation) in enumerate(witness.DIMENSION_VIEWS.items()):
        full = f"{role}@owned.Part"
        parameter = parameters[role] = NS(FullName=full)
        view = NS(
            GetOrientationName=lambda orientation=orientation: orientation,
            ReferencedDocument=part,
        )
        views[str(index)] = view
        key = f"View{index}/{role}"
        display = NS(GetDimension2=lambda _, parameter=parameter: parameter, Type2=97)
        annotation = NS(
            Owner=view, GetSpecificAnnotation=lambda display=display: display
        )
        display.GetAnnotation = lambda annotation=annotation: annotation
        # 97/99 deliberately synthetic; do not silently pin these observations.
        raw[key] = {
            "semantic": {
                "kind": 4,
                "owner_type": 0,
                "attachment_types": (99,),
                "null_attachments": (False,),
                "visible": 1,
                "dangling": False,
            },
            "generic": {"texts": [{"value": "synthetic value"}]},
        }
        handles[key] = (annotation,)
    source_handles = {value.FullName: value for value in parameters.values()}
    app = NS(IsSame=lambda a, b: int(a is b))
    adapter = NS(swApp=app, currentModel=object())
    monkeypatch.setattr(witness, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(witness.attachments, "views", lambda _: views)
    if damage == "wrong_parameter":
        display.GetDimension2 = lambda _: NS(FullName=parameter.FullName)
    if damage == "wrong_named":
        part.Parameter = lambda _: object()
    if damage == "wrong_roundtrip":
        display.GetAnnotation = object
    if damage == "wrong_source":
        view.ReferencedDocument = object()
    if damage == "wrong_owner":
        annotation.Owner = object()
    if damage == "wrong_view":
        view.GetOrientationName = lambda: "*Wrong"
    if damage == "missing":
        del raw[key]
    if damage == "extra":
        raw["extra"] = deepcopy(raw[key])
        handles["extra"] = handles[key]
    if damage.startswith("retained_"):
        raw.update(sheet_background.raw)
        handles.update(sheet_background.handles)
        adapter.currentModel = sheet_background.adapter.currentModel
    if damage.startswith("retained_unknown"):
        raw["unknown"] = {
            "semantic": {
                "kind": 99,
                "owner_type": 2 if damage == "retained_unknown_template" else 1,
            }
        }
    if damage != "none" and not damage.startswith("retained_"):
        with pytest.raises(
            RuntimeError, match="identity|inventory|native view|missing"
        ):
            witness.capture_roles(adapter, raw, handles, part, source_handles)
        return
    background = None
    if damage.startswith("retained_"):
        background = witness.capture_sheet_background(
            adapter,
            raw,
            handles,
            sheet_background.directory,
            sheet_background.controller,
        )
    if damage.startswith("retained_unknown") or damage == "retained_hidden_changed":
        if damage == "retained_hidden_changed":
            raw[sheet_background.key]["position"][0] = 1e-12
        with pytest.raises(
            RuntimeError, match="unexpected annotation|background changed"
        ):
            witness.capture_roles(
                adapter, raw, handles, part, source_handles, background=background
            )
        return
    observed = witness.capture_roles(
        adapter, raw, handles, part, source_handles, background=background
    )
    assert observed.keys() == witness.DIMENSION_VIEWS.keys()
    assert all(
        row["attachment_types"] == (99,) and row["display_type"] == 97
        for row in observed.values()
    )


def test_actual_pdfium_full_page_reader_keeps_uncropped_image(tmp_path):
    from PIL import Image

    # A self-contained synthetic PDF, not a native CAD output or source artifact.
    content = b"BT /F1 12 Tf 10 30 Td (2.50) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(content)).encode()
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
    ]
    pdf_bytes = b"%PDF-1.4\n"
    offsets = []
    for index, obj in enumerate(objects, 1):
        offsets.append(len(pdf_bytes))
        pdf_bytes += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(pdf_bytes)
    pdf_bytes += b"xref\n0 6\n0000000000 65535 f \n"
    pdf_bytes += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    pdf_bytes += (
        f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    pdf, png = tmp_path / "fixture.pdf", tmp_path / "full.png"
    pdf.write_bytes(pdf_bytes)
    result = witness.read_pdf(pdf, png)
    assert result["page_size_pt"] == [72.0, 72.0]
    assert "".join(row["text"] for row in result["glyphs"]) == "2.50"
    assert result["full_page_raster"]["size"] == [300, 300]
    with Image.open(png) as image:
        assert list(image.size) == [300, 300]
    assert pdf.read_bytes() == pdf_bytes
    with pytest.raises(RuntimeError, match="fresh PNG"):
        witness.read_pdf(pdf, png)
