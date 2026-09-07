"""Read-only, explicit title-field regions; accumulate every fit defect."""

from __future__ import annotations

from itertools import combinations
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


def field_audit(notes, lines, *, pdf_reader):
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
            pdf = pdf_reader(row["text"])
            entry["pdf"] = pdf
            # Only separately observed repeated ASCII-space representation may
            # differ; no symbol/line-wrap/text replacement is inferred.
            if " ".join(filter(None, pdf["text"].split(" "))) != " ".join(
                filter(None, row["text"].split(" "))
            ):
                raise RuntimeError("native/PDF field text differs")
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
