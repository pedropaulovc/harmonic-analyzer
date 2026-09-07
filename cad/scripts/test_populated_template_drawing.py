"""Populated-template controls never turn measured defects into acceptance."""

import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import _populated_template_fields as fields
from diagnostics import probe_populated_template as probe
from test_baked_template_layout_drawing import note, scene
from test_title_cell_drawing import box_lines


def populated():
    notes, lines = scene()
    for name, text in (("title", "rocker-arm"), ("dwg", "MHA-071"), ("rev", "v32")):
        notes[name]["text"], notes[name]["extent_scope"] = text, "measured"
    notes["label"] = note("REV", "REV", x=0.38, y=0.034, height=0.00254, horizontal=1)
    notes["material"] = note(fields.VALUE_LINKS["material"], "Steel", x=0.205, y=0.023)
    notes["finish"] = note(fields.VALUE_LINKS["finish"], "Plain", x=0.205, y=0.037)
    notes["copyright"] = note(
        '© 2026 $PRPSHEET:"SW-Author(Author)"', "© 2026 Pedro", x=0.35, y=0.018
    )
    notes["copyright"]["extent"][1] = 0.015
    lines += (
        box_lines(0.2, 0.017, 0.26, 0.027)
        + box_lines(0.2, 0.03, 0.26, 0.043)
        + box_lines(0.0127, 0.0127, 0.4191, 0.2667)
    )

    def pdf(text):
        row = next(row for row in notes.values() if row["text"] == text)
        e = row["extent"]
        return {
            "text": text,
            "ink_box_pt": [e[i] * 72 / 0.0254 for i in (0, 1, 3, 4)],
            "characters": [{"text": text, "box_pt": [1, 2, 3, 4]}],
        }

    return notes, lines, pdf


def test_footer_is_explicit_measured_strip_not_fallback_closed_cell():
    notes, lines, pdf = populated()
    result = fields.field_audit(notes, lines, pdf_reader=pdf)
    assert result["status"] == "passed", result["issues"]
    footer = result["fields"]["copyright"]
    assert footer["region_kind"] == "measured_footer_strip"
    assert footer["region_m"] == (0.0127, 0.0127, 0.4191, 0.019)


def test_all_material_finish_and_footer_defects_are_reported_independently():
    notes, lines, pdf = populated()
    notes["material_label"] = note("MATERIAL", "MATERIAL", x=0.205, y=0.028)
    notes["finish_label"] = note("FINISH", "FINISH", x=0.205, y=0.0415)
    lines.append(((0.355, 0.014, 0), (0.355, 0.019, 0)))
    result = fields.field_audit(notes, lines, pdf_reader=pdf)
    assert result["status"] == "failed"
    assert any(
        row["field"] == "material_label" and row["kind"] == "native_fit"
        for row in result["issues"]
    )
    assert any(
        "finish_label" in row["field"] and "clearance" in row["kind"]
        for row in result["issues"]
    )
    assert any(
        row["field"] == "copyright" and "rule_crossing" in row["kind"]
        for row in result["issues"]
    )
    # MATERIAL is associated with its real value cell, not the label's wrong anchor cell.
    assert result["fields"]["material_label"]["region_kind"] == "semantic_material_cell"
    assert result["fields"]["finish"]["status"] == "failed"
    assert result["fields"]["finish_label"]["status"] == "failed"


@pytest.mark.parametrize(
    "mode", ["formula", "unknown_region", "empty_ink", "pdf_text", "no_frame"]
)
def test_unsupported_missing_or_unresolved_fields_are_not_accepted(mode):
    notes, lines, pdf = populated()
    if mode == "formula":
        notes["rev"]["text"] = "$PRPSHEET:{Revision}"
    if mode == "unknown_region":
        notes["outside"] = note('$PRP:"Other"', "Other", x=0.5)
    if mode == "empty_ink":
        notes["material"]["text"] = ""
    if mode == "pdf_text":
        original = pdf

        def pdf(text):
            return dict(original(text), text="wrong")

    if mode == "no_frame":
        lines = [line for line in lines if not line[0][0] == line[1][0] == 0.0127]
    assert fields.field_audit(notes, lines, pdf_reader=pdf)["status"] == "failed"


