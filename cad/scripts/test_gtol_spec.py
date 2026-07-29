from __future__ import annotations

from types import SimpleNamespace

import pytest

from _drawing_common import PmiDrawingPlacement
from _gtol_spec import (
    CylinderFace,
    GeometricControl,
    PartDatum,
    PlanarFace,
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
