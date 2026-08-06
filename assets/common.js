(() => {
  "use strict";

  const STORAGE_LANGUAGE = "cm_language";
  const STORAGE_ALERT_ACK = "cm_alert_acknowledged_at";
  const COLORS = ["#2563eb", "#0f9f8f", "#d97706", "#7c3aed", "#db2777", "#475569"];

  const I18N = {
    ar: {
      appTitle: "رصد وتحليل المنافسين",
      appSubtitle: "لوحة تحليلية للعروض والمنشورات والخصومات في قطاع المدفوعات الرقمية",
      overview: "نظرة عامة",
      alerts: "التنبيهات",
      alertsSubtitle: "كل ما استجد منذ آخر مراجعة",
      noAlerts: "لا توجد تحديثات جديدة منذ آخر مراجعة.",
      markReviewed: "تحديد الكل كمراجع",
      confirmedOffers: "العروض المؤكدة",
      partnerDiscounts: "خصومات الشركاء",
      socialPosts7d: "منشورات آخر 7 أيام",
      needsReview: "بحاجة إلى مراجعة",
      sourceHealth: "سلامة المصادر",
      competitors: "المنافسون",
      categories: "التصنيفات",
      benefits: "نوع المنفعة",
      contentType: "نوع المحتوى",
      status: "الحالة",
      source: "المصدر",
      platform: "المنصة",
      search: "بحث",
      searchPlaceholder: "ابحث باسم العرض أو المنافس…",
      all: "الكل",
      active: "نشط",
      inactive: "غير نشط",
      website: "الموقع الرسمي",
      social: "السوشيال ميديا",
      instagram: "Instagram",
      facebook: "Facebook",
      x: "X",
      tiktok: "TikTok",
      confirmedOffer: "عرض مؤكد",
      partnerOffer: "عرض شريك",
      productPost: "منشور منتج",
      awareness: "توعية",
      generalPost: "منشور عام",
      uncertain: "بحاجة إلى مراجعة",
      openAnalysis: "فتح التحليل",
      openOfficialOffer: "فتح العرض الرسمي",
      openOffersPage: "فتح صفحة العروض",
      openPost: "فتح المنشور",
      directLink: "رابط مباشر",
      generalLink: "رابط عام",
      latestUpdates: "أحدث التحديثات",
      activity30d: "النشاط خلال 30 يومًا",
      channelActivity7d: "نشاط القنوات خلال 7 أيام",
      offersByCompetitor: "العروض المؤكدة حسب المنافس",
      partnerByCompetitor: "خصومات الشركاء حسب المنافس",
      productHeatmap: "خريطة تركيز المنتجات",
      quickView: "نظرة سريعة",
      marketPulse: "نبض السوق",
      lastCheck: "آخر فحص",
      dataFresh: "البيانات محدثة",
      dataStale: "البيانات قديمة",
      loadError: "تعذر تحميل البيانات. تأكد من نجاح GitHub Actions وGitHub Pages.",
      retry: "إعادة المحاولة",
      latestMedia: "أحدث المنشورات المصورة",
      noMedia: "لا توجد صور أو فيديوهات متاحة من المصادر الحالية.",
      offers: "العروض",
      partnerOffers: "خصومات الشركاء",
      posts: "المنشورات",
      reviewQueue: "قائمة المراجعة",
      allContent: "كل المحتوى",
      clearFilters: "مسح الفلاتر",
      results: "نتيجة",
      activeOnly: "النشط فقط",
      firstDetected: "أول رصد",
      lastChanged: "آخر تغيير",
      published: "تاريخ النشر",
      version: "الإصدار",
      confidence: "الثقة",
      high: "مرتفعة",
      medium: "متوسطة",
      low: "منخفضة",
      analysisSummary: "الملخص التحليلي",
      strongestFocus: "أبرز تركيز",
      topChannel: "القناة الأكثر نشاطًا",
      contentMix: "مزيج المحتوى",
      back: "العودة",
      officialWebsite: "الموقع الرسمي",
      officialOffersPage: "صفحة العروض الرسمية",
      noData: "لا توجد بيانات مطابقة.",
      newOffer: "عرض جديد",
      updatedOffer: "عرض تم تحديثه",
      newPartner: "خصم شريك جديد",
      newPost: "منشور جديد",
      reviewAlert: "عنصر يحتاج مراجعة",
      directLinkWarning: "لم يتم العثور على رابط تفصيلي مباشر لهذا العنصر.",
      classificationWarning: "التصنيف غير مؤكد ويحتاج مراجعة بشرية.",
      sourceDetails: "تفاصيل المصادر",
      healthy: "يعمل",
      failed: "متعثر",
      skippedGeneral: "روابط عامة مستبعدة",
      itemTimeline: "سجل التغييرات",
      classification: "التصنيف",
      media: "الوسائط",
      noTimeline: "لا يوجد سجل تغييرات إضافي بعد.",
      baseline: "استيراد أولي",
      detected: "تم الرصد",
      updated: "تم التحديث",
      reactivated: "عاد للنشاط",
      expired: "أصبح غير نشط",
      itemDetails: "تفاصيل العنصر",
      language: "English",
      count: "العدد",
      socialShare: "حصة النشاط الاجتماعي",
      categoryCoverage: "تغطية التصنيفات",
      dataQuality: "جودة البيانات",
      previous7d: "السبعة أيام السابقة",
      current7d: "آخر 7 أيام",
      noRecentActivity: "لا يوجد نشاط مؤرخ خلال الفترة.",
      initialImportNote: "العناصر القديمة التي تم استيرادها أول مرة لا تُحسب كنشاط اليوم ما لم يتوفر تاريخ نشر فعلي.",
      brandNamesNote: "أسماء الشركات ثابتة بالإنجليزية في اللغتين.",
      offerDefinitionNote: "يُحسب العرض فقط عند وجود منفعة واضحة مثل خصم أو كاش باك أو جائزة أو إعفاء من الرسوم.",
      videoUnavailable: "الفيديو غير قابل للتشغيل داخل الصفحة؛ افتح المنشور الأصلي.",
      viewCompetitor: "فتح تحليل المنافس",
      latest: "الأحدث",
      noConfirmedOffers: "لا توجد عروض مؤكدة مرصودة حاليًا.",
      noPartnerOffers: "لا توجد خصومات شركاء مرصودة حاليًا.",
      noPosts: "لا توجد منشورات مطابقة.",
      days: "يوم",
      hours: "ساعة",
      minutes: "دقيقة",
      now: "الآن"
    },
    en: {
      appTitle: "Competitor Intelligence Monitor",
      appSubtitle: "Analytical dashboard for offers, posts, and partner discounts in digital payments",
      overview: "Overview",
      alerts: "Alerts",
      alertsSubtitle: "Everything new since the last review",
      noAlerts: "No new updates since the last review.",
      markReviewed: "Mark all reviewed",
      confirmedOffers: "Confirmed offers",
      partnerDiscounts: "Partner discounts",
      socialPosts7d: "Social posts in 7 days",
      needsReview: "Needs review",
      sourceHealth: "Source health",
      competitors: "Competitors",
      categories: "Categories",
      benefits: "Benefit type",
      contentType: "Content type",
      status: "Status",
      source: "Source",
      platform: "Platform",
      search: "Search",
      searchPlaceholder: "Search offers or competitors…",
      all: "All",
      active: "Active",
      inactive: "Inactive",
      website: "Official website",
      social: "Social media",
      instagram: "Instagram",
      facebook: "Facebook",
      x: "X",
      tiktok: "TikTok",
      confirmedOffer: "Confirmed offer",
      partnerOffer: "Partner discount",
      productPost: "Product post",
      awareness: "Awareness",
      generalPost: "General post",
      uncertain: "Needs review",
      openAnalysis: "Open analysis",
      openOfficialOffer: "Open official offer",
      openOffersPage: "Open offers page",
      openPost: "Open post",
      directLink: "Direct link",
      generalLink: "General link",
      latestUpdates: "Latest updates",
      activity30d: "Activity over 30 days",
      channelActivity7d: "Channel activity over 7 days",
      offersByCompetitor: "Confirmed offers by competitor",
      partnerByCompetitor: "Partner discounts by competitor",
      productHeatmap: "Product focus heatmap",
      quickView: "Quick view",
      marketPulse: "Market pulse",
      lastCheck: "Last check",
      dataFresh: "Data is fresh",
      dataStale: "Data may be stale",
      loadError: "Unable to load data. Confirm GitHub Actions and GitHub Pages succeeded.",
      retry: "Retry",
      latestMedia: "Latest visual posts",
      noMedia: "No images or videos are available from the current sources.",
      offers: "Offers",
      partnerOffers: "Partner discounts",
      posts: "Posts",
      reviewQueue: "Review queue",
      allContent: "All content",
      clearFilters: "Clear filters",
      results: "results",
      activeOnly: "Active only",
      firstDetected: "First detected",
      lastChanged: "Last changed",
      published: "Published",
      version: "Version",
      confidence: "Confidence",
      high: "High",
      medium: "Medium",
      low: "Low",
      analysisSummary: "Analysis summary",
      strongestFocus: "Strongest focus",
      topChannel: "Most active channel",
      contentMix: "Content mix",
      back: "Back",
      officialWebsite: "Official website",
      officialOffersPage: "Official offers page",
      noData: "No matching data.",
      newOffer: "New offer",
      updatedOffer: "Offer updated",
      newPartner: "New partner discount",
      newPost: "New post",
      reviewAlert: "Item needs review",
      directLinkWarning: "No direct detail link was found for this item.",
      classificationWarning: "The classification is uncertain and requires human review.",
      sourceDetails: "Source details",
      healthy: "Healthy",
      failed: "Failed",
      skippedGeneral: "Excluded general links",
      itemTimeline: "Change timeline",
      classification: "Classification",
      media: "Media",
      noTimeline: "No additional change history yet.",
      baseline: "Initial import",
      detected: "Detected",
      updated: "Updated",
      reactivated: "Reactivated",
      expired: "Became inactive",
      itemDetails: "Item details",
      language: "العربية",
      count: "Count",
      socialShare: "Social activity share",
      categoryCoverage: "Category coverage",
      dataQuality: "Data quality",
      previous7d: "Previous 7 days",
      current7d: "Current 7 days",
      noRecentActivity: "No dated activity in this period.",
      initialImportNote: "Items imported during the first run are not counted as today's activity unless an actual publication date is available.",
      brandNamesNote: "Company names stay in English in both languages.",
      offerDefinitionNote: "An item counts as an offer only when a clear benefit exists, such as a discount, cashback, prize, or fee waiver.",
      videoUnavailable: "The video cannot be played inside the page; open the original post.",
      viewCompetitor: "Open competitor analysis",
      latest: "Latest",
      noConfirmedOffers: "No confirmed offers are currently detected.",
      noPartnerOffers: "No partner discounts are currently detected.",
      noPosts: "No matching posts.",
      days: "days",
      hours: "hours",
      minutes: "minutes",
      now: "Now"
    }
  };

  function language() { return localStorage.getItem(STORAGE_LANGUAGE) || "ar"; }
  function t(key) { return I18N[language()]?.[key] ?? I18N.en[key] ?? key; }
  function setLanguage(lang, emit = true) {
    const value = lang === "en" ? "en" : "ar";
    localStorage.setItem(STORAGE_LANGUAGE, value);
    document.documentElement.lang = value;
    document.documentElement.dir = value === "ar" ? "rtl" : "ltr";
    document.querySelectorAll("[data-i18n]").forEach(node => { node.textContent = t(node.dataset.i18n); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(node => node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder)));
    document.querySelectorAll("[data-language-toggle]").forEach(node => { node.textContent = t("language"); });
    if (emit) window.dispatchEvent(new CustomEvent("cm:language", { detail: { language: value } }));
  }
  function initLanguage() {
    setLanguage(language(), false);
    document.querySelectorAll("[data-language-toggle]").forEach(button => button.addEventListener("click", () => setLanguage(language() === "ar" ? "en" : "ar")));
  }

  async function loadData() {
    const response = await fetch(`data.json?_=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.items) || !Array.isArray(data.competitors)) throw new Error("Invalid schema");
    return data;
  }

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([key, value]) => {
      if (value === null || value === undefined || value === false) return;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key === "html") node.innerHTML = value;
      else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
      else if (key === "dataset") Object.entries(value).forEach(([k, v]) => { node.dataset[k] = v; });
      else if (value === true) node.setAttribute(key, "");
      else node.setAttribute(key, String(value));
    });
    children.flat(Infinity).forEach(child => {
      if (child === null || child === undefined || child === false) return;
      node.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
    });
    return node;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function byId(rows) { return Object.fromEntries((rows || []).map(row => [row.id, row])); }
  function competitorName(row) { return row?.name_en || row?.name_ar || "—"; }
  function taxonomyName(row) { return language() === "ar" ? row?.name_ar : row?.name_en; }
  function locale() { return language() === "ar" ? "ar-SA" : "en-GB"; }
  function formatDate(value, withTime = false) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    return new Intl.DateTimeFormat(locale(), { day: "numeric", month: "short", year: "numeric", hour: withTime ? "2-digit" : undefined, minute: withTime ? "2-digit" : undefined }).format(date);
  }
  function timeAgo(value) {
    if (!value) return "—";
    const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000));
    if (minutes < 1) return t("now");
    if (minutes < 60) return `${minutes} ${t("minutes")}`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} ${t("hours")}`;
    return `${Math.floor(hours / 24)} ${t("days")}`;
  }
  function activeItems(items) { return items.filter(item => item.active !== false); }
  function contentTypeLabel(type) {
    return ({ offer: t("confirmedOffer"), partner_offer: t("partnerOffer"), product_post: t("productPost"), awareness: t("awareness"), general_post: t("generalPost"), uncertain: t("uncertain") })[type] || type;
  }
  function contentTypeClass(type) {
    return ({ offer: "success", partner_offer: "partner", product_post: "info", awareness: "neutral", general_post: "neutral", uncertain: "warning" })[type] || "neutral";
  }
  function platformLabel(platform) { return t(platform || "website"); }
  function activityDate(item) {
    if (item.published_at) return new Date(item.published_at);
    if (item.source_type === "website" && Number(item.version || 1) <= 1) return null;
    if (item.baseline_import) return null;
    return item.last_changed ? new Date(item.last_changed) : null;
  }
  function withinDays(item, days) {
    const date = activityDate(item);
    return date && !Number.isNaN(date.getTime()) && date >= new Date(Date.now() - days * 86400000);
  }
  function countBy(items, fn) {
    const map = new Map();
    items.forEach(item => {
      const key = fn(item);
      if (Array.isArray(key)) key.forEach(value => map.set(value, (map.get(value) || 0) + 1));
      else if (key) map.set(key, (map.get(key) || 0) + 1);
    });
    return map;
  }
  function isConfirmedOffer(item) { return item.active !== false && item.source_type === "website" && item.content_type === "offer" && item.direct_link; }
  function isPartnerOffer(item) { return item.active !== false && item.source_type === "website" && item.content_type === "partner_offer" && item.direct_link; }
  function getAlertAck() { return localStorage.getItem(STORAGE_ALERT_ACK) || "1970-01-01T00:00:00Z"; }
  function markAlertsReviewed() { localStorage.setItem(STORAGE_ALERT_ACK, new Date().toISOString()); }
  function alertsSince(items, acknowledgedAt = getAlertAck()) {
    const hasAcknowledged = Boolean(localStorage.getItem(STORAGE_ALERT_ACK));
    const cutoff = new Date(acknowledgedAt).getTime();
    const changes = items.filter(item => !item.baseline_import && new Date(item.last_changed || 0).getTime() > cutoff);
    const review = items.filter(item => item.active !== false && item.review_required && (!hasAcknowledged || new Date(item.last_changed || 0).getTime() > cutoff));
    const merged = new Map();
    [...changes, ...review].forEach(item => merged.set(item.id, item));
    return [...merged.values()].sort((a, b) => new Date(b.last_changed || 0) - new Date(a.last_changed || 0));
  }
  function alertLabel(item) {
    if (item.review_required) return t("reviewAlert");
    if (item.content_type === "offer") return Number(item.version || 1) > 1 ? t("updatedOffer") : t("newOffer");
    if (item.content_type === "partner_offer") return t("newPartner");
    return t("newPost");
  }

  function pill(text, kind = "neutral") { return el("span", { class: `pill pill--${kind}` }, text); }

  function renderBarChart(container, rows, options = {}) {
    clear(container);
    const filtered = rows.filter(row => row.value > 0);
    if (!filtered.length) return container.appendChild(el("div", { class: "empty-state" }, t("noData")));
    const max = Math.max(...filtered.map(row => row.value), 1);
    filtered.forEach((row, index) => {
      container.appendChild(el("div", { class: "bar-row" },
        el("div", { class: "bar-row__label" }, row.label),
        el("div", { class: "bar-row__track" }, el("span", { class: "bar-row__fill", style: `width:${Math.max(4, row.value / max * 100)}%;--bar-color:${row.color || COLORS[index % COLORS.length]}` })),
        el("strong", { class: "bar-row__value" }, String(row.value))
      ));
    });
  }

  function renderLineChart(container, series, days = 30) {
    clear(container);
    const width = 760, height = 230, pad = 34;
    const dates = Array.from({ length: days }, (_, i) => {
      const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - (days - 1 - i)); return d;
    });
    const rows = series.map((entry, idx) => ({
      ...entry,
      color: entry.color || COLORS[idx % COLORS.length],
      values: dates.map(date => entry.items.filter(item => {
        const d = activityDate(item); return d && d.toDateString() === date.toDateString();
      }).length)
    }));
    const total = rows.reduce((sum, row) => sum + row.values.reduce((a, b) => a + b, 0), 0);
    if (!total) return container.appendChild(el("div", { class: "empty-state" }, t("noRecentActivity")));
    const max = Math.max(1, ...rows.flatMap(row => row.values));
    const svg = el("svg", { class: "line-chart", viewBox: `0 0 ${width} ${height}`, role: "img" });
    for (let y = 0; y <= 4; y++) {
      const py = pad + (height - pad * 2) * y / 4;
      svg.appendChild(el("line", { x1: pad, x2: width - pad, y1: py, y2: py, class: "chart-gridline" }));
    }
    rows.forEach(row => {
      const points = row.values.map((value, i) => {
        const x = pad + (width - pad * 2) * i / Math.max(1, days - 1);
        const y = height - pad - (height - pad * 2) * value / max;
        return `${x},${y}`;
      }).join(" ");
      svg.appendChild(el("polyline", { points, fill: "none", stroke: row.color, "stroke-width": 3, "stroke-linecap": "round", "stroke-linejoin": "round" }));
    });
    container.appendChild(svg);
    container.appendChild(el("div", { class: "chart-legend" }, rows.map(row => el("span", {}, el("i", { style: `--legend-color:${row.color}` }), row.label))));
  }

  function renderChannelMatrix(container, competitors, items) {
    clear(container);
    const platforms = ["instagram", "facebook", "x", "tiktok"];
    const recent = items.filter(item => item.source_type === "social" && withinDays(item, 7));
    if (!recent.length) return container.appendChild(el("div", { class: "empty-state" }, t("noRecentActivity")));
    const table = el("div", { class: "matrix" });
    table.appendChild(el("div", { class: "matrix__row matrix__row--head" }, el("strong", {}, t("competitors")), ...platforms.map(p => el("strong", {}, platformLabel(p)))));
    competitors.forEach(comp => {
      const rowItems = recent.filter(item => item.competitor_id === comp.id);
      table.appendChild(el("div", { class: "matrix__row" },
        el("a", { href: `competitor.html?id=${encodeURIComponent(comp.id)}` }, competitorName(comp)),
        ...platforms.map(platform => el("span", { class: "matrix__cell" }, String(rowItems.filter(item => item.platform === platform).length)))
      ));
    });
    container.appendChild(table);
  }

  function renderHeatmap(container, competitors, categories, items) {
    clear(container);
    const confirmed = items.filter(isConfirmedOffer);
    if (!confirmed.length) return container.appendChild(el("div", { class: "empty-state" }, t("noConfirmedOffers")));
    const relevantCategories = categories.filter(cat => cat.id !== "other");
    const max = Math.max(1, ...competitors.flatMap(comp => relevantCategories.map(cat => confirmed.filter(item => item.competitor_id === comp.id && item.categories?.includes(cat.id)).length)));
    const grid = el("div", { class: "heatmap" });
    grid.appendChild(el("div", { class: "heatmap__row heatmap__row--head" }, el("span", {}), ...relevantCategories.map(cat => el("span", { title: taxonomyName(cat) }, taxonomyName(cat)))));
    competitors.forEach(comp => {
      grid.appendChild(el("div", { class: "heatmap__row" },
        el("a", { href: `competitor.html?id=${encodeURIComponent(comp.id)}` }, competitorName(comp)),
        ...relevantCategories.map(cat => {
          const value = confirmed.filter(item => item.competitor_id === comp.id && item.categories?.includes(cat.id)).length;
          return el("span", { class: "heatmap__cell", style: `--heat:${value / max}`, title: `${taxonomyName(cat)}: ${value}` }, value ? String(value) : "—");
        })
      ));
    });
    container.appendChild(grid);
  }

  function renderMedia(item, compact = false) {
    const media = item.media;
    if (!media?.url) return null;
    if (media.type === "video") {
      const canPlay = /\.(mp4|webm|mov|m4v)(\?|$)/i.test(media.url);
      if (canPlay) return el("video", { class: compact ? "media media--compact" : "media", controls: true, preload: "metadata", poster: media.thumbnail_url || "" }, el("source", { src: media.url }));
      if (media.thumbnail_url) return el("div", { class: "media-link" }, el("img", { src: media.thumbnail_url, alt: "", loading: "lazy" }), el("span", { class: "media-play" }, "▶"));
      return el("div", { class: "media-placeholder" }, "▶", el("small", {}, t("videoUnavailable")));
    }
    return el("img", { class: compact ? "media media--compact" : "media", src: media.thumbnail_url || media.url, alt: item.title || "", loading: "lazy", referrerpolicy: "no-referrer" });
  }

  function renderItemCard(item, data, options = {}) {
    const competitors = byId(data.competitors), categories = byId(data.categories), benefits = byId(data.benefit_types);
    const comp = competitors[item.competitor_id];
    const card = el("article", { class: `item-card item-card--${contentTypeClass(item.content_type)}` });
    const media = options.showMedia ? renderMedia(item, true) : null;
    if (media) card.appendChild(el("a", { class: "item-card__media", href: item.link, target: "_blank", rel: "noopener noreferrer" }, media));
    const pills = [pill(contentTypeLabel(item.content_type), contentTypeClass(item.content_type))];
    if (item.primary_category && categories[item.primary_category]) pills.push(pill(taxonomyName(categories[item.primary_category]), "info"));
    (item.benefit_types || []).slice(0, 2).forEach(id => benefits[id] && pills.push(pill(taxonomyName(benefits[id]), "benefit")));
    if (item.review_required) pills.push(pill(t("needsReview"), "warning"));
    card.appendChild(el("div", { class: "item-card__body" },
      el("div", { class: "item-card__top" }, el("span", { class: "item-card__brand" }, competitorName(comp)), el("span", { class: "item-card__source" }, platformLabel(item.platform))),
      el("div", { class: "pill-row" }, pills),
      el("h3", {}, item.title || "—"),
      item.snippet ? el("p", {}, item.snippet) : null,
      el("div", { class: "item-card__meta" },
        el("span", {}, `${t("published")}: ${formatDate(item.published_at || item.first_seen)}`),
        el("span", {}, `${t("version")}: ${item.version || 1}`)
      ),
      el("div", { class: "item-card__actions" },
        el("a", { class: "button button--primary", href: `item.html?id=${encodeURIComponent(item.id)}` }, t("openAnalysis")),
        el("a", { class: "button button--ghost", href: item.link, target: "_blank", rel: "noopener noreferrer" }, item.source_type === "social" ? t("openPost") : (item.direct_link ? t("openOfficialOffer") : t("openOffersPage")))
      )
    ));
    return card;
  }

  function renderMediaCard(item, data) {
    const comp = byId(data.competitors)[item.competitor_id];
    const media = renderMedia(item);
    if (!media) return null;
    return el("article", { class: "media-card" },
      el("a", { class: "media-card__visual", href: item.link, target: "_blank", rel: "noopener noreferrer" }, media),
      el("div", { class: "media-card__body" },
        el("div", { class: "media-card__meta" }, competitorName(comp), " · ", platformLabel(item.platform)),
        el("h3", {}, item.title || "—"),
        el("div", { class: "media-card__actions" },
          el("a", { href: `item.html?id=${encodeURIComponent(item.id)}` }, t("openAnalysis")),
          el("a", { href: item.link, target: "_blank", rel: "noopener noreferrer" }, t("openPost"))
        )
      )
    );
  }

  function showError(container, error) {
    clear(container);
    container.appendChild(el("div", { class: "error-state" }, el("strong", {}, t("loadError")), el("code", {}, String(error)), el("button", { class: "button button--primary", onclick: () => location.reload() }, t("retry"))));
  }

  window.CM = {
    t, language, setLanguage, initLanguage, loadData, el, clear, byId, competitorName, taxonomyName,
    formatDate, timeAgo, activeItems, contentTypeLabel, platformLabel, activityDate, withinDays,
    countBy, isConfirmedOffer, isPartnerOffer, getAlertAck, markAlertsReviewed, alertsSince, alertLabel,
    pill, renderBarChart, renderLineChart, renderChannelMatrix, renderHeatmap, renderItemCard, renderMediaCard,
    renderMedia, showError
  };
})();
