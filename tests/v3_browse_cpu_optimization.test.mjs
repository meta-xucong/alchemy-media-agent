import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(
  new URL("../src_skeleton/app/static/app.js", import.meta.url),
  "utf8",
);

function extractFunction(name, nextMarker) {
  const start = source.indexOf(`function ${name}(`);
  const asyncStart = source.indexOf(`async function ${name}(`);
  const functionStart = asyncStart >= 0 ? asyncStart : start;
  const end = source.indexOf(nextMarker, functionStart);
  assert.ok(functionStart >= 0 && end > functionStart, `${name} function must be present`);
  return source.slice(functionStart, end);
}

test("job output projection signature ignores progress-only changes", () => {
  const context = {};
  vm.runInNewContext(
    extractFunction("v3JobOutputProjectionSignature", "\nfunction withV3SoftTimeout"),
    context,
  );
  const before = context.v3JobOutputProjectionSignature({
    status: "generating",
    progress: 20,
    metadata: {},
    candidates: [],
    asset_series: [],
  });
  const after = context.v3JobOutputProjectionSignature({
    status: "generating",
    progress: 80,
    metadata: {},
    candidates: [],
    asset_series: [],
  });
  const withOutput = context.v3JobOutputProjectionSignature({
    status: "generating",
    metadata: {},
    candidates: [{ output_id: "out_1" }],
  });
  assert.equal(before, "");
  assert.equal(after, "");
  assert.notEqual(withOutput, "");
});

test("recovery does not refresh project projections on unchanged poll ticks", async () => {
  const recoverySource = extractFunction("recoverV3GeneratedJob", "\nfunction v3JobAwaitingFinalDelivery");
  let jobReads = 0;
  let projectRefreshes = 0;
  let timelineReads = 0;
  let outputReads = 0;
  const running = {
    status: "generating",
    metadata: {},
    candidates: [],
    asset_series: [],
  };
  const terminal = { ...running, status: "generated" };
  const context = {
    v3RecoveryMaxAttempts: 4,
    v3State: {},
    v3ApiBase: "/api/v3",
    v3Delay: async () => {},
    request: async () => {
      jobReads += 1;
      return jobReads <= 2 ? running : terminal;
    },
    v3JobOutputProjectionSignature: (job) => {
      const outputs = (job.candidates || []).map((item) => item.output_id).filter(Boolean);
      return outputs.length ? JSON.stringify(outputs) : "";
    },
    v3JobHasTerminalOutcome: (job) => job.status === "generated",
    v3JobHasExpectedVisibleImages: () => false,
    v3JobHasRecoverablePartialDelivery: () => false,
    v3GenerationSessionOwns: () => true,
    v3SettleEcommerceTerminalReceipt: () => {},
    renderV3Job: () => {},
    refreshV3CurrentProject: async () => { projectRefreshes += 1; },
    loadV3ProjectTimeline: async () => { timelineReads += 1; },
    loadV3ProjectOutputs: async () => { outputReads += 1; },
    setV3Progress: () => {},
    v3JobProviderRetryActive: () => false,
    v3JobAwaitingFinalDelivery: () => false,
    v3RecoveryAttemptLimitForServerWatchdog: () => 0,
    v3RecoveredJobFromProjectOutputs: () => null,
    v3ProviderFailureUserMessage: () => "failed",
    clearV3RecoverPolling: () => {},
    renderV3ProjectDetail: () => {},
  };
  vm.runInNewContext(recoverySource, context);
  const result = await context.recoverV3GeneratedJob(
    "project_1",
    "job_1",
    new Error("pending"),
    { expectedCount: 1 },
  );
  assert.equal(result.status, "generated");
  assert.equal(jobReads, 3);
  assert.equal(projectRefreshes, 0);
  assert.equal(timelineReads, 0);
  assert.equal(outputReads, 0);
});

test("V3 protected media queue deduplicates URLs and caps active fetches at two", async () => {
  const start = source.indexOf("const v3ProtectedMediaQueue = [];");
  const end = source.indexOf("async function resolveAuthenticatedMediaSource", start);
  assert.ok(start >= 0 && end > start, "V3 protected media scheduler must be present");
  const schedulerSource = source.slice(start, end);
  let active = 0;
  let peak = 0;
  const fetches = new Map();
  const context = {
    AbortController,
    Map,
    Promise,
    Error,
    getVeyraToken: () => "test-token",
    fetch: async (url) => {
      fetches.set(url, Number(fetches.get(url) || 0) + 1);
      active += 1;
      peak = Math.max(peak, active);
      await new Promise((resolve) => setTimeout(resolve, 10));
      active -= 1;
      return { ok: true, blob: async () => ({ size: 1, type: "image/png" }) };
    },
  };
  vm.runInNewContext(schedulerSource, context);
  const blobs = await Promise.all([
    context.fetchV3ProtectedMediaBlob("/api/v3/media/a", null),
    context.fetchV3ProtectedMediaBlob("/api/v3/media/a", null),
    context.fetchV3ProtectedMediaBlob("/api/v3/media/b", null),
    context.fetchV3ProtectedMediaBlob("/api/v3/media/c", null),
  ]);
  assert.equal(blobs.length, 4);
  assert.equal(fetches.get("/api/v3/media/a"), 1);
  assert.equal(peak, 2);
});

