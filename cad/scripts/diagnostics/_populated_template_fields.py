"""Read-only, explicit title-field regions; accumulate every fit defect."""

from __future__ import annotations

from itertools import combinations
import math
import re

from diagnostics import _baked_template_layout as layout

VALUE_LINKS = {
    "title": layout.TITLE_LINK,
    "number": layout.NUMBER_LINK,
    "revision": layout.REVISION_LINK,
    "material": '$PRPSHEET:"Material"',
    "finish": '$PRPSHEET:"Finish"',
}
LABEL_VALUE = {
    "PART": "title",
    "DWG.  NO.": "number",
    "REV": "revision",
    "MATERIAL": "material",
    "FINISH": "finish",
}
AUTHOR_LINK = re.compile(r'^© \d{4} \$PRPSHEET:"SW-Author\(Author\)"$')


def outer_frame(lines):
    """The two longest horizontal frame rules must have full vertical sides."""
    horizontal = [
        (min(a[0], b[0]), a[1], max(a[0], b[0]))
        for a, b in lines
        if abs(a[1] - b[1]) <= layout.cells.TOPOLOGY_M
    ]
    if not horizontal:
        raise RuntimeError("no measured horizontal sheet frame")
    span = max(right - left for left, _, right in horizontal)
    borders = [
        (left, y, right)
        for left, y, right in horizontal
        if abs(right - left - span) <= layout.cells.TOPOLOGY_M
    ]
    if len(borders) != 2:
        raise RuntimeError("sheet frame horizontal inventory is ambiguous")
    lower, upper = sorted(borders, key=lambda row: row[1])
    if lower[::2] != upper[::2] or lower[1] >= upper[1]:
        raise RuntimeError("sheet frame boundaries disagree")
    left, bottom, right, top = lower[0], lower[1], lower[2], upper[1]
    for x in (left, right):
        if not any(
            abs(a[0] - x) <= layout.cells.TOPOLOGY_M
            and abs(b[0] - x) <= layout.cells.TOPOLOGY_M
            and min(a[1], b[1]) <= bottom
            and max(a[1], b[1]) >= top
            for a, b in lines
        ):
            raise RuntimeError("sheet frame lacks a measured full vertical side")
    return left, bottom, right, top


def footer_region(lines, number_cell, anchor):
    frame = outer_frame(lines)
    region = (frame[0], frame[1], frame[2], number_cell[1])
    if not region[1] < anchor[1] < region[3]:
        raise RuntimeError("copyright is outside designated measured footer strip")
    return region


def intersects_rule(box, endpoints):
    """Closed rectangle/segment intersection, without a coordinate tolerance."""
    lo, hi = 0.0, 1.0
    a, b = endpoints
    for axis in (0, 1):
        delta = b[axis] - a[axis]
        if not delta:
            if a[axis] < box[axis] or a[axis] > box[axis + 2]:
                return False
            continue
        start, end = sorted(
            ((box[axis] - a[axis]) / delta, (box[axis + 2] - a[axis]) / delta)
        )
        lo, hi = max(lo, start), min(hi, end)
        if lo > hi:
            return False
    return True


def native_run_breaks(note, pdf):
    """Reconcile only generated zero-ink CRLF between exact native text runs.

    Full native GetText and ordered display run text must agree independently.
    No character replacement, space normalization or inferred word wrap occurs.
    The raw PDF dictionary remains untouched, including separator boxes/flags.
    """
    runs = note.get("display", {}).get("texts", [])
    values = [run["value"] for run in runs]
    if (
        len(runs) < 2
        or note["display"]["counts"]["Text"] != len(runs)
        or any(not value or "\r" in value or "\n" in value for value in values)
        or "".join(values) != note["text"]
        or "\r\n".join(values) != pdf["text"]
    ):
        raise RuntimeError("native/PDF text does not match exact native run breaks")
    previous_y = math.inf
    for run in runs:
        position = run["position"]
        if (
            len(position) != 3
            or not all(math.isfinite(value) for value in position)
            or not position[1] < previous_y
            or run["angle_rad"] != 0
            or run["reference"] != 1
            or run["inverted"] != 0
            or run["plane"] is not None
        ):
            raise RuntimeError("unsupported native line geometry at PDF run break")
        previous_y = position[1]
    characters = pdf["characters"]
    if (
        any(len(row["text"]) != 1 for row in characters)
        or "".join(row["text"] for row in characters) != pdf["text"]
    ):
        raise RuntimeError(
            "PDF character inventory differs from complete extracted text"
        )
    separators, offset = [], 0
    for index, value in enumerate(values[:-1]):
        offset += len(value)
        for row, expected in zip(characters[offset : offset + 2], "\r\n", strict=True):
            box = row["box_pt"]
            if (
                row["text"] != expected
                or type(row.get("generated")) is not int
                or row["generated"] != 1
                or len(box) != 4
                or not all(math.isfinite(value) for value in box)
                or box[0] != box[2]
                or box[1] != box[3]
            ):
                raise RuntimeError(
                    "native run separator is not generated zero-ink CRLF"
                )
        separators.append(
            {"after_native_run": index, "character_indices": [offset, offset + 1]}
        )
        offset += 2
    return {
        "representation": "pdfium_generated_native_run_breaks",
        "text": note["text"],
        "separators": separators,
    }


