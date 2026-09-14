"""Run the doit graph with a human-facing console verbosity flag and an executor.

Examples:
    uv run python build.py --verbosity warning -n 4
    uv run python build.py --verbosity debug check:math
    uv run python build.py --executor farm assembly:harmonic_analyzer

The wrapper only consumes ``--verbosity`` and ``--executor``; every other argument
is passed to ``doit`` unchanged. Structured telemetry capture remains full-fidelity.

``--executor farm`` (the ``build`` / ``build.cmd`` entry points) keeps doit as the
local dependency scheduler but runs every cache-missing part/assembly/drawing on
the SolidWorks build farm instead of the local seat (``dodo._farm_build``). It
needs a clean tree whose HEAD is on ``origin`` (the farm clones from there), the
remote cache enabled (the farm hands results back through it), and the commit's
sources published to the pool (``farm.py publish``) before doit starts.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from doit.doit_cmd import DoitMain

REPO_ROOT = Path(__file__).resolve().parent
_LEVELS = ("debug", "info", "success", "warning", "error", "critical")
_EXECUTORS = ("local", "farm")
_DEFAULT_FARM_PARALLELISM = "8"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--verbosity", choices=_LEVELS, default="warning")
    parser.add_argument(
        "--executor",
        choices=_EXECUTORS,
        default=os.environ.get("HARMONIC_EXECUTOR", "local"),
    )
    options, doit_args = parser.parse_known_args(argv)
    if options.verbosity is not None:
        os.environ["HARMONIC_VERBOSITY"] = options.verbosity
    doit = DoitMain()
    doit_args = list(doit_args)
    if options.executor == "farm":
        problem = _farm_preflight()
        if problem:
            print(problem, file=sys.stderr)
            return 2
        doit_args = _with_farm_parallelism(doit_args, doit.get_cmds())
    return doit.run(doit_args)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout


def _farm_preflight() -> str | None:
    """Publish HEAD to the farm and stamp the environment; a message means stop."""
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    dirty = [line[3:] for line in status.splitlines()]
    dirty += [
        line.split()[1]
        for line in _git("submodule", "status", "--recursive").splitlines()
        if line and not line.startswith(" ")
    ]
    if dirty:
        return "farm: working tree is dirty:\n" + "\n".join(f"  {p}" for p in dirty)
    sha = _git("rev-parse", "HEAD").strip()
    _git("fetch", "--quiet", "origin")
    if not _git("branch", "-r", "--contains", "HEAD").strip():
        return f"farm: HEAD {sha} is not on origin; push it to any branch first"

    sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))
    import _artifact_cache

    if not _artifact_cache.enabled():
        return "farm: HARMONIC_REMOTE_CACHE_MODE must be ro or rw"

    pool = Path(
        os.environ.get("SOLIDWORKS_POOL_HOME", REPO_ROOT.parent / "solidworks-pool")
    )
    publish = subprocess.run(
        [
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
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        text=True,
    )
    lines = [line for line in publish.stdout.splitlines() if line.strip()]
    if publish.returncode != 0 or not lines:
        sys.stderr.write(publish.stdout)
        return f"farm: publish failed (exit {publish.returncode})"
    summary = json.loads(lines[-1])
    identity = summary["source_identity_sha256"]
    print(f"farm: sources {identity[:16]} @ {sha[:12]} {summary['state']}")
    os.environ["HARMONIC_FARM_SOURCE_IDENTITY"] = identity
    os.environ["HARMONIC_FARM_COMMIT"] = sha
    os.environ["HARMONIC_EXECUTOR"] = "farm"
    os.environ["HARMONIC_SW_AUTOSTART"] = "0"
    return None


def _with_farm_parallelism(doit_args: list[str], commands) -> list[str]:
    """Keep up to ``HARMONIC_FARM_PARALLELISM`` (8) leaves in flight on the farm.

    Only the ``run`` command (explicit, or implied by a leading task name) takes
    ``-n``; an explicit ``-n``/``--process`` wins.
    """
    if any(arg.startswith(("-n", "--process")) for arg in doit_args):
        return doit_args
    workers = os.environ.get("HARMONIC_FARM_PARALLELISM", _DEFAULT_FARM_PARALLELISM)
    if doit_args and doit_args[0] in commands:
        if doit_args[0] != "run":
            return doit_args
        return ["run", "-n", workers, *doit_args[1:]]
    return ["-n", workers, *doit_args]


if __name__ == "__main__":
    raise SystemExit(main())
