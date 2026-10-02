"""Regenerate every tracked README picture from one CAD artifact tree.

Use a versioned release to keep the README tied to the published geometry::

    uv run python cad/scripts/trim_renders.py --release-root cad/out/release/harmonic-analyzer-v38

``--output-dir`` prepares the complete image set outside the tracked tree. The
publisher uses the same generator before tagging, then installs those prepared
images only after publication succeeds, alongside the next-revision bump.
Explicit refreshes stage first too, so missing inputs and failed renderers leave
tracked pictures unchanged. Installation replaces files individually; a failed
replacement reports which images were already installed.

Assembly previews are cropped deterministically; single-sheet drawing PNGs are
copied unchanged; selected PDF sheets are rasterized at 300 dpi. The display-pose
GLB render preserves the meshprobe recipe in ``cad/docs/images/README.md`` and
requires Blender >= 5.2 with a working graphics device. No SolidWorks seat is
used. The fixed photograph and unrelated ``output.png`` are never touched.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from shutil import copyfile, rmtree
from pathlib import Path

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _telemetry  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DOCS_IMAGES = ROOT / "cad" / "docs" / "images"
PAD = 24
THRESHOLD = 30

README_RENDERS = {
    "harmonic-analyzer": "hero.png",
    "frame": "frame.png",
    "drive-train": "drive-train.png",
    "channel": "channel.png",
    "summing": "summing.png",
    "magnifier": "magnifier.png",
    "pen": "pen.png",
    "paper-drive": "paper-drive.png",
}

README_DRAWINGS = {
    "rocker-arm-support": "rocker-arm-support-drawing.png",
    "pinion-arbor": "pinion-arbor-drawing.png",
}

README_PDF_SHEETS = {
    "drive-train-assembly-sheet-4.png": ("drive-train-assembly.pdf", 3),
    "frame-assembly-sheet-3.png": ("frame-assembly.pdf", 2),
}
DISPLAY_POSE_NAME = "cad-model-display-pose.png"
README_IMAGE_NAMES = (
    *README_RENDERS.values(),
    *README_DRAWINGS.values(),
    *README_PDF_SHEETS,
    DISPLAY_POSE_NAME,
)
PDF_DPI = 300


def trim(src: Path, dst: Path) -> str:
    """Crop ``src`` to its content (vs the corner background colour) + PAD."""
    with Image.open(src) as source:
        img = source.convert("RGB")
    background = Image.new("RGB", img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, background).convert("L")
    bbox = diff.point(lambda p: 255 if p > THRESHOLD else 0).getbbox()  # type: ignore[operator]  # PIL stubs type ImagePointTransform too broadly
    if bbox is None:
        raise ValueError(f"{src}: no content found above threshold")
    left, top, right, bottom = bbox
    bbox = (
        max(0, left - PAD),
        max(0, top - PAD),
        min(img.width, right + PAD),
        min(img.height, bottom + PAD),
    )
    cropped = img.crop(bbox)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(dst)
    return f"{dst}: {img.size} -> {cropped.size}"


def render_pdf_sheet(src: Path, dst: Path, page_index: int) -> None:
    """Rasterize one zero-based PDF page, not the build-owned contact sheet."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(src))
    try:
        if not 0 <= page_index < len(document):
            raise ValueError(
                f"{src}: required sheet {page_index + 1} is missing "
                f"(PDF has {len(document)} sheets)"
            )
        page = document[page_index]
        try:
            bitmap = page.render(scale=PDF_DPI / 72.0)
            try:
                image = bitmap.to_pil()
                try:
                    image.save(dst, dpi=(PDF_DPI, PDF_DPI))
                finally:
                    image.close()
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        document.close()


def validate_display_pose(path: Path) -> None:
    """Reject a blank or edge-clipped machine instead of publishing that asset."""
    with Image.open(path) as source:
        image = source.convert("RGB")
    background = Image.new("RGB", image.size, "white")
    difference = ImageChops.difference(image, background).convert("L")
    bounds = difference.point(lambda p: 255 if p > THRESHOLD else 0).getbbox()
    if bounds is None:
        raise ValueError(f"{path}: display-pose render contains no machine")
    left, top, right, bottom = bounds
    if left == 0 or top == 0 or right == image.width or bottom == image.height:
        raise ValueError(
            f"{path}: display-pose machine touches an image edge; "
            "the renderer framing must be recalibrated before publication"
        )


