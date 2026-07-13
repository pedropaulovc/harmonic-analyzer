"""Static scan: or_flag fallback names must be declared on their interface.

``early_bound_or_flag(obj, "IFace", *fallback_names)`` (and the
``_common._early_bound`` shim) only applies its fallback ``_FlagAsMethod``
names when the checked-in makepy wrapper is UNAVAILABLE. When the wrapper
loads (the normal case), a fallback name that is NOT declared on the named
interface routes through the early-bound wrapper's lazily-built — and
UNFLAGGED — dynamic fallback dispatch, silently reintroducing the zero-arg
method-vs-property drift the name was listed to prevent. That is exactly how
``create_drawing_standards`` bound segments to base ``ISketchSegment`` while
listing the derived-only ``GetStartPoint2``/``GetEndPoint2``/
``GetCenterPoint2``: every point read failed silently and border segments
were misclassified (fixed via ``concrete_sketch_segment``; this gate keeps
the class of bug from coming back).

The scan parses every ``early_bound_or_flag`` / ``_early_bound`` call site
(``ast``, not regex) across ``cad/scripts`` and ``SolidworksMCP-python/src``
and asserts each string-literal fallback name resolves on the string-literal
interface in the checked-in wrapper — as a declared method
(``sw_type_info.interface_method_names``) or a declared property
(``_prop_map_get_`` / ``_prop_map_put_``). An interface name absent from the
wrapper entirely is also a violation (``early_bound`` raises on it at
runtime). Call sites whose interface or names are not string literals cannot
be checked statically and are counted as skipped.

SolidWorks-free: only imports the vendored ``_generated`` wrapper module
(needs pywin32 importable, no COM connection).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

pytest.importorskip("win32com.client")

from solidworks_mcp.adapters import sw_type_info  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (
    REPO_ROOT / "cad" / "scripts",
    REPO_ROOT / "SolidworksMCP-python" / "src",
)
# The wrapper itself and virtualenvs are not call sites.
EXCLUDE_PARTS = {"_generated", ".venv", "__pycache__"}
CALL_NAMES = {"early_bound_or_flag", "_early_bound"}


def _call_name(node: ast.Call) -> str | None:
    """Return the bare callable name for ``f(...)`` / ``mod.f(...)`` calls."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _str_literal(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _iter_call_sites() -> tuple[list[tuple[Path, int, str, list[str]]], int]:
    """Collect ``(file, line, interface, fallback_names)`` call sites.

    Returns the statically-checkable sites plus a count of sites skipped
    because their interface or a fallback name is not a string literal.
    """
    sites: list[tuple[Path, int, str, list[str]]] = []
    skipped = 0
    for root in SCAN_ROOTS:
        for path in sorted(root.rglob("*.py")):
            if EXCLUDE_PARTS.intersection(path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if _call_name(node) not in CALL_NAMES:
                    continue
                if len(node.args) < 2:
                    continue  # the shim's own def/passthroughs
                interface = _str_literal(node.args[1])
                names = [_str_literal(arg) for arg in node.args[2:]]
                if interface is None or any(n is None for n in names):
                    skipped += 1
                    continue
                if not names:
                    continue  # nothing to flag, nothing to check
                sites.append((path, node.lineno, interface, names))  # type: ignore[arg-type]
    return sites, skipped


def _declared_names(interface: str) -> frozenset[str] | None:
    """All member names resolvable on ``interface``, or None if absent."""
    cls = getattr(sw_type_info._wrapper_module, interface, None)
    if cls is None:
        return None
    methods = sw_type_info.interface_method_names(interface)
    props = set(getattr(cls, "_prop_map_get_", {})) | set(
        getattr(cls, "_prop_map_put_", {})
    )
    return frozenset(methods) | frozenset(props)


def test_or_flag_fallback_names_are_declared_on_their_interface() -> None:
    sw_type_info._ensure_loaded()
    if sw_type_info._wrapper_module is None:
        pytest.skip("checked-in SolidWorks wrapper failed to load")

    # name -> interfaces declaring it, for actionable violation messages.
    declaring: dict[str, list[str]] = {}
    for iface, methods in sw_type_info._interface_methods.items():
        for method in methods:
            declaring.setdefault(method, []).append(iface)

    sites, skipped = _iter_call_sites()
    assert sites, "scan found no or_flag call sites — scanner or layout broke"

    violations: list[str] = []
    for path, lineno, interface, names in sites:
        rel = path.relative_to(REPO_ROOT)
        declared = _declared_names(interface)
        if declared is None:
            violations.append(
                f"{rel}:{lineno}: interface {interface!r} is not in the "
                "checked-in wrapper (early_bound raises on it at runtime)"
            )
            continue
        for name in names:
            if name in declared:
                continue
            hint = sorted(declaring.get(name, []))[:4]
            where = f"; declared on {', '.join(hint)}" if hint else "; declared nowhere"
            violations.append(
                f"{rel}:{lineno}: fallback {name!r} is not declared on "
                f"{interface}{where} — under early binding it routes to an "
                "unflagged dynamic fallback (method-vs-property drift); bind "
                "the right interface (or concrete_sketch_segment for segments)"
            )

    print(
        f"or_flag scan: {len(sites)} call sites checked, "
        f"{skipped} skipped (non-literal args)",
        file=sys.stderr,
    )
    assert not violations, "\n".join(violations)
