from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from xml.etree import ElementTree

import pytest

import _drawing_common
import _part_pmi
from _drawing_common import PmiDrawingPlacement
from _gtol_cone import ConeFace
from _gtol_cylinder import CylinderFace
from _gtol_controls import GeometricControl, PartDatum, validate_part_pmi
from _gtol_planar import PlanarFace
from _gtol_sphere import SphereFace
from _gtol_torus import TorusFace
from _gtol_frame import (
    TRANSLATION_GLYPH,
    gtol_frame_datums,
    gtol_frame_signature,
    gtol_frame_xml,
    translation_print_problem,
)
from _gtol_face import FaceGeometry



def test_frame_datums_read_a_composite_lower_tier_without_its_symbol() -> None:
    # Farm run 20261009T200747541Z: the knife mount's composite lower tier
    # read back one empty <ToleranceSymbol>; the full signature refuses it,
    # its datum references do not need it.
    lower = gtol_frame_xml(
        "position", "0.05", datums=("A", "B", "C"), translated=("C",), diameter=True
    ).replace("<ToleranceSymbol>GTOL-POSI</ToleranceSymbol>", "<ToleranceSymbol />")
    assert "<ToleranceSymbol />" in lower
    with pytest.raises(ValueError, match="frame XML has 1 tolerance symbols"):
        gtol_frame_signature(lower)
    assert gtol_frame_datums(lower) == ("A", "B", "C")
    with pytest.raises(ValueError, match="invalid feature-control-frame XML"):
        gtol_frame_datums("<GtolFrame>")


def test_frame_signature_reads_the_symbol_code_solidworks_unescapes() -> None:
    # Farm run 20261009T200747541Z: SetSymbolXml took "C&lt;MOD-TRANS2&gt;"
    # and GetSymbolXml read it back as "C<MOD-TRANS2>" ("mismatched tag").
    authored = gtol_frame_xml(
        "position", "0.05", datums=("B", "C"), translated=("C",)
    )
    applied = authored.replace("&lt;", "<").replace("&gt;", ">")
    assert "<DatumLetter>C<MOD-TRANS2></DatumLetter>" in applied
    assert gtol_frame_signature(applied) == gtol_frame_signature(authored)
    assert gtol_frame_signature(applied).translated == ("C",)
    assert gtol_frame_datums(applied) == ("B", "C")


def test_frame_signature_preserves_every_authored_semantic() -> None:
    control = GeometricControl(
        "axis_position",
        "position",
        "0.05",
        CylinderFace(5.0),
        datums=("A", "B"),
        tolerance_zone="diametral",
    )
    serialized = control.frame_xml.replace(
        "</GtolFrame>", "<SolidWorksDefault /></GtolFrame>"
    )

    signature = gtol_frame_signature(serialized)

    assert signature.characteristic_symbol == "GTOL-POSI"
    assert signature.tolerance == "0.05"
    assert signature.datums == ("A", "B")
    assert signature.tolerance_zone == "diametral"


def test_frame_signature_rejects_unsupported_range_symbol() -> None:
    xml = GeometricControl(
        "flat", "flatness", "0.03", PlanarFace((1.0, 0.0, 0.0), 0.0)
    ).frame_xml

    with pytest.raises(ValueError, match="unsupported primary range symbols"):
        gtol_frame_signature(
            xml.replace(
                "</ToleranceRangeInfo>",
                "<PrimaryRangeSymbol>radius</PrimaryRangeSymbol></ToleranceRangeInfo>",
            )
        )


def test_part_pmi_validation_rejects_name_collision_and_unknown_datum() -> None:
    datum = PartDatum("A", CylinderFace(5.0))
    collision = GeometricControl("datum_A", "cylindricity", "0.01", CylinderFace(5.0))
    with pytest.raises(ValueError, match="annotation-name collision"):
        validate_part_pmi((datum,), (collision,))

    unknown = GeometricControl(
        "runout",
        "circular_runout",
        "0.03",
        CylinderFace(5.0),
        datums=("B",),
    )
    with pytest.raises(ValueError, match="unknown datum references"):
        validate_part_pmi((datum,), (unknown,))


def test_cylinder_face_tolerance_is_diametral_not_radial() -> None:
    geometry = FaceGeometry(
        face=SimpleNamespace(),
        identity=4002,
        parameters=(0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 5.04e-3),
        outward_normal=None,
        box=(0.0, 0.0, 0.0, 1.0, 1.0, 1.0),
    )

    assert not CylinderFace(10.0, tolerance_mm=0.05).matches(geometry)
    assert CylinderFace(10.0, tolerance_mm=0.1).matches(geometry)


