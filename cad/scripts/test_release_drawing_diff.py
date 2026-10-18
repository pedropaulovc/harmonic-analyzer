"""Published drawing baselines use real ZIP members, never the full CAD asset."""

from __future__ import annotations

import io
import json
import struct
import tracemalloc
import urllib.error
import urllib.request
import warnings
import zipfile
from pathlib import Path

import pytest
from pypdf import PdfWriter

from _release_drawing_diff import extract_release_pdfs, previous_published_release


URL = "https://example.test/harmonic-analyzer-v43.zip"


def _release(tag: str = "v43", **metadata: object) -> dict:
    return {
        "tag_name": tag,
        "draft": False,
        "prerelease": False,
        "published_at": "2026-10-18T00:00:00Z",
        "assets": [{"name": f"harmonic-analyzer-{tag}.zip", "browser_download_url": URL}],
        **metadata,
    }


def _pdf() -> bytes:
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=120, height=80)
    writer.write(output)
    return output.getvalue()


def _archive(members: list[tuple[str, bytes]], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        # A large unselected native member proves that extraction is selective.
        archive.writestr("solidworks/opaque.SLDASM", b"x" * 250_000, compress_type=zipfile.ZIP_STORED)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for name, data in members:
                # ZipInfo(name) normalizes backslashes on Windows. Assign the
                # raw archive name afterward so hostile fixtures reach the reader.
                info = zipfile.ZipInfo()
                info.filename = name
                archive.writestr(info, data, compress_type=compression)
    return output.getvalue()


def _serve(monkeypatch: pytest.MonkeyPatch, data: bytes, *, status: int = 206, truncate: bool = False) -> list[tuple[int, int]]:
    requests: list[tuple[int, int]] = []

    class Response(io.BytesIO):
        def __init__(self, first: int, last: int) -> None:
            self.status = status
            self.headers = {"Content-Range": f"bytes {first}-{last}/{len(data)}"}
            payload = data[first:last + 1]
            super().__init__(payload[:-1] if truncate else payload)

        def read(self, size: int = -1) -> bytes:
            assert self.status == 206, "ignored Range response body must not be read"
            assert size >= 0, "reader must bound every download"
            return super().read(size)

    def urlopen(request: urllib.request.Request, **_kwargs: object) -> Response:
        assert request.full_url == URL
        value = request.get_header("Range")
        assert value is not None and value.startswith("bytes=")
        first, last = map(int, value.removeprefix("bytes=").split("-"))
        last = min(last, len(data) - 1)
        requests.append((first, last))
        return Response(first, last)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return requests


def test_baseline_uses_all_published_release_pages_not_local_or_draft_tags() -> None:
    pages = [
        [_release("v41"), _release("v44"), _release("v0.20.0")]
        + [_release(f"draft-{index}", draft=True) for index in range(97)],
        [_release("v43"), _release("v42"), _release("v45", draft=True), _release("v46", prerelease=True)],
    ]
    calls: list[tuple[str, ...]] = []

    def gh(*args: str) -> str:
        calls.append(args)
        return json.dumps(pages[len(calls) - 1])

    assert previous_published_release("v44", "owner/repo", gh)["tag_name"] == "v43"
    assert calls == [
        ("api", "repos/owner/repo/releases?per_page=100&page=1"),
        ("api", "repos/owner/repo/releases?per_page=100&page=2"),
    ]
    assert previous_published_release("v1", "owner/repo", lambda *_a: "[]") is None


@pytest.mark.parametrize("payload", ["{}", "not JSON", '[{"tag_name":"v43"}]'])
def test_malformed_release_metadata_never_becomes_first_release(payload: str) -> None:
    with pytest.raises(ValueError):
        previous_published_release("v44", "owner/repo", lambda *_a: payload)


def test_release_api_failure_is_not_an_empty_baseline() -> None:
    def denied(*_args: str) -> str:
        raise RuntimeError("gh api: HTTP 401")

    with pytest.raises(RuntimeError, match="HTTP 401"):
        previous_published_release("v44", "owner/repo", denied)


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_extracts_real_pdfs_only_with_original_relative_identities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, compression: int,
) -> None:
    pdf = _pdf()
    members = [("pdf/part.pdf", pdf), ("pdf/sub/assembly.PDF", pdf), ("pdf/artwork.dxf", b"not a PDF")]
    data = _archive(members, compression)
    requests = _serve(monkeypatch, data)
    destination = extract_release_pdfs(_release(), tmp_path / "old")

    assert {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()} == {
        "part.pdf", "sub/assembly.PDF",
    }
    assert (destination / "part.pdf").read_bytes() == pdf
    assert (destination / "sub" / "assembly.PDF").read_bytes() == pdf
    # The native member starts near the front and is never requested in full.
    assert all(not (first < 10_000 and last > 100_000) for first, last in requests)
    assert sum(last - first + 1 for first, last in requests) < len(data) // 2


def test_valid_historical_bundle_without_pdfs_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _serve(monkeypatch, _archive([("png/drawing.png", b"preview")]))
    destination = extract_release_pdfs(_release(), tmp_path / "old")
    assert destination.is_dir()
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("names", [
    ["pdf/../escape.pdf"], ["pdf/sub/../../escape.pdf"], ["pdf/C:escape.pdf"],
    ["pdf\\escape.pdf"], ["pdf/sub\\escape.pdf"], ["pdf/CON.pdf"],
    ["pdf/part.pdf", "PDF/PART.PDF"], ["pdf/part.pdf", "pdf/part.pdf"],
])
def test_unsafe_or_duplicate_pdf_identity_fails_before_any_member_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, names: list[str],
) -> None:
    data = _archive([(name, _pdf()) for name in names])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert [info.orig_filename for info in archive.infolist()][1:] == names
    _serve(monkeypatch, data)
    with pytest.raises(ValueError, match="unsafe|duplicate"):
        extract_release_pdfs(_release(), tmp_path / "old")
    assert not (tmp_path / "old").exists()
    assert not (tmp_path / "escape.pdf").exists()


