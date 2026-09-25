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
needs a clean project tree, the remote cache enabled, and a fleet that advertises
this client's farm protocol. The worker shallow-fetches the requested committed
HEAD directly from the approved repository into its disposable workspace, resets
and cleans that workspace, checks out pinned required submodules, and keeps its
locked Python environment outside the cleaned checkout.
That preflight runs for every doit command that executes task actions
(``Command.execute_tasks``: ``run``, explicit or implicit, and ``strace``) whose
argv the command's own parser accepts; the others (``list``, ``info``, ``clean``,
...), ``--help``/``--version`` and an argv doit would reject (``run --help``: doit
has no per-command help and exits 3) skip it and pass through untouched.
``-n`` is added for ``run`` only. A release therefore needs no local SolidWorks;
only the Blender-bound ``gallery`` task and the publishing half of ``release``
run here.
"""

from __future__ import annotations

import argparse
import copy
import functools
import getopt
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from doit.cmd_base import get_loader
from doit.cmdparse import CmdParseError
from doit.control import TaskControl
from doit.doit_cmd import DoitMain

REPO_ROOT = Path(__file__).resolve().parent
_LEVELS = ("debug", "info", "success", "warning", "error", "critical")
_EXECUTORS = ("local", "farm")
_DEFAULT_FARM_PARALLELISM = "8"

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
  preflight     clean local project inputs, remote cache ro/rw, fleet protocol
                compatible -- only before a command that executes tasks (run,
                strace) with an argv doit accepts; --help, list, info, clean, ...
                never reach it

doit's own help follows. `build.py help run` shows the run options (-n, -a,
-c, -v ...), `build.py help <task>` a task's own parameters."""


class FarmPreflightError(Exception):
    """Why a farm run must stop before task actions; printed as ``farm: <reason>``."""


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
    if options.leaf_timeout is not None:
        os.environ["HARMONIC_FARM_LEAF_TIMEOUT_S"] = str(options.leaf_timeout * 60)
    # dodo reads the executor while loading the graph; an explicit
    # --executor must win over an inherited HARMONIC_EXECUTOR.
    os.environ["HARMONIC_EXECUTOR"] = options.executor

    doit = _FarmDoitMain() if options.executor == "farm" else DoitMain()
    if options.executor == "farm":
        executing = _executing_command(doit_args, doit)
        if executing is not None:
            doit_args = _with_farm_parallelism(doit_args, *executing)
    return doit.run(doit_args)


def _isolated_tasks(task_list):
    """Copy only the task state needed by doit's mutating selection pass.

    Task.__getstate__ omits runtime action/value-saver state during copy.copy;
    TaskControl does not use it. The original tasks remain executable.
    """
    isolated = []
    for task in task_list:
        task_copy = copy.copy(task)
        task_copy.task_dep = task.task_dep.copy()
        if task.loader:
            task_copy.loader = copy.copy(task.loader)
            task_copy.loader.regex_groups = task.loader.regex_groups.copy()
        isolated.append(task_copy)
    return isolated


def _validate_farm_selection(
    task_list, selection, *, auto_delayed_regex: bool = False
) -> None:
    """Parse farm selections exactly as doit will, without consuming real tasks."""
    control = TaskControl(
        _isolated_tasks(task_list), auto_delayed_regex=auto_delayed_regex
    )
    control.process(selection)


def _farm_command(command_class):
    """Wrap one native task-executing command at its loaded-graph boundary."""

    class FarmCommand(command_class):
        name = command_class.get_name()

        @functools.wraps(command_class._execute)
        def _execute(self, *args, **kwargs):
            try:
                _validate_farm_selection(
                    self.task_list,
                    self.sel_tasks,
                    auto_delayed_regex=kwargs.get("auto_delayed_regex", False),
                )
                _farm_preflight()
                print(
                    "farm: every SolidWorks task runs on the farm (parts, "
                    "assemblies, drawings, verify:*, preflight, export, "
                    "package:release)"
                )
            except BaseException as problem:
                self.dep_manager.close()
                if isinstance(problem, FarmPreflightError):
                    print(f"farm: {problem}", file=sys.stderr)
                    return 2
                raise
            return command_class._execute(self, *args, **kwargs)

    return FarmCommand


