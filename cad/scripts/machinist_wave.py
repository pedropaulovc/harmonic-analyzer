r"""The machinist-review wave: every drawing the release gate blocks, reviewed once.

``check:machinist`` fails the release for every registry drawing whose rendered
sheets match no accepted, counting review in the ledger
(``machinist_ledger.py``).  This driver clears that list in one pass against a
checkout rendered at the release head:

* **Route** -- each blocked drawing goes to the reviewer of the other model
  family from its draw script's author: the model in the last commit's
  ``Co-Authored-By`` trailer, else ``cad/reviews/author-rulings.json``: a
  ruling on that drawing naming that exact commit, or the ``untrailered``
  class rule (the user's 2026-09-25 ruling: an untrailered commit is
  Claude's).  A drawing none of these covers is left unrouted, never guessed.
  Where a ruling and the class rule disagree (``both_families``), the drawing
  gets a review from each reviewer family it still lacks, and never a last
  resort, since its author model is not on record.
* **Review** -- ``machinist_review.review_package`` on the checkout's PDF,
  ``--jobs`` at a time (default 6).
* **Quota** -- a cross-family run refused for usage limits keeps its report as
  the refusal evidence.  When the author model is on record (a trailer) and
  the tier rule allows it, the same-family top-tier reviewer runs at once as
  the policy's last resort; otherwise the drawing is left ``refused`` and
  retried after ``--quota-backoff`` minutes (``--quota-retries`` times in this
  run, and on every resume).
* **Ingest** -- a passing review is recorded in the ledger through
  ``record_review``, so the family rule and the last-resort evidence are the
  ones every other entry meets.  A FIX is left for the author, with its counts.
* **Checkpoint** -- ``cad/out/reports/machinist-wave/<wave>/manifest.json`` is
  rewritten atomically on every state change.  Re-running the same ``--wave``
  resumes: a drawing already ingested or FIXed against the same PDF bytes is
  not reviewed again; anything else (pending, interrupted, refused, errored,
  or re-rendered since) is.
* **Telemetry** -- one ``machinist.review`` span per reviewer run, carrying the
  drawing, reviewer, model, tier, effort, slot, verdict, duration and cost
  (Claude's reported USD; Codex's token counts).

Usage (SolidWorks-free; the checkout's ``cad/out/pdf`` must be rendered)::

    uv run cad/scripts/machinist_wave.py plan [--checkout <dir>]
    uv run cad/scripts/machinist_wave.py run --wave <id> --all-blocked [--jobs 6]
    uv run cad/scripts/machinist_wave.py run --wave <id> crank_arm pen_rod
    uv run cad/scripts/machinist_wave.py table --wave <id>

``run`` reviews only the drawings it is given, or every blocked one with
``--all-blocked``: there is no default that spends reviewer quota.
"""

from __future__ import annotations

import argparse
import contextlib
import contextvars
import json
import os
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import _telemetry  # noqa: E402
import machinist_ledger as ml  # noqa: E402
import machinist_review as mr  # noqa: E402
from _drawing_registry import CAD_ROOT, DRAWINGS_BY_NAME  # noqa: E402

WAVE_ROOT = CAD_ROOT / "out" / "reports" / "machinist-wave"
DEFAULT_JOBS = 6
QUOTA_BACKOFF = timedelta(minutes=30)
# The same-family reviewer a last resort runs: the top tier of the author's family.
LAST_RESORT_REVIEWER = {"claude": "claude", "gpt": "codex"}


class State(StrEnum):
    PENDING = "pending"
    RUNNING = "running"  # a manifest left here by a crash is re-run on resume
    INGESTED = "ship-ingested"
    FIX = "fix"  # a verdict with gating findings; the author's to clear
    NOT_COUNTED = "not-counted"  # passed, but the ledger rule rejects the entry
    REFUSED = "refused"  # quota; retried after the backoff
    ERROR = "error"  # no verdict for another reason; retried on resume
    UNROUTED = "unrouted"  # no author family on record; never guessed


# Settled for these PDF bytes: resuming does not spend another review on them.
SETTLED = {State.INGESTED, State.FIX, State.NOT_COUNTED}


@dataclass(frozen=True)
class Route:
    name: str
    pdf: Path
    author_family: str | None
    author_model: str | None
    author_source: str  # "trailer" | "ruling" | ml.UNTRAILERED | ml.BOTH_FAMILIES | ""
    commit: str
    reviewer: str | None
    problem: str  # why it is unrouted; "" when routed
    families: tuple[str, ...] = ()  # reviewer families a both-families drawing lacks


