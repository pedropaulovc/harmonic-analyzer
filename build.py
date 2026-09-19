"""Run the doit graph with a console verbosity flag, an executor and a leaf budget.

Examples:
    uv run python build.py --help
    uv run python build.py --verbosity warning -n 4
    uv run python build.py --verbosity debug check:math
    uv run python build.py --executor farm --leaf-timeout 90 assembly:harmonic_analyzer

The wrapper consumes ``--verbosity``, ``--executor`` and ``--leaf-timeout``; every
other argument is passed to ``doit`` unchanged. A leading ``--help``/``-h`` (after
doit's loader options, as ``DoitMain.run`` reads them) prints the wrapper's own
options and farm defaults and then doit's command list, whose ``build.py help
<command>``/``build.py help <task>`` lines are the route to doit's own help.
Structured telemetry capture remains full-fidelity.

``--executor farm`` (the ``build`` / ``build.cmd`` entry points) keeps doit as the
local dependency scheduler but runs every cache-missing COM task -- parts,
assemblies, drawings, the ``verify:*`` gates, ``preflight``, the neutral ``export``
and the release Pack-and-Go (``package:release``) -- on the SolidWorks build farm
instead of a local seat (``dodo._cached_com_action`` -> ``dodo._farm_build``). It
needs a clean tree whose HEAD is on ``origin`` (the farm clones from there), the
remote cache enabled (the farm hands results back through it), a pool checkout
whose agent build is the one the fleet runs (``farm.py agents``: a package
published for any other agent lands under a prefix no worker reads), and the
commit's sources published to the pool (``farm.py publish``) before doit starts.
That preflight runs for every doit command that executes task actions
(``Command.execute_tasks``: ``run``, explicit or implicit, and ``strace``); the
others (``list``, ``info``, ``clean``, ...) and ``--help``/``--version`` skip it.
``-n`` is added for ``run`` only. A release therefore needs no local SolidWorks;
only the Blender-bound ``gallery`` task and the publishing half of ``release``
run here.
"""

from __future__ import annotations

import argparse
import getopt
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from doit.doit_cmd import DoitMain

REPO_ROOT = Path(__file__).resolve().parent
_LEVELS = ("debug", "info", "success", "warning", "error", "critical")
_EXECUTORS = ("local", "farm")
_DEFAULT_FARM_PARALLELISM = "8"
_PUBLISH_STATES = ("published", "exists")

# doit hands the leading task-loader options to ``getopt`` before it reads the
# subcommand (``DoitMain.run``); the wrapper's ``-h``/``--help`` ride along so a
# help request after them is seen where it stands.
_LOADER_SHORT = "f:d:kh"
_LOADER_LONG = ("file=", "dir=", "seek-file", "help")
_HELP = ("--help", "-h")

_USAGE = (
    "build.py [--verbosity LEVEL] [--executor {local,farm}] "
    "[--leaf-timeout MINUTES] [doit arguments ...]"
)
_DESCRIPTION = """\
Run the doit graph (dodo.py). Only the options below belong to the wrapper; every
other argument goes to doit unchanged, so `build.py part:cone_gear`, `build.py
-n 4`, `build.py list` and `build.py help run` mean what they mean under `doit`."""
_EPILOG = f"""\
farm defaults (--executor farm; `build` / `build.cmd` pass it for you):
  parallelism   -n {_DEFAULT_FARM_PARALLELISM} unless you pass -n/--process or set HARMONIC_FARM_PARALLELISM
  leaf timeout  15 min per attempt (the control plane's default) unless you pass
                --leaf-timeout or HARMONIC_FARM_LEAF_TIMEOUT_S (seconds) is
                already set; the farm clamps either to 1 min - 3 h. A cold leaf
                measured 61.5 min, so raise it for anything cold
  preflight     clean tree, HEAD on origin, remote cache ro/rw, fleet agent
                matching the pool checkout, sources published -- only before a
                command that executes tasks (run, strace); --help, list, info,
                clean, ... never reach it

doit's own help follows. `build.py help run` shows the run options (-n, -a,
-c, -v ...), `build.py help <task>` a task's own parameters."""


