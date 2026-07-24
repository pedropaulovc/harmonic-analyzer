# Recipe: assembly drawings

Every assembly drawing is a single ASME B sheet with three model views:
`*Front`, `*Right`, and `*Isometric`. Assembly drawings intentionally use the
SolidWorks/template defaults for view display. They do not add BOMs, balloons,
assembly notes, extra sheets, component isolation, or per-view display-mode
overrides.

The shared implementation is `_assembly_drawing.py`. An assembly entry point is
only responsible for preserving its registry identity, output paths, measured
sheet scale, and precomputed view centers:

```python
SPEC = DRAWINGS_BY_NAME["<stem>_assembly"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)

SHEET_SCALE = (1.0, 4.0)
FRONT_CENTER = (0.070, 0.150)
RIGHT_CENTER = (0.150, 0.150)
ISO_CENTER = (0.225, 0.140)


async def build(adapter):
    return await build_simple_three_view_drawing(
        adapter,
        source=SOURCE,
        outputs=OUTPUTS,
        sheet_scale=SHEET_SCALE,
        front_center=FRONT_CENTER,
        right_center=RIGHT_CENTER,
        iso_center=ISO_CENTER,
        pdf_title="<Title> Assembly Drawing",
    )
```

The builder explicitly pins every view to `SHEET_SCALE`. SolidWorks can
otherwise auto-scale a newly inserted view according to the seat preference,
which makes the saved placement nondeterministic. Explicit scale is placement
determinism, not a visual-style override.

Registry rows, task names, CLI arguments, and output stems remain unchanged.
The normal build command is:

```powershell
uv run python -m doit drawing:<stem>_assembly
```

Offline coverage lives in `test_assembly_drawing_batch_contract.py` plus one
small per-assembly contract file. The batch contract owns the shared invariants;
the per-assembly files pin each registry row, output mapping, scale, and centers.
