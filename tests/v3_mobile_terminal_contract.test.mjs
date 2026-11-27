import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(
  new URL("../src_skeleton/app/mobile_static/mobile.js", import.meta.url),
  "utf8",
);
const projectionStart = source.indexOf("function mobileV3FinalDeliveryProjection(");
const noticeStart = source.indexOf("function mobileV3FormalPartialDeliveryNotice(");
const reviewLinesStart = source.indexOf("function mobileV3JobReviewLines(", noticeStart);
assert.ok(projectionStart >= 0, "mobile final-delivery projection must be present");
assert.ok(noticeStart > projectionStart, "mobile partial-delivery notice must follow the projection");
assert.ok(reviewLinesStart > noticeStart, "mobile partial-delivery notice boundary must be present");
const productionNoticeSource = source.slice(projectionStart, reviewLinesStart);
const completionStart = source.indexOf("const deliveryWithheld = mobileV3JobDeliveryWithheld(finalJob);");
const completionEnd = source.indexOf("  } catch (error) {", completionStart);
assert.ok(completionStart >= 0 && completionEnd > completionStart, "mobile terminal completion block must be present");
const completionSource = source.slice(completionStart, completionEnd);
const plannedRecoveryStart = source.indexOf("async function recoverMobileV3PlannedJob(");
const plannedRecoveryEnd = source.indexOf("\nasync function generateMobileV3Job", plannedRecoveryStart);
assert.ok(plannedRecoveryStart >= 0 && plannedRecoveryEnd > plannedRecoveryStart, "mobile planned job recovery function must be present");
const plannedRecoverySource = source.slice(plannedRecoveryStart, plannedRecoveryEnd);

test("backend formal partial delivery reports the eligible image count on mobile", () => {
  const context = {};
  vm.runInNewContext(productionNoticeSource, context);
  const backendResponse = {
    job_id: "job_partial_delivery_contract",
    status: "generated",
    asset_series: [{ output_id: "output_eligible_1", asset_id: "asset_1" }],
    metadata: {
      final_delivery: {
        final_delivery_status: "ready",
        delivery_gate_applies: true,
        automatic_delivery_available: true,
        partial_delivery: true,
        reviewed_output_count: 2,
        final_delivery_output_count: 1,
      },
    },
  };

  const notice = context.mobileV3FormalPartialDeliveryNotice(backendResponse);
  assert.match(notice, /已交付 1 张合格图片/);
  assert.match(notice, /其余图片未通过审核或需要人工确认/);
  assert.match(completionSource, /const partialDeliveryNotice = mobileV3FormalPartialDeliveryNotice\(finalJob\)/);
  assert.match(completionSource, /: partialDeliveryNotice \|\| "生成完成"/);
});

test("mobile does not label full or review-held delivery as formal partial delivery", () => {
  const context = {};
  vm.runInNewContext(productionNoticeSource, context);
  const fullDelivery = {
    metadata: { final_delivery: { automatic_delivery_available: true, partial_delivery: false, final_delivery_output_count: 2 } },
  };
  const reviewHeld = {
    metadata: { final_delivery: { automatic_delivery_available: false, partial_delivery: true, final_delivery_output_count: 1 } },
  };
  assert.equal(context.mobileV3FormalPartialDeliveryNotice(fullDelivery), "");
  assert.equal(context.mobileV3FormalPartialDeliveryNotice(reviewHeld), "");
});