@pytest.mark.parametrize(
    "mode", ["positive", "raised", "different_template", "extra_call"]
)
def test_normal_factory_redirects_one_argument_and_always_restores(
    monkeypatch, tmp_path, mode
):
    path = tmp_path / "derived.DRWDOT"
    path.write_bytes(b"derived")
    sha = probe.title.pilot.attachments.file_digest(path)
    adapter = object()
    native = Mock(return_value="drawing")
    monkeypatch.setattr(probe.common, "new_drawing", native)

    def current(current_adapter, **_):
        if mode == "raised":
            raise RuntimeError("normal setup failure")
        result = probe.common.new_drawing(
            current_adapter,
            template="wrong"
            if mode == "different_template"
            else str(probe.common.PROJECT_DRWDOT),
            width=probe.common.ASME_B_WIDTH_M,
            height=probe.common.ASME_B_HEIGHT_M,
        )
        if mode == "extra_call":
            probe.common.new_drawing(
                current_adapter,
                template=str(probe.common.PROJECT_DRWDOT),
                width=probe.common.ASME_B_WIDTH_M,
                height=probe.common.ASME_B_HEIGHT_M,
            )
        return result

    monkeypatch.setattr(probe.common, "new_project_drawing", current)
    witness = Mock(return_value={"exact": "normal defaults"})
    monkeypatch.setattr(probe, "snapshot_defaults", witness)
    controller = probe.PopulatedControl(path, sha, Mock())
    if mode == "positive":
        assert controller.factory(adapter, scale=probe.title.SCALE) == "drawing"
        native.assert_called_once_with(
            adapter,
            template=str(path),
            width=probe.common.ASME_B_WIDTH_M,
            height=probe.common.ASME_B_HEIGHT_M,
        )
        witness.assert_called_once()
        with pytest.raises(RuntimeError, match="only once"):
            controller.factory(adapter)
    else:
        with pytest.raises(RuntimeError):
            controller.factory(adapter)
        witness.assert_not_called()
    assert probe.common.new_drawing is native


def test_template_hash_mismatch_stops_before_any_factory_call(monkeypatch, tmp_path):
    path = tmp_path / "derived.DRWDOT"
    path.write_bytes(b"wrong bytes")
    native = Mock(side_effect=AssertionError("no native call"))
    monkeypatch.setattr(probe.common, "new_drawing", native)
    controller = probe.PopulatedControl(path, "0" * 64, Mock())
    with pytest.raises(RuntimeError):
        controller.factory(object())
    native.assert_not_called()


@pytest.mark.parametrize(
    "mode", ["pass", "fit_issues", "cold_issues", "native_failure"]
)
def test_thin_controller_reuses_two_trials_and_retains_failed_acceptance(
    monkeypatch, tmp_path, mode
):
    template = tmp_path / "derived.DRWDOT"
    template.write_bytes(b"derived")
    original = tmp_path / "original.DRWDOT"
    original.write_bytes(b"original")
    sources = tmp_path / "parts"
    sources.mkdir()
    expected = {}
    for target in probe.TARGETS:
        path = sources / f"{target.replace('_', '-')}.SLDPRT"
        path.write_bytes(target.encode())
        expected[str(path)] = probe.title.pilot.attachments.file_digest(path)
    monkeypatch.setattr(probe.common, "PROJECT_DRWDOT", original)
    monkeypatch.setattr(probe.title.pilot, "require_sources", lambda *_: dict(expected))
    monkeypatch.setattr(probe.title.pilot, "helper_fingerprints", lambda: {})
    monkeypatch.setattr(probe.title.pilot, "adapter_fingerprints", lambda: {})
    monkeypatch.setattr(probe.title.pilot.benchmark, "revision", lambda _: "frozen")
    calls = []

    async def trial(
        adapter, variant, source, directory, report, checkpoint, inputs, **kwargs
    ):
        calls.append(kwargs)
        assert variant is probe.title.Variant.BASELINE
        assert kwargs["source_target"] in probe.TARGETS
        assert directory.name.startswith("populated-template-")
        assert directory.name.endswith(kwargs["source_target"])
        assert kwargs["source_title"] == probe.TARGETS[kwargs["source_target"]]
        assert kwargs["factory"].__self__ is kwargs["observe_output"].__self__
        if mode == "native_failure":
            raise RuntimeError("native guard failure")
        issue = (
            [{"field": "material", "kind": "native_fit"}]
            if mode == "fit_issues"
            else []
        )
        result = {
            "linked_fields": {
                "built": {"fit": {"issues": issue}},
                "cold": {"fit": {"issues": deepcopy(issue)}},
            },
            "cold_delta": {"changed_leaf_count": int(mode == "cold_issues")},
            "printed": {"classification": "unchanged"},
            "png_delta": {"changed_pixel_count": 0},
        }
        report["trials"].append(result)
        return result

    monkeypatch.setattr(probe.title, "one_trial", trial)

    async def close():
        pass

    adapter = SimpleNamespace(
        ownership=SimpleNamespace(register_directory=Mock(), register_source=Mock()),
        close_owned_documents=close,
    )
    sha = probe.title.pilot.attachments.file_digest(template)
    if mode == "pass":
        asyncio.run(probe.probe(adapter, template, sha, sources, tmp_path / "reports"))
    else:
        with pytest.raises(ExceptionGroup):
            asyncio.run(
                probe.probe(adapter, template, sha, sources, tmp_path / "reports")
            )
    assert len(calls) == (1 if mode == "native_failure" else 2)
    (path,) = (tmp_path / "reports").glob("*/populated-template.json")
    report = json.loads(path.read_text())
    assert report["status"] == ("passed" if mode == "pass" else "failed")
    assert report["inputs_before"] == report["inputs_after"]
    if mode in {"fit_issues", "cold_issues"}:
        assert all(row["acceptance_issues"] for row in report["trials"])