def test_cylinder_face_can_disambiguate_by_x_and_y_stations() -> None:
    geometry = FaceGeometry(
        face=SimpleNamespace(),
        identity=4002,
        parameters=(0.011, -0.04, 0.008, 0.0, 1.0, 0.0, 4e-3),
        outward_normal=None,
        box=(0.007, 0.008, 0.004, 0.015, 0.018, 0.012),
    )

    assert CylinderFace(8.0, contains_x_mm=11.0, contains_y_mm=13.0).matches(geometry)
    assert not CylinderFace(8.0, contains_x_mm=21.0, contains_y_mm=13.0).matches(geometry)


def test_cone_face_matches_live_coneparams2_contract() -> None:
    geometry = FaceGeometry(
        face=SimpleNamespace(),
        identity=4003,
        parameters=(
            0.045,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0025,
            0.01041629,
            0.0,
            -1.0,
            0.0,
        ),
        outward_normal=None,
        box=(0.0, -0.003, -0.003, 0.045, 0.003, 0.003),
    )

    assert ConeFace(0.596809, contains_x_mm=22.5, tolerance_degrees=0.001).matches(geometry)
    assert not ConeFace(1.0).matches(geometry)


def test_planar_face_can_disambiguate_coplanar_trunnions_by_z_station() -> None:
    geometry = FaceGeometry(
        face=SimpleNamespace(),
        identity=4001,
        parameters=(-0.510265461, -0.860016953, 0.0, 0.0043265, 0.002567, 0.097917),
        outward_normal=(0.510265461, 0.860016953, 0.0),
        box=(0.0, 0.002567, 0.0762, 0.0043265, 0.005134, 0.097917),
    )

    assert PlanarFace(
        (0.510265461, 0.860016953, 0.0),
        4.415327,
        contains_z_mm=87.0585,
    ).matches(geometry)
    assert not PlanarFace(
        (0.510265461, 0.860016953, 0.0),
        4.415327,
        contains_z_mm=-87.0585,
    ).matches(geometry)


def test_planar_face_pins_one_of_four_coplanar_cap_seats_by_x_and_z() -> None:
    """The top frame's four cap-recess floors share one plane and one area.

    Only both plan stations together name one of them, so a control that
    pins just the plane -- or pins the wrong corner -- must not match.
    """
    geometry = FaceGeometry(
        face=SimpleNamespace(),
        identity=4001,
        parameters=(0.0, -1.0, 0.0, 0.197, 0.00645, 0.112),
        outward_normal=(0.0, 1.0, 0.0),
        box=(0.18325, 0.00645, 0.09825, 0.21075, 0.00645, 0.12575),
    )

    assert PlanarFace((0.0, 1.0, 0.0), 6.45, contains_x_mm=197.0, contains_z_mm=112.0).matches(geometry)
    assert not PlanarFace((0.0, 1.0, 0.0), 6.45, contains_x_mm=-197.0, contains_z_mm=112.0).matches(geometry)
    assert not PlanarFace((0.0, 1.0, 0.0), 6.45, contains_x_mm=197.0, contains_z_mm=-112.0).matches(geometry)


def test_sphere_identity_is_not_cone_identity() -> None:
    geometry = FaceGeometry(
        face=SimpleNamespace(),
        identity=4004,
        parameters=(0.0, 0.0252, 0.0, 0.0065),
        outward_normal=None,
        box=(),
    )

    assert SphereFace(13.0, center_mm=(0.0, 25.2, 0.0)).matches(geometry)


def test_torus_face_matches_generating_radii_and_center() -> None:
    geometry = FaceGeometry(
        face=SimpleNamespace(),
        identity=4005,
        parameters=(0.0, 0.0085, 0.0, 0.0, 1.0, 0.0, 0.0015, 0.005),
        outward_normal=None,
        box=(),
    )

    assert TorusFace(1.5, 5.0, center_mm=(0.0, 8.5, 0.0)).matches(geometry)
    assert not TorusFace(2.0, 5.0).matches(geometry)


def test_imported_pmi_placement_requires_one_attachment() -> None:
    view = SimpleNamespace()
    with pytest.raises(ValueError, match="exactly one attachment"):
        PmiDrawingPlacement(view=view, position=(0.1, 0.2))
    with pytest.raises(ValueError, match="exactly one attachment"):
        PmiDrawingPlacement(
            view=view,
            position=(0.1, 0.2),
            attachment_xy=(0.1, 0.1),
            entity=SimpleNamespace(),
        )


