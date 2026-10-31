"""MHA-FR-VN-52 gooseneck set screw (McMaster 91410A540): its inch sheet, offline."""

from __future__ import annotations

import ast
import asyncio
import inspect
from fractions import Fraction
from pathlib import Path

import pytest

import _config
import _mcmaster_91410a540 as supplier
import _purchased_fastener_drawing as purchased
import _supplier_dimensions
import draw_fr_vn_gooseneck_set_screw as draw
from _drawing_package_unit import package_drawing_unit
from _part_properties import part_drawing_unit

STEM = "fr-vn-gooseneck-set-screw"
IN = 25.4


def test_package_declares_the_inch_sheet() -> None:
    row = _config.parts(STEM)
    assert row["drawing_unit"] == "in"
    assert row["supplier_skus"] == ["91410A540"]
    # One declaration: the sheet, its TOL_* stamps and the source part's
    # saved document units all resolve the same row.
    assert draw.PACKAGE == STEM == draw.SPEC.artifact_stem
    assert package_drawing_unit(draw.PACKAGE) == "in"
    assert part_drawing_unit(STEM) == "in"


def test_supplier_sizes_are_the_catalogue_inches_unchanged() -> None:
    assert Fraction(supplier.SHANK_LEN / IN).limit_denominator(64) == Fraction(3, 4)
    assert Fraction(supplier.SHANK_DIA / IN).limit_denominator(64) == Fraction(1, 4)
    assert Fraction(supplier.HEAD_AF / IN).limit_denominator(64) == Fraction(1, 4)
    assert Fraction(supplier.HEAD_H / IN).limit_denominator(64) == Fraction(3, 16)
    for name, value, _orientation in supplier.SUPPLIER_REFERENCE_DIMENSIONS:
        exact = abs(value) / IN
        assert abs(exact * 64 - round(exact * 64)) < 1e-9, name


def _shown(name: str) -> tuple[int, int, str, str]:
    value = dict((n, v) for n, v, _ in supplier.SUPPLIER_REFERENCE_DIMENSIONS)[name]
    precision, presentation, denominator, callout = supplier.SUPPLIER_REFERENCE_FORMATS[
        name
    ]
    return _supplier_dimensions._presentation(
        label=name,
        units="in",
        precision=precision,
        presentation=presentation,
        fraction_denominator=denominator,
        callout=callout,
        expected_mm=abs(value),
    )


def test_head_prints_supplier_fractions_and_shank_decimal_inches() -> None:
    # (units, fraction base, prefix, suffix): swINCHES with an exact fraction
    # on the head, decimal on the shank; every value labelled in inches.
    assert _shown("SupplierHeadWidth") == (3, 2, "(", ")")
    assert _shown("SupplierHeadHeight") == (3, 2, "(", ")")
    assert _shown("SupplierLength") == (3, 1, "(", " in)")
    assert _shown("SupplierThreadDiameter") == (3, 1, "(<MOD-DIAM>", " in)")
    formats = supplier.SUPPLIER_REFERENCE_FORMATS
    assert formats["SupplierHeadWidth"][2] == 4
    assert formats["SupplierHeadHeight"][2] == 16
    assert formats["SupplierLength"][:3] == (2, "length", None)
    assert formats["SupplierThreadDiameter"][:3] == (2, "diameter", None)
    # A fraction the geometry cannot show exactly is refused, never rounded.
    with pytest.raises(ValueError, match="exact geometry"):
        _supplier_dimensions._presentation(
            label="SupplierHeadHeight",
            units="in",
            precision=0,
            presentation="length",
            fraction_denominator=8,
            callout=None,
            expected_mm=supplier.HEAD_H,
        )


class _Annotation:
    Visible, OwnerType, Owner = 1, 0, object()

    def IsDangling(self):
        return False

    def GetAttachedEntities3(self):
        return (object(),)

    def GetAttachedEntityTypes(self):
        return (1,)

    def GetAttachedEntityCount3(self):
        return 1


