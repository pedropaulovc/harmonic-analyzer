"""Offline contracts for the machinist-review ledger and its drift check.

The sheets are synthetic PDFs (pypdf content streams, PDF base-14 Helvetica),
rendered by the same PDFium path the real drawings go through, so every
fingerprint claim below is exercised end to end without SolidWorks.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import machinist_ledger as ml
import machinist_review as mr

PT_PER_PX = 72.0 / ml.FINGERPRINT_DPI
PT_PER_MM = 1 / ml.MM_PER_PT

NOTE = "ANCHOR DRILL \xd86.5 X 13 DEEP (DO NOT BREAK THROUGH)."
# Verbatim from a real refused Codex attempt (dt-logs/swing-7980e977-render).
CODEX_REFUSAL = (
    '{"type":"error","message":"You\'ve hit your usage limit. Visit '
    "https://chatgpt.com/codex/settings/usage to purchase more credits or try again "
    'at Sep 26th, 2026 9:51 AM."}'
)
NOW = datetime.now(timezone.utc).replace(microsecond=0)
REVIEWED_AT = NOW.isoformat()
REFUSED_AT = (NOW - timedelta(hours=1)).isoformat()


def _sheet(
    path: Path,
    *,
    revision: str = "v37",
    note: str = NOTE,
    size: float = 10,
    note_x: float = 30.0,
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
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    ops = [f"BT /F1 {size} Tf {note_x} 200 Td ({note}) Tj ET"]
    lines = ((300, 40, revision), (200, 15, f"BUILD {revision}"), *extra_lines)
    ops += [f"BT /F1 10 Tf {x} {y} Td ({text}) Tj ET" for x, y, text in lines]
    ops.append(f"1.5 w {edge_x} 60 m {edge_x} 180 l S")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(ops).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.add_metadata({"/Producer": producer})
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def _verdict(passed: bool = True) -> dict:
    return {
        "verdict": "SHIP" if passed else "FIX",
        "summary": "ready to make" if passed else "two notes the shop does not need",
        "blockers": [],
        "over_specification": []
        if passed
        else [
            {
                "where": "note 2",
                "issue": "band repeats the title block",
                "fix": "drop it",
            },
            {
                "where": "datum A",
                "issue": "datum scheme on a hand part",
                "fix": "drop it",
            },
        ],
        "clarity": [],
        "minor": [{"where": "note 1", "issue": "wordy", "fix": "trim"}],
    }


def _review(
    pdf: Path,
    *,
    name: str = "crank_arm",
    reviewer: str = "codex",
    passed: bool = True,
    effort: str = "low",
    reviewed_at: str = REVIEWED_AT,
) -> dict:
    return asdict(
        mr.Review(
            name=name,
            kind="part",
            sources=[str(pdf)],
            source_sha256=[ml.sha256_file(pdf)],
            verdict=_verdict(passed),
            passed=passed,
            blind=True,
            tool_events=0,
            reviewer=reviewer,
            model="gpt-6-astra" if reviewer == "codex" else "claude-fable-5-1",
            effort=effort,
            prompt_sha256="a" * 64,
            sheet_count=1,
            duration_s=1.0,
            reviewed_at=reviewed_at,
        )
    )


@pytest.fixture
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the crank_arm registry row at a temp PDF path; return that path.

    The draw script's commit names no model unless a test sets one with
    ``_trailer``.
    """
    pdf = tmp_path / "out" / "crank-arm.pdf"
    pdf.parent.mkdir()
    row = SimpleNamespace(outputs={"pdf": pdf}, script_name="draw_crank_arm.py")
    monkeypatch.setitem(ml.DRAWINGS_BY_NAME, "crank_arm", row)
    _trailer(monkeypatch, None)
    return pdf


def _trailer(monkeypatch: pytest.MonkeyPatch, model: str | None) -> None:
    author = ml.Author(model, "c" * 40, "cad/scripts/draw_crank_arm.py")
    monkeypatch.setattr(ml, "draw_script_author", lambda name: author)
    monkeypatch.setattr(
        ml, "draw_script_authors", lambda names: {n: author for n in names}
    )


def _only(pdf: Path) -> ml.Sheet:
    return ml.read_sheets(pdf)[0]


# --- sheet content -------------------------------------------------------------------


def test_revision_and_byte_churn_do_not_move_the_fingerprint(tmp_path: Path) -> None:
    released = _sheet(tmp_path / "v37.pdf", revision="v37", producer="release")
    development = _sheet(tmp_path / "dev.pdf", revision="DEV", producer="farm worker 5")

    assert released.read_bytes() != development.read_bytes()
    assert ml.fingerprint(released) == ml.fingerprint(development)
    assert _only(released).text == _only(development).text


def test_revision_mask_covers_only_whole_revision_lines(tmp_path: Path) -> None:
    # Positive control: a revision-looking token INSIDE a note is design content.
    base = _sheet(tmp_path / "a.pdf", extra_lines=((30, 150, "SEE v37 NOTES"),))
    edited = _sheet(tmp_path / "b.pdf", extra_lines=((30, 150, "SEE v38 NOTES"),))

    assert ml.fingerprint(base) != ml.fingerprint(edited)
    assert ml.text_difference(_only(base).text, _only(edited).text)


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
    assert _only(a).text == _only(b).text

    # Positive control: the text around the stamp is still content.
    edited = development.replace("BUILD", "BUILT BUILD")
    c = _sheet(tmp_path / "c.pdf", extra_lines=((150, 110, edited),))
    assert ml.fingerprint(c) != ml.fingerprint(b)


def test_re_render_of_the_same_sheet_matches(tmp_path: Path) -> None:
    base = _only(_sheet(tmp_path / "base.pdf"))
    twin = _only(_sheet(tmp_path / "twin.pdf", producer="second render"))
    nudged = _only(_sheet(tmp_path / "nudged.pdf", edge_x=40.0 + PT_PER_PX))

    assert ml.sheet_digest(twin.ink) == ml.sheet_digest(base.ink)
    assert ml.sheet_digest(nudged.ink) != ml.sheet_digest(
        base.ink
    )  # the digest alone would fail
    assert ml.sheet_difference(base, twin, index=1) is None
    assert ml.sheet_difference(base, nudged, index=1) is None


def test_a_real_geometry_move_is_a_different_sheet(tmp_path: Path) -> None:
    base = _only(_sheet(tmp_path / "base.pdf"))
    moved = _only(_sheet(tmp_path / "moved.pdf", edge_x=40.0 + 6 * PT_PER_PX))

    difference = ml.sheet_difference(base, moved, index=1)

    assert difference is not None and difference.pixels > 0
    assert not difference.text  # geometry is the raster's job


