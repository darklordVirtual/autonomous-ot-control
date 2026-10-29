"""Offline authority_fixture harness: both checks on the same captured input, both verdicts recorded.

    python -m runner.authority_harness --fixtures federation/authority/fixtures/t3 \
        --verifier federation/authority/template-verifier --out <dir>

For every case of a sealed set (runner.authority_fixtures):

- the **delegation check** is the verifier's (APS's, or the stand-in), run
  once over the set as a subprocess with the scorer's timeout. Its answer per
  case is ``pass`` or ``refuse`` with a registered machine-readable reason and
  its extracted delegation identity. ``indeterminate`` is recorded separately
  with a null scored verdict, never as a refusal or catch. Other answer problems: ``error`` (the
  process failed), ``timeout``, ``malformed`` (an answer outside pass/refuse)
  or ``unanswered``;
- the **work-order check** is the testbed's (runner.work_order.check) on the
  same normalized call, work order and delegation;
- **admitted** means both passed. Neither check can admit on its own;
- the **oracle** judges the same call from how the case was built
  (``delegation_fault``) and the work order's range, without reading either
  verdict. Its permitted/forbidden must agree with the expected admission.

Each column is compared with the expectation the manifest fixed before any
verifier ran. The run passes only when the set is sealed and unchanged, the
oracle agrees with the manifest, and both checks, verifier identity and registered
delegation reasons give the expected result on every case. Historical verdict-only
reproduction requires an explicit flag and is labelled in both output formats.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from runner import authority_fixtures as af
from runner import work_order as wo
from runner import edge_check
from runner.edge_check import run_adapter
from runner.oracle import Tables, judge

SCHEMA = "ot-authority-result/v1"
TABLES = Tables(zones=("ZONE-01", "ZONE-02", "ZONE-03"), setpoint_min_c=19.0, setpoint_max_c=23.0,
                max_delta_c=1.0, budgets={})


def oracle_verdict(case: dict[str, Any], fault: str | None) -> dict[str, Any]:
    """The oracle on the same call: work order as an inclusive range, delegation fault as built."""
    call, order = case["call"], case["work_order"]
    rng = order["value_range"]
    proposal = {"at_sim_s": 0, "intent_ref": order["work_order_id"], "from_c": None,
                "call": {"tool_name": call["operation"], "arguments": {"zone_id": call["asset"],
                                                                         "setpoint_c": call["value"]}}}
    if fault:
        proposal["delegation_fault"] = fault
    work_orders = {order["work_order_id"]: {"zones": {order["asset"]: {"min": rng["min"], "max": rng["max"]}}}}
    return judge(proposal, work_orders, TABLES).to_dict()


def run_verifier(verifier: Path, set_dir: Path, out: Path, *, timeout_s: int | None = None,
                 known: set[str] | None = None) -> tuple[dict[str, dict[str, Any]] | None, str, float, list[str]]:
    """Run the verifier once over the set. Returns its answers by case, a status, the wall time, and
    problems with the answers: entries without a case id, answers for unknown cases, several answers for
    one case (that case then counts as malformed)."""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    saved = edge_check.ADAPTER_TIMEOUT_S
    if timeout_s is not None:
        edge_check.ADAPTER_TIMEOUT_S = timeout_s
    t0 = time.perf_counter()
    try:
        rc, tail = run_adapter(verifier, set_dir, out)
    finally:
        edge_check.ADAPTER_TIMEOUT_S = saved
    ms = round((time.perf_counter() - t0) * 1000, 1)
    if rc == 124:
        return None, "timeout", ms, []
    if rc != 0:
        last = tail.strip().splitlines()[-1] if tail.strip() else ""
        return None, f"error: exit {rc}: {last}", ms, []
    try:
        res = json.loads((out / "result.json").read_text("utf-8"))
        entries = res["verdicts"]
        if not isinstance(entries, list):
            raise TypeError("verdicts is not a list")
    except (OSError, ValueError, KeyError, TypeError) as e:
        return None, f"error: malformed result ({type(e).__name__})", ms, []
    answers: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    for v in entries:
        if not isinstance(v, dict) or not isinstance(v.get("case_id"), str):
            problems.append("an answer without a case_id")
            continue
        cid = v["case_id"]
        if known is not None and cid not in known:
            problems.append(f"answer for unknown case {cid!r}")
        elif cid in answers:
            problems.append(f"more than one answer for {cid!r}")
            answers[cid] = {"verdict": "ambiguous", "reason": "more than one answer"}
        else:
            answers[cid] = v
    return answers, "ok", ms, problems


def run(set_dir: Path, verifier: Path, out: Path, *, timeout_s: int | None = None,
        legacy_verdict_only: bool = False) -> dict[str, Any]:
    problems = af.check(set_dir)
    if any(p.startswith("manifest.json") for p in problems):
        raise SystemExit(f"{set_dir}: the manifest is unreadable or does not follow ot-authority-fixtures/v1: "
                         + "; ".join(problems))
    m = json.loads((set_dir / "manifest.json").read_text("utf-8"))
    profile = "legacy-verdict-only" if legacy_verdict_only else af.STRICT_PROFILE
    contract_problems = []
    if not legacy_verdict_only and m.get("evaluation_profile") != af.STRICT_PROFILE:
        contract_problems.append("set has no sealed identity-reason/v2 expectations; use a new strict set, "
                                 "or --legacy-verdict-only exclusively for historical reproduction")
    verdicts, status, ms, answer_problems = run_verifier(verifier, set_dir, out / "verifier", timeout_s=timeout_s,
                                                         known={c["case_id"] for c in m["cases"]})
    rows = []
    for entry in m["cases"]:
        cid = entry["case_id"]
        case = json.loads((set_dir / "cases" / f"{cid}.json").read_text("utf-8"))
        if verdicts is None:
            aps = {"class": "timeout" if status == "timeout" else "error", "verdict": None, "reason": status}
        elif cid not in verdicts:
            aps = {"class": "unanswered", "verdict": None, "reason": None}
        elif verdicts[cid].get("verdict") == "indeterminate":
            reason = verdicts[cid].get("reason")
            aps = {"class": "indeterminate" if isinstance(reason, str) and reason.strip() else "malformed",
                   "verdict": None, "reason": reason}
        elif verdicts[cid].get("verdict") not in ("pass", "refuse"):
            aps = {"class": "malformed", "verdict": None, "reason": verdicts[cid].get("reason")}
        elif not legacy_verdict_only and (not isinstance(verdicts[cid].get("reason"), str)
                                         or not verdicts[cid]["reason"].strip()):
            aps = {"class": "malformed", "verdict": None, "reason": verdicts[cid].get("reason")}
        else:
            aps = {"class": "answered", "verdict": verdicts[cid]["verdict"], "reason": verdicts[cid].get("reason")}
        # Only an unambiguous answered verifier supplies an identity. Never borrow the expected id,
        # the signed order's id, or an unverified leaf parsed here as a substitute.
        identity = verdicts[cid].get("delegation_id") if aps["class"] == "answered" else None
        aps["delegation_id"] = identity
        woc = wo.check(case["work_order"], case["call"], m["work_order_issuer_keys"],
                       delegation=case["delegation"], delegation_id=identity,
                       legacy_digest_only=legacy_verdict_only)
        exp = entry["expected"]
        orc = oracle_verdict(case, entry.get("delegation_fault"))
        admitted = (not problems and not contract_problems and not answer_problems
                    and aps["verdict"] == "pass" and woc["verdict"] == "pass")
        reason_as_expected = (aps["class"] == "answered" and isinstance(exp.get("aps_reason"), str)
                              and aps["reason"] == exp["aps_reason"]) if not legacy_verdict_only else None
        # A value-range refusal must not hide a broken identity binding (case 5). Score it
        # independently of the aggregate work-order verdict, even for expected refusals.
        identity_as_expected = (aps["class"] == "answered" and isinstance(identity, str)
                                and bool(identity.strip()) and identity == case["work_order"]["delegation_id"]
                                ) if not legacy_verdict_only else None
        # These were independently evaluated by the local checker. None may be masked by
        # another, expected work-order refusal (for example an out-of-range value).
        binding_errors = {"malformed", "unknown_issuer", "signature_missing", "signature_invalid",
                          "delegation_digest_mismatch", "delegation_not_canonicalizable"}
        binding_as_expected = (identity_as_expected and not binding_errors.intersection(woc["reasons"])
                               ) if not legacy_verdict_only else None
        rows.append({
            "case_id": cid, "construction": entry["construction"], "delegation_fault": entry.get("delegation_fault"),
            "expected": exp, "aps": aps, "work_order": woc, "admitted": admitted, "oracle": orc,
            "aps_as_expected": aps["verdict"] == exp["aps"],
            "aps_reason_as_expected": reason_as_expected,
            "identity_as_expected": identity_as_expected,
            "binding_as_expected": binding_as_expected,
            "work_order_as_expected": woc["verdict"] == exp["work_order"],
            "oracle_agrees": (orc["verdict"] == "permitted") == exp["admitted"],
        })
    counts = {"cases": len(rows),
              "aps_as_expected": sum(r["aps_as_expected"] for r in rows),
              "aps_reason_as_expected": sum(r["aps_reason_as_expected"] is True for r in rows)
                                        if not legacy_verdict_only else None,
              "identity_as_expected": sum(r["identity_as_expected"] is True for r in rows)
                                      if not legacy_verdict_only else None,
              "binding_as_expected": sum(r["binding_as_expected"] is True for r in rows)
                                     if not legacy_verdict_only else None,
              "work_order_as_expected": sum(r["work_order_as_expected"] for r in rows),
              "oracle_agrees": sum(r["oracle_agrees"] for r in rows),
              "admitted": sum(r["admitted"] for r in rows),
              "aps_classes": {k: sum(1 for r in rows if r["aps"]["class"] == k)
                              for k in ("answered", "indeterminate", "error", "timeout", "malformed", "unanswered")}}
    ok = not problems and not contract_problems and not answer_problems and all(
        r["aps_as_expected"] and r["work_order_as_expected"] and r["oracle_agrees"]
        and (legacy_verdict_only or (r["aps_reason_as_expected"] and r["binding_as_expected"])) for r in rows)
    verifier_meta = json.loads((verifier / "edge.json").read_text("utf-8"))
    result = {"schema": SCHEMA, "fixture_set": m["fixture_set"], "package_digest": m["package_digest"],
              "manifest_sha256": af._sha(set_dir / "manifest.json"),
              "profile": profile, "contract_problems": contract_problems,
              "identity_binding_scored": not legacy_verdict_only, "delegation_reasons_scored": not legacy_verdict_only,
              "set_problems": problems, "verifier": {"edge_id": verifier_meta.get("edge_id"),
                                                     "project": verifier_meta.get("project"),
                                                     "status": status, "runtime_ms": ms,
                                                     "answer_problems": answer_problems},
              "counts": counts, "cases": rows, "pass": ok,
              "note": "Both checks ran on the same captured input. Indeterminate, errors, timeouts, malformed and "
                      "unanswered verifier answers are separate classes: never a refusal, never a catch. "
                      + ("LEGACY REPRODUCTION ONLY: identity binding and delegation reasons are NOT scored; "
                         "PASS does not establish the complete authority contract." if legacy_verdict_only else
                         "Strict identity/reason evaluation; no runtime authorization or physical control.")}
    out.mkdir(parents=True, exist_ok=True)
    (out / "authority-result.json").write_text(json.dumps(result, indent=2) + "\n", "utf-8", newline="\n")
    (out / "authority-result.md").write_text(render_md(result), "utf-8", newline="\n")
    return result


def render_md(r: dict[str, Any]) -> str:
    c = r["counts"]
    v = r["verifier"]
    L = [f"# authority_fixture: `{r['fixture_set']}` with `{v['edge_id']}`", "",
         f"Profile: **{r['profile']}**. Manifest SHA-256: `{r['manifest_sha256']}`.", "",
         f"Result: **{'PASS' if r['pass'] else 'FAIL'}**. Verifier {v['project']}: {v['status']}, {v['runtime_ms']} ms. "
         f"Package `{r['package_digest']}`" + (f"; set problems: {', '.join(r['set_problems'])}" if r["set_problems"] else "")
         + (f"; answer problems: {', '.join(v['answer_problems'])}" if v.get("answer_problems") else "") + ".", "",
         "Contract problems: " + ("; ".join(r["contract_problems"]) or "none") + ".", "",
         f"Delegation check as expected {c['aps_as_expected']}/{c['cases']}; work-order check as expected "
         f"{c['work_order_as_expected']}/{c['cases']}; oracle agrees {c['oracle_agrees']}/{c['cases']}; admitted "
         f"{c['admitted']}. Verifier answers by class: "
         + ", ".join(f"{k} {n}" for k, n in c["aps_classes"].items()) + ".", "",
         f"Delegation reasons as expected: {c['aps_reason_as_expected'] if r['delegation_reasons_scored'] else 'NOT SCORED (legacy)'}. "
         f"Identity bindings as expected: {c['identity_as_expected'] if r['identity_binding_scored'] else 'NOT SCORED (legacy)'}.", "",
         f"Complete signed bindings as expected: {c['binding_as_expected'] if r['identity_binding_scored'] else 'NOT SCORED (legacy)'}.", "",
         "| Case | Built as | Delegation check (expected / got, reason) | Work-order check (expected / got, reasons) | Admitted | Oracle |",
         "|---|---|---|---|---|---|"]
    for row in r["cases"]:
        a, w, e = row["aps"], row["work_order"], row["expected"]
        got_a = a["verdict"] if a["class"] == "answered" else f"*{a['class']}*"
        L.append(f"| `{row['case_id']}` | {row['construction']} | {e['aps']} / {got_a}"
                 f"{'' if row['aps_as_expected'] else ' ✗'} ({a['reason']}; expected reason: {e.get('aps_reason', 'not registered')}; "
                 f"reason match: {row['aps_reason_as_expected']}; identity: {a['delegation_id']}; "
                 f"identity match: {row['identity_as_expected']}) | {e['work_order']} / {w['verdict']}"
                 f"{'' if row['work_order_as_expected'] else ' ✗'} ({', '.join(w['reasons']) or 'none'}) | "
                 f"{'yes' if row['admitted'] else 'no'} | {row['oracle']['verdict']} "
                 f"{'(' + row['oracle']['rule'] + ')' if row['oracle']['rule'] else ''}{'' if row['oracle_agrees'] else ' ✗'} |")
    L += ["", r["note"], ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="runner.authority_harness")
    p.add_argument("--fixtures", required=True)
    p.add_argument("--verifier", required=True, help="verifier directory with edge.json and its entrypoint")
    p.add_argument("--out", required=True)
    p.add_argument("--timeout", type=int, default=120, help="seconds the verifier may take over the whole set")
    p.add_argument("--legacy-verdict-only", action="store_true",
                   help="historical reproduction ONLY: do not score delegation identity or reasons; labelled in results")
    p.add_argument("--trust-edge", action="append", default=[], metavar="EDGE_DIR_NAME",
                   help="run this edge on the host instead of the container sandbox (your own code only)")
    a = p.parse_args(argv)
    from runner import edge_sandbox
    edge_sandbox.EXTRA_TRUSTED.update(a.trust_edge)
    r = run(Path(a.fixtures), Path(a.verifier), Path(a.out), timeout_s=a.timeout,
            legacy_verdict_only=a.legacy_verdict_only)
    print(render_md(r))
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
