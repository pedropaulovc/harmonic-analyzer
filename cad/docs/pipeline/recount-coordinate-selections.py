"""Re-run the literal AST predicate used for the e5b3da74 43/92 audit.

Read-only: parses registered recipe files, without importing project modules or
connecting to SolidWorks. Run with the audited source checkout as --root.
The classification is a bounded source-callsite inventory, not dynamic coverage.
"""

import argparse
import ast
import collections
import pathlib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, required=True)
    args = parser.parse_args()
    scripts = args.root.resolve() / "cad/scripts"
    registry = ast.parse((scripts / "_drawing_registry.py").read_text(encoding="utf-8"))
    rows = [
        {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords}
        for call in ast.walk(registry)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "DrawingSpec"
    ]
    counts = collections.Counter()
    recipes = collections.defaultdict(set)
    locations = collections.defaultdict(list)
    for row in rows:
        tree = ast.parse((scripts / row["script_name"]).read_text(encoding="utf-8"))
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call):
                continue
            name = (
                call.func.id
                if isinstance(call.func, ast.Name)
                else call.func.attr
                if isinstance(call.func, ast.Attribute)
                else ""
            )
            supplied = {
                keyword.arg
                for keyword in call.keywords
                if not (
                    isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is None
                )
            }
            coordinate = (
                name in {"add_edge_dimension", "find_edge_near", "SelectByID2"}
                or name
                in {
                    "PmiDrawingPlacement",
                    "add_datum_feature",
                    "add_feature_control_frame",
                    "add_surface_finish",
                }
                and not supplied & {"entity", "edge_entity", "annotation"}
                or name == "add_native_hole_callout"
                and "edge" not in supplied
                or name == "add_view_centerline"
                and not supplied & {"face", "entity"}
                or name == "insert_hole_table"
                and (
                    "hole_entities" not in supplied
                    or not supplied & {"datum_entity", "datum_axes"}
                )
            )
            if not coordinate:
                continue
            counts[name] += 1
            recipes[name].add(row["name"])
            locations[name].append(f"{row['script_name']}:{call.lineno}")

    union = set().union(*recipes.values())
    print("Source root:", args.root.resolve())
    print(
        "Registry:",
        len(rows),
        dict(collections.Counter(row.get("source_kind", "part") for row in rows)),
    )
    print("Coordinate union:", len(union))
    for name in sorted(counts):
        print(name, "sites", counts[name], "recipes", len(recipes[name]))
        print("  ", ", ".join(locations[name]))
    print("Union names:", ", ".join(sorted(union)))
    assert len(rows) == 92 and len(union) == 43, "audited registry/count changed"


if __name__ == "__main__":
    main()
