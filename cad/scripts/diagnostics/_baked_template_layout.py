"""One-time owned-template note layout, never imported by production recipes.

Only TITLE, the REV label, and the DWG/REV values may change. The source
template's other native defaults/content remain exact. A saved blank template
is not proof that populated linked fields fit; that needs instantiated drawings.
"""

from __future__ import annotations

from copy import deepcopy
import json
from _drawing_native_display_data import native_display_data
from _drawing_template_defaults import _surface_finish_snapshot
from diagnostics import _linked_title_cell as cells
from diagnostics.probe_fresh_title_update import TITLE_LINK, title_font_format

NUMBER_LINK = '$PRPSHEET:"Number"'
REVISION_LINK = '$PRP:"Revision"$PRPSHEET:"Revision"'
VALUE_HEIGHT_M = 0.0035
FIELD_GAP_M = 0.001


def plain(value):
    return json.loads(json.dumps(value, allow_nan=False))


def note_snapshot(annotation):
    note = cells.required(annotation.GetSpecificAnnotation(), "INote")
    text, link = str(note.GetText() or ""), str(note.PropertyLinkedText or "")
    display = native_display_data(annotation)
    extent = cells.finite(note.GetExtent(), 6, "template note extent")
    zero_ink = (
        not text
        and bool(link)
        and not any(display["counts"].values())
        and not display["leaders"]
        and not display["multi_jog_leader_count"]
    )
    return plain(
        {
            "text": text,
            "link": link,
            "visible": int(annotation.Visible),
            "owner_type": int(annotation.OwnerType),
            "kind": int(annotation.GetType()),
            "position": cells.finite(
                annotation.GetPosition(), 3, "template note anchor"
            ),
            "horizontal": int(note.GetTextJustification()),
            "vertical": int(note.GetTextVerticalJustification()),
            "lock": "locked" if note.LockPosition else "unlocked",
            "font": title_font_format(annotation),
            "display": display,
            "extent": extent,
            "extent_scope": "observed_zero_ink" if zero_ink else "measured",
        }
    )


def note_inventory(adapter):
    drawing = cells.required(adapter.currentModel, "IDrawingDoc")
    groups = tuple(drawing.GetViews() or ())
    if len(groups) != 1 or not groups[0]:
        raise RuntimeError("template layout requires one drawing sheet")
    sheet_view = cells.required(groups[0][0], "IView")
    notes, handles, finishes = {}, {}, []
    for raw in sheet_view.GetAnnotations() or ():
        annotation = cells.required(raw, "IAnnotation")
        kind = int(annotation.GetType())
        if kind == 7:
            finishes.append(_surface_finish_snapshot(adapter, annotation))
            continue
        if kind != 6:
            raise RuntimeError(f"unsupported template annotation kind {kind}")
        name = str(annotation.GetName())
        if not name or name in notes:
            raise RuntimeError("template note names must be unique and nonempty")
        notes[name] = note_snapshot(annotation)
        handles[name] = (annotation, annotation.Owner)
    return (
        notes,
        handles,
        sorted(finishes, key=lambda row: json.dumps(row, sort_keys=True)),
    )


def blank_snapshot(adapter):
    import _drawing_common as drawing

    model = cells.required(adapter.currentModel, "IModelDoc2")
    ddoc = cells.required(model, "IDrawingDoc")
    groups = tuple(ddoc.GetViews() or ())
    if len(groups) != 1 or len(tuple(groups[0])) != 1:
        raise RuntimeError("DRWDOT authoring requires zero model views")
    if cells.required(groups[0][0], "IView").ReferencedDocument is not None:
        raise RuntimeError("DRWDOT authoring has a source model reference")
    sheet = cells.required(ddoc.GetCurrentSheet(), "ISheet")
    notes, handles, finishes = note_inventory(adapter)
    lines, geometry = cells.template_lines(adapter)
    state = {
        "units": {
            str(pref): model.GetUserPreferenceIntegerValue(pref)
            for pref in (263, 47, 49)
        },
        "dimension_styles": {
            name: model.Extension.GetUserPreferenceInteger(
                drawing._PREF_DIM_TEXT_AND_LEADER_STYLE, option
            )
            for name, option in drawing._DIM_DETAILING_SCOPES.items()
        },
        "sheet_properties": sheet.GetProperties2(),
        "sheet_format_visible": sheet.SheetFormatVisible,
        "sheet_mode": ddoc.GetEditSheet(),
        "notes": notes,
        "surface_finishes": finishes,
        "template_geometry": geometry,
    }
    return plain(state), handles, lines


