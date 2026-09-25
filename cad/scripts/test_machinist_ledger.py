"""Offline contracts for the machinist-review ledger and its drift check.

The sheets are synthetic PDFs (pypdf content streams, PDF base-14 Helvetica),
rendered by the same PDFium path the real drawings go through, so every
fingerprint claim below is exercised end to end without SolidWorks.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

import machinist_ledger as ml
import machinist_review as mr

PT_PER_PX = 72.0 / ml.FINGERPRINT_DPI

NOTE = "ANCHOR DRILL: 6.5 DEEP (DO NOT BREAK THROUGH)."
# Verbatim from a real refused Codex attempt (dt-logs/swing-7980e977-render).
CODEX_REFUSAL = (
    '{"type":"error","message":"You\'ve hit your usage limit. Visit '
    'https://chatgpt.com/codex/settings/usage to purchase more credits or try again '
    'at Sep 26th, 2026 9:51 AM."}'
)


def _sheet(
    path: Path,
    *,
    revision: str = "v37",
    note: str = NOTE,
    extra_lines: tuple[tuple[float, float, str], ...] = (),
    edge_x: float = 40.0,
    producer: str = "first render",
) -> Path:
    """One drawing-like sheet: a view edge, a note, and the title-block revision."""
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=360, height=240)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    lines = ((30, 200, note), (300, 40, revision), (200, 15, f"BUILD {revision}"), *extra_lines)
    ops = [f"BT /F1 10 Tf {x} {y} Td ({text}) Tj ET" for x, y, text in lines]
    ops.append(f"1.5 w {edge_x} 60 m {edge_x} 180 l S")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(ops).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.add_metadata({"/Producer": producer})
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def _review(
    pdf: Path,
    *,
    name: str = "crank_arm",
    reviewer: str = "codex",
    passed: bool = True,
    effort: str = "low",
) -> dict:
    verdict = {
        "verdict": "SHIP" if passed else "FIX",
        "summary": "ready to make",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [{"where": "note 1", "issue": "wordy", "fix": "trim"}],
    }
    return asdict(
        mr.Review(
            name=name,
            kind="part",
            sources=[str(pdf)],
            source_sha256=[ml.sha256_file(pdf)],
            verdict=verdict,
            passed=passed,
            blind=True,
            tool_events=0,
            reviewer=reviewer,
            model="gpt-6-astra" if reviewer == "codex" else "claude-fable-5-1",
            effort=effort,
            prompt_sha256="a" * 64,
            sheet_count=1,
            duration_s=1.0,
            reviewed_at="2026-09-25T16:50:08+00:00",
        )
    )


@pytest.fixture
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the crank_arm registry row at a temp PDF path; return that path."""
    pdf = tmp_path / "out" / "crank-arm.pdf"
    pdf.parent.mkdir()
    monkeypatch.setitem(ml.DRAWINGS_BY_NAME, "crank_arm", SimpleNamespace(outputs={"pdf": pdf}))
    return pdf


# --- sheet content -------------------------------------------------------------------


def test_revision_and_byte_churn_do_not_move_the_fingerprint(tmp_path: Path) -> None:
    released = _sheet(tmp_path / "v37.pdf", revision="v37", producer="release")
    development = _sheet(tmp_path / "dev.pdf", revision="DEV", producer="farm worker 5")

    assert released.read_bytes() != development.read_bytes()
    assert ml.fingerprint(released) == ml.fingerprint(development)


def test_revision_mask_covers_only_whole_revision_lines(tmp_path: Path) -> None:
    # Positive control: a revision-looking token INSIDE a note is design content.
    base = _sheet(tmp_path / "a.pdf", extra_lines=((30, 150, "SEE v37 NOTES"),))
    edited = _sheet(tmp_path / "b.pdf", extra_lines=((30, 150, "SEE v38 NOTES"),))

    assert ml.fingerprint(base) != ml.fingerprint(edited)
    assert ml.residual(ml.masked_sheets(base)[0], ml.masked_sheets(edited)[0]) > 0