@pytest.mark.parametrize(
    ("label", "kwargs"),
    [
        ("decimal point dropped", {"note": NOTE.replace("6.5", "65")}),
        ("3 read as 8", {"note": NOTE.replace("13", "18")}),
        ("diameter sign removed", {"note": NOTE.replace("\xd8", "")}),
        ("note moved 0.3 mm", {"note_x": 30.0 + 0.3 * PT_PER_MM}),
        ("comma for a full stop", {"note": NOTE[:-1] + ","}),
    ],
)
@pytest.mark.parametrize("size", [10, 3.5])
def test_planted_note_edits_are_different_sheets(
    tmp_path: Path, label: str, kwargs: dict, size: float
) -> None:
    base = _only(_sheet(tmp_path / "base.pdf", size=size))
    edited = _only(_sheet(tmp_path / "edited.pdf", size=size, **kwargs))

    difference = ml.sheet_difference(base, edited, index=1)

    assert difference is not None, label
    assert difference.text, label


def test_the_text_layer_catches_what_the_ink_tolerance_cannot(tmp_path: Path) -> None:
    # At 3.5 pt a 3 -> 8 swap leaves no ink more than 2 px from the original.
    base = _only(_sheet(tmp_path / "base.pdf", size=3.5))
    edited = _only(
        _sheet(tmp_path / "edited.pdf", size=3.5, note=NOTE.replace("13", "18"))
    )

    assert ml.residual(base.ink, edited.ink) == 0
    difference = ml.sheet_difference(base, edited, index=1)
    assert difference is not None and difference.pixels == 0
    assert any("18 DEEP" in line for line in difference.text)


def test_text_positions_tolerate_render_noise_but_not_a_move(tmp_path: Path) -> None:
    # 0.06 mm is the largest wobble measured between noise-only renders.
    base = _only(_sheet(tmp_path / "base.pdf"))
    wobble = _only(_sheet(tmp_path / "wobble.pdf", note_x=30.0 + 0.06 * PT_PER_MM))
    nudge = _only(_sheet(tmp_path / "nudge.pdf", note_x=30.0 + 0.15 * PT_PER_MM))
    moved = _only(_sheet(tmp_path / "moved.pdf", note_x=30.0 + 0.3 * PT_PER_MM))

    assert ml.text_difference(base.text, wobble.text) == []
    assert ml.text_difference(base.text, nudge.text)
    assert ml.text_difference(base.text, moved.text) == [
        f"~ {NOTE!r} moved (+0.30, +0.00) mm at (10.88, 69.82) mm"
    ]


def test_diff_shows_leftover_pixels_in_red_and_the_text_change(tmp_path: Path) -> None:
    import numpy as np
    from PIL import Image

    base = _only(_sheet(tmp_path / "base.pdf"))
    edited = _only(_sheet(tmp_path / "edited.pdf", note=NOTE.replace("6.5", "65")))
    difference = ml.sheet_difference(base, edited, index=1)

    files = ml.write_diff("crank_arm", [difference], [edited], tmp_path / "report")

    image = np.array(Image.open(tmp_path / "report" / "crank_arm-sheet1-diff.png"))
    red = (image[..., 0] == 220) & (image[..., 1] == 0)
    assert int(red.sum()) == difference.pixels
    text = (tmp_path / "report" / "crank_arm-diff.txt").read_text(encoding="utf-8")
    assert "+ 'ANCHOR DRILL Ø65 X 13" in text
    assert [path.name for path in files] == [
        "crank_arm-sheet1-diff.png",
        "crank_arm-diff.txt",
    ]


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
def test_slot_follows_reviewer_and_author_family(
    reviewer: str, author: str, slot: str
) -> None:
    assert ml.review_slot(reviewer, author) == slot


def test_unknown_families_are_refused() -> None:
    with pytest.raises(ValueError, match="author family"):
        ml.review_slot("codex", "gemini")
    with pytest.raises(ValueError, match="reviewer"):
        ml.review_slot("gemini", "claude")


def test_record_keeps_the_verdict_and_the_reviewed_pdf(
    tmp_path: Path, registry: Path
) -> None:
    ledger_path = tmp_path / "reviews" / "machinist-ledger.json"
    pdf = _sheet(registry)

    recorded = ml.record_review(
        _review(pdf),
        pdf,
        author_family="claude",
        provenance={"head": "abc"},
        ledger_path=ledger_path,
    )

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry = ledger["drawings"]["crank_arm"][ml.CROSS_FAMILY]
    assert (recorded.slot, recorded.status, entry["status"]) == (
        ml.CROSS_FAMILY,
        ml.SHIP,
        ml.SHIP,
    )
    assert entry["sheets"] == ml.fingerprint(pdf) == list(recorded.sheets)
    assert entry["pdf"] == ml.sha256_file(pdf)
    assert (
        ledger_path.parent / "sheets" / f"{entry['pdf']}.pdf"
    ).read_bytes() == pdf.read_bytes()
    assert entry["reviewer_family"] == "gpt"
    assert entry["author"] == {
        "family": "claude",
        "model": None,
        "model_source": "claimed",
        "commit": "c" * 40,
        "script": "cad/scripts/draw_crank_arm.py",
    }
    assert entry["findings"] == {
        "blockers": 0,
        "over_specification": 0,
        "clarity": 0,
        "minor": 1,
    }
    assert entry["renderer"].startswith("pypdfium2 ")


def test_only_the_exact_reviewed_pdf_of_an_accepted_registry_review_is_recorded(
    tmp_path: Path, registry: Path
) -> None:
    ledger_path = tmp_path / "ledger.json"
    pdf = _sheet(registry)
    review = _review(pdf)
    kwargs = {"author_family": "claude", "provenance": {}, "ledger_path": ledger_path}

    with pytest.raises(
        ValueError, match="only a passing review, or one with rebuttals"
    ):
        ml.record_review(_review(pdf, passed=False), pdf, **kwargs)
    with pytest.raises(ValueError, match="blind review"):
        ml.record_review({**review, "blind": False}, pdf, **kwargs)
    with pytest.raises(ValueError, match="not a registry drawing"):
        ml.record_review({**review, "name": "not-a-drawing"}, pdf, **kwargs)
    with pytest.raises(ValueError, match="sheets, the review saw"):
        ml.record_review({**review, "sheet_count": 2}, pdf, **kwargs)
    _sheet(registry, producer="re-rendered after the review")
    with pytest.raises(ValueError, match="is not the reviewed"):
        ml.record_review(review, pdf, **kwargs)
    assert not ledger_path.exists()


def test_replacing_an_entry_prunes_pdfs_nothing_references(
    tmp_path: Path, registry: Path
) -> None:
    ledger_path = tmp_path / "ledger.json"
    first = _sheet(registry)
    ml.record_review(
        _review(first),
        first,
        author_family="claude",
        provenance={},
        ledger_path=ledger_path,
    )
    old = ml.sha256_file(first)

    second = _sheet(registry, note=NOTE.replace("6.5", "6.6"))
    ml.record_review(
        _review(second),
        second,
        author_family="claude",
        provenance={},
        ledger_path=ledger_path,
    )

    stored = {path.stem for path in (tmp_path / "sheets").glob("*.pdf")}
    assert stored == {ml.sha256_file(second)}
    assert old not in stored


