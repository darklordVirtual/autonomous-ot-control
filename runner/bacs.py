"""Building-automation function audit in the structure of EN ISO 52120-1 (formerly EN 15232-1).

    python -m runner.bacs --out artifacts/bacs            # markdown + json
    python -m runner.bacs --savings artifacts/pilot/pilot.json --out artifacts/bacs

The standard lists the control functions of a building (heating, cooling,
ventilation, lighting, technical building management), defines levels for
each, and assigns a building-automation efficiency class D..A from the levels
reached. It also gives *BAC factors*: for an office, the ratio of thermal and
electrical energy at each class to class C. The EPBD recast (Directive (EU)
2024/1275, Article 13) requires building automation and control systems in
non-residential buildings with heating or combined systems above 290 kW, and
above 70 kW from 2030.

This module records, function by function, what the as-found building (P0)
and the caretaker (P3) implement in the twin, with the twin's data point or
the caretaker's algorithm as the evidence. It then puts the standard's office
BAC factors beside the simulated saving so the two can be compared. It does
**not** issue a certified class: the level definitions and the class
thresholds below are a transcription (`TRANSCRIBED`, checked against the
standard's structure, not a licensed copy), the function list is limited to
what the twin can represent, and a formal classification needs the full
table and the site's installed equipment. Where the as-found level of a real
site differs from P0's, the site's level is what counts.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

STANDARD = "EN ISO 52120-1:2022 (EN 15232-1:2017)"
TRANSCRIPTION_NOTE = ("Function names, levels and class thresholds are transcribed from the standard's structure, "
                      "not quoted from a licensed copy; verify against the standard before any contractual or "
                      "regulatory use. The formal class is assigned by an assessor over the installed equipment.")

#: Office BAC factors (ratio to class C), thermal and electrical, as transcribed.
OFFICE_BAC_FACTORS = {
    "thermal": {"D": 1.51, "C": 1.00, "B": 0.80, "A": 0.70},
    "electrical": {"D": 1.10, "C": 1.00, "B": 0.93, "A": 0.87},
}

EPBD = {
    "directive": "Directive (EU) 2024/1275 (EPBD recast), Article 13",
    "requirements": [
        "non-residential buildings with heating, air-conditioning or combined systems of effective rated output "
        "over 290 kW: building automation and control systems (continuous monitoring, logging, analysis and "
        "adjustment; benchmarking against reference values; fault detection and alerting; interoperability)",
        "the same for systems over 70 kW, by 31 December 2029",
    ],
    "note": "Norway's transposition through the EEA agreement is pending; the thresholds are given as the directive "
            "states them, as the market signal the caretaker's functions answer, not as a Norwegian legal requirement.",
}


@dataclass
class Function:
    id: str
    domain: str
    name: str
    levels: dict[int, str]
    #: minimum level for each class (TRANSCRIBED); a class not listed is the next lower one's
    class_min: dict[str, int]
    p0_level: int
    p0_evidence: str
    p3_level: int
    p3_evidence: str
    applicable: bool = True
    note: str = ""

    def grade(self, level: int) -> str:
        best = "D"
        for cls in ("C", "B", "A"):
            if level >= self.class_min.get(cls, 99):
                best = cls
        return best


FUNCTIONS: list[Function] = [
    Function("1.1", "heating", "Emission control (room temperature)",
             {0: "no automatic control", 1: "central automatic control", 2: "individual room control",
              3: "individual room control with communication", 4: "with communication and presence detection"},
             {"C": 2, "B": 3, "A": 4},
             1, "P0: one scheduled setpoint for every zone (runner.baseline)",
             3, "per-zone heating setpoint written and read back through the governed tools "
                "(`set_zone_setpoint`, `ZONE-0x.AirTemp`); no presence sensor in the twin, so not level 4"),
    Function("1.3", "heating", "Control of distribution network hot-water temperature",
             {0: "no automatic control", 1: "outside temperature compensated", 2: "demand based"},
             {"C": 1, "B": 2, "A": 2},
             0, "P0: tank fixed at 50 degC (strategies.py)",
             2, "weather-reset tank following the radiator curve, demand-held on price and peak "
                "(`weather_reset`, `price_ranked_charge`, `set_tank_setpoint`)"),
    Function("1.5", "heating", "Intermittent control of emission and/or distribution",
             {0: "no automatic control", 1: "automatic with fixed time program",
              2: "automatic with optimum start/stop", 3: "automatic with demand evaluation"},
             {"C": 1, "B": 2, "A": 3},
             1, "P0: fixed 1 h preheat and schedule",
             3, "self-tuning optimal start (`ReheatLearner`), recovery-limited setback by outdoor mean, "
                "occupancy horizon (`optimal_start`, `recovery_setback`, `setback`)"),
    Function("1.7", "heating", "Heat-pump generator control",
             {0: "constant temperature", 1: "variable temperature by outdoor temperature",
              2: "variable temperature by load"},
             {"C": 1, "B": 2, "A": 2},
             0, "P0: fixed tank setpoint",
             2, "tank setpoint from the weather curve plus demand hold; compressor cap for the peak budget "
                "(`set_heat_pump_limit`, ADR-011)"),
    Function("1.10", "heating", "Thermal energy storage control",
             {0: "continuous storage operation", 1: "two-sensor charging", 2: "load-prediction based charging"},
             {"C": 1, "B": 1, "A": 2},
             0, "P0: tank charged on hysteresis only",
             2, "charging ranked by the day-ahead price and held before a peak block (`price_ranked_charge`)",
             note="The twin's price-ranked charging is prediction-based on the published day-ahead price, "
                  "not on a load forecast."),
    Function("3.1", "cooling", "Emission control (room temperature)",
             {0: "no automatic control", 1: "central automatic control", 2: "individual room control",
              3: "individual room control with communication", 4: "with communication and presence detection"},
             {"C": 2, "B": 3, "A": 4},
             1, "P0: one cooling setpoint", 3, "per-zone cooling setpoint through `set_zone_cooling_setpoint`, "
                                               "unoccupied setback (`unoccupied_cooling_setback`)"),
    Function("3.6", "cooling", "Interlock between heating and cooling",
             {0: "no interlock", 1: "partial interlock", 2: "total interlock"},
             {"C": 1, "B": 2, "A": 2},
             2, "IL-01: the twin refuses a cooling setpoint within 2 K of heating",
             2, "IL-01 held by the twin, the signed ToolSpec and the caretaker's validator"),
    Function("4.1", "ventilation", "Supply-air flow control at room level",
             {0: "no automatic control", 1: "time control", 2: "presence control", 3: "demand control (air quality)"},
             {"C": 1, "B": 2, "A": 3},
             1, "P0: fixed AHU schedule",
             3, "DCV on CO2 in every zone (`ZONE-0x.CO2Setpoint`, `set_zone_co2_setpoint`), "
                "IAQ overlay keeps the AHU on above 950 ppm"),
    Function("4.3", "ventilation", "Heat-exchanger icing protection",
             {0: "without", 1: "with"}, {"C": 1, "B": 1, "A": 1},
             1, "twin: HRV frost limit (`hrv_frost_limit_c`)", 1, "same (plant function, not a caretaker lever)"),
    Function("4.5", "ventilation", "Free mechanical cooling",
             {0: "no automatic control", 1: "night cooling", 2: "free cooling (modulated)", 3: "h,x-directed control"},
             {"C": 1, "B": 2, "A": 2},
             0, "P0: none",
             1, "summer night purge through the HRV bypass (`night_purge`); the twin has no modulated free-cooling damper",
             note="Free cooling from the energy wells (`free_cooling_eer`) is a plant property of SITE_001, not a "
                  "controlled function."),
    Function("4.6", "ventilation", "Supply-air temperature control",
             {0: "no automatic control", 1: "constant setpoint", 2: "variable setpoint by outdoor temperature",
              3: "variable setpoint by load"},
             {"C": 1, "B": 2, "A": 3},
             1, "P0: fixed supply-air setpoint",
             3, "Trim & Respond on zone requests outside the heating season (`trim_respond`, `set_supply_air_setpoint`)"),
    Function("5.1", "lighting", "Occupancy control",
             {0: "manual on/off", 1: "manual on/off plus extended-off signal", 2: "automatic detection, auto on / dimmed",
              3: "automatic detection, auto on / auto off", 4: "manual on / dimmed", 5: "manual on / auto off"},
             {"C": 1, "B": 2, "A": 3},
             1, "P0: lighting on the schedule (`schedule` mode)",
             3, "presence mode: lit while people are present, off when they leave (`set_zone_lighting_mode`)"),
    Function("5.2", "lighting", "Daylight control",
             {0: "manual", 1: "automatic (dimming or switching)"}, {"C": 0, "B": 1, "A": 1},
             0, "P0: no daylight dimming", 1, "daylight harvesting to the lux setpoint (`daylight_harvesting`)"),
    Function("7.3", "tbm", "Detecting faults of technical building systems and support to diagnosis",
             {0: "no", 1: "with central reporting of faults"}, {"C": 0, "B": 0, "A": 1},
             0, "P0: none",
             1, "zone-sensor FDD: stale, frozen, drifted, mis-mapped readings alarmed with evidence and ground truth "
                "(`fdd-alarms.jsonl`); escalation route to a human"),
    Function("7.4", "tbm", "Reporting energy consumption, indoor conditions and possibilities for improvement",
             {0: "no", 1: "with"}, {"C": 0, "B": 0, "A": 1},
             0, "P0: none",
             1, "every decision record carries context, algorithms and validation; energy by consumer, comfort, "
                "IAQ and tank safety reported per day (`runner.areas`, `runner.pilot`)"),
    Function("7.5", "tbm", "Smart-grid integration (demand response)",
             {0: "no", 1: "with"}, {"C": 0, "B": 0, "A": 1},
             0, "P0: none",
             1, "demand-response profile on the day-ahead price, peak limiter and monthly peak budget on the grid "
                "tariff's power part (`demand_response`, `peak_limiter`, `peak_budget`)"),
    Function("2.1", "dhw", "Domestic hot-water storage control", {0: "automatic on/off", 1: "with time scheduling",
                                                                 2: "with demand or multi-sensor control"},
             {"C": 1, "B": 2, "A": 2}, 0, "n/a", 0, "n/a", applicable=False,
             note="The twin has no domestic hot water; SITE_001's electric hot water is a constant auxiliary load. "
                  "A site with DHW adds a water-safety overlay before any energy function."),
    Function("6.1", "blinds", "Blind control", {0: "manual", 1: "motorized, manual", 2: "motorized, automatic",
                                               3: "combined light/blind/HVAC control"},
             {"C": 1, "B": 2, "A": 3}, 0, "n/a", 0, "n/a", applicable=False,
             note="No blinds in the twin."),
]


def audit() -> dict[str, Any]:
    rows = []
    for f in FUNCTIONS:
        rows.append({**asdict(f), "p0_grade": f.grade(f.p0_level) if f.applicable else None,
                     "p3_grade": f.grade(f.p3_level) if f.applicable else None})
    applicable = [r for r in rows if r["applicable"]]
    order = {"D": 0, "C": 1, "B": 2, "A": 3}
    overall = {
        "P0": min((r["p0_grade"] for r in applicable), key=order.get),
        "P3": min((r["p3_grade"] for r in applicable), key=order.get),
    }
    counts = {s: {g: sum(1 for r in applicable if r[f"{s.lower()}_grade"] == g) for g in "DCBA"} for s in ("P0", "P3")}
    return {"schema": "ot-bacs-audit/v1", "standard": STANDARD, "transcription": TRANSCRIPTION_NOTE,
            "functions": rows, "overall_class_floor": overall, "grade_counts": counts,
            "office_bac_factors": OFFICE_BAC_FACTORS, "epbd": EPBD,
            "reading": "The class floor is the lowest grade of any applicable function, which is how the standard "
                       "assigns a class; a single function at a low level holds the whole building down. "
                       "The grade counts show where the caretaker sits per function."}


def cross_check(bacs: dict[str, Any], p0_thermal_kwh: float, p0_electrical_kwh: float,
                simulated_saving_kwh: float, from_class: str = "C", to_class: str = "A") -> dict[str, Any]:
    """The standard's office BAC factors applied to the as-found energy, beside the simulated saving.

    `p0_thermal_kwh` is the energy the thermal factor governs (heating, cooling, ventilation heat; here the heat
    pump, backup heater and chiller electricity), `p0_electrical_kwh` the rest the electrical factor governs
    (lighting, fans, auxiliary). Equipment (plug loads) is outside both and is not counted.
    """
    th, el = OFFICE_BAC_FACTORS["thermal"], OFFICE_BAC_FACTORS["electrical"]
    thermal_saving = p0_thermal_kwh * (1 - th[to_class] / th[from_class])
    electrical_saving = p0_electrical_kwh * (1 - el[to_class] / el[from_class])
    factor_saving = thermal_saving + electrical_saving
    return {"from_class": from_class, "to_class": to_class,
            "p0_thermal_kwh": round(p0_thermal_kwh), "p0_electrical_kwh": round(p0_electrical_kwh),
            "factor_thermal_saving_kwh": round(thermal_saving), "factor_electrical_saving_kwh": round(electrical_saving),
            "factor_saving_kwh": round(factor_saving),
            "simulated_saving_kwh": round(simulated_saving_kwh),
            "ratio_simulated_to_factor": round(simulated_saving_kwh / factor_saving, 2) if factor_saving else None,
            "reading": "The BAC factors are statistical defaults for a typical office in the standard's reference "
                       "climate, not a prediction for this building; the simulated saving is one building on one "
                       "year of weather. Agreement in order of magnitude is the check; a ratio far from 1 says the "
                       "twin's as-found case or its levers differ from the standard's reference, and why should be "
                       "stated."}


def to_markdown(b: dict[str, Any], xc: dict[str, Any] | None = None) -> str:
    out = [f"# Building-automation function audit ({b['standard']})", "",
           f"> {b['transcription']}", ""]
    out += ["| Id | Function | As found (P0) | Caretaker (P3) | Evidence (P3) |", "|---|---|---|---|---|"]
    for r in b["functions"]:
        if not r["applicable"]:
            out.append(f"| {r['id']} | {r['name']} | n/a | n/a | {r['note']} |")
            continue
        out.append(f"| {r['id']} | {r['name']} | {r['p0_level']} ({r['p0_grade']}) | {r['p3_level']} ({r['p3_grade']}) "
                   f"| {r['p3_evidence']}{(' *' + r['note'] + '*') if r['note'] else ''} |")
    c = b["grade_counts"]
    out += ["", f"Class floor (lowest applicable function): P0 **{b['overall_class_floor']['P0']}**, "
                f"P3 **{b['overall_class_floor']['P3']}**. Functions at each grade, P3: "
                + ", ".join(f"{g} {c['P3'][g]}" for g in "ABCD") + f"; P0: " + ", ".join(f"{g} {c['P0'][g]}" for g in "ABCD")
            + ".", "", b["reading"], ""]
    out += ["## Office BAC factors", "", "| Class | Thermal | Electrical |", "|---|---:|---:|"]
    for g in "DCBA":
        out.append(f"| {g} | {b['office_bac_factors']['thermal'][g]:.2f} | {b['office_bac_factors']['electrical'][g]:.2f} |")
    if xc:
        out += ["", f"## Cross-check, class {xc['from_class']} to {xc['to_class']}", "",
                f"- As-found energy the factors govern: thermal {xc['p0_thermal_kwh']:,} kWh, electrical "
                f"{xc['p0_electrical_kwh']:,} kWh (equipment excluded).",
                f"- The factors say: {xc['factor_saving_kwh']:,} kWh a year (thermal {xc['factor_thermal_saving_kwh']:,}, "
                f"electrical {xc['factor_electrical_saving_kwh']:,}).",
                f"- The simulation says: {xc['simulated_saving_kwh']:,} kWh a year "
                f"(ratio {xc['ratio_simulated_to_factor']}).", "", xc["reading"]]
    out += ["", "## EPBD context", "", f"{b['epbd']['directive']}:"]
    out += [f"- {r}" for r in b["epbd"]["requirements"]]
    out += ["", b["epbd"]["note"], ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="runner.bacs")
    p.add_argument("--out", required=True)
    p.add_argument("--savings", help="a runner.pilot pilot.json to cross-check the factors against")
    a = p.parse_args(argv)
    b = audit()
    xc = None
    if a.savings:
        s = json.loads(Path(a.savings).read_text("utf-8"))
        y = s["primary"]["year"]
        xc = cross_check(b, y["P0"]["heat_pump"] + y["P0"]["backup_heater"] + y["P0"]["cooling"],
                         y["P0"]["lighting"] + y["P0"]["fans"] + y["P0"]["pumps_dhw"],
                         y["P0"]["kwh"] - y[s["primary"]["strategy"]]["kwh"])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "bacs.json").write_text(json.dumps({**b, "cross_check": xc}, indent=2), encoding="utf-8")
    (out / "bacs.md").write_text(to_markdown(b, xc), encoding="utf-8")
    print(to_markdown(b, xc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
