# 35 V3 Project-First Frontend UX Specification

This document defines the Project Mode frontend experience.

It supersedes job-first interpretations of the V3 home screen in documents
`30` and `31`, while preserving their visual direction: card-module layout,
Alchemy Lab-like clarity, V3 runtime independence, and beginner-friendly copy.

---

## 1. Product Principle

The V3 frontend should not feel like an engineering workbench.

The user should understand:

```text
I create a project.
I choose what kind of visual work I want inside the project.
V3 remembers the good results I select.
I can come back later and continue the same style.
```

The user should not need to understand:

```text
job ids
scenario routes
provider setup
prompt compiler
capability modules
generation metadata
```

---

## 2. Information Architecture

Required first-level flow:

```text
Shared site shell
  -> V3 Home
      -> New Project
      -> Project Cards
      -> Locked future template cards as secondary hints
  -> Project Detail
      -> Project Overview
      -> Template Entry Cards
      -> Current Template Workspace
      -> Project Timeline
```

The V3 home is not a generation form.

---

## 3. V3 Home

The home view must show:

```text
product title
short beginner-facing promise
primary New Project action
recent project cards
optional locked/future template preview area
```

The home view must not show:

```text
prompt textarea
upload dropzone
job result board
commerce advanced fields
raw job history as the primary list
provider/model controls
debug summaries
```

Recommended Chinese copy:

```text
V3 项目
把一次创意需求做成可持续延展的视觉项目。
```

Primary action:

```text
新建项目
```

Empty state:

```text
还没有项目。先用一句话创建一个项目，后续每次生成都会沿用这个项目的风格和已选结果。
```

---

## 4. Project Cards

Each project card should be image-first and simple.

Show:

```text
latest 1-3 thumbnails
project title
one-line goal summary
template label
confirmed style chips
selected asset count
last action time
continue action
```

Do not show:

```text
job id
raw status enum
route
manifest
provider
candidate score
technical metadata
```

Recommended action label:

```text
继续这个项目
```

If no thumbnail exists, use a calm empty preview that says:

```text
等待第一组图片
```

Do not show a broken image icon.

---

## 5. New Project Flow

Use a compact modal or focused panel.

Minimum inputs:

```text
one sentence project goal
optional project name
optional reference image upload
```

Default template:

```text
通用模板
```

Do not ask the beginner to choose advanced settings.

Recommended placeholder:

```text
例如：帮我做一组夏季新品宣传图，清爽、高级，适合小红书
```

Project title may be generated from the goal if the user leaves it empty.

After creation:

```text
open Project Detail
show General Template as active
use the project goal as the first request draft
```

Do not generate automatically unless a later accepted spec explicitly adds
one-click create-and-generate.

---

## 6. Project Detail Page

Project detail must be the continuation surface.

Required sections:

```text
Project header
Project overview
Template entry cards
Active template workspace
Selected results
Project timeline
```

### 6.1 Project Header

Show:

```text
project title
goal summary
last updated time
back to V3 home
```

### 6.2 Project Overview

Show beginner-friendly context:

```text
这个项目目前的方向
已确认的风格
已选图片
还可以继续做什么
```

Example:

```text
已形成清爽、高级、留白多的新品宣传风格。
已选 2 张图作为后续参考。
可以继续生成同风格海报、封面或活动图。
```

### 6.3 Template Entry Cards

Current phase:

```text
通用模板: active
电商模板: locked
新媒体模板: locked
私域模板: locked
品牌 IP 模板: locked
```

Locked cards may explain what they will do later, but cannot create jobs.

Locked copy:

```text
即将开放。当前先用通用模板完成项目风格和延续能力。
```

---

## 7. General Template Workspace Inside Project

The General Template workspace must appear only after a project exists.

Show:

```text
simple request textarea
optional reference upload
optional desired feeling
primary generate action
result board
simple outcome summary
select/continue actions
```

Hide:

