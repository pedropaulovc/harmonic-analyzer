"""Native supplier reference sizes for the five purchased VN hex nuts.

The stock recipes place their thread axes on +Z and retain the exact nominal
hex width and height. Drawing-owned dimensions measure the existing solid;
supplier fractions and decimal places affect presentation only. The plain
model bore is an envelope, not a thread diameter to print, so its rim receives
an attached thread-designation note instead of a numeric diameter dimension.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from _com import _early_bound
from _drawing_attachment import _assert_attached_to
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdge, scan_view_edges
from _drawing_leader_notes import add_attached_note
from _drawing_projection import model_points_in_view
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
import _telemetry


def _reference_between_edges(
    adapter: Any,
    view: Any,
    edges: tuple[ViewEdge, ViewEdge],
    *,
    text_xy: tuple[float, float],
    expected_mm: float,
    precision: int,
    label: str,
    fraction_denominator: int | None = None,
    callout: str | None = None,
) -> str:
    picks = model_points_in_view(
        adapter,
        view,
        [tuple(value / 1000.0 for value in edge.midpoint_mm) for edge in edges],
        label=label,
    )
    entities = (edges[0].edge, edges[1].edge)
    display = add_edge_dimension(
        adapter,
        view,
        p0=picks[0],
        p1=picks[1],
        text_xy=text_xy,
        label=label,
        orientation="horizontal",
        entities=entities,
    )
    # The shared helper reads the native linear type before its SI value, and
    # proves units, precision, reference state and absence of text overrides.
    supplier_reference_dimension(
        adapter,
        display,
        label=label,
        units="in",
        precision=precision,
        expected_mm=expected_mm,
        fraction_denominator=fraction_denominator,
        callout=callout,
    )
    assert_dimension_measures(
        adapter,
        display,
        expected_mm=expected_mm,
        label=label,
        entities=entities,
    )
    return str(_early_bound(display.GetDimension2(0), "IDimension").FullName)


@_telemetry.traced("drawing.supplier_nut_dimensions")
def add_supplier_nut_dimensions(
    adapter: Any,
    views_by_orientation: Mapping[str, Any],
    *,
    across_flats_mm: float,
    thickness_mm: float,
    bore_diameter_mm: float,
    thread: str,
    precision: Mapping[str, int],
    fraction_denominator: int,
) -> Callable[[], None]:
    """Measure the unchanged hex and attach its source thread designation.

    Front looks onto the +Z end face. Its opposing vertical edges carry the
    across-flats width. Right looks onto the +X flat; that flat's two end
    edges carry the axial height. Exact model-space picks cannot silently
    select a corner-to-corner width or the bore instead.
    Returns the read-only settled proof for the shared builder to run after
    finalization's last rebuild and before saving.
    """
    front = views_by_orientation["*Front"]
    right = views_by_orientation["*Right"]
    # Read the fitted, annotation-free outlines before adding anything. The
    # shared builder pins captions at the cell floor and does not shrink views.
    front_box = tuple(float(value) for value in front.GetOutline())
    right_box = tuple(float(value) for value in right.GetOutline())
    front_edges = scan_view_edges(front, label="supplier nut front")
    right_edges = scan_view_edges(right, label="supplier nut right")
    half_width = across_flats_mm / 2.0
    flats = tuple(
        front_edges.exact_line_through(
            (x, 0.0, thickness_mm), label="supplier nut opposing flat"
        )
        for x in (-half_width, half_width)
    )
    ends = tuple(
        right_edges.exact_line_through(
            (half_width, 0.0, z), label="supplier nut end face"
        )
        for z in (0.0, thickness_mm)
    )
    width_name = _reference_between_edges(
        adapter,
        front,
        flats,
        text_xy=((front_box[0] + front_box[2]) / 2.0, front_box[3] + 0.008),
        expected_mm=across_flats_mm,
        precision=precision["AcrossFlats"],
        label="supplier nut across flats",
        fraction_denominator=fraction_denominator,
        callout="ACROSS FLATS",
    )
    height_name = _reference_between_edges(
        adapter,
        right,
        ends,
        text_xy=((right_box[0] + right_box[2]) / 2.0, right_box[1] - 0.008),
        expected_mm=thickness_mm,
        precision=precision["Height"],
        label="supplier nut height",
    )
    bore = front_edges.circle_at(
        (0.0, 0.0, thickness_mm),
        bore_diameter_mm / 2.0,
        axis=(0.0, 0.0, 1.0),
        label="supplier nut thread rim",
        center_tol_mm=1e-4,
        radius_tol_mm=1e-4,
    )
    thread_text = f"({thread.removeprefix('#')} THREAD)"
    note = add_attached_note(
        adapter,
        front,
        text=thread_text,
        entity=bore.edge,
        attached_to=bore.edge,
        note_xy=(front_box[2] + 0.008, (front_box[1] + front_box[3]) / 2.0 + 0.012),
        label="supplier nut thread designation",
    )
    if _early_bound(note, "INote").GetText() != thread_text:
        raise RuntimeError("supplier nut thread designation did not survive rebuild")

    references = {
        "*Front": (
            width_name,
            (flats[0].edge, flats[1].edge),
            across_flats_mm,
            precision["AcrossFlats"],
            fraction_denominator,
            "ACROSS FLATS",
            "supplier nut across flats",
        ),
        "*Right": (
            height_name,
            (ends[0].edge, ends[1].edge),
            thickness_mm,
            precision["Height"],
            None,
            None,
            "supplier nut height",
        ),
    }

    @_telemetry.traced("drawing.supplier_nut_settled")
    def assert_settled() -> None:
        thread_annotations = []
        # Enumerate the final view inventories rather than trusting retained
        # display handles: deletion, suppression or duplication must fail.
        for orientation, view in views_by_orientation.items():
            dimensions = []
            for raw in _early_bound(view, "IView").GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                kind = int(annotation.GetType())
                if kind == 4:  # swAnnotationType_e.swDisplayDimension
                    if int(annotation.Visible) != 1:  # swAnnotationVisible
                        raise RuntimeError(
                            f"{orientation}: supplier nut dimension is hidden"
                        )
                    dimensions.append(
                        _early_bound(
                            annotation.GetSpecificAnnotation(), "IDisplayDimension"
                        )
                    )
                elif kind == 6:  # swAnnotationType_e.swNote
                    note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
                    if note.GetText() == thread_text:
                        if orientation != "*Front" or int(annotation.Visible) != 1:
                            raise RuntimeError(
                                "supplier nut thread note lost its visible Front owner"
                            )
                        thread_annotations.append(annotation)
            expected_count = 1 if orientation in references else 0
            if len(dimensions) != expected_count:
                raise RuntimeError(
                    f"{orientation}: expected {expected_count} supplier nut "
                    f"dimensions, found {len(dimensions)}"
                )
            if not expected_count:
                continue
            name, entities, expected, places, denominator, callout, label = references[
                orientation
            ]
            display = dimensions[0]
            native = _early_bound(display.GetDimension2(0), "IDimension")
            if str(native.FullName) != name:
                raise RuntimeError(
                    f"{label}: the authored native dimension was replaced"
                )
            assert_supplier_reference_dimension(
                adapter,
                display,
                label=label,
                units="in",
                precision=places,
                expected_mm=expected,
                fraction_denominator=denominator,
                callout=callout,
            )
            assert_dimension_measures(
                adapter,
                display,
                expected_mm=expected,
                label=label,
                entities=entities,
            )
        if len(thread_annotations) != 1:
            raise RuntimeError(
                "supplier nut requires one final attached thread designation; "
                f"found {len(thread_annotations)}"
            )
        _assert_attached_to(
            adapter,
            thread_annotations[0],
            bore.edge,
            entity_type="EDGE",
            what="supplier thread note",
            label=thread_text,
        )

    return assert_settled
