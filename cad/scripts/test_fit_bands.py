"""Every fit band a build script hands to SolidWorks is valid at import time.

A band only reaches ``_fit_limits.deviations`` (or the bilateral setter) inside
``build()``, which needs a SolidWorks seat. So an inverted or zero-width band
used to pass the whole offline suite and fail its farm leaf instead: warm-c486
lost ``part:crank_drive_gear`` to "fit band is inverted: (0.025, 0.025)" at
``build_crank_drive_gear.build()`` -> ``deviations(BORE_DIA_BAND)``.

This file finds every band consumer by reading the scripts' source, resolves each
argument in the imported module (the value ``build()`` would see), and applies
the same checks ``build()`` would. ``deviations(band)`` /
``fit_limits(nominal, band)`` / ``band_text(band)`` take an ``(upper, lower)``
band; the helper must accept it and return lower < upper.

Two source rules keep every band on that checked path:

* ``set_dimension_bilateral_tolerance`` takes its signed (lower, upper) pair only
  as ``*deviations(BAND)``; a raw tuple or two loose numbers skip the check.
* No script reads a band raw (``X_BAND[i]``, ``*X_BAND``, ``a, b = X_BAND``)
  outside the audited ``RAW_ACCESS_ALLOWLIST``. ``deviations(X_BAND)`` returns
  (lower, upper) whatever the band, so ``deviations(X_BAND)[1]`` is the upper.

A second test inventories every module-level band (an uppercase name with
``BAND`` or ``BANDS`` as a word) in every script outside ``OUT_OF_SCOPE``. A
scalar is a symmetric half-width and must be finite and positive. A tuple must be
fed to a checked consumer, be listed in ``INDEXED_FIT_BANDS`` (a fit band read
by index, checked the same way), or be listed in ``NOT_FIT_BANDS`` with the
reason it is not a fit. Any other shape fails.

Planted sources prove each scanner and rule fails on what it exists to catch,
so a scanner that silently finds nothing cannot pass the suite.
"""

from __future__ import annotations

import ast
import importlib
import math
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import _fit_limits

SCRIPTS = Path(__file__).resolve().parent

# Helpers that take an (upper, lower) band, and the positional index of the band.
_BAND_HELPERS = {"deviations": 0, "band_text": 0, "fit_limits": 1}

# Setters that take a signed (lower, upper) deviation pair after
# (adapter, feature, dimension), and the helpers allowed to produce that pair
# from an (upper, lower) band.
_PAIR_SETTERS = {"set_dimension_bilateral_tolerance": 3}
_PAIR_PRODUCERS = {"deviations"}

# A consumer whose argument is a name local to build() (so it cannot be read off
# the imported module) must say here which module-level value build() derives it
# from. "each" means build() loops over the tuple of bands.
LOCAL_BAND_SOURCES: dict[tuple[str, str], tuple[str, str]] = {
    # for section, band in enumerate(SECTION_DIA_BANDS): ... deviations(band)
    ("build_cone_gear_shaft", "band"): ("SECTION_DIA_BANDS", "each"),
}

# Scripts whose module-level bands are not tolerances, with the reason.
OUT_OF_SCOPE: dict[str, str] = {
    "verify": (
        "_COMPONENT_BAND is the retired component-count gate's reference data "
        "(component counts per assembly), not a size tolerance"
    ),
}

# Consumer modules that cannot be imported without SolidWorks, with the reason.
# Empty today: every band consumer imports offline.
OFFLINE_IMPORT_EXCLUSIONS: dict[str, str] = {}

