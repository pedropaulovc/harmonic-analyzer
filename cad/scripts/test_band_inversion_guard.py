"""Every module-level tolerance band is well-formed before any build runs it.

A band is only *evaluated* where a build uses it: ``_fit_limits.deviations``
raises on an inverted ``(upper, lower)`` band inside ``build()``, which only
the SolidWorks leaf reaches.  So an input edit that collapses a DERIVED band
passed the whole offline suite and failed on the farm instead (warm-c486,
``part:crank_drive_gear``: ``fit band is inverted: (0.025, 0.025)``, the
``shaft_in_bushing`` running fit applied to MHA-014's 0.05-wide land).

This test finds every band constant a build module defines or re-exports at
module level and checks it offline, the way its consumer will:

* ``(upper, lower)`` deviations -- the default for a 2-tuple, the convention
  ``_fit_limits`` documents -- must pass ``deviations`` (upper > lower);
* a scalar is a symmetric half-width (the ``.X`` / ``.XX`` title-block rows)
  and must be positive;
* a tuple of bands or a dict of bands is checked member by member;
* the few bands in another convention are named in :data:`BAND_KIND` with
  the consumer that fixes their order.

A shape no rule covers fails, so a new band convention has to be classified
here rather than slipping past.  A module that cannot be imported offline
must be listed in :data:`UNIMPORTABLE` with its reason; none is skipped
silently.
"""

from __future__ import annotations

import ast
import importlib
import math
from pathlib import Path

import pytest

from _fit_limits import deviations

SCRIPTS = Path(__file__).resolve().parent

# Build-side modules whose module-level constants feed build().  Any other
# script that DEFINES a band at module level is scanned too, unless it is
# listed in OUT_OF_SCOPE, so a band moved into a new helper module (a
# ``*_bands.py``) stays covered without editing this list.
MODULE_GLOBS = ("build_*.py", "*_spec.py", "*_geometry.py", "*_geom.py")

OUT_OF_SCOPE = {
    "verify": "_COMPONENT_BAND is the retired component-count gate's reference "
    "data (component counts per assembly), not a size tolerance",
}

# Modules that cannot be imported without SolidWorks, with the reason.  Each
# entry is re-checked: an entry that imports cleanly again must be removed.
UNIMPORTABLE: dict[str, str] = {}

BAND_WORDS = {"BAND", "BANDS"}

# Bands whose order is NOT the (upper, lower) deviation default, keyed by
# constant name, with the consumer that fixes the convention.
BAND_KIND = {
    # (lower, upper) deviations splatted straight into
    # _drawing_marks.set_dimension_bilateral_tolerance, which takes
    # (lower_deviation_mm, upper_deviation_mm).
    "TIP_SLOT_W_BAND": "lower_upper",
    "SPOTFACE_DEPTH_BAND_MM": "lower_upper",
    # (low, high) world-z coordinate intervals the drive-train clearance
    # asserts intersect against, not deviations about a nominal.
    "ARBOR_PED_SOUTH_Z_BAND": "interval",
    "ARBOR_PED_NORTH_Z_BAND": "interval",
    "_G64_BAND": "interval",
    # ((low, high) interval, minimum gap) pairs.
    "_ARB_Z_BANDS": "interval_gap",
}

# Bands known to be broken on this integration head, each removed by the fix
# it names.  strict: the entry fails the suite the moment the band is fixed.
KNOWN_BROKEN = {
    "build_crank_drive_gear.BORE_DIA_BAND": (
        "zero-width (+0.025/+0.025): shaft_in_bushing on the 0.05 gear-seat land; "
        "crankhub's 64T fix (integ/64t-bore-resolve) re-derives it from the "
        "retained-joint fit and removes this entry"
    ),
}


def _is_band_name(name: str) -> bool:
    return name.isupper() and not BAND_WORDS.isdisjoint(name.split("_"))


def _top_level_statements(body: list[ast.stmt]):
    """Module-level statements, descending into if/try blocks but never into
    a function or class body."""
    for node in body:
        yield node
        if isinstance(node, ast.If):
            yield from _top_level_statements(node.body)
            yield from _top_level_statements(node.orelse)
        if isinstance(node, ast.Try):
            for block in (node.body, node.orelse, node.finalbody):
                yield from _top_level_statements(block)
            for handler in node.handlers:
                yield from _top_level_statements(handler.body)


def _assigned_names(target: ast.expr):
    if isinstance(target, ast.Name):
        yield target.id
    if isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            yield from _assigned_names(element)


