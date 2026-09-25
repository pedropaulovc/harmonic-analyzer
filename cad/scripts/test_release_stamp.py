"""Offline contracts for release-time stamping (``package_native.stamp_release``).

Builds write the constant ``Revision``/``BUILD_ID`` ``DEV``; the release number
enters a document only when ``package:release`` stamps the Pack-and-Go copies.
These tests drive the stamping through a fake SolidWorks session whose "disk" is
a property store keyed by path, so they prove the orchestration: every model in
BOTH packaged trees is stamped and saved before any drawing opens, every drawing
is stamped, rebuilt, saved and (portable tree) exported, a reference resolved
outside the package fails the leaf, and the offline print gate reads the PDF
text. The COM calls themselves are proven on the farm (the release dry run);
the marshalling facts the fake cannot show are pinned against comtypes itself,
with no seat: it cannot unpack a SAFEARRAY of IDispatch, which is why residents
are walked one by one, and OpenDoc6 hands back Errors and Warnings ahead of the
document.
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

import package_native
from _drawing_registry import DrawingLayout


class _PropertyManager:
    def __init__(self, document: "_Document") -> None:
        self._document = document

    def Add3(self, name: str, _kind: int, value: str, _option: int) -> int:
        self._document.props[name] = value
        return 0


class _Extension:
    def __init__(self, document: "_Document") -> None:
        self._document = document

    def CustomPropertyManager(self, _configuration: str) -> _PropertyManager:
        return _PropertyManager(self._document)


class _Document:
    def __init__(self, session: "_Session", path: Path) -> None:
        self.session = session
        self.path = path
        self.props = dict(session.disk.get(path, {}))
        self.Extension = _Extension(self)
        self.rebuilt = False

    def GetPathName(self) -> str:
        return str(self.path)

    def GetTitle(self) -> str:
        return self.path.name

    def GetCustomInfoValue(self, _configuration: str, name: str) -> str:
        return self.props.get(name, "")

    def GetNext(self):
        resident = self.session.resident
        at = next(i for i, doc in enumerate(resident) if doc is self)
        return resident[at + 1] if at + 1 < len(resident) else None

    def Save3(self, _options: int) -> list:
        """comtypes' shape: the [in, out] Errors and Warnings, then the result."""
        if self.path in self.session.refuse_save:
            return [0, 0, True]  # reports success, leaves the file as it was
        self.session.disk[self.path] = dict(self.props)
        with self.path.open("ab") as handle:
            handle.write(b"+saved")
        if self.path in self.session.fail_save:
            return [0x4, 0, False]  # touched the file, then failed
        self.session.saves.append(self.path)
        return [0, 0, True]

    def ForceRebuild3(self, _top_only: bool) -> bool:
        self.rebuilt = self.path not in self.session.refuse_rebuild
        return self.rebuilt

    def SaveAs3(self, name: str, _version: int, _options: int) -> int:
        assert self.rebuilt, "a print must be exported after the REV cell refresh"
        Path(name).write_bytes(b"%PDF fake print")
        self.session.exports.append((self.path, Path(name)))
        return 0


class _Session:
    """A SolidWorks session: opening a document loads its references too."""

    def __init__(self, references: dict[Path, list[Path]]) -> None:
        self.references = references
        self.disk: dict[Path, dict[str, str]] = {}
        self.resident: list[_Document] = []
        self.saves: list[Path] = []
        self.exports: list[tuple[Path, Path]] = []
        self.opened: list[Path] = []
        self.refuse_save: set[Path] = set()
        self.fail_save: set[Path] = set()
        self.refuse_rebuild: set[Path] = set()
        # (swFileLoadError_e, swFileLoadWarning_e) an open reports, by path.
        self.load_codes: dict[Path, tuple[int, int]] = {}

    @property
    def IActiveDoc2(self):
        return self.resident[0] if self.resident else None

    def OpenDoc6(self, name, _kind, _options, _config, _errors, _warnings):
        """comtypes' shape: the [in, out] Errors and Warnings, then the document."""
        path = Path(name).resolve()
        self.opened.append(path)
        self.resident = [_Document(self, path)] + [
            _Document(self, ref) for ref in self.references.get(path, [])
        ]
        errors, warnings = self.load_codes.get(path, (0, 0))
        return [errors, warnings, self.resident[0]]

    def GetFirstDocument(self):
        return self.resident[0] if self.resident else None

    def GetDocuments(self):
        # What comtypes does with this SAFEARRAY of IDispatch on a real seat.
        raise KeyError(9)

    def CloseDoc(self, _title: str) -> None:
        self.resident = []

    def CloseAllDocuments(self, _include_unsaved: bool) -> bool:
        self.resident = []
        return True


