import { readFile } from "node:fs/promises";
import assert from "node:assert/strict";

const source = await readFile(new URL("../cloudflare-worker.js", import.meta.url), "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { default: worker } = await import(moduleUrl);

const env = {
  ADMIN_USERNAME: " admin ",
  ADMIN_PASSWORD: " secret ",
  VIEWER_USERNAME: " viewer ",
  VIEWER_PASSWORD: " viewer-secret ",
  SESSION_SECRET: " session-secret ",
  GITHUB_ACTIONS_TOKEN: " github-token ",
};

let requestId = "";
let busy = false;
globalThis.fetch = async (input, init = {}) => {
  const request = input instanceof Request ? input : new Request(input, init);
  if (request.url.includes("/actions/workflows/monitor.yml/runs")) {
    if (busy) return Response.json({ workflow_runs: [{ status: "in_progress", display_title: "Monitor all" }] });
    if (requestId) return Response.json({ workflow_runs: [{ status: "completed", conclusion: "success", display_title: `Monitor mobily-pay · ${requestId}`, updated_at: new Date().toISOString() }] });
    return Response.json({ workflow_runs: [] });
  }
  if (request.url.endsWith("/actions/workflows/monitor.yml/dispatches")) {
    const body = JSON.parse(await request.clone().text());
    requestId = body.inputs.request_id;
    assert.equal(body.inputs.competitor, "mobily-pay");
    return new Response(null, { status: 204 });
  }
  return new Response("origin", { status: 200, headers: { "Content-Type": "text/plain" } });
};

async function login(username, password) {
  const body = new URLSearchParams({ username, password, next: "/", remember: "on" });
  const response = await worker.fetch(new Request("https://competitor-monitors.com/__login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  }), env);
  assert.equal(response.status, 302);
  return response.headers.get("set-cookie").split(";", 1)[0];
}

const adminCookie = await login("admin", "secret");
const viewerCookie = await login("viewer", "viewer-secret");

const refresh = await worker.fetch(new Request("https://competitor-monitors.com/__refresh", {
  method: "POST",
  headers: { Cookie: adminCookie, "Content-Type": "application/json" },
  body: JSON.stringify({ competitor: "mobily-pay" }),
}), env);
assert.equal(refresh.status, 202);
const queued = await refresh.json();
assert.equal(queued.accepted, true);
assert.match(queued.request_id, /^[0-9a-f-]{36}$/i);

const status = await worker.fetch(new Request(`https://competitor-monitors.com/__refresh-status?request_id=${queued.request_id}`, {
  headers: { Cookie: adminCookie },
}), env);
assert.equal(status.status, 200);
assert.equal((await status.json()).conclusion, "success");

const viewerRefresh = await worker.fetch(new Request("https://competitor-monitors.com/__refresh", {
  method: "POST",
  headers: { Cookie: viewerCookie, "Content-Type": "application/json" },
  body: JSON.stringify({ competitor: "mobily-pay" }),
}), env);
assert.equal(viewerRefresh.status, 403);

requestId = "";
busy = true;
const duplicate = await worker.fetch(new Request("https://competitor-monitors.com/__refresh", {
  method: "POST",
  headers: { Cookie: adminCookie, "Content-Type": "application/json" },
  body: JSON.stringify({ competitor: "all" }),
}), env);
assert.equal(duplicate.status, 409);

console.log("Worker refresh tests passed");
