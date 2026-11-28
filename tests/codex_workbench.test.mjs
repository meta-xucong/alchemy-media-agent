import assert from "node:assert/strict";
import test from "node:test";
import { caseThumbnail, createPayload, initialDraft, projectRun, runPath, updateDraft } from "../src_skeleton/app/static/codex-workbench-state.mjs";

const styles = new Map([["M001", {}], ["M002", {}]]);
const limits = { maxSelectedStyles: 8, maxImagesPerStyle: 4, maxTotalImages: 3 };

test("V2 inputs preserve selected case, count, and ratio", () => {
  const draft = updateDraft(initialDraft(), { prompt: "商品海报", case_id: "case_selected", ratio: "4:5", count: 2 }, styles, limits);
  assert.deepEqual(createPayload(draft), { user_prompt: "商品海报", template_case_id: "case_selected",
    mode_hint: "template_customize", output: { aspect_ratio: "4:5", count: 2 } });
  assert.throws(() => updateDraft(draft, { ratio: "7:3" }, styles, limits));
});

test("LAB sends the selected IDs and coherent per-style and total counts", () => {
  const draft = updateDraft(initialDraft(), { product: "lab", prompt: "陶瓷瓶", style_ids: ["M001", "M002"], ratio: "1:1" }, styles, limits);
  assert.deepEqual(createPayload(draft), { idea: "陶瓷瓶", selected_style_ids: ["M001", "M002"], target_count: 2, images_per_style: 1, aspect_ratio: "1:1" });
  assert.throws(() => updateDraft(draft, { per_style: 2 }, styles, limits));
  assert.throws(() => updateDraft(draft, { style_ids: ["missing"] }, styles, limits));
});

test("case cards use the same-origin derivative and reject arbitrary source URLs", () => {
  const image = "images/ad-creative_case177/output.jpg";
  assert.equal(caseThumbnail("https://raw.githubusercontent.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts/main/" + image),
    "/api/v2/case-thumbnails/grid/" + image);
  assert.equal(caseThumbnail("/api/v2/case-thumbnails/preview/" + image), "/api/v2/case-thumbnails/grid/" + image);
  assert.equal(caseThumbnail("https://unrelated.example/" + image), "");
});

test("V2 results include unapproved images and preserve preview and original identity", () => {
  const run = projectRun("v2", { run_id: "run_test", status: "completed", selected_cases: [{ case_id: "case_id", title: "Poster" }],
    generation_jobs: [{ outputs: [{ output_id: "out_test", review: { decision: "needs_review", reasons: ["missing block"] } }] }] });
  assert.equal(runPath(run), "/api/v2/creative/runs/run_test");
  assert.equal(run.terminal, true);
  assert.deepEqual(run.outputs, [{ id: "out_test", preview: "/api/v2/image/history/out_test/preview",
    original: "/api/v2/outputs/out_test/download", review: "needs_review", reasons: ["missing block"] }]);
});

test("LAB results retain the original output ID and use only LAB routes", () => {
  const run = projectRun("lab", { session: { id: "lab_test", variants: [{ id: "variant_test", asset: { output_id: "out_test" } }] },
    board: { status: "partial_success", groups: [{ cards: [{ variant_id: "variant_test", style_preset_id: "M001", image_url: "/v1/outputs/out_test/download" }] }] } });
  assert.equal(runPath(run), "/api/lab/rare-style-explorer/sessions/lab_test");
  assert.equal(run.terminal, true);
  assert.equal(run.outputs[0].original, "/api/lab/outputs/out_test/download");
  assert.equal(run.outputs[0].style_id, "M001");
});

test("a missing or malformed receipt cannot switch to an arbitrary task", () => {
  assert.throws(() => projectRun("v2", { run_id: "../another" }));
  assert.throws(() => projectRun("lab", { session: {} }));
});

