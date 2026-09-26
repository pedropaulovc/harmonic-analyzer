"""Offline contracts for the machinist-review wave driver.

The reviewer is a fake that writes the same records machinist_review does, so
routing, quota fallback, ingest and resume run end to end without a model.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import machinist_ledger as ml
import machinist_review as mr
import machinist_wave as mw
from test_machinist_ledger import (
    CODEX_REFUSAL,
    _author_rulings,
    _outages,
    _sheet,
    _verdict,
)

NAMES = ("crank_arm", "pen_rod")


@pytest.fixture
def checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A rendered checkout of two registry drawings; neither is in the ledger."""
    root = tmp_path / "checkout"
    for name in NAMES:
        pdf = root / "cad" / "out" / "pdf" / f"{name.replace('_', '-')}.pdf"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        _sheet(pdf, note=f"{name.upper()} NOTE")
        row = SimpleNamespace(
            outputs={"pdf": pdf}, script_name=f"draw_{name}.py", source_kind="part"
        )
        monkeypatch.setitem(mw.DRAWINGS_BY_NAME, name, row)
    monkeypatch.setattr(mw, "WAVE_ROOT", tmp_path / "waves")
    # A stand-in render with no registry or git history of its own; the
    # checkout rule has its own test below.
    monkeypatch.setattr(ml, "checkout_metadata_problem", lambda checkout: None)
    return root


def _authors(monkeypatch: pytest.MonkeyPatch, **models: str | None) -> None:
    """The model each draw script's last commit names (None: no trailer)."""
    authors = {
        name: ml.Author(model, "c" * 40, f"cad/scripts/draw_{name}.py")
        for name, model in models.items()
    }
    monkeypatch.setattr(
        ml, "draw_script_authors", lambda names, **_: {n: authors[n] for n in names}
    )
    monkeypatch.setattr(ml, "draw_script_author", lambda name, **_: authors[name])


REAL_CHECKOUT_PROBLEM = ml.checkout_metadata_problem


class FakeReviewer:
    """Stands in for review_package: a verdict per (drawing, reviewer), or quota."""

    def __init__(self, outcomes: dict[tuple[str, str], str]) -> None:
        self.outcomes = outcomes  # "ship" | "fix" | "quota" | "sighted"
        self.calls: list[tuple[str, str, str, str]] = []

    def __call__(self, package, *, reviewer, model, effort, report_dir, **_):
        self.calls.append((package.name, reviewer, model, effort))
        outcome = self.outcomes[(package.name, reviewer)]
        pdf = package.sources[0]
        extra: dict = {}
        verdict = None
        if outcome == "quota":
            stdout = report_dir / f"{package.name}.attempts" / "a1" / "stdout.txt"
            stdout.parent.mkdir(parents=True, exist_ok=True)
            stdout.write_text(CODEX_REFUSAL + "\n", encoding="utf-8")
            extra = {"evidence": {"attempts": [{"stdout_file": str(stdout)}]}}
        else:
            verdict = _verdict(passed=outcome in ("ship", "sighted"))
        events = report_dir / f"{package.name}.events.jsonl"
        report_dir.mkdir(parents=True, exist_ok=True)
        events.write_text(
            json.dumps({"event": {"type": "result", "total_cost_usd": 0.25}})
            if reviewer == "claude"
            else json.dumps(
                {"event": {"type": "turn.completed", "usage": {"output_tokens": 700}}}
            ),
            encoding="utf-8",
        )
        prompt = mr._review_prompt(package, 1, reviewer=reviewer)
        extra.setdefault("evidence", {})["effective_prompt"] = prompt
        review = mr.Review(
            name=package.name,
            kind=package.kind,
            sources=[str(pdf)],
            source_sha256=[ml.sha256_file(pdf)],
            verdict=verdict,
            passed=outcome == "ship",
            blind=outcome != "sighted",  # a SHIP from a run that used a tool
            tool_events=int(outcome == "sighted"),
            reviewer=reviewer,
            model=model,
            effort=effort,
            prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            sheet_count=1,
            duration_s=12.5,
            reviewed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            error="RuntimeError: codex exit 1: " if outcome == "quota" else None,
            events_file=str(events),
            extra=extra,
        )
        mr.write_review(review, report_dir)
        return review


def _wave(
    tmp_path: Path,
    checkout: Path,
    fake: FakeReviewer,
    wave: str = "w1",
    rulings: ml.AuthorRulings | None = None,
    outage: dict | None = None,
):
    directory = mw.WAVE_ROOT / wave
    manifest = mw.Manifest.open(
        directory / "manifest.json", {"wave": wave, "head": "h" * 40}
    )
    return mw.Wave(
        manifest,
        directory,
        tmp_path / "ledger.json",
        checkout,
        review=fake,
        rulings=rulings or ml.AuthorRulings(),
        outage=outage,
    )


def _routes(
    checkout: Path, tmp_path: Path, rulings=None, untrailered=None
) -> list[mw.Route]:
    ruled = ml.AuthorRulings(rulings or {}, untrailered)
    failing, _ = mw.blocked(checkout, tmp_path / "ledger.json", NAMES, ruled)
    return mw.route(failing, checkout, ruled)


def test_routing_follows_the_author_on_record(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod=None)

    routes = {r.name: r for r in _routes(checkout, tmp_path)}
    assert routes["crank_arm"].reviewer == "codex"
    assert routes["crank_arm"].author_source == "trailer"
    assert routes["pen_rod"].reviewer is None  # no trailer, no ruling: not guessed
    assert "no ruling" in routes["pen_rod"].problem

    ruling = {"drawing": "pen_rod", "family": "gpt", "commit": "c" * 40}
    routes = {r.name: r for r in _routes(checkout, tmp_path, {"pen_rod": ruling})}
    assert (routes["pen_rod"].reviewer, routes["pen_rod"].author_source) == (
        "claude",
        "ruling",
    )


