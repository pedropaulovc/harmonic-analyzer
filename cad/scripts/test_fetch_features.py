"""fetch_features: seat-free bundles from a release ZIP, read by byte range."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

import _config
import export_features
import fetch_features

STEM = "ch_amplitude_bar"


def _release_zip(
    tmp_path: Path, *, tamper: bool = False, extra: tuple[str, ...] = ()
) -> bytes:
    """A release ZIP: a large unrelated member, then one real undeclared bundle."""
    _manifest, step = export_features.bundle_paths(STEM, tmp_path)
    step.parent.mkdir(parents=True)
    step.write_bytes(
        b"ISO-10303-21;\r\nDATA;\r\n#10 = ADVANCED_FACE('NONE',(#1),#2,.T.);\r\nENDSEC;\r\n"
    )
    manifest = export_features.write_manifest(
        STEM, step, revision=_config.release_revision()
    )
    if tamper:
        step.write_bytes(step.read_bytes() + b"/* drift */")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr(
            "solidworks/ha-harmonic-analyzer.SLDASM", bytes(range(256)) * 4096
        )
        for path in (step, manifest):
            archive.writestr(f"features/{STEM}/{path.name}", path.read_bytes())
        for name in extra:
            # ZipInfo() turns os.sep into "/"; keep the name byte-for-byte.
            info = zipfile.ZipInfo(name)
            info.filename = name
            archive.writestr(info, b"x")
    return buffer.getvalue()


def _serve(monkeypatch, content: bytes) -> list[tuple[int, int]]:
    """Answer range requests from ``content``, recording each byte range."""
    ranges: list[tuple[int, int]] = []

    class _Response(io.BytesIO):
        def __init__(self, data: bytes, start: int) -> None:
            super().__init__(data)
            self.status = 206
            self.headers = {
                "Content-Range": f"bytes {start}-{start + len(data) - 1}/{len(content)}"
            }

    def urlopen(request, timeout=None):
        first, _, last = (
            request.get_header("Range").removeprefix("bytes=").partition("-")
        )
        start, end = int(first), int(last) + 1
        ranges.append((start, end))
        return _Response(content[start:end], start)

    monkeypatch.setattr(fetch_features.urllib.request, "urlopen", urlopen)
    return ranges


def _release(
    monkeypatch,
    tmp_path: Path,
    *,
    tamper: bool = False,
    changed: tuple[str, ...] = (),
    extra: tuple[str, ...] = (),
) -> list:
    ranges = _serve(
        monkeypatch, _release_zip(tmp_path / "published", tamper=tamper, extra=extra)
    )
    monkeypatch.setattr(
        fetch_features,
        "release_asset",
        lambda _tag: ("v99", "https://example.invalid/r.zip"),
    )
    monkeypatch.setattr(fetch_features, "tag_commit", lambda _tag: "a" * 40)
    monkeypatch.setattr(fetch_features, "_git", lambda *_args: "b" * 40)
    monkeypatch.setattr(
        fetch_features,
        "recipe_files",
        lambda _stem: {"cad/scripts/build_ch_amplitude_bar.py": "geometry"},
    )
    monkeypatch.setattr(
        fetch_features, "changed_since", lambda _commit, _files: list(changed)
    )
    return ranges


def test_a_current_bundle_is_fetched_by_range_without_the_rest_of_the_zip(
    tmp_path: Path, monkeypatch
) -> None:
    ranges = _release(monkeypatch, tmp_path)
    out = tmp_path / "out"
    assert fetch_features.main([STEM, "--out", str(out)]) == 0
    manifest, step = export_features.bundle_paths(STEM, out)
    published = export_features.bundle_paths(STEM, tmp_path / "published")
    assert manifest.read_bytes() == published[0].read_bytes()
    assert step.read_bytes() == published[1].read_bytes()
    # The 1 MiB unrelated member is never read.
    assert sum(end - start for start, end in ranges) < 1 << 20


def test_a_stale_bundle_is_reported_and_not_written_unless_accepted(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _release(monkeypatch, tmp_path, changed=("cad/scripts/build_ch_amplitude_bar.py",))
    out = tmp_path / "out"
    assert fetch_features.main([STEM, "--out", str(out)]) == 2
    err = capsys.readouterr().err
    assert "STALE ch_amplitude_bar" in err
    assert (
        "geometry input changed since v99: cad/scripts/build_ch_amplitude_bar.py" in err
    )
    assert not (out / "features").exists()
    assert fetch_features.main([STEM, "--out", str(out), "--accept-stale"]) == 0
    assert export_features.bundle_paths(STEM, out)[0].is_file()


def test_a_bundle_that_does_not_bind_its_step_is_refused(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _release(monkeypatch, tmp_path, tamper=True)
    out = tmp_path / "out"
    assert fetch_features.main([STEM, "--out", str(out), "--accept-stale"]) == 1
    assert "bundle records" in capsys.readouterr().err
    assert not (out / "features").exists()


@pytest.mark.parametrize(
    "member",
    [f"features/{STEM}/..\\..\\x", f"features/{STEM}/C:x", f"features/{STEM}/sub/x"],
)
def test_an_unsafe_or_nested_bundle_member_is_refused(
    tmp_path: Path, monkeypatch, capsys, member: str
) -> None:
    _release(monkeypatch, tmp_path, extra=(member,))
    out = tmp_path / "out"
    assert fetch_features.main([STEM, "--out", str(out), "--accept-stale"]) == 1
    err = capsys.readouterr().err
    assert repr(member) in err or member in err
    assert not (out / "features").exists()


def test_unknown_parts_are_refused() -> None:
    with pytest.raises(SystemExit) as refused:
        fetch_features.main(["fr_vn_lag_screw"])
    assert refused.value.code == 2
