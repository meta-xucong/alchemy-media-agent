# 99 V3 Deployable Identity Sidecar Gateway And Acceptance Matrix Spec

> SUPERSEDED FOR PRODUCTION BY DOC100. This gateway is retained only as an
> isolated research and benchmarking artifact. It is not a V3 provider, must not
> receive production jobs, and must not create or modify final user deliverables.

## 1. Purpose

Doc98 completed the V3-side provider contract. Doc99 supplies the independently
deployable service that translates that contract into an external GPU workflow.

The target is:

```text
keep GPU/model dependencies outside the V3 application container
connect V3 to a reviewed identity workflow through one stable HTTP contract
prove capability from configuration, workflow structure, installed nodes, and health
protect uploads, credentials, concurrency, and duplicate requests
provide a fixed multi-view identity acceptance matrix
refuse to claim quality before real sidecar outputs pass objective and manual review
```

## 2. Authority And Compatibility

Doc99 extends Doc98. It does not replace:

```text
Doc50 Visual Capability Cluster ownership
Doc76 foundation versus specialized-template governance
Doc89 portrait photography stability protocol
Doc93 reference-channel ownership
Doc95 complementary identity evidence
Doc96 objective identity metric and commercial thresholds
Doc97 subject continuity pack and adaptive reference order
Doc98 provider selection, fallback, and actual-capability audit
```

Doc99 is authoritative for:

```text
the deployable sidecar process
ComfyUI workflow translation
operator capability attestations
GPU queue and idempotency behavior
sidecar upload and output limits
sidecar certification artifacts
```

V3 Central Brain, Project Mode, Scenario Packs, Product API, and frontend remain
unchanged. The gateway is a separate process under `services/v3_identity_sidecar`.

## 3. Backend Decision

The reference gateway uses ComfyUI's official HTTP API as the execution plane:

```text
POST /upload/image
POST /prompt
GET  /history/{prompt_id}
GET  /view
GET  /system_stats
GET  /object_info
```

Primary sources:

