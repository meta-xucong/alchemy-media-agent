# 42 V3 E-Commerce Template Project Mode Unfreeze Spec

This document defines how to unfreeze the E-Commerce Template after Project Mode
and General Template continuation are stable.

Current authority note:

```text
Document 57 extends this document for three ecommerce/commercial quality
corrections: lifestyle images must become more real-world/in-use when the slot
requires lifestyle, ecommerce generation must respect the same requested image
count control as the V3 workbench, and faint watermark/signature/corner-mark
artifacts must be treated as commercial QA issues.
```

It must not be implemented before documents 38, 39, 41, and 43 are accepted. It
is recommended to implement document 40 first if cross-project brand consistency
is needed for E-Commerce.

## 1. Purpose

The E-Commerce Template turns:

```text
product image + simple user instruction
```

into:

```text
a mature, commercially usable e-commerce image suite
```

The user should not need to write professional prompts, understand ad strategy,
or manually choose image recipes.

## 2. Relationship To Existing V3

The E-Commerce Template must run inside Project Mode:

```text
Project
  -> ecommerce_template
      -> ecommerce Scenario Pack
          -> project jobs
          -> selected outputs
          -> project context
          -> export
```

It must not revive standalone E-Commerce job flows that bypass Project Mode.

## 3. Preconditions

Before activating E-Commerce:

```text
1. Project detail continuation UX is complete.
2. Project references and feedback persist correctly.
3. Template registry and activation gate exist.
4. Document 43 product experience quality gate passes.
5. E-Commerce template is still locked by backend.
6. General Template tests still pass.
7. Project jobs require project_id.
8. Output previews and downloads work.
```

## 4. User-Facing Promise

Beginner-facing promise:

```text
上传产品图，说一句想要什么，V3 自动生成可用于电商的套图。
```

Do not promise:

```text
guaranteed platform approval
guaranteed sales increase
perfect product geometry preservation without review
```

## 5. Required Inputs

Minimum beginner inputs:

```text
product image
one-sentence request
target platform or usage scene
```

Recommended optional inputs:

```text
product category
target market
main selling point
price range
target audience
brand style
competitor/reference images
keywords
must-keep product facts
```

Advanced inputs should be hidden under:

```text
更多设置
```

## 6. E-Commerce Project Profile

Add a project-scoped commerce profile.

Required fields:

```text
project_id: string
product_name: string | null
product_category: string | null
target_platform: string | null
target_market: string | null
price_positioning: string | null
target_audience: string | null
core_selling_points: list[string]
must_keep_facts: list[string]
avoid_claims: list[string]
keyword_roots: list[string]
keywords: list[string]
competitor_notes: list[string]
suite_slots_requested: list[string]
```

Rules:

```text
Product facts must come from user input, uploaded materials, or explicit analysis.
Do not invent specifications.
If unsure, ask or mark as unknown.
```

## 7. Agent Reasoning Stages

The central brain should run these stages internally:

```text
1. Product Truth Extraction
2. Market Intent Mapping
3. Audience And Pain Point Mapping
4. Selling Point Prioritization
5. Visual Suite Strategy
6. Slot Recipe Planning
7. Prompt And Constraint Compilation
8. Generation
9. Commercial QA
10. Selection And Continuation
11. Export Summary
```

Only the useful outcome is shown to users.

## 8. Product Truth Extraction

Inputs:

```text
uploaded product image
user product description
optional specification sheet
optional existing listing text
```

Outputs:

```text
visible product attributes
confirmed product facts
unknown facts
must-not-change areas
```

Beginner-facing display:

```text
V3 已识别的产品重点
需要保持不变的地方
还不确定的信息
```

## 9. Market Intent Mapping

The agent should map:

```text
who buys this
why they buy this
what they worry about
what scene makes the product desirable
what proof increases trust
```

Do not expose long research tables in default UI.

Show only:

```text
本次套图重点
适合突出的人群/场景
建议强化的卖点
```

## 10. Visual Suite Slots

Default suite slots:

```text
main_image
feature_highlight
usage_scene
detail_proof
comparison_or_trust
social_cover
```

Slot definitions:

```text
main_image:
  clean product-first image, clear subject, platform-safe

feature_highlight:
  one key selling point, enough room for text overlay if needed

usage_scene:
  product in realistic target use case

detail_proof:
  material, structure, capacity, texture, or functional proof

comparison_or_trust:
  quality, before/after, packaging, certificate, or trust cue when truthful

social_cover:
  higher-impact image for social commerce, ads, or campaign cover
```

Users may choose:

```text
一键生成完整套图
只生成主图
只生成场景图
继续补一张同风格图
```

## 11. Recipe Contract

Each slot recipe must include:

```text
slot_id
slot_goal
target_audience_need
selling_point
visual_scene
composition
product_integrity_constraints
copy_space_instruction
style_reference_policy
negative_constraints
expected_output_summary
```

Rules:

```text
product_integrity_constraints outrank decorative style.
selling_point must connect to a user need.
copy_space must be planned if the image is likely to need text.
```

## 12. Context Policy

E-Commerce reads:

```text
project goal
commerce project profile
selected outputs
active uploaded product/reference images
negative feedback
explicitly selected Brand Memory if available
```

E-Commerce writes:

```text
commerce profile updates
slot recipes
generated suite outputs
selected output states
project timeline events
export manifest
```

E-Commerce must not write:

```text
Brand Memory without confirmation
V1/V2/Lab state
General Template-specific fields
```

## 13. Product Integrity Rules

Mandatory:

```text
Do not change core product shape intentionally.
Do not invent labels, certificates, materials, capacities, or technical claims.
Do not add unsafe platform claims.
Do not hide product defects unless user explicitly asks for retouching and policy allows.
Do not imply certification without proof.
```

When the model may alter product details, show a warning:

```text
请检查产品细节是否与实物一致。
```

## 14. Frontend Workspace

E-Commerce workspace must be visually different from General Template.

Required sections:

```text
product image area
product facts summary
suite slot selector
one-sentence request composer
selling point suggestions
generated suite board
slot-by-slot timeline
export actions
```

Beginner-facing labels:

```text
产品图
这次要做什么
套图类型
主打卖点
已生成套图
继续补图
导出图片
```

Do not show:

```text
workflow graph
prompt chain
provider parameters
manifest JSON
RUFUS tables by default
```

## 15. API Plan

Use project template job API as the main entry:

```text
POST /api/v3/creative-agent/projects/{project_id}/jobs
```

Required request fields:

```text
template_id: ecommerce_template
user_instruction
input_asset_refs
commerce_profile_patch
suite_slot_request
```

Recommended supporting endpoints:

```text
GET /api/v3/creative-agent/projects/{project_id}/ecommerce/profile
PATCH /api/v3/creative-agent/projects/{project_id}/ecommerce/profile
POST /api/v3/creative-agent/projects/{project_id}/ecommerce/suite
GET /api/v3/creative-agent/projects/{project_id}/ecommerce/export
```

If fewer endpoints are preferred, keep the profile under generic project
template fields but preserve the same data contract.

## 16. Output Summary

Each generated suite should summarize:

```text
generated slot count
slot purpose
main selling point used
what to check before publishing
which image is recommended first
```

Example:

```text
本次生成了 6 张电商图：主图、功能卖点图、使用场景图、细节图、信任感图和社媒封面。建议先检查产品外观细节是否与实物一致，再选择最适合上架的版本。
```

## 17. Export Requirements

Minimum export:

```text
download individual images
download selected images
plain summary of each slot
project timeline remains available
```

Later export:

```text
zip package
platform-specific naming
listing copy pairing
thumbnail contact sheet
```

## 18. Implementation Order

Recommended sequence:

```text
1. Keep ecommerce_template locked.
2. Add commerce project profile schema.
3. Add E-Commerce manifest in template registry with status locked.
4. Add backend validation for commerce inputs.
5. Add slot recipe planner using existing E-Commerce Scenario Pack logic.
6. Adapt E-Commerce generation to require project_id.
7. Add E-Commerce workspace UI behind locked feature flag.
8. Add tests while template remains locked.
9. Switch status to active only after tests pass.
10. Run manual QA on real product image.
```

## 19. Required Tests

Backend:

```text
test_ecommerce_template_locked_until_activation
test_ecommerce_job_requires_project_id
test_ecommerce_job_requires_product_image_or_product_reference
test_commerce_profile_defaults_unknown_fields
test_slot_recipe_contains_product_integrity_constraints
test_selected_ecommerce_output_enters_project_context
test_unselected_ecommerce_output_does_not_enter_context
test_ecommerce_does_not_write_brand_memory_without_confirmation
test_general_template_does_not_load_ecommerce_profile
```

Frontend:

```text
ecommerce workspace differs from general workspace
beginner can upload product image and one sentence
suite slot selector is visible
advanced fields are hidden by default
locked state blocks generation before activation
active state generates project job after activation
generated suite shows slot labels and images
```

Manual QA:

```text
use a real product image
generate a six-slot suite
select one image
continue same style for one slot
reject one wrong direction
confirm future context follows selected image and avoids rejected direction
```

## 20. Activation Acceptance Criteria

E-Commerce may be unfrozen only when:

```text
1. Template registry marks ecommerce_template active.
2. Backend and frontend both enforce project_id.
3. Product image/reference upload works.
4. E-Commerce workspace is beginner-facing and distinct from General Template.
5. E-Commerce produces visible generated images.
6. Suite slots are labeled and useful.
7. Selected outputs affect future E-Commerce continuation.
8. General Template remains policy-neutral.
9. Brand Memory is not updated without explicit confirmation.
10. Full V3 tests and focused E-Commerce tests pass.
11. Document 43 product experience quality gate passes for the E-Commerce workspace.
```
