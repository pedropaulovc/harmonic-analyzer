"""Behavioral fixtures for the observed saved-native display-data layout."""

import struct
import sys
import zlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))

import _saved_display_data as gate  # noqa: E402


MARKER = bytes.fromhex("140006000800")
DISPLAY_LISTS = "Contents/DisplayLists"


def _deflate(data: bytes) -> bytes:
    compressor = zlib.compressobj(wbits=-15)
    return compressor.compress(data) + compressor.flush()


def _envelope(
    payload: bytes, name: str = DISPLAY_LISTS, checksum: int = 0, expanded_size: int = 0
) -> bytes:
    encoded = name.encode("latin1")
    swapped = bytes(((b << 4) & 0xF0) | (b >> 4) for b in encoded)
    return (
        MARKER
        + b"\x00" * 4
        + struct.pack("<4I", checksum, len(payload), expanded_size, len(swapped))
        + swapped
        + payload
    )


def _stream(data: bytes, name: str = DISPLAY_LISTS) -> bytes:
    return _envelope(_deflate(data), name, zlib.crc32(data), len(data))


def _string(text: str) -> bytes:
    """An MFC CArchive Unicode CString: marker, then AfxWriteStringLength."""
    encoded = text.encode("utf-16le")
    units = len(encoded) // 2
    if units < 0xFF:
        length = bytes([units])
    elif units < 0xFFFE:
        length = b"\xff" + struct.pack("<H", units)
    else:
        length = b"\xff\xff\xff" + struct.pack("<I", units)
    return b"\xff\xfe\xff" + length + encoded


def _record(path: str = r"C:\parts\pin.SLDPRT", flag: int = 1) -> bytes:
    return _string(path) + b"\x00" * 8 + struct.pack("<IdI", 6, 1000.0, flag)


def _save(tmp_path: Path, data: bytes) -> Path:
    path = tmp_path / "saved.SLDASM"
    path.write_bytes(data)
    return path


def _reject(
    tmp_path: Path, data: bytes, message: str, *, incomplete: bool = False
) -> None:
    path = _save(tmp_path, data)
    with pytest.raises(RuntimeError, match=message) as failure:
        gate.assert_saved_display_data(path)
    expected = gate.IncompleteSavedDisplayData if incomplete else RuntimeError
    assert type(failure.value) is expected
    assert str(path) in str(failure.value)
    assert path.read_bytes() == data


def test_accepts_observed_visible_flag_without_modifying_file(tmp_path):
    data = _stream(_record())
    path = _save(tmp_path, data)
    assert gate.assert_saved_display_data(path) is None
    assert path.read_bytes() == data


@pytest.mark.parametrize("flag", [2, 0xFFFFFFFF])
def test_unsupported_flags_fail_closed(tmp_path, flag):
    _reject(tmp_path, _stream(_record(flag=flag)), "unsupported display flag")


@pytest.mark.parametrize("prefix_offset", [0, 8])
def test_unsupported_record_prefix_fails_closed(tmp_path, prefix_offset):
    data = bytearray(_record())
    end = len(_string(r"C:\parts\pin.SLDPRT"))
    data[end + prefix_offset] = 7
    _reject(tmp_path, _stream(bytes(data)), "unsupported part record prefix")


def test_legitimate_zero_flag_subassembly_is_excluded(tmp_path):
    data = _record(r"C:\parts\frame.SLDASM", 0) + _record()
    gate.assert_saved_display_data(_save(tmp_path, _stream(data)))


def test_reports_hidden_component_path(tmp_path):
    _reject(tmp_path, _stream(_record(flag=0)), r"flag=0.*pin\.SLDPRT", incomplete=True)


@pytest.mark.parametrize("bad_first", [True, False])
def test_inspects_every_display_stream_not_just_largest(tmp_path, bad_first):
    good = _stream(_record() * 10)
    bad = _stream(_record(r"C:\parts\hidden.SLDPRT", 0))
    data = bad + good if bad_first else good + bad
    _reject(tmp_path, data, r"flag=0.*hidden\.SLDPRT", incomplete=True)


def test_inspects_every_component_record(tmp_path):
    data = _record() + _record(r"C:\parts\other.sldprt", 0)
    _reject(tmp_path, _stream(data), r"flag=0.*other\.sldprt", incomplete=True)


@pytest.mark.parametrize("name", [r"C:\部品\轴.SLDPRT", r"C:\parts\gear-🔧.sldprt"])
def test_unicode_paths_count_utf16_units_not_python_characters(tmp_path, name):
    gate.assert_saved_display_data(_save(tmp_path, _stream(_record(name))))
    _reject(tmp_path, _stream(_record(name, 0)), "flag=0", incomplete=True)


