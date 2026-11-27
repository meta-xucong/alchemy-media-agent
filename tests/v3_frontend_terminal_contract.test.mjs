import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(
  new URL("../src_skeleton/app/static/app.js", import.meta.url),
  "utf8",
);
const start = source.indexOf("async function completeV3GeneratedJob(");
const end = source.indexOf("\nasync function runV3GenerationWithRecovery", start);
assert.ok(start >= 0 && end > start, "desktop completion function must be present");
const completionSource = source.slice(start, end);
const partialStart = source.indexOf("function v3JobHasRecoverablePartialDelivery(");
const partialEnd = source.indexOf("\nfunction v3StoredProjectOutputItems", partialStart);
assert.ok(partialStart >= 0 && partialEnd > partialStart, "partial-delivery helper must be present");
const partialDeliverySource = source.slice(partialStart, partialEnd);
const recoveryStart = source.indexOf("async function recoverV3PlannedJob(");
const recoveryEnd = source.indexOf("\nasync function createV3Job", recoveryStart);
assert.ok(recoveryStart >= 0 && recoveryEnd > recoveryStart, "planned job recovery function must be present");
const plannedJobRecoverySource = source.slice(recoveryStart, recoveryEnd);

async function completeWith(job, expectedCount = null, { reviewItems = [], hydratedItems = [] } = {}) {
  const progress = [];
  const notices = [];
  const partialExpectedCounts = [];
  const resultBoardSnapshots = [];
  const context = {
    v3State: { selectedScenario: "general_creative", projectOutputs: [], projectReviewOutputs: [] },
    els: { v3ProjectSubpage: { hidden: true } },
    v3ScenarioWorkspaceCopy: () => ({ generatedNotice: "生成成功" }),
    v3SettleEcommerceTerminalReceipt: () => {},
    syncV3ProjectOutputsFromPayload: () => {},
    v3CurrentJobImageItems: () => context.v3State.projectOutputs.length ? context.v3State.projectOutputs : (job.candidates || []),
    v3ReviewOnlyJobImageItems: () => context.v3State.projectReviewOutputs,
    v3OutputItemIdentity: (item) => item.output_id,
    v3OutputItemCandidateId: (item) => item.candidate_id,
    v3OutputItemAssetId: (item) => item.asset_id,
    v3IsOutputItemSelected: () => false,
    v3OutputDisplayPurpose: (item) => item.purpose,
    v3OutputImageCandidates: (item) => [item.thumbnail_url],
    v3OutputDownloadUrl: (item) => item.download_url,
    v3ProjectReviewReason: (item) => item.review_reason,
    generatedImageSourceText: () => "RenderBridge",
    v3JobDeliverySettled: (value) => ["generated", "selected"].includes(value.status),
    v3JobVisibleImageCount: (value) => Number(value.visibleCount || 0),
    v3ExpectedImageCountForJob: (value, count) => Number(count ?? value.expectedCount ?? 1),
    v3JobDeliveryWithheld: (value) => value.deliveryWithheld === true,
    v3FinalDeliveryProjection: (value) => value?.metadata?.final_delivery || null,
    v3JobHasExpectedVisibleImages: (value, count) => (
      count == null
        ? value.hasExpectedDelivery === true
        : Number(value.visibleCount || 0) >= Number(count)
    ),
    v3JobFinalDeliveryNotice: () => "审查拦截",
    setV3Progress: (...args) => progress.push(args),
    renderV3Job: (value) => {
      resultBoardSnapshots.push(context.v3State.projectReviewOutputs.map((item) => item.output_id));
    },
    renderV3ResultBoard: (value) => {
      resultBoardSnapshots.push(context.v3State.projectReviewOutputs.map((item) => item.output_id));
    },
    loadV3ProjectOutputs: async () => {
      context.v3State.projectReviewOutputs = reviewItems;
      context.v3State.projectOutputs = hydratedItems;
      return true;
    },
    syncV3CurrentJobFromProjectOutputs: () => false,
    maybePersistV3UploadedReferences: async () => {},
    openV3ProjectSubpage: () => {},
    v3EcommerceFailureMessage: () => "",
    updateV3Notice: (...args) => notices.push(args),
  };
  vm.runInNewContext(`${partialDeliverySource}\n${completionSource}`, context);
  const originalPartialCheck = context.v3JobHasRecoverablePartialDelivery;
  context.v3JobHasRecoverablePartialDelivery = (value, count) => {
    partialExpectedCounts.push(count);
    return originalPartialCheck(value, count);
  };
  await context.completeV3GeneratedJob(
    job,
    [],
    { generatedNotice: "生成成功" },
    { expectedCount },
  );
  return {
    progress,
    notices,
    partialExpectedCounts,
    resultBoardSnapshots,
    formalOutputCount: context.v3State.projectOutputs.length,
  };
}

