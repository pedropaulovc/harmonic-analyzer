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

RESULTS, 2026-07-28 (second session, fresh SolidWorks), R2026x SP3.0 Makers
===========================================================================

**ALL FIVE QUESTIONS NOW PASS (Q5 = save; drawing-side import still open).**
The morning session's InsertDatum wedge DID NOT REPRODUCE against a freshly
launched SolidWorks — not even in its exact original form (no ``DatumLength``,
same part, same selector, same VARIANT array; see
``probe_dimxpert_authoring.py datum-nolength``).  The wedge was a property of
that session's SolidWorks state, not of the call.  Full verdict trail:

* **Positive control** (``probe_dimxpert_authoring.py auto``):
  ``AutoDimensionScheme`` with default options authors 3 features +
  3 annotations on this Makers seat (retval ``False`` = partial scheme — a
  soft signal, not a failure).  DimXpert authoring is NOT licence-gated.
* **Q2** ``InsertDatum`` returns ``True`` in ~0.5 s, ``Datum19@Plane1(A)``
  created — with or without the official example's ``DatumLength = 0.06``.
* **Q3** ``InsertGtol`` creates cylindricity and circular-runout annotations
  (also with NO preceding datum — the form-control path works).
* **Q4** The 2026-07-28-morning "GetFrameCount()=0 / GetFormat()=None" reads
  were a PROBE BUG: ``IDimXpertAnnotation.GetDisplayEntity`` returns the
  display-side ``IAnnotation``, and the ``IGtol`` is one hop further via
  ``IAnnotation::GetSpecificAnnotation`` (None would mean PMI-only).  Behind
  that hop the Gtol is ALREADY current-format (``GetFormat()=2``,
  ``GetFrameCount()=1``) and ``IGtolFrame.SetSymbolXml`` applies the same XML
  payload the drawings use, read-back verified (``GTOL-CYL``/0.01,
  ``GTOL-SRUN``/0.03).  No old-format migration needed.