@pytest.mark.parametrize("failure", ["ignored-range", "truncated", "malformed", "header-identity", "crc"])
def test_remote_zip_failures_surface_instead_of_an_empty_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    data = _archive([("pdf/part.pdf", _pdf())], zipfile.ZIP_STORED)
    if failure in ("header-identity", "crc"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            offset = archive.getinfo("pdf/part.pdf").header_offset
        mutable = bytearray(data)
        if failure == "header-identity":
            mutable[offset + 30 + len("pdf/")] = ord("X")
        else:
            name_size, extra_size = struct.unpack_from("<HH", mutable, offset + 26)
            mutable[offset + 30 + name_size + extra_size] ^= 1
        data = bytes(mutable)
    if failure == "malformed":
        data = b"not a ZIP asset"
    _serve(monkeypatch, data, status=200 if failure == "ignored-range" else 206, truncate=failure == "truncated")
    with pytest.raises(ValueError):
        extract_release_pdfs(_release(), tmp_path / "old")
    assert not (tmp_path / "old" / "part.pdf").exists()


def test_remote_asset_http_auth_error_surfaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.HTTPError(URL, 403, "Forbidden", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", denied)
    with pytest.raises(urllib.error.HTTPError, match="403"):
        extract_release_pdfs(_release(), tmp_path / "old")


def test_missing_historical_cad_asset_is_not_an_empty_pdf_set(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly one harmonic-analyzer-v43.zip"):
        extract_release_pdfs(_release(assets=[]), tmp_path / "old")


@pytest.mark.parametrize("has_previous", [False, True])
def test_release_creates_separate_drawing_zip_from_the_published_pdf_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, has_previous: bool,
) -> None:
    import cut_release

    release_dir = tmp_path / "release"
    stage = release_dir / "harmonic-analyzer-v44"
    pdf_dir = stage / "pdf"
    pdf_dir.mkdir(parents=True)
    pdf = _pdf()
    (pdf_dir / "part.pdf").write_bytes(pdf)
    (pdf_dir / "added.pdf").write_bytes(pdf)
    if has_previous:
        _serve(monkeypatch, _archive([("pdf/part.pdf", pdf), ("pdf/removed.pdf", pdf)]))
    monkeypatch.setattr(cut_release, "RELEASE_DIR", release_dir)
    monkeypatch.setattr(cut_release, "_repo_slug", lambda: "owner/repo")
    monkeypatch.setattr(
        cut_release, "_gh",
        lambda *_args: json.dumps([_release()] if has_previous else []),
    )

    result = cut_release.drawing_diff(stage, "v44")

    asset = Path(result["asset_path"])
    assert asset == release_dir / "harmonic-analyzer-v44-drawing-diff.zip"
    assert result["prev"] == ("v43" if has_previous else None)
    assert len(result["added_drawings"]) == (1 if has_previous else 2)
    assert len(result["removed_drawings"]) == (1 if has_previous else 0)
    assert len(result["unchanged_drawings"]) == (1 if has_previous else 0)
    assert result["changed_drawings"] == []
    with zipfile.ZipFile(asset) as archive:
        assert {"index.html", "summary.json"} <= set(archive.namelist())
        assert len([name for name in archive.namelist() if name.endswith(".png")]) == 2
    assert {path.name for path in release_dir.iterdir()} == {stage.name, asset.name}
    assert {path.relative_to(stage).as_posix() for path in stage.rglob("*") if path.is_file()} == {
        "pdf/part.pdf", "pdf/added.pdf",
    }


@pytest.mark.parametrize("size_delta", [-1, 1])
def test_deflate_member_rejects_truncated_or_trailing_compressed_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size_delta: int,
) -> None:
    data = _archive([("pdf/part.pdf", _pdf())])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        compressed_size = archive.getinfo("pdf/part.pdf").compress_size
    mutable = bytearray(data)
    central = data.rfind(b"pdf/part.pdf") - 46
    assert data[central:central + 4] == b"PK\x01\x02"
    struct.pack_into("<I", mutable, central + 20, compressed_size + size_delta)
    _serve(monkeypatch, bytes(mutable))

    with pytest.raises(ValueError, match="invalid/oversized deflate"):
        extract_release_pdfs(_release(), tmp_path / "old")
    assert not (tmp_path / "old" / "part.pdf").exists()


def test_compressed_pdf_cannot_allocate_beyond_its_declared_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Measure inflation, not cold imports of the shared comparison tool's deps.
    __import__("numpy")
    __import__("trimesh")
    data = _archive([("pdf/part.pdf", b"x" * (8 * 1024 * 1024))])
    mutable = bytearray(data)
    central = data.rfind(b"pdf/part.pdf") - 46
    assert data[central:central + 4] == b"PK\x01\x02"
    struct.pack_into("<I", mutable, central + 24, 32)
    _serve(monkeypatch, bytes(mutable))

    already_tracing = tracemalloc.is_tracing()
    if not already_tracing:
        tracemalloc.start()
    try:
        before, _ = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        with pytest.raises(ValueError, match="invalid/oversized deflate"):
            extract_release_pdfs(_release(), tmp_path / "old")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        if not already_tracing:
            tracemalloc.stop()
    assert peak - before < 2 * 1024 * 1024
    assert not (tmp_path / "old" / "part.pdf").exists()
