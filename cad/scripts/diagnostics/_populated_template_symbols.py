"""One observed SW symbol/PDF path form; not a general symbol decoder.

The retained export serializes the angular path on a 0.1 pt grid (plus decimal
serialization/float32 error). That bound identifies its library shape only.
Actual ink bounds and cold raw path equality are never rounded or relaxed.
"""

from __future__ import annotations

import ctypes
import hashlib
import math

from diagnostics import probe_retained_drawing_export as retained
from diagnostics._populated_template_fields import intersects_rule

TOKEN = "<GGTOL-ANGULAR>"
LINK = TOKEN + '\r\n$PRPSHEET:"TOL_ANG"'
GRID_PT = 0.1
SERIALIZATION_PT = 0.00005
PT_PER_M = 72 / 0.0254
DISPLAY_KINDS = {
    "Text",
    "Line",
    "Arc",
    "PolyLine",
    "Triangle",
    "ArrowHead",
    "Polygon",
    "Ellipse",
    "Parabola",
    "Point",
}


def symbol_library(path):
    data = path.read_bytes()
    active_library = active_symbol = ""
    records = []
    for raw in data.decode("utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("#"):
            active_library, active_symbol = line[1:].split(",", 1)[0], ""
            continue
        if line.startswith("*"):
            active_symbol = line[1:].split(",", 1)[0]
            continue
        if (active_library, active_symbol) == ("GGTOL", "ANGULAR"):
            records.append(line)
    expected = ["A,LINE .0,.0,1.6,1.", "A,LINE .0,.0,1.6,.0"]
    if records != expected:
        raise RuntimeError("unsupported installed GGTOL-ANGULAR symbol definition")
    return {
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "token": TOKEN,
        "records": records,
        "grid_lines": [[0.0, 0.0, 1.6, 1.0], [0.0, 0.0, 1.6, 0.0]],
    }


def path_snapshot(obj):
    import pypdfium2.raw as raw

    matrix = tuple(obj.get_matrix().get())
    if obj.level or matrix != (1.0, 0.0, 0.0, 1.0, 0.0, 0.0):
        raise RuntimeError("unsupported transformed/nested angular PDF path")
    count = raw.FPDFPath_CountSegments(obj)
    if not 0 < count <= 20000:
        raise RuntimeError("unsupported angular-area PDF path inventory")
    segments = []
    for index in range(count):
        segment = raw.FPDFPath_GetPathSegment(obj, index)
        x, y = ctypes.c_float(), ctypes.c_float()
        if not segment or not raw.FPDFPathSegment_GetPoint(segment, x, y):
            raise RuntimeError("failed reading angular PDF path endpoint")
        segments.append(
            {
                "kind": raw.FPDFPathSegment_GetType(segment),
                "point_pt": [x.value, y.value],
                "closure": "closed"
                if raw.FPDFPathSegment_GetClose(segment)
                else "open",
            }
        )
    width, fill, stroke = ctypes.c_float(), ctypes.c_int(), ctypes.c_int()
    color = [ctypes.c_uint() for _ in range(4)]
    if not (
        raw.FPDFPageObj_GetStrokeWidth(obj, width)
        and raw.FPDFPath_GetDrawMode(obj, fill, stroke)
        and raw.FPDFPageObj_GetStrokeColor(obj, *color)
    ):
        raise RuntimeError("failed reading angular PDF stroke style")
    return {
        "matrix": list(matrix),
        "segments": segments,
        "ink_box_pt": list(obj.get_bounds()),
        "width_pt": width.value,
        "fill": fill.value,
        "stroke": stroke.value,
        "rgba": [channel.value for channel in color],
    }


def intersects_path(path, extent):
    """A sheet-frame object's whole-page bounds are not local symbol ink."""
    if (
        not all(
            math.isfinite(value)
            for value in [
                *extent,
                path["width_pt"],
                *(
                    value
                    for segment in path["segments"]
                    for value in segment["point_pt"]
                ),
            ]
        )
        or path["width_pt"] <= 0
    ):
        raise RuntimeError("nonfinite or nonpositive angular-area path geometry")
    radius = path["width_pt"] / 2
    box = [
        extent[0] - radius,
        extent[1] - radius,
        extent[2] + radius,
        extent[3] + radius,
    ]
    previous = start = None
    for segment in path["segments"]:
        point, kind = segment["point_pt"], segment["kind"]
        if kind == 2:
            previous = start = point
            continue
        if kind != 0 or previous is None:
            raise RuntimeError("unsupported non-line path crossing the angular area")
        if intersects_rule(box, (previous, point)):
            return True
        previous = point
        if segment["closure"] == "closed" and intersects_rule(box, (point, start)):
            return True
    return False


def require_angular_path(path, library):
    segments = path["segments"]
    values = [value for row in segments for value in row["point_pt"]]
    values += [*path["ink_box_pt"], path["width_pt"]]
    if not all(math.isfinite(value) for value in values):
        raise RuntimeError("nonfinite angular PDF geometry")
    if (
        len(segments) != 4
        or [row["kind"] for row in segments] != [2, 0, 2, 0]
        or any(row["closure"] != "open" for row in segments)
        or path["fill"] != 0
        or path["stroke"] != 1
        or path["rgba"] != [0, 0, 0, 255]
        or path["width_pt"] <= 0
    ):
        raise RuntimeError("unsupported angular PDF topology/style")
    a, b, c, d = [row["point_pt"] for row in segments]
    if a != c or b[0] != d[0] or d[1] != a[1] or b[0] <= a[0] or b[1] <= a[1]:
        raise RuntimeError("PDF does not contain the two directed angular symbol lines")
    residual = max(
        abs(value - round(value / GRID_PT) * GRID_PT)
        for row in segments
        for value in row["point_pt"]
    )
    if residual > SERIALIZATION_PT:
        raise RuntimeError("unsupported angular PDF coordinate grid")
    ratio = library["grid_lines"][0][2] / library["grid_lines"][0][3]
    shape_residual = abs((b[0] - a[0]) - ratio * (b[1] - a[1]))
    # Two independently quantized coordinates form each displacement.
    bound = (1 + ratio) * (GRID_PT + 2 * SERIALIZATION_PT)
    if shape_residual > bound:
        raise RuntimeError("PDF line proportions disagree with the SW symbol library")
    return {
        "status": "library_shape_witnessed",
        "library": library,
        "path": path,
        "grid_pt": GRID_PT,
        "grid_residual_pt": residual,
        "shape_residual_pt": shape_residual,
        "shape_bound_pt": bound,
    }


def pdf_field(path, note, library):
    """Literal notes unchanged; exactly one supported two-run symbol note."""
    text = note["text"]
    if "<" not in text and ">" not in text:
        return retained.pdf_title(path, text)
    rows = note["display"]["texts"]
    literal = text.removeprefix(TOKEN + "\r\n")
    if (
        note["link"] != LINK
        or not text.startswith(TOKEN + "\r\n")
        or not literal
        or "<" in literal
        or ">" in literal
        or len(rows) != 2
        or set(note["display"]["counts"]) != DISPLAY_KINDS
        or [row["value"] for row in rows] != [TOKEN, literal]
        or any(
            row["angle_rad"] != 0
            or row["reference"] != 1
            or row["inverted"] != 0
            or row["plane"] is not None
            for row in rows
        )
        or note["display"]["counts"]
        != {key: 2 if key == "Text" else 0 for key in note["display"]["counts"]}
        or note["display"]["leader_count"]
        or note["display"]["multi_jog_leader_count"]
    ):
        raise RuntimeError("unsupported native linked symbol/text form")
    literal_pdf = retained.pdf_title(path, literal)
    if literal_pdf["text"] != literal:
        raise RuntimeError("angular tolerance literal PDF text differs")
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    extent = [note["extent"][index] * PT_PER_M for index in (0, 1, 3, 4)]
    document = pdfium.PdfDocument(str(path))
    try:
        if len(document) != 1:
            raise RuntimeError("angular witness requires one PDF page")
        paths = []
        for obj in document[0].get_objects(max_depth=1):
            box = obj.get_bounds()
            if (
                box[2] < extent[0]
                or box[0] > extent[2]
                or box[3] < extent[1]
                or box[1] > extent[3]
            ):
                continue
            if obj.type == raw.FPDF_PAGEOBJ_PATH:
                candidate = path_snapshot(obj)
                if intersects_path(candidate, extent):
                    paths.append(candidate)
            elif obj.type != raw.FPDF_PAGEOBJ_TEXT:
                raise RuntimeError("unsupported non-text/path object at angular note")
        if len(paths) != 1:
            raise RuntimeError(
                "angular note must have one unique intersecting PDF path"
            )
        witness = require_angular_path(paths[0], library)
    finally:
        document.close()
    boxes = [literal_pdf["ink_box_pt"], paths[0]["ink_box_pt"]]
    return dict(
        literal_pdf,
        representation="native_symbol_and_literal",
        decoded_native_text=TOKEN + "\r\n" + literal_pdf["text"],
        symbol=witness,
        ink_box_pt=[
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        ],
    )


def audit_retained(receipt, expected_sha256, library_path):
    """COM-free replay of every built/cold symbol witness, pinned receipt bytes."""
    import json
    from pathlib import Path

    data = receipt.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise RuntimeError("retained populated receipt SHA256 differs")
    report = json.loads(data)
    library = symbol_library(library_path)
    result = {"receipt_sha256": expected_sha256, "library": library, "targets": {}}
    for trial in report["trials"]:
        phases = {}
        for phase, artifacts in (
            ("built", trial["artifacts"]),
            ("cold", trial["cold_artifacts"]),
        ):
            notes = trial["linked_fields"][phase]["notes"]
            matches = [note for note in notes.values() if note["link"] == LINK]
            if len(matches) != 1:
                raise RuntimeError("retained angular-note inventory differs")
            pdf = Path(artifacts["pdf"])
            phases[phase] = {
                "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                "witness": pdf_field(pdf, matches[0], library),
            }
        if phases["built"]["witness"] != phases["cold"]["witness"]:
            raise RuntimeError("retained angular PDF changed across cold reopen")
        result["targets"][trial["target"]] = phases
    return result


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="COM-free retained angular PDF witness"
    )
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--symbol-library", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            audit_retained(args.receipt, args.sha256, args.symbol_library),
            indent=2,
            allow_nan=False,
        )
    )
