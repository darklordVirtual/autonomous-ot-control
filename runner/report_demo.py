"""Interactive demo page for a pilot evidence pack: one self-contained HTML file, no dependencies.

    python -m runner.report_demo --pack artifacts/pilot-site-001 --out artifacts/pilot-site-001/demo.html

Reads `pilot.json`, `sweep.json` (optional, from `runner.peak_sweep`), `decision-records.jsonl`
and the calibration file the pack names. The page lets a reader move the peak budget and see
the year's cost, peaks and comfort change; follow one winter day decision by decision (profile,
overlays, cap, tank, power against the budget, route); compare the baseline model with the
site's meters month by month; and read the governance counts and the evidence digests.
Everything on the page is data from the pack; the page computes nothing new.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runner.report_pilot import CSS, STRATEGY_NAMES, _n

ROOT = Path(__file__).resolve().parents[1]

JS = r"""
const D = window.__DEMO__;
const fmt = (v, d=0) => (v==null? '–' : Number(v).toLocaleString('en-US',{maximumFractionDigits:d,minimumFractionDigits:d}).replace(/,/g,' '));
const pct = v => v==null? '–' : v.toFixed(1)+' %';
const C = {P0:'#9aa5b1',P1:'#6b8fb3',P2:'#3f7fbf',P3:'#1f5fa8',P3pb:'#0b8a5a',budget:'#b9410f',measured:'#9aa5b1',simulated:'#1f5fa8'};
const MN = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];

function bars(el, series, labels, unit, hline){
  const W=1040,H=260,L=56,T=16,B=36, keys=Object.keys(series);
  const vmax=Math.max(hline||0, ...keys.flatMap(k=>series[k]))||1;
  const pw=W-L-12, ph=H-T-B, gw=pw/labels.length, bw=gw/(keys.length+1);
  let s=`<svg viewBox="0 0 ${W} ${H}" width="100%">`;
  for(let i=0;i<5;i++){const yv=vmax*i/4, yy=T+ph-ph*i/4; s+=`<line x1="${L}" y1="${yy}" x2="${W-12}" y2="${yy}" stroke="#dde3e8"/><text x="${L-6}" y="${yy+4}" text-anchor="end" fill="#5b6b7a">${fmt(yv)}</text>`;}
  labels.forEach((lab,j)=>{const x0=L+j*gw; s+=`<text x="${x0+gw/2}" y="${H-12}" text-anchor="middle" fill="#5b6b7a">${lab}</text>`;
    keys.forEach((k,i)=>{const v=series[k][j], h=ph*v/vmax; s+=`<rect x="${x0+bw*(i+.5)}" y="${T+ph-h}" width="${bw*.9}" height="${h}" fill="${C[k]||'#888'}"><title>${k} ${lab}: ${fmt(v)} ${unit}</title></rect>`;});});
  if(hline){const yy=T+ph-ph*hline/vmax; s+=`<line x1="${L}" y1="${yy}" x2="${W-12}" y2="${yy}" stroke="${C.budget}" stroke-dasharray="6 4" stroke-width="2"/><text x="${W-14}" y="${yy-6}" text-anchor="end" fill="${C.budget}">budget ${fmt(hline)} kW</text>`;}
  s+='</svg>';
  el.innerHTML=s+'<div class="legend">'+keys.map(k=>`<span><i style="background:${C[k]||'#888'}"></i>${D.names[k]||k}</span>`).join('')+'</div>';
}

