import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const script = readFileSync(new URL("../../src_skeleton/app/static/v2-entry.js", import.meta.url), "utf8");

async function runEntry({ href, fetchImpl }) {
  const current = new URL(href);
  const events = [];
  const elements = [];
  const window = {
    location: {
      href: current.href,
      search: current.search,
      pathname: current.pathname,
      hash: current.hash,
      replace: (destination) => events.push({ type: "navigate", destination }),
    },
    history: {
      replaceState: (_state, _title, destination) => events.push({ type: "clean-url", destination }),
    },
    sessionStorage: { setItem: () => {} },
    navigator: { userAgent: "Desktop" },
    matchMedia: () => ({ matches: false }),
  };
  const document = {
    body: {
      replaceChildren: () => elements.splice(0),
      append: (element) => elements.push(element),
    },
    createElement: (tagName) => ({ tagName, textContent: "" }),
  };

  vm.runInNewContext(script, {
    window,
    document,
    fetch: async (...args) => {
      events.push({ type: "fetch", args });
      return fetchImpl(...args);
    },
    URL,
    URLSearchParams,
  });
  await new Promise((resolve) => setImmediate(resolve));
  return { events, elements };
}

test("exchanges the one-time ticket before opening V2 and removes it from the URL", async () => {
  const { events } = await runEntry({
    href: "https://alchemy.aiself.vip/go/v2?ticket=one-time-ticket",
    fetchImpl: async () => ({ ok: true }),
  });

  assert.equal(events[0].type, "clean-url");
  assert.equal(events[0].destination, "/go/v2");
  assert.equal(events[1].type, "fetch");
  assert.equal(events[1].args[0], "/api/v2/veyra/login");
  assert.deepEqual(JSON.parse(events[1].args[1].body), { ticket: "one-time-ticket" });
  assert.deepEqual(events[2], { type: "navigate", destination: "/?tab=v2" });
});

test("stops on ticket exchange failure instead of creating a login redirect loop", async () => {
  const { events, elements } = await runEntry({
    href: "https://alchemy.aiself.vip/go/v2?ticket=expired-ticket",
    fetchImpl: async () => ({ ok: false, status: 401 }),
  });

  assert.equal(events.some((event) => event.type === "navigate"), false);
  assert.equal(elements.length, 1);
  assert.match(elements[0].textContent, /Veyra 登录失败/);
});

test("keeps ordinary direct V2 entry behavior when no ticket is present", async () => {
  const { events } = await runEntry({
    href: "https://alchemy.aiself.vip/go/v2",
    fetchImpl: async () => assert.fail("must not exchange a missing ticket"),
  });

  assert.deepEqual(events, [{ type: "navigate", destination: "/?tab=v2" }]);
});
