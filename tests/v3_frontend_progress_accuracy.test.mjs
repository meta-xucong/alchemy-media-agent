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

function progressHelpers(source, { delayName, progressName, nextName, awaitingName, retryName = null }) {
  const delay = functionSlice(source, delayName, progressName);
  const progress = functionSlice(source, progressName, nextName);
  const context = {
    [awaitingName]: (job) => job?.status === "finalizing" || Boolean(job?.metadata?.delivery_settling),
  };
  if (retryName) context[retryName] = () => false;
  vm.runInNewContext(
    `${delay}\n${progress}\nthis.resolveDelay = ${delayName};\nthis.resolveProgress = ${progressName};`,
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
    retryName: "v3JobProviderRetryActive",
  }],
  ["mobile", mobile, {
    delayName: "mobileV3RecoveryDelayMs",
    progressName: "mobileV3RecoveryProgressPresentation",
    nextName: "mobileV3RecoveryAttemptLimitForServerWatchdog",
    awaitingName: "mobileV3JobAwaitingFinalDelivery",
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
