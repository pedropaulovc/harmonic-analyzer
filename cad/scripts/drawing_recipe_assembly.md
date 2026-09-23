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

`draw_summing_assembly.py` ships `MHA-A07` as five landscape ASME B sheets
(`SHEET_NAMES`), each stamped `SHEET n OF 5`:

1. **ASSEMBLED VIEWS** (1:4): collapsed `*Front`/`*Right` HLR views and a
   standard Shaded With Edges isometric, headed as the neutral reference pose.
   The `lever_rock` DOF stays genuinely free: the saved pose is the neutral
   reference, and no parked or engaged configuration exists.
2. **EXPLODED VIEW + BOM** (1:4): the builder-owned persisted
   `SUMMING_EXPLODED` presentation as a Shaded With Edges isometric with the
   native BOM (seven rows, ten direct instances, one balloon per row). The view
   is moved so its balloon ring fits `EXPLODED_RING_REGION`, left of the BOM,
   which sits bottom-right above the title block. The MHA-077 frame, its MHA-118
   gooseneck set screw, and the twenty channel MHA-090/MHA-011 spring
   connections are identified as external installation interfaces rather than
   duplicated BOM occurrences.
3. **ASSEMBLY SEQUENCE** (1:6): a finished-assembly isometric with the ordered
   match-drill and assembly sequence. The MHA-077 hanger holes transfer from the
   actual MHA-037 tap axes (the released top-frame print keeps the native final
   hole size but carries no independent hanger X/Z requirement), never from CAD
   marks.
4. **HANGER FIT + INSPECTION** (1:1 sheet): a hanger-station front parent
   isolated to MHA-037/MHA-131/MHA-119 (1:2) and its hanger-axis section A-A
   (1:2, bolts and washers drawn unsectioned per ASME Y14.3, showing the #10-24
   tip in its tap). Detail B (2:1) is cut from the FRONT parent, where the knife
   bore is a circle: it shows the stud shoulder seated on the MHA-037 boss and
   carries C, the associative seat-to-knife-line depth (shoulder face to the
   bore crown), as a two-place reference. The right note field gives the per-side
   fit (TURN MHA-119 SHOULDER L = T + W + 14.87 - C, 14.87 = casting underside to
   knife line, from `knife_hanger_interface`) and the as-built inspection. Before
   dimensioning, the drawing judges the built joint from the solids
   (`build_summing_assembly.measure_hanger_joint`): shoulder seated on the seat
   plane, full-thread engagement >= 1.5D, tip inside the usable thread, boss and
   shank clear of the casting hole.
5. **CHECKS + SETUP** (1:6): the assembly-only functional checks, the
   neutral/free-rocking setup and the external installation interfaces, with a
   reference isometric under the right notes. The finalizer links title-block
   properties through a view, so no sheet may be notes-only. The sheet is
   appended after sheet 4 so the MHA-119 cross-reference stays valid.

Note blocks stack top-down in the `NOTE_FIELD_*` fields at 3.5 mm text (the ASME
Y14.2 minimum on B size is 3 mm). Each block's rendered `INote.GetExtent` is
gated against its field, and the build ends with `check_drawing_layout` on every
sheet: any overlap, border crossing or leader crossing fails the drawing.

The MHA-119 stud drawing points back here: "FIT SHOULDER TO STACK PER MHA-A07
SHEET 4, HANGER FIT + INSPECTION, DETAIL B."
`test_summing_assembly_drawing.py` pins that sentence to
`build_summing_assembly.DRAWING_NUMBER`, `draw_summing_assembly.SHEET_NAMES[3]`,
and `draw_summing_assembly.HANGER_DETAIL_LABEL`, so renaming any of them fails
the offline suite.

The builder saves the source collapsed in `Default` and owns the
`SUMMING_EXPLODED` presentation; the drawing only consumes it and verifies the
source stays byte-identical. Final balance is established with the installed
springs by sliding MHA-032 in the MHA-077 guide before tightening MHA-118, and
the MHA-032 retainer screw's open travel is a spring-access installation
allowance, not a saved stand-off or a second assembly configuration. The
assembly source separately gates the nominal root-cone, drill-shoulder, and
runout envelope.

Use `uv run python -m doit drawing:summing_assembly` to regenerate the package.
Inspect all four pages and complete the blind machinist review before release.
