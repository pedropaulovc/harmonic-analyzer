# Logbook: learning to machine

I am a software engineer. I designed this machine in CAD without ever having cut
metal. Before I can write a machining book, I have to become a machinist.

This directory is that process. It holds a beginner's lathe and milling course,
sized to exactly what this project needs, plus the log of actually working
through it.

The primary goal is my own competence. The book is downstream: every chapter in
[`book/`](../book/README.md) Part III gets written from the module here that
taught me the operation, and every part chapter in Part IV from the entry where
I actually cut the part. Nothing gets taught that hasn't been done.

## Layout

| path | what |
|---|---|
| [`curriculum/`](curriculum/README.md) | The course. Twelve modules, M00 to M11, each ending by cutting a real part of the analyzer. |
| [`entries/`](entries/README.md) | Dated practice log. One entry per session: what I set out to do, what happened, what it cost. |
| [`SKILLS.md`](SKILLS.md) | The matrix. Skill, module, parts it unlocks, book chapter it feeds. |
| [`progress.md`](progress.md) | Where I am. Module status, hours, and what is blocking. |

## How the course is built

Every module ends by making a real part of the machine. No practice pieces for
their own sake. If a module can't be closed by cutting something the analyzer
needs, it doesn't belong in the course.

Modules are ordered by what the build needs next rather than by textbook order.
Parting off to a length tolerance comes early because thirty-eight bushings
whose lengths set the channel pitch come early.

Competency is measured, not felt. Each module has a check with a number in it,
like "hold ±0.02 mm across five consecutive parts", instead of "feel confident
turning".

The gear modules are the long pole and there is no point pretending otherwise.
Off-the-shelf cutters for this machine's diametral pitch do not exist, so M10
includes making the cutters, and it is scheduled with the most slack.

## References on hand

All in [`references/`](../references/), which is a git submodule:

- `machining-for-hobbyists-getting-started/`, the beginner spine, a chapter per topic
- `machinerys-handbook/`, the lookup, with a local search index
- `gears-and-gear-cutting/`, whose ch. 12 is the Eureka form-cutter method
- `jet-bd-920n-operators-manual.pdf`, the lathe
- `magxact-mx100m-mill-dro-manual/` and `el400-operation-manual/`, the DROs

## Machines

| | |
|---|---|
| Mill | PM-30MV (1 HP, R8, 4000 RPM) |
| Lathe | JET BD-920N (9″ × 20″) |
| Dividing head | not yet acquired, which blocks M09 and M10 |

## The honest note

This log records failures at full detail: scrapped parts, broken tools, wrong
speeds, misread micrometers. That is deliberate. A machining book written by
someone who has forgotten what it was like to be a beginner is a worse book, and
the mistakes are the part a reader can't get anywhere else.
