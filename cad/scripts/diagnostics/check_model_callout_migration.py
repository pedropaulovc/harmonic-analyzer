"""Read-only AST check for the bounded source-callout migration; no COM."""

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "cad/scripts"
sys.path.insert(0, str(SCRIPTS))
from diagnostics._model_callout_migration_inventory import INVENTORY as inventory  # noqa: E402

definitions = {row["drawing"]: row for row in inventory["map_definitions"]}
active = sorted(
    {row["drawing"] for row in inventory["calls"] if row["rows"]}
    - {"draw_alignment_pinion"}
)
removed_expression_imports = {
    "draw_cone_lock_knob": {"STUD_THREAD"},
    "draw_cone_pivot_screw": {"THREAD_DESIGNATION"},
    "draw_magnifying_vertical_rod": {"ROD_DIA"},
    "draw_pinion_arbor": {"CAP_R"},
}
separate_callout_modules = {
    "draw_cone_pivot_post": "cone_pivot_post_callouts",
    "draw_crank_drive_gear": "crank_drive_gear_callouts",
    "draw_cone_pivot_screw": "cone_pivot_screw_callouts",
    "draw_fillister_screw": "fillister_screw_callouts",
}


class ApprovedCalloutChanges(ast.NodeTransformer):
    def __init__(self, drawing):
        self.drawing = drawing
        self.spec = drawing.removeprefix("draw_") + "_spec"
        self.maps = {row["name"] for row in definitions[drawing]["maps"]}
        if drawing == "draw_connecting_rod":
            self.maps = {"DIMENSION_CALLOUTS"}
        if drawing == "draw_fillister_screw":
            # Existing whole-text callout, separately pinned by the fillister
            # identity/content test; not a geometry or arbitrary import exemption.
            self.maps.add("DIMENSION_TEXT")

    def visit_ImportFrom(self, node):
        if node.level != 0:
            return node
        removed = set()
        if node.module == self.spec:
            removed = self.maps | removed_expression_imports.get(self.drawing, set())
        if (
            self.drawing in separate_callout_modules
            and node.module == separate_callout_modules[self.drawing]
        ):
            removed = self.maps
        if node.module == "_drawing_common":
            removed = {"set_dimension_callouts", "verify_dimension_callouts"}
        if node.module == "_model_dimension_callouts":
            removed = {"author_model_callouts"}
        node.names = [name for name in node.names if name.name not in removed]
        return node if node.names else None

    def visit_Assign(self, node):
        names = {target.id for target in node.targets if isinstance(target, ast.Name)}
        if names & (self.maps | {"callout_source_model"}):
            return None
        return self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if isinstance(node.target, ast.Name) and node.target.id in self.maps:
            return None
        return self.generic_visit(node)

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
            if node.value.func.id in {
                "set_dimension_callouts",
                "verify_dimension_callouts",
                "author_model_callouts",
            }:
                return None
        return self.generic_visit(node)

    def visit_Call(self, node):
        if (
            self.drawing == "draw_cone_pivot_screw"
            and isinstance(node.func, ast.Name)
            and node.func.id == "FastenerSheet"
        ):
            node.keywords = [
                kw for kw in node.keywords if kw.arg != "side_callout_feature"
            ]
        return self.generic_visit(node)


def check(baseline):
    rows = []
    for drawing in active:
        stem = drawing.removeprefix("draw_")
        for name in (drawing, "build_" + stem, stem + "_spec"):
            relative = "cad/scripts/" + name + ".py"
            before = subprocess.check_output(
                ["git", "show", baseline + ":" + relative], text=True, encoding="utf-8"
            )
            after = (ROOT / relative).read_text(encoding="utf-8")
            expected = ApprovedCalloutChanges(drawing).visit(ast.parse(before))
            actual = ApprovedCalloutChanges(drawing).visit(ast.parse(after))
            if ast.dump(expected) != ast.dump(actual):
                raise AssertionError(relative + ": non-callout AST changed")
            rows.append(relative)
    print(
        json.dumps(
            {
                "baseline": subprocess.check_output(
                    ["git", "rev-parse", baseline], text=True
                ).strip(),
                "status": "passed",
                "files": rows,
                "count": len(rows),
                "scope": "all AST except explicitly enumerated callout maps, imports, source capture, author/verifier calls and cone-pivot metadata; exact removed callout content independently pinned by test_model_callout_fleet_drawing and test_fillister_screw_drawing",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default=inventory["baseline"])
    check(parser.parse_args().baseline)
