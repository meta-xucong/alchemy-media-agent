# RB26: VPS adaptation, local acceptance first

## Scope and order

This follow-up builds on Alchemy PR #39 (`bb91ba3e`) and Bridge PR #2
(`80f155d4`). It does not replace or overwrite ongoing local optimization.
The order remains: cloud implementation and synthetic checks, local update and
acceptance, then a separately authorized VPS deployment and remote acceptance.
Neither PR authorizes merging, deployment, network exposure or paid calls.

Alchemy branch: `codex/vps-bridge-production-adaptation-20261025`.
Bridge branch: `codex/remote-source-production-adaptation-20261025`, PR #3,
`16e020e82f90da7f6f739642cf2fd66d7bcd926f`.
Use the exact Alchemy head recorded in the PR, not a guessed SHA from this file.
The branches include their respective earlier adapter work; these are stacked
review diffs, not instructions to apply isolated patches onto an unrelated main.

## Local handoff

1. Read AGENTS.md, RB20 and RB21–RB25. Record current checkout and running process
   revisions. Preserve local uncommitted changes, configuration, databases,
   unknown tasks and actual generated files. Use a separate worktree or reconcile
   local commits deliberately; do not reset or overwrite the active test checkout.
2. Install/update through the existing local setup procedure. Local default paths,
   explicitly permitted loopback HTTP, authentication-disabled development and
   the original Bridge example remain compatible. Do not apply VPS systemd or
   Compose overrides locally, and do not replace local settings with the remote
   example merely to run these regressions.
3. Run normal product tests and the new owner-isolation, cache-retirement and
   capacity tests. Run the source HTTP contract runner using the companion's
   locked dependencies. These use synthetic pixels and fixtures, not a real CLI.
4. Verify completed image replay after restart, history deletion and interrupted
   ACK. Native images must remain available unless deliberately deleted; missing
   or deleted media must never trigger replacement generation. Unknown execution
   and unresolved settlement must retain their recovery data.
5. Run V1/V2/V3/Lab's existing local real acceptance only within separately agreed
   account, material and spending limits. Include current prompt canvas versus
   stale UI parameters, original image hash/dimensions, review, owner and billing
   outcome. Do not make repeated paid calls to diagnose unknown status.
6. Report exact two revisions, startup configuration differences (redacted),
   test counts and errors, task/receipt correlation, and pass/fail/not-run phases.
   Do not include tokens, user sessions, private prompts or personal media in a
   public PR or report. Local changes made after these candidates need their own
   integration review before they become the VPS release candidate.

## What changed, and what did not

- VPS candidate/activation now installs the neutral package in V2's independent
  environment as part of the normal future update. The old VPS lacking this new
  dependency is not itself a fault and requires no manual hotfix now.
- VPS-only shared storage wiring and read-only preflight preserve authentication
  configuration and require safe dedicated persistent paths. The base local
  Compose file is unchanged. No data or credentials are automatically migrated.
- V2 query/resume/cancel use one persisted owner authority. Consistent historical
  frozen/output provenance is accepted; ambiguous ownerless historical jobs are
  not exposed to arbitrary authenticated users. No administrative impersonation
  bypass or silent ownership assignment is added.
- Completed duplicate transport payloads can be retired only with explicit native
  completion and ACK/API completion evidence. Native images and minimal task,
  receipt and idempotency identities remain. SQLite freed pages are reusable;
  this is not a promise of immediate physical file shrink or secure erasure.
- Bridge object capacity is optionally configurable and diagnosed through its
  authenticated API. Local defaults are unchanged. The remote example explicitly
  opts into safe retention; input size/pixel limits have not been silently raised.
- Cross-process TCP tests cover real socket response loss and process restart.
  Production timeout defaults are unchanged; HTTP activity timeout is not a total
  image-generation deadline.

## Before later VPS deployment

The topology is VPS Alchemy/Veyra authority → trusted source HTTPS API → local
Bridge/Agent/Codex. No shared filesystem and no Bridge callback are required.
Only a source credential belongs on Alchemy; user sessions and CLI credentials
stay with their existing authorities. Stable endpoint/workspace identities matter
for recovery; do not copy active local ledgers and change their endpoint.

Use RB21/RB24 and the companion remote runbook for the read-only preflight and
actual HTTPS fixture checks. Test A/B account isolation, permissions, insufficient
balance, lost debit response, offline local computer, slow transfers and original
task recovery. Then run separately authorized real generation/billing acceptance.
An HTTPS example is not an installed tunnel; no firewall, credential or security
change has been performed by these patches. Nginx configuration needs actual
syntax/certificate/runtime validation in its chosen environment.

Do not deploy until these live acceptance boundaries and the exact final candidate
CI are resolved. A green mock suite does not prove the current VPS configuration,
Windows power-loss durability, real tool parameters, account status or billing.

## Cloud verification receipt

Final pre-publication V2 full suite: 998 passed, one framework warning.
Cross-product transport/canvas/core and deployment selection: 414 passed, ten
existing framework warnings. Bridge complete locked suite: 274 passed. These
selections overlap; do not add their counts as independent coverage.
Independent final late-ACK/core/product review: 154 passed (overlapping).
Deployment workflow functions were exercised with no-network command doubles.
The actual cross-process fixture discarded create/download/ACK replies and
restarted Bridge: two admitted tasks still produced exactly two create calls.
Exact published-head GitHub CI is recorded in the PR, separately from these
cloud checks. Historical completions without a retirement intent are not bulk
migrated; they remain protected and can be reconciled through owning lifecycles.
