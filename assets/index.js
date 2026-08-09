(() => {
  "use strict";
  const C = window.CM;
  const state = { data: null, ai: null, intel: null, tab: "campaign", filters: { q: "", competitor: "", category: "", source: "" } };

  function kpi(label, value, detail, kind = "default") { return C.el("article", { class: `kpi-card kpi-card--${kind}` }, C.el("span", { class: "kpi-card__label" }, label), C.el("strong", {}, String(value)), C.el("small", {}, detail)); }
  function activeCampaigns() { return C.activeCampaigns(state.data.items); }
  function merchants() { return C.activeMerchants(state.data.items); }

  function renderHero() {
    document.getElementById("last-check").textContent = `${C.t("lastCheck")}: ${C.formatDate(state.data.generated_at, true)}`;
    const stats = state.data.stats || {};
    document.getElementById("source-health-summary").textContent = `${stats.healthy_sources || 0} ${C.t("healthy")} · ${stats.failed_sources || 0} ${C.t("failed")}`;
    const inventory = state.data.inventory_source || {};
    document.getElementById("inventory-meta").textContent = `${C.t("inventoryReviewed")}: ${inventory.review_date || "—"}`;
  }

  function renderAlerts() {
    const rows = C.alerts(state.data.items); const container = document.getElementById("alerts-list"); C.clear(container);
    document.getElementById("alert-count").textContent = String(rows.length);
    document.getElementById("alerts-summary-text").textContent = rows.length ? `${C.t("alerts")}: ${rows.length}` : C.t("noAlerts");
    if (!rows.length) return container.appendChild(C.el("div", { class: "empty-state empty-state--compact" }, C.t("noAlerts")));
    rows.slice(0, 15).forEach(item => container.appendChild(C.el("a", { class: "alert-row", href: `item.html?id=${encodeURIComponent(item.id)}` }, C.el("span", { class: "alert-row__type" }, C.alertLabel(item)), C.el("strong", {}, item.title || "—"), C.el("small", {}, C.timeAgo(item.last_changed || item.first_seen)))));
  }

  function renderAiSummary() {
    const section = document.getElementById("ai-summary-section");
    const payload = state.ai?.market;
    const localized = payload?.[C.language()] || payload?.en || payload?.ar;
    if (!localized?.summary) { section.hidden = true; return; }
    section.hidden = false;
    document.getElementById("ai-summary-text").textContent = localized.summary;
    document.getElementById("ai-summary-meta").textContent = state.ai?.generated_at ? `${C.t("aiGenerated")}: ${C.formatDate(state.ai.generated_at, true)}` : C.t("aiFallback");
    const bullets = document.getElementById("ai-summary-bullets"); C.clear(bullets);
    (localized.bullets || []).slice(0, 3).forEach(text => bullets.appendChild(C.el("div", { class: "ai-summary-bullet" }, C.el("span", { class: "ai-summary-bullet__dot" }, "•"), C.el("span", {}, text))));
  }


  function renderTextList(container, items, emptyText = "—") {
    C.clear(container);
    const rows = (items || []).filter(Boolean);
    if (!rows.length) return container.appendChild(C.el("div", { class: "empty-state empty-state--compact" }, emptyText));
    rows.forEach(text => container.appendChild(C.el("div", { class: "intelligence-list__item" }, C.el("span", { class: "intelligence-list__dot" }, "•"), C.el("span", {}, text))));
  }

  function renderAiStrategic() {
    const section = document.getElementById("ai-strategic-section");
    const localized = state.ai?.market?.[C.language()] || state.ai?.market?.en || state.ai?.market?.ar;
    if (!localized?.management_takeaway) { section.hidden = true; return; }
    section.hidden = false;
    renderTextList(document.getElementById("ai-what-changed"), localized.what_changed, C.t("noMaterialChange"));
    renderTextList(document.getElementById("ai-why-matters"), localized.why_it_matters);
    document.getElementById("ai-management-takeaway").textContent = localized.management_takeaway || "—";
    document.getElementById("ai-weekly-brief").textContent = localized.weekly_brief || "—";
    const gaps = document.getElementById("ai-opportunity-gaps"); C.clear(gaps);
    (localized.opportunity_gaps || []).forEach(text => gaps.appendChild(C.el("div", { class: "gap-card" }, text)));
    const categories = C.byId(state.data.categories || []); const catGrid = document.getElementById("ai-category-insights"); C.clear(catGrid);
    (localized.category_insights || []).forEach(row => { const cat = categories[row.category_id]; catGrid.appendChild(C.el("article", { class: "category-insight-card" }, C.el("strong", {}, cat ? C.taxonomyName(cat) : row.category_id), C.el("p", {}, row.insight))); });
  }

  function renderActivityScores() {
    const grid = document.getElementById("activity-score-grid"); C.clear(grid);
    const rows = state.intel?.competitor_scores || [];
    if (!rows.length) return grid.appendChild(C.el("div", { class: "empty-state" }, C.t("noData")));
    rows.forEach((row, index) => {
      const comp = C.byId(state.data.competitors)[row.competitor_id];
      grid.appendChild(C.el("a", { class: "score-card", href: `competitor.html?id=${encodeURIComponent(row.competitor_id)}` },
        C.el("div", { class: "score-card__head" }, C.el("span", { class: "score-rank" }, `#${index + 1}`), C.el("strong", {}, comp ? C.competitorName(comp) : row.name), C.el("span", { class: "score-value" }, `${row.score}/100`)),
        C.el("div", { class: "score-track" }, C.el("span", { class: "score-fill", style: `width:${row.score}%` })),
        C.el("div", { class: "score-components" },
          C.el("span", {}, `${C.t("campaignIntensity")}: ${row.components?.campaign_intensity ?? 0}`),
          C.el("span", {}, `${C.t("priorityBreadth")}: ${row.components?.priority_category_breadth ?? 0}`),
          C.el("span", {}, `${C.t("socialActivity")}: ${row.components?.social_activity_7d ?? 0}`),
          C.el("span", {}, `${C.t("multiChannelCoverage")}: ${row.components?.platform_coverage ?? 0}`)
        )
      ));
    });
  }

  function renderExpiryWatch() {
    const container = document.getElementById("expiry-watch-list"); C.clear(container);
    const rows = state.intel?.market?.expiry_watch?.within_30_days || [];
    if (!rows.length) return container.appendChild(C.el("div", { class: "empty-state empty-state--compact" }, C.t("noExpiryWatch")));
    const comps = C.byId(state.data.competitors);
    rows.slice(0, 12).forEach(row => {
      const bucket = row.days_remaining <= 7 ? C.t("within7") : row.days_remaining <= 14 ? C.t("within14") : C.t("within30");
      container.appendChild(C.el("a", { class: "expiry-row", href: `item.html?id=${encodeURIComponent(row.id)}` },
        C.el("div", {}, C.el("strong", {}, row.title || "—"), C.el("small", {}, comps[row.competitor_id] ? C.competitorName(comps[row.competitor_id]) : row.competitor_id)),
        C.el("span", { class: `expiry-badge expiry-badge--${row.days_remaining <= 7 ? "urgent" : row.days_remaining <= 14 ? "soon" : "watch"}` }, bucket)
      ));
    });
  }

  function renderHistory() {
    const history = state.intel?.history || [];
    C.renderLineChart(document.getElementById("market-history-chart"), history.map(row => ({ label: row.date, value: Number(row.active_campaigns || 0) })));
  }

  function renderCategoryIntensity() {
    const grid = document.getElementById("category-intensity-grid"); C.clear(grid);
    const rows = state.intel?.market?.category_intensity || []; const cats = C.byId(state.data.categories);
    if (!rows.length) return grid.appendChild(C.el("div", { class: "empty-state empty-state--compact" }, C.t("noData")));
    rows.forEach(row => {
      const cat = cats[row.category_id]; const label = row.intensity === "high" ? C.t("intensityHigh") : row.intensity === "medium" ? C.t("intensityMedium") : C.t("intensityLow");
      grid.appendChild(C.el("div", { class: `intensity-row intensity-row--${row.intensity}` }, C.el("strong", {}, cat ? C.taxonomyName(cat) : row.category_id), C.el("span", {}, `${label} · ${row.active_campaigns}`)));
    });
  }

  function renderKpis() {
    const campaigns = activeCampaigns(); const merchantRows = merchants(); const social7 = C.socialPosts(state.data.items, 7);
    const expiring = campaigns.filter(item => /Expiring/.test(item.current_status || "")); const review = state.data.items.filter(item => item.active !== false && item.review_required);
    const rows = [
      kpi(C.t("activeCampaigns"), campaigns.length, C.t("activeCampaignsDetail"), "primary"),
      kpi(C.t("merchantPortfolio"), merchantRows.length, C.t("merchantPortfolioDetail"), "gold"),
      kpi(C.t("remittanceCampaigns"), campaigns.filter(item => item.campaign_category === "remittance").length, C.t("remittance"), "blue"),
      kpi(C.t("expiring30d"), expiring.length, C.t("expiryRisk"), expiring.length ? "danger" : "default"),
      kpi(C.t("socialPosts7d"), social7.length, C.t("channelActivity7d"), "purple"),
      kpi(C.t("reviewRequired"), review.length, C.t("review"), review.length ? "warning" : "default")
    ]; const container = document.getElementById("kpi-grid"); C.clear(container); rows.forEach(row => container.appendChild(row));
  }

  function competitorRows(items, fn) { return state.data.competitors.map((comp, index) => ({ label: C.competitorName(comp), value: fn(items.filter(item => item.competitor_id === comp.id)), color: ["#0f766e", "#2563eb", "#7c3aed", "#d97706", "#dc2626", "#475569"][index] })); }

  function renderCharts() {
    const campaigns = activeCampaigns(), merchantRows = merchants();
    C.renderBarChart(document.getElementById("campaigns-chart"), competitorRows(campaigns, rows => rows.length), { keepZero: true });
    C.renderBarChart(document.getElementById("merchant-chart"), competitorRows(merchantRows, rows => rows.length), { keepZero: true });
    C.renderBarChart(document.getElementById("remittance-chart"), competitorRows(campaigns.filter(item => item.campaign_category === "remittance"), rows => rows.length), { keepZero: true });
    const categories = state.data.categories.filter(row => !["merchant"].includes(row.id)); const categoryCounts = C.countBy(campaigns, item => item.campaign_category);
    C.renderBarChart(document.getElementById("category-chart"), categories.map(row => ({ label: C.taxonomyName(row), value: categoryCounts.get(row.id) || 0 })), { keepZero: true });
    const mechanicMap = C.byId(state.data.mechanic_types); const mechanicCounts = C.countBy(campaigns, item => item.mechanic_tags || []);
    C.renderBarChart(document.getElementById("mechanics-chart"), Object.keys(mechanicMap).map(id => ({ label: C.taxonomyName(mechanicMap[id]), value: mechanicCounts.get(id) || 0 })).filter(row => row.label), { keepZero: true });
    C.renderBarChart(document.getElementById("expiry-chart"), competitorRows(campaigns, rows => rows.filter(item => /Expiring/.test(item.current_status || "")).length), { keepZero: true });
    const platformRows = state.data.competitors.map(comp => ({ id: comp.id, label: C.competitorName(comp), href: `competitor.html?id=${encodeURIComponent(comp.id)}` }));
    const platforms = ["instagram", "facebook", "x", "tiktok"].map(id => ({ id, label: C.t(id) }));
    const recent = C.socialPosts(state.data.items, 7);
    C.renderMatrix(document.getElementById("channel-matrix"), platformRows, platforms, (row, col) => recent.filter(item => item.competitor_id === row.id && item.platform === col.id).length);
    const categoryCols = categories.map(row => ({ id: row.id, label: C.taxonomyName(row) }));
    C.renderMatrix(document.getElementById("coverage-matrix"), platformRows, categoryCols, (row, col) => campaigns.filter(item => item.competitor_id === row.id && item.campaign_category === col.id).length);
    C.renderBarChart(document.getElementById("platform-coverage-chart"), competitorRows(campaigns, rows => rows.length ? Number((rows.reduce((sum, item) => sum + Number(item.social_link_count || 0), 0) / rows.length).toFixed(1)) : 0), { keepZero: true });
  }

  function topEntry(map) { return [...map.entries()].sort((a, b) => b[1] - a[1])[0]; }
  function renderSignals() {
    const campaigns = activeCampaigns(), social7 = C.socialPosts(state.data.items, 7); const grid = document.getElementById("signal-grid"); C.clear(grid);
    const compMap = C.countBy(social7, item => item.competitor_id); const topComp = topEntry(compMap); const comp = topComp ? C.byId(state.data.competitors)[topComp[0]] : null;
    const coverage = state.data.competitors.map(c => { const rows = campaigns.filter(item => item.competitor_id === c.id); return [c, rows.length ? rows.reduce((sum, item) => sum + Number(item.social_link_count || 0), 0) / rows.length : 0]; }).sort((a, b) => b[1] - a[1])[0];
    const catMap = C.countBy(campaigns, item => item.campaign_category); const topCat = topEntry(catMap); const cat = topCat ? C.byId(state.data.categories)[topCat[0]] : null;
    const expiry = state.data.competitors.map(c => [c, campaigns.filter(item => item.competitor_id === c.id && /Expiring/.test(item.current_status || "")).length]).sort((a, b) => b[1] - a[1])[0];
    const signals = [
      [C.t("mostActiveCompetitor"), comp ? `${C.competitorName(comp)} (${topComp[1]})` : "—"],
      [C.t("bestPlatformCoverage"), coverage?.[0] ? `${C.competitorName(coverage[0])} (${coverage[1].toFixed(1)})` : "—"],
      [C.t("strongestCategory"), cat ? `${C.taxonomyName(cat)} (${topCat[1]})` : "—"],
      [C.t("highestExpiryRisk"), expiry?.[0] ? `${C.competitorName(expiry[0])} (${expiry[1]})` : "—"]
    ]; signals.forEach(([label, value]) => grid.appendChild(C.el("article", { class: "signal-card" }, C.el("span", {}, label), C.el("strong", {}, value))));
  }

  function renderCompetitors() {
    const container = document.getElementById("competitor-grid"); C.clear(container); const campaigns = activeCampaigns(), merchantRows = merchants(), social7 = C.socialPosts(state.data.items, 7);
    state.data.competitors.forEach(comp => {
      const cRows = campaigns.filter(item => item.competitor_id === comp.id); const avg = cRows.length ? (cRows.reduce((sum, item) => sum + Number(item.social_link_count || 0), 0) / cRows.length).toFixed(1) : "0.0";
      container.appendChild(C.el("article", { class: "competitor-card" }, C.el("div", { class: "competitor-card__head" }, C.el("h3", {}, C.competitorName(comp)), C.el("a", { href: `competitor.html?id=${encodeURIComponent(comp.id)}` }, C.t("viewCompetitor"))), C.el("div", { class: "mini-kpis" }, C.el("span", {}, C.el("strong", {}, cRows.length), C.t("campaigns")), C.el("span", {}, C.el("strong", {}, merchantRows.filter(item => item.competitor_id === comp.id).length), C.t("merchantOffers")), C.el("span", {}, C.el("strong", {}, social7.filter(item => item.competitor_id === comp.id).length), C.t("posts")), C.el("span", {}, C.el("strong", {}, avg), C.t("socialLinks")), C.el("span", {}, C.el("strong", {}, state.intel?.competitor_scores?.find(row => row.competitor_id === comp.id)?.score ?? "—"), C.t("activityScore")))));
    });
  }

  function renderMedia() { const container = document.getElementById("media-grid"); C.clear(container); const rows = C.socialPosts(state.data.items).filter(item => item.media?.url).sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0)).slice(0, 12); if (!rows.length) return container.appendChild(C.el("div", { class: "empty-state" }, C.t("noMedia"))); rows.forEach(item => { const card = C.renderMediaCard(item, state.data); if (card) container.appendChild(card); }); }

  function filterOptions(select, rows, placeholder) { C.clear(select); select.appendChild(C.el("option", { value: "" }, placeholder)); rows.forEach(row => select.appendChild(C.el("option", { value: row.id }, row.label))); }
  function setupFilters() {
    filterOptions(document.getElementById("competitor-filter"), state.data.competitors.map(row => ({ id: row.id, label: C.competitorName(row) })), C.t("all"));
    filterOptions(document.getElementById("category-filter"), state.data.categories.map(row => ({ id: row.id, label: C.taxonomyName(row) })), C.t("all"));
    filterOptions(document.getElementById("source-filter"), [{ id: "inventory", label: C.t("inventorySource") }, { id: "website", label: C.t("website") }, { id: "social", label: C.t("posts") }], C.t("all"));
  }
  function tabMatch(item) { if (state.tab === "all") return true; if (state.tab === "campaign") return item.content_type === "campaign"; if (state.tab === "merchant_offer") return item.content_type === "merchant_offer"; if (state.tab === "posts") return item.source_type === "social"; if (state.tab === "review") return item.review_required || item.content_type === "review"; return true; }
  function filtered() { const q = state.filters.q.toLowerCase(); return state.data.items.filter(item => item.active !== false && tabMatch(item) && (!q || `${item.title} ${item.snippet}`.toLowerCase().includes(q)) && (!state.filters.competitor || item.competitor_id === state.filters.competitor) && (!state.filters.category || (item.campaign_category || item.primary_category) === state.filters.category) && (!state.filters.source || item.source_type === state.filters.source)); }
  function renderInventory() { const rows = filtered(); document.getElementById("result-count").textContent = `${rows.length} ${C.t("results")}`; const container = document.getElementById("item-list"); C.clear(container); if (!rows.length) return container.appendChild(C.el("div", { class: "empty-state" }, C.t("noData"))); rows.slice(0, 150).forEach(item => container.appendChild(C.renderItemCard(item, state.data, { media: false }))); }
  function renderSources() { const container = document.getElementById("source-list"); C.clear(container); (state.data.source_status || []).forEach(status => container.appendChild(C.sourceRow(status, state.data))); }

  function bind() {
    document.getElementById("mark-reviewed").onclick = () => { C.acknowledgeAlerts(); renderAlerts(); };
    document.getElementById("export-edits").onclick = C.exportOverrides;
    const importInput = document.getElementById("import-file"); document.getElementById("import-edits").onclick = () => importInput.click(); importInput.onchange = () => importInput.files[0] && C.importOverrides(importInput.files[0]);
    document.getElementById("content-tabs").addEventListener("click", event => { const button = event.target.closest("button[data-type]"); if (!button) return; state.tab = button.dataset.type; document.querySelectorAll("#content-tabs .tab").forEach(node => node.classList.toggle("is-active", node === button)); renderInventory(); });
    [["search", "q"], ["competitor-filter", "competitor"], ["category-filter", "category"], ["source-filter", "source"]].forEach(([id, key]) => document.getElementById(id).addEventListener(id === "search" ? "input" : "change", event => { state.filters[key] = event.target.value; renderInventory(); }));
    document.getElementById("clear-filters").onclick = () => { state.filters = { q: "", competitor: "", category: "", source: "" }; ["search", "competitor-filter", "category-filter", "source-filter"].forEach(id => document.getElementById(id).value = ""); renderInventory(); };
  }

  function renderAll() { renderHero(); renderAlerts(); renderAiSummary(); renderAiStrategic(); renderKpis(); renderActivityScores(); renderExpiryWatch(); renderHistory(); renderCategoryIntensity(); renderCharts(); renderSignals(); renderCompetitors(); renderMedia(); setupFilters(); renderInventory(); renderSources(); }
  async function init() { C.initLanguage(); try { [state.data, state.ai, state.intel] = await Promise.all([C.loadData(), C.loadAiSummary(), C.loadIntelligence()]); document.getElementById("loading").hidden = true; document.getElementById("content").hidden = false; renderAll(); bind(); window.addEventListener("cm:language", () => location.reload()); } catch (error) { document.getElementById("loading").hidden = true; C.showError(document.getElementById("error"), error); } }
  document.addEventListener("DOMContentLoaded", init);
})();
