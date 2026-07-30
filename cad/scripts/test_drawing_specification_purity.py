from __future__ import annotations

from pathlib import Path

import pytest

from _drawing_contract import (
    drawing_fleet_specification_violations,
    drawing_specification_violations,
)


def _rules(source: str) -> list[str]:
    return [item.rule for item in drawing_specification_violations(source)]


@pytest.mark.parametrize(
    "value",
    (
        '"+0.00/-0.02"',
        '"±0.05"',
        '"Ra 1.6"',
        '"R0.10 MAX"',
        '"3.00 MIN"',
        '"6.375 MAX / 6.360 MIN"',
        'f"{upper:.3f} MAX / {lower:.3f} MIN"',
        'f"Ra {local_grade}"',
    ),
)
def test_detector_finds_frozen_manufacturing_string_fragments(value: str) -> None:
    assert "drawing-spec-string" in _rules(f"CALLOUT = {value}\n")


def test_detector_finds_fit_renderers_through_import_aliases() -> None:
    source = """
from _fit_limits import fit_limits as limits
import _fit_limits as bands

FIRST = limits(6.0, (-0.1, 0.1))
SECOND = bands.band_text((-0.1, 0.1))
"""
    assert _rules(source) == [
        "drawing-tolerance-renderer",
        "drawing-tolerance-renderer",
    ]


def test_detector_rejects_literal_and_local_surface_finish_grades() -> None:
    source = """
from _drawing_common import add_surface_finish as finish

LOCAL_GRADE = "1.6"
finish(adapter, view, symbol_xy=(0.1, 0.2), roughness_ra="0.8", label="first")
finish(adapter, view, symbol_xy=(0.2, 0.2), roughness_ra=LOCAL_GRADE, label="second")
"""
    assert _rules(source).count("drawing-roughness-provenance") == 2


def test_detector_allows_catalog_surface_finish_grades_and_local_aliases() -> None:
    source = """
from _drawing_common import add_surface_finish
from _surface_finish import MACHINED as CATALOG_GRADE
import _surface_finish as finish_catalog

LOCAL_ALIAS = CATALOG_GRADE
PLACEMENT = (0.125, 0.240, 2.0)
PROPERTY = '$PRPSHEET:"SurfaceFinish"'
PROSE = "REPORT MAX-MIN RADIAL WALL THICKNESS"
TEXT = f"Ra {CATALOG_GRADE}"

add_surface_finish(
    adapter,
    view,
    symbol_xy=PLACEMENT[:2],
    roughness_ra=LOCAL_ALIAS,
    label="catalog direct",
)
add_surface_finish(
    adapter,
    view,
    symbol_xy=PLACEMENT[:2],
    roughness_ra=finish_catalog.GROUND,
    label="catalog module",
)
"""
    assert drawing_specification_violations(source) == ()


def test_detector_finds_direct_drawing_com_tolerance_mutation() -> None:
    source = """
model_dimension.SetToleranceType(2)
tolerance = _early_bound(model_dimension.Tolerance, "IDimensionTolerance")
tolerance.Type = 2
tolerance.SetValues(-0.00005, 0.00005)
series.SetValues(1.0, 2.0)
"""
    assert _rules(source) == [
        "drawing-tolerance-mutation",
        "drawing-tolerance-mutation",
        "drawing-tolerance-mutation",
    ]


def test_detector_ignores_docstrings_property_links_placement_and_prose() -> None:
    source = '''
"""Examples such as Ra 1.6 and +0.00/-0.02 are documentation only."""

VIEW_XY = (0.130, 0.170)
SCALE = (2, 1)
PROPERTY = '$PRPSHEET:"ToleranceCallout"'
NOTE = "KEEP MAX-MIN RESULTS WITH THE INSPECTION REPORT"
'''
    assert drawing_specification_violations(source) == ()


def test_drawing_fleet_owns_placement_not_manufacturing_values() -> None:
    scripts = Path(__file__).parent.glob("draw_*.py")
    violations = drawing_fleet_specification_violations(scripts)
    assert not violations, "drawing-owned manufacturing specifications:\n" + "\n".join(
        str(item) for item in violations
    )
