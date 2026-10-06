# Doc333 — V3 Result Consistency Change Impact And Data Safety

Status: **PLANNING ONLY**. No user data, Brand Profile, generated output, production configuration, or service was changed by this documentation packet.

## 1. Compatibility boundary

### Invariant-preserving corrections

The planned changes should be derivable from existing V3 contracts:

- Doc321 already defines exact output-scoped review/delivery eligibility and permits an eligible output to survive a held sibling.
- Docs 95/96 already require comparing attempts and retaining the best reviewed output, not blindly choosing the newest retry.
- E34/Doc280 already separate ordinary final delivery from retained review/history pixels and derive the public view from server-owned review/output facts.
- Existing Product API selection and Brand Memory types already carry asset/candidate selection and accepted reference data.
- Existing provider adapter and Anthropic headers elsewhere in this repo establish the minimal Brain transport repair.

The implementation should not add a new storage table, lifecycle enum family, duplicate “approved IDs” store, user control, retry state, or provider SDK. If one becomes necessary, stop for explicit API/data compatibility review before changing it.

### Public response compatibility

- Prefer correcting the current response projection and preserving existing schema fields.
- Existing explicit unreviewed candidate browsing may continue where already supported, but its `not_evaluated`/review-pending nature must remain explicit in downstream facts.
- Formal selection may begin rejecting requests that were previously silently accepted. The error must identify the ineligible/unknown selection without exposing private provider evidence.
- Any required new status enum, changed response schema, or changed consumer contract is outside this TaskSpec until migration and compatibility tests are documented.

### Provider compatibility

- OpenAI default URL applies only when the user has not configured a custom base. Preserve custom compatible gateways.
- Anthropic header addition should not change the request body or other provider headers.
- Do not upgrade provider SDKs or globally rewrite provider defaults as part of these defects.

## 2. Durable data behavior

### Brand Memory

- New writes after the fix must be limited to exact selected eligible assets/references.
- Existing Brand Profiles are immutable within this repair. Do not bulk-delete, rewrite, or “repair” prior references based on guesses.
- If a later user-authorized audit examines history, it must be read-only, record affected IDs/counts and source associations, distinguish confirmed from ambiguous contamination, and stop before modifying stored profiles.
- Any cleanup proposal needs a separate exact target list, backup/restore plan, and explicit authorization.

### Review and output history

- Retry outputs and their review evidence remain append-only.
- Correcting the final winner projection must not erase superseded, failed, manual-review, or incomplete outputs from authorized diagnostic/history views.
- A changed formal winner is a read-model decision over retained facts unless existing storage requires a specific repair. No historical output deletion is part of this plan.

### Export

- Do not regenerate/overwrite archived manifests as a migration.
- Future formal manifests derive from the current canonical eligible set.
- If history manifests are still necessary, label them as review/history and retain the true state per output. They must not be interchangeable with formal delivery artifacts.
- URL presence, provider file existence, or `metadata_ready` is not evidence that a visual output passed review.

## 3. Frontend safety

- Server status and exact delivery projection are authoritative; the browser must not infer success from “poll ended,” warning text, output count alone, or a previous project result.
- Partial delivery requires explicit eligible output facts. Any failed/not-found job with zero eligible images stays a failure/missing state.
- Do not expose raw review provider diagnostics, IDs, secrets, local paths, hashes, or retry internals in public UI copy.
- Preserve accessible warnings and actionable user recovery paths for held/partial/failure states.

## 4. V1/V2 and specialized-module isolation

- No V1 (`/api/v1`, V1 storage/history/provider settings) or V2 backend, storage, queue, provider, or API code is in scope.
- V3 browser shell file `src_skeleton/app/static/app.js` is shared; edits must be limited to V3 functions and accompanied by tests showing V1/V2 flow behavior remains unchanged.
- E-Commerce owns its export packaging contract. The shared V3 per-output review authority supplies eligible output facts; the shared layer does not learn E-Commerce slot/deliverable roles.
- General Template and Central Brain remain scenario-neutral. No vertical deliverable maps or ecommerce/photography rules are introduced into shared quality code.
- Project Mode’s current explicit Brand Memory confirmation flow is preserved.

## 5. Failure, rollback, and containment

- Before each milestone, record baseline hash and current changed-file list. Do not use `git reset --hard`, `git clean`, or file-overwriting checkout commands.
- A code rollback must revert only the scoped feature changes on its feature branch; do not alter another worktree or historical user data.
- If the new exact gate unexpectedly withholds previously valid candidates, do not lower evidence requirements. Inspect exact ID/evidence bindings and correct the owning projection, with a failing regression first.
- If selection rejection or Brand Memory filtering fails, stop that mutation path; preserve the current stored profile and job record.
- If a test or validation unexpectedly creates a job, candidate, output, selection, or memory write, halt further mutating validation and preserve the evidence append-only under repo escalation rules.
- No live provider/model call should be used as a diagnostic. A later real acceptance run requires separately defined authorization and bounded mutation controls.

## 6. Data review checklist for future implementation

- [ ] Is each final output tied to its original output ID, asset ID, candidate ID, attempt, and review receipt?
- [ ] Can any stale/mismatched review row authorize another image?
- [ ] Does a selected ID map to the same source asset/candidate in Brand Memory?
- [ ] Is empty intersection still empty and non-writing?
- [ ] Are failed/manual/unreviewed outputs still visible only in intended history surfaces?
- [ ] Does the E-Commerce manifest distinguish metadata package readiness from final visual approval?
- [ ] Did the diff touch only V3 product/Project/Brain/frontend owners and their focused tests?
- [ ] Were pre-existing local files and all other worktrees preserved?
