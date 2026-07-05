# 32 V3 Project Mode Core Control Specification

This document is the long-term control document for the next V3 development
stage.

It upgrades V3 from a job/history image-generation product into a
project-based commercial visual production agent. It must be read before
documents `33` to `37`, and it supersedes older V3 home/history interpretations
whenever they conflict with Project Mode.

---

## 1. Core Decision

Alchemy Creative Agent 3.0 is not a single-run image generator, a prompt
playground, or a design-workbench clone.

It is:

```text
a Lovart-benchmarked commercial visual production agent
with a stronger agentic central brain
and a simpler beginner-facing product surface.
```

The product should produce and continue a high-consistency design chain:

```text
rough business intent
-> project understanding
-> template selection
-> multi-round jobs
-> selected outputs
-> reusable project context
-> consistent follow-up assets
```

The central user-facing object is no longer a single generated image or a
single job history item. The central user-facing object is a V3-owned
`Project`.

---

## 2. Original V3 Product Thesis

The original V3 thesis remains valid:

```text
Say what you need.
Alchemy creates a brand-consistent commercial visual series for you.
```

Project Mode is not a new product direction. It is the missing product layer
that makes the original thesis operational.

The original documents already required:

```text
brand memory
style continuation
successful prior results
user choices
product references
asset series
selection and continuation
```

Those requirements cannot be fully satisfied by a flat job history list. They
need a project container.

---

## 3. Lovart Benchmark And V3 Difference

Lovart-like products are strong because they behave like AI design agents, not
prompt boxes. They coordinate concept direction, visual consistency, layout,
generation, refinement, and export-ready production.

V3 keeps that quality bar but should not expose a professional design
workstation to beginners.

V3 must hide the design workflow and let the agentic system do the work:

```text
user says what they need
V3 creates or continues a project
V3 selects the right template
V3 plans and generates the next assets
V3 reviews results
V3 lets the user select what becomes future context
```

V3 is stronger than a broad Lovart-like workstation in three ways:

1. It is vertical-commercial by default.
2. It has scenario/template agents that can specialize over time.
3. It converts user selections into reusable project context without requiring
   the user to manage a professional canvas, board, or workflow graph.

---

## 4. Required Architecture Shape

The target architecture is:

```text
V3 foundation
  -> Project application layer
      -> template entry
          -> Scenario Pack runtime
              -> Product Job
                  -> runs, candidates, selections, exports
```

The implementation must preserve the current V3 foundation:

```text
ScenarioRuntime
ScenarioPackRegistry
ScenarioPackManifest
ProductJobRecord
V3ProductApiService
BrandProfileService
shared_capabilities
provider adapters
uploaded asset store
generated output store
```

Project Mode is an additive application layer. It must not replace the current
V3 runtime.

---

## 5. Three Memory Layers

V3 must distinguish three layers.

### 5.1 Brand Memory

Brand Memory is long-term continuity across projects.

It may contain:

```text
brand tone
brand colors
layout preference
copywriting tone
successful assets
rejected style tags
platform history
```

Persistent Brand Memory updates require explicit user confirmation. A generated
result must never silently overwrite persistent Brand Memory.

### 5.2 Project

A Project is one coherent commercial design chain.

Examples:

```text
summer milk-tea campaign
new product launch visual set
homestay Xiaohongshu content set
brand refresh exploration
one SKU ecommerce image pack later
```

A Project stores:

```text
project goal
active template ids
uploaded references
selected outputs
rejected directions
confirmed visual style
timeline of jobs and user actions
project-level continuation context
optional linked brand id
```

Project is the main user-facing history object.

### 5.3 Job

A Job is one execution inside a Project.

Examples:

```text
initial generation
continue same style
regenerate with new reference
create social cover from selected visual style
export selected assets
```

Jobs are immutable records once completed. Continuing a direction creates a new
job linked to the same project, not an in-place rewrite of the old job.

---

## 6. Template Rule

The user may think in templates such as:

```text
通用模板
电商模板
新媒体模板
私域模板
品牌 IP 模板
```

The implementation must not create a second template framework.

In V3 code, a template is a productized entry over an existing or future
Scenario Pack:

```text
通用模板 -> general_creative Scenario Pack
电商模板 -> ecommerce Scenario Pack
future templates -> future Scenario Packs
```

Project Mode wraps Scenario Packs. It does not replace them.

---

## 7. Current Stage Boundary

The current accepted implementation stage after this document should activate
only:

```text
Project Mode shell
General Template project flow
Project-owned history
Project context builder
```

The following must remain inactive for generation in that stage:

```text
E-Commerce Template
New Media Template
Private Domain Template
Brand IP Template
other future templates
```

These templates may appear as project-entry cards, but they must not create
jobs until their own Project Mode integration has an accepted spec and tests.

---

## 8. Beginner-Facing Product Rule

V3 must speak to non-technical, non-design users.

The normal UI may show:

```text
项目
通用创意
继续同风格生成
已确认风格
已选图片
参考图
这次完成了什么
下一步可以做什么
```

The normal UI must not show:

```text
provider
adapter
job id
manifest
prompt compiler
capability module
closure check
raw route
seed
sampler
ControlNet
ComfyUI
LoRA
```

Debug surfaces may be added later, but they are outside this stage.

---

## 9. Context Source Rule

Project context must be built from user-approved signals.

Positive context may include:

```text
selected candidate images
selected asset ids
explicitly uploaded references
confirmed project tone
confirmed required text or facts
manual user notes
explicitly accepted style summaries
```

Unselected candidates must remain in project history only. They must not become
positive style references unless the user explicitly selects or restores them.

Rejected directions must be stored as negative context.

---

## 10. Compatibility Rule

Older documents remain valid where they define:

```text
V3 independence
Scenario Pack runtime
General Creative behavior
shared capability modules
asset upload
provider and output handling
candidate selection
Brand Memory confirmation
```

Older documents are superseded where they imply:

```text
V3 home opens job history directly
history is mainly a list of generated images
clicking history opens a standalone job workspace
E-Commerce remains active during the next Project Mode implementation phase
General Creative and E-Commerce should both be productized at once
```

Use this precedence for the Project Mode phase:

```text
1. 32 Project Mode core control
2. 33 compatibility and migration
3. 34 project contracts
4. 35 project-first frontend UX
5. 36 General Template project flow
6. 37 template interface and audit
7. 30/31 for legacy frontend shell details not conflicting with Project Mode
8. 18/24/25 for General Creative and shared capability behavior
```

---

## 11. Non-Negotiable Rules

1. Project Mode must be V3-owned.
2. Project Mode must not read V1, V2, or Alchemy Lab runtime state.
3. Project Mode may copy proven interaction ideas from Alchemy Lab, but not its
   state model or APIs.
4. Project Mode must not expose provider controls to normal users.
5. Project continuation must use selected project context, not every generated
   candidate.
6. General Template must not import E-Commerce rules.
7. E-Commerce must be locked during the Project Mode foundation phase.
8. Persistent Brand Memory must remain confirmation-based.

---

## 12. Acceptance Criteria

This document is satisfied when later implementation can prove:

1. V3 home is project-first, not job-first.
2. Project Mode is additive and does not rewrite the V3 foundation.
3. General Template uses `general_creative` through Scenario Pack runtime.
4. E-Commerce and future templates are visible but cannot create jobs in this
   phase.
5. Project continuation reads selected project context.
6. Brand Memory is not silently updated.
7. Existing V3 job/provider/shared-capability tests can keep passing.

