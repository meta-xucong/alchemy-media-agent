# Doc185: Shared Provider Admission Contract and Character Card Resume

Status: active shared-runtime contract. This document closes the Provider
admission gap exposed by the local Character Card Face Identity resume. It
extends Docs 178, 183 and 184 without creating a new image channel, reviewer,
retry budget or storage path.

## 1. Problem and boundary

The Remote Brain correctly received the Character Card face-only capture scope,
but its complete canonical direction could still contain long contrastive
safety wording or micro-anatomy language. The upstream image edit endpoint
could reject that wording with an opaque HTTP 400 before any pixels existed.

The fix belongs at the shared final Brain signing boundary. The Brain remains
the only creative author. Local code must not search, replace, append, trim or
otherwise rewrite the prompt. The Provider and MCP channels receive the same
signed prompt and the same admission receipt.

## 2. Typed admission contract

Character Card Face Identity preparation adds this frozen context only when the
typed capture scope is `character_card_face_identity`:

```text
provider_admission_decision:
  required: true
  contract_version: v3_provider_admission_decision_v1
  provider_admission_status: admitted
  prompt_language_mode: concise_positive_renderer_direction
  safety_sensitive_prompt_normalized: applied
  owner: remote_v3_llm_brain
  frozen_binding: server-owned execution binding
```

For each output, the finalizer must return the same schema-only receipt plus
`status: approved|rewritten`. The receipt proves that the Brain preserved the
protected identity, stage, clothing, scene and capture facts while expressing
the renderer direction concisely, positively, fully clothed and plainly
age-appropriate. It is audit evidence, never renderer prose.

Missing, malformed or mismatched receipts fail closed before Provider or MCP
materialization. Historical records without this field remain readable.

## 3. Channel parity

Provider and MCP continue to be transport alternatives after one canonical
Brain signing result:

```text
Brain finalizer + admission receipt
  -> exact canonical prompt and hash
  -> Provider or MCP materializer
  -> shared output store, Vision, bounded retry and winner writeback
```

No channel may normalize the prompt independently. The existing Doc183 handoff
hash and reference parity checks remain authoritative. A pending MCP handoff is
still resumable and does not spend visual retry budget.

## 4. Scope and compatibility

The admission receipt is required for Character Card Face Identity only. It is
not a child-specific prompt recipe and does not alter ordinary adult work,
General Template behavior, E-Commerce, Photography, ordinary Anchor Pack
stages, Vision thresholds, or the shared retry budget. Later Expression Set and
Body Silhouette stages may adopt the same generic contract if their typed
semantic boundary requires it; they must not copy Face Identity-specific rules.

This document supersedes any older wording that treats local prompt filtering,
provider-side safety retries, or a second MCP/Provider creative path as an
acceptable solution. Production gates, M5, Gate C/D and real upstream
availability remain separate acceptance items.

## 5. Acceptance evidence

- Face Identity payload exposes the typed admission receipt only when its typed
  capture scope is active.
- The adapter rejects missing or mismatched receipts.
- Ordinary Anchor Pack schema remains unchanged.
- Provider and MCP consume the same canonical prompt contract.
- Resume continues from the accepted `face.front` winner without replaying old
  outputs; later views remain blocked until the preceding view has a verified
  winner.
