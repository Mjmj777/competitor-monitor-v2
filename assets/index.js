(() => {
  "use strict";

  const state = {
    data: null,
    filters: {
      strategicOnly: true,
      categoryId: "all",
      sourceType: "all",
      status: "active",
      query: ""
    }
  };

  function setText(id, value) {
    const node = document.getElementById(id);
    if (node) node.textContent = value;
  }

  function renderHeader() {
    const { data } = state;
    setText("last-updated", `${CM.t("lastCheck")}: ${CM.formatDate(data.generated_at, { withTime: true })} (${CM.timeAgo(data.generated_at)})`);
    const freshness = CM.freshnessStatus(data.generated_at);
    const badge = document.getElementById("freshness-badge");
    badge.textContent = CM.t(freshness === "fresh" ? "dataFresh" : "dataStale");
    badge.className = `status-badge status-badge--${freshness}`;
    setText("source-health-label", CM.sourceHealthText(data));
    const failed = (data.stats?.failed_sources || 0) > 0;
    document.getElementById("source-warning").hidden = !failed;
  }

  function kpiCard(label, value, detail, kind) {
    return CM.el("article", { class: `kpi-card kpi-card--${kind}` },
      CM.el("span", { class: "kpi-card__label", text: label }),
      CM.el("strong", { class: "kpi-card__value", text: String(value) }),
      CM.el("small", { class: "kpi-card__detail", text: detail })
    );
  }

  function renderKpis() {
    const { data } = state;
    const active = CM.activeItems(data.items);
    const strategic = active.filter((item) => item.strategic);
    const recent = strategic.filter((item) => CM.isNew(item, data.new_badge_hours));
    const activeCompetitors = new Set(strategic.map((item) => item.competitor_id)).size;
    const healthy = data.stats?.healthy_sources || 0;
    const totalSources = data.stats?.total_sources || 0;
    const healthRate = totalSources ? Math.round((healthy / totalSources) * 100) : 0;

    const container = document.getElementById("kpi-grid");
    CM.clear(container);
    container.append(
      kpiCard(CM.t("activeStrategicOffers"), strategic.length, `${CM.percent(strategic.length, active.length)}% ${CM.t("share")}`, "primary"),
      kpiCard(CM.t("newUpdates"), recent.length, `${data.new_badge_hours} ${CM.t("hours")}`, "new"),
      kpiCard(CM.t("activeCompetitors"), activeCompetitors, `${data.competitors.length} ${CM.t("competitors")}`, "success"),
      kpiCard(CM.t("sourceHealth"), `${healthRate}%`, `${healthy}/${totalSources}`, healthRate >= 90 ? "success" : "warning")
    );
  }

  function analysisItems() {
    const active = CM.activeItems(state.data.items);
    return state.data.default_strategic_only ? active.filter((item) => item.strategic) : active;
  }

  function renderCharts() {
    const { data } = state;
    const items = analysisItems();
    const competitors = CM.mapById(data.competitors);
    const categories = CM.mapById(data.categories);

    const byCompetitor = [...CM.countBy(items, (item) => item.competitor_id).entries()]
      .map(([id, value]) => ({
        label: CM.competitorName(competitors.get(id)) || id,
        value,
        href: `competitor.html?id=${encodeURIComponent(id)}`
      }))
      .sort((a, b) => b.value - a.value);
    CM.renderBarChart(document.getElementById("competitor-chart"), byCompetitor);

    const byCategory = [...CM.countBy(items, (item) => item.primary_category).entries()]
      .map(([id, value]) => ({ label: CM.categoryName(categories.get(id)) || id, value }))
      .sort((a, b) => b.value - a.value);
    CM.renderDonutChart(document.getElementById("category-chart"), byCategory);

    CM.renderLineChart(document.getElementById("trend-chart"), CM.trendRows(items, 30));

    const byChannel = [...CM.countBy(items, (item) => item.platform).entries()]
      .map(([platform, value]) => ({ label: CM.platformName(platform), value }))
      .sort((a, b) => b.value - a.value);
    CM.renderBarChart(document.getElementById("channel-chart"), byChannel);
  }

  function renderCompetitors() {
    const { data } = state;
    const active = CM.activeItems(data.items);
    const categories = CM.mapById(data.categories);
    const container = document.getElementById("competitor-grid");
    CM.clear(container);

    data.competitors.forEach((competitor) => {
      const items = active.filter((item) => item.competitor_id === competitor.id);
      const strategic = items.filter((item) => item.strategic);
      const newCount = strategic.filter((item) => CM.isNew(item, data.new_badge_hours)).length;
      const categoryCounts = [...CM.countBy(strategic, (item) => item.primary_category).entries()].sort((a, b) => b[1] - a[1]);
      const leading = categoryCounts[0] ? CM.categoryName(categories.get(categoryCounts[0][0])) : "—";
      const channels = new Set(items.map((item) => item.platform)).size;

      const card = CM.el("article", { class: "competitor-card" },
        CM.el("div", { class: "competitor-card__head" },
          CM.el("div", {},
            CM.el("span", { class: "eyebrow", text: CM.t("competitor") || CM.t("competitors") }),
            CM.el("h3", { text: CM.competitorName(competitor) })
          ),
          newCount ? CM.renderPill(`${newCount} ${CM.t("new")}`, "new") : null
        ),
        CM.el("div", { class: "competitor-card__metrics" },
          CM.el("div", {}, CM.el("strong", { text: String(strategic.length) }), CM.el("span", { text: CM.t("activeStrategicOffers") })),
          CM.el("div", {}, CM.el("strong", { text: `${CM.percent(strategic.length, items.length)}%` }), CM.el("span", { text: CM.t("strategicShare") })),
          CM.el("div", {}, CM.el("strong", { text: String(channels) }), CM.el("span", { text: CM.t("platformCoverage") }))
        ),
        CM.el("div", { class: "competitor-card__focus" },
          CM.el("span", { text: CM.t("topCategory") }),
          CM.el("strong", { text: leading })
        ),
        CM.el("a", { class: "button button--primary button--full", href: `competitor.html?id=${encodeURIComponent(competitor.id)}`, text: CM.t("openAnalysis") })
      );
      container.appendChild(card);
    });
  }

  function populateFilters() {
    const { data } = state;
    const categorySelect = document.getElementById("category-filter");
    const currentCategory = state.filters.categoryId;
    CM.clear(categorySelect);
    categorySelect.appendChild(CM.el("option", { value: "all", text: CM.t("all") }));
    data.categories.forEach((category) => {
      categorySelect.appendChild(CM.el("option", { value: category.id, text: CM.categoryName(category) }));
    });
    categorySelect.value = currentCategory;

    const sourceSelect = document.getElementById("source-filter");
    const currentSource = state.filters.sourceType;
    CM.clear(sourceSelect);
    sourceSelect.append(
      CM.el("option", { value: "all", text: CM.t("all") }),
      CM.el("option", { value: "website", text: CM.t("website") }),
      CM.el("option", { value: "social", text: CM.t("social") })
    );
    sourceSelect.value = currentSource;

    const statusSelect = document.getElementById("status-filter");
    const currentStatus = state.filters.status;
    CM.clear(statusSelect);
    statusSelect.append(
      CM.el("option", { value: "active", text: CM.t("active") }),
      CM.el("option", { value: "inactive", text: CM.t("inactive") }),
      CM.el("option", { value: "all", text: CM.t("all") })
    );
    statusSelect.value = currentStatus;

    document.getElementById("strategic-filter").checked = state.filters.strategicOnly;
    document.getElementById("search-filter").value = state.filters.query;
  }

  function renderLatest() {
    const { data, filters } = state;
    const filtered = CM.filterItems(data.items, filters).sort(
      (a, b) => new Date(b.last_changed || b.first_seen) - new Date(a.last_changed || a.first_seen)
    );
    setText("result-count", `${CM.t("filteredResults")}: ${filtered.length}`);
    const container = document.getElementById("latest-list");
    CM.clear(container);
    if (!filtered.length) {
      container.appendChild(CM.el("div", { class: "empty-state", text: CM.t("noData") }));
      return;
    }
    filtered.slice(0, 80).forEach((item) => container.appendChild(CM.renderItemCard(item, data, { compact: true })));
  }

  function renderSourceDetails() {
    const { data } = state;
    const container = document.getElementById("source-table-body");
    CM.clear(container);
    data.source_status.forEach((source) => {
      const competitor = data.competitors.find((item) => item.id === source.competitor_id);
      container.appendChild(CM.el("tr", {},
        CM.el("td", { text: CM.competitorName(competitor) || source.competitor_id }),
        CM.el("td", { text: source.source_type === "website" ? CM.t("website") : CM.platformName(source.platform) }),
        CM.el("td", {}, CM.renderPill(CM.t(source.success ? "healthy" : "failed"), source.success ? "strategic" : "inactive")),
        CM.el("td", { text: String(source.item_count || 0) }),
        CM.el("td", { class: "source-error", text: source.error || "—" })
      ));
    });
  }

  function renderAll() {
    if (!state.data) return;
    CM.applyTranslations();
    renderHeader();
    renderKpis();
    renderCharts();
    renderCompetitors();
    populateFilters();
    renderLatest();
    renderSourceDetails();
  }

  function bindFilters() {
    document.getElementById("strategic-filter").addEventListener("change", (event) => {
      state.filters.strategicOnly = event.target.checked;
      renderLatest();
    });
    document.getElementById("category-filter").addEventListener("change", (event) => {
      state.filters.categoryId = event.target.value;
      renderLatest();
    });
    document.getElementById("source-filter").addEventListener("change", (event) => {
      state.filters.sourceType = event.target.value;
      renderLatest();
    });
    document.getElementById("status-filter").addEventListener("change", (event) => {
      state.filters.status = event.target.value;
      renderLatest();
    });
    document.getElementById("search-filter").addEventListener("input", (event) => {
      state.filters.query = event.target.value;
      renderLatest();
    });
    document.getElementById("clear-filters").addEventListener("click", () => {
      state.filters = {
        strategicOnly: state.data.default_strategic_only !== false,
        categoryId: "all",
        sourceType: "all",
        status: "active",
        query: ""
      };
      populateFilters();
      renderLatest();
    });
    document.getElementById("refresh-page").addEventListener("click", () => window.location.reload());
  }

  async function init() {
    CM.initializeLanguage();
    bindFilters();
    try {
      state.data = await CM.loadData();
      state.filters.strategicOnly = state.data.default_strategic_only !== false;
      document.getElementById("app-loading").hidden = true;
      document.getElementById("app-content").hidden = false;
      renderAll();
      window.addEventListener("cm:language", renderAll);
    } catch (error) {
      document.getElementById("app-loading").hidden = true;
      CM.showLoadError(document.getElementById("app-error"), error);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
