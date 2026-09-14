# Doc308 - V3 Home Project Card Projection And Image Count Repair

Status: implementation contract for the V3 home project-card repair. This
document is the authoritative correction model for the `0 张`/missing-cover
regression found after the Doc301 bootstrap optimization. It changes the
authenticated read projection only; it does not change Brain, Provider,
Review, Retry, generation, output retention, or account ownership semantics.

## 1. Task record and acceptance phase

### 1.1 Objective

The total objective is to make every visible V3 home project card represent
the correct project and an honest image state on desktop and mobile, including
the first page, subsequent pages, slow/error output reads, and cached reloads.

The current phase objective is to implement and verify the smallest complete
repair, then publish the fixed mainline to GitHub and the authorized VPS.

### 1.2 Scope

- Scope: the V3 project-card/home-preview read contract, desktop and mobile
  projections, lightweight-summary interpretation, cache merge behavior, and
  regression coverage.
- Non-goals: creative prompt composition, Brain/aiself transport, provider
  quality, generation lifecycle, output authorization, project ownership,
  visual-asset behavior, V2 code, and database/storage migration.
- Baseline: clean `main` at `e037db54` (`fix: keep V3 home mask until previews settle`).
- Contract revision: `DOC308_V1_HOME_PROJECT_CARD_PROJECTION`.
- Complexity gate: `ESCALATE_REQUIRED`; the repair crosses the Product API
  query contract, Project Mode read projection, desktop, mobile, and cache
  state.

### 1.3 Responsibilities and write boundary

- Main control and sole writer: the current Codex task, writing only the
  allowed files listed below on the unique main checkout.
- Design/reasoning: the correction model in this document and the code-first
  audit that produced it.
- Execution: the current task, after the contract and regression tests are
  frozen.
- Independent audit: a separate read-only audit phase by the main control
  after version freeze. The current environment exposes no callable worker
  Agent, so no independent Agent result is claimed.
- Allowed implementation surface: this document, the V3 project-output route
  handler, Project Mode service, desktop V3 shell, mobile V3 shell, and
  focused V3 regression tests. No generated media, logs, caches, or scratch
  evidence are committed.

### 1.4 Invariants

1. `ProjectMemorySummary.visible_output_count` and
   `latest_thumbnail_urls` from `view=summary` remain a lightweight persisted
   project-card projection. They are not allowed to masquerade as a complete
   output read when the summary intentionally contains zero/empty values.
2. The authenticated server remains authoritative for project visibility and
   ownership. A requested home-preview project ID is filtered through the same
   visibility and archived-project predicates as the existing endpoint.
3. `surface=home_preview` remains delivery-preview-only, non-reconciling,
   review-free, and bounded. The new project scope is additive and does not
   alter callers that omit it.
4. A home-preview response is never treated as complete project history.
   Project detail/history continues to use the existing project-scoped full
   output path.
5. A read failure or incomplete summary must not be rendered as a confirmed
   `0 张` state and must not erase a usable cached project card.
6. A preview output with only `preview_url` remains displayable. URL fallback
   must not weaken private-media authorization or introduce original-file
   reads into the home contract.
7. Load-more project pages must request previews for the newly returned
   project IDs and append them without dropping previews already shown.

## 2. Observed mismatch and root cause

The baseline implementation has five cooperating defects:

| ID | Observed mismatch | Owning layer | Evidence at baseline | Correct authority |
| --- | --- | --- | --- | --- |
| E1 | A lightweight summary returns empty thumbnails and `visible_output_count=0`, and a card prints `0 张` | Browser projection | `_lightweight_memory_summary`; `v3ProjectGroupFromProject`; `mobileV3GroupFromProject` | Summary completeness and output-surface state |
| E2 | Global home preview consumes its quota with projects outside the visible page | Product API / Project Mode | `list_project_outputs(surface=home_preview)` scans recent projects without a page allowlist | Current-page project IDs supplied by the browser, then server ownership filtering |
| E3 | Loading more projects does not fetch their home previews | Desktop/mobile interaction | `loadV3Projects` and `loadMobileV3Projects` only append catalog rows | The new page's IDs trigger an additive preview read |
| E4 | A successful/previous cache cover is overwritten by an empty lightweight summary | Browser cache merge | desktop merge spread order; mobile direct replacement | Non-empty cached cover remains provisional until targeted preview settles |
| E5 | Desktop refuses a result whose item has `preview_url` but no `thumbnail_url` | Browser media projection | `v3OutputStrictThumbImageUrl` only reads thumbnail fields | Thumbnail first, preview fallback, no original download fallback for home cards |