class FarmPreflightError(Exception):
    """Why a farm run must stop before doit starts; printed as ``farm: <reason>``."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build.py",
        usage=_USAGE,
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument(
        "--verbosity",
        choices=_LEVELS,
        default="warning",
        metavar="LEVEL",
        help="console level for the build's own logging, one of %(choices)s "
        "(default: %(default)s; sets HARMONIC_VERBOSITY). doit's run "
        "verbosity stays `-v N`.",
    )
    parser.add_argument(
        "--executor",
        choices=_EXECUTORS,
        default=os.environ.get("HARMONIC_EXECUTOR", "local"),
        help="where cache-missing SolidWorks tasks build: local = a seat on this "
        "machine, farm = the SolidWorks build farm (default: HARMONIC_EXECUTOR "
        "if set, else local)",
    )
    # A cold leaf (source sync plus a cold SOLIDWORKS start) measured 61.5 min on
    # the farm, well past the control plane's 15 min default, so a run that knows
    # it is cold raises the per-attempt budget for the leaves it dispatches.
    parser.add_argument(
        "--leaf-timeout",
        type=int,
        metavar="MINUTES",
        help="per-attempt budget for each farm leaf, in minutes (overrides an "
        "inherited HARMONIC_FARM_LEAF_TIMEOUT_S; the farm clamps it to 1-180)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    options, doit_args = parser.parse_known_args(argv)
    doit_args = list(doit_args)
    if _asks_for_help(doit_args):
        parser.print_help()
        print()
        return DoitMain().run(["--help"])
    if options.verbosity is not None:
        os.environ["HARMONIC_VERBOSITY"] = options.verbosity
    doit = DoitMain()
    if options.leaf_timeout is not None:
        os.environ["HARMONIC_FARM_LEAF_TIMEOUT_S"] = str(options.leaf_timeout * 60)
    if options.executor == "farm":
        executing = _executing_command(doit_args, doit.get_cmds())
        if executing is not None:
            try:
                _farm_preflight()
            except FarmPreflightError as problem:
                print(f"farm: {problem}", file=sys.stderr)
                return 2
            print(
                "farm: every SolidWorks task runs on the farm (parts, assemblies, "
                "drawings, verify:*, preflight, export, package:release)"
            )
            doit_args = _with_farm_parallelism(doit_args, *executing)
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


def _excluded_submodules() -> frozenset[str]:
    """Submodule paths ``.farm-sources.json`` declares the farm never reads.

    The same file the pool's publisher reads off the checked-out commit, read
    here for one purpose only: deciding whether a submodule's local state can
    affect the build. A missing file declares nothing. A file that is PRESENT
    and malformed is refused right here rather than read as "exclude
    nothing": degrading would report the excluded submodule as a dirty tree,
    send the operator to clone 878 MB, and only then have ``farm.py publish``
    -- which runs inside this same preflight, off the same file -- refuse it
    anyway. Paths are normalized the way the publisher normalizes them, so
    ``references/`` and ``./references`` mean here what they mean there.
    """
    source = REPO_ROOT / ".farm-sources.json"
    try:
        text = source.read_text("utf-8")
    except FileNotFoundError:
        return frozenset()
    except (OSError, UnicodeError) as exc:
        raise FarmPreflightError(f".farm-sources.json is unreadable: {exc}")
    try:
        declared = json.loads(text)
    except ValueError as exc:
        raise FarmPreflightError(f".farm-sources.json is not valid JSON: {exc}")
    if not isinstance(declared, dict):
        raise FarmPreflightError(".farm-sources.json must be a JSON object")
    paths = declared.get("exclude_submodules", [])
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        raise FarmPreflightError(
            ".farm-sources.json: exclude_submodules must be a list of strings"
        )
    return frozenset(PurePosixPath(path).as_posix() for path in paths)


def _dirty_submodules() -> list[str]:
    """Submodule paths whose local state the farm would not reproduce.

    ``git submodule status`` marks an UNINITIALIZED submodule ``-`` alongside
    the ``+`` of a checked-out commit that differs from the index. Those are
    not the same claim: a submodule that was never cloned holds exactly the
    pin the commit records, so there is nothing local for the farm to miss.
    It still refuses by default, because the local doit graph reads those
    files -- but NOT for a submodule this commit declares the farm never
    reads. Without the exemption, dispatching a build requires cloning the
    878 MB of photographs ``.farm-sources.json`` exists to keep off every
    worker (measured 2026-09-18: the exclusion could not be exercised at all).

    The exemption covers every farm leaf and both ``build`` and
    ``build_bare``. It does NOT make the submodule optional for the whole
    repo: ``gallery`` -- a submitter-side task in ``release``'s closure --
    reads the manifest photographs directly and fails in
    ``export_models._gallery_input_digest`` if they were never cloned, so a
    release still needs ``git submodule update --init references``.
    """
    excluded = _excluded_submodules()
    dirty = []
    for line in _git("submodule", "status", "--recursive").splitlines():
        if not line or line.startswith(" "):
            continue
        path = line.split()[1]
        if line.startswith("-") and path in excluded:
            continue
        dirty.append(path)
    return dirty


def _farm_preflight() -> None:
    """Publish HEAD to the farm and stamp the environment; raises to stop."""
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    dirty = [line[3:] for line in status.splitlines()] + _dirty_submodules()
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


def _doit_head(doit_args: list[str]) -> tuple[bool, int, int | None]:
    """How ``DoitMain.run`` reads argv before it picks a subcommand.

    Returns ``(help, loader_end, head)``. doit hands the leading loader options
    to ``getopt`` (``f:d:k`` / ``file= dir= seek-file``: grouped shorts, attached
    or separate values, unique long prefixes) and, when that parse fails, gives
    the whole argv to ``run`` instead, so ``loader_end`` is then 0. Every
    remaining ``name=value`` token is a command-line variable, dropped before the
    subcommand is read, so ``head`` is the first token that is not one (``None``
    when nothing but variables follows). ``-h``/``--help`` are the wrapper's
    (doit only knows a bare leading ``--help``): ``help`` is true when getopt
    meets one among the loader options (even malformed, ``--help=x``) or when
    it is the head.
    """
    try:
        opts, rest = getopt.getopt(doit_args, _LOADER_SHORT, _LOADER_LONG)
    except getopt.GetoptError as error:
        if error.opt in ("h", "help"):
            return True, 0, None
        opts, rest = [], doit_args
    loader_end = len(doit_args) - len(rest)
    head = next(
        (loader_end + j for j, arg in enumerate(rest) if not _is_variable(arg)),
        None,
    )
    asked = any(opt in _HELP for opt, _value in opts) or (
        head is not None and doit_args[head] in _HELP
    )
    return asked, loader_end, head


def _is_variable(arg: str) -> bool:
    """``DoitMain.process_args``'s test for a ``name=value`` command-line variable."""
    return not arg.startswith("-") and "=" in arg


