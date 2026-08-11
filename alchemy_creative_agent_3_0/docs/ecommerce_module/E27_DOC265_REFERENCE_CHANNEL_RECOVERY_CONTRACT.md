# E27 / Doc265 Reference Channel Recovery Contract

Status: Phase 1 implementation in the isolated E-Commerce worktree. This
document authorizes no Provider/MCP/ImageGen call, deployment, or
production-record mutation.

## 1. Scope And Authority

Doc265 is a specialized Professional E-Commerce Project Mode correction. It
repairs the boundary between the old ordinary V3 continuation mechanism and
the strict E-Commerce product-truth admission introduced by Doc263/Doc264.
The owning authority is server-side Project Mode and Product API state:

```text
durable project records and asset stores
  -> server channel classifier
  -> E-Commerce product-truth admission / visual-asset binding
  -> explicit continuation projection
  -> Product API job command
  -> public project view
```

The Provider receives only the already separated, typed physical inputs. It
does not classify a browser list, decide whether an output is a product
original, or repair a stale project command.

## 2. Observed Failure

The ordinary V3 UI historically treated a selected generated image as a
continuation reference. Professional E-Commerce later treated
`uploaded_asset_ids` as a strict product-truth pool. A legacy project can
therefore contain four real uploaded product originals plus historical
`v3_output_*` IDs in the same request field. The current E-Commerce admission
then rejects the whole request before ImageGen, even though the product
originals are valid.

This is a channel-confusion defect, not a provider-policy failure. The same
confusion also makes the project surface look as though an automatically
generated image is an active product reference when the user never selected
it.

## 3. Four Explicit Channels

Every E-Commerce project read and generation command must preserve these
independent channels:

| Channel | Authority | May enter product truth? | Default behavior |
| --- | --- | --- | --- |
| `original_product_inputs` | V3UploadedAssetStore ready record plus active project association | Yes, after Product API admission | Used for current product appearance |
| `locked_person_identity` | Project Visual Asset Binding Service and catalog | No | Used for person identity only |
| `selected_continuation_directions` | Exact project-owned generated output selected by the user | No | Used only after explicit selection |
| `generated_and_review_history` | Durable job/output/review records | No | Read-only history; never an input by default |

The public project view continues to expose exactly these four groups. A
history item must not be copied into either of the first three groups merely
because it has a preview, appears in a job record, or was present in a legacy
request list.

## 4. Server Classification Rules

1. `uploaded_asset_ids` is a compatibility input, not an authority. For the
   E-Commerce route the server resolves every ID against the authoritative
   upload store and project association records before deriving the current
   product pool.
2. A ready upload with the admitted product role/channel is an original
   product input. Its actual content digest and project association remain
   governed by Doc262-264.
3. A generated output ID, review output ID, candidate ID, or output asset ID
   found in the legacy uploaded list is historical evidence. It is removed
   from product admission, preserved in append-only history, and does not
   cause a fresh upload or a raw `product_truth_admission_invalid` failure.
4. A generated output becomes a continuation direction only through an
   explicit user selection operation. The server must verify that the output
   belongs to the same project, job, and durable output record, and that the
   output is readable. Caller-provided project/job lineage is not sufficient.
5. Unknown, cross-project, cross-job, unreadable, or forged output selectors
   fail closed as a sanitized input problem. They must not be silently
   promoted, guessed, or merged into product truth.
6. A bound People Visual Asset is resolved only through the server-owned
   Project Visual Asset Binding Service and catalog. Its ID/version and
   display name are identity metadata, not uploaded product references. It
   must never be included in the product pool or sent through product-truth
   admission.
7. A project with no admitted product original keeps the existing E-Commerce
   text-to-image path. Historical outputs and a locked People asset do not
   manufacture a product reference.
8. The server derives the final typed channel payload before idempotency and
   command identity. Replaying the same continuation action returns the same
   command and does not re-add old output IDs to product truth.
