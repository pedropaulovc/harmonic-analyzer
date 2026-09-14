"""Offline contracts for the pen-rod drawing."""

from __future__ import annotations

from pathlib import Path

import build_pen_rod as part
import draw_pen_rod as drawing
import pen_rod_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm, drill_process


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = pen_rod_spec.SURFACE_FINISHES
    assert control.key == "slide_face"
    assert control.roughness_um == 1.6
    assert control.face.normal == (-1, 0, 0)
    assert control.face.offset_mm == pen_rod_spec.ROD_SECTION / 2.0


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pen-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pen-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pen-rod_drawing.png")
    assert DRAWINGS_BY_NAME["pen_rod"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pen_rod_spec.DRAWING_DIMENSIONS
    marked = set().union(*pen_rod_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert (part.ROD_SECTION, part.ROD_LENGTH, part.WIRE_HOLE_Y) == (
        pen_rod_spec.ROD_SECTION,
        pen_rod_spec.ROD_LENGTH,
        pen_rod_spec.WIRE_HOLE_Y,
    )


def test_wire_hole_is_part_owned_and_consumers_derive_from_it() -> None:
    assert part.WIRE_HOLE_SPEC is pen_rod_spec.WIRE_HOLE_SPEC
    assert drawing.WIRE_HOLE_SPEC is pen_rod_spec.WIRE_HOLE_SPEC
    assert drawing._WIRE_HOLE_DIA == blind_cut_dia_mm(pen_rod_spec.WIRE_HOLE_SPEC)
    assert pen_rod_spec.WIRE_HOLE_Y < pen_rod_spec.ROD_LENGTH


def test_front_datum_edge_resolver_returns_visible_bottom_and_left(monkeypatch) -> None:
    hidden_bottom = object()
    visible_bottom = object()
    hidden_left = object()
    visible_left = object()
    wrong_length = object()
    half_section = drawing.ROD_SECTION / 2000.0
    section = drawing.ROD_SECTION / 1000.0
    length = drawing.ROD_LENGTH / 1000.0
    endpoints = {
        hidden_bottom: (-half_section, 0.0, 0.0, half_section, 0.0, 0.0),
        visible_bottom: (
            -half_section,
            0.0,
            section,
            half_section,
            0.0,
            section,
        ),
        hidden_left: (-half_section, 0.0, 0.0, -half_section, length, 0.0),
        visible_left: (
            -half_section,
            0.0,
            section,
            -half_section,
            length,
            section,
        ),
        wrong_length: (-half_section, 0.0, 0.0, -half_section, 0.120, 0.0),
    }

    class FakeSpan:
        def __init__(self) -> None:
            self.attributes = {}

        def set_attribute(self, key, value) -> None:
            self.attributes[key] = value

    span = FakeSpan()
    monkeypatch.setattr(
        drawing._telemetry.trace, "get_current_span", lambda context=None: span
    )
    monkeypatch.setattr(
        drawing,
        "visible_view_entities",
        lambda view, entity_kind, *, label: [
            hidden_bottom,
            visible_left,
            wrong_length,
            hidden_left,
            visible_bottom,
        ],
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda entity, interface: entity)
    monkeypatch.setattr(
        drawing,
        "_edge_endpoint_key",
        lambda adapter, edge: endpoints[edge],
    )

    resolver = drawing._visible_front_datum_edges.__wrapped__
    assert resolver(object(), object()) == (visible_bottom, visible_left)
    assert span.attributes == {
        "edges": 5,
        "bottom_matches": 2,
        "left_matches": 2,
    }


def test_linked_notes_define_remaining_square_rod_operations() -> None:
    notes = pen_rod_spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}
    assert drawing.TOP_DIMENSION_CALLOUTS == {}
    assert pen_rod_spec.SECTION_BAND == (0.00, -0.05)
    assert model_toleranced_dimensions(part) == {
        ("RodProfile", "Section"): "*deviations(SECTION_BAND)",
        ("Rod", "Depth"): "*deviations(SECTION_BAND)",
    }
    assert "V-BLOCK" in notes
    assert drill_process(pen_rod_spec.WIRE_HOLE_SPEC) in notes
    assert "X.XX" not in notes
    assert len(notes.splitlines()) == 3
    assert max(map(len, notes.splitlines())) <= 60


def test_native_gdt_controls_slide_faces_and_ends() -> None:
    """GD&T identity lives in the spec's PMI rows; the sheet only imports it."""
    from pen_rod_spec import GEOMETRIC_CONTROLS, PART_DATUMS

    by_key = {control.key: control for control in GEOMETRIC_CONTROLS}
    assert set(by_key) == {"opposite_slide_face_parallelism", "bottom_end_squareness"}
    assert by_key["opposite_slide_face_parallelism"].characteristic == "parallelism"
    assert by_key["opposite_slide_face_parallelism"].tolerance == "0.03"
    assert by_key["opposite_slide_face_parallelism"].datums == ("A",)
    assert by_key["bottom_end_squareness"].characteristic == "perpendicularity"
    assert by_key["bottom_end_squareness"].tolerance == "0.05"
    assert by_key["bottom_end_squareness"].datums == ("A",)
    # Datum A is the -X slide face; its +X opposite rides parallel to it.
    assert tuple(datum.letter for datum in PART_DATUMS) == ("A",)
    assert PART_DATUMS[0].face.normal == (-1, 0, 0)
    assert PART_DATUMS[0].face.offset_mm == pen_rod_spec.ROD_SECTION / 2.0
    assert by_key["opposite_slide_face_parallelism"].face.normal == (1, 0, 0)
    assert by_key["bottom_end_squareness"].face.normal == (0, -1, 0)



def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.TOP_VIEW_SCALE == 4.0
    assert pen_rod_spec.TOP_VIEW_NOTE == "TOP VIEW SCALE 4:1"


def test_part_config_has_critical_properties() -> None:
    import _config

    config = _config.parts("pen-rod")
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
