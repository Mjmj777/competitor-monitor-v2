(() => {
  "use strict";

  const C = window.CM;
  const params = new URLSearchParams(location.search);
  const state = { data: null, item: null };

  const kv = (label, value) =>
    C.el("div", {}, C.el("dt", {}, label), C.el("dd", {}, value || "—"));

  const skpi = (label, value) =>
    C.el(
      "article",
      { class: "kpi-card" },
      C.el("span", { class: "kpi-card__label" }, label),
      C.el("strong", {}, String(value ?? 0))
    );

  function isSocialUrl(value) {
    if (!value) return false;
    try {
      const host = new URL(value, location.href).hostname.toLowerCase().replace(/^www\./, "");
      return ["instagram.com", "facebook.com", "m.facebook.com", "x.com", "twitter.com", "tiktok.com"]
        .some(h => host === h || host.endsWith(`.${h}`));
    } catch {
      return false;
    }
  }

  function socialIdentity(value) {
    if (!value) return "";
    try {
      const u = new URL(value, location.href);
      let host = u.hostname.toLowerCase().replace(/^www\./, "");
      if (host === "twitter.com") host = "x.com";
      if (host === "m.facebook.com") host = "facebook.com";
      const path = (u.pathname || "/").replace(/\/{2,}/g, "/").replace(/\/$/, "").toLowerCase() || "/";
      return `${host}${path}`;
    } catch {
      return String(value).trim().toLowerCase().replace(/\/$/, "");
    }
  }

  function socialMetrics(i) {
    const unique = new Map();
    const add = row => {
      if (!row?.link) return;
      const key = socialIdentity(row.link);
      if (!key) return;
      const current = unique.get(key) || {};
      unique.set(key, { ...current, ...row });
    };

    Object.entries(i.social_links || {}).forEach(([platform, raw]) => {
      const urls = Array.isArray(raw) ? raw : [raw];
      urls.filter(Boolean).forEach(url => add({
        id: `master:${platform}:${socialIdentity(url)}`,
        platform,
        title: `Official ${platform} post`,
        link: url,
        published_at: null,
        match_method: "master_link",
        source_origin: "master"
      }));
    });

    (i.linked_posts || []).forEach(post => add(post));
    const posts = [...unique.values()];
    const platforms = ["instagram", "x", "facebook", "tiktok"];
    const counts = Object.fromEntries(platforms.map(p => [p, posts.filter(x => x.platform === p).length]));
    const dated = posts.filter(p => p.published_at && !Number.isNaN(new Date(p.published_at).getTime()));
    dated.sort((a, b) => new Date(a.published_at) - new Date(b.published_at));
    const now = Date.now();
    return {
      posts,
      counts,
      total: posts.length,
      platformCount: platforms.filter(p => counts[p] > 0).length,
      first: dated[0]?.published_at || null,
      latest: dated.at(-1)?.published_at || null,
      posts7d: dated.filter(p => now - new Date(p.published_at).getTime() <= 7 * 86400000).length,
      posts30d: dated.filter(p => now - new Date(p.published_at).getTime() <= 30 * 86400000).length
    };
  }

  function evidenceLooksLikeLoginShell(value) {
    const s = String(value || "").toLowerCase();
    return [
      "instagram تسجيل الدخول",
      "instagram log in",
      "log into instagram",
      "© 2026 instagram from meta",
      "meta verified",
      "تحميل جهات الاتصال وغير المستخدمين"
    ].some(x => s.includes(x));
  }

  function addSourceLink(container, seen, label, url, kind = "official") {
    if (!url) return;
    let key = String(url).trim();
    if (!key || seen.has(key)) return;
    seen.add(key);

    container.appendChild(
      C.el(
        "a",
        {
          class: `social-link social-link--${kind}`,
          href: key,
          target: "_blank",
          rel: "noopener noreferrer"
        },
        label
      )
    );
  }

  function renderSources(i) {
    const links = document.getElementById("social-links");
    C.clear(links);
    const seen = new Set();

    addSourceLink(
      links,
      seen,
      C.t("officialCampaignUrl"),
      i.official_campaign_page_url,
      "official"
    );

    if (
      i.primary_official_source_url &&
      i.primary_official_source_url !== i.official_campaign_page_url
    ) {
      addSourceLink(
        links,
        seen,
        C.t("primarySourceUrl"),
        i.primary_official_source_url,
        isSocialUrl(i.primary_official_source_url) ? "social" : "official"
      );
    }

    const platformLabels = {
      instagram: "Instagram",
      x: "X",
      facebook: "Facebook",
      tiktok: "TikTok"
    };

    Object.entries(i.social_links || {})
      .forEach(([platform, raw]) => {
        const urls = (Array.isArray(raw) ? raw : [raw]).filter(Boolean);
        urls.forEach((url, index) =>
          addSourceLink(
            links,
            seen,
            `${platformLabels[platform] || C.t(platform)}${urls.length > 1 ? ` ${index + 1}` : ""}`,
            url,
            "social"
          )
        );
      });

    if (i.link && !seen.has(String(i.link).trim())) {
      addSourceLink(
        links,
        seen,
        isSocialUrl(i.link) ? C.t("openPost") : C.t("openOfficial"),
        i.link,
        isSocialUrl(i.link) ? "social" : "official"
      );
    }

    if (!links.children.length) {
      links.appendChild(C.el("div", { class: "empty-state" }, "—"));
    }
  }

  function renderVerification(i) {
    const sv = document.getElementById("source-verification");
    const v = i.source_verification || {};
    C.clear(sv);

    const sourceUrl = v.source_url || i.official_campaign_page_url || i.primary_official_source_url || i.link;
    const social =
      v.status === "verified_social" ||
      v.verification_method === "official_social_rss" ||
      (v.status === "verified" && isSocialUrl(sourceUrl));
    const website =
      v.status === "verified_website" ||
      v.verification_method === "official_website_page" ||
      (v.status === "verified" && sourceUrl && !isSocialUrl(sourceUrl));

    const label = website
      ? C.t("verifiedOfficialWebsite")
      : social
        ? C.t("verifiedOfficialSocial")
        : (i.review_required ? C.t("needsReview") : C.t("couldNotVerify"));

    sv.appendChild(
      C.el("div", { class: "verification-state" }, label),
      C.el(
        "p",
        {},
        v.checked_at
          ? `${C.t("lastCheck")}: ${C.formatDate(v.checked_at, true)}`
          : "—"
      )
    );

    if (v.source_changed) {
      sv.appendChild(C.el("div", { class: "conflict-banner" }, C.t("sourceConflict")));
    }

    if (
      website &&
      i.evidence_snapshot &&
      !evidenceLooksLikeLoginShell(i.evidence_snapshot)
    ) {
      sv.appendChild(C.el("div", { class: "evidence-snippet" }, i.evidence_snapshot));
    }

    if (sourceUrl) {
      sv.appendChild(
        C.el(
          "a",
          {
            class: "button button--ghost",
            href: sourceUrl,
            target: "_blank",
            rel: "noopener noreferrer"
          },
          isSocialUrl(sourceUrl) ? C.t("openPost") : C.t("openOfficial")
        )
      );
    }
  }

  function sameSourcePage(a, b) {
    if (!a || !b) return false;
    try {
      const normalize = value => {
        const u = new URL(value, location.href);
        u.hash = "";
        [ ...u.searchParams.keys() ]
          .filter(k => k.toLowerCase().startsWith("utm_"))
          .forEach(k => u.searchParams.delete(k));
        return `${u.hostname.toLowerCase().replace(/^www\./, "")}${u.pathname.replace(/\/$/, "").toLowerCase()}`;
      };
      return normalize(a) === normalize(b);
    } catch {
      return String(a).trim() === String(b).trim();
    }
  }

  function mediaItemForDisplay(i) {
    // Social/awareness records may display their own media.
    if (!["campaign", "merchant_offer"].includes(i.content_type)) return i;

    const m = i.media || {};
    const official = i.official_campaign_page_url || i.primary_official_source_url;

    // Campaign hero media must have explicit provenance from the exact official
    // campaign-detail webpage. Old/unproven/social images are intentionally hidden.
    if (
      !m.url ||
      m.source_type !== "official_website" ||
      !m.source_url ||
      !official ||
      isSocialUrl(m.source_url) ||
      !sameSourcePage(m.source_url, official)
    ) {
      return null;
    }

    return i;
  }

  function render() {
    const i = state.item;
    const d = state.data;
    const comp = C.byId(d.competitors)[i.competitor_id];

    document.getElementById("item-title").textContent = i.title || "—";
    document.getElementById("item-snippet").textContent = i.snippet || i.summary || "";
    document.getElementById("back-link").href = `competitor.html?id=${encodeURIComponent(i.competitor_id)}`;

    const ext = document.getElementById("external-link");
    const preferred = i.official_campaign_page_url || i.primary_official_source_url || i.link || "#";
    ext.href = preferred;
    ext.textContent = isSocialUrl(preferred) ? C.t("openPost") : C.t("openOfficial");

    const pills = document.getElementById("hero-pills");
    C.clear(pills);
    pills.append(
      C.pill(C.contentLabel(i), i.review_required ? "warning" : "info"),
      C.pill(C.categoryLabel(i, d), "neutral"),
      C.pill(C.competitorName(comp), "success")
    );

    const meta = document.getElementById("metadata");
    C.clear(meta);
    [
      [C.t("recordId"), i.record_id],
      [C.t("published"), C.formatDate(i.published_at)],
      [C.t("startDate"), C.formatDate(i.start_date)],
      [C.t("endDate"), C.formatDate(i.end_date)],
      [C.t("currentStatus"), i.current_status],
      [C.t("operationType"), i.operation_type],
      [C.t("mechanic"), i.mechanic],
      [C.t("eligibility"), i.eligibility],
      [C.t("terms"), i.terms_note],
      [C.t("lastReviewed"), C.formatDate(i.last_reviewed || i.last_live_verified_at, true)]
    ].forEach(x => meta.appendChild(kv(...x)));

    const cls = document.getElementById("classification");
    C.clear(cls);
    cls.append(C.pill(C.contentLabel(i), "info"), C.pill(C.categoryLabel(i, d), "neutral"));
    if (i.duplicate_candidate_id) {
      cls.appendChild(C.el("p", { class: "conflict-banner" }, `Possible duplicate: ${i.duplicate_candidate_id}`));
    }
    if (i.replacement_candidate_id) {
      cls.appendChild(C.el("p", {}, `Possible replacement of: ${i.replacement_candidate_id}`));
    }

    renderVerification(i);

    const oi = document.getElementById("offer-intelligence");
    C.clear(oi);
    oi.append(
      kv(C.t("mechanic"), (i.mechanic_tags || []).join(", ")),
      kv(C.t("corridors"), (i.corridors || []).join(", ")),
      kv(C.t("offerValues"), (i.offer_values || []).join(", "))
    );

    renderSources(i);

    const media = document.getElementById("media");
    C.clear(media);
    const mediaItem = mediaItemForDisplay(i);
    media.appendChild(
      (mediaItem && C.renderMedia(mediaItem)) ||
      C.el("div", { class: "empty-state" }, C.t("noMedia"))
    );

    renderSocial();
    renderTimeline();
    const editButton=document.getElementById("edit-item");
    editButton.hidden=!C.isAdmin();
    if(C.isAdmin()) editButton.onclick=()=>C.openEditor(i,d);
  }

  function renderSocial() {
    const i = state.item;
    const section = document.getElementById("social-analysis-section");
    if (!["campaign", "merchant_offer"].includes(i.content_type)) {
      section.hidden = true;
      return;
    }

    section.hidden = false;
    const metrics = socialMetrics(i);
    const grid = document.getElementById("social-kpis");
    C.clear(grid);
    [
      [C.t("totalPosts"), metrics.total],
      [C.t("platformsUsed"), metrics.platformCount],
      [C.t("posts7d"), metrics.posts7d],
      [C.t("posts30d"), metrics.posts30d],
      [C.t("firstPost"), C.formatDate(metrics.first)],
      [C.t("latestPost"), C.formatDate(metrics.latest)]
    ].forEach(x => grid.appendChild(skpi(...x)));

    const counts = metrics.counts;
    C.renderBarChart(
      document.getElementById("social-platform-chart"),
      ["instagram", "x", "facebook", "tiktok"].map(p => ({
        label: C.t(p),
        value: counts[p] || 0
      })),
      { keepZero: true }
    );

    const box = document.getElementById("linked-posts");
    C.clear(box);
    const posts = metrics.posts || [];
    if (!posts.length) {
      box.appendChild(C.el("div", { class: "empty-state" }, "—"));
      return;
    }

    posts.slice().reverse().forEach(p =>
      box.appendChild(
        C.el(
          "a",
          {
            class: "linked-post",
            href: p.link || "#",
            target: "_blank",
            rel: "noopener noreferrer"
          },
          C.el("strong", {}, C.t(p.platform || "website")),
          C.el("span", {}, p.title || "—"),
          C.el("small", {}, C.formatDate(p.published_at))
        )
      )
    );
  }

  function renderTimeline() {
    const box = document.getElementById("timeline");
    C.clear(box);
    const rows = (state.item.change_history || []).slice().reverse();
    if (!rows.length) {
      box.appendChild(C.el("div", { class: "empty-state" }, "—"));
      return;
    }

    rows.forEach(r =>
      box.appendChild(
        C.el(
          "article",
          { class: "timeline-row" },
          C.el("time", {}, C.formatDate(r.at, true)),
          C.el("strong", {}, r.type || "Update"),
          r.details ? C.el("small", {}, JSON.stringify(r.details)) : null
        )
      )
    );
  }

  async function init() {
    C.initLanguage();
    try {
      await C.loadAuth();
      state.data = await C.loadData();
      state.item = state.data.items.find(i => i.id === params.get("id"));
      if (!state.item) throw new Error("Item not found");

      document.getElementById("loading").hidden = true;
      document.getElementById("content").hidden = false;
      render();
      window.addEventListener("cm:language", () => location.reload());
    } catch (e) {
      document.getElementById("loading").hidden = true;
      C.showError(document.getElementById("error"), e);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
