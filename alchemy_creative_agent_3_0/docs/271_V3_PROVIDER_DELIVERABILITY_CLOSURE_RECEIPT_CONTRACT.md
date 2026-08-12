# Doc271 V3 Provider Deliverability Closure Receipt Contract

Status: Phase 0 shared-foundation design and deterministic red-contract
authority. It defines a narrow response to an already observed, explicit
upstream Provider policy refusal. It does not alter a user goal, select a new
route, make a Provider request, or guarantee that any upstream will deliver a
policy-refused image.

## 1. Observed Failure And Correction Model

Read-only production evidence for `project_65432102a2` records a fresh
Professional E-Commerce job, `job_6594a9620b`, reaching terminal `blocked` at
2026-08-12 10:54Z with `provider_policy_blocked`. Its final Doc269 physical
reference package was correct: one uploaded `product_truth` original followed
by three locked `people_identity` Visual Asset Library face references. The
request retained the user's child/minor and swimwear facts; no sexualized
language was detected. The upstream returned an explicit policy response and
no pixels. The earlier `job_e75abeb646` is a similar historical terminal
record.

This is not evidence that the physical plan, product/People binding, browser
receipt, or reference count is wrong. It is also not authorization to replace
the subject with an adult, weaken the garment fact, inject history, retry a
route, or rotate providers to evade an upstream decision. The observed
product defect is that a later explicit continuation can repeat the same known
undeliverable route and present a new preparation cycle.

The correction is a server-owned, append-only
`ProviderDeliverabilityClosureReceipt`. It records only an explicit upstream
content-policy fact for one exact immutable delivery binding. Before a *new
explicit command* can create a Job or invoke Brain/provider materialization,
the owning server compares the command's independently resolved binding with
the receipt. An exact match closes locally with a receipt-scoped, actionable
terminal projection. It creates no Job, plan, Provider request, automatic
retry, or automatic resubmission.

## 2. Scope And Authority

Doc117 and Doc124 remain the authority for Provider classification,
no-pixel/provider-policy closure, public safety, and no-policy-evasion. This
document adds no classifier based on keywords, age, garment, template, or a
generic HTTP 4xx. It consumes only durable, explicit evidence already
classified as `provider_policy_blocked`, whose upstream evidence includes a
bounded `content_policy_violation`-type fact.

The receipt is shared foundation data, but its first consumer is the explicit
Professional E-Commerce Project Mode command. General and Photography do not
inherit its command suppression, UX, template rule, or route behavior merely
because they use a Provider.

The following authority remains unchanged:

| Authority | Continues to own |
| --- | --- |
| Doc93 | channel contribution and prompt-owned versus reference-owned facts |
| Doc261/265 | uploaded originals, selected continuation, review/history separation, and durable same-project selection |
| Doc263 | complete product-truth pool and selected projection admission |
| Doc269 | exact final physical renderer plan and adapter input sequence |
| Doc268 | server-issued same-project job receipt and browser current-action ownership |
| Provider | capability declaration, one operation's execution, and explicit upstream policy classification |

Neither Brain, browser, Project Mode, template, Product API, nor Provider may
have competing final selection authority. Product API/Project Mode resolves
the binding from its existing authorities; Provider supplies only durable
execution evidence; the receipt comparison is server-owned; the browser
projects the returned terminal state only.

## 3. Immutable Receipt

### 3.1 Creation predicate

A receipt may be created exactly when all of the following are true:

1. A server-issued, same-project Job reached terminal `blocked` with no
   pixels/delivery.
2. Its durable Provider execution summary is explicitly classified
   `provider_policy_blocked` and contains attributable
   `content_policy_violation`-type evidence. A generic
   `image_edit_invalid_request_unattributed`, an ambiguous 400, a timeout,
   a local admission failure, or a browser warning is insufficient.