def blocked(
    checkout: Path,
    ledger_path: Path,
    names: Sequence[str] = (),
    rulings: ml.AuthorRulings | None = None,
) -> tuple[dict[str, tuple[str, ...]], list[str]]:
    """Drawings the release gate blocks at ``checkout``, and those not rendered.

    Each blocked drawing maps to the reviewer families it still lacks when its
    ruling requires both families; to () otherwise.
    """
    rulings = ml.load_author_rulings() if rulings is None else rulings
    ledger = ml.load_ledger(ledger_path)
    references = ml._References(ml.sheets_dir(ledger_path))
    failing: dict[str, tuple[str, ...]] = {}
    unrendered: list[str] = []
    for name in names or list(DRAWINGS_BY_NAME):
        pdf = ml._current_pdf(name, checkout)
        status = ml.gate_status(
            name, ledger, references=references, rulings=rulings, pdf=pdf, repo=checkout
        )
        if status.state == ml.State.UNRENDERED:
            unrendered.append(name)
        elif status.state != ml.State.OK:
            failing[name] = status.missing
    return failing, unrendered


def route(
    failing: dict[str, tuple[str, ...]], checkout: Path, rulings: ml.AuthorRulings
) -> list[Route]:
    """The cross-family reviewer for each drawing, from its author on record.

    A drawing whose ruling requires both families is routed to each family it
    still lacks (``failing`` from ``blocked``), whoever its author was.
    """
    names = list(failing)
    authors = ml.draw_script_authors(names, repo=checkout) if names else {}
    routes: list[Route] = []
    for name in names:
        pdf = ml._current_pdf(name, checkout)
        author = authors[name]
        if isinstance(author, ValueError):
            routes.append(Route(name, pdf, None, None, "", "", None, str(author)))
            continue
        if rulings.both_families(name, author):
            families = failing[name] or ml.REVIEW_FAMILIES
            family = ml.other_family(families[0])  # the first review's cross author
            routes.append(
                Route(
                    name,
                    pdf,
                    family,
                    author.model,
                    ml.BOTH_FAMILIES,
                    author.commit,
                    ml.cross_family_reviewer(family),
                    "",
                    families,
                )
            )
            continue
        if author.model is not None:
            family, source, problem = ml.model_family(author.model), "trailer", ""
        else:
            family, source, _, problem = ml.ruled_family(name, author, rulings)
        reviewer = ml.cross_family_reviewer(family) if family else None
        routes.append(
            Route(
                name,
                pdf,
                family,
                author.model,
                source,
                author.commit,
                reviewer,
                problem,
            )
        )
    return routes


# --- manifest ----------------------------------------------------------------------


class Manifest:
    """The wave's checkpoint, rewritten atomically on every change."""

    def __init__(self, path: Path, data: dict[str, Any]) -> None:
        self.path = path
        self.data = data
        self.lock = threading.Lock()

    @classmethod
    def open(cls, path: Path, header: dict[str, Any]) -> Manifest:
        if path.is_file():  # resume: same wave, possibly a newer render
            data = json.loads(path.read_text(encoding="utf-8"))
            data.update({k: v for k, v in header.items() if k != "created_at"})
        else:
            data = {**header, "drawings": {}}
        data["resumed_at"] = _now()
        manifest = cls(path, data)
        manifest.save()
        return manifest

    @property
    def drawings(self) -> dict[str, dict[str, Any]]:
        return self.data["drawings"]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def update(self, name: str, **fields: Any) -> dict[str, Any]:
        with self.lock:
            entry = self.drawings.setdefault(name, {"name": name, "attempts": []})
            entry.update(fields)
            entry["updated_at"] = _now()
            self.save()
            return dict(entry)

    def add_attempt(self, name: str, attempt: dict[str, Any]) -> None:
        with self.lock:
            self.drawings[name]["attempts"].append(attempt)
            self.save()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def due(entry: dict[str, Any] | None, pdf_sha256: str, now: datetime) -> bool:
    """Whether a drawing needs a review run now, given its manifest entry."""
    if entry is None or entry.get("pdf_sha256") != pdf_sha256:
        return True
    state = State(entry["state"])
    if state in SETTLED:
        return False
    if state == State.REFUSED and entry.get("retry_after"):
        return now >= datetime.fromisoformat(entry["retry_after"])
    return True