# Hand-authored oracle using the installed R2026x public frame XSD's hierarchy.
# Do not derive the expected projected payload from the production XML writer.
_ORDINARY_XML = (
    "<GtolFrame><ToleranceSymbol>GTOL-PERP</ToleranceSymbol>"
    "<ToleranceRangeInfo><PrimaryToleranceValue>0.010</PrimaryToleranceValue>"
    "<PrimaryRangeSymbol>phi</PrimaryRangeSymbol></ToleranceRangeInfo></GtolFrame>"
)
_PROJECTED_FEATURE_INFO = (
    "<FeatureInfo><ProjectedToleranceZone>true</ProjectedToleranceZone>"
    "<Projection>31.3</Projection></FeatureInfo>"
)
_PROJECTED_XML = _ORDINARY_XML.replace(
    "</GtolFrame>", f"{_PROJECTED_FEATURE_INFO}</GtolFrame>"
)


def _projected_control(height: float | None = 31.3) -> GeometricControl:
    return GeometricControl(
        "projected_axis",
        "perpendicularity",
        "0.010",
        CylinderFace(5.0),
        tolerance_zone="diametral",
        projected_zone_height_mm=height,
    )


@pytest.mark.parametrize("height", (31.3, 39.2375, 1e-7, 1e20))
def test_projected_xml_authors_schema_nodes_not_tolerance_text(height: float) -> None:
    control = _projected_control(height)
    root = ElementTree.fromstring(control.frame_xml)

    assert root.findtext("ToleranceRangeInfo/PrimaryToleranceValue") == "0.010"
    assert root.findtext("ToleranceRangeInfo/PrimaryRangeSymbol") == "phi"
    assert root.findtext("FeatureInfo/ProjectedToleranceZone") == "true"
    projection = root.findtext("FeatureInfo/Projection")
    assert projection is not None and "e" not in projection.lower()
    assert float(projection) == height
    assert [child.tag for child in root] == [
        "ToleranceSymbol",
        "ToleranceRangeInfo",
        "FeatureInfo",
    ]
    assert gtol_frame_signature(control.frame_xml).projected_zone_height_mm == height


def test_ordinary_frame_payload_and_signature_remain_unprojected() -> None:
    assert _projected_control(None).frame_xml == _ORDINARY_XML
    assert gtol_frame_signature(_ORDINARY_XML).projected_zone_height_mm is None
    defaulted = _ORDINARY_XML.replace(
        "</GtolFrame>",
        "<FeatureInfo><ProjectedToleranceZone>false</ProjectedToleranceZone>"
        "<Projection>0</Projection><ProjectionRange>0</ProjectionRange>"
        "</FeatureInfo></GtolFrame>",
    )
    assert gtol_frame_signature(defaulted) == gtol_frame_signature(_ORDINARY_XML)


@pytest.mark.parametrize(
    "height", (0.0, -1.0, float("nan"), float("inf"), -float("inf"), True)
)
def test_projected_height_requires_finite_positive_source(height: float) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        _projected_control(height)
    with pytest.raises(ValueError, match="finite and positive"):
        gtol_frame_xml("perpendicularity", "0.010", projected_zone_height_mm=height)


def test_projected_signature_accepts_native_decimal_and_namespace_normalization() -> None:
    native = (
        _PROJECTED_XML.replace("0.010", ".010")
        .replace(">31.3<", ">31.3000<")
        .replace(">true<", ">1<")
        .replace("<GtolFrame>", '<GtolFrame xmlns="urn:swGtolFrame">')
    )
    assert gtol_frame_signature(native) == gtol_frame_signature(_PROJECTED_XML)


def test_projected_signature_preserves_datum_order_and_full_zone_height() -> None:
    xml = gtol_frame_xml(
        "position", "0.010", datums=("A", "B"), diameter=True,
        projected_zone_height_mm=39.2375,
    )
    root = ElementTree.fromstring(xml)
    assert [child.tag for child in root] == [
        "ToleranceSymbol", "ToleranceRangeInfo", "FeatureInfo",
        "DatumCompartment", "DatumCompartment",
    ]
    swapped = xml.replace(">A<", ">TEMP<").replace(">B<", ">A<").replace(">TEMP<", ">B<")
    assert gtol_frame_signature(swapped) != gtol_frame_signature(xml)
    assert gtol_frame_signature(xml).projected_zone_height_mm == 39.2375