class _FarmDoitMain(DoitMain):
    """Doit with preflight wrappers around native action-executing commands."""

    def get_cmds(self):
        commands = super().get_cmds()
        for name in commands:
            command_class = commands.get_plugin(name)
            if getattr(command_class, "execute_tasks", False):
                commands[name] = _farm_command(command_class)
        return commands


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

    The declaration belongs to the commit and is read here only to decide
    whether a submodule's local state can affect doit's local graph and cache
    keys. A missing file declares nothing. A present malformed file is refused
    rather than degraded to "exclude nothing". Paths are normalized exactly as
    the worker normalizes them, so ``references/`` and ``./references`` mean
    the same thing.
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
    """Submodule paths whose local state can change the local graph or cache keys.

    ``git submodule status`` marks an uninitialized submodule ``-`` alongside
    the ``+`` of a checkout at another commit. The local doit graph reads
    required submodule files, so required paths must be initialized at the
    committed pin. A submodule this commit explicitly excludes from every farm
    leaf may remain uninitialized; a modified checkout still blocks.

    The exemption covers every farm leaf and both ``build`` and
    ``build_bare``. It does not make the submodule optional for the whole repo:
    ``gallery`` is submitter-side, belongs to ``release``'s closure, and reads
    the manifest photographs directly. A release still needs
    ``git submodule update --init references``.
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
    """Validate local graph inputs, fleet protocol, and stamp committed HEAD."""
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    dirty = [line[3:] for line in status.splitlines()] + _dirty_submodules()
    if dirty:
        raise FarmPreflightError(
            "working tree is dirty:\n" + "\n".join(f"  {p}" for p in dirty)
        )
    sha = _git("rev-parse", "HEAD").strip()

    sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))
    import _artifact_cache
    import _farm

    if not _artifact_cache.enabled():
        raise FarmPreflightError("HARMONIC_REMOTE_CACHE_MODE must be ro or rw")

    _require_fleet_protocol(_pool_home(), _farm.FARM_PROTOCOL_VERSION)
    os.environ["HARMONIC_FARM_COMMIT"] = sha
    os.environ["HARMONIC_SW_AUTOSTART"] = "0"


def _pool_home() -> Path:
    return Path(
        os.environ.get("SOLIDWORKS_POOL_HOME", REPO_ROOT.parent / "solidworks-pool")
    )


def _pool_farm(pool: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run one ``farm.py`` subcommand from the pool checkout, capturing stdout.

    stderr is inherited so the pool's own progress and diagnostics reach the
    console as they happen; stdout is the machine-readable result. The nested
    ``uv`` targets the pool's own environment (``--project``); the
    ``VIRTUAL_ENV`` this process inherited from the outer ``uv run`` names
    ours, which uv would (correctly) ignore with a warning on every call.
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
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    try:
        return subprocess.run(
            argv, cwd=REPO_ROOT, env=env, stdout=subprocess.PIPE, text=True
        )
    except OSError as exc:
        raise FarmPreflightError(
            f"{args[0]} could not start ({argv[0]}): {exc}"
        ) from None


def _dissenting_workers(reports: object, protocol: int) -> list[str]:
    """Stale reports that are incompatible with or unreadable under ``protocol``."""
    if not isinstance(reports, list):
        return []
    named = []
    for report in reports:
        if not isinstance(report, dict):
            named.append("? (protocol unreadable)")
            continue
        other = report.get("farm_protocol_version")
        if (
            isinstance(other, int)
            and not isinstance(other, bool)
            and other == protocol
        ):
            continue
        advertised = (
            f"protocol {other}"
            if isinstance(other, int) and not isinstance(other, bool)
            else "protocol unreadable"
        )
        age = report.get("age_s")
        if not isinstance(age, int):
            age = report.get("written_age_s")
        seen = f", last seen {age // 86400}d ago" if isinstance(age, int) else ""
        named.append(f"{report.get('worker_id') or '?'} ({advertised}{seen})")
    return sorted(named)


def _require_fleet_protocol(pool: Path, protocol: int) -> None:
    """Stop unless the pool CLI and every known worker support ``protocol``."""
    result = _pool_farm(pool, "agents", "--json")
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or not lines:
        raise FarmPreflightError(
            f"agents failed (exit {result.returncode}){_tail(result.stdout)}"
        )
    summary = _agents_summary(lines[-1], protocol)
    if summary["verdict"] in _PROTOCOL_VERDICT_BLOCKS:
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
    if fresh:
        print(f"farm: protocol {protocol} on {fresh} worker(s)")
    elif workers:
        print(
            f"farm: protocol {protocol}; no worker has reported within "
            f"{summary['fresh_within_s']}s, but the last report of "
            f"{len(workers)} worker(s) supports it"
        )
    elif summary["ignored"]:
        days = summary["evidence_horizon_s"] // 86400
        dissent = _dissenting_workers(summary["ignored"], protocol)
        if dissent:
            raise FarmPreflightError(
                f"farm protocol {protocol} is required, and no worker has "
                f"reported within {days}d, but the last report of "
                + ", ".join(dissent)
                + " is incompatible or unreadable. Deploy a protocol-compatible "
                "agent, or delete the seat report of an instance that will "
                "never come back."
            )
        print(
            f"farm: protocol {protocol}; {len(summary['ignored'])} worker(s) last "
            f"reported more than {days}d ago supporting it, too old to prove "
            "the fleet is up but not contradicting it"
        )
    else:
        print(
            f"farm: protocol {protocol}; no worker has ever reported, so "
            "compatibility is unconfirmed"
        )


_PROTOCOL_VERDICT_BLOCKS = ("mismatch", "unreadable")
_PROTOCOL_VERDICTS = (*_PROTOCOL_VERDICT_BLOCKS, "matched", "unverified")


def _agents_summary(line: str, expected_protocol: int) -> dict:
    """Parse and validate the last stdout line of ``farm.py agents --json``."""
    try:
        summary = json.loads(line)
    except json.JSONDecodeError:
        raise FarmPreflightError(
            f"agents printed no JSON summary; last line: {line[:200]}"
        ) from None
    if not isinstance(summary, dict):
        raise FarmPreflightError(f"agents summary is not an object: {line[:200]}")
    protocol = summary.get("farm_protocol_version")
    if not isinstance(protocol, int) or isinstance(protocol, bool):
        raise FarmPreflightError(
            "agents summary farm_protocol_version is not an integer: "
            f"{protocol!r}"
        )
    if protocol != expected_protocol:
        raise FarmPreflightError(
            f"pool CLI supports farm protocol {protocol}, but this client requires "
            f"{expected_protocol}"
        )
    if summary.get("verdict") not in _PROTOCOL_VERDICTS:
        raise FarmPreflightError(
            f"agents summary verdict is not one of {_PROTOCOL_VERDICTS}: "
            f"{summary.get('verdict')!r}"
        )
    for key in ("workers", "ignored"):
        if not isinstance(summary.get(key), list):
            raise FarmPreflightError(
                f"agents summary {key} is not a list: {line[:200]}"
            )
    for key in ("fresh_within_s", "evidence_horizon_s"):
        value = summary.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise FarmPreflightError(
                f"agents summary {key} is not an integer: {value!r}"
            )
    return summary


def _loader_parse(doit_args: list[str]) -> tuple[list[tuple[str, str]], list[str], bool]:
    """doit's leading loader-option parse (``DoitMain.run``): ``(opts, rest, help)``.

    doit hands the leading loader options to ``getopt`` (``f:d:k`` / ``file=
    dir= seek-file``: grouped shorts, attached or separate values, unique long
    prefixes) and, when that parse fails, gives the whole argv to ``run``
    instead. ``-h``/``--help`` are the wrapper's (doit only knows a bare leading
    ``--help``): ``help`` is true when getopt meets one among the loader
    options, even malformed (``--help=x``).
    """
    try:
        opts, rest = getopt.getopt(doit_args, _LOADER_SHORT, _LOADER_LONG)
    except getopt.GetoptError as error:
        return [], doit_args, error.opt in ("h", "help")
    return opts, rest, any(opt in _HELP for opt, _value in opts)


def _is_variable(arg: str) -> bool:
    """``DoitMain.process_args``'s test for a ``name=value`` command-line variable."""
    return not arg.startswith("-") and "=" in arg


