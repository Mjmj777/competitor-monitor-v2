(() => {
  "use strict";

  const STORAGE_LANGUAGE = "competitor_intelligence_language";
  const STORAGE_READ_IDS = "competitor_intelligence_read_ids";
  const PALETTE = ["#2f6bff", "#00a58e", "#f5a524", "#8b5cf6", "#ef5da8", "#64748b", "#e76f51", "#14b8a6", "#84cc16", "#f97316", "#a855f7"];

  const I18N = {
    ar: {
      appTitle: "رصد وتحليل المنافسين",
      appSubtitle: "لوحة تحليلية للعروض والحملات في قطاع المدفوعات الرقمية",
      overview: "نظرة عامة",
      competitors: "المنافسون",
      competitor: "المنافس",
      latestUpdates: "أحدث التحديثات",
      strategicOnly: "العروض المرتبطة بمنتجاتنا فقط",
      allOffers: "جميع العروض",
      filters: "الفلاتر",
      category: "التصنيف",
      source: "المصدر",
      status: "الحالة",
      search: "بحث",
      searchPlaceholder: "ابحث في اسم العرض أو المنافس…",
      all: "الكل",
      active: "نشط",
      inactive: "غير نشط",
      website: "الموقع الرسمي",
      social: "السوشيال ميديا",
      openOffer: "فتح العرض",
      openPost: "فتح المنشور",
      openAnalysis: "فتح التحليل",
      officialOffers: "صفحة العروض الرسمية",
      officialWebsite: "الموقع الرسمي",
      lastCheck: "آخر فحص",
      generated: "تم التحديث",
      new: "جديد",
      updated: "محدّث",
      read: "مقروء",
      unread: "غير مقروء",
      noData: "لا توجد بيانات مطابقة للفلاتر الحالية.",
      loadError: "تعذر تحميل data.json. تأكد من نجاح GitHub Actions ونشر GitHub Pages.",
      retry: "إعادة المحاولة",
      activeStrategicOffers: "العروض الاستراتيجية النشطة",
      newUpdates: "جديد أو محدّث",
      activeCompetitors: "منافسون لديهم نشاط",
      sourceHealth: "سلامة المصادر",
      offersByCompetitor: "العروض حسب المنافس",
      categoryMix: "توزيع التصنيفات",
      activityTrend: "نشاط آخر 30 يومًا",
      channelMix: "توزيع القنوات",
      sourceCoverage: "تغطية المصادر",
      items: "عرض/منشور",
      strategicShare: "نسبة العروض الاستراتيجية",
      topCategory: "التصنيف الأبرز",
      activeOffers: "العروض النشطة",
      totalHistory: "إجمالي السجل",
      platformCoverage: "القنوات المستخدمة",
      analysisSummary: "ملخص تحليلي",
      strongestFocus: "أبرز تركيز حالي",
      recentActivity: "النشاط الحديث",
      channelDiversity: "تنوع القنوات",
      offerList: "قائمة العروض والمنشورات",
      title: "العنوان",
      categories: "التصنيفات",
      platform: "المنصة",
      detected: "تاريخ الرصد",
      changed: "آخر تغيير",
      version: "الإصدار",
      backToOverview: "العودة للنظرة العامة",
      competitorNotFound: "لم يتم العثور على المنافس المطلوب.",
      sourcesOk: "مصدر يعمل",
      sourcesFailed: "مصدر متعثر",
      noRecentActivity: "لا يوجد نشاط جديد خلال آخر 30 يومًا.",
      oneChannel: "قناة واحدة",
      multipleChannels: "قنوات متعددة",
      strategicDominant: "أغلب نشاط المنافس مرتبط بمنتجاتنا المستهدفة.",
      merchantDominant: "أغلب النشاط الحالي عبارة عن عروض تجار أو محتوى عام.",
      balancedMix: "المزيج الحالي متوازن بين العروض الاستراتيجية وعروض التجار.",
      language: "English",
      strategic: "استراتيجي",
      referenceOnly: "مرجعي",
      failedSourcesNotice: "بعض المصادر لم تستجب في آخر فحص، وتم الاحتفاظ بآخر بيانات ناجحة.",
      liveStatus: "حالة الرصد",
      dataFresh: "البيانات محدثة",
      dataStale: "البيانات قديمة",
      days: "يوم",
      hours: "ساعة",
      minutes: "دقيقة",
      now: "الآن",
      instagram: "إنستغرام",
      facebook: "فيسبوك",
      x: "X",
      tiktok: "تيك توك",
      count: "العدد",
      share: "النسبة",
      sourceDetails: "تفاصيل المصادر",
      healthy: "يعمل",
      failed: "متعثر",
      classificationNote: "التصنيف آلي بالاعتماد على كلمات العرض، ويمكن تعديله من config.json.",
      noStrategicOffers: "لا توجد عروض استراتيجية مرصودة حاليًا لهذا المنافس.",
      filteredResults: "النتائج المطابقة",
      clearFilters: "مسح الفلاتر",
      currentActivity: "النشاط الحالي",
      historical: "تاريخي",
      last30Days: "آخر 30 يومًا",
      campaignTimeline: "الخط الزمني للنشاط",
      refreshPage: "تحديث الصفحة",
      goHome: "الرئيسية"
    },
    en: {
      appTitle: "Competitor Intelligence Monitor",
      appSubtitle: "Analytical dashboard for offers and campaigns in digital payments",
      overview: "Overview",
      competitors: "Competitors",
      competitor: "Competitor",
      latestUpdates: "Latest updates",
      strategicOnly: "Offers related to our products only",
      allOffers: "All offers",
      filters: "Filters",
      category: "Category",
      source: "Source",
      status: "Status",
      search: "Search",
      searchPlaceholder: "Search offers or competitors…",
      all: "All",
      active: "Active",
      inactive: "Inactive",
      website: "Official website",
      social: "Social media",
      openOffer: "Open offer",
      openPost: "Open post",
      openAnalysis: "Open analysis",
      officialOffers: "Official offers page",
      officialWebsite: "Official website",
      lastCheck: "Last check",
      generated: "Updated",
      new: "New",
      updated: "Updated",
      read: "Read",
      unread: "Unread",
      noData: "No data matches the current filters.",
      loadError: "Unable to load data.json. Confirm that GitHub Actions and GitHub Pages deployment succeeded.",
      retry: "Retry",
      activeStrategicOffers: "Active strategic offers",
      newUpdates: "New or updated",
      activeCompetitors: "Competitors with activity",
      sourceHealth: "Source health",
      offersByCompetitor: "Offers by competitor",
      categoryMix: "Category mix",
      activityTrend: "Activity over 30 days",
      channelMix: "Channel mix",
      sourceCoverage: "Source coverage",
      items: "offers/posts",
      strategicShare: "Strategic offer share",
      topCategory: "Leading category",
      activeOffers: "Active offers",
      totalHistory: "Total history",
      platformCoverage: "Channels used",
      analysisSummary: "Analysis summary",
      strongestFocus: "Current strongest focus",
      recentActivity: "Recent activity",
      channelDiversity: "Channel diversity",
      offerList: "Offers and posts",
      title: "Title",
      categories: "Categories",
      platform: "Platform",
      detected: "First detected",
      changed: "Last changed",
      version: "Version",
      backToOverview: "Back to overview",
      competitorNotFound: "The requested competitor was not found.",
      sourcesOk: "healthy sources",
      sourcesFailed: "failed sources",
      noRecentActivity: "No new activity during the last 30 days.",
      oneChannel: "One channel",
      multipleChannels: "Multiple channels",
      strategicDominant: "Most current activity relates to the targeted products.",
      merchantDominant: "Most current activity consists of merchant offers or general content.",
      balancedMix: "The current mix is balanced between strategic and merchant offers.",
      language: "العربية",
      strategic: "Strategic",
      referenceOnly: "Reference",
      failedSourcesNotice: "Some sources did not respond in the latest check. The last successful data was retained.",
      liveStatus: "Monitoring status",
      dataFresh: "Data is fresh",
      dataStale: "Data may be stale",
      days: "days",
      hours: "hours",
      minutes: "minutes",
      now: "Now",
      instagram: "Instagram",
      facebook: "Facebook",
      x: "X",
      tiktok: "TikTok",
      count: "Count",
      share: "Share",
      sourceDetails: "Source details",
      healthy: "Healthy",
      failed: "Failed",
      classificationNote: "Classification is automatic based on offer keywords and can be adjusted in config.json.",
      noStrategicOffers: "No strategic offers are currently detected for this competitor.",
      filteredResults: "Matching results",
      clearFilters: "Clear filters",
      currentActivity: "Current activity",
      historical: "Historical",
      last30Days: "Last 30 days",
      campaignTimeline: "Activity timeline",
      refreshPage: "Refresh page",
      goHome: "Home"
    }
  };

  function currentLanguage() {
    return localStorage.getItem(STORAGE_LANGUAGE) || "ar";
  }

  function t(key) {
    const lang = currentLanguage();
    return I18N[lang]?.[key] ?? I18N.en[key] ?? key;
  }

  function applyTranslations(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((node) => {
      node.textContent = t(node.dataset.i18n);
    });
    root.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
      node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
    });
    root.querySelectorAll("[data-i18n-title]").forEach((node) => {
      node.setAttribute("title", t(node.dataset.i18nTitle));
    });
  }

  function setLanguage(language, emit = true) {
    const lang = language === "en" ? "en" : "ar";
    localStorage.setItem(STORAGE_LANGUAGE, lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    applyTranslations();
    const toggle = document.querySelector("[data-language-toggle]");
    if (toggle) toggle.textContent = t("language");
    if (emit) window.dispatchEvent(new CustomEvent("cm:language", { detail: { language: lang } }));
  }

  function initializeLanguage() {
    setLanguage(currentLanguage(), false);
    document.querySelectorAll("[data-language-toggle]").forEach((button) => {
      button.addEventListener("click", () => setLanguage(currentLanguage() === "ar" ? "en" : "ar"));
    });
  }

  async function loadData() {
    const response = await fetch(`data.json?_=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.items) || !Array.isArray(data.competitors)) {
      throw new Error("Invalid data.json schema");
    }
    return data;
  }

  function el(tag, attributes = {}, ...children) {
    const node = document.createElement(tag);
    Object.entries(attributes || {}).forEach(([key, value]) => {
      if (value === null || value === undefined || value === false) return;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key === "html") node.innerHTML = value;
      else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
      else if (key === "dataset") Object.entries(value).forEach(([dataKey, dataValue]) => (node.dataset[dataKey] = dataValue));
      else if (value === true) node.setAttribute(key, "");
      else node.setAttribute(key, String(value));
    });
    children.flat(Infinity).forEach((child) => {
      if (child === null || child === undefined || child === false) return;
      node.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
    });
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function competitorName(competitor) {
    return currentLanguage() === "ar" ? competitor?.name_ar : competitor?.name_en;
  }

  function categoryName(category) {
    return currentLanguage() === "ar" ? category?.name_ar : category?.name_en;
  }

  function platformName(platform) {
    return t(platform || "website");
  }

  function locale() {
    return currentLanguage() === "ar" ? "ar-SA" : "en-GB";
  }

  function formatDate(value, options = {}) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    return new Intl.DateTimeFormat(locale(), {
      day: "numeric",
      month: "short",
      year: options.withYear === false ? undefined : "numeric",
      hour: options.withTime ? "2-digit" : undefined,
      minute: options.withTime ? "2-digit" : undefined
    }).format(date);
  }

  function timeAgo(value) {
    if (!value) return "—";
    const diff = Math.max(0, Date.now() - new Date(value).getTime());
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return t("now");
    if (minutes < 60) return `${minutes} ${t("minutes")}`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} ${t("hours")}`;
    return `${Math.floor(hours / 24)} ${t("days")}`;
  }

  function isNew(item, badgeHours = 24) {
    const reference = item.last_changed || item.first_seen;
    if (!reference) return false;
    return Date.now() - new Date(reference).getTime() <= badgeHours * 3600000;
  }

  function getReadIds() {
    try {
      return new Set(JSON.parse(localStorage.getItem(STORAGE_READ_IDS) || "[]"));
    } catch (_) {
      return new Set();
    }
  }

  function markRead(id) {
    const read = getReadIds();
    read.add(id);
    localStorage.setItem(STORAGE_READ_IDS, JSON.stringify([...read]));
  }

  function mapById(items) {
    return new Map((items || []).map((item) => [item.id, item]));
  }

  function activeItems(items) {
    return (items || []).filter((item) => item.active !== false);
  }

  function filterItems(items, filters = {}) {
    const query = (filters.query || "").trim().toLocaleLowerCase();
    return (items || []).filter((item) => {
      if (filters.competitorId && item.competitor_id !== filters.competitorId) return false;
      if (filters.strategicOnly && !item.strategic) return false;
      if (filters.categoryId && filters.categoryId !== "all" && !(item.categories || []).includes(filters.categoryId)) return false;
      if (filters.sourceType && filters.sourceType !== "all" && item.source_type !== filters.sourceType) return false;
      if (filters.status === "active" && item.active === false) return false;
      if (filters.status === "inactive" && item.active !== false) return false;
      if (query) {
        const haystack = `${item.title || ""} ${item.snippet || ""} ${item.competitor_id || ""}`.toLocaleLowerCase();
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
  }

  function countBy(items, keyFn) {
    const counts = new Map();
    items.forEach((item) => {
      const key = keyFn(item);
      if (Array.isArray(key)) {
        key.forEach((entry) => counts.set(entry, (counts.get(entry) || 0) + 1));
      } else if (key !== null && key !== undefined) {
        counts.set(key, (counts.get(key) || 0) + 1);
      }
    });
    return counts;
  }

  function percent(part, total) {
    return total ? Math.round((part / total) * 100) : 0;
  }

  function renderBarChart(container, rows, options = {}) {
    clear(container);
    if (!rows.length) {
      container.appendChild(el("div", { class: "empty-state", text: t("noData") }));
      return;
    }
    const max = Math.max(...rows.map((row) => row.value), 1);
    const wrapper = el("div", { class: "bar-chart" });
    rows.forEach((row, index) => {
      const bar = el("div", { class: "bar-chart__bar" });
      bar.style.width = `${Math.max(2, (row.value / max) * 100)}%`;
      bar.style.setProperty("--bar-color", PALETTE[index % PALETTE.length]);
      const line = el("div", { class: "bar-chart__row" },
        el("div", { class: "bar-chart__label", text: row.label }),
        el("div", { class: "bar-chart__track" }, bar),
        el("div", { class: "bar-chart__value", text: options.suffix ? `${row.value}${options.suffix}` : String(row.value) })
      );
      if (row.href) {
        line.classList.add("is-clickable");
        line.addEventListener("click", () => (window.location.href = row.href));
      }
      wrapper.appendChild(line);
    });
    container.appendChild(wrapper);
  }

  function renderDonutChart(container, rows) {
    clear(container);
    const total = rows.reduce((sum, row) => sum + row.value, 0);
    if (!rows.length || total === 0) {
      container.appendChild(el("div", { class: "empty-state", text: t("noData") }));
      return;
    }
    let cursor = 0;
    const stops = rows.map((row, index) => {
      const start = cursor;
      cursor += (row.value / total) * 360;
      return `${PALETTE[index % PALETTE.length]} ${start}deg ${cursor}deg`;
    });
    const donut = el("div", { class: "donut-chart" },
      el("div", { class: "donut-chart__center" },
        el("strong", { text: String(total) }),
        el("span", { text: t("items") })
      )
    );
    donut.style.background = `conic-gradient(${stops.join(",")})`;
    const legend = el("div", { class: "chart-legend" });
    rows.forEach((row, index) => {
      const swatch = el("span", { class: "chart-legend__swatch" });
      swatch.style.background = PALETTE[index % PALETTE.length];
      legend.appendChild(el("div", { class: "chart-legend__item" },
        swatch,
        el("span", { class: "chart-legend__label", text: row.label }),
        el("strong", { text: `${row.value} (${percent(row.value, total)}%)` })
      ));
    });
    container.appendChild(el("div", { class: "donut-layout" }, donut, legend));
  }

  function renderLineChart(container, rows) {
    clear(container);
    if (!rows.length || rows.every((row) => row.value === 0)) {
      container.appendChild(el("div", { class: "empty-state", text: t("noRecentActivity") }));
      return;
    }
    const width = 720;
    const height = 240;
    const padding = { top: 18, right: 16, bottom: 46, left: 38 };
    const max = Math.max(...rows.map((row) => row.value), 1);
    const xStep = rows.length > 1 ? (width - padding.left - padding.right) / (rows.length - 1) : 0;
    const y = (value) => padding.top + (height - padding.top - padding.bottom) * (1 - value / max);
    const points = rows.map((row, index) => [padding.left + index * xStep, y(row.value)]);
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("class", "line-chart");

    for (let tick = 0; tick <= 4; tick += 1) {
      const value = Math.round((max / 4) * tick);
      const yPos = y(value);
      const line = document.createElementNS(svg.namespaceURI, "line");
      line.setAttribute("x1", padding.left);
      line.setAttribute("x2", width - padding.right);
      line.setAttribute("y1", yPos);
      line.setAttribute("y2", yPos);
      line.setAttribute("class", "line-chart__grid");
      svg.appendChild(line);
      const label = document.createElementNS(svg.namespaceURI, "text");
      label.setAttribute("x", padding.left - 8);
      label.setAttribute("y", yPos + 4);
      label.setAttribute("text-anchor", "end");
      label.setAttribute("class", "line-chart__axis-label");
      label.textContent = String(value);
      svg.appendChild(label);
    }

    const area = document.createElementNS(svg.namespaceURI, "path");
    const pathData = points.map((point, index) => `${index ? "L" : "M"}${point[0]},${point[1]}`).join(" ");
    area.setAttribute("d", `${pathData} L${points.at(-1)[0]},${height - padding.bottom} L${points[0][0]},${height - padding.bottom} Z`);
    area.setAttribute("class", "line-chart__area");
    svg.appendChild(area);

    const path = document.createElementNS(svg.namespaceURI, "path");
    path.setAttribute("d", pathData);
    path.setAttribute("class", "line-chart__path");
    svg.appendChild(path);

    rows.forEach((row, index) => {
      const [xPos, yPos] = points[index];
      const circle = document.createElementNS(svg.namespaceURI, "circle");
      circle.setAttribute("cx", xPos);
      circle.setAttribute("cy", yPos);
      circle.setAttribute("r", "4");
      circle.setAttribute("class", "line-chart__point");
      const title = document.createElementNS(svg.namespaceURI, "title");
      title.textContent = `${row.label}: ${row.value}`;
      circle.appendChild(title);
      svg.appendChild(circle);

      if (index === 0 || index === rows.length - 1 || index % Math.max(1, Math.ceil(rows.length / 6)) === 0) {
        const label = document.createElementNS(svg.namespaceURI, "text");
        label.setAttribute("x", xPos);
        label.setAttribute("y", height - 18);
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("class", "line-chart__axis-label");
        label.textContent = row.label;
        svg.appendChild(label);
      }
    });
    container.appendChild(svg);
  }

  function trendRows(items, days = 30) {
    const result = [];
    const dateFormat = new Intl.DateTimeFormat(locale(), { day: "numeric", month: "short" });
    for (let offset = days - 1; offset >= 0; offset -= 1) {
      const date = new Date();
      date.setHours(0, 0, 0, 0);
      date.setDate(date.getDate() - offset);
      const next = new Date(date);
      next.setDate(next.getDate() + 1);
      const value = items.filter((item) => {
        const timestamp = new Date(item.last_changed || item.first_seen || 0).getTime();
        return timestamp >= date.getTime() && timestamp < next.getTime();
      }).length;
      result.push({ label: dateFormat.format(date), value });
    }
    return result;
  }

  function renderPill(text, kind = "neutral") {
    return el("span", { class: `pill pill--${kind}`, text });
  }

  function itemStatusPills(item, data) {
    const pills = [];
    if (isNew(item, data.new_badge_hours)) pills.push(renderPill(t(item.version > 1 ? "updated" : "new"), "new"));
    pills.push(renderPill(t(item.strategic ? "strategic" : "referenceOnly"), item.strategic ? "strategic" : "reference"));
    if (item.active === false) pills.push(renderPill(t("inactive"), "inactive"));
    return pills;
  }

  function renderItemCard(item, data, options = {}) {
    const competitors = mapById(data.competitors);
    const categories = mapById(data.categories);
    const readIds = getReadIds();
    const card = el("article", { class: `offer-card${readIds.has(item.id) ? " is-read" : ""}` });
    const tags = el("div", { class: "offer-card__tags" });
    itemStatusPills(item, data).forEach((pill) => tags.appendChild(pill));
    (item.categories || []).slice(0, 3).forEach((id) => {
      const category = categories.get(id);
      if (category) tags.appendChild(renderPill(categoryName(category), "category"));
    });
    const competitor = competitors.get(item.competitor_id);
    const title = el("h3", { class: "offer-card__title", text: item.title || "—" });
    const meta = el("div", { class: "offer-card__meta" },
      el("span", { text: competitorName(competitor) || item.competitor_id }),
      el("span", { text: platformName(item.platform) }),
      el("span", { text: `${t("changed")}: ${formatDate(item.last_changed, { withTime: true })}` })
    );
    const body = el("div", { class: "offer-card__body" }, title, meta);
    if (item.snippet) body.appendChild(el("p", { class: "offer-card__snippet", text: item.snippet }));
    body.appendChild(tags);
    const action = el("a", {
      class: "button button--secondary",
      href: item.link,
      target: "_blank",
      rel: "noopener noreferrer",
      text: t(item.source_type === "social" ? "openPost" : "openOffer"),
      onclick: () => {
        markRead(item.id);
        card.classList.add("is-read");
      }
    });
    card.append(body, el("div", { class: "offer-card__actions" }, action));
    if (options.compact) card.classList.add("offer-card--compact");
    return card;
  }

  function sourceHealthText(data) {
    const stats = data.stats || {};
    return `${stats.healthy_sources || 0} ${t("sourcesOk")} · ${stats.failed_sources || 0} ${t("sourcesFailed")}`;
  }

  function freshnessStatus(generatedAt) {
    const ageHours = (Date.now() - new Date(generatedAt).getTime()) / 3600000;
    return ageHours <= 2 ? "fresh" : "stale";
  }

  function showLoadError(container, error) {
    clear(container);
    container.appendChild(el("div", { class: "load-error" },
      el("h2", { text: t("loadError") }),
      el("code", { text: error?.message || String(error) }),
      el("button", { class: "button button--primary", type: "button", text: t("retry"), onclick: () => window.location.reload() })
    ));
  }

  window.CM = {
    I18N,
    PALETTE,
    t,
    el,
    clear,
    currentLanguage,
    setLanguage,
    initializeLanguage,
    applyTranslations,
    loadData,
    competitorName,
    categoryName,
    platformName,
    formatDate,
    timeAgo,
    isNew,
    getReadIds,
    markRead,
    mapById,
    activeItems,
    filterItems,
    countBy,
    percent,
    renderBarChart,
    renderDonutChart,
    renderLineChart,
    trendRows,
    renderPill,
    renderItemCard,
    sourceHealthText,
    freshnessStatus,
    showLoadError
  };
})();
