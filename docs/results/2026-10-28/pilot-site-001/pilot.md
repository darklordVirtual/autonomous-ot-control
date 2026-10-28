# Pilot evidence pack: site-001-v3 (NO1 Oslo, no1-2025-hvac-v1)

## Summary

On the twin calibrated to **SITE_001**, the governed caretaker **P3 + peak budget** against the as-found control **P0** over 365 days, 3 seeds, priced on *Elvia, stor næring effekt, lavspent uttak, from 2026-07-01*:

- **44 800 NOK a year (18.3 % of 244 933 NOK)**, seed range 44 238..45 216 NOK.
- **22 229 kWh (11.8 % of 187 842 kWh)**.
- Winter peak (mean of the winter months' highest hourly mean): 105 kW to 76 kW (-29 kW); grid power part 84 468 to 62 734 NOK.
- Comfort while occupied: 45 degree-hours (P0 0); CO2 above the ceiling 0 ppm·h (P0 0); tank above 60 degC 0 h; backup heater 5 311 kWh (P0 12 791).

Baseline model: monthly CV(RMSE) 11.8 %, NMBE -0.7 % over 9 metered months (Guideline 14 monthly met; hourly CV(RMSE) 59.2 %, not met). In-sample.

Plant sized from the design heat load (106 kW at -20.0 degC): heat pump 58 kW (55 % of the design load), backup heater 48 kW, buffer 1 456 l, ground source at 4.0 degC, Carnot fraction 0.609 (seasonal COP 4.28 at 40.0 degC supply). Derived from `site-001-v2`, whose heat pump was the installed radiator capacity; none of these values is measured.

Monthly check of this fixture against the site's measured months (same hours as the fit, in-sample): total: CV(RMSE) 12.2 %, NMBE -0.0 % (met); E01_vs_tenant: CV(RMSE) 12.1 %, NMBE 0.2 % (met); E02_vs_technical: CV(RMSE) 19.1 %, NMBE -0.4 % (not met).

## Strategies

| Strategy | Cost (NOK) | Saving (NOK) | Saving (%) | kWh | Saving (kWh) | Winter peak (kW) | Comfort (dh) | Backup (kWh) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 as found | 244 933 | – | – | 187 842 | – | 105 | 0 | 12 791 |
| P1 setback + optimal start | 225 055 | 19 878 (19 162..20 517) | 8.1 % | 188 206 | -363 | 85 | 0 | 13 091 |
| P2 caretaker presets | 216 383 | 28 550 (28 107..29 023) | 11.7 % | 173 399 | 14 443 | 90 | 0 | 14 533 |
| P3 governed caretaker | 217 316 | 27 617 (27 173..28 062) | 11.3 % | 174 377 | 13 465 | 90 | 44 | 15 685 |
| P3 + peak budget | 200 133 | 44 800 (44 238..45 216) | 18.3 % | 165 613 | 22 229 | 76 | 45 | 5 311 |

Saving = P0 cost minus the strategy's cost, per seed; mean and seed range. Cost = spot + grid energy part + power part on the month's highest hourly mean kW + fixed part; taxes excluded.

## What drives the number

Energy by consumer, P0 and P3pb (kWh a year):

| Consumer | P0 | P3pb | Saved |
|---|---:|---:|---:|
| Heat pump | 20 938 | 20 248 | 690 |
| Backup heater | 12 791 | 5 311 | 7 480 |
| AHU fans | 12 689 | 9 696 | 2 993 |
| Chiller | 1 037 | 1 101 | -64 |
| Lighting | 19 375 | 8 245 | 11 130 |
| Pumps / DHW | 28 917 | 28 917 | 0 |
| Equipment | 92 096 | 92 096 | 0 |
| Heating cables | 0 | 0 | 0 |

Cost saving by part: spot 21 955 NOK, grid energy part 1 111 NOK, power part 21 733 NOK.

## Tariff sensitivity

| Tariff | P0 cost | P1 saving | P2 saving | P3 saving | P3pb saving |
|---|---:|---:|---:|---:|---:|
| Elvia, stor næring effekt, lavspent uttak, from 2026-07-01 | 244 933 | 19 878 (8.1 %) | 28 550 (11.7 %) | 27 617 (11.3 %) | 44 800 (18.3 %) |
| Elvia, stor næring effekt, lavspent uttak, from 2026-01-01 | 216 882 | 15 161 (7.0 %) | 24 419 (11.3 %) | 23 546 (10.9 %) | 37 573 (17.3 %) |
| Generic reference business tariff (ASSUMPTION D-13) | 233 170 | 17 953 (7.7 %) | 26 762 (11.5 %) | 25 818 (11.1 %) | 41 722 (17.9 %) |

## Monthly

| Month | P0 kWh | P0 peak kW | P0 NOK | P3pb kWh | P3pb peak kW | P3pb NOK |
|---|---:|---:|---:|---:|---:|---:|
| 2025-01 | 22 341 | 106 | 34 404 | 19 785 | 105 | 29 860 |
| 2025-02 | 19 841 | 107 | 35 575 | 17 251 | 102 | 30 696 |
| 2025-03 | 16 225 | 104 | 22 387 | 14 109 | 63 | 16 077 |
| 2025-04 | 12 909 | 67 | 12 323 | 11 183 | 49 | 10 295 |
| 2025-05 | 13 024 | 45 | 12 144 | 11 233 | 41 | 10 753 |
| 2025-06 | 12 715 | 45 | 9 818 | 11 033 | 39 | 8 623 |
| 2025-07 | 13 638 | 46 | 10 227 | 11 965 | 41 | 9 082 |
| 2025-08 | 13 041 | 45 | 12 639 | 11 587 | 41 | 11 388 |
| 2025-09 | 12 919 | 68 | 12 240 | 11 731 | 52 | 10 710 |
| 2025-10 | 15 289 | 103 | 22 627 | 13 976 | 56 | 16 272 |
| 2025-11 | 17 152 | 106 | 31 619 | 15 396 | 65 | 24 069 |
| 2025-12 | 18 748 | 103 | 28 930 | 16 363 | 66 | 22 307 |

## Governance

P3pb: 35 040 proposals per seed; routes escalate 0, fallback 0, hold 26 051, submit 8 988.
Validator violations: IL-09 0.
Peak budget: cap steps 1, held 554, released 12 230.
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

- Testbed commit `b20a9607850b6f61f8b88730df4088f0b0731dd1` (dirty tree)
- Fixture `twin/fixtures/calibrated/site-001-v3.json` sha256 `941b522dcc657c0a…`
- Scenario `scenarios/no1-2025-hvac-v1.json` sha256 `6da38b7a4bf6bd60…`; series verified: outdoor ok, price ok, solar ok, humidity ok, precipitation ok
- Site policy sha256 `82f85aa4b5a44401…`; policy overrides {"peak_budget": {"kw": 60.0}}
- Seeds [177, 178, 179]; created 2026-10-28T06:12:24.251642Z

Rebuild: `python -m runner.pilot --config twin/fixtures/calibrated/site-001-v3.json --area NO1 --seeds 177 178 179 --strategies P0 P1 P2 P3 P3pb --peak-budget-kw 60 --monthly-check docs/results/2026-10-28/pilot-site-001/monthly-check-v3.json --workers 2 --out /tmp/claude-0/-home-claude/307815a1-36f2-58ee-a5dc-ff066381ef80/scratchpad/t1/pilot-2025`
