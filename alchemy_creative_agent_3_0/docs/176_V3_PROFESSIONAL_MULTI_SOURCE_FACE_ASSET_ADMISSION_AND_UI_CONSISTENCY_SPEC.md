# Doc176 — Professional People Asset Multi-Source Admission and Unified Upload UX

## Status

Implemented as a bounded Professional Mode correction. This document does not
change Standard Mode, ordinary project reference uploads, the Remote Brain,
the shared Provider, shared review, retry, or final-delivery contracts.

## Problem

The Professional visual-asset creation surface exposed a browser-native
single-file input and the client read only `files[0]`. That was both visually
inconsistent with the ordinary V3 reference uploader and misleading: users
could not provide a primary likeness source together with a complementary
reference when establishing a reusable People Asset.

Adding HTML `multiple` alone would be incorrect. Face Identity preparation is
a serial evidence workflow with a fixed Provider reference budget of 2 / 3 / 5
for front / three-quarter / profile. Any accepted source must therefore have a
declared role, a persisted ready-upload record, and a deterministic place in
that budget.

## User-facing contract

For the first Face Identity release, a new People Asset accepts:

1. one required **primary source**; and
2. at most one optional **supplementary identity reference**.

The user can remove either image and can choose which selected source is the
primary source. The UI says explicitly that two images are the supported
maximum. Selecting more than two is rejected before upload; no selected file
is silently discarded.

The primary source is the root provenance for the asset. The supplementary
source is initial calibration evidence only. It does not become an additional
project binding, an invisible style lock, or a future prompt fragment.

## Frozen evidence and budget contract

The preparation contract remains bounded and fail-closed:

| Stage | Direct evidence | Provider derivatives | Total |
| --- | --- | --- | --- |
| Standard front | primary only, or primary + one supplementary source | primary-only: complementary feature/geometry pair; two-source: one stage-flexible facial-feature derivative per direct source | 2 |
| Three-quarter | primary root + reviewed front winner | root pose geometry + winner feature/pose pair | 3 |
| Profile | primary root + reviewed front and three-quarter winners | root pose geometry + two reviewed winner pairs | 5 |

After a reviewed front winner exists, it replaces the supplementary source in
the serial chain. This preserves a bounded, user-auditable identity path and
prevents a growing bag of references from leaking into later stages.

Three or more initial sources are not accepted by this release. Supporting
them safely requires a separately reviewed source-consolidation stage; a UI
must never imply that an ignored third image influenced the asset.

## Ownership and privacy

- The public create request carries only ready upload IDs, consent, and the
  user's natural-language preparation intent.
- Source ordering and derivative selection are server-owned evidence routing,
  not local prompt prose or keyword recipes.
- The Remote Brain continues to author and sign off on the final canonical
  prompt. Neither the frontend nor the evidence router adds facial
  descriptions, negative keywords, or presentation rules.
- Public library/project responses keep source IDs, paths, hashes, raw prompt
  content, Provider details, and review internals private.
- Existing single-source assets and historical records remain readable and
  preserve their one-source behavior.

## Unified UX rules

1. All V3 image selection surfaces use the shared file-drop visual language:
   visible action label, allowed format hint, selected-file list, and explicit
   remove controls.
2. The Professional surface labels the first source `主原型` and the optional
   second source `补充参考`; only one source may be primary.
3. Uploading source images only creates a draft asset. Building the three
   views and explicitly activating the reviewed version remain separate,
   visible steps.
4. Busy states disable duplicate submit actions, retain the selected-file list
   on failure, and present human-readable recovery guidance.
5. The file selection and library view must remain usable at desktop and
   narrow mobile widths without horizontal overflow.

## Required regression evidence

- one-source assets retain the existing 2 / 3 / 5 Provider derivative path;
- two-source front preparation produces exactly two initial derivatives,
  preserves primary-first ordering, and transitions to primary-plus-winner;
- duplicate, unready, non-face-reference, cross-root, or over-limit sources
  block before Brain/Provider work;
- the UI supports selecting, reordering, removing, and submitting one or two
  images; three selected images are visibly refused;
- Standard, General, E-Commerce, and Photography uploads do not acquire
  Professional People Asset semantics.
