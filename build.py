"""Run the doit graph locally with a console verbosity flag.

Examples:
    uv run python build.py --help
    uv run python build.py --verbosity warning
    uv run python build.py --verbosity debug check:math

The wrapper consumes ``--verbosity``, ``--force-cache-refresh`` and
``--force-cache-refresh-reason``; every other argument goes to ``doit`` unchanged.
A leading ``--help``/``-h`` (after doit's loader options, as ``DoitMain.run``
reads them) prints the wrapper's own options and then doit's command list, whose
``build.py help <command>``/``build.py help <task>`` lines are the route to
doit's own help. Structured telemetry capture remains full-fidelity.

``build.py`` always runs the local executor: a cache-missing COM task builds on
this machine's seat. Farm builds go through ``farm_build.py``. The farm worker
also runs each leaf through this entry point (``--farm-execution-*``, the
selected canonical closure).
"""

from __future__ import annotations

import argparse
import copy
import functools
import getopt
import json
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path

# Capture the dependency-import boundary before loading doit.
_BUILD_IMPORT_STARTED = time.perf_counter()

from doit.cmd_base import get_loader, tasks_and_deps_iter  # noqa: E402
from doit.cmdparse import CmdParseError  # noqa: E402
from doit.control import TaskControl  # noqa: E402
from doit.doit_cmd import DoitMain  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent
# Read as an AST literal by the pool; changing it changes the graph contract.
SELECTIVE_EXECUTION_CAPABILITY = "canonical-closure-v1"
_LEVELS = ("debug", "info", "success", "warning", "error", "critical")

# doit hands the leading task-loader options to ``getopt`` before it reads the
# subcommand (``DoitMain.run``); the wrapper's ``-h``/``--help`` ride along so a
# help request after them is seen where it stands.
_LOADER_SHORT = "f:d:kh"
_LOADER_LONG = ("file=", "dir=", "seek-file", "help")
_HELP = ("--help", "-h")

_USAGE = (
    "build.py [--verbosity LEVEL] "
    "[--force-cache-refresh LABELS --force-cache-refresh-reason TEXT] [doit arguments ...]"
)
_DESCRIPTION = """\
Run the doit graph (dodo.py) on this machine. Only the options below belong to the
wrapper; every other argument goes to doit unchanged, so `build.py part:dt_cone_gear`,
`build.py --continue`, `build.py list` and `build.py help run` mean what they mean
under `doit`. Farm builds: `farm_build.py run`."""
_EPILOG = """\
doit's own help follows. `build.py help run` shows the run options (-n, -a,
-c, -v ...), `build.py help <task>` a task's own parameters."""


class CacheRefreshError(Exception):
    """Why a refresh request must stop before any task or fleet side effect."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build.py",
        usage=_USAGE,
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        allow_abbrev=False,
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
        "--force-cache-refresh",
        action="append",
        default=[],
        metavar="LABELS",
        help="rebuild and overwrite selected remote-cache leaves (repeatable; "
        "comma-separated exact task names; requires cache mode rw and a reason)",
    )
    parser.add_argument(
        "--force-cache-refresh-reason",
        metavar="TEXT",
        help="required refresh audit reason: nonblank single-line text, no control "
        "characters, at most 160 characters",
    )
    for option in ("graph", "task", "identity"):
        parser.add_argument(f"--farm-execution-{option}", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    build_import_seconds = time.perf_counter() - _BUILD_IMPORT_STARTED
    parser = _parser()
    options, doit_args = parser.parse_known_args(argv)
    doit_args = list(doit_args)
    selected_options = (
        options.farm_execution_graph,
        options.farm_execution_task,
        options.farm_execution_identity,
    )
    selected_mode = any(value is not None for value in selected_options)
    if selected_mode:
        from cad.scripts._selected_execution import (
            SelectedExecutionError, SelectedTaskLoader, validate_invocation,
        )

        try:
            if not all(selected_options):
                raise SelectedExecutionError("internal execution requires graph, task and identity together")
            validate_invocation(doit_args, options.farm_execution_task)
        except SelectedExecutionError as problem:
            print(f"farm execution: {problem}", file=sys.stderr)
            return 2
    refresh_labels = list(dict.fromkeys(
        label.strip()
        for option in options.force_cache_refresh
        for label in option.split(",")
    ))
    refresh_request = None
    if options.force_cache_refresh_reason is not None and not refresh_labels:
        print(
            "cache refresh: --force-cache-refresh-reason requires "
            "--force-cache-refresh labels",
            file=sys.stderr,
        )
        return 2
    if refresh_labels:
        sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))
        import _artifact_cache

        try:
            reason = _artifact_cache.validate_refresh_reason(options.force_cache_refresh_reason)
            if not _artifact_cache.writable():
                raise RuntimeError("forced cache refresh requires HARMONIC_REMOTE_CACHE_MODE=rw")
            if "" in refresh_labels:
                raise RuntimeError("--force-cache-refresh contains an empty task label")
        except RuntimeError as problem:
            print(f"cache refresh: {problem}", file=sys.stderr)
            return 2
        refresh_request = json.dumps(
            {"labels": refresh_labels, "reason": reason}, separators=(",", ":")
        )
    if _asks_for_help(doit_args):
        parser.print_help()
        print()
        return DoitMain().run(["--help"])
    if options.verbosity is not None:
        os.environ["HARMONIC_VERBOSITY"] = options.verbosity
    # dodo reads the executor while loading the graph; this entry point is
    # always local, whatever an inherited HARMONIC_EXECUTOR says.
    os.environ["HARMONIC_EXECUTOR"] = "local"

    if selected_mode:
        try:
            selected_loader = SelectedTaskLoader(
                REPO_ROOT, Path(options.farm_execution_graph),
                options.farm_execution_task, options.farm_execution_identity,
                capability=SELECTIVE_EXECUTION_CAPABILITY,
                isolate_tasks=_isolated_tasks,
                build_import_seconds=build_import_seconds,
            )
        except SelectedExecutionError as problem:
            print(f"farm execution: {problem}", file=sys.stderr)
            return 2
        main_class = _RefreshDoitMain if refresh_labels else DoitMain
        doit = main_class(task_loader=selected_loader)
    elif refresh_labels:
        doit = _RefreshDoitMain()
    else:
        doit = DoitMain()
    if refresh_labels:
        doit.refresh_labels = refresh_labels
    executing = _executing_command(doit_args, doit)
    if refresh_labels and executing is None:
        print("cache refresh: requires a command that executes selected tasks", file=sys.stderr)
        return 2
    refusal = _release_refusal(doit_args, executing)
    if refusal:
        print(f"release: {refusal}", file=sys.stderr)
        return 2
    previous_refresh = os.environ.get("HARMONIC_CACHE_REFRESH")
    if refresh_request is not None:
        os.environ["HARMONIC_CACHE_REFRESH"] = refresh_request
    try:
        return doit.run(doit_args)
    finally:
        if refresh_request is not None:
            if previous_refresh is None:
                os.environ.pop("HARMONIC_CACHE_REFRESH", None)
            else:
                os.environ["HARMONIC_CACHE_REFRESH"] = previous_refresh


def _release_refusal(
    doit_args: Sequence[str], executing: tuple[str, int] | None
) -> str | None:
    """Why this command may not run, if it EXECUTES ``release`` with debt left.

    ``info``/``clean``/``forget release`` publish nothing, so only a command
    doit executes (``_executing_command``) is gated (Codex on #880)."""
    if executing is None or not _selects_release(doit_args):
        return None
    return _visibility_debt()


def _selects_release(doit_args: Sequence[str]) -> bool:
    """Whether the command names the ``release`` task (not a forwarded arg)."""
    selection = list(doit_args)
    if "--" in selection:
        selection = selection[: selection.index("--")]
    return "release" in selection


def _visibility_debt() -> str | None:
    """Refuse a release whose parts still save reference sketches shown.

    Seat-free and instant, so it runs before any leaf is dispatched rather
    than after hours of gates (visibility_debt, #880)."""
    sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))
    import visibility_debt

    try:
        visibility_debt.assert_no_visibility_debt()
    except RuntimeError as problem:
        return str(problem)
    return None


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
) -> TaskControl:
    """Parse farm selections exactly as doit will, without consuming real tasks."""
    control = TaskControl(
        _isolated_tasks(task_list), auto_delayed_regex=auto_delayed_regex
    )
    control.process(selection)
    return control


