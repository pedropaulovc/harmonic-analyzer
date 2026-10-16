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

Each invocation resumes matching valid results automatically. Inputs plus harness,
evaluator, schema and sheet-server hashes, Pillow/pypdfium2/mcp and reviewer CLI
versions (queried once per invocation), model, effort, timeout and retry settings
define the run identity.
Use a separate report directory for an independent repeat of identical inputs.
Concurrent invocations must not share a report directory. Each completed case is
checkpointed atomically; interrupted/invalid cases rerun without overwriting old
attempt artifacts. stdout contains only aggregate JSON; telemetry uses stderr.
The run's inputs/ directory preserves raw baseline.txt, candidate.txt and
schema.json bytes. Each report's extra.evidence preserves the exact effective
prompt, schema text, and authorized immutable source snapshots, each bound to
the frozen source hashes, plus actual argv and a path-adapted retained_argv for
every provider attempt. retained_argv only points attempt-dir file arguments at
their retained copies; it is provenance, not a runnable replay.
Frozen PNGs stay outside the per-attempt directories; retained MCP configuration,
process/output files and Codex's authoritative session rollout live directly in
each retained attempt directory. Codex evidence is judged from that rollout, which
must show no injected context before the prompt and no tool beyond sheet viewing.
extra.evidence.mcp_catalog must equal the current sheet server's resource-free
catalog (sole ``sheets`` server, zero resources and templates); only after that
proof, and argv configuring exactly that server, may Codex's built-in MCP resource
helpers appear, as recorded neutral calls that never prove inspection.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import functools
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Sequence

import _telemetry as telemetry
import machinist_review as mr

DEFAULT_CASES = mr.CAD_ROOT / "comparisons" / "bench" / "machinist_review" / "manifest.json"
VERSIONS = ("baseline", "candidate")
# Rendering dependencies of the sheet server; it runs under this interpreter.
RUNTIME_PACKAGES = ("Pillow", "pypdfium2", "mcp")
INVOCATION_FIELDS = frozenset({
    "attempt", "reviewer", "cwd", "attempt_dir", "codex_home", "sources", "command",
    "outcome", "error", "exit_code", "session_id", "resume_command", "stdout_file",
    "stderr_file", "artifacts", "retained_dir", "retained_argv", "rollout_file",
    "retention_warning",
})


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, suffix=".tmp", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, value: Any) -> None:
    _atomic_bytes(path, (json.dumps(value, indent=2) + "\n").encode("utf-8"))


def persist_inputs(
    run_dir: Path, identity: dict[str, Any], prompts: dict[str, bytes],
) -> None:
    """Freeze replayable input bytes; never replace a mismatched existing input."""
    inputs = [
        (f"{version}.txt", prompts[version], identity["prompts"][version]["raw_sha256"])
        for version in VERSIONS
    ]
    inputs.append(("schema.json", mr.SCHEMA_FILE.read_bytes(), identity["schema_sha256"]))
    for name, content, expected_hash in inputs:
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise ValueError(f"{name}: input changed after run identity was computed")
        destination = run_dir / "inputs" / name
        if destination.exists():
            if mr._sha256(destination) != expected_hash:
                raise ValueError(f"{name}: preserved input hash mismatch")
        else:
            _atomic_bytes(destination, content)


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