3. The Job's canonical user-goal/prompt binding, source/reference binding,
   locked Visual Asset binding, Provider capability/model/operation/route
   identity, exact Doc269 per-output plan, and a canonical terminal-Job
   receipt/audit digest can be read and verified. The terminal receipt digest
   authenticates the exact same-project terminal Job, terminal status, and
   durable Provider failure summary; it cannot be inferred from surrounding
   metadata.

For legacy recognition, those Provider identity facts must already be durable
safe execution facts on the terminal record. The authoritative source is the
server-written Provider failure execution audit, including its declared
capability ID, Provider name, model, operation, and configured route identity;
the terminal-Job receipt digest canonically covers that audit together with the
same-project terminal status and explicit Provider failure evidence. Current
configuration is not evidence of what an old operation used and must not be
substituted for missing model, capability, operation, route identity, or
terminal receipt evidence.

The receipt is append-only and canonical. It must bind at least:

```text
schema_version, authority, receipt_id
project_id, terminal_job_id, terminal_job_receipt_digest
canonical_goal_prompt_digest
reference_binding_digest
  - ordered source/reference IDs, actual content SHA-256, role, channel
  - locked Visual Asset/version/evidence binding digest
provider_capability_id, provider_name, model, operation, route_identity
physical_plan_digest(s), output-index binding(s), created_at
policy_evidence_class = explicit_content_policy_violation
```

`canonical_goal_prompt_digest` is the server-built pre-dispatch command
binding: current project goal, explicit command direction, selected template,
and other existing server-owned prompt inputs in canonical form. It is not a
browser digest and it is not a request to run Brain merely to recreate a final
renderer prompt. The terminal receipt may retain a separately verified final
prompt/plan audit digest, but a final renderer prompt or a job-bound Doc269
plan cannot be the pre-dispatch comparator because neither exists before the
new command is admitted.

The receipt stores safe identifiers/digests for durable audit but never raw
provider messages, routes/credentials, local paths, full prompt text, or a
policy rationale in a public projection. Browser/request metadata cannot
author, supply, patch, or override any receipt fact. A public forged receipt
or policy field is ignored/rejected without Job or receipt mutation.

The durable receipt may bind `terminal_job_id` and
`terminal_job_receipt_digest`, but the public current operation may expose
only a newly issued opaque `closure_receipt_id` and safe next-action IDs. It
must not expose a historical terminal Job ID, terminal receipt digest, source
binding, final-plan binding, canonical goal/prompt binding, source path, or
content hash. A closure operation is never a historical Job represented as a
current command receipt.

### 3.2 Exact comparison and closure

For a new explicit Professional E-Commerce command, the server must resolve a
server-owned **pre-dispatch comparison binding** from the current active
Doc263 product facts, Doc265 selected-continuation admission, locked People
binding, and declared configured provider capability. It compares that binding
to a verified same-project receipt *before* Brain planning, job-bound Doc269
physical-plan materialization, Provider dispatch, retry ownership, or Job
creation. The terminal receipt's actual Doc269 plan remains audit corroboration
for the original no-pixel attempt; it is not recomputed by starting a new Job.

Only equality of every bound field may close the command. A changed canonical
goal/prompt, source SHA/role/channel/order, locked visual asset version or
evidence, selected continuation, provider capability/model/operation/route,
project, or malformed receipt makes it non-matching. It may not silently reuse
the old closure. A non-matching command follows its normal server-issued
creation path, subject to all existing admissions.

An exact match returns a receipt-scoped terminal `needs_input` or
`delivery_route_unavailable` **project-command closure**, not a
`ProductJobStatus` and not the historical terminal Job as a successful create
response. Its public shape must identify the closure safely and contain no new
or historical `job_id` as the active command receipt. It has one safe next
action such as editing the stated goal/reference facts or reviewing an
explicitly configured and capability-proven route option. It must report `loading=false`,
`busy=false`, terminal progress, and no polling/recovery timer. It must not
claim an image exists or show a raw provider code/exception/Job ID/path/hash.

