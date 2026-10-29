# Authority fixture identity and reason scoring implementation plan

> **For agentic workers:** Use superpowers:executing-plans; implement and verify the tasks below before opening the requested PR.

**Goal:** Address the three offline authority-fixture gaps reported in issue #27 without importing APS implementation code or changing runtime control.

**Architecture:** Keep delegation opaque to the local work-order checker. The verifier returns the delegation identity; the local checker compares it with the signed order, independently of scope validity. A new sealed stand-in set `t3` registers machine-readable delegation reasons. Strict evaluation is the default; an explicit legacy-verdict-only mode reproduces earlier sets without claiming identity/reason coverage.

**Tech stack:** Existing Python, Ed25519, RFC 8785 JCS, JSON Schema and pytest.

**Spec:** Issue #27, especially APS comment 6475642387, and `docs/federation/authority-fixture-contract.md`. User authorized implementation and creation of a PR after the preceding review.

## Global constraints

- Synthetic offline fixtures only; no inline APS integration or physical control.
- Do not modify any bytes of sealed `t1`, `t2`, `aps-1` or historic results.
- APS verifier, signing keys and implementation stay in the APS repository.
- Do not imply external acceptance of new result fields, reason codes or the final contract.
- Missing identity or expected reason must prevent a strict evaluation PASS.
- `indeterminate`, malformed, timeout, error and unanswered are separate classes, never policy catches or admissions.

## Review focus

- Correctly signed order with wrong identity but correct digest must fail identity binding.
- Verifier reason missing or wrong must fail strict scoring, even with correct pass/refuse values.
- Legacy mode must be visibly labelled and must not weaken strict evaluation through fixture metadata.
- Reordered, duplicate, unknown and invalid verifier answers must not gain admission.
- New sets must bind expectation metadata to a distinct package digest and reproduce across platforms.

## Task 1: Regression tests and local identity binding

- [x] Add failing tests for mismatch, unavailable verifier identity and digest mismatch preservation.
- [x] Extend `runner.work_order.check` with an opaque verifier-supplied `delegation_id`; require it when a delegation is supplied unless explicit legacy binding is requested. Keep field/range and signature checks independent.
- [x] Update fixture assembly to pass construction identity for its own sanity check; it does not claim external verification.
- [x] Run work-order tests and preserve the five-case responsibility split.

## Task 2: Strict scoring and new sealed stand-in expectations

- [x] Add failing subprocess-based harness tests for wrong/missing identity, wrong/missing refusal reason, indeterminate and explicit legacy reporting.
- [x] Extend manifest/submission/result schemas additively; strict profile registers expected delegation reason per case. Verifier outputs include delegation identity and machine-readable reason.
- [x] Build new `t3` with expectation metadata included in its package digest. Historical package rules remain unchanged.
- [x] Default harness to strict identity/reason scoring; `legacy_verdict_only=True` / `--legacy-verdict-only` is an explicit historical reproduction profile. Report profile, coverage and limitations.
- [x] Run focused tests, strict stand-in harness and legacy reproduction tests.

## Task 3: Documentation, verification and PR

- [x] Update the authority contract and add a validation record with exact commands, counters, old fixture immutability, regression evidence and external APS migration requirements.
- [x] Run the full available suite, preflight and diff checks. Record any environmental failures by test name; compare against baseline.
- [ ] Obtain one fresh whole-branch review, resolve material findings and open a PR against main. Do not merge.
