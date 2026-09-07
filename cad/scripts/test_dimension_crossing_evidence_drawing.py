"""Archived native leader evidence, not a complete sheet acceptance rule."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from diagnostics import audit_dimension_leader_crossings as audit
from _drawing_annotation_bounds import Segment
from _drawing_leader_clearance import validate_gtol_leader_clearance
from _drawing_view_packing import Rect


def fixture():
    return json.loads(audit.FIXTURE.read_text(encoding="utf-8"))


def test_actual_native_leader_legs_cross_both_complete_frames_and_text_cells():
    result = audit.replay(fixture())
    assert (
        result["provenance"]["sha256"]
        == "bd281f36661a6d52001c6104806df241e31df834e3529c65eb59eeedd399e119"
    )
    first, second = result["crossings"]
    assert first["frame_intersection"]["length_m"] * 1000 == pytest.approx(
        11.730126325819219
    )
    assert first["text_cell_intersection"]["length_m"] * 1000 == pytest.approx(
        10.59875070470509
    )
    assert second["frame_intersection"]["length_m"] * 1000 == pytest.approx(
        8.732147908389264
    )
    assert second["text_cell_intersection"]["length_m"] * 1000 == pytest.approx(
        4.757773160370914
    )


def test_overlapping_diagonal_aabb_is_not_accepted_as_a_line_crossing():
    assert audit.clip_witness(Segment((0, 0), (1, 1)), Rect(0.1, 0.8, 0.2, 0.9)) is None


@pytest.mark.parametrize("fault", ["frame", "chain", "nonfinite"])
def test_changed_native_shape_is_not_guessed(fault):
    data = deepcopy(fixture())
    if fault == "frame":
        data["annotations"]["NoseRadius"]["native"]["lines"][0]["start"][0] += 0.001
    if fault == "chain":
        data["annotations"]["FulcrumDia"]["native"]["lines"][2]["start"][0] += 0.001
    if fault == "nonfinite":
        data["annotations"]["FulcrumDia"]["native"]["lines"][0]["start"][0] = float(
            "nan"
        )
    with pytest.raises(ValueError):
        audit.replay(data)


def test_existing_gtol_only_gate_does_not_cover_these_dimension_targets():
    # Explicit coverage-gap repro. This does NOT broaden production acceptance:
    # the existing helper promises GTol clearance, not every dimension pair.
    data = fixture()
    measured = {}
    for name, row in data["annotations"].items():
        bounds = row["measurement"]
        measured[name] = SimpleNamespace(
            kind=row["native"]["kind"],
            body=Rect(**bounds["body"]) if bounds else None,
            text_boxes=tuple(Rect(**box) for box in bounds["text_boxes"])
            if bounds
            else (),
            text_runs=(),
            native_leader_segments=(),
            native_strokes=tuple(Segment(**line) for line in row["native"]["lines"]),
            leader_decorations=(),
            leader_segments=(),
        )
    assert all(row["frame_intersection"] for row in audit.replay(data)["crossings"])
    observed = validate_gtol_leader_clearance({"front": measured})["front"]
    assert observed["gtol_count"] == 0
    assert observed["crossings"] == observed["reverse_crossings"] == []
