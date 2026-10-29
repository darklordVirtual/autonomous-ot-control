# Reproduced strict stand-in run

Testbed code revision: `1d652081e97b8e9bd390a6ebe4ca823572363b7f`. Synthetic offline testbed verifier; not APS or runtime integration.

# authority_fixture: `t3` with `authority-template-verifier`

Profile: **identity-reason/v2**. Manifest SHA-256: `b29634f2da909da3f77c222caa2f4f1492097ceaf4e4189e1597b33b9433d3f9`.

Result: **PASS**. Verifier autonomous-ot-control (stand-in for APS): ok, 62.6 ms. Package `sha256:5ecb698548410a4006b1fb5fb130e7ab6311c3db40554c7be04aa9249b775097`.

Contract problems: none.

Delegation check as expected 5/5; work-order check as expected 5/5; oracle agrees 5/5; admitted 1. Verifier answers by class: answered 5, indeterminate 0, error 0, timeout 0, malformed 0, unanswered 0.

Delegation reasons as expected: 5. Identity bindings as expected: 5.

Complete signed bindings as expected: 5.

| Case | Built as | Delegation check (expected / got, reason) | Work-order check (expected / got, reasons) | Admitted | Oracle |
|---|---|---|---|---|---|
| `af-1-valid` | valid chain, in scope, value in range | pass / pass (scope_covered; expected reason: scope_covered; reason match: True; identity: DLG-af-1-valid; identity match: True) | pass / pass (none) | yes | permitted  |
| `af-2-widened` | the operator holds ZONE-01 and ZONE-02 but grants the agent ZONE-01 and ZONE-03 | refuse / refuse (widened; expected reason: widened; reason match: True; identity: DLG-af-2-widened; identity match: True) | pass / pass (none) | no | forbidden (delegation_invalid) |
| `af-3-expired` | the agent's link expired at 06:00, before the decision time 07:00 | refuse / refuse (expired; expected reason: expired; reason match: True; identity: DLG-af-3-expired; identity match: True) | pass / pass (none) | no | forbidden (delegation_invalid) |
| `af-4-out-of-scope` | a valid, narrowed chain grants the agent ZONE-02 only; the call is on ZONE-01 | refuse / refuse (out_of_scope; expected reason: out_of_scope; reason match: True; identity: DLG-af-4-out-of-scope; identity match: True) | pass / pass (none) | no | forbidden (delegation_invalid) |
| `af-5-value-out-of-range` | valid chain and scope; the value 22.5 is outside the work order's 19.0..21.0 | pass / pass (scope_covered; expected reason: scope_covered; reason match: True; identity: DLG-af-5-value-out-of-range; identity match: True) | refuse / refuse (value_above_range) | no | forbidden (outside_work_order) |

Both checks ran on the same captured input. Indeterminate, errors, timeouts, malformed and unanswered verifier answers are separate classes: never a refusal, never a catch. Strict identity/reason evaluation; no runtime authorization or physical control.
