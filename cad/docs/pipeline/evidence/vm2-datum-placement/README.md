# VM2 datum placement investigation

This independent correction starts from main
`55056d4990d38ebb461f343d3002fc90731b9e73`, with adapter
`2269009ed56712867826516f4406afc98a0c2814`, under the
[handoff at 1319994b](https://github.com/pedropaulovc/harmonic-analyzer/blob/1319994b3c6b93f1610513897ed4fbb9a8a3b9c9/cad/docs/pipeline/second-vm-datum-placement.md).

No correction or native acceptance is claimed yet. Both placement tolerances
remain fixed: 20 micrometres for pinion-lift-rod and 100 for rack-pinion.
The assembly branches and #682/#685 remain unchanged; VM1 owns integration and merging.

## Original failure receipts

The files in `raw/` are byte-for-byte copies of VM2's unchanged targeted retry
at assembly candidate `2d10203b0d554e1d53fb5f13d84951412afb4a82`.
Git text normalization is disabled for these copies. Their SHA-256 values were
verified against the original files before and after copying. The originals
remain in their existing checkout report directories.

| File | SHA-256 |
|---|---|
| [candidate-2d-datum-retry-full.log](raw/candidate-2d-datum-retry-full.log) | `a7ec86f9a83f2ff9bc7717f940e19c238a494f0352e0c613ddab89853184061f` |
| [candidate-2d-datum-retry-process.json](raw/candidate-2d-datum-retry-process.json) | `395b96c33637782495b1eec7506975887bf8231db6b93ba59635a7199469fda6` |
| [candidate-2d-datum-retry-summary.json](raw/candidate-2d-datum-retry-summary.json) | `78a32ddbe768e59150b419ba0d4931b77dc44c7c9b9c1c4f08c7d891e23e86cf` |

The command exited 2 in 38.0207716999575 seconds. Both part dependencies were
current. Datum A returned these sheet coordinates after the requested move:

| Drawing | Requested position, m | Returned position, m |
|---|---|---|
| pinion-lift-rod | `(0.055, 0.22899999999999998)` | `(0.05499999999999966, 0.22897646401719635)` |
| rack-pinion | `(0.22, 0.20099999999999998)` | `(0.21999999999999942, 0.20083662770023045)` |

These are datum-symbol position readbacks, not manufacturing geometry errors.
The process receipt contains complete before/after input hashes. The summary
contains the two failing drawing task records and telemetry boundaries; it is
not a copy of the entire append-only telemetry history.

## Investigation boundaries

The first probes will compare coordinate, semantic-edge and existing-dimension
attachment while retaining the requested position and tolerance. The documented
`SetPosition2` contract allows restricted annotations to land near the requested
position; it does not establish the cause of these two failures.

Shared-helper native-placement changes and the shared gear drawing test's
coordinate-specific assertion require
[VM1 coordination](https://github.com/pedropaulovc/harmonic-analyzer/pull/698#issuecomment-5577757811).
The ordinary finalizer on this baseline does not prove cold-reopen, move/scale or
attachment identity. Dedicated native evidence must cover those checks.

## Native probe results

[The probe report](probe-results.md) records semantic-edge and diameter-dimension
trials, their partial prints, the rack export identity failure, and the remaining
acceptance work. These trials have not established a production correction.
