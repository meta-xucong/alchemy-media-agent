# 48 V3 LLM Brain Adapter And Pre-Generation Reasoning Spec

Current authority note:

```text
Documents 51 and 52 supersede this document where this document discusses
Lovart-like commercial consistency, strong selected references,
subject/identity consistency, post-generation review hooks, retry
recommendations, retry execution, suite variation direction, or output
curation.

This document remains the authority for the V3 LLM Brain Adapter and
multi-stage checkpoint reasoning. Document 51 clarifies that output review,
identity/product locking, strong reference binding, automatic retry planning,
and best-output selection are owned by the Visual Capability Cluster, while
the LLM Brain consumes and summarizes those results.

Document 52 further clarifies that real image inspection, retry execution
policy, suite variation planning, and output curation remain Visual Capability
Cluster / Product API responsibilities. The LLM Brain may summarize reports and
write beginner-facing explanations, but it must not own visual review or retry
scoring.
```

## 1. Purpose

This document adds one missing capability to the current V3 project-mode system:

```text
before image generation, V3 should perform real LLM-based intent understanding,
project-context reasoning, prompt refinement, and quality self-checking
```

The goal is not to reuse the V2 Claude orchestrator.

The goal is to make V3's own architecture do what the product vision always
intended:

```text
simple user input
  -> project context reading
  -> LLM creative reasoning
  -> structured V3 plans
  -> prompt compilation
  -> real image generation
  -> review
  -> project memory continuation
```

The user should still experience the product as:

```text
write one sentence
optionally upload references
click generate
receive a coherent commercial image set inside a project
```

The heavy thinking must happen behind the scenes.

---

## Document 50 Update

Document `50` supersedes this document wherever brain routing or reusable
visual enhancement ownership is ambiguous.

Current authoritative refinement:

```text
1. V3 uses one reasoning architecture: a V3-owned direct LLM checkpoint brain
   with deterministic fallback.
2. V3 must not add Claude Code as an expert-brain runtime, CLI provider,
   sidecar agent, or future extension point.
3. Direct LLM API providers may still be used through V3-owned adapters.
4. Visual grammar, reference binding, project visual memory, consistency
   guards, and visual review are owned by the Visual Capability Cluster, not by
   the LLM Brain.
5. The LLM Brain consumes Visual Capability Cluster outputs and produces
   checkpoint decisions; it must not absorb or duplicate the cluster's visual
   module responsibilities.
```

Use document `50` for the next implementation phase that upgrades this adapter
from a single enrichment step into multi-stage checkpoints.

---

## 2. Compatibility Decision

This document is fully compatible with documents `32` through `47`.

It does not replace:

```text
Project Mode
Template-first project creation
ProjectContextPackage
ScenarioRuntime
Scenario Pack Registry
CentralCreativeBrain
Shared Capability modules
Product API
Generation Provider adapters
Brand Memory confirmation flow
Single production entry UI
```

It adds:

```text
V3-owned LLM Brain Adapter
Pre-generation reasoning contracts
Prompt review contract
User-facing reasoning summary
Optional post-generation review hook
Selected-output strong reference bridge
```

Template scope guard:

```text
this phase originally wired the LLM Brain into the general creative template first
the ecommerce freeze line was historical for the Doc48 implementation phase
current template activation follows Document 42, the template registry, and
Document 51 template consistency policy
the LLM Brain must not re-enable ecommerce job creation
the LLM Brain must not mix general project context into ecommerce template state
future templates may opt in only through the template interface contract
```

The architecture remains:

```text
V3 Foundation
  -> Project
      -> Template
          -> Scenario Pack
              -> Shared Capabilities
              -> LLM Brain Adapter
              -> CentralCreativeBrain
              -> Job
              -> Generation Provider
              -> Review / Selection / Continuation
```

The LLM Brain Adapter must be optional and degradable. If no LLM provider is
configured, V3 must continue to use the current deterministic Central Creative
Brain flow.

---

## 3. Relationship To Existing Documents

### 3.1 Document 02 - System Architecture

