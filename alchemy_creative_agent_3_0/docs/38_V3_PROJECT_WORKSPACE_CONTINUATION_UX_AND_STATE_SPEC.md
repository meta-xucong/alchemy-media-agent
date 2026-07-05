# 38 V3 Project Workspace Continuation UX And State Spec

This document is the next implementation specification after documents 32-37.

It turns the accepted Project Mode idea into a concrete project workspace
experience: users open a project, see what has already been decided, continue
the same visual direction, upload new references, select useful outputs, reject
wrong directions, and keep working without seeing engineering concepts.

## 1. Scope

This document covers the next frontend and interaction layer only.

It must be implemented after:

```text
32_V3_PROJECT_MODE_CORE_CONTROL_SPEC.md
33_V3_PROJECT_MODE_COMPATIBILITY_AND_MIGRATION_SPEC.md
34_V3_PROJECT_CONTRACT_AND_CONTEXT_SPEC.md
35_V3_PROJECT_FIRST_FRONTEND_UX_SPEC.md
36_V3_GENERAL_TEMPLATE_PROJECT_FLOW_SPEC.md
37_V3_TEMPLATE_INTERFACE_AND_AUDIT_SPEC.md
```

It must be implemented before:

```text
40_V3_PROJECT_TO_BRAND_MEMORY_CONFIRMATION_SPEC.md
42_V3_ECOMMERCE_TEMPLATE_PROJECT_MODE_UNFREEZE_SPEC.md
```

## 2. Non-Goals

Do not activate E-Commerce generation in this phase.

Do not write to Brand Memory automatically in this phase.

Do not replace ScenarioRuntime, ScenarioPack, ProductJobRecord, provider
contracts, V3 upload store, or existing project APIs.

Do not make a professional design workstation. The interface must remain
beginner-facing.

## 3. Product Principle

The project detail page is the user's living design room.

The user should understand:

```text
What this project is trying to make.
Which visual direction has been confirmed.
Which images are useful references.
What V3 generated before.
What the user can do next.
```

The user must not need to understand:

```text
job id
provider
scenario runtime
manifest
prompt compiler
capability module
context package
asset ref
```

## 4. Target User Mental Model

The ideal beginner-facing mental model is:

```text
Project = one design task that can keep improving.
Selected images = the style examples V3 should keep following.
Rejected directions = looks V3 should avoid next time.
New generation = one more attempt inside the same project.
Timeline = what has happened in this project.
```

## 5. Information Architecture

The V3 home remains project-first:

```text
V3 Home
  create project
  project cards
  recent project history
```

Clicking a project opens:

```text
Project Detail Workspace
  project header
  project goal summary
  confirmed visual direction
  useful references
  continuation actions
  output board
  project timeline
  template cards
```

Template cards live inside the project detail page. They must not create
standalone jobs outside a project.

## 6. Project Detail Layout

Desktop layout:

```text
┌──────────────────────────────────────────────────────────────┐
│ Project Header                                                │
│ title, plain-language status, last updated                    │
├──────────────────────────────────────┬───────────────────────┤
│ Main Workspace                       │ Side Panel            │
│                                      │                       │
│ Project Goal                         │ Useful References     │
│ Confirmed Direction                  │                       │
│ Continuation Actions                 │ Timeline              │
│ Output Board                         │                       │
│                                      │                       │
└──────────────────────────────────────┴───────────────────────┘
```

Mobile layout:

```text
Project Header
Project Goal
Continuation Actions
Output Board
Useful References
Timeline
Template Cards
```

No nested cards inside cards. Use section bands, compact panels, and image
tiles.

## 7. Required Frontend Sections

### 7.1 Project Header

The header must show:

```text
project title
one-line purpose summary
last meaningful activity
project status
```

Allowed copy examples:

```text
正在为你延续这组视觉方向
已选 2 张作为后续参考
上次生成了 4 张图，可继续优化
```

Forbidden copy examples:

```text
project_id
job_id
scenario_pack
provider_status
context_builder
```

