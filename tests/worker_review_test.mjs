import { readFile } from "node:fs/promises";
import assert from "node:assert/strict";

const source = await readFile(new URL("../cloudflare-worker.js", import.meta.url), "utf8");
const { default: worker } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const env = { ADMIN_USERNAME: "admin", ADMIN_PASSWORD: "secret", VIEWER_USERNAME: "viewer", VIEWER_PASSWORD: "viewer-secret", SESSION_SECRET: "session-secret", GITHUB_ACTIONS_TOKEN: "github-token" };
let requestId = "";
let dispatchedPayload = null;
globalThis.fetch = async (input, init = {}) => {
  const request = input instanceof Request ? input : new Request(input, init);
  if (request.url.includes("/actions/workflows/review.yml/runs")) {
    return Response.json({ workflow_runs: requestId ? [{ status: "completed", conclusion: "success", display_title: `Admin review · ${requestId}`, updated_at: new Date().toISOString() }] : [] });
  }
  if (request.url.endsWith("/actions/workflows/review.yml/dispatches")) {
    const body = JSON.parse(await request.clone().text()); requestId = body.inputs.request_id;
    assert.equal(body.inputs.reviewer, "admin");
    const encoded = body.inputs.payload.replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(Buffer.from(encoded, "base64").toString("utf8"));
    dispatchedPayload = payload;
    return new Response(null, { status: 204 });
  }
  return new Response("origin", { status: 200 });
};

async function login(username, password) {
  const response = await worker.fetch(new Request("https://competitor-monitors.com/__login", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ username, password, next: "/" }) }), env);
  assert.equal(response.status, 302); return response.headers.get("set-cookie").split(";", 1)[0];
}

const admin = await login("admin", "secret"), viewer = await login("viewer", "viewer-secret");
const reviewPayload = { action: "group_campaign", item_ids: ["post:barq:x:one", "post:barq:x:two"], record_type: "campaign", title: "One campaign", official_source_url: "https://x.com/barq/status/1" };
const queuedResponse = await worker.fetch(new Request("https://competitor-monitors.com/__review", { method: "POST", headers: { Cookie: admin, "Content-Type": "application/json" }, body: JSON.stringify(reviewPayload) }), env);
assert.equal(queuedResponse.status, 202); const queued = await queuedResponse.json(); assert.match(queued.request_id, /^[0-9a-f-]{36}$/i);
const status = await worker.fetch(new Request(`https://competitor-monitors.com/__review-status?request_id=${queued.request_id}`, { headers: { Cookie: admin } }), env);
assert.equal(status.status, 200); assert.equal((await status.json()).conclusion, "success");
assert.equal(dispatchedPayload.action, "group_campaign"); assert.equal(dispatchedPayload.item_ids.length, 2);
const mergePayload = { action: "merge_campaigns", item_ids: ["campaign:alinma:duplicate"], target_campaign_id: "campaign:alinma:primary" };
const mergeResponse = await worker.fetch(new Request("https://competitor-monitors.com/__review", { method: "POST", headers: { Cookie: admin, "Content-Type": "application/json" }, body: JSON.stringify(mergePayload) }), env);
assert.equal(mergeResponse.status, 202); assert.equal(dispatchedPayload.action, "merge_campaigns"); assert.equal(dispatchedPayload.target_campaign_id, "campaign:alinma:primary");
const denied = await worker.fetch(new Request("https://competitor-monitors.com/__review", { method: "POST", headers: { Cookie: viewer, "Content-Type": "application/json" }, body: JSON.stringify(reviewPayload) }), env);
assert.equal(denied.status, 403);
const invalid = await worker.fetch(new Request("https://competitor-monitors.com/__review", { method: "POST", headers: { Cookie: admin, "Content-Type": "application/json" }, body: JSON.stringify({ action: "group_campaign", item_ids: ["bad id"] }) }), env);
assert.equal(invalid.status, 400);

console.log("Worker Admin review tests passed");
