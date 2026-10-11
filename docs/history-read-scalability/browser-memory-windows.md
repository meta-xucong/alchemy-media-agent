# Bounded browser history windows

## Correction model and approved compatibility change

PR #29's demand-loading work bounded each transport page, but every Load more
appended to permanent module arrays and every explicit favorites request scanned
and retained all history. Its growing render limit also rebuilt an unbounded
number of cards. This was a browser retained-state/rendering problem; smaller
API pages or backend indexes alone did not solve it.

The follow-up replaces accumulated history with explicit, revisitable windows.
This intentionally supersedes the earlier `v2-and-demand-loading.md` statements
that each gesture always appends to all prior cards and that complete favorites
are eagerly scanned. It is a scoped compatibility change, not silent history
truncation. V3 behavior, account overview samples, and Provider configuration
remain outside this correction.

## Window and access contract

- Each V1/V2 module retains at most 72 raw rows in its current window. Transport
  requests remain at most 24 rows. Within a window, Load more reveals 24, 48,
  then up to 72 cards. At the boundary, Next group replaces the window.
- Previous group refetches the preceding 72-row raw range. Each mode keeps one
  numeric position, `all` and `favorites`; there is no growing cursor map, page
  map, object cache, or retained array of visited records.
- Labels identify the raw source range and total, plus the number of cards
  displayed in this window. They do not claim that earlier records remain
  loaded. An empty/mock-only window still exposes Next and, when applicable,
  Previous. Every older range remains reachable.
- V2 mock filtering and ID deduplication do not advance offsets by displayed
  count. Offsets advance by the raw response length. Each gesture reads at most
  three transport pages and never crosses the 72-row raw window boundary.
  Buffered renderable rows are shown before moving to the next window.
- Explicit favorite filters and pickers use additive `favorite=true` on the
  existing V1 history and V2 history/account-history endpoints. Omitted/false
  remains ordinary history; the response shape remains `items,total` with the
  existing offset/limit semantics. The server filters before pagination and
  returns the exact visible-favorite total. The browser does not collect all
  favorite IDs or scan all history. Favorite-all users are still bounded.
- Closing a picker restores the ordinary browsing position by refetch, unless
  the ordinary grid's favorite-only filter remains active. This deliberately
  trades a bounded read for retaining a second payload window.
- Both the grid and the picker render at most 72 image cards independently.
  A selected reference or revision may retain its existing single selected
  item; selection does not create an unbounded collection.

## Hero, mutation, and authenticated media

The ordinary latest-history Hero has a separate bounded sample of at most 24
rows and still displays at most eight slides. Loading old/favorite windows does
not replace it with old/favorite results. When a favorite-only entry has no
ordinary sample, the Hero makes its own single-flight ordinary demand only if
the Hero is visible. It uses 24-row transport and at most three sparse refill
pages, retaining no more than 24 renderable rows. Hidden mobile sheets/pickers
do not cause these requests. A failed Hero request remains an error rather than
an empty-success substitute for ordinary history.

Favorite mutations update the cached Hero favorite bit and invalidate filtered
windows/totals without an unnecessary ordinary Hero reread. Deletion prunes the
deleted item from the sample and refreshes a stale sample only when visible.
Auth changes clear every window and the Hero. History, Hero, and favorite/delete
completion use owner token/epoch fences so a prior account cannot populate the
new account's retained state. Closing/navigating away stops subsequent refill
pages and hidden image binding.

Replacing or clearing history, picker, or ordinary Hero DOM explicitly revokes
its authenticated object URLs, clears image handlers, and invalidates pending
image binding tokens. A late detached-image resolver revokes its newly created
URL rather than attaching it. V1's direct card-delete path performs the same
cleanup before removing the card. Merely removing DOM nodes would not release
these browser-managed Blob URLs.

Per module the persistent raw payload bound is 72 window records plus 24 Hero
records, rather than a function of pages visited. Both products can retain
their own bounded state when navigation changes. The shared normalized active
Hero retains at most eight projections, and bounded account samples remain
separate: V1 48, V2 72, usage 100 per product, template enrichment at most 30.
An in-flight response/work array is also page/window bounded; these bounds are
not a claim of a byte limit for arbitrarily large individual payload fields.

## Verification receipt

At this follow-up's frontend freeze:

- `node --test tests/*.test.mjs`: **169 passed**, including the existing V3
  terminal/browse contracts and direct-Lab provider/settings dependency tests.
- The actual shipped functions execute under Node VM against request spies and
  a DOM fixture. New coverage traverses hundreds of pages, asserts retained
  payload/card/Blob bounds, refetches prior windows, exercises empty sparse
  windows through their actual buttons, switches modes during pending reads,
  checks filtered favorite paging, preserves ordinary Hero state, and verifies
  auth-fenced mutation/late-Hero behavior and delete cleanup.
- The two frontend static API smoke tests pass: **2 passed, 95 deselected**, six
  existing FastAPI lifecycle deprecation warnings. Only their obsolete private
  call-spelling expectations changed; account 48/72 assertions remain.
- JavaScript syntax checks and `git diff --check` pass. All **715 V3-named
  function bodies** are byte-for-byte unchanged from `fd259486` (468 desktop,
  247 mobile), checked with parser-validated function extraction.

### Real Chromium measurement is blocked, not passed

`scripts/probe_browser_history_windows.mjs` is a prepared, syntax-checked focused
Chromium renderer probe. It injects the actual published functions into real
DOM, intercepts all HTTP requests with synthetic 50,000-row history fixtures,
exercises 360 ordinary and 360 favorite gestures per shell/product, and records
CDP post-GC heap/DOM counters plus active object URL counts. Its media resolver
uses small synthetic PNG Blobs, not production image transfer/authentication.
It is a renderer probe, not the full product's browser navigation or UX test.
Its browser-independent `--check` mode also passed: 41 shipped functions from
each shell, plus 26 desktop and 22 mobile numeric constants, were extracted and
parser-validated as complete combined programs before browser launch.

Invocation in an environment that permits Chromium:

```sh
PLAYWRIGHT_MODULE_PATH=/path/to/node_modules/playwright \
CHROMIUM_EXECUTABLE_PATH=/path/to/chromium \
node scripts/probe_browser_history_windows.mjs /tmp/history-browser-probe.json
```

In this cloud executor Chromium aborted before loading any page at
`process_singleton_posix.cc:297`: `socket() failed: Operation not permitted`.
A single approved sandbox-escalated retry had the same runtime restriction.
The browser probe has therefore **not executed**, and no real Chromium heap,
RSS, layout, focus, or image-decode result is claimed. The script itself needs
its first executable-environment validation. Node's object/card assertions are
not a substitute for actual browser heap measurement. No Provider, production
data, VPS, deployment, or user-account mutation was involved.

The `history-browser-contracts` GitHub-hosted job now installs pinned Playwright
`1.62.1` (verified with the official npm registry) and its official Chromium into
temporary runner paths, runs this probe with a
bounded timeout, and uploads the JSON/log artifact. It uses no additional
permissions or secrets. Its result must be verified against the actual pushed
head before any real-browser measurement is reported as passed. If no executable
override is supplied, the probe uses Playwright's installed Chromium.
