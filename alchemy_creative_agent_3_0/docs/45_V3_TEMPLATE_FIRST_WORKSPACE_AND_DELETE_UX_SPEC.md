# V3 Template-First Workspace And Delete UX Spec

## Status

Accepted implementation document for the next V3 Project Mode frontend and API
iteration.

This document extends documents 32-44. It does not replace the V3 Project Mode
foundation:

```text
V3 base
  -> Project
      -> Template
          -> Scenario Pack
              -> Project-scoped Job
```

The backend architecture stays the same. The user-facing order changes to:

```text
Choose Template
  -> Create Project
      -> Work Inside Project
          -> Generate, Select, Continue, Remove, Archive
```

## Why This Exists

The previous V3 Project Mode UI proved the backend project model works, but the
frontend order and information architecture are wrong for beginner users:

1. Users had to create a generic project before choosing the template. This
   hides the most important decision: what kind of work the agent will do.
2. Project detail mixed outputs, references, templates, workflow, brand memory,
   ecommerce fields, and generation controls into one surface with weak visual
   hierarchy.
3. Temporary or future actions were visible too early, which made the primary
   path harder to understand.
4. Users could not archive projects or remove references from the beginner-facing
   project interface.

V3 should feel like an agent that guides a complete design chain. The visible
interface must therefore show only the next meaningful decision while preserving
the deeper project context internally.

## Product Principle

Use this rule for all implementation choices:

```text
Home chooses the type of project.
Project detail shows what has been produced.
The project homepage stays clean: navigation cards, overview, images, and useful
artifacts only.
The action area is opened from cards as a child subpage; detailed forms do not
live inline on the project homepage.
Deletes remove items from future positive context.
```

## Scope

Implement in this phase:

- V3 home shows template cards before project creation.
- New project creation is launched from a selected template.
- Project cards remain on the home page as recent project history.
- A project opens directly into its primary template workspace.
- Project detail has two clear regions:
  - persistent display region
  - step-based navigation card region
- Clicking a step card opens a project child subpage for detailed actions.
- Secondary or not-yet-needed functions are collapsed into compact cards.
- Add beginner-facing archive/delete controls:
  - archive project from home or project detail
  - remove active project references from the project context
- Add backend soft-delete/soft-archive APIs required by the frontend.
- Add tests proving the new order, structure, delete behavior, and template
  isolation.

Do not implement in this phase:

- physical deletion of generated image files
- destructive permanent project deletion
- cross-template advanced project branching
- future templates beyond visible placeholder cards
- a new template system separate from Scenario Pack or Project Template Registry
- V1/V2/Lab runtime coupling

## Compatibility Rules

1. Project still wraps Job.
2. Template still wraps Scenario Pack.
3. Existing `/api/v3/creative-agent/projects/{project_id}/jobs` remains the
   only Project Mode job creation path.
4. Existing Product API jobs and generated outputs are not mutated during
   archive/remove actions.
5. Soft deletion changes Project Mode context, list visibility, and UI state.
6. Legacy V3 `/jobs` compatibility remains outside Project Mode and is not the
   frontend path.
7. Brand Memory is never written by delete/archive actions.

## New Home UX

The V3 home must display in this order:

```text
1. Template chooser
2. New project form for the selected template
3. Recent project cards
```

### Template Chooser

Template cards come from the existing Project Template Registry:

- General Creative: active
- E-Commerce: active only through Project Mode and product-reference rules
- Future templates: visible but disabled/placeholder

Each active template card must show:

- beginner-friendly name
- one-line description
- what the user needs to provide
- primary action label
- visual active state when selected

Forbidden visible text:

- scenario pack
- manifest
- provider
- job id
- prompt compiler
- capability module
- context package

### New Project Form

The form belongs to the selected template.

General template minimum fields:

```text
Project goal: required natural language
Reference images: optional, may be uploaded later
Brand/project name: optional
Desired feeling: optional
```

E-Commerce template minimum fields:

```text
Project goal: required natural language
Product image: required before generating, but project creation may still happen
Product/category/market fields: optional starter fields
```

The create button copy changes by template:

```text
General: "创建通用创意项目"
E-Commerce: "创建电商套图项目"
Future placeholder: disabled, "暂未开放"
```

Project creation payload must include:

```json
{
  "primary_template_id": "<selected template id>",
  "metadata": {
    "frontend_surface": "commercial_v3_project_mode",
    "template_first_create": true
  }
}
```

After creation, open the project workspace for the created project's primary
template. Do not show a second template selection step inside the new project.

## Project Detail UX

Project detail must read as a project homepage. It uses three visible layers:

1. a persistent display region
2. a step-card navigation region
3. a hidden child subpage that opens only after the user clicks a step card

### Region A: Persistent Display Region

Purpose: "What already exists in this project?"

Always visible near the top of the project page. It contains:

1. Project header:
   - project title
   - template label
   - project goal summary
   - project status
   - archive/delete action
2. Output board:
   - generated images first
   - selected outputs visibly marked
   - empty state explains what will appear after generation
