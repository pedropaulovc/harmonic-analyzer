"""Source contracts for drawing tests, independent of Python line wrapping."""

import ast


def linked_note_properties(source: str) -> tuple[str, ...]:
    return tuple(
        node.args[1].value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_property_linked_note"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    )
