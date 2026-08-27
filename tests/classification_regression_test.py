"""Regression tests for source-aware official campaign classification."""
from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import enhance  # noqa: E402

config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def official_item(**values):
    row = {
        "id": "detected:test",
        "competitor_id": "stc-bank",
        "source_type": "website",
        "official_discovery": True,
        "content_type": "review",
        "campaign_category": "remittance",
        "title": "Transfer internationally and enter the draw",
        "snippet": "Make an international transfer and enter the draw to win a car every week and cash prizes.",
        "evidence_snapshot": "The campaign runs from 19 August 2026 to 19 October 2026",
        "link": "https://stcbank.com.sa/en/web/guest/w/transfer-internationally-and-enter-the-draw",
        "official_campaign_page_url": "https://stcbank.com.sa/en/web/guest/w/transfer-internationally-and-enter-the-draw",
        "source_verification": {"status": "verified_website", "verification_method": "official_website_page", "source_url": "https://stcbank.com.sa/en/web/guest/w/transfer-internationally-and-enter-the-draw"},
        "start_date": "2026-08-19T00:00:00+00:00",
        "end_date": "2026-10-19T00:00:00+00:00",
        "active": True,
        "review_required": True,
        "review_reasons": ["ai_needs_review", "new_official_campaign_needs_review"],
    }
    row.update(values)
    return row


stc = official_item()
data = {"items": [stc]}
assert enhance.apply_verified_official_classification(data, config) == 1
assert stc["content_type"] == "campaign"
assert stc["review_required"] is False
assert stc["classification_method"] == "verified_official_rules_v6"

# The cache key must change when a page moves from unverified to verified.
unverified = official_item(source_verification={"status": "needs_review"})
verified = copy.deepcopy(unverified)
verified["source_verification"]["status"] = "verified_website"
assert enhance.classification_content_key(unverified) != enhance.classification_content_key(verified)

barq = official_item(
    id="detected:barq",
    competitor_id="barq",
    campaign_category="other",
    title="Restaurant partner offer",
    snippet="Get a discount 20% at the restaurant when paying with a barq Visa card.",
    evidence_snapshot="Partner discount valid at the restaurant.",
    link="https://barq.com/ar/offers/restaurant-offer/",
    official_campaign_page_url="https://barq.com/ar/offers/restaurant-offer/",
)
alinma = official_item(
    id="detected:alinma",
    competitor_id="alinma-pay",
    campaign_category="musaned",
    title="Musaned Salary Cashback",
    snippet="Transfer domestic worker salary and enter the monthly draw for 100% cashback.",
    evidence_snapshot="The campaign is a monthly Musaned salary draw.",
    link="https://alinmapay.com.sa/Offers/Musaned-Cashback",
    official_campaign_page_url="https://alinmapay.com.sa/Offers/Musaned-Cashback",
)
ambiguous = official_item(
    id="detected:ambiguous",
    competitor_id="urpay",
    campaign_category="other",
    title="Learn more about urpay",
    snippet="Discover our services.",
    evidence_snapshot="General product information.",
    link="https://www.urpay.com.sa/en/services/example",
    official_campaign_page_url="https://www.urpay.com.sa/en/services/example",
)
payload = {"items": [barq, alinma, ambiguous]}
enhance.apply_verified_official_classification(payload, config)
assert barq["content_type"] == "merchant_offer"
assert alinma["content_type"] == "campaign"
assert ambiguous["content_type"] == "review"


def merchant_offer(**values):
    row = {
        "id": "detected:alinma-pay:iherb",
        "competitor_id": "alinma-pay",
        "source_type": "website",
        "official_discovery": True,
        "content_type": "merchant_offer",
        "campaign_category": "merchant",
        "title": "عرض آيهيرب 40%",
        "summary": "استمتع بخصم 40% على مشترياتك من آيهيرب. يسري العرض من 21 أغسطس 2026 حتى 4 سبتمبر 2026.",
        "link": "https://www.alinmapay.com.sa/Offers/iHerb_Aug_2026",
        "official_campaign_page_url": "https://www.alinmapay.com.sa/Offers/iHerb_Aug_2026",
        "source_verification": {"status": "verified_website", "verification_method": "official_website_page"},
        "verified": True,
        "start_date": "2026-08-21T00:00:00+00:00",
        "end_date": "2026-09-04T00:00:00+00:00",
        "active": True,
        "review_required": False,
        "review_reasons": [],
        "social_links": {},
    }
    row.update(values)
    return row


