# Doc276: V3 Face Integrity And Delivery Certification Contract

## 1. Purpose And Scope

Doc276 closes a shared V3 delivery-certification gap: an image can pass a
generic hybrid review while its visible primary face has an anatomically or
expressively implausible result. This contract applies to the shared Human
Realism, Vision review, retry, and final-delivery layers. It does not create an
E-Commerce, child, apparel, or other scenario-specific face policy.

The goal is not to prescribe a face, alter age, weaken product facts, or evade
an upstream policy. It is to ensure that a result intended for final delivery
has enough server-verifiable evidence to be certified as a commercially usable
human rendering when a visible person is in scope.

## 2. Authority And Non-Goals

The following authorities remain unchanged:

- Docs 77 and 78 own the shared visual-quality and long-term human-realism
  foundations.
- Docs 93, 95, and 96 own reference-channel inheritance, same-person evidence,
  and high-fidelity identity execution. Doc276 does not expand an identity
  reference into a style, wardrobe, scene, or product-truth lock.
- Docs 128, 143, 147, and 153 own the existing visual-review, human-authenticity,
  inspection, and expression-quality contracts.
- Docs 260, 267, 268, and 272 own their respective final-delivery, terminal
  state, exact-command, and historical-projection compatibility rules. The
  current E-Commerce implementations are documented in E28 and E29; Doc276
  consumes their terminal-state discipline rather than replacing it.
- Doc270 source selection and Doc271 provider-deliverability closure remain
  separate. A face-integrity outcome cannot select source assets, change a
  physical reference plan, or route around a provider closure.

Doc276 never derives a decision from a filename, prompt phrase, score alone,
face-like decoration, browser metadata, or historical output. It never adds an
automatic alternate provider, adult substitution, garment rewrite, or retry
loop.

## 3. Applicability

The contract is active only when all of the following are true for a newly
reviewed output:

1. The output is a verified readable pixel result.
2. Shared Human Realism is enabled for that output.
3. The review identifies a visible primary human face in the rendered subject.

No-reference text-to-image, nonhuman imagery, and outputs without a visible
primary face are not blocked by this contract. Existing General, E-Commerce,
Photography, Brand, and other template authorities continue to decide whether
human realism is applicable; Doc276 adds no scenario-specific taxonomy.

## 4. Frozen Face-Integrity Attestation

For an applicable output, the review provider must return a new frozen,
schema-validated `face_integrity_attestation` bound to the reviewed output
pixels and review receipt. Its only states are:

- `pass`
- `retry_recommended`
- `not_verifiable`

The attestation must say that it assessed the actual visible primary face, not
a face-like image on clothing, packaging, a screen, or the background. It must
claim its reviewed project, job, and output; the frozen Doc260
`review_evidence_plan_digest`; its source-binding digest; the frozen
reference-evidence digest; primary-face scope; state; and shared issue codes.
It may only use the shared Human Realism dimensions, including
`human_anatomy_or_proportion`, `human_expression_context`, and
`human_rendering_artifact`. It is review evidence only. It is never renderer
prompt text, a local face-edit recipe, or a new source-reference channel.

Missing, malformed, stale, or output-mismatched attestation is
`not_verifiable`; high generic identity or human-realism scores cannot fill the
gap. The legacy `human_naturalness_verdict` remains a separate supporting
Human Realism signal. It must never synthesize, upgrade, or substitute for the
new face-integrity attestation.

Provider values are claims, not authority. The server derives the expected
binding tuple from the current `GeneratedOutputResolution`, its authoritative
project/job/output relation, and the frozen server-owned `ReviewEvidencePlan`.
The Product API injects that exact per-output plan, canonical plan digest,
`exact_review_evidence_resolver` authority marker, and admitted reference
evidence metadata into `VisionOutputInspector` before the provider call. It
verifies the typed plan's canonical digest, source-binding digest, and reference
channel before accepting an attestation or comparison certification.
Missing values, wrong project/job/output, digest drift, cross-output or
cross-job reuse, and unknown extra fields fail as `not_verifiable`; browser
metadata cannot supply an expected binding or repair a provider claim.

`VisualInspectionReport.evidence` is the sole internal authority location for
the attestation, identity metric, and comparison certification. When a complete
review package persists an inspection, those fields remain nested under that
inspection's `evidence` object. Top-level copies are not an authority and must
not be introduced as a compatibility fallback.

## 5. Identity Comparison Certification

When a locked person identity or identity-reference channel is required, final
certification additionally requires an explicit provider comparison
certification bound to the same complete server-derived tuple and the frozen
reference evidence. Local identity metric unavailability, no detected reference
face, or multiple face-like detections is evidence of uncertainty, never an
identity pass. A high provider score likewise cannot substitute for the
comparison certification. A valid provider `pass` comparison certification
tied to the same frozen reference evidence may certify a result even where the
local metric is unavailable, including a valid cross-view case.

If this evidence is absent or not verifiable, the result is withheld for
manual review. Ordinary no-reference and nonhuman results do not acquire this
requirement.

## 6. Review, Retry, And Delivery States

An applicable output is eligible for formal delivery only when it has all of:

1. A complete review receipt and verified pixel result.
2. A `pass` face-integrity attestation bound to those pixels.
3. A valid identity comparison certification when an identity channel is
   required.

`retry_recommended` with a shared anatomy, expression, or rendering-artifact
issue is a retryable review result, not a final delivery. It may use the
existing server-owned single bounded Brain-authored quality retry. The retry
ledger is authoritative: it records at most one new retry output, retains the
prior output and review attempt append-only, and never replays a historical
job. After the bounded retry is consumed, or when evidence is not verifiable,
the state is manual/review withheld.

Newly activated jobs must not enter homepage or project final delivery merely
because they are `GENERATED` or have generic high scores. Legacy jobs remain
readable as history or review evidence. They are never deleted, rewritten, or
silently upgraded from an incomplete receipt.

## 7. Public Projection And Terminal UX

Public projections expose only a safe terminal review state and one deliberate
review action. They do not expose face IDs, reference IDs, image paths,
hashes, provider messages, raw issue evidence, or private receipt digests.

For `review_withheld`, `manual_review`, and related terminal face-integrity
states, desktop and H5 consume one shared server terminal-operation projection
without creating a template-specific recovery path. The operation atomically
clears busy/loading, progress stage, polling, recovery timers, and counters.
The UI must not show a stopped or withheld result alongside preparing,
generating, polling, or recovering text. The deliberate review action is local
navigation only and never submits a new job. General, E-Commerce, and
Photography may retain their existing reference boards and actions, but none
may reinterpret this shared review state as an E-Commerce-only recovery rule.
Existing retry controls remain available only when the server's bounded retry
authority explicitly permits them.

## 8. Migration And Compatibility

Doc276 is prospective for newly activated review paths. Historical records are
read-only and history-only unless a new server-owned complete review receipt is
created through an authorized new review path. Missing face-integrity evidence
remains manual/review-withheld. No migration may invent an attestation,
automatically re-certify a legacy row, replay a job, mutate historical output
records, or auto-submit a replacement.

## 9. Phase Acceptance

Phase 0 defines deterministic red tests only. Phase 1 may introduce the shared
attestation and delivery gate after the tests prove: identity uncertainty cannot
auto-certify, generic shared retry remains bounded, nonhuman/no-reference flows
remain open, final-delivery projections require complete evidence, and desktop
and H5 settle terminal review states coherently.
