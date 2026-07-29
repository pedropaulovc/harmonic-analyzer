r"""Plain (non-DimXpert) model gtols/datum tag: the COM-controllable quadrant?

DimXpert PMI placement is UI-drag-only (see memory/dimxpert-pmi-placement).
This probe tests whether ORDINARY model annotations — IModelDoc2::InsertGtol
and ::InsertDatumTag2, attached to the same spec faces, filled with the same
frame XML — are fully COM-controllable end to end:

1. PART: author datum tag A (base) + two gtols (seat) on a COPY of the built
   part; SetPosition to distinct spots; save; reopen; positions persisted?
2. SHEET: front + section drawing; InsertModelAnnotations3(datums|gtols);
   where do they land; SetPosition on sheet; save; reopen; persisted?
3. B&W PDF render for the eye pass.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/probe_pmi_plain_annotations.py
"""

from __future__ import annotations

import asyncio
import math
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
import _watchdog  # noqa: E402
from _common import CAD_ROOT, _early_bound, _read_member  # noqa: E402
from _drawing_common import create_section_view, model_point_in_view  # noqa: E402
from _part_pmi import _resolve_faces, _select_face  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter  # noqa: E402
from transgear_stub_spec import GEOMETRIC_CONTROLS, PART_DATUMS  # noqa: E402

SOURCE = CAD_ROOT / "out" / "sldprt" / "transgear-stub.SLDPRT"
SCRATCH_PRT = CAD_ROOT / "out" / "sldprt" / "transgear-stub-plain.SLDPRT"
SCRATCH_DRW = CAD_ROOT / "out" / "slddrw" / "transgear-stub-plain.SLDDRW"
OUT_PDF = CAD_ROOT / "out" / "pdf" / "transgear-stub-plain.pdf"
SEAT_MID_Y = 0.016

# part-space targets (model metres), well separated
PART_TARGETS = {
    "datum:A": (0.012, 0.002, 0.010),
    GEOMETRIC_CONTROLS[0].key: (-0.018, 0.016, 0.008),
    GEOMETRIC_CONTROLS[1].key: (0.018, 0.016, -0.008),
}
# sheet-space targets (sheet metres)
SHEET_TARGETS = [(0.205, 0.115), (0.205, 0.185), (0.275, 0.115)]

_INSERT_DATUMS = 0x2
_INSERT_GTOLS = 0x20


def _plain_gtols_and_datums(model):
    """Every non-DimXpert gtol (t5) / datum tag (t2) in the doc, by name."""
    out = {}
    annotation = model.GetFirstAnnotation2()
    while annotation is not None:
        item = _early_bound(annotation, "IAnnotation")
        if int(item.GetType()) in (2, 5) and not bool(item.IsDimXpert()):
            out[str(item.GetName())] = item
        annotation = item.GetNext3()
    return out


def _sheet_items(draw):
    ddoc = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(ddoc.GetFirstView(), "IView")
    out = {}
    while True:
        raw = view.GetNextView()
        if raw is None:
            break
        view = _early_bound(raw, "IView")
        vname = str(view.GetName2())
        for raw_ann in tuple(view.GetAnnotations() or ()):
            item = _early_bound(raw_ann, "IAnnotation")
            if int(item.GetType()) in (2, 5):
                out[f"{vname}/{item.GetName()}"] = item
    return out


