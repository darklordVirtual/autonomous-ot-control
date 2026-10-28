"""The pilot evidence pack: tariff registry, repricing, summary statistics, manifest and reports.

The pricing and summary are checked on synthetic runs built in the test (two strategies, two seeds,
twelve months), so the arithmetic is verifiable by hand; the manifest and reports are checked on a
two-day real run of the calibrated fixture.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from runner import bacs, pilot, tariffs
from runner.report_pilot import render_html, render_markdown

ROOT = Path(__file__).resolve().parents[2]


def test_tariff_registry_has_the_published_sheets_and_applies_to_a_config():
    cur = tariffs.get_tariff("elvia-stor-naering-lavspent-2026-07")
    assert cur["power_nok_per_kw_month"] == {"winter": 111.0, "summer": 46.0} and cur["fixed_nok_per_month"] == 500.0
    t = tariffs.get_tariff("elvia-stor-naering-lavspent-2026-01")
    assert t["power_nok_per_kw_month"] == {"winter": 74.0, "summer": 31.0}
    assert set(t["winter_months"]) == {10, 11, 12, 1, 2, 3} and t["energy_nok_per_kwh"] == 0.05
    assert t["source"]["kind"] == "published_tariff_sheet" and t["source"]["url"].startswith("https://www.elvia.no/")
    cfg = json.loads((ROOT / "twin/fixtures/calibrated/site-001-v2.json").read_text("utf-8"))
    priced = tariffs.apply_tariff(cfg, "elvia-stor-naering-lavspent-2026-01")
    assert priced["plant"]["grid_tariff"]["tariff_id"] == "elvia-stor-naering-lavspent-2026-01"
    assert cfg["plant"]["grid_tariff"].get("tariff_id") is None       # the input is not mutated
    assert tariffs.describe(priced)["source"]["kind"] == "published_tariff_sheet"
    assert tariffs.describe(cfg)["tariff_id"] == "fixture-declared"
    with pytest.raises(KeyError):
        tariffs.get_tariff("no-such-tariff")


def _synthetic_run(strategy: str, seed: int, kwh_per_day: float, peak_kw: float) -> dict:
    days = []
    for m in range(1, 13):
        for d in range(1, 3):
            days.append({"date": f"2025-{m:02d}-{d:02d}", "kwh": kwh_per_day, "spot_nok": kwh_per_day * 1.0,
                         "grid_energy_nok": 0.0, "comfort_dh": 0.0, "hazard_h": 0.0, "heating_season_h": 0.0,
                         "co2_excess_ppmh": 0.0, "tank_over_60_h": 0.0,
                         **{k: kwh_per_day / len(pilot.METERS) for k in pilot.METERS}})
    peaks = {f"2025-{m:02d}": peak_kw for m in range(1, 13)}
    return {"area": "NO1", "strategy": strategy, "seed": seed, "days": days, "faults": False,
            "monthly_peak_kw": peaks, "monthly_power_nok": dict.fromkeys(peaks, 0.0), "setpoint_changes": 0}


def test_repricing_and_summary_arithmetic_on_synthetic_runs():
    runs = [_synthetic_run("P0", 1, 100.0, 50.0), _synthetic_run("P0", 2, 100.0, 50.0),
            _synthetic_run("P3pb", 1, 90.0, 40.0), _synthetic_run("P3pb", 2, 80.0, 40.0)]
    t = tariffs.get_tariff("elvia-stor-naering-lavspent-2026-01")
    y = pilot.price_run(runs[0], t)["year"]
    # 24 days x 100 kWh at spot 1.0 + 0.05/kWh energy part; 12 peaks of 50 kW (6 winter at 74, 6 summer at 31); 12 x 500 fixed
    assert y["kwh"] == pytest.approx(2400) and y["spot_nok"] == pytest.approx(2400)
    assert y["grid_energy_nok"] == pytest.approx(120) and y["grid_power_nok"] == pytest.approx(50 * (6 * 74 + 6 * 31))
    assert y["grid_fixed_nok"] == pytest.approx(6000) and y["peak_kw_max"] == 50 and y["peak_kw_winter_mean"] == 50
    assert y["total_nok"] == pytest.approx(2400 + 120 + 50 * 630 + 6000)
    s = pilot.summarize(runs, [1, 2], ["P0", "P3pb"], ["elvia-stor-naering-lavspent-2026-01", "reference-generic"])
    r = s["by_tariff"]["elvia-stor-naering-lavspent-2026-01"]["strategies"]["P3pb"]
    # seed 1 saves 240 kWh (10 %), seed 2 saves 480 kWh (20 %): mean 360, min 240, max 480
    assert r["saving_kwh"] == {"mean": 360.0, "min": 240.0, "max": 480.0, "sd": 120.0, "n": 2}
    assert r["saving_kwh_pct"]["mean"] == pytest.approx(15.0)
    assert r["peak_reduction_kw_winter_mean"] == pytest.approx(10.0)
    assert r["saving_by_part_nok"]["grid_power_nok"] == pytest.approx(10 * 630)
    g = s["by_tariff"]["reference-generic"]["strategies"]["P3pb"]
    assert g["saving_by_part_nok"]["grid_power_nok"] == pytest.approx(10 * (5 * 110 + 7 * 45))
    assert s["by_tariff"]["reference-generic"]["strategies"]["P0"]["grid_fixed_nok"] == 0.0


def test_pack_end_to_end_two_days_writes_manifest_reports_and_verifies_series(tmp_path):
    out = tmp_path / "pack"
    cmd = [sys.executable, "-m", "runner.pilot", "--config", "twin/fixtures/calibrated/site-001-v2.json", "--area", "NO1",
           "--days", "2", "--seeds", "177", "--strategies", "P0", "P3pb", "--peak-budget-kw", "80", "--workers", "2",
           "--out", str(out)]
    subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)
    res = json.loads((out / "pilot.json").read_text("utf-8"))
    man = json.loads((out / "manifest.json").read_text("utf-8"))
    assert res["schema"] == pilot.SCHEMA and res["building_id"] == "site-001-v2" and res["days"] == 2
    assert all(v["verified"] for v in man["inputs"]["series"].values())
    assert man["inputs"]["calibration"]["site_id"] == "SITE_001"
    assert man["policy_overrides"]["peak_budget"]["kw"] == 80.0
    assert len(man["inputs"]["fixture"]["sha256"]) == 64
    y = res["primary"]["year"]
    assert "saving_nok" in y["P3pb"] and y["P3pb"]["saving_nok"]["n"] == 1
    md, h = (out / "pilot.md").read_text("utf-8"), (out / "pilot.html").read_text("utf-8")
    assert "Not established" in md and "IPMVP Option D" in md and "over the 2-day period" in md
    assert "<svg" in h and "Guideline 14" in h and "a year" not in h
    assert (out / "monthly.csv").read_text("utf-8").startswith("month,")
    # the reports are rebuilt from the json alone
    assert render_markdown(res) == md and render_html(res) == h


def test_bacs_audit_grades_and_cross_check():
    b = bacs.audit()
    applicable = [f for f in b["functions"] if f["applicable"]]
    assert all(f["p3_grade"] in "ABCD" and f["p0_grade"] in "ABCD" for f in applicable)
    assert b["overall_class_floor"]["P0"] == "D"
    order = "DCBA"
    assert all(order.index(f["p3_grade"]) >= order.index(f["p0_grade"]) for f in applicable)
    xc = bacs.cross_check(b, p0_thermal_kwh=40_000, p0_electrical_kwh=60_000, simulated_saving_kwh=15_000)
    assert xc["factor_thermal_saving_kwh"] == 12_000 and xc["factor_electrical_saving_kwh"] == 7_800
    assert xc["ratio_simulated_to_factor"] == pytest.approx(15_000 / 19_800, abs=0.01)
    md = bacs.to_markdown(b, xc)
    assert "TRANSCRIBED" not in md and "verify against the standard" in md and "290 kW" in md


def test_sweep_and_demo_page_on_a_one_day_pack(tmp_path):
    out = tmp_path / "pack"
    base = [sys.executable, "-m", "runner.pilot", "--config", "twin/fixtures/calibrated/site-001-v2.json", "--area", "NO1",
            "--days", "1", "--seeds", "177", "--strategies", "P0", "P3pb", "--peak-budget-kw", "80", "--workers", "2",
            "--out", str(out)]
    subprocess.run(base, cwd=ROOT, check=True, capture_output=True, text=True)
    sweep = [sys.executable, "-m", "runner.peak_sweep", "--config", "twin/fixtures/calibrated/site-001-v2.json",
             "--area", "NO1", "--days", "1", "--budgets", "80", "120", "--workers", "2", "--out", str(out)]
    subprocess.run(sweep, cwd=ROOT, check=True, capture_output=True, text=True)
    sw = json.loads((out / "sweep.json").read_text("utf-8"))
    assert [r["strategy"] for r in sw["rows"]] == ["P0", "P3", "P3pb", "P3pb"]
    assert sw["rows"][0]["saving_nok"] == 0.0 and sw["rows"][2]["budget_kw"] == 80.0
    assert sw["tariff"]["tariff_id"] == "elvia-stor-naering-lavspent-2026-07"
    from runner.report_demo import render
    page = render(out)
    (out / "demo.html").write_text(page, encoding="utf-8")
    assert "window.__DEMO__=" in page and '"sweep": {' in page and "Choose the budget" in page
    assert '"2025-01-15"' not in page            # a one-day pack has no record day; the page still renders
    assert "Not established" in page and "renderSweep(); renderDay(); renderCalibration();" in page
