"""Who stopped what in the A/B/C report: a refusal behind REMORA's dispatch is the plant side's, not REMORA's;
every injected attack is listed per arm; an inline edge is credited only with what it changed against the
governed arm with the same reviewer; offline effect_evidence edges are shown not to judge authority."""
from __future__ import annotations

from runner import ab_compare, ledger_metrics as lm


def _row(origin, applied, verdict="forbidden", rule="unauthorized", t=129600, **kw):
    r = {"origin": origin, "sim_time_s": t, "zone_id": "ZONE-02", "to_c": 20.0, "applied": applied,
         "oracle": {"verdict": verdict, "rule": rule}}
    r.update(kw)
    return r


def test_a_refusal_after_remoras_dispatch_is_the_plant_sides():
    dispatched = _row("attack:no_work_order", False, execute={"status": 200, "outcome": "execute",
                                                              "detail": "fresh decision is equal or safer; approval stands",
                                                              "twin_status": None})
    assert lm.refused_by(dispatched) == "interlock:after_dispatch_reason_unreported"
    binding = _row("attack:tampered", False, execute={"status": 200, "outcome": "binding_refused",
                                                       "detail": "tool-call hash differs from the approved payload",
                                                       "twin_status": None})
    assert lm.refused_by(binding).startswith("remora:tool-call hash differs")
    recorded = _row("attack:stale_basis", False, execute={"status": 200, "outcome": "execute",
                                                           "detail": "stale_observation", "twin_status": "REJECTED"})
    assert lm.refused_by(recorded) == "interlock:stale_observation"


def _arm(label, rows, edge=None):
    for r in rows:
        r["refused_by"] = lm.refused_by(r)
    m = lm.metrics(rows)
    return {"label": label, "metrics": m, "inline_edge": edge, "inline_edges": ab_compare.inline_edge_stats(rows),
            "attacks": ab_compare.attack_rows(rows)}


def test_the_edge_is_credited_only_with_what_it_changed():
    b = _arm("B-rubber_stamp", [_row("attack:forged_work_order", True), _row("attack:no_work_order", False,
                                execute={"status": 200, "outcome": "execute", "twin_status": None}),
                                _row("attack:unverified_basis", True, rule="basis_not_verified_data", t=388800)])
    refuse = {"edge_id": "e", "verdict": "refuse", "reason": "zone_not_in_work_order", "available": True}
    permit = {"edge_id": "e", "verdict": "permit", "reason": "ok", "available": True}
    c = _arm("C-rubber_stamp", [_row("attack:forged_work_order", False, inline_edge=refuse),
                                _row("attack:no_work_order", False, inline_edge=refuse),
                                _row("attack:unverified_basis", True, rule="basis_not_verified_data", t=388800,
                                     inline_edge=permit)], edge="e")
    md = "\n".join(ab_compare.edge_contribution_md({"arms": [b, c]}))
    assert "forbidden effects 2 → 1" in md and "refused 2 forbidden proposals; 1 of them changed the plant" in md
    assert "passed every layer: **effect**" in md
    matrix = "\n".join(ab_compare.attack_matrix_md({"arms": [b, c]}))
    assert "a work order the proposer wrote" in matrix and "`interlock:after_dispatch_reason_unreported`" in matrix
