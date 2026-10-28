"""The A/B/C weak points closed on the execution side and in the reviewer (docs/results/2026-10-28/abc-full-analysis.md):

W1/W2 the work-order gate in the adapter refuses a write REMORA admitted under an unresolved, unsigned, expired or
      non-permitting work order, whoever reviewed it; the authority withdraws a day order once a later one exists;
W3    a proposal declares its basis, and the reviewer and the inline edge refuse one that is not the verified series;
W6/W7 the inline edge gets its context from the reviewer, with the precise problem of the work order.
"""
from __future__ import annotations

import importlib.util
import json
import secrets
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapter import work_orders as wo
from adapter.actuation import ActuationError, ActuatorClient
from adapter.contracts import ToolSpec
from twin.api import build_actuator_app, build_read_app

ROOT = Path(__file__).resolve().parents[2]
OT = ROOT / "deploy" / "ot"


def _load(name: str):
    if str(OT) not in sys.path:
        sys.path.insert(0, str(OT))
    spec = importlib.util.spec_from_file_location(name, OT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def key():
    return wo.key_from_seed(secrets.token_hex(32))


def _table(tmp_path, key, extra=None):
    plans = _load("ot_day_plans")
    t = {}
    for day in ("2026-01-14", "2026-01-15"):
        ref, entry = plans.plan_entry(day)
        t[ref] = wo.sign_entry(ref, entry, key)
    standing = {"task_text": "Lower ZONE-01", "permits": {"set_zone_setpoint": {"ZONE-01": {"min": 19.0, "max": 23.0}}}}
    t["WORK-ORDER-001"] = wo.sign_entry("WORK-ORDER-001", standing, key)
    t.update(extra or {})
    p = tmp_path / "ot_intents.json"
    p.write_text(json.dumps(t), "utf-8")
    return p, t


def _gate(tmp_path, key, ref_of_record, status="resolved", extra=None):
    reg = _load("ot_registry")
    path, table = _table(tmp_path, key, extra)
    trusted = wo.trusted_document(key)["keys"]
    hashes = {r: f"h-{r}" for r, e in table.items() if wo.verify_entry(r, e, trusted)[0]}  # only signed ones resolve
    assessed = {"intent_resolution_status": status, "intent_authority_hash": hashes.get(ref_of_record, "h-none")}
    return reg.WorkOrderGate(str(path), assessed=lambda pid: assessed, intent_hash=hashes.get)


@pytest.mark.parametrize("ref,zone,value,day,why", [
    ("PLAN-2026-01-15", "ZONE-01", 20.0, "2026-01-15", None),
    ("WORK-ORDER-001", "ZONE-01", 20.5, "2026-01-18", None),          # a standing order is valid every day
    ("PLAN-2026-01-14", "ZONE-01", 20.0, "2026-01-15", "expired"),     # yesterday's plan (W2)
    ("PLAN-2026-01-15", "ZONE-02", 22.0, "2026-01-15", "not_permitted"),  # off-plan value
    ("PLAN-2026-01-15", "ZONE-03", 20.0, "2026-01-15", "not_permitted"),
    ("PLAN-2026-01-15-F", "ZONE-02", 22.0, "2026-01-15", "no_signed_work_order"),  # the proposer's own (W1)
])
def test_the_gate_lets_through_only_what_a_signed_valid_work_order_permits(tmp_path, key, ref, zone, value, day, why):
    forged = {"PLAN-2026-01-15-F": {"task_text": "x", "valid_on": "2026-01-15",
                                    "permits": {"set_zone_setpoint": {"ZONE-02": [22.0]}}}}
    gate = _gate(tmp_path, key, ref, extra=forged)
    args = {"zone_id": zone, "setpoint_c": value}
    if why is None:
        assert gate.check("p-1", "set_zone_setpoint", args, day) == ref
    else:
        with pytest.raises(ActuationError, match=f"work_order_gate:{why}"):
            gate.check("p-1", "set_zone_setpoint", args, day)


def test_the_gate_refuses_an_unresolved_work_order_and_an_unreadable_record(tmp_path, key):
    with pytest.raises(ActuationError, match="unresolved_work_order"):
        _gate(tmp_path, key, "PLAN-2026-01-15", status="unresolved").check("p", "set_zone_setpoint",
                                                                             {"zone_id": "ZONE-01", "setpoint_c": 20.0}, "2026-01-15")
    reg = _load("ot_registry")
    path, _ = _table(tmp_path, key)

    def boom(pid):
        raise RuntimeError("chain down")
    with pytest.raises(ActuationError, match="record_unavailable"):
        reg.WorkOrderGate(str(path), assessed=boom, intent_hash=lambda r: None).check(
            "p", "set_zone_setpoint", {"zone_id": "ZONE-01", "setpoint_c": 20.0}, "2026-01-15")


def test_a_refused_write_never_reaches_the_plant(tmp_path, key, twin, tokens):
    reg = _load("ot_registry")
    gate = _gate(tmp_path, key, "PLAN-2026-01-14")  # expired
    t = reg.OtTools(actuator=ActuatorClient("http://testserver", tokens.actuator,
                                            client=TestClient(build_actuator_app(twin, tokens))),
                    read_base_url="http://testserver", read_token=tokens.read, toolspec=ToolSpec.load(),
                    read_client=TestClient(build_read_app(twin, tokens)),
                    proposal_id=lambda: "5d2c8f0e-1111-4222-8333-944455556666", work_order_gate=gate)
    rev = twin.revision
    with pytest.raises(ActuationError, match="work_order_gate:expired"):
        t.set_zone_setpoint({"zone_id": "ZONE-01", "setpoint_c": 20.5})
    assert twin.revision == rev and not twin.operations


def test_the_authority_withdraws_a_day_order_once_a_later_one_exists(tmp_path):
    auth = _load("ot_authority")
    seed = tmp_path / "seed"
    seed.write_text(secrets.token_hex(32), "utf-8")
    table = tmp_path / "ot_intents.json"
    table.write_text(json.dumps({"WORK-ORDER-001": {"task_text": "standing"}}), "utf-8")
    auth.issue("plan-P1", "2026-01-15", seed, table)
    auth.issue("lab", "2026-01-15", seed, table)
    out = auth.issue("plan-P1", "2026-01-16", seed, table)
    assert sorted(out["retired"]) == ["LAB-2026-01-15", "PLAN-2026-01-15"]
    assert sorted(json.loads(table.read_text("utf-8"))) == ["PLAN-2026-01-16", "WORK-ORDER-001"]


def test_the_reviewer_refuses_a_basis_that_is_not_the_verified_series(key):
    rev = _load("ot_reviewer")
    plans = _load("ot_day_plans")
    ref, entry = plans.plan_entry("2026-01-15")
    intents = {ref: wo.sign_entry(ref, entry, key)}
    trusted = wo.trusted_document(key)["keys"]
    call = {"tool_name": "set_zone_setpoint", "intent_ref": ref, "arguments": {"zone_id": "ZONE-01", "setpoint_c": 20.0}}
    verified = "sha256:" + "a" * 64
    ok = lambda basis, v=verified: rev.judge(call, intents, trusted, "2026-01-15", lambda z: 21.0, 1.0,  # noqa: E731
                                            basis=basis, verified_series=v)
    assert ok(verified)[0] is True
    assert ok("sha256:" + "b" * 64) == (False, "the proposal was computed from a series that is not the verified one")
    assert ok(None) == (False, "the proposal declares no basis series")
    assert ok(None, v=None)[0] is True  # the deployment names no verified series: the check is off


def test_the_edge_is_told_the_precise_problem_and_refuses_with_it(key):
    rev = _load("ot_reviewer")
    plans = _load("ot_day_plans")
    spec = importlib.util.spec_from_file_location("edge_srv", ROOT / "federation" / "edges" / "_inline_template" / "server.py")
    edge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(edge)
    ref, entry = plans.plan_entry("2026-01-15")
    yref, yentry = plans.plan_entry("2026-01-14")
    intents = {ref: wo.sign_entry(ref, entry, key), yref: wo.sign_entry(yref, yentry, key), "PLAN-F": dict(entry)}
    trusted = wo.trusted_document(key)["keys"]
    status = {"sim_utc": "2026-01-15T12:00:00Z", "sim_time_s": 43200}
    verified = "sha256:" + "a" * 64

    def ask(ref_, basis=verified, value=20.0):
        call = {"tool_name": "set_zone_setpoint", "intent_ref": ref_, "arguments": {"zone_id": "ZONE-01", "setpoint_c": value}}
        cx = rev.edge_context(call, intents, trusted, status, 21.0, 1.0, basis, verified)
        return edge.decide({"call": call, "context": cx})

    assert ask(ref)["verdict"] == "permit"
    assert ask(yref)["reason"] == "work_order_expired"
    assert ask("PLAN-F")["reason"] == "work_order_unsigned"
    assert ask(None)["reason"] == "work_order_missing"
    assert ask(ref, basis="sha256:" + "b" * 64)["reason"] == "basis_not_verified"
    assert ask(ref, value=22.0)["reason"] == "value_not_in_work_order"


def test_the_shipped_work_orders_state_what_they_permit():
    shipped = json.loads((OT / "ot_intents.json").read_text("utf-8"))
    for ref in ("WORK-ORDER-001", "WORK-ORDER-002", "WORK-ORDER-003", "WORK-ORDER-PLANT"):
        assert shipped[ref].get("permits"), ref
    assert "permits" not in shipped["MON-ROUND"]  # a read-only round permits no write
    compose = (ROOT / "compose.governed.yaml").read_text("utf-8")
    assert "REMORA_OT_WORK_ORDER_GATE: enforce" in compose
