# Doc310 - V3 Home Project Image Count Synchronization Repair

Status: implemented, audited, and locally accepted. Doc313 supersedes only the
home-card presentation portion of this contract; formal count authority and
delivery semantics remain here. This document freezes the
correction model for the V3 home regression where project cards can show a
valid cover but do not show the project's formal image count, while other
projects show a stale or unsynchronized count.

## 1. Task record

### 1.1 User objective

Repair the V3 home/project-card read projection so that every visible project
card shows an honest, synchronized count of formal final-delivery images when
the count read succeeds. A project with no formal delivery must show `0`; a
count that has not been read must remain an explicit pending/unknown state.
The desktop and mobile cards must agree.

### 1.2 Baseline and gate

- Baseline: clean `main` at `32130e8afd2d49a1139226d80ddf802a6aaa87df`.
- Contract revision: `DOC310_V1_HOME_PROJECT_IMAGE_COUNT_SYNC`.
- Complexity gate: `ESCALATE_REQUIRED`; the defect crosses the Project Mode
  read projection, the home-preview response, desktop rendering, mobile
  rendering, and authenticated cache merge behavior.
- Unique writer: the current mainline integrator in
  `D:\AI\Alchemy Media Agent System`.
- Audit owner: a separate read-only audit phase after version freeze. No
  callable worker Agent is exposed in the current environment, so no external
  Agent result is claimed.

### 1.3 Non-goals

This repair does not change Brain, Provider, Review, Retry, generation,
output retention, project ownership, media authorization, V2 behavior,
professional asset semantics, or the meaning of formal final delivery.
It does not make the home preview a full gallery and does not use review-only
or process-only images in the formal count. Doc313 may expose a separately
labeled display-only review count and cover without changing that formal
count.

## 2. Observed mismatch and root cause

The previous bootstrap repair intentionally made
`GET /projects?view=summary` cheap: its persisted summary returns
`visible_output_count=0` and no thumbnails without reading Jobs or outputs.
The separate `surface=home_preview` request returns at most one cover per
project. The browser then has no authoritative count for the page:

1. the desktop and mobile project groups see one cover and label it only as a
   cover preview;
2. projects without a returned cover remain indistinguishable from projects
   whose count is still unknown;
3. the project catalog cards display Job count, not final image count;
4. a lightweight summary can overwrite a previously known cached count with
   its intentional zero.

This is a read-contract/projection defect. The existing delivery predicates
remain the authority and must be reused for count calculation.

## 3. Frozen correction model

### 3.1 Server count projection

The existing `surface=home_preview` read returns an additive
`project_output_counts` map keyed by the requested visible project ID. Each
entry is the count of unique formal final-delivery outputs after the existing
owner, lifecycle, review, selection, and failure predicates. A visible
project with no formal output receives a known `0`; a project whose bounded
index/read cannot be evaluated does not receive a count entry.

The count is a read-only projection. It does not reconcile or mutate the
project, Job, output, review, or selection stores. The response remains
`complete=false` for gallery/history purposes even when a per-project count is
known. The formal one-cover preview behavior remains unchanged; Doc313 adds a
separate review-only cover slot.

### 3.2 Explicit count completeness

`ProjectMemorySummary.visible_output_count_known` is additive. Lightweight
summary responses set it to `false`; full summaries and the home-preview
count merge set it to `true`. This prevents an intentional lightweight zero
from being mistaken for an authoritative empty project.

### 3.3 Browser projection

Desktop and mobile merge `project_output_counts` into the matching project
summary, preserve known cached counts when a later lightweight summary is
unknown, and re-render both the catalog card and history card. When a count is
known, a cover card displays the numeric count (`N 张图片`); when it is known
to be empty it displays `0 张图片`; when it is not known it retains the
existing explicit `图片数量未同步`/`尚未出图` state. Opening a project still
loads the project-scoped full output surface.

## 4. Allowed implementation surface

- this document;
- `alchemy_creative_agent_3_0/app/project_mode/contracts.py`;
- `alchemy_creative_agent_3_0/app/project_mode/service.py`;
- `src_skeleton/app/static/app.js`;
- `src_skeleton/app/mobile_static/mobile.js`;
- focused V3 regression tests.

No generated media, cache, logs, scratch files, Brain/provider code, or V2
implementation may be changed.

## 5. Acceptance matrix

| ID | Requirement | Evidence |
| --- | --- | --- |
| R1 | Lightweight summaries remain cheap and mark count unknown | service regression |
| R2 | Home preview returns a count for every evaluated requested project, including known zero | Project Mode regression |
| R3 | Count uses the existing formal-delivery authority and excludes review/process outputs | service regression and adjacent delivery tests |
| R4 | Desktop merges page counts, preserves cache counts, and renders numeric cover/empty labels | browser regression |
| R5 | Mobile has the same count and cache behavior | browser regression |
| R6 | Unknown/error states never become a false `0 张图片` | browser regression |
| R7 | Detail/full-history and ownership behavior remain unchanged | adjacent V3 regression |
| R8 | Python/JavaScript syntax, focused tests, audit, and diff hygiene pass | final-version receipts |

## 6. Delivery status

- Implementation: complete. The home-preview response now returns an
  additive per-project count map; an unreadable index remains unknown rather
  than becoming a false zero. Desktop/mobile cache merges preserve known
  counts across later lightweight summaries.
- Read-only audit: complete. Changed code is limited to Project Mode summary /
  home-preview projection, the shared count contract, desktop/mobile V3
  rendering, and focused regression contracts. No Brain, Provider, Review,
  Retry, generation, media, or V2 path changed.
- Local acceptance: complete. Focused and adjacent V3 regressions passed;
  Python and JavaScript syntax checks passed; `git diff --check` passed.
- VPS acceptance: complete for the runtime implementation commit
  `44048483077a309b28f231684d505585c6f5befd`. It was deployed through the
  governed release procedure to
  `/opt/alchemy-media-agent-releases/v3-release-governed-20260914T221051Z-44048483077a`.
  The active release commit, container environment mount, V3 count field, and
  desktop/mobile count-sync markers were verified. Internal V3 health, V2
  health, and public `/healthz` each returned HTTP 200. The previous release
  remains available for rollback.
- Release receipt: complete. The runtime implementation is on the VPS; this
  final documentation update is a no-code follow-up pushed to GitHub.