test("the page and site tools share LAB selections and result delivery", async (t) => {
  class Node {
    constructor() { this.listeners = {}; this.children = []; this.dataset = {}; this.value = ""; this.attributes = {}; this.classList = { add() {} }; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    setAttribute(name, value) { this.attributes[name] = value; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    querySelectorAll() { return this.children.filter((node) => node.dataset.id); }
    click() { this.listeners.click?.({ preventDefault() {} }); }
  }
  const buttons = ["v2", "lab"].map((product) => Object.assign(new Node(), { dataset: { product } }));
  const elements = new Map();
  const tools = new Map();
  const posted = [];
  const requestPaths = [];
  const getElementById = (id) => {
    if (!elements.has(id)) elements.set(id, new Node());
    return elements.get(id);
  };
  t.mock.method(globalThis, "fetch", async (url, options) => {
    requestPaths.push([options.method, url]);
    const json = (body) => new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
    if (url.startsWith("/api/v2/templates/page?")) return json({ items: [] });
    if (url.endsWith("/styles")) return json({ styles: [{ id: "M002", display_name: "氧化铜绿锈" }] });
    if (url.endsWith("/sessions")) {
      posted.push(JSON.parse(options.body));
      return json({ session: { id: "lab_test", status: "queued" } });
    }
    if (url.endsWith("/sessions/lab_test")) return json({
      session: { id: "lab_test", style_presets: [{ id: "M002", display_name: "氧化铜绿锈" }],
        variants: [{ id: "variant_test", asset: { output_id: "out_test" } }] },
      board: { status: "completed", groups: [{ cards: [{ variant_id: "variant_test",
        style_preset_id: "M002", style_name: "氧化铜绿锈", image_url: "/v1/outputs/out_test/download" }] }] },
    });
    throw new Error("unexpected route: " + url);
  });
  const originalTimeout = globalThis.setTimeout;
  t.mock.method(globalThis, "setTimeout", (fn, ms, ...args) => originalTimeout(fn, ms === 2500 ? 0 : ms, ...args));
  globalThis.document = { getElementById, createElement: () => new Node(), querySelectorAll: () => buttons,
    modelContext: { registerTool: (tool) => tools.set(tool.name, tool.execute) } };
  globalThis.window = new Node();
  try {
    await import("../src_skeleton/app/static/codex-workbench.mjs");
    const update = tools.get("alchemy_update_draft");
    const read = tools.get("alchemy_read_draft");
    await update({ product: "lab" });
    const results = await tools.get("alchemy_find_cards")({ query: "铜绿" });
    assert.match(results.cards[0].image, /copper-v1\.jpg$/);
    getElementById("catalog").children[0].click();
    assert.deepEqual((await read()).style_ids, ["M002"]);
    await update({ prompt: "铜器产品照", ratio: "4:5", per_style: 2 });
    assert.equal(getElementById("ratio").value, "4:5");
    assert.equal(getElementById("total").textContent, "共 2 张");
    const submit = getElementById("generation").listeners.submit;
    submit({ preventDefault() {} });
    submit({ preventDefault() {} });
    const getResult = tools.get("alchemy_read_result");
    for (let retry = 0; retry < 10 && !(await getResult())?.terminal; retry++) {
      await new Promise((resolve) => originalTimeout(resolve, 5));
    }
    assert.equal((await getResult()).status, "completed");
    assert.equal(posted.length, 1);
    assert.deepEqual(posted[0].selected_style_ids, ["M002"]);
    assert.equal(posted[0].target_count, 2);
    assert.ok(requestPaths.some(([method, url]) => method === "GET" && url.endsWith("/sessions/lab_test")));
    const rendered = getElementById("results").children[0].children;
    assert.equal(rendered[0].src, "/api/lab/outputs/out_test/preview");
    assert.equal(rendered[2].href, "/api/lab/outputs/out_test/download");
  } finally {
    delete globalThis.document;
    delete globalThis.window;
  }
});
