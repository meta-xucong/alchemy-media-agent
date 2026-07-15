# P12: Doc127 P10 Restricted Evidence Manifest And Browser Checklist

## Status And Scope

This is the Photography template owner's execution aid for Doc127 §10. It is
not evidence of a completed case, does not enable a deployment flag, and must
not be used against a process whose recorded commit is older than the frozen
campaign baseline.

Current offline preparation baseline: `origin/main@8c9760d`.

The controlled instance must be explicitly confirmed by the mainline operator
as running this commit or a documented later frozen commit before any P10
generation is submitted. A browser observation from an older process is
diagnostic only and cannot populate this checklist.

Photography owns its scene/role acceptance interpretation. Central Brain,
GPT Image 2 materialization, visual review, bounded retry, and final-winner
selection remain shared-runtime responsibilities. This checklist adds no
private Provider, reviewer, retry, selector, or creative recipe.

## Restricted Evidence Location

Create the following outside Git for the acceptance campaign. Do not create
these folders in the repository and never commit images, screenshots, request
or response bodies, credentials, private endpoints, or personal data.

```text
ACPT-YYYYMMDD-v3-release-<short-commit>/
  00-environment.json
  01-material-authority.json
  02-automated-preflight.txt
  runs/<acceptance-run-id>/manifest.json
  runs/<acceptance-run-id>/review.md
  runs/<acceptance-run-id>/provenance-redacted.json
  browser/<acceptance-run-id>/steps-and-screenshots/
  release-decision.md
```

Every file references the campaign's acceptance-run ID and uses content hashes
or redacted IDs only. The material owner supplies a written rights/source,
watermark, and allowed-use statement before a reference image is uploaded.

## Manifest Template

Record the following JSON shape externally for every case. Omit any secret or
raw media field; redact internal Provider identity and endpoint details.

```json
{
  "acceptance_run_id": "P10-<scene>-<mode>-<delivery>-<sequence>",
  "timestamp_timezone": "",
  "commit": "",
  "deployment_id": "",
  "config_fingerprint": "",
  "template": "photographer_template",
  "scenario": "portrait | landscape | still_life | animal",
  "input_mode": "text_to_image | reference_reshoot",
  "delivery_mode": "single_hero | professional_set",
  "requested_roles": ["session_hero"],
  "material_rights_reference": "text_only | restricted-material-id-and-hash",
  "user_request_and_authorized_facts": "",
  "frozen_envelope_id": "",
  "brain": {
    "llm_used": true,
    "fallback_used": false,
    "direction_count": 1,
    "creative_owner": "remote_v3_llm_brain"
  },
  "renderer": {
    "family": "gpt_image_2",
    "outer_operation_count": 1
  },
  "source_asset_bindings": [],
  "role_outcomes": [
    {
      "role_key": "session_hero",
      "terminal_state": "",
      "candidate_hash": "",
      "winner_hash": "",
      "review_mode": "vision_model | hybrid | metadata_only | null",
      "review_status": "pass | warning | manual_review | fail_retryable | fail_final | null",
      "verification_state": "verified | unverified | unavailable | null",
      "certification_state": "certified | manual_confirmation_required | blocked",
      "retry_history_reference": ""
    }
  ],
  "public_delivery_state": "ready | withheld_manual_confirmation | not_evaluated | blocked | failed",
  "refresh_reopen_result": "",
  "human_decision": "accept | reject | hold",
  "restricted_evidence_references": []
}
```

For `professional_set`, `requested_roles` and `role_outcomes` contain exactly
`session_hero`, `environmental_context`, and `detail_or_moment`. Each must
have its own terminal state and exactly one certified winner before the case
can pass. Never substitute a single final image for an incomplete set.

## P10 Matrix Ledger

Run sequentially only after Doc127 Phase 0–4 preconditions and a mainline
deployment confirmation. Initially mark every cell `not_started`; `pass` is
valid only with the complete restricted manifest and human review.