- [ComfyUI server routes](https://docs.comfy.org/development/comfyui-server/comms_routes)
- [ComfyUI official repository](https://github.com/Comfy-Org/ComfyUI)
- [PhotoMaker official repository](https://github.com/TencentARC/PhotoMaker)
- [PhotoMaker V2 model card](https://huggingface.co/TencentARC/PhotoMaker-V2)
- [PuLID official repository](https://github.com/ToTheBeginning/PuLID)
- [InstantID official repository](https://github.com/instantX-research/InstantID)

The gateway does not hard-code a PhotoMaker, PuLID, or InstantID node. The
operator exports an API-format workflow and supplies it as data. This preserves
V3's pluggable architecture and avoids coupling the application to unstable
community-node Python environments.

### 3.1 Initial Production Candidate

PhotoMaker V2 is the preferred first candidate for controlled evaluation because
its official model card identifies an Apache-2.0 license, supports one or more
identity images, and is designed to balance identity fidelity and prompt control.
This is not a blanket commercial clearance: the operator must separately verify
the selected base model, face encoder, custom nodes, transitive dependencies,
and deployment terms.

InstantID is not the default commercial candidate because its official project
notes research restrictions for released checkpoints and face models even though
parts of the code are Apache-2.0. PuLID remains an evaluation candidate after the
same complete dependency-license review.

## 4. Deployment Topology

```text
Alchemy V3 application container
  -> private HTTPS or Docker network
      -> Doc99 identity-sidecar gateway (CPU, small image)
          -> private ComfyUI HTTP API
              -> GPU worker and identity workflow
```

The gateway container contains no CUDA, PyTorch, model weights, or face encoder.
ComfyUI owns the GPU environment. A model/node update cannot alter V3's Python
environment.

Reference files:

```text
services/v3_identity_sidecar/Dockerfile
services/v3_identity_sidecar/docker-compose.identity-sidecar.yml
services/v3_identity_sidecar/.env.example
services/v3_identity_sidecar/workflows/README.md
```

## 5. Capability Proof

The gateway returns `identity_conditioning=true` only when all gates pass:

1. `IDENTITY_MODEL_LICENSE_CONFIRMED=true`.
2. `IDENTITY_CONDITIONING_CONFIRMED=true`.
3. The identity workflow is valid API-format JSON.
4. The workflow contains `${prompt}` and `${reference_0}`.
5. ComfyUI `/system_stats` is healthy.
6. Every workflow `class_type` appears in `/object_info`.

Local repair additionally requires:

```text
a separate repair workflow
${prompt}, ${reference_0}, ${canvas}, and ${mask} tokens
IDENTITY_LOCAL_REPAIR_CONFIRMED=true
all repair workflow nodes installed
```

A generic LoadImage or mask node is not identity capability. Operator
confirmation is required because arbitrary workflow semantics cannot be proven
from node names alone.

## 6. Workflow Token Contract

Required identity tokens:

```text
${prompt}
${reference_0}
```

Optional:

```text
${negative_prompt}
${reference_1}
${reference_2}
${seed}
${width}
${height}
${quality}
${input_fidelity}
```

Repair-only:

```text
${canvas}
${mask}
```

Replacement walks parsed JSON recursively. Exact tokens retain their native
type, so `${seed}`, `${width}`, and `${height}` become integers. Embedded tokens
remain strings, allowing a workflow-specific class trigger such as:

```json
{"text": "${prompt}, person img"}
```

If a graph has more reference slots than the current request, the highest-ranked
last available reference fills remaining slots. V3 still sends Doc97 references
in authoritative order and never exceeds the workflow-reported capacity.

## 7. Runtime Sequence

```text
1. Authenticate the request.
2. Parse the Doc98 manifest with extra fields forbidden.
3. Enforce provider family, model, prompt, file, total-body, and reference limits.
4. Validate PNG/JPEG/WebP bytes with Pillow.
5. Write request-scoped temporary files.
6. Build a body fingerprint from manifest and reference hashes.
7. Collapse matching idempotent requests.
8. Serialize GPU work to configured concurrency.
9. Probe workflow, license attestation, ComfyUI health, and installed nodes.
10. Upload references to ComfyUI.
11. Render and submit the API-format workflow.
12. Poll history until output, explicit failure, or deadline.
13. Download and validate bounded image outputs.
14. Return normalized Doc98 base64 outputs.
15. Delete gateway temporary files.
```

One process defaults to one GPU request at a time. The in-memory idempotency
cache stores at most 4 recent results for three minutes by default. Failures are
not cached.

## 8. Security And Retention

```text
gateway API key uses constant-time comparison
ComfyUI credentials are never returned in audit metadata
only PNG, JPEG, and WebP uploads are accepted
Content-Length is rejected before multipart parsing when it exceeds the request budget
per-file and total-upload bounds are enforced while reading parsed upload spools
temporary gateway files are request-scoped and deleted
output bytes are size-bounded and image-validated
face embeddings are not computed or persisted by the gateway
```

ComfyUI's standard upload route stores input files in its input volume. Production
must use an ephemeral volume or a TTL cleanup policy. The service should bind to
loopback or a private network; remote deployment requires TLS and network access
control. The ingress must also enforce a body-size limit for chunked requests,
which do not provide a trustworthy `Content-Length` header.

## 9. License Deployment Gate

Before setting confirmation flags, record:

```text
identity adapter/model name and exact revision
base image model and exact revision
face detector/encoder and weights
ComfyUI custom nodes and revisions
all model and software licenses
allowed commercial use and redistribution terms
operator and review date
```

The flags are deployment attestations, not legal advice. Unknown or conflicting
terms keep capability disabled.

## 10. Controlled Acceptance Matrix

The certifier runs one uploaded identity through:

```text
front head-and-shoulders
left three-quarter
right profile
half-body
environmental portrait
```

For every output it records:

```text
provider and model
prompt and view role
dimensions and output path
Doc96 SFace calibrated identity score when available
identity threshold result
```

Automatic identity gate:

```text
every case has an objective score
minimum score >= 0.82
no case may be silently omitted
```

Manual review remains mandatory for:

```text
same-person readability across views
prompt-owned hair, makeup, wardrobe, light, camera, and scene
human realism and absence of plastic/AI-face finish
commercial beauty and facial proportion
hands, anatomy, text, watermark, and artifact cleanliness
meaningful view variation rather than cloned stills
```

The certifier always emits `quality_claim_allowed=false`. A reviewer may approve
deployment only after the objective gate and the Doc89/Doc96 manual matrix pass.

## 11. Failure Behavior

```text
bad auth                       -> 401
invalid manifest/image         -> 400
unsupported image              -> 415
file/body too large            -> 413
provider/model mismatch        -> 409
workflow semantic failure      -> 422 JSON error
ComfyUI unavailable/timeout    -> 503 JSON retryable error
```

No service error returns an HTML proxy page. Doc98 receives structured errors and
falls back to the standard provider with full audit history.

## 12. Acceptance Tests

### Service Contract

- Authentication is enforced when configured.
- Capability response mirrors backend truth.
- Multipart references and repair files are validated.
- Duplicate idempotent requests execute once.
- Invalid and oversized files never reach the backend.

### ComfyUI Adapter

- License and semantic confirmations are mandatory.
- Required workflow tokens are mandatory.
- `/system_stats` and `/object_info` are checked.
- References upload in Doc97 order.
- Typed tokens render correctly.
- `/prompt`, `/history`, and `/view` complete one output.
- Missing nodes, errors, timeouts, and empty outputs fail structurally.

### Integration

- The sidecar Docker image builds without GPU dependencies.
- Doc98 provider contract tests pass against the service.
- Existing V3, root, and frontend/API regressions pass unchanged.
- Real visual quality is not accepted without an external GPU matrix.

## 13. Definition Of Done

Doc99 engineering is complete when:

```text
the standalone gateway builds and starts
the ComfyUI adapter passes simulated end-to-end execution
capability cannot be claimed by workflow shape alone
files, auth, idempotency, concurrency, errors, and cleanup are bounded
the five-view certifier produces an auditable report
V3 core architecture and existing generation behavior are unchanged
```

Doc99 production quality remains incomplete until an authenticated GPU ComfyUI
endpoint with a legally reviewed identity workflow passes the controlled matrix.
