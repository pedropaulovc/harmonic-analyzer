# Recipe: assembly drawings

## Legacy three-view sheets

The shared `_assembly_drawing.py` recipe produces one ASME B sheet with
`*Front`, `*Right`, and `*Isometric` views. These overview sheets are not complete
manufacturing assembly packages. New or recreated packages must follow
[`drawing-simplicity-policy.md`](../docs/drawing-simplicity-policy.md), including
the assembly information needed to build and inspect the mechanism.

`_drawing_common.finalize_drawing` enforces the project-wide isometric contract:
Shaded With Edges, precision geometry (draft/faceted quality off), and
high-quality cosmetic threads.

An entry point using the legacy recipe supplies its registry identity, output
paths, sheet scale, and view centers:

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

Offline coverage for the remaining simple recipes lives in
`test_assembly_drawing_batch_contract.py` plus one small per-assembly contract
file. The batch contract owns their shared invariants; each per-assembly file
pins its registry row, output mapping, scale, and centers.

## Frame package

`draw_frame_assembly.py` uses three ASME B sheets: landscape working views,
portrait exploded view with native BOM and balloons, and landscape assembly
instructions. The registry includes both orientation templates as dependencies.
Finalization checks each native sheet and each exported PDF page against its
declared layout.

The frame builder owns the persisted `FRAME_EXPLODED` presentation and saves the
assembly collapsed. The drawing consumes that presentation without authoring
source features. Explode validation checks component movement in world
coordinates; a view's exploded flag alone does not establish correct separation.
The drawing lifecycle also checks that the source assembly remains unchanged.

Use `uv run python -m doit drawing:frame_assembly` to regenerate the package.
Inspect every page and complete the blind machinist review before release.

## Summing package

`draw_summing_assembly.py` uses three landscape ASME B sheets: collapsed
assembled Front/Right HLR views with a standard Shaded With Edges isometric,
the builder-owned persisted `SUMMING_EXPLODED` presentation with a native
seven-row BOM and one balloon per row, and ordered assembly/setup instructions
with functional checks. The BOM contains the ten direct instances only.
Top-frame MHA-077, its MHA-118 gooseneck set screw, and the twenty channel
MHA-090/MHA-011 spring connections are identified as external installation
interfaces rather than duplicated BOM occurrences.

The source assembly remains saved collapsed in `Default`. Its `lever_rock` DOF
stays genuinely free, and the package identifies the saved pose as the neutral
reference; it does not invent parked or engaged assembly configurations.
Final balance is established with the installed springs by sliding MHA-032 in
the MHA-077 guide before tightening MHA-118, rather than treating the computed
CAD spring placement as a fitter tolerance.

Use `uv run python -m doit drawing:summing_assembly` to regenerate the package.
Inspect all three pages and complete the blind machinist review before release.