def social_post(post_id, title, **values):
    row = {
        "id": post_id,
        "competitor_id": "alinma-pay",
        "source_type": "social",
        "platform": "instagram",
        "content_type": "social_post",
        "campaign_category": "merchant",
        "title": title,
        "snippet": title,
        "link": f"https://www.instagram.com/p/{post_id.rsplit(':', 1)[-1]}/",
        "published_at": "2026-08-24T12:20:00+00:00",
        "active": True,
        "review_required": True,
        "review_reasons": ["social_campaign_match_uncertain"],
    }
    row.update(values)
    return row


social_config = copy.deepcopy(config)
social_config.setdefault("ai", {})["classification_enabled"] = False
iherb = merchant_offer()
iherb_instagram = social_post("post:alinma-pay:instagram:iherb", "ناوي تطلب من آيهيرب؟ استفد من خصم 40% ببطاقات الإنماء باي")
iherb_x = social_post("post:alinma-pay:x:iherb", "اطلب من آيهيرب واستفد من خصم 40%", platform="x", link="https://x.com/alinmapay/status/100")
wrong_value = social_post("post:alinma-pay:x:iherb-wrong", "عرض آيهيرب بخصم 20%", platform="x", link="https://x.com/alinmapay/status/101")
wrong_date = social_post("post:alinma-pay:x:iherb-date", "عرض آيهيرب بخصم 40%. العرض ساري حتى 5 سبتمبر 2026.", platform="x", link="https://x.com/alinmapay/status/102")
merchant_payload = {"items": [iherb, iherb_instagram, iherb_x, wrong_value, wrong_date]}
enhance.enrich_social(merchant_payload, {}, social_config, {"items": {}})
for linked in (iherb_instagram, iherb_x):
    assert linked["campaign_id"] == iherb["id"]
    assert linked["content_type"] == "social_post"
    assert linked["review_required"] is False
    assert linked["match_method"] == "merchant_name_value_date"
assert iherb["social_posts_total"] == 2
assert wrong_value.get("campaign_id") is None
assert wrong_value["review_required"] is True
assert "merchant_offer_match_conflict" in wrong_value["review_reasons"]
assert wrong_date.get("campaign_id") is None
assert wrong_date["review_required"] is True
assert "merchant_offer_match_conflict" in wrong_date["review_reasons"]

# The same explicit Merchant Offer published across official social platforms becomes one
# canonical offer, while each post remains a linked social evidence record.
taco_facebook = social_post(
    "post:mobily-pay:facebook:taco",
    "مضبطينك بخصم 20% مع تاكو هت ولا تنسى الكود",
    competitor_id="mobily-pay",
    platform="facebook",
    campaign_category="merchant",
    published_at="2026-08-25T18:08:14+00:00",
    review_reasons=["potential_merchant_offer_unmatched"],
)
taco_instagram = social_post(
    "post:mobily-pay:instagram:taco",
    "مضبطينك بخصم 20% مع تاكو هت ولا تنسى الكود",
    competitor_id="mobily-pay",
    platform="instagram",
    campaign_category="merchant",
    published_at="2026-08-25T18:06:59+00:00",
    review_reasons=["potential_merchant_offer_unmatched"],
)
taco_payload = {"items": [taco_facebook, taco_instagram]}
taco_offers = enhance.promote_repeated_social_merchant_offers(taco_payload)
assert len(taco_offers) == 1
assert taco_offers[0]["content_type"] == "merchant_offer"
assert taco_offers[0]["classification_method"] == "official_social_cross_platform_match"
assert taco_offers[0]["start_date"].startswith("2026-08-25")
assert {taco_facebook["campaign_id"], taco_instagram["campaign_id"]} == {taco_offers[0]["id"]}
assert taco_facebook["review_required"] is False and taco_instagram["review_required"] is False