test("cancelled protected media is removed before an immediate same-URL retry", async () => {
  const start = source.indexOf("const v3ProtectedMediaQueue = [];");
  const end = source.indexOf("async function resolveAuthenticatedMediaSource", start);
  const schedulerSource = source.slice(start, end);
  const requests = [];
  const context = {
    AbortController,
    Map,
    Promise,
    Error,
    getVeyraToken: () => "test-token",
    fetch: (url, options) => new Promise((resolve, reject) => {
      requests.push({ url, options, resolve, reject });
    }),
  };
  vm.runInNewContext(schedulerSource, context);
  const firstWaiter = new AbortController();
  const first = context.fetchV3ProtectedMediaBlob("/api/v3/media/retry", firstWaiter.signal)
    .catch((error) => error);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests.length, 1);

  firstWaiter.abort();
  assert.equal((await first).name, "AbortError");

  const retry = context.fetchV3ProtectedMediaBlob("/api/v3/media/retry", null);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests.length, 2);
  requests[0].reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
  requests[1].resolve({ ok: true, blob: async () => ({ size: 1, type: "image/png" }) });
  assert.deepEqual(await retry, { size: 1, type: "image/png" });
});

test("protected media in-flight deduplication is isolated by authentication token", async () => {
  const start = source.indexOf("const v3ProtectedMediaQueue = [];");
  const end = source.indexOf("async function resolveAuthenticatedMediaSource", start);
  const schedulerSource = source.slice(start, end);
  const requests = [];
  let token = "account-a-token";
  const context = {
    AbortController,
    Map,
    Promise,
    Error,
    getVeyraToken: () => token,
    fetch: (url, options) => new Promise((resolve, reject) => {
      requests.push({ url, options, resolve, reject });
    }),
  };
  vm.runInNewContext(schedulerSource, context);
  const accountA = context.fetchV3ProtectedMediaBlob("/api/v3/media/shared", null);
  await new Promise((resolve) => setImmediate(resolve));
  token = "account-b-token";
  const accountB = context.fetchV3ProtectedMediaBlob("/api/v3/media/shared", null);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests.length, 2);
  assert.equal(requests[0].options.headers.Authorization, "Bearer account-a-token");
  assert.equal(requests[1].options.headers.Authorization, "Bearer account-b-token");
  for (const request of requests) {
    request.resolve({ ok: true, blob: async () => ({ size: 1, type: "image/png" }) });
  }
  assert.deepEqual(await accountA, { size: 1, type: "image/png" });
  assert.deepEqual(await accountB, { size: 1, type: "image/png" });
});

test("V3 authenticated image fetch waits for intersection and cancels offscreen work", async () => {
  const start = source.indexOf("const v3DeferredImageLoads = new Map();");
  const end = source.indexOf("function bindProgressiveLightboxImage", start);
  assert.ok(start >= 0 && end > start, "V3 deferred image binder must be present");
  const imageSource = source.slice(start, end);
  const observers = [];
  class MockIntersectionObserver {
    constructor(callback) {
      this.callback = callback;
      this.observed = new Set();
      observers.push(this);
    }
    observe(image) { this.observed.add(image); }
    unobserve(image) { this.observed.delete(image); }
    intersect(image) {
      this.callback([{ target: image, isIntersecting: true, intersectionRatio: 1 }]);
    }
  }
  let fetchCount = 0;
  const context = {
    Map,
    WeakMap,
    AbortController,
    IntersectionObserver: MockIntersectionObserver,
    Date,
    Math,
    URL,
    uniqueNonEmpty: (values) => [...new Set(values.filter(Boolean))],
    mediaUrlNeedsAuthenticatedFetch: () => true,
    releaseImageObjectUrl: () => {},
    resolveAuthenticatedMediaSource: async (url) => {
      fetchCount += 1;
      return { url: `blob:${url}`, objectUrl: false };
    },
    v3State: { projectDetailProjectId: "project_1", projectDetailEpoch: 1 },
    v3ProjectDetailSignal: () => undefined,
  };
  vm.runInNewContext(imageSource, context);
  const makeImage = () => ({
    dataset: {},
    loading: "lazy",
    isConnected: true,
    classList: { add() {}, remove() {} },
    removeAttribute() { this.src = ""; },
  });

  const offscreen = makeImage();
  context.bindImageWithFallback(offscreen, ["/api/v3/media/offscreen"], {
    deferAuthenticated: true,
    v3Queued: true,
  });
  assert.equal(fetchCount, 0);
  observers[0].intersect(offscreen);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(fetchCount, 1);

  const controller = new AbortController();
  const cancelled = makeImage();
  context.bindImageWithFallback(cancelled, ["/api/v3/media/cancelled"], {
    deferAuthenticated: true,
    v3Queued: true,
    signal: controller.signal,
  });
  controller.abort();
  observers[0].intersect(cancelled);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(fetchCount, 1);
});

