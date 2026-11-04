"""Offline contracts for the MHA-CH-06-TL-VN-82 feed nut (the ReliaBot screw's brass flange nut, as fitted)."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm_tl_vn_oblique_feed_nut as part
import ch_rocker_arm_tl_oblique_feed_block_spec as feed_block
import ch_rocker_arm_tl_vn_oblique_feed_nut_spec as spec
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_vn_oblique_leadscrew_stock_spec as leadscrew_stock
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _mcmaster_91771a112 import DIMS as SCREW_DIMS

STEM = "ch-rocker-arm-tl-vn-oblique-feed-nut"
RETIRED = (
    "ch-rocker-arm-tl-oblique-feed-nut",  # MHA-CH-06-TL-27
    "ch-rocker-arm-tl-vn-oblique-nut-dowel",  # MHA-CH-06-TL-VN-81
    "ch-rocker-arm-tl-vn-oblique-nut-screw",  # MHA-CH-06-TL-VN-66
)


def test_registry_row_is_the_nut_bought_with_the_screw() -> None:
    # Owner ruling 2026-11-04 (#2177, option B): the nut ships with the
    # ReliaBot lead screw, so it carries that listing's supplier and SKU.
    row = _config.parts(STEM)
    assert row["number"] == spec.NUMBER == "MHA-CH-06-TL-VN-82"
    assert spec.PART_NAME == part.PART_NAME == STEM
    assert row["supplier"] == spec.SUPPLIER == leadscrew_stock.SUPPLIER
    assert row["supplier_skus"] == [spec.SKU] == [leadscrew_stock.SKU]
    assert row["process"] == "purchased"
    assert row["drawing_unit"] == "mm"
    assert row["material"] == spec.MATERIAL == "Brass"
    assert row["quantity"] == spec.QUANTITY == 1


def test_retired_nut_dowel_and_screw_left_no_registry_or_drawing() -> None:
    root = Path(__file__).resolve().parents[1]
    for stem in RETIRED:
        assert not (root / "config" / "parts" / f"{stem}.yaml").exists(), stem
        assert stem.replace("-", "_") not in DRAWINGS_BY_NAME, stem
        assert not Path(__file__).with_name(f"build_{stem.replace('-', '_')}.py").exists(), stem


def test_sourced_envelope_and_the_faced_length() -> None:
    # The listing's dimension image: spigot, flange and body make its 15
    # overall; the fitter faces the 1.5 spigot off, leaving 13.5.
    assert (spec.FLANGE_DIA, spec.FLANGE_THICK) == (22.0, 3.5)
    assert (spec.HOLE_DIA, spec.HOLE_PCD, len(spec.HOLE_ANGLES_DEG)) == (3.5, 16.0, 4)
    assert (spec.BODY_DIA, spec.BODY_LENGTH, spec.SPIGOT_LENGTH) == (10.2, 10.0, 1.5)
    assert spec.SPIGOT_LENGTH + spec.LENGTH == spec.SUPPLIED_LENGTH == 15.0
    assert spec.LENGTH == spec.FLANGE_THICK + spec.BODY_LENGTH == 13.5
    assert spec.LENGTH >= 5.0 * leadscrew_stock.LEAD
    # The thread is modelled as a plain bore at the Tr8x2 minor diameter.
    assert spec.BORE_DIA == leadscrew_stock.MINOR_DIA == 6.0
    assert spec.LEAD == leadscrew_stock.LEAD


def test_receipt_limits_bracket_the_image_and_print_in_f1() -> None:
    # UNVERIFIED nominals: F1 measures the nut against these before the lug's
    # taps are transferred, in the nut's own millimetres.
    assert spec.FLANGE_THICK_MIN < spec.FLANGE_THICK < spec.FLANGE_THICK_MAX
    assert spec.HOLE_DIA_MIN < spec.HOLE_DIA < spec.HOLE_DIA_MAX
    assert spec.BODY_DIA < spec.BODY_DIA_MAX
    assert spec.FLANGE_DIA < spec.FLANGE_DIA_MAX
    assert spec.LENGTH < spec.LENGTH_MAX
    assert spec.HOLE_STATION_BAND == spec.HOLE_PCD_BAND / 2.0
    assert spec.RECEIPT_TEXT == (
        f"FLANGE {spec.FLANGE_THICK_MIN:.1f}-{spec.FLANGE_THICK_MAX:.1f} MM THICK, "
        f"BODY Ø{spec.BODY_DIA_MAX:.1f} MM MAX, 4 HOLES "
        f"Ø{spec.HOLE_DIA_MIN:.2f}-{spec.HOLE_DIA_MAX:.2f} MM ON A Ø16 "
        f"±{spec.HOLE_PCD_BAND:.1f} MM PCD, FACED LENGTH {spec.LENGTH_MAX:.1f} MM MAX"
    )
    # The #29 transfer spot enters the least hole; the largest hole at its
    # worst station still leaves brass between it and the largest body.
    assert feed_block.TRANSFER_SPOT_DIA < spec.HOLE_DIA_MIN
    assert spec.HOLE_PCD / 2.0 - spec.HOLE_STATION_BAND - spec.HOLE_DIA_MAX / 2.0 > (
        spec.BODY_DIA_MAX / 2.0
    )
    # The faced nut's reach is the near-KP08 feed gap's.
    assert spec.REACH == spec.LENGTH_MAX
    assert feed_block.NUT_REACH_X[0] == pytest.approx(feed_block.NUT_FACE_X - spec.LENGTH_MAX)


def test_countersinks_seat_the_flat_heads_proud_and_off_the_body() -> None:
    tan = math.tan(math.radians(spec.CSK_ANGLE / 2.0))
    assert spec.CSK_ANGLE == SCREW_DIMS.head_angle_deg == 82.0
    # The head's cone meets each mouth below its top Ø, so it stands proud at
    # the least, nominal and largest (opened) countersink alike.
    for mouth, proud in (
        (spec.CSK_DIA_MIN, spec.HEAD_PROUD_MAX),
        (spec.CSK_DIA, spec.HEAD_PROUD_NOMINAL),
        (spec.CSK_DIA_OPEN_MAX, spec.HEAD_PROUD_MIN),
    ):
        assert proud == pytest.approx((SCREW_DIMS.head_dia - mouth) / (2.0 * tan))
        assert proud > 0.0
    assert spec.CSK_DIA_OPEN_MAX == spec.CSK_CUTTER_DIA_MAX == pytest.approx(3.0 / 16.0 * 25.4)
    assert spec.CSK_DIA + spec.CSK_DIA_BAND < spec.CSK_DIA_OPEN_MAX
    # F2's head limit is the catalogue head the proud and body checks use.
    assert spec.SCREW_HEAD_DIA_MAX == SCREW_DIMS.head_dia == pytest.approx(0.212 * 25.4)
    # The countersink never runs through the thinnest flange.
    assert spec.CSK_DEPTH == pytest.approx((spec.CSK_DIA - spec.HOLE_DIA) / (2.0 * tan))
    assert spec.CSK_DEPTH < spec.FLANGE_THICK_MIN
    # The Ø3/16 cutter's cone stays off the largest body at the worst hole
    # station; a Ø1/4 cutter would gouge it.
    def cutter_to_body(cutter: float) -> float:
        return (
            spec.HOLE_PCD / 2.0 - spec.HOLE_STATION_BAND - spec.CSK_ECCENTRICITY_MAX
            - cutter / 2.0 - spec.BODY_DIA_MAX / 2.0
        )

    assert spec.CSK_CUTTER_TO_BODY == pytest.approx(cutter_to_body(spec.CSK_CUTTER_DIA_MAX))
    assert spec.CSK_CUTTER_TO_BODY > 0.0
    assert cutter_to_body(0.25 * 25.4) < 0.0
    # The heads bear on each cone between the underhead fillet and the least
    # mouth.
    assert spec.CSK_BEARING_INNER_DIA == max(spec.HOLE_DIA_MAX, spec.SCREW_FILLET_DIA_MAX)
    assert spec.CSK_BEARING_AREA_MIN == pytest.approx(
        math.pi / 4.0 * (spec.CSK_DIA_MIN**2 - spec.CSK_BEARING_INNER_DIA**2)
    )
    assert spec.CSK_BEARING_AREA_MIN > 0.0


def test_flat_heads_engage_the_lug_at_rule_18_and_stop_inside_it() -> None:
    assert spec.SCREW_COUNT == len(spec.HOLE_ANGLES_DEG) == 4
    assert spec.SCREW_LENGTH == SCREW_DIMS.length == pytest.approx(0.625 * 25.4)
    assert spec.SCREW_GRIP == pytest.approx(spec.FLANGE_THICK + spec.HEAD_PROUD_NOMINAL)
    assert spec.SCREW_ENGAGEMENT == pytest.approx(spec.SCREW_LENGTH - spec.SCREW_GRIP)
    full = (
        spec.SCREW_LENGTH - 0.03 * 25.4
        - (spec.FLANGE_THICK_MAX + spec.HEAD_PROUD_MAX)
        - leadscrew.TAP_MOUTH_BREAK
        - 2.0 * SCREW_DIMS.pitch
    )
    assert spec.SCREW_FULL_THREAD_MIN == pytest.approx(full)
    assert full >= leadscrew.ENGAGEMENT_TARGET_D * spec.SCREW_MAJOR
    reach = spec.SCREW_LENGTH - spec.FLANGE_THICK_MIN - spec.HEAD_PROUD_MIN
    assert spec.SCREW_TIP_REACH_MAX == pytest.approx(reach)
    assert reach < feed_block.LUG_WIDTH
    # The heads stand short of the body's end, inside the nut's own reach.
    assert spec.FLANGE_THICK_MAX + spec.HEAD_PROUD_MAX < spec.LENGTH


def test_model_profile_holes_and_countersinks_follow_the_envelope() -> None:
    r_bore, r_body, r_flange = spec.BORE_DIA / 2.0, spec.BODY_DIA / 2.0, spec.FLANGE_DIA / 2.0
    assert part.profile_points() == [
        (r_bore, 0.0), (r_flange, 0.0), (r_flange, spec.FLANGE_THICK),
        (r_body, spec.FLANGE_THICK), (r_body, spec.LENGTH), (r_bore, spec.LENGTH),
    ]
    for (x, z), angle in zip(spec.HOLE_CENTRES, spec.HOLE_ANGLES_DEG, strict=True):
        assert math.hypot(x, z) == pytest.approx(spec.HOLE_PCD / 2.0)
        assert math.degrees(math.atan2(z, x)) % 360.0 == pytest.approx(angle)
    assert part.hole_sketch_points() == [(x, -z) for x, z in spec.HOLE_CENTRES]
    # One countersink per hole: Front's u is model x, Right's is -z.
    axes = sorted(
        (u, 0.0) if plane == "Front" else (0.0, -u) for plane, u in spec.COUNTERSINK_AXES
    )
    assert axes == pytest.approx(sorted(spec.HOLE_CENTRES))
    tan = math.tan(math.radians(spec.CSK_ANGLE / 2.0))
    for _plane, u in spec.COUNTERSINK_AXES:
        top, outer, apex = spec.countersink_points(u)
        assert top == (u, spec.CSK_TOP_Y) and apex == (u, spec.CSK_APEX_Y)
        # The outer corner lies on the 82° cone through the mouth on the face.
        radius = abs(outer[0] - u)
        assert outer[1] == spec.CSK_TOP_Y
        assert radius - spec.CSK_DIA / 2.0 == pytest.approx((spec.CSK_TOP_Y - spec.FLANGE_THICK) * tan)
        assert (spec.FLANGE_THICK - spec.CSK_APEX_Y) * tan == pytest.approx(spec.CSK_DIA / 2.0)
        # The overrun cone still clears the modelled body.
        assert abs(u) - radius > r_body


def test_volume_is_the_revolved_profile_less_holes_and_countersinks() -> None:
    tan = math.tan(math.radians(spec.CSK_ANGLE / 2.0))
    flange = math.pi / 4.0 * (spec.FLANGE_DIA**2 - spec.BORE_DIA**2) * spec.FLANGE_THICK
    body = math.pi / 4.0 * (spec.BODY_DIA**2 - spec.BORE_DIA**2) * spec.BODY_LENGTH
    assert spec.BODY_VOLUME_MM3 == pytest.approx(flange + body)
    hole = math.pi / 4.0 * spec.HOLE_DIA**2 * spec.FLANGE_THICK
    r_m, r_h = spec.CSK_DIA / 2.0, spec.HOLE_DIA / 2.0
    depth = (r_m - r_h) / tan
    frustum = math.pi * depth / 3.0 * (r_m**2 + r_m * r_h + r_h**2)
    countersink = frustum - math.pi * r_h**2 * depth
    assert spec.CSK_VOLUME_MM3 == pytest.approx(countersink)
    assert spec.VOLUME_MM3 == pytest.approx(flange + body - 4 * (hole + countersink))
    assert spec.VOLUME_MM3 == pytest.approx(1622.7, abs=0.1)


def test_supplier_references_are_the_dimension_image() -> None:
    values = {name: value for name, value, _orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS}
    assert values == {
        "SupplierBodyLength": spec.BODY_LENGTH,
        "SupplierFlangeThickness": spec.FLANGE_THICK,
        "SupplierFlangeDiameter": spec.FLANGE_DIA,
        "SupplierBodyDiameter": spec.BODY_DIA,
        "SupplierMountingHoleDiameter": spec.HOLE_DIA,
        "SupplierHolePitchDiameter": spec.HOLE_PCD,
    }
    assert set(spec.SUPPLIER_REFERENCE_UNITS.values()) == {"mm"}
    assert set(spec.SUPPLIER_REFERENCE_STARTS) == set(values) == set(spec.SUPPLIER_REFERENCE_FORMATS)
    assert spec.SUPPLIER_REFERENCE_FORMATS["SupplierMountingHoleDiameter"][3] == "4X"
    assert spec.SUPPLIER_REFERENCE_FORMATS["SupplierHolePitchDiameter"][3] == "PCD"
    # The hole chord starts on the +X hole's edge, the PCD chord on the -Z hole.
    assert spec.SUPPLIER_REFERENCE_STARTS["SupplierMountingHoleDiameter"] == (
        spec.HOLE_CENTRES[0][0], -spec.HOLE_DIA / 2.0,
    )
    assert spec.SUPPLIER_REFERENCE_STARTS["SupplierHolePitchDiameter"] == (0.0, -spec.HOLE_PCD / 2.0)
    assert spec.SUPPLIER_PRODUCT_URL == f"https://www.amazon.com/dp/{spec.SKU}"


def test_footer_note_fits_one_purchased_row_and_reads_cut_at_assembly() -> None:
    import _purchased_fastener_drawing as footer
    import draw_ch_rocker_arm_tl_vn_oblique_feed_nut as drawing

    # The note is one footer row: at the repo's widest 2.36 mm a character
    # (the ITEM row's budget basis) it stops at _FOOTER_RIGHT, clear of the
    # title block. The farm proof of 2026-11-04 measured the former
    # 107-character note 0.227 m wide, past it.
    lines = footer.note_lines(spec.DRAWING_NOTES, label=STEM)
    budget = math.floor((footer._FOOTER_RIGHT - footer._NOTE_X) / 0.00236)
    assert len(lines) == 1 and budget == 83
    assert all(len(line) <= budget for line in lines)
    # One row keeps the bottom captions at their floor, so the tall_top cells
    # the supplier lane budget assumes do not shrink.
    assert footer.view_band_bottom(spec.DRAWING_NOTES, label=STEM) == footer._LOWEST_CAPTION_Y
    # The builder writes the note where the sheet reads it, and the note is
    # fit-up work, so the sheet's general line reads cut at assembly.
    assert part.DRAWING_NOTES is spec.DRAWING_NOTES
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    [call] = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "build_purchased_part_drawing"
    ]
    keywords = {keyword.arg: keyword.value for keyword in call.keywords}
    assert isinstance(keywords["cut_to_suit"], ast.Constant) and keywords["cut_to_suit"].value is True


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_feed_nut as drawing
    from _machinist_review_mode import MachinistReviewMode

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_feed_nut"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert drawing.VIEW_LAYOUT == "tall_top"
    assert set(drawing.SHELVES) == {name for name, _v, _o in spec.SUPPLIER_REFERENCE_DIMENSIONS}
    # The builder centres each view less its lane reserves: Front's must
    # balance both ways and Top's left/right, or the views leave projection.
    for name, lanes in drawing.SUPPLIER_MARGINS.items():
        if name == "*Front":
            assert lanes[0] == pytest.approx(lanes[2]) and lanes[1] == pytest.approx(lanes[3])
        if name == "*Top":
            assert lanes[0] == pytest.approx(lanes[2])
    with pytest.raises(ValueError, match="leave the projection axis"):
        drawing.projection_margins({"*Front": (1.0, 0.0, 0.0, 0.0)})
    with pytest.raises(ValueError, match="leave the projection axis"):
        drawing.projection_margins({"*Top": (0.0, 0.0, 1.0, 0.0)})
    assert drawing.projection_margins({"*Right": (1.0, 0.0, 0.0, 0.0)}) == {"*Right": (1.0, 0.0, 0.0, 0.0)}
