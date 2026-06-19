# cad/tools — nameplate engraving toolchain

Offline asset generators for the maker's nameplate engraving (build_nameplate.py).
They turn the book photo into the vendored DXFs the SolidWorks build imports, and
render an off-Windows preview. Not part of the `doit` build; heavy deps stay out
of the build venv (run via `uv run --with ...`).

## Source

The p.71 nameplate macro from the public book *Albert Michelson's Harmonic
Analyzer* (engineerguy.com). The image itself is **not committed** — to
regenerate, extract page 71 of the book PDF, crop the nameplate, and save it as
`cad/assets/nameplate-source.jpg` (git-ignored). The engraving is polished brass
on a blackened field, so it segments by local-adaptive threshold.

## Pipeline

```
nameplate-source.jpg
  │  extract_engraving.py   (segment + de-jag trace -> shapely)
  ▼
nameplate-engraving.pkl     (intermediate, git-ignored)
  │  make_engraving_dxf.py   (-> build plate mm, add pinstripe frame)
  ▼
nameplate-engraving.dxf     (smoothed letters + cartouche, cut into the field)
nameplate-border.dxf        (pinstripe frame, cut on the raised border)
  │  preview_nameplate.py    (CadQuery: same dims as build_nameplate.py)
  ▼
nameplate-engraving-preview.png   (photo-faithful cross-check render)
```

Regenerate everything:

```sh
uv run --with pillow --with numpy --with scipy --with opencv-python-headless \
       --with shapely cad/tools/extract_engraving.py
uv run --with ezdxf --with shapely cad/tools/make_engraving_dxf.py
uv run --with cadquery --with ezdxf --with shapely --with matplotlib \
       --with numpy-stl cad/tools/preview_nameplate.py
```

## Why DXF (not SketchText / a font)

No off-the-shelf font is pixel-identical, and none carries the scroll cartouche
or the superscript-underline `Wᴹ`/`Cᴼ` abbreviations. The lettering is a heavy
early-1900s American grotesque (the ATF Franklin/News Gothic lineage, period- and
place-correct for Gaertner of Chicago); tracing the real glyphs is strictly more
faithful than any substitute. `build_nameplate.py` imports the DXFs and cuts them.
The plate frame (rounded corners, raised border, pinstripe) is the "accurate
border" — modelled to match the photo.