def stable_snapshot(snapshot):
    result = deepcopy(snapshot)
    for row in result["notes"].values():
        if row["extent_scope"] == "observed_zero_ink":
            row.pop("extent")
    return result


def require_equal(before, after, label):
    if stable_snapshot(before) != stable_snapshot(after):
        raise RuntimeError(f"{label}: exact template snapshot changed")


def unique_note(notes, *, link=None, text=None):
    found = [
        name
        for name, row in notes.items()
        if row["visible"] == 1
        and row["owner_type"] == 2
        and (link is None or row["link"] == link)
        and (text is None or row["text"] == text)
    ]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one exact template note link={link!r}, text={text!r}: {found}"
        )
    return found[0]


def layout_plan(notes, lines):
    names = {
        "title": unique_note(notes, link=TITLE_LINK),
        "number": unique_note(notes, link=NUMBER_LINK),
        "revision": unique_note(notes, link=REVISION_LINK),
        "revision_label": unique_note(notes, text="REV"),
        "number_label": unique_note(notes, text="DWG.  NO."),
    }
    boxes = {
        key: cells.enclosing_cell(lines, notes[names[key]]["position"])
        for key in ("title", "number", "revision")
    }
    revision_label = notes[names["revision_label"]]
    label_x = boxes["revision"][0] + revision_label["font"]["CharHeight"] / 2
    targets = {
        "title": cells.left_anchor(
            boxes["title"],
            notes[names["title"]]["position"],
            notes[names["title"]]["font"]["CharHeight"],
        ),
        "number": (
            notes[names["number_label"]]["position"][0],
            notes[names["number"]]["position"][1],
            0,
        ),
        "revision_label": (label_x, revision_label["position"][1], 0),
        "revision": (label_x, notes[names["revision"]]["position"][1], 0),
    }
    plan = {}
    for role, position in targets.items():
        name = names[role]
        row = notes[name]
        if row["lock"] != "unlocked" or row["horizontal"] not in (1, 2):
            raise RuntimeError(f"{role}: unsupported locked/aligned template note")
        cell = boxes["revision" if role == "revision_label" else role]
        if not (cell[0] < position[0] < cell[2] and cell[1] < position[1] < cell[3]):
            raise RuntimeError(f"{role}: requested anchor is outside its measured cell")
        plan[name] = {
            "role": role,
            "position": list(position),
            "cell": cell,
            "horizontal": 1,
            "height_m": VALUE_HEIGHT_M
            if role in ("number", "revision")
            else row["font"]["CharHeight"],
        }
    return plain(plan)


def require_same_handles(app, before, after):
    if before.keys() != after.keys():
        raise RuntimeError("template note inventory changed")
    for name, (annotation, owner) in before.items():
        actual, actual_owner = after[name]
        if (
            int(app.IsSame(annotation, actual)) != 1
            or (owner is None) != (actual_owner is None)
            or (owner is not None and int(app.IsSame(owner, actual_owner)) != 1)
        ):
            raise RuntimeError(f"{name}: exact template annotation/owner replaced")


