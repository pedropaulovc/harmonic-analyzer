"""Validate a trusted farm graph, then load its canonical doit task closure.

The graph selects names; it never supplies executable actions. Action arguments,
trackers and hooks remain exclusively owned by dodo's canonical factories.
"""

from __future__ import annotations

import functools
import hashlib
import importlib
import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from doit import loader
from doit.action import PythonAction
from doit.cmd_base import TaskLoader2
from doit.control import TaskControl
from doit.exceptions import InvalidDodoFile
from doit.task import Task

# canonical-closure-v1 is the exact schema-3/protocol-7 record contract below.
# Pool upgrades must migrate/version that contract explicitly, never retry full.
_SCHEMA_VERSION = 3
_FARM_PROTOCOL_VERSION = 7
_HEX_IDENTITY = re.compile(r"[0-9a-f]{64}\Z")
_TASK_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*\Z")
_LEAF_PREFIXES = frozenset(
    {"assembly", "check", "drawing", "package", "part", "verify", "verify_soundness"}
)
_RECORD_KEYS = frozenset(
    {"name", "dependencies", "file_dependencies", "targets", "actions"}
)


class SelectedExecutionError(InvalidDodoFile):
    """Refuse internal execution before any action, without a full-loader retry."""


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value, allow_nan=False, ensure_ascii=False,
            separators=(",", ":"), sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise SelectedExecutionError(f"graph is not canonical JSON: {error}") from error


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SelectedExecutionError(f"graph has duplicate JSON key {key!r}")
        result[key] = value
    return result


