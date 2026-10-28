"""Sweep the peak budget on one building: P3pb at several budgets, one seed, beside P0 and P3.

    python -m runner.peak_sweep --config twin/fixtures/calibrated/site-001-v2.json --area NO1 \
        --budgets 60 70 80 90 100 --tariff elvia-stor-naering-lavspent-2026-01 --out artifacts/pilot-site-001

Writes `sweep.json`: for every budget the year's cost, kWh, winter peaks, comfort degree-hours,
backup kWh and the budget's release count, priced on the named tariff. The sweep is what a
site uses to choose its budget (ADR-011): the optimum is not smooth, because a budget that
is too tight is released for comfort on the coldest mornings and those hours set the peak.
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from runner.areas import AREAS, run_one
from runner.pilot import price_run
from runner.tariffs import get_tariff


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="runner.peak_sweep")
    p.add_argument("--config", required=True)
    p.add_argument("--area", default="NO1", choices=list(AREAS))
    p.add_argument("--scenario", default=None)
    p.add_argument("--days", type=int, default=0)
    p.add_argument("--seed", type=int, default=177)
    p.add_argument("--budgets", type=float, nargs="+", default=[60, 70, 80, 90, 100])
    p.add_argument("--hp-full-kw-prior", type=float, default=150.0)
    p.add_argument("--tariff", default="elvia-stor-naering-lavspent-2026-07")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    jobs: list[tuple] = [(a.area, "P0", a.seed, a.days, False, a.config, a.tariff, a.scenario, None),
                         (a.area, "P3", a.seed, a.days, False, a.config, a.tariff, a.scenario, None)]
    for b in a.budgets:
        jobs.append((a.area, "P3pb", a.seed, a.days, False, a.config, a.tariff, a.scenario,
                     {"peak_budget": {"kw": b, "hp_full_kw_prior": a.hp_full_kw_prior}}))
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        runs = list(ex.map(run_one, jobs))
    tariff = get_tariff(a.tariff)
    winter = set(tariff["winter_months"])
    rows: list[dict[str, Any]] = []
    for job, r in zip(jobs, runs):
        pr = price_run(r, tariff)
        y = pr["year"]
        ck = r.get("caretaker") or {}
        rows.append({"strategy": job[1], "budget_kw": (job[8] or {}).get("peak_budget", {}).get("kw"),
                     "total_nok": y["total_nok"], "kwh": y["kwh"], "grid_power_nok": y["grid_power_nok"],
                     "spot_nok": y["spot_nok"], "comfort_dh": y["comfort_dh"], "backup_kwh": y["backup_heater"],
                     "peak_kw_winter_mean": y["peak_kw_winter_mean"], "peak_kw_max": y["peak_kw_max"],
                     "monthly_peak_kw": {m: v["peak_kw"] for m, v in pr["month"].items()},
                     "released": (ck.get("algorithms") or {}).get("peak_budget_released", 0),
                     "fallback": (ck.get("routes") or {}).get("fallback", 0)})
    p0 = next(x for x in rows if x["strategy"] == "P0")
    for x in rows:
        x["saving_nok"] = p0["total_nok"] - x["total_nok"]
        x["saving_pct"] = 100 * x["saving_nok"] / p0["total_nok"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = {"schema": "ot-peak-sweep/v1", "config": a.config, "area": a.area, "seed": a.seed, "tariff": tariff,
           "winter_months": sorted(winter), "rows": rows}
    (out / "sweep.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    for x in rows:
        print(f"{x['strategy']:5} {x['budget_kw'] or '':>5} {x['total_nok']:9.0f} NOK  save {x['saving_pct']:5.1f} %  "
              f"winter peak {x['peak_kw_winter_mean']:5.0f} kW  comfort {x['comfort_dh']:4.0f} dh  "
              f"backup {x['backup_kwh']:5.0f} kWh  released {x['released']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
