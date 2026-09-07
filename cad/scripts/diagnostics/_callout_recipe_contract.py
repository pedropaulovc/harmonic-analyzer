"""Explicit diagnostic ABIs, recognized before native attachment or file writes.

This is not a runtime fallback: exactly one reviewed direct import is required.
Historical setter experiments belong to DRAWING_SETTER_V1; the new production
recipe calls SOURCE_VERIFIER_V1. Never invent one alias from the other.
"""

import ast
from enum import StrEnum


class CalloutContract(StrEnum):
    DRAWING_SETTER_V1 = "drawing_setter_v1"
    SOURCE_VERIFIER_V1 = "source_verifier_v1"

    @property
    def helper_name(self):
        return {
            CalloutContract.DRAWING_SETTER_V1: "set_dimension_callouts",
            CalloutContract.SOURCE_VERIFIER_V1: "verify_dimension_callouts",
        }[self]


HISTORICAL_REPLAY = (
    "Use an independent checkout of frozen 9f2f5d9a and its matching tooling "
    "for historical lower-text negatives; no setter alias is synthesized."
)


def recipe_contract(code):
    tree = ast.parse(code)
    names = {variant.helper_name: variant for variant in CalloutContract}
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        for imported in node.names:
            if imported.name not in names:
                continue
            if node.module != "_drawing_common" or node.level or imported.asname is not None:
                raise ValueError("unsupported callout recipe import contract")
            found.append(names[imported.name])
    if len(found) != 1:
        raise ValueError("recipe requires exactly one explicit callout helper contract")
    contract = found[0]
    if contract is CalloutContract.SOURCE_VERIFIER_V1:
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == contract.helper_name
        ]
        if len(calls) != 1 or not any(
            keyword.arg == "feature_name"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "ArborBoreProfile"
            for keyword in calls[0].keywords
        ):
            raise ValueError(
                "alignment verifier contract requires one exact ArborBoreProfile call"
            )
        required = {"view", "source_model"}
        if not required.issubset(keyword.arg for keyword in calls[0].keywords):
            raise ValueError(
                "alignment verifier contract requires explicit view and source_model"
            )
    return contract


def require_experiment(contract, *, lower_text=None, source_authoring=None):
    if lower_text is not None and contract is not CalloutContract.DRAWING_SETTER_V1:
        raise ValueError(
            "lower-text experiment does not support the source verifier recipe. "
            + HISTORICAL_REPLAY
        )
    if (
        source_authoring is not None
        and contract is not CalloutContract.SOURCE_VERIFIER_V1
    ):
        raise ValueError(
            "source-authoring control requires the actual verify_dimension_callouts recipe; historical setter interception is retired"
        )
