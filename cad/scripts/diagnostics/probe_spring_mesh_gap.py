"""Read-only exact-coordinate STL gap replay; this does not count native solids."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

SOURCE_SHA256 = "c3f6c95e1b67184a743a412670d985a2efbaa45307849e46962c5c2695df011f"
STL_SHA256 = "d154abf72744102e770dbf8a38e40fba168f2af4903a56a33602a6054076447b"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect_stl(raw):
    """No rounding, repair or removal, including zero-area triangles."""
    count = int.from_bytes(raw[80:84], "little")
    if not 1 <= count <= 200_000 or len(raw) != 84 + count * 50:
        raise ValueError("expected a bounded, complete binary STL triangle bank")
    dtype = np.dtype([
        ("normal", "<f4", (3,)), ("points", "<f4", (3, 3)), ("attribute", "<u2"),
    ])
    triangles = np.frombuffer(raw, dtype=dtype, offset=84)["points"].astype(np.float64)
    if not np.isfinite(triangles).all():
        raise ValueError("nonfinite native STL coordinate")
    vertices, inverse = np.unique(triangles.reshape(-1, 3), axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3)
    parents = list(range(len(vertices)))

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for a, b, c in faces:
        parent = root(int(a))
        parents[root(int(b))] = parent
        parents[root(int(c))] = parent
    labels = np.array([root(index) for index in range(len(vertices))])
    face_labels = labels[faces[:, 0]]
    components = []
    for label in np.unique(face_labels):
        points, tris = vertices[labels == label], triangles[face_labels == label]
        area = np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
        components.append({
            "triangles": len(tris), "vertices": len(points),
            "bounds": [points.min(axis=0).tolist(), points.max(axis=0).tolist()],
            "zero_area_triangles": int(np.count_nonzero(area == 0)),
        })
    slabs = []
    for first, left in enumerate(components):
        for second in range(first + 1, len(components)):
            right = components[second]
            for axis, name in enumerate("XYZ"):
                for low, high, end, start in (
                    (first, second, left["bounds"][1][axis], right["bounds"][0][axis]),
                    (second, first, right["bounds"][1][axis], left["bounds"][0][axis]),
                ):
                    if start > end:
                        slabs.append({"lower": low, "upper": high, "axis": name,
                                      "open_interval": [end, start], "gap_lower_bound": start - end})
    return {"triangle_count": count, "components": components, "separating_slabs": slabs,
            "scope": "exact STL coordinates only; mesh components are not native body counts"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--stl", type=Path, required=True)
    args = parser.parse_args(argv)
    token = args.source.with_name(f".{args.source.stem}.execution")
    protected = {args.source: SOURCE_SHA256, args.stl: STL_SHA256}

    def guard():
        for path, expected in protected.items():
            if digest(path) != expected:
                raise RuntimeError(f"protected artifact SHA differs: {path}")
        if token.read_text(encoding="utf-8").strip() != SOURCE_SHA256:
            raise RuntimeError("spring execution token differs from the retained source")

    guard()
    report = inspect_stl(args.stl.read_bytes())
    guard()
    print(json.dumps({"source": str(args.source), "source_sha256": SOURCE_SHA256,
                      "stl_sha256": STL_SHA256, **report, "final_guards": "exact"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