class _NullPointer:
    """A NULL comtypes interface pointer: falsy, and unusable if dereferenced."""

    def __bool__(self) -> bool:
        return False

    def __getattr__(self, name: str):
        raise ValueError("NULL COM pointer access")


def test_resident_documents_walks_first_and_next_not_the_document_array(tmp_path):
    """rekey2's package:release (2026-09-25) died in ``GetDocuments`` with
    comtypes' KeyError 9. The walk must reach every resident -- the hidden
    references a drawing loads included -- through GetFirstDocument/GetNext,
    and stop at the NULL pointer comtypes hands back after the last one."""
    drawing, part = (tmp_path / "a.SLDDRW").resolve(), (tmp_path / "b.SLDPRT").resolve()
    session = _Session({drawing: [part]})
    session.OpenDoc6(str(drawing), 3, 1, "", 0, 0)
    last = session.resident[-1]
    last.GetNext = lambda: _NullPointer()

    residents = package_native.resident_documents(session)

    assert [path for path, _doc in residents] == [drawing, part]


def test_resident_documents_refuses_a_walk_that_never_ends(tmp_path, monkeypatch):
    monkeypatch.setattr(package_native, "_MAX_RESIDENTS", 3)
    session = _Session({})
    session.OpenDoc6(str((tmp_path / "a.SLDPRT").resolve()), 1, 1, "", 0, 0)
    looping = session.resident[0]
    looping.GetNext = lambda: looping

    with pytest.raises(RuntimeError, match="GetNext never ended"):
        package_native.resident_documents(session)


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 only: oleaut32 SAFEARRAYs")
def test_comtypes_cannot_unpack_a_safearray_of_idispatch():
    """The seat-free half of the rekey2 failure: comtypes converts a SAFEARRAY
    of BSTR (Pack-and-Go's GetDocumentNames) but raises KeyError 9 on one of
    IDispatch (GetDocuments) -- before reading a single element."""
    from comtypes.automation import VARIANT, VT_ARRAY, VT_BSTR, VT_DISPATCH

    create = ctypes.windll.oleaut32.SafeArrayCreateVector
    create.restype = ctypes.c_void_p
    create.argtypes = [ctypes.c_ushort, ctypes.c_long, ctypes.c_ulong]

    def array_of(vt: int) -> VARIANT:
        variant = VARIANT()
        variant.vt = VT_ARRAY | vt
        variant._.c_void_p = create(vt, 0, 2)
        return variant

    assert array_of(VT_BSTR).value == (None, None)
    with pytest.raises(KeyError) as err:
        array_of(VT_DISPATCH).value
    assert err.value.args == (VT_DISPATCH,)


def _solidworks_typelib():
    """The generated SolidWorks typelib module, or a skip where it is not registered."""
    if sys.platform != "win32":
        pytest.skip("Win32 only: the SolidWorks typelib")
    import comtypes
    import comtypes.client

    try:
        return comtypes.client.GetModule(
            (comtypes.GUID(package_native.SW_TYPELIB), *package_native.SW_TYPELIB_VER)
        )
    except OSError as error:
        pytest.skip(f"SolidWorks typelib not registered: {error}")


def test_comtypes_returns_opendoc6_errors_and_warnings_before_the_document():
    """The order open_silently unpacks, against the real ISldWorks typelib and
    an in-process COM object -- no seat: [in, out] Errors, [in, out] Warnings,
    then the [out, retval] document, in declaration order."""
    from comtypes import COMObject

    typelib = _solidworks_typelib()

    class _Seat(COMObject):
        _com_interfaces_ = [typelib.ISldWorks]

        def OpenDoc6(self, this, _name, _kind, _options, _config, errors, warnings, _doc):
            # comtypes passes the interface pointer only to a parameter named "this".
            del this
            errors[0] = 0x2
            warnings[0] = 0x100000
            return 0

    seat = _Seat().QueryInterface(typelib.ISldWorks)

    errors, warnings, document = seat.OpenDoc6("x.SLDASM", 2, 1, "", 0, 0)

    assert (errors, warnings, bool(document)) == (0x2, 0x100000, False)


