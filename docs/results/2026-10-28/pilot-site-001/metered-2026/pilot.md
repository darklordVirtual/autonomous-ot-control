# Pilot evidence pack: site-001-v3 (NO1 Oslo, no1-2026-metered-period-hvac-v1)

## Summary

On the twin calibrated to **SITE_001**, the governed caretaker **P3 + peak budget** against the as-found control **P0** over 253 days, 1 seeds, priced on *Elvia, stor næring effekt, lavspent uttak, from 2026-07-01*:

- **35 025 NOK over the 253-day period (17.8 % of 197 013 NOK)**, seed range 35 025..35 025 NOK.
- **14 683 kWh (12.5 % of 117 815 kWh)**.
- Winter peak (mean of the winter months' highest hourly mean): 104 kW to 62 kW (-41 kW); grid power part 49 649 to 32 454 NOK.
- Comfort while occupied: 39 degree-hours (P0 0); CO2 above the ceiling 0 ppm·h (P0 0); tank above 60 degC 0 h; backup heater 1 297 kWh (P0 4 070).

Baseline model: monthly CV(RMSE) 11.8 %, NMBE -0.7 % over 9 metered months (Guideline 14 monthly met; hourly CV(RMSE) 59.2 %, not met). In-sample.

Plant sized from the design heat load (106 kW at -20.0 degC): heat pump 58 kW (55 % of the design load), backup heater 48 kW, buffer 1 456 l, ground source at 4.0 degC, Carnot fraction 0.609 (seasonal COP 4.28 at 40.0 degC supply). Derived from `site-001-v2`, whose heat pump was the installed radiator capacity; none of these values is measured.

Monthly check of this fixture against the site's measured months (same hours as the fit, in-sample): total: CV(RMSE) 12.2 %, NMBE -0.0 % (met); E01_vs_tenant: CV(RMSE) 12.1 %, NMBE 0.2 % (met); E02_vs_technical: CV(RMSE) 19.1 %, NMBE -0.4 % (not met).

## Strategies

| Strategy | Cost (NOK) | Saving (NOK) | Saving (%) | kWh | Saving (kWh) | Winter peak (kW) | Comfort (dh) | Backup (kWh) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 as found | 197 013 | – | – | 117 815 | – | 104 | 0 | 4 070 |
| P1 setback + optimal start | 187 104 | 9 910 (9 910..9 910) | 5.0 % | 117 930 | -115 | 80 | 0 | 4 042 |
| P3 governed caretaker | 173 416 | 23 597 (23 597..23 597) | 12.0 % | 105 768 | 12 047 | 83 | 39 | 4 350 |
| P3 + peak budget | 161 988 | 35 025 (35 025..35 025) | 17.8 % | 103 132 | 14 683 | 62 | 39 | 1 297 |

Saving = P0 cost minus the strategy's cost, per seed; mean and seed range. Cost = spot + grid energy part + power part on the month's highest hourly mean kW + fixed part; taxes excluded.

## What drives the number

Energy by consumer, P0 and P3pb (kWh over the 253-day period):

| Consumer | P0 | P3pb | Saved |
|---|---:|---:|---:|
| Heat pump | 6 393 | 6 362 | 32 |
| Backup heater | 4 070 | 1 297 | 2 773 |
| AHU fans | 8 808 | 6 782 | 2 026 |
| Chiller | 1 072 | 1 103 | -31 |
| Lighting | 13 436 | 3 553 | 9 883 |
| Pumps / DHW | 20 044 | 20 044 | 0 |
| Equipment | 63 992 | 63 992 | 0 |
| Heating cables | 0 | 0 | 0 |

Cost saving by part: spot 17 096 NOK, grid energy part 734 NOK, power part 17 195 NOK.

## Tariff sensitivity

| Tariff | P0 cost | P1 saving | P3 saving | P3pb saving |
|---|---:|---:|---:|---:|
| Elvia, stor næring effekt, lavspent uttak, from 2026-07-01 | 197 013 | 9 910 (5.0 %) | 23 597 (12.0 %) | 35 025 (17.8 %) |
| Elvia, stor næring effekt, lavspent uttak, from 2026-01-01 | 180 573 | 6 876 (3.8 %) | 20 557 (11.4 %) | 29 318 (16.2 %) |
| Generic reference business tariff (ASSUMPTION D-13) | 186 316 | 7 399 (4.0 %) | 21 436 (11.5 %) | 31 726 (17.0 %) |

## Monthly

| Month | P0 kWh | P0 peak kW | P0 NOK | P3pb kWh | P3pb peak kW | P3pb NOK |
|---|---:|---:|---:|---:|---:|---:|
| 2026-02 | 9 580 | 105 | 24 463 | 8 030 | 73 | 18 310 |
| 2026-03 | 17 072 | 102 | 32 810 | 14 956 | 61 | 25 370 |
| 2026-04 | 13 514 | 100 | 20 652 | 11 520 | 52 | 16 283 |
| 2026-05 | 12 665 | 46 | 16 036 | 10 863 | 38 | 14 050 |
| 2026-06 | 13 177 | 45 | 13 868 | 11 487 | 40 | 12 258 |
| 2026-07 | 13 633 | 46 | 17 641 | 11 793 | 41 | 15 485 |
| 2026-08 | 13 074 | 45 | 20 295 | 11 555 | 41 | 18 099 |
| 2026-09 | 12 854 | 48 | 21 130 | 11 658 | 43 | 19 140 |
| 2026-10 | 12 247 | 104 | 30 118 | 11 271 | 54 | 22 993 |

## Governance

P3pb: 24 288 proposals per seed; routes escalate 0, fallback 0, hold 19 545, submit 4 743.
Validator violations: none.
Peak budget: cap steps 0, held 166, released 10 833.
FDD: 0 alarms, 0 true; optimizer faults caught 0.

## Scope

Method: IPMVP Option D (calibrated simulation); calibration reported against ASHRAE Guideline 14 (monthly CV(RMSE) <= 15 %, |NMBE| <= 5 %; hourly <= 30 %, <= 10 %).

Established:
- The twin, calibrated to the site's named meters, reproduces the site's monthly electricity within the Guideline 14 monthly criteria on the metered period (in-sample).
- On that twin, the strategies' energy, cost, peak and comfort differences are deterministic and reproducible from the pinned inputs and seeds.
- Every supervisory change of the caretaker is one governed tool call with a decision record; the validator's refusals and routes are counted.

Not established:
- A measured saving in the building. The calibration is in-sample (the fit period is the validation period), monthly only (the hourly criterion is not met), and on nine months of 2026 while the savings year is 2025.
- The as-found control. P0 is the testbed's generic as-found sequence (fixed schedules, constant tank), not the site's documented sequence; the site's real baseline may already contain some of the levers.
- The plant as sized: the heat pump's output, the backup heater, the buffer volume and the ground-source temperature are derived from the certificate and stated assumptions (calibration.plant_sizing), not measured; whether the real plant stages its backup heater as the twin does, and whether lighting can be controlled by presence and daylight, are site questions.
- The grid tariff's power part: priced on a published sheet, transcribed by hand, excluding taxes and the reactive-power charge; the site's contract may differ.
- Physical OT safety. No write path to a real plant exists (INV-12).

A 90-day pilot replaces every item above with measurement: the site's own control sequence as P0, a held-out validation period, the meters as the measurement boundary, and the governed caretaker in shadow then controlled operation under the signed limits.

## Evidence

- Testbed commit `77b9fe82061141220c21deac557244b5c0a766e3` (dirty tree)
- Fixture `twin/fixtures/calibrated/site-001-v3.json` sha256 `941b522dcc657c0a…`
- Scenario `scenarios/no1-2026-metered-period-hvac-v1.json` sha256 `d533651b0724ce40…`; series verified: outdoor ok, price ok, solar ok, humidity ok, precipitation ok
- Site policy sha256 `82f85aa4b5a44401…`; policy overrides {"peak_budget": {"kw": 60.0}}
- Seeds [177]; created 2026-10-28T06:25:09.915661Z

Rebuild: `python -m runner.pilot --config twin/fixtures/calibrated/site-001-v3.json --area NO1 --scenario scenarios/no1-2026-metered-period-hvac-v1.json --seeds 177 --strategies P0 P1 P3 P3pb --peak-budget-kw 60 --monthly-check docs/results/2026-10-28/pilot-site-001/monthly-check-v3.json --workers 2 --out /tmp/claude-0/-home-claude/307815a1-36f2-58ee-a5dc-ff066381ef80/scratchpad/t1/pilot-metered`