@pytest.mark.parametrize(
    ("released", "development"),
    [
        # Real DEV sheets join the stamp onto the title-block legend line.
        ("DO NOT SCALE DRAWING BUILD v37", "DO NOT SCALE DRAWING BUILD DEV"),
        # Older farm builds carry a build-number suffix.
        ("BUILD v37-b3843", "BUILD v38-b4102"),
    ],
)
def test_build_stamp_is_masked_wherever_the_text_layer_puts_it(
    tmp_path: Path, released: str, development: str
) -> None:
    a = _sheet(tmp_path / "a.pdf", extra_lines=((150, 110, released),))
    b = _sheet(tmp_path / "b.pdf", extra_lines=((150, 110, development),))
    assert ml.fingerprint(a) == ml.fingerprint(b)

    # Positive control: the text around the stamp is still content.
    edited = development.replace("BUILD", "BUILT BUILD")
    c = _sheet(tmp_path / "c.pdf", extra_lines=((150, 110, edited),))
    assert ml.fingerprint(c) != ml.fingerprint(b)


def test_one_character_note_edit_is_a_different_sheet(tmp_path: Path) -> None:
    base = _sheet(tmp_path / "base.pdf")
    twin = _sheet(tmp_path / "twin.pdf", producer="second render")
    for label, note in (("digit", NOTE.replace("6.5", "6.6")), ("punctuation", NOTE[:-1] + ",")):
        edited = _sheet(tmp_path / f"{label}.pdf", note=note)
        assert ml.fingerprint(edited) != ml.fingerprint(base), label
        assert ml.residual(ml.masked_sheets(base)[0], ml.masked_sheets(edited)[0]) > 0, label

    # Positive control: the same content rendered twice is identical.
    assert ml.fingerprint(twin) == ml.fingerprint(base)
    assert ml.residual(ml.masked_sheets(base)[0], ml.masked_sheets(twin)[0]) == 0


def test_tolerance_absorbs_a_one_pixel_shift_but_not_a_real_move(tmp_path: Path) -> None:
    base = ml.masked_sheets(_sheet(tmp_path / "base.pdf"))[0]
    nudged = ml.masked_sheets(_sheet(tmp_path / "nudged.pdf", edge_x=40.0 + PT_PER_PX))[0]
    moved = ml.masked_sheets(_sheet(tmp_path / "moved.pdf", edge_x=40.0 + 6 * PT_PER_PX))[0]

    assert ml.sheet_digest(nudged) != ml.sheet_digest(base)  # exact digest alone would fail
    assert ml.residual(base, nudged) == 0
    assert ml.residual(base, moved) > 0


def test_raster_round_trips_exactly(tmp_path: Path) -> None:
    import numpy as np

    ink = ml.masked_sheets(_sheet(tmp_path / "sheet.pdf"))[0]
    ml.save_raster(ink, tmp_path / "sheet.png")

    assert np.array_equal(ml.load_raster(tmp_path / "sheet.png"), ink)


# --- recording -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("reviewer", "author", "slot"),
    [
        ("codex", "claude", ml.CROSS_FAMILY),
        ("claude", "gpt", ml.CROSS_FAMILY),
        ("claude", "mimo", ml.CROSS_FAMILY),
        ("claude", "claude", ml.LAST_RESORT),
        ("codex", "gpt", ml.LAST_RESORT),
    ],
)
def test_slot_follows_reviewer_and_author_family(reviewer: str, author: str, slot: str) -> None:
    assert ml.review_slot(reviewer, author) == slot


def test_unknown_families_are_refused() -> None:
    with pytest.raises(ValueError, match="author family"):
        ml.review_slot("codex", "gemini")
    with pytest.raises(ValueError, match="reviewer"):
        ml.review_slot("gemini", "claude")


def test_record_keeps_the_verdict_and_every_reviewed_raster(tmp_path: Path, registry: Path) -> None:
    ledger_path = tmp_path / "reviews" / "machinist-ledger.json"
    pdf = _sheet(registry)

    recorded = ml.record_review(
        _review(pdf), pdf, author_family="claude", provenance={"head": "abc"}, ledger_path=ledger_path
    )

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry = ledger["drawings"]["crank_arm"][ml.CROSS_FAMILY]
    assert recorded.slot == ml.CROSS_FAMILY
    assert entry["sheets"] == ml.fingerprint(pdf) == list(recorded.sheets)
    assert (entry["reviewer_family"], entry["author_family"]) == ("gpt", "claude")
    assert entry["source_sha256"] == ml.sha256_file(pdf)
    assert entry["findings"] == {"blockers": 0, "over_specification": 0, "clarity": 0, "minor": 1}
    assert (ledger_path.parent / "sheets" / f"{entry['sheets'][0]}.png").is_file()


