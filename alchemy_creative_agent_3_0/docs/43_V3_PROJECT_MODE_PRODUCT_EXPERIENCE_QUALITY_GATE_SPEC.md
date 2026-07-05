# 43 V3 Project Mode Product Experience Quality Gate Spec

Current compatibility note:

```text
Document 52 extends this quality gate for the next implementation phase.
Future acceptance must verify not only backend planning/generation, but also
real output file resolution, post-generation visual inspection, append-only
automatic retry, suite variation usefulness, output curation, and
beginner-friendly quality summaries.
```

This document defines the product-level quality gate for all V3 Project Mode
implementation after documents 32-42.

It exists because V3 must satisfy four requirements at the same time:

```text
fit the overall V3 architecture
remain beginner-friendly
feel functionally complete
prioritize images while still showing high-value plain-language work results
```

No future V3 Project Mode phase should be accepted if it only passes backend
tests but fails this product experience gate.

## 1. Relationship To Existing Docs

This document does not replace documents 32-42.

It audits them from the user's point of view.

Use it as a final checklist for:

```text
38 Project Workspace Continuation UX
39 Project Context Asset And Feedback Persistence
40 Project To Brand Memory Confirmation
41 Template Manifest Registry And Activation Gate
42 E-Commerce Template Project Mode Unfreeze
all later templates
```

## 2. Gate A: Architecture Fit

Every feature must preserve the accepted V3 architecture:

```text
V3 Foundation
  -> Project
      -> Template
          -> Scenario Pack
              -> Job
```

Required rules:

```text
Project wraps Job; it does not replace Job.
Template wraps Scenario Pack; it does not create a parallel runtime.
Project detail opens before template work.
Project jobs always include project_id.
Selected outputs and active references build project context.
Unselected outputs stay as history only.
Brand Memory is updated only after explicit confirmation.
V3 does not import V1/V2/Lab runtime state.
E-Commerce stays locked until the unfreeze gate is accepted.
```

Architecture failure examples:

```text
frontend creates a standalone job outside project
ecommerce template bypasses template registry
project continuation reads all generated candidates as positive references
Brand Memory updates automatically after generation
V3 UI reads V1/V2 history state directly
```

## 3. Gate B: Beginner-Friendly Experience

The normal UI must be understandable to a user who knows nothing about code,
providers, prompts, model parameters, or workflow systems.

Allowed default language:

```text
这次生成了什么
为什么这些图适合继续
后续会参考哪些图
接下来可以做什么
哪里需要你检查
```

Forbidden default language:

```text
provider
job id
asset ref
manifest
context package
prompt compiler
scenario runtime
capability module
workflow graph
raw prompt chain
```

Advanced or debug information may exist only behind an explicit future advanced
mode. The default product must not feel like an engineering console.

## 4. Gate C: Functional Completeness

Each accepted Project Mode workspace must support the full loop expected for its
current phase.

Minimum loop for General Template:

```text
create project
open project
generate first images
show generated images
select useful image
persist selected reference
continue same style
upload new reference and continue
mark unwanted direction
see project timeline
return later and continue
download useful output
```

Minimum loop for future E-Commerce Template:

```text
create or open product project
upload product image
enter one-sentence request
choose suite scope
generate visible suite images
show slot labels
select useful images
continue one slot or same style
record avoid feedback
export selected outputs
return later and continue with product context
```

If a phase intentionally does not implement one item, the UI must mark it as
locked or planned. It must not show a clickable control that appears functional
but does nothing.

## 5. Gate D: Image-First, High-Value Content Second

Images are the main deliverable. The UI must visually prioritize generated and
selected images.

Required image-first rules:

```text
project cards show meaningful image thumbnails when available
project detail shows output board above long text
selected references use image tiles
generated image previews must replace placeholders when URLs exist
download/open actions are close to each image
empty states should not dominate once images exist
```

Text is still valuable, but it must be concise and useful.

Required high-value content blocks:

```text
project goal summary
confirmed visual direction
useful references explanation
this run summary
user-facing workflow progress
next action suggestions
simple quality/check notes
timeline of meaningful project events
```

Do not show long internal reasoning. Do not show chain-of-thought. Show the
result of V3's work in plain language.

## 6. User-Facing Workflow Layer

The product should show a workflow, but not an engineering workflow graph.

The user-facing workflow answers:

```text
V3 做了哪几步？
每一步产出了什么有用信息？
这些信息如何帮助下一次生成？
用户下一步应该怎么选？
```

