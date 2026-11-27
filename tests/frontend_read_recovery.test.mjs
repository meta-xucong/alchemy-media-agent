import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

function extract(source, name) {
  const start = source.search(new RegExp("^(?:async )?function " + name + "\\(", "m"));
  assert.notEqual(start, -1, name);
  return source.slice(start, source.indexOf("\n}", start) + 2);
}

function install(source, globals, names) {
  return vm.runInNewContext(names.map((name) => extract(source, name)).join("\n") +
    "\n({" + names.join(",") + "})", globals);
}

function clock() {
  const callbacks = new Map();
  let next = 0;
  return {
    setTimeout(run, milliseconds) {
      callbacks.set(++next, { run, milliseconds });
      return next;
    },
    clearTimeout(id) { callbacks.delete(id); },
    expire(milliseconds) {
      const due = [...callbacks].filter(([, item]) => item.milliseconds === milliseconds);
      assert.ok(due.length);
      for (const [id, item] of due) {
        callbacks.delete(id);
        item.run();
      }
    },
  };
}

const never = () => new Promise(() => {});
for (const [surface, file] of [
  ["desktop", "../src_skeleton/app/static/app.js"],
  ["H5", "../src_skeleton/app/mobile_static/mobile.js"],
]) {
  const source = readFileSync(new URL(file, import.meta.url), "utf8").replaceAll("\r\n", "\n");

  test(surface + " retries a stalled read with the same URL", async () => {
    const window = clock();
    const { readWithTimeout } = install(source, { window, DOMException, AbortController }, [
      "withRequestDeadline", "readWithTimeout",
    ]);
    const requests = [];
    const load = (path, { signal }) => {
      requests.push({ path, signal });
      return requests.length === 1 ? never() : "original result";
    };
    const read = readWithTimeout(load, "/projects/original", { retry: true });
    window.expire(8000);
    assert.equal(await read, "original result");
    assert.equal(requests[0].signal.aborted, true);
    assert.deepEqual(requests.map(({ path }) => path), ["/projects/original", "/projects/original"]);
  });

  test(surface + " recovers a lost V2 receipt with the same key and payload", async () => {
    const requests = [];
    const notices = [];
    const window = clock();
    const { submitV2Run } = install(source, {
      window, DOMException, AbortController,
      crypto: { randomUUID: () => "operation-id" },
      getVeyraToken: () => "current-session",
      v2Delay: async () => {},
      updateV2Notice: (notice) => notices.push(notice),
      v2Request: (path, options) => {
        requests.push({ path, options });
        return requests.length === 1 ? never() : { run_id: "original-run" };
      },
    }, ["withRequestDeadline", "submitV2Run"]);
    const body = { user_prompt: "offline fixture" };
    const receipt = submitV2Run(body);
    window.expire(8000);
    assert.equal((await receipt).run_id, "original-run");
    assert.equal(notices.length, 1);
    assert.equal(requests.length, 2);
    for (const { path, options } of requests) {
      assert.equal(path, "/creative/runs/async");
      assert.equal(options.headers["Idempotency-Key"], "operation-id");
      assert.equal(options.body, body);
    }
  });

  test(surface + " V2 gallery uses only small variants and leaves original for the lightbox", () => {
    const { v2HistoryImageCandidates, v2OutputImageCandidates } = install(source, {
      uniqueNonEmpty: (items) => [...new Set(items.filter(Boolean))],
      v2ExplicitDownloadUrl: (item) => item.url,
      v2OutputThumbnailUrl: (id) => "/outputs/" + id + "/thumbnail",
      v2OutputPreviewUrl: (id) => "/outputs/" + id + "/preview",
      v2DisplayMediaUrl: (url) => url,
      v2MediaUrl: (url) => url,
    }, ["v2HistoryImageCandidates", "v2OutputImageCandidates"]);
    const url = "/outputs/image/download";
    const item = { output_id: "image", url, thumbnail_url: url };
    for (const candidates of [v2HistoryImageCandidates, v2OutputImageCandidates]) {
      assert.deepEqual([...new Set(candidates(item))], [
        "/outputs/image/thumbnail", "/outputs/image/preview",
      ]);
      assert.equal(candidates(item, { thumbnail: false })[0], url);
    }
  });

  test(surface + " V2 lightbox opens the existing preview and keeps the original download", () => {
    const preview = "/api/v2/image/history/out_saved/preview";
    const thumb = "/api/v2/image/history/out_saved/thumbnail";
    const original = "/api/v2/outputs/out_saved/download";
    let loadOptions;
    let download;
    const els = {
      lightboxTitle: {}, lightboxImage: { dataset: {} }, lightboxMeta: {}, lightboxPromptText: {},
      lightboxPromptBtn: { classList: { toggle() {} } }, copyPromptBtn: {}, imageLightbox: {},
      closeImageLightboxBtn: { focus() {} },
    };
    const { openImageLightbox } = install(source, {
      els, document: { body: { classList: { add() {} } } },
      bindProgressiveLightboxImage: (_image, options) => { loadOptions = options; },
      bindDownloadLink: (_button, url) => { download = url; },
      normalizeOriginalDownloadUrl: (url) => url,
      shareDescriptionFromPrompt: () => "", shareCurrentLightboxImage() {},
      setPromptCopyState() {}, closeLightboxPrompt() {}, resetLightboxZoom() {}, renderLightboxActions() {},
    }, ["openImageLightbox"]);
    openImageLightbox({ url: original, thumbnailUrl: thumb, previewUrl: preview, v2Preview: true });
    assert.equal(loadOptions.displayUrl, preview);
    assert.equal(loadOptions.thumbnailUrl, thumb);
    assert.equal(loadOptions.recoverPreview, true);
    assert.equal(loadOptions.originalUrl, original);
    assert.equal(download, original);
    assert.equal(els.lightboxImage.dataset.fullUrl, original);
    openImageLightbox({ url: original, thumbnailUrl: thumb, previewUrl: preview });
    assert.equal(loadOptions.displayUrl, original);
    assert.equal(loadOptions.recoverPreview, false);
  });

  test(surface + " V2 lightbox retries only the stalled preview and cancels when closed", async () => {
    const window = clock();
    const preview = "/api/v2/image/history/out_saved/preview";
    const requests = [];
    const { loadV2LightboxSource } = install(source, {
      window, DOMException, AbortController,
      resolveAuthenticatedMediaSource: (url, { signal }) => {
        requests.push({ url, signal });
        return requests.length === 2 ? { url: "blob:preview", objectUrl: true } : never();
      },
    }, ["withRequestDeadline", "loadV2LightboxSource"]);
    const first = new AbortController();
    const reading = loadV2LightboxSource(preview, "/original", first.signal);
    window.expire(8000);
    assert.equal((await reading).url, "blob:preview");
    assert.deepEqual(requests.map(({ url }) => url), [preview, preview]);
    assert.equal(requests[0].signal.aborted, true);
    const closing = new AbortController();
    const closed = loadV2LightboxSource(preview, "/original", closing.signal);
    closing.abort();
    await assert.rejects(closed, { name: "AbortError" });
    assert.equal(requests.length, 3);
    assert.equal(requests[2].signal.aborted, true);
  });

  test(surface + " V2 legacy preview falls back on 404 and respects access errors", async () => {
    const requests = [];
    const window = clock();
    let status = 404;
    const { loadV2LightboxSource } = install(source, {
      window, DOMException, AbortController,
      resolveAuthenticatedMediaSource: async (url) => {
        requests.push(url);
        if (url === "/preview") throw Object.assign(new Error("preview unavailable"), { status });
        return { url: "blob:original" };
      },
    }, ["withRequestDeadline", "loadV2LightboxSource"]);
    assert.equal((await loadV2LightboxSource("/preview", "/original", new AbortController().signal)).url, "blob:original");
    assert.deepEqual(requests, ["/preview", "/original"]);
    requests.length = 0;
    status = 403;
    await assert.rejects(loadV2LightboxSource("/preview", "/original", new AbortController().signal), { status: 403 });
    assert.deepEqual(requests, ["/preview"]);
  });

  test(surface + " keeps a download slot for thumbnails and releases a stalled original", async () => {
    const desktop = surface === "desktop";
    const queue = desktop ? "v3ProtectedMediaQueue" : "protectedMediaQueue";
    const enqueue = desktop ? "fetchV3ProtectedMediaBlob" : "fetchProtectedMediaBlob";
    const start = source.indexOf("const " + queue + " =");
    const end = source.indexOf(extract(source, enqueue), start) + extract(source, enqueue).length;
    const requests = [];
    const timers = clock();
    const add = vm.runInNewContext(source.slice(start, end) + "\n" + enqueue, {
      ...timers, AbortController, getVeyraToken: () => "",
      fetch: async (url, { signal }) => {
        requests.push(url);
        return {
          ok: true,
          blob: () => url.endsWith("/thumbnail") ? { size: 1, type: "image/webp" } :
            new Promise((_, reject) => signal.addEventListener("abort", () => reject(signal.reason), { once: true })),
        };
      },
    });
    const first = add("/api/first/download", null, { preview: true });
    const second = add("/api/second/download", null, { preview: true });
    await add("/api/third/thumbnail");
    assert.deepEqual(requests.slice(0, 2), ["/api/first/download", "/api/third/thumbnail"]);
    timers.expire(30000);
    await assert.rejects(first, { name: "AbortError" });
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(requests.at(-1), "/api/second/download");
    timers.expire(30000);
    await assert.rejects(second, { name: "AbortError" });
  });
}
