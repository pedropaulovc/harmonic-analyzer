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
    <out>/native-package.json  the COM-derived facts the publisher cannot obtain
                               off-seat: SolidWorks revision, referenced-document
                               count, per-drawing members and original sources

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

Requires SolidWorks already open (3DEXPERIENCE Platform shortcut) and NOTHING
else driving it -- single STA COM server.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from _common import CAD_ROOT, OUT_SLDASM, log
from _drawing_registry import DRAWINGS

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
SIDECAR_NAME = "native-package.json"
SIDECAR_SCHEMA = 1
DRAWING_OUTPUTS = {drawing.name: drawing.outputs for drawing in DRAWINGS}

# SolidWorks COM type library (SldWorks); the version pins the same revision the
# pywin32 gen_py module exposes (...x0x34x0) so comtypes generates matching stubs.
SW_TYPELIB = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
SW_TYPELIB_VER = (34, 0)
SW_DOC_ASSEMBLY = 2  # swDocumentTypes_e.swDocASSEMBLY
SW_DOC_DRAWING = 3  # swDocumentTypes_e.swDocDRAWING
SW_OPEN_SILENT = 1  # swOpenDocOptions_e.swOpenDocOptions_Silent


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
    """
    _discard_open_documents(sw)
    log("seat released: no document left open")


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

    mod = comtypes.client.GetModule((comtypes.GUID(SW_TYPELIB), *SW_TYPELIB_VER))
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
    (out / NATIVE_SUBDIR).mkdir(parents=True)
    (out / DRAWING_SUBDIR).mkdir(parents=True)


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


def write_sidecar(
    out: Path,
    revision: str,
    documents: tuple[Path, ...],
    drawings: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Write ``native-package.json``: every COM-derived fact the publisher needs.

    Paths are repo-relative POSIX (see the module docstring); ``native_files`` /
    ``drawing_files`` let the publisher prove the tree it restored from the remote
    cache is the tree this run produced.
    """
    native_dir = out / NATIVE_SUBDIR
    drawing_dir = out / DRAWING_SUBDIR
    package = {
        "schema": SIDECAR_SCHEMA,
        "solidworks_revision": revision,
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
    return write_sidecar(out, revision, documents, drawings)


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
        _telemetry.info(f"tree:     {out}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
