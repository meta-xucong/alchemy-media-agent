#!/usr/bin/env node
// Isolated Chromium renderer probe. No application server, account, or Provider.
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const checkOnly = process.argv[2] === "--check";
const output = process.argv[2];
if (!output) throw new Error("Usage: node scripts/probe_browser_history_windows.mjs --check | /tmp/history-browser-probe.json");
const functions = [
  "historyDemandState", "historyDemandVisible", "historyPickerVisible", "historyFavoritesDemanded",
  "invalidateHistoryDemand", "clearHistoryDemandCaches", "ensureHistoryDemand", "renderHistoryDemand",
  "clearHistoryMedia", "historyWindowLabel", "renderHistoryWindowNavigation", "loadPreviousHistoryWindow",
  "changeHistoryBrowseMode", "historyHeroVisible", "ensureHistoryHero", "historyMediaDemand", "readHistoryDemand",
  "refreshHistory", "loadV2History", "hasMoreV1History", "hasMoreV2History", "loadMoreV1History", "loadMoreV2History",
  "loadRemainingV1HistoryForFavorites", "loadRemainingV2HistoryForFavorites", "renderHistory", "renderV2History",
  "renderFavoritePicker", "renderV2FavoriteReferencePicker", "editableFavoriteHistoryItems", "v2FavoriteReferenceItems",
  "closeFavoritePicker", "closeV2FavoriteReferencePicker", "renderHeroHistory", "releaseImageObjectUrl", "bindImageWithFallback",
  "v2HistoryEndpoint", "v2HistoryPath", "loadV2RequestWithTimeout", "loadV2HistoryWithTimeout", "loadV2HistoryResponse",
];
function extract(source, name) {
  const start = new RegExp(`^(?:async )?function ${name}\\(`, "m").exec(source);
  assert.ok(start, name);
  const tail = source.slice(start.index);
  for (const close of tail.matchAll(/^\};?\s*$/gm)) {
    const text = tail.slice(0, close.index + close[0].trimEnd().length);
    try { new vm.Script(text); return text; } catch (error) { if (!(error instanceof SyntaxError)) throw error; }
  }
  throw new Error(`Cannot extract ${name}`);
}
function initializeFixture({ moduleName }) {
      window.moduleName = moduleName;
      const names = ["historyGallery", "historyCount", "v2HistoryGrid", "v2HistoryCount", "heroHistoryCarousel",
        "favoritePickerModal", "favoritePickerGrid", "favoritePickerCount", "v2FavoriteReferenceModal",
        "v2FavoriteReferenceGrid", "v2FavoriteReferenceCount", "refreshHistoryBtn", "v2RefreshHistoryBtn"];
      window.els = Object.fromEntries(names.map((name) => {
        const element = document.createElement("div"); element.id = name; document.body.append(element); return [name, element];
      }));
      els.favoritePickerModal.hidden = els.v2FavoriteReferenceModal.hidden = true;
      els.favoritePickerModal.append(els.favoritePickerGrid, els.favoritePickerCount);
      els.v2FavoriteReferenceModal.append(els.v2FavoriteReferenceGrid, els.v2FavoriteReferenceCount);
      window.state = { historyItems: [], historyTotal: 0, historyRenderLimit: 24, historyFavoritesOnly: false };
      window.v2State = { history: [], historyTotal: 0, historyRenderLimit: 24, historyFavoritesOnly: false };
      window.veyraState = {};
      // The desktop media binder owns deferred V3 bindings even on V1/V2 calls.
      // Include its actual helper state rather than replacing cleanup with a no-op.
      window.v3DeferredImageLoads = new Map();
      window.v3ImageBindingStates = new WeakMap();
      window.v3DeferredImageObserver = null;
      window.activePanelName = () => moduleName === "v1" ? "image" : "v2";
      window.getVeyraToken = () => "synthetic-account";
      window.request = window.v2Request = async (url, options = {}) => (await fetch(url, { signal: options.signal })).json();
      window.isRenderableV2HistoryImage = (item) => item.renderable !== false;
      window.compareHistoryItems = (a, b) => b.created_at - a.created_at;
      window.uniqueNonEmpty = (values) => [...new Set(values.filter(Boolean))];
      window.friendlyError = (error) => error.message;
      window.showNotice = window.updateV2Notice = window.showGlobalToast = (message, kind) => { if (kind === "error") throw new Error(message); };
      window.clearHeroCarouselTimer = window.restartHeroCarousels = window.scheduleMobileSummaryUpdate = () => {};
      window.normalizeHeroHistoryItem = (item) => ({ id: item.id, url: item.url, thumbnailUrl: item.url });
      window.historyItemCanDelete = () => false;
      window.createFavoriteButton = () => document.createElement("button");
      window.bindDownloadLink = () => {};
      for (const name of ["historyMetaText", "v2HistoryProviderResultText", "historyDetailText", "historyRecordLabel", "formatDate", "favoriteRevisionDetail"]) window[name] = () => "synthetic";
      window.v2HistoryCardPrompt = (item) => item.prompt;
      window.v2HistoryImageCandidates = (item) => [item.url];
      window.v1ExplicitDownloadUrl = window.v2ExplicitDownloadUrl = (item) => item.url;
      window.v2HistoryFormat = () => "png";
      window.mediaUrlNeedsAuthenticatedFetch = () => true;
      const png = Uint8Array.from(atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="), (char) => char.charCodeAt(0));
      window.liveObjectUrls = new Set();
      const create = URL.createObjectURL.bind(URL), revoke = URL.revokeObjectURL.bind(URL);
      URL.createObjectURL = (blob) => { const url = create(blob); liveObjectUrls.add(url); return url; };
      URL.revokeObjectURL = (url) => { liveObjectUrls.delete(url); revoke(url); };
      window.resolveAuthenticatedMediaSource = async () => ({ url: URL.createObjectURL(new Blob([png], { type: "image/png" })), objectUrl: true });
      window.sample = () => {
        const model = moduleName === "v1" ? state : v2State;
        const rows = model[moduleName === "v1" ? "historyItems" : "history"];
        const grid = moduleName === "v1" ? els.historyGallery : els.v2HistoryGrid;
        const picker = moduleName === "v1" ? els.favoritePickerGrid : els.v2FavoriteReferenceGrid;
        return { rows: rows.length, heroRows: model.historyHeroItems?.length || 0,
          historyImages: grid.querySelectorAll("img").length, pickerImages: picker.querySelectorAll("img").length,
          heroImages: els.heroHistoryCarousel.querySelectorAll("img").length, objectUrls: liveObjectUrls.size,
          start: model.historyDemand?.start || 0, offset: model.historyDemand?.offset || 0 };
      };
}

// This lightweight DOM checks the exact browser fixture and dynamic programs
// for missing runtime dependencies. It is not browser/heap evidence.
function fixtureNode(tagName = "div") {
  const classes = new Set();
  return {
    tagName: tagName.toUpperCase(), dataset: {}, hidden: false, children: [], parentElement: null,
    get innerHTML() { return ""; },
    set innerHTML(value) { this.children.forEach((child) => { child.parentElement = null; }); this.children = []; },
    classList: {
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      contains: (name) => classes.has(name),
      toggle(name, force = !classes.has(name)) { if (force) classes.add(name); else classes.delete(name); },
    },
    append(...children) { children.forEach((child) => this.appendChild(child)); },
    appendChild(child) {
      if (child.parentElement) child.parentElement.children = child.parentElement.children.filter((entry) => entry !== child);
      child.parentElement = this; this.children.push(child); return child;
    },
    querySelectorAll(selector) {
      const children = this.children.flatMap((child) => [child, ...child.querySelectorAll("*")]);
      return selector === "*" ? children : children.filter((child) => child.tagName === selector.toUpperCase());
    },
    closest(selector) {
      for (let current = this; current; current = current.parentElement) if (selector === "[hidden]" && current.hidden) return current;
      return null;
    },
    addEventListener() {}, removeEventListener() {}, removeAttribute(name) { delete this[name]; },
    setAttribute(name, value) { this[name] = value; }, focus() {},
  };
}

async function validateFixtureRuntime(sources) {
  for (const [shell, { program }] of sources) for (const moduleName of ["v1", "v2"]) {
    let blobId = 0;
    class FixtureURL extends URL {
      static createObjectURL() { return `blob:offline-${++blobId}`; }
      static revokeObjectURL() {}
    }
    const context = vm.createContext({
      console, URL: FixtureURL, URLSearchParams, Blob, atob, AbortController, setTimeout, clearTimeout,
      document: { body: fixtureNode("body"), createElement: fixtureNode, removeEventListener() {} },
      fetch: async (path) => {
        const url = new URL(path, "http://history-probe.test");
        assert.ok(url.pathname.endsWith("/history"));
        const offset = Number(url.searchParams.get("offset"));
        const limit = Number(url.searchParams.get("limit"));
        assert.ok(limit > 0 && limit <= 24);
        return { json: async () => ({ total: 50000, items: Array.from({ length: limit }, (_, index) => ({
          id: `row-${offset + index}`, output_id: `row-${offset + index}`, favorite: true,
          created_at: 50000 - offset - index, format: "png", source: "repository", prompt: "offline", url: "/media.png",
        })) }) };
      },
    });
    vm.runInContext('globalThis.window = globalThis;', context);
    vm.runInContext(`(${initializeFixture.toString()})(${JSON.stringify({ moduleName })});`, context);
    vm.runInContext(program, context);
    await context.ensureHistoryDemand(moduleName);
    for (const favorites of [false, true]) {
      if (favorites) {
        context.els[moduleName === "v1" ? "favoritePickerModal" : "v2FavoriteReferenceModal"].hidden = false;
        await context.ensureHistoryDemand(moduleName);
      }
      for (let page = 0; page < 12; page += 1) {
        await context[moduleName === "v1" ? "loadMoreV1History" : "loadMoreV2History"]();
        const sample = context.sample();
        assert.ok(sample.rows <= 72 && sample.heroRows <= 24);
        assert.ok(sample.historyImages <= 72 && sample.pickerImages <= 72 && sample.heroImages <= 8);
        assert.ok(sample.objectUrls <= 152);
      }
      const start = context.sample().start;
      await context.loadPreviousHistoryWindow(moduleName);
      assert.equal(context.sample().start, start - 72);
    }
    // Execute the desktop deferred branch too; it shares cleanup state.
    if (shell === "desktop") {
      const image = fixtureNode("img");
      context.bindImageWithFallback(image, ["/media.png"], { deferAuthenticated: true });
      await new Promise((resolve) => setImmediate(resolve));
      context.releaseImageObjectUrl(image);
    }
    context.clearHistoryDemandCaches();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(context.sample().rows, 0);
    assert.equal(context.sample().objectUrls, 0);
    console.log(`${shell}/${moduleName}: shared probe fixture executed paging, favorites, Previous and auth cleanup`);
  }
}

// Validate every dynamically constructed pattern and function before launching
// a browser. This can run even where the executor cannot start Chromium.
const sources = new Map();
for (const shell of ["desktop", "mobile"]) {
  const path = shell === "desktop" ? "../src_skeleton/app/static/app.js" : "../src_skeleton/app/mobile_static/mobile.js";
  const source = readFileSync(new URL(path, import.meta.url), "utf8");
  const constants = [...source.matchAll(/^const (\w+) = (\d+);$/gm)];
  assert.ok(constants.some((match) => match[1] === "historyWindowSize" && match[2] === "72"));
  const helpers = ["cancelV3DeferredImageLoad", "deferV3ImageUntilVisible"]
    .filter((name) => source.includes(`function ${name}(`));
  const selectedFunctions = [...functions, ...helpers];
  const program = constants.map((match) => `window.${match[1]} = ${match[2]};`).join("\n")
    + "\n" + selectedFunctions.map((name) => extract(source, name)).join("\n");
  new vm.Script(program);
  sources.set(shell, { source, program });
  if (checkOnly) console.log(`${shell}: extracted and parsed ${selectedFunctions.length} shipped functions and ${constants.length} constants`);
}
if (checkOnly) {
  await validateFixtureRuntime(sources);
  process.exit(0);
}
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROMIUM_EXECUTABLE_PATH || chromium.executablePath(),
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const report = {
  scope: "Actual shipped history functions and DOM in isolated Chromium; synthetic intercepted history; not full product navigation, Provider, or VPS acceptance.",
  commit: process.env.GITHUB_SHA || null,
  chromium: browser.version(),
  fixture: { rows: 50000, promptBytesPerRow: 2048, allRowsFavorited: true, gesturesPerSurface: 360 },
  results: [],
};
try {
  for (const shell of ["desktop", "mobile"]) for (const moduleName of ["v1", "v2"]) {
    const { source, program } = sources.get(shell);
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (error) => { if (errors.length < 10) errors.push(String(error)); });
    let historyRequests = 0;
    await page.route("**/*", async (route) => {
      const url = new URL(route.request().url());
      assert.equal(url.origin, "http://history-probe.test", "No external requests are allowed");
      if (url.pathname === "/") return route.fulfill({ contentType: "text/html", body: "<!doctype html><html><body></body></html>" });
      assert.ok(url.pathname.endsWith("/history"), `Unexpected endpoint: ${url.pathname}`);
      historyRequests += 1;
      const offset = Number(url.searchParams.get("offset"));
      const limit = Number(url.searchParams.get("limit"));
      assert.ok(limit > 0 && limit <= 24);
      const items = Array.from({ length: Math.min(limit, 50000 - offset) }, (_, index) => ({
        id: `row-${offset + index}`, output_id: `row-${offset + index}`, favorite: true,
        created_at: 50000 - offset - index, format: "png", source: "repository",
        prompt: `${offset + index}:` + "p".repeat(2048), url: "/media.png", thumbnail_url: "/media.png",
      }));
      return route.fulfill({ contentType: "application/json", body: JSON.stringify({ items, total: 50000 }) });
    });
    await page.goto("http://history-probe.test/");
    await page.evaluate(initializeFixture, { moduleName });
    await page.addScriptTag({ content: program });
    const cdp = await page.context().newCDPSession(page);
    const samples = [];
    async function checkpoint(label) {
      await page.waitForTimeout(30);
      await cdp.send("HeapProfiler.collectGarbage");
      const sample = await page.evaluate(() => sample());
      const heap = await cdp.send("Runtime.getHeapUsage");
      const dom = await cdp.send("Memory.getDOMCounters");
      assert.ok(sample.rows <= 72 && sample.heroRows <= 24);
      assert.ok(sample.historyImages <= 72 && sample.pickerImages <= 72 && sample.heroImages <= 8);
      assert.ok(sample.objectUrls <= 152, JSON.stringify(sample));
      assert.deepEqual(errors, []);
      samples.push({ label, ...sample, heap, dom });
    }
    await page.evaluate(() => ensureHistoryDemand(moduleName));
    await checkpoint("first_page");
    for (const favorites of [false, true]) {
      if (favorites) await page.evaluate(() => {
        els[moduleName === "v1" ? "favoritePickerModal" : "v2FavoriteReferenceModal"].hidden = false;
        return ensureHistoryDemand(moduleName);
      });
      let done = 0;
      for (const target of [24, 120, 360]) {
        await page.evaluate(async ({ count }) => {
          for (let index = 0; index < count; index += 1) {
            await (moduleName === "v1" ? loadMoreV1History() : loadMoreV2History());
            const value = sample();
            if (value.rows > 72 || value.historyImages > 72 || value.pickerImages > 72) throw new Error(JSON.stringify(value));
          }
        }, { count: target - done });
        done = target;
        await checkpoint(`${favorites ? "favorites" : "ordinary"}_${target}_gestures`);
      }
      const start = await page.evaluate(() => sample().start);
      await page.evaluate(() => loadPreviousHistoryWindow(moduleName));
      assert.equal(await page.evaluate(() => sample().start), start - 72);
    }
    const warm = samples.find((sample) => sample.label === "favorites_24_gestures");
    const late = samples.find((sample) => sample.label === "favorites_360_gestures");
    assert.ok(late.heap.usedSize - warm.heap.usedSize < 8 * 1024 * 1024, "Post-GC heap grew by more than the probe's 8 MiB tolerance");
    await page.evaluate(() => clearHistoryDemandCaches());
    await checkpoint("auth_cache_clear");
    assert.equal(samples.at(-1).objectUrls, 0);
    report.results.push({ shell, module: moduleName,
      sourceSha256: createHash("sha256").update(source).digest("hex"), historyRequests, samples });
    // Preserve completed surface evidence even if a later surface fails.
    writeFileSync(output, JSON.stringify(report, null, 2) + "\n");
    await page.close();
  }
  writeFileSync(output, JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify(report.results.map(({ shell, module, historyRequests, samples }) => ({ shell, module, historyRequests,
    warmHeap: samples.find((sample) => sample.label === "favorites_24_gestures").heap.usedSize,
    lateHeap: samples.find((sample) => sample.label === "favorites_360_gestures").heap.usedSize,
    clearedObjectUrls: samples.at(-1).objectUrls })), null, 2));
} finally {
  await browser.close();
}
