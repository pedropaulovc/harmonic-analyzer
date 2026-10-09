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
    TRANSLATION_FORMS,
    TRANSLATION_GLYPH,
    SphereFace,
    TorusFace,
    gtol_frame_datums,
    gtol_frame_signature,
    gtol_frame_xml,
    translation_print_problem,
    validate_part_pmi,
)
from _part_pmi import _FaceGeometry, _face_matches



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
        "position", "0.05", datums=("B", "C"), translated=("C",), translation_form="inline"
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


def test_planar_face_pins_one_of_four_coplanar_cap_seats_by_x_and_z() -> None:
    """The top frame's four cap-recess floors share one plane and one area.

    Only both plan stations together name one of them, so a control that
    pins just the plane -- or pins the wrong corner -- must not match.
    """
    geometry = _FaceGeometry(
        face=SimpleNamespace(),
        identity=4001,
        parameters=(0.0, -1.0, 0.0, 0.197, 0.00645, 0.112),
        outward_normal=(0.0, 1.0, 0.0),
        box=(0.18325, 0.00645, 0.09825, 0.21075, 0.00645, 0.12575),
    )

    assert _face_matches(
        geometry,
        PlanarFace((0.0, 1.0, 0.0), 6.45, contains_x_mm=197.0, contains_z_mm=112.0),
    )
    assert not _face_matches(
        geometry,
        PlanarFace((0.0, 1.0, 0.0), 6.45, contains_x_mm=-197.0, contains_z_mm=112.0),
    )
    assert not _face_matches(
        geometry,
        PlanarFace((0.0, 1.0, 0.0), 6.45, contains_x_mm=197.0, contains_z_mm=-112.0),
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


def test_each_translation_form_states_the_modifier_on_its_datum_only() -> None:
    # User ruling: the modifier's symbol code inline in the letter first; the
    # <Translation> flag (which prints "[0,0,0]", farm runs
    # 20261009T174542021Z / 20261009T182549169Z) as the last form.
    from xml.etree import ElementTree

    assert TRANSLATION_FORMS == ("inline", "flag")
    assert TRANSLATION_GLYPH == "<MOD-TRANS2>"
    shapes = {}
    for form in TRANSLATION_FORMS:
        xml = gtol_frame_xml(
            "position", "0.05", datums=("B", "C"), translated=("C",),
            translation_form=form,
        )
        signature = gtol_frame_signature(xml)
        assert signature.datums == ("B", "C"), form
        assert signature.translated == ("C",), form
        plain, moved = ElementTree.fromstring(xml).iter("DatumCompartment")
        assert [(c.tag, c.findtext("DatumLetter")) for c in plain] == [("DatumDetail", "B")]
        shapes[form] = [
            (child.tag, child.findtext("DatumLetter") if child.tag == "DatumDetail" else child.text)
            for child in moved
        ]
    assert shapes == {
        "inline": [("DatumDetail", "C<MOD-TRANS2>")],
        "flag": [("Translation", "true"), ("DatumDetail", "C")],
    }
    # The glyph is XML-escaped text in the letter, not markup.
    inline = gtol_frame_xml(
        "position", "0.05", datums=("B", "C"), translated=("C",), translation_form="inline"
    )
    assert "<DatumLetter>C&lt;MOD-TRANS2&gt;</DatumLetter>" in inline
    assert "Translation" not in inline


@pytest.mark.parametrize(
    ("texts", "zero_vector", "problem"),
    (
        # Farm run 20261009T174542021Z, rear slot frame DetailItem507.
        (("<GTOL-POSI>", "0.05", "C", "B", "<MOD-TRANS2>", "[0,0,0]"), False, "translation vector"),
        (("<GTOL-POSI>", "0.05", "C", "B", "<MOD-TRANS2>", "[0,0,0]"), True, ""),
        (("<GTOL-POSI>", "0.05", "C", "B", "<MOD-TRANS2>", "[false,false,false]"), True, "translation vector"),
        (("<GTOL-POSI>", "0.05", "C", "B", "[0,0,0]", "<MOD-TRANS2>"), True, "translation vector"),
        (("<GTOL-POSI>", "0.05", "C", "B"), False, "0 translation modifier"),
        (("<GTOL-POSI>", "0.05", "C", "<MOD-TRANS2>", "B"), False, "off datum B"),
        (("<GTOL-POSI>", "0.05", "C", "B", "<MOD-TRANS2>"), False, ""),
        (("<GTOL-POSI>", "0.05", "C", "B<MOD-TRANS2>"), False, ""),
    ),
)
def test_translation_prints_the_modifier_after_its_letter(
    texts: tuple[str, ...], zero_vector: bool, problem: str
) -> None:
    found = translation_print_problem(texts, ("B",), zero_vector=zero_vector)
    assert (problem in found and found) if problem else found == ""
