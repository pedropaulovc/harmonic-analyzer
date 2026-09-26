"""#923: the rendered-text gate fails any toleranced dimension printing ISO's
``max.``/``min.``, reads only after a forced regen, and fails when it cannot read."""

from __future__ import annotations

import pytest

import _drawing_limit_text as lt

_MAX = 6  # swTolMAX
_NOTE = 6  # swAnnotationType_e.swNote


class _Drawing:
    def __init__(self, rows):
        self.rows = rows
        self.calls: list[str] = []
        self.forced = False

    def EditRebuild3(self):
        self.calls.append("EditRebuild3")

    def ForceRebuild3(self, top_only):
        assert top_only is False
        self.calls.append("ForceRebuild3")
        self.forced = True

    def GetViews(self):
        return self.rows


class _View:
    def __init__(self, name, annotations=()):
        self.name = name
        self.annotations = list(annotations)
        self.updated = 0

    def GetName2(self):
        return self.name

    def GetAnnotations(self):
        return self.annotations

    def UpdateViewDisplayGeometry(self):
        self.updated += 1


class _Tolerance:
    def __init__(self, kind):
        self.Type = kind


class _Dimension:
    def __init__(self, kind):
        self.Tolerance = _Tolerance(kind)


class _DisplayDimension:
    def __init__(self, kind):
        self.kind = kind

    def GetDimension2(self, index):
        return None if self.kind is None else _Dimension(self.kind)


class _DisplayData:
    def __init__(self, texts):
        self.texts = texts

    def GetTextCount(self):
        return len(self.texts)

    def GetTextAtIndex(self, index):
        return self.texts[index]


class _Annotation:
    """A dimension whose text is ``stale`` until the drawing force-rebuilds."""

    def __init__(
        self, name, drawing, *, text, stale=None, tolerance=_MAX, kind=lt._ANNOT_DIM
    ):
        self.name, self.drawing = name, drawing
        self.text, self.stale = text, stale
        self.tolerance, self.kind = tolerance, kind

    def GetName(self):
        return self.name

    def GetType(self):
        return self.kind

    def GetSpecificAnnotation(self):
        return _DisplayDimension(self.tolerance)

    def GetDisplayData(self):
        self.drawing.calls.append(f"read {self.name}")
        text = (
            self.stale
            if self.stale is not None and not self.drawing.forced
            else self.text
        )
        return None if text is None else _DisplayData([text] if text else [])


def _sheet(*annotations_of_view):
    drawing = _Drawing([])
    views = [_View(f"v{index}") for index in range(len(annotations_of_view))]
    for view, specs in zip(views, annotations_of_view, strict=True):
        view.annotations = [_Annotation(name, drawing, **spec) for name, spec in specs]
    drawing.rows = [views]
    return drawing, views


def test_asme_limit_words_pass_and_count_only_toleranced_dimensions():
    drawing, _ = _sheet(
        [
            ("Break", {"text": " 0.1 MAX "}),
            ("Length", {"text": " 12.5 ", "tolerance": lt._TOL_NONE}),
        ],
        [("Note", {"text": "0.5 min. engagement", "kind": _NOTE})],
    )
    assert lt.assert_no_iso_limit_text(drawing, label="post-mount-screw") == 1


def test_iso_limit_words_fail_naming_the_dimension():
    drawing, _ = _sheet(
        [("Break", {"text": " 0.1 max. "}), ("Floor", {"text": " 2.0 MIN. "})]
    )
    with pytest.raises(
        RuntimeError, match=r"2 dimension\(s\) print ISO.*v0/Break.*v0/Floor"
    ):
        lt.assert_no_iso_limit_text(drawing, label="post-mount-screw")


def test_an_untoleranced_dimension_is_not_scanned():
    drawing, _ = _sheet([("Custom", {"text": " 5 min. ", "tolerance": lt._TOL_NONE})])
    assert lt.assert_no_iso_limit_text(drawing, label="x") == 0


def test_it_reads_only_after_a_forced_regen():
    """The diag's first pass read the old words straight after the standard
    changed; the gate must regenerate every view before it reads."""
    drawing, views = _sheet([("Break", {"text": " 0.1 MAX ", "stale": " 0.1 max. "})])
    assert lt.assert_no_iso_limit_text(drawing, label="x") == 1
    assert drawing.calls == [
        "EditRebuild3",
        "ForceRebuild3",
        "EditRebuild3",
        "read Break",
    ]
    assert views[0].updated == 1


def test_unreadable_display_data_fails_loud():
    drawing, _ = _sheet([("Gone", {"text": None}), ("Empty", {"text": ""})])
    with pytest.raises(
        RuntimeError, match=r"no display data for 2 .*v0/Gone.*v0/Empty"
    ):
        lt.assert_no_iso_limit_text(drawing, label="x")


def test_a_dimension_with_no_readable_tolerance_is_scanned():
    drawing, _ = _sheet([("Callout", {"text": " 0.1 max. ", "tolerance": None})])
    with pytest.raises(RuntimeError, match="v0/Callout"):
        lt.assert_no_iso_limit_text(drawing, label="x")


def test_every_sheet_row_is_scanned_including_the_sheet_view():
    drawing, _ = _sheet([("OnSheet", {"text": " 1 max. "})], [])
    second, _ = _sheet([], [("Later", {"text": " 1 min. "})])
    drawing.rows.append(second.rows[0])
    for view in second.rows[0]:
        for annotation in view.annotations:
            annotation.drawing = drawing
    with pytest.raises(RuntimeError, match=r"2 dimension\(s\).*OnSheet.*Later"):
        lt.assert_no_iso_limit_text(drawing, label="x")


def test_finalize_runs_the_gate_after_its_settling_rebuild():
    import inspect

    import _drawing_common as dc

    source = inspect.getsource(dc.finalize_drawing)
    settle = source.index('rebuild_drawing(adapter, label="finalize_drawing")')
    gate = source.index("assert_no_iso_limit_text(drawing_model, label=pdf_title)")
    assert settle < gate < source.index("save_drawing(")
