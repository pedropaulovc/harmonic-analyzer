# FAQ

Drafts. Rewrite in campaign voice before publishing; keep the answers this
blunt.

**Is this the same as the engineerguy book?**
No. Hammack, Kranz and Carpenter's *Albert Michelson's Harmonic Analyzer*
(2014) is a beautiful visual tour of the machine — it shows you what it is.
This book tells you how to make one. It is an independent project, not
affiliated with or endorsed by them, and it cites their work throughout. Go
read theirs; it's free.

**What happens to the machine you build?**
It goes to [Matemateca](https://matemateca.ime.usp.br/index_ingles.html), the
mathematics outreach collection at the University of São Paulo's Institute of
Mathematics and Statistics. They use objects to teach mathematics to the public
and to school groups, and this one will be used with middle and high schoolers.
I don't keep it. That is also why the build targets a machine that survives
being operated by teenagers rather than one that looks good in a photograph.

**Can I buy a finished machine, or a kit?**
No. Building one analyzer is this project. Building them to order is a
different business, and pretending otherwise is how campaigns fail.

**Do I need CNC?**
For the milled parts, the book assumes it. I cut them on a CNC-converted bench
mill (a PM-30MV running FluidNC, sent from CNCjs) because makerspace mill time
costs too much to make them by hand, and the programs are posted with
open-source CAM (FreeCAD); each release ships the G-code for every part that
has a program, beside its drawing. Turned parts are made on a manual lathe.
Without a CNC mill you can still work from the drawings on a manual mill at
your own pace, but the book does not walk that route and I have not tested it.

**What machines and tooling do I actually need?**
A CNC bench mill (or a manual one, at your own pace), a lathe, a dividing head,
and a normal measuring kit. The full
list with sizes is in the book's shop-setup chapter, and it is published free
before launch so you can decide before you pledge.

**How hard is this really?**
Hard. One part, a six-tooth gear 4.31 mm across with about 0.64 mm of
metal between tooth root and bore, is genuinely at the edge of home-shop
capability. Stock cutters cover the rest of the gear train, but that gear needs
a cutter you make yourself. The book
says exactly where the difficulty is instead of pretending it's uniform.

**How long does a build take?**
Unknown, honestly. The CAD inventory has
[149 registered part families](../../cad/docs/subsystem-identities.md), including
parts repeated across the twenty channels.
The logbook records real hours per part as they are cut, and the book publishes
those numbers.

**Do I have to build the whole thing?**
No, and the book is structured so you don't have to. The cone gear set alone is
a satisfying, self-contained project; so is a single channel.

**Are the CAD files free?**
Yes. The model, the STEP exports and the drawing sheets are MIT-licensed and
already public on GitHub, funded or not. You are paying for the book — the
process, the setups, the tolerances, the failures.

**What if the machine doesn't work?**
Then the book documents why, and that's still the book. The machining chapters
stand on their own, and a failed calibration analyzed properly is more useful
than a success story with the details left out.

**Why are you qualified? You said you're learning.**
I'm not a machinist — I'm a software engineer who did the engineering design
work and is learning to machine it. That's exactly who the book is for. Every
mistake I make gets written down while it's still fresh, which is not something
an expert can do.

**Where does the money go?**
Stock, tooling, spring winding, editing, layout, photography, printing and
shipping. The breakdown is published in the repo. The mill, the lathe and the
CAD work are already paid for and are not in the goal.

**When do I get it?**
See the timeline on the campaign page. The digital edition ships first.

**Shipping outside the US/EU/BR?**
TBD before launch — see `../rewards/fulfilment.md`.
