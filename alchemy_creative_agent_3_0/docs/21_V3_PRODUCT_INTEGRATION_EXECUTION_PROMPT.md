# 19 V3 Product Integration Execution Prompt

This document is the execution bridge for implementing the user-facing Alchemy Creative Agent 3.x product inside `alchemy-media-agent`.

It must be used after the V3 foundation, brand-memory, generation-loop, product-boundary, scenario-platform, and General Creative specifications have been read.

This document does not replace any earlier specification. It tells an implementation agent how to combine them into one continuous delivery run without stopping after an intermediate phase.

---

## 1. Objective

Implement the V3 product integration as one coherent, non-destructive addition to the current `alchemy-media-agent` repository.

The implementation target is:

```text
shared V1 / V2 / Alchemy Lab site shell
  -> new 3.0 navigation entry
  -> V3 Scenario Hub
  -> registry-driven scenario cards
  -> General Creative full workspace
  -> V3-owned API and runtime
  -> existing Central Creative Brain
  -> auditable product result flow
```

The current stage must deliver:

```text
V3 extension framework
V3 3.0 home UI inside the shared shell
General Creative as the only complete executable scenario
placeholder cards for ecommerce, new media, private community, and brand IP
end-to-end local tests and smoke validation
```

The current stage must not deliver:

```text
detailed ecommerce workflow
detailed new-media workflow
detailed private-community workflow
detailed brand-IP workflow
AI manga-drama first-screen workflow
real heavy sidecar integration unless already required by earlier accepted docs
any V1/V2 runtime coupling
```

---

## 2. Required Reading Order

Read these documents before writing code:

```text
alchemy_creative_agent_3_0/docs/00_ROOT_RULES.md
alchemy_creative_agent_3_0/docs/01_PRODUCT_VISION.md
alchemy_creative_agent_3_0/docs/02_SYSTEM_ARCHITECTURE.md
alchemy_creative_agent_3_0/docs/03_AGENT_AND_MODULE_SPEC.md
alchemy_creative_agent_3_0/docs/05_DEVELOPMENT_ROADMAP.md
alchemy_creative_agent_3_0/docs/06_CODEX_TASK_PROMPT.md
alchemy_creative_agent_3_0/docs/07_SCHEMA_CONTRACTS.md
alchemy_creative_agent_3_0/docs/08_GOLDEN_CASES.md
alchemy_creative_agent_3_0/docs/09_RULES_AND_DEFAULTS.md
alchemy_creative_agent_3_0/docs/10_BRAND_MEMORY_SPEC.md
alchemy_creative_agent_3_0/docs/11_EVALUATION_AND_REFINEMENT_SPEC.md
alchemy_creative_agent_3_0/docs/12_PROVIDER_INTERFACES.md
alchemy_creative_agent_3_0/docs/13_STEP_BY_STEP_DELIVERY_PLAN.md
alchemy_creative_agent_3_0/docs/14_CODEX_TASK_PROMPTS_PHASE_2_AND_3.md
alchemy_creative_agent_3_0/docs/15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md
alchemy_creative_agent_3_0/docs/16_V3_FOUNDATION_EXECUTION_GUARDRAILS.md
alchemy_creative_agent_3_0/docs/17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md
alchemy_creative_agent_3_0/docs/18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md
alchemy_creative_agent_3_0/docs/19_GENERAL_CREATIVE_QUICK_START_PRESETS_SPEC.md
alchemy_creative_agent_3_0/docs/20_GENERAL_COMMON_SCENE_EXECUTION_AND_CONTRACT_CLOSURE_SPEC.md
alchemy_creative_agent_3_0/docs/21_V3_PRODUCT_INTEGRATION_EXECUTION_PROMPT.md
```

If any document appears to conflict with another, use this precedence:

```text
1. 00_ROOT_RULES.md
2. frozen V3 core schema and provider contracts
3. existing Central Creative Brain behavior
4. 15 product boundary rules
5. 17 scenario-platform rules
6. 18 General Creative product/runtime rules
7. 19 General Creative quick-start preset rules
8. 20 General Common Scene execution and contract-closure rules
9. this execution bridge
```

---

## 3. Repository Integration Boundary

Use the latest target branch as the repository baseline before opening a pull request.

The implementation must preserve existing V1, V2, and Alchemy Lab behavior.

Allowed edits outside `alchemy_creative_agent_3_0/`:

```text
shared shell navigation entry for 3.0
shared shell static asset references needed to mount V3
backend route registration that delegates to V3-owned handlers
README or documentation index updates
tests needed to prove V1/V2/Alchemy Lab are not broken
```

Forbidden edits outside `alchemy_creative_agent_3_0/`:

```text
rewriting V1 generation flow
rewriting V2 prompt transform or generation flow
rewriting Alchemy Lab rare-style explorer logic
renaming existing V1/V2/Alchemy Lab routes
changing V1/V2 data models to fit V3
calling V3 through V1/V2 runtime internals
```

If an implementation needs platform behavior such as account, balance, storage, or deployment, create a V3-owned adapter and bridge through that adapter.

---

## 4. Existing Local V3 Code Reconciliation

If V3 code already exists in a local worktree, do not rewrite it blindly.

Required reconciliation sequence:

```text
1. Identify the source branch and commit of the local V3 code.
2. Compare it against the latest target branch.
3. Preserve V3-owned files under alchemy_creative_agent_3_0/.
4. Drop runtime artifacts, caches, media output folders, and temporary logs.
5. Re-run V3 tests.
6. Re-run affected root tests.
7. Add missing scenario-platform and General Creative contracts from docs 17 and 18.
8. Add shared-shell integration only after backend/runtime tests pass.
```

Do not stage:

```text
.media_storage/
__pycache__/
*.pyc
.pytest_cache/
temporary screenshots
local server logs
personal environment files
```

---

## 5. Required Product Behavior

The V3 entry must be visible from the existing site shell as `3.0`.

Clicking `3.0` opens the V3 Scenario Hub.

The V3 Scenario Hub must show exactly these first-screen cards:

```text
General Creative / 通用创作        available
E-Commerce / 电商特调             placeholder
New Media Marketing / 新媒体营销  placeholder
Private Community / 私域社群运营  placeholder
Brand IP Operations / 品牌 IP 运营 placeholder
```

Only `General Creative / 通用创作` may create jobs in the current stage.

Placeholder cards may show:

```text
name
short description
typical use cases
coming-soon state
Use General Creative instead action
```

Placeholder cards must not:

```text
open complex forms
create jobs
call pack-owned APIs
call pack-owned agents
activate pack-specific generation or evaluation policies
```

---

## 6. General Creative Workspace

The default General Creative UI must be beginner-first.

Default visible UI:

```text
one main natural-language input
quick-start scene cards
optional brand selector
optional reference upload
one primary generate button
progress area
result area
history area
```

Required quick-start cards:

```text
single_commercial_image        一张商业图
commercial_image_series       一组营销图
festival_campaign             节日活动图
poster_or_cover               海报 / 封面 / 宣传图
brand_style_continuation      延续品牌风格
reference_image_recreation    参考图再创作
text_or_price_revision        改文字 / 改价格
auto_planning                 不知道怎么做，帮我规划
```

Advanced configuration must be collapsed by default.

The beginner UI must not expose:

```text
provider
adapter
sampler
node graph
seed
CFG
IP-Adapter
ControlNet
ComfyUI
raw provider payloads
```

---

## 7. General Agent Logic

Every General Creative request must pass through intent understanding before V3 job creation.

Supported intent categories:

```text
single_image
image_series
brand_continuation
reference_image_recreation
text_revision
campaign_or_event
ambiguous_request
```

Required flow:

```text
NaturalLanguageInput
  -> GeneralIntentInterpreter
  -> optional brief expansion for ambiguous_request
  -> CreativeJob draft
  -> ScenarioRuntime
  -> GeneralCreativeScenarioPack
  -> DefaultCommercialPack
  -> Central Creative Brain
```

The General Creative agent may use:

```text
CommercialBrief
BrandProfile / brand memory
CreativePlan
SeriesPlan
LayoutPlan
PromptCompilationResult
ConditionPlan
GenerationPlan
EvaluationReport
CommercialAssetPack
```

It must not call future specialized agents in this stage.

---

## 8. Continuous Delivery Rule

Do not stop after Foundation if the task objective or document set requires a complete V3 product flow.

Required phase loop:

```text
1. Analyze all V3 documents.
2. Build or reconcile current implementation.
3. Run focused tests.
4. Audit against docs.
5. Fix gaps.
6. Proceed to next required phase automatically.
7. Repeat until all current-stage docs are satisfied.
8. Run final full audit.
9. Run simulated UI/API tests.
10. Run real local smoke tests when environment allows.
11. Prepare GitHub PR without merging automatically.
```

Do not mark complete while any current-stage requirement in docs 17, 18, 19, 20, or this document remains unmet.

---

## 9. Minimum Test Gate

Run at least:

```text
python -B -m pytest alchemy_creative_agent_3_0/tests -q
python -B -m pytest tests -q
```

If the full root suite is too broad or requires unavailable external services, run the closest offline subset and document the limitation.

Required assertions:

```text
V3 does not import V1/V2 runtime modules
V3 docs 17, 18, 19, 20, and 21 are indexed
Scenario Hub manifests are registry-driven
General Creative is executable
General Common Scene preset resolution is deterministic and schema-safe
placeholder cards are not executable
V3 API routes are V3-owned
V1/V2/Alchemy Lab smoke paths still load
```

---

## 10. Final Report Format

At the end of the implementation run, report:

```text
V3_PRODUCT_INTEGRATION_STATUS: COMPLETE or INCOMPLETE
BASELINE_RECONCILIATION_STATUS: PASS or FAIL
V1_V2_ALCHEMY_LAB_IMPACT_STATUS: PASS or FAIL
SCENARIO_HUB_STATUS: PASS or FAIL
GENERAL_CREATIVE_STATUS: PASS or FAIL
PLACEHOLDER_BOUNDARY_STATUS: PASS or FAIL
APP_BOUNDARY_STATUS: PASS or FAIL
INDEPENDENCE_STATUS: PASS or FAIL
TEST_STATUS: PASS or FAIL
GITHUB_PR_STATUS: CREATED or NOT_CREATED
```

Also summarize:

```text
target branch
local source branch if reconciled
files changed outside alchemy_creative_agent_3_0/
tests run
known limitations
manual verification steps
```
