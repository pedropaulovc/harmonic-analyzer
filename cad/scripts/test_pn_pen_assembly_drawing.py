"""Offline contract for the pen fitter package (MHA-PN-000)."""

from pathlib import Path

import build_pn_pen_assembly as builder
import draw_pn_pen_assembly as drawing
import pn_pen_assembly_spec as spec
import pn_pen_carriage_geom as carriage
import pn_pen_v_block_spec as v_block
import vn_pen_rod_set_screw_spec as rod_set_screw
from _drawing_registry import DRAWINGS_BY_NAME
from _named_views import octant_axes, octant_view_name
from _simplified_names import simplified_name


def test_pen_package_keeps_registry_outputs() -> None:
    registered = DRAWINGS_BY_NAME["pn_pen_assembly"]
    assert registered.source_kind == "assembly"
    assert registered.part == "pn_pen"
    assert drawing.SOURCE == registered.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        registered.outputs["slddrw"],
        registered.outputs["pdf"],
        registered.outputs["png"],
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "build_simple_three_view_drawing" not in source


def test_pen_package_is_three_landscape_sheets_at_half_scale() -> None:
    assert drawing.SHEET_NAMES == (
        "ASSEMBLED VIEWS + SETTINGS",
        "EXPLODED VIEW + BOM",
        "ASSEMBLY STEPS",
    )
    assert set(drawing.SHEET_LAYOUTS.values()) == {
        DRAWINGS_BY_NAME["pn_pen_assembly"].layout
    }
    assert set(drawing.SHEET_SCALES.values()) == {(1.0, 2.0)}
    assert drawing.EXPLODED_SCALES[0] == drawing.SHEET_SCALE


def test_bom_covers_every_family_in_builder_order_with_registry_identity() -> None:
    assert drawing.BOM_COMPONENTS == spec.BOM_ORDER
    assert set(drawing.BALLOON_ANCHORS) == set(spec.BOM_ORDER)
    assert [spec.ITEM[stem] for stem in spec.BOM_ORDER] == list(
        range(1, len(spec.BOM_ORDER) + 1)
    )
    # The builder inserts the hanger, the rod, then the riders in RIDERS
    # order, then the hanger screw and its nuts: the BOM's item order.
    riders = tuple(stem for stem, *_ in builder.RIDERS)
    assert spec.BOM_ORDER[2 : 2 + len(riders)] == riders
    assert all(
        number.startswith("MHA-") for number in drawing.BOM_PART_NUMBERS.values()
    )
    assert drawing.BOM_SKUS[spec.HANGER] == drawing.MADE_PART_SKU
    assert drawing.BOM_SKUS[spec.HANGER_JAM_NUT] != drawing.MADE_PART_SKU


def test_explode_names_match_the_builder() -> None:
    assert drawing.EXPLODED_VIEW_NAMES == {
        "Default": spec.EXPLODED_VIEW_NAME,
        "Default Simplified": simplified_name(spec.EXPLODED_VIEW_NAME),
    }
    for configuration, name in drawing.EXPLODED_VIEW_NAMES.items():
        assert builder.pn_exploded_view_name(configuration) == name


def test_exploded_octant_faces_the_set_screw_tap_and_explodes_along_it() -> None:
    assert drawing.EXPLODED_ORIENTATION == octant_view_name(*spec.EXPLODED_OCTANT)
    # The tap opens on the block's front face (local -Z, BODY_Z0).
    rows = carriage.BLOCK_ROWS
    normal = tuple(-rows[2][axis] for axis in range(3))
    viewer = octant_axes(*spec.EXPLODED_OCTANT)[2]
    assert sum(n * v for n, v in zip(normal, viewer)) > 0.5
    moves = [0.0, 0.0, 0.0]
    for _label, stems, key, distance in spec.EXPLODE_STEPS:
        if stems == (spec.ROD_SET_SCREW,):
            moves["xyz".index(key)] += distance
    length = sum(value * value for value in moves) ** 0.5
    # Straight out of the tap, and past the screw's own recess in it.
    assert all(abs(m / length - n) < 1e-9 for m, n in zip(moves, normal))
    assert length > v_block.SET_SCREW_TAP_LENGTH + 2 * rod_set_screw.LENGTH


def test_every_setting_is_printed_with_a_callout_beside_its_detail() -> None:
    printed = {
        name for points in drawing.DIMENSION_TEXT_POINTS.values() for name in points
    }
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    assert printed == marked == set(spec.DIMENSION_CALLOUTS)
    details = {detail.key: detail for detail in drawing.DETAILS}
    for key, points in drawing.DIMENSION_TEXT_POINTS.items():
        detail = details[key]
        assert detail.feature is not None
        for xyz in points.values():
            # The plan detail projects Y away; the front detail projects Z.
            # A text may stand outside the crop circle (the nib preset's sits
            # beyond the nib tip), but beside it, not across the sheet.
            axes = (0, 2) if detail.orientation == "*Top" else (0, 1)
            offset = [xyz[axis] - detail.model_centre[axis] for axis in axes]
            assert sum(value * value for value in offset) ** 0.5 < 2 * detail.radius_mm


def test_text_blocks_respect_the_measured_note_width() -> None:
    for block, width in (
        (drawing.ASSEMBLY_STEPS, drawing.STEPS_LINE_WIDTH),
        (drawing.ASSEMBLY_CHECKS, drawing.STEPS_LINE_WIDTH),
        (drawing.SETTINGS_NOTE, drawing.SETTINGS_NOTE_WIDTH),
    ):
        assert max(len(line) for line in block.splitlines()) <= width