test("failed and not_found jobs with no deliverable never show success", async () => {
  for (const status of ["failed", "not_found"]) {
    const result = await completeWith({ status, hasExpectedDelivery: false, warnings: [] });
    assert.equal(result.progress[0][0], "failed");
    assert.equal(result.progress[0][2], "warning");
    assert.equal(result.notices[0][1], "warning");
  }
});

test("blocked jobs remain failures while complete delivery is successful", async () => {
  const blocked = await completeWith({ status: "blocked", hasExpectedDelivery: false, warnings: [] });
  assert.equal(blocked.progress[0][0], "failed");
  assert.equal(blocked.notices[0][1], "warning");

  const complete = await completeWith({ status: "generated", hasExpectedDelivery: true });
  assert.equal(complete.progress[0][0], "completed");
  assert.equal(complete.progress[0][2], "success");
  assert.equal(complete.notices[0][1], "success");
  assert.deepEqual(complete.resultBoardSnapshots, [[]]);
});

test("partial recovery and review-held delivery stay distinct from full success", async () => {
  const partial = await completeWith({
    status: "generated",
    hasExpectedDelivery: false,
    visibleCount: 1,
    expectedCount: 2,
    metadata: {
      partial_generation_recovery: { status: "partial_output_preserved" },
    },
  });
  assert.equal(partial.progress[0][0], "completed");
  assert.equal(partial.progress[0][2], "warning");
  assert.equal(partial.notices[0][1], "warning");

  const withheld = await completeWith({
    status: "generated",
    hasExpectedDelivery: false,
    deliveryWithheld: true,
  });
  assert.equal(withheld.progress[0][0], "review_blocked");
  assert.equal(withheld.progress[0][2], "warning");
  assert.equal(withheld.notices[0][1], "warning");
});

test("review-only images render after project refresh without becoming formal delivery", async () => {
  const result = await completeWith(
    {
      job_id: "job-review-held",
      status: "generated",
      hasExpectedDelivery: false,
      deliveryWithheld: true,
    },
    null,
    {
      reviewItems: [{ job_id: "job-review-held", output_id: "review-output-1", review_only: true }],
    },
  );

  assert.deepEqual(result.resultBoardSnapshots, [[], ["review-output-1"]]);
  assert.equal(result.formalOutputCount, 0);
});

test("a scoped gallery read refreshes the result when it supplies a thumbnail for an existing output", async () => {
  const item = { output_id: "formal-image", preview_url: "/preview" };
  const result = await completeWith({ status: "generated", hasExpectedDelivery: true, candidates: [item] }, null, {
    hydratedItems: [{ ...item, thumbnail_url: "/thumbnail" }],
  });
  assert.equal(result.resultBoardSnapshots.length, 2);
});

