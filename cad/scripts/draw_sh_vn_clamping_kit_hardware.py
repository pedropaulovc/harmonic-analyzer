"""Draw the three installed forms from one Precision Matthews clamping kit.

Each explicitly configured member retains its four-view reference content.
The twelve installed members are not twelve procurement units.
"""

from __future__ import annotations

import argparse
import sys
import math
from collections.abc import Callable
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_variant_drawing import build_purchased_variant_drawing
from _com import _early_bound, _read_member
from _drawing_attachment import _is_same_attachment
from _drawing_common import set_high_quality_shaded_with_edges
from _drawing_dimensions import set_reference_dimension
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import visible_view_entities
from _drawing_projection import model_points_in_view
from _purchased_fastener_drawing import _box, _inside
import sh_vn_clamping_kit_hold_down_stud_spec as stud
from _layout_audit import display_box, estimated_text_runs
from _drawing_layout_audit import annotation_display


SPEC = DRAWINGS_BY_NAME["sh_vn_clamping_kit_hardware"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "52-PIECE CLAMPING KIT, 14 MM T-SLOT, 1/2-13 HARDWARE"
VARIANTS = (
    ("HoldDownStud", "HOLD-DOWN STUD"),
    ("TNut", "T-NUT"),
    ("FlangeNut", "FLANGE NUT"),
)
PURCHASE_UNIT = "52-PIECE KIT"


def _measured_display_box(rendered: dict[str, Any]) -> Any:
    """Normalize swTextPosition_e anchors before the lower-left ink boxer."""
    texts = []
    for item in rendered.get("texts", ()):
        width, height = float(item.get("w", 0)), float(item.get("h", 0))
        reference = int(item.get("ref", -1))
        position = tuple(float(value) for value in item.get("pos", ()))
        angle = float(item.get("ang", 0))
        if (
            min(width, height) <= 0
            or reference not in range(6)
            or len(position) < 2
            or not all(
                math.isfinite(value) for value in (width, height, angle, *position)
            )
        ):
            raise RuntimeError("kit: native rendered text geometry is unreadable")
        # swUPPER_LEFT, LOWER_LEFT, CENTER, UPPER_RIGHT, LOWER_RIGHT, UPPER_CENTER.
        dx, dy = (
            (0, -height),
            (0, 0),
            (-width / 2, -height / 2),
            (-width, -height),
            (-width, 0),
            (-width / 2, -height),
        )[reference]
        cosine, sine = math.cos(angle), math.sin(angle)
        texts.append(
            {
                **item,
                "ref": 1,
                "pos": (
                    position[0] + dx * cosine - dy * sine,
                    position[1] + dx * sine + dy * cosine,
                    0.0,
                ),
            }
        )
    return display_box({**rendered, "texts": texts})


def _stud_length_reference(
    adapter: Any, cells: tuple, views: list[Any]
) -> Callable[[], None]:
    """Measure the revolved model's two end rims, not its shorter straight land."""
    front = views[0]
    rims = []
    for raw in visible_view_entities(front, 1, label="kit stud end rims"):
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if curve is None or curve.IsCircle() is not True:
            continue
        params = tuple(float(value) for value in curve.CircleParams)
        if (
            len(params) == 7
            and math.isclose(params[0], 0.0, abs_tol=1e-9)
            and math.isclose(params[2], 0.0, abs_tol=1e-9)
            and math.isclose(abs(params[4]), 1.0, abs_tol=1e-9)
            and math.isclose(
                params[6] * 1000, stud.RADIUS - stud.END_CHAMFER, abs_tol=1e-5
            )
        ):
            rims.append((params[1], edge))
    rims.sort(key=lambda item: item[0])
    if len(rims) != 2:
        raise RuntimeError("kit stud: expected exactly two native end rims")
    length_mm = (rims[1][0] - rims[0][0]) * 1000
    if not math.isclose(length_mm, stud.LENGTH, abs_tol=1e-5):
        raise RuntimeError(
            "kit stud: native overall length differs from the installed member"
        )
    entities = (rims[0][1], rims[1][1])
    _early_bound(front, "IView").UpdateViewDisplayGeometry()  # VT_VOID
    points = model_points_in_view(
        adapter,
        front,
        [(0.0, station, 0.0) for station, _edge in rims],
        label="kit stud overall end stations",
    )
    cell = cells[0][2]
    display = _early_bound(
        add_edge_dimension(
            adapter,
            front,
            p0=points[0],
            p1=points[1],
            text_xy=(cell[0] + 0.022, (points[0][1] + points[1][1]) / 2),
            label="kit stud overall length",
            orientation="vertical",
            entities=entities,
        ),
        "IDisplayDimension",
    )
    native = _early_bound(display.GetDimension2(0), "IDimension")
    native.DrivenState = 1  # swDimensionDriven: drawing-only reference measurement.
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    set_reference_dimension(adapter, annotation, label="kit stud overall length")

    def settled() -> None:
        present = [
            raw
            for raw in (front.GetAnnotations() or ())
            if int(adapter.swApp.IsSame(raw, annotation)) == 1
        ]
        if len(present) != 1:
            raise RuntimeError("kit stud: overall reference annotation was lost")
        assert_dimension_measures(
            adapter,
            display,
            expected_mm=length_mm,
            label="kit stud overall length",
            entities=entities,
        )
        if (
            int(native.DrivenState) != 1
            or int(annotation.Visible) != 1
            or (display.GetText(1), display.GetText(2)) != ("(", ")")
        ):
            raise RuntimeError("kit stud: overall reference display was lost")
        rendered, errors = annotation_display(adapter, annotation)
        ink = _measured_display_box(rendered)
        if (
            errors
            or not rendered.get("texts")
            or estimated_text_runs(rendered)
            or ink is None
            or not _inside((ink.xmin, ink.ymin, ink.xmax, ink.ymax), cell)
        ):
            raise RuntimeError(
                "kit stud: reference text/strokes leave the FRONT cell or are unreadable"
            )

    settled()
    return settled


def _note_text_box(annotation: Any) -> tuple[float, float, float, float]:
    """Native rendered text only: INote.GetExtent also includes its fixed leader."""
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    texts = []
    for index in range(int(data.GetTextCount())):
        text = data.GetTextAtIndex(index)
        if not text.strip():
            continue
        width = float(data.GetTextInBoxWidthAtIndex(index))
        height = float(data.GetTextHeightAtIndex(index))
        if (
            not math.isfinite(width)
            or not math.isfinite(height)
            or min(width, height) <= 0
        ):
            raise RuntimeError("kit T-nut: native thread text size is unreadable")
        texts.append(
            {
                "t": text,
                "w": width,
                "h": height,
                "pos": tuple(data.GetTextPositionAtIndex(index)),
                "ref": int(data.GetTextRefPositionAtIndex(index)),
                "ang": float(data.GetTextAngleAtIndex(index)),
            }
        )
    box = _measured_display_box({"texts": texts})
    if box is None:
        raise RuntimeError("kit T-nut: native thread text is missing")
    return (box.xmin, box.ymin, box.xmax, box.ymax)


def _tnut_thread_note(
    adapter: Any, cells: tuple, views: list[Any]
) -> Callable[[], None]:
    """Author and relocate the native cosmetic-thread callout, never free text.

    The b3c709 native canary had one cosmetic thread but no drawing callout.
    Select that bore-owned thread and request its native callout once during
    authoring. ICThread.ThreadCallout is the creation proof; later settled
    checks only read it and must not recreate a lost note.
    """
    iso = _early_bound(views[3], "IView")
    # The member hook follows HLR fitting, before the finalizer authors this
    # mode. Inspect the same display mode that will print, then flush its
    # geometry before reading annotations. This is not a note-generation retry.
    set_high_quality_shaded_with_edges(adapter, iso, label="kit T-nut isometric")

    def attachment_state(annotation: Any) -> tuple:
        attached = tuple(annotation.GetAttachedEntities3() or ())
        types = tuple(
            int(value) for value in (annotation.GetAttachedEntityTypes() or ())
        )
        count = int(annotation.GetAttachedEntityCount3())
        features = []
        for entity, kind in zip(attached, types):
            if entity is None:
                faces = ()
            elif kind == 1:  # swSelectType_e.swSelEDGES
                faces = _early_bound(entity, "IEdge").GetTwoAdjacentFaces2() or ()
            elif kind == 2:  # swSelectType_e.swSelFACES
                faces = (entity,)
            else:
                faces = ()
            names = []
            for face in faces:
                if face is not None:
                    feature = _early_bound(face, "IFace2").GetFeature()
                    if feature is not None:
                        names.append(str(_early_bound(feature, "IFeature").Name))
            features.append(tuple(names))
        return attached, types, count, tuple(features)

    def belongs_to_bore(state: tuple) -> bool:
        attached, types, count, features = state
        return (
            bool(attached)
            and count == len(attached) == len(types)
            and all(entity is not None for entity in attached)
            and all(kind in (1, 2) for kind in types)
            and any("TNutThreadBore" in names for names in features)
        )

    insertion_before: dict[str, Any] = {}

    def insert_callout(thread_annotation: Any, state: tuple) -> None:
        thread_name = str(thread_annotation.GetName())
        part = _early_bound(iso.ReferencedDocument, "IPartDoc")
        # ICThread's SDK overview documents this name-to-source-feature lookup.
        feature = part.FeatureByName(thread_name)
        definition: dict[str, Any] = {"feature_resolved": feature is not None}
        if feature is not None:
            feature = _early_bound(feature, "IFeature")
            definition["feature_type"] = str(feature.GetTypeName2())
            if definition["feature_type"] == "CosmeticThread":
                raw_data = feature.GetDefinition()
                if raw_data is not None:
                    data = _early_bound(raw_data, "ICosmeticThreadFeatureData")
                    definition.update(
                        standard=int(data.Standard),
                        standard_type=str(data.StandardType)[:80],
                        text=str(data.ThreadCallout)[:120],
                    )
        insertion_before.update(
            view=str(iso.GetName2())[:80],
            thread_name=thread_name[:120],
            attachment_count=state[2],
            attachment_types=state[1][:8],
            attachment_features=tuple(
                tuple(name[:64] for name in names[:4]) for names in state[3][:8]
            ),
            source_definition=definition,
            selected=False,
            requested=False,
        )
        draw = _early_bound(adapter.currentModel, "IModelDoc2")
        drawing = _early_bound(draw, "IDrawingDoc")
        previous = drawing.ActiveDrawingView
        previous_name = (
            _early_bound(previous, "IView").GetName2() if previous is not None else None
        )
        sheet_name = _early_bound(drawing.GetCurrentSheet(), "ISheet").GetName()
        primary_error: BaseException | None = None
        try:
            if drawing.ActivateView(iso.GetName2()) is not True:
                raise RuntimeError(
                    f"kit T-nut: cannot activate thread-callout view; {insertion_before!r}"
                )
            draw.ClearSelection2(True)
            manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
            # Follow the established drawing-annotation Select2 convention;
            # its reported success is not proof of the actual selection.
            selected = thread_annotation.Select2(False, 0)
            count = int(manager.GetSelectedObjectCount2(-1))
            kind = int(manager.GetSelectedObjectType3(1, -1)) if count else 0
            picked = manager.GetSelectedObject6(1, -1) if count else None
            picked_annotation = None
            if count == 1 and kind == 39 and picked is not None:
                # swSelectType_e.swSelCTHREADS = 39; drawing selections return ICThread.
                picked_annotation = _early_bound(
                    _early_bound(picked, "ICThread").GetAnnotation(),
                    "IAnnotation",
                )
            same = (
                picked_annotation is not None
                and int(adapter.swApp.IsSame(picked_annotation, thread_annotation)) == 1
            )
            insertion_before.update(
                selection_count=count,
                selection_type=kind,
                selection_name=(
                    str(picked_annotation.GetName())[:120]
                    if picked_annotation is not None
                    else None
                ),
                same_thread=same,
            )
            if selected is not True or count != 1 or kind != 39 or not same:
                raise RuntimeError(
                    f"kit T-nut: cannot select cosmetic thread; {insertion_before!r}"
                )
            insertion_before["selected"] = True
            insertion_before["requested"] = True
            _telemetry.info(
                f"kit T-nut: requesting native thread callout; {insertion_before!r}"
            )
            # VT_VOID. Method docs give no eligibility remarks; the UI command
            # documents no-standard/nonempty-text restrictions, so only the
            # same ICThread's subsequent ThreadCallout readback proves success.
            drawing.InsertThreadCallout()
        except BaseException as error:
            primary_error = error
            raise
        finally:
            try:
                draw.ClearSelection2(True)
                restored = (
                    drawing.ActivateView(previous_name)
                    if previous_name is not None
                    else drawing.ActivateSheet(sheet_name)
                )
                active = drawing.ActiveDrawingView
                active_name = (
                    _early_bound(active, "IView").GetName2()
                    if active is not None
                    else None
                )
                active_sheet = _early_bound(
                    drawing.GetCurrentSheet(),
                    "ISheet",
                ).GetName()
                if (
                    restored is not True
                    or active_name != previous_name
                    or active_sheet != sheet_name
                ):
                    raise RuntimeError(
                        f"activation readback: expected view={previous_name!r}, "
                        f"sheet={sheet_name!r}; actual view={active_name!r}, "
                        f"sheet={active_sheet!r}, reported={restored!r}"
                    )
            except Exception as restore_error:
                message = (
                    f"kit T-nut: cannot restore drawing activation: {restore_error!r}; "
                    f"insertion_before={insertion_before!r}"
                )
                if primary_error is not None:
                    primary_error.add_note(message)
                else:
                    raise RuntimeError(message) from restore_error

    def notes(*, author_missing: bool = False) -> list[tuple]:
        iso.UpdateViewDisplayGeometry()  # VT_VOID: immediate display-geometry access.
        found, observed = [], []
        thread_annotations = [
            annotation
            for raw in (iso.GetAnnotations() or ())
            if int((annotation := _early_bound(raw, "IAnnotation")).GetType()) == 1
            # swAnnotationType_e.swCThread
        ]
        threads, callouts = len(thread_annotations), 0
        for thread_annotation in thread_annotations:
            thread = _early_bound(thread_annotation.GetSpecificAnnotation(), "ICThread")
            raw_note = _read_member(thread, "ThreadCallout")
            if raw_note is None:
                state = attachment_state(thread_annotation)
                if author_missing and threads == 1 and belongs_to_bore(state):
                    insert_callout(thread_annotation, state)
                    iso.UpdateViewDisplayGeometry()
                    fresh = [
                        annotation
                        for raw in (iso.GetAnnotations() or ())
                        if int(
                            (annotation := _early_bound(raw, "IAnnotation")).GetType()
                        )
                        == 1
                        and int(adapter.swApp.IsSame(annotation, thread_annotation))
                        == 1
                    ]
                    if len(fresh) != 1:
                        raise RuntimeError(
                            "kit T-nut: selected cosmetic thread lost identity after "
                            f"insertion; matching_annotations={len(fresh)}, "
                            f"insertion_before={insertion_before!r}"
                        )
                    thread_annotation = fresh[0]
                    thread = _early_bound(
                        thread_annotation.GetSpecificAnnotation(),
                        "ICThread",
                    )
                    raw_note = _read_member(thread, "ThreadCallout")
                if raw_note is None:
                    if len(observed) < 4:
                        observed.append(
                            {
                                "callout": None,
                                "thread_count": state[2],
                                "thread_types": state[1][:8],
                                "thread_features": tuple(
                                    tuple(name[:64] for name in names[:4])
                                    for names in state[3][:8]
                                ),
                            }
                        )
                    continue
            callouts += 1
            note = _early_bound(raw_note, "INote")
            annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
            attached, types, count, features = attachment_state(annotation)
            if len(observed) < 4:
                observed.append(
                    {
                        "text": str(note.GetText())[:120],
                        "count": count,
                        "types": types[:8],
                        "features": tuple(
                            tuple(name[:64] for name in names[:4])
                            for names in features[:8]
                        ),
                        "nulls": sum(entity is None for entity in attached),
                    }
                )
            if belongs_to_bore((attached, types, count, features)):
                found.append((note, annotation, thread_annotation, attached, types))
        if len(found) != 1:
            # Diagnostic only: ordinary view notes are not a substitute for the
            # native ICThread -> ThreadCallout relationship.
            view_notes = tuple(iso.GetNotes() or ())
            view_note_texts = tuple(
                str(_early_bound(raw, "INote").GetText())[:120]
                for raw in view_notes[:4]
            )
            raise RuntimeError(
                "kit T-nut: expected one automatic isometric thread note attached "
                f"to TNutThreadBore; found={len(found)}, cosmetic_threads={threads}, "
                f"callouts={callouts}, candidates={observed!r}, "
                f"view_notes={len(view_notes)}, view_note_texts={view_note_texts!r}, "
                f"insertion_before={insertion_before!r}"
            )
        return found

    note, annotation, thread_annotation, attachments, attachment_types = notes(
        author_missing=True,
    )[0]
    text, linked = note.GetText(), note.PropertyLinkedText
    if not text.strip():
        raise RuntimeError("kit T-nut: native thread callout has no text")

    def region() -> tuple[float, float, float, float]:
        top = max(_box(view.GetOutline(), label="T-nut")[3] for view in views)
        return (cells[0][2][0] + 0.002, top + 0.002, cells[2][2][2] - 0.002, 0.253)

    bounds = _note_text_box(annotation)
    clear = region()
    position = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    target = (
        position[0] + (clear[0] + clear[2] - bounds[0] - bounds[2]) / 2,
        position[1] + (clear[1] + clear[3] - bounds[1] - bounds[3]) / 2,
        0.0,
    )
    if annotation.SetPosition2(*target) is not True:
        raise RuntimeError("kit T-nut: native thread-note relocation refused")

    def settled() -> None:
        current = notes()
        current_note, current_annotation, current_thread, attached, types = current[0]
        if (
            current_note.GetText() != text
            # swObjectEquality.swObjectSame = 1 (SOLIDWORKS API Help).
            or int(adapter.swApp.IsSame(current_annotation, annotation)) != 1
            or int(adapter.swApp.IsSame(current_thread, thread_annotation)) != 1
            or current_note.PropertyLinkedText != linked
            or current_annotation.IsDangling() is not False
            or int(current_annotation.Visible) != 1
            or types != attachment_types
            or len(attached) != len(attachments)
            or any(
                not _is_same_attachment(
                    adapter,
                    actual,
                    expected,
                    "EDGE" if kind == 1 else "FACE",
                )
                for actual, expected, kind in zip(
                    attached, attachments, attachment_types, strict=True
                )
            )
            or not _inside(_note_text_box(annotation), region())
            or not _inside(
                _box(note.GetExtent(), label=text, kind="note"),
                (cells[0][2][0], cells[3][2][1], cells[2][2][2], 0.255),
            )
        ):
            raise RuntimeError(
                "kit T-nut: thread note lost identity, attachment or clearance"
            )

    settled()
    return settled


def annotate_member(
    adapter: Any,
    configuration: str,
    cells: tuple,
    views: list[Any],
) -> tuple[Callable[[], None], ...]:
    if configuration == "HoldDownStud":
        return (_stud_length_reference(adapter, cells, views),)
    if configuration == "TNut":
        return (_tnut_thread_note(adapter, cells, views),)
    return ()


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_variant_drawing(
        adapter,
        SPEC,
        variants=VARIANTS,
        item=ITEM,
        purchase_unit=PURCHASE_UNIT,
        annotate_member=annotate_member,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
