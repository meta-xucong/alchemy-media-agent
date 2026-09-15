# Doc313 - V3 Home Review-Only Image Projection Repair

Status: implementation complete; local regression accepted; VPS acceptance pending
Contract revision: `DOC313_V3_HOME_REVIEW_PROJECTION`
Upstream authorities: Doc93 reference channels, Doc94 shared visual runtime,
Doc310 formal home count synchronization, and Doc312 legacy media authorization

Narrow supersession: this document changes only the home-card presentation
described by Doc301 and Doc310. Doc309's timeout/newest-first behavior and the
formal delivery/history/review boundaries remain authoritative.

## 1. Total objective and current phase

The total objective is to make existing V3 project media honestly discoverable
from the home project cards while preserving formal-delivery, review,
selection, continuation, ownership, and media authorization boundaries.

This phase addresses the home read projection only. The pre-fix source returns
valid image-bearing outputs in a project-scoped `review_items` collection, but
the home surface intentionally drops that collection and renders the same
`0 张图片` label as a truly empty project. On the VPS this affects most recent
projects even though their scoped reads contain review-only images.

## 2. Observed mismatch and responsible layer

The mismatch is a Project Mode public projection plus desktop/mobile rendering
defect, not an upstream Brain/provider failure and not a media-file loss:

1. The project-scoped full read classifies withheld, rejected, or superseded
   image records as `review_items`.
2. The home preview returns formal `project_output_counts` and legacy
   `project_history_counts`, but hard-codes `review_items=[]` and has no review
   count or cover projection.
3. The browser therefore sees formal count zero, history count zero, and no
   cover, then displays `0 张图片`.

The formal delivery predicates remain authoritative. Existing review pixels are
not promoted to formal delivery merely because they are shown as a card
preview.

## 3. Frozen correction model

### 3.1 Separate three public facts

The home response gains two additive fields:

- `project_review_counts`: exact image-bearing review-only count for each
  evaluated visible project;
- `project_review_preview_items`: at most one safe, compact, image-bearing
  review-only item per project for card artwork.

`project_output_counts` remains the formal final-delivery count and
`project_history_counts` remains legacy history-only count. A known formal zero
is still a formal zero; it is not rewritten to the review count.

### 3.2 Safe review cover

The review cover is a display-only projection. It must:

- be produced by the existing owner, lifecycle, image, review, retry, and
  failure predicates;
- carry `review_only=true` and a `home_review_preview` marker;
- expose only safe media pointers and display identity;
- remain absent from `items`, `history_items`, formal counts, selection,
  continuation references, and provider input resolution.

The home card label must make the state explicit:

- formal only: `N 张图片`;
- review only: `N 张待复核图片`;
- formal plus review: `N 张图片 · M 张待复核`;
- history remains separately labeled as historical media.

### 3.3 Read performance

The home path must reuse one request-scoped output/Job snapshot. It must not
perform one full project-scoped review request per card, invoke the full
history deserializer, or extend the first-paint mask merely to load review
details. The output index remains a candidate locator; exact output and Job
predicates remain the authority. If the bounded index cannot be evaluated, the
review count remains unknown rather than becoming zero.

Job state is read lazily through the existing newest-first projection. A home
project is given a bounded candidate budget; when the indexed Job set exceeds
that budget, the newest candidate may still supply a safe cover, but exact
formal/review counts are omitted and rendered as unknown. An index read uses a
sentinel record so truncation is never reported as complete.

Cover, formal-count probing, review probing, and legacy history share one
newest-first bounded candidate set. They do not each open an independent
64-Job window, and the history adapter receives only records belonging to that
same set.

For declared project Jobs, the home snapshot also performs a bounded
compatibility read through \`list_by_job()\`. This covers older output records
whose \`metadata.project_id\` is absent even though the project still owns the
Job. The fallback is limited to the same 64-Job budget; a failed or incomplete
fallback omits exact maps instead of recording a false zero.

Output-only legacy projects receive the same newest 64-job/record boundary in
the history adapter. The home path never expands that compatibility branch
into an unbounded Job walk; when its indexed candidate set exceeds the bound,
the history count is omitted and the visible state remains explicitly
unsynchronized.

### 3.4 Desktop/mobile/cache parity

Desktop and mobile must merge review counts and review covers by exact
project ID in one response-level update. A successful response clears stale
home count/cover slots for the requested projects before applying current
known maps; omitted map entries become unknown. Direct response-level
\`*_known\` fields are authoritative and cannot be restored by an older nested
\`memory_summary\`. A failed request may retain cached artwork only with an
explicit stale/error state. A review cover may be cached for home artwork
only; it must not become a generated-output collection item. A one-cover
preview must not be used as an exact count while the corresponding map is
unknown. The explicit full-history surface may also be page-limited; its
currently loaded group length is not an exact total. Desktop and mobile may
render an exact full-surface count only from an explicit known count set;
otherwise they show the known portions plus \`数量未同步\`.

## 4. Non-goals and isolation

This repair does not change Brain, Provider, generation modes, review
decisions, retry budgets, formal delivery, V2, specialized template
deliverables, reference inheritance, selection, continuation admission,
ownership fallback, or media-route authorization. It does not mutate existing
VPS project/output records or reclassify a withheld output as deliverable.

## 5. Acceptance matrix

| Case | Formal count | Review count | Home cover | Formal collection |
| --- | ---: | ---: | --- | --- |
| Formal delivery only | N | 0 | formal | unchanged |
| Review-only pixels | 0 | M | labeled review-only | empty |
| Formal and review pixels | N | M | formal preferred | formal only |
| Legacy history only | 0 | 0 | historical | unchanged |
| True empty project | 0 | 0 | empty | empty |
| Unreadable bounded index | omitted | omitted | no false cover | unknown |

Required evidence:

- Project Mode service regression for formal/review independence and safe
  preview output;
- desktop and mobile browser regressions for labels, cards, and cache merge;
- syntax, diff, focused V3 regression, and independent code audit;
- authenticated VPS browser verification showing review-only counts/covers for
  the affected projects while scoped full reads still classify them as
  `review_items` and formal collections remain unchanged.

## 6. Implementation receipt

The bounded implementation adds the two additive home response fields,
reuses the request-scoped Project Mode snapshot, adds a bounded declared-Job
compatibility read, and updates desktop/mobile count, cover, cache, and
error-state projections. Legacy output-only projects remain on the existing
history adapter and are not scanned as modern review projects; that adapter is
also capped at the newest 64 indexed candidates. Local focused and adjacent
V3 regressions, syntax checks, and diff-hygiene checks have passed.
Independent audit and authenticated VPS browser acceptance remain release-gate
evidence for this document.
