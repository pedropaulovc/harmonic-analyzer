"""Populated-template controls never turn measured defects into acceptance."""

import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import _populated_template_fields as fields
from diagnostics import probe_populated_template as probe
from diagnostics import _populated_template_symbols as symbols
from diagnostics._populated_template_native_fixture import RETAINED
from test_baked_template_layout_drawing import note, scene
from test_title_cell_drawing import box_lines


def angular_path():
    # Raw PDFium reads of the recorded first/cold PDFs; no manufactured Unicode.
    points = [
        [887.2000122070312, 154.70001220703125],
        [897.4000244140625, 161.10000610351562],
        [887.2000122070312, 154.70001220703125],
        [897.4000244140625, 154.70001220703125],
    ]
    return {
        "segments": [
            {"kind": kind, "point_pt": point, "closure": "open"}
            for kind, point in zip([2, 0, 2, 0], points, strict=True)
        ],
        "matrix": [1, 0, 0, 1, 0, 0],
        "fill": 0,
        "stroke": 1,
        "rgba": [0, 0, 0, 255],
        "width_pt": 0.5102400183677673,
        "ink_box_pt": [
            886.4966430664062,
            153.99661254882812,
            898.1033935546875,
            161.80340576171875,
        ],
    }


def test_retained_angular_path_matches_symbol_grid_without_rounding_raw_data(tmp_path):
    path = tmp_path / "gtol.sym"
    path.write_text(
        "#GGTOL,GOST\n*ANGULAR,Angularity\nA,LINE .0,.0,1.6,1.\nA,LINE .0,.0,1.6,.0\n"
    )
    library = symbols.symbol_library(path)
    actual = angular_path()
    expected = deepcopy(actual)
    result = symbols.require_angular_path(actual, library)
    assert result["shape_residual_pt"] == 0.03997802734375
    assert result["grid_residual_pt"] == pytest.approx(0.00002441406240905053)
    assert result["path"] == actual == expected
    path.write_text(path.read_text().replace("1.6,1.", "1.8,1."))
    with pytest.raises(RuntimeError, match="definition"):
        symbols.symbol_library(path)


@pytest.mark.parametrize(
    "mode",
    [
        "missing",
        "curve",
        "closed",
        "extra",
        "transparent",
        "fill",
        "nan",
        "wrong_angle",
        "off_grid",
    ],
)
def test_angular_shape_does_not_accept_unknown_or_changed_vector_ink(mode):
    path = angular_path()
    if mode == "missing":
        path["segments"].pop()
    if mode == "extra":
        path["segments"].append(deepcopy(path["segments"][-1]))
    if mode == "curve":
        path["segments"][1]["kind"] = 1
    if mode == "closed":
        path["segments"][-1]["closure"] = "closed"
    if mode == "transparent":
        path["rgba"][-1] = 0
    if mode == "fill":
        path["fill"] = 1
    if mode == "nan":
        path["segments"][0]["point_pt"][0] = float("nan")
    if mode == "wrong_angle":
        path["segments"][1]["point_pt"][1] += 1
    if mode == "off_grid":
        path["segments"][1]["point_pt"][1] += 0.012
    with pytest.raises(RuntimeError):
        symbols.require_angular_path(path, {"grid_lines": [[0, 0, 1.6, 1]]})


def test_whole_sheet_frame_bbox_is_not_misidentified_as_symbol_ink():
    path = angular_path()
    path["segments"] = [
        {"kind": kind, "point_pt": point, "closure": "open"}
        for kind, point in [
            (2, [0, 0]),
            (0, [1224, 0]),
            (0, [1224, 792]),
            (0, [0, 792]),
            (0, [0, 0]),
        ]
    ]
    assert not symbols.intersects_path(path, [880, 145, 901, 163])
    assert symbols.intersects_path(angular_path(), [880, 145, 901, 163])


@pytest.mark.parametrize(
    "mode",
    [
        "pass",
        "token",
        "font_rotation",
        "run_count",
        "missing_path",
        "extra_path",
        "cold_drift",
    ],
)
def test_retained_symbol_note_preserves_literal_and_full_pdf_vector_witness(
    monkeypatch, mode
):
    import pypdfium2

    note = deepcopy(RETAINED["angular_note"])
    if mode == "token":
        note["text"] = note["text"].replace("ANGULAR", "UNKNOWN")
    if mode == "font_rotation":
        note["display"]["texts"][0]["angle_rad"] = 0.1
    if mode == "run_count":
        note["display"]["texts"].append(deepcopy(note["display"]["texts"][0]))
    literal = {
        "text": "±1°",
        "characters": [{"text": "±1°", "box_pt": [888, 147, 897, 152]}],
        "ink_box_pt": [888, 147, 897, 152],
        "page_size_pt": [1224, 792],
    }
    monkeypatch.setattr(symbols.retained, "pdf_title", lambda *_: deepcopy(literal))
    obj = SimpleNamespace(type=2, get_bounds=lambda: (886, 153, 899, 162))
    native = angular_path()
    monkeypatch.setattr(symbols, "path_snapshot", lambda _: deepcopy(native))
    objects = (
        [] if mode == "missing_path" else [obj, obj] if mode == "extra_path" else [obj]
    )
    page = SimpleNamespace(get_objects=lambda **_: iter(objects))

    class Document:
        def __len__(self):
            return 1

        def __getitem__(self, _):
            return page

        def close(self):
            pass

    monkeypatch.setattr(pypdfium2, "PdfDocument", lambda _: Document())
    library = {"grid_lines": [[0, 0, 1.6, 1]]}
    if mode not in ("pass", "cold_drift"):
        with pytest.raises(RuntimeError):
            symbols.pdf_field("owned.pdf", note, library)
        return
    result = symbols.pdf_field("owned.pdf", note, library)
    assert result["text"] == "±1°"
    assert result["decoded_native_text"] == note["text"]
    assert result["symbol"]["path"] == native
    assert result["ink_box_pt"][0] == native["ink_box_pt"][0]
    if mode == "cold_drift":
        native["ink_box_pt"][0] += 1e-9
        assert symbols.pdf_field("cold.pdf", note, library) != result