Document `02` already defines V3 as a multi-agent creative production pipeline,
not a single prompt enhancer.

This document implements the missing LLM reasoning layer inside that pipeline.

The LLM Brain Adapter is not a second central brain. It is a reasoning provider
used by the existing Central Creative Brain.

### 3.2 Document 03 - Agent And Module Spec

Document `03` says the Central Creative Brain must orchestrate:

```text
intent interpretation
commercial brief generation
brand memory usage
creative planning
series planning
layout planning
prompt compilation
generation routing
evaluation and refinement
```

The current implementation performs these tasks mostly through deterministic
agents. This document adds an LLM-based enrichment step while keeping those
agents and schemas.

### 3.3 Document 11 - Evaluation And Refinement

Document `11` defines a future closed loop:

```text
plan -> generate candidates -> score -> critique -> refine -> accept best
```

This document adds the first real implementation path for:

```text
LLM prompt self-check before generation
optional vision/LLM review after generation
refinement instructions when results are weak
```

### 3.4 Document 24 - V1/V2 Shared Capability Migration

Document `24` says V1/V2 advantages must not be copied directly into V3 and
must not be buried only inside a vertical template.

This document follows that rule:

```text
do not import V1/V2 runtime
do not reuse V2 prompt plan objects
do not reuse V2 Claude orchestration code
rebuild the thinking layer as V3-owned contracts
```

### 3.5 Document 34 - Project Contract And Context

Document `34` defines `ProjectContextPackage` as the reusable project context.

The LLM Brain Adapter must read `ProjectContextPackage`.

It must obey the same rules:

```text
selected outputs only become positive context
unselected candidates do not become positive context
negative feedback is respected
Brand Memory is read only when linked or selected
Brand Memory is not silently overwritten
provider-specific fields stay out of project context
```

### 3.6 Document 36 - General Template Project Flow

Document `36` requires continuation jobs to use project context.

This document clarifies how:

```text
ProjectContextPackage
  -> LLM Brain Adapter
  -> structured creative decision
  -> CentralCreativeBrain metadata
  -> prompt compilation
  -> provider prompt
```

### 3.7 Document 43 - Product Experience Quality Gate

Document `43` requires beginner-friendly UI and high-value plain-language work
results.

The LLM Brain Adapter may produce detailed internal reasoning, but the UI must
only show concise user-facing summaries.

Forbidden:

```text
chain-of-thought
raw provider payload
debug prompt fragments
model call logs
internal schema dumps
```

Allowed:

```text
V3 understood the goal
V3 kept these references
V3 optimized this visual direction
V3 checked these quality points
V3 will avoid these rejected directions
```

### 3.8 Document 47 - Single Production Entry

Document `47` simplifies the UI to one production entry.

This document does not add more user steps.

The LLM stages should appear only as compact progress messages and optional
folded details.

---

## 4. Current State Audit

The current V3 implementation already has:

```text
Project mode
Template-first project creation
General Template project jobs
ProjectContextPackage
Selected-output context
Brand Memory proposal / confirmation
Shared Capability modules
CentralCreativeBrain deterministic pipeline
PromptCompilerAgent
GenerationRouter
Real image provider through GPT image 2 / OpenAI-compatible settings
Final provider prompt metadata
Frontend workflow summary
Project history and image grouping
```

The current V3 implementation does not yet fully have:

```text
real LLM reasoning before generation
multi-stage intent and context analysis
LLM prompt refinement and self-check
LLM-readable project memory digest
post-generation visual review
automatic retry based on review
selected generated outputs passed as strong provider references
```

Therefore, V3 is already a project-based generation agent, but it is not yet a
fully LLM-led creative director.

---

## 5. Design Principle

The LLM Brain Adapter must be:

```text
V3-owned
schema-first
optional
auditable
degradable
template-aware
project-context-aware
provider-agnostic
safe for beginner UI
```

It must not be:

```text
a V2 Claude bridge
a prompt-only hack
a hidden monolithic workflow
a provider-specific parameter generator
a replacement for ScenarioRuntime
a replacement for CentralCreativeBrain
a replacement for Shared Capabilities
```

