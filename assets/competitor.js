(() => {
  "use strict";
  const C = window.CM; const params = new URLSearchParams(location.search); const state = { data: null, ai: null, intel: null, competitor: null, tab: "campaign", filters: { q: "", category: "", status: "" } };
  function rows() { return state.data.items.filter(item => item.competitor_id === state.competitor.id); }
  function campaigns() { return C.activeCampaigns(rows()); }
  function merchants() { return C.activeMerchants(rows()); }
  function kpi(label, value, detail, kind = "default") { return C.el("article", { class: `kpi-card kpi-card--${kind}` }, C.el("span", { class: "kpi-card__label" }, label), C.el("strong", {}, String(value)), C.el("small", {}, detail)); }

  function hero() { document.getElementById("competitor-name").textContent = C.competitorName(state.competitor); const campaignsRows = campaigns(); document.getElementById("competitor-summary").textContent = `${campaignsRows.length} ${C.t("activeCampaigns")} · ${merchants().length} ${C.t("merchantOffers")} · ${C.socialPosts(rows(), 7).length} ${C.t("socialPosts7d")}`; document.getElementById("website-url").href = state.competitor.website || "#"; document.getElementById("offers-url").href = state.competitor.offers_url || "#"; const switcher = document.getElementById("competitor-switcher"); C.clear(switcher); state.data.competitors.forEach(comp => switcher.appendChild(C.el("option", { value: comp.id, selected: comp.id === state.competitor.id }, C.competitorName(comp)))); switcher.onchange = () => location.href = `competitor.html?id=${encodeURIComponent(switcher.value)}`; }
  function offerPriority(item) {
    const status = item.current_status || "";
    if (/≤7/.test(status)) return 0;
    if (/8–30|Expiring/.test(status)) return 1;
    if (item.end_date) return 2;
    return 3;
  }
  function renderFeaturedOffers() {
    const container = document.getElementById("featured-offers-grid"); C.clear(container);
    const active = campaigns().slice().sort((a, b) => offerPriority(a) - offerPriority(b) || new Date(a.end_date || "2999-12-31") - new Date(b.end_date || "2999-12-31") || (a.title || "").localeCompare(b.title || ""));
    document.getElementById("featured-offers-count").textContent = `${active.length} ${C.t("activeCampaigns")}`;
    if (!active.length) return container.appendChild(C.el("div", { class: "empty-state" }, C.t("noCurrentOffers")));
    active.forEach(item => {
      const statusKind = /Expiring|≤7|8–30/.test(item.current_status || "") ? "urgent" : "active";
      const card = C.el("article", { class: `featured-offer-card featured-offer-card--${statusKind}` },
        C.el("div", { class: "featured-offer-card__top" },
          C.pill(C.categoryLabel(item, state.data), "info"),
          C.el("span", { class: `featured-offer-status featured-offer-status--${statusKind}` }, item.current_status || C.t("active"))
        ),
        C.el("h3", {}, item.title || "—"),
        item.mechanic ? C.el("p", { class: "featured-offer-mechanic" }, item.mechanic) : (item.snippet ? C.el("p", { class: "featured-offer-mechanic" }, item.snippet) : null),
        C.el("div", { class: "featured-offer-footer" },
          C.el("span", { class: "featured-offer-date" }, item.end_date ? `${C.t("offerEnds")}: ${C.formatDate(item.end_date)}` : C.t("noEndDate")),
          C.el("div", { class: "featured-offer-actions" },
            C.el("a", { class: "button button--primary", href: `item.html?id=${encodeURIComponent(item.id)}` }, C.t("viewOffer")),
            item.link ? C.el("a", { class: "button button--ghost", href: item.link, target: "_blank", rel: "noopener noreferrer" }, C.t("openOfficial")) : null
          )
        )
      );
      container.appendChild(card);
    });
  }
  function renderAiSummary() {
    const section = document.getElementById("ai-summary-section");
    const payload = state.ai?.competitors?.[state.competitor.id];
    const localized = payload?.[C.language()] || payload?.en || payload?.ar;
    if (!localized?.summary) { section.hidden = true; return; }
    section.hidden = false;
    document.getElementById("ai-summary-text").textContent = localized.summary;
    document.getElementById("ai-summary-meta").textContent = state.ai?.generated_at ? `${C.t("aiGenerated")}: ${C.formatDate(state.ai.generated_at, true)}` : C.t("aiFallback");
    const bullets = document.getElementById("ai-summary-bullets"); C.clear(bullets);
    (localized.bullets || []).slice(0, 3).forEach(text => bullets.appendChild(C.el("div", { class: "ai-summary-bullet" }, C.el("span", { class: "ai-summary-bullet__dot" }, "•"), C.el("span", {}, text))));
  }


  function renderTextList(container, items, emptyText = "—") {
    C.clear(container); const values = (items || []).filter(Boolean);
    if (!values.length) return container.appendChild(C.el("div", { class: "empty-state empty-state--compact" }, emptyText));
    values.forEach(text => container.appendChild(C.el("div", { class: "intelligence-list__item" }, C.el("span", { class: "intelligence-list__dot" }, "•"), C.el("span", {}, text))));
  }

  function renderAiDetails() {
    const section = document.getElementById("ai-competitor-detail-section");
    const localized = state.ai?.competitors?.[state.competitor.id]?.[C.language()] || state.ai?.competitors?.[state.competitor.id]?.en || state.ai?.competitors?.[state.competitor.id]?.ar;
    if (!localized?.positioning) { section.hidden = true; return; }
    section.hidden = false;
    document.getElementById("ai-positioning").textContent = localized.positioning || "—";
    renderTextList(document.getElementById("ai-competitor-changes"), localized.what_changed, C.t("noMaterialChange"));
    renderTextList(document.getElementById("ai-watchpoints"), localized.watchpoints);
  }

  function selectedScore() { return state.intel?.competitor_scores?.find(row => row.competitor_id === state.competitor.id); }
  function renderScoreDetail() {
    const container = document.getElementById("competitor-score-detail"); C.clear(container); const row = selectedScore();
    if (!row) return container.appendChild(C.el("div", { class: "empty-state empty-state--compact" }, C.t("noData")));
    container.appendChild(C.el("div", { class: "score-detail" },
      C.el("div", { class: "score-detail__value" }, C.el("strong", {}, `${row.score}`), C.el("span", {}, "/100")),
      C.el("div", { class: "score-track" }, C.el("span", { class: "score-fill", style: `width:${row.score}%` })),
      C.el("div", { class: "score-components score-components--detail" },
        C.el("span", {}, `${C.t("campaignIntensity")}: ${row.components?.campaign_intensity ?? 0}`),
        C.el("span", {}, `${C.t("priorityBreadth")}: ${row.components?.priority_category_breadth ?? 0}`),
        C.el("span", {}, `${C.t("socialActivity")}: ${row.components?.social_activity_7d ?? 0}`),
        C.el("span", {}, `${C.t("multiChannelCoverage")}: ${row.components?.platform_coverage ?? 0}`)
      )
    ));
  }

  function renderCompetitorExpiry() {
    const container = document.getElementById("competitor-expiry-watch"); C.clear(container);
    const all = state.intel?.market?.expiry_watch?.within_30_days || []; const rows = all.filter(row => row.competitor_id === state.competitor.id);
    if (!rows.length) return container.appendChild(C.el("div", { class: "empty-state empty-state--compact" }, C.t("noExpiryWatch")));
    rows.slice(0, 10).forEach(row => { const bucket = row.days_remaining <= 7 ? C.t("within7") : row.days_remaining <= 14 ? C.t("within14") : C.t("within30"); container.appendChild(C.el("a", { class: "expiry-row", href: `item.html?id=${encodeURIComponent(row.id)}` }, C.el("div", {}, C.el("strong", {}, row.title || "—"), C.el("small", {}, row.record_type === "merchant_offer" ? C.t("merchantOffers") : C.t("campaigns"))), C.el("span", { class: `expiry-badge expiry-badge--${row.days_remaining <= 7 ? "urgent" : row.days_remaining <= 14 ? "soon" : "watch"}` }, bucket))); });
  }

  function renderCompetitorHistory() {
    const history = state.intel?.history || [];
    C.renderLineChart(document.getElementById("competitor-history-chart"), history.map(row => ({ label: row.date, value: Number(row.competitors?.[state.competitor.id]?.active_campaigns || 0) })));
  }

  function renderKpis() { const c = campaigns(); const expiring = c.filter(item => /Expiring/.test(item.current_status || "")); const avg = c.length ? (c.reduce((sum, item) => sum + Number(item.social_link_count || 0), 0) / c.length).toFixed(1) : "0.0"; const cards = [kpi(C.t("activeCampaigns"), c.length, C.t("activeCampaignsDetail"), "primary"), kpi(C.t("merchantPortfolio"), merchants().length, C.t("merchantPortfolioDetail"), "gold"), kpi(C.t("remittanceCampaigns"), c.filter(item => item.campaign_category === "remittance").length, C.t("remittance"), "blue"), kpi(C.t("expiring30d"), expiring.length, C.t("expiryRisk"), expiring.length ? "danger" : "default"), kpi(C.t("socialPosts7d"), C.socialPosts(rows(), 7).length, C.t("channelActivity7d"), "purple"), kpi(C.t("platformCoverage"), avg, C.t("socialLinkCount"))]; const grid = document.getElementById("kpi-grid"); C.clear(grid); cards.forEach(card => grid.appendChild(card)); }
  function renderSignals() { const grid = document.getElementById("signal-grid"); C.clear(grid); const c = campaigns(); const catMap = C.countBy(c, item => item.campaign_category); const topCat = [...catMap.entries()].sort((a, b) => b[1] - a[1])[0]; const mechMap = C.countBy(c, item => item.mechanic_tags || []); const topMech = [...mechMap.entries()].sort((a, b) => b[1] - a[1])[0]; const platformMap = C.countBy(C.socialPosts(rows(), 7), item => item.platform); const topPlatform = [...platformMap.entries()].sort((a, b) => b[1] - a[1])[0]; const cat = topCat ? C.byId(state.data.categories)[topCat[0]] : null; const mech = topMech ? C.byId(state.data.mechanic_types)[topMech[0]] : null; [[C.t("strongestCategory"), cat ? `${C.taxonomyName(cat)} (${topCat[1]})` : "—"], [C.t("mechanicsMix"), mech ? `${C.taxonomyName(mech)} (${topMech[1]})` : "—"], [C.t("mostActiveCompetitor"), topPlatform ? `${C.t(topPlatform[0])} (${topPlatform[1]})` : "—"], [C.t("reviewRequired"), rows().filter(item => item.active !== false && item.review_required).length]].forEach(([label, value]) => grid.appendChild(C.el("article", { class: "signal-card" }, C.el("span", {}, label), C.el("strong", {}, String(value))))); }
  function renderCharts() { const c = campaigns(); const catCounts = C.countBy(c, item => item.campaign_category); C.renderBarChart(document.getElementById("category-chart"), state.data.categories.filter(row => row.id !== "merchant").map(row => ({ label: C.taxonomyName(row), value: catCounts.get(row.id) || 0 })), { keepZero: true }); const mech = C.countBy(c, item => item.mechanic_tags || []); C.renderBarChart(document.getElementById("mechanics-chart"), state.data.mechanic_types.map(row => ({ label: C.taxonomyName(row), value: mech.get(row.id) || 0 })), { keepZero: true }); C.renderBarChart(document.getElementById("expiry-chart"), [{ label: "≤7", value: c.filter(item => /≤7/.test(item.current_status || "")).length }, { label: "8–30", value: c.filter(item => /8–30/.test(item.current_status || "")).length }, { label: C.t("active"), value: c.filter(item => item.current_status === "Active").length }, { label: "No end date", value: c.filter(item => item.current_status === "End Date Not Stated").length }], { keepZero: true }); const platforms = ["instagram", "facebook", "x", "tiktok"].map(id => ({ id, label: C.t(id) })); C.renderMatrix(document.getElementById("channel-chart"), [{ id: state.competitor.id, label: C.competitorName(state.competitor) }], platforms, (_row, col) => C.socialPosts(rows(), 7).filter(item => item.platform === col.id).length); }
  function renderMedia() { const container = document.getElementById("media-grid"); C.clear(container); const media = C.socialPosts(rows()).filter(item => item.media?.url).sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0)).slice(0, 12); if (!media.length) return container.appendChild(C.el("div", { class: "empty-state" }, C.t("noMedia"))); media.forEach(item => { const card = C.renderMediaCard(item, state.data); if (card) container.appendChild(card); }); }
  function setupFilters() { const category = document.getElementById("category-filter"); C.clear(category); category.appendChild(C.el("option", { value: "" }, C.t("all"))); state.data.categories.forEach(row => category.appendChild(C.el("option", { value: row.id }, C.taxonomyName(row)))); }
  function tabMatch(item) { if (state.tab === "all") return true; if (state.tab === "campaign") return item.content_type === "campaign"; if (state.tab === "merchant_offer") return item.content_type === "merchant_offer"; if (state.tab === "posts") return item.source_type === "social"; if (state.tab === "review") return item.review_required || item.content_type === "review"; return true; }
  function filtered() { const q = state.filters.q.toLowerCase(); return rows().filter(item => item.active !== false && tabMatch(item) && (!q || `${item.title} ${item.snippet}`.toLowerCase().includes(q)) && (!state.filters.category || item.campaign_category === state.filters.category) && (!state.filters.status || item.current_status === state.filters.status)); }
  function renderList() { const result = filtered(); document.getElementById("result-count").textContent = `${result.length} ${C.t("results")}`; const container = document.getElementById("item-list"); C.clear(container); if (!result.length) return container.appendChild(C.el("div", { class: "empty-state" }, C.t("noData"))); result.forEach(item => container.appendChild(C.renderItemCard(item, state.data, { media: false }))); }
  function renderSources() { const container = document.getElementById("source-list"); C.clear(container); state.data.source_status.filter(row => row.competitor_id === state.competitor.id).forEach(status => container.appendChild(C.sourceRow(status, state.data))); }
  function bind() { document.getElementById("content-tabs").onclick = event => { const button = event.target.closest("button[data-type]"); if (!button) return; state.tab = button.dataset.type; document.querySelectorAll("#content-tabs .tab").forEach(node => node.classList.toggle("is-active", node === button)); renderList(); }; document.getElementById("search").oninput = event => { state.filters.q = event.target.value; renderList(); }; document.getElementById("category-filter").onchange = event => { state.filters.category = event.target.value; renderList(); }; document.getElementById("status-filter").onchange = event => { state.filters.status = event.target.value; renderList(); }; document.getElementById("clear-filters").onclick = () => { state.filters = { q: "", category: "", status: "" }; ["search", "category-filter", "status-filter"].forEach(id => document.getElementById(id).value = ""); renderList(); }; document.getElementById("export-edits").onclick = C.exportOverrides; }
  function renderAll() { hero(); renderFeaturedOffers(); renderAiSummary(); renderAiDetails(); renderKpis(); renderScoreDetail(); renderCompetitorExpiry(); renderCompetitorHistory(); renderSignals(); renderCharts(); renderMedia(); setupFilters(); renderList(); renderSources(); }
  async function init() { C.initLanguage(); try { [state.data, state.ai, state.intel] = await Promise.all([C.loadData(), C.loadAiSummary(), C.loadIntelligence()]); state.competitor = C.byId(state.data.competitors)[params.get("id")] || state.data.competitors[0]; if (!state.competitor) throw new Error("No competitor data"); document.getElementById("loading").hidden = true; document.getElementById("content").hidden = false; renderAll(); bind(); window.addEventListener("cm:language", () => location.reload()); } catch (error) { document.getElementById("loading").hidden = true; C.showError(document.getElementById("error"), error); } }
  document.addEventListener("DOMContentLoaded", init);
})();