function renderSweep(){
  const sw=D.sweep; if(!sw){document.getElementById('sweep').style.display='none'; return;}
  const rows=sw.rows.filter(r=>r.strategy==='P3pb').sort((a,b)=>a.budget_kw-b.budget_kw);
  const p0=sw.rows.find(r=>r.strategy==='P0'), p3=sw.rows.find(r=>r.strategy==='P3');
  const sl=document.getElementById('budget'); sl.min=0; sl.max=rows.length-1; sl.value=Math.min(rows.length-1, rows.findIndex(r=>r.budget_kw===D.pack_budget)>=0?rows.findIndex(r=>r.budget_kw===D.pack_budget):0);
  const months=Object.keys(p0.monthly_peak_kw).sort(), labels=months.map(m=>MN[+m.slice(5,7)-1]);
  function draw(){
    const r=rows[+sl.value];
    document.getElementById('bval').textContent=fmt(r.budget_kw)+' kW';
    document.getElementById('skpi').innerHTML=[
      ['Cost', fmt(r.total_nok)+' NOK', `P0 ${fmt(p0.total_nok)} · P3 ${fmt(p3.total_nok)}`],
      ['Saving vs P0', pct(r.saving_pct), `${fmt(r.saving_nok)} NOK; P3 alone ${pct(p3.saving_pct)}`],
      ['Winter peak, mean', fmt(r.peak_kw_winter_mean)+' kW', `P0 ${fmt(p0.peak_kw_winter_mean)} · P3 ${fmt(p3.peak_kw_winter_mean)}`],
      ['Comfort / releases', `${fmt(r.comfort_dh)} dh · ${fmt(r.released)}`, `P0 ${fmt(p0.comfort_dh)} dh; backup ${fmt(r.backup_kwh)} kWh; fallback ${fmt(r.fallback)}`]
    ].map(k=>`<div class="kpi"><b>${k[1]}</b><span>${k[0]} — ${k[2]}</span></div>`).join('');
    bars(document.getElementById('schart'), {P0:months.map(m=>p0.monthly_peak_kw[m]), P3:months.map(m=>p3.monthly_peak_kw[m]), P3pb:months.map(m=>r.monthly_peak_kw[m])}, labels, 'kW', r.budget_kw);
    document.getElementById('stable').innerHTML='<tr><th>Budget kW</th><th>Cost NOK</th><th>Saving</th><th>Winter peak kW</th><th>Max peak kW</th><th>kWh</th><th>Comfort dh</th><th>Backup kWh</th><th>Releases</th></tr>'+
      [p0,p3,...rows].map(x=>`<tr${x===r?' style="background:#e8f5ee"':''}><td>${x.strategy==='P3pb'?fmt(x.budget_kw):x.strategy}</td><td>${fmt(x.total_nok)}</td><td>${pct(x.saving_pct)}</td><td>${fmt(x.peak_kw_winter_mean)}</td><td>${fmt(x.peak_kw_max)}</td><td>${fmt(x.kwh)}</td><td>${fmt(x.comfort_dh)}</td><td>${fmt(x.backup_kwh)}</td><td>${fmt(x.released)}</td></tr>`).join('');
  }
  sl.oninput=draw; draw();
}