def test_ingest_bootstraps_an_existing_verdict_json(
    tmp_path: Path, registry: Path
) -> None:
    pdf = _sheet(registry)
    mr.write_review(mr.Review(**_review(pdf)), tmp_path / "reports")
    ledger_path = tmp_path / "ledger.json"

    recorded = ml.ingest(
        tmp_path / "reports" / "crank_arm.json",
        author_family="claude",
        ledger_path=ledger_path,
    )

    entry = ml.load_ledger(ledger_path)["drawings"]["crank_arm"][ml.CROSS_FAMILY]
    assert recorded.slot == ml.CROSS_FAMILY
    assert entry["provenance"]["ingested_from"].endswith("reports/crank_arm.json")
    assert ml.check(["crank_arm"], ledger_path=ledger_path)[0].state == ml.State.OK


def test_ledger_refuses_other_fingerprint_settings(tmp_path: Path) -> None:
    ledger = ml.empty_ledger()
    ledger["fingerprint"]["text_position_tolerance_mm"] = 0.5
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(ledger), encoding="utf-8")

    with pytest.raises(ValueError, match="fingerprint settings"):
        ml.load_ledger(path)


# --- author --------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _commit(repo: Path, script: Path, body: str) -> None:
    script.write_text(body.splitlines()[0] + "\n", encoding="utf-8")
    _git(repo, "add", script.name)
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        "commit",
        "-q",
        "-m",
        body,
    )


def test_author_model_comes_from_the_draw_scripts_commit_trailer(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    script = repo / "draw_crank_arm.py"

    _commit(
        repo,
        script,
        "draw: crank arm\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
    )
    assert ml.script_author(script, repo=repo).model == "claude-opus-5-5"

    _commit(repo, script, "draw: tidy\n\nCo-Authored-By: Pedro <pedro@example.com>")
    assert (
        ml.script_author(script, repo=repo).model is None
    )  # a human co-author names no model

    _commit(
        repo,
        script,
        "draw: pair\n\nCo-Authored-By: Claude Opus 5.5 <a@b>\nCo-Authored-By: GPT-6 Sol <c@d>",
    )
    with pytest.raises(ValueError, match="several models"):
        ml.script_author(script, repo=repo)

    # The batch form answers every script in a fixed number of git calls.
    other = repo / "draw_pen_rod.py"
    _commit(
        repo, other, "draw: pen rod\n\nCo-Authored-By: GPT-6 Sol <noreply@openai.com>"
    )
    batch = ml.script_authors([script, other, repo / "draw_never.py"], repo=repo)
    assert isinstance(batch[script], ValueError)
    assert batch[other].model == "gpt-6-sol"
    assert "has no commit" in str(batch[repo / "draw_never.py"])

    script.write_text("edited, not committed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="uncommitted"):
        ml.script_author(script, repo=repo)


def _repo_with_history(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Old commits, then the draw script's trailered commit on top of them."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _commit(repo, repo / "README", "base")
    old = repo / "draw_pen_rod.py"
    _commit(
        repo, old, "draw: pen rod\n\nCo-Authored-By: GPT-6 Sol <noreply@openai.com>"
    )
    script = repo / "draw_crank_arm.py"
    _commit(
        repo,
        script,
        "draw: crank arm\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
    )
    return repo, script, old


def test_the_author_walk_stops_at_each_scripts_latest_commit(tmp_path: Path) -> None:
    repo, script, _ = _repo_with_history(tmp_path)
    base = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD~2"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    # Older objects missing, as in a partial clone: a walk past the latest
    # commit that touched the script would fail on them.
    obj = repo / ".git" / "objects" / base[:2] / base[2:]
    obj.chmod(0o666)  # git writes loose objects read-only
    obj.unlink()

    author = ml.script_author(script, repo=repo)

    assert author.model == "claude-opus-5-5"


def test_a_shallow_clone_names_no_author_instead_of_erroring(tmp_path: Path) -> None:
    repo, script, old = _repo_with_history(tmp_path)
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", repo.resolve().as_uri(), str(clone)],
        check=True,
        capture_output=True,
    )

    authors = ml.script_authors([clone / script.name, clone / old.name], repo=clone)

    # The depth-1 root diffs against nothing, so it lists every file whether or
    # not it touched them: pen_rod's GPT commit is past the boundary and must
    # not read as HEAD's Claude trailer, and nothing tells crank_arm apart.
    for path in (clone / script.name, clone / old.name):
        missing = authors[path]
        assert isinstance(missing, ValueError)
        assert "shallow" in str(missing)
    status = ml.Status("crank_arm", ml.State.UNREVIEWED, "", "", "-")
    assert "--author-family <family>" in ml.fix_command(status, missing)


def test_the_author_is_the_commit_that_produced_the_scripts_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Integ's draw_cone_tip_bushing.py: a newer side-branch edit (6b993ef73) that
    # the merge did not take read as the author of the older content it kept.
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    script, other = repo / "draw_crank_arm.py", repo / "notes.py"
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-09-20T00:00:00Z")
    _commit(repo, other, "base")
    _git(repo, "checkout", "-q", "-b", "side")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-09-22T00:00:00Z")
    _commit(repo, script, "side edit\n\nCo-Authored-By: GPT-6 Sol <noreply@openai.com>")
    _commit(repo, other, "side notes\n\nCo-Authored-By: GPT-6 Sol <noreply@openai.com>")
    _git(repo, "checkout", "-q", "main")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-09-21T00:00:00Z")
    _commit(
        repo,
        script,
        "kept edit\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
    )
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-09-23T00:00:00Z")
    # A merge that takes the side's notes and keeps main's script.
    _git(repo, "merge", "-q", "-s", "ours", "--no-commit", "side")
    _git(repo, "checkout", "side", "--", other.name)
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        "commit",
        "-q",
        "-m",
        "merge side's notes, keeping main's script",
    )

    authors = ml.script_authors([script, other], repo=repo)

    assert authors[script].model == "claude-opus-5-5"
    assert authors[other].model == "gpt-6-sol"


def test_claims_must_agree_with_the_trailer(
    registry: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _trailer(monkeypatch, "claude-opus-5-5")

    assert (
        ml.resolve_author("crank_arm", "claude", "Claude Opus 5.5")["model_source"]
        == "trailer"
    )
    with pytest.raises(ValueError, match="disagrees"):
        ml.resolve_author("crank_arm", "claude", "claude-fable-5-1")
    with pytest.raises(ValueError, match="not in the gpt family"):
        ml.resolve_author("crank_arm", "gpt", None)

    _trailer(monkeypatch, None)
    claimed = ml.resolve_author("crank_arm", "gpt", "gpt-6-sol")
    assert (claimed["model"], claimed["model_source"]) == ("gpt-6-sol", "claimed")


# --- last resort ---------------------------------------------------------------------


def _refused(
    tmp_path: Path,
    pdf: Path,
    *,
    name: str = "crank_arm",
    message: str = CODEX_REFUSAL,
    refused_at: str = REFUSED_AT,
) -> Path:
    """A codex report with no verdict, its refusal only in the attempt stdout."""
    stdout = tmp_path / "refused" / f"{name}.attempts" / "a1" / "stdout.txt"
    stdout.parent.mkdir(parents=True)
    stdout.write_text('{"type":"thread.started"}\n' + message + "\n", encoding="utf-8")
    attempt = {
        "command": ["codex", "exec", "--model", "gpt-6-astra"],
        "stdout_file": str(stdout),
    }
    review = mr.Review(
        **{
            **_review(pdf, name=name, passed=False, reviewed_at=refused_at),
            "verdict": None,
            "error": "RuntimeError: codex exit 1: ",
            "extra": {"evidence": {"attempts": [attempt]}},
        }
    )
    mr.write_review(review, tmp_path / "refused")
    return tmp_path / "refused" / f"{name}.json"


def test_quota_refusal_is_read_from_the_refused_attempt(tmp_path: Path) -> None:
    pdf = _sheet(tmp_path / "sheet.pdf")
    refusal = ml.quota_refusal(
        _refused(tmp_path, pdf), name="crank_arm", author_family="claude"
    )

    assert refusal["message"] == CODEX_REFUSAL
    assert refusal["evidence_file"].endswith("a1/stdout.txt")
    assert refusal["command"] == ["codex", "exec", "--model", "gpt-6-astra"]
    assert (refusal["reviewer"], refusal["model"], refusal["refused_at"]) == (
        "codex",
        "gpt-6-astra",
        REFUSED_AT,
    )


def test_quota_refusal_needs_a_cross_family_usage_limit_for_the_same_drawing(
    tmp_path: Path,
) -> None:
    pdf = _sheet(tmp_path / "sheet.pdf")
    report = _refused(tmp_path, pdf)

    with pytest.raises(ValueError, match="not 'pen_rod'"):
        ml.quota_refusal(report, name="pen_rod", author_family="claude")
    with pytest.raises(ValueError, match="cross-family"):
        ml.quota_refusal(report, name="crank_arm", author_family="gpt")
    other = tmp_path / "other"
    other.mkdir()
    crashed = _refused(
        other, pdf, message='{"type":"error","message":"stream disconnected"}'
    )
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
        ("gpt-6-astra", "gpt-6-astra", "xhigh", True),
        (
            "claude-fable-5-1",
            "claude-fable-5-1",
            "medium",
            False,
        ),  # same tier, not high
        ("claude-opus-5-5", "claude-opus-5-5", "high", False),  # same workhorse tier
        ("claude-opus-5-5", "claude-sonnet-5", "high", False),  # Sonnet reviewing Opus
        (
            "claude-sonnet-5",
            "claude-fable-5-1",
            "high",
            False,
        ),  # no tier for the author
    ],
)
def test_last_resort_tier_rule(
    author: str, reviewer: str, effort: str, counts: bool
) -> None:
    assert (ml.last_resort_tier_problem(author, reviewer, effort) is None) == counts


