"""``_fit_limits`` renders tolerance bands the way ASME Y14.5 prints them."""

from __future__ import annotations

import ast
import dataclasses
import importlib
import re
import types
from collections import Counter
from pathlib import Path

import pytest

from _fit_limits import REAM_H7, SHAFT_H, band_text, deviations


def test_a_nil_deviation_is_a_bare_zero():
    """#923 / #851: Y14.5-2018 §2.3 metric unilateral -- a single 0, no sign."""
    assert band_text(SHAFT_H) == "0/-0.02"
    assert band_text(REAM_H7) == "+0.01/0"
    assert band_text((0.000, -0.250)) == "0/-0.25"


def test_a_band_that_straddles_the_nominal_keeps_both_signs():
    assert band_text((0.025, 0.010)) == "+0.03/+0.01"
    assert band_text((0.1, -0.1)) == "+0.10/-0.10"


def test_an_inverted_band_is_refused():
    with pytest.raises(ValueError):
        band_text((-0.02, 0.0))
    with pytest.raises(ValueError):
        deviations((-0.02, 0.0))


def test_a_band_quotes_its_nominals_places():
    assert band_text((0.000, -0.020), decimals=3) == "0/-0.020"
    assert band_text((0.012, 0.000), decimals=3) == "+0.012/0"
    with pytest.raises(ValueError):
        band_text((0.1, 0.0), decimals=-1)


# --------------------------------------------------------------------------
# Fleet burn-down: a signed nil deviation ("+0.00/-0.02", "+0.10/-0.00")
# typed into drawing text instead of rendered through band_text.  The six
# sites below are main's legacy text in files being rewritten in flight; each
# owner renders its band through band_text(...) and DELETES its entry here.
# A new site fails; so does a listed site that is gone but still listed.
# --------------------------------------------------------------------------

SCRIPTS = Path(__file__).resolve().parent
BAND = re.compile(r"[+-]\d+\.\d+\s*/\s*[+-]\d+\.\d+")
SIGNED_NIL = re.compile(r"^[+-]0\.0+$")

# (module, band text) -> (sites, owning PR)
LEGACY_SIGNED_NIL_BANDS = {
    ("alignment_pinion_spec.py", "+0.00/-0.02"): (1, "#814"),
    ("cone_tip_block_spec.py", "+0.10/-0.00"): (1, "#838"),
    ("crank_drive_gear_spec.py", "+0.000/-0.020"): (2, "#892/#906"),
    ("crank_pinion_spec.py", "+0.000/-0.020"): (2, "#892/#906"),
}


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _strings(value: object, seen: set[int]):
    """Every string reachable from an exported value (containers, dataclasses)."""
    if id(value) in seen:
        return
    seen.add(id(value))
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(key, seen)
            yield from _strings(item, seen)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _strings(item, seen)
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            yield from _strings(getattr(value, field.name), seen)


def _nil_bands(text: str) -> list[str]:
    """Signed-nil bands in ``text``, normalized to ``upper/lower`` without spaces."""
    bands = ["/".join(side.strip() for side in band.split("/")) for band in BAND.findall(text)]
    return [band for band in bands if any(SIGNED_NIL.match(side) for side in band.split("/"))]


def _signed_nil_bands() -> Counter[tuple[str, str]]:
    """Every band with a signed nil side a drawing can print.

    A ``*_spec.py`` module is pure data, so its EXPORTED strings are scanned
    as rendered -- a band an f-string assembles from numbers
    (``f"+{BAND[0]:.3f}/{BAND[1]:.3f}"``) is only visible there. Every other
    build/drawing module is scanned by its string literals (f-string pieces
    included, docstrings and comments excluded).
    """
    found: Counter[tuple[str, str]] = Counter()
    for path in sorted(SCRIPTS.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        if path.name.endswith("_spec.py"):
            module = importlib.import_module(path.stem)
            seen: set[int] = set()
            for name, value in vars(module).items():
                if name.startswith("__") or isinstance(value, types.ModuleType):
                    continue
                for text in _strings(value, seen):
                    for band in _nil_bands(text):
                        found[(path.name, band)] += 1
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = _docstring_ids(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                for band in _nil_bands(node.value):
                    found[(path.name, band)] += 1
    return found


def test_no_new_signed_nil_deviation_in_drawing_text():
    """#923 / #851: ASME Y14.5 §2.3 prints a nil deviation as a bare 0."""
    expected = Counter({site: count for site, (count, _owner) in LEGACY_SIGNED_NIL_BANDS.items()})
    assert _signed_nil_bands() == expected, (
        "a signed nil deviation site appeared or was fixed: render bands through "
        "_fit_limits.band_text(...) and keep LEGACY_SIGNED_NIL_BANDS exact"
    )


def test_the_burn_down_detector_sees_a_band_an_f_string_assembles():
    """reviewfirst on #814: MHA-002's gear-data row builds its band from numbers."""
    band = (0.0, -0.100)
    rows = {"BASE-TANGENT SPAN": f"{3.964:.3f} +{band[0]:.3f}/{band[1]:.3f}"}
    assert [b for text in _strings(rows, set()) for b in _nil_bands(text)] == ["+0.000/-0.100"]
    assert _nil_bands(f"3.964 {band_text(band, decimals=3)}") == []


def test_the_burn_down_detector_reads_through_spaces_around_the_slash():
    """Codex P2 on #923: ``+0.000 / -0.100`` is the same band."""
    assert _nil_bands(f"3.964 +{0.0:.3f} / {-0.1:.3f}") == ["+0.000/-0.100"]


def test_the_burn_down_detector_sees_a_band_in_an_f_string_piece():
    tree = ast.parse('NOTE = f"DIA {X:.3f} +0.10/-0.00 FROM E"\n')
    pieces = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert [b for p in pieces for b in BAND.findall(p)] == ["+0.10/-0.00"]