def field_audit(notes, lines, *, pdf_reader, symbol_reader=None):
    """Unknown/missing regions and all collisions are failures, not exclusions."""
    fields, issues, regions = {}, [], {}

    def issue(name, kind, error):
        issues.append({"field": name, "kind": kind, "error": str(error)})

    for role, link in VALUE_LINKS.items():
        try:
            name = layout.unique_note(notes, link=link)
            regions[role] = layout.cells.enclosing_cell(lines, notes[name]["position"])
        except Exception as error:
            issue(role, "semantic_region", error)
    for name, row in notes.items():
        if row["visible"] != 1 or (
            "$PRP" not in row["link"] and row["text"] not in LABEL_VALUE
        ):
            continue
        entry = fields[name] = {
            "link": row["link"],
            "native_text": row["text"],
            "status": "pending",
        }
        if not row["text"]:
            if row["extent_scope"] != "observed_zero_ink":
                issue(name, "missing_ink_witness", "empty field has unmeasured ink")
            entry["status"] = (
                "proven_zero_ink"
                if row["extent_scope"] == "observed_zero_ink"
                else "failed"
            )
            continue
        if "$PRP" in row["text"]:
            issue(
                name,
                "unresolved_link",
                "native visible formula remains after source population",
            )
        try:
            role = next(
                (role for role, link in VALUE_LINKS.items() if row["link"] == link),
                None,
            )
            if row["text"] in LABEL_VALUE:
                role = LABEL_VALUE[row["text"]]
            if AUTHOR_LINK.fullmatch(row["link"]):
                region = footer_region(lines, regions["number"], row["position"])
                entry["region_kind"] = "measured_footer_strip"
            elif role is not None:
                region = regions[role]
                entry["region_kind"] = f"semantic_{role}_cell"
            else:
                region = layout.cells.enclosing_cell(lines, row["position"])
                entry["region_kind"] = "measured_cell"
            entry["region_m"] = region
        except Exception as error:
            issue(name, "region", error)
            region = None
        extent = row["extent"]
        entry["native_box_m"] = (extent[0], extent[1], extent[3], extent[4])
        try:
            if region is None:
                raise RuntimeError("no accepted semantic region")
            layout.cells.require_box(
                region, entry["native_box_m"], f"{name} native extent"
            )
        except Exception as error:
            issue(name, "native_fit", error)
        try:
            pdf = (
                symbol_reader(row)
                if symbol_reader is not None and "<" in row["text"]
                else pdf_reader(row["text"])
            )
            entry["pdf"] = pdf
            # Existing repeated ASCII-space policy remains separate. A line
            # separator needs actual PDFium flags plus exact native run proof.
            printed_text = pdf.get("decoded_native_text", pdf["text"])
            if " ".join(filter(None, printed_text.split(" "))) != " ".join(
                filter(None, row["text"].split(" "))
            ):
                entry["text_representation"] = native_run_breaks(row, pdf)
            entry["pdf_box_m"] = tuple(
                value * 0.0254 / 72 for value in pdf["ink_box_pt"]
            )
            if region is None:
                raise RuntimeError("no accepted semantic region")
            layout.cells.require_box(region, entry["pdf_box_m"], f"{name} PDF glyphs")
        except Exception as error:
            issue(name, "pdf_fit", error)
        # Footer is intentionally not called a closed cell. Any real frame rule
        # crossing its native extent or printed glyph union is still a defect.
        if entry.get("region_kind") == "measured_footer_strip":
            for kind in ("native_box_m", "pdf_box_m"):
                if kind in entry:
                    crossings = [
                        index
                        for index, line in enumerate(lines)
                        if intersects_rule(entry[kind], line)
                    ]
                    if crossings:
                        issue(name, f"{kind}_rule_crossing", crossings)
        entry["status"] = (
            "failed" if any(item["field"] == name for item in issues) else "passed"
        )
    for kind in ("native_box_m", "pdf_box_m"):
        for (name, a), (other, b) in combinations(fields.items(), 2):
            if kind not in a or kind not in b:
                continue
            first, second = a[kind], b[kind]
            gap = max(
                second[0] - first[2],
                first[0] - second[2],
                second[1] - first[3],
                first[1] - second[3],
            )
            if gap < layout.FIELD_GAP_M:
                issue(
                    f"{name}/{other}",
                    f"{kind}_clearance",
                    {"observed_m": gap, "required_m": layout.FIELD_GAP_M},
                )
                issues[-1]["fields"] = [name, other]
                a["status"] = b["status"] = "failed"
    return {
        "fields": fields,
        "issues": issues,
        "status": "failed" if issues else "passed",
    }