def require_transition(before, after, plan):
    """Explicit field allowlist, not a blanket skip of the four changed notes."""
    expected, actual = stable_snapshot(before), stable_snapshot(after)
    if expected["notes"].keys() != actual["notes"].keys():
        raise RuntimeError("template layout changed note inventory")
    for name, target in plan.items():
        old, new = expected["notes"][name], actual["notes"][name]
        if new["horizontal"] != 1 or new["position"] != target["position"]:
            raise RuntimeError(f"{name}: layout setter was rejected or clamped")
        if new["font"]["CharHeight"] != target["height_m"]:
            raise RuntimeError(f"{name}: exact template font height differs")
        old["position"], old["horizontal"] = new["position"], new["horizontal"]
        if target["role"] in ("number", "revision"):
            if (
                new["font"]["IsHeightSpecifiedInPts"]
                or new["font"]["GetUseDocTextFormat"]
            ):
                raise RuntimeError("template value must use explicit metre-height font")
            for field in (
                "CharHeight",
                "CharHeightInPts",
                "IsHeightSpecifiedInPts",
                "GetUseDocTextFormat",
            ):
                old["font"][field] = new["font"][field]
        if "extent" in new:
            old["extent"] = new["extent"]
        # Only native glyph positions and the two explicitly resized text heights
        # are layout outputs. Counts/content/font/reference/decorations stay exact.
        if len(old["display"]["texts"]) != len(new["display"]["texts"]):
            raise RuntimeError("template text-run multiplicity changed")
        for old_text, new_text in zip(
            old["display"]["texts"], new["display"]["texts"], strict=True
        ):
            old_text["position"] = new_text["position"]
            if target["role"] in ("number", "revision"):
                if new_text["height_m"] != target["height_m"]:
                    raise RuntimeError(
                        "template value's native displayed height differs"
                    )
                old_text["height_m"] = new_text["height_m"]
    if expected != actual:
        raise RuntimeError("template layout changed fields outside explicit allowlist")


def apply_layout(adapter, handles, plan, receipt, checkpoint):
    """One-time blank-template setters; originals and production recipes untouched."""
    model = adapter.currentModel
    for name, target in plan.items():
        if (
            int(adapter.swApp.IsSame(adapter.currentModel, model)) != 1
            or int(adapter.swApp.IsSame(adapter.swApp.ActiveDoc, model)) != 1
        ):
            raise RuntimeError("template layout lost its exact active owned drawing")
        annotation, owner = handles[name]
        actual_owner = annotation.Owner
        if (owner is None) != (actual_owner is None) or (
            owner is not None and int(adapter.swApp.IsSame(owner, actual_owner)) != 1
        ):
            raise RuntimeError("template layout note owner changed")
        note = cells.required(annotation.GetSpecificAnnotation(), "INote")
        operation = {
            "name": name,
            "role": target["role"],
            "target": target,
            "calls": [],
        }
        receipt.append(operation)
        checkpoint()
        if note.LockPosition:
            raise RuntimeError("refusing to unlock a template note")
        if target["role"] in ("number", "revision"):
            fmt = cells.required(annotation.GetTextFormat(0), "ITextFormat")
            fmt.CharHeight = target["height_m"]
            operation["calls"].append("SetTextFormat")
            returned = annotation.SetTextFormat(0, False, fmt)
            operation["format_return"] = repr(returned)
            checkpoint()
            if returned is not True:
                raise RuntimeError("template native text format setter rejected")
        operation["calls"].append("SetTextJustification")
        note.SetTextJustification(1)
        operation["calls"].append("SetPosition2")
        returned = annotation.SetPosition2(*target["position"])
        operation["position_return"] = repr(returned)
        checkpoint()
        if returned is not True:
            raise RuntimeError("template native note position setter rejected")
    adapter.currentModel.GraphicsRedraw2()  # Documented for font and justification.


def validation_plan(notes, lines, changes):
    result = deepcopy(changes)
    for name, row in notes.items():
        if row["visible"] != 1 or name in result:
            continue
        if "$PRP" not in row["link"] and row["text"] not in {
            "REV",
            "DWG.  NO.",
            "PART",
            "MATERIAL",
            "FINISH",
        }:
            continue
        zero_ink = row["extent_scope"] == "observed_zero_ink"
        result[name] = {
            "role": "other_link_or_label",
            "cell": None if zero_ink else cells.enclosing_cell(lines, row["position"]),
        }
    return result


