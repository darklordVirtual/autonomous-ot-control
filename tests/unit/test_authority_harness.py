"""authority_fixture: the five cases of issue #27, the stand-in verifier and the offline harness.

- the committed set is sealed and is exactly what a rebuild gives (Ed25519 is deterministic);
- every case is built as it says: the stand-in verifier's refusal reason is the case's delegation
  fault, and each work order binds that case's delegation by its JCS SHA-256;
- the harness runs both checks on the same input and passes with the stand-in verifier: delegation
  check, work-order check and oracle all as the manifest fixed them, one case admitted;
- a verifier that passes everything is caught on cases 2 to 4; a crashing verifier, a malformed
  answer and a missing answer are their own classes, never refusals; a changed fixture fails the set.
"""
from __future__ import annotations

import json
import hashlib
import shutil
from pathlib import Path

import pytest

from runner import authority_fixtures as af
from runner import authority_harness as ah
from runner import work_order as wo

ROOT = Path(__file__).resolve().parents[2]
SET = ROOT / "federation" / "authority" / "fixtures" / "t3"
T2 = ROOT / "federation" / "authority" / "fixtures" / "t2"
T1 = ROOT / "federation" / "authority" / "fixtures" / "t1"  # superseded, kept unchanged
VERIFIER = ROOT / "federation" / "authority" / "template-verifier"


def _verifier(tmp_path: Path, name: str, body: str) -> Path:
    d = tmp_path / name
    shutil.copytree(VERIFIER, d, ignore=shutil.ignore_patterns("__pycache__"))
    (d / "adapter.py").write_text(
        "import json, sys\nfrom pathlib import Path\na = sys.argv\n"
        "fx, out = Path(a[a.index('--fixtures') + 1]), Path(a[a.index('--out') + 1])\n"
        "cases = [json.loads(p.read_text('utf-8')) for p in sorted((fx / 'cases').glob('*.json'))]\n" + body, "utf-8")
    return d


def test_committed_set_is_sealed_and_rebuilds_byte_for_byte(tmp_path):
    assert af.check(SET) == []
    m = af.build(tmp_path / "t3")
    for f in m["files"] + [{"path": "manifest.json"}]:
        assert (tmp_path / "t3" / f["path"]).read_bytes() == (SET / f["path"]).read_bytes(), f["path"]


def test_the_builder_writes_lf_on_every_platform(tmp_path):
    """The cause of t1's CRLF bytes: a text-mode write on Windows. No sealed byte may depend on the OS."""
    af.build(tmp_path / "s")
    for p in sorted((tmp_path / "s").rglob("*.json")):
        assert b"\r" not in p.read_bytes(), p.name
    for p in sorted(SET.rglob("*.json")):
        assert b"\r" not in p.read_bytes(), p.name


def test_t1_is_kept_unchanged_and_t2_names_what_it_replaces():
    """t1 stays as it was sealed (CRLF, its own digests still hold); t2 is the same cases with LF."""
    assert af.check(T1) == []
    m1 = json.loads((T1 / "manifest.json").read_text("utf-8"))
    m2 = json.loads((T2 / "manifest.json").read_text("utf-8"))
    assert m2["supersedes"]["fixture_set"] == "t1" and m2["supersedes"]["package_digest"] == m1["package_digest"]
    assert m1["package_digest"] != m2["package_digest"]
    assert [c["expected"] for c in m1["cases"]] == [c["expected"] for c in m2["cases"]]
    for c in m1["cases"]:
        name = f"{c['case_id']}.json"
        a, b = (T1 / "cases" / name).read_bytes(), (T2 / "cases" / name).read_bytes()
        assert a != b and a.replace(b"\r\n", b"\n") == b, name  # only the line endings differ
    gitattributes = (ROOT / ".gitattributes").read_text("utf-8")
    assert "federation/authority/fixtures/** -text" in gitattributes and "federation/fixtures/** -text" in gitattributes


