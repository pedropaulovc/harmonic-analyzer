"""Repro: can this seat AUTHOR DimXpert geometric tolerances on a PART?

Backs the open question behind the drawing-purity audit: every feature control
frame the project ships is authored per-SHEET (``_drawing_common.
add_feature_control_frame``, 125 ``tolerance="..."`` literals across 55 drawing
scripts).  Moving them to model PMI needs FIVE mechanics to hold, none of them
previously exercised here.  This probe answers each one with a logged return
value rather than an argument.

Q1  ``IModelDocExtension::DimXpertManager(config, True).DimXpertPart`` resolves
    through LATE binding -- ``IDimXpertPart`` lives in ``swdimxpert.tlb``, which
    is absent from the vendored ``_generated/sldworks_2026.py`` makepy wrapper,
    so ``_sw_type_info.early_bound`` cannot reach it.
Q2  ``InsertDatum`` attaches a datum to a face selected in PART space (the
    repo's selection machinery is all drawing-view based).
Q3  ``InsertGtol(<type>)`` returns an ``IDimXpertAnnotation``.
Q4  The empty Gtol it creates (documented default: 0.02 for Tolerance 1) can be
    FILLED.  Two candidate paths, both tried with read-back:
      * ``IGtolFrame::SetSymbolXml`` -- the current-format path already live and
        read-back-verified in ``_drawing_common.add_feature_control_frame``; and
      * ``IGtol::SetFrameSymbols2`` / ``SetFrameValues2`` + ``ConvertFormat`` --
        the path ``InsertGtol``'s own Remarks prescribe, whose docs carry
        "valid only if this Gtol was created in a version of SOLIDWORKS earlier
        than 2022".  ``add_feature_control_frame`` already uses exactly this
        pair to SEED an old-format frame before converting it, so the note means
        "old-format only", not "removed" -- which is why it is worth trying.
Q5  Part PMI reaches a SHEET: ``IDrawingDoc::InsertModelAnnotations3`` with the
    DimXpert filter.  Q1-Q4 are pointless if the annotations never print.

``swDimXpertGtolType_e`` -- the enum ``InsertGtol``'s only parameter takes -- is
ABSENT from the offline API-doc bundle, so this probe reads it straight off the
installed ``swdimxpert.tlb`` (``_gtol_type_map``) and ASSERTS the members it
uses.  That is the same "read it off the type library, do not guess" move
``_drawing_common`` documents for the undocumented detailing preferences.  A
blind ``InsertGtol(t) for t in range(30)`` sweep is NOT needed.

Opens a COPY of a built part under the temp dir and closes only that copy, so
the build artefact is never dirtied.

RESULTS, 2026-07-28, 3DEXPERIENCE R2026x SP3.0 Makers seat
==========================================================

**Q1 PASSES — the DimXpert API surface is reachable and early-bindable.**
``ext.DimXpertManager(config, True)`` and ``.DimXpertPart`` both resolve, and
the recon's "no makepy pass over swdimxpert" blocker is REMOVED: the wrapper
generates from the installed typelib in ~0.1 s.  Three binding facts, each
found the hard way and each a prerequisite for any future PMI work:

* the DimXpert dispatch exposes NO type info (``GetTypeInfo`` -> "Invalid
  index"), so ``Dispatch()`` and ``CastTo()`` BOTH silently fall back to a
  late-bound ``CDispatch`` and every property PUT is then refused;
* constructing the generated class around the RAW ``_oleobj_``
  (``wrapper.IDimXpertPart(obj._oleobj_)``) is the only binding that works —
  passing the CDispatch nests a dispatch in a dispatch; and
* ``swDimXpertGtolType_e`` is recoverable from ``swdimxpert.tlb`` even though
  the offline doc bundle omits it.  ``CircularRunout = 12`` is CONFIRMED (the
  audit's synthesizer had rejected that value as fabricated; the typelib says
  otherwise).

**Q2 WEDGES THE SEAT — reproducible, twice.** ``InsertDatum`` on a part-space
planar face hangs SolidWorks: the window goes ``IsHungAppWindow``, the scratch
part is left open and dirty, COM never returns, and only a full
``_sw_lifecycle.force_recover()`` (kill + connector relaunch, ~2-5 min)
recovers the seat.  Reproduced with the ``FeatureSelectorOptions`` array passed
BOTH as a bare Python list and as an explicit ``VT_ARRAY | VT_I4`` VARIANT (the
typing trap ``com_variant.double_array`` documents), so the marshalling fix is
NOT the answer.

Q3/Q4/Q5 are therefore UNREACHED, not disproven.

**Untested deltas** — what would have to be tried before calling part-side PMI
dead: driving ``InsertGtol`` WITHOUT a preceding ``InsertDatum`` (a form control
like flatness/cylindricity needs no datum, so the wedge may be specific to the
datum path); a different ``FeatureSelectorOptions`` value (``_Default = -1``
rather than ``_Plane = 0``); a face selected via ``SelectByID2`` instead of
``IEntity::Select4``; ``AutoDimensionScheme`` as a positive control that the
schema accepts ANY authoring on this seat; a non-Makers licence tier; and the
VBA path the API example is written for.  A positive control matters most: no
form of DimXpert authoring has yet been shown to work here, so "InsertDatum is
broken" and "DimXpert authoring is unavailable on a Makers seat" are not yet
distinguishable.

**Consequence for the drawing-purity work: none.** The unit and drift hazards
the audit found are fully closed by moving values into ``*_spec.py`` /
``_fit_limits`` / ``_surface_finish`` and keeping the existing, working,
read-back-verified DRAWING-side annotation path.  PMI would be an additional
step, not a prerequisite.

.. warning::

   Running this probe COSTS THE SEAT at Q2 until the wedge is understood. Do
   not run it during a build.

    uv run python cad/scripts/diagnostics/probe_dimxpert_gtol.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import CAD_ROOT, _early_bound, _read_member  # noqa: E402
from _drawing_common import _gtol_frame_xml  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import (  # noqa: E402
    PyWin32Adapter,
    null_callout,
)

# The audit's poster child: draw_transgear_stub.py carries a cylindricity 0.01
# and a circular-runout 0.03 on the gear seat, both as frozen sheet strings.
SOURCE_PART = CAD_ROOT / "out" / "sldprt" / "transgear-stub.SLDPRT"

# swDimXpertFeatureSelectorOption_e (read from swdimxpert.tlb, see _gtol_type_map).
SELECTOR_PLANE = 0

# swDimXpertAnnotationType_e.swDimXpertDatum
ANNOTATION_DATUM = 150

# The two controls draw_transgear_stub.py types as literals today.
PROBE_CONTROLS = (
    ("cylindricity", "Cylindricity", "0.01", ()),
    ("circular_runout", "CircularRunout", "0.03", ("A",)),
)


def _swdimxpert_tlb() -> Path:
    """Locate the installed swdimxpert type library."""
    roots = sorted(
        Path(r"C:\Program Files\Dassault Systemes").glob(
            "SOLIDWORKS*/SOLIDWORKS/swdimxpert.tlb"
        )
    ) + sorted(
        Path(r"C:\Program Files\SOLIDWORKS Corp").glob(
            "SOLIDWORKS/swdimxpert.tlb"
        )
    )
    if not roots:
        raise FileNotFoundError("swdimxpert.tlb not found in any SOLIDWORKS install")
    return roots[-1]


def _gtol_type_map() -> dict[str, int]:
    """Read ``swDimXpertGtolType_e`` off the installed type library.

    The offline API bundle documents ``IDimXpertPart::InsertGtol`` as taking
    "swDimXpertGtolType_e" but ships no such enum file, and the published help
    prints no integers.  comtypes' typelib loader recovers every member and its
    value, so the mapping is SOURCED rather than guessed -- and a SolidWorks
    upgrade that renumbers it fails this probe instead of silently inserting the
    wrong characteristic.
    """
    import comtypes.client

    module = comtypes.client.GetModule(str(_swdimxpert_tlb()))
    prefix = "swDimXpertGtolType_"
    return {
        name[len(prefix) :]: int(getattr(module, name))
        for name in dir(module)
        if name.startswith(prefix) and not name.endswith("_e")
    }


# swdimxpert.tlb identity, read from the installed library (pythoncom
# LoadTypeLib -> GetLibAttr). Needed because the DimXpert dispatches arrive
# LATE-bound: pywin32 then refuses a property PUT it has no type info for
# ("Property '<unknown>.FeatureSelectorOptions' can not be set"). Generating the
# makepy wrapper for this one typelib makes the DimXpert objects early-bound and
# their properties settable -- the missing makepy pass the recon flagged.
_SWDIMXPERT_TLB_GUID = "{582D0D5B-FF58-42CD-8968-A8A001A52454}"
_SWDIMXPERT_TLB_MAJOR = 34
_SWDIMXPERT_TLB_MINOR = 0


def _ensure_swdimxpert_wrapper() -> object:
    """makepy-generate (and import) the swdimxpert wrapper, returning the module."""
    from win32com.client import gencache

    return gencache.EnsureModule(
        _SWDIMXPERT_TLB_GUID, 0, _SWDIMXPERT_TLB_MAJOR, _SWDIMXPERT_TLB_MINOR
    )


def _close_if_open(adapter: object, title: str) -> None:
    """Close a document by title if this SolidWorks session has it open."""
    app = adapter.swApp
    for document in app.GetDocuments() or ():
        if str(_read_member(document, "GetTitle")) == title:
            app.CloseDoc(title)
            _telemetry.info(f"closed stale scratch document {title!r}")


def _long_array(values: list[int]):
    """Wrap ints as a ``VT_ARRAY | VT_I4`` VARIANT.

    ``FeatureSelectorOptions`` is documented as "array of long values".  A bare
    Python list marshals as ``VT_ARRAY | VT_VARIANT``, which is the same trap
    ``com_variant.double_array`` / ``bool_array`` exist to avoid for other SW
    setters -- and here it does not merely fail: it WEDGED SolidWorks (window
    "Not Responding", seat unrecoverable without a force-restart) on the
    2026-07-28 run.  Type the array explicitly.
    """
    import pythoncom
    from win32com.client import VARIANT

    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I4, [int(v) for v in values])


def _report(label: str, ok: bool, detail: str = "") -> bool:
    """Log one probe outcome; returns ``ok`` so callers can branch on it."""
    emit = _telemetry.success if ok else _telemetry.warn
    emit(f"{label}: {ok}" + (f" -- {detail}" if detail else ""))
    return ok


def _faces_of_type(adapter: object, model: object, surface_kind: int) -> list:
    """Every face of the part whose surface identifies as ``surface_kind``.

    swSurfaceTypes_e: 4001 = PLANE, 4002 = CYLINDER.  Walked body-first because
    DimXpert selects FACES, and the repo's existing pick helpers all resolve
    entities inside a drawing VIEW, which does not exist in part space.
    """
    # GetBodies2 is IPartDoc, NOT IModelDoc2 — a part dispatch answers both, but
    # `early_bound` is strict and refuses off-interface members by design.
    part = _early_bound(model, "IPartDoc")
    bodies = part.GetBodies2(0, False)  # swBodyType_e.swAllBodies, no visible-only
    faces = []
    for body in bodies or ():
        face = _read_member(body, "GetFirstFace")
        while face:
            surface = _read_member(face, "GetSurface")
            if surface is not None and int(_read_member(surface, "Identity")) == surface_kind:
                faces.append(face)
            face = _read_member(face, "GetNextFace")
    return faces


async def main() -> int:
    _telemetry.set_service("diagnostics")
    async with _telemetry.aspan("probe.dimxpert_gtol"):
        return await _probe()


async def _probe() -> int:
    gtol_types = _gtol_type_map()
    _telemetry.info(
        f"swDimXpertGtolType_e recovered from {_swdimxpert_tlb().name}: "
        + ", ".join(f"{k}={v}" for k, v in sorted(gtol_types.items(), key=lambda kv: kv[1]))
    )
    for _characteristic, member, _tolerance, _datums in PROBE_CONTROLS:
        if member not in gtol_types:
            raise RuntimeError(
                f"swDimXpertGtolType_e has no member {member!r} on this seat: "
                f"{sorted(gtol_types)}"
            )

    if not SOURCE_PART.is_file():
        raise FileNotFoundError(
            f"build a part first -- {SOURCE_PART} is missing "
            "(uv run python -m doit part:transgear_stub)"
        )
    scratch = Path(tempfile.gettempdir()) / "probe_dimxpert_gtol.SLDPRT"

    adapter = PyWin32Adapter({})
    try:
        await adapter.connect()
        # A previous run that raised mid-probe left the scratch part OPEN, and
        # SolidWorks holds a write lock on an open document -- the copy below
        # then dies with WinError 32. Close it first so the probe is rerunnable
        # without hand-clearing the session.
        _close_if_open(adapter, scratch.name)
        shutil.copy2(SOURCE_PART, scratch)
        opened = await adapter.open_model(str(scratch))
        if not opened.is_success:
            raise RuntimeError(f"open failed: {opened.error}")
        model = adapter.currentModel
        ext = _read_member(model, "Extension")
        config = _read_member(_read_member(model, "GetActiveConfiguration"), "Name")

        # --- Q1: does the swdimxpert typelib reach us through late binding? ---
        manager = ext.DimXpertManager(str(config), True)
        if not _report("Q1 DimXpertManager", manager is not None):
            return 1
        dim_part = _read_member(manager, "DimXpertPart")
        if not _report(
            "Q1 DimXpertPart (late-bound, no makepy pass)", dim_part is not None
        ):
            return 1
        # swdimxpert.tlb is NOT in the vendored makepy wrapper, so this dispatch
        # is late-bound and pywin32 resolves every unknown name as a PROPERTY --
        # `GetDimOption()` then invokes the default dispatch and dies with
        # "Member not found". Flag the zero-argument methods explicitly; this is
        # exactly the fallback path sw_type_info documents for interfaces the
        # wrapper cannot reach.
        wrapper = _ensure_swdimxpert_wrapper()
        _report(
            "Q1 swdimxpert makepy wrapper generated",
            wrapper is not None,
            getattr(wrapper, "__name__", ""),
        )
        # The DimXpert dispatch exposes NO type info (GetTypeInfo -> "Invalid
        # index"), so neither Dispatch() nor CastTo() can auto-resolve it -- both
        # fall back to a late-bound CDispatch, and pywin32 then refuses any
        # property PUT. Constructing the generated wrapper class AROUND the raw
        # dispatch is the one path that works: the type info comes from the
        # typelib we just makepy'd, not from the object.
        # Wrap the RAW IDispatch: the generated class calls InvokeTypes on
        # self._oleobj_, and handing it a CDispatch nests one dispatch inside
        # another (AttributeError: DimXpertPart.InvokeTypes).
        dim_part = wrapper.IDimXpertPart(getattr(dim_part, "_oleobj_", dim_part))
        _report(
            "Q1 IDimXpertPart wrapped early-bound",
            type(dim_part).__name__ == "IDimXpertPart",
            type(dim_part).__name__,
        )
        _telemetry.info(
            f"schema name={_read_member(manager, 'SchemaName')!r} "
            f"features={dim_part.GetFeatureCount()} "
            f"annotations={dim_part.GetAnnotationCount()}"
        )

        # --- Q2: InsertDatum on a face selected in PART space ---
        planes = _faces_of_type(adapter, model, 4001)
        cylinders = _faces_of_type(adapter, model, 4002)
        _telemetry.info(f"part faces: {len(planes)} planar, {len(cylinders)} cylindrical")
        if not planes or not cylinders:
            raise RuntimeError("probe part lacks the planar/cylindrical faces it needs")

        model.ClearSelection2(True)
        datum_ok = False
        # Select4 is IEntity, not IFace2, and its ISelectData argument must be a
        # real null VARIANT -- `None` marshals as a type mismatch.
        if _early_bound(planes[0], "IEntity").Select4(False, null_callout()):
            raw_option = dim_part.GetDimOption()
            option = wrapper.IDimXpertDimensionOption(
                getattr(raw_option, "_oleobj_", raw_option)
            )
            option.FeatureSelectorOptions = _long_array([SELECTOR_PLANE])
            datum_ok = bool(dim_part.InsertDatum(option))
        _report("Q2 InsertDatum on a part-space planar face", datum_ok)
        if datum_ok:
            for annotation in dim_part.GetAnnotations() or ():
                if int(_read_member(annotation, "Type")) == ANNOTATION_DATUM:
                    _telemetry.info(
                        f"  datum annotation: name={_read_member(annotation, 'Name')!r}"
                    )

        # --- Q3/Q4: InsertGtol, then try to FILL the empty frame ---
        for characteristic, member, tolerance, datums in PROBE_CONTROLS:
            model.ClearSelection2(True)
            if not _early_bound(cylinders[0], "IEntity").Select4(
                False, null_callout()
            ):
                _report(f"Q3 select cylinder for {characteristic}", False)
                continue
            annotation = dim_part.InsertGtol(gtol_types[member])
            if not _report(
                f"Q3 InsertGtol({member}={gtol_types[member]})", annotation is not None
            ):
                continue
            gtol = _read_member(annotation, "GetDisplayEntity")
            if gtol is None:
                _report(f"Q4 reach IGtol behind {characteristic}", False)
                continue
            fmt = _read_member(gtol, "GetFormat")
            _telemetry.info(
                f"  {characteristic}: GetFormat()={fmt} "
                "(2 = swGtolFormatType_e.GTOL_SW2022, the only format "
                "_drawing_common accepts)"
            )
            frame_count = int(_read_member(gtol, "GetFrameCount") or 0)
            _telemetry.info(f"  {characteristic}: GetFrameCount()={frame_count}")

            # Path A -- the current-format XML payload the drawings already use.
            xml = _gtol_frame_xml(characteristic, tolerance, datums=datums)
            frame = gtol.GetFrame(1) if frame_count else None
            xml_ok = False
            if frame is not None:
                xml_ok = bool(frame.SetSymbolXml(xml))
                applied = str(frame.GetSymbolXml() or "")
                xml_ok = xml_ok and tolerance in applied
                _report(
                    f"Q4a SetSymbolXml on a DimXpert-created Gtol ({characteristic})",
                    xml_ok,
                    f"read back {applied[:120]!r}",
                )
            else:
                _report(
                    f"Q4a GetFrame(1) on a DimXpert-created Gtol ({characteristic})",
                    False,
                    "no current-format frame to write XML into",
                )

            # Path B -- the recipe InsertGtol's own Remarks prescribe.
            if not xml_ok:
                seeded = bool(
                    gtol.SetFrameValues2(1, tolerance, "", *[*datums[:3], "", "", ""][:3])
                )
                _report(
                    f"Q4b SetFrameValues2 (pre-2022 path) ({characteristic})", seeded
                )

            # Whatever path took, does the VALUE read back through DimXpert?
            tolerance_obj = _read_member(annotation, "GetAppliedAnnotations")
            _telemetry.info(
                f"  {characteristic}: DimXpert applied-annotation count="
                f"{_read_member(annotation, 'GetAppliedAnnotationCount')} "
                f"applied={tolerance_obj is not None}"
            )

        _telemetry.info(
            f"final DimXpert annotation count: {dim_part.GetAnnotationCount()}"
        )

        # --- Q5: does part PMI reach a sheet? ---
        saved = await adapter.save_file(str(scratch))
        _report("Q5 save part carrying DimXpert annotations", saved.is_success)
        _telemetry.warn(
            "Q5 drawing-side import is NOT exercised here: it needs a drawing "
            "document and a view of this part. Run it from a draw_* recipe with "
            "IDrawingDoc::InsertModelAnnotations3(..., swInsertAnnotation_DimXpert) "
            "once Q3/Q4 pass -- there is no point automating the import of "
            "annotations that cannot be authored."
        )

        title = _read_member(model, "GetTitle")
        adapter.swApp.QuitDoc(title)
        _telemetry.success(f"scratch part closed: {title}")
        return 0
    finally:
        await adapter.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
