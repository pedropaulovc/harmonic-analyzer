"""Raw diagnostic capture must use native definitions for GTol symbol cells."""

from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from _drawing_annotation_bounds import NativeSnapshot, TextRun
from _drawing_view_packing import Rect
from diagnostics import probe_datum_shoulder as probe


@pytest.mark.parametrize("definition", ["known", "unknown"])
def test_one_snapshot_and_native_definition_per_distinct_symbol(
    monkeypatch, definition
):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    environment = NS(
        GetSymEdgeCounts=Mock(
            return_value=(1, 0, 0, 0, 0) if definition == "known" else (0,) * 5
        ),
        GetSymLines=Mock(return_value=(0.0, 0.0, 0.0, 1.6, 1.0, 0.0)),
    )
    view = NS(GetName2=lambda: "Right")
    annotations, frames = [], []
    for name in ("cylindricity", "runout"):
        frame = NS(GetSymbolXml=lambda: "unchanged frame")
        frames.append(frame)
        specific = NS(GetFrameCount=lambda: 1, GetFrame=lambda _, frame=frame: frame)
        annotations.append(
            NS(
                GetName=lambda name=name: name,
                GetType=lambda: 5,
                OwnerType=0,
                Owner=view,
                Visible=1,
                IsDangling=lambda: False,
                GetAttachedEntities3=lambda: (),
                GetAttachedEntityTypes=lambda: (),
                GetAttachedEntityCount3=lambda: 0,
                GetSpecificAnnotation=lambda specific=specific: specific,
                GetPosition=lambda: (0.1, 0.2, 0),
            )
        )
    for annotation, expected_frame in zip(annotations, frames, strict=True):
        assert annotation.GetSpecificAnnotation().GetFrame(0) is expected_frame
    view.GetAnnotations = lambda: annotations
    app = NS(GetEnvironment=Mock(return_value=environment))
    adapter = NS(
        currentModel=NS(GetViews=lambda: ((view,),), Extension=object()), swApp=app
    )
    native = NativeSnapshot(
        "frame",
        5,
        (0.1, 0.2),
        (TextRun("<GTOL-CYL>", (0.1, 0.2), 0.0035, "Century Gothic", 0, 1, 0),),
        (),
        (),
        (),
        None,
        ("same native format",),
    )
    capture = Mock(return_value=native)
    monkeypatch.setattr(probe, "_native_snapshot", capture)
    monkeypatch.setattr(probe, "raw_display_data", lambda _: {"texts": ()})

    def measured(snapshot, *, symbol_extent=None):
        assert snapshot is native
        if symbol_extent is None:
            raise ValueError("native symbol definition required: '<GTOL-CYL>'")
        return Rect(*symbol_extent("<GTOL-CYL>"))

    monkeypatch.setattr(probe, "bounds_from_snapshot", measured)
    rows, handles = probe.all_annotation_layout(adapter)
    assert len(rows) == len(handles) == 2
    assert capture.call_count == 2  # Not a second annotation_box COM scan.
    for row in rows.values():
        assert row["native"]["format_signature"] == ("same native format",)
        if definition == "unknown":
            assert "measurement" not in row
            assert "unknown native symbol geometry" in row["measurement_exclusion"]
            continue
        assert "measurement_exclusion" not in row
        assert row["measurement"] == {
            "xmin": 0.0,
            "ymin": 0.0,
            "xmax": 1.6,
            "ymax": 1.0,
        }
    assert environment.GetSymEdgeCounts.call_count == (
        1 if definition == "known" else 2
    )
    assert environment.GetSymLines.call_count == (1 if definition == "known" else 0)