def test_only_the_exact_reviewed_pdf_of_a_passing_registry_review_is_recorded(
    tmp_path: Path, registry: Path
) -> None:
    ledger_path = tmp_path / "ledger.json"
    pdf = _sheet(registry)
    review = _review(pdf)
    kwargs = {"author_family": "claude", "provenance": {}, "ledger_path": ledger_path}

    with pytest.raises(ValueError, match="passing blind"):
        ml.record_review(_review(pdf, passed=False), pdf, **kwargs)
    with pytest.raises(ValueError, match="not a registry drawing"):
        ml.record_review({**review, "name": "not-a-drawing"}, pdf, **kwargs)
    with pytest.raises(ValueError, match="sheets, the review saw"):
        ml.record_review({**review, "sheet_count": 2}, pdf, **kwargs)
    _sheet(registry, producer="re-rendered after the review")
    with pytest.raises(ValueError, match="is not the reviewed"):
        ml.record_review(review, pdf, **kwargs)
    assert not ledger_path.exists()


def test_replacing_an_entry_prunes_rasters_nothing_references(tmp_path: Path, registry: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    first = _sheet(registry)
    ml.record_review(_review(first), first, author_family="claude", provenance={}, ledger_path=ledger_path)
    old = ml.fingerprint(first)[0]

    second = _sheet(registry, note=NOTE.replace("6.5", "6.6"))
    ml.record_review(_review(second), second, author_family="claude", provenance={}, ledger_path=ledger_path)

    rasters = {path.stem for path in (tmp_path / "sheets").glob("*.png")}
    assert rasters == set(ml.fingerprint(second))
    assert old not in rasters


def test_ingest_bootstraps_an_existing_verdict_json(tmp_path: Path, registry: Path) -> None:
    pdf = _sheet(registry)
    review = mr.Review(**_review(pdf))
    mr.write_review(review, tmp_path / "reports")
    ledger_path = tmp_path / "ledger.json"

    recorded = ml.ingest(
        tmp_path / "reports" / "crank_arm.json", author_family="claude", ledger_path=ledger_path
    )

    entry = ml.load_ledger(ledger_path)["drawings"]["crank_arm"][ml.CROSS_FAMILY]
    assert recorded.slot == ml.CROSS_FAMILY
    assert entry["provenance"]["ingested_from"].endswith("reports/crank_arm.json")
    assert ml.check(["crank_arm"], ledger_path=ledger_path)[0].state == ml.State.OK


def test_ledger_refuses_other_fingerprint_settings(tmp_path: Path) -> None:
    ledger = ml.empty_ledger()
    ledger["fingerprint"]["match_tolerance_px"] = 5
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(ledger), encoding="utf-8")

    with pytest.raises(ValueError, match="fingerprint settings"):
        ml.load_ledger(path)


# --- drift check ---------------------------------------------------------------------


def _recorded(tmp_path: Path, registry: Path, *, reviewer: str = "codex", author: str = "claude") -> Path:
    ledger_path = tmp_path / "ledger.json"
    pdf = _sheet(registry, producer="reviewed render")
    ml.record_review(
        _review(pdf, reviewer=reviewer), pdf, author_family=author, provenance={}, ledger_path=ledger_path
    )
    return ledger_path


def test_check_accepts_a_re_render_of_the_reviewed_sheet(tmp_path: Path, registry: Path) -> None:
    ledger_path = _recorded(tmp_path, registry)
    _sheet(registry, revision="DEV", producer="post-integration build")
    assert ml.check(["crank_arm"], ledger_path=ledger_path)[0].state == ml.State.OK

    # A sub-tolerance shift needs the stored raster, not the digest.
    _sheet(registry, edge_x=40.0 + PT_PER_PX)
    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]
    assert status.state == ml.State.OK


def test_check_reports_drift_when_the_sheet_changed_after_review(tmp_path: Path, registry: Path) -> None:
    ledger_path = _recorded(tmp_path, registry)
    _sheet(registry, note=NOTE[:-1] + ",")

    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]

    assert status.state == ml.State.DRIFT
    assert status.detail.startswith("sheet 1 (")
    assert "since codex/gpt-6-astra" in status.detail


