"""Offline contracts for release-time stamping (``package_native.stamp_release``).

Builds write the constant ``Revision``/``BUILD_ID`` ``DEV``; the release number
enters a document only when ``package:release`` stamps the Pack-and-Go copies.
These tests drive the stamping through a fake SolidWorks session whose "disk" is
a property store keyed by path, so they prove the orchestration: every model in
BOTH packaged trees is stamped and saved before any drawing opens, every drawing
is stamped, rebuilt, saved and (portable tree) exported, a reference resolved
outside the package fails the leaf, and the offline print gate reads the PDF
text. The COM calls themselves are proven on the farm (the release dry run).
"""

from __future__ import annotations

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

    def Save3(self, _options: int) -> bool:
        if self.path in self.session.refuse_save:
            return False
        self.session.disk[self.path] = dict(self.props)
        with self.path.open("ab") as handle:
            handle.write(b"+saved")
        self.session.saves.append(self.path)
        return True

    def ForceRebuild3(self, _top_only: bool) -> bool:
        self.rebuilt = True
        return True

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

    @property
    def IActiveDoc2(self):
        return self.resident[0] if self.resident else None

    def OpenDoc6(self, name, _kind, _options, _config, _errors, _warnings):
        path = Path(name).resolve()
        self.opened.append(path)
        self.resident = [_Document(self, path)] + [
            _Document(self, ref) for ref in self.references.get(path, [])
        ]
        return self.resident[0]

    def GetDocuments(self):
        return tuple(self.resident)

    def CloseDoc(self, _title: str) -> None:
        self.resident = []

    def CloseAllDocuments(self, _include_unsaved: bool) -> bool:
        self.resident = []
        return True


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
    with pytest.raises(RuntimeError, match="page 1 does not name v37"):
        package_native.assert_pdf_revision(missing, "v37", pages=1)

    # v370 is not v37: the match is a whole token.
    longer = _pdf(tmp_path / "longer.pdf", ["REV v370"])
    with pytest.raises(RuntimeError, match="does not name v37"):
        package_native.assert_pdf_revision(longer, "v37", pages=1)

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
