import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const shells = [
  ["desktop", "../src_skeleton/app/static/app.js"],
  ["mobile", "../src_skeleton/app/mobile_static/mobile.js"],
];

function extractFunction(source, name) {
  const start = new RegExp(`^([ \\t]*)(?:async )?function ${name}\\(`, "m").exec(source);
  assert.ok(start, `source function ${name} is present`);
  const tail = source.slice(start.index);
  const closes = new RegExp(`^${start[1]}\\};?\\s*$`, "gm");
  for (const close of tail.matchAll(closes)) {
    const candidate = tail.slice(0, close.index + close[0].trimEnd().length);
    try {
      new vm.Script(candidate);
      return candidate;
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
    }
  }
  assert.fail(`complete source function ${name} is extractable`);
}

for (const [name, relativePath] of shells) {
  const source = readFileSync(new URL(relativePath, import.meta.url), "utf8");

  test(`${name}: V1 explains an unresolved Bridge state and keeps polling until terminal`, async () => {
    const context = vm.createContext({
      state: {},
      setStatus() {},
      showNotice() {},
      delay: async () => {},
      request: async () => {
        calls += 1;
        return calls < 131
          ? { id: "job-1", status: "generating", error: { code: "bridge_execution_unknown" } }
          : { id: "job-1", status: "ready", outputs: [{ id: "output-1" }] };
      },
    });
    let calls = 0;
    context.calls = calls;
    for (const functionName of [
      "v1ImageJobReady", "v1ImageJobTerminal", "v1ImageJobPollDelay",
      "v1BridgeWaitMessage", "waitForV1ImageJob",
    ]) {
      vm.runInContext(extractFunction(source, functionName), context);
    }
    const bridgeMessage = context.v1BridgeWaitMessage({ error: { code: "bridge_execution_unknown" } });
    assert.equal(bridgeMessage, "Bridge 尚未确认原任务的执行结果，系统正在继续对账。");
    const timeoutMessage = context.v1BridgeWaitMessage({ error: { code: "bridge_codex_turn_timed_out" } });
    assert.match(timeoutMessage, /600 秒/);
    const result = await context.waitForV1ImageJob({ id: "job-1", status: "generating" });
    assert.equal(result.status, "ready");
    assert.equal(calls, 131);
  });

  test(`${name}: V2 preserves the exact Bridge reconciliation action`, () => {
    const context = vm.createContext({});
    vm.runInContext(extractFunction(source, "v2BridgeWaitMessage"), context);
    const run = {
      status: "generating",
      next_actions: ["Render Bridge is reconciling the existing task."],
      generation_jobs: [{
        provider_id: "render_bridge",
        error: { error_code: "bridge_wait", retryable: true, detail: { state: "execution_unknown" } },
      }],
    };
    assert.equal(context.v2BridgeWaitMessage(run), "Render Bridge is reconciling the existing task.");
    run.generation_jobs[0].error.detail.attention_code = "codex_turn_timed_out";
    assert.match(context.v2BridgeWaitMessage(run), /600 秒/);
  });

  test(`${name}: Lab keeps polling after its long-wait threshold until the session is terminal`, async () => {
    const timers = [];
    const delays = [];
    let calls = 0;
    let finished = 0;
    const context = vm.createContext({
      labPollIntervalMs: 3000,
      labPollMaxAttempts: 360,
      labState: { currentSession: { id: "session-1" }, pollAttempt: 0, pollTimer: null },
      window: { setTimeout: (callback, delay) => { delays.push(delay); timers.push({ callback, delay }); return timers.length; } },
      request: async () => {
        calls += 1;
        const terminal = calls === 362;
        return {
          session: { id: "session-1", progress: { message: "Bridge 尚未确认原任务的执行结果，系统正在继续对账。" } },
          board: { status: terminal ? "completed" : "running", groups: [] },
        };
      },
      stopLabPolling() {}, renderLabIntentSummary() {}, renderLabBoard() {}, updateLabSessionFromPayload() {},
      isLabTerminalStatus: (status) => ["completed", "partial_success", "failed"].includes(status),
      finishLabPolling: async () => { finished += 1; },
      updateLabNotice() {}, setLabBusy() {}, friendlyError: (error) => String(error),
      clearTimeout() {},
    });
    vm.runInContext(extractFunction(source, "scheduleLabPolling"), context);
    context.scheduleLabPolling();
    for (let index = 0; index < 362; index += 1) {
      const timer = timers.shift();
      assert.ok(timer, `poll ${index + 1} remains scheduled`);
      await timer.callback();
    }
    assert.equal(calls, 362);
    assert.equal(finished, 1);
    assert.ok(delays.includes(30000), "long waits reduce polling frequency without detaching the task");
  });
}
