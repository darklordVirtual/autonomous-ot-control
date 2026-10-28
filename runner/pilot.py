"""Pilot evidence pack: a calibrated building, every strategy, every number with its provenance.

    python -m runner.pilot --config twin/fixtures/calibrated/site-001-v2.json --area NO1 \
        --seeds 177 178 179 --peak-budget-kw 80 --out artifacts/pilot-site-001

Measurement & verification in the shape of IPMVP Option D (calibrated
simulation), reported against ASHRAE Guideline 14: the baseline is the twin
calibrated to the site's meters (`scenarios/calibration/<site>.json`), the
measure is the caretaker, and the saving is the difference between the two
simulations on the same weather, prices and occupancy. Every input is pinned
by SHA-256 in `manifest.json`, the runs are seeded and deterministic, and the
reports (`pilot.md`, `pilot.html`, `pilot.json`) are rebuilt from the JSON.

What is reported, per strategy and tariff:
- energy by consumer, spot cost, grid energy and power parts, fixed part;
- the month's highest hourly mean kW, which the power part is charged on;
- comfort degree-hours while occupied, CO2 above the IL-07 ceiling, hours
  with the tank above 60 degC, backup-heater kWh;
- the caretaker's routes (submit / hold / fallback / escalate), validator
  violations, FDD, peak-budget releases;
- the saving against P0 as mean, min and max over the seeds (the seeds vary
  presence and plug loads, not the building), under each named tariff, and
  the share of the saving per lever (consumer).

Nothing here is a measured saving. The calibration is in-sample and monthly;
the hourly criterion is not met; the as-found control (P0) is the testbed's
generic as-found, not the site's documented control sequence. The report
says all of this in its scope section, with the status line from
`docs/status.md`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from runner.areas import AREAS, METERS, aggregate, run_one, scenario_path
from runner.tariffs import TARIFFS, describe, get_tariff

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ot-pilot-evidence/v1"
KPIS = ("comfort_dh", "co2_excess_ppmh", "tank_over_60_h", "hazard_h")
LEVERS = ("heat_pump", "backup_heater", "fans", "cooling", "lighting", "pumps_dhw", "equipment", "heating_cables")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git_head() -> dict[str, Any]:
    try:
        rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip() != ""
        return {"commit": rev, "dirty": dirty}
    except Exception:  # noqa: BLE001
        return {"commit": None, "dirty": None}


# -- pricing ------------------------------------------------------------------------------

def price_run(run: dict[str, Any], tariff: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Month and year totals of one run under a named tariff, from its day rows and monthly peaks.

    The runs are controlled on the fixture's own price signal; a tariff only changes the accounting
    (grid energy part per kWh, power part on the month's peak, fixed part per month), so one run can
    be priced under every tariff without being rerun."""
    agg = aggregate(run)
    winter = set(tariff["winter_months"])
    out: dict[str, dict[str, float]] = {}
    for month, row in agg["month"].items():
        rate = tariff["power_nok_per_kw_month"]["winter" if int(month[5:7]) in winter else "summer"]
        peak = run["monthly_peak_kw"].get(month, 0.0)
        grid_energy = row["kwh"] * tariff["energy_nok_per_kwh"]
        grid_power = peak * rate
        out[month] = {**{k: v for k, v in row.items() if k not in ("grid_energy_nok", "grid_power_nok", "total_nok")},
                      "peak_kw": peak, "grid_energy_nok": grid_energy, "grid_power_nok": grid_power,
                      "grid_fixed_nok": tariff["fixed_nok_per_month"],
                      "total_nok": row["spot_nok"] + grid_energy + grid_power + tariff["fixed_nok_per_month"]}
    year: dict[str, float] = {}
    for row in out.values():
        for k, v in row.items():
            year[k] = year.get(k, 0.0) + (v if k != "peak_kw" else 0.0)
    year.pop("peak_kw", None)
    year["peak_kw_max"] = max((r["peak_kw"] for r in out.values()), default=0.0)
    year["peak_kw_winter_mean"] = statistics.mean([r["peak_kw"] for m, r in out.items() if int(m[5:7]) in winter] or [0.0])
    return {"month": out, "year": year}


