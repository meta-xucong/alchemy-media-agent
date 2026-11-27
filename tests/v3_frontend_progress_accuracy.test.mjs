import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const desktop = readFileSync(new URL("../src_skeleton/app/static/app.js", import.meta.url), "utf8");
const mobile = readFileSync(new URL("../src_skeleton/app/mobile_static/mobile.js", import.meta.url), "utf8");

function functionSlice(source, name, nextName) {
  const start = source.indexOf(`function ${name}(`);
  const end = source.indexOf(`\nfunction ${nextName}(`, start);
  assert.ok(start >= 0 && end > start, `${name} must be present before ${nextName}`);
  return source.slice(start, end);
}

function progressHelpers(source, { delayName, progressName, nextName, awaitingName, billingName, billingNextName, retryName = null }) {
  const delay = functionSlice(source, delayName, progressName);
  const progress = functionSlice(source, progressName, nextName);
  const billing = functionSlice(source, billingName, billingNextName);
  const context = {
    [awaitingName]: (job) => job?.status === "finalizing" || Boolean(job?.metadata?.delivery_settling),
  };
  if (retryName) context[retryName] = () => false;
  vm.runInNewContext(
    `${delay}\n${progress}\n${billing}\nthis.resolveDelay = ${delayName};\nthis.resolveProgress = ${progressName};\nthis.resolveBilling = ${billingName};`,
    context,
  );
  return context;
}

for (const [surface, source, names] of [
  ["desktop", desktop, {
    delayName: "v3RecoveryDelayMs",
    progressName: "v3RecoveryProgressPresentation",
    nextName: "v3RecoveryAttemptLimitForServerWatchdog",
    awaitingName: "v3JobAwaitingFinalDelivery",
    billingName: "v3ImageBillingNotice",
    billingNextName: "v3RecoveryDelayMs",
    retryName: "v3JobProviderRetryActive",
  }],
  ["mobile", mobile, {
    delayName: "mobileV3RecoveryDelayMs",
    progressName: "mobileV3RecoveryProgressPresentation",
    nextName: "mobileV3RecoveryAttemptLimitForServerWatchdog",
    awaitingName: "mobileV3JobAwaitingFinalDelivery",
    billingName: "mobileV3ImageBillingNotice",
    billingNextName: "mobileV3JobHasTerminalOutcome",
  }],
]) {
  test(`${surface} V3 polling backs off while preserving the base observation window`, () => {
    const helpers = progressHelpers(source, names);
    assert.equal(helpers.resolveDelay(1), 1200);
    assert.equal(helpers.resolveDelay(2), 2500);
    assert.equal(helpers.resolveDelay(25), 2500);
    assert.equal(helpers.resolveDelay(26), 5000);
    assert.equal(helpers.resolveDelay(61), 5000);
    assert.equal(helpers.resolveDelay(62), 10000);
    const elapsedForAttempts = (count) => {
      let elapsed = 0;
      for (let attempt = 1; attempt <= count; attempt += 1) elapsed += helpers.resolveDelay(attempt);
      return elapsed;
    };
    if (surface === "desktop") {
      assert.equal(elapsedForAttempts(96), 591200);
      assert.match(source, /const v3RecoveryMaxAttempts = 96;/);
    } else {
      assert.equal(elapsedForAttempts(66), 291200);
      assert.match(source, /let recoveryAttemptLimit = 66;/);
    }
  });

  test(`${surface} V3 progress copy follows the actual status and counts status queries`, () => {
    const helpers = progressHelpers(source, names);
    const queued = helpers.resolveProgress({ status: "queued" }, 8);
    const generating = helpers.resolveProgress({ status: "generating" }, 18);
    const finalizing = helpers.resolveProgress({ status: "finalizing" }, 352);
    const unavailable = helpers.resolveProgress({ status: "generating" }, 19, { statusReadFailed: true });

    assert.match(queued.detail, /后台队列/);
    assert.match(queued.detail, /后台状态查询已尝试 8 次/);
    assert.equal(queued.stageKey, "recovering");
    assert.doesNotMatch(generating.detail, /排队/);
    assert.match(generating.detail, /正在生成/);
    assert.equal(generating.stageKey, "recovering");
    assert.match(finalizing.detail, /质量复检和最终交付/);
    assert.match(finalizing.detail, /后台状态查询已尝试 352 次/);
    assert.equal(finalizing.stageKey, surface === "desktop" ? "reviewing" : "recovering");
    assert.doesNotMatch(finalizing.detail, /刷新 352 次|生成或排队/);
    assert.match(unavailable.detail, /暂时无法读取最新任务状态/);
    assert.doesNotMatch(unavailable.detail, /排队/);
  });

  test(`${surface} V3 distinguishes wallet reconciliation from quality review and reports the amount`, () => {
    const helpers = progressHelpers(source, names);
    const job = (status, imageBilling) => ({ status, metadata: { image_billing: imageBilling } });
    const pending = helpers.resolveProgress(job("finalizing", { status: "pending", code: "wallet_unavailable" }), 8);
    const topUp = helpers.resolveProgress(job("finalizing", { status: "pending", code: "insufficient_balance" }), 9);
    const blocked = helpers.resolveProgress(job("blocked", { status: "blocked", code: "insufficient_balance" }), 1);
    const reviewing = helpers.resolveProgress(job("finalizing", { status: "checking", unit_price: "0.07" }), 8);

    assert.equal(pending.stageKey, "billing");
    assert.match(pending.detail, /确认本次扣费.*原任务/);
    assert.doesNotMatch(pending.detail, /质量复检|正在生成/);
    assert.equal(topUp.stageKey, "billing");
    assert.match(topUp.detail, /补足积分.*原任务/);
    assert.equal(blocked.stageKey, "failed");
    assert.match(blocked.detail, /未开始生成，也未扣费/);
    assert.match(reviewing.detail, /质量复检/);
    assert.match(helpers.resolveBilling(job("generated", { status: "charged", amount: "0.14" })), /已扣 0\.14 积分/);
    assert.equal(helpers.resolveBilling(job("failed", { status: "no_charge" })), "");
  });

  test(`${surface} watchdog allowance follows the real backoff schedule`, () => {
    const delay = functionSlice(source, names.delayName, names.progressName);
    const watchdogEnd = surface === "desktop" ? "v3JobProviderRetrySummary" : "setMobileV3Busy";
    const watchdog = functionSlice(source, `${surface === "desktop" ? "v3" : "mobileV3"}RecoveryAttemptLimitForServerWatchdog`, watchdogEnd);
    class FixedDate extends Date {
      static now() { return 1000; }
    }
    const helperName = `${surface === "desktop" ? "v3" : "mobileV3"}RecoveryAttemptLimitForServerWatchdog`;
    const context = { Date: FixedDate };
    vm.runInNewContext(`${delay}\n${watchdog}\nthis.resolveLimit = ${helperName};`, context);
    const job = {
      metadata: {
        background_generation_watchdog: {
          timeout_seconds: 5,
          started_at: new Date(1000).toISOString(),
        },
      },
    };
    assert.equal(context.resolveLimit(job, 61), 66);
  });
}