class _Display:
    """An imported model reference: document units until dressed."""

    def __init__(self, value_mm: float) -> None:
        self.dimension = type("Dimension", (), {"SystemValue": value_mm / 1000.0})()
        self.Type2 = 2  # swLinearDimension
        self.ShowDimensionValue = True
        self.ShowParenthesis = False
        self.units_call: tuple = ()
        self.state = {
            "use_doc": True,
            "units": 0,
            "base": 1,
            "value": 0,
            "round": False,
        }
        self.precision = 2
        self.text = {1: "", 2: "", 4: ""}

    def GetAnnotation(self):
        return _Annotation()

    def GetDimension2(self, _index):
        return self.dimension

    def GetOverride(self):
        return False

    def SetUnits2(self, use_doc, units, base, value, round_to_fraction, half_away):
        self.units_call = (use_doc, units, base, value, round_to_fraction, half_away)
        self.state = {
            "use_doc": use_doc,
            "units": units,
            "base": base,
            "value": value,
            "round": round_to_fraction,
        }
        return 0

    def GetUseDocUnits(self):
        return self.state["use_doc"]

    def GetUnits(self):
        return self.state["units"]

    def GetFractionBase(self):
        return self.state["base"]

    def GetFractionValue(self):
        return self.state["value"]

    def GetRoundToFraction(self):
        return self.state["round"]

    def SetPrecision3(self, primary, *_rest):
        self.precision = primary
        return 0

    def GetPrimaryPrecision2(self):
        return self.precision

    def SetText(self, part, text):
        self.text[part] = text

    def GetText(self, part):
        return self.text[part]


def test_head_height_is_an_exact_unrounded_sixteenth() -> None:
    display = _Display(supplier.HEAD_H)
    precision, presentation, denominator, callout = supplier.SUPPLIER_REFERENCE_FORMATS[
        "SupplierHeadHeight"
    ]
    _supplier_dimensions.supplier_reference_dimension(
        object(),
        display,
        label="SupplierHeadHeight",
        units="in",
        precision=precision,
        expected_mm=supplier.HEAD_H,
        presentation=presentation,
        fraction_denominator=denominator,
        callout=callout,
    )
    # SetUnits2(UseDoc=False, swINCHES, swFRACTION, 16, RoundToFraction=False, 0).
    assert display.units_call == (False, 3, 2, 16, False, 0)
    assert (display.text[1], display.text[2]) == ("(", ")")
    # The duplicate explicit unit must not return after a rebuild either.
    display.text[2] = " in)"
    with pytest.raises(RuntimeError, match="suffix"):
        _supplier_dimensions.assert_supplier_reference_dimension(
            object(), display, label="SupplierHeadHeight", units="in",
            precision=precision, expected_mm=supplier.HEAD_H,
            presentation=presentation, fraction_denominator=denominator, callout=callout,
        )
    display.text[2] = ")"
    # A seat that rounds the head to the nearest fraction no longer proves it.
    display.state["round"] = True
    with pytest.raises(RuntimeError, match="exact supplier fraction"):
        _supplier_dimensions.assert_supplier_reference_dimension(
            object(),
            display,
            label="SupplierHeadHeight",
            units="in",
            precision=precision,
            expected_mm=supplier.HEAD_H,
            presentation=presentation,
            fraction_denominator=denominator,
            callout=callout,
        )


def test_sheet_names_its_own_package(monkeypatch) -> None:
    captured = {}

    async def purchased_sheet(_adapter, spec, **kwargs):
        captured.update(kwargs, spec=spec)
        return {"pdf": "sheet.pdf"}

    monkeypatch.setattr(draw, "build_purchased_fastener_drawing", purchased_sheet)
    assert asyncio.run(draw.build(object())) == {"pdf": "sheet.pdf"}
    assert captured["spec"] is draw.SPEC
    assert captured["package_name"] == STEM


def test_purchased_sheet_refuses_a_foreign_package() -> None:
    with pytest.raises(ValueError, match="not its own part"):
        asyncio.run(
            purchased.build_purchased_fastener_drawing(
                object(), draw.SPEC, package_name="ch-rocker-arm-tl-vn-oblique-rail"
            )
        )


