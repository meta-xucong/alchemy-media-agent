# 36 V3 General Template Project Flow Specification

> **Current-status note (Docs 113, 134–135):** General remains a neutral
> project flow. Historical preset/mode wording may preserve user intent or
> read old records, but must never compile a new scene, role, camera or retry
> prompt. A remote Brain-approved canonical prompt is the only renderer text.

Current compatibility note:

```text
Document 52 is the current authority for the next General Template continuation
upgrade: post-generation visual inspection, safe automatic retry execution,
suite variation direction, and beginner-facing output curation.

This document still defines the General Template project flow. Doc52 deepens
the continuation/generation loop without changing the rule that General
Template remains the first active template and must not become an E-Commerce
agent by accident.
```

This document defines the first active template in Project Mode:

```text
通用模板 -> general_creative Scenario Pack
```

The General Template should prove the V3 project-level consistency loop before
E-Commerce and future templates are reactivated.

---

## 1. Template Purpose

General Template is for broad commercial visual work:

```text
poster
social cover
brand key visual
campaign image
product-style creative visual without marketplace listing rules
festival visual
local business promotion
```

It must remain policy-neutral. It must not become an E-Commerce agent by
accident.

---

## 2. Active Scope

In the Project Mode implementation phase, General Template supports:

```text
new project first generation
generate from simple request
upload reference images
select result as project reference
continue same style
regenerate with a short adjustment
view useful project timeline
download generated images when available
```

Out of scope:

```text
Amazon listing logic
SEO keywords
competitor mining
marketplace compliance
ecommerce suite slots
professional canvas editing
manual layer editing
raw prompt editing
```

---

## 3. First Generation Flow

Flow:

```text
user creates project
ProjectRecord is created
General Template is selected by default
user enters one sentence or uses project goal
optional references are uploaded through V3 upload store
Project API creates a job inside the project
existing V3ProductApiService creates a general_creative job
generation runs through existing provider/output path
result appears in project result board
timeline records job_created and job_generated
```

The generated job must include:

```text
project_id
template_id=general_template
scenario_selection.scenario_id=general_creative
project context snapshot metadata
```

---

## 4. Project Context Use

When the project has selected outputs, continuation jobs must use
`ProjectContextPackage`.

Project context should influence:

```text
commercial brief
visual tone
layout direction
reference binding
history continuation
prompt constraints
output review
```

The implementation should reuse existing shared capability modules:

```text
AssetRoleAnalyzer
AssetBindingPlanner
VisualGrammarLockModule
InformationIntegrityLockModule
PromptConstraintCompiler
OutputReviewModule
HistoryReferenceModule
```

These modules must remain V3-owned and optional.

---

## 5. Selection Flow

When the user clicks:

```text
选中作为后续参考
```

The system must:

```text
call existing job selection path or project selection wrapper
record selected candidate/asset
append candidate_selected timeline item
update ProjectRecord.selected_output_refs
rebuild ProjectContextPackage
show a simple success message
```

Default message:

```text
已选中。这张图会作为本项目后续风格参考。
```

Do not silently apply persistent Brand Memory.

Optional later action:

```text
保存为品牌风格
```

---

## 6. Continue Same Style Flow

When the user clicks:

```text
继续同风格生成
```

The UI should ask for one short instruction:

```text
这次想继续做什么？
```

Example placeholders:

```text
继续同风格，做一张朋友圈海报
继续同风格，换成小红书封面
继续同风格，突出新品优惠
```

The backend must create a new job inside the same project. It must not mutate
the old job.

The new job should receive:

```text
current ProjectContextPackage
selected output references
new user instruction
scenario_id=general_creative
```

---

## 7. Regenerate Flow

Regenerate should stay beginner-friendly.

Allowed user controls:

```text
更清爽
更高级
更有点击感
产品更突出
留白更多
换一个构图
```

The UI may use a free-text adjustment box, but should offer simple chips.

Regenerate creates a new project job or a new generation attempt according to
the existing Product API capability. For project consistency, the project
timeline must record the action either way.

---

## 8. Useful Output Summary

The right-side or secondary summary should be titled:

```text
这次 V3 帮你完成了
```

Allowed summary items:

```text
已理解图片用途
已整理画面风格
已参考你上传的图片
已保护需要保留的主体或文字
已沿用本项目已选风格
已检查结果是否贴近需求
```

Do not show:

```text
capability module names
closure check names
raw score arrays
prompt fragments
provider messages
```

---

## 9. General Template And E-Commerce Boundary

General Template may accept product-like references, but only as generic visual
facts.

It must not:

```text
rank marketplace selling points
build Amazon bullets
use keyword roots
create competitor analysis
promise listing-ready suites
activate ecommerce image recipes
```

If the user asks for explicit ecommerce suite behavior while E-Commerce is
frozen, show:

```text
电商模板即将开放。当前可以先用通用模板做产品风格图，后续再进入电商套图。
```

---

## 10. Failure Handling

Use simple failure language:

```text
项目还没有可延续的已选图片
图片生成暂时受阻
参考图暂时不可用
这个模板还未开放
```

When context is missing:

```text
No selected outputs -> generate normally and invite the user to select one.
No uploaded references -> continue from project goal and confirmed style only.
No linked brand -> use project context only.
```

---

## 11. Frontend Acceptance

General Template is correct when:

1. It can only generate inside a project.
2. It asks for one simple request, not a professional prompt.
3. It can use optional reference images.
4. It displays generated images as the main result.
5. It records selected outputs into the project.
6. It can continue the same style in a new project job.
7. It does not show E-Commerce-specific fields.
8. It does not show engineering language.

---

## 12. Backend Acceptance

Backend behavior is correct when:

1. Project-created General jobs still use `general_creative`.
2. Existing Product API job tests still pass.
3. Project jobs include `project_id`.
4. Continuation jobs include project context.
5. Selection updates project context.
6. Brand Memory is not updated without explicit confirmation.
7. Shared capabilities remain optional and product-level.