---

## 6. Target Runtime Flow

### 6.1 Current Flow

```text
Project job request
  -> ScenarioRuntime
  -> Shared Capabilities
  -> CentralCreativeBrain deterministic agents
  -> PromptCompilerAgent
  -> GenerationRouter
  -> Provider
```

### 6.2 Target Flow

```text
Project job request
  -> ProjectContextPackage
  -> ScenarioRuntime
  -> Shared Capabilities
  -> LLM Brain Adapter
       1. understand user intent
       2. read project memory
       3. decide visual direction
       4. plan image set slots
       5. draft final prompt guidance
       6. self-check conflicts and quality risks
  -> CentralCreativeBrain deterministic agents
       consume LLM structured decision
  -> PromptCompilerAgent
       compile V3 prompt with LLM guidance
  -> GenerationRouter
  -> Provider
  -> optional OutputReviewModule / LLM review
  -> Project output records
```

The LLM Brain Adapter enriches the pipeline. It does not create jobs directly.

---

## 7. New Package

Add:

```text
alchemy_creative_agent_3_0/app/llm_brain/
```

Recommended files:

```text
__init__.py
contracts.py
adapter.py
providers.py
prompts.py
context_digest.py
prompt_review.py
quality_review.py
audit.py
fallback.py
```

Responsibilities:

| File | Responsibility |
| --- | --- |
| `contracts.py` | V3-native request/result schemas |
| `adapter.py` | Main `V3LLMBrainAdapter` orchestration |
| `providers.py` | Direct configured LLM API calls through V3-owned adapters |
| `prompts.py` | System prompts and JSON schema prompts |
| `context_digest.py` | Convert project context into compact LLM-safe digest |
| `prompt_review.py` | Pre-generation prompt self-check |
| `quality_review.py` | Optional post-generation review contract |
| `audit.py` | Safe metadata and user-facing summary helpers |
| `fallback.py` | Deterministic fallback result |

---

## 8. Contracts

### 8.1 BrainRunRequest

Fields:

```text
request_id
project_id
template_id
scenario_id
user_input
project_context
shared_capability_summary
brand_memory_summary
uploaded_reference_summary
selected_output_summary
negative_feedback_summary
requested_image_count
requested_image_size
quality_mode
metadata
```

Rules:

1. `project_context` must be a `ProjectContextPackage` snapshot or a safe
   subset of it.
2. Selected outputs are positive context only when their project selection state
   is selected.
3. Unselected outputs may appear only as history counts, never as positive
   references.
4. Rejected direction notes must be included.
5. Provider names and raw API parameters must not be part of the request payload
   sent to the LLM unless needed for internal routing diagnostics outside the
   prompt.

### 8.2 BrainIntentSummary

Fields:

```text
main_goal
use_case
target_audience
primary_subject
must_keep
must_avoid
ambiguities
missing_but_optional_inputs
```

Purpose:

Capture what the user wants in plain structured form.

### 8.3 BrainProjectMemoryDigest

Fields:

```text
confirmed_style
confirmed_palette
confirmed_layout_logic
selected_reference_outputs
uploaded_references
brand_memory
negative_directions
continuity_strength
```

Purpose:

Give the LLM a safe, compact view of the current project.

### 8.4 BrainImageSetPlan

Fields:

```text
set_goal
image_count
slots
continuity_rules
variation_rules
```

Each slot:

```text
slot_id
slot_name
purpose
subject_focus
scene_direction
composition_direction
style_direction
reference_usage
avoid_notes
```

For the current General Template phase, slot names should remain generic and
beginner-friendly:

```text
main visual
social cover
detail / mood variation
same-style extension
```

Do not introduce marketplace-specific slot logic in this document.

### 8.5 BrainPromptGuidance

Fields:

```text
visual_direction
style_notes
layout_notes
hard_constraints
negative_prompt
reference_binding_notes
final_prompt_guidance
```

Rules:

1. It must refine the user's request without reversing it.
2. It must preserve exact user facts.
3. It must not silently add "no people", "no text", "no logo", "remove brand",
   or similar exclusions.
