# Local V3 Real-Image Acceptance Receipt

Status: The official local V3 real-image run recorded below passed for its audited source snapshot. This receipt is historical evidence and does not accept the later working-tree corrections; the current corrected-code real-image acceptance is still pending. The initial Brain-gate failure and intermediate mock-path diagnostic remain historical and are excluded from that earlier acceptance.

## Frozen acceptance target

- Main baseline for this historical run: `6672d36a978848c048b3a2bae00b7cecba6e906c`.
- Independent code audit: PASS, recorded in Doc05 before this run.
- Local route: `src_skeleton.app.main:app`, exercised through the actual V3
  FastAPI API using the project's local Python environment.
- Request ID: `fcea6bd4-256f-40cf-9a85-862aee37ebff`.
- Project ID: `project_65488a6b0a`.
- Planning operation: `doc277_project_planning_36a8f5c9d1`.
- Job ID: `job_b0b590bc0b`.
- Requested scope: General Template, one 1024x1024 image, no uploaded reference,
  standard quality, visual automatic retry disabled.

## Result and evidence

- Terminal job state: `blocked`.
- Blocking stage: remote Brain `plan`; `blocked_before_planning=true`.
- Primary model: `claude-sonnet-5-5`; result: failed structured response after
  60,738 ms (`invalid_structured_response`).
- Backup model: `gpt-6.1-sol`; fallback was selected and attempted, then failed
  during connection setup after 239,269 ms (`timeout`, `connect_timeout`).
- Remote Brain outcome: `remote_brain_unavailable`. The Claude Brain request
  did start and returned content that failed structured-response parsing. The
  exact response body was not persisted, so the malformed content cannot be
  diagnosed retrospectively. The GPT fallback request then timed out in
  connection setup; its terminal receipt reports `request_dispatched=false`
  for that GPT attempt and request acceptance as unknown. The image provider
  was not invoked.
- Candidate count: 0. Selected result: none. Exported assets: 0.
- After the failed run, DNS resolution for the configured gateway host and a
  TCP connection to port 443 both succeeded. This confirms current basic
  network reachability only; it does not prove the gateway API or model routes
  are healthy, and it does not explain either the primary structured-response
  failure or the earlier fallback connection timeout.
- No retry was submitted. The terminal job record was inspected read-only.

## Acceptance status

The initial local attempt failed before image generation. The timeout
correction passed focused tests and fresh independent code audit. The
intermediate follow-up below is excluded because it used the mock contract
path; the later corrected official-endpoint run is the passing acceptance
evidence.

## Follow-up diagnostic run (not acceptance)

- Project/job: `project_166c1b4ca9` / `job_d85cf4b07b`.
- The job was created by calling the in-process V3 route handler directly. This
  bypassed the public `/projects/{id}/jobs` endpoint's `auto_generate` intent
  envelope, so the frozen job request had neither `require_real_images` nor
  `real_image_generation`. The official web UI does send this envelope.
- Provider strategy consequently resolved to `MOCK_GENERATION`; `explore`
  returned a 2x2 fixture (`v3_mock_contract_fixture` / `deterministic-2px`).
  The `generated` job status is not evidence of a real Brain or image-provider
  success. Preserve the fixture and job record; do not display it as the
  requested image.
- In the Brain audit, Claude and GPT both ended as `retryable_upstream` with
  `connection_error` after 1,186 ms and 3,563 ms. The terminal safe receipt
  reports request acceptance `unknown` and `request_dispatched=false`; it does
  not identify whether DNS, TCP, TLS, or gateway routing failed.
- A read-only local probe at the same point could not resolve `aiself.vip` and
  could not open TCP port 443. This supports a local DNS/network reachability
  problem at probe time, but cannot distinguish sandbox egress policy from a
  transient local network issue or establish the gateway's own health.
- No further provider calls were made. Real acceptance needs the official
  public endpoint with explicit `auto_generate.metadata.require_real_images`
  and a reachable gateway. The earlier Claude `invalid_structured_response`
  remains a separate issue with no persisted response body.

## Corrected official-endpoint real-image run

- Date/time (local): 2026-10-18 04:28–04:32 Asia/Shanghai.
- Local app: `src_skeleton.app.main:app`, on `127.0.0.1:18105`; health check
  returned HTTP 200. The job was submitted through the public
  `POST /api/v3/creative-agent/projects/{project_id}/jobs` endpoint.
- Project/job: `project_166c1b4ca9` / `job_df6825a9fd`.
- The first client wait timed out while the server continued processing. A
  second submission returned the same existing planning operation; it did not
  create a duplicate. The durable operation completed as
  `doc277_project_planning_454e48e14f` and linked to the single job above.
- Frozen request intent: `require_real_images=true`, one 1024x1024 image,
  `quality_mode=explore`, visual auto-retry disabled. The persistent Job record
  confirms the real-image flag; it did not select mock generation.
- Brain route: `anthropic / claude-sonnet-5-5`; `fallback_used=false`.
- Image route: `openai_gpt_image / gpt-image-2`; terminal job state `generated`.
- Output: `v3_output_c0acb2f6cbe742e8a99f`, 1024x1024 PNG, 1,944,177 bytes.
  The output metadata has no mock fixture marker, and the original image file
  exists at `.media_storage/v3_outputs/v3_output_c0acb2f6cbe742e8a99f/original.png`.
- The image was visually inspected locally and is shown to the user. The job
  carries `output_review_metadata_only`, so this run proves the official
  end-to-end Brain plus image-provider route and real image persistence; it
  does not claim a live automated pixel-review pass.
- A fresh elevated read-only DNS/TCP probe resolved `aiself.vip` to
  `45.113.1.228` and connected to TCP 443. This shows reachability at the
  latest test time, but the old receipt lacks enough detail to prove whether
  its earlier connection timeout was caused by transient local networking,
  Sub2API, or its upstream route.
- The temporary local service was stopped after the run. No VPS deployment,
  commit, or push was performed.
