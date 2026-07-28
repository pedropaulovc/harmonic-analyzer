"""Staged DimXpert authoring probe — one stage per process, safe -> wedge-risky.

Follow-up to ``probe_dimxpert_gtol.py``, whose 2026-07-28 run WEDGED the seat at
``IDimXpertPart.InsertDatum`` (twice) and therefore never reached Q3-Q5.  The
API-doc bundle has since been refreshed (v3.11.0) and now ships the official
``swdimxpertapi`` examples, which expose one delta from the wedged run and give
the positive control its docstring asked for:

* **Every official ``Get and Set Datum`` variant sets
  ``IDimXpertDimensionOption.DatumLength = 0.06`` BEFORE ``InsertDatum``** —
  the wedged probe never touched it.  ``DatumLength`` is "leader length of the
  datum in meters"; an uninitialized length is the prime wedge suspect.
* **``Auto Dimension Scheme`` is a complete positive-control recipe**:
  ``GetAutoDimSchemeOption()`` -> ``AutoDimensionScheme(option)`` ->
  ``GetFeatureCount``/``GetFeatures`` read-back -> ``DeleteAllTolerances()``.
  If ANY DimXpert authoring works on this Makers seat, this is it — and until
  it passes, "InsertDatum is broken" and "DimXpert authoring is unavailable on
  this licence tier" are indistinguishable.

Stages (run each as its OWN process, in this order; stop at the first wedge):

    uv run python cad/scripts/diagnostics/probe_dimxpert_authoring.py read
        Read-only sanity: early-bound wrap, counts, option DEFAULTS —
        including the factory value of ``DatumLength``, evidence for the
        uninitialized-length hypothesis.  Zero authoring, zero risk.
    uv run python cad/scripts/diagnostics/probe_dimxpert_authoring.py auto
        POSITIVE CONTROL: AutoDimensionScheme with default options, feature/
        annotation read-back, then DeleteAllTolerances.  First authoring call.
    uv run python cad/scripts/diagnostics/probe_dimxpert_authoring.py datum
        The wedge repro WITH the doc-derived delta applied (DatumLength set
        exactly as the official example does).  WEDGE-RISKY: run last, with a
        driver-side timeout, and keep ``_sw_lifecycle.force_recover()`` handy.
    uv run python cad/scripts/diagnostics/probe_dimxpert_authoring.py datum-nolength
        Control for root-cause attribution: the ORIGINAL wedge form (no
        DatumLength).  Only worth running if ``datum`` PASSES — a pass/wedge
        pair pins the cause to the one missing property.  WEDGE-RISKY.
    uv run python cad/scripts/diagnostics/probe_dimxpert_authoring.py gtol
        ``InsertGtol`` (cylindricity — a form control, needs NO datum) with no
        preceding InsertDatum: the "is the wedge datum-specific?" delta from
        the gtol probe's untested list.  WEDGE-RISKY.
    uv run python cad/scripts/diagnostics/probe_dimxpert_authoring.py import
        THE SHEET LEG (the gtol probe's unreached Q5 second half): author a
        datum + an XML-filled gtol on the part, save it, place a view of it on
        a scratch drawing and pull the PMI in with ``IView::ImportAnnotations
        (IncludeDimXpertAnnotations=True)`` — the per-view import API (there
        is NO swInsertAnnotation_e member for DimXpert; InsertModelAnnotations3
        cannot reach PMI).  Imports into a *Front AND a *Right view (an
        annotation lands only in a view its annotation plane faces: observed
        2026-07-28, the plane-face datum landed in *Front — before=0 after=1 —
        while the cylinder-face gtol did not).  The stage passes only if the
        datum landed somewhere AND at least one imported gtol frame reads back
        the 0.01 value; the *Right leg is authored from that routing model and
        is still unproven live.  Nothing is saved.

RESULTS, 2026-07-28 (fresh SolidWorks session), R2026x SP3.0 Makers seat
========================================================================

Every stage PASSES; the wedge did not reproduce in ANY form:

* ``read`` — option defaults: ``DatumLength = 0.05`` (sane, weakening the
  uninitialized-length hypothesis), ``TextPosition`` = denormal garbage
  (uninitialized memory; different garbage each run; harmless — neither the
  official examples nor these probes set it), ``FeatureFilters = 65535``.
* ``auto`` — POSITIVE CONTROL PASSES: 3 features + 3 annotations authored
  (``AutoDimensionScheme`` returns ``False`` = partial scheme, a soft signal).
  DimXpert authoring is not licence-gated on a Makers seat.
* ``datum`` AND ``datum-nolength`` — ``InsertDatum`` returns ``True`` in
  ~0.5 s either way, ``Datum19@Plane1(A)`` created.  The DatumLength delta is
  therefore NOT the wedge cause: the wedge was that session's SolidWorks
  state, not the call shape.  A recurrence is a session-health event —
  ``_sw_lifecycle.force_recover()`` — not a reason to change the call.
* ``gtol`` — ``InsertGtol(Cylindricity)`` with NO preceding datum returns an
  annotation: the form-control path needs no datum, as documented.

Every stage opens a COPY of a built part under the temp dir, never saves, and
closes only that copy.  All DimXpert dispatches are EARLY-BOUND via the makepy
wrapper generated from ``swdimxpert.tlb``, constructed around the raw
``_oleobj_`` — the ONLY binding under which property puts work (the dispatches
expose no type info, so ``Dispatch``/``CastTo`` silently fall back to late
binding; see probe_dimxpert_gtol.py Q1 notes).

.. warning::

   The ``datum*`` / ``gtol`` stages COST THE SEAT if the wedge reproduces.  Do
   not run them during a build.  Recover with::

       uv run python -c "import sys; sys.path.insert(0, 'cad/scripts'); \
           import _sw_lifecycle; print(_sw_lifecycle.force_recover())"
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
import _watchdog  # noqa: E402
from _common import CAD_ROOT, _early_bound, _read_member  # noqa: E402
from probe_dimxpert_gtol import (  # noqa: E402
    _FAILED_CHECKS,
    SELECTOR_PLANE,
    _close_if_open,
    _gtol_type_map,
    _long_array,
    _report,
)


def _failed_checks() -> list[str]:
    """Failures accumulated by the shared ``_report`` (lives in the gtol
    probe's module); nonempty means some required check warned through."""
    if _FAILED_CHECKS:
        _telemetry.error(
            f"probe finished with {len(_FAILED_CHECKS)} failed check(s): "
            + "; ".join(_FAILED_CHECKS)
        )
    return _FAILED_CHECKS
from solidworks_mcp.adapters.pywin32_adapter import (  # noqa: E402
    PyWin32Adapter,
    null_callout,
)

SOURCE_PART = CAD_ROOT / "out" / "sldprt" / "transgear-stub.SLDPRT"

# The official Get_and_Set_Datum examples (C#/VB.NET/VBA — all three) set this
# before InsertDatum; the wedged probe_dimxpert_gtol run did not.  Meters.
EXAMPLE_DATUM_LENGTH = 0.06

STAGES = ("read", "auto", "datum", "datum-nolength", "gtol", "import")


def _faces_of_type(model: object, surface_kind: int) -> list:
    """Faces whose surface identifies as ``surface_kind`` (4001 plane, 4002 cyl)."""
    part = _early_bound(model, "IPartDoc")
    faces = []
    for body in part.GetBodies2(0, False) or ():
        face = _read_member(body, "GetFirstFace")
        while face:
            surface = _read_member(face, "GetSurface")
            if surface is not None and int(_read_member(surface, "Identity")) == surface_kind:
                faces.append(face)
            face = _read_member(face, "GetNextFace")
    return faces


async def _open_scratch(adapter: PyWin32Adapter, stage: str) -> tuple[object, object]:
    """Copy the source part to a scratch path, open it, return (model, dim_part)."""
    scratch = Path(tempfile.gettempdir()) / f"probe_dimxpert_authoring_{stage}.SLDPRT"
    _close_if_open(adapter, scratch.name)
    shutil.copy2(SOURCE_PART, scratch)
    opened = await adapter.open_model(str(scratch))
    if not opened.is_success:
        raise RuntimeError(f"open failed: {opened.error}")
    model = adapter.currentModel
    ext = _read_member(model, "Extension")
    config = _read_member(_read_member(model, "GetActiveConfiguration"), "Name")
    manager = ext.DimXpertManager(str(config), True)
    if manager is None:
        raise RuntimeError("DimXpertManager returned None")
    dim_part = _early_bound(_read_member(manager, "DimXpertPart"), "IDimXpertPart")
    _report(
        "early-bound IDimXpertPart (sw_type_info aux typelib)",
        type(dim_part).__name__.startswith("IDimXpertPart"),
        type(dim_part).__name__,
    )
    return model, dim_part


def _counts(dim_part: object, when: str) -> tuple[int, int]:
    features = int(dim_part.GetFeatureCount())
    annotations = int(dim_part.GetAnnotationCount())
    _telemetry.info(f"{when}: features={features} annotations={annotations}")
    return features, annotations


def _stage_read(model: object, dim_part: object) -> bool:
    """Read-only: counts + option defaults.  The DatumLength factory value is
    the evidence the datum stages interpret."""
    _counts(dim_part, "initial")

    scheme_option = _early_bound(
        dim_part.GetAutoDimSchemeOption(), "IDimXpertAutoDimSchemeOption"
    )
    for name in (
        "ScopeAllFeature",
        "FeatureFilters",
        "PartType",
        "PatternType",
        "PolarPatternHoleCount",
        "ToleranceType",
    ):
        _telemetry.info(f"AutoDimSchemeOption.{name} = {getattr(scheme_option, name)!r}")

    dim_option = _early_bound(dim_part.GetDimOption(), "IDimXpertDimensionOption")
    for name in ("DatumLength", "TextPosition", "DimensionPositionOption"):
        try:
            _telemetry.info(f"DimensionOption.{name} = {getattr(dim_option, name)!r}")
        except Exception as exc:  # noqa: BLE001 — a default that cannot be read is itself a finding
            _telemetry.warn(f"DimensionOption.{name} unreadable: {exc}")
    return True


def _stage_auto(model: object, dim_part: object) -> bool:
    """POSITIVE CONTROL — the official Auto Dimension Scheme recipe, verbatim."""
    _counts(dim_part, "before AutoDimensionScheme")
    scheme_option = _early_bound(
        dim_part.GetAutoDimSchemeOption(), "IDimXpertAutoDimSchemeOption"
    )
    ok = bool(dim_part.AutoDimensionScheme(scheme_option))
    features, annotations = _counts(dim_part, "after AutoDimensionScheme")
    # The return value is a SOFT signal: on this part it returns False yet
    # creates 3 features + 3 annotations (a partial scheme — some geometry
    # could not be toleranced). The control's question is "does ANY DimXpert
    # authoring work on this seat?", so created evidence decides it.
    authored = features > 0 or annotations > 0
    _report(
        "positive control: DimXpert authoring works on this seat",
        authored,
        f"retval={ok} features={features} annotations={annotations}",
    )
    for feature in (dim_part.GetFeatures() or ())[:10]:
        _telemetry.info(
            f"  feature: name={_read_member(feature, 'Name')!r} "
            f"type={_read_member(feature, 'Type')!r}"
        )
    cleared = bool(dim_part.DeleteAllTolerances())
    _report("DeleteAllTolerances", cleared)
    _counts(dim_part, "after DeleteAllTolerances")
    return authored


def _stage_datum(model: object, dim_part: object, *, set_length: bool) -> bool:
    """The wedge repro, with (``datum``) or without (``datum-nolength``) the
    doc-derived DatumLength delta."""
    planes = _faces_of_type(model, 4001)
    if not planes:
        raise RuntimeError("probe part has no planar face")
    model.ClearSelection2(True)
    if not _early_bound(planes[0], "IEntity").Select4(False, null_callout()):
        raise RuntimeError("face selection failed")

    option = _early_bound(dim_part.GetDimOption(), "IDimXpertDimensionOption")
    if set_length:
        option.DatumLength = EXAMPLE_DATUM_LENGTH
        _telemetry.info(
            f"DatumLength set to {EXAMPLE_DATUM_LENGTH} (official example value); "
            f"read-back {option.DatumLength!r}"
        )
    else:
        _telemetry.warn(
            "DatumLength deliberately NOT set — reproducing the original wedge form"
        )
    option.FeatureSelectorOptions = _long_array([SELECTOR_PLANE])

    _telemetry.info("calling InsertDatum — the call that wedged on 2026-07-28 …")
    ok = bool(dim_part.InsertDatum(option))
    _report("InsertDatum returned (no wedge)", True, f"result={ok}")
    features, annotations = _counts(dim_part, "after InsertDatum")
    for annotation in (dim_part.GetAnnotations() or ()):
        _telemetry.info(
            f"  annotation: name={_read_member(annotation, 'Name')!r} "
            f"type={_read_member(annotation, 'Type')!r}"
        )
    return ok and annotations > 0


async def _stage_import(adapter: PyWin32Adapter, model: object, dim_part: object) -> bool:
    """Author datum + filled gtol, save the scratch part, import onto a sheet."""
    from _drawing_common import _gtol_frame_xml

    planes = _faces_of_type(model, 4001)
    cylinders = _faces_of_type(model, 4002)

    model.ClearSelection2(True)
    if not _early_bound(planes[0], "IEntity").Select4(False, null_callout()):
        raise RuntimeError("plane selection failed")
    option = _early_bound(dim_part.GetDimOption(), "IDimXpertDimensionOption")
    option.DatumLength = EXAMPLE_DATUM_LENGTH
    option.FeatureSelectorOptions = _long_array([SELECTOR_PLANE])
    _report("import: InsertDatum", bool(dim_part.InsertDatum(option)))

    model.ClearSelection2(True)
    if not _early_bound(cylinders[0], "IEntity").Select4(False, null_callout()):
        raise RuntimeError("cylinder selection failed")
    annotation = dim_part.InsertGtol(_gtol_type_map()["Cylindricity"])
    if annotation is None:
        raise RuntimeError("InsertGtol returned None")
    display = _early_bound(_read_member(annotation, "GetDisplayEntity"), "IAnnotation")
    gtol = _early_bound(display.GetSpecificAnnotation(), "IGtol")
    frame = _early_bound(gtol.GetFrame(1), "IGtolFrame")
    filled = bool(frame.SetSymbolXml(_gtol_frame_xml("cylindricity", "0.01", datums=())))
    _report("import: gtol XML-filled on the part", filled)
    if not filled:
        raise RuntimeError("gtol XML fill failed -- nothing meaningful to import")

    scratch = Path(str(_read_member(model, "GetPathName")))
    saved = await adapter.save_file(str(scratch))
    if not saved.is_success:
        raise RuntimeError(f"save failed: {saved.error}")
    adapter.swApp.QuitDoc(str(_read_member(model, "GetTitle")))

    from solidworks_mcp.adapters.solidworks.drawing import new_drawing, place_view

    new_drawing(adapter)
    # A DimXpert annotation imports only into a view its annotation plane
    # faces, so one view cannot prove the whole path: the plane-face datum
    # lands in *Front while the cylinder-face gtol does not. Import into both
    # a Front and a Right view and demand (a) the datum landed somewhere and
    # (b) at least one imported gtol whose frame reads back the 0.01 value --
    # zero validated gtols means the XML-filled frame did NOT survive the
    # part-to-drawing path, which must fail this stage, not pass vacuously.
    datum_landed = False
    validated_gtols = 0
    frames_ok = True
    for orientation, center_x in (("*Front", 0.13), ("*Right", 0.30)):
        view = place_view(
            adapter, str(scratch), orientation, center_x, 0.14, scale=(1.0, 1.0)
        )
        view = _early_bound(view, "IView")
        before = len(tuple(view.GetAnnotations() or ()))
        view.ImportAnnotations(False, False, True, False, False)
        imported = tuple(view.GetAnnotations() or ())
        for item in imported:
            item = _early_bound(item, "IAnnotation")
            _telemetry.info(
                f"  {orientation} annotation: name={item.GetName()!r} "
                f"type={item.GetType()}"
            )
        landed = len(imported) > before
        _report(
            f"import: ImportAnnotations(DimXpert=True) landed PMI in {orientation}",
            landed,
            f"before={before} after={len(imported)}",
        )
        datum_landed = datum_landed or any(
            int(_early_bound(item, "IAnnotation").GetType()) == 2  # swDatumTag
            for item in imported
        )
        for item in imported:
            item = _early_bound(item, "IAnnotation")
            if int(item.GetType()) != 5:  # swAnnotationType_e.swGTol
                continue
            sheet_gtol = _early_bound(item.GetSpecificAnnotation(), "IGtol")
            xml = str(
                _early_bound(sheet_gtol.GetFrame(1), "IGtolFrame").GetSymbolXml()
            )
            frame_ok = "0.01" in xml
            frames_ok = frames_ok and frame_ok
            validated_gtols += frame_ok
            _report(
                f"import: {orientation} gtol frame carries the 0.01 tolerance",
                frame_ok,
                xml[:120],
            )
    _report(
        "import: the datum survived to a sheet view",
        datum_landed,
    )
    _report(
        "import: at least one XML-filled gtol survived to a sheet view",
        validated_gtols >= 1,
        f"validated_gtols={validated_gtols}",
    )
    ok = datum_landed and frames_ok and validated_gtols >= 1
    draw_title = str(_read_member(adapter.currentModel, "GetTitle"))
    adapter.swApp.QuitDoc(draw_title)
    _telemetry.success(f"scratch drawing discarded without saving: {draw_title}")
    return ok


def _stage_gtol(model: object, dim_part: object) -> bool:
    """InsertGtol with NO preceding datum — is the wedge datum-specific?"""
    gtol_types = _gtol_type_map()
    cylinders = _faces_of_type(model, 4002)
    if not cylinders:
        raise RuntimeError("probe part has no cylindrical face")
    model.ClearSelection2(True)
    if not _early_bound(cylinders[0], "IEntity").Select4(False, null_callout()):
        raise RuntimeError("face selection failed")
    _telemetry.info("calling InsertGtol(Cylindricity) with no preceding datum …")
    annotation = dim_part.InsertGtol(gtol_types["Cylindricity"])
    _report("InsertGtol returned (no wedge)", True, f"annotation={annotation is not None}")
    _counts(dim_part, "after InsertGtol")
    return annotation is not None


async def main() -> int:
    _telemetry.set_service("diagnostics")
    if len(sys.argv) != 2 or sys.argv[1] not in STAGES:
        _telemetry.error(
            f"usage: {Path(sys.argv[0]).name} {{{'|'.join(STAGES)}}}"
        )
        return 2
    stage = sys.argv[1]

    if not SOURCE_PART.is_file():
        raise FileNotFoundError(
            f"build a part first -- {SOURCE_PART} is missing "
            "(uv run python -m doit part:transgear_stub)"
        )

    async with _telemetry.aspan(f"probe.dimxpert_authoring.{stage}"):
        adapter = PyWin32Adapter({})
        # The wedge this probe exists to study blocks the COM call itself, so
        # without the watchdog neither the finally block nor a timeout could
        # ever run -- arm the same crash/idle guard run_build uses.
        _watchdog.start()
        try:
            await adapter.connect()
            model, dim_part = await _open_scratch(adapter, stage)
            if stage == "import":
                # closes its own documents (the part is saved + reopened in a view)
                passed = bool(await _stage_import(adapter, model, dim_part))
                _report(f"stage {stage}", passed)
                return 0 if passed and not _failed_checks() else 1
            runner = {
                "read": lambda: _stage_read(model, dim_part),
                "auto": lambda: _stage_auto(model, dim_part),
                "datum": lambda: _stage_datum(model, dim_part, set_length=True),
                "datum-nolength": lambda: _stage_datum(model, dim_part, set_length=False),
                "gtol": lambda: _stage_gtol(model, dim_part),
            }[stage]
            passed = bool(runner())
            _report(f"stage {stage}", passed)
            title = _read_member(model, "GetTitle")
            adapter.swApp.QuitDoc(title)
            _telemetry.success(f"scratch part closed without saving: {title}")
            return 0 if passed and not _failed_checks() else 1
        finally:
            await adapter.disconnect()
            _watchdog.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