@pytest.mark.parametrize(
    "data", [b"", b"not a native container", _stream(_record(), "Other")]
)
def test_missing_display_streams_fail_closed(tmp_path, data):
    _reject(tmp_path, data, "display-data gate failed")


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"arbitrary content",
        _string("not a part"),
        _record().replace(b"\xff\xfe\xff", b"\x00\x00\x00"),
    ],
)
def test_missing_component_records_fail_closed(tmp_path, data):
    _reject(tmp_path, _stream(data), "no recognizable part records")


def test_an_empty_secondary_display_stream_is_not_ignored(tmp_path):
    _reject(tmp_path, _stream(_record()) + _stream(b""), "no recognizable part records")


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (MARKER, "truncated stream header"),
        (MARKER + b"\x00" * 20, "invalid stream name length"),
        (_stream(_record())[:-1], "truncated or empty stream"),
        (_envelope(b""), "truncated or empty stream"),
        (_envelope(b"invalid deflate"), "Contents/DisplayLists"),
        (_envelope(_deflate(_record())[:-1]), "truncated raw-deflate"),
        (_envelope(_deflate(_record()) + b"trailing"), "trailing compressed data"),
        (_envelope(_deflate(_record()) * 2), "trailing compressed data"),
        (_envelope(_deflate(_record()), "\x00"), "invalid stream name"),
    ],
)
def test_malformed_container_and_compression_fail_closed(tmp_path, data, message):
    _reject(tmp_path, data, message)


def test_damaged_secondary_stream_is_not_ignored(tmp_path):
    _reject(
        tmp_path, _stream(_record()) + _envelope(b"invalid"), "Contents/DisplayLists"
    )


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"\xff\xfe\xff", "truncated string length"),
        (b"\xff\xfe\xff\xff", "truncated string length"),
        (b"\xff\xfe\xff\xff\x01", "truncated string length"),
        (b"\xff\xfe\xff\xff\xff\xff\x01\x00", "truncated string length"),
        (b"\xff\xfe\xff\xff\xff\xff" + b"\xff" * 4, "unsupported 64-bit string length"),
        (b"\xff\xfe\xff\xff\xfe\xff\x01x\x00", "repeated Unicode string tag"),
        (
            b"\xff\xfe\xff\xff" + struct.pack("<H", 300) + b"x\x00" * 299,
            "truncated UTF-16 string",
        ),
        (b"\xff\xfe\xff\x05x\x00", "truncated UTF-16 string"),
        (b"\xff\xfe\xff\x01\x00\xd8", "invalid UTF-16 string"),
        (_string("pin.SLDPRT") + b"\x00" * 23, "truncated display flag"),
        (_record("pin\x00.SLDPRT"), "invalid part path"),
        (
            _string("pin.SLDPRT") + _string("x") + b"\x00" * 24,
            "overlapping string/flag",
        ),
    ],
)
def test_malformed_record_data_fail_closed(tmp_path, data, message):
    _reject(tmp_path, _stream(data), message)


def test_truncated_trailing_string_is_not_ignored_after_good_record(tmp_path):
    _reject(tmp_path, _stream(_record() + b"\xff\xfe\xff"), "truncated string length")


@pytest.mark.parametrize("units", [0xFF, 300, 0xFFFE, 0xFFFF, 70000])
def test_long_part_paths_use_the_mfc_word_or_dword_length(tmp_path, units):
    path = "C:\\" + "p" * (units - len("C:\\.SLDPRT")) + ".SLDPRT"
    assert len(path) == units
    gate.assert_saved_display_data(_save(tmp_path, _stream(_record(path))))
    _reject(
        tmp_path, _stream(_record(path, 0)), r"flag=0.*pppp\.SLDPRT", incomplete=True
    )


def test_long_face_identity_record_is_skipped_whole(tmp_path):
    # Run 23 (#1905): round-ended V strokes give an edge many faces, so its
    # identity record outgrows the BYTE length form.
    ids = "".join(f"moEndFace3IntSurfIdRep_c,176,1,{k},0, \n" for k in range(12))
    assert len(ids) > 0xFF
    gate.assert_saved_display_data(_save(tmp_path, _stream(_string(ids) + _record())))
    _reject(
        tmp_path, _stream(_string(ids) + _record(flag=0)), "flag=0", incomplete=True
    )


def test_untagged_utf16_part_path_is_not_a_component_record(tmp_path):
    _reject(
        tmp_path,
        _stream("pin.SLDPRT".encode("utf-16le") + b"\x00" * 24),
        "no recognizable part records",
    )


