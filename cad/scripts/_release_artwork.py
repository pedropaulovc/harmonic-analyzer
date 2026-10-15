"""Where artwork a drawing note names ships in the release bundle.

Pure data, stdlib only. A drawing spec prints each artwork file through
``bundle_path``; ``cut_release`` finds those paths in every drawing's notes
with ``NOTED_ARTWORK`` and copies each tracked file there, so the path on the
sheet is the path in the zip.
"""

from __future__ import annotations

import re

# Beside the drawing PDFs: ``cut_release.stage_drawings`` puts each sheet's
# ``pdf`` output in the bundle directory of the same name.
ARTWORK_DIR = "pdf"

# The bundle directory, a slash, then a DXF file name. Matched without regard
# to case so that a mis-cased directory is caught and refused rather than
# silently left out of the bundle.
NOTED_ARTWORK = re.compile(
    rf"(?<![\w./\\-])({re.escape(ARTWORK_DIR)})/([\w-]+\.dxf)(?![\w.-])",
    re.IGNORECASE,
)


def bundle_path(file_name: str) -> str:
    """The bundle-relative path a note prints for the artwork ``file_name``."""
    path = f"{ARTWORK_DIR}/{file_name}"
    if not NOTED_ARTWORK.fullmatch(path):
        raise ValueError(f"not a noted-artwork file name: {file_name!r}")
    return path