async def main() -> int:
    _telemetry.set_service("diagnostics")
    adapter = PyWin32Adapter({})
    _watchdog.start()
    try:
        await adapter.connect()
        adapter.swApp.CloseAllDocuments(True)
        shutil.copy2(SOURCE, SCRATCH_PRT)
        SCRATCH_DRW.unlink(missing_ok=True)

        check = await adapter.open_model(str(SCRATCH_PRT))
        if not check.is_success:
            raise RuntimeError(f"part open failed: {check.error}")
        model = adapter.currentModel
        requests = {datum.key: datum.face for datum in PART_DATUMS}
        requests.update({control.key: control.face for control in GEOMETRIC_CONTROLS})
        resolved_faces = _resolve_faces(model, requests)

        datum = PART_DATUMS[0]
        face = resolved_faces[datum.key]
        _select_face(model, face, label="plain datum A")
        tag = model.InsertDatumTag2()
        if tag is None:
            raise RuntimeError("InsertDatumTag2 returned None")
        tag = _early_bound(tag, "IDatumTag")
        if not tag.SetLabel(datum.letter):
            raise RuntimeError("datum tag SetLabel failed")
        tag_ann = _early_bound(tag.GetAnnotation(), "IAnnotation")
        authored = {"datum:A": tag_ann}

        for control in GEOMETRIC_CONTROLS:
            face = resolved_faces[control.key]
            _select_face(model, face, label=control.key)
            gtol = model.InsertGtol()
            if gtol is None:
                raise RuntimeError(f"InsertGtol returned None for {control.key}")
            gtol = _early_bound(gtol, "IGtol")
            if int(gtol.GetFormat()) != 2:
                # same flow as add_feature_control_frame's migrated branch:
                # SW 2026 drops the tolerance display if an EMPTY old-format
                # gtol is converted first and populated afterward — seed the
                # simple compartments, THEN convert.
                from _gtol_spec import GTOL_SYMBOLS

                datum_values = [*control.datums[:3], "", "", ""][:3]
                gtol.SetFrameSymbols2(
                    1,
                    f"<{GTOL_SYMBOLS[control.characteristic]}>",
                    control.tolerance_zone == "diametral",
                    "",
                    False,
                    "",
                    "",
                    "",
                    "",
                )
                if not gtol.SetFrameValues2(1, control.tolerance, "", *datum_values):
                    raise RuntimeError(f"{control.key}: SetFrameValues2 failed")
                converted = int(gtol.ConvertFormat())
                if converted != 0:
                    raise RuntimeError(
                        f"{control.key}: ConvertFormat error {converted}"
                    )
            frame = _early_bound(gtol.GetFrame(1), "IGtolFrame")
            applied = str(frame.GetSymbolXml() or "")
            if control.tolerance not in applied:
                raise RuntimeError(
                    f"{control.key}: tolerance missing after seed+convert "
                    f"(read back {applied[:120]!r})"
                )
            authored[control.key] = _early_bound(gtol.GetAnnotation(), "IAnnotation")

        for key, item in authored.items():
            target = PART_TARGETS[key]
            ok = bool(item.SetPosition2(*target))
            after = tuple(item.GetPosition() or ())
            _telemetry.info(
                f"part {key} ({item.GetName()}): SetPosition2={ok} "
                f"-> {tuple(round(v, 5) for v in after)}"
            )
        names = {key: str(item.GetName()) for key, item in authored.items()}

        model.ClearSelection2(True)
        model.SaveAs3(os.path.abspath(SCRATCH_PRT), 0, 0)
        adapter.swApp.CloseAllDocuments(True)

        check = await adapter.open_model(str(SCRATCH_PRT))
        if not check.is_success:
            raise RuntimeError(f"part reopen failed: {check.error}")
        model = adapter.currentModel
        reopened = _plain_gtols_and_datums(model)
        for key, name in names.items():
            item = reopened.get(name)
            if item is None:
                _telemetry.warn(f"part {key} ({name}): MISSING after reopen")
                continue
            final = tuple(item.GetPosition() or ())
            t = PART_TARGETS[key]
            drift = math.dist(final, t)
            verdict = "PERSISTED" if drift < 0.0005 else "REVERTED"
            _telemetry.info(
                f"part {verdict} {key}: {tuple(round(v, 5) for v in final)} "
                f"drift={drift * 1000:.2f}mm"
            )
        adapter.swApp.CloseAllDocuments(True)

        from solidworks_mcp.adapters.solidworks.drawing import new_drawing, place_view

        new_drawing(adapter)
        draw = adapter.currentModel
        ddoc = _early_bound(draw, "IDrawingDoc")
        front = _early_bound(
            place_view(
                adapter, str(SCRATCH_PRT), "*Front", 0.09, 0.15, scale=(4.0, 1.0)
            ),
            "IView",
        )
        cut_x, cut_y = model_point_in_view(
            adapter, front, (0.0, SEAT_MID_Y, 0.0), label="seat mid"
        )
        create_section_view(
            adapter,
            front,
            line_start=(cut_x - 0.04, cut_y),
            line_end=(cut_x + 0.04, cut_y),
            view_xy=(0.24, 0.15),
            section_label="C",
            scale=(4, 1),
            label="plain pmi section",
        )
        inserted = ddoc.InsertModelAnnotations3(
            0, _INSERT_DATUMS | _INSERT_GTOLS, True, True, False, False
        )
        count = len(tuple(inserted or ()))
        _telemetry.info(f"InsertModelAnnotations3 (all views) -> {count} items")
        items = _sheet_items(draw)
        for label, item in items.items():
            _telemetry.info(
                f"sheet {label}: t{item.GetType()} "
                f"{tuple(round(v, 5) for v in tuple(item.GetPosition() or ()))}"
            )
        moved = {}
        for (label, item), (tx, ty) in zip(sorted(items.items()), SHEET_TARGETS):
            ok = bool(item.SetPosition2(tx, ty, 0.0))
            moved[label] = (tx, ty)
            _telemetry.info(
                f"sheet move {label}: SetPosition2={ok} target=({tx}, {ty})"
            )
        draw.ClearSelection2(True)
        sw = adapter.swApp
        sw.SetUserPreferenceToggle(323, False)
        try:
            draw.SaveAs3(os.path.abspath(OUT_PDF), 0, 0)
        finally:
            sw.SetUserPreferenceToggle(323, True)
        draw.SaveAs3(os.path.abspath(SCRATCH_DRW), 0, 0)
        adapter.swApp.CloseAllDocuments(True)

        check = await adapter.open_model(str(SCRATCH_DRW))
        if not check.is_success:
            raise RuntimeError(f"drawing reopen failed: {check.error}")
        for label, item in _sheet_items(adapter.currentModel).items():
            final = tuple(item.GetPosition() or ())
            target = moved.get(label)
            verdict = ""
            if target is not None:
                drift = math.hypot(final[0] - target[0], final[1] - target[1])
                verdict = (
                    f" {'PERSISTED' if drift < 0.0005 else 'REVERTED'} "
                    f"drift={drift * 1000:.2f}mm"
                )
            _telemetry.info(
                f"reopened sheet {label}: {tuple(round(v, 5) for v in final)}{verdict}"
            )
        adapter.swApp.QuitDoc(str(_read_member(adapter.currentModel, "GetTitle")))
        _telemetry.success(f"plain-annotation probe complete: {OUT_PDF}")
        return 0
    finally:
        await adapter.disconnect()
        _watchdog.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