def audit_retained(receipt, expected_sha256, library_path):
    """Replay every built/cold field from unchanged native rows and actual PDFs.

    This is not a new native run or a replacement for the archived native,
    source, ownership and whole-sheet comparisons. Their raw receipt is pinned.
    """
    import hashlib
    import json
    from pathlib import Path

    from diagnostics import _populated_template_symbols as symbols
    from diagnostics import probe_retained_drawing_export as retained

    def digest(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    if digest(receipt) != expected_sha256:
        raise RuntimeError("retained populated receipt SHA256 differs")
    report = json.loads(receipt.read_text(encoding="utf-8"))
    expected = {str(receipt): expected_sha256, **report["inputs_before"]}
    if report["inputs_before"] != report["inputs_after"]:
        raise RuntimeError("archived original input hashes changed")
    paths = set(expected)
    for trial in report["trials"]:
        if trial["copy_hashes"]["initial"] != trial["copy_hashes"]["final"]:
            raise RuntimeError("archived owned source hash changed")
        expected[trial["source_copy"]] = trial["copy_hashes"]["initial"]
        paths.update(
            [
                trial["source_copy"],
                *trial["artifacts"].values(),
                *trial["cold_artifacts"].values(),
            ]
        )
    initial_hashes = {path: digest(path) for path in sorted(paths)}
    if any(initial_hashes[path] != sha for path, sha in expected.items()):
        raise RuntimeError("retained input/source hash differs from native receipt")
    library = symbols.symbol_library(library_path)
    if (
        str(library_path) not in expected
        or library["sha256"] != expected[str(library_path)]
    ):
        raise RuntimeError("symbol library is not the exact archived input")
    result = {
        "scope": "COM-free complete populated field replay; not a native invocation",
        "receipt_sha256": expected_sha256,
        "original_status": report["status"],
        "inputs_before": initial_hashes,
        "helpers": {
            str(Path(path).resolve()): digest(path)
            for path in (
                __file__,
                symbols.__file__,
                retained.__file__,
                layout.__file__,
                layout.cells.__file__,
            )
        },
        "archived_acceptance_issues": {
            trial["target"]: trial["acceptance_issues"] for trial in report["trials"]
        },
        "targets": {},
    }
    for trial in report["trials"]:
        phases = {}
        for phase, artifacts in (
            ("built", trial["artifacts"]),
            ("cold", trial["cold_artifacts"]),
        ):
            observation = trial["linked_fields"][phase]
            lines = [
                tuple(segment["sheet_points"])
                for segment in observation["template_geometry"]["segments"]
                if segment["kind"] == 0 and segment["role"] == "drawing"
            ]
            pdf = Path(artifacts["pdf"])
            fit = field_audit(
                observation["notes"],
                lines,
                pdf_reader=lambda text: retained.pdf_title(pdf, text),
                symbol_reader=lambda note: symbols.pdf_field(pdf, note, library),
            )
            if fit["fields"].keys() != observation["fit"]["fields"].keys():
                raise RuntimeError("retained field inventory changed during replay")
            # Prove all pre-existing PDF text/ink observations are unchanged;
            # only new generated-character metadata may be absent in the archive.
            for name, row in fit["fields"].items():
                if "pdf" not in row:
                    continue
                raw_pdf = retained.serialized(row["pdf"])
                for character in raw_pdf["characters"]:
                    character.pop("generated", None)
                if raw_pdf != observation["fit"]["fields"][name].get("pdf"):
                    raise RuntimeError(
                        f"retained PDF raw field changed: {trial['target']}/{phase}/{name}"
                    )
            phases[phase] = {"pdf_sha256": digest(pdf), "fit": fit}
        result["targets"][trial["target"]] = phases
    result["inputs_after"] = {path: digest(path) for path in sorted(paths)}
    if result["inputs_after"] != initial_hashes:
        raise RuntimeError("retained files changed during field replay")
    result["status"] = (
        "passed"
        if all(
            phase["fit"]["status"] == "passed"
            for phases in result["targets"].values()
            for phase in phases.values()
        )
        else "failed"
    )
    return result


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="COM-free complete retained field audit"
    )
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--symbol-library", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("field replay output already exists")
    result = audit_retained(args.receipt, args.sha256, args.symbol_library)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, allow_nan=False)
    print(json.dumps({"status": result["status"], "output": str(args.output)}))
    raise SystemExit(0 if result["status"] == "passed" else 1)
