"""Calibrate the shadow drawing-change gate's judge variants on labeled real sheets.

The manifest is a JSON list of ``{"id", "before", "after", "kind", "expected",
"label_source"}`` objects. ``before``/``after`` are PDFs (absolute, or relative to
the repository root); ``expected`` is ``noise`` or ``meaningful`` and
``label_source`` states how the pair was produced, which is what justifies the
label. Every pair runs ``--repeats`` times per variant, each as its own gate CLI
process (PDFium is not thread-safe), through a bounded pool. Every sidecar lands
in ``<out-dir>/runs/``; ``<out-dir>/calibration.json`` holds every run and, per
variant, the expected-by-observed confusion matrix (``unsure`` included), false
noise with the judge's reason verbatim, the false-meaningful rate, per-pair
stability across repeats, wall times and errors.

False noise is the dangerous error: it would skip a needed review. False
meaningful only costs a review.

Run from the repository root, without SolidWorks::

    uv run --frozen python cad/scripts/diagnostics/change_gate_calibration.py \
        --manifest MANIFEST.json --out-dir DIR [--repeats 3] [--jobs 6]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE = REPO_ROOT / "cad" / "scripts" / "machinist_review_change_gate.py"
VARIANTS = ("precheck", "side_by_side")
EXPECTED = ("noise", "meaningful")
OBSERVED = ("noise", "meaningful", "unsure")
# The gate's own judge budget is 600 s per attempt with one retry.
RUN_TIMEOUT_S = 1500.0


def load_manifest(path: Path) -> list[dict[str, Any]]:
    """Validate every pair before any model call; resolve paths to the repo root."""
    pairs = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("manifest must be a nonempty JSON list")
    seen: set[str] = set()
    for pair in pairs:
        keys = {"id", "before", "after", "kind", "expected", "label_source"}
        if not isinstance(pair, dict) or set(pair) != keys:
            raise ValueError(
                f"manifest entry must have exactly {sorted(keys)}: {pair!r}"
            )
        if pair["id"] in seen:
            raise ValueError(f"duplicate manifest id {pair['id']!r}")
        seen.add(pair["id"])
        if pair["expected"] not in EXPECTED:
            raise ValueError(f"{pair['id']}: expected must be one of {EXPECTED}")
        if not str(pair["label_source"]).strip():
            raise ValueError(f"{pair['id']}: label_source must justify the label")
        for side in ("before", "after"):
            resolved = Path(pair[side])
            resolved = resolved if resolved.is_absolute() else REPO_ROOT / resolved
            if not resolved.is_file():
                raise ValueError(f"{pair['id']}: {side} PDF not found: {resolved}")
            pair[side] = str(resolved)
    return pairs


def _run(
    pair: dict[str, Any], variant: str, repeat: int, runs_dir: Path
) -> dict[str, Any]:
    name = f"{pair['id']}.{variant}.r{repeat}"
    command = [
        sys.executable,
        str(GATE),
        "--before",
        pair["before"],
        "--after",
        pair["after"],
        "--kind",
        pair["kind"],
        "--name",
        name,
        "--out-dir",
        str(runs_dir),
        "--judge-variant",
        variant,
    ]
    record: dict[str, Any] = {
        "id": pair["id"],
        "variant": variant,
        "repeat": repeat,
        "expected": pair["expected"],
        "observed": None,
        "stage": None,
        "judge_model": None,
        "judge_error": None,
        "process_error": None,
        "prompt_sha256": None,
        "reason": None,
        "sidecar": None,
    }
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=REPO_ROOT,
            env=_telemetry.inject_env(),
            timeout=RUN_TIMEOUT_S,
        )
        (runs_dir / f"{name}.log").write_text(
            completed.stdout + completed.stderr, encoding="utf-8"
        )
        if completed.returncode != 0:
            record["process_error"] = f"gate exit {completed.returncode}"
    except subprocess.TimeoutExpired:
        record["process_error"] = f"gate timed out after {RUN_TIMEOUT_S:g} s"
    record["wall_s"] = round(time.monotonic() - started, 1)
    sidecar = runs_dir / f"{name}.change-gate.json"
    if record["process_error"] is None and sidecar.is_file():
        result = json.loads(sidecar.read_text(encoding="utf-8"))
        record.update(
            observed=result["verdict"],
            stage=result["stage"],
            judge_model=result["judge_model"],
            judge_error=result["judge_error"],
            prompt_sha256=result["prompt_sha256"],
            reason=result["reason"],
            sidecar=str(sidecar),
        )
    elif record["process_error"] is None:
        record["process_error"] = "gate wrote no sidecar"
    _telemetry.info(
        "change_gate_calibration.run",
        package=name,
        observed=record["observed"],
        expected=record["expected"],
        wall_s=record["wall_s"],
    )
    return record


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def summarize(runs: Sequence[dict[str, Any]], variant: str) -> dict[str, Any]:
    mine = [run for run in runs if run["variant"] == variant]
    judged = [run for run in mine if run["stage"] == "judge"]
    confusion = {
        expected: dict(
            Counter(run["observed"] for run in judged if run["expected"] == expected)
        )
        for expected in EXPECTED
    }
    by_expected = {
        expected: [run for run in judged if run["expected"] == expected]
        for expected in EXPECTED
    }
    false_noise = [
        {"id": run["id"], "repeat": run["repeat"], "reason": run["reason"]}
        for run in by_expected["meaningful"]
        if run["observed"] == "noise"
    ]
    false_meaningful = sum(
        run["observed"] == "meaningful" for run in by_expected["noise"]
    )
    verdicts: dict[str, list[str | None]] = defaultdict(list)
    for run in sorted(mine, key=lambda run: run["repeat"]):
        verdicts[run["id"]].append(run["observed"])
    stability = {
        pair: {"verdicts": observed, "stable": len(set(observed)) == 1}
        for pair, observed in sorted(verdicts.items())
    }
    walls = [run["wall_s"] for run in mine]
    return {
        "runs": len(mine),
        "judged_runs": len(judged),
        "confusion": confusion,
        "false_noise": false_noise,
        "false_noise_rate": _rate(len(false_noise), len(by_expected["meaningful"])),
        "false_meaningful_rate": _rate(false_meaningful, len(by_expected["noise"])),
        "unsure_rate": _rate(
            sum(run["observed"] == "unsure" for run in judged), len(judged)
        ),
        "stable_pairs": sum(entry["stable"] for entry in stability.values()),
        "pairs": len(stability),
        "stability": stability,
        # Decided before the judge despite the manifest: not in the matrix.
        "not_judged": [
            {
                "id": run["id"],
                "repeat": run["repeat"],
                "stage": run["stage"],
                "observed": run["observed"],
            }
            for run in mine
            if run["stage"] not in (None, "judge")
        ],
        "provider_errors": [
            {"id": run["id"], "repeat": run["repeat"], "error": run["judge_error"]}
            for run in mine
            if run["judge_error"]
        ],
        "process_errors": [
            {"id": run["id"], "repeat": run["repeat"], "error": run["process_error"]}
            for run in mine
            if run["process_error"]
        ],
        "wall_s": {
            "sum": round(sum(walls), 1),
            "mean": round(sum(walls) / len(walls), 1) if walls else None,
            "max": max(walls, default=None),
        },
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--manifest", type=Path, required=True, help="labeled pair list (JSON)"
    )
    parser.add_argument(
        "--out-dir", type=Path, required=True, help="sidecars and calibration.json"
    )
    parser.add_argument(
        "--repeats", type=int, default=3, help="runs per pair and variant"
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=VARIANTS,
        default=list(VARIANTS),
        help="judge variants",
    )
    parser.add_argument("--jobs", type=int, default=6, help="concurrent gate processes")
    args = parser.parse_args(argv)
    if args.repeats < 1 or args.jobs < 1:
        parser.error("--repeats and --jobs must be at least 1")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    pairs = load_manifest(args.manifest)
    runs_dir = args.out_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    tasks = [
        (pair, variant, repeat)
        for repeat in range(1, args.repeats + 1)
        for variant in args.variants
        for pair in pairs
    ]
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    started = time.monotonic()
    with (
        _telemetry.span(
            "change_gate_calibration",
            pairs=len(pairs),
            repeats=args.repeats,
            jobs=args.jobs,
        ),
        ThreadPoolExecutor(max_workers=args.jobs) as pool,
    ):
        runs = list(pool.map(lambda task: _run(*task, runs_dir), tasks))
    report = {
        "manifest": str(args.manifest.resolve()),
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "pairs": len(pairs),
        "expected_counts": dict(Counter(pair["expected"] for pair in pairs)),
        "repeats": args.repeats,
        "jobs": args.jobs,
        "started_at": started_at,
        "wall_s": round(time.monotonic() - started, 1),
        "variants": {variant: summarize(runs, variant) for variant in args.variants},
        "runs": runs,
    }
    output = args.out_dir / "calibration.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _telemetry.info(
        "change_gate_calibration.written", report=str(output), wall_s=report["wall_s"]
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
