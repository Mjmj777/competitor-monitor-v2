const ORIGIN = "https://mjmj777.github.io/competitor-monitor-v2";
const GITHUB_REPOSITORY = "Mjmj777/competitor-monitor-v2";
const GITHUB_WORKFLOW = "monitor.yml";
const GITHUB_REVIEW_WORKFLOW = "review.yml";
const WORKER_BUILD = "5.9.1";
const REFRESH_TARGETS = new Set([
  "all",
  "stc-bank",
  "barq",
  "mobily-pay",
  "tiqmo",
  "urpay",
  "alinma-pay",
]);

const COOKIE_NAME = "cm_session";

// 12 hours
const NORMAL_SESSION_SECONDS = 60 * 60 * 12;

// 30 days
const REMEMBER_SESSION_SECONDS = 60 * 60 * 24 * 30;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // ---------------------------------------------------------
    // Logout
    // ---------------------------------------------------------
    if (path === "/__logout") {
      return new Response(null, {
        status: 302,
        headers: {
          Location: "/",
          "Set-Cookie":
            `${COOKIE_NAME}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`,
        },
      });
    }

    // ---------------------------------------------------------
    // Login POST
    // ---------------------------------------------------------
    if (path === "/__login" && request.method === "POST") {
      return handleLogin(request, env);
    }

    // ---------------------------------------------------------
    // Read current authenticated session
    // Used by the website to determine Admin / Viewer permissions
    // ---------------------------------------------------------
    if (path === "/__session") {
      const session = await getSession(request, env);

      if (!session) {
        return jsonResponse(
          {
            authenticated: false,
          },
          401
        );
      }

      return jsonResponse({
        authenticated: true,
        username: session.username,
        role: session.role,
        expires_at: session.exp,
        worker_build: WORKER_BUILD,
      });
    }

    // ---------------------------------------------------------
    // Admin-only manual refresh
    // ---------------------------------------------------------
    if (path === "/__refresh") {
      const session = await getSession(request, env);
      return handleRefresh(request, env, session);
    }

    if (path === "/__refresh-status") {
      const session = await getSession(request, env);
      return handleRefreshStatus(request, env, session);
    }

    // Admin review decisions are persisted by a dedicated GitHub workflow.
    if (path === "/__review") {
      const session = await getSession(request, env);
      return handleReview(request, env, session);
    }

    if (path === "/__review-status") {
      const session = await getSession(request, env);
      return handleReviewStatus(request, env, session);
    }

    // ---------------------------------------------------------
    // Protect everything else
    // ---------------------------------------------------------
    const session = await getSession(request, env);

    if (!session) {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return new Response("Unauthorized", { status: 401 });
      }

      return loginPage(url.pathname + url.search);
    }

    // ---------------------------------------------------------
    // Proxy authenticated request to GitHub Pages
    // ---------------------------------------------------------
    return proxyToOrigin(request);
  },
};


// =============================================================
// LOGIN
// =============================================================

