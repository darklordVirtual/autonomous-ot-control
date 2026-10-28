"""P3, the caretaker: safety overlays, one base profile, an algorithm per setpoint, an independent validator.

The design follows a hybrid hierarchy:

    site policy (hard constraints) -> safety overlays -> one base profile
        -> one algorithm per setpoint -> proposal
        -> independent validator -> deterministic fallback if invalid
        -> decision record (what REMORA receives as evidence with the write)

The parts:
- **Overlays** are constraints, not competing profiles. `frost_protection`,
  `iaq_protection`, `icing_protection` and `telemetry_degraded` can all be
  active at once on top of any base profile. A demand-response hour cannot
  switch off frost protection.
- **Base profiles**, highest priority first: `comfort_priority` (occupied),
  `demand_response` (top-price hour, or power near the month's peak),
  `preconditioning` (an optimal-start recovery, or a high-price block ahead
  of occupancy), `night_setback` (>= 10 h to occupancy), `energy_saving`
  (otherwise). `balanced_default` is what the fallback runs.
- **Algorithms** are small, versioned and explainable. Every one is named in
  the decision record:
  - optimal start with a self-tuning reheat rate;
  - recovery-limited setback;
  - an unoccupied cooling setback;
  - ASHRAE Guideline 36 style Trim & Respond on the supply-air temperature;
  - a summer night purge through the heat-recovery bypass;
  - a weather-reset tank with price-ranked charging;
  - a peak limiter;
  - presence lighting with daylight dimming;
  - ground-sensor cables.
  None of them is an MPC. A model-predictive controller would slot in as
  another algorithm behind the same validator.
- **The validator** checks each proposal against `deploy/ot/site_policy.v1.json`
  and the active overlays. It reads the twin's own occupancy and state, never
  the optimizer's view of it. A failed proposal is replaced by the
  hash-pinned fallback in `deploy/ot/caretaker_fallback.v1.json`. That
  fallback reads no zone sensor, and it is validated too. If it also fails,
  the caretaker holds the current state and escalates.
- **Telemetry checks**: a reading older than the guard's observation age is
  stale. A reading that jumps more than is physically plausible in one step
  is suspect. So is one with the wrong unit, or one that does not carry the
  TFM identifier of that zone's temperature sensor (`twin.tfm`): a mis-mapped
  point. Either puts the zone on the fallback and escalates once. The
  zone recovers only when a recovery criterion holds (fresh again, or the
  reverse jump) for an hour, and never in under 24 h.
- **Optimizer faults** (`proposal_fault_rate`, seeded): a share of the
  proposals is corrupted before validation, as a defective or compromised
  optimizer would emit them. The validator must catch every one; `P3raw`
  applies them.

`P3raw` is the same proposal engine with the telemetry checks and the
validator removed: the B arm of an A/B/C comparison. P0 is A, P3 is C. It
runs offline only. A real building never receives an unvalidated write.

With REMORA in the loop, reads ACCEPT under the grounded-read rule, and each
submitted write goes as a VERIFY with its decision record as evidence.
`escalate` is the caretaker asking for a human. REMORA's own decision is
separate and is not predicted here.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from runner.demo import STEP_S, ZONES, ReheatLearner, next_step, p1_target
from twin.model import Twin
from twin.tfm import zone_sensor_tfm
from twin.plant import weather_compensated_supply_c

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "deploy" / "ot" / "site_policy.v1.json"
FALLBACK_PATH = ROOT / "deploy" / "ot" / "caretaker_fallback.v1.json"
VERSION = "p3/1"
LAB = "ZONE-03"
OVERLAYS = ("frost_protection", "iaq_protection", "icing_protection", "telemetry_degraded")
PROFILES = ("comfort_priority", "demand_response", "preconditioning", "night_setback", "energy_saving",
            "balanced_default")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    raw = json.loads(path.read_text("utf-8"))
    return {k: v["value"] for k, v in raw["constraints"].items()}


@dataclass
class Proposal:
    heating: dict[str, float]
    cooling: dict[str, float]
    supply_air_c: float
    tank_c: float
    hp_max_fraction: float
    ahu_enabled: bool
    cables: str
    lighting_mode: str = "presence"
    daylight_harvesting: bool = True
    co2_ppm: dict[str, float] = field(default_factory=dict)
    algorithms: dict[str, str] = field(default_factory=dict)


class PeakBudget:
    """Forward-looking cap on the heat pump so the building's hourly mean power
    stays under a monthly budget (the grid tariff's power part is charged on
    the month's highest hourly mean kW; ADR-011).

    The budget is a site value (`site_policy.peak_budget.kw_by_month`, or one
    `kw` for every month). The cap is derived from what the plant reports,
    never from its configuration: the heat pump's full-output electrical draw
    is learned as an exponential mean of `HP-01.ElectricPower / HP-01.MaxFraction`
    while it runs (prior: `hp_full_kw_prior`), and the rest of the building's
    power is read from the energy meter minus the heat pump. The cap is

        cap = clamp((budget_kw - other_kw) / hp_full_kw, min_fraction, 1)

    so that even at 100 % duty the hour stays under budget. Three guards release
    the cap, comfort and safety before the tariff: frost protection, an occupied
    zone below the comfort floor plus `comfort_margin_k`, and a tank within
    `tank_release_k` of the backup heater's threshold (setpoint - 5 K, COP 1).
    A cap is set or tightened only while the tank holds (IL-09); with a short
    tank the caretaker first brings the tank setpoint down to the tank so that
    the write is valid, and while a cap binds the setpoint follows the tank so
    that the caretaker never asks for heat the budget forbids (the lower supply
    temperature is the throttle). The cheap-hour tank charge is skipped.
    """

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.enabled = bool(cfg.get("enabled", False))
        self.kw_by_month: dict[str, float] = {str(k): float(v) for k, v in (cfg.get("kw_by_month") or {}).items()}
        self.kw_default = cfg.get("kw")
        self.min_fraction = float(cfg.get("min_fraction", 0.3))
        self.comfort_margin_k = float(cfg.get("comfort_margin_k", 0.3))
        self.tank_release_k = float(cfg.get("tank_release_k", 1.0))
        self.backup_margin_k = float(cfg.get("backup_margin_k", 4.5))
        self.hp_full_kw = float(cfg.get("hp_full_kw_prior", 0.0)) or None
        self.alpha = float(cfg.get("learning_rate", 0.05))
        self.observations = 0

    def budget_kw(self, month: str) -> float | None:
        """`month` is `YYYY-MM`; a budget keyed by month number (`"01"`) or by `YYYY-MM`."""
        if not self.enabled:
            return None
        v = self.kw_by_month.get(month, self.kw_by_month.get(month[5:7]))
        if v is None and self.kw_default is not None:
            v = float(self.kw_default)
        return v

    def observe(self, points: dict[str, float], fraction: float) -> None:
        if not self.enabled or points.get("HP-01.Running", 0.0) < 0.5 or fraction <= 0:
            return
        full_kw = points.get("HP-01.ElectricPower", 0.0) / 1000 / fraction
        if full_kw <= 0:
            return
        self.hp_full_kw = full_kw if self.hp_full_kw is None else (1 - self.alpha) * self.hp_full_kw + self.alpha * full_kw
        self.observations += 1

    def cap(self, month: str, other_kw: float) -> tuple[float, dict[str, float]] | None:
        budget = self.budget_kw(month)
        if budget is None or not self.hp_full_kw:
            return None
        raw = (budget - other_kw) / self.hp_full_kw
        cap = max(self.min_fraction, min(1.0, raw))
        return round(cap, 2), {"budget_kw": budget, "other_kw": round(other_kw, 2),
                               "hp_full_kw": round(self.hp_full_kw, 2), "raw": round(raw, 3)}


@dataclass
class Stats:
    profiles: dict[str, int] = field(default_factory=lambda: dict.fromkeys(PROFILES, 0))
    overlays: dict[str, int] = field(default_factory=lambda: dict.fromkeys(OVERLAYS, 0))
    routes: dict[str, int] = field(default_factory=lambda: dict.fromkeys(("submit", "hold", "fallback", "escalate"), 0))
    violations: dict[str, int] = field(default_factory=dict)
    algorithms: dict[str, int] = field(default_factory=dict)
    zone_fallback_steps: int = 0
    purge_steps: int = 0
    #: FDD scored against the injected faults (the detector never reads them).
    fdd_alarms: int = 0
    fdd_true_alarms: int = 0
    fdd_episodes: int = 0
    fdd_episodes_detected: int = 0
    #: Corrupted proposals injected, and how many of them the validator caught.
    optimizer_faults: dict[str, int] = field(default_factory=dict)
    optimizer_faults_caught: int = 0


class Caretaker:
    """Drive the twin's supervisory layer every 15 simulated minutes."""

    def __init__(self, tw: Twin, *, validated: bool = True, record_days: set[str] | None = None,
                 adaptive_deadband: bool = False, proposal_fault_rate: float = 0.0, seed: int = 0,
                 dispatcher: Callable[[str, dict[str, Any]], bool] | None = None,
                 policy_overrides: dict[str, Any] | None = None) -> None:
        self.tw, self.validated, self.adaptive_deadband = tw, validated, adaptive_deadband
        self.dispatcher = dispatcher
        self.proposal_fault_rate = proposal_fault_rate
        self._fault_rng = random.Random(f"{seed}:optimizer-faults")
        self.policy = load_policy()
        # Site-specific values a run may set on top of the policy file (a pilot's
        # peak budget, say). They are part of the decision record's provenance.
        self.policy_overrides = dict(policy_overrides or {})
        for k, v in self.policy_overrides.items():
            if isinstance(v, dict) and isinstance(self.policy.get(k), dict):
                self.policy[k] = {**self.policy[k], **v}
            else:
                self.policy[k] = v
        self.policy_overrides_sha = hashlib.sha256(
            json.dumps(self.policy_overrides, sort_keys=True).encode()).hexdigest() if self.policy_overrides else None
        self.peak_budget = PeakBudget(self.policy.get("peak_budget") or {})
        self.fallback = json.loads(FALLBACK_PATH.read_text("utf-8"))
        self.fallback_sha = _sha(FALLBACK_PATH)
        self.policy_sha = _sha(POLICY_PATH)
        self.learner = ReheatLearner()
        self.stats = Stats()
        self.records: list[dict[str, Any]] = []
        self.record_days = record_days or set()
        self.changes = 0
        self._prev_reading: dict[str, float] = {}
        self._fault: dict[str, dict[str, Any]] = {}
        self._sat = float(tw.setpoints.supply_air_c)
        self._purging = False
        self._budget_ctx: dict[str, Any] | None = None
        self._chiller_eer: float | None = None
        self._day_prices: dict[int, list[float]] = {}
        self._detected: set[tuple[str, str, int]] = set()
        self.alarms: list[dict[str, Any]] = []

    # -- context ----------------------------------------------------------------
    def _prices(self, day: int) -> list[float]:
        if day not in self._day_prices:
            sc = self.tw.scenario
            self._day_prices[day] = [sc.price_per_kwh(min(day * 86400 + h * 3600, sc.duration_seconds - 1))
                                     for h in range(24)]
        return self._day_prices[day]

    def _price_rank(self, t: int) -> tuple[float, float, list[int], list[int]]:
        """(percentile of this hour in its day, the day's spread, cheapest 4 hours, top 3 hours)."""
        ps = self._prices(t // 86400)
        hour = (t // 3600) % 24
        order = sorted(range(24), key=lambda h: ps[h])
        pct = order.index(hour) / 23
        spread = max(ps) - min(ps)
        return pct, spread, order[:4], order[-3:]

    def _next_occupancy(self, t: int, horizon: int = 3 * 86400) -> int | None:
        sc = self.tw.scenario
        for u in range(t, min(t + horizon, sc.duration_seconds), STEP_S):
            if sc.occupied(u):
                return u
        return None

    def _telemetry(self, t: int) -> dict[str, dict[str, Any]]:
        """Each zone's reading and whether the caretaker trusts it."""
        out = {}
        for z in ZONES:
            r = self.tw.read_zone(z)
            prev = self._prev_reading.get(z)
            stale = r.age_seconds > self.policy["max_observation_age_s"]
            jump = prev is not None and abs(r.measured_temp_c - prev) > self.policy["max_reading_jump_k_per_step"]
            wrong_unit = r.unit != "degC"
            wrong_tfm = r.tfm != zone_sensor_tfm(z)   # a mis-mapped point (AT-09)
            delta = 0.0 if prev is None else r.measured_temp_c - prev
            newly = False
            fault = self._fault.get(z)
            if self.validated and fault is None and (stale or jump or wrong_unit or wrong_tfm):
                rule = "stale" if stale else "unit" if wrong_unit else "tfm" if wrong_tfm else "jump"
                self._fault[z] = {"rule": rule, "sign": (delta > 0) - (delta < 0), "since": t, "recovered_at": None}
                newly = True
                self._alarm(t, z, r.measured_temp_c, prev, r.age_seconds, rule)
            elif fault is not None:
                # Recovery criteria: a stale sensor is fresh again; a jumped one has
                # jumped back by as much in the other direction; a wrong unit or
                # TFM identifier is right again. Then it must hold for recovery_hold_s, and the zone
                # stays distrusted for at least suspect_latch_s in all.
                rule = fault["rule"]
                if rule == "stale":
                    ok = not stale
                elif rule == "unit":
                    ok = not wrong_unit
                elif rule == "tfm":
                    ok = not wrong_tfm
                else:
                    ok = fault["recovered_at"] is not None or (jump and (delta > 0) - (delta < 0) == -fault["sign"])
                if not ok:
                    fault["recovered_at"] = None
                elif fault["recovered_at"] is None:
                    fault["recovered_at"] = t
                if (fault["recovered_at"] is not None
                        and t - fault["recovered_at"] >= self.policy["recovery_hold_s"]
                        and t - fault["since"] >= self.policy["suspect_latch_s"]):
                    del self._fault[z]
            self._prev_reading[z] = r.measured_temp_c
            suspect = self.validated and z in self._fault
            out[z] = {"temp_c": r.measured_temp_c, "age_s": r.age_seconds, "stale": stale, "jump": jump,
                      "suspect": suspect, "newly_suspect": newly}
        return out

    def _alarm(self, t: int, zone: str, reading: float, prev: float | None, age: int, rule: str) -> None:
        """Record an FDD alarm with its evidence, then score it against the injected faults."""
        truth = [d for d in self.tw.scenario.disturbances
                 if d.zone_id == zone and d.from_s - STEP_S <= t <= d.to_s + STEP_S]
        self.stats.fdd_alarms += 1
        self.stats.fdd_true_alarms += bool(truth)
        for d in truth:
            self._detected.add((d.kind, d.zone_id, d.from_s))
        self.alarms.append({"t_s": t, "utc": self.tw.clock.utc_at(t).isoformat().replace("+00:00", "Z"),
                            "zone": zone, "rule": rule, "reading_c": round(reading, 2),
                            "previous_c": None if prev is None else round(prev, 2), "age_s": age,
                            "threshold": {"max_observation_age_s": self.policy["max_observation_age_s"],
                                          "max_reading_jump_k_per_step": self.policy["max_reading_jump_k_per_step"]},
                            "action": "zone on the fallback until the recovery criterion holds; escalated",
                            "recovery": {"stale": "fresh for recovery_hold_s", "jump": "the reverse jump, then recovery_hold_s",
                                         "unit": "degC again for recovery_hold_s",
                                         "tfm": "the expected TFM identifier again for recovery_hold_s"}[rule],
                            "ground_truth": [d.kind for d in truth] or ["none (false alarm)"]})

    def finish(self) -> None:
        """Close the run: the FDD recall over the fault episodes that started in it."""
        dur = self.tw.scenario.duration_seconds
        eps = {(d.kind, d.zone_id, d.from_s) for d in self.tw.scenario.disturbances if d.from_s < dur}
        self.stats.fdd_episodes = len(eps)
        self.stats.fdd_episodes_detected = len(eps & self._detected)

    # -- one control step --------------------------------------------------------
    def step(self, t: int) -> dict[str, Any]:
        tw, sc, pol = self.tw, self.tw.scenario, self.policy
        tel = self._telemetry(t)
        occupied = sc.occupied(t)
        nxt = self._next_occupancy(t)
        to_occ = None if nxt is None else nxt - t
        out_c, mean24 = sc.outdoor_c(t), sc.mean_outdoor_24h(t)
        pct, spread, cheap, top = self._price_rank(t)
        if spread < 0.40:   # not worth the storage loss on a flat day
            cheap = []
        hour = (t // 3600) % 24
        pts = tw.points
        co2 = {z: pts.get(f"{z}.CO2", 420.0) for z in ZONES}
        wet = bool(pts.get("OUT-01.SurfaceWet", 0.0))
        lo_ice, hi_ice = pol["icing_band_c"]
        heating_season = bool(pts.get("HYD-01.HeatingSeason", 1.0))
        month = tw.clock.utc_at(t).strftime("%Y-%m")
        peak_kw = getattr(tw, "monthly_peak_kw", {}).get(month, 0.0)
        power_kw = tw.power_w / 1000
        tank = tw.plant_state.tank_c
        self.peak_budget.observe(pts, tw.setpoints.hp_max_fraction)

        # -- overlays (constraints on top of any profile) --
        overlays = []
        if (any(tw.zones[z].temp_c < pol["frost_overlay_zone_c"] for z in ZONES)
                or mean24 < pol["frost_overlay_outdoor_mean_c"]):
            overlays.append("frost_protection")
        if any(c > pol["iaq_overlay_co2_ppm"] for c in co2.values()):
            overlays.append("iaq_protection")
        if wet and lo_ice <= out_c <= hi_ice:
            overlays.append("icing_protection")
        if any(v["suspect"] for v in tel.values()):
            overlays.append("telemetry_degraded")

        # -- one base profile --
        high_price = spread >= 0.40 and hour in top
        dr_block_soon = spread >= 0.40 and any(((hour + k) % 24) in top for k in (1, 2))
        near_peak = peak_kw > 0 and power_kw > 0.9 * peak_kw
        recovering = any(self.learner.preheating(z) for z in ZONES)
        if occupied:
            profile = "comfort_priority"
        elif high_price or near_peak:
            profile = "demand_response"
        elif recovering or (heating_season and dr_block_soon and to_occ is not None and to_occ <= 6 * 3600):
            profile = "preconditioning"
        elif to_occ is None or to_occ >= 10 * 3600:
            profile = "night_setback"
        else:
            profile = "energy_saving"

        prop = self._propose(t, profile, overlays, tel, occupied, to_occ, out_c, mean24, cheap, top, hour,
                             heating_season, tank, near_peak, high_price)
        corrupted = None
        if self.proposal_fault_rate and self._fault_rng.random() < self.proposal_fault_rate:
            corrupted = self._fault_rng.choice(OPTIMIZER_FAULTS)
            prop = corrupt(prop, corrupted)
            self.stats.optimizer_faults[corrupted] = self.stats.optimizer_faults.get(corrupted, 0) + 1
        violations = self.validate(prop, t, overlays) if self.validated else []
        if corrupted and violations:
            self.stats.optimizer_faults_caught += 1
        route = "submit"
        used_fallback = False
        if violations:
            fb = self._fallback(t, overlays)
            fb_viol = self.validate(fb, t, overlays)
            if fb_viol:
                route = "escalate"
                prop = None
            else:
                route, prop, used_fallback = "fallback", fb, True
            for v in violations:
                self.stats.violations[v] = self.stats.violations.get(v, 0) + 1
        if any(v["newly_suspect"] for v in tel.values()):
            route = "escalate" if route == "submit" else route
        changed = self._apply(t, prop) if prop is not None else []
        if route == "submit" and not changed:
            route = "hold"

        st = self.stats
        st.profiles[profile] += 1
        for o in overlays:
            st.overlays[o] += 1
        st.routes[route] += 1
        if prop is not None:
            for a in set(prop.algorithms.values()):
                st.algorithms[a] = st.algorithms.get(a, 0) + 1
        st.zone_fallback_steps += sum(1 for v in tel.values() if v["suspect"])
        st.purge_steps += self._purging

        rec = None
        day = tw.clock.utc_at(t).date().isoformat()
        if day in self.record_days:
            ctx = {"price_nok_per_kwh": round(sc.price_per_kwh(t), 4), "price_percentile_day": round(pct, 3),
                   "price_spread_day": round(spread, 3), "outdoor_c": round(out_c, 2), "outdoor_mean_24h_c": round(mean24, 2),
                   "occupied": occupied, "next_occupancy_h": None if to_occ is None else round(to_occ / 3600, 2),
                   "heating_season": heating_season, "surface_wet": wet, "tank_c": round(tank, 2),
                   "power_kw": round(power_kw, 2), "month_peak_kw": round(peak_kw, 2),
                   "co2_ppm": {z: round(c) for z, c in co2.items()},
                   "telemetry": {z: {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()}
                                 for z, r in tel.items()}}
            rec = {"schema": "ot-caretaker-decision/v1", "engine": VERSION, "validated": self.validated,
                   "t_s": t, "utc": tw.clock.utc_at(t).isoformat().replace("+00:00", "Z"),
                   "context": ctx,
                   "context_sha256": hashlib.sha256(json.dumps(ctx, sort_keys=True).encode()).hexdigest(),
                   "site_policy_sha256": self.policy_sha,
                   "policy_overrides_sha256": self.policy_overrides_sha,
                   "peak_budget": getattr(self, "_budget_ctx", None),
                   "overlays": overlays, "base_profile": profile,
                   "algorithms": prop.algorithms if prop else {}, "proposal": _plain(prop) if prop else None,
                   "validation": {"ok": not violations, "violations": violations},
                   "fallback": {"used": used_fallback, "sha256": self.fallback_sha} if used_fallback else None,
                   "changes": changed, "route": route}
            self.records.append(rec)
        return rec or {"route": route}

    # -- proposal ---------------------------------------------------------------------
    def _propose(self, t: int, profile: str, overlays: list[str], tel: dict[str, dict[str, Any]],
                 occupied: bool, to_occ: int | None, out_c: float, mean24: float, cheap: list[int],
                 top: list[int], hour: int, heating_season: bool, tank: float, near_peak: bool,
                 high_price: bool) -> Proposal:
        tw, sc, pol = self.tw, self.tw.scenario, self.policy
        pts = tw.points
        algos: dict[str, str] = {}
        heating: dict[str, float] = {}
        frost = "frost_protection" in overlays
        month = tw.clock.utc_at(t).strftime("%Y-%m")
        budget_active = self.peak_budget.enabled and self.peak_budget.budget_kw(month) is not None
        for z in ZONES:
            reading = tel[z]["temp_c"]
            if tel[z]["suspect"]:
                heating[z] = self._fallback_heating(t, z)
                algos[f"{z}.heating"] = "fallback_schedule"
                continue
            tgt, why = p1_target(sc, t, z, reading, self.learner, max_lead_h=12.0)
            self.learner.observe(z, t, reading, why.startswith("optimal start"))
            algo = "occupied_schedule" if why == "occupied" else (
                "constant_laboratory" if z == LAB else "optimal_start" if why.startswith("optimal") else "setback")
            if z != LAB and tgt < 21.0 and not self.learner.preheating(z):
                if to_occ is None or to_occ >= 10 * 3600:
                    tgt = pol["setback_floor_c"] if mean24 >= 0 else 17.0 if mean24 >= -5 else 18.0
                    algo = "recovery_setback"
                    if budget_active:
                        # Only as deep as the compressor can recover on its own before
                        # occupancy (ADR-011): the learned reheat rate (observed under the
                        # budget, so without the backup heater) over the longest optimal-start
                        # lead, less its margin hour. A deeper setback would be paid back by
                        # the backup heater at COP 1, in the hour that sets the month's peak.
                        rate = self.learner.rate_for(z, out_c)
                        recoverable = max(0.0, (12.0 - 1.0) * rate)
                        floor = round(21.0 - recoverable, 1)
                        if floor > tgt:
                            tgt, algo = floor, "recovery_setback+budget"
                if profile == "demand_response" and high_price:
                    tgt = max(pol["setback_floor_c"], tgt - 1.0)
                    algo = "dr_offset"
            if (profile == "preconditioning" and z != LAB and to_occ is not None and to_occ <= 3 * 3600
                    and any(((hour + k) % 24) in top for k in (1, 2))):
                tgt = min(21.5, max(tgt, 21.0) + 0.5)
                algo = "dr_precondition"
            if self.adaptive_deadband and algo == "occupied_schedule" and z != LAB:
                # Adaptive deadband: in an expensive hour the occupied heating
                # setpoint gives way by up to 0.5 K, never below the comfort
                # floor plus a 0.5 K margin (delta = min(0.5, 0.5 * z_p),
                # z_p = the price's excess over the day's median, relative).
                # Off by default: measured on NO1 2025 it saved 9 kWh and 31 NOK
                # spot but cost 268 NOK more power charge, because the room
                # reheats after the expensive hour (ADR-009, negative result).
                ps = sorted(self._prices(t // 86400))
                med = (ps[11] + ps[12]) / 2
                zp = max(0.0, (sc.price_per_kwh(t) - med) / med) if med > 0 else 0.0
                delta = min(0.5, 0.5 * zp)
                if delta >= 0.1:
                    tgt = max(pol["occupied_heating_min_c"] + 0.5, tgt - round(delta, 1))
                    algo = "adaptive_deadband"
            if frost:
                tgt = max(tgt, pol["frost_overlay_heating_min_c"])
                algo += "+frost"
            heating[z] = tgt
            algos[f"{z}.heating"] = algo

        # Cooling: in band while occupied (and 1 h before), set back when empty.
        cooling = {}
        soon = occupied or (to_occ is not None and to_occ <= 3600)
        for z in ZONES:
            c = 23.5 if (soon or z == LAB) else pol["cooling_max_c"]
            cooling[z] = c
        algos["cooling"] = "occupied_cooling" if soon else "unoccupied_cooling_setback"

        # Summer night purge through the HRV bypass.
        temps = [tel[z]["temp_c"] for z in ZONES if not tel[z]["suspect"]] or [tw.zones[z].temp_c for z in ZONES]
        zmean = sum(temps) / len(temps)
        night = hour >= 20 or hour < 4
        # A purge only pays where it displaces mechanical cooling that costs
        # something: the fans run at SFP while the cooling they avoid may come
        # at an EER of 30+ from energy wells (SITE_001). The chiller's observed
        # EER is learned from CH-01.EER while cooling runs; above
        # purge_max_chiller_eer the purge is skipped (ADR-011).
        eer = pts.get("CH-01.EER", 0.0)
        if pts.get("CH-01.CoolingLoad", 0.0) > 0 and eer > 0:
            self._chiller_eer = eer if self._chiller_eer is None else 0.95 * self._chiller_eer + 0.05 * eer
        purge_pays = self._chiller_eer is None or self._chiller_eer <= pol.get("purge_max_chiller_eer", 8.0)
        if self._purging:
            self._purging = (purge_pays and not heating_season and not occupied and night and zmean > 21.0
                             and out_c < zmean - 2.0)
        else:
            self._purging = (purge_pays and not heating_season and not occupied and night and zmean > 22.5
                             and 10.0 <= out_c < zmean - 3.0)

        # Supply air: Trim & Respond outside the heating season, a fixed reset in it.
        if self._purging:
            target_sat = pol["supply_air_min_c"]
            algos["supply_air"] = "night_purge"
        elif heating_season:
            target_sat = 19.0
            algos["supply_air"] = "fixed_reset"
        else:
            requests = sum(1 for z in ZONES if not tel[z]["suspect"] and tel[z]["temp_c"] > cooling[z] - 0.5)
            if requests > 0:   # respond: colder air, at most 1 K per step
                target_sat = self._sat - min(0.5 * requests, 1.0)
            else:              # trim: warmer air, less coil cooling
                target_sat = self._sat + 0.5
            algos["supply_air"] = "trim_respond"
        sat = max(pol["supply_air_min_c"], min(pol["supply_air_max_c"], target_sat))
        sat = self._sat + max(-pol["supply_air_max_step_k"], min(pol["supply_air_max_step_k"], sat - self._sat))

        ahu = (occupied or (to_occ is not None and to_occ <= 3600) or self._purging
               or "iaq_protection" in overlays)
        algos["ahu"] = "occupancy_schedule" + ("+purge" if self._purging else "")

        # Tank: weather reset, charged in the day's cheapest hours, held before a price block.
        # Under a peak budget the cheap-hour charge is skipped: a +5 K charge of the
        # buffer is one hour of high compressor power, exactly what the budget pays for
        # (ADR-011; the price shift was already a negative result on its own).
        curve_c = weather_compensated_supply_c(out_c)
        need = curve_c + 5.0
        base = min(55.0, max(45.0, need))
        if hour in cheap and heating_season and not budget_active:
            tgt_tank, algos["tank"] = min(pol["tank_max_c"], base + 5.0), "price_ranked_charge"
        else:
            tgt_tank, algos["tank"] = base, "weather_reset"
        cur = tw.setpoints.tank_c
        tank_sp = cur + max(-pol["tank_max_step_k"], min(pol["tank_max_step_k"], tgt_tank - cur))

        cap = 1.0
        algos["heat_pump"] = "uncapped"
        recovering = any(self.learner.preheating(z) for z in ZONES)
        if not frost and not recovering and (near_peak or (profile == "demand_response" and high_price)) \
                and tank >= tank_sp - 2.0:
            cap, algos["heat_pump"] = 0.6, "peak_limiter"
        # Peak budget (ADR-011): forward-looking, independent of the reactive limiter above.
        self._budget_ctx = None
        if budget_active:
            # The rest of the building, without the heat pump and without the backup heater:
            # a firing backup must not drive the cap to its floor (that would starve the tank
            # further and keep the backup on); the backup is kept off by the setpoint below.
            other_kw = max(0.0, (tw.power_w - pts.get("HP-01.ElectricPower", 0.0)
                                 - pts.get("HP-01.BackupHeaterPower", 0.0)) / 1000)
            comfort_short = occupied and any(
                not tel[z]["suspect"] and tel[z]["temp_c"] < pol["occupied_heating_min_c"] + self.peak_budget.comfort_margin_k
                for z in ZONES)
            # The tank is short when the backup heater (COP 1, at setpoint - 5 K) is near.
            # A slower recovery under the cap is the budget's price; the self-tuning
            # optimal start sees the slower reheat and starts earlier.
            tank_short = tank < cur - 5.0 + self.peak_budget.tank_release_k
            budget = self.peak_budget.cap(month, other_kw)
            released = "frost" if frost else "comfort" if comfort_short else "tank" if tank_short else None
            if released:
                # Comfort and safety before the tariff: the cap goes, and for frost or an
                # occupied zone at the floor the setpoint goes back to the curve, so the
                # backup heater may fire. A tank near the backup threshold releases the
                # cap only; the setpoint keeps following the tank (below), which is what
                # keeps the backup off when the compressor is already at full output.
                cap, algos["heat_pump"] = 1.0, "peak_budget_released"
                self._budget_ctx = {"released": released}
            elif budget is not None:
                cap_b, ctx = budget
                if tank >= round(tank_sp, 2) - 2.0:           # IL-09: a cap only while the tank holds
                    if cap_b < cap:
                        cap, algos["heat_pump"] = cap_b, "peak_budget"
                elif cap_b < min(cap, tw.setpoints.hp_max_fraction) and tank >= cur - pol["tank_max_step_k"] - 1.99:
                    # A short tank and a cap to set or tighten (after a release, at the
                    # start, or when the rest of the building's load rose): bring the
                    # setpoint down to the tank so the cap is valid now (IL-09 reads the
                    # proposal's setpoint), instead of running above budget for the steps
                    # it would take the buffer to climb back within 2 K of the old setpoint.
                    tank_sp = round(max(pol["tank_min_c"], cur - pol["tank_max_step_k"], tank + 1.99), 2)
                    cap, algos["heat_pump"] = cap_b, "peak_budget"
                elif tw.setpoints.hp_max_fraction < 1.0:      # hold what is set
                    cap, algos["heat_pump"] = tw.setpoints.hp_max_fraction, "peak_budget_hold"
                self._budget_ctx = ctx
            if released in (None, "tank"):
                # Ask the buffer for no more than the compressor can hold. The setpoint
                # follows the tank: +3 K (the charging hysteresis) while a cap binds, and
                # never more than backup_margin_k above the tank otherwise, so the resistive
                # backup heater (at setpoint - 5 K, COP 1) never fires for a recovery the
                # compressor can make on its own, only slower. Within IL-04's step. The
                # lower supply temperature is the throttle (supply = min(curve, tank)).
                lead = 3.0 if cap < 1.0 else self.peak_budget.backup_margin_k
                follow = round(max(pol["tank_min_c"], min(tank_sp, tank + lead)), 2)
                tank_sp = round(max(cur - pol["tank_max_step_k"], follow), 2)
                if tank_sp < round(base, 2):
                    algos["tank"] = algos["tank"] + "+budget_follow"
        algos["lighting"] = "presence_daylight"
        algos["cables"] = "ground_sensor"
        return Proposal(heating=heating, cooling=cooling, supply_air_c=round(sat, 2), tank_c=round(tank_sp, 2),
                        hp_max_fraction=cap, ahu_enabled=ahu, cables="sensor",
                        co2_ppm={z: zs.co2_ppm for z, zs in tw.setpoints.zones.items()}, algorithms=algos)

    # -- fallback ---------------------------------------------------------------------
    def _fallback_heating(self, t: int, z: str) -> float:
        fb = self.fallback["heating"]
        if z == LAB:
            return fb["laboratory_c"]
        sc = self.tw.scenario
        soon = sc.occupied(t) or any(sc.occupied(min(t + k, sc.duration_seconds - 1))
                                     for k in range(0, fb["occupied_or_within_s"] + 1, STEP_S))
        return fb["occupied_c"] if soon else fb["otherwise_c"]

    def _fallback(self, t: int, overlays: list[str]) -> Proposal:
        fb, sc, tw = self.fallback, self.tw.scenario, self.tw
        heating = {z: self._fallback_heating(t, z) for z in ZONES}
        if "frost_protection" in overlays:
            heating = {z: max(v, self.policy["frost_overlay_heating_min_c"]) for z, v in heating.items()}
        within = fb["ahu"]["on_when_occupied_or_within_s"]
        ahu = sc.occupied(t) or any(sc.occupied(min(t + k, sc.duration_seconds - 1))
                                    for k in range(0, within + 1, STEP_S)) or "iaq_protection" in overlays
        tk = fb["tank"]
        tgt = min(tk["max_c"], max(tk["min_c"], weather_compensated_supply_c(sc.outdoor_c(t)) + tk["follow_weather_curve_plus_k"]))
        cur = tw.setpoints.tank_c
        tank_sp = cur + max(-self.policy["tank_max_step_k"], min(self.policy["tank_max_step_k"], tgt - cur))
        sat = self._sat + max(-1.0, min(1.0, fb["supply_air_c"] - self._sat))
        return Proposal(heating=heating, cooling=dict.fromkeys(ZONES, fb["cooling_c"]), supply_air_c=round(sat, 2),
                        tank_c=round(tank_sp, 2), hp_max_fraction=fb["hp_max_fraction"], ahu_enabled=ahu,
                        cables=fb["cables"], lighting_mode=fb["lighting"]["mode"],
                        daylight_harvesting=fb["lighting"]["daylight_harvesting"],
                        co2_ppm={z: zs.co2_ppm for z, zs in tw.setpoints.zones.items()},
                        algorithms=dict.fromkeys(("heating", "cooling", "supply_air", "tank", "ahu"), "fallback"))

    # -- validator (independent of the proposal engine) --------------------------------
    def validate(self, p: Proposal, t: int, overlays: list[str]) -> list[str]:
        """Every hard constraint the proposal breaks, by interlock id. Reads the twin, not the caretaker."""
        tw, sc, pol = self.tw, self.tw.scenario, self.policy
        occupied = sc.occupied(t)
        v: list[str] = []
        for z in ZONES:
            h, c = p.heating[z], p.cooling[z]
            if c < h + pol["heating_cooling_deadband_k"]:
                v.append(f"IL-01:{z}")
            if occupied and h < pol["occupied_heating_min_c"]:
                v.append(f"IL-02:{z}")
            if h < max(pol["frost_floor_c"], pol["setback_floor_c"]):
                v.append(f"IL-03:{z}")
            if "frost_protection" in overlays and h < pol["frost_overlay_heating_min_c"]:
                v.append(f"OVL-frost:{z}")
            if c > pol["cooling_max_c"]:
                v.append(f"cooling_max:{z}")
            if not pol["co2_setpoint_min_ppm"] <= p.co2_ppm.get(z, 900.0) <= pol["co2_setpoint_max_ppm"]:
                v.append(f"IL-07:{z}")
        if not pol["tank_min_c"] <= p.tank_c <= pol["tank_max_c"]:
            v.append("IL-04:range")
        if abs(p.tank_c - tw.setpoints.tank_c) > pol["tank_max_step_k"] + 1e-9:
            v.append("IL-04:step")
        if not pol["supply_air_min_c"] <= p.supply_air_c <= pol["supply_air_max_c"]:
            v.append("IL-05:range")
        if abs(p.supply_air_c - tw.setpoints.supply_air_c) > pol["supply_air_max_step_k"] + 1e-9:
            v.append("IL-11:supply_air_step")
        if occupied and not p.ahu_enabled:
            v.append("IL-06")
        if "iaq_protection" in overlays and not p.ahu_enabled:
            v.append("OVL-iaq")
        if occupied and p.lighting_mode not in ("presence", "schedule"):
            v.append("IL-08")
        # IL-09 governs the write: a cap may not be set or tightened while the tank is
        # short (the twin's guard refuses exactly that). A cap already in force is
        # held, not re-written; the peak budget releases it at tank_release_k, before
        # the backup heater would start (ADR-011).
        if (p.hp_max_fraction < 1.0 and p.hp_max_fraction < tw.setpoints.hp_max_fraction - 1e-9
                and tw.plant_state.tank_c < p.tank_c - 2.0):
            v.append("IL-09")
        if p.hp_max_fraction < 1.0 and "frost_protection" in overlays:
            v.append("OVL-frost:hp_cap")
        if p.cables in ("off", "thermostat") and "icing_protection" in overlays:
            v.append("IL-10")
        return v

    # -- apply ------------------------------------------------------------------------
    def tool_calls(self, p: Proposal) -> list[dict[str, Any]]:
        """Decompose a validated proposal into governed tool calls (PR-01..PR-05 ordering).

        Each returned item has ``tool_name``, ``arguments``, ``label`` and ``algorithm``.
        When raising a zone's heating setpoint toward its cooling setpoint, the cooling
        setpoint moves first so the IL-01 deadband holds at every intermediate step.
        """
        tw = self.tw
        sp = tw.setpoints
        calls: list[dict[str, Any]] = []
        algos = p.algorithms or {}
        for z in ZONES:
            cur_h = tw.zones[z].setpoint_c
            nv = next_step(cur_h, p.heating[z])
            zs = sp.zones[z]
            eff_h = nv if nv is not None else cur_h
            cooling = round(max(p.cooling[z], eff_h + 2.5), 1)
            cool_changed = abs(cooling - zs.cooling_c) > 1e-6
            # PR-01: if heating rises and would narrow the current deadband, raise cooling first.
            if cool_changed and nv is not None and nv > cur_h and cooling > zs.cooling_c:
                calls.append({"tool_name": "set_zone_cooling_setpoint",
                              "arguments": {"zone_id": z, "cooling_c": cooling},
                              "label": f"{z}.CoolingSetpoint={cooling}",
                              "algorithm": algos.get("cooling", "cooling")})
            if nv is not None:
                calls.append({"tool_name": "set_zone_setpoint",
                              "arguments": {"zone_id": z, "setpoint_c": nv},
                              "label": f"{z}.HeatingSetpoint={nv}",
                              "algorithm": algos.get(f"{z}.heating", "heating")})
            if cool_changed and not (nv is not None and nv > cur_h and cooling > zs.cooling_c):
                calls.append({"tool_name": "set_zone_cooling_setpoint",
                              "arguments": {"zone_id": z, "cooling_c": cooling},
                              "label": f"{z}.CoolingSetpoint={cooling}",
                              "algorithm": algos.get("cooling", "cooling")})
            if zs.lighting_mode != p.lighting_mode or zs.daylight_harvesting is not p.daylight_harvesting:
                calls.append({"tool_name": "set_zone_lighting_mode",
                              "arguments": {"zone_id": z, "mode": p.lighting_mode,
                                            "daylight_harvesting": p.daylight_harvesting},
                              "label": f"{z}.Lighting",
                              "algorithm": algos.get("lighting", "presence_daylight")})
            co2_tgt = int(round(p.co2_ppm.get(z, zs.co2_ppm)))
            if abs(co2_tgt - zs.co2_ppm) > 1e-6:
                calls.append({"tool_name": "set_zone_co2_setpoint",
                              "arguments": {"zone_id": z, "co2_ppm": co2_tgt},
                              "label": f"{z}.CO2Setpoint={co2_tgt}",
                              "algorithm": algos.get("co2", "dcv")})
        # PR-02: morning start sets supply air before enabling AHU when warming up.
        sat = round(round(p.supply_air_c / 0.5) * 0.5, 1)
        if abs(sat - sp.supply_air_c) > 1e-6:
            calls.append({"tool_name": "set_supply_air_setpoint",
                          "arguments": {"supply_air_c": sat},
                          "label": f"supply_air_c={sat}",
                          "algorithm": algos.get("supply_air", "supply_air")})
        if p.ahu_enabled != sp.ahu_enabled:
            calls.append({"tool_name": "set_ahu_enabled",
                          "arguments": {"enabled": p.ahu_enabled},
                          "label": f"ahu_enabled={p.ahu_enabled}",
                          "algorithm": algos.get("ahu", "occupancy_schedule")})
        # PR-03 / PR-04: release HP cap before raising tank, or raise tank before capping HP.
        tank_sp = round(round(p.tank_c / 0.5) * 0.5, 1)
        hp_cap = round(round(p.hp_max_fraction / 0.05) * 0.05, 2)
        if hp_cap > sp.hp_max_fraction + 1e-6:
            calls.append({"tool_name": "set_heat_pump_limit",
                          "arguments": {"max_fraction": hp_cap},
                          "label": f"hp_max_fraction={hp_cap}",
                          "algorithm": algos.get("heat_pump", "uncapped")})
        if abs(tank_sp - sp.tank_c) > 1e-6:
            calls.append({"tool_name": "set_tank_setpoint",
                          "arguments": {"tank_c": tank_sp},
                          "label": f"tank_c={tank_sp}",
                          "algorithm": algos.get("tank", "weather_reset")})
        if hp_cap < sp.hp_max_fraction - 1e-6:
            calls.append({"tool_name": "set_heat_pump_limit",
                          "arguments": {"max_fraction": hp_cap},
                          "label": f"hp_max_fraction={hp_cap}",
                          "algorithm": algos.get("heat_pump", "peak_limiter")})
        for circuit in ("CABLE-RAMP", "CABLE-GUTTER"):
            if sp.cable_modes.get(circuit, "auto") != p.cables:
                calls.append({"tool_name": "set_heating_cable_mode",
                              "arguments": {"circuit": circuit, "mode": p.cables},
                              "label": f"{circuit}.Mode={p.cables}",
                              "algorithm": algos.get("cables", "ground_sensor")})
        return calls

    def _apply(self, t: int, p: Proposal) -> list[str]:
        if self.dispatcher is not None:
            changed = []
            for c in self.tool_calls(p):
                if self.dispatcher(c["tool_name"], c["arguments"]):
                    if c["tool_name"] == "set_zone_setpoint":
                        self.changes += 1
                    changed.append(c["label"])
            self._sat = self.tw.setpoints.supply_air_c
            return changed
        tw = self.tw
        changed = []
        for z in ZONES:
            nv = next_step(tw.zones[z].setpoint_c, p.heating[z])   # IL-11: <= 1 K per change
            if nv is not None:
                rec, _ = tw.apply_setpoint({"operation_id": f"P3-{t}-{z}", "zone_id": z, "setpoint_c": nv,
                                            "units": "degC", "expected_state_revision": tw.revision})
                if rec.status == "APPLIED":
                    self.changes += 1
                    changed.append(f"{z}.HeatingSetpoint={nv}")
        sp = tw.setpoints
        zones = {}
        for z, zs in sp.zones.items():
            cooling = max(p.cooling[z], tw.zones[z].setpoint_c + 2.5)
            new = replace(zs, cooling_c=cooling, lighting_mode=p.lighting_mode,
                          daylight_harvesting=p.daylight_harvesting)
            if new != zs:
                changed.append(f"{z}.CoolingSetpoint={cooling}" if cooling != zs.cooling_c else f"{z}.Lighting")
            zones[z] = new
        new_sp = replace(sp, zones=zones, supply_air_c=p.supply_air_c, tank_c=p.tank_c,
                         hp_max_fraction=p.hp_max_fraction, ahu_enabled=p.ahu_enabled,
                         cable_modes={"CABLE-RAMP": p.cables, "CABLE-GUTTER": p.cables})
        for k in ("supply_air_c", "tank_c", "hp_max_fraction", "ahu_enabled", "cable_modes"):
            if getattr(new_sp, k) != getattr(sp, k):
                changed.append(f"{k}={getattr(new_sp, k)}")
        tw.setpoints = new_sp
        self._sat = p.supply_air_c
        return changed


OPTIMIZER_FAULTS = ("tank_overtemperature", "supply_air_too_cold", "ahu_off", "cables_off",
                    "heating_too_low", "deadband_inverted")


def corrupt(p: Proposal, kind: str) -> Proposal:
    """A proposal as a defective optimizer would emit it (test injection only)."""
    if kind == "tank_overtemperature":
        return replace(p, tank_c=70.0)
    if kind == "supply_air_too_cold":
        return replace(p, supply_air_c=10.0)
    if kind == "ahu_off":
        return replace(p, ahu_enabled=False)
    if kind == "cables_off":
        return replace(p, cables="off")
    if kind == "heating_too_low":
        return replace(p, heating=dict.fromkeys(p.heating, 12.0))
    if kind == "deadband_inverted":
        return replace(p, cooling={z: h - 1.0 for z, h in p.heating.items()})
    raise ValueError(kind)


def _plain(p: Proposal) -> dict[str, Any]:
    d = asdict(p)
    d.pop("algorithms")
    return d