def _source_commit(workspace: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"], cwd=workspace,
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise SelectedExecutionError(f"cannot read selected source commit: {error}") from error
    return result.stdout.strip()


def _workspace_path(workspace: Path, value: str) -> str:
    """The pool's path-only contract: resolved repo-relative POSIX spelling."""
    try:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = workspace / candidate
        candidate = candidate.resolve(strict=False)
    except (OSError, ValueError) as error:
        raise SelectedExecutionError(
            f"cannot normalize task path {value!r}: {error}"
        ) from error
    root_parts = [os.path.normcase(part) for part in workspace.parts]
    candidate_parts = [os.path.normcase(part) for part in candidate.parts]
    if candidate_parts[:len(root_parts)] != root_parts:
        raise SelectedExecutionError(f"task path escapes selected workspace: {value!r}")
    return PurePosixPath(*candidate.parts[len(root_parts):]).as_posix()


def task_record(workspace: Path, task: Task) -> dict[str, Any]:
    """Comparable projection of a TaskControl-processed canonical Task.

    Deliberately do not normalize action arguments a second time in the producer.
    The trusted graph hash still binds them; only the live canonical actions run.
    """
    workspace = workspace.resolve(strict=False)
    unsupported = [
        label for label, value in (
            ("delayed loader", task.loader), ("calc_dep", task.calc_dep),
            ("setup", task.setup_tasks), ("getargs", task.getargs),
        ) if value
    ]
    if unsupported:
        raise SelectedExecutionError(
            f"task {task.name!r} uses unsupported features: {', '.join(unsupported)}"
        )
    actions = []
    for action in task.actions:
        if not isinstance(action, PythonAction):
            raise SelectedExecutionError(f"task {task.name!r} has a non-Python action")
        module = getattr(action.py_callable, "__module__", None)
        name = getattr(action.py_callable, "__qualname__", None)
        if not isinstance(module, str) or not isinstance(name, str) or name.endswith("<lambda>"):
            raise SelectedExecutionError(f"task {task.name!r} has no stable callable identity")
        actions.append(f"{module}.{name}")
    return {
        "name": task.name,
        "dependencies": sorted(set(task.task_dep)),
        "file_dependencies": sorted(_workspace_path(workspace, path) for path in task.file_dep),
        "targets": sorted(_workspace_path(workspace, path) for path in task.targets),
        "actions": actions,
    }


def validate_invocation(arguments: list[str], task_name: str) -> None:
    """Only the serial, dependency-preserving worker invocation is internal."""
    ordinary = ["run", "-n", "0", task_name]
    forced = ["run", "--always-execute", "-n", "0", task_name]
    if arguments not in (ordinary, forced):
        raise SelectedExecutionError(
            "internal execution requires run [--always-execute] -n 0 and exactly the selected task"
        )


class SelectedTaskLoader(TaskLoader2):
    """A name-selecting loader retaining the original genuine Task lifecycle."""

    def __init__(
        self, workspace: Path, graph_path: Path, task_name: str,
        expected_identity: str, *, capability: str,
        isolate_tasks: Callable[[Iterable[Task]], list[Task]],
        build_import_seconds: float | None = None,
    ) -> None:
        super().__init__()
        self.workspace = workspace.resolve(strict=False)
        self.task_name = task_name
        self.isolate_tasks = isolate_tasks
        self.started = time.perf_counter()
        self.first_action = False
        self.module = None
        if build_import_seconds is not None:
            self._marker("build_import", seconds=build_import_seconds)
        if not graph_path.is_absolute():
            raise SelectedExecutionError("internal graph path must be absolute")
        if not isinstance(expected_identity, str) or not _HEX_IDENTITY.fullmatch(expected_identity):
            raise SelectedExecutionError("internal graph identity must be 64 lowercase hexadecimal characters")
        prefix, separator, _ = task_name.partition(":")
        if not _TASK_NAME.fullmatch(task_name) or not (
            (separator and prefix in _LEAF_PREFIXES) or task_name in {"export", "preflight"}
        ):
            raise SelectedExecutionError(f"unsupported internal leaf {task_name!r}")
        try:
            graph = json.loads(graph_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        except (OSError, UnicodeError, ValueError) as error:
            raise SelectedExecutionError(f"cannot read trusted execution graph: {error}") from error
        if not isinstance(graph, dict):
            raise SelectedExecutionError("execution graph must be an object")
        payload = {key: value for key, value in graph.items() if key != "graph_identity_sha256"}
        identity = hashlib.sha256(_canonical_json(payload)).hexdigest()
        if graph.get("graph_identity_sha256") != expected_identity or identity != expected_identity:
            raise SelectedExecutionError("execution graph identity differs from the trusted identity")
        if type(graph.get("schema_version")) is not int or graph["schema_version"] != _SCHEMA_VERSION:
            raise SelectedExecutionError("execution graph schema is incompatible")
        if type(graph.get("farm_protocol_version")) is not int or graph["farm_protocol_version"] != _FARM_PROTOCOL_VERSION:
            raise SelectedExecutionError("execution graph farm protocol is incompatible")
        if graph.get("execution_loader") != capability:
            raise SelectedExecutionError("execution graph loader capability is incompatible")
        commit = graph.get("commit")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise SelectedExecutionError("execution graph commit must be a full source identity")
        if commit != _source_commit(self.workspace):
            raise SelectedExecutionError("execution graph commit differs from selected source HEAD")
        self.records = self._records(graph)
        if task_name not in self.records or not self.records[task_name]["actions"]:
            raise SelectedExecutionError("selected leaf is not a unique action-bearing graph task")
        self.names = self._closure([task_name])

    def _marker(self, phase: str, **fields: Any) -> None:
        # Bounded structured stdout works before dodo/telemetry have imported.
        # Dependency restore remains between first_action and selected_action.
        try:
            print("farm-execution " + json.dumps({
                "phase": phase, "elapsed_s": round(time.perf_counter() - self.started, 6),
                **fields,
            }, separators=(",", ":"), sort_keys=True), flush=True)
        except (OSError, ValueError):
            pass

    @contextmanager
    def _phase(self, name: str):
        start = time.perf_counter()
        status = "error"
        try:
            yield
            status = "ok"
        finally:
            self._marker(name, seconds=round(time.perf_counter() - start, 6), status=status)

    def _records(self, graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
        entries = graph.get("tasks")
        if not isinstance(entries, list):
            raise SelectedExecutionError("graph tasks must be an array")
        records: dict[str, dict[str, Any]] = {}
        for record in entries:
            if not isinstance(record, dict) or set(record) != _RECORD_KEYS:
                raise SelectedExecutionError("graph task has an invalid record shape")
            name = record["name"]
            if not isinstance(name, str) or not _TASK_NAME.fullmatch(name) or name in records:
                raise SelectedExecutionError("graph task names must be valid and unique")
            for field in ("dependencies", "file_dependencies", "targets"):
                values = record[field]
                if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
                    raise SelectedExecutionError(f"task {name!r} has invalid {field}")
                if values != sorted(values) or (field == "dependencies" and len(values) != len(set(values))):
                    raise SelectedExecutionError(f"task {name!r} has noncanonical {field}")
                if field != "dependencies" and any(
                    "\\" in value or PurePosixPath(value).is_absolute()
                    or PureWindowsPath(value).drive
                    or ".." in PurePosixPath(value).parts
                    or PurePosixPath(value).as_posix() != value
                    for value in values
                ):
                    raise SelectedExecutionError(f"task {name!r} has noncanonical workspace paths")
            actions = record["actions"]
            if not isinstance(actions, list) or any(
                not isinstance(action, dict) or set(action) != {"kind", "callable", "args", "kwargs"}
                or action["kind"] != "python" or not isinstance(action["callable"], str)
                or not action["callable"] or not isinstance(action["args"], list)
                or not isinstance(action["kwargs"], dict)
                for action in actions
            ):
                raise SelectedExecutionError(f"task {name!r} has invalid Python action records")
            records[name] = record
        for name, record in records.items():
            if any(dependency not in records for dependency in record["dependencies"]):
                raise SelectedExecutionError(f"task {name!r} has a missing graph dependency")
        # Detect cycles before doit can execute a different, acyclic branch.
        finished: set[str] = set()
        active: set[str] = set()
        for root in records:
            stack = [(root, False)]
            while stack:
                name, leaving = stack.pop()
                if leaving:
                    active.remove(name)
                    finished.add(name)
                elif name in active:
                    raise SelectedExecutionError(f"graph dependency cycle at {name!r}")
                elif name not in finished:
                    active.add(name)
                    stack.append((name, True))
                    stack.extend((dependency, False) for dependency in records[name]["dependencies"])
        roots = graph.get("requested_targets")
        if not isinstance(roots, list) or not roots or not all(isinstance(name, str) for name in roots):
            raise SelectedExecutionError("graph requested_targets must name its exported roots")
        if len(roots) != len(set(roots)) or any(name not in records for name in roots):
            raise SelectedExecutionError("graph requested roots must be present and unique")
        self.records = records
        if self._closure(roots) != set(records):
            raise SelectedExecutionError("graph contains tasks outside its exported root closure")
        return records

    def _closure(self, roots: Iterable[str]) -> set[str]:
        result: set[str] = set()
        pending = list(roots)
        while pending:
            name = pending.pop()
            if name not in result:
                result.add(name)
                pending.extend(self.records[name]["dependencies"])
        return result

    def _require_workspace_authority(self, module: Any) -> None:
        """One root authority: the provider's REPO_ROOT is this loader's workspace.

        canonical_target_owners normalizes against REPO_ROOT while this loader
        normalizes against its workspace; a split would misattribute producers.
        """
        root = getattr(module, "REPO_ROOT", None)
        if not isinstance(root, (str, os.PathLike)):
            raise SelectedExecutionError("canonical provider must declare its REPO_ROOT workspace")
        try:
            candidate = Path(root)
            if not candidate.is_absolute():
                raise SelectedExecutionError(
                    f"canonical provider REPO_ROOT must be absolute: {str(candidate)!r}"
                )
            resolved = candidate.resolve(strict=False)
        except (OSError, TypeError, ValueError) as error:
            raise SelectedExecutionError(
                f"cannot normalize canonical provider REPO_ROOT {root!r}: {error}"
            ) from error
        if resolved != self.workspace:
            raise SelectedExecutionError(
                f"canonical provider REPO_ROOT {str(resolved)!r} differs from "
                f"selected workspace {str(self.workspace)!r}"
            )

    def load_doit_config(self):
        with self._phase("dodo_import"):
            module = importlib.import_module("dodo")
        # Before its DOIT_CONFIG opens a dependency file, tasks or ownership.
        self._require_workspace_authority(module)
        # Match the ordinary loader before resolving relative recipe inputs.
        os.chdir(self.workspace)
        self.module = module
        return loader.load_doit_config(vars(self.module))

    def _validate_owners(self, tasks: list[Task]) -> None:
        paths = {
            path for task in tasks
            for collection in (task.targets, task.file_dep) for path in collection
        }
        try:
            owners = self.module.canonical_target_owners(paths)
        except (OSError, ValueError) as error:
            raise SelectedExecutionError(
                f"cannot construct canonical target ownership index: {error}"
            ) from error
        if not isinstance(owners, dict):
            raise SelectedExecutionError("canonical target ownership index must be a mapping")
        selected_targets: dict[str, str] = {}
        for task in tasks:
            for target in task.targets:
                path = _workspace_path(self.workspace, target)
                if path in selected_targets or owners.get(path) != task.name:
                    raise SelectedExecutionError(f"canonical target ownership differs for {path!r}")
                selected_targets[path] = task.name
        for task in tasks:
            for dependency in task.file_dep:
                path = _workspace_path(self.workspace, dependency)
                owner = owners.get(path)
                if owner is not None and (
                    owner not in self.names or selected_targets.get(path) != owner
                ):
                    raise SelectedExecutionError(
                        f"task {task.name!r} omits implicit producer {owner!r} for {path!r}"
                    )

    def _instrument(self, task: Task) -> None:
        if not task.actions:
            return
        execute = task.execute

        @functools.wraps(execute)
        def measured_execute(stream):
            if not self.first_action:
                self.first_action = True
                self._marker("first_action", task=task.name, selected_root=task.name == self.task_name)
            if task.name == self.task_name:
                self._marker("selected_action", task=task.name, dependency_restore_in_head=True)
            return execute(stream)

        task.execute = measured_execute

    def load_tasks(self, cmd, pos_args):
        try:
            if cmd.get_name() != "run" or pos_args != [self.task_name]:
                raise SelectedExecutionError("internal loader requires exactly the selected run task")
            with self._phase("task_construction"):
                tasks = self.module.canonical_tasks(sorted(self.names))
                if not isinstance(tasks, list) or not all(isinstance(task, Task) for task in tasks):
                    raise SelectedExecutionError("canonical factories must return genuine doit Tasks")
                names = [task.name for task in tasks]
                if len(names) != len(set(names)) or set(names) != self.names:
                    raise SelectedExecutionError("canonical factory closure differs from the selected graph")
                # Match NamespaceTaskLoader's configuration and API option handling.
                for task in tasks:
                    stanza = "task:" + task.name
                    if self.config is not None and stanza in self.config:
                        task.cfg_values = self.config[stanza]
                    if self.task_opts is not None and task.name in self.task_opts:
                        task.cfg_values = self.task_opts[task.name]
                        if task.pos_arg and task.pos_arg in task.cfg_values:
                            task.pos_arg_val = task.cfg_values[task.pos_arg]
            with self._phase("ownership_index"):
                self._validate_owners(tasks)
            with self._phase("control_validation"):
                control = TaskControl(self.isolate_tasks(tasks))
                control.process([self.task_name])
                for task in control.tasks.values():
                    expected = dict(self.records[task.name])
                    expected["actions"] = [action["callable"] for action in expected["actions"]]
                    actual = task_record(self.workspace, task)
                    if actual != expected:
                        differing = sorted(key for key in expected if expected[key] != actual[key])
                        raise SelectedExecutionError(
                            f"canonical task {task.name!r} differs from trusted graph: {', '.join(differing)}"
                        )
            for task in tasks:
                self._instrument(task)
            return tasks
        except BaseException:
            if getattr(cmd, "dep_manager", None) is not None:
                cmd.dep_manager.close()
            raise
