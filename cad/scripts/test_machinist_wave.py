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
from test_machinist_ledger import CODEX_REFUSAL, _outages, _sheet, _verdict

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


class FakeReviewer:
    """Stands in for review_package: a verdict per (drawing, reviewer), or quota."""

    def __init__(self, outcomes: dict[tuple[str, str], str]) -> None:
        self.outcomes = outcomes  # "ship" | "fix" | "quota"
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
            verdict = _verdict(passed=outcome == "ship")
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
            blind=True,
            tool_events=0,
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
    wave = _wave(tmp_path, checkout, fake)
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


def test_due_honours_the_refusal_backoff() -> None:
    now = datetime.now(timezone.utc)
    later = (now + timedelta(minutes=5)).isoformat()
    refused = {"state": "refused", "pdf_sha256": "s", "retry_after": later}
    assert not mw.due(refused, "s", now)
    assert mw.due(refused, "s", now + timedelta(minutes=6))
    assert mw.due(refused, "other bytes", now)
    assert not mw.due({"state": "ship-ingested", "pdf_sha256": "s"}, "s", now)
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
    assert "2 blocked: codex 1, unrouted 1" in err


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
