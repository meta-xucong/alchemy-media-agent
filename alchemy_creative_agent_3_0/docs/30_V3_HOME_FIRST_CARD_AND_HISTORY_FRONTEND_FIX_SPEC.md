# 30 V3 Home-First Card And History Frontend Fix Specification

This document corrects the V3 commercial frontend entry logic after documents
`27`, `28`, and `29`.

Document `27` remains the broad commercial frontend target. This document is a
more specific implementation correction for the current state: the V3 landing
surface must behave like Alchemy Lab, not like an engineering workbench.

Project Mode note:

```text
Document 32 and its follow-up documents 33-37 supersede this document for the
meaning of "history". In Project Mode, the V3 first screen should show New
Project and project cards. Raw V3 job history becomes a compatibility/fallback
source inside Project Mode, not the primary user-facing continuation object.
```

---

## 1. Problem Found

The current V3 shared-shell panel exposes too much detail on first entry:

```text
scenario cards
prompt composer
upload controls
job result board
agent analysis summary
commerce fields
```

This is not the desired beginner-facing product flow. A non-technical user
should first see only:

```text
1. agent / scenario cards
2. recent V3 history
```

For the pre-Project-Mode stage, "recent V3 history" meant job history. For the
Project Mode stage, documents `32`-`37` replace this with recent V3 projects.

The specific workspace should appear only after the user clicks an active card
or a history item.

---

## 2. Correct Product Logic

Use the Alchemy Lab interaction model as the reference:

```text
V3 tab or /creative-agent-v3
  -> V3 home
       -> active agent cards
       -> future agent cards
       -> recent history

User clicks active card
  -> dedicated V3 workspace
       -> simple request
       -> upload references
       -> optional beginner-friendly fields
       -> generate / select / export-facing result board

User clicks back
  -> V3 home
```

The V3 home is not a form page. It is an entry and continuation page.

---

## 3. Relationship To Existing Documents

Use this document with the following precedence for frontend entry behavior:

```text
1. Document 32 Project Mode core control when implementing Project Mode
2. Documents 33-37 for Project Mode migration, contracts, UX, General Template,
   and template audit rules
3. V3 product boundary and API independence rules
4. This document's legacy home-first card/history rule for pre-Project Mode UI
5. Document 27 commercial frontend target
6. Documents 26 and 28 E-Commerce activation details unless frozen by document 37
7. Earlier minimal UI or app-shell probes
```

Document `27` describes the desired commercial frontend broadly. This document
overrides any interpretation of document `27` that makes the V3 first screen
show the full workspace by default. Documents `32`-`37` then upgrade the first
screen again from job-history-first to project-first.

---

## 3.1 V3 Independence Boundary

V3 must be independent from V1, V2, and Alchemy Lab at runtime.

Allowed overlap:

```text
shared outer page
shared top navigation
shared visual tokens / base CSS primitives
shared authentication shell if the site already gates the page globally
```

Forbidden overlap:

```text
calling V1/V2/Lab generation APIs from V3
loading V1/V2/Lab history into V3 history
sharing V1/V2/Lab frontend state objects as V3 state
using V1/V2/Lab upload APIs for V3 assets
using V1/V2/Lab job IDs as V3 job records
using Lab module APIs as V3 scenario APIs
silently importing V1/V2 provider settings into V3 UI or payloads
sharing V1/V2/Lab localStorage or sessionStorage keys
sharing V1/V2/Lab selected result state
sharing V1/V2/Lab export manifests
```

V3 may copy interaction patterns from Alchemy Lab, such as card entries and a
recent-history strip, but the data source and runtime must remain V3-owned.

This boundary should be treated as a release blocker: if a V3 feature needs a
capability that exists in V1, V2, or Alchemy Lab, implement or adapt it inside
the V3 namespace before exposing it to users.

---

## 4. Required First Screen

The V3 first screen must include:

```text
V3HomeView
  Header:
    product-facing title
    short beginner-facing explanation
    active scenario count

  Scenario card grid:
    General Creative
    E-Commerce
    New Media
    Private Domain
    Brand IP

  Recent history:
    recent V3 jobs
    status
    scenario label
    short request summary
    continue action
```

Project Mode replacement:

```text
V3ProjectHomeView
  Header
  New Project action
  Recent project cards
  Locked future template hints
```

When Project Mode is implemented, `Recent history` must mean recent V3
projects. Raw job history may be used only as a fallback/import source.

The first screen must not include:

```text
prompt textarea
file upload dropzone
provider/model/seed controls
commerce advanced form fields
result board
agent capability internals
raw API or debug wording
```

---

## 5. Scenario Card Behavior

Active cards:

```text
General Creative
E-Commerce
```

Clicking an active card:

```text
open shared V3 workspace
select the clicked scenario
show scenario-specific beginner fields
do not create a job automatically
```

Future cards:

```text
New Media
Private Domain
Brand IP
```

Clicking a future card:

```text
show a friendly unavailable state or toast
stay on V3 home
never create a job
never call scenario-owned execution APIs
```

---

## 6. Workspace Behavior

The workspace is a second-level surface.

Required workspace elements:

```text
Back to V3 home action
selected scenario title and short promise
quick-start preset cards
simple request textarea
reference/product image upload
optional brand/tone fields
scenario-specific optional details
primary generation actions
result board
agent summary in product language
warnings and recovery notes
```

E-Commerce may be active because document `26` and document `28` have already
been implemented for the accepted current-stage scope. Its UI must still be
beginner-first:

```text
upload product image
type a simple request
optionally choose platform / market
optional advanced commerce facts collapsed or visually secondary
```

Do not force the user through Amazon copywriting, keyword mining, or competitor
analysis forms on first use. Those are later advanced enhancements for the
E-Commerce pack.

---

## 7. History Behavior

V3 history should be V3-owned.

Preferred API:

```text
GET /api/v3/creative-agent/history?limit=20
```

The frontend may also keep a local browser cache as a graceful fallback:

```text
localStorage key: alchemy_v3_job_history_v1
```

History cards should show product-facing information only:

```text
scenario label
job status
request summary
updated time
continue button behavior
```

Clicking a history item:

```text
fetch job by /api/v3/creative-agent/jobs/{job_id}
open the relevant V3 workspace
render the job if it still exists
fall back to local summary if the server-side in-memory job is gone
```

Do not use V1/V2 generation routes to execute V3 jobs. Cross-version history
can be designed later as an explicit import/continue feature.

---

## 8. Implementation Steps

### Step 1 - Documentation

1. Add this document.
2. Add this document to the README and delivery-plan document list.
3. Add a short note to document `27` saying this document corrects the first
   screen behavior.

### Step 2 - API Support

1. Extend the V3 in-memory job store with a recent-list method.
2. Add a V3 product-level history response contract.
3. Add `GET /api/v3/creative-agent/history`.
4. Keep all history responses free of low-level generation controls.

### Step 3 - HTML Structure

1. Split `v3Tab` into:

```text
v3HomeView
v3WorkspaceView
```

2. Move scenario cards and history into `v3HomeView`.
3. Move prompt, uploads, result board, and agent summary into
   `v3WorkspaceView`.
4. Add a back button in the workspace header.

### Step 4 - Frontend State

1. Add `v3State.view`.
2. Add V3 history state.
3. Add:

```text
openV3Home
openV3ScenarioWorkspace
renderV3ViewState
loadV3History
renderV3History
saveV3HistorySnapshot
openV3HistoryJob
```

4. Route `/creative-agent-v3` to V3 home.
5. Route `/creative-agent-v3/ecommerce` and `/creative-agent-v3/general` to
   the relevant workspace.

### Step 5 - CSS

1. Style V3 home cards and history cards as commercial product modules.
2. Keep card radii and density consistent with Alchemy Lab.
3. Ensure the workspace is hidden with `hidden` when on home.
4. Ensure mobile cards stack cleanly.

### Step 6 - Tests

Add or update tests for:

```text
V3 home exists
V3 workspace exists but is hidden on first load
home contains cards and history
workspace contains the detailed form
history API returns recent V3 jobs
V3 JS exposes home/workspace/history functions
V3 frontend does not call V1/V2 generation APIs
existing V1/V2/Alchemy Lab smoke paths still pass
```

### Step 7 - Browser Verification

After tests pass, start the local server and click through:

```text
V3 navigation entry
General Creative card
Back to home
E-Commerce card
Back to home
future card disabled behavior
create job
generate
select
history item opens workspace
```

---

## 9. Acceptance Criteria

This fix is complete only when:

```text
1. V3 first screen shows only agent cards and recent history.
2. Prompt/upload/result/agent-detail content is not visible until an active card
   or history item is opened.
3. The UI copy is understandable by a beginner who does not know code.
4. E-Commerce uses the shared V3 workspace instead of a forked page.
5. Future agent cards cannot create jobs.
6. V3 history cards are visible and clickable.
7. V3 history uses V3-owned API/local fallback, not V1/V2 execution routes.
8. Existing V1/V2/Alchemy Lab routes still work.
9. Frontend tests and API tests pass.
10. Manual browser click-through passes.
11. V3 does not share V1/V2/Lab upload, job, selection, export, provider, or
    browser-cache state.
```