4. It must not invent product facts, awards, certifications, performance
   claims, or platform claims.
5. It must explain how selected project references should be used.

### 8.6 BrainPromptReview

Fields:

```text
status
conflicts
missing_constraints
overly_generic_parts
unsafe_or_unsupported_claims
reference_consistency_risks
final_rewrite_notes
```

Allowed status values:

```text
pass
revise
fallback_to_deterministic
block
```

### 8.7 BrainRunResult

Fields:

```text
brain_run_id
status
provider
model
fallback_used
intent_summary
project_memory_digest
image_set_plan
prompt_guidance
prompt_review
user_visible_summary
progress_steps
warnings
metadata
```

Forbidden fields:

```text
chain_of_thought
raw_hidden_reasoning
full provider response body
API key
provider request headers
```

### 8.8 BrainUserVisibleSummary

Fields:

```text
goal_understood
style_to_keep
references_to_use
new_direction
quality_checks
next_step_hint
```

This is the only LLM reasoning summary that the default UI should show.

---

## 9. LLM Provider Rules

The LLM Brain Adapter may use direct LLM API providers through V3-owned
adapters:

```text
OpenAI-compatible LLM provider
Kimi-compatible provider
other direct LLM API provider explicitly configured in V3 settings
```

It must not call:

```text
Claude Code CLI
Claude Code expert mode
Claude Code provider sidecar
V2 Claude orchestrator
V2 image_service.apply_work_intensity
V2 prompt plan objects
V2 case intelligence runtime
```

Settings may reuse platform-level API keys and base URLs through an explicit V3
configuration adapter, similar to how V3 image generation reuses provider
credentials.

Recommended environment/settings:

```text
V3_LLM_BRAIN_ENABLED=true
V3_LLM_BRAIN_PROVIDER=auto
V3_LLM_BRAIN_MODEL=
V3_LLM_BRAIN_TIMEOUT_SECONDS=45
V3_LLM_BRAIN_MAX_CALLS=2
V3_LLM_BRAIN_FALLBACK=deterministic
V3_LLM_BRAIN_STORE_AUDIT=true
V3_POST_GENERATION_REVIEW_ENABLED=false
```

Forbidden settings:

```text
V3_LLM_BRAIN_PROVIDER=claude_code
V3_LLM_BRAIN_EXPERT_MODE=claude_code
V3_CLAUDE_CODE_BRAIN_ENABLED=true
```

If unset, use the existing global LLM provider settings only through a V3-owned
adapter.

---

## 10. Reasoning Depth Modes

The product should support different reasoning depth without exposing technical
language to beginner users.

Internal modes:

| Mode | LLM Calls | Use Case |
| --- | ---: | --- |
| `off` | 0 | deterministic fallback / tests |
| `balanced` | 1 | default generation |
| `studio` | 2 | stronger prompt refinement |
| `atelier` | 2-3 | high-consistency work, optional post-review |

Beginner UI labels:

```text
快速
标准
精修
高一致性
```

Default should be `standard/balanced`.

The UI must not show:

```text
LLM calls
reasoning tokens
temperature
provider name
model name
```

Those may appear only in an explicit developer/debug view.

---

## 11. Multi-Stage Reasoning

### 11.1 Stage A - Intent And Context

Input:

```text
user_input
project goal
template id
selected output summaries
uploaded reference summaries
negative feedback
brand memory summary
```

Output:

```text
BrainIntentSummary
BrainProjectMemoryDigest
```

User-facing progress:

```text
V3 正在理解这次要做什么
V3 正在整理本项目要沿用的风格
```

### 11.2 Stage B - Image Set Planning

Input:

```text
BrainIntentSummary
BrainProjectMemoryDigest
requested image count
requested size
template rules
```

Output:

```text
BrainImageSetPlan
```

User-facing progress:

```text
V3 正在规划这一组图的画面方向
```

### 11.3 Stage C - Prompt Guidance

Input:

```text
image set plan
shared capability constraints
template rules
provider-neutral prompt requirements
```

Output:

```text
BrainPromptGuidance
```

User-facing progress:

```text
V3 正在优化给生图模型的画面描述
```

### 11.4 Stage D - Prompt Self-Check

Input:

```text
compiled prompt guidance
must keep facts
negative notes
reference rules
```

Output:

```text
BrainPromptReview
```

User-facing progress:

```text
V3 正在检查风格、参考图和画面要求是否冲突
```

### 11.5 Stage E - Optional Post-Generation Review

This stage is optional and may come after the first implementation.

Input:

```text
generated output metadata
thumbnail or preview image if a vision provider exists
BrainRunResult
project context
```

Output:

```text
quality score summary
accept / manual_review / retry recommendation
plain-language issue list
refinement hint
```

User-facing progress:

```text
V3 正在检查生成结果是否适合继续使用
```

---

## 12. Runtime Integration

### 12.1 ScenarioRuntime Integration Point

Modify `ScenarioRuntime.plan_job` and `ScenarioRuntime.generate_job` so the
order becomes:

```text
resolve scenario pack
run shared capabilities
build LLM brain request
run LLM Brain Adapter if enabled
pass brain result into CentralCreativeBrain runtime_metadata
enrich PlanningResult / GenerationResult metadata with safe brain summary
```

Do not call the LLM Brain Adapter from frontend code.

Do not call it from provider adapters.

### 12.2 CentralCreativeBrain Consumption

`CentralCreativeBrain` should read:

```text
runtime_metadata["llm_brain"]
```

It should use the result to enrich:

```text
CommercialBrief
CreativePlan
SeriesPlan
LayoutPlan
PromptCompilationResult
GenerationPlan metadata
EvaluationReport metadata
```

It must not depend on a specific LLM provider.

### 12.3 PromptCompilerAgent Consumption

`PromptCompilerAgent` should consume:

```text
BrainPromptGuidance.visual_direction
BrainPromptGuidance.style_notes
BrainPromptGuidance.layout_notes
BrainPromptGuidance.hard_constraints
BrainPromptGuidance.negative_prompt
BrainPromptReview.final_rewrite_notes
PromptConstraintCompiler constraints
```

Priority order:

```text
1. safety and policy checks
2. explicit user instruction
3. selected project references
4. uploaded reference facts
5. confirmed Brand Memory
6. template rules
7. LLM style enhancement
8. generic commercial polish
```

LLM guidance must never override explicit user instructions silently.

### 12.4 Product API Metadata

The job status should include safe metadata:

```text
llm_brain.enabled
llm_brain.status
llm_brain.fallback_used
llm_brain.user_visible_summary
llm_brain.progress_steps
llm_brain.warning_count
```

Do not expose:

```text
raw LLM request
raw LLM response
hidden reasoning
provider headers
full prompt chain
```

---

## 13. Selected-Output Strong Reference Bridge

The largest consistency gap in the current V3 flow is that selected generated
outputs enter project context, but they are not always passed as real reference
images to the generation provider.

Add a bridge:

```text
selected OutputRef
  -> locate stored V3 output file
  -> create/generated ProjectReferenceAsset
  -> expose file_path in runtime uploaded/reference assets
  -> GenerationProvider receives true reference image input
```

Rules:

1. Only selected outputs may become strong references.
2. Removed or unselected outputs must not be passed.
3. User-uploaded reference images keep their original roles.
4. Generated selected references should use role:

```text
generated_style_reference
generated_identity_reference
generated_composition_reference
```

5. Default role for General Template:

```text
generated_style_reference
```

6. If the file cannot be found, degrade to prompt-only project context.
7. Store this degradation as a warning, not a crash.

This bridge is essential for stronger commercial consistency.

---

## 14. Shared Capability Relationship

The LLM Brain Adapter does not replace shared capabilities.

Shared capabilities remain responsible for:

```text
uploaded asset analysis
reference binding
case retrieval
visual grammar locking
information integrity
prompt constraint compilation
output review hooks
history reference context
```

The LLM Brain Adapter consumes their summarized results.

Example:

