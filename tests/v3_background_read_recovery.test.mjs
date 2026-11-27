import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const desktop = readFileSync(new URL("../src_skeleton/app/static/app.js", import.meta.url), "utf8");
const mobile = readFileSync(new URL("../src_skeleton/app/mobile_static/mobile.js", import.meta.url), "utf8");

function install(source, globals, names) {
  const normalized = source.replaceAll("\r\n", "\n");
  const program = names.map((name) => {
    const start = normalized.search(new RegExp("^(?:async )?function " + name + "\\(", "m"));
    assert.notEqual(start, -1, name);
    return normalized.slice(start, normalized.indexOf("\n}\n", start) + 2);
  }).join("\n");
  return vm.runInNewContext(program + "\n({" + names.join(",") + "})", globals);
}

function fakeClock() {
  const timers = new Map();
  let next = 0;
  return {
    window: {
      setTimeout(run, milliseconds) {
        timers.set(++next, { run, milliseconds });
        return next;
      },
      clearTimeout(id) { timers.delete(id); },
    },
    async tick(milliseconds) {
      const due = [...timers].find(([, item]) => item.milliseconds === milliseconds);
      assert.ok(due, "Expected a timer for " + milliseconds);
      timers.delete(due[0]);
      due[1].run();
      await new Promise(setImmediate);
    },
  };
}

const never = () => new Promise(() => {});
const helpers = ["withRequestDeadline", "readWithTimeout", "v3TransientReadError", "retryV3Read"];

test("desktop restores the same project job after repeated timeouts", async () => {
  const clock = fakeClock();
  const task = { job_id: "original", status: "generating" };
  const queries = [];
  const v3State = {};
  const { restoreV3LatestProjectJob } = install(desktop, {
    ...clock, AbortController, DOMException, v3State, v3ApiBase: "/api/v3",
    getVeyraToken: () => "owner", v3GenerationSessionOwns: (owns) => !owns || owns(),
    v3EcommerceReceiptForProject: () => null, v3LatestProjectJobId: () => "original",
    v3ProjectDetailSignal: () => null, v3JobDeliverySettled: () => false,
    request(path, options) {
      queries.push(path);
      assert.equal(options.method, undefined);
      return queries.length < 3 ? never() : task;
    },
  }, [...helpers, "restoreV3LatestProjectJob"]);
  const recovery = restoreV3LatestProjectJob({ project_id: "p" }, { retryStatus: true, throwOnError: true });
  for (let index = 0; index < 2; index += 1) {
    await clock.tick(8000);
    await clock.tick(5000);
  }
  assert.equal(await recovery, task);
  assert.deepEqual(queries, Array(3).fill("/api/v3/jobs/original"));
  assert.equal(v3State.currentJob, task);
});

test("H5 starts the recoverable gallery read even when project detail does not resolve", () => {
  const reads = [];
  const gallery = [];
  const { syncMobileV3ProjectDetailFull } = install(mobile, {
    mobileV3ProjectDetailRequestIsCurrent: () => true,
    loadMobileV3ProjectOutputs: (id) => { gallery.push(id); return never(); },
    mobileV3Request: (path) => { reads.push(path); return never(); },
  }, ["syncMobileV3ProjectDetailFull"]);
  void syncMobileV3ProjectDetailFull("p", { detailEpoch: 1 });
  assert.deepEqual(gallery, ["p"]);
  assert.deepEqual(reads, ["/projects/p", "/projects/p/timeline"]);
});

for (const [label, source, loader] of [
  ["desktop", desktop, "loadV3ProjectOutputs"],
  ["H5", mobile, "loadMobileV3ProjectOutputs"],
]) {
  for (const leave of [false, true]) {
    test(label + (leave ? " ignores a late gallery retry after changing project" : " renders delivery and review after two gallery timeouts"), async () => {
      const clock = fakeClock();
      const queries = [];
      const project = { project_id: "p" };
      const state = { currentProject: project, projectDetailEpoch: 1, previewProjectIds: new Set(), projectGalleryReads: new Map() };
      const rendered = [];
      const stillViewing = () => state.currentProject === project;
      const apply = (items, reviews) => { state.items = items; state.reviews = reviews; };
      let finishRetry;
      const reader = (path, options) => {
        assert.equal(options.method, undefined);
        queries.push(path);
        return queries.length < 3 ? never() : new Promise((resolve) => { finishRetry = resolve; });
      };
      const context = {
        ...clock, AbortController, DOMException, v3ApiBase: "/api/v3", v3State: state, mobileV3State: state,
        v3ProjectDetailRequestIsCurrent: (_id, _epoch, owns) => !owns || owns(),
        v3HistoryModalRequestIsCurrent: () => true, v3ProjectDetailSignal: () => null,
        getVeyraToken: () => "owner", friendlyError: (error) => error.message,
        mobileV3GenerationSessionOwns: (owns) => !owns || owns(),
        syncV3ProjectOutputsFromList: (items, _id, reviews) => apply(items, reviews),
        mobileV3MergeProjectOutputs: (_id, items, reviews) => apply(items, reviews),
        request: reader, mobileV3Request: reader, els: { v3RefreshHistoryBtn: {} },
        renderV3ResultBoard: () => rendered.push(state.reviews),
        renderMobileV3ProjectOutputs: () => rendered.push(state.reviews),
      };
      for (const name of ["renderV3History", "renderV3HeroHistory", "renderV3ProjectOutputBoard", "renderV3ProjectSnapshot",
        "renderV3StepCards", "renderV3ProjectNextActions", "renderMobileV3ProjectCards", "renderMobileV3ProjectGallery",
        "persistMobileV3Caches"]) context[name] = () => {};
      const read = install(source, context, [...helpers, loader])[loader];
      const foreground = label === "H5"
        ? read("p", { shouldContinue: stillViewing, preserveOnError: true })
        : read({ projectId: "p", silent: true, shouldContinue: stillViewing, preserveOnError: true });
      await clock.tick(8000);
      await clock.tick(8000);
      assert.equal((await foreground).length, 0);
      assert.ok(!state.imageHistoryLoading);
      await clock.tick(5000);
      if (leave) {
        state.currentProject = { project_id: "other" };
        state.projectDetailEpoch += 1;
      }
      finishRetry({ items: [{ output_id: "delivered" }], review_items: [{ output_id: "review", reason: "off-axis light" }] });
      await new Promise(setImmediate);
      assert.equal(queries.length, 3);
      assert.ok(queries.every((path) => path === queries[0]));
      assert.equal(state.items?.[0]?.output_id, leave ? undefined : "delivered");
      assert.equal(rendered.at(-1)?.[0]?.reason, leave ? undefined : "off-axis light");
    });
  }
}
