# Offline authority contract: issue #27 gap validation

Scope: synthetic `authority_fixture` evaluation only. This patch changes no runtime adapter, REMORA authorization, plant, physical interface, APS verifier source/image, or inline A/B/C integration.

Base inspected: `5822e506e15240cd997f89e80e673cda2cb18182`.
Code revision tested: `1d652081e97b8e9bd390a6ebe4ca823572363b7f`. The subsequent evidence-only commit adds this record and the raw run output; it does not change runtime or scorer code.

## Changes and observed regressions

| Gap | Before | After / regression |
|---|---|---|
| Signed delegation identity | Correct digest could hide a wrong signed `delegation_id`. | `test_signed_identity_must_match_verifier_identity_even_when_digest_matches` and `test_signed_wrong_leaf_cannot_pass_the_harness` require exact equality with the verifier-extracted ID. Missing ID refuses; no parsing/fallback on the testbed side. |
| Refusal reason | Any reason, including `WRONG_REASON`, could score a correct verdict. | `test_wrong_refusal_reason_fails_even_with_correct_verdicts` scores the sealed reason; missing/non-string/blank reasons cannot pass strict scoring. |
| Indeterminate | Collapsed into malformed. | `test_indeterminate_is_distinct_from_malformed_and_never_admitted`: own class, null scored verdict, zero admissions. |
| Refusal masking found in independent review | The expected range refusal in case 5 could hide an absent/wrong ID, even after the local checker was fixed. | `test_value_refusal_cannot_hide_missing_or_wrong_delegation_identity` was observed failing for both null and wrong IDs, then passing. Identity is scored on every case independently of the aggregate work-order verdict. |
| Complete binding masking | A freshly sealed case 5 with a signed but wrong chain digest still produced the expected aggregate refusal. | `test_value_refusal_cannot_hide_a_broken_complete_chain_binding` was observed failing, then passing. Invalid signature, issuer and digest errors cannot hide behind an expected range refusal. |
| Null delegation | An explicitly supplied JSON null could use the function's no-delegation default and skip binding. | `test_explicit_null_delegation_cannot_skip_identity_and_digest_binding` was observed failing, then passing. Omitted and explicit null are now distinct. |

## New sealed set

`t3` uses the **same case bytes** as `t2`, but a new manifest, profile and package digest:

- Profile: `identity-reason/v2`.
- Package: `sha256:5ecb698548410a4006b1fb5fb130e7ab6311c3db40554c7be04aa9249b775097`.
- Manifest: `b29634f2da909da3f77c222caa2f4f1492097ceaf4e4189e1597b33b9433d3f9` (raw SHA-256).
- Strict package rule: SHA-256 of RFC 8785 JCS of the entire manifest without `package_digest`. Thus expectations, issuer keys and profile are bound alongside case hashes. Older package rules are preserved.
- Cases 1–4 pass local work-order admission; case 5 refuses on value. Delegation refuses cases 2–4. Both checks and reasons are recorded for all five.

The `t3` verifier is the testbed's own `ot-test-delegation/v1` stand-in. A pass is not an APS result and never authorizes an action.

## Reproduction

Use Python 3.11+ and the repository's hash-locked development dependencies:

```bash
python -m pip install --require-hashes --no-deps -r requirements-dev.lock
python -m pytest -q tests/unit/test_authority_harness.py tests/unit/test_work_order.py
python -m runner.authority_fixtures check federation/authority/fixtures/t3
python -m runner.authority_harness --fixtures federation/authority/fixtures/t3 \
  --verifier federation/authority/template-verifier --out /tmp/authority-t3
python -m pytest -q
./deploy/scripts/preflight.sh
git -c core.whitespace=cr-at-eol diff --check
```

The whitespace option recognizes the existing CRLF in edited schema files; those files retain their prior line-ending convention. All new sealed files use LF.

Tests run in a fresh virtual environment with `requirements-dev.lock`, Python 3.12, cryptography 50.0.2, jsonschema 4.26.0, pytest 9.1.1. Host HTTP/SOCKS proxy variables were removed only for the test process so local HTTP integration tests use their loopback test servers. An initial run outside this environment failed due to missing SOCKS support and a subprocess interpreter without pytest; the locked environment resolved these environmental failures without changes to unrelated project code.

## Compatibility and external APS work

- `t1`, `t2`, `aps-1`, the APS submission/verifier metadata and all earlier reports were compared byte for byte against the base and remain unchanged. Reassembly of `aps-1` is still tested byte for byte.
- Strict evaluation is the default. Legacy fixtures lack registered reason expectations, so they fail strict evaluation with zero combined admissions.
- `--legacy-verdict-only` deliberately reproduces the previous verdict-only contract. The result explicitly says identity/reasons are not scored, with `profile: legacy-verdict-only`; its PASS is not a strict-contract claim.
- APS must supply a **new** pinned verifier returning `delegation_id` from its chain leaf, stable reason codes and a new strict submission registering those reasons. Current `aps-1` remains historical; the testbed does not synthesize verified APS output or vendor APS source.
- For APS the digest covers the entire signed root-to-leaf chain; UTC fixture decision time is converted to milliseconds by APS. Fixture time does not replace REMORA's runtime lease clock.
- The contract remains proposed. Runtime ToolSpec binding, inline integration and revocation require separate external work/review. Issue #27 should remain open.

No Docker/APS-container rerun or pinned REMORA SDK job was performed here. The local full suite is the suite available without that separately checked-out SDK; CI's required pinned SDK job remains the external check. No A/B/C or physical-control result is claimed.

## Final local results

- Focused authority/work-order suite: **50 passed**.
- Full available suite with hash-locked dependencies: **840 passed in 69.42 s**, no failures or reported skips.
- Strict t3: delegation verdict 5/5; delegation reason 5/5; identity 5/5; complete signed binding 5/5; work order 5/5; oracle 5/5; combined offline admissions 1.
- Error classes: answered 5; indeterminate/error/timeout/malformed/unanswered 0.
- t2 and t3 rebuild byte for byte; t1/t2/aps-1 seals validate.
- Explicit legacy t2 reproduction passes with limitations labelled; default strict t2 fails with zero admissions.
- Preflight and whitespace validation pass.
- One independent whole-branch review identified the case-5 masking path described above; regressions were observed failing and then passing after independent binding scoring was added. No other confirmed findings were reported.

Raw result: [authority-t3.json](authority-t3.json) · [readable result](authority-t3.md).

Publication provenance: the connected GitHub API published the code tree under the repository account; implementation and validation were prepared by Codex. Remote code tree `cbc9534e07e0bd13f5ddb25db455d7e7dabd08cc` exactly equals locally tested commit `c131503164624bf6505864dee5caf6bb466c6abd`. Only Git commit publication metadata differs.