def test_nested_hidden_record_fails_closed(tmp_path):
    inner = _record("hidden.SLDPRT", 0)
    outer = b"\xff\xfe\xff" + bytes([len(inner) // 2]) + inner
    _reject(tmp_path, _stream(outer + _record()), "nested or overlapping")


def test_marker_crossing_from_header_into_text_fails_closed(tmp_path):
    # codjiflo #1964: a record starting inside a BYTE-length header must not be
    # skipped as the outer string's text.
    outer = (b"\xff\xfe" + _record("hidden000.SLDPRT", 0)).ljust(512, b"\x00")
    _reject(tmp_path, _stream(outer + _record()), "nested or overlapping")


def test_tag_bytes_wholly_inside_a_dword_length_header_are_not_nested(tmp_path):
    header = _string("p" * 0xFFFE)[:10]
    assert (
        header.find(b"\xff\xfe\xff", 1) == 5
    )  # the header's own WORD 0xFFFF + DWORD 0xFFFE
    gate.assert_saved_display_data(
        _save(tmp_path, _stream(_string("p" * 0xFFFE) + _record()))
    )


def test_container_markers_inside_stored_payload_are_not_entries(tmp_path):
    unrelated = _envelope(MARKER + b"damaged nested header", "Other")
    gate.assert_saved_display_data(_save(tmp_path, unrelated + _stream(_record())))


def test_expansion_limit_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "_MAX_DISPLAY_BYTES", 16)
    _reject(tmp_path, _stream(_record()), "inspection limit")


def test_unreadable_saved_file_fails_closed(tmp_path):
    path = tmp_path / "missing.SLDASM"
    with pytest.raises(RuntimeError) as failure:
        gate.assert_saved_display_data(path)
    assert str(path) in str(failure.value)


@pytest.mark.parametrize("field", [10, 18])
def test_relevant_checksum_and_expanded_size_are_validated(tmp_path, field):
    data = bytearray(_stream(_record()))
    value = struct.unpack_from("<I", data, field)[0]
    struct.pack_into("<I", data, field, value + 1)
    _reject(tmp_path, bytes(data), "mismatch")


def _decoy(size: int = 450, remainder: int = 0) -> bytes:
    name = bytes(((b << 4) & 0xF0) | (b >> 4) for b in DISPLAY_LISTS.encode("latin1"))
    return (
        MARKER
        + b"\x00" * 4
        + struct.pack(
            "<4I", 4 * size + remainder, size, 2 * size + remainder // 2, len(name)
        )
        + name
        + b"observed nondeflate decoy filler"
    )


@pytest.mark.parametrize(("size", "remainder"), [(450, 0), (232, 2)])
def test_observed_decoy_envelopes_do_not_hide_true_display_stream(
    tmp_path, size, remainder
):
    data = _decoy(size, remainder) + _stream(_record() * 20) + b"\x00" * size
    gate.assert_saved_display_data(_save(tmp_path, data))


def test_observed_decoy_does_not_hide_corrupt_true_display_stream(tmp_path):
    data = _decoy() + _envelope(b"invalid deflate" * 100)
    _reject(tmp_path, data, "Contents/DisplayLists")


def test_arithmetic_header_without_nested_marker_is_not_silently_skipped(tmp_path):
    name = DISPLAY_LISTS.encode("latin1")
    swapped = bytes(((b << 4) & 0xF0) | (b >> 4) for b in name)
    data = MARKER + b"\x00" * 4 + struct.pack("<4I", 1800, 450, 900, len(name))
    data += swapped + b"invalid deflate".ljust(450, b"\x00")
    _reject(tmp_path, data, "Contents/DisplayLists")


def _directory_copy(local: bytes, reference: int = 0) -> bytes:
    name_size = struct.unpack_from("<I", local, 22)[0]
    return (
        b"\x00\x00"
        + local[:26]
        + b"\x00" * 10
        + struct.pack("<I", reference)
        + local[26 : 26 + name_size]
    )


def test_verified_directory_reference_is_not_another_stored_stream(tmp_path):
    local = _stream(_record())
    data = b"\x00" * 12 + local + _directory_copy(local)
    gate.assert_saved_display_data(_save(tmp_path, data))


def test_unverified_directory_like_data_does_not_hide_damage(tmp_path):
    local = _stream(_record())
    data = b"\x00" * 12 + local + _directory_copy(local, reference=999999)
    _reject(tmp_path, data, "display-data gate failed")


@pytest.mark.parametrize("later_stream", [False, True])
@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (_record("unknown.SLDPRT", 2), "unsupported display flag"),
        (b"\xff\xfe\xff", "truncated string length"),
    ],
)
def test_zero_does_not_mask_unsupported_or_malformed_later_data(
    tmp_path, later_stream, bad, message
):
    zero = _record(flag=0)
    data = _stream(zero) + _stream(bad) if later_stream else _stream(zero + bad)
    _reject(tmp_path, data, message)


def test_zero_does_not_mask_a_malformed_later_container(tmp_path):
    _reject(tmp_path, _stream(_record(flag=0)) + MARKER, "truncated stream header")
