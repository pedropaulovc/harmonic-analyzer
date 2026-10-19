"""Offline release contracts for the MHA-VN-029 axial arm-to-hub seam pin."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _supplier_pin_drawing as supplier_drawing
import build_vn_crank_hub_pin as part
import dt_crank_hub_geometry as geometry
import vn_crank_hub_pin_spec as pin_spec
import draw_vn_crank_hub_pin as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_pin_length_is_half_the_shared_arm_thickness() -> None:
    assert pin_spec.PIN_LEN == geometry.ARM_THICKNESS / 2.0 == 4.0


def test_six_oclock_seam_leaves_the_u27_web_without_a_matched_check() -> None:
    assert geometry.HUB_SEAT_DIA_MIN_GENERAL == pytest.approx(18.6)
    assert geometry.AXIAL_PIN_DIA_STOCK_MAX == pytest.approx(4.012)
    assert geometry.HUB_BORE_DIA_MAX == pytest.approx(9.58)
    assert geometry.SEAM_WEB_WORST_MM >= geometry.WALL_TARGET_MM
    assert "LIGHT DRIVE FIT ON ACTUAL MHA-VN-029 PIN" in pin_spec.DRAWING_NOTES
    assert len(pin_spec.DRAWING_NOTES.splitlines()) <= 4


def test_drawing_registry_and_native_dimensions_are_complete() -> None:
    assert DRAWINGS_BY_NAME["vn_crank_hub_pin"].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/vn-crank-hub-pin.SLDDRW")
    assert set(drawing.RIGHT_KEEP) == set().union(*pin_spec.DRAWING_DIMENSIONS.values())
    assert pin_spec.DRAWING_PRECISION_BY_NAME == {"PinDia": 3, "PinLen": 0}


def test_assembly_places_pin_axially_at_six_oclock() -> None:
    import build_dt_drive_train_assembly as assembly

    assert assembly.CRANK_HUB_PIN_ORIGIN == pytest.approx(
        (
            assembly.X_CRANK,
            assembly.Y_CRANK - geometry.AXIAL_PIN_RADIUS_FROM_AXIS,
            assembly.CRANK_FACE_Z,
        )
    )
    assert assembly.CRANK_HUB_PIN_ROWS[2] == pytest.approx((0.0, 0.0, 1.0))


def test_registered_stock_matches_the_live_iso2338_source() -> None:
    row = _config.parts("vn-crank-hub-pin")
    source = pin_spec.SUPPLIER_REFERENCE
    assert source.sku == pin_spec.SKU == "91585A377"
    assert row["supplier"] == "McMaster-Carr"
    assert row["supplier_skus"] == [source.sku]
    assert row["material"] == "18-8 stainless steel"
    assert row["finish"] == "passivated"
    assert row["process"] == "purchased"
    assert part.SPEC.stock_name == row["stock_name"]
    assert part.SPEC.supplier == row["supplier"]
    assert part.SPEC.skus == (source.sku,)
    assert row["installation_notes"] == pin_spec.DRAWING_NOTES
    assert source.sku in row["material_specification"]
    assert "ISO 2338-m6" in row["material_specification"]
    assert part.MATERIAL == "AISI 304"
    assert source.units == "mm"
    assert source.diameter_mm == pin_spec.PIN_DIA == 4.0
    assert source.length_mm == pin_spec.PIN_LEN == 4.0
    assert source.diameter_precision == 3
    assert source.length_precision == 0
    assert source.diameter_band == pin_spec.PIN_DIA_BAND == (0.004, 0.012)
    assert source.diameter_mm + max(pin_spec.PIN_DIA_BAND) == pytest.approx(
        geometry.AXIAL_PIN_DIA_STOCK_MAX
    )


def test_native_profile_uses_vendor_step_leads_without_changing_installation() -> None:
    assert pin_spec.PIN_CHAMFER_AXIAL == pytest.approx(0.630)
    assert pin_spec.PIN_CHAMFER_ANGLE_DEG == 15.0
    assert pin_spec.PIN_END_RADIUS == pytest.approx(1.8311920087683926)
    assert pin_spec.PIN_FULL_DIA_LENGTH == pytest.approx(2.740)
    assert part.V_PIN == pytest.approx(48.96666084388053, rel=1e-12)
    assert pin_spec.PIN_FULL_DIA_LENGTH + 2 * pin_spec.PIN_CHAMFER_AXIAL == 4.0


def _native_source():
    def point(x, y):
        return SimpleNamespace(X=x / 1000.0, Y=y / 1000.0, Z=0.0)

    def line(first, second, *, construction=False):
        return SimpleNamespace(
            ConstructionGeometry=construction,
            GetType=lambda: 0,
            GetStartPoint2=lambda: first,
            GetEndPoint2=lambda: second,
        )

    length = pin_spec.PIN_LEN
    radius = pin_spec.PIN_DIA / 2.0
    lead = pin_spec.PIN_CHAMFER_AXIAL
    end_radius = pin_spec.PIN_END_RADIUS
    points = [
        point(0.0, 0.0), point(0.0, end_radius), point(-lead, radius),
        point(-(length - lead), radius), point(-length, end_radius),
        point(-length, 0.0),
    ]
    profile = [line(points[index], points[(index + 1) % 6]) for index in range(6)]
    axis = line(point(0.0, 0.0), point(-length, 0.0), construction=True)
    sketch = SimpleNamespace(GetSketchSegments=lambda: [axis, *profile])
    feature = SimpleNamespace(GetSpecificFeature2=lambda: sketch)
    caps = [
        SimpleNamespace(
            IsPlane=lambda: True,
            PlaneParams=(0.0, 0.0, 1.0, 0.0, 0.0, station),
        )
        for station in (0.0, length / 1000.0)
    ]
    cylinder = SimpleNamespace(
        IsPlane=lambda: False,
        IsCylinder=lambda: True,
        CylinderParams=(0.0, 0.0, 0.0, 0.0, 0.0, 1.0, radius / 1000.0),
    )
    faces = [
        SimpleNamespace(GetSurface=lambda surface=surface: surface)
        for surface in (*caps, cylinder)
    ]
    body = SimpleNamespace(GetFaces=lambda: faces)
    model = SimpleNamespace(
        FeatureByName=lambda name: feature if name == "PinProfile" else None,
        GetBodies2=lambda _kind, _visible: (body,),
    )
    return SimpleNamespace(
        model=model, feature=feature, points=points, caps=caps, cylinder=cylinder,
        axis_points=(axis.GetStartPoint2(), axis.GetEndPoint2()),
        references={
            "PinDia": (axis, profile[2]),
            "PinLen": (profile[5].GetStartPoint2(), profile[5].GetEndPoint2()),
        },
    )


def _reference(name: str, source=None):
    diameter = name == "PinDia"
    if source is None:
        source = _native_source()
    state = {
        "lower": pin_spec.PIN_DIA_BAND[0] / 1000.0,
        "upper": pin_spec.PIN_DIA_BAND[1] / 1000.0,
        "precision": 3,
        "entities": source.references[name],
        "source": source,
    }
    tolerance = SimpleNamespace(
        Type=2 if diameter else 0,
        GetMinValue=lambda: state["lower"],
        GetMaxValue=lambda: state["upper"],
    )
    dimension = SimpleNamespace(
        Tolerance=tolerance,
        FullName=f"{name}@PinProfile@vn-crank-hub-pin-1",
        GetFeatureOwner=lambda: source.feature,
    )
    annotation = SimpleNamespace(
        name=name,
        GetAttachedEntities3=lambda: state["entities"],
        GetSpecificAnnotation=lambda: display,
    )
    display = SimpleNamespace(
        Type2=15 if diameter else 11,
        GetDimension2=lambda _index: dimension,
        GetAnnotation=lambda: annotation,
        GetPrimaryTolPrecision2=lambda: state["precision"],
    )
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    return adapter, display, annotation, state


@pytest.fixture
def native_reference_fakes(monkeypatch):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        supplier_drawing, "_early_bound", lambda value, _interface: value
    )
    monkeypatch.setattr(
        drawing,
        "assert_supplier_reference_dimension",
        lambda _adapter, _display, **_kwargs: None,
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("kind", "native type"),
        ("tolerance_type", "tolerance type"),
        ("lower", "reference band"),
        ("upper", "reference band"),
        ("precision", "reference band"),
        ("missing_attachment", "attachments are incomplete"),
        ("changed_attachment", "attachment changed"),
    ),
)
def test_final_diameter_readback_rejects_corrupted_stock_reference(
    native_reference_fakes, mutation, message
) -> None:
    adapter, display, _annotation, state = _reference("PinDia")
    entities = state["entities"]
    if mutation == "kind":
        display.Type2 = 3
    elif mutation == "tolerance_type":
        display.GetDimension2(0).Tolerance.Type = 0
    elif mutation in ("lower", "upper", "precision"):
        state[mutation] = 0
    elif mutation == "missing_attachment":
        state["entities"] = entities[:1]
    elif mutation == "changed_attachment":
        state["entities"] = (entities[0], object())
    with pytest.raises(RuntimeError, match=message):
        drawing._assert_supplier_pin_reference(
            adapter, display, name="PinDia", source_model=state["source"].model
        )


def test_final_length_readback_rejects_an_invented_supplier_band(
    native_reference_fakes,
) -> None:
    adapter, display, _annotation, state = _reference("PinLen")
    display.GetDimension2(0).Tolerance.Type = 2
    with pytest.raises(RuntimeError, match="tolerance type"):
        drawing._assert_supplier_pin_reference(
            adapter, display, name="PinLen", source_model=state["source"].model
        )


def test_settled_check_reacquires_final_dimensions_and_requires_both_sizes(
    native_reference_fakes, monkeypatch
) -> None:
    source = _native_source()
    adapter, diameter, dia_annotation, _dia_state = _reference("PinDia", source)
    _adapter, _length, len_annotation, _len_state = _reference("PinLen", source)
    monkeypatch.setattr(
        drawing, "dimension_name", lambda _adapter, annotation: annotation.name
    )
    monkeypatch.setattr(
        drawing, "supplier_reference_dimension",
        lambda _adapter, display, **_kwargs: display,
    )
    annotations = [dia_annotation, len_annotation]
    view = SimpleNamespace(
        GetAnnotationsByType=lambda _kind: annotations, ReferencedDocument=source.model
    )
    settled = drawing._supplier_references(adapter, annotations.copy(), view)
    settled()
    diameter.GetDimension2(0).Tolerance.Type = 0
    with pytest.raises(RuntimeError, match="tolerance type"):
        settled()
    diameter.GetDimension2(0).Tolerance.Type = 2
    annotations.pop()
    with pytest.raises(RuntimeError, match="final supplier-reference census"):
        settled()


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("solid_span", "actual pin end planes"),
        ("solid_diameter", "actual pin cylinder"),
        ("profile_span", "source profile geometry changed"),
        ("end_radius", "source profile geometry changed"),
        ("wrong_owner", "wrong model owner"),
        ("initial_wrong_attachment", "attachment changed"),
    ),
)
def test_reference_rejects_wrong_native_geometry_even_with_correct_nominal_dimension(
    native_reference_fakes, mutation, message
) -> None:
    adapter, display, _annotation, state = _reference("PinLen")
    source = state["source"]
    if mutation == "solid_span":
        source.caps[1].PlaneParams = (0.0, 0.0, 1.0, 0.0, 0.0, 0.002740)
    elif mutation == "solid_diameter":
        source.cylinder.CylinderParams = (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0019)
    elif mutation == "profile_span":
        source.points[5].X = -0.002740
    elif mutation == "end_radius":
        source.points[1].Y += 0.0001
    elif mutation == "wrong_owner":
        display.GetDimension2(0).GetFeatureOwner = lambda: object()
    elif mutation == "initial_wrong_attachment":
        # The construction-axis points also span 4 mm, but are not the profile
        # closing-edge endpoints selected by the native PinLen dimension.
        state["entities"] = source.axis_points
    with pytest.raises(RuntimeError, match=message):
        drawing._assert_supplier_pin_reference(
            adapter, display, name="PinLen", source_model=source.model
        )
