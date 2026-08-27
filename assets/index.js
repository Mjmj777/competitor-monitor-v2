(() => {
  "use strict";

  const C = window.CM;
  const state = {
    data: null,
    tab: "campaign",
    visible: 40,
    campaignChangePeriod: 30,
    socialPeriod: 7,
    socialPlatform: "",
    marketEventFilter: "",
    filters: { q: "", competitor: "", category: "", source: "", reviewReason: "" },
  };

  const CATEGORY_COLORS = {
    remittance: "#2457d6",
    musaned: "#7c3aed",
    sadad: "#0f766e",
    card: "#d97706",
    engagement: "#d94676",
    other: "#64748b",
  };

  const kpi = (label, value, detail, kind = "default") =>
    C.el(
      "article",
      { class: `kpi-card kpi-card--${kind}` },
      C.el("span", { class: "kpi-card__label" }, label),
      C.el("strong", {}, String(value)),
      C.el("small", {}, detail),
    );

  function campaigns() {
    return C.activeCampaigns(state.data.items);
  }

  function merchants() {
    return C.activeMerchants(state.data.items);
  }

  function validDate(value) {
    const parsed = new Date(value || 0);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function ageInDays(value) {
    const parsed = validDate(value);
    return parsed ? (Date.now() - parsed.getTime()) / 86400000 : Number.POSITIVE_INFINITY;
  }

  function inAgeRange(value, fromDays, toDays) {
    const age = ageInDays(value);
    return age >= fromDays && age < toDays;
  }

  function socialDate(item) {
    return item.published_at || item.first_seen || item.last_changed;
  }

  function renderKpis() {
    const s = state.data.stats || {};
    const grid = document.getElementById("kpi-grid");
    C.clear(grid);
    const expiring7 = campaigns().filter((item) => {
      const end = validDate(item.end_date);
      const days = end ? (end.getTime() - Date.now()) / 86400000 : -1;
      return days >= 0 && days <= 7;
    }).length;
    const rows = [
      [C.t("activeCampaigns"), s.active_campaigns || campaigns().length, C.t("activeCampaignsDetail"), "primary"],
      [C.t("merchantPortfolio"), s.merchant_offers || merchants().length, C.t("merchantPortfolioDetail"), "gold"],
      [C.t("remittanceCampaigns"), s.remittance_campaigns || 0, C.t("remittance"), "blue"],
      [C.t("upcomingExpiries7d"), expiring7, C.t("expiryRisk"), expiring7 ? "danger" : "default"],
      [C.t("socialPosts7d"), s.social_posts_7d || 0, C.t("channelActivity7d"), "purple"],
    ];
    if (C.isAdmin()) {
      rows.push([C.t("reviewRequired"), s.review_required || 0, C.t("review"), s.review_required ? "warning" : "default"]);
    }
    rows.forEach((row) => grid.appendChild(kpi(...row)));
  }

  function summaryCard(title, content, wide = false) {
    const card = C.el("article", { class: `summary-card${wide ? " summary-card--wide" : ""}` }, C.el("h3", {}, title));
    if (Array.isArray(content)) card.appendChild(C.el("ul", {}, content.map((item) => C.el("li", {}, item))));
    else card.appendChild(C.el("p", {}, content || "—"));
    return card;
  }

  function renderSummary() {
    const summary = state.data.ai_summary || {};
    const box = document.getElementById("ai-summary");
    C.clear(box);
    if (summary.executive_view) {
      box.append(
        summaryCard(C.t("executiveView"), summary.executive_view, true),
        summaryCard(C.t("keyMarketDevelopments"), summary.key_developments || []),
        summaryCard(C.t("managementAttention"), summary.management_attention || []),
        summaryCard(C.t("recommendedActions"), summary.recommended_actions || []),
        summaryCard(C.t("portfolioInsight"), summary.portfolio_insight || ""),
      );
      return;
    }
    // Backward compatibility while a newly deployed frontend waits for the next data refresh.
    box.append(
      summaryCard(C.t("whatChanged"), summary.what_changed || []),
      summaryCard(C.t("whyMatters"), summary.why_it_matters || []),
      summaryCard(C.t("managementTakeaway"), summary.management_takeaway || "", true),
    );
    const categories = (summary.category_snapshot || []).map((item) => `${item.category}: ${item.summary}`);
    if (categories.length) box.append(summaryCard(C.t("categorySnapshot"), categories, true));
  }

  function selectTab(tab) {
    state.tab = tab;
    document.querySelectorAll("#content-tabs .tab").forEach((node) => node.classList.toggle("is-active", node.dataset.type === tab));
  }

  function applyChartFilters(competitor = "", category = "", tab = "campaign") {
    state.marketEventFilter = "";
    state.filters.competitor = competitor;
    state.filters.category = category;
    const competitorSelect = document.getElementById("competitor-filter");
    const categorySelect = document.getElementById("category-filter");
    if (competitorSelect) competitorSelect.value = competitor;
    if (categorySelect) categorySelect.value = category;
    selectTab(tab);
    resetList();
    document.getElementById("content-tabs")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function applyMarketEventFilter(competitor, eventType) {
    state.marketEventFilter = eventType;
    state.filters.competitor = competitor;
    state.filters.category = "";
    document.getElementById("competitor-filter").value = competitor;
    document.getElementById("category-filter").value = "";
    selectTab("campaign");
    resetList();
    document.getElementById("content-tabs")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function campaignChangeValues(competitorId) {
    const records = state.data.items.filter((item) => item.content_type === "campaign" && item.competitor_id === competitorId);
    const period = state.campaignChangePeriod;
    return {
      new: records.filter((item) => !item.review_required && inAgeRange(item.market_launch_date, 0, period)).length,
      updated: records.filter((item) => inAgeRange(item.market_last_changed, 0, period)).length,
      expired: records.filter((item) => item.active === false && inAgeRange(item.market_expiry_date || item.end_date, 0, period)).length,
    };
  }

  function renderSocialChart() {
    const period = state.socialPeriod;
    const platform = state.socialPlatform;
    const social = C.socialPosts(state.data.items).filter((item) => !platform || item.platform === platform);
    const rows = state.data.competitors.map((competitor) => {
      const competitorPosts = social.filter((item) => item.competitor_id === competitor.id);
      return {
        id: competitor.id,
        label: C.competitorName(competitor),
        values: {
          current: competitorPosts.filter((item) => inAgeRange(socialDate(item), 0, period)).length,
          previous: competitorPosts.filter((item) => inAgeRange(socialDate(item), period, period * 2)).length,
        },
        colors: { current: C.competitorColor(competitor.id), previous: "#cbd5e1" },
        tooltips: {
          current: `${C.competitorName(competitor)} · ${C.t("currentPeriod")}: ${competitorPosts.filter((item) => inAgeRange(socialDate(item), 0, period)).length} · ${C.t("selectToView")}`,
          previous: `${C.competitorName(competitor)} · ${C.t("previousPeriod")}: ${competitorPosts.filter((item) => inAgeRange(socialDate(item), period, period * 2)).length}`,
        },
        onClick: () => applyChartFilters(competitor.id, "", "posts"),
      };
    });

    rows.sort((a, b) => b.values.current - a.values.current || b.values.previous - a.values.previous);
    C.renderGroupedBarChart(
      document.getElementById("channel-chart"),
      rows,
      [
        { id: "current", label: C.t("currentPeriod"), color: "#2457d6" },
        { id: "previous", label: C.t("previousPeriod"), color: "#cbd5e1" },
      ],
    );

    const current = rows.reduce((sum, row) => sum + row.values.current, 0);
    const previous = rows.reduce((sum, row) => sum + row.values.previous, 0);
    const delta = previous ? Math.round(((current - previous) / previous) * 100) : current ? null : 0;
    const trend = delta === null || delta > 0 ? "is-up" : delta < 0 ? "is-down" : "is-flat";
    const trendLabel = delta === null || delta > 0 ? C.t("comparisonUp") : delta < 0 ? C.t("comparisonDown") : C.t("comparisonFlat");
    const trendValue = delta === null ? `+${current}` : `${delta > 0 ? "+" : ""}${delta}%`;
    const summary = document.getElementById("social-comparison-summary");
    C.clear(summary);
    summary.append(
      C.el("span", {}, `${C.t("currentPeriod")}: ${current}`),
      C.el("span", {}, `${C.t("previousPeriod")}: ${previous}`),
      C.el("span", { class: trend }, `${trendLabel}: ${trendValue}`),
    );
  }

  function renderCharts() {
    const competitors = state.data.competitors;
    const activeCampaigns = campaigns();
    const activeMerchants = merchants();
    const categories = state.data.categories.filter((item) => item.id !== "merchant");
    const campaignCounts = C.countBy(activeCampaigns, (item) => item.competitor_id);
    const changeTitle = document.getElementById("campaign-changes-title");
    const changeNote = document.getElementById("campaign-changes-note");
    if (changeTitle) changeTitle.textContent = C.t("campaignChanges");
    if (changeNote) changeNote.textContent = C.t("campaignChangesNote").replace("{days}", String(state.campaignChangePeriod));

    C.renderBarChart(
      document.getElementById("campaigns-chart"),
      competitors.map((competitor) => {
        const rows = activeCampaigns.filter((item) => item.competitor_id === competitor.id);
        const breakdown = categories.map((category) => ({ label: C.taxonomyName(category), value: rows.filter((item) => item.campaign_category === category.id).length })).filter((entry) => entry.value).map((entry) => `${entry.label}: ${entry.value}`).join(" · ");
        const expiring = rows.filter((item) => { const end = validDate(item.end_date); const days = end ? (end.getTime() - Date.now()) / 86400000 : -1; return days >= 0 && days <= 7; }).length;
        return { id: competitor.id, label: C.competitorName(competitor), value: campaignCounts.get(competitor.id) || 0, color: C.competitorColor(competitor.id), tooltip: `${C.competitorName(competitor)}: ${rows.length}\n${breakdown}${expiring ? `\n${C.t("upcomingExpiries7d")}: ${expiring}` : ""}\n${C.t("selectToView")}`, onClick: () => applyChartFilters(competitor.id) };
      }),
      { keepZero: true },
    );

    C.renderStackedBarChart(
      document.getElementById("changes-chart"),
      competitors.map((competitor) => ({
        id: competitor.id,
        label: C.competitorName(competitor),
        href: `competitor.html?id=${competitor.id}`,
        values: campaignChangeValues(competitor.id),
      })),
      [
        { id: "new", label: C.t("newStatus"), color: "#16a34a" },
        { id: "updated", label: C.t("updatedStatus"), color: "#2563eb" },
        { id: "expired", label: C.t("expiredStatus"), color: "#dc2626" },
      ],
      { normalize: false, onSegmentClick: (competitor, eventType) => applyMarketEventFilter(competitor.id, eventType.id) },
    );

    const categorySeries = categories.map((category) => ({
      id: category.id,
      label: C.taxonomyName(category),
      color: CATEGORY_COLORS[category.id] || "#64748b",
    }));
    const categoryCounts = C.countBy(activeCampaigns, (item) => item.campaign_category);
    C.renderDonutChart(
      document.getElementById("category-chart"),
      categories.map((category) => {
        const value = categoryCounts.get(category.id) || 0;
        const leaders = competitors.map((competitor) => ({ name: C.competitorName(competitor), value: activeCampaigns.filter((item) => item.competitor_id === competitor.id && item.campaign_category === category.id).length })).sort((a, b) => b.value - a.value);
        const share = activeCampaigns.length ? Math.round(value / activeCampaigns.length * 100) : 0;
        return { id: category.id, label: C.taxonomyName(category), value, color: CATEGORY_COLORS[category.id] || "#64748b", tooltip: `${C.taxonomyName(category)}: ${value} (${share}% ${C.t("shareOfActive")})${leaders[0]?.value ? `\n${C.t("highestCompetitor")}: ${leaders[0].name} — ${leaders[0].value}` : ""}\n${C.t("selectToView")}`, onClick: () => applyChartFilters("", category.id) };
      }),
      { centerLabel: C.t("activeCampaigns") },
    );

    C.renderMatrix(
      document.getElementById("coverage-matrix"),
      competitors.map((competitor) => ({ id: competitor.id, label: C.competitorName(competitor), href: `competitor.html?id=${competitor.id}` })),
      categorySeries,
      (competitor, category) => activeCampaigns.filter((item) => item.competitor_id === competitor.id && item.campaign_category === category.id).length,
      { onCellClick: (competitor, category) => applyChartFilters(competitor.id, category.id) },
    );

    C.renderColumnChart(
      document.getElementById("remittance-chart"),
      competitors.map((competitor) => { const rows = activeCampaigns.filter((item) => item.competitor_id === competitor.id && item.campaign_category === "remittance"); return { id: competitor.id, label: C.competitorName(competitor), value: rows.length, color: C.competitorColor(competitor.id), tooltip: `${C.competitorName(competitor)} · ${C.t("remittanceCampaigns")}: ${rows.length}\n${C.t("selectToView")}`, onClick: () => applyChartFilters(competitor.id, "remittance") }; }),
      { keepZero: true },
    );

    C.renderBarChart(
      document.getElementById("merchant-chart"),
      competitors.map((competitor) => ({
        id: competitor.id,
        label: C.competitorName(competitor),
        value: activeMerchants.filter((item) => item.competitor_id === competitor.id).length,
        color: C.competitorColor(competitor.id),
        onClick: () => applyChartFilters(competitor.id, "", "merchant_offer"),
      })),
      { keepZero: true },
    );

    const mechanics = C.countBy(activeCampaigns, (item) => item.mechanic_tags || []);
    C.renderBarChart(
      document.getElementById("mechanics-chart"),
      (state.data.mechanic_types || []).map((mechanic, index) => ({
        label: C.taxonomyName(mechanic),
        value: mechanics.get(mechanic.id) || 0,
        color: ["#0f766e", "#2563eb", "#7c3aed", "#d97706", "#d94676", "#64748b"][index % 6],
      })),
      { keepZero: true },
    );

    const allCampaignRecords = state.data.items.filter((item) => item.content_type === "campaign");
    C.renderStackedBarChart(
      document.getElementById("expiry-chart"),
      competitors.map((competitor) => {
        const records = allCampaignRecords.filter((item) => item.competitor_id === competitor.id);
        return {
          id: competitor.id,
          label: C.competitorName(competitor),
          href: `competitor.html?id=${competitor.id}`,
          values: {
            seven: records.filter((item) => item.active !== false && /≤7/.test(item.current_status || "")).length,
            thirty: records.filter((item) => item.active !== false && /8–30/.test(item.current_status || "")).length,
            noend: records.filter((item) => item.active !== false && item.current_status === "End Date Not Stated").length,
            expired: records.filter((item) => (item.current_status === "Expired" || item.active === false) && inAgeRange(item.end_date || item.last_changed, 0, 30)).length,
          },
        };
      }),
      [
        { id: "seven", label: C.t("expiring7"), color: "#dc2626" },
        { id: "thirty", label: C.t("expiring30"), color: "#f59e0b" },
        { id: "noend", label: C.t("noEndDate"), color: "#64748b" },
        { id: "expired", label: C.t("expiredStatus"), color: "#7f1d1d" },
      ],
      { normalize: false },
    );

    renderSocialChart();
  }

  function renderDecisionSignals() {
    const now = Date.now();
    const competitors = C.byId(state.data.competitors);
    const upcoming = campaigns().map((item) => ({ item, end: validDate(item.end_date) })).filter((row) => row.end && row.end.getTime() >= now && row.end.getTime() - now <= 7 * 86400000).sort((a, b) => a.end - b.end);
    const expiryBox = document.getElementById("upcoming-expiries");
    document.getElementById("upcoming-expiry-count").textContent = String(upcoming.length);
    C.clear(expiryBox);
    if (!upcoming.length) expiryBox.appendChild(C.el("div", { class: "empty-state empty-state--compact" }, C.t("noUpcomingExpiries")));
    upcoming.forEach(({ item, end }) => {
      const days = Math.max(0, Math.ceil((end.getTime() - now) / 86400000));
      expiryBox.appendChild(C.el("a", { class: "decision-row", href: `item.html?id=${encodeURIComponent(item.id)}` }, C.el("span", { class: "decision-row__marker decision-row__marker--expiry" }, String(days)), C.el("span", { class: "decision-row__body" }, C.el("strong", {}, item.title || "—"), C.el("small", {}, `${C.competitorName(competitors[item.competitor_id])} · ${C.formatDate(item.end_date)}`)), C.el("span", { class: "decision-row__meta" }, days ? `${days} ${C.t("daysRemaining")}` : C.t("expiresToday"))));
    });

    const events = [];
    state.data.items.filter((item) => item.content_type === "campaign" && !item.review_required).forEach((item) => {
      if (inAgeRange(item.market_launch_date, 0, 30)) events.push({ item, type: "new", at: item.market_launch_date });
      if (inAgeRange(item.market_last_changed, 0, 30)) events.push({ item, type: "updated", at: item.market_last_changed });
      if (item.active === false && inAgeRange(item.market_expiry_date || item.end_date, 0, 30)) events.push({ item, type: "expired", at: item.market_expiry_date || item.end_date });
    });
    events.sort((a, b) => new Date(b.at) - new Date(a.at));
    const changesBox = document.getElementById("recent-market-changes");
    C.clear(changesBox);
    if (!events.length) changesBox.appendChild(C.el("div", { class: "empty-state empty-state--compact" }, C.t("noRecentMarketChanges")));
    events.slice(0, 5).forEach(({ item, type, at }) => changesBox.appendChild(C.el("a", { class: "decision-row", href: `item.html?id=${encodeURIComponent(item.id)}` }, C.el("span", { class: `decision-row__marker decision-row__marker--${type}` }, type === "new" ? "+" : type === "updated" ? "↻" : "−"), C.el("span", { class: "decision-row__body" }, C.el("strong", {}, item.title || "—"), C.el("small", {}, C.competitorName(competitors[item.competitor_id]))), C.el("span", { class: "decision-row__meta" }, `${C.t(`${type}Status`)} · ${C.formatDate(at)}`))));
  }

  function renderFreshness() {
    const relevant = (state.data.source_status || []).filter((status) => ["website", "social"].includes(status.source_type));
    const latestByCompetitor = new Map();
    relevant.filter((status) => status.success && status.last_success_at).forEach((status) => {
      const current = latestByCompetitor.get(status.competitor_id);
      if (!current || new Date(status.last_success_at) > new Date(current)) latestByCompetitor.set(status.competitor_id, status.last_success_at);
    });
    const delayed = state.data.competitors.some((competitor) => { const value = latestByCompetitor.get(competitor.id); return !value || Date.now() - new Date(value).getTime() > 72 * 3600000; });
    const node = document.getElementById("data-freshness");
    node.textContent = `${delayed ? C.t("dataMayBeDelayed") : C.t("dataUpToDate")} · ${C.t("lastUpdated")}: ${C.formatDate(state.data.generated_at, true)}`;
    node.classList.toggle("meta-chip--warning", delayed);
  }

  function renderCompetitors() {
    const box = document.getElementById("competitor-grid");
    C.clear(box);
    state.data.competitors.forEach((competitor) => {
      const competitorRows = state.data.items.filter((item) => item.competitor_id === competitor.id);
      const current = C.activeCampaigns(competitorRows).sort((a, b) => new Date(b.first_seen || b.published_at || b.start_date || b.last_changed || 0) - new Date(a.first_seen || a.published_at || a.start_date || a.last_changed || 0));
      const latest = current[0]?.first_seen || current[0]?.published_at || current[0]?.last_changed;
      const list = C.el("div", { class: "campaign-preview-list" });
      if (!current.length) list.appendChild(C.el("div", { class: "campaign-preview-empty" }, C.t("noCurrentCampaigns")));
      current.slice(0, 3).forEach((item) => list.appendChild(C.el("a", { class: "campaign-preview", href: `item.html?id=${encodeURIComponent(item.id)}` }, C.el("div", {}, C.el("strong", {}, item.title || "—"), C.el("small", {}, `${C.categoryLabel(item, state.data)}${item.current_status ? ` · ${item.current_status}` : ""}`)), C.el("span", { class: "campaign-preview__arrow" }, "›"))));
      const actions = C.el("div", { class: "competitor-card__actions" });
      if (C.isAdmin()) actions.appendChild(C.el("button", { type: "button", class: "button button--primary", "data-refresh-control": "true", onclick: (event) => C.triggerRefresh(competitor.id, event.currentTarget) }, C.t("checkNow")));
      actions.appendChild(C.el("a", { class: "button button--secondary competitor-card__viewall", href: `competitor.html?id=${competitor.id}` }, C.t("viewAllCampaigns")));
      box.appendChild(C.el("article", { class: "competitor-card competitor-card--campaigns" }, C.el("div", { class: "competitor-card__head" }, C.el("div", {}, C.el("h3", {}, C.competitorName(competitor)), latest ? C.el("small", { class: "competitor-last-new" }, `${C.t("lastNewOffer")}: ${C.formatDate(latest)}`) : null), C.el("span", { class: "count-badge" }, String(current.length))), list, actions));
    });
  }

  function renderMedia() {
    const box = document.getElementById("media-grid");
    C.clear(box);
    const rows = C.socialPosts(state.data.items).filter((item) => item.media?.url).sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0)).slice(0, 12);
    if (!rows.length) return box.appendChild(C.el("div", { class: "empty-state" }, C.t("noMedia")));
    rows.forEach((item) => {
      const card = C.renderMediaCard(item, state.data);
      if (card) box.appendChild(card);
    });
  }

  function renderAlerts() {
    if (!C.isAdmin()) return;
    const rows = C.alerts(state.data.items);
    const box = document.getElementById("alerts-list");
    document.getElementById("alert-count").textContent = rows.length;
    C.clear(box);
    if (!rows.length) return box.appendChild(C.el("div", { class: "empty-state empty-state--compact" }, C.t("noAlerts")));
    rows.slice(0, 30).forEach((item) => box.appendChild(C.el("a", { class: "alert-row", href: `item.html?id=${encodeURIComponent(item.id)}` }, C.el("span", { class: "alert-row__type" }, C.alertLabel(item)), C.el("strong", {}, item.title || "—"), C.el("small", {}, C.timeAgo(item.last_changed || item.first_seen)))));
  }

  function renderSources() {
    if (!C.isAdmin()) return;
    const statuses = state.data.source_status || [];
    const discovery = statuses.filter((status) => ["website", "social"].includes(status.source_type));
    const ok = discovery.filter((status) => status.success).length;
    const bad = discovery.length - ok;
    document.getElementById("source-health-summary").textContent = `${ok} ${C.t("healthy")} · ${bad} ${C.t("failed")}`;
    const performance = state.data.detail_verification_stats || {};
    const timing = document.getElementById("verification-timing");
    if (timing) {
      timing.hidden = false;
      timing.textContent = performance.completed_at ? `${C.t("verificationTiming")}: ${Number(performance.elapsed_seconds || 0).toFixed(1)}s · ${Number(performance.network_checks || 0)} ${C.t("networkChecks")} · ${C.formatDate(performance.completed_at, true)}` : `${C.t("verificationTiming")}: —`;
    }
    const box = document.getElementById("source-list");
    C.clear(box);
    statuses.forEach((status) => box.appendChild(C.sourceRow(status, state.data)));
  }

  function renderRefreshHistory() {
    if (!C.isAdmin()) return;
    const box = document.getElementById("refresh-history-list");
    if (!box) return;
    C.clear(box);
    const rows = [...(state.data.refresh_history || [])].reverse().slice(0, 10);
    if (!rows.length) return box.appendChild(C.el("div", { class: "empty-state empty-state--compact" }, C.t("noRefreshHistory")));
    rows.forEach((row) => box.appendChild(C.refreshHistoryRow(row, state.data)));
  }

  function setupFilters() {
    for (const [id, rows] of [["competitor-filter", state.data.competitors], ["category-filter", state.data.categories]]) {
      const select = document.getElementById(id);
      C.clear(select);
      select.appendChild(C.el("option", { value: "" }, C.t("all")));
      rows.forEach((row) => select.appendChild(C.el("option", { value: row.id }, id === "competitor-filter" ? C.competitorName(row) : C.taxonomyName(row))));
    }
    const source = document.getElementById("source-filter");
    C.clear(source);
    source.appendChild(C.el("option", { value: "" }, C.t("all")));
    ["inventory", "website", "social", "manual"].forEach((value) => source.appendChild(C.el("option", { value }, C.t(value))));
    const reason = document.getElementById("review-reason-filter");
    if (reason) {
      C.clear(reason);
      reason.appendChild(C.el("option", { value: "" }, C.t("all")));
      [...new Set(state.data.items.flatMap((item) => item.review_reasons || []).filter(Boolean))].sort().forEach((value) => reason.appendChild(C.el("option", { value }, value.replaceAll("_", " "))));
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
    return state.data.items.filter((item) => {
      const eventMatch = !state.marketEventFilter || (state.marketEventFilter === "new" && inAgeRange(item.market_launch_date, 0, state.campaignChangePeriod)) || (state.marketEventFilter === "updated" && inAgeRange(item.market_last_changed, 0, state.campaignChangePeriod)) || (state.marketEventFilter === "expired" && item.active === false && inAgeRange(item.market_expiry_date || item.end_date, 0, state.campaignChangePeriod));
      const lifecycleMatch = state.marketEventFilter ? eventMatch : item.active !== false;
      return lifecycleMatch && (C.isAdmin() || !(item.review_required || item.content_type === "review")) && tabMatch(item) && (!query || `${item.title || ""} ${item.snippet || ""}`.toLowerCase().includes(query)) && (!state.filters.competitor || item.competitor_id === state.filters.competitor) && (!state.filters.category || item.campaign_category === state.filters.category) && (!state.filters.source || item.source_type === state.filters.source) && (!state.filters.reviewReason || (item.review_reasons || []).includes(state.filters.reviewReason));
    });
  }

  function renderBulk() {
    const box = document.getElementById("bulk-review");
    if (!C.isAdmin() || state.tab !== "review") {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    C.clear(box);
    const availableCampaigns = state.data.items.filter((item) => item.content_type === "campaign" && item.active !== false);
    const select = C.el("select", {}, C.el("option", { value: "" }, C.t("noCampaign")), ...availableCampaigns.map((campaign) => C.el("option", { value: campaign.id }, `${C.competitorName(C.byId(state.data.competitors)[campaign.competitor_id])} · ${campaign.title}`)));
    box.append(C.el("strong", {}, C.t("bulkReview")), select, C.el("button", { class: "button button--secondary", onclick: () => {
      const ids = [...document.querySelectorAll(".review-select:checked")].map((node) => node.dataset.itemId);
      if (!ids.length) return alert(C.t("selectItems"));
      ids.forEach((id) => C.saveItemOverride(id, { linked_campaign_id: select.value || null, campaign_id: select.value || null, review_required: !select.value, review_reasons: select.value ? [] : ["manual_review_required"] }));
      C.exportOverrides();
      location.reload();
    } }, C.t("linkSelected")));
  }

  function renderList() {
    const rows = filtered().sort((a, b) => (b.review_priority || 0) - (a.review_priority || 0));
    const box = document.getElementById("item-list");
    const more = document.getElementById("load-more");
    document.getElementById("result-count").textContent = `${rows.length} ${C.t("results")}`;
    C.clear(box);
    if (!rows.length) {
      more.hidden = true;
      return box.appendChild(C.el("div", { class: "empty-state" }, C.t("noData")));
    }
    rows.slice(0, state.visible).forEach((item) => box.appendChild(C.renderItemCard(item, state.data, { selectable: state.tab === "review" })));
    more.hidden = state.visible >= rows.length;
    renderBulk();
  }

  function resetList() {
    state.visible = 40;
    renderList();
  }

  function bind() {
    document.getElementById("content-tabs").onclick = (event) => {
      const button = event.target.closest("button[data-type]");
      if (!button) return;
      state.marketEventFilter = "";
      selectTab(button.dataset.type);
      resetList();
    };
    document.getElementById("search").oninput = (event) => {
      state.filters.q = event.target.value;
      resetList();
    };
    for (const [id, key] of [["competitor-filter", "competitor"], ["category-filter", "category"], ["source-filter", "source"], ["review-reason-filter", "reviewReason"]]) {
      const node = document.getElementById(id);
      if (node) node.onchange = (event) => {
        state.filters[key] = event.target.value;
        resetList();
      };
    }
    document.getElementById("clear-filters").onclick = () => {
      state.marketEventFilter = "";
      state.filters = { q: "", competitor: "", category: "", source: "", reviewReason: "" };
      ["search", "competitor-filter", "category-filter", "source-filter", "review-reason-filter"].forEach((id) => {
        const node = document.getElementById(id);
        if (node) node.value = "";
      });
      resetList();
    };
    document.getElementById("load-more").onclick = () => {
      state.visible += 40;
      renderList();
    };
    document.getElementById("social-period-filter").onchange = (event) => {
      state.socialPeriod = Number(event.target.value) === 30 ? 30 : 7;
      renderSocialChart();
    };
    document.getElementById("campaign-change-period-filter").onchange = (event) => {
      const value = Number(event.target.value);
      state.campaignChangePeriod = [7, 14, 30].includes(value) ? value : 30;
      renderCharts();
    };
    document.getElementById("social-platform-filter").onchange = (event) => {
      state.socialPlatform = event.target.value;
      renderSocialChart();
    };
    const mark = document.getElementById("mark-reviewed");
    if (mark && C.isAdmin()) mark.onclick = () => {
      C.acknowledgeAlerts();
      renderAlerts();
    };
    const refreshAll = document.getElementById("refresh-all");
    if (refreshAll && C.isAdmin()) refreshAll.onclick = (event) => C.triggerRefresh("all", event.currentTarget);
    document.getElementById("export-edits").onclick = C.exportOverrides;
    document.getElementById("import-edits").onclick = () => document.getElementById("import-file").click();
    document.getElementById("import-file").onchange = (event) => event.target.files[0] && C.importOverrides(event.target.files[0]);
    document.getElementById("add-campaign").onclick = () => C.openAddCampaign(state.data);
    document.getElementById("delta-export").onclick = () => C.exportDelta(state.data);
  }

  function applyPermissions() {
    const admin = C.isAdmin();
    const add = document.getElementById("add-campaign");
    if (add) add.hidden = !admin;
    const tools = document.getElementById("admin-tools");
    if (tools) tools.hidden = !admin;
    const monitoring = document.getElementById("admin-monitoring-tools");
    if (monitoring) monitoring.hidden = !admin;
    document.querySelectorAll("[data-admin-only]").forEach((node) => node.hidden = !admin);
  }

  function renderAll() {
    document.getElementById("last-check").textContent = C.formatDate(state.data.generated_at, true);
    document.getElementById("inventory-meta").textContent = state.data.inventory_source?.review_date ? `Excel · ${C.formatDate(state.data.inventory_source.review_date)}` : "Excel Master";
    renderAlerts();
    renderSources();
    renderRefreshHistory();
    renderKpis();
    renderSummary();
    renderFreshness();
    renderDecisionSignals();
    renderCharts();
    renderCompetitors();
    renderMedia();
    setupFilters();
    renderList();
  }

  async function init() {
    C.initLanguage();
    try {
      await C.loadAuth();
      applyPermissions();
      state.data = await C.loadData();
      document.getElementById("loading").hidden = true;
      document.getElementById("content").hidden = false;
      renderAll();
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