The earlier output-storage evidence showed raw output records and previews
still present on the VPS. Therefore this repair treats the defect as a read
projection/contract failure, not as output deletion or an upstream Brain
failure.

## 3. Frozen correction model

### 3.1 Page-scoped home preview

Add an optional comma-separated `project_ids` query parameter to
`GET /api/v3/creative-agent/project-outputs`. The route parses and bounds
the list, and `V3ProjectModeService.list_project_outputs` applies it only for
`surface=home_preview`:

1. Resolve the requested IDs against visible, non-archived projects owned by
   the authenticated user.
2. Preserve the existing output-index locator and delivery-preview gate.
3. Return at most one formal preview per requested project and at most the
   bounded request limit.
4. If the parameter is omitted, preserve the existing global home-preview
   behavior for compatibility with older callers.
5. If the parameter is explicitly present but empty, return no projects rather
   than silently falling back to a global scan.

The frontend sends the IDs of the currently loaded first page or newly loaded
page. It merges page previews by project ID so loading another page cannot
erase earlier covers.

### 3.2 Honest card state

The lightweight summary remains intentionally incomplete. Desktop and mobile
must therefore distinguish:

- complete project history: a full output surface has settled, so `0 张` is
  an authoritative empty result;
- home preview: one cover may be present, but it is labeled as a cover and
  never as the full count;
- incomplete/failed output read: use an explicit pending/temporarily
  unavailable label, never `0 张`.

This keeps the public summary schema stable while correcting the consumer's
interpretation. A project with no jobs may still say it has not generated an
image; a project with jobs but no settled full history says its image count is
not synchronized.

### 3.3 Cache and failure behavior

When a new lightweight summary contains an empty thumbnail list, merge logic
may retain a non-empty cached cover for the same authenticated project. The
cover is provisional and is replaced by the page-scoped home preview when it
arrives. Output-read failures retain the project catalog and usable card
projection; they set an explicit error state instead of clearing the cache
and manufacturing an empty history.

### 3.4 URL projection

Home cards use `thumbnail_url` first and `preview_url` second. They do not
fall back to `download_url` merely to make a card appear, which protects the
home performance contract. Existing detail/gallery URL behavior is unchanged.

## 4. Implementation plan

1. Add the additive route/handler/service `project_ids` contract with owner
   filtering and focused service tests.
2. Add desktop query scoping, page-preview append/merge, cache-cover
   preservation, honest count labels, and preview URL fallback.
3. Add mobile query scoping, page-preview append/merge, cache-cover
   preservation, and honest count labels.
4. Add desktop/mobile browser regressions for first-page scope, load-more
   scope, cache preservation, error state, and preview-only media fallback.
5. Run focused tests, JavaScript syntax checks, adjacent V3 regressions, and
   an independent read-only audit against this document.
6. Freeze the accepted commit, push `origin/main`, deploy the same commit to
   the governed VPS release path, and perform read-only health/static route
   verification.

## 5. Acceptance matrix

| ID | Requirement | Evidence required |
| --- | --- | --- |
| R1 | Additive `project_ids` route parses safely and preserves project-scoped/full compatibility | route/handler/service test |
| R2 | Scoped home preview returns only requested visible projects, one cover each, with existing delivery gate | Project Mode regression |
| R3 | Omitted scope keeps legacy global home-preview behavior | compatibility regression |
| R4 | Desktop initial and load-more calls carry the correct page IDs; previews append without loss | source contract + browser regression |
| R5 | Mobile initial and load-more calls carry the correct page IDs; previews append without loss | source contract + browser regression |
| R6 | Empty lightweight summaries cannot overwrite non-empty cached covers | desktop/mobile merge regression |
| R7 | Incomplete or failed home reads never claim `0 张` | desktop/mobile browser regression |
| R8 | Thumbnail-only and preview-only outputs both render; no home download fallback is introduced | URL projection regression |
| R9 | Existing project detail/full-history and ownership behavior remains intact | adjacent V3 suite |
| R10 | Syntax, focused tests, relevant regression suite, diff hygiene, and VPS read-only verification pass | command receipts bound to final commit |
| R11 | Final fixed version is independently audited before GitHub/VPS delivery | read-only audit receipt |

## 6. Delivery status

At document freeze: `PLANNED`, baseline `e037db54`, no implementation or
external mutation performed. This status must be updated only after the
implementation version is frozen, tests are rerun, the independent audit is
complete, and GitHub/VPS evidence is bound to the same commit.