# Module-level *_BAND tuples that are not fit bands, so no checked consumer
# reads them. A new band tuple must be fed to a consumer above or listed here.
NOT_FIT_BANDS: dict[tuple[str, str], str] = {
    ("build_drive_train_assembly", "ARBOR_PED_SOUTH_Z_BAND"): (
        "plan z extent of the south pedestal foot (clearance geometry)"
    ),
    ("build_drive_train_assembly", "ARBOR_PED_NORTH_Z_BAND"): (
        "plan z extent of the north pedestal foot (clearance geometry)"
    ),
    ("build_drive_train_assembly", "_G64_BAND"): (
        "64T gear z extent used for clearance checks"
    ),
    ("build_drive_train_assembly", "_ARB_Z_BANDS"): (
        "(z extent, minimum gap) pairs for the swing-plate clearance sweep"
    ),
}

# (upper, lower) fit bands that no helper reads: the owning module indexes them
# to print or derive limits. An inverted one prints wrong limits, so they get
# the same check as a helper-fed band.
INDEXED_FIT_BANDS: dict[tuple[str, str], str] = {
    ("alignment_pinion_spec", "BASE_TANGENT_SPAN_BAND"): (
        "indexed into the span-measurement note text"
    ),
    ("pinion_arbor_spec", "DRUM_LEN_BAND"): "indexed into the drum-length limits",
    ("pinion_handle_geometry", "ROD_DIA_BAND"): (
        "indexed by pinion_arbor_spec for the cross-rod fit limits"
    ),
}

# The crank-drive gear's derived bore band collapses to zero width on this
# integration head. crankhub's 64T bore fix (integ/64t-bore-resolve) resolves
# it and removes this mark.
_XFAIL_64T_BORE = pytest.mark.xfail(
    strict=True,
    raises=ValueError,
    reason=(
        "BORE_DIA_BAND derives to (0.025, 0.025): zero width. Fixed by crankhub's "
        "64T bore resolve (integ/64t-bore-resolve), which removes this xfail."
    ),
)
KNOWN_BAD: dict[str, pytest.MarkDecorator] = {
    "build_crank_drive_gear:BORE_DIA_BAND": _XFAIL_64T_BORE,
}