@pytest.mark.parametrize(
    "feature_info",
    (
        "<FeatureInfo><ProjectedToleranceZone>true</ProjectedToleranceZone></FeatureInfo>",
        "<FeatureInfo><ProjectedToleranceZone>true</ProjectedToleranceZone>"
        "<Projection>0</Projection></FeatureInfo>",
        "<FeatureInfo><ProjectedToleranceZone>true</ProjectedToleranceZone>"
        "<Projection>-1</Projection></FeatureInfo>",
        "<FeatureInfo><ProjectedToleranceZone>true</ProjectedToleranceZone>"
        "<Projection>NaN</Projection></FeatureInfo>",
        "<FeatureInfo><ProjectedToleranceZone>true</ProjectedToleranceZone>"
        "<Projection>Infinity</Projection></FeatureInfo>",
        "<FeatureInfo><ProjectedToleranceZone>true</ProjectedToleranceZone>"
        "<Projection>3.13e1</Projection></FeatureInfo>",
        "<FeatureInfo><ProjectedToleranceZone>P</ProjectedToleranceZone>"
        "<Projection>31.3</Projection></FeatureInfo>",
        "<FeatureInfo><Projection>31.3</Projection></FeatureInfo>",
        "<FeatureInfo><ProjectedToleranceZone>false</ProjectedToleranceZone>"
        "<Projection>31.3</Projection></FeatureInfo>",
        "<FeatureInfo><ProjectedToleranceZone>true</ProjectedToleranceZone>"
        "<Projection>31.3</Projection><Projection>31.3</Projection></FeatureInfo>",
        "<FeatureInfo><ProjectedToleranceZone>true</ProjectedToleranceZone>"
        "<ProjectedToleranceZone>true</ProjectedToleranceZone>"
        "<Projection>31.3</Projection></FeatureInfo>",
        _PROJECTED_FEATURE_INFO + _PROJECTED_FEATURE_INFO,
        "<FeatureInfo><ProjectedToleranceZone>true</ProjectedToleranceZone>"
        "<Projection>31.3</Projection><ProjectionRange>1</ProjectionRange></FeatureInfo>",
        "<ProjectedToleranceZone>true</ProjectedToleranceZone><Projection>31.3</Projection>",
    ),
)
def test_projected_signature_refuses_unmeasured_or_changed_zone(feature_info: str) -> None:
    malformed = _ORDINARY_XML.replace("</GtolFrame>", f"{feature_info}</GtolFrame>")
    with pytest.raises(ValueError):
        gtol_frame_signature(malformed)


def test_signature_ignores_datum_projection_when_reading_feature_height() -> None:
    native = _PROJECTED_XML.replace(
        "</GtolFrame>",
        "<DatumCompartment><DatumDetail><DatumLetter>A</DatumLetter>"
        "<FeatureProjection>true</FeatureProjection><Projection>99</Projection>"
        "</DatumDetail></DatumCompartment></GtolFrame>",
    )
    signature = gtol_frame_signature(native)
    assert signature.projected_zone_height_mm == 31.3
    assert signature.datums == ("A",)


_NO_READBACK_OVERRIDE = object()


class _NativeFrame:
    """Actual IGtolFrame shape: two methods; BOOL setter and BSTR getter."""

    def __init__(self) -> None:
        self.xml = _ORDINARY_XML
        self.write_result: Any = True
        self.readback: Any = _NO_READBACK_OVERRIDE
        self.writes: list[str] = []

    def SetSymbolXml(self, xml: str) -> bool:  # noqa: N802
        self.writes.append(xml)
        if self.write_result is True:
            self.xml = xml
        return self.write_result

    def GetSymbolXml(self) -> str:  # noqa: N802
        return self.xml if self.readback is _NO_READBACK_OVERRIDE else self.readback


class _NativeAnnotation:
    def __init__(self, view: Any) -> None:
        self.Owner = view
        self.position = (0.1, 0.2, 0.0)
        self.name = ""

    def GetAttachedEntityCount3(self) -> int:  # noqa: N802
        return 1

    def SetLeader3(self, *_args: Any) -> int:  # noqa: N802
        return 0

    def SetPosition2(self, x: float, y: float, z: float) -> bool:  # noqa: N802
        self.position = (x, y, z)
        return True

    def GetPosition(self) -> tuple[float, float, float]:  # noqa: N802
        return self.position

    def SetName(self, name: str) -> bool:  # noqa: N802
        self.name = name
        return True

    def GetName(self) -> str:  # noqa: N802
        return self.name