# A single-platform official social offer is auto-registered only after the AI returns an
# explicit Merchant Offer decision at 90% confidence or higher.
solo_offer = social_post(
    "post:urpay:x:solo-merchant",
    "Get 25% off at Blue Cafe with your urpay card",
    competitor_id="urpay",
    platform="x",
    campaign_category="merchant",
)
solo_payload = {"items": [solo_offer]}
solo_config = copy.deepcopy(config)
solo_config["ai"].update({"classification_enabled": True, "classification_max_items_per_run": 10, "classification_recent_days": 365})
original_ai_batched = enhance.ai_classify_batched
try:
    enhance.ai_classify_batched = lambda posts, campaigns, state, cfg: {
        solo_offer["id"]: {
            "id": solo_offer["id"], "decision": "standalone", "record_type": "merchant_offer",
            "category": "merchant", "matched_campaign_id": None, "confidence": 0.95,
            "merchant_name": "Blue Cafe",
        }
    } if solo_offer in posts else {}
    enhance.enrich_social(solo_payload, {}, solo_config, {"items": {}})
finally:
    enhance.ai_classify_batched = original_ai_batched
solo_records = [row for row in solo_payload["items"] if row.get("content_type") == "merchant_offer"]
assert len(solo_records) == 1
assert solo_offer["campaign_id"] == solo_records[0]["id"]
assert solo_offer["review_required"] is False
assert solo_records[0]["merchant_name"] == "Blue Cafe"

# Similar merchant wording with a different benefit is never collapsed by fuzzy title alone.
different_value_payload = {"items": [
    social_post("post:merchant:x:20", "خصم 20% لدى المطعم", competitor_id="barq", platform="x", campaign_category="merchant"),
    social_post("post:merchant:instagram:30", "خصم 30% لدى المطعم", competitor_id="barq", platform="instagram", campaign_category="merchant"),
]}
assert enhance.promote_repeated_social_merchant_offers(different_value_payload) == []

# A freshly rediscovered named Barq partner card is trusted as first-party listing evidence
# even when the browser-only detail route returns 404 to the direct verification client.
barq_listing = official_item(
    id="detected:barq:vogacloset",
    competitor_id="barq",
    title="VogaCloset × برق",
    snippet="تقدم فيزا بالشراكة مع VogaCloset عرضًا لحاملي بطاقة برق فيزا.",
    evidence_snapshot="يسري هذا العرض ابتداءً من 16 ابريل 2026 وحتى 30 سبتمبر 2026",
    link="https://barq.com/ar/offers/vogacloset-offer/",
    official_campaign_page_url="https://barq.com/ar/offers/vogacloset-offer/",
    verified=True,
    last_seen=enhance.iso(enhance.now()),
    source_verification={"status": "failed", "verification_method": "official_website_page", "error": "HTTP 404"},
)
barq_listing_payload = {"items": [barq_listing]}
enhance.apply_verified_official_classification(barq_listing_payload, config)
assert barq_listing["content_type"] == "merchant_offer"
assert barq_listing["review_required"] is False
assert barq_listing["classification_method"] == "verified_official_listing_merchant_v1"

# An explicit end date printed on the official social poster fills a missing website date.
aliexpress = merchant_offer(
    id="detected:tiqmo:aliexpress",
    competitor_id="tiqmo",
    title="AliExpress offer",
    summary="Back-to-school savings with the tiqmo Platinum card.",
    link="https://tiqmo.com/en/offers/aliexpress",
    official_campaign_page_url="https://tiqmo.com/en/offers/aliexpress",
    start_date=None,
    end_date=None,
)
aliexpress_post = social_post(
    "post:tiqmo:instagram:aliexpress",
    "Get SAR 65 off at AliExpress. Offer valid until 31 August 2026.",
    competitor_id="tiqmo",
    link="https://www.instagram.com/p/ALIEXPRESS/",
    published_at="2026-08-21T18:00:00+00:00",
)
date_payload = {"items": [aliexpress, aliexpress_post]}
enhance.enrich_social(date_payload, {}, social_config, {"items": {}})
assert aliexpress_post["campaign_id"] == aliexpress["id"]
assert aliexpress_post["review_required"] is False
assert aliexpress["end_date"].startswith("2026-08-31")
assert aliexpress["date_extraction_method"] == "linked_official_social_post"