def blank_label_plan(notes, lines, changes):
    """Only two static labels have source-independent authoring-fit acceptance.

    This does not classify formula tokens as empty or relax the populated fit
    functions. The blank has no source model, so native printed formula widths
    cannot establish the eventual widths of resolved manufacturing values.
    """
    revisions = [
        name for name, row in changes.items() if row["role"] == "revision_label"
    ]
    if len(revisions) != 1:
        raise RuntimeError("blank authoring requires one planned static REV label")
    revision = unique_note(notes, text="REV")
    if revision != revisions[0] or notes[revision]["link"] != "REV":
        raise RuntimeError("blank REV fit target differs from the exact static label")
    number = unique_note(notes, text="DWG.  NO.")
    if notes[number]["link"] != "DWG.  NO.":
        raise RuntimeError("blank DWG label is not exact static content")
    return {
        revision: deepcopy(changes[revision]),
        number: {
            "role": "number_label",
            "cell": cells.enclosing_cell(lines, notes[number]["position"]),
        },
    }


def blank_phase_scope(notes):
    """Retain all native formula ink; defer fit explicitly, never waive it."""
    return {
        "phase": "blank_four_note_persistence",
        "geometric_acceptance": "static_REV_and_DWG_labels_only",
        "unresolved_linked_field_fit": "deferred_until_owned_source_population",
        "copyright_open_footer": "not_accepted_or_fixed",
        "material_finish_crowding": "not_accepted_or_fixed",
        "linked_fields": {
            name: {
                "link": row["link"],
                "native_text": row["text"],
                "extent_scope": row["extent_scope"],
                "native_extent": row["extent"],
                "native_display_counts": row["display"]["counts"],
                "fit_status": "deferred",
            }
            for name, row in notes.items()
            if "$PRP" in row["link"]
        },
    }


def require_field_fit(notes, plan):
    """Resolved native field extents: each own cell plus 1 mm neighboring clearance."""
    boxes = {}
    for name, target in plan.items():
        row = notes[name]
        if not row["text"]:
            if row["extent_scope"] != "observed_zero_ink":
                raise RuntimeError(f"{name}: unresolved field lacks zero-ink witness")
            continue
        extent = row["extent"]
        box = (extent[0], extent[1], extent[3], extent[4])
        cells.require_box(target["cell"], box, f"{target['role']} native extent")
        boxes[name] = box
    return require_clearance(boxes, "native extent")


def require_clearance(boxes, label):
    for i, (name, first) in enumerate(boxes.items()):
        for other, second in list(boxes.items())[i + 1 :]:
            separation = max(
                second[0] - first[2],
                first[0] - second[2],
                second[1] - first[3],
                first[1] - second[3],
            )
            if separation < FIELD_GAP_M:
                raise RuntimeError(
                    f"template fields {name}/{other} lack 1 mm {label} clearance: {separation}"
                )
    return {"checked": list(boxes), "gap_m": FIELD_GAP_M}


def pdf_field_fit(path, notes, plan):
    from diagnostics.probe_retained_drawing_export import pdf_title

    boxes, evidence = {}, {}
    for name, target in plan.items():
        if not notes[name]["text"]:
            continue  # require_field_fit independently requires zero native ink.
        native_text = notes[name]["text"]
        row = pdf_title(path, native_text)
        # Retained native DWG.  NO. exports as DWG. NO. (two ASCII spaces→one).
        # Preserve both raw strings; no character/case/link substitution.
        if " ".join(filter(None, row["text"].split(" "))) != " ".join(
            filter(None, native_text.split(" "))
        ):
            raise RuntimeError(f"{name}: PDF field text differs from native content")
        box = tuple(value * 0.0254 / 72 for value in row["ink_box_pt"])
        cells.require_box(target["cell"], box, f"{name} PDF glyphs")
        boxes[name], evidence[name] = box, {"native_text": native_text, **row}
    return {"fields": evidence, "clearance": require_clearance(boxes, "PDF glyph")}
