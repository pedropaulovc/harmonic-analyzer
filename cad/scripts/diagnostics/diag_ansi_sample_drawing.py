"""diag (never merge): one real drawing on the re-based true-ANSI template (#923).

``argv[1]`` names a registered LANDSCAPE drawing (``post_mount_screw``, the one
sheet with a MAX limit dimension, or ``cone_tip_block``, with Ra, hole callouts
and a section). The user asked to see a real sheet on the ANSI template before
any template binary is committed. This leaf:

1. re-bases a copy of the landscape template in-process with the re-base
   leaf's own functions (13 = 2 -> 1, then the manifest's restores), so it does
   not depend on that leaf's cached output;
2. points the registry's landscape entry at that copy, for this process only;
3. redirects the draw module's OUTPUTS to ``cad/out/ansi-sample/``, so the real
   ``drawing:<stem>`` targets are never written;
4. moves every drawing Ra from text 8 to text 5 (the ruled ANSI field) through
   a proxy on the ISFSymbol that ``_drawing_common.add_surface_finish`` gets,
   without editing ``_drawing_common`` (no drawing re-keys);
5. runs the real ``draw_<stem>.build()``, with every gate it carries, then
   reads back what each toleranced dimension and Ra prints.

The side-by-side "today" sheet is the real ``drawing:<stem>`` output at the same
base commit. The PDF and PNG ride the task log as base64.
"""

from __future__ import annotations

import dataclasses
import importlib
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
import _telemetry
import ansi_template_manifest as manifest
from _common import _early_bound, run_build
from _drawing_common import DrawingOutputs
from _drawing_limit_text import assert_no_iso_limit_text
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from diagnostics import diag_ansi_template_rebase as leaf

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "out" / "ansi-sample"
SAMPLES = ("post_mount_screw", "cone_tip_block")
_ANNOT_SF = 7  # swAnnotationType_e.swSFSymbol
_ANSI_ROUGHNESS_TEXT = 5  # swSFSymbolMaximumRoughness (leaf ansi-rebase-7494)
_ISO_ROUGHNESS_TEXT = 8  # swSFSymbolRoughnessValue1, today's field


def sample_outputs(stem: str) -> DrawingOutputs:
    base = SAMPLE_DIR / DRAWINGS_BY_NAME[stem].artifact_stem
    return DrawingOutputs(
        slddrw=base.with_suffix(".SLDDRW"),
        pdf=base.with_suffix(".pdf"),
        png=base.with_suffix(".png"),
    )


def _log(message: str) -> None:
    _telemetry.warn(f"ansi-sample {message}")


class _RoughnessInAnsiField:
    """ISFSymbol whose roughness text (8 today) lands in ANSI's text 5."""

    def __init__(self, symbol: Any) -> None:
        object.__setattr__(self, "_symbol", symbol)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._symbol, name)

    @staticmethod
    def _field(index: int) -> int:
        return _ANSI_ROUGHNESS_TEXT if index == _ISO_ROUGHNESS_TEXT else index

    def SetText(self, index: int, text: str) -> Any:  # noqa: N802 - COM name
        return self._symbol.SetText(self._field(index), text)

    def GetText(self, index: int) -> Any:  # noqa: N802 - COM name
        return self._symbol.GetText(self._field(index))


def _move_roughness_to_ansi_field() -> None:
    original = _sw_type_info.early_bound_or_flag

    def early_bound_or_flag(obj: Any, interface: str, *members: str) -> Any:
        bound = original(obj, interface, *members)
        if interface == "ISFSymbol":
            return _RoughnessInAnsiField(bound)
        return bound

    _sw_type_info.early_bound_or_flag = early_bound_or_flag


