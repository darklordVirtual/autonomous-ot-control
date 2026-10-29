# Before sharing the testbed widely

This is an experimental, simulation-only testbed. A public introduction can
show reproducible experiments without claiming production safety or measured
savings. This checklist separates documentation work from evidence still needed.

## First visitor

- [x] Put a credential-free offline check near the top of the README, with prerequisites and expected counts.
- [x] Show the governed flow as a diagram and link one permitted/refused authority example.
- [x] Describe APS consistently: offline `aps-1` reproduced; inline A/B/C integration pending.
- [x] Keep calibration limits visible beside synthetic savings.
- [ ] Record a short demonstration from the selected launch revision, showing a permitted action, a refusal and the evidence files.

## Refresh the A/B/C evidence

The published [abc-gate](results/2026-10-28/abc-gate.md) ran at `3ea8b12`.
Its header records a later attribution correction: two C-arm refusals were
credited to the edge although the reviewer stopped them. Keep that report
intact as historical evidence. Do not relabel it as a run of current `main`.

On a Docker Compose v2 host with access to the pinned dependencies, start
from a clean checkout of the selected full commit SHA. Do not run another
experiment against the same compose stack concurrently.

```bash
git checkout --detach <full-launch-commit-sha>
test -z "$(git status --porcelain)"
git rev-parse HEAD
RUN_ID="launch-$(date -u +%Y%m%dT%H%M%SZ)" ATTACK_SET=full DAYS=7 ./deploy/scripts/run-abc.sh
```

Allow about two hours. The script prints the output path. Preserve the full
artifact directory, including per-arm metrics and evidence, before publishing
a new report under a new dated path. Check all five arms completed, revision
checks match, forbidden/permitted denominators and proposals outside the
episode are explained, and refusals are attributed to the actual layer.
Report failures and missing results as such. Update the README only with
counts supported by that new run; retain the previous report and its caveat.

- [ ] Fresh five-arm report from a clean, identified revision.
- [ ] Corrected reviewer/edge attribution checked against per-arm records.
- [ ] New report linked from README with run ID, code and upstream pins.

No fresh A/B/C run is supplied by this documentation change. Docker is
unavailable in the authoring environment.

## Model validation before promoting savings claims

The [calibration record](calibration.md) distinguishes certificate priors,
in-sample meter fitting and remaining hourly errors. A monthly in-sample fit
is not held-out validation and does not establish a causal saving.

- [ ] Freeze fitted parameters and reserve an unused validation period.
- [ ] Publish validation dates, coverage, exclusions and energy/temperature errors.
- [ ] Investigate the technical-meter hourly mismatch and occupancy/load timing.
- [ ] Compare savings with comfort, a stated baseline and uncertainty.

These steps improve future model claims; they do not prevent inviting
contributors to test the current simulator under its stated limits.