```text
marketplace fields
keywords
competitor fields
provider fields
raw prompts
debug checks
```

Recommended button labels:

```text
生成创意图
继续同风格生成
选中作为后续参考
```

---

## 8. Result Board

Generated images must be the visual focus.

Cards should show:

```text
image preview
asset purpose in simple words
recommended/selected state
download action when available
select action
```

Avoid numeric scores as primary language.

Allowed labels:

```text
推荐
已选
适合继续
需要再调
```

If generation is still waiting:

```text
图片正在生成
```

If a provider fails:

```text
图片生成暂时受阻，请稍后重试或检查后台配置。
```

Do not show raw provider error text in normal UI.

---

## 9. Timeline UX

Timeline should explain what happened in plain language.

Examples:

```text
创建了项目
上传了 2 张参考图
生成了一组创意图
选中了 1 张作为后续风格
继续生成了同风格素材
```

Timeline items should be clickable when they contain images or useful details.

Clicking a timeline job should open its result detail inside the project, not
leave the project and open a standalone job page.

---

## 10. State Model

The frontend should introduce V3 project-specific state.

Recommended shape:

```text
v3ProjectState
  view: home | project_detail
  projects: []
  currentProject: null
  currentTemplate: general_template
  currentJob: null
  timeline: []
  selectedOutputs: []
  files: []
```

Do not reuse V1, V2, Lab, or old V3 job-history state as the primary Project
Mode state.

Local fallback storage must use V3 project-specific keys, for example:

```text
alchemy_v3_project_history_v1
```

---

## 11. Mobile Behavior

Mobile must use a simple vertical stack:

```text
project header
overview chips
template cards
composer
result cards
selected results
timeline
```

Requirements:

1. No text overlap.
2. No horizontal dependency.
3. Project action buttons remain visible near their content.
4. Image previews keep stable aspect ratios.
5. Locked template cards remain compact.

---

## 12. Visual And Interaction Style

Use the existing Alchemy Lab card-module feeling as the closest visual
reference, but keep V3 project-specific.

Required style:

```text
image-first project cards
quiet commercial dashboard tone
compact card grid
clear primary action
simple chips for style and status
stable result-card aspect ratios
large enough touch targets
no nested cards inside cards
no decorative hero page
no engineering control panel visual language
```

Recommended project detail composition:

```text
┌──────────────────────────────────────────────────────────┐
│ 项目标题 / 目标摘要                         返回 V3 首页 │
├──────────────────────────────────────────────────────────┤
│ 项目方向 chips      已选图片 thumbnails      下一步建议   │
├──────────────────────────────────────────────────────────┤
│ 模板卡片: 通用 active | 电商 locked | 未来模板 locked     │
├───────────────────────────────┬──────────────────────────┤
│ 通用模板输入与上传             │ 这次 V3 帮你完成了        │
├───────────────────────────────┴──────────────────────────┤
│ 生成图片结果 board                                       │
├──────────────────────────────────────────────────────────┤
│ 项目时间线                                               │
└──────────────────────────────────────────────────────────┘
```

Color and density:

```text
follow the existing shared shell tokens where possible
avoid one-note purple/blue or beige-heavy palettes
do not use floating decorative blobs or gradient orbs
keep cards at 8px radius or below unless existing CSS requires otherwise
make thumbnails and generated images more visually dominant than text
```

Interaction:

```text
click project card -> open project detail
click locked template -> show concise locked message
click generated image -> preview/download
click select -> mark as project reference
click continue -> open one-sentence continuation input
```

---

## 13. Acceptance Criteria

The frontend UX is correct when:

1. V3 home is project-first.
2. The user cannot create a standalone V3 job from the home page.
3. Project detail is the place where generation happens.
4. General Template is the only active generation template.
5. E-Commerce and future templates are visible but locked.
6. History appears as project cards and project timeline, not raw job cards.
7. The normal UI contains no engineering language.
8. The visual style remains compatible with the existing Alchemy Lab-like card
   module layout.
