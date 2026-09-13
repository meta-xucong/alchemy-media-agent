# V3 General Mode Authority, Anchor Gate, and Role Binding Hardening

Status: implementation plan and acceptance contract
Scope: V3 foundation/runtime for enforced `general_template` multi-image jobs
Baseline: `d9e13d1352015ee9ff8d05fc26344bb145794b35`

## 1. Objective

The four General generation modes must be selected from the current request,
materialized by the same server-owned contract, and preserved through Brain,
Visual Capability Cluster, Runtime ledger, Provider projection, durable output
metadata, replay, and public review. Optional historical identity continuity
must never turn a stylized or semantically ambiguous request into an
`image_edit` request.

This is foundation/runtime hardening. It does not add scenario-specific
deliverable maps to General Template and it does not change the Core
candidate-to-slot acceptance path.

## 2. Observed mismatches

The independent code audit found six fail-open seams:

1. Doc73/Doc287 automatic first-output identity continuity still enabled when
   the Brain profile was absent, incomplete, ambiguous, or selected a
   non-photoreal rendering mode. A role-plan `character` fallback could
   therefore create a historical reference and change a new request from
   `image_generate` to `image_edit`.
2. Desktop and mobile new-job payloads sent the browser's derived effective
   mode as `continuation_mode` even when the visible selection was `auto`.
   The shared resolver treats that field as an explicit choice and can let it
   override a current inference or frozen-contract precedence.
3. An enforced General contract could reach
   `_build_template_deliverable_plan` without its complete mode role plan and
   silently create generic deliverables. This makes the Provider role and the
   review role diverge while the Job still looks structurally successful.
4. `variation_mode_binding` was built in Runtime and consumed by Brain, but
   was not a typed Visual Cluster field and was not consistently included in
   the trusted continuation/runtime metadata set. Replay and output-store
   restoration could therefore lose the original mode provenance.
5. The deterministic compatibility classifier treated any non-empty mode
   label as evidence of a suite, so a one-image request carrying a stale
   `variation_mode` activated `suite_direction` and its director.
6. When Brain sign-off failed after a visual-asset snapshot was frozen, the
   blocked Product API receipt derived a different fallback job ID from the
   Runtime ID. The snapshot and public status could therefore describe two
   different jobs.

## 3. Correction model

### 3.1 Automatic identity anchor authority

Doc73 automatic continuity is an optional enhanced capability. It is enabled
only when all of these server/Brain facts are present:

- the request is a non-E-Commerce human/person multi-output request;
- `require_real_images` is true;
- `visual_task_profile.rendering_intent.rendering_mode` is explicitly one of
  the photoreal modes;
- `stylization_scope` is explicitly `none` or `object_surface`;
- the typed profile contains a human subject entity;
- there is no explicit user/project reference truth source.

Missing profile, missing rendering intent, `ambiguous`, `whole_image`, or an
unknown rendering mode closes the optional anchor path. Role-plan labels and
prompt words cannot reopen it. Historical records remain readable through
their existing Doc285 compatibility boundary.

### 3.2 Current request mode authority

The current user choice is authoritative. A browser-derived value is not a
continuation choice. New General requests with `variation_mode=auto` omit
`continuation_mode`; the server resolves explicit override, explicit non-auto
selection, explicit continuation (only when supplied by a continuation-aware
caller), current inferred mode, frozen contract reuse, and persisted/default
compatibility in that order.

The resolver remains backward compatible with direct callers that supply only
an explicit `continuation_mode`, but it ignores a continuation value paired
with `variation_mode=auto` and `variation_mode_source=auto` unless the caller
marks `continuation_mode_explicit=true`.

### 3.3 Role binding authority

For an enforced General multi-image contract, the server must persist and
validate one complete `variation_execution_role_plan` before creating
`TemplateDeliverable` records. It must contain exactly the requested number of
ordered, unique recipes; each recipe must have a non-empty role key, label,
purpose, and matching output index. Missing or mismatched role data blocks the
job with a typed activation error. Provider generic-role fallback remains
available only to non-enforced compatibility paths.

### 3.4 Mode binding persistence authority

`variation_mode_binding` is a typed server-owned value. The same validated
binding is carried in:

```text
Runtime request -> VisualCapabilityClusterResult -> capability ledger
-> Provider projection -> durable output envelope -> trusted continuation
```

The binding's effective mode and contract version/digest must match the frozen
variation contract. It is private execution provenance; public projections may
expose only existing allowlisted mode summaries, never raw internal prompt or
reference facts.

### 3.5 Single-image boundary

General Suite Direction is a multi-output capability. Fallback activation may
request it only when the normalized requested image count is greater than one;
mode labels alone are compatibility metadata, not output-count evidence. A
single-image request must remain on the foundation path and must not execute a
suite director or create suite roles.

### 3.6 Job identity closure on blocked planning

Planning success and planning failure share the same Runtime job identity.
If Brain sign-off or another planning-stage contract blocks the run after a
server-owned snapshot is frozen, Product API must reuse the Runtime-derived
ID for the blocked receipt. It must not derive a separate fallback ID from a
shorter input tuple. This keeps snapshot, lifecycle failure, replay, and
public status on one append-only job boundary.

## 4. Implementation boundaries

- `CentralCreativeBrain`: strict Doc73 applicability predicate.
- `variation_modes.py`: current-request continuation guard and inference
  precedence.
- desktop/mobile V3 payload builders: omit derived continuation for `auto`.
- `ScenarioRuntime`: validate General role-plan completeness and typed mode
  binding before ledger/provider execution.
- activation fallback: gate Suite Direction on requested output count rather
  than the presence of a mode label.
- Product API: reuse the Runtime job ID for blocked planning receipts.
- Visual Cluster contracts/module: add typed binding and project it into the
  active cluster.
- Product API: persist the binding and role plan in the server activation
  metadata and trusted continuation set.

No Provider policy bypass, provider switch, prompt suffix, threshold tuning,
or historical-job rewrite is part of this repair.

## 5. Regression and acceptance gates

1. Add failing tests for incomplete/ambiguous anchor profiles, browser-derived
   continuation, frozen-vs-current inference, role-plan gaps/index mismatch,
   typed binding mismatch, and trusted continuation preservation.
2. Run focused anchor/mode/runtime/ledger/output projection tests.
3. Run the bounded V3 mode regression suite and syntax/import/diff checks.
4. Perform an independent read-only audit of the frozen diff.
5. Deploy the exact main commit to VPS and run one controlled real Job per
   General mode on the approved safe comparison project. Inspect all final
   pixels and receipts; do not report metadata-only success as visual
   acceptance.

## 6. Non-goals

- no changes to E-Commerce, Photography, or New Media deliverable maps;
- no deletion or rewriting of existing VPS evidence;
- no biometric persistence;
- no deterministic creative fallback when Brain is required;
- no claim that a provider policy block is fixed by local routing until a fresh
  safe request proves the correct provider operation and real pixels.
