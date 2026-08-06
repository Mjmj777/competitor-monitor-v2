(() => {
  "use strict";
  const C = window.CM;
  const params = new URLSearchParams(location.search);
  const state = { data: null, item: null };

  function detailRow(term, value) { return C.el("div", {}, C.el("dt", {}, term), C.el("dd", {}, value || "—")); }
  function render() {
    const item = state.item, competitors = C.byId(state.data.competitors), categories = C.byId(state.data.categories), benefits = C.byId(state.data.benefit_types), comp = competitors[item.competitor_id];
    document.title = `${item.title} · ${C.competitorName(comp)}`;
    document.getElementById("back-link").href = `competitor.html?id=${encodeURIComponent(item.competitor_id)}`;
    document.getElementById("item-title").textContent = item.title || "—";
    document.getElementById("item-snippet").textContent = item.snippet || "";
    const pills = document.getElementById("hero-pills"); C.clear(pills);
    pills.append(C.pill(C.competitorName(comp), "info"), C.pill(C.contentTypeLabel(item.content_type), item.review_required ? "warning" : "success"), C.pill(C.platformLabel(item.platform), "neutral"));
    const external = document.getElementById("external-link"); external.href = item.link; external.textContent = item.source_type === "social" ? C.t("openPost") : (item.direct_link ? C.t("openOfficialOffer") : C.t("openOffersPage"));

    const warnings = document.getElementById("warnings"); C.clear(warnings);
    if (item.source_type === "website" && !item.direct_link) warnings.appendChild(C.el("div", { class: "warning-box" }, C.t("directLinkWarning")));
    if (item.review_required) warnings.appendChild(C.el("div", { class: "warning-box" }, C.t("classificationWarning")));

    const metadata = document.getElementById("metadata"); C.clear(metadata);
    metadata.append(
      detailRow(C.t("competitors"), C.competitorName(comp)), detailRow(C.t("source"), item.source_type === "website" ? C.t("website") : C.t("social")),
      detailRow(C.t("platform"), C.platformLabel(item.platform)), detailRow(C.t("status"), C.t(item.active === false ? "inactive" : "active")),
      detailRow(C.t("published"), C.formatDate(item.published_at)), detailRow(C.t("firstDetected"), C.formatDate(item.first_seen, true)),
      detailRow(C.t("lastChanged"), C.formatDate(item.last_changed, true)), detailRow(C.t("version"), String(item.version || 1)),
      detailRow(C.t("confidence"), C.t(item.confidence || "medium")), detailRow(item.direct_link ? C.t("directLink") : C.t("generalLink"), item.link)
    );

    const classification = document.getElementById("classification"); C.clear(classification);
    classification.appendChild(C.el("div", { class: "classification-block" },
      C.el("h3", {}, C.t("categories")), C.el("div", { class: "pill-row" }, (item.categories || []).map(id => categories[id] ? C.pill(C.taxonomyName(categories[id]), "info") : null)),
      C.el("h3", {}, C.t("benefits")), C.el("div", { class: "pill-row" }, (item.benefit_types || []).length ? item.benefit_types.map(id => benefits[id] ? C.pill(C.taxonomyName(benefits[id]), "benefit") : null) : C.pill("—", "neutral")),
      item.review_reasons?.length ? C.el("div", { class: "review-reasons" }, item.review_reasons.map(reason => C.el("code", {}, reason))) : null
    ));

    const media = document.getElementById("media"); C.clear(media); const visual = C.renderMedia(item); media.appendChild(visual || C.el("div", { class: "empty-state" }, C.t("noMedia")));

    const timeline = document.getElementById("timeline"); C.clear(timeline);
    const history = [...(item.change_history || [])].reverse();
    if (!history.length) timeline.appendChild(C.el("div", { class: "empty-state" }, C.t("noTimeline")));
    history.forEach(event => {
      const label = ({ baseline: C.t("baseline"), detected: C.t("detected"), updated: C.t("updated"), reactivated: C.t("reactivated"), inactive: C.t("expired") })[event.type] || event.type;
      timeline.appendChild(C.el("article", { class: "timeline-row" }, C.el("span", { class: "timeline-row__dot" }), C.el("div", {}, C.el("strong", {}, label), C.el("p", {}, event.title || item.title), C.el("small", {}, `${C.formatDate(event.at, true)} · ${C.t("version")} ${event.version}`))));
    });
  }

  async function init() {
    C.initLanguage();
    try {
      state.data = await C.loadData(); state.item = state.data.items.find(item => item.id === params.get("id"));
      if (!state.item) throw new Error("Item not found");
      document.getElementById("loading").hidden = true; document.getElementById("content").hidden = false; render();
      window.addEventListener("cm:language", render);
    } catch (error) { document.getElementById("loading").hidden = true; C.showError(document.getElementById("error"), error); }
  }
  document.addEventListener("DOMContentLoaded", init);
})();
