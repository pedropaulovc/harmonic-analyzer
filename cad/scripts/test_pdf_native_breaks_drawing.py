"""PDFium layout separators are not permission to replace any printed text."""

from copy import deepcopy

import pytest

from diagnostics import _populated_template_fields as fields
from diagnostics._pdf_native_break_fixture import RETAINED


def test_actual_finish_requires_two_generated_zero_ink_crlf_at_native_run_break():
    note, pdf = deepcopy(RETAINED["note"]), deepcopy(RETAINED["pdf"])
    original = deepcopy(pdf)
    assert len(note["text"]) == 61 and len(pdf["text"]) == 63
    assert pdf["text"] != note["text"]
    witness = fields.native_run_breaks(note, pdf)
    assert witness["text"] == note["text"]
    assert witness["separators"] == [
        {"after_native_run": 0, "character_indices": [47, 48]}
    ]
    assert pdf == original  # Raw text, every character and all boxes stay intact.
    box = tuple(value * 0.0254 / 72 for value in pdf["ink_box_pt"])
    fields.layout.cells.require_box(RETAINED["region_m"], box, "actual FINISH PDF")


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "substitute",
        "extra",
        "order",
        "space",
        "boundary",
        "not_generated",
        "unknown_generated",
        "ink",
        "missing_character",
        "native_text",
        "native_count",
        "native_rotation",
        "native_same_line",
        "native_nonfinite",
        "character_text",
    ],
)
def test_native_run_reconciliation_never_waives_unproved_text_or_separator(fault):
    note, pdf = deepcopy(RETAINED["note"]), deepcopy(RETAINED["pdf"])
    if fault == "missing":
        pdf["text"] = pdf["text"].replace("bores", "bore")
    if fault == "substitute":
        pdf["text"] = pdf["text"].replace("6005", "6006")
    if fault == "extra":
        pdf["text"] += "x"
    if fault == "order":
        note["display"]["texts"].reverse()
    if fault == "space":
        pdf["text"] = pdf["text"].replace("; \r\n", ";\r\n")
    if fault == "boundary":
        pdf["text"] = pdf["text"].replace("; \r\nmask", "; mask\r\n")
    if fault in {"not_generated", "unknown_generated"}:
        pdf["characters"][47]["generated"] = 0 if fault == "not_generated" else -1
    if fault == "ink":
        pdf["characters"][47]["box_pt"][2] += 0.01
    if fault == "missing_character":
        pdf["characters"].pop()
    if fault == "native_text":
        note["text"] = note["text"].replace("6005", "6006")
    if fault == "native_count":
        note["display"]["counts"]["Text"] = 3
    if fault == "native_rotation":
        note["display"]["texts"][0]["angle_rad"] = 0.1
    if fault == "native_same_line":
        note["display"]["texts"][1]["position"][1] = note["display"]["texts"][0][
            "position"
        ][1]
    if fault == "native_nonfinite":
        note["display"]["texts"][1]["position"][1] = float("nan")
    if fault == "character_text":
        pdf["characters"][-1]["text"] = "x"
    with pytest.raises(RuntimeError):
        fields.native_run_breaks(note, pdf)


@pytest.mark.parametrize("fault", ["fit", "collision"])
def test_reconciled_finish_keeps_existing_full_cell_and_pairwise_ink_gates(fault):
    from test_populated_template_drawing import populated

    notes, lines, original_pdf = populated()
    finish = notes["finish"]
    # Preserve the actual text/runs, using the already measured synthetic cell
    # only to isolate the unchanged fit/collision predicates.
    finish.update(
        text=RETAINED["note"]["text"], display=deepcopy(RETAINED["note"]["display"])
    )
    note = deepcopy(finish)
    pdf = deepcopy(RETAINED["pdf"])
    pdf["ink_box_pt"] = [value * 72 / 0.0254 for value in (0.205, 0.036, 0.225, 0.039)]
    if fault == "fit":
        pdf["ink_box_pt"][2] = 0.28 * 72 / 0.0254
    if fault == "collision":
        pdf["ink_box_pt"] = [
            value * 72 / 0.0254 for value in (0.205, 0.021, 0.225, 0.024)
        ]
    result = fields.field_audit(
        notes,
        lines,
        pdf_reader=lambda text: pdf if text == note["text"] else original_pdf(text),
    )
    assert result["status"] == "failed"
    assert result["fields"]["finish"]["text_representation"]["text"] == note["text"]
    assert any(
        "fit" in issue["kind"] or "clearance" in issue["kind"]
        for issue in result["issues"]
    )


