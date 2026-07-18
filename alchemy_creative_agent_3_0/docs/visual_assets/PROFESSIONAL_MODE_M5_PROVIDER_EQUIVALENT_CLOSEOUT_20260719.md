# Professional Mode M5 Provider-Equivalent Closeout — 2026-07-19

Status: **provider-independent image-channel acceptance complete; persistent pack activation not repeated; production gate unchanged**

## 1. Scope and acceptance boundary

This record closes the remaining Professional Face Identity image-quality
question under the operator-approved acceptance rule that the Web Provider and
Codex built-in ImageGen are equivalent rendering channels when both receive
the byte-identical canonical Brain prompt and the same admitted reference
files.

It does not convert conversation-only MCP pixels into Product API records. It
does not fabricate a candidate, review history, winner, pack activation or
production flag. The persistent lifecycle remains governed by the existing
Product API and shared Vision path.

## 2. Model-ready Product API evidence

Controlled baseline: `main@23c67c42c2c8e3a423e0af399874ad72655fa15b`.

The local runtime first installed the repository-pinned YuNet/SFace model
artifacts through `scripts/fetch_v3_identity_models.py`. The previously
missing runtime dependency was therefore corrected without changing a review
threshold or adding a fallback detector.

The fresh formal run used:

- project `project_c2fde2e6d5`;
- People Asset `people_asset_doc166_model_ready_fde2e6d5`;
- pack `pack_069b1d79354046bd9fdaa3337e23d9be`;
- frozen preparation-intent SHA-256
  `f6d363441bfccc41506e726dbd0acdedeac24689cc34e735962f02d8017ad3ca`.

The front stage produced two verified passing candidates after one bounded
repair opportunity. Likeness-first selection chose
`candidate_385fc988fc` (`overall=0.92`, `same_person=0.8443`,
`identity=0.86`).

The three-quarter stage produced three verified passing candidates. The
winner was `candidate_8a87641045` (`overall=0.94`,
`same_person=0.9448`, `identity=0.94`).

All five profile materializer inputs were then independently audited before
the image request:

```text
reference_count=5
reference_total_bytes=271657
derivative_kinds=
  root pose_geometry
  front feature_detail + pose_geometry
  three-quarter feature_detail + pose_geometry
face_localization_status=detected for all five
view_conditioned_evidence.ready=true
view_conditioned_evidence.missing=[]
```

The canonical profile prompt was signed successfully by the Remote Brain.
The Web Provider path still returned no profile pixels in that run. This is an
upstream hold after a complete local materialization contract, not a missing
Alchemy prompt, reference, face-localization or serial-lineage implementation.

## 3. Canonical MCP profile candidates

The exact canonical profile prompt from the local materializer was passed
unchanged to Codex built-in ImageGen with the exact five admitted local
reference files. No phrase was appended, removed or rewritten. The prompt
SHA-256 was:

`e30ac4cb14709708f6ff6b4622bfad2aca5b1dcc27cb58515e4b8ef210eacc65`

Three independent candidates were generated and inspected through the shared
Professional Vision score contract:

| Candidate | Output SHA-256 | Status | Overall | Same person | Distinctive features | Age direction/coherence | Human realism |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `4729d0973ea59cf3671b1e7c5e630987f3a6983e2ba20e7b518ff361af7a02da` | pass | 0.93 | 0.90 | 0.89 | 0.94 / 0.95 | 0.90 |
| 2 | `00f5f6d6a7c3c79d6082d45282b1f510b9d7fbc28cebe11f8d62fd1f4663d81b` | pass | 0.94 | 0.88 | 0.84 | 0.93 / 0.95 | 0.95 |
| 3 | `cdc2ff1bfc9aeaf75febc34af96a4c92024f9aa74388fbd145a11d70c3afd9d6` | pass | 0.94 | 0.88 | 0.78 | 0.96 / 0.97 | 0.98 |

All candidates had an empty issue-code set. Candidate 1 is the accepted
profile winner because M5 is likeness-first: its same-person and distinctive-
feature scores exceed candidates 2 and 3 even though their aggregate finish
scores are slightly higher.

The generated media remains outside Git under Codex's generated-image store.
Only hashes and provider-neutral review scores are recorded here.

## 4. Decision

The following claims are now supported:

- the shared Professional front, three-quarter and profile visual contracts
  can all produce accepted approximately-six-year-old identity anchors;
- Brain prompt ownership, 2/3/5 reference parity, face localization, age
  coherence, neutral capture and shared Vision quality all operate correctly;
- the remaining Web Provider no-pixel result is upstream hold evidence and is
  not an Alchemy code or quality failure;
- provider-independent Professional image-channel quality is accepted under
  the operator's explicit MCP-equivalence rule.

The following claims remain intentionally false:

- the MCP outputs were persisted as Product API candidates;
- the fresh Product API pack was activated;
- the Professional browser or production gate was opened;
- a failed Web Provider transaction was rewritten as success.

No new Provider, Brain, reviewer, retry loop, storage system, child-specific
module, keyword recipe or local prompt patch was introduced.
