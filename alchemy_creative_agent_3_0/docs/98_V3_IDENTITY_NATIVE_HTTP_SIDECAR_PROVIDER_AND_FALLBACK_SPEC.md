# 98 V3 Identity-Native HTTP Sidecar Provider And Fallback Spec

## 1. Purpose

Doc98 turns the identity-native extension point reserved by Doc96 and Doc97
into an operational provider contract. It does not embed a GPU runtime into V3
and does not add model logic to the Central Brain.

The target is:

```text
let an external InstantID, PhotoMaker, PuLID, or equivalent backend plug in
require live capability evidence before calling it identity-native
route only applicable portrait-identity jobs to that backend
fall back to the existing image provider when the optional sidecar is unhealthy
record whether identity-native execution was attempted, delivered, or degraded
let local identity repair run only when the delivered backend explicitly supports it
```

Doc98 is a provider-ceiling extension. Prompt rules, reference ranking, identity
metrics, visual review, and best-result selection remain necessary.

## 2. Authority And Compatibility

Doc98 extends:

```text
Doc12 provider interfaces
Doc58 selected-output strong-reference loop
Doc80 provider reference transport compression
Doc81 provider failure retry
Doc85 image-to-image reference truth
Doc93 reference-channel ownership
Doc95 complementary identity evidence
Doc96 objective identity metric and bounded repair
Doc97 subject continuity pack and capability-gated repair routing
```

Doc98 is authoritative when older text implies that `PhotoMakerProvider`,
`InstantIDProvider`, or `ComfyUISidecarProvider` is already a live generator.
Those condition-engine facades remain optional unavailable placeholders. The
live integration is the normalized `IdentityNativeSidecarProvider` in the app
provider layer.

Doc98 does not change:

```text
Project -> Template -> Scenario Pack -> Job ownership
Central Brain or LLM orchestration
Visual Capability Cluster child-module boundaries
General/E-Commerce template semantics
V1/V2/Lab runtime independence
account isolation, output storage, or frontend workflows
the user's written prompt
```

## 3. Architecture Placement

```text
Central Brain
  decides intent, template, prompt-owned channels, and user controls

Visual Capability Cluster
  builds Doc97 SubjectContinuityAssetPackage
  ranks references and keeps uploaded root truth
  reviews identity and commercial quality

Generation Router
  detects whether the Doc97 package is an applicable character package
  chooses the identity sidecar only when locally enabled
  records attempted/delivered/fallback state

IdentityNativeSidecarProvider
  probes live capabilities
  sends normalized multipart requests
  validates returned image bytes and capability evidence

External GPU service
  implements InstantID, PhotoMaker, PuLID, or a compatible identity engine

Existing GPT Image/Gemini provider
  remains the bounded fallback
```

The sidecar is an ordinary provider plugin. It is not a Central Brain child and
does not own project memory, prompt compilation, or final selection.

## 4. Configuration

The feature is disabled by default.

```dotenv
V3_IDENTITY_SIDECAR_ENABLED=false
V3_IDENTITY_SIDECAR_BASE_URL=https://identity-sidecar.example.com
V3_IDENTITY_SIDECAR_API_KEY=
V3_IDENTITY_SIDECAR_PROVIDER=pulid
V3_IDENTITY_SIDECAR_MODEL=identity-native
V3_IDENTITY_SIDECAR_CAPABILITIES_PATH=/v1/capabilities
V3_IDENTITY_SIDECAR_GENERATE_PATH=/v1/identity/generate
V3_IDENTITY_SIDECAR_TIMEOUT_SECONDS=420
V3_IDENTITY_SIDECAR_HEALTH_TIMEOUT_SECONDS=10
V3_IDENTITY_SIDECAR_HEALTH_TTL_SECONDS=30
V3_IDENTITY_SIDECAR_MAX_REFERENCES=3
```

Supported provider-family labels are descriptive, not hard-coded execution
branches:

```text
instantid
photomaker
pulid
custom
```

The external service chooses its internal checkpoints, GPU runtime, and model
files. V3 consumes only the normalized contract.

## 5. Capability Contract

### 5.1 Probe

```http
GET /v1/capabilities
Authorization: Bearer <optional key>
```

Minimum valid response:

```json
{
  "status": "ok",
  "provider": "pulid",
  "models": ["pulid-flux"],
  "capabilities": {
    "identity_conditioning": true,
    "multi_reference": true,
    "identity_native_local_repair": false
  }
}
```

Rules:

```text
identity_conditioning=true is mandatory
multi_reference is recorded from the live response
identity_native_local_repair is false unless explicitly true
local configuration alone is never capability evidence
capability responses may be cached only for the configured health TTL
```

### 5.2 Generation

```http
POST /v1/identity/generate
Content-Type: multipart/form-data
```

Form parts:

```text
manifest      application/json
reference_0   image/*
reference_1   image/*, optional
reference_2   image/*, optional
canvas        image/*, required only for local repair
mask          image/*, required only for local repair
```

Multipart is required instead of JSON base64 input so reference transport does
not pay base64's body-size overhead. References reuse the existing provider
derivative/compression path.

Manifest:

```json
{
  "contract_version": "doc98-v1",
  "operation": "identity_reference_generation",
  "backend_family": "pulid",
  "model": "identity-native",
  "prompt": "lossless V3 provider prompt",
  "negative_constraints": [],
  "count": 1,
  "size": "1024x1536",
  "quality": "high",
  "output_format": "png",
  "idempotency_key": "...",
  "trace_id": "...",
  "input_fidelity": "high",
  "reference_manifest": [
    {
      "field": "reference_0",
      "asset_id": "...",
      "source_asset_id": "...",
      "truth_layer": "portrait_identity_truth",
      "derivative_kind": "portrait_identity_crop"
    }
  ],
  "requested_capabilities": {
    "identity_conditioning": true,
    "multi_reference": false,
    "identity_native_local_repair": false
  },
  "repair": {
    "active": false,
    "canvas_field": null,
    "mask_field": null
  }
}
```