# Winner mechanics stay eligible for campaign matching; only actual result announcements
# are quarantined as winner posts.
assert not enhance.is_winner_announcement({"title": "Spend SAR 100 and enter to win — one winner every week"})
assert not enhance.is_winner_announcement({"title": "Spend SAR 100 and enter to win — one winner every week", "post_role": "winner_announcement"})
assert enhance.is_winner_announcement({"title": "Congratulations to our winner, who received the prize"})

# Full review reconciliation scans the existing backlog, links safe matches, clears ordinary
# awareness posts and leaves genuinely new promotions as Potential Campaign/Merchant Offer.
canonical_campaign = official_item(
    id="campaign:stc-bank:zero-fee-india",
    content_type="campaign",
    title="Zero-fee international transfers to India",
    snippet="Transfer internationally to India with zero fees through STC Bank.",
    evidence_snapshot="Valid from 19 August 2026 to 19 October 2026.",
    review_required=False,
    review_reasons=[],
    verified=True,
)
campaign_post = social_post(
    "post:stc-bank:instagram:zero-fee-india",
    "Transfer internationally to India with zero fees until 19 October 2026",
    competitor_id="stc-bank",
    campaign_category="remittance",
)
awareness_post = social_post(
    "post:stc-bank:x:security",
    "Protect your account and never share your password",
    competitor_id="stc-bank",
    campaign_category="other",
    platform="x",
    link="https://x.com/stcbank/status/900",
)
potential_merchant = social_post(
    "post:stc-bank:instagram:blue-cafe",
    "Get 25% discount at Blue Cafe with your card",
    competitor_id="stc-bank",
    campaign_category="merchant",
)
website_duplicate = official_item(
    id="detected:stc-bank:zero-fee-india-copy",
    title="صفر رسوم على التحويل الدولي إلى الهند",
    snippet="حوّل دوليًا إلى الهند بدون رسوم.",
    link=canonical_campaign["official_campaign_page_url"],
    official_campaign_page_url=canonical_campaign["official_campaign_page_url"],
)
manual_review = social_post(
    "post:stc-bank:x:manual",
    "A manually approved review decision",
    competitor_id="stc-bank",
    platform="x",
    link="https://x.com/stcbank/status/901",
    review_approved=True,
)
review_payload = {"items": [canonical_campaign, campaign_post, awareness_post, potential_merchant, website_duplicate, manual_review]}
scan = enhance.rescan_needs_review(review_payload, config)
assert scan["linked_social"] == 1
assert campaign_post["campaign_id"] == canonical_campaign["id"]
assert campaign_post["review_required"] is False
assert awareness_post["content_type"] == "awareness" and awareness_post["review_required"] is False
assert potential_merchant["suggested_record_type"] == "merchant_offer" and potential_merchant["review_required"] is True
assert website_duplicate["duplicate_candidate_id"] == canonical_campaign["id"]
assert manual_review["review_required"] is True
assert enhance.consolidate_duplicates(review_payload) == 1
assert website_duplicate["id"] not in {row["id"] for row in review_payload["items"]}

# A lower-confidence review URL is retained as alternate evidence and never replaces the
# canonical verified website URL during deduplication.
canonical_url = "https://stcbank.com.sa/en/w/canonical-offer"
target = official_item(id="campaign:canonical", content_type="campaign", official_campaign_page_url=canonical_url, primary_official_source_url=canonical_url, link=canonical_url, review_required=False, verified=True)
source = official_item(id="detected:copy", official_campaign_page_url="https://stcbank.com.sa/en/w/unverified-copy", primary_official_source_url="https://stcbank.com.sa/en/w/unverified-copy", link="https://stcbank.com.sa/en/w/unverified-copy", source_verification={"status": "needs_review"})
enhance.merge_into_campaign(target, source)
assert target["official_campaign_page_url"] == canonical_url
assert source["official_campaign_page_url"] in target["alternate_official_source_urls"]