def _require_cache_refresh(task_list, selected: set[str], labels: list[str]) -> None:
    """Admit exact remote-keyed leaves that doit will actually execute."""
    tasks = {task.name: task for task in task_list}
    for label in labels:
        task = tasks.get(label)
        if task is None:
            raise CacheRefreshError(f"unknown task {label!r}")
        if label not in selected:
            raise CacheRefreshError(f"task {label!r} is not in the selected task closure")
        if not any(
            getattr(getattr(action, "py_callable", None), "_remote_cache_action", False)
            for action in task.actions
        ):
            raise CacheRefreshError(f"task {label!r} is not a remote-cache-keyed leaf")
        # Task's normalized uptodate entries are (callable/bool, args, kwargs).
        # Keep trackers/value savers intact while overriding even present targets.
        task.uptodate.append((False, None, None))


def _refresh_commands(commands, labels):
    if not labels:
        return commands
    for name in commands:
        command_class = commands.get_plugin(name)
        if not getattr(command_class, "execute_tasks", False):
            continue

        def wrap(base):
            class RefreshCommand(base):
                name = base.get_name()

                @functools.wraps(base._execute)
                def _execute(self, *args, **kwargs):
                    try:
                        # Name unknown refresh labels before doit's selector
                        # parser can turn the same typo into an unrelated exit 3.
                        known = {task.name for task in self.task_list}
                        for label in labels:
                            if label not in known:
                                raise CacheRefreshError(f"unknown task {label!r}")
                        control = _validate_farm_selection(
                            self.task_list,
                            self.sel_tasks,
                            auto_delayed_regex=kwargs.get("auto_delayed_regex", False),
                        )
                        if kwargs.get("single", False):
                            # Run reparses single-mode selectors; mirror its
                            # task-option consumption on the isolated graph.
                            control.process(self.sel_tasks)
                            selected = set(control.selected_tasks)
                        else:
                            selected = {
                                task.name
                                for task in tasks_and_deps_iter(
                                    control.tasks, control.selected_tasks
                                )
                            }
                        _require_cache_refresh(self.task_list, selected, labels)
                    except BaseException as problem:
                        self.dep_manager.close()
                        if isinstance(problem, CacheRefreshError):
                            print(f"cache refresh: {problem}", file=sys.stderr)
                            return 2
                        raise
                    return base._execute(self, *args, **kwargs)

            return RefreshCommand

        commands[name] = wrap(command_class)
    return commands


class _RefreshDoitMain(DoitMain):
    """Admit refresh requests at doit's loaded-graph execution boundary."""

    refresh_labels: list[str] = []

    def get_cmds(self):
        return _refresh_commands(super().get_cmds(), self.refresh_labels)


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


if __name__ == "__main__":
    raise SystemExit(main())