# -- summary --------------------------------------------------------------------------------

def _stat(vals: list[float]) -> dict[str, float]:
    return {"mean": statistics.mean(vals), "min": min(vals), "max": max(vals),
            "sd": statistics.pstdev(vals) if len(vals) > 1 else 0.0, "n": len(vals)}


def summarize(runs: list[dict[str, Any]], seeds: list[int], strategies: list[str], tariffs: list[str],
              baseline: str = "P0") -> dict[str, Any]:
    priced = {(r["strategy"], r["seed"], tid): price_run(r, get_tariff(tid)) for r in runs for tid in tariffs}
    out: dict[str, Any] = {"by_tariff": {}}
    for tid in tariffs:
        t: dict[str, Any] = {"tariff": get_tariff(tid), "strategies": {}, "monthly": {}}
        for s in strategies:
            years = [priced[(s, sd, tid)]["year"] for sd in seeds]
            row = {k: statistics.mean(y[k] for y in years) for k in years[0]}
            row["seed_total_nok"] = {str(sd): priced[(s, sd, tid)]["year"]["total_nok"] for sd in seeds}
            if s != baseline:
                base_years = [priced[(baseline, sd, tid)]["year"] for sd in seeds]
                sav_nok = [b["total_nok"] - y["total_nok"] for b, y in zip(base_years, years)]
                sav_kwh = [b["kwh"] - y["kwh"] for b, y in zip(base_years, years)]
                base_nok = statistics.mean(b["total_nok"] for b in base_years)
                base_kwh = statistics.mean(b["kwh"] for b in base_years)
                row["saving_nok"] = _stat(sav_nok)
                row["saving_pct"] = _stat([100 * v / base_nok for v in sav_nok])
                row["saving_kwh"] = _stat(sav_kwh)
                row["saving_kwh_pct"] = _stat([100 * v / base_kwh for v in sav_kwh])
                row["saving_by_part_nok"] = {k: statistics.mean(b[k] - y[k] for b, y in zip(base_years, years))
                                             for k in ("spot_nok", "grid_energy_nok", "grid_power_nok")}
                row["saving_by_lever_kwh"] = {k: statistics.mean(b.get(k, 0.0) - y.get(k, 0.0) for b, y in zip(base_years, years))
                                              for k in LEVERS if k in years[0]}
                row["peak_reduction_kw_winter_mean"] = statistics.mean(
                    b["peak_kw_winter_mean"] - y["peak_kw_winter_mean"] for b, y in zip(base_years, years))
            t["strategies"][s] = row
            months = sorted(priced[(s, seeds[0], tid)]["month"])
            t["monthly"][s] = {m: {k: statistics.mean(priced[(s, sd, tid)]["month"][m][k] for sd in seeds)
                                   for k in priced[(s, seeds[0], tid)]["month"][m]} for m in months}
        out["by_tariff"][tid] = t
    out["caretaker"] = {}
    for s in strategies:
        cs = [r["caretaker"] for r in runs if r["strategy"] == s and "caretaker" in r]
        if cs:
            agg: dict[str, Any] = {}
            for k in ("routes", "violations", "algorithms", "overlays", "profiles"):
                keys = sorted({kk for c in cs for kk in c[k]})
                agg[k] = {kk: statistics.mean(c[k].get(kk, 0) for c in cs) for kk in keys}
            for k in ("fdd_alarms", "fdd_true_alarms", "fdd_episodes", "fdd_episodes_detected",
                      "optimizer_faults_caught", "zone_fallback_steps"):
                agg[k] = statistics.mean(c.get(k, 0) for c in cs)
            agg["proposals"] = sum(agg["routes"].values())
            out["caretaker"][s] = agg
    return out


