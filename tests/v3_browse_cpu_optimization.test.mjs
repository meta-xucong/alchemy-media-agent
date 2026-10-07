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

test("unchanged successful output projection is read once across running polls", async () => {
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
  const context = {
    v3RecoveryMaxAttempts: 8,
    v3State: {},
    v3ApiBase: "/api/v3",
    Date: { now: () => now },
    v3Delay: async () => { now += 3000; },
    request: async () => {
      jobReads += 1;
      return jobReads <= 7 ? running : { ...running, status: "failed" };
    },
    v3JobOutputProjectionSignature: (job) => JSON.stringify((job.candidates || []).map((item) => item.output_id)),
    v3JobHasTerminalOutcome: (job) => job.status === "failed",
    v3JobHasExpectedVisibleImages: () => false,
    v3JobHasRecoverablePartialDelivery: () => false,
    v3GenerationSessionOwns: () => true,
    v3SettleEcommerceTerminalReceipt: () => {},
    renderV3Job: () => {},
    loadV3ProjectOutputs: async () => { outputReads += 1; return []; },
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
  await context.recoverV3GeneratedJob("project_1", "job_1", new Error("pending"));
  assert.equal(jobReads, 8);
  assert.equal(outputReads, 1, "a changed projection is read once while the job remains active");
});

test("output projection retries once after failure then suppresses unchanged successful reads", async () => {
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
  const context = {
    v3RecoveryMaxAttempts: 8,
    v3State: {},
    v3ApiBase: "/api/v3",
    Date: { now: () => now },
    v3Delay: async () => { now += 3000; },
    request: async () => {
      jobReads += 1;
      return jobReads <= 7 ? running : { ...running, status: "failed" };
    },
    v3JobOutputProjectionSignature: (job) => JSON.stringify((job.candidates || []).map((item) => item.output_id)),
    v3JobHasTerminalOutcome: (job) => job.status === "failed",
    v3JobHasExpectedVisibleImages: () => false,
    v3JobHasRecoverablePartialDelivery: () => false,
    v3GenerationSessionOwns: () => true,
    v3SettleEcommerceTerminalReceipt: () => {},
    renderV3Job: () => {},
    loadV3ProjectOutputs: async () => {
      outputReads += 1;
      if (outputReads === 1) throw new Error("temporary output read failure");
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
  await context.recoverV3GeneratedJob("project_1", "job_1", new Error("pending"));
  assert.equal(jobReads, 8);
  assert.equal(outputReads, 2, "failed read followed by one successful retry");
});

test("returning home releases an opening project and permits a later project after stale success or abort", async () => {
  const invalidate = extractFunction("invalidateV3ProjectDetail", "\nfunction v3ProjectDetailIsCurrent");
  const isCurrent = extractFunction("v3ProjectDetailIsCurrent", "\nfunction v3ProjectDetailRequestIsCurrent");
  const requestIsCurrent = extractFunction("v3ProjectDetailRequestIsCurrent", "\nfunction v3ProjectDetailSignal");
  const home = extractFunction("openV3Home", "\nfunction openV3ProfessionalWorkspace");
  const openProject = extractFunction("openV3Project", "\nasync function syncV3ProjectDetailInBackground");

  for (const oldOutcome of ["late_success", "abort_error"]) {
    const pendingA = [];
    const overlay = { hidden: true };
    const context = {
      AbortController,
      Promise,
      encodeURIComponent,
      v3ApiBase: "/api/v3",
      v3State: {
        projectDetailEpoch: 7,
        projectDetailProjectId: "",
        projectDetailAbortController: null,
        currentProject: null,
        currentJob: null,
        projectsLoaded: true,
        projectsLoading: false,
        loading: false,
        templates: [],
      },
      els: { v3WorkspaceView: { dataset: {} }, v3PromptInput: { value: "" } },
      window: { setTimeout: () => {}, scrollTo: () => {} },
      closeV3ProjectSubpage: () => {},
      renderV3ViewState: () => {},
      renderV3ScenarioState: () => {},
      renderV3HomeTemplateChooser: () => {},
      renderV3Projects: () => {},
      renderV3History: () => {},
      renderV3ProjectDetail: () => {},
      renderV3ProjectOpeningState: () => {},
      renderV3Job: () => {},
      clearV3PendingUploads: () => {},
      setV3PageLoading: (visible) => { overlay.hidden = !visible; },
      setV3Busy: (busy) => { context.v3State.loading = Boolean(busy); },
      releaseV3ScrollLockIfNoModal: () => {},
      updateV3Notice: () => {},
      v3GenerationSessionOwns: () => true,
      v3ProjectWithResponsePreferences: (project) => project,
      applyV3GenerationPreferences: () => {},
      setV3WorkspaceMode: () => {},
      v3ProjectUsesProfessionalWorkspace: () => false,
      closeV3VisualAssetBindingDialog: () => {},
      closeV3VisualAssetLibraryDialog: () => {},
      syncV3ProjectOutputsFromPayload: () => {},
      syncV3ProjectOutputsFromList: () => {},
      v3ProjectTemplateId: (project) => project.primary_template_id,
      saveV3ProjectSnapshot: () => {},
      openV3ScenarioWorkspace: () => {},
      v3ScenarioForTemplate: () => "general_creative",
      waitForV3FirstProjectPreviewImage: async () => true,
      syncV3ProjectDetailInBackground: () => {},
      v3RequestWithTimeout: (path, _timeoutMs, signal) => {
        if (path.includes("project_id=A") || path.includes("projects/A?")) {
          return new Promise((resolve, reject) => pendingA.push({ resolve, reject, signal }));
        }
        if (path.includes("projects/B?")) {
          return Promise.resolve({ project: { project_id: "B", primary_template_id: "general_template" } });
        }
        return Promise.resolve({ items: [] });
      },
    };
    vm.runInNewContext(`${invalidate}\n${isCurrent}\n${requestIsCurrent}\n${home}\n${openProject}`, context);

    const openingA = context.openV3Project("A");
    assert.equal(pendingA.length, 2);
    assert.equal(context.v3State.projectOpening, true);
    assert.equal(context.v3State.loading, true);
    assert.equal(overlay.hidden, false);
    const controllerA = context.v3State.projectDetailAbortController;

    context.openV3Home();
    assert.equal(controllerA.signal.aborted, true);
    assert.equal(context.v3State.projectDetailEpoch, 9);
    assert.equal(context.v3State.projectDetailProjectId, "");
    assert.equal(context.v3State.currentProject, null);

    for (const request of pendingA) {
      if (oldOutcome === "late_success") {
        request.resolve({ project: { project_id: "A", primary_template_id: "general_template" } });
      } else {
        request.reject(Object.assign(new Error("cancelled"), { name: "AbortError" }));
      }
    }
    await openingA;

    assert.equal(context.v3State.view, "home");
    assert.equal(context.v3State.projectOpening, false);
    assert.equal(context.v3State.loading, false);
    assert.equal(overlay.hidden, true);
    assert.equal(Object.hasOwn(context.els.v3WorkspaceView.dataset, "v3Opening"), false);

    await context.openV3Project("B");
    assert.equal(context.v3State.currentProject.project_id, "B");
    assert.equal(context.v3State.view, "workspace");
    assert.equal(context.v3State.projectOpening, false);
    assert.equal(overlay.hidden, true);
  }
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
