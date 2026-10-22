"""Offline base/head *source impact*, not observed cache misses or rebuilds.

Uses each revision's dodo dependency builders and ContentChecker in a fresh
process. No recipe module, native output, task action, cache service or COM seat
is loaded. Revision Python is executable code: use a disposable sandbox for
untrusted revisions (the PR workflow supplies a networkless container).

uv run --no-sync python cache_impact.py --base <sha> --head <sha> \
    --json impact.json --markdown impact.md

Pass --merge-base for PR semantics; the report records the requested base,
resolved comparison base and exact head separately. Exact SHA comparison is
the default. Missing required inputs produce evidence plus exit status 3.
Optional duration evidence is JSON: {"source": "run/artifact identifier",
"durations_seconds": {"part:example": 12.5}}. Values must be measured per-task
work durations, not guesses. Their covered sum is not elapsed build time.
"""

from __future__ import annotations

import argparse
from collections import deque
import html
import importlib.abc
import importlib.util
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile


class ImpactError(RuntimeError):
    """Discovery/materialization failed; this is not a zero-impact result."""


def _git_environment() -> dict[str, str]:
    keys = ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG",
            "TMP", "TEMP", "TMPDIR")
    env = {key: os.environ[key] for key in keys if key in os.environ}
    # Checkout must not execute a developer's global filters/hooks, prompt for
    # credentials, or inherit a GIT_DIR/GIT_WORK_TREE redirect from its caller.
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})
    return env


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False,
        env=_git_environment(),
    )
    if result.returncode:
        raise ImpactError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def resolve_commit(repo: Path, revision: str) -> str:
    # Full object IDs only: never a mutable ref or the PR synthetic merge commit.
    if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", revision):
        raise ImpactError("base/head must be full commit SHAs, not branch names")
    return _git(repo, "rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip()


def _entries(repo: Path, sha: str) -> list[tuple[str, str, str]]:
    rows = []
    for row in _git(repo, "ls-tree", "-r", "-z", sha).split(b"\0"):
        if row:
            metadata, path = row.split(b"\t", 1)
            mode, _kind, oid = metadata.decode("ascii").split()
            rows.append((mode, oid, path.decode("utf-8")))
    return rows


def _safe_path(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or "\\" in name
        or ":" in name
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
        or any(part.lower() == ".git" for part in relative.parts)
    ):
        raise ImpactError(f"unsafe tracked path: {name!r}")
    return root.joinpath(*relative.parts)


def materialize(repo: Path, sha: str, root: Path, metadata: Path | None = None) -> dict:
    """Detached worktree in an owned scratch clone; original Git state is read-only.

    Sharing the object store avoids copying repository history. All indexes,
    worktree registrations, hooks configuration and sidecars belong to scratch.
    No submodule URLs from PR-controlled .gitmodules are followed.
    """
    entries = _entries(repo, sha)
    for mode, _oid, name in entries:
        _safe_path(root, name)
        if mode not in {"100644", "100755", "120000", "160000"}:
            raise ImpactError(f"unsupported tracked mode {mode}: {name}")
    root.parent.mkdir(parents=True, exist_ok=True)
    metadata = metadata or root.parent / f".{root.name}-metadata"
    metadata.mkdir(parents=True)
    store = metadata / "repository.git"
    hooks = metadata / "empty-hooks"
    hooks.mkdir()
    result = subprocess.run(
        ["git", "-c", f"core.hooksPath={hooks}", "-c", "core.longpaths=true",
         "clone", "--bare", "--shared", str(repo), str(store)], capture_output=True,
        env=_git_environment(),
    )
    if result.returncode:
        raise ImpactError(result.stderr.decode("utf-8", errors="replace"))
    _git(store, "-c", f"core.hooksPath={hooks}", "-c", "core.autocrlf=false",
         "-c", "core.symlinks=false", "-c", "core.longpaths=true",
         "worktree", "add", "--detach", str(root), sha)
    if _git(root, "rev-parse", "HEAD").decode().strip() != sha:
        raise ImpactError("isolated worktree did not resolve to requested SHA")
    gitlinks = {}
    symlinks = [name for mode, _oid, name in entries if mode == "120000"]
    for mode, oid, name in entries:
        if mode != "160000":
            continue
        available = False
        # Never initialize the large/private references submodule. If any actual
        # recipe reads an absent file, that input is explicitly unavailable.
        if name == "SolidworksMCP-python" and (repo / name / ".git").exists():
            try:
                resolve_commit(repo / name, oid)
            except ImpactError:
                pass
            else:
                # Git creates an empty gitlink directory in a worktree. A nested
                # detached worktree has its own exact index and HEAD, too.
                (root / name).rmdir()
                nested = materialize(repo / name, oid, root / name, metadata / "adapter")
                symlinks.extend(f"{name}/{path}" for path in nested["symlinks"])
                available = True
        gitlinks[name] = {"sha": oid, "available": available}
    return {"gitlinks": gitlinks, "symlinks": sorted(symlinks)}


class _NoRecipes(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        leaf = fullname.rsplit(".", 1)[-1]
        if (
            leaf.startswith(("build_", "draw_"))
            or fullname.split(".", 1)[0]
            in {"solidworks_mcp", "pythoncom", "win32com", "comtypes"}
        ):
            raise ImpactError(f"offline discovery attempted recipe/COM import: {fullname}")
        return None


def _restrict_worker_writes(state: Path, output: Path) -> None:
    """Accidental-side-effect guard, NOT a sandbox for hostile Python."""
    def check(event, args):
        paths = ()
        if event == "open":
            path, mode, flags = args
            if isinstance(path, (str, bytes, os.PathLike)) and (
                (mode is not None and any(c in mode for c in "wax+"))
                or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            ):
                paths = (path,)
        elif event == "os.chmod" and isinstance(args[0], int):
            # fchmod reports its existing descriptor here, not a filesystem path.
            return
        elif event in {"os.mkdir", "os.remove", "os.rmdir", "os.chmod"}:
            paths = args[:1]
        elif event in {"os.rename", "os.link", "os.symlink"}:
            paths = args[:2]
        elif event in {
            "subprocess.Popen", "os.system", "os.exec", "os.spawn",
            "os.posix_spawn", "os.startfile", "os.startfile/2",
            "_winapi.CreateProcess", "socket.connect", "socket.bind",
        }:
            raise ImpactError(f"offline discovery attempted host/network action: {event}")
        for path in paths:
            resolved = Path(os.fsdecode(path)).resolve()
            if not (resolved.is_relative_to(state) or resolved.is_relative_to(output)):
                raise ImpactError(f"discovery write outside isolated state/output: {path}")
    sys.addaudithook(check)


def _recipe_digest(dodo, label, dependencies):
    """Revision-local provenance instrumentation; never compute review PDF keys.

    The production review helper owns its frozen-profile digest closure. Capture
    that exact callback only for this invocation, then restore the key function.
    Historical revisions need no new reporting-specific production API.
    """
    provenance = {"method": "ContentChecker._digest"}
    if not label.startswith("check:machinist_review:"):
        return dodo.ContentChecker._digest, provenance
    profile = dodo._machinist_review_profile()
    captures = []
    original = dodo._cache.cache_key

    def capture(file_deps, digest_one, label=None):
        captures.append((list(file_deps), digest_one, label))
        # The helper's return value is deliberately unused: unavailable PDF bytes
        # prohibit a full-key claim. Only its production digest callback is used.
        return None

    try:
        dodo._cache.cache_key = capture
        dodo._machinist_review_cache_key(label.removeprefix("check:machinist_review:"), profile, label)
    finally:
        dodo._cache.cache_key = original
    if len(captures) != 1 or captures[0][0] != list(dependencies) or captures[0][2] != label:
        raise ImpactError(f"production review digest/input contract changed: {label}")
    provenance = {
        "method": "_machinist_review_cache_key contextual callback",
        "profile": dict(profile._asdict()),
        "instrumentation": "revision-local callback capture; no full key computed",
    }
    return captures[0][1], provenance


def snapshot(root: Path, state: Path, gitlinks: dict, symlinks: list[str] = ()) -> dict:
    """Called only in a disposable per-revision process; no task actions run."""
    root, state = root.resolve(), state.resolve()
    state.mkdir(parents=True, exist_ok=True)
    sys.dont_write_bytecode = True
    sys.meta_path.insert(0, _NoRecipes())
    output = root / "cad" / "out"
    _restrict_worker_writes(state, output)
    sys.path.insert(0, str(root / "cad" / "scripts"))
    spec = importlib.util.spec_from_file_location("dodo", root / "dodo.py")
    if spec is None or spec.loader is None:
        raise ImpactError("revision has no loadable dodo.py")
    dodo = importlib.util.module_from_spec(spec)
    sys.modules["dodo"] = dodo
    spec.loader.exec_module(dodo)
    bg = sys.modules["_buildgraph"]
    if dodo.CAD_OUT.resolve() != output:
        raise ImpactError("revision uses an unexpected native output root")

    def tag(path):
        path = Path(path).resolve()
        # Keep actual production repo-relative tags, including generated sidecars.
        if not path.is_relative_to(root):
            raise ImpactError(f"recipe input outside revision tree: {path}")
        name = path.relative_to(root).as_posix()
        if name in symlinks:
            raise ImpactError(f"symlink recipe input cannot be evaluated conservatively: {name}")
        return name

    parts = {stem: bg.script_for(stem) for stem in bg.part_stems()}
    native = {}
    for kind, stems in (("part", parts), ("assembly", dodo.ASSEMBLY_ORDER)):
        for stem in stems:
            label = f"{kind}:{stem}"
            target = dodo._sldprt(stem) if kind == "part" else dodo._sldasm(stem)
            token = dodo._part_execution_token(stem) if kind == "part" else dodo._assembly_execution_token(stem)
            native[str(Path(target).resolve())] = (label, "recipe")
            native[str(Path(token).resolve())] = (label, "execution")
    scripts = {f"part:{stem}": script for stem, script in parts.items()}
    scripts.update({f"assembly:{stem}": bg.script_for(stem) for stem in dodo.ASSEMBLY_ORDER})
    scripts.update({f"drawing:{stem}": drawing.script for stem, drawing in dodo.DRAWINGS_BY_NAME.items()})
    # This production inventory is also used by its cache diagnostics. Do not
    # load task generators, actions, freshness checks or cache/backend probes.
    definitions = [(label, scripts.get(label), deps) for label, deps in dodo._cache_rows()]
    if len({label for label, _, _ in definitions}) != len(definitions):
        raise ImpactError("production cache inventory contains duplicate task labels")

    outputs = {}
    for label, _script, _deps in definitions:
        stem = label.rsplit(":", 1)[-1]
        if label.startswith("part:"):
            produced = dodo._part_cache_outputs(stem)
        elif label.startswith("assembly:"):
            produced = dodo._assembly_cache_outputs(stem)
        elif label.startswith("drawing:"):
            produced = dodo._drawing_cache_outputs(stem)
        elif label.startswith("package:features:"):
            produced = dodo._feature_export_outputs(stem)
        else:
            produced = ()
        for produced_path in produced:
            path = Path(produced_path).resolve()
            tag(path)
            if path in outputs and outputs[path] != label:
                raise ImpactError(f"ambiguous generated-output producer: {tag(path)}")
            outputs[path] = label
    output_roots = sorted(outputs, key=lambda path: (-len(path.parts), str(path)))

    def generated_producer(path):
        return next((outputs[parent] for parent in output_roots if path.is_relative_to(parent)), None)

    # Use the same direct import resolver as production, not a parallel AST engine.
    modules = bg._local_modules()
    edges = {}
    paths = {Path(path).resolve() for _, script, deps in definitions for path in [*([script] if script else []), *deps] if str(path).endswith(".py")}
    for path in sorted(paths):
        if path.is_file():
            edges[tag(path)] = sorted(tag(modules[name]) for name in bg._direct_local_imports(path))

    adapter = "SolidworksMCP-python"
    for name in symlinks:
        if name.startswith(adapter + "/src/solidworks_mcp/"):
            raise ImpactError(f"symlink recipe input cannot be evaluated conservatively: {name}")
    adapter_available = bool(gitlinks.get(adapter, {}).get("available")) and bool(dodo._submodule_src_files())
    tasks = {}
    for label, script, deps in definitions:
        inputs, recipe_inputs, execution_inputs, generated_inputs, unavailable = {}, {}, {}, {}, []
        digest, digest_provenance = _recipe_digest(dodo, label, deps)
        uses_adapter = False
        for dependency in sorted(set(deps)):
            path = Path(dependency).resolve()
            native_input = native.get(str(path))
            if native_input:
                producer, kind = native_input
                name = tag(path)
                if kind == "execution":
                    execution_inputs[name] = producer
                else:
                    # A declared target's ContentChecker branch hashes only its
                    # producing recipe, recursively. Never fall back to CAD bytes.
                    if dodo._stable_artefact_digest(str(path)) is None:
                        raise ImpactError(f"native target lacks a pure recipe digest: {name}")
                    recipe_inputs[name] = {
                        "producer": producer,
                        "digest": dodo.ContentChecker._digest(str(path)),
                        "available": True,
                    }
                continue
            name = tag(path)
            origins = [name]
            if path.is_relative_to(output):
                if ".solidworks-mcp-submodule" in path.name:
                    origins = [adapter]
                elif path.parent.name == ".drawing-registry":
                    origins = ["cad/scripts/_drawing_registry.py"]
                elif path.parent.name == ".fastener-catalog":
                    origins = ["cad/scripts/_fastener_catalog.py"]
                else:
                    producer = generated_producer(path)
                    if producer is None and path.suffix == ".digest":
                        raise ImpactError(f"unclassified generated recipe input: {name}")
                    generated_inputs[name] = {
                        "producer": producer, "digest": None, "available": False,
                        "reason": "generated byte identity is not evaluable from source",
                    }
                    continue
            uses_adapter = uses_adapter or adapter in origins
            exists = path.is_file()
            inputs[name] = {
                "digest": digest(str(path)) if exists else None,
                "origins": origins,
                "available": exists,
            }
            if not exists:
                unavailable.append(name)
        # Do not let production's empty-tree adapter fallback become a false
        # unchanged/complete result. An unavailable pin is a conservative input,
        # explicitly distinguished from actual production digest evidence.
        if uses_adapter and not adapter_available:
            pin = gitlinks.get(adapter, {}).get("sha")
            inputs["unavailable-gitlink:" + adapter] = {
                "digest": pin, "origins": [adapter], "available": False,
            }
            unavailable.append(adapter)
        part_key = None
        if label.startswith("part:") and not unavailable:
            part_key = dodo._cache_key(deps)
        tasks[label] = {
            "script": tag(script) if script else None, "inputs": dict(sorted(inputs.items())),
            "native_recipe_inputs": dict(sorted(recipe_inputs.items())),
            "execution_identity_inputs": dict(sorted(execution_inputs.items())),
            "generated_content_inputs": dict(sorted(generated_inputs.items())),
            "digest_provenance": digest_provenance,
            "unavailable_inputs": sorted(unavailable),
            "production_part_cache_key": part_key,
        }
    available = {}

    def resolve_availability(label, visiting):
        if label in available:
            return available[label]
        if label in visiting or label not in tasks:
            raise ImpactError(f"invalid native recipe dependency: {label}")
        task = tasks[label]
        missing = set(task["unavailable_inputs"])
        for info in task["native_recipe_inputs"].values():
            if not resolve_availability(info["producer"], visiting | {label}):
                info["available"] = False
                info["digest"] = None
                missing.add("native-recipe:" + info["producer"])
        task["unavailable_inputs"] = sorted(missing)
        if missing:
            task["production_part_cache_key"] = None
        available[label] = not missing
        return available[label]

    for label in tasks:
        resolve_availability(label, set())
    return {
        "tasks": dict(sorted(tasks.items())), "import_edges": edges, "gitlinks": gitlinks,
        "inventory": [label for label, _, _ in definitions],
        "conditional_auxiliary_keys": [
            {"label": f"assembly:{stem} explode-base", "producer": f"assembly:{stem}",
             "status": "not_evaluated_action_time",
             "reason": "conditional explode-base alias is selected inside the native assembly action"}
            for stem in dodo.ASSEMBLY_ORDER
        ],
        "cache_context": {"epoch": dodo._cache._CACHE_EPOCH, "salt": dodo._cache._salt()},
        "runtime": {"python": sys.version.split()[0], "packages": {
            name: importlib.metadata.version(name)
            for name in ("doit", "filelock", "pyyaml", "opentelemetry-api", "opentelemetry-sdk")
        }},
    }


def _worker_environment(state: Path) -> dict[str, str]:
    # Never inherit Azure credentials, OTLP endpoints, cache roles or farm flags.
    keys = ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG")
    env = {key: os.environ[key] for key in keys if key in os.environ}
    env.update({
        "HOME": str(state), "USERPROFILE": str(state),
        "TMP": str(state), "TEMP": str(state), "TMPDIR": str(state),
        "PYTHONDONTWRITEBYTECODE": "1",
        "HARMONIC_BUILDGRAPH_CACHE": "off", "HARMONIC_REMOTE_CACHE_MODE": "off",
        "HARMONIC_EXECUTOR": "local", "HARMONIC_SW_AUTOSTART": "0",
        "HARMONIC_COM_LOCK": str(state / "com-seat.lock"),
        "OTEL_SDK_DISABLED": "true", "OTEL_TRACES_EXPORTER": "none",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "",
        "OTEL_METRICS_EXPORTER": "none", "OTEL_LOGS_EXPORTER": "none",
    })
    return env


def analyze_tree(root: Path, state: Path, gitlinks: dict, timeout: int = 300, symlinks: list[str] = ()) -> dict:
    state.mkdir(parents=True)
    manifest = state / "gitlinks.json"
    manifest.write_text(json.dumps({"gitlinks": gitlinks, "symlinks": symlinks}), encoding="utf-8")
    result_path = state / "snapshot.json"
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-X", "utf8", str(Path(__file__).resolve()), "--worker", str(root),
         str(state), str(manifest), str(result_path)],
        cwd=state, env=_worker_environment(state), capture_output=True, timeout=timeout,
    )
    if result.returncode:
        # Keep machine-independent diagnostics: no scratch path in the report.
        detail = result.stderr.decode("utf-8", errors="replace").replace(str(root), "<revision>").replace(str(state), "<state>")
        raise ImpactError(f"revision discovery failed:\n{detail.strip()}")
    return json.loads(result_path.read_text(encoding="utf-8"))