def test_purchased_sheet_forwards_the_package_to_setup_and_finalize() -> None:
    tree = ast.parse(inspect.getsource(purchased._build_reference_sheet).lstrip())
    calls = {
        node.func.id: {kw.arg: ast.unparse(kw.value) for kw in node.keywords if kw.arg}
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("new_project_drawing", "finalize_drawing")
    }
    assert calls["new_project_drawing"]["package_name"] == "package_name"
    assert calls["finalize_drawing"]["package_name"] == "package_name"
    source = Path(purchased.__file__).read_text(encoding="utf-8")
    assert "package_name=package_name," in source


def test_native_thread_text_is_shelved_and_reacquired_after_final_rebuild(monkeypatch) -> None:
    imported = {"SupplierThreadDiameter": object()}
    reacquired = {"SupplierThreadDiameter": object()}
    stations = {"SupplierThreadDiameter": {"tips": "retained native tips"}}
    events = []
    monkeypatch.setattr(draw, "_assert_projection_alignment", lambda *_: events.append("aligned"))

    def annotate(adapter, views, **kwargs):
        assert kwargs["dimensions"] is supplier.SUPPLIER_REFERENCE_DIMENSIONS
        assert kwargs["formats"] is supplier.SUPPLIER_REFERENCE_FORMATS
        kwargs["settled_checks"].append(lambda: reacquired)
        events.append("import")
        return imported

    def shelve(adapter, displays, shelves):
        assert displays is imported
        assert shelves == {"SupplierThreadDiameter": (True, "right")}
        events.append("shelve")
        return stations

    def assert_shelves(adapter, displays, shelves, retained):
        assert displays is reacquired
        assert shelves == draw.TEXT_SHELVES
        assert retained == stations
        events.append("settled")

    async def purchased_sheet(adapter, spec, **kwargs):
        kwargs["supplier_dimensions"](adapter, {})
        assert events == ["aligned", "import", "shelve"]
        kwargs["settled_checks"][0]()
        with pytest.raises(RuntimeError, match="exactly one settled proof"):
            kwargs["settled_checks"][0]()
        return {"pdf": "sheet.pdf"}

    monkeypatch.setattr(draw, "annotate_supplier_screw", annotate)
    monkeypatch.setattr(draw, "shelve_supplier_text", shelve)
    monkeypatch.setattr(draw, "assert_supplier_shelves", assert_shelves)
    monkeypatch.setattr(draw, "build_purchased_fastener_drawing", purchased_sheet)
    assert asyncio.run(draw.build(object())) == {"pdf": "sheet.pdf"}
    assert events == ["aligned", "import", "shelve", "settled", "aligned"]


def test_right_reserves_front_vertical_lanes_without_changing_front_budget() -> None:
    original = draw.supplier_screw_margins(
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
        sides=supplier.SUPPLIER_REFERENCE_SIDES,
    )
    assert draw.SUPPLIER_MARGINS["*Front"] == original["*Front"]
    assert draw.SUPPLIER_MARGINS["*Top"] == original["*Top"]
    assert draw.SUPPLIER_MARGINS["*Right"] == (
        0.0, original["*Front"][1], 0.0, original["*Front"][3]
    )


@pytest.mark.parametrize(
    "right_origin,right_scale,valid",
    [
        ((0.30, 0.12), (1, 1), True),
        ((0.30, 0.117), (1, 1), False),
        ((0.05, 0.12), (1, 1), False),
        ((0.30, float("nan")), (1, 1), False),
        ((0.30, 0.12), (2, 1), False),
    ],
)
def test_projection_proof_refuses_origin_or_scale_drift(
    monkeypatch, right_origin, right_scale, valid
) -> None:
    front = type("View", (), {"ScaleRatio": (1, 1)})()
    right = type("View", (), {"ScaleRatio": right_scale})()
    monkeypatch.setattr(
        draw, "model_point_in_view",
        lambda adapter, view, point, **kwargs: (0.10, 0.12) if view is front else right_origin,
    )
    views = {"*Front": front, "*Right": right}
    if valid:
        draw._assert_projection_alignment(object(), views)
    else:
        with pytest.raises(RuntimeError, match="third-angle aligned"):
            draw._assert_projection_alignment(object(), views)
