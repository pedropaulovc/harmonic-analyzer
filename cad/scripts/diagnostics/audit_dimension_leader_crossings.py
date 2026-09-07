"""Read-only replay of two retained dimension-leader/frame crossings.

Run with uv in the project venv. No native session, source writes, or guessed
glyph bounds: the fixture contains exact archived native segments and measured
cells from the failed lever pilot. This proves those two intersections only.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _drawing_annotation_bounds import Segment  # noqa: E402
from _drawing_leader_clearance import intersects_cell  # noqa: E402
from _drawing_view_packing import Rect  # noqa: E402


FIXTURE = Path(__file__).with_name("fixtures") / "lever-dimension-crossings.json"


def clip_witness(line, cell):
    """Use the production segment clipper, then report its entry/exit distance."""
    if not intersects_cell(line, cell):
        return None
    near, far = 0.0, 1.0
    radius = line.width_m / 2
    for axis, minimum, maximum in (
        (0, cell.xmin - radius, cell.xmax + radius),
        (1, cell.ymin - radius, cell.ymax + radius),
    ):
        delta = line.end[axis] - line.start[axis]
        if delta == 0:
            continue
        enter, leave = sorted(
            ((minimum - line.start[axis]) / delta, (maximum - line.start[axis]) / delta)
        )
        near, far = max(near, enter), min(far, leave)
    if near > far:
        raise AssertionError("entry/exit witness disagrees with production clipper")
    points = [
        tuple(a + t * (b - a) for a, b in zip(line.start, line.end, strict=True))
        for t in (near, far)
    ]
    return {
        "entry_m": points[0],
        "exit_m": points[1],
        "length_m": math.dist(*points),
        "parameter_interval": (near, far),
    }


def closed_frame(lines):
    """Require four actual axis-aligned frame edges, not an arbitrary AABB."""
    points = [tuple(point) for line in lines for point in (line["start"], line["end"])]
    box = Rect(
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    )
    corners = (
        (box.xmin, box.ymin),
        (box.xmin, box.ymax),
        (box.xmax, box.ymax),
        (box.xmax, box.ymin),
    )
    expected = {frozenset((corners[i], corners[(i + 1) % 4])) for i in range(4)}
    actual = {frozenset((tuple(row["start"]), tuple(row["end"]))) for row in lines}
    if len(lines) != 4 or actual != expected:
        raise ValueError("native frame is not exactly four closed upright edges")
    return box


def replay(fixture):
    rows = fixture["annotations"]
    result = []
    for source, target, frame_start in (
        ("FulcrumDia", "NoseRadius", 0),
        ("RD5", "DetailItem349", 2),
    ):
        native = rows[source]["native"]
        lines = native["lines"]
        # In these two captured circular callouts, the arrow-tail segment joins
        # the sloping leg, which joins the horizontal text shoulder. Therefore
        # line 0 is a leader leg, not an inferred linear extension or frame edge.
        if (
            native["kind"] != 4
            or len(lines) != 3
            or lines[1]["end"] != lines[0]["start"]
            or lines[0]["end"] != lines[2]["start"]
            or lines[2]["start"][1] != lines[2]["end"][1]
            or lines[0]["start"][1] == lines[0]["end"][1]
        ):
            raise ValueError("captured circular callout chain differs from its witness")
        frame = closed_frame(
            rows[target]["native"]["lines"][frame_start : frame_start + 4]
        )
        line = Segment(**lines[0])
        text = Rect(**rows[target]["measurement"]["text_boxes"][0])
        result.append(
            {
                "source": source,
                "target": target,
                "source_line_index": 0,
                "native_frame_m": frame.bounds,
                "frame_intersection": clip_witness(line, frame),
                "text_cell_intersection": clip_witness(line, text),
            }
        )
    return {"provenance": fixture["provenance"], "crossings": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    args = parser.parse_args()
    print(
        json.dumps(
            replay(json.loads(args.fixture.read_text(encoding="utf-8"))), indent=2
        )
    )


if __name__ == "__main__":
    main()