test("V3 elapsed time is labeled as cumulative and review stage is named clearly", () => {
  assert.match(desktop, /`累计用时 \$\{elapsed\}`/);
  assert.match(desktop, /key: "reviewing", percent: 92, label: "复检与交付"/);
  assert.match(mobile, /累计用时 \$\{elapsed\}/);
  assert.match(mobile, /key: "recovering", percent: 86, label: "核对结果"/);
  assert.match(desktop, /v3State\.progressStageKey === "reviewing" && waitProgress\.stageKey === "recovering"/);
});

test("desktop and mobile keep polling the original pending billing job past the observation limit", async () => {
  const jobId = "job_wallet";
  const pending = { job_id: jobId, status: "finalizing", metadata: { image_billing: { status: "pending" } } };
  const charged = { job_id: jobId, status: "generated", metadata: { image_billing: { status: "charged" } } };
  const terminal = (job) => job.status === "generated";
  const noop = () => {};
  for (const [source, recoveryName, nextName, defaultLimit] of [
    [desktop, "recoverV3GeneratedJob", "v3JobAwaitingFinalDelivery", 2],
    [mobile, "recoverMobileV3GeneratedJob", "mobileV3RecoveryDelayMs", 66],
  ]) {
    const calls = [];
    const getJob = async (path, options) => {
      calls.push({ path, options });
      return calls.length > defaultLimit + 1 ? charged : pending;
    };
    const context = {
      clearV3RecoverPolling: noop,
      v3State: { currentJob: pending },
      v3RecoveryMaxAttempts: defaultLimit,
      v3Delay: async () => {},
      v3RecoveryDelayMs: () => 0,
      v3ApiBase: "/v3",
      readWithTimeout: (read, path, { signal } = {}) => read(path, { signal }),
      request: getJob,
      v3JobOutputProjectionSignature: () => "",
      v3JobHasTerminalOutcome: terminal,
      v3JobHasExpectedVisibleImages: () => false,
      v3JobHasRecoverablePartialDelivery: () => false,
      v3RecoveredJobFromProjectOutputs: () => null,
      v3RecoveryAttemptLimitForServerWatchdog: () => 0,
      v3RecoveryProgressPresentation: () => ({ stageKey: "billing" }),
      v3SettleEcommerceTerminalReceipt: noop,
      renderV3Job: noop,
      setV3Progress: noop,
      renderV3ProjectDetail: noop,
      mobileV3GenerationSessionOwns: () => true,
      window: { setTimeout: (resolve) => resolve() },
      mobileV3RecoveryDelayMs: () => 0,
      readWithTimeout: (read, path, { signal } = {}) => read(path, { signal }),
      mobileV3Request: getJob,
      mobileV3JobHasTerminalOutcome: terminal,
      loadMobileV3ProjectOutputs: async () => {},
      mobileV3SettleEcommerceTerminalReceipt: noop,
      mobileV3RecoveryAttemptLimitForServerWatchdog: () => 0,
      mobileV3RecoveryProgressPresentation: () => ({ stageKey: "billing" }),
      setMobileV3Progress: noop,
    };
    vm.runInNewContext(`async ${functionSlice(source, recoveryName, nextName)}\nthis.recover = ${recoveryName};`, context);
    const result = source === desktop
      ? await context.recover("project", jobId, null)
      : await context.recover("project", jobId, { initialJob: pending });
    assert.equal(result, charged);
    assert.equal(calls.length, defaultLimit + 2);
    assert.ok(calls.every(({ path, options }) => path.endsWith(`/jobs/${jobId}`) && (!options?.method || options.method === "GET")));
  }
});