def test_a_qualifying_last_resort_counts(
    tmp_path: Path, registry: Path, monkeypatch
) -> None:
    _trailer(monkeypatch, "claude-opus-5-5")
    ledger_path = tmp_path / "ledger.json"
    pdf = _sheet(registry)
    refusal = ml.quota_refusal(
        _refused(tmp_path, pdf), name="crank_arm", author_family="claude"
    )

    recorded = ml.record_review(
        _review(pdf, reviewer="claude", effort="medium"),
        pdf,
        author_family="claude",
        refusal=refusal,
        provenance={},
        ledger_path=ledger_path,
    )

    entry = ml.load_ledger(ledger_path)["drawings"]["crank_arm"][ml.LAST_RESORT]
    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]
    assert recorded.counts and entry["counts"]
    assert entry["quota_refusal"]["message"] == CODEX_REFUSAL
    assert entry["quota_refusal"]["source_sha256"] == ml.sha256_file(pdf)
    assert entry["quota_refusal_window_hours"] == 24
    assert entry["author"]["model"] == "claude-opus-5-5"
    assert (entry["model"], entry["effort"]) == ("claude-fable-5-1", "medium")
    assert (status.state, status.via) == (ml.State.OK, "last_resort ship")


@pytest.mark.parametrize(
    ("trailer", "refused_at", "effort", "reason"),
    [
        ("claude-opus-5-5", None, "medium", "no recorded quota refusal"),
        (
            "claude-opus-5-5",
            (NOW - timedelta(hours=30)).isoformat(),
            "medium",
            "not within 24 h",
        ),
        (
            "claude-opus-5-5",
            (NOW + timedelta(hours=1)).isoformat(),
            "medium",
            "not within 24 h",
        ),
        ("claude-fable-5-1", REFUSED_AT, "medium", "high effort"),
        (None, REFUSED_AT, "high", "not named by a trailer"),
        ("claude-opus-5-5", "other sheet", "medium", "a different PDF"),
    ],
)
def test_a_last_resort_without_its_evidence_does_not_count(
    tmp_path: Path, registry: Path, monkeypatch, trailer, refused_at, effort, reason
) -> None:
    _trailer(monkeypatch, trailer)
    ledger_path = tmp_path / "ledger.json"
    pdf = _sheet(registry)
    refusal = None
    if refused_at == "other sheet":
        other = _sheet(tmp_path / "other.pdf", note=NOTE.replace("13", "14"))
        report = _refused(tmp_path, other)
        refusal = ml.quota_refusal(report, name="crank_arm", author_family="claude")
    elif refused_at is not None:
        report = _refused(tmp_path, pdf, refused_at=refused_at)
        refusal = ml.quota_refusal(report, name="crank_arm", author_family="claude")

    recorded = ml.record_review(
        _review(pdf, reviewer="claude", effort=effort),
        pdf,
        author_family="claude",
        refusal=refusal,
        provenance={},
        ledger_path=ledger_path,
    )

    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]
    assert not recorded.counts and reason in recorded.problem
    assert (status.state, status.last_resort) == (ml.State.UNREVIEWED, "matches")
    assert reason in status.detail