def test_comtypes_returns_save3_errors_and_warnings_before_the_result():
    """save_document's unpacking, pinned the same way: a one-argument Save3
    defaults the [in, out] codes and returns [Errors, Warnings, result]."""
    from comtypes import COMObject

    typelib = _solidworks_typelib()

    class _Model(COMObject):
        _com_interfaces_ = [typelib.IModelDoc2]

        def Save3(self, this, _options, errors, warnings, result):
            del this
            errors[0] = 0x4
            warnings[0] = 0x1
            result[0] = False
            return 0

    model = _Model().QueryInterface(typelib.IModelDoc2)

    assert model.Save3(package_native.SW_SAVE_SILENT) == [0x4, 0x1, False]


def _opened(tmp_path: Path, errors: int, warnings: int) -> tuple[_Session, Path]:
    assembly = (tmp_path / "a.SLDASM").resolve()
    session = _Session({})
    session.load_codes[assembly] = (errors, warnings)
    return session, assembly


@pytest.mark.parametrize(
    ("warnings", "named"),
    [
        (0x100000, "MissingExternalReferences"),
        (0x40, "BasePartNotLoaded"),
        (0x400, "ViewMissingReferencedConfig"),
        (0x8000, "ComponentMissingReferencedConfig"),
    ],
)
def test_an_open_whose_references_did_not_resolve_fails(tmp_path, warnings, named):
    """Codex on #876: a silent open hands back the parent even when a component
    did not load, and the resident walk cannot see what never loaded. A missing
    referenced configuration (round 3) substitutes the active one, so a released
    view would show the wrong configuration."""
    session, assembly = _opened(tmp_path, 0, warnings)

    with pytest.raises(RuntimeError, match=rf"references did not resolve \({named}"):
        package_native.open_silently(session, assembly, package_native.SW_DOC_ASSEMBLY)


def test_an_open_that_reports_a_load_error_fails(tmp_path):
    session, assembly = _opened(tmp_path, 0x2, 0)

    with pytest.raises(RuntimeError, match="swFileLoadError_e 0x2"):
        package_native.open_silently(session, assembly, package_native.SW_DOC_ASSEMBLY)


def test_an_open_with_other_warnings_only_warns_naming_the_references(tmp_path, capsys):
    """IdMismatch stays non-fatal until a release run shows whether a healthy
    open raises it; OpenDoc6 does not say which reference mismatched, so the
    warn line names the document, the bits and every resident reference."""
    session, assembly = _opened(tmp_path, 0, 0x21)  # IdMismatch | NeedsRegen
    session.references[assembly] = [(tmp_path / "b.SLDPRT").resolve()]

    package_native.open_silently(session, assembly, package_native.SW_DOC_ASSEMBLY)

    assert (
        "OpenDoc6 a.SLDASM: swFileLoadWarning_e 0x21 (IdMismatch, NeedsRegen); "
        "resident references: b.SLDPRT"
    ) in capsys.readouterr().err


def _tree(root: Path, names: list[str]) -> list[Path]:
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in names:
        path = (root / name).resolve()
        path.write_bytes(b"packaged copy")
        paths.append(path)
    return paths


