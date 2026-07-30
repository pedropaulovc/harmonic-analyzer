from __future__ import annotations

from types import SimpleNamespace

import pytest

from _drawing_common import PmiDrawingPlacement
from _gtol_spec import (
    ConeFace,
    CylinderFace,
    GeometricControl,
    PartDatum,
    PlanarFace,
    SphereFace,
    TorusFace,
    gtol_frame_signature,
    validate_part_pmi,
)
from _part_pmi import _FaceGeometry, _face_matches


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
    geometry = _FaceGeometry(
        face=SimpleNamespace(),
        identity=4002,
        parameters=(0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 5.04e-3),
        outward_normal=None,
        box=(0.0, 0.0, 0.0, 1.0, 1.0, 1.0),
    )

    assert not _face_matches(geometry, CylinderFace(10.0, tolerance_mm=0.05))
    assert _face_matches(geometry, CylinderFace(10.0, tolerance_mm=0.1))


def test_cylinder_face_can_disambiguate_by_x_and_y_stations() -> None:
    geometry = _FaceGeometry(
        face=SimpleNamespace(),
        identity=4002,
        parameters=(0.011, -0.04, 0.008, 0.0, 1.0, 0.0, 4e-3),
        outward_normal=None,
        box=(0.007, 0.008, 0.004, 0.015, 0.018, 0.012),
    )

    assert _face_matches(
        geometry, CylinderFace(8.0, contains_x_mm=11.0, contains_y_mm=13.0)
    )
    assert not _face_matches(
        geometry, CylinderFace(8.0, contains_x_mm=21.0, contains_y_mm=13.0)
    )


def test_cone_face_matches_live_coneparams2_contract() -> None:
    geometry = _FaceGeometry(
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

    assert _face_matches(
        geometry, ConeFace(0.596809, contains_x_mm=22.5, tolerance_degrees=0.001)
    )
    assert not _face_matches(geometry, ConeFace(1.0))


def test_planar_face_can_disambiguate_coplanar_trunnions_by_z_station() -> None:
    geometry = _FaceGeometry(
        face=SimpleNamespace(),
        identity=4001,
        parameters=(-0.510265461, -0.860016953, 0.0, 0.0043265, 0.002567, 0.097917),
        outward_normal=(0.510265461, 0.860016953, 0.0),
        box=(0.0, 0.002567, 0.0762, 0.0043265, 0.005134, 0.097917),
    )

    assert _face_matches(
        geometry,
        PlanarFace(
            (0.510265461, 0.860016953, 0.0),
            4.415327,
            contains_z_mm=87.0585,
        ),
    )
    assert not _face_matches(
        geometry,
        PlanarFace(
            (0.510265461, 0.860016953, 0.0),
            4.415327,
            contains_z_mm=-87.0585,
        ),
    )


def test_sphere_identity_is_not_cone_identity() -> None:
    geometry = _FaceGeometry(
        face=SimpleNamespace(),
        identity=4004,
        parameters=(0.0, 0.0252, 0.0, 0.0065),
        outward_normal=None,
        box=(),
    )

    assert _face_matches(geometry, SphereFace(13.0, center_mm=(0.0, 25.2, 0.0)))


def test_torus_face_matches_generating_radii_and_center() -> None:
    geometry = _FaceGeometry(
        face=SimpleNamespace(),
        identity=4005,
        parameters=(0.0, 0.0085, 0.0, 0.0, 1.0, 0.0, 0.0015, 0.005),
        outward_normal=None,
        box=(),
    )

    assert _face_matches(
        geometry, TorusFace(1.5, 5.0, center_mm=(0.0, 8.5, 0.0))
    )
    assert not _face_matches(geometry, TorusFace(2.0, 5.0))


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
