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
remote cache enabled (the farm hands results back through it), a pool checkout
whose agent build is the one the fleet runs (``farm.py agents``: a package
published for any other agent lands under a prefix no worker reads), and the
commit's sources published to the pool (``farm.py publish``) before doit starts. A
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

    pool = _pool_home()
    agent = _require_fleet_agent(pool)
    identity = _publish(pool, sha, agent)
    os.environ["HARMONIC_FARM_SOURCE_IDENTITY"] = identity
    os.environ["HARMONIC_FARM_COMMIT"] = sha
    os.environ["HARMONIC_SW_AUTOSTART"] = "0"


def _pool_home() -> Path:
    return Path(
        os.environ.get("SOLIDWORKS_POOL_HOME", REPO_ROOT.parent / "solidworks-pool")
    )


def _pool_farm(pool: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run one ``farm.py`` subcommand from the pool checkout, capturing stdout.

    stderr is inherited so the pool's own progress and diagnostics reach the
    console as they happen; stdout is the machine-readable result.
    """
    argv = [
        "uv",
        "run",
        "--frozen",
        "--project",
        str(pool),
        "python",
        str(pool / "farm.py"),
        *args,
    ]
    try:
        return subprocess.run(argv, cwd=REPO_ROOT, stdout=subprocess.PIPE, text=True)
    except OSError as exc:
        raise FarmPreflightError(
            f"{args[0]} could not start ({argv[0]}): {exc}"
        ) from None


def _dissenting_workers(reports: object, version: str) -> list[str]:
    """``worker (agent build, last seen)`` for each report naming another build.

    A report the pool ignored as stale is still evidence AGAINST a match: the
    agent tree it names lives on that worker's own disk, so a worker idle for
    a month comes back on exactly the build its last report published. Only
    reports that disagree are returned -- agreement at any age proves nothing
    and blocks nothing.
    """
    if not isinstance(reports, list):
        return []
    named = []
    for report in reports:
        if not isinstance(report, dict):
            continue
        other = report.get("agent_version")
        if not isinstance(other, str) or not other or other == version:
            continue
        age = report.get("age_s")
        if not isinstance(age, int):
            age = report.get("written_age_s")
        seen = f", last seen {age // 86400}d ago" if isinstance(age, int) else ""
        named.append(f"{report.get('worker_id') or '?'} ({other}{seen})")
    return sorted(named)


def _require_fleet_agent(pool: Path) -> str:
    """Stop unless the fleet runs the agent this pool checkout would publish for.

    A package is published under ``<source identity>-<agent identity>`` and every
    worker rebuilds that prefix from the agent deployed on it, so a pool checkout
    ahead of (or behind) the fleet publishes where no worker ever looks. On
    2026-09-18 that cost a farm build 8.5 min and failed every COM leaf with an
    unexplained ``package_download``. Each worker publishes its agent build in
    its seat report, and that build lives on the worker's own disk -- so even a
    worker that has been asleep for hours still names the build it will come
    back on, and ``farm.py agents`` can answer before a leaf is dispatched.
    Returns the agent build ``pool`` would publish for.

    There is deliberately no override on this side. ``farm.py publish`` has one,
    because a publish mid-rollout is legitimate; a farm build is not -- it hands
    every COM task to those same workers, and a mismatch fails all of them.

    This read is not the only enforcement, and is not the last one: the pool's
    ``publish_source`` calls ``require_fleet_agent(allow_mismatch=False)``
    before it uploads anything, so a mismatch that appears between this read
    and the publish still stops the build -- with the pool's own wording,
    which does mention the override. Two reads means two Azure round-trips and
    a window in which they can disagree; the window is worth it, because this
    one runs before doit is even constructed, so the operator sees the fleet's
    agent build in the first line of output rather than after a preflight's
    worth of work.
    """
    result = _pool_farm(pool, "agents", "--json")
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or not lines:
        raise FarmPreflightError(
            f"agents failed (exit {result.returncode}){_tail(result.stdout)}"
        )
    summary = _agents_summary(lines[-1])
    if summary["verdict"] in _AGENT_VERDICT_BLOCKS:
        report = summary.get("report")
        if not isinstance(report, str) or not report:
            raise FarmPreflightError(
                f"agents returned verdict {summary['verdict']!r} without a report: "
                f"{lines[-1][:200]}"
            )
        raise FarmPreflightError(report)
    workers = summary["workers"]
    fresh = sum(
        1 for worker in workers if isinstance(worker, dict) and worker.get("fresh")
    )
    version = summary["agent_version"]
    if fresh:
        print(f"farm: agent {version} on {fresh} worker(s)")
    elif workers:
        # The fleet is asleep, not unknown: an agent tree lives on the worker's
        # own disk, so the last report of each worker still names the build it
        # will come back on, and the pool has already checked them.
        print(
            f"farm: agent {version}; no worker has reported within "
            f"{summary['fresh_within_s']}s, but the last report of "
            f"{len(workers)} worker(s) names this build"
        )
    elif summary["ignored"]:
        # "Nothing reported" would be false with these in hand. The pool
        # believes no report past its evidence horizon, and saying so is the
        # difference between a fleet nobody has ever seen and one whose
        # instances were renumbered or idle for a fortnight.
        days = summary["evidence_horizon_s"] // 86400
        dissent = _dissenting_workers(summary["ignored"], version)
        if dissent:
            # Too old to CONFIRM is not too old to CONTRADICT. The agent tree
            # lives on the worker's OS disk, so an old report still names the
            # build that worker will come back on; a horizon that discards
            # that turns the one piece of evidence we have into silence, and
            # silence here publishes to a prefix nobody reads -- the
            # package_download failure this preflight exists to stop.
            raise FarmPreflightError(
                f"this pool checkout's agent is {version}, and no worker has "
                f"reported within {days}d, but the last report of "
                + ", ".join(dissent)
                + " names another build. Deploy this agent to the fleet "
                "(farm.py agent-release publish, then deploy), or delete the "
                "seat report of an instance that will never come back."
            )
        print(
            f"farm: agent {version}; {len(summary['ignored'])} worker(s) last "
            f"reported more than {days}d ago on this same build, too old to "
            "prove the fleet is up but not contradicting it"
        )
    else:
        print(
            f"farm: agent {version}; no worker has ever reported, so nothing "
            "confirms which agent build the fleet will run"
        )
    return version


# Verdicts that mean a leaf would look for a package under a prefix nobody wrote:
# a readable report naming another build, at any age, or a fleet whose reports the
# pool cannot read at all (a SeatReport contract skew is itself a mismatch).
_AGENT_VERDICT_BLOCKS = ("mismatch", "unreadable")
_AGENT_VERDICTS = (*_AGENT_VERDICT_BLOCKS, "matched", "unverified")


def _agents_summary(line: str) -> dict:
    """The parsed and validated last stdout line of ``farm.py agents --json``."""
    try:
        summary = json.loads(line)
    except json.JSONDecodeError:
        raise FarmPreflightError(
            f"agents printed no JSON summary; last line: {line[:200]}"
        ) from None
    if not isinstance(summary, dict):
        raise FarmPreflightError(f"agents summary is not an object: {line[:200]}")
    version = summary.get("agent_version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9a-f]{16}", version):
        raise FarmPreflightError(
            f"agents summary agent_version is not 16 hex: {version!r}"
        )
    if summary.get("verdict") not in _AGENT_VERDICTS:
        raise FarmPreflightError(
            f"agents summary verdict is not one of {_AGENT_VERDICTS}: "
            f"{summary.get('verdict')!r}"
        )
    for key in ("workers", "ignored"):
        if not isinstance(summary.get(key), list):
            raise FarmPreflightError(
                f"agents summary {key} is not a list: {line[:200]}"
            )
    # Both windows are printed back to the operator, and the pool emits them as
    # second counts. A strict check keeps a silent type change on that side from
    # arriving here as a sentence with "120.0s" in it.
    for key in ("fresh_within_s", "evidence_horizon_s"):
        value = summary.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise FarmPreflightError(
                f"agents summary {key} is not an integer: {value!r}"
            )
    return summary


def _publish(pool: Path, sha: str, agent: str) -> str:
    """Run ``farm.py publish`` for ``sha`` and return the source identity.

    ``agent`` is the agent build the preflight checked the fleet against; the
    package the workers will look for is named after the agent the publish
    actually ran with, so the two have to be the same one.
    """
    publish = _pool_farm(pool, "publish", "--commit", sha, "--json")
    lines = [line for line in publish.stdout.splitlines() if line.strip()]
    if publish.returncode != 0 or not lines:
        raise FarmPreflightError(
            f"publish failed (exit {publish.returncode}){_tail(publish.stdout)}"
        )
    summary = _publish_summary(lines[-1], sha)
    published_agent = summary["agent_identity_sha256"][: len(agent)]
    if published_agent != agent:
        raise FarmPreflightError(
            f"publish used agent {published_agent}, but the fleet was checked "
            f"against {agent}; the pool checkout changed mid-preflight"
        )
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
    agent = summary.get("agent_identity_sha256")
    if not isinstance(agent, str) or not re.fullmatch(r"[0-9a-f]{64}", agent):
        raise FarmPreflightError(
            f"publish summary agent_identity_sha256 is not 64 hex: {agent!r}"
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