def test_check_treats_a_missing_reference_raster_as_drift(tmp_path: Path, registry: Path) -> None:
    ledger_path = _recorded(tmp_path, registry)
    for raster in (tmp_path / "sheets").glob("*.png"):
        raster.unlink()
    _sheet(registry, edge_x=40.0 + PT_PER_PX)

    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]

    assert status.state == ml.State.DRIFT
    assert "reference raster missing" in status.detail


def _refused(tmp_path: Path, pdf: Path, *, name: str = "crank_arm", message: str = CODEX_REFUSAL) -> Path:
    """A codex report that returned no verdict, its refusal only in the attempt stdout."""
    stdout = tmp_path / "refused" / f"{name}.attempts" / "a1" / "stdout.txt"
    stdout.parent.mkdir(parents=True)
    stdout.write_text('{"type":"thread.started"}\n' + message + "\n", encoding="utf-8")
    review = mr.Review(
        **{
            **_review(pdf, name=name, passed=False),
            "verdict": None,
            "error": "RuntimeError: codex exit 1: ",
            "extra": {"evidence": {"attempts": [{"stdout_file": str(stdout), "stderr_file": None}]}},
        }
    )
    mr.write_review(review, tmp_path / "refused")
    return tmp_path / "refused" / f"{name}.json"


def test_quota_refusal_is_read_from_the_refused_attempt(tmp_path: Path) -> None:
    pdf = _sheet(tmp_path / "sheet.pdf")
    refusal = ml.quota_refusal(_refused(tmp_path, pdf), name="crank_arm", author_family="claude")

    assert refusal["message"] == CODEX_REFUSAL
    assert refusal["evidence_file"].endswith("a1/stdout.txt")
    assert (refusal["reviewer"], refusal["model"]) == ("codex", "gpt-6-astra")


def test_quota_refusal_needs_a_cross_family_usage_limit_for_the_same_drawing(tmp_path: Path) -> None:
    pdf = _sheet(tmp_path / "sheet.pdf")
    report = _refused(tmp_path, pdf)

    with pytest.raises(ValueError, match="not 'pen_rod'"):
        ml.quota_refusal(report, name="pen_rod", author_family="claude")
    with pytest.raises(ValueError, match="cross-family"):
        ml.quota_refusal(report, name="crank_arm", author_family="gpt")
    other = tmp_path / "other"
    other.mkdir()
    crashed = _refused(other, pdf, message='{"type":"error","message":"stream disconnected"}')
    with pytest.raises(ValueError, match="no usage-limit refusal"):
        ml.quota_refusal(crashed, name="crank_arm", author_family="claude")
    answered = tmp_path / "answered.json"
    answered.write_text(json.dumps(_review(pdf)), encoding="utf-8")
    with pytest.raises(ValueError, match="returned a verdict"):
        ml.quota_refusal(answered, name="crank_arm", author_family="claude")


@pytest.mark.parametrize(
    ("author", "reviewer", "effort", "counts"),
    [
        ("claude-opus-5-5", "claude-fable-5-1", "medium", True),
        ("gpt-6-sol", "gpt-6-astra", "low", True),
        ("claude-fable-5-1", "claude-fable-5-1", "high", True),
        ("claude-fable-5-1", "claude-fable-5-1", "xhigh", True),
        ("claude-fable-5-1", "claude-fable-5-1", "medium", False),  # same tier, not high
        ("claude-opus-5-5", "claude-opus-5-5", "high", False),  # same workhorse tier
        ("claude-sonnet-5", "claude-fable-5-1", "high", False),  # no tier for the author
        ("mimo-v2.6-pro", "claude-fable-5-1", "high", False),
    ],
)
def test_last_resort_tier_rule(author: str, reviewer: str, effort: str, counts: bool) -> None:
    assert (ml.last_resort_tier_problem(author, reviewer, effort) is None) == counts


