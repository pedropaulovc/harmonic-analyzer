"""A unit literal's global is read back against its intended value, and every
part gets eight angular and eight linear places at creation (issue #889).
SolidWorks-free."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from _dimensions import set_global
from _document_units import apply_package_model_units, keep_equation_places_exact

_SW_MM, _SW_INCHES, _SW_FEET_INCHES = 0, 3, 5
_SW_DEGREES, _SW_RADIANS = 0, 3


class _Extension:
    """Document preferences: unit codes answer reads, writes are logged."""

    def __init__(self, linear: int = _SW_INCHES, angular: int = _SW_DEGREES) -> None:
        # A template's places: two angular, three linear.
        self.values = {47: linear, 49: 3, 51: angular, 52: 2}
        self.writes: list[tuple[int, int]] = []
        self.rejected: set[int] = set()

    def GetUserPreferenceInteger(self, preference: int, _option: int) -> int:
        return self.values[preference]

    def SetUserPreferenceInteger(
        self, preference: int, _option: int, value: int
    ) -> bool:
        self.writes.append((preference, value))
        if preference in self.rejected:
            return False
        self.values[preference] = value
        return True


def _adapter(evaluated, extension: _Extension | None = None, doc_type: int = 1):
    extension = extension or _Extension()
    result = SimpleNamespace(is_success=True, error=None, data={"value": evaluated})
    return SimpleNamespace(
        set_global_variable=lambda _params: result,
        currentModel=SimpleNamespace(Extension=extension, GetType=lambda: doc_type),
    )


@pytest.mark.parametrize(
    ("expr", "evaluated", "linear", "angular"),
    [
        ("12.5182deg", 12.5182, _SW_INCHES, _SW_DEGREES),
        ("12.5182deg", math.radians(12.5182), _SW_INCHES, _SW_RADIANS),
        # pd_pinion_cam's CamOd, as logged at eight inch places.
        ("14.6mm", 0.57480315, _SW_INCHES, _SW_DEGREES),
        ("808.2932000000001mm", 31.82256693, _SW_INCHES, _SW_DEGREES),
        ("14.6mm", 14.6, _SW_MM, _SW_DEGREES),
        ("0.25in", 6.35, _SW_MM, _SW_DEGREES),
        ("-1.5e-3mm", -0.0015, _SW_MM, _SW_DEGREES),
    ],
)
def test_a_literal_evaluated_exactly_passes(expr, evaluated, linear, angular):
    adapter = _adapter(evaluated, _Extension(linear, angular))
    assert set_global(adapter, "G", expr) == evaluated


@pytest.mark.parametrize(
    ("expr", "evaluated", "linear"),
    [
        # #889: two angular places evaluated ConeIncline as 12.52.
        ("12.5182deg", 12.52, _SW_INCHES),
        # Three inch places would evaluate CamOd as .575 in.
        ("14.6mm", 0.575, _SW_INCHES),
        ("14.6mm", None, _SW_INCHES),
    ],
)
def test_a_rounded_or_missing_literal_evaluation_fails(expr, evaluated, linear):
    adapter = _adapter(evaluated, _Extension(linear))
    with pytest.raises(
        RuntimeError, match=r"set_global G='.*': evaluated .*, intended"
    ):
        set_global(adapter, "G", expr)


def test_a_formula_is_not_gated():
    adapter = _adapter(3.0, _Extension(_SW_FEET_INCHES))
    assert set_global(adapter, "G", '"A" + 2mm') == 3.0


def test_a_document_unit_without_a_readback_scale_fails():
    adapter = _adapter(1.0, _Extension(_SW_FEET_INCHES))
    with pytest.raises(
        RuntimeError, match="document length unit 5 has no readback scale"
    ):
        set_global(adapter, "G", "25.4mm")


@pytest.mark.parametrize("unit", ["mm", "in"])
def test_a_part_gets_eight_angular_places_before_its_length_units(unit):
    extension = _Extension()
    apply_package_model_units(_adapter(None, extension), unit, label="part")
    assert extension.writes[0] == (52, 8)
    assert extension.values[52] == 8
    lengths = [(49, 8)] if unit == "mm" else [(47, 3), (48, 1), (49, 8), (263, 3)]
    assert extension.writes[1:] == lengths


def test_a_part_without_package_units_gets_eight_places_in_its_template_unit():
    # Codjiflo P1 on #3149: a millimetre package's literals must not rest on
    # the template's linear places; its length unit stays the template's.
    extension = _Extension()
    keep_equation_places_exact(_adapter(None, extension), label="part")
    assert extension.writes == [(52, 8), (49, 8)]
    assert extension.values[47] == _SW_INCHES


def test_an_assembly_keeps_its_angular_places():
    extension = _Extension()
    apply_package_model_units(_adapter(None, extension, doc_type=2), "mm", label="asm")
    assert extension.writes == []


@pytest.mark.parametrize("preference", [52, 49])
def test_equation_places_that_do_not_read_back_fail(preference):
    extension = _Extension()
    extension.rejected.add(preference)
    with pytest.raises(RuntimeError, match="DecimalPlaces = 8 rejected"):
        keep_equation_places_exact(_adapter(None, extension), label="part")

    class Ignoring(_Extension):
        def SetUserPreferenceInteger(self, preference, option, value):
            self.writes.append((preference, value))
            return True

    with pytest.raises(RuntimeError, match="model units read"):
        keep_equation_places_exact(_adapter(None, Ignoring()), label="part")
