r"""Read SolidWorks' own mate-error PROSE -- the string the tree tooltip shows.

Neither `IModelDocExtension::GetWhatsWrong` nor `IFeature::GetErrorCode2`
returns a description: both hand back only a numeric `swFeatureError_e`. And the
code is COARSER than the UI text -- 47's enum blurb is the generic "This mate
cannot be solved. Consider: deleting this mate / dragging / adding more mates",
while the live message names the actual cause:

    Distance32: The components cannot be moved to a position which satisfies
    this mate.  Planes are parallel but their alignment is reversed. If the
    components are in the correct orientation, edit this mate and change the
    alignment setting.

That prose IS reachable: SolidWorks writes it into the session message stack
whenever a rebuild produces errors, and `ISldWorks::GetErrorMessages` returns
that stack. So the recipe is

    drain the stack  ->  ForceRebuild3  ->  read the stack  ->  split per mate

Verified 2026-07-25 against the drive-train assembly left failing by the PR #415
cylinder `CopyWithMates2` alignment repro (`Distance32`, code 47).

Traps this probe encodes:

* `GetWhatsWrong` / `GetErrorCode2` / `GetErrorMessages` all take `out` params.
  Call them BARE through the generated wrapper and consume the return tuple --
  makepy defaults every `[out]` to `pythoncom.Missing`. The byref
  `VT_BYREF|VT_VARIANT` form is correct ONLY on a raw late-bound dispatch; pass
  byrefs to an early-bound object and they stay unwritten, which silently reads
  as "no errors found".
* `GetErrorMessages` CLEARS the stack and keeps only the last 20 messages --
  drain BEFORE the rebuild or you parse stale text.
* Every mate problem arrives concatenated into ONE string with no separator
  (``...red error icons.Coincident37: This mate is over...Distance32: The
  components...``), so the per-mate split anchors on the mate NAMES from
  `GetWhatsWrong`, never on punctuation.
* The text is UI-LOCALIZED; the code is not. Decide on the code, explain with
  the text.

Read-only apart from the rebuild; never saves. Run against whatever assembly is
open (SolidWorks already running)::

    uv run python cad\scripts\diagnostics\probe_mate_error_text.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _common import _early_bound, log  # noqa: E402

ERR_NAMES = {
    1: "(folder/component rollup)",
    2: "swFeatureErrorRebuild",
    38: "swFeatureErrorMateInvalidEdge",
    39: "swFeatureErrorMateInvalidFace",
    40: "swFeatureErrorMateFailedCreatingSurface",
    41: "swFeatureErrorMateInvalidEntity",
    42: "swFeatureErrorMateUnknownTangent",
    43: "swFeatureErrorMateDanglingGeometry",
    44: "swFeatureErrorMateEntityNotLinear",
    45: "swFeatureErrorMateEntityFailed",
    46: "swFeatureErrorMateOverdefined",
    47: "swFeatureErrorMateIlldefined",
    48: "swFeatureErrorMateBroken",
}
ALIGN = {0: "ALIGNED", 1: "ANTI_ALIGNED", 2: "CLOSEST"}


def whats_wrong(doc) -> list[tuple[str, int, bool]]:
    """``[(feature_name, swFeatureError_e, is_warning)]`` for the document.

    Bare call, outs consumed from the return tuple -- the generated wrapper
    defaults each ``[out]`` to ``pythoncom.Missing``. (This used to demand the
    RAW late-bound dispatch and pass byref VARIANTs; that form is correct only
    off the makepy path, and mixing them reads as "no errors".)
    """
    ext = _early_bound(doc.Extension, "IModelDocExtension")
    res = ext.GetWhatsWrong()
    if not isinstance(res, tuple) or len(res) < 4:
        raise RuntimeError(f"GetWhatsWrong returned {res!r}, expected a 4-tuple")
    _ret, feats, codes, warns = res
    return [
        (feat.Name, int(code), bool(warn))
        for feat, code, warn in zip(
            feats or [], codes or [], warns or [], strict=False)
    ]


def error_messages(sw) -> list[str]:
    """Drain the session message stack. Read-and-CLEAR, last 20 only."""
    res = _early_bound(sw, "ISldWorks").GetErrorMessages()
    if not isinstance(res, tuple) or len(res) < 2:
        return []
    return list(res[1] or [])


def rebuild_error_text(sw, model) -> str:
    """The prose SolidWorks emits for this document's current rebuild errors."""
    error_messages(sw)              # drain so we read only what the rebuild adds
    model.ForceRebuild3(False)
    return "\n".join(error_messages(sw))


def split_by_feature(blob: str, names: list[str]) -> dict[str, str]:
    """Cut the concatenated blob into per-feature text, anchored on ``names``."""
    hits = sorted((blob.index(f"{n}: "), n) for n in names if f"{n}: " in blob)
    out: dict[str, str] = {}
    for k, (pos, name) in enumerate(hits):
        end = hits[k + 1][0] if k + 1 < len(hits) else len(blob)
        out[name] = blob[pos + len(name) + 2:end].strip()
    return out


def main() -> int:
    import win32com.client

    sw = win32com.client.GetObject(Class="SldWorks.Application")
    doc = sw.GetFirstDocument
    while doc is not None and doc.GetType != 2:
        doc = doc.GetNext
    if doc is None:
        log("no assembly document open in the session")
        return 1

    model = _early_bound(doc, "IModelDoc2")
    # FeatureByName is declared on IAssemblyDoc, not IModelDoc2 (same dispatch).
    by_name = _early_bound(doc, "IAssemblyDoc")
    log(f"document: {doc.GetTitle!r}")

    entries = whats_wrong(doc)
    if not entries:
        log("What's Wrong is empty -- no mate errors or warnings to describe")
        return 0

    texts = split_by_feature(
        rebuild_error_text(sw, model), [n for n, _c, _w in entries])

    for name, code, is_warning in entries:
        sev = "WARNING" if is_warning else "ERROR  "
        print(f"{sev} {name!r}  code={code} ({ERR_NAMES.get(code, '?')})")
        text = texts.get(name)
        if text:
            print(f"        {text}")
        feat = _early_bound(by_name.FeatureByName(name), "IFeature")
        mate = feat.GetSpecificFeature2() if feat is not None else None
        align = getattr(mate, "Alignment", None) if mate is not None else None
        if align is not None:
            print(f"        IMate2: alignment={ALIGN.get(align, align)}"
                  f" flipped={mate.Flipped} canBeFlipped={mate.CanBeFlipped}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
