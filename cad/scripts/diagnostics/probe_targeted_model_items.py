"""COM probe: can ONE feature's marked dimensions be imported into a view?

Attach-only, read-only, on the built tube-frame drawing. Every recipe runs in a
freshly opened document so no recipe sees another's insertions, and nothing is
saved (the insertions die with ``CloseDoc``).

Selection (settled, printed by the ``names`` pass):

* ``IModelDocExtension::SelectByID2`` reaches a model feature inside a drawing
  view as ``"<feature>@<drawing component>@<view>"`` -- the form the "Reset
  Visibility of Sketches in Drawing View" example uses
  (``"Sketch1@model-7@Drawing View1"``). The middle name is
  ``IView::RootDrawingComponent2::Name`` (``tube-frame-2`` for the second view),
  so nothing is guessed; the Type argument must be the real kind (``"SKETCH"``
  or ``"BODYFEATURE"``) -- an empty Type resolves none of these names.
* ``IFeature::Select2`` on the feature reached through
  ``IView::ReferencedDocument`` selects it in the PART and leaves the drawing's
  selection list empty, so it cannot drive a drawing-side import.

Import: ``IDrawingDoc::InsertModelAnnotations3``'s remarks publish two
conflicting Option tables (pre-2008-SP3: 1 = selected component, 2 = selected
feature; corrected enum names: ``swImportModelItemsFromSelectedFeature`` = 1),
and ``IDrawingDoc::InsertModelDimensions`` still documents the old numbering, so
the probe runs every plausible combination -- both Options, both methods,
``InsertModelAnnotations4``, feature-only vs view+feature selections, a
selection mark, and DuplicateDims off -- and reports which one moves ink.

Every import is judged by an ``IView::GetAnnotations`` census of ALL views
before and after, never by the return value.

The built drawing already holds the dimensions its recipe kept and
``DuplicateDims=True`` eliminates duplicates, so only what the build DELETED can
come back. In tube-frame's end view that is ``OuterDia`` (owned by the
``AnnulusProfile`` sketch): the entire-model controls at the end of the run
prove it is importable, so any recipe that brings nothing failed on its own.

    HARMONIC_SW_AUTOSTART=0 HARMONIC_COM_SEAT=probe:model-items \
      uv run cad/scripts/diagnostics/probe_targeted_model_items.py \
      [drawing.SLDDRW] [view name]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "cad/scripts")]

from _common import _early_bound  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import null_callout  # noqa: E402

DRAWING = Path(
    sys.argv[1] if len(sys.argv) > 1 else ROOT / "cad/out/slddrw/tube-frame.SLDDRW"
).resolve()
TARGET_VIEW = sys.argv[2] if len(sys.argv) > 2 else None
MASK = 0x8000 | 0x20000  # marked-for-drawing | hole-wizard location
# The sketch that owns OuterDia, the one dimension tube-frame's end view lost.
FEATURE = "AnnulusProfile"
FEATURES = ("AnnulusProfile", "CrossHoleProfile", "Column", "TopEndBreak")
TYPES = ("SKETCH", "BODYFEATURE", "")


def attach():
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    app = _early_bound(
        win32com.client.GetActiveObject("SldWorks.Application"), "ISldWorks"
    )
    print(f"attached pid={app.GetProcessID()} revision={app.RevisionNumber()}")
    return app


def open_drawing(app):
    opened = app.OpenDoc6(str(DRAWING), 3, 1 | 2, "", 0, 0)  # drawing, silent|readonly
    document = opened[0] if isinstance(opened, tuple) else opened
    if document is None:
        raise RuntimeError(f"failed to open {DRAWING}: {opened!r}")
    return _early_bound(document, "IModelDoc2")


def views(document):
    """Every ``IView`` on the drawing, sheet view first (``GetFirstView``)."""
    drawing = _early_bound(document, "IDrawingDoc")
    view = drawing.GetFirstView()
    found = []
    while view:
        typed = _early_bound(view, "IView")
        found.append(typed)
        view = typed.GetNextView()
    return found


def component_name(view):
    """``IView::RootDrawingComponent2::Name`` -- the middle name qualifier."""
    # RootDrawingComponent2(InChildContext): False = this view's own component.
    root = view.RootDrawingComponent2(False)
    return _early_bound(root, "IDrawingComponent").Name if root else None


def select(document, name, type_name, *, append=False, mark=0):
    return document.Extension.SelectByID2(
        name, type_name, 0.0, 0.0, 0.0, append, mark, null_callout(), 0
    )


def select_feature(context, feature=FEATURE, *, append=False, mark=0):
    """Select a model feature inside the target view; returns the Type that won."""
    document, _, view_name, component = context
    return next(
        (
            type_name
            for type_name in ("SKETCH", "BODYFEATURE")
            if select(
                document,
                f"{feature}@{component}@{view_name}",
                type_name,
                append=append,
                mark=mark,
            )
        ),
        None,
    )


def dimension_names(annotations):
    """Model dimension names of an ``IAnnotation`` sequence; other kinds skipped."""
    names = []
    for annotation in annotations or ():
        typed = _early_bound(annotation, "IAnnotation")
        try:
            display = typed.GetSpecificAnnotation()
            dimension = _early_bound(display, "IDisplayDimension").GetDimension()
            names.append(_early_bound(dimension, "IDimension").FullName.split("@")[0])
        except Exception:  # noqa: BLE001 - not a model dimension: irrelevant here
            continue
    return sorted(names)


def census(found, names):
    """``{view name: [dimension names]}`` over every view of the drawing."""
    return {
        name: dimension_names(tuple(view.GetAnnotations() or ()))
        for view, name in zip(found, names)
    }


def arrivals(before, after):
    """Per view, the dimensions that appeared between two censuses."""
    return {
        name: sorted(set(after[name]) - set(before[name]))
        for name in after
        if set(after[name]) - set(before[name])
    }


def pass_names(app, target):
    """Which selection route reaches a model feature from the drawing?"""
    document = open_drawing(app)
    try:
        drawing = _early_bound(document, "IDrawingDoc")
        manager = document.SelectionManager
        found = views(document)
        names = [view.GetName2() for view in found]
        print(f"views={names} target={target!r}")
        for view, name in zip(found, names):
            print(f"  component of {name}: {component_name(view)!r}")
        print(f"  census: {census(found, names)}")
        print("SelectByID2 '<feature>@<component>@<view>', per Type:")
        for view, name in zip(found[1:], names[1:]):
            drawing.ActivateView(name)
            component = component_name(view)
            for feature in FEATURES:
                hits = []
                for type_name in TYPES:
                    document.ClearSelection2(True)
                    if select(document, f"{feature}@{component}@{name}", type_name):
                        hits.append(
                            (
                                type_name or "<empty>",
                                manager.GetSelectedObjectType3(1, -1),
                            )
                        )
                print(f"    {name} {feature!r}: {hits}")
        print("IFeature::Select2 through IView::ReferencedDocument:")
        referenced = found[1].ReferencedDocument
        model = _early_bound(referenced, "IModelDoc2") if referenced else None
        print(f"    ReferencedDocument={model and model.GetPathName()!r}")
        feature = model.FirstFeature() if model else None
        handles = {}
        while feature:
            typed = _early_bound(feature, "IFeature")
            handles[typed.Name] = typed
            feature = typed.GetNextFeature()
        for name in FEATURES:
            handle = handles.get(name)
            document.ClearSelection2(True)
            ok = handle is not None and handle.Select2(False, 0)
            print(
                f"    {name}: Select2={ok} "
                f"drawing selection count={manager.GetSelectedObjectCount2(-1)}"
            )
        document.ClearSelection2(True)
    finally:
        document.ClearSelection2(True)
        app.CloseDoc(str(DRAWING))


# --- recipes: each gets (document, drawing, view name, component name) ---------


def annotations3(option, *, duplicate_dims=True):
    def run(context):
        document, drawing, _, _ = context
        type_name = select_feature(context)
        result = drawing.InsertModelAnnotations3(
            option, MASK, False, duplicate_dims, True, False
        )
        return f"type={type_name} returned={dimension_names(list(result or ()))}"

    return run


def annotations3_view_then_feature(option):
    def run(context):
        document, drawing, view_name, _ = context
        if not select(document, view_name, "DRAWINGVIEW"):
            return "view selection FAILED"
        type_name = select_feature(context, append=True)
        count = document.SelectionManager.GetSelectedObjectCount2(-1)
        result = drawing.InsertModelAnnotations3(option, MASK, False, True, True, False)
        return (
            f"type={type_name} selected={count} "
            f"returned={dimension_names(list(result or ()))}"
        )

    return run


def annotations3_marked(option, mark):
    def run(context):
        document, drawing, _, _ = context
        type_name = select_feature(context, mark=mark)
        result = drawing.InsertModelAnnotations3(option, MASK, False, True, True, False)
        return f"type={type_name} returned={dimension_names(list(result or ()))}"

    return run


def annotations4(option):
    def run(context):
        document, drawing, _, _ = context
        type_name = select_feature(context)
        result = drawing.InsertModelAnnotations4(
            option, MASK, False, True, True, False, False, False
        )
        return f"type={type_name} returned={dimension_names(list(result or ()))}"

    return run


def model_dimensions(option, *, select_view=False):
    def run(context):
        document, drawing, view_name, _ = context
        if select_view and not select(document, view_name, "DRAWINGVIEW"):
            return "view selection FAILED"
        type_name = None if select_view else select_feature(context)
        drawing.InsertModelDimensions(option)
        return f"type={type_name} (InsertModelDimensions returns void)"

    return run


def entire_model_control(context):
    document, drawing, view_name, _ = context
    if not select(document, view_name, "DRAWINGVIEW"):
        return "view selection FAILED"
    result = drawing.InsertModelAnnotations3(0, MASK, False, True, True, False)
    return f"returned={dimension_names(list(result or ()))}"


RECIPES = (
    ("InsertModelAnnotations3(1) feature", annotations3(1)),
    ("InsertModelAnnotations3(2) feature", annotations3(2)),
    ("InsertModelAnnotations3(1) feature, DuplicateDims=False", annotations3(1, duplicate_dims=False)),
    ("InsertModelAnnotations3(1) view+feature", annotations3_view_then_feature(1)),
    ("InsertModelAnnotations3(2) view+feature", annotations3_view_then_feature(2)),
    ("InsertModelAnnotations3(1) feature, mark=1", annotations3_marked(1, 1)),
    ("InsertModelAnnotations4(1) feature", annotations4(1)),
    ("InsertModelDimensions(2) feature", model_dimensions(2)),
    ("InsertModelDimensions(1) feature", model_dimensions(1)),
    ("InsertModelDimensions(0) view [control]", model_dimensions(0, select_view=True)),
    ("InsertModelAnnotations3(0) view [control]", entire_model_control),
)


def run_recipe(app, target, label, recipe):
    document = open_drawing(app)
    try:
        drawing = _early_bound(document, "IDrawingDoc")
        found = views(document)
        names = [view.GetName2() for view in found]
        target_view = found[names.index(target)]
        drawing.ActivateView(target)
        document.ClearSelection2(True)
        before = census(found, names)
        note = recipe((document, drawing, target, component_name(target_view)))
        after = census(found, names)
        print(f"  {label}: {note} arrivals={arrivals(before, after)}")
    finally:
        document.ClearSelection2(True)
        app.CloseDoc(str(DRAWING))


def main():
    if os.environ.get("HARMONIC_SW_AUTOSTART") != "0":
        raise SystemExit("probe requires HARMONIC_SW_AUTOSTART=0: attach, never launch")
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise SystemExit("probe requires the coordinated COM seat")
    app = attach()
    document = open_drawing(app)
    try:
        names = [view.GetName2() for view in views(document)]
    finally:
        app.CloseDoc(str(DRAWING))
    # GetFirstView returns the SHEET's view; the drawing views follow.
    target = TARGET_VIEW or names[2]
    print("\n--- pass: names")
    pass_names(app, target)
    print(f"\n--- pass: imports into {target!r} (each in a fresh document)")
    for label, recipe in RECIPES:
        run_recipe(app, target, label, recipe)
    print(f"\ndocuments left open={app.GetDocumentCount()}")


if __name__ == "__main__":
    main()