* **Q5** The part saves carrying the DimXpert annotations.  (The DimXpert
  ``GetAppliedAnnotationCount`` stays 0 for XML-filled gtols — the fill lives
  on the display annotation, not in DimXpert's feature-association model.)

Binding facts (unchanged, now CODIFIED in ``sw_type_info``): the DimXpert
dispatches expose NO type info, so ``Dispatch()``/``CastTo()`` silently fall
back late-bound and property PUTs are refused; the ONLY working binding is the
makepy class generated from ``swdimxpert.tlb`` constructed around the RAW
``_oleobj_``.  ``sw_type_info.early_bound`` now serves DimXpert interfaces
through its auxiliary-typelib registry (lazy ``EnsureModule``, version read
off the installed tlb), so ``_early_bound(obj, "IDimXpertPart")`` is all a
call site needs.  ``swDimXpertGtolType_e`` is still absent from the offline
doc bundle (v3.11.0) and still read off the tlb here (``CircularRunout = 12``
confirmed).

**Still untested:** ``IDrawingDoc::InsertModelAnnotations3`` with the DimXpert
filter (does part PMI actually land on a sheet?), and whether the morning
wedge recurs in long/degraded sessions — treat a recurrence as a session-state
problem (recover via ``_sw_lifecycle.force_recover``), not a call-shape one.

**Consequence for the drawing-purity work: unchanged.** The unit and drift
hazards close entirely with the spec relocation; PMI is now PROVEN authorable
but remains an additional step (blocked only on the sheet-import question),
not a prerequisite.

.. warning::

   The 2026-07-28-morning session wedged at Q2 twice (unreproducible since —
   see RESULTS).  Still: do not run this probe during a build, and if it
   hangs, recover with ``_sw_lifecycle.force_recover()``.

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
from _drawing_common import _GTOL_SYMBOLS, _gtol_frame_xml  # noqa: E402
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
        # The DimXpert dispatch exposes NO type info (GetTypeInfo -> "Invalid
        # index"), so neither Dispatch() nor CastTo() can auto-resolve it -- both
        # fall back to a late-bound CDispatch, and pywin32 then refuses any
        # property PUT. sw_type_info's auxiliary-typelib support (added off this
        # probe's findings) makepy-generates swdimxpert.tlb on first use and
        # constructs the generated class around the RAW _oleobj_ -- the one
        # binding that works -- so the ordinary `_early_bound` call now serves
        # DimXpert interfaces too.
        dim_part = _early_bound(dim_part, "IDimXpertPart")
        _report(
            "Q1 IDimXpertPart early-bound via aux typelib",
            type(dim_part).__name__.startswith("IDimXpertPart"),
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
            option = _early_bound(dim_part.GetDimOption(), "IDimXpertDimensionOption")
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
            # GetDisplayEntity returns the display-side IAnnotation, NOT the
            # IGtol (the C# Get_and_Set_Datum example casts it to Annotation and
            # reads GetName). The IGtol is one hop further, via
            # IAnnotation::GetSpecificAnnotation — which returns None for a
            # PMI-only annotation, itself a reportable outcome. The 2026-07-28
            # run treated the display entity AS the IGtol, so its
            # GetFrameCount()=0 / GetFormat()=None reads were against the wrong
            # interface and prove nothing.
            display = _read_member(annotation, "GetDisplayEntity")
            if display is None:
                _report(f"Q4 reach display IAnnotation behind {characteristic}", False)
                continue
            display = _early_bound(display, "IAnnotation")
            _telemetry.info(
                f"  {characteristic}: display annotation name="
                f"{display.GetName()!r} type={display.GetType()}"
            )
            gtol = display.GetSpecificAnnotation()
            if gtol is None:
                _report(
                    f"Q4 GetSpecificAnnotation behind {characteristic}",
                    False,
                    "None — PMI-only annotation (see IAnnotation::GetSpecificAnnotation Remarks)",
                )
                continue
            gtol = _early_bound(gtol, "IGtol")
            fmt = _read_member(gtol, "GetFormat")
            _telemetry.info(
                f"  {characteristic}: GetFormat()={fmt} "
                "(2 = swGtolFormatType_e.GTOL_SW2022, the only format "
                "_drawing_common accepts)"
            )
            # Mirror the PROVEN drawing-side recipe (_drawing_common.
            # add_feature_control_frame): count -> AddFrame if none ->
            # GetFrame(1); a None frame means an OLD-format Gtol, seeded via
            # SetFrameSymbols2/SetFrameValues2 then ConvertFormat; finally the
            # current-format IGtolFrame takes the XML payload.
            frame_count = int(_read_member(gtol, "GetFrameCount") or 0)
            if frame_count == 0 and bool(gtol.AddFrame()):
                frame_count = int(_read_member(gtol, "GetFrameCount") or 0)
            _telemetry.info(f"  {characteristic}: GetFrameCount()={frame_count}")
            frame = gtol.GetFrame(1) if frame_count else None
            migrated = frame is None
            if migrated:
                datum_values = [*datums[:3], "", "", ""][:3]
                gtol.SetFrameSymbols2(
                    1, f"<{_GTOL_SYMBOLS[characteristic]}>", "", "", False,
                    "", "", "", "",
                )
                seeded = bool(gtol.SetFrameValues2(1, tolerance, "", *datum_values))
                converted = seeded and gtol.CanConvertFormat() and int(gtol.ConvertFormat()) == 0
                _report(
                    f"Q4b old-format seed + ConvertFormat ({characteristic})",
                    bool(converted),
                    f"seeded={seeded}",
                )
                frame = gtol.GetFrame(1) if converted else None

            xml_ok = False
            if frame is not None:
                frame = _early_bound(frame, "IGtolFrame")
                if not migrated:
                    xml = _gtol_frame_xml(characteristic, tolerance, datums=datums)
                    frame.SetSymbolXml(xml)
                applied = str(frame.GetSymbolXml() or "")
                xml_ok = tolerance in applied
                _report(
                    f"Q4a current-format frame carries the tolerance ({characteristic})",
                    xml_ok,
                    f"migrated={migrated}, read back {applied[:120]!r}",
                )
            else:
                _report(
                    f"Q4 no usable IGtolFrame ({characteristic})",
                    False,
                    "GetFrame(1) is None on both the direct and migrated paths",
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