# -- main -------------------------------------------------------------------------------------

def run_pack(config: Path, area: str, seeds: list[int], strategies: list[str], tariffs: list[str],
             peak_budget_kw: float | None, hp_full_kw_prior: float, days: int, workers: int,
             scenario: Path | None = None, faults: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    overrides = ({"peak_budget": {"kw": peak_budget_kw, **({"hp_full_kw_prior": hp_full_kw_prior} if hp_full_kw_prior else {})}}
                 if peak_budget_kw else {})
    jobs = [(area, s, sd, days, faults, str(config), tariffs[0], str(scenario) if scenario else None, overrides)
            for s in strategies for sd in seeds]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        runs = list(ex.map(run_one, jobs))
    return runs, overrides


def build_manifest(config: Path, area: str, scenario: Path, seeds: list[int], strategies: list[str],
                   tariffs: list[str], overrides: dict[str, Any], argv: list[str],
                   monthly_check: Path | None = None) -> dict[str, Any]:
    cfg = json.loads(config.read_text("utf-8"))
    sc = json.loads(scenario.read_text("utf-8"))
    inputs: dict[str, Any] = {
        "fixture": {"path": _rel(config), "sha256": sha256_file(config), "building_id": cfg.get("building_id")},
        "scenario": {"path": _rel(scenario), "sha256": sha256_file(scenario), "scenario_id": sc.get("scenario_id")},
        "series": {}, "policy": {}, "calibration": None,
    }
    for kind in ("outdoor", "price", "solar", "humidity", "precipitation"):
        ref = (sc.get(kind) or {}).get("series_ref")
        if ref:
            p = (scenario.parent / ref).resolve()
            inputs["series"][kind] = {"path": _rel(p), "sha256": sha256_file(p),
                                      "declared_sha256": sc[kind].get("sha256"),
                                      "verified": sha256_file(p) == sc[kind].get("sha256")}
    for name, rel in (("site_policy", "deploy/ot/site_policy.v1.json"), ("fallback", "deploy/ot/caretaker_fallback.v1.json")):
        inputs["policy"][name] = {"path": rel, "sha256": sha256_file(ROOT / rel)}
    cal = (cfg.get("calibration") or {}).get("source") or {}
    site_id = cal.get("site_id")
    if site_id:
        calp = ROOT / "scenarios" / "calibration" / f"{site_id.lower().replace('_', '-')}.json"
        if calp.exists():
            inputs["calibration"] = {"site_id": site_id, "path": _rel(calp), "sha256": sha256_file(calp),
                                     "source_sha256": cal.get("source_sha256")}
    if monthly_check:
        inputs["monthly_check"] = {"path": _rel(monthly_check), "sha256": sha256_file(monthly_check)}
    return {"schema": SCHEMA + "/manifest", "created_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "testbed": git_head(), "python": platform.python_version(), "argv": argv,
            "area": area, "seeds": seeds, "strategies": strategies, "tariffs": tariffs,
            "policy_overrides": overrides, "inputs": inputs}


def _rel(p: Path) -> str:
    p = p.resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)