9. Once the Product API has the durable `ProductJobRecord.job_id`, it rebuilds
   and freezes every ProductTruthAdmission and per-output physical projection
   to that exact ID. The request record, planning result, every generation
   plan, and renderer request carry byte-equivalent typed contract copies.
   Generate-stage context refresh may validate that final contract but must
   not replace it with an instance/pending ID. A mismatched persisted contract
   closes before materialization; Provider metadata precedence is never used
   as a recovery rule.

## 5. Legacy Recovery And Compatibility

Doc265 is a read/continuation migration, not a destructive cleanup.

- Existing product upload records, output files, review records, old jobs,
  and old references remain append-only and are not deleted.
- Duplicate product uploads remain governed by Doc262/Doc264 content
  canonicalization; a generated output with identical pixels is still not a
  product original.
- Old ordinary V3 projects retain their existing explicit selected-output
  continuation behavior. The new separation is enforced for Professional
  E-Commerce and must not add E-Commerce suite semantics to General Template.
- The server may write a bounded recovery receipt identifying the source
  classification and canonical channel digest. The receipt must contain no
  browser authority, provider payload, file path, prompt, or raw internal
  error body.
- No ImageGen, MCP, or Provider request is sent when the only resolvable
  references are invalid output selectors or unresolved product facts.
- A historical blocked E-Commerce record may be superseded only when trusted
  persisted request admission/projection facts prove the final-ID drift shape:
  its request admission binds a different ID, while the same record's
  persisted planning result and every generation plan bind the record ID with
  a valid typed projection. Project Mode creates one new command from the
  current canonical originals and records trusted lineage; it never mutates
  the historical record or accepts a browser-supplied supersession claim.

## 6. Frontend Contract

The desktop and mobile clients must render the server-owned four-group view.
They must not reconstruct a single `reference_assets` list as a universal
generation input. For a new or continued E-Commerce request:

1. Original product uploads are sent through the product-input selector.
2. Locked person identity is sent through the existing visual-asset binding
   path.
3. Selected continuation directions are sent through the explicit output
   selection path.
4. Unselected generated/review items stay in the project history panel and
   are not automatically checked, uploaded, or included in the next command.

When an old project is loaded, the UI must show a clear recovery state if the
server cannot classify a record. It must not show both “generation stopped”
and “preparing” for one command, and it must offer one bounded action: review
or repair the affected input. Refresh and replay are idempotent.

## 7. Required Phase 0 Red Matrix

The deterministic local suite must cover:

1. Four valid product uploads plus three generated historical outputs in the
   legacy `uploaded_asset_ids` list recover to exactly four product sources;
   no output ID reaches ProductTruthAdmission or Provider dispatch.
2. An unselected generated/review output appears only in
   `generated_and_review_history`; it is absent from product inputs and
   continuation directions.
3. An explicitly selected same-project output appears in
   `selected_continuation_directions`, remains absent from product truth, and
   can be replayed without creating a second command.
4. An unknown or cross-project output selector fails closed with a sanitized
   action and never becomes a reference input.
5. A locked People Visual Asset remains in `locked_person_identity` and does
   not alter product admission, even when product originals are present.
6. A no-product project with only text and/or historical outputs retains the
   E-Commerce text-to-image path.
7. Desktop and mobile public projections expose the same four groups and do
   not display history items as active original inputs.

## 8. Phase Plan And Acceptance

Phase 0: this document and deterministic red tests only.

Phase 1: Project Mode/Product API server classification and compatibility
recovery after a renewed implementation audit.

Phase 2: desktop/mobile command projection and recovery-state presentation,
with no provider changes unless a typed contract requires a narrow adapter.

Phase 3: local focused/regression/browser verification on the integrated main
checkout. Passing Phase 0, 1, or 2 is not total acceptance.

Phase 4: only after all local tests pass, review the main commit for GitHub
publication and guarded VPS synchronization. No real generation is part of
Phase 0 or implementation diagnosis.

## 9. Non-Goals

- No prompt rewrite, retry increase, threshold relaxation, or provider switch.
- No automatic promotion of generated/review output to product truth.
- No deletion or rewriting of old project, upload, output, or review records.
- No change to Face/Body character-card authority or shared Human Realism.
- No General Template or ordinary V3 behavior change beyond preserving its
  existing explicit selected-output continuation semantics.
