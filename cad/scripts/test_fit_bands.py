"""Every fit band a build script hands to SolidWorks is valid at import time.

A band only reaches ``_fit_limits.deviations`` (or the bilateral setter) inside
``build()``, which needs a SolidWorks seat. So an inverted or zero-width band
used to pass the whole offline suite and fail its farm leaf instead: warm-c486
lost ``part:crank_drive_gear`` to "fit band is inverted: (0.025, 0.025)" at
``build_crank_drive_gear.build()`` -> ``deviations(BORE_DIA_BAND)``.

This file finds every band consumer by reading the scripts' source, resolves each
argument in the imported module (the value ``build()`` would see), and applies
the same checks ``build()`` would:

* ``deviations(band)`` / ``fit_limits(nominal, band)`` / ``band_text(band)`` take
  ``(upper, lower)``; the helper must accept it and return lower < upper.
* ``set_dimension_bilateral_tolerance(..., *BAND)`` splats ``(lower, upper)``
  straight into the setter, which refuses lower >= upper.

A second test inventories every module-level ``*_BAND`` / ``*_BANDS`` /
``*_BAND_MM`` tuple in the ``build_*``, ``*_spec``, ``*_geometry`` and ``*_geom``
modules. Each must be fed to a checked consumer, be listed in
``INDEXED_FIT_BANDS`` (a fit band read by index, checked the same way), or be
listed in ``NOT_FIT_BANDS`` with the reason it is not a fit.
"""

from __future__ import annotations

import ast
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import _fit_limits

SCRIPTS = Path(__file__).resolve().parent

# Helpers that take an (upper, lower) band, and the positional index of the band.
_BAND_HELPERS = {"deviations": 0, "band_text": 0, "fit_limits": 1}
_SETTER = "set_dimension_bilateral_tolerance"

# A consumer whose argument is a name local to build() (so it cannot be read off
# the imported module) must say here which module-level value build() derives it
# from. "each" means build() loops over the tuple of bands.
LOCAL_BAND_SOURCES: dict[tuple[str, str], tuple[str, str]] = {
    # for section, band in enumerate(SECTION_DIA_BANDS): ... deviations(band)
    ("build_cone_gear_shaft", "band"): ("SECTION_DIA_BANDS", "each"),
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
    order: str  # "upper_lower" (helpers) or "lower_upper" (setter splat)


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _band_uses() -> list[BandUse]:
    uses: list[BandUse] = []
    for path in sorted(SCRIPTS.glob("*.py")):
        if path.name.startswith("test_") or path.name == "_fit_limits.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name in _BAND_HELPERS:
                index = _BAND_HELPERS[name]
                if len(node.args) > index:
                    arg = node.args[index]
                    uses.append(
                        BandUse(path.stem, node.lineno, ast.unparse(arg), "upper_lower")
                    )
            elif name == _SETTER:
                # A splat that is not itself a helper call hands the setter a
                # raw (lower, upper) pair.
                for arg in node.args:
                    if isinstance(arg, ast.Starred) and not isinstance(
                        arg.value, ast.Call
                    ):
                        uses.append(
                            BandUse(
                                path.stem,
                                node.lineno,
                                ast.unparse(arg.value),
                                "lower_upper",
                            )
                        )
    return uses


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


def _check_band(label: str, band: Any, order: str) -> None:
    assert isinstance(band, tuple) and len(band) == 2, f"{label}: not a 2-tuple: {band!r}"
    assert all(isinstance(v, (int, float)) for v in band), f"{label}: {band!r}"
    if order == "upper_lower":
        # Exactly what build() does; raises on an inverted or zero-width band.
        lower, upper = _fit_limits.deviations(band)
    else:
        lower, upper = band
    assert lower < upper, f"{label}: lower {lower} >= upper {upper} ({order})"
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
    helpers = [u for u in BAND_USES if u.order == "upper_lower"]
    assert len(helpers) >= 50, len(helpers)
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
        _check_band(f"{use.module}:{use.line} {label}", band, use.order)


def _inventory() -> list[tuple[str, str]]:
    """(module, name) of every module-level *_BAND / *_BANDS / *_BAND_MM
    assignment whose value is a tuple, in the band-owning module families."""
    found: list[tuple[str, str]] = []
    for path in sorted(SCRIPTS.glob("*.py")):
        stem = path.stem
        if not (
            stem.startswith("build_")
            or stem.endswith(("_spec", "_geometry", "_geom"))
        ):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
                if isinstance(node, ast.AnnAssign)
                else []
            )
            for target in targets:
                if isinstance(target, ast.Name) and target.id.endswith(
                    ("_BAND", "_BANDS", "_BAND_MM")
                ):
                    found.append((stem, target.id))
    return found


def test_every_band_tuple_is_checked_or_classified() -> None:
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
    unclassified = []
    for module_name, name in _inventory():
        value = getattr(importlib.import_module(module_name), name)
        if not isinstance(value, tuple):
            continue  # a scalar .X/.XX half-width, not a two-sided band
        key = (module_name, name)
        if id(value) in checked or key in NOT_FIT_BANDS or key in INDEXED_FIT_BANDS:
            continue
        unclassified.append(f"{module_name}.{name} = {value!r}")
    assert not unclassified, (
        "band tuples that no checked consumer reads; feed them through "
        "_fit_limits.deviations or list them in NOT_FIT_BANDS with a reason: "
        + "; ".join(unclassified)
    )


@pytest.mark.parametrize(
    ("module_name", "name"),
    sorted(INDEXED_FIT_BANDS),
    ids=[f"{m}:{n}" for m, n in sorted(INDEXED_FIT_BANDS)],
)
def test_indexed_fit_bands_are_valid(module_name: str, name: str) -> None:
    band = getattr(importlib.import_module(module_name), name)
    _check_band(f"{module_name}.{name}", band, "upper_lower")


def test_classification_lists_are_current() -> None:
    inventory = set(_inventory())
    for listing in (NOT_FIT_BANDS, INDEXED_FIT_BANDS):
        stale = set(listing) - inventory
        assert not stale, f"listed constants that are gone: {sorted(stale)}"
    assert not set(NOT_FIT_BANDS) & set(INDEXED_FIT_BANDS)


@pytest.mark.parametrize(
    ("band", "order"),
    [
        ((0.025, 0.025), "upper_lower"),  # the warm-c486 crank_drive_gear band
        ((0.010, 0.050), "upper_lower"),
        ((0.050, 0.010), "lower_upper"),
        ((0.020, 0.020), "lower_upper"),
    ],
)
def test_check_band_rejects_inverted_and_zero_width_bands(
    band: tuple[float, float], order: str
) -> None:
    # The guard must fail on the shapes it exists to catch, in both argument
    # orders, or every parametrized case above passes vacuously.
    with pytest.raises((AssertionError, ValueError)):
        _check_band("synthetic", band, order)
