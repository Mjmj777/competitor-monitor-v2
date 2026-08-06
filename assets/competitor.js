(() => {
  "use strict";

  const state = {
    data: null,
    competitor: null,
    filters: {
      strategicOnly: true,
      categoryId: "all",
      sourceType: "all",
      status: "active",
      query: ""
    }
  };

  function competitorItems() {
    return state.data.items.filter((item) => item.competitor_id === state.competitor.id);
  }

  function filteredItems() {
    return CM.filterItems(competitorItems(), {
      ...state.filters,
      competitorId: state.competitor.id
    }).sort((a, b) => new Date(b.last_changed || b.first_seen) - new Date(a.last_changed || a.first_seen));
  }

  function setText(id, text) {
    const node = document.getElementById(id);
    if (node) node.textContent = text;
  }

  function renderHeader() {
    document.title = `${CM.competitorName(state.competitor)} | ${CM.t("appTitle")}`;
    setText("competitor-name", CM.competitorName(state.competitor));
    setText("competitor-subtitle", `${CM.t("analysisSummary")} · ${CM.t("lastCheck")}: ${CM.formatDate(state.data.generated_at, { withTime: true })}`);

    const officialOffers = document.getElementById("official-offers-link");
    officialOffers.href = state.competitor.offers_url || state.competitor.website;
    officialOffers.textContent = CM.t("officialOffers");

    const website = document.getElementById("official-website-link");
    website.href = state.competitor.website;
    website.textContent = CM.t("officialWebsite");

    const select = document.getElementById("competitor-switcher");
    const current = state.competitor.id;
    CM.clear(select);
    state.data.competitors.forEach((competitor) => {
      select.appendChild(CM.el("option", {
        value: competitor.id,
        text: CM.competitorName(competitor)
      }));
    });
    select.value = current;
  }

  function kpiCard(label, value, detail, kind) {
    return CM.el("article", { class: `kpi-card kpi-card--${kind}` },
      CM.el("span", { class: "kpi-card__label", text: label }),
      CM.el("strong", { class: "kpi-card__value", text: String(value) }),
      CM.el("small", { class: "kpi-card__detail", text: detail })
    );
  }

  function currentMetrics() {
    const all = competitorItems();
    const active = CM.activeItems(all);
    const strategic = active.filter((item) => item.strategic);
    const categories = CM.countBy(strategic, (item) => item.primary_category);
    const topCategoryEntry = [...categories.entries()].sort((a, b) => b[1] - a[1])[0];
    const categoryMap = CM.mapById(state.data.categories);
    const topCategory = topCategoryEntry ? CM.categoryName(categoryMap.get(topCategoryEntry[0])) : "—";
    const channels = new Set(active.map((item) => item.platform));
    const recentCutoff = Date.now() - 30 * 86400000;
    const recent = active.filter((item) => new Date(item.last_changed || item.first_seen).getTime() >= recentCutoff);
    return { all, active, strategic, topCategory, channels, recent };
  }

  function renderKpis() {
    const metrics = currentMetrics();
    const container = document.getElementById("competitor-kpis");
    CM.clear(container);
    container.append(
      kpiCard(CM.t("activeStrategicOffers"), metrics.strategic.length, `${CM.percent(metrics.strategic.length, metrics.active.length)}% ${CM.t("share")}`, "primary"),
      kpiCard(CM.t("newUpdates"), metrics.strategic.filter((item) => CM.isNew(item, state.data.new_badge_hours)).length, `${state.data.new_badge_hours} ${CM.t("hours")}`, "new"),
      kpiCard(CM.t("topCategory"), metrics.topCategory, CM.t("currentActivity"), "success"),
      kpiCard(CM.t("platformCoverage"), metrics.channels.size, [...metrics.channels].map(CM.platformName).join(" · ") || "—", "warning")
    );
  }

  function insightCard(label, value, body) {
    return CM.el("article", { class: "insight-card" },
      CM.el("span", { class: "insight-card__label", text: label }),
      CM.el("strong", { class: "insight-card__value", text: value }),
      CM.el("p", { text: body })
    );
  }

  function renderInsights() {
    const metrics = currentMetrics();
    const strategicShare = CM.percent(metrics.strategic.length, metrics.active.length);
    let mixText = CM.t("balancedMix");
    if (strategicShare >= 65) mixText = CM.t("strategicDominant");
    if (strategicShare <= 35) mixText = CM.t("merchantDominant");

    const recentText = metrics.recent.length
      ? `${metrics.recent.length} ${CM.t("items")} · ${CM.t("last30Days")}`
      : CM.t("noRecentActivity");
    const channelText = metrics.channels.size > 1 ? CM.t("multipleChannels") : CM.t("oneChannel");

    const container = document.getElementById("insight-grid");
    CM.clear(container);
    container.append(
      insightCard(CM.t("strongestFocus"), metrics.topCategory, metrics.strategic.length ? mixText : CM.t("noStrategicOffers")),
      insightCard(CM.t("recentActivity"), String(metrics.recent.length), recentText),
      insightCard(CM.t("channelDiversity"), String(metrics.channels.size), `${channelText}: ${[...metrics.channels].map(CM.platformName).join(" · ") || "—"}`)
    );
  }

  function chartItems() {
    const active = CM.activeItems(competitorItems());
    return state.data.default_strategic_only ? active.filter((item) => item.strategic) : active;
  }

  function renderCharts() {
    const categories = CM.mapById(state.data.categories);
    const items = chartItems();
    const categoryRows = [...CM.countBy(items, (item) => item.primary_category).entries()]
      .map(([id, value]) => ({ label: CM.categoryName(categories.get(id)) || id, value }))
      .sort((a, b) => b.value - a.value);
    CM.renderDonutChart(document.getElementById("competitor-category-chart"), categoryRows);

    const channelRows = [...CM.countBy(items, (item) => item.platform).entries()]
      .map(([id, value]) => ({ label: CM.platformName(id), value }))
      .sort((a, b) => b.value - a.value);
    CM.renderBarChart(document.getElementById("competitor-channel-chart"), channelRows);

    CM.renderLineChart(document.getElementById("competitor-trend-chart"), CM.trendRows(items, 30));

    const statusRows = [
      { label: CM.t("active"), value: competitorItems().filter((item) => item.active !== false).length },
      { label: CM.t("historical"), value: competitorItems().filter((item) => item.active === false).length }
    ];
    CM.renderBarChart(document.getElementById("competitor-status-chart"), statusRows);
  }

  function populateFilters() {
    const categorySelect = document.getElementById("category-filter");
    const categoryValue = state.filters.categoryId;
    CM.clear(categorySelect);
    categorySelect.appendChild(CM.el("option", { value: "all", text: CM.t("all") }));
    state.data.categories.forEach((category) => {
      categorySelect.appendChild(CM.el("option", { value: category.id, text: CM.categoryName(category) }));
    });
    categorySelect.value = categoryValue;

    const sourceSelect = document.getElementById("source-filter");
    const sourceValue = state.filters.sourceType;
    CM.clear(sourceSelect);
    sourceSelect.append(
      CM.el("option", { value: "all", text: CM.t("all") }),
      CM.el("option", { value: "website", text: CM.t("website") }),
      CM.el("option", { value: "social", text: CM.t("social") })
    );
    sourceSelect.value = sourceValue;

    const statusSelect = document.getElementById("status-filter");
    const statusValue = state.filters.status;
    CM.clear(statusSelect);
    statusSelect.append(
      CM.el("option", { value: "active", text: CM.t("active") }),
      CM.el("option", { value: "inactive", text: CM.t("inactive") }),
      CM.el("option", { value: "all", text: CM.t("all") })
    );
    statusSelect.value = statusValue;

    document.getElementById("strategic-filter").checked = state.filters.strategicOnly;
    document.getElementById("search-filter").value = state.filters.query;
  }

  function renderOffers() {
    const items = filteredItems();
    setText("result-count", `${CM.t("filteredResults")}: ${items.length}`);
    const container = document.getElementById("competitor-offer-list");
    CM.clear(container);
    if (!items.length) {
      container.appendChild(CM.el("div", { class: "empty-state", text: CM.t("noData") }));
      return;
    }
    items.forEach((item) => container.appendChild(CM.renderItemCard(item, state.data)));
  }

  function renderSourceHealth() {
    const sources = state.data.source_status.filter((source) => source.competitor_id === state.competitor.id);
    const container = document.getElementById("competitor-source-list");
    CM.clear(container);
    sources.forEach((source) => {
      container.appendChild(CM.el("div", { class: "source-status-row" },
        CM.el("div", {},
          CM.el("strong", { text: source.source_type === "website" ? CM.t("website") : CM.platformName(source.platform) }),
          CM.el("small", { text: source.url })
        ),
        CM.renderPill(CM.t(source.success ? "healthy" : "failed"), source.success ? "strategic" : "inactive"),
        CM.el("span", { text: `${source.item_count || 0} ${CM.t("items")}` })
      ));
      if (source.error) container.appendChild(CM.el("p", { class: "source-status-error", text: source.error }));
    });
  }

  function renderAll() {
    CM.applyTranslations();
    renderHeader();
    renderKpis();
    renderInsights();
    renderCharts();
    populateFilters();
    renderOffers();
    renderSourceHealth();
  }

  function bindEvents() {
    document.getElementById("competitor-switcher").addEventListener("change", (event) => {
      window.location.href = `competitor.html?id=${encodeURIComponent(event.target.value)}`;
    });
    document.getElementById("strategic-filter").addEventListener("change", (event) => {
      state.filters.strategicOnly = event.target.checked;
      renderOffers();
    });
    document.getElementById("category-filter").addEventListener("change", (event) => {
      state.filters.categoryId = event.target.value;
      renderOffers();
    });
    document.getElementById("source-filter").addEventListener("change", (event) => {
      state.filters.sourceType = event.target.value;
      renderOffers();
    });
    document.getElementById("status-filter").addEventListener("change", (event) => {
      state.filters.status = event.target.value;
      renderOffers();
    });
    document.getElementById("search-filter").addEventListener("input", (event) => {
      state.filters.query = event.target.value;
      renderOffers();
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
      renderOffers();
    });
  }

  function showNotFound() {
    document.getElementById("app-loading").hidden = true;
    const error = document.getElementById("app-error");
    CM.clear(error);
    error.appendChild(CM.el("div", { class: "load-error" },
      CM.el("h2", { text: CM.t("competitorNotFound") }),
      CM.el("a", { class: "button button--primary", href: "index.html", text: CM.t("goHome") })
    ));
  }

  async function init() {
    CM.initializeLanguage();
    bindEvents();
    try {
      state.data = await CM.loadData();
      const id = new URLSearchParams(window.location.search).get("id");
      state.competitor = state.data.competitors.find((item) => item.id === id);
      if (!state.competitor) {
        showNotFound();
        return;
      }
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
