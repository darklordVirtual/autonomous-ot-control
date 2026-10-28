"""Plant sizing from the design heat load (runner.calibration.size_plant) and the ground-source heat pump.

The first calibrated run (ADR-011) showed that a fixture built from certificate priors sizes the
heat pump as the installed radiators: on SITE_001 a 463 kW pump drew about 150 kW electric in a
January recovery while the site's meters show daytime medians near 30 kW. `size_plant` derives
the heat source from the design load instead and records every assumption.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner.calibration import size_plant
from twin import plant as plant_mod

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "twin/fixtures/calibrated/site-001-v2.json"
V3 = ROOT / "twin/fixtures/calibrated/site-001-v3.json"


def test_size_plant_derives_the_heat_source_from_the_design_load_and_records_it():
    cfg = json.loads(V2.read_text("utf-8"))
    out = size_plant(cfg, hp_share=0.55, dut_c=-20.0, hp_source_c=4.0, seasonal_cop=4.28, supply_mean_c=40.0,
                     tank_l_per_kw=25.0, building_id="x-v3")
    ps = out["calibration"]["plant_sizing"]
    ua = sum(z["ua_w_per_k"] for z in cfg["zones"])
    assert ps["transmission_w_per_k"] == pytest.approx(ua, abs=0.1)
    assert ps["design_heat_load_w"] == pytest.approx((ua + ps["ventilation_w_per_k"]) * 41.0, abs=1.0)
    assert out["plant"]["hp_nominal_heat_w"] == pytest.approx(0.55 * ps["design_heat_load_w"], abs=1.0)
    assert out["plant"]["backup_heater_w"] == pytest.approx(0.45 * ps["design_heat_load_w"], abs=1.0)
    assert out["plant"]["tank_volume_l"] == pytest.approx(25.0 * out["plant"]["hp_nominal_heat_w"] / 1000, abs=1.0)
    assert out["plant"]["hp_source_c"] == 4.0 and out["building_id"] == "x-v3"
    # the Carnot fraction reproduces the certificate's seasonal COP at the mean supply temperature
    assert plant_mod.heat_pump_cop(4.0, 40.0, out["plant"]["hp_carnot_fraction"]) == pytest.approx(4.28, abs=0.02)
    assert cfg["plant"]["hp_nominal_heat_w"] == 463060.0                   # the input is not mutated
    assert out["plant"]["hp_nominal_heat_w"] < 0.2 * cfg["plant"]["hp_nominal_heat_w"]


def test_the_committed_v3_fixture_is_what_size_plant_builds_from_v2():
    rebuilt = size_plant(json.loads(V2.read_text("utf-8")), seasonal_cop=4.28, building_id="site-001-v3")
    committed = json.loads(V3.read_text("utf-8"))
    assert rebuilt == committed


def test_ground_source_pump_ignores_outdoor_temperature_and_air_source_does_not():
    cfg = json.loads(V3.read_text("utf-8"))["plant"]
    ground = plant_mod.PlantConfig.from_dict(cfg)
    air = plant_mod.PlantConfig.from_dict({**cfg, "hp_source_c": None})
    assert ground.hp_source_c == 4.0 and air.hp_source_c is None
    with pytest.raises(plant_mod.PlantError):
        plant_mod.PlantConfig.from_dict({**cfg, "hp_source_c": 40.0})
    # the same plant state and setpoints, a -20 degC hour: the ground-source pump keeps its output and COP
    from dataclasses import replace
    from twin.model import Twin, load_config
    from twin.scenarios import load_scenario
    from runner.areas import scenario_path
    raw = json.loads(scenario_path("NO4").read_text("utf-8"))
    raw["duration_seconds"] = 2 * 3600
    sc = load_scenario(raw, base_dir=scenario_path("NO4").parent)
    outputs = {}
    for name, src in (("ground", 4.0), ("air", None)):
        full = load_config(V3)
        full["plant"]["hp_source_c"] = src
        tw = Twin(full, sc)
        tw.setpoints = replace(tw.setpoints, tank_c=55.0)
        tw.plant_state = replace(tw.plant_state, tank_c=45.0)
        tw.advance(1800)
        p = tw.points
        outputs[name] = (p["HP-01.HeatOutput"], p["HP-01.COP"], sc.outdoor_c(tw.clock.now_s))
    assert outputs["ground"][2] == outputs["air"][2] < 0.0
    assert outputs["ground"][0] > 0 and outputs["ground"][0] >= outputs["air"][0]
    assert outputs["ground"][1] > outputs["air"][1] or outputs["air"][0] == 0.0