def test_retained_fixture_is_an_actual_recipe_gate_input():
    import dodo
    from diagnostics import _populated_template_native_fixture
    from pathlib import Path

    recipe = next(row for row in dodo.task_check() if row["name"] == "recipe")
    assert Path(_populated_template_native_fixture.__file__).resolve() in {
        Path(path).resolve() for path in recipe["file_dep"]
    }


def test_populated_defaults_require_the_exact_explicit_property_source_transition():
    blank = {
        "units": {"system": 4},
        "sheet_properties": [2, 12, 1, 2, 0, 0.4318, 0.2794, 1],
    }
    final = deepcopy(blank)
    final["sheet_properties"][7] = 0
    transition = probe.require_linked_preferences(blank, final)
    assert transition["field"] == "ISheet.GetProperties2.sameCustomProp"
    assert transition["before"] == 1 and transition["after"] == 0
    assert blank["sheet_properties"][7] == 1
    for bad in (
        blank,
        dict(final, units={"system": 5}),
        dict(final, sheet_properties=final["sheet_properties"][:7]),
    ):
        with pytest.raises(RuntimeError):
            probe.require_linked_preferences(blank, bad)
    with pytest.raises(RuntimeError):
        probe.require_linked_preferences(final, final)


@pytest.mark.parametrize(
    "mode", ["pass", "wrong_view", "extra_view", "foreign_source", "configuration"]
)
def test_property_source_is_the_one_exact_owned_model_view(monkeypatch, tmp_path, mode):
    source = object()
    view = SimpleNamespace(
        GetName2=lambda: "Front",
        ReferencedDocument=object() if mode == "foreign_source" else source,
        ReferencedConfiguration="Other" if mode == "configuration" else "Default",
    )
    sheet = SimpleNamespace(
        CustomPropertyView="Other" if mode == "wrong_view" else "Front"
    )
    document = SimpleNamespace(GetCurrentSheet=lambda: sheet)
    adapter = SimpleNamespace(
        currentModel=document, swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b))
    )
    monkeypatch.setattr(probe.layout.cells, "required", lambda value, _: value)
    monkeypatch.setattr(
        probe.common,
        "iter_views",
        lambda _: iter([view, view] if mode == "extra_view" else [view]),
    )
    if mode != "pass":
        with pytest.raises(RuntimeError):
            probe.property_source(adapter, source, tmp_path / "owned.SLDPRT", "Default")
        return
    assert probe.property_source(
        adapter, source, tmp_path / "owned.SLDPRT", "Default"
    ) == {
        "view": "Front",
        "source": str(tmp_path / "owned.SLDPRT"),
        "configuration": "Default",
        "identity": "exact_native_source",
    }


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
    controller = probe.PopulatedControl(path, sha, Mock(), {})
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
    controller = probe.PopulatedControl(path, "0" * 64, Mock(), {})
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
    symbol_path = tmp_path / "gtol.sym"
    symbol_path.write_text(
        "#GGTOL,GOST\n*ANGULAR,Angularity\nA,LINE .0,.0,1.6,1.\nA,LINE .0,.0,1.6,.0\n"
    )
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
        asyncio.run(
            probe.probe(
                adapter, template, sha, sources, tmp_path / "reports", symbol_path
            )
        )
    else:
        with pytest.raises(ExceptionGroup):
            asyncio.run(
                probe.probe(
                    adapter, template, sha, sources, tmp_path / "reports", symbol_path
                )
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
    prefs = {
        "units": {"system": 4, "linear": 0, "decimals": 2},
        "sheet_properties": [2, 12, 1, 2, 0, 0.4318, 0.2794, 0],
    }
    monkeypatch.setattr(probe, "preferences", lambda _: deepcopy(prefs))
    monkeypatch.setattr(
        probe,
        "property_source",
        lambda *_: {"view": "Front", "identity": "exact_native_source"},
    )
    glyph = {"text": "REV", "characters": [{"text": "R", "box_pt": [1, 2, 3, 4]}]}
    monkeypatch.setattr(
        probe.fields,
        "field_audit",
        lambda *_args, **_kwargs: {
            "issues": [],
            "fields": {"label": {"pdf": deepcopy(glyph)}},
        },
    )
    controller = probe.PopulatedControl(
        tmp_path / "derived.DRWDOT", "0" * 64, Mock(), {}
    )
    controller.setup["normalized_blank_defaults"] = deepcopy(prefs)
    controller.setup["normalized_blank_defaults"]["sheet_properties"][7] = 1
    trial = {"source_copy": str(path), "source_before": {"configuration": "Default"}}
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