class _NativeGtol:
    """No legacy PTZ members: attempting any fallback must fail.

    The seed-symbol setter is genuinely void. Refused BOOL writes record the
    call but leave state untouched; migration returns an integer status.
    """

    def __init__(self, frame: _NativeFrame, annotation: _NativeAnnotation) -> None:
        self.frame, self.annotation = frame, annotation
        self.format = 2
        self.frame_count = 1
        self.seed_calls = 0
        self.seed_result: Any = True
        self.convertible: Any = True
        self.add_result: Any = True
        self.conversion_error = 0

    def GetFormat(self) -> int:  # noqa: N802
        return self.format

    def GetFrameCount(self) -> int:  # noqa: N802
        return self.frame_count

    def AddFrame(self) -> bool:  # noqa: N802
        if self.add_result is True:
            self.frame_count += 1
        return self.add_result

    def GetFrame(self, index: int) -> _NativeFrame | None:  # noqa: N802
        assert index == 1
        return self.frame if self.format == 2 and self.frame_count == 1 else None

    def SetFrameSymbols2(self, *args: Any) -> None:  # noqa: N802
        assert args == (1, "<GTOL-PERP>", True, "", False, "", "", "", "")
        self.seed_calls += 1
        return None

    def SetFrameValues2(self, *args: Any) -> bool:  # noqa: N802
        assert args == (1, "0.010", "", "", "", "")
        if self.seed_result is True:
            # Official conversion example explicitly documents ".01" readback.
            self.frame.xml = _ORDINARY_XML.replace("0.010", ".010")
        return self.seed_result

    def CanConvertFormat(self) -> bool:  # noqa: N802
        return self.convertible

    def ConvertFormat(self) -> int:  # noqa: N802
        if self.conversion_error == 0:
            self.format = 2
        return self.conversion_error

    def GetAnnotation(self) -> _NativeAnnotation:  # noqa: N802
        return self.annotation

    def IsAttached(self) -> bool:  # noqa: N802
        return True

    def GetLeaderCount(self) -> int:  # noqa: N802
        return 1