def _import_path(snapshot_data: dict, script: str | None, destination: str) -> list[str] | None:
    if script is None:
        return None
    queue = deque([[script]])
    visited = {script}
    while queue:
        path = queue.popleft()
        if path[-1] == destination:
            return path
        for child in snapshot_data["import_edges"].get(path[-1], []):
            if child not in visited:
                visited.add(child)
                queue.append([*path, child])
    return None


def _native_paths(base: dict, head: dict, seeds: set[str], kind: str) -> dict[str, list[str]]:
    """Shortest causal paths over the union of the two actual dependency DAGs."""
    dependents = {}
    for data in (base, head):
        for label, task in data["tasks"].items():
            producers = set()
            if kind in {"recipe", "potential"}:
                producers.update(info["producer"] for info in task["native_recipe_inputs"].values())
            if kind in {"execution", "potential"}:
                producers.update(task["execution_identity_inputs"].values())
            if kind in {"generated", "potential"}:
                producers.update(info["producer"] for info in task["generated_content_inputs"].values() if info["producer"])
            for producer in producers:
                dependents.setdefault(producer, set()).add(label)
    routes = {seed: [seed] for seed in sorted(seeds)}
    downstream = {}
    queue = deque(sorted(seeds))
    while queue:
        source = queue.popleft()
        for dependent in sorted(dependents.get(source, ())):
            path = [*routes[source], dependent]
            # A task can be both a direct seed and downstream of another seed.
            # Preserve that orthogonal causal evidence instead of hiding overlap.
            downstream.setdefault(dependent, path)
            if dependent not in routes:
                routes[dependent] = path
                queue.append(dependent)
    return downstream