test("mobile planned job recovery reads only the job bound to its operation id", async () => {
  const calls = [];
  const context = {
    mobileV3State: { currentProject: { job_ids: ["job_previous_one_image"] } },
    window: { setTimeout: (resolve) => resolve() },
    mobileV3GenerationSessionOwns: () => true,
    readWithTimeout: (read, path, { signal } = {}) => read(path, { signal }),
    mobileV3Request: async (url) => {
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
  vm.runInNewContext(plannedRecoverySource, context);

  const result = await context.recoverMobileV3PlannedJob("project_1", "op_current");

  assert.equal(result.job.job_id, "job_current_two_images");
  assert.deepEqual(calls, [
    "/projects/project_1/planning-operations/op_current",
    "/jobs/job_current_two_images",
  ]);
  assert.ok(!calls.some((url) => url.endsWith("/jobs/job_previous_one_image")));
});

test("mobile cancelled planning recovery does not write a stale project after refresh", async () => {
  let ownsSession = true;
  const previousProject = { project_id: "project_1", marker: "previous" };
  const context = {
    mobileV3State: { currentProject: previousProject },
    window: { setTimeout: (resolve) => resolve() },
    mobileV3GenerationSessionOwns: () => ownsSession,
    readWithTimeout: (read, path, { signal } = {}) => read(path, { signal }),
    mobileV3Request: async (url) => {
      if (url.endsWith("/planning-operations/op_current")) {
        return { operation_id: "op_current", state: "planning_failed" };
      }
      ownsSession = false;
      return { project: { project_id: "project_1", marker: "stale_refresh" } };
    },
  };
  vm.runInNewContext(plannedRecoverySource, context);

  const result = await context.recoverMobileV3PlannedJob("project_1", "op_current");

  assert.equal(result.operation, null);
  assert.equal(result.job, null);
  assert.equal(context.mobileV3State.currentProject.marker, "previous");
});

test("mobile keeps following the original planning operation beyond the old polling limit", async () => {
  let reads = 0;
  let ticks = 0;
  const context = {
    window: { setTimeout: (resolve) => { ticks += 1; resolve(); } },
    mobileV3GenerationSessionOwns: (owns) => owns(),
    setMobileV3Progress: () => {},
    readWithTimeout: (read, path, { signal } = {}) => read(path, { signal }),
    mobileV3Request: async (url, options) => {
      assert.equal(options?.method ?? "GET", "GET");
      if (url.endsWith("/jobs/job_current")) return { job_id: "job_current", status: "finalizing" };
      assert.ok(url.endsWith("/planning-operations/op_current"));
      reads += 1;
      if (reads === 241) throw new Error("temporary read failure");
      return reads > 245
        ? { operation_id: "op_current", state: "completed", job_id: "job_current" }
        : { operation_id: "op_current", state: "planning" };
    },
  };
  vm.runInNewContext(plannedRecoverySource, context);

  const result = await context.recoverMobileV3PlannedJob("project_1", "op_current", {
    shouldContinue: () => ticks < 280,
  });

  assert.equal(result.job?.job_id, "job_current");
  assert.equal(reads, 246);
});

test("mobile submission stays locked until the bound job finishes review", async () => {
  const followEnd = source.indexOf("\nfunction mobileV3RecoveryDelayMs", plannedRecoveryEnd);
  const projectStart = source.indexOf("function mobileV3ProjectWithResponseMetadata(");
  const projectEnd = source.indexOf("\nfunction applyMobileV3GenerationPreferences", projectStart);
  const mobileV3State = { currentProject: { project_id: "p1", primary_template_id: "general" }, files: [], generationCount: 1 };
  const job = {
    job_id: "job_exact", status: "generated",
    metadata: { post_generation_review: { inspections: [{ status: "pass" }] } },
  };
  const requests = [];
  const progress = [];
  let reviewing = 0;
  let displayed;
  const context = {
    mobileV3State, window: { setTimeout: (resolve) => resolve() },
    document: { body: { dataset: {} } },
    mobileV3ScenarioForTemplate: () => "general_creative", mobileV3BoundedCount: () => 1,
    setMobileV3Busy: (busy) => { mobileV3State.busy = busy; },
    uploadMobileV3Files: async () => [], buildMobileV3JobPayload: () => ({}),
    mobileV3GenerationSessionOwns: (owns) => owns(),
    mobileV3JobNeedsProductInputReview: () => false, mobileV3IsTerminalJob: () => false,
    setMobileV3Progress: (stage) => progress.push(stage), updateMobileV3Status() {},
    renderMobileV3ProjectOutputs: () => { displayed = mobileV3State.currentJob; },
    renderMobileV3ProjectCurrentOperation() {},
    mobileV3MergeProjectOutputs: (_projectId, outputs) => { mobileV3State.outputs = outputs; },
    mobileV3RecoveryDelayMs: () => 1, mobileV3RecoveryAttemptLimitForServerWatchdog: () => 0,
    mobileV3RecoveryProgressPresentation: () => ({}),
    mobileV3JobHasTerminalOutcome: (result) => result.status === "generated",
    loadMobileV3ProjectOutputs: async () => { mobileV3State.outputs = [{ output_id: "image_final" }]; },
    mobileV3SettleEcommerceTerminalReceipt() {},
    refreshMobileV3ProjectDetail: async () => { throw new Error("auxiliary project read temporarily failed"); },
    mobileV3JobDeliveryWithheld: () => false, mobileV3FormalPartialDeliveryNotice: () => "",
    friendlyError: (error) => String(error),
    readWithTimeout: (read, path, { signal } = {}) => read(path, { signal }),
    mobileV3Request: async (url, options = {}) => {
      requests.push([url, options.method || "GET"]);
      if (requests.length > 130) {
        mobileV3State.followingGeneration = null;
        throw new Error("test read ceiling");
      }
      if (url === "/projects/p1/jobs") {
        await context.generateMobileV3Job();
        return { status: "planning", metadata: { current_operation: { operation_id: "op_exact", state: "planning" } } };
      }
      if (url.endsWith("/planning-operations/op_exact")) {
        return { state: "completed", operation_id: "op_exact", job_id: "job_exact" };
      }
      if (url === "/jobs/job_exact") {
        return ++reviewing > 75 ? job : { ...job, status: "finalizing" };
      }
      throw new Error(`unexpected request: ${url}`);
    },
  };
  vm.runInNewContext(source.slice(projectStart, projectEnd) + source.slice(plannedRecoveryStart, followEnd), context);
  await context.generateMobileV3Job();

  assert.deepEqual(requests.filter(([, method]) => method !== "GET"), [["/projects/p1/jobs", "POST"]]);
  assert.equal(reviewing, 76);
  assert.equal(displayed, job);
  assert.deepEqual(mobileV3State.outputs, [{ output_id: "image_final" }]);
  assert.equal(progress.at(-1), "completed");
  assert.equal(mobileV3State.currentProject.metadata.current_operation, undefined);
  assert.equal(mobileV3State.busy, false);
});

test("mobile moves from the composer to this job's visible results with one gallery read", async () => {
  const start = source.indexOf("async function showMobileV3FinishedResults(");
  const end = source.indexOf("\nasync function recoverMobileV3GeneratedJob(", start);
  const reads = [];
  const transitions = [];
  const actions = [];
  let active = "v3-compose";
  let current = true;
  let owns = true;
  let leaveDuringRead = false;
  const job = { job_id: "job_new", candidates: [{ output_id: "candidate_review" }] };
  const card = (id, jobId, { review = false, history = false } = {}) => {
    const element = { scrollIntoView: () => actions.push(["scroll", id]) };
    return {
      __mobileV3OutputItem: { output_id: id, job_id: jobId },
      dataset: { mobileV3ReviewOnly: String(review) },
      closest: (selector) => selector.endsWith(".history-only") ? (history ? element : null) : element,
      focus: () => actions.push(["focus", id]),
    };
  };
  const previous = card("previous", "job_old");
  const superseded = card("superseded", "job_new", { history: true });
  const review = card("candidate_review", "", { review: true });
  const delivered = card("delivered", "job_new");
  let cards = [previous, superseded, review, delivered];
  const context = {
    mobileV3State: { get currentProject() { return { project_id: current ? "p1" : "p2" }; } },
    document: {
      body: { dataset: { get mobileActiveSurface() { return active; } } },
      querySelectorAll: () => cards,
    },
    loadMobileV3ProjectOutputs: async (project, options) => {
      reads.push([project, options.limit]);
      if (leaveDuringRead) active = "v3-workflow";
    },
    mobileV3GenerationSessionOwns: (shouldContinue) => shouldContinue(),
    openMobileSurface: (surface) => { transitions.push(surface); active = surface; },
  };
  vm.runInNewContext(source.slice(start, end), context);

  await context.showMobileV3FinishedResults("p1", job, () => owns);
  assert.deepEqual(reads, [["p1", 120]]);
  assert.deepEqual(transitions, ["v3-project-detail"]);
  assert.deepEqual(actions, [["scroll", "delivered"], ["focus", "delivered"]]);

  active = "v3-compose";
  cards = [previous, superseded, review];
  await context.showMobileV3FinishedResults("p1", job, () => owns);
  assert.deepEqual(actions.slice(-2), [["scroll", "candidate_review"], ["focus", "candidate_review"]]);

  active = "v3-compose";
  cards = [previous, superseded];
  await context.showMobileV3FinishedResults("p1", job, () => owns);
  assert.equal(transitions.length, 2);

  cards = [delivered];
  leaveDuringRead = true;
  await context.showMobileV3FinishedResults("p1", job, () => owns);
  assert.equal(transitions.length, 2);

  active = "v3-compose";
  leaveDuringRead = false;
  current = false;
  await context.showMobileV3FinishedResults("p1", job, () => owns);
  current = true;
  owns = false;
  await context.showMobileV3FinishedResults("p1", job, () => owns);
  assert.equal(transitions.length, 2);
});

test("mobile progress displays only the matching terminal outcome", () => {
  const start = source.indexOf("const mobileV3ProgressStages = ");
  const end = source.indexOf("\nfunction clearMobileV3Progress(", start);
  const steps = {};
  const nodes = { "#mobileV3ProgressPanel": {}, "#mobileV3ProgressFill": { style: {} }, "#mobileV3ProgressSteps": steps };
  const context = {
    document: { querySelector: (selector) => nodes[selector] },
    mobileV3State: {},
    progressElapsedLabel: () => "",
    setText() {},
    escapeHtml: (label) => label,
  };
  vm.runInNewContext(source.slice(start, end), context);
  for (const [stage, label] of [["completed", "完成"], ["review_blocked", "未交付"], ["failed", "需重试"]]) {
    context.setMobileV3Progress(stage);
    const outcomes = [...steps.innerHTML.matchAll(/<span class="([^"]*)">(完成|未交付|需重试)<\/span>/g)];
    assert.deepEqual(outcomes.map((item) => item.slice(1)), [["active", label]]);
  }
});
