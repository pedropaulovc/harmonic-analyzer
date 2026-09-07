"""Offline exact leaf audit of a retained datum-policy pilot receipt.

This reports differences; it is not a tolerance or a replacement CAD gate.
Run with --receipt <pilot.json> --output <new-delta.json>. No COM imports/calls.
Paths use JSON Pointer escaping so view/annotation keys containing / are exact.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path


def _pointer(tokens):
    return "/" + "/".join(
        str(token).replace("~", "~0").replace("/", "~1") for token in tokens
    )


def changed_leaves(before, after):
    """Return every exact changed leaf plus container type/length events."""
    result = []

    def validate(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("snapshot contains a nonfinite numeric field")
        if isinstance(value, dict):
            for item in value.values():
                validate(item)
        if isinstance(value, list):
            for item in value:
                validate(item)

    def emit(tokens, kind, old, new):
        row = {
            "path": _pointer(tokens),
            "tokens": tokens,
            "kind": kind,
            "before": old,
            "after": new,
        }
        if kind == "numeric":
            row["delta"] = new - old
        result.append(row)

    def absent(value, tokens, side):
        items = None
        if isinstance(value, dict):
            items = sorted(value.items())
        if isinstance(value, list):
            items = list(enumerate(value))
        if items:
            for key, item in items:
                absent(item, (*tokens, key), side)
            return
        missing = {"missing": True}
        old, new = (value, missing) if side == "before" else (missing, value)
        emit(tokens, "missing", old, new)

    def walk(old, new, tokens):
        if type(old) is not type(new):
            emit(tokens, "type", old, new)
            return
        if isinstance(old, dict):
            for key in sorted(old.keys() | new.keys()):
                if key not in old:
                    absent(new[key], (*tokens, key), "after")
                    continue
                if key not in new:
                    absent(old[key], (*tokens, key), "before")
                    continue
                walk(old[key], new[key], (*tokens, key))
            return
        if isinstance(old, list):
            if len(old) != len(new):
                emit(tokens, "length", len(old), len(new))
            for index in range(max(len(old), len(new))):
                if index >= len(old):
                    absent(new[index], (*tokens, index), "after")
                    continue
                if index >= len(new):
                    absent(old[index], (*tokens, index), "before")
                    continue
                walk(old[index], new[index], (*tokens, index))
            return
        if old == new:
            return
        kind = "numeric" if type(old) in (int, float) else "value"
        emit(tokens, kind, old, new)

    validate(before)
    validate(after)
    walk(before, after, ())
    return result


def _summary(rows):
    numeric = [row for row in rows if row["kind"] == "numeric"]
    maximum = max((abs(row["delta"]) for row in numeric), default=0.0)
    return {
        "count": len(rows),
        "kinds": dict(Counter(row["kind"] for row in rows)),
        "max_absolute_numeric_delta": maximum,
        "maximum_paths": [
            row["path"] for row in numeric if abs(row["delta"]) == maximum
        ],
    }


def audit_pair(before, after):
    rows = changed_leaves(before, after)
    annotations, fields = defaultdict(list), defaultdict(list)
    for row in rows:
        tokens = row["tokens"]
        if len(tokens) < 3 or tokens[0] != "annotations":
            continue
        annotations[tokens[1]].append(row)
        fields[tokens[2]].append(row)
    direct = [
        row
        for row in rows
        if len(row["tokens"]) >= 3
        and row["tokens"][0] == "annotations"
        and row["tokens"][2] in ("generic", "position")
    ]
    return {
        "scope": "exact JSON observations; numeric units depend on each field; no acceptance tolerance",
        "changed_leaf_count": len(rows),
        "summary": _summary(rows),
        "by_annotation": {name: _summary(group) for name, group in annotations.items()},
        "by_annotation_field": {
            name: _summary(group) for name, group in fields.items()
        },
        "generic_or_anchor_changed_leaf_count": len(direct),
        "semantics_equal": before.get("semantics") == after.get("semantics"),
        "layout_equal": before.get("layout") == after.get("layout"),
        "differences": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--trial", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    raw = args.receipt.read_bytes()
    trial = json.loads(raw)["trials"][args.trial]
    result = audit_pair(trial["built"], trial["reopened"])
    result.update(
        receipt=str(args.receipt.resolve()),
        receipt_sha256=hashlib.sha256(raw).hexdigest(),
        trial=args.trial,
    )
    # Never overwrite the retained raw receipt or an earlier evidence report.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "differences"},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