def load_calibration(manifest: dict[str, Any], config: Path, monthly_check: Path | None = None) -> dict[str, Any] | None:
    c = manifest["inputs"].get("calibration")
    if not c:
        return None
    raw = json.loads((ROOT / c["path"]).read_text("utf-8"))
    fit = raw.get("fit", {})
    cfg = json.loads(config.read_text("utf-8"))
    check = json.loads(monthly_check.read_text("utf-8")) if monthly_check else None
    return {"site_id": raw.get("site_id"), "note": raw.get("note"), "version": fit.get("version"),
            "validation": fit.get("validation"), "params": fit.get("params"),
            "plant_sizing": (cfg.get("calibration") or {}).get("plant_sizing"),
            "monthly_check": check,
            "certificate": {k: raw.get("certificate", {}).get(k) for k in
                            ("BRA_m2", "byggeaar", "heat_source_note", "heat_recovery_eff", "sfp_operating",
                             "measured_electricity_kwh_per_year", "calculated_delivered_kwh_m2")},
            "period_utc": raw.get("targets", {}).get("period_utc"), "open_questions": raw.get("open_questions")}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="runner.pilot")
    p.add_argument("--config", required=True, help="the calibrated twin fixture")
    p.add_argument("--area", default="NO1", choices=list(AREAS))
    p.add_argument("--scenario", help="scenario file (default: the area's 2025 year)")
    p.add_argument("--days", type=int, default=0, help="0: the scenario's own duration")
    p.add_argument("--seeds", type=int, nargs="+", default=[177, 178, 179])
    p.add_argument("--strategies", nargs="+", default=["P0", "P1", "P2", "P3", "P3pb"])
    p.add_argument("--tariffs", nargs="+",
                   default=["elvia-stor-naering-lavspent-2026-07", "elvia-stor-naering-lavspent-2026-01", "reference-generic"],
                   choices=list(TARIFFS), help="the first is the primary; the runs are priced under every one")
    p.add_argument("--peak-budget-kw", type=float, default=None, help="monthly hourly-mean kW budget for P3pb")
    p.add_argument("--hp-full-kw-prior", type=float, default=0.0, help="0: learn from the first running hour")
    p.add_argument("--primary", default="P3pb", help="the strategy the headline is written for")
    p.add_argument("--monthly-check", default=None,
                   help="runner.site_calibration --monthly-check output for a derived fixture, carried into the report")
    p.add_argument("--faults", action="store_true")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    config = Path(a.config).resolve()
    scenario = Path(a.scenario).resolve() if a.scenario else scenario_path(a.area)
    if "P3pb" in a.strategies and not a.peak_budget_kw:
        p.error("--peak-budget-kw is required with P3pb")
    primary = a.primary if a.primary in a.strategies else a.strategies[-1]
    runs, overrides = run_pack(config, a.area, a.seeds, a.strategies, a.tariffs, a.peak_budget_kw,
                               a.hp_full_kw_prior, a.days, a.workers, scenario if a.scenario else None, a.faults)
    summary = summarize(runs, a.seeds, a.strategies, a.tariffs)
    manifest = build_manifest(config, a.area, scenario, a.seeds, a.strategies, a.tariffs, overrides, sys.argv[1:],
                              Path(a.monthly_check).resolve() if a.monthly_check else None)
    prim = summary["by_tariff"][a.tariffs[0]]
    res = {"schema": SCHEMA, "building_id": manifest["inputs"]["fixture"]["building_id"], "area": a.area,
           "area_name": AREAS[a.area], "scenario_id": manifest["inputs"]["scenario"]["scenario_id"],
           "days": len(runs[0]["days"]), "seeds": a.seeds, "strategies": a.strategies,
           "baseline": "P0", "primary": {"strategy": primary, "tariff": a.tariffs[0],
                                         "year": prim["strategies"], "monthly": prim["monthly"]},
           "summary": summary,
           "calibration": load_calibration(manifest, config, Path(a.monthly_check) if a.monthly_check else None),
           "manifest": manifest,
           "tariff_in_runs": describe(json.loads(config.read_text("utf-8"))),
           "scope": SCOPE}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "pilot.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    import gzip
    with gzip.open(out / "runs.json.gz", "wt", encoding="utf-8") as f:   # day rows and peaks: enough to reprice later
        json.dump([{k: v for k, v in r.items() if k not in ("records", "alarms")} for r in runs], f)
    with (out / "decision-records.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for r in runs:
            if r["seed"] == a.seeds[0]:
                for rec in r.get("records", []):
                    f.write(json.dumps({"strategy": r["strategy"], "seed": r["seed"], **rec}, sort_keys=True) + "\n")
    with (out / "fdd-alarms.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for r in runs:
            for al in r.get("alarms", []):
                f.write(json.dumps({"strategy": r["strategy"], "seed": r["seed"], **al}, sort_keys=True) + "\n")
    _write_monthly_csv(out / "monthly.csv", res)
    from runner.report_pilot import render_html, render_markdown
    (out / "pilot.md").write_text(render_markdown(res), encoding="utf-8")
    (out / "pilot.html").write_text(render_html(res), encoding="utf-8")
    y = prim["strategies"]
    print(f"{res['building_id']} {a.area} {res['scenario_id']} seeds {a.seeds} tariff {a.tariffs[0]}")
    print(f"P0 {y['P0']['total_nok']:9.0f} NOK  {y['P0']['kwh']:8.0f} kWh  winter peak mean {y['P0']['peak_kw_winter_mean']:.0f} kW")
    for s in a.strategies[1:]:
        r = y[s]
        print(f"{s:5} saves {r['saving_nok']['mean']:8.0f} NOK ({r['saving_pct']['mean']:4.1f} %, "
              f"{r['saving_pct']['min']:.1f}..{r['saving_pct']['max']:.1f}) {r['saving_kwh']['mean']:7.0f} kWh "
              f"({r['saving_kwh_pct']['mean']:4.1f} %)  peak -{r['peak_reduction_kw_winter_mean']:.0f} kW  "
              f"comfort {r['comfort_dh']:.0f} dh  backup {r['backup_heater']:.0f} kWh")
    return 0


def _write_monthly_csv(path: Path, res: dict[str, Any]) -> None:
    import csv
    m = res["primary"]["monthly"]
    strategies = res["strategies"]
    months = sorted(next(iter(m.values())))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["month"] + [f"{s}_{k}" for s in strategies for k in ("kwh", "peak_kw", "total_nok", "comfort_dh")])
        for mo in months:
            w.writerow([mo] + [round(m[s][mo][k], 1) for s in strategies for k in ("kwh", "peak_kw", "total_nok", "comfort_dh")])


SCOPE = {
    "method": "IPMVP Option D (calibrated simulation); calibration reported against ASHRAE Guideline 14 "
              "(monthly CV(RMSE) <= 15 %, |NMBE| <= 5 %; hourly <= 30 %, <= 10 %).",
    "established": [
        "The twin, calibrated to the site's named meters, reproduces the site's monthly electricity within the "
        "Guideline 14 monthly criteria on the metered period (in-sample).",
        "On that twin, the strategies' energy, cost, peak and comfort differences are deterministic and "
        "reproducible from the pinned inputs and seeds.",
        "Every supervisory change of the caretaker is one governed tool call with a decision record; the "
        "validator's refusals and routes are counted.",
    ],
    "not_established": [
        "A measured saving in the building. The calibration is in-sample (the fit period is the validation period), "
        "monthly only (the hourly criterion is not met), and on nine months of 2026 while the savings year is 2025.",
        "The as-found control. P0 is the testbed's generic as-found sequence (fixed schedules, constant tank), not "
        "the site's documented sequence; the site's real baseline may already contain some of the levers.",
        "The plant as sized: the heat pump's output, the backup heater, the buffer volume and the ground-source "
        "temperature are derived from the certificate and stated assumptions (calibration.plant_sizing), not "
        "measured; whether the real plant stages its backup heater as the twin does, and whether lighting can be "
        "controlled by presence and daylight, are site questions.",
        "The grid tariff's power part: priced on a published sheet, transcribed by hand, excluding taxes and the "
        "reactive-power charge; the site's contract may differ.",
        "Physical OT safety. No write path to a real plant exists (INV-12).",
    ],
    "pilot_next": "A 90-day pilot replaces every item above with measurement: the site's own control sequence as P0, "
                  "a held-out validation period, the meters as the measurement boundary, and the governed "
                  "caretaker in shadow then controlled operation under the signed limits.",
}


if __name__ == "__main__":
    raise SystemExit(main())
