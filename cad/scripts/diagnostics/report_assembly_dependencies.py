"""Record actual transitive recipes and cache keys without COM or cache transfers.

Run before and after an assembly-helper extraction. The report distinguishes a
builder's direct full-rebuild recipe from its task key, which also folds child
recipes and exact execution identities. Does not open the doit database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "cad/scripts")]

import dodo  # noqa: E402
from _buildgraph import module_deps_of, part_scripts, script_for  # noqa: E402


def record(script, dependencies):
    key, inputs = dodo._cache.key_inputs(dependencies, dodo.ContentChecker._digest)
    return {
        "modules": [dodo._rel_tag(path) for path in module_deps_of(script)],
        "key": key,
        "inputs": dict(inputs),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    assembly_tasks = {task["name"]: task for task in dodo.task_assembly()}
    part_tasks = {task["name"]: task for task in dodo.task_part()}
    assemblies = {}
    for stem in dodo.ASSEMBLY_ORDER:
        dependencies = assembly_tasks[stem]["file_dep"]
        assert dependencies == dodo._assembly_file_deps(stem)
        item = record(script_for(stem), dependencies)
        recipe = dodo._recipe_files(stem)
        item["recipe"] = dodo._digest_files(recipe)
        item["recipe_files"] = [dodo._rel_tag(path) for path in recipe]
        assemblies[stem] = item
    parts = {}
    for script in part_scripts():
        stem = script.stem.removeprefix("build_")
        dependencies = part_tasks[stem]["file_dep"]
        assert dependencies == dodo._part_file_deps(script, stem)
        parts[stem] = record(script, dependencies)
    report = {
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "working_tree": subprocess.check_output(
            ["git", "status", "--short"], cwd=ROOT, text=True
        ).splitlines(),
        "assemblies": assemblies,
        "parts": parts,
        "entrypoints": {
            name: [dodo._rel_tag(path) for path in module_deps_of(ROOT / "cad/scripts" / name)]
            for name in ("refresh_assembly.py", "verify.py", "_assembly_postbuild.py")
        },
        "verify_tasks": {
            f"{group}:{task['name']}": [dodo._rel_tag(path) for path in task["file_dep"]]
            for group, tasks in (
                ("verify_soundness", dodo.task_verify_soundness()),
                ("verify", dodo.task_verify()),
            )
            for task in tasks
        },
    }
    sources = {
        path
        for item in (*assemblies.values(), *parts.values())
        for path in item["inputs"]
        if not path.startswith("cad/out/")
    }
    report["source_sha256"] = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        if (ROOT / path).is_file() else "<missing>"
        for path in sorted(sources)
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(f"{args.output.resolve()} sha256={digest}")
    print(f"{len(assemblies)} assemblies, {len(parts)} leaf parts; no COM or cache transfers")


if __name__ == "__main__":
    main()
