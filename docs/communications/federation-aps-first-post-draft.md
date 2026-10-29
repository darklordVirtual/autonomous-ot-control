# Draft for joint review: the first federation social post (APS x REMORA OT testbed)

> **REVIEW DRAFT — do not publish or merge as an endorsement.** Proposed LinkedIn text, attributable evidence and review questions. Opened following [federation #177](https://github.com/aeoess/agent-governance-vocabulary/issues/177#issuecomment-6502334967). Comments and corrections are welcome before public posting. The GitHub @handles below are **not** verified LinkedIn account tags; confirm profiles with each person before converting them into LinkedIn mentions.

## Proposed public post (English)

**Can an AI agent have valid delegated authority and still be refused permission to change a building? It should.**

That's the boundary we've been testing publicly with two independent projects: **Agent Passport System (APS)** and the **REMORA-governed autonomous-ot-control testbed**.

**The people behind this specific experiment:**
- **@aeoess / APS:** proposed the delegation boundary and supplied five signed synthetic delegation chains plus a verifier distributed as a digest-pinned container (PR #35).
- **@darklordVirtual / REMORA testbed:** built the separate signed work-order checks, offline harness and independent expected-outcome oracle (PR #29), reproduced the submitted verifier in the testbed's Docker sandbox, and reviewed the integration before merge.

In the recorded **aps-1 offline run**, all five cases matched their expected delegation, work-order and oracle outcomes. **One** synthetic operation was admitted; **four** were refused. A widened delegation, expired delegation and out-of-scope operation were rejected by APS. Another request had valid delegation but exceeded the work-order setpoint range, so the **local work-order check** refused it.

The review found a mismatch between the verifier's reported edge identity and its manifest. It was corrected **before PR #35 merged**. That correction matters as much as the green result: independent projects can challenge the evidence and improve the integration.

**Credit beyond this APS experiment:** @astrogilda (Probity AI's separate effect-evidence edge), @giskard09 (an external reference-verifier reproduction), @altrudev (independent runner-failure tests) and @Tetsurohhori (reader and mutation evaluations) have tested **other** boundaries of this same OT testbed. Those contributions are not presented as tests of APS itself.

The broader **Agent Governance Vocabulary** effort led by @aeoess also credits @QueBallSharken, @douglasborthwick-crypto, @MoltyCel and many additional crosswalk contributors. The federation works because projects remain independent and retain their authorship.

**What this does *not* establish:** live building control, production safety, revocation coverage, complete runtime mediation, or proof that adding APS provides incremental protection beyond REMORA. These are synthetic, offline, bounded tests. The testbed's reproduction executes the APS-authored verifier; it is not an independently implemented APS verifier.

**Independent projects. Shared boundaries. Verifiable evidence.**

We welcome developers, independent reviewers, building-automation specialists and potential pilot partners who want to challenge the results or explore future integrations.

**Check the result, not just the claim:**
- APS contribution: https://github.com/darklordVirtual/autonomous-ot-control/pull/35
- Reproduced aps-1 result: https://github.com/darklordVirtual/autonomous-ot-control/blob/main/docs/results/2026-10-28/aps-authority.md
- Federation discussion: https://github.com/aeoess/agent-governance-vocabulary/issues/177

#AgenticAI #AIGovernance #OpenSource #Interoperability #REMORA #BuildingAutomation

---

## Claims ledger — direct APS integration (check these before approval)

| Claim in post | Public evidence and attribution | Limit |
| --- | --- | --- |
| APS supplied five signed synthetic delegation chains and a pinned verifier | [APS contributor PR #35](https://github.com/darklordVirtual/autonomous-ot-control/pull/35), by [@aeoess](https://github.com/aeoess); [APS source repo](https://github.com/agent-passport-system/aps-ot-authority) | Author-produced delegated authority material; not a complete OT authorization |
| OT testbed supplied independent work-order decisions and harness | [OT harness PR #29](https://github.com/darklordVirtual/autonomous-ot-control/pull/29), by [@darklordVirtual](https://github.com/darklordVirtual); [authority contract](https://github.com/darklordVirtual/autonomous-ot-control/blob/main/docs/federation/authority-fixture-contract.md) | Local signed work orders and simulator check are separate from APS delegation |
| Five cases matched expected outputs; one admitted | [aps-1 reproduction on testbed](https://github.com/darklordVirtual/autonomous-ot-control/blob/main/docs/results/2026-10-28/aps-authority.md) at testbed `4b3e25c`; sealed package `sha256:cf5cdbf3345b844df6254314f02de001ed3d4ba2141b76355b068d40a26240d6` | Delegation 5/5, work order 5/5, oracle 5/5. One admitted *synthetically*. No real plant, no production safety |
| APS rejected widened, expired and out-of-scope delegation, while local work order rejected the out-of-range value | [Five-row result table](https://github.com/darklordVirtual/autonomous-ot-control/blob/main/docs/results/2026-10-28/aps-authority.md) | APS verifier does **not** inspect setpoint value, unit or signed work order; case 5 is **not** an APS refusal |
| Verifier identity discrepancy was found and corrected before merge | [@darklordVirtual review comment](https://github.com/darklordVirtual/autonomous-ot-control/pull/35#issuecomment-6476591952), [@aeoess fix report](https://github.com/darklordVirtual/autonomous-ot-control/pull/35#issuecomment-6476642993), [merged PR #35](https://github.com/darklordVirtual/autonomous-ot-control/pull/35) | A corrected metadata identity mismatch, not a proven production exploit |
| Measurable protection added by APS over REMORA | [Scope in PR #35](https://github.com/darklordVirtual/autonomous-ot-control/pull/35), [issue #27](https://github.com/darklordVirtual/autonomous-ot-control/issues/27) | **NOT ESTABLISHED.** Offline verdict testing is not an inline B/C measurement; do not claim additional security benefit yet |

### Other contributors and their *separate* testbed/federation boundaries

| Contributor / project | What they actually contributed | Checkable reference | Do **not** imply |
| --- | --- | --- | --- |
| [@astrogilda](https://github.com/astrogilda), Probity AI / agent-evidence-vectors | External `effect_evidence` reader and test evidence, including observation-vantage limitation | [PR #22](https://github.com/darklordVirtual/autonomous-ot-control/pull/22) | APS verifier implementation or independent APS result |
| [@giskard09](https://github.com/giskard09), argentum-core / Mycelium Trails | External `L1_REPRODUCTION` run of the testbed's **reference** effect-evidence verifier | [PR #25](https://github.com/darklordVirtual/autonomous-ot-control/pull/25) | An independently implemented APS verifier |
| [@altrudev](https://github.com/altrudev), Altru.dev / Frequency | Bounded offline runner-validity evaluation, including four adverse adapter probes | [Published report](https://gist.github.com/altrudev/0980db0fb44ad4772ec8bc4efb6d0d17) | Runtime OT integration or full security review |
| [@Tetsurohhori](https://github.com/Tetsurohhori), aos-standard/catalog | Independently authored effect-evidence reader and mutation analysis; published disagreements and limitations | [First mutation analysis](https://github.com/aeoess/agent-governance-vocabulary/issues/177#issuecomment-6468878522), [subsequent 42-case run](https://github.com/aeoess/agent-governance-vocabulary/issues/177#issuecomment-6499700482) | Direct APS integration or a fully blind evaluation |
| [@aeoess](https://github.com/aeoess), [@QueBallSharken](https://github.com/QueBallSharken), [@douglasborthwick-crypto](https://github.com/douglasborthwick-crypto), [@MoltyCel](https://github.com/MoltyCel), others | Named vocabulary co-authors and many project-specific crosswalk contributions | [Agent Governance Vocabulary README](https://github.com/aeoess/agent-governance-vocabulary/blob/main/README.md) | That the entire vocabulary group worked on APS or the OT testbed |

**Credit policy:** Each person retains authorship over their contribution and project. Inclusion as a credited contributor is not a claim of federation opt-in, endorsement, production use or any commercial agreement. Probity AI's effect-evidence reader remains independently authored and licensed; do not conflate it with REMORA's core. The publication is not a claim of an external security certification.

### Status after the historical aps-1 run (not part of the first-post result)

- [OT PR #38](https://github.com/darklordVirtual/autonomous-ot-control/pull/38) proposes stricter delegation leaf-ID binding, scored refusal reasons and separate `indeterminate` results. **Open when this draft was prepared.**
- [@aeoess's PR #38 comment](https://github.com/darklordVirtual/autonomous-ot-control/pull/38#issuecomment-6501108734) reports author-run `aps-2` tests with a newer APS verifier and a Docker CI run. These are APS-side reports, **not** a merged strict APS integration or a result to silently substitute for historical `aps-1`.
- Even after technical hardening, the boundary remains synthetic and offline. Future inline A/B/C evaluation is separate and requires an independent baseline and oracle.

## Review requested from credited contributors

- [ ] **@aeoess:** Verify APS scope, signed-chain/verifier provenance, test counts, correction history and phrasing of your credit.
- [ ] **@darklordVirtual:** Verify testbed/work-order/oracle claims and that publishing does not imply production readiness.
- [ ] **@astrogilda, @giskard09, @altrudev, @Tetsurohhori:** Check that the *other-boundaries* credits are precise and do not imply APS contribution or endorsement. Propose any corrections.
- [ ] **Vocabulary contributors:** Confirm description and whether attribution is appropriately limited to vocabulary/crosswalk work.
- [ ] Replace GitHub @handles with confirmed LinkedIn profiles/tags, or use plain-text names where no confirmation exists.
- [ ] Confirm final wording and links with participants before publishing. No automated social posting is part of this PR.

The file is intentionally editorial only: no changes to code, verifier, contracts, tests, fixtures, claims, CI or runtime behavior.
