"""Key supplier-nut installation legends to source-owned physical bearing edges."""

from __future__ import annotations

from collections.abc import Callable
import math
from typing import Any

import _config
import _telemetry
from _com import _early_bound
from _drawing_attachment import _assert_attached_to, _assert_leader_lands
from _drawing_edges import scan_view_edges
from _drawing_layout_audit import _OWNER_DRAWING_TEMPLATE, annotation_display
from _drawing_leader_notes import add_attached_note
from _drawing_projection import model_points_in_view
from _layout_geometry import Box
from _purchased_fastener_drawing import (
    _box, _inside, fastener_view_cells, view_band_bottom,
)
from _supplier_reference_text import measured_native_text_bounds


@_telemetry.traced("drawing.supplier_nut_installation_flag", label_param="artifact_stem")
def add_supplier_nut_installation_flag(
    adapter: Any,
    right: Any,
    *,
    artifact_stem: str,
    bearing_point_mm: tuple[float, float, float],
) -> Callable[[], None]:
    """Key the legend to a recipe-owned bearing point in final model millimetres.

    The returned settled proof only reads the native key, leader and legend.
    """
    label = f"{artifact_stem} installation flag"
    key = "1"
    legend = str(_config.parts(artifact_stem)["installation_notes"])
    if not legend.startswith(f"{key} INSTALLATION - "):
        raise RuntimeError(f"{label}: installation instruction has no matching key")
    cell = next(
        cell for name, _, cell in fastener_view_cells(
            view_band_bottom(legend, label=label)
        ) if name == "*Right"
    )
    # The recipe supplies its actual mating-face boundary, independently of
    # a construction chord or whichever entity a sheet hit-test would pick.
    point_mm = bearing_point_mm

    def anchor() -> tuple[Any, tuple[float, float]]:
        right.UpdateViewDisplayGeometry()
        edge = scan_view_edges(right, label=label).exact_line_through(
            point_mm, label=label
        ).edge
        pick = model_points_in_view(
            adapter, right,
            [tuple(value / 1000.0 for value in point_mm)], label=label,
        )[0]
        return edge, pick

    edge, pick = anchor()
    note = _early_bound(
        add_attached_note(
            adapter, right, text=key, entity=edge, attached_to=edge,
            leader_attach_xy=pick,
            note_xy=(pick[0] + 0.012, pick[1] + 0.010), label=label,
        ),
        "INote",
    )
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")

    @_telemetry.traced("drawing.supplier_nut_installation_flag_settled")
    def assert_settled() -> None:
        current_edge, current_pick = anchor()
        if int(adapter.swApp.IsSame(current_edge, edge)) != 1:
            raise RuntimeError(f"{label}: bearing edge lost native identity")
        _assert_attached_to(
            adapter, annotation, current_edge, entity_type="EDGE",
            what="installation flag", label=label,
        )
        owner = annotation.Owner
        if (
            note.GetText() != key or note.PropertyLinkedText != key
            or int(annotation.Visible) != 1 or int(annotation.OwnerType) != 0
            or owner is None
            or int(adapter.swApp.IsSame(_early_bound(owner, "IView"), right)) != 1
        ):
            raise RuntimeError(f"{label}: key text, visibility or native owner changed")
        points = tuple(float(value) for value in annotation.GetLeaderPointsAtIndex(0) or ())
        if (
            len(points) < 6 or len(points) % 3
            or not all(math.isfinite(value) for value in points)
        ):
            raise RuntimeError(f"{label}: native key leader is unreadable")
        _assert_leader_lands(
            annotation, current_pick, what="installation flag", label=label
        )
        geometry, refused = annotation_display(adapter, annotation)
        texts = geometry.get("texts", ())
        if refused or not texts:
            raise RuntimeError(f"{label}: native key text is unreadable")
        bounds, _ = measured_native_text_bounds(texts, label=f"{label} native key")
        text_box = (bounds.xmin, bounds.ymin, bounds.xmax, bounds.ymax)
        if (
            not all(math.isfinite(value) for value in text_box)
            or not _inside(text_box, cell)
            or not _inside(_box(note.GetExtent(), label=label, kind="note"), cell)
            or any(
                not _inside((points[i], points[i + 1], points[i], points[i + 1]), cell)
                for i in range(0, len(points), 3)
            )
            or bounds.gap(Box(*_box(right.GetOutline(), label=label))) < 0.002
        ):
            raise RuntimeError(f"{label}: native key leaves its cell or crowds the view")
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        inventory = []
        for sheet_views in drawing.GetViews() or ():
            for raw_view in sheet_views or ():
                for raw in _early_bound(raw_view, "IView").GetNotes() or ():
                    current_note = _early_bound(raw, "INote")
                    current_annotation = _early_bound(
                        current_note.GetAnnotation(), "IAnnotation"
                    )
                    if not any(
                        int(adapter.swApp.IsSame(current_annotation, prior[1])) == 1
                        for prior in inventory
                    ):
                        inventory.append((current_note, current_annotation))
        keys = []
        template_keys = []
        for current_note, current_annotation in inventory:
            if current_note.GetText() != key:
                continue
            # The format's numeric border zone is not an installation key.
            # Do not exclude sheet/foreign keys or any legend/instruction.
            if int(current_annotation.OwnerType) == _OWNER_DRAWING_TEMPLATE:
                template_keys.append((current_note, current_annotation))
            else:
                keys.append((current_note, current_annotation))
        legends = [
            item for item in inventory
            if item[0].PropertyLinkedText == '$PRP:"Installation Notes"'
        ]
        instructions = [
            item for item in inventory
            if item[0].GetText().replace("\r\n", "\n")
            in (legend, legend.removeprefix(f"{key} "))
        ]
        if (
            len(keys) != 1
            or int(adapter.swApp.IsSame(keys[0][1], annotation)) != 1
            or len(legends) != 1
            or legends[0][0].GetText().replace("\r\n", "\n") != legend
            or len(instructions) != 1
        ):
            key_details = []
            for current_note, current_annotation in (*keys, *template_keys):
                try:
                    details = {
                        "owner_type": int(current_annotation.OwnerType),
                        "text": current_note.GetText(),
                        "authored_key_is_same": int(
                            adapter.swApp.IsSame(current_annotation, annotation)
                        ),
                    }
                except Exception as error:
                    details = {
                        "native_read_error": f"{type(error).__name__}: {error}"
                    }
                key_details.append(details)
            raise RuntimeError(
                f"{label}: expected one native key and its unchanged linked legend "
                f"(native_key_count={len(keys)}, template_key_count={len(template_keys)}, "
                f"linked_legend_count={len(legends)}, "
                f"installation_instruction_count={len(instructions)}, "
                f"key_candidates={key_details!r})"
            )
        _telemetry.annotate(
            key=key, model_point_mm=point_mm, landing_xy_m=current_pick,
            leader_xyz_m=points, text_box_m=text_box, cell_m=cell,
            native_key_count=len(keys), linked_legend_count=len(legends),
            template_key_count=len(template_keys),
            raw_key_candidate_count=len(keys) + len(template_keys),
            installation_instruction_count=len(instructions),
        )

    return assert_settled