def test_cross_family_drift_is_covered_by_a_counting_last_resort(
    tmp_path: Path, registry: Path, monkeypatch
) -> None:
    ledger_path = tmp_path / "ledger.json"
    first = _sheet(registry)
    ml.record_review(
        _review(first),
        first,
        author_family="claude",
        provenance={},
        ledger_path=ledger_path,
    )
    edited = _sheet(registry, note=NOTE[:-1] + ",")
    assert ml.check(["crank_arm"], ledger_path=ledger_path)[0].state == ml.State.DRIFT

    _trailer(monkeypatch, "claude-opus-5-5")
    refusal = ml.quota_refusal(
        _refused(tmp_path, edited), name="crank_arm", author_family="claude"
    )
    ml.record_review(
        _review(edited, reviewer="claude"),
        edited,
        author_family="claude",
        refusal=refusal,
        provenance={},
        ledger_path=ledger_path,
    )
    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]
    assert (status.state, status.via, status.last_resort) == (
        ml.State.OK,
        "last_resort ship",
        "matches",
    )


# --- rulings -------------------------------------------------------------------------


def _rulings_log(tmp_path: Path) -> Path:
    log = tmp_path / "handoff.md"
    filler = "".join(f"- 14:{minute:02d}Z build notes\n" for minute in range(10))
    log.write_text(
        f"# handoff\n{filler}- ~15:50Z USER RULINGS (via Main):\n"
        "- U31: the note band stays on the sheet\n"
        "- U37: datum A stays for the fixture\n",
        encoding="utf-8",
    )
    return log


def _rebuttals(log: Path) -> list[dict]:
    return [
        {
            "category": "over_specification",
            "index": 0,
            "where": "note 2",
            "ruling": "U31",
            "citation": f"{log.as_posix()}:13",
            "rebuttal": "the user ruled the band onto the sheet",
        },
        {
            "category": "over_specification",
            "index": 1,
            "where": "datum A",
            "ruling": "U37",
            "citation": log.as_posix(),
            "rebuttal": "the fixture needs datum A",
        },
    ]


def test_a_fix_whose_every_finding_cites_a_ruling_is_accepted_with_rulings(
    tmp_path: Path, registry: Path
) -> None:
    ledger_path = tmp_path / "ledger.json"
    pdf = _sheet(registry)
    log = _rulings_log(tmp_path)

    recorded = ml.record_review(
        _review(pdf, passed=False),
        pdf,
        author_family="claude",
        rebuttals=_rebuttals(log),
        provenance={},
        ledger_path=ledger_path,
    )

    entry = ml.load_ledger(ledger_path)["drawings"]["crank_arm"][ml.CROSS_FAMILY]
    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]
    assert recorded.status == entry["status"] == ml.ACCEPTED_WITH_RULINGS
    assert [(r["where"], r["ruling"], r["cited"]) for r in entry["rebuttals"]] == [
        ("note 2", "U31", "- U31: the note band stays on the sheet"),
        ("datum A", "U37", "- U37: datum A stays for the fixture"),
    ]
    assert entry["rebuttals"][0]["issue"] == "band repeats the title block"
    assert (status.state, status.via) == (
        ml.State.OK,
        "cross_family accepted_with_rulings",
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda r: r[:1],
            r"findings with no cited ruling: \['over_specification\[1\] datum A'\]",
        ),
        (lambda r: [{**r[0], "ruling": "U99"}, r[1]], "does not mention U99"),
        (
            lambda r: [{**r[0], "citation": r[0]["citation"][:-3] + ":2"}, r[1]],
            "near that line",
        ),
        (lambda r: [{**r[0], "citation": "missing.md:3"}, r[1]], "no such file"),
        (lambda r: [{**r[0], "where": "note 3"}, r[1]], "where 'note 3'"),
        (lambda r: [r[0], r[0], r[1]], "rebutted twice"),
        (lambda r: [*r, {**r[0], "index": 5}], "names no finding"),
        (
            lambda r: [{**r[0], "rebuttal": ""}, r[1]],
            "needs a ruling id, a citation and its text",
        ),
    ],
)
def test_an_uncited_finding_keeps_the_drawing_failing(
    tmp_path: Path, registry: Path, change, message: str
) -> None:
    ledger_path = tmp_path / "ledger.json"
    pdf = _sheet(registry)

    with pytest.raises(ValueError, match=message):
        ml.record_review(
            _review(pdf, passed=False),
            pdf,
            author_family="claude",
            rebuttals=change(_rebuttals(_rulings_log(tmp_path))),
            provenance={},
            ledger_path=ledger_path,
        )
    assert not ledger_path.exists()


def test_a_passing_review_has_nothing_to_rebut(tmp_path: Path, registry: Path) -> None:
    pdf = _sheet(registry)
    with pytest.raises(ValueError, match="nothing to rebut"):
        ml.record_review(
            _review(pdf),
            pdf,
            author_family="claude",
            rebuttals=_rebuttals(_rulings_log(tmp_path)),
            provenance={},
            ledger_path=tmp_path / "ledger.json",
        )


# --- drift check ---------------------------------------------------------------------


def _recorded(tmp_path: Path, registry: Path) -> Path:
    ledger_path = tmp_path / "ledger.json"
    pdf = _sheet(registry, producer="reviewed render")
    ml.record_review(
        _review(pdf),
        pdf,
        author_family="claude",
        provenance={},
        ledger_path=ledger_path,
    )
    return ledger_path


def test_check_accepts_a_re_render_of_the_reviewed_sheet(
    tmp_path: Path, registry: Path
) -> None:
    ledger_path = _recorded(tmp_path, registry)
    _sheet(registry, revision="DEV", producer="post-integration build")
    assert ml.check(["crank_arm"], ledger_path=ledger_path)[0].state == ml.State.OK

    # A sub-tolerance shift needs the stored PDF, not the digest.
    _sheet(registry, edge_x=40.0 + PT_PER_PX)
    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]
    assert (status.state, status.via) == (ml.State.OK, "cross_family ship")


def test_check_re_renders_the_stored_pdf_when_the_recorded_digests_are_stale(
    tmp_path: Path, registry: Path
) -> None:
    # A renderer upgrade moves every digest; the stored PDF is re-rendered instead.
    ledger_path = _recorded(tmp_path, registry)
    ledger = ml.load_ledger(ledger_path)
    ledger["drawings"]["crank_arm"][ml.CROSS_FAMILY]["sheets"] = ["0" * 64]
    ml.save_ledger(ledger, ledger_path)

    assert ml.check(["crank_arm"], ledger_path=ledger_path)[0].state == ml.State.OK


def test_check_reports_drift_and_writes_the_diff(
    tmp_path: Path, registry: Path
) -> None:
    ledger_path = _recorded(tmp_path, registry)
    _sheet(registry, note=NOTE[:-1] + ",")

    status = ml.check(
        ["crank_arm"], ledger_path=ledger_path, report_dir=tmp_path / "report"
    )[0]

    assert status.state == ml.State.DRIFT
    assert status.detail.startswith("sheet 1 (")
    assert "2 text changes" in status.detail
    assert "since codex/gpt-6-astra" in status.detail
    reviewed = ml.load_ledger(ledger_path)["drawings"]["crank_arm"][ml.CROSS_FAMILY]
    current = ml.fingerprint(registry)[0]
    assert (
        f"reviewed {reviewed['sheets'][0][:12]} -> now {current[:12]}" in status.detail
    )
    assert [Path(path).name for path in status.diff_files] == [
        "crank_arm-sheet1-diff.png",
        "crank_arm-diff.txt",
    ]


