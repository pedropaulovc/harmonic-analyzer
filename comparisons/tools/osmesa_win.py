"""Headless software OpenGL for VTK / pyvista on Windows via Mesa's OSMesa.

This box has no usable GPU OpenGL, so VTK's offscreen render fails. VTK >= 9.4
supports *runtime* OpenGL window selection: with no platform GL it falls back to
an OSMesa (software) render window -- but on Windows that needs ``osmesa.dll`` on
the DLL search path (the bare error is "Failed to initialize OpenGL functions!
osmesa.dll not found"). Kitware's own guidance points at pal1000/mesa-dist-win for
that DLL. Mesa shipped ``osmesa.dll`` (x64, self-contained gallium+llvmpipe build)
through 25.0.x and *removed it in 25.1.0*, so we pin 25.0.7 and fetch it on demand
into a gitignored cache.

Call :func:`enable_offscreen_gl` BEFORE importing ``vtk`` / ``pyvista``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cad" / "scripts"))
import _telemetry  # noqa: E402

# Last Mesa release that still ships a standalone osmesa.dll (removed in 25.1.0).
MESA_VERSION = "25.0.7"
_REL = f"https://github.com/pal1000/mesa-dist-win/releases/download/{MESA_VERSION}"
MESA_7Z_URL = f"{_REL}/mesa3d-{MESA_VERSION}-release-msvc.7z"
# Mesa's 7z uses the BCJ2 filter, which py7zr can't decode -- use the official
# standalone 7zr.exe (handles BCJ2) to extract.
SEVENZIP_URL = "https://www.7-zip.org/a/7zr.exe"

CACHE_DIR = Path(__file__).resolve().parent / ".osmesa-cache"
OSMESA_DLL = CACHE_DIR / "osmesa.dll"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "harmonic-analyzer/osmesa"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)


def ensure_osmesa() -> Path:
    """Return a cached ``osmesa.dll``, downloading + extracting it once if absent."""
    if OSMESA_DLL.exists():
        return OSMESA_DLL
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    archive = CACHE_DIR / "mesa.7z"
    sevenzip = CACHE_DIR / "7zr.exe"
    _telemetry.info(f"[osmesa] fetching Mesa {MESA_VERSION} osmesa.dll (one-time, ~68 MB) ...")
    _download(MESA_7Z_URL, archive)
    _download(SEVENZIP_URL, sevenzip)
    # ``e`` extracts flat, so x64/osmesa.dll lands directly as CACHE_DIR/osmesa.dll.
    subprocess.run(
        [str(sevenzip), "e", str(archive), f"-o{CACHE_DIR}", "-y", "x64/osmesa.dll"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    archive.unlink(missing_ok=True)
    sevenzip.unlink(missing_ok=True)
    if not OSMESA_DLL.exists():
        raise RuntimeError(f"osmesa.dll missing after extracting {MESA_7Z_URL}")
    _telemetry.success(f"[osmesa] cached {OSMESA_DLL}")
    return OSMESA_DLL


def enable_offscreen_gl() -> Path | None:
    """Make VTK select the OSMesa software render window. Windows-only; no-op else.

    Must run BEFORE ``import vtk`` / ``import pyvista``. On non-Windows the platform
    GL (or ``xvfb-run``) serves offscreen rendering, so this is a no-op there.
    Returns the DLL directory it wired up, or ``None`` off Windows.
    """
    if sys.platform != "win32":
        return None
    dll = ensure_osmesa()
    dll_dir = dll.parent
    os.add_dll_directory(str(dll_dir))
    os.environ["PATH"] = str(dll_dir) + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("VTK_DEFAULT_OPENGL_WINDOW", "vtkOSOpenGLRenderWindow")
    return dll_dir


if __name__ == "__main__":
    print(ensure_osmesa())
