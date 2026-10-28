"""The peak budget (ADR-011): a forward-looking cap on the heat pump under a monthly kW budget.

What is checked:
- the cap arithmetic and its clamps;
- the budget is learned from plant points only, never from the plant's configuration;
- over a cold week on the calibrated SITE_001 twin, the cap is valid at every write (no IL-09 fallback),
  the backup heater never starts because of the budget, occupied comfort holds, and the month's
  highest hourly mean falls below P3 without a budget;
- the validator's IL-09 semantics: a held cap is not a write, a tightening with a short tank is refused;
- the policy file's default is off, so every earlier result is unchanged.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from runner import caretaker as ck
from runner.areas import scenario_path
from runner.demo import STEP_S
from twin.model import Twin, load_config
from twin.scenarios import load_scenario

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "twin/fixtures/calibrated/site-001-v2.json"


def _twin(days: int = 7, start_day: int = 0) -> Twin:
    raw = json.loads(scenario_path("NO1").read_text("utf-8"))
    raw["duration_seconds"] = (start_day + days) * 86400
    raw["seed"] = 177
    return Twin(load_config(SITE), load_scenario(raw, base_dir=scenario_path("NO1").parent))


def test_cap_arithmetic_and_clamps():
    pb = ck.PeakBudget({"enabled": True, "kw": 90.0, "hp_full_kw_prior": 150.0, "min_fraction": 0.3})
    cap, ctx = pb.cap("2025-01", other_kw=15.0)
    assert cap == pytest.approx(0.5) and ctx["raw"] == pytest.approx(0.5)
    assert pb.cap("2025-01", other_kw=200.0)[0] == 0.3            # never below the floor
    assert ck.PeakBudget({"enabled": True, "kw": 400.0, "hp_full_kw_prior": 150.0}).cap("2025-01", 0.0)[0] == 1.0   # never above 1
    monthly = ck.PeakBudget({"enabled": True, "kw_by_month": {"01": 80, "2025-07": 40}, "hp_full_kw_prior": 100.0})
    assert monthly.budget_kw("2025-01") == 80 and monthly.budget_kw("2025-07") == 40 and monthly.budget_kw("2025-05") is None
    assert ck.PeakBudget({}).budget_kw("2025-01") is None         # off by default


def test_full_power_is_learned_from_points_not_configuration():
    pb = ck.PeakBudget({"enabled": True, "kw": 90.0})
    assert pb.cap("2025-01", 10.0) is None                        # no prior, nothing observed: no cap
    pb.observe({"HP-01.Running": 1.0, "HP-01.ElectricPower": 60_000.0}, fraction=0.5)
    assert pb.hp_full_kw == pytest.approx(120.0)
    pb.observe({"HP-01.Running": 0.0, "HP-01.ElectricPower": 0.0}, fraction=0.5)   # off: ignored
    assert pb.hp_full_kw == pytest.approx(120.0) and pb.observations == 1


def test_policy_default_is_off_and_p3_is_unchanged():
    pol = ck.load_policy()
    assert pol["peak_budget"]["enabled"] is False
    tw = _twin(days=2)
    ct = ck.Caretaker(tw, seed=177)
    assert ct.peak_budget.enabled is False and ct.policy_overrides_sha is None
    for t in range(0, 2 * 86400, STEP_S):
        ct.step(t)
        tw.advance(STEP_S)
    assert "peak_budget" not in ct.stats.algorithms and "peak_budget_hold" not in ct.stats.algorithms


def _week(budget_kw: float | None):
    tw = _twin(days=7)
    ov = {"peak_budget": {"enabled": True, "kw": budget_kw, "hp_full_kw_prior": 150.0}} if budget_kw else None
    ct = ck.Caretaker(tw, seed=177, policy_overrides=ov)
    lo, _ = tw.scenario.comfort_band()
    comfort_dh = backup_kwh = 0.0
    hourly: dict[str, float] = {}
    for t in range(0, 7 * 86400, STEP_S):
        ct.step(t)
        for _ in range(STEP_S // tw.step_s):
            tw._step()
            p = tw.points
            backup_kwh += p.get("HP-01.BackupHeaterPower", 0.0) * tw.step_s / 3.6e6
            if tw.scenario.occupied(tw.clock.now_s):
                comfort_dh += sum(max(lo - z.temp_c, 0.0) for z in tw.zones.values()) * tw.step_s / 3600
            h = tw.clock.utc_at(tw.clock.now_s).strftime("%Y-%m-%dT%H")
            hourly[h] = hourly.get(h, 0.0) + tw.power_w / 1000 * tw.step_s / 3600
    return ct, max(hourly.values()), comfort_dh, backup_kwh


def test_budget_week_on_site_001_caps_the_peak_without_fallback_backup_or_comfort_loss():
    base, base_peak, base_dh, base_backup = _week(None)
    ct, peak, dh, backup = _week(90.0)
    assert ct.policy_overrides_sha is not None
    assert ct.stats.routes["fallback"] == 0 and ct.stats.routes["escalate"] == 0
    assert "IL-09" not in ct.stats.violations and "IL-04:step" not in ct.stats.violations
    assert ct.stats.algorithms.get("peak_budget", 0) > 100
    assert backup == pytest.approx(0.0, abs=1e-6)
    assert dh <= base_dh + 1e-9
    assert peak < base_peak - 20.0, (peak, base_peak)
    assert ct.peak_budget.observations > 0 and 100 < ct.peak_budget.hp_full_kw < 200


def test_decision_record_carries_the_budget_and_the_overrides_digest():
    tw = _twin(days=1)
    ov = {"peak_budget": {"enabled": True, "kw": 90.0, "hp_full_kw_prior": 150.0}}
    ct = ck.Caretaker(tw, seed=177, policy_overrides=ov, record_days={"2025-01-01"})
    for t in range(0, 86400, STEP_S):
        ct.step(t)
        tw.advance(STEP_S)
    recs = [r for r in ct.records if r["peak_budget"]]
    assert recs and all(r["policy_overrides_sha256"] == ct.policy_overrides_sha for r in recs)
    assert any("budget_kw" in r["peak_budget"] for r in recs)


def test_validator_il09_refuses_a_tightening_with_a_short_tank_but_not_a_held_cap():
    tw = _twin(days=1)
    ct = ck.Caretaker(tw, seed=177)
    ct.step(0)
    tw.setpoints = replace(tw.setpoints, hp_max_fraction=0.6, tank_c=55.0)
    tw.plant_state = replace(tw.plant_state, tank_c=50.0)          # short: 50 < 55 - 2
    p = ct._propose(900, "night_setback", [], ct._telemetry(900), False, 8 * 3600, -5.0, -5.0, [], [], 0, True,
                    50.0, False, False)
    held = replace(p, hp_max_fraction=0.6, tank_c=55.0)
    assert "IL-09" not in ct.validate(held, 900, [])
    tightened = replace(p, hp_max_fraction=0.5, tank_c=55.0)
    assert "IL-09" in ct.validate(tightened, 900, [])
    tw.setpoints = replace(tw.setpoints, hp_max_fraction=1.0)
    newcap = replace(p, hp_max_fraction=0.6, tank_c=55.0)
    assert "IL-09" in ct.validate(newcap, 900, [])                 # a new cap with a short tank is a write
    assert "IL-09" not in ct.validate(replace(newcap, tank_c=51.9), 900, [])   # setpoint brought to the tank: valid
