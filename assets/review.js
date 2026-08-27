(() => {
  "use strict";
  const C = window.CM;
  const state = { data: null, selected: new Set(), filters: { search: "", competitor: "", reason: "", source: "", suggested: "" }, saving: false };
  const $ = (id) => document.getElementById(id);
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function reviewItems() {
    return (state.data?.items || []).filter((item) => item.review_required === true);
  }

  function potentialMerchant(item) {
    return item?.suggested_record_type === "merchant_offer";
  }

  function potentialCampaign(item) {
    return item?.suggested_record_type === "campaign";
  }

  function separateMerchantEligible(item) {
    return potentialMerchant(item) && item?.source_type === "website" && item?.official_discovery === true && Boolean(officialEvidence(item));
  }

  function visibleItems() {
    const query = state.filters.search.trim().toLowerCase();
    return reviewItems().filter((item) => {
      if (state.filters.competitor && item.competitor_id !== state.filters.competitor) return false;
      if (state.filters.reason && !(item.review_reasons || []).includes(state.filters.reason)) return false;
      if (state.filters.source && item.source_type !== state.filters.source) return false;
      if (state.filters.suggested === "none" && item.suggested_record_type) return false;
      if (state.filters.suggested && state.filters.suggested !== "none" && item.suggested_record_type !== state.filters.suggested) return false;
      return !query || `${item.title || ""} ${item.snippet || ""}`.toLowerCase().includes(query);
    }).sort((a, b) => (Number(potentialCampaign(b)) * 2 + Number(potentialMerchant(b))) - (Number(potentialCampaign(a)) * 2 + Number(potentialMerchant(a))) || Number(b.review_priority || 0) - Number(a.review_priority || 0));
  }

  function option(value, label) { return C.el("option", { value }, label); }

  function fillFilters() {
    const items = reviewItems(), competitors = C.byId(state.data.competitors);
    const competitor = $("review-competitor"), reason = $("review-reason"), source = $("review-source"), suggested = $("review-suggested");
    C.clear(competitor); competitor.append(option("", C.t("all")), ...[...new Set(items.map((i) => i.competitor_id))].sort().map((id) => option(id, C.competitorName(competitors[id]))));
    C.clear(reason); reason.append(option("", C.t("allReasons")), ...[...new Set(items.flatMap((i) => i.review_reasons || []))].sort().map((value) => option(value, value.replaceAll("_", " "))));
    C.clear(source); source.append(option("", C.t("allSources")), ...[...new Set(items.map((i) => i.source_type).filter(Boolean))].sort().map((value) => option(value, C.t(value === "social" ? "posts" : value))));
    C.clear(suggested); suggested.append(option("", C.t("all")), option("merchant_offer", C.t("merchantCandidates")), option("campaign", C.t("suggestedCampaign")), option("none", C.t("suggestedUnclassified")));
    competitor.value = state.filters.competitor; reason.value = state.filters.reason; source.value = state.filters.source; suggested.value = state.filters.suggested;
    const campaignCount = items.filter(potentialCampaign).length;
    const merchantCount = items.filter(potentialMerchant).length;
    $("review-filter-campaigns").textContent = `${C.t("suggestedCampaign")} (${campaignCount})`;
    $("review-filter-merchants").textContent = `${C.t("merchantCandidates")} (${merchantCount})`;
  }

  function officialEvidence(item) {
    return item.official_evidence_url || item.official_campaign_page_url || item.primary_official_source_url || item.link || "";
  }

  function reasonPills(item) {
    return C.el("div", { class: "review-reasons" }, (item.review_reasons || []).map((reason) => C.pill(reason.replaceAll("_", " "), "warning")));
  }

  function quickAction(item, action) {
    if (action === "link_existing") return openLinkDialog([item.id]);
    if (action === "confirm_campaign" && item.source_type === "social") return openGroupDialog([item.id], "campaign");
    if (action === "confirm_merchant_offer" && item.source_type === "social") return openGroupDialog([item.id], "merchant_offer");
    return submitDecision({ action, item_ids: [item.id] });
  }

  function renderCard(item) {
    const competitors = C.byId(state.data.competitors), checked = state.selected.has(item.id), evidence = officialEvidence(item);
    const checkbox = C.el("input", { type: "checkbox", class: "review-card__check", checked, "aria-label": C.t("selectItems") });
    checkbox.addEventListener("change", () => { checkbox.checked ? state.selected.add(item.id) : state.selected.delete(item.id); updateBulk(); });
    return C.el("article", { class: `review-card${potentialMerchant(item) ? " review-card--merchant-candidate" : ""}` },
      C.el("div", { class: "review-card__selector" }, checkbox),
      C.el("div", { class: "review-card__content" },
        C.el("div", { class: "review-card__top" }, C.el("strong", {}, C.competitorName(competitors[item.competitor_id])), C.pill(C.contentLabel(item), "warning"), item.suggested_record_type ? C.pill(`${C.t("suggestedType")}: ${C.t(item.suggested_record_type)}`, potentialMerchant(item) ? "gold" : "info") : null),
        C.el("h2", {}, item.title || "—"), item.snippet ? C.el("p", {}, item.snippet) : null,
        reasonPills(item),
        C.el("div", { class: "review-card__meta" }, C.el("span", {}, `${C.t("source")}: ${item.platform || item.source_type || "—"}`), item.published_at ? C.el("span", {}, C.formatDate(item.published_at, true)) : null),
        evidence ? C.el("a", { class: "review-evidence", href: evidence, target: "_blank", rel: "noopener noreferrer" }, `${C.t("officialEvidence")} ↗`) : null,
        C.el("div", { class: "review-card__actions" },
          C.el("button", { class: "button button--primary", onclick: () => quickAction(item, "confirm_campaign") }, C.t("confirmCampaign")),
          C.el("button", { class: "button button--secondary", onclick: () => quickAction(item, "confirm_merchant_offer") }, C.t("confirmMerchant")),
          C.el("button", { class: "button button--ghost", onclick: () => quickAction(item, "link_existing") }, C.t("linkExisting")),
          C.el("button", { class: "button button--ghost", onclick: () => quickAction(item, "mark_not_campaign") }, C.t("markNotCampaign")),
          C.el("button", { class: "button button--ghost", onclick: () => quickAction(item, "mark_awareness") }, C.t("markAwareness"))
        )
      )
    );
  }

  function renderScanSummary() {
    const node = $("review-scan-summary"), scan = state.data?.full_review_scan;
    if (!node || !scan?.completed_at) { if (node) node.textContent = ""; return; }
    const linked = Number(scan.linked_social || 0);
    const duplicates = Number(scan.counted_duplicates_removed || 0) + Number(scan.review_duplicates_removed || 0);
    node.textContent = `${C.t("lastFullReviewScan")}: ${C.formatDate(scan.completed_at, true)} · ${C.t("reviewCleaned")}: ${Number(scan.cleaned || 0)} · ${C.t("autoLinked")}: ${linked} · ${C.t("duplicatesRemoved")}: ${duplicates}`;
  }

  function render() {
    const rows = visibleItems(), list = $("review-list"); C.clear(list);
    if (!rows.length) list.append(C.el("div", { class: "empty-state" }, C.t("noReviewItems")));
    else rows.forEach((item) => list.append(renderCard(item)));
    $("review-total").textContent = `${reviewItems().length} ${C.t("reviewRequired")}`;
    $("review-result-count").textContent = `${rows.length} ${C.t("results")}`;
    $("review-select-all").checked = rows.length > 0 && rows.every((item) => state.selected.has(item.id));
    renderScanSummary();
    updateBulk();
  }

  function selectedItems(ids = [...state.selected]) {
    const byId = C.byId(state.data.items); return ids.map((id) => byId[id]).filter(Boolean);
  }

  function ensureSameCompetitor(items) {
    if (!items.length) { alert(C.t("selectItems")); return false; }
    if (new Set(items.map((item) => item.competitor_id)).size !== 1) { alert(C.t("sameCompetitorRequired")); return false; }
    return true;
  }

  function updateBulk() {
    const bulk = $("review-bulk"); bulk.hidden = state.selected.size === 0;
    $("review-selected").textContent = `${C.t("selectedCount")}: ${state.selected.size}`;
  }

  function confirmSeparateMerchants(ids) {
    const items = selectedItems(ids);
    if (!items.length) return alert(C.t("selectItems"));
    if (items.some((item) => !separateMerchantEligible(item))) return alert(C.t("merchantBulkWebsiteOnly"));
    const message = C.t("bulkMerchantConfirm").replace("{count}", String(items.length));
    if (!window.confirm(message)) return;
    submitDecision({ action: "confirm_merchant_offers_bulk", item_ids: items.map((item) => item.id) });
  }

  function field(label, input) { return C.el("label", { class: "editor-field" }, C.el("span", {}, label), input); }
  function closeModal() { document.querySelector("#review-modal")?.remove(); }

  function openGroupDialog(ids, presetType = "campaign") {
    const items = selectedItems(ids); if (!ensureSameCompetitor(items)) return;
    const type = C.el("select", {}, option("campaign", C.t("campaign")), option("merchant_offer", C.t("merchant_offer"))); type.value = presetType;
    const category = C.el("select", {}, state.data.categories.filter((row) => row.id !== "merchant").map((row) => option(row.id, C.taxonomyName(row)))); category.value = items[0].campaign_category === "merchant" ? "other" : (items[0].campaign_category || "other");
    const title = C.el("input", { value: items[0].title || "", maxlength: 280 }), summary = C.el("textarea", { rows: 4, maxlength: 3000 }, items[0].snippet || ""), start = C.el("input", { type: "date" }), end = C.el("input", { type: "date" }), source = C.el("input", { type: "url", value: officialEvidence(items[0]), placeholder: "https://..." });
    const modal = C.el("div", { id: "review-modal", class: "modal-backdrop" }, C.el("section", { class: "modal" }, C.el("header", { class: "modal__header" }, C.el("h2", {}, C.t("createOneCampaign")), C.el("button", { class: "icon-button", onclick: closeModal }, "×")), C.el("div", { class: "modal__body" }, C.el("div", { class: "editor-grid" }, field(C.t("recordType"), type), field(C.t("category"), category), field(C.t("campaignTitle"), title), field(C.t("campaignSummary"), summary), field(C.t("startDate"), start), field(C.t("endDate"), end), field(C.t("officialSourceRequired"), source))), C.el("footer", { class: "modal__footer" }, C.el("button", { class: "button button--ghost", onclick: closeModal }, C.t("cancel")), C.el("button", { class: "button button--primary", onclick: () => { if (!source.value.trim()) return source.focus(); submitDecision({ action: ids.length === 1 && presetType !== "campaign" ? "confirm_merchant_offer" : "group_campaign", item_ids: ids, record_type: type.value, campaign_category: category.value, title: title.value.trim(), summary: summary.value.trim(), start_date: start.value, end_date: end.value, official_source_url: source.value.trim() }); } }, C.t("saveDecision")))));
    document.body.append(modal); modal.addEventListener("click", (event) => { if (event.target === modal) closeModal(); });
  }

  function openLinkDialog(ids) {
    const items = selectedItems(ids); if (!ensureSameCompetitor(items)) return;
    const campaigns = state.data.items.filter((item) => item.competitor_id === items[0].competitor_id && ["campaign", "merchant_offer"].includes(item.content_type) && item.active !== false);
    if (!campaigns.length) return openGroupDialog(ids);
    const select = C.el("select", {}, campaigns.map((item) => option(item.id, item.title || item.id)));
    const modal = C.el("div", { id: "review-modal", class: "modal-backdrop" }, C.el("section", { class: "modal modal--compact" }, C.el("header", { class: "modal__header" }, C.el("h2", {}, C.t("linkExisting")), C.el("button", { class: "icon-button", onclick: closeModal }, "×")), C.el("div", { class: "modal__body" }, field(C.t("chooseCampaign"), select)), C.el("footer", { class: "modal__footer" }, C.el("button", { class: "button button--ghost", onclick: closeModal }, C.t("cancel")), C.el("button", { class: "button button--primary", onclick: () => submitDecision({ action: "link_existing", item_ids: ids, target_campaign_id: select.value }) }, C.t("saveDecision")))));
    document.body.append(modal);
  }

  async function pollReview(requestId) {
    for (let attempt = 0; attempt < 360; attempt += 1) {
      const response = await fetch(`/__review-status?request_id=${encodeURIComponent(requestId)}`, { cache: "no-store", credentials: "same-origin" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok && response.status !== 202) throw new Error(payload.message || `HTTP ${response.status}`);
      if (payload.status === "completed") {
        if (payload.conclusion !== "success") throw new Error(payload.conclusion || C.t("reviewSaveFailed"));
        return;
      }
      await sleep(5000);
    }
    throw new Error("Review save timed out");
  }

  async function submitDecision(payload) {
    if (state.saving) return; state.saving = true; closeModal();
    document.querySelectorAll("button,input,select,textarea").forEach((node) => { if (!node.closest("header")) node.disabled = true; });
    const status = C.el("div", { class: "review-save-status" }, C.t("reviewSaving")); document.body.append(status);
    try {
      const response = await fetch("/__review", { method: "POST", credentials: "same-origin", cache: "no-store", headers: { "Content-Type": "application/json", "X-Requested-With": "competitor-monitor" }, body: JSON.stringify(payload) });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(response.status === 409 ? C.t("reviewBusy") : (result.message || `HTTP ${response.status}`));
      status.textContent = C.t("reviewQueued"); await pollReview(result.request_id); status.textContent = C.t("reviewSaved"); await sleep(1200); location.reload();
    } catch (error) {
      alert(`${C.t("reviewSaveFailed")}: ${error.message || error}`); status.remove(); state.saving = false; document.querySelectorAll("button,input,select,textarea").forEach((node) => { node.disabled = false; });
    }
  }

  function bind() {
    $("review-search").addEventListener("input", (event) => { state.filters.search = event.target.value; render(); });
    for (const [id, key] of [["review-competitor", "competitor"], ["review-reason", "reason"], ["review-source", "source"], ["review-suggested", "suggested"]]) $(id).addEventListener("change", (event) => { state.filters[key] = event.target.value; render(); });
    $("review-clear-filters").onclick = () => { state.filters = { search: "", competitor: "", reason: "", source: "", suggested: "" }; $("review-search").value = ""; fillFilters(); render(); };
    $("review-filter-campaigns").onclick = () => { state.selected.clear(); state.filters.suggested = "campaign"; state.filters.source = ""; $("review-suggested").value = "campaign"; $("review-source").value = ""; render(); };
    $("review-filter-merchants").onclick = () => { state.selected.clear(); state.filters.suggested = "merchant_offer"; state.filters.source = ""; $("review-suggested").value = "merchant_offer"; $("review-source").value = ""; render(); };
    $("review-select-all").onchange = (event) => { visibleItems().forEach((item) => event.target.checked ? state.selected.add(item.id) : state.selected.delete(item.id)); render(); };
    $("review-group").onclick = () => openGroupDialog([...state.selected]); $("review-link").onclick = () => openLinkDialog([...state.selected]);
    $("review-confirm-merchants").onclick = () => confirmSeparateMerchants([...state.selected]);
    $("review-not-campaign").onclick = () => submitDecision({ action: "mark_not_campaign", item_ids: [...state.selected] });
    $("review-awareness").onclick = () => submitDecision({ action: "mark_awareness", item_ids: [...state.selected] });
    $("review-clear-selection").onclick = () => { state.selected.clear(); render(); };
    $("review-full-scan").onclick = (event) => { if (window.confirm(C.t("fullReviewScanConfirm"))) C.triggerRefresh("all", event.currentTarget); };
    window.addEventListener("cm:language", () => { fillFilters(); render(); });
  }

  async function init() {
    C.initLanguage();
    try {
      await C.loadAuth();
      if (!C.isAdmin()) { $("loading").hidden = true; $("error").append(C.el("div", { class: "error-state" }, C.t("accessDenied"))); return; }
      state.data = await C.loadData(); fillFilters(); bind(); render(); $("loading").hidden = true; $("content").hidden = false; C.resumeRefresh();
    } catch (error) { $("loading").hidden = true; C.showError($("error"), error); }
  }
  document.addEventListener("DOMContentLoaded", init);
})();
