(() => {
  "use strict";

  const C = window.CM;
  const params = new URLSearchParams(location.search);
  const state = {
    data: null,
    competitor: null,
    tab: "campaign",
    visible: 40,
    socialPeriod: 7,
    socialPlatform: "",
    filters: { q: "", category: "", status: "", reviewReason: "" },
  };

  const CATEGORY_COLORS = {
    remittance: "#2457d6",
    musaned: "#7c3aed",
    sadad: "#0f766e",
    card: "#d97706",
    engagement: "#d94676",
    other: "#64748b",
  };
  const PLATFORM_COLORS = { instagram: "#d94676", facebook: "#1877f2", x: "#111827", tiktok: "#00a6a6" };

  const rows = () => state.data.items.filter((item) => item.competitor_id === state.competitor.id);
  const campaigns = () => C.activeCampaigns(rows());
  const merchants = () => C.activeMerchants(rows());
  const kpi = (label, value, detail, kind = "default") => C.el("article", { class: `kpi-card kpi-card--${kind}` }, C.el("span", { class: "kpi-card__label" }, label), C.el("strong", {}, String(value)), C.el("small", {}, detail));

  function ageInDays(value) {
    const parsed = new Date(value || 0);
    return Number.isNaN(parsed.getTime()) ? Number.POSITIVE_INFINITY : (Date.now() - parsed.getTime()) / 86400000;
  }

  function inAgeRange(value, fromDays, toDays) {
    const age = ageInDays(value);
    return age >= fromDays && age < toDays;
  }

  function socialDate(item) {
    return item.published_at || item.first_seen || item.last_changed;
  }

  function hero() {
    document.getElementById("competitor-name").textContent = C.competitorName(state.competitor);
    document.getElementById("competitor-summary").textContent = `${campaigns().length} ${C.t("activeCampaigns")} · ${merchants().length} ${C.t("merchantOffers")} · ${C.socialPosts(rows(), 7).length} ${C.t("socialPosts7d")}`;
    document.getElementById("website-url").href = state.competitor.website || "#";
    document.getElementById("offers-url").href = state.competitor.offers_url || "#";
    const switcher = document.getElementById("competitor-switcher");
    C.clear(switcher);
    state.data.competitors.forEach((competitor) => switcher.appendChild(C.el("option", { value: competitor.id, selected: competitor.id === state.competitor.id }, C.competitorName(competitor))));
    switcher.onchange = () => location.href = `competitor.html?id=${encodeURIComponent(switcher.value)}`;
  }

  function renderKpis() {
    const current = campaigns();
    const expiring = current.filter((item) => /Expiring/.test(item.current_status || ""));
    const review = rows().filter((item) => item.active !== false && item.review_required).length;
    const grid = document.getElementById("kpi-grid");
    C.clear(grid);
    const cards = [
      [C.t("activeCampaigns"), current.length, C.t("activeCampaignsDetail"), "primary"],
      [C.t("merchantPortfolio"), merchants().length, C.t("merchantPortfolioDetail"), "gold"],
      [C.t("remittanceCampaigns"), current.filter((item) => item.campaign_category === "remittance").length, C.t("remittance"), "blue"],
      [C.t("expiring30d"), expiring.length, C.t("expiryRisk"), expiring.length ? "danger" : "default"],
      [C.t("socialPosts7d"), C.socialPosts(rows(), 7).length, C.t("channelActivity7d"), "purple"],
    ];
    if (C.isAdmin()) cards.push([C.t("reviewRequired"), review, C.t("review"), review ? "warning" : "default"]);
    cards.forEach((card) => grid.appendChild(kpi(...card)));
  }

  function renderSocialChart() {
    const period = state.socialPeriod;
    const social = C.socialPosts(rows());
    const platformIds = state.socialPlatform ? [state.socialPlatform] : ["instagram", "facebook", "x", "tiktok"];
    const chartRows = platformIds.map((platform) => {
      const platformPosts = social.filter((item) => item.platform === platform);
      return {
        id: platform,
        label: C.t(platform),
        values: {
          current: platformPosts.filter((item) => inAgeRange(socialDate(item), 0, period)).length,
          previous: platformPosts.filter((item) => inAgeRange(socialDate(item), period, period * 2)).length,
        },
        colors: { current: PLATFORM_COLORS[platform], previous: "#cbd5e1" },
      };
    });
    chartRows.sort((a, b) => b.values.current - a.values.current || b.values.previous - a.values.previous);
    C.renderGroupedBarChart(document.getElementById("channel-chart"), chartRows, [
      { id: "current", label: C.t("currentPeriod"), color: C.competitorColor(state.competitor.id) },
      { id: "previous", label: C.t("previousPeriod"), color: "#cbd5e1" },
    ]);

    const current = chartRows.reduce((sum, item) => sum + item.values.current, 0);
    const previous = chartRows.reduce((sum, item) => sum + item.values.previous, 0);
    const delta = previous ? Math.round(((current - previous) / previous) * 100) : current ? null : 0;
    const trend = delta === null || delta > 0 ? "is-up" : delta < 0 ? "is-down" : "is-flat";
    const trendLabel = delta === null || delta > 0 ? C.t("comparisonUp") : delta < 0 ? C.t("comparisonDown") : C.t("comparisonFlat");
    const trendValue = delta === null ? `+${current}` : `${delta > 0 ? "+" : ""}${delta}%`;
    const summary = document.getElementById("competitor-social-comparison-summary");
    C.clear(summary);
    summary.append(
      C.el("span", {}, `${C.t("currentPeriod")}: ${current}`),
      C.el("span", {}, `${C.t("previousPeriod")}: ${previous}`),
      C.el("span", { class: trend }, `${trendLabel}: ${trendValue}`),
    );
  }

  function renderCharts() {
    const current = campaigns();
    const categories = C.countBy(current, (item) => item.campaign_category);
    C.renderBarChart(document.getElementById("category-chart"), state.data.categories.filter((category) => category.id !== "merchant").map((category) => ({ label: C.taxonomyName(category), value: categories.get(category.id) || 0, color: CATEGORY_COLORS[category.id] || "#64748b" })), { keepZero: true });

    const mechanics = C.countBy(current, (item) => item.mechanic_tags || []);
    C.renderBarChart(document.getElementById("mechanics-chart"), (state.data.mechanic_types || []).map((mechanic, index) => ({ label: C.taxonomyName(mechanic), value: mechanics.get(mechanic.id) || 0, color: ["#0f766e", "#2563eb", "#7c3aed", "#d97706", "#d94676", "#64748b"][index % 6] })), { keepZero: true });

    const allCampaignRecords = rows().filter((item) => item.content_type === "campaign");
    C.renderBarChart(document.getElementById("expiry-chart"), [
      { label: C.t("expiring7"), value: current.filter((item) => /≤7/.test(item.current_status || "")).length, color: "#dc2626" },
      { label: C.t("expiring30"), value: current.filter((item) => /8–30/.test(item.current_status || "")).length, color: "#f59e0b" },
      { label: C.t("noEndDate"), value: current.filter((item) => item.current_status === "End Date Not Stated").length, color: "#64748b" },
      { label: C.t("expiredStatus"), value: allCampaignRecords.filter((item) => (item.current_status === "Expired" || item.active === false) && inAgeRange(item.end_date || item.last_changed, 0, 30)).length, color: "#7f1d1d" },
    ], { keepZero: true, sort: false });

    renderSocialChart();
  }

  function renderMedia() {
    const box = document.getElementById("media-grid");
    C.clear(box);
    const media = C.socialPosts(rows()).filter((item) => item.media?.url).sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0)).slice(0, 12);
    if (!media.length) return box.appendChild(C.el("div", { class: "empty-state" }, C.t("noMedia")));
    media.forEach((item) => {
      const card = C.renderMediaCard(item, state.data);
      if (card) box.appendChild(card);
    });
  }

  function setupFilters() {
    const category = document.getElementById("category-filter");
    C.clear(category);
    category.appendChild(C.el("option", { value: "" }, C.t("all")));
    state.data.categories.forEach((item) => category.appendChild(C.el("option", { value: item.id }, C.taxonomyName(item))));
    const reason = document.getElementById("review-reason-filter");
    if (reason) {
      C.clear(reason);
      reason.appendChild(C.el("option", { value: "" }, C.t("all")));
      [...new Set(rows().flatMap((item) => item.review_reasons || []).filter(Boolean))].sort().forEach((value) => reason.appendChild(C.el("option", { value }, value.replaceAll("_", " "))));
    }
  }

  function tabMatch(item) {
    if (state.tab === "all") return true;
    if (state.tab === "campaign") return item.content_type === "campaign";
    if (state.tab === "merchant_offer") return item.content_type === "merchant_offer";
    if (state.tab === "posts") return item.source_type === "social";
    if (state.tab === "review") return item.review_required || item.content_type === "review";
    return true;
  }

  function filtered() {
    const query = state.filters.q.toLowerCase();
    return rows().filter((item) => item.active !== false && (C.isAdmin() || !(item.review_required || item.content_type === "review")) && tabMatch(item) && (!query || `${item.title || ""} ${item.snippet || ""}`.toLowerCase().includes(query)) && (!state.filters.category || item.campaign_category === state.filters.category) && (!state.filters.status || item.current_status === state.filters.status) && (!state.filters.reviewReason || (item.review_reasons || []).includes(state.filters.reviewReason)));
  }

  function renderList() {
    const result = filtered();
    const box = document.getElementById("item-list");
    const more = document.getElementById("load-more");
    document.getElementById("result-count").textContent = `${result.length} ${C.t("results")}`;
    C.clear(box);
    if (!result.length) {
      more.hidden = true;
      return box.appendChild(C.el("div", { class: "empty-state" }, C.t("noData")));
    }
    result.slice(0, state.visible).forEach((item) => box.appendChild(C.renderItemCard(item, state.data)));
    more.hidden = state.visible >= result.length;
  }

  function renderSources() {
    if (!C.isAdmin()) return;
    const all = (state.data.source_status || []).filter((status) => status.competitor_id === state.competitor.id);
    const box = document.getElementById("source-list");
    C.clear(box);
    all.forEach((status) => box.appendChild(C.sourceRow(status, state.data)));
    const discovery = all.filter((status) => ["website", "social"].includes(status.source_type));
    const ok = discovery.filter((status) => status.success).length;
    const summary = document.getElementById("source-summary");
    if (summary) summary.textContent = `${ok} ${C.t("healthy")} · ${discovery.length - ok} ${C.t("failed")}`;
  }

  function renderRefreshHistory() {
    if (!C.isAdmin()) return;
    const box = document.getElementById("refresh-history-list");
    if (!box) return;
    C.clear(box);
    const history = (state.data.refresh_history || []).filter((entry) => entry.competitor === "all" || entry.competitor === state.competitor.id).reverse().slice(0, 10);
    if (!history.length) return box.appendChild(C.el("div", { class: "empty-state empty-state--compact" }, C.t("noRefreshHistory")));
    history.forEach((entry) => box.appendChild(C.refreshHistoryRow(entry, state.data)));
  }

  function applyPermissions() {
    const admin = C.isAdmin();
    const add = document.getElementById("add-campaign");
    if (add) add.hidden = !admin;
    const exportButton = document.getElementById("export-edits");
    if (exportButton) exportButton.hidden = !admin;
    const health = document.getElementById("competitor-source-health");
    if (health) health.hidden = !admin;
    document.querySelectorAll("[data-admin-only]").forEach((node) => node.hidden = !admin);
  }

  function resetList() {
    state.visible = 40;
    renderList();
  }

  function bind() {
    document.getElementById("content-tabs").onclick = (event) => {
      const button = event.target.closest("button[data-type]");
      if (!button) return;
      state.tab = button.dataset.type;
      document.querySelectorAll("#content-tabs .tab").forEach((node) => node.classList.toggle("is-active", node === button));
      resetList();
    };
    document.getElementById("search").oninput = (event) => {
      state.filters.q = event.target.value;
      resetList();
    };
    for (const [id, key] of [["category-filter", "category"], ["status-filter", "status"], ["review-reason-filter", "reviewReason"]]) {
      const node = document.getElementById(id);
      if (node) node.onchange = (event) => {
        state.filters[key] = event.target.value;
        resetList();
      };
    }
    document.getElementById("clear-filters").onclick = () => {
      state.filters = { q: "", category: "", status: "", reviewReason: "" };
      ["search", "category-filter", "status-filter", "review-reason-filter"].forEach((id) => {
        const node = document.getElementById(id);
        if (node) node.value = "";
      });
      resetList();
    };
    document.getElementById("load-more").onclick = () => {
      state.visible += 40;
      renderList();
    };
    document.getElementById("competitor-social-period-filter").onchange = (event) => {
      state.socialPeriod = Number(event.target.value) === 30 ? 30 : 7;
      renderSocialChart();
    };
    document.getElementById("competitor-social-platform-filter").onchange = (event) => {
      state.socialPlatform = event.target.value;
      renderSocialChart();
    };
    const refresh = document.getElementById("refresh-competitor");
    if (refresh && C.isAdmin()) refresh.onclick = (event) => C.triggerRefresh(state.competitor.id, event.currentTarget);
    document.getElementById("export-edits").onclick = C.exportOverrides;
    const add = document.getElementById("add-campaign");
    if (add) add.onclick = () => C.openAddCampaign(state.data, state.competitor.id);
  }

  async function init() {
    C.initLanguage();
    try {
      await C.loadAuth();
      applyPermissions();
      state.data = await C.loadData();
      state.competitor = C.byId(state.data.competitors)[params.get("id")] || state.data.competitors[0];
      document.getElementById("loading").hidden = true;
      document.getElementById("content").hidden = false;
      hero();
      renderKpis();
      renderCharts();
      renderMedia();
      setupFilters();
      renderList();
      renderSources();
      renderRefreshHistory();
      bind();
      C.resumeRefresh();
      window.addEventListener("cm:language", () => location.reload());
    } catch (error) {
      document.getElementById("loading").hidden = true;
      C.showError(document.getElementById("error"), error);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