@pytest.fixture
def packaged(tmp_path: Path, monkeypatch):
    """A prepared tree: both subtrees carry a part, and a drawing of it;
    solidworks/ also has the top assembly."""
    out = tmp_path / "native"
    native_part, top, native_drawing = _tree(
        out / package_native.NATIVE_SUBDIR,
        ["platen-guide.SLDPRT", "harmonic-analyzer.SLDASM", "platen-guide.SLDDRW"],
    )
    portable_part, portable_drawing = _tree(
        out / package_native.DRAWING_SUBDIR,
        ["platen-guide.SLDPRT", "platen-guide.SLDDRW"],
    )
    (out / package_native.PDF_SUBDIR).mkdir()
    build = tmp_path / "cad" / "out"
    monkeypatch.setattr(
        package_native,
        "DRAWING_OUTPUTS",
        {
            "platen_guide": {
                "slddrw": build / "slddrw" / "platen-guide.SLDDRW",
                "pdf": build / "pdf" / "platen-guide.pdf",
                "png": build / "png" / "platen-guide_drawing.png",
            }
        },
    )
    monkeypatch.setattr(
        package_native, "DRAWING_SOURCES", {"platen_guide": "platen-guide.SLDPRT"}
    )
    references = {
        top: [native_part],
        native_drawing: [native_part],
        portable_drawing: [portable_part],
    }
    session = _Session(references)
    return (
        out,
        session,
        {
            "native_part": native_part,
            "top": top,
            "native_drawing": native_drawing,
            "portable_part": portable_part,
            "portable_drawing": portable_drawing,
            "build": build,
        },
    )


def test_stamp_release_stamps_both_trees_and_exports_portable_prints(packaged):
    out, session, docs = packaged

    stamped = package_native.stamp_release(session, out, "v37")

    for model in ("native_part", "top", "portable_part"):
        assert session.disk[docs[model]]["Revision"] == "v37", model
    for drawing in ("native_drawing", "portable_drawing"):
        assert session.disk[docs[drawing]]["BUILD_ID"] == "v37", drawing
    # Models are stamped before any drawing of the same tree opens, so every
    # drawing reads its references back from the stamped "disk".
    native_order = [path for path in session.saves if path.parent == docs["top"].parent]
    assert native_order.index(docs["native_part"]) < native_order.index(docs["top"])
    assert native_order[-1] == docs["native_drawing"]
    # Only the portable copy is printed, into <out>/pdf under the build's name.
    assert session.exports == [
        (docs["portable_drawing"], (out / "pdf" / "platen-guide.pdf"))
    ]
    assert stamped["pdfs"] == {"platen_guide": out / "pdf" / "platen-guide.pdf"}
    assert stamped["trees"] == {
        "solidworks": {"models": 2, "drawings": 1},
        "slddrw": {"models": 1, "drawings": 1},
    }
    assert stamped["external_residents"] == []
    assert session.resident == []  # the seat is left empty


def test_stamp_release_fails_on_a_reference_resolved_outside_the_package(packaged):
    out, session, docs = packaged
    original = docs["build"] / "sldprt" / "platen-guide.SLDPRT"
    session.references[docs["portable_drawing"]] = [original.resolve()]

    with pytest.raises(RuntimeError, match="outside the package"):
        package_native.stamp_release(session, out, "v37")


def test_stamp_release_fails_on_a_sibling_source_root_copy(packaged, tmp_path):
    """Same filename as a packaged model, loaded from anywhere else: foreign."""
    out, session, docs = packaged
    sibling = (tmp_path / "other-root" / "platen-guide.SLDPRT").resolve()
    session.references[docs["top"]] = [sibling]

    with pytest.raises(RuntimeError, match="1 reference"):
        package_native.stamp_release(session, out, "v37")


def test_stamp_release_records_library_residents(packaged, tmp_path):
    """A Hole Wizard library part SolidWorks loads from its install is allowed."""
    out, session, docs = packaged
    library = (tmp_path / "SOLIDWORKS Data" / "binding head screw_ai.sldprt").resolve()
    session.references[docs["native_drawing"]].append(library)

    stamped = package_native.stamp_release(session, out, "v37")

    assert stamped["external_residents"] == ["binding head screw_ai.sldprt"]


def test_stamp_release_fails_when_a_drawing_opens_without_its_model(packaged):
    """A silent open hides a missing reference: the drawing opens on cached
    views with nothing foreign and nothing stale resident, and its REV cell
    would keep DEV. The drawing's own model must be resident from the tree."""
    out, session, docs = packaged
    session.references[docs["native_drawing"]] = []

    with pytest.raises(RuntimeError, match="opened without its model platen-guide"):
        package_native.stamp_release(session, out, "v37")


def test_stamp_release_fails_when_a_drawing_rebuild_fails(packaged):
    """Codex on #876: a failed rebuild leaves the REV cell stale, and only the
    portable copy's print is checked -- the native drawing must not be saved."""
    out, session, docs = packaged
    session.refuse_rebuild.add(docs["native_drawing"])

    with pytest.raises(RuntimeError, match="ForceRebuild3 failed on solidworks/platen-guide"):
        package_native.stamp_release(session, out, "v37")
    assert docs["native_drawing"] not in session.saves