def test_an_untrailered_script_goes_to_gpt_review_and_a_trailer_is_followed(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The user's ruling (2026-09-25): untrailered = Claude, so GPT reviews it.
    rule = {"family": "claude", "ruled_by": "user", "ruled_at": "2026-09-25"}
    _authors(monkeypatch, crank_arm="gpt-6-sol", pen_rod=None)

    routes = {r.name: r for r in _routes(checkout, tmp_path, untrailered=rule)}

    pen = routes["pen_rod"]
    assert (pen.author_family, pen.reviewer, pen.author_source) == (
        "claude",
        "codex",
        ml.UNTRAILERED,
    )
    crank = routes["crank_arm"]  # its GPT trailer wins over the rule
    assert (crank.author_family, crank.reviewer, crank.author_source) == (
        "gpt",
        "claude",
        "trailer",
    )


BOTH = "class rule conflicts with per-drawing ruling; both families required"


def test_a_both_families_drawing_gets_a_review_from_each_family_it_lacks(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm=None, pen_rod=None)
    rule = {"family": "claude", "ruled_by": "user", "ruled_at": "2026-09-25"}
    both = {"drawing": "crank_arm", "family": "gpt", "commit": "c" * 40}
    both["both_families"] = BOTH
    rulings = ml.AuthorRulings({"crank_arm": both}, rule)
    ledger_path = tmp_path / "ledger.json"
    # crank_arm already has its Claude SHIP on record (the backfilled one).
    pdf = ml._current_pdf("crank_arm", checkout)
    claude = asdict(
        FakeReviewer({("crank_arm", "claude"): "ship"})(
            mr.ReviewPackage("crank_arm", "part", (pdf,)),
            reviewer="claude",
            model="claude-fable-5-1",
            effort="high",
            report_dir=tmp_path / "earlier",
        )
    )
    ml.record_review(
        claude,
        pdf,
        author_family="gpt",
        provenance={},
        ledger_path=ledger_path,
        rulings=rulings,
    )

    routes = {r.name: r for r in _routes(checkout, tmp_path, {"crank_arm": both}, rule)}
    crank = routes["crank_arm"]
    assert (crank.families, crank.reviewer, crank.author_source) == (
        ("gpt",),
        "codex",
        ml.BOTH_FAMILIES,
    )
    assert routes["pen_rod"].families == ()  # the class rule alone: one review

    fake = FakeReviewer({("crank_arm", "codex"): "ship", ("pen_rod", "codex"): "ship"})
    wave = _wave(tmp_path, checkout, fake, rulings=rulings)
    outcome = mw.run_wave([crank], wave, jobs=1)

    assert outcome == {"crank_arm": mw.State.INGESTED}
    assert [call[:2] for call in fake.calls] == [("crank_arm", "codex")]
    [status] = ml.check(["crank_arm"], ledger_path=ledger_path, rulings=rulings)
    assert status.state == ml.State.OK
    assert status.via == "both_families_claude ship + both_families_gpt ship"


def test_a_both_families_drawing_lacking_both_runs_each_and_takes_no_last_resort(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm=None, pen_rod=None)
    both = {"drawing": "crank_arm", "family": "gpt", "commit": "c" * 40}
    both["both_families"] = BOTH
    rulings = ml.AuthorRulings({"crank_arm": both})
    [crank] = [
        r for r in _routes(checkout, tmp_path, {"crank_arm": both}) if r.families
    ]
    assert crank.families == ("claude", "gpt")

    # Codex refuses on quota after the Claude review passed: no last resort.
    fake = FakeReviewer(
        {("crank_arm", "claude"): "ship", ("crank_arm", "codex"): "quota"}
    )
    outcome = mw.run_wave(
        [crank], _wave(tmp_path, checkout, fake, rulings=rulings), jobs=1
    )

    assert outcome == {"crank_arm": mw.State.REFUSED}
    assert [call[:2] for call in fake.calls] == [
        ("crank_arm", "claude"),
        ("crank_arm", "codex"),
    ]
    [status] = ml.check(
        ["crank_arm"], ledger_path=tmp_path / "ledger.json", rulings=rulings
    )
    assert (status.state, status.missing) == (ml.State.UNREVIEWED, ("gpt",))


def test_an_outage_sends_the_down_reviewers_drawings_to_the_directed_fallback(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # crank_arm: a Claude author, so codex would review it -- but codex is down.
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    outage = ml.load_outages(_outages(tmp_path))["codex-401-test"]
    fake = FakeReviewer(
        {("crank_arm", "claude"): "ship", ("pen_rod", "claude"): "ship"}
    )
    wave = _wave(tmp_path, checkout, fake, outage=outage)

    outcome = mw.run_wave(_routes(checkout, tmp_path), wave, jobs=1)

    assert outcome == {"crank_arm": mw.State.INGESTED, "pen_rod": mw.State.INGESTED}
    assert ("crank_arm", "claude", "claude-fable-5-1") in [c[:3] for c in fake.calls]
    assert all(call[1] == "claude" for call in fake.calls)  # codex never ran
    ledger = ml.load_ledger(tmp_path / "ledger.json")["drawings"]
    assert list(ledger["crank_arm"]) == [ml.OUTAGE_FALLBACK]
    assert ledger["crank_arm"][ml.OUTAGE_FALLBACK]["outage"]["id"] == "codex-401-test"
    assert list(ledger["pen_rod"]) == [ml.CROSS_FAMILY]
    [attempt] = wave.manifest.drawings["crank_arm"]["attempts"]
    assert attempt["slot"] == ml.OUTAGE_FALLBACK


def test_a_both_families_drawing_waits_for_the_reviewer_that_is_down(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm=None, pen_rod=None)
    both = {"drawing": "crank_arm", "family": "gpt", "commit": "c" * 40}
    both["both_families"] = BOTH
    rulings = ml.AuthorRulings({"crank_arm": both})
    [crank] = [
        r for r in _routes(checkout, tmp_path, {"crank_arm": both}) if r.families
    ]
    outage = ml.load_outages(_outages(tmp_path))["codex-401-test"]
    fake = FakeReviewer({("crank_arm", "claude"): "ship"})
    wave = _wave(tmp_path, checkout, fake, rulings=rulings, outage=outage)

    assert mw.run_wave([crank], wave, jobs=1) == {"crank_arm": mw.State.DOWN}
    # The claude half ran; the gpt half waits for codex, with no fallback.
    assert [call[:2] for call in fake.calls] == [("crank_arm", "claude")]
    entry = ml.load_ledger(tmp_path / "ledger.json")["drawings"]["crank_arm"]
    assert list(entry) == ["both_families_claude"]
    detail = wave.manifest.drawings["crank_arm"]["detail"]
    assert "gpt reviewer is down" in detail and "does not stand in" in detail
    assert mw.due(
        wave.manifest.drawings["crank_arm"],
        ml.sha256_file(crank.pdf),
        datetime.now(timezone.utc),
    )


def test_only_an_open_outage_reroutes_the_wave(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    monkeypatch.setattr(mr, "review_package", pytest.fail)
    argv = ["--checkout", str(checkout), "--ledger", str(tmp_path / "l.json")]
    argv += ["--outages", str(_outages(tmp_path))]

    assert mw.main([*argv, "--outage", "codex-401-test", "plan", *NAMES]) == 0
    out = capsys.readouterr().out
    assert [line.split()[:2] for line in out.splitlines()] == [
        ["crank_arm", "claude"],
        ["pen_rod", "claude"],
    ]
    assert mw.main([*argv, "--outage", "nope", "plan"]) == 2
    assert "no outage 'nope'" in capsys.readouterr().err

    ended = [
        "--outages",
        str(_outages(tmp_path, ended_at=datetime.now(timezone.utc).isoformat())),
    ]
    assert mw.main([*argv, *ended, "--outage", "codex-401-test", "plan"]) == 2
    assert "route cross-family" in capsys.readouterr().err


def test_a_ship_is_ingested_and_a_fix_is_left_with_its_counts(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer({("crank_arm", "codex"): "ship", ("pen_rod", "claude"): "fix"})
    wave = _wave(tmp_path, checkout, fake)

    outcome = mw.run_wave(_routes(checkout, tmp_path), wave, jobs=2)

    assert outcome == {"crank_arm": mw.State.INGESTED, "pen_rod": mw.State.FIX}
    ledger = ml.load_ledger(tmp_path / "ledger.json")["drawings"]
    assert list(ledger) == ["crank_arm"]
    assert ledger["crank_arm"]["cross_family"]["provenance"]["wave"] == "w1"
    status = ml.check(["crank_arm"], ledger_path=tmp_path / "ledger.json")[0]
    assert status.state == ml.State.OK
    saved = json.loads((mw.WAVE_ROOT / "w1" / "manifest.json").read_text("utf-8"))
    pen = saved["drawings"]["pen_rod"]
    assert pen["state"] == "fix"
    assert pen["attempts"][0]["findings"]["over_specification"] == 2
    assert pen["attempts"][0]["cost_usd"] == 0.25
    table = mw.table(saved)
    assert "ship-ingested: 1, fix: 1" in table
    assert "claude: 1 runs, $0.25 total" in table
    assert "codex: 1 runs, tokens per review {'output_tokens': 700}" in table


def test_a_quota_refusal_falls_back_to_the_last_resort_the_rule_allows(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # crank_arm: an Opus author, so a Fable reviewer is a valid last resort.
    # pen_rod: a ruled author with no trailer model, so it cannot be one.
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod=None)
    ruling = {"drawing": "pen_rod", "family": "claude", "commit": "c" * 40}
    fake = FakeReviewer(
        {
            ("crank_arm", "codex"): "quota",
            ("crank_arm", "claude"): "ship",
            ("pen_rod", "codex"): "quota",
        }
    )
    wave = _wave(tmp_path, checkout, fake)

    routes = _routes(checkout, tmp_path, {"pen_rod": ruling})
    outcome = mw.run_wave(routes, wave, jobs=2)

    assert outcome == {"crank_arm": mw.State.INGESTED, "pen_rod": mw.State.REFUSED}
    assert ("crank_arm", "claude", "claude-fable-5-1", "medium") in fake.calls
    entry = ml.load_ledger(tmp_path / "ledger.json")["drawings"]["crank_arm"]
    assert entry["last_resort"]["counts"]
    assert entry["last_resort"]["quota_refusal"]["reviewer"] == "codex"
    pen = wave.manifest.drawings["pen_rod"]
    assert "not in a trailer" in pen["detail"] and pen["retry_after"]
    kept = (
        mw.WAVE_ROOT / "w1" / "reviews" / "codex" / "pen_rod.codex.quota-refused.json"
    )
    assert kept.is_file()


def test_a_top_tier_author_gets_its_last_resort_at_high_effort(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-fable-5-1", pen_rod="claude-opus-5-5")
    fake = FakeReviewer(
        {("crank_arm", "codex"): "quota", ("crank_arm", "claude"): "ship"}
    )
    wave = _wave(tmp_path, checkout, fake)
    [crank] = [r for r in _routes(checkout, tmp_path) if r.name == "crank_arm"]

    assert mw.run_wave([crank], wave) == {"crank_arm": mw.State.INGESTED}
    assert fake.calls[-1] == ("crank_arm", "claude", "claude-fable-5-1", "high")


def test_refused_drawings_are_retried_after_the_backoff(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm=None, pen_rod=None)
    ruling = {"drawing": "crank_arm", "family": "gpt", "commit": "c" * 40}
    outcomes = {("crank_arm", "claude"): "quota"}
    fake = FakeReviewer(outcomes)
    # Routed and recorded under the same ruling: with none, the author of an
    # untrailered commit rests on nobody's authority and nothing counts.
    wave = _wave(
        tmp_path, checkout, fake, rulings=ml.AuthorRulings({"crank_arm": ruling})
    )
    [crank] = [
        r
        for r in _routes(checkout, tmp_path, {"crank_arm": ruling})
        if r.name == "crank_arm"
    ]
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        outcomes[("crank_arm", "claude")] = "ship"  # quota came back
        entry = wave.manifest.drawings["crank_arm"]
        entry["retry_after"] = datetime.now(timezone.utc).isoformat()

    outcome = mw.run_wave([crank], wave, quota_retries=1, sleep=sleep)

    assert outcome == {"crank_arm": mw.State.INGESTED}
    assert slept == [mw.QUOTA_BACKOFF.total_seconds()]
    assert [call[1] for call in fake.calls] == ["claude", "claude"]


def test_resume_reviews_only_what_is_not_settled_for_these_bytes(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer({("crank_arm", "codex"): "fix", ("pen_rod", "claude"): "fix"})
    wave = _wave(tmp_path, checkout, fake)
    mw.run_wave(_routes(checkout, tmp_path), wave)
    assert len(fake.calls) == 2

    # A crash after the reviewer returned, before the checkpoint recorded it,
    # leaves "running" and the report on disk: resuming adopts the report.
    # pen_rod was re-rendered since, so its verdict no longer applies.
    wave.manifest.update("crank_arm", state=mw.State.RUNNING)
    _sheet(checkout / "cad" / "out" / "pdf" / "pen-rod.pdf", note="PEN_ROD v2")
    fake.calls.clear()
    resumed = _wave(tmp_path, checkout, fake)
    outcome = mw.run_wave(_routes(checkout, tmp_path), resumed)
    assert [call[0] for call in fake.calls] == ["pen_rod"]
    assert outcome["crank_arm"] == mw.State.FIX
    assert resumed.manifest.drawings["crank_arm"]["attempts"][-1]["reused_report"]

    fake.calls.clear()
    mw.run_wave(_routes(checkout, tmp_path), _wave(tmp_path, checkout, fake))
    assert fake.calls == []  # both FIXed against the bytes rendered now


def test_an_ingested_drawing_blocked_again_gets_a_fresh_review(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    path = _outages(tmp_path)
    outage = ml.load_outages(path)["codex-401-test"]
    fake = FakeReviewer(
        {("crank_arm", "claude"): "ship", ("crank_arm", "codex"): "ship"}
    )
    ledger_path = tmp_path / "ledger.json"

    def routes(outages: dict) -> list[mw.Route]:
        failing, _ = mw.blocked(checkout, ledger_path, ("crank_arm",), None, outages)
        return mw.route(failing, checkout, ml.AuthorRulings())

    wave = _wave(tmp_path, checkout, fake, outage=outage)
    assert mw.run_wave(routes({outage["id"]: outage}), wave) == {
        "crank_arm": mw.State.INGESTED
    }
    assert routes({outage["id"]: outage}) == []  # accepted while the outage is open

    # Codex is back: the fallback no longer counts, so the same wave resumes it.
    ended = ml.load_outages(
        _outages(tmp_path, ended_at=datetime.now(timezone.utc).isoformat())
    )
    [crank] = routes(ended)
    fake.calls.clear()
    resumed = _wave(tmp_path, checkout, fake)
    assert mw.run_wave([crank], resumed) == {"crank_arm": mw.State.INGESTED}
    assert [call[:2] for call in fake.calls] == [("crank_arm", "codex")]
    entry = ml.load_ledger(ledger_path)["drawings"]["crank_arm"]
    assert ml.CROSS_FAMILY in entry


def test_a_ship_from_a_review_that_was_not_blind_is_retried_not_a_fix(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    outcomes = {("crank_arm", "codex"): "sighted"}
    fake = FakeReviewer(outcomes)
    [crank] = [r for r in _routes(checkout, tmp_path) if r.name == "crank_arm"]

    wave = _wave(tmp_path, checkout, fake)
    assert mw.run_wave([crank], wave) == {"crank_arm": mw.State.ERROR}
    assert "not blind" in wave.manifest.drawings["crank_arm"]["detail"]

    outcomes[("crank_arm", "codex")] = "ship"
    fake.calls.clear()
    assert mw.run_wave([crank], _wave(tmp_path, checkout, fake)) == {
        "crank_arm": mw.State.INGESTED
    }
    assert len(fake.calls) == 1  # reviewed again; the sighted report is not adopted


def test_a_pass_the_ledger_could_not_take_is_recorded_on_resume_for_free(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer({("crank_arm", "codex"): "ship"})
    [crank] = [r for r in _routes(checkout, tmp_path) if r.name == "crank_arm"]
    real = ml.record_review

    def locked(*args, **kwargs):
        raise PermissionError("the ledger is locked by another process")

    monkeypatch.setattr(ml, "record_review", locked)
    wave = _wave(tmp_path, checkout, fake)
    assert mw.run_wave([crank], wave) == {"crank_arm": mw.State.ERROR}
    assert "could not be written" in wave.manifest.drawings["crank_arm"]["detail"]

    monkeypatch.setattr(ml, "record_review", real)
    fake.calls.clear()
    resumed = _wave(tmp_path, checkout, fake)
    assert mw.run_wave([crank], resumed) == {"crank_arm": mw.State.INGESTED}
    assert fake.calls == []
    assert resumed.manifest.drawings["crank_arm"]["attempts"][-1]["reused_report"]


def test_a_requested_drawing_that_is_not_rendered_fails_the_run(
    tmp_path: Path, checkout: Path
) -> None:
    ml._current_pdf("crank_arm", checkout).unlink()
    argv = ["--checkout", str(checkout), "--ledger", str(tmp_path / "l.json")]

    assert mw.main([*argv, "run", "--wave", "w", "crank_arm"]) == 1

    saved = json.loads((mw.WAVE_ROOT / "w" / "manifest.json").read_text("utf-8"))
    assert saved["drawings"]["crank_arm"]["state"] == "unrendered"
    assert "no rendered PDF" in saved["drawings"]["crank_arm"]["detail"]


def test_a_checkpoint_taken_while_drawings_are_queued_can_be_resumed(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer({("crank_arm", "codex"): "ship", ("pen_rod", "claude"): "ship"})
    on_disk: list[str | None] = []

    def reviewing(package, **kwargs):
        # One job at a time: the other drawing is queued while this one runs.
        saved = mw.WAVE_ROOT / "w1" / "manifest.json"
        on_disk.append(mw.manifest_problem(json.loads(saved.read_text("utf-8"))))
        return fake(package, **kwargs)

    mw.run_wave(
        _routes(checkout, tmp_path), _wave(tmp_path, checkout, reviewing), jobs=1
    )

    assert on_disk == [None, None]


def test_a_report_never_checkpointed_is_charged_when_it_is_recovered(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer({("pen_rod", "claude"): "fix"})
    [pen] = [r for r in _routes(checkout, tmp_path) if r.name == "pen_rod"]
    wave = _wave(tmp_path, checkout, fake)
    mw.run_wave([pen], wave)
    # The process died after the report was written, before its checkpoint.
    wave.manifest.update("pen_rod", state=mw.State.RUNNING, attempts=[])
    fake.calls.clear()

    resumed = _wave(tmp_path, checkout, fake)
    mw.run_wave([pen], resumed)

    assert fake.calls == []  # recovered, not reviewed again
    [attempt] = resumed.manifest.drawings["pen_rod"]["attempts"]
    assert attempt["reused_report"] and attempt["cost_usd"] == 0.25
    assert "claude: 1 runs, $0.25 total" in mw.table(resumed.manifest.data)


def test_a_report_whose_flag_contradicts_its_verdict_is_not_adopted(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer({("crank_arm", "codex"): "ship"})
    [crank] = [r for r in _routes(checkout, tmp_path) if r.name == "crank_arm"]
    real = ml.record_review

    def locked(*args, **kwargs):
        raise PermissionError("the ledger is locked by another process")

    monkeypatch.setattr(ml, "record_review", locked)
    mw.run_wave([crank], _wave(tmp_path, checkout, fake))
    monkeypatch.setattr(ml, "record_review", real)
    report = mw.WAVE_ROOT / "w1" / "reviews" / "codex" / "crank_arm.json"
    data = json.loads(report.read_text(encoding="utf-8"))
    report.write_text(json.dumps({**data, "passed": False}), encoding="utf-8")
    fake.calls.clear()

    assert mw.run_wave([crank], _wave(tmp_path, checkout, fake)) == {
        "crank_arm": mw.State.INGESTED
    }
    assert len(fake.calls) == 1  # reviewed again, never settled as a FIX


def test_a_checkout_with_other_review_metadata_is_refused(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(ml, "checkout_metadata_problem", REAL_CHECKOUT_PROBLEM)
    argv = ["--checkout", str(checkout), "--ledger", str(tmp_path / "l.json")]

    assert mw.main([*argv, "run", "--wave", "w", "crank_arm"]) == 2
    assert "run that checkout's own" in capsys.readouterr().err
    assert mw.main([*argv, "plan"]) == 2
    assert not (mw.WAVE_ROOT / "w").exists()


class Crash(BaseException):
    """The process dying mid-run: nothing the wave catches."""


def test_a_lapsed_report_stays_lapsed_across_a_crash(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer({("crank_arm", "codex"): "ship"})
    [crank] = [r for r in _routes(checkout, tmp_path) if r.name == "crank_arm"]
    assert mw.run_wave([crank], _wave(tmp_path, checkout, fake)) == {
        "crank_arm": mw.State.INGESTED
    }
    (tmp_path / "ledger.json").unlink()  # its acceptance is withdrawn

    def dies(*args, **kwargs):
        raise Crash()

    with pytest.raises(Crash):  # marked for a fresh review, then the process dies
        mw.run_wave([crank], _wave(tmp_path, checkout, dies))
    fake.calls.clear()

    assert mw.run_wave([crank], _wave(tmp_path, checkout, fake)) == {
        "crank_arm": mw.State.INGESTED
    }
    assert len(fake.calls) == 1  # reviewed afresh, not the withdrawn report


def test_a_mimo_drawings_outage_alternative_is_an_ordinary_cross_family_review(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A Mimo author: Claude reviews it, and Codex is cross-family to it too.
    _authors(monkeypatch, crank_arm="mimo-v2.6-pro", pen_rod="gpt-6-sol")
    path = _outages(
        tmp_path,
        id="claude-down-test",
        reviewer="claude",
        fallback_reviewer="codex",
        fallback_model=mr.DEFAULT_MODELS["codex"],
    )
    outage = ml.load_outages(path)["claude-down-test"]
    fake = FakeReviewer({("crank_arm", "codex"): "ship"})
    [crank] = [r for r in _routes(checkout, tmp_path) if r.name == "crank_arm"]
    assert crank.reviewer == "claude"

    outcome = mw.run_wave([crank], _wave(tmp_path, checkout, fake, outage=outage))

    assert outcome == {"crank_arm": mw.State.INGESTED}
    ledger = ml.load_ledger(tmp_path / "ledger.json")["drawings"]
    assert list(ledger["crank_arm"]) == [ml.CROSS_FAMILY]


def test_a_later_uncheckpointed_report_is_charged_though_it_looks_like_an_old_one(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer({("pen_rod", "claude"): "fix"})
    [pen] = [r for r in _routes(checkout, tmp_path) if r.name == "pen_rod"]
    wave = _wave(tmp_path, checkout, fake)
    mw.run_wave([pen], wave)  # one paid FIX, checkpointed
    # A second paid run of the same drawing wrote its report, then the process
    # died before the checkpoint: same reviewer, model, effort, verdict.
    later = mr.ReviewPackage("pen_rod", "part", (pen.pdf,))
    fake(
        later,
        reviewer="claude",
        model=mr.DEFAULT_MODELS["claude"],
        effort=mr.DEFAULT_EFFORTS["claude"],
        report_dir=mw.WAVE_ROOT / "w1" / "reviews" / "claude",
    )
    report = mw.WAVE_ROOT / "w1" / "reviews" / "claude" / "pen_rod.json"
    data = json.loads(report.read_text(encoding="utf-8"))
    later_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    data["reviewed_at"] = later_at.isoformat(timespec="seconds")
    report.write_text(json.dumps(data), encoding="utf-8")
    wave.manifest.update("pen_rod", state=mw.State.RUNNING)

    resumed = _wave(tmp_path, checkout, fake)
    mw.run_wave([pen], resumed)

    assert "claude: 2 runs, $0.50 total" in mw.table(resumed.manifest.data)


def test_a_custom_rubric_report_is_not_adopted_on_resume(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer({("crank_arm", "codex"): "fix"})
    [crank] = [r for r in _routes(checkout, tmp_path) if r.name == "crank_arm"]
    wave = _wave(tmp_path, checkout, fake)
    mw.run_wave([crank], wave)
    report = mw.WAVE_ROOT / "w1" / "reviews" / "codex" / "crank_arm.json"
    data = json.loads(report.read_text(encoding="utf-8"))
    custom = "a custom rubric: be terse"  # what --prompt-file would have sent
    data["extra"]["evidence"]["effective_prompt"] = custom
    data["prompt_sha256"] = hashlib.sha256(custom.encode("utf-8")).hexdigest()
    report.write_text(json.dumps(data), encoding="utf-8")
    wave.manifest.update("crank_arm", state=mw.State.RUNNING)  # a crash
    fake.calls.clear()

    mw.run_wave([crank], _wave(tmp_path, checkout, fake))

    assert len(fake.calls) == 1  # a calibrated review, not the custom one


def test_a_new_outage_routes_a_refused_drawing_past_its_backoff(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # pen_rod: untrailered, so Claude's by the class rule; codex reviews it,
    # and with no trailer there is no last resort.
    rule = {"family": "claude", "ruled_by": "user", "ruled_at": "2026-09-25"}
    rulings = ml.AuthorRulings({}, rule)
    _authors(monkeypatch, crank_arm="gpt-6-sol", pen_rod=None)
    [pen] = [
        r for r in _routes(checkout, tmp_path, untrailered=rule) if r.name == "pen_rod"
    ]
    fake = FakeReviewer({("pen_rod", "codex"): "quota", ("pen_rod", "claude"): "ship"})
    assert mw.run_wave([pen], _wave(tmp_path, checkout, fake, rulings=rulings)) == {
        "pen_rod": mw.State.REFUSED
    }

    # Before its retry time, the user directs a fallback for the codex outage.
    outage = ml.load_outages(_outages(tmp_path))["codex-401-test"]
    resumed = _wave(tmp_path, checkout, fake, rulings=rulings, outage=outage)

    assert mw.run_wave([pen], resumed) == {"pen_rod": mw.State.INGESTED}
    assert fake.calls[-1][:2] == ("pen_rod", "claude")


def test_plan_lists_every_review_a_route_will_run(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _authors(monkeypatch, crank_arm=None, pen_rod=None)
    rulings = _author_rulings(tmp_path, family="gpt", both_families=BOTH)
    monkeypatch.setattr(mr, "review_package", pytest.fail)
    argv = ["--checkout", str(checkout), "--ledger", str(tmp_path / "l.json")]
    argv += ["--author-rulings", str(rulings)]

    assert mw.main([*argv, "plan", "crank_arm"]) == 0
    out, err = capsys.readouterr()
    assert "claude+codex" in out
    assert "1 blocked, 2 reviews: claude 1, codex 1" in err

    argv += ["--outages", str(_outages(tmp_path)), "--outage", "codex-401-test"]
    assert mw.main([*argv, "plan", "crank_arm"]) == 0
    out, err = capsys.readouterr()
    assert "claude+down" in out
    assert "1 blocked, 2 reviews: claude 1, down 1" in err


def test_a_reused_report_is_not_charged_again(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer({("pen_rod", "claude"): "ship"})
    [pen] = [r for r in _routes(checkout, tmp_path) if r.name == "pen_rod"]
    real = ml.record_review

    def locked(*args, **kwargs):
        raise PermissionError("the ledger is locked by another process")

    monkeypatch.setattr(ml, "record_review", locked)
    assert mw.run_wave([pen], _wave(tmp_path, checkout, fake)) == {
        "pen_rod": mw.State.ERROR
    }
    monkeypatch.setattr(ml, "record_review", real)
    resumed = _wave(tmp_path, checkout, fake)
    assert mw.run_wave([pen], resumed) == {"pen_rod": mw.State.INGESTED}

    table = mw.table(resumed.manifest.data)
    assert "claude: 1 runs, $0.25 total" in table  # one paid review, not two
    assert "reused" in table


def test_a_recovered_last_resort_pass_keeps_the_refusal_that_licensed_it(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # crank_arm: an Opus author, so codex reviews it and Fable is its last resort.
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer(
        {("crank_arm", "codex"): "quota", ("crank_arm", "claude"): "ship"}
    )
    [crank] = [r for r in _routes(checkout, tmp_path) if r.name == "crank_arm"]
    real = ml.record_review

    def locked(*args, **kwargs):
        raise PermissionError("the ledger is locked by another process")

    monkeypatch.setattr(ml, "record_review", locked)
    assert mw.run_wave([crank], _wave(tmp_path, checkout, fake)) == {
        "crank_arm": mw.State.ERROR
    }

    # Codex is still out of quota: the pass and its refusal are recovered as
    # a pair, with no reviewer call and no newer refusal replacing the old one.
    monkeypatch.setattr(ml, "record_review", real)
    fake.calls.clear()
    resumed = _wave(tmp_path, checkout, fake)
    assert mw.run_wave([crank], resumed) == {"crank_arm": mw.State.INGESTED}
    assert fake.calls == []
    entry = ml.load_ledger(tmp_path / "ledger.json")["drawings"]["crank_arm"]
    assert entry[ml.LAST_RESORT]["counts"]


def test_the_run_result_is_what_the_gate_blocks_now_not_the_waves_history(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer({("crank_arm", "codex"): "fix", ("pen_rod", "claude"): "ship"})
    wave = _wave(tmp_path, checkout, fake)
    assert mw.run_wave(_routes(checkout, tmp_path), wave, jobs=1) == {
        "crank_arm": mw.State.FIX,
        "pen_rod": mw.State.INGESTED,
    }
    # crank_arm is then accepted outside the wave, its PDF unchanged.
    pdf = ml._current_pdf("crank_arm", checkout)
    ship = FakeReviewer({("crank_arm", "codex"): "ship"})(
        mr.ReviewPackage("crank_arm", "part", (pdf,)),
        reviewer="codex",
        model="gpt-6-astra",
        effort="low",
        report_dir=tmp_path / "elsewhere",
    )
    ml.record_review(
        asdict(ship),
        pdf,
        author_family="claude",
        provenance={},
        ledger_path=tmp_path / "ledger.json",
        rulings=ml.AuthorRulings(),
    )
    argv = ["--checkout", str(checkout), "--ledger", str(tmp_path / "ledger.json")]
    argv += ["--author-rulings", str(tmp_path / "none.json")]

    # Named: nothing it names is blocked now, so the run succeeds.
    assert mw.main([*argv, "run", "--wave", "w1", "crank_arm", "pen_rod"]) == 0
    saved = json.loads((mw.WAVE_ROOT / "w1" / "manifest.json").read_text("utf-8"))
    assert saved["drawings"]["crank_arm"]["state"] == "fix"  # history is kept


@pytest.mark.parametrize(
    ("manifest", "error"),
    [
        ([], "is not an object"),
        ({"wave": "w", "drawings": []}, "drawings is not an object"),
        ({"wave": "w", "drawings": {"crank_arm": {"state": "bogus"}}}, "state 'bogus'"),
        (
            {"wave": "w", "drawings": {"crank_arm": {"state": "fix", "attempts": {}}}},
            "attempts is not a list",
        ),
    ],
)
def test_a_corrupt_manifest_is_refused_before_it_is_used(
    tmp_path: Path, checkout: Path, capsys, manifest, error: str
) -> None:
    path = mw.WAVE_ROOT / "w" / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    argv = ["--checkout", str(checkout), "--ledger", str(tmp_path / "l.json")]

    assert mw.main([*argv, "run", "--wave", "w", "crank_arm"]) == 2
    assert error in capsys.readouterr().err
    assert mw.main(["table", "--wave", "w"]) == 2
    assert error in capsys.readouterr().err


@pytest.mark.parametrize(
    "broken",
    [
        {"reviewed_at": "2026-09-25T10:00:00"},  # naive: cannot be ordered
        {"verdict": "FIX"},
        {"blind": "yes"},
    ],
    ids=["naive-time", "verdict-not-object", "blind-not-bool"],
)
def test_a_malformed_report_is_not_adopted_on_resume(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch, broken: dict
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer({("crank_arm", "codex"): "fix"})
    [crank] = [r for r in _routes(checkout, tmp_path) if r.name == "crank_arm"]
    wave = _wave(tmp_path, checkout, fake)
    mw.run_wave([crank], wave)
    report = mw.WAVE_ROOT / "w1" / "reviews" / "codex" / "crank_arm.json"
    data = json.loads(report.read_text(encoding="utf-8"))
    report.write_text(json.dumps({**data, **broken}), encoding="utf-8")
    wave.manifest.update("crank_arm", state=mw.State.RUNNING)  # a crash
    fake.calls.clear()

    mw.run_wave([crank], _wave(tmp_path, checkout, fake))

    assert len(fake.calls) == 1  # reviewed again, not adopted


def test_a_report_of_another_kind_is_not_adopted_on_resume(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    fake = FakeReviewer({("crank_arm", "codex"): "fix"})
    [crank] = [r for r in _routes(checkout, tmp_path) if r.name == "crank_arm"]
    wave = _wave(tmp_path, checkout, fake)
    mw.run_wave([crank], wave)
    report = mw.WAVE_ROOT / "w1" / "reviews" / "codex" / "crank_arm.json"
    data = json.loads(report.read_text(encoding="utf-8"))
    report.write_text(json.dumps({**data, "kind": "assembly"}), encoding="utf-8")
    wave.manifest.update("crank_arm", state=mw.State.RUNNING)  # a crash
    fake.calls.clear()

    mw.run_wave([crank], _wave(tmp_path, checkout, fake))

    assert len(fake.calls) == 1  # reviewed again, not adopted


def test_the_usage_examples_parse() -> None:
    usage = mw.__doc__.split("Usage")[1]
    lines = [
        line.split("machinist_wave.py", 1)[1].split()
        for line in usage.splitlines()
        if "machinist_wave.py" in line
    ]
    assert len(lines) == 4
    for argv in lines:
        argv = [arg.strip("[]") for arg in argv]  # an optional part, as typed
        mw._parse_args(["x" if arg.startswith("<") else arg for arg in argv])


def test_due_honours_the_refusal_backoff() -> None:
    now = datetime.now(timezone.utc)
    later = (now + timedelta(minutes=5)).isoformat()
    refused = {"state": "refused", "pdf_sha256": "s", "retry_after": later}
    assert not mw.due(refused, "s", now)
    assert mw.due(refused, "s", now + timedelta(minutes=6))
    assert mw.due(refused, "other bytes", now)
    assert not mw.due({"state": "fix", "pdf_sha256": "s"}, "s", now)
    # Routed again only when the gate blocks it again: its acceptance lapsed.
    assert mw.due({"state": "ship-ingested", "pdf_sha256": "s"}, "s", now)
    assert mw.due({"state": "running", "pdf_sha256": "s"}, "s", now)


def test_one_span_per_review_carries_reviewer_tier_and_duration(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod="gpt-6-sol")
    spans: list[dict] = []
    annotations: list[dict] = []

    class _Span:
        def __init__(self, name: str, attrs: dict) -> None:
            spans.append({"name": name, **attrs})

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def set_attributes(self, attrs: dict) -> None:
            annotations.append(attrs)

    monkeypatch.setattr(mw._telemetry, "span", lambda name, **a: _Span(name, a))
    fake = FakeReviewer({("crank_arm", "codex"): "ship", ("pen_rod", "claude"): "fix"})

    mw.run_wave(_routes(checkout, tmp_path), _wave(tmp_path, checkout, fake), jobs=1)

    reviews = [s for s in spans if s["name"] == "machinist.review"]
    assert {(s["drawing"], s["reviewer"], s["tier"]) for s in reviews} == {
        ("crank_arm", "codex", "top"),
        ("pen_rod", "claude", "top"),
    }
    assert all(a["duration_s"] == 12.5 for a in annotations)
    assert {a["verdict"] for a in annotations} == {"SHIP", "FIX"}


def test_run_spends_no_quota_without_names_or_all_blocked(
    tmp_path: Path, checkout: Path, capsys
) -> None:
    argv = ["--checkout", str(checkout), "--ledger", str(tmp_path / "l.json")]
    assert mw.main([*argv, "run", "--wave", "w"]) == 2
    assert "--all-blocked" in capsys.readouterr().err
    assert mw.main([*argv, "run", "--wave", "w", "--all-blocked", "crank_arm"]) == 2


def test_plan_routes_without_reviewing(
    tmp_path: Path, checkout: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _authors(monkeypatch, crank_arm="claude-opus-5-5", pen_rod=None)
    monkeypatch.setattr(mr, "review_package", pytest.fail)
    argv = ["--checkout", str(checkout), "--ledger", str(tmp_path / "l.json")]
    argv += ["--author-rulings", str(tmp_path / "none.json")]

    assert mw.main([*argv, "plan", *NAMES]) == 0

    out, err = capsys.readouterr()
    assert "crank_arm" in out and "codex" in out
    assert "UNROUTED" in out
    assert "2 blocked, 2 reviews: codex 1, unrouted 1" in err


def test_the_wave_tests_run_under_the_recipe_gate() -> None:
    dodo = (ml.REPO_ROOT / "dodo.py").read_text(encoding="utf-8")
    assert 'SCRIPTS_DIR / "test_machinist_wave.py"' in dodo


def test_a_review_record_round_trips(tmp_path: Path) -> None:
    # The fake writes what machinist_review writes; guard that the shapes agree.
    pdf = _sheet(tmp_path / "s.pdf")
    review = FakeReviewer({("x", "codex"): "ship"})(
        mr.ReviewPackage("x", "part", (pdf,)),
        reviewer="codex",
        model="gpt-6-astra",
        effort="low",
        report_dir=tmp_path / "r",
    )
    saved = json.loads((tmp_path / "r" / "x.json").read_text(encoding="utf-8"))
    assert saved == asdict(review)