def test_second_source_title_comparison_keeps_exact_glyph_gate():
    text = "channel-lever"
    row = {
        "text": text,
        "page_size_pt": [1224, 792],
        "characters": [
            {"text": letter, "box_pt": [i, 0, i + 1, 1]}
            for i, letter in enumerate(text)
        ],
    }
    assert (
        probe.title.printed_displacement(row, row, expected_title=text)[
            "classification"
        ]
        == "unchanged"
    )
    with pytest.raises(RuntimeError):
        probe.title.printed_displacement(row, row)
    moved = deepcopy(row)
    moved["characters"][0]["box_pt"][0] += 1e-9
    assert (
        probe.title.printed_displacement(row, moved, expected_title=text)[
            "classification"
        ]
        != "unchanged"
    )


@pytest.mark.parametrize(
    "mode",
    ["pass", "number", "revision", "font", "pdf_drift", "preferences", "wrong_owner"],
)
def test_read_only_observer_keeps_links_full_cold_style_and_independent_failures(
    monkeypatch, tmp_path, mode
):
    notes, lines, _ = populated()
    for name in ("title", "dwg", "rev"):
        notes[name]["horizontal"] = 1
    notes["dwg"]["font"]["CharHeight"] = notes["rev"]["font"]["CharHeight"] = 0.0035
    path = tmp_path / "owned.SLDPRT"
    source = SimpleNamespace(
        GetPathName=lambda: str(
            tmp_path / "wrong.SLDPRT" if mode == "wrong_owner" else path
        ),
        GetType=lambda: 1,
        SummaryInfo=lambda _: "rocker-arm",
        GetCustomInfoValue=lambda _, key: {"Number": "MHA-071", "Revision": "v32"}[key],
    )
    document = SimpleNamespace(
        GetCustomInfoValue=lambda *_: "v31" if mode == "revision" else ""
    )
    adapter = SimpleNamespace(
        currentModel=document,
        swApp=SimpleNamespace(GetOpenDocumentByName=lambda _: source),
    )
    monkeypatch.setattr(probe.layout.cells, "required", lambda value, _: value)
    monkeypatch.setattr(
        probe.layout, "note_inventory", lambda _: (deepcopy(notes), {}, ["same SF raw"])
    )
    monkeypatch.setattr(
        probe.layout.cells,
        "template_lines",
        lambda _: (lines, {"same": "native lines"}),
    )
    prefs = {"units": {"system": 4, "linear": 0, "decimals": 2}}
    monkeypatch.setattr(probe, "preferences", lambda _: deepcopy(prefs))
    glyph = {"text": "REV", "characters": [{"text": "R", "box_pt": [1, 2, 3, 4]}]}
    monkeypatch.setattr(
        probe.fields,
        "field_audit",
        lambda *_args, **_kwargs: {
            "issues": [],
            "fields": {"label": {"pdf": deepcopy(glyph)}},
        },
    )
    controller = probe.PopulatedControl(tmp_path / "derived.DRWDOT", "0" * 64, Mock())
    controller.setup["normalized_blank_defaults"] = deepcopy(prefs)
    trial = {"source_copy": str(path)}
    if mode == "wrong_owner":
        with pytest.raises(RuntimeError, match="wrong exact source"):
            controller.observe(adapter, "built", trial, tmp_path / "first.pdf")
        return
    if mode == "number":
        notes["dwg"]["text"] = "WRONG"
    controller.observe(adapter, "built", trial, tmp_path / "first.pdf")
    if mode == "font":
        notes["rev"]["font"]["Bold"] = True
    if mode == "pdf_drift":
        glyph["characters"][0]["box_pt"][0] += 1e-9
    if mode == "preferences":
        prefs["units"]["system"] = 5
    controller.observe(adapter, "cold", trial, tmp_path / "cold.pdf")
    issues = trial["linked_fields"]["cold"]["fit"]["issues"]
    if mode == "pass":
        assert not issues
    else:
        assert issues
    if mode == "font":
        assert any(row["kind"] == "raw_snapshot" for row in issues)
    if mode == "pdf_drift":
        assert any(row["kind"] == "pdf_field_glyphs" for row in issues)