# Generic card mechanics are not enough to link a different promotion. Prize amounts and
# specialised products must agree before the full scan auto-links them.
zero_fee_card = official_item(
    id="campaign:tiqmo:zero-fees",
    competitor_id="tiqmo",
    content_type="campaign",
    campaign_category="card",
    title="Zero International Card Transaction Fees",
    snippet="Use the Platinum card with 0% international transaction fees.",
    review_required=False,
    review_reasons=[],
    verified=True,
)
new_spend_campaign = social_post(
    "post:tiqmo:facebook:new-spend",
    "Spend More, Win More! Every riyal spent gets you closer to win SAR 100,000",
    competitor_id="tiqmo",
    campaign_category="card",
    platform="facebook",
)
assert enhance.campaign_record_match(new_spend_campaign, [zero_fee_card], include_inactive=True) == (None, None)

musaned_campaign = official_item(
    id="campaign:alinma-pay:musaned",
    competitor_id="alinma-pay",
    content_type="campaign",
    campaign_category="musaned",
    title="Musaned Salary Transfer – 100% Cashback Draw",
    snippet="Transfer a domestic worker salary through Musaned for a chance at 100% cashback.",
    review_required=False,
    review_reasons=[],
    verified=True,
)
generic_card_cashback = social_post(
    "post:alinma-pay:tiktok:new-customer",
    "New customers get 100% cashback when shopping online with the card",
    competitor_id="alinma-pay",
    campaign_category="card",
    platform="tiktok",
)
assert enhance.campaign_record_match(generic_card_cashback, [musaned_campaign], include_inactive=True) == (None, None)

# Management reporting must use the market event date, never the time of Admin review,
# record ingestion, reclassification or missing-field completion.
fixed_now = enhance.dt("2026-08-27T12:00:00+00:00")
original_now = enhance.now
enhance.now = lambda: fixed_now


def management_campaign(record_id, start_date="2025-01-01T00:00:00+00:00", **values):
    row = {
        "id": record_id,
        "competitor_id": "tiqmo",
        "content_type": "campaign",
        "campaign_category": "card",
        "title": "Spend More, Win More!",
        "summary": "Spend with the card for a chance to win.",
        "start_date": start_date,
        "end_date": "2026-09-30T00:00:00+00:00",
        "active": True,
        "current_status": "Active",
        "verified": True,
        "review_required": False,
        "source_verification": {"status": "verified_website"},
        "change_history": [],
    }
    row.update(values)
    return row


control = management_campaign("campaign:control")
enhance.annotate_market_timing([control])
control_snapshot = enhance.snapshot_campaigns([control])

# A historical campaign reviewed today is an inventory correction, not a market launch.
late_review = management_campaign(
    "manual:review:late",
    start_date="2026-08-01T00:00:00+00:00",
    source_type="manual",
    review_approved=True,
    reviewed_at="2026-08-27T11:30:00+00:00",
    first_seen="2026-08-27T11:30:00+00:00",
)
late_rows = [copy.deepcopy(control), late_review]
enhance.annotate_market_timing(late_rows)
late_delta = enhance.material_delta(control_snapshot, enhance.snapshot_campaigns(late_rows), late_rows, "2026-08-27T08:00:00+00:00")
assert not late_delta["market_launches"]
assert late_delta["inventory_adjustment_count"] >= 1