function renderDay(){
  const days=Object.keys(D.records).sort(); const sel=document.getElementById('day');
  if(!days.length){document.getElementById('dayblock').style.display='none';return;}
  sel.innerHTML=days.map(d=>`<option value="${d}">${d}</option>`).join('');
  function draw(){
    const rs=D.records[sel.value];
    const W=1040,H=300,L=56,T=16,B=40,pw=W-L-12,ph=H-T-B, n=rs.length;
    const vmax=Math.max(...rs.map(r=>r.power_kw), D.pack_budget||0)*1.1||1;
    const x=i=>L+pw*i/(n-1), y=v=>T+ph-ph*v/vmax;
    let s=`<svg viewBox="0 0 ${W} ${H}" width="100%">`;
    for(let i=0;i<5;i++){const yv=vmax*i/4; s+=`<line x1="${L}" y1="${y(yv)}" x2="${W-12}" y2="${y(yv)}" stroke="#dde3e8"/><text x="${L-6}" y="${y(yv)+4}" text-anchor="end" fill="#5b6b7a">${fmt(yv)}</text>`;}
    rs.forEach((r,i)=>{ if(r.occupied){s+=`<rect x="${x(i)}" y="${T}" width="${pw/(n-1)}" height="${ph}" fill="#fff3d6" opacity=".6"/>`;}});
    for(let h=0;h<24;h+=3){const i=rs.findIndex(r=>r.hour===h); if(i>=0) s+=`<text x="${x(i)}" y="${H-14}" text-anchor="middle" fill="#5b6b7a">${String(h).padStart(2,'0')}:00</text>`;}
    if(D.pack_budget) s+=`<line x1="${L}" y1="${y(D.pack_budget)}" x2="${W-12}" y2="${y(D.pack_budget)}" stroke="${C.budget}" stroke-dasharray="6 4" stroke-width="2"/>`;
    s+=`<polyline fill="none" stroke="${C.P3pb}" stroke-width="2" points="${rs.map((r,i)=>x(i)+','+y(r.power_kw)).join(' ')}"/>`;
    s+=`<polyline fill="none" stroke="#1f5fa8" stroke-width="1.5" stroke-dasharray="3 3" points="${rs.map((r,i)=>x(i)+','+y(r.cap*vmax*0.5)).join(' ')}"/>`;
    rs.forEach((r,i)=>{const col=r.hp==='peak_budget_released'?C.budget:(r.route==='fallback'||r.route==='escalate')?'#b9410f':(r.hp||'').startsWith('peak_budget')?C.P3pb:'#9aa5b1';
      s+=`<circle cx="${x(i)}" cy="${y(r.power_kw)}" r="3.5" fill="${col}"><title>${r.utc.slice(11,16)} ${fmt(r.power_kw)} kW · ${r.profile} ${r.overlays.join('+')} · HP ${r.hp} cap ${r.cap} · tank ${r.tank_c}→${r.tank_sp} · route ${r.route}</title></circle>`;});
    s+='</svg>';
    document.getElementById('dchart').innerHTML=s+`<div class="legend"><span><i style="background:${C.P3pb}"></i>building power, hourly-mean basis (kW)</span><span><i style="background:#1f5fa8"></i>compressor cap (dashed, ×½ scale)</span><span><i style="background:${C.budget}"></i>budget / release</span><span><i style="background:#fff3d6"></i>occupied</span></div>`;
    document.getElementById('dtable').innerHTML='<tr><th>UTC</th><th>Profile</th><th>Overlays</th><th>Out °C</th><th>Price</th><th>Power kW</th><th>Cap</th><th>Tank °C → SP</th><th>Heat pump</th><th>Validation</th><th>Route</th><th>Changes</th></tr>'+
      rs.map(r=>`<tr><td>${r.utc.slice(11,16)}</td><td>${r.profile}</td><td>${r.overlays.join(', ')||'–'}</td><td>${fmt(r.outdoor_c,1)}</td><td>${fmt(r.price,2)}</td><td>${fmt(r.power_kw)}</td><td>${r.cap}</td><td>${fmt(r.tank_c,1)} → ${fmt(r.tank_sp,1)}</td><td>${r.hp}</td><td>${r.violations.length?r.violations.join(', '):'ok'}</td><td>${r.route}</td><td>${r.changes.join('; ')||'–'}</td></tr>`).join('');
  }
  sel.onchange=draw; draw();
}

