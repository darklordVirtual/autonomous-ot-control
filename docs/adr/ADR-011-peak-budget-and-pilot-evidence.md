# ADR-011: A monthly peak budget, site-aware levers, and the pilot evidence pack

- Status: Accepted for the simulator. Not a physical-OT authorization. Not a measured saving.
- Date: 2026-10-28
- Related: ADR-005 (site data, savings, decision audit), ADR-007 (plant, tools, interlocks), ADR-009 (caretaker)
- Code: `runner/caretaker.py` (`PeakBudget`), `runner/calibration.py` (`size_plant`), `runner/site_calibration.py` (`monthly_check`), `twin/plant.py` (`hp_source_c`), `runner/tariffs.py`, `runner/pilot.py`, `runner/report_pilot.py`, `runner/peak_sweep.py`, `runner/report_demo.py`, `runner/bacs.py`
- Policy: `deploy/ot/site_policy.v1.json` (`peak_budget`, `purge_max_chiller_eer`)

## Context

The first run of every strategy on the twin calibrated to a measured office
(`site-001-v2`, 3 562 m², NO1, `docs/calibration.md`) showed where the money
is for a Norwegian commercial building, and where the caretaker was leaving
it:

1. **The grid tariff's power part dominates.** On the fixture's reference
   tariff the power part was 40 % of P0's annual cost; on Elvia's published
   2026 sheet (74 NOK/kW/month Oct–Mar, 31 Apr–Sep) it is 32 %. It is charged
   on the month's highest hourly mean kW, and that peak was set by the heat
   pump recovering the building after a setback: 158 kW in January for P0,
   and **higher** for P2 and P3 (166 and 160 kW) than for P1 (132 kW),
   because the deeper weekend setback and the cheap-hour tank charge both
   put the compressor at full output for an hour. The existing peak limiter
   is reactive (it caps at 60 % only after the building is within 10 % of a
   peak it has already set, and never during a recovery), so it could not
   prevent this.
2. **The cheap-hour tank charge costs more than it saves** on a heat-pump
   building: +5 K on a buffer is one hour of high compressor power, and the
   spot gain was already a negative result (`levers-2025.json`: 36 NOK).
3. **The summer night purge costs more than it saves** where mechanical
   cooling is nearly free: SITE_001 cools from its energy wells at an EER of
   about 40, and the purge ran the fans at SFP 0.7 to displace it (P3 used
   3 000 kWh more fan energy than P2 over the summer, for 200 kWh less
   cooling).
4. **The twin's plant was sized from the radiators.** `build_fixture` sets
   the heat pump's nominal output to the certificate's installed heating
   capacity (130 W/m²), which is the radiators, not the pump: a 463 kW heat
   pump that drew about 150 kW electric in a January recovery, on a site
   whose meters show weekday daytime medians near 30 kW (`site_E01` +
   `site_E02`). The monthly energy was right (the recovery is short) and the
   peaks were not; a power-part saving computed on that plant would have
   been an artefact. The first pack, on `site-001-v2` (three seeds, the
   2026-07 sheet, a 70 kW budget), showed P3pb at 58 260 NOK (21.0 %,
   seeds 20.2..21.8 %) a year, two thirds of it in the power part, with
   winter peaks cut from 141 to 87 kW; it is recorded here and was not
   published, because its plant is not the site's.
5. **The pilot conversation needs one document** that a building owner's
   adviser can check: the baseline model and its calibration statistics,
   the strategies, the saving with its uncertainty and its drivers, the
   tariff it is priced on, the non-energy outcomes, and the digest of every
   input, in the shape the M&V profession already uses (IPMVP Option D,
   ASHRAE Guideline 14).

## Decision