@functools.cache
def runtime_versions(reviewer: str) -> dict[str, str]:
    """Installed renderer/MCP and reviewer CLI versions; queried once per process.

    review_package resolves the reviewer the same way, through PATH.
    """
    try:
        versions = {name: importlib.metadata.version(name) for name in RUNTIME_PACKAGES}
        executable = shutil.which(reviewer)
        if not executable:
            raise RuntimeError(f"{reviewer} CLI not found on PATH")
        process = subprocess.run(
            [executable, "--version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError, importlib.metadata.PackageNotFoundError) as exc:
        raise RuntimeError(f"cannot determine review runtime versions: {exc}") from exc
    cli = process.stdout.strip()
    if process.returncode != 0 or not cli:
        raise RuntimeError(f"{reviewer} --version failed: {process.stderr.strip()[-400:]}")
    return {**versions, "reviewer_cli": cli}



def make_identity(
    manifest: dict[str, Any], packages: Sequence[mr.ReviewPackage],
    prompts: dict[str, bytes], *, reviewer: str, model: str, effort: str,
    retries: int, timeout_s: float, runtime: dict[str, str],
) -> dict[str, Any]:
    """Content identity, independent of checkout and output directory locations."""
    return {
        "schema_version": 1,
        "manifest": manifest,
        "engine_sha256": mr._sha256(Path(mr.__file__)),
        "evaluator_sha256": mr._sha256(Path(__file__)),
        "sheets_server_sha256": mr._sha256(mr.SHEETS_SERVER),
        "schema_sha256": mr._sha256(mr.SCHEMA_FILE),
        "reviewer": reviewer, "model": model, "effort": effort,
        "retries": retries, "timeout_s": timeout_s, "runtime": dict(runtime),
        "prompts": {
            version: {"raw_sha256": hashlib.sha256(raw).hexdigest(),
                      "effective_sha256": {
                          package.name: hashlib.sha256(mr._review_prompt(
                              package, len(package.sources), reviewer=reviewer,
                              prompt_text=raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n"),
                          ).encode("utf-8")).hexdigest()
                          for package in packages}}
            for version, raw in prompts.items()
        },
        "images": {p.name: [mr._sha256(source) for source in p.sources] for p in packages},
    }


def _retained_file(recorded: Any, retained: Path, name: str, label: str) -> Path:
    if not isinstance(recorded, str):
        raise ValueError(f"missing retained {label}")
    path = Path(recorded)
    if (
        not path.is_absolute() or path != retained / name
        or path.resolve().parent != retained.resolve() or not path.is_file()
    ):
        raise ValueError(f"missing or misplaced retained {label}")
    return path


def _codex_rollout_events(
    rollout: Path, *, session_id: str, cwd: Path, cli: str, prompt: str,
    neutral_resources: bool,
) -> list[dict[str, Any]]:
    """Normalized calls from one retained Codex session, after context checks."""
    rows = [
        json.loads(line)
        for line in rollout.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError("malformed retained Codex rollout")
    meta = rows[0].get("payload") if rows[0].get("type") == "session_meta" else None
    if (
        not isinstance(meta, dict) or meta.get("id") != session_id
        or not isinstance(meta.get("cwd"), str) or Path(meta["cwd"]) != cwd
        or not isinstance(meta.get("cli_version"), str) or meta["cli_version"] not in cli.split()
    ):
        raise ValueError("retained Codex rollout belongs to another session, workdir or CLI")
    evidence = mr.codex_rollout_evidence(rows, prompt, neutral_resources=neutral_resources)
    if evidence["context_errors"]:
        raise ValueError(
            "retained Codex rollout shows injected reviewer context: "
            + "; ".join(map(str, evidence["context_errors"]))
        )
    return evidence["events"]


def _check_codex_model_catalog(path: Path, model: str) -> None:
    """The retained catalog must pin direct (not code-mode or deferred) sheet tools."""
    catalog = json.loads(path.read_text(encoding="utf-8"))
    models = catalog.get("models") if isinstance(catalog, dict) and set(catalog) == {"models"} else None
    if (
        not isinstance(models, list) or len(models) != 1 or not isinstance(models[0], dict)
        or models[0].get("slug") != model or models[0].get("tool_mode") != "direct"
        or models[0].get("supports_search_tool") is not False
    ):
        raise ValueError("retained Codex model catalog does not pin direct tools for the model")


def _codex_mcp_servers(command: list[str]) -> set[str]:
    """MCP servers a Codex argv configures; a whole-table override is unnamed."""
    servers = set()
    for flag, setting in zip(command, command[1:]):
        key = setting.partition("=")[0]
        if flag == "-c" and key.split(".")[0] == "mcp_servers":
            servers.add(key.split(".")[1] if "." in key else "")
    return servers


def _relocated(argument: str, attempt_dir: Path, retained: Path) -> str | None:
    """Retained form of an attempt-dir file argument (bare or ``key=<JSON path>``)."""
    def moved(value: str) -> Path | None:
        path = Path(value)
        if path.is_absolute() and path.is_relative_to(attempt_dir):
            return retained / path.relative_to(attempt_dir)
        return None

    target = moved(argument)
    if target is not None:
        return str(target)
    key, separator, value = argument.partition("=")
    if separator:
        try:
            decoded = json.loads(value)
        except ValueError:
            return None
        if isinstance(decoded, str) and (target := moved(decoded)) is not None:
            return f"{key}={json.dumps(str(target))}"
    return None


def _check_retained_argv(
    command: list[str], retained_argv: Any, attempt_dir: Path, retained: Path,
) -> None:
    """retained_argv is provenance: only attempt-dir files move; nothing else may."""
    if (
        not isinstance(retained_argv, list) or len(retained_argv) != len(command)
        or any(
            adapted != (_relocated(original, attempt_dir, retained) or original)
            for original, adapted in zip(command, retained_argv)
        )
    ):
        raise ValueError("retained argv must relocate exactly the attempt-dir file arguments")


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
    sources = [source.resolve() for source in package.sources]
    snapshot_dir = report_path.parent / f"{package.name}.sources"
    snapshot_sources = [snapshot_dir / source.name for source in sources]
    resolved_snapshot_dir = snapshot_dir.resolve()
    if (
        not snapshot_dir.is_dir()
        or not resolved_snapshot_dir.is_relative_to(report_path.parent.resolve())
        or any(
            not snapshot.is_file()
            or snapshot.resolve().parent != resolved_snapshot_dir
            or mr._sha256(snapshot) != expected_hash
            for snapshot, expected_hash in zip(
                snapshot_sources, identity["images"][package.name],
            )
        )
    ):
        raise ValueError("missing, misplaced or changed immutable source snapshot")
    if [mr._sha256(source) for source in sources] != identity["images"][package.name]:
        raise ValueError("source changed after run identity was computed")
    expected = {
        "name": package.name, "kind": package.kind, "sheet_count": len(sources),
        "sources": [str(source) for source in sources],
        "source_sha256": identity["images"][package.name],
        "prompt_sha256": identity["prompts"][version]["effective_sha256"][package.name],
        "reviewer": identity["reviewer"], "model": identity["model"], "effort": identity["effort"],
    }
    if type(review.sheet_count) is not int or any(getattr(review, key) != value for key, value in expected.items()):
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
    if not isinstance(review.extra, dict):
        raise ValueError("missing preserved invocation evidence")
    evidence = review.extra.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("missing preserved invocation evidence")
    for field, expected_hash in (
        ("effective_prompt", review.prompt_sha256),
        ("schema", identity["schema_sha256"]),
    ):
        content = evidence.get(field)
        if not isinstance(content, str) or hashlib.sha256(content.encode("utf-8")).hexdigest() != expected_hash:
            raise ValueError(f"preserved {field} hash mismatch")
    attempts = evidence.get("attempts")
    if not isinstance(attempts, list) or len(attempts) != review.attempts:
        raise ValueError("incomplete invocation history")
    # The resource-free sole-sheets catalog is recomputed from the current SDK
    # server; only under it are Codex resource helpers neutral (never Claude's).
    current_catalog = mr._sheet_resource_manifest(snapshot_sources)
    if _digest(evidence.get("mcp_catalog")) != _digest(current_catalog):
        raise ValueError("recorded MCP catalog differs from the current sheet server")
    if not mr._resource_neutrality_permitted(current_catalog):
        raise ValueError("sheet server MCP catalog is not the resource-free sole sheets server")
    neutral_resources = review.reviewer == "codex"
    attempt_dirs: set[Path] = set()
    sessions: set[str] = set()
    rollout_events: list[dict[str, Any]] = []
    for number, invocation in enumerate(attempts, start=1):
        if (
            not isinstance(invocation, dict) or set(invocation) != INVOCATION_FIELDS
            or type(invocation["attempt"]) is not int or invocation["attempt"] != number
        ):
            raise ValueError("invalid invocation record")
        session_id = invocation["session_id"]
        if (
            invocation["reviewer"] != review.reviewer
            or (session_id is not None and (not isinstance(session_id, str) or not session_id))
            or invocation["resume_command"] != mr._resume_command(review.reviewer, session_id)
            or (session_id is not None and session_id in sessions)
        ):
            raise ValueError("invalid session provenance")
        if session_id is not None:
            sessions.add(session_id)
        if not isinstance(invocation["attempt_dir"], str) or not isinstance(invocation["cwd"], str):
            raise ValueError("missing invocation directories")
        attempt_dir = Path(invocation["attempt_dir"])
        cwd = Path(invocation["cwd"])
        if (
            not attempt_dir.is_absolute() or attempt_dir.resolve() in attempt_dirs
            or not attempt_dir.name.startswith("machrev-")
        ):
            raise ValueError("invalid or reused attempt directory")
        attempt_dirs.add(attempt_dir.resolve())
        warning = invocation["retention_warning"]
        if warning is not None and (not isinstance(warning, str) or not warning.strip()):
            raise ValueError("invalid retention warning")
        if attempt_dir.exists() and warning is None:
            raise ValueError("original attempt directory survived without a retention warning")
        expected_home = None if review.reviewer == "claude" else str(mr.CODEX_HOME)
        if cwd != attempt_dir or invocation["codex_home"] != expected_home:
            raise ValueError("reviewer must run in its own attempt directory and expected home")
        if any((parent / ".git").exists() for parent in (attempt_dir, *attempt_dir.resolve().parents)):
            raise ValueError("reviewer attempt directory must be outside every git repository")
        retained_dir = report_path.parent / f"{package.name}.attempts" / attempt_dir.name
        if not isinstance(invocation["retained_dir"], str):
            raise ValueError("missing retained attempt directory")
        retained = Path(invocation["retained_dir"])
        if (
            not retained.is_absolute() or retained != retained_dir
            or not retained.resolve().is_relative_to(report_path.parent.resolve())
            or not retained.is_dir()
        ):
            raise ValueError("missing or misplaced retained attempt directory")
        if (
            invocation["sources"] != [str(source.resolve()) for source in snapshot_sources]
            or any(
                source.is_relative_to(directory.resolve())
                for source in sources
                for directory in (cwd, attempt_dir, retained)
            )
        ):
            raise ValueError("invocation source allowlist differs from package")
        outcome, error, exit_code = invocation["outcome"], invocation["error"], invocation["exit_code"]
        if exit_code is not None and type(exit_code) is not int:
            raise ValueError("invalid invocation exit code")
        if number == review.attempts:
            if outcome != "succeeded" or error is not None or exit_code != 0:
                raise ValueError("final invocation lacks successful process evidence")
        elif (
            outcome not in ("failed", "timed_out")
            or not isinstance(error, str) or not error.strip()
            or (outcome == "timed_out" and exit_code is not None)
        ):
            raise ValueError("invalid failed invocation outcome")
        command = invocation["command"]
        attempt_events = [row["event"] for row in events if row["attempt"] == number]
        if review.reviewer == "codex" and session_id != mr._codex_session_id(attempt_events):
            raise ValueError("session differs from retry event history")
        input_names: set[str] = set()
        schema = retained / "schema.json"
        if schema.exists():
            if not schema.is_file() or schema.resolve().parent != retained.resolve() or mr._sha256(schema) != identity["schema_sha256"]:
                raise ValueError("retained schema hash/path mismatch")
            input_names.add(schema.name)
        elif command is not None:
            raise ValueError("missing retained schema")
        config = retained / "mcp.json"
        if config.exists():
            if (
                review.reviewer != "claude" or not config.is_file()
                or config.resolve().parent != retained.resolve()
                or json.loads(config.read_text(encoding="utf-8")) != {
                    "mcpServers": {"sheets": {
                        "command": sys.executable,
                        "args": [
                            str(mr.SHEETS_SERVER),
                            *(str(source.resolve()) for source in snapshot_sources),
                        ],
                    }},
                }
            ):
                raise ValueError("retained MCP configuration mismatch")
            input_names.add(config.name)
        elif command is not None and review.reviewer == "claude":
            raise ValueError("missing retained MCP configuration")
        for stream in ("stdout", "stderr"):
            recorded_path = invocation[f"{stream}_file"]
            if recorded_path is None:
                if exit_code is not None or (stream == "stdout" and attempt_events):
                    raise ValueError("missing retained process stream")
                continue
            if not isinstance(recorded_path, str):
                raise ValueError("invalid retained process stream path")
            path = Path(recorded_path)
            if (
                not path.is_absolute() or path != retained / f"{stream}.txt"
                or path.resolve().parent != retained.resolve() or not path.is_file()
            ):
                raise ValueError("missing or misplaced retained process stream")
            input_names.add(path.name)
            if stream == "stdout" and mr._parse_events(
                path.read_bytes().decode("utf-8", errors="replace")
            ) != attempt_events:
                raise ValueError("retained stdout differs from retry event history")
        rollout_file = invocation["rollout_file"]
        rollout: Path | None = None
        if review.reviewer == "claude" or session_id is None:
            if rollout_file is not None:
                raise ValueError("unexpected retained Codex rollout")
        else:
            # A started Codex thread is only judged from its authoritative rollout,
            # parsed once this attempt's argv is bound to the proven catalog.
            rollout = _retained_file(rollout_file, retained, "rollout.jsonl", "Codex rollout")
            input_names.add(rollout.name)
        artifacts = invocation["artifacts"]
        if not isinstance(artifacts, list) or any(not isinstance(path, str) for path in artifacts):
            raise ValueError("invalid retained artifact paths")
        artifact_paths = [Path(path) for path in artifacts]
        if len(set(artifact_paths)) != len(artifact_paths) or any(
            not path.is_absolute() or path.parent != retained
            or path.resolve().parent != retained.resolve() or not path.is_file()
            or review.reviewer != "codex" or path.name not in ("codex-models.json", "verdict.json")
            for path in artifact_paths
        ):
            raise ValueError("missing or misplaced retained artifact")
        catalog = retained / "codex-models.json"
        if catalog in artifact_paths:
            _check_codex_model_catalog(catalog, review.model)
        elif command is not None and review.reviewer == "codex":
            raise ValueError("missing retained Codex model catalog")
        if {path.name for path in retained.iterdir()} != input_names | {
            path.name for path in artifact_paths
        }:
            raise ValueError("incomplete retained artifact inventory")
        if command is None:
            if (
                attempt_events or number == review.attempts or outcome != "failed"
                or exit_code is not None or invocation["retained_argv"] is not None
                or invocation["stdout_file"] is not None or invocation["stderr_file"] is not None
                or rollout_file is not None or any(path.name == "verdict.json" for path in artifact_paths)
            ):
                raise ValueError("events without a recorded provider invocation")
            continue
        if not isinstance(command, list) or not command or any(not isinstance(arg, str) for arg in command):
            raise ValueError("invalid invocation command")
        if review.reviewer == "claude" and session_id is None:
            raise ValueError("missing Claude invocation session")
        expected_command = (
            mr.build_claude_command(
                workdir=attempt_dir, mcp_config=attempt_dir / "mcp.json",
                schema=attempt_dir / "schema.json", model=review.model, effort=review.effort,
                session_id=session_id or "", claude=command[0],
                schema_content=evidence["schema"],
            )
            if review.reviewer == "claude"
            else mr.build_codex_command(
                workdir=cwd, attempt_dir=attempt_dir, sources=snapshot_sources,
                schema=attempt_dir / "schema.json", output=attempt_dir / "verdict.json",
                model=review.model, effort=review.effort, codex=command[0],
            )
        )
        if command != expected_command:
            raise ValueError("invocation command permissions/settings mismatch")
        _check_retained_argv(command, invocation["retained_argv"], attempt_dir, retained)
        if review.reviewer == "codex" and (
            "--ignore-user-config" not in command
            or _codex_mcp_servers(command) != set(current_catalog["servers"])
        ):
            raise ValueError("Codex argv does not configure exactly the cataloged MCP server")
        if rollout is not None:
            rollout_events.extend(mr._tag_events(number, _codex_rollout_events(
                rollout, session_id=session_id, cwd=cwd,
                cli=identity["runtime"]["reviewer_cli"], prompt=evidence["effective_prompt"],
                neutral_resources=neutral_resources,
            )))
    if review.extra.get("context_errors") != []:
        raise ValueError("recorded reviewer context was not proven clean")
    successful = [row["event"] for row in events if row["attempt"] == review.attempts]
    if review.reviewer == "codex":
        # The --json stream is a projection that can omit calls (e.g. code-mode
        # cells); it may still never show one, but only the rollout proves views.
        if mr.evaluate_sheet_evidence(
            events, reviewer="codex", sheet_count=review.sheet_count,
            neutral_resources=neutral_resources,
        )["tool_events"]:
            raise ValueError("Codex event projection does not prove authorized sheet inspection")
        authoritative = rollout_events
    else:
        authoritative = events
    all_inspection = mr.evaluate_sheet_evidence(
        authoritative, reviewer=review.reviewer, sheet_count=review.sheet_count,
        neutral_resources=neutral_resources,
    )
    final_inspection = mr.evaluate_sheet_evidence(
        [row for row in authoritative if row["attempt"] == review.attempts],
        reviewer=review.reviewer, sheet_count=review.sheet_count,
        neutral_resources=neutral_resources,
    )
    if all_inspection["tool_events"] or not final_inspection["inspection_proven"]:
        raise ValueError("event history does not prove authorized sheet inspection")
    expected_inspection = {
        "sheets_viewed": final_inspection["sheets_viewed"],
        "inspection_proven": final_inspection["inspection_proven"],
        "crop_calls": all_inspection["crop_calls"],
        "crops": all_inspection["crops"],
        # Every attempt's neutral resource requests, exactly as normalized.
        "neutral_calls": all_inspection["neutral_calls"],
    }
    if _digest({field: review.extra.get(field) for field in expected_inspection}) != _digest(expected_inspection):
        raise ValueError("recorded sheet inspection differs from event history")
    if review.reviewer == "codex":
        output = Path(attempts[-1]["retained_dir"]) / "verdict.json"
        if mr.extract_codex_verdict(output, successful) != review.verdict:
            raise ValueError("report differs from retained Codex verdict")
        if any(
            isinstance(node, dict) and node.get("type") == "agent_message"
            for node in mr._walk(successful)
        ) and mr.extract_codex_verdict(output.parent, successful) != review.verdict:
            raise ValueError("report differs from successful Codex event verdict")
    elif mr.extract_claude_verdict(successful) != review.verdict:
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
                                 model=args.model, effort=args.effort, retries=args.retries,
                                 timeout_s=args.timeout, runtime=runtime_versions(args.reviewer))
        frozen_baseline = manifest.get("baseline_prompt")
        if (
            frozen_baseline is not None
            and args.baseline.resolve() == (args.cases.parent / frozen_baseline["path"]).resolve()
            and identity["prompts"]["baseline"]["raw_sha256"] != frozen_baseline["sha256"]
        ):
            raise ValueError("baseline prompt hash differs from frozen manifest")
        assessments = json.loads(args.assessments.read_text(encoding="utf-8")) if args.assessments else None
        if args.assessments and (
            not isinstance(assessments, dict)
            or assessments.get("run_id") != _digest(identity)
        ):
            raise ValueError("assessment run identity mismatch")
        run_dir = args.report_dir.resolve() / _digest(identity)
        _atomic_json(run_dir / "identity.json", identity)
        persist_inputs(run_dir, identity, prompts)
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
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
        telemetry.error("Evaluation failed", reason=str(exc))
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
