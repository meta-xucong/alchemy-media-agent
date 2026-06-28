# 28 V3 Asset Upload And Export Closure Specification

This document records the post-document-26 production-closure slice that turns
the active E-Commerce Scenario Pack from a planning-only UI into a usable
upload, asset-analysis, job-creation, and export-manifest loop.

It exists because documents `23` through `27` define the foundation, shared
capabilities, General Creative productization, E-Commerce Scenario Pack, and
commercial frontend shell, but they do not explicitly close the product gap
between:

```text
user selects local product images
-> V3 receives real uploaded assets
-> shared capabilities inspect those assets
-> E-Commerce jobs use real asset records as product evidence
-> frontend receives export metadata that can be downloaded
```

## 1. Relationship To Earlier Documents

This document is additive.

It depends on:

```text
23_V3_FOUNDATION_GAP_AUDIT_AND_COMPLETION_SPEC.md
24_V3_SHARED_CAPABILITY_MODULES_FROM_V1_V2_SPEC.md
25_GENERAL_CREATIVE_DOC_DELTA_FOR_SHARED_CAPABILITIES.md
26_ECOMMERCE_SCENARIO_PACK_AND_COMMERCE_CAPABILITY_SPEC.md
27_V3_COMMERCIAL_FRONTEND_SHELL_AND_PAGE_SPEC.md
```

It does not replace document `26`. It closes the first practical handoff loop
needed by document `26`: real uploaded product/reference images can now enter
the V3-owned Product API and E-Commerce export metadata can leave it.

## 2. Scope

Implement:

1. V3-owned uploaded asset lifecycle.
2. V3 upload Product API contracts.
3. FastAPI routes under `/api/v3/creative-agent/uploads`.
4. Product API resolution from `uploaded_asset_ids` to `UploadedAssetInfo`.
5. Real local file inspection by shared capabilities when assets are uploaded through V3.
6. E-Commerce export response and downloadable JSON manifest routes.
7. Frontend upload-before-create flow in the commercial V3 shell.
8. Focused tests and regression tests proving V3 independence.

## 3. Non-Goals

This document does not implement:

1. Real provider image generation for V3 E-Commerce outputs.
2. ZIP batch download of final generated images.
3. Pixel-level QA for generated provider outputs.
4. Slot-level regeneration UI for one E-Commerce recipe.
5. New Media, Private Domain, Brand IP, or other future Scenario Packs.
6. Direct V1/V2 runtime imports or compatibility adapters.
7. Provider-level controls such as seed, sampler, LoRA, ControlNet, IP-Adapter scale, or node graphs.

Those items are future boundaries and must receive their own accepted specs or
phase plans before implementation.

## 4. Required Backend Contracts

Add V3 Product API contracts for:

```text
V3AssetUploadCreateRequest
V3AssetContentUploadRequest
V3UploadedAssetRecord
V3ExportPackageResponse
V3ExportDownloadPayload
```

The upload contracts must remain product-level. They may contain file metadata
and base64 image content, but they must not expose image-model controls.

## 5. Required Upload Lifecycle

The V3 Product API must support:

```text
POST /api/v3/creative-agent/uploads
PUT  /api/v3/creative-agent/uploads/{asset_id}/content
POST /api/v3/creative-agent/uploads/{asset_id}/complete
GET  /api/v3/creative-agent/uploads/{asset_id}
GET  /api/v3/creative-agent/uploads/{asset_id}/content
```

Required behavior:

1. Accept PNG, JPEG, and WebP images.
2. Reject unsupported MIME types.
3. Enforce a bounded upload size.
4. Sanitize filenames before writing to local storage.
5. Validate image bytes before marking an upload ready.
6. Persist metadata and image bytes in a V3-owned storage area.
7. Return V3-owned `asset_id` values.

## 6. Runtime Resolution Rules

When a Product API request includes `uploaded_asset_ids`, the service must:

1. Look up each ID in the V3 upload store.
2. Convert found records into `UploadedAssetInfo`.
3. Include `file_path`, `filename`, `mime_type`, role, URI, and upload metadata when available.
4. Preserve metadata-only fallback behavior for legacy or external asset IDs.
5. Pass the resolved `uploaded_assets` list into `ScenarioRuntime`.

This lets `AssetRoleAnalyzer` inspect real pixels for V3-uploaded assets while
remaining backward-compatible with older metadata-only IDs.

## 7. E-Commerce Export Closure

The Product API must expose:

```text
GET /api/v3/creative-agent/jobs/{job_id}/export
GET /api/v3/creative-agent/jobs/{job_id}/export/download
```

For E-Commerce jobs, export metadata must include:

1. job id and scenario id
2. package id
3. platform and market
4. uploaded asset summaries
5. product truth
6. commerce brief
7. image recipes
8. export file records
9. critic/review checks
10. warnings
11. `imports_v1_v2_runtime: false`

The download route may return a JSON manifest in this phase. A final ZIP asset
bundle belongs to a later generated-output packaging phase.

## 8. Frontend Closure

The commercial V3 frontend must:

1. Accept user-selected local image files.
2. Upload valid image files to the V3 upload API before creating a job.
3. Use returned V3 `asset_id` values in `uploaded_asset_ids`.
4. Stop using fake frontend-only asset IDs.
5. Keep the user flow simple: upload images, enter a short prompt, create job.
6. Keep all V3 actions inside `/api/v3/creative-agent/*`.

## 9. Acceptance Criteria

This document is complete when:

1. V3 upload lifecycle routes work.
2. Upload content can be retrieved from V3 routes.
3. Uploaded assets resolve into `UploadedAssetInfo` with local `file_path`.
4. Shared capability metadata proves local image inspection ran for V3-uploaded assets.
5. E-Commerce product truth uses uploaded asset evidence.
6. E-Commerce export and export/download routes return useful metadata.
7. The V3 commercial frontend uploads files before job creation.
8. No fake `frontend_reference_*` asset IDs remain in the V3 frontend.
9. V3 backend and frontend remain isolated from V1/V2 runtime APIs.
10. Focused tests, full V3 tests, root tests, compile checks, JS checks, and diff checks pass.

## 10. Implementation Status

Status: complete for the scope of this document.

Implemented files include:

```text
app/product_api/assets.py
app/product_api/contracts.py
app/product_api/service.py
app/product_api/route_handlers.py
src_skeleton/app/main.py
src_skeleton/app/static/app.js
```

Focused tests include:

```text
alchemy_creative_agent_3_0/tests/test_v3_asset_upload_and_export_doc28.py
tests/test_v3_commercial_frontend_shell.py
```

Final verification for this document:

```text
Doc28 focused tests: passed
V3 commercial frontend/API smoke: passed
full V3 package suite: passed
main app smoke plus V3 smoke: passed
root pytest: passed
compile audit: passed
desktop/mobile JavaScript syntax: passed
scope audits: passed
git diff --check: passed with LF-to-CRLF warnings only
```

## 11. What Is Still Future Work

The following work is not part of this document and must not be counted as a
Doc28 defect:

1. Real provider-produced E-Commerce images.
2. Final image asset binding per E-Commerce recipe.
3. Batch export ZIP containing generated images and manifest.
4. Visual QA over generated provider outputs.
5. Slot-level regenerate/edit flows.
6. Future vertical Scenario Packs.

Recommended next boundary after user acceptance:

```text
V3.8B Provider/output production closure
```

That future boundary should connect E-Commerce recipes and V3 generation output
storage to real or mock provider assets, then add downloadable final image
packages and generated-output review gates.