test("formal partial delivery from the backend remains visible as a partial outcome", async () => {
  for (const expectedCount of [2, null]) {
    const partial = await completeWith(
      {
        status: "generated",
        visibleCount: 1,
        metadata: {
          final_delivery: {
            final_delivery_status: "ready",
            automatic_delivery_available: true,
            partial_delivery: true,
            final_delivery_output_count: 1,
          },
        },
      },
      expectedCount,
    );
    assert.equal(partial.progress[0][0], "completed");
    assert.equal(partial.progress[0][2], "warning");
    assert.equal(partial.notices[0][1], "warning");
    assert.match(partial.notices[0][0], /已交付 1 张合格图片/);
    assert.notEqual(partial.notices[0][0], "生成成功");
    assert.ok(partial.partialExpectedCounts.includes(expectedCount));
  }
});

test("terminal generated payloads without expected outputs do not show success", async () => {
  const missing = await completeWith({ status: "generated", hasExpectedDelivery: false });
  assert.equal(missing.progress[0][0], "failed");
  assert.equal(missing.progress[0][2], "warning");
  assert.equal(missing.notices[0][1], "warning");

  const shortCount = await completeWith(
    { status: "generated", visibleCount: 1 },
    2,
  );
  assert.equal(shortCount.progress[0][0], "failed");
  assert.equal(shortCount.notices[0][1], "warning");
});

test("planned job recovery reads only the job bound to its operation id", async () => {
  const calls = [];
  const context = {
    v3ApiBase: "/api/v3/creative-agent",
    v3State: { currentProject: { job_ids: ["job_previous_one_image"] } },
    window: { setTimeout: (resolve) => resolve() },
    v3GenerationSessionOwns: () => true,
    readWithTimeout: (read, path, { signal } = {}) => read(path, { signal }),
    request: async (url) => {
      calls.push(url);
      if (url.endsWith("/planning-operations/op_current")) {
        return {
          operation_id: "op_current",
          state: "completed",
          job_id: "job_current_two_images",
        };
      }
      if (url.endsWith("/jobs/job_current_two_images")) {
        return { job_id: "job_current_two_images", status: "generated" };
      }
      throw new Error(`unexpected request: ${url}`);
    },
  };
  vm.runInNewContext(plannedJobRecoverySource, context);

  const result = await context.recoverV3PlannedJob("project_1", "op_current");

  assert.equal(result.job.job_id, "job_current_two_images");
  assert.deepEqual(calls, [
    "/api/v3/creative-agent/projects/project_1/planning-operations/op_current",
    "/api/v3/creative-agent/jobs/job_current_two_images",
  ]);
  assert.ok(!calls.some((url) => url.endsWith("/jobs/job_previous_one_image")));
});

test("planned job recovery continues beyond 240 reads and never follows a different operation", async () => {
  const delays = [];
  let reads = 0;
  const context = {
    v3ApiBase: "/api/v3/creative-agent",
    v3State: { currentProject: { job_ids: ["job_previous_one_image"] } },
    window: { setTimeout: (resolve, delay) => { delays.push(delay); resolve(); } },
    v3GenerationSessionOwns: (owns) => owns(),
    readWithTimeout: (read, path, { signal } = {}) => read(path, { signal }),
    request: async (url, options) => {
      assert.equal(options?.method ?? "GET", "GET");
      if (url.endsWith("/jobs/job_current")) return { job_id: "job_current", status: "finalizing" };
      assert.ok(url.endsWith("/planning-operations/op_current"));
      reads += 1;
      if (reads === 241) throw new Error("temporary read failure");
      if (reads > 245) return { operation_id: "op_current", state: "completed", job_id: "job_current" };
      return { operation_id: "op_other", state: "completed", job_id: "job_previous_one_image" };
    },
    setV3Progress: () => {},
  };
  vm.runInNewContext(plannedJobRecoverySource, context);

  const result = await context.recoverV3PlannedJob("project_1", "op_current", {
    shouldContinue: () => delays.length < 280,
  });

  assert.equal(result.operation, null);
  assert.equal(result.job?.job_id, "job_current");
  assert.equal(reads, 246);
  assert.ok(delays.at(-1) > delays[1]);
});

