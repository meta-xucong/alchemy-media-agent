import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const desktopJs = readFileSync(
  new URL("../src_skeleton/app/static/app.js", import.meta.url),
  "utf8",
);
const mobileJs = readFileSync(
  new URL("../src_skeleton/app/mobile_static/mobile.js", import.meta.url),
  "utf8",
);
const desktopHtml = readFileSync(
  new URL("../src_skeleton/app/static/index.html", import.meta.url),
  "utf8",
);
const mobileHtml = readFileSync(
  new URL("../src_skeleton/app/mobile_static/index.html", import.meta.url),
  "utf8",
);
const desktopCss = readFileSync(
  new URL("../src_skeleton/app/static/styles.css", import.meta.url),
  "utf8",
);
const mobileCss = readFileSync(
  new URL("../src_skeleton/app/mobile_static/mobile.css", import.meta.url),
  "utf8",
);

function sourceHelpers(source) {
  const start = source.indexOf("function generatedImageRoute(");
  const end = source.indexOf("\nfunction providerResultText(", start);
  assert.ok(start >= 0 && end > start, "image route display helpers must be present");
  const context = {};
  vm.runInNewContext(`${source.slice(start, end)}\nthis.resolve = generatedImageSourceText;`, context);
  return context.resolve;
}

for (const [surface, source] of [["desktop", desktopJs], ["mobile", mobileJs]]) {
  test(`${surface} labels actual bridge/API provenance and fails closed on missing data`, () => {
    const label = sourceHelpers(source);

    assert.equal(label({ metadata: { render_bridge_primary: { route: "bridge" }, actual_provider: "openai_gpt_image" } }), "RenderBridge");
    assert.equal(label({ metadata: { render_bridge_primary: { route: "api" }, actual_provider: "codex-image" } }), "API");
    assert.equal(label({ metadata: { primary_provenance: { route: "bridge" } } }), "RenderBridge");
    assert.equal(label({ provider_id: "doubao_image" }), "API");
    assert.equal(label({ provider_id: "codex-image" }), "RenderBridge");
    assert.equal(label({ metadata: { mock: true } }), "Mock");
    assert.equal(label({ metadata: { requested_provider: "openai_gpt_image" } }), "来源未记录");
  });
}

test("V1, V2, and V3 image cards visibly label source on both surfaces", () => {
  for (const source of [desktopJs, mobileJs]) {
    assert.match(source, /function outputProviderResultText\(output, job\)\s*\{\s*return generatedImageSourceText\(output, job\);/);
    assert.match(source, /function v2ProviderResultText\(job, output\)\s*\{\s*return generatedImageSourceText\(output, job\);/);
    assert.match(source, /function v2HistoryProviderResultText\(item\)\s*\{\s*return generatedImageSourceText\(item\);/);
    assert.match(source, /生成方式：\$\{escapeHtml\(generatedImageSourceText\(item,/);
  }
  assert.match(desktopJs, /class="v3-source-badge"/);
  assert.match(mobileJs, /className = "v3-mobile-source-badge"/);
});

test("V1 image IDs stay collapsed until requested", () => {
  for (const html of [desktopHtml, mobileHtml]) {
    assert.match(
      html,
      /<details class="output-diagnostics">\s*<summary>图片 ID<\/summary>\s*<span class="output-id"><\/span>\s*<\/details>/,
    );
    assert.match(
      html,
      /<details class="status-id-details">\s*<summary>跟踪 ID<\/summary>\s*<strong id="traceId">-<\/strong>\s*<\/details>/,
    );
  }

  for (const source of [desktopJs, mobileJs]) {
    assert.match(source, /function renderGallery\(outputs\)[\s\S]*?const provider = node\.querySelector\("\.output-provider"\);/);
    assert.match(source, /provider\.textContent = outputProviderResultText\(output, state\.currentJob\);/);
    assert.match(
      source,
      /function renderHistory\(items\)[\s\S]*?diagnosticsSummary\.textContent = "图片 ID"[\s\S]*?diagnostics\.append\(diagnosticsSummary, id\)[\s\S]*?footer\.append\(diagnostics(?:, actions)?\)/,
    );
  }
});

test("unneeded provider panels and V3 mode selectors are hidden without removing compatibility data", () => {
  for (const html of [desktopHtml, mobileHtml]) {
    assert.match(html, /class="[^"]*provider-panel[^"]*"[^>]*hidden/);
    assert.match(html, /class="[^"]*v2-provider-area[^"]*"[^>]*hidden/);
    assert.match(html, /class="[^"]*v2-model-card-grid-panel[^"]*"[^>]*hidden/);
  }
  assert.doesNotMatch(desktopHtml, /data-v3-workspace-entry/);
  assert.doesNotMatch(mobileHtml, /data-mobile-v3-workspace/);
  assert.match(desktopJs, /v3ProjectUsesProfessionalWorkspace\(v3State\.currentProject\) \? "professional" : "standard"/);
  assert.match(mobileJs, /mobileV3ProjectUsesProfessionalWorkspace\(project\)/);
  assert.match(desktopJs, /v3State\.workspaceMode = "standard";/);
  assert.match(mobileJs, /preserveV3Workspace: id\.startsWith\("v3-"\)/);
  assert.match(mobileJs, /activeId\?\.startsWith\("v3-"\) && !preserveV3Workspace/);
});

test("V2 metadata wraps and empty V3 feedback boxes stay hidden until populated", () => {
  assert.match(desktopCss, /\.v2-output-meta > strong\s*\{[^}]*white-space:\s*normal;[^}]*overflow-wrap:\s*anywhere;/s);
  assert.match(mobileCss, /\.v2-output-meta > strong\s*\{[^}]*white-space:\s*normal;[^}]*overflow-wrap:\s*anywhere;/s);
  assert.match(desktopHtml, /id="v3VisualAssetLibraryStatus"[^>]*hidden/);
  assert.match(desktopHtml, /id="v3VisualAssetCreateFeedback"[^>]*hidden/);
  assert.match(mobileHtml, /id="mobileV3VisualAssetCreateFeedback"[^>]*hidden/);
  assert.match(desktopJs, /v3VisualAssetCreateFeedback\.hidden = true;/);
  assert.match(mobileJs, /node\.hidden = !node\.textContent;/);
});