Recommended workflow cards:

```text
理解需求
  已确认这次要做的目标和用途

整理参考
  已记录后续会参考的图片和风格

生成图片
  已生成可选择的结果

筛选方向
  选中的图片会进入后续参考，不喜欢的方向会被避开

继续优化
  可以保持同风格继续生成，也可以上传新参考继续
```

For E-Commerce later:

```text
识别产品
  提取产品外观重点和必须保持的信息

匹配卖点
  把产品卖点转成适合图片表达的方向

规划套图
  自动拆成主图、卖点图、场景图、细节图等位置

生成套图
  输出可直接挑选和下载的图片

检查发布
  提醒用户检查产品细节、文案空间和平台适配
```

These cards should be collapsible or compact. They should help users trust the
system without overwhelming them.

## 7. Project Detail Minimum Valuable Content

Every project detail page must show these blocks when data exists:

```text
1. project title and goal
2. large generated/selected images
3. useful references
4. confirmed style or direction
5. this run summary
6. simple workflow progress
7. next action buttons
8. timeline
```

The order should favor images:

```text
header
primary image/output board
next actions
useful summaries
timeline
```

On mobile, images and next actions must appear before dense summaries.

## 8. Template Requirements

Every template manifest must define:

```text
image_priority_policy
user_visible_workflow_steps
plain_summary_policy
required_beginner_actions
hidden_debug_fields
quality_check_notes
```

General Template example:

```text
image_priority_policy:
  output board first after generation

user_visible_workflow_steps:
  understand need
  collect references
  generate images
  select direction
  continue

plain_summary_policy:
  say what was generated, what style was used, and what can be done next
```

E-Commerce Template example:

```text
image_priority_policy:
  product image and generated suite slots are primary

user_visible_workflow_steps:
  identify product
  map selling points
  plan suite
  generate images
  check and export

plain_summary_policy:
  explain slot count, slot purpose, selling point, and publish checks
```

## 9. UI Audit Checklist

Before accepting frontend work, verify:

```text
home is project-first
project cards show image thumbnails when possible
project detail is not a developer dashboard
generated images are visible without opening debug panels
selected images are visually distinct
next actions are obvious
workflow summary is plain and compact
timeline is meaningful and clickable
engineering labels are hidden
locked templates cannot create jobs
mobile order still prioritizes images and actions
```

## 10. Backend Audit Checklist

Before accepting backend work, verify:

```text
project_id is required for project jobs
selected outputs are persisted as positive references
uploaded project references persist after refresh
unselected outputs are excluded from positive context
negative feedback can enter future context
timeline events have user-facing summaries
context builder can produce a plain project summary
template gate blocks locked templates
Brand Memory writes require explicit confirmation
V3 does not touch V1/V2/Lab runtime state
```

## 11. Tests Required By This Gate

Frontend tests:

```text
test_v3_home_project_cards_prioritize_images
test_project_detail_shows_output_board_before_dense_text
test_project_detail_shows_plain_workflow_progress
test_project_detail_hides_engineering_labels
test_selected_reference_board_uses_image_tiles
test_locked_template_control_is_non_executing
test_mobile_project_detail_keeps_images_and_actions_first
```

Backend tests:

```text
test_project_job_requires_project_id
test_selected_output_enters_positive_context
test_unselected_output_excluded_from_positive_context
test_rejected_direction_enters_negative_context
test_timeline_events_include_plain_user_summary
test_template_gate_blocks_locked_template
test_brand_memory_write_requires_confirmation
```

Manual QA:

```text
1. Create a project with one sentence.
2. Generate images.
3. Confirm images are the visual focus.
4. Read the page as a non-technical user.
5. Select one image.
6. Continue the project.
7. Confirm the new result follows selected context.
8. Reject one direction.
9. Confirm the next job avoids it.
10. Return to home and reopen the project.
11. Confirm the project still makes sense without debug knowledge.
```

## 12. Acceptance Criteria

A V3 Project Mode phase passes this product quality gate when:

```text
1. It preserves the accepted architecture.
2. It is understandable to beginners.
3. It supports the complete loop promised by that phase.
4. Images are the main visual focus.
5. High-value summaries and workflow progress are visible in plain language.
6. Engineering details are hidden from normal users.
7. Locked or future functionality cannot be accidentally executed.
8. Tests and manual QA cover the four product requirements.
```
