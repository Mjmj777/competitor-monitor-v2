import { readFile } from "node:fs/promises";
import assert from "node:assert/strict";

const source = await readFile(new URL("../cloudflare-worker.js", import.meta.url), "utf8");
const { default: worker } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

let assetRequests = 0;
const env = {
  ADMIN_USERNAME: "admin",
  ADMIN_PASSWORD: "secret",
  VIEWER_USERNAME: "viewer",
  VIEWER_PASSWORD: "viewer-secret",
  SESSION_SECRET: "session-secret",
  GITHUB_ACTIONS_TOKEN: "github-token",
  ASSETS: {
    async fetch(request) {
      assetRequests += 1;
      assert.equal(new URL(request.url).pathname, "/data.json");
      return new Response('{"host":"cloudflare"}', {
        status: 200,
        headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=3600" },
      });
    },
  },
};

globalThis.fetch = async () => {
  throw new Error("Authenticated static files must not be fetched from GitHub Pages when ASSETS exists");
};

const loginResponse = await worker.fetch(new Request("https://competitor-monitors.com/__login", {
  method: "POST",
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
  body: new URLSearchParams({ username: "viewer", password: "viewer-secret", next: "/" }),
}), env);
assert.equal(loginResponse.status, 302);
const cookie = loginResponse.headers.get("set-cookie").split(";", 1)[0];

const response = await worker.fetch(new Request("https://competitor-monitors.com/data.json", {
  headers: { Cookie: cookie },
}), env);
assert.equal(response.status, 200);
assert.equal(await response.text(), '{"host":"cloudflare"}');
assert.equal(response.headers.get("cache-control"), "private, no-store");
assert.equal(response.headers.get("x-content-type-options"), "nosniff");
assert.equal(response.headers.get("x-frame-options"), "DENY");
assert.equal(assetRequests, 1);

const anonymous = await worker.fetch(new Request("https://competitor-monitors.com/data.json"), env);
assert.equal(anonymous.status, 200);
assert.match(await anonymous.text(), /Sign in/i);
assert.equal(assetRequests, 1);

console.log("Worker Cloudflare static-assets tests passed");
