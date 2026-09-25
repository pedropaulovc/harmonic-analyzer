r"""Pack-and-Go the native SolidWorks release tree -- the release's only COM work.

doit task: ``package:release``. Runnable standalone:

    uv run python cad\scripts\package_native.py [--out <dir>]

``cut_release.py`` publishes a release from a machine with NO SolidWorks seat, so
every SolidWorks document a release opens is opened HERE, on the COM seat (a farm
worker under ``--executor farm``). This script produces a PREPARED native tree
the publisher only has to COPY into its stage:

    <out>/solidworks/          the flat deduped native model set -- the top
                               assembly's Pack-and-Go, merged with every
                               drawing's Pack-and-Go (the drawing documents ride
                               along, as they do in the shipped bundle)
    <out>/slddrw/              each drawing document plus the models it references
    <out>/pdf/, <out>/png/     each drawing re-exported from its STAMPED portable
                               copy (the build's own prints say DEV)
    <out>/native-package.json  the COM-derived facts the publisher cannot obtain
                               off-seat: SolidWorks revision, the CAD revision it
                               stamped, referenced-document count, per-drawing
                               members, original sources and release prints

The release number is stamped HERE and only here.  Every build writes the
constant ``Revision``/``BUILD_ID`` ``DEV`` (``_common.BUILD_REVISION``), so a
``release.yaml`` bump re-keys this one leaf instead of every cached part,
assembly and drawing.  After Pack-and-Go, ``stamp_release`` opens every packaged
copy -- models first, then drawings, in both ``solidworks/`` and ``slddrw/`` --
writes ``Revision = vNN`` (models) and ``BUILD_ID = vNN`` (drawings), rebuilds
each drawing so its ``$PRPSHEET:"Revision"`` REV cell re-reads the stamped model,
saves it, and exports the release PDF from the portable copy.  Every document
SolidWorks resolves while a copy is open must be that tree's own copy; one
loaded from anywhere else (the ``cad/out`` original, a sibling source root)
fails the leaf, because a stamp written through a foreign reference would ship
unstamped.  The re-exported PDFs are then sanitized, rendered to PNG and
text-checked offline: every page must name ``vNN`` and none may say ``DEV``.

``<out>`` is wiped and recreated on every run, so a rerun can never inherit a
stale member, and the transient Pack-and-Go ``.zip`` archives are deleted again:
the prepared tree, not the zips, is the artefact.

EVERY path inside ``native-package.json`` is a POSIX path RELATIVE TO THE
REPOSITORY ROOT (``cad/out/release/native/solidworks/harmonic-analyzer.SLDASM``),
never absolute -- the file is written on a farm worker and read on the submitter,
whose checkout lives elsewhere. ``out_dir`` records the prepared tree's own
repo-relative directory, so the publisher turns any member path into the
stage-relative one with ``relative_to(out_dir)``.

The seat is left EMPTY on every exit path (``_release_seat``): a document still
resident here share-locks its ``cad/out`` file past this COM session, and the NEXT
task's remote-cache restore runs OUTSIDE the seat -- it would fail with
``PermissionError(13)`` (AGENTS.md, "the holder leaves the seat EMPTY").
And the seat's own WORKING DIRECTORY is parked outside every checkout: Pack-and-Go
opens documents from ``cad/out``, SolidWorks parks its process current directory
in the directory it last opened, and Windows refuses to remove a directory that
is any process's cwd -- which on a farm worker is how an unrelated leaf's source
root cleanup fails with ``WinError 32``.

Requires SolidWorks already open (3DEXPERIENCE Platform shortcut) and NOTHING
else driving it -- single STA COM server.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import _seat_forensics
from _common import BUILD_REVISION, CAD_ROOT, OUT_SLDASM, log
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS, DrawingLayout

import _config
import _telemetry

REPO_ROOT = CAD_ROOT.parent
TOP_ASSEMBLY = "harmonic-analyzer"
RELEASE_DIR = CAD_ROOT / "out" / "release"
# Default prepared-tree location; the whole directory is this task's cached output.
NATIVE_DIR = RELEASE_DIR / "native"
# Layout of the prepared tree. These names are ALSO the bundle's stage-relative
# directories, so the publisher copies them across without rewriting a path.
NATIVE_SUBDIR = "solidworks"
DRAWING_SUBDIR = "slddrw"
# The release prints, re-exported from the stamped portable drawings. Same
# names as the bundle's pdf/ and png/ directories.
PDF_SUBDIR = "pdf"
PNG_SUBDIR = "png"
SIDECAR_NAME = "native-package.json"
SIDECAR_SCHEMA = 2
DRAWING_OUTPUTS = {drawing.name: drawing.outputs for drawing in DRAWINGS}
# The model each drawing documents (its $PRPSHEET REV source), by filename.
DRAWING_SOURCES = {drawing.name: drawing.source.name for drawing in DRAWINGS}
# Every sheet orientation a drawing may use; release pages are matched to one.
DRAWING_LAYOUTS = {
    drawing.name: tuple(dict.fromkeys((drawing.layout, *drawing.additional_layouts)))
    for drawing in DRAWINGS
}

# Custom properties the release stamps. ``Revision`` is the model property the
# title block's REV cell links ($PRPSHEET); ``BUILD_ID`` is the drawing's own
# property behind its BUILD cell ($PRP).
REVISION_PROPERTY = "Revision"
BUILD_ID_PROPERTY = "BUILD_ID"

# SolidWorks COM type library (SldWorks); the version pins the same revision the
# pywin32 gen_py module exposes (...x0x34x0) so comtypes generates matching stubs.
SW_TYPELIB = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
SW_TYPELIB_VER = (34, 0)
SW_DOC_PART = 1  # swDocumentTypes_e.swDocPART
SW_DOC_ASSEMBLY = 2  # swDocumentTypes_e.swDocASSEMBLY
SW_DOC_DRAWING = 3  # swDocumentTypes_e.swDocDRAWING
SW_OPEN_SILENT = 1  # swOpenDocOptions_e.swOpenDocOptions_Silent
SW_SAVE_SILENT = 1  # swSaveAsOptions_e.swSaveAsOptions_Silent
SW_CUSTOM_TEXT = 30  # swCustomInfoType_e.swCustomInfoText
SW_PROP_REPLACE = 2  # swCustomPropertyAddOption_e.swCustomPropertyReplaceValue
_MODEL_DOC_TYPES = {".sldprt": SW_DOC_PART, ".sldasm": SW_DOC_ASSEMBLY}
# The typelib module attach_solidworks generated; _as_model uses it to view a
# document enumerated as IDispatch through IModelDoc2.
_SW_MODULE: Any = None


# --------------------------------------------------------------------------- #
# SolidWorks Pack-and-Go (COM via comtypes)
# --------------------------------------------------------------------------- #
def _close_active_documents(sw: Any) -> None:
    """Close every open document WITHOUT a "Save Modified Documents" prompt.

    Close the active doc by its TITLE, not the empty string: although
    ``CloseDoc("")`` is documented to close the active doc, in 3DX R2026x it
    silently NO-OPS on any assembly that has loaded components (it only closes a
    standalone part) -- so an export that relied on it left every assembly + its
    components resident. ``CloseDoc(GetTitle())`` closes the assembly AND its
    hidden components (document count drops to 0), and ``CloseDoc`` still discards
    a dirty document without saving, so no save modal appears. Loop until no
    document is active; bounded so a misbehaving session can't spin, and RAISE
    on exhaustion -- returning
    normally would make a still-occupied seat indistinguishable from an empty
    one, hand a resident document to ``CloseAllDocuments(True)`` (the modal path
    this function exists to avoid), and let ``_release_seat`` log "seat
    released" over an occupied seat.

    Refuse an empty title: ``CloseDoc("")`` is the very no-op trap above, so
    falling back to it would silently spin this loop and leave the doc resident.
    Fail loud instead of regressing invisibly.
    """
    for _ in range(500):
        doc = sw.IActiveDoc2
        if doc is None:
            return
        title = doc.GetTitle()
        if not title:
            raise RuntimeError(
                f"active document has an empty title ({title!r}) -- refusing "
                f"CloseDoc(''), which silently no-ops on assemblies and would "
                f"leave the document resident"
            )
        sw.CloseDoc(title)
    if sw.IActiveDoc2 is not None:
        raise RuntimeError(
            "documents are still open after 500 CloseDoc calls -- the seat is "
            "not empty, so refusing to report it released; close SolidWorks' "
            "documents by hand"
        )


def _discard_open_documents(sw: Any) -> None:
    """Close every open document WITHOUT a "Save Modified Documents" prompt.

    ``CloseAllDocuments(True)`` still pops that modal in 3DX R2026x when an open
    assembly has a DIRTY referenced child -- e.g. after a ``verify.py --suite
    motion`` run re-solved a child, or an interrupted build left a doc un-saved.
    Headless, that modal hangs the release forever.

    Discard the active docs first (above), then ``CloseAllDocuments(True)`` as a
    backstop -- with nothing dirty left, it has nothing to prompt about.
    """
    _close_active_documents(sw)
    sw.CloseAllDocuments(True)


def _release_seat(sw: Any) -> None:
    """Leave the seat EMPTY -- load-bearing, see the module docstring.

    Called on EVERY exit path: a document left resident here share-locks its
    ``cad/out`` file past this COM session, and the next task's remote-cache
    restore runs outside the seat.

    Empty of DIRECTORIES too: Pack-and-Go opens documents from ``cad/out``, so
    the seat's own current directory ends up inside this checkout -- which, on a
    farm worker, is a source root the agent later removes. Warn-only, unlike the
    close above: a `cwd` this session cannot move is the next leaf's hazard, and
    failing a finished release over it would be worse than reporting it.
    """
    try:
        _discard_open_documents(sw)
        log("seat released: no document left open")
    finally:
        # In a ``finally``, so a close that RAISES still re-points: an exit that
        # dies mid-teardown is exactly the one that leaves a seat parked in a
        # source root, and the raising close propagates either way.
        try:
            left = _seat_forensics.release_seat_working_directory(sw)
        except Exception as error:  # noqa: BLE001
            _telemetry.warn(f"seat working directory re-point failed: {error}")
        else:
            if left is not None:
                log(f"seat working directory moved to {left}")


def attach_solidworks() -> tuple[Any, str]:
    """Attach to the running SolidWorks via comtypes; return (ISldWorks, revision).

    Uses comtypes, NOT the pywin32 adapter: ``GetPackAndGo`` returns an
    ``[out, retval] IPackAndGo**`` param that win32com cannot marshal (it returns
    null across every invocation style -- pywin32 issues #1303/#622), whereas
    comtypes generates correct [out,retval] handling straight from the typelib.
    GetActiveObject attaches to the SW instance the user already launched from the
    3DEXPERIENCE Platform shortcut (never start sldworks.exe -- the Makers seat
    rejects a COM-launched instance as unlicensed).
    """
    import comtypes
    import comtypes.client

    global _SW_MODULE
    mod = comtypes.client.GetModule((comtypes.GUID(SW_TYPELIB), *SW_TYPELIB_VER))
    _SW_MODULE = mod
    sw = comtypes.client.GetActiveObject(
        "SldWorks.Application", interface=mod.ISldWorks
    )
    revision = sw.RevisionNumber()
    log(f"attached to SolidWorks, revision {revision}")
    return sw, revision


def _pack_and_go_document(
    sw: Any, source: Path, doc_type: int, zip_path: Path
) -> tuple[Path, ...]:
    """Pack-and-Go ``source`` and all references into a flat zip.

    Pack-and-Go bundles a document with every file it references; SetSaveToName2
    with a ``.zip`` target writes a single archive, FlattenToSingleFolder drops
    the original folder tree so the zip opens cleanly anywhere.
    """
    # Discard any open docs silently first: a dirty referenced child (left by a
    # prior motion verify) would make CloseAllDocuments(True) prompt.
    _discard_open_documents(sw)
    log("discarded any open documents (clean session)")
    sw.OpenDoc6(str(source), doc_type, SW_OPEN_SILENT, "", 0, 0)
    log(f"opened {source.name}")

    active = sw.IActiveDoc2
    if active is None:
        raise RuntimeError(f"SolidWorks did not open {source}")
    active_path = Path(str(active.GetPathName())).resolve()
    if active_path != source.resolve():
        raise RuntimeError(
            f"active document {active_path} != Pack-and-Go source {source.resolve()}"
        )

    ext = active.Extension
    pg = ext.GetPackAndGo()
    if pg is None:
        raise RuntimeError("GetPackAndGo returned None")

    # Bundle exactly the CAD: no drawings/sim/toolbox, but DO include components
    # suppressed in the active config so no part is dropped from the archive.
    pg.IncludeDrawings = False
    pg.IncludeSimulationResults = False
    pg.IncludeToolboxComponents = False
    pg.IncludeSuppressed = True
    pg.FlattenToSingleFolder = True

    names_count = pg.GetDocumentNamesCount()
    document_names, got_names = pg.GetDocumentNames()
    if not got_names:
        raise RuntimeError("Pack-and-Go did not return original document names")
    documents = tuple(Path(str(name)).resolve() for name in document_names)
    if len(documents) != names_count:
        raise RuntimeError(
            "Pack-and-Go document-name count mismatch: "
            f"reported {names_count}, returned {len(documents)}"
        )
    log(f"pack-and-go: {names_count} referenced documents")

    if not pg.SetSaveToName2(True, str(zip_path)):
        raise RuntimeError(f"SetSaveToName2 rejected {zip_path}")

    statuses = ext.SavePackAndGo(pg)
    log(f"pack-and-go: SavePackAndGo statuses = {statuses}")

    # Run-don't-build: the only proof Pack-and-Go succeeded is the file on disk.
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        raise RuntimeError(f"Pack-and-Go produced no zip at {zip_path}")

    return documents


# --------------------------------------------------------------------------- #
# Flat-archive merge (original-source identity decides every collision)
# --------------------------------------------------------------------------- #
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _source_index(paths: tuple[Path, ...]) -> dict[str, Path]:
    """Index Pack-and-Go originals by their case-insensitive flat filename."""
    indexed: dict[str, Path] = {}
    for path in paths:
        key = path.name.casefold()
        previous = indexed.get(key)
        if previous is not None and previous != path:
            raise RuntimeError(
                "Pack-and-Go cannot flatten distinct source files with the same "
                f"name: {previous} and {path}"
            )
        indexed[key] = path
    return indexed


def _merge_pack_and_go_zip(
    archive: Path,
    original_sources: tuple[Path, ...],
    destinations: tuple[tuple[Path, dict[str, Path]], ...],
) -> tuple[str, ...]:
    """Merge one flat Pack-and-Go archive using original source identity.

    Pack-and-Go rewrites internal reference paths, so two archives made from the
    same source document can legitimately have different bytes.  A duplicate is
    accepted only when ``GetDocumentNames`` proves both copies came from the exact
    same original path; a same-filename collision from distinct originals remains
    a hard failure.
    """
    unpacked = archive.with_suffix("")
    if unpacked.exists():
        shutil.rmtree(unpacked)
    unpacked.mkdir(parents=True)
    archive_sources = _source_index(original_sources)
    members: list[str] = []
    try:
        shutil.unpack_archive(str(archive), str(unpacked), "zip")
        for source in unpacked.iterdir():
            if not source.is_file():
                raise RuntimeError(
                    f"Pack-and-Go archive is not flat: {source.relative_to(unpacked)}"
                )
            key = source.name.casefold()
            original = archive_sources.get(key)
            if original is None:
                raise RuntimeError(
                    "Pack-and-Go archive member has no original source identity: "
                    f"{source.name}"
                )
            for destination, known_sources in destinations:
                known = known_sources.get(key)
                if known is not None and known != original:
                    raise RuntimeError(
                        "Pack-and-Go filename collision comes from different "
                        f"sources: {known} and {original}"
                    )
                target = destination / source.name
                if not target.exists():
                    shutil.copy2(source, target)
                elif _sha256(source) != _sha256(target):
                    _telemetry.event(
                        "release.pack_collision_same_source",
                        filename=source.name,
                        original_source=str(original),
                        destination=str(destination),
                    )
                    log(
                        "pack-and-go: kept existing rewritten copy of "
                        f"{source.name}; original source identity matches"
                    )
                known_sources[key] = original
            members.append(source.name)
        missing = sorted(
            path.name
            for key, path in archive_sources.items()
            if key not in {name.casefold() for name in members}
        )
        if missing:
            raise RuntimeError(
                "Pack-and-Go archive omitted named source documents: "
                + ", ".join(missing)
            )
    finally:
        shutil.rmtree(unpacked, ignore_errors=True)
    return tuple(sorted(members))


# --------------------------------------------------------------------------- #
# Prepared native tree
# --------------------------------------------------------------------------- #
def _repo_relative(path: Path) -> str:
    """Repo-relative POSIX path -- the ONE path convention of the sidecar.

    An absolute path would be meaningless to the submitter that reads the sidecar
    (this runs on a farm worker whose checkout lives somewhere else), so a
    document outside the repository is a hard failure rather than a leaked
    machine path.
    """
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise RuntimeError(
            f"cannot record a path outside the repository in {SIDECAR_NAME}: "
            f"{resolved}"
        ) from exc


def _file_count(directory: Path) -> int:
    return sum(1 for path in directory.iterdir() if path.is_file())


def prepare_out(out: Path) -> None:
    """Wipe and recreate the prepared-tree directory.

    Regenerate-don't-repair: a rerun that inherited a member from a previous
    Pack-and-Go would publish a document this run never produced.
    """
    if out.exists():
        shutil.rmtree(out)
    for subdir in (NATIVE_SUBDIR, DRAWING_SUBDIR, PDF_SUBDIR, PNG_SUBDIR):
        (out / subdir).mkdir(parents=True)


def package_top_assembly(sw: Any, out: Path) -> tuple[Path, ...]:
    """Pack-and-Go the top assembly and lay its flat member set down first.

    The top-assembly set has precedence: every later drawing Pack-and-Go merges
    INTO this directory without overwriting a native model that is already there
    (Pack-and-Go rewrites reference paths, so the drawing's copy of a model has
    different bytes for the same original source).
    """
    top = OUT_SLDASM / f"{TOP_ASSEMBLY}.SLDASM"
    archive = RELEASE_DIR / f"_{TOP_ASSEMBLY}-packandgo.zip"
    archive.unlink(missing_ok=True)
    try:
        documents = _pack_and_go_document(sw, top, SW_DOC_ASSEMBLY, archive)
        log(f"pack-and-go: {archive.stat().st_size / 1e6:.1f} MB native archive")
        shutil.unpack_archive(str(archive), str(out / NATIVE_SUBDIR), "zip")
    finally:
        archive.unlink(missing_ok=True)
    return documents


def package_drawings(
    sw: Any,
    out: Path,
    native_sources: dict[str, Path],
) -> dict[str, dict[str, Any]]:
    """Pack each native drawing with its model references into the prepared tree.

    Two destinations per drawing: ``solidworks/`` (merged into the top-assembly
    set, never overwriting it) and ``slddrw/`` (the drawing plus the models it
    references, so the print opens standalone).
    """
    native_dir = out / NATIVE_SUBDIR
    drawing_dir = out / DRAWING_SUBDIR
    drawing_sources: dict[str, Path] = {}
    packaged: dict[str, dict[str, Any]] = {}
    for drawing_name, outputs in DRAWING_OUTPUTS.items():
        source = outputs["slddrw"]
        archive = RELEASE_DIR / f"_{drawing_name}-drawing-packandgo.zip"
        archive.unlink(missing_ok=True)
        with _telemetry.span("package.drawing", drawing=drawing_name) as sp:
            try:
                original_sources = _pack_and_go_document(
                    sw, source, SW_DOC_DRAWING, archive
                )
                members = _merge_pack_and_go_zip(
                    archive,
                    original_sources,
                    (
                        (native_dir, native_sources),
                        (drawing_dir, drawing_sources),
                    ),
                )
            finally:
                archive.unlink(missing_ok=True)

            native_drawing = native_dir / source.name
            if not native_drawing.is_file() or native_drawing.stat().st_size == 0:
                raise RuntimeError(
                    f"drawing Pack-and-Go omitted its source document: {source.name}"
                )
            sp.set_attribute("members", len(members))
            packaged[drawing_name] = {
                "source": _repo_relative(source),
                "native_slddrw": _repo_relative(native_drawing),
                "portable_slddrw": _repo_relative(drawing_dir / source.name),
                "sources": sorted(_repo_relative(path) for path in original_sources),
            }
    return packaged


# --------------------------------------------------------------------------- #
# Release stamping (the ONLY place the real vNN enters a document)
# --------------------------------------------------------------------------- #
def _as_model(document: Any) -> Any:
    """View an enumerated document through IModelDoc2.

    ``GetDocuments`` returns IDispatch pointers that comtypes may wrap as the
    coclass' default interface (IPartDoc/IAssemblyDoc/IDrawingDoc), none of
    which carries ``GetPathName``; ``IActiveDoc2`` is already IModelDoc2.
    """
    query = getattr(document, "QueryInterface", None)
    if query is None or _SW_MODULE is None:
        return document
    return query(_SW_MODULE.IModelDoc2)


def resident_documents(sw: Any) -> list[tuple[Path, Any]]:
    """Every document resident in the session (visible or hidden), with its path."""
    residents: list[tuple[Path, Any]] = []
    for raw in sw.GetDocuments() or ():
        if raw is None:
            continue
        document = _as_model(raw)
        name = str(document.GetPathName() or "")
        if name:
            residents.append((Path(name).resolve(), document))
    return residents


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def assert_contained(sw: Any, tree: Path, tree_names: set[str]) -> set[str]:
    """Fail unless every packaged model SolidWorks resolved is ``tree``'s own copy.

    Opening a Pack-and-Go copy can resolve a reference through SolidWorks'
    external-reference search rules to a document OUTSIDE the tree -- the
    ``cad/out`` original it was packed from, or a sibling source root on a farm
    worker.  A stamp written through such a reference lands on the wrong file
    and the packaged copy ships unstamped, so any resident whose filename is a
    member of this tree (or that lives under any ``cad/out``) must be the tree
    copy itself.  Residents that are neither -- library documents such as a Hole
    Wizard fastener SolidWorks keeps loaded from its own install -- are allowed
    and returned so the sidecar records them.
    """
    tree = tree.resolve()
    foreign: list[str] = []
    external: set[str] = set()
    for path, _document in resident_documents(sw):
        if _inside(path, tree):
            continue
        parts = [part.casefold() for part in path.parts]
        from_build_tree = any(
            first == "cad" and second == "out"
            for first, second in zip(parts, parts[1:])
        )
        if path.name.casefold() in tree_names or from_build_tree:
            foreign.append(str(path))
            continue
        external.add(path.name)
    if foreign:
        raise RuntimeError(
            f"packaged documents in {tree} resolved {len(foreign)} reference(s) "
            f"outside the package -- a stamp would miss the shipped copy: "
            + ", ".join(sorted(foreign))
        )
    return external


def _open_document(sw: Any, path: Path, doc_type: int) -> Any:
    """Open ``path`` silently and return it as the active IModelDoc2."""
    sw.OpenDoc6(str(path), doc_type, SW_OPEN_SILENT, "", 0, 0)
    active = sw.IActiveDoc2
    if active is None:
        raise RuntimeError(f"SolidWorks did not open {path}")
    active_path = Path(str(active.GetPathName())).resolve()
    if active_path != path.resolve():
        raise RuntimeError(f"active document {active_path} != opened {path.resolve()}")
    return active


def set_document_property(document: Any, name: str, value: str) -> None:
    """Write one file-level text property and prove it by reading it back."""
    manager = document.Extension.CustomPropertyManager("")
    if manager is None:
        raise RuntimeError("CustomPropertyManager unavailable")
    manager.Add3(name, SW_CUSTOM_TEXT, value, SW_PROP_REPLACE)
    back = str(document.GetCustomInfoValue("", name) or "")
    if back != value:
        raise RuntimeError(f"custom property {name} reads {back!r} after writing {value!r}")


def _file_state(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def save_document(document: Any, path: Path) -> None:
    """``Save3`` in place; the rewritten file on disk is the only proof.

    comtypes returns Save3's [out] error/warning codes alongside its result in
    an order that is not worth trusting, so success is judged the way Pack-and-Go
    already is: by the file itself changing.
    """
    before = _file_state(path)
    result = document.Save3(SW_SAVE_SILENT)
    if _file_state(path) == before:
        raise RuntimeError(f"Save3 did not rewrite {path.name} (result {result!r})")


def export_pdf(document: Any, pdf: Path) -> None:
    """The build's own PDF export (``save_drawing``'s extension-driven SaveAs3)."""
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.unlink(missing_ok=True)
    result = document.SaveAs3(str(pdf), 0, 0)
    if not pdf.is_file() or pdf.stat().st_size == 0:
        raise RuntimeError(f"SaveAs3 produced no PDF at {pdf} (result {result!r})")


def _stale_revisions(
    sw: Any, tree: Path, revision: str
) -> list[str]:
    """Tree models resident with a Revision other than ``revision``.

    A drawing opens its models FROM DISK, so this reads back what the model
    pass saved -- the round trip that proves the stamp reached the file.
    """
    stale = []
    for path, document in resident_documents(sw):
        if path.suffix.casefold() not in _MODEL_DOC_TYPES or not _inside(path, tree):
            continue
        value = str(document.GetCustomInfoValue("", REVISION_PROPERTY) or "")
        if value != revision:
            stale.append(f"{path.name}={value!r}")
    return stale


def _require_source_resident(sw: Any, tree: Path, drawing: Path, source: str) -> None:
    """The drawing's own model must have loaded from this tree.

    A silent open never shows the missing-reference dialog: a drawing whose
    model failed to resolve opens on its cached views, nothing foreign is
    resident, nothing stale is found -- and its REV cell would keep the build's
    ``DEV``.  So the model it documents must be resident, as the tree's copy.
    """
    wanted = source.casefold()
    for path, _document in resident_documents(sw):
        if path.name.casefold() == wanted and _inside(path, tree.resolve()):
            return
    raise RuntimeError(
        f"{tree.name}/{drawing.name} opened without its model {source} -- "
        "the reference did not resolve, so its REV cell cannot refresh"
    )


def stamp_models(sw: Any, tree: Path, revision: str) -> tuple[int, set[str]]:
    """Stamp ``Revision`` into every packaged part, then every assembly.

    Parts go first so an assembly (whose save may rewrite dirty children) only
    ever loads already-stamped parts.  The order is also load-bearing for
    reference resolution: SolidWorks searches the folder it last opened from
    BEFORE the referencing document's own folder, so opening this tree's parts
    directly first makes the tree the "last path" by the time any assembly or
    drawing resolves its children.  Each document opens in an empty session,
    is proven contained, stamped, read back and saved.
    """
    files = sorted(path for path in tree.iterdir() if path.is_file())
    tree_names = {path.name.casefold() for path in files}
    models = [path for path in files if path.suffix.casefold() == ".sldprt"]
    models += [path for path in files if path.suffix.casefold() == ".sldasm"]
    external: set[str] = set()
    with _telemetry.span(
        "package.stamp_models", tree=tree.name, documents=len(models)
    ):
        for path in models:
            _discard_open_documents(sw)
            document = _open_document(sw, path, _MODEL_DOC_TYPES[path.suffix.casefold()])
            external |= assert_contained(sw, tree, tree_names)
            set_document_property(document, REVISION_PROPERTY, revision)
            save_document(document, path)
            log(f"stamped {tree.name}/{path.name} Revision={revision}")
        _discard_open_documents(sw)
    return len(models), external


def stamp_drawings(
    sw: Any,
    tree: Path,
    revision: str,
    pdf_dir: Path | None,
) -> tuple[dict[str, Path], set[str]]:
    """Stamp ``BUILD_ID``, refresh the REV cell and save every packaged drawing.

    With ``pdf_dir`` (the portable tree), each registered drawing is also
    exported to ``pdf_dir/<stem>.pdf`` after its save.  Returns the exported
    PDFs by drawing name and the external library residents seen.
    """
    files = sorted(path for path in tree.iterdir() if path.is_file())
    tree_names = {path.name.casefold() for path in files}
    drawings = [path for path in files if path.suffix.casefold() == ".slddrw"]
    registered = {
        outputs["slddrw"].name.casefold(): (name, outputs)
        for name, outputs in DRAWING_OUTPUTS.items()
    }
    exported: dict[str, Path] = {}
    external: set[str] = set()
    for path in drawings:
        with _telemetry.span(
            "package.stamp_drawing", tree=tree.name, drawing=path.name
        ) as sp:
            _discard_open_documents(sw)
            document = _open_document(sw, path, SW_DOC_DRAWING)
            external |= assert_contained(sw, tree, tree_names)
            entry = registered.get(path.name.casefold())
            if entry is not None:
                _require_source_resident(sw, tree, path, DRAWING_SOURCES[entry[0]])
            stale = _stale_revisions(sw, tree, revision)
            if stale:
                raise RuntimeError(
                    f"{tree.name}/{path.name} references models without Revision "
                    f"{revision}: {', '.join(stale)}"
                )
            set_document_property(document, BUILD_ID_PROPERTY, revision)
            # The REV cell is a $PRPSHEET link: a rebuild re-reads the stamped
            # model property before the save and the export capture it.
            document.ForceRebuild3(False)
            save_document(document, path)
            if pdf_dir is not None and entry is not None:
                name, outputs = entry
                pdf = pdf_dir / outputs["pdf"].name
                export_pdf(document, pdf)
                exported[name] = pdf
                sp.set_attribute("pdf", pdf.name)
    _discard_open_documents(sw)
    return exported, external


def stamp_release(sw: Any, out: Path, revision: str) -> dict[str, Any]:
    """Stamp both packaged trees with ``revision``; export the release PDFs.

    ``solidworks/`` is the flat native set, ``slddrw/`` the portable drawing
    set with its own model copies -- both ship, so both are stamped.  PDFs come
    from the portable copies (the documents a consumer opens standalone).
    """
    stamped: dict[str, Any] = {"revision": revision, "trees": {}}
    pdfs: dict[str, Path] = {}
    external: set[str] = set()
    with _telemetry.span("package.stamp_release", revision=revision) as sp:
        for subdir, pdf_dir in (
            (NATIVE_SUBDIR, None),
            (DRAWING_SUBDIR, out / PDF_SUBDIR),
        ):
            tree = out / subdir
            models, seen = stamp_models(sw, tree, revision)
            external |= seen
            exported, seen = stamp_drawings(sw, tree, revision, pdf_dir)
            external |= seen
            pdfs.update(exported)
            drawings = sum(
                1 for path in tree.iterdir() if path.suffix.casefold() == ".slddrw"
            )
            stamped["trees"][subdir] = {"models": models, "drawings": drawings}
        missing = sorted(set(DRAWING_OUTPUTS) - set(pdfs))
        if missing:
            raise RuntimeError(
                f"no stamped portable drawing to export for: {', '.join(missing)}"
            )
        stamped["external_residents"] = sorted(external)
        sp.set_attribute("pdfs", len(pdfs))
        sp.set_attribute("external_residents", len(external))
    stamped["pdfs"] = pdfs
    return stamped


# --------------------------------------------------------------------------- #
# Release prints (offline: no seat needed)
# --------------------------------------------------------------------------- #
def build_pdf_facts(build_pdf: Path) -> tuple[str, int]:
    """Title and page count of the build's own print for this drawing.

    The drawing task sanitized its PDF with the drawing's title and checked its
    page count against the sheets; the release print must match both.
    """
    from pypdf import PdfReader

    if not build_pdf.is_file():
        raise RuntimeError(f"build PDF missing: {build_pdf} -- rerun its drawing task")
    reader = PdfReader(build_pdf)
    title = str((reader.metadata or {}).get("/Title") or "")
    if not title:
        raise RuntimeError(f"build PDF has no /Title: {build_pdf}")
    return title, len(reader.pages)


def page_layouts(pdf: Path, allowed: Sequence[DrawingLayout]) -> tuple[DrawingLayout, ...]:
    """Match each PDF page to the one allowed ASME B orientation it measures.

    Measured with pdfium, the renderer ``render_pdf_png`` validates against.
    """
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(pdf))
    sizes: list[tuple[float, float]] = []
    try:
        for index in range(len(document)):
            page = document[index]
            sizes.append((float(page.get_width()), float(page.get_height())))
            page.close()
    finally:
        document.close()
    layouts: list[DrawingLayout] = []
    for index, size in enumerate(sizes, start=1):
        matches = [
            layout
            for layout in allowed
            if all(
                abs(actual - expected) <= 72.0 / DRAWING_TEMPLATES[layout].dpi + 1e-6
                for actual, expected in zip(
                    size,
                    (
                        DRAWING_TEMPLATES[layout].width_m / 0.0254 * 72.0,
                        DRAWING_TEMPLATES[layout].height_m / 0.0254 * 72.0,
                    ),
                    strict=True,
                )
            )
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"{pdf.name} page {index} ({size[0]:g} x {size[1]:g} pt) matches "
                f"{len(matches)} of the allowed layouts {[item.value for item in allowed]}"
            )
        layouts.append(matches[0])
    return tuple(layouts)


def assert_pdf_revision(pdf: Path, revision: str, *, pages: int) -> None:
    """Every page names ``revision`` and no page says the build's ``DEV``.

    End-to-end proof that the title block's REV (a link to the model) and
    BUILD (the drawing's own property) cells refreshed before the export.
    """
    from pypdf import PdfReader

    reader = PdfReader(pdf)
    if len(reader.pages) != pages:
        raise RuntimeError(f"{pdf.name} has {len(reader.pages)} pages, expected {pages}")
    wanted = re.compile(rf"\b{re.escape(revision)}\b")
    build = re.compile(rf"\b{re.escape(BUILD_REVISION)}\b")
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if build.search(text):
            raise RuntimeError(f"{pdf.name} page {index} still says {BUILD_REVISION}")
        if not wanted.search(text):
            raise RuntimeError(f"{pdf.name} page {index} does not name {revision}")


def finish_release_prints(
    out: Path, revision: str, pdfs: dict[str, Path]
) -> dict[str, dict[str, str]]:
    """Sanitize, verify and render every stamped release PDF to its PNG."""
    from _drawing_common import render_pdf_png, sanitize_pdf_metadata

    prints: dict[str, dict[str, str]] = {}
    with _telemetry.span("package.release_prints", drawings=len(pdfs)):
        for name, pdf in sorted(pdfs.items()):
            outputs = DRAWING_OUTPUTS[name]
            title, pages = build_pdf_facts(outputs["pdf"])
            sanitize_pdf_metadata(pdf, title=title, expected_pages=pages)
            assert_pdf_revision(pdf, revision, pages=pages)
            layouts = page_layouts(pdf, DRAWING_LAYOUTS[name])
            png = out / PNG_SUBDIR / outputs["png"].name
            render_pdf_png(
                pdf,
                png,
                layout=DRAWING_LAYOUTS[name][0],
                expected_pages=pages,
                page_layouts=layouts,
            )
            prints[name] = {"pdf": _repo_relative(pdf), "png": _repo_relative(png)}
    return prints


def write_sidecar(
    out: Path,
    revision: str,
    documents: tuple[Path, ...],
    drawings: dict[str, dict[str, Any]],
    *,
    cad_revision: str,
    stamped: dict[str, Any],
    prints: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Write ``native-package.json``: every COM-derived fact the publisher needs.

    Paths are repo-relative POSIX (see the module docstring); ``native_files`` /
    ``drawing_files`` let the publisher prove the tree it restored from the remote
    cache is the tree this run produced.  ``cad_revision`` is the release number
    every packaged document was stamped with; the publisher refuses to ship a
    tree stamped for any other tag.  Each drawing entry gains the ``pdf`` and
    ``png`` release prints exported from its stamped portable copy.
    """
    native_dir = out / NATIVE_SUBDIR
    drawing_dir = out / DRAWING_SUBDIR
    missing = sorted(set(drawings) - set(prints))
    if missing:
        raise RuntimeError(f"no release print for drawing(s): {', '.join(missing)}")
    drawings = {
        name: {**entry, **prints[name]} for name, entry in sorted(drawings.items())
    }
    package = {
        "schema": SIDECAR_SCHEMA,
        "solidworks_revision": revision,
        "cad_revision": cad_revision,
        "stamped": {key: value for key, value in stamped.items() if key != "pdfs"},
        "packaged_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "out_dir": _repo_relative(out),
        "native_dir": _repo_relative(native_dir),
        "drawing_dir": _repo_relative(drawing_dir),
        "top_assembly": _repo_relative(OUT_SLDASM / f"{TOP_ASSEMBLY}.SLDASM"),
        "documents": len(documents),
        "top_assembly_sources": sorted(_repo_relative(path) for path in documents),
        "native_files": _file_count(native_dir),
        "drawing_files": _file_count(drawing_dir),
        "drawings": drawings,
    }
    sidecar = out / SIDECAR_NAME
    sidecar.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    log(
        f"native package: {package['native_files']} files in {NATIVE_SUBDIR}/ "
        f"({package['documents']} referenced documents), "
        f"{package['drawing_files']} in {DRAWING_SUBDIR}/ for "
        f"{len(drawings)} drawings -> {sidecar.name}"
    )
    return package


def package_native(out: Path) -> dict[str, Any]:
    """Produce the whole prepared tree + sidecar under ``out``."""
    top = OUT_SLDASM / f"{TOP_ASSEMBLY}.SLDASM"
    if not top.exists():
        raise SystemExit(f"!!  {top} not built -- run doit first")
    if not DRAWING_OUTPUTS:
        raise SystemExit("!!  the drawing registry is empty -- nothing to package")

    # The one read of release.yaml in the whole pipeline's COM half.
    cad_revision = _config.release_revision()
    prepare_out(out)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    sw, revision = attach_solidworks()
    failed = False
    try:
        with _telemetry.span("package.top_assembly", document=top.name) as sp:
            documents = package_top_assembly(sw, out)
            sp.set_attribute("documents", len(documents))
        native_sources = _source_index(documents)
        drawings = package_drawings(sw, out, native_sources)
        stamped = stamp_release(sw, out, cad_revision)
    except Exception:
        failed = True
        raise
    finally:
        try:
            _release_seat(sw)
        except Exception:
            _telemetry.error(
                "could not close every open document -- SolidWorks may still "
                "share-lock a cad/out document, which fails the next task's "
                "out-of-seat cache restore with PermissionError(13); close "
                "SolidWorks' documents (or run release_seat_documents.py)",
                exc_info=True,
            )
            if not failed:
                raise
    prints = finish_release_prints(out, cad_revision, stamped["pdfs"])
    return write_sidecar(
        out,
        revision,
        documents,
        drawings,
        cad_revision=cad_revision,
        stamped=stamped,
        prints=prints,
    )


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Pack-and-Go the native SolidWorks release tree."
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=NATIVE_DIR,
        help=f"prepared-tree directory (default: {NATIVE_DIR.relative_to(REPO_ROOT)})",
    )
    opts = ap.parse_args()

    out = opts.out.resolve()
    # prepare_out() rmtree's this directory, so containment in the repo is NOT
    # enough: `--out .` or `--out cad/out` would pass that check and delete
    # tracked sources or every build output. Accept only the dedicated
    # NATIVE_DIR, or a path under RELEASE_DIR that does not exist yet.
    native = NATIVE_DIR.resolve()
    release = RELEASE_DIR.resolve()
    if out != native:
        try:
            out.relative_to(release)
        except ValueError:
            raise SystemExit(
                f"!!  --out must be {native} or a new path under {release} -- "
                f"it is wiped before packaging: {out}"
            ) from None
        if out.exists():
            raise SystemExit(
                f"!!  --out already exists and is not the dedicated "
                f"{native} -- refusing to wipe it: {out}"
            )

    # Advertise "package-native" as this process's telemetry resource (Aspire
    # "resource" column); fallback-only, so dodo's inherited OTEL_SERVICE_NAME wins
    # under the task and this self-labels a standalone run.
    _telemetry.set_service("package-native")
    # run_pipeline_span extracts the TRACEPARENT dodo._run injected (under
    # `doit package:release`), so this COM work continues the doit task span
    # instead of tracing detached.
    with _telemetry.run_pipeline_span("package_native", out=out.name) as root:
        _telemetry.info(f"packaging the native release tree into {out}")
        started = time.perf_counter()
        try:
            package = package_native(out)
        except Exception as exc:
            # Mark the span ERROR before the early return, else the caught failure
            # would exit the span cleanly and trace as success.
            root.record_exception(exc)
            root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
            traceback.print_exc()
            return 1
        _telemetry.success(f"Done in {time.perf_counter() - started:.1f}s.")
        _telemetry.info(f"revision: {package['solidworks_revision']}")
        _telemetry.info(f"stamped:  {package['cad_revision']}")
        _telemetry.info(f"tree:     {out}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