def _asks_for_help(doit_args: list[str]) -> bool:
    """A leading ``--help``/``-h`` (past loader options and command-line
    variables) is the wrapper's; ``build.py help <x>`` stays doit's."""
    opts, rest, asked = _loader_parse(doit_args)
    head = next((arg for arg in rest if not _is_variable(arg)), None)
    return asked or head in _HELP


def _executing_command(doit_args: list[str], doit: DoitMain) -> tuple[str, int] | None:
    """The doit subcommand that would execute task actions and where ``-n`` goes;
    ``None`` when doit executes no task.

    Mirrors ``DoitMain.run``: past the loader options and the ``name=value``
    variables, the head names a subcommand or is a task of the implicit ``run``.
    doit's ``Command.execute_tasks`` is the verdict (``run`` and ``strace``, a
    ``Run`` subclass, execute actions; ``list``, ``info``, ``clean``, ... and
    ``--help``/``-h``/``--version`` do not), and the command's own option parser
    has the last word: an argv it rejects (``run --help``, ``-n abc``) makes doit
    print its parse error and exit 3 before any task, so the preflight is
    skipped and the argv passed through untouched. ``-n`` goes right after the
    loader options for an implicit run, right after ``run`` for an explicit one.
    """
    opts, rest, asked = _loader_parse(doit_args)
    if asked:
        return None
    args = [arg for arg in rest if not _is_variable(arg)]
    commands = doit.get_cmds()
    options_end = len(doit_args) - len(rest)
    if options_end and doit_args[options_end - 1] == "--" and all(
        value != "--" for _opt, value in opts
    ):
        options_end -= 1  # getopt swallowed the terminator; -n must precede it
    if not args or args[0] not in commands:
        name, at = "run", options_end  # implicit run: default or named tasks
    else:
        name = args.pop(0)
        if not commands.get_plugin(name).execute_tasks:
            return None
        at = doit_args.index(name, len(doit_args) - len(rest)) + 1
    loader = get_loader(doit.config, doit.task_loader, commands)
    command = commands.get_plugin(name)(
        task_loader=loader, config=doit.config, bin_name=doit.BIN_NAME, cmds=commands
    )
    try:
        command.cmdparser.parse(args)
    except CmdParseError:
        return None
    return name, at


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
