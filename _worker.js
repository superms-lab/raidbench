const ANALYTICS_PAGEVIEW_PATH = "/api/analytics/pageview";
const ANALYTICS_EVENT_PATH = "/api/analytics/event";
const API_PREFIX = "/api/";
const ORIGIN_PREFIX = "/__raidbench/app";
const RETIRED_DRAFT_PREFIX = "/draft-review/";
const ALLOWED_HOSTS = new Set(["raidbench.com", "www.raidbench.com"]);
const ALLOWED_ORIGINS = new Set(["https://raidbench.com", "https://www.raidbench.com"]);
const ALLOWED_EVENTS = new Set([
  "account_auth_submit",
  "account_auth_success",
  "answer_submit",
  "answer_ready",
  "answer_held",
  "break_even_calculated",
  "button_click",
  "calculator_ready",
  "checkout_redirect",
  "checkout_start",
  "credit_consent",
  "cta_click",
  "embed_full_route_click",
  "guide_link_click",
  "live_account_cta_click",
  "payment_capture_success",
  "raid_add_target",
  "raid_data_download",
  "raid_plan_share_copy",
  "raid_remove_target",
  "raid_reset",
  "raid_shared_route_open",
  "upkeep_input_change",
  "widget_embed_code_copy",
]);

function response(status, body = null) {
  const headers = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
  };

  if (body === null) return new Response(null, { status, headers });
  headers["Content-Type"] = "application/json; charset=utf-8";
  return new Response(JSON.stringify(body), { status, headers });
}

function normalizePath(value) {
  if (typeof value !== "string" || value.length > 240) return null;

  try {
    const pathname = new URL(value, "https://raidbench.com").pathname;
    if (!/^\/[A-Za-z0-9%_./-]*$/.test(pathname)) return null;
    return pathname.slice(0, 200) || "/";
  } catch {
    return null;
  }
}

function normalizeReferrerHost(value) {
  if (value === "direct" || value === "internal") return value;
  if (typeof value !== "string") return "direct";
  const cleaned = value.toLowerCase().replace(/[^a-z0-9.-]/g, "").slice(0, 120);
  return cleaned || "direct";
}

function normalizeDimension(value, fallback, maxLength = 80) {
  if (typeof value !== "string") return fallback;
  const cleaned = value.toLowerCase().replace(/[^a-z0-9._-]/g, "_").replace(/_+/g, "_").slice(0, maxLength);
  return cleaned || fallback;
}

function analyticsRequestAllowed(request) {
  const url = new URL(request.url);
  if (!ALLOWED_HOSTS.has(url.hostname.toLowerCase())) return false;
  const origin = request.headers.get("Origin");
  return !origin || ALLOWED_ORIGINS.has(origin);
}

async function recordPageView(request, env) {
  const url = new URL(request.url);
  if (!ALLOWED_HOSTS.has(url.hostname.toLowerCase())) return response(204);
  if (request.method !== "POST") return response(405, { error: "method_not_allowed" });

  const origin = request.headers.get("Origin");
  if (origin && !ALLOWED_ORIGINS.has(origin)) return response(403, { error: "origin_not_allowed" });

  const contentLength = Number(request.headers.get("Content-Length") || 0);
  if (contentLength > 3072) return response(413, { error: "payload_too_large" });
  if (!env.ANALYTICS_DB) return response(503, { error: "analytics_unavailable" });

  let payload;
  try {
    payload = await request.json();
  } catch {
    return response(400, { error: "invalid_json" });
  }

  const path = normalizePath(payload.path);
  if (!path) return response(400, { error: "invalid_path" });

  const day = new Date().toISOString().slice(0, 10);
  const updatedAt = new Date().toISOString();
  const referrerHost = normalizeReferrerHost(payload.referrerHost);
  const source = normalizeDimension(payload.source, referrerHost);
  const medium = normalizeDimension(payload.medium, referrerHost === "direct" ? "none" : "referral");
  const campaign = normalizeDimension(payload.campaign, "none", 100);
  const countryValue = String(request.cf?.country || "XX").toUpperCase();
  const country = /^[A-Z]{2}$/.test(countryValue) ? countryValue : "XX";

  const insert = env.ANALYTICS_DB.prepare(
    `INSERT INTO page_views (day, path, referrer_host, country, views, updated_at)
     VALUES (?, ?, ?, ?, 1, ?)
     ON CONFLICT(day, path, referrer_host, country)
     DO UPDATE SET views = views + 1, updated_at = excluded.updated_at`,
  ).bind(day, path, referrerHost, country, updatedAt);
  const acquisitionInsert = env.ANALYTICS_DB.prepare(
    `INSERT INTO acquisition_page_views (day, path, source, medium, campaign, country, views, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, 1, ?)
     ON CONFLICT(day, path, source, medium, campaign, country)
     DO UPDATE SET views = views + 1, updated_at = excluded.updated_at`,
  ).bind(day, path, source, medium, campaign, country, updatedAt);
  const cleanup = env.ANALYTICS_DB.prepare(
    "DELETE FROM page_views WHERE day < date('now', '-400 days')",
  );
  const acquisitionCleanup = env.ANALYTICS_DB.prepare(
    "DELETE FROM acquisition_page_views WHERE day < date('now', '-400 days')",
  );

  await env.ANALYTICS_DB.batch([insert, acquisitionInsert, cleanup, acquisitionCleanup]);
  return response(204);
}