test("V3 deferred image teardown releases disconnected image references and subscriptions", () => {
  const start = source.indexOf("const v3DeferredImageLoads = new Map();");
  const end = source.indexOf("function bindProgressiveLightboxImage", start);
  const imageSource = `${source.slice(start, end)}\nthis.deferredCount = () => v3DeferredImageLoads.size;`;
  const observers = [];
  class MockIntersectionObserver {
    constructor(callback) { this.callback = callback; this.observed = new Set(); observers.push(this); }
    observe(image) { this.observed.add(image); }
    unobserve(image) { this.observed.delete(image); }
  }
  const context = {
    Map,
    WeakMap,
    AbortController,
    IntersectionObserver: MockIntersectionObserver,
    Date,
    Math,
    URL,
    uniqueNonEmpty: (values) => [...new Set(values.filter(Boolean))],
    mediaUrlNeedsAuthenticatedFetch: () => true,
    releaseImageObjectUrl: () => {},
    resolveAuthenticatedMediaSource: async () => ({ url: "blob:test", objectUrl: false }),
    v3State: { projectDetailProjectId: "project_1", projectDetailEpoch: 1 },
    v3ProjectDetailSignal: () => undefined,
  };
  vm.runInNewContext(imageSource, context);
  const container = {
    images: [],
    querySelectorAll(selector) { assert.equal(selector, "img"); return this.images; },
    matches() { return false; },
  };
  const makeImage = () => ({
    dataset: {},
    loading: "lazy",
    isConnected: true,
    classList: { add() {}, remove() {} },
    removeAttribute() { this.src = ""; },
  });
  for (let render = 0; render < 100; render += 1) {
    container.images = Array.from({ length: 24 }, () => makeImage());
    for (const image of container.images) {
      context.bindV3ImageWithFallback(image, ["/api/v3/media/deferred"], { detailBound: true });
    }
    assert.equal(context.deferredCount(), 24);
    context.releaseV3ImageBindingsWithin(container);
    container.images = [];
    assert.equal(context.deferredCount(), 0);
  }
  assert.equal(observers[0].observed.size, 0);
});

test("output projection retry commits a signature only after successful refresh", async () => {
  const recoverySource = extractFunction("recoverV3GeneratedJob", "\nfunction v3JobAwaitingFinalDelivery");
  let now = 0;
  let jobReads = 0;
  let outputReads = 0;
  const running = {
    status: "generating",
    metadata: {},
    candidates: [{ output_id: "out_1" }],
    asset_series: [],
  };
  const terminal = { ...running, status: "generated" };
  const context = {
    v3RecoveryMaxAttempts: 4,
    v3State: {},
    v3ApiBase: "/api/v3",
    Date: { now: () => now },
    v3Delay: async () => { now += 3000; },
    request: async () => {
      jobReads += 1;
      return jobReads <= 3 ? running : terminal;
    },
    v3JobOutputProjectionSignature: (job) => JSON.stringify((job.candidates || []).map((item) => item.output_id)),
    v3JobHasTerminalOutcome: (job) => job.status === "generated",
    v3JobHasExpectedVisibleImages: () => false,
    v3JobHasRecoverablePartialDelivery: () => false,
    v3GenerationSessionOwns: () => true,
    v3SettleEcommerceTerminalReceipt: () => {},
    renderV3Job: () => {},
    refreshV3CurrentProject: async () => { throw new Error("recovery must not refresh terminal projections"); },
    loadV3ProjectTimeline: async () => {},
    loadV3ProjectOutputs: async (options) => {
      assert.equal(options.throwOnError, true);
      assert.equal(options.preserveOnError, true);
      outputReads += 1;
      if (outputReads === 1) throw new Error("temporary output request failure");
      return [];
    },
    setV3Progress: () => {},
    v3JobProviderRetryActive: () => false,
    v3JobAwaitingFinalDelivery: () => false,
    v3RecoveryAttemptLimitForServerWatchdog: () => 0,
    v3RecoveredJobFromProjectOutputs: () => null,
    v3ProviderFailureUserMessage: () => "failed",
    clearV3RecoverPolling: () => {},
    renderV3ProjectDetail: () => {},
  };
  vm.runInNewContext(recoverySource, context);
  const result = await context.recoverV3GeneratedJob("project_1", "job_1", new Error("pending"));
  assert.equal(result.status, "generated");
  assert.equal(outputReads, 2);
});

test("generation completion uses one project projection refresh", () => {
  const completion = extractFunction("completeV3GeneratedJob", "\nasync function runV3GenerationWithRecovery");
  const recovery = extractFunction("recoverV3GeneratedJob", "\nfunction v3JobAwaitingFinalDelivery");
  assert.equal((completion.match(/refreshV3CurrentProject\(/g) || []).length, 1);
  assert.equal((completion.match(/loadV3ProjectOutputs\(/g) || []).length, 0);
  assert.match(completion, /restoreJob:\s*false/);
  assert.match(completion, /preserveOutputOnError:\s*true/);
  assert.match(completion, /preserveOutputOnError:\s*true/);
  assert.doesNotMatch(recovery, /refreshV3CurrentProject\(/);
});
