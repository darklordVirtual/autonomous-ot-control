# Energy-saving strategies and REMORA synergy (2025, five price areas)

The caretaker (`runner/caretaker.py`, ADR-009) combines safety overlays
(`frost_protection`, `iaq_protection`, `icing_protection`, `telemetry_degraded`),
one active base profile (`comfort_priority`, `demand_response`, `preconditioning`,
`night_setback`, `energy_saving`, or `balanced_default`), one named algorithm
per setpoint, an independent validator against [`deploy/ot/site_policy.v1.json`](../deploy/ot/site_policy.v1.json),
a hash-pinned sensor-free fallback ([`deploy/ot/caretaker_fallback.v1.json`](../deploy/ot/caretaker_fallback.v1.json)),
and zone sensor FDD. Every supervisory change maps to one of the 10 governed
tools in [datapoints.md](datapoints.md) and carries its decision record
(`ot-caretaker-decision/v1`) as evidence into REMORA.

## Strategies

| Strategy | What it is |
|---|---|
| P0 | As found (`runner.baseline`): 21 °C occupied with 1 h preheat, 20 °C otherwise; fixed AHU schedule; lighting on schedule; heating cables on an air thermostat; tank at 50 °C with no cap |
| P1 | P0 plus night setback to 19 °C and self-tuning optimal start (`runner/strategies.py`, ADR-006) |
| P2 | P1 plus weekend/holiday setback by outdoor mean, occupancy-aware ventilation, presence lighting with daylight dimming, ground-sensor cable control, tank on the radiator curve with a cheap-hour boost and a peak limiter |
| P3 | The caretaker profile engine: overlays, profiles, independent validator, hash-pinned fallback and FDD (`runner/caretaker.py`, ADR-009) |
| P3raw | P3 without the independent validator, run with the same seeded sensor faults |
| P3pb | P3 with the monthly peak budget on (ADR-011): the compressor is capped so the building's hourly mean stays under a site-set kW budget, released only for comfort, frost or a tank near the backup heater; no cheap-hour tank charge |

## Results, full year 2025

| Price area | P0 cost (NOK) | P0 energy (kWh) | P3 saves vs P0 (%) | P3 saves (NOK) | P3raw (no validator, faulted) | Validator value |
|---|---:|---:|---:|---:|---:|---:|
| **NO1 Oslo** | 56 127 | 47 331 | **41.9 %** | 23 517 | 37.4 % | +4.5 pp (0 h tank > 60 °C vs 322 h) |
| **NO2 Kristiansand** | 53 103 | 40 410 | **39.9 %** | 21 208 | 34.5 % | +5.5 pp (0 h tank > 60 °C vs 383 h) |
| **NO5 Bergen** | 48 704 | 43 629 | **39.8 %** | 19 384 | 32.1 % | +7.3 pp (0 h tank > 60 °C vs 452 h) |
| **NO3 Trondheim** | 37 092 | 48 840 | **33.8 %** | 12 539 | 27.3 % | +6.5 pp (0 h tank > 60 °C vs 355 h) |
| **NO4 Tromsø** | 29 997 | 65 101 | **25.5 %** | 7 637 | 16.4 % | +9.5 pp (0 h tank > 60 °C vs 283 h) |

**Read the headline with care.** 80–90 % of the saved kWh in every area is one
lever: the heating cables, which as found (P0) run on an air thermostat and
with P3 on the ground moisture sensor. That lever rests on three stated,
unmeasured assumptions of the twin: the installed cable rating (9 kW for a
260 m² building), the as-found control, and the surface moisture model. The
figure to quote until a real site has been measured is the one **without the
cable lever: P3 saves 9–14 % of the kWh** from the HVAC and lighting levers
(roughly 14–18 % of cost, an estimate because the grid power part is not
attributable per consumer). Each report opens with a "What drives the number"
section that gives this split per area and a kWh/m² reasonableness check.

Synthetic, uncalibrated building (3 seeds, full year 2025, verified local Nord
Pool spot prices + ERA5 weather + declared reference grid tariff, taxes
excluded). None of this is a real-building saving.

Full reports: [areas-2025.md](results/2026-10-27/areas-2025.md) /
[areas-2025.html](results/2026-10-27/areas-2025.html) and
[abc-2025.md](results/2026-10-27/abc-2025.md) /
[abc-2025.html](results/2026-10-27/abc-2025.html).

Reproduce without Docker:

```bash
python -m runner.areas --seeds 177 178 179 --out artifacts/areas-2025
```

## Results on a calibrated building: SITE_001, NO1 2025 (ADR-011)

The same strategies on the twin calibrated to a measured Oslo office
(3 562 m², 1980, ground-source heat pump; `docs/calibration.md`), its plant
sized from the design heat load (`site-001-v3`), three seeds, the peak
budget at 60 kW, priced on Elvia's published 2026 sheet for large
low-voltage customers (effektledd 111 NOK/kW/month Oct–Mar, 46 Apr–Sep;
`runner/tariffs.py`).
The full pack with every table, the seed ranges, the monthly peaks, the
tariff sensitivity and the evidence digests:
[`results/2026-10-28/pilot-site-001/pilot.html`](results/2026-10-28/pilot-site-001/pilot.html)
([md](results/2026-10-28/pilot-site-001/pilot.md)); the interactive page:
[`demo.html`](results/2026-10-28/pilot-site-001/demo.html).

| Strategy | Cost (NOK) | Saving (NOK) | Saving (%) | kWh | Saving (kWh) | Winter peak (kW) | Backup (kWh) | Comfort (dh) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 as found | 244 933 | – | – | 187 842 | – | 105 | 12 791 | 0 |
| P1 | 225 055 | 19 878 (19 162..20 517) | 8.1 % | 188 206 | -363 (-0.2 %) | 85 | 13 091 | 0 |
| P2 | 216 383 | 28 550 (28 107..29 023) | 11.7 % | 173 399 | 14 443 (7.7 %) | 90 | 14 533 | 0 |
| P3 caretaker | 217 316 | 27 617 (27 173..28 062) | 11.3 % | 174 377 | 13 465 (7.2 %) | 90 | 15 685 | 44 |
| **P3pb caretaker + peak budget** | 200 133 | 44 800 (44 238..45 216) | 18.3 % | 165 613 | 22 229 (11.8 %) | 76 | 5 311 | 45 |

**Read it with care.** On this building, as sized from its certificate
(a 58 kW ground-source heat pump with a 48 kW direct-electric backup,
`docs/calibration.md`), the month's highest hourly mean is set by the
backup heater firing for a recovery after a setback. The budget's value
here is not the compressor cap, which almost never binds, but a heat-pump
-only recovery: the buffer setpoint never asks for more than the compressor
can hold, and the setback is only as deep as the learned reheat rate
recovers before occupancy. That cuts the backup heater by more than half
and the shoulder-month peaks by a third; January and February stay at the
compressor's limit, where the comfort guard restores the backup. The kWh
saving is lighting (presence and daylight) and the avoided backup at
COP 1. The calibration is in-sample and monthly, P0 is the testbed's
generic as-found control, not the site's sequence, and the plant's size is
a stated assumption until the site's winter hourly maxima are measured:
the pack's scope section lists every such item. None of this is a
measured saving.

Reproduce without Docker (about 30 minutes on two cores):

```bash
python -m runner.pilot --config twin/fixtures/calibrated/site-001-v3.json --area NO1 \
    --seeds 177 178 179 --strategies P0 P1 P2 P3 P3pb --peak-budget-kw 60 \
    --monthly-check docs/results/2026-10-28/pilot-site-001/monthly-check-v3.json --out artifacts/pilot-site-001
```