async function handleLogin(request, env) {
  try {
    const form = await request.formData();

    const username = String(form.get("username") || "").trim();
    const password = String(form.get("password") || "").trim();
    const remember = form.get("remember") === "on";

    // Important:
    // trim both user input AND Cloudflare secrets.
    const adminUser = String(env.ADMIN_USERNAME || "").trim();
    const adminPass = String(env.ADMIN_PASSWORD || "").trim();

    const viewerUser = String(env.VIEWER_USERNAME || "").trim();
    const viewerPass = String(env.VIEWER_PASSWORD || "").trim();

    let role = null;
    let authenticatedUsername = null;

    if (
      secureStringEqual(username, adminUser) &&
      secureStringEqual(password, adminPass) &&
      adminUser &&
      adminPass
    ) {
      role = "admin";
      authenticatedUsername = adminUser;
    } else if (
      secureStringEqual(username, viewerUser) &&
      secureStringEqual(password, viewerPass) &&
      viewerUser &&
      viewerPass
    ) {
      role = "viewer";
      authenticatedUsername = viewerUser;
    }

    if (!role) {
      return loginPage("/", true);
    }

    const maxAge = remember
      ? REMEMBER_SESSION_SECONDS
      : NORMAL_SESSION_SECONDS;

    const token = await createSessionToken(
      authenticatedUsername,
      role,
      maxAge,
      env.SESSION_SECRET
    );

    const target = safeRedirect(String(form.get("next") || "/"));

    return new Response(null, {
      status: 302,
      headers: {
        Location: target,
        "Set-Cookie":
          `${COOKIE_NAME}=${token}; ` +
          `Path=/; ` +
          `HttpOnly; ` +
          `Secure; ` +
          `SameSite=Lax; ` +
          `Max-Age=${maxAge}`,
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return loginPage("/", true);
  }
}


// =============================================================
// SESSION
// =============================================================

async function createSessionToken(username, role, maxAge, secret) {
  const signingSecret = String(secret || "").trim();
  if (!signingSecret) {
    throw new Error("SESSION_SECRET is missing");
  }

  const exp = Math.floor(Date.now() / 1000) + maxAge;

  const payload = {
    username,
    role,
    exp,
  };

  const encodedPayload = textToBase64Url(JSON.stringify(payload));
  const signature = await sign(encodedPayload, signingSecret);

  return `${encodedPayload}.${signature}`;
}


async function getSession(request, env) {
  try {
    const signingSecret = String(env.SESSION_SECRET || "").trim();
    if (!signingSecret) {
      return null;
    }
    const cookieHeader = request.headers.get("Cookie") || "";
    const cookies = parseCookies(cookieHeader);

    const token = cookies[COOKIE_NAME];

    if (!token) {
      return null;
    }

    const parts = token.split(".");

    if (parts.length !== 2) {
      return null;
    }

    const [encodedPayload, receivedSignature] = parts;

    const expectedSignature = await sign(
      encodedPayload,
      signingSecret
    );

    if (!secureStringEqual(receivedSignature, expectedSignature)) {
      return null;
    }

    const payload = JSON.parse(base64UrlToText(encodedPayload));

    if (!payload.exp || Math.floor(Date.now() / 1000) >= payload.exp) {
      return null;
    }

    if (payload.role !== "admin" && payload.role !== "viewer") {
      return null;
    }

    return payload;
  } catch (error) {
    return null;
  }
}


// =============================================================
// HMAC SIGNATURE
// =============================================================

async function sign(value, secret) {
  const encoder = new TextEncoder();

  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(String(secret || "")),
    {
      name: "HMAC",
      hash: "SHA-256",
    },
    false,
    ["sign"]
  );

  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(value)
  );

  return bytesToBase64Url(new Uint8Array(signature));
}


// =============================================================
// GITHUB PAGES PROXY
// =============================================================

async function proxyToOrigin(request) {
  const incomingUrl = new URL(request.url);

  // Keep the GitHub Pages project path:
  // /competitor-monitor-v2/
  const originUrl =
    ORIGIN +
    incomingUrl.pathname +
    incomingUrl.search;

  const headers = new Headers(request.headers);

  // Cloudflare authentication cookie should not
  // be forwarded to GitHub Pages.
  headers.delete("Cookie");
  headers.delete("Host");

  const init = {
    method: request.method,
    headers,
    redirect: "follow",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
  }

  const originResponse = await fetch(originUrl, init);

  const responseHeaders = new Headers(originResponse.headers);

  responseHeaders.set(
    "Cache-Control",
    "private, no-store"
  );

  return new Response(originResponse.body, {
    status: originResponse.status,
    statusText: originResponse.statusText,
    headers: responseHeaders,
  });
}


// =============================================================
// ADMIN REFRESH
// =============================================================

function githubHeaders(token) {
  return {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${token}`,
    "User-Agent": "competitor-monitor-auth-worker",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

async function workflowRuns(token) {
  const response = await fetch(
    `https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/workflows/${GITHUB_WORKFLOW}/runs?branch=main&per_page=30`,
    { headers: githubHeaders(token) }
  );
  if (!response.ok) {
    throw new Error(`GitHub Actions status request failed (${response.status})`);
  }
  const payload = await response.json();
  return Array.isArray(payload?.workflow_runs) ? payload.workflow_runs : [];
}

async function reviewWorkflowRuns(token) {
  const response = await fetch(
    `https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/workflows/${GITHUB_REVIEW_WORKFLOW}/runs?branch=main&per_page=100`,
    { headers: githubHeaders(token) }
  );
  if (!response.ok) {
    throw new Error(`GitHub review status request failed (${response.status})`);
  }
  const payload = await response.json();
  return Array.isArray(payload?.workflow_runs) ? payload.workflow_runs : [];
}

async function handleRefreshStatus(request, env, session) {
  if (request.method !== "GET") {
    return jsonResponse({ error: "method_not_allowed", message: "GET required" }, 405, { Allow: "GET" });
  }
  if (!session) {
    return jsonResponse({ error: "unauthorized", message: "Authentication required" }, 401);
  }
  if (session.role !== "admin") {
    return jsonResponse({ error: "forbidden", message: "Admin access required" }, 403);
  }
  const token = String(env.GITHUB_ACTIONS_TOKEN || "").trim();
  if (!token) {
    return jsonResponse({ error: "missing_github_token", message: "GITHUB_ACTIONS_TOKEN is not configured" }, 503);
  }
  const requestId = String(new URL(request.url).searchParams.get("request_id") || "").trim();
  if (!/^[A-Za-z0-9_-]{8,120}$/.test(requestId)) {
    return jsonResponse({ error: "invalid_request_id", message: "Invalid refresh request ID" }, 400);
  }
  try {
    const runs = await workflowRuns(token);
    const run = runs.find((item) => String(item?.display_title || "").includes(requestId));
    if (!run) {
      return jsonResponse({ found: false, request_id: requestId, status: "queued" }, 202);
    }
    return jsonResponse({
      found: true,
      request_id: requestId,
      status: run.status,
      conclusion: run.conclusion || null,
      updated_at: run.updated_at || null,
    });
  } catch (error) {
    return jsonResponse({ error: "github_status_failed", message: String(error?.message || error) }, 502);
  }
}

async function handleRefresh(request, env, session) {
  if (request.method !== "POST") {
    return jsonResponse(
      { error: "method_not_allowed", message: "POST required" },
      405,
      { Allow: "POST" }
    );
  }

  if (!session) {
    return jsonResponse(
      { error: "unauthorized", message: "Authentication required" },
      401
    );
  }

  if (session.role !== "admin") {
    return jsonResponse(
      { error: "forbidden", message: "Admin access required" },
      403
    );
  }

  const requestUrl = new URL(request.url);
  const origin = request.headers.get("Origin");
  if (origin && origin !== requestUrl.origin) {
    return jsonResponse(
      { error: "forbidden_origin", message: "Invalid request origin" },
      403
    );
  }

  if (!(request.headers.get("Content-Type") || "").toLowerCase().startsWith("application/json")) {
    return jsonResponse(
      { error: "unsupported_media_type", message: "JSON body required" },
      415
    );
  }

  let payload;
  try {
    payload = await request.json();
  } catch {
    return jsonResponse(
      { error: "invalid_json", message: "Invalid JSON body" },
      400
    );
  }

  const competitor = String(payload?.competitor || "").trim();
  if (!REFRESH_TARGETS.has(competitor)) {
    return jsonResponse(
      { error: "invalid_competitor", message: "Unknown competitor" },
      400
    );
  }

  const token = String(env.GITHUB_ACTIONS_TOKEN || "").trim();
  if (!token) {
    return jsonResponse(
      { error: "missing_github_token", message: "GITHUB_ACTIONS_TOKEN is not configured" },
      503
    );
  }

  try {
    const runs = await workflowRuns(token);
    const activeRun = runs.find((item) => item && item.status !== "completed");
    if (activeRun) {
      return jsonResponse(
        { error: "refresh_in_progress", message: "A monitoring refresh is already running" },
        409
      );
    }
  } catch (error) {
    return jsonResponse(
      { error: "github_status_failed", message: String(error?.message || error) },
      502
    );
  }

  const requestId = crypto.randomUUID();

  const githubResponse = await fetch(
    `https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/workflows/${GITHUB_WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: { ...githubHeaders(token), "Content-Type": "application/json" },
      body: JSON.stringify({
        ref: "main",
        inputs: { competitor, request_id: requestId },
      }),
    }
  );

  if (githubResponse.status !== 204) {
    return jsonResponse(
      {
        error: "github_dispatch_failed",
        message: `GitHub rejected the refresh request (${githubResponse.status})`,
      },
      502
    );
  }

  return jsonResponse(
    {
      accepted: true,
      competitor,
      request_id: requestId,
      message: "Refresh queued",
    },
    202
  );
}


// =============================================================
// ADMIN REVIEW
// =============================================================

const REVIEW_ACTIONS = new Set([
  "confirm_campaign",
  "confirm_merchant_offer",
  "confirm_merchant_offers_bulk",
  "group_campaign",
  "link_existing",
  "mark_not_campaign",
  "mark_awareness",
]);

function validateAdminJsonRequest(request, session) {
  if (!session) return jsonResponse({ error: "unauthorized", message: "Authentication required" }, 401);
  if (session.role !== "admin") return jsonResponse({ error: "forbidden", message: "Admin access required" }, 403);
  const requestUrl = new URL(request.url);
  const origin = request.headers.get("Origin");
  if (origin && origin !== requestUrl.origin) return jsonResponse({ error: "forbidden_origin", message: "Invalid request origin" }, 403);
  if (!(request.headers.get("Content-Type") || "").toLowerCase().startsWith("application/json")) {
    return jsonResponse({ error: "unsupported_media_type", message: "JSON body required" }, 415);
  }
  return null;
}

function validReviewPayload(payload) {
  if (!payload || !REVIEW_ACTIONS.has(String(payload.action || ""))) return "Unknown review action";
  const maxItems = payload.action === "confirm_merchant_offers_bulk" ? 200 : 50;
  if (!Array.isArray(payload.item_ids) || payload.item_ids.length < 1 || payload.item_ids.length > maxItems) return `Select between 1 and ${maxItems} items`;
  if (payload.item_ids.some((value) => typeof value !== "string" || !/^[A-Za-z0-9:._-]{4,240}$/.test(value))) return "Invalid item ID";
  if (payload.action === "link_existing" && !/^[A-Za-z0-9:._-]{4,240}$/.test(String(payload.target_campaign_id || ""))) return "A target campaign is required";
  for (const field of ["title", "summary", "campaign_category", "record_type", "start_date", "end_date", "official_source_url"]) {
    if (payload[field] != null && typeof payload[field] !== "string") return `Invalid ${field}`;
  }
  if (String(payload.title || "").length > 280 || String(payload.summary || "").length > 3000) return "Review text is too long";
  if (payload.official_source_url) {
    try {
      const source = new URL(payload.official_source_url);
      if (!new Set(["http:", "https:"]).has(source.protocol)) return "Invalid official source URL";
    } catch { return "Invalid official source URL"; }
  }
  return null;
}

async function handleReviewStatus(request, env, session) {
  if (request.method !== "GET") return jsonResponse({ error: "method_not_allowed", message: "GET required" }, 405, { Allow: "GET" });
  if (!session) return jsonResponse({ error: "unauthorized", message: "Authentication required" }, 401);
  if (session.role !== "admin") return jsonResponse({ error: "forbidden", message: "Admin access required" }, 403);
  const token = String(env.GITHUB_ACTIONS_TOKEN || "").trim();
  if (!token) return jsonResponse({ error: "missing_github_token", message: "GITHUB_ACTIONS_TOKEN is not configured" }, 503);
  const requestId = String(new URL(request.url).searchParams.get("request_id") || "").trim();
  if (!/^[A-Za-z0-9_-]{8,120}$/.test(requestId)) return jsonResponse({ error: "invalid_request_id", message: "Invalid review request ID" }, 400);
  try {
    const runs = await reviewWorkflowRuns(token);
    const run = runs.find((item) => String(item?.display_title || "").includes(requestId));
    if (!run) return jsonResponse({ found: false, request_id: requestId, status: "queued" }, 202);
    return jsonResponse({ found: true, request_id: requestId, status: run.status, conclusion: run.conclusion || null, updated_at: run.updated_at || null, run_url: run.html_url || null });
  } catch (error) {
    return jsonResponse({ error: "github_status_failed", message: String(error?.message || error) }, 502);
  }
}

async function handleReview(request, env, session) {
  if (request.method !== "POST") return jsonResponse({ error: "method_not_allowed", message: "POST required" }, 405, { Allow: "POST" });
  const rejected = validateAdminJsonRequest(request, session);
  if (rejected) return rejected;
  const length = Number(request.headers.get("Content-Length") || 0);
  if (length > 60_000) return jsonResponse({ error: "payload_too_large", message: "Review payload is too large" }, 413);
  let payload;
  try {
    const raw = await request.text();
    if (raw.length > 60_000) return jsonResponse({ error: "payload_too_large", message: "Review payload is too large" }, 413);
    payload = JSON.parse(raw);
  } catch {
    return jsonResponse({ error: "invalid_json", message: "Invalid JSON body" }, 400);
  }
  const invalid = validReviewPayload(payload);
  if (invalid) return jsonResponse({ error: "invalid_review", message: invalid }, 400);
  const token = String(env.GITHUB_ACTIONS_TOKEN || "").trim();
  if (!token) return jsonResponse({ error: "missing_github_token", message: "GITHUB_ACTIONS_TOKEN is not configured" }, 503);
  // GitHub's shared workflow concurrency group safely serializes monitor and review
  // writes. Do not reject a new Admin decision merely because an older run is queued
  // or waiting; that stale lock caused review actions to remain blocked indefinitely.
  const requestId = crypto.randomUUID();
  const encodedPayload = textToBase64Url(JSON.stringify(payload));
  const githubResponse = await fetch(
    `https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/workflows/${GITHUB_REVIEW_WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: { ...githubHeaders(token), "Content-Type": "application/json" },
      body: JSON.stringify({
        ref: "main",
        inputs: { request_id: requestId, reviewer: String(session.username || "admin").slice(0, 100), payload: encodedPayload },
      }),
    }
  );
  if (githubResponse.status !== 204) {
    return jsonResponse({ error: "github_dispatch_failed", message: `GitHub rejected the review request (${githubResponse.status})` }, 502);
  }
  return jsonResponse({ accepted: true, request_id: requestId, message: "Review queued" }, 202);
}


// =============================================================
// LOGIN PAGE
// =============================================================

function loginPage(next = "/", invalid = false) {
  const safeNext = safeRedirect(next);

  const errorMessage = invalid
    ? `
      <div class="error">
        Incorrect username or password.
      </div>
    `
    : "";

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
  >

  <title>Competitor Intelligence Monitor</title>

  <style>
    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      font-family:
        Inter,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
      background:
        radial-gradient(
          circle at top,
          #1b2738 0%,
          #101722 40%,
          #080c12 100%
        );
      color: #ffffff;
    }

    .card {
      width: 100%;
      max-width: 420px;
      padding: 36px;
      border-radius: 18px;
      background: rgba(18, 25, 36, 0.96);
      border: 1px solid rgba(255,255,255,0.08);
      box-shadow: 0 24px 60px rgba(0,0,0,0.38);
    }

    .eyebrow {
      margin-bottom: 12px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 1.6px;
      text-transform: uppercase;
      color: #8ea0b7;
    }

    h1 {
      margin: 0 0 8px;
      font-size: 25px;
      line-height: 1.25;
    }

    .subtitle {
      margin: 0 0 28px;
      color: #98a7ba;
      font-size: 14px;
      line-height: 1.6;
    }

    label {
      display: block;
      margin-bottom: 8px;
      font-size: 13px;
      font-weight: 600;
      color: #d6deea;
    }

    input[type="text"],
    input[type="password"] {
      width: 100%;
      height: 46px;
      margin-bottom: 18px;
      padding: 0 14px;
      border-radius: 10px;
      border: 1px solid #303b4c;
      background: #0d131d;
      color: #ffffff;
      outline: none;
      font-size: 14px;
    }

    input[type="text"]:focus,
    input[type="password"]:focus {
      border-color: #7185a1;
    }

    .remember {
      display: flex;
      align-items: center;
      gap: 9px;
      margin: 2px 0 22px;
      font-size: 13px;
      color: #b8c3d1;
    }

    .remember input {
      margin: 0;
    }

    button {
      width: 100%;
      height: 46px;
      border: 0;
      border-radius: 10px;
      background: #ffffff;
      color: #0c1119;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
    }

    button:hover {
      opacity: 0.92;
    }

    .error {
      margin-bottom: 20px;
      padding: 12px 14px;
      border-radius: 9px;
      background: rgba(211, 64, 64, 0.14);
      border: 1px solid rgba(255, 91, 91, 0.3);
      color: #ffb0b0;
      font-size: 13px;
    }

    .footer {
      margin-top: 22px;
      text-align: center;
      font-size: 11px;
      color: #66768a;
    }
  </style>
</head>

<body>
  <div class="card">

    <div class="eyebrow">
      Secure Access
    </div>

    <h1>
      Competitor Intelligence Monitor
    </h1>

    <p class="subtitle">
      Sign in to access the monitoring dashboard.
    </p>

    ${errorMessage}

    <form method="POST" action="/__login">

      <input
        type="hidden"
        name="next"
        value="${escapeHtml(safeNext)}"
      >

      <label for="username">
        Username
      </label>

      <input
        id="username"
        name="username"
        type="text"
        autocomplete="username"
        required
      >

      <label for="password">
        Password
      </label>

      <input
        id="password"
        name="password"
        type="password"
        autocomplete="current-password"
        required
      >

      <label class="remember">
        <input
          type="checkbox"
          name="remember"
        >
        Remember me
      </label>

      <button type="submit">
        Sign in
      </button>

    </form>

    <div class="footer">
      Authorized users only
    </div>

  </div>
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=UTF-8",
      "Cache-Control": "no-store",
      "X-Frame-Options": "DENY",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "same-origin",
    },
  });
}


// =============================================================
// HELPERS
// =============================================================

function parseCookies(cookieHeader) {
  const result = {};

  for (const part of cookieHeader.split(";")) {
    const index = part.indexOf("=");

    if (index === -1) continue;

    const key = part.slice(0, index).trim();
    const value = part.slice(index + 1).trim();

    if (key) {
      result[key] = value;
    }
  }

  return result;
}


function safeRedirect(value) {
  const target = String(value || "/");

  // Only allow redirects inside our own site.
  if (!target.startsWith("/") || target.startsWith("//")) {
    return "/";
  }

  if (
    target.startsWith("/__login") ||
    target.startsWith("/__logout")
  ) {
    return "/";
  }

  return target;
}


function jsonResponse(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=UTF-8",
      "Cache-Control": "no-store",
      ...extraHeaders,
    },
  });
}


function textToBase64Url(text) {
  return bytesToBase64Url(
    new TextEncoder().encode(text)
  );
}


function bytesToBase64Url(bytes) {
  let binary = "";

  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }

  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}


function base64UrlToText(value) {
  let base64 = value
    .replace(/-/g, "+")
    .replace(/_/g, "/");

  while (base64.length % 4) {
    base64 += "=";
  }

  const binary = atob(base64);

  const bytes = new Uint8Array(binary.length);

  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }

  return new TextDecoder().decode(bytes);
}


function secureStringEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string") {
    return false;
  }

  if (a.length !== b.length) {
    return false;
  }

  let result = 0;

  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }

  return result === 0;
}


function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
