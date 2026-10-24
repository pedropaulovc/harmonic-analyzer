import mmap
import struct
import zlib
from pathlib import Path


_STREAM_MARKER = bytes.fromhex("140006000800")
_STRING_MARKER = b"\xff\xfe\xff"
_DISPLAY_LISTS = "Contents/DisplayLists"
_MAX_DISPLAY_BYTES = 64 * 1024 * 1024


class IncompleteSavedDisplayData(RuntimeError):
    """Supported native records have zero flags; the entire parsed layout is valid."""


def _inflate(data: mmap.mmap, start: int, end: int) -> bytes:
    """Bound raw-deflate expansion; require exactly one complete compressed stream."""
    inflater = zlib.decompressobj(-15)
    result = bytearray()
    for offset in range(start, end, 65536):
        chunk = data[offset : min(offset + 65536, end)]
        result.extend(inflater.decompress(chunk, _MAX_DISPLAY_BYTES + 1 - len(result)))
        if len(result) > _MAX_DISPLAY_BYTES or inflater.unconsumed_tail:
            raise ValueError("DisplayLists exceeds the 64 MiB inspection limit")
        if inflater.unused_data or (inflater.eof and offset + len(chunk) != end):
            raise ValueError("DisplayLists has trailing compressed data")
    if not inflater.eof:
        raise ValueError("DisplayLists has truncated raw-deflate data")
    return bytes(result)


def _display_streams(data: mmap.mmap):
    """Read only the marker/header/name envelope observed in swfile.py.

    Native v37/v40 establish CRC32, compressed size, expanded size, and name
    length at marker+10. Non-stream decoys have fields (K, K//4, K//2),
    with another marker inside the claimed payload. Only that observed
    arithmetic signature is skipped. Skip whole true payloads so embedded
    markers cannot masquerade as container entries.
    Native v37 ends with directory copies: names begin at marker+40 and the
    uint32 at +36 points 12 bytes before the matching earlier local marker.
    Stop only after verifying that exact header/name reference; directory
    metadata (including its decoys) is not a second set of stored payloads.
    """
    cursor = 0
    seen: dict[int, tuple[tuple[int, ...], bytes]] = {}
    while (offset := data.find(_STREAM_MARKER, cursor)) != -1:
        if offset + 26 > len(data):
            raise ValueError(f"truncated stream header at file offset {offset}")
        checksum, size, expanded_size, name_size = struct.unpack_from(
            "<4I", data, offset + 10
        )
        if not 0 < name_size < 300:
            raise ValueError(f"invalid stream name length at file offset {offset}")
        fields = (checksum, size, expanded_size, name_size)
        if offset >= 2 and offset + 40 + name_size <= len(data):
            reference = struct.unpack_from("<I", data, offset + 36)[0] + 12
            directory_name = data[offset + 40 : offset + 40 + name_size]
            if (
                data[offset - 2 : offset] == b"\x00\x00"
                and data[offset + 26 : offset + 30] == b"\x00" * 4
                and seen.get(reference) == (fields, directory_name)
            ):
                return
        start = offset + 26 + name_size
        end = start + size
        if start > len(data) or end > len(data) or size == 0:
            raise ValueError(f"truncated or empty stream at file offset {offset}")
        encoded = data[offset + 26 : start]
        name = bytes(((b << 4) & 0xF0) | (b >> 4) for b in encoded).decode("latin1")
        if not name.isprintable():
            raise ValueError(f"invalid stream name at file offset {offset}")
        if checksum // 4 == size and checksum // 2 == expanded_size:
            nested = data.find(_STREAM_MARKER, start, end)
            if nested != -1:
                cursor = nested
                continue
        seen[offset] = (fields, encoded)
        cursor = end
        if name == _DISPLAY_LISTS:
            try:
                inflated = _inflate(data, start, end)
                if len(inflated) != expanded_size:
                    raise ValueError("DisplayLists expanded-size mismatch")
                if zlib.crc32(inflated) != checksum:
                    raise ValueError("DisplayLists CRC32 mismatch")
                yield offset, inflated
            except (ValueError, zlib.error) as exc:
                raise ValueError(f"{name} at file offset {offset}: {exc}") from exc


def _string_span(data: bytes, offset: int, context: str) -> tuple[int, int]:
    """Text start and UTF-16 unit count of the CString whose marker is at offset.

    The marker is MFC's BYTE 0xFF + WORD 0xFFFE Unicode tag; the length then
    follows ``AfxWriteStringLength``: a BYTE below 0xFF; else 0xFF and a WORD
    below 0xFFFE; else 0xFF, WORD 0xFFFF and a DWORD. Face-identity records
    longer than 254 units use the WORD form. A second Unicode tag (WORD
    0xFFFE) and the 64-bit escape are not written after a tag, so both are
    refused. A DWORD length whose own bytes spell the tag is refused by the
    caller's overlap check: fail closed rather than guess which tag is real.
    """
    lengths = ((offset + 3, "<B"), (offset + 4, "<H"), (offset + 6, "<I"))
    for (at, layout), escape in zip(lengths, (0xFF, 0xFFFF, 0xFFFFFFFF), strict=True):
        if at + struct.calcsize(layout) > len(data):
            raise ValueError(f"{context}: truncated string length")
        units = struct.unpack_from(layout, data, at)[0]
        if layout == "<H" and units == 0xFFFE:
            raise ValueError(f"{context}: repeated Unicode string tag")
        if units != escape:
            return at + struct.calcsize(layout), units
    raise ValueError(f"{context}: unsupported 64-bit string length")


