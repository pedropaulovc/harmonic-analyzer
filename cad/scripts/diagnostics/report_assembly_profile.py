"""Report one completed assembly trace without COM or importing build helpers.

Usage: report_assembly_profile.py TRACE_JSONL TRACE_ID OUTPUT_JSON

Exclusive time subtracts the union of direct-child intervals. Assembly traces
are serial: overlapping siblings are rejected rather than double-counted in
category totals. All original span records and integer nanoseconds are retained.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


UMBRELLAS = frozenset({
    "cone.replicate", "cylinder.replicate", "cylinder.mesh_bank",
    "assembly.geometry_digest", "gate.dof_free_necessity",
    "assembly.final_rebuild", "gate.health", "gate.interference",
    "assembly.reconcile_rebuild",
})
MATE_KINDS = frozenset({
    "lock", "gear", "coincident", "concentric", "distance", "angle",
    "parallel", "rack_pinion", "tangent",
})
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def timestamp_ns(value: str) -> int:
    match = re.fullmatch(r"(.+T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})", value)
    if match is None:
        raise ValueError(f"Invalid timestamp: {value!r}")
    base, fraction, offset = match.groups()
    delta = datetime.fromisoformat(base + offset.replace("Z", "+00:00")) - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000_000 + int(
        (fraction or "").ljust(9, "0")
    )


def union_ns(intervals: list[tuple[int, int]]) -> int:
    covered = 0
    end = None
    for start, stop in sorted(intervals):
        covered += max(0, stop - max(start, end if end is not None else start))
        end = max(stop, end if end is not None else stop)
    return covered


def report(trace_file: Path, trace_id: str) -> dict:
    spans = {}
    selected_hash = hashlib.sha256()
    with trace_file.open("rb") as source:
        for line_number, line in enumerate(source, 1):
            if trace_id.encode("utf-8") not in line:
                continue
            record = json.loads(line)
            if record["context"]["trace_id"] != trace_id:
                continue
            span_id = record["context"]["span_id"]
            if span_id in spans:
                raise ValueError(f"Duplicate span {span_id} at line {line_number}")
            start = timestamp_ns(record["start_time"])
            end = timestamp_ns(record["end_time"])
            if end < start:
                raise ValueError(f"Negative duration in span {span_id}")
            spans[span_id] = {
                "source_line": line_number,
                "record": record,
                "start_ns": start,
                "end_ns": end,
                "duration_ns": end - start,
                "duration_s": (end - start) / 1_000_000_000,
            }
            selected_hash.update(line)
    if not spans:
        raise ValueError(f"Trace {trace_id!r} not found in {trace_file}")

    roots = [item for item in spans.values() if item["record"]["parent_id"] is None]
    if len(roots) != 1:
        raise ValueError(f"Expected one complete trace root, found {len(roots)}")
    root = roots[0]
    children = defaultdict(list)
    for span_id, item in spans.items():
        parent_id = item["record"]["parent_id"]
        if parent_id is None:
            continue
        if parent_id not in spans:
            raise ValueError(f"Span {span_id} has missing parent {parent_id}")
        parent = spans[parent_id]
        if not parent["start_ns"] <= item["start_ns"] <= item["end_ns"] <= parent["end_ns"]:
            raise ValueError(f"Span {span_id} extends outside parent {parent_id}")
        children[parent_id].append(item)

    categories = defaultdict(lambda: {"span_count": 0, "exclusive_ns": 0})
    for span_id, item in spans.items():
        intervals = [(child["start_ns"], child["end_ns"]) for child in children[span_id]]
        covered = union_ns(intervals)
        overlap = sum(end - start for start, end in intervals) - covered
        if overlap:
            raise ValueError(
                f"Span {span_id} has {overlap} ns overlapping children; "
                "serial category totals would double-count their work"
            )
        item["direct_child_count"] = len(intervals)
        item["direct_children_union_ns"] = covered
        item["exclusive_ns"] = item["duration_ns"] - covered
        item["exclusive_s"] = item["exclusive_ns"] / 1_000_000_000
        chain = item
        visited = set()
        umbrella = None
        while chain is not None:
            identity = chain["record"]["context"]["span_id"]
            if identity in visited:
                raise ValueError(f"Parent cycle containing {identity}")
            visited.add(identity)
            name = chain["record"]["name"]
            if umbrella is None and name in UMBRELLAS:
                umbrella = name
            chain = spans.get(chain["record"]["parent_id"])
        kind = item["record"].get("attributes", {}).get("kind")
        category = umbrella or (
            "scalar mates" if kind in MATE_KINDS else item["record"]["name"].split(" ")[0]
        )
        item["category"] = category
        categories[category]["span_count"] += 1
        categories[category]["exclusive_ns"] += item["exclusive_ns"]

    total = sum(item["exclusive_ns"] for item in spans.values())
    if total != root["duration_ns"]:
        raise ValueError("Exclusive attribution does not reconcile to root duration")
    statuses = Counter(item["record"]["status"]["status_code"] for item in spans.values())
    category_rows = [
        {"category": name, **values, "exclusive_s": values["exclusive_ns"] / 1_000_000_000}
        for name, values in categories.items()
    ]
    return {
        "schema_version": 1,
        "trace_file": str(trace_file.resolve()),
        "trace_id": trace_id,
        "selected_records_sha256": selected_hash.hexdigest(),
        "span_count": len(spans),
        "error_span_count": statuses["ERROR"],
        "status_counts": dict(statuses),
        "task": {
            "span_id": root["record"]["context"]["span_id"],
            "name": root["record"]["name"],
            "start_time": root["record"]["start_time"],
            "end_time": root["record"]["end_time"],
            "status": root["record"]["status"],
            "duration_ns": root["duration_ns"],
            "duration_s": root["duration_s"],
            "attributes": root["record"].get("attributes", {}),
            "seat_wait_s": root["record"].get("attributes", {}).get("seat_wait_s"),
        },
        "exclusive_total_ns": total,
        "unattributed_build_ns": categories.get("assembly.build", {}).get("exclusive_ns", 0),
        "categories": sorted(category_rows, key=lambda row: (-row["exclusive_ns"], row["category"])),
        "spans": sorted(spans.values(), key=lambda item: (item["start_ns"], item["source_line"])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_file", type=Path)
    parser.add_argument("trace_id")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.trace_file.resolve() == args.output.resolve():
        parser.error("Output must not overwrite the input trace")
    result = report(args.trace_file, args.trace_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"{args.output.resolve()}: {result['span_count']} spans, "
        f"{result['error_span_count']} errors, {result['task']['duration_s']:.6f} s"
    )


if __name__ == "__main__":
    main()