function renderCalibration(){
  const c=D.calibration; if(!c||!c.validation){document.getElementById('cal').style.display='none';return;}
  const v=c.validation.total, bm=v.by_month_kwh||{}; const months=Object.keys(bm).sort();
  bars(document.getElementById('cchart'), {measured:months.map(m=>bm[m][0]), simulated:months.map(m=>bm[m][1])}, months.map(m=>MN[+m.slice(5,7)-1]+' '+m.slice(2,4)), 'kWh');
  document.getElementById('ctext').innerHTML=`Site <b>${c.site_id}</b>: monthly CV(RMSE) <b>${v.monthly_cv_rmse_pct} %</b>, NMBE <b>${v.monthly_nmbe_pct} %</b> over ${v.months} months (Guideline 14 monthly ${v.guideline14_monthly?'<b class="ok">met</b>':'<b class="bad">not met</b>'}); hourly CV(RMSE) ${v.cv_rmse_pct} % (${v.guideline14_hourly?'met':'not met'}). Measured ${fmt(v.measured_kwh)} kWh, simulated ${fmt(v.simulated_kwh)} kWh on the hours both have. In-sample.`;
}
renderSweep(); renderDay(); renderCalibration();
"""


def _records_for_demo(path: Path, strategy: str, seed: int) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    if not path.exists():
        return out
    for line in path.read_text("utf-8").splitlines():
        r = json.loads(line)
        if r.get("strategy") != strategy or r.get("seed") != seed:
            continue
        ctx = r["context"]
        prop = r.get("proposal") or {}
        day = r["utc"][:10]
        out.setdefault(day, []).append({
            "utc": r["utc"], "hour": int(r["utc"][11:13]), "profile": r["base_profile"], "overlays": r["overlays"],
            "occupied": ctx.get("occupied"), "outdoor_c": ctx.get("outdoor_c"), "price": ctx.get("price_nok_per_kwh"),
            "power_kw": ctx.get("power_kw"), "tank_c": ctx.get("tank_c"), "tank_sp": prop.get("tank_c"),
            "cap": prop.get("hp_max_fraction"), "hp": (r.get("algorithms") or {}).get("heat_pump"),
            "violations": r["validation"]["violations"], "route": r["route"], "changes": r.get("changes") or [],
            "budget": r.get("peak_budget")})
    return out


def render(pack: Path) -> str:
    res = json.loads((pack / "pilot.json").read_text("utf-8"))
    sweep = json.loads((pack / "sweep.json").read_text("utf-8")) if (pack / "sweep.json").exists() else None
    ps = res["primary"]["strategy"]
    y = res["primary"]["year"]
    r = y[ps]
    base = res["baseline"]
    budget = ((res["manifest"].get("policy_overrides") or {}).get("peak_budget") or {}).get("kw")
    records = _records_for_demo(pack / "decision-records.jsonl", ps, res["seeds"][0])
    data = {"names": STRATEGY_NAMES, "sweep": sweep, "records": records, "pack_budget": budget,
            "calibration": res.get("calibration")}
    tariff = res["summary"]["by_tariff"][res["primary"]["tariff"]]["tariff"]
    m = res["manifest"]
    ck = res["summary"].get("caretaker", {}).get(ps) or {}
    sc = res["scope"]
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;")  # noqa: E731
    h = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Demo · governed autonomy on {esc(res['building_id'])}</title><style>{CSS}
input[type=range]{{width:100%}}.row{{display:flex;gap:16px;align-items:center;margin:8px 0}}select{{font:inherit;padding:4px 8px}}
.tbl{{max-height:420px;overflow:auto;border:1px solid var(--line);border-radius:8px}}.tbl table{{margin:0}}.tbl th{{position:sticky;top:0;background:#fff}}
</style></head><body><main>
<h1>Governed autonomy, one calibrated building</h1>
<p class='sub'>{esc(res['building_id'])} · {esc(res['area'])} {esc(res['area_name'])} · {res['days']} days · {len(res['seeds'])} seeds · priced on {esc(tariff['name'])} · simulation only, IPMVP Option D</p>
<div class='kpis'>
<div class='kpi'><b>{_n(r['saving_nok']['mean'])} NOK</b><span>saved {'a year' if res['days'] >= 360 else 'over the period'} by {esc(STRATEGY_NAMES.get(ps, ps))} vs P0 ({r['saving_pct']['mean']:.1f} %; seeds {_n(r['saving_nok']['min'])}..{_n(r['saving_nok']['max'])})</span></div>
<div class='kpi'><b>{_n(r['saving_kwh']['mean'])} kWh</b><span>{r['saving_kwh_pct']['mean']:.1f} % of {_n(y[base]['kwh'])} kWh</span></div>
<div class='kpi'><b>−{_n(r['peak_reduction_kw_winter_mean'])} kW</b><span>winter peak, {_n(y[base]['peak_kw_winter_mean'])} → {_n(r['peak_kw_winter_mean'])} kW; power part {_n(y[base]['grid_power_nok'])} → {_n(r['grid_power_nok'])} NOK</span></div>
<div class='kpi'><b>{_n(r['comfort_dh'])} dh</b><span>comfort degree-hours occupied (P0 {_n(y[base]['comfort_dh'])}); backup {_n(r['backup_heater'])} kWh; CO₂ excess {_n(r['co2_excess_ppmh'])} ppm·h</span></div>
</div>
<section id='sweep'><h2>Choose the budget</h2>
<p>The grid tariff's power part is charged on the month's highest hourly mean. Move the budget: the caretaker caps the compressor so the hour stays under it and releases the cap only for comfort, frost or a tank near the backup heater. A budget that is too tight is released on the coldest mornings, and those hours set the peak.</p>
<div class='row'><input id='budget' type='range' step='1'><b id='bval' style='min-width:90px'></b></div>
<div class='kpis' id='skpi'></div><div id='schart'></div><table id='stable'></table>
</section>
<section id='dayblock'><h2>One day, decision by decision</h2>
<p>Every 15 minutes the caretaker proposes one bounded change, the independent validator checks it against the site policy, and the result is one governed tool call with its decision record. Hover a point. <select id='day'></select></p>
<div id='dchart'></div><div class='tbl'><table id='dtable'></table></div>
</section>
<section id='cal'><h2>The baseline model against the site's meters</h2><p id='ctext'></p><div id='cchart'></div></section>
<h2>Governance</h2><ul>
<li>{esc(ps)}: {_n(ck.get('proposals', 0))} proposals per seed; routes {', '.join(f"{k} {_n(v)}" for k, v in (ck.get('routes') or {}).items())}.</li>
<li>Validator violations: {', '.join(f"{k} {_n(v)}" for k, v in (ck.get('violations') or {}).items()) or 'none'}. Corrupted proposals caught: {_n(ck.get('optimizer_faults_caught', 0))}.</li>
<li>Peak budget: cap steps {_n((ck.get('algorithms') or {}).get('peak_budget', 0))}, held {_n((ck.get('algorithms') or {}).get('peak_budget_hold', 0))}, released {_n((ck.get('algorithms') or {}).get('peak_budget_released', 0))}.</li>
<li>FDD: {_n(ck.get('fdd_alarms', 0))} alarms, {_n(ck.get('fdd_true_alarms', 0))} true.</li></ul>
<h2>Scope</h2><p>{esc(sc['method'])}</p><div class='note'><b>Not established</b><ul>{''.join(f'<li>{esc(x)}</li>' for x in sc['not_established'])}</ul>{esc(sc['pilot_next'])}</div>
<h2>Evidence</h2><ul>
<li>Testbed commit <code>{esc(m['testbed']['commit'])}</code>; fixture <code>{esc(m['inputs']['fixture']['path'])}</code> <code>{esc(m['inputs']['fixture']['sha256'][:24])}…</code>; scenario <code>{esc(m['inputs']['scenario']['path'])}</code> <code>{esc(m['inputs']['scenario']['sha256'][:24])}…</code></li>
<li>Series verified against the scenario's digests: {', '.join(f"{k} {'ok' if v['verified'] else 'MISMATCH'}" for k, v in m['inputs']['series'].items())}; site policy <code>{esc(m['inputs']['policy']['site_policy']['sha256'][:24])}…</code>; overrides <code>{esc(json.dumps(m['policy_overrides']))}</code></li>
<li>Full report with every table: <code>pilot.html</code> / <code>pilot.md</code>; rebuild with <code>python -m runner.pilot {esc(' '.join(m['argv']))}</code></li></ul>
</main><script>window.__DEMO__={json.dumps(data)};</script><script>{JS}</script></body></html>"""
    return h


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="runner.report_demo")
    p.add_argument("--pack", required=True, help="directory written by runner.pilot (and runner.peak_sweep)")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    Path(a.out).write_text(render(Path(a.pack)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