def _asks_for_help(doit_args: list[str]) -> bool:
    """A leading ``--help``/``-h`` is the wrapper's; ``build.py help <x>`` and a
    per-command ``--help`` stay doit's."""
    return _doit_head(doit_args)[0]


def _executing_command(doit_args: list[str], commands) -> tuple[str, int] | None:
    """The doit subcommand that would execute task actions and where its own
    arguments start; ``None`` when doit executes no task.

    doit's ``Command.execute_tasks`` is the verdict: ``run`` (explicit, or
    implicit when the head is a task name or nothing) and ``strace`` (a ``Run``
    subclass) execute actions, so a farm run needs the preflight; ``--help``/
    ``-h``/``--version`` and ``list``, ``info``, ``clean``, ``forget``, ...
    execute nothing and never reach it.
    """
    asked, loader_end, head = _doit_head(doit_args)
    if asked:
        return None
    if head is None:
        return "run", loader_end  # implicit run of the default tasks
    name = doit_args[head]
    if name == "--version":
        return None
    if name not in commands:
        return "run", head  # implicit run of the named tasks
    if not commands.get_plugin(name).execute_tasks:
        return None
    return name, head + 1


def _with_farm_parallelism(doit_args: list[str], command: str, at: int) -> list[str]:
    """Keep up to ``HARMONIC_FARM_PARALLELISM`` (8) leaves in flight on the farm.

    Only ``run`` takes ``-n``, at ``at`` (see ``_executing_command``), unless the
    caller already chose ``-n``/``--process``; ``strace`` traces one task and
    has no such option.
    """
    if command != "run" or any(
        arg.startswith(("-n", "--process")) for arg in doit_args
    ):
        return doit_args
    workers = os.environ.get("HARMONIC_FARM_PARALLELISM", _DEFAULT_FARM_PARALLELISM)
    return [*doit_args[:at], "-n", workers, *doit_args[at:]]


if __name__ == "__main__":
    raise SystemExit(main())
