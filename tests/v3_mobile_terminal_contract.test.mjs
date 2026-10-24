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
  assert.match(completionSource, /: partialDeliveryNotice \|\| "生成完成，已刷新项目图片"/);
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
  let ownershipChecks = 0;
  const previousProject = { project_id: "project_1", marker: "previous" };
  const context = {
    mobileV3State: { currentProject: previousProject },
    window: { setTimeout: (resolve) => resolve() },
    mobileV3GenerationSessionOwns: () => {
      ownershipChecks += 1;
      if (ownershipChecks >= 3) ownsSession = false;
      return ownsSession;
    },
    mobileV3Request: async (url) => (
      url.endsWith("/planning-operations/op_current")
        ? { operation_id: "op_current", state: "planning_failed" }
        : { project: { project_id: "project_1", marker: "stale_refresh" } }
    ),
  };
  vm.runInNewContext(plannedRecoverySource, context);

  const result = await context.recoverMobileV3PlannedJob("project_1", "op_current");

  assert.equal(result.operation, null);
  assert.equal(result.job, null);
  assert.equal(context.mobileV3State.currentProject.marker, "previous");
});
