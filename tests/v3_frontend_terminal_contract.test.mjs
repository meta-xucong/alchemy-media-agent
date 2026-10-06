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

async function completeWith(job, expectedCount = null) {
  const progress = [];
  const notices = [];
  const context = {
    v3State: { selectedScenario: "general_creative" },
    els: { v3ProjectSubpage: { hidden: true } },
    v3ScenarioWorkspaceCopy: () => ({ generatedNotice: "生成成功" }),
    v3SettleEcommerceTerminalReceipt: () => {},
    syncV3ProjectOutputsFromPayload: () => {},
    v3JobHasRecoverablePartialDelivery: (value) => value.partialRecovery === true,
    v3JobDeliveryWithheld: (value) => value.deliveryWithheld === true,
    v3JobHasExpectedVisibleImages: (value, count) => (
      count == null
        ? value.hasExpectedDelivery === true
        : Number(value.visibleCount || 0) >= Number(count)
    ),
    v3JobFinalDeliveryNotice: () => "审查拦截",
    setV3Progress: (...args) => progress.push(args),
    renderV3Job: () => {},
    refreshV3CurrentProject: async () => {},
    loadV3ProjectOutputs: async () => {},
    syncV3CurrentJobFromProjectOutputs: () => false,
    maybePersistV3UploadedReferences: async () => {},
    openV3ProjectSubpage: () => {},
    v3EcommerceFailureMessage: () => "",
    updateV3Notice: (...args) => notices.push(args),
  };
  vm.runInNewContext(completionSource, context);
  await context.completeV3GeneratedJob(
    job,
    [],
    { generatedNotice: "生成成功" },
    { expectedCount },
  );
  return { progress, notices };
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
});

test("partial recovery and review-held delivery stay distinct from full success", async () => {
  const partial = await completeWith({
    status: "failed",
    hasExpectedDelivery: false,
    partialRecovery: true,
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