3. Useful reference board:
   - selected generated references
   - uploaded references
   - remove button for each active reference
4. Artifact drawer:
   - collapsed by default
   - contains workflow strip, brand memory prompt, and timeline
   - label uses plain language such as "项目产物与记录"
5. Workflow strip:
   - plain-language progress
   - no technical checks or module names
6. Timeline:
   - collapsed or compact by default
   - plain-language events only

This region must not contain large input forms.

### Region B: Step-Card Navigation Region

Purpose: "What should I do next?"

This region is a clean navigation surface. It contains compact cards only. It
must not contain upload fields, prompt textareas, ecommerce fields, generated
result controls, or provider/debug status.

General template step model:

```text
1. Describe project goal
2. Add optional reference images
3. Generate first creative images
4. Select a preferred result
5. Continue in the same style, save brand style, or export later
```

E-Commerce template step model:

```text
1. Add product image
2. Add simple product facts
3. Choose suite purpose
4. Generate ecommerce image set
5. Select, remove references, continue, or export later
```

Current step expansion rules:

- No generated job yet:
  - mark input/generate card as current
- Generated but no selected output:
  - mark select-result card as current
- Has selected reference:
  - mark continue card as current
- E-Commerce without product reference:
  - mark product image card as current and disable generation inside the child
    subpage

Each collapsed step card shows:

```text
step label
done / current / later status
one short sentence
```

Clicking any enabled step card opens Region C.

### Region C: Project Child Subpage

Purpose: "Do the selected step without cluttering the project homepage."

The child subpage is hidden by default and opens as an in-page overlay when the
user clicks a step card. It is visually framed as a temporary working surface,
with a clear "返回项目主页" button.

The child subpage contains the detailed controls that would otherwise clutter
the homepage:

- prompt textarea
- upload/reference controls
- optional intent/preset controls
- ecommerce-only fields when ecommerce is active
- generate/regenerate/select buttons
- current result board
- beginner-facing completion summary
- warnings rewritten into plain user language

Rules:

- Template switching is forbidden inside the project child subpage.
- The child subpage always uses `project.primary_template_id`.
- Closing the child subpage returns to the project homepage without losing the
  current project context.
- After successful generation, keep the child subpage open and switch the active
  step to result review.
- After selecting a result, keep the child subpage open and switch the active
  step to continuation.
- The project homepage output board must refresh after each generation or
  selection so images remain the visual focus.

## Delete And Archive Behavior

### Project Archive

Add a soft archive operation:

```text
POST /api/v3/creative-agent/projects/{project_id}/archive
```

Behavior:

- set `project.status = archived`
- update `project.updated_at`
- append timeline item with plain-language title "归档了项目"
- exclude archived projects from default project list
- keep project detail readable by direct URL/API
- do not delete project JSON, jobs, generated outputs, uploads, or brand memory

The frontend action label should be "归档项目" or "删除项目" depending on the
surface, but explanatory text must make clear it is removed from recent projects
and not physically destroyed.

### Reference Removal

Use the existing update-reference capability or add a convenience route:

```text
POST /api/v3/creative-agent/projects/{project_id}/references/{reference_id}/remove
```

Behavior:

- set `reference.status = inactive`
- if the reference points to a selected output, mark that output unselected
- add `remove_reference` feedback when useful
- refresh ProjectContextPackage
- append plain-language timeline item "移除了项目参考"
- future jobs must not use that reference as positive context

The UI shows "移除参考" on each active reference card.

### Generated Output Removal

Do not physically delete generated output files in this phase.

If the user removes a generated output that is currently used as a reference,
route it through the reference removal/unselect path. Non-selected generated
outputs remain historical job results and are not part of positive context.

## Frontend Implementation Map

Primary files:

```text
src_skeleton/app/static/index.html
src_skeleton/app/static/styles.css
src_skeleton/app/static/app.js
tests/test_v3_commercial_frontend_shell.py
```

Required frontend state additions:

```text
v3State.selectedTemplateId
v3State.createTemplateId
v3State.projectActionStep
```

Required DOM anchors:

```text
v3TemplateChooser
v3TemplateCreatePanel
v3SelectedTemplateTitle
v3SelectedTemplateIntro
v3ProjectSnapshot
v3ProjectArchiveBtn
v3PersistentDisplayRegion
v3StepActionRegion
v3StepCards
v3ProjectSubpage
v3SubpageTitle
v3SubpageIntro
v3CloseSubpageBtn
```

`v3ProjectSnapshot` is a beginner-facing project overview, not an engineering
status panel. It must explain, in plain language, what this project has fixed
and remembered:

- project type is fixed after creation and cannot be switched mid-project
- project goal
- confirmed references / directions
- current progress and best next action

Required UI event behavior:

- click template card:
  - select template
  - update create form copy
  - focus goal input only when useful
- create project:
  - include selected `primary_template_id`
  - open the created project's primary template workspace
- open project card:
  - open project detail using `project.primary_template_id`
  - do not show any generic template picker inside the primary workspace
  - show project overview before action controls so users understand what the
    project remembers before continuing