# Filling a previously missing end date is data enrichment, even when completed today.
before_backfill = management_campaign("campaign:backfill", end_date=None)
enhance.annotate_market_timing([before_backfill])
after_backfill = copy.deepcopy(before_backfill)
after_backfill["end_date"] = "2026-09-30T00:00:00+00:00"
after_backfill["change_history"] = [{"at": "2026-08-27T11:00:00+00:00", "type": "end_date_updated"}]
enhance.annotate_market_timing([after_backfill])
backfill_delta = enhance.material_delta(enhance.snapshot_campaigns([before_backfill]), enhance.snapshot_campaigns([after_backfill]), [after_backfill], "2026-08-27T08:00:00+00:00")
assert not backfill_delta["market_updates"]
assert backfill_delta["inventory_adjustment_count"] == 1

# A verified source-side change from one known value to another is a genuine market update.
before_extension = management_campaign("campaign:extension", end_date="2026-09-01T00:00:00+00:00")
enhance.annotate_market_timing([before_extension])
after_extension = copy.deepcopy(before_extension)
after_extension["end_date"] = "2026-10-01T00:00:00+00:00"
after_extension["change_history"] = [{"at": "2026-08-27T11:00:00+00:00", "type": "source_content_changed"}]
enhance.annotate_market_timing([after_extension])
extension_delta = enhance.material_delta(enhance.snapshot_campaigns([before_extension]), enhance.snapshot_campaigns([after_extension]), [after_extension], "2026-08-27T08:00:00+00:00")
assert extension_delta["market_updates"][0]["fields"] == ["end_date"]
assert after_extension["market_last_changed"] == "2026-08-27T11:00:00+00:00"

# A campaign with a verified recent start date is a real launch, even if discovered later.
recent_launch = management_campaign("campaign:recent", start_date="2026-08-26T00:00:00+00:00")
recent_rows = [copy.deepcopy(control), recent_launch]
enhance.annotate_market_timing(recent_rows)
recent_delta = enhance.material_delta(control_snapshot, enhance.snapshot_campaigns(recent_rows), recent_rows, "2026-08-27T08:00:00+00:00")
assert [row["id"] for row in recent_delta["market_launches"]] == ["campaign:recent"]

# A new social post attached to an older campaign is context, not a relaunch.
old_with_new_post = management_campaign("campaign:old-social", start_date="2026-08-01T00:00:00+00:00", social_first_post="2026-08-27T10:00:00+00:00")
social_rows = [copy.deepcopy(control), old_with_new_post]
enhance.annotate_market_timing(social_rows)
social_delta = enhance.material_delta(control_snapshot, enhance.snapshot_campaigns(social_rows), social_rows, "2026-08-27T08:00:00+00:00")
assert not social_delta["market_launches"]

# Every approved campaign receives a Start Date. The priority is an explicit official date,
# then the earliest confirmed official publication/post, then a clearly marked first-observed
# estimate. The last fallback must never be reported as a market launch.
explicit_start = management_campaign("campaign:start:official", start_date="2026-08-10T00:00:00+00:00")
confirmed_post_start = management_campaign(
    "campaign:start:confirmed-post",
    start_date=None,
    published_at="2026-08-20T09:00:00+00:00",
    social_first_post="2026-08-18T18:30:00+00:00",
    linked_posts=[{
        "id": "post:start:confirmed",
        "link": "https://www.instagram.com/p/STARTCONFIRMED/",
        "published_at": "2026-08-18T18:30:00+00:00",
    }],
    first_seen="2026-08-22T00:00:00+00:00",
)
observed_start = management_campaign(
    "campaign:start:observed",
    start_date=None,
    published_at=None,
    social_first_post=None,
    linked_posts=[],
    first_seen="2026-08-23T14:00:00+00:00",
)
start_date_payload = {"items": [explicit_start, confirmed_post_start, observed_start]}
start_stats = enhance.ensure_campaign_start_dates(start_date_payload)
assert start_stats == {
    "official": 1,
    "from_verified_post": 1,
    "from_first_observed": 1,
    "remaining_missing": 0,
    "at": "2026-08-27T12:00:00+00:00",
}
assert confirmed_post_start["start_date"].startswith("2026-08-18")
assert confirmed_post_start["start_date_basis"] == "first_verified_social_post"
assert confirmed_post_start["start_date_source_url"].endswith("/STARTCONFIRMED/")
assert enhance.campaign_market_date(confirmed_post_start)[1] == "first_official_campaign_post"
published_evidence = management_campaign(
    "campaign:start:official-publication",
    start_date="2026-08-20T09:00:00+00:00",
    start_date_basis="first_verified_social_post",
    start_date_evidence_type="record_publication",
)
assert enhance.campaign_market_date(published_evidence)[1] == "official_published_date"
assert observed_start["start_date"].startswith("2026-08-23")
assert observed_start["start_date_basis"] == "first_observed"
assert observed_start["start_date_estimated"] is True
assert enhance.campaign_market_date(observed_start) == (None, None)
assert all(enhance.dt(row.get("start_date")) for row in start_date_payload["items"])

