"""Offline pins for the MHA-091 callout probe's pure helpers (diag, never merge)."""

from __future__ import annotations

import hashlib
import math

import pytest

from _layout_geometry import Box, Segment
from diagnostics import mha091_callout_probe as probe


def test_file_stamp_reads_size_and_sha256(tmp_path):
    path = tmp_path / "part.SLDPRT"
    path.write_bytes(b"solid")
    stamp = probe.file_stamp(path)
    assert stamp["state"] == "present"
    assert stamp["size"] == 5
    assert stamp["sha256"] == hashlib.sha256(b"solid").hexdigest()
    assert isinstance(stamp["mtime_ns"], int)


def test_file_stamp_says_absent_for_a_missing_file(tmp_path):
    assert probe.file_stamp(tmp_path / "never.SLDDRW") == {"state": "absent"}


def test_discard_verdict_passes_only_when_every_file_is_byte_identical():
    same = {"state": "present", "size": 5, "mtime_ns": 1, "sha256": "a"}
    absent = {"state": "absent"}
    before = {"part": same, "drawing": absent}
    assert probe.discard_verdict(before, {"part": dict(same), "drawing": absent}) == (
        True,
        ["part: unchanged sha256 a", "drawing: absent before and after"],
    )
    ok, rows = probe.discard_verdict(before, {"part": {**same, "sha256": "b"}, "drawing": absent})
    assert not ok and rows[0] == "part: CHANGED sha256 a -> b"
    ok, rows = probe.discard_verdict(before, {"part": same, "drawing": same})
    assert not ok and rows[1] == "drawing: CREATED (absent -> sha256 a)"


def test_discard_verdict_refuses_mismatched_file_sets():
    with pytest.raises(ValueError):
        probe.discard_verdict({"a": {"state": "absent"}}, {"b": {"state": "absent"}})


def test_crop_radius_holds_both_dowel_rims_plus_margin():
    dowels = ((-2.914, -179.050), (2.914, -205.298))
    centre, radius = probe.dowel_pair_crop_mm(dowels, ream_dia_mm=3.162, margin_mm=2.0)
    assert centre == pytest.approx((0.0, -192.174))
    assert radius == pytest.approx(math.hypot(5.828, 26.248) / 2 + 3.162 / 2 + 2.0)


def test_inside_length_clips_a_segment_to_the_view_outline():
    box = Box(0.0, 0.0, 0.010, 0.010)
    # Wholly inside, wholly outside, and crossing the right edge at x = 10 mm.
    assert probe.inside_length(Segment(0.001, 0.001, 0.009, 0.001), box) == pytest.approx(0.008)
    assert probe.inside_length(Segment(0.020, 0.001, 0.030, 0.001), box) == 0.0
    assert probe.inside_length(Segment(0.005, 0.005, 0.015, 0.005), box) == pytest.approx(0.005)
    # A diagonal from inside to outside through the top-right corner region.
    seg = Segment(0.005, 0.005, 0.015, 0.015)
    assert probe.inside_length(seg, box) == pytest.approx(math.hypot(0.005, 0.005))


def test_break_variants_split_the_prefix_where_the_native_tokens_begin_and_before_thru():
    process = "MATCH-DRILL/REAM WITH\nMHA-016 AT ASSEMBLY;\nREAM (.1245 IN)"
    native = "<MOD-DIAM><hw-diam> <hw-tol> THRU"
    prefix = process + " " + native
    variants = dict(probe.break_variants(prefix, process))
    assert variants["process|native"] == process + "\n" + native
    assert variants["before THRU"] == process + " <MOD-DIAM><hw-diam> <hw-tol>\nTHRU"


def test_break_variants_skip_what_they_cannot_find():
    assert probe.break_variants("<MOD-DIAM><hw-diam>", "REAM") == []


def test_run_carries_on_past_failing_steps_discards_and_always_raises(tmp_path, monkeypatch):
    import _common

    part = tmp_path / "cone-swing-platform.SLDPRT"
    part.write_bytes(b"part")
    calls = []

    def boom(*_args, **_kwargs):
        calls.append("step")
        raise RuntimeError("seat said no")

    for name in ("probe_line_break", "probe_cropped_view", "_describe", "_export_pdf"):
        monkeypatch.setattr(probe, name, boom)
    monkeypatch.setattr(_common, "discard_open_documents", lambda adapter: calls.append("discard"))
    with pytest.raises(RuntimeError, match="discard proof ok"):
        probe.run(
            object(),
            source=part,
            slddrw=tmp_path / "cone-swing-platform.SLDDRW",
            dowel_callout=object(),
            process="REAM",
            out_dir=tmp_path,
        )
    assert calls == ["step", "step", "step", "step", "discard"]


def test_run_reports_a_changed_file(tmp_path, monkeypatch):
    import _common

    part = tmp_path / "cone-swing-platform.SLDPRT"
    part.write_bytes(b"part")
    for name in ("probe_line_break", "probe_cropped_view", "_describe", "_export_pdf"):
        monkeypatch.setattr(probe, name, lambda *a, **k: None)
    monkeypatch.setattr(_common, "discard_open_documents", lambda adapter: part.write_bytes(b"saved"))
    with pytest.raises(RuntimeError, match="discard proof FAILED"):
        probe.run(object(), source=part, slddrw=tmp_path / "x.SLDDRW", dowel_callout=object(),
                  process="REAM", out_dir=tmp_path)