0. **The plant is sized from the design heat load** (`runner.calibration
   size-plant`, fixture `site-001-v3`): heat pump = 55 % of the design load
   (a pump covering ~55 % of the design load covers ~85–90 % of the heating
   energy, the certificate's 87 % heat-pump share), backup heater = the
   rest (the certificate's direct-electric share), a ground-source pump
   (constant brine temperature, no outdoor derating, no defrost: a new
   optional `hp_source_c` in the plant), the Carnot fraction set to the
   certificate's seasonal COP 4.28 at a 40 °C mean supply, and a buffer of
   25 l per kW. Every value is written into the fixture's
   `calibration.plant_sizing` with its assumptions. Checked month by month
   against the site's measured months without the hourly export
   (`runner.site_calibration --monthly-check`): total CV(RMSE) 12.2 %,
   NMBE 0.0 % (v2: 11.8 %, −0.7 %), Guideline 14 monthly met; the technical
   meter 19.1 % / −0.4 % (v2: 18.0 % / −2.4 %). The January peak is now
   105 kW for P0 and it is the backup heater, which is what the
   certificate's direct-electric share says it should be.
1. **A forward-looking monthly peak budget** (`PeakBudget`, policy
   `peak_budget`, off by default). The site sets a budget in kW, one value
   or one per month. Each step the caretaker caps the compressor at
   `(budget − other load) / full-output electrical draw`, clamped to
   `[min_fraction, 1]`, so that the hour stays under budget at any duty
   cycle. The full-output draw is **learned from the plant's own points**
   (`HP-01.ElectricPower / HP-01.MaxFraction` while running, exponential
   mean, with a stated prior), never read from the plant's configuration:
   the model is not the plant (ADR-009). The rest of the load is the energy
   meter minus the heat pump.
2. **Three releases, comfort and safety before the tariff:** frost
   protection; an occupied zone below the comfort floor plus
   `comfort_margin_k`; a tank near the backup heater's threshold
   (setpoint − 5 K + `tank_release_k`). A release sets the cap to 1 and is
   counted (`peak_budget_released`) and recorded.
3. **The buffer setpoint follows the capped tank.** Asking the tank for more
   than the capped compressor can deliver would only trigger the backup
   heater or IL-09. While a cap is binding the setpoint follows the tank
   (+3 K, the charging hysteresis) within IL-04's 3 K step; the lower supply
   temperature (`supply = min(curve, tank)`) is the throttle, and the lower
   tank temperature raises the COP. When the budget needs a cap set or
   tightened while the tank is short, the setpoint is brought down to the
   tank so that the write is valid now (IL-09 reads the proposal's setpoint)
   instead of the building running above budget for the steps the buffer
   would take to climb back.
4. **IL-09 in the validator governs the write, as in the twin's guard:** a
   cap may not be set or tightened while the tank is short; a cap already in
   force is held, not re-written. Before this change the validator failed
   any proposal that merely kept a cap while the tank cycled below
   setpoint − 2 K, which is why the reactive limiter was ineffective.
5. **No cheap-hour tank charge under a budget**; the weather-reset tank
   remains.
5b. **Under a budget the heat pump recovers alone.** Where the backup
   heater is the peak (SITE_001 as sized), capping the compressor does
   nothing; what sets the month's peak is the resistive backup firing for a
   recovery the compressor could make on its own, only slower. So under a
   budget the buffer setpoint never sits more than `backup_margin_k` (4.5 K)
   above the tank, the backup's threshold (setpoint − 5 K) is not reached by
   the caretaker's own request, and the setback is only as deep as the
   learned reheat rate recovers over the longest optimal-start lead
   (`recovery_setback+budget`). A deeper setback would be paid back at
   COP 1 in the hour that sets the peak. The comfort guard still restores
   the curve, and so the backup, when an occupied zone reaches the floor.
   The rest of the building's load, for the cap, excludes the backup heater,
   so a firing backup cannot drive the cap to its floor and starve the tank.
6. **The night purge runs only where it pays:** the chiller's observed EER
   (`CH-01.EER`, learned while cooling runs) must be at or below
   `purge_max_chiller_eer` (default 8). Energy wells at EER 40 never see a
   purge; a conventional chiller at EER 3 does.
7. **Named tariffs** (`runner/tariffs.py`): a run can be priced on a
   published tariff sheet, transcribed by hand with its URL, validity and
   exclusions, beside the fixture's declared reference tariff. The twin's
   control is not changed by the tariff, so one run is priced under every
   tariff after the fact.
8. **The pilot evidence pack** (`runner.pilot`): one command runs every
   strategy over the pinned scenario with several seeds, prices the runs
   under every tariff, and writes `pilot.json`, `pilot.md`, `pilot.html`,
   `manifest.json` (SHA-256 of fixture, scenario, every series with the
   scenario's declared digest verified, site policy, fallback, calibration
   file and the meter export's digest; git commit; seeds; overrides; command
   line), `monthly.csv`, the decision records of the first seed and the FDD
   alarms. The report opens with the saving and its seed range, the peak
   reduction and the non-energy outcomes, then what drives the number (a
   waterfall per consumer), the monthly peaks and costs, tariff sensitivity,
   governance counts, scope, and the evidence list. Strategy `P3pb` is P3
   with the budget on; `P3` is unchanged so that every earlier result stands.
9. **A BACS function audit** (`runner.bacs`) in the structure of
   EN ISO 52120-1: each function the twin can represent, the level P0 and P3
   reach with the data point or algorithm as evidence, the class floor, the
   office BAC factors beside the simulated saving, and the EPBD recast's
   Article 13 thresholds (290 kW now, 70 kW from 2030) as the market
   context. It is marked as a transcription and does not issue a class.

## Consequences

- On `site-001-v3`, NO1 2025, Elvia's 2026-07 sheet, a 60 kW budget: see
  `docs/results/2026-10-28/pilot-site-001/pilot.md` for the figures and the
  seed ranges. Seed 177 during development: P0 187 923 kWh, 244 557 NOK;
  P3 −7.2 % kWh, −11.1 % NOK; P3pb −11.9 % kWh, −18.4 % NOK, the backup
  heater 12 831 → 5 271 kWh, the winter peak mean 104 → 76 kW, with the
  cold months (January, February) unchanged at about 104 kW because the
  compressor cannot carry them and the comfort guard restores the backup.
  Comfort degree-hours 44 a year for P3 and P3pb against 0 for P0 and P1.
- On this plant the compressor cap almost never binds (3 steps a year):
  the budget's value is the heat-pump-only recovery and the recoverable
  setback, and the pack's sweep shows the number is insensitive to the
  budget's kW. On a plant where the compressor is the peak (`site-001-v2`,
  463 kW) the cap is the lever, and the same mode cut January from 160 to
  94 kW. A site's measured peaks say which case it is.
- What the sizing assumes, stated in the fixture and the pack's scope: the
  heat pump's share of the design load, the backup heater's size and
  staging rule, the buffer volume, the ground-source temperature and the
  seasonal COP. None is measured; the pilot's phase 0 replaces each with
  the plant's documentation and the meters' winter peaks.
- Every earlier report is unchanged: the policy default is off, `P3` does
  not read the budget, and the only behaviour change to `P3` is the purge
  rule, which the fixture-declared chiller EER of the demo buildings (about
  3–4) does not trigger. The validator's IL-09 semantics changed for held
  caps only; a new or tightened cap with a short tank is refused as before.