def test_stamp_release_fails_when_a_save_reports_failure_after_touching_the_file(packaged):
    """Codex on #876: a changed file is not proof -- a save that wrote part of it
    and then failed must not be published as stamped CAD."""
    out, session, docs = packaged
    session.fail_save.add(docs["native_part"])

    with pytest.raises(RuntimeError, match="Save3 failed on platen-guide.SLDPRT: swFileSaveError_e 0x4"):
        package_native.stamp_release(session, out, "v37")


def test_stamp_release_fails_when_a_save_does_not_reach_disk(packaged):
    out, session, docs = packaged
    session.refuse_save.add(docs["portable_part"])

    with pytest.raises(RuntimeError, match="did not rewrite platen-guide.SLDPRT"):
        package_native.stamp_release(session, out, "v37")


def test_drawing_refuses_a_model_that_kept_its_build_revision(packaged):
    """The drawing pass reads each model back from disk; DEV there is fatal."""
    out, session, docs = packaged
    tree = docs["native_part"].parent
    session.disk[docs["native_part"]] = {"Revision": "DEV"}

    with pytest.raises(RuntimeError, match="without Revision v37"):
        package_native.stamp_drawings(session, tree, "v37", None)


def _pdf(path: Path, texts: list[str], *, size=(1224, 792)) -> Path:
    """A real PDF whose pages carry ``texts`` (one per page) as extractable text."""
    writer = PdfWriter()
    font = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    for text in texts:
        page = writer.add_blank_page(width=size[0], height=size[1])
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 72 72 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer.write(path)
    return path


def test_release_print_gate_reads_every_page(tmp_path: Path):
    good = _pdf(tmp_path / "good.pdf", ["REV v37 BUILD v37", "REV v37 BUILD v37"])
    package_native.assert_pdf_revision(good, "v37", pages=2)

    stale = _pdf(tmp_path / "stale.pdf", ["REV v37 BUILD v37", "REV DEV BUILD v37"])
    with pytest.raises(RuntimeError, match="page 2 still says DEV"):
        package_native.assert_pdf_revision(stale, "v37", pages=2)

    missing = _pdf(tmp_path / "missing.pdf", ["REV v36 BUILD v36"])
    with pytest.raises(RuntimeError, match="page 1 BUILD cell does not name v37"):
        package_native.assert_pdf_revision(missing, "v37", pages=1)

    # v370 is not v37: the match is a whole token.
    longer = _pdf(tmp_path / "longer.pdf", ["REV v370 BUILD v370"])
    with pytest.raises(RuntimeError, match="BUILD cell does not name v37"):
        package_native.assert_pdf_revision(longer, "v37", pages=1)

    # Codex on #876: each cell is checked on its own, so a fresh BUILD cannot
    # stand in for a stale or blank REV.
    stale_rev = _pdf(tmp_path / "stale-rev.pdf", ["REV v36 BUILD v37"])
    with pytest.raises(RuntimeError, match="page 1 REV cell does not name v37"):
        package_native.assert_pdf_revision(stale_rev, "v37", pages=1)
    blank_rev = _pdf(tmp_path / "blank-rev.pdf", ["REV BUILD v37"])
    with pytest.raises(RuntimeError, match="page 1 REV cell does not name v37"):
        package_native.assert_pdf_revision(blank_rev, "v37", pages=1)

    with pytest.raises(RuntimeError, match="has 1 pages, expected 2"):
        package_native.assert_pdf_revision(missing, "v36", pages=2)


def test_release_print_pages_match_their_sheet_orientation(tmp_path: Path):
    landscape = _pdf(tmp_path / "landscape.pdf", ["REV v37"])
    portrait = _pdf(tmp_path / "portrait.pdf", ["REV v37"], size=(792, 1224))
    both = (DrawingLayout.LANDSCAPE, DrawingLayout.PORTRAIT)

    assert package_native.page_layouts(landscape, both) == (DrawingLayout.LANDSCAPE,)
    assert package_native.page_layouts(portrait, both) == (DrawingLayout.PORTRAIT,)
    with pytest.raises(RuntimeError, match="matches 0 of the allowed layouts"):
        package_native.page_layouts(portrait, (DrawingLayout.LANDSCAPE,))


