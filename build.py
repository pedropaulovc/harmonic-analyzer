"""Run the doit graph with a human-facing console verbosity flag and an executor.

Examples:
    uv run python build.py --verbosity warning -n 4
    uv run python build.py --verbosity debug check:math
    uv run python build.py --executor farm assembly:harmonic_analyzer

The wrapper only consumes ``--verbosity`` and ``--executor``; every other argument
is passed to ``doit`` unchanged. Structured telemetry capture remains full-fidelity.

``--executor farm`` (the ``build`` / ``build.cmd`` entry points) keeps doit as the
local dependency scheduler but runs every cache-missing COM task -- parts,
assemblies, drawings, the ``verify:*`` gates, ``preflight``, the neutral ``export``
and the release Pack-and-Go (``package:release``) -- on the SolidWorks build farm
instead of a local seat (``dodo._cached_com_action`` -> ``dodo._farm_build``). It
needs a clean tree whose HEAD is on ``origin`` (the farm clones from there), the
remote cache enabled (the farm hands results back through it), and the commit's
sources published to the pool (``farm.py publish``) before doit starts. A full
release therefore needs no local SolidWorks; only the Blender-bound ``gallery``
task and the publishing half of ``release`` run here.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from doit.doit_cmd import DoitMain

REPO_ROOT = Path(__file__).resolve().parent
_LEVELS = ("debug", "info", "success", "warning", "error", "critical")
_EXECUTORS = ("local", "farm")
_DEFAULT_FARM_PARALLELISM = "8"
_PUBLISH_STATES = ("published", "exists")

# doit's task-loader options may precede the subcommand (``DoitMain.run`` parses
# them first). ``-f``/``-d`` take a value, attached (``-fdodo.py``, ``--file=x``)
# or as the next token; ``-k``/``--seek-file`` is a flag.
_LOADER_SEPARATE_VALUE = ("-f", "-d", "--file", "--dir")
_LOADER_ONE_TOKEN = ("-k", "--seek-file")
_LOADER_ATTACHED_VALUE = ("-f", "-d", "--file=", "--dir=")
_NO_RUN = ("--help", "-h", "--version")


class FarmPreflightError(Exception):
    """Why a farm run must stop before doit starts; printed as ``farm: <reason>``."""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--verbosity", choices=_LEVELS, default="warning")
    parser.add_argument(
        "--executor",
        choices=_EXECUTORS,
        default=os.environ.get("HARMONIC_EXECUTOR", "local"),
    )
    # A cold leaf (source sync plus a cold SOLIDWORKS start) measured 61.5 min on
    # the farm, well past the control plane's 15 min default, so a run that knows
    # it is cold raises the per-attempt budget for the leaves it dispatches.
    parser.add_argument("--leaf-timeout", type=int, metavar="MINUTES")
    options, doit_args = parser.parse_known_args(argv)
    if options.verbosity is not None:
        os.environ["HARMONIC_VERBOSITY"] = options.verbosity
    doit = DoitMain()
    doit_args = list(doit_args)
    if options.leaf_timeout is not None:
        os.environ["HARMONIC_FARM_LEAF_TIMEOUT_S"] = str(options.leaf_timeout * 60)
    if options.executor == "farm":
        run_at = _run_insertion_point(doit_args, doit.get_cmds())
        if run_at is not None:
            try:
                _farm_preflight()
            except FarmPreflightError as problem:
                print(f"farm: {problem}", file=sys.stderr)
                return 2
            print(
                "farm: every SolidWorks task runs on the farm (parts, assemblies, "
                "drawings, verify:*, preflight, export, package:release)"
            )
            doit_args = _with_farm_parallelism(doit_args, run_at)
    # dodo reads the executor from the environment; an explicit --executor must
    # win over an inherited HARMONIC_EXECUTOR.
    os.environ["HARMONIC_EXECUTOR"] = options.executor
    return doit.run(doit_args)


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise FarmPreflightError(
            f"git {' '.join(args)} failed (exit {exc.returncode}){_tail(exc.stderr)}"
        ) from None
    except OSError as exc:
        raise FarmPreflightError(
            f"git {' '.join(args)} could not start: {exc}"
        ) from None


def _tail(text: str | None, lines: int = 20) -> str:
    """The last non-blank lines of a captured stream, indented for a diagnostic."""
    kept = [line for line in (text or "").splitlines() if line.strip()][-lines:]
    if not kept:
        return ""
    return "\n" + "\n".join(f"  {line}" for line in kept)


def _farm_preflight() -> None:
    """Publish HEAD to the farm and stamp the environment; raises to stop."""
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    dirty = [line[3:] for line in status.splitlines()]
    dirty += [
        line.split()[1]
        for line in _git("submodule", "status", "--recursive").splitlines()
        if line and not line.startswith(" ")
    ]
    if dirty:
        raise FarmPreflightError(
            "working tree is dirty:\n" + "\n".join(f"  {p}" for p in dirty)
        )
    sha = _git("rev-parse", "HEAD").strip()
    # Prune first and ask only origin: the farm clones from origin, so a commit
    # reachable from another remote or a deleted-upstream branch is not on it.
    _git("fetch", "--quiet", "--prune", "origin")
    if not _git("branch", "-r", "--contains", "HEAD", "--list", "origin/*").strip():
        raise FarmPreflightError(
            f"HEAD {sha} is not on origin; push it to any branch first"
        )

    sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))
    import _artifact_cache

    if not _artifact_cache.enabled():
        raise FarmPreflightError("HARMONIC_REMOTE_CACHE_MODE must be ro or rw")

    identity = _publish(sha)
    os.environ["HARMONIC_FARM_SOURCE_IDENTITY"] = identity
    os.environ["HARMONIC_FARM_COMMIT"] = sha
    os.environ["HARMONIC_SW_AUTOSTART"] = "0"


def _publish(sha: str) -> str:
    """Run ``farm.py publish`` for ``sha`` and return the source identity."""
    pool = Path(
        os.environ.get("SOLIDWORKS_POOL_HOME", REPO_ROOT.parent / "solidworks-pool")
    )
    argv = [
        "uv",
        "run",
        "--frozen",
        "--project",
        str(pool),
        "python",
        str(pool / "farm.py"),
        "publish",
        "--commit",
        sha,
        "--json",
    ]
    try:
        # stderr is inherited so publish progress streams to the console.
        publish = subprocess.run(argv, cwd=REPO_ROOT, stdout=subprocess.PIPE, text=True)
    except OSError as exc:
        raise FarmPreflightError(
            f"publish could not start ({argv[0]}): {exc}"
        ) from None
    lines = [line for line in publish.stdout.splitlines() if line.strip()]
    if publish.returncode != 0 or not lines:
        raise FarmPreflightError(
            f"publish failed (exit {publish.returncode}){_tail(publish.stdout)}"
        )
    summary = _publish_summary(lines[-1], sha)
    identity = summary["source_identity_sha256"]
    print(f"farm: sources {identity[:16]} @ {sha[:12]} {summary['state']}")
    return identity


def _publish_summary(line: str, sha: str) -> dict:
    """The parsed and validated last stdout line of ``farm.py publish --json``."""
    try:
        summary = json.loads(line)
    except json.JSONDecodeError:
        raise FarmPreflightError(
            f"publish printed no JSON summary; last line: {line[:200]}"
        ) from None
    if not isinstance(summary, dict):
        raise FarmPreflightError(f"publish summary is not an object: {line[:200]}")
    state = summary.get("state")
    if state not in _PUBLISH_STATES:
        raise FarmPreflightError(
            f"publish summary state {state!r} is not one of {_PUBLISH_STATES}"
        )
    identity = summary.get("source_identity_sha256")
    if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{64}", identity):
        raise FarmPreflightError(
            f"publish summary source_identity_sha256 is not 64 hex: {identity!r}"
        )
    commit = summary.get("commit")
    if commit != sha:
        raise FarmPreflightError(
            f"publish summary is for commit {commit!r}, expected {sha}"
        )
    return summary


def _run_insertion_point(doit_args: list[str], commands) -> int | None:
    """Where ``-n`` goes for a run invocation; ``None`` when doit runs no task.

    Skips doit's leading loader options the way ``DoitMain.run`` does before it
    reads the subcommand. ``--help``/``-h``/``--version`` and every subcommand
    but ``run`` (``list``, ``info``, ``clean``, ``forget``, ...) run nothing, so
    they neither take ``-n`` nor need the farm preflight.
    """
    i = 0
    while i < len(doit_args):
        arg = doit_args[i]
        if arg in _LOADER_SEPARATE_VALUE:
            i += 2
        elif arg in _LOADER_ONE_TOKEN or arg.startswith(_LOADER_ATTACHED_VALUE):
            i += 1
        else:
            break
    if i >= len(doit_args):
        return i  # implicit run of the default tasks
    head = doit_args[i]
    if head in _NO_RUN:
        return None
    if head not in commands:
        return i  # implicit run of the named tasks
    if head != "run":
        return None
    return i + 1


def _with_farm_parallelism(doit_args: list[str], run_at: int) -> list[str]:
    """Keep up to ``HARMONIC_FARM_PARALLELISM`` (8) leaves in flight on the farm.

    ``-n`` goes at ``run_at`` (see ``_run_insertion_point``) unless the caller
    already chose ``-n``/``--process``.
    """
    if any(arg.startswith(("-n", "--process")) for arg in doit_args):
        return doit_args
    workers = os.environ.get("HARMONIC_FARM_PARALLELISM", _DEFAULT_FARM_PARALLELISM)
    return [*doit_args[:run_at], "-n", workers, *doit_args[run_at:]]


if __name__ == "__main__":
    raise SystemExit(main())
