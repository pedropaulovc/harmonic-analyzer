"""Compare two blind drawing-review rubrics against frozen calibration images.

No SolidWorks session is needed. These fixtures are calibration inputs, not native
release evidence. SHIP/FIX describes the whole sheet, not the targeted fit score.
Results remain unassessed until a human supplies --assessments JSON:

    {"schema_version": 1, "run_id": "<aggregate run_id>", "assessments": {
      "baseline": {"<case name>": {"report_sha256": "<result report_sha256>",
        "outcome": "pass", "justification": "Explain the targeted expectation",
        "evidence": ["/over_specification/0", "/blockers"]}}}}

Evidence references address the report's verdict: a finding, category (including
an empty category for absence claims), or /summary. No keyword scoring is used.
Only pass/fail are human outcomes. Invalid evidence is an infrastructure failure;
unassessed evidence and targeted failures remain usable experiment outcomes.

Each invocation resumes matching valid results automatically. Inputs, engine and
schema hashes, model, effort, timeout and retry settings define the run identity.
Use a separate report directory for an independent repeat of identical inputs.
Concurrent invocations must not share a report directory. Each completed case is
checkpointed atomically; interrupted/invalid cases rerun without overwriting old
attempt artifacts. stdout contains only aggregate JSON; telemetry uses stderr.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
from typing import Any, Sequence

import _telemetry as telemetry
import machinist_review as mr

DEFAULT_CASES = mr.CAD_ROOT / "comparisons" / "bench" / "machinist_review" / "manifest.json"
VERSIONS = ("baseline", "candidate")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
    ) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2)
        stream.write("\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_cases(manifest: Path) -> tuple[dict[str, Any], list[mr.ReviewPackage]]:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("case manifest requires schema_version 1")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("case manifest requires non-empty cases")
    packages = []
    names: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each case must be an object")
        name = case.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", name):
            raise ValueError("case names must be safe lowercase identifiers")
        if name in names:
            raise ValueError(f"duplicate case: {name}")
        names.add(name)
        if not isinstance(case.get("expected_behavior"), str) or not case["expected_behavior"].strip():
            raise ValueError(f"{name}: expected_behavior is required")
        image_path = case.get("path")
        if not isinstance(image_path, str) or Path(image_path).is_absolute():
            raise ValueError(f"{name}: image path must be relative to the manifest")
        image = (manifest.parent / image_path).resolve()
        if not image.is_relative_to(manifest.parent.resolve()) or image.suffix.lower() != ".png":
            raise ValueError(f"{name}: expected a PNG within the manifest directory")
        if mr._sha256(image) != case.get("sha256"):
            raise ValueError(f"{name}: image hash differs from frozen manifest")
        kind = case.get("package_kind", "part")
        package = mr.ReviewPackage(name, kind, (image,))
        mr._validate_package(package)
        packages.append(package)
    return data, packages


def make_identity(
    manifest: dict[str, Any], packages: Sequence[mr.ReviewPackage],
    prompts: dict[str, bytes], *, reviewer: str, model: str, effort: str,
    retries: int, timeout_s: float,
) -> dict[str, Any]:
    """Content identity, independent of checkout and output directory locations."""
    return {
        "schema_version": 1,
        "manifest": manifest,
        "engine_sha256": mr._sha256(Path(mr.__file__)),
        "evaluator_sha256": mr._sha256(Path(__file__)),
        "schema_sha256": mr._sha256(mr.SCHEMA_FILE),
        "reviewer": reviewer, "model": model, "effort": effort,
        "retries": retries, "timeout_s": timeout_s,
        "prompts": {
            version: {"raw_sha256": hashlib.sha256(raw).hexdigest(),
                      "effective_sha256": {
                          package.name: hashlib.sha256(mr._review_prompt(
                              package, 1, reviewer=reviewer,
                              prompt_text=raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n"),
                          ).encode("utf-8")).hexdigest()
                          for package in packages}}
            for version, raw in prompts.items()
        },
        "images": {p.name: [mr._sha256(source) for source in p.sources] for p in packages},
    }


def validate_evidence(
    result: dict[str, Any], identity: dict[str, Any], version: str,
    package: mr.ReviewPackage, directory: Path,
) -> mr.Review:
    """Reject stale, incomplete or non-blind checkpoints, independently of SHIP."""
    if result.get("run_id") != _digest(identity) or result.get("case") != package.name or result.get("version") != version:
        raise ValueError("checkpoint identity mismatch")
    if result.get("error") is not None:
        raise ValueError(f"case failed: {result['error']}")
    report_path = directory / result["report"]
    events_path = directory / result["events"]
    for path in (report_path, events_path):
        if not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError("evidence path escapes case directory")
    if mr._sha256(report_path) != result["report_sha256"] or mr._sha256(events_path) != result["events_sha256"]:
        raise ValueError("evidence hash mismatch")
    review = mr.Review(**json.loads(report_path.read_text(encoding="utf-8")))
    if result.get("review") != asdict(review):
        raise ValueError("checkpoint review differs from preserved report")
    mr.validate_verdict(review.verdict)
    expected = {
        "name": package.name, "kind": package.kind, "sheet_count": 1,
        "source_sha256": identity["images"][package.name],
        "prompt_sha256": identity["prompts"][version]["effective_sha256"][package.name],
        "reviewer": identity["reviewer"], "model": identity["model"], "effort": identity["effort"],
    }
    if any(getattr(review, key) != value for key, value in expected.items()):
        raise ValueError("report inputs/settings mismatch")
    if review.error is not None or review.blind is not True or type(review.tool_events) is not int or review.tool_events != 0:
        raise ValueError("report lacks valid blind evidence")
    if type(review.attempts) is not int or not 1 <= review.attempts <= identity["retries"] + 1:
        raise ValueError("invalid attempt count")
    if review.passed is not mr.is_pass(review.verdict):
        raise ValueError("inconsistent whole-sheet pass flag")
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not events or any(
        not isinstance(row, dict) or type(row.get("attempt")) is not int
        or not 1 <= row["attempt"] <= review.attempts or not isinstance(row.get("event"), dict)
        for row in events
    ):
        raise ValueError("missing or malformed retry event history")
    successful = [row["event"] for row in events if row["attempt"] == review.attempts]
    if identity["reviewer"] == "codex":
        if mr.count_codex_tool_events(events):
            raise ValueError("unauthorized tool activity")
        # Re-extract from the event stream where available; Codex may instead
        # have written only its schema-validated output file in the neutral cwd.
        if not successful:
            raise ValueError("missing successful attempt events")
        if any(
            isinstance(node, dict) and node.get("type") == "agent_message"
            for node in mr._walk(successful)
        ) and mr.extract_codex_verdict(directory, successful) != review.verdict:
            raise ValueError("report differs from successful Codex event verdict")
    else:
        for attempt in range(1, review.attempts + 1):
            attempt_events = [row["event"] for row in events if row["attempt"] == attempt]
            allowed: set[Path] = set()
            for node in mr._walk(attempt_events):
                if isinstance(node, dict) and str(node.get("name", "")).lower() == "read":
                    arguments = node.get("input")
                    if isinstance(arguments, dict) and isinstance(arguments.get("file_path"), str):
                        path = Path(arguments["file_path"])
                        if path.is_absolute() and path.parent.name.startswith("machrev-") and path.name == "sheet-1.png":
                            allowed.add(path.resolve())
            # Relative Read paths are legitimate in the engine's neutral cwd.
            # If the event stream never names that cwd, a stand-in resolves only
            # the permitted relative filename; no filesystem access occurs here.
            if not allowed:
                allowed.add((directory / "neutral-evidence" / "sheet-1.png").resolve())
            unauthorized, inspected = mr._claude_event_evidence(
                attempt_events, allowed_images=tuple(allowed)
            )
            if unauthorized or (attempt == review.attempts and len(inspected) != 1):
                raise ValueError("event history does not prove a blind image review")
        if mr.extract_claude_verdict(successful) != review.verdict:
            raise ValueError("report differs from successful Claude event verdict")
    return review


def run_case(
    identity: dict[str, Any], version: str, package: mr.ReviewPackage,
    prompt_text: str, directory: Path,
) -> dict[str, Any]:
    checkpoint = directory / "result.json"
    if checkpoint.exists():
        try:
            if [mr._sha256(p) for p in package.sources] != identity["images"][package.name]:
                raise ValueError("image changed after run identity was computed")
            cached = json.loads(checkpoint.read_text(encoding="utf-8"))
            validate_evidence(cached, identity, version, package, directory)
            telemetry.info("Resuming review evaluation", case=package.name, version=version)
            return cached
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            telemetry.warn("Discarding unusable checkpoint", case=package.name, reason=str(exc))
    directory.mkdir(parents=True, exist_ok=True)
    attempt_dir = Path(tempfile.mkdtemp(prefix="attempt-", dir=directory))
    result: dict[str, Any] = {
        "run_id": _digest(identity), "case": package.name, "version": version,
        "error": None,
    }
    try:
        if [mr._sha256(p) for p in package.sources] != identity["images"][package.name]:
            raise ValueError("image changed after run identity was computed")
        review = mr.review_package(
            package, reviewer=identity["reviewer"], model=identity["model"],
            effort=identity["effort"], retries=identity["retries"],
            timeout_s=identity["timeout_s"], prompt_text=prompt_text, report_dir=attempt_dir,
        )
        report_path = attempt_dir / f"{package.name}.json"
        events_path = attempt_dir / f"{package.name}.events.jsonl"
        result.update({
            "report": report_path.relative_to(directory).as_posix(),
            "report_sha256": mr._sha256(report_path),
            "events": events_path.relative_to(directory).as_posix(),
            "events_sha256": mr._sha256(events_path),
            "review": asdict(review),
        })
        if [mr._sha256(p) for p in package.sources] != identity["images"][package.name]:
            raise ValueError("image changed during review")
        validate_evidence(result, identity, version, package, directory)
    except Exception as exc:  # one failed provider must not lose completed cases
        result["error"] = f"{type(exc).__name__}: {exc}"
    _atomic_json(checkpoint, result)
    telemetry.info("Completed review evaluation", case=package.name, version=version, error=result["error"])
    return result


def aggregate(
    identity: dict[str, Any], results: list[dict[str, Any]],
    assessments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_id = _digest(identity)
    adjudications: dict[str, Any] = {}
    if assessments is not None:
        if not isinstance(assessments, dict) or set(assessments) != {"schema_version", "run_id", "assessments"} or assessments["schema_version"] != 1 or assessments["run_id"] != run_id:
            raise ValueError("assessment run identity/schema mismatch")
        adjudications = assessments["assessments"]
        if not isinstance(adjudications, dict) or set(adjudications) - set(VERSIONS):
            raise ValueError("unknown assessment version")
        for version, cases in adjudications.items():
            if not isinstance(cases, dict) or set(cases) - {r["case"] for r in results if r["version"] == version}:
                raise ValueError("unknown assessment case")
    counts = {version: dict.fromkeys(("pass", "fail", "unassessed", "invalid"), 0) for version in VERSIONS}
    rows = []
    for result in results:
        row = dict(result)
        version_assessments = adjudications.get(row["version"], {})
        assessment = version_assessments.get(row["case"])
        row["outcome"] = "invalid" if row["error"] else "unassessed"
        if row["case"] in version_assessments:
            if row["error"]:
                raise ValueError("cannot assess invalid model evidence")
            if not isinstance(assessment, dict) or set(assessment) != {"report_sha256", "outcome", "justification", "evidence"}:
                raise ValueError("assessment fields must be exact")
            if assessment["report_sha256"] != row["report_sha256"]:
                raise ValueError("stale assessment report hash")
            if assessment["outcome"] not in ("pass", "fail") or not isinstance(assessment["justification"], str) or not assessment["justification"].strip():
                raise ValueError("assessment requires pass/fail and human justification")
            evidence = assessment["evidence"]
            if not isinstance(evidence, list) or not evidence:
                raise ValueError("assessment requires report evidence references")
            verdict = row["review"]["verdict"]
            for reference in evidence:
                if not isinstance(reference, str) or not re.fullmatch(r"/(summary|blockers|over_specification|clarity|minor)(/\d+)?", reference):
                    raise ValueError("invalid assessment evidence reference")
                parts = reference.split("/")[1:]
                if len(parts) == 2 and (parts[0] == "summary" or int(parts[1]) >= len(verdict[parts[0]])):
                    raise ValueError("assessment references a missing finding")
            row["outcome"] = assessment["outcome"]
            row["assessment"] = assessment
        counts[row["version"]][row["outcome"]] += 1
        rows.append(row)
    return {"schema_version": 1, "run_id": run_id, "identity": identity,
            "counts": counts, "results": rows}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--reviewer", choices=mr.REVIEWERS, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=1800.0, help="seconds per provider attempt")
    parser.add_argument("--assessments", type=Path, help="human-authored assessment JSON; see format above")
    args = parser.parse_args(argv)
    if args.jobs < 1 or args.retries < 0 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("jobs/timeout must be positive and retries non-negative")
    try:
        manifest, packages = load_cases(args.cases)
        prompts = {v: getattr(args, v).read_bytes() for v in VERSIONS}
        identity = make_identity(manifest, packages, prompts, reviewer=args.reviewer,
                                 model=args.model, effort=args.effort, retries=args.retries, timeout_s=args.timeout)
        assessments = json.loads(args.assessments.read_text(encoding="utf-8")) if args.assessments else None
        if args.assessments and (
            not isinstance(assessments, dict)
            or assessments.get("run_id") != _digest(identity)
        ):
            raise ValueError("assessment run identity mismatch")
        run_dir = args.report_dir.resolve() / _digest(identity)
        _atomic_json(run_dir / "identity.json", identity)
        results = []
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(
                run_case, identity, version, package,
                prompts[version].decode("utf-8").replace("\r\n", "\n").replace("\r", "\n"),
                run_dir / version / package.name,
            ) for version in VERSIONS for package in packages]
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda r: (r["version"], r["case"]))
        summary = aggregate(identity, results, assessments)
        _atomic_json(run_dir / "results.json", summary)
        print(json.dumps(summary, indent=2))
        return int(any(r["outcome"] == "invalid" for r in summary["results"]))
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        telemetry.error("Evaluation failed", reason=str(exc))
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
