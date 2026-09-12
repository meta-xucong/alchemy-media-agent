# Doc301 - V3 Home Bootstrap Performance And V2 Parity

Status: implementation contract for the V3 home loading repair.

## 1. User objective and phase objective

The total objective is to make the V3 home surface feel as fast as the V2
surface without weakening V3 project ownership, pagination, output-delivery,
review, or workspace contracts.

This phase repairs the V3 home read path. It must make the shell interactive
after the project catalog is available, move output and image work behind the
first-paint boundary, and remove the duplicated and unnecessarily full read
paths identified by the code audit.

## 2. Evidence and correction model

The current V3 home path is:

```text
paint -> projects -> global project-outputs -> first thumbnail -> unlock
       -> another global project-outputs request
```

The browser asks for one output but clamps the request to at least twelve.
The project list builds a rich memory summary for each returned project, and
the global output projection traverses project Jobs and output records again.
The thumbnail endpoint also re-reads the output record and validates the full
original image on every request. This is local Alchemy read-path work; Brain
and the upstream aiself provider are not called by these home GET requests.

V2 releases its shell after a parallel resource fan-out. History is optional,
template responses are cached, and image loading is progressive. V3 should
adopt the same critical-path shape while keeping its own V3 contracts.

## 3. Authority, scope, and non-goals

### 3.1 Authorities and invariants

- The authenticated server remains authoritative for project visibility,
  ownership, cursor order, and `total`/`has_more` pagination.
- A persisted project remains authoritative for Standard versus Professional;
  the lightweight list may expose only the safe `metadata.v3_workspace` fact.
- Formal delivery, review-only output, retry lineage, and continuation gates
  remain owned by the existing Product API and Project Mode predicates.
- Existing callers of `GET /projects` and global `GET /project-outputs` keep
  their current full behavior unless they opt into the new read views.
- Output file authorization and canonical-path validation remain mandatory.
  Caching may skip unchanged work only after a stat/version check.
- No Brain, Provider, Review, Retry, generation, storage-retention, or
  account-isolation semantic changes are allowed in this phase.

### 3.2 Allowed files and modules

- `src_skeleton/app/static/app.js`
- `src_skeleton/app/mobile_static/mobile.js`
- `src_skeleton/app/main.py`
- `alchemy_creative_agent_3_0/app/product_api/route_handlers.py`
- `alchemy_creative_agent_3_0/app/project_mode/service.py`
- `alchemy_creative_agent_3_0/app/product_api/outputs.py`
- focused V3 regression tests and this document

No V2 implementation is changed. No generated media, cache, log, or evidence
artifact is committed.

## 4. Contract changes

### 4.1 Lightweight project catalog

`GET /api/v3/creative-agent/projects?view=summary` is an additive read view.
It returns the existing `ProjectListResponse` shape, including templates,
cursor pagination, `total`, `has_more`, and `next_cursor`. Its project cards
use only persisted project fields and `_lightweight_memory_summary`; it must
not call timeline, Job, output, review, reconciliation, or full-context
builders. `view=full` and an omitted view retain the current behavior.

The desktop and mobile frontend home and project pagination requests use
`view=summary`.

### 4.2 Home preview output surface

`GET /api/v3/creative-agent/project-outputs?surface=home_preview` is an
additive global read surface. It returns at most the requested number of
formal delivery preview items, respects authenticated project visibility,
returns no `review_items`, performs no reconciliation, and uses the existing
delivery predicates after using the output store's project index as a
candidate locator. Its `complete=false` marker is authoritative for the
browser: a cover is never counted or labeled as the project's complete
history. Opening a project history view must request the project-scoped full
output surface, even when a home cover is already present. The ordinary
endpoint and project-scoped full/history paths remain unchanged.

### 4.3 Browser first-paint contract

V3 desktop and mobile home initialization must:

1. render cached/local project placeholders when available;
2. await only the summary project catalog request;
3. render an interactive project shell and release the page mask;
4. start one `home_preview` output request in the background;
5. treat thumbnails as progressive media; a failed or slow image must never
   keep the page locked.

Direct V3 route restoration must not create a second catalog request while
the shell bootstrap is active. The auth/session cookie must be established
before a direct V3 bootstrap can issue the protected catalog request.

### 4.4 Read-cache contract

The output store may reuse a fully parsed record index when the storage root
revision is unchanged. `get_output` must retain its direct-file fallback for
generation and cross-process freshness. Canonical original-content and image
validation may be reused only for an unchanged file stat and record digest;
changed files must be revalidated. No authorization check is removed.

The global full output projection also builds one disposable request-scoped
Job/output snapshot and derives both delivery and review projections from it.
This is a read optimization only; it does not replace the existing delivery,
review, owner, or retry predicates and it is never persisted as Job state.

## 5. Implementation plan

### P0 - critical path

- add `view=summary` to the V3 project route and service;
- switch desktop V3 catalog calls to the summary view;
- remove the initial global output wait and first-image wait;
- run one background home-preview request after the catalog render;
- deduplicate direct-route initialization and move route restoration after V3
  session-cookie synchronization.

### P1 - home read model

- add the `home_preview` global surface;
- use the project output index plus existing delivery gates instead of the
  full global delivery/review traversal;
- preserve default full output behavior for detail/history callers.

### P2 - media and record reads

- use the parsed output index for repeated `get_output` calls when its
  revision is current;
- cache canonical integrity/image validation by unchanged file stat and
  expected digest, invalidating on any observed mutation;
- keep private media authorization and canonical path checks intact.
- share one request-scoped Job/output read snapshot between global delivery
  and review projections; home preview uses the bounded project index and
  only resolves candidate Jobs needed by its existing delivery gate.

## 6. Acceptance matrix

| ID | Requirement | Evidence |
| --- | --- | --- |
| R1 | Summary catalog has the old response shape and pagination | route/service regression test |
| R2 | Summary catalog does not read Jobs, outputs, timeline, review, or context | instrumented service test |
| R3 | Home preview is delivery-only, owner-scoped, non-reconciling, and bounded | service regression test |
| R4 | V3 shell unlocks before output/image work and makes one background preview request | desktop browser/contract test |
| R5 | Direct V3 route cannot duplicate the catalog request | frontend contract test |
| R6 | Full project/output compatibility path remains unchanged | existing project/output regression suite |
| R7 | Record/integrity caching preserves direct fallback and revalidates changed files | output-store regression test |
| R8 | JavaScript syntax, focused V3 tests, relevant full regression, diff hygiene pass | reproducible commands and exit codes |
| R9 | Final fixed version is independently audited before GitHub/VPS delivery | separate read-only audit receipt |
| R10 | A partial home cover cannot masquerade as complete history; opening history loads the full project surface | desktop/mobile contract test and scoped-history regression |
| R11 | Global delivery and review reads share one request-scoped Job/output snapshot | instrumented snapshot regression |

## 7. Delivery gates

The implementation is not accepted after a phase-level test alone. The final
version must have: a clean diff review, focused and relevant regression tests,
independent read-only audit, mainline integration re-test, GitHub push, VPS
deployment, VPS health/read-only route verification, and a report that names
any unverified browser or authenticated timing limitation.
