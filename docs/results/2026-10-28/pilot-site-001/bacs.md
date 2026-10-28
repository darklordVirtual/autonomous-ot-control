# Building-automation function audit (EN ISO 52120-1:2022 (EN 15232-1:2017))

> Function names, levels and class thresholds are transcribed from the standard's structure, not quoted from a licensed copy; verify against the standard before any contractual or regulatory use. The formal class is assigned by an assessor over the installed equipment.

| Id | Function | As found (P0) | Caretaker (P3) | Evidence (P3) |
|---|---|---|---|---|
| 1.1 | Emission control (room temperature) | 1 (D) | 3 (B) | per-zone heating setpoint written and read back through the governed tools (`set_zone_setpoint`, `ZONE-0x.AirTemp`); no presence sensor in the twin, so not level 4 |
| 1.3 | Control of distribution network hot-water temperature | 0 (D) | 2 (A) | weather-reset tank following the radiator curve, demand-held on price and peak (`weather_reset`, `price_ranked_charge`, `set_tank_setpoint`) |
| 1.5 | Intermittent control of emission and/or distribution | 1 (C) | 3 (A) | self-tuning optimal start (`ReheatLearner`), recovery-limited setback by outdoor mean, occupancy horizon (`optimal_start`, `recovery_setback`, `setback`) |
| 1.7 | Heat-pump generator control | 0 (D) | 2 (A) | tank setpoint from the weather curve plus demand hold; compressor cap for the peak budget (`set_heat_pump_limit`, ADR-011) |
| 1.10 | Thermal energy storage control | 0 (D) | 2 (A) | charging ranked by the day-ahead price and held before a peak block (`price_ranked_charge`) *The twin's price-ranked charging is prediction-based on the published day-ahead price, not on a load forecast.* |
| 3.1 | Emission control (room temperature) | 1 (D) | 3 (B) | per-zone cooling setpoint through `set_zone_cooling_setpoint`, unoccupied setback (`unoccupied_cooling_setback`) |
| 3.6 | Interlock between heating and cooling | 2 (A) | 2 (A) | IL-01 held by the twin, the signed ToolSpec and the caretaker's validator |
| 4.1 | Supply-air flow control at room level | 1 (C) | 3 (A) | DCV on CO2 in every zone (`ZONE-0x.CO2Setpoint`, `set_zone_co2_setpoint`), IAQ overlay keeps the AHU on above 950 ppm |
| 4.3 | Heat-exchanger icing protection | 1 (A) | 1 (A) | same (plant function, not a caretaker lever) |
| 4.5 | Free mechanical cooling | 0 (D) | 1 (C) | summer night purge through the HRV bypass (`night_purge`); the twin has no modulated free-cooling damper *Free cooling from the energy wells (`free_cooling_eer`) is a plant property of SITE_001, not a controlled function.* |
| 4.6 | Supply-air temperature control | 1 (C) | 3 (A) | Trim & Respond on zone requests outside the heating season (`trim_respond`, `set_supply_air_setpoint`) |
| 5.1 | Occupancy control | 1 (C) | 3 (A) | presence mode: lit while people are present, off when they leave (`set_zone_lighting_mode`) |
| 5.2 | Daylight control | 0 (C) | 1 (A) | daylight harvesting to the lux setpoint (`daylight_harvesting`) |
| 7.3 | Detecting faults of technical building systems and support to diagnosis | 0 (B) | 1 (A) | zone-sensor FDD: stale, frozen, drifted, mis-mapped readings alarmed with evidence and ground truth (`fdd-alarms.jsonl`); escalation route to a human |
| 7.4 | Reporting energy consumption, indoor conditions and possibilities for improvement | 0 (B) | 1 (A) | every decision record carries context, algorithms and validation; energy by consumer, comfort, IAQ and tank safety reported per day (`runner.areas`, `runner.pilot`) |
| 7.5 | Smart-grid integration (demand response) | 0 (B) | 1 (A) | demand-response profile on the day-ahead price, peak limiter and monthly peak budget on the grid tariff's power part (`demand_response`, `peak_limiter`, `peak_budget`) |
| 2.1 | Domestic hot-water storage control | n/a | n/a | The twin has no domestic hot water; SITE_001's electric hot water is a constant auxiliary load. A site with DHW adds a water-safety overlay before any energy function. |
| 6.1 | Blind control | n/a | n/a | No blinds in the twin. |

Class floor (lowest applicable function): P0 **D**, P3 **C**. Functions at each grade, P3: A 13, B 2, C 1, D 0; P0: A 2, B 3, C 5, D 6.

The class floor is the lowest grade of any applicable function, which is how the standard assigns a class; a single function at a low level holds the whole building down. The grade counts show where the caretaker sits per function.

## Office BAC factors

| Class | Thermal | Electrical |
|---|---:|---:|
| D | 1.51 | 1.10 |
| C | 1.00 | 1.00 |
| B | 0.80 | 0.93 |
| A | 0.70 | 0.87 |

## Cross-check, class C to A

- As-found energy the factors govern: thermal 34 766 kWh, electrical 60 981 kWh (equipment excluded).
- The factors say: 18 357 kWh a year (thermal 10 430, electrical 7 927).
- The simulation says: 22 229 kWh a year (ratio 1.21).

The BAC factors are statistical defaults for a typical office in the standard's reference climate, not a prediction for this building; the simulated saving is one building on one year of weather. Agreement in order of magnitude is the check; a ratio far from 1 says the twin's as-found case or its levers differ from the standard's reference, and why should be stated.

## EPBD context

Directive (EU) 2024/1275 (EPBD recast), Article 13:
- non-residential buildings with heating, air-conditioning or combined systems of effective rated output over 290 kW: building automation and control systems (continuous monitoring, logging, analysis and adjustment; benchmarking against reference values; fault detection and alerting; interoperability)
- the same for systems over 70 kW, by 31 December 2029

Norway's transposition through the EEA agreement is pending; the thresholds are given as the directive states them, as the market signal the caretaker's functions answer, not as a Norwegian legal requirement.