@pytest.mark.parametrize(
    ("damage", "message"),
    [
        (lambda stored: stored.unlink(), "reviewed PDF is missing"),
        (
            lambda stored: stored.write_bytes(b"%PDF-1.4 not the reviewed file"),
            "does not hash",
        ),
    ],
)
def test_an_exact_match_still_needs_the_stored_pdf(
    tmp_path: Path, registry: Path, damage, message: str
) -> None:
    ledger_path = _recorded(tmp_path, registry)  # the current PDF IS the reviewed one
    for stored in (tmp_path / "sheets").glob("*.pdf"):
        damage(stored)

    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]

    assert status.state == ml.State.DRIFT
    assert message in status.detail


def test_check_treats_a_missing_reviewed_pdf_as_drift(
    tmp_path: Path, registry: Path
) -> None:
    ledger_path = _recorded(tmp_path, registry)
    for stored in (tmp_path / "sheets").glob("*.pdf"):
        stored.unlink()
    _sheet(registry, edge_x=40.0 + PT_PER_PX)

    status = ml.check(["crank_arm"], ledger_path=ledger_path)[0]

    assert status.state == ml.State.DRIFT
    assert "reviewed PDF is missing" in status.detail


def test_check_names_unrendered_and_unknown_drawings(
    tmp_path: Path, registry: Path
) -> None:
    ledger_path = tmp_path / "ledger.json"
    assert (
        ml.check(["crank_arm"], ledger_path=ledger_path)[0].state == ml.State.UNRENDERED
    )
    with pytest.raises(ValueError, match="unknown drawing names"):
        ml.check(["not-a-drawing"], ledger_path=ledger_path)


