from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from _drawing_contract import (
    drawing_fleet_specification_violations,
    drawing_specification_violations,
    model_toleranced_dimensions,
)


def _rules(source: str) -> list[str]:
    return [item.rule for item in drawing_specification_violations(source)]


@pytest.mark.parametrize(
    "value",
    (
        '"+0.00/-0.02"',
        '"+0.10/0"',
        '"+0.10/+0.00"',
        '"-0.02/-0.04"',
        '"+0.04/+0.02"',
        '"-0.02/+0.04"',
        '"+ 0.04 / + 0.02"',
        '"0/-0.10"',
        '"+0.00/-0.10"',
        '"±0.05"',
        '"Ra 1.6"',
        '"R0.10 MAX"',
        '"3.00 MIN"',
        '"6.375 MAX / 6.360 MIN"',
        'f"{upper:.3f} MAX / {lower:.3f} MIN"',
        'f"{upper:+.2f}/{lower:+.2f}"',
        'f"{upper:>+.3f} / {lower:*>+8.3f}"',
        'f"{upper:-.2f}/{lower:-.2f}"',
        'f"Ra {local_grade}"',
    ),
)
def test_detector_finds_frozen_manufacturing_string_fragments(value: str) -> None:
    assert "drawing-spec-string" in _rules(f"CALLOUT = {value}\n")


def test_detector_preserves_f_string_signs_in_violation_evidence() -> None:
    violations = drawing_specification_violations(
        'CALLOUT = f"{upper:+.2f}/{lower:+.2f}"\n'
    )
    assert len(violations) == 1
    assert violations[0].rule == "drawing-spec-string"
    assert violations[0].evidence == "'+{...}/+{...}'"


@pytest.mark.parametrize(
    "value",
    (
        'f"{numerator:.2f}/{denominator:.2f}"',
        'f"{month:02d}/{day:02d}"',
        'f"{value:+.2f}"',
        'f"{width:+.2f} BY {height:+.2f}"',
    ),
)
def test_detector_does_not_treat_unbanded_f_strings_as_tolerances(value: str) -> None:
    assert drawing_specification_violations(f"LABEL = {value}\n") == ()


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


def test_detector_requires_surface_finish_controls_from_a_part_spec() -> None:
    local_control = """
from _drawing_common import add_surface_finish
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

add_surface_finish(
    adapter,
    view,
    symbol_xy=(0.1, 0.2),
    control=SurfaceFinishControl(
        "strap_bore", MACHINED_UM, CylinderFace(30.8)
    ),
    label="local control",
)
"""
    assert _rules(local_control) == ["drawing-surface-finish-provenance"]

    imported_controls = """
from _drawing_common import add_surface_finish
from _surface_finish import surface_finish_by_key
from connecting_rod_spec import SURFACE_FINISHES
import connecting_rod_spec as rod_spec
import _surface_finish as finish_catalog

CONTROL = surface_finish_by_key(SURFACE_FINISHES, "strap_bore")
add_surface_finish(
    adapter, view, symbol_xy=(0.1, 0.2), control=CONTROL, label="direct spec"
)
add_surface_finish(
    adapter,
    view,
    symbol_xy=(0.2, 0.2),
    control=finish_catalog.surface_finish_by_key(
        rod_spec.SURFACE_FINISHES, "strap_bore"
    ),
    label="module spec",
)
"""
    assert drawing_specification_violations(imported_controls) == ()


def test_detector_finds_direct_drawing_com_tolerance_mutation() -> None:
    source = """
model_dimension.SetToleranceType(2)
tolerance = _early_bound(model_dimension.Tolerance, "IDimensionTolerance")
tolerance.Type = 2
tolerance.SetValues(-0.00005, 0.00005)
set_dimension_symmetric_angular_tolerance(adapter, "Chamfer", "Angle", 0.5)
series.SetValues(1.0, 2.0)
"""
    assert _rules(source) == [
        "drawing-tolerance-mutation",
        "drawing-tolerance-mutation",
        "drawing-tolerance-mutation",
        "drawing-tolerance-mutation",
    ]


def test_model_tolerance_analysis_includes_symmetric_angular_setter(
    tmp_path: Path,
) -> None:
    source = tmp_path / "build_sample.py"
    source.write_text(
        'set_dimension_symmetric_angular_tolerance('
        'adapter, "Chamfer", "Angle", ANGULAR_TOLERANCE_MM)\n',
        encoding="utf-8",
    )
    module = SimpleNamespace(__file__=source)
    assert model_toleranced_dimensions(module) == {
        ("Chamfer", "Angle"): "ANGULAR_TOLERANCE_MM"
    }


def test_detector_ignores_docstrings_property_links_placement_and_prose() -> None:
    source = '''
"""Examples such as Ra 1.6 and +0.00/-0.02 are documentation only."""

VIEW_XY = (0.130, 0.170)
SCALE = (2, 1)
PROPERTY = '$PRPSHEET:"ToleranceCallout"'
NOTE = "KEEP MAX-MIN RESULTS WITH THE INSPECTION REPORT"
RATIO = "12/24"
THREAD = "1/4-20 UNC"
'''
    assert drawing_specification_violations(source) == ()


def test_drawing_fleet_owns_placement_not_manufacturing_values() -> None:
    scripts = Path(__file__).parent.glob("draw_*.py")
    violations = drawing_fleet_specification_violations(scripts)
    assert not violations, "drawing-owned manufacturing specifications:\n" + "\n".join(
        str(item) for item in violations
    )
