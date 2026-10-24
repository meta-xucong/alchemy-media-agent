# RB10: opt-in health and queue fallback

Implemented on the existing V3 single-image development path; ordinary Generate
and old bridge_only payloads remain unchanged. This is not formal delivery or
production billing acceptance.

Administrator settings `auto_fallback_enabled=false` and `queue_wait_seconds=30`
remain opt-in and bounded. A new request must explicitly choose
`routing_strategy=prefer_bridge` and acknowledge cloud fees/input transmission;
`local_only` wins. Existing authenticated owner, native mode/profile, project,
canonical reference and provider admission remain authoritative. Upstream calls
may charge even while the V3 zero-credit development adapter reports zero debit.

The module consumes negotiated `routing_availability_v1`, stores per-profile
freshness and recovery evidence, and performs one bounded background capabilities
refresh while enabled. A transient failure resets recovery; stale/global-only
revisions cannot refresh a profile. Retry-After persists. Known authorization
failure invalidates cached negotiation. First-ever offline service cannot be
silently treated as a compatible Bridge; previously negotiated compatible service
may support cloud routing for fresh unsubmitted requests during outage.

Queue and health triggers share one policy. Durable route CAS precedes dispatch.
An existing Bridge task must return an exact, immutable withdraw-before-start
proof before cloud dispatch. 404/cancellation/lease expiry/start/unknown/manual
handoff never substitutes. Cloud possible-execution state only queries its exact
native checkpoint; it does not invoke the provider again. Default Bridge task
wire remains bridge_only; the policy lives on Alchemy, not Bridge.

The gateway uses a constrained ProductionImageGenerationProvider continuation,
not another Brain plan or a fake implementation. Frozen prompt/options/ordered
reference hashes are checked and native review-only persistence is reused. Normal
provider-internal retries are retained; the no-duplicate claim concerns cross-route
redispatch, not an assertion that the existing upstream transport never retries.
Recovery changes future unbound requests only. Admin draining does not interrupt
existing-task reconciliation; cancellation propagates to the native target.

Verification at runtime revision 68c079bd: 370 scoped contract/original-path tests
passed. Independent final routing/native47 passed (overlapping). Actual full-host
HTTP matrix with Bridge89f665d passed healthy/unavailable/queue/recovery/restarts/
unknown cases using real native/provider code and synthetic external transport,
auth/Brain/review/clock. Six outputs/reviews; no repeated dispatch after restart.
Final exact published-head browser and legacy CI are tracked in PR37. No real
provider, account refresh, deployment or merge occurred.

Shared contract and local setup live in the companion Bridge repository:
`docs/shared-contract/08_自动回退代码落地与兼容契约.md`,
`docs/implementation/AUTO_FALLBACK_ACCEPTANCE.md`, and
`docs/implementation/WINDOWS_LOCAL_LOOPBACK.md`.
The user's real test uses local Alchemy + Bridge + own Codex CLI on one Windows
computer, with separate environments/data and loopback HTTP. It is still pending.