def test_cli_exit_status_is_the_gate(tmp_path: Path, registry: Path, capsys) -> None:
    ledger = str(tmp_path / "ledger.json")
    assert ml.main(["--ledger", ledger, "check", "crank_arm"]) == 1
    assert (
        ml.main(["--ledger", ledger, "check", "crank_arm", "--allow-unrendered"]) == 0
    )

    _sheet(registry)
    assert ml.main(["--ledger", ledger, "check", "crank_arm"]) == 1
    assert "unreviewed" in capsys.readouterr().out

    ml.record_review(
        _review(registry),
        registry,
        author_family="claude",
        provenance={},
        ledger_path=Path(ledger),
    )
    assert ml.main(["--ledger", ledger, "check", "crank_arm", "--json"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)[0]["state"] == "ok"
    assert (
        "1/1 drawings match an accepted review (0 via last resort, 0 accepted with rulings)"
        in captured.err
    )

    assert ml.main(["--ledger", ledger, "check", "not-a-drawing"]) == 2
    assert "unknown drawing names" in capsys.readouterr().err


def test_ingest_cli_records_rebuttals_and_last_resort(
    tmp_path: Path, registry: Path, monkeypatch, capsys
) -> None:
    pdf = _sheet(registry)
    ledger = str(tmp_path / "ledger.json")
    mr.write_review(mr.Review(**_review(pdf, reviewer="claude")), tmp_path / "reports")
    report = str(tmp_path / "reports" / "crank_arm.json")
    _trailer(monkeypatch, "claude-opus-5-5")

    assert (
        ml.main(["--ledger", ledger, "ingest", report, "--author-family", "claude"])
        == 1
    )
    assert "does NOT count: no recorded quota refusal" in capsys.readouterr().out
    assert ml.main(["--ledger", ledger, "check", "crank_arm"]) == 1

    refused = str(_refused(tmp_path, pdf))
    argv = ["ingest", report, "--author-family", "claude", "--quota-refusal", refused]
    assert ml.main(["--ledger", ledger, *argv]) == 0
    assert "does NOT count" not in capsys.readouterr().out
    assert ml.main(["--ledger", ledger, "check", "crank_arm"]) == 0

    fix = tmp_path / "fix"
    mr.write_review(mr.Review(**_review(pdf, passed=False)), fix)
    rebuttals = tmp_path / "rebuttals.json"
    payload = {"drawing": "crank_arm", "rebuttals": _rebuttals(_rulings_log(tmp_path))}
    rebuttals.write_text(json.dumps(payload), encoding="utf-8")
    argv = ["ingest", str(fix / "crank_arm.json"), "--author-family", "claude"]
    assert ml.main(["--ledger", ledger, *argv, "--rebuttals", str(rebuttals)]) == 0
    assert "cross_family accepted_with_rulings" in capsys.readouterr().out


# --- machinist_review integration ----------------------------------------------------


def test_review_run_requires_a_cross_family_author(capsys) -> None:
    assert mr.main(["--reviewer", "codex", "crank_arm"]) == 2
    assert "--author-family is required" in capsys.readouterr().err

    assert mr.main(["--reviewer", "codex", "--author-family", "gpt", "crank_arm"]) == 2
    assert "same family" in capsys.readouterr().err

    assert (
        mr.main(
            [
                "--reviewer",
                "codex",
                "--author-family",
                "claude",
                "--last-resort",
                "crank_arm",
            ]
        )
        == 2
    )
    assert "only to a same-family review" in capsys.readouterr().err


def test_last_resort_run_is_refused_before_any_reviewer_runs(
    tmp_path: Path, registry: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    pdf = _sheet(registry)
    reports = tmp_path / "reports"
    refused = _refused(tmp_path, pdf)
    stale = _refused(
        tmp_path / "stale", pdf, refused_at=(NOW - timedelta(hours=30)).isoformat()
    )
    monkeypatch.setattr(
        mr, "review_package", lambda *a, **k: pytest.fail("reviewer ran")
    )
    same = [
        "--reviewer",
        "claude",
        "--author-family",
        "claude",
        "--last-resort",
        "--report-dir",
        str(reports),
    ]
    evidence = ["--quota-refusal", str(refused)]

    _trailer(monkeypatch, "claude-opus-5-5")
    cases = [
        ([*same, "crank_arm"], "quota-refused.json"),  # nothing kept for this drawing
        ([*same, "--all", *evidence], "exactly one registry drawing"),
        ([*same, "pen_rod", *evidence], "not 'pen_rod'"),
        ([*same, "crank_arm", "--quota-refusal", str(stale)], "not within 24 h"),
        (
            [*same, "crank_arm", *evidence, "--author-model", "claude-sonnet-5"],
            "disagrees",
        ),
    ]
    for argv, message in cases:
        assert mr.main(argv) == 2, message
        assert message in capsys.readouterr().err

    other = _sheet(tmp_path / "other.pdf", note=NOTE.replace("13", "14"))
    elsewhere = _refused(tmp_path / "elsewhere", other)
    assert mr.main([*same, "crank_arm", "--quota-refusal", str(elsewhere)]) == 2
    assert "a different PDF" in capsys.readouterr().err

    _trailer(monkeypatch, "claude-fable-5-1")
    assert mr.main([*same, "crank_arm", *evidence]) == 2
    assert "high effort" in capsys.readouterr().err

    _trailer(monkeypatch, None)
    assert mr.main([*same, "crank_arm", *evidence]) == 2
    assert "names no author model" in capsys.readouterr().err


def _fake_run(monkeypatch: pytest.MonkeyPatch, pdf: Path, make_review) -> None:
    def fake_review(package, *, report_dir, **kwargs):
        assert package.sources == (pdf,)
        review = make_review()
        mr.write_review(review, report_dir)
        return review

    monkeypatch.setattr(
        mr, "package_for", lambda name: mr.ReviewPackage(name, "part", (pdf,))
    )
    monkeypatch.setattr(mr, "review_package", fake_review)


def test_a_last_resort_whose_refusal_expires_mid_run_fails_the_run(
    tmp_path: Path, registry: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    # The clock: the refusal is 23 h old when the run starts (the pre-run check
    # passes) and 25 h old when the reviewer finishes (the record does not count).
    pdf = _sheet(registry)
    refused = _refused(
        tmp_path, pdf, refused_at=(NOW - timedelta(hours=23)).isoformat()
    )
    finished = (NOW + timedelta(hours=2)).isoformat()
    _trailer(monkeypatch, "claude-opus-5-5")
    _fake_run(
        monkeypatch,
        pdf,
        lambda: mr.Review(**_review(pdf, reviewer="claude", reviewed_at=finished)),
    )
    ledger_path = tmp_path / "ledger.json"

    code = mr.main(
        ["--reviewer", "claude", "--author-family", "claude", "--last-resort", "crank_arm",
         "--quota-refusal", str(refused), "--ledger", str(ledger_path),
         "--report-dir", str(tmp_path / "reports")]
    )  # fmt: skip

    err = capsys.readouterr().err
    assert code == 1
    assert "recorded in the ledger but does NOT count" in err
    assert "25.0 h before the review, not within 24 h" in err
    entry = ml.load_ledger(ledger_path)["drawings"]["crank_arm"][ml.LAST_RESORT]
    assert entry["counts"] is False


def test_ingest_of_a_review_that_does_not_count_exits_nonzero(
    tmp_path: Path, registry: Path, capsys
) -> None:
    pdf = _sheet(registry)
    mr.write_review(mr.Review(**_review(pdf, reviewer="claude")), tmp_path / "reports")
    ledger = str(tmp_path / "ledger.json")
    argv = [
        "ingest",
        str(tmp_path / "reports" / "crank_arm.json"),
        "--author-family",
        "claude",
    ]

    assert ml.main(["--ledger", ledger, *argv]) == 1
    assert "does NOT count: no recorded quota refusal" in capsys.readouterr().out
    assert (
        ml.load_ledger(Path(ledger))["drawings"]["crank_arm"][ml.LAST_RESORT]["counts"]
        is False
    )


def test_a_quota_refusal_is_kept_and_unlocks_the_last_resort_run(
    tmp_path: Path, registry: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = _sheet(registry)
    reports = tmp_path / "reports"
    ledger_path = tmp_path / "ledger.json"
    refusal = json.loads(_refused(tmp_path, pdf).read_text(encoding="utf-8"))
    common = ["crank_arm", "--ledger", str(ledger_path), "--report-dir", str(reports)]

    _fake_run(monkeypatch, pdf, lambda: mr.Review(**refusal))
    assert mr.main(["--reviewer", "codex", "--author-family", "claude", *common]) == 1
    assert (reports / "crank_arm.quota-refused.json").is_file()

    _trailer(monkeypatch, "claude-opus-5-5")
    _fake_run(monkeypatch, pdf, lambda: mr.Review(**_review(pdf, reviewer="claude")))
    code = mr.main(
        ["--reviewer", "claude", "--author-family", "claude", "--last-resort", *common]
    )

    entry = ml.load_ledger(ledger_path)["drawings"]["crank_arm"]
    assert code == 0
    assert list(entry) == [ml.LAST_RESORT] and entry[ml.LAST_RESORT]["counts"]
    assert entry[ml.LAST_RESORT]["quota_refusal"]["report"].endswith(
        "crank_arm.quota-refused.json"
    )
    assert ml.check(["crank_arm"], ledger_path=ledger_path)[0].state == ml.State.OK


def test_passing_cross_family_run_records_the_ledger(
    tmp_path: Path, registry: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = _sheet(registry)
    _fake_run(monkeypatch, pdf, lambda: mr.Review(**_review(pdf)))
    ledger_path = tmp_path / "ledger.json"

    code = mr.main(
        [
            "--reviewer",
            "codex",
            "--author-family",
            "claude",
            "crank_arm",
            "--ledger",
            str(ledger_path),
            "--report-dir",
            str(tmp_path / "reports"),
        ]
    )

    assert code == 0
    assert list(ml.load_ledger(ledger_path)["drawings"]["crank_arm"]) == [
        ml.CROSS_FAMILY
    ]
    assert ml.check(["crank_arm"], ledger_path=ledger_path)[0].state == ml.State.OK


@pytest.mark.parametrize(("keep", "code"), [(2, 0), (1, 1)])
def test_review_run_with_rebuttals(
    tmp_path: Path,
    registry: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    keep: int,
    code: int,
) -> None:
    pdf = _sheet(registry)
    _fake_run(monkeypatch, pdf, lambda: mr.Review(**_review(pdf, passed=False)))
    rebuttals = tmp_path / "rebuttals.json"
    payload = {
        "drawing": "crank_arm",
        "rebuttals": _rebuttals(_rulings_log(tmp_path))[:keep],
    }
    rebuttals.write_text(json.dumps(payload), encoding="utf-8")
    ledger_path = tmp_path / "ledger.json"

    result = mr.main(
        [
            "--reviewer",
            "codex",
            "--author-family",
            "claude",
            "crank_arm",
            "--rebuttals",
            str(rebuttals),
            "--ledger",
            str(ledger_path),
            "--report-dir",
            str(tmp_path / "reports"),
        ]
    )

    assert result == code
    if code:
        assert "findings with no cited ruling" in capsys.readouterr().err
        assert not ledger_path.exists()
        return
    entry = ml.load_ledger(ledger_path)["drawings"]["crank_arm"][ml.CROSS_FAMILY]
    assert entry["status"] == ml.ACCEPTED_WITH_RULINGS


def test_review_run_fails_when_the_pdf_changed_before_it_could_be_recorded(
    tmp_path: Path, registry: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    pdf = _sheet(registry)

    def make_review():
        review = mr.Review(**_review(pdf))
        _sheet(registry, producer="a concurrent build rewrote it")
        return review

    _fake_run(monkeypatch, pdf, make_review)
    ledger_path = tmp_path / "ledger.json"

    code = mr.main(
        [
            "--reviewer",
            "codex",
            "--author-family",
            "claude",
            "crank_arm",
            "--ledger",
            str(ledger_path),
            "--report-dir",
            str(tmp_path / "reports"),
        ]
    )

    assert code == 1
    assert "not recorded in the ledger" in capsys.readouterr().err
    assert not ledger_path.exists()


def test_the_ledger_tests_run_under_the_recipe_gate() -> None:
    dodo = (ml.REPO_ROOT / "dodo.py").read_text(encoding="utf-8")
    assert 'SCRIPTS_DIR / "test_machinist_ledger.py"' in dodo
    assert 'SCRIPTS_DIR / "test_machinist_review.py"' in dodo


def test_only_the_review_tools_and_the_release_gate_read_the_ledger() -> None:
    """Naming a test file (``test_machinist_ledger.py``) to enroll it is not a read.

    dodo.py reads it only for ``check:machinist``; the next test proves no
    cache-keyed build task does.
    """
    import re

    reads = re.compile(r"(?<!\w)machinist_ledger(?!\w)|machinist-ledger")
    readers = {
        path.name
        for path in [*ml.SCRIPTS_DIR.rglob("*.py"), ml.REPO_ROOT / "dodo.py"]
        if reads.search(path.read_text(encoding="utf-8"))
    }
    assert readers == {
        "dodo.py",
        "machinist_ledger.py",
        "machinist_review.py",
        "test_machinist_ledger.py",
    }


def _load_dodo():
    import importlib.util

    spec = importlib.util.spec_from_file_location("dodo", ml.REPO_ROOT / "dodo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_is_gated_on_the_ledger_and_no_build_task_is_keyed_on_it() -> None:
    dodo = _load_dodo()
    gate = next(task for task in dodo.task_check() if task["name"] == "machinist")
    ledger = str(ml.LEDGER_PATH.resolve())
    pdfs = {str(spec.outputs["pdf"].resolve()) for spec in ml.DRAWINGS}

    # SolidWorks-free, but ordered after (and re-run by) every rendered sheet.
    assert ledger in gate["file_dep"]
    assert pdfs <= set(gate["file_dep"])
    assert str((ml.SCRIPTS_DIR / "machinist_ledger.py").resolve()) in gate["file_dep"]
    assert "check:machinist" in dodo.task_release()["task_dep"]
    # In build it would fail every build between a drawing edit and its re-review.
    assert "check:machinist" not in dodo.task_build()["task_dep"]
    # Always run: a stored reviewed PDF deleted after a green run must be
    # re-verified, never excused by a stale stamp.
    assert gate["uptodate"] == [False]

    reviews = str((ml.CAD_ROOT / "reviews").resolve())
    tool = str((ml.SCRIPTS_DIR / "machinist_ledger.py").resolve())
    keyed = [
        (label, dep)
        for label, deps in dodo._cache_rows()
        for dep in deps
        if str(Path(dep).resolve()).startswith(reviews)
        or str(Path(dep).resolve()) == tool
    ]
    assert keyed == []


def test_a_drawing_whose_ink_moved_fails_with_its_sheet_and_digest_pair(
    tmp_path: Path, registry: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    ledger_path = tmp_path / "ledger.json"
    reviewed = _sheet(registry)
    ml.record_review(
        _review(reviewed),
        reviewed,
        author_family="claude",
        provenance={},
        ledger_path=ledger_path,
    )
    before = ml.fingerprint(registry)[0]
    _sheet(
        registry, edge_x=40.0 + 6 * PT_PER_PX
    )  # a view edge 6 px over: beyond tolerance
    after = ml.fingerprint(registry)[0]
    _trailer(monkeypatch, "claude-opus-5-5")

    assert (
        ml.main(
            [
                "--ledger",
                str(ledger_path),
                "check",
                "crank_arm",
                "--report-dir",
                str(tmp_path / "r"),
            ]
        )
        == 1
    )

    err = capsys.readouterr().err
    assert "crank_arm (drift: sheet 1 (" in err
    assert f"reviewed {before[:12]} -> now {after[:12]}" in err
    assert "--reviewer codex --author-family claude" in err


def test_failing_check_lists_each_blocked_drawing_with_its_fix(
    tmp_path: Path, registry: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    ledger = str(tmp_path / "ledger.json")
    _sheet(registry)
    _trailer(monkeypatch, "claude-opus-5-5")

    assert ml.main(["--ledger", ledger, "check", "crank_arm"]) == 1
    err = capsys.readouterr().err
    assert "1 drawings have no counting machinist review" in err
    assert (
        "  crank_arm (unreviewed): uv run cad/scripts/machinist_review.py crank_arm "
        "--reviewer codex --author-family claude"
    ) in err

    assert ml.main(["--ledger", ledger, "check", "crank_arm", "--json"]) == 1
    row = json.loads(capsys.readouterr().out)[0]
    assert row["fix"].endswith("--reviewer codex --author-family claude")


@pytest.mark.parametrize(
    ("state", "author", "fix"),
    [
        (
            ml.State.UNRENDERED,
            "claude-opus-5-5",
            "uv run python -m doit drawing:crank_arm, then uv run cad/scripts/"
            "machinist_review.py crank_arm --reviewer codex --author-family claude",
        ),
        (ml.State.DRIFT, "gpt-6-sol", "--reviewer claude --author-family gpt"),
        (ml.State.UNREVIEWED, None, "(its last commit names no model)"),
        (
            ml.State.UNREVIEWED,
            ValueError("draw_crank_arm.py has uncommitted changes"),
            "uncommitted",
        ),
    ],
)
def test_fix_command(registry: Path, state, author, fix: str) -> None:
    if isinstance(author, str) or author is None:
        author = ml.Author(author, "c" * 40, "cad/scripts/draw_crank_arm.py")
    status = ml.Status("crank_arm", state, "", "", "-")

    assert fix in ml.fix_command(status, author)


def test_the_tracked_ledger_matches_this_checkouts_fingerprint_settings() -> None:
    ledger = ml.load_ledger(ml.LEDGER_PATH)
    assert ledger["fingerprint"] == ml.empty_ledger()["fingerprint"]


def test_no_failing_drawing_means_no_git_call(monkeypatch: pytest.MonkeyPatch) -> None:
    # An empty pathspec would walk the whole history instead of nothing.
    monkeypatch.setattr(ml, "_git", lambda *a, **k: pytest.fail(f"git {a}"))
    assert ml.draw_script_authors([]) == {}
    assert ml.script_authors([]) == {}