def _assert_flags(data: bytes, stream_offset: int) -> str | None:
    """Validate every observed record, returning the first supported zero flag.

    The encoded length counts UTF-16 code units (not Python characters). A part
    path's uint32 flag is 20 bytes after its encoded end. Native v37/v40 part
    records have eight zero bytes, uint32 6, eight uninterpreted bytes, then a
    flag of 0 or 1. Refuse unsupported prefixes/flags rather than infer semantics.
    """
    cursor = 0
    records = 0
    incomplete = None
    while (offset := data.find(_STRING_MARKER, cursor)) != -1:
        context = f"DisplayLists at file offset {stream_offset}, string offset {offset}"
        start, units = _string_span(data, offset, context)
        end = start + 2 * units
        if end > len(data):
            raise ValueError(f"{context}: truncated UTF-16 string")
        # Any tag starting after this one and before its end overlaps it,
        # including one that crosses the end or lies in a long-form header.
        if data.find(_STRING_MARKER, offset + 1, end + len(_STRING_MARKER) - 1) != -1:
            raise ValueError(f"{context}: nested or overlapping serialized string")
        try:
            text = data[start:end].decode("utf-16le")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{context}: invalid UTF-16 string") from exc
        cursor = end
        if not text.upper().endswith(".SLDPRT"):
            continue
        if not text.isprintable():
            raise ValueError(f"{context}: invalid part path {text!r}")
        if end + 24 > len(data):
            raise ValueError(f"{context}: truncated display flag for {text!r}")
        if data.find(_STRING_MARKER, end, end + 24) != -1:
            raise ValueError(f"{context}: overlapping string/flag data for {text!r}")
        if (
            data[end : end + 8] != b"\x00" * 8
            or struct.unpack_from("<I", data, end + 8)[0] != 6
        ):
            raise ValueError(f"{context}: unsupported part record prefix for {text!r}")
        flag = struct.unpack_from("<I", data, end + 20)[0]
        if flag not in (0, 1):
            raise ValueError(f"{context}: unsupported display flag={flag} for {text!r}")
        if flag == 0 and incomplete is None:
            incomplete = f"{context}: saved display flag=0 for {text!r}"
        records += 1
        cursor = end + 24
    if records == 0:
        raise ValueError(
            f"DisplayLists at file offset {stream_offset}: no recognizable part records"
        )
    return incomplete


def assert_saved_display_data(path: Path) -> None:
    """Fail closed on missing, unreadable, malformed, or zero-flag saved display data.

    This read-only gate implements the empirically observed swfile.py modern
    container layout, not a documented SolidWorks format. Every exact
    Contents/DisplayLists stream is inspected, not merely the largest. The
    64 MiB per-stream expansion bound refuses unusually large display lists.
    Observed decoy envelopes are excluded by their arithmetic header signature
    and overlapping next marker. This empirical discriminator is not a formal
    guarantee against damaged data sharing that signature. Inspection ends at
    a verified directory-copy reference; the remaining footer is not audited.

    Success proves flag=1 on recognized .SLDPRT records only. A standalone tagged
    part-path string with the same observed record prefix remains indistinguishable
    from a component record; absent configurations and rendering are not proven.
    Native good v37 saves contain flag=0 .SLDASM records, so those are excluded.
    The gate does not validate nested assembly containers or their visibility.
    Nested/overlapping serialized strings and unknown layouts/extended lengths
    are refused. Markers inside stored container payloads are not separate entries.
    Supported zero flags raise ``IncompleteSavedDisplayData`` only after every
    stream and record passes structural validation. Both zero flags and malformed
    data fail publication; neither authorizes an automatic repair save.
    """
    try:
        incomplete = None
        with path.open("rb") as source:
            with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
                streams = 0
                for offset, display_data in _display_streams(data):
                    missing = _assert_flags(display_data, offset)
                    if incomplete is None:
                        incomplete = missing
                    streams += 1
                if streams == 0:
                    raise ValueError("no Contents/DisplayLists streams found")
        if incomplete is not None:
            raise IncompleteSavedDisplayData(
                f"Saved assembly display-data gate failed for {path}: {incomplete}. "
                "Regenerate and save the assembly with valid display data before "
                "publishing."
            )
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            f"Saved assembly display-data gate failed for {path}: {exc}. "
            "Regenerate and save the assembly with valid display data before "
            "publishing; investigate the saved native format if parsing fails."
        ) from exc
