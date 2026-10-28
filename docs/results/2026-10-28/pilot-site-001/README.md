# Pilot evidence pack, SITE_001 (`site-001-v3`), 2026-10-28

The twin calibrated to a measured Oslo office (3 562 m², 1980, ground-source
heat pump; `docs/calibration.md`), its plant sized from the design heat load
(`site-001-v3`), under every strategy, three seeds, NO1 2025 weather and
prices, priced on Elvia's published 2026 tariff sheets and the fixture's
reference tariff. Method, limits and the decision record:
`docs/adr/ADR-011-peak-budget-and-pilot-evidence.md`.

| File | What it is |
|---|---|
| `pilot.html`, `pilot.md` | The report: summary with seed ranges, what drives the number (per consumer), monthly peaks and costs, tariff sensitivity, governance counts, scope (established / not established), evidence digests. Rebuilt from `pilot.json` by `python -m runner.report_pilot`. |
| `demo.html` | Interactive page: move the peak budget and see cost, peaks, comfort and releases; one day decision by decision; the baseline model against the site's meters. Rebuilt by `python -m runner.report_demo --pack <this dir>`. |
| `pilot.json` | Every number in the reports: per tariff, per strategy, year and month; caretaker statistics; calibration summary; scope; manifest. |
| `manifest.json` | SHA-256 of the fixture, the scenario, every weather and price series (verified against the scenario's declared digests), the site policy, the fallback and the calibration file; the meter export's digest (the export is not in the repository); git commit; Python; seeds; policy overrides; command line. |
| `sweep.json` | `runner.peak_sweep`: P3pb at 40, 50, 60, 80 and 100 kW beside P0 and P3, seed 177, priced on the 2026-07-01 sheet. On this plant the compressor is not the peak, so the number is insensitive to the budget's kW. |
| `monthly-check-v3.json` | `runner.site_calibration --monthly-check`: the v3 fixture's months against the site's measured months (in-sample, same hours as the fit). |
| `monthly.csv` | Month by strategy: kWh, peak kW, NOK, comfort degree-hours (primary tariff). |
| `decision-records.jsonl` | The caretaker's decision record (`ot-caretaker-decision/v1`) for every step of 2025-01-15 and 2025-07-15, seed 177, P3 and P3pb, with the peak budget's context and the policy overrides' digest. |
| `fdd-alarms.jsonl` | Every FDD alarm of the pack's runs (none are seeded here; `--faults` seeds them). |
| `bacs.md`, `bacs.json` | `runner.bacs`: the EN ISO 52120-1 function audit with the office BAC factors cross-checked against this pack's saving. |
| `metered-2026/` | The same pack on the site's own metered period (2026-02-16..2026-10-26, the scenario the calibration was fitted on), one seed, P0 / P1 / P3 / P3pb. |

Scope for every file: a calibrated simulation (IPMVP Option D), in-sample and
monthly; P0 is the testbed's generic as-found control, not the site's
sequence; the heat pump, backup heater, buffer and brine temperature are sized from stated assumptions;
taxes are excluded from every price. Not a measured saving.
