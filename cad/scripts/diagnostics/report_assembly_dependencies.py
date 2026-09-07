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
    assemblies = {}
    for stem in dodo.ASSEMBLY_ORDER:
        item = record(script_for(stem), dodo._assembly_file_deps(stem))
        recipe = dodo._recipe_files(stem)
        item["recipe"] = dodo._digest_files(recipe)
        item["recipe_files"] = [dodo._rel_tag(path) for path in recipe]
        assemblies[stem] = item
    parts = {}
    for script in part_scripts():
        stem = script.stem.removeprefix("build_")
        parts[stem] = record(script, dodo._part_file_deps(script, stem))
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
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(f"{args.output.resolve()} sha256={digest}")
    print(f"{len(assemblies)} assemblies, {len(parts)} leaf parts; no COM or cache transfers")


if __name__ == "__main__":
    main()
