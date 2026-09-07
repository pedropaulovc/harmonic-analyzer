"""Explicit next blank-template variant, derived from pinned populated evidence.

No model is opened during authoring. These translations predict fit for only
the two measured sources; fresh native/printed population must prove it.
"""

from __future__ import annotations

from copy import deepcopy
from enum import StrEnum
import hashlib
import json

from diagnostics import _baked_template_layout as layout


class LayoutPolicy(StrEnum):
    FOUR_NOTES = "four-notes"
    POPULATED_GAPS = "populated-gaps"


PLANNING_HEADROOM_M = 0.0005
ROLES = {
    "title": {"link": layout.TITLE_LINK},
    "title_label": {"text": "PART"},
    "material": {"link": '$PRPSHEET:"Material"'},
    "material_label": {"text": "MATERIAL"},
    "finish": {"link": '$PRPSHEET:"Finish"'},
    "finish_label": {"text": "FINISH"},
}


def read_population(path, sha256, template_sha256):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise RuntimeError("populated layout evidence SHA256 differs")
    report = json.loads(raw)
    if report["inputs_before"] != report["inputs_after"]:
        raise RuntimeError("populated evidence has changed protected inputs")
    templates = [
        value
        for name, value in report["inputs_before"].items()
        if name.replace("\\", "/").endswith("/templates/harmonic-analyzer.DRWDOT")
    ]
    if templates != [template_sha256]:
        raise RuntimeError(
            "populated evidence does not describe this exact source template"
        )
    if report["status"] != "failed" or len(report["trials"]) != 2:
        raise RuntimeError("expected complete two-target failed-fit evidence")
    targets = {}
    for trial in report["trials"]:
        if (
            trial["status"] != "observed"
            or trial["cold_delta"]["changed_leaf_count"] != 0
            or trial["png_delta"]["changed_pixel_count"] != 0
            or trial["printed"]["classification"] != "unchanged"
            or trial["copy_hashes"]["initial"] != trial["copy_hashes"]["final"]
        ):
            raise RuntimeError("populated evidence lacks exact source/cold persistence")
        built, cold = (trial["linked_fields"][phase] for phase in ("built", "cold"))
        if (
            built["notes"] != cold["notes"]
            or built["template_geometry"] != cold["template_geometry"]
        ):
            raise RuntimeError("populated raw note or rule inventory changed")
        target = trial["target"]
        if target in targets:
            raise RuntimeError("duplicate populated evidence target")
        targets[target] = {
            "notes": built["notes"],
            "lines": [
                row["sheet_points"]
                for row in built["template_geometry"]["segments"]
                if "sheet_points" in row
            ],
        }
    if set(targets) != {"rocker_arm", "channel_lever"}:
        raise RuntimeError("populated evidence must contain rocker and lever")
    return {
        "receipt": str(path),
        "sha256": sha256,
        "targets": targets,
        "original_issues": {
            row["target"]: row["acceptance_issues"] for row in report["trials"]
        },
    }


def box(row):
    extent = layout.cells.finite(row["extent"], 6, "populated extent")
    result = (extent[0], extent[1], extent[3], extent[4])
    if result[0] >= result[2] or result[1] >= result[3]:
        raise RuntimeError("populated measurement must have actual positive-area ink")
    return result


