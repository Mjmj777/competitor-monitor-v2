(() => {
  "use strict";

  const LANG_KEY = "cm_v4_language";
  const ALERT_KEY = "cm_v4_alert_ack";
  const OVERRIDE_KEY = "cm_v4_manual_overrides";
  const COLORS = ["#0f766e", "#2563eb", "#7c3aed", "#d97706", "#dc2626", "#475569"];

  const I18N = {
    ar: {
      appTitle: "لوحة ذكاء المنافسين",
      appSubtitle: "متابعة الحملات والعروض والشركاء والنشاط التسويقي في قطاع المدفوعات الرقمية",
      overview: "النظرة العامة", campaigns: "الحملات والعروض", merchantOffers: "عروض الشركاء", posts: "المنشورات", review: "بحاجة إلى مراجعة", all: "الكل",
      activeCampaigns: "الحملات النشطة", activeCampaignsDetail: "جميع الحملات الحالية من مخزون Excel والمصادر الحية — Merchant مستبعد",
      merchantPortfolio: "محفظة عروض الشركاء", merchantPortfolioDetail: "مرجع مستقل ولا يدخل في مؤشرات الحملات",
      remittanceCampaigns: "حملات التحويل الدولي", expiring30d: "تنتهي خلال 30 يومًا", socialPosts7d: "منشورات آخر 7 أيام", reviewRequired: "عناصر تحتاج مراجعة",
      alerts: "التنبيهات", alertsHint: "تحديثات منذ آخر فتح", openAlerts: "فتح التنبيهات", markReviewed: "تحديد الكل كمراجع", noAlerts: "لا توجد تنبيهات جديدة.",
      sourceHealth: "سلامة المصادر", sourceHealthHint: "افتح لمعرفة المصادر المتعثرة وتفاصيل الخطأ", healthy: "يعمل", failed: "متعثر", noItems: "يعمل بدون عناصر", lastSuccess: "آخر نجاح", lastCheck: "آخر فحص", extracted: "عناصر مستخرجة", error: "الخطأ", openSource: "فتح المصدر",
      marketAnalysis: "التحليل العام", campaignsByCompetitor: "الحملات الحالية حسب المنافس", categoryMix: "توزيع تصنيفات الحملات", remittanceComparison: "مقارنة التحويل الدولي", merchantComparison: "عروض الشركاء حسب المنافس", expiryRisk: "مخاطر انتهاء الحملات", mechanicsMix: "آليات العروض", channelActivity7d: "نشاط القنوات خلال 7 أيام", platformCoverage: "تغطية الحملات عبر المنصات", competitiveMatrix: "مصفوفة التغطية التنافسية",
      marketingSignals: "إشارات تسويقية سريعة", mostActiveCompetitor: "الأكثر نشاطًا اجتماعيًا", bestPlatformCoverage: "الأفضل في التغطية متعددة القنوات", strongestCategory: "أبرز تصنيف في السوق", highestExpiryRisk: "أعلى مخاطر انتهاء", shareOfVoice: "حصة الصوت الاجتماعي",
      competitors: "المنافسون", viewCompetitor: "فتح تحليل المنافس", latestMedia: "أحدث الصور والفيديو", noMedia: "لا توجد وسائط متاحة من RSS حاليًا.",
      inventory: "مخزون الحملات", search: "بحث", searchPlaceholder: "ابحث باسم الحملة أو الملخص…", category: "التصنيف", contentType: "نوع السجل", status: "الحالة", source: "المصدر", platform: "المنصة", clear: "مسح",
      openAnalysis: "فتح التفاصيل", openOfficial: "فتح الرابط الرسمي", openPost: "فتح المنشور", edit: "تعديل", editItem: "تعديل السجل", saveLocal: "حفظ التعديل", resetEdit: "إلغاء التعديل", close: "إغلاق",
      exportEdits: "تصدير التعديلات", importEdits: "استيراد التعديلات", editsNote: "التعديل يحفظ فورًا في هذا المتصفح. صدّر manual_overrides.json وارفعه للمستودع لجعله دائمًا لجميع المستخدمين.",
      title: "الاسم", summary: "الملخص", active: "نشط", inactive: "غير نشط", officialCampaignUrl: "رابط صفحة الحملة", primarySourceUrl: "المصدر الرسمي الأساسي", instagramUrl: "Instagram URL", xUrl: "X URL", facebookUrl: "Facebook URL", tiktokUrl: "TikTok URL",
      socialLinks: "روابط السوشيال", socialLinkCount: "عدد روابط السوشيال", operationType: "نوع العملية", mechanic: "آلية العرض", eligibility: "الأهلية / المنتج", terms: "الشروط والتوقيت", published: "تاريخ النشر", startDate: "تاريخ البداية", endDate: "تاريخ النهاية", currentStatus: "الحالة الحالية", recordId: "Record ID", lastReviewed: "آخر مراجعة",
      campaign: "حملة أو عرض", merchant_offer: "عرض شريك", social_post: "منشور اجتماعي", awareness: "محتوى توعوي", review_type: "بحاجة إلى مراجعة",
      remittance: "التحويل الدولي", musaned: "مساند", sadad: "سداد", card: "البطاقات", engagement: "التفاعل والمسابقات", other: "أخرى", merchant: "عروض الشركاء",
      discount: "خصم", cashback: "كاش باك", fee_waiver: "إعفاء من الرسوم", prize_draw: "جائزة أو سحب", reward: "مكافأة أو نقاط", preferred_rate: "سعر تفضيلي",
      instagram: "Instagram", facebook: "Facebook", x: "X", tiktok: "TikTok", website: "Website", inventorySource: "Excel Inventory",
      noData: "لا توجد بيانات مطابقة.", loading: "جارٍ تحميل البيانات…", loadError: "تعذر تحميل البيانات. تأكد من نجاح GitHub Actions.", retry: "إعادة المحاولة", results: "نتيجة", back: "العودة", officialWebsite: "الموقع الرسمي", officialOffers: "صفحة العروض",
      dataBasis: "أساس الحساب", dataBasisText: "الملخص يحسب جميع الحملات والعروض النشطة حاليًا، وليس فقط ما ظهر منذ آخر زيارة.", excelAligned: "متوافق مع ملف Excel", excelAlignedText: "التصنيفات والأعمدة تتبع المخزون المعتمد بتاريخ 6 أغسطس 2026.",
      newCampaign: "حملة جديدة", updatedCampaign: "حملة تم تحديثها", newMerchant: "عرض شريك جديد", newPost: "منشور جديد", reviewAlert: "عنصر يحتاج تصنيفًا",
      sourceStatusSuccess: "المصدر يعمل", sourceStatusFailed: "المصدر متعثر", zeroItemsMeaning: "نجح الاتصال لكن لم تُستخرج عناصر؛ راجع رابط RSS أو بنية الصفحة.",
      campaignTimeline: "سجل التغييرات", classification: "التصنيف", media: "الوسائط", linkedCampaign: "الحملة المرتبطة", companyNames: "أسماء الشركات تظهر بالإنجليزية في اللغتين.",
      language: "English", days: "يوم", hours: "ساعة", minutes: "دقيقة", now: "الآن"
    },
    en: {
      appTitle: "Competitor Intelligence Dashboard",
      appSubtitle: "Campaign, offer, merchant and marketing activity intelligence for digital payments",
      overview: "Overview", campaigns: "Campaigns & offers", merchantOffers: "Merchant offers", posts: "Posts", review: "Needs review", all: "All",
      activeCampaigns: "Active campaigns", activeCampaignsDetail: "All current campaigns from the Excel inventory and live sources — Merchant excluded",
      merchantPortfolio: "Merchant offers portfolio", merchantPortfolioDetail: "Separate reference portfolio excluded from campaign KPIs",
      remittanceCampaigns: "Remittance campaigns", expiring30d: "Expiring within 30 days", socialPosts7d: "Social posts in 7 days", reviewRequired: "Items needing review",
      alerts: "Alerts", alertsHint: "Changes since your last visit", openAlerts: "Open alerts", markReviewed: "Mark all reviewed", noAlerts: "No new alerts.",
      sourceHealth: "Source health", sourceHealthHint: "Open to inspect failed sources and error details", healthy: "Healthy", failed: "Failed", noItems: "Healthy with zero items", lastSuccess: "Last success", lastCheck: "Last check", extracted: "Extracted items", error: "Error", openSource: "Open source",
      marketAnalysis: "Market analysis", campaignsByCompetitor: "Current campaigns by competitor", categoryMix: "Campaign category mix", remittanceComparison: "Remittance comparison", merchantComparison: "Merchant offers by competitor", expiryRisk: "Campaign expiry risk", mechanicsMix: "Offer mechanics", channelActivity7d: "Channel activity over 7 days", platformCoverage: "Campaign platform coverage", competitiveMatrix: "Competitive coverage matrix",
      marketingSignals: "Marketing signals", mostActiveCompetitor: "Most socially active", bestPlatformCoverage: "Best multi-channel coverage", strongestCategory: "Strongest market category", highestExpiryRisk: "Highest expiry risk", shareOfVoice: "Social share of voice",
      competitors: "Competitors", viewCompetitor: "Open competitor analysis", latestMedia: "Latest images and video", noMedia: "No media is currently available from RSS.",
      inventory: "Campaign inventory", search: "Search", searchPlaceholder: "Search campaign name or summary…", category: "Category", contentType: "Record type", status: "Status", source: "Source", platform: "Platform", clear: "Clear",
      openAnalysis: "Open details", openOfficial: "Open official link", openPost: "Open post", edit: "Edit", editItem: "Edit record", saveLocal: "Save edit", resetEdit: "Reset edit", close: "Close",
      exportEdits: "Export edits", importEdits: "Import edits", editsNote: "Edits are saved immediately in this browser. Export manual_overrides.json and upload it to the repository to make them permanent for everyone.",
      title: "Title", summary: "Summary", active: "Active", inactive: "Inactive", officialCampaignUrl: "Official campaign page URL", primarySourceUrl: "Primary official source URL", instagramUrl: "Instagram URL", xUrl: "X URL", facebookUrl: "Facebook URL", tiktokUrl: "TikTok URL",
      socialLinks: "Social links", socialLinkCount: "Social link count", operationType: "Operation type", mechanic: "Mechanic / offer", eligibility: "Eligibility / product", terms: "Terms / timing", published: "Published date", startDate: "Start date", endDate: "End date", currentStatus: "Current status", recordId: "Record ID", lastReviewed: "Last reviewed",
      campaign: "Campaign / offer", merchant_offer: "Merchant offer", social_post: "Social post", awareness: "Awareness", review_type: "Needs review",
      remittance: "Remittance", musaned: "Musaned", sadad: "SADAD", card: "Card", engagement: "Engagement", other: "Other", merchant: "Merchant",
      discount: "Discount", cashback: "Cashback", fee_waiver: "Fee waiver", prize_draw: "Prize / draw", reward: "Reward / points", preferred_rate: "Preferred rate",
      instagram: "Instagram", facebook: "Facebook", x: "X", tiktok: "TikTok", website: "Website", inventorySource: "Excel Inventory",
      noData: "No matching data.", loading: "Loading data…", loadError: "Unable to load data. Confirm GitHub Actions succeeded.", retry: "Retry", results: "results", back: "Back", officialWebsite: "Official website", officialOffers: "Offers page",
      dataBasis: "Calculation basis", dataBasisText: "The summary counts all currently active campaigns and offers, not only items detected since the previous visit.", excelAligned: "Excel aligned", excelAlignedText: "Categories and fields follow the approved inventory reviewed on 6 August 2026.",
      newCampaign: "New campaign", updatedCampaign: "Campaign updated", newMerchant: "New merchant offer", newPost: "New post", reviewAlert: "Item needs classification",
      sourceStatusSuccess: "Source is healthy", sourceStatusFailed: "Source failed", zeroItemsMeaning: "The connection succeeded but no items were extracted; review the RSS URL or page structure.",
      campaignTimeline: "Change history", classification: "Classification", media: "Media", linkedCampaign: "Linked campaign", companyNames: "Company names remain English in both languages.",
      language: "العربية", days: "days", hours: "hours", minutes: "minutes", now: "Now"
    }
  };

  function language() { return localStorage.getItem(LANG_KEY) || "ar"; }
  function t(key) { return I18N[language()]?.[key] ?? I18N.en[key] ?? key; }
  function setLanguage(value) { localStorage.setItem(LANG_KEY, value); applyLanguage(); window.dispatchEvent(new CustomEvent("cm:language")); }
  function applyLanguage() {
    const lang = language(); document.documentElement.lang = lang; document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    document.querySelectorAll("[data-i18n]").forEach(node => node.textContent = t(node.dataset.i18n));
    document.querySelectorAll("[data-i18n-placeholder]").forEach(node => node.placeholder = t(node.dataset.i18nPlaceholder));
    document.querySelectorAll("[data-language-toggle]").forEach(node => { node.textContent = t("language"); node.onclick = () => setLanguage(lang === "ar" ? "en" : "ar"); });
  }
  function initLanguage() { applyLanguage(); }

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, value]) => {
      if (value === null || value === undefined || value === false) return;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2).toLowerCase(), value);
      else if (key === "checked") node.checked = Boolean(value);
      else node.setAttribute(key, String(value));
    });
    children.flat(Infinity).filter(value => value !== null && value !== undefined && value !== false).forEach(child => node.append(child instanceof Node ? child : document.createTextNode(String(child))));
    return node;
  }
  function clear(node) { while (node?.firstChild) node.removeChild(node.firstChild); }
  function byId(rows) { return Object.fromEntries((rows || []).map(row => [row.id, row])); }
  function competitorName(row) { return row?.name_en || "—"; }
  function taxonomyName(row) { return language() === "ar" ? row?.name_ar : row?.name_en; }
  function locale() { return language() === "ar" ? "ar-SA" : "en-GB"; }
  function formatDate(value, withTime = false) { if (!value) return "—"; const d = new Date(value); return Number.isNaN(d.getTime()) ? String(value) : new Intl.DateTimeFormat(locale(), withTime ? { dateStyle: "medium", timeStyle: "short" } : { dateStyle: "medium" }).format(d); }
  function timeAgo(value) { if (!value) return "—"; const ms = Date.now() - new Date(value).getTime(); if (ms < 60000) return t("now"); if (ms < 3600000) return `${Math.floor(ms / 60000)} ${t("minutes")}`; if (ms < 86400000) return `${Math.floor(ms / 3600000)} ${t("hours")}`; return `${Math.floor(ms / 86400000)} ${t("days")}`; }
  function withinDays(item, days) { const d = new Date(item.published_at || item.last_changed || 0); return !Number.isNaN(d.getTime()) && d >= new Date(Date.now() - days * 86400000); }
  function countBy(items, getter) { const map = new Map(); items.forEach(item => { const raw = getter(item); (Array.isArray(raw) ? raw : [raw]).filter(Boolean).forEach(key => map.set(key, (map.get(key) || 0) + 1)); }); return map; }

  function getOverrides() { try { return JSON.parse(localStorage.getItem(OVERRIDE_KEY) || '{"schema_version":1,"items":{}}'); } catch { return { schema_version: 1, items: {} }; } }
  function setOverrides(value) { localStorage.setItem(OVERRIDE_KEY, JSON.stringify(value)); }
  function applyOverride(item, patch) {
    if (!patch) return item;
    const row = { ...item, ...patch, manual_override: true };
    if (patch.campaign_category) { row.primary_category = patch.campaign_category; row.categories = [patch.campaign_category]; }
    row.social_links = Object.fromEntries(Object.entries(row.social_links || {}).filter(([, url]) => url));
    row.social_link_count = Object.keys(row.social_links).length;
    return row;
  }
  function applyOverrides(data) { const overrides = getOverrides().items || {}; return { ...data, items: (data.items || []).map(item => applyOverride(item, overrides[item.id])) }; }
  async function loadData() { const response = await fetch(`data.json?_=${Date.now()}`, { cache: "no-store" }); if (!response.ok) throw new Error(`HTTP ${response.status}`); return applyOverrides(await response.json()); }
  function saveItemOverride(itemId, patch) { const value = getOverrides(); value.updated_at = new Date().toISOString(); value.items ||= {}; value.items[itemId] = { ...(value.items[itemId] || {}), ...patch }; setOverrides(value); window.dispatchEvent(new CustomEvent("cm:overrides")); }
  function resetItemOverride(itemId) { const value = getOverrides(); delete value.items?.[itemId]; value.updated_at = new Date().toISOString(); setOverrides(value); window.dispatchEvent(new CustomEvent("cm:overrides")); }
  function exportOverrides() { const value = getOverrides(); value.updated_at = new Date().toISOString(); const blob = new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }); const a = el("a", { href: URL.createObjectURL(blob), download: "manual_overrides.json" }); document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500); }
  function importOverrides(file) { const reader = new FileReader(); reader.onload = () => { try { const value = JSON.parse(reader.result); if (!value.items) throw new Error("Missing items"); setOverrides(value); location.reload(); } catch (error) { alert(String(error)); } }; reader.readAsText(file); }

  function activeCampaigns(items) { return items.filter(item => item.active !== false && item.content_type === "campaign"); }
  function activeMerchants(items) { return items.filter(item => item.active !== false && item.content_type === "merchant_offer"); }
  function socialPosts(items, days = null) { return items.filter(item => item.active !== false && item.source_type === "social" && (!days || withinDays(item, days))); }
  function alerts(items) { const cutoff = new Date(localStorage.getItem(ALERT_KEY) || "1970-01-01T00:00:00Z"); const rows = items.filter(item => { const d = new Date(item.last_changed || item.first_seen || 0); return !item.baseline_import && d > cutoff || item.review_required && d > cutoff; }); return [...new Map(rows.map(item => [item.id, item])).values()].sort((a, b) => new Date(b.last_changed || 0) - new Date(a.last_changed || 0)); }
  function acknowledgeAlerts() { localStorage.setItem(ALERT_KEY, new Date().toISOString()); }
  function alertLabel(item) { if (item.review_required) return t("reviewAlert"); if (item.content_type === "campaign") return Number(item.version || 1) > 1 ? t("updatedCampaign") : t("newCampaign"); if (item.content_type === "merchant_offer") return t("newMerchant"); return t("newPost"); }

  function pill(text, kind = "neutral") { return el("span", { class: `pill pill--${kind}` }, text); }
  function renderBarChart(container, rows, options = {}) {
    clear(container); const values = options.keepZero ? rows : rows.filter(row => row.value > 0); if (!values.length) return container.appendChild(el("div", { class: "empty-state" }, t("noData")));
    const max = Math.max(1, ...values.map(row => row.value)); values.forEach((row, index) => container.appendChild(el("div", { class: "bar-row" }, el("div", { class: "bar-row__label" }, row.label), el("div", { class: "bar-row__track" }, el("span", { class: "bar-row__fill", style: `width:${row.value ? Math.max(3, row.value / max * 100) : 0}%;--bar-color:${row.color || COLORS[index % COLORS.length]}` })), el("strong", { class: "bar-row__value" }, String(row.value)))));
  }
  function renderMatrix(container, rowDefs, colDefs, valueFn) {
    clear(container); const table = el("div", { class: "matrix" }); table.appendChild(el("div", { class: "matrix__row matrix__row--head" }, el("strong", {}, ""), ...colDefs.map(col => el("strong", {}, col.label))));
    rowDefs.forEach(row => table.appendChild(el("div", { class: "matrix__row" }, row.href ? el("a", { href: row.href }, row.label) : el("strong", {}, row.label), ...colDefs.map(col => el("span", { class: "matrix__cell" }, String(valueFn(row, col) || 0)))))); container.appendChild(table);
  }
  function renderMedia(item, compact = false) { const media = item.media; if (!media?.url) return null; if (media.type === "video") { if (/\.(mp4|webm|mov)(\?|$)/i.test(media.url)) return el("video", { class: compact ? "media media--compact" : "media", controls: true, preload: "metadata", poster: media.thumbnail_url || "" }, el("source", { src: media.url })); if (media.thumbnail_url) return el("div", { class: "media-link" }, el("img", { src: media.thumbnail_url, alt: "", loading: "lazy" }), el("span", { class: "media-play" }, "▶")); return el("div", { class: "media-placeholder" }, "▶"); } return el("img", { class: compact ? "media media--compact" : "media", src: media.thumbnail_url || media.url, alt: item.title || "", loading: "lazy", referrerpolicy: "no-referrer" }); }

  function contentLabel(item) { return item.content_type === "review" ? t("review_type") : t(item.content_type); }
  function categoryLabel(item, data) { const row = byId(data.categories)[item.campaign_category || item.primary_category]; return row ? taxonomyName(row) : "—"; }
  function renderItemCard(item, data, options = {}) {
    const comp = byId(data.competitors)[item.competitor_id];
    const card = el("article", { class: `item-card item-card--${item.content_type || "review"}` });
    if (options.media) {
      const media = renderMedia(item, true);
      if (media) card.appendChild(el("a", { class: "item-card__media", href: item.link || "#", target: "_blank", rel: "noopener noreferrer" }, media));
    }
    const socialCount = Object.keys(item.social_links || {}).length;
    const pillRow = el("div", { class: "pill-row" },
      pill(contentLabel(item), item.content_type === "merchant_offer" ? "gold" : item.review_required ? "warning" : "info"),
      pill(categoryLabel(item, data), "neutral"),
      socialCount ? pill(`${socialCount} ${t("socialLinks")}`, "success") : null,
      item.manual_override ? pill(t("edit"), "purple") : null
    );
    const actions = el("div", { class: "item-card__actions" },
      el("a", { class: "button button--primary", href: `item.html?id=${encodeURIComponent(item.id)}` }, t("openAnalysis")),
      item.link ? el("a", { class: "button button--ghost", href: item.link, target: "_blank", rel: "noopener noreferrer" }, item.source_type === "social" ? t("openPost") : t("openOfficial")) : null,
      el("button", { class: "button button--secondary", onclick: () => openEditor(item, data) }, t("edit"))
    );
    const body = el("div", { class: "item-card__body" },
      el("div", { class: "item-card__top" }, el("strong", {}, competitorName(comp)), el("span", {}, item.source_type === "inventory" ? t("inventorySource") : t(item.platform || "website"))),
      pillRow,
      el("h3", {}, item.title || "—"),
      item.snippet ? el("p", {}, item.snippet) : null,
      el("div", { class: "item-card__meta" },
        item.current_status ? el("span", {}, item.current_status) : null,
        item.end_date ? el("span", {}, `${t("endDate")}: ${formatDate(item.end_date)}`) : null
      ),
      actions
    );
    card.appendChild(body);
    return card;
  }
  function renderMediaCard(item, data) { const media = renderMedia(item); if (!media) return null; const comp = byId(data.competitors)[item.competitor_id]; return el("article", { class: "media-card" }, el("a", { class: "media-card__visual", href: item.link || "#", target: "_blank", rel: "noopener noreferrer" }, media), el("div", { class: "media-card__body" }, el("div", { class: "media-card__meta" }, `${competitorName(comp)} · ${t(item.platform || "website")}`), el("h3", {}, item.title || "—"), el("a", { href: `item.html?id=${encodeURIComponent(item.id)}` }, t("openAnalysis")))); }

  function field(label, input) { return el("label", { class: "editor-field" }, el("span", {}, label), input); }
  function openEditor(item, data) {
    document.getElementById("cm-editor")?.remove();
    const categories = data.categories.filter(row => row.id !== "merchant");
    const content = el("select", {}, ["campaign", "merchant_offer", "social_post", "awareness", "review"].map(value => el("option", { value, selected: item.content_type === value }, t(value === "review" ? "review_type" : value))));
    const category = el("select", {}, [...categories, data.categories.find(row => row.id === "merchant")].filter(Boolean).map(row => el("option", { value: row.id, selected: (item.campaign_category || item.primary_category) === row.id }, taxonomyName(row))));
    const title = el("input", { value: item.title || "" }); const summary = el("textarea", { rows: 4 }, item.snippet || item.summary || ""); const status = el("input", { value: item.current_status || "" }); const active = el("input", { type: "checkbox", checked: item.active !== false });
    const official = el("input", { value: item.official_campaign_page_url || "", type: "url" }); const primary = el("input", { value: item.primary_official_source_url || "", type: "url" });
    const social = Object.fromEntries(["instagram", "x", "facebook", "tiktok"].map(platform => [platform, el("input", { value: item.social_links?.[platform] || "", type: "url" })]));
    const modal = el("div", { id: "cm-editor", class: "modal-backdrop" }, el("section", { class: "modal" },
      el("header", { class: "modal__header" }, el("div", {}, el("span", { class: "eyebrow" }, competitorName(byId(data.competitors)[item.competitor_id])), el("h2", {}, t("editItem"))), el("button", { class: "icon-button", onclick: () => modal.remove() }, "×")),
      el("div", { class: "modal__body" }, el("p", { class: "editor-note" }, t("editsNote")), el("div", { class: "editor-grid" }, field(t("contentType"), content), field(t("category"), category), field(t("title"), title), field(t("currentStatus"), status), field(t("summary"), summary), field(t("active"), active), field(t("officialCampaignUrl"), official), field(t("primarySourceUrl"), primary), field(t("instagramUrl"), social.instagram), field(t("xUrl"), social.x), field(t("facebookUrl"), social.facebook), field(t("tiktokUrl"), social.tiktok))),
      el("footer", { class: "modal__footer" }, el("button", { class: "button button--ghost", onclick: () => { resetItemOverride(item.id); location.reload(); } }, t("resetEdit")), el("button", { class: "button button--secondary", onclick: exportOverrides }, t("exportEdits")), el("button", { class: "button button--primary", onclick: () => { const chosenCategory = category.value; const chosenContent = chosenCategory === "merchant" ? "merchant_offer" : content.value; const links = Object.fromEntries(Object.entries(social).map(([key, input]) => [key, input.value.trim()]).filter(([, value]) => value)); saveItemOverride(item.id, { title: title.value.trim(), snippet: summary.value.trim(), summary: summary.value.trim(), content_type: chosenContent, campaign_category: chosenCategory, current_status: status.value.trim(), active: active.checked, official_campaign_page_url: official.value.trim(), primary_official_source_url: primary.value.trim(), link: official.value.trim() || primary.value.trim() || item.link, social_links: links, review_required: chosenContent === "review", review_reasons: chosenContent === "review" ? ["manual_review_required"] : [] }); location.reload(); } }, t("saveLocal")))));
    document.body.appendChild(modal); modal.addEventListener("click", event => { if (event.target === modal) modal.remove(); });
  }

  function sourceRow(status, data) { const comp = byId(data.competitors)[status.competitor_id]; const state = status.success ? status.item_count ? t("healthy") : t("noItems") : t("failed"); return el("article", { class: `source-card ${status.success ? "source-card--ok" : "source-card--failed"}` }, el("div", {}, el("strong", {}, `${competitorName(comp)} · ${t(status.platform || "website")}`), el("span", { class: "source-state" }, state)), el("dl", {}, el("div", {}, el("dt", {}, t("lastCheck")), el("dd", {}, formatDate(status.checked_at, true))), el("div", {}, el("dt", {}, t("lastSuccess")), el("dd", {}, formatDate(status.last_success_at, true))), el("div", {}, el("dt", {}, t("extracted")), el("dd", {}, String(status.item_count || 0)))), status.error ? el("code", {}, status.error) : status.success && !status.item_count ? el("p", { class: "source-note" }, t("zeroItemsMeaning")) : null, el("a", { href: status.url, target: "_blank", rel: "noopener noreferrer" }, t("openSource"))); }
  function showError(container, error) { clear(container); container.appendChild(el("div", { class: "error-state" }, el("strong", {}, t("loadError")), el("code", {}, String(error)), el("button", { class: "button button--primary", onclick: () => location.reload() }, t("retry")))); }

  window.CM = { t, language, setLanguage, initLanguage, loadData, el, clear, byId, competitorName, taxonomyName, formatDate, timeAgo, withinDays, countBy, getOverrides, exportOverrides, importOverrides, activeCampaigns, activeMerchants, socialPosts, alerts, acknowledgeAlerts, alertLabel, pill, renderBarChart, renderMatrix, renderMedia, renderItemCard, renderMediaCard, openEditor, sourceRow, showError, categoryLabel, contentLabel };
})();