def render_display_pose(src: Path, dst: Path, *, blender: str | None = None) -> None:
    """Render the documented photo-matched pose using the pinned meshprobe CLI."""
    if importlib.util.find_spec("meshprobe") is None:
        raise RuntimeError("README display render requires meshprobe; run uv sync")

    # A private workspace owns its daemon/session. Keep it on cleanup failure
    # and report how to recover, rather than masking the original render error.
    workspace = Path(tempfile.mkdtemp(prefix="readme-meshprobe-"))
    daemon_metadata = workspace / ".meshprobe" / "daemon.json"
    command = [
        sys.executable, "-m", "meshprobe.cli",
        "--workspace", str(workspace), "--session", "readme-images",
    ]

    def run(*args: str) -> str:
        try:
            result = subprocess.run(
                [*command, *args],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"README meshprobe {' '.join(args)} failed:\n{exc.stdout}"
            ) from exc
        return result.stdout

    open_args = ["open", str(src.resolve())]
    if blender is not None:
        open_args.extend(("--blender", blender))
    opened = False
    primary_error: BaseException | None = None
    try:
        run(*open_args)
        opened = True
        run("illumination-set", "high_key", "--background-srgb", "1", "1", "1")
        # meshprobe 1.4 frames per-component corners more tightly than the 1.2
        # recipe. This margin was calibrated against the original image, with
        # azimuth/elevation, lighting, projection, and rendering unchanged.
        # --all and explicit snapshot IDs use the same per-component corners.
        run(
            "view-frame", "--all",
            "--azimuth", "95", "--elevation", "8",
            "--margin", "0.71", "--aspect-ratio", "0.3198",
        )
        run(
            "render-image", "--output", str(dst.resolve()),
            "--width", "1180", "--height", "3690",
            "--style", "screen_edges", "--samples", "128",
        )
        if not dst.is_file():
            raise FileNotFoundError(
                f"meshprobe did not write the required README render: {dst}"
            )
        validate_display_pose(dst)
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        daemon_pid: object = "unknown"
        try:
            if daemon_metadata.is_file():
                daemon_pid = json.loads(
                    daemon_metadata.read_text(encoding="utf-8")
                ).get("pid", "unknown")
        except (OSError, ValueError):
            pass  # PID is diagnostic only; still attempt the owned cleanup.
        try:
            if opened or daemon_metadata.is_file():
                run("close", "--all")
            rmtree(workspace)
        except Exception as exc:
            message = (
                f"README meshprobe cleanup failed for private workspace {workspace}, "
                f"daemon PID {daemon_pid}: {exc}. Recover with "
                f'`uv run meshprobe --workspace "{workspace}" close --all`'
            )
            if primary_error is not None:
                primary_error.add_note(message)
            else:
                raise RuntimeError(message) from exc


def regenerate_readme_images(
    release_root: Path, output_dir: Path, *, blender: str | None = None
) -> None:
    """Prepare the full generated image set in an explicitly supplied directory."""
    release_root = release_root.resolve()
    png = release_root / "png"
    inputs = [
        *(png / name / f"{name}_isometric.png" for name in README_RENDERS),
        *(png / f"{name}_drawing.png" for name in README_DRAWINGS),
        *(release_root / "pdf" / name for name, _ in README_PDF_SHEETS.values()),
        release_root / "gltf" / "harmonic-analyzer.glb",
    ]
    missing = [str(path) for path in inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "required README image sources are missing:\n  " + "\n  ".join(missing)
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, docs_name in README_RENDERS.items():
        _telemetry.info(trim(png / name / f"{name}_isometric.png", output_dir / docs_name))
    for name, docs_name in README_DRAWINGS.items():
        copyfile(png / f"{name}_drawing.png", output_dir / docs_name)
        _telemetry.info(f"{output_dir / docs_name}: copied full drawing sheet")
    for docs_name, (pdf_name, page_index) in README_PDF_SHEETS.items():
        render_pdf_sheet(release_root / "pdf" / pdf_name, output_dir / docs_name, page_index)
        _telemetry.info(f"{output_dir / docs_name}: {pdf_name} sheet {page_index + 1}")
    render_display_pose(
        release_root / "gltf" / "harmonic-analyzer.glb",
        output_dir / DISPLAY_POSE_NAME,
        blender=blender,
    )
    _telemetry.info(f"{output_dir / DISPLAY_POSE_NAME}: rendered matched display pose")


def install_readme_images(prepared_dir: Path, output_dir: Path) -> None:
    """Install a complete prepared set, replacing each destination atomically."""
    for name in README_IMAGE_NAMES:
        source = prepared_dir / name
        if not source.is_file():
            raise FileNotFoundError(f"required prepared README image is missing: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    for name in README_IMAGE_NAMES:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=output_dir, prefix=f".{name}.", suffix=".tmp", delete=False
            ) as target:
                temporary = Path(target.name)
            copyfile(prepared_dir / name, temporary)
            os.replace(temporary, output_dir / name)
            installed.append(name)
        except BaseException as exc:
            if installed:
                exc.add_note(f"partially installed README images: {', '.join(installed)}")
            raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release-root", type=Path, required=True,
        help="pinned release artifact tree containing png/, pdf/, and gltf/",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DOCS_IMAGES,
        help="image destination (default: cad/docs/images); use an untracked directory to prepare",
    )
    parser.add_argument(
        "--blender",
        help="Blender >= 5.2 executable (otherwise meshprobe discovers it, or uses MESHPROBE_BLENDER)",
    )
    options = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="readme-images-") as temporary:
        prepared_dir = Path(temporary)
        regenerate_readme_images(options.release_root, prepared_dir, blender=options.blender)
        install_readme_images(prepared_dir, options.output_dir)
    _telemetry.success(f"Refreshed {len(README_IMAGE_NAMES)} README images in {options.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