def _band_names(path: Path) -> tuple[set[str], set[str]]:
    """(defined, imported) module-level band names in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    defined: set[str] = set()
    imported: set[str] = set()
    for node in _top_level_statements(tree.body):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                defined.update(n for n in _assigned_names(target) if _is_band_name(n))
        if isinstance(node, ast.AnnAssign) and node.value is not None:
            defined.update(n for n in _assigned_names(node.target) if _is_band_name(n))
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                if _is_band_name(name):
                    imported.add(name)
    return defined, imported


def _scripts() -> list[Path]:
    return sorted(p for p in SCRIPTS.glob("*.py") if not p.name.startswith("test_"))


def _scanned_modules() -> dict[str, set[str]]:
    """Module stem -> every band name it defines or re-exports."""
    in_glob = {p.stem for pattern in MODULE_GLOBS for p in SCRIPTS.glob(pattern)}
    scanned: dict[str, set[str]] = {}
    for path in _scripts():
        defined, imported = _band_names(path)
        if path.stem in OUT_OF_SCOPE:
            continue
        if path.stem not in in_glob and not defined:
            continue
        if defined or imported:
            scanned[path.stem] = defined | imported
    return scanned


SCANNED = _scanned_modules()
CASES = sorted(f"{module}.{name}" for module, names in SCANNED.items() for name in names)


def _import(module: str):
    if module in UNIMPORTABLE:
        pytest.skip(f"{module} cannot import offline: {UNIMPORTABLE[module]}")
    return importlib.import_module(module)


def _check_deviation(band) -> None:
    upper, lower = band
    assert math.isfinite(upper) and math.isfinite(lower), band
    assert lower < upper, f"(upper, lower) band is inverted or zero-width: {band!r}"
    assert upper - lower > 0.0, band
    assert deviations(band) == (lower, upper)


def _check_lower_upper(band) -> None:
    lower, upper = band
    assert math.isfinite(lower) and math.isfinite(upper), band
    assert lower < upper, f"(lower, upper) band is inverted or zero-width: {band!r}"
    # The same band in the (upper, lower) order deviations() takes.
    assert deviations((upper, lower)) == (lower, upper)


def _check_interval(band) -> None:
    low, high = band
    assert math.isfinite(low) and math.isfinite(high), band
    assert low < high, f"(low, high) interval is inverted or empty: {band!r}"


def _check_half_width(band) -> None:
    assert math.isfinite(band) and band > 0.0, f"half-width band must be positive: {band!r}"


def _is_pair(value) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)
    )


def _check_band(name: str, value) -> None:
    kind = BAND_KIND.get(name, "default")
    if kind == "lower_upper":
        _check_lower_upper(value)
        return
    if kind == "interval":
        _check_interval(value)
        return
    if kind == "interval_gap":
        assert value, name
        for interval, gap in value:
            _check_interval(interval)
            _check_half_width(gap)
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        _check_half_width(value)
        return
    if _is_pair(value):
        _check_deviation(value)
        return
    members = list(value.values()) if isinstance(value, dict) else value
    if isinstance(members, (tuple, list)) and members and all(map(_is_pair, members)):
        for member in members:
            _check_deviation(member)
        return
    pytest.fail(f"{name} = {value!r}: unclassified band shape; add it to BAND_KIND")


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(case, marks=pytest.mark.xfail(reason=KNOWN_BROKEN[case], strict=True))
        if case in KNOWN_BROKEN
        else case
        for case in CASES
    ],
)
def test_module_level_band_is_well_formed(case: str) -> None:
    module, name = case.rsplit(".", 1)
    _check_band(name, getattr(_import(module), name))


def test_scan_covers_the_build_modules() -> None:
    # The derived band that broke on the farm, a spec band, a tuple of bands
    # and a band living outside the build globs' own names must all be found.
    assert "build_crank_drive_gear.BORE_DIA_BAND" in CASES
    assert "cone_gear_shaft_spec.SECTION_DIA_BANDS" in CASES
    assert "harmonic_base_spec.SPOTFACE_DEPTH_BAND_MM" in CASES
    assert len(CASES) > 100


def test_classification_tables_name_live_constants() -> None:
    names = {name for names in SCANNED.values() for name in names}
    assert set(BAND_KIND) <= names, set(BAND_KIND) - names
    assert set(KNOWN_BROKEN) <= set(CASES), set(KNOWN_BROKEN) - set(CASES)
    assert set(OUT_OF_SCOPE) <= {p.stem for p in _scripts()}


def test_unimportable_modules_still_fail_to_import() -> None:
    for module in UNIMPORTABLE:
        with pytest.raises(Exception):
            importlib.import_module(module)


def _splatted_band_names(path: Path):
    """Band names splatted straight into set_dimension_bilateral_tolerance."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if called != "set_dimension_bilateral_tolerance":
            continue
        for arg in node.args:
            if not isinstance(arg, ast.Starred):
                continue
            value = arg.value
            name = value.attr if isinstance(value, ast.Attribute) else getattr(value, "id", "")
            if _is_band_name(name):
                yield name


def test_raw_setter_splats_are_lower_upper_bands() -> None:
    # The setter takes (lower, upper).  Splatting an (upper, lower) band into
    # it without deviations() silently swaps the limits, so a raw splat is
    # only legal for a band declared lower_upper above.
    offenders = sorted(
        f"{path.name}: *{name}"
        for path in _scripts()
        for name in _splatted_band_names(path)
        if BAND_KIND.get(name) != "lower_upper"
    )
    assert not offenders, offenders