@pytest.mark.parametrize(
    "fault", [None, "receipt", "source", "copy", "raw_text", "raw_ink", "inventory"]
)
def test_complete_replay_keeps_hashes_field_inventory_and_prior_raw_pdf_exact(
    tmp_path, monkeypatch, fault
):
    import hashlib
    import json
    from diagnostics import _populated_template_symbols as symbols
    from test_populated_template_drawing import populated

    def file(name, data):
        path = tmp_path / name
        path.write_bytes(data)
        return str(path)

    def digest(path):
        from pathlib import Path

        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    source = file("source.SLDPRT", b"source")
    copied = file("copy.SLDPRT", b"source")
    library = file(
        "gtol.sym",
        b"#GGTOL,GOST\n*ANGULAR,Angularity\nA,LINE .0,.0,1.6,1.\nA,LINE .0,.0,1.6,.0\n",
    )
    notes, lines, pdf_reader = populated()
    fit = fields.field_audit(notes, lines, pdf_reader=pdf_reader)
    observation = {
        "notes": notes,
        "template_geometry": {
            "segments": [
                {"kind": 0, "role": "drawing", "sheet_points": line} for line in lines
            ]
        },
        "fit": fit,
    }
    artifacts = {
        kind: file("built." + kind, b"owned") for kind in ("drawing", "pdf", "png")
    }
    cold = {kind: file("cold." + kind, b"owned") for kind in ("pdf", "png")}
    expected = {source: digest(source), library: digest(library)}
    report = {
        "status": "failed",
        "inputs_before": expected,
        "inputs_after": expected,
        "trials": [
            {
                "target": "part",
                "source_copy": copied,
                "copy_hashes": {"initial": digest(copied), "final": digest(copied)},
                "artifacts": artifacts,
                "cold_artifacts": cold,
                "linked_fields": {
                    "built": deepcopy(observation),
                    "cold": deepcopy(observation),
                },
                "acceptance_issues": [],
            }
        ],
    }
    if fault == "copy":
        report["trials"][0]["copy_hashes"]["final"] = "wrong"
    if fault in {"raw_text", "raw_ink"}:
        raw = report["trials"][0]["linked_fields"]["cold"]["fit"]["fields"]["title"][
            "pdf"
        ]
        if fault == "raw_text":
            raw["text"] = "different"
        else:
            raw["ink_box_pt"][0] += 1
    if fault == "inventory":
        report["trials"][0]["linked_fields"]["cold"]["fit"]["fields"]["extra"] = {}
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(report), encoding="utf-8")
    sha = digest(receipt)
    if fault == "receipt":
        sha = "wrong"
    if fault == "source":
        file("source.SLDPRT", b"changed")
    calls = []

    def reader(path, text):
        calls.append(str(path))
        return dict(
            pdf_reader(text),
            characters=[
                dict(row, generated=0) for row in pdf_reader(text)["characters"]
            ],
        )

    monkeypatch.setattr(symbols.retained, "pdf_title", reader)
    if fault is not None:
        with pytest.raises(RuntimeError):
            fields.audit_retained(receipt, sha, tmp_path / "gtol.sym")
        return
    result = fields.audit_retained(receipt, sha, tmp_path / "gtol.sym")
    assert result["status"] == "passed"
    assert result["inputs_before"] == result["inputs_after"]
    assert set(calls) == {artifacts["pdf"], cold["pdf"]}
    assert all(
        phase["fit"]["status"] == "passed"
        for phase in result["targets"]["part"].values()
    )