The external service must return base64 image data in the normalized response:

```json
{
  "provider": "pulid",
  "model": "pulid-flux",
  "outputs": [
    {
      "b64_json": "...",
      "mime_type": "image/png",
      "format": "png",
      "width": 1024,
      "height": 1536
    }
  ]
}
```

V3 validates that outputs exist and that `b64_json` is valid before persistence.

## 6. Eligibility And Routing

All conditions must be true:

```text
V3_IDENTITY_SIDECAR_ENABLED=true
base URL is configured
Doc97 SubjectContinuityAssetPackage applies
subject_type=character
the provider input plan contains portrait_identity_truth
at least one identity reference file is readable
the live sidecar advertises identity_conditioning=true
```

The sidecar must not receive:

```text
pure text-to-image jobs
product-only jobs
style-only references
scene-only references
an inferred portrait without Doc97 subject-continuity evidence
```

The sidecar receives at most three Doc97-ranked identity references. User-selected
master priority and uploaded-root retention remain owned by Doc97.

## 7. Failure And Fallback State Machine

```text
not eligible
  -> use the existing provider directly

eligible and capability probe succeeds
  -> run one sidecar request
  -> persist and review normally

capability probe or sidecar request fails
  -> record the sidecar failure classification
  -> select the existing configured image provider
  -> run its existing bounded retry policy
  -> never label fallback output as identity-native

sidecar and fallback both unavailable
  -> preserve the original error and attach fallback-unavailable audit evidence
```

The optional sidecar gets one V3-level attempt. Its own HTTP/model service may
implement bounded internal retries. V3 then spends its remaining work on the
known fallback rather than repeatedly waiting on the same unavailable GPU lane.

Audit fields:

```text
identity_sidecar_attempted
identity_sidecar_fallback
identity_sidecar_failure_classification
final_provider
identity_native_routing.attempted
identity_native_routing.delivered
identity_native_routing.fallback_used
identity_native_routing.capability_evidence_source
```

## 8. Local Identity Repair

Doc97's pre-generation repair strategy remains conservative. After generation,
the Product API may unlock one bounded local identity repair only when the
persisted output proves all of the following:

```text
identity-native output was actually delivered
live sidecar response advertised identity_native_local_repair=true
the candidate remains in Doc96's repairable identity-score band
no existing artifact, anatomy, policy, or prompt-ownership blocker applies
the repaired result passes the existing reviewed best-result gate
```

A configured sidecar, a provider name, mask support, or generic image edit is
not sufficient.

## 9. Security And Privacy

```text
API keys are sent only in Authorization headers
capability audit stores booleans and provider family, not secrets
manifest contains IDs and truth-layer labels, not biometric vectors
face embeddings and provider-private tensors remain non-persistent
reference files remain bounded and use the existing transport preparation
response body is not persisted beyond normalized output and public audit summary
```

Deploy the sidecar behind TLS and an authenticated private route. Production
operators should restrict network access to the Alchemy application host.

## 10. Acceptance Tests

### 10.1 Contract

- Disabled or unconfigured sidecar reports not configured.
- Missing live `identity_conditioning` is rejected.
- Multipart contains one manifest and bounded identity references.
- Invalid or missing base64 output is rejected.
- Capability booleans come from the live response.

### 10.2 Routing

- Applicable Doc97 character jobs choose the sidecar.
- Product subject packages choose the standard provider.
- No Doc97 package means no sidecar routing.
- Sidecar failure falls back to the existing provider.
- Fallback outputs never claim identity-native delivery.

### 10.3 Repair

- Delivered live local-repair capability may unlock Doc96's bounded repair.
- Config-only or failed-sidecar metadata cannot unlock repair.
- A worse repair still cannot replace the reviewed best result.

### 10.4 Regression

- Doc96, Doc97, provider-output, V3, root, and frontend/API tests pass.
- Existing optional condition-engine sidecar facade tests remain valid.
- V1/V2/Lab imports remain absent from the V3 provider plugin.

## 11. Deployment And Real Quality Gate

Code completion and quality completion are separate gates.

```text
Gate A: adapter, routing, fallback, audit, and regression tests pass
Gate B: an external GPU sidecar is deployed and health checks pass
Gate C: fixed-seed or controlled A/B portrait suite is generated
Gate D: identity, prompt ownership, realism, and commercial beauty are reviewed
Gate E: only then may the sidecar be enabled by default in production
```

The minimum real A/B set should use the same uploaded person across frontal,
three-quarter, profile, half-body, and environmental shots. It must compare the
sidecar route with the current GPT Image route using Doc89 and Doc96 metrics.

## 12. Definition Of Done

Doc98 engineering is complete when:

```text
the HTTP sidecar contract is executable
routing is limited to Doc97 portrait-identity jobs
live capabilities are mandatory and auditable
sidecar failure degrades to the existing provider without blocking the project
fallback results cannot masquerade as identity-native
actual capability evidence controls local repair
all relevant regression tests pass
```

Doc98 visual validation is complete only after a real external identity backend
is configured and passes the A/B quality gate. With no GPU sidecar endpoint,
V3 remains on its current provider and this document makes no image-quality gain
claim.