A persisted `ProviderDeliverabilityClosureReceipt` is verified before use.
An absent, malformed, internally inconsistent, or terminal-digest-mismatched
receipt fails open: it remains durable audit/history only, is not repaired or
rewritten from current configuration, and cannot suppress a fresh explicit
command. This is distinct from a legacy terminal Job that has no closure
receipt at all.

The normal deliberate retry button remains a user action, but an unchanged
exact closed command remains locally closed. The user must explicitly change
the goal, hard reference binding, or select a separately configured route
whose capability evidence proves support for all frozen hard inputs. No blind
reroute, automatic alternate-route attempt, adult substitution, age rewrite,
garment deletion/weakening, continuation inference, or history injection is
permitted.

## 4. Historical Compatibility

For an existing project, Project Mode may read a legacy append-only terminal
Job such as the `job_6594a9620b` shape and construct a receipt only if every
required binding and explicit policy fact verifies. It must not replay,
generate from, rewrite, or otherwise mutate that Job. A partial, ambiguous,
or unverified historical record remains ordinary history and cannot block a
new command. In particular, missing canonical command binding, product/source
SHA-role-channel-order evidence, locked Visual Asset binding, Provider
capability/model/operation/route evidence, final per-output physical plan, or
same-project terminal Job linkage is fail-open for recognition: the historical
record stays history and produces no closure. A malformed record cannot be upgraded using
browser metadata, a new Brain pass, a new Job, or a Provider call.

A missing or mismatched terminal-Job receipt/audit digest has the same result.
Project linkage alone is not an authentication substitute for the exact
terminal receipt.

The recognized receipt is attached to the current project view only as a
sanitized operation. A Doc271 command closure is deliberately not a Doc268
job receipt: Doc268 continues to keep a real newly accepted/in-flight Job
receipt current when one exists, while Doc271 prevents an unchanged command
from pretending a historical terminal Job was newly accepted. History cannot
become a substitute current Job. The browser may navigate to history
deliberately, but historical delivery/review state cannot be used as an input
or an automatic continuation.

## 5. Negative Rules

The receipt must not:

- globally block `child`, `minor`, `swimwear`, apparel, or any other request
  vocabulary;
- infer a policy refusal from a generic invalid request or any unclassified
  4xx;
- apply across projects, provider models, operations, routes, or changed
  reference bindings;
- convert a policy block into successful delivery, review approval, or a
  retry candidate;
- alter General, Photography, Product Truth, People identity, continuation
  selection, review, or route capability policy.

## 6. Browser Projection

Desktop and H5 consume only the server-projected terminal operation. On an
exact closure they atomically retire busy/progress/recovery ownership and
render one safe action. They must not issue a POST, automatically retry,
display preparation/generation/recovery copy, leak durable/provider detail, or
replace the current exact receipt with a historical Job. The browser cannot
manufacture a closure by sending metadata.

## 7. Phase Boundaries And Acceptance

Phase 0 creates this document and deterministic red contracts only. It does
not change Python/JS runtime, stores, Provider configuration, project/job
records, `main`, VPS, or live jobs.

Phase 1 may add the minimum server persistence/comparison and E-Commerce
projection after separate audit. It must first prove the existing Product API
and Project Mode binding sources used for each receipt field. No implementation
may treat this contract as assurance that the upstream will deliver the
policy-refused combination.

Acceptance requires deterministic proof that:

1. an explicit policy block creates one exact receipt with no public raw
   policy detail;
2. an exact same-project command creates no Job/plan/Provider call/retry;
3. changed goal, reference, locked binding, provider/model/operation, or
   project does not reuse the receipt;
4. forged browser policy/receipt fields cannot create or alter a receipt;
5. complete legacy evidence, including a verifiable terminal receipt digest,
   is recognized read-only without replay while incomplete or malformed
   legacy/current receipts fail open;
6. desktop/H5 close terminal state without preparation copy or POST; and
7. General and Photography remain unaffected.