def test_cases_are_built_as_they_say():
    m = json.loads((SET / "manifest.json").read_text("utf-8"))
    assert [c["case_id"] for c in m["cases"]] == [c[0] for c in af.CASES]
    roots, keys = m["delegation_root_keys"], m["delegation_signer_keys"]
    import importlib.util
    spec = importlib.util.spec_from_file_location("authority_template_adapter", VERIFIER / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for entry in m["cases"]:
        case = json.loads((SET / "cases" / f"{entry['case_id']}.json").read_text("utf-8"))
        verdict, reason = mod.decide(case, roots, keys)
        assert verdict == entry["expected"]["aps"]
        if entry["delegation_fault"]:
            assert reason == entry["delegation_fault"], (entry["case_id"], reason)
        assert case["work_order"]["delegation_sha256"] == wo.delegation_sha256(case["delegation"])
        assert wo.verify_signature(case["work_order"], m["work_order_issuer_keys"]) is None


def test_harness_passes_with_the_stand_in_and_records_both_verdicts(tmp_path):
    r = ah.run(SET, VERIFIER, tmp_path / "out")
    assert r["pass"] and r["set_problems"] == []
    c = r["counts"]
    assert c["aps_as_expected"] == c["work_order_as_expected"] == c["oracle_agrees"] == 5 and c["admitted"] == 1
    by = {x["case_id"]: x for x in r["cases"]}
    assert by["af-5-value-out-of-range"]["aps"]["verdict"] == "pass"
    assert by["af-5-value-out-of-range"]["work_order"]["reasons"] == ["value_above_range"]
    assert by["af-5-value-out-of-range"]["oracle"]["rule"] == "outside_work_order"
    assert all(by[k]["oracle"]["rule"] == "delegation_invalid" for k in ("af-2-widened", "af-3-expired", "af-4-out-of-scope"))
    assert "PASS" in (tmp_path / "out" / "authority-result.md").read_text("utf-8")


def test_a_verifier_that_passes_everything_is_caught(tmp_path):
    v = _verifier(tmp_path, "lenient", "out.write_text(json.dumps({'verdicts': [{'case_id': c['case_id'], 'verdict': 'pass', 'reason': 'scope_covered', 'delegation_id': c['delegation']['delegation_id']} for c in cases]}))\n")
    r = ah.run(SET, v, tmp_path / "out")
    assert not r["pass"]
    assert sorted(x["case_id"] for x in r["cases"] if not x["aps_as_expected"]) == ["af-2-widened", "af-3-expired", "af-4-out-of-scope"]
    # cases 1 to 4 get through: 2 to 4 pass the work-order check, so only the delegation check stops them
    assert r["counts"]["admitted"] == 4 and not next(x for x in r["cases"] if x["case_id"].startswith("af-5"))["admitted"]


def test_errors_malformed_and_missing_answers_are_not_refusals(tmp_path):
    crash = _verifier(tmp_path, "crash", "raise SystemExit(3)\n")
    r = ah.run(SET, crash, tmp_path / "o1")
    assert not r["pass"] and r["counts"]["aps_classes"]["error"] == 5
    assert all(x["aps"]["verdict"] is None for x in r["cases"])
    odd = _verifier(tmp_path, "odd", "out.write_text(json.dumps({'verdicts': [{'case_id': c['case_id'], 'verdict': 'maybe'} for c in cases[1:]]}))\n")
    r = ah.run(SET, odd, tmp_path / "o2")
    assert r["counts"]["aps_classes"] == {"answered": 0, "indeterminate": 0, "error": 0, "timeout": 0, "malformed": 4, "unanswered": 1}
    assert r["counts"]["admitted"] == 0 and not r["pass"]


def test_a_changed_fixture_fails_the_set(tmp_path):
    s = tmp_path / "t2"
    shutil.copytree(SET, s)
    p = s / "cases" / "af-1-valid.json"
    case = json.loads(p.read_text("utf-8"))
    case["call"]["value"] = 20.0
    p.write_text(json.dumps(case, indent=2, sort_keys=True) + "\n", "utf-8")
    r = ah.run(s, VERIFIER, tmp_path / "out")
    assert r["set_problems"] == ["changed cases/af-1-valid.json"] and not r["pass"]


# -- a delegation owner's submission (APS), and verifier answers the harness does not accept ---------

def _submission(tmp_path: Path) -> Path:
    """A submission as APS would send it, here with the stand-in's delegations from t2."""
    m = json.loads((SET / "manifest.json").read_text("utf-8"))
    d = tmp_path / "submission"
    (d / "delegations").mkdir(parents=True)
    cases = []
    for entry in m["cases"]:
        case = json.loads((SET / "cases" / f"{entry['case_id']}.json").read_text("utf-8"))
        (d / "delegations" / f"{entry['case_id']}.json").write_text(json.dumps(case["delegation"]), "utf-8")
        cases.append({"case_id": entry["case_id"], "construction": entry["construction"],
                      "delegation_fault": entry["delegation_fault"],
                      "delegation_file": f"delegations/{entry['case_id']}.json",
                      "delegation_id": case["delegation"]["delegation_id"],
                      "call": {"asset": case["call"]["asset"], "value": case["call"]["value"],
                               "decision_time": case["call"]["decision_time"]},
                      "expected_work_order": entry["expected"]["work_order"],
                      "expected_aps_reason": entry["expected"]["aps_reason"]})
    sub = {"schema": "ot-authority-submission/v1", "set_id": "sub-1", "evaluation_profile": "identity-reason/v2",
           "source": {"project": "stand-in", "repository": "local", "revision": "0000000"},
           "delegation_format": "ot-test-delegation/v1 (stand-in)",
           "delegation_root_keys": m["delegation_root_keys"], "delegation_signer_keys": m["delegation_signer_keys"],
           "cases": cases}
    (d / "submission.json").write_text(json.dumps(sub), "utf-8")
    return d / "submission.json"


def test_a_submission_assembles_into_a_sealed_set_the_harness_passes(tmp_path):
    sub = _submission(tmp_path)
    m = af.assemble(sub, tmp_path / "set")
    assert af.check(tmp_path / "set") == [] and m["source"]["project"] == "stand-in"
    assert [c["expected"] for c in m["cases"]] == [c["expected"] for c in json.loads((SET / "manifest.json").read_text("utf-8"))["cases"]]
    case = json.loads((tmp_path / "set" / "cases" / "af-2-widened.json").read_text("utf-8"))
    original = json.loads((sub.parent / "delegations" / "af-2-widened.json").read_text("utf-8"))
    assert case["delegation"] == original  # never changed or re-encoded
    assert case["work_order"]["delegation_sha256"] == wo.delegation_sha256(original)
    r = ah.run(tmp_path / "set", VERIFIER, tmp_path / "out")
    assert r["pass"] and r["counts"]["admitted"] == 1


def test_a_submission_is_refused_when_it_is_not_what_it_says(tmp_path):
    import pytest
    sub = _submission(tmp_path)
    s = json.loads(sub.read_text("utf-8"))
    s["cases"][4]["expected_work_order"] = "pass"  # the value 22.5 is outside the default range
    sub.write_text(json.dumps(s), "utf-8")
    with pytest.raises(SystemExit, match="gives refuse"):
        af.assemble(sub, tmp_path / "set")
    s["cases"][4]["expected_work_order"] = "refuse"
    s["cases"][0]["delegation_file"] = "../../outside.json"
    sub.write_text(json.dumps(s), "utf-8")
    with pytest.raises(SystemExit):
        af.assemble(sub, tmp_path / "set2")
    del s["source"]
    sub.write_text(json.dumps(s), "utf-8")
    with pytest.raises(SystemExit, match="source"):
        af.assemble(sub, tmp_path / "set3")


def test_contradictory_expectations_and_schema_violations_fail_the_set(tmp_path):
    s = tmp_path / "t2"
    shutil.copytree(SET, s)
    m = json.loads((s / "manifest.json").read_text("utf-8"))
    m["cases"][1]["delegation_fault"] = None  # widened case no longer labelled, still expected to be refused
    (s / "manifest.json").write_text(json.dumps(m), "utf-8")
    assert any("delegation fault" in p for p in af.check(s))
    m["cases"][1]["delegation_fault"] = "widened"
    m["cases"][1]["expected"]["aps"] = "maybe"
    (s / "manifest.json").write_text(json.dumps(m), "utf-8")
    assert any(p.startswith("manifest.json:") for p in af.check(s))


def test_unknown_and_duplicate_answers_fail_the_run(tmp_path):
    v = _verifier(tmp_path, "chatty",
                  "ans = [{'case_id': c['case_id'], 'verdict': 'pass' if c['case_id'].startswith(('af-1', 'af-5')) else 'refuse'} for c in cases]\n"
                  "ans += [{'case_id': 'af-9-invented', 'verdict': 'refuse'}, {'case_id': 'af-1-valid', 'verdict': 'refuse'}, 'junk']\n"
                  "out.write_text(json.dumps({'verdicts': ans}))\n")
    r = ah.run(SET, v, tmp_path / "out")
    probs = r["verifier"]["answer_problems"]
    assert "answer for unknown case 'af-9-invented'" in probs and "more than one answer for 'af-1-valid'" in probs
    assert "an answer without a case_id" in probs and not r["pass"]
    assert next(x for x in r["cases"] if x["case_id"] == "af-1-valid")["aps"]["class"] == "malformed"


def test_the_sealed_aps_1_set_is_the_assembly_of_the_submission(tmp_path):
    """APS's submission (PR #35), sealed by this testbed: the committed set checks clean and re-assembling the
    submission gives the same bytes and the same package digest."""
    sealed = ROOT / "federation" / "authority" / "fixtures" / "aps-1"
    assert af.check(sealed) == []
    again = tmp_path / "aps-1"
    af.assemble(ROOT / "federation" / "authority" / "submissions" / "aps-1" / "submission.json", again)
    for f in sorted(p.relative_to(sealed) for p in sealed.rglob("*") if p.is_file()):
        assert (again / f).read_bytes() == (sealed / f).read_bytes(), f


def _identity_answers(*, identity="c['delegation']['delegation_id']", reason="e['delegation_fault'] or 'scope_covered'",
                      verdict="e['expected']['aps']"):
    """An independently controlled subprocess response; never reads an expected reason field."""
    return ("m = json.loads((fx / 'manifest.json').read_text())\n"
            "by_id = {e['case_id']: e for e in m['cases']}\n"
            "answers = []\n"
            "for c in cases:\n"
            "    e = by_id[c['case_id']]\n"
            f"    answers.append({{'case_id': c['case_id'], 'verdict': {verdict}, 'reason': {reason}, 'delegation_id': {identity}}})\n"
            "out.write_text(json.dumps({'verdicts': answers}))\n")


def test_signed_wrong_leaf_cannot_pass_the_harness(tmp_path):
    v = _verifier(tmp_path, "wrong-leaf", _identity_answers(identity="'WRONG-LEAF'"))
    r = ah.run(SET, v, tmp_path / "out")
    assert not r["pass"] and r["counts"]["admitted"] == 0
    assert all("delegation_id_mismatch" in c["work_order"]["reasons"] for c in r["cases"])


def test_indeterminate_is_distinct_from_malformed_and_never_admitted(tmp_path):
    v = _verifier(tmp_path, "indeterminate", _identity_answers(verdict="'indeterminate'", identity="None"))
    r = ah.run(SET, v, tmp_path / "out")
    assert not r["pass"] and r["counts"]["admitted"] == 0
    assert r["counts"]["aps_classes"]["indeterminate"] == 5
    assert r["counts"]["aps_classes"]["malformed"] == 0
    assert all(c["aps"]["verdict"] is None for c in r["cases"])


def test_strict_scoring_refuses_legacy_expectations_without_silent_downgrade(tmp_path):
    v = _verifier(tmp_path, "correct-verdicts", _identity_answers())
    r = ah.run(T2, v, tmp_path / "out")
    assert not r["pass"]
    assert r["profile"] == "identity-reason/v2"
    assert r["contract_problems"]


def test_wrong_refusal_reason_fails_even_with_correct_verdicts(tmp_path):
    # t3 registers reasons independently of the verifier; no sealed legacy set is edited.
    strict = tmp_path / "t3"
    af.build(strict, set_id="t3")
    v = _verifier(tmp_path, "wrong-reason", _identity_answers(reason="'WRONG_REASON'"))
    r = ah.run(strict, v, tmp_path / "out")
    assert not r["pass"]
    assert r["counts"]["aps_as_expected"] == 5
    assert r["counts"]["aps_reason_as_expected"] == 0


def test_missing_identity_fails_strict_but_explicit_legacy_is_labelled(tmp_path):
    v = _verifier(tmp_path, "no-identity", _identity_answers(identity="None"))
    r = ah.run(SET, v, tmp_path / "strict")
    assert not r["pass"] and r["counts"]["admitted"] == 0
    assert all(c["work_order"]["reasons"] == ["delegation_id_unavailable"] for c in r["cases"][:-1])
    r = ah.run(T2, v, tmp_path / "legacy", legacy_verdict_only=True)
    assert r["pass"] and r["counts"]["admitted"] == 1
    assert r["profile"] == "legacy-verdict-only"
    assert not r["identity_binding_scored"] and not r["delegation_reasons_scored"]


@pytest.mark.parametrize("reason", ["None", "''", "'   '", "42", "[]"])
def test_missing_or_non_string_reason_cannot_score_a_strict_verdict(tmp_path, reason):
    v = _verifier(tmp_path, "bad-reason", _identity_answers(reason=reason))
    r = ah.run(SET, v, tmp_path / "out")
    assert not r["pass"] and r["counts"]["admitted"] == 0
    assert r["counts"]["aps_classes"]["malformed"] == 5


def test_strict_expectations_and_trust_metadata_are_sealed(tmp_path):
    s = tmp_path / "set"
    shutil.copytree(SET, s)
    p = s / "manifest.json"
    m = json.loads(p.read_text())
    m["cases"][1]["expected"]["aps_reason"] = "signature_invalid"
    p.write_text(json.dumps(m))
    assert "package digest does not match the sealed metadata and files" in af.check(s)
    r = ah.run(s, VERIFIER, tmp_path / "out")
    assert not r["pass"] and r["counts"]["admitted"] == 0
    m = json.loads((SET / "manifest.json").read_text())
    m["delegation_root_keys"]["delegation-root-test-key"] = "A" * 43
    p.write_text(json.dumps(m))
    assert "package digest does not match the sealed metadata and files" in af.check(s)


def test_unknown_answer_blocks_admission_even_with_all_correct_known_answers(tmp_path):
    body = _identity_answers().replace("out.write_text", "answers.append({'case_id': 'unknown', 'verdict': 'pass'})\nout.write_text")
    v = _verifier(tmp_path, "unknown-answer", body)
    r = ah.run(SET, v, tmp_path / "out")
    assert not r["pass"] and r["counts"]["admitted"] == 0


def test_missing_expected_reason_is_a_contract_error_not_a_reason_wildcard(tmp_path):
    s = tmp_path / "set"
    shutil.copytree(SET, s)
    p = s / "manifest.json"
    m = json.loads(p.read_text())
    del m["cases"][1]["expected"]["aps_reason"]
    p.write_text(json.dumps(m))
    with pytest.raises(SystemExit, match="aps_reason"):
        ah.run(s, VERIFIER, tmp_path / "out")


def test_timeout_is_not_a_policy_refusal(tmp_path):
    v = _verifier(tmp_path, "slow", "import time\ntime.sleep(2)\n")
    r = ah.run(SET, v, tmp_path / "out", timeout_s=1)
    assert not r["pass"] and r["counts"]["admitted"] == 0
    assert r["counts"]["aps_classes"]["timeout"] == 5
    assert all(c["aps"]["verdict"] is None for c in r["cases"])


def test_t3_keeps_case_bytes_but_seals_new_expectations_and_names_t2():
    m = json.loads((SET / "manifest.json").read_text())
    assert m["supersedes"]["fixture_set"] == "t2"
    for p in (SET / "cases").glob("*.json"):
        assert p.read_bytes() == (T2 / "cases" / p.name).read_bytes()


def test_strict_submission_preserves_registered_reasons_and_binding(tmp_path):
    submission = _submission(tmp_path)
    sealed = tmp_path / "strict-submission"
    m = af.assemble(submission, sealed)
    assert m["evaluation_profile"] == "identity-reason/v2"
    assert [e["expected"]["aps_reason"] for e in m["cases"]] == [
        "scope_covered", "widened", "expired", "out_of_scope", "scope_covered"]
    assert ah.run(sealed, VERIFIER, tmp_path / "out")["pass"]


@pytest.mark.parametrize("identity", ["None", "'WRONG-LEAF'"])
def test_value_refusal_cannot_hide_missing_or_wrong_delegation_identity(tmp_path, identity):
    v = _verifier(tmp_path, "bad-fifth-id", _identity_answers(
        identity=f"{identity} if c['case_id'] == 'af-5-value-out-of-range' else c['delegation']['delegation_id']"))
    r = ah.run(SET, v, tmp_path / "out")
    assert r["counts"]["aps_as_expected"] == r["counts"]["work_order_as_expected"] == 5
    assert r["counts"]["identity_as_expected"] == 4
    assert not r["pass"]


def test_value_refusal_cannot_hide_a_broken_complete_chain_binding(tmp_path):
    strict = tmp_path / "strict"
    m = af.build(strict)
    p = strict / "cases/af-5-value-out-of-range.json"
    case = json.loads(p.read_text())
    case["work_order"] = wo.sign({**case["work_order"], "delegation_sha256": "0" * 64},
                                 wo.issuer_test_key(), wo.TEST_ISSUER)
    p.write_text(json.dumps(case, indent=2, sort_keys=True) + "\n")
    for f in m["files"]:
        if f["path"] == "cases/af-5-value-out-of-range.json":
            f["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    m["package_digest"] = af.manifest_package_digest(m)
    (strict / "manifest.json").write_text(json.dumps(m))
    assert af.check(strict) == []  # A freshly sealed construction, not a broken byte seal.
    r = ah.run(strict, VERIFIER, tmp_path / "out")
    assert r["counts"]["work_order_as_expected"] == 5
    assert not r["pass"]
