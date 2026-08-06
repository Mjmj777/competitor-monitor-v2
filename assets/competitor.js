(() => {
  "use strict";
  const C = window.CM;
  const params = new URLSearchParams(location.search);
  const state = { data: null, competitor: null, tab: "offer", search: "", category: "all", source: "all", status: "active" };

  function items() { return state.data.items.filter(item => item.competitor_id === state.competitor.id); }
  function active() { return C.activeItems(items()); }
  function kpi(label, value, detail, kind = "default") { return C.el("article", { class: `kpi-card kpi-card--${kind}` }, C.el("span", { class: "kpi-card__label" }, label), C.el("strong", {}, String(value)), C.el("small", {}, detail || "")); }

  function renderHero() {
    document.title = `${C.competitorName(state.competitor)} · Competitor Intelligence`;
    document.getElementById("competitor-name").textContent = C.competitorName(state.competitor);
    document.getElementById("competitor-summary").textContent = C.t("offerDefinitionNote");
    document.getElementById("offers-url").href = state.competitor.offers_url || state.competitor.website || "#";
    document.getElementById("website-url").href = state.competitor.website || "#";
    const switcher = document.getElementById("competitor-switcher"); C.clear(switcher);
    state.data.competitors.forEach(comp => switcher.appendChild(C.el("option", { value: comp.id, selected: comp.id === state.competitor.id }, C.competitorName(comp))));
  }

  function renderKpis() {
    const rows = active(); const grid = document.getElementById("kpi-grid"); C.clear(grid);
    grid.append(
      kpi(C.t("confirmedOffers"), rows.filter(C.isConfirmedOffer).length, C.t("offerDefinitionNote"), "success"),
      kpi(C.t("partnerDiscounts"), rows.filter(C.isPartnerOffer).length, C.t("partnerOffers"), "partner"),
      kpi(C.t("socialPosts7d"), rows.filter(i => i.source_type === "social" && C.withinDays(i, 7)).length, C.t("channelActivity7d"), "info"),
      kpi(C.t("needsReview"), rows.filter(i => i.review_required).length, C.t("dataQuality"), rows.some(i => i.review_required) ? "warning" : "success")
    );
  }

  function topCategory(rows) {
    const cats = C.byId(state.data.categories), counts = C.countBy(rows.filter(C.isConfirmedOffer), i => i.categories || []);
    const top = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
    return top && cats[top[0]] ? `${C.taxonomyName(cats[top[0]])} (${top[1]})` : "—";
  }
  function topChannel(rows) {
    const counts = C.countBy(rows.filter(i => i.source_type === "social" && C.withinDays(i, 7)), i => i.platform);
    const top = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]; return top ? `${C.platformLabel(top[0])} (${top[1]})` : "—";
  }
  function renderInsights() {
    const rows = active(), grid = document.getElementById("insight-grid"); C.clear(grid);
    const offerCount = rows.filter(C.isConfirmedOffer).length, partnerCount = rows.filter(C.isPartnerOffer).length, postCount = rows.filter(i => i.source_type === "social" && C.withinDays(i, 7)).length;
    grid.append(
      C.el("article", { class: "insight-card" }, C.el("span", {}, C.t("strongestFocus")), C.el("strong", {}, topCategory(rows)), C.el("p", {}, C.t("confirmedOffers"))),
      C.el("article", { class: "insight-card" }, C.el("span", {}, C.t("topChannel")), C.el("strong", {}, topChannel(rows)), C.el("p", {}, C.t("channelActivity7d"))),
      C.el("article", { class: "insight-card" }, C.el("span", {}, C.t("contentMix")), C.el("strong", {}, `${offerCount} / ${partnerCount} / ${postCount}`), C.el("p", {}, `${C.t("offers")} / ${C.t("partnerOffers")} / ${C.t("posts")}`))
    );
  }

  function renderCharts() {
    const rows = active(), cats = C.byId(state.data.categories);
    const catCounts = C.countBy(rows.filter(C.isConfirmedOffer), i => i.categories || []);
    C.renderBarChart(document.getElementById("category-chart"), [...catCounts.entries()].map(([id, value]) => ({ label: C.taxonomyName(cats[id]) || id, value })).sort((a, b) => b.value - a.value));
    const typeCounts = C.countBy(rows, i => i.content_type);
    C.renderBarChart(document.getElementById("content-chart"), [...typeCounts.entries()].map(([id, value]) => ({ label: C.contentTypeLabel(id), value })).sort((a, b) => b.value - a.value));
    C.renderLineChart(document.getElementById("activity-chart"), [
      { label: C.t("social"), items: rows.filter(i => i.source_type === "social") },
      { label: C.t("offers"), items: rows.filter(i => i.source_type === "website" && ["offer", "partner_offer"].includes(i.content_type)) }
    ], 30);
    const platforms = ["instagram", "facebook", "x", "tiktok"];
    C.renderBarChart(document.getElementById("channel-chart"), platforms.map(platform => ({ label: C.platformLabel(platform), value: rows.filter(i => i.source_type === "social" && i.platform === platform && C.withinDays(i, 7)).length })));
  }

  function renderMedia() {
    const grid = document.getElementById("media-grid"); C.clear(grid);
    const rows = active().filter(i => i.source_type === "social" && i.media?.url).sort((a, b) => new Date(b.published_at || b.last_changed) - new Date(a.published_at || a.last_changed)).slice(0, 12);
    if (!rows.length) return grid.appendChild(C.el("div", { class: "empty-state" }, C.t("noMedia")));
    rows.forEach(item => { const card = C.renderMediaCard(item, state.data); if (card) grid.appendChild(card); });
  }

  function option(value, label) { return C.el("option", { value }, label); }
  function populateFilters() {
    const cat = document.getElementById("category-filter"), source = document.getElementById("source-filter"), status = document.getElementById("status-filter");
    C.clear(cat); C.clear(source); C.clear(status);
    cat.append(option("all", C.t("all")), ...state.data.categories.map(row => option(row.id, C.taxonomyName(row))));
    source.append(option("all", C.t("all")), option("website", C.t("website")), option("social", C.t("social")));
    status.append(option("active", C.t("active")), option("all", C.t("all")), option("inactive", C.t("inactive")));
    cat.value = state.category; source.value = state.source; status.value = state.status;
  }

  function tabMatch(item) {
    if (state.tab === "all") return true;
    if (state.tab === "posts") return item.source_type === "social" && !["offer", "partner_offer"].includes(item.content_type);
    if (state.tab === "review") return item.review_required;
    return item.content_type === state.tab;
  }
  function filtered() {
    const q = state.search.trim().toLocaleLowerCase();
    return items().filter(item => {
      if (!tabMatch(item)) return false;
      if (state.category !== "all" && !(item.categories || []).includes(state.category)) return false;
      if (state.source !== "all" && item.source_type !== state.source) return false;
      if (state.status === "active" && item.active === false) return false;
      if (state.status === "inactive" && item.active !== false) return false;
      if (q && !`${item.title} ${item.snippet}`.toLocaleLowerCase().includes(q)) return false;
      return true;
    });
  }
  function renderItems() {
    const list = document.getElementById("item-list"); C.clear(list); const rows = filtered();
    document.getElementById("result-count").textContent = `${rows.length} ${C.t("results")}`;
    if (!rows.length) return list.appendChild(C.el("div", { class: "empty-state" }, state.tab === "offer" ? C.t("noConfirmedOffers") : state.tab === "partner_offer" ? C.t("noPartnerOffers") : C.t("noData")));
    rows.slice(0, 120).forEach(item => list.appendChild(C.renderItemCard(item, state.data, { showMedia: item.source_type === "social" })));
  }

  function renderSources() {
    const list = document.getElementById("source-list"); C.clear(list);
    state.data.source_status.filter(src => src.competitor_id === state.competitor.id).forEach(src => list.appendChild(C.el("div", { class: "source-row" }, C.el("strong", {}, C.platformLabel(src.platform)), C.el("span", {}, `${src.item_count}${src.skipped_general_links ? ` · ${C.t("skippedGeneral")}: ${src.skipped_general_links}` : ""}`), C.pill(src.success ? C.t("healthy") : C.t("failed"), src.success ? "success" : "warning"), src.error ? C.el("code", {}, src.error) : null)));
  }

  function renderAll() { renderHero(); renderKpis(); renderInsights(); renderCharts(); renderMedia(); populateFilters(); renderItems(); renderSources(); }
  function bind() {
    document.getElementById("competitor-switcher").addEventListener("change", e => { location.href = `competitor.html?id=${encodeURIComponent(e.target.value)}`; });
    document.getElementById("content-tabs").addEventListener("click", e => { const b = e.target.closest("button[data-type]"); if (!b) return; state.tab = b.dataset.type; document.querySelectorAll("#content-tabs .tab").forEach(n => n.classList.toggle("is-active", n === b)); renderItems(); });
    document.getElementById("search").addEventListener("input", e => { state.search = e.target.value; renderItems(); });
    document.getElementById("category-filter").addEventListener("change", e => { state.category = e.target.value; renderItems(); });
    document.getElementById("source-filter").addEventListener("change", e => { state.source = e.target.value; renderItems(); });
    document.getElementById("status-filter").addEventListener("change", e => { state.status = e.target.value; renderItems(); });
    document.getElementById("clear-filters").addEventListener("click", () => { state.search = ""; state.category = state.source = "all"; state.status = "active"; document.getElementById("search").value = ""; populateFilters(); renderItems(); });
    window.addEventListener("cm:language", renderAll);
  }

  async function init() {
    C.initLanguage(); bind();
    try {
      state.data = await C.loadData();
      state.competitor = state.data.competitors.find(c => c.id === params.get("id")) || state.data.competitors[0];
      if (!state.competitor) throw new Error("Competitor not found");
      document.getElementById("loading").hidden = true; document.getElementById("content").hidden = false; renderAll();
    } catch (error) { document.getElementById("loading").hidden = true; C.showError(document.getElementById("error"), error); }
  }
  document.addEventListener("DOMContentLoaded", init);
})();