async function recordConversionEvent(request, env) {
  const url = new URL(request.url);
  if (!ALLOWED_HOSTS.has(url.hostname.toLowerCase())) return response(204);
  if (request.method !== "POST") return response(405, { error: "method_not_allowed" });
  if (!analyticsRequestAllowed(request)) return response(403, { error: "origin_not_allowed" });

  const contentLength = Number(request.headers.get("Content-Length") || 0);
  if (contentLength > 3072) return response(413, { error: "payload_too_large" });
  if (!env.ANALYTICS_DB) return response(503, { error: "analytics_unavailable" });

  let payload;
  try {
    payload = await request.json();
  } catch {
    return response(400, { error: "invalid_json" });
  }

  const eventName = typeof payload.eventName === "string" ? payload.eventName : "";
  if (!ALLOWED_EVENTS.has(eventName)) return response(400, { error: "invalid_event" });
  const pagePath = normalizePath(payload.pagePath);
  if (!pagePath) return response(400, { error: "invalid_path" });

  const day = new Date().toISOString().slice(0, 10);
  const updatedAt = new Date().toISOString();
  const countryValue = String(request.cf?.country || "XX").toUpperCase();
  const country = /^[A-Z]{2}$/.test(countryValue) ? countryValue : "XX";
  const source = normalizeDimension(payload.source, "direct");
  const medium = normalizeDimension(payload.medium, "none");
  const campaign = normalizeDimension(payload.campaign, "none", 100);

  const insert = env.ANALYTICS_DB.prepare(
    `INSERT INTO conversion_events (day, event_name, page_path, source, medium, campaign, country, events, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
     ON CONFLICT(day, event_name, page_path, source, medium, campaign, country)
     DO UPDATE SET events = events + 1, updated_at = excluded.updated_at`,
  ).bind(day, eventName, pagePath, source, medium, campaign, country, updatedAt);
  const cleanup = env.ANALYTICS_DB.prepare(
    "DELETE FROM conversion_events WHERE day < date('now', '-400 days')",
  );

  await env.ANALYTICS_DB.batch([insert, cleanup]);
  return response(204);
}

async function proxyCustomerApi(request, env) {
  if (!env.RAIDBENCH_ORIGIN_URL || !env.RAIDBENCH_ORIGIN_KEY) {
    return response(503, { error: "customer_service_unavailable" });
  }

  const publicUrl = new URL(request.url);
  if (!ALLOWED_HOSTS.has(publicUrl.hostname.toLowerCase())) {
    return response(403, { error: "host_not_allowed" });
  }

  let origin;
  try {
    origin = new URL(env.RAIDBENCH_ORIGIN_URL);
  } catch {
    return response(503, { error: "customer_service_unavailable" });
  }
  if (origin.protocol !== "https:") {
    return response(503, { error: "customer_service_unavailable" });
  }

  origin.pathname = `${ORIGIN_PREFIX}${publicUrl.pathname}`;
  origin.search = publicUrl.search;
  const headers = new Headers(request.headers);
  headers.set("X-RaidBench-Origin-Key", env.RAIDBENCH_ORIGIN_KEY);
  headers.set("X-RaidBench-Public-Host", publicUrl.hostname.toLowerCase());

  const upstream = await fetch(origin.toString(), {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
    redirect: "manual",
  });
  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.set("Cache-Control", "no-store");
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith(RETIRED_DRAFT_PREFIX)) {
      return new Response("This Reddit draft workflow has been withdrawn.", {
        status: 410,
        headers: {
          "Cache-Control": "private, no-store",
          "Content-Type": "text/plain; charset=utf-8",
          "X-Content-Type-Options": "nosniff",
          "X-Robots-Tag": "noindex, nofollow, noarchive",
        },
      });
    }

    if (url.pathname === ANALYTICS_PAGEVIEW_PATH) {
      try {
        return await recordPageView(request, env);
      } catch (error) {
        console.error("RaidBench analytics write failed", error instanceof Error ? error.message : "unknown");
        return response(503, { error: "analytics_unavailable" });
      }
    }

    if (url.pathname === ANALYTICS_EVENT_PATH) {
      try {
        return await recordConversionEvent(request, env);
      } catch (error) {
        console.error("RaidBench conversion analytics write failed", error instanceof Error ? error.message : "unknown");
        return response(503, { error: "analytics_unavailable" });
      }
    }

    if (url.pathname.startsWith(API_PREFIX)) {
      try {
        return await proxyCustomerApi(request, env);
      } catch (error) {
        console.error("RaidBench customer API proxy failed", error instanceof Error ? error.message : "unknown");
        return response(503, { error: "customer_service_unavailable" });
      }
    }

    return env.ASSETS.fetch(request);
  },
};