- click project step card:
  - do not navigate away from the project page
  - open `v3ProjectSubpage`
  - update subpage title and intro based on the selected step
  - render detailed controls inside the subpage only
- close project child subpage:
  - hide `v3ProjectSubpage`
  - keep project homepage, project overview, images, selected references, and
    navigation cards visible
- archive project:
  - ask for confirmation
  - call archive API
  - return to home and refresh recent projects
- remove reference:
  - ask for confirmation
  - call remove API or patch status inactive
  - refresh project detail/context/timeline

## Backend Implementation Map

Primary files:

```text
alchemy_creative_agent_3_0/app/project_mode/contracts.py
alchemy_creative_agent_3_0/app/project_mode/service.py
alchemy_creative_agent_3_0/app/product_api/route_handlers.py
src_skeleton/app/main.py
alchemy_creative_agent_3_0/tests/test_v3_project_mode.py
```

Required backend additions:

- timeline type for project archived and reference removed, or reuse
  `reference_updated`/`note_added` with plain-language title if schema churn is
  intentionally avoided
- service method `archive_project(project_id)`
- service method `remove_project_reference(project_id, reference_id, payload)`
- route handler methods for both operations
- FastAPI route adapters for both operations

List behavior:

- default project list returns only active/draft projects
- direct project detail can return archived project
- archived project metadata must mark it as not shown in recent list

## Data Integrity Rules

1. Removing a reference must remove it from positive context.
2. Removing a selected generated reference must also remove or inactivate the
   corresponding selected output state.
3. Archived projects must not disappear from storage.
4. Archived projects must not be returned in the normal home list.
5. E-Commerce product reference validation from the QA bugfix must stay intact.
6. Project creation from E-Commerce template must not allow generation without
   a valid product reference.
7. General project continuation must not read E-Commerce commerce profile data.

## Acceptance Tests

Focused backend tests:

- active projects list excludes archived projects
- archived project detail remains readable
- archive project appends plain-language timeline item
- reference remove marks the reference inactive
- removed reference exits `uploaded_reference_assets` and
  `selected_reference_assets`
- removing generated selected reference unselects corresponding output context
- E-Commerce still rejects no product image/reference

Frontend/API tests:

- static HTML contains template-first anchors
- V3 home template chooser appears before new project form
- project creation script sends `primary_template_id`
- project detail contains persistent display region and step-card navigation
  region
- project detail contains a hidden child subpage for detailed actions
- clicking step cards calls the child subpage opener instead of navigating away
- project homepage does not inline prompt/upload/generation controls outside the
  child subpage
- child subpage has a "返回项目主页" control
- project detail no longer uses a generic in-project template picker as the
  primary workflow
- archive/remove controls exist in JS and call V3 Project Mode APIs
- visible V3 section still avoids engineering copy

Browser QA:

- open `/creative-agent-v3`
- verify active V3 tab
- verify template cards are visible before project creation
- select General template, create project, verify General workspace opens
- create/open E-Commerce project, verify product-image step is the current step
- verify project page has clear persistent display and navigation-card regions
- click each enabled project step card and verify the child subpage opens with
  the matching title, copy, controls, and return behavior
- verify closing the child subpage leaves overview, images, references, and
  navigation cards on the project homepage
- verify archive action removes a project from recent projects
- verify reference removal removes a reference card from useful references

## Auditor Review Before Coding

The implementation is acceptable only if all answers are yes:

1. Does this preserve `Project -> Template -> Scenario Pack -> Job`?
2. Does the user choose a template before creating a project?
3. Does the project page show outputs and references before forms?
4. Is there one obvious next action for a beginner?
5. Are future or unavailable actions collapsed/disabled instead of competing
   with the current action?
6. Are deletes soft and reversible at the storage level?
7. Does delete/remove affect future context correctly?
8. Does E-Commerce support text-only generation while strengthening consistency when product image evidence exists?
9. Does General remain policy-neutral?
10. Does the normal UI hide technical implementation terms?
11. Do tests cover both successful and adversarial paths?

## Audit Result

Reviewed against current documents 32-44 and current implementation:

- Compatible with V3 architecture: yes. It changes the frontend order and adds
  Project Mode service methods; it does not replace Scenario Runtime, Product
  API, provider/output stores, or shared capabilities.
- Compatible with the user's product requirement: yes. It makes the main path
  easier for non-code users by starting from "what do you want to make" and then
  showing a single current step.
- Functional completeness: acceptable for this phase. Permanent deletion,
  batch deletion, and export packaging remain future scoped features, but the
  required beginner-facing delete/archive actions are covered.
- Risk areas to test carefully:
  - archived projects must not vanish from direct project detail
  - reference removal must refresh context and not only update visual state
  - E-Commerce project creation must not accidentally bypass product-reference
    validation during later generation
  - existing V1/V2/Lab pages must not inherit V3-only UI behavior

Coding may proceed after this document is added to the README index and the
long-running roadmap state for this phase.