def measured_plan(notes, lines, base, targets):
    if set(targets) != {"rocker_arm", "channel_lever"}:
        raise RuntimeError("both populated targets are required")
    names = {
        role: layout.unique_note(notes, **selector) for role, selector in ROLES.items()
    }
    samples = {}
    for target, sample in targets.items():
        if layout.plain(lines) != sample["lines"]:
            raise RuntimeError(
                "populated cell geometry differs from this blank template"
            )
        rows = {
            role: sample["notes"][layout.unique_note(sample["notes"], **selector)]
            for role, selector in ROLES.items()
        }
        for role, row in rows.items():
            current = notes[names[role]]
            expected_position = base.get(names[role], current)["position"]
            expected_alignment = base.get(names[role], current)["horizontal"]
            if (
                any(
                    row[key] != current[key]
                    for key in (
                        "link",
                        "font",
                        "vertical",
                        "lock",
                        "kind",
                        "visible",
                        "owner_type",
                    )
                )
                or row["position"] != list(expected_position)
                or row["horizontal"] != 1
                or expected_alignment != row["horizontal"]
                or row["lock"] != "unlocked"
                or not row["text"]
                or "$PRP" in row["text"]
            ):
                raise RuntimeError(
                    f"{target}/{role}: evidence no longer matches blank note/style/anchor"
                )
            box(row)
        samples[target] = rows
    first = samples["rocker_arm"]
    cells = {
        role: layout.cells.enclosing_cell(lines, first[role]["position"])
        for role in ("title", "material", "finish")
    }
    gap = layout.FIELD_GAP_M + PLANNING_HEADROOM_M
    plan = deepcopy(base)

    def translated(role, dx, dy, cell):
        name, row = names[role], first[role]
        position = [row["position"][0] + dx, row["position"][1] + dy, 0.0]
        if not cell[0] < position[0] < cell[2] or not cell[1] < position[1] < cell[3]:
            raise RuntimeError(
                f"{role}: translated native anchor does not fit its cell"
            )
        plan[name] = {
            "role": role,
            "position": position,
            "cell": cell,
            "horizontal": 1,
            "height_m": row["font"]["CharHeight"],
        }

    for role in ("title", "finish"):
        label_bottom = min(box(rows[role + "_label"])[1] for rows in samples.values())
        value_top = max(box(rows[role])[3] for rows in samples.values())
        translated(role, 0.0, min(0.0, label_bottom - gap - value_top), cells[role])

    # The shallow MATERIAL cell has ample width, not enough vertical stack margin.
    material_cell = cells["material"]
    center = (material_cell[1] + material_cell[3]) / 2
    label = box(first["material_label"])
    left = material_cell[0] + first["material_label"]["font"]["CharHeight"] / 2
    translated(
        "material_label",
        left - label[0],
        center - (label[1] + label[3]) / 2,
        material_cell,
    )
    values = [box(rows["material"]) for rows in samples.values()]
    translated(
        "material",
        left + label[2] - label[0] + gap - min(v[0] for v in values),
        center - (min(v[1] for v in values) + max(v[3] for v in values)) / 2,
        material_cell,
    )

    witness = {
        "planned_gap_m": gap,
        "planning_headroom_m": PLANNING_HEADROOM_M,
        "validated_gap_m": layout.FIELD_GAP_M,
        "targets": {},
    }
    for target, rows in samples.items():
        before = {role: box(row) for role, row in rows.items()}
        after = {}
        for role, row in rows.items():
            position = plan.get(names[role], row)["position"]
            dx, dy = position[0] - row["position"][0], position[1] - row["position"][1]
            after[role] = [
                value + (dx if i % 2 == 0 else dy)
                for i, value in enumerate(before[role])
            ]
            cell = cells[role.removesuffix("_label")]
            layout.cells.require_box(cell, after[role], f"predicted {target}/{role}")
        layout.require_clearance(after, f"predicted {target} native extent")
        witness["targets"][target] = {
            "before": before,
            "predicted_after": after,
            "predicted_gaps_m": {
                "title": after["title_label"][1] - after["title"][3],
                "finish": after["finish_label"][1] - after["finish"][3],
                "material": after["material"][0] - after["material_label"][2],
            },
        }
    return layout.plain(plan), layout.plain(witness)


def static_label_plan(notes, lines, plan):
    result = layout.blank_label_plan(notes, lines, plan)
    for role in ("title", "material", "finish"):
        label = layout.unique_note(notes, **ROLES[role + "_label"])
        if notes[label]["link"] != notes[label]["text"]:
            raise RuntimeError("audited static label became dynamic")
        value = layout.unique_note(notes, **ROLES[role])
        result[label] = {
            "role": role + "_label",
            "cell": layout.cells.enclosing_cell(lines, notes[value]["position"]),
        }
    return result


def phase_scope(notes):
    scope = layout.blank_phase_scope(notes)
    scope.update(
        phase="blank_measured_gap_persistence",
        geometric_acceptance="static_REV_DWG_PART_MATERIAL_FINISH_labels_only",
        material_finish_crowding="predicted_from_two_sources_fresh_population_required",
    )
    return scope