def compare(base: dict, head: dict, base_sha: str, head_sha: str, durations: dict | None = None) -> dict:
    old, new = base["tasks"], head["tasks"]
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    gitlink_changes = [
        {"input": name, "base": base["gitlinks"].get(name), "head": head["gitlinks"].get(name)}
        for name in sorted(base["gitlinks"].keys() | head["gitlinks"].keys())
        if base["gitlinks"].get(name) != head["gitlinks"].get(name)
    ]
    context_changes = [
        {"input": name, "base": base["cache_context"][name], "head": head["cache_context"][name]}
        for name in sorted(base["cache_context"])
        if base["cache_context"][name] != head["cache_context"][name]
    ]
    direct, transitive, execution_edges, generated_edges = [], [], [], []
    for label in sorted(old.keys() & new.keys()):
        before, after = old[label], new[label]
        changes = []
        for name in sorted(before["inputs"].keys() | after["inputs"].keys()):
            left, right = before["inputs"].get(name), after["inputs"].get(name)
            if left == right:
                continue
            causes = []
            for revision, data, task, info in (("base", base, before, left), ("head", head, after, right)):
                if info is None:
                    continue
                for origin in info["origins"]:
                    path = _import_path(data, task["script"], origin)
                    causes.append({
                        "revision": revision, "input": origin,
                        "kind": "module_import" if path else "declared_recipe_input",
                        "path": [label, *(path or ([task["script"], origin] if task["script"] else [origin]))],
                    })
            changes.append({"input": name, "base": left, "head": right, "causes": causes})
        if changes:
            direct.append({"task": label, "changed_inputs": changes})
        if label.startswith("part:"):
            left_key, right_key = before["production_part_cache_key"], after["production_part_cache_key"]
            if left_key is not None and right_key is not None:
                if (left_key != right_key) != bool(changes or context_changes):
                    raise ImpactError(f"production part-key/input parity mismatch: {label}")
        native_changes = []
        for name in sorted(before["native_recipe_inputs"].keys() | after["native_recipe_inputs"].keys()):
            left = before["native_recipe_inputs"].get(name)
            right = after["native_recipe_inputs"].get(name)
            if left == right:
                continue
            # Missing source is unknown, not a confident <missing>-hash equality
            # or a deterministic native recipe identity change.
            if (left and not left["available"]) or (right and not right["available"]):
                continue
            native_changes.append({"input": name, "base": left, "head": right})
        if native_changes:
            transitive.append({"task": label, "changed_inputs": native_changes})
        if before["execution_identity_inputs"] != after["execution_identity_inputs"]:
            execution_edges.append({
                "task": label, "base": before["execution_identity_inputs"],
                "head": after["execution_identity_inputs"],
            })
        if before["generated_content_inputs"] != after["generated_content_inputs"]:
            generated_edges.append({
                "task": label, "base": before["generated_content_inputs"],
                "head": after["generated_content_inputs"],
            })

    direct_labels = {entry["task"] for entry in direct}
    transitive_labels = {entry["task"] for entry in transitive}
    source_seeds = set(added) | set(removed) | direct_labels
    if context_changes:
        source_seeds.update(old.keys() | new.keys())
    recipe_paths = _native_paths(base, head, source_seeds, "recipe")
    for entry in transitive:
        first = entry["changed_inputs"][0]
        producer = (first["head"] or first["base"])["producer"]
        entry["path"] = recipe_paths.get(entry["task"], [producer, entry["task"]])

    execution_edge_labels = {entry["task"] for entry in execution_edges}
    generated_edge_labels = {entry["task"] for entry in generated_edges}
    potential_seeds = source_seeds | execution_edge_labels | generated_edge_labels
    # Mixed paths retain the source-rooted cause across recipe, token and byte
    # edges. Classify the terminal edge separately; do not claim byte equality.
    mixed_paths = _native_paths(base, head, potential_seeds, "potential")
    reachable = potential_seeds | transitive_labels | mixed_paths.keys()
    potential_paths = _native_paths(base, head, reachable, "execution")
    generated_paths = _native_paths(base, head, reachable, "generated")
    for label in sorted(execution_edge_labels):
        potential_paths.setdefault(label, [label])
    for label in sorted(generated_edge_labels):
        generated_paths.setdefault(label, [label])
    potential = [
        {
            "task": label, "path": mixed_paths.get(label, path),
            "also_recipe_affected": label in source_seeds or label in transitive_labels,
            "execution_dependency_changed": label in execution_edge_labels,
        }
        for label, path in sorted(potential_paths.items())
    ]
    generated_potential = [
        {"task": label, "path": mixed_paths.get(label, path),
         "also_recipe_affected": label in source_seeds or label in transitive_labels}
        for label, path in sorted(generated_paths.items())
    ]
    offline_unknown = {
        label: {
            revision: {
                "execution_tokens": data["tasks"][label]["execution_identity_inputs"],
                "generated_content": data["tasks"][label]["generated_content_inputs"],
            }
            for revision, data in (("base", base), ("head", head))
            if label in data["tasks"] and (
                data["tasks"][label]["execution_identity_inputs"]
                or data["tasks"][label]["generated_content_inputs"]
            )
        }
        for label in sorted(old.keys() | new.keys())
    }
    offline_unknown = {label: evidence for label, evidence in offline_unknown.items() if evidence}
    uncertain = {
        label: {revision: data["tasks"][label]["unavailable_inputs"]
                for revision, data in (("base", base), ("head", head))
                if label in data["tasks"] and data["tasks"][label]["unavailable_inputs"]}
        for label in sorted(old.keys() | new.keys())
    }
    uncertain = {label: evidence for label, evidence in uncertain.items() if evidence}
    uncertain_head = set(uncertain) & new.keys()
    affected = sorted((source_seeds | transitive_labels | potential_paths.keys() | generated_paths.keys() | uncertain_head) & new.keys())
    direct_work = (source_seeds & new.keys()) - uncertain_head
    transitive_work = (transitive_labels & new.keys()) - direct_work - uncertain_head
    execution_work = (potential_paths.keys() & new.keys()) - direct_work - transitive_work - uncertain_head
    generated_work = (generated_paths.keys() & new.keys()) - direct_work - transitive_work - execution_work - uncertain_head
    cost = {
        "available": False, "reason": "No measured duration evidence supplied.",
        "covered_tasks": 0, "affected_head_tasks": len(affected),
        "uncertain_head_tasks": len(uncertain_head),
        "offline_unknown_head_tasks": len(set(offline_unknown) & new.keys()),
    }
    if durations is not None:
        if not isinstance(durations, dict):
            raise ImpactError("duration evidence must be an object")
        source, samples = durations.get("source"), durations.get("durations_seconds")
        if not isinstance(source, str) or not source.strip() or not isinstance(samples, dict):
            raise ImpactError("duration evidence needs source and durations_seconds mapping")
        for label, seconds in samples.items():
            if not isinstance(label, str) or isinstance(seconds, bool) or not isinstance(seconds, (float, int)) or not math.isfinite(seconds) or seconds < 0:
                raise ImpactError(f"invalid measured duration for {label!r}")
        covered = sorted(set(affected) & samples.keys())
        cost.update({
            "available": bool(covered), "evidence_source": source,
            "covered_tasks": len(covered), "coverage": covered,
            "missing_tasks": sorted(set(affected) - samples.keys()),
            "covered_work_seconds": sum(samples[label] for label in covered),
            "reason": (
                "Sum of supplied measured task work; not elapsed time or predicted cache misses."
                if covered else "No supplied measured durations cover affected or uncertain head tasks."
            ),
        })
        # These timing groups are disjoint even though source-recipe and token
        # potential evidence can overlap for the same native consumer.
        for category, targets in (
            ("direct_work", direct_work), ("transitive_recipe_only_work", transitive_work),
            ("execution_potential_only_work", execution_work), ("uncertain_work", uncertain_head),
            ("generated_potential_only_work", generated_work),
        ):
            measured = sorted(targets & samples.keys())
            cost[category] = {
                "covered_tasks": len(measured), "affected_tasks": len(targets),
                "covered_work_seconds": sum(samples[label] for label in measured),
                "missing_tasks": sorted(targets - samples.keys()),
            }
    return {
        "schema_version": 1, "kind": "source_impact", "base_sha": base_sha, "head_sha": head_sha,
        "scope": "all leaves in each revision's production dodo._cache_rows() inventory",
        "notice": "Source impact only: not observed cache misses, rebuilds, execution-identity changes, or geometry/sheet changes.",
        "added_tasks": added, "removed_tasks": removed, "direct_recipe_changes": direct,
        "transitive_recipe_changes": transitive,
        "potential_execution_identity_dependents": potential,
        "execution_dependency_changes": execution_edges,
        "potential_generated_content_dependents": generated_potential,
        "generated_content_dependency_changes": generated_edges,
        "offline_unknown_inputs": offline_unknown,
        "unavailable_inputs": uncertain,
        "changed_gitlinks": gitlink_changes, "global_cache_context_changes": context_changes,
        "global_cache_context_affected_tasks": sorted(old.keys() | new.keys()) if context_changes else [],
        "complete": not uncertain, "cost_estimate": cost,
        "counts": {
            "added": len(added), "removed": len(removed), "direct": len(direct),
            "transitive_recipe": len(transitive), "execution_potential": len(potential),
            "generated_potential": len(generated_potential), "uncertain": len(uncertain),
        },
        "revisions": {"base": base, "head": head},
        "limitations": [
            "All production _cache_rows leaves are enumerated; conditional action-time assembly explode-base aliases are listed separately but not evaluated.",
            "Declared native target inputs use production pure recipe digests, recursively, without reading native CAD bytes.",
            "Execution tokens are not read: their dependent leaves express potential exact-identity propagation, not observed changes.",
            "Generated PDF, SLDDRW, feature bundle and DOF/sweep byte identities remain explicit offline unknowns, with production output-producer links when available.",
            "Expected absent generated/native bytes do not make source enumeration incomplete; missing tracked/config/adapter source inputs do.",
            "Recipe effects, execution-identity potential and generated-content potential can overlap; measured-duration buckets are disjoint.",
            "Machinist review source digests use the actual production frozen-profile callback captured in the isolated revision worker.",
            "Unavailable inputs and their recipe dependents remain unknown even when recorded pins match.",
            "Declared recipe input paths are not inferred Python import chains; only module_import causes are actual import paths.",
            "Part cache keys use production default salt; complete part input/context deltas are checked against actual key deltas.",
            "Gitlink changes are reported even when production tier projections retain identical recipe digests.",
            "Both revisions use the invoking interpreter and installed graph dependencies (versions recorded); incompatible revisions fail discovery.",
            "Durations are historical measured work, not predicted assembly tiers, rebuild costs, or elapsed time.",
        ],
    }


