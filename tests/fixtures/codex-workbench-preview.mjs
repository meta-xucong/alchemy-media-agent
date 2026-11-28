// A loopback test server. Fixtures never send traffic to an image provider.
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { extname, join } from "node:path";

const assets = fileURLToPath(new URL("../../src_skeleton/app/static/", import.meta.url));
const staticMime = { ".html": "text/html; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".jpg": "image/jpeg" };
const caseId = "case_example";
const example = { case_id: caseId, title: "Matcha Granola Ad Poster", category: "ad-creative",
  preview_url: "/api/v2/case-thumbnails/images/fixture/output.jpg", is_active: true };
const v2Image = await readFile(join(assets, "codex-lab-chrome-v1.jpg"));
const labImage = await readFile(join(assets, "codex-lab-copper-v1.jpg"));
const styles = [
  { id: "M001", display_name: "液态铬金属" },
  { id: "M002", display_name: "氧化铜绿锈" },
  { id: "M003", display_name: "黑漆莳绘" },
];
const byRun = new Map();
let v2Receipt, labReceipt;
const labPrefix = "/api/lab/rare-style-explorer";

function insert(product, payload) {
  const id = (product === "v2" ? "run_example_" : "lab_example_") + (byRun.size + 1);
  byRun.set(id, payload);
  return id;
}

const routes = async (req, res) => {
  const url = new URL(req.url, "http://127.0.0.1");
  const path = url.pathname;
  const json = (data, status = 200) => res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" }).end(JSON.stringify(data));
  const image = (bytes) => res.writeHead(200, { "Content-Type": "image/jpeg" }).end(bytes);
  const payload = async () => {
    let body = "";
    for await (const chunk of req) body += chunk.toString("utf8");
    return JSON.parse(body);
  };
  if (path === "/codex-workbench" || /^\/static\/codex-[a-z.0-9-]+$/.test(path)) {
    const file = path === "/codex-workbench" ? "codex-workbench.html" : path.split("/").at(-1);
    return res.writeHead(200, { "Content-Type": staticMime[extname(file)] }).end(await readFile(join(assets, file)));
  }
  if (path === "/api/v2/templates/page") return json({ items: [example], next_cursor: null });
  if (path === "/api/v2/prompt-cases/search") return json({ cases: [example] });
  if (path === "/api/v2/prompt-cases/" + caseId) return json(example);
  if (path.startsWith("/api/v2/case-thumbnails/")) return image(v2Image);
  if (path === labPrefix + "/styles") return json({ styles });
  if (req.method === "POST" && path === "/api/v2/creative/runs/async") {
    const body = await payload();
    if (!req.headers["idempotency-key"] || body.template_case_id !== caseId) return json({ error: "wrong case" }, 400);
    v2Receipt = insert("v2", body);
    return json({ run_id: v2Receipt, status: "planning" }, 202);
  }
  if (path === "/api/v2/creative/runs/" + v2Receipt) return json({
    run_id: v2Receipt, status: "completed", selected_cases: [example],
    generation_jobs: [{ outputs: [{ output_id: "out_example_v2", review: { decision: "needs_review", reasons: ["版面留白不足"] } }] }],
  });
  if (req.method === "POST" && path === labPrefix + "/sessions") {
    const body = await payload();
    if (body.selected_style_ids[0] !== "M002") return json({ error: "wrong style" }, 400);
    labReceipt = insert("lab", body);
    return json({ session: { id: labReceipt, status: "queued" } }, 202);
  }
  if (path === labPrefix + "/sessions/" + labReceipt) return json({
    session: { id: labReceipt, status: "completed", style_presets: [styles[1]],
      variants: [{ id: "variant_example", asset: { output_id: "out_example_lab" } }] },
    board: { status: "completed", groups: [{ cards: [{ variant_id: "variant_example",
      style_preset_id: "M002", style_name: styles[1].display_name, image_url: "/v1/outputs/out_example_lab/download" }] }] },
  });
  if (path === "/api/lab/outputs/out_example_lab/download" || path === "/api/lab/outputs/out_example_lab/preview") return image(labImage);
  if (path === "/api/v2/outputs/out_example_v2/download" || path === "/api/v2/image/history/out_example_v2/preview") return image(v2Image);
  if (path === "/test/receipts") return json(Object.fromEntries(byRun));
  return json({ error: "fixture_route_not_found" }, 404);
};

createServer((req, res) => { routes(req, res).catch(() => res.writeHead(500).end()); })
  .listen(18776, "127.0.0.1", () => console.log("http://127.0.0.1:18776/codex-workbench"));