@dataclass(frozen=True)
class BandUse:
    module: str  # consumer module stem
    line: int
    expression: str  # the argument as written


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _script_trees() -> list[tuple[str, ast.Module]]:
    """(stem, parsed source) of every non-test script."""
    return [
        (path.stem, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for path in sorted(SCRIPTS.glob("*.py"))
        if not path.name.startswith("test_")
    ]


SCRIPT_TREES = _script_trees()


def _band_uses_in(tree: ast.AST, module: str) -> list[BandUse]:
    uses: list[BandUse] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name not in _BAND_HELPERS:
            continue
        index = _BAND_HELPERS[name]
        if len(node.args) > index:
            uses.append(BandUse(module, node.lineno, ast.unparse(node.args[index])))
    return uses


def _band_uses() -> list[BandUse]:
    return [
        use
        for stem, tree in SCRIPT_TREES
        if stem != "_fit_limits"
        for use in _band_uses_in(tree, stem)
    ]


BAND_USES = _band_uses()


def _import(module: str) -> Any:
    if module in OFFLINE_IMPORT_EXCLUSIONS:
        pytest.skip(f"{module}: {OFFLINE_IMPORT_EXCLUSIONS[module]}")
    return importlib.import_module(module)


def _resolve(use: BandUse) -> list[tuple[str, Any]]:
    """The value(s) build() passes, read from the imported consumer module."""
    module = _import(use.module)
    key = (use.module, use.expression)
    if key in LOCAL_BAND_SOURCES:
        source, how = LOCAL_BAND_SOURCES[key]
        value = getattr(module, source)
        assert how == "each", f"unknown local-source mode {how!r}"
        return [(f"{source}[{i}]", band) for i, band in enumerate(value)]
    try:
        value = eval(use.expression, vars(module))  # noqa: S307 -- repo source
    except NameError as error:
        raise AssertionError(
            f"{use.module}:{use.line}: band argument {use.expression!r} is not a "
            "module-level value, so this test cannot see what build() passes. Add "
            "it to LOCAL_BAND_SOURCES with the module-level value it derives from."
        ) from error
    return [(use.expression, value)]


def _check_band(label: str, band: Any) -> None:
    assert isinstance(band, tuple) and len(band) == 2, f"{label}: not a 2-tuple: {band!r}"
    assert all(isinstance(v, (int, float)) for v in band), f"{label}: {band!r}"
    # Exactly what build() does; raises on an inverted or zero-width band.
    lower, upper = _fit_limits.deviations(band)
    assert lower < upper, f"{label}: lower {lower} >= upper {upper}"
    assert upper - lower > 0.0, f"{label}: zero-width band {band!r}"


def _case_ids() -> list[Any]:
    params = []
    seen: set[str] = set()
    for use in BAND_USES:
        case_id = f"{use.module}:{use.expression}"
        if case_id in seen:
            continue
        seen.add(case_id)
        marks = [KNOWN_BAD[case_id]] if case_id in KNOWN_BAD else []
        params.append(pytest.param(use, id=case_id, marks=marks))
    return params


def test_band_uses_are_found() -> None:
    # A scanner that silently finds nothing would pass every case below.
    assert len(BAND_USES) >= 50, len(BAND_USES)
    ids = {f"{u.module}:{u.expression}" for u in BAND_USES}
    assert "build_crank_drive_gear:BORE_DIA_BAND" in ids
    assert "build_cone_gear_shaft:band" in ids


def test_known_bad_ids_are_live() -> None:
    ids = {f"{u.module}:{u.expression}" for u in BAND_USES}
    assert set(KNOWN_BAD) <= ids, set(KNOWN_BAD) - ids
    assert set(LOCAL_BAND_SOURCES) <= {(u.module, u.expression) for u in BAND_USES}


@pytest.mark.parametrize("use", _case_ids())
def test_every_band_build_passes_is_valid(use: BandUse) -> None:
    for label, band in _resolve(use):
        _check_band(f"{use.module}:{use.line} {label}", band)


def _is_band_name(name: str) -> bool:
    return name.isupper() and not {"BAND", "BANDS"}.isdisjoint(name.split("_"))


def _module_statements(body: list[ast.stmt]) -> Iterator[ast.stmt]:
    """Module-level statements, including those inside if/try blocks, but never
    a function or class body."""
    for node in body:
        yield node
        if isinstance(node, ast.If):
            yield from _module_statements(node.body)
            yield from _module_statements(node.orelse)
        if isinstance(node, ast.Try):
            for block in (node.body, node.orelse, node.finalbody):
                yield from _module_statements(block)
            for handler in node.handlers:
                yield from _module_statements(handler.body)


def _assigned_names(target: ast.expr) -> Iterator[str]:
    if isinstance(target, ast.Name):
        yield target.id
    if isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            yield from _assigned_names(element)


def _band_names_in(tree: ast.Module) -> list[str]:
    """Every band name the module assigns at module level."""
    found: list[str] = []
    for node in _module_statements(tree.body):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            found += [name for name in _assigned_names(target) if _is_band_name(name)]
    return found


def _inventory() -> list[tuple[str, str]]:
    """(module, name) of every module-level band in every in-scope script."""
    return [
        (stem, name)
        for stem, tree in SCRIPT_TREES
        if stem not in OUT_OF_SCOPE
        for name in _band_names_in(tree)
    ]


def _inventory_problems(
    entries: list[tuple[str, str, Any]], checked: set[int]
) -> list[str]:
    """Bands in ``entries`` (module, name, value) that fail their shape's rule."""
    problems = []
    for module_name, name, value in entries:
        label = f"{module_name}.{name} = {value!r}"
        key = (module_name, name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            # A scalar is a symmetric .X/.XX half-width.
            if not (math.isfinite(value) and value > 0):
                problems.append(f"{label}: a half-width must be finite and > 0")
            continue
        if not isinstance(value, tuple):
            problems.append(f"{label}: unclassified band shape")
            continue
        if id(value) in checked or key in NOT_FIT_BANDS or key in INDEXED_FIT_BANDS:
            continue
        problems.append(f"{label}: no checked consumer reads it")
    return problems


def test_every_band_is_checked_or_classified() -> None:
    checked: set[int] = set()
    for use in BAND_USES:
        if use.module in OFFLINE_IMPORT_EXCLUSIONS:
            continue
        module = importlib.import_module(use.module)
        key = (use.module, use.expression)
        if key in LOCAL_BAND_SOURCES:
            source = getattr(module, LOCAL_BAND_SOURCES[key][0])
            checked.add(id(source))
            checked.update(id(band) for band in source)
            continue
        try:
            checked.add(id(eval(use.expression, vars(module))))  # noqa: S307
        except NameError:
            continue  # reported by the per-use test
    entries = [
        (module_name, name, getattr(importlib.import_module(module_name), name))
        for module_name, name in _inventory()
    ]
    problems = _inventory_problems(entries, checked)
    assert not problems, (
        "feed each band through _fit_limits.deviations, or list it in "
        "NOT_FIT_BANDS / INDEXED_FIT_BANDS with a reason: " + "; ".join(problems)
    )


@pytest.mark.parametrize(
    ("module_name", "name"),
    sorted(INDEXED_FIT_BANDS),
    ids=[f"{m}:{n}" for m, n in sorted(INDEXED_FIT_BANDS)],
)
def test_indexed_fit_bands_are_valid(module_name: str, name: str) -> None:
    band = getattr(importlib.import_module(module_name), name)
    _check_band(f"{module_name}.{name}", band)


def test_classification_lists_are_current() -> None:
    inventory = set(_inventory())
    for listing in (NOT_FIT_BANDS, INDEXED_FIT_BANDS):
        stale = set(listing) - inventory
        assert not stale, f"listed constants that are gone: {sorted(stale)}"
    assert not set(NOT_FIT_BANDS) & set(INDEXED_FIT_BANDS)


@pytest.mark.parametrize(
    "band",
    [
        (0.025, 0.025),  # the warm-c486 crank_drive_gear band
        (0.010, 0.050),
    ],
)
def test_check_band_rejects_inverted_and_zero_width_bands(
    band: tuple[float, float],
) -> None:
    # The guard must fail inside deviations(), as the farm leaf did, or every
    # parametrized case above passes vacuously.
    with pytest.raises(ValueError, match="fit band is inverted"):
        _check_band("synthetic", band)


def test_scanner_finds_a_planted_consumer() -> None:
    source = (
        "def build(adapter):\n"
        "    deviations(NEW_BAND)\n"
        "    _fit_limits.fit_limits(12.0, OTHER_BAND)\n"
        "    band_text(TEXT_BAND)\n"
    )
    found = {use.expression for use in _band_uses_in(ast.parse(source), "planted")}
    assert found == {"NEW_BAND", "OTHER_BAND", "TEXT_BAND"}


def test_inventory_finds_a_planted_band_constant() -> None:
    source = (
        "NEW_BAND = (0.1, 0.0)\n"
        "SEAT_BAND_MM: tuple[float, float] = (0.05, 0.0)\n"
        "LEFT_BAND, RIGHT_BANDS = (0.1, 0.0), ((0.1, 0.0),)\n"
        "if FLAG:\n"
        "    IF_BAND = 0.5\n"
        "try:\n"
        "    TRY_BAND = 0.5\n"
        "except ImportError:\n"
        "    EXCEPT_BAND = 0.5\n"
        "BANDWIDTH = 3\n"
        "band_local = (0.1, 0.0)\n"
        "def build():\n"
        "    LOCAL_BAND = (0.1, 0.0)\n"
    )
    assert _band_names_in(ast.parse(source)) == [
        "NEW_BAND",
        "SEAT_BAND_MM",
        "LEFT_BAND",
        "RIGHT_BANDS",
        "IF_BAND",
        "TRY_BAND",
        "EXCEPT_BAND",
    ]


@pytest.mark.parametrize(
    "value",
    [0.0, -0.1, math.nan, math.inf, {"a": (0.1, 0.0)}, [0.1, 0.0], (0.1, 0.0)],
    ids=["zero", "negative", "nan", "inf", "dict", "list", "unread-tuple"],
)
def test_inventory_rejects_a_planted_bad_band(value: Any) -> None:
    assert _inventory_problems([("planted", "NEW_BAND", value)], checked=set())


def test_inventory_accepts_a_planted_good_band() -> None:
    read = (0.1, 0.0)
    entries = [("planted", "HALF_BAND", 0.5), ("planted", "READ_BAND", read)]
    assert not _inventory_problems(entries, checked={id(read)})


# _holes.wizard_holes(dia_tolerance_mm=(minus, plus)) writes unsigned magnitudes,
# minus first, straight into SetValues: a third ordering that no band check sees.
# Nothing passes it, and the parameter is due for deletion.
_UNCHECKED_TOLERANCE_KEYWORDS = {"dia_tolerance_mm"}


def _unchecked_tolerance_uses(tree: ast.AST, module: str) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            passes_value = keyword.arg in _UNCHECKED_TOLERANCE_KEYWORDS and not (
                isinstance(keyword.value, ast.Constant) and keyword.value.value is None
            )
            # **kwargs into the hole wizard could carry it unseen.
            hides_it = keyword.arg is None and _call_name(node) == "wizard_holes"
            if passes_value or hides_it:
                found.append(f"{module}:{node.lineno} {ast.unparse(node)}")
    return found


def test_no_script_uses_the_unchecked_hole_tolerance() -> None:
    uses = [
        use for stem, tree in SCRIPT_TREES for use in _unchecked_tolerance_uses(tree, stem)
    ]
    assert not uses, (
        "dia_tolerance_mm takes unsigned (minus, plus) magnitudes that no band "
        "check sees; route the fit through deviations() or delete the path: "
        + "; ".join(uses)
    )


@pytest.mark.parametrize(
    "call",
    [
        "wizard_holes(a, spec, pts, n, 'h', dia_tolerance_mm=(0.0, 0.05))",
        "wizard_holes(a, spec, pts, n, 'h', dia_tolerance_mm=BAND)",
        "wizard_holes(a, spec, pts, n, 'h', **options)",
    ],
    ids=["tuple", "name", "kwargs"],
)
def test_hole_tolerance_tripwire_rejects_a_use(call: str) -> None:
    assert _unchecked_tolerance_uses(ast.parse(call), "planted")


def test_hole_tolerance_tripwire_accepts_none() -> None:
    call = "wizard_holes(a, spec, pts, n, 'h', dia_tolerance_mm=None)"
    assert not _unchecked_tolerance_uses(ast.parse(call), "planted")


def _setter_violations(tree: ast.AST, module: str) -> list[str]:
    """Setter calls whose deviation pair does not come from a producer."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name not in _PAIR_SETTERS:
            continue
        pair = node.args[_PAIR_SETTERS[name] :]
        produced = (
            len(pair) == 1
            and not node.keywords
            and isinstance(pair[0], ast.Starred)
            and isinstance(pair[0].value, ast.Call)
            and _call_name(pair[0].value) in _PAIR_PRODUCERS
        )
        if not produced:
            found.append(f"{module}:{node.lineno} {ast.unparse(node)}")
    return found


def test_tolerance_setters_take_pairs_from_deviations() -> None:
    violations = [
        violation
        for stem, tree in SCRIPT_TREES
        if stem != "_drawing_marks"  # the setter's own definition
        for violation in _setter_violations(tree, stem)
    ]
    assert not violations, (
        "pass the setter *deviations(BAND) with BAND written (upper, lower), so "
        "the band is checked the way every other fit is: " + "; ".join(violations)
    )


@pytest.mark.parametrize(
    "call",
    [
        "set_dimension_bilateral_tolerance(a, 'F', 'D', *BAND)",
        "set_dimension_bilateral_tolerance(a, 'F', 'D', 0.0, 0.1)",
        "set_dimension_bilateral_tolerance(a, 'F', 'D', *swap(BAND))",
        "marks.set_dimension_bilateral_tolerance(a, 'F', 'D', *BAND)",
        "set_dimension_bilateral_tolerance(a, 'F', 'D', lower_deviation_mm=0.0, "
        "upper_deviation_mm=0.1)",
    ],
    ids=["raw-splat", "loose-numbers", "other-call", "attribute", "keywords"],
)
def test_setter_rule_rejects_a_raw_pair(call: str) -> None:
    assert _setter_violations(ast.parse(call), "planted")


def test_setter_rule_accepts_deviations() -> None:
    call = "set_dimension_bilateral_tolerance(a, 'F', 'D', *deviations(BAND))"
    assert not _setter_violations(ast.parse(call), "planted")


# Raw access to a band -- X_BAND[i], *X_BAND, or `a, b = X_BAND` -- reads the
# tuple in whatever order the reader assumes, and nothing checks that the band
# still has that order. A flipped band read raw stays silent: normalizing
# TIP_SLOT_W_BAND to (upper, lower) turns cone_swing_platform_spec's
# TIP_SLOT_W_BAND[1] from the 0.10 upper into 0.0. deviations(X_BAND) validates
# the band and returns (lower, upper) whatever it looks like, so
# deviations(X_BAND)[1] is always the upper deviation.
#
# RAW_ACCESS_ALLOWLIST is a ratchet, not a design. Every raw access in the tree
# on 2026-09-25 was audited against its band's order and is listed, keyed by
# (module, source text), with its count and what it reads. A new access fails,
# and so does an entry whose count changed. The listed sites move to
# deviations() and this allowlist is DELETED in the post-release re-key window,
# with the _holes dia_tolerance_mm deletion: rewriting them now would re-key
# every part that imports these specs.
RAW_ACCESS_ALLOWLIST: dict[tuple[str, str], tuple[int, str]] = {
    ("alignment_pinion_spec", "BASE_TANGENT_SPAN_BAND[0]"): (1, "upper, printed"),
    ("alignment_pinion_spec", "BASE_TANGENT_SPAN_BAND[1]"): (1, "lower, printed"),
    ("build_cone_gear", "BORE_DIA_BAND[0]"): (1, "upper: maximum bore"),
    ("build_cone_tip_bushing", "cone_gear_shaft_spec.SECTION_DIA_BANDS[-1]"): (
        1,
        "journal band, unpacked as (upper, lower)",
    ),
    ("build_crank_drive_gear", "cone_gear_shaft_spec.SECTION_DIA_BANDS[1]"): (
        1,
        "land band, unpacked as (upper, lower)",
    ),
    ("build_drive_train_assembly", "CONE_GEAR_BLANK_DIA_BAND[0]"): (
        1,
        "upper: maximum blank OD",
    ),
    ("cone_gear_spec", "TOOTH_THICKNESS_BAND[0]"): (1, "upper; the band is symmetric"),
    ("cone_gear_spec", "BORE_DIA_BAND[0]"): (2, "upper: width check and its message"),
    ("cone_gear_spec", "BORE_DIA_BAND[1]"): (2, "lower: width check and its message"),
    (
        "crank_pinion_spec",
        "_SHAFT_UPPER, _SHAFT_LOWER = crankshaft_spec.SHAFT_DIA_BAND",
    ): (1, "unpacked as (upper, lower)"),
    ("draw_crank_arm", "CRANKSHAFT_DIA_BAND[0]"): (1, "upper: minimum clearance"),
    ("draw_crank_arm", "CRANKSHAFT_DIA_BAND[1]"): (1, "lower: maximum clearance"),
    ("pinion_arbor_collar_spec", "BORE_BAND[0]"): (2, "upper: worst-case walls"),
    ("pinion_arbor_collar_spec", "BORE_BAND[1]"): (1, "lower: minimum clearance"),
    ("pinion_arbor_collar_spec", "SHAFT_DIA_BAND[0]"): (1, "upper: minimum clearance"),
    ("pinion_arbor_pin_spec", "SHAFT_DIA_BAND[1]"): (1, "lower: worst ligament"),
    ("pinion_arbor_spec", "DRUM_LEN_BAND[0]"): (1, "upper: longest drum"),
    ("pinion_arbor_spec", "DRUM_LEN_BAND[1]"): (1, "lower: shortest drum"),
    ("pinion_arbor_spec", "CROSS_HOLE_DIA_BAND[0]"): (
        2,
        "upper: worst web, maximum clearance",
    ),
    ("pinion_arbor_spec", "CROSS_HOLE_DIA_BAND[1]"): (1, "lower: minimum clearance"),
    ("pinion_arbor_spec", "ROD_DIA_BAND[0]"): (1, "upper: minimum clearance"),
    ("pinion_arbor_spec", "ROD_DIA_BAND[1]"): (1, "lower: maximum clearance"),
    ("pinion_bracket_spec", "PIN_SEAT_DIA_BAND[0]"): (1, "upper: largest seat"),
    ("pinion_cam_pin_spec", "SEAT_BAND[0]"): (1, "upper of REAM_H7: maximum clearance"),
    ("pinion_cam_pin_spec", "SEAT_BAND[1]"): (1, "lower of REAM_H7: minimum clearance"),
    ("pinion_cam_pin_spec", "PIN_DIA_BAND[0]"): (1, "upper: minimum clearance"),
    ("pinion_cam_pin_spec", "PIN_DIA_BAND[1]"): (1, "lower: maximum clearance"),
    ("pinion_cam_spec", "BORE_BAND[0]"): (1, "upper: maximum clearance"),
    ("pinion_cam_spec", "BORE_BAND[1]"): (1, "lower: minimum clearance"),
    ("pinion_cam_spec", "LIFT_ROD_DIA_BAND[0]"): (1, "upper: minimum clearance"),
    ("pinion_cam_spec", "LIFT_ROD_DIA_BAND[1]"): (1, "lower: maximum clearance"),
    ("pinion_strap_pin_spec", "HOLE_BAND[0]"): (1, "upper: largest hole"),
}

# A raw access that is wrong, or about to be, on this integration head. swing's
# I31 plate commit (#830) reads TIP_SLOT_W_BAND through deviations() as it flips
# the band to (upper, lower); that removes the site, and this entry with it.
_XFAIL_TIP_SLOT_READ = pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "TIP_SLOT_W_BAND[1] is the upper only while the band is (lower, upper); "
        "swing's I31 plate commit (#830) reads it through deviations() and "
        "removes this xfail."
    ),
)
KNOWN_BAD_ACCESS: dict[str, pytest.MarkDecorator] = {
    "cone_swing_platform_spec:TIP_SLOT_W_BAND[1]": _XFAIL_TIP_SLOT_READ,
}

# NOT_FIT_BANDS are (low, high) intervals, not deviations; indexing them is how
# they are used.
_INTERVAL_BANDS = {name for _module, name in NOT_FIT_BANDS}


def _band_ref(node: ast.expr) -> str | None:
    """The band a Name or attribute refers to, unless it is an interval."""
    if isinstance(node, ast.Name):
        name = node.id
    elif isinstance(node, ast.Attribute):
        name = node.attr
    else:
        return None
    if not _is_band_name(name) or name in _INTERVAL_BANDS:
        return None
    return name


def _is_unpack(target: ast.expr) -> bool:
    return isinstance(target, (ast.Tuple, ast.List))


def _raw_band_access_in(tree: ast.AST) -> list[str]:
    """Source text of every raw read of a band in ``tree``."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Subscript, ast.Starred)) and _band_ref(node.value):
            found.append(ast.unparse(node))
        elif (
            isinstance(node, ast.Assign)
            and any(_is_unpack(target) for target in node.targets)
            and _band_ref(node.value)
        ):
            found.append(ast.unparse(node))
        elif (
            isinstance(node, (ast.For, ast.comprehension))
            and _is_unpack(node.target)
            and _band_ref(node.iter)
        ):
            found.append(f"for {ast.unparse(node.target)} in {ast.unparse(node.iter)}")
    return found


RAW_ACCESS: Counter[tuple[str, str]] = Counter(
    (stem, text)
    for stem, tree in SCRIPT_TREES
    if stem != "_fit_limits"
    for text in _raw_band_access_in(tree)
)


def _raw_access_cases() -> list[Any]:
    params = []
    for (module, text), count in sorted(RAW_ACCESS.items()):
        case_id = f"{module}:{text}"
        marks = [KNOWN_BAD_ACCESS[case_id]] if case_id in KNOWN_BAD_ACCESS else []
        params.append(pytest.param(module, text, count, id=case_id, marks=marks))
    return params


@pytest.mark.parametrize(("module", "text", "count"), _raw_access_cases())
def test_no_raw_band_access(module: str, text: str, count: int) -> None:
    allowed = RAW_ACCESS_ALLOWLIST.get((module, text))
    assert allowed is not None, (
        f"{module}: raw band access {text!r}. Read the band through "
        "deviations(), which returns (lower, upper) whatever the band's order."
    )
    assert count <= allowed[0], (
        f"{module}: {text!r} occurs {count} times, {allowed[0]} audited; read the "
        "new ones through deviations()"
    )


def test_raw_access_allowlist_is_current() -> None:
    # The ratchet only turns one way: a migrated site must leave the list.
    stale = {
        key: (allowed, RAW_ACCESS.get(key, 0))
        for key, (allowed, _reads) in RAW_ACCESS_ALLOWLIST.items()
        if RAW_ACCESS.get(key, 0) != allowed
    }
    assert not stale, f"update the audited counts, (listed, found): {stale}"


def test_known_bad_access_ids_are_live() -> None:
    ids = {f"{module}:{text}" for module, text in RAW_ACCESS}
    assert set(KNOWN_BAD_ACCESS) <= ids, set(KNOWN_BAD_ACCESS) - ids
    listed = {f"{module}:{text}" for module, text in RAW_ACCESS_ALLOWLIST}
    assert not set(KNOWN_BAD_ACCESS) & listed


@pytest.mark.parametrize(
    "source",
    [
        "x = X_BAND[0]",
        "x = X_BAND_MM[i]",
        "x = spec.X_BANDS[1]",
        "f(*X_BAND)",
        "lower, upper = X_BAND",
        "[lower, upper] = spec.X_BAND",
        "for upper, lower in X_BANDS:\n    pass",
        "y = [u - l for u, l in X_BANDS]",
    ],
    ids=[
        "index",
        "index-mm",
        "attribute",
        "splat",
        "unpack",
        "unpack-attribute",
        "for-unpack",
        "comprehension",
    ],
)
def test_raw_access_rule_catches_a_planted_read(source: str) -> None:
    assert _raw_band_access_in(ast.parse(source))


@pytest.mark.parametrize(
    "source",
    [
        "x = deviations(X_BAND)[1]",
        "lower, upper = deviations(X_BAND)",
        "f(*deviations(X_BAND))",
        "for band in X_BANDS:\n    deviations(band)",
        "x = X_BAND",
        "x = _G64_BAND[0]",
    ],
    ids=[
        "deviations-index",
        "deviations-unpack",
        "deviations-splat",
        "loop",
        "alias",
        "interval",
    ],
)
def test_raw_access_rule_passes_the_checked_path(source: str) -> None:
    assert not _raw_band_access_in(ast.parse(source))
