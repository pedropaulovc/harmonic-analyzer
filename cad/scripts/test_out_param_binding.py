r"""The ``[out]``-param convention is enforced, not just documented.

542 of SolidWorks' methods declare at least one ``[out]`` param, and which
marshalling convention applies depends entirely on the binding of the object at
the call site:

* through the **makepy wrapper** the outs ride the RETURN TUPLE (the generated
  method defaults each one to ``pythoncom.Missing``);
* on a **raw late-bound dispatch** they must be ``VT_BYREF`` VARIANTs read back
  via ``.value``.

Mixing them does not raise. An unwritten byref reads as "no data", which for a
diagnostic API is indistinguishable from "no errors found" -- a WRONG ANSWER
that looks like a clean result. That is what makes this trap expensive: it cost
a full session chasing a "GetWhatsWrong is blind mid-build" defect that did not
exist.

The fix is structural rather than advisory: ``_common._early_bound`` now raises
instead of silently returning a raw dispatch, so on the build path every object
IS early-bound and the byref form is never correct. These tests keep it that
way, because a comment saying "consume the tuple" is exactly the kind of
un-enforced guidance that decayed into folklore last time.

Run: ``uv run python -m pytest cad/scripts/test_out_param_binding.py -q``
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
DIAGNOSTICS = SCRIPTS / "diagnostics"

# A standalone probe that connects with its own GetObject/Dispatch really is
# late-bound, so byrefs there are CORRECT, not a slip. Such a file must say so
# out loud -- the marker is what keeps the divergence visible instead of it
# looking like two contradictory idioms for the same call.
LATE_BOUND_MARKER = "LATE-BOUND PROBE"

_BYREF = re.compile(r"VT_BYREF")


def _code_lines(path: Path) -> list[tuple[int, str]]:
    """(lineno, text) for real CODE only -- comments and strings dropped.

    Tokenized rather than grepped: this file, ``_common._early_bound`` and the
    memory notes all legitimately DISCUSS ``VT_BYREF`` in prose, and a plain
    text search cannot tell an explanation from a call.
    """
    source = path.read_text(encoding="utf-8")
    kept: dict[int, list[str]] = {}
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok in tokens:
            if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.NL):
                continue
            kept.setdefault(tok.start[0], []).append(tok.string)
    except (tokenize.TokenError, IndentationError, SyntaxError):  # pragma: no cover
        return [(n, ln) for n, ln in enumerate(source.splitlines(), 1)]
    return [(n, " ".join(parts)) for n, parts in sorted(kept.items())]


def _function_body(source: str, name: str) -> str:
    """A function's source with its docstring removed."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            return "\n".join(ast.unparse(stmt) for stmt in body)
    raise AssertionError(f"{name} not found")


def _build_path_sources() -> list[Path]:
    """Every script the build/verify path can import (diagnostics excluded)."""
    return sorted(
        path
        for path in SCRIPTS.glob("*.py")
        if not path.name.startswith("test_")
    )


def test_no_byref_variants_on_the_build_path() -> None:
    """The build path is uniformly early-bound, so a byref is always a bug."""
    offenders = [
        f"{path.name}:{number}: {text}"
        for path in _build_path_sources()
        for number, text in _code_lines(path)
        if _BYREF.search(text)
    ]
    assert not offenders, (
        "VT_BYREF on the build path. Every build-path object is early-bound "
        "(_common._early_bound raises rather than returning a raw dispatch), so "
        "[out] params ride the RETURN TUPLE -- call the method bare and unpack. "
        "A byref here stays unwritten and reads as 'no data':\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    "path", sorted(DIAGNOSTICS.glob("*.py")), ids=lambda p: p.name
)
def test_late_bound_probes_declare_themselves(path: Path) -> None:
    """A diagnostic using byrefs must state that it is late-bound.

    Without this the two idioms look interchangeable, which is precisely how a
    probe that "works standalone" and the same call coming back EMPTY in-build
    were treated as one mystery rather than two bindings.
    """
    source = path.read_text(encoding="utf-8")
    if not _BYREF.search(source):
        return
    assert LATE_BOUND_MARKER in source, (
        f"{path.name} passes VT_BYREF VARIANTs but does not declare itself a "
        f"{LATE_BOUND_MARKER!r}. Either add the marker to its module docstring "
        "(with a line saying it connects via its own GetObject/Dispatch, so the "
        "outs land in the byrefs rather than the return tuple), or bind the "
        "interface through the generated wrapper and consume the tuple instead."
    )


def test_early_bound_refuses_to_return_a_raw_dispatch() -> None:
    """The root-cause fix itself: no silent fallback to late binding.

    Pinned by reading the source rather than by calling it, so this runs with no
    SolidWorks and no pywin32 -- the historic ``except Exception: return obj``
    is the single line that made binding invisible at 313 call sites.
    """
    source = (SCRIPTS / "_common.py").read_text(encoding="utf-8")
    body = _function_body(source, "_early_bound")
    assert "except Exception:" not in body, (
        "_early_bound must not swallow a binding failure -- returning the raw "
        "dispatch flips the [out]-param convention invisibly"
    )
    assert "raise RuntimeError(" in body
    assert "early_bound_or_flag" not in body, (
        "early_bound_or_flag falls back to a flagged LATE-BOUND object when no "
        "generated class resolves, which is the silent path being removed"
    )
