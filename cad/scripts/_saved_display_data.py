import mmap
import struct
import zlib
from pathlib import Path


_STREAM_MARKER = bytes.fromhex("140006000800")
_STRING_MARKER = b"\xff\xfe\xff"
_DISPLAY_LISTS = "Contents/DisplayLists"
_MAX_DISPLAY_BYTES = 64 * 1024 * 1024


def _inflate(data: mmap.mmap, start: int, end: int) -> bytes:
    """Bound raw-deflate expansion; require exactly one complete compressed stream."""
    inflater = zlib.decompressobj(-15)
    result = bytearray()
    for offset in range(start, end, 65536):
        chunk = data[offset : min(offset + 65536, end)]
        result.extend(
            inflater.decompress(chunk, _MAX_DISPLAY_BYTES + 1 - len(result))
        )
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


def _assert_flags(data: bytes, stream_offset: int) -> None:
    """Recognize the observed short UTF-16 string form, not arbitrary UTF-16 bytes.

    The encoded length counts UTF-16 code units (not Python characters). A part
    path's uint32 flag is 20 bytes after its encoded end. No undocumented record
    prefix, configuration mapping, or semantics of other nonzero flags is assumed.
    """
    cursor = 0
    records = 0
    while (offset := data.find(_STRING_MARKER, cursor)) != -1:
        context = f"DisplayLists at file offset {stream_offset}, string offset {offset}"
        if offset + 4 > len(data):
            raise ValueError(f"{context}: truncated string length")
        units = data[offset + 3]
        if units == 0xFF:
            raise ValueError(f"{context}: unsupported extended string length")
        end = offset + 4 + 2 * units
        if end > len(data):
            raise ValueError(f"{context}: truncated UTF-16 string")
        try:
            text = data[offset + 4 : end].decode("utf-16le")
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
        flag = struct.unpack_from("<I", data, end + 20)[0]
        if flag == 0:
            raise ValueError(f"{context}: saved display flag=0 for {text!r}")
        records += 1
        cursor = end + 24
    if records == 0:
        raise ValueError(
            f"DisplayLists at file offset {stream_offset}: no recognizable part records"
        )


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

    Success proves nonzero flags on recognized .SLDPRT records only. The observed
    layout cannot distinguish a standalone tagged part-path string from a real
    component record, identify absent configurations, validate .SLDASM records,
    or prove rendering/visibility. Nested tagged strings inside another string
    or stored container payload are not independently interpreted. Unknown
    layouts/extended string lengths must be investigated rather than accepted.
    """
    try:
        with path.open("rb") as source:
            with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
                streams = 0
                for offset, display_data in _display_streams(data):
                    _assert_flags(display_data, offset)
                    streams += 1
                if streams == 0:
                    raise ValueError("no Contents/DisplayLists streams found")
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            f"Saved assembly display-data gate failed for {path}: {exc}. "
            "Regenerate and save the assembly with valid display data before "
            "publishing; investigate the saved native format if parsing fails."
        ) from exc