def test_finish_release_prints_titles_renders_and_records(tmp_path: Path, monkeypatch):
    """The offline half: title from the build print, text gate, PNG render."""
    build_pdf = tmp_path / "cad" / "out" / "pdf" / "platen-guide.pdf"
    _pdf(build_pdf, ["REV DEV BUILD DEV"])
    writer = PdfWriter(clone_from=build_pdf)
    writer.add_metadata({"/Title": "Platen Guide Manufacturing Drawing"})
    writer.write(build_pdf)
    out = tmp_path / "native"
    release_pdf = _pdf(out / "pdf" / "platen-guide.pdf", ["REV v37 BUILD v37"])
    monkeypatch.setattr(package_native, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        package_native,
        "DRAWING_OUTPUTS",
        {
            "platen_guide": {
                "slddrw": tmp_path / "cad" / "out" / "slddrw" / "platen-guide.SLDDRW",
                "pdf": build_pdf,
                "png": tmp_path / "cad" / "out" / "png" / "platen-guide_drawing.png",
            }
        },
    )
    monkeypatch.setattr(
        package_native, "DRAWING_LAYOUTS", {"platen_guide": (DrawingLayout.LANDSCAPE,)}
    )

    prints = package_native.finish_release_prints(
        out, "v37", {"platen_guide": release_pdf}
    )

    assert prints == {
        "platen_guide": {
            "pdf": "native/pdf/platen-guide.pdf",
            "png": "native/png/platen-guide_drawing.png",
        }
    }
    from pypdf import PdfReader

    assert PdfReader(release_pdf).metadata["/Title"] == (
        "Platen Guide Manufacturing Drawing"
    )
    assert (out / "png" / "platen-guide_drawing.png").stat().st_size > 0


def test_build_print_is_never_a_release_print(tmp_path: Path, monkeypatch):
    """The build's DEV print fails the gate if it ever reached a release."""
    build_pdf = _pdf(tmp_path / "platen-guide.pdf", ["REV DEV BUILD DEV"])
    with pytest.raises(RuntimeError, match="still says DEV"):
        package_native.assert_pdf_revision(build_pdf, "v37", pages=1)


def test_package_native_empties_the_seat_before_wiping_the_prepared_tree(
    tmp_path: Path, monkeypatch
):
    """Codex round 4 on #876: a run killed mid-stamping can leave a packaged copy
    open and share-locked, so the next run must close it before prepare_out's
    rmtree -- not after, when the rmtree has already failed."""
    events: list[str] = []
    sldasm = tmp_path / "sldasm"
    sldasm.mkdir()
    (sldasm / f"{package_native.TOP_ASSEMBLY}.SLDASM").write_bytes(b"asm")
    monkeypatch.setattr(package_native, "OUT_SLDASM", sldasm)
    monkeypatch.setattr(package_native, "RELEASE_DIR", tmp_path / "release")
    monkeypatch.setattr(package_native._config, "release_revision", lambda: "v37")
    monkeypatch.setattr(
        package_native, "attach_solidworks", lambda: (events.append("attach"), (object(), "34.0"))[1]
    )
    monkeypatch.setattr(
        package_native, "_discard_open_documents", lambda _sw: events.append("discard")
    )
    monkeypatch.setattr(package_native, "prepare_out", lambda _out: events.append("wipe"))
    monkeypatch.setattr(
        package_native, "package_top_assembly", lambda _sw, _out: (events.append("top"), ())[1]
    )
    monkeypatch.setattr(package_native, "package_drawings", lambda *_a: {})
    monkeypatch.setattr(package_native, "stamp_release", lambda *_a: {"pdfs": {}})
    monkeypatch.setattr(package_native, "_release_seat", lambda _sw: events.append("release"))
    monkeypatch.setattr(package_native, "finish_release_prints", lambda *_a: {})
    monkeypatch.setattr(package_native, "write_sidecar", lambda *_a, **_k: {})

    package_native.package_native(tmp_path / "release" / "native")

    assert events == ["attach", "discard", "wipe", "top", "release"]
