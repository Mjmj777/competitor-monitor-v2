(() => {
  "use strict";
  const C = window.CM;
  const state = { data: null, tab: "all", search: "", competitor: "all", category: "all", source: "all" };

  function kpi(label, value, detail, kind = "default") {
    return C.el("article", { class: `kpi-card kpi-card--${kind}` }, C.el("span", { class: "kpi-card__label" }, label), C.el("strong", {}, String(value)), C.el("small", {}, detail || ""));
  }

  function renderHeader() {
    const ageHours = (Date.now() - new Date(state.data.generated_at).getTime()) / 3600000;
    document.getElementById("freshness").textContent = C.t(ageHours <= 2 ? "dataFresh" : "dataStale");
    document.getElementById("freshness").className = `status-chip ${ageHours <= 2 ? "status-chip--success" : "status-chip--warning"}`;
    document.getElementById("last-check").textContent = `${C.t("lastCheck")}: ${C.timeAgo(state.data.generated_at)}`;
    document.getElementById("source-health").textContent = `${state.data.stats.healthy_sources}/${state.data.stats.total_sources} ${C.t("sourceHealth")}`;
  }

  function renderAlerts() {
    const list = document.getElementById("alerts-list");
    C.clear(list);
    const alerts = C.alertsSince(C.activeItems(state.data.items));
    document.getElementById("alert-count").textContent = alerts.length;
    if (!alerts.length) return list.appendChild(C.el("div", { class: "empty-state" }, C.t("noAlerts")));
    alerts.slice(0, 16).forEach(item => {
      const comp = C.byId(state.data.competitors)[item.competitor_id];
      list.appendChild(C.el("a", { class: `alert-row alert-row--${item.review_required ? "warning" : "info"}`, href: `item.html?id=${encodeURIComponent(item.id)}` },
        C.el("span", { class: "alert-row__icon" }, item.review_required ? "!" : "↗"),
        C.el("span", { class: "alert-row__body" }, C.el("strong", {}, C.alertLabel(item)), C.el("span", {}, `${C.competitorName(comp)} · ${item.title}`)),
        C.el("time", {}, C.timeAgo(item.last_changed))
      ));
    });
  }

  function renderKpis() {
    const grid = document.getElementById("kpi-grid"); C.clear(grid);
    const s = state.data.stats;
    grid.append(
      kpi(C.t("confirmedOffers"), s.confirmed_offers, C.t("offerDefinitionNote"), "success"),
      kpi(C.t("partnerDiscounts"), s.partner_offers, C.t("partnerOffers"), "partner"),
      kpi(C.t("socialPosts7d"), s.social_posts_7d, C.t("channelActivity7d"), "info"),
      kpi(C.t("needsReview"), s.review_required, C.t("dataQuality"), s.review_required ? "warning" : "success"),
      kpi(C.t("sourceHealth"), `${s.healthy_sources}/${s.total_sources}`, `${s.failed_sources} ${C.t("failed")}`, s.failed_sources ? "warning" : "success")
    );
  }

  function renderCharts() {
    const comps = state.data.competitors;
    const items = C.activeItems(state.data.items);
    C.renderBarChart(document.getElementById("offers-chart"), comps.map(c => ({ label: C.competitorName(c), value: items.filter(i => i.competitor_id === c.id && C.isConfirmedOffer(i)).length })));
    C.renderBarChart(document.getElementById("partner-chart"), comps.map(c => ({ label: C.competitorName(c), value: items.filter(i => i.competitor_id === c.id && C.isPartnerOffer(i)).length })));
    C.renderLineChart(document.getElementById("activity-chart"), [
      { label: C.t("social"), items: items.filter(i => i.source_type === "social") },
      { label: C.t("offers"), items: items.filter(i => i.source_type === "website" && ["offer", "partner_offer"].includes(i.content_type)) }
    ], 30);
    C.renderChannelMatrix(document.getElementById("channel-matrix"), comps, items);
    C.renderHeatmap(document.getElementById("heatmap"), comps, state.data.categories, items);
  }

  function strongestCategory(compItems) {
    const cats = C.byId(state.data.categories);
    const counts = C.countBy(compItems.filter(C.isConfirmedOffer), i => i.categories || []);
    const top = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
    return top && cats[top[0]] ? C.taxonomyName(cats[top[0]]) : "—";
  }

  function topChannel(compItems) {
    const counts = C.countBy(compItems.filter(i => i.source_type === "social" && C.withinDays(i, 7)), i => i.platform);
    const top = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
    return top ? `${C.platformLabel(top[0])} (${top[1]})` : "—";
  }

  function renderCompetitors() {
    const grid = document.getElementById("competitor-grid"); C.clear(grid);
    const items = C.activeItems(state.data.items);
    state.data.competitors.forEach(comp => {
      const rows = items.filter(i => i.competitor_id === comp.id);
      grid.appendChild(C.el("article", { class: "competitor-card" },
        C.el("div", { class: "competitor-card__head" }, C.el("h3", {}, C.competitorName(comp)), C.el("a", { href: `competitor.html?id=${encodeURIComponent(comp.id)}` }, C.t("viewCompetitor"))),
        C.el("div", { class: "mini-kpis" },
          C.el("span", {}, C.el("strong", {}, String(rows.filter(C.isConfirmedOffer).length)), C.t("confirmedOffers")),
          C.el("span", {}, C.el("strong", {}, String(rows.filter(C.isPartnerOffer).length)), C.t("partnerDiscounts")),
          C.el("span", {}, C.el("strong", {}, String(rows.filter(i => i.source_type === "social" && C.withinDays(i, 7)).length)), C.t("socialPosts7d"))
        ),
        C.el("dl", { class: "compact-dl" }, C.el("div", {}, C.el("dt", {}, C.t("strongestFocus")), C.el("dd", {}, strongestCategory(rows))), C.el("div", {}, C.el("dt", {}, C.t("topChannel")), C.el("dd", {}, topChannel(rows))))
      ));
    });
  }

  function renderMedia() {
    const grid = document.getElementById("media-grid"); C.clear(grid);
    const rows = C.activeItems(state.data.items).filter(i => i.source_type === "social" && i.media?.url).sort((a, b) => new Date(b.published_at || b.last_changed) - new Date(a.published_at || a.last_changed)).slice(0, 12);
    if (!rows.length) return grid.appendChild(C.el("div", { class: "empty-state" }, C.t("noMedia")));
    rows.forEach(item => { const card = C.renderMediaCard(item, state.data); if (card) grid.appendChild(card); });
  }

  function option(value, label) { return C.el("option", { value }, label); }
  function populateFilters() {
    const comp = document.getElementById("competitor-filter"), cat = document.getElementById("category-filter"), source = document.getElementById("source-filter");
    C.clear(comp); C.clear(cat); C.clear(source);
    comp.append(option("all", C.t("all")), ...state.data.competitors.map(c => option(c.id, C.competitorName(c))));
    cat.append(option("all", C.t("all")), ...state.data.categories.map(c => option(c.id, C.taxonomyName(c))));
    source.append(option("all", C.t("all")), option("website", C.t("website")), option("social", C.t("social")));
    comp.value = state.competitor; cat.value = state.category; source.value = state.source;
  }

  function tabMatch(item) {
    if (state.tab === "all") return true;
    if (state.tab === "posts") return item.source_type === "social" && !["offer", "partner_offer"].includes(item.content_type);
    if (state.tab === "review") return item.review_required;
    return item.content_type === state.tab;
  }
  function filteredItems() {
    const q = state.search.trim().toLocaleLowerCase();
    return C.activeItems(state.data.items).filter(item => {
      if (!tabMatch(item)) return false;
      if (state.competitor !== "all" && item.competitor_id !== state.competitor) return false;
      if (state.category !== "all" && !(item.categories || []).includes(state.category)) return false;
      if (state.source !== "all" && item.source_type !== state.source) return false;
      if (q && !`${item.title} ${item.snippet}`.toLocaleLowerCase().includes(q)) return false;
      return true;
    });
  }
  function renderItems() {
    const list = document.getElementById("item-list"); C.clear(list);
    const rows = filteredItems();
    document.getElementById("result-count").textContent = `${rows.length} ${C.t("results")}`;
    if (!rows.length) return list.appendChild(C.el("div", { class: "empty-state" }, C.t("noData")));
    rows.slice(0, 100).forEach(item => list.appendChild(C.renderItemCard(item, state.data, { showMedia: item.source_type === "social" })));
  }

  function renderSources() {
    const list = document.getElementById("source-list"); C.clear(list);
    const comps = C.byId(state.data.competitors);
    state.data.source_status.forEach(src => list.appendChild(C.el("div", { class: "source-row" },
      C.el("strong", {}, C.competitorName(comps[src.competitor_id])),
      C.el("span", {}, `${C.platformLabel(src.platform)} · ${src.item_count}${src.skipped_general_links ? ` · ${C.t("skippedGeneral")}: ${src.skipped_general_links}` : ""}`),
      C.pill(src.success ? C.t("healthy") : C.t("failed"), src.success ? "success" : "warning"),
      src.error ? C.el("code", {}, src.error) : null
    )));
  }

  function renderAll() { renderHeader(); renderAlerts(); renderKpis(); renderCharts(); renderCompetitors(); renderMedia(); populateFilters(); renderItems(); renderSources(); }

  function bind() {
    document.getElementById("mark-reviewed").addEventListener("click", () => { C.markAlertsReviewed(); renderAlerts(); });
    document.getElementById("content-tabs").addEventListener("click", event => {
      const button = event.target.closest("button[data-type]"); if (!button) return;
      state.tab = button.dataset.type; document.querySelectorAll("#content-tabs .tab").forEach(node => node.classList.toggle("is-active", node === button)); renderItems();
    });
    document.getElementById("search").addEventListener("input", event => { state.search = event.target.value; renderItems(); });
    document.getElementById("competitor-filter").addEventListener("change", event => { state.competitor = event.target.value; renderItems(); });
    document.getElementById("category-filter").addEventListener("change", event => { state.category = event.target.value; renderItems(); });
    document.getElementById("source-filter").addEventListener("change", event => { state.source = event.target.value; renderItems(); });
    document.getElementById("clear-filters").addEventListener("click", () => { state.search = ""; state.competitor = state.category = state.source = "all"; document.getElementById("search").value = ""; populateFilters(); renderItems(); });
    window.addEventListener("cm:language", renderAll);
  }

  async function init() {
    C.initLanguage(); bind();
    try { state.data = await C.loadData(); document.getElementById("loading").hidden = true; document.getElementById("content").hidden = false; renderAll(); }
    catch (error) { document.getElementById("loading").hidden = true; C.showError(document.getElementById("error"), error); }
  }
  document.addEventListener("DOMContentLoaded", init);
})();