test("desktop submits once and follows long planning and review through to the original delivery", async () => {
  const create = source.slice(recoveryEnd, start);
  const followStart = source.indexOf("async function recoverV3GeneratedJob(");
  const followEnd = source.indexOf("\nfunction v3JobAwaitingFinalDelivery", followStart);
  const follow = source.slice(followStart, followEnd);
  const v3State = { currentProject: { project_id: "p1" }, files: [], projectDetailEpoch: 1 };
  const job = {
    job_id: "job_exact", status: "generated", asset_series: [{ output_id: "image_final" }],
    metadata: { post_generation_review: { inspections: [{ status: "pass" }] } },
  };
  const requests = [];
  let checks = 0;
  let planning = 0;
  let reviewing = 0;
  let galleryReads = 0;
  let delivered;
  const context = {
    v3State, v3ApiBase: "/v3", window: { setTimeout: (resolve) => resolve() },
    v3ScenarioWorkspaceCopy: () => ({}),
    setV3Busy: (busy) => { v3State.loading = busy; },
    startV3Progress() {}, setV3Progress() {}, updateV3Notice() {},
    uploadV3Files: async () => [], buildV3JobPayload: () => ({ metadata: {} }),
    v3CurrentGenerationSettings: () => ({ count: 1 }),
    syncV3ProjectOutputsFromPayload() {}, renderV3Job() {}, renderV3ProjectDetail() {},
    refreshV3CurrentProject: async () => {
      throw new Error("project details and timeline must not delay polling");
    },
    loadV3ProjectOutputs: async () => {
      galleryReads += 1;
      throw new Error("project outputs must not delay polling");
    },
    v3GenerationSessionOwns: (owns) => owns(), v3IsTerminalJob: () => false,
    clearV3RecoverPolling() {}, clearV3ProgressTimer() {},
    v3Delay: async () => {}, v3RecoveryDelayMs: () => 1, v3RecoveryMaxAttempts: 96,
    v3RecoveryAttemptLimitForServerWatchdog: () => 0,
    v3JobOutputProjectionSignature: () => "pending-assets", v3SettleEcommerceTerminalReceipt() {},
    v3JobHasTerminalOutcome: (result) => result.status === "generated",
    v3JobHasExpectedVisibleImages: () => true, v3JobHasRecoverablePartialDelivery: () => false,
    v3RecoveredJobFromProjectOutputs: () => null,
    v3RecoveryProgressPresentation: () => ({ stageKey: "reviewing" }),
    friendlyError: (error) => String(error),
    completeV3GeneratedJob: async (result) => { delivered = result; },
    readWithTimeout: (read, path, { signal } = {}) => read(path, { signal }),
    request: async (url, options = {}) => {
      requests.push([url, options.method || "GET"]);
      if (++checks > 390) {
        v3State.followingGeneration = null;
        throw new Error("test read ceiling");
      }
      if (url.endsWith("/projects/p1/jobs")) {
        await context.createV3Job(); // Duplicate click while the original POST is in flight.
        return { status: "planning", metadata: { current_operation: { operation_id: "op_exact" } } };
      }
      if (url.endsWith("/planning-operations/op_exact")) {
        return ++planning > 245
          ? { state: "completed", operation_id: "op_exact", job_id: "job_exact" }
          : { state: "planning", operation_id: "op_exact" };
      }
      if (url.endsWith("/jobs/job_exact")) {
        return ++reviewing > 105 ? job : { ...job, status: "finalizing" };
      }
      throw new Error(`unexpected request: ${url}`);
    },
  };
  vm.runInNewContext(`${plannedJobRecoverySource}\n${create}\n${follow}`, context);
  await context.createV3Job();

  assert.deepEqual(requests.filter(([, method]) => method !== "GET"), [["/v3/projects/p1/jobs", "POST"]]);
  assert.equal(planning, 246);
  assert.equal(reviewing, 106);
  assert.equal(galleryReads, 0);
  assert.equal(delivered, job);
  assert.equal(v3State.loading, false);
});