def _markdown_safe(value):
    if isinstance(value, str):
        return html.escape(value, quote=False).replace("`", "&#96;").replace("\r", "&#13;").replace("\n", "&#10;")
    if isinstance(value, list):
        return [_markdown_safe(item) for item in value]
    if isinstance(value, dict):
        return {_markdown_safe(key): _markdown_safe(item) for key, item in value.items()}
    return value


def markdown(report: dict) -> str:
    report = _markdown_safe(report)
    if "error" in report:
        return "# Cache source impact — tool error\n\nNo impact conclusion is available.\n\n```text\n" + report["error"].replace("```", "'''") + "\n```\n"
    lines = ["# Cache source impact", "", report["notice"], "",
             f"Base: `{report['base_sha']}`  ", f"Head: `{report['head_sha']}`", "",
             "| Added | Removed | Direct recipes | Transitive recipes | Execution potential | Generated potential | Uncertain |",
             "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
             "| " + " | ".join(str(report["counts"][key]) for key in ("added", "removed", "direct", "transitive_recipe", "execution_potential", "generated_potential", "uncertain")) + " |", ""]
    if "requested_base_sha" in report:
        lines.extend([f"Requested base: `{report['requested_base_sha']}`; comparison mode: `{report['comparison_mode']}`.", ""])
    lines.extend([
        f"Production `_cache_rows()` inventory: **{len(report['revisions']['base']['tasks'])} base / {len(report['revisions']['head']['tasks'])} head leaves**, including review, verification, export and packaging.",
        "Conditional assembly explode-base aliases are recorded in the JSON revision evidence; their action-time keys are not evaluated.",
        "",
    ])
    lines.extend(["## Global cache context and gitlinks", ""])
    for change in report["global_cache_context_changes"]:
        lines.append(f"- Global `{change['input']}`: `{change['base']}` → `{change['head']}` (all reported leaves).")
    for change in report["changed_gitlinks"]:
        left = change["base"]["sha"] if change["base"] else "absent"
        right = change["head"]["sha"] if change["head"] else "absent"
        lines.append(f"- Gitlink `{change['input']}`: `{left}` → `{right}`.")
    lines.append("")
    for title, values in (("Added tasks", report["added_tasks"]), ("Removed tasks", report["removed_tasks"])):
        lines.extend([f"## {title}", "", *(f"- `{value}`" for value in values), "" if values else "None.\n"])
    lines.extend(["## Direct recipe inputs", ""])
    for entry in report["direct_recipe_changes"]:
        lines.append(f"- **`{entry['task']}`**")
        for change in entry["changed_inputs"]:
            lines.append(f"  - `{change['input']}`")
            for cause in change["causes"]:
                lines.append(f"    - {cause['revision']} / {cause['kind']}: " + " → ".join(f"`{part}`" for part in cause["path"]))
    lines.extend(["", "## Deterministic transitive recipe changes (no native bytes read)", ""])
    for entry in report["transitive_recipe_changes"]:
        lines.append("- " + " → ".join(f"`{part}`" for part in entry["path"]))
        for change in entry["changed_inputs"]:
            lines.append(f"  - Pure recipe input `{change['input']}`")
    lines.extend(["", "## Potential execution-identity dependents (tokens not observed)", "",
                  "This orthogonal category can overlap direct and transitive recipe effects.", ""])
    for entry in report["potential_execution_identity_dependents"]:
        suffix = " (also recipe-affected)" if entry["also_recipe_affected"] else ""
        lines.append("- " + " → ".join(f"`{part}`" for part in entry["path"]) + suffix)
    for entry in report["execution_dependency_changes"]:
        lines.append(f"- Execution-token dependency set changed for `{entry['task']}`.")
    lines.extend(["", "## Potential generated-content dependents (bytes not observed)", "",
                  "Producer links come from production output metadata. These are not deterministic native recipe changes.", ""])
    for entry in report["potential_generated_content_dependents"]:
        suffix = " (also recipe-affected)" if entry["also_recipe_affected"] else ""
        lines.append("- " + " → ".join(f"`{part}`" for part in entry["path"]) + suffix)
    for entry in report["generated_content_dependency_changes"]:
        lines.append(f"- Generated-content dependency set changed for `{entry['task']}`.")
    lines.extend(["", "## Expected offline-unknown identities", "",
                  "These expected native/generated inputs are not missing tracked source and do not by themselves make the source report incomplete.", ""])
    for label, revisions in report["offline_unknown_inputs"].items():
        lines.append(f"- `{label}`")
        for revision, evidence in revisions.items():
            for name, producer in evidence["execution_tokens"].items():
                lines.append(f"  - {revision}: execution token `{name}` ← `{producer}` (not observed)")
            for name, info in evidence["generated_content"].items():
                lines.append(f"  - {revision}: generated bytes `{name}` ← `{info['producer'] or 'unknown producer'}` (not evaluable offline)")
    lines.extend(["", "## Unavailable inputs", ""])
    if not report["unavailable_inputs"]:
        lines.append("None.")
    for label, evidence in report["unavailable_inputs"].items():
        lines.append(f"- `{label}`: " + "; ".join(f"{revision}: " + ", ".join(f"`{item}`" for item in inputs) for revision, inputs in evidence.items()))
    cost = report["cost_estimate"]
    lines.extend(["", "## Cost estimate", ""])
    if cost["available"]:
        lines.append(f"Measured duration evidence: `{cost['evidence_source']}`. No missing durations are extrapolated.")
        for key, title in (
            ("direct_work", "Direct/source-context work"),
            ("transitive_recipe_only_work", "Transitive recipe-only work"),
            ("execution_potential_only_work", "Execution potential-only work"),
            ("generated_potential_only_work", "Generated-content potential-only work"),
            ("uncertain_work", "Unavailable-input/uncertain work"),
        ):
            group = cost[key]
            lines.append(f"- {title}: **{group['covered_work_seconds']:.3f} s** measured; coverage **{group['covered_tasks']}/{group['affected_tasks']}** tasks.")
    else:
        lines.append("Unavailable. " + cost["reason"])
    lines.append(f"Unavailable-input uncertainty covers {cost['uncertain_head_tasks']} head tasks; it is not silently excluded.")
    lines.append(f"Expected offline-unknown identities occur in {cost['offline_unknown_head_tasks']} head tasks; only source-affected/uncertain tasks enter duration coverage.")
    lines.extend(["", "This is not an elapsed build-time estimate. Missing task durations are not extrapolated.", "", "## Limitations", "", *(f"- {item}" for item in report["limitations"]), ""])
    return "\n".join(lines)


