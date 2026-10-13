import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const desktop = readFileSync(
  new URL("../src_skeleton/app/static/app.js", import.meta.url),
  "utf8",
);
const mobile = readFileSync(
  new URL("../src_skeleton/app/mobile_static/mobile.js", import.meta.url),
  "utf8",
);

function extractFunction(source, name) {
  const match = new RegExp(`^([ \\t]*)(?:async )?function ${name}\\(`, "m").exec(source);
  assert.ok(match, `production function ${name} exists`);
  const tail = source.slice(match.index);
  const closes = new RegExp(`^${match[1]}\\};?\\s*$`, "gm");
  for (const close of tail.matchAll(closes)) {
    const candidate = tail.slice(0, close.index + close[0].trimEnd().length);
    try {
      new vm.Script(candidate);
      return candidate;
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
    }
  }
  assert.fail(`complete production function ${name} is extractable`);
}

const desktopFunctions = [
  "function uniqueNonEmpty(values) { return [...new Set(values.map((item) => String(item || \"\").trim()).filter(Boolean))]; }",
  "function v3MediaUrl(value) { return String(value || \"\").trim(); }",
  extractFunction(desktop, "v3OutputImageCandidates"),
  extractFunction(desktop, "mergeV3ReviewImageSources"),
].join("\n");
const mobileFunctions = [
  "const mobileV3ApiBase = \"\";",
  extractFunction(mobile, "mobileV3MediaUrl"),
  extractFunction(mobile, "mobileV3ThumbUrl"),
  extractFunction(mobile, "mobileV3PreviewUrl"),
  extractFunction(mobile, "mobileV3FullUrl"),
  extractFunction(mobile, "mergeMobileV3ReviewImageSources"),
].join("\n");

const mobileLightboxFunctions = [
  extractFunction(mobile, "mobileV3OutputId"),
  extractFunction(mobile, "mobileV3ReviewImageReason"),
  extractFunction(mobile, "openMobileV3OutputLightbox"),
  extractFunction(mobile, "handleMobileV3GalleryPreviewClick"),
].join("\n");

function mergeUsing(source, functionName, ...sources) {
  const context = {};
  vm.runInNewContext(source, context);
  return context[functionName](...sources);
}

for (const [surface, source, functionName] of [
  ["desktop", desktopFunctions, "mergeV3ReviewImageSources"],
  ["mobile", mobileFunctions, "mergeMobileV3ReviewImageSources"],
]) {
  test(`${surface} keeps distinct outputs that share one logical asset`, () => {
    const thumbnail = {
      project_id: "project-a",
      job_id: "job-a",
      output_id: "output-a",
      candidate_id: "candidate-a",
      asset_id: "shared-role-asset",
      thumbnail_url: "/media/output-a/thumb",
      review_reason: "reason A",
    };
    const download = {
      project_id: "project-a",
      job_id: "job-a",
      output_id: "output-b",
      candidate_id: "candidate-b",
      asset_id: "shared-role-asset",
      download_url: "/media/output-b/full",
      review_reason: "reason B",
    };
    const merged = mergeUsing(source, functionName, [thumbnail, download]);
    assert.equal(merged.length, 2);
    assert.deepEqual(Array.from(merged, (item) => item.output_id), ["output-a", "output-b"]);
    assert.deepEqual(Array.from(merged, (item) => item.review_reason), ["reason A", "reason B"]);
    assert.equal(merged[0].download_url || "", "");
    assert.equal(merged[1].thumbnail_url || "", "");
  });

  test(`${surface} only fills media and missing metadata for one exact image identity`, () => {
    const persisted = {
      project_id: "project-a",
      job_id: "job-a",
      output_id: "output-a",
      candidate_id: "candidate-a",
      asset_id: "logical-asset",
      thumbnail_url: "/media/output-a/thumb",
      review_reason: "persisted review reason",
      metadata: { project_id: "project-a", job_id: "job-a" },
    };
    const candidate = {
      project_id: "project-a",
      job_id: "job-a",
      output_id: "output-a",
      candidate_id: "candidate-a",
      asset_id: "logical-asset",
      download_url: "/media/output-a/full",
      review_reason: "",
      metadata: { extra_review_context: "same output" },
    };
    const merged = mergeUsing(source, functionName, [persisted], [candidate]);
    assert.equal(merged.length, 1);
    assert.equal(merged[0].thumbnail_url, "/media/output-a/thumb");
    assert.equal(merged[0].download_url, "/media/output-a/full");
    assert.equal(merged[0].review_reason, "persisted review reason");
    assert.equal(merged[0].candidate_id, "candidate-a");
  });

  test(`${surface} refuses weak asset aliases, identity collisions, and contradictory scope`, () => {
    const cases = [
      [
        { job_id: "job-a", output_id: "output-a", candidate_id: "candidate-a", asset_id: "shared" },
        { job_id: "job-a", output_id: "output-b", candidate_id: "candidate-b", asset_id: "shared" },
      ],
      [
        { job_id: "job-a", output_id: "output-a", candidate_id: "candidate-a", asset_id: "shared" },
        { job_id: "job-a", output_id: "output-b", candidate_id: "candidate-a", asset_id: "shared" },
      ],
      [
        { job_id: "job-a", output_id: "same-token" },
        { job_id: "job-a", candidate_id: "same-token" },
      ],
      [
        { job_id: "job-a", asset_id: "shared" },
        { job_id: "job-a", asset_id: "shared" },
      ],
      [
        { project_id: "project-a", job_id: "job-a", output_id: "output-a" },
        { metadata: { project_id: "project-b", job_id: "job-a", output_id: "output-a" } },
      ],
      [
        { project_id: "project-a", job_id: "job-a", output_id: "output-a" },
        { project_id: "project-a", related_job_id: "job-b", output_id: "output-a" },
      ],
      [
        { job_id: "job-a", metadata: { job_id: "job-b" }, output_id: "output-a" },
        { job_id: "job-a", output_id: "output-a" },
      ],
    ];
    for (const [index, pair] of cases.entries()) {
      assert.equal(mergeUsing(source, functionName, pair).length, 2, `case ${index}: ${JSON.stringify(pair)}`);
    }
  });

  test(`${surface} uses exact output identity before differing reference IDs`, () => {
    const records = mergeUsing(
      source,
      functionName,
      [
        { project_id: "project-a", job_id: "job-a", output_id: "output-a", output_ref_id: "ref-old", thumbnail_url: "/thumb" },
        { project_id: "project-a", job_id: "job-a", output_id: "output-a", output_ref_id: "ref-new", download_url: "/full", review_reason: "reason" },
      ],
    );
    assert.equal(records.length, 1);
    assert.equal(records[0].thumbnail_url, "/thumb");
    assert.equal(records[0].download_url, "/full");
    assert.equal(records[0].review_reason, "reason");
  });
}

