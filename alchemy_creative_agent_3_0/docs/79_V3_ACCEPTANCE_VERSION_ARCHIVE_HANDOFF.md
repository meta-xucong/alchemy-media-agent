# V3 Acceptance Version Archive Handoff

Date: 2026-07-05

## Archive Goal

This handoff archives the V3 Creative OS acceptance checkpoint after the project-mode frontend, general template workflow, LLM brain integration, visual capability cluster, strong-reference loop, post-generation review, retry guardrails, and long-term identity / beautiful realism tuning were brought together into one coherent V3 stage.

This archive is intended to be a stable GitHub checkpoint before moving into the next specialized-agent stage.

## Scope Included

- V3 Project Mode application layer over the existing V3 runtime.
- Project-first frontend with project cards, project history, grouped image history, fixed-size cards, modal project image review, and continuation workflow.
- General template production flow with four user-facing modes:
  - Auto selection
  - Similar candidate mode
  - Suite expansion mode
  - Creative exploration mode
  - Size / layout adaptation mode
- Generation count and image size controls in the V3 workbench.
- LLM brain adapter and checkpoint-style reasoning metadata.
- Native V3 shared visual capability cluster, including:
  - visual grammar extraction and reuse
  - strong reference continuation
  - identity anchor planning
  - human natural variation balancing
  - post-generation visual review
  - retry decisions and retry guardrails
  - anti-AI-face photorealism guidance
  - East Asian fair complexion and proportion guard
  - long-term identity and beautiful-realism final tuning
- V3 frontend and provider contract regression tests.
- Documentation set through Doc78 plus this archive handoff.

## Architecture Boundary Confirmed

V3 keeps the intended modular structure:

```text
V3 base runtime
  -> Project Mode
      -> Template / Scenario Pack
          -> Job
              -> Shared Capabilities
                  -> Visual Capability Cluster
              -> LLM Brain
              -> Provider Router
```

The recent visual upgrades are centralized under the native V3 shared capability cluster. The central brain and scenario runtime read and pass the capability metadata; they do not own the visual enhancement rules directly.

V1/V2 remain independent. V3 can reuse proven ideas and provider configuration patterns, but V3 does not require V1/V2 runtime code to function.

## Verification Passed

Latest acceptance audit results:

```text
python -m pytest alchemy_creative_agent_3_0\tests -q --tb=short
305 passed

python -m pytest tests\test_v3_commercial_frontend_shell.py tests\test_provider_contract.py -q --tb=short
34 passed

python -m pytest alchemy_creative_agent_3_0\tests\test_v3_doc66_strong_reference_real_review.py `
  alchemy_creative_agent_3_0\tests\test_v3_doc68_casebook_guided_quality.py `
  alchemy_creative_agent_3_0\tests\test_v3_doc70_human_ai_feel_reduction.py `
  alchemy_creative_agent_3_0\tests\test_v3_doc72_east_asian_fair_complexion_and_proportion_guard.py `
  alchemy_creative_agent_3_0\tests\test_v3_doc73_first_output_identity_anchor.py `
  alchemy_creative_agent_3_0\tests\test_v3_doc78_long_term_identity_beautiful_realism.py -q --tb=short
32 passed

python -m compileall -q alchemy_creative_agent_3_0\app src_skeleton\app alchemy_creative_agent_3_0\tests tests
passed

git diff --check -- alchemy_creative_agent_3_0\app alchemy_creative_agent_3_0\tests src_skeleton\app tests
passed, with Windows LF/CRLF warnings only
```

Frontend audit confirmed:

- `/creative-agent-v3` returns HTTP 200.
- V3 navigation title is `生图 V3.0 creative OS`.
- V3 appears before Alchemy Lab in the top navigation.
- V3 homepage is project-first.
- The V3 workbench exposes the four mode choices, generation count, and image size controls.
- Browser console had no frontend errors during acceptance audit.

## Files Intentionally Excluded

Temporary real-generation output folders are not part of the source archive:

```text
tmp_v3_doc*_real_outputs*/
.codex-longrun/
```

These files can contain generated images, local run logs, and bulky validation artifacts. They are useful locally but should not be committed as source.

## Known Non-Blocking Notes

- The legacy-compatible `/api/v3/creative-agent/history` endpoint may still return older records without `project_id`. The V3 homepage no longer depends on direct old job history rendering; project-mode rendering uses project records.
- Real image generation quality still depends on upstream provider stability. The application has retry and health guardrails, but provider 403/500 fluctuations can still affect a live generation attempt.
- Specialized modules such as ecommerce and photographer workflows should tune suite-director semantics inside their own templates rather than forcing every scene-specific rule into the general template.

## Next Development Direction

After this archive, the recommended next stage is specialized module development:

- ecommerce template suite director
- photographer template
- product-specific commercial image QA
- deeper provider-side reliability and health probes
- optional human evaluation set for Lovart-level benchmark comparison

This archive should be treated as the V3 general-template foundation checkpoint.
