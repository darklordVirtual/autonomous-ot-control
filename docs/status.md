# Capability status

What this repository has established, by capability, and the evidence level
behind each line. Statuses are promoted only by new evidence, never by editing
this table. The README carries a short summary; this is the full record.

| Status | Meaning |
|---|---|
| `TESTED_LOCALLY` | Exercised by the unit or integration suite (`python -m pytest`) on one host, no Docker. |
| `TESTED_DOCKER` | Exercised on one host, one REMORA replica, Docker networks, synthetic plant, `same_test_deployment` vantage. Not a hosted or multi-node claim. |
| `SPECIFIED` | Written down (SDD, ADR, contract), not run. |
| `NOT_ESTABLISHED` | Nothing here shows it. |

## Delivery history

**PR 1 (OT-001 + OT-002)** delivered the simulator boundary. **PR 2 (OT-003 +
OT-004)** added the governed safety boundary. **OT-005..OT-012** run the stack
end to end: the pinned REMORA (`123a5fd0`) in production mode with PostgreSQL,
a signed ToolSpec v5 bundle (with signed postconditions) REMORA enforces and
pins by digest, signed cumulative limits across all 10 supervisory write tools,
the P3 caretaker profile engine with independent validator and FDD, verified
2025 Nord Pool prices and ERA5 weather across all five Norwegian price areas,
Statsbygg PA 0802 TFM mapping, and the opt-in federation onboarding kit.

## Capabilities