```text
AssetBindingPlanner says uploaded asset is a strong style reference.
LLM Brain turns that into beginner-safe creative guidance.
PromptConstraintCompiler turns it into prompt constraints.
PromptCompilerAgent writes provider-neutral prompt text.
GenerationProvider receives actual reference image files.
```

Capability-specific logic must not be moved into the LLM Brain Adapter.

---

## 15. Frontend Requirements

The frontend must keep the current single production entry.

Do not add new required user steps.

### 15.1 Progress Bar

The progress bar should show compact steps:

```text
理解需求
整理参考
规划画面
优化描述
生成图片
检查结果
```

These steps map to backend events/metadata but must remain plain-language.

### 15.2 Optional Details

Add or reuse a folded "V3 做了什么" section.

Show:

```text
这次要做的目标
沿用的风格
参考了哪些已选图
避开了哪些方向
优化后的画面方向
简单质量检查
```

Do not show by default:

```text
raw prompt
provider
job id
scenario runtime
capability module names
LLM provider
model
tokens
chain-of-thought
```

If an advanced prompt view already exists, it may show:

```text
final provider prompt
compiled visual direction
style notes
layout notes
hard constraints
```

It must still avoid hidden reasoning.

---

## 16. Implementation Phases

### Phase 0 - Documentation And Guardrails

1. Add this document.
2. Confirm it does not supersede documents `32` through `47`.
3. Add test expectations for no V2 runtime imports.
4. Add settings names but keep default disabled until implementation is ready.

Exit criteria:

```text
docs exist
no old document conflict
no code behavior change
```

### Phase 1 - Contracts And Deterministic Fallback

Add:

```text
app/llm_brain/contracts.py
app/llm_brain/fallback.py
app/llm_brain/context_digest.py
```

Implement:

```text
BrainRunRequest
BrainRunResult
BrainIntentSummary
BrainProjectMemoryDigest
BrainImageSetPlan
BrainPromptGuidance
BrainPromptReview
BrainUserVisibleSummary
```

The fallback result should mimic current deterministic behavior and include:

```text
status=fallback
fallback_used=true
user_visible_summary
no provider call
```

Tests:

```text
contract serialization
fallback result shape
no chain_of_thought field
selected-only context digest
negative feedback included
```

### Phase 2 - LLM Provider Adapter

Add:

```text
app/llm_brain/providers.py
app/llm_brain/prompts.py
app/llm_brain/adapter.py
```

Implement provider-neutral JSON calls.

Minimum provider behavior:

```text
OpenAI-compatible JSON response
Anthropic-compatible JSON response
timeout
fallback
safe error summary
no API key leakage
```

Tests:

```text
mock provider returns structured JSON
malformed JSON falls back safely
provider timeout falls back safely
disabled settings return deterministic fallback
```

### Phase 3 - ScenarioRuntime Integration

Modify `ScenarioRuntime`:

```text
run shared capabilities
build BrainRunRequest
run V3LLMBrainAdapter
attach safe BrainRunResult to runtime_metadata
```

Modify `PlanningResult` / `ProductJobStatus` metadata:

```text
llm_brain.enabled
llm_brain.status
llm_brain.fallback_used
llm_brain.user_visible_summary
llm_brain.progress_steps
```

Tests:

```text
general template job includes llm_brain metadata when enabled
general template job falls back when no provider configured
placeholder templates do not call LLM
required shared capability failure blocks before LLM
project_id stays present
```

### Phase 4 - CentralCreativeBrain Consumption

Modify:

```text
creative_core/central_brain.py
agents/commercial_strategy_agent.py
agents/creative_director_agent.py
agents/series_planner_agent.py
agents/prompt_compiler_agent.py
```

Use LLM guidance as structured enrichment.

Do not replace deterministic agents.

Tests:

```text
LLM visual direction appears in PromptCompilationResult
LLM style notes merge with project style chips
LLM negative prompt merges without duplication
explicit user instruction wins over generic LLM enhancement
metadata records brain_run_id
```

### Phase 5 - Prompt Self-Check

Implement `BrainPromptReview`.

Before provider generation:

```text
compile draft prompt
run prompt self-check
if pass: continue
if revise: apply final_rewrite_notes once
if fallback: use deterministic prompt
if block: block job with user-safe warning
```

Tests:

```text
no unsupported exclusions are added
exact user facts remain present
negative feedback remains present
selected reference rule remains present
block returns user-safe warning
```

### Phase 6 - Selected-Output Strong Reference Bridge

Modify project/reference pipeline:

```text
selected generated outputs with files become generated reference assets
generated reference assets are included in runtime uploaded/reference assets
provider receives real file_path when available
```

Tests:

```text
selected output is passed as reference
unselected output is not passed
removed selected output is not passed
missing file degrades to prompt-only warning
reference count appears in provider metadata
```

### Phase 7 - Optional Post-Generation Review

Start with metadata-based review.

Later, add vision model review behind:

```text
V3_POST_GENERATION_REVIEW_ENABLED=true
```

Review should produce:

```text
plain quality notes
consistency score
commercial usefulness score
retry recommendation
```

Tests:

```text
review metadata exists
low score can mark manual_review
critical failure can request retry
review never deletes generated output
```

### Phase 8 - Frontend Product Display

Update V3 frontend:

```text
progress bar consumes llm_brain progress steps
folded workflow details show user_visible_summary
advanced details may show final prompt
default UI remains image-first
no engineering language appears in normal view
```

Tests:

```text
progress labels exist
workflow summary is folded/compact
default UI does not show provider/model/job id/capability names
generated images remain primary
mobile layout remains readable
```

---

## 17. API / Metadata Additions

No new public API is required in the first implementation.

Existing project/job endpoints may return additional metadata:

```json
{
  "metadata": {
    "llm_brain": {
      "enabled": true,
      "status": "complete",
      "fallback_used": false,
      "user_visible_summary": {
        "goal_understood": "...",
        "style_to_keep": ["..."],
        "references_to_use": ["..."],
        "new_direction": "...",
        "quality_checks": ["..."]
      },
      "progress_steps": [
        {"label": "理解需求", "status": "done"},
        {"label": "整理参考", "status": "done"},
        {"label": "规划画面", "status": "done"},
        {"label": "优化描述", "status": "done"}
      ]
    }
  }
}
```

If the metadata becomes too large, add:

```text
GET /api/v3/creative-agent/projects/{project_id}/jobs/{job_id}/brain-summary
```

Do not add this endpoint until necessary.

---

## 18. Safety And Privacy

Rules:

1. Never store API keys in brain metadata.
2. Never expose raw LLM response to default UI.
3. Never store chain-of-thought.
4. Store only structured decisions and concise summaries.
5. Keep user-uploaded assets scoped to the project/user.
6. Do not send unrelated project history to the LLM.
7. Do not send unselected candidate images as positive references.
8. Respect explicit user negative feedback.
9. LLM output cannot create unsupported product claims.
10. LLM output cannot silently change the selected template.

---

## 19. Commercial Consistency Requirements

To approach Lovart-like consistency, the implementation must improve three
levels:

### 19.1 Style Consistency

Achieved through:

```text
ProjectContextPackage
selected outputs
Brand Memory
BrainProjectMemoryDigest
style notes
prompt self-check
```

### 19.2 Composition Consistency

Achieved through:

```text
selected reference output analysis
VisualGrammarLockModule
BrainImageSetPlan
layout notes
strong reference bridge when file exists
```

### 19.3 Subject / Identity Consistency

Achieved through:

```text
strong reference bridge
generated_identity_reference role when user chooses identity lock
provider reference images
post-generation review
manual selection feedback
```

Current V3 already has style continuity. The key upgrade is subject/identity
continuity through real reference images and review.

---

## 20. Non-Goals

This phase does not:

```text
rewrite Project Mode
rewrite frontend project structure
rewrite Product API
rewrite Scenario Pack Registry
activate future templates
replace GPT image 2 provider
add a Lovart-style infinite canvas
add layer-based design editing
add automatic Brand Memory overwrite
import V1/V2 runtime modules
copy V2 Claude orchestration code
```

