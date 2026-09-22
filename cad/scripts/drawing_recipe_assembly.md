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

`draw_summing_assembly.py` uses four landscape ASME B sheets: collapsed
assembled Front/Right HLR views with a standard Shaded With Edges isometric,
the builder-owned persisted `SUMMING_EXPLODED` presentation with a native
seven-row BOM and one balloon per row, ordered assembly/setup instructions
with functional checks, and an associative hanger-axis section/detail carrying
the actual MHA-037 tap-mouth to MHA-119 finished-tip fit dimension. The BOM
contains the ten direct instances only.
Top-frame MHA-077, its MHA-118 gooseneck set screw, and the twenty channel
MHA-090/MHA-011 spring connections are identified as external installation
interfaces rather than duplicated BOM occurrences.

MHA-077 retains the native final hanger-hole size, but the released top-frame
print carries no independent hanger X/Z requirement. Fit MHA-073 between the
actual MHA-037 pair first, preserve both knife contacts and free axial rock,
then align its counter-boss tap axis with the MHA-077 guide-bore axis in one
plane normal to the knife axis. Transfer the actual MHA-037 tap centres, remove
the fitted set, and only then pilot and drill the MHA-077 clearance holes;
never enter the mount taps or recenter to CAD marks. Retain the identified
front/rear MHA-077/MHA-037 set as non-interchangeable.

Each identified MHA-119/MHA-131 station is fitted from its actual MHA-077
thickness, assigned-washer thickness, and positive mount-to-frame clearance;
the MHA-119 under-head length remains a reference, not a fixed cut acceptance.
The fourth sheet keeps the engagement target and its printed general `.XX`
window on the native actual-edge measurement. It then requires the finished
tip to remain within the actual MHA-037 complete-thread depth, positive
complete-thread overlap, full seating, positive clearance, and free rock
without axial rub or bottoming. The assembly source separately gates its
nominal root-cone, drill-shoulder, and runout envelope. Neither route claims a
load rating or invents a minimum number of turns.

The released default clamps the MHA-019 upper eye between the MHA-032 retainer
head and arm end. Loosen that screw only for spring access, then retighten it
without threadlocker; its open travel is an installation allowance, not a saved
stand-off or a second assembly configuration.

The source assembly remains saved collapsed in `Default`. Its `lever_rock` DOF
stays genuinely free, and the package identifies the saved pose as the neutral
reference; it does not invent parked or engaged assembly configurations.
Final balance is established with the installed springs by sliding MHA-032 in
the MHA-077 guide before tightening MHA-118, rather than treating the computed
CAD spring placement as a fitter tolerance.

Use `uv run python -m doit drawing:summing_assembly` to regenerate the package.
Inspect all four pages and complete the blind machinist review before release.