| ID | Scene | Input | Delivery | Start condition | Required terminal result | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P10-01 | portrait | T2I | single_hero | Brain + GPT Image 2 + vision/hybrid available | 1 certified winner | not_started |
| P10-02 | portrait | T2I | professional_set | same | 3 certified role winners | not_started |
| P10-03 | portrait | reference-reshoot | single_hero | authorized reference + native edit path | 1 certified winner | not_started |
| P10-04 | portrait | reference-reshoot | professional_set | same | 3 certified role winners | not_started |
| P10-05 | landscape | T2I | single_hero | Brain + GPT Image 2 + vision/hybrid available | 1 certified winner | not_started |
| P10-06 | landscape | T2I | professional_set | same | 3 certified role winners | not_started |
| P10-07 | landscape | reference-reshoot | single_hero | authorized reference + native edit path | 1 certified winner | not_started |
| P10-08 | landscape | reference-reshoot | professional_set | same | 3 certified role winners | not_started |
| P10-09 | still life | T2I | single_hero | Brain + GPT Image 2 + vision/hybrid available | 1 certified winner | not_started |
| P10-10 | still life | T2I | professional_set | same | 3 certified role winners | not_started |
| P10-11 | still life | reference-reshoot | single_hero | authorized reference + native edit path | 1 certified winner | not_started |
| P10-12 | still life | reference-reshoot | professional_set | same | 3 certified role winners | not_started |
| P10-13 | animal | T2I | single_hero | Brain + GPT Image 2 + vision/hybrid available | 1 certified winner | not_started |
| P10-14 | animal | T2I | professional_set | same | 3 certified role winners | not_started |
| P10-15 | animal | reference-reshoot | single_hero | authorized nonhuman identity reference + high-fidelity capability | 1 certified winner | not_started |
| P10-16 | animal | reference-reshoot | professional_set | same | 3 certified role winners | not_started |

## Browser Checklist

Use the controlled Photography workspace only; do not substitute a General
project or call a renderer directly.

### Before a submission

- [ ] Mainline operator confirms the live instance's commit, deployment ID,
  controlled-only Photography flag, shared remote Brain, GPT Image 2 route,
  and `vision_model` or `hybrid` inspection availability.
- [ ] Browser hard-refresh/new session shows `photographer_template` as
  creatable and the resulting project summary identifies it as Photography.
- [ ] The campaign's restricted environment record and material register exist.
- [ ] Reference case only: source/rights/watermark evidence is recorded; the
  intended reference role is explicit. Animal/pet identity uses
  `nonhuman_identity_reference` and high-fidelity capability negotiation.
- [ ] Named profile case only: user chooses the trusted profile in the UI and
  explicitly reconfirms identical profile ID, version, and checksum. Any
  mismatch must block; no General fallback is acceptable.

### Submission and live terminal truth

- [ ] Create one new Photography project and select the intended scene/input/
  delivery mode. Confirm `single_hero=1`; confirm a professional set freezes
  exactly the three structural roles.
- [ ] Submit once through the visible V3 workflow. Do not direct-call GPT
  Image 2, add a local retry, or start concurrent matrix rows.
- [ ] Verify the history shows a remote Brain result with no fallback and one
  natural-language direction per frozen role. It must not show a deterministic
  camera/light/pose recipe as the creative source.
- [ ] Verify each role reaches an honest terminal state. Provider failure or
  Brain failure has no candidate/review/retry/delivery; it is not a visual pass.
- [ ] Verify final review provenance in both the result panel and project
  history: review mode, verification state, certification state, and held/
  manual state.
- [ ] Accept only `vision_model`/`hybrid` with `pass`/`warning` plus
  `certified` for automatic delivery. `metadata_only`, unavailable, or
  `manual_confirmation_required` is withheld and recorded as non-pass.
- [ ] For a professional set, verify three separate terminal role results and
  exactly three certified final winners. A partial set stays withheld with its
  diagnostic history.

### Refresh, review, and closure

- [ ] Refresh and reopen the project. The certification/withheld state,
  append-only history, exact final count, profile binding, and reference
  binding persist without a false spinner or duplicate card.
- [ ] Record redacted IDs/hashes, timing, certification, retry history, and
  final public state in the restricted manifest.
- [ ] Human reviewer records accept/reject/hold against scene truth,
  professional utility, reference truth, natural detail/anatomy/material,
  absence of unwanted text/watermarks, and role distinction.
- [ ] Mark the ledger pass only after both technical and human criteria pass.
  Hold/block cases stay visible and do not change the production gate.

## Stop Conditions

Do not submit a P10 case, and report the exact blocker, when any of these is
missing: confirmed frozen deployment, reachable remote Brain, GPT Image 2
production route, certifying `vision_model`/`hybrid` review, material rights,
or reference-edit/high-fidelity capability for reference rows. Never convert
a blocked reference case into a text-only pass.
