# RB09: honor upstream retry deadlines

## Correction model

The shared HTTP contract requires respecting Retry-After on 429/503. The client
previously discarded that header and both preview and native reconciliation used
only a local 2–60 second backoff, allowing an earlier retry than the server asked.

Keep the existing single-request client and bounded coordinator. Parse delta
seconds or a timezone-bearing HTTP date into an absolute deadline on BridgeError.
The shared PreviewService.tick (also inherited by NativeBridgeService) persists
the later of that deadline and the existing local backoff, then releases its lease.
Do not sleep in a reconciliation step, cap a valid server deadline to 60 seconds,
change request/origin/import/ACK identities, or alter native authority.

The module's store preserves this retry floor when cancellation or review reopening
requests an immediate poll, including after restart. Cancellation intent is still
recorded immediately; its remote reconciliation waits for the upstream deadline.
Missing/malformed hints retain existing bounded backoff. Past dates and zero wait
cannot shorten the local backoff. This affects only module-owned records and HTTP
retry timing, not ordinary generation, review policy, delivery or billing.

## Verification

Focused synthetic cases cover both HTTP statuses, delta seconds, HTTP dates,
zero/past/absent/invalid hints, both coordinators, waits longer than 60 seconds,
restart eligibility, released leases, cancellation, no immediate repeated HTTP
request, and stable request identities. No real provider or account is exercised.

Local verification on 2026-10-21 used the existing credential-free mock wrapper:
- All top-level Bridge contract tests: 245 passed (including the initial 24 retry
  cases), with existing FastAPI lifecycle deprecation warnings only.
- The final retry test file, expanded with zero/past-date scheduler cases:
  28 passed. The four added cases change no production code.
- API smoke plus V3 minimal UX/scenario/generic-export-gate selection: 67 passed.
- Whitespace check passed. No browser, deployment or real-tool acceptance claimed.
