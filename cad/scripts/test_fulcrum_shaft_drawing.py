"""Offline contracts for the fulcrum-shaft drawing."""

from __future__ import annotations

import pytest

import draw_fulcrum_shaft as drawing
import fulcrum_shaft_spec
from _drawing_common import ViewEdge, ViewEdges


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = fulcrum_shaft_spec.SURFACE_FINISHES
    assert control.key == "bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == fulcrum_shaft_spec.SHAFT_DIA


def test_every_marked_model_dimension_is_shown() -> None:
    marked = set().union(*fulcrum_shaft_spec.DRAWING_DIMENSIONS.values())
    displayed = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert displayed == marked


def test_native_gdt_controls_shaft_form_orientation_and_finish() -> None:
    """GD&T identity lives in the spec's PMI rows; the sheet only imports it."""
    from fulcrum_shaft_spec import GEOMETRIC_CONTROLS, PART_DATUMS

    by_key = {control.key: control for control in GEOMETRIC_CONTROLS}
    assert set(by_key) == {
        "bearing_cylindricity",
        "plus_z_end_perpendicularity",
        "minus_z_end_perpendicularity",
    }
    assert by_key["bearing_cylindricity"].characteristic == "cylindricity"
    assert by_key["bearing_cylindricity"].tolerance == "0.01"
    for key in ("plus_z_end_perpendicularity", "minus_z_end_perpendicularity"):
        assert by_key[key].characteristic == "perpendicularity"
        assert by_key[key].tolerance == "0.05"
        assert by_key[key].datums == ("A",)
    assert tuple(datum.letter for datum in PART_DATUMS) == ("A",)


def test_pmi_rim_resolution_requires_unique_model_geometry() -> None:
    target = object()
    opposite_end = object()
    station = drawing.SHAFT_LENGTH / 2.0
    radius = drawing.SHAFT_DIA / 2.0
    target_circle = (0.0, 0.0, station, 0.0, 0.0, 1.0, radius)
    edges = ViewEdges(
        label="shaft profile",
        edges=(
            ViewEdge(target, None, target_circle, None),
            ViewEdge(
                opposite_end,
                None,
                (0.0, 0.0, -station, 0.0, 0.0, 1.0, radius),
                None,
            ),
        ),
    )
    assert drawing._unique_shaft_rim(edges, station, label="plus-Z rim") is target
    assert (
        drawing._unique_shaft_rim(edges, -station, label="minus-Z rim") is opposite_end
    )

    ambiguous = ViewEdges(
        label="ambiguous shaft profile",
        edges=(*edges.edges, ViewEdge(object(), None, target_circle, None)),
    )
    with pytest.raises(RuntimeError, match="expected one visible circle"):
        drawing._unique_shaft_rim(ambiguous, station, label="plus-Z rim")