@pytest.fixture
def projected_native(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Exercise real writers with contract doubles, never a native seat."""
    view = SimpleNamespace(GetName2=lambda: "Front")
    frame = _NativeFrame()
    annotation = _NativeAnnotation(view)
    gtol = _NativeGtol(frame, annotation)
    unit = SimpleNamespace(
        UnitType=0,
        SpecificUnitType=0,
        GetConversionFactor=lambda: 1000.0,
        GetFullUnitName=lambda _plural: "millimeter",
    )
    model = SimpleNamespace(
        InsertGtol=lambda: gtol,
        ClearSelection2=lambda _all: None,  # IModelDoc2 VT_VOID
        GetType=lambda: 1,
        GetPathName=lambda: "",
        GetTitle=lambda: "Unsaved contract double",
        GetUserUnit=lambda unit_type: unit if unit_type == 0 else None,
    )
    state = SimpleNamespace(
        frame=frame,
        gtol=gtol,
        annotation=annotation,
        view=view,
        adapter=SimpleNamespace(currentModel=model),
        on_rebuild=lambda: None,
    )
    import _native_projected_zone

    monkeypatch.setattr(_native_projected_zone, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(_part_pmi, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        _part_pmi, "_resolve_faces", lambda *_args: {"projected_axis": object()}
    )
    monkeypatch.setattr(_part_pmi, "_select_face", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(_part_pmi, "_verify_attachment", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        _drawing_common._sw_type_info,
        "early_bound_or_flag",
        lambda value, *_args: value,
    )
    monkeypatch.setattr(
        _drawing_common, "_select_annotation_entity", lambda *_args, **_kwargs: object()
    )
    monkeypatch.setattr(
        _drawing_common, "_assert_attached_to", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        _drawing_common, "rebuild_drawing", lambda *_args, **_kwargs: state.on_rebuild()
    )
    return state


def _author_native(state: SimpleNamespace, path: str, height: float | None = 31.3) -> Any:
    control = _projected_control(height)
    if path == "model":
        state.adapter.currentModel.GetType = lambda: 1
        return _part_pmi.author_part_pmi(state.adapter, controls=(control,))
    state.adapter.currentModel.GetType = lambda: 3
    if path == "projection":
        return _drawing_common.project_part_pmi(
            state.adapter,
            placements={
                control.key: PmiDrawingPlacement(
                    view=state.view, position=(0.1, 0.2), attachment_xy=(0.0, 0.0)
                )
            },
            datums=(),
            controls=(control,),
            label="projected axis",
        )
    assert path == "drawing"
    return _drawing_common.add_feature_control_frame(
        state.adapter,
        state.view,
        edge_xy=(0.0, 0.0),
        frame_xy=(0.1, 0.2),
        characteristic=control.characteristic,
        tolerance=control.tolerance,
        diameter=True,
        projected_zone_height_mm=control.projected_zone_height_mm,
        label=control.key,
    )


@pytest.mark.parametrize("path", ("model", "drawing", "projection"))
@pytest.mark.parametrize("migrated", (False, True))
def test_native_projected_writers_keep_height_after_void_seed_and_conversion(
    projected_native: SimpleNamespace, path: str, migrated: bool
) -> None:
    state = projected_native
    state.gtol.format = 1 if migrated else 2
    _author_native(state, path)
    assert state.gtol.seed_calls == int(migrated)
    assert state.gtol.format == 2
    assert state.frame.writes == [_PROJECTED_XML]
    assert gtol_frame_signature(state.frame.GetSymbolXml()).projected_zone_height_mm == 31.3


@pytest.mark.parametrize("path", ("model", "drawing", "projection"))
def test_native_ordinary_migration_never_repopulates_current_frame(
    projected_native: SimpleNamespace, path: str
) -> None:
    state = projected_native
    state.gtol.format = 1
    _author_native(state, path, None)
    assert state.gtol.seed_calls == 1
    assert state.frame.writes == []
    assert gtol_frame_signature(state.frame.GetSymbolXml()).projected_zone_height_mm is None


@pytest.mark.parametrize("path", ("model", "drawing", "projection"))
@pytest.mark.parametrize("result", (False, None, 1, object()))
def test_native_projected_xml_requires_actual_bool_success(
    projected_native: SimpleNamespace, path: str, result: Any
) -> None:
    projected_native.frame.write_result = result
    with pytest.raises(RuntimeError, match="rejected"):
        _author_native(projected_native, path)
    assert projected_native.frame.xml == _ORDINARY_XML


@pytest.mark.parametrize("path", ("model", "drawing", "projection"))
@pytest.mark.parametrize("failure", ("seed", "convertible", "conversion", "add"))
def test_native_projected_migration_refusals_are_not_success(
    projected_native: SimpleNamespace, path: str, failure: str
) -> None:
    state = projected_native
    if failure == "add":
        state.gtol.frame_count = 0
        state.gtol.add_result = False
    else:
        state.gtol.format = 1
        if failure == "seed":
            state.gtol.seed_result = False
        elif failure == "convertible":
            state.gtol.convertible = False
        else:
            state.gtol.conversion_error = 1
    message = {
        "seed": "SetFrameValues2 failed|failed to seed",
        "convertible": "cannot convert|cannot migrate",
        "conversion": "ConvertFormat error|migration failed",
        "add": "failed to add current frame|failed to create feature-control frame",
    }[failure]
    with pytest.raises(RuntimeError, match=message):
        _author_native(state, path)
    assert state.frame.writes == []


@pytest.mark.parametrize("path", ("model", "drawing", "projection"))
@pytest.mark.parametrize(
    "readback",
    (
        _ORDINARY_XML,
        _PROJECTED_XML.replace(">31.3<", ">39.2375<"),
        _PROJECTED_XML.replace("<Projection>31.3</Projection>", ""),
        _PROJECTED_XML.replace("<ProjectedToleranceZone>true</ProjectedToleranceZone>", ""),
        _PROJECTED_XML.replace("<PrimaryRangeSymbol>phi</PrimaryRangeSymbol>", ""),
        _PROJECTED_XML.replace("GTOL-PERP", "GTOL-POSI"),
    ),
    ids=(
        "projection-lost", "wrong-height", "height-omitted", "symbol-omitted",
        "diameter-lost", "characteristic-changed",
    ),
)
def test_native_projected_semantic_readback_rejects_loss_or_wrong_height(
    projected_native: SimpleNamespace, path: str, readback: str
) -> None:
    projected_native.frame.readback = readback
    with pytest.raises((RuntimeError, ValueError)):
        _author_native(projected_native, path)


@pytest.mark.parametrize("path", ("model", "drawing", "projection"))
@pytest.mark.parametrize("readback", (None, True, "method"))
def test_native_projected_readback_requires_bstr_not_bound_method(
    projected_native: SimpleNamespace, path: str, readback: Any
) -> None:
    projected_native.frame.readback = (
        projected_native.frame.GetSymbolXml if readback == "method" else readback
    )
    with pytest.raises(RuntimeError, match="not a string"):
        _author_native(projected_native, path)


@pytest.mark.parametrize("path", ("model", "drawing", "projection"))
def test_native_projected_empty_bstr_has_labelled_parse_refusal(
    projected_native: SimpleNamespace, path: str
) -> None:
    projected_native.frame.readback = ""
    with pytest.raises(RuntimeError, match="invalid .*XML readback") as info:
        _author_native(projected_native, path)
    assert "projected_axis" in str(info.value)


@pytest.mark.parametrize("path", ("drawing", "projection"))
def test_native_projected_zone_loss_on_drawing_rebuild_refuses(
    projected_native: SimpleNamespace, path: str
) -> None:
    state = projected_native
    state.on_rebuild = lambda: setattr(state.frame, "xml", _ORDINARY_XML)
    with pytest.raises(RuntimeError, match="changed semantics after rebuild"):
        _author_native(state, path)


@pytest.mark.parametrize("path", ("model", "drawing", "projection"))
@pytest.mark.parametrize("member", ("seed_result", "convertible", "add_result"))
@pytest.mark.parametrize("result", (1, object()))
def test_native_migration_bool_guards_reject_truthy_non_bool_results(
    projected_native: SimpleNamespace, path: str, member: str, result: Any
) -> None:
    state = projected_native
    if member == "add_result":
        state.gtol.frame_count = 0
        message = "failed to add current frame|failed to create feature-control frame"
    else:
        state.gtol.format = 1
        message = (
            "SetFrameValues2 failed|failed to seed"
            if member == "seed_result"
            else "cannot convert|cannot migrate"
        )
    setattr(state.gtol, member, result)
    with pytest.raises(RuntimeError, match=message):
        _author_native(state, path)


def test_direct_projected_height_validates_before_native_insertion(
    projected_native: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_native_call(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("invalid projected height reached native selection or insertion")

    monkeypatch.setattr(
        _drawing_common, "_select_annotation_entity", unexpected_native_call
    )
    monkeypatch.setattr(
        projected_native.adapter.currentModel, "InsertGtol", unexpected_native_call
    )
    with pytest.raises(ValueError, match="finite and positive"):
        _drawing_common.add_feature_control_frame(
            projected_native.adapter,
            projected_native.view,
            edge_xy=(0.0, 0.0),
            frame_xy=(0.1, 0.2),
            characteristic="perpendicularity",
            tolerance="0.010",
            projected_zone_height_mm=float("nan"),
            label="invalid projected axis",
        )


@pytest.mark.parametrize("readback", (None, True, "method"))
def test_spec_projection_own_bstr_guard_is_discriminating(
    projected_native: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, readback: Any
) -> None:
    state = projected_native
    state.frame.xml = _PROJECTED_XML
    state.frame.readback = state.frame.GetSymbolXml if readback == "method" else readback
    # Isolate the receiver's getter guard from the direct helper's guard.
    monkeypatch.setattr(
        _drawing_common, "add_feature_control_frame", lambda *_args, **_kwargs: state.gtol
    )
    with pytest.raises(RuntimeError, match="not a string"):
        _author_native(state, "projection")


@pytest.mark.parametrize("path", ("drawing", "projection"))
@pytest.mark.parametrize("readback", (None, True, "method"))
def test_post_rebuild_bstr_guard_is_discriminating(
    projected_native: SimpleNamespace, path: str, readback: Any
) -> None:
    state = projected_native
    changed = state.frame.GetSymbolXml if readback == "method" else readback
    state.on_rebuild = lambda: setattr(state.frame, "readback", changed)
    with pytest.raises(RuntimeError, match="not a string"):
        _author_native(state, path)


@pytest.mark.parametrize("path", ("drawing", "projection"))
def test_post_rebuild_semantics_use_freshly_fetched_frame(
    projected_native: SimpleNamespace, path: str
) -> None:
    state = projected_native
    state.on_rebuild = lambda: setattr(state.gtol, "frame", _NativeFrame())
    with pytest.raises(RuntimeError, match="changed semantics after rebuild"):
        _author_native(state, path)


@pytest.mark.parametrize("path", ("model", "drawing", "projection"))
def test_projected_writers_capture_canonical_native_xml_unit_evidence(
    projected_native: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        _part_pmi._telemetry, "event",
        lambda name, **fields: events.append((name, fields)),
    )
    _author_native(projected_native, path)
    observed = [
        fields for name, fields in events if name == "native.projected_zone_readback"
    ]
    assert len(observed) == 1
    receipt = observed[0]
    assert receipt["expected_xml"] == _PROJECTED_XML
    assert receipt["applied_xml"] == projected_native.frame.xml
    assert receipt["readback_projected_zone_height_xml_numeric"] == 31.3
    assert receipt["length_conversion_factor_raw"] == 1000.0
    assert receipt["document_type"] == (1 if path == "model" else 3)
    assert receipt["physical_projection_unit_verified"] is False
    assert receipt["physical_projection_unit_qualification"] == "UNQUALIFIED"
    if path == "model":
        gtol_event = next(fields for name, fields in events if name == "pmi.gtol")
        assert gtol_event["expected_xml"] == _PROJECTED_XML
        assert gtol_event["applied_xml"] == projected_native.frame.xml


@pytest.mark.parametrize("path", ("model", "drawing", "projection"))
def test_ordinary_native_writers_skip_projected_capture_and_unit_getters(
    projected_native: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    def unexpected_capture(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("ordinary frame reached projected native evidence capture")

    monkeypatch.setattr(_part_pmi, "capture_projected_gtol", unexpected_capture)
    monkeypatch.setattr(_drawing_common, "capture_projected_gtol", unexpected_capture)
    monkeypatch.setattr(
        projected_native.adapter.currentModel, "GetUserUnit", unexpected_capture
    )
    _author_native(projected_native, path, None)


def test_frame_xml_carries_the_translation_modifier_on_its_datum_only() -> None:
    xml = gtol_frame_xml(
        "position", "0.05", datums=("B", "C"), translated=("C",)
    )

    signature = gtol_frame_signature(xml)

    assert signature.datums == ("B", "C")
    assert signature.translated == ("C",)
    plain = gtol_frame_xml("position", "0.05", datums=("B",))
    assert gtol_frame_signature(plain).translated == ()
    with pytest.raises(ValueError, match="non-primary datum"):
        gtol_frame_xml("position", "0.05", datums=("B", "C"), translated=("B",))
    with pytest.raises(ValueError, match="non-primary datum"):
        gtol_frame_xml("position", "0.05", datums=("B",), translated=("D",))


def test_translation_modifier_is_the_symbol_code_in_its_letter() -> None:
    # Farm run 20261009T204136744Z printed this XML as "C | B<triangle>"
    # with no vector; the <Translation> flag printed "[0,0,0]" beside the
    # triangle (20261009T174542021Z / 20261009T182549169Z) and is not used.
    from xml.etree import ElementTree

    assert TRANSLATION_GLYPH == "<MOD-TRANS2>"
    xml = gtol_frame_xml("position", "0.05", datums=("B", "C"), translated=("C",))
    plain, moved = ElementTree.fromstring(xml).iter("DatumCompartment")
    shape = [
        [(child.tag, child.findtext("DatumLetter")) for child in compartment]
        for compartment in (plain, moved)
    ]
    assert shape == [[("DatumDetail", "B")], [("DatumDetail", "C<MOD-TRANS2>")]]
    # The glyph is XML-escaped text in the letter, not markup.
    assert "<DatumLetter>C&lt;MOD-TRANS2&gt;</DatumLetter>" in xml
    assert "Translation" not in xml


@pytest.mark.parametrize(
    ("texts", "problem"),
    (
        # Farm run 20261009T174542021Z, rear slot frame DetailItem507.
        (("<GTOL-POSI>", "0.05", "C", "B", "<MOD-TRANS2>", "[0,0,0]"), "translation vector"),
        (("<GTOL-POSI>", "0.05", "C", "B", "<MOD-TRANS2>", "[false,false,false]"), "translation vector"),
        (("<GTOL-POSI>", "0.05", "C", "B"), "0 translation modifier"),
        (("<GTOL-POSI>", "0.05", "C", "<MOD-TRANS2>", "B"), "off datum B"),
        # Farm run 20261009T204136744Z, the same frame, inline.
        (("<GTOL-POSI>", "0.05", "C", "B", "<MOD-TRANS2>"), ""),
        (("<GTOL-POSI>", "0.05", "C", "B<MOD-TRANS2>"), ""),
    ),
)
def test_translation_prints_the_modifier_after_its_letter(
    texts: tuple[str, ...], problem: str
) -> None:
    found = translation_print_problem(texts, ("B",))
    assert (problem in found and found) if problem else found == ""
