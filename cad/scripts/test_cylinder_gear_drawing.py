"""Finished-fit and tooth-system contracts consumed by the native drawing."""

from __future__ import annotations

import runpy
from collections import Counter
from pathlib import Path

import pytest

import _config
from _buildgraph import module_deps_of
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from build_cone_gear import gear_facts
import build_cylinder_gear as part
import cylinder_gear_shaft_spec as arbor
import cylinder_gear_spec as spec
import draw_cylinder_gear as drawing


def test_running_bore_limits_follow_the_finished_arbor() -> None:
    # Opposite ends of the arbor size band must not receive one fixed bore band.
    assert spec.matched_bore_limits(9.505) == pytest.approx((9.535, 9.575))
    assert spec.matched_bore_limits(9.525) == pytest.approx((9.555, 9.595))


def test_native_bore_represents_a_finished_running_fit() -> None:
    # Equal nominal bore/arbor diameters previously modeled zero clearance,
    # even though the drawing required a positive matched running clearance.
    minimum, maximum = spec.matched_bore_limits(arbor.SHAFT_DIA)
    assert minimum <= spec.BORE_DIA <= maximum
    assert spec.BORE_DIA - arbor.SHAFT_DIA == pytest.approx(0.050)


def test_blank_and_tooth_profile_follow_the_same_configured_pitch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_pitch = 40.0  # Deliberately differs from the current machine setting.
    original_machine = _config.machine

    def machine_value(*keys: str):
        if keys == ("gear_train", "diametral_pitch"):
            return configured_pitch
        return original_machine(*keys)

    monkeypatch.setattr(_config, "machine", machine_value)
    dimensions = runpy.run_path(spec.__file__)
    profile = gear_facts(dimensions["TEETH"], configured_pitch)
    assert dimensions["OUTSIDE_DIA"] / 2.0 == pytest.approx(profile["Ra"] * 25.4)


def test_every_marked_dimension_has_exactly_one_view_owner() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    ownership = Counter(
        name
        for view_dimensions in (
            drawing.FRONT_KEEP,
            drawing.RIGHT_KEEP,
            drawing.NOTCH_DETAIL_DIMENSIONS,
        )
        for name in view_dimensions
    )
    assert ownership == Counter(marked)
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_the_part_owns_every_printed_decimal_place() -> None:
    """Policy rule 2: places are the tolerance, so the .SLDPRT carries them.

    Three places only where a three-place band rides the dimension (the
    matched bore's reference nominal, the cam eccentricity); the overall is
    the one sheet-derived value, a parenthesised reference.
    """
    by_name = spec.DRAWING_PRECISION_BY_NAME
    assert set(by_name) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert {name for name, places in by_name.items() if places == 3} == {
        "BoreDia",
        "CamCy",
    }
    assert spec.DRAWING_REFERENCE_PRECISION == {"overall axial thickness": 1}
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in part_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # The sheet reads the places back and never rewrites them.
    assert "set_dimension_precision" not in source
    assert "assert_imported_precision(" in source
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


@pytest.mark.parametrize(
    "assembly_script",
    (
        "build_channel_assembly.py",
        "build_drive_train_assembly.py",
        "build_paper_drive_assembly.py",
    ),
)
def test_assembly_recipes_exclude_cylinder_drawing_prose(assembly_script: str) -> None:
    dependencies = {
        Path(path).name
        for path in module_deps_of(Path(__file__).with_name(assembly_script))
    }
    assert "cylinder_gear_spec.py" in dependencies
    assert dependencies.isdisjoint({"build_cylinder_gear.py", "cylinder_gear_notes.py"})