### 7.2 Project Goal Summary

The goal summary must explain the current project in plain language.

It should be derived from:

```text
ProjectRecord.title
ProjectRecord.user_goal
ProjectMemorySummary
latest selected output summary
```

It should show at most:

```text
1 short title
2 short sentences
3 small tags
```

Example:

```text
目标: 做一组清爽、明亮、适合社媒发布的夏季饮品宣传图
方向: 干净背景、自然光、突出饮品颜色和新鲜感
```

### 7.3 Confirmed Visual Direction

This panel summarizes what V3 should preserve.

It must show only confirmed or selected information.

Sources:

```text
selected outputs
accepted project summary
explicit user instruction
uploaded references marked as useful
```

Do not infer strong style commitments from unselected candidates.

Suggested fields:

```text
Style: clean, bright, commercial, fresh
Composition: product centered, clear background, room for text
Color: light green, white, soft yellow
Avoid: dark lighting, cluttered table, excessive illustration
```

Beginner-facing Chinese labels:

```text
已确认风格
画面重点
适合继续参考
后续尽量避免
```

### 7.4 Useful References Board

The useful references board shows images that can influence future jobs.

It must include:

```text
selected generated outputs
uploaded references marked useful
optional product/reference images saved to the project
```

Each tile must show:

```text
image preview
short reason label
selected/useful status
open detail action
remove from future reference action
```

Allowed labels:

```text
继续参考
适合这个项目
只作为历史保留
不再参考
```

Do not show raw asset paths or storage identifiers.

### 7.5 Continuation Action Rail

The continuation action rail is the primary action surface.

Required actions:

```text
继续同风格生成
上传新参考继续
重新生成一轮
换一个方向试试
```

Only `继续同风格生成` and `上传新参考继续` are required for the next code phase.

`换一个方向试试` may create a new job inside the same project, but it must not
overwrite confirmed references. It should add an instruction that this is an
alternative attempt.

### 7.6 Continuation Composer

When the user clicks a continuation action, show a small composer.

The composer asks one simple question:

```text
这次想继续做什么？
```

It may provide examples:

```text
保持这个风格，再做一张横版海报
继续这个清爽感觉，突出新品优惠
换成小红书封面比例
参考我新传的图片继续
```

Required fields:

```text
instruction text
optional upload references
output count selector
aspect ratio selector
generate button
```

Advanced parameters must be hidden.

### 7.7 Output Board

The output board shows generated images for the current and previous project
jobs.

Each output tile must expose beginner-facing actions:

```text
选为后续参考
不参考这张
下载
放大查看
继续按这张做
```

Optional but recommended:

```text
这张适合什么
V3 做了哪些调整
```

Do not show provider metadata unless a hidden debug mode is explicitly active.

### 7.8 Output Detail Drawer

Clicking an image opens a drawer or modal.

Required visible information:

```text
large image preview
why this image may be useful
what it can be used for
simple generation summary
selection state
actions
```

Forbidden visible information:

```text
raw prompt
seed
provider
job id
asset id
capability logs
```

Raw prompt can exist only behind a future advanced/export mode.

### 7.9 Negative Feedback Modal

When the user clicks `不参考这张` or `不要这种方向`, ask one simple optional
question:

```text
你不想继续哪一点？
```

Suggested chips:

```text
太暗
太乱
不像产品图
风格太卡通
文字空间不够
主体不清楚
```

The modal must create project feedback, not delete the image.

### 7.10 Project Timeline

Timeline items must be written in plain language.

Examples:

```text
新建了项目
上传了 2 张参考图
生成了 4 张图
选中了 1 张作为后续参考
标记了 1 个不想继续的方向
```

Clicking a timeline item should open:

```text
related images
short user instruction
plain output summary
selection/feedback state
```

Do not show internal event names.

## 8. Workspace State Model

The frontend should model project detail state explicitly.