summary = enhance.deterministic_summary(late_rows, late_delta)
assert "executive_view" in summary and "recommended_actions" in summary
assert "No verified market launch" in summary["key_developments"][0]
assert "1 added" not in json.dumps(summary)
assert enhance.MANAGEMENT_EXPIRY_DAYS == 7
assert all("within 30 days" not in row for row in summary["management_attention"])

chart_source = (ROOT / "assets" / "index.js").read_text(encoding="utf-8")
chart_logic = chart_source.split("function campaignChangeValues", 1)[1].split("function renderSocialChart", 1)[0]
assert "market_launch_date" in chart_logic and "market_last_changed" in chart_logic and "market_expiry_date" in chart_logic
assert "item.first_seen" not in chart_logic and "item.last_changed" not in chart_logic
assert "state.campaignChangePeriod" in chart_logic
assert "item.market_expiry_date || item.end_date" in chart_logic
index_html = (ROOT / "index.html").read_text(encoding="utf-8")
assert 'id="campaign-change-period-filter"' in index_html
assert all(f'value="{days}"' in index_html for days in (7, 14, 30))

# Published Date remains internal social evidence; campaign-facing pages and Excel show only
# Start Date and End Date.
item_source = (ROOT / "assets" / "item.js").read_text(encoding="utf-8")
common_source = (ROOT / "assets" / "common.js").read_text(encoding="utf-8")
excel_source = (ROOT / "export_excel.py").read_text(encoding="utf-8")
assert 'i.source_type === "social" ? [[C.t("published")' in item_source
assert 'const showPublished=item.source_type==="social"' in common_source
assert 'showPublished?field(t("published"),pub):null' in common_source
assert '("E","published_at")' not in excel_source
assert '[("F","start_date"),("G","end_date")]' in excel_source
enhance.now = original_now

# Detail verification must stop starting new network calls when its wall-clock budget is
# exhausted. Unchecked records remain in the dataset and keep their last-known-good fields.
budget_config = copy.deepcopy(config)
budget_config["settings"].update({
    "detail_verification_time_budget_seconds": 0.055,
    "detail_verification_max_timeout_seconds": 5,
    "detail_verification_retries": 0,
    "max_detail_checks_per_run": 24,
})
budget_items = [
    official_item(
        id=f"campaign:budget:{index}",
        content_type="campaign",
        link=f"https://example.com/offer-{index}",
        official_campaign_page_url=f"https://example.com/offer-{index}",
        source_verification={"status": "verified_website"},
        review_required=False,
        review_reasons=[],
    )
    for index in range(8)
]


class SlowFailingSession:
    def __init__(self):
        self.headers = {}

    def mount(self, *_args, **_kwargs):
        return None

    def get(self, *_args, **_kwargs):
        time.sleep(0.035)
        raise TimeoutError("simulated slow source")


original_session = enhance.requests.Session
try:
    enhance.requests.Session = SlowFailingSession
    budget_data = {"items": budget_items, "source_status": []}
    enhance.verify_details(budget_data, {}, budget_config, {"items": {}})
finally:
    enhance.requests.Session = original_session

assert 1 <= budget_data["detail_verification_stats"]["network_checks"] < len(budget_items)
assert budget_data["detail_verification_stats"]["elapsed_seconds"] < 0.5
assert len(budget_data["items"]) == len(budget_items)

print("Source-aware classification regression tests passed")
