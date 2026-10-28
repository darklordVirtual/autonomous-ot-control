"""Render a pilot evidence pack (`runner.pilot`'s pilot.json) as Markdown and a self-contained HTML page.

    python -m runner.report_pilot --results artifacts/pilot-site-001/pilot.json --out artifacts/pilot-site-001

The HTML has no external dependencies: inline CSS and inline SVG charts, so it
can be opened from a file, attached to a mail, or published as is.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

MONTHS_NO = ["jan", "feb", "mar", "apr", "mai", "jun", "jul", "aug", "sep", "okt", "nov", "des"]
LEVER_NAMES = {"heat_pump": "Heat pump", "backup_heater": "Backup heater", "fans": "AHU fans", "cooling": "Chiller",
               "lighting": "Lighting", "pumps_dhw": "Pumps / DHW", "equipment": "Equipment", "heating_cables": "Heating cables"}
STRATEGY_NAMES = {"P0": "P0 as found", "P1": "P1 setback + optimal start", "P2": "P2 caretaker presets",
                  "P3": "P3 governed caretaker", "P3pb": "P3 + peak budget", "P3raw": "P3 unvalidated"}


def _n(v: float, d: int = 0) -> str:
    s = f"{v:,.{d}f}".replace(",", " ")
    return s


def _pct(v: float) -> str:
    return f"{v:.1f} %"


def _period(res: dict[str, Any]) -> str:
    return "a year" if res["days"] >= 360 else f"over the {res['days']}-day period"


# -- markdown ----------------------------------------------------------------------------------

def render_markdown(res: dict[str, Any]) -> str:
    prim, strategies, base = res["primary"], res["strategies"], res["baseline"]
    y = prim["year"]
    ps = prim["strategy"]
    tariff = res["summary"]["by_tariff"][prim["tariff"]]["tariff"]
    cal = res.get("calibration") or {}
    val = (cal.get("validation") or {}).get("total") or {}
    out = [f"# Pilot evidence pack: {res['building_id']} ({res['area']} {res['area_name']}, {res['scenario_id']})", ""]
    r = y[ps]
    out += ["## Summary", "",
            f"On the twin calibrated to **{cal.get('site_id', res['building_id'])}**, the governed caretaker "
            f"**{STRATEGY_NAMES.get(ps, ps)}** against the as-found control **P0** over {res['days']} days, "
            f"{len(res['seeds'])} seeds, priced on *{tariff['name']}*:", "",
            f"- **{_n(r['saving_nok']['mean'])} NOK {_period(res)} ({_pct(r['saving_pct']['mean'])} of {_n(y[base]['total_nok'])} NOK)**, "
            f"seed range {_n(r['saving_nok']['min'])}..{_n(r['saving_nok']['max'])} NOK.",
            f"- **{_n(r['saving_kwh']['mean'])} kWh ({_pct(r['saving_kwh_pct']['mean'])} of {_n(y[base]['kwh'])} kWh)**.",
            f"- Winter peak (mean of the winter months' highest hourly mean): {_n(y[base]['peak_kw_winter_mean'])} kW to "
            f"{_n(r['peak_kw_winter_mean'])} kW (-{_n(r['peak_reduction_kw_winter_mean'])} kW); "
            f"grid power part {_n(y[base]['grid_power_nok'])} to {_n(r['grid_power_nok'])} NOK.",
            f"- Comfort while occupied: {_n(r['comfort_dh'])} degree-hours (P0 {_n(y[base]['comfort_dh'])}); "
            f"CO2 above the ceiling {_n(r['co2_excess_ppmh'])} ppm·h (P0 {_n(y[base]['co2_excess_ppmh'])}); "
            f"tank above 60 degC {_n(r['tank_over_60_h'])} h; backup heater {_n(r['backup_heater'])} kWh "
            f"(P0 {_n(y[base]['backup_heater'])}).", ""]
    if val:
        out += [f"Baseline model: monthly CV(RMSE) {val.get('monthly_cv_rmse_pct')} %, NMBE {val.get('monthly_nmbe_pct')} % "
                f"over {val.get('months')} metered months (Guideline 14 monthly "
                f"{'met' if val.get('guideline14_monthly') else 'not met'}; hourly CV(RMSE) {val.get('cv_rmse_pct')} %, "
                f"{'met' if val.get('guideline14_hourly') else 'not met'}). In-sample.", ""]
    out += _plant_md(cal)
    out += ["## Strategies", "", "| Strategy | Cost (NOK) | Saving (NOK) | Saving (%) | kWh | Saving (kWh) | Winter peak (kW) | Comfort (dh) | Backup (kWh) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in strategies:
        q = y[s]
        if s == base:
            out.append(f"| {STRATEGY_NAMES.get(s, s)} | {_n(q['total_nok'])} | – | – | {_n(q['kwh'])} | – | "
                       f"{_n(q['peak_kw_winter_mean'])} | {_n(q['comfort_dh'])} | {_n(q['backup_heater'])} |")
        else:
            out.append(f"| {STRATEGY_NAMES.get(s, s)} | {_n(q['total_nok'])} | {_n(q['saving_nok']['mean'])} "
                       f"({_n(q['saving_nok']['min'])}..{_n(q['saving_nok']['max'])}) | {_pct(q['saving_pct']['mean'])} | "
                       f"{_n(q['kwh'])} | {_n(q['saving_kwh']['mean'])} | {_n(q['peak_kw_winter_mean'])} | "
                       f"{_n(q['comfort_dh'])} | {_n(q['backup_heater'])} |")
    out += ["", "Saving = P0 cost minus the strategy's cost, per seed; mean and seed range. Cost = spot + grid energy part "
                "+ power part on the month's highest hourly mean kW + fixed part; taxes excluded.", ""]
    out += ["## What drives the number", "", f"Energy by consumer, P0 and {ps} (kWh {_period(res)}):", "",
            "| Consumer | P0 | " + ps + " | Saved |", "|---|---:|---:|---:|"]
    for k, name in LEVER_NAMES.items():
        if k in y[base]:
            out.append(f"| {name} | {_n(y[base][k])} | {_n(y[ps][k])} | {_n(y[base][k] - y[ps][k])} |")
    parts = y[ps]["saving_by_part_nok"]
    out += ["", f"Cost saving by part: spot {_n(parts['spot_nok'])} NOK, grid energy part {_n(parts['grid_energy_nok'])} NOK, "
                f"power part {_n(parts['grid_power_nok'])} NOK.", ""]
    out += ["## Tariff sensitivity", "", "| Tariff | P0 cost | " + " | ".join(f"{s} saving" for s in strategies if s != base) + " |",
            "|---|---:|" + "---:|" * (len(strategies) - 1)]
    for tid, t in res["summary"]["by_tariff"].items():
        ys = t["strategies"]
        out.append(f"| {t['tariff']['name']} | {_n(ys[base]['total_nok'])} | " + " | ".join(
            f"{_n(ys[s]['saving_nok']['mean'])} ({_pct(ys[s]['saving_pct']['mean'])})" for s in strategies if s != base) + " |")
    out += ["", "## Monthly", "", "| Month | " + " | ".join(f"{s} kWh | {s} peak kW | {s} NOK" for s in (base, ps)) + " |",
            "|---|" + "---:|" * 6]
    for mo in sorted(prim["monthly"][base]):
        out.append(f"| {mo} | " + " | ".join(
            f"{_n(prim['monthly'][s][mo]['kwh'])} | {_n(prim['monthly'][s][mo]['peak_kw'])} | {_n(prim['monthly'][s][mo]['total_nok'])}"
            for s in (base, ps)) + " |")
    ck = res["summary"].get("caretaker", {}).get(ps)
    if ck:
        out += ["", "## Governance", "",
                f"{ps}: {_n(ck['proposals'])} proposals per seed; routes " +
                ", ".join(f"{k} {_n(v)}" for k, v in ck["routes"].items()) + ".",
                f"Validator violations: " + (", ".join(f"{k} {_n(v)}" for k, v in ck["violations"].items()) or "none") + ".",
                f"Peak budget: cap steps {_n(ck['algorithms'].get('peak_budget', 0))}, held {_n(ck['algorithms'].get('peak_budget_hold', 0))}, "
                f"released {_n(ck['algorithms'].get('peak_budget_released', 0))}.",
                f"FDD: {_n(ck['fdd_alarms'])} alarms, {_n(ck['fdd_true_alarms'])} true; optimizer faults caught {_n(ck['optimizer_faults_caught'])}.", ""]
    sc = res["scope"]
    out += ["## Scope", "", f"Method: {sc['method']}", "", "Established:"] + [f"- {x}" for x in sc["established"]]
    out += ["", "Not established:"] + [f"- {x}" for x in sc["not_established"]] + ["", sc["pilot_next"], ""]
    m = res["manifest"]
    out += ["## Evidence", "", f"- Testbed commit `{m['testbed']['commit']}`" + (" (dirty tree)" if m["testbed"].get("dirty") else ""),
            f"- Fixture `{m['inputs']['fixture']['path']}` sha256 `{m['inputs']['fixture']['sha256'][:16]}…`",
            f"- Scenario `{m['inputs']['scenario']['path']}` sha256 `{m['inputs']['scenario']['sha256'][:16]}…`; series verified: "
            + ", ".join(f"{k} {'ok' if v['verified'] else 'MISMATCH'}" for k, v in m["inputs"]["series"].items()),
            f"- Site policy sha256 `{m['inputs']['policy']['site_policy']['sha256'][:16]}…`; policy overrides {json.dumps(m['policy_overrides'])}",
            f"- Seeds {m['seeds']}; created {m['created_utc']}", "",
            "Rebuild: `python -m runner.pilot " + " ".join(m["argv"]) + "`", ""]
    return "\n".join(out)


def _plant_md(cal: dict[str, Any]) -> list[str]:
    ps, mc = cal.get("plant_sizing"), cal.get("monthly_check")
    out: list[str] = []
    if ps:
        out += [f"Plant sized from the design heat load ({_n(ps['design_heat_load_w'] / 1000)} kW at {ps['dut_c']} degC): "
                f"heat pump {_n(ps['hp_nominal_heat_w'] / 1000)} kW ({int(100 * ps['hp_share_of_design_load'])} % of the design load), "
                f"backup heater {_n(ps['backup_heater_w'] / 1000)} kW, buffer {_n(ps['tank_volume_l'])} l, ground source at "
                f"{ps['hp_source_c']} degC, Carnot fraction {ps['hp_carnot_fraction']} (seasonal COP {ps['seasonal_cop']} at "
                f"{ps['supply_mean_c']} degC supply). Derived from `{ps['derived_from']}`, whose heat pump was the installed "
                f"radiator capacity; none of these values is measured.", ""]
    if mc:
        g = mc["groups"]
        out += ["Monthly check of this fixture against the site's measured months (same hours as the fit, in-sample): "
                + "; ".join(f"{k}: CV(RMSE) {v['monthly_cv_rmse_pct']} %, NMBE {v['monthly_nmbe_pct']} % "
                            f"({'met' if v['guideline14_monthly'] else 'not met'})" for k, v in g.items()) + ".", ""]
    return out


def _plant_html(cal: dict[str, Any]) -> str:
    return "".join(f"<p>{html.escape(line)}</p>" for line in _plant_md(cal) if line)


# -- html ----------------------------------------------------------------------------------------

CSS = """
:root{--ink:#14202b;--mute:#5b6b7a;--line:#dde3e8;--bg:#fff;--card:#f6f8fa;--occ:#fff3d6;--hl:#e8f5ee;--note-bg:#fff8e6;--note-line:#f1d58a;--note-ink:#5a4300;--p0:#9aa5b1;--p1:#6b8fb3;--p2:#3f7fbf;--p3:#1f5fa8;--pb:#0b8a5a;--warn:#b9410f}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--ink:#e6edf3;--mute:#9fb0c0;--line:#2b3744;--bg:#0f1720;--card:#172230;--occ:#3a2f12;--hl:#143324;--note-bg:#2b2410;--note-line:#6a5a1e;--note-ink:#f1dfa0;--p0:#7f8c99;--p1:#7ea0c4;--p2:#5392d0;--p3:#4f8fe0;--pb:#2fb37e;--warn:#e0693a;color-scheme:dark}}
:root[data-theme="dark"]{--ink:#e6edf3;--mute:#9fb0c0;--line:#2b3744;--bg:#0f1720;--card:#172230;--occ:#3a2f12;--hl:#143324;--note-bg:#2b2410;--note-line:#6a5a1e;--note-ink:#f1dfa0;--p0:#7f8c99;--p1:#7ea0c4;--p2:#5392d0;--p3:#4f8fe0;--pb:#2fb37e;--warn:#e0693a;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 -apple-system,Segoe UI,Inter,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
main{max-width:1080px;margin:0 auto;padding:32px 20px 80px}h1{font-size:28px;margin:0 0 4px}h2{font-size:20px;margin:40px 0 12px;border-bottom:1px solid var(--line);padding-bottom:6px}
.sub{color:var(--mute);margin:0 0 24px}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:20px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}.kpi b{display:block;font-size:26px;line-height:1.2}.kpi span{color:var(--mute);font-size:13px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0 16px}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right}th:first-child,td:first-child{text-align:left}th{color:var(--mute);font-weight:600}
.note{background:var(--note-bg);border:1px solid var(--note-line);border-radius:8px;padding:10px 14px;color:var(--note-ink)}.ok{color:var(--pb)}.bad{color:var(--warn)}
svg text{font:12px -apple-system,Segoe UI,Inter,Helvetica,Arial,sans-serif;fill:var(--ink)}.legend span{display:inline-block;margin-right:14px;font-size:13px}.legend i{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:6px;vertical-align:-1px}
ul{padding-left:20px}code{background:var(--card);padding:1px 4px;border-radius:4px;font-size:13px}a{color:var(--p3)}
"""

COLORS = {"P0": "var(--p0)", "P1": "var(--p1)", "P2": "var(--p2)", "P3": "var(--p3)", "P3pb": "var(--pb)", "P3raw": "var(--warn)"}


def _bars(series: dict[str, list[float]], labels: list[str], width: int = 1040, height: int = 260, unit: str = "") -> str:
    keys = list(series)
    n, g = len(labels), len(keys)
    vmax = max((v for vs in series.values() for v in vs), default=1.0) or 1.0
    left, top, bottom = 56, 16, 36
    pw = width - left - 12
    ph = height - top - bottom
    group_w = pw / n
    bar_w = group_w / (g + 1)
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">']
    for i in range(5):
        yv = vmax * i / 4
        yy = top + ph - ph * i / 4
        parts.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{width - 12}" y2="{yy:.1f}" stroke="var(--line)"/>'
                     f'<text x="{left - 6}" y="{yy + 4:.1f}" text-anchor="end" fill="var(--mute)">{_n(yv)}</text>')
    for j, lab in enumerate(labels):
        x0 = left + j * group_w
        parts.append(f'<text x="{x0 + group_w / 2:.1f}" y="{height - 12}" text-anchor="middle" fill="var(--mute)">{html.escape(lab)}</text>')
        for k, key in enumerate(keys):
            v = series[key][j]
            h = ph * v / vmax
            parts.append(f'<rect x="{x0 + bar_w * (k + 0.5):.1f}" y="{top + ph - h:.1f}" width="{bar_w * 0.9:.1f}" height="{h:.1f}" '
                         f'fill="{COLORS.get(key, "#888")}"><title>{html.escape(key)} {html.escape(lab)}: {_n(v)} {unit}</title></rect>')
    parts.append("</svg>")
    legend = '<div class="legend">' + "".join(f'<span><i style="background:{COLORS.get(k, "#888")}"></i>{html.escape(STRATEGY_NAMES.get(k, k))}</span>' for k in keys) + "</div>"
    return "".join(parts) + legend


def _waterfall(base: float, steps: list[tuple[str, float]], final_label: str, width: int = 1040, height: int = 280) -> str:
    left, top, bottom = 56, 16, 60
    pw, ph = width - left - 12, height - top - bottom
    items = [("P0", base, 0.0)]
    run = base
    for name, d in steps:
        items.append((name, run, -d))
        run -= d
    items.append((final_label, run, 0.0))
    vmax = max(base, run) * 1.05
    n = len(items)
    bw = pw / n
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">']
    for i in range(5):
        yv = vmax * i / 4
        yy = top + ph - ph * i / 4
        parts.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{width - 12}" y2="{yy:.1f}" stroke="var(--line)"/>'
                     f'<text x="{left - 6}" y="{yy + 4:.1f}" text-anchor="end" fill="var(--mute)">{_n(yv)}</text>')
    for j, (name, start, delta) in enumerate(items):
        x = left + j * bw + bw * 0.15
        if delta == 0.0:
            h = ph * start / vmax
            y = top + ph - h
            fill = "var(--p0)" if j == 0 else "var(--pb)"
            label = _n(start)
        else:
            lo, hi = min(start, start + delta), max(start, start + delta)
            h = ph * (hi - lo) / vmax
            y = top + ph - ph * hi / vmax
            fill = "var(--p3)" if delta < 0 else "var(--warn)"
            label = f"{'-' if delta < 0 else '+'}{_n(abs(delta))}"
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw * 0.7:.1f}" height="{max(h, 1):.1f}" fill="{fill}"><title>{html.escape(name)}: {label} kWh</title></rect>')
        parts.append(f'<text x="{x + bw * 0.35:.1f}" y="{y - 4:.1f}" text-anchor="middle">{label}</text>')
        parts.append(f'<text x="{x + bw * 0.35:.1f}" y="{height - 40}" text-anchor="middle" fill="var(--mute)">{html.escape(name)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def render_html(res: dict[str, Any]) -> str:
    prim, strategies, base = res["primary"], res["strategies"], res["baseline"]
    y, ps = prim["year"], prim["strategy"]
    t = res["summary"]["by_tariff"][prim["tariff"]]
    tariff = t["tariff"]
    cal = res.get("calibration") or {}
    val = (cal.get("validation") or {}).get("total") or {}
    r = y[ps]
    months = sorted(prim["monthly"][base])
    labels = [MONTHS_NO[int(m[5:7]) - 1] + (f" {m[:4]}" if len({mm[:4] for mm in months}) > 1 else "") for m in months]
    peak_series = {s: [prim["monthly"][s][m]["peak_kw"] for m in months] for s in strategies}
    cost_series = {s: [prim["monthly"][s][m]["total_nok"] for m in months] for s in strategies}
    kwh_series = {s: [prim["monthly"][s][m]["kwh"] for m in months] for s in strategies}
    levers = [(LEVER_NAMES.get(k, k), y[base][k] - y[ps][k]) for k in LEVER_NAMES if k in y[base] and abs(y[base][k] - y[ps][k]) >= 1]
    levers.sort(key=lambda kv: -abs(kv[1]))
    esc = html.escape
    h = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>Pilot evidence: {esc(res['building_id'])}</title><style>{CSS}</style></head><body><main>",
         f"<h1>Pilot evidence pack · {esc(res['building_id'])}</h1>",
         f"<p class='sub'>{esc(res['area'])} {esc(res['area_name'])} · scenario {esc(res['scenario_id'])} · {res['days']} days · "
         f"{len(res['seeds'])} seeds · priced on {esc(tariff['name'])} · IPMVP Option D (calibrated simulation), simulation only</p>",
         "<div class='kpis'>",
         f"<div class='kpi'><b>{_n(r['saving_nok']['mean'])} NOK</b><span>saved {_period(res)} by {esc(STRATEGY_NAMES.get(ps, ps))} vs P0 "
         f"({_pct(r['saving_pct']['mean'])}; seeds {_n(r['saving_nok']['min'])}..{_n(r['saving_nok']['max'])})</span></div>",
         f"<div class='kpi'><b>{_n(r['saving_kwh']['mean'])} kWh</b><span>{_pct(r['saving_kwh_pct']['mean'])} of {_n(y[base]['kwh'])} kWh</span></div>",
         f"<div class='kpi'><b>-{_n(r['peak_reduction_kw_winter_mean'])} kW</b><span>winter peak, {_n(y[base]['peak_kw_winter_mean'])} to "
         f"{_n(r['peak_kw_winter_mean'])} kW hourly mean; power part {_n(y[base]['grid_power_nok'])} → {_n(r['grid_power_nok'])} NOK</span></div>",
         f"<div class='kpi'><b>{_n(r['comfort_dh'])} dh</b><span>comfort degree-hours while occupied (P0 {_n(y[base]['comfort_dh'])}); "
         f"backup heater {_n(r['backup_heater'])} kWh; tank &gt; 60 °C {_n(r['tank_over_60_h'])} h</span></div>",
         "</div>"]
    if val:
        ok = val.get("guideline14_monthly")
        h.append(f"<p>Baseline model: <b>{esc(cal.get('site_id', ''))}</b>, {cal.get('certificate', {}).get('BRA_m2')} m², built "
                 f"{cal.get('certificate', {}).get('byggeaar')}, {esc(str(cal.get('certificate', {}).get('heat_source_note')))}. "
                 f"Calibration against the site's meters: monthly CV(RMSE) <b class='{'ok' if ok else 'bad'}'>{val.get('monthly_cv_rmse_pct')} %</b>, "
                 f"NMBE <b class='{'ok' if ok else 'bad'}'>{val.get('monthly_nmbe_pct')} %</b> over {val.get('months')} metered months "
                 f"(Guideline 14 monthly {'met' if ok else 'not met'}); hourly CV(RMSE) {val.get('cv_rmse_pct')} % "
                 f"({'met' if val.get('guideline14_hourly') else 'not met'}). In-sample: the fit period is the validation period.</p>")
    h.append(_plant_html(cal))
    h.append("<h2>What drives the number</h2><p>Energy by consumer, P0 to " + esc(ps) + " (kWh " + _period(res) + "). The bars after P0 are what each consumer saved; a red bar is a consumer that used more.</p>")
    h.append(_waterfall(y[base]["kwh"], levers, ps))
    parts = r["saving_by_part_nok"]
    h.append(f"<p>Cost saving by part: spot <b>{_n(parts['spot_nok'])} NOK</b>, grid energy part <b>{_n(parts['grid_energy_nok'])} NOK</b>, "
             f"power part <b>{_n(parts['grid_power_nok'])} NOK</b>. The power part is {_pct(100 * y[base]['grid_power_nok'] / y[base]['total_nok'])} of P0's cost on this tariff.</p>")
    h.append("<h2>Monthly peak, kW (highest hourly mean of the month: what the power part is charged on)</h2>")
    h.append(_bars(peak_series, labels, unit="kW"))
    h.append("<h2>Monthly cost, NOK</h2>")
    h.append(_bars(cost_series, labels, unit="NOK"))
    h.append("<h2>Monthly energy, kWh</h2>")
    h.append(_bars(kwh_series, labels, unit="kWh"))
    h.append("<h2>Strategies</h2><table><tr><th>Strategy</th><th>Cost (NOK)</th><th>Saving (NOK)</th><th>Saving</th><th>kWh</th><th>Saved kWh</th><th>Winter peak kW</th><th>Comfort dh</th><th>CO₂ ppm·h</th><th>Backup kWh</th></tr>")
    for s in strategies:
        q = y[s]
        if s == base:
            h.append(f"<tr><td>{esc(STRATEGY_NAMES.get(s, s))}</td><td>{_n(q['total_nok'])}</td><td>–</td><td>–</td><td>{_n(q['kwh'])}</td><td>–</td>"
                     f"<td>{_n(q['peak_kw_winter_mean'])}</td><td>{_n(q['comfort_dh'])}</td><td>{_n(q['co2_excess_ppmh'])}</td><td>{_n(q['backup_heater'])}</td></tr>")
        else:
            h.append(f"<tr><td>{esc(STRATEGY_NAMES.get(s, s))}</td><td>{_n(q['total_nok'])}</td><td>{_n(q['saving_nok']['mean'])} "
                     f"<small>({_n(q['saving_nok']['min'])}..{_n(q['saving_nok']['max'])})</small></td><td>{_pct(q['saving_pct']['mean'])}</td>"
                     f"<td>{_n(q['kwh'])}</td><td>{_n(q['saving_kwh']['mean'])}</td><td>{_n(q['peak_kw_winter_mean'])}</td>"
                     f"<td>{_n(q['comfort_dh'])}</td><td>{_n(q['co2_excess_ppmh'])}</td><td>{_n(q['backup_heater'])}</td></tr>")
    h.append("</table><p>Cost = spot + grid energy part + power part on the month's highest hourly mean kW + fixed part; taxes excluded. "
             "Saving = P0 minus the strategy, per seed; mean and seed range (the seeds vary presence and plug loads, not the building or the weather).</p>")
    h.append("<h2>Tariff sensitivity</h2><table><tr><th>Tariff</th><th>P0 cost</th>" + "".join(f"<th>{esc(s)} saving</th>" for s in strategies if s != base) + "</tr>")
    for tid, tt in res["summary"]["by_tariff"].items():
        ys = tt["strategies"]
        src = tt["tariff"]["source"]
        name = tt["tariff"]["name"] + (f" (<a href='{esc(src['url'])}'>sheet</a>)" if src.get("url") else "")
        h.append(f"<tr><td>{name}</td><td>{_n(ys[base]['total_nok'])}</td>" + "".join(
            f"<td>{_n(ys[s]['saving_nok']['mean'])} ({_pct(ys[s]['saving_pct']['mean'])})</td>" for s in strategies if s != base) + "</tr>")
    h.append("</table>")
    ck = res["summary"].get("caretaker", {}).get(ps)
    if ck:
        h.append("<h2>Governance</h2><ul>")
        h.append(f"<li>{esc(ps)}: {_n(ck['proposals'])} proposals per seed, every supervisory change one governed tool call with its decision record. "
                 f"Routes: " + ", ".join(f"{esc(k)} {_n(v)}" for k, v in ck["routes"].items()) + ".</li>")
        h.append("<li>Validator violations: " + (", ".join(f"{esc(k)} {_n(v)}" for k, v in ck["violations"].items()) or "none") + ".</li>")
        h.append(f"<li>Peak budget: cap steps {_n(ck['algorithms'].get('peak_budget', 0))}, held {_n(ck['algorithms'].get('peak_budget_hold', 0))}, "
                 f"released for comfort, frost or tank {_n(ck['algorithms'].get('peak_budget_released', 0))}.</li>")
        h.append(f"<li>FDD: {_n(ck['fdd_alarms'])} alarms, {_n(ck['fdd_true_alarms'])} true; corrupted proposals caught {_n(ck['optimizer_faults_caught'])}.</li></ul>")
    sc = res["scope"]
    h.append(f"<h2>Scope</h2><p>{esc(sc['method'])}</p><p><b>Established</b></p><ul>" + "".join(f"<li>{esc(x)}</li>" for x in sc["established"]) + "</ul>")
    h.append("<div class='note'><b>Not established</b><ul>" + "".join(f"<li>{esc(x)}</li>" for x in sc["not_established"]) + f"</ul>{esc(sc['pilot_next'])}</div>")
    m = res["manifest"]
    h.append("<h2>Evidence</h2><ul>")
    h.append(f"<li>Testbed commit <code>{esc(str(m['testbed']['commit']))}</code>{' (dirty tree)' if m['testbed'].get('dirty') else ''}, Python {esc(m['python'])}, created {esc(m['created_utc'])}</li>")
    h.append(f"<li>Fixture <code>{esc(m['inputs']['fixture']['path'])}</code> sha256 <code>{esc(m['inputs']['fixture']['sha256'])}</code></li>")
    h.append(f"<li>Scenario <code>{esc(m['inputs']['scenario']['path'])}</code> sha256 <code>{esc(m['inputs']['scenario']['sha256'])}</code></li>")
    for k, v in m["inputs"]["series"].items():
        h.append(f"<li>{esc(k)} series <code>{esc(v['path'])}</code> sha256 <code>{esc(v['sha256'])}</code> "
                 f"<b class='{'ok' if v['verified'] else 'bad'}'>{'verified against the scenario' if v['verified'] else 'MISMATCH'}</b></li>")
    for k, v in m["inputs"]["policy"].items():
        h.append(f"<li>{esc(k)} <code>{esc(v['path'])}</code> sha256 <code>{esc(v['sha256'])}</code></li>")
    if m["inputs"].get("calibration"):
        c = m["inputs"]["calibration"]
        h.append(f"<li>Calibration <code>{esc(c['path'])}</code> sha256 <code>{esc(c['sha256'])}</code>; meter export sha256 <code>{esc(str(c['source_sha256']))}</code> (not in the repository)</li>")
    h.append(f"<li>Policy overrides <code>{esc(json.dumps(m['policy_overrides']))}</code>; seeds {esc(str(m['seeds']))}</li>")
    h.append(f"<li>Rebuild: <code>python -m runner.pilot {esc(' '.join(m['argv']))}</code></li></ul>")
    h.append("</main></body></html>")
    return "".join(h)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="runner.report_pilot")
    p.add_argument("--results", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    res = json.loads(Path(a.results).read_text("utf-8"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "pilot.md").write_text(render_markdown(res), encoding="utf-8")
    (out / "pilot.html").write_text(render_html(res), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