def _rebased_template(adapter: Any, layout: DrawingLayout) -> Path:
    source = DRAWING_TEMPLATES[layout].path
    work = SAMPLE_DIR / f"work-{source.name}"
    result = SAMPLE_DIR / f"ansi-{source.name}"
    for path in (work, result):
        if path.exists():
            path.unlink()
    shutil.copyfile(source, work)
    model = leaf._open(adapter, work)
    ext = model.Extension
    b0 = leaf._dump(ext)
    for value in manifest.REBASE_SEQUENCE:
        ext.SetUserPreferenceInteger(manifest.STANDARD_PREF, 0, value)
    model.EditRebuild3()
    leaf._write_restores(ext, b0)
    model.EditRebuild3()
    _log(f"template re-based: {leaf._standard(ext)!r}")
    model.SaveAs3(str(result), 0, 1)
    leaf._close(adapter, model)
    work.unlink()
    return result


def _readback(adapter: Any, stem: str, outputs: DrawingOutputs) -> dict[str, object]:
    """Reopen the saved sample: every toleranced dimension's printed text
    through the limit-text gate, and every Ra symbol's printed text."""
    model = leaf._open(adapter, outputs.slddrw)
    out: dict[str, object] = {}
    try:
        out["limit_gate_scanned"] = assert_no_iso_limit_text(
            model, label=f"ansi-sample-{stem}"
        )
    except RuntimeError as exc:
        out["limit_gate_error"] = str(exc)
    finishes: list[dict[str, object]] = []
    ddoc = _early_bound(model, "IDrawingDoc")
    for row in ddoc.GetViews() or ():
        for raw_view in row or ():
            view = _early_bound(raw_view, "IView")
            for raw in view.GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                if int(annotation.GetType()) != _ANNOT_SF:
                    continue
                symbol = _early_bound(annotation.GetSpecificAnnotation(), "ISFSymbol")
                finishes.append(
                    {
                        "where": f"{view.GetName2()}/{annotation.GetName()}",
                        "text5": str(symbol.GetText(_ANSI_ROUGHNESS_TEXT) or ""),
                        "text8": str(symbol.GetText(_ISO_ROUGHNESS_TEXT) or ""),
                        "prints": leaf._rendered(annotation),
                    }
                )
    out["surface_finishes"] = finishes
    leaf._close(adapter, model)
    _log(f"{stem} readback {out!r}")
    return out


async def build(adapter: Any) -> dict[str, str]:
    stem = sys.argv[1]
    if stem not in SAMPLES:
        raise ValueError(f"not a sample drawing: {stem!r} (one of {SAMPLES})")
    spec = DRAWINGS_BY_NAME[stem]
    if spec.layout != DrawingLayout.LANDSCAPE:
        raise ValueError(f"{stem}: only the landscape template is re-based here")
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    outputs = sample_outputs(stem)
    template = _rebased_template(adapter, spec.layout)

    module = importlib.import_module(spec.script_name.removesuffix(".py"))
    module.OUTPUTS = outputs
    for name in ("SLDDRW", "PDF", "PNG"):
        if hasattr(module, name):
            setattr(module, name, getattr(outputs, name.lower()))
    tracked = DRAWING_TEMPLATES[spec.layout]
    DRAWING_TEMPLATES[spec.layout] = dataclasses.replace(tracked, path=template)
    _move_roughness_to_ansi_field()
    try:
        result = await module.build(adapter)
    finally:
        DRAWING_TEMPLATES[spec.layout] = tracked
    for path in (outputs.slddrw, outputs.pdf, outputs.png):
        if not path.is_file():
            raise RuntimeError(f"{stem}: sample output missing: {path}")
    readback = _readback(adapter, stem, outputs)
    leaf._emit_blob(f"pdf-{stem}", outputs.pdf.read_bytes())
    leaf._emit_blob(f"png-{stem}", outputs.png.read_bytes())
    if "limit_gate_error" in readback:
        raise RuntimeError(f"{stem}: {readback['limit_gate_error']}")
    blank = [f for f in readback["surface_finishes"] if not f["prints"]]
    if blank:
        raise RuntimeError(f"{stem}: surface-finish symbols print no Ra: {blank}")
    return {key: str(value) for key, value in result.items()}


if __name__ == "__main__":
    sys.exit(run_build(build))