def test_last_resort_counts_only_with_a_refusal_and_the_tier_rule(tmp_path: Path, registry: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    pdf = _sheet(registry)
    refusal = ml.quota_refusal(_refused(tmp_path, pdf), name="crank_arm", author_family="claude")
    fable = _review(pdf, reviewer="claude", effort="medium")
    base = {"author_family": "claude", "provenance": {}, "ledger_path": ledger_path}

    recorded = ml.record_review(fable, pdf, author_model="claude-opus-5-5", **base)
    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]
    assert not recorded.counts
    assert (status.state, status.last_resort) == (ml.State.UNREVIEWED, "matches")
    assert "no recorded quota refusal" in status.detail

    ml.record_review(fable, pdf, author_model="claude-fable-5-1", refusal=refusal, **base)
    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]
    assert status.state == ml.State.UNREVIEWED
    assert "high effort" in status.detail

    recorded = ml.record_review(fable, pdf, author_model="claude-opus-5-5", refusal=refusal, **base)
    entry = ml.load_ledger(ledger_path)["drawings"]["crank_arm"][ml.LAST_RESORT]
    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]
    assert recorded.counts and entry["counts"]
    assert entry["quota_refusal"]["message"] == refusal["message"]
    assert (entry["author_model"], entry["not_counted_because"]) == ("claude-opus-5-5", None)
    assert status.state == ml.State.OK
    assert status.detail.startswith("last-resort claude/claude-fable-5-1")

    # A counting last resort still has to match the sheet now shipping.
    _sheet(registry, note=NOTE[:-1] + ",")
    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]
    assert (status.state, status.last_resort) == (ml.State.UNREVIEWED, "drift")


def test_cross_family_drift_is_covered_by_a_counting_last_resort(tmp_path: Path, registry: Path) -> None:
    ledger_path = _recorded(tmp_path, registry)
    edited = _sheet(registry, note=NOTE[:-1] + ",")
    assert ml.check(["crank_arm"], ledger_path=ledger_path)[0].state == ml.State.DRIFT

    refusal = ml.quota_refusal(_refused(tmp_path, edited), name="crank_arm", author_family="claude")
    ml.record_review(
        _review(edited, reviewer="claude"),
        edited,
        author_family="claude",
        author_model="claude-opus-5-5",
        refusal=refusal,
        provenance={},
        ledger_path=ledger_path,
    )
    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]
    assert (status.state, status.last_resort) == (ml.State.OK, "matches")


def test_ingest_records_a_last_resort_with_its_refusal(tmp_path: Path, registry: Path, capsys) -> None:
    pdf = _sheet(registry)
    mr.write_review(mr.Review(**_review(pdf, reviewer="claude")), tmp_path / "reports")
    refused = _refused(tmp_path, pdf)
    ledger = str(tmp_path / "ledger.json")
    report = str(tmp_path / "reports" / "crank_arm.json")

    assert ml.main(["--ledger", ledger, "ingest", report, "--author-family", "claude"]) == 0
    assert "does NOT count" in capsys.readouterr().out
    assert ml.main(["--ledger", ledger, "check", "crank_arm"]) == 1

    argv = ["--author-model", "claude-opus-5-5", "--quota-refusal", str(refused)]
    assert ml.main(["--ledger", ledger, "ingest", report, "--author-family", "claude", *argv]) == 0
    assert "does NOT count" not in capsys.readouterr().out
    assert ml.main(["--ledger", ledger, "check", "crank_arm"]) == 0