```text
empty_project
ready_for_first_generation
generating
generated_waiting_for_selection
has_selected_reference
has_negative_feedback
continuation_ready
locked_template_selected
error_recoverable
```

### 8.1 empty_project

Condition:

```text
project exists
no jobs
no selected outputs
no uploaded references
```

Primary CTA:

```text
开始生成第一组图
```

### 8.2 ready_for_first_generation

Condition:

```text
project has goal
general template active
```

Primary CTA:

```text
用通用模板生成
```

### 8.3 generating

Condition:

```text
job submitted
job not terminal
```

Visible copy:

```text
正在为这个项目生成新图片
```

Poll project timeline and latest job.

### 8.4 generated_waiting_for_selection

Condition:

```text
latest job has outputs
no output selected from latest job
```

Primary prompt:

```text
选择你希望后续继续参考的图片
```

### 8.5 has_selected_reference

Condition:

```text
project has one or more selected outputs
```

Primary CTA:

```text
继续同风格生成
```

### 8.6 has_negative_feedback

Condition:

```text
project has active avoid notes
```

Show the avoid notes in the confirmed direction panel with user-friendly copy.

### 8.7 locked_template_selected

Condition:

```text
user clicks ecommerce or future template while locked
```

Show:

```text
这个模板还在准备中。当前可先用通用模板继续做图。
```

Do not create a job.

## 9. Required User Flows

### 9.1 Open Existing Project

Steps:

```text
1. User opens V3 home.
2. User clicks a project card.
3. Frontend calls project detail API.
4. Frontend calls timeline API.
5. Frontend renders goal, references, actions, outputs, and timeline.
6. No generation happens automatically.
```

Acceptance:

```text
The page is useful even before the user generates again.
```

### 9.2 First Generation Inside Project

Steps:

```text
1. User creates or opens project.
2. User chooses General Template.
3. User enters one sentence.
4. Optional: user uploads reference images.
5. Frontend creates a project job.
6. Job result appears in output board.
7. User can select a useful image.
```

Acceptance:

```text
The generated job must have project_id.
The output board must show images, not placeholders, when output URLs exist.
```

### 9.3 Continue Same Style

Steps:

```text
1. User has at least one selected reference.
2. User clicks continue same style.
3. Frontend opens continuation composer.
4. User enters a short instruction.
5. Frontend creates a new project job.
6. Backend builds context from selected references and project summary.
7. New outputs appear as a new timeline item.
```

Acceptance:

```text
The old job remains unchanged.
The new job uses project context.
The UI explains that the new images are based on selected project references.
```

### 9.4 Upload New Reference And Continue

Steps:

```text
1. User clicks upload new reference continue.
2. User uploads one or more images.
3. Frontend asks whether these should be used for this project.
4. Frontend creates a new project job with uploaded references.
5. Uploaded references are persisted according to document 39.
6. Output board updates.
```

Acceptance:

```text
Uploaded references are not lost after refresh when marked useful.
```

### 9.5 Select Output As Future Reference

Steps:

```text
1. User clicks select on an output tile.
2. Frontend calls select endpoint.
3. Project useful references board updates immediately.
4. Confirmed visual direction updates.
5. Timeline records a plain-language selection event.
```

Acceptance:

```text
Only selected outputs influence future positive context.
```

### 9.6 Unselect Output

Steps:

```text
1. User opens selected image detail.
2. User clicks no longer reference.
3. Frontend calls unselect endpoint or feedback endpoint.
4. Image remains in timeline but leaves useful references board.
5. Future context excludes it.
```

Acceptance:

```text
Unselecting does not delete generated files.
```

### 9.7 Mark Wrong Direction

Steps:

```text
1. User clicks do not continue this direction.
2. User optionally selects a simple reason.
3. Frontend saves project feedback.
4. Future context includes avoid notes.
5. Timeline records the feedback.
```

Acceptance:

```text
Negative feedback affects future context but does not remove history.
```

## 10. API Usage

Existing APIs:

```text
GET /api/v3/creative-agent/projects
POST /api/v3/creative-agent/projects
GET /api/v3/creative-agent/projects/{project_id}
POST /api/v3/creative-agent/projects/{project_id}/jobs
GET /api/v3/creative-agent/projects/{project_id}/timeline
POST /api/v3/creative-agent/projects/{project_id}/outputs/select
```

New or extended APIs are defined in document 39.

The frontend must tolerate missing new endpoints during incremental rollout by
showing disabled actions rather than breaking the project page.

## 11. Frontend Component Plan

Suggested component names:

```text
V3ProjectHome
V3ProjectCard
V3ProjectWorkspace
V3ProjectHeader
V3ProjectGoalPanel
V3ProjectDirectionPanel
V3UsefulReferenceBoard
V3ContinuationActionRail
V3ContinuationComposer
V3ProjectOutputBoard
V3ProjectOutputTile
V3ProjectOutputDrawer
V3ProjectTimeline
V3ProjectTimelineItem
V3NegativeFeedbackModal
V3LockedTemplateNotice
```

If the existing frontend is not componentized, keep equivalent function names
and DOM sections.

## 12. Copy Rules

Use plain outcome language:

```text
生成了 4 张图
选中后可继续保持这个方向
这张会作为后续参考
已记录下次尽量避免
```

Avoid engineering language:

```text
provider
manifest
scenario runtime
context package
prompt compiler
asset ref
job payload
```

Use action labels instead of abstract terms:

```text
继续同风格生成
上传参考图继续
选为后续参考
不参考这张
查看详情
下载图片
```

## 13. Data Display Rules

Show:

```text
project title
project goal
selected images
uploaded useful references
generated images
plain output summary
project timeline
simple next actions
```

Hide:

```text
raw ids
storage paths
provider payload
internal prompts
capability module traces
manifest details
debug logs
```

## 14. Visual Rules

Follow the current Alchemy Lab-inspired card-module style:

```text
project cards
compact image grids
clear action cards
8px or less radius unless existing shell requires otherwise
restrained shadows
high image priority
beginner-facing text
```

Do not create a developer dashboard.

Do not turn the project page into a file manager.

## 15. Implementation Order

Recommended code sequence:

```text
1. Add project workspace state normalization helper.
2. Split project detail into clear rendering sections.
3. Add useful references board.
4. Add continuation action rail and composer.
5. Add output detail drawer.
6. Add select/unselect-ready UI states.
7. Add negative feedback modal in disabled or stubbed state if document 39 is not implemented yet.
8. Add timeline detail expansion.
9. Hide remaining engineering fields from normal UI.
10. Add frontend tests.
```

## 16. Required Frontend Tests

Add or update tests for:

```text
home shows project cards, not standalone job history
project detail loads without generating automatically
project detail shows beginner-facing goal and next actions
general template can create a project job
continue same style creates a new project job with project_id
selected output appears in useful references board
unselected output remains in timeline but leaves useful references board
locked ecommerce template cannot create a job
no engineering labels appear in normal UI
generated image URLs render as image previews
```

## 17. Required Manual QA

Manual QA script:

```text
1. Open V3 home.
2. Create a new project with one sentence.
3. Enter project detail.
4. Generate with General Template.
5. Confirm images are visible.
6. Select one image.
7. Refresh page.
8. Confirm selected image remains useful reference.
9. Continue same style.
10. Confirm a new timeline item appears.
11. Click E-Commerce template.
12. Confirm locked message and no job creation.
```

## 18. Acceptance Criteria

This phase is complete when:

```text
1. Project detail is the main continuation surface.
2. Users can understand the project state without engineering knowledge.
3. Users can continue a project from selected outputs.
4. Generated outputs remain visible and actionable.
5. Useful references and timeline are visually separate.
6. E-Commerce remains locked.
7. No V1/V2/Lab state is used by V3 runtime.
8. Existing V3 provider/job/shared capability tests continue to pass.
9. Document 43 product experience quality gate passes for this workspace.
```
