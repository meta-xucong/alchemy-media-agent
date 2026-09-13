# V3 Format/Layout Per-Output Canvas Closure

Status: implementation and audit-repair contract
Scope: V3 foundation/runtime for enforced `general_template` multi-image jobs
Baseline: `c748a5597d1ee8f19998ae3c2027e089dfd20053`

## 1. Objective

`format_layout_adaptation` must preserve one approved visual idea while
assigning a real, output-specific layout duty. The duty must survive the
server-owned General variation contract, Brain planning/finalization, Provider
canvas selection, persisted output metadata, and review. A job-level canvas
size is not sufficient evidence for a multi-format mode.

This is General foundation/runtime work. It does not add a vertical-specific
deliverable map or change the Core candidate-to-slot acceptance path.

## 2. Evidence and exact mismatch

The controlled VPS run used the approved safe comparison project and the same
original request for all four General modes. Selection, delivery, and creative
exploration produced two real images each and their Brain review records were
`hybrid/pass` with no detected issues. The format mode produced a valid single
image, proving the renderer route itself was available, but its two-output run
was blocked once by the upstream provider policy gate.

The read-only prompt audit found a local semantic loss independent of that
upstream block:

* the mode role plan assigned output 1 `vertical_cover` and output 2
  `square_feed`;
* the typed variation bridge projected both roles only to the generic axis
  `layout`;
* Brain therefore authored output 2 as another vertical cover;
* Provider also read one job-level `requested_image_size`, so no per-output
  physical canvas target existed even if the prompt happened to mention one.

The upstream `400 content_policy_violation` is a separate terminal provider
decision. It must remain fail-closed and must not be bypassed by a fallback
provider or local prompt suffix.

## 3. Correction model

The current General role plan remains the source of the mode's output duties.
The existing neutral `variation_axes` bridge remains the single Brain-facing
contract. Four additive neutral axes make format intent unambiguous without
leaking role names or local recipe prose:

| Neutral axis | Meaning | Provider canvas |
| --- | --- | --- |
| `format_vertical` | tall portrait layout with top/bottom safe space | `1024x1536` |
| `format_square` | balanced square layout | `1024x1024` |
| `format_horizontal` | wide layout with side space | `1536x1024` |
| `format_tight` | tight/detail-safe framing | retain the frozen job canvas |

The axes are semantic evidence, not renderer text. Brain finalization must
translate the exact axis for each output into one complete natural-language
direction and copy the exact ordered axes into the existing semantic receipt.
The Provider may use only the validated frozen General contract to select the
per-output canvas; it must not infer a target from prompt words or a mutable
role label. An explicit Provider image-option size remains a user-supplied
transport override; otherwise the mode target is authoritative for its own
output canvas. The original user subject, scene, style, mood, and exclusions
remain protected.

Format role targets are applied to the local `AssetSpec` before Layout Agent
execution as well, so layout planning, Provider size, output metadata, and
review observe the same target. `format_tight` changes framing but does not
invent a new canvas.

Historical v1 contracts without these axes remain readable. Their digest and
projection behavior must not be rewritten; only fresh contracts issued after
this repair receive the explicit format axes.

### Audit repair after the first Doc307 implementation

The independent review rejected the first implementation because it still
allowed three sources of drift: Provider could fall back from a malformed
output index or ambiguous axis row, Central Brain selected by a local role key
while Provider selected by contract row, and post-generation review only read
top-level candidate fields instead of persisted `CandidateResult.metadata`
and actual pixel dimensions.

The corrected authority is now one shared resolver in the Visual Cluster
contract module. It validates the contract digest, requires a strict
zero-based generation output index converted to the contract's one-based row,
requires the resolved-ledger contract binding on an enforced Provider path,
and accepts exactly one physical format target per current row. A historical
contract with no format axes returns no override; a partially populated or
ambiguous current contract fails closed.

Central Brain and Provider both call that resolver. The Provider no longer
accepts a Boolean `variation_execution_contract_enforced` marker as canvas
authority. The post-generation mode review receives the same contract and
binding, reads nested provider metadata, checks the declared target and size,
and compares the persisted width/height with the expected canvas. Explicit
typed Provider size remains an auditable transport override; tight format
keeps the frozen job canvas.

Central Brain also fails closed when a current multi-image format plan has no
contract at all; it does not proceed with a local role-key-only canvas guess.
The same rule applies to a single-output request only when the format mode is
explicitly server-bound; an incidental legacy role label on an ordinary
single-image job remains compatible.

The reference-edit transport is also covered. If a constrained square edit
profile cannot carry a contract-required vertical, horizontal, or tight
canvas, `_resolve_provider_size` preserves the contract size and lets the
Provider capability guard stop the request. It may not silently turn the
output into a square image merely because a reference is present.

## 4. Implementation boundary

1. Add the four neutral axis literals and a server-owned target map in the
   Visual Cluster contract layer.
2. Project format role recipes to the explicit axes in
   `ModeAwareRoleDirector`; keep all other modes byte/semantic-compatible.
3. Apply the same target map to General asset/layout planning in Central Brain.
4. Teach the compact Brain payload and canonical finalizer contract to honor
   the exact format axis and preserve its semantic receipt.
5. Make the production Provider resolve the validated output-index contract
   to a per-output canvas and persist the target/size audit facts.
6. Add regression tests for contract projection, Brain instructions and
   receipt matching, per-output Provider size, strict binding/index failure,
   malformed or historical contract behavior, nested metadata and actual
   pixel review, and non-format mode isolation.

No prompt keyword patch, provider-policy bypass, extra retry, or specialized
template change is part of this repair.

## 5. Acceptance gates

* All focused contract/Brain/Provider tests pass, then the full V3 test suite,
  compile/import checks, Node checks, and `git diff --check` pass.
* An independent read-only code audit finds no authority or isolation defect;
  a failed audit is a repair gate, not a release result.
* The exact committed mainline is pushed and deployed to VPS.
* The safe comparison project is run again in all four General modes. Each
  successful output has the expected role, Brain semantic receipt, final
  prompt direction, and canvas metadata. The format two-output run is retried
  after the upstream policy result; if the same terminal upstream block recurs,
  it is reported separately from local correctness and the single-output
  format route remains the provider-availability control.
* Downloaded pixels are inspected. Contract/receipt success alone is never
  reported as visual-quality acceptance.
