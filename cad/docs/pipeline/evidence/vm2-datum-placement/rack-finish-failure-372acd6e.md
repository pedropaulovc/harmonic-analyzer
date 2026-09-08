# Rack finish cold-reopen failure at 372acd6e

The normal drawing build passed, but the complete rack lifecycle failed at its
first cold open. This head is not accepted for readable prints.

The [original lifecycle receipt](probes/rack-production-lifecycle-372acd6e/receipt.json)
has SHA-256 `94de73f21928ad2f707a5bbcf994037bb6fff759a95d22d3f59c888b18e56490`.
Its error says `datum/diameter ink clearance 0 m < 0.001 m`; the caller was
comparing the **finish leader against the datum**, not the diameter dimension.
The shared diagnostic error wording does not identify that caller.

The finish still has exactly one edge attachment, native equality 1, is not
dangling, and reads `Ra 1.6`. Its endpoint is
`(0.21804349740134313, 0.17344369111470476, 0.0015)` metres, at the crowded
datum location. Attachment alone does not prove clearance.

The subsequent [point/rebuild/cold-reopen experiment](probes/rack-production-lifecycle-372acd6e/finish-persistent-trial.json)
has SHA-256 `c25160bf30d218d77691c48606b84c831244f857343e77b4bd3ef627a49e0fe3`.
The endpoint remains at that location after rebuild and cold reopen, while
semantic attachment remains intact. The earlier immediate-only trial did not
prove persistence; the production helper's claim that its route persists is
not supported by this later experiment. A correction and fresh cold-print
validation are still required. These tried call sequences do not establish
that all native placement methods fail.

Source SHA-256 remained
`24eb4236303c758016d2340bd6cfbee63ffed63e2f5a73bfb99f889adbaac418` and the
saved production drawing remained
`d6f6920616a1bbb1e04ea4db3b205b71678e0938cb9354458f8015523a3177aa`.
The original production drawing is published with its
[normal-build receipt](probes/production-372acd6e/receipt.json).
The experimental drawing copy was subsequently saved by the point trial, so
it is not presented as the original failed drawing snapshot.

Raw receipts retain their exact bytes and local paths as the owner requested.
The exact probe source used by the point trial is archived beside its receipt.
No placement or manufacturing tolerance has changed. VM1's running combined
build remains frozen; even a green result does not clear this known failure.