def test_check_names_unrendered_and_unknown_drawings(tmp_path: Path, registry: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    assert ml.check(["crank_arm"], ledger_path=ledger_path)[0].state == ml.State.UNRENDERED
    with pytest.raises(ValueError, match="unknown drawing names"):
        ml.check(["not-a-drawing"], ledger_path=ledger_path)


def test_cli_exit_status_is_the_gate(tmp_path: Path, registry: Path, capsys) -> None:
    ledger = str(tmp_path / "ledger.json")
    assert ml.main(["--ledger", ledger, "check", "crank_arm"]) == 1
    assert ml.main(["--ledger", ledger, "check", "crank_arm", "--allow-unrendered"]) == 0

    _sheet(registry)
    assert ml.main(["--ledger", ledger, "check", "crank_arm"]) == 1
    assert "unreviewed" in capsys.readouterr().out

    ml.record_review(
        _review(registry), registry, author_family="claude", provenance={}, ledger_path=Path(ledger)
    )
    assert ml.main(["--ledger", ledger, "check", "crank_arm", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["state"] == "ok"

    assert ml.main(["--ledger", ledger, "check", "not-a-drawing"]) == 2
    assert "unknown drawing names" in capsys.readouterr().err


# --- machinist_review integration ----------------------------------------------------


def test_review_run_requires_a_cross_family_author(capsys) -> None:
    assert mr.main(["--reviewer", "codex", "crank_arm"]) == 2
    assert "--author-family is required" in capsys.readouterr().err

    assert mr.main(["--reviewer", "codex", "--author-family", "gpt", "crank_arm"]) == 2
    assert "same family" in capsys.readouterr().err

    assert mr.main(["--reviewer", "codex", "--author-family", "claude", "--last-resort", "crank_arm"]) == 2
    assert "only to a same-family review" in capsys.readouterr().err


def test_last_resort_run_is_refused_before_any_reviewer_runs(
    tmp_path: Path, registry: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    pdf = _sheet(registry)
    refused = _refused(tmp_path, pdf)
    monkeypatch.setattr(mr, "review_package", lambda *a, **k: pytest.fail("reviewer ran"))
    same = ["--reviewer", "claude", "--author-family", "claude", "--last-resort"]
    evidence = ["--author-model", "claude-opus-5-5", "--quota-refusal", str(refused)]
    fable_author = ["--author-model", "claude-fable-5-1", "--quota-refusal", str(refused)]
    reports = ["--report-dir", str(tmp_path / "reports")]

    cases = [
        ([*same, "crank_arm", *reports], "needs --author-model and --quota-refusal"),
        ([*same, "--all", *evidence, *reports], "exactly one registry drawing"),
        ([*same, "pen_rod", *evidence, *reports], "not 'pen_rod'"),
        ([*same, "crank_arm", *fable_author, *reports], "high effort"),
        ([*same, "crank_arm", *evidence, "--report-dir", str(tmp_path / "refused")], "overwrites"),
    ]
    for argv, message in cases:
        assert mr.main(argv) == 2, message
        assert message in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argv", "slot"),
    [
        (["--reviewer", "codex", "--author-family", "claude"], ml.CROSS_FAMILY),
        (
            ["--reviewer", "claude", "--author-family", "claude", "--last-resort",
             "--author-model", "claude-opus-5-5", "--quota-refusal", "REFUSED"],
            ml.LAST_RESORT,
        ),
    ],
)
def test_passing_review_run_records_the_ledger(
    tmp_path: Path, registry: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str], slot: str
) -> None:
    pdf = _sheet(registry)
    reviewer = argv[1]
    argv = [str(_refused(tmp_path, pdf)) if arg == "REFUSED" else arg for arg in argv]

    def fake_review(package, **kwargs):
        assert package.sources == (pdf,)
        return mr.Review(**_review(pdf, reviewer=reviewer))

    monkeypatch.setattr(mr, "package_for", lambda name: mr.ReviewPackage(name, "part", (pdf,)))
    monkeypatch.setattr(mr, "review_package", fake_review)
    ledger_path = tmp_path / "ledger.json"

    code = mr.main(
        [*argv, "crank_arm", "--ledger", str(ledger_path), "--report-dir", str(tmp_path / "reports")]
    )

    assert code == 0
    entry = ml.load_ledger(ledger_path)["drawings"]["crank_arm"]
    assert list(entry) == [slot]
    assert entry[slot]["counts"]
    assert ml.check(["crank_arm"], ledger_path=ledger_path)[0].state == ml.State.OK


def test_review_run_fails_when_the_pdf_changed_before_it_could_be_recorded(
    tmp_path: Path, registry: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    pdf = _sheet(registry)

    def fake_review(package, **kwargs):
        review = mr.Review(**_review(pdf))
        _sheet(registry, producer="a concurrent build rewrote it")
        return review

    monkeypatch.setattr(mr, "package_for", lambda name: mr.ReviewPackage(name, "part", (pdf,)))
    monkeypatch.setattr(mr, "review_package", fake_review)
    ledger_path = tmp_path / "ledger.json"

    code = mr.main(
        ["--reviewer", "codex", "--author-family", "claude", "crank_arm",
         "--ledger", str(ledger_path), "--report-dir", str(tmp_path / "reports")]
    )

    assert code == 1
    assert "not recorded in the ledger" in capsys.readouterr().err
    assert not ledger_path.exists()


def test_no_build_task_reads_the_ledger() -> None:
    """Recording a review must never re-key a build: only these tools import it."""
    readers = {
        path.name
        for path in [*ml.SCRIPTS_DIR.rglob("*.py"), ml.REPO_ROOT / "dodo.py"]
        if "machinist_ledger" in path.read_text(encoding="utf-8")
        or "machinist-ledger" in path.read_text(encoding="utf-8")
    }
    assert readers == {"machinist_ledger.py", "machinist_review.py", "test_machinist_ledger.py"}