# --- one drawing -------------------------------------------------------------------


def review_cost(events_file: str | None) -> dict[str, Any]:
    """What a review run cost, from its event stream.

    Claude reports USD per run; Codex reports tokens only.
    """
    cost: dict[str, Any] = {}
    if not events_file or not Path(events_file).is_file():
        return cost
    usd = 0.0
    tokens: Counter[str] = Counter()
    for line in Path(events_file).read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line).get("event") or {}
        except (json.JSONDecodeError, AttributeError):
            continue
        if event.get("type") == "result" and "total_cost_usd" in event:
            usd += float(event["total_cost_usd"] or 0)
        if event.get("type") == "turn.completed":
            for key, value in (event.get("usage") or {}).items():
                if isinstance(value, int):
                    tokens[key] += value
    if usd:
        cost["cost_usd"] = round(usd, 4)
    if tokens:
        cost["tokens"] = dict(tokens)
    return cost


ReviewFn = Callable[..., mr.Review]


@dataclass
class Wave:
    manifest: Manifest
    directory: Path
    ledger_path: Path
    checkout: Path
    review: ReviewFn = mr.review_package
    timeout_s: float = 1800.0
    retries: int = 1
    backoff: timedelta = QUOTA_BACKOFF
    rulings: ml.AuthorRulings = field(default_factory=ml.load_author_rulings)
    ledger_lock: threading.Lock = field(default_factory=threading.Lock)

    def run_one(self, route: Route) -> State:
        """Review one routed drawing, fall back on quota, ingest a pass.

        A both-families drawing gets one review per family it lacks, in turn,
        each recorded as cross-family to the other family; it stops at the
        first that is not ingested.
        """
        if not route.families:
            return self._run_one(route)
        state = State.INGESTED
        for family in route.families:
            author = ml.other_family(family)
            state = self._run_one(
                replace(
                    route,
                    author_family=author,
                    reviewer=ml.cross_family_reviewer(author),
                )
            )
            if state != State.INGESTED:
                return state
        return state

    def _run_one(self, route: Route) -> State:
        pdf_sha = ml.sha256_file(route.pdf)
        self.manifest.update(route.name, state=State.RUNNING, pdf_sha256=pdf_sha)
        review = self._attempt(route, route.reviewer, slot=ml.CROSS_FAMILY)
        if not self._quota_refused(review):
            return self._settle(route, review, None)
        refusal = self._refusal(route, review)
        fallback, why = (
            self._last_resort(route, refusal, pdf_sha)
            if refusal is not None
            else (None, "its refusal is not usable last-resort evidence")
        )
        if fallback is None:
            return self._refused(route, f"{route.reviewer} refused on quota; {why}")
        reviewer, model, effort = fallback
        review = self._attempt(
            route, reviewer, slot=ml.LAST_RESORT, model=model, effort=effort
        )
        if self._quota_refused(review):
            return self._refused(route, "both reviewer families refused on quota")
        return self._settle(route, review, refusal)

    def _refused(self, route: Route, detail: str) -> State:
        retry = datetime.now(timezone.utc) + self.backoff
        self.manifest.update(
            route.name,
            state=State.REFUSED,
            detail=detail,
            retry_after=retry.isoformat(timespec="seconds"),
        )
        return State.REFUSED

    def _report(self, reviewer: str, name: str) -> Path:
        return self.directory / "reviews" / reviewer / f"{name}.json"

    def _quota_refused(self, review: mr.Review) -> bool:
        if review.verdict is not None:
            return False
        report = self._report(review.reviewer, review.name)
        return ml.quota_evidence(asdict(review), report) is not None

    def _attempt(
        self,
        route: Route,
        reviewer: str,
        *,
        slot: str,
        model: str | None = None,
        effort: str | None = None,
    ) -> mr.Review:
        model = model or mr.DEFAULT_MODELS[reviewer]
        effort = effort or mr.DEFAULT_EFFORTS[reviewer]
        package = mr.ReviewPackage(
            route.name, DRAWINGS_BY_NAME[route.name].source_kind, (route.pdf,)
        )
        started = _now()
        with _telemetry.span(
            "machinist.review",
            drawing=route.name,
            reviewer=reviewer,
            model=model,
            tier=ml.model_tier(model),
            effort=effort,
            slot=slot,
            author_family=route.author_family,
        ) as span:
            review = self._finished(route, reviewer, model, effort)
            reused = review is not None
            if review is None:
                review = self.review(
                    package,
                    reviewer=reviewer,
                    model=model,
                    effort=effort,
                    report_dir=self.directory / "reviews" / reviewer,
                    retries=self.retries,
                    timeout_s=self.timeout_s,
                )
            verdict = (review.verdict or {}).get("verdict")
            cost = review_cost(review.events_file)
            # The checkpoint first: nothing after the reviewer returns may lose it.
            self.manifest.add_attempt(
                route.name,
                {
                    "reviewer": reviewer,
                    "model": model,
                    "effort": effort,
                    "slot": slot,
                    "started_at": started,
                    "duration_s": review.duration_s,
                    "verdict": verdict,
                    "passed": review.passed,
                    "findings": _findings(review),
                    "error": review.error,
                    "report": self._report(reviewer, route.name).as_posix(),
                    "reused_report": reused,
                    **cost,
                },
            )
            measured = {
                "verdict": verdict or "none",
                "passed": review.passed,
                "duration_s": review.duration_s,
                "reused_report": reused,
                "cost_usd": cost.get("cost_usd"),
                "output_tokens": (cost.get("tokens") or {}).get("output_tokens"),
                "error": review.error,
            }
            with contextlib.suppress(Exception):  # telemetry never costs a review
                span.set_attributes(
                    {k: v for k, v in measured.items() if v is not None}
                )
        return review

    def _finished(
        self, route: Route, reviewer: str, model: str, effort: str
    ) -> mr.Review | None:
        """A verdict this wave already has for these exact bytes, if any.

        A crash (or a failure) after the reviewer returned but before the
        checkpoint recorded it leaves the report on disk; resuming adopts it
        instead of spending the review again.
        """
        report = self._report(reviewer, route.name)
        if not report.is_file():
            return None
        try:
            review = mr.Review(**json.loads(report.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return None
        same = (
            review.source_sha256 == [ml.sha256_file(route.pdf)]
            and (review.model, review.effort) == (model, effort)
            and review.verdict is not None
        )
        return review if same else None

    def _refusal(self, route: Route, review: mr.Review) -> dict[str, Any] | None:
        """The cross-family refusal, kept where no later run overwrites it."""
        report_dir = self.directory / "reviews" / review.reviewer
        mr._keep_quota_refusal(review, report_dir)
        kept = mr.quota_refused_path(report_dir, route.name, review.reviewer)
        try:
            return ml.quota_refusal(
                kept, name=route.name, author_family=route.author_family or ""
            )
        except ValueError:
            return None

    def _last_resort(
        self, route: Route, refusal: dict[str, Any], pdf_sha: str
    ) -> tuple[tuple[str, str, str] | None, str]:
        """The same-family reviewer the last-resort rule allows here, or why none."""
        if route.author_source != "trailer" or route.author_model is None:
            return None, "no last resort: the author model is not in a trailer"
        reviewer = LAST_RESORT_REVIEWER.get(route.author_family or "")
        if reviewer is None:
            return None, f"no last resort: no {route.author_family} reviewer"
        model = mr.DEFAULT_MODELS[reviewer]
        effort = (
            "high"
            if ml.model_tier(route.author_model) == "top"
            else mr.DEFAULT_EFFORTS[reviewer]
        )
        problem = ml.last_resort_tier_problem(
            route.author_model, model, effort
        ) or ml.refusal_problem(refusal, pdf_sha256=pdf_sha, reviewed_at=_now())
        if problem:
            return None, f"no last resort: {problem}"
        return (reviewer, model, effort), ""

    def _settle(
        self, route: Route, review: mr.Review, refusal: dict[str, Any] | None
    ) -> State:
        if review.verdict is None:
            self.manifest.update(route.name, state=State.ERROR, detail=review.error)
            return State.ERROR
        if not review.passed:
            self.manifest.update(
                route.name,
                state=State.FIX,
                detail=f"{review.verdict.get('verdict')} {_findings(review)}",
            )
            return State.FIX
        slot = ml.review_slot(review.reviewer, route.author_family or "")
        try:
            with self.ledger_lock:  # the ledger file is read-modify-written
                recorded = ml.record_review(
                    asdict(review),
                    route.pdf,
                    author_family=route.author_family or "",
                    refusal=refusal if slot == ml.LAST_RESORT else None,
                    provenance={
                        "wave": self.manifest.data["wave"],
                        "checkout_head": self.manifest.data.get("head"),
                        "report": self._report(review.reviewer, route.name).as_posix(),
                    },
                    ledger_path=self.ledger_path,
                    repo=self.checkout,
                    rulings=self.rulings,
                )
        except (OSError, ValueError) as exc:
            self.manifest.update(route.name, state=State.NOT_COUNTED, detail=str(exc))
            return State.NOT_COUNTED
        if not recorded.counts:
            self.manifest.update(
                route.name,
                state=State.NOT_COUNTED,
                detail=f"{recorded.slot}: {recorded.problem}",
            )
            return State.NOT_COUNTED
        self.manifest.update(
            route.name,
            state=State.INGESTED,
            detail=f"{recorded.slot} {recorded.status}",
        )
        return State.INGESTED


def _findings(review: mr.Review) -> dict[str, int]:
    return {key: len((review.verdict or {}).get(key) or []) for key in mr.FINDING_KEYS}


# --- the wave ----------------------------------------------------------------------


def run_wave(
    routes: Sequence[Route],
    wave: Wave,
    *,
    jobs: int = DEFAULT_JOBS,
    quota_retries: int = 0,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, State]:
    """Review every due, routed drawing ``jobs`` at a time; checkpoint each."""
    for route in routes:
        if route.reviewer is None:
            wave.manifest.update(
                route.name,
                state=State.UNROUTED,
                detail=route.problem,
                pdf_sha256=ml.sha256_file(route.pdf),
            )
        else:
            wave.manifest.update(
                route.name,
                author={
                    "family": route.author_family,
                    "model": route.author_model,
                    "source": route.author_source,
                    "commit": route.commit,
                },
                reviewer=route.reviewer,
            )
    outcome: dict[str, State] = {}
    pending = [route for route in routes if route.reviewer is not None]
    for round_ in range(quota_retries + 1):
        now = datetime.now(timezone.utc)
        todo = [
            route
            for route in pending
            if due(
                wave.manifest.drawings.get(route.name), ml.sha256_file(route.pdf), now
            )
        ]
        with _telemetry.span("machinist.wave.round", round=round_, drawings=len(todo)):
            with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
                futures = {
                    pool.submit(
                        contextvars.copy_context().run, wave.run_one, route
                    ): route
                    for route in todo
                }
                for future in as_completed(futures):
                    route = futures[future]
                    try:
                        outcome[route.name] = future.result()
                    except Exception as exc:  # noqa: BLE001 - one drawing must not sink the wave
                        wave.manifest.update(
                            route.name,
                            state=State.ERROR,
                            detail=f"{type(exc).__name__}: {exc}",
                        )
                        outcome[route.name] = State.ERROR
        refused = [n for n, state in outcome.items() if state == State.REFUSED]
        if not refused or round_ == quota_retries:
            break
        _telemetry.info(
            f"{len(refused)} drawings refused on quota; retrying in "
            f"{wave.backoff / timedelta(minutes=1):g} min"
        )
        sleep(wave.backoff.total_seconds())
        pending = [route for route in pending if route.name in refused]
    for name, entry in wave.manifest.drawings.items():
        outcome.setdefault(name, State(entry["state"]))
    return outcome


def table(manifest: dict[str, Any]) -> str:
    """The wave's outcome: one row per drawing, then counts and cost."""
    rows = sorted(
        manifest["drawings"].values(),
        key=lambda e: (list(State).index(State(e["state"])), e["name"]),
    )
    lines = [
        f"{'state':<14} {'drawing':<30} {'reviewer/model':<28} {'b/o/c/m':<9} "
        f"{'secs':>6} {'cost':>9}  detail"
    ]
    usd = 0.0
    priced = 0
    tokens: Counter[str] = Counter()
    token_runs = 0
    for entry in rows:
        last = (entry.get("attempts") or [{}])[-1]
        findings = last.get("findings") or {}
        counts = "/".join(str(findings.get(k, "-")) for k in mr.FINDING_KEYS)
        for attempt in entry.get("attempts") or []:
            if "cost_usd" in attempt:
                usd += attempt["cost_usd"]
                priced += 1
            if "tokens" in attempt:
                tokens.update(attempt["tokens"])
                token_runs += 1
        cost = (
            f"${last['cost_usd']:.2f}"
            if "cost_usd" in last
            else f"{(last.get('tokens') or {}).get('output_tokens', '-')} tok"
            if last
            else "-"
        )
        who = f"{last.get('reviewer', '-')}/{last.get('model', '-')}"
        lines.append(
            f"{entry['state']:<14} {entry['name']:<30} {who:<28} {counts:<9} "
            f"{last.get('duration_s', '-')!s:>6} {cost:>9}  {entry.get('detail') or ''}"
        )
    states = Counter(entry["state"] for entry in manifest["drawings"].values())
    lines.append(", ".join(f"{state}: {states[state]}" for state in State))
    if priced:
        lines.append(
            f"claude: {priced} runs, ${usd:.2f} total, ${usd / priced:.2f} per review"
        )
    if token_runs:
        per = {k: round(v / token_runs) for k, v in tokens.items()}
        lines.append(f"codex: {token_runs} runs, tokens per review {per}")
    return "\n".join(lines)


# --- CLI ---------------------------------------------------------------------------


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ledger", type=Path, default=ml.LEDGER_PATH)
    parser.add_argument(
        "--checkout",
        type=Path,
        default=ml.REPO_ROOT,
        help="checkout rendered at the release head (its cad/out/pdf and draw-script "
        "history)",
    )
    parser.add_argument("--author-rulings", type=Path, default=ml.AUTHOR_RULINGS_PATH)
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan", help="route the blocked drawings; review none")
    plan.add_argument("names", nargs="*")

    run = commands.add_parser("run", help="review and ingest")
    run.add_argument("names", nargs="*")
    run.add_argument("--wave", required=True, help="wave id; the same id resumes")
    run.add_argument(
        "--all-blocked", action="store_true", help="every drawing the gate blocks"
    )
    run.add_argument("--jobs", type=int, default=DEFAULT_JOBS)
    run.add_argument("--retries", type=int, default=1)
    run.add_argument("--timeout", type=float, default=1800.0)
    run.add_argument("--quota-retries", type=int, default=0)
    run.add_argument(
        "--quota-backoff",
        type=float,
        default=QUOTA_BACKOFF / timedelta(minutes=1),
        help="minutes before a refused drawing is tried again",
    )

    show = commands.add_parser("table", help="print a wave's outcome")
    show.add_argument("--wave", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return _run(args)
    except (OSError, ValueError) as exc:
        print(f"{args.command}: {exc}", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    _telemetry.set_service("machinist-wave")
    if args.command == "table":
        manifest = WAVE_ROOT / args.wave / "manifest.json"
        print(table(json.loads(manifest.read_text(encoding="utf-8"))))
        return 0
    unknown = [n for n in args.names if n not in DRAWINGS_BY_NAME]
    if unknown:
        raise ValueError(f"unknown drawing names: {unknown}")
    if args.command == "run" and bool(args.names) == args.all_blocked:
        raise ValueError(
            "name the drawings to review, or pass --all-blocked (not both)"
        )
    rulings = ml.load_author_rulings(args.author_rulings)
    failing, unrendered = blocked(args.checkout, args.ledger, args.names, rulings)
    routes = route(failing, args.checkout, rulings)
    if unrendered:
        print(f"unrendered, not reviewed: {', '.join(unrendered)}", file=sys.stderr)
    if args.command == "plan":
        for r in routes:
            print(
                f"{r.name:<32} {r.reviewer or 'UNROUTED':<8} author "
                f"{r.author_family or '?'} ({r.author_source or r.problem})"
            )
        by = Counter(r.reviewer or "unrouted" for r in routes)
        print(
            f"{len(routes)} blocked: " + ", ".join(f"{k} {v}" for k, v in by.items()),
            file=sys.stderr,
        )
        return 0
    directory = WAVE_ROOT / args.wave
    manifest = Manifest.open(
        directory / "manifest.json",
        {
            "wave": args.wave,
            "checkout": args.checkout.resolve().as_posix(),
            "head": ml._checkout_head(args.checkout),
            "ledger": args.ledger.resolve().as_posix(),
            "created_at": _now(),
        },
    )
    wave = Wave(
        manifest,
        directory,
        args.ledger,
        args.checkout,
        timeout_s=args.timeout,
        retries=args.retries,
        backoff=timedelta(minutes=args.quota_backoff),
        rulings=rulings,
    )
    with _telemetry.span(
        "machinist.wave", wave=args.wave, drawings=len(routes), jobs=args.jobs
    ):
        outcome = run_wave(
            routes, wave, jobs=args.jobs, quota_retries=args.quota_retries
        )
    print(table(manifest.data))
    return 0 if all(state == State.INGESTED for state in outcome.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