def report_revisions(repo: Path, base: str, head: str, durations: dict | None = None, timeout: int = 300, merge_base: bool = False) -> dict:
    requested_base, head_sha = resolve_commit(repo, base), resolve_commit(repo, head)
    base_sha = requested_base
    if merge_base:
        bases = _git(repo, "merge-base", "--all", requested_base, head_sha).decode().split()
        if len(bases) != 1:
            raise ImpactError("comparison requires exactly one merge base")
        base_sha = bases[0]
    with tempfile.TemporaryDirectory(prefix="ha-cache-impact-") as scratch:
        scratch = Path(scratch)
        snapshots = []
        for name, sha in (("base", base_sha), ("head", head_sha)):
            root = scratch / name / "source"
            materialized = materialize(repo, sha, root)
            snapshots.append(analyze_tree(root, scratch / name / "state",
                                         materialized["gitlinks"], timeout, materialized["symlinks"]))
        report = compare(*snapshots, base_sha, head_sha, durations)
        report["requested_base_sha"] = requested_base
        report["comparison_mode"] = "merge_base" if merge_base else "exact"
        return report


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--worker":
        root, state, manifest, result = map(Path, argv[1:])
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        data = snapshot(root, state, manifest_data["gitlinks"], manifest_data["symlinks"])
        result.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        return 0
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--base", required=True, help="exact base commit SHA")
    parser.add_argument("--head", required=True, help="exact head commit SHA (not merge SHA)")
    parser.add_argument("--merge-base", action="store_true", help="compare merge-base(base, head) to exact head; recommended for PRs")
    parser.add_argument("--json", required=True, type=Path, dest="json_path")
    parser.add_argument("--markdown", required=True, type=Path, dest="markdown_path")
    parser.add_argument("--durations", type=Path, help="measured duration evidence JSON")
    parser.add_argument("--timeout", type=int, default=300, help="per-revision discovery timeout in seconds")
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(args.durations.read_text(encoding="utf-8")) if args.durations else None
        report = report_revisions(args.repo.resolve(), args.base, args.head, evidence, args.timeout, args.merge_base)
        code = 0 if report["complete"] else 3
        if code:
            print("cache impact incomplete: required recipe inputs unavailable (see artifacts)", file=sys.stderr)
    except (ImpactError, OSError, ValueError, subprocess.SubprocessError) as error:
        report = {"schema_version": 1, "kind": "source_impact", "base_sha": args.base,
                  "head_sha": args.head, "error": str(error)}
        print(f"cache impact tool error: {error}", file=sys.stderr)
        code = 2
    for path, text in ((args.json_path, json.dumps(report, indent=2, sort_keys=True) + "\n"),
                       (args.markdown_path, markdown(report))):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
