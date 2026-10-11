"""Blank drawing-sheet creation and pictorial-sheet placement.

Multi-sheet recipes create blank and pictorial sheets here without coupling
single-sheet templates to sheet-placement changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import iter_views, place_view

from _com import _early_bound
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
import _telemetry


@dataclass(frozen=True)
class FaceLabel:
    """One face name on a pictorial: ``text`` at ``text_xy`` pointing at ``point_mm``."""

    text: str
    point_mm: tuple[float, float, float]
    text_xy: tuple[float, float]


@dataclass(frozen=True)
class PictorialView:
    """One octant view of the priming sheet.

    ``octant`` is the viewer octant ``(sx, sy, sz)`` from ``_named_views``;
    the part build must have named it. ``center_xy`` is the view centre on the
    sheet in metres; ``labels`` are the face names the view carries.
    """

    octant: tuple[int, int, int]
    center_xy: tuple[float, float]
    labels: tuple[FaceLabel, ...]


@_telemetry.traced("drawing.pictorial_sheet", label_param="label")
def place_pictorial_sheet(
    adapter: Any,
    model_path: str,
    views: Sequence[PictorialView],
    *,
    scale: tuple[float, float],
    label: str,
) -> list[Any]:
    """Place octant pictorials with leadered face names on the ACTIVE sheet.

    The priming sheet a print opens on: two isometrics from opposite octants
    (front-top-left and front-bottom-right show all six faces between them),
    each face named where the reader sees it, so the orthographic sheets that
    follow need no orientation key. Views are placed by the octant's model
    view name (``_named_views.octant_view_name``); the finalizer styles them
    Shaded With Edges and the post-export precision check covers them, the
    same as ``*Isometric``. Returns the ``IView`` objects in order.
    """
    from _named_views import octant_view_name  # noqa: PLC0415 -- part-side module

    placed = []
    for pictorial in views:
        view = place_view(
            adapter,
            model_path,
            octant_view_name(*pictorial.octant),
            *pictorial.center_xy,
            scale=scale,
        )
        set_hidden_lines_removed(adapter, view)
        for face in pictorial.labels:
            attach_xy = model_point_in_view(
                adapter,
                view,
                tuple(value / 1000.0 for value in face.point_mm),
                label=f"{label} {face.text} face",
            )
            add_leader_note(
                adapter,
                face.text,
                text_xy=face.text_xy,
                attach_xy=attach_xy,
                view=view,
                label=f"{label} {face.text} label",
            )
        placed.append(view)
    return placed


@_telemetry.traced("drawing.create_sheets", label_param="label")
def create_blank_drawing_sheets(
    adapter: Any, sheet_names: Sequence[str], *, label: str
) -> None:
    """Rename the initial blank sheet and duplicate it into a checked package."""
    if not sheet_names or len(sheet_names) != len(set(sheet_names)):
        raise ValueError(f"{label}: sheet names must be nonempty and unique")
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    sheet = ddoc.GetCurrentSheet()
    if sheet is None:
        raise RuntimeError(f"{label}: drawing template has no initial sheet")
    initial_names = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    if len(initial_names) != 1:
        raise RuntimeError(
            f"{label}: drawing template has {len(initial_names)} sheets, expected 1"
        )
    if next(iter_views(adapter), None) is not None:
        raise RuntimeError(f"{label}: initial drawing sheet is not blank")
    sheet.SetName(sheet_names[0])
    renamed = str(adapter._get_attr_or_call(sheet, "GetName") or "")
    if renamed != sheet_names[0]:
        raise RuntimeError(f"{label}: failed to rename initial sheet: {renamed!r}")

    for previous_name, new_name in zip(sheet_names[:-1], sheet_names[1:], strict=True):
        pasted_name = ""
        for attempt in range(1, 4):
            if not ddoc.ActivateSheet(previous_name):
                raise RuntimeError(f"{label}: failed to activate {previous_name!r}")
            before_names = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
            draw.ClearSelection2(True)
            if not draw.Extension.SelectByID2(
                previous_name,
                "SHEET",
                0.0,
                0.0,
                0.0,
                False,
                0,
                null_callout(),
                0,
            ):
                raise RuntimeError(f"{label}: failed to select {previous_name!r}")
            draw.EditCopy()
            returned = bool(ddoc.PasteSheet(2, 2))
            after_names = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
            added = tuple(name for name in after_names if name not in before_names)
            if len(after_names) == len(before_names) + 1 and len(added) == 1:
                pasted_name = added[0]
                if not returned:
                    _telemetry.warn(
                        f"{label}: PasteSheet returned false but created "
                        f"{pasted_name!r}"
                    )
                break
            _telemetry.warn(
                f"{label}: PasteSheet attempt {attempt}/3 created no sheet "
                f"(returned={returned!r}, before={before_names!r}, "
                f"after={after_names!r})"
            )
        if not pasted_name:
            raise RuntimeError(f"{label}: failed to duplicate {previous_name!r}")
        if not ddoc.ActivateSheet(pasted_name):
            raise RuntimeError(f"{label}: failed to activate {pasted_name!r}")
        sheet = ddoc.GetCurrentSheet()
        if sheet is None:
            raise RuntimeError(f"{label}: pasted sheet has no ISheet")
        sheet.SetName(new_name)
        renamed = str(adapter._get_attr_or_call(sheet, "GetName") or "")
        if renamed != new_name:
            raise RuntimeError(f"{label}: failed to rename sheet: {renamed!r}")

    actual = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    if actual != tuple(sheet_names):
        raise RuntimeError(f"{label}: sheet order mismatch: {actual!r}")