---

## 21. Test Plan

### 21.1 Unit Tests

Add tests for:

```text
BrainRunRequest serialization
BrainRunResult serialization
context digest selected-only rule
negative feedback digest
fallback behavior
provider JSON parsing
prompt review status handling
safe metadata redaction
```

### 21.2 Runtime Tests

Add tests for:

```text
ScenarioRuntime attaches llm_brain metadata
CentralCreativeBrain consumes llm_brain guidance
PromptCompilerAgent merges LLM guidance
GenerationRouter still receives V3 standard GenerationRequest
shared capability failure blocks before LLM
LLM fallback does not block generation
```

### 21.3 Project Mode Tests

Add tests for:

```text
project continuation includes ProjectContextPackage in BrainRunRequest
selected output appears in brain digest
unselected output does not appear in brain digest
removed selected output does not appear
Brand Memory is read but not updated
project_id remains on every job
```

### 21.4 Strong Reference Tests

Add tests for:

```text
selected output file becomes generated reference asset
generated reference asset includes file_path
provider metadata records reference count
missing selected output file degrades safely
```

### 21.5 Frontend Tests

Add tests for:

```text
progress bar can render LLM brain steps
workflow details can render user_visible_summary
normal UI hides engineering terms
image board remains primary
mobile layout does not overflow
```

### 21.6 Suggested Commands

```powershell
python -m pytest alchemy_creative_agent_3_0\tests\test_v3_foundation_guardrails.py -q
python -m pytest alchemy_creative_agent_3_0\tests\test_v3_shared_capability_runtime_integration.py -q
python -m pytest alchemy_creative_agent_3_0\tests\test_v3_project_mode.py -q
python -m pytest tests\test_v3_commercial_frontend_shell.py -q
python -m compileall -q alchemy_creative_agent_3_0 src_skeleton
node --check src_skeleton\app\static\app.js
node --check src_skeleton\app\mobile_static\mobile.js
git diff --check
```

---

## 22. Acceptance Criteria

The phase is complete only when:

```text
V3 can generate through existing project flow with LLM Brain enabled
V3 can generate through existing project flow with LLM Brain disabled
general creative template is the first enabled template
ecommerce activation is not controlled by this document; use Document 42 and
the template registry for activation state
LLM Brain uses ProjectContextPackage
LLM Brain respects selected-only positive context
LLM Brain produces user-visible summaries
PromptCompilerAgent consumes LLM guidance
final provider prompt is better than deterministic prompt
selected generated outputs can become strong references when files exist
no V1/V2 runtime import is introduced
normal UI remains beginner-friendly
tests pass
```

Commercial quality acceptance:

```text
same project continuation should preserve style more strongly than current V3
selected reference images should visibly influence new generations
prompt output should be less generic and less template-like
new images should not overwrite old project images
user can understand what V3 did without seeing engineering details
```

---

## 23. Developer Checklist

Before coding:

```text
read documents 02, 03, 11, 24, 32, 34, 36, 43, 47, and this document
confirm current worktree status
confirm no V1/V2 runtime import is needed
confirm LLM provider credentials are accessed through V3-safe adapter
confirm default fallback path works
```

During coding:

```text
add contracts first
add fallback second
add provider adapter third
add ScenarioRuntime integration fourth
add CentralCreativeBrain consumption fifth
add prompt review sixth
add strong reference bridge seventh
add frontend progress/summary last
```

After coding:

```text
run unit tests
run project mode tests
run frontend shell tests
run compile checks
manually generate one project image set
continue the same project with selected references
inspect final_provider_prompt and user_visible_summary
verify old images are not overwritten
verify selected references improve consistency
```

---

## 24. Final Product Meaning

After this phase, V3 should no longer feel like:

```text
a project UI wrapped around a deterministic prompt compiler
```

It should feel like:

```text
a project-based creative operating system where an LLM creative director reads
the project, understands the user's next sentence, preserves the chosen visual
direction, and prepares a stronger image generation plan automatically
```

The frontend remains simple.

The backend becomes much smarter.
