# Narration script

The copy shown in the simulator's panel, chapter by chapter. `narration.ts`
holds the structure (crank range, amplitude setting, camera); this file holds
the words.

## Sourcing

The beat order and pacing follow the engineerguy series, whose transcripts are
in `references/engineerguy-youtube/`:

| video | file | what it gives us |
|---|---|---|
| 1/4 Intro & History | `(14) IntroHistory ….vtt` | the hook, Michelson, why it exists |
| 2/4 Synthesis | `(24) Synthesis ….vtt` | the mechanism, in build order |
| 3/4 Analysis | `(34) Analysis ….vtt` | running it backwards |
| 4/4 Operation | `(44) Operation ….vtt` | setup: notches, sines vs cosines, gearing |
| Bonus | `Bonus Rocker arms ….vtt` | the rocker-arm collective motion |

**Paraphrase, never paste.** The videos are copyrighted; the order in which a
mechanism is best explained is not. Where this script says something the videos
say better, link the video rather than competing with it.

## Voice

Second person, present tense, short sentences. Assume curiosity, not knowledge.
One idea per chapter, and the idea must be visible on screen while it is said —
if the viewer can't see the thing being described, it belongs in a different
chapter.

## Chapters

Placeholder copy is in `narration.ts` and is deliberately thin. Rewrite each
against the transcript, then move the final text here and have `narration.ts`
import it.

| id | working title | source video | status |
|---|---|---|---|
| `introduction` | A hundred-year-old computer | 1/4 | placeholder |
| `crank` | One input | 1/4 | placeholder |
| `cone-gears` | Twenty speeds from one shaft | 2/4 | placeholder |
| `cylinder-gears` | Rotation into oscillation | 2/4 | placeholder |
| `amplitude-bars` | Setting the coefficients | 2/4 | placeholder |
| `summing` | Twenty springs, one lever | 2/4 | placeholder |
| `magnifier` | Making it visible | 2/4 | placeholder |
| `synthesis` | Drawing a square wave | 2/4 | placeholder |
| `analysis` | Running it backwards | 3/4 | placeholder |
| `setup` | Sines or cosines | 4/4 | placeholder |

## Open questions

- **Does the tour autoplay or wait?** Autoplay demos better; waiting respects
  the visitor. Current lean: autoplay the first chapter, then wait.
- **How much maths on screen?** Current lean: the equation appears once, in
  `synthesis`, and never again.
- **Where does the Kickstarter call-to-action go?** Probably a persistent,
  small link — not an interstitial. The simulator's job is to make people care;
  the campaign page's job is to convert.