| Capability | Status |
|---|---|
| Deterministic 3-zone RC + HVAC building-services twin (`twin/plant.py`), seeded scenarios | `TESTED_LOCALLY` |
| All 10 supervisory write tools + interlocks `IL-01..IL-11` (zones, AHU, lighting, cables, tank, heat pump) | `TESTED_LOCALLY` |
| Single-use operation IDs incl. replay after restart (twin side) | `TESTED_LOCALLY` |
| Restart continues from the complete state: snapshot v2 carries the HVAC setpoints, plant state, point history (min-interval interlock), last plant points, heat and electricity meters and the tariff/season/surface state; a v1 snapshot is refused for the hvac model and migrated explicitly (event `snapshot_migrated`) for the simple one (finding of 2026-10-27 after PR #20; `tests/unit/test_twin_restart_state.py`) | `TESTED_LOCALLY` — before the fix a twin resumed from its snapshot kept revision 1 and an APPLIED record for cooling 24.0 while the cooling setpoint was back at 23.5, `point_history_s` was empty, and a change the interlock had just refused was accepted at the same simulated instant |
| Separate read / actuator / control listeners and credentials | `TESTED_LOCALLY` |
| Runner and harness cannot reach the actuator over Docker networks (AT-05) | `TESTED_DOCKER` |
| Read-only effect observer (`same_test_deployment` vantage) + ToolSpec v5 signed postconditions | `TESTED_LOCALLY` |
| Observer binds an effect to the operation that claims it: same tool, same target, same applied value, or `EFFECT_MISMATCH` whatever the plant shows (finding of 2026-10-27, `tests/unit/test_effect_observer_binding.py`) | `TESTED_LOCALLY` — before the fix an applied operation's id passed as proof of another tool's or zone's effect when the desired state already existed |
| Attestor keeps the observer's binding refusal through SDK verification and the recording boundary: a refused binding is an attested `EFFECT_MISMATCH` with the refusal as reason, never re-decided by comparing the plant's current value, and no `observed` fields are attached for a server to recompute from (finding of 2026-10-27 after PR #20; `tests/sdk/test_attestor_binding_sdk.py` with the real SDK at pin `123a5fd0`, `tests/unit/test_verifier_binding.py` without it) | `TESTED_LOCALLY` — before the fix the observer said `EFFECT_MISMATCH` (wrong tool, wrong zone, earlier value) and `verification.status` still came back `EFFECT_VERIFIED` from the real SDK; `attest_tool` downgraded the same refusal to `EFFECT_UNOBSERVABLE`. Server acceptance of an attested MISMATCH is not tested here |
| Rule baseline, scoring, evidence manifest | `TESTED_LOCALLY` |
| Signed ToolSpec enforced by REMORA (schema, target, closure digest, pinned bundle) | `TESTED_DOCKER` |
| Signed cumulative limits, mandatory; ZONE-03 budget refuses what the interlock allows (LIM-01) | `TESTED_DOCKER` |
| Authorized effect **through REMORA's dispatcher**, exactly once; operator cannot approve (AT-02) | `TESTED_DOCKER` |
| Replay refused, also after a REMORA restart (AT-04); tampered call refused (AT-03) | `TESTED_DOCKER` |
| Contract refusals: unknown tool/zone, bounds, extra args, wrong target (AT-08) | `TESTED_DOCKER` |
| Interlock refusal and stop switch: no effect, no replay shortcut (AT-08b, AT-10) | `TESTED_DOCKER` |
| PostgreSQL outage: unready, no effect, no blind resend on recovery (AT-11) | `TESTED_DOCKER` |
| Two concurrent approved writes to one zone: at most one effect (AT-13) | `TESTED_DOCKER` — held by the twin interlock, not by REMORA |
| Typed SDK `approve` on a deferred audit ref (SDK-01) | `TESTED_DOCKER` — fixed at pin `123a5fd0` (REMORA-research#1099) |
| Stale observation, timeout after actuation (AT-09, AT-12) | `NOT_ESTABLISHED` — TFM & stale checks tested in caretaker; no live fault hook in twin yet |
| Strategies P0/P1/P2/P3 over 2025 in all five price areas, verified local prices and weather ([report](results/2026-10-27/areas-2025.html)) | `TESTED_LOCALLY` — headline to quote: 9–14 % kWh from HVAC and lighting levers. The 25–42 % total is 80–90 % the heating-cable lever, which rests on unmeasured twin assumptions (cable rating, as-found thermostat control, surface model); every report opens with "What drives the number" |
| Caretaker P3: overlays, profiles, independent validator, fallback, FDD; A/B/C with seeded faults ([report](results/2026-10-27/abc-2025.html), ADR-009) | `TESTED_LOCALLY` — all 10 supervisory tools wired to REMORA (`runner.demo --strategy P3`) |
| TFM (Statsbygg PA 0802): register of every system and component code, parser and validator, every data point mapped to a TFM object ([tfm.md](tfm.md), ADR-010) | `TESTED_LOCALLY` — fictitious building `+DEMO01`; a real site's TFM needs its approved inventory (D-08) |
| Federation onboarding kit (`federation/`, sealed sets `v1` and `v2`, sandboxed runner, run records with derived independence level, reviewed reports, CI workflow) | `TESTED_DOCKER` — one external `L4_INDEPENDENT_HOST_RUN` record (Probity, PR #22) and one reviewed `runner_validity` report (Altru.dev); see [federation/RESULTS.md](federation/RESULTS.md) |
| Edges beside the run: every offline `effect_evidence` edge over a governed run's exported trails, findings listed, outcome untouched (`runner.edge_pass`, run by `run-demo-governed.sh`). Each claim's input comes from a record written when it happened (REMORA's readback and lifecycle, the twin's operation record, the observer's sealed record, the digest captured at export or REMORA's export manifest); a missing record is `NOT_ESTABLISHED`, never filled in. Reported three ways: the edge's answer, on recorded inputs only, and with strict vantage | `TESTED_DOCKER` — `observer-e2e-20261028T012704Z` (one day on Docker): both edges establish 14/14 new trails on recorded inputs, strict vantage 0/14 (`docs/results/2026-10-28/observer-e2e-edges.md`). Mutations of those trails (`runner.edge_mutations`, 518 case and 140 pipeline mutants): reference 100 %, Probity's edge 97.3 % exact with one crash on a missing observed value, 100 % after the adapter repair (`docs/results/2026-10-28/edge-mutations-after-adapter-fix.md`) (`docs/results/2026-10-28/edge-mutations.md`). On the older `abc-20261027T204956Z` trails, exported before the observer record, both answer 0/44 established; the earlier 44/44 rested on values the pass filled in itself |
| Episodes and the oracle (`ot-episode/v1`): the demo week's P1 proposal stream plus four injected attacks, each judged `permitted` or `forbidden:<rule>` from the work orders and the plant's limits alone, before any run; inputs pinned by digest, rebuild compared (`runner.episode check`) | `TESTED_LOCALLY` — `tests/unit/test_oracle_episode.py` fails if the oracle imports anything of REMORA's or reads a decision, reason or refusal field |
| Per-layer refusal accounting for arm B: `refused_by` (`interlock` / `remora:<reason>` / `reviewer`) and the oracle verdict on every ledger proposal, forbidden and permitted effects over their denominators, refusals by layer and rule, twin revision delta checked against counted effects (`runner.ledger_metrics`, `arm-b-metrics.json`) | `TESTED_LOCALLY` — synthetic ledgers and the committed episode; not yet run on a Docker demo |
| Arm A of the federation A/B/C: the ungoverned known-negative applies every episode proposal directly, interlock only, labelled `KNOWN_NEGATIVE`, nothing default refers to it (`runner.arm_a`) | `TESTED_LOCALLY` — on the committed episode: 44 permitted, 4 forbidden proposals; forbidden effects counted, interlock refusals attributed |
| Arm C harness: inline admission edge consulted after REMORA and the reviewer approved, 2 s budget, `refuse` rejects the approval, `permit` changes nothing, unavailable is `refuse` reported as `edge_unavailable`; composition rule pinned so no edge answer turns a refusal into an effect (`runner.admission`, `runner.demo --inline-edge`, reference edge `federation/edges/_inline_template`) | `TESTED_LOCALLY` — harness, composition rule, reference edge over HTTP, demo wiring; not yet run on a Docker demo |
| Federation A/B/C comparison and report: every arm against the oracle, per-rule table, refusals by layer, plant outcome, inline edges by what they added, offline edges by findings and sealed-set record, Markdown and HTML (`runner.ab_compare`, `deploy/scripts/run-abc.sh`) | `TESTED_LOCALLY` — arm A real, arms B and C as synthetic ledgers in the demo's shape; the Docker run of B-careful, B-rubber_stamp and C-rubber_stamp has not been done. See [federation/ABC-ROADMAP.md](federation/ABC-ROADMAP.md) |
| Reference verifier requires the evidence each claim needs: missing dispatch time, observation time or execution count is `NOT_ESTABLISHED`, a trail that says nothing executed while the twin recorded APPLIED is `CONTRADICTED`; fixture set `v2` adds those four negatives and the scorer counts a negative as caught only on the manifest's expected verdict (finding of 2026-10-27 after PR #20; `tests/unit/test_reference_verifier_evidence.py`) | `TESTED_LOCALLY` — before the fix all four schema-valid mutations came back `ESTABLISHED` (defaults of 1 execution and observation-at-dispatch, a skipped time check, a skipped authorization check when `executed` was false). Offline verifier only; no bypass of the manifest's hash check or of actuator authorization was shown |
| Peak budget (ADR-011): forward-looking cap on the heat pump from a site-set monthly kW budget, full-output draw learned from the plant's points, releases for frost, occupied comfort and a tank near the backup heater, buffer setpoint following the capped tank; IL-09 in the validator governs the write, as in the twin's guard (`runner/caretaker.py::PeakBudget`, strategy `P3pb`, policy `peak_budget` off by default) | `TESTED_LOCALLY` — `tests/unit/test_peak_budget.py`: a January week on `site-001-v2` with a 90 kW budget: no fallback or escalation, no IL-09 or IL-04 violation, backup heater 0 kWh, occupied comfort unchanged, the week's highest hourly mean more than 20 kW below P3's. Every earlier result is unchanged (P3 does not read the budget) |
| Pilot evidence pack (ADR-011): every strategy on the calibrated `site-001-v3`, three seeds, priced on Elvia's published 2026 sheets and the reference tariff, IPMVP Option D / Guideline 14 report with seed ranges, lever waterfall, monthly peaks, tariff sensitivity, governance counts, scope, and a manifest with the SHA-256 of every input (`runner.pilot`, `runner.report_pilot`, `runner.peak_sweep`, `runner.report_demo`; [pilot report](results/2026-10-28/pilot-site-001/pilot.html), [interactive page](results/2026-10-28/pilot-site-001/demo.html)) | `TESTED_LOCALLY` — PILOT_STATUS_LINE. The calibration is in-sample and monthly; P0 is the testbed's generic as-found control; the plant's ability to cap the compressor is a site question. Not a measured saving |
| Plant sized from the design heat load (`runner.calibration size-plant`, fixture `site-001-v3`, ADR-011): heat pump as a share of the design load, backup heater as the rest, ground-source pump (`hp_source_c`, optional in `twin/plant.py`, every earlier fixture unchanged), Carnot fraction from the certificate's seasonal COP, buffer by litres per kW; checked month by month against the site's measured months without the hourly export (`runner.site_calibration --monthly-check`) | `TESTED_LOCALLY` — `tests/unit/test_plant_sizing.py` pins v3 as what `size_plant` builds from v2 and the ground-source pump's behaviour at −20 °C; the monthly check: total CV(RMSE) 12.2 %, NMBE 0.0 % (Guideline 14 monthly met), technical meter 19.1 % / −0.4 % (not met), in-sample ([monthly-check-v3.json](results/2026-10-28/pilot-site-001/monthly-check-v3.json)). The heat pump's size, the backup's staging, the buffer and the brine temperature are stated assumptions, not measurements; the site's winter hourly maxima decide them |
| Named tariffs (`runner/tariffs.py`): a run priced on a published tariff sheet with its URL, validity and exclusions; the control is unchanged by the tariff so one run is priced under every one | `TESTED_LOCALLY` — transcribed by hand from Elvia's Tariffblad 3.0 (2026-01-01 and 2026-07-01); a transcription error is a defect of the registry, not of the twin |
| BACS function audit (`runner.bacs`) in the structure of EN ISO 52120-1: the level P0 and P3 reach per function with the data point or algorithm as evidence, the class floor, the office BAC factors beside the simulated saving, EPBD recast Article 13 thresholds ([bacs.md](results/2026-10-28/pilot-site-001/bacs.md)) | `SPECIFIED` — a transcription of the standard's structure, not a licensed copy; no class is issued |
| Miniflare / Cloudflare autonomous runtime ([architecture/autonomous-runtime-cloudflare.md](architecture/autonomous-runtime-cloudflare.md), MCP OpenAPI) | `SPECIFIED` (`NOT_ESTABLISHED` runtime) |
| Real-building savings, physical OT safety | `NOT_ESTABLISHED` — synthetic model only |

## Not established, by design

- No physical OT/BMS write path exists in this repository, and simulation
  results never unlock a live connector (INV-12).
- Every Docker result is one deployment seen from inside that deployment.
  Nothing here shows what a real plant does, or that REMORA's policy is the
  right policy for a real site.
