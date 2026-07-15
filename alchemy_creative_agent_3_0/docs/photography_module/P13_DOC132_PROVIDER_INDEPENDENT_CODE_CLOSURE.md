# P13: Doc132 Photography Provider-Independent Code Closure

Status: `code_closure_passed` for the Alchemy-owned Photography contracts on
the frozen baseline below. This is not a P10 production pass.

## Frozen Baseline

| Field | Value |
| --- | --- |
| Mainline base | `origin/main@d521b3777654edfe7c0d92cc15d5371e509bdde3` |
| Scope | `photographer_template` structural contracts and public projection |
| Provider dependency | None; all execution uses existing shared deterministic seams |
| Local MCP | Current General-only gate remains correct; a future frozen-plan relay is a mainline test seam, not a Provider or code-closure blocker |
| Production release | `production_gate_pending` under Doc127 real Web Provider and certifying-review requirements |

## Fixture Evidence

`test_v3_photography_doc132_code_closure.py` adds a small deterministic
closure fixture. It uses the existing remote-Brain test double, shared
generation, shared review/retry, shared final-delivery projection and durable
project store. It introduces no Photography-specific Provider, reviewer,
retry loop, selector, prompt recipe or image artifact.

| Fixture ID | Scenario / requested count | Expected and observed closure |
| --- | --- | --- |
| PX132-1 | `single_hero` / 1 | One frozen `hero_photograph` role reaches the shared final-delivery projection; reopen retains `photographer_template`. |
| PX132-2 | `professional_set` / 3 | The frozen roles are exactly `session_hero`, `environmental_context`, `detail_or_moment`; each has one current final winner and append-only root history. No set is reconciled as a single image. |
| PX132-3 | Browser/API projection | Recent summary and reopened detail retain `primary_template_id=photographer_template`; browser mapping selects the Photography workspace and fixes the professional-set count at three structurally. |
| PX132-4 | `professional_set` / metadata-only review | Every role remains visible to the shared certification ledger, but terminal state is blocked, automatic delivery is false and ordinary project outputs are empty. |

Existing shared regressions remain the authority for the related boundary
contracts:

- explicit named-profile reconfirmation and immutable binding;
- new nonhuman identity evidence requiring shared high-fidelity negotiation;
- explicit incomplete-role diagnostics and append-only retry-winner history;
- manual confirmation/metadata-only withholding; and
- Local MCP rejecting `photographer_template` rather than downgrading it to
  General.

## Commands And Results

```text
python -m pytest \
  alchemy_creative_agent_3_0/tests/test_v3_photography_doc132_code_closure.py \
  alchemy_creative_agent_3_0/tests/test_v3_photography_mainline_004.py \
  alchemy_creative_agent_3_0/tests/test_v3_photography_llm_first_mainline_005.py \
  alchemy_creative_agent_3_0/tests/test_v3_photography_p6_professional_set.py \
  alchemy_creative_agent_3_0/tests/test_v3_photography_production_activation.py \
  alchemy_creative_agent_3_0/tests/test_v3_photography_p6_provider_acceptance.py \
  alchemy_creative_agent_3_0/tests/test_v3_nonhuman_subject_identity.py \
  alchemy_creative_agent_3_0/tests/test_v3_project_mode.py \
  alchemy_creative_agent_3_0/tests/test_v3_product_api_minimal_ux.py \
  tests/test_doc130_codex_native_prompt_parity.py -q

165 passed in 24.19s

python -m pytest alchemy_creative_agent_3_0/tests -q

724 passed, 2 FastAPI deprecation warnings in 77.31s
```

The full V3, compile, browser syntax and whitespace checks are recorded with
the closure commit. No customer media, full creative prompts, credentials,
Provider endpoints, account/line information, raw responses or generated
media are included in this record.

## Boundary Verdict

`code_closure_passed` applies only to the Alchemy implementation listed here.
No real Web Provider pixel, visual certification or human quality review is
asserted. Photography therefore remains `production_gate_pending`; any
upstream no-pixel outcome remains `upstream_hold` unless it produces a
reproducible Alchemy contract defect.

## Future Mainline Seam: Frozen Photography Plan Relay

Current Local MCP correctly rejects raw `photographer_template` requests and
must continue to do so until mainline adds an explicit relay. That relay must
consume an **already frozen** Photography execution plan; it must not call
Scenario Runtime planning or reinterpret the request as General.

The smallest safe consumable contract is:

```text
template_id=photographer_template
scenario_id=photography
remote_brain_provenance={llm_used=true, fallback_used=false}
frozen_role_order=[session_hero, environmental_context, detail_or_moment]
per_role={role_id, canonical_final_prompt, canonical_prompt_sha256,
          admitted_reference_paths, reference_source_hashes}
```

The relay should validate the immutable role order and exact requested count,
then make one conversation-only Codex ImageGen call per frozen role using the
canonical prompt and admitted references unchanged. Its outputs must remain
`conversation_only_not_certified`: no project candidate, review, retry,
selector, artifact import, final delivery or P10 evidence may be created.

Recommended mainline regression tests:

1. a relay fixture whose Scenario Runtime planner raises if called, proving no
   replan or General downgrade occurs;
2. exact prompt hashes and reference-source hashes match the shared Web
   materializer for every frozen role;
3. wrong role count, reordered roles, missing remote-Brain provenance or a
   missing high-fidelity nonhuman reference fail closed;
4. normal Local MCP requests for `photographer_template` remain rejected until
   the explicit relay entry point is selected; and
5. relay output never reaches project outputs, review certification or
   production-gate evidence.