test("mobile candidate-only review card opens its bound item as non-delivery with its reason", () => {
  const context = {
    mobileV3State: { outputs: [], reviewOutputs: [], currentJob: null },
    mobileV3FullUrl: (item) => item.download_url || "",
    mobileV3DownloadUrl: (item) => item.download_url || "",
    mobileV3ThumbUrl: (item) => item.thumbnail_url || "",
    mobileV3PreviewUrl: (item) => item.preview_url || "",
    mobileV3OutputSummary: () => "output summary",
    openImageLightbox: (options) => { context.lastLightboxOptions = options; },
    els: { lightboxPromptPanel: { hidden: true } },
    toggleLightboxPrompt: () => {},
  };
  vm.runInNewContext(mobileLightboxFunctions, context);
  const item = {
    output_id: "candidate-only-output",
    candidate_id: "candidate-only-review",
    review_reason: "Candidate-only review reason.",
    thumbnail_url: "/media/candidate-only/thumb",
  };
  const button = {
    dataset: { mobileV3GalleryPreview: item.output_id, mobileV3ReviewOnly: "true" },
    classList: { contains: () => false },
    __mobileV3OutputItem: item,
  };
  let defaultPrevented = false;
  let propagationStopped = false;
  context.handleMobileV3GalleryPreviewClick({
    target: { closest: () => button },
    preventDefault: () => { defaultPrevented = true; },
    stopPropagation: () => { propagationStopped = true; },
  });

  assert.equal(defaultPrevented, true);
  assert.equal(propagationStopped, true);
  assert.equal(context.lastLightboxOptions.id, item.output_id);
  assert.equal(context.lastLightboxOptions.title, "复核图 · 非正式交付");
  assert.match(context.lastLightboxOptions.meta, /Candidate-only review reason\./);
  assert.match(context.lastLightboxOptions.meta, /仅供复核，不属于正式交付/);
});

test("mobile lightbox recovers a review reason from the matching Job inspection", () => {
  const context = {
    mobileV3State: {
      currentJob: {
        metadata: {
          post_generation_review_package: {
            inspections: [{ output_id: "output-a", detected_issues: [{ message: "manual identity check needed" }] }],
          },
        },
      },
    },
    mobileV3FullUrl: () => "",
    mobileV3DownloadUrl: () => "",
    mobileV3ThumbUrl: () => "",
    mobileV3PreviewUrl: () => "",
    mobileV3OutputSummary: () => "output summary",
    openImageLightbox: (options) => { context.lastLightboxOptions = options; },
    els: { lightboxPromptPanel: { hidden: true } },
    toggleLightboxPrompt: () => {},
  };
  vm.runInNewContext(mobileLightboxFunctions, context);
  context.openMobileV3OutputLightbox({ output_id: "output-a" }, { reviewOnly: true });
  assert.match(context.lastLightboxOptions.meta, /manual identity check needed/);
  assert.equal(context.lastLightboxOptions.title, "复核图 · 非正式交付");
});

test("mobile review reason prefers the exact output when sibling outputs share an asset", () => {
  const context = {
    mobileV3State: {
      currentJob: {
        metadata: {
          post_generation_review_package: {
            inspections: [
              { output_id: "output-a", asset_id: "shared-asset", review_reason: "reason for A" },
              { output_id: "output-b", asset_id: "shared-asset", review_reason: "reason for B" },
            ],
          },
        },
      },
    },
  };
  vm.runInNewContext(mobileLightboxFunctions, context);
  assert.equal(
    context.mobileV3ReviewImageReason({ output_id: "output-b", asset_id: "shared-asset" }),
    "reason for B",
  );
});

test("mobile asset-only review reason never aliases an output ID with the same string", () => {
  const context = {
    mobileV3State: {
      currentJob: {
        metadata: {
          post_generation_review_package: {
            inspections: [
              { output_id: "shared-token", review_reason: "wrong output reason" },
              { asset_id: "shared-token", review_reason: "exact asset reason" },
            ],
          },
        },
      },
    },
  };
  vm.runInNewContext(mobileLightboxFunctions, context);
  assert.equal(context.mobileV3ReviewImageReason({ asset_id: "shared-token" }), "exact asset reason");
});
