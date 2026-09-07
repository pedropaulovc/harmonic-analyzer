"""Minimally populate an explicit immutable DRWDOT with rocker and lever sources.

Reuses the existing one-view owned title trial and its cold/native/PDF/PNG/source
guards. Normal project setup runs unchanged except for its NewDocument template
argument. No new title/layout setter; this is not prepared-default setup or a
full manufacturing recipe. Every linked-field fit problem is retained and makes
acceptance fail, including existing footer/material/finish defects.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

import _drawing_common as common  # noqa: E402
from _drawing_prepared_template import TemplateSpec  # noqa: E402
from _drawing_template_defaults import snapshot_defaults  # noqa: E402
from diagnostics import _baked_template_layout as layout  # noqa: E402
from diagnostics import _populated_template_fields as fields  # noqa: E402
from diagnostics import probe_fresh_title_update as title  # noqa: E402
from diagnostics._owned_native_documents import run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402

TARGETS = {"rocker_arm": "rocker-arm", "channel_lever": "channel-lever"}


def require_template(path, sha256):
    if path.suffix.lower() != ".drwdot" or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("explicit DRWDOT and lowercase SHA256 are required")
    title.retained.require_hashes({str(path): sha256}, "immutable derived DRWDOT")


def preferences(adapter):
    model = layout.cells.required(adapter.currentModel, "IModelDoc2")
    ddoc = layout.cells.required(model, "IDrawingDoc")
    sheet = layout.cells.required(ddoc.GetCurrentSheet(), "ISheet")
    common.assert_asme_b_sheet(
        adapter, sheet, phase="populated template", scale=title.SCALE
    )
    return layout.plain(
        {
            "units": {
                name: int(model.GetUserPreferenceIntegerValue(pref))
                for name, pref in (("system", 263), ("linear", 47), ("decimals", 49))
            },
            "dimension_styles": {
                name: int(
                    model.Extension.GetUserPreferenceInteger(
                        common._PREF_DIM_TEXT_AND_LEADER_STYLE, option
                    )
                )
                for name, option in common._DIM_DETAILING_SCOPES.items()
            },
            "sheet_properties": list(sheet.GetProperties2()),
            "sheet_format_visibility": "visible"
            if sheet.SheetFormatVisible
            else "hidden",
            "sheet_mode": "edit_sheet" if ddoc.GetEditSheet() else "edit_template",
        }
    )


def require_linked_preferences(blank, current):
    """finalize_drawing explicitly changes only the sheet property-source mode."""
    expected = {key: deepcopy(blank[key]) for key in current}
    properties = expected.get("sheet_properties", [])
    if len(properties) != 8 or properties[7] != 1:
        raise RuntimeError(
            "blank template must use the documented inherited property-source mode"
        )
    properties[7] = 0
    if current != expected:
        raise RuntimeError(
            "populated defaults differ from the exact explicit-source phase contract"
        )
    return {
        "field": "ISheet.GetProperties2.sameCustomProp",
        "before": 1,
        "after": 0,
        "operation": "finalize_drawing: SetProperties2(..., False)",
    }


def property_source(adapter, source, source_path, configuration):
    """Witness the actual explicit source; no name-only ownership acceptance."""
    drawing = layout.cells.required(adapter.currentModel, "IDrawingDoc")
    sheet = layout.cells.required(drawing.GetCurrentSheet(), "ISheet")
    views = tuple(common.iter_views(adapter))
    if len(views) != 1:
        raise RuntimeError("minimal populated control requires one exact model view")
    view = layout.cells.required(views[0], "IView")
    name = str(view.GetName2())
    if not name or str(sheet.CustomPropertyView) != name:
        raise RuntimeError("sheet properties do not reference the exact model view")
    if int(adapter.swApp.IsSame(view.ReferencedDocument, source)) != 1:
        raise RuntimeError("sheet property view references a foreign native source")
    if str(view.ReferencedConfiguration) != configuration:
        raise RuntimeError("sheet property view references a different configuration")
    return {
        "view": name,
        "source": str(source_path),
        "configuration": configuration,
        "identity": "exact_native_source",
    }


class PopulatedControl:
    def __init__(self, template, sha256, checkpoint):
        self.template, self.sha256, self.checkpoint = template, sha256, checkpoint
        self.setup = {
            "calls": 0,
            "template_calls": 0,
            "scope": "normal units/styles/scale/rebuild setup; baked title formatting, not prepared defaults",
        }

    def factory(self, adapter, **kwargs):
        if self.setup["calls"]:
            raise RuntimeError("normal setup may run only once")
        require_template(self.template, self.sha256)
        self.setup["calls"] += 1
        original = common.new_drawing

        def redirected(current, *args, **native):
            if (
                current is not adapter
                or args
                or native
                != {
                    "template": str(common.PROJECT_DRWDOT),
                    "width": common.ASME_B_WIDTH_M,
                    "height": common.ASME_B_HEIGHT_M,
                }
                or self.setup["template_calls"]
            ):
                raise RuntimeError("normal NewDocument template contract changed")
            self.setup["template_calls"] += 1
            return original(current, **dict(native, template=str(self.template)))

        start = time.perf_counter()
        common.new_drawing = redirected
        try:
            result = common.new_project_drawing(adapter, **kwargs)
        finally:
            common.new_drawing = original
            self.setup["normal_setup_seconds"] = time.perf_counter() - start
            self.checkpoint()
        if self.setup["template_calls"] != 1:
            raise RuntimeError(
                "normal setup did not consume the derived template exactly once"
            )
        start = time.perf_counter()
        self.setup["normalized_blank_defaults"] = snapshot_defaults(
            adapter, TemplateSpec(title.SCALE, 2)
        )
        self.setup["default_witness_seconds"] = time.perf_counter() - start
        self.checkpoint()
        return result

    def observe(self, adapter, phase, trial, pdf):
        notes, _, finishes = layout.note_inventory(adapter)
        lines, geometry = layout.cells.template_lines(adapter)
        source_path = Path(trial["source_copy"])
        source = layout.cells.required(
            adapter.swApp.GetOpenDocumentByName(str(source_path)), "IModelDoc2"
        )
        if (
            Path(source.GetPathName()).resolve() != source_path
            or int(source.GetType()) != 1
        ):
            raise RuntimeError("linked field witness has wrong exact source document")
        expected = {
            layout.TITLE_LINK: str(source.SummaryInfo(0)),
            layout.NUMBER_LINK: str(source.GetCustomInfoValue("", "Number")),
            layout.REVISION_LINK: str(
                adapter.currentModel.GetCustomInfoValue("", "Revision")
            )
            + str(source.GetCustomInfoValue("", "Revision")),
        }
        row = {
            "notes": notes,
            "surface_finishes": finishes,
            "template_geometry": geometry,
            "preferences": preferences(adapter),
            "expected_link_values": expected,
            "property_source": property_source(
                adapter, source, source_path, trial["source_before"]["configuration"]
            ),
        }
        trial.setdefault("linked_fields", {})[phase] = row
        self.checkpoint()
        row["fit"] = fields.field_audit(
            notes, lines, pdf_reader=lambda text: title.retained.pdf_title(pdf, text)
        )
        issues = row["fit"]["issues"]
        for link, value in expected.items():
            try:
                name = layout.unique_note(notes, link=link)
                if not value or notes[name]["text"] != value:
                    raise RuntimeError(
                        f"expected exact linked value {value!r}, observed {notes[name]['text']!r}"
                    )
            except Exception as error:
                issues.append(
                    {"field": link, "kind": "linked_value", "error": str(error)}
                )
        for link in (layout.TITLE_LINK, layout.NUMBER_LINK, layout.REVISION_LINK):
            try:
                name = layout.unique_note(notes, link=link)
                if notes[name]["horizontal"] != 1:
                    raise RuntimeError("baked linked value is no longer left justified")
                if (
                    link != layout.TITLE_LINK
                    and notes[name]["font"]["CharHeight"] != layout.VALUE_HEIGHT_M
                ):
                    raise RuntimeError("baked DWG/REV value is not exactly 3.5 mm high")
            except Exception as error:
                issues.append(
                    {"field": link, "kind": "baked_format", "error": str(error)}
                )
        initial = self.setup["normalized_blank_defaults"]
        try:
            row["preference_transition"] = require_linked_preferences(
                initial, row["preferences"]
            )
        except RuntimeError as error:
            issues.append(
                {
                    "field": "defaults",
                    "kind": "normal_setup_changed",
                    "error": str(error),
                }
            )
        if phase == "cold":
            built = trial["linked_fields"]["built"]
            old = {
                key: built[key]
                for key in (
                    "notes",
                    "surface_finishes",
                    "template_geometry",
                    "preferences",
                    "expected_link_values",
                    "property_source",
                )
            }
            new = {key: row[key] for key in old}
            try:
                layout.require_equal(old, new, "populated linked-field cold equality")
            except Exception as drift:
                issues.append(
                    {"field": "cold", "kind": "raw_snapshot", "error": str(drift)}
                )
            before_pdf = {
                name: item.get("pdf") for name, item in built["fit"]["fields"].items()
            }
            after_pdf = {
                name: item.get("pdf") for name, item in row["fit"]["fields"].items()
            }
            if before_pdf != after_pdf:
                issues.append(
                    {
                        "field": "cold",
                        "kind": "pdf_field_glyphs",
                        "error": "exact linked-field PDF glyph inventory changed",
                    }
                )
        row["fit"]["status"] = "failed" if issues else "passed"
        self.checkpoint()


async def probe(adapter, template, sha256, source_root, output_root):
    require_template(template, sha256)
    sources = {
        target: (source_root / f"{target.replace('_', '-')}.SLDPRT").resolve(
            strict=True
        )
        for target in TARGETS
    }
    expected = title.pilot.require_sources(sources, sources)
    expected.update(
        {
            str(template): sha256,
            str(common.PROJECT_DRWDOT): title.pilot.attachments.file_digest(
                common.PROJECT_DRWDOT
            ),
        }
    )
    output_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="populated-template-", dir=output_root))
    adapter.ownership.register_directory(directory)
    for path in expected:
        adapter.ownership.register_source(Path(path))
    report = {
        "status": "running",
        "scope": "minimal one-view rocker/lever; baked title format with normal setup; full recipes pending",
        "inputs_before": expected,
        "revision": title.pilot.benchmark.revision("HEAD"),
        "helpers": title.pilot.helper_fingerprints(),
        "adapter": title.pilot.adapter_fingerprints(),
        "trials": [],
        "setups": {},
        "errors": [],
    }
    path = directory / "populated-template.json"

    def checkpoint():
        path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")

    errors = []
    checkpoint()
    try:
        for target, source_title in TARGETS.items():
            # one_trial derives native basenames from its directory name; retain
            # the fresh run nonce here, not a repeated 'rocker_arm' basename.
            trial_dir = directory / f"{directory.name}-{target}"
            trial_dir.mkdir()
            adapter.ownership.register_directory(trial_dir)
            control = PopulatedControl(template, sha256, checkpoint)
            report["setups"][target] = control.setup
            trial = await title.one_trial(
                adapter,
                title.Variant.BASELINE,
                sources[target],
                trial_dir,
                report,
                checkpoint,
                expected,
                source_target=target,
                source_title=source_title,
                factory=control.factory,
                observe_output=control.observe,
            )
            trial["target"] = target
            trial["acceptance_issues"] = [
                {"phase": phase, **item}
                for phase, row in trial["linked_fields"].items()
                for item in row["fit"]["issues"]
            ]
            for name, failed in (
                ("cold_native", trial["cold_delta"]["changed_leaf_count"] != 0),
                ("printed_title", trial["printed"]["classification"] != "unchanged"),
                ("whole_png", trial["png_delta"]["changed_pixel_count"] != 0),
            ):
                if failed:
                    trial["acceptance_issues"].append(
                        {"kind": name, "error": "strict unchanged gate failed"}
                    )
            checkpoint()
        if any(trial["acceptance_issues"] for trial in report["trials"]):
            raise RuntimeError(
                "populated template has unresolved acceptance issues; every field/phase retained"
            )
    except Exception as error:
        errors.append(error)
    finally:
        try:
            await adapter.close_owned_documents()
        except Exception as error:
            errors.append(error)
        report["inputs_after"] = title.retained.final_hashes(expected)
        try:
            title.retained.require_hashes(
                expected, "protected source/template inputs after populated control"
            )
            title.pilot.benchmark.check_fingerprints(
                report["helpers"],
                title.pilot.helper_fingerprints(),
                "frozen populated control",
            )
            if report["adapter"] != title.pilot.adapter_fingerprints():
                raise RuntimeError("imported adapter changed")
        except Exception as error:
            errors.append(error)
        report.update(
            status="failed" if errors else "passed",
            errors=[repr(error) for error in errors],
        )
        try:
            checkpoint()
        except Exception as error:
            errors.append(error)
    if errors:
        raise ExceptionGroup("populated template control failed", errors)
    return {"report": str(path), "outcome": "minimal_populated_template_passed"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--template-sha256", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, default=ROOT / "cad/out/reports")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    if (
        os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off"
        or not os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID", "").isdecimal()
    ):
        raise RuntimeError("populated control requires remote off and expected PID")
    template, source_root = (
        args.template.resolve(strict=True),
        args.source_root.resolve(strict=True),
    )
    require_template(template, args.template_sha256)
    if args.worker:
        return run_copy_diagnostic(
            lambda adapter: probe(
                adapter,
                template,
                args.template_sha256,
                source_root,
                args.report_root.resolve(),
            )
        )
    import dodo

    dodo._run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--template",
            str(template),
            "--template-sha256",
            args.template_sha256,
            "--source-root",
            str(source_root),
            "--report-root",
            str(args.report_root.resolve()),
            "--worker",
        ],
        "populated baked template control",
        com=True,
        log_stem="populated-template",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
