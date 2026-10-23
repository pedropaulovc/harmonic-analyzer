"""Create the purchased reference drawing for the counter-anchor jam nut (MHA-SM-VN-55, McMaster 90760A140)."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import math
from pathlib import Path
import sys
from typing import Any

import _telemetry
import _config
from _com import _early_bound
from _drawing_attachment import _assert_attached_to, _assert_leader_lands
from _drawing_edges import scan_view_edges
from _drawing_layout_audit import _OWNER_DRAWING_TEMPLATE, annotation_display
from _drawing_leader_notes import add_attached_note
from _drawing_projection import model_points_in_view
from _layout_geometry import Box
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import (
    _box, _inside, build_purchased_fastener_drawing,
    fastener_view_cells, view_band_bottom,
)
from _supplier_nut_drawing import add_supplier_nut_dimensions, assert_saved_supplier_nut_nominal
from _supplier_reference_text import measured_native_text_bounds
from _supplier_screw_layout import supplier_screw_margins
import sm_vn_boss_hook_jam_nut_spec as supplier


SPEC = DRAWINGS_BY_NAME["sm_vn_boss_hook_jam_nut"]
ITEM = "#10-24 NARROW-PROFILE HEX NUT"
# Shared Front budget includes the bottom nominal-major/thread callout; its
# 20 mm top reservation also covers the physical AF fraction 8 mm above Front.
# Tuple order is (left, bottom, right, top), in sheet metres.
SUPPLIER_MARGINS = supplier_screw_margins(
    supplier.SUPPLIER_REFERENCE_DIMENSIONS,
    sides={"ThreadNominalMajor": "bottom"},
)
# Match Front's vertical fit budget to preserve projected alignment.
SUPPLIER_MARGINS["*Right"] = (
    0.007, SUPPLIER_MARGINS["*Front"][1], 0.007, SUPPLIER_MARGINS["*Front"][3],
)


def _installation_flag(adapter: Any, right: Any) -> Callable[[], None]:
    """Key the existing instruction to its actual z=0 bearing-face boundary."""
    label = f"{SPEC.artifact_stem} installation flag"
    key = "1"
    legend = str(_config.parts(SPEC.artifact_stem)["installation_notes"])
    if not legend.startswith(f"{key} INSTALLATION - "):
        raise RuntimeError(f"{label}: installation instruction has no matching key")
    cell = next(
        cell for name, _, cell in fastener_view_cells(
            view_band_bottom(legend, label=label)
        ) if name == "*Right"
    )
    # build_sm_summing_assembly.JAM_NUT_POS seats this local z=0 face on
    # MHA-SM-03. The visible +X hex flat bounds that face, independently of
    # the construction chord and of whichever entity a sheet hit-test picks.
    point_mm = (supplier.ACROSS_FLATS / 2.0, 0.0, 0.0)

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


def _supplier_dimensions(
    adapter: Any, views_by_orientation: dict[str, Any]
) -> Callable[[], None]:
    dimensions_check = add_supplier_nut_dimensions(
        adapter,
        views_by_orientation,
        across_flats_mm=supplier.ACROSS_FLATS,
        thickness_mm=supplier.THICKNESS,
        bore_diameter_mm=supplier.BORE_DIA,
        thread=supplier.THREAD,
        precision=supplier.DRAWING_REFERENCE_PRECISION,
        fraction_denominator=supplier.SUPPLIER_FRACTION_DENOMINATOR,
        reference_dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        reference_starts=supplier.SUPPLIER_REFERENCE_STARTS,
    )
    flag_check = _installation_flag(adapter, views_by_orientation["*Right"])

    def assert_settled() -> None:
        dimensions_check()
        flag_check()

    return assert_settled


async def build(adapter: Any) -> dict[str, str]:
    authored_checks: list[Callable[[], None]] = []
    source_configuration: str | None = None

    def supplier_dimensions(target: Any, views: dict[str, Any]) -> None:
        nonlocal source_configuration
        source_configuration = views["*Front"].ReferencedConfiguration
        if not isinstance(source_configuration, str) or not source_configuration.strip():
            raise RuntimeError("supplier nut has no authored source configuration")
        authored_checks.append(_supplier_dimensions(target, views))

    def assert_settled() -> None:
        if len(authored_checks) != 1:
            raise RuntimeError("supplier nut annotations must be authored exactly once")
        authored_checks[0]()

    def assert_saved(target: Any, path: Path) -> None:
        if source_configuration is None:
            raise RuntimeError("supplier nut saved check has no authored source binding")
        authored_checks.clear()  # Release closed drawing wrappers before reopening.
        assert_saved_supplier_nut_nominal(
            target, path, nominal_major_mm=supplier.SUPPLIER_NOMINAL_MAJOR_MM,
            source_path=SPEC.source, configuration=source_configuration,
        )

    # Every purchased view is hidden-lines-removed (rule 9), which also clears
    # the dashed bore the r6/r7 reviews flagged in the TOP/RIGHT views.
    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_settled,),
        saved_check=assert_saved,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
